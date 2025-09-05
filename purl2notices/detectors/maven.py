"""Maven/Java package detector."""

import xml.etree.ElementTree as ET
import zipfile
import json
from pathlib import Path
from typing import List, Dict, Any, Optional

from .base import BaseDetector, DetectorResult


class MavenDetector(BaseDetector):
    """Detector for Maven/Java packages."""
    
    PACKAGE_TYPE = "maven"
    FILE_PATTERNS = ["pom.xml", "*.pom", "build.gradle", "build.gradle.kts"]
    ARCHIVE_EXTENSIONS = [".jar", ".war", ".ear", ".aar"]
    
    # Maven namespace
    MAVEN_NS = {'m': 'http://maven.apache.org/POM/4.0.0'}
    
    def detect_from_file(self, file_path: Path) -> DetectorResult:
        """Detect Maven package from file."""
        if not self.can_handle_file(file_path):
            return DetectorResult(detected=False)
        
        if file_path.name == "pom.xml" or file_path.suffix == ".pom":
            return self._detect_from_pom(file_path)
        elif file_path.suffix in [".jar", ".war", ".ear", ".aar"]:
            return self._detect_from_jar(file_path)
        elif file_path.name in ["build.gradle", "build.gradle.kts"]:
            return self._detect_from_gradle(file_path)
        
        return DetectorResult(detected=False)
    
    def detect_from_directory(self, directory: Path) -> List[DetectorResult]:
        """Detect Maven packages in directory."""
        results = []
        
        # Look for pom.xml
        pom_file = directory / "pom.xml"
        if pom_file.exists():
            result = self._detect_from_pom(pom_file)
            if result.detected:
                results.append(result)
        
        # Look for build.gradle
        gradle_file = directory / "build.gradle"
        if gradle_file.exists():
            result = self._detect_from_gradle(gradle_file)
            if result.detected:
                results.append(result)
        
        # Look for JAR files in target or build directories
        for subdir in ['target', 'build', 'build/libs', 'target/libs']:
            jar_dir = directory / subdir
            if jar_dir.exists():
                for jar_file in jar_dir.glob('*.jar'):
                    if not jar_file.name.endswith('-sources.jar') and not jar_file.name.endswith('-javadoc.jar'):
                        result = self._detect_from_jar(jar_file)
                        if result.detected:
                            results.append(result)
        
        return results
    
    def _detect_from_pom(self, pom_file: Path) -> DetectorResult:
        """Extract package info from pom.xml."""
        try:
            tree = ET.parse(pom_file)
            root = tree.getroot()
            
            # Handle namespace
            if root.tag.startswith('{'):
                ns = {'m': root.tag[1:root.tag.index('}')]}
            else:
                ns = {'m': ''}
            
            # Extract coordinates
            group_id = self._get_element_text(root, './/m:groupId', ns)
            artifact_id = self._get_element_text(root, './/m:artifactId', ns)
            version = self._get_element_text(root, './/m:version', ns)
            
            # Check parent for missing values
            parent = root.find('.//m:parent', ns)
            if parent is not None:
                if not group_id:
                    group_id = self._get_element_text(parent, './/m:groupId', ns)
                if not version:
                    version = self._get_element_text(parent, './/m:version', ns)
            
            if not artifact_id:
                return DetectorResult(detected=False)
            
            # Extract additional metadata
            metadata = {
                'packaging': self._get_element_text(root, './/m:packaging', ns) or 'jar',
                'name': self._get_element_text(root, './/m:name', ns),
                'description': self._get_element_text(root, './/m:description', ns),
                'url': self._get_element_text(root, './/m:url', ns),
                'source_file': str(pom_file)
            }
            
            # Extract licenses
            licenses = []
            for license_elem in root.findall('.//m:licenses/m:license', ns):
                license_name = self._get_element_text(license_elem, './/m:name', ns)
                license_url = self._get_element_text(license_elem, './/m:url', ns)
                if license_name:
                    licenses.append({'name': license_name, 'url': license_url})
            metadata['licenses'] = licenses
            
            purl = self._build_purl(artifact_id, version, group_id)
            
            return DetectorResult(
                detected=True,
                package_type=self.PACKAGE_TYPE,
                name=artifact_id,
                version=version or '',
                namespace=group_id,
                purl=purl,
                metadata=metadata,
                confidence=1.0
            )
        except Exception:
            return DetectorResult(detected=False)
    
    def _detect_from_jar(self, jar_file: Path) -> DetectorResult:
        """Extract package info from JAR file."""
        try:
            with zipfile.ZipFile(jar_file, 'r') as jar:
                # Look for pom.properties
                pom_properties = None
                manifest = None
                
                for name in jar.namelist():
                    if name.endswith('pom.properties'):
                        pom_properties = name
                    elif name == 'META-INF/MANIFEST.MF':
                        manifest = name
                
                # Try pom.properties first
                if pom_properties:
                    with jar.open(pom_properties) as f:
                        props = {}
                        for line in f.read().decode('utf-8').splitlines():
                            if '=' in line and not line.startswith('#'):
                                key, value = line.split('=', 1)
                                props[key.strip()] = value.strip()
                        
                        group_id = props.get('groupId', '')
                        artifact_id = props.get('artifactId', '')
                        version = props.get('version', '')
                        
                        if artifact_id:
                            return DetectorResult(
                                detected=True,
                                package_type=self.PACKAGE_TYPE,
                                name=artifact_id,
                                version=version,
                                namespace=group_id,
                                purl=self._build_purl(artifact_id, version, group_id),
                                metadata={'source_archive': str(jar_file)},
                                confidence=1.0
                            )
                
                # Try MANIFEST.MF
                if manifest:
                    with jar.open(manifest) as f:
                        manifest_content = f.read().decode('utf-8')
                        manifest_data = self._parse_manifest(manifest_content)
                        
                        # Try to extract from Implementation or Bundle headers
                        artifact_id = (
                            manifest_data.get('Bundle-SymbolicName', '') or
                            manifest_data.get('Implementation-Title', '') or
                            manifest_data.get('Bundle-Name', '')
                        )
                        version = (
                            manifest_data.get('Bundle-Version', '') or
                            manifest_data.get('Implementation-Version', '') or
                            manifest_data.get('Specification-Version', '')
                        )
                        vendor = manifest_data.get('Implementation-Vendor', '')
                        
                        if artifact_id:
                            # Clean bundle symbolic name
                            if ';' in artifact_id:
                                artifact_id = artifact_id.split(';')[0]
                            
                            return DetectorResult(
                                detected=True,
                                package_type=self.PACKAGE_TYPE,
                                name=artifact_id,
                                version=version,
                                namespace=vendor,
                                purl=self._build_purl(artifact_id, version, vendor),
                                metadata={
                                    'source_archive': str(jar_file),
                                    'manifest': manifest_data
                                },
                                confidence=0.7
                            )
        except Exception:
            pass
        
        # Fallback: parse filename
        return self._detect_from_jar_filename(jar_file)
    
    def _detect_from_jar_filename(self, jar_file: Path) -> DetectorResult:
        """Try to extract info from JAR filename."""
        filename = jar_file.stem
        
        # Common pattern: artifact-version.jar
        if '-' in filename:
            parts = filename.rsplit('-', 1)
            if len(parts) == 2:
                name, version = parts
                # Check if last part looks like version
                if version and (version[0].isdigit() or version.startswith('v')):
                    return DetectorResult(
                        detected=True,
                        package_type=self.PACKAGE_TYPE,
                        name=name,
                        version=version,
                        purl=self._build_purl(name, version),
                        metadata={'source_archive': str(jar_file)},
                        confidence=0.4
                    )
        
        # No version in filename
        return DetectorResult(
            detected=True,
            package_type=self.PACKAGE_TYPE,
            name=filename,
            version='',
            metadata={'source_archive': str(jar_file)},
            confidence=0.3
        )
    
    def _detect_from_gradle(self, gradle_file: Path) -> DetectorResult:
        """Extract package info from build.gradle (basic parsing)."""
        try:
            content = gradle_file.read_text(encoding='utf-8')
            
            # Basic extraction (Gradle files are complex to parse properly)
            group_match = self._search_gradle_property(content, 'group')
            name_match = self._search_gradle_property(content, ['archivesBaseName', 'artifactId', 'name'])
            version_match = self._search_gradle_property(content, 'version')
            
            name = name_match or gradle_file.parent.name
            
            if name:
                return DetectorResult(
                    detected=True,
                    package_type=self.PACKAGE_TYPE,
                    name=name,
                    version=version_match or '',
                    namespace=group_match,
                    purl=self._build_purl(name, version_match, group_match),
                    metadata={'source_file': str(gradle_file)},
                    confidence=0.6
                )
        except Exception:
            pass
        
        return DetectorResult(detected=False)
    
    def _get_element_text(self, element: ET.Element, path: str, ns: Dict) -> Optional[str]:
        """Get text from XML element."""
        elem = element.find(path, ns)
        return elem.text if elem is not None else None
    
    def _parse_manifest(self, content: str) -> Dict[str, str]:
        """Parse MANIFEST.MF content."""
        manifest = {}
        current_key = None
        current_value = []
        
        for line in content.splitlines():
            if line and line[0] == ' ':
                # Continuation line
                if current_key:
                    current_value.append(line[1:])
            elif ':' in line:
                # Save previous key-value
                if current_key:
                    manifest[current_key] = ''.join(current_value)
                # Parse new key-value
                key, value = line.split(':', 1)
                current_key = key.strip()
                current_value = [value.strip()]
        
        # Save last key-value
        if current_key:
            manifest[current_key] = ''.join(current_value)
        
        return manifest
    
    def _search_gradle_property(self, content: str, properties: Any) -> Optional[str]:
        """Search for property in Gradle file."""
        import re
        
        if isinstance(properties, str):
            properties = [properties]
        
        for prop in properties:
            # Look for: property = value or property = "value" or property = 'value'
            patterns = [
                rf'{prop}\s*=\s*["\']([^"\']+)["\']',
                rf'{prop}\s*=\s*([^\s]+)',
                rf'{prop}\s+["\']([^"\']+)["\']'
            ]
            
            for pattern in patterns:
                match = re.search(pattern, content)
                if match:
                    return match.group(1)
        
        return None