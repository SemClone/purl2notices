"""The license text emitted is the one the package ships (issue #38).

osslili names the file a license was found in but does not carry its contents,
so purl2notices fell back to the SPDX template and emitted it with `<year>` and
`<copyright holders>` still literal, next to the real holders it had already
detected.

Where osslili scanned an archive, the name it reports is a path inside that
archive rather than one on disk, so both shapes have to be read.
"""

import io
import tarfile
import zipfile

import pytest

from purl2notices.extractors.osslili_extractor import OssliliExtractor


class FakeDetection:
    """Stands in for one of osslili's license objects."""

    def __init__(self, spdx_id, source_file, match_type, text=""):
        self.spdx_id = spdx_id
        self.name = spdx_id
        self.source_file = str(source_file) if source_file else None
        self.match_type = match_type
        self.text = text
        self.confidence = 0.9
        self.category = "declared"
        self.detection_method = "test"


MIT_AS_SHIPPED = """(The MIT License)

Copyright (c) 2009-2014 TJ Holowaychuk <tj@vision-media.ca>
Copyright (c) 2013-2014 Roman Shtylman <shtylman+expressjs@gmail.com>

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction.
"""


@pytest.fixture
def extractor():
    return OssliliExtractor()


def _tgz(tmp_path, members):
    archive = tmp_path / "pkg.tgz"
    with tarfile.open(archive, "w:gz") as tf:
        for name, body in members.items():
            data = body.encode()
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))
    return archive


class TestFromDirectory:
    def test_license_file_contents_are_read(self, extractor, tmp_path):
        lic = tmp_path / "LICENSE"
        lic.write_text(MIT_AS_SHIPPED, encoding="utf-8")

        text = extractor._shipped_license_text(
            FakeDetection("MIT", lic, "license_file"), tmp_path
        )

        assert text == MIT_AS_SHIPPED
        assert "<copyright holders>" not in text
        assert "TJ Holowaychuk" in text

    def test_relative_name_is_resolved_against_the_scanned_root(self, extractor, tmp_path):
        (tmp_path / "package").mkdir()
        (tmp_path / "package" / "LICENSE").write_text(MIT_AS_SHIPPED, encoding="utf-8")

        assert extractor._shipped_license_text(
            FakeDetection("MIT", "package/LICENSE", "license_file"), tmp_path
        ) == MIT_AS_SHIPPED

    def test_package_metadata_is_not_read_as_license_text(self, extractor, tmp_path):
        meta = tmp_path / "package.json"
        meta.write_text('{"name": "express", "license": "MIT"}', encoding="utf-8")

        assert extractor._shipped_license_text(
            FakeDetection("MIT", meta, "package_metadata"), tmp_path
        ) is None

    def test_text_already_present_is_kept(self, extractor, tmp_path):
        lic = tmp_path / "LICENSE"
        lic.write_text("on disk", encoding="utf-8")

        assert extractor._shipped_license_text(
            FakeDetection("MIT", lic, "license_file", text="from detector"), tmp_path
        ) is None

    def test_missing_file_is_not_an_error(self, extractor, tmp_path):
        assert extractor._shipped_license_text(
            FakeDetection("MIT", tmp_path / "nope" / "LICENSE", "license_file"), tmp_path
        ) is None

    def test_no_source_file_is_not_an_error(self, extractor, tmp_path):
        assert extractor._shipped_license_text(
            FakeDetection("MIT", None, "license_file"), tmp_path
        ) is None

    def test_absurdly_large_file_is_declined(self, extractor, tmp_path):
        lic = tmp_path / "LICENSE"
        lic.write_text("x" * (extractor.MAX_LICENSE_TEXT_BYTES + 1), encoding="utf-8")

        assert extractor._shipped_license_text(
            FakeDetection("MIT", lic, "license_file"), tmp_path
        ) is None

    def test_directory_is_declined(self, extractor, tmp_path):
        d = tmp_path / "LICENSES"
        d.mkdir()
        assert extractor._shipped_license_text(
            FakeDetection("MIT", d, "license_file"), tmp_path
        ) is None

    def test_escaping_the_scanned_root_is_declined(self, extractor, tmp_path):
        """A name pointing outside what was scanned is not this package's license."""
        outside = tmp_path.parent / "outside-LICENSE"
        outside.write_text("not ours", encoding="utf-8")
        root = tmp_path / "root"
        root.mkdir()

        assert extractor._shipped_license_text(
            FakeDetection("MIT", "../outside-LICENSE", "license_file"), root
        ) is None


