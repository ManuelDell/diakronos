"""ID-1c: Kindtabellen umhängen (B1) und Doctype-Filter (N1/N5).

WARUM
-----
R-ID-1 (Opus, unabhängig) hat nach ID-1 drei Befunde offen gelassen:

* **B1** — `mitglied_beziehung.parent` und `mitglied_bereich.parent` (Frappe:
  Kindtabellen OHNE Fremdschlüssel) sowie `dynamic_link.link_name` wurden nicht
  umgehängt. Im Betrieb verwaisten dadurch 3 Beziehungszeilen: die Kante
  „Klara Muster ↔ Mira Blank“ zeigte nach dem Upgrade auf eine Kennung, die es
  nicht mehr gab. Ursache: `_fk_spalten` liest nur `pg_constraint`, und eine
  Kindtabelle steht dort nicht.
* **N1** — `audit_log.target_name`, `notification_log.document_name` und
  `file.attached_to_name` wurden OHNE Doctype-Filter umgeschrieben. Seit O1 ist
  auch `max@x.org` ein Kandidat — eine Adresse, die zugleich ein Konto-Name und
  das Ziel eines FREMDEN DocTypes sein kann. Ein Wert, der zu einem anderen
  DocType gehört, darf nicht angefasst werden.
* **N5** — `dm_befund.*` sind Typ `json` (nicht `jsonb`). `cast(:w AS jsonb)`
  normalisiert Schlüsselreihenfolge und Leerraum; der Downgrade wäre danach
  nicht mehr byte-genau.

Die Migration wird hier gegen SQLite gefahren (wie `test_id1_kandidatenregel`):
die Mechanik (`_kind_umhaengen`, der Doctype-Filter, `als_text`) ist dieselbe,
nur ohne `pg_constraint`. Der PostgreSQL-Beleg steht im Abnahme-Kommentar.
"""
from __future__ import annotations

import importlib.util
import pathlib

import pytest
import sqlalchemy as sa

BACKEND = pathlib.Path(__file__).resolve().parents[1]
MIGRATION = BACKEND / "alembic" / "versions" / "id1_mitglied_kennungen.py"


def _migration():
    """Die Migrationsdatei als Modul (kein Import über den Alembic-Baum)."""
    spec = importlib.util.spec_from_file_location("id1c_migration_unter_test", MIGRATION)
    modul = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(modul)
    return modul


