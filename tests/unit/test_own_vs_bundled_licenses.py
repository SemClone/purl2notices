"""A package's own license is separated from the ones it carries (issue #39).

    $ purl2notices -i "pkg:pypi/numpy@1.26.2" -f text
    Apache-2.0, BSD-3-Clause, LGPL-2.1-only, LGPL-3.0-only, MIT, Zlib

numpy is BSD-3-Clause. The rest is real, but it belongs to code numpy ships:
a vendored meson tree, bundled runtime libraries, LICENSES_bundled.txt. Under
one heading it reads as numpy being licensed under all of them, and an LGPL on
a line that reads as the package's own terms changes what a policy check
decides. Dropping them is wrong the other way, since that code does ship.

osslili has a third-party category but never assigns it: all 51 of numpy's
detections come back "declared", "detected" or "referenced". The signal it does
give is the path each was found at.
"""

import pytest

from purl2notices.extractors.base import (
    CATEGORY_DECLARED, CATEGORY_DETECTED, CATEGORY_THIRD_PARTY,
    detection_root, is_bundled_path,
)
from purl2notices.extractors.osslili_extractor import OssliliExtractor


class TestDetectionRoot:
    """The package root has to come from the paths, since its name varies."""

    def test_archive_top_level_directory_is_found(self):
        assert detection_root([
            "numpy-1.26.2/LICENSE.txt",
            "numpy-1.26.2/vendored-meson/meson/COPYING",
            "numpy-1.26.2/tools/wheels/LICENSE_linux.txt",
        ]) == "numpy-1.26.2"

    def test_npm_style_root_is_found(self):
        assert detection_root([
            "package/package.json", "package/LICENSE",
        ]) == "package"

    def test_no_paths_is_no_root(self):
        assert detection_root([]) == ""
        assert detection_root([None, None]) == ""

    def test_a_single_detection_still_yields_its_directory(self):
        assert detection_root(["package/LICENSE"]) == "package"


class TestIsBundledPath:
    """Where a license file sits says whose license it is."""

    ROOT = "numpy-1.26.2"

    @pytest.mark.parametrize("path", [
        "numpy-1.26.2/LICENSE.txt",
        "numpy-1.26.2/setup.py",
        "numpy-1.26.2/pyproject.toml",
    ])
    def test_root_files_are_the_packages_own(self, path):
        assert is_bundled_path(path, self.ROOT) is False

    @pytest.mark.parametrize("path", [
        "numpy-1.26.2/vendored-meson/meson/COPYING",
        "numpy-1.26.2/vendored-meson/meson-python/LICENSE",
        "numpy-1.26.2/tools/wheels/LICENSE_linux.txt",
        "numpy-1.26.2/tools/npy_tempita/license.txt",
        "numpy-1.26.2/numpy/random/LICENSE.md",
        "numpy-1.26.2/numpy/linalg/lapack_lite/LICENSE.txt",
    ])
    def test_nested_files_belong_to_the_code_they_sit_with(self, path):
        assert is_bundled_path(path, self.ROOT) is True

    def test_a_file_that_says_bundled_in_its_name_is_bundled(self):
        """At the root, but it is a notice about what ships, not a declaration."""
        assert is_bundled_path("numpy-1.26.2/LICENSES_bundled.txt", self.ROOT) is True

    @pytest.mark.parametrize("name", [
        "THIRD-PARTY-NOTICES.txt", "third_party_licenses.txt",
        "vendor-licenses.txt",
    ])
    def test_other_bundled_notice_names(self, name):
        assert is_bundled_path(f"{self.ROOT}/{name}", self.ROOT) is True

    def test_an_apache_notice_file_is_the_packages_own(self):
        """NOTICE is the attribution an Apache-2.0 package owes for itself.

        Reading it as a notice about bundled code puts a spurious
        "Bundles: Apache-2.0" beside every Apache artifact's own Apache-2.0.
        """
        assert is_bundled_path(f"{self.ROOT}/NOTICE", self.ROOT) is False
        assert is_bundled_path(f"{self.ROOT}/META-INF/NOTICE", self.ROOT) is False

    def test_no_path_is_not_a_judgement(self):
        """Without a path the detector's own category is the only signal."""
        assert is_bundled_path(None, self.ROOT) is False
        assert is_bundled_path("", self.ROOT) is False

    def test_a_carried_directory_answers_wherever_the_path_sits(self):
        """Depth needs a known root; a directory that names itself does not."""
        assert is_bundled_path("/elsewhere/vendor/LICENSE", self.ROOT) is True
        assert is_bundled_path("/elsewhere/node_modules/x/LICENSE", "") is True

    def test_an_unplaceable_path_is_not_called_carried_on_depth_alone(self):
        """Without a root every absolute path looks nested, including the root one."""
        assert is_bundled_path("/somewhere/pkg/LICENSE", "") is False
        assert is_bundled_path("/somewhere/pkg/LICENSE", "different-root") is False


