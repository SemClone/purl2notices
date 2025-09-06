"""Unit tests for cache module."""

import json
from pathlib import Path

import pytest
from purl2notices.cache import CacheManager
from purl2notices.models import Package, License, Copyright


class TestCacheManager:
    """Test CacheManager functionality."""
    
    def test_cache_manager_initialization(self, temp_dir):
        """Test CacheManager initialization."""
        cache_file = temp_dir / "test.cache.json"
        manager = CacheManager(cache_file)
        
        assert manager.cache_file == cache_file
        assert not cache_file.exists()
    
    def test_save_packages_to_cache(self, temp_dir, sample_packages):
        """Test saving packages to cache."""
        cache_file = temp_dir / "test.cache.json"
        manager = CacheManager(cache_file)
        
        manager.save(sample_packages)
        
        assert cache_file.exists()
        
        # Load and verify cache content
        with open(cache_file) as f:
            data = json.load(f)
        
        assert data["bomFormat"] == "CycloneDX"
        assert data["specVersion"] == "1.6"
        assert len(data["components"]) == len(sample_packages)
    
    def test_load_packages_from_cache(self, temp_dir, sample_packages):
        """Test loading packages from cache."""
        cache_file = temp_dir / "test.cache.json"
        manager = CacheManager(cache_file)
        
        # Save packages first
        manager.save(sample_packages)
        
        # Load packages
        loaded_packages = manager.load()
        
        assert len(loaded_packages) == len(sample_packages)
        assert all(isinstance(pkg, Package) for pkg in loaded_packages)
        
        # Verify package data
        for original, loaded in zip(sample_packages, loaded_packages):
            assert loaded.name == original.name
            assert loaded.version == original.version
            assert loaded.purl == original.purl
    
    def test_merge_packages(self, temp_dir):
        """Test merging packages with existing cache."""
        cache_file = temp_dir / "test.cache.json"
        manager = CacheManager(cache_file)
        
        # Initial packages
        initial_packages = [
            Package(
                name="express",
                version="4.18.0",
                purl="pkg:npm/express@4.18.0",
                licenses=[License(spdx_id="MIT", name="", text="")]
            )
        ]
        
        # Save initial packages
        manager.save(initial_packages)
        
        # New packages to merge
        new_packages = [
            Package(
                name="django",
                version="4.2.0",
                purl="pkg:pypi/django@4.2.0",
                licenses=[License(spdx_id="BSD-3-Clause", name="", text="")]
            ),
            # Duplicate that should be merged
            Package(
                name="express",
                version="4.18.0",
                purl="pkg:npm/express@4.18.0",
                licenses=[License(spdx_id="MIT", name="", text="")]
            )
        ]
        
        # Merge packages
        merged = manager.merge(new_packages)
        
        # Should have 2 unique packages
        assert len(merged) == 2
        purls = [pkg.purl for pkg in merged]
        assert "pkg:npm/express@4.18.0" in purls
        assert "pkg:pypi/django@4.2.0" in purls
    
    def test_save_with_merge(self, temp_dir):
        """Test that save merges with existing cache."""
        cache_file = temp_dir / "test.cache.json"
        manager = CacheManager(cache_file)
        
        # First save
        first_packages = [
            Package(
                name="package1",
                version="1.0.0",
                purl="pkg:npm/package1@1.0.0"
            )
        ]
        manager.save(first_packages)
        
        # Second save should merge
        second_packages = [
            Package(
                name="package2",
                version="2.0.0",
                purl="pkg:npm/package2@2.0.0"
            )
        ]
        manager.save(second_packages)
        
        # Load and verify both packages are present
        loaded = manager.load()
        assert len(loaded) == 2
        purls = [pkg.purl for pkg in loaded]
        assert "pkg:npm/package1@1.0.0" in purls
        assert "pkg:npm/package2@2.0.0" in purls
    
    def test_load_nonexistent_cache(self, temp_dir):
        """Test loading from nonexistent cache file."""
        cache_file = temp_dir / "nonexistent.cache.json"
        manager = CacheManager(cache_file)
        
        packages = manager.load()
        assert packages == []
    
    def test_load_invalid_cache(self, temp_dir):
        """Test loading from invalid cache file."""
        cache_file = temp_dir / "invalid.cache.json"
        cache_file.write_text("not valid json {]}")
        
        manager = CacheManager(cache_file)
        packages = manager.load()
        assert packages == []
    
    def test_cache_with_overrides(self, temp_dir, overrides_file):
        """Test cache with user overrides."""
        from purl2notices.overrides import OverrideManager
        
        cache_file = temp_dir / "test.cache.json"
        manager = CacheManager(cache_file, overrides_file)
        
        packages = [
            Package(
                name="internal-package",
                version="1.0.0",
                purl="pkg:npm/internal-package@1.0.0"
            ),
            Package(
                name="express",
                version="4.18.0",
                purl="pkg:npm/express@4.18.0"
            )
        ]
        
        manager.save(packages, apply_overrides=True)
        loaded = manager.load(apply_overrides=True)
        
        # Internal package should be excluded
        assert len(loaded) == 1
        assert loaded[0].purl == "pkg:npm/express@4.18.0"
    
    def test_cache_format_compliance(self, temp_dir, sample_package):
        """Test that cache format complies with CycloneDX."""
        cache_file = temp_dir / "test.cache.json"
        manager = CacheManager(cache_file)
        
        manager.save([sample_package])
        
        with open(cache_file) as f:
            data = json.load(f)
        
        # Check CycloneDX required fields
        assert "bomFormat" in data
        assert data["bomFormat"] == "CycloneDX"
        assert "specVersion" in data
        assert "version" in data
        assert "serialNumber" in data
        assert "metadata" in data
        assert "timestamp" in data["metadata"]
        assert "components" in data
        
        # Check component structure
        component = data["components"][0]
        assert "type" in component
        assert "name" in component
        assert "version" in component
        assert "purl" in component