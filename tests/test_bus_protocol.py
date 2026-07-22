"""Tests for the ovos.common_reading.* bus protocol handlers."""
from unittest.mock import MagicMock

from conftest import COMMON_READING_SEARCH_RESPONSE, COMMON_READING_FETCH_CONTENT_RESPONSE, COMMON_READING_PONG, StoryFetchError


def make_message(data=None, msg_type="ovos.common_reading.search"):
    m = MagicMock()
    m.data = data or {}
    m.msg_type = msg_type
    m.reply = MagicMock(side_effect=lambda mtype, d: MagicMock(msg_type=mtype, data=d))
    return m


def test_handle_search_matches_by_phrase(skill):
    skill.index = {"Cinderella": "http://x/cinderella", "The Frog King": "http://x/frog"}

    skill.handle_search(make_message({"phrase": "cinderella"}))

    sent = skill.bus.emit.call_args[0][0]
    assert sent.msg_type == COMMON_READING_SEARCH_RESPONSE
    assert sent.data["title"] == "Cinderella"
    assert sent.data["content_id"] == "Cinderella"
    assert sent.data["author"] == "the Brothers Grimm"
    assert sent.data["source"] == "grimmstories.com"
    assert 0.0 <= sent.data["confidence"] <= 1.0


def test_handle_search_stays_silent_on_empty_index(skill):
    skill.index = {}
    skill.handle_search(make_message({"phrase": "anything"}))
    skill.bus.emit.assert_not_called()


def test_handle_search_stays_silent_when_collection_hint_does_not_match(skill):
    skill.index = {"Cinderella": "http://x/cinderella"}
    skill.handle_search(make_message({"phrase": "cinderella", "collection_hint": "andersen"}))
    skill.bus.emit.assert_not_called()


def test_handle_search_responds_when_collection_hint_matches(skill):
    skill.index = {"Cinderella": "http://x/cinderella"}
    skill.handle_search(make_message({"phrase": "cinderella", "collection_hint": "the brothers grimm"}))
    skill.bus.emit.assert_called_once()


def test_handle_search_surprise_me_with_matching_hint_and_no_phrase(skill):
    skill.index = {"Cinderella": "http://x/cinderella"}
    skill.handle_search(make_message({"phrase": None, "collection_hint": "grimm"}))
    skill.bus.emit.assert_called_once()
    data = skill.bus.emit.call_args[0][0].data
    assert data["title"] == "Cinderella"
    assert data["confidence"] == 1.0


def test_handle_search_no_phrase_no_hint_stays_silent(skill):
    skill.index = {"Cinderella": "http://x/cinderella"}
    skill.handle_search(make_message({"phrase": None, "collection_hint": None}))
    skill.bus.emit.assert_not_called()


def test_handle_search_stays_silent_for_mismatched_content_type(skill):
    skill.index = {"Cinderella": "http://x/cinderella"}
    skill.handle_search(make_message({"phrase": "cinderella", "content_type": "article"}))
    skill.bus.emit.assert_not_called()


def test_handle_search_responds_for_matching_content_type(skill):
    skill.index = {"Cinderella": "http://x/cinderella"}
    for content_type in ["story", "tale", "STORY"]:
        skill.bus.emit.reset_mock()
        skill.handle_search(make_message({"phrase": "cinderella", "content_type": content_type}))
        skill.bus.emit.assert_called_once()


def test_handle_fetch_content_success(skill):
    skill.index = {"Cinderella": "http://x/cinderella"}
    skill.get_story = MagicMock(return_value="Once upon a time.\n\nThe end.")

    skill.handle_fetch_content(make_message({"content_id": "Cinderella"}))

    sent = skill.bus.emit.call_args[0][0]
    assert sent.msg_type == COMMON_READING_FETCH_CONTENT_RESPONSE
    assert sent.data["paragraphs"] == ["Once upon a time.", "The end."]


def test_handle_fetch_content_unknown_id_returns_empty(skill):
    skill.index = {}
    skill.handle_fetch_content(make_message({"content_id": "Nonexistent"}))
    sent = skill.bus.emit.call_args[0][0]
    assert sent.data["paragraphs"] == []


def test_handle_fetch_content_fetch_error_returns_empty(skill):
    skill.index = {"Cinderella": "http://x/cinderella"}
    skill.get_story = MagicMock(side_effect=StoryFetchError("boom"))

    skill.handle_fetch_content(make_message({"content_id": "Cinderella"}))

    sent = skill.bus.emit.call_args[0][0]
    assert sent.data["paragraphs"] == []


def test_handle_ping_replies_with_pong(skill):
    skill.handle_ping(make_message())

    sent = skill.bus.emit.call_args[0][0]
    assert sent.msg_type == COMMON_READING_PONG
    assert sent.data["skill_id"] == skill.skill_id
    assert sent.data["collection"] == "Grimm's Fairy Tales"


def test_handle_ping_does_not_touch_the_index(skill):
    skill.index = None

    skill.handle_ping(make_message())

    skill.bus.emit.assert_called_once()
