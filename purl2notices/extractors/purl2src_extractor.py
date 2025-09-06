"""Extractor using purl2src library."""

import logging
from pathlib import Path
from typing import Optional

from .base import BaseExtractor, ExtractionResult, ExtractionSource


logger = logging.getLogger(__name__)


class Purl2SrcExtractor(BaseExtractor):
    """Extractor that uses purl2src to get package download URLs."""
    
    async def extract_from_purl(self, purl: str) -> ExtractionResult:
        """
        Extract download URL from PURL using purl2src.
        
        Note: purl2src only provides download URLs, not license/copyright info.
        """
        try:
            from purl2src import get_download_url
        except ImportError:
            logger.error("purl2src library not installed")
            return ExtractionResult(
                success=False,
                errors=["purl2src library not available"],
                source=ExtractionSource.PURL2SRC
            )
        
        try:
            # Normalize PURL - remove trailing slashes
            purl = purl.rstrip('/')
            
            # Get download URL
            result = get_download_url(purl)
            
            if result and hasattr(result, 'download_url') and result.download_url:
                return ExtractionResult(
                    success=True,
                    metadata={
                        'download_url': result.download_url,
                    },
                    source=ExtractionSource.PURL2SRC
                )
            else:
                return ExtractionResult(
                    success=False,
                    errors=[f"No download URL found for {purl}"],
                    source=ExtractionSource.PURL2SRC
                )
        except ImportError:
            logger.error("purl2src library not installed")
            return ExtractionResult(
                success=False,
                errors=["purl2src library not available"],
                source=ExtractionSource.PURL2SRC
            )
        except Exception as e:
            logger.error(f"Error extracting from purl2src: {e}")
            return ExtractionResult(
                success=False,
                errors=[str(e)],
                source=ExtractionSource.PURL2SRC
            )
    
    async def extract_from_path(self, path: Path) -> ExtractionResult:
        """purl2src doesn't work with local paths."""
        return ExtractionResult(
            success=False,
            errors=["purl2src only works with PURLs, not local paths"],
            source=ExtractionSource.PURL2SRC
        )
    
    async def get_download_url(self, purl: str) -> Optional[str]:
        """
        Get download URL for a PURL.
        
        This is the main functionality of purl2src.
        """
        result = await self.extract_from_purl(purl)
        if result.success and result.metadata:
            return result.metadata.get('download_url')
        return None