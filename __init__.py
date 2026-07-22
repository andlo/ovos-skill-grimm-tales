"""
skill OVOS Grimm Tales
Copyright (C) 2026  Andreas Lorensen

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.

---

Provider skill for ovos-common-reading-pipeline-plugin: implements the
ovos.common_reading.* bus protocol and registers NO intents of its own.
See https://github.com/andlo/ovos-common-reading-pipeline-plugin for the
full protocol - this skill has no standalone voice interface, it needs
the pipeline plugin installed and configured to be useful.
"""

from ovos_workshop.skills import OVOSSkill
from ovos_utils.parse import match_one
from ovos_utils import classproperty
from ovos_utils.process_utils import RuntimeRequirements

import requests
from bs4 import BeautifulSoup
import time
import json
import random


class StoryFetchError(Exception):
    """Raised when a story/index page could not be fetched or parsed
    from grimmstories.com."""


COMMON_READING_SEARCH = "ovos.common_reading.search"
COMMON_READING_SEARCH_RESPONSE = "ovos.common_reading.search.response"
COMMON_READING_FETCH_CONTENT = "ovos.common_reading.fetch_content"  # + ".{this_skill_id}"
COMMON_READING_FETCH_CONTENT_RESPONSE = "ovos.common_reading.fetch_content.response"
COMMON_READING_PING = "ovos.common_reading.ping"
COMMON_READING_PONG = "ovos.common_reading.pong"

# names a user might call this collection via 'collection_hint' - matched
# fuzzily against, not required to be exact
COLLECTION_ALIASES = ["grimm", "the brothers grimm", "brothers grimm", "grimm brothers"]
COLLECTION_HINT_THRESHOLD = 0.85  # see ovos-common-reading-pipeline-plugin's README for why not lower
CONTENT_TYPES = ["story", "tale"]
AUTHOR_NAME = "the Brothers Grimm"
COLLECTION_NAME = "Grimm's Fairy Tales"
SOURCE_NAME = "grimmstories.com"

# grimmstories.com offers 20 languages total; we only support the ones
# also part of OVOS's actively-tracked language set (see
# andlo/ovos-skill-fairytales#31) - 7 shared with Andersen plus
# Portuguese (Grimm-only, no Andersen stories exist in Portuguese). This
# provider does NOT translate (unlike ovos-skill-ovosblog/
# ovos-skill-arxiv-papers) - a device set to any other language gets no
# response at all, decided once at load time (see initialize()).
SUPPORTED_LANGUAGES = {"da", "en", "de", "es", "fr", "it", "nl", "pt"}


