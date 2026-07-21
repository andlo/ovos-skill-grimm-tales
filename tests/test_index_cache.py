"""Tests for index caching and language fallback (ported pattern from
ovos-skill-andersen-tales)."""
import json
import time

from conftest import StoryFetchError


def test_refresh_index_uses_fresh_cache_without_scraping(skill):
    cache_file = skill._index_cache_filename()
    (skill.file_system.base / cache_file).write_text(
        json.dumps({"timestamp": time.time(), "index": {"Cached Tale": "http://x/cached"}})
    )
    skill.update_index = lambda: (_ for _ in ()).throw(AssertionError("should not scrape when cache is fresh"))

    skill.refresh_index()

    assert skill.index == {"Cached Tale": "http://x/cached"}


def test_refresh_index_falls_back_to_stale_cache_on_scrape_failure(skill):
    cache_file = skill._index_cache_filename()
    stale_timestamp = time.time() - skill.INDEX_CACHE_TTL - 1000
    (skill.file_system.base / cache_file).write_text(
        json.dumps({"timestamp": stale_timestamp, "index": {"Old Tale": "http://x/old"}})
    )

    def fail():
        raise StoryFetchError("network down")
    skill.update_index = fail

    skill.refresh_index()

    assert skill.index == {"Old Tale": "http://x/old"}


def test_refresh_index_writes_cache_after_successful_scrape(skill):
    skill.update_index = lambda: setattr(skill, "index", {"Fresh Tale": "http://x/fresh"})

    skill.refresh_index()

    cache_file = skill._index_cache_filename()
    cached = json.loads((skill.file_system.base / cache_file).read_text())
    assert cached["index"] == {"Fresh Tale": "http://x/fresh"}
