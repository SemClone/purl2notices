"""NPM package detector."""

import json
import tarfile
from pathlib import Path
from typing import List, Dict, Any, Optional

from .base import BaseDetector, DetectorResult


class NpmDetector(BaseDetector):
    """Detector for NPM packages."""
    
    PACKAGE_TYPE = "npm"
    FILE_PATTERNS = ["package.json", "package-lock.json", "npm-shrinkwrap.json"]
    ARCHIVE_EXTENSIONS = [".tgz", ".tar.gz"]
    
    def detect_from_file(self, file_path: Path) -> DetectorResult:
        """Detect NPM package from file."""
        if not self.can_handle_file(file_path):
            return DetectorResult(detected=False)
        
        # Handle package.json
        if file_path.name == "package.json":
            return self._detect_from_package_json(file_path)
        
        # Handle package-lock.json
        if file_path.name == "package-lock.json":
            return self._detect_from_package_lock(file_path)
        
        # Handle archives
        if file_path.suffix in [".tgz", ".gz"]:
            return self._detect_from_archive(file_path)
        
        return DetectorResult(detected=False)
    
    def detect_from_directory(self, directory: Path) -> List[DetectorResult]:
        """Detect NPM packages in directory."""
        results = []
        
        # Look for package.json
        package_json = directory / "package.json"
        if package_json.exists():
            result = self._detect_from_package_json(package_json)
            if result.detected:
                results.append(result)
        
        # Look for node_modules (each subdirectory is a package)
        node_modules = directory / "node_modules"
        if node_modules.exists() and node_modules.is_dir():
            for package_dir in node_modules.iterdir():
                if package_dir.is_dir() and not package_dir.name.startswith('.'):
                    # Handle scoped packages
                    if package_dir.name.startswith('@'):
                        for scoped_package in package_dir.iterdir():
                            if scoped_package.is_dir():
                                pkg_json = scoped_package / "package.json"
                                if pkg_json.exists():
                                    result = self._detect_from_package_json(pkg_json)
                                    if result.detected:
                                        results.append(result)
                    else:
                        pkg_json = package_dir / "package.json"
                        if pkg_json.exists():
                            result = self._detect_from_package_json(pkg_json)
                            if result.detected:
                                results.append(result)
        
        return results
    
    def _detect_from_package_json(self, package_json: Path) -> DetectorResult:
        """Extract package info from package.json."""
        try:
            with open(package_json, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            name = data.get('name', '')
            version = data.get('version', '')
            
            if not name:
                return DetectorResult(detected=False)
            
            # Handle scoped packages
            namespace = None
            if name.startswith('@'):
                parts = name.split('/')
                if len(parts) == 2:
                    namespace = parts[0][1:]  # Remove @
                    name = parts[1]
            
            purl = self._build_purl(name, version, namespace)
            
            return DetectorResult(
                detected=True,
                package_type=self.PACKAGE_TYPE,
                name=name,
                version=version,
                namespace=namespace,
                purl=purl,
                metadata={
                    'description': data.get('description', ''),
                    'license': data.get('license', ''),
                    'author': data.get('author', ''),
                    'dependencies': data.get('dependencies', {}),
                    'source_file': str(package_json)
                },
                confidence=1.0
            )
        except Exception:
            return DetectorResult(detected=False)
    
    def _detect_from_package_lock(self, lock_file: Path) -> DetectorResult:
        """Extract package info from package-lock.json."""
        try:
            with open(lock_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            name = data.get('name', '')
            version = data.get('version', '')
            
            if not name:
                return DetectorResult(detected=False)
            
            return DetectorResult(
                detected=True,
                package_type=self.PACKAGE_TYPE,
                name=name,
                version=version,
                purl=self._build_purl(name, version),
                metadata={'source_file': str(lock_file)},
                confidence=0.9
            )
        except Exception:
            return DetectorResult(detected=False)
    
    def _detect_from_archive(self, archive_path: Path) -> DetectorResult:
        """Extract package info from NPM tarball."""
        try:
            with tarfile.open(archive_path, 'r:*') as tar:
                # NPM packages have package/package.json structure
                for member in tar.getmembers():
                    if member.name == 'package/package.json' or member.name.endswith('/package.json'):
                        f = tar.extractfile(member)
                        if f:
                            data = json.loads(f.read().decode('utf-8'))
                            name = data.get('name', '')
                            version = data.get('version', '')
                            
                            if name:
                                # Handle scoped packages
                                namespace = None
                                if name.startswith('@'):
                                    parts = name.split('/')
                                    if len(parts) == 2:
                                        namespace = parts[0][1:]
                                        name = parts[1]
                                
                                return DetectorResult(
                                    detected=True,
                                    package_type=self.PACKAGE_TYPE,
                                    name=name,
                                    version=version,
                                    namespace=namespace,
                                    purl=self._build_purl(name, version, namespace),
                                    metadata={
                                        'source_archive': str(archive_path),
                                        'license': data.get('license', '')
                                    },
                                    confidence=1.0
                                )
        except Exception:
            pass
        
        # Try to extract from filename
        filename = archive_path.stem
        if '-' in filename:
            parts = filename.rsplit('-', 1)
            if len(parts) == 2:
                name, version = parts
                return DetectorResult(
                    detected=True,
                    package_type=self.PACKAGE_TYPE,
                    name=name,
                    version=version,
                    purl=self._build_purl(name, version),
                    metadata={'source_archive': str(archive_path)},
                    confidence=0.5
                )
        
        return DetectorResult(detected=False)