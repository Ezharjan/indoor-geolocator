# Indoor clue catalogue

Used in workflow steps 3–5. Ordered roughly by **exclusion power**: one item near the top outweighs a
dozen near the bottom. For every clue: crop it (`igl.py crop`), describe the shape before naming it,
record it (`igl.py note`) with an honest status, then link it. Strength column: **S** strong (a fixed
standard or readable fact), **M** medium (regional habit), **W** weak (taste, trend, portable object).

Contents: 0 sweep method · 1 photo & provenance · 2 text & language · 3 numbers, money, dates, units ·
4 codes & digital traces · 5 electrical · 6 plumbing & bathroom · 7 heating, cooling, ventilation ·
8 windows, doors, floors, walls, ceilings · 9 safety & public-information signage · 10 lifts, stairs,
floor numbering · 11 products, brands, retail, payment · 12 appliances, devices, media · 13 furniture,
decor, style, patterns, textiles · 13a local references (pictures and objects that point at the town) ·
14 religion, customs, seasonal decor · 15 people & personal items · 16 light, time, season ·
17 negative clues · 18 portable-object traps

---

## 0. Sweep method

- Look at the whole frame, then every tile from `igl.py scan` (`.work/tiles/`), then the four corners
  and edges. The eye goes to the biggest object first, but the decisive clue is usually small: a
  sticker on a door frame, a socket behind a lamp, a leaflet on a table, a reflection in a TV or window.
- Sort what you find into three piles. **Identity carriers** name the venue or exist only there (text,
  logos, a unique artwork or sculpture, custom carpet, the view): they generate and verify candidates.
  **Region evidence** is fixed to the building (sections 5-10): it narrows the country. **Local
  references** point at the town (section 13a). Everything else is context.
- Read text yourself. `scan` reports only OCR lines that look like language, and an empty list is
  normal for a room; stylised logos, tiny labels, screens and reflections need your eyes on a crop.
- For each zone ask: *what is fixed to the building* (standards: sockets, switches, radiators, windows,
  signs - strong) vs *what is movable* (furniture, decor, products - weaker, can be imported).
- Check orientation and mirroring first. Reversed text, a steering wheel on the "wrong" side in a window
  view, or a clock reading backwards means `igl.py crop --flip` and re-read.
- If you can't name something, describe it: "white square plate, two round recessed holes, two metal
  clips at 12 and 6 o'clock". A wrong name gets something ordinary discarded, or something ordinary
  over-weighted.

## 1. Photo and provenance (from `init`)

| Clue | Implies | Strength |
|---|---|---|
| EXIF GPS | the position, if not edited or spoofed: verify against the content | S (metadata cap 20 until corroborated) |
| EXIF `OffsetTimeOriginal` + date | UTC offset → the set of time zones (`init` lists them) | S for zone set |
| Camera clock local time | day/night vs the window light, season | M |
| XMP/IPTC City, Country, Location, caption, keywords | someone typed a place; verify | M–S |
| Embedded EXIF thumbnail that differs | photo was cropped or edited; the thumbnail may show more | S (look at it) |
| Filename pattern | source app (WhatsApp, Telegram, Pixel, screenshot language) and date | W–M |
| ICC "Display P3" / Apple HostComputer / Make-Model | device family; market hints only | W |
| AI / C2PA / generator markers, PNG `parameters` | possibly synthetic, so the place may not exist | S for authenticity |
| Social-media size without EXIF, FBMD | passed through a platform; search that platform | W |
| Watermark, username, logo burned into the image | provenance lead: photographer, agency, listing site | S lead |
| Screen UI (status bar, app chrome) in a screenshot | carrier name, language, time format, map app | M–S |

## 2. Text and language

Read **everything**: signs, notices, posters, menus, receipts, packaging, book spines, TV screens,
device screens, stickers on equipment, embroidered logos, labels on fire extinguishers and lifts.
Zoom (`crop --enhance auto`), straighten (`--rotate`), mirror (`--flip`). Copy the original text
verbatim and search the original, not a translation.

