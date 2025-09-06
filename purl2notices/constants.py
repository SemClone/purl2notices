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