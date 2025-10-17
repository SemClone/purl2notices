"""Unit tests for validators module."""

from pathlib import Path

import pytest
from purl2notices.validators import PurlValidator, FileValidator


class TestPURLValidator:
    """Test PURL validation functionality."""
    
    def test_valid_npm_purl(self):
        """Test validation of valid npm PURL."""
        purl = "pkg:npm/express@4.18.0"
        is_valid, error = PurlValidator.validate(purl)
        assert is_valid
        assert error is None
    
    def test_valid_pypi_purl(self):
        """Test validation of valid PyPI PURL."""
        purl = "pkg:pypi/django@4.2.0"
        is_valid, error = PurlValidator.validate(purl)
        assert is_valid
        assert error is None
    
    def test_valid_maven_purl(self):
        """Test validation of valid Maven PURL."""
        purl = "pkg:maven/org.springframework/spring-core@5.3.0"
        is_valid, error = PurlValidator.validate(purl)
        assert is_valid
        assert error is None
    
    def test_invalid_purl_no_version(self):
        """Test that PURL without version is invalid."""
        purl = "pkg:npm/express"
        is_valid, error = PurlValidator.validate(purl)
        assert not is_valid
        assert "version" in error.lower()
    
    def test_invalid_purl_format(self):
        """Test that malformed PURL is invalid."""
        purl = "not-a-purl"
        is_valid, error = PurlValidator.validate(purl)
        assert not is_valid
        assert error is not None
    
    def test_empty_purl(self):
        """Test that empty string is invalid."""
        purl = ""
        is_valid, error = PurlValidator.validate(purl)
        assert not is_valid
        assert error is not None
    
    def test_unsupported_ecosystem(self):
        """Test PURL with unsupported ecosystem."""
        purl = "pkg:unknown/package@1.0.0"
        is_valid, error = PurlValidator.validate(purl)
        # Should still be valid as a PURL, even if ecosystem is unknown
        assert is_valid or "ecosystem" in error.lower()


class TestFileValidator:
    """Test file validation functionality."""
    
    def test_archive_file_detection_jar(self):
        """Test detection of JAR files."""
        assert FileValidator.is_archive_file(Path("test.jar"))
        assert FileValidator.is_archive_file(Path("library.jar"))
    
    def test_archive_file_detection_python(self):
        """Test detection of Python archive files."""
        assert FileValidator.is_archive_file(Path("package.whl"))
        assert FileValidator.is_archive_file(Path("package.egg"))
        assert FileValidator.is_archive_file(Path("package.tar.gz"))
        assert FileValidator.is_archive_file(Path("package.tgz"))
    
    def test_archive_file_detection_other(self):
        """Test detection of other archive types."""
        assert FileValidator.is_archive_file(Path("package.gem"))
        assert FileValidator.is_archive_file(Path("package.nupkg"))
        assert FileValidator.is_archive_file(Path("package.crate"))
        assert FileValidator.is_archive_file(Path("package.deb"))
        assert FileValidator.is_archive_file(Path("package.rpm"))
    
    def test_non_archive_files(self):
        """Test that non-archive files are not detected."""
        assert not FileValidator.is_archive_file(Path("test.txt"))
        assert not FileValidator.is_archive_file(Path("script.py"))
        assert not FileValidator.is_archive_file(Path("config.yaml"))
    
    def test_cache_file_detection(self):
        """Test detection of cache files."""
        assert FileValidator.is_cache_file(Path("test.cdx.json"))
        assert FileValidator.is_cache_file(Path("test.cache.json"))
        assert not FileValidator.is_cache_file(Path("test.json"))
        assert not FileValidator.is_cache_file(Path("test.txt"))
    
    def test_validate_kissbom_valid(self, temp_dir):
        """Test validation of valid KissBOM file."""
        kissbom_file = temp_dir / "packages.txt"
        kissbom_file.write_text("""pkg:npm/express@4.18.0
pkg:pypi/django@4.2.0
# Comment line
pkg:maven/org.springframework/spring-core@5.3.0
""")
        
        is_valid, purls, error = FileValidator.validate_kissbom(kissbom_file)
        assert is_valid
        assert len(purls) == 3
        assert error is None
    
    def test_validate_kissbom_invalid_purl(self, temp_dir):
        """Test validation of KissBOM with invalid PURL."""
        kissbom_file = temp_dir / "invalid.txt"
        kissbom_file.write_text("""pkg:npm/express@4.18.0
not-a-valid-purl
pkg:pypi/django@4.2.0
""")
        
        is_valid, purls, error = FileValidator.validate_kissbom(kissbom_file)
        assert not is_valid
        assert error is not None
    
    def test_validate_kissbom_empty_file(self, temp_dir):
        """Test validation of empty KissBOM file."""
        kissbom_file = temp_dir / "empty.txt"
        kissbom_file.write_text("")
        
        is_valid, purls, error = FileValidator.validate_kissbom(kissbom_file)
        assert not is_valid
        assert "no valid purls" in error.lower()
    
    def test_detect_input_type_purl(self):
        """Test detection of PURL input type."""
        assert FileValidator.detect_input_type("pkg:npm/express@4.18.0") == 'purl'
    
    def test_detect_input_type_directory(self, temp_dir):
        """Test detection of directory input type."""
        assert FileValidator.detect_input_type(str(temp_dir)) == 'directory'
    
    def test_detect_input_type_cache_file(self, temp_dir):
        """Test detection of cache file input type."""
        cache_file = temp_dir / "test.cache.json"
        cache_file.write_text('{"bomFormat": "CycloneDX"}')
        assert FileValidator.detect_input_type(str(cache_file)) == 'cache'
    
    def test_detect_input_type_archive(self, temp_dir):
        """Test detection of archive file input type."""
        archive_file = temp_dir / "test.jar"
        archive_file.touch()
        assert FileValidator.detect_input_type(str(archive_file)) == 'archive'