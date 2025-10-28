"""Package scanner for directory mode."""

import os
import json
import magic
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from fnmatch import fnmatch
import tarfile
import zipfile
from packageurl import PackageURL

from .config import Config
from .models import Package
from .utils import get_archive_type, guess_purl_from_archive


class PackageScanner:
    """Scan directories for packages and metadata."""
    
    def __init__(self, config: Config):
        """Initialize scanner."""
        self.config = config
        self.file_magic = magic.Magic(mime=True)
    
    def scan_directory(
        self,
        directory: Path,
        recursive: bool = True,
        max_depth: int = 10,
        exclude_patterns: Optional[List[str]] = None
    ) -> Tuple[List[Package], List[Path]]:
        """
        Scan directory for packages.
        
        Returns:
            Tuple of (identified_packages, unidentified_paths)
        """
        if not directory.exists() or not directory.is_dir():
            raise ValueError(f"Invalid directory: {directory}")
        
        exclude_patterns = exclude_patterns or self.config.get("scanning.exclude_patterns", [])
        
        packages = []
        unidentified_paths = []
        
        # Scan for archives and metadata files
        archives = self._find_archives(directory, recursive, max_depth, exclude_patterns)
        metadata_files = self._find_metadata_files(directory, recursive, max_depth, exclude_patterns)
        
        # Process archives
        for archive_path in archives:
            package = self._process_archive(archive_path)
            if package:
                packages.append(package)
            else:
                unidentified_paths.append(archive_path)
        
        # Process metadata files
        metadata_packages = self._process_metadata_files(metadata_files)
        packages.extend(metadata_packages)
        
        # If no packages found, mark entire directory for OSSLILI processing
        if not packages and not unidentified_paths:
            unidentified_paths.append(directory)
        
        return packages, unidentified_paths
    
    def _find_archives(
        self,
        directory: Path,
        recursive: bool,
        max_depth: int,
        exclude_patterns: List[str]
    ) -> List[Path]:
        """Find archive files in directory."""
        archives = []
        
        for root, dirs, files in os.walk(directory):
            # Check depth
            depth = len(Path(root).relative_to(directory).parts)
            if not recursive or depth >= max_depth:
                dirs.clear()
                if not recursive:
                    break
            
            # Apply exclusions to directories
            dirs[:] = [d for d in dirs if not self._is_excluded(Path(root) / d, exclude_patterns)]
            
            # Find archives
            for file in files:
                file_path = Path(root) / file
                if self._is_excluded(file_path, exclude_patterns):
                    continue
                
                # Check if it's an archive file
                if get_archive_type(file_path):
                    archives.append(file_path)
        
        return archives
    
    def _find_metadata_files(
        self,
        directory: Path,
        recursive: bool,
        max_depth: int,
        exclude_patterns: List[str]
    ) -> Dict[str, List[Path]]:
        """Find package metadata files grouped by type."""
        metadata_files = {ecosystem: [] for ecosystem in Config.METADATA_PATTERNS}
        
        for root, dirs, files in os.walk(directory):
            # Check depth
            depth = len(Path(root).relative_to(directory).parts)
            if not recursive or depth >= max_depth:
                dirs.clear()
                if not recursive:
                    break
            
            # Apply exclusions
            dirs[:] = [d for d in dirs if not self._is_excluded(Path(root) / d, exclude_patterns)]
            
            # Find metadata files
            for file in files:
                file_path = Path(root) / file
                if self._is_excluded(file_path, exclude_patterns):
                    continue
                
                # Check against patterns
                for ecosystem, patterns in Config.METADATA_PATTERNS.items():
                    for pattern in patterns:
                        if fnmatch(file, pattern):
                            metadata_files[ecosystem].append(file_path)
                            break
        
        return metadata_files
    
    def _is_excluded(self, path: Path, exclude_patterns: List[str]) -> bool:
        """Check if path matches exclusion patterns."""
        path_str = str(path)
        for pattern in exclude_patterns:
            if fnmatch(path_str, pattern):
                return True
        return False
    
    def _process_archive(self, archive_path: Path) -> Optional[Package]:
        """Process an archive file to extract package info."""
        try:
            # Try to guess PURL from archive filename first
            purl = guess_purl_from_archive(archive_path)
            if purl:
                from packageurl import PackageURL
                parsed = PackageURL.from_string(purl)
                return Package(
                    purl=purl,
                    name=parsed.name,
                    version=parsed.version or '',
                    type=parsed.type,
                    namespace=parsed.namespace,
                    source_path=str(archive_path)
                )
            
            # Fallback to specific processing for complex cases
            if archive_path.suffix == '.jar':
                return self._process_jar(archive_path)
            elif archive_path.name.endswith(('.tar.gz', '.tgz')):
                return self._process_tarball(archive_path)
            else:
                # Generic archive processing
                archive_type = get_archive_type(archive_path)
                return Package(
                    name=archive_path.stem,
                    type=archive_type or 'archive',
                    source_path=str(archive_path)
                )
        except Exception:
            return None
    
    
    def _process_jar(self, jar_path: Path) -> Optional[Package]:
        """Process Java JAR file."""
        try:
            # Try to extract Maven coordinates from JAR
            with zipfile.ZipFile(jar_path, 'r') as jar:
                # Look for pom.properties
                for name in jar.namelist():
                    if name.endswith('pom.properties'):
                        with jar.open(name) as f:
                            props = {}
                            for line in f.read().decode('utf-8').splitlines():
                                if '=' in line:
                                    key, value = line.split('=', 1)
                                    props[key.strip()] = value.strip()
                            
                            if 'groupId' in props and 'artifactId' in props:
                                group_id = props['groupId']
                                artifact_id = props['artifactId']
                                version = props.get('version', 'unknown')
                                
                                purl = PackageURL(
                                    type='maven',
                                    namespace=group_id,
                                    name=artifact_id,
                                    version=version
                                ).to_string()
                                
                                return Package(
                                    purl=purl,
                                    name=artifact_id,
                                    version=version,
                                    type='maven',
                                    namespace=group_id,
                                    source_path=str(jar_path)
                                )
        except Exception:
            pass
        
        # Fallback: use filename
        return Package(
            name=jar_path.stem,
            type='maven',
            source_path=str(jar_path)
        )
    
    
    def _process_tarball(self, tarball_path: Path) -> Optional[Package]:
        """Process tarball archive."""
        try:
            # Try to extract package info from tarball
            with tarfile.open(tarball_path, 'r:*') as tar:
                # Look for package.json (npm)
                for member in tar.getmembers():
                    if member.name.endswith('package.json'):
                        f = tar.extractfile(member)
                        if f:
                            data = json.loads(f.read().decode('utf-8'))
                            name = data.get('name', '')
                            version = data.get('version', '')
                            
                            if name:
                                purl = PackageURL(
                                    type='npm',
                                    name=name,
                                    version=version
                                ).to_string()
                                
                                return Package(
                                    purl=purl,
                                    name=name,
                                    version=version,
                                    type='npm',
                                    source_path=str(tarball_path)
                                )
        except Exception:
            pass
        
        # Fallback: use filename
        return Package(
            name=tarball_path.stem.replace('.tar', ''),
            source_path=str(tarball_path)
        )
    
    def _process_metadata_files(self, metadata_files: Dict[str, List[Path]]) -> List[Package]:
        """Process metadata files to extract package info."""
        packages = []
        
        # Process npm packages
        for package_json in metadata_files.get('npm', []):
            pkg = self._process_package_json(package_json)
            if pkg:
                packages.append(pkg)
        
        # Process Python packages
        for pyproject in metadata_files.get('pypi', []):
            if pyproject.name == 'pyproject.toml':
                pkg = self._process_pyproject_toml(pyproject)
                if pkg:
                    packages.append(pkg)
            elif pyproject.name == 'setup.py':
                pkg = self._process_setup_py(pyproject)
                if pkg:
                    packages.append(pkg)
        
        # Process Maven packages
        for pom in metadata_files.get('maven', []):
            pkg = self._process_pom_xml(pom)
            if pkg:
                packages.append(pkg)
        
        # Add more processors as needed...
        
        return packages
    
    def _process_package_json(self, path: Path) -> Optional[Package]:
        """Process package.json file."""
        try:
            with open(path, 'r') as f:
                data = json.load(f)
            
            name = data.get('name', '')
            version = data.get('version', '')
            
            if name:
                purl = PackageURL(
                    type='npm',
                    name=name,
                    version=version
                ).to_string()
                
                return Package(
                    purl=purl,
                    name=name,
                    version=version,
                    type='npm',
                    source_path=str(path.parent)
                )
        except Exception:
            pass
        return None
    
    def _process_pyproject_toml(self, path: Path) -> Optional[Package]:
        """Process pyproject.toml file."""
        try:
            try:
                import tomllib  # Python 3.11+
            except ImportError:
                import tomli as tomllib  # Python 3.8-3.10
            with open(path, 'rb') as f:
                data = tomllib.load(f)
            
            project = data.get('project', {})
            name = project.get('name', '')
            version = project.get('version', '')
            
            if name:
                purl = PackageURL(
                    type='pypi',
                    name=name.lower(),
                    version=version
                ).to_string()
                
                return Package(
                    purl=purl,
                    name=name,
                    version=version,
                    type='pypi',
                    source_path=str(path.parent)
                )
        except Exception:
            pass
        return None
    
    def _process_setup_py(self, path: Path) -> Optional[Package]:
        """Process setup.py file (basic extraction)."""
        # This is simplified - full parsing would require AST analysis
        return Package(
            name=path.parent.name,
            type='pypi',
            source_path=str(path.parent)
        )
    
    def _process_pom_xml(self, path: Path) -> Optional[Package]:
        """Process pom.xml file."""
        try:
            import xml.etree.ElementTree as ET
            tree = ET.parse(path)
            root = tree.getroot()
            
            # Handle namespace
            ns = {'m': 'http://maven.apache.org/POM/4.0.0'}
            
            group_id = root.find('.//m:groupId', ns)
            artifact_id = root.find('.//m:artifactId', ns)
            version = root.find('.//m:version', ns)
            
            if artifact_id is not None:
                name = artifact_id.text
                namespace = group_id.text if group_id is not None else None
                ver = version.text if version is not None else ''
                
                purl = PackageURL(
                    type='maven',
                    namespace=namespace,
                    name=name,
                    version=ver
                ).to_string()
                
                return Package(
                    purl=purl,
                    name=name,
                    version=ver,
                    type='maven',
                    namespace=namespace,
                    source_path=str(path.parent)
                )
        except Exception:
            pass
        return None