class TestCategoryOverride:
    """The path corrects the detector's category, in one direction only."""

    class Detection:
        def __init__(self, category, source_file):
            self.category = category
            self.source_file = source_file

    def test_a_nested_declaration_becomes_third_party(self):
        d = self.Detection(CATEGORY_DECLARED, "numpy-1.26.2/vendored-meson/meson/COPYING")
        assert OssliliExtractor._category_for(d, "numpy-1.26.2") == CATEGORY_THIRD_PARTY

    def test_a_root_declaration_is_left_alone(self):
        d = self.Detection(CATEGORY_DECLARED, "numpy-1.26.2/LICENSE.txt")
        assert OssliliExtractor._category_for(d, "numpy-1.26.2") == CATEGORY_DECLARED

    def test_a_root_detection_keeps_its_weaker_category(self):
        """Only provenance is corrected here, not how strong the evidence is."""
        d = self.Detection(CATEGORY_DETECTED, "numpy-1.26.2/LICENSE.txt")
        assert OssliliExtractor._category_for(d, "numpy-1.26.2") == CATEGORY_DETECTED

    def test_third_party_is_never_overridden_towards_own(self):
        """A path that looks like the package's own does not undo the detector."""
        d = self.Detection(CATEGORY_THIRD_PARTY, "numpy-1.26.2/LICENSE.txt")
        assert OssliliExtractor._category_for(d, "numpy-1.26.2") == CATEGORY_THIRD_PARTY

    def test_a_detection_with_no_path_keeps_its_category(self):
        d = self.Detection(CATEGORY_DECLARED, None)
        assert OssliliExtractor._category_for(d, "numpy-1.26.2") == CATEGORY_DECLARED


def _pkg(name, own, bundled):
    from purl2notices.models import Package, License
    return Package(
        name=name, version="1", purl=f"pkg:pypi/{name}@1",
        licenses=(
            [License(spdx_id=i, name=i, text="", source="t", bundled=False) for i in own]
            + [License(spdx_id=i, name=i, text="", source="t", bundled=True) for i in bundled]
        ),
    )


class TestModelSeparatesThem:
    def test_own_and_bundled_are_reachable_separately(self):
        pkg = _pkg("numpy", ["BSD-3-Clause"], ["LGPL-3.0-only", "MIT"])
        assert [l.spdx_id for l in pkg.own_licenses] == ["BSD-3-Clause"]
        assert sorted(l.spdx_id for l in pkg.bundled_licenses) == ["LGPL-3.0-only", "MIT"]

    def test_the_same_id_can_be_both(self):
        """numpy bundles BSD-3-Clause code and is itself BSD-3-Clause."""
        pkg = _pkg("numpy", ["BSD-3-Clause"], ["BSD-3-Clause"])
        assert len(pkg.own_licenses) == 1
        assert len(pkg.bundled_licenses) == 1


class TestGrouping:
    def _groups(self, packages):
        from purl2notices.formatter import NoticeFormatter
        return NoticeFormatter()._group_by_license(packages)

    def test_a_package_is_grouped_under_its_own_license_only(self):
        groups = self._groups([_pkg("numpy", ["BSD-3-Clause"],
                                    ["LGPL-3.0-only", "MIT", "Zlib"])])
        assert list(groups) == ["BSD-3-Clause"]

    def test_several_own_licenses_still_combine(self):
        groups = self._groups([_pkg("dual", ["MIT", "Apache-2.0"], ["Zlib"])])
        assert list(groups) == ["Apache-2.0, MIT"]

    def test_a_package_with_only_carried_licenses_says_nothing_about_itself(self):
        """Not silently dropped, and not claiming the carried ones either."""
        groups = self._groups([_pkg("only-vendored", [], ["MIT"])])
        assert list(groups) == ["NOASSERTION"]


