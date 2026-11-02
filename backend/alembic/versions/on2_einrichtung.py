"""ON-2 — Einrichtungs-Daten: Kontaktfelder, Logo-Verweis, Assistentenstand.

Was diese Migration tut
-----------------------
1. Ergaenzt ``gemeinde_einstellungen`` um die Felder des Einrichtungs-Assistenten:
   ``kurzname``, ``strasse``, ``plz``, ``ort``, ``telefon``, ``website`` und
   ``logo_datei``. Alle nullable — eine bestehende Installation hat diese
   Angaben schlicht noch nicht, und der Assistent laesst sie ueberspringen.
2. Legt die Single-Zeilen-Tabelle ``einrichtung_stand`` an (Assistentenstand
   und „Spaeter erinnern“). Es wird KEINE Zeile vorbefuellt: „noch nie
   gespeichert“ und „alles offen“ sind derselbe gueltige Zustand.
3. Aendert KEINE Daten. Eine Datenmigration gibt es hier nicht — die
   Assistenten-Punkte werden zur Laufzeit aus echten Daten berechnet
   (``einrichtung.status``), es gibt also nichts zu uebernehmen.

Idempotent
----------
Jede Operation prueft zuerst, ob Spalte/Tabelle schon existiert (Vorfall 15.10.:
eine Migration muss auf frischer UND bestehender DB laufen). ``downgrade``
entfernt nur, was diese Migration angelegt hat.

Einziger Head
-------------
``down_revision = "bs1a_website_freigaben"`` (F3: auf das aktuelle main
angehoben — BS-1a haengt seinerseits an ``web1b_primo_konto``) — die Kette hat
genau einen Kopf.

Revises: bs1a_website_freigaben

Revision ID: on2_einrichtung
Create Date: 2026-10-31
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "on2_einrichtung"
down_revision: Union[str, None] = "bs1a_website_freigaben"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

GEMEINDE = "gemeinde_einstellungen"
STAND = "einrichtung_stand"

#: (Spaltenname, Typ) in der Reihenfolge des Modells.
NEUE_SPALTEN = (
    ("kurzname", sa.String(length=40)),
    ("strasse", sa.String(length=120)),
    ("plz", sa.String(length=10)),
    ("ort", sa.String(length=120)),
    ("telefon", sa.String(length=40)),
    ("website", sa.String(length=255)),
    ("logo_datei", sa.String(length=255)),
)


def _tabelle_echt(bind, name: str) -> str | None:
    """Name der Tabelle in der Datenbank (Gross-/Kleinschreibung egal).

    ``schema="public"`` wird nur auf PostgreSQL abgefragt: auf SQLite gibt es
    das Schema nicht, und ``get_table_names(schema="public")`` laesst den
    Dialekt ``public.sqlite_master`` fragen (``OperationalError``). Der
    Testlauf im Image faehrt die Migrationen auf SQLite — dort also ohne
    Schema, im Betrieb (PostgreSQL) mit.
    """
    insp = sa.inspect(bind)
    kandidaten = list(insp.get_table_names())
    if bind.dialect.name == "postgresql":
        kandidaten += insp.get_table_names(schema="public")
    for kandidat in kandidaten:
        if str(kandidat).lower() == str(name).lower():
            return str(kandidat)
    return None


def _spalten(bind, tabelle: str) -> set[str]:
    insp = sa.inspect(bind)
    return {str(s.get("name") or "").lower() for s in insp.get_columns(tabelle)}


def upgrade() -> None:
    bind = op.get_bind()

    echt = _tabelle_echt(bind, GEMEINDE)
    if echt is not None:
        vorhanden = _spalten(bind, echt)
        for spalte, typ in NEUE_SPALTEN:
            if spalte.lower() not in vorhanden:
                op.add_column(echt, sa.Column(spalte, typ, nullable=True))

    if _tabelle_echt(bind, STAND) is None:
        op.create_table(
            STAND,
            sa.Column("name", sa.String(length=140), primary_key=True),
            sa.Column(
                "assistent_abgeschlossen",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
            sa.Column("schritt_gemeinde", sa.String(length=20), nullable=True),
            sa.Column("schritt_kontakt", sa.String(length=20), nullable=True),
            sa.Column("schritt_mailversand", sa.String(length=20), nullable=True),
            sa.Column("schritt_module", sa.String(length=20), nullable=True),
            sa.Column(
                "schritt_mitglieder_kalender", sa.String(length=20), nullable=True
            ),
            sa.Column("erinnerung_ab", sa.Date(), nullable=True),
            sa.Column("created", sa.DateTime(), nullable=True),
            sa.Column("modified", sa.DateTime(), nullable=True),
            sa.Column("modified_by", sa.String(length=140), nullable=True),
            sa.Column("created_by", sa.String(length=140), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()

    echt = _tabelle_echt(bind, STAND)
    if echt is not None:
        op.drop_table(echt)

    echt = _tabelle_echt(bind, GEMEINDE)
    if echt is not None:
        vorhanden = _spalten(bind, echt)
        for spalte, _typ in reversed(NEUE_SPALTEN):
            if spalte.lower() in vorhanden:
                op.drop_column(echt, spalte)
