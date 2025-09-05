"""Core processing logic for purl2notices."""

import asyncio
import aiohttp
import json
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

from packageurl import PackageURL
from semantic_copycat_purl2src import purl2src
from semantic_copycat_upmex import upmex
from semantic_copycat_oslili import oslili

from .models import Package, License, Copyright, ProcessingStatus
from .config import Config
from .validators import PurlValidator, FileValidator
from .scanner import PackageScanner
from .cache import CacheManager
from .formatter import NoticeFormatter


class Purl2Notices:
    """Main processor for generating legal notices."""
    
    def __init__(self, config: Optional[Config] = None):
        """Initialize processor."""
        self.config = config or Config()
        self.scanner = PackageScanner(self.config)
        self.cache_manager = None
        self.formatter = NoticeFormatter()
        self.error_log = []
    
    async def process_single_purl(self, purl_string: str) -> Package:
        """Process a single PURL."""
        # Validate PURL
        is_valid, error, parsed_purl = PurlValidator.validate(purl_string)
        if not is_valid:
            package = Package(purl=purl_string, status=ProcessingStatus.FAILED)
            package.error_message = f"Invalid PURL: {error}"
            self.error_log.append(f"PURL validation failed: {purl_string} - {error}")
            return package
        
        # Create package object
        package = Package(
            purl=purl_string,
            name=parsed_purl.name,
            version=parsed_purl.version or "",
            type=parsed_purl.type,
            namespace=parsed_purl.namespace
        )
        
        try:
            # Get download URL using purl2src
            download_url = await self._get_download_url(purl_string)
            if not download_url:
                package.status = ProcessingStatus.UNAVAILABLE
                package.error_message = "Could not resolve download URL"
                self.error_log.append(f"No download URL for: {purl_string}")
                return package
            
            # Download package
            package_path = await self._download_package(download_url, parsed_purl)
            if not package_path:
                package.status = ProcessingStatus.UNAVAILABLE
                package.error_message = "Could not download package"
                self.error_log.append(f"Download failed for: {purl_string}")
                return package
            
            # Extract metadata using upmex
            metadata = await self._extract_metadata_upmex(package_path)
            
            # Extract additional info using oslili
            oslili_data = await self._extract_metadata_oslili(package_path)
            
            # Combine results
            package = self._combine_metadata(package, metadata, oslili_data)
            
            # Clean up downloaded file
            if package_path.exists():
                package_path.unlink()
            
        except Exception as e:
            package.status = ProcessingStatus.FAILED
            package.error_message = str(e)
            self.error_log.append(f"Processing error for {purl_string}: {e}")
        
        return package
    
    async def process_batch(self, purl_list: List[str], parallel: int = 4) -> List[Package]:
        """Process multiple PURLs in parallel."""
        packages = []
        
        # Use semaphore to limit parallelism
        semaphore = asyncio.Semaphore(parallel)
        
        async def process_with_limit(purl):
            async with semaphore:
                return await self.process_single_purl(purl)
        
        # Process all PURLs
        tasks = [process_with_limit(purl) for purl in purl_list]
        
        # Use tqdm for progress
        with tqdm(total=len(tasks), desc="Processing PURLs") as pbar:
            for coro in asyncio.as_completed(tasks):
                package = await coro
                packages.append(package)
                pbar.update(1)
        
        return packages
    
    def process_directory(self, directory: Path) -> List[Package]:
        """Process a directory by scanning for packages."""
        # Scan directory
        identified_packages, unidentified_paths = self.scanner.scan_directory(
            directory,
            recursive=self.config.get("scanning.recursive", True),
            max_depth=self.config.get("scanning.max_depth", 10),
            exclude_patterns=self.config.get("scanning.exclude_patterns", [])
        )
        
        packages = []
        
        # Process identified packages (those with PURLs)
        if identified_packages:
            # Convert to PURLs and process
            purl_list = [pkg.purl for pkg in identified_packages if pkg.purl]
            if purl_list:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                processed = loop.run_until_complete(self.process_batch(purl_list))
                packages.extend(processed)
                loop.close()
            
            # Add packages without PURLs
            for pkg in identified_packages:
                if not pkg.purl:
                    packages.append(pkg)
        
        # Process unidentified paths with OSLILI only
        for path in unidentified_paths:
            package = self._process_with_oslili_only(path)
            if package:
                packages.append(package)
        
        return packages
    
    def process_cache(self, cache_file: Path) -> List[Package]:
        """Load packages from cache file."""
        cache_manager = CacheManager(cache_file)
        return cache_manager.load()
    
    def generate_notices(
        self,
        packages: List[Package],
        output_format: str = "text",
        template_path: Optional[Path] = None,
        group_by_license: bool = True,
        include_copyright: bool = True,
        include_license_text: bool = True
    ) -> str:
        """Generate legal notices from packages."""
        # Load SPDX license texts if needed
        license_texts = {}
        if include_license_text:
            license_texts = self._load_license_texts(packages)
        
        # Format output
        formatter = NoticeFormatter(template_path)
        return formatter.format(
            packages=packages,
            format_type=output_format,
            group_by_license=group_by_license,
            include_copyright=include_copyright,
            include_license_text=include_license_text,
            license_texts=license_texts
        )
    
    async def _get_download_url(self, purl_string: str) -> Optional[str]:
        """Get download URL for a PURL using purl2src."""
        try:
            result = purl2src.get_download_url(purl_string)
            return result.get("url") if result else None
        except Exception as e:
            self.error_log.append(f"purl2src error for {purl_string}: {e}")
            return None
    
    async def _download_package(self, url: str, parsed_purl: PackageURL) -> Optional[Path]:
        """Download package from URL."""
        try:
            cache_dir = self.config.cache_dir / "downloads"
            cache_dir.mkdir(parents=True, exist_ok=True)
            
            # Create filename from PURL
            filename = f"{parsed_purl.type}_{parsed_purl.name}_{parsed_purl.version or 'latest'}"
            file_path = cache_dir / filename
            
            # Download file
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=self.config.get("general.timeout", 30)) as response:
                    if response.status == 200:
                        content = await response.read()
                        with open(file_path, 'wb') as f:
                            f.write(content)
                        return file_path
            
            return None
        except Exception as e:
            self.error_log.append(f"Download error for {url}: {e}")
            return None
    
    async def _extract_metadata_upmex(self, package_path: Path) -> Dict[str, Any]:
        """Extract metadata using upmex."""
        try:
            return upmex.extract(str(package_path))
        except Exception as e:
            self.error_log.append(f"upmex error for {package_path}: {e}")
            return {}
    
    async def _extract_metadata_oslili(self, package_path: Path) -> Dict[str, Any]:
        """Extract metadata using oslili."""
        try:
            return oslili.extract(str(package_path))
        except Exception as e:
            self.error_log.append(f"oslili error for {package_path}: {e}")
            return {}
    
    def _combine_metadata(
        self,
        package: Package,
        upmex_data: Dict[str, Any],
        oslili_data: Dict[str, Any]
    ) -> Package:
        """Combine metadata from different sources."""
        # Extract licenses
        licenses_seen = set()
        
        # From upmex
        if "licenses" in upmex_data:
            for lic_data in upmex_data["licenses"]:
                spdx_id = lic_data.get("spdx_id", "NOASSERTION")
                if spdx_id not in licenses_seen:
                    package.licenses.append(License(
                        spdx_id=spdx_id,
                        name=lic_data.get("name", spdx_id),
                        text=lic_data.get("text", ""),
                        source="upmex"
                    ))
                    licenses_seen.add(spdx_id)
        
        # From oslili
        if "licenses" in oslili_data:
            for lic_data in oslili_data["licenses"]:
                spdx_id = lic_data.get("spdx_id", "NOASSERTION")
                if spdx_id not in licenses_seen:
                    package.licenses.append(License(
                        spdx_id=spdx_id,
                        name=lic_data.get("name", spdx_id),
                        text=lic_data.get("text", ""),
                        source="oslili"
                    ))
                    licenses_seen.add(spdx_id)
        
        # Extract copyrights
        copyrights_seen = set()
        
        # From upmex
        if "copyrights" in upmex_data:
            for copyright_str in upmex_data["copyrights"]:
                if copyright_str not in copyrights_seen:
                    package.copyrights.append(Copyright(statement=copyright_str))
                    copyrights_seen.add(copyright_str)
        
        # From oslili
        if "copyrights" in oslili_data:
            for copyright_str in oslili_data["copyrights"]:
                if copyright_str not in copyrights_seen:
                    package.copyrights.append(Copyright(statement=copyright_str))
                    copyrights_seen.add(copyright_str)
        
        # Update status
        if not package.licenses:
            package.status = ProcessingStatus.NO_LICENSE
        elif not package.copyrights:
            package.status = ProcessingStatus.NO_COPYRIGHT
        else:
            package.status = ProcessingStatus.SUCCESS
        
        return package
    
    def _process_with_oslili_only(self, path: Path) -> Optional[Package]:
        """Process a path using only OSLILI (for unidentified packages)."""
        try:
            oslili_data = oslili.extract(str(path))
            
            package = Package(
                name=path.name,
                source_path=str(path)
            )
            
            # Extract licenses
            if "licenses" in oslili_data:
                for lic_data in oslili_data["licenses"]:
                    package.licenses.append(License(
                        spdx_id=lic_data.get("spdx_id", "NOASSERTION"),
                        name=lic_data.get("name", "Unknown"),
                        text=lic_data.get("text", ""),
                        source="oslili"
                    ))
            
            # Extract copyrights
            if "copyrights" in oslili_data:
                for copyright_str in oslili_data["copyrights"]:
                    package.copyrights.append(Copyright(statement=copyright_str))
            
            # Update status
            if not package.licenses:
                package.status = ProcessingStatus.NO_LICENSE
            elif not package.copyrights:
                package.status = ProcessingStatus.NO_COPYRIGHT
            else:
                package.status = ProcessingStatus.SUCCESS
            
            return package
            
        except Exception as e:
            self.error_log.append(f"OSLILI processing error for {path}: {e}")
            return None
    
    def _load_license_texts(self, packages: List[Package]) -> Dict[str, str]:
        """Load SPDX license texts."""
        license_texts = {}
        spdx_dir = Path(__file__).parent / "data" / "licenses"
        
        # Collect needed licenses
        needed_licenses = set()
        for package in packages:
            for license in package.licenses:
                if license.spdx_id and license.spdx_id != "NOASSERTION":
                    needed_licenses.add(license.spdx_id)
        
        # Load license texts
        for spdx_id in needed_licenses:
            license_file = spdx_dir / f"{spdx_id}.txt"
            if license_file.exists():
                with open(license_file, 'r') as f:
                    license_texts[spdx_id] = f.read()
            else:
                # Try to get from packages themselves
                for package in packages:
                    for license in package.licenses:
                        if license.spdx_id == spdx_id and license.text:
                            license_texts[spdx_id] = license.text
                            break
        
        return license_texts