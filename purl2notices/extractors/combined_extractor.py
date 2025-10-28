"""Combined extractor that uses multiple sources."""

import logging
import tempfile
from pathlib import Path
from typing import Optional, List
import aiohttp
import aiofiles

from .base import (
    BaseExtractor, ExtractionResult, ExtractionSource,
    LicenseInfo, CopyrightInfo
)
from .purl2src_extractor import Purl2SrcExtractor
from .upmex_extractor import UpmexExtractor
from .osslili_extractor import OssliliExtractor


logger = logging.getLogger(__name__)


class CombinedExtractor(BaseExtractor):
    """
    Combined extractor that uses purl2src, upmex, and osslili.
    
    Workflow:
    1. Use purl2src to get download URL
    2. Download the package
    3. Use upmex to extract metadata
    4. Use osslili for additional extraction
    5. Combine results
    """
    
    def __init__(self, cache_dir: Optional[Path] = None):
        """Initialize combined extractor."""
        super().__init__()
        self.purl2src = Purl2SrcExtractor()
        self.upmex = UpmexExtractor()
        self.osslili = OssliliExtractor()
        
        # Set up cache directory for downloads
        if cache_dir:
            self.cache_dir = cache_dir
        else:
            self.cache_dir = Path(tempfile.gettempdir()) / "purl2notices_cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    async def extract_from_purl(self, purl: str) -> ExtractionResult:
        """Extract information from a PURL using all available sources."""
        # Normalize PURL - remove trailing slashes
        purl = purl.rstrip('/')
        
        errors = []
        all_licenses = []
        all_copyrights = []
        metadata = {}
        
        try:
            from packageurl import PackageURL
            parsed_purl = PackageURL.from_string(purl)
            
            # Special handling for generic packages with vcs_url - bypass purl2src
            download_url = None
            if parsed_purl.type == 'generic' and 'vcs_url' in parsed_purl.qualifiers:
                vcs_url = parsed_purl.qualifiers['vcs_url']
                # Parse git+https://... format
                if vcs_url.startswith('git+'):
                    vcs_url = vcs_url[4:]  # Remove 'git+' prefix
                
                # Extract commit/tag from URL if present
                if '@' in vcs_url:
                    base_url, ref = vcs_url.rsplit('@', 1)
                    # Try to convert to archive URL if it's a GitHub/GitLab URL
                    if 'github.com' in base_url:
                        # Extract owner/repo from URL
                        parts = base_url.replace('https://github.com/', '').replace('.git', '').split('/')
                        if len(parts) >= 2:
                            download_url = f"https://github.com/{parts[0]}/{parts[1]}/archive/{ref}.tar.gz"
                            logger.debug(f"Converted generic GitHub VCS URL to archive: {download_url}")
                    elif 'gitlab' in base_url or 'git.fsfe.org' in base_url:
                        # For GitLab-style repos, construct archive URL
                        base_url = base_url.replace('.git', '')
                        download_url = f"{base_url}/-/archive/{ref}/archive.tar.gz"
                        logger.debug(f"Converted generic GitLab VCS URL to archive: {download_url}")
                else:
                    # No ref specified, just use the URL as-is
                    download_url = vcs_url
            
            # If we didn't handle it specially, use purl2src
            if not download_url:
                # Step 1: Get download URL using purl2src
                logger.debug(f"Getting download URL for {purl}")
                purl2src_result = await self.purl2src.extract_from_purl(purl)
                
                if not purl2src_result.success:
                    errors.extend(purl2src_result.errors)
                    return ExtractionResult(
                        success=False,
                        errors=errors,
                        source=ExtractionSource.PURL2SRC
                    )
                
                download_url = purl2src_result.metadata.get('download_url')
                if not download_url:
                    return ExtractionResult(
                        success=False,
                        errors=["No download URL found"],
                        source=ExtractionSource.PURL2SRC
                    )
                
                metadata.update(purl2src_result.metadata)
            
            # Additional handling for GitHub packages that returned git URLs
            if parsed_purl.type == 'github' and download_url.endswith('.git'):
                # Convert to tarball URL: https://github.com/{namespace}/{name}/archive/{version}.tar.gz
                if parsed_purl.version:
                    download_url = f"https://github.com/{parsed_purl.namespace}/{parsed_purl.name}/archive/{parsed_purl.version}.tar.gz"
                    logger.debug(f"Converted GitHub URL to archive: {download_url}")
                else:
                    # Default to main branch if no version
                    download_url = f"https://github.com/{parsed_purl.namespace}/{parsed_purl.name}/archive/main.tar.gz"
            
            # Step 2: Download the package
            logger.debug(f"Downloading package from {download_url}")
            package_path = await self._download_package(download_url, purl)
            
            if not package_path:
                return ExtractionResult(
                    success=False,
                    errors=["Failed to download package"],
                    metadata=metadata
                )
            
            # Step 3: Extract using upmex
            logger.debug(f"Extracting metadata with upmex from {package_path}")
            upmex_result = await self.upmex.extract_from_path(package_path)
            
            if upmex_result.success:
                all_licenses.extend(upmex_result.licenses)
                all_copyrights.extend(upmex_result.copyrights)
                metadata.update(upmex_result.metadata)
            else:
                errors.extend(upmex_result.errors)
            
            # Step 4: Extract using osslili
            logger.debug(f"Extracting with osslili from {package_path}")
            osslili_result = await self.osslili.extract_from_path(package_path)

            if osslili_result.success:
                all_licenses.extend(osslili_result.licenses)
                all_copyrights.extend(osslili_result.copyrights)
                metadata.update(osslili_result.metadata)
            else:
                errors.extend(osslili_result.errors)
            
            # Step 5: Combine and deduplicate results
            combined_licenses = self._combine_licenses(all_licenses)
            combined_copyrights = self._combine_copyrights(all_copyrights)
            
            # Clean up downloaded file if it's in temp directory
            if package_path.parent == self.cache_dir and package_path.exists():
                try:
                    package_path.unlink()
                except Exception:
                    pass
            
            return ExtractionResult(
                success=True,
                licenses=combined_licenses,
                copyrights=combined_copyrights,
                metadata=metadata,
                errors=errors if errors else None
            )
            
        except Exception as e:
            logger.error(f"Error in combined extraction: {e}")
            return ExtractionResult(
                success=False,
                errors=[str(e)],
                metadata=metadata
            )
    
    async def extract_from_path(self, path: Path) -> ExtractionResult:
        """Extract information from a local path using upmex and osslili."""
        errors = []
        all_licenses = []
        all_copyrights = []
        metadata = {}
        
        try:
            # Use upmex for packages
            if path.is_file() and self._is_package_file(path):
                logger.debug(f"Extracting metadata with upmex from {path}")
                upmex_result = await self.upmex.extract_from_path(path)
                
                if upmex_result.success:
                    all_licenses.extend(upmex_result.licenses)
                    all_copyrights.extend(upmex_result.copyrights)
                    metadata.update(upmex_result.metadata)
                else:
                    errors.extend(upmex_result.errors)
            
            # Always use osslili for additional extraction
            logger.debug(f"Extracting with osslili from {path}")
            osslili_result = await self.osslili.extract_from_path(path)

            if osslili_result.success:
                all_licenses.extend(osslili_result.licenses)
                all_copyrights.extend(osslili_result.copyrights)

                # Merge osslili metadata, but preserve upmex package identification fields
                if osslili_result.metadata:
                    # Save package fields from upmex (if any)
                    upmex_package_fields = {
                        key: metadata[key] for key in ['package_name', 'package_version', 'package_purl', 'package_type']
                        if key in metadata and metadata[key]
                    }

                    # Update with osslili metadata
                    metadata.update(osslili_result.metadata)

                    # Restore upmex package fields (they take precedence)
                    metadata.update(upmex_package_fields)
            else:
                errors.extend(osslili_result.errors)
            
            # Combine results
            combined_licenses = self._combine_licenses(all_licenses)
            combined_copyrights = self._combine_copyrights(all_copyrights)
            
            return ExtractionResult(
                success=bool(combined_licenses or combined_copyrights),
                licenses=combined_licenses,
                copyrights=combined_copyrights,
                metadata=metadata,
                errors=errors if errors else None
            )
            
        except Exception as e:
            logger.error(f"Error in combined extraction from path: {e}")
            return ExtractionResult(
                success=False,
                errors=[str(e)],
                metadata=metadata
            )
    
    async def _download_package(self, url: str, purl: str) -> Optional[Path]:
        """Download a package from URL."""
        try:
            # Create filename from PURL
            from packageurl import PackageURL
            parsed = PackageURL.from_string(purl)
            
            # Determine extension from URL
            extension = '.tar.gz'
            if '.whl' in url:
                extension = '.whl'
            elif '.jar' in url:
                extension = '.jar'
            elif '.gem' in url:
                extension = '.gem'
            elif '.zip' in url:
                extension = '.zip'
            elif '.nupkg' in url.lower():
                extension = '.nupkg'
            elif '.tar.bz2' in url:
                extension = '.tar.bz2'
            elif parsed.type == 'nuget':
                extension = '.nupkg'
            elif parsed.type == 'conda':
                extension = '.tar.bz2'
            
            filename = f"{parsed.type}_{parsed.name}_{parsed.version or 'latest'}{extension}"
            file_path = self.cache_dir / filename
            
            # Check if already cached
            if file_path.exists():
                logger.debug(f"Using cached file: {file_path}")
                return file_path
            
            # Download file
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=60)) as response:
                    if response.status == 200:
                        async with aiofiles.open(file_path, 'wb') as f:
                            content = await response.read()
                            await f.write(content)
                        logger.debug(f"Downloaded to: {file_path}")
                        return file_path
                    else:
                        logger.error(f"Download failed with status {response.status}")
                        return None
                        
        except Exception as e:
            logger.error(f"Download error: {e}")
            return None
    
    def _is_package_file(self, path: Path) -> bool:
        """Check if file is a package archive."""
        from ..constants import ARCHIVE_EXTENSIONS
        
        for ext in ARCHIVE_EXTENSIONS:
            if path.name.endswith(ext):
                return True
        return False
    
    def _combine_licenses(self, licenses: List[LicenseInfo]) -> List[LicenseInfo]:
        """Combine licenses from multiple sources, preferring higher confidence."""
        combined = {}
        
        for license_info in licenses:
            key = (license_info.spdx_id, license_info.name)
            
            if key not in combined:
                combined[key] = license_info
            else:
                # Keep the one with higher confidence or more complete info
                existing = combined[key]
                if (license_info.confidence > existing.confidence or
                    (license_info.text and not existing.text)):
                    combined[key] = license_info
                elif license_info.text and existing.text:
                    # Merge text if different
                    if len(license_info.text) > len(existing.text):
                        existing.text = license_info.text
        
        return list(combined.values())
    
    def _combine_copyrights(self, copyrights: List[CopyrightInfo]) -> List[CopyrightInfo]:
        """Combine copyrights from multiple sources, removing duplicates."""
        seen_statements = set()
        combined = []
        
        for copyright_info in copyrights:
            # Normalize statement for comparison
            normalized = copyright_info.statement.strip().lower()
            
            if normalized not in seen_statements:
                seen_statements.add(normalized)
                combined.append(copyright_info)
        
        return combined