| Clue | Implies | Strength |
|---|---|---|
| Venue name, address, phone, URL, e-mail domain on fixed signage | the place itself, after a map check | S |
| The same on portable items (pen, notepad, bag, cup) | the item's origin, which is often but not always this place | M (see section 18) |
| Writing system: Han (Simplified vs Traditional), kana, Hangul, Thai, Lao, Khmer, Myanmar, Arabic, Hebrew, Devanagari, Bengali, Tamil, Sinhala, Georgian, Armenian, Ethiopic, Cyrillic, Greek | language family → country set (`countries --script`) | S |
| Simplified Chinese | mainland China, Singapore, Malaysia | S |
| Traditional Chinese | Taiwan, Hong Kong, Macau (also older diaspora) | S |
| Diacritics: ß (DE/AT; never Swiss), ł ą ę (PL), ř ě ů (CZ), ő ű (HU), ñ (ES), ã õ (PT), ğ ş ı (TR), ș ț (RO), đ ơ ư (VN), å ø æ (Nordic), þ ð (IS) | language → country set (`scan` lists them) | S |
| Officially bilingual signage (EN/FR, NL/FR, DE/FR/IT, CA/ES, CY/EN, GA/EN, FI/SV, HE/AR/EN, ZH/EN with Traditional, ZH/PT) | officially multilingual area, not just "near" a language | S |
| Spelling variants: colour/color, centre/center, metre; pt-PT vs pt-BR (ecrã/tela, casa de banho/banheiro); ES Spain vs Latin America (ordenador/computadora) | variety → country | M |
| Swiss German "Strasse" with no ß, Austrian "Jänner", Belgian/Swiss "septante" | sub-variety | M |
| English used everywhere in an international hotel | weak: chains standardise English | W |

## 3. Numbers, money, dates and units (`scan` mines these)