class TestOutputShowsBoth:
    def _text(self, packages):
        from purl2notices.formatter import NoticeFormatter
        return NoticeFormatter().format(packages, format_type="text",
                                        group_by_license=True)

    def test_the_heading_is_the_packages_own_license(self):
        out = self._text([_pkg("numpy", ["BSD-3-Clause"], ["LGPL-3.0-only"])])
        assert "\nBSD-3-Clause\n" in out
        assert "BSD-3-Clause, LGPL-3.0-only" not in out

    def test_carried_licenses_are_listed_and_not_dropped(self):
        out = self._text([_pkg("numpy", ["BSD-3-Clause"],
                               ["LGPL-3.0-only", "Zlib"])])
        assert "Bundled components" in out
        assert "LGPL-3.0-only" in out
        assert "Zlib" in out

    def test_a_package_carrying_nothing_gets_no_bundled_section(self):
        out = self._text([_pkg("express", ["MIT"], [])])
        assert "Bundled components" not in out

    def test_json_reports_carried_licenses_beside_the_package(self):
        import json
        from purl2notices.formatter import NoticeFormatter
        out = json.loads(NoticeFormatter().format(
            [_pkg("numpy", ["BSD-3-Clause"], ["LGPL-3.0-only", "MIT"])],
            format_type="json", group_by_license=True,
        ))
        entry = out["licenses"][0]
        assert entry["id"] == "BSD-3-Clause"
        assert [b["id"] for b in entry["packages"][0]["bundled_licenses"]] == [
            "LGPL-3.0-only", "MIT"]


class TestSurvivesTheCache:
    """A cached package must not reload claiming what it carries as its own."""

    def _pkgs(self):
        return [_pkg("numpy", ["BSD-3-Clause"], ["BSD-3-Clause", "LGPL-3.0-only"])]

    def test_round_trip_keeps_the_distinction(self, tmp_path):
        from purl2notices.cache import CacheManager
        cache = tmp_path / "cache.json"
        CacheManager(cache).save(self._pkgs())

        loaded = CacheManager(cache).load()

        assert len(loaded) == 1
        assert [l.spdx_id for l in loaded[0].own_licenses] == ["BSD-3-Clause"]
        assert sorted(l.spdx_id for l in loaded[0].bundled_licenses) == [
            "BSD-3-Clause", "LGPL-3.0-only"]

    def test_the_same_id_survives_as_both(self, tmp_path):
        """Recorded by position, since the SPDX id does not identify the entry."""
        from purl2notices.cache import CacheManager
        cache = tmp_path / "cache.json"
        CacheManager(cache).save([_pkg("numpy", ["BSD-3-Clause"], ["BSD-3-Clause"])])

        loaded = CacheManager(cache).load()[0]

        assert len(loaded.own_licenses) == 1
        assert len(loaded.bundled_licenses) == 1

    def test_a_package_carrying_nothing_writes_no_marker(self, tmp_path):
        import json
        from purl2notices.cache import CacheManager
        cache = tmp_path / "cache.json"
        CacheManager(cache).save([_pkg("express", ["MIT"], [])])

        body = json.loads(cache.read_text())
        names = [p["name"] for c in body["components"] for p in c.get("properties", [])]
        assert "purl2notices:bundled_licenses" not in names

    def test_the_cache_version_moved(self):
        """Caches written before the distinction cannot be read as own-only."""
        from purl2notices.constants import CACHE_VERSION
        assert CACHE_VERSION != "2.0"


class TestCombineKeepsBoth:
    """Own and carried records for one id must not collapse before output."""

    def _info(self, category, source_file, confidence=0.9):
        from purl2notices.extractors.base import LicenseInfo, ExtractionSource
        return LicenseInfo(
            spdx_id="BSD-3-Clause", name="BSD-3-Clause", text="",
            source=ExtractionSource.OSSLILI, confidence=confidence,
            category=category, match_type="license_file",
            detection_method="test", source_file=source_file,
        )

    def test_the_same_id_survives_as_own_and_carried(self):
        from purl2notices.extractors.base import CATEGORY_DECLARED
        from purl2notices.extractors.combined_extractor import CombinedExtractor

        result = CombinedExtractor()._combine_licenses([
            self._info(CATEGORY_DECLARED, "numpy-1.26.2/LICENSE.txt"),
            self._info(CATEGORY_THIRD_PARTY, "numpy-1.26.2/vendor/LICENSE"),
        ])

        assert len(result) == 2


