# indoor-geolocator

[English](README.md) · [简体中文](README.zh-CN.md) · [Português](README.pt-BR.md) · [Français](README.fr.md) · [Español](README.es.md) · [日本語](README.ja.md) · **Deutsch**

Ein Agent-Skill, der herausfindet, **wo ein Innenraumfoto aufgenommen wurde**: ein Hotelzimmer, eine
Wohnung, ein Restaurant, ein Geschäft, ein Bahnhof, ein Museum, ein Klassenzimmer, ein Auto. Er liefert
den Ort, die Adresse, Koordinaten mit Fehlerradius und eine Konfidenzstufe, die von den Belegen
tatsächlich getragen wird. Außerdem hinterlässt er einen aufgeräumten Fallordner, der jeden Schritt der
Herleitung zeigt.

Er ist ein quelloffenes OSINT-Werkzeug zur Bild-Geolokalisierung durch KI-Agenten: Schlussfolgern im Stil von GeoGuessr für Innenräume, gestützt auf Rückwärts-Bildersuche, OCR, EXIF-Metadaten und den Abgleich mit Referenzfotos.

**Projektseite und interaktive Demo:** https://ezharjan.github.io/indoor-geolocator/

Foto anhängen und den Skill aufrufen. Ein Prompt ist nicht nötig. Die Antwort kommt in der Sprache des
Nutzers und hat diese Form (die Werte sind Beispiele):

```
📍 <Ort> — <Adresse, Stadt, Land>
   51.044560, -114.064700 (WGS84) ± 60 m · Ebene: site · Konfidenz: MEDIUM
Warum: ... die 2 bis 4 entscheidenden Belege, jeweils mit Quelle und Art der Prüfung
Geprüft gegen: ... die verglichenen Referenzfotos, die übereinstimmenden Merkmale, der getestete Rivale
Beste Spur (ungeprüft): ... ein feinerer Kandidat, seine Koordinaten (der wahrscheinlichste Punkt) und der Test, der ihn bestätigen würde
Alternativen: ... der Zweitplatzierte, seine Wahrscheinlichkeit und der Test, der beide trennen würde
Nicht geprüft / Grenzen: ... was nicht geprüft werden konnte und warum
Fallordner: .../photo-geolocation (REPORT.md enthält die vollständige Herleitung)
```

## Was er tut

Der Skill gibt dem Modell einen strengen Arbeitsablauf, bei dem Genauigkeit an erster Stelle steht, und
einen Kommandozeilen-Werkzeugkasten (`scripts/igl.py`, Python 3.9+, Pillow). Jede Beobachtung wandert in
ein einziges Protokoll, und Rangfolge und Konfidenz werden aus diesem Protokoll berechnet statt behauptet.

Innenraumfotos werden aus einer Handvoll Gründen falsch verortet, und der Ablauf ist um sie herum gebaut:
Ein ähnlich aussehender Raum wird für den Ort gehalten, der erste plausible Kandidat wird beibehalten,
Maschinenausgabe (OCR auf einem Teppich, das Etikett einer Suchmaschine, eine Suche, die nie lief) wird
als Tatsache gelesen, ein tragbarer Gegenstand wird als Gebäude gelesen, eine Marke wird für eine Filiale
gehalten, und Genauigkeit wird erfunden.

1. **Aufnahme.** Kopiert das Foto Byte für Byte. Liest EXIF, GPS, XMP, IPTC, ICC, das eingebettete
   Vorschaubild (ein Zuschnitt oder eine Bearbeitung fällt auf), das Muster des Dateinamens, KI-Marker
   und C2PA-Content-Credentials und rechnet den UTC-Versatz in Zeitzonen um. Prüft in fünf Sekunden,
   welche Online-Dienste der Werkzeugkasten erreicht.
2. **Zuerst Hypothesen.** Zwei bis vier gereihte Hypothesen werden vor jeder Werkzeugausgabe
   festgehalten (Schutz vor Ankereffekten).
