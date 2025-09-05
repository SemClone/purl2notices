"""PyPI package detector."""

import json
import zipfile
import tarfile
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
from email.parser import Parser

from .base import BaseDetector, DetectorResult


class PyPiDetector(BaseDetector):
    """Detector for Python/PyPI packages."""
    
    PACKAGE_TYPE = "pypi"
    FILE_PATTERNS = [
        "setup.py", "setup.cfg", "pyproject.toml",
        "requirements.txt", "Pipfile", "Pipfile.lock",
        "poetry.lock", "pdm.lock", "*.whl", "*.egg"
    ]
    ARCHIVE_EXTENSIONS = [".whl", ".tar.gz", ".zip", ".egg"]
    
    def detect_from_file(self, file_path: Path) -> DetectorResult:
        """Detect PyPI package from file."""
        if not self.can_handle_file(file_path):
            return DetectorResult(detected=False)
        
        # Handle different file types
        if file_path.name == "pyproject.toml":
            return self._detect_from_pyproject_toml(file_path)
        elif file_path.name == "setup.cfg":
            return self._detect_from_setup_cfg(file_path)
        elif file_path.name == "setup.py":
            return self._detect_from_setup_py(file_path)
        elif file_path.suffix == ".whl":
            return self._detect_from_wheel(file_path)
        elif file_path.name.endswith((".tar.gz", ".zip")):
            return self._detect_from_sdist(file_path)
        
        return DetectorResult(detected=False)
    
    def detect_from_directory(self, directory: Path) -> List[DetectorResult]:
        """Detect Python packages in directory."""
        results = []
        
        # Priority order for detection
        detection_files = [
            ("pyproject.toml", self._detect_from_pyproject_toml),
            ("setup.cfg", self._detect_from_setup_cfg),
            ("setup.py", self._detect_from_setup_py),
            ("PKG-INFO", self._detect_from_pkg_info)
        ]
        
        for filename, detector_func in detection_files:
            file_path = directory / filename
            if file_path.exists():
                result = detector_func(file_path)
                if result.detected:
                    results.append(result)
                    break  # Use first successful detection
        
        # Check for .dist-info or .egg-info directories
        for path in directory.iterdir():
            if path.is_dir():
                if path.name.endswith('.dist-info'):
                    metadata_file = path / 'METADATA'
                    if metadata_file.exists():
                        result = self._detect_from_metadata(metadata_file)
                        if result.detected:
                            results.append(result)
                elif path.name.endswith('.egg-info'):
                    pkg_info = path / 'PKG-INFO'
                    if pkg_info.exists():
                        result = self._detect_from_pkg_info(pkg_info)
                        if result.detected:
                            results.append(result)
        
        return results
    
    def _detect_from_pyproject_toml(self, file_path: Path) -> DetectorResult:
        """Extract package info from pyproject.toml."""
        try:
            try:
                import tomllib  # Python 3.11+
            except ImportError:
                import tomli as tomllib  # Python 3.8-3.10
            
            with open(file_path, 'rb') as f:
                data = tomllib.load(f)
            
            # Check for PEP 621 metadata
            if 'project' in data:
                project = data['project']
                name = project.get('name', '')
                version = project.get('version', '')
                
                if not name:
                    return DetectorResult(detected=False)
                
                # Normalize name for PyPI
                normalized_name = re.sub(r'[-_.]+', '-', name).lower()
                
                return DetectorResult(
                    detected=True,
                    package_type=self.PACKAGE_TYPE,
                    name=normalized_name,
                    version=version,
                    purl=self._build_purl(normalized_name, version),
                    metadata={
                        'description': project.get('description', ''),
                        'license': self._extract_license_from_pyproject(project),
                        'authors': project.get('authors', []),
                        'dependencies': project.get('dependencies', []),
                        'source_file': str(file_path)
                    },
                    confidence=1.0
                )
            
            # Check for Poetry
            if 'tool' in data and 'poetry' in data['tool']:
                poetry = data['tool']['poetry']
                name = poetry.get('name', '')
                version = poetry.get('version', '')
                
                if name:
                    normalized_name = re.sub(r'[-_.]+', '-', name).lower()
                    return DetectorResult(
                        detected=True,
                        package_type=self.PACKAGE_TYPE,
                        name=normalized_name,
                        version=version,
                        purl=self._build_purl(normalized_name, version),
                        metadata={
                            'description': poetry.get('description', ''),
                            'license': poetry.get('license', ''),
                            'source_file': str(file_path)
                        },
                        confidence=1.0
                    )
        except Exception:
            pass
        
        return DetectorResult(detected=False)
    
    def _detect_from_setup_cfg(self, file_path: Path) -> DetectorResult:
        """Extract package info from setup.cfg."""
        try:
            import configparser
            config = configparser.ConfigParser()
            config.read(file_path)
            
            if 'metadata' in config:
                metadata = config['metadata']
                name = metadata.get('name', '')
                version = metadata.get('version', '')
                
                if name:
                    normalized_name = re.sub(r'[-_.]+', '-', name).lower()
                    return DetectorResult(
                        detected=True,
                        package_type=self.PACKAGE_TYPE,
                        name=normalized_name,
                        version=version,
                        purl=self._build_purl(normalized_name, version),
                        metadata={
                            'description': metadata.get('description', ''),
                            'license': metadata.get('license', ''),
                            'author': metadata.get('author', ''),
                            'source_file': str(file_path)
                        },
                        confidence=0.9
                    )
        except Exception:
            pass
        
        return DetectorResult(detected=False)
    
    def _detect_from_setup_py(self, file_path: Path) -> DetectorResult:
        """Extract package info from setup.py (basic parsing)."""
        try:
            content = file_path.read_text(encoding='utf-8')
            
            # Basic regex extraction (not perfect but works for simple cases)
            name_match = re.search(r'name\s*=\s*["\']([^"\']+)["\']', content)
            version_match = re.search(r'version\s*=\s*["\']([^"\']+)["\']', content)
            
            if name_match:
                name = name_match.group(1)
                version = version_match.group(1) if version_match else ''
                normalized_name = re.sub(r'[-_.]+', '-', name).lower()
                
                return DetectorResult(
                    detected=True,
                    package_type=self.PACKAGE_TYPE,
                    name=normalized_name,
                    version=version,
                    purl=self._build_purl(normalized_name, version),
                    metadata={'source_file': str(file_path)},
                    confidence=0.7
                )
        except Exception:
            pass
        
        # Fallback: use directory name
        return DetectorResult(
            detected=True,
            package_type=self.PACKAGE_TYPE,
            name=file_path.parent.name.lower(),
            version='',
            metadata={'source_file': str(file_path)},
            confidence=0.3
        )
    
    def _detect_from_wheel(self, wheel_path: Path) -> DetectorResult:
        """Extract package info from wheel file."""
        try:
            # Parse wheel filename: {name}-{version}-{python}-{abi}-{platform}.whl
            filename = wheel_path.stem
            parts = filename.split('-')
            
            if len(parts) >= 2:
                name = parts[0]
                version = parts[1]
                normalized_name = re.sub(r'[_]+', '-', name).lower()
                
                # Try to get more info from METADATA inside wheel
                metadata = {}
                try:
                    with zipfile.ZipFile(wheel_path, 'r') as wheel:
                        # Find .dist-info/METADATA
                        for file_name in wheel.namelist():
                            if file_name.endswith('.dist-info/METADATA'):
                                with wheel.open(file_name) as f:
                                    content = f.read().decode('utf-8')
                                    parsed = Parser().parsestr(content)
                                    metadata['license'] = parsed.get('License', '')
                                    metadata['summary'] = parsed.get('Summary', '')
                                    metadata['author'] = parsed.get('Author', '')
                                break
                except Exception:
                    pass
                
                metadata['source_archive'] = str(wheel_path)
                
                return DetectorResult(
                    detected=True,
                    package_type=self.PACKAGE_TYPE,
                    name=normalized_name,
                    version=version,
                    purl=self._build_purl(normalized_name, version),
                    metadata=metadata,
                    confidence=1.0
                )
        except Exception:
            pass
        
        return DetectorResult(detected=False)
    
    def _detect_from_sdist(self, archive_path: Path) -> DetectorResult:
        """Extract package info from source distribution."""
        try:
            # Try to extract PKG-INFO from archive
            if archive_path.suffix == '.gz':
                with tarfile.open(archive_path, 'r:*') as tar:
                    for member in tar.getmembers():
                        if '/PKG-INFO' in member.name or member.name == 'PKG-INFO':
                            f = tar.extractfile(member)
                            if f:
                                content = f.read().decode('utf-8')
                                return self._parse_pkg_info_content(content, archive_path)
            elif archive_path.suffix == '.zip':
                with zipfile.ZipFile(archive_path, 'r') as zip_file:
                    for file_name in zip_file.namelist():
                        if '/PKG-INFO' in file_name or file_name == 'PKG-INFO':
                            with zip_file.open(file_name) as f:
                                content = f.read().decode('utf-8')
                                return self._parse_pkg_info_content(content, archive_path)
        except Exception:
            pass
        
        # Fallback: parse filename
        filename = archive_path.stem
        if filename.endswith('.tar'):
            filename = filename[:-4]
        
        # Common pattern: package-version
        if '-' in filename:
            parts = filename.rsplit('-', 1)
            if len(parts) == 2 and parts[1][0].isdigit():
                name, version = parts
                normalized_name = re.sub(r'[-_.]+', '-', name).lower()
                return DetectorResult(
                    detected=True,
                    package_type=self.PACKAGE_TYPE,
                    name=normalized_name,
                    version=version,
                    purl=self._build_purl(normalized_name, version),
                    metadata={'source_archive': str(archive_path)},
                    confidence=0.6
                )
        
        return DetectorResult(detected=False)
    
    def _detect_from_pkg_info(self, file_path: Path) -> DetectorResult:
        """Extract package info from PKG-INFO file."""
        try:
            content = file_path.read_text(encoding='utf-8')
            return self._parse_pkg_info_content(content, file_path)
        except Exception:
            return DetectorResult(detected=False)
    
    def _detect_from_metadata(self, file_path: Path) -> DetectorResult:
        """Extract package info from METADATA file."""
        try:
            content = file_path.read_text(encoding='utf-8')
            return self._parse_pkg_info_content(content, file_path)
        except Exception:
            return DetectorResult(detected=False)
    
    def _parse_pkg_info_content(self, content: str, source_path: Path) -> DetectorResult:
        """Parse PKG-INFO or METADATA content."""
        try:
            parsed = Parser().parsestr(content)
            name = parsed.get('Name', '')
            version = parsed.get('Version', '')
            
            if name:
                normalized_name = re.sub(r'[-_.]+', '-', name).lower()
                return DetectorResult(
                    detected=True,
                    package_type=self.PACKAGE_TYPE,
                    name=normalized_name,
                    version=version,
                    purl=self._build_purl(normalized_name, version),
                    metadata={
                        'summary': parsed.get('Summary', ''),
                        'license': parsed.get('License', ''),
                        'author': parsed.get('Author', ''),
                        'source_file': str(source_path)
                    },
                    confidence=1.0
                )
        except Exception:
            pass
        
        return DetectorResult(detected=False)
    
    def _extract_license_from_pyproject(self, project: Dict) -> str:
        """Extract license from pyproject.toml project section."""
        license_info = project.get('license', {})
        if isinstance(license_info, dict):
            return license_info.get('text', '') or license_info.get('file', '')
        elif isinstance(license_info, str):
            return license_info
        return ''