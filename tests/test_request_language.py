"""Each request's own language picks which index answers. On a HiveMind
hub one ovos-core serves users in several languages; secondary_langs
decides which indexes exist, the request decides which one answers."""
import pytest
from ovos_bus_client.message import Message
from ovos_bus_client.session import Session

from conftest import COMMON_READING_SEARCH_RESPONSE, COMMON_READING_FETCH_CONTENT_RESPONSE, COMMON_READING_PONG


@pytest.fixture
def hub(skill):
    """An en-us hub also configured for Danish."""
    skill.served = {"en", "da"}
    skill.indexes = {"en": {"Cinderella": "http://x/en/cinderella"},
                     "da": {"Askepot": "http://x/da/askepot"}}
    skill._meta = {"en": {"aliases": ["grimm"], "author": "Brothers Grimm", "collection": "EN"},
                   "da": {"aliases": ["grimm"], "author": "Brødrene Grimm", "collection": "DA"}}
    return skill


def request(msg_type, data, session_lang=None):
    context = {}
    if session_lang:
        context["session"] = Session("a-hivemind-client", lang=session_lang).serialize()
    return Message(msg_type, data, context)


def searched(skill, data, session_lang=None):
    skill.bus.emit.reset_mock()
    skill.handle_search(request("ovos.common_reading.search", data, session_lang))
    return [c[0][0].data for c in skill.bus.emit.call_args_list]


def test_danish_session_gets_the_danish_index(hub):
    sent = searched(hub, {"phrase": "askepot"}, session_lang="da-DK")
    assert [d["content_id"] for d in sent] == ["Askepot"]
    assert sent[0]["collection"] == "DA"


def test_lang_field_wins_over_the_session(hub):
    sent = searched(hub, {"phrase": "cinderella", "lang": "en-US"}, session_lang="da-DK")
    assert [d["content_id"] for d in sent] == ["Cinderella"]


def test_unconfigured_language_gets_no_answer(hub):
    assert searched(hub, {"phrase": "cinderella", "lang": "de-DE"}) == []


def test_no_language_falls_back_to_the_device_language(hub):
    """An older plugin sends neither 'lang' nor a session."""
    assert [d["content_id"] for d in searched(hub, {"phrase": "cinderella"})] == ["Cinderella"]


def test_title_matching_ignores_case(hub):
    sent = searched(hub, {"phrase": "CINDERELLA"})
    assert sent[0]["confidence"] == 1.0


def test_fetch_finds_a_title_in_any_served_index(hub):
    hub.get_story = lambda url: f"text from {url}"
    hub.skill_id = hub.skill_id
    hub.bus.emit.reset_mock()
    hub.handle_fetch_content(request(f"ovos.common_reading.fetch_content.{hub.skill_id}",
                                     {"content_id": "Askepot"}))
    sent = hub.bus.emit.call_args[0][0]
    assert sent.msg_type == COMMON_READING_FETCH_CONTENT_RESPONSE
    assert sent.data["paragraphs"] == ["text from http://x/da/askepot"]


def test_ping_only_for_a_served_language(hub):
    hub.bus.emit.reset_mock()
    hub.handle_ping(request("ovos.common_reading.ping", {"lang": "de-DE"}))
    hub.bus.emit.assert_not_called()
    hub.handle_ping(request("ovos.common_reading.ping", {"lang": "da-DK"}))
    sent = hub.bus.emit.call_args[0][0]
    assert sent.msg_type == COMMON_READING_PONG and sent.data["collection"] == "DA"