class TestUngroupedOutputs:
    """The per-package views must draw the same distinction."""

    def _pkg(self):
        return _pkg("numpy", ["BSD-3-Clause"], ["LGPL-3.0-only"])

    def test_license_ids_are_the_packages_own(self):
        pkg = self._pkg()
        assert pkg.license_ids == ["BSD-3-Clause"]
        assert pkg.bundled_license_ids == ["LGPL-3.0-only"]

    @pytest.mark.parametrize("fmt", ["text", "html"])
    def test_ungrouped_shows_own_as_the_license_and_carried_apart(self, fmt):
        from purl2notices.formatter import NoticeFormatter
        out = NoticeFormatter().format([self._pkg()], format_type=fmt,
                                       group_by_license=False)
        assert "BSD-3-Clause" in out
        assert "LGPL-3.0-only" in out
        assert "BSD-3-Clause, LGPL-3.0-only" not in out

    def test_ungrouped_json_separates_them(self):
        import json
        from purl2notices.formatter import NoticeFormatter
        out = json.loads(NoticeFormatter().format(
            [self._pkg()], format_type="json", group_by_license=False))
        entry = out["packages"][0]
        assert entry["licenses"] == ["BSD-3-Clause"]
        assert [b["id"] for b in entry["bundled_licenses"]] == ["LGPL-3.0-only"]

    @pytest.mark.parametrize("fmt", ["text", "html"])
    def test_carried_licenses_show_without_license_texts(self, fmt):
        """The section is about what ships, not about texts being included."""
        from purl2notices.formatter import NoticeFormatter
        out = NoticeFormatter().format([self._pkg()], format_type=fmt,
                                       group_by_license=True,
                                       include_license_text=False)
        assert "LGPL-3.0-only" in out


class TestOverridesKeepTheMarkerHonest:
    """Disabling a license rewrites the list the marker points into."""

    def _cache(self, tmp_path, disabled):
        import json
        from purl2notices.cache import CacheManager
        overrides = tmp_path / "overrides.json"
        overrides.write_text(json.dumps({
            "disabled_licenses": {"pkg:pypi/numpy@1": disabled}
        }))
        return CacheManager(tmp_path / "cache.json", override_file=overrides)

    def test_disabling_the_own_license_does_not_promote_a_carried_one(self, tmp_path):
        """The marker is positional, so a shifted list must shift with it."""
        manager = self._cache(tmp_path, ["MIT"])
        manager.save([_pkg("numpy", ["MIT"], ["GPL-3.0-only"])])

        loaded = self._cache(tmp_path, ["MIT"]).load()[0]

        assert [l.spdx_id for l in loaded.own_licenses] == []
        assert [l.spdx_id for l in loaded.bundled_licenses] == ["GPL-3.0-only"]

    def test_disabling_a_carried_license_leaves_the_own_one_alone(self, tmp_path):
        manager = self._cache(tmp_path, ["GPL-3.0-only"])
        manager.save([_pkg("numpy", ["MIT"], ["GPL-3.0-only"])])

        loaded = self._cache(tmp_path, ["GPL-3.0-only"]).load()[0]

        assert [l.spdx_id for l in loaded.own_licenses] == ["MIT"]
        assert [l.spdx_id for l in loaded.bundled_licenses] == []


class TestCachedLicenseText:
    """Two records for one id do not hold the same text."""

    def test_own_and_carried_texts_do_not_overwrite_each_other(self, tmp_path):
        from purl2notices.cache import CacheManager
        from purl2notices.models import Package, License
        pkg = Package(
            name="numpy", version="1", purl="pkg:pypi/numpy@1",
            licenses=[
                License(spdx_id="BSD-3-Clause", name="BSD-3-Clause",
                        text="numpy's own BSD text", source="t"),
                License(spdx_id="BSD-3-Clause", name="BSD-3-Clause",
                        text="the vendored BSD text", source="t", bundled=True),
            ],
        )
        cache = tmp_path / "cache.json"
        CacheManager(cache).save([pkg])

        loaded = CacheManager(cache).load()[0]

        assert loaded.own_licenses[0].text == "numpy's own BSD text"
        assert loaded.bundled_licenses[0].text == "the vendored BSD text"


