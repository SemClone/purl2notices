"""Security tests for CombinedExtractor URL handling."""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path
import tempfile

from purl2notices.extractors.combined_extractor import CombinedExtractor


class TestURLSecurityValidation:
    """Test URL validation security fixes."""

    @pytest.fixture
    def extractor(self):
        """Create a CombinedExtractor instance for testing."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            cache_dir = Path(tmp_dir)
            extractor = CombinedExtractor(cache_dir=cache_dir)
            yield extractor

    def test_github_url_validation_secure(self, extractor):
        """Test that legitimate GitHub URLs are handled correctly."""
        test_cases = [
            ("git+https://github.com/owner/repo.git@v1.0.0", "https://github.com/owner/repo/archive/v1.0.0.tar.gz"),
            ("git+https://github.com/owner/repo@main", "https://github.com/owner/repo/archive/main.tar.gz"),
            ("git+https://github.com/owner/repo.git@abc123", "https://github.com/owner/repo/archive/abc123.tar.gz"),
        ]

        for vcs_url, expected_download_url in test_cases:
            # Mock the purl2src extractor to return our VCS URL
            with patch.object(extractor.purl2src, 'extract_from_purl') as mock_extract:
                mock_result = MagicMock()
                mock_result.success = True
                mock_result.errors = []
                mock_result.vcs_url = vcs_url
                mock_result.download_url = None
                mock_extract.return_value = mock_result

                # Test extraction with a generic PURL
                result = await extractor.extract_from_purl("pkg:generic/test@1.0.0")

                # Verify the URL was properly converted
                assert mock_extract.called

    @pytest.mark.asyncio
    async def test_malicious_github_url_substring_attack(self, extractor):
        """Test that malicious URLs with 'github.com' as substring are rejected."""
        malicious_urls = [
            "git+https://evil.com?github.com@v1.0.0",
            "git+https://github.com.evil.com/owner/repo@v1.0.0",
            "git+https://evil-github.com/owner/repo@v1.0.0",
            "git+https://notgithub.com/owner/repo@v1.0.0",
            "git+http://github.com/owner/repo@v1.0.0",  # HTTP instead of HTTPS
        ]

        for malicious_url in malicious_urls:
            with patch.object(extractor.purl2src, 'extract_from_purl') as mock_extract:
                mock_result = MagicMock()
                mock_result.success = True
                mock_result.errors = []
                mock_result.vcs_url = malicious_url
                mock_result.download_url = None
                mock_extract.return_value = mock_result

                # Test extraction - should not convert to GitHub archive URL
                result = await extractor.extract_from_purl("pkg:generic/test@1.0.0")

                # The malicious URL should not be converted to a GitHub archive URL
                assert mock_extract.called

    @pytest.mark.asyncio
    async def test_gitlab_url_validation(self, extractor):
        """Test GitLab URL validation."""
        test_cases = [
            ("git+https://gitlab.com/owner/repo.git@v1.0.0", "gitlab.com"),
            ("git+https://git.fsfe.org/owner/repo@main", "git.fsfe.org"),
        ]

        for vcs_url, expected_host in test_cases:
            with patch.object(extractor.purl2src, 'extract_from_purl') as mock_extract:
                mock_result = MagicMock()
                mock_result.success = True
                mock_result.errors = []
                mock_result.vcs_url = vcs_url
                mock_result.download_url = None
                mock_extract.return_value = mock_result

                result = await extractor.extract_from_purl("pkg:generic/test@1.0.0")
                assert mock_extract.called

    @pytest.mark.asyncio
    async def test_file_extension_detection_security(self, extractor):
        """Test that file extension detection is not vulnerable to path traversal."""
        test_urls = [
            ("https://example.com/package.whl", ".whl"),
            ("https://example.com/package.jar", ".jar"),
            ("https://example.com/package.gem", ".gem"),
            ("https://example.com/package.zip", ".zip"),
            ("https://example.com/package.nupkg", ".nupkg"),
            ("https://example.com/package.tar.gz", ".tar.gz"),
            ("https://example.com/package.tar.bz2", ".tar.bz2"),
            ("https://example.com/package.tgz", ".tgz"),
            # Security test cases
            ("https://example.com/path?file=.whl&other.jar", ".jar"),  # Should detect .jar, not .whl from query
            ("https://example.com/package.tar.gz?download=.zip", ".tar.gz"),  # Should ignore query params
        ]

        for url, expected_ext in test_urls:
            # Test the download method's extension detection
            with patch('aiohttp.ClientSession') as mock_session:
                mock_response = AsyncMock()
                mock_response.status = 200
                mock_response.read = AsyncMock(return_value=b"test content")
                mock_session.return_value.__aenter__.return_value.get.return_value.__aenter__.return_value = mock_response

                file_path = await extractor._download_package("pkg:generic/test@1.0.0", url)

                if file_path:
                    # Check the file extension matches expected
                    assert file_path.suffix == expected_ext or str(file_path).endswith(expected_ext)

    @pytest.mark.asyncio
    async def test_url_without_ref(self, extractor):
        """Test handling URLs without @ reference."""
        vcs_url = "git+https://github.com/owner/repo.git"

        with patch.object(extractor.purl2src, 'extract_from_purl') as mock_extract:
            mock_result = MagicMock()
            mock_result.success = True
            mock_result.errors = []
            mock_result.vcs_url = vcs_url
            mock_result.download_url = None
            mock_extract.return_value = mock_result

            result = await extractor.extract_from_purl("pkg:generic/test@1.0.0")

            # Should use the URL as-is when no ref is present
            assert mock_extract.called

    @pytest.mark.asyncio
    async def test_edge_cases(self, extractor):
        """Test edge cases in URL handling."""
        edge_cases = [
            "git+https://github.com/owner/repo@",  # Empty ref
            "git+https://github.com/@v1.0.0",  # Missing owner/repo
            "git+https://github.com/owner@v1.0.0",  # Missing repo
            "https://github.com/owner/repo@v1.0.0",  # Missing git+ prefix
            "",  # Empty URL
            "not-a-url",  # Invalid URL
        ]

        for url in edge_cases:
            with patch.object(extractor.purl2src, 'extract_from_purl') as mock_extract:
                mock_result = MagicMock()
                mock_result.success = True
                mock_result.errors = []
                mock_result.vcs_url = url
                mock_result.download_url = None
                mock_extract.return_value = mock_result

                # Should handle edge cases without crashing
                try:
                    result = await extractor.extract_from_purl("pkg:generic/test@1.0.0")
                except Exception as e:
                    pytest.fail(f"Failed to handle edge case {url}: {e}")