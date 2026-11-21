"""Rechte: Chat-Modul standardmäßig an (Manuel 17.11.).

* Neue Hauptgruppe → ``kern.STANDARD_MODULE`` (Chat) sofort an, sonst nichts.
* ``verwaltung.standard_module_anlegen``: nur Administrator, wiederholbar,
  nimmt nichts weg, schaltet ein abgeschaltetes Modul NICHT eigenmächtig
  wieder ein, wenn es nicht aufgerufen wird.
* Migration ``r_chat_standard``: Bestand bekommt das Modul genau einmal,
  vorhandene Zeilen bleiben, ``downgrade`` nimmt nichts weg.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy import select

from diakronos_app import rechte as R
from diakronos_app.frappe_compat.exceptions import PermissionError
from diakronos_app.frappe_compat.session import set_user
from diakronos_app.models.rechte import RechteModul
from diakronos_app.rechte import kern
from diakronos_app.rechte import verwaltung as V

from test_r1_rechte_kern import (  # noqa: F401 — gemeinsame Welt
    ADMIN, MIRA, REBEKKA, SAMUEL, welt,
)

BACKEND = Path(__file__).resolve().parents[1]


def _module(sess, gruppe):
    sess.expire_all()
    return set(sess.execute(select(RechteModul.modul).where(RechteModul.gruppe == gruppe)).scalars())


@pytest.fixture(autouse=True)
def _benutzer_zuruecksetzen():
    yield
    set_user("Administrator")


def test_standard_ist_genau_der_chat():
    assert kern.STANDARD_MODULE == ("chat",)
    assert set(kern.STANDARD_MODULE) <= set(kern.MODULE)


def test_neue_gruppe_hat_den_chat_sofort(welt):
    from diakronos_app.api.gruppen import create_gruppe

    set_user(ADMIN)
    name = create_gruppe("Hauskreis Nord", None)["name"]
    assert _module(welt, name) == {"chat"}
    assert R.modul_aktiv(name, "chat")
    assert not R.modul_aktiv(name, "kalender")


def test_neue_gruppe_nur_durch_admin_kein_modul_ohne_gruppe(welt):
    from diakronos_app.api.gruppen import create_gruppe

    set_user(REBEKKA)
    with pytest.raises(PermissionError):
        create_gruppe("Heimlich", None)
    welt.expire_all()
    assert not welt.execute(select(RechteModul).where(RechteModul.modul == "chat")).scalars().all()


def test_standard_module_anlegen_nur_admin(welt):
    for wer in (REBEKKA, MIRA, SAMUEL):
        with pytest.raises(PermissionError):
            V.standard_module_anlegen(wer, "Jugend")
    assert "chat" not in _module(welt, "Jugend")


def test_standard_module_anlegen_wiederholbar_und_nimmt_nichts_weg(welt):
    vorher = _module(welt, "Jugend")
    assert V.standard_module_anlegen(ADMIN, "Jugend") == ["chat"]
    assert _module(welt, "Jugend") == vorher | {"chat"}
    assert V.standard_module_anlegen(ADMIN, "Jugend") == []
    assert _module(welt, "Jugend") == vorher | {"chat"}
    zeilen = welt.execute(select(RechteModul).where(
        RechteModul.gruppe == "Jugend", RechteModul.modul == "chat")).scalars().all()
    assert len(zeilen) == 1


def test_abgeschalteter_chat_bleibt_aus(welt):
    V.standard_module_anlegen(ADMIN, "Jugend")
    V.setze_module(ADMIN, "Jugend", sorted(_module(welt, "Jugend") - {"chat"}))
    assert not R.modul_aktiv("Jugend", "chat")
    # Jeder lesende Zugriff lässt ihn aus — nur der Administrator schaltet ihn ein.
    assert not R.darf(SAMUEL, R.LESEN, "chat_gespraech", gruppe="Jugend")
    assert "chat" not in _module(welt, "Jugend")


def test_chat_rechte_folgen_dem_modul(welt):
    assert not R.darf(SAMUEL, R.LESEN, "chat_gespraech", gruppe="Jugend")
    V.standard_module_anlegen(ADMIN, "Jugend")
    assert R.darf(SAMUEL, R.LESEN, "chat_gespraech", gruppe="Jugend")


# ── Migration ────────────────────────────────────────────────────────────────


def _migration():
    pfad = BACKEND / "alembic" / "versions" / "r_chat_standard.py"
    modul = importlib.util.module_from_spec(
        importlib.util.spec_from_file_location("r_chat_standard", pfad))
    modul.__spec__.loader.exec_module(modul)
    return modul


@pytest.fixture()
def bestand():
    engine = sa.create_engine("sqlite://")
    with engine.begin() as v:
        v.execute(sa.text("CREATE TABLE gruppe (name VARCHAR(140) PRIMARY KEY, geloescht_am DATETIME)"))
        v.execute(sa.text(
            "CREATE TABLE rechte_modul (id INTEGER PRIMARY KEY AUTOINCREMENT,"
            " gruppe VARCHAR(140) NOT NULL, modul VARCHAR(40) NOT NULL)"))
        v.execute(sa.text("CREATE UNIQUE INDEX uq_rechte_modul_gruppe_modul ON rechte_modul (gruppe, modul)"))
        v.execute(sa.text(
            "INSERT INTO gruppe (name, geloescht_am) VALUES"
            " ('Chor', NULL), ('Jugend', NULL), ('Alt', '2026-01-01 00:00:00')"))
        v.execute(sa.text(
            "INSERT INTO rechte_modul (gruppe, modul) VALUES"
            " ('Chor', 'chat'), ('Chor', 'kalender'), ('Jugend', 'wiki')"))
    return engine


def _zeilen(engine):
    with engine.connect() as v:
        return sorted(tuple(z) for z in v.execute(sa.text("SELECT gruppe, modul FROM rechte_modul")))


def _lauf(engine, schritt):
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    with engine.begin() as v:
        with Operations.context(MigrationContext.configure(v)):
            schritt()


def test_migration_bestand_bekommt_chat_genau_einmal(bestand):
    modul = _migration()
    _lauf(bestand, modul.upgrade)
    erwartet = [("Alt", "chat"), ("Chor", "chat"), ("Chor", "kalender"),
                ("Jugend", "chat"), ("Jugend", "wiki")]
    assert _zeilen(bestand) == erwartet
    _lauf(bestand, modul.upgrade)  # idempotent
    assert _zeilen(bestand) == erwartet
    _lauf(bestand, modul.downgrade)  # nimmt nichts weg
    assert _zeilen(bestand) == erwartet


def test_migration_ohne_tabellen_tut_nichts():
    modul = _migration()
    engine = sa.create_engine("sqlite://")
    _lauf(engine, modul.upgrade)
    assert not sa.inspect(engine).has_table("rechte_modul")


def test_migration_haengt_hinter_backoff_und_ist_einziger_kopf():
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "alembic"))
    skripte = ScriptDirectory.from_config(cfg)
    rev = skripte.get_revision("r_chat_standard")
    assert rev.down_revision == "chat12a2_backoff"
    # CHAT-12c hängt DAHINTER (chat12c_anhang_groesse) — der Kopf ist damit
    # nicht mehr diese Revision, sondern genau EINER: der Anhanggröße.
    assert skripte.get_heads() == ["chat12c_anhang_groesse"]