class TestRootWhenNothingSitsAtIt:
    """A package whose only licenses are vendored has not stated its own."""

    def test_the_shallowest_vendored_directory_is_not_the_root(self):
        from purl2notices.extractors.base import detection_root, is_bundled_path
        paths = ["pkg-1.0/vendor/foo/LICENSE", "pkg-1.0/vendor/bar/LICENSE"]
        root = detection_root(paths)
        assert root == "pkg-1.0"
        assert all(is_bundled_path(p, root) for p in paths)

    def test_a_lone_vendored_license_is_still_carried(self):
        from purl2notices.extractors.base import detection_root, is_bundled_path
        paths = ["pkg-1.0/vendor/foo/LICENSE"]
        assert is_bundled_path(paths[0], detection_root(paths)) is True

    def test_a_scanned_directory_uses_its_own_path(self):
        from purl2notices.extractors.base import detection_root, is_bundled_path
        paths = ["/tmp/x/package/LICENSE", "/tmp/x/package/package.json"]
        root = detection_root(paths)
        assert root == "/tmp/x/package"
        assert not any(is_bundled_path(p, root) for p in paths)


class TestOwnLicenseQuestions:
    """Code asking 'does this package have a license' means its own."""

    def test_status_is_no_license_when_only_carried_ones_were_found(self):
        """NO_LICENSE means the package said nothing about its own terms."""
        from purl2notices.models import ProcessingStatus

        carried_only = _pkg("only-vendored", [], ["MIT"])
        assert not carried_only.own_licenses

        # The status decision this pins lives in core, gated on own_licenses.
        import inspect
        from purl2notices.core import Purl2Notices
        source = inspect.getsource(Purl2Notices)
        assert "if not package.own_licenses:" in source
        assert "ProcessingStatus.NO_LICENSE" in source
        assert "if not package.licenses:\n            package.status" not in source

    def test_declared_metadata_fallback_still_runs(self):
        from purl2notices.core import Purl2Notices
        from purl2notices.config import Config
        core = Purl2Notices(Config())
        pkg = _pkg("only-vendored", [], ["MIT"])
        pkg.metadata = {"license": "ISC"}
        core._apply_declared_license_fallback(pkg)
        assert [l.spdx_id for l in pkg.own_licenses] == ["ISC"]

    def test_format_simple_says_noassertion_rather_than_nothing(self):
        from purl2notices.formatter import NoticeFormatter
        out = NoticeFormatter().format_simple([_pkg("only-vendored", [], ["MIT"])])
        assert "License: NOASSERTION" in out


class TestCarriedOnlyPackagesAreNotDropped:
    """An attribution file that omits shipped code is incomplete."""

    @pytest.mark.parametrize("fmt", ["text", "html"])
    def test_a_package_with_only_carried_licenses_still_appears(self, fmt):
        from purl2notices.formatter import NoticeFormatter
        out = NoticeFormatter().format([_pkg("only-vendored", [], ["MIT"])],
                                       format_type=fmt, group_by_license=True)
        assert "only-vendored" in out
        assert "MIT" in out

    def test_it_appears_in_format_simple_too(self):
        from purl2notices.formatter import NoticeFormatter
        out = NoticeFormatter().format_simple([_pkg("only-vendored", [], ["MIT"])])
        assert "only-vendored" in out
        assert "License: NOASSERTION" in out

    def test_a_package_with_nothing_at_all_is_still_dropped(self):
        from purl2notices.formatter import NoticeFormatter
        out = NoticeFormatter().format_simple([_pkg("empty", [], [])])
        assert "empty" not in out


