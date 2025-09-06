"""Pytest configuration and shared fixtures."""

import json
import tempfile
from pathlib import Path
from typing import Generator

import pytest
from purl2notices.models import Package, License, Copyright


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_package() -> Package:
    """Create a sample package for testing."""
    return Package(
        name="test-package",
        version="1.0.0",
        purl="pkg:npm/test-package@1.0.0",
        licenses=[License(spdx_id="MIT", name="MIT License", text="MIT License text...")],
        copyrights=[Copyright(statement="Copyright (c) 2024 Test Author")],
        homepage="https://example.com",
        description="Test package description"
    )


@pytest.fixture
def sample_packages() -> list[Package]:
    """Create multiple sample packages for testing."""
    return [
        Package(
            name="express",
            version="4.18.0",
            purl="pkg:npm/express@4.18.0",
            licenses=[License(spdx_id="MIT", name="MIT License", text="")],
            copyrights=[Copyright(statement="Copyright (c) 2009-2024 TJ Holowaychuk")]
        ),
        Package(
            name="django",
            version="4.2.0",
            purl="pkg:pypi/django@4.2.0",
            licenses=[License(spdx_id="BSD-3-Clause", name="BSD 3-Clause License", text="")],
            copyrights=[Copyright(statement="Copyright (c) Django Software Foundation")]
        ),
        Package(
            name="spring-core",
            version="5.3.0",
            purl="pkg:maven/org.springframework/spring-core@5.3.0",
            licenses=[License(spdx_id="Apache-2.0", name="Apache License 2.0", text="")],
            copyrights=[Copyright(statement="Copyright (c) VMware, Inc.")]
        )
    ]


@pytest.fixture
def kissbom_file(temp_dir: Path) -> Path:
    """Create a KissBOM file for testing."""
    kissbom_path = temp_dir / "packages.txt"
    kissbom_path.write_text("""# Test KissBOM file
pkg:npm/express@4.18.0
pkg:pypi/django@4.2.0
pkg:maven/org.springframework/spring-core@5.3.0

# Comments should be ignored
pkg:cargo/serde@1.0.0
""")
    return kissbom_path


@pytest.fixture
def cache_file(temp_dir: Path, sample_packages: list[Package]) -> Path:
    """Create a CycloneDX cache file for testing."""
    cache_path = temp_dir / "test.cache.json"
    cache_data = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.6",
        "components": [
            {
                "type": "library",
                "name": pkg.name,
                "version": pkg.version,
                "purl": pkg.purl,
                "licenses": [
                    {"license": {"id": lic.spdx_id, "name": lic.name}}
                    for lic in pkg.licenses
                ],
                "copyright": " ".join(c.statement for c in pkg.copyrights)
            }
            for pkg in sample_packages
        ]
    }
    cache_path.write_text(json.dumps(cache_data, indent=2))
    return cache_path


@pytest.fixture
def overrides_file(temp_dir: Path) -> Path:
    """Create an overrides configuration file for testing."""
    overrides_path = temp_dir / "overrides.json"
    overrides_data = {
        "exclude_purls": [
            "pkg:npm/internal-package@1.0.0"
        ],
        "license_overrides": {
            "pkg:npm/ambiguous@1.0.0": ["MIT"]
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
            "pkg:npm/noisy@1.0.0": ["Generated copyright"]
        }
    }
    overrides_path.write_text(json.dumps(overrides_data, indent=2))
    return overrides_path


@pytest.fixture
def config_file(temp_dir: Path) -> Path:
    """Create a configuration file for testing."""
    config_path = temp_dir / "config.yaml"
    config_path.write_text("""general:
  verbose: 1
  parallel_workers: 2
  timeout: 30

scanning:
  recursive: true
  max_depth: 5
  exclude_patterns:
    - "*/node_modules/*"
    - "*/.git/*"

output:
  format: text
  group_by_license: true
  include_copyright: true
  include_license_text: false

cache:
  enabled: true
  location: "test.cache.json"
""")
    return config_path