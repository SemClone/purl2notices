"""Extractor using osslili library."""

import logging
from pathlib import Path

from .base import (
    BaseExtractor, ExtractionResult, ExtractionSource,
    LicenseInfo, CopyrightInfo
)


logger = logging.getLogger(__name__)


class OssliliExtractor(BaseExtractor):
    """Extractor that uses osslili for license/copyright detection."""
    
    async def extract_from_purl(self, purl: str) -> ExtractionResult:
        """osslili works with local files, not PURLs directly."""
        return ExtractionResult(
            success=False,
            errors=["osslili requires local files or directories"],
            source=ExtractionSource.OSSLILI
        )
    
    async def extract_from_path(self, path: Path) -> ExtractionResult:
        """Extract license and copyright info using osslili."""
        try:
            try:
                from osslili import LicenseCopyrightDetector
            except ImportError:
                logger.warning("osslili not installed, returning empty result")
                return ExtractionResult(
                    success=False,
                    errors=["osslili library not available"],
                    source=ExtractionSource.OSSLILI
                )
            
            # Extract information
            detector = LicenseCopyrightDetector()
            result = detector.process_local_path(str(path))
            
            if not result:
                return ExtractionResult(
                    success=False,
                    errors=[f"No information extracted from {path}"],
                    source=ExtractionSource.OSSLILI
                )
            
            # Parse licenses
            licenses = []
            if hasattr(result, 'licenses') and result.licenses:
                for lic_data in result.licenses:
                    license_info = LicenseInfo(
                        spdx_id=self.normalize_license_id(
                            getattr(lic_data, 'spdx_id', '') or
                            getattr(lic_data, 'name', 'NOASSERTION')
                        ),
                        name=getattr(lic_data, 'name', '') or getattr(lic_data, 'spdx_id', ''),
                        text=getattr(lic_data, 'text', ''),
                        source=ExtractionSource.OSSLILI,
                        confidence=getattr(lic_data, 'confidence', 0.8)
                    )
                    licenses.append(license_info)
            
            # Parse copyrights
            copyrights = []
            if hasattr(result, 'copyrights') and result.copyrights:
                for copyright_data in result.copyrights:
                    copyright_info = CopyrightInfo(
                        statement=getattr(copyright_data, 'statement', ''),
                        year_start=getattr(copyright_data, 'years', None),
                        year_end=None,
                        holders=[getattr(copyright_data, 'holder', '')] if getattr(copyright_data, 'holder', '') else [],
                        source=ExtractionSource.OSSLILI,
                        confidence=getattr(copyright_data, 'confidence', 0.8)
                    )
                    if copyright_info.statement:
                        copyrights.append(copyright_info)
            
            # Additional metadata
            metadata = {
                'package_name': getattr(result, 'package_name', ''),
                'package_version': getattr(result, 'package_version', ''),
            }
            
            return ExtractionResult(
                success=True,
                licenses=self.deduplicate_licenses(licenses),
                copyrights=self.deduplicate_copyrights(copyrights),
                metadata=metadata,
                source=ExtractionSource.OSSLILI
            )
            
        except ImportError:
            logger.error("osslili library not installed")
            return ExtractionResult(
                success=False,
                errors=["osslili library not available"],
                source=ExtractionSource.OSSLILI
            )
        except Exception as e:
            logger.error(f"Error extracting with osslili: {e}")
            return ExtractionResult(
                success=False,
                errors=[str(e)],
                source=ExtractionSource.OSSLILI
            )