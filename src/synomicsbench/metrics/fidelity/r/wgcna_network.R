# WGCNA routines behind synomicsbench.metrics.fidelity.NetworkPreservation.
#
# Every network is built with the same parameters: signed hybrid network, biweight
# midcorrelation, one block holding all genes (maxBlockSize above the gene count).
# Sourced through rpy2; each function takes a samples x genes numeric matrix whose
# column names are the gene names.

suppressPackageStartupMessages(library(WGCNA))
options(stringsAsFactors = FALSE)

SB_WGCNA <- list(
  networkType       = "signed hybrid",
  TOMType           = "signed",
  corType           = "bicor",
  maxPOutliers      = 0.05,
  minModuleSize     = 30,
  deepSplit         = 2,
  mergeCutHeight    = 0.25,
  pamRespectsDendro = FALSE,
  RsquaredCut       = 0.85,
  MeanKFloor        = 10,
  FAQ_BETA          = 12,
  POWERS            = c(1:10, seq(12, 20, 2))
)

# Soft-thresholding power. Among the powers that keep the network connected
# (mean connectivity >= MeanKFloor), take the one with the best scale-free fit; the
# plain "lowest power with R^2 >= cut" can land on an almost edgeless network. When no
# power keeps the network connected, fall back to the WGCNA FAQ default for signed
# hybrid networks.
sb_pick_beta <- function(expr) {
  sft <- pickSoftThreshold(expr, powerVector = SB_WGCNA$POWERS,
                           networkType = SB_WGCNA$networkType,
                           corFnc = bicor,
                           corOptions = list(use = "p", maxPOutliers = SB_WGCNA$maxPOutliers),
                           RsquaredCut = SB_WGCNA$RsquaredCut, verbose = 0)
  fi <- sft$fitIndices
  connected <- fi[fi[["mean.k."]] >= SB_WGCNA$MeanKFloor, , drop = FALSE]
  if (nrow(connected) > 0) {
    beta <- as.integer(connected[which.max(connected[["SFT.R.sq"]]), ][["Power"]])
    rule <- if (!is.na(sft$powerEstimate) && beta == sft$powerEstimate)
              "R2cut+meanK" else "maxR2 given meanK floor"
  } else {
    beta <- SB_WGCNA$FAQ_BETA
    rule <- "FAQ fallback (no power keeps mean.k above floor)"
  }
  row <- fi[fi[["Power"]] == beta, ]
  list(beta = beta, rule = rule,
       rsq = as.numeric(row[["SFT.R.sq"]]), mean_k = as.numeric(row[["mean.k."]]))
}

# Module colours of one network ("grey" = unassigned genes).
sb_modules <- function(expr, beta, seed) {
  net <- blockwiseModules(
    expr, power = beta,
    networkType = SB_WGCNA$networkType, TOMType = SB_WGCNA$TOMType,
    corType = SB_WGCNA$corType, maxPOutliers = SB_WGCNA$maxPOutliers,
    minModuleSize = SB_WGCNA$minModuleSize, deepSplit = SB_WGCNA$deepSplit,
    mergeCutHeight = SB_WGCNA$mergeCutHeight,
    pamRespectsDendro = SB_WGCNA$pamRespectsDendro,
    maxBlockSize = max(12000, ncol(expr) + 1), numericLabels = TRUE,
    saveTOMs = FALSE, randomSeed = seed, verbose = 0
  )
  if (!is.null(net$goodGenes) && !all(net$goodGenes)) {
    stop(sprintf("blockwiseModules dropped %d genes as 'not good'.", sum(!net$goodGenes)))
  }
  labels2colors(net$colors)
}

# Positions (in the upper triangle, column-major) of the `frac` gene pairs with the
# highest topological overlap. Ties at the threshold are cut to keep exactly K pairs.
sb_top_edges <- function(expr, beta, frac) {
  adj <- adjacency(expr, power = beta, type = SB_WGCNA$networkType,
                   corFnc = "bicor",
                   corOptions = list(use = "p", maxPOutliers = SB_WGCNA$maxPOutliers))
  TOM <- TOMsimilarity(adj, TOMType = SB_WGCNA$TOMType, verbose = 0)
  rm(adj); invisible(gc())
  tomVec <- TOM[upper.tri(TOM)]
  rm(TOM); invisible(gc())
  n <- length(tomVec)
  K <- round(frac * n)
  thr <- sort(tomVec, partial = n - K + 1)[n - K + 1]
  idx <- which(tomVec >= thr)
  if (length(idx) > K) {
    idx <- idx[order(tomVec[idx], decreasing = TRUE)[seq_len(K)]]
  }
  idx
}

# Preservation of the reference modules in the test data (WGCNA::modulePreservation).
sb_module_preservation <- function(ref, test, colors, nperm, seed, max_module_size) {
  stopifnot(identical(colnames(ref), colnames(test)))
  multiExpr  <- list(ref = list(data = as.data.frame(ref)),
                     test = list(data = as.data.frame(test)))
  multiColor <- list(ref = colors)
  mp <- modulePreservation(
    multiExpr, multiColor,
    referenceNetworks = 1,
    nPermutations = nperm,
    networkType = SB_WGCNA$networkType,
    corFnc = "bicor",
    corOptions = sprintf("use = 'p', maxPOutliers = %g", SB_WGCNA$maxPOutliers),
    maxModuleSize = max_module_size,
    randomSeed = seed,
    parallelCalculation = TRUE,
    savePermutedStatistics = FALSE,
    verbose = 0
  )
  zs  <- mp$preservation$Z$ref.ref$inColumnsAlsoPresentIn.test
  obs <- mp$preservation$observed$ref.ref$inColumnsAlsoPresentIn.test
  for (nm in c("Zsummary.pres", "Zdensity.pres", "Zconnectivity.pres")) {
    if (is.null(zs[[nm]])) stop(sprintf("modulePreservation: column '%s' missing", nm))
  }
  data.frame(module        = rownames(zs),
             moduleSize    = obs[["moduleSize"]],
             Zsummary      = zs[["Zsummary.pres"]],
             Zdensity      = zs[["Zdensity.pres"]],
             Zconnectivity = zs[["Zconnectivity.pres"]],
             stringsAsFactors = FALSE)
}
