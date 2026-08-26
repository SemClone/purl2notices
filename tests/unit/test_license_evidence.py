"""What counts as evidence that a package carries a license.

Every fixture here is the shape of a real detection taken from a real package,
because the bug these guard against did not look like a bug in the output: the
notices file was well-formed and confidently wrong.
"""

import pytest

from purl2notices.extractors.base import (
    LicenseInfo, ExtractionSource,
    CATEGORY_DECLARED, CATEGORY_DETECTED, CATEGORY_THIRD_PARTY,
    MATCH_LICENSE_FILE,
)
from purl2notices.extractors.combined_extractor import CombinedExtractor


@pytest.fixture
def extractor(tmp_path):
    return CombinedExtractor(cache_dir=tmp_path)


def scanned(spdx, category, confidence, source_file, match_type=None, method=None):
    """A detection that names the file it came from, as osslili reports one."""
    return LicenseInfo(
        spdx_id=spdx, name=spdx, source=ExtractionSource.OSSLILI,
        category=category, confidence=confidence,
        source_file=source_file, match_type=match_type, detection_method=method,
    )


def unsourced(spdx, confidence):
    """A detection with no file behind it, as upmex reports one."""
    return LicenseInfo(
        spdx_id=spdx, name=spdx, source=ExtractionSource.UPMEX,
        confidence=confidence, source_file=None,
    )


def ids(licenses):
    return sorted({lic.spdx_id for lic in licenses})


class TestProseIsNotADeclaration:
    """express@4.18.2 shipped as JSON-licensed. This is that package."""

    def test_a_changelog_keyword_hit_does_not_become_a_license(self, extractor):
        result = extractor._stated_licenses([
            scanned("MIT", CATEGORY_DECLARED, 1.0, "/pkg/package.json", "package_metadata", "tag"),
            scanned("MIT", CATEGORY_DECLARED, 0.997, "/pkg/LICENSE", MATCH_LICENSE_FILE, "dice-sorensen"),
            scanned("MIT", CATEGORY_DETECTED, 0.9, "/pkg/LICENSE", "keyword", "keyword"),
            scanned("JSON", CATEGORY_DETECTED, 0.85, "/pkg/History.md", "keyword", "keyword"),
        ])
        assert ids(result) == ["MIT"]

    def test_the_declared_license_itself_is_not_lost(self, extractor):
        result = extractor._stated_licenses([
            scanned("MIT", CATEGORY_DECLARED, 1.0, "/pkg/package.json", "package_metadata", "tag"),
            scanned("JSON", CATEGORY_DETECTED, 0.85, "/pkg/History.md", "keyword", "keyword"),
        ])
        assert [lic.spdx_id for lic in result] == ["MIT"]

    def test_docs_naming_a_license_do_not_add_it(self, extractor):
        """cryptography's docs discuss OpenSSL across four files."""
        result = extractor._stated_licenses([
            scanned("Apache-2.0", CATEGORY_DECLARED, 1.0, "/pkg/LICENSE.APACHE", MATCH_LICENSE_FILE, "tag"),
            scanned("BSD-3-Clause", CATEGORY_DECLARED, 1.0, "/pkg/pyproject.toml", "package_metadata", "tag"),
            scanned("OpenSSL", CATEGORY_DETECTED, 0.85, "/pkg/docs/faq.rst", "keyword", "keyword"),
            scanned("OpenSSL", CATEGORY_DETECTED, 0.85, "/pkg/CHANGELOG.rst", "keyword", "keyword"),
        ])
        assert ids(result) == ["Apache-2.0", "BSD-3-Clause"]


class TestDualLicensingSurvives:
    """The fix must not collapse a package that really does carry two."""

    def test_two_declared_licenses_are_both_kept(self, extractor):
        result = extractor._stated_licenses([
            scanned("Apache-2.0", CATEGORY_DECLARED, 0.989, "/pkg/LICENSE.APACHE", MATCH_LICENSE_FILE, "dice-sorensen"),
            scanned("BSD-2-Clause", CATEGORY_DECLARED, 0.988, "/pkg/LICENSE.BSD", MATCH_LICENSE_FILE, "dice-sorensen"),
        ])
        assert ids(result) == ["Apache-2.0", "BSD-2-Clause"]

    def test_the_weaker_of_two_declared_licenses_is_not_dropped(self, extractor):
        """Neither is the winner of a confidence contest. Both are declared."""
        result = extractor._stated_licenses([
            scanned("Apache-2.0", CATEGORY_DECLARED, 1.0, "/pkg/pyproject.toml", "package_metadata", "tag"),
            scanned("BSD-3-Clause", CATEGORY_DECLARED, 0.6, "/pkg/LICENSE.BSD", MATCH_LICENSE_FILE, "dice-sorensen"),
        ])
        assert ids(result) == ["Apache-2.0", "BSD-3-Clause"]


