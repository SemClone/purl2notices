# purl2notices Documentation

Welcome to the purl2notices documentation. This tool generates legal notices (attribution to authors and copyrights) for software packages.

## Documentation Structure

### Getting Started
- **[User Guide](user-guide.md)** - Comprehensive guide covering all features and functionality
- **[Examples](examples.md)** - Practical examples for common use cases
- **[Configuration](configuration.md)** - Configuration files, overrides, and customization options

### Quick Links

#### Basic Usage
- [Processing single packages](user-guide.md#basic-usage)
- [Batch processing](user-guide.md#batch-processing)
- [Directory scanning](user-guide.md#directory-scanning)

#### Advanced Topics
- [Working with archives](user-guide.md#working-with-archives)
- [Cache management](user-guide.md#cache-management)
- [User overrides](user-guide.md#user-overrides)
- [Custom templates](configuration.md#custom-templates)

#### Integration
- [CI/CD integration](examples.md#cicd-integration)
- [Multi-repository projects](examples.md#multi-repository-project)
- [API usage](../README.md#api-usage)

## Quick Reference

### Common Commands

```bash
# Process a single package
purl2notices -i pkg:npm/express@4.0.0

# Scan a directory
purl2notices -i ./project --recursive -o NOTICE.txt

# Use cache
purl2notices -i packages.txt --cache project.cache.json

# Merge caches
purl2notices -i cache1.json --merge-cache cache2.json -o NOTICE.txt
```

### File Formats

- **Input**: PURLs, KissBOM files, CycloneDX cache, archive files, directories
- **Output**: Text, HTML, custom templates
- **Configuration**: YAML for settings, JSON for overrides

## Getting Help

- **Issues**: [GitHub Issue Tracker](https://github.com/oscarvalenzuelab/semantic-copycat-purl2notices/issues)
- **Source**: [GitHub Repository](https://github.com/oscarvalenzuelab/semantic-copycat-purl2notices)
- **License**: Apache-2.0