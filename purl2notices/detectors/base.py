"""Base detector interface."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List, Dict, Any


@dataclass
class DetectorResult:
    """Result from package detection."""
    
    detected: bool
    package_type: Optional[str] = None
    name: Optional[str] = None
    version: Optional[str] = None
    namespace: Optional[str] = None
    purl: Optional[str] = None
    metadata: Dict[str, Any] = None
    confidence: float = 0.0  # 0.0 to 1.0
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class BaseDetector(ABC):
    """Base class for package detectors."""
    
    # Package type this detector handles
    PACKAGE_TYPE: str = ""
    
    # File patterns this detector looks for
    FILE_PATTERNS: List[str] = []
    
    # Archive extensions this detector handles
    ARCHIVE_EXTENSIONS: List[str] = []
    
    def __init__(self):
        """Initialize detector."""
        if not self.PACKAGE_TYPE:
            raise ValueError(f"{self.__class__.__name__} must define PACKAGE_TYPE")
    
    @abstractmethod
    def detect_from_file(self, file_path: Path) -> DetectorResult:
        """
        Detect package from a file.
        
        Args:
            file_path: Path to file (metadata or archive)
            
        Returns:
            DetectorResult with detection information
        """
        pass
    
    @abstractmethod
    def detect_from_directory(self, directory: Path) -> List[DetectorResult]:
        """
        Detect packages in a directory.
        
        Args:
            directory: Path to directory
            
        Returns:
            List of DetectorResults
        """
        pass
    
    def can_handle_file(self, file_path: Path) -> bool:
        """Check if this detector can handle the file."""
        file_name = file_path.name
        
        # Check file patterns
        for pattern in self.FILE_PATTERNS:
            if self._match_pattern(file_name, pattern):
                return True
        
        # Check archive extensions
        for ext in self.ARCHIVE_EXTENSIONS:
            if file_name.endswith(ext):
                return True
        
        return False
    
    def _match_pattern(self, filename: str, pattern: str) -> bool:
        """Match filename against pattern (supports wildcards)."""
        import fnmatch
        return fnmatch.fnmatch(filename, pattern)
    
    def _extract_from_archive(self, archive_path: Path) -> Optional[Dict[str, Any]]:
        """Extract metadata from archive."""
        import zipfile
        import tarfile
        import json
        
        try:
            # Handle different archive types
            if archive_path.suffix in ['.whl', '.jar', '.zip']:
                with zipfile.ZipFile(archive_path, 'r') as archive:
                    return self._extract_from_zip(archive)
            elif archive_path.name.endswith(('.tar.gz', '.tgz', '.tar.bz2')):
                with tarfile.open(archive_path, 'r:*') as archive:
                    return self._extract_from_tar(archive)
        except Exception:
            return None
        
        return None
    
    def _extract_from_zip(self, archive: Any) -> Optional[Dict[str, Any]]:
        """Extract metadata from zip archive."""
        return None
    
    def _extract_from_tar(self, archive: Any) -> Optional[Dict[str, Any]]:
        """Extract metadata from tar archive."""
        return None
    
    def _build_purl(
        self,
        name: str,
        version: Optional[str] = None,
        namespace: Optional[str] = None,
        qualifiers: Optional[Dict[str, str]] = None,
        subpath: Optional[str] = None
    ) -> str:
        """Build Package URL."""
        from packageurl import PackageURL
        
        return PackageURL(
            type=self.PACKAGE_TYPE,
            namespace=namespace,
            name=name,
            version=version,
            qualifiers=qualifiers,
            subpath=subpath
        ).to_string()