class TestAClaimHasToBeCheckable:
    """upmex reports a license with no file and calls near-misses exact."""

    def test_an_unsourced_license_no_file_supports_is_dropped(self, extractor):
        """urllib3: JSON arrives at 0.983 labelled exact. Nothing declares it."""
        result = extractor._stated_licenses([
            scanned("MIT", CATEGORY_DECLARED, 0.997, "/pkg/LICENSE.txt", MATCH_LICENSE_FILE, "dice-sorensen"),
            unsourced("MIT", 1.0),
            unsourced("JSON", 0.983),
        ])
        assert ids(result) == ["MIT"]

    def test_confidence_does_not_rescue_it(self, extractor):
        """The phantom outscores the real license and still loses."""
        result = extractor._stated_licenses([
            scanned("MIT", CATEGORY_DECLARED, 0.51, "/pkg/LICENSE", MATCH_LICENSE_FILE, "dice-sorensen"),
            unsourced("BSD-4-Clause", 0.99),
        ])
        assert ids(result) == ["MIT"]

    def test_an_unsourced_license_a_file_does_support_is_kept(self, extractor):
        result = extractor._stated_licenses([
            scanned("BSD-3-Clause", CATEGORY_DECLARED, 1.0, "/pkg/LICENSE.rst", MATCH_LICENSE_FILE, "tag"),
            unsourced("BSD-3-Clause", 1.0),
            unsourced("BSD-4-Clause", 0.971),
        ])
        assert ids(result) == ["BSD-3-Clause"]
        assert len(result) == 2, "the corroborating detection is kept, not merged away"

    def test_unsourced_licenses_are_all_kept_when_nothing_can_be_ranked(self, extractor):
        """No provenance anywhere is a reason to report more, not less."""
        result = extractor._stated_licenses([
            unsourced("MIT", 1.0),
            unsourced("Apache-2.0", 0.9),
        ])
        assert ids(result) == ["Apache-2.0", "MIT"]


class TestWhenNothingIsDeclared:
    def test_a_license_file_beats_a_keyword_hit(self, extractor):
        result = extractor._stated_licenses([
            scanned("ISC", CATEGORY_DETECTED, 0.95, "/pkg/COPYING", MATCH_LICENSE_FILE, "dice-sorensen"),
            scanned("JSON", CATEGORY_DETECTED, 0.85, "/pkg/README.md", "keyword", "keyword"),
        ])
        assert ids(result) == ["ISC"]

    def test_two_license_files_are_both_kept(self, extractor):
        result = extractor._stated_licenses([
            scanned("MIT", CATEGORY_DETECTED, 0.95, "/pkg/LICENSE-MIT", MATCH_LICENSE_FILE, "dice-sorensen"),
            scanned("Apache-2.0", CATEGORY_DETECTED, 0.94, "/pkg/LICENSE-APACHE", MATCH_LICENSE_FILE, "dice-sorensen"),
            scanned("JSON", CATEGORY_DETECTED, 0.85, "/pkg/CHANGES.rst", "keyword", "keyword"),
        ])
        assert ids(result) == ["Apache-2.0", "MIT"]

    def test_only_mentions_reports_the_best_one_not_all_of_them(self, extractor):
        result = extractor._stated_licenses([
            scanned("MIT", CATEGORY_DETECTED, 0.9, "/pkg/README.md", "keyword", "keyword"),
            scanned("JSON", CATEGORY_DETECTED, 0.85, "/pkg/HISTORY.md", "keyword", "keyword"),
            scanned("WTFPL", CATEGORY_DETECTED, 0.8, "/pkg/docs/index.md", "keyword", "keyword"),
        ])
        assert ids(result) == ["MIT"]

    def test_a_mention_is_still_reported_when_it_is_all_there_is(self, extractor):
        result = extractor._stated_licenses([
            scanned("MIT", CATEGORY_DETECTED, 0.9, "/pkg/README.md", "keyword", "keyword"),
        ])
        assert ids(result) == ["MIT"]


