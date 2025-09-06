"""Core processing logic for purl2notices."""

import asyncio
import logging
from pathlib import Path
from typing import List, Optional, Dict

from tqdm import tqdm

from .models import Package, License, Copyright, ProcessingStatus
from .config import Config
from .validators import PurlValidator
from .cache import CacheManager
from .formatter import NoticeFormatter
from .detectors import DetectorRegistry, DetectorResult
from .extractors import CombinedExtractor, ExtractionResult


logger = logging.getLogger(__name__)


class Purl2Notices:
    """Main processor for generating legal notices from package URLs."""
    
    def __init__(self, config: Optional[Config] = None):
        """Initialize processor."""
        self.config = config or Config()
        
        # Initialize components
        self.detector_registry = DetectorRegistry()
        self.extractor = CombinedExtractor(
            cache_dir=self.config.cache_dir / "downloads"
        )
        self.cache_manager = None
        self.formatter = NoticeFormatter()
        self.error_log = []
        
        # Set up logging
        self._setup_logging()
    
    def _setup_logging(self):
        """Set up logging configuration."""
        log_level = logging.WARNING
        verbose = self.config.get("general.verbose", 0)
        
        if verbose == 1:
            log_level = logging.INFO
        elif verbose >= 2:
            log_level = logging.DEBUG
        
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    
    async def process_single_purl(self, purl_string: str) -> Package:
        """Process a single PURL."""
        logger.info(f"Processing PURL: {purl_string}")
        
        # Validate PURL
        is_valid, error, parsed_purl = PurlValidator.validate(purl_string)
        if not is_valid:
            package = Package(purl=purl_string, status=ProcessingStatus.FAILED)
            package.error_message = f"Invalid PURL: {error}"
            self.error_log.append(f"PURL validation failed: {purl_string} - {error}")
            return package
        
        # Create initial package
        package = Package(
            purl=purl_string,
            name=parsed_purl.name,
            version=parsed_purl.version or "",
            type=parsed_purl.type,
            namespace=parsed_purl.namespace
        )
        
        try:
            # Extract information using combined extractor
            extraction_result = await self.extractor.extract_from_purl(purl_string)
            
            if not extraction_result.success:
                package.status = ProcessingStatus.UNAVAILABLE
                package.error_message = "; ".join(extraction_result.errors)
                self.error_log.extend(extraction_result.errors)
                return package
            
            # Convert extraction result to package model
            package = self._extraction_to_package(package, extraction_result)
            
        except Exception as e:
            logger.error(f"Processing error for {purl_string}: {e}")
            package.status = ProcessingStatus.FAILED
            package.error_message = str(e)
            self.error_log.append(f"Processing error for {purl_string}: {e}")
        
        return package
    
    async def process_batch(self, purl_list: List[str], parallel: int = 4) -> List[Package]:
        """Process multiple PURLs in parallel."""
        logger.info(f"Processing batch of {len(purl_list)} PURLs")
        packages = []
        
        # Use semaphore to limit parallelism
        semaphore = asyncio.Semaphore(parallel)
        
        async def process_with_limit(purl):
            async with semaphore:
                return await self.process_single_purl(purl)
        
        # Process all PURLs with progress bar
        tasks = [process_with_limit(purl) for purl in purl_list]
        
        # Use tqdm with asyncio.as_completed
        with tqdm(total=len(tasks), desc="Processing PURLs") as pbar:
            for coro in asyncio.as_completed(tasks):
                result = await coro
                packages.append(result)
                pbar.update(1)
        
        return packages
    
    def process_directory(self, directory: Path) -> List[Package]:
        """Process a directory by scanning for packages."""
        logger.info(f"Scanning directory: {directory}")
        
        # Detect packages in directory
        detection_results = self.detector_registry.detect_from_directory(directory)
        
        packages = []
        purls_to_process = []
        paths_to_process = []
        
        # Separate detected packages by whether they have PURLs
        for detection in detection_results:
            if detection.purl:
                purls_to_process.append(detection.purl)
            else:
                # Create package from detection
                package = self._detection_to_package(detection)
                if detection.metadata.get('source_file'):
                    paths_to_process.append((Path(detection.metadata['source_file']), package))
                else:
                    packages.append(package)
        
        # Process packages with PURLs
        if purls_to_process:
            logger.info(f"Processing {len(purls_to_process)} detected PURLs")
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            parallel = self.config.get("general.parallel_workers", 4)
            processed = loop.run_until_complete(
                self.process_batch(purls_to_process, parallel)
            )
            packages.extend(processed)
            loop.close()
        
        # Process paths without PURLs using extractors
        if paths_to_process:
            logger.info(f"Processing {len(paths_to_process)} local packages")
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            for path, package in paths_to_process:
                extraction = loop.run_until_complete(
                    self.extractor.extract_from_path(path)
                )
                if extraction.success:
                    package = self._extraction_to_package(package, extraction)
                packages.append(package)
            
            loop.close()
        
        # Find and process archive files separately for proper attribution
        # Use the max_depth from config or a reasonable default
        max_depth = self.config.get("scanning.max_depth", 10)
        archive_files = self._find_archive_files(directory, max_depth=max_depth)
        if archive_files:
            logger.info(f"Processing {len(archive_files)} archive files")
            for archive in archive_files:
                logger.debug(f"Found archive: {archive.name} ({archive.suffix})")
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            for archive_path in archive_files:
                # Process each archive as its own package
                extraction = loop.run_until_complete(
                    self.extractor.extract_from_path(archive_path)
                )
                
                # Create package with proper coordinates
                package = Package(
                    name=archive_path.stem,
                    source_path=str(archive_path),
                    type='archive'
                )
                
                # Try to determine package type from file extension
                if archive_path.suffix in ['.jar', '.war', '.ear', '.aar']:
                    package.type = 'maven'
                elif archive_path.suffix in ['.whl', '.egg']:
                    package.type = 'pypi'
                elif archive_path.suffix == '.gem':
                    package.type = 'gem'
                elif archive_path.suffix == '.nupkg':
                    package.type = 'nuget'
                
                if extraction.success:
                    package = self._extraction_to_package(package, extraction)
                else:
                    package.status = ProcessingStatus.FAILED
                    package.error_message = f"Failed to extract from {archive_path.name}"
                
                packages.append(package)
            
            loop.close()
        
        # Scan remaining source code (excluding archives already processed)
        logger.info("Scanning directory for source code")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Configure oslili to skip archives since we processed them separately
        extraction = loop.run_until_complete(
            self._extract_source_code_only(directory, skip_archives=True)
        )
        
        if extraction.success and (extraction.licenses or extraction.copyrights):
            # Create a package for the source code
            package = Package(
                name=f"{directory.name}_sources",
                source_path=str(directory)
            )
            package = self._extraction_to_package(package, extraction)
            packages.append(package)
        
        loop.close()
        
        return packages
    
    def process_cache(self, cache_file: Path, override_file: Optional[Path] = None) -> List[Package]:
        """Load packages from cache file."""
        logger.info(f"Loading from cache: {cache_file}")
        override_file = override_file or Path("purl2notices.overrides.json")
        cache_manager = CacheManager(cache_file, override_file)
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
        logger.info(f"Generating {output_format} notices for {len(packages)} packages")
        
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
    
    def _detection_to_package(self, detection: DetectorResult) -> Package:
        """Convert DetectorResult to Package."""
        package = Package(
            purl=detection.purl,
            name=detection.name or "",
            version=detection.version or "",
            type=detection.package_type,
            namespace=detection.namespace
        )
        
        # Add metadata
        if detection.metadata:
            package.metadata = detection.metadata
            if 'source_file' in detection.metadata:
                package.source_path = detection.metadata['source_file']
            elif 'source_archive' in detection.metadata:
                package.source_path = detection.metadata['source_archive']
        
        return package
    
    def _extraction_to_package(self, package: Package, extraction: ExtractionResult) -> Package:
        """Update package with extraction results."""
        # Add licenses
        for license_info in extraction.licenses:
            # Try to load license text from SPDX if not provided
            license_text = license_info.text or ""
            if not license_text and license_info.spdx_id and license_info.spdx_id != "NOASSERTION":
                spdx_file = Path(__file__).parent / "data" / "licenses" / f"{license_info.spdx_id}.txt"
                if spdx_file.exists():
                    try:
                        license_text = spdx_file.read_text(encoding='utf-8')
                    except Exception:
                        pass
            
            license_obj = License(
                spdx_id=license_info.spdx_id,
                name=license_info.name,
                text=license_text,
                source=str(license_info.source.value) if license_info.source else "unknown"
            )
            package.licenses.append(license_obj)
        
        # Add copyrights
        for copyright_info in extraction.copyrights:
            copyright_obj = Copyright(
                statement=copyright_info.statement,
                year_start=copyright_info.year_start,
                year_end=copyright_info.year_end,
                holders=copyright_info.holders
            )
            package.copyrights.append(copyright_obj)
        
        # Update metadata
        if extraction.metadata:
            package.metadata.update(extraction.metadata)
        
        # Update status
        if not package.licenses:
            package.status = ProcessingStatus.NO_LICENSE
        elif not package.copyrights:
            package.status = ProcessingStatus.NO_COPYRIGHT
        else:
            package.status = ProcessingStatus.SUCCESS
        
        return package
    
    def _load_license_texts(self, packages: List[Package]) -> Dict[str, str]:
        """Load SPDX license texts."""
        license_texts = {}
        spdx_dir = Path(__file__).parent / "data" / "licenses"
        
        # Collect needed licenses
        needed_licenses = set()
        for package in packages:
            for license_obj in package.licenses:
                if license_obj.spdx_id and license_obj.spdx_id != "NOASSERTION":
                    needed_licenses.add(license_obj.spdx_id)
        
        # Load license texts
        for spdx_id in needed_licenses:
            # First check if any package already has the text
            for package in packages:
                for license_obj in package.licenses:
                    if license_obj.spdx_id == spdx_id and license_obj.text:
                        license_texts[spdx_id] = license_obj.text
                        break
                if spdx_id in license_texts:
                    break
            
            # If not found, try to load from bundled licenses
            if spdx_id not in license_texts:
                license_file = spdx_dir / f"{spdx_id}.txt"
                if license_file.exists():
                    try:
                        with open(license_file, 'r', encoding='utf-8') as f:
                            license_texts[spdx_id] = f.read()
                    except Exception as e:
                        logger.error(f"Failed to load license text for {spdx_id}: {e}")
        
        return license_texts
    
    def _find_archive_files(self, directory: Path, max_depth: int = 3) -> List[Path]:
        """Find all archive files in a directory recursively."""
        from .constants import ARCHIVE_EXTENSIONS
        archive_extensions = ARCHIVE_EXTENSIONS
        
        archive_files = []
        
        def scan_dir(path: Path, current_depth: int = 0):
            if current_depth >= max_depth:
                return
            
            try:
                for item in path.iterdir():
                    if item.is_file():
                        for ext in archive_extensions:
                            if item.name.endswith(ext):
                                archive_files.append(item)
                                break
                    elif item.is_dir():
                        # Include all directories, even hidden ones
                        scan_dir(item, current_depth + 1)
            except PermissionError:
                logger.debug(f"Permission denied accessing: {path}")
        
        scan_dir(directory)
        return archive_files
    
    async def _extract_source_code_only(self, directory: Path, skip_archives: bool = True) -> ExtractionResult:
        """Extract licenses from source code only, optionally skipping archives."""
        try:
            # For now, we'll use oslili but in the future we could configure it
            # to skip archives. Since oslili doesn't have that option yet,
            # we'll process everything and rely on the fact that we already
            # processed archives separately
            result = await self.extractor.oslili.extract_from_path(directory)
            
            # Note: In a production system, we might want to filter out
            # licenses that we know came from archives we already processed
            # This would require oslili to provide source file information
            # for each license detected
            
            return result
        except Exception as e:
            logger.error(f"Error extracting from source code: {e}")
            return ExtractionResult(
                success=False,
                errors=[str(e)]
            )