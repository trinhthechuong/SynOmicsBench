"""
Synthetic data generation module.

This module provides implementations of various synthetic data generation methods:
- Gaussian Copula
- CTGAN
- TVAE
- Synthpop
- Avatars

All synthesizers follow a unified interface through BaseSynthesizer.
"""

from SynOmics.synthesizer.BaseSynthesizer import BaseSynthesizer
from SynOmics.synthesizer.GaussianCopulasynthesizer import GaussianCopulasynthesizer
from SynOmics.synthesizer.CTGANsynthesizer import CTGANSynthesizer
from SynOmics.synthesizer.TVAEsynthesizer import TVAEsynthesizer
from SynOmics.synthesizer.Synthpopsynthesizer import SynthpopSynthesizer
