"""Gemeinsame, installierbare Metadaten fuer Import und Nachkontrolle.

Die JSON-/TSV-Dateien in diesem Paket sind die Snapshot-Quellen des Imports:
`doctypes.json` (DocType-Spezifikation der App) und `live_schema_ist.tsv`
(Spalten der Tabellen, die der Import wirklich liest — die 73 App-DocTypes
plus die Frappe-Core-Tabellen aus `tools/import_aus_frappe.py:CORE_TABLES`).
Die TSV ist bewusst auf genau diesen Ausschnitt reduziert; Tabellen fremder
Apps stehen nicht darin. Bei einer erneuten Inventarisierung beide Snapshots
gemeinsam aktualisieren. Das Modell-Mapping wird nicht kopiert: es bleibt die
gemeinsame Quelle im models-Paket.
"""
import json
from importlib.resources import files


def doctypes():
    return json.loads((files(__package__) / 'doctypes.json').read_text(encoding='utf-8'))


def mapping():
    return json.loads((files('diakronos_app.models') / '_mapping.json').read_text(encoding='utf-8'))


def live_schema():
    return (files(__package__) / 'live_schema_ist.tsv').read_text(encoding='utf-8')