3. **Das ganze Foto lesen.**
   - Auf Präzision gefilterte OCR (Textur wird nicht als Text gemeldet), QR-Codes und Barcodes mit
     Auswertung des Inhalts (EMV-Zahlungscodes, Schweizer QR-Rechnungen, SEPA, UPI, WLAN, vCards,
     GS1-Präfixe), Textauswertung (Telefonnummern bis zur Stadt, Domains, Preise, Postleitzahlen,
     Einheiten, Steuerbegriffe).
   - Ein Katalog von rund 200 Hinweisen, den der Agent auf überlappenden Kacheln liest:
     Identitätsträger (Namen, einzigartige Kunst, der Ausblick), feste Standards (Steckdosen, Schalter,
     Sanitärinstallation, Sicherheitsschilder) und lokale Bezüge (ein Gemälde eines örtlichen
     Wahrzeichens, eine Karte, ein Faltblatt).
4. **Kandidaten finden.**
   - **Rückwärts-Bildersuche** ohne Oberfläche bei Yandex, TinEye und Baidu, dazu Google Lens und Bing
     über ein Browser-Werkzeug. Jeder Treffer wird mit dem Foto verglichen und als **COPY** (dieselbe
     Fotografie: Herkunft), **SAME SCENE** / **PARTIAL** (übereinstimmende Struktur) oder
     **unconfirmed** eingestuft.
   - **Bildersuche per Text** (`refs`): Bildersuchen für einen Ort oder für jeden Ort einer Art in
     einem Gebiet. Die Bilder werden mit dem Foto verglichen und **nach Ähnlichkeit sortiert, das
     ähnlichste zuerst**, angezeigt (DINOv2), sodass der richtige Ort auch dann auftaucht, wenn keine
     Bildunterschrift ihn beschreibt. In einem Test setzten zwei allgemeine Suchen nach Hotelbars in
     einem US-Bundesstaat die tatsächliche Bar unter 100 Bildern verschiedener Bars an die erste
     Stelle.
   - Namen, Telefonnummern, URLs und WLAN-Namen mit der Websuche des Agenten selbst; feste Standards
     offline über 250 Länder geschnitten; jeder Ort einer Art aus OpenStreetMap und Wikidata
     aufgezählt; Inserate und soziale Medien (ortsbezogen).
5. **Prüfen: die Schranke zwischen einer Spur und einer Antwort.** Zuerst wird ein
   Falsifikationstest aufgeschrieben. Die eigenen Fotos des Kandidaten werden neben das Foto gelegt,
   und bestimmte feste Merkmale werden gezählt (Fenster, Decke, Einbauten, der Ausblick, für den Ort
   geschaffene Kunst; Möbel belegen nur eine Gestaltung). Der nächste Rivale durchläuft denselben
   Vergleich. „Passt“ auch der Rivale, sind die Merkmale eine gemeinsame Gestaltung: Die
   Übereinstimmung wird für das Gebiet der Gruppe festgehalten, und die Orte bleiben Spuren.
6. **Konsistenz.** Zeitzone, Sonne, Wetter, Jahreszeit und Standards werden am Kandidaten geprüft, für
   den Zweitplatzierten wird argumentiert, und der entscheidende Schritt wird auf andere Weise
   wiederholt.
7. **Entscheidung.** Die Antwort ist die feinste Ebene, die die Belege bestätigen. Ein ungeprüfter Ort
   in einem bestätigten Gebiet wird als beste Spur mit eigenen Koordinaten (dem wahrscheinlichsten
   Punkt) gemeldet, nie als Antwort. Der Fallordner wird abgeschlossen und ausgedünnt.

### Genauigkeitsregeln, die im Code verankert sind

