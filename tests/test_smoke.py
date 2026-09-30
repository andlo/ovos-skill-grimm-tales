"""Smoke tests + the load-time language gate in initialize()."""
from unittest.mock import MagicMock

from conftest import GrimmTales, StoryFetchError


def test_imports_cleanly():
    assert GrimmTales is not None
    assert issubclass(StoryFetchError, Exception)


def test_grimm_tales_is_an_ovos_skill():
    from ovos_workshop.skills import OVOSSkill
    assert issubclass(GrimmTales, OVOSSkill)


def test_initialize_stays_inert_when_no_configured_language_is_supported(skill, monkeypatch):
    """Never even build an index or register bus events when none of
    the languages this installation is configured for (lang +
    secondary_langs) is one this provider serves - it doesn't translate."""
    monkeypatch.setattr(type(skill), "native_langs", ["pl-PL", "ja-JP"], raising=False)
    skill.refresh_index = MagicMock()
    skill.add_event = MagicMock()

    skill.initialize()

    skill.refresh_index.assert_not_called()
    skill.add_event.assert_not_called()
    assert skill.served == set()


def test_initialize_loads_normally_for_supported_language(skill, monkeypatch):
    monkeypatch.setattr(type(skill), "native_langs", ["da-DK"], raising=False)
    skill.refresh_index = MagicMock()
    skill._load_collection_meta = MagicMock()
    skill.add_event = MagicMock()

    skill.initialize()

    skill.refresh_index.assert_called_once_with(lang="da")
    skill._load_collection_meta.assert_called_once_with("da")
    assert skill.add_event.call_count == 4  # search, fetch, ping, vocabulary.get


def test_initialize_builds_an_index_per_configured_language(skill, monkeypatch):
    """A HiveMind hub lists the languages its users speak in
    secondary_langs: one index each, unsupported ones skipped."""
    monkeypatch.setattr(type(skill), "native_langs", ["en-US", "da-DK", "pl-PL"], raising=False)
    skill.refresh_index = MagicMock()
    skill._load_collection_meta = MagicMock()
    skill.add_event = MagicMock()

    skill.initialize()

    assert skill.served == {"en", "da"}
    assert sorted(c.kwargs["lang"] for c in skill.refresh_index.call_args_list) == ["da", "en"]
