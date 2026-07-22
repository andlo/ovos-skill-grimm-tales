"""Tests for _load_collection_meta() against the real locale/<lang>/
collection.voc + collection_meta.json files - not mocked, since the
whole point is verifying the actual bundled translations load and
parse correctly for every supported language (see
ovos-common-reading-pipeline-plugin#26)."""
import pytest


@pytest.mark.parametrize("lang,expected_author,expected_collection", [
    ("en-us", "the Brothers Grimm", "Grimm's Fairy Tales"),
    ("da-dk", "Brødrene Grimm", "Grimms Eventyr"),
    ("de-de", "die Gebrüder Grimm", "Grimms Märchen"),
    ("es-es", "los Hermanos Grimm", "Cuentos de los Hermanos Grimm"),
    ("fr-fr", "les Frères Grimm", "Contes des Frères Grimm"),
    ("it-it", "i Fratelli Grimm", "Fiabe dei Fratelli Grimm"),
    ("nl-nl", "de Gebroeders Grimm", "Grimm's Sprookjes"),
    ("pt-pt", "os Irmãos Grimm", "Contos dos Irmãos Grimm"),
])
def test_load_collection_meta_per_language(skill, monkeypatch, lang, expected_author, expected_collection):
    monkeypatch.setattr(type(skill), "lang", lang, raising=False)

    skill._load_collection_meta()

    assert skill._author_name == expected_author
    assert skill._collection_name == expected_collection
    assert "grimm" in skill._collection_aliases


def test_load_collection_meta_falls_back_for_english_variant(skill, monkeypatch):
    """en-gb has no dedicated locale folder - OVOS's own resource
    resolution (langcodes.tag_distance) should fall back to en-us
    automatically, with no special-casing needed here."""
    monkeypatch.setattr(type(skill), "lang", "en-gb", raising=False)

    skill._load_collection_meta()

    assert skill._author_name == "the Brothers Grimm"
    assert skill._collection_name == "Grimm's Fairy Tales"


def test_danish_alias_matches_danish_phrasing(skill, monkeypatch):
    """Regression guard for the actual bug this fixes: a Danish
    collection_hint should match against Danish aliases, not just the
    English ones - see ovos-common-reading-pipeline-plugin#26."""
    monkeypatch.setattr(type(skill), "lang", "da-dk", raising=False)
    skill._load_collection_meta()

    assert skill._matches_collection_hint("brødrene grimm") is True


def test_german_alias_matches_german_phrasing(skill, monkeypatch):
    monkeypatch.setattr(type(skill), "lang", "de-de", raising=False)
    skill._load_collection_meta()

    assert skill._matches_collection_hint("die gebrüder grimm") is True