- **Obergrenzen nach Status.** Das Gewicht eines Hinweises ist danach begrenzt, wie er gewonnen wurde:
  eine Schlussfolgerung ≤3, eine Beobachtung ≤6, ein Bericht Dritter ≤10, Dateimetadaten oder eine
  zurückverfolgte Kopie des Fotos ≤20, auf einem vergrößerten Ausschnitt gelesener Text oder ein
  berechnetes Ergebnis ≤50, eine Übereinstimmung mit unabhängigen Referenzbildern ≤100. Das Etikett
  einer Suchmaschine ist eine Spur (≤3), was immer es sagt.
- **Identifizierende Hinweise und Kategoriehinweise.** Ein entscheidender Hinweis (ein im Foto
  gelesener Name, ein dekodierter Code, GPS, eine zurückverfolgte Kopie, eine übereinstimmende
  Referenz) identifiziert genau einen Ort und wird gegen alle Alternativen zusammen gewogen: LR 50
  bedeutet etwa 50:1, gleich wie viele Rivalen aufgeführt wurden. Ein Kategoriehinweis (ein
  Steckdosentyp, eine Sprache, ein Stil) konkurriert mit jeder Alternative einzeln, sodass erst
  mehrere zusammen ein Land festlegen.
- **Nachprüfbare Übereinstimmungen.** Ein `matched`-Hinweis muss mindestens drei bestimmte feste
  Merkmale nennen und die Vergleichsdatei zitieren. Eine Kopie des Fotos wird als Übereinstimmung
  abgelehnt: Sie ist Herkunft und wird als `traced` mit ihrer Seite festgehalten.
- **Die Rivalenkontrolle.** Eine Referenzübereinstimmung erreicht HIGH nur, wenn ein rivalisierender
  Ort denselben Vergleich durchlaufen hat oder wenn eine zweite entscheidende Linie (ein im Foto
  gelesener Name, GPS, eine zurückverfolgte Kopie) denselben Ort nennt.
- **Ein Ort braucht einen entscheidenden Hinweis.** Ähnlichkeit, Suchmaschinen-Etiketten und
  Bildunterschriften lassen einen Ort auf LOW, wie viele davon auch übereinstimmen: Genau diese
  Kombination erzeugt ein Doppelgänger.
- **Unabhängige Linien.** Übereinstimmung zählt nur zwischen unabhängigen Quellen (image, text,
  metadata, web, engine, map, reference, geometry). Fünf Dekor-Hinweise sind eine Linie.
- **Eine offene, stimmige Tafel.** Nicht aufgeführte Alternativen behalten auf jeder Ebene einen
  Anteil, eine Stadt ist nie sicherer als ihr Land, und ein Widerspruch gegen ein Land sperrt HIGH
  auch für das Hotel darin.
- **Ehrliches Scheitern.** Eine Suche, die blockiert wurde oder nie startete, wird als solche gemeldet,
  nie als „keine Ergebnisse“. Unbestätigte Bilder werden nie „anders“ genannt.
- **Abdeckungsschranke.** Dreizehn Kernmethoden müssen jeweils mit results, no_results oder
  not_applicable enden, bevor `check` besteht; `check` meldet außerdem einen Ort ohne
  Referenzvergleich oder ohne Rivalen, einen Rivalen, der ebenfalls passte, und Rückwärtssuchen, die
  nie liefen.

## Installation

**claude.ai, Claude Desktop und Cowork.**
1. Sicherstellen, dass die Codeausführung eingeschaltet ist (*Settings → Capabilities*). Netzzugang für
   die Codeausführung hilft (der Werkzeugkasten erreicht die Karten- und Rückwärtssuchdienste dann
   selbst); ohne ihn erledigt der Agent diese Schritte mit seinen eigenen Werkzeugen für Websuche,
   Fetch und Browser.
2. *Customize → Skills* öffnen, auf **+** klicken, **+ Create skill → Upload a skill** wählen und
   `indoor-geolocator.zip` auswählen.
3. Ein Foto anhängen und den Skill aufrufen oder einfach fragen: „Wo wurde das aufgenommen?“

Das Zip enthält den Ordner `indoor-geolocator/` auf oberster Ebene, wie der Upload es verlangt.

