"""TabDiff behind the SynOmicsBench synthesizer interface.

Gives `TabDiff <https://github.com/MinkaiXu/TabDiff>`_ (Shi et al., ICLR 2025) the same call
shape as ``CTGANsynthesizer`` / ``TVAEsynthesizer``::

    synth = TabDiffsynthesizer(output_path="./results/tabdiff", metadata=metadata)
    synthetic = synth.generate(
        data=df, data_ids=list(df.index), n_samples=len(df), seed=42,
        fit_params={"epochs": 3000},
        output_filename="tabdiff.csv",
    )

The TabDiff sources ship with this package, unmodified, under
``synomicsbench/third_party/tabdiff`` (commit ``5ecdb33``, see ``VENDORED.md`` there). Every
adaptation is applied at run time by this module. Its extra dependencies are installed with
``pip install "synomicsbench[tabdiff]"``.

Every hyperparameter comes from TabDiff's own ``tabdiff/configs/tabdiff_configs.toml``, read at
fit time and never written. The construction sequence mirrors TabDiff's ``tabdiff/main.py``,
including the two overrides its ``main.py:212-214`` applies on a default run
(``power_mean_per_column`` / ``log_linear_per_column``, the learnable per-column noise
schedules).

Three things are supplied by this wrapper rather than read from the toml. None of them is a model
hyperparameter, and ``main.py`` passes all three the same way:

``sample_batch_size``
    How many noise vectors are denoised *per pass* at sampling time: memory chunking, not a
    sample count. ``sample_all`` (``unified_ctime_diffusion.py:216``) uses it without clamping
    it to the number of rows requested, so the shipped value of 10,000 would denoise 10,000 rows
    to keep a few hundred. It is set to the number of rows actually requested.

``metrics`` / ``logger``
    ``main.py`` builds a ``TabMetrics`` and a ``wandb`` run. The metrics are replaced by a no-op:
    TabDiff's internal suite (density / MLE / C2ST / DCR) compares against a holdout, and the
    model is trained on the whole cohort, as CTGAN and TVAE are, so those numbers would be
    computed against training data. Fidelity is assessed by SynOmicsBench's own metrics instead.
    The wandb run is replaced by ``_EpochLog``, which writes the per-epoch training curve to
    ``train_log.csv`` in the output directory.

``check_val_every`` keeps its shipped value of 2,000 unless overridden. With the no-op metrics the
periodic evaluation still saves both models and samples a full synthetic cohort from each, so
long runs usually set it past the last epoch through ``config_overrides``.
"""

from __future__ import annotations

import contextlib
import copy
import importlib
import importlib.util
import json
import os
import random
import sys
import time
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from synomicsbench.synthesizer.BaseSynthesizer import BaseSynthesizer

_CATEGORICAL_KINDS = ("ordinal_categorical", "dummy_categorical", "missing_categorical")

TABDIFF_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "third_party", "tabdiff")

# Top-level names the vendored TabDiff code imports itself under.
_TABDIFF_MODULES = ("src", "tabdiff", "utils_train", "process_dataset")
_EXTRA_DEPENDENCIES = ("icecream", "category_encoders", "tomli", "tomli_w")


def _prepare_tabdiff_imports() -> None:
    """Put the vendored TabDiff on ``sys.path`` and refuse a foreign module of the same name.

    TabDiff imports its packages by short top-level names (``import src``,
    ``from tabdiff.trainer import Trainer``). If a different module with one of those names is
    already imported, Python would hand that one back, so it is reported instead of used.
    """
    missing = [name for name in _EXTRA_DEPENDENCIES if importlib.util.find_spec(name) is None]
    if missing:
        raise ImportError(f"TabDiff needs {missing}. Install them with "
                          f"pip install \"synomicsbench[tabdiff]\"")
    for name in _TABDIFF_MODULES:
        module = sys.modules.get(name)
        if module is None:
            continue
        locations = [getattr(module, "__file__", None) or ""] + list(getattr(module, "__path__", []))
        if not any(os.path.abspath(loc).startswith(TABDIFF_DIR) for loc in locations if loc):
            raise ImportError(
                f"a module named {name!r} is already imported from {locations[0] or locations[1:]}; "
                f"TabDiff needs that name for its own code. Run TabDiff in a process that has "
                f"not imported it."
            )
    if TABDIFF_DIR not in sys.path:
        sys.path.insert(0, TABDIFF_DIR)


@contextlib.contextmanager
def _pushd(path: str):
    """TabDiff resolves ``data/...`` relative to the working directory, so run inside one."""
    prev = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(prev)


@contextlib.contextmanager
def _clean_argv():
    """``process_dataset.py`` calls ``parse_args()`` at module level (line 23)."""
    saved = sys.argv
    sys.argv = [saved[0] if saved else "process_dataset.py"]
    try:
        yield
    finally:
        sys.argv = saved


class _NullMetrics:
    """The four attributes ``Trainer`` touches (``trainer.py`` lines 405/420/438/450)."""

    def __init__(self, info: dict, real_data_size: int) -> None:
        self.info = info
        self.real_data_size = real_data_size

    def evaluate(self, syn_data):
        return {}, {}

    def plot_density(self, syn_data):
        from PIL import Image

        return Image.new("RGB", (1, 1))


