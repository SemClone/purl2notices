"""Unit tests for the declared-license fallback (issue #30)."""

import pytest

from purl2notices.core import Purl2Notices
from purl2notices.config import Config
from purl2notices.models import Package, License, Copyright, ProcessingStatus


@pytest.fixture
def core():
    return Purl2Notices(Config())


class TestDeclaredLicenseId:
    """Normalization of declared license metadata values."""

    @pytest.mark.parametrize("declared,expected", [
        ("ISC", "ISC"),
        ("  MIT  ", "MIT"),
        ("(MIT OR Apache-2.0)", "(MIT OR Apache-2.0)"),
        ({"type": "ISC", "url": "https://example.com"}, "ISC"),
    ])
    def test_usable_values(self, declared, expected):
        assert Purl2Notices._declared_license_id(declared) == expected

    @pytest.mark.parametrize("declared", [
        "", "   ", None, "UNLICENSED", "unknown", "NOASSERTION",
        "SEE LICENSE IN LICENSE", {}, {"url": "x"}, 123,
    ])
    def test_unusable_values(self, declared):
        assert Purl2Notices._declared_license_id(declared) is None


class TestDeclaredLicenseFallback:
    """Fallback to declared license metadata when detection found none."""

    def test_fills_in_declared_license_when_none_detected(self, core):
        pkg = Package(name="picocolors", version="1.1.1",
                      purl="pkg:npm/picocolors@1.1.1",
                      status=ProcessingStatus.NO_LICENSE,
                      metadata={"license": "ISC"})

        core._apply_declared_license_fallback(pkg)

        assert [l.spdx_id for l in pkg.licenses] == ["ISC"]
        assert pkg.licenses[0].source == "declared-metadata"
        # No copyright, so status moves from NO_LICENSE to NO_COPYRIGHT.
        assert pkg.status == ProcessingStatus.NO_COPYRIGHT

    def test_status_becomes_success_when_copyright_present(self, core):
        pkg = Package(name="picocolors", version="1.1.1",
                      status=ProcessingStatus.NO_LICENSE,
                      metadata={"license": "ISC"})
        pkg.copyrights.append(Copyright(statement="Copyright (c) 2024"))

        core._apply_declared_license_fallback(pkg)

        assert pkg.status == ProcessingStatus.SUCCESS

    def test_does_not_override_detected_license(self, core):
        pkg = Package(name="dotenv", version="16.6.1",
                      metadata={"license": "BSD-2-Clause"})
        pkg.licenses.append(License(spdx_id="BSD-3-Clause", name="BSD-3-Clause",
                                    text="", source="content"))

        core._apply_declared_license_fallback(pkg)

        # Detected license is authoritative; declared value is not appended.
        assert [l.spdx_id for l in pkg.licenses] == ["BSD-3-Clause"]

    def test_no_op_without_declared_license(self, core):
        pkg = Package(name="mystery", version="0.0.0",
                      status=ProcessingStatus.NO_LICENSE, metadata={})

        core._apply_declared_license_fallback(pkg)

        assert pkg.licenses == []
        assert pkg.status == ProcessingStatus.NO_LICENSE

    def test_does_not_bump_unavailable_status(self, core):
        # A package that could not be fetched keeps its UNAVAILABLE status even
        # though we record its declared license for SBOM completeness.
        pkg = Package(name="picocolors", version="1.1.1",
                      status=ProcessingStatus.UNAVAILABLE,
                      metadata={"license": "ISC"})

        core._apply_declared_license_fallback(pkg)

        assert [l.spdx_id for l in pkg.licenses] == ["ISC"]
        assert pkg.status == ProcessingStatus.UNAVAILABLE
