# Configuration Guide

## Configuration File

purl2notices supports configuration via YAML files to set default behaviors and preferences.

### Basic Configuration

Create a `purl2notices.yaml` file:

```yaml
general:
  verbose: 1
  parallel_workers: 8
  timeout: 60

scanning:
  recursive: true
  max_depth: 10
  exclude_patterns:
    - "*/node_modules/*"
    - "*/venv/*"
    - "*/.git/*"
    - "*/__pycache__/*"
    - "*/test/*"

output:
  format: html
  group_by_license: true
  include_copyright: true
  include_license_text: true

cache:
  enabled: true
  location: "purl2notices.cache.json"
  auto_mode: true
```

### Using Configuration

```bash
# Use configuration file
purl2notices -i ./project --config purl2notices.yaml

# Override config settings via CLI
purl2notices -i ./project --config purl2notices.yaml --format text
```

## User Overrides

The override system allows you to customize package metadata and filter unwanted content.

### Override File Structure

Create `purl2notices.overrides.json`:

```json
{
  "exclude_purls": [
    "pkg:npm/internal-package@1.0.0",
    "pkg:pypi/test-only@*"
  ],
  
  "license_overrides": {
    "pkg:npm/ambiguous@1.0.0": ["MIT"],
    "pkg:pypi/custom@2.0.0": ["Apache-2.0"],
    "pkg:maven/com.example/legacy@1.0": ["BSD-3-Clause"]
  },
  
  "copyright_overrides": {
    "pkg:npm/missing-copyright@1.0.0": [
      "Copyright (c) 2024 Original Author"
    ],
    "pkg:cargo/old-crate@0.1.0": [
      "Copyright 2020-2024 Rust Contributors"
    ]
  },
  
  "disabled_licenses": {
    "pkg:npm/multi-license@1.0.0": ["GPL-3.0"],
    "pkg:pypi/dual-licensed@2.0.0": ["AGPL-3.0"]
  },
  
  "disabled_copyrights": {
    "pkg:npm/noisy@1.0.0": ["Generated copyright statement"],
    "pkg:pypi/verbose@1.0.0": ["Auto-extracted copyright"]
  }
}
```

### Override Fields

- **exclude_purls**: List of PURLs to completely exclude from output
- **license_overrides**: Replace detected licenses with specified ones
- **copyright_overrides**: Replace detected copyrights with specified ones
- **disabled_licenses**: Remove specific licenses from multi-licensed packages
- **disabled_copyrights**: Remove specific copyright statements

### Applying Overrides

```bash
purl2notices -i packages.txt --overrides purl2notices.overrides.json -o NOTICE.txt
```

## Input Formats

### KissBOM Format

Simple text file with one PURL per line:

```
# Frontend dependencies
pkg:npm/react@18.0.0
pkg:npm/webpack@5.0.0

# Backend dependencies
pkg:pypi/django@4.2.0
pkg:pypi/celery@5.2.0

# Comments are supported
pkg:maven/org.springframework/spring-core@5.3.0
pkg:cargo/serde@1.0.0
```

### Cache Format

CycloneDX JSON format for intermediate storage:

```json
{
  "bomFormat": "CycloneDX",
  "specVersion": "1.6",
  "serialNumber": "urn:uuid:...",
  "version": 1,
  "metadata": {
    "timestamp": "2024-01-06T12:00:00Z"
  },
  "components": [
    {
      "type": "library",
      "bom-ref": "pkg:npm/express@4.18.0",
      "name": "express",
      "version": "4.18.0",
      "purl": "pkg:npm/express@4.18.0",
      "licenses": [
        {
          "license": {
            "id": "MIT",
            "text": "..."
          }
        }
      ],
      "copyright": "Copyright (c) 2009-2024 TJ Holowaychuk",
      "properties": [
        {
          "name": "source_path",
          "value": "/path/to/express.jar"
        }
      ]
    }
  ]
}
```

## Command-Line Options

### Input/Output Options