class _EpochLog:
    """Stands in for ``main.py``'s wandb run and writes one CSV row per epoch instead.

    ``Trainer`` calls ``define_metric`` (line 133) and ``log`` (line 289, once per epoch, and
    once more after training with only ``training_time``). Each epoch row keeps the training
    losses, the learning rate and the continuous-loss weight; the per-column noise parameters
    (one key per column) are not kept. The row is flushed at once, so a job killed at its
    walltime still leaves the curve up to that point.

    The EMA-model loss is computed by ``Trainer.compute_loss`` (line 244) but never put into the
    logged dict, so ``watch_ema_loss`` wraps that method to record it here. With ``every > 1``
    the wrapper evaluates it only every ``every`` epochs and on the last one, and returns NaN
    otherwise. Its only consumer is the best-EMA checkpoint test at line 253, for which
    ``nan < best`` is False, and that test is gated on epoch > 4000 anyway. The EMA weights
    themselves are still updated every epoch (lines 222-224), which this does not touch.

    ``wall_s`` is training time since epoch 0, summed over every job of a resumed run.
    ``on_epoch_end`` is called with the epoch number after each row is written.
    """

    COLUMNS = ["epoch", "wall_s", "lr", "closs_weight", "dloss", "closs", "total",
               "ema_dloss", "ema_closs", "ema_total"]

    def __init__(self, path: str) -> None:
        self.path = path
        self._fh = None
        self._ema: Dict[int, tuple] = {}
        self.t0 = time.time()
        self.on_epoch_end = None

    def open(self, resume_epoch: int = 0, wall_s: float = 0.0) -> None:
        """Start the CSV, or continue it after ``resume_epoch``. Rows past that epoch were
        written by a job that was stopped before its next checkpoint; they are trained again,
        so they are dropped."""
        kept = []
        if resume_epoch and os.path.exists(self.path):
            with open(self.path) as fh:
                next(fh, None)
                kept = [line for line in fh
                        if line.split(",", 1)[0].isdigit() and int(line.split(",", 1)[0]) <= resume_epoch]
        self._fh = open(self.path, "w")
        self._fh.write(",".join(self.COLUMNS) + "\n")
        self._fh.writelines(kept)
        self._fh.flush()
        self.t0 = time.time() - wall_s

    def watch_ema_loss(self, trainer, every: int = 1) -> None:
        evaluate = trainer.compute_loss

        def compute_loss():
            epoch = trainer.curr_epoch
            if epoch % every and epoch != trainer.steps:
                return float("nan"), float("nan")
            dloss, closs = evaluate()
            self._ema[epoch] = (dloss, closs)
            return dloss, closs

        trainer.compute_loss = compute_loss

    def define_metric(self, *args, **kwargs) -> None:
        pass

    def log(self, values: dict, *args, **kwargs) -> None:
        if "epoch" not in values:
            return
        epoch = int(values["epoch"])
        ema_d, ema_c = self._ema.pop(epoch, (float("nan"), float("nan")))
        row = [epoch, round(time.time() - self.t0, 2), values["lr"], values["closs_weight"],
               values["loss/d_loss"], values["loss/c_loss"], values["loss/total_loss"],
               ema_d, ema_c, ema_d + ema_c]
        self._fh.write(",".join(f"{v:.6g}" if isinstance(v, float) else str(v) for v in row) + "\n")
        self._fh.flush()
        if self.on_epoch_end is not None:
            self.on_epoch_end(epoch)

    def close(self) -> None:
        if self._fh is not None:
            self._fh.close()


class TrainingPaused(BaseException):
    """Training stopped at an epoch boundary, after saving its state, because the job's
    walltime is near. A ``BaseException`` so that ``BaseSynthesizer.generate``'s
    ``except Exception`` passes it through instead of reporting a failure."""

    def __init__(self, epoch: int, steps: int, path: str) -> None:
        super().__init__(f"paused at epoch {epoch}/{steps}; state saved to {path}")
        self.epoch, self.steps, self.path = epoch, steps, path


