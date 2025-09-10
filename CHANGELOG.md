# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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