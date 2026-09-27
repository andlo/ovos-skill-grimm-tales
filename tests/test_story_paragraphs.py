"""grimmstories.com puts each paragraph in its own <div class="s"> and separates
verse lines with <br>: both must survive into what gets read."""
from bs4 import BeautifulSoup

from conftest import _module

story_paragraphs = _module.story_paragraphs

PAGE = """<div itemprop="text"><div class="s">It was lovely summer weather
in the country.</div><div class="s">"Quack, quack," said the mother.</div><div class="s">Shiver and quiver,<br/>my little tree,<br />silver and gold<br>throw down over me.</div><div class="s">   </div></div>"""


def _container(html=PAGE):
    return BeautifulSoup(html, "html.parser").find("div", {"itemprop": "text"})


def test_each_div_is_a_paragraph():
    paragraphs = story_paragraphs(_container())
    assert len(paragraphs) == 3
    assert paragraphs[0] == "It was lovely summer weather in the country."
    assert paragraphs[1] == '"Quack, quack," said the mother.'


def test_verse_keeps_one_line_per_line():
    assert story_paragraphs(_container())[2] == \
        "Shiver and quiver,\nmy little tree,\nsilver and gold\nthrow down over me."


def test_page_without_paragraph_divs_is_one_paragraph():
    assert story_paragraphs(_container('<div itemprop="text">Just  some\n text.</div>')) == ["Just some text."]


def test_get_story_joins_paragraphs_for_the_fetch_handler(skill, monkeypatch):
    monkeypatch.setattr(skill, "get_soup", lambda url: BeautifulSoup(PAGE, "html.parser"))
    text = skill.get_story("http://x/story")
    assert [p for p in text.split("\n\n") if p.strip()] == story_paragraphs(_container())
