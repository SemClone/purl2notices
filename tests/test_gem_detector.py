"""Tests for Ruby Gem and Chef cookbook detector."""

import pytest
from pathlib import Path
from purl2notices.detectors.gem import GemDetector


@pytest.fixture
def gem_detector():
    """Create a GemDetector instance."""
    return GemDetector()


@pytest.fixture
def temp_dir(tmp_path):
    """Create a temporary directory with test files."""
    return tmp_path


def test_detect_chef_cookbook_metadata_rb(gem_detector, temp_dir):
    """Test detection of Chef cookbook from metadata.rb."""
    metadata_rb = temp_dir / "metadata.rb"
    metadata_rb.write_text("""
name 'my_cookbook'
maintainer 'The Authors'
maintainer_email 'you@example.com'
license 'Apache-2.0'
description 'Installs/Configures my_cookbook'
version '1.2.3'
chef_version '>= 14.0' if respond_to?(:chef_version)

depends 'java'
depends 'nginx', '~> 2.7'
""")

    result = gem_detector.detect_from_file(metadata_rb)

    assert result.detected
    assert result.package_type == 'chef'
    assert result.name == 'my_cookbook'
    assert result.version == '1.2.3'
    assert result.purl is None  # Local cookbooks don't get PURLs
    assert result.metadata['license'] == 'Apache-2.0'
    assert result.metadata['maintainer'] == 'The Authors'
    assert 'java' in result.metadata['dependencies']


def test_detect_chef_cookbook_metadata_json(gem_detector, temp_dir):
    """Test detection of Chef cookbook from metadata.json."""
    metadata_json = temp_dir / "metadata.json"
    metadata_json.write_text("""{
    "name": "my_cookbook",
    "version": "2.0.0",
    "license": "MIT",
    "maintainer": "Test Author",
    "description": "Test cookbook",
    "dependencies": {
        "apache2": ">= 0.0.0",
        "mysql": "~> 8.0"
    }
}""")

    result = gem_detector.detect_from_file(metadata_json)

    assert result.detected
    assert result.package_type == 'chef'
    assert result.name == 'my_cookbook'
    assert result.version == '2.0.0'
    assert result.purl is None  # Local cookbooks don't get PURLs
    assert result.metadata['license'] == 'MIT'
    assert 'apache2' in result.metadata['dependencies']


def test_detect_ruby_gemspec(gem_detector, temp_dir):
    """Test detection of Ruby gem from gemspec."""
    gemspec = temp_dir / "my_gem.gemspec"
    gemspec.write_text("""
Gem::Specification.new do |s|
  s.name        = 'my_gem'
  s.version     = '0.1.0'
  s.license     = 'BSD-3-Clause'
  s.summary     = 'A test gem'
  s.homepage    = 'https://example.com/my_gem'
  s.authors     = ['John Doe', 'Jane Smith']
  s.files       = Dir['lib/**/*']
end
""")

    result = gem_detector.detect_from_file(gemspec)

    assert result.detected
    assert result.package_type == 'gem'
    assert result.name == 'my_gem'
    assert result.version == '0.1.0'
    assert result.purl == 'pkg:gem/my_gem@0.1.0'
    assert result.metadata['license'] == 'BSD-3-Clause'
    assert result.metadata['homepage'] == 'https://example.com/my_gem'
    assert 'John Doe' in result.metadata['authors']


def test_detect_multiple_chef_cookbooks_in_directory(gem_detector, temp_dir):
    """Test detection of multiple Chef cookbooks in subdirectories."""
    # Create first cookbook
    cookbook1_dir = temp_dir / "cookbook1"
    cookbook1_dir.mkdir()
    (cookbook1_dir / "metadata.rb").write_text("""
name 'cookbook1'
version '1.0.0'
license 'Apache-2.0'
""")

    # Create second cookbook
    cookbook2_dir = temp_dir / "cookbook2"
    cookbook2_dir.mkdir()
    (cookbook2_dir / "metadata.rb").write_text("""
name 'cookbook2'
version '2.0.0'
license 'MIT'
""")

    # Create a Ruby gem
    gem_dir = temp_dir / "my_gem"
    gem_dir.mkdir()
    (gem_dir / "my_gem.gemspec").write_text("""
Gem::Specification.new do |s|
  s.name = 'my_gem'
  s.version = '1.0.0'
  s.license = 'BSD'
end
""")

    results = gem_detector.detect_from_directory(temp_dir)

    # Should detect all three packages
    assert len(results) == 3

    # Check we have both cookbooks and the gem
    names = {r.name for r in results}
    assert 'cookbook1' in names
    assert 'cookbook2' in names
    assert 'my_gem' in names

    # Check package types
    chef_results = [r for r in results if r.package_type == 'chef']
    gem_results = [r for r in results if r.package_type == 'gem']
    assert len(chef_results) == 2
    assert len(gem_results) == 1


def test_gemfile_detection(gem_detector, temp_dir):
    """Test that Gemfile is detected but doesn't create a package."""
    gemfile = temp_dir / "Gemfile"
    gemfile.write_text("""
source 'https://rubygems.org'

gem 'rails', '~> 6.0'
gem 'pg', '>= 0.18', '< 2.0'
""")

    result = gem_detector.detect_from_file(gemfile)

    # Gemfile should be detected but not have package info
    assert result.detected
    assert result.package_type == 'gem'
    assert result.name is None  # Gemfile doesn't define a package
    assert result.version is None


def test_no_detection_for_non_ruby_files(gem_detector, temp_dir):
    """Test that non-Ruby files are not detected."""
    python_file = temp_dir / "setup.py"
    python_file.write_text("# Python setup file")

    result = gem_detector.detect_from_file(python_file)

    assert not result.detected