**Claude Code.** Den Ordner `indoor-geolocator/` nach `~/.claude/skills/` (alle Projekte) oder
`<project>/.claude/skills/` (ein Projekt) kopieren. Aufruf mit `/indoor-geolocator`, oder Claude greift
ihn auf, sobald ein Innenraumfoto geteilt wird.

**Andere Agenten** (Codex, Gemini CLI, Cursor, …): den Agenten auf `indoor-geolocator/SKILL.md`
verweisen. Der Werkzeugkasten ist eine schlichte Python-CLI.

**Abhängigkeiten.** Pillow ist erforderlich, unter Windows auch `tzdata`. Alles andere ist optional und
schaltet nur die jeweilige Methode frei.

```bash
pip install -r indoor-geolocator/requirements.txt             # Pillow (+ tzdata, unter Windows nötig)
pip install -r indoor-geolocator/requirements-optional.txt    # OpenCV + numpy, Playwright, onnxruntime, phonenumbers, HEIC, RapidOCR
playwright install chromium                                   # Rückwärtssuche ohne Oberfläche, Bildersuche, Seitenabzüge
# OCR-Engine (empfohlen): tesseract mit Sprachpaketen
#   apt install tesseract-ocr-all  |  brew install tesseract tesseract-lang  |  winget install UB-Mannheim.TesseractOCR
python indoor-geolocator/scripts/igl.py doctor                 # was hier funktioniert, was fehlt
```

Drei Extras zählen für die Genauigkeit am meisten: OpenCV (die Tests COPY / SAME SCENE), Playwright mit
Chromium (Rückwärts-Bildersuche und Bildersuche) und onnxruntime (Bilder nach Ähnlichkeit zum Foto
sortiert). Das Ähnlichkeitsmodell (DINOv2 ViT-S/14, 24 MB, Apache-2.0) ist nicht Teil des Skills: Es wird
bei der ersten Verwendung einmal von huggingface.co geladen und gegen einen SHA-256 geprüft.
`IGL_NO_EMBED=1` schaltet es ab.

## Den Werkzeugkasten direkt verwenden

```bash
IGL="python3 indoor-geolocator/scripts/igl.py"
$IGL init photo.jpg                                    # Fallordner + Metadaten + Rasteransicht + Netzprüfung
$IGL note CASE "Hypotheses: 1) ... 2) ..." --kind hypothesis --status inferred --source image
$IGL scan CASE                                         # OCR, QR/Barcodes, Textsignale, Kacheln zum Durchsehen
$IGL crop CASE --cell C3:D4 --enhance auto --label socket
$IGL revsearch CASE --cell B2:C3 --flip                # Yandex, TinEye, Baidu; jeder Treffer gegen das Foto eingestuft
$IGL share CASE --cell B2:C3                           # Links für Google Lens und Bing (temporäre Kopie)
$IGL countries --plug G --currency £ --drive left --case CASE --clue N2
$IGL refs CASE "hotel lounge sea view Poole"           # Bilder eines ganzen Gebiets, die ähnlichsten zuerst
$IGL geo poi --tag tourism=hotel --area "Poole" --case CASE --add site --parent C3
$IGL refs CASE "Hotel Name Poole lounge" --for C12     # die Fotos eines Kandidaten neben dem eigenen
$IGL compare CASE --refs E14 --pick 3,7 --for C12      # große Gegenüberstellung + Übereinstimmungstests
$IGL note CASE "Matches a traveller photo (2023)" --kind match --status matched --source reference --file E16 \
     --features "arched window pair; coffered ceiling 3x4; green marble fireplace" --for C12:60 --why "..."
$IGL refs CASE "Rival Hotel Poole lounge" --for C13    # die Rivalenkontrolle
$IGL rank CASE
$IGL answer CASE C12 --summary "..."
$IGL check CASE
$IGL finalize CASE
```

