"""Base extractor interface."""

import os
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any, Dict, Iterable, List, Optional
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


# A license file's path says who it belongs to. A package states its own terms
# at its root; a license sitting inside a subdirectory came with the code in
# that subdirectory, and one in a file that says so in its name is a notice
# about what the package bundles rather than what it is.
# "notice" is deliberately absent: an Apache-2.0 section 4(d) NOTICE file is the
# package's own attribution, so matching it would put a spurious "Bundles:
# Apache-2.0" beside every Apache artifact's own Apache-2.0.
BUNDLED_FILE_NAME = re.compile(
    r"bundled|third[-_ ]?party|vendor", re.IGNORECASE)

# Directory names that say the code below them came from somewhere else. Unlike
# depth, these do not need the package root to be known, so they still answer
# for a path we cannot place.
BUNDLED_DIR_NAME = re.compile(
    r"^(vendor|vendored|third[-_]?party|node_modules|externals?|deps|"
    r"bundled).*", re.IGNORECASE)

# Directories where an ecosystem conventionally keeps the package's own
# license, so a license one level inside them is still the package's own:
# META-INF for jars, .dist-info and .egg-info for wheels and sdists, LICENSES
# for REUSE-compliant trees.
OWN_LICENSE_DIRS = frozenset({
    "META-INF", "LICENSES", "licenses", "licence", "LICENCES",
})

# Wheels and sdists keep the package's own license inside a metadata directory
# named after the package, so the name is not fixed and has to be matched.
OWN_LICENSE_DIR_SUFFIXES = (".dist-info", ".egg-info")


def detection_root(
    source_files: Iterable[Optional[str]],
    scanned_root: Optional[object] = None,
) -> str:
    """The directory the scanned package sits at, derived from what was found.

    An archive reports its members under a single top-level directory whose name
    is not known ahead of time ("numpy-1.26.2", "package"), so depth has to be
    measured from something the paths themselves agree on.

    Only the shallowest path decides it. Taking the common prefix of every
    detection would follow them down into a vendored tree when that is where
    most licenses are, and then a package's own root license would look nested.
    """
    paths = [PurePosixPath(s) for s in source_files if s]
    if not paths:
        return ""

    # A scanned archive reports members relative to it, all under one top-level
    # directory, so that directory is the root whether or not any license sits
    # at it. Deriving the root from where licenses happen to be would make the
    # shallowest vendored directory the root in a package whose only licenses
    # are vendored, and hand it one of those as its own.
    if not any(path.is_absolute() for path in paths):
        # A path with a single part is already at the package root, so there is
        # no wrapper directory to strip. Deriving one from the paths that do
        # have directories would make the first of those the root, and an
        # archive holding LICENSE alongside vendor/LICENSE would call the
        # vendored one the package's own.
        if any(len(path.parts) == 1 for path in paths):
            return ""
        tops = {path.parts[0] for path in paths}
        if len(tops) == 1:
            return tops.pop()
        return ""

    # A scanned directory reports absolute paths. Its root is known from what
    # was scanned and is passed in; inferring it from where licenses happen to
    # sit would do exactly what the archive branch above refuses to do, and hand
    # a dependency's license to the package as its own.
    if scanned_root is not None:
        # Resolved, because the paths reported alongside it are absolute and a
        # relative root would match none of them.
        try:
            return str(Path(scanned_root).resolve())
        except OSError:
            return str(scanned_root)

    dirs = [str(path.parent) for path in paths]
    try:
        root = os.path.commonpath(dirs) if len(dirs) > 1 else dirs[0]
    except ValueError:
        # Mixed absolute and relative paths have nothing in common. Judging
        # none of them beats judging them against a wrong root.
        return ""
    return "" if root == "." else root


def is_bundled_path(source_file: Optional[str], root: str) -> bool:
    """Whether this path belongs to code the package carries rather than to it.

    Returns False when there is no path to judge, which leaves the detector's
    own category as the only signal, as before.
    """
    if not source_file:
        return False
    path = PurePosixPath(str(source_file))
    try:
        relative = path.relative_to(root) if root else path
    except ValueError:
        relative = path
    parts = relative.parts
    if not parts:
        return False
    if BUNDLED_FILE_NAME.search(parts[-1]):
        return True
    # A directory that names itself as carried answers wherever the path sits.
    if any(BUNDLED_DIR_NAME.match(part) for part in parts[:-1]):
        return True
    # Depth is only meaningful relative to a known root. Without one, or when
    # the path does not sit under the root we were given, every absolute path
    # looks deeply nested and a package's own root license reads as carried.
    if not root or relative == path:
        return False
    if len(parts) == 1:
        return False
    # Some ecosystems keep a package's own license in a fixed subdirectory
    # rather than at the root, so depth alone would call it carried.
    if parts[0] in OWN_LICENSE_DIRS or parts[0].endswith(OWN_LICENSE_DIR_SUFFIXES):
        return len(parts) > 2
    return True


def _dedupe_key(license_info):
    """What makes two records for one license the same record.

    Provenance is part of it: a package can be under BSD-3-Clause and also ship
    BSD-3-Clause code. For carried records the text is part of it too, since two
    vendored components under the same license ship differently filled notices
    and both are owed attribution. The package's own records still collapse on
    the license alone, so that the best-evidenced one wins as before.
    """
    from ..utils import license_text_identity

    carried = is_carried(license_info)
    return (
        license_info.spdx_id,
        license_info.name,
        carried,
        license_text_identity(license_info.text) if carried else None,
    )


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
            key = _dedupe_key(license_info)
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