# <img src='story-512.png' card_color='#40DBB0' width='50' height='50' style='vertical-align:bottom'/> Grimm Tales (provider)

A *provider* skill for [ovos-common-reading-pipeline-plugin](https://github.com/andlo/ovos-common-reading-pipeline-plugin),
delivering the Brothers Grimm's fairy tales.

_"He who is too well off is always longing for something new."_
— from "The Mouse, the Bird, and the Sausage," Brothers Grimm

[![Tests](https://github.com/andlo/ovos-skill-grimm-tales/actions/workflows/test.yml/badge.svg)](https://github.com/andlo/ovos-skill-grimm-tales/actions/workflows/test.yml)
[![PyPI version](https://img.shields.io/pypi/v/ovos-skill-grimm-tales.svg)](https://pypi.org/project/ovos-skill-grimm-tales/)

> **This skill has no standalone voice interface.** It registers no
> intents and never speaks. It only answers
> [ovos.common_reading.* bus messages](https://github.com/andlo/ovos-common-reading-pipeline-plugin#the-ovoscommon_reading-bus-protocol),
> so you also need **ovos-common-reading-pipeline-plugin** installed and
> added to your pipeline config for it to be useful at all.

## Install
```bash
pip install ovos-skill-grimm-tales ovos-common-reading-pipeline-plugin
```

## Languages

Sourced live from [grimmstories.com](https://www.grimmstories.com/),
which supports 8 languages here: EN, DA, DE, ES, FR, IT, NL, PT.

Grimmstories.com actually offers 20 languages total - the other 12
(FI, HU, VI, TR, PL, RO, RU, UK, EL, ZH, JA, KO) aren't included here yet
since they fall outside [OVOS's actively-tracked language set](https://openvoiceos.github.io/lang-support-tracker/).
Portuguese is Grimm-only among the 8 supported here - no equivalent
Andersen source exists in Portuguese.

**This provider does not translate.** It loads only for the languages
the installation is configured for - the device's own `lang` plus
`secondary_langs` in `mycroft.conf` - that it supports. If none of them
is one of the 8, it **never loads at all**: `initialize()` builds no
index, registers no bus events, and logs a clear message rather than
silently serving English (or any other) content.

For each configured, supported language it builds its own story index,
and each search is answered from the index of the language it was made
in: the pipeline plugin's `lang` field, else the language of the session
the search came from, else the device's own. A single device builds one
index, as before. A HiveMind hub serving users in several languages lists
them in `secondary_langs`:

```json
{
  "lang": "en-US",
  "secondary_langs": ["da-DK", "de-DE"]
}
```

A search in a language the installation doesn't serve gets no answer at
all. A search with no title ("tell me a story") gets a random story at
0.9, and titles match regardless of case.

**Author/collection name and collection_hint aliases are also
per-language**, not hardcoded English - "the Brothers Grimm" only makes
sense to announce on an English device; a Danish device hears "Brødrene
Grimm" instead, and a Danish user saying "brødrene grimm" as a
collection_hint matches correctly (not just by luck, the way it would
have if we'd only shipped English aliases). See
`locale/<lang>/collection.voc` (aliases) and
`locale/<lang>/collection_meta.json` (author/collection name), loaded
via OVOS's own resource file resolution rather than Python constants -
see [ovos-common-reading-pipeline-plugin#26](https://github.com/andlo/ovos-common-reading-pipeline-plugin/issues/26)
for the full reasoning. This also means every supported language has
its own `locale/<lang>/skill.json`, so the Skills Store can see this
provider genuinely supports 8 languages, not just English.

## Collection hints

Responds to `collection_hint` values in the *device's own language* -
e.g. "grimm"/"the brothers grimm" on English, "grimm"/"brødrene grimm"
on Danish, "grimm"/"die gebrüder grimm" on German - matched fuzzily
against that language's own alias list (see `locale/<lang>/collection.voc`).

## Content type

Identifies as `content_type: "story"` or `"tale"`. A search with a
`content_type` hint for anything else (e.g. "article", "poem") gets no
response from this provider.

## Credits

Content sourced from grimmstories.com. Scraping/caching logic ported
from [ovos-skill-fairytales](https://github.com/andlo/ovos-skill-fairytales)
and [ovos-skill-andersen-tales](https://github.com/andlo/ovos-skill-andersen-tales).

## Category
**Entertainment**

## Tags
#stories #fairytales #grimm #provider