| Clue | Implies | Strength |
|---|---|---|
| Currency symbol/code with amounts | country set (`countries --currency`) | S |
| Former currencies: DM, FF, Lira, Peseta, Escudo, Drachma, Gulden, Schilling, Markka (pre-2002) | country + date before the euro | S |
| Decimal comma (1.234,56) vs decimal point (1,234.56); apostrophe thousands (1'234.50 → CH/LI) | locale family | M |
| "12,50 €" (symbol after: FR, DE, AT, ES, IT, PT...) vs "€ 12,50" (symbol first with decimal comma: NL, Flemish BE) vs "€12.50" (IE, MT) | locale | M |
| Tax words: MwSt/USt/MWST, TVA/TTC, IVA, BTW, moms (SE/DK), mva (NO), ALV (FI), GST/HST/PST/QST (CA; GST also AU/NZ/SG/IN/MY), 税込/税抜, 含税/增值税, 부가세, KDV, НДС, ПДВ (UA), DPH, PDV, DDV (SI), PTU, ÁFA, ΦΠΑ | country/region | S |
| Price magnitude (coffee, beer, minibar) | price level of the country/city | W–M |
| Dates: D.M.Y with dots (DE/AT/CH/RU/PL/CZ/FI/NO/TR); M/D/Y (US); Y-M-D (East Asia, SE, LT, CA); Y年M月D日 | locale | M |
| Calendar eras: 令和/平成 (JP), 民國 (TW), พ.ศ. 25xx (TH), Solar Hijri 14xx (IR/AF), Hebrew 57xx | country | S |
| 12-hour (am/pm, 午前/午後, 오전/오후) vs 24-hour; "14h30" (FR/PT/BR/ES) | locale | M |
| Calendar week starting Sunday vs Monday (vs Saturday in parts of the Middle East) | `countries --week` | M |
| °F thermostat or display | US (plus BS, BZ, KY, PR, PW, LR) | S |
| Units: sq ft (US/UK/IN/HK/SG/AE listings), 坪 (JP/TW), 평 (KR), mph, lbs, pints | country set | M |
| Postcodes with distinctive formats (UK, CA, NL, JP 〒, BR, PL, PT, IE Eircode, US ZIP+4) | country, often district | S |
| Paper size US-Letter (US, CA, MX, PH, much of Central America) vs A4 | `countries --paper` | M |

## 4. Codes and digital traces (`scan` decodes these)

| Clue | Implies | Strength |
|---|---|---|
| QR → URL | the business or listing (open it; take `igl.py snapshot` of the page) | S |
| EMVCo payment QR (Pix, PayNow, PromptPay, QRIS, FPS, DuitNow, QR Ph, VietQR...) | merchant NAME + CITY + COUNTRY are inside the code | S |
| Swiss QR-bill (SPC) | creditor name/address (CH/LI) | S |
| EPC/SEPA QR (BCD) | beneficiary + IBAN country | S |
| UPI (upi://) | India; payee name is usually the shop | S |
| Wi-Fi QR or card: SSID | venue/ISP name; WiGLE with a user key | M–S |
| vCard / MECARD | company + address | S |
| Barcode GS1 prefix (690–699 CN, 400–440 DE, 450–459/490–499 JP, 880 KR, 300–379 FR, 500–509 UK...) | where the BRAND registered, not where it is sold | W–M |
| ISBN group (978-3 German, 978-2 French, 978-4 Japanese...) | book's language region | W |
| Router/ISP branding (Livebox, Freebox, Bbox → FR; Fritz!Box, Speedport → DE; BT Hub, Sky, Virgin → UK; Xfinity → US; Telstra → AU; Bell, Rogers → CA; KPN, Ziggo → NL; Movistar → ES/LatAm; NTT, au, SoftBank → JP; KT, SK, LG U+ → KR; Jio, Airtel → IN) | country | M–S |
| COVID-era check-in QR posters (2020–22): NHS COVID-19 app (England, Wales), Check In Scotland, SafeEntry (SG), LeaveHomeSafe (HK), Service NSW / Check In CBR (AU), Luca / Corona-Warn-App (DE), MySejahtera (MY), PeduliLindungi (ID), Thai Chana (TH) | country (often state) + date bracket | S |

## 5. Electrical (fixed to the building: among the strongest clues)

Sockets: `igl.py lookup plugs` prints every type's shape, and `igl.py countries --plug X` gives the
country set. Two different socket types visible together narrow a lot (`--plug F --plug E`).

| Seen | Implies |
|---|---|
| Two vertical flat slots, often one longer (polarised), ± round earth hole (A/B), with 100–127 V habits | North America, Mexico, Central America, Caribbean, Japan (often non-polarised two-slot), Taiwan, Philippines, Colombia/Ecuador/Venezuela/Peru (mixed) |
| US outlets with TEST/RESET buttons (GFCI) near sinks; "TR" tamper-resistant marking | US/Canada building code |
| Japanese wide flat rocker switch panels with small orange/green indicator lights; earth-terminal screw outlets in kitchens and bathrooms | Japan |
| UK square 86×86 mm white plate, three rectangular holes (G), a switch on the socket; bathroom pull-cord ceiling switch; two-pin shaver socket | UK, Ireland (G also MT, CY, HK, SG, MY, Gulf states, KE, NG...) |
| Round recess, two round holes, side earth clips (F, Schuko) on square 80×80 mm plates with large rockers (Gira, Jung, Busch-Jaeger, Berker) | Germany, Austria, Netherlands, Nordic countries, much of Europe, Russia, Korea, Indonesia... |
| Round recess with a protruding male earth pin (E) | France, Belgium, Poland, Czechia, Slovakia (also parts of Africa) |
| Rectangular modular frames (BTicino, Vimar) with three-in-line holes (L) and "bipasso" sockets | Italy (also Chile, Uruguay) |
| Hexagonal recessed socket, three holes with offset earth (J), often triple | Switzerland, Liechtenstein |
| Two round holes + half-round earth below (K, "surprised face") | Denmark, Greenland |
| Angled V slots (I); in China the combined "five-hole" socket (two-slot A above an angled I) on 86-type panels | China (five-hole: very characteristic) |
| Angled V slots (I), each socket with its own small switch; slim vertical switch plates | Australia, New Zealand (also Argentina, Fiji, PNG) |
| Three large round pins in a triangle (D/M); white modular switch boards with switched sockets; "universal" multi-pin sockets | India, Nepal, Sri Lanka, Pakistan, Bangladesh; M also South Africa, Lesotho, Eswatini |
| Three round pins in a hexagon-shaped recess (N) | Brazil, South Africa (new installations) |
| Y/V three-pin (H) | Israel |
| Thai TIS three round pins (O) or universal sockets | Thailand |
| "Universal" sockets accepting A, C, G and I | hotels everywhere; homes in SE Asia, Middle East, parts of Africa: WEAK |

Pitfalls: hotels fit international and USB outlets, and travel adapters are portable. A Europlug (C)
fits most continental sockets, so the visible PLUG is weaker evidence than the wall SOCKET. Old
buildings keep legacy types (e.g. D/M on British lighting circuits). Use `observed`, LR ≤6, link it to
every country of the type (`countries --plug X --case C --clue N#`) and let other clues intersect.

Switch conventions: in the UK, Ireland, Australia, NZ, India and South Africa, rocker **down = on**;
in North America **up = on**. A light-switch plate's shape and size (US 2.75"×4.5" vertical, UK and
China 86 mm square, DIN 80 mm square, Australian slim vertical, Italian/Brazilian rectangular modular)
is a strong family clue.

## 6. Plumbing and bathroom

| Seen | Implies | Strength |
|---|---|---|
| High water level in the bowl, siphon-jet, tank lever at front-left | US/Canada | M–S |
| Dual-flush buttons, wall-hung bowl with concealed cistern and large flush plate (Geberit, Grohe, Viega) | Europe (esp. DE/AT/CH/NL/Nordics), Australia, much of Asia | M |
| "Shelf" (washout) toilet with a dry inspection shelf | Germany, Austria, Netherlands, Poland, Czechia, Hungary (older stock) | S-ish |
| Electronic bidet seat with Japanese control panel (TOTO, LIXIL, Panasonic) | Japan (also KR/TW/CN, more and more) | M–S |
| Small hand-wash basin on top of the toilet cistern | Japan | M |
| Squat toilet | East, South and Southeast Asia, Middle East, Turkey, parts of Southern and Eastern Europe, Africa | M |
| Bidet shower hose (shattaf) beside the toilet | Middle East, South and Southeast Asia, Turkey, Finland, parts of Eastern Europe | M |
| Separate bidet fixture | Italy (required in homes since 1975), Portugal, Spain, Greece, Argentina, Uruguay, Chile, Turkey (built-in nozzle), France (older) | M–S |
| Separate hot and cold taps on the basin | UK, Ireland (older stock) | M |
| Wall-mounted electric shower box (Mira, Triton, Aqualisa) | UK, Ireland | S |
| Electric shower head with wiring ("suicide shower", Lorenzetti) | Brazil, Peru, Central America | S |
| Unit bath: moulded plastic, deep tub, separate washing area with stool and bucket, control panel (Rinnai, Noritz) | Japan | S |
| Wet room: no enclosure, floor drain, shower on the wall | Korea, Taiwan, Hong Kong, parts of SE Asia | M |
| Wall-mounted water-heater tank ("geyser") above the shower | India, South Africa (term), Middle East, SE Asia | M |
| Combi boiler on a kitchen wall (Worcester Bosch, Vaillant, Baxi, Ideal) | UK (brands → UK), Europe | M |
| Garbage disposal switch by the kitchen sink | US/Canada | M |
| Shower curtain + tub-shower combo | US/Canada (also UK) | W |

## 7. Heating, cooling, ventilation

| Seen | Implies | Strength |
|---|---|---|
| Panel radiators with thermostatic valves | Europe, North China, Russia, Turkey, Korea (rare) | M |
| **Heat-cost allocators** (small meters clipped to radiators: Techem, ista, Brunata, Minol) | continental European apartment buildings (DE, AT, CH, DK, CZ, PL, IT, FR...) | S |
| Ribbed cast-iron "accordion" radiators (MS-140 type) painted many times | Russia, Ukraine, Belarus, Kazakhstan and the former USSR, plus Eastern Europe | S |
| Radiators indoors in China | north of the Qinling–Huaihe heating line | S |
| Underfloor heating, no radiators, linoleum floor (jangpan), residents sitting on the floor | Korea (ondol) | M–S |
| Ductless split AC indoor unit high on the wall | Asia, Southern Europe, Middle East, Latin America, Australia: W–M. The brand matters (Gree, Midea, Haier: China; Daikin, Mitsubishi: global/JP) | W–M |
| Window AC unit | US (esp. NYC), India, Middle East | M |
| PTAC through-wall unit under the hotel window | US/Canada hotels and apartments | S |
| Floor/ceiling forced-air registers, wall thermostat (°F) | US/Canada | M–S |
| Electric baseboard heaters | Canada, Norway, northeastern US | M |
| Kotatsu table, kerosene heater | Japan | S |
| Tiled stove (Kachelofen) | Austria, Germany, Switzerland, Nordic, Eastern Europe | M |
| Ceiling fan + mosquito net | tropics, South and Southeast Asia, US South, Australia, Latin America | W–M |

## 8. Windows, doors, floors, walls, ceilings

| Seen | Implies | Strength |
|---|---|---|
| Tilt-and-turn window with a single lever handle | Germany, Austria, Switzerland, Netherlands, Poland, Czechia, Nordics; now common across Europe, Russia, Turkey | M |
| Roller shutter with a strap winder beside the window (Rollladen / tapparelle / persianas / volets roulants) | DE, NL, BE, FR, IT, ES, PT, PL | M–S |
| Double (box) windows, two sashes one behind the other | Russia and the former USSR, Nordic and Central European old buildings (Vienna) | M |
| Sash window (vertical sliding, cords or spiral balances) | UK, Ireland, US older stock | M |
| Horizontal sliding aluminium windows | East/Southeast Asia, Latin America, US | W–M |
| Casement windows opened with a crank | US/Canada | W |
| Jalousie glass louvres | tropics: Philippines, Caribbean, Pacific, parts of Africa | M |
| Shoji screens, fusuma sliding doors, tatami | Japan | S |
| Security grilles on windows | Latin America, South Africa, SE Asia, Middle East | W–M |
| Genkan: step down at the entrance for shoes | Japan | S |
| Keypad/digital door lock on an apartment door | Korea (very common); China (common) | M |
| Double front door: steel outer + wooden inner | Russia, the former USSR | M |
| Doors opening outward (front doors) | Nordics | W |
| Heated linoleum with wood print (jangpan) | Korea | M |
| Wall-to-wall carpet in homes | US, UK, Ireland, Australia, NZ, Canada | W–M |
| Terrazzo or large polished tiles everywhere | South Asia, Latin America, Mediterranean, Middle East, SE Asia | W |
| Herringbone parquet | Europe, Russia | W |
| Deep window reveals (thick masonry walls) | Europe, Russia, older buildings generally; vs thin drywall frames (North America) | W–M |
| Popcorn ceiling | US (1950s–80s stock) | M |
| Exposed surface conduit on walls and ceilings | retrofits: Italy, Spain, Japan; common in South/SE Asia | W |
| Suspended ceiling grid: 600×600 mm (most of the world) vs 2×4 ft (610×1220 mm, US) | metric vs US | M |

## 9. Safety and public-information signage (usually legally mandated, so very strong)

| Seen | Implies | Strength |
|---|---|---|
| Green "running man" exit sign (ISO 7010) | most of the world (Japan originated it, 1982) | W alone |
| Red or green "EXIT" text sign | United States (local codes); old Canadian stock | M–S |
| "非常口" (JP), "安全出口" (CN), "비상구" (KR), "Notausgang" (DE), "Sortie de secours" (FR), "Salida de emergencia" (ES), "Uscita di emergenza" (IT) | language → country | S |
| Fire extinguisher label language and standard; UK colour bands (cream foam, blue powder, black CO2) on red bodies | UK (bands) / EU EN3 / US UL ratings / JP "消火器" ABC labels | M–S |
| Fire alarm call point: "PULL DOWN" pull station (US) vs "break glass / push" (UK/EU) vs "火災報知機 強く押す" (JP) | standard family | M–S |
| "FIRE HOSE REEL" (UK, HK, SG, AU, NZ), "消火栓" (JP/CN/TW), "소화전" (KR) | region | M |
| **Evacuation plan** ("You are here", often on the back of hotel doors) | building name, address, floor, room number, layout: S. Crop it at full resolution. ISO 23601 symbols suggest Europe. | S |
| GDPR-style CCTV signs naming the controller and address (EU), UK "CCTV in operation" with ICO details | country + often the operator | S |
| Emergency numbers on signs (911, 112, 999, 000, 110/119/120, 995, 100/101/102...) | `countries --emergency 999` | S |
| Braille + raised-character room signs (ADA) | United States | M |
| Yellow tactile paving indoors (stations, malls) | Japan (origin), China, Korea, Taiwan | M |
| No-smoking signs with fines in local currency | country | S |

## 10. Lifts, stairs, floor numbering

| Seen | Implies | Strength |
|---|---|---|
| Lift inspection certificate: US state certificate with the building address; China 电梯使用标志 with registration code and issuing city bureau; Japan 昇降機定期検査報告済証; Korea 승강기 안전검사; Germany TÜV sticker; HK EMSD | building or city, often the address itself | S |
| Lift maker plate (Otis, Kone, Schindler, Mitsubishi, Hitachi, Fujitec, Toshiba, Hyundai Elevator, Orona, TK Elevator) | weak alone; Hyundai Elevator → Korea; Orona → Spain | W–M |
| Ground floor "1"/"1F" | North America, East Asia, Russia and the former USSR, Norway, Finland (Denmark: "st." is the ground floor and 1 the floor above) | M |
| Ground floor "G", "0", "E"/"EG", "RC", "PB", "PT", "BG", "T" (térreo), "L" (lobby) | G: UK, Commonwealth. E/EG: DE/AT. RC: FR/BE/CH. PB: ES/MX/AR. PT: IT. BG: NL. T: BR. L: US lobby | M–S |
| Floors 4, 14, 24 missing (or 4 shown as "F") | Chinese-speaking regions, Korea ("F"), Japan in some buildings, Vietnam | M |
| Floor 13 missing | US/Western hotels | W–M |
| "LG / UG / B1 / M" levels | malls in SG/HK/MY/AU/UK (LG/UG), East Asia (B1) | W–M |
| Room number format (floor + 2 digits is near-universal) | the floor (for window-view geometry) | W |

## 11. Products, brands, retail, payment

| Seen | Implies | Strength |
|---|---|---|
| Supermarket/retail chain brand on bags, receipts, price tags (Tesco, Sainsbury's → UK; Carrefour, E.Leclerc → FR; Mercadona → ES; Albert Heijn → NL; Woolworths, Coles → AU; Oxxo → MX; Lawson, FamilyMart → JP, also TW/TH/CN; Walmart, Target → US. 7-Eleven is everywhere, but its store format differs by country) | country, sometimes region | M–S |
| Payment acceptance stickers and terminals: Interac (CA), girocard (DE), CB (FR), Bancontact (BE), Dankort (DK), BankAxept/Vipps (NO), Swish (SE), MobilePay (DK/FI), Bizum (ES), Multibanco (PT), EFTPOS (AU/NZ), UPI (IN), Pix (BR), PromptPay (TH), PayNow (SG), Alipay/WeChat Pay (CN), PayPay/Suica (JP), Octopus (HK), EasyCard (TW), T-money (KR), Mir (RU) | country | S |
| Regulatory marks: CE (EU), UKCA (UK, 2021+), EAC (RU/BY/KZ/AM/KG), CCC (CN), PSE (JP), KC (KR), BIS (IN), INMETRO (BR), NOM (MX), RCM (AU/NZ) | market where the product was SOLD | M |
| Recycling marks and bins: Triman (FR, 2015+), Grüner Punkt (DE/EU), プラ/PET marks (JP), 可回收物 (CN), bin colour schemes | country | M |
| Local beverage and food brands (Irn-Bru → Scotland; Inca Kola → Peru; Guaraná Antarctica → Brazil; Mezzo Mix → DE/AT/CH...) | country/region | M |
| Cigarette packs: plain packaging and national warning designs | country | M–S |
| Medicines: Panadol, Doliprane (FR), Tachipirina (IT), ben-u-ron (DE/PT), Tylenol (US); pharmacy labels | country | M |
| Chain store with corporate interior | weak alone. Local decor (murals, local photos), the window view and the layout identify the branch | W→S |

## 12. Appliances, devices, media

| Seen | Implies | Strength |
|---|---|---|
| TV channel logo, news ticker, programme guide | country, often region or time | S |
| Keyboard: QWERTZ (DE/AT/CH/CZ/SK/HU/Balkans), AZERTY (FR/BE), Swiss keys, Ñ (ES/LatAm), Ç (PT/BR), Å Ä Ö / Æ Ø (Nordics), Turkish Ğ Ş or F-layout, Cyrillic, Hangul, kana, Arabic, Hebrew, Greek, Thai, ₹ key (IN), £ on "3" (UK) | country set | S |
| Phone or laptop screen: carrier name, language, weather widget units, map app (Naver/Kakao → KR, Amap/Baidu → CN, Yandex/2GIS → RU/CIS) | country | S |
| Rice cooker, hot-water dispenser/thermos pot | East/Southeast Asia | W |
| Electric kettle | UK, Europe, Asia; less common in US homes | W |
| Washing machine in the kitchen | UK, Ireland | M |
| Front-loader + drying rack (Europe) vs top-loader + dryer (North America); top-loaders are also common in East and Southeast Asia and Latin America | weak family hint | W |
| Over-the-range microwave, French-door fridge | US/Canada | W |
| LPG cylinder by the stove | India, Latin America, SE Asia, Middle East, Africa | M |
| Samovar, Turkish tulip tea glasses, mate gourd + bombilla | RU/IR; TR; AR/UY/PY/South BR | M |
| Regional appliance brands: Godrej (IN), Arçelik/Beko (TR), Mabe (MX/LatAm), Brastemp/Consul (BR), Defy (ZA), Fisher & Paykel (NZ/AU) | country | M |

## 13. Furniture, decor, style, patterns, textiles

Use as M/W evidence. Taste travels, so always seek a fixed or textual clue to corroborate.

| Seen | Implies |
|---|---|
| Azulejos (painted tin-glazed tiles, often blue-white) | Portugal; also Brazil (colonial), Spain |
| Zellige mosaics, carved plaster, brass lanterns, low cushioned seating | Morocco and the Maghreb |
| Iznik/Kütahya tiles, kilims, nazar beads | Turkey |
| Persian carpets with floor cushions (poshti) | Iran (carpets alone: global) |
| Mashrabiya screens, majlis floor seating along walls | Gulf / Arab world |
| Talavera tiles, papel picado, ofrendas | Mexico |
| Delftware | Netherlands (souvenir trap) |
| Wall carpets (rugs hung on walls), lacquered "stenka" wall units, crystal in glass cabinets | Russia and the former USSR, Eastern Europe |
| Washitsu (tatami, tokonoma alcove, shoji) | Japan |
| Hanji paper, low floor tables, ondol living | Korea |
| Carved wood lattice, red lanterns, round moon doors | China (also diaspora restaurants: trap) |
| Batik, carved teak, rattan | Indonesia, Malaysia |
| Royal portraits, a Buddha shelf mounted high on the wall, Thai silk | Thailand |
| Andean weaving, Peruvian/Bolivian textiles | Andes (souvenir trap) |
| Tartan, Hawaiian/Polynesian prints, kente, Maasai shuka | regional (often souvenir) |
| Scandinavian minimalism, IKEA products | weak: global |
| Hotel brand design packages (carpet, headboard, art, lamps) | the brand. Then enumerate its properties (scene-playbooks.md) |
| Unique artwork, sculpture, murals, custom carpet patterns | often property-specific: reverse-search a tight crop, and describe it in a picture search (`igl.py refs`) |

## 13a. Local references: pictures and objects that point at the town

What a venue hangs on its walls and leaves on its tables is often local. These rarely name the venue,
but they give the town or the coast, which turns "a hotel somewhere in the country" into a short list.

| Seen | Implies | Strength |
|---|---|---|
| A painting, print or photograph of a recognisable landmark, coastline, skyline or mountain | the venue is usually within sight or a short drive of it; identify the landmark (reverse-search a tight crop) | M–S for the area |
| A framed local map, nautical chart, old town plan, railway poster | the town or region shown | M–S |
| Historic photos of "this building" or "this street" (lobbies, pubs, restaurants love them) | the venue's own history: read the captions | S |
| Local newspaper, listings magazine, tourist leaflets, a "what's on" board | the town (and the date) | S |
| Calendar, pen or business card from a named local business; a taxi firm's card with a dialling code | the neighbourhood | M–S |
| Local club pennants, team scarves, regatta or race memorabilia, school crests | the town or district (fans travel: M) | M |
| Regional food and drink on display: local brewery taps, regional wines, named farm produce | the region | M |
| A named local artist's work throughout a hotel | commissioned for the property: search the artist | M |

A landmark picture is the same trap as any souvenir when it is famous (the Eiffel Tower hangs
everywhere); it is good evidence when it is local and unglamorous (a chalk headland, a town pier, a
particular bridge). Record it as `observed`, link it to the area, and let it choose where to enumerate.

## 14. Religion, customs, seasonal decor

| Seen | Implies | Strength |
|---|---|---|
| Qibla direction sticker (hotel ceiling, desk, drawer), prayer mat, Quran on a stand | Muslim-majority country hotel | M–S |
| Mezuzah on door frames | Israel (on most doorways of public buildings) or Jewish homes elsewhere | M |
| Orthodox icon corner | RU, UA, BY, RS, GR, RO, BG, GE, CY | M |
| Crucifix in public rooms (classrooms, offices); "Herrgottswinkel" corner | Catholic regions: PL, IT, ES, IE, Bavaria/Austria, Latin America, Philippines | M |
| Butsudan or kamidana | Japan | S |
| Chinese god altar, "福" upside down, red couplets, feng-shui bagua mirror | Chinese communities (CN/TW/HK/SG/MY + diaspora) | M |
| Hindu puja shelf, deity images, marigold garlands | India, Nepal, Bali; diaspora | M |
| Maneki-neko | JP/CN/SE Asia (portable) | W |
| Leader or royal portraits (Thai King, Moroccan King, Gulf rulers, Ho Chi Minh, Kim portraits) | country | S |
| Seasonal: Christmas (Dec), Lunar New Year (Jan–Feb), Ramadan lanterns (moving), Diwali (Oct–Nov), Halloween (Oct), Día de Muertos (1–2 Nov), Hinamatsuri (3 Mar), Koinobori (May), Tanabata (7 Jul), Mid-Autumn (Sep–Oct), Songkran (Apr), Hanukkah, Easter | season and date, plus culture | M |
| Shoes off at the door, slippers rack | JP, KR, Nordics, Eastern Europe, Turkey, Middle East, much of Asia | W–M |

## 15. People and personal items (the privacy rules of SKILL.md apply)

Use items only for what they say about the PLACE. Never identify a person.

| Seen | Implies | Strength |
|---|---|---|
| Staff uniform + name badge with the employer's logo (hotel, hospital, airline, shop) | the employer → venue | S |
| Conference lanyard/badge, event banner (name, year, city) | event → venue + date | S |
| Boarding pass, bag tag (airport codes), transit ticket (operator, station), museum ticket | route, airport or venue + date | S |
| Receipt (store name, address, VAT/tax ID, date and time) | the store, often the building | S |
| Parcel/mail label | city/postcode level (redact names; private address → rule 11) | S |
| School uniform, university or club merchandise | the institution or local club (fans travel: M) | M |
| Shopping bags, coffee cups, takeaway packaging | a nearby store (bags travel) | M |
| Newspaper or magazine masthead and date | country/city + date | S |
| Children's school notices, calendars from local businesses | town or district | S |
| Traditional dress: kimono/yukata, hanbok, sari, shalwar kameez, thobe/abaya, barong, áo dài, dirndl | culture. Tourists and diaspora wear it too | W–M |
| Physical appearance / apparent ethnicity | weak, bias-prone, diaspora and tourism: LR ≤1.5, never exclude | W |

## 16. Light, time and season

- Window light colour and angle, shadow direction on the floor + EXIF time → facade orientation, after
  the place is known (`igl.py sun`, window-and-light.md).
- Darkness outside at a given local time → latitude and season consistency.
- Plants visible outdoors (bare trees, blossoms, palms) → season and climate (pair with the date).
- Indoor clothing (coats indoors suggest little heating), open windows, fans running → climate/season.
  Weak.

## 17. Negative clues

Write what is absent: no AC in a hot-looking region, no radiators in a cold one, no Chinese characters
anywhere in a "Chinese-style" interior, no English on any notice. Negative clues depend on visibility.
Only use them for ranking (LR 0.5–0.8), never for exclusion, unless the absent thing would certainly be
in the frame.

## 18. Portable-object traps

Anything that can be carried, bought online or shipped (souvenirs, branded pens, imported food, travel
adapters, IKEA furniture, tourist textiles, books) indicates where the OBJECT came from, not where the
ROOM is. Weight portable objects at most `observed` LR 3 unless several independent portable clues
agree, or a fixed clue confirms them. Fixed infrastructure (sockets, switches, windows, radiators,
mandated signage, lift certificates) outranks movable decor.
