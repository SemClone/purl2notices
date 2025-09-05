"""Ruby Gem package detector."""

from pathlib import Path
from typing import List
from .base import BaseDetector, DetectorResult


class GemDetector(BaseDetector):
    """Detector for Ruby Gem packages."""
    
    PACKAGE_TYPE = "gem"
    FILE_PATTERNS = ["Gemfile", "Gemfile.lock", "*.gemspec"]
    ARCHIVE_EXTENSIONS = [".gem"]
    
    def detect_from_file(self, file_path: Path) -> DetectorResult:
        """Detect Gem package from file."""
        # Stub implementation
        return DetectorResult(detected=False)
    
    def detect_from_directory(self, directory: Path) -> List[DetectorResult]:
        """Detect Gem packages in directory."""
        # Stub implementation
        return []