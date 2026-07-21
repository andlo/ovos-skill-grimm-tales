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

**This provider does not translate.** On any other device language, it
doesn't just decline to answer searches - it **never loads at all**:
`initialize()` checks the device's language against `SUPPORTED_LANGUAGES`
before building any index or registering any bus events, and logs a
clear message if the language isn't supported, rather than silently
serving English (or any other) content. Set your device to one of the 8
supported languages to use this provider.

## Collection hints

Responds to `collection_hint` values like "grimm", "the brothers grimm",
"brothers grimm", "grimm brothers", matched fuzzily (see
`COLLECTION_ALIASES` in `__init__.py`).

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
