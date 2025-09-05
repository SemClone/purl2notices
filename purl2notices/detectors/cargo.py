"""Cargo/Rust package detector."""

from pathlib import Path
from typing import List
from .base import BaseDetector, DetectorResult


class CargoDetector(BaseDetector):
    """Detector for Cargo/Rust packages."""
    
    PACKAGE_TYPE = "cargo"
    FILE_PATTERNS = ["Cargo.toml", "Cargo.lock"]
    ARCHIVE_EXTENSIONS = [".crate"]
    
    def detect_from_file(self, file_path: Path) -> DetectorResult:
        """Detect Cargo package from file."""
        if not self.can_handle_file(file_path):
            return DetectorResult(detected=False)
        
        if file_path.name == "Cargo.toml":
            return self._detect_from_cargo_toml(file_path)
        
        return DetectorResult(detected=False)
    
    def detect_from_directory(self, directory: Path) -> List[DetectorResult]:
        """Detect Cargo packages in directory."""
        results = []
        cargo_toml = directory / "Cargo.toml"
        if cargo_toml.exists():
            result = self._detect_from_cargo_toml(cargo_toml)
            if result.detected:
                results.append(result)
        return results
    
    def _detect_from_cargo_toml(self, file_path: Path) -> DetectorResult:
        """Extract package info from Cargo.toml."""
        try:
            try:
                import tomllib
            except ImportError:
                import tomli as tomllib
            
            with open(file_path, 'rb') as f:
                data = tomllib.load(f)
            
            package = data.get('package', {})
            name = package.get('name', '')
            version = package.get('version', '')
            
            if name:
                return DetectorResult(
                    detected=True,
                    package_type=self.PACKAGE_TYPE,
                    name=name,
                    version=version,
                    purl=self._build_purl(name, version),
                    metadata={
                        'license': package.get('license', ''),
                        'description': package.get('description', ''),
                        'source_file': str(file_path)
                    },
                    confidence=1.0
                )
        except Exception:
            pass
        
        return DetectorResult(detected=False)