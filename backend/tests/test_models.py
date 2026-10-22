"""Prueft die generierten SQLAlchemy-Modelle gegen das Inventar.

Sichert ab, dass
  * fuer alle 73 DocTypes des Frappe-Originals eine Tabelle existiert,
  * die Mapper ohne Fehler konfigurieren (Relationship-Wiring),
  * jeder DocType einen String-Primaerschluessel `name` besitzt,
  * Kindtabellen die Frappe-Spalten `parent`, `parenttype`, `parentfield` haben.
"""

import json
from pathlib import Path

import pytest
from sqlalchemy import String

from diakronos_app.import_metadaten import doctypes as paket_doctypes
from diakronos_app.models import __all__ as MODEL_EXPORTS
from diakronos_app.models.base import Base

MAPPING = Path(__file__).resolve().parents[1] / "src" / "diakronos_app" / "models" / "_mapping.json"

CHILD_PARENT_COLUMNS = {"parent", "parenttype", "parentfield"}


def test_umlaut_spaltennamen_bleiben_wortgleich():
    """Regression zur zweiten Drift-Klasse (siehe Schema-Drift-Nachtrag).

    `column_name()` darf Umlaute/ß NICHT zu `_` verstuemmeln: die Live-DB
    fuehrt `Mitglied.straße` wortgleich, und das Modell muss denselben
    Spaltennamen tragen — sonst laeuft der Port gegen eine Spalte, die es
    nicht gibt (frueher `stra_e`).

    Der Modell-Teil laeuft IMMER (er braucht nur die Modelle). Der
    `column_name()`-Teil braucht `tools/gen_models.py` — das ist eine
    Generator-Eingabe und per `.dockerignore`/Dockerfile NICHT im Image. Fehlt
    es, wird dieser Teil uebersprungen statt rot zu leuchten; im Repo/CI
    (tools/ vorhanden) laeuft er mit.
    """
    import sys

    tools_dir = Path(__file__).resolve().parents[2] / "tools"
    gen_models = tools_dir / "gen_models.py"

    # Modell-Teil: immer pruefen (keine externen Eingaben noetig).
    mitglied = Base.metadata.tables["mitglied"]
    assert "straße" in mitglied.columns

    if not gen_models.is_file():
        pytest.skip(
            f"tools/gen_models.py nicht vorhanden (Deployment-Kontext): {tools_dir} "
            "— der Modell-Teil oben ist trotzdem gelaufen."
        )

    sys.path.insert(0, str(tools_dir))
    from gen_models import column_name

    assert column_name("straße") == "straße"
    assert column_name("personenbezogene_daten_löschen") == "personenbezogene_daten_löschen"
    # Echte Trennzeichen werden weiterhin ersetzt.
    assert column_name("zwei worte") == "zwei_worte"
    assert column_name("stra-e") == "stra_e"


@pytest.fixture(scope="module")
def doctypes():
    """DocType-Schema aus dem installierbaren Paket (laeuft auch IM Image)."""
    return paket_doctypes()


@pytest.fixture(scope="module")
def mapping():
    assert MAPPING.is_file(), f"Mapping fehlt: {MAPPING}"
    return json.loads(MAPPING.read_text(encoding="utf-8"))


def test_mapper_configuration_succeeds():
    from sqlalchemy.orm import configure_mappers

    configure_mappers()  # wirft bei kaputtem Relationship-Wiring


def test_every_doctype_has_a_table(doctypes, mapping):
    tables = set(Base.metadata.tables)
    missing = [dt["name"] for dt in doctypes if mapping[dt["name"]]["table"] not in tables]
    assert not missing, f"Tabellen fehlen: {missing}"


def test_all_exports_exist():
    import diakronos_app.models as models

    missing = [name for name in MODEL_EXPORTS if not hasattr(models, name)]
    assert not missing, f"Exporte fehlen: {missing}"


def test_doctypes_have_string_primary_key(doctypes, mapping):
    problems = []
    for dt in doctypes:
        table = Base.metadata.tables[mapping[dt["name"]]["table"]]
        pk = list(table.primary_key.columns)
        if len(pk) != 1 or not isinstance(pk[0].type, String):
            problems.append((dt["name"], [c.name for c in pk]))
    assert not problems, f"Kein String-PK: {problems}"


def test_child_tables_have_frappe_parent_columns(doctypes, mapping):
    problems = []
    for dt in doctypes:
        if not dt.get("istable"):
            continue
        table = Base.metadata.tables[mapping[dt["name"]]["table"]]
        cols = set(table.columns.keys())
        if not CHILD_PARENT_COLUMNS <= cols:
            problems.append((dt["name"], sorted(CHILD_PARENT_COLUMNS - cols)))
    assert not problems, f"Eltern-Spalten fehlen: {problems}"


def test_foreign_keys_present():
    total = sum(len(t.foreign_key_constraints) for t in Base.metadata.tables.values())
    assert total > 0, "keine Foreign Keys erzeugt"
