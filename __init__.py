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
from ovos_bus_client.session import SessionManager
from ovos_utils.parse import match_one
from ovos_utils import classproperty
from ovos_utils.process_utils import RuntimeRequirements

import requests
from bs4 import BeautifulSoup
import time
import json
import os
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
# fuzzily against, not required to be exact. Loaded per-language from
# locale/<lang>/collection.voc and collection_meta.json (see
# _load_collection_meta below) rather than hardcoded here - "grimm" isn't
# called the same thing in every one of the 8 languages this provider
# supports (see ovos-common-reading-pipeline-plugin#26).
COLLECTION_HINT_THRESHOLD = 0.85  # see ovos-common-reading-pipeline-plugin's README for why not lower
CONTENT_TYPES = ["story", "tale"]
SOURCE_NAME = "grimmstories.com"

# grimmstories.com offers 20 languages total; we only support the ones
# also part of OVOS's actively-tracked language set (see
# andlo/ovos-skill-fairytales#31) - 7 shared with Andersen plus
# Portuguese (Grimm-only, no Andersen stories exist in Portuguese). This
# provider does NOT translate (unlike ovos-skill-ovosblog/
# ovos-skill-arxiv-papers) - it loads only for the configured languages
# (lang + secondary_langs) it supports, and each request's language
# picks the index that answers.
SUPPORTED_LANGUAGES = {"da", "en", "de", "es", "fr", "it", "nl", "pt"}



# 'tell me a story' names no title: answer with a random one, confident
# enough to be read without an "is it that one?" round trip (the plugin
# asks below 0.8) but below the 1.0 of a title somebody actually named -
# the same value as ovos-skill-andrew-lang-tales/-bechstein/-cosquin
RANDOM_STORY_CONFIDENCE = 0.9


def primary_subtag(lang):
    """'en-US', 'en_gb', 'EN' -> 'en'."""
    return (lang or "").replace("_", "-").split("-")[0].lower()


