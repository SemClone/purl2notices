#!/usr/bin/env python3
"""Test CLI functionality."""

from pathlib import Path
from jinja2 import Environment, FileSystemLoader

# Check template loading
template_dir = Path(__file__).parent / "purl2notices" / "templates"
print(f"Template directory: {template_dir}")
print(f"Exists: {template_dir.exists()}")
print(f"Is directory: {template_dir.is_dir()}")

if template_dir.exists():
    print(f"Contents: {list(template_dir.iterdir())}")
    
    # Try to load with Jinja2
    env = Environment(loader=FileSystemLoader(str(template_dir)))
    try:
        template = env.get_template("default.text.j2")
        print(f"✓ Successfully loaded template")
    except Exception as e:
        print(f"✗ Failed to load template: {e}")

# Also test the actual path resolution
from purl2notices.formatter import NoticeFormatter
formatter = NoticeFormatter()
print(f"\nFormatter template directory: {formatter.env.loader.searchpath if hasattr(formatter.env, 'loader') else 'No loader'}")