class _Checkpoint:
    """Full training state, so a run longer than one job continues exactly where it stopped.

    TabDiff's own ``ckpt_path`` reloads the weights and the epoch counter only
    (``trainer.py:77-84``): the AdamW moments, the ReduceLROnPlateau state, the EMA copy and the
    random streams would restart, and the resumed run would no longer be the run it continues.
    Everything is saved here at the end of an epoch -- after the optimizer step, the scheduler
    step and the EMA update of that epoch, and before the next epoch draws its shuffle -- so the
    restored state is the one the next epoch would have started from. The run-loop locals
    ``best_loss``, ``best_ema_loss`` and ``patience`` restart; they only drive the best-model
    checkpoints, which ``trainer.py:227/253`` gate on epoch > 4000.

    A checkpoint is written every ``every`` epochs, and also when the next two epochs (at the
    longest epoch seen so far) plus ``MARGIN_S`` would pass ``deadline``; training then stops
    with ``TrainingPaused``. No checkpoint is written at the last epoch.
    """

    MARGIN_S = 900

    def __init__(self, path: str, trainer, epoch_log: "_EpochLog", identity: dict,
                 every: int = 0, deadline: Optional[float] = None) -> None:
        self.path, self.trainer, self.epoch_log = path, trainer, epoch_log
        self.identity, self.every, self.deadline = identity, every, deadline
        self.segment = 1
        self._last = time.time()
        self._longest = 0.0

    def load(self):
        """Restore the saved state into the trainer. Returns (epoch, wall_s)."""
        import torch

        state = torch.load(self.path, map_location="cpu", weights_only=False)
        if state["identity"] != self.identity:
            raise ValueError(f"{self.path} belongs to a different run: {state['identity']} "
                             f"vs {self.identity}")
        t = self.trainer
        t.diffusion.load_state_dict(state["diffusion"])
        t.ema_model.load_state_dict(state["ema_model"])
        t.ema_num_schedule.load_state_dict(state["ema_num_schedule"])
        t.ema_cat_schedule.load_state_dict(state["ema_cat_schedule"])
        t.optimizer.load_state_dict(state["optimizer"])
        t.scheduler.load_state_dict(state["scheduler"])
        t.curr_epoch = state["epoch"]
        self.segment = state["segment"] + 1
        rng = state["rng"]
        random.setstate(rng["python"])
        np.random.set_state(rng["numpy"])
        torch.set_rng_state(rng["torch"])
        if rng["cuda"] and torch.cuda.is_available():
            torch.cuda.set_rng_state_all(rng["cuda"])
        return state["epoch"], state["wall_s"]

    def save(self, epoch: int) -> None:
        import torch

        t = self.trainer
        state = {
            "identity": self.identity, "epoch": epoch, "segment": self.segment,
            "wall_s": time.time() - self.epoch_log.t0,
            "diffusion": t.diffusion.state_dict(),
            "ema_model": t.ema_model.state_dict(),
            "ema_num_schedule": t.ema_num_schedule.state_dict(),
            "ema_cat_schedule": t.ema_cat_schedule.state_dict(),
            "optimizer": t.optimizer.state_dict(),
            "scheduler": t.scheduler.state_dict(),
            "rng": {"python": random.getstate(), "numpy": np.random.get_state(),
                    "torch": torch.get_rng_state(),
                    "cuda": torch.cuda.get_rng_state_all() if torch.cuda.is_available() else []},
        }
        tmp = f"{self.path}.tmp"
        torch.save(state, tmp)
        os.replace(tmp, self.path)

    def start(self) -> None:
        self._last = time.time()

    def __call__(self, epoch: int) -> None:
        now = time.time()
        self._longest = max(self._longest, now - self._last)
        self._last = now
        if epoch >= self.trainer.steps:
            return
        stop = self.deadline is not None and now + 2 * self._longest + self.MARGIN_S > self.deadline
        if stop or (self.every and epoch % self.every == 0):
            self.save(epoch)
        if stop:
            raise TrainingPaused(epoch, self.trainer.steps, self.path)


def _bridge_torch_version(trainer_module) -> List[str]:
    """Make TabDiff (written for torch 2.0.1) run under newer torch releases.

    These are API removals in torch, not hyperparameter changes:

    * ``ReduceLROnPlateau(verbose=...)`` was deprecated in torch 2.2 and removed later.
      ``trainer.py:61`` still passes it. ``verbose`` only controlled a print statement, so
      dropping it changes no numerics.

    Returns the list of bridges applied, so the caller can log them.
    """
    applied = []
    import torch
    from torch.optim.lr_scheduler import ReduceLROnPlateau

    import inspect

    if "verbose" not in inspect.signature(ReduceLROnPlateau.__init__).parameters:
        class _ReduceLROnPlateauCompat(ReduceLROnPlateau):
            def __init__(self, *args, verbose=False, **kwargs):
                super().__init__(*args, **kwargs)

        trainer_module.ReduceLROnPlateau = _ReduceLROnPlateauCompat
        applied.append(f"ReduceLROnPlateau(verbose=) dropped (removed in torch {torch.__version__})")
    return applied


def _config_paths(cfg, prefix=()):
    """Every leaf path in the config, for error messages."""
    for key, value in cfg.items():
        if isinstance(value, dict):
            yield from _config_paths(value, prefix + (key,))
        else:
            yield ".".join(prefix + (key,))


def _apply_overrides(cfg, overrides, applied, prefix=()):
    """Apply a nested override dict, failing loudly on a wrong path.

    The nesting must mirror the TOML, e.g. ``{"train": {"main": {"steps": 100}}}``. Getting a
    level wrong is easy, so a bad path raises with the valid alternatives rather than a bare
    KeyError.
    """
    for key, value in overrides.items():
        path = prefix + (key,)
        dotted = ".".join(path)
        if key not in cfg:
            elsewhere = [p for p in _config_paths(cfg) if p.split(".")[-1] == key]
            hint = f" Did you mean {' or '.join(elsewhere)}?" if elsewhere else ""
            raise KeyError(
                f"config_overrides path {dotted!r} does not exist. "
                f"Keys available at {'.'.join(prefix) or '<root>'}: {sorted(cfg)}.{hint}"
            )
        if isinstance(value, dict):
            if not isinstance(cfg[key], dict):
                raise KeyError(f"config_overrides: {dotted!r} is a value, not a section")
            _apply_overrides(cfg[key], value, applied, path)
        else:
            if isinstance(cfg[key], dict):
                raise KeyError(f"config_overrides: {dotted!r} is a section, not a value; "
                               f"it contains {sorted(cfg[key])}")
            applied[dotted] = (cfg[key], value)
            cfg[key] = value