def configured_languages(langs):
    """Primary subtags of the languages an installation is configured
    for (core lang + secondary_langs): ['en-US', 'da-DK'] -> {'en', 'da'}."""
    return {primary_subtag(lang) for lang in langs or [] if lang}


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
        # Loads only for the languages this installation is configured
        # for - the device's own 'lang' plus 'secondary_langs' in
        # mycroft.conf - that grimmstories.com also offers. A single device builds
        # one index, as before; a HiveMind hub lists the languages its
        # users speak in secondary_langs and gets an index for each. Each
        # request's own language then picks which one answers.
        self.served = configured_languages(self.native_langs) & SUPPORTED_LANGUAGES
        self.indexes = {}  # 'da' -> {title: url}
        self._meta = {}  # 'da' -> {"aliases": [...], "author": ..., "collection": ...}
        # in-memory cache of already-fetched story text, keyed by URL
        self._story_text_cache = {}
        if not self.served:
            self.log.info(
                f"{self.skill_id}: none of the configured languages "
                f"{sorted(self.native_langs)} is one of "
                f"{sorted(SUPPORTED_LANGUAGES)} that grimmstories.com supports, and "
                f"this provider does not translate - skill will stay inert "
                f"(no bus events registered, index not built)."
            )
            return
        for lang in sorted(self.served):
            self._load_collection_meta(lang)
            self.refresh_index(lang=lang)
        self.log.info(f"{self.skill_id}: serving {sorted(self.served)}")
        self.add_event(COMMON_READING_SEARCH, self.handle_search)
        self.add_event(f"{COMMON_READING_FETCH_CONTENT}.{self.skill_id}", self.handle_fetch_content)
        self.add_event(COMMON_READING_PING, self.handle_ping)

    # --- per-language state ------------------------------------------------
    # index / _collection_aliases / _author_name / _collection_name are the
    # view for the current language (self.lang, which ovos-workshop takes
    # from the session of the message being handled). Handlers pass the
    # request's language explicitly instead - see _request_lang().

    def _default_lang(self):
        return primary_subtag(self.lang)

    def _meta_for(self, lang=None):
        return self._state("_meta").setdefault(lang or self._default_lang(), {})

    def _state(self, name):
        if name not in self.__dict__:
            self.__dict__[name] = {}
        return self.__dict__[name]

    @property
    def index(self):
        return self._state("indexes").get(self._default_lang(), {})

    @index.setter
    def index(self, value):
        self._state("indexes")[self._default_lang()] = value

    @property
    def _collection_aliases(self):
        return self._meta_for().get("aliases", [])

    @_collection_aliases.setter
    def _collection_aliases(self, value):
        self._meta_for()["aliases"] = value

    @property
    def _author_name(self):
        return self._meta_for().get("author")

    @_author_name.setter
    def _author_name(self, value):
        self._meta_for()["author"] = value

    @property
    def _collection_name(self):
        return self._meta_for().get("collection")

    @_collection_name.setter
    def _collection_name(self, value):
        self._meta_for()["collection"] = value

    def _locale_tag(self, lang):
        """The locale/ folder for a primary subtag: 'da' -> 'da-dk'."""
        for name in sorted(os.listdir(os.path.join(self.res_dir, "locale"))):
            if primary_subtag(name) == lang:
                return name
        return lang

    @staticmethod
    def _request_lang(message):
        """The language a request was made in, or None when it does not
        say: the pipeline plugin's own 'lang' field first, then the
        language of the session the request was forwarded from (a
        HiveMind client's, on a hub). An older plugin sends neither."""
        lang = message.data.get("lang") or message.context.get("lang")
        if not lang and message.context.get("session"):
            lang = SessionManager.get(message).lang
        return lang or None

    def _serves(self, lang):
        return primary_subtag(lang) in getattr(self, "served", set())

    def _load_collection_meta(self, lang=None):
        """Loads collection_aliases/author_name/collection_name for one
        language (default: the current one) from locale/<lang>/ via
        OVOS's own resource file resolution - not hardcoded English
        constants. See ovos-common-reading-pipeline-plugin#26."""
        lang = lang or self._default_lang()
        resources = self.resources if lang == self._default_lang() else \
            self.load_lang(self.res_dir, self._locale_tag(lang))
        aliases_raw = resources.load_vocabulary_file("collection")
        meta = resources.load_json_file("collection_meta.json")
        self._meta_for(lang).update({
            "aliases": [phrase for line in aliases_raw for phrase in line],
            "author": meta["author"],
            "collection": meta["collection"],
        })

    def _index_cache_filename(self, lang=None):
        return f"index_{lang or self._default_lang()}.json"

    def _read_index_cache(self, lang=None):
        cache_file = self._index_cache_filename(lang)
        if not self.file_system.exists(cache_file):
            return None
        try:
            with self.file_system.open(cache_file, "r") as f:
                return json.load(f)
        except (OSError, ValueError) as e:
            self.log.warning(f"could not read story index cache: {e}")
            return None

    def _write_index_cache(self, lang=None):
        cache_file = self._index_cache_filename(lang)
        index = self._state("indexes").get(lang or self._default_lang(), {})
        try:
            with self.file_system.open(cache_file, "w") as f:
                json.dump({"timestamp": time.time(), "index": index}, f)
        except OSError as e:
            self.log.warning(f"could not write story index cache: {e}")

    def refresh_index(self, force=False, lang=None):
        lang = lang or self._default_lang()
        indexes = self._state("indexes")
        cached = self._read_index_cache(lang)
        if not force and cached and (time.time() - cached.get("timestamp", 0)) < self.INDEX_CACHE_TTL:
            indexes[lang] = cached.get("index", {})
            return
        try:
            indexes[lang] = self.update_index(lang)
            self._write_index_cache(lang)
        except StoryFetchError as e:
            self.log.error(f"Could not refresh story index ({lang}): {e}")
            if cached:
                self.log.warning("Falling back to previously cached (possibly stale) story index")
                indexes[lang] = cached.get("index", {})

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

    def update_index(self, lang=None):
        url_grimm = {'da': 'https://www.grimmstories.com/da/grimm_eventyr/',
                     'en': 'https://www.grimmstories.com/en/grimm_fairy-tales/',
                     'de': 'https://www.grimmstories.com/de/grimm_maerchen/',
                     'es': 'https://www.grimmstories.com/es/grimm_cuentos/',
                     'fr': 'https://www.grimmstories.com/fr/grimm_contes/',
                     'it': 'https://www.grimmstories.com/it/grimm_fiabe/',
                     'nl': 'https://www.grimmstories.com/nl/grimm_sprookjes/',
                     'pt': 'https://www.grimmstories.com/pt/grimm_contos/'}
        return self.get_index(url_grimm[lang or self._default_lang()] + "list")

    def _matches_collection_hint(self, hint, lang=None):
        if not hint:
            return True
        aliases = self._meta_for(lang).get("aliases", [])
        if not aliases:
            return False
        _, score = match_one(hint.lower(), aliases)
        return score >= COLLECTION_HINT_THRESHOLD

    def _matches_content_type(self, content_type):
        if not content_type:
            return True
        return content_type.lower() in CONTENT_TYPES

    def handle_search(self, message):
        # the language this search was made in - a search in a language
        # this installation doesn't serve gets no answer at all, not an
        # empty one. With no language on the request (an older plugin),
        # the device's own language decides, as it always did.
        lang = primary_subtag(self._request_lang(message) or self.lang)
        if not self._serves(lang):
            return
        index = self._state("indexes").get(lang)
        if not index:
            return
        meta = self._meta_for(lang)
        collection_hint = message.data.get("collection_hint")
        if not self._matches_collection_hint(collection_hint, lang):
            return  # this search isn't aimed at us - stay silent
        content_type = message.data.get("content_type")
        if not self._matches_content_type(content_type):
            return  # asking for a kind of content we don't offer

        phrase = (message.data.get("phrase") or "").strip()
        if phrase:
            # titles keep their case ('The Ugly Duckling'), requests
            # rarely do - compare both lower case
            by_lower = {title.lower(): title for title in index}
            match, confidence = match_one(phrase.lower(), list(by_lower))
            title = by_lower[match]
        else:
            # no title asked for: 'tell me a story', or 'a story from
            # <collection>' - a random one, fully confident only when the
            # collection itself was named
            title = random.choice(list(index.keys()))
            confidence = 1.0 if collection_hint else RANDOM_STORY_CONFIDENCE

        self.bus.emit(message.reply(COMMON_READING_SEARCH_RESPONSE, {
            "skill_id": self.skill_id,
            "content_id": title,
            "title": title,
            "author": meta.get("author"),
            "collection": meta.get("collection"),
            "source": SOURCE_NAME,
            "confidence": confidence,
        }))

    def handle_fetch_content(self, message):
        content_id = message.data.get("content_id")
        # never gated on language: it is addressed to this provider by id.
        # Look in the request's language first, then in every other one.
        indexes = self._state("indexes")
        first = primary_subtag(self._request_lang(message) or self.lang)
        url = None
        for lang in [first] + sorted(set(indexes) - {first}):
            url = indexes.get(lang, {}).get(content_id)
            if url:
                break
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
        search. A ping that says which language it is asking for (its
        'lang' field or the session it was forwarded from) only gets a
        pong when this installation serves that language. An
        installation serving none never registered this handler."""
        lang = self._request_lang(message)
        if lang and not self._serves(lang):
            return
        meta = self._meta_for(primary_subtag(lang) if lang else None)
        self.bus.emit(message.reply(COMMON_READING_PONG, {
            "skill_id": self.skill_id,
            "collection": meta.get("collection"),
        }))
