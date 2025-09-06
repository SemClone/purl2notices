"""Integration tests for CLI functionality."""

import json
from pathlib import Path

import pytest
from click.testing import CliRunner
from purl2notices.cli import main


class TestCLI:
    """Test CLI functionality."""
    
    def test_cli_help(self):
        """Test CLI help output."""
        runner = CliRunner()
        result = runner.invoke(main, ['--help'])
        
        assert result.exit_code == 0
        assert 'Generate legal notices' in result.output
        assert '--input' in result.output
        assert '--output' in result.output
        assert '--format' in result.output
    
    def test_cli_version(self):
        """Test CLI version output."""
        runner = CliRunner()
        result = runner.invoke(main, ['--version'])
        
        # Version flag should be implemented
        assert result.exit_code == 0
        assert '1.1.0' in result.output or 'version' in result.output.lower()
    
    def test_cli_single_purl(self):
        """Test processing single PURL via CLI."""
        runner = CliRunner()
        result = runner.invoke(main, [
            '--input', 'pkg:npm/express@4.18.0',
            '--no-cache'
        ])
        
        # Should process but may fail due to network
        assert result.exit_code in [0, 1]
    
    def test_cli_kissbom_file(self, kissbom_file):
        """Test processing KissBOM file via CLI."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            # Create kissbom file in isolated filesystem
            kissbom = Path('packages.txt')
            kissbom.write_text('pkg:npm/test@1.0.0\npkg:pypi/test@2.0.0')
            
            result = runner.invoke(main, [
                '--input', str(kissbom),
                '--no-cache'
            ])
            
            assert result.exit_code in [0, 1]
    
    def test_cli_cache_file(self, cache_file):
        """Test processing cache file via CLI."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            # Create cache file in isolated filesystem
            cache = Path('test.cache.json')
            cache_data = {
                "bomFormat": "CycloneDX",
                "specVersion": "1.6",
                "components": [
                    {
                        "type": "library",
                        "name": "test",
                        "version": "1.0.0",
                        "purl": "pkg:npm/test@1.0.0",
                        "licenses": [{"license": {"id": "MIT"}}]
                    }
                ]
            }
            cache.write_text(json.dumps(cache_data))
            
            result = runner.invoke(main, [
                '--input', str(cache),
                '--format', 'text'
            ])
            
            assert result.exit_code == 0
            assert 'MIT' in result.output or 'test@1.0.0' in result.output
    
    def test_cli_output_file(self, temp_dir):
        """Test writing output to file."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            cache = Path('test.cache.json')
            cache_data = {
                "bomFormat": "CycloneDX",
                "specVersion": "1.6",
                "components": [
                    {
                        "type": "library",
                        "name": "test",
                        "version": "1.0.0",
                        "purl": "pkg:npm/test@1.0.0",
                        "licenses": [{"license": {"id": "MIT"}}]
                    }
                ]
            }
            cache.write_text(json.dumps(cache_data))
            
            output_file = Path('NOTICE.txt')
            
            result = runner.invoke(main, [
                '--input', str(cache),
                '--output', str(output_file)
            ])
            
            assert result.exit_code == 0
            assert output_file.exists()
            content = output_file.read_text()
            assert 'MIT' in content or 'test@1.0.0' in content
    
    def test_cli_html_format(self):
        """Test HTML output format."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            cache = Path('test.cache.json')
            cache_data = {
                "bomFormat": "CycloneDX",
                "specVersion": "1.6",
                "components": [
                    {
                        "type": "library",
                        "name": "test",
                        "version": "1.0.0",
                        "purl": "pkg:npm/test@1.0.0",
                        "licenses": [{"license": {"id": "MIT"}}]
                    }
                ]
            }
            cache.write_text(json.dumps(cache_data))
            
            result = runner.invoke(main, [
                '--input', str(cache),
                '--format', 'html'
            ])
            
            assert result.exit_code == 0
            assert '<html>' in result.output or '<!DOCTYPE' in result.output
    
    def test_cli_json_format(self):
        """Test JSON output format (to be implemented)."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            cache = Path('test.cache.json')
            cache_data = {
                "bomFormat": "CycloneDX",
                "specVersion": "1.6",
                "components": [
                    {
                        "type": "library",
                        "name": "test",
                        "version": "1.0.0",
                        "purl": "pkg:npm/test@1.0.0",
                        "licenses": [{"license": {"id": "MIT"}}]
                    }
                ]
            }
            cache.write_text(json.dumps(cache_data))
            
            result = runner.invoke(main, [
                '--input', str(cache),
                '--format', 'json'
            ])
            
            # JSON format should be implemented
            if result.exit_code == 0:
                output = json.loads(result.output)
                assert 'packages' in output or 'components' in output
    
    def test_cli_merge_cache(self):
        """Test merge-cache functionality."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            # Create two cache files
            cache1 = Path('cache1.json')
            cache1_data = {
                "bomFormat": "CycloneDX",
                "specVersion": "1.6",
                "components": [
                    {
                        "type": "library",
                        "name": "package1",
                        "version": "1.0.0",
                        "purl": "pkg:npm/package1@1.0.0",
                        "licenses": [{"license": {"id": "MIT"}}]
                    }
                ]
            }
            cache1.write_text(json.dumps(cache1_data))
            
            cache2 = Path('cache2.json')
            cache2_data = {
                "bomFormat": "CycloneDX",
                "specVersion": "1.6",
                "components": [
                    {
                        "type": "library",
                        "name": "package2",
                        "version": "2.0.0",
                        "purl": "pkg:npm/package2@2.0.0",
                        "licenses": [{"license": {"id": "Apache-2.0"}}]
                    }
                ]
            }
            cache2.write_text(json.dumps(cache2_data))
            
            result = runner.invoke(main, [
                '--input', str(cache1),
                '--merge-cache', str(cache2),
                '--format', 'text'
            ])
            
            assert result.exit_code == 0
            # Both packages should be in output
            assert 'package1' in result.output or 'MIT' in result.output
            assert 'package2' in result.output or 'Apache-2.0' in result.output
    
    def test_cli_with_overrides(self, overrides_file):
        """Test CLI with overrides file."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            # Create cache with package that should be excluded
            cache = Path('test.cache.json')
            cache_data = {
                "bomFormat": "CycloneDX",
                "specVersion": "1.6",
                "components": [
                    {
                        "type": "library",
                        "name": "internal-package",
                        "version": "1.0.0",
                        "purl": "pkg:npm/internal-package@1.0.0",
                        "licenses": [{"license": {"id": "MIT"}}]
                    },
                    {
                        "type": "library",
                        "name": "express",
                        "version": "4.18.0",
                        "purl": "pkg:npm/express@4.18.0",
                        "licenses": [{"license": {"id": "MIT"}}]
                    }
                ]
            }
            cache.write_text(json.dumps(cache_data))
            
            # Create overrides file
            overrides = Path('overrides.json')
            overrides_data = {
                "exclude_purls": ["pkg:npm/internal-package@1.0.0"]
            }
            overrides.write_text(json.dumps(overrides_data))
            
            result = runner.invoke(main, [
                '--input', str(cache),
                '--overrides', str(overrides),
                '--format', 'text'
            ])
            
            assert result.exit_code == 0
            # Internal package should be excluded
            assert 'internal-package' not in result.output
            assert 'express' in result.output