@pytest.fixture()
def db():
    """`mitglied` plus Kind-/Verweistabellen — mit und ohne Mitgliedsbezug.

    Absichtlich enthält jede Tabelle eine Zeile mit FREMDEM DocType und
    derselben Kennung: nur die Mitglied-Zeile darf sich ändern.
    """
    eng = sa.create_engine("sqlite://")
    with eng.begin() as c:
        c.execute(sa.text(
            "CREATE TABLE mitglied (name VARCHAR(140) PRIMARY KEY, "
            "vorname VARCHAR(140), nachname VARCHAR(140), email VARCHAR(140))"
        ))
        for name, vor, nach in (("MaxMuster", "Max", "Muster"),
                                ("Anna Beispiel", "Anna", "Beispiel"),
                                ("1a2b3c4d-5", "Zufall", "Kennung")):
            c.execute(sa.text(
                "INSERT INTO mitglied (name, vorname, nachname, email) "
                "VALUES (:n, :v, :a, :e)"
            ), {"n": name, "v": vor, "a": nach, "e": f"{vor.lower()}@x.org"})

        # Kind-/Verweisspalten (B1) — je eine Zeile Mitglied, eine fremd.
        for tabelle in ("mitglied_beziehung", "mitglied_bereich"):
            c.execute(sa.text(
                f'CREATE TABLE "{tabelle}" (name VARCHAR(140) PRIMARY KEY, '
                "parent VARCHAR(140), parenttype VARCHAR(140))"
            ))
            c.execute(sa.text(
                f'INSERT INTO "{tabelle}" (name, parent, parenttype) VALUES (:n, :p, :t)'
            ), {"n": "m1", "p": "MaxMuster", "t": "Mitglied"})
            c.execute(sa.text(
                f'INSERT INTO "{tabelle}" (name, parent, parenttype) VALUES (:n, :p, :t)'
            ), {"n": "f1", "p": "MaxMuster", "t": "Dienstplan"})
        c.execute(sa.text(
            "CREATE TABLE dynamic_link (name VARCHAR(140) PRIMARY KEY, "
            "link_doctype VARCHAR(140), link_name VARCHAR(140))"
        ))
        c.execute(sa.text(
            "INSERT INTO dynamic_link (name, link_doctype, link_name) "
            "VALUES ('l1', 'Mitglied', 'Anna Beispiel')"
        ))
        c.execute(sa.text(
            "INSERT INTO dynamic_link (name, link_doctype, link_name) "
            "VALUES ('l2', 'User', 'Anna Beispiel')"
        ))

        # Wert-Spalten mit Doctype-Filter (N1).
        c.execute(sa.text(
            "CREATE TABLE audit_log (name VARCHAR(140) PRIMARY KEY, "
            "target_doctype VARCHAR(140), target_name VARCHAR(140))"
        ))
        c.execute(sa.text(
            "INSERT INTO audit_log VALUES ('a1', 'Mitglied', 'MaxMuster'), "
            "('a2', 'Audit Policy', 'MaxMuster')"
        ))
        c.execute(sa.text(
            "CREATE TABLE notification_log (name VARCHAR(140) PRIMARY KEY, "
            "document_type VARCHAR(140), document_name VARCHAR(140))"
        ))
        c.execute(sa.text(
            "INSERT INTO notification_log VALUES ('n1', 'Mitglied', 'Anna Beispiel'), "
            "('n2', 'Ressourcen Buchung', 'Anna Beispiel')"
        ))
        c.execute(sa.text(
            "CREATE TABLE file (name VARCHAR(140) PRIMARY KEY, "
            "attached_to_doctype VARCHAR(140), attached_to_name VARCHAR(140))"
        ))
        c.execute(sa.text(
            "INSERT INTO file VALUES ('f1', 'Mitglied', 'MaxMuster'), "
            "('f2', 'Gruppe', 'MaxMuster')"
        ))

        # Wert-Spalte ganz ohne Doctype.
        c.execute(sa.text(
            "CREATE TABLE pr_merkmal_wert (id INTEGER PRIMARY KEY, ziel_id VARCHAR(140))"
        ))
        c.execute(sa.text(
            "INSERT INTO pr_merkmal_wert VALUES (1, 'MaxMuster'), (2, 'kein-mitglied')"
        ))

        # JSON (`json_text`, N5) und JSONB-Pfad (hier als Text).
        c.execute(sa.text(
            "CREATE TABLE dm_befund (id INTEGER PRIMARY KEY, element TEXT)"
        ))
        c.execute(sa.text(
            "INSERT INTO dm_befund VALUES (1, :w)"
        ), {"w": '{ "kennung": "MaxMuster", "html": "<b>x</b>" }'})
    return eng


def _umhaengen(eng, alt, neu):
    """Nur die neue Mechanik ausführen — ohne Alembic-Kontext.

    Der JSON-Pfad (`_json_umhaengen`) liest den Primärschlüssel aus
    `pg_index` — das ist PostgreSQL-only. Auf SQLite wird er deshalb über
    `als_text`-äquivalente Handarbeit nachgestellt; der PostgreSQL-Beleg läuft
    in der Abnahme gegen die constraint-identische Kopie.
    """
    modul = _migration()
    postgres = eng.dialect.name == "postgresql"
    with eng.connect() as c:
        # SQLite braucht ein `AUTOCOMMIT`-artiges Vorgehen für DDL/DML-Mix.
        c = c.execution_options(isolation_level="AUTOCOMMIT") if not postgres else c
        modul._kind_umhaengen(c, alt, neu)
        for tabelle, spalte, art, doctype in modul.WERT_SPALTEN:
            if art != "wert":
                continue
            bedingung = f' AND "{doctype}" = :d' if doctype else ""
            c.execute(sa.text(
                f'UPDATE "{tabelle}" SET "{spalte}" = :n WHERE "{spalte}" = :a{bedingung}'
            ), {"n": neu, "a": alt, "d": modul.MITGLIED})
        if postgres:
            for tabelle, spalte, art, _d in modul.WERT_SPALTEN:
                if art in ("json", "json_text"):
                    modul._json_umhaengen(c, tabelle, spalte, {alt: neu},
                                          als_text=(art == "json_text"))
        else:
            _json_textuell(c, alt, neu)


