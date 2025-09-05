"""Go package detector."""

from pathlib import Path
from typing import List
from .base import BaseDetector, DetectorResult


class GoDetector(BaseDetector):
    """Detector for Go packages."""
    
    PACKAGE_TYPE = "golang"
    FILE_PATTERNS = ["go.mod", "go.sum"]
    ARCHIVE_EXTENSIONS = []
    
    def detect_from_file(self, file_path: Path) -> DetectorResult:
        """Detect Go package from file."""
        if not self.can_handle_file(file_path):
            return DetectorResult(detected=False)
        
        if file_path.name == "go.mod":
            return self._detect_from_go_mod(file_path)
        
        return DetectorResult(detected=False)
    
    def detect_from_directory(self, directory: Path) -> List[DetectorResult]:
        """Detect Go packages in directory."""
        results = []
        go_mod = directory / "go.mod"
        if go_mod.exists():
            result = self._detect_from_go_mod(go_mod)
            if result.detected:
                results.append(result)
        return results
    
    def _detect_from_go_mod(self, file_path: Path) -> DetectorResult:
        """Extract package info from go.mod."""
        try:
            content = file_path.read_text(encoding='utf-8')
            lines = content.splitlines()
            
            module_name = None
            go_version = None
            
            for line in lines:
                line = line.strip()
                if line.startswith('module '):
                    module_name = line[7:].strip()
                elif line.startswith('go '):
                    go_version = line[3:].strip()
            
            if module_name:
                # Extract namespace and name from module path
                parts = module_name.split('/')
                if len(parts) >= 2:
                    namespace = '/'.join(parts[:-1])
                    name = parts[-1]
                else:
                    namespace = None
                    name = module_name
                
                return DetectorResult(
                    detected=True,
                    package_type=self.PACKAGE_TYPE,
                    name=name,
                    version='',  # go.mod doesn't have package version
                    namespace=namespace,
                    purl=self._build_purl(name, None, namespace),
                    metadata={
                        'module': module_name,
                        'go_version': go_version,
                        'source_file': str(file_path)
                    },
                    confidence=1.0
                )
        except Exception:
            pass
        
        return DetectorResult(detected=False)