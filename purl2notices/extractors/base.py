"""Base extractor interface."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Any, Optional
from enum import Enum


class ExtractionSource(Enum):
    """Source of extraction."""
    PURL2SRC = "purl2src"
    UPMEX = "upmex"
    OSLILI = "oslili"
    MANUAL = "manual"
    CACHE = "cache"


@dataclass
class LicenseInfo:
    """License information."""
    spdx_id: str
    name: str
    text: Optional[str] = None
    source: ExtractionSource = ExtractionSource.MANUAL
    confidence: float = 1.0
    
    def __hash__(self):
        return hash((self.spdx_id, self.name))


@dataclass
class CopyrightInfo:
    """Copyright information."""
    statement: str
    year_start: Optional[int] = None
    year_end: Optional[int] = None
    holders: List[str] = field(default_factory=list)
    source: ExtractionSource = ExtractionSource.MANUAL
    confidence: float = 1.0
    
    def __hash__(self):
        return hash(self.statement)


@dataclass
class ExtractionResult:
    """Result from extraction."""
    success: bool
    licenses: List[LicenseInfo] = field(default_factory=list)
    copyrights: List[CopyrightInfo] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    source: Optional[ExtractionSource] = None


class BaseExtractor(ABC):
    """Base class for extractors."""
    
    def __init__(self):
        """Initialize extractor."""
        self.name = self.__class__.__name__
    
    @abstractmethod
    async def extract_from_purl(self, purl: str) -> ExtractionResult:
        """
        Extract information from a Package URL.
        
        Args:
            purl: Package URL string
            
        Returns:
            ExtractionResult with extracted information
        """
        pass
    
    @abstractmethod
    async def extract_from_path(self, path: Path) -> ExtractionResult:
        """
        Extract information from a local path.
        
        Args:
            path: Path to file or directory
            
        Returns:
            ExtractionResult with extracted information
        """
        pass
    
    def normalize_license_id(self, license_str: str) -> str:
        """
        Normalize license identifier to SPDX format.
        
        Common normalizations:
        - MIT License -> MIT
        - Apache 2.0 -> Apache-2.0
        - BSD 3-Clause -> BSD-3-Clause
        """
        if not license_str:
            return "NOASSERTION"
        
        # Remove common suffixes
        license_str = license_str.replace(" License", "")
        license_str = license_str.replace(" license", "")
        
        # Common mappings
        mappings = {
            "MIT": "MIT",
            "Apache 2.0": "Apache-2.0",
            "Apache-2": "Apache-2.0",
            "Apache 2": "Apache-2.0",
            "BSD 3-Clause": "BSD-3-Clause",
            "BSD-3": "BSD-3-Clause",
            "BSD 2-Clause": "BSD-2-Clause",
            "BSD-2": "BSD-2-Clause",
            "GPL-2": "GPL-2.0",
            "GPL-3": "GPL-3.0",
            "LGPL-2.1": "LGPL-2.1",
            "LGPL-3": "LGPL-3.0",
            "ISC": "ISC",
            "MPL-2": "MPL-2.0",
            "Unlicense": "Unlicense",
            "WTFPL": "WTFPL",
        }
        
        # Try exact match first
        if license_str in mappings:
            return mappings[license_str]
        
        # Try case-insensitive match
        license_upper = license_str.upper()
        for key, value in mappings.items():
            if key.upper() == license_upper:
                return value
        
        # Return as-is if no mapping found
        return license_str
    
    def parse_copyright_statement(self, statement: str) -> CopyrightInfo:
        """
        Parse a copyright statement.
        
        Examples:
        - Copyright (c) 2020 John Doe
        - Copyright 2020-2024 Jane Smith
        - © 2024 Company Inc.
        """
        import re
        
        # Extract years
        year_pattern = r'(\d{4})(?:\s*-\s*(\d{4}))?'
        year_match = re.search(year_pattern, statement)
        
        year_start = None
        year_end = None
        if year_match:
            year_start = int(year_match.group(1))
            if year_match.group(2):
                year_end = int(year_match.group(2))
        
        # Extract holders (simple approach - text after year)
        holders = []
        if year_match:
            holder_text = statement[year_match.end():].strip()
            # Remove common prefixes
            holder_text = re.sub(r'^[,\s]+', '', holder_text)
            holder_text = re.sub(r'^by\s+', '', holder_text, flags=re.IGNORECASE)
            if holder_text:
                holders.append(holder_text)
        
        return CopyrightInfo(
            statement=statement.strip(),
            year_start=year_start,
            year_end=year_end,
            holders=holders
        )
    
    def deduplicate_licenses(self, licenses: List[LicenseInfo]) -> List[LicenseInfo]:
        """Remove duplicate licenses, keeping the one with highest confidence."""
        seen = {}
        for license_info in licenses:
            key = (license_info.spdx_id, license_info.name)
            if key not in seen or license_info.confidence > seen[key].confidence:
                seen[key] = license_info
        return list(seen.values())
    
    def deduplicate_copyrights(self, copyrights: List[CopyrightInfo]) -> List[CopyrightInfo]:
        """Remove duplicate copyright statements."""
        seen = set()
        unique = []
        for copyright_info in copyrights:
            if copyright_info.statement not in seen:
                seen.add(copyright_info.statement)
                unique.append(copyright_info)
        return unique