"""iglib - the engine behind scripts/igl.py (indoor-geolocator skill).

Modules: util (I/O helpers), case (the ledger), scoring (ranking and confidence caps), imaging (views,
crops, tiles), metadata (EXIF/XMP/IPTC/provenance), ocr (text reader with a precision filter), codes
(QR/barcodes), textmine (patterns in text), knowledge (offline country standards), net (polite HTTP,
retrying downloads), geo (geocoding, OSM, Commons, Wikidata, time zones, sun), revsearch (reverse image
search engines), refs (reference photos: image search, gallery pages, ranking against the photo), match
(near-duplicate and geometric image tests), share (temporary public copies for search by URL), report
(REPORT.md / result.json), doctor (environment check), common (helpers shared by the command modules),
commands (ledger, knowledge and geodata subcommands), visual (revsearch, refs, compare, share, snapshot).
"""
__version__ = "2.0.0"
SCHEMA_CASE = "igl.case/1"
SCHEMA_RESULT = "igl.result/1"
