# PURL2NOTICES - Package URL (PURL) to Legal Notices

Generate legal notices (attribution to authors and copyrights) for software packages.

## Features

- **Multi-format support**: Process PURLs, archives (JAR/WAR/WHL), directories, and cache files
- **12+ ecosystems**: npm, PyPI, Maven, Cargo, Go, NuGet, Conda, and more
- **Smart extraction**: Uses multiple engines (purl2src, upmex, oslili) for accurate license detection
- **Flexible output**: Text/HTML with customizable Jinja2 templates
- **Cache management**: CycloneDX format with merge capabilities
- **Override system**: Customize licenses and filter unwanted content

## Installation

```bash
pip install semantic-copycat-purl2notices
```

For development:
```bash
git clone https://github.com/oscarvalenzuelab/semantic-copycat-purl2notices.git
cd semantic-copycat-purl2notices
pip install -e .[dev]
```

## Quick Start

```bash
# Process a single package
purl2notices -i pkg:npm/express@4.0.0

# Process an archive file
purl2notices -i library.jar -o NOTICE.txt

# Scan a directory
purl2notices -i ./src --recursive -o NOTICE.html -f html

# Process multiple packages
echo "pkg:npm/express@4.0.0" > packages.txt
echo "pkg:pypi/django@4.2.0" >> packages.txt
purl2notices -i packages.txt -o NOTICE.txt
```

## Documentation

- **[User Guide](docs/user-guide.md)** - Complete usage documentation
- **[Examples](docs/examples.md)** - Detailed examples and use cases
- **[Configuration](docs/configuration.md)** - Configuration options and customization

## Common Use Cases

### Generate notices for a project

```bash
purl2notices -i ./my-project --recursive --cache project.cache.json -o NOTICE.txt
```

### Merge notices from multiple sources

```bash
purl2notices -i cache1.json --merge-cache cache2.json -o combined-NOTICE.txt
```

### Customize output with overrides

```bash
purl2notices -i packages.txt --overrides custom.json -o NOTICE.txt
```

## API Usage

```python
from purl2notices import Purl2Notices
import asyncio

processor = Purl2Notices()
package = asyncio.run(processor.process_single_purl("pkg:npm/express@4.0.0"))
notices = processor.generate_notices([package])
print(notices)
```

