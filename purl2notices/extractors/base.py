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
    OSSLILI = "osslili"
    MANUAL = "manual"
    CACHE = "cache"


# How a detector arrived at a license. These are osslili's own category values,
# so they are matched as it spells them: "third-party" carries a hyphen, and an
# underscore is accepted only because an earlier build used one. Getting the
# spelling wrong is silent, since a category that matches nothing simply never
# excludes anything.
CATEGORY_DECLARED = "declared"
CATEGORY_DETECTED = "detected"
CATEGORY_REFERENCED = "referenced"
CATEGORY_THIRD_PARTY = "third-party"
THIRD_PARTY_CATEGORIES = frozenset({"third-party", "third_party"})

MATCH_LICENSE_FILE = "license_file"
# osslili reports this when a whole license text matches inside a file that is
# not named like a license file, which is how a vendored source file carrying a
# complete license reads. Unlike a keyword hit, the text is actually there.
MATCH_TEXT_SIMILARITY = "text_similarity"


def is_third_party(license_info) -> bool:
    """Whether this license belongs to code the package bundles, not to it."""
    return license_info.category in THIRD_PARTY_CATEGORIES


def is_carried(license_info) -> bool:
    """Whether this license is present in the package rather than claimed by it.

    Two kinds. A third-party notice names the license of code the package
    bundles. A whole license text matching inside a file not named like a
    license file is how a vendored source carrying a complete license reads.

    Text must never move across this line. A vendored notice standing in for
    the package's own license attributes it to whoever wrote the vendored code.
    """
    if is_third_party(license_info):
        return True
    return (
        license_info.category != CATEGORY_DECLARED
        and license_info.match_type == MATCH_TEXT_SIMILARITY
    )


def evidence_rank(license_info) -> int:
    """How strong the evidence behind a license is. Higher wins.

    Used wherever two records for the same license have to be reduced to one,
    so that a package's own declaration outranks a passing mention of it and
    the record that survives is the one that can still be justified.
    """
    if is_third_party(license_info):
        return 0
    if license_info.category == CATEGORY_DECLARED:
        return 3
    if license_info.match_type == MATCH_LICENSE_FILE:
        return 2
    return 1


@dataclass
class LicenseInfo:
    """License information."""
    spdx_id: str
    name: str
    text: Optional[str] = None
    source: ExtractionSource = ExtractionSource.MANUAL
    confidence: float = 1.0
    # Where this came from. Defaults describe a license the package declares,
    # which is what every source other than a full-tree scan reports.
    category: str = CATEGORY_DECLARED
    match_type: Optional[str] = None
    detection_method: Optional[str] = None
    source_file: Optional[str] = None

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
        """Remove duplicate licenses, keeping the best-evidenced record.

        Confidence alone is the wrong tiebreak here, and it runs before anything
        ranks evidence: a package that declares MIT and also mentions it in a
        readme can score the mention higher, and dropping the declaration turns
        MIT into a mention that a later filter is then entitled to discard.
        """
        seen = {}
        for license_info in licenses:
            # Bundled licenses are deduplicated separately from the package's
            # own. Sharing a key lets a readme that merely mentions MIT outrank
            # the MIT in a third-party notice, erase the category that marked it
            # as bundled, and take the attribution down with it.
            key = (
                license_info.spdx_id,
                license_info.name,
                is_third_party(license_info),
            )
            best = seen.get(key)
            if best is None:
                seen[key] = license_info
                continue
            candidate = (evidence_rank(license_info), license_info.confidence)
            incumbent = (evidence_rank(best), best.confidence)
            # The key separates third-party from own, but not the broader
            # carried boundary, so two records here can still differ about
            # whether the license is the package's own.
            same_provenance = is_carried(license_info) == is_carried(best)

            if candidate > incumbent:
                # Only the record naming a file carries the text the package
                # ships, and it is not always the best-evidenced one. Losing it
                # here leaves the SPDX template as the only text available, which
                # is emitted with its placeholders still literal.
                if same_provenance and best.text and not license_info.text:
                    license_info.text = best.text
                seen[key] = license_info
            elif (same_provenance and license_info.text
                    and len(license_info.text) > len(best.text or '')):
                best.text = license_info.text
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