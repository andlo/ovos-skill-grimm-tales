"""Smoke tests + the load-time language gate in initialize()."""
from unittest.mock import MagicMock

from conftest import GrimmTales, StoryFetchError


def test_imports_cleanly():
    assert GrimmTales is not None
    assert issubclass(StoryFetchError, Exception)


def test_grimm_tales_is_an_ovos_skill():
    from ovos_workshop.skills import OVOSSkill
    assert issubclass(GrimmTales, OVOSSkill)


def test_initialize_stays_inert_for_unsupported_language(skill, monkeypatch):
    monkeypatch.setattr(type(skill), "lang", "pl-pl", raising=False)
    skill.refresh_index = MagicMock()
    skill.add_event = MagicMock()

    skill.initialize()

    skill.refresh_index.assert_not_called()
    skill.add_event.assert_not_called()
    assert skill.index == {}


def test_initialize_loads_normally_for_supported_language(skill, monkeypatch):
    monkeypatch.setattr(type(skill), "lang", "da-dk", raising=False)
    skill.refresh_index = MagicMock()
    skill.add_event = MagicMock()

    skill.initialize()

    skill.refresh_index.assert_called_once()
    assert skill.add_event.call_count == 3


def test_initialize_loads_normally_for_portuguese(skill, monkeypatch):
    """Grimm-only language (no Andersen equivalent) - see
    andlo/ovos-skill-fairytales#31 for the research behind this."""
    monkeypatch.setattr(type(skill), "lang", "pt-pt", raising=False)
    skill.refresh_index = MagicMock()
    skill.add_event = MagicMock()

    skill.initialize()

    skill.refresh_index.assert_called_once()


def test_update_index_uses_configured_language(skill, monkeypatch):
    monkeypatch.setattr(type(skill), "lang", "pt-pt", raising=False)
    requested_urls = []

    def fake_get_index(url):
        requested_urls.append(url)
        return {}

    skill.get_index = fake_get_index
    skill.update_index()

    assert requested_urls == ["https://www.grimmstories.com/pt/grimm_contos/list"]
