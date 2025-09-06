"""Constants used across the purl2notices package."""

# Non-OSS license indicators
NON_OSS_INDICATORS = [
    'proprietary', 'commercial', 'custom', 'closed',
    'all rights reserved', 'confidential', 'private',
    'unlicensed', 'no license', 'other'
]

# Common OSS license patterns (for recognition without exact version)
COMMON_OSS_PATTERNS = [
    'apache', 'mit', 'bsd', 'gpl', 'lgpl', 'mpl', 'isc',
    'artistic', 'zlib', 'python', 'boost', 'unlicense',
    'cc0', 'wtfpl', 'postgresql', 'openssl', 'curl'
]

# Cache format constants
CACHE_FORMAT = "CycloneDX"
CACHE_SPEC_VERSION = "1.6"
CACHE_VERSION = "1.0"

# Archive extensions by ecosystem (based on upmex extractors)
DEFAULT_ARCHIVE_EXTENSIONS = {
    # Java/JVM
    '.jar': 'java',
    '.war': 'java',
    '.ear': 'java',
    '.aar': 'java',
    '.jpi': 'java',
    '.hpi': 'java',
    
    # Python
    '.whl': 'python',
    '.egg': 'python',
    '.tar.gz': 'python',  # Common for Python but also generic
    '.tgz': 'python',
    '.tar.bz2': 'python',
    '.tar.xz': 'python',
    
    # Ruby
    '.gem': 'ruby',
    
    # Rust
    '.crate': 'rust',
    
    # .NET/NuGet
    '.nupkg': 'nuget',
    '.snupkg': 'nuget',
    
    # Go
    '.mod': 'go',
    
    # Node.js/npm  
    '.tgz': 'npm',  # npm packages are .tgz
    
    # Perl
    '.par': 'perl',
    
    # CocoaPods (iOS/macOS)
    '.podspec': 'cocoapods',
    
    # Conan (C/C++)
    '.conan': 'conan',
    
    # Conda
    '.conda': 'conda',
    
    # Linux packages
    '.deb': 'deb',
    '.udeb': 'deb',
    '.rpm': 'rpm',
    '.srpm': 'rpm',
    
    # Generic archives
    '.zip': 'generic',
    '.tar': 'generic',
    '.7z': 'generic',
    '.rar': 'generic',
    '.gz': 'generic',
    '.bz2': 'generic',
    '.xz': 'generic',
}

# Get unique extensions as a list for backward compatibility
ARCHIVE_EXTENSIONS = list(set(DEFAULT_ARCHIVE_EXTENSIONS.keys()))