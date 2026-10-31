"""The cache BOM has to name the version that actually wrote it (issue #44).

`metadata.tools[].version` is a provenance field: the only answer the file
gives to "which purl2notices produced this cache". It was the literal "0.1.0"
while the package shipped 2.0.0, so every cache ever written carried a false
one.

`__version__` was stale too (1.3.0 against a 2.0.0 pyproject), and that one is
what `purl2notices --version` prints. Reading the BOM off a second stale
literal would have moved the wrong answer rather than fixed it, so the version
is declared once and everything else derives from it.
"""

import re
from pathlib import Path

import pytest

import purl2notices
from purl2notices.cache import CacheManager
from purl2notices.config import Config
from purl2notices.models import Package

try:
    import tomllib
except ModuleNotFoundError:  # Python < 3.11
    import tomli as tomllib

REPO_ROOT = Path(__file__).resolve().parents[2]
PYPROJECT = REPO_ROOT / "pyproject.toml"
CHANGELOG = REPO_ROOT / "CHANGELOG.md"


def _bom_tool(temp_dir):
    manager = CacheManager(temp_dir / "test.cache.json")
    bom = manager._create_cyclonedx([
        Package(name="click", version="8.1.7", purl="pkg:pypi/click@8.1.7")
    ])
    tools = bom["metadata"]["tools"]
    assert len(tools) == 1, tools
    return tools[0]


class TestBomToolVersion:
    """What the written cache claims about its producer."""

    def test_bom_names_the_running_version(self, temp_dir):
        assert _bom_tool(temp_dir)["version"] == purl2notices.__version__

    def test_bom_does_not_carry_the_old_literal(self, temp_dir):
        # Guards the specific regression: a version equal to __version__ by
        # accident, because both were pinned back to the 0.1.0 literal.
        assert _bom_tool(temp_dir)["version"] != "0.1.0"
        assert purl2notices.__version__ != "0.1.0"

    def test_bom_still_names_the_tool(self, temp_dir):
        tool = _bom_tool(temp_dir)
        assert tool["name"] == "purl2notices"
        assert tool["vendor"] == "oscarvalenzuelab"


class TestNetworkUserAgent:
    """The same literal was pinned in the User-Agent we send to registries."""

    def test_user_agent_names_the_running_version(self):
        assert Config().get("network.user_agent") == (
            f"purl2notices/{purl2notices.__version__}"
        )


class TestVersionIsDeclaredOnce:
    """pyproject and the package must not be able to disagree."""

    def test_pyproject_agrees_with_dunder_version(self):
        with open(PYPROJECT, "rb") as f:
            config = tomllib.load(f)

        declared = config["project"].get("version")
        if declared is not None:
            # A second literal: it can only be right by someone remembering.
            assert declared == purl2notices.__version__
        else:
            # Derived: check it derives from this attribute specifically, not
            # from some other module that could drift the same way again.
            assert "version" in config["project"].get("dynamic", [])
            attr = config["tool"]["setuptools"]["dynamic"]["version"]["attr"]
            assert attr == "purl2notices.__version__"

    def test_changelog_agrees_with_dunder_version(self):
        """Deriving everything from one literal makes a wrong literal
        self-consistent: nothing in the code can contradict it. The changelog
        is the one record of the version that was actually released, so it is
        what the attribute is checked against."""
        released = [
            m.group(1)
            for m in re.finditer(
                r"^## \[([^\]]+)\]", CHANGELOG.read_text(encoding="utf-8"),
                re.MULTILINE,
            )
            if m.group(1).lower() != "unreleased"
        ]
        assert released, "no released version headings in CHANGELOG.md"
        assert released[0] == purl2notices.__version__