class TestBundledDependencyLicenses:
    """Code the package ships but did not write.

    typescript declares Apache-2.0 and ships a ThirdPartyNoticeText.txt carrying
    MIT and CC-BY-4.0 for code compiled into typescript.js. That code has no PURL
    of its own, so nothing else in the notices file will ever attribute it.
    """

    def test_a_bundled_license_is_reported_alongside_the_package_own(self, extractor):
        result = extractor._stated_licenses([
            scanned("Apache-2.0", CATEGORY_DECLARED, 1.0, "/pkg/package.json", "package_metadata", "tag"),
            scanned("CC-BY-4.0", CATEGORY_THIRD_PARTY, 0.85, "/pkg/ThirdPartyNoticeText.txt", "third_party_notice"),
        ])
        assert ids(result) == ["Apache-2.0", "CC-BY-4.0"]

    def test_a_bundled_license_is_not_treated_as_the_package_own(self, extractor):
        """It is kept, and it does not displace or outrank the real one."""
        result = extractor._stated_licenses([
            scanned("MIT", CATEGORY_DETECTED, 0.7, "/pkg/README.md", "keyword", "keyword"),
            scanned("GPL-3.0", CATEGORY_THIRD_PARTY, 1.0, "/pkg/vendor/NOTICE", "keyword", "keyword"),
        ])
        assert ids(result) == ["GPL-3.0", "MIT"]
        own = [lic for lic in result if lic.spdx_id == "MIT"]
        assert own and own[0].category == CATEGORY_DETECTED

    def test_a_bundled_license_file_does_not_suppress_the_package_own(self, extractor):
        """The vendored file is the more confident match. Both are reported."""
        result = extractor._stated_licenses([
            scanned("MIT", CATEGORY_DETECTED, 0.95, "/pkg/LICENSE", MATCH_LICENSE_FILE, "dice-sorensen"),
            scanned("GPL-3.0", CATEGORY_THIRD_PARTY, 1.0, "/pkg/vendor/LICENSE", MATCH_LICENSE_FILE, "tag"),
        ])
        assert ids(result) == ["GPL-3.0", "MIT"]

    def test_a_bundled_license_is_kept_when_it_is_all_there_is(self, extractor):
        result = extractor._stated_licenses([
            scanned("GPL-3.0", CATEGORY_THIRD_PARTY, 1.0, "/pkg/vendor/NOTICE", MATCH_LICENSE_FILE, "tag"),
        ])
        assert ids(result) == ["GPL-3.0"]

    def test_a_bundled_license_does_not_corroborate_an_unsourced_one(self, extractor):
        """A phantom must not be rescued by bundled code carrying that license."""
        result = extractor._stated_licenses([
            scanned("MIT", CATEGORY_DECLARED, 1.0, "/pkg/package.json", "package_metadata", "tag"),
            scanned("JSON", CATEGORY_THIRD_PARTY, 1.0, "/pkg/vendor/NOTICE", "third_party_notice"),
            unsourced("JSON", 0.983),
        ])
        own_and_unsourced = [lic for lic in result if not is_third_party_test(lic)]
        assert ids(own_and_unsourced) == ["MIT"]


def is_third_party_test(lic):
    from purl2notices.extractors.base import is_third_party
    return is_third_party(lic)


class TestNothingToDo:
    def test_no_detections_returns_nothing(self, extractor):
        assert extractor._stated_licenses([]) == []


class TestTheProvenanceReachesTheResult:
    """The rule is only auditable if the fields survive the extractor."""

    def test_osslili_fields_are_carried_onto_the_license(self):
        from purl2notices.extractors.osslili_extractor import OssliliExtractor
        import asyncio
        from pathlib import Path
        from unittest.mock import patch

        class FakeLicense:
            spdx_id = "JSON"
            name = "JSON"
            text = ""
            confidence = 0.85
            category = CATEGORY_DETECTED
            match_type = "keyword"
            detection_method = "keyword"
            source_file = "/pkg/History.md"

        class FakeResult:
            licenses = [FakeLicense()]
            copyrights = []
            package_name = "express"
            package_version = "4.18.2"

        class FakeDetector:
            def process_local_path(self, path):
                return FakeResult()

        import sys, types
        module = types.ModuleType("osslili")
        module.LicenseCopyrightDetector = FakeDetector
        with patch.dict(sys.modules, {"osslili": module}):
            result = asyncio.run(OssliliExtractor().extract_from_path(Path("/pkg")))

        assert len(result.licenses) == 1
        got = result.licenses[0]
        assert got.category == CATEGORY_DETECTED
        assert got.source_file == "/pkg/History.md"
        assert got.match_type == "keyword"
        assert got.detection_method == "keyword"


