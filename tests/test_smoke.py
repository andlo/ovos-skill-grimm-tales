"""Smoke tests + language fallback in update_index()."""
from conftest import GrimmTales, StoryFetchError


def test_imports_cleanly():
    assert GrimmTales is not None
    assert issubclass(StoryFetchError, Exception)


def test_grimm_tales_is_an_ovos_skill():
    from ovos_workshop.skills import OVOSSkill
    assert issubclass(GrimmTales, OVOSSkill)


def test_update_index_falls_back_to_english_for_unsupported_language(skill, monkeypatch):
    monkeypatch.setattr(type(skill), "lang", "xx-xx", raising=False)
    requested_urls = []

    def fake_get_index(url):
        requested_urls.append(url)
        return {}

    skill.get_index = fake_get_index
    skill.update_index()

    assert requested_urls == ["https://www.grimmstories.com/en/grimm_fairy-tales/list"]


def test_update_index_supports_portuguese(skill, monkeypatch):
    """Grimm-only language (no Andersen equivalent) - see
    andlo/ovos-skill-fairytales#31 for the research behind this."""
    monkeypatch.setattr(type(skill), "lang", "pt-pt", raising=False)
    requested_urls = []

    def fake_get_index(url):
        requested_urls.append(url)
        return {}

    skill.get_index = fake_get_index
    skill.update_index()

    assert requested_urls == ["https://www.grimmstories.com/pt/grimm_contos/list"]