class TestFromArchive:
    """osslili reports a member path when it scans an archive, not a disk path."""

    def test_tar_member_is_read(self, extractor, tmp_path):
        archive = _tgz(tmp_path, {
            "package/package.json": '{"license": "MIT"}',
            "package/LICENSE": MIT_AS_SHIPPED,
        })

        text = extractor._shipped_license_text(
            FakeDetection("MIT", "package/LICENSE", "license_file"), archive
        )

        assert text == MIT_AS_SHIPPED
        assert "<copyright holders>" not in text

    def test_zip_member_is_read(self, extractor, tmp_path):
        archive = tmp_path / "pkg.whl"
        with zipfile.ZipFile(archive, "w") as zf:
            zf.writestr("pkg-1.0.dist-info/LICENSE", MIT_AS_SHIPPED)

        assert extractor._shipped_license_text(
            FakeDetection("MIT", "pkg-1.0.dist-info/LICENSE", "license_file"), archive
        ) == MIT_AS_SHIPPED

    def test_missing_member_is_not_an_error(self, extractor, tmp_path):
        archive = _tgz(tmp_path, {"package/README": "hi"})

        assert extractor._shipped_license_text(
            FakeDetection("MIT", "package/LICENSE", "license_file"), archive
        ) is None

    def test_oversized_member_is_declined(self, extractor, tmp_path):
        archive = _tgz(tmp_path, {
            "package/LICENSE": "x" * (extractor.MAX_LICENSE_TEXT_BYTES + 1),
        })

        assert extractor._shipped_license_text(
            FakeDetection("MIT", "package/LICENSE", "license_file"), archive
        ) is None

    def test_a_member_that_is_not_a_file_is_declined(self, extractor, tmp_path):
        archive = tmp_path / "pkg.tgz"
        with tarfile.open(archive, "w:gz") as tf:
            info = tarfile.TarInfo("package/LICENSE")
            info.type = tarfile.DIRTYPE
            tf.addfile(info)

        assert extractor._shipped_license_text(
            FakeDetection("MIT", "package/LICENSE", "license_file"), archive
        ) is None

    def test_a_corrupt_archive_is_not_an_error(self, extractor, tmp_path):
        archive = tmp_path / "pkg.tgz"
        archive.write_bytes(b"not an archive at all")

        assert extractor._shipped_license_text(
            FakeDetection("MIT", "package/LICENSE", "license_file"), archive
        ) is None


class TestDedupeKeepsTheText:
    """Reducing two records for one license must not throw the text away.

    Only one of osslili's records for a license names the file, so it is the
    only one carrying the shipped text. If it loses the dedupe, the text goes
    with it and the template is all that is left.
    """

    def _info(self, **kw):
        from purl2notices.extractors.base import LicenseInfo, ExtractionSource
        base = dict(spdx_id="MIT", name="MIT", text="", source=ExtractionSource.OSSLILI,
                    confidence=0.8, category="declared", match_type=None,
                    detection_method="test", source_file=None)
        base.update(kw)
        return LicenseInfo(**base)

    def test_text_survives_when_the_record_holding_it_loses(self, extractor):
        """The winner keeps its provenance and gains the text it lacked."""
        with_text = self._info(match_type="license_file", source_file="package/LICENSE",
                               text=MIT_AS_SHIPPED, confidence=0.8)
        without = self._info(match_type="package_metadata",
                             source_file="package/package.json", confidence=0.95)

        result = extractor.deduplicate_licenses([without, with_text])

        assert len(result) == 1
        assert result[0].text == MIT_AS_SHIPPED
        assert result[0].match_type == "package_metadata"

    def test_text_survives_when_the_record_holding_it_wins(self, extractor):
        with_text = self._info(match_type="license_file", source_file="package/LICENSE",
                               text=MIT_AS_SHIPPED, confidence=0.95)
        without = self._info(match_type="package_metadata", confidence=0.8)

        result = extractor.deduplicate_licenses([without, with_text])

        assert len(result) == 1
        assert result[0].text == MIT_AS_SHIPPED

    def test_the_longer_text_is_kept(self, extractor):
        short = self._info(match_type="license_file", text="MIT", confidence=0.95)
        full = self._info(match_type="license_file", text=MIT_AS_SHIPPED, confidence=0.8)

        result = extractor.deduplicate_licenses([short, full])

        assert len(result) == 1
        assert result[0].text == MIT_AS_SHIPPED