class TestDeduplicationDoesNotDestroyEvidence:
    """Records are reduced to one per license before anything ranks them."""

    def test_a_declaration_outranks_a_more_confident_mention(self, extractor):
        """The declaration scores lower and is still the one to keep.

        Left to confidence alone the mention wins, MIT becomes a mention, and
        the declared-only tier below is then entitled to drop it entirely.
        """
        from purl2notices.extractors.base import BaseExtractor

        kept = BaseExtractor.deduplicate_licenses(extractor, [
            scanned("MIT", CATEGORY_DECLARED, 0.6, "/pkg/package.json", "package_metadata", "tag"),
            scanned("MIT", CATEGORY_DETECTED, 0.9, "/pkg/README.md", "keyword", "keyword"),
        ])
        assert [lic.category for lic in kept] == [CATEGORY_DECLARED]

    def test_the_declared_license_survives_all_the_way_through(self, extractor):
        """End to end, on the exact shape that lost MIT before this fix."""
        from purl2notices.extractors.base import BaseExtractor

        deduped = BaseExtractor.deduplicate_licenses(extractor, [
            scanned("MIT", CATEGORY_DECLARED, 0.6, "/pkg/package.json", "package_metadata", "tag"),
            scanned("MIT", CATEGORY_DETECTED, 0.9, "/pkg/README.md", "keyword", "keyword"),
            scanned("Apache-2.0", CATEGORY_DECLARED, 1.0, "/pkg/pyproject.toml", "package_metadata", "tag"),
        ])
        assert ids(extractor._combine_licenses(deduped)) == ["Apache-2.0", "MIT"]

    def test_confidence_still_decides_between_equal_evidence(self, extractor):
        from purl2notices.extractors.base import BaseExtractor

        kept = BaseExtractor.deduplicate_licenses(extractor, [
            scanned("MIT", CATEGORY_DECLARED, 0.7, "/pkg/a.json", "package_metadata", "tag"),
            scanned("MIT", CATEGORY_DECLARED, 0.95, "/pkg/b.json", "package_metadata", "tag"),
        ])
        assert [lic.confidence for lic in kept] == [0.95]


class TestTheRecordThatSurvivesCanStillBeChecked:
    def test_an_unsourced_record_does_not_replace_a_sourced_one(self, extractor):
        """upmex reports no file and, unread, defaulted to a confidence of 1.0."""
        result = extractor._combine_licenses([
            scanned("MIT", CATEGORY_DECLARED, 0.97, "/pkg/LICENSE", MATCH_LICENSE_FILE, "dice-sorensen"),
            unsourced("MIT", 1.0),
        ])
        assert len(result) == 1
        assert result[0].source_file == "/pkg/LICENSE"

    def test_license_text_is_not_lost_when_the_better_record_arrives_second(self, extractor):
        """Two declarations of the same license: one carries the text, one wins.

        The LICENSE file match carries the real text at a lower confidence; the
        metadata tag is the more confident record and has no text at all. The
        record kept must not be the one that dropped the text.
        """
        with_text = scanned("MIT", CATEGORY_DECLARED, 0.5, "/pkg/LICENSE", MATCH_LICENSE_FILE, "dice-sorensen")
        with_text.text = "MIT License\n\nCopyright (c) 2009-2014 TJ Holowaychuk"
        more_confident = scanned("MIT", CATEGORY_DECLARED, 0.9, "/pkg/package.json", "package_metadata", "tag")

        result = extractor._combine_licenses([with_text, more_confident])
        assert len(result) == 1
        assert result[0].source_file == "/pkg/package.json"
        assert "TJ Holowaychuk" in (result[0].text or "")

    def test_license_text_is_not_lost_to_the_preference(self, extractor):
        sourced = scanned("MIT", CATEGORY_DECLARED, 0.97, "/pkg/LICENSE", MATCH_LICENSE_FILE, "dice-sorensen")
        carries_text = unsourced("MIT", 1.0)
        carries_text.text = "MIT License\n\nCopyright (c) 2009-2014 TJ Holowaychuk"

        result = extractor._combine_licenses([carries_text, sourced])
        assert len(result) == 1
        assert result[0].source_file == "/pkg/LICENSE"
        assert "TJ Holowaychuk" in result[0].text


