"""Offline mode must scan what is on disk and never reach the network.

`--offline` exists for air-gapped and network-restricted runs, so "it happened
to work because nothing was reachable" is not the property under test. These
tests make any network call an error and then assert the scan still produces
packages, which is the only way to tell a skipped download from a failed one.
"""

import asyncio
from pathlib import Path

import pytest

from purl2notices.config import Config
from purl2notices.core import Purl2Notices
from purl2notices.extractors.base import (
    ExtractionResult, ExtractionSource, LicenseInfo,
    CATEGORY_DECLARED, MATCH_LICENSE_FILE,
)
from purl2notices.extractors.combined_extractor import CombinedExtractor


MIT_TEXT = """MIT License

Copyright (c) 2009-2014 TJ Holowaychuk

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction.
"""


def node_modules_tree(root: Path) -> Path:
    """A directory with one npm dependency carrying its own LICENSE file."""
    pkg_dir = root / "node_modules" / "express"
    pkg_dir.mkdir(parents=True)
    (pkg_dir / "package.json").write_text(
        '{"name": "express", "version": "4.18.0", "license": "MIT"}',
        encoding="utf-8",
    )
    (pkg_dir / "LICENSE").write_text(MIT_TEXT, encoding="utf-8")
    return pkg_dir


def offline_processor() -> Purl2Notices:
    config = Config()
    config.set("general.offline", True)
    return Purl2Notices(config)


class TestOfflineConfigurationReachesTheExtractor:
    def test_offline_is_off_by_default(self):
        processor = Purl2Notices()
        assert processor.offline is False
        assert processor.extractor.offline is False

    def test_the_config_flag_reaches_the_extractor(self):
        processor = offline_processor()
        assert processor.offline is True
        assert processor.extractor.offline is True


class TestOfflineExtractorRefusesTheNetwork:
    def test_a_purl_is_not_resolved_to_a_download_url(self, monkeypatch):
        extractor = CombinedExtractor(offline=True)

        async def must_not_run(purl):
            raise AssertionError(f"purl2src was consulted for {purl}")

        monkeypatch.setattr(
            extractor.purl2src, "extract_from_purl", must_not_run
        )

        result = asyncio.run(
            extractor.extract_from_purl("pkg:npm/express@4.18.0")
        )

        assert result.success is False
        assert any("offline" in error.lower() for error in result.errors)

    def test_a_generic_vcs_purl_is_not_fetched_either(self, monkeypatch):
        """The vcs_url branch builds its own download URL without purl2src, so
        guarding purl2src alone would leave this door open."""
        extractor = CombinedExtractor(offline=True)

        async def must_not_run(url, purl):
            raise AssertionError(f"download attempted: {url}")

        monkeypatch.setattr(extractor, "_download_package", must_not_run)

        purl = (
            "pkg:generic/thing@1.0.0"
            "?vcs_url=git%2Bhttps://github.com/owner/repo@v1.0.0"
        )
        result = asyncio.run(extractor.extract_from_purl(purl))

        assert result.success is False
        assert any("offline" in error.lower() for error in result.errors)

    def test_the_downloader_itself_refuses_to_open_a_session(self, monkeypatch):
        """Second guard: any caller reaching the downloader directly still
        makes no request.

        The attempt is recorded rather than raised. _download_package catches
        every exception and returns None, so a raised failure would be
        swallowed and the assertion on the return value alone would hold
        whether or not the request went out.
        """
        extractor = CombinedExtractor(offline=True)
        attempts = []

        import aiohttp

        def record_session(*args, **kwargs):
            attempts.append(args)
            raise AssertionError("an HTTP session was opened in offline mode")

        monkeypatch.setattr(aiohttp, "ClientSession", record_session)

        path = asyncio.run(
            extractor._download_package(
                "https://registry.example/express.tgz", "pkg:npm/express@4.18.0"
            )
        )

        assert attempts == []
        assert path is None

    def test_online_mode_still_consults_purl2src(self, monkeypatch):
        """The guard must not fire when it was not asked for."""
        extractor = CombinedExtractor(offline=False)
        consulted = []

        async def record(purl):
            consulted.append(purl)
            return ExtractionResult(
                success=False,
                errors=["no download URL found"],
                source=ExtractionSource.PURL2SRC,
            )

        monkeypatch.setattr(extractor.purl2src, "extract_from_purl", record)

        result = asyncio.run(
            extractor.extract_from_purl("pkg:npm/express@4.18.0")
        )

        assert consulted == ["pkg:npm/express@4.18.0"]
        assert result.errors == ["no download URL found"]


