"""Utility functions for purl2notices."""

from pathlib import Path
from typing import Iterable, Optional

from .constants import DEFAULT_ARCHIVE_EXTENSIONS


def get_archive_type(file_path: Path) -> Optional[str]:
    """Determine the type of archive based on file extension.
    
    Args:
        file_path: Path to the file
        
    Returns:
        Archive type (e.g., 'java', 'python', 'ruby') or None if not an archive
    """
    for ext, archive_type in DEFAULT_ARCHIVE_EXTENSIONS.items():
        if file_path.name.endswith(ext):
            return archive_type
    return None


def is_archive_file(file_path: Path) -> bool:
    """Check if a file is a supported archive file.
    
    Args:
        file_path: Path to check
        
    Returns:
        True if file is an archive, False otherwise
    """
    return get_archive_type(file_path) is not None


def guess_purl_from_archive(archive_path: Path) -> Optional[str]:
    """Try to generate a PURL from archive filename.
    
    Args:
        archive_path: Path to archive file
        
    Returns:
        PURL string or None if cannot determine
    """
    archive_type = get_archive_type(archive_path)
    if not archive_type:
        return None
    
    filename = archive_path.stem
    
    # Handle different archive types
    if archive_type == 'python' and archive_path.suffix == '.whl':
        # Parse wheel filename: {name}-{version}-{python}-{abi}-{platform}.whl
        parts = filename.split('-')
        if len(parts) >= 2:
            name = parts[0]
            version = parts[1]
            return f"pkg:pypi/{name}@{version}"
    
    elif archive_type == 'java':
        # Parse JAR filename: {artifact}-{version}.jar
        parts = filename.rsplit('-', 1)
        if len(parts) == 2 and parts[1][0].isdigit():
            artifact = parts[0]
            version = parts[1]
            # Try to guess group from common patterns
            if '.' in artifact:
                group = artifact.rsplit('.', 1)[0]
                artifact = artifact.rsplit('.', 1)[1]
            else:
                group = artifact
            return f"pkg:maven/{group}/{artifact}@{version}"
    
    elif archive_type == 'ruby':
        # Parse gem filename: {name}-{version}.gem  
        parts = filename.rsplit('-', 1)
        if len(parts) == 2:
            name = parts[0]
            version = parts[1]
            return f"pkg:gem/{name}@{version}"
    
    elif archive_type == 'nuget':
        # Parse nupkg filename: {id}.{version}.nupkg
        parts = filename.rsplit('.', 2)
        if len(parts) >= 2:
            package_id = '.'.join(parts[:-1])
            version = parts[-1]
            return f"pkg:nuget/{package_id}@{version}"
    
    elif archive_type == 'rust':
        # Parse crate filename: {name}-{version}.crate
        parts = filename.rsplit('-', 1)
        if len(parts) == 2:
            name = parts[0]
            version = parts[1]
            return f"pkg:cargo/{name}@{version}"
    
    elif archive_type == 'npm':
        # npm packages as .tgz: {name}-{version}.tgz
        parts = filename.rsplit('-', 1)
        if len(parts) == 2:
            name = parts[0]
            version = parts[1]
            return f"pkg:npm/{name}@{version}"
    
    return None

def license_text_identity(text: Optional[str]) -> Optional[str]:
    """How two copies of a license text are told apart.

    Two packages shipping the same license should not read as disagreeing
    because one uses CRLF or leaves trailing spaces on a line.
    """
    if text is None:
        return None
    return "\n".join(line.rstrip() for line in text.strip().splitlines())


def package_license_text(texts: Iterable[str], neutral: Optional[str] = None) -> Optional[str]:
    """What one package ships for a license, ignoring the canonical text.

    Every record with no text of its own is given the canonical license, so a
    package usually carries both that and whatever it actually ships. Only the
    latter says anything about this package.
    """
    neutral_key = license_text_identity(neutral)
    seen = {}
    for text in texts:
        if not text:
            continue
        key = license_text_identity(text)
        if key != neutral_key:
            seen.setdefault(key, text)
    # More than one is this package disagreeing with itself, which is not an
    # answer about what it ships. Taking the first would pick by list order.
    if len(seen) == 1:
        return next(iter(seen.values()))
    return None


def agreed_license_text(
    package_texts: Iterable[Optional[str]], neutral: Optional[str] = None
) -> Optional[str]:
    """The one text that speaks for every package sharing a license id.

    Takes one entry per package: what that package ships, or None where it
    ships nothing. Returns None unless every package agrees.

    A package that ships nothing has not agreed, it is unknown, and lending it
    another package's copyright holders is the misattribution this exists to
    prevent. Naming one package's text for a group would do exactly that, and
    an attribution file saying nothing beats one saying whose.
    """
    seen = {}
    unknown = False
    for text in package_texts:
        if not text:
            unknown = True
            continue
        seen.setdefault(license_text_identity(text), text)
    if len(seen) == 1 and not unknown:
        return next(iter(seen.values()))
    return None


def bundled_license_text(spdx_id: str) -> Optional[str]:
    """The canonical SPDX text purl2notices ships for an id, if it has one."""
    import purl2notices

    path = Path(purl2notices.__file__).parent / "data" / "licenses" / f"{spdx_id}.txt"
    if not path.exists():
        return None
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return None