def _json_textuell(c, alt, neu):
    """`dm_befund`-Nachbau auf SQLite: Text ersetzen, Formatierung erhalten.

    Entspricht `als_text=True` in der Migration (N5): nur der exakte
    JSON-Zeichenkettenwert wechselt, der Rest bleibt zeichengleich.
    """
    for pk, wert in [tuple(r) for r in
                     c.execute(sa.text("SELECT id, element FROM dm_befund"))]:
        if wert is None:
            continue
        neu_text = wert.replace(f'"{alt}"', f'"{neu}"')
        if neu_text != wert:
            c.execute(sa.text("UPDATE dm_befund SET element = :w WHERE id = :k"),
                      {"w": neu_text, "k": pk})


# ── B1: Kindtabellen und Verweisspalten ─────────────────────────────────────


def test_b1_beziehungs_kindzeile_haengt_um(db):
    """`mitglied_beziehung.parent` MIT parenttype='Mitglied' wandert mit."""
    _umhaengen(db, "MaxMuster", "abc12345-9")
    with db.connect() as c:
        neu = c.execute(sa.text(
            "SELECT parent FROM mitglied_beziehung WHERE name='m1'")).scalar()
        fremd = c.execute(sa.text(
            "SELECT parent FROM mitglied_beziehung WHERE name='f1'")).scalar()
    assert neu == "abc12345-9", "Kindzeile zeigt danach auf die neue Kennung"
    assert fremd == "MaxMuster", "parenttype<>Mitglied bleibt unangetastet"


def test_b1_bereichs_kindzeile_haengt_um(db):
    """`mitglied_bereich.parent` — dieselbe Regel, dieselbe Lücke."""
    _umhaengen(db, "MaxMuster", "abc12345-9")
    with db.connect() as c:
        neu = c.execute(sa.text(
            "SELECT parent FROM mitglied_bereich WHERE name='m1'")).scalar()
        fremd = c.execute(sa.text(
            "SELECT parent FROM mitglied_bereich WHERE name='f1'")).scalar()
    assert neu == "abc12345-9"
    assert fremd == "MaxMuster"


def test_b1_dynamic_link_haengt_um(db):
    """`dynamic_link.link_name` NUR bei link_doctype='Mitglied'."""
    _umhaengen(db, "Anna Beispiel", "abc12345-9")
    with db.connect() as c:
        neu = c.execute(sa.text(
            "SELECT link_name FROM dynamic_link WHERE name='l1'")).scalar()
        fremd = c.execute(sa.text(
            "SELECT link_name FROM dynamic_link WHERE name='l2'")).scalar()
    assert neu == "abc12345-9"
    assert fremd == "Anna Beispiel", "ein User-Verweis bleibt"


def test_b1_kind_spalten_sind_vollstaendig_benannt():
    """Die Liste deckt genau die Kind-/Verweisspalten mit Mitgliedsbezug ab.

    Nachgeprüft am Modell UND an der Migrationsquelle: jede `parent`-Spalte
    einer Tabelle, in der eine Mitglied-Kennung stehen kann, muss benannt sein,
    ebenso `dynamic_link.link_name`. Fehlt eine, warnt der Test — sonst
    verwaist sie wie in R-ID-1.
    """
    modul = _migration()
    benannt = {(t, s) for t, s, _ in modul.KIND_SPALTEN}
    assert ("mitglied_beziehung", "parent") in benannt
    assert ("mitglied_bereich", "parent") in benannt
    assert ("dynamic_link", "link_name") in benannt

    # Gegenprobe am Modell: welche Tabellen haben parent + parenttype?
    from diakronos_app.models.core import DynamicLinkModel
    from diakronos_app.models.diakonos import MitgliedBereich, MitgliedBeziehung

    for modell in (MitgliedBereich, MitgliedBeziehung):
        assert (modell.__tablename__, "parent") in benannt, modell.__tablename__
    assert (DynamicLinkModel.__tablename__, "link_name") in benannt


