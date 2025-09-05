"""Extractors for license and copyright information."""

from .base import BaseExtractor, ExtractionResult
from .purl2src_extractor import Purl2SrcExtractor
from .upmex_extractor import UpmexExtractor
from .oslili_extractor import OsliliExtractor
from .combined_extractor import CombinedExtractor

__all__ = [
    "BaseExtractor",
    "ExtractionResult",
    "Purl2SrcExtractor",
    "UpmexExtractor",
    "OsliliExtractor",
    "CombinedExtractor",
]