class GrimmTales(OVOSSkill):

    INDEX_CACHE_TTL = 60 * 60 * 24 * 7  # 7 days

    @classproperty
    def runtime_requirements(self):
        return RuntimeRequirements(
            internet_before_load=True,
            network_before_load=True,
            requires_internet=True,
            requires_network=True,
            no_internet_fallback=True,
            no_network_fallback=True,
        )

    def initialize(self):
        lang = self.lang.split("-")[0]
        if lang not in SUPPORTED_LANGUAGES:
            self.log.info(
                f"{self.skill_id}: device language '{self.lang}' is not one of "
                f"{sorted(SUPPORTED_LANGUAGES)} that grimmstories.com supports, "
                f"and this provider does not translate - skill will stay inert "
                f"(no bus events registered, index not built)."
            )
            self.index = {}
            return
        self.index = {}
        self._story_text_cache = {}
        self.refresh_index()
        self.add_event(COMMON_READING_SEARCH, self.handle_search)
        self.add_event(f"{COMMON_READING_FETCH_CONTENT}.{self.skill_id}", self.handle_fetch_content)
        self.add_event(COMMON_READING_PING, self.handle_ping)

    def _index_cache_filename(self):
        lang = self.lang.split("-")[0]
        return f"index_{lang}.json"

    def _read_index_cache(self):
        cache_file = self._index_cache_filename()
        if not self.file_system.exists(cache_file):
            return None
        try:
            with self.file_system.open(cache_file, "r") as f:
                return json.load(f)
        except (OSError, ValueError) as e:
            self.log.warning(f"could not read story index cache: {e}")
            return None

    def _write_index_cache(self):
        cache_file = self._index_cache_filename()
        try:
            with self.file_system.open(cache_file, "w") as f:
                json.dump({"timestamp": time.time(), "index": self.index}, f)
        except OSError as e:
            self.log.warning(f"could not write story index cache: {e}")

    def refresh_index(self, force=False):
        cached = self._read_index_cache()
        if not force and cached and (time.time() - cached.get("timestamp", 0)) < self.INDEX_CACHE_TTL:
            self.index = cached.get("index", {})
            return
        try:
            self.update_index()
            self._write_index_cache()
        except StoryFetchError as e:
            self.log.error(f"Could not refresh story index: {e}")
            if cached:
                self.log.warning("Falling back to previously cached (possibly stale) story index")
                self.index = cached.get("index", {})

    def get_soup(self, url):
        try:
            r = requests.get(url, timeout=10)
            r.raise_for_status()
            r.encoding = r.apparent_encoding
            return BeautifulSoup(r.text, "html.parser")
        except requests.RequestException as e:
            raise StoryFetchError(f"failed to fetch {url}: {e}") from e

    def get_story(self, url):
        if url in self._story_text_cache:
            return self._story_text_cache[url]
        soup = self.get_soup(url)
        elements = soup.find_all("div", {'itemprop': ['text']})
        if not elements:
            raise StoryFetchError(f"story text not found at {url}")
        text = elements[0].text.strip()
        self._story_text_cache[url] = text
        return text

    def get_title(self, url):
        soup = self.get_soup(url)
        elements = soup.find_all("h2", {'itemprop': ['name']})
        if not elements:
            raise StoryFetchError(f"title not found at {url}")
        return elements[0].text.strip()

    def get_index(self, url):
        soup = self.get_soup(url)
        lists = soup.find_all("ul", {'class': ['list_link']})
        if not lists:
            raise StoryFetchError(f"story index not found at {url}")
        index = {}
        for link in lists[0].find_all("a"):
            index[link.text] = link.get("href")
        return index

    def update_index(self):
        # initialize() already checked self.lang is in SUPPORTED_LANGUAGES
        # before this is ever called, so no fallback is needed here.
        url_grimm = {'da': 'https://www.grimmstories.com/da/grimm_eventyr/',
                     'en': 'https://www.grimmstories.com/en/grimm_fairy-tales/',
                     'de': 'https://www.grimmstories.com/de/grimm_maerchen/',
                     'es': 'https://www.grimmstories.com/es/grimm_cuentos/',
                     'fr': 'https://www.grimmstories.com/fr/grimm_contes/',
                     'it': 'https://www.grimmstories.com/it/grimm_fiabe/',
                     'nl': 'https://www.grimmstories.com/nl/grimm_sprookjes/',
                     'pt': 'https://www.grimmstories.com/pt/grimm_contos/'}
        lang = self.lang.split("-")[0]
        self.index = self.get_index(url_grimm[lang] + "list")

    def _matches_collection_hint(self, hint):
        if not hint:
            return True
        _, score = match_one(hint.lower(), COLLECTION_ALIASES)
        return score >= COLLECTION_HINT_THRESHOLD

    def _matches_content_type(self, content_type):
        if not content_type:
            return True
        return content_type.lower() in CONTENT_TYPES

    def handle_search(self, message):
        if not self.index:
            return
        collection_hint = message.data.get("collection_hint")
        if not self._matches_collection_hint(collection_hint):
            return  # this search isn't aimed at us - stay silent
        content_type = message.data.get("content_type")
        if not self._matches_content_type(content_type):
            return  # asking for a kind of content we don't offer

        phrase = message.data.get("phrase")
        if phrase:
            title, confidence = match_one(phrase, list(self.index.keys()))
        elif collection_hint:
            # 'a story from Grimm' with no specific tale named - only a
            # sensible response if the hint was actually for us
            title = random.choice(list(self.index.keys()))
            confidence = 1.0
        else:
            return  # no phrase and no hint - nothing to go on

        self.bus.emit(message.reply(COMMON_READING_SEARCH_RESPONSE, {
            "skill_id": self.skill_id,
            "content_id": title,
            "title": title,
            "author": AUTHOR_NAME,
            "collection": COLLECTION_NAME,
            "source": SOURCE_NAME,
            "confidence": confidence,
        }))

    def handle_fetch_content(self, message):
        content_id = message.data.get("content_id")
        url = self.index.get(content_id)
        if not url:
            self.bus.emit(message.reply(COMMON_READING_FETCH_CONTENT_RESPONSE, {"paragraphs": []}))
            return
        try:
            text = self.get_story(url)
        except StoryFetchError as e:
            self.log.error(f"Could not fetch story '{content_id}': {e}")
            self.bus.emit(message.reply(COMMON_READING_FETCH_CONTENT_RESPONSE, {"paragraphs": []}))
            return
        paragraphs = [p for p in text.split('\n\n') if p.strip()]
        self.bus.emit(message.reply(COMMON_READING_FETCH_CONTENT_RESPONSE, {"paragraphs": paragraphs}))

    def handle_ping(self, message):
        """Cheap 'is anyone there?' reply - no index lookup. Only ever
        called by the pipeline plugin on its rare 0-candidates path
        (see ovos-common-reading-pipeline-plugin#2), never on every
        search. A device with an unsupported language never reaches
        this handler at all, since initialize() returned early and
        never registered it - which is exactly the right behavior."""
        self.bus.emit(message.reply(COMMON_READING_PONG, {
            "skill_id": self.skill_id,
            "collection": COLLECTION_NAME,
        }))
