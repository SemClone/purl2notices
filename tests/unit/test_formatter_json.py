"""Tests for JSON formatter output, covering the SBOM completeness guarantee
that unlicensed packages are never silently dropped (issue #30)."""

import json

import pytest

from purl2notices.formatter import NoticeFormatter
from purl2notices.models import Package, License


@pytest.fixture
def formatter():
    return NoticeFormatter()


def _mit(name, version):
    return Package(name=name, version=version, purl=f"pkg:npm/{name}@{version}",
                   licenses=[License(spdx_id="MIT", name="MIT", text="")])


def _unlicensed(name, version):
    return Package(name=name, version=version, purl=f"pkg:npm/{name}@{version}")


class TestJsonUnlicensedNotDropped:
    """An unlicensed package must appear in JSON output, marked NOASSERTION."""

    def test_grouped_output_surfaces_unlicensed_under_noassertion(self, formatter):
        packages = [_mit("cookie", "1.1.1"), _unlicensed("picocolors", "1.1.1")]

        result = json.loads(formatter.format(packages, format_type="json"))

        assert result["metadata"]["total_packages"] == 2
        groups = {g["id"]: [p["name"] for p in g["packages"]]
                  for g in result["licenses"]}
        assert groups["MIT"] == ["cookie"]
        assert groups["NOASSERTION"] == ["picocolors"]

    def test_ungrouped_output_marks_unlicensed_noassertion(self, formatter):
        packages = [_mit("cookie", "1.1.1"), _unlicensed("picocolors", "1.1.1")]

        result = json.loads(
            formatter.format(packages, format_type="json", group_by_license=False)
        )

        by_name = {p["name"]: p["licenses"] for p in result["packages"]}
        assert by_name["cookie"] == ["MIT"]
        assert by_name["picocolors"] == ["NOASSERTION"]

    def test_all_unlicensed_still_reported(self, formatter):
        packages = [_unlicensed("a", "1.0.0"), _unlicensed("b", "2.0.0")]

        result = json.loads(formatter.format(packages, format_type="json"))

        assert result["metadata"]["total_packages"] == 2
        groups = {g["id"]: [p["name"] for p in g["packages"]]
                  for g in result["licenses"]}
        assert sorted(groups["NOASSERTION"]) == ["a", "b"]


class TestFilterOssPackages:
    """The keep_unlicensed flag governs whether unlicensed packages survive."""

    def test_default_drops_unlicensed(self, formatter):
        packages = [_mit("cookie", "1.1.1"), _unlicensed("picocolors", "1.1.1")]

        kept = formatter._filter_oss_packages(packages)

        assert [p.name for p in kept] == ["cookie"]

    def test_keep_unlicensed_retains_them(self, formatter):
        packages = [_mit("cookie", "1.1.1"), _unlicensed("picocolors", "1.1.1")]

        kept = formatter._filter_oss_packages(packages, keep_unlicensed=True)

        assert sorted(p.name for p in kept) == ["cookie", "picocolors"]
