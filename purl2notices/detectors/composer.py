"""Composer/PHP package detector."""

from pathlib import Path
from typing import List
from .base import BaseDetector, DetectorResult


class ComposerDetector(BaseDetector):
    """Detector for Composer/PHP packages."""
    
    PACKAGE_TYPE = "composer"
    FILE_PATTERNS = ["composer.json", "composer.lock"]
    ARCHIVE_EXTENSIONS = []
    
    def detect_from_file(self, file_path: Path) -> DetectorResult:
        """Detect Composer package from file."""
        # Stub implementation
        return DetectorResult(detected=False)
    
    def detect_from_directory(self, directory: Path) -> List[DetectorResult]:
        """Detect Composer packages in directory."""
        # Stub implementation
        return []