`$IGL <command> -h` dokumentiert jede Option. Unter Windows `python` statt `python3` verwenden. Südliche
und westliche Koordinaten funktionieren wie eingegeben (`--at -33.86,151.21`).

## Was man bekommt

```
photo-geolocation/
├── REPORT.md       die Antwort, die beste Spur, Konfidenz je Ebene, Belege, Kandidaten, Zeitleiste, Methoden, Umgang mit Daten
├── result.json     dasselbe als maschinenlesbares JSON (Schema igl.result/1)
├── case.json       das vollständige Protokoll: Hinweise, Kandidaten, Verknüpfungen, Ausschlüsse, Versuche, Zeitstempel
├── input/          das Foto (bytegenau) und metadata.json
└── evidence/       nur die Ausschnitte, Bögen, Vergleichsansichten und Abzüge, die das Protokoll zitiert
```

Arbeitsmaterial (Kacheln, Caches, Downloads) liegt in `.work/` und wird von `finalize` gelöscht, das auch
jede Belegdatei entfernt, die nirgends zitiert wird. Ein bestehender Fallordner wird nie überschrieben.

## Datenschutz und verantwortungsvoller Einsatz

- **Menschen sind keine Ziele.** Keine Gesichtserkennung und keine Identifizierung von Personen.
  - Kleidung, Uniformen, Namensschilder und persönliche Gegenstände werden nur für das genutzt, was sie
    über den Ort aussagen.
  - Die augenscheinliche ethnische Zugehörigkeit gilt als schwacher, verzerrungsanfälliger Kontext, nie
    als Ausschlussgrund.
  - Soziale Medien werden nach Orten, Text, Tags und dem Foto selbst durchsucht, nie nach Personen oder
    Verfassern von Beiträgen.
- **Privatwohnungen.** Bei einer erkennbaren Privatwohnung ohne genannten Zweck fragt der Skill einmal,
  wofür das Ergebnis gedacht ist. Ohne legitimen Zweck bleibt er auf Stadt- oder Stadtteilebene stehen.
- **Schwärzung.** Namen von Privatpersonen und Wohnadressen bleiben aus Berichten heraus.
  WLAN-Passwörter, IBANs und Namen aus Kontaktkarten werden überall geschwärzt, wo sie dekodiert oder
  von einer Suchmaschine oder Seite zurückgegeben werden.
- **Uploads.** Die Rückwärts-Bildersuche lädt das Foto (ohne Metadaten) zu den Suchmaschinen hoch.
  `share` legt eine Kopie ohne Metadaten bei einem temporären Hoster ab (nach 1 bis 3 Stunden gelöscht)
  für Lens und Bing, und `revsearch` tut dasselbe von sich aus, wenn das Upload-Formular einer
  Suchmaschine versagt (`--no-share` verhindert das). Der Bericht führt jede Suchmaschine und jede
  temporäre Kopie auf. `refs` sendet nur Suchtext, und das Ähnlichkeitsmodell läuft lokal. Ausschnitte
  ohne Personen sind vorzuziehen; markiert der Nutzer ein Foto als privat, wird nichts ohne Rückfrage
  hochgeladen.
- **Dienste.** Der Skill hält die Regeln der Dienste ein (Nominatim ≤1 Anfrage/s, begrenzte
  Overpass-Abfragen, identifizierender User-Agent). Er meldet sich nie im Namen anderer an, löst nie
  CAPTCHAs und betreibt nie Massenabruf. Optionale Schlüssel des Nutzers: `SERPAPI_KEY` für Google Lens
  innerhalb von `revsearch`, `WIGLE_API_NAME` / `WIGLE_API_TOKEN` für WLAN-SSID-Abfragen.
  `IGL_USER_AGENT` setzt einen eigenen User-Agent.

Geolokalisierungsergebnisse sind nach Belegen gewichtete Schätzungen, keine Gewissheiten. Vor dem Handeln
auf eine Antwort hin die Konfidenz, die beste Spur und die Zeile „nicht geprüft“ lesen.

## Aufbau des Repositorys

