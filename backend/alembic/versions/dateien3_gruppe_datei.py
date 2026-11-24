"""DATEIEN-3: Gruppendateien (``gruppe_datei``) + Entsorgungsliste.

Revision ID: dateien3_gruppe_datei
Revises: dateien_r_gruppeneinstellung
Create Date: 2026-11-23

Konzept ``DATEIEN-KONZEPT.md`` Abschnitt 3 und die Entscheidungen Manuel
23.11.2026 (F3, F4, F5, F9):

  ``gruppe_datei`` (NEUE Tabelle) — ``name`` (PK, ``gdatei-<hex>``), ``gruppe``,
  ``untergruppe`` (NULL = Datei der Hauptgruppe, F3), ``schluessel`` (Ablage),
  ``dateiname`` (≤ 120), ``mime``, ``groesse``, ``angelegt_am``,
  ``angelegt_von``, ``angepinnt``/``angepinnt_am``/``angepinnt_von``,
  ``geloescht_am``/``geloescht_von`` (Papierkorb, F5).

  Zwei Indizes aus dem Konzept: ``ix_gruppe_datei_raum``
  (gruppe, untergruppe, geloescht_am — der Listen-Abruf) und
  ``ix_gruppe_datei_angepinnt`` (gruppe, angepinnt — der obere Block).

  ``gruppe_datei_entsorgung`` (NEUE Tabelle) — wörtlich das Muster von
  ``chat_anhang_entsorgung``: ``schluessel`` (PK), ``versuche``,
  ``naechster_versuch_am``, ``belegt_bis``, ``angelegt_am``. Abgearbeitet wird
  sie vom Aufräum-Job aus DATEIEN-5; diese Karte legt nur Tabelle und Weg an.

  KEINE ``gruppe_datei_hochladung``: F9 sagt „kein Tageslimit“.

  Alle drei ``user``-Verweise tragen ``ON DELETE SET NULL`` — wie
  ``chat_anhang.angelegt_von``. Den Personenbezug erfasst trotzdem die DSGVO
  VOR dem Löschen der ``user``-Zeile (``dsgvo_anonymisierung``).

Idempotent: jede Tabelle/jeder Index wird nur angelegt, wenn er fehlt; das
Upgrade läuft damit auch auf einer Datenbank durch, die durch
``Base.metadata.create_all`` schon alles hat.
``downgrade`` entfernt beide Tabellen (Indizes zuerst); Dateien in der Ablage
bleiben dabei bewusst stehen — ohne ihre Zeile sind sie nicht erreichbar.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "dateien3_gruppe_datei"
down_revision: Union[str, None] = "dateien_r_gruppeneinstellung"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABELLE = "gruppe_datei"
ENTSORGUNG = "gruppe_datei_entsorgung"
INDEX_RAUM = "ix_gruppe_datei_raum"
INDEX_PIN = "ix_gruppe_datei_angepinnt"
INDEX_ENTS_AM = "ix_gruppe_datei_entsorgung_am"
INDEX_ENTS_NAECHSTER = "ix_gruppe_datei_entsorgung_naechster"


def _indizes(bind, tabelle: str) -> set[str]:
    return {i["name"] for i in sa.inspect(bind).get_indexes(tabelle)}


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if not insp.has_table(TABELLE):
        op.create_table(
            TABELLE,
            sa.Column("name", sa.String(140), primary_key=True),
            sa.Column("gruppe", sa.String(140), nullable=False),
            sa.Column("untergruppe", sa.String(140), nullable=True),
            sa.Column("schluessel", sa.String(200), nullable=False),
            sa.Column("dateiname", sa.String(120), nullable=False),
            sa.Column("mime", sa.String(100), nullable=False),
            sa.Column("groesse", sa.BigInteger(), nullable=False),
            sa.Column("angelegt_am", sa.DateTime(), nullable=False),
            sa.Column("angelegt_von", sa.String(140), nullable=True),
            sa.Column("angepinnt", sa.Boolean(), nullable=False,
                      server_default=sa.text("false")),
            sa.Column("angepinnt_am", sa.DateTime(), nullable=True),
            sa.Column("angepinnt_von", sa.String(140), nullable=True),
            sa.Column("geloescht_am", sa.DateTime(), nullable=True),
            sa.Column("geloescht_von", sa.String(140), nullable=True),
            # Drei Konto-Verweise, ON DELETE SET NULL — wie
            # ``chat_anhang.angelegt_von``. Den Personenbezug erfasst die DSGVO
            # VOR dem Löschen der ``user``-Zeile (dsgvo_anonymisierung).
            sa.ForeignKeyConstraint(["angelegt_von"], ["user.name"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["angepinnt_von"], ["user.name"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["geloescht_von"], ["user.name"], ondelete="SET NULL"),
        )

    vorhanden = _indizes(bind, TABELLE)
    if INDEX_RAUM not in vorhanden:
        op.create_index(INDEX_RAUM, TABELLE, ["gruppe", "untergruppe", "geloescht_am"])
    if INDEX_PIN not in vorhanden:
        op.create_index(INDEX_PIN, TABELLE, ["gruppe", "angepinnt"])

    if not sa.inspect(bind).has_table(ENTSORGUNG):
        op.create_table(
            ENTSORGUNG,
            sa.Column("schluessel", sa.String(200), primary_key=True),
            sa.Column("versuche", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("naechster_versuch_am", sa.DateTime(), nullable=False),
            sa.Column("belegt_bis", sa.DateTime(), nullable=True),
            sa.Column("angelegt_am", sa.DateTime(), nullable=False),
        )

    entsorgung_indizes = _indizes(bind, ENTSORGUNG)
    if INDEX_ENTS_AM not in entsorgung_indizes:
        op.create_index(INDEX_ENTS_AM, ENTSORGUNG, ["angelegt_am"])
    if INDEX_ENTS_NAECHSTER not in entsorgung_indizes:
        op.create_index(INDEX_ENTS_NAECHSTER, ENTSORGUNG, ["naechster_versuch_am"])


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if insp.has_table(TABELLE):
        vorhanden = _indizes(bind, TABELLE)
        for name in (INDEX_RAUM, INDEX_PIN):
            if name in vorhanden:
                op.drop_index(name, table_name=TABELLE)
        op.drop_table(TABELLE)

    if sa.inspect(bind).has_table(ENTSORGUNG):
        vorhanden = _indizes(bind, ENTSORGUNG)
        for name in (INDEX_ENTS_AM, INDEX_ENTS_NAECHSTER):
            if name in vorhanden:
                op.drop_index(name, table_name=ENTSORGUNG)
        op.drop_table(ENTSORGUNG)