class TestOwnHeadingTextIsNotBorrowedFromCarried:
    """The heading is the package's own license, so the text must be too."""

    def test_a_carried_record_does_not_supply_the_own_headings_text(self):
        from purl2notices.core import Purl2Notices
        from purl2notices.config import Config
        from purl2notices.models import Package, License
        pkg = Package(
            name="numpy", version="1", purl="pkg:pypi/numpy@1",
            licenses=[
                License(spdx_id="BSD-3-Clause", name="BSD-3-Clause",
                        text="", source="t"),
                License(spdx_id="BSD-3-Clause", name="BSD-3-Clause",
                        text="Copyright (c) The Vendored Project\nterms\n",
                        source="t", bundled=True),
            ],
        )

        texts = Purl2Notices(Config())._load_license_texts([pkg])

        assert "The Vendored Project" not in texts.get("BSD-3-Clause", "")


class TestEcosystemMetadataDirs:
    """Some ecosystems keep the package's own license one level in."""

    @pytest.mark.parametrize("path", [
        "pkg-1.0/META-INF/LICENSE",
        "pkg-1.0/pkg-1.0.dist-info/LICENSE",
        "pkg-1.0/pkg.egg-info/LICENSE",
        "pkg-1.0/LICENSES/MIT.txt",
    ])
    def test_they_are_the_packages_own(self, path):
        from purl2notices.extractors.base import is_bundled_path
        assert is_bundled_path(path, "pkg-1.0") is False

    @pytest.mark.parametrize("path", [
        "pkg-1.0/META-INF/vendor/dep/LICENSE",
        "pkg-1.0/pkg-1.0.dist-info/vendored/LICENSE",
    ])
    def test_but_not_two_levels_in(self, path):
        from purl2notices.extractors.base import is_bundled_path
        assert is_bundled_path(path, "pkg-1.0") is True


class TestCarriedTextsAreNotDropped:
    """A license that requires its text to ship must ship it.

    Naming "carries: LGPL-2.1-or-later" without the text is the omission the
    issue calls wrong the other way, and the text is already held.
    """

    LGPL = "GNU LESSER GENERAL PUBLIC LICENSE\nVersion 2.1\n\nfull terms here\n"

    def _pkg(self):
        from purl2notices.models import Package, License
        return Package(
            name="numpy", version="1", purl="pkg:pypi/numpy@1",
            licenses=[
                License(spdx_id="BSD-3-Clause", name="BSD-3-Clause",
                        text="numpy's own BSD", source="t"),
                License(spdx_id="LGPL-2.1-or-later", name="LGPL-2.1-or-later",
                        text=self.LGPL, source="t", bundled=True),
            ],
        )

    @pytest.mark.parametrize("fmt", ["text", "html"])
    @pytest.mark.parametrize("grouped", [True, False])
    def test_the_carried_text_is_emitted(self, fmt, grouped):
        from purl2notices.formatter import NoticeFormatter
        out = NoticeFormatter().format([self._pkg()], format_type=fmt,
                                       group_by_license=grouped)
        assert "full terms here" in out

    def test_json_carries_the_text(self):
        import json
        from purl2notices.formatter import NoticeFormatter
        out = json.loads(NoticeFormatter().format(
            [self._pkg()], format_type="json", group_by_license=True))
        bundled = out["licenses"][0]["packages"][0]["bundled_licenses"]
        assert bundled[0]["id"] == "LGPL-2.1-or-later"
        assert "full terms here" in bundled[0]["text"]

    @pytest.mark.parametrize("fmt", ["text", "html"])
    def test_texts_are_omitted_when_texts_are_turned_off(self, fmt):
        from purl2notices.formatter import NoticeFormatter
        out = NoticeFormatter().format([self._pkg()], format_type=fmt,
                                       group_by_license=True,
                                       include_license_text=False)
        assert "LGPL-2.1-or-later" in out
        assert "full terms here" not in out

    def test_two_components_under_one_license_keep_both_notices(self):
        """Same id, different filled-in notices, both owed attribution."""
        from purl2notices.models import Package, License
        pkg = Package(
            name="app", version="1", purl="pkg:npm/app@1",
            licenses=[
                License(spdx_id="MIT", name="MIT", text="own", source="t"),
                License(spdx_id="MIT", name="MIT", text="Copyright A\n",
                        source="t", bundled=True),
                License(spdx_id="MIT", name="MIT", text="Copyright B\n",
                        source="t", bundled=True),
                License(spdx_id="MIT", name="MIT", text="Copyright A\n",
                        source="t", bundled=True),
            ],
        )
        assert len(pkg.distinct_bundled_licenses) == 2


