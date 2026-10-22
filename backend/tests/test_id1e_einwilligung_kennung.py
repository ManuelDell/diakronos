"""ID-1e (N3): der Einwilligungs-Schlüssel trägt keinen Klarnamen mehr.

WARUM
-----
R-ID-1/N3: `dsgvo_einwilligung.name` hatte im Betrieb das Muster
``DSGVO-<Klarname>-000n`` und ``EINW-<Klarname>-000n`` (9 echte Zeilen, am
Dump geprüft). Die Migration ID-1 schlüsselte nur ``mitglied.name`` um — die
Nachweiszeilen (Art. 7) blieben mit dem Namen im SCHLÜSSEL stehen. Damit stand
der Klarname weiter in einer Tabelle, die eine Löschung ausdrücklich überlebt.

WAS HIER GEPRÜFT WIRD
---------------------
Die Migration benennt solche Zeilen in einem eigenen Schritt um
(``EINWILLIGUNG_SPALTEN``): der Namensanteil wird die Kennung der Person,
``DSGVO-Anna Beispiel-0002`` -> ``DSGVO-def67890-1-0002``.

* nur eigene Zeilen (``typ``-Muster + Namensanteil gleich einer Kennung, die
  umgeschlüsselt wurde) — eine Zeile zu einem FREMDEN DocType bleibt,
* eine Zeile ohne erkennbare Person (``EINW-Fremd-0001``) bleibt,
* der Schlüssel bleibt eindeutig (Kollision bekommt einen Zusatz),
* der Rückweg stellt den alten Schlüssel zeichengleich her.
"""
from __future__ import annotations

import importlib.util
import pathlib

import pytest
import sqlalchemy as sa

BACKEND = pathlib.Path(__file__).resolve().parents[1]
MIGRATION = BACKEND / "alembic" / "versions" / "id1_mitglied_kennungen.py"

#: Alte Kennung (Klarname) -> neue Kennung, wie in der Migration erzeugt.
ABBILDUNG = {"Max Muster": "abc12345-9", "Anna Beispiel": "def67890-1"}


def _migration():
    spec = importlib.util.spec_from_file_location("id1e_migration_unter_test", MIGRATION)
    modul = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(modul)
    return modul


