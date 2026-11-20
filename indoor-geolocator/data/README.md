# Offline data

Two lookup tables used by `igl.py countries` and `igl.py lookup`. Both are plain JSON with a `_meta`
block recording the build date, the sources and the licences. They were built on 2026-11-19 by
`tools/build_data.py` in the source repository, which can rebuild them from the original sources.

## countries.json

257 countries and territories, keyed by ISO 3166-1 alpha-2 code.

| Fields | Source | Licence |
|---|---|---|
| `name`, `alt_names`, `un_region`, `calling_codes`, `currencies`, `former_currencies`, `languages` (code, script, share of speakers, official status), `week_starts`, `clock`, `measurement`, `temperature`, `paper` | [Unicode CLDR](https://github.com/unicode-org/cldr-json) 49.0.0 (`cldr-core`, `cldr-localenames-full`, `cldr-numbers-full`) | [Unicode License v3](https://www.unicode.org/license.txt) |
| `plug_types`, `plug_types_raw`, `plug_standard`, `voltage`, `frequency`, `mains_notes` | Wikipedia: [Mains electricity by country](https://en.wikipedia.org/wiki/Mains_electricity_by_country) | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/), © Wikipedia contributors |
| `driving_side` | Wikipedia: [Left- and right-hand traffic](https://en.wikipedia.org/wiki/Left-_and_right-hand_traffic) | CC BY-SA 4.0, © Wikipedia contributors |
| `emergency` | Wikipedia: [List of emergency telephone numbers](https://en.wikipedia.org/wiki/List_of_emergency_telephone_numbers) | CC BY-SA 4.0, © Wikipedia contributors |
| `cctld` | derived from the ISO code (`.uk` for GB) | — |

## gs1_prefixes.json

141 GS1 company-prefix ranges (the first three digits of an EAN-13/GTIN-13) mapped to the issuing GS1
member organisation. A prefix tells where the barcode was **registered**, not where the product was made
or sold. Source: Wikipedia, [List of GS1 country codes](https://en.wikipedia.org/wiki/List_of_GS1_country_codes),
CC BY-SA 4.0, © Wikipedia contributors.

## Notes

- The Wikipedia-derived fields are adapted factual tables. They keep their CC BY-SA 4.0 licence and
  attribution; they are not covered by the MIT licence of the code.
- Tables describe the norm. Older buildings, hotels, expat housing and border regions deviate, so the
  skill treats table-based clues as observations that rank countries, never as proof.
- `_meta.unmatched_source_rows` lists the few source rows (sub-national regions, disputed areas) that
  could not be matched to an ISO code.
