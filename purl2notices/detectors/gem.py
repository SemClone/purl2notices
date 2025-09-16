"""Ruby Gem and Chef cookbook package detector."""

import re
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any
from .base import BaseDetector, DetectorResult

logger = logging.getLogger(__name__)


class GemDetector(BaseDetector):
    """Detector for Ruby Gems and Chef cookbooks."""

    PACKAGE_TYPE = "gem"
    FILE_PATTERNS = ["Gemfile", "Gemfile.lock", "*.gemspec", "metadata.rb", "metadata.json"]
    ARCHIVE_EXTENSIONS = [".gem"]

    def detect_from_file(self, file_path: Path) -> DetectorResult:
        """Detect Gem package from file."""
        if not file_path.exists():
            return DetectorResult(detected=False)

        file_name = file_path.name

        # Check for Chef cookbook metadata
        if file_name == "metadata.rb":
            result = self._parse_chef_metadata_rb(file_path)
            if result:
                return result
        elif file_name == "metadata.json":
            result = self._parse_chef_metadata_json(file_path)
            if result:
                return result

        # Check for gemspec file
        if file_name.endswith(".gemspec"):
            result = self._parse_gemspec(file_path)
            if result:
                return result

        # Check for Gemfile
        if file_name in ["Gemfile", "Gemfile.lock"]:
            # Gemfile doesn't define a package itself, just dependencies
            # Return detected but without package info
            return DetectorResult(
                detected=True,
                package_type=self.PACKAGE_TYPE,
                metadata={'source_file': str(file_path)}
            )

        # Check for .gem archive
        if file_name.endswith(".gem"):
            return self._detect_from_gem_archive(file_path)

        return DetectorResult(detected=False)

    def detect_from_directory(self, directory: Path) -> List[DetectorResult]:
        """Detect Gem packages in directory."""
        results = []

        # Look for Chef cookbooks (metadata.rb or metadata.json)
        for metadata_file in directory.rglob("metadata.rb"):
            result = self._parse_chef_metadata_rb(metadata_file)
            if result and result.detected:
                results.append(result)
                logger.debug(f"Detected Chef cookbook: {result.name}@{result.version}")

        for metadata_file in directory.rglob("metadata.json"):
            # Skip if we already found metadata.rb in same directory
            if (metadata_file.parent / "metadata.rb").exists():
                continue
            result = self._parse_chef_metadata_json(metadata_file)
            if result and result.detected:
                results.append(result)
                logger.debug(f"Detected Chef cookbook: {result.name}@{result.version}")

        # Look for Ruby gems (*.gemspec)
        for gemspec in directory.rglob("*.gemspec"):
            result = self._parse_gemspec(gemspec)
            if result and result.detected:
                results.append(result)
                logger.debug(f"Detected Ruby gem: {result.name}@{result.version}")

        # Look for .gem archives
        for gem_file in directory.rglob("*.gem"):
            result = self._detect_from_gem_archive(gem_file)
            if result and result.detected:
                results.append(result)
                logger.debug(f"Detected Ruby gem archive: {result.name}@{result.version}")

        return results

    def _parse_chef_metadata_rb(self, metadata_file: Path) -> Optional[DetectorResult]:
        """Parse Chef cookbook metadata.rb file."""
        try:
            content = metadata_file.read_text(encoding='utf-8')

            # Extract cookbook information using regex
            name_match = re.search(r"^name\s+['\"]([^'\"]+)['\"]\s*$", content, re.MULTILINE)
            version_match = re.search(r"^version\s+['\"]([^'\"]+)['\"]\s*$", content, re.MULTILINE)
            license_match = re.search(r"^license\s+['\"]([^'\"]+)['\"]\s*$", content, re.MULTILINE)
            maintainer_match = re.search(r"^maintainer\s+['\"]([^'\"]+)['\"]\s*$", content, re.MULTILINE)
            description_match = re.search(r"^description\s+['\"]([^'\"]+)['\"]\s*$", content, re.MULTILINE)

            if not name_match:
                return None

            name = name_match.group(1)
            version = version_match.group(1) if version_match else "0.0.0"

            # Build metadata
            metadata = {
                'source_file': str(metadata_file),
                'cookbook_dir': str(metadata_file.parent),
                'type': 'chef_cookbook'
            }

            if license_match:
                metadata['license'] = license_match.group(1)
            if maintainer_match:
                metadata['maintainer'] = maintainer_match.group(1)
            if description_match:
                metadata['description'] = description_match.group(1)

            # Extract dependencies
            depends_matches = re.findall(r"^depends\s+['\"]([^'\"]+)['\"](?:,\s*['\"]([^'\"]+)['\"])?\s*$", content, re.MULTILINE)
            if depends_matches:
                metadata['dependencies'] = [dep[0] for dep in depends_matches]

            # For local Chef cookbooks, don't generate PURL as they can't be downloaded
            # Mark them for local processing only
            return DetectorResult(
                detected=True,
                package_type='chef',
                name=name,
                version=version,
                purl=None,  # No PURL for local cookbooks
                metadata=metadata,
                confidence=0.9
            )
        except Exception as e:
            logger.error(f"Error parsing Chef metadata.rb {metadata_file}: {e}")
            return None

    def _parse_chef_metadata_json(self, metadata_file: Path) -> Optional[DetectorResult]:
        """Parse Chef cookbook metadata.json file."""
        try:
            import json

            with open(metadata_file, 'r') as f:
                data = json.load(f)

            name = data.get('name')
            if not name:
                return None

            version = data.get('version', '0.0.0')

            # Build metadata
            metadata = {
                'source_file': str(metadata_file),
                'cookbook_dir': str(metadata_file.parent),
                'type': 'chef_cookbook'
            }

            if 'license' in data:
                metadata['license'] = data['license']
            if 'maintainer' in data:
                metadata['maintainer'] = data['maintainer']
            if 'description' in data:
                metadata['description'] = data['description']
            if 'dependencies' in data:
                metadata['dependencies'] = list(data['dependencies'].keys())

            # For local Chef cookbooks, don't generate PURL as they can't be downloaded
            # Mark them for local processing only
            return DetectorResult(
                detected=True,
                package_type='chef',
                name=name,
                version=version,
                purl=None,  # No PURL for local cookbooks
                metadata=metadata,
                confidence=1.0
            )
        except Exception as e:
            logger.error(f"Error parsing Chef metadata.json {metadata_file}: {e}")
            return None

    def _parse_gemspec(self, gemspec_file: Path) -> Optional[DetectorResult]:
        """Parse Ruby gemspec file."""
        try:
            content = gemspec_file.read_text(encoding='utf-8')

            # Extract gem information using regex
            # Look for Gem::Specification.new block
            name_match = re.search(r"\.name\s*=\s*['\"]([^'\"]+)['\"]\s*$", content, re.MULTILINE)
            version_match = re.search(r"\.version\s*=\s*['\"]([^'\"]+)['\"]\s*$", content, re.MULTILINE)

            # Alternative patterns
            if not name_match:
                name_match = re.search(r"^\s*s\.name\s*=\s*['\"]([^'\"]+)['\"]\s*$", content, re.MULTILINE)
            if not version_match:
                version_match = re.search(r"^\s*s\.version\s*=\s*['\"]([^'\"]+)['\"]\s*$", content, re.MULTILINE)

            if not name_match:
                # Try to get name from filename
                name = gemspec_file.stem
            else:
                name = name_match.group(1)

            version = version_match.group(1) if version_match else "0.0.0"

            # Extract additional metadata
            metadata = {
                'source_file': str(gemspec_file),
                'type': 'ruby_gem'
            }

            # Try to extract other fields
            license_match = re.search(r"\.license\s*=\s*['\"]([^'\"]+)['\"]\s*$", content, re.MULTILINE)
            if license_match:
                metadata['license'] = license_match.group(1)
            else:
                # Try licenses (plural)
                licenses_match = re.search(r"\.licenses\s*=\s*\[([^\]]+)\]", content)
                if licenses_match:
                    licenses = re.findall(r"['\"]([^'\"]+)['\"]" , licenses_match.group(1))
                    metadata['licenses'] = licenses

            homepage_match = re.search(r"\.homepage\s*=\s*['\"]([^'\"]+)['\"]\s*$", content, re.MULTILINE)
            if homepage_match:
                metadata['homepage'] = homepage_match.group(1)

            author_match = re.search(r"\.author\s*=\s*['\"]([^'\"]+)['\"]\s*$", content, re.MULTILINE)
            if author_match:
                metadata['author'] = author_match.group(1)
            else:
                # Try authors (plural)
                authors_match = re.search(r"\.authors\s*=\s*\[([^\]]+)\]", content)
                if authors_match:
                    authors = re.findall(r"['\"]([^'\"]+)['\"]" , authors_match.group(1))
                    metadata['authors'] = authors

            # Build PURL for Ruby gem
            purl = self._build_purl(name, version)

            return DetectorResult(
                detected=True,
                package_type=self.PACKAGE_TYPE,
                name=name,
                version=version,
                purl=purl,
                metadata=metadata,
                confidence=0.8
            )
        except Exception as e:
            logger.error(f"Error parsing gemspec {gemspec_file}: {e}")
            return None

    def _detect_from_gem_archive(self, gem_path: Path) -> Optional[DetectorResult]:
        """Detect Ruby gem from .gem archive."""
        try:
            import tarfile
            import gzip
            import yaml

            # .gem files are tar archives
            with tarfile.open(gem_path, 'r') as tar:
                # Look for metadata.gz
                for member in tar.getmembers():
                    if member.name == 'metadata.gz':
                        metadata_file = tar.extractfile(member)
                        if metadata_file:
                            # Decompress and parse YAML
                            metadata_content = gzip.decompress(metadata_file.read())
                            metadata_yaml = yaml.safe_load(metadata_content)

                            name = metadata_yaml.get('name')
                            version = str(metadata_yaml.get('version', {}).get('version', '0.0.0'))

                            metadata = {
                                'source_archive': str(gem_path),
                                'type': 'ruby_gem'
                            }

                            if 'license' in metadata_yaml:
                                metadata['license'] = metadata_yaml['license']
                            if 'licenses' in metadata_yaml:
                                metadata['licenses'] = metadata_yaml['licenses']
                            if 'homepage' in metadata_yaml:
                                metadata['homepage'] = metadata_yaml['homepage']
                            if 'authors' in metadata_yaml:
                                metadata['authors'] = metadata_yaml['authors']

                            purl = self._build_purl(name, version)

                            return DetectorResult(
                                detected=True,
                                package_type=self.PACKAGE_TYPE,
                                name=name,
                                version=version,
                                purl=purl,
                                metadata=metadata,
                                confidence=1.0
                            )

            # If no metadata.gz found, try to infer from filename
            name = gem_path.stem
            # Try to extract version from filename (e.g., package-1.2.3.gem)
            version_match = re.search(r'-([\d\.]+)$', name)
            if version_match:
                version = version_match.group(1)
                name = name[:version_match.start()]
            else:
                version = '0.0.0'

            return DetectorResult(
                detected=True,
                package_type=self.PACKAGE_TYPE,
                name=name,
                version=version,
                purl=self._build_purl(name, version),
                metadata={'source_archive': str(gem_path), 'type': 'ruby_gem'},
                confidence=0.5
            )
        except Exception as e:
            logger.error(f"Error detecting from gem archive {gem_path}: {e}")
            return None

    def _build_chef_purl(self, name: str, version: str) -> str:
        """Build PURL for Chef cookbook."""
        # Using 'chef' as package type for Chef cookbooks
        # This follows the PURL spec for Chef Supermarket
        from packageurl import PackageURL

        return PackageURL(
            type='chef',
            name=name,
            version=version
        ).to_string()