@pytest.fixture()
def db():
    """`mitglied` + `dsgvo_einwilligung` mit echten Betriebszeilen."""
    eng = sa.create_engine("sqlite://")
    with eng.begin() as c:
        c.execute(sa.text(
            "CREATE TABLE mitglied (name VARCHAR(140) PRIMARY KEY, "
            "vorname VARCHAR(140), nachname VARCHAR(140), email VARCHAR(140))"
        ))
        for name, vor, nach in (("Max Muster", "Max", "Muster"),
                                ("Anna Beispiel", "Anna", "Beispiel"),
                                ("1a2b3c4d-5", "Zufall", "Kennung")):
            c.execute(sa.text(
                "INSERT INTO mitglied (name, vorname, nachname, email) "
                "VALUES (:n, :v, :a, :e)"
            ), {"n": name, "v": vor, "a": nach, "e": f"{vor.lower()}@x.org"})
        c.execute(sa.text(
            "CREATE TABLE dsgvo_einwilligung (name VARCHAR(140) PRIMARY KEY, "
            "mitglied VARCHAR(140), typ VARCHAR(140), aktion VARCHAR(140))"
        ))
        # Der Mitglieder-Schritt schreibt AUCH in die Kind-/Verweisspalten
        # (ID-1c); hier leer, aber vorhanden.
        for tabelle in ("mitglied_beziehung", "mitglied_bereich"):
            c.execute(sa.text(
                f'CREATE TABLE "{tabelle}" (name VARCHAR(140) PRIMARY KEY, '
                "parent VARCHAR(140), parenttype VARCHAR(140))"
            ))
        c.execute(sa.text(
            "CREATE TABLE dynamic_link (name VARCHAR(140) PRIMARY KEY, "
            "link_doctype VARCHAR(140), link_name VARCHAR(140))"
        ))
        # Wert- und JSON-Spalten des Mitglieder-Schritts (WERT_SPALTEN) —
        # leer, aber vorhanden, damit der Schritt vollständig läuft.
        c.execute(sa.text(
            "CREATE TABLE pr_merkmal_wert (id INTEGER PRIMARY KEY, ziel_id VARCHAR(140))"
        ))
        for tabelle, spalten in (
            ("audit_log", "target_doctype VARCHAR(140), target_name VARCHAR(140)"),
            ("notification_log", "document_type VARCHAR(140), document_name VARCHAR(140)"),
            ("file", "attached_to_doctype VARCHAR(140), attached_to_name VARCHAR(140)"),
            ("pr_eintrag", "wert TEXT"),
            ("pr_verlauf", "vorher TEXT, nachher TEXT"),
            ("pr_plan", "veroeffentlichter_stand TEXT"),
            ("pr_sammlung_eintrag", "daten TEXT"),
            ("dm_befund", "fehlerumfeld TEXT, element TEXT, bilder TEXT"),
        ):
            c.execute(sa.text(
                f'CREATE TABLE "{tabelle}" (id INTEGER PRIMARY KEY, {spalten})'
            ))
        zeilen = (
            # Eigene Zeilen MIT Namen — der Befund.
            ("DSGVO-Max Muster-0002", "Max Muster", "foto", "erteilt"),
            ("EINW-Max Muster-0029", "Max Muster", "werbung", "erteilt"),
            # Eigene Zeile einer ZWEITEN Person (Kollisionsprobe, s. u.).
            ("DSGVO-Anna Beispiel-0004", "Anna Beispiel", "foto", "erteilt"),
            # Zeile ohne Mitglied-Kennung in der Person (Altbestand).
            ("EINW-Fremd-0001", "fremd", "datenschutz", "erteilt"),
            # Zeile zu einer Person, die NICHT umgeschlüsselt wurde.
            ("DSGVO-1a2b3c4d-5-0007", "1a2b3c4d-5", "foto", "erteilt"),
        )
        for name, mitglied, typ, aktion in zeilen:
            c.execute(sa.text(
                "INSERT INTO dsgvo_einwilligung (name, mitglied, typ, aktion) "
                "VALUES (:n, :m, :t, :a)"
            ), {"n": name, "m": mitglied, "t": typ, "a": aktion})
    return eng


def _umbenennen(eng, richtung: str, mitglieder: bool = False):
    """Den Migrationsschritt ausführen, ohne Alembic-Kontext.

    ``richtung`` ist ``"hin"`` (upgrade) oder ``"zurueck"`` (downgrade) — so
    wird derselbe Code geprüft, den die Migration aufruft. ``mitglieder=True``
    hängt den Hinweg an die Mitglieder-Umschlüsselung (wie in `upgrade`): erst
    danach zeigt `dsgvo_einwilligung.mitglied` auf die neue Kennung.
    """
    modul = _migration()
    with eng.begin() as c:
        if richtung == "hin":
            if mitglieder:
                modul._mitglieder_umhaengen(
                    c, ABBILDUNG, spalten=["name", "vorname", "nachname", "email"],
                    fks=[("dsgvo_einwilligung", "mitglied", True, "a")],
                    json_pfade=False,
                )
            modul._einwilligungen_umbenennen(c, ABBILDUNG)
        else:
            modul._einwilligungen_umbenennen(
                c, {neu: alt for alt, neu in ABBILDUNG.items()}, zurueck=True,
            )


def _namen(eng) -> dict[str, str]:
    with eng.connect() as c:
        return dict(c.execute(sa.text(
            "SELECT name, mitglied FROM dsgvo_einwilligung")).all())


# ── Hinweg ──────────────────────────────────────────────────────────────────

