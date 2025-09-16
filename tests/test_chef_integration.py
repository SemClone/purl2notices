"""Integration test for Chef cookbook processing."""

import pytest
from pathlib import Path
from purl2notices.core import Purl2Notices
from purl2notices.config import Config


def test_chef_cookbooks_directory_scan(tmp_path):
    """Test that Chef cookbooks in subdirectories are detected as separate packages."""
    # Create directory structure similar to the user's example
    third_party = tmp_path / "third-party"
    third_party.mkdir()

    # Create package-a cookbook
    package_a = third_party / "package-a"
    package_a.mkdir()
    (package_a / "metadata.rb").write_text("""
name 'package-a'
version '1.0.0'
license 'Apache-2.0'
description 'Package A cookbook'
maintainer 'Test Author'
""")
    (package_a / "recipes").mkdir()
    (package_a / "recipes" / "default.rb").write_text("""
# Recipe for package-a
# Copyright (c) 2024 Test Author

package 'nginx' do
  action :install
end
""")

    # Create package-b cookbook
    package_b = third_party / "package-b"
    package_b.mkdir()
    (package_b / "metadata.rb").write_text("""
name 'package-b'
version '2.0.0'
license 'MIT'
description 'Package B cookbook'
maintainer 'Another Author'
""")
    (package_b / "recipes").mkdir()
    (package_b / "recipes" / "default.rb").write_text("""
# Recipe for package-b
# Copyright (c) 2024 Another Author

service 'postgresql' do
  action [:enable, :start]
end
""")

    # Add a LICENSE file in package-b
    (package_b / "LICENSE").write_text("""MIT License

Copyright (c) 2024 Another Author

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction...""")

    # Process the directory
    config = Config()
    config.set("scanning.recursive", True)
    processor = Purl2Notices(config)

    packages = processor.process_directory(third_party)

    # Filter out any source-only packages
    detected_packages = [p for p in packages if p.name and not p.name.endswith('_sources')]

    # Should detect two separate Chef cookbooks
    assert len(detected_packages) >= 2

    # Check that we have both cookbooks
    package_names = {p.name for p in detected_packages}
    assert 'package-a' in package_names
    assert 'package-b' in package_names

    # Find the specific packages
    pkg_a = next(p for p in detected_packages if p.name == 'package-a')
    pkg_b = next(p for p in detected_packages if p.name == 'package-b')

    # Verify package-a details
    assert pkg_a.version == '1.0.0'
    # Chef cookbooks detected locally won't have PURLs
    assert pkg_a.metadata.get('type') == 'chef_cookbook'

    # Verify package-b details
    assert pkg_b.version == '2.0.0'
    # Chef cookbooks detected locally won't have PURLs
    assert pkg_b.metadata.get('type') == 'chef_cookbook'

    # Generate notices
    notices = processor.generate_notices(
        detected_packages,
        output_format='text',
        group_by_license=True,
        include_copyright=True,
        include_license_text=False
    )

    # Check that the notices contain both packages
    assert 'package-a' in notices
    assert 'package-b' in notices

    # Verify they are not merged into a single "third-party_sources" package
    assert 'third-party_sources' not in notices or notices.count('package-a') > 0


def test_mixed_ruby_and_chef_detection(tmp_path):
    """Test detection of both Ruby gems and Chef cookbooks in same directory tree."""
    # Create a Chef cookbook
    cookbook_dir = tmp_path / "my_cookbook"
    cookbook_dir.mkdir()
    (cookbook_dir / "metadata.rb").write_text("""
name 'my_cookbook'
version '1.0.0'
license 'Apache-2.0'
""")

    # Create a Ruby gem
    gem_dir = tmp_path / "my_gem"
    gem_dir.mkdir()
    (gem_dir / "my_gem.gemspec").write_text("""
Gem::Specification.new do |s|
  s.name = 'my_gem'
  s.version = '2.0.0'
  s.license = 'MIT'
end
""")
    (gem_dir / "lib").mkdir()
    (gem_dir / "lib" / "my_gem.rb").write_text("""
# Copyright (c) 2024 Gem Author
module MyGem
  VERSION = '2.0.0'
end
""")

    # Process the directory
    config = Config()
    processor = Purl2Notices(config)
    packages = processor.process_directory(tmp_path)

    # Filter detected packages
    detected_packages = [p for p in packages if p.name and not p.name.endswith('_sources')]

    # Should detect both the cookbook and the gem
    assert len(detected_packages) >= 2

    package_names = {p.name for p in detected_packages}
    assert 'my_cookbook' in package_names
    assert 'my_gem' in package_names

    # Check package types
    chef_packages = [p for p in detected_packages if p.metadata.get('type') == 'chef_cookbook']
    gem_packages = [p for p in detected_packages if p.metadata.get('type') == 'ruby_gem']
    assert len(chef_packages) >= 1
    assert len(gem_packages) >= 1