class TestWhenNothingTraceableIsDeclared:
    def test_an_unsourced_license_is_kept(self, extractor):
        """Then no traceable detection read the metadata, and upmex may have."""
        result = extractor._stated_licenses([
            scanned("MIT", CATEGORY_DETECTED, 0.9, "/pkg/README.md", "keyword", "keyword"),
            unsourced("Apache-2.0", 1.0),
        ])
        assert ids(result) == ["Apache-2.0", "MIT"]

    def test_but_not_once_something_traceable_is_declared(self, extractor):
        result = extractor._stated_licenses([
            scanned("MIT", CATEGORY_DECLARED, 0.9, "/pkg/LICENSE", MATCH_LICENSE_FILE, "dice-sorensen"),
            unsourced("Apache-2.0", 1.0),
        ])
        assert ids(result) == ["MIT"]


class TestTheCategoryValueMatchesTheDetector:
    """A category spelled wrong here excludes nothing, and does so silently."""

    def test_third_party_is_spelled_the_way_osslili_spells_it(self):
        osslili_models = pytest.importorskip("osslili.core.models")
        emitted = {member.value for member in osslili_models.LicenseCategory}

        from purl2notices.extractors.base import THIRD_PARTY_CATEGORIES
        assert THIRD_PARTY_CATEGORIES & emitted, (
            f"none of {sorted(THIRD_PARTY_CATEGORIES)} is emitted by osslili, "
            f"which uses {sorted(emitted)}"
        )

    def test_declared_and_detected_are_spelled_that_way_too(self):
        osslili_models = pytest.importorskip("osslili.core.models")
        emitted = {member.value for member in osslili_models.LicenseCategory}
        assert {CATEGORY_DECLARED, CATEGORY_DETECTED} <= emitted


class TestUpmexProvenanceWhenItHasSome:
    """upmex carries a file path per license and usually leaves it empty.

    While it is empty, its licenses can only be corroborated. Where it is set,
    dropping the license for want of provenance it did supply would be a
    plain false negative.
    """

    def test_a_license_upmex_can_point_at_is_not_dropped(self, extractor):
        """osslili declares MIT from LICENSE; upmex declares Apache-2.0 from
        package.json, which osslili did not read. Both are real."""
        from_metadata = LicenseInfo(
            spdx_id="Apache-2.0", name="Apache-2.0", source=ExtractionSource.UPMEX,
            confidence=1.0, source_file="/pkg/package.json",
        )
        result = extractor._stated_licenses([
            scanned("MIT", CATEGORY_DECLARED, 0.99, "/pkg/LICENSE", MATCH_LICENSE_FILE, "dice-sorensen"),
            from_metadata,
        ])
        assert ids(result) == ["Apache-2.0", "MIT"]

    def test_a_license_upmex_cannot_point_at_still_needs_corroboration(self, extractor):
        result = extractor._stated_licenses([
            scanned("MIT", CATEGORY_DECLARED, 0.99, "/pkg/LICENSE", MATCH_LICENSE_FILE, "dice-sorensen"),
            unsourced("Apache-2.0", 1.0),
        ])
        assert ids(result) == ["MIT"]

    def test_the_extractor_maps_the_field_upmex_actually_uses(self):
        """The attribute is `file_path`, not `file` or `source_file`."""
        upmex_models = pytest.importorskip("upmex.core.models")
        import dataclasses

        fields = {f.name for f in dataclasses.fields(upmex_models.LicenseInfo)}
        assert "file_path" in fields, (
            f"upmex renamed its provenance field; it now has {sorted(fields)}"
        )

    def test_the_path_reaches_the_license(self, tmp_path):
        from purl2notices.extractors.upmex_extractor import UpmexExtractor
        import asyncio
        from unittest.mock import patch
        import upmex

        package = tmp_path / "thing-1.0.0.tgz"
        package.write_bytes(b"not really a tarball")

        class FakeUpmexLicense:
            spdx_id = "Apache-2.0"
            name = "Apache-2.0"
            text = None
            confidence = 0.88
            detection_method = "osslili_tag"
            file_path = "/pkg/package.json"

        class FakeMetadata:
            licenses = [FakeUpmexLicense()]
            copyright = None
            name = "thing"
            version = "1.0.0"

        class FakePackageExtractor:
            def __init__(self, config=None):
                pass

            def extract(self, path):
                return FakeMetadata()

        with patch.object(upmex, "PackageExtractor", FakePackageExtractor):
            result = asyncio.run(UpmexExtractor().extract_from_path(package))

        assert result.licenses, result.errors
        assert result.licenses[0].source_file == "/pkg/package.json"
        assert result.licenses[0].confidence == 0.88


