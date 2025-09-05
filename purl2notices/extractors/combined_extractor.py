"""Combined extractor that uses multiple sources."""

import asyncio
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
from .oslili_extractor import OsliliExtractor


logger = logging.getLogger(__name__)


class CombinedExtractor(BaseExtractor):
    """
    Combined extractor that uses purl2src, upmex, and oslili.
    
    Workflow:
    1. Use purl2src to get download URL
    2. Download the package
    3. Use upmex to extract metadata
    4. Use oslili for additional extraction
    5. Combine results
    """
    
    def __init__(self, cache_dir: Optional[Path] = None):
        """Initialize combined extractor."""
        super().__init__()
        self.purl2src = Purl2SrcExtractor()
        self.upmex = UpmexExtractor()
        self.oslili = OsliliExtractor()
        
        # Set up cache directory for downloads
        if cache_dir:
            self.cache_dir = cache_dir
        else:
            self.cache_dir = Path(tempfile.gettempdir()) / "purl2notices_cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    async def extract_from_purl(self, purl: str) -> ExtractionResult:
        """Extract information from a PURL using all available sources."""
        errors = []
        all_licenses = []
        all_copyrights = []
        metadata = {}
        
        try:
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
            
            # Step 4: Extract using oslili
            logger.debug(f"Extracting with oslili from {package_path}")
            oslili_result = await self.oslili.extract_from_path(package_path)
            
            if oslili_result.success:
                all_licenses.extend(oslili_result.licenses)
                all_copyrights.extend(oslili_result.copyrights)
                metadata.update(oslili_result.metadata)
            else:
                errors.extend(oslili_result.errors)
            
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
        """Extract information from a local path using upmex and oslili."""
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
            
            # Always use oslili for additional extraction
            logger.debug(f"Extracting with oslili from {path}")
            oslili_result = await self.oslili.extract_from_path(path)
            
            if oslili_result.success:
                all_licenses.extend(oslili_result.licenses)
                all_copyrights.extend(oslili_result.copyrights)
                metadata.update(oslili_result.metadata)
            else:
                errors.extend(oslili_result.errors)
            
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
        package_extensions = [
            '.whl', '.egg', '.tar.gz', '.tgz', '.zip',
            '.jar', '.war', '.ear', '.gem', '.nupkg',
            '.deb', '.rpm', '.crate'
        ]
        
        for ext in package_extensions:
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