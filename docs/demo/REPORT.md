# Indoor geolocation report

| | |
|---|---|
| **Answer (verified level)** | **London** |
| **Coordinates** | 51.507200, -0.127600 (WGS84) ± 25000 m — [OpenStreetMap](https://www.openstreetmap.org/?mlat=51.507200&mlon=-0.127600#map=19/51.507200/-0.127600) · [Google Maps](https://www.google.com/maps/search/?api=1&query=51.507200,-0.127600) |
| **Confidence** | **MEDIUM** at city level · share 0.80 of the city board |
| **Photo** | `input/larkspur-room.jpg` · sha256 `907d63b789f4c494…` |
| **Generated** | 2026-11-20 12:13 · indoor-geolocator 2.0.0 |

> A '+44 20' phone number read on the tent card places the room in London (libphonenumber, decisive). Independent fixed standards agree on the UK: a BS 1363 Type G switched socket and £ prices with VAT. The venue named on the card is fictional, so no site candidate exists and the site level stays open.

## Confidence by level

| Level | Candidate | Share | Tier | Basis |
|---|---|---|---|---|
| country | United Kingdom | 0.82 | high | share 0.82 at country level; 2 decisive clue(s) from text; 2 independent lineage(s) with LR>=2: image, text |
| city | London | 0.80 | medium | share 0.80 at city level (0.97 within United Kingdom); 1 decisive clue(s) from text; 1 independent lineage(s) with LR>=2: text |

## Evidence

| Clue | Observation | Obtained (grade) | Lineage | Effect on candidates | Files |
|---|---|---|---|---|---|
| N1 | Hypotheses: scene=hotel room desk. 1) United Kingdom: switched three-pin socket and £ prices; 2) another British Isles or Commonwealth territory sharing the so… | inferred (D) | image | context |  |
| N2 | Double switched socket: per outlet one vertical earth slot above two horizontal slots, rocker switch with red indicator = BS 1363 (Type G) | observed (B) | image | 55 candidates ×6 (e.g. United Kingdom, Falkland Islands, Gibraltar, Guernsey, …) | [E05](evidence/E05_socket.jpg) |
| N3 | '£14.50 per person incl. VAT' read on the tent card | read (A) | text | 10 candidates ×20 (e.g. United Kingdom, Falkland Islands, Gibraltar, Guernsey, …) | [E06](evidence/E06_tent-card.jpg) |
| N4 | '+44 20 7946 0321' read on the tent card; libphonenumber: GB, London (area code 20) | computed (A) | text | United Kingdom ×30; London ×30 | [E06](evidence/E06_tent-card.jpg) |
| N5 | English on every item, no other script | observed (B) | text | 118 candidates ×1.5 (e.g. United Kingdom, Falkland Islands, Gibraltar, Guernsey, …) | [E06](evidence/E06_tent-card.jpg) |
| N6 | Venue name 'THE LARKSPUR' and Wi-Fi SSID 'Larkspur-Guest' (password redacted by the decoder); the demo venue is fictional, so it is not searched | computed (A) | text | context | [E06](evidence/E06_tent-card.jpg) |

## Candidates considered

**country**

| # | Candidate | Share | Status | Location |
|---|---|---|---|---|
| C52 | United Kingdom | 0.82 | contains the answer |  |
| C10 | Falkland Islands | 0.03 | open |  |
| C13 | Gibraltar | 0.03 | open |  |
| C15 | Guernsey | 0.03 | open |  |
| C20 | Isle of Man | 0.03 | open |  |
| C21 | Jersey | 0.03 | open |  |
| C44 | St. Helena, Ascension & Tristan da Cunha | 0.03 | open |  |
| … | 127 more candidate(s), each with share < 0.01 (South Georgia & South Sandwich Islands, South Sudan, Syria, Belize, Botswana, Cyprus, Dominica, Gambia, …) | | | |
| C* | other countries (116 not on the board) | 0.00 | not on the board | |

**city**

| # | Candidate | Share | Status | Location |
|---|---|---|---|---|
| C135 | London | 0.80 | answer | 51.50720, -0.12760 |
| C* | unlisted alternatives (any city not on the board) | 0.20 | not on the board | |

## Reasoning timeline

