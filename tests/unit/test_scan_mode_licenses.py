"""Scanning a directory must rank licenses the same way a PURL does.

`purl2notices -i <directory>` reaches osslili through a different path from
`-i pkg:npm/...`, and that path went straight from a raw scan into the notices
file. Someone pointing this at a checkout containing express got the JSON
license from its changelog, which is the bug the PURL path was fixed for.
"""

import asyncio
from pathlib import Path

import pytest

from purl2notices.core import Purl2Notices
from purl2notices.extractors.base import (
    ExtractionResult, ExtractionSource, LicenseInfo,
    CATEGORY_DECLARED, CATEGORY_DETECTED, MATCH_LICENSE_FILE,
)


def express_shaped_scan():
    """What osslili returns for a tree containing express."""
    return ExtractionResult(
        success=True,
        source=ExtractionSource.OSSLILI,
        licenses=[
            LicenseInfo(
                spdx_id="MIT", name="MIT License", source=ExtractionSource.OSSLILI,
                confidence=1.0, category=CATEGORY_DECLARED,
                source_file="/tree/express/package.json",
                match_type="package_metadata", detection_method="tag",
            ),
            LicenseInfo(
                spdx_id="JSON", name="JSON", source=ExtractionSource.OSSLILI,
                confidence=0.85, category=CATEGORY_DETECTED,
                source_file="/tree/express/History.md",
                match_type="keyword", detection_method="keyword",
            ),
        ],
    )


@pytest.fixture
def app():
    return Purl2Notices()


def scan(app, monkeypatch, result):
    async def fake_extract_from_path(path):
        return result
    monkeypatch.setattr(
        app.extractor.osslili, "extract_from_path", fake_extract_from_path
    )
    return asyncio.run(app._extract_source_code_only(Path("/tree")))


class TestScanningADirectory:
    def test_a_changelog_keyword_hit_does_not_reach_the_notices(self, app, monkeypatch):
        result = scan(app, monkeypatch, express_shaped_scan())
        assert sorted(lic.spdx_id for lic in result.licenses) == ["MIT"]

    def test_the_real_license_is_still_reported(self, app, monkeypatch):
        result = scan(app, monkeypatch, express_shaped_scan())
        assert result.success
        assert [lic.spdx_id for lic in result.licenses] == ["MIT"]

    def test_a_scan_that_found_nothing_is_left_alone(self, app, monkeypatch):
        empty = ExtractionResult(success=True, licenses=[], source=ExtractionSource.OSSLILI)
        result = scan(app, monkeypatch, empty)
        assert result.licenses == []
        assert result.success

    def test_a_failed_scan_is_left_alone(self, app, monkeypatch):
        failed = ExtractionResult(
            success=False, errors=["osslili library not available"],
            source=ExtractionSource.OSSLILI,
        )
        result = scan(app, monkeypatch, failed)
        assert not result.success
        assert result.errors == ["osslili library not available"]

    def test_two_declared_licenses_both_survive_a_scan(self, app, monkeypatch):
        dual = ExtractionResult(
            success=True, source=ExtractionSource.OSSLILI,
            licenses=[
                LicenseInfo(
                    spdx_id="Apache-2.0", name="Apache-2.0", confidence=0.989,
                    source=ExtractionSource.OSSLILI, category=CATEGORY_DECLARED,
                    source_file="/tree/LICENSE.APACHE", match_type=MATCH_LICENSE_FILE,
                ),
                LicenseInfo(
                    spdx_id="BSD-2-Clause", name="BSD-2-Clause", confidence=0.988,
                    source=ExtractionSource.OSSLILI, category=CATEGORY_DECLARED,
                    source_file="/tree/LICENSE.BSD", match_type=MATCH_LICENSE_FILE,
                ),
            ],
        )
        result = scan(app, monkeypatch, dual)
        assert sorted(lic.spdx_id for lic in result.licenses) == ["Apache-2.0", "BSD-2-Clause"]