```
.
├── indoor-geolocator/          DER Skill (dieser Ordner wird installiert)
│   ├── SKILL.md                Arbeitsablauf, Belegregeln, Verhalten, Antwortformat
│   ├── LICENSE.txt             Kopie von LICENSE (das Zip kommt ohne die Wurzel des Repositorys)
│   ├── requirements*.txt
│   ├── references/             Hinweiskatalog, Leitfäden für Szenen und Suche, Fenster/Licht, Prüfung,
│   │                           Belege und Konfidenz, Quellen und Werkzeuge
│   ├── scripts/igl.py          die CLI; scripts/iglib/ enthält ihre Module
│   └── data/                   countries.json, gs1_prefixes.json (+ README mit Quellen und Lizenzen)
├── indoor-geolocator.zip       derselbe Skill, zum Hochladen gepackt
├── build_skill_zip.py          baut und prüft das Zip neu (nach jeder Änderung am Skill ausführen)
├── tools/build_data.py         Wartungswerkzeug: baut data/ aus Unicode CLDR und Wikipedia neu
├── tools/make_demo.py          Wartungswerkzeug: baut docs/demo/ mit der aktuellen Version neu
├── tests/                      Offline-Testsuite (pytest; `pytest.ini` verweist darauf)
├── docs/                       Projektseite (GitHub Pages) mit dem veröffentlichten Demofall
├── LICENSE
├── README.md                   dieses README auf Englisch
└── README.*.md                 Übersetzungen (zh-CN, pt-BR, fr, es, ja, de)
```

## Entwicklung

```bash
python -m pytest                   # Offline-Tests: Protokollregeln, Obergrenzen, Abgleich, Rangfolge, Parser, Geometrie;
                                   # außerdem Doku gegen CLI, das Zip gegen den Skill-Ordner, die Projektseite gegen den Demofall
python tools/build_data.py         # aktualisiert data/ (Quellen im Cache unter .data-src/; --offline baut aus dem Cache neu)
python tools/make_demo.py          # baut den Demofall in docs/demo/ mit der aktuellen Version neu
python build_skill_zip.py          # baut indoor-geolocator.zip neu, wenn sich der Ordner geändert hat; --check prüft nur
```

## Änderungsprotokoll

### 2.0.0

Die Genauigkeitsversion: gebaut gegen die häufigste falsche Antwort, einen selbstsicher benannten
Doppelgänger-Ort.

- **Finden.** Neuer Befehl `refs`: Bildersuche per Text (Brave, Startpage) und Galerieseiten, wobei
  jedes Bild mit dem Foto verglichen wird. Bilder und Treffer der Rückwärtssuche werden nach visueller
  Ähnlichkeit sortiert (DINOv2, optional), sodass die wahrscheinlichsten Referenzen die ersten Kacheln
  sind, die der Agent sieht.
- **Rückwärtssuche.** Jeder Treffer wird gegen das Foto als COPY / SAME SCENE / PARTIAL / unconfirmed
  eingestuft. Eine Suche, die nie startete, ist `unavailable`, nicht `no_results`; Ausweichweg per URL,
  wenn ein Upload-Formular versagt; optional Google Lens über den SerpApi-Schlüssel des Nutzers.
- **Prüfung.** `matched`-Hinweise müssen drei Merkmale nennen und den Vergleich zitieren; Kopien werden
  als Übereinstimmung abgelehnt und als Herkunft `traced` festgehalten; `compare --refs E## --pick`;
  die Rivalenkontrolle ist für HIGH erforderlich; Gestaltungsübereinstimmungen werden für das Gebiet
  festgehalten, mit den Orten als Spuren.
- **Konfidenz.** Entscheidende Hinweise werden gegen das gesamte Feld gewogen (ein bestätigter Ort wird
  nicht mehr durch nicht aufgeführte Länder oder durch die vom Agenten aufgezählten Rivalen verdünnt);
  ein Ort braucht für MEDIUM einen entscheidenden Hinweis; Suchmaschinen-Etiketten sind auf 3
  begrenzt; Widersprüche sperren HIGH die Kette hinunter; ein Ort ist mindestens so sicher wie der
  bestätigte Ort in ihm.