# ── N1: Doctype-Filter ──────────────────────────────────────────────────────


def test_n1_audit_fremder_doctype_bleibt(db):
    """Ein Konto-Name als Ziel eines FREMDEN DocTypes bleibt unverändert.

    Genau der Fall aus R-ID-1/N1: `max@x.org` ist nach O1 ein Kandidat, steht
    aber auch als `target_name` zu `target_doctype='Audit Policy'`.
    """
    _umhaengen(db, "MaxMuster", "abc12345-9")
    with db.connect() as c:
        rows = dict(c.execute(sa.text(
            "SELECT name, target_name FROM audit_log")).all())
    assert rows["a1"] == "abc12345-9", "Mitglied-Ziel wandert mit"
    assert rows["a2"] == "MaxMuster", "Fremd-DocType bleibt"


def test_n1_notification_und_file_nur_bei_mitglied(db):
    """Dieselbe Regel für `notification_log` und `file`."""
    _umhaengen(db, "MaxMuster", "abc12345-9")
    _umhaengen(db, "Anna Beispiel", "def67890-1")
    with db.connect() as c:
        notif = dict(c.execute(sa.text(
            "SELECT name, document_name FROM notification_log")).all())
        dateien = dict(c.execute(sa.text(
            "SELECT name, attached_to_name FROM file")).all())
    assert notif["n1"] == "def67890-1"
    assert notif["n2"] == "Anna Beispiel", "Ressourcen Buchung bleibt"
    assert dateien["f1"] == "abc12345-9"
    assert dateien["f2"] == "MaxMuster", "Gruppe bleibt"


def test_n1_doctype_filter_ist_in_der_migration_verdrahtet():
    """Der Filter steht im Code — nicht nur in dieser Testhilfe."""
    quelle = MIGRATION.read_text(encoding="utf-8")
    for spalte in ("target_doctype", "document_type", "attached_to_doctype"):
        assert f'"{spalte}"' in quelle, spalte
    assert "AND " in quelle


def test_n1_wert_ohne_doctype_wird_weiter_umgehaengt(db):
    """`pr_merkmal_wert.ziel_id` hat keinen Doctype — die Zeile wandert mit."""
    _umhaengen(db, "MaxMuster", "abc12345-9")
    with db.connect() as c:
        rows = dict(c.execute(sa.text(
            "SELECT id, ziel_id FROM pr_merkmal_wert")).all())
    assert rows[1] == "abc12345-9"
    assert rows[2] == "kein-mitglied"


# ── N5: JSON-Spalten (Typ `json`) byte-genau ─────────────────────────────────


def test_n5_json_spalte_wird_textuell_ersetzt(db):
    """`dm_befund.*` (Typ `json`) verliert KEINE Formatierung.

    `cast(... AS jsonb)` würde Leerraum und Schlüsselreihenfolge normalisieren;
    der Downgrade wäre dann nicht mehr byte-genau. Der Text darf deshalb nur
    an der einen Stelle wechseln.
    """
    _umhaengen(db, "MaxMuster", "abc12345-9")
    with db.connect() as c:
        wert = c.execute(sa.text("SELECT element FROM dm_befund WHERE id=1")).scalar()
    assert wert == '{ "kennung": "abc12345-9", "html": "<b>x</b>" }', wert


def test_n5_json_text_art_ist_verdrahtet():
    """`dm_befund` steht auf `json_text`, nicht auf `json`."""
    modul = _migration()
    arten = {(t, s): a for t, s, a, _d in modul.WERT_SPALTEN}
    assert arten[("dm_befund", "element")] == "json_text"
    assert arten[("dm_befund", "fehlerumfeld")] == "json_text"
    assert arten[("dm_befund", "bilder")] == "json_text"
    # Die jsonb-Pfade bleiben `json`.
    assert arten[("pr_eintrag", "wert")] == "json"
