"""Data models for purl2notices."""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum


class ProcessingStatus(Enum):
    """Status of package processing."""
    SUCCESS = "success"
    FAILED = "failed"
    NO_LICENSE = "no_license"
    NO_COPYRIGHT = "no_copyright"
    UNAVAILABLE = "unavailable"


@dataclass
class License:
    """License information."""
    spdx_id: str
    name: str
    text: str
    source: str = "unknown"  # Where the license was found
    # Whether this is the package's own license or one belonging to code it
    # carries. Without the distinction a package reports the licenses of
    # everything it vendors as its own, and an LGPL on a line that reads as the
    # package's own terms changes what a policy check decides.
    bundled: bool = False

    def __hash__(self) -> int:
        return hash((self.spdx_id, self.bundled))


@dataclass
class Copyright:
    """Copyright information."""
    statement: str
    confidence: float = 1.0
    year_start: Optional[int] = None
    year_end: Optional[int] = None
    holders: List[str] = field(default_factory=list)

    def __hash__(self) -> int:
        return hash(self.statement)


@dataclass
class Package:
    """Package information."""
    purl: Optional[str] = None
    name: str = ""
    version: str = ""
    type: str = ""  # npm, pypi, maven, etc.
    namespace: Optional[str] = None
    licenses: List[License] = field(default_factory=list)
    copyrights: List[Copyright] = field(default_factory=list)
    status: ProcessingStatus = ProcessingStatus.SUCCESS
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    source_path: Optional[str] = None  # For directory scan mode
    
    @property
    def own_licenses(self) -> List["License"]:
        """The licenses the package is under."""
        return [lic for lic in self.licenses if not lic.bundled]

    @property
    def bundled_licenses(self) -> List["License"]:
        """The licenses of code the package carries."""
        return [lic for lic in self.licenses if lic.bundled]

    @property
    def distinct_bundled_licenses(self) -> List["License"]:
        """One record per carried license, keeping the text of each.

        Deduplicated on the text as well as the id, since a package can carry
        two components under the same license with differently filled notices,
        and both are owed attribution.
        """
        from .utils import license_text_identity

        seen = set()
        out = []
        for lic in self.bundled_licenses:
            key = (lic.spdx_id, license_text_identity(lic.text))
            if key in seen:
                continue
            seen.add(key)
            out.append(lic)
        return out

    @property
    def display_name(self) -> str:
        """Get display name for the package."""
        if self.purl:
            # If we have a PURL and source_path (archive), show both for traceability
            if self.source_path:
                from pathlib import Path
                filename = Path(self.source_path).name
                return f"{self.purl} (from {filename})"
            return self.purl
        elif self.name and self.version:
            if self.source_path:
                from pathlib import Path
                filename = Path(self.source_path).name
                return f"{self.name}@{self.version} (from {filename})"
            else:
                return f"{self.name}@{self.version}"
        elif self.name:
            return self.name
        elif self.source_path:
            return f"local:{self.source_path}"
        return "unknown"

    @property
    def source_filename(self) -> Optional[str]:
        """Get just the source filename if available."""
        if self.source_path:
            from pathlib import Path
            return Path(self.source_path).name
        return None

    @property
    def license_ids(self) -> List[str]:
        """The SPDX ids this package is licensed under.

        Licenses belonging to code the package carries are not among them.
        Listing them here says the package is under all of them, which for a
        vendored LGPL changes what a policy check decides. They are reachable
        as bundled_license_ids and are reported beside the package.
        """
        return [lic.spdx_id for lic in self.own_licenses]

    @property
    def bundled_license_ids(self) -> List[str]:
        """The SPDX ids of code the package carries, in order, deduplicated."""
        return list(dict.fromkeys(lic.spdx_id for lic in self.bundled_licenses))

    @property
    def has_licenses(self) -> bool:
        """Check if package has any licenses."""
        return len(self.licenses) > 0
    
    def __hash__(self) -> int:
        return hash(self.purl or self.display_name)