1. `12:13` case created for larkspur-room.jpg
2. `12:13` A1 metadata: results - no EXIF - stripped (messaging/social upload, screenshot, export) or synthetic; absence proves nothing; C2PA content credentials present (is…
3. `12:13` metadata read: 4 notable fields; overview grid 8x5
4. `12:13` N1 [inferred/image] Hypotheses: scene=hotel room desk. 1) United Kingdom: switched three-pin socket and £ prices; 2) another British Isles or Commonwealth territory sharing the so…
5. `12:13` A2 text_ocr/tesseract: results - tesseract: 8 language-like line(s) [THE LARKSPUR, Guest Wi-Fi, Welcome to your room, Breakfast 7:00 - 10:30, £14.50 per person incl. VAT, R…
6. `12:13` A3 codes: results - 1 code(s): WIFI:T:WPA;S:Larkspur-Guest;P:<redacted>;;
7. `12:13` scan: 8 OCR lines, 1 codes, tiles 3x3
8. `12:13` N2 [observed/image] Double switched socket: per outlet one vertical earth slot above two horizontal slots, rocker switch with red indicator = BS 1363 (Type G)
9. `12:13` N3 [read/text] '£14.50 per person incl. VAT' read on the tent card
10. `12:13` N4 [computed/text] '+44 20 7946 0321' read on the tent card; libphonenumber: GB, London (area code 20)
11. `12:13` N5 [observed/text] English on every item, no other script
12. `12:13` N6 [computed/text] Venue name 'THE LARKSPUR' and Wi-Fi SSID 'Larkspur-Guest' (password redacted by the decoder); the demo venue is fictional, so it is not searched
13. `12:13` countries filter via N2: 55 countries linked x6 (55 new candidates)
14. `12:13` countries filter via N3: 10 countries linked x20 (3 new candidates)
15. `12:13` countries filter via N5: 118 countries linked x1.5 (76 new candidates)
16. `12:13` N4 linked: N4 -> C52 United Kingdom: LR 30
17. `12:13` C135 city: London @ 51.50720,-0.12760
18. `12:13` N4 linked: N4 -> C135 London: LR 30
19. `12:13` A4 visual_sweep: results - 9 tiles: tent card, Wi-Fi card, double socket, lamp, framed print; no window or reflection
20. `12:13` A5 standards: results - BS 1363 Type G socket; £ prices with VAT
21. `12:13` A6 culture_style: results - generic international hotel decor; English only; no cultural or religious markers
22. `12:13` A7 consistency: results - socket, currency, language and phone agree on GB/London; no EXIF time to test sun or time zone
23. `12:13` A8 reverse_search: not_applicable - demo photo is synthetic and the venue fictional: online routes skipped on purpose
24. `12:13` A9 text_search: not_applicable - demo photo is synthetic and the venue fictional: online routes skipped on purpose
25. `12:13` A10 social_search: not_applicable - demo photo is synthetic and the venue fictional: online routes skipped on purpose
26. `12:13` A11 candidate_enum: not_applicable - demo photo is synthetic and the venue fictional: online routes skipped on purpose
27. `12:13` A12 reference_match: not_applicable - demo photo is synthetic and the venue fictional: online routes skipped on purpose
28. `12:13` A13 window_view: not_applicable - no window, door or reflection in the frame
29. `12:13` answer C135 London (city, confidence medium, cap medium)

## Methods attempted

| Method | Status | Attempts | Last detail |
|---|---|---|---|
| metadata (core) | results | 1 | no EXIF - stripped (messaging/social upload, screenshot, export) or synthetic; absence proves nothing; C2PA c… |
| visual_sweep (core) | results | 1 | 9 tiles: tent card, Wi-Fi card, double socket, lamp, framed print; no window or reflection |
| text_ocr (core) | results | 1 | tesseract: 8 language-like line(s) [THE LARKSPUR, Guest Wi-Fi, Welcome to your room, Breakfast 7:00 - 10:30, … |
| codes (core) | results | 1 | 1 code(s): WIFI:T:WPA;S:Larkspur-Guest;P:<redacted>;; |
| standards (core) | results | 1 | BS 1363 Type G socket; £ prices with VAT |
| culture_style (core) | results | 1 | generic international hotel decor; English only; no cultural or religious markers |
| reverse_search (core) | not_applicable | 1 | demo photo is synthetic and the venue fictional: online routes skipped on purpose |
| text_search (core) | not_applicable | 1 | demo photo is synthetic and the venue fictional: online routes skipped on purpose |
| social_search (core) | not_applicable | 1 | demo photo is synthetic and the venue fictional: online routes skipped on purpose |
| candidate_enum (core) | not_applicable | 1 | demo photo is synthetic and the venue fictional: online routes skipped on purpose |
| reference_match (core) | not_applicable | 1 | demo photo is synthetic and the venue fictional: online routes skipped on purpose |
| window_view (core) | not_applicable | 1 | no window, door or reflection in the frame |
| consistency (core) | results | 1 | socket, currency, language and phone agree on GB/London; no EXIF time to test sun or time zone |

## Open questions and alternatives

- Site level: the venue named on the card is fictional, so no reference imagery exists.

## Data handling

- Photo uploaded for reverse image search to: none recorded
- Temporary public copies (metadata stripped): none
- Online services queried by the tools: none recorded
- Personal names / home addresses of private individuals are not reproduced in this report.

## Files

| File | What it shows |
|---|---|
| [input/larkspur-room.jpg](input/larkspur-room.jpg) | the photo (byte-exact copy) |
| [input/metadata.json](input/metadata.json) | full metadata dump |
| [evidence/E01_overview-grid.jpg](evidence/E01_overview-grid.jpg) | the photo with a labelled grid (use --cell C3 or C3:E5 to crop) |
| [evidence/E02_scan.json](evidence/E02_scan.json) | machine scan: OCR lines (T#), decoded codes (Q#), text signals |
| [evidence/E03_scan-annotated.jpg](evidence/E03_scan-annotated.jpg) | photo with OCR line boxes (T#) and code boxes (Q#) |
| [evidence/E04_text-crops.jpg](evidence/E04_text-crops.jpg) | enlarged crops of the OCR lines (T#): read them yourself |
| [evidence/E05_socket.jpg](evidence/E05_socket.jpg) | double switched socket on the wall beside the desk |
| [evidence/E06_tent-card.jpg](evidence/E06_tent-card.jpg) | tent card on the desk: venue name, breakfast price, reception number |
| [case.json](case.json) | the complete ledger (every clue, link, attempt and timestamp) |