def _merge_training_shortcuts(config_overrides: Optional[Dict[str, Any]],
                              epochs: Optional[int],
                              batch_size: Optional[int]) -> Dict[str, Any]:
    """Fold ``epochs`` / ``batch_size`` into the override dict as ``train.main.steps`` /
    ``train.main.batch_size``, refusing to set the same value twice."""
    overrides = copy.deepcopy(config_overrides) if config_overrides else {}
    shortcuts = {"steps": ("epochs", epochs), "batch_size": ("batch_size", batch_size)}
    for key, (arg, value) in shortcuts.items():
        if value is None:
            continue
        train = overrides.setdefault("train", {})
        main = train.setdefault("main", {}) if isinstance(train, dict) else None
        if not isinstance(main, dict):
            raise ValueError("config_overrides['train']['main'] must be a dict")
        if key in main:
            raise ValueError(f"{arg} and config_overrides['train']['main'][{key!r}] are both "
                             f"set; pass only one")
        main[key] = int(value)
    return overrides


def _sdpa_attention_forward(self, x_q, x_kv, key_compression=None, value_compression=None):
    """Drop-in for ``MultiheadAttention.forward`` that never materialises the L x L matrix.

    TabDiff's version (``transformer.py:121-123``) builds ``a = q @ k.T`` and then a second
    full-size tensor for the softmax, holding both at once, with one token per column. With tens
    of thousands of gene columns that is several GiB per row per layer.
    ``F.scaled_dot_product_attention`` computes the identical quantity
    ``softmax(QK^T / sqrt(d_head)) V`` but lets PyTorch pick a kernel.

    The EFFICIENT (cutlass) kernel tiles the computation and never materialises the matrix, so
    memory becomes O(L) instead of O(L^2). It accepts fp32 and head dim 4 and is available on
    sm70 (V100) and newer; only FLASH requires sm80+, and FLASH additionally requires
    fp16/bf16, which TabDiff does not use.

    Equivalences preserved:
      * scaling -- SDPA divides by ``sqrt(E)`` with ``E = q.size(-1) = d_head_key``, the same
        ``math.sqrt(d_head_key)`` the original uses;
      * dropout -- applied to the attention weights, and only while training, matching
        ``nn.Dropout``'s behaviour;
      * shapes, head reshaping and the optional ``W_out`` projection are unchanged.

    Not bit-identical: the tiled kernels sum in a different order, so results differ in the
    last few floating-point digits. Against the unmodified module on a V100 in fp32 at
    L = 18,814, the output agrees to a relative 6.2e-06 and the input and weight gradients to
    1.7e-06, i.e. float32 summation epsilon.
    """
    import math

    import torch.nn.functional as F

    q, k, v = self.W_q(x_q), self.W_k(x_kv), self.W_v(x_kv)
    for tensor in [q, k, v]:
        assert tensor.shape[-1] % self.n_heads == 0
    if key_compression is not None:
        assert value_compression is not None
        k = key_compression(k.transpose(1, 2)).transpose(1, 2)
        v = value_compression(v.transpose(1, 2)).transpose(1, 2)
    else:
        assert value_compression is None

    batch_size = len(q)
    d_head_value = v.shape[-1] // self.n_heads
    n_q_tokens = q.shape[1]

    # ``_reshape`` folds the heads into dim 0, giving 3-D ``(batch * n_heads, tokens, d_head)``.
    # Every fused SDPA kernel requires 4-D query, key and value; on 3-D input PyTorch falls back
    # to the MATH kernel, which materialises the full tokens x tokens matrix. ``unsqueeze(1)``
    # restores the head axis the kernels expect; the following ``reshape`` is unchanged because
    # the extra axis has length 1 and so does not move any element.
    q, k, v = (self._reshape(t).unsqueeze(1) for t in (q, k, v))
    dropout_p = self.dropout.p if (self.dropout is not None and self.training) else 0.0
    x = F.scaled_dot_product_attention(q, k, v, dropout_p=dropout_p)

    x = (
        x.reshape(batch_size, self.n_heads, n_q_tokens, d_head_value)
        .transpose(1, 2)
        .reshape(batch_size, n_q_tokens, self.n_heads * d_head_value)
    )
    if self.W_out is not None:
        x = self.W_out(x)
    return x