class TestTemplateIsALastResort:
    """The SPDX template must not outrank the text the package ships.

    Every license record with no text of its own is given the bundled SPDX
    template, so both a real and a template record exist for the same id. Which
    one the notices file showed came down to their order in the list.
    """

    def _core(self):
        from purl2notices.core import Purl2Notices
        from purl2notices.config import Config
        return Purl2Notices(Config())

    def _pkg(self, texts):
        from purl2notices.models import Package, License
        return Package(
            name="p", version="1", purl="pkg:npm/p@1",
            licenses=[License(spdx_id="MIT", name="MIT", text=t, source="test")
                      for t in texts],
        )

    def _bundled_mit(self):
        from pathlib import Path
        import purl2notices
        return (Path(purl2notices.__file__).parent / "data" / "licenses" / "MIT.txt").read_text()

    def test_shipped_text_wins_over_the_template(self):
        core = self._core()
        bundled = self._bundled_mit()

        # The template record first, which is the order that used to lose.
        texts = core._load_license_texts([self._pkg([bundled, MIT_AS_SHIPPED])])

        assert texts["MIT"] == MIT_AS_SHIPPED
        assert "<copyright holders>" not in texts["MIT"]

    def test_shipped_text_wins_regardless_of_order(self):
        core = self._core()
        bundled = self._bundled_mit()

        texts = core._load_license_texts([self._pkg([MIT_AS_SHIPPED, bundled])])

        assert texts["MIT"] == MIT_AS_SHIPPED

    def test_template_is_used_when_nothing_was_shipped(self):
        core = self._core()
        bundled = self._bundled_mit()

        texts = core._load_license_texts([self._pkg([bundled])])

        assert texts["MIT"] == bundled


class TestArchiveMemberShapes:
    """Member shapes that are not a license file the package ships."""

    def test_zip_symlink_member_is_declined(self, extractor, tmp_path):
        """Reading a symlink entry yields the link target, not a license.

        tarfile refuses one through isfile(); zipfile does not, so it has to be
        refused explicitly.
        """
        import stat as stat_mod

        archive = tmp_path / "pkg.zip"
        with zipfile.ZipFile(archive, "w") as zf:
            info = zipfile.ZipInfo("pkg/LICENSE")
            info.external_attr = (stat_mod.S_IFLNK | 0o777) << 16
            zf.writestr(info, "../../../etc/passwd")

        assert extractor._shipped_license_text(
            FakeDetection("MIT", "pkg/LICENSE", "license_file"), archive
        ) is None

    def test_ordinary_zip_member_is_still_read(self, extractor, tmp_path):
        """The symlink guard must not refuse a normal entry."""
        archive = tmp_path / "pkg.zip"
        with zipfile.ZipFile(archive, "w") as zf:
            zf.writestr("pkg/LICENSE", MIT_AS_SHIPPED)

        assert extractor._shipped_license_text(
            FakeDetection("MIT", "pkg/LICENSE", "license_file"), archive
        ) == MIT_AS_SHIPPED

    def test_tar_symlink_member_is_declined(self, extractor, tmp_path):
        archive = tmp_path / "pkg.tgz"
        with tarfile.open(archive, "w:gz") as tf:
            info = tarfile.TarInfo("package/LICENSE")
            info.type = tarfile.SYMTYPE
            info.linkname = "../../../etc/passwd"
            tf.addfile(info)

        assert extractor._shipped_license_text(
            FakeDetection("MIT", "package/LICENSE", "license_file"), archive
        ) is None

    def test_absolute_member_name_is_looked_up_relative(self, extractor, tmp_path):
        """A leading slash is stripped, so the lookup stays inside the archive."""
        archive = _tgz(tmp_path, {"package/LICENSE": MIT_AS_SHIPPED})

        assert extractor._shipped_license_text(
            FakeDetection("MIT", "/package/LICENSE", "license_file"), archive
        ) == MIT_AS_SHIPPED


