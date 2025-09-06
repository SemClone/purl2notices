"""Utility functions for purl2notices."""

from pathlib import Path
from typing import Optional

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