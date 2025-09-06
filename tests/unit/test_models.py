"""Unit tests for models module."""

import pytest
from purl2notices.models import Package, License, Copyright


class TestLicense:
    """Test License model."""
    
    def test_license_creation(self):
        """Test creating a License instance."""
        license = License(
            id="MIT",
            name="MIT License",
            text="MIT License text..."
        )
        assert license.id == "MIT"
        assert license.name == "MIT License"
        assert license.text == "MIT License text..."
    
    def test_license_equality(self):
        """Test License equality comparison."""
        license1 = License(id="MIT", name="MIT License")
        license2 = License(id="MIT", name="MIT License")
        license3 = License(id="Apache-2.0", name="Apache License 2.0")
        
        assert license1 == license2
        assert license1 != license3
    
    def test_license_dict_conversion(self):
        """Test License to_dict conversion."""
        license = License(
            id="MIT",
            name="MIT License",
            text="MIT text"
        )
        
        data = license.to_dict()
        assert data["id"] == "MIT"
        assert data["name"] == "MIT License"
        assert data["text"] == "MIT text"
    
    def test_license_from_dict(self):
        """Test License from_dict creation."""
        data = {
            "id": "Apache-2.0",
            "name": "Apache License 2.0",
            "text": "Apache text"
        }
        
        license = License.from_dict(data)
        assert license.id == "Apache-2.0"
        assert license.name == "Apache License 2.0"
        assert license.text == "Apache text"


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
    
    def test_copyright_dict_conversion(self):
        """Test Copyright to_dict conversion."""
        copyright = Copyright(
            statement="Copyright (c) 2024 Test",
            confidence=0.9
        )
        
        data = copyright.to_dict()
        assert data["statement"] == "Copyright (c) 2024 Test"
        assert data["confidence"] == 0.9


class TestPackage:
    """Test Package model."""
    
    def test_package_creation(self):
        """Test creating a Package instance."""
        package = Package(
            name="test-package",
            version="1.0.0",
            purl="pkg:npm/test-package@1.0.0",
            licenses=[License(id="MIT")],
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
        
        assert package.display_name == "express@4.18.0"
    
    def test_package_display_name_with_source(self):
        """Test Package display_name with source_path."""
        package = Package(
            name="library",
            version="1.0.0",
            purl="pkg:maven/com.example/library@1.0.0",
            source_path="/path/to/library.jar"
        )
        
        assert package.display_name == "library@1.0.0 (from library.jar)"
    
    def test_package_license_ids(self):
        """Test Package license_ids property."""
        package = Package(
            name="test",
            version="1.0.0",
            licenses=[
                License(id="MIT"),
                License(id="Apache-2.0")
            ]
        )
        
        assert package.license_ids == ["MIT", "Apache-2.0"]
    
    def test_package_has_licenses(self):
        """Test Package has_licenses property."""
        package_with_licenses = Package(
            name="test",
            version="1.0.0",
            licenses=[License(id="MIT")]
        )
        
        package_without_licenses = Package(
            name="test",
            version="1.0.0",
            licenses=[]
        )
        
        assert package_with_licenses.has_licenses
        assert not package_without_licenses.has_licenses
    
    def test_package_dict_conversion(self):
        """Test Package to_dict conversion."""
        package = Package(
            name="test",
            version="1.0.0",
            purl="pkg:npm/test@1.0.0",
            licenses=[License(id="MIT")],
            copyrights=[Copyright(statement="Copyright 2024")],
            homepage="https://example.com",
            description="Test package"
        )
        
        data = package.to_dict()
        assert data["name"] == "test"
        assert data["version"] == "1.0.0"
        assert data["purl"] == "pkg:npm/test@1.0.0"
        assert len(data["licenses"]) == 1
        assert len(data["copyrights"]) == 1
        assert data["homepage"] == "https://example.com"
        assert data["description"] == "Test package"
    
    def test_package_from_dict(self):
        """Test Package from_dict creation."""
        data = {
            "name": "test",
            "version": "2.0.0",
            "purl": "pkg:pypi/test@2.0.0",
            "licenses": [{"id": "BSD-3-Clause"}],
            "copyrights": [{"statement": "Copyright 2024 Test"}],
            "homepage": "https://test.com"
        }
        
        package = Package.from_dict(data)
        assert package.name == "test"
        assert package.version == "2.0.0"
        assert package.purl == "pkg:pypi/test@2.0.0"
        assert len(package.licenses) == 1
        assert package.licenses[0].id == "BSD-3-Clause"
        assert len(package.copyrights) == 1
        assert package.homepage == "https://test.com"
    
    def test_package_equality(self):
        """Test Package equality based on PURL."""
        package1 = Package(
            name="test",
            version="1.0.0",
            purl="pkg:npm/test@1.0.0"
        )
        
        package2 = Package(
            name="test",
            version="1.0.0",
            purl="pkg:npm/test@1.0.0"
        )
        
        package3 = Package(
            name="other",
            version="1.0.0",
            purl="pkg:npm/other@1.0.0"
        )
        
        assert package1 == package2
        assert package1 != package3