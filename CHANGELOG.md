# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.2.0] - 2025-10-16

### Fixed
- Fix KissBOM CLI parameter order mismatch that was causing validation failures
- Update JSON format test expectations to match actual output structure
- Enhance CombinedExtractor metadata merging to preserve upmex package identification fields
- Ensure metadata from upmex takes precedence over oslili during merge operations
- Remove cache file from repository to prevent accidental commits

### Changed
- Improved metadata handling in CombinedExtractor to preserve package identification data
- Better error handling and test coverage for CLI functionality
- Enhanced test suite reliability for JSON output format validation

## [1.1.9] - 2025-09-16

### Added
- Full implementation of Ruby Gem and Chef cookbook detector
- Support for Chef cookbooks with metadata.rb and metadata.json files
- Support for Ruby gems with .gemspec files
- Support for .gem archive detection
- Comprehensive test coverage for Ruby/Chef detection
- Special handling for Chef cookbooks to process entire cookbook directory
- Metadata preservation for packages detected with PURLs

### Fixed
- Chef cookbooks in subdirectories are now detected as separate packages instead of being merged
- License information from Chef metadata.rb is properly extracted and converted to License objects
- Detection metadata is preserved when processing packages through PURL pipeline
- Homepage property access in formatter now safely retrieves from metadata dictionary (fixes #8)

### Changed
- GemDetector is no longer a stub - fully functional implementation
- Chef cookbooks detected locally do not generate PURLs since they cannot be downloaded from registries
- Improved core processor to handle Chef cookbooks specially by processing cookbook directories

## [1.1.8] - 2025-09-15

### Added
- Table of Contents index for HTML notice files with navigation links
- Package-based anchor IDs for direct navigation to specific packages
- License information displayed next to each package in the index
- Smooth scrolling CSS for better navigation experience
- "Back to Top" link for easy return to the index

### Changed
- HTML template now lists all packages individually in the Table of Contents
- Anchor IDs are placed on package elements rather than license headers
- Improved support for package names with special characters (colons, slashes)

## [1.1.7] - 2025-09-10

### Fixed
- NPM detector now properly handles node_modules as input directory
- Correctly detects packages when scanning node_modules directly

### Added
- Filed issue #4 for future --offline mode feature

## [1.1.6] - 2025-09-10

### Added
- Explicit offline-only mode configuration for upmex extractor

### Changed
- upmex extractor now operates strictly in offline mode to prevent network lookups
- Improved JAR file processing reliability with fallback to oslili

## [1.1.5] - 2025-09-10

### Fixed
- License text display in HTML output for grouped licenses with multiple IDs
- Updated minimum dependency versions for better compatibility
- Added python-Levenshtein for optimal fuzzy matching performance

## [1.1.4] - 2025-09-10

### Fixed
- UnboundLocalError in CLI caused by duplicate sys import inside main() function

## [1.1.3] - 2025-09-06

### Added
- Shell completion support for bash, zsh, and fish
- JSON output format (`--format json`) for programmatic processing
- Test suite with unit and integration tests
- Utility functions module to reduce code duplication
- Exclusion pattern support for archive file scanning

### Changed
- Archive scanner now includes hidden directories (e.g., `.mvn/`)
- CLI always sets recursive and max_depth configuration values
- Refactored to eliminate code duplication across modules

### Fixed
- CLI depth parameter (`-d`) now correctly passes to directory scanner
- Hidden directories are no longer skipped during archive scanning
- Config key mismatch for max_depth (was `scan.max_depth`, now `scanning.max_depth`)
- License model missing @dataclass decorator
- Test data files in test directories can now be excluded with `-e test`

## [1.1.0] - 2024-01-06

### Added
- Archive file mode for processing individual archive files (JAR, WAR, WHL, etc.)
- Separate package attribution for archive files during directory scans
- Support for merging multiple cache files with `--merge-cache` option
- Dynamic license recognition for common OSS patterns
- Centralized constants module for better maintainability
- User override system for filtering packages and modifying metadata
- Improved cache merging that preserves existing data

### Changed
- Directory scanning now processes archive files as separate packages with proper attribution
- Cache saving now merges with existing cache instead of replacing it
- Override system now properly applies to both new and cached packages
- Improved Apache license variant recognition

### Fixed
- Cache merging now properly combines packages instead of replacing
- User overrides are now correctly applied when loading from cache
- Package exclusion via `exclude_purls` now works correctly
- Archive files in deep directory structures are now properly detected

### Removed
- Dead code: unused `save_cache()` and `validate_cache()` methods from core module
- Unused `validate()` method from cache manager
- Various unused imports across modules

## [0.1.0] - 2024-01-01

### Added
- Initial release
- Support for processing Package URLs (PURLs)
- KissBOM file processing
- Directory scanning for packages
- Cache support using CycloneDX format
- Multiple output formats (text, HTML)
- Integration with semantic-copycat ecosystem (purl2src, upmex, oslili)
- License and copyright extraction
- Configurable parallel processing
- Template-based output generation