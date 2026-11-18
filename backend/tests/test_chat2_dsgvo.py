"""CHAT-2 (S1): Migration, Alembic-Kette und DSGVO-Anonymisierung des Chats.

Drei Zusagen, je gegen die ECHTE Mechanik geprüft (nicht gegen eine Attrappe):

1. **Kette**: ``chat2_chat_s1`` hängt hinter ``tg1_element_gruppe_kalender`` und
   die Kette hat weiterhin GENAU EINEN Kopf — sonst startet der Betrieb nicht
   (``alembic upgrade head`` im Entrypoint, wie ``test_dsgvo1d_alembic_kette``).

2. **Migration**: ``upgrade`` → die vier Tabellen sind da (mit Index
   ``(gespraech, erstellt_am)`` und den beiden zusammengesetzten
   Primärschlüsseln), ``downgrade`` nimmt sie wieder weg, ein zweiter
   ``upgrade`` läuft durch (idempotent). Der Lauf gegen den
   **Betriebs-Dump** steht NICHT hier, sondern im Übergabetext der Karte —
   auf SQLite lässt sich das Frappe-Schema nicht migrieren
   („No support for ALTER of constraints in SQLite dialect“, belegt).

3. **DSGVO** (Konzept 4.3): der Chat-Verlauf bleibt lesbar, die Person
   verschwindet — ``chat_nachricht.autor`` wird auf die neutrale Kennung
   umgehängt, Teilnahme und Reaktionen fallen ganz, der Text bleibt.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory

from diakronos_app import db as dbmod
from diakronos_app.models.chat import ChatGespraech, ChatNachricht, ChatReaktion, ChatTeilnehmer
from diakronos_app.models.core import User
from diakronos_app.models.diakonos import Mitglied

BACKEND = Path(__file__).resolve().parents[1]


# ── Alembic-Kette ───────────────────────────────────────────────────────────


def _skripte() -> ScriptDirectory:
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "alembic"))
    return ScriptDirectory.from_config(cfg)


def test_genau_ein_head_und_chat2_haengt_dahinter():
    """EIN Kopf, und ``chat2_chat_s1`` sitzt in der Kette dahinter.

    CHAT-6 hat ``chat6_meldung`` als neuen Kopf angehaengt (der Test dieser
    Karte prueft die Kante ``chat6_meldung -> chat2_chat_s1``); hier bleibt
    die Zusage dieser Karte: genau EIN Kopf und die Kante
    ``chat2_chat_s1 -> tg1_element_gruppe_kalender``.
    """
    skripte = _skripte()
    heads = skripte.get_heads()
    assert len(heads) == 1, f"Kopf(e): {heads}"
    revision = skripte.get_revision("chat2_chat_s1")
    assert revision is not None
    assert revision.down_revision == "tg1_element_gruppe_kalender", revision.down_revision
    assert "Revises: tg1_element_gruppe_kalender" in Path(revision.path).read_text(encoding="utf-8")


# ── Migration (upgrade/downgrade/idempotent) ────────────────────────────────


@pytest.fixture()
def fresh_engine():
    """Leere SQLite-Engine NUR mit dem Rechte-/User-Gerüst für die FKs."""
    from sqlalchemy import create_engine
    from sqlalchemy.pool import StaticPool

    from diakronos_app.models.base import Base

    eng = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(eng)
    # Die Migration prüft den Bestand; ein leerer Katalog ist der sauberste
    # Start. Die vier Chat-Tabellen nimmt sie vorher heraus, damit `upgrade`
    # sie WIRKLICH anlegt (und nicht nur „schon da“ meldet).
    with eng.begin() as verbindung:
        for name in ("chat_reaktion", "chat_nachricht", "chat_teilnehmer", "chat_gespraech"):
            verbindung.exec_driver_sql(f'DROP TABLE IF EXISTS "{name}"')
    yield eng
    eng.dispose()


def test_migration_legt_die_vier_tabellen_an_und_nimmt_sie_zurueck(fresh_engine):
    import importlib.util

    from sqlalchemy import inspect

    # `alembic/versions` ist KEIN Paket (keine __init__): das Modul wird über
    # seinen Pfad geladen — derselbe Weg, den Alembic selbst geht.
    pfad = BACKEND / "alembic" / "versions" / "chat2_chat_s1.py"
    spec = importlib.util.spec_from_file_location("chat2_chat_s1", pfad)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)

    with fresh_engine.begin() as verbindung:
        from alembic.migration import MigrationContext
        from alembic.operations import Operations

        ctx = MigrationContext.configure(verbindung)
        with Operations.context(ctx):
            modul.upgrade()
        insp = inspect(verbindung)
        for tabelle in ("chat_gespraech", "chat_teilnehmer", "chat_nachricht", "chat_reaktion"):
            assert insp.has_table(tabelle), tabelle
        # Index (gespraech, erstellt_am) — der eine Index für beide Richtungen.
        spalten = [i["column_names"] for i in insp.get_indexes("chat_nachricht")]
        assert ["gespraech", "erstellt_am"] in spalten
        # Zusammengesetzte Primärschlüssel (die Zusage „einmalig“).
        assert insp.get_pk_constraint("chat_teilnehmer")["constrained_columns"] == \
            ["gespraech", "benutzer"]
        assert insp.get_pk_constraint("chat_reaktion")["constrained_columns"] == \
            ["nachricht", "benutzer"]
        # EIN Gespräch je Einheit — in der Datenbank, nicht nur im Code. Zwei
        # PARTIELLE Unique-Indizes (Review Punkt 2): ein Constraint über
        # (art, gruppe, untergruppe) griffe bei `untergruppe IS NULL` nicht.
        anzahlen = {}
        for i in insp.get_indexes("chat_gespraech"):
            if i.get("unique"):
                anzahlen[tuple(i["column_names"])] = dict(i.get("dialect_options") or {})
        assert ("art", "gruppe") in anzahlen
        assert ("art", "gruppe", "untergruppe") in anzahlen

    # Zweiter Lauf: idempotent (nichts doppelt, kein Fehler). Eigener Kontext —
    # `Operations.context` gilt nur INNERHALB des `with`.
    with fresh_engine.begin() as verbindung:
        from alembic.migration import MigrationContext
        from alembic.operations import Operations

        with Operations.context(MigrationContext.configure(verbindung)):
            modul.upgrade()
            modul.downgrade()
        insp = inspect(verbindung)
        for tabelle in ("chat_gespraech", "chat_teilnehmer", "chat_nachricht", "chat_reaktion"):
            assert not insp.has_table(tabelle), tabelle


def test_migration_ist_gegen_das_betriebsschema_nicht_auf_sqlite_pruefbar():
    """Warum der Betriebs-Dump-Lauf NICHT hier steht (ehrlich, nicht still).

    Das Frappe-Schema enthält echte FK-Zyklen; schon die Baseline
    (``p1bmodelle``) scheitert auf SQLite an ``ALTER TABLE … ADD CONSTRAINT``.
    Der Dump-Lauf braucht deshalb einen Wegwerf-PostgreSQL und wird im
    Übergabetext berichtet. Dieser Test hält die Grenze fest, damit niemand
    den SQLite-Lauf für den Dump-Nachweis hält.
    """
    quelle = (BACKEND / "alembic" / "versions" / "p1bmodelle_schema_aus_73_doctypes.py").read_text(
        encoding="utf-8")
    assert "create_foreign_key" in quelle  # ALTER-basiert → auf SQLite nicht möglich


# ── DSGVO ───────────────────────────────────────────────────────────────────


@pytest.fixture()
def welt(patched_db):
    s = patched_db()
    for konto, kurz in [("anna@x.org", "Anna"), ("bert@x.org", "Bert")]:
        s.add(User(name=konto, email=konto, enabled=1, full_name=f"{kurz} Beispiel"))
        s.add(Mitglied(name=f"M-{kurz}", vorname=kurz, nachname="Beispiel", email=konto,
                       user=konto))
    s.commit()
    yield s
    s.close()


def test_anonymisierung_haengt_den_autor_um_und_laesst_den_verlauf(welt):
    """Nach Art. 17: Autor → neutrale Kennung, Text bleibt, Teilnahme/Reaktion weg."""
    from diakronos_app import dsgvo_anonymisierung as D

    with dbmod.SessionLocal.begin() as s:
        g = ChatGespraech(name="G-1", art="gruppe", gruppe="Chor", angelegt_von="anna@x.org",
                          angelegt_am=dt.datetime(2026, 11, 18, 9, 0))
        s.add(g)
        s.add(ChatTeilnehmer(gespraech="G-1", benutzer="anna@x.org", stumm=False))
        s.add(ChatTeilnehmer(gespraech="G-1", benutzer="bert@x.org", stumm=False))
        s.add(ChatNachricht(name="N-1", gespraech="G-1", autor="M-Anna",
                            autor_benutzer="anna@x.org",
                            text="Ich bringe Kuchen mit, sagt Anna Beispiel.",
                            erstellt_am=dt.datetime(2026, 11, 18, 9, 1)))
        s.add(ChatNachricht(name="N-2", gespraech="G-1", autor="M-Bert",
                            autor_benutzer="bert@x.org",
                            text="Super, bis Samstag!",
                            erstellt_am=dt.datetime(2026, 11, 18, 9, 2)))
        s.add(ChatReaktion(nachricht="N-2", benutzer="anna@x.org", reaktion="👍"))

    with dbmod.SessionLocal.begin() as s:
        ergebnis = D.anonymisiere(s, "M-Anna", ["anna@x.org"])
        kennung = ergebnis["kennung"]
        s.flush()

        eigene = s.get(ChatNachricht, "N-1")
        assert eigene.autor == kennung            # Verlauf bleibt, Bezug neutral
        assert eigene.autor_benutzer is None      # Besitz (Konto) ist weg
        assert "Kuchen" in (eigene.text or "")    # Fachdatum bleibt stehen
        assert "Anna Beispiel" not in (eigene.text or "")  # voller Name ersetzt
        fremd = s.get(ChatNachricht, "N-2")
        assert fremd.autor == "M-Bert"            # fremde Zeile unberuehrt
        assert s.get(ChatTeilnehmer, ("G-1", "anna@x.org")) is None   # Zeile gefallen
        assert s.get(ChatTeilnehmer, ("G-1", "bert@x.org")) is not None
        assert s.query(ChatReaktion).filter_by(benutzer="anna@x.org").count() == 0
        assert s.get(ChatGespraech, "G-1") is not None

    # Kein Verweis auf das geloeschte Konto bleibt in den Chat-Tabellen.
    with dbmod.SessionLocal.begin() as s:
        assert s.query(ChatNachricht).filter(ChatNachricht.autor_benutzer == "anna@x.org").count() == 0
        assert s.query(ChatTeilnehmer).filter(ChatTeilnehmer.benutzer == "anna@x.org").count() == 0
        assert s.query(ChatGespraech).filter(ChatGespraech.angelegt_von == "anna@x.org").count() == 0


def test_inventar_deckt_die_chat_tabellen():
    """Freitexte und Bezüge der neuen Tabellen haben eine DSGVO-Entscheidung."""
    from diakronos_app import dsgvo_anonymisierung as D

    for tabelle, spalten in {
        "chat_gespraech": {"angelegt_von", "titel"},
        "chat_teilnehmer": {"benutzer"},
        "chat_nachricht": {"autor", "autor_benutzer", "text", "entfernt_grund",
                           "geloescht_von"},
        "chat_reaktion": {"benutzer"},
        # CHAT-6: die Meldung selbst ist personenbezogen (wer meldet), der
        # Freitext ebenso; der Grund ist ein festes Set und keine Person.
        "chat_meldung": {"melder", "bearbeitet_von", "freitext",
                         "entscheidung_grund"},
    }.items():
        assert spalten <= set(D.SPALTEN.get(tabelle, {})), (tabelle, D.SPALTEN.get(tabelle))

    # Zwei Verfasserspalten mit ZWEI Entscheidungen (Review Punkt 4): der
    # Besitz (Konto) wird genullt, die Anzeige (Mitglied) umgehängt.
    assert D.SPALTEN["chat_nachricht"]["autor_benutzer"][0] == "user_null"
    assert D.SPALTEN["chat_nachricht"]["autor"][0] == "mitglied"

    loeschzeilen = {name for name, _ in D.ZEILEN_LOESCHEN}
    assert {"chat_teilnehmer", "chat_reaktion"} <= loeschzeilen
    assert "chat_nachricht" not in loeschzeilen  # der Verlauf bleibt
    assert "chat_nachricht.autor"  # (nur zur Lesbarkeit: Pflichtfeld steht oben)
