"""Schema-Drift-Waechter.

Haelt `import_metadaten/live_schema_ist.tsv` — den (auf die Diakronos-DocTypes
reduzierten) Abzug der Frappe-DB — gegen die generierten SQLAlchemy-Modelle.
Schlaegt fehl, sobald eine Live-Spalte kein Modellfeld hat.

Warum das sein muss: der Generator baut die Modelle aus dem DocType-Schema
(den DocType-JSONs). Die laufende DB kennt aber Spalten, die in den JSONs
fehlen. Ohne diesen Test faellt das erst beim 1:1-Import in P7 auf — als
stiller Datenverlust.

Die 12 Spalten, die aus diesem Abgleich bereits nachgezogen wurden, stehen in
Schema-Nachtrag der Portierung und sind in Schema-Drift-Nachtrag begruendet.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from diakronos_app.models.base import Base

# Frappe-interne Spalten: von Frappe selbst gepflegt (Kommentare, Tags,
# Zuweisungen), NICHT Teil des fachlichen Schemas. Bewusst als EXPLIZITE Liste
# — kein Praefix-Match auf "_", damit ein neu auftauchendes Frappe-Feld
# (`_seen` selbst war so ein Fall) den Test rot macht statt still durchzurutschen.
FRAPPE_INTERN = {
    "_user_tags",
    "_comments",
    "_assign",
    "_liked_by",
    "_seen",
    "_deleted",       # Frappe-Soft-Delete-Marker (falls je aktiviert)
    "_assign_comment",  # Frappe-ToDo-Verknuepfung
}

# Der Abzug liegt IM Python-Paket (Paketdaten, in pyproject eingetragen) — er
# ist damit auch im ausgerollten Image vorhanden. `inventar/` bleibt die
# interne Arbeitsunterlage (per .dockerignore ausgeschlossen) und wird hier
# nur als Rechenbasis fuer den Vergleich App-DocType vs. Frappe-Core benutzt,
# wenn sie existiert.
INVENTAR = Path(__file__).resolve().parents[2] / "inventar"
TSV = (
    Path(__file__).resolve().parents[1]
    / "src" / "diakronos_app" / "import_metadaten" / "live_schema_ist.tsv"
)

# Die TSV ist auf die Diakronos-Tabellen reduziert: 73 App-DocTypes + die
# Frappe-Core-Tabellen, die der Import wirklich liest (`CORE_TABLES` in
# tools/import_aus_frappe.py). Der Selbstschutz unten haelt diese Untergrenze.
MIN_TABELLEN = 70

# DocType-Name (Frappe) -> Modelltabelle.
# Wird ueber `models/_mapping.json` aufgeloest, das der Generator mitschreibt.
MAPPING = (
    Path(__file__).resolve().parents[1]
    / "src" / "diakronos_app" / "models" / "_mapping.json"
)


@pytest.fixture(scope="module")
def live_schema() -> dict[str, set[str]]:
    """`import_metadaten/live_schema_ist.tsv` -> {DocType-Name: {spalte, ...}}.

    Fehlt der Abzug, schlaegt der Test FEHL statt sich stillschweigend
    abzuschalten. Ein Waechter, der ohne seine Eingabe einfach gruen bleibt,
    gibt falsche Sicherheit — genau der Zustand, den er verhindern soll.
    """
    if not TSV.is_file():
        pytest.fail(
            f"Live-Schema-Abzug fehlt: {TSV} — der Drift-Waechter kann so nicht "
            "laufen. Abzug nach `import_metadaten/live_schema_ist.tsv` erzeugen, "
            "nicht diesen Test ueberspringen."
        )
    out: dict[str, set[str]] = {}
    for line in TSV.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        tab, _, cols = line.partition("\t")
        if not tab.startswith("tab"):
            continue
        doctype = tab[3:]
        out[doctype] = {c for c in cols.split(",") if c}
    return out


@pytest.fixture(scope="module")
def mapping() -> dict:
    import json

    assert MAPPING.is_file(), f"Modell-Mapping fehlt: {MAPPING}"
    return json.loads(MAPPING.read_text(encoding="utf-8"))


def test_abzug_ist_nicht_leer(live_schema):
    """Selbstschutz: ein leerer/fehlgeschlagener Abzug darf nicht gruen sein."""
    assert len(live_schema) >= MIN_TABELLEN, (
        f"nur {len(live_schema)} Tabellen im Abzug — Datei kaputt oder geleert?")
    assert "Mitglied" in live_schema
    assert "User" in live_schema



# Spalten, die eine LIVE-Tabelle fuehrt, das ZIELMODELL aber bewusst nicht:
# `import_table` schneidet die Dump-Spalten gegen das Zielinformationsschema
# und ignoriert sie damit — es geht nichts verloren, was das Modell traegt.
# Fuer die Frappe-Core-Stubs (models/core.py) ist das ausnahmslos richtig: sie
# halten Identitaet, Rollen und die Datei-Anbindung, nicht Frappes Desk-Felder
# und keine Ordner-/Cloud-Synchronisation.
CORE_BEKANNT_NICHT_IMPORTIERT = {
    "File": {
        # Verknuepfung Datei -> Ordner-DocType (Frappe-Desk-Baum). Dateien
        # haengen in Diakronos ueber attached_to_* an ihrem Dokument.
        "parent", "parenttype", "parentfield", "old_parent", "folder",
        "is_folder", "is_home_folder", "is_attachments_folder", "file_type",
        # Frappe-Modulzuordnung + Cloud-Anbindungen (Dropbox, Google Drive):
        # fuer den Diakronos-Import ohne Bedeutung, das Ziel hat keine Felder.
        "module", "thumbnail_url", "uploaded_to_dropbox",
        "uploaded_to_google_drive",
    },
}


def _core_tabellen() -> dict[str, str]:
    """{DocType-Name: PostgreSQL-Tabelle} der Frappe-Core-Tabellen."""
    return {
        dt: mapping_info["table"]
        for dt, mapping_info in json.loads(
            (Path(__file__).resolve().parents[1]
             / "src" / "diakronos_app" / "models" / "_mapping.json").read_text(encoding="utf-8")
        ).items()
        if mapping_info["table"] in {
            "doctype", "role", "user", "has_role", "user_role",
            "dynamic_link", "event_participants", "file",
        }
    }


def test_core_stubs_nehmen_jede_live_spalte_auf_oder_schneiden_sie_bewusst_ab(
    live_schema,
):
    """Gegenprobe fuer die Core-Tabellen im Abzug.

    Die Core-Modelle sind absichtlich schmal (kein Modellfeld fuer Frappes
    Desk-Felder). Damit `import_table` keine Spalte STILL verliert, muss jede
    Live-Spalte entweder ein Modellfeld haben oder hier ausdruecklich als
    "wird nicht importiert" stehen.
    """
    pruefbar = {"File"}  # Tabellen, deren Import-Verlust fachlich zaehlt
    geprueft = 0
    for doctype, table in _core_tabellen().items():
        if doctype not in pruefbar:
            continue
        live_cols = live_schema.get(doctype)
        if live_cols is None:
            continue
        modell = Base.metadata.tables.get(table)
        assert modell is not None, f"Core-Tabelle fehlt im Modell: {table}"
        fehlend = sorted(
            live_cols - set(modell.columns.keys()) - FRAPPE_INTERN
            - CORE_BEKANNT_NICHT_IMPORTIERT[doctype]
        )
        assert not fehlend, (
            f"{doctype}: Live-Spalten ohne Modellfeld und ohne Eintrag in "
            f"CORE_BEKANNT_NICHT_IMPORTIERT: {fehlend}"
        )
        geprueft += 1
    assert geprueft == len(pruefbar)


def _app_doctypes() -> set[str]:
    """Die 73 App-eigenen DocTypes — Geltungsbereich des Drift-Waechters.

    Quelle ist der installierbare Snapshot `import_metadaten/doctypes.json`
    (auch im Image vorhanden), nicht die interne Arbeitsunterlage.
    """
    from diakronos_app import import_metadaten

    return {d["name"] for d in import_metadaten.doctypes()}


def test_keine_live_spalte_ohne_modellfeld(live_schema, mapping):
    """Der eigentliche Drift-Waechter.

    Fuer jede Tabelle des Abzugs, die ein generiertes Modell hat, muss jede
    Live-Spalte (ausser den Frappe-internen) als Spalte im Modell existieren.
    """
    problems: dict[str, list[str]] = {}
    geprueft = 0

    app_doctypes = _app_doctypes()

    for doctype, live_cols in sorted(live_schema.items()):
        if doctype not in mapping:
            # DocType liegt ausserhalb der 73 (z.B. Frappe-Core) — kein Modell
            # erwartet. Details: Portierungsbericht.
            continue
        if doctype not in app_doctypes:
            # Frappe-CORE-Stub (User, Role, DocType, File, Dynamic Link,
            # Event Participants). Diese Modelle sind BEWUSST minimal: sie
            # halten keine Diakronos-Fachdaten, sondern nur so viel, dass die
            # ForeignKeys aufloesen. Frappes echtes tabUser hat ~70 Spalten
            # (api_key, desk_theme, dropbox-Flags ...) — die nachzubauen waere
            # falsch, nicht sicherer. Der Waechter schuetzt App-Daten vor
            # stillem Verlust; dafuer sind ausschliesslich die 73 DocTypes
            # aus dem DocType-Schema des Frappe-Originals massgeblich.
            continue
        table_name = mapping[doctype]["table"]
        table = Base.metadata.tables.get(table_name)
        if table is None:
            problems[doctype] = [f"<Tabelle {table_name!r} fehlt im Modell>"]
            continue

        geprueft += 1
        model_cols = set(table.columns.keys())
        fehlend = sorted(live_cols - model_cols - FRAPPE_INTERN)
        if fehlend:
            problems[doctype] = fehlend

    assert geprueft > 60, f"nur {geprueft} Tabellen abgeglichen — Mapping kaputt?"
    assert not problems, (
        "Live-Spalten ohne Modellfeld (Drift):\n"
        + "\n".join(f"  {dt}: {cols}" for dt, cols in problems.items())
        + "\n\nFix: Spalte in Schema-Nachtrag der Portierung deklarieren und "
          "`python tools/gen_models.py` neu laufen lassen. Begruendung nach "
          "Schema-Drift-Nachtrag."
    )


def test_frappe_interne_liste_ist_explizit():
    """Die Ausnahmeliste ist absichtlich hart und klein — kein Praefix-Match."""
    assert FRAPPE_INTERN == {
        "_user_tags", "_comments", "_assign", "_liked_by", "_seen",
        "_deleted", "_assign_comment",
    }


def test_overlay_spalten_sind_im_modell(live_schema, mapping):
    """Gegenprobe: jede Overlay-Spalte muss LIVE existieren.

    Verhindert, dass ein Overlay-Eintrag stehen bleibt, nachdem die Spalte in
    der Quelle verschwunden ist (dann waere das Modell breiter als die Realitaet).
    """
    import json

    overlay_path = INVENTAR / "schema_overlay.json"
    if not overlay_path.is_file():
        pytest.skip(
            f"Overlay fehlt: {overlay_path} — die Gegenprobe ist eine reine "
            "Repo-Pruefung gegen die interne Arbeitsunterlage (nicht Teil des "
            "Images)."
        )
    overlay = json.loads(overlay_path.read_text(encoding="utf-8"))
    doc_types = overlay.get("docTypes") or {}

    verwaist: list[str] = []
    for doctype, fields in doc_types.items():
        live_cols = live_schema.get(doctype)
        if live_cols is None:
            verwaist.append(f"{doctype}.<ganze Tabelle fehlt im Abzug>")
            continue
        for f in fields:
            if f["fieldname"] not in live_cols:
                verwaist.append(f"{doctype}.{f['fieldname']}")
    assert not verwaist, (
        "Overlay-Spalten ohne Live-Entsprechung — Overlay-Eintrag entfernen: "
        + ", ".join(verwaist)
    )
