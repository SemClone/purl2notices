"""Extractor using oslili library."""

import logging
from pathlib import Path

from .base import (
    BaseExtractor, ExtractionResult, ExtractionSource,
    LicenseInfo, CopyrightInfo
)


logger = logging.getLogger(__name__)


class OsliliExtractor(BaseExtractor):
    """Extractor that uses oslili for license/copyright detection."""
    
    async def extract_from_purl(self, purl: str) -> ExtractionResult:
        """oslili works with local files, not PURLs directly."""
        return ExtractionResult(
            success=False,
            errors=["oslili requires local files or directories"],
            source=ExtractionSource.OSLILI
        )
    
    async def extract_from_path(self, path: Path) -> ExtractionResult:
        """Extract license and copyright info using oslili."""
        try:
            try:
                from semantic_copycat_oslili import oslili
            except ImportError:
                logger.warning("oslili not installed, returning empty result")
                return ExtractionResult(
                    success=False,
                    errors=["oslili library not available"],
                    source=ExtractionSource.OSLILI
                )
            
            # Extract information
            result = oslili.extract(str(path))
            
            if not result:
                return ExtractionResult(
                    success=False,
                    errors=[f"No information extracted from {path}"],
                    source=ExtractionSource.OSLILI
                )
            
            # Parse licenses
            licenses = []
            if 'licenses' in result:
                for lic_data in result['licenses']:
                    if isinstance(lic_data, dict):
                        license_info = LicenseInfo(
                            spdx_id=self.normalize_license_id(
                                lic_data.get('spdx_id', '') or
                                lic_data.get('id', '') or
                                lic_data.get('name', 'NOASSERTION')
                            ),
                            name=lic_data.get('name', ''),
                            text=lic_data.get('text', ''),
                            source=ExtractionSource.OSLILI,
                            confidence=lic_data.get('confidence', 0.8)
                        )
                    else:
                        license_info = LicenseInfo(
                            spdx_id=self.normalize_license_id(str(lic_data)),
                            name=str(lic_data),
                            source=ExtractionSource.OSLILI,
                            confidence=0.7
                        )
                    licenses.append(license_info)
            
            # Parse copyrights
            copyrights = []
            if 'copyrights' in result:
                for copyright_data in result['copyrights']:
                    if isinstance(copyright_data, dict):
                        # Structured copyright data
                        copyright_info = CopyrightInfo(
                            statement=copyright_data.get('statement', ''),
                            year_start=copyright_data.get('year_start'),
                            year_end=copyright_data.get('year_end'),
                            holders=copyright_data.get('holders', []),
                            source=ExtractionSource.OSLILI,
                            confidence=copyright_data.get('confidence', 0.8)
                        )
                    else:
                        # Simple string
                        copyright_info = self.parse_copyright_statement(str(copyright_data))
                        copyright_info.source = ExtractionSource.OSLILI
                        copyright_info.confidence = 0.7
                    
                    if copyright_info.statement:
                        copyrights.append(copyright_info)
            
            # Additional metadata
            metadata = {
                'files_scanned': result.get('files_scanned', 0),
                'detection_method': result.get('detection_method', ''),
                'confidence_score': result.get('confidence_score', 0.0),
            }
            
            return ExtractionResult(
                success=True,
                licenses=self.deduplicate_licenses(licenses),
                copyrights=self.deduplicate_copyrights(copyrights),
                metadata=metadata,
                source=ExtractionSource.OSLILI
            )
            
        except ImportError:
            logger.error("oslili library not installed")
            return ExtractionResult(
                success=False,
                errors=["oslili library not available"],
                source=ExtractionSource.OSLILI
            )
        except Exception as e:
            logger.error(f"Error extracting with oslili: {e}")
            return ExtractionResult(
                success=False,
                errors=[str(e)],
                source=ExtractionSource.OSLILI
            )