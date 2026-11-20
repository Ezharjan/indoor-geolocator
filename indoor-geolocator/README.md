# indoor-geolocator

A skill that works out where an indoor photo was taken: a hotel room, a flat, a restaurant, a shop, a
station. It answers with the venue, the address, coordinates with an error radius, and a confidence level
that is computed from the recorded evidence. It also leaves a case folder with the full reasoning trail.

This file describes the plugin for people who install it and for directory reviewers: what it does, what it
runs, and what it sends over the network. The full manual is the [project README](https://github.com/Ezharjan/indoor-geolocator#readme), and a
worked case is on the [project page](https://ezharjan.github.io/indoor-geolocator/).

## Install

In a terminal (PowerShell, Terminal or bash) on a computer where Claude Code is installed:

```
claude plugin marketplace add Ezharjan/indoor-geolocator
claude plugin install indoor-geolocator@ezharjan-plugins
pip install pillow
```

On Windows also run `pip install tzdata`. The plugin is then available in the Claude Code terminal, in the
desktop app's local Code sessions and in the VS Code extension, from the next session on. Inside a session of
the Claude Code terminal (version 2.1.275 or later) the first two steps can also be done in one:

```
/plugin install indoor-geolocator --marketplace Ezharjan/indoor-geolocator
```

The `/plugin` command belongs to the terminal. Where it is not available, such as the desktop app, use the
commands above.

The same skill can also be installed on its own, without the plugin (see the project README). Use one or the
other, not both: as a plugin it is called `/indoor-geolocator:indoor-geolocator`, as a skill `/indoor-geolocator`.

## Try it

Attach an interior photo and say one of these:

1. "Where was this photo taken?"
2. "Which hotel is this room in? Show me the evidence and how sure you are."
3. "Check whether this photo really shows the lobby of the hotel named in the caption."

The skill also starts when a photo of an interior is shared with no text at all.

## What it is for, and what it refuses

It is built for verifying where a photo comes from: journalism and fact-checking, checking a listing before
booking, finding the place in one's own old photos, research and teaching of open-source investigation.

- It does no face recognition and never identifies a person.
- People, clothing and belongings are read only for what they say about the place.
- For a private home with no stated purpose it asks once what the result is for, and without a legitimate
  purpose it stops at city or neighbourhood level.
- It never logs in on anyone's behalf, never solves CAPTCHAs and never collects data in bulk.
- A result is an evidence-weighted estimate. An unverified venue is reported as a lead, never as the answer.

## What it runs

- A Python command-line tool, `scripts/igl.py`, with its modules in `scripts/iglib/`. It needs Python 3.9 or
  later and Pillow. The source is plain, readable Python; nothing is compiled or minified.
- Optional packages, used only when installed: OpenCV and numpy, Playwright with Chromium, onnxruntime,
  phonenumbers, pillow-heif, RapidOCR, and the tesseract program. The skill does not install them by itself.
- Two offline lookup tables in `data/` (country standards and barcode prefixes).
- No hooks, no MCP servers, no background processes, and no telemetry.

## What it sends and fetches

Everything below happens only while a case is being worked on, and the report of each case lists the
services that were actually contacted. The author of the skill operates none of these services and receives
no data.

| Purpose | Service | What is sent |
|---|---|---|
| Reverse image search | Yandex, TinEye, Baidu | The photo or a crop of it, with metadata removed |
| Reverse image search by link (Google Lens, Bing; optional SerpApi with the user's own key) | A temporary file host: uguu.se, tmpfiles.org or litterbox.catbox.moe | A copy of the photo or crop with metadata removed, deleted by the host after 1 to 3 hours |
| Picture search by text | Brave Search, Startpage | Search words only |
| Places and maps | OpenStreetMap Nominatim, Photon, Overpass servers, Wikidata, Wikimedia Commons | Place names, coordinates and map queries |
| Time zone and past weather | timeapi.io, Open-Meteo | Coordinates and a date |
| Public posts about places | Bluesky, Flickr, Openverse, Mastodon, Lemmy | Search words only |
| Wi-Fi network names (optional, with the user's own key) | WiGLE | A network name |
| Pages and pictures of candidate venues | The websites found by the searches above | Ordinary page requests |
| Similarity model, on first use | huggingface.co | Nothing about the photo; a 24 MB model file is downloaded once and checked against a SHA-256 |

- Uploading the photo can be avoided: the option `--no-share` stops temporary copies, and the skill uploads
  nothing without asking when the user marks a photo as private.
- Wi-Fi passwords, IBANs and names on contact cards found in a photo are redacted before anything is stored
  or shown.

## What it stores

- One case folder per photo, on the machine where the skill runs: a copy of the photo, the evidence it
  cites, a report and a ledger. Nothing else is kept between sessions.
- The similarity model, in the user's cache folder.

The privacy notice is at https://ezharjan.github.io/indoor-geolocator/privacy.html.

## Support and licence

Questions and problems: https://github.com/Ezharjan/indoor-geolocator/issues. The code is released under the MIT licence (see LICENSE.txt); the
data tables keep the licences of their sources, described in `data/README.md`.
