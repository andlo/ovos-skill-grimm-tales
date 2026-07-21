"""Tests for fuzzy collection_hint and content_type matching."""
import pytest


@pytest.mark.parametrize("hint", ["grimm", "Grimm", "the brothers grimm", "brothers grimm", "grimm brothers"])
def test_matches_known_aliases(skill, hint):
    assert skill._matches_collection_hint(hint) is True


@pytest.mark.parametrize("hint", ["andersen", "hans christian andersen", "andrew lang"])
def test_does_not_match_other_collections(skill, hint):
    assert skill._matches_collection_hint(hint) is False


def test_none_hint_matches_everyone(skill):
    assert skill._matches_collection_hint(None) is True


def test_empty_string_hint_matches_everyone(skill):
    assert skill._matches_collection_hint("") is True


@pytest.mark.parametrize("content_type", ["story", "tale", "STORY", None, ""])
def test_matches_expected_content_types(skill, content_type):
    assert skill._matches_content_type(content_type) is True


@pytest.mark.parametrize("content_type", ["article", "poem", "news"])
def test_does_not_match_other_content_types(skill, content_type):
    assert skill._matches_content_type(content_type) is False
