# PURL2NOTICES - Package URL to Legal Notices Generator

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![PyPI version](https://img.shields.io/pypi/v/purl2notices.svg)](https://pypi.org/project/purl2notices/)

Generate comprehensive legal notices and attribution documentation from Package URLs (PURLs). Automatically extracts copyright and license information from packages across 12+ ecosystems, producing customizable text and HTML output for compliance documentation.

## Features

- **Multi-Format Input**: Process PURLs, archives (JAR/WAR/WHL), directories, and cache files
- **12+ Ecosystem Support**: NPM, PyPI, Maven, Cargo, Go, NuGet, Conda, and more
- **Smart License Detection**: Multiple engines (purl2src, upmex, osslili) for accurate extraction
- **SEMCL.ONE Integration**: Works seamlessly with src2purl, osslili, and ecosystem tools

## Installation

```bash
pip install purl2notices
```

For development:
```bash
git clone https://github.com/SemClone/purl2notices.git
cd purl2notices
pip install -e .
```

## Quick Start

```bash
# Generate notices for a single package
purl2notices -i pkg:npm/express@4.0.0

# Process multiple packages from file
purl2notices -i packages.txt -o NOTICE.txt

# Scan directory recursively
purl2notices -i ./src --recursive -o NOTICE.html -f html
```

## Usage

### CLI Usage

```bash
# Basic notice generation
purl2notices -i pkg:npm/express@4.0.0 -o NOTICE.txt

# Process JAR/WAR archives
purl2notices -i library.jar -o NOTICE.txt

# Scan directory with caching
purl2notices -i ./project --recursive --cache project.cache.json -o NOTICE.txt

# Merge multiple cache files
purl2notices -i cache1.json --merge-cache cache2.json -o combined-NOTICE.txt

# HTML output with custom template
purl2notices -i packages.txt -o NOTICE.html -f html --template custom.jinja2

# Apply license overrides
purl2notices -i packages.txt --overrides custom.json -o NOTICE.txt
```

### Python API

```python
from purl2notices import Purl2Notices
import asyncio

# Initialize processor
processor = Purl2Notices()

# Process single package
package = asyncio.run(processor.process_single_purl("pkg:npm/express@4.0.0"))

# Generate notices
notices = processor.generate_notices([package])
print(notices)

# Custom configuration
processor = Purl2Notices(
    output_format="html",
    template_path="custom_template.jinja2"
)
```

## Supported Input Types

### Package URLs (PURLs)

```bash
# NPM packages
purl2notices -i pkg:npm/express@4.0.0

# Python packages
purl2notices -i pkg:pypi/django@4.2.0

# Maven artifacts
purl2notices -i pkg:maven/org.apache.commons/commons-lang3@3.12.0

# Multiple PURLs from file
echo "pkg:npm/express@4.0.0" > packages.txt
echo "pkg:pypi/django@4.2.0" >> packages.txt
purl2notices -i packages.txt
```

### Archive Files

```bash
# Java archives
purl2notices -i application.jar
purl2notices -i webapp.war

# Python wheels
purl2notices -i package-1.0.0-py3-none-any.whl

# Process multiple archives
purl2notices -i libs/*.jar -o NOTICE.txt
```

### Directories

```bash
# Scan current directory
purl2notices -i . -o NOTICE.txt

# Recursive scan with specific patterns
purl2notices -i ./src --recursive --include "*.py" -o NOTICE.txt

# Exclude patterns
purl2notices -i ./project --recursive --exclude "test/*" -o NOTICE.txt
```

### Cache Files

```bash
# Use CycloneDX cache
purl2notices -i project.cache.json -o NOTICE.txt

# Merge multiple caches
purl2notices -i cache1.json --merge-cache cache2.json --merge-cache cache3.json
```

## Output Formats

### Text Format (Default)

```text
================================================================================
express 4.0.0
--------------------------------------------------------------------------------
Copyright (c) 2009-2014 TJ Holowaychuk <tj@vision-media.ca>
Copyright (c) 2013-2014 Roman Shtylman <shtylman+expressjs@gmail.com>
Copyright (c) 2014-2015 Douglas Christopher Wilson <doug@somethingdoug.com>

MIT License
[Full license text...]
================================================================================
```

### HTML Format

```bash
# Generate HTML with default template
purl2notices -i packages.txt -o NOTICE.html -f html

# Use custom Jinja2 template
purl2notices -i packages.txt -o NOTICE.html -f html --template custom.jinja2
```

## Configuration

### License Overrides

Create a JSON file to override detected licenses:

```json
{
  "pkg:npm/express@4.0.0": {
    "license": "MIT",
    "copyright": "Copyright (c) Express Authors"
  }
}
```

Apply overrides:
```bash
purl2notices -i packages.txt --overrides overrides.json -o NOTICE.txt
```

### Custom Templates

Create custom Jinja2 templates for HTML output:

```html
<!DOCTYPE html>
<html>
<head><title>Legal Notices</title></head>
<body>
  {% for package in packages %}
    <h2>{{ package.name }} {{ package.version }}</h2>
    <p>{{ package.copyright }}</p>
    <pre>{{ package.license_text }}</pre>
  {% endfor %}
</body>
</html>
```

### Environment Variables

```bash
# Set default output format
export PURL2NOTICES_FORMAT=html

# Set default template path
export PURL2NOTICES_TEMPLATE=/path/to/template.jinja2

# Enable debug logging
export PURL2NOTICES_DEBUG=true
```

## Integration with SEMCL.ONE

PURL2NOTICES is a core component of the SEMCL.ONE ecosystem:

- Works with **src2purl** for package identification from source
- Uses **osslili** for enhanced license detection
- Integrates with **upmex** for package metadata extraction
- Complements **ospac** for policy compliance evaluation
- Supports **purl2src** for source code retrieval

### Complete Workflow Example

```bash
# 1. Identify package from source
src2purl ./project > project.purl

# 2. Generate legal notices
purl2notices -i project.purl -o NOTICE.txt

# 3. Validate compliance
ospac evaluate NOTICE.txt --policy compliance.yaml
```

## Advanced Features

### Batch Processing

```bash
# Process large lists efficiently
purl2notices -i packages.txt --batch-size 20 --workers 4 -o NOTICE.txt
```

### Filtering and Exclusions

```bash
# Exclude specific packages
purl2notices -i packages.txt --exclude-purl "pkg:npm/test-*" -o NOTICE.txt

# Include only specific licenses
purl2notices -i packages.txt --include-license MIT --include-license Apache-2.0
```

### Cache Management

```bash
# Generate cache for later use
purl2notices -i ./project --recursive --cache-only -o project.cache.json

# Update existing cache
purl2notices -i new-packages.txt --update-cache project.cache.json

# Clear cache
purl2notices --clear-cache
```

## Documentation

- [User Guide](docs/user-guide.md) - Comprehensive usage documentation
- [Examples](docs/examples.md) - Detailed examples and use cases
- [Configuration](docs/configuration.md) - Configuration options and customization

## Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for details on:
- Code of conduct
- Development setup
- Submitting pull requests
- Reporting issues

## Support

For support and questions:
- [GitHub Issues](https://github.com/SemClone/purl2notices/issues) - Bug reports and feature requests
- [Documentation](https://github.com/SemClone/purl2notices) - Complete project documentation
- [SEMCL.ONE Community](https://semcl.one) - Ecosystem support and discussions

## License

Apache License 2.0 - see [LICENSE](LICENSE) file for details.

## Authors

See [AUTHORS.md](AUTHORS.md) for a list of contributors.

---

*Part of the [SEMCL.ONE](https://semcl.one) ecosystem for comprehensive OSS compliance and code analysis.*