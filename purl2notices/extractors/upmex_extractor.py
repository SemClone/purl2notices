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
                from semantic_copycat_upmex import upmex
            except ImportError:
                logger.warning("upmex not installed, returning empty result")
                return ExtractionResult(
                    success=False,
                    errors=["upmex library not available"],
                    source=ExtractionSource.UPMEX
                )
            
            # Extract metadata
            result = upmex.extract(str(path))
            
            if not result:
                return ExtractionResult(
                    success=False,
                    errors=[f"No metadata extracted from {path}"],
                    source=ExtractionSource.UPMEX
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
                                lic_data.get('name', '')
                            ),
                            name=lic_data.get('name', ''),
                            text=lic_data.get('text', ''),
                            source=ExtractionSource.UPMEX
                        )
                    else:
                        # Simple string license
                        license_info = LicenseInfo(
                            spdx_id=self.normalize_license_id(str(lic_data)),
                            name=str(lic_data),
                            source=ExtractionSource.UPMEX
                        )
                    licenses.append(license_info)
            elif 'license' in result:
                # Single license
                license_str = result['license']
                if license_str:
                    licenses.append(LicenseInfo(
                        spdx_id=self.normalize_license_id(license_str),
                        name=license_str,
                        source=ExtractionSource.UPMEX
                    ))
            
            # Parse copyrights
            copyrights = []
            if 'copyrights' in result:
                for copyright_str in result['copyrights']:
                    if isinstance(copyright_str, str):
                        copyright_info = self.parse_copyright_statement(copyright_str)
                        copyright_info.source = ExtractionSource.UPMEX
                        copyrights.append(copyright_info)
            elif 'copyright' in result:
                # Single copyright
                copyright_str = result['copyright']
                if copyright_str:
                    copyright_info = self.parse_copyright_statement(copyright_str)
                    copyright_info.source = ExtractionSource.UPMEX
                    copyrights.append(copyright_info)
            
            # Additional metadata
            metadata = {
                'package_name': result.get('name', ''),
                'package_version': result.get('version', ''),
                'description': result.get('description', ''),
                'homepage': result.get('homepage', ''),
                'repository': result.get('repository', ''),
                'authors': result.get('authors', []),
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