- **Lesen.** Die OCR-Ausgabe wird auf Präzision gefiltert (kein „Text“ und keine exotischen Schriften
  mehr, die von Teppichen und Decken abgelesen werden); `scan` schreibt einen Bogen mit den
  Textausschnitten; `crop --of` zoomt in jedes Belegbild.
- **Robustheit.** Ausweichen auf Photon, wenn Overpass nicht erreichbar ist, Downloads mit
  Wiederholung, Meldung von Ratenbegrenzungen je Lauf, Methoden, die sich aus festgehaltenen Hinweisen
  ergeben, `log` mit Kommalisten.
- **Ausgabe.** Eine Markierung der besten Schätzung (die Koordinaten der Spur, wenn die Antwort gröber
  ist), ein Prüfabschnitt mit der Rivalenkontrolle im Bericht, Kandidatentabellen, die sagen, was jede
  Zeile ist (die Antwort, ein Ort, der sie enthält, die ungeprüfte Spur, die Alternativen außerhalb
  der Tafel), `tools/make_demo.py` zum Neuaufbau des Demofalls und Tests, die die Projektseite an
  diesen Fall und das Zip an den Skill-Ordner binden.

### 1.1.0

Nicht eigens getaggt oder veröffentlicht: Diese Änderungen erscheinen erstmals mit 2.0.0.

- Ablauf neu geordnet um Wege der exakten Übereinstimmung und eine Prüfschranke; Hypothesen vor der
  Werkzeugausgabe; Aufgabenteilung zwischen dem Werkzeugkasten und den eigenen Werkzeugen des Agenten
  für Websuche, Fetch und Browser.
- Bewertung: eine offene Tafel auf jeder Ebene, stimmige Anteile entlang der Kette, Kategoriehinweise
  wandern nicht nach oben, Schranke bei der Antwort mit getrennter bester Spur, Prüfungen vor dem
  Bericht.
- Rückwärtssuche: Baidu ergänzt, Kontaktbögen ähnlicher Bilder, `share` für Lens und Bing per URL.
- `compare`: Tests auf Beinahe-Duplikat, auf dieselbe Fotografie und geometrisch mit SIFT/RANSAC, auch
  für gespiegelte Räume.
- Netzprüfung in `init`; `geo ... --print-url`; `note --for/--against` in einem Aufruf; C2PA-Leser.

### 1.0.0

Erste öffentliche Version.

## Lizenz

Code und Dokumentation stehen unter der [MIT License](LICENSE). Die Datendateien in
`indoor-geolocator/data/` behalten die Lizenzen ihrer Quellen:
- Felder aus Unicode CLDR: [Unicode License v3](https://www.unicode.org/license.txt).
- Aus Wikipedia abgeleitete Felder (Steckertypen, Netzspannung, Fahrseite, Notrufnummern, GS1-Präfixe):
  [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/), © Wikipedia-Autoren.

Einzelheiten stehen in [indoor-geolocator/data/README.md](indoor-geolocator/data/README.md).

Gestaltungsideen wurden aus den Open-Source-Projekten geo-sleuth, Geo-Guesser und Searching-skill
übernommen: im Code durchgesetzte Regeln, eine Kandidatentafel mit Likelihood-Quotienten, nach Linie
abgestufte Belege, eine Abdeckungsschranke für Methoden, „die Maschine ordnet zuerst“ mit einer
DINOv2-Ähnlichkeitsreihenfolge und SIFT/RANSAC-Prüfung. Das Ähnlichkeitsmodell ist DINOv2 (Meta AI,
Apache-2.0) im ONNX-Export, der als `Xenova/dinov2-small` veröffentlicht ist; es wird zur Laufzeit geladen
und hier nicht weiterverbreitet.
