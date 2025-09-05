"""Package detectors for identifying different package types."""

from .base import BaseDetector, DetectorResult
from .npm import NpmDetector
from .pypi import PyPiDetector
from .maven import MavenDetector
from .cargo import CargoDetector
from .go import GoDetector
from .gem import GemDetector
from .composer import ComposerDetector
from .nuget import NuGetDetector
from .registry import DetectorRegistry

__all__ = [
    "BaseDetector",
    "DetectorResult",
    "NpmDetector",
    "PyPiDetector", 
    "MavenDetector",
    "CargoDetector",
    "GoDetector",
    "GemDetector",
    "ComposerDetector",
    "NuGetDetector",
    "DetectorRegistry",
]