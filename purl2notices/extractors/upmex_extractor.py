"""Extractor using upmex library."""

import logging
from pathlib import Path
from typing import Dict, Any

from .base import (
    BaseExtractor, ExtractionResult, ExtractionSource,
    LicenseInfo, CopyrightInfo
)


logger = logging.getLogger(__name__)


class UpmexExtractor(BaseExtractor):
    """Extractor that uses upmex to extract metadata from packages."""
    
    async def extract_from_purl(self, purl: str) -> ExtractionResult:
        """upmex works with downloaded packages, not PURLs directly."""
        return ExtractionResult(
            success=False,
            errors=["upmex requires a downloaded package file"],
            source=ExtractionSource.UPMEX
        )
    
    async def extract_from_path(self, path: Path) -> ExtractionResult:
        """Extract metadata from a package file using upmex."""
        try:
            try:
                from upmex import PackageExtractor
            except ImportError:
                logger.warning("upmex not installed, returning empty result")
                return ExtractionResult(
                    success=False,
                    errors=["upmex library not available"],
                    source=ExtractionSource.UPMEX
                )
            
            # Extract metadata - ensure offline mode only
            # Pass config to ensure no online lookups
            config = {
                'offline': True,  # Force offline mode if supported
                'no_network': True,  # Alternative flag for no network access
            }
            extractor = PackageExtractor(config=config)
            result = extractor.extract(str(path))
            
            if not result:
                return ExtractionResult(
                    success=False,
                    errors=[f"No metadata extracted from {path}"],
                    source=ExtractionSource.UPMEX
                )
            
            # Parse licenses from PackageMetadata object
            licenses = []
            if hasattr(result, 'licenses') and result.licenses:
                for lic_data in result.licenses:
                    # lic_data is a LicenseInfo object from upmex
                    license_info = LicenseInfo(
                        spdx_id=self.normalize_license_id(lic_data.spdx_id or lic_data.name or ''),
                        name=lic_data.name or lic_data.spdx_id or '',
                        text=lic_data.text or '',
                        source=ExtractionSource.UPMEX
                    )
                    licenses.append(license_info)
            
            # Parse copyrights from PackageMetadata object
            copyrights = []
            if hasattr(result, 'copyright') and result.copyright:
                copyright_info = self.parse_copyright_statement(result.copyright)
                copyright_info.source = ExtractionSource.UPMEX
                copyrights.append(copyright_info)
            
            # Additional metadata from PackageMetadata object
            metadata = {
                'package_name': getattr(result, 'name', ''),
                'package_version': getattr(result, 'version', ''),
                'description': getattr(result, 'description', ''),
                'homepage': getattr(result, 'homepage', ''),
                'repository': getattr(result, 'repository', ''),
                'authors': getattr(result, 'authors', []),
            }
            
            return ExtractionResult(
                success=True,
                licenses=self.deduplicate_licenses(licenses),
                copyrights=self.deduplicate_copyrights(copyrights),
                metadata=metadata,
                source=ExtractionSource.UPMEX
            )
            
        except ImportError:
            logger.error("upmex library not installed")
            return ExtractionResult(
                success=False,
                errors=["upmex library not available"],
                source=ExtractionSource.UPMEX
            )
        except Exception as e:
            logger.error(f"Error extracting with upmex: {e}")
            return ExtractionResult(
                success=False,
                errors=[str(e)],
                source=ExtractionSource.UPMEX
            )