class TestOneTextPerLicenseId:
    """Packages grouped under one license id must not borrow each other's text.

    The grouped view holds one text per license id. When two packages ship
    different texts for the same id, naming one of them makes the other
    package's entry claim copyright holders that are not its own.
    """

    def _core(self):
        from purl2notices.core import Purl2Notices
        from purl2notices.config import Config
        return Purl2Notices(Config())

    def _pkg(self, name, text):
        from purl2notices.models import Package, License
        return Package(
            name=name, version="1", purl=f"pkg:npm/{name}@1",
            licenses=[License(spdx_id="MIT", name="MIT", text=text, source="test")],
        )

    def _bundled_mit(self):
        from pathlib import Path
        import purl2notices
        return (Path(purl2notices.__file__).parent / "data" / "licenses" / "MIT.txt").read_text()

    LODASH_MIT = "MIT License\n\nCopyright OpenJS Foundation and other contributors\n"

    def test_a_package_that_ships_nothing_has_not_agreed(self):
        """It is unknown, not consenting to another package's holders."""
        core = self._core()
        texts = core._load_license_texts([
            self._pkg("express", MIT_AS_SHIPPED),
            self._pkg("other", self._bundled_mit()),
        ])
        assert texts["MIT"] == self._bundled_mit()
        assert "TJ Holowaychuk" not in texts["MIT"]

    def test_a_single_package_still_shows_what_it_ships(self):
        """The reported case in #38: one package, its own license text."""
        core = self._core()
        texts = core._load_license_texts([self._pkg("express", MIT_AS_SHIPPED)])
        assert texts["MIT"] == MIT_AS_SHIPPED

    def test_agreeing_shipped_texts_are_used(self):
        core = self._core()
        texts = core._load_license_texts([
            self._pkg("a", MIT_AS_SHIPPED),
            self._pkg("b", MIT_AS_SHIPPED),
        ])
        assert texts["MIT"] == MIT_AS_SHIPPED

    def test_differing_shipped_texts_fall_back_to_the_canonical_license(self):
        """Neither package's holders may stand in for the other's."""
        core = self._core()
        texts = core._load_license_texts([
            self._pkg("express", MIT_AS_SHIPPED),
            self._pkg("lodash", self.LODASH_MIT),
        ])

        assert texts["MIT"] == self._bundled_mit()
        assert "TJ Holowaychuk" not in texts["MIT"]
        assert "OpenJS Foundation" not in texts["MIT"]


class TestTextIdentity:
    """Two copies of one license must not read as disagreeing over whitespace."""

    def _core(self):
        from purl2notices.core import Purl2Notices
        from purl2notices.config import Config
        return Purl2Notices(Config())

    def _pkg(self, name, text):
        from purl2notices.models import Package, License
        return Package(
            name=name, version="1", purl=f"pkg:npm/{name}@1",
            licenses=[License(spdx_id="MIT", name="MIT", text=text, source="test")],
        )

    def test_crlf_and_lf_are_the_same_text(self):
        core = self._core()
        texts = core._load_license_texts([
            self._pkg("a", MIT_AS_SHIPPED),
            self._pkg("b", MIT_AS_SHIPPED.replace("\n", "\r\n")),
        ])
        assert "TJ Holowaychuk" in texts["MIT"]

    def test_trailing_whitespace_is_the_same_text(self):
        core = self._core()
        padded = "\n".join(line + "   " for line in MIT_AS_SHIPPED.splitlines())
        texts = core._load_license_texts([
            self._pkg("a", MIT_AS_SHIPPED),
            self._pkg("b", padded),
        ])
        assert "TJ Holowaychuk" in texts["MIT"]

    def test_no_canonical_fallback_means_no_text_rather_than_someone_elses(self):
        """An id purl2notices ships no template for cannot borrow one package's."""
        from purl2notices.models import Package, License
        core = self._core()

        def pkg(name, text):
            return Package(name=name, version="1", purl=f"pkg:npm/{name}@1",
                           licenses=[License(spdx_id="LicenseRef-Custom", name="LicenseRef-Custom",
                                             text=text, source="test")])

        texts = core._load_license_texts([pkg("a", "text A"), pkg("b", "text B")])

        assert "LicenseRef-Custom" not in texts


