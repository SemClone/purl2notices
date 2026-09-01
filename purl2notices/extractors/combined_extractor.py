"""Combined extractor that uses multiple sources."""

import logging
import tempfile
from pathlib import Path
from typing import Optional, List
from urllib.parse import urlparse, urlunparse
import aiohttp
import aiofiles

from .base import (
    BaseExtractor, ExtractionResult, ExtractionSource,
    LicenseInfo, CopyrightInfo,
    CATEGORY_DECLARED, MATCH_LICENSE_FILE, MATCH_TEXT_SIMILARITY,
    evidence_rank, is_third_party, is_carried, _dedupe_key
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
                    # Parse URL properly to avoid substring matching vulnerabilities
                    parsed_url = urlparse(base_url)

                    # Check hostname explicitly to prevent URL substring attacks
                    if parsed_url.hostname == 'github.com' and parsed_url.scheme == 'https':
                        # Extract owner/repo from path
                        path_parts = parsed_url.path.strip('/').replace('.git', '').split('/')
                        if len(path_parts) >= 2:
                            # Sanitize owner and repo names
                            owner = path_parts[0]
                            repo = path_parts[1]
                            download_url = f"https://github.com/{owner}/{repo}/archive/{ref}.tar.gz"
                            logger.debug(f"Converted generic GitHub VCS URL to archive: {download_url}")
                    elif parsed_url.hostname in ['gitlab.com', 'git.fsfe.org'] or (
                        parsed_url.hostname and 'gitlab' in parsed_url.hostname.split('.')
                    ):
                        # For GitLab-style repos, construct archive URL
                        # Reconstruct URL without .git extension
                        path = parsed_url.path.replace('.git', '')
                        base_url = urlunparse((
                            parsed_url.scheme,
                            parsed_url.netloc,
                            path,
                            parsed_url.params,
                            parsed_url.query,
                            parsed_url.fragment
                        ))
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

            # Determine extension from URL using proper parsing
            url_lower = url.lower()
            extension = '.tar.gz'

            # Parse URL path to get filename
            url_path = urlparse(url).path
            filename = url_path.split('/')[-1] if url_path else ''
            filename_lower = filename.lower()

            # Check file extension from the actual filename
            if filename_lower.endswith('.whl'):
                extension = '.whl'
            elif filename_lower.endswith('.jar'):
                extension = '.jar'
            elif filename_lower.endswith('.gem'):
                extension = '.gem'
            elif filename_lower.endswith('.zip'):
                extension = '.zip'
            elif filename_lower.endswith('.nupkg'):
                extension = '.nupkg'
            elif filename_lower.endswith('.tar.bz2'):
                extension = '.tar.bz2'
            elif filename_lower.endswith('.tar.gz'):
                extension = '.tar.gz'
            elif filename_lower.endswith('.tgz'):
                extension = '.tgz'
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
    
    def _stated_licenses(self, licenses: List[LicenseInfo]) -> List[LicenseInfo]:
        """Narrow a scan's detections to the licenses the package actually has.

        Two different things get reported as licenses. A package *states* its
        license, in metadata or a license file. A scan also *recognises* license
        wording anywhere it appears, and prose that names a license reads much
        like the license itself: express's changelog matches the JSON license at
        0.85, and urllib3 and cryptography have the same shape in their changelog
        and docs. Treated as equals, those become declared licenses, and we tell
        a customer their express dependency carries the JSON license, whose
        "Good, not Evil" clause most policies forbid.

        So take the strongest kind of evidence present and stop there, rather
        than filtering on a confidence number. A keyword hit on a changelog is
        not weak evidence that the package is JSON-licensed; it is evidence of
        something else, and no threshold separates those. urllib3 shows why the
        number cannot be trusted on its own: its phantom JSON arrives from one
        detector at 0.85 and from another at 0.983 labelled exact.

        The tiers come from the detector's own classification rather than being
        re-derived here. That is a deliberate limit: a detector that files a
        changelog hit under "declared" defeats this, which is what numpy's
        vendored tree does today, so this narrows what a scan reports without
        claiming to be a second opinion on it.

        A claim also has to be checkable. Detections that name the file they came
        from can be ranked this way; detections that do not cannot be. Those are
        kept only where a traceable declaration agrees, which is what removes the
        JSON from urllib3, the BSD-4-Clause from click and the BSD-3-Clause from
        packaging. When nothing traceable is declared, they are kept regardless,
        because then no traceable detection read the package's own metadata and
        an unsourced one may be the only thing that did.

        Licenses the package carries rather than claims are never ranked against
        its own and are never dropped: a third-party notice, and a whole license
        text found in a file not named like a license file. typescript declares
        Apache-2.0 and ships a ThirdPartyNoticeText.txt carrying MIT and
        CC-BY-4.0 for code compiled into typescript.js; that code has no PURL of
        its own, so if this omits it nothing will attribute it. Overstating a
        license and omitting one are both wrong, and only the first is fixed by
        narrowing.

        Dual licensing survives all of this: cryptography and packaging each
        declare two licenses in their own metadata, and both are kept.
        """
        if not licenses:
            return []

        # Set aside everything that is present in the package rather than
        # claimed by it. Neither kind competes with the package's own license,
        # and neither is dropped for losing that competition.
        carried = [lic for lic in licenses if self._is_carried(lic)]
        own = [lic for lic in licenses if not self._is_carried(lic)]
        if not own:
            return carried

        traceable = [lic for lic in own if lic.source_file]
        untraceable = [lic for lic in own if not lic.source_file]

        if not traceable:
            # Nothing can be ranked. Reporting what we have beats reporting
            # nothing, and there is no basis here for dropping any of it.
            return own + carried

        selected = self._strongest_evidence(traceable)

        if not any(lic.category == CATEGORY_DECLARED for lic in traceable):
            return selected + untraceable + carried

        supported = {lic.spdx_id for lic in selected}
        kept = [lic for lic in untraceable if lic.spdx_id in supported]
        return selected + kept + carried

    @staticmethod
    def _is_carried(license_info: LicenseInfo) -> bool:
        """Whether this license is present in the package rather than claimed.

        Two kinds. A third-party notice names the license of code the package
        bundles. A whole license text matching inside a file not named like a
        license file, which is how a vendored source carrying a complete
        license reads, is that license's text genuinely shipping.

        Both are omissions if dropped, and an omission in an attribution file
        is worse than the overclaim this narrowing exists to fix. Neither is
        ranked against what the package declares about itself.
        """
        if is_third_party(license_info):
            return True
        return (
            license_info.category != CATEGORY_DECLARED
            and license_info.match_type == MATCH_TEXT_SIMILARITY
        )

    def _strongest_evidence(self, licenses: List[LicenseInfo]) -> List[LicenseInfo]:
        """Pick the tier of evidence to answer from, strongest first.

        Only the package's own licenses reach here; bundled ones are set aside
        by the caller rather than competing with them.
        """
        declared = [lic for lic in licenses if lic.category == CATEGORY_DECLARED]
        if declared:
            return declared

        # Nothing declared. A license file is still the package speaking about
        # itself, even with no metadata behind it. osslili does not currently
        # emit this combination, which is why nothing below the declared tier
        # fires against it today; the ordering is here so a detector that does
        # emit it ranks the way it should.
        from_license_file = [
            lic for lic in licenses if lic.match_type == MATCH_LICENSE_FILE
        ]
        if from_license_file:
            return from_license_file

        # Only mentions left. Report the single best one rather than every
        # license the package's prose happens to name.
        return [max(licenses, key=lambda lic: lic.confidence)]

    def _combine_licenses(self, licenses: List[LicenseInfo]) -> List[LicenseInfo]:
        """Combine licenses from multiple sources, keeping the best evidenced."""
        licenses = self._stated_licenses(licenses)
        combined = {}

        for license_info in licenses:
            key = _dedupe_key(license_info)
            existing = combined.get(key)

            if existing is None:
                combined[key] = license_info
                continue

            # This bucket is keyed on the license alone, so a record for code
            # the package vendors can share it with the package's own. Text may
            # move between records that agree about which they are, never
            # across: a vendored notice standing in for the package's own
            # license attributes it to whoever wrote the vendored code.
            # _is_carried rather than is_third_party, because a whole license
            # text found outside a license file is vendored code shipping its
            # license too, and this class already draws the line there.
            same_provenance = is_carried(license_info) == is_carried(existing)

            if self._better_evidenced(license_info, existing):
                # Do not lose license text by preferring a leaner record.
                if same_provenance and existing.text and not license_info.text:
                    license_info.text = existing.text
                combined[key] = license_info
            elif (same_provenance and license_info.text
                    and len(license_info.text) > len(existing.text or '')):
                existing.text = license_info.text

        return list(combined.values())

    @staticmethod
    def _better_evidenced(candidate: LicenseInfo, existing: LicenseInfo) -> bool:
        """Whether candidate is the record worth keeping for this license.

        Provenance comes first. A record with no file behind it can carry any
        confidence at all, so ranking on the number alone replaced a license
        file match with a record nobody can check.
        """
        if bool(candidate.source_file) != bool(existing.source_file):
            return bool(candidate.source_file)
        candidate_rank = evidence_rank(candidate)
        existing_rank = evidence_rank(existing)
        if candidate_rank != existing_rank:
            return candidate_rank > existing_rank
        if candidate.confidence != existing.confidence:
            return candidate.confidence > existing.confidence
        return bool(candidate.text) and not existing.text

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