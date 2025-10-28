# Examples

## Basic Usage Examples

### Processing Single Packages

```bash
# Process a single PURL
purl2notices -i pkg:npm/express@4.0.0

# Process an archive file (JAR, WAR, WHL, etc.)
purl2notices -i library.jar -o NOTICE.txt

# Process a Python wheel
purl2notices -i package-1.0.0-py3-none-any.whl
```

### Batch Processing

```bash
# Process multiple PURLs from a file
purl2notices -i packages.txt -o NOTICE.txt

# With parallel processing
purl2notices -i packages.txt --parallel 8 -o NOTICE.txt
```

### Directory Scanning

```bash
# Basic directory scan
purl2notices -i ./src --recursive -o NOTICE.html -f html

# With exclusions and depth limit
purl2notices -i ./project \
  --recursive \
  --max-depth 5 \
  --exclude "*/test/*" \
  --exclude "*/node_modules/*"
```

## Advanced Examples

### Cache Management

```bash
# Generate cache for manual review
purl2notices -i packages.txt --cache project.cache.json

# Edit the cache file manually to fix licenses or copyrights
vim project.cache.json

# Regenerate notices from edited cache
purl2notices -i project.cache.json -o NOTICE.txt

# Merge multiple cache files
purl2notices -i cache1.json \
  --merge-cache cache2.json \
  --merge-cache cache3.json \
  -o combined-notice.txt
```

### Custom Templates

Create a custom template `custom-notice.j2`:

```jinja2
# Legal Notices

{% for license_id, packages in packages_by_license.items() %}
## {{ license_id }}

### Packages
{% for package in packages %}
- {{ package.display_name }}
{% endfor %}

{% if include_copyright %}
### Copyright Notices
{% for package in packages %}
{% for copyright in package.copyrights %}
- {{ copyright.statement }}
{% endfor %}
{% endfor %}
{% endif %}

{% if include_license_text and license_id in license_texts %}
### License Text
{{ license_texts[license_id] }}
{% endif %}
{% endfor %}
```

Use the template:

```bash
purl2notices -i packages.txt --template custom-notice.j2 -o NOTICE.md
```

### Using Overrides

Create `purl2notices.overrides.json`:

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

Apply overrides:

```bash
purl2notices -i packages.txt \
  --overrides purl2notices.overrides.json \
  -o NOTICE.txt
```

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Generate Notices
on: [push]

jobs:
  notices:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Install purl2notices
        run: pip install purl2notices
      
      - name: Generate notices
        run: |
          purl2notices -i . \
            --recursive \
            --cache build/notices.cache.json \
            --continue-on-error \
            -o dist/NOTICE.txt
      
      - name: Upload notices
        uses: actions/upload-artifact@v3
        with:
          name: legal-notices
          path: dist/NOTICE.txt
```

### Shell Script Example

```bash
#!/bin/bash
# generate-notices.sh

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

# Generate final notices
purl2notices -i build/notices.cache.json \
  -o dist/NOTICE.txt \
  --no-license-text
```

## Multi-Repository Project

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

## Complete Project Scan

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

# Review and edit cache if needed
# vim project.cache.json

# Generate final notices with custom template
purl2notices -i project.cache.json \
  --overrides overrides.json \
  --template custom-notice.j2 \
  -o NOTICE.html \
  -f html
```