class TestVendoredTextDoesNotBecomeTheOwnLicense:
    """A notice for vendored code must not stand in for the package's license."""

    def _combined(self):
        from purl2notices.extractors.combined_extractor import CombinedExtractor
        return CombinedExtractor()

    def _info(self, category, text, confidence=0.8, match_type="license_file"):
        from purl2notices.extractors.base import LicenseInfo, ExtractionSource
        return LicenseInfo(
            spdx_id="MIT", name="MIT", text=text, source=ExtractionSource.OSSLILI,
            confidence=confidence, category=category, match_type=match_type,
            detection_method="test", source_file="LICENSE",
        )

    def test_vendored_text_is_not_grafted_onto_the_packages_own_record(self):
        from purl2notices.extractors.base import CATEGORY_DECLARED
        own = self._info(CATEGORY_DECLARED, "", confidence=0.95)
        vendored = self._info("third-party", "Copyright (c) Somebody Else\n" * 20)

        result = self._combined()._combine_licenses([own, vendored])

        for lic in result:
            if lic.category == CATEGORY_DECLARED:
                assert "Somebody Else" not in (lic.text or "")

    def test_text_still_moves_between_records_of_the_same_provenance(self):
        from purl2notices.extractors.base import CATEGORY_DECLARED
        without = self._info(CATEGORY_DECLARED, "", confidence=0.95,
                             match_type="package_metadata")
        with_text = self._info(CATEGORY_DECLARED, MIT_AS_SHIPPED, confidence=0.8)

        result = self._combined()._combine_licenses([without, with_text])

        assert any(MIT_AS_SHIPPED in (lic.text or "") for lic in result)


class TestFormatterHonoursTheSameRule:
    """The formatter must not undo the decision made when texts were loaded."""

    def _pkg(self, name, text):
        from purl2notices.models import Package, License
        return Package(name=name, version="1", purl=f"pkg:npm/{name}@1",
                       licenses=[License(spdx_id="MIT", name="MIT",
                                         text=text, source="test")])

    def _format(self, packages):
        from purl2notices.formatter import NoticeFormatter
        # license_texts omitted, so the formatter's own fallback path runs.
        return NoticeFormatter().format(
            packages, format_type="text", group_by_license=True,
        )

    def test_disagreeing_package_texts_are_not_resolved_by_taking_the_first(self):
        out = self._format([
            self._pkg("a", "MIT License\n\nCopyright (c) Package A\n"),
            self._pkg("b", "MIT License\n\nCopyright (c) Package B\n"),
        ])

        assert "pkg:npm/a@1" in out, "the group should still render"
        assert "Package A" not in out
        assert "Package B" not in out
        assert "License text not available" in out

    def test_agreeing_package_texts_are_still_shown(self):
        shared = "MIT License\n\nCopyright (c) The Same People\n"
        out = self._format([self._pkg("a", shared), self._pkg("b", shared)])

        assert "The Same People" in out


class TestCarriedBoundary:
    """The vendored boundary is this class's own, not just third-party."""

    def _combined(self):
        from purl2notices.extractors.combined_extractor import CombinedExtractor
        return CombinedExtractor()

    def _info(self, category, text, match_type, confidence=0.8):
        from purl2notices.extractors.base import LicenseInfo, ExtractionSource
        return LicenseInfo(
            spdx_id="MIT", name="MIT", text=text, source=ExtractionSource.OSSLILI,
            confidence=confidence, category=category, match_type=match_type,
            detection_method="test", source_file="src/vendor/thing.c",
        )

    def test_a_whole_license_found_outside_a_license_file_is_not_grafted(self):
        """That shape is vendored code shipping its license, not the package's."""
        from purl2notices.extractors.base import (
            CATEGORY_DECLARED, CATEGORY_DETECTED, MATCH_TEXT_SIMILARITY,
        )
        own = self._info(CATEGORY_DECLARED, "", "package_metadata", confidence=0.95)
        vendored = self._info(CATEGORY_DETECTED,
                              "Copyright (c) Somebody Else\n" * 20,
                              MATCH_TEXT_SIMILARITY)

        result = self._combined()._combine_licenses([own, vendored])

        for lic in result:
            if lic.category == CATEGORY_DECLARED:
                assert "Somebody Else" not in (lic.text or "")
