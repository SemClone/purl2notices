"""`--offline` at the command line.

The flag's promise is that a run makes no network request, so these tests
replace the two doors to the network with failures and then check the scan
still produces notices.
"""

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from purl2notices.cli import main


MIT_TEXT = """MIT License

Copyright (c) 2014 Node.js Foundation

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software.
"""


@pytest.fixture
def network_attempts(monkeypatch):
    """Record every attempt to reach the network and make it fail.

    Recording matters: the CLI catches exceptions per package and carries on,
    so a raised failure alone can leave a run looking successful. The test
    reads the list afterwards.
    """
    attempts = []

    import aiohttp

    def session_opened(*args, **kwargs):
        attempts.append("aiohttp.ClientSession")
        raise AssertionError("an HTTP session was opened")

    monkeypatch.setattr(aiohttp, "ClientSession", session_opened)

    import purl2src

    def resolver_called(*args, **kwargs):
        attempts.append("purl2src.get_download_url")
        raise AssertionError("purl2src was consulted")

    monkeypatch.setattr(purl2src, "get_download_url", resolver_called)

    return attempts


def write_tree(root: Path) -> None:
    pkg_dir = root / "node_modules" / "left-pad"
    pkg_dir.mkdir(parents=True)
    (pkg_dir / "package.json").write_text(
        '{"name": "left-pad", "version": "1.3.0", "license": "MIT"}',
        encoding="utf-8",
    )
    (pkg_dir / "LICENSE").write_text(MIT_TEXT, encoding="utf-8")


class TestOfflineFlag:
    def test_the_flag_is_documented(self):
        result = CliRunner().invoke(main, ['--help'])
        assert result.exit_code == 0
        assert '--offline' in result.output

    def test_a_directory_scan_needs_no_network(self, tmp_path, network_attempts):
        write_tree(tmp_path)
        output = tmp_path / "NOTICE.txt"

        result = CliRunner().invoke(main, [
            '--input', str(tmp_path),
            '--offline',
            '--no-cache',
            '--output', str(output),
        ])

        assert result.exit_code == 0, result.output
        assert network_attempts == []
        notices = output.read_text(encoding='utf-8')
        assert 'left-pad' in notices
        assert 'MIT' in notices

    def test_without_the_flag_the_same_scan_does_reach_the_network(
        self, tmp_path, network_attempts
    ):
        """The control. Without it, an offline run proves nothing: the scan
        might never have had a reason to download anything."""
        write_tree(tmp_path)

        CliRunner().invoke(main, [
            '--input', str(tmp_path),
            '--no-cache',
            '--output', str(tmp_path / "NOTICE.txt"),
        ])

        assert 'purl2src.get_download_url' in network_attempts

    def test_a_purl_input_is_refused_rather_than_silently_empty(self, tmp_path):
        """Nothing local answers a bare PURL, so an offline run that accepted
        one would report every package as unavailable and still exit as though
        it had produced notices."""
        result = CliRunner().invoke(main, [
            '--input', 'pkg:npm/express@4.18.0',
            '--offline',
            '--no-cache',
        ])

        assert result.exit_code == 1
        assert '--offline' in result.output

    def test_a_kissbom_input_is_refused_too(self, tmp_path):
        kissbom = tmp_path / "packages.txt"
        kissbom.write_text("pkg:npm/express@4.18.0\n", encoding="utf-8")

        result = CliRunner().invoke(main, [
            '--input', str(kissbom),
            '--offline',
            '--no-cache',
        ])

        assert result.exit_code == 1
        assert '--offline' in result.output

    def test_a_cache_input_is_still_allowed(self, tmp_path):
        """A cache file is local, so offline mode has no reason to refuse it."""
        from purl2notices.constants import CACHE_VERSION, CACHE_VERSION_PROPERTY

        cache = tmp_path / "test.cache.json"
        cache.write_text(json.dumps({
            "bomFormat": "CycloneDX",
            "specVersion": "1.6",
            "metadata": {"properties": [
                {"name": CACHE_VERSION_PROPERTY, "value": CACHE_VERSION}
            ]},
            "components": [{
                "type": "library",
                "name": "test",
                "version": "1.0.0",
                "purl": "pkg:npm/test@1.0.0",
                "licenses": [{"license": {"id": "MIT"}}],
            }],
        }), encoding="utf-8")

        result = CliRunner().invoke(main, [
            '--input', str(cache),
            '--offline',
        ])

        assert result.exit_code == 0, result.output
        assert 'MIT' in result.output or 'test@1.0.0' in result.output
