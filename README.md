# purl2notices

Generate legal notices (attribution to authors and copyrights) for software packages.

## Features

- **Multiple Input Modes**:
  - Single Package URL (PURL)
  - Batch processing from KissBOM files
  - Directory scanning for packages
  - Cache-based processing

- **Comprehensive Package Support**:
  - 12+ package ecosystems (npm, PyPI, Maven, Cargo, Go, etc.)
  - Archive file detection (JAR, wheel, gem, tarball, etc.)
  - Metadata file parsing (package.json, pom.xml, Cargo.toml, etc.)

- **Flexible Output**:
  - Text and HTML formats
  - Customizable templates (Jinja2)
  - Group packages by license
  - Include/exclude copyright and license texts

- **Advanced Features**:
  - Parallel processing for batch operations
  - CycloneDX cache format for manual review
  - SPDX license identification
  - Multiple extraction engines (purl2src, upmex, oslili)

## Installation

```bash
pip install semantic-copycat-purl2notices
```

### Development Installation

```bash
git clone https://github.com/oscarvalenzuelab/semantic-copycat-purl2notices.git
cd semantic-copycat-purl2notices
pip install -e .[dev]

# Download SPDX license data
python scripts/download_spdx_licenses.py
```

## Usage

### Basic Examples

```bash
# Process a single PURL
purl2notices -i pkg:npm/express@4.0.0

# Process multiple PURLs from a file
purl2notices -i packages.txt -o NOTICE.txt

# Scan a directory for packages
purl2notices -i ./src --recursive -o NOTICE.html -f html

# Use a cache file
purl2notices -i project.cdx.json -o NOTICE.txt
```

### Advanced Usage

```bash
# Generate cache for manual review
purl2notices -i packages.txt --cache project.cache.json

# Edit the cache file manually...

# Regenerate notices from edited cache
purl2notices -i project.cache.json -o NOTICE.txt

# Custom template and configuration
purl2notices -i ./project \
  --template custom-notice.j2 \
  --config purl2notices.yaml \
  --exclude "*/test/*" \
  --parallel 8
```

### Command-Line Options

```
Options:
  -i, --input TEXT              Input (PURL, file, directory, or cache)
  -m, --mode [auto|single|kissbom|scan|cache]
                                Operation mode (auto-detected by default)
  -o, --output PATH             Output file (default: stdout)
  -f, --format [text|html]      Output format (default: text)
  -c, --cache PATH              Cache file location
  --no-cache                    Disable caching
  -t, --template PATH           Custom template file
  --config PATH                 Configuration file
  -v, --verbose                 Increase verbosity
  -p, --parallel INTEGER        Parallel workers (default: 4)
  -r, --recursive               Recursive directory scan
  -d, --max-depth INTEGER       Max scan depth (default: 10)
  -e, --exclude TEXT            Exclude patterns (multiple)
  --group-by-license            Group by license (default: true)
  --no-copyright                Exclude copyright notices
  --no-license-text             Exclude license texts
  --continue-on-error           Continue on errors
  --log-file PATH               Log file path
  --help                        Show this message and exit
```

## Configuration

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

output:
  format: html
  group_by_license: true
  include_copyright: true
  include_license_text: true

cache:
  enabled: true
  location: ".purl2notices.cache.json"
  auto_mode: true
```

## Input Formats

### KissBOM Format

Simple text file with one PURL per line:

```
pkg:npm/express@4.18.0
pkg:pypi/requests@2.28.0
pkg:maven/org.springframework/spring-core@5.3.0
# Comments are supported
pkg:cargo/serde@1.0.0
```

### Cache Format

CycloneDX JSON format for intermediate storage and manual editing:

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

## Output Examples

### Text Format

```
================================================================================
MIT
================================================================================

Packages:
  - pkg:npm/express@4.18.0
  - pkg:npm/body-parser@1.20.0

Copyright Notices:
  Copyright (c) 2009-2024 TJ Holowaychuk
  Copyright (c) 2014-2024 Douglas Wilson

License Text:
--------------------------------------------------------------------------------
MIT License

Permission is hereby granted, free of charge...
--------------------------------------------------------------------------------
```

### HTML Format

Generated HTML with styled layout, grouped licenses, and formatted text.

## Custom Templates

Create custom Jinja2 templates:

```jinja2
{% for package in packages %}
Package: {{ package.display_name }}
License: {{ ', '.join(package.license_ids) }}
{% for copyright in package.copyrights %}
  {{ copyright.statement }}
{% endfor %}
{% endfor %}
```

## API Usage

```python
from purl2notices import Purl2Notices

# Initialize processor
processor = Purl2Notices()

# Process single PURL
import asyncio
package = asyncio.run(processor.process_single_purl("pkg:npm/express@4.0.0"))

# Generate notices
notices = processor.generate_notices(
    packages=[package],
    output_format="html",
    group_by_license=True
)

print(notices)
```

## Development

### Running Tests

```bash
pytest
pytest --cov=purl2notices
```

### Code Quality

```bash
# Linting
ruff check .

# Formatting
ruff format .

# Type checking
mypy purl2notices
```

### Building

```bash
python -m build
```

## Dependencies

- `semantic-copycat-purl2src`: Package URL resolution
- `semantic-copycat-upmex`: Metadata extraction
- `semantic-copycat-oslili`: License/copyright detection
- `click`: CLI framework
- `jinja2`: Template engine
- `aiohttp`: Async HTTP client
- `packageurl-python`: PURL parsing

## License

Apache-2.0

## Author

Oscar Valenzuela B  
Email: oscar.valenzuela.b@gmail.com

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Support

For issues and questions, please use the [GitHub issue tracker](https://github.com/oscarvalenzuelab/semantic-copycat-purl2notices/issues).