class TabDiffsynthesizer(BaseSynthesizer):
    """TabDiffsynthesizer for generating synthetic data using TabDiff.

    Args:
        output_path (str): Where logs, checkpoints, TabDiff's working files and synthetic data
            are written.
        metadata (dict, optional): Column-type metadata, as for the other synthesizers.

    Methods:
        fit: Train TabDiff.
        sample: Generate synthetic samples.
        postprocess: Apply postprocessing (anonymize IDs, rounding, scaling).
        generate: Orchestrate data synthesis pipeline.
    """

    _DATASET_NAME = "synomicsbench"

    def __init__(self, output_path: str, metadata: Optional[Dict[str, str]] = None) -> None:
        super().__init__(output_path=output_path, metadata=metadata)
        # TabDiff reads and writes ``data/<name>/`` and ``data/Info/<name>.json`` relative to
        # the working directory. Running inside the output directory keeps those files out of
        # the installed package and separate for every run.
        self.work_dir = os.path.join(os.path.abspath(self.output_path), "tabdiff_work")
        self.model = None
        self.trainer = None
        self.use_sdpa = False

    # ------------------------------------------------------------------ helpers
    def _seed_all(self, seed: Optional[int] = None, use_cuda: bool = False) -> None:
        """Seed Python, NumPy and Torch, matching CTGANsynthesizer._seed_all."""
        if seed is None:
            return
        random.seed(seed)
        np.random.seed(seed)
        try:
            import torch

            torch.manual_seed(seed)
            if use_cuda and torch.cuda.is_available():
                torch.cuda.manual_seed_all(seed)
        except Exception:
            pass

    def _split_columns(self, data: pd.DataFrame, target: Optional[str]):
        """Partition columns into numerical / categorical / target using self.metadata."""
        if self.metadata is None:
            raise ValueError("Metadata dictionary must be set before fitting the model.")
        cols = data.columns.tolist()
        num_cols = [c for c in cols if self.metadata.get(c) == "numerical"]
        cat_cols = [c for c in cols if self.metadata.get(c) in _CATEGORICAL_KINDS]
        unclassified = [c for c in cols if c not in set(num_cols) | set(cat_cols)]
        if unclassified:
            raise ValueError(f"metadata does not classify {len(unclassified)} columns, "
                             f"e.g. {unclassified[:5]}")

        if target is None:
            # TabDiff requires exactly one target column; prefer a binary categorical so
            # task_type can be "binclass". The choice only drives TabDiff's own MLE metric,
            # which is disabled here -- the column is still generated like any other.
            binary = [c for c in cat_cols if data[c].nunique(dropna=False) == 2]
            if not binary:
                raise ValueError("no binary categorical column found to use as TabDiff's "
                                 "target; pass target=... explicitly")
            target = binary[0]
        if target not in cat_cols:
            raise ValueError(f"target {target!r} must be a categorical column")

        cat_cols = [c for c in cat_cols if c != target]
        return num_cols, cat_cols, target

    def _stage(self, data: pd.DataFrame, num_cols, cat_cols, target) -> dict:
        """Write the CSV + Info json layout TabDiff expects, and return the info dict."""
        name = self._DATASET_NAME
        work = self.work_dir
        os.makedirs(f"{work}/data/{name}", exist_ok=True)
        os.makedirs(f"{work}/data/Info", exist_ok=True)

        ordered = list(num_cols) + list(cat_cols) + [target]
        assert sorted(ordered) == sorted(data.columns.tolist())
        self._ordered_columns = ordered
        self._original_columns = data.columns.tolist()
        self._original_dtypes = data.dtypes.to_dict()

        # index=False: process_dataset.train_val_test_split indexes positionally, so the frame
        # it reads back must have a RangeIndex.
        frame = data[ordered].reset_index(drop=True)
        csv_path = f"{work}/data/{name}/{name}.csv"
        frame.to_csv(csv_path, index=False)

        # Supplying a test path makes process_data take its `train_df = data_df` branch, so
        # every row is used for training, as for CTGAN and TVAE. TabDiff's own holdout metrics
        # would therefore be computed on training data; they are disabled.
        test_path = f"{work}/data/{name}/{name}_test.csv"
        frame.to_csv(test_path, index=False)

        n_num, n_cat = len(num_cols), len(cat_cols)
        info = {
            "name": name,
            "task_type": "binclass",
            "header": "infer",
            "column_names": None,
            "num_col_idx": list(range(n_num)),
            "cat_col_idx": list(range(n_num, n_num + n_cat)),
            "target_col_idx": [n_num + n_cat],
            "file_type": "csv",
            "data_path": f"data/{name}/{name}.csv",
            "val_path": None,
            "test_path": f"data/{name}/{name}_test.csv",
        }
        idx = info["num_col_idx"] + info["cat_col_idx"] + info["target_col_idx"]
        assert len(set(idx)) == len(idx), "index lists overlap"
        assert sorted(idx) == list(range(len(ordered))), "index lists do not cover every column"

        with open(f"{work}/data/Info/{name}.json", "w") as handle:
            json.dump(info, handle, indent=4)

        self.logger.info(f"staged {frame.shape} at {csv_path}")
        self.logger.info(f"  {n_num} numerical + {n_cat} categorical + target {target!r}")
        return info

    # ---------------------------------------------------------------------- fit
    def fit(self, data: pd.DataFrame, seed: Optional[int] = None, *,
            epochs: Optional[int] = None, batch_size: Optional[int] = None,
            cuda: bool = True, use_sdpa: bool = True, target: Optional[str] = None,
            n_samples: Optional[int] = None,
            config_overrides: Optional[Dict[str, Dict[str, Any]]] = None,
            ema_loss_every: int = 1, checkpoint_every: int = 0,
            deadline: Optional[float] = None, **kwargs) -> None:
        """Stage the data, then train TabDiff with its default configuration.

        Args:
            data (pd.DataFrame): Preprocessed input frame.
            seed (int, optional): Random seed.
            epochs (int, optional): Training epochs (TabDiff's ``train.main.steps``, which
                ``trainer.py`` loops epochs over). Defaults to TabDiff's 8,000.
            batch_size (int, optional): Training batch (``train.main.batch_size``). Defaults to
                TabDiff's 4,096, which the loader clamps to the number of rows.
            cuda (bool): Use the GPU if available.
            use_sdpa (bool): Replace TabDiff's hand-written attention with
                ``F.scaled_dot_product_attention``, which never materialises the L x L score
                matrix (one token per column). Same maths to float32 summation epsilon, O(L)
                memory instead of O(L^2). This is what makes tens of thousands of gene columns
                trainable. Set False for TabDiff's original attention; it is a deviation from
                the TabDiff code and should be reported as such.
            target (str, optional): Column to declare as TabDiff's target. Auto-picks a binary
                categorical. It only affects TabDiff's disabled MLE metric.
            n_samples (int, optional): Rows to be generated later; sets the sampling chunk size.
                Defaults to the number of training rows.
            config_overrides (dict, optional): Nested dict of deviations from
                ``tabdiff_configs.toml``, e.g. ``{"train": {"main": {"check_val_every": 3001}}}``.
                A wrong path raises with the valid alternatives. Every override applied is
                logged and recorded in ``self.config_overrides_applied``.
            ema_loss_every (int): Evaluate the EMA model's loss every this many epochs (and on
                the last) instead of every epoch. ``Trainer`` spends one extra forward pass over
                the whole cohort per epoch on it and only uses it for the best-EMA checkpoint
                after epoch 4,000. The EMA weights are still updated every epoch. The skipped
                passes also skip their noise draws, so a run with ``ema_loss_every > 1`` follows
                a different random stream than one with 1, not a different algorithm. Per-epoch
                losses, lr and the recorded EMA losses are written to
                ``<output_path>/train_log.csv``.
            checkpoint_every (int): Save the full training state (weights, EMA copy, optimizer,
                LR scheduler, random streams) to ``<output_path>/resume.pt`` every this many
                epochs. 0 disables periodic saves.
            deadline (float, optional): Unix time by which this job must have stopped (its
                walltime). Training saves its state and raises ``TrainingPaused`` at the last
                epoch boundary that leaves a safe margin. With either option set, an existing
                ``resume.pt`` is loaded and training continues from it. The file is left in
                place; the caller removes it once the synthetic data are written.
            **kwargs: Accepted for interface compatibility and ignored.

        Raises:
            ValueError: If metadata is not set, the data are empty, or ``epochs`` /
                ``batch_size`` duplicate a value in ``config_overrides``.
            TrainingPaused: If ``deadline`` stopped training before the last epoch.
        """
        if not isinstance(data, pd.DataFrame) or data.empty:
            raise ValueError("Input 'data' must be a non-empty pandas DataFrame.")
        if int(ema_loss_every) < 1:
            raise ValueError("ema_loss_every must be a positive integer.")
        ema_loss_every = int(ema_loss_every)
        config_overrides = _merge_training_shortcuts(config_overrides, epochs, batch_size)
        _prepare_tabdiff_imports()
        import torch

        self._seed_all(seed, use_cuda=cuda)
        device = "cuda" if (cuda and torch.cuda.is_available()) else "cpu"
        n_samples = int(n_samples or len(data))

        num_cols, cat_cols, target = self._split_columns(data, target)
        info = self._stage(data, num_cols, cat_cols, target)

        started = time.time()
        with _pushd(self.work_dir):
            # --- TabDiff's preprocessing, unmodified ---
            with _clean_argv():
                process_dataset = importlib.import_module("process_dataset")
                process_dataset.process_data(self._DATASET_NAME)
            with open(f"data/{self._DATASET_NAME}/info.json") as handle:
                info = json.load(handle)
            self.logger.info(f"process_data: train_num={info.get('train_num')} "
                             f"test_num={info.get('test_num')}")

            import src
            from torch.utils.data import DataLoader

            from tabdiff.models.unified_ctime_diffusion import UnifiedCtimeDiffusion
            from tabdiff.modules.main_modules import Model, UniModMLP
            from tabdiff.modules.transformer import MultiheadAttention
            import tabdiff.trainer as tabdiff_trainer
            from tabdiff.trainer import Trainer
            from utils_train import TabDiffDataset

            bridges = _bridge_torch_version(tabdiff_trainer)
            for msg in bridges:
                self.logger.info(f"torch-version bridge: {msg}")

            # The attention is chosen per fit, so one process can train both variants.
            if not hasattr(MultiheadAttention, "_original_forward"):
                MultiheadAttention._original_forward = MultiheadAttention.forward
            self.use_sdpa = bool(use_sdpa)
            if self.use_sdpa:
                MultiheadAttention.forward = _sdpa_attention_forward
                self.logger.info(
                    "attention replaced with scaled_dot_product_attention (same maths to "
                    "float32 epsilon, O(L) memory instead of O(L^2)); this is a deviation "
                    "from the TabDiff code"
                )
            else:
                MultiheadAttention.forward = MultiheadAttention._original_forward

            # --- config: every value as shipped, file untouched ---
            cfg = src.load_config(os.path.join(TABDIFF_DIR, "tabdiff", "configs",
                                               "tabdiff_configs.toml"))
            self.config_overrides_applied = {}
            _apply_overrides(cfg, config_overrides, self.config_overrides_applied)
            if self.config_overrides_applied:
                self.logger.info(
                    "not using TabDiff defaults for: "
                    + ", ".join(f"{k} {a}->{b}" for k, (a, b) in
                                self.config_overrides_applied.items())
                )
            else:
                self.logger.info("using TabDiff's default configuration verbatim")
            self.config = cfg

            data_dir = f"data/{self._DATASET_NAME}"
            train_data = TabDiffDataset(
                self._DATASET_NAME, data_dir, info, y_only=False, isTrain=True,
                dequant_dist=cfg["data"]["dequant_dist"],
                int_dequant_factor=cfg["data"]["int_dequant_factor"],
            )
            val_data = TabDiffDataset(
                self._DATASET_NAME, data_dir, info, y_only=False, isTrain=False,
                dequant_dist=cfg["data"]["dequant_dist"],
                int_dequant_factor=cfg["data"]["int_dequant_factor"],
            )
            train_loader = DataLoader(train_data, batch_size=cfg["train"]["main"]["batch_size"],
                                      shuffle=True, num_workers=4)
            d_numerical, categories = train_data.d_numerical, train_data.categories

            # mirrors main.py:157-158 -- +1 for the mask category
            cfg["unimodmlp_params"]["d_numerical"] = d_numerical
            cfg["unimodmlp_params"]["categories"] = (categories + 1).tolist()
            backbone = UniModMLP(**cfg["unimodmlp_params"])
            model = Model(backbone, **cfg["diffusion_params"]["edm_params"]).to(device)

            # main.py:212-214 applies these on a default run (no --non_learnable_schedule)
            cfg["diffusion_params"]["scheduler"] = "power_mean_per_column"
            cfg["diffusion_params"]["cat_scheduler"] = "log_linear_per_column"
            diffusion = UnifiedCtimeDiffusion(
                num_classes=categories, num_numerical_features=d_numerical,
                denoise_fn=model, y_only_model=None,
                **cfg["diffusion_params"], device=device,
            ).to(device)
            self.n_parameters = sum(p.numel() for p in diffusion.parameters())
            self.logger.info(f"TabDiff on {device} | {self.n_parameters:,} parameters | "
                             f"{d_numerical} numerical + {len(categories)} categorical tokens")

            epoch_log = _EpochLog(os.path.join(self.output_path, "train_log.csv"))
            trainer = Trainer(
                diffusion, train_loader, train_data, val_data,
                _NullMetrics(info, len(train_data)), epoch_log,
                **cfg["train"]["main"],
                sample_batch_size=n_samples,
                num_samples_to_generate=n_samples,
                model_save_path=os.path.join(self.output_path, "ckpt"),
                result_save_path=os.path.join(self.output_path, "result"),
                device=device, ckpt_path=None, y_only=False,
            )
            os.makedirs(trainer.model_save_path, exist_ok=True)
            os.makedirs(trainer.result_save_path, exist_ok=True)

            # Attention memory: with TabDiff's own attention every layer holds a
            # batch x tokens x tokens score matrix, which is what runs out of GPU memory at
            # wide gene counts, so warn before training rather than after the setup. With
            # ``use_sdpa`` that matrix is never built and the peak is model + Adam + EMA plus
            # activations linear in ``batch * tokens``.
            eff_batch = min(cfg["train"]["main"]["batch_size"], len(train_data))
            tokens = d_numerical + len(categories)
            attn_gib = eff_batch * tokens * tokens * 4 / 2**30
            self.attention_gib = 0.0 if self.use_sdpa else attn_gib
            self._n_tokens = tokens
            if device == "cuda":
                total_gib = torch.cuda.get_device_properties(0).total_memory / 2**30
                if self.use_sdpa:
                    # About 3.26 GiB per million cell-tokens (rows in the batch x columns),
                    # measured on a V100 with 18,814 and 21,997 columns.
                    est = 3.26 * eff_batch * tokens / 1e6
                    self.logger.info(f"attention: {tokens} tokens x batch {eff_batch}, sdpa on "
                                     f"-> O(L) attention; estimated peak ~{est:.1f} GiB "
                                     f"(GPU has {total_gib:.1f} GiB)")
                else:
                    self.logger.info(f"attention: {tokens} tokens x batch {eff_batch} "
                                     f"-> {attn_gib:.2f} GiB per layer (GPU has {total_gib:.1f} GiB)")
                if not self.use_sdpa and attn_gib * 3 > total_gib * 0.9:
                    self.logger.warning(
                        f"likely CUDA OOM: ~{attn_gib * 3:.1f} GiB needed for 2 layers "
                        f"forward+backward, GPU has {total_gib:.1f} GiB. Use use_sdpa=True or a "
                        f"smaller batch, e.g. batch_size="
                        f"{max(8, int(eff_batch * total_gib * 0.25 / max(attn_gib, 1e-9)))}"
                    )

            self.logger.info(
                f"training: steps={cfg['train']['main']['steps']} "
                f"batch_size={cfg['train']['main']['batch_size']} "
                f"(effective {min(cfg['train']['main']['batch_size'], len(train_data))}, "
                f"{len(train_loader)} batch/epoch) "
                f"num_timesteps={cfg['diffusion_params']['num_timesteps']}"
            )
            # Training is timed separately from ``started``: staging, process_data and model
            # construction are a fixed cost that grows with the column count, and folding it
            # into the training time would make s/epoch unusable for planning a walltime.
            if ema_loss_every > 1:
                self.logger.info(f"EMA-model loss evaluated every {ema_loss_every} epochs and "
                                 f"on the last one (EMA weights still updated every epoch)")
            epoch_log.watch_ema_loss(trainer, ema_loss_every)
            resume_epoch, wall_s = 0, 0.0
            checkpoint = None
            if checkpoint_every or deadline is not None:
                identity = {"steps": cfg["train"]["main"]["steps"],
                            "batch_size": cfg["train"]["main"]["batch_size"],
                            "seed": seed, "ema_loss_every": ema_loss_every,
                            "shape": list(data.shape), "n_parameters": self.n_parameters}
                checkpoint = _Checkpoint(os.path.join(self.output_path, "resume.pt"), trainer,
                                         epoch_log, identity, checkpoint_every, deadline)
                if os.path.exists(checkpoint.path):
                    # Last before run_loop: restoring the random streams must come after
                    # everything above that draws from them (model init, loaders).
                    resume_epoch, wall_s = checkpoint.load()
                    self.logger.info(f"resuming from {checkpoint.path} at epoch {resume_epoch} "
                                     f"(job {checkpoint.segment} of this run)")
                epoch_log.on_epoch_end = checkpoint
            self.resumed_from_epoch = resume_epoch
            epoch_log.open(resume_epoch, wall_s)
            train_t0 = time.time()
            if checkpoint is not None:
                checkpoint.start()
            try:
                trainer.run_loop()      # main.py:283 -- TabDiff's training entry point
            finally:
                epoch_log.close()
            self.train_seconds_job = time.time() - train_t0
            self.train_seconds = time.time() - epoch_log.t0
            self.segments = checkpoint.segment if checkpoint is not None else 1

        self.model = diffusion
        self.trainer = trainer
        self.fit_seconds = time.time() - started
        n_epochs = cfg["train"]["main"]["steps"]
        self.logger.info(
            f"TabDiff training completed in {self.train_seconds:.1f}s "
            f"({self.train_seconds / max(n_epochs, 1):.2f} s/epoch over {n_epochs} epochs"
            f"{f', {self.segments} jobs' if self.segments > 1 else ''}); "
            f"this job: fit total {self.fit_seconds:.1f}s including "
            f"{self.fit_seconds - self.train_seconds_job:.1f}s of staging and setup"
        )

    # ------------------------------------------------------------------- sample
    def sample(self, n_samples: int = 10, seed: Optional[int] = None, **kwargs) -> pd.DataFrame:
        """Generate synthetic rows and restore the original column layout.

        Args:
            n_samples (int): Number of samples to generate.
            seed (int, optional): Random seed used for sampling.
            **kwargs: ``sample_batch_size`` sets the first sampling chunk explicitly.

        Returns:
            pd.DataFrame: Synthetic samples with the training columns, order and dtypes.

        Raises:
            ValueError: If the model is not fitted.
        """
        if getattr(self, "trainer", None) is None:
            self.logger.error("Model is not fitted. Call fit() first.")
            raise ValueError("Model is not fitted. Call fit() first.")
        import torch

        self._seed_all(seed, use_cuda=torch.cuda.is_available())

        # Choosing the sampling chunk. ``sample_all`` loops over chunks, so a smaller chunk only
        # costs more passes, never a different result. With TabDiff's own attention the decoder
        # and encoder each run two attention layers whose softmax needs an input and an output
        # buffer, so the first chunk is sized from the free GPU memory. With ``use_sdpa`` there
        # is no L x L matrix to budget for and the chunk starts at the full request. Either way
        # the chunk is halved on an out-of-memory error until it fits.
        tokens = getattr(self, "_n_tokens", None)
        requested = int(n_samples)
        chunk = kwargs.get("sample_batch_size")
        if chunk is None:
            chunk = requested
            if torch.cuda.is_available() and tokens and not self.use_sdpa:
                torch.cuda.empty_cache()
                free_b, _ = torch.cuda.mem_get_info()
                # 8 concurrent attention buffers: 4 layers x (softmax in + out)
                per_row = tokens * tokens * 4 * 8
                fits = max(1, int(free_b * 0.6 // per_row))
                if fits < chunk:
                    self.logger.info(
                        f"first attempt with chunk {fits}: {free_b / 2**30:.2f} GiB free, "
                        f"~{per_row / 2**30:.3f} GiB of attention per row"
                    )
                chunk = min(chunk, fits)
        chunk = int(chunk)

        self.trainer.num_samples_to_generate = requested
        syn, attempts = None, []
        while True:
            self.trainer.sample_batch_size = chunk
            self.logger.info(f"sampling {requested} rows, chunk {chunk} "
                             f"({int(np.ceil(requested / chunk))} pass(es))")
            try:
                with _pushd(self.work_dir):
                    syn = self.trainer.sample_synthetic(requested)
                break
            except torch.OutOfMemoryError as exc:
                attempts.append(chunk)
                if chunk <= 1:
                    raise RuntimeError(
                        f"sampling OOMs even at chunk 1 ({tokens} tokens). Tried {attempts}. "
                        f"This width does not fit this GPU for sampling."
                    ) from exc
                chunk = max(1, chunk // 2)
                self.logger.warning(f"CUDA OOM at chunk {attempts[-1]}, retrying with {chunk}")
                del exc
                import gc

                gc.collect()
                torch.cuda.empty_cache()
        if attempts:
            self.logger.info(f"sampling succeeded at chunk {chunk} after backing off from "
                             f"{attempts}")
        self.sample_chunk_used = chunk

        syn = pd.DataFrame(np.asarray(syn) if not isinstance(syn, pd.DataFrame) else syn.values)
        if syn.shape[1] != len(self._ordered_columns):
            raise ValueError(f"TabDiff returned {syn.shape[1]} columns, "
                             f"expected {len(self._ordered_columns)}")
        syn.columns = self._ordered_columns
        syn = syn[self._original_columns]

        for col, dtype in self._original_dtypes.items():
            if syn[col].dtype == dtype:
                continue
            values = syn[col]
            try:
                if pd.api.types.is_numeric_dtype(dtype):
                    values = pd.to_numeric(values)
                syn[col] = values.astype(dtype)
            except (ValueError, TypeError):
                self.logger.warning(f"could not restore dtype {dtype} for column {col!r}")

        self.logger.info(f"sampled {syn.shape} rows")
        return syn