class TestALicenseTextThatIsActuallyThere:
    """osslili reports `detected` + `text_similarity` when a whole license text
    matches inside a file not named like a license file, which is how a vendored
    source carrying a complete license reads. The text really is in the package.
    """

    def test_an_embedded_license_text_is_not_dropped(self, extractor):
        from purl2notices.extractors.base import MATCH_TEXT_SIMILARITY

        result = extractor._stated_licenses([
            scanned("MIT", CATEGORY_DECLARED, 1.0, "/pkg/package.json", "package_metadata", "tag"),
            scanned("BSD-3-Clause", CATEGORY_DETECTED, 0.96, "/pkg/vendor/foo.c",
                    MATCH_TEXT_SIMILARITY, "dice-sorensen"),
        ])
        assert ids(result) == ["BSD-3-Clause", "MIT"]

    def test_a_keyword_hit_in_the_same_place_is_still_dropped(self, extractor):
        """The distinction is whether the text is there, not where it is."""
        result = extractor._stated_licenses([
            scanned("MIT", CATEGORY_DECLARED, 1.0, "/pkg/package.json", "package_metadata", "tag"),
            scanned("BSD-3-Clause", CATEGORY_DETECTED, 0.96, "/pkg/vendor/foo.c",
                    "keyword", "keyword"),
        ])
        assert ids(result) == ["MIT"]

    def test_a_license_file_text_match_is_the_package_own(self, extractor):
        """osslili files that one as declared, so it goes through the ladder."""
        from purl2notices.extractors.base import MATCH_TEXT_SIMILARITY

        result = extractor._stated_licenses([
            scanned("MIT", CATEGORY_DECLARED, 0.99, "/pkg/LICENSE",
                    MATCH_TEXT_SIMILARITY, "dice-sorensen"),
            scanned("JSON", CATEGORY_DETECTED, 0.85, "/pkg/History.md", "keyword", "keyword"),
        ])
        assert ids(result) == ["MIT"]

    def test_osslili_still_emits_the_match_type_this_relies_on(self):
        """If osslili renames it, embedded texts start being dropped again."""
        detector = pytest.importorskip("osslili.detectors.license_detector")
        import inspect

        from purl2notices.extractors.base import MATCH_TEXT_SIMILARITY
        source = inspect.getsource(detector)
        assert f'"{MATCH_TEXT_SIMILARITY}"' in source, (
            f"osslili no longer emits {MATCH_TEXT_SIMILARITY!r}"
        )


class TestDeduplicationKeepsTheGroupsApart:
    """A mention must not be able to erase what a third-party notice recorded."""

    def test_a_readme_mention_does_not_erase_a_bundled_license(self, extractor):
        from purl2notices.extractors.base import BaseExtractor

        deduped = BaseExtractor.deduplicate_licenses(extractor, [
            scanned("Apache-2.0", CATEGORY_DECLARED, 1.0, "/pkg/package.json", "package_metadata", "tag"),
            scanned("MIT", CATEGORY_THIRD_PARTY, 0.9, "/pkg/ThirdPartyNoticeText.txt", "third_party_notice"),
            scanned("MIT", CATEGORY_DETECTED, 0.9, "/pkg/README.md", "keyword", "keyword"),
        ])
        assert ids(extractor._combine_licenses(deduped)) == ["Apache-2.0", "MIT"]

    def test_the_surviving_record_is_still_the_bundled_one(self, extractor):
        from purl2notices.extractors.base import BaseExtractor, is_third_party

        deduped = BaseExtractor.deduplicate_licenses(extractor, [
            scanned("MIT", CATEGORY_THIRD_PARTY, 0.9, "/pkg/ThirdPartyNoticeText.txt", "third_party_notice"),
            scanned("MIT", CATEGORY_DETECTED, 0.95, "/pkg/README.md", "keyword", "keyword"),
        ])
        assert any(is_third_party(lic) for lic in deduped)

    def test_duplicates_within_a_group_are_still_reduced(self, extractor):
        from purl2notices.extractors.base import BaseExtractor

        deduped = BaseExtractor.deduplicate_licenses(extractor, [
            scanned("MIT", CATEGORY_THIRD_PARTY, 0.7, "/pkg/NOTICE", "third_party_notice"),
            scanned("MIT", CATEGORY_THIRD_PARTY, 0.9, "/pkg/NOTICE", "third_party_notice"),
        ])
        assert len(deduped) == 1
        assert deduped[0].confidence == 0.9