def test_eigene_zeile_traegt_die_kennung_statt_des_namens(db):
    """Der Kern von N3: `DSGVO-<Klarname>-0002` -> `DSGVO-<Kennung>-0002`."""
    # Der Hinweg in der Reihenfolge der Migration: erst die Mitglieder
    # umschlüsseln, dann die Nachweiszeilen (die Verweise zeigen danach auf
    # die neuen Kennungen, hier ohne PostgreSQL-Fremdschlüssel).
    _umbenennen(db, "hin", mitglieder=True)
    zeilen = _namen(db)
    assert "DSGVO-abc12345-9-0002" in zeilen, sorted(zeilen)
    assert "DSGVO-Max Muster-0002" not in zeilen
    # Das Muster bleibt: nur der Namensanteil wechselt, die Nummer nicht.
    assert zeilen["DSGVO-abc12345-9-0002"] == "abc12345-9"


def test_zweite_person_wird_ebenfalls_umbenannt(db):
    """Jede betroffene Zeile, nicht nur die erste — inkl. Präfix `EINW-`."""
    _umbenennen(db, "hin")
    zeilen = _namen(db)
    assert "EINW-abc12345-9-0029" in zeilen, sorted(zeilen)
    assert "DSGVO-def67890-1-0004" in zeilen, sorted(zeilen)


def test_fremde_und_bereits_saubere_zeilen_bleiben(db):
    """Gegenprobe: ohne erkennbare Person wird nichts umgeschrieben.

    ``EINW-Fremd-0001`` gehört zu keinem Mitglied, dessen Kennung sich
    ändert, ``DSGVO-1a2b3c4d-5-0007`` trägt bereits eine Zufallskennung.
    """
    _umbenennen(db, "hin")
    zeilen = _namen(db)
    assert "EINW-Fremd-0001" in zeilen, sorted(zeilen)
    assert "DSGVO-1a2b3c4d-5-0007" in zeilen, sorted(zeilen)


def test_schluessel_bleibt_eindeutig(db):
    """Steht der Zielschlüssel schon, bekommt die Zeile einen Zusatz."""
    with db.begin() as c:
        c.execute(sa.text(
            "INSERT INTO dsgvo_einwilligung (name, mitglied, typ, aktion) "
            "VALUES ('DSGVO-abc12345-9-0002', 'abc12345-9', 'foto', 'widerrufen')"
        ))
    _umbenennen(db, "hin")
    zeilen = _namen(db)
    assert "DSGVO-abc12345-9-0002-1" in zeilen, sorted(zeilen)
    assert len(zeilen) == 6


def test_zweiter_lauf_aendert_nichts(db):
    """Idempotenz: der Entrypoint migriert bei JEDEM Start."""
    _umbenennen(db, "hin")
    vorher = _namen(db)
    _umbenennen(db, "hin")
    assert _namen(db) == vorher


# ── Rückweg ─────────────────────────────────────────────────────────────────

def test_downgrade_stellt_den_alten_schluessel_wieder_her(db):
    """Der Rückweg ist zeichengleich — die Abbildung liegt vollständig vor."""
    vorher = _namen(db)
    _umbenennen(db, "hin")
    _umbenennen(db, "zurueck")
    assert _namen(db) == vorher


# ── Verdrahtung ─────────────────────────────────────────────────────────────

def test_migration_ruft_den_schritt_im_upgrade_und_downgrade():
    """Der Schritt steht in BEIDEN Richtungen — nicht nur im Hinweg."""
    quelle = MIGRATION.read_text(encoding="utf-8")
    assert "_einwilligungen_umbenennen" in quelle
    # upgrade: nach dem Umschlüsseln der Mitglieder (Abbildung steht),
    # downgrade: VOR dem Zurückdrehen der Mitglieder (Abbildung noch da).
    hinweg = quelle.split("def upgrade()", 1)[1].split("def _kind_umhaengen", 1)[0]
    rueckweg = quelle.split("def downgrade()", 1)[1]
    assert "_einwilligungen_umbenennen" in hinweg
    assert "_einwilligungen_umbenennen" in rueckweg
