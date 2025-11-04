"""Pytest configuration for purl2notices."""

import sys
import tempfile
from pathlib import Path

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from purl2notices.models import Package, License, Copyright


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_packages():
    """Create sample packages for testing."""
    packages = [
        Package(
            purl="pkg:npm/express@4.18.0",
            name="express",
            version="4.18.0",
            licenses=[
                License(
                    spdx_id="MIT",
                    name="MIT License",
                    text="MIT License text..."
                )
            ],
            copyrights=[
                Copyright(
                    statement="Copyright (c) 2009-2024 TJ Holowaychuk",
                    confidence=0.95
                )
            ]
        ),
        Package(
            purl="pkg:pypi/requests@2.31.0",
            name="requests",
            version="2.31.0",
            licenses=[
                License(
                    spdx_id="Apache-2.0",
                    name="Apache License 2.0",
                    text="Apache License text..."
                )
            ],
            copyrights=[
                Copyright(
                    statement="Copyright 2019 Kenneth Reitz",
                    confidence=0.90
                )
            ]
        )
    ]
    return packages


@pytest.fixture
def kissbom_file(temp_dir):
    """Create a sample KissBOM file."""
    kissbom_path = temp_dir / "packages.txt"
    kissbom_path.write_text(
        "pkg:npm/express@4.18.0\n"
        "pkg:pypi/requests@2.31.0\n"
        "pkg:maven/org.apache/commons-lang3@3.12.0\n"
    )
    return kissbom_path


@pytest.fixture
def cache_file(temp_dir):
    """Create a sample cache file."""
    import json

    cache_path = temp_dir / "test.cache.json"
    cache_data = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.6",
        "components": [
            {
                "type": "library",
                "name": "express",
                "version": "4.18.0",
                "purl": "pkg:npm/express@4.18.0",
                "licenses": [{"license": {"id": "MIT"}}]
            }
        ]
    }
    cache_path.write_text(json.dumps(cache_data, indent=2))
    return cache_path


@pytest.fixture
def overrides_file(temp_dir):
    """Create a sample overrides file."""
    import yaml

    overrides_path = temp_dir / "overrides.yaml"
    overrides_data = {
        "exclude": [
            "pkg:npm/internal-*",
            "pkg:pypi/test-*"
        ],
        "override": {
            "pkg:npm/express@4.18.0": {
                "license": "MIT",
                "copyright": "Copyright (c) 2009-2024 TJ Holowaychuk and contributors"
            }
        }
    }
    overrides_path.write_text(yaml.dump(overrides_data))
    return overrides_path