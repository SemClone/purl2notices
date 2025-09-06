# purl2notices User Guide

## Table of Contents

1. [Introduction](#introduction)
2. [Installation](#installation)
3. [Basic Usage](#basic-usage)
4. [Input Types](#input-types)
5. [Working with Archives](#working-with-archives)
6. [Cache Management](#cache-management)
7. [User Overrides](#user-overrides)
8. [Output Formats](#output-formats)
9. [Advanced Features](#advanced-features)
10. [Troubleshooting](#troubleshooting)

## Introduction

purl2notices is a tool for generating legal notices (attribution to authors and copyrights) for software packages. It supports multiple package ecosystems and can process various input types including Package URLs (PURLs), archive files, and entire directories.

## Installation

### From PyPI

```bash
pip install semantic-copycat-purl2notices
```

### From Source

```bash
git clone https://github.com/oscarvalenzuelab/semantic-copycat-purl2notices.git
cd semantic-copycat-purl2notices
pip install -e .
```

## Basic Usage

### Processing a Single Package

```bash
# Using a Package URL
purl2notices -i pkg:npm/express@4.0.0

# Processing a JAR file
purl2notices -i library.jar

# Processing a Python wheel
purl2notices -i package-1.0.0-py3-none-any.whl
```

### Batch Processing

Create a file `packages.txt` with one PURL per line:

```
pkg:npm/express@4.18.0
pkg:pypi/requests@2.28.0
pkg:maven/org.springframework/spring-core@5.3.0
```

Then process:

```bash
purl2notices -i packages.txt -o NOTICE.txt
```

### Directory Scanning

Scan a project directory for packages and archive files:

```bash
# Basic scan
purl2notices -i ./my-project

# Recursive scan with depth limit
purl2notices -i ./my-project --recursive --max-depth 5

# Exclude certain patterns
purl2notices -i ./my-project -e "*/test/*" -e "*/node_modules/*"
```

## Input Types

### Package URLs (PURLs)

PURLs follow the format: `pkg:ecosystem/namespace/name@version`

Examples:
- `pkg:npm/express@4.0.0`
- `pkg:pypi/django@4.2.0`
- `pkg:maven/org.apache.commons/commons-lang3@3.12.0`
- `pkg:cargo/serde@1.0.0`
- `pkg:github/microsoft/vscode@1.75.0`

### Archive Files

Supported archive types:
- **Java**: `.jar`, `.war`, `.ear`, `.aar`
- **Python**: `.whl`, `.egg`, `.tar.gz`, `.tgz`
- **Ruby**: `.gem`
- **NuGet**: `.nupkg`
- **Rust**: `.crate`
- **Generic**: `.zip`, `.tar`, `.tar.bz2`

When processing archives, the tool:
1. First attempts to extract metadata using upmex (fast)
2. Falls back to extracting and scanning contents with oslili
3. Maintains proper attribution to the specific archive file

### KissBOM Files

Simple text format with one PURL per line:

```
# Frontend dependencies
pkg:npm/react@18.0.0
pkg:npm/webpack@5.0.0

# Backend dependencies
pkg:pypi/django@4.2.0
pkg:pypi/celery@5.2.0
```

### Cache Files

CycloneDX JSON format for intermediate storage:

```json
{
  "bomFormat": "CycloneDX",
  "specVersion": "1.6",
  "components": [
    {
      "type": "library",
      "name": "express",
      "version": "4.18.0",
      "purl": "pkg:npm/express@4.18.0",
      "licenses": [
        {"license": {"id": "MIT"}}
      ]
    }
  ]
}
```

## Working with Archives

### Individual Archive Processing

```bash
# Process a single JAR file
purl2notices -i application.jar -o jar-notice.txt

# Process with verbose output to see extraction details
purl2notices -i application.jar -vv
```

### Directory Scanning with Archives

When scanning directories, archives are processed separately:

```bash
purl2notices -i ./project --max-depth 5
```

This will:
- Detect and process each archive file individually
- Scan source code separately
- Maintain attribution showing which licenses came from which archives

Example output structure:
```
Packages:
  - maven-wrapper (from maven-wrapper.jar)
  - project_sources (from source code scan)
```

## Cache Management

### Creating a Cache

```bash
# Generate cache without output
purl2notices -i packages.txt --cache project.cache.json

# Generate cache and output
purl2notices -i packages.txt --cache project.cache.json -o NOTICE.txt
```

### Merging Caches

Combine multiple cache files:

```bash
# Merge multiple cache files
purl2notices -i cache1.json \
  --merge-cache cache2.json \
  --merge-cache cache3.json \
  -o combined-notice.txt
```

### Manual Cache Editing

The cache file can be manually edited to:
- Correct license information
- Add missing copyright notices
- Remove incorrect entries
- Update package metadata

After editing, regenerate notices:

```bash
purl2notices -i edited-cache.json -o NOTICE.txt
```

## User Overrides

Create a `purl2notices.overrides.json` file to customize processing:

```json
{
  "exclude_purls": [
    "pkg:npm/internal-package@1.0.0"
  ],
  "license_overrides": {
    "pkg:npm/ambiguous@1.0.0": ["MIT"],
    "pkg:pypi/custom@2.0.0": ["Apache-2.0"]
  },
  "copyright_overrides": {
    "pkg:npm/missing-copyright@1.0.0": [
      "Copyright (c) 2024 Original Author"
    ]
  },
  "disabled_licenses": {
    "pkg:npm/multi-license@1.0.0": ["GPL-3.0"]
  },
  "disabled_copyrights": {
    "pkg:npm/noisy@1.0.0": ["Generated copyright statement"]
  }
}
```

Use the overrides:

```bash
purl2notices -i packages.txt --overrides purl2notices.overrides.json -o NOTICE.txt
```

## Output Formats

### Text Format

Default human-readable format:

```bash
purl2notices -i packages.txt -o NOTICE.txt
```

Options:
- `--group-by-license`: Group packages by license (default: true)
- `--no-copyright`: Exclude copyright notices
- `--no-license-text`: Exclude full license texts

### HTML Format

Generate styled HTML output:

```bash
purl2notices -i packages.txt -o NOTICE.html -f html
```

### Custom Templates

Create a custom Jinja2 template `custom.j2`:

```jinja2
# Legal Notices

{% for license_id, packages in packages_by_license.items() %}
## {{ license_id }}

{% for package in packages %}
- {{ package.display_name }}
{% endfor %}

{% if include_license_text and license_id in license_texts %}
{{ license_texts[license_id] }}
{% endif %}
{% endfor %}
```

Use the template:

```bash
purl2notices -i packages.txt --template custom.j2 -o NOTICE.md
```

## Advanced Features

### Parallel Processing

Speed up batch processing:

```bash
# Use 8 parallel workers
purl2notices -i packages.txt --parallel 8 -o NOTICE.txt
```

### Configuration File

Create `purl2notices.yaml`:

```yaml
general:
  verbose: 1
  parallel_workers: 8
  timeout: 60

scanning:
  recursive: true
  max_depth: 10
  exclude_patterns:
    - "*/test/*"
    - "*/vendor/*"
    - "*/__pycache__/*"

output:
  format: text
  group_by_license: true
  include_copyright: true
  include_license_text: true

cache:
  enabled: true
  location: ".purl2notices.cache.json"
```

Use configuration:

```bash
purl2notices -i ./project --config purl2notices.yaml
```

### Verbose Output

Control verbosity for debugging:

```bash
# Level 1: Info messages
purl2notices -i packages.txt -v

# Level 2: Debug messages
purl2notices -i packages.txt -vv
```

### Error Handling

Continue processing on errors:

```bash
purl2notices -i packages.txt --continue-on-error --log-file errors.log
```

## Troubleshooting

### Common Issues

#### 1. Package Not Found

**Error**: "No download URL found for package"

**Solution**: 
- Verify the PURL is correct
- Check if the package exists in the registry
- For private packages, ensure authentication is configured

#### 2. Archive Extraction Failed

**Error**: "Failed to extract from archive.jar"

**Solution**:
- Verify the archive is not corrupted
- Check file permissions
- Try processing with verbose mode (-vv) for details

#### 3. License Not Recognized

**Issue**: License shown as "NOASSERTION"

**Solution**:
- Use overrides file to specify correct license
- Manually edit cache file
- Report issue if it's a common license

#### 4. Duplicate Packages

**Issue**: Same package appears multiple times

**Solution**:
- Cache automatically merges duplicates
- Use `--merge-cache` carefully
- Check for different versions of same package

### Performance Tips

1. **Use Caching**: Always use `--cache` for large projects
2. **Parallel Processing**: Increase workers with `--parallel`
3. **Limit Depth**: Use `--max-depth` for directory scans
4. **Exclude Patterns**: Skip unnecessary directories

### Getting Help

- Check verbose output: `purl2notices -i input -vv`
- Review error log: `--log-file debug.log`
- Check cache file for processing status
- Report issues on GitHub

## Examples

### Complete Project Scan

```bash
# Initial scan with cache
purl2notices -i ./my-project \
  --recursive \
  --max-depth 10 \
  --exclude "*/test/*" \
  --exclude "*/vendor/*" \
  --cache project.cache.json \
  --parallel 8 \
  -v

# Review and edit cache
# vim project.cache.json

# Generate final notices
purl2notices -i project.cache.json \
  --overrides overrides.json \
  --template custom-notice.j2 \
  -o NOTICE.html \
  -f html
```

### CI/CD Integration

```bash
#!/bin/bash
# ci-notices.sh

# Scan project
purl2notices -i . \
  --recursive \
  --cache build/notices.cache.json \
  --continue-on-error \
  --log-file build/notices.log

# Check for errors
if [ -f build/notices.log ]; then
  echo "Warning: Some packages failed processing"
  cat build/notices.log
fi

# Generate notices
purl2notices -i build/notices.cache.json \
  -o dist/NOTICE.txt \
  --no-license-text
```

### Multi-Repository Project

```bash
# Process each repository
purl2notices -i repo1/ --cache repo1.cache.json
purl2notices -i repo2/ --cache repo2.cache.json
purl2notices -i repo3/ --cache repo3.cache.json

# Merge all caches
purl2notices -i repo1.cache.json \
  --merge-cache repo2.cache.json \
  --merge-cache repo3.cache.json \
  -o combined-NOTICE.txt
```