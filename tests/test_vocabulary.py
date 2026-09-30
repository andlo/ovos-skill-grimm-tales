"""ovos.common_reading.vocabulary: what this provider tells the pipeline it
can read. Since pipeline 0.3.0 a request only reaches a provider whose
words (a kind of text, a collection or a title) it names."""
from ovos_bus_client.message import Message


def _sent(skill):
    return [c.args[0] for c in skill.bus.emit.call_args_list
            if c.args[0].msg_type == "ovos.common_reading.vocabulary"]


def _prepare(skill):
    skill.served = {"en", "da"}
    skill._state("indexes").update({"en": {"The Frog Prince": "u1", "Rapunzel": "u2"},
                                    "da": {"Frøkongen": "u3"}})
    skill._meta_for("en")["aliases"] = ["grimm", "brothers grimm"]
    skill._meta_for("da")["aliases"] = ["grimm", "brødrene grimm"]


def test_vocabulary_is_collection_names_and_titles(skill):
    _prepare(skill)
    assert skill._vocabulary("da") == {"collections": ["grimm", "brødrene grimm"], "titles": ["Frøkongen"]}


def test_announced_for_every_language_served(skill):
    _prepare(skill)
    skill._announce_vocabulary()
    sent = _sent(skill)
    assert [m.data["lang"] for m in sent] == ["da", "en"]
    assert all(m.data["skill_id"] == skill.skill_id for m in sent)
    assert sorted(sent[1].data["titles"]) == ["Rapunzel", "The Frog Prince"]


def test_the_pipeline_asks_for_the_languages_it_needs(skill):
    _prepare(skill)
    skill.handle_vocabulary_get(Message("ovos.common_reading.vocabulary.get", {"langs": ["da-DK", "sv-SE"]}))
    assert [m.data["lang"] for m in _sent(skill)] == ["da"]