class TestOfflineDirectoryScan:
    def test_a_detected_purl_is_read_from_disk_not_downloaded(
        self, monkeypatch, temp_dir
    ):
        pkg_dir = node_modules_tree(temp_dir)
        processor = offline_processor()
        scanned = []

        async def record_path(path):
            scanned.append(Path(path))
            return ExtractionResult(
                success=True,
                source=ExtractionSource.OSSLILI,
                licenses=[
                    LicenseInfo(
                        spdx_id="MIT", name="MIT", text=MIT_TEXT,
                        source=ExtractionSource.OSSLILI, confidence=1.0,
                        category=CATEGORY_DECLARED,
                        source_file=str(pkg_dir / "LICENSE"),
                        match_type=MATCH_LICENSE_FILE,
                    )
                ],
            )

        async def must_not_batch(purl_list, parallel=4):
            raise AssertionError(f"downloads attempted for {purl_list}")

        monkeypatch.setattr(processor.extractor, "extract_from_path", record_path)
        monkeypatch.setattr(processor, "process_batch", must_not_batch)
        monkeypatch.setattr(
            processor, "_extract_source_code_only",
            lambda directory, skip_archives=True: _empty_scan(),
        )

        packages = processor.process_directory(temp_dir)

        # The package directory, not the package.json: a metadata file names
        # the package but the LICENSE sits beside it.
        assert pkg_dir.resolve() in {p.resolve() for p in scanned}

        express = [p for p in packages if p.name == "express"]
        assert len(express) == 1
        assert express[0].purl == "pkg:npm/express@4.18.0"
        assert [lic.spdx_id for lic in express[0].own_licenses] == ["MIT"]

    def test_online_mode_still_downloads_detected_purls(
        self, monkeypatch, temp_dir
    ):
        node_modules_tree(temp_dir)
        processor = Purl2Notices()
        batched = []

        async def record_batch(purl_list, parallel=4):
            batched.extend(purl_list)
            return []

        monkeypatch.setattr(processor, "process_batch", record_batch)
        monkeypatch.setattr(
            processor.extractor, "extract_from_path",
            lambda path: _empty_scan(),
        )
        monkeypatch.setattr(
            processor, "_extract_source_code_only",
            lambda directory, skip_archives=True: _empty_scan(),
        )

        processor.process_directory(temp_dir)

        assert batched == ["pkg:npm/express@4.18.0"]

    def test_an_archive_is_not_read_twice(self, monkeypatch, temp_dir):
        """A detection naming an archive and the archive sweep are the same
        file. Offline mode reads it once, under its detected coordinates."""
        import zipfile

        jar = temp_dir / "target" / "widget-1.2.3.jar"
        jar.parent.mkdir(parents=True)
        with zipfile.ZipFile(jar, "w") as zf:
            zf.writestr(
                "META-INF/maven/com.example/widget/pom.properties",
                "groupId=com.example\nartifactId=widget\nversion=1.2.3\n",
            )

        processor = offline_processor()
        scanned = []

        async def record_path(path):
            scanned.append(Path(path))
            return _empty_extraction()

        monkeypatch.setattr(processor.extractor, "extract_from_path", record_path)
        monkeypatch.setattr(
            processor, "_extract_source_code_only",
            lambda directory, skip_archives=True: _empty_scan(),
        )

        packages = processor.process_directory(temp_dir)

        assert [p.resolve() for p in scanned].count(jar.resolve()) == 1
        widget = [p for p in packages if p.name == "widget"]
        assert len(widget) == 1
        assert widget[0].purl == "pkg:maven/com.example/widget@1.2.3"


async def _empty_scan():
    return ExtractionResult(
        success=True, licenses=[], copyrights=[],
        source=ExtractionSource.OSSLILI,
    )


def _empty_extraction():
    return ExtractionResult(
        success=False, errors=["nothing found"],
        source=ExtractionSource.OSSLILI,
    )


class TestOneConfigDoesNotChangeAnother:
    """Setting offline on one Config must not set it on the next one.

    DEFAULT_CONFIG is a class attribute, so a shallow copy handed every Config
    the same nested dicts: one process scanning offline left the flag set for
    everything built after it.
    """

    def test_setting_offline_does_not_leak_into_a_new_config(self):
        first = Config()
        first.set("general.offline", True)

        assert Config().get("general.offline") is False

    def test_appending_an_exclude_pattern_does_not_leak_either(self):
        first = Config()
        first.get("scanning.exclude_patterns").append("*/leaked/*")

        assert "*/leaked/*" not in Config().get("scanning.exclude_patterns")
