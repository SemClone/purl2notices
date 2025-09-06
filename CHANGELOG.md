# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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