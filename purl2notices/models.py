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
    
    def __hash__(self) -> int:
        return hash(self.spdx_id)


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
        """Get list of SPDX IDs for licenses."""
        return [lic.spdx_id for lic in self.licenses]

    @property
    def has_licenses(self) -> bool:
        """Check if package has any licenses."""
        return len(self.licenses) > 0
    
    def __hash__(self) -> int:
        return hash(self.purl or self.display_name)