class TestCarriedNoticesSurviveDeduplication:
    """Two vendored components under one license ship different notices.

    Both are owed attribution, so the text is part of what makes two carried
    records distinct. The package's own records still collapse on the license
    alone, so the best-evidenced one still wins.
    """

    def _info(self, category, text, source_file, confidence=0.9):
        from purl2notices.extractors.base import LicenseInfo, ExtractionSource
        return LicenseInfo(
            spdx_id="MIT", name="MIT", text=text, source=ExtractionSource.OSSLILI,
            confidence=confidence, category=category, match_type="license_file",
            detection_method="test", source_file=source_file,
        )

    def test_extractor_dedupe_keeps_both_notices(self):
        from purl2notices.extractors.osslili_extractor import OssliliExtractor
        result = OssliliExtractor().deduplicate_licenses([
            self._info(CATEGORY_THIRD_PARTY, "Copyright A\n", "p/vendor/a/LICENSE"),
            self._info(CATEGORY_THIRD_PARTY, "Copyright B\n", "p/vendor/b/LICENSE"),
        ])
        assert len(result) == 2

    def test_extractor_dedupe_still_collapses_identical_notices(self):
        from purl2notices.extractors.osslili_extractor import OssliliExtractor
        result = OssliliExtractor().deduplicate_licenses([
            self._info(CATEGORY_THIRD_PARTY, "Copyright A\n", "p/vendor/a/LICENSE"),
            self._info(CATEGORY_THIRD_PARTY, "Copyright A\n", "p/vendor/b/LICENSE"),
        ])
        assert len(result) == 1

    def test_own_records_still_collapse_on_the_license_alone(self):
        from purl2notices.extractors.osslili_extractor import OssliliExtractor
        result = OssliliExtractor().deduplicate_licenses([
            self._info(CATEGORY_DECLARED, "", "p/package.json", confidence=0.95),
            self._info(CATEGORY_DECLARED, "the shipped text\n", "p/LICENSE"),
        ])
        assert len(result) == 1

    def test_combining_keeps_both_notices(self):
        from purl2notices.extractors.combined_extractor import CombinedExtractor
        result = CombinedExtractor()._combine_licenses([
            self._info(CATEGORY_THIRD_PARTY, "Copyright A\n", "p/vendor/a/LICENSE"),
            self._info(CATEGORY_THIRD_PARTY, "Copyright B\n", "p/vendor/b/LICENSE"),
        ])
        assert len(result) == 2

    def test_cache_merge_keeps_both_notices(self, tmp_path):
        from purl2notices.cache import CacheManager
        from purl2notices.models import Package, License

        def pkg(texts):
            return Package(
                name="app", version="1", purl="pkg:npm/app@1",
                licenses=[License(spdx_id="MIT", name="MIT", text=t,
                                  source="t", bundled=True) for t in texts],
            )

        cache = tmp_path / "cache.json"
        CacheManager(cache).save([pkg(["Copyright A\n"])])
        CacheManager(cache).save([pkg(["Copyright B\n"])])

        loaded = CacheManager(cache).load()[0]
        assert len(loaded.bundled_licenses) == 2


class TestArchiveWithoutAWrapperDirectory:
    """Not every archive puts its contents under one top-level directory."""

    def test_a_root_level_file_means_there_is_no_wrapper_to_strip(self):
        from purl2notices.extractors.base import detection_root, is_bundled_path
        paths = ["LICENSE", "vendor/LICENSE"]

        root = detection_root(paths)

        assert root == ""
        assert is_bundled_path("LICENSE", root) is False
        assert is_bundled_path("vendor/LICENSE", root) is True

    def test_a_wrapper_directory_is_still_stripped_when_there_is_one(self):
        from purl2notices.extractors.base import detection_root, is_bundled_path
        paths = ["numpy-1.26.2/LICENSE.txt", "numpy-1.26.2/vendor/LICENSE"]

        root = detection_root(paths)

        assert root == "numpy-1.26.2"
        assert is_bundled_path("numpy-1.26.2/LICENSE.txt", root) is False
        assert is_bundled_path("numpy-1.26.2/vendor/LICENSE", root) is True

    def test_two_top_level_directories_mean_no_wrapper(self):
        from purl2notices.extractors.base import detection_root
        assert detection_root(["a/LICENSE", "b/LICENSE"]) == ""