| Option | Description | Default |
|--------|-------------|---------|
| `-i, --input` | Input (PURL, file, directory, archive, or cache) | Required |
| `-o, --output` | Output file path | stdout |
| `-f, --format` | Output format (text, html) | text |
| `-t, --template` | Custom Jinja2 template file | built-in |

### Processing Options

| Option | Description | Default |
|--------|-------------|---------|
| `-m, --mode` | Operation mode (auto, single, kissbom, scan, archive, cache) | auto |
| `-p, --parallel` | Number of parallel workers | 4 |
| `-c, --cache` | Cache file location | None |
| `--no-cache` | Disable caching | False |
| `--merge-cache` | Additional cache files to merge | None |

### Scanning Options

| Option | Description | Default |
|--------|-------------|---------|
| `-r, --recursive` | Recursive directory scan | False |
| `-d, --max-depth` | Maximum scan depth | 10 |
| `-e, --exclude` | Exclude patterns (can use multiple times) | None |

### Output Options

| Option | Description | Default |
|--------|-------------|---------|
| `--group-by-license` | Group packages by license | True |
| `--no-copyright` | Exclude copyright notices | False |
| `--no-license-text` | Exclude full license texts | False |

### Other Options

| Option | Description | Default |
|--------|-------------|---------|
| `-v, --verbose` | Increase verbosity (use -vv for debug) | 0 |
| `--config` | Configuration file path | None |
| `--overrides` | User overrides file path | None |
| `--continue-on-error` | Continue processing on errors | False |
| `--log-file` | Log file path | None |
| `--help` | Show help message | - |

## Environment Variables

You can set default values using environment variables:

```bash
export PURL2NOTICES_CONFIG=/path/to/config.yaml
export PURL2NOTICES_CACHE=/path/to/cache.json
export PURL2NOTICES_OVERRIDES=/path/to/overrides.json
export PURL2NOTICES_PARALLEL=8

purl2notices -i packages.txt -o NOTICE.txt
```

## Custom Templates

### Template Variables

Available variables in templates:

- `packages`: List of all packages
- `packages_by_license`: Dict grouping packages by license
- `license_texts`: Dict of license ID to full text
- `include_copyright`: Boolean for copyright inclusion
- `include_license_text`: Boolean for license text inclusion
- `timestamp`: Generation timestamp
- `total_packages`: Total package count

### Example Template

```jinja2
# Software Bill of Materials
Generated: {{ timestamp }}
Total Packages: {{ total_packages }}

{% for license_id, packages in packages_by_license.items() %}
## License: {{ license_id }}

### Components ({{ packages|length }})
{% for package in packages %}
- **{{ package.name }}** v{{ package.version }}
  {%- if package.source_path %}
  - Source: {{ package.source_path }}
  {%- endif %}
  {%- if package.homepage %}
  - Homepage: {{ package.homepage }}
  {%- endif %}
{% endfor %}

{% if include_copyright %}
### Attributions
{% for package in packages %}
{% for copyright in package.copyrights %}
- {{ copyright.statement }}
{% endfor %}
{% endfor %}
{% endif %}

{% endfor %}
```

## Performance Tuning

### Parallel Processing

Adjust worker count based on your system:

```bash
# CPU-bound tasks (license detection)
purl2notices -i ./large-project --parallel $(nproc)

# Network-bound tasks (package downloads)
purl2notices -i packages.txt --parallel 16
```

### Cache Strategy

For large projects:

1. Initial scan with aggressive caching:
```bash
purl2notices -i ./project --cache full-scan.cache.json -v
```

2. Incremental updates:
```bash
purl2notices -i ./new-packages --merge-cache full-scan.cache.json \
  --cache updated.cache.json
```

3. Final generation:
```bash
purl2notices -i updated.cache.json -o NOTICE.txt --no-cache
```

### Memory Management

For very large projects with thousands of packages:

```bash
# Process in batches
split -l 100 packages.txt batch_

for batch in batch_*; do
  purl2notices -i $batch --cache $batch.cache.json
done

# Merge all caches
purl2notices -i batch_aa.cache.json \
  --merge-cache batch_ab.cache.json \
  --merge-cache batch_ac.cache.json \
  -o NOTICE.txt
```