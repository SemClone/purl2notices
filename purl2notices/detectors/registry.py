"""Registry for package detectors."""

from pathlib import Path
from typing import List, Dict, Type, Optional
import logging

from .base import BaseDetector, DetectorResult
from .npm import NpmDetector
from .pypi import PyPiDetector
from .maven import MavenDetector
from .cargo import CargoDetector
from .go import GoDetector
from .gem import GemDetector
from .composer import ComposerDetector
from .nuget import NuGetDetector


logger = logging.getLogger(__name__)


class DetectorRegistry:
    """Registry for managing package detectors."""
    
    # Default detector classes
    DEFAULT_DETECTORS = [
        NpmDetector,
        PyPiDetector,
        MavenDetector,
        CargoDetector,
        GoDetector,
        GemDetector,
        ComposerDetector,
        NuGetDetector,
    ]
    
    def __init__(self):
        """Initialize registry."""
        self.detectors: Dict[str, BaseDetector] = {}
        self._register_default_detectors()
    
    def _register_default_detectors(self) -> None:
        """Register default detectors."""
        for detector_class in self.DEFAULT_DETECTORS:
            try:
                detector = detector_class()
                self.register(detector)
            except Exception as e:
                logger.error(f"Failed to register {detector_class.__name__}: {e}")
    
    def register(self, detector: BaseDetector) -> None:
        """Register a detector."""
        if not isinstance(detector, BaseDetector):
            raise ValueError("Detector must be an instance of BaseDetector")
        
        package_type = detector.PACKAGE_TYPE
        if package_type in self.detectors:
            logger.warning(f"Overwriting existing detector for {package_type}")
        
        self.detectors[package_type] = detector
        logger.debug(f"Registered detector for {package_type}")
    
    def unregister(self, package_type: str) -> None:
        """Unregister a detector."""
        if package_type in self.detectors:
            del self.detectors[package_type]
            logger.debug(f"Unregistered detector for {package_type}")
    
    def get_detector(self, package_type: str) -> Optional[BaseDetector]:
        """Get detector for specific package type."""
        return self.detectors.get(package_type)
    
    def detect_from_file(self, file_path: Path) -> List[DetectorResult]:
        """
        Detect package from file using all applicable detectors.
        
        Returns list of results from all detectors that can handle the file.
        """
        results = []
        
        for detector in self.detectors.values():
            try:
                if detector.can_handle_file(file_path):
                    result = detector.detect_from_file(file_path)
                    if result.detected:
                        results.append(result)
                        logger.debug(f"{detector.PACKAGE_TYPE} detected package in {file_path}")
            except Exception as e:
                logger.error(f"Error in {detector.PACKAGE_TYPE} detector for {file_path}: {e}")
        
        return results
    
    def detect_from_directory(self, directory: Path) -> List[DetectorResult]:
        """
        Detect packages in directory using all detectors.
        
        Returns combined list of results from all detectors.
        """
        all_results = []
        
        for detector in self.detectors.values():
            try:
                results = detector.detect_from_directory(directory)
                if results:
                    all_results.extend(results)
                    logger.debug(f"{detector.PACKAGE_TYPE} found {len(results)} packages in {directory}")
            except Exception as e:
                logger.error(f"Error in {detector.PACKAGE_TYPE} detector for {directory}: {e}")
        
        return all_results
    
    def detect_from_purl(self, purl: str) -> Optional[DetectorResult]:
        """
        Create DetectorResult from PURL string.
        
        This doesn't actually detect anything, but creates a result
        from a known PURL.
        """
        try:
            from packageurl import PackageURL
            
            parsed = PackageURL.from_string(purl)
            
            # Find appropriate detector
            detector = self.get_detector(parsed.type)
            if not detector:
                # Create generic result
                return DetectorResult(
                    detected=True,
                    package_type=parsed.type,
                    name=parsed.name,
                    version=parsed.version,
                    namespace=parsed.namespace,
                    purl=purl,
                    confidence=1.0
                )
            
            # Use detector to create proper result
            return DetectorResult(
                detected=True,
                package_type=parsed.type,
                name=parsed.name,
                version=parsed.version,
                namespace=parsed.namespace,
                purl=purl,
                confidence=1.0
            )
        except Exception as e:
            logger.error(f"Failed to parse PURL {purl}: {e}")
            return None
    
    def get_supported_types(self) -> List[str]:
        """Get list of supported package types."""
        return list(self.detectors.keys())
    
    def get_file_patterns(self) -> Dict[str, List[str]]:
        """Get all file patterns from all detectors."""
        patterns = {}
        for package_type, detector in self.detectors.items():
            patterns[package_type] = detector.FILE_PATTERNS
        return patterns
    
    def get_archive_extensions(self) -> Dict[str, List[str]]:
        """Get all archive extensions from all detectors."""
        extensions = {}
        for package_type, detector in self.detectors.items():
            extensions[package_type] = detector.ARCHIVE_EXTENSIONS
        return extensions