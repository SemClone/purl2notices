"""A cache written before licenses were ranked must not be merged forward.

_merge_package only ever adds licenses to a cached entry, so a license the
current code no longer reports survives every later run. The users who most
need the ranking fix are the ones who already have a cache full of the licenses
it removes.
"""

import json

import pytest

from purl2notices.cache import CacheManager, StaleCacheError
from purl2notices.constants import (
    CACHE_FORMAT, CACHE_SPEC_VERSION, CACHE_VERSION, CACHE_VERSION_PROPERTY,
)


def write_cache(path, version):
    """A cache holding the phantom license this release removes."""
    properties = (
        [{"name": CACHE_VERSION_PROPERTY, "value": version}] if version else []
    )
    path.write_text(json.dumps({
        "bomFormat": CACHE_FORMAT,
        "specVersion": CACHE_SPEC_VERSION,
        "metadata": {"properties": properties},
        "components": [{
            "type": "library",
            "name": "express",
            "version": "4.18.2",
            "purl": "pkg:npm/express@4.18.2",
            "licenses": [
                {"license": {"id": "MIT"}},
                {"license": {"id": "JSON"}},
            ],
        }],
    }))


class TestAStaleCacheIsNotUsed:
    def test_a_cache_from_before_the_ranking_is_refused(self, tmp_path):
        cache = tmp_path / "project.cache.json"
        write_cache(cache, "1.0")
        with pytest.raises(StaleCacheError) as raised:
            CacheManager(cache).load()
        assert "1.0" in str(raised.value)
        assert "Regenerate" in str(raised.value)

    def test_a_cache_with_no_version_at_all_is_refused(self, tmp_path):
        cache = tmp_path / "project.cache.json"
        write_cache(cache, None)
        with pytest.raises(StaleCacheError):
            CacheManager(cache).load()

    def test_a_refusal_is_not_swallowed_as_a_read_failure(self, tmp_path):
        """load() catches everything else and returns []; this must escape."""
        cache = tmp_path / "project.cache.json"
        write_cache(cache, "1.0")
        try:
            CacheManager(cache).load()
        except StaleCacheError:
            return
        pytest.fail("a stale cache was read as an empty one")

    def test_an_unreadable_cache_is_still_only_a_warning(self, tmp_path):
        """The refusal must not turn every read problem into a crash."""
        cache = tmp_path / "project.cache.json"
        cache.write_text("{not json")
        assert CacheManager(cache).load() == []

    def test_a_current_cache_is_still_loaded(self, tmp_path):
        """The guard has to reject the old, not everything."""
        cache = tmp_path / "project.cache.json"
        write_cache(cache, CACHE_VERSION)
        packages = CacheManager(cache).load()
        assert [pkg.name for pkg in packages] == ["express"]

    def test_saving_over_a_stale_cache_rebuilds_it(self, tmp_path):
        """Where the cache is an optimisation, not the input, it is rebuilt."""
        from purl2notices.models import Package, License

        cache = tmp_path / "project.cache.json"
        write_cache(cache, "1.0")
        manager = CacheManager(cache)
        fresh = Package(
            purl="pkg:npm/express@4.18.2", name="express", version="4.18.2",
            licenses=[License(spdx_id="MIT", name="MIT", text="")],
        )
        merged = manager.merge([fresh])
        assert [lic.spdx_id for pkg in merged for lic in pkg.licenses] == ["MIT"]
        assert not any(
            lic.spdx_id == "JSON" for pkg in merged for lic in pkg.licenses
        )


class TestWhatWeWrite:
    def test_a_saved_cache_carries_the_current_version(self, tmp_path):
        cache = tmp_path / "out.cache.json"
        manager = CacheManager(cache)
        bom = manager._create_cyclonedx([])
        properties = bom["metadata"]["properties"]
        stamped = {
            prop["name"]: prop["value"] for prop in properties
        }
        assert stamped[CACHE_VERSION_PROPERTY] == CACHE_VERSION

    def test_a_real_save_then_load_survives_the_guard(self, tmp_path):
        """Through save(), not through the BOM builder.

        Checking the builder alone would pass even if save() mangled the
        metadata on the way out, which is the half that actually writes.
        """
        from purl2notices.models import Package, License

        cache = tmp_path / "out.cache.json"
        manager = CacheManager(cache)
        manager.save([Package(
            purl="pkg:npm/express@4.18.2", name="express", version="4.18.2",
            licenses=[License(spdx_id="MIT", name="MIT", text="")],
        )])

        reloaded = CacheManager(cache).load()
        assert [pkg.name for pkg in reloaded] == ["express"]


class TestTheVersionIsRead:
    def test_a_cache_with_other_properties_still_finds_the_version(self, tmp_path):
        cache = tmp_path / "c.json"
        cache.write_text(json.dumps({
            "bomFormat": CACHE_FORMAT,
            "specVersion": CACHE_SPEC_VERSION,
            "metadata": {"properties": [
                {"name": "something:else", "value": "x"},
                {"name": CACHE_VERSION_PROPERTY, "value": CACHE_VERSION},
            ]},
            "components": [],
        }))
        assert CacheManager(cache)._cache_version(json.loads(cache.read_text())) == CACHE_VERSION

    def test_a_cache_with_no_metadata_block_reads_as_unversioned(self, tmp_path):
        cache = tmp_path / "c.json"
        data = {"bomFormat": CACHE_FORMAT, "components": []}
        assert CacheManager(cache)._cache_version(data) is None
