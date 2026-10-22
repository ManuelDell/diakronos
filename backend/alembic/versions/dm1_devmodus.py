"""DM1: Dev-Modus — Tabellen, Datenuebernahme aus der Testsuite, Testsuite-Tabellen weg.

Revision ID: dm1_devmodus
Revises: ts1_testsuite
Create Date: 2026-10-15

Der Dev-Modus ersetzt die Testsuite. Diese Migration:

1. Legt die neuen Tabellen an: ``dm_sitzung`` (Herzschlag je Nutzer),
   ``dm_ereignis`` (Fehlerumfeld) und ``dm_befund`` (Text, Art, Wichtigkeit,
   Status, Ort, Element-Kontext, Bilder, Audio).
2. **Uebernimmt die Daten** aus ``ts_befund`` und ``ts_kommentar`` in
   ``dm_befund`` (falls die alten Tabellen vorhanden sind) — nichts geht
   verloren, bevor die alten Tabellen fallen.
3. Entfernt die Testsuite-Tabellen ``ts_szenario``, ``ts_kommentar``,
   ``ts_ereignis``, ``ts_befund``, ``ts_sitzung``.

Idempotent: jede Operation prueft zuerst, ob das Objekt schon existiert.
``downgrade`` legt die Testsuite-Tabellen in der Form von ``ts1_testsuite``
wieder an (ohne Katalogdaten — die kommen aus dem Paket) und entfernt die
Dev-Modus-Tabellen. Die Rolle ``Tester`` bleibt bestehen (sie gehoert zur
Benutzerverwaltung, nicht zur Testsuite).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "dm1_devmodus"
down_revision: Union[str, None] = "ts1_testsuite"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _tabelle_existiert(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def upgrade() -> None:
    if not _tabelle_existiert("dm_sitzung"):
        op.create_table(
            "dm_sitzung",
            sa.Column("benutzer", sa.String(length=140), primary_key=True),
            sa.Column("aktiv", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("begonnen", sa.DateTime(), nullable=True),
            sa.Column("herzschlag", sa.DateTime(), nullable=True),
            sa.Column("creation", sa.DateTime(), nullable=True),
            sa.Column("modified", sa.DateTime(), nullable=True),
        )

    if not _tabelle_existiert("dm_ereignis"):
        op.create_table(
            "dm_ereignis",
            sa.Column("name", sa.String(length=140), primary_key=True),
            sa.Column("benutzer", sa.String(length=140), nullable=True),
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
            sa.Column("erzeugt", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_dm_ereignis_benutzer", "dm_ereignis", ["benutzer"])
        op.create_index("ix_dm_ereignis_zeitpunkt", "dm_ereignis", ["zeitpunkt"])

    if not _tabelle_existiert("dm_befund"):
        op.create_table(
            "dm_befund",
            sa.Column("name", sa.String(length=140), primary_key=True),
            sa.Column("benutzer", sa.String(length=140), nullable=True),
            sa.Column("text", sa.Text(), nullable=True),
            sa.Column("art", sa.String(length=30), nullable=False, server_default="fehler"),
            sa.Column("wichtigkeit", sa.String(length=20), nullable=False, server_default="mittel"),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="offen"),
            sa.Column("titel", sa.String(length=300), nullable=True),
            sa.Column("url", sa.String(length=1000), nullable=True),
            sa.Column("route", sa.String(length=300), nullable=True),
            sa.Column("seitentitel", sa.String(length=300), nullable=True),
            sa.Column("seite", sa.String(length=200), nullable=True),
            sa.Column("viewport", sa.String(length=40), nullable=True),
            sa.Column("bildschirm", sa.String(length=40), nullable=True),
            sa.Column("geraet", sa.String(length=300), nullable=True),
            sa.Column("browser", sa.String(length=300), nullable=True),
            sa.Column("theme", sa.String(length=20), nullable=True),
            sa.Column("sprache", sa.String(length=20), nullable=True),
            sa.Column("element", sa.JSON(), nullable=True),
            sa.Column("fehlerumfeld", sa.JSON(), nullable=True),
            sa.Column("bilder", sa.JSON(), nullable=True),
            sa.Column("audio", sa.JSON(), nullable=True),
            sa.Column("zeitpunkt", sa.DateTime(), nullable=True),
            sa.Column("creation", sa.DateTime(), nullable=True),
            sa.Column("modified", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_dm_befund_benutzer", "dm_befund", ["benutzer"])
        op.create_index("ix_dm_befund_art", "dm_befund", ["art"])
        op.create_index("ix_dm_befund_status", "dm_befund", ["status"])
        op.create_index("ix_dm_befund_seite", "dm_befund", ["seite"])
        op.create_index("ix_dm_befund_zeitpunkt", "dm_befund", ["zeitpunkt"])

    _befunde_uebernehmen()
    _testsuite_tabellen_entfernen()


def _befunde_uebernehmen() -> None:
    """Kopiert ts_befund und ts_kommentar nach dm_befund (vor dem Loeschen).

    Alles laeuft ueber dieselbe Transaktion der Migration. Die Namen werden mit
    ``alt-``/``altk-`` gepraefixt, damit die Herkunft erkennbar bleibt und ein
    erneuter Lauf (idempotent) keine Doppel erzeugt.
    """
    bind = op.get_bind()
    if _tabelle_existiert("ts_befund"):
        zeilen = bind.execute(sa.text(
            "SELECT name, seite, titel, meldung, status, gemeldet_von, zeitpunkt "
            "FROM ts_befund")).mappings().all()
        for z in zeilen:
            name = f"alt-{z['name']}"[:140]
            da = bind.execute(sa.text("SELECT 1 FROM dm_befund WHERE name = :n"),
                              {"n": name}).first()
            if da:
                continue
            bind.execute(sa.text(
                "INSERT INTO dm_befund (name, benutzer, text, art, wichtigkeit,"
                " status, titel, seitentitel, seite, bilder, zeitpunkt, creation, modified)"
                " VALUES (:name, :benutzer, :text, 'fehler', 'mittel', :status,"
                " :titel, :seitentitel, :seite, '[]', :zeitpunkt, now(), now())"),
                {"name": name, "benutzer": z["gemeldet_von"], "text": z["meldung"],
                 "status": z["status"] if z["status"] in
                 ("offen", "an_claude", "behoben", "verworfen") else "offen",
                 "titel": z["titel"], "seitentitel": z["titel"], "seite": z["seite"],
                 "zeitpunkt": z["zeitpunkt"]})
    if _tabelle_existiert("ts_kommentar"):
        zeilen = bind.execute(sa.text(
            "SELECT name, text, seite, route, benutzer, zeitpunkt "
            "FROM ts_kommentar")).mappings().all()
        for z in zeilen:
            name = f"altk-{z['name']}"[:140]
            da = bind.execute(sa.text("SELECT 1 FROM dm_befund WHERE name = :n"),
                              {"n": name}).first()
            if da:
                continue
            bind.execute(sa.text(
                "INSERT INTO dm_befund (name, benutzer, text, art, wichtigkeit,"
                " status, titel, route, seite, bilder, zeitpunkt, creation, modified)"
                " VALUES (:name, :benutzer, :text, 'frage', 'mittel', 'offen',"
                " :titel, :route, :seite, '[]', :zeitpunkt, now(), now())"),
                {"name": name, "benutzer": z["benutzer"], "text": z["text"],
                 "titel": z["seite"] or z["route"], "route": z["route"],
                 "seite": z["seite"], "zeitpunkt": z["zeitpunkt"]})


def _testsuite_tabellen_entfernen() -> None:
    for tabelle in ("ts_szenario", "ts_kommentar", "ts_ereignis", "ts_befund", "ts_sitzung"):
        if _tabelle_existiert(tabelle):
            op.drop_table(tabelle)


def downgrade() -> None:
    """Zurueck zur Testsuite: dm_* weg, ts_* in der Form von ts1_testsuite wieder da."""
    for tabelle in ("dm_befund", "dm_ereignis", "dm_sitzung"):
        if _tabelle_existiert(tabelle):
            op.drop_table(tabelle)

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
