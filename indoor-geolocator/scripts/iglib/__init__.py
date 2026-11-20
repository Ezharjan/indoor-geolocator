"""iglib - the engine behind scripts/igl.py (indoor-geolocator skill).

Modules: util (I/O helpers), case (the ledger), scoring (ranking and confidence caps), imaging (views,
crops, tiles), metadata (EXIF/XMP/IPTC/provenance), ocr, codes (QR/barcodes), textmine (patterns in
text), knowledge (offline country standards), net (polite HTTP), geo (geocoding, OSM, Commons,
Wikidata, time zones, sun), revsearch (reverse image search), report (REPORT.md / result.json),
doctor (environment check), commands (the CLI subcommands).
"""
__version__ = "1.0.0"
SCHEMA_CASE = "igl.case/1"
SCHEMA_RESULT = "igl.result/1"
