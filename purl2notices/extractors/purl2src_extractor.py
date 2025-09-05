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
            try:
                from semantic_copycat_purl2src import purl2src
            except ImportError:
                # Fallback - return a mock download URL for testing
                logger.warning("purl2src not installed, using fallback")
                # For npm packages, we can construct a registry URL
                if purl.startswith("pkg:npm/"):
                    parts = purl.replace("pkg:npm/", "").split("@")
                    if len(parts) == 2:
                        name, version = parts
                        url = f"https://registry.npmjs.org/{name}/-/{name}-{version}.tgz"
                        return ExtractionResult(
                            success=True,
                            metadata={'download_url': url},
                            source=ExtractionSource.PURL2SRC
                        )
                return ExtractionResult(
                    success=False,
                    errors=["purl2src not available and no fallback for this package type"],
                    source=ExtractionSource.PURL2SRC
                )
            
            # Get download URL
            result = purl2src.get_download_url(purl)
            
            if result and 'url' in result:
                return ExtractionResult(
                    success=True,
                    metadata={
                        'download_url': result['url'],
                        'repository_url': result.get('repository_url'),
                        'homepage_url': result.get('homepage_url'),
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