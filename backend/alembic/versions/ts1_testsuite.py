"""TS1: Testsuite — Tabellen, Rolle 'Tester' und Rollen-Auswahl.

Revision ID: ts1_testsuite
Revises: pf2_lied_indizes
Create Date: 2026-10-15

Legt an:

1. ``ts_sitzung``   — Testsitzungen (wer testet welches Szenario).
2. ``ts_ereignis``  — Fehler/Logs/Anfragen je Sitzung (Backend-Monitoring).
3. ``ts_kommentar`` — Kommentare mit Bildpfaden.
4. ``ts_szenario``  — Zustand je Szenario/Seite (Fortschritt).
5. ``ts_befund``    — Befundliste je Sitzung (offen/an Claude/behoben/verworfen).

Ausserdem:

* Rolle ``Tester`` in ``role`` (die Tabelle hat NUR die Spalte ``name`` —
  geprueft mit ``\d role`` an der migrierten Datenbank). Die Zuordnung zu einem
  Benutzer passiert wie bei allen Rollen ueber ``has_role`` (Child von
  ``user``, ``parentfield='roles'``). Tester werden danach in der
  Benutzerverwaltung wie jede andere Rolle zugeordnet.
* Bestehende Administratoren bekommen die Rolle NICHT: der Server laesst
  Administratoren ohnehin durch (``zugriff_pruefen``). Eine Zeile weniger in
  ``has_role`` ist besser als eine, die jemand spaeter wieder entfernen muss.

Idempotent: jede Operation prueft zuerst, ob das Objekt schon existiert.
``downgrade`` entfernt die Testsuite-Tabellen und die angelegten
Rollen-Zeilen in umgekehrter Reihenfolge. ``has_role``-Zuordnungen auf
``Tester`` werden vorher entfernt, damit kein Kind ohne Rolle zurueckbleibt.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "ts1_testsuite"
down_revision: Union[str, None] = "pf2_lied_indizes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ROLLE = "Tester"
def _tabelle_existiert(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def upgrade() -> None:
    if not _tabelle_existiert("ts_sitzung"):
        op.create_table(
            "ts_sitzung",
            sa.Column("name", sa.String(length=140), primary_key=True),
            sa.Column("benutzer", sa.String(length=140), nullable=False),
            sa.Column("szenario_id", sa.String(length=200), nullable=True),
            sa.Column("seite", sa.String(length=200), nullable=True),
            sa.Column("route", sa.String(length=300), nullable=True),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="laeuft"),
            sa.Column("ergebnis", sa.String(length=30), nullable=False, server_default="ungetestet"),
            sa.Column("schritte", sa.JSON(), nullable=True),
            sa.Column("eingeplant", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("punkte", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("abzeichen", sa.JSON(), nullable=True),
            sa.Column("begonnen", sa.DateTime(), nullable=True),
            sa.Column("beendet", sa.DateTime(), nullable=True),
            sa.Column("creation", sa.DateTime(), nullable=True),
            sa.Column("modified", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_ts_sitzung_benutzer", "ts_sitzung", ["benutzer"])
        op.create_index("ix_ts_sitzung_status", "ts_sitzung", ["status"])

    if not _tabelle_existiert("ts_ereignis"):
        op.create_table(
            "ts_ereignis",
            sa.Column("name", sa.String(length=140), primary_key=True),
            sa.Column("sitzung", sa.String(length=140), nullable=True),
            sa.Column("art", sa.String(length=30), nullable=False),
            sa.Column("zeitpunkt", sa.DateTime(), nullable=True),
            sa.Column("methode", sa.String(length=12), nullable=True),
            sa.Column("pfad", sa.String(length=500), nullable=True),
            sa.Column("status", sa.Integer(), nullable=True),
            sa.Column("dauer_ms", sa.Integer(), nullable=True),
            sa.Column("request_id", sa.String(length=80), nullable=True),
            sa.Column("meldung", sa.Text(), nullable=True),
            sa.Column("meldungen", sa.JSON(), nullable=True),
            sa.Column("traceback", sa.Text(), nullable=True),
            sa.Column("benutzer", sa.String(length=140), nullable=True),
            sa.Column("erzeugt", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_ts_ereignis_sitzung", "ts_ereignis", ["sitzung"])
        op.create_index("ix_ts_ereignis_zeitpunkt", "ts_ereignis", ["zeitpunkt"])

    if not _tabelle_existiert("ts_kommentar"):
        op.create_table(
            "ts_kommentar",
            sa.Column("name", sa.String(length=140), primary_key=True),
            sa.Column("sitzung", sa.String(length=140), nullable=True),
            sa.Column("benutzer", sa.String(length=140), nullable=True),
            sa.Column("text", sa.Text(), nullable=True),
            sa.Column("art", sa.String(length=30), nullable=False, server_default="kommentar"),
            sa.Column("seite", sa.String(length=200), nullable=True),
            sa.Column("route", sa.String(length=300), nullable=True),
            sa.Column("viewport", sa.String(length=40), nullable=True),
            sa.Column("user_agent", sa.String(length=300), nullable=True),
            sa.Column("bilder", sa.JSON(), nullable=True),
            sa.Column("ereignisse", sa.JSON(), nullable=True),
            sa.Column("zeitpunkt", sa.DateTime(), nullable=True),
            sa.Column("creation", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_ts_kommentar_sitzung", "ts_kommentar", ["sitzung"])

    if not _tabelle_existiert("ts_szenario"):
        op.create_table(
            "ts_szenario",
            sa.Column("name", sa.String(length=140), primary_key=True),
            sa.Column("szenario_id", sa.String(length=200), nullable=False),
            sa.Column("modul", sa.String(length=80), nullable=True),
            sa.Column("seite", sa.String(length=200), nullable=True),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="ungetestet"),
            sa.Column("ergebnis", sa.String(length=30), nullable=False, server_default="ungetestet"),
            sa.Column("befunde", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("offene_befunde", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("letzter_tester", sa.String(length=140), nullable=True),
            sa.Column("letzte_pruefung", sa.DateTime(), nullable=True),
            sa.Column("notiz", sa.Text(), nullable=True),
            sa.Column("geaendert_von_hand", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("creation", sa.DateTime(), nullable=True),
            sa.Column("modified", sa.DateTime(), nullable=True),
            sa.UniqueConstraint("szenario_id", name="uq_ts_szenario_id"),
        )
        op.create_index("ix_ts_szenario_modul", "ts_szenario", ["modul"])

    if not _tabelle_existiert("ts_befund"):
        op.create_table(
            "ts_befund",
            sa.Column("name", sa.String(length=140), primary_key=True),
            sa.Column("sitzung", sa.String(length=140), nullable=True),
            sa.Column("szenario_id", sa.String(length=200), nullable=True),
            sa.Column("seite", sa.String(length=200), nullable=True),
            sa.Column("titel", sa.String(length=300), nullable=True),
            sa.Column("meldung", sa.Text(), nullable=True),
            sa.Column("ereignis", sa.String(length=140), nullable=True),
            sa.Column("kommentar", sa.String(length=140), nullable=True),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="offen"),
            sa.Column("gemeldet_von", sa.String(length=140), nullable=True),
            sa.Column("zeitpunkt", sa.DateTime(), nullable=True),
            sa.Column("creation", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_ts_befund_sitzung", "ts_befund", ["sitzung"])
        op.create_index("ix_ts_befund_szenario", "ts_befund", ["szenario_id"])

    _rolle_anlegen()


def _rolle_anlegen() -> None:
    """Rolle ``Tester`` in der ``role``-Tabelle anlegen.

    **Spalten sind geprueft, nicht angenommen** (`\\d role` an der migrierten
    Datenbank): ``role`` hat genau EINE Spalte (``name``). Ein INSERT mit
    ``creation``/``modified``/``docstatus`` scheitert auf PostgreSQL hart
    (``column "creation" of relation "role" does not exist``) — der erste
    Teststack-Lauf hat genau das gezeigt.

    Die Zuordnung zu einem Benutzer laeuft NICHT ueber ``nutzereinzelrechte``
    (die Tabelle hat keine ``role``-Spalte, sondern ``nutzer`` + ``name``),
    sondern wie bei allen Rollen ueber ``has_role`` (Kind von ``user``). Das
    ist derselbe Weg, den ``rechte.ist_tester`` liest.
    """
    bind = op.get_bind()
    if _tabelle_existiert("role"):
        vorhanden = bind.execute(
            sa.text("SELECT 1 FROM role WHERE name = :n"), {"n": ROLLE}
        ).first()
        if not vorhanden:
            bind.execute(sa.text("INSERT INTO role (name) VALUES (:n)"), {"n": ROLLE})


def downgrade() -> None:
    bind = op.get_bind()
    if _tabelle_existiert("has_role"):
        bind.execute(sa.text("DELETE FROM has_role WHERE role = :r"), {"r": ROLLE})
    if _tabelle_existiert("role"):
        bind.execute(sa.text("DELETE FROM role WHERE name = :r"), {"r": ROLLE})

    for tabelle in ("ts_befund", "ts_szenario", "ts_kommentar", "ts_ereignis", "ts_sitzung"):
        if _tabelle_existiert(tabelle):
            op.drop_table(tabelle)
