"""Unit tests for models module."""

import pytest
import dataclasses
from purl2notices.models import Package, License, Copyright


class TestLicense:
    """Test License model."""
    
    def test_license_creation(self):
        """Test creating a License instance."""
        license = License(
            spdx_id="MIT",
            name="MIT License",
            text="MIT License text..."
        )
        assert license.spdx_id == "MIT"
        assert license.name == "MIT License"
        assert license.text == "MIT License text..."
    
    def test_license_equality(self):
        """Test License equality comparison."""
        license1 = License(spdx_id="MIT", name="MIT License", text="")
        license2 = License(spdx_id="MIT", name="MIT License", text="")
        license3 = License(spdx_id="Apache-2.0", name="Apache License 2.0", text="")
        
        assert license1 == license2
        assert license1 != license3
    



class TestCopyright:
    """Test Copyright model."""
    
    def test_copyright_creation(self):
        """Test creating a Copyright instance."""
        copyright = Copyright(
            statement="Copyright (c) 2024 Test Author",
            confidence=0.95
        )
        assert copyright.statement == "Copyright (c) 2024 Test Author"
        assert copyright.confidence == 0.95
    
    def test_copyright_default_confidence(self):
        """Test Copyright default confidence value."""
        copyright = Copyright(statement="Copyright 2024 Test")
        assert copyright.confidence == 1.0
    
    def test_copyright_equality(self):
        """Test Copyright equality comparison."""
        copyright1 = Copyright(statement="Copyright (c) 2024 Test")
        copyright2 = Copyright(statement="Copyright (c) 2024 Test")
        copyright3 = Copyright(statement="Copyright (c) 2023 Other")
        
        assert copyright1 == copyright2
        assert copyright1 != copyright3
    



class TestPackage:
    """Test Package model."""
    
    def test_package_creation(self):
        """Test creating a Package instance."""
        package = Package(
            name="test-package",
            version="1.0.0",
            purl="pkg:npm/test-package@1.0.0",
            licenses=[License(spdx_id="MIT", name="", text="")],
            copyrights=[Copyright(statement="Copyright 2024 Test")]
        )
        
        assert package.name == "test-package"
        assert package.version == "1.0.0"
        assert package.purl == "pkg:npm/test-package@1.0.0"
        assert len(package.licenses) == 1
        assert len(package.copyrights) == 1
    
    def test_package_display_name(self):
        """Test Package display_name property."""
        package = Package(
            name="express",
            version="4.18.0",
            purl="pkg:npm/express@4.18.0"
        )
        
        assert package.display_name == "pkg:npm/express@4.18.0"
    
    def test_package_display_name_with_source(self):
        """Test Package display_name with source_path."""
        package = Package(
            name="library",
            version="1.0.0",
            purl="pkg:maven/com.example/library@1.0.0",
            source_path="/path/to/library.jar"
        )
        
        assert package.display_name == "pkg:maven/com.example/library@1.0.0 (from library.jar)"
    
    def test_package_license_ids(self):
        """Test Package license_ids property."""
        package = Package(
            name="test",
            version="1.0.0",
            licenses=[
                License(spdx_id="MIT", name="", text=""),
                License(spdx_id="Apache-2.0", name="", text="")
            ]
        )
        
        assert package.license_ids == ["MIT", "Apache-2.0"]
    
    def test_package_has_licenses(self):
        """Test Package has_licenses property."""
        package_with_licenses = Package(
            name="test",
            version="1.0.0",
            licenses=[License(spdx_id="MIT", name="", text="")]
        )
        
        package_without_licenses = Package(
            name="test",
            version="1.0.0",
            licenses=[]
        )
        
        assert package_with_licenses.has_licenses
        assert not package_without_licenses.has_licenses
    
