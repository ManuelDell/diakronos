"""BS-3a: Einwilligung fuer die Website-Ansprechpartner + Auswahl der Bereiche.

Was diese Migration tut
-----------------------
Sie legt die zwei Bausteine an, die die Karte P1/P2 verlangt:

**1. Einwilligung am Mitglied** (personenbezogen, DSGVO — Default AUS):

  * ``mitglied.website_einwilligung``        BOOLEAN NOT NULL DEFAULT false
  * ``mitglied.website_einwilligung_am``     TIMESTAMP, NULL
  * ``mitglied.website_einwilligung_foto``   BOOLEAN NOT NULL DEFAULT false
  * ``mitglied.website_anzeigename``         VARCHAR(140), NULL

Die Defaults sind der Kern: nach der Migration ist NIEMAND oeffentlich. Eine
Migration darf keine Oeffentlichkeit erzeugen (G1) — sie kann eine Zustimmung
nicht ersetzen, weil nur die Person selbst sie geben kann.

**2. Auswahl der Bereiche** (Verwaltungsentscheidung, keine Personendaten):
die Tabelle ``website_ansprechpartner`` mit einer Zeile je Funktion/Position,
die auf der Website erscheinen soll, und einem optionalen Kontakt-Postfach
(``postfach`` = Slug aus ``website_kontakt_postfach``, NIE eine Adresse).
Eindeutigkeit ueber ``(art, funktion)``.

Idempotent
----------
Jeder Schritt prueft den Bestand (Spalte/Tabelle/Index vorhanden?); ein
zweiter Lauf aendert nichts. ``downgrade`` entfernt Tabelle, Index und
Spalten wieder; Daten in anderen Spalten bleiben unberuehrt (die
Einwilligungswerte gehen mit den Spalten verloren — das ist der Preis eines
Rueckbaus und in der Übergabe benannt).

SQLite und PostgreSQL
---------------------
Alle Bestandspruefungen laufen ueber den SQLAlchemy-Inspector; es gibt kein
rohes SQL mit Schemapraefix und keinen typabhaengigen Ausdruck (Vorfall ON-6:
ein Typfehler fiel erst im Betrieb auf). ``BOOLEAN`` mit ``sa.text("false")``
ist auf beiden Dialekten derselbe Weg wie in ``bs1a_website_freigaben``; der
Zeitstempel ist ``TIMESTAMP`` ohne Zone wie der gesamte Bestand.

Revision ID: bs3a_website_einwilligung
Revises: on6_root_benutzer
Create Date: 2026-11-08
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "bs3a_website_einwilligung"
down_revision: Union[str, None] = "on6_root_benutzer"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

#: (Spalte, Typ, serverseitiger Default, NOT NULL) — Tabelle ist ``mitglied``.
NEUE_SPALTEN = (
    ("website_einwilligung", sa.Boolean(), sa.text("false"), True),
    ("website_einwilligung_am", sa.DateTime(timezone=False), None, False),
    ("website_einwilligung_foto", sa.Boolean(), sa.text("false"), True),
    ("website_anzeigename", sa.String(length=140), None, False),
)

TABELLE = "mitglied"
#: Tabelle der ausgewaehlten Bereiche (Handmodell
#: ``models/website_ansprechpartner.py``).
TABELLE_BEREICHE = "website_ansprechpartner"
INDEX_BEREICHE = "uq_website_ansprechpartner_art_funktion"


def _tabelle_namen(bind) -> set[str]:
    """Vorhandene Tabellennamen in den durchsuchten Schemata (klein)."""
    insp = sa.inspect(bind)
    namen = insp.get_table_names()
    if bind.dialect.name != "sqlite":
        namen = namen + insp.get_table_names(schema="public")
    return {str(name).lower() for name in namen}


def _hat_tabelle(bind, name: str) -> bool:
    """Case-insensibler Tabellentest (Frappe legt klein an, Modelle schreiben gross)."""
    return str(name).lower() in _tabelle_namen(bind)


def _echter_name(bind, name: str) -> str:
    """Katalogschreibweise eines Tabellennamens."""
    insp = sa.inspect(bind)
    vorhanden = insp.get_table_names()
    if bind.dialect.name != "sqlite":
        vorhanden = vorhanden + insp.get_table_names(schema="public")
    for kandidat in vorhanden:
        if str(kandidat).lower() == str(name).lower():
            return str(kandidat)
    return name


def _hat_spalte(bind, tabelle: str, spalte: str) -> bool:
    insp = sa.inspect(bind)
    return any(
        str(s["name"]).lower() == str(spalte).lower()
        for s in insp.get_columns(_echter_name(bind, tabelle))
    )


def _hat_index(bind, tabelle: str, index: str) -> bool:
    insp = sa.inspect(bind)
    return any(
        str(ix.get("name") or "").lower() == str(index).lower()
        for ix in insp.get_indexes(_echter_name(bind, tabelle))
    )


def upgrade() -> None:
    bind = op.get_bind()

    # Review BS-3a (HOCH 3): OHNE die Tabelle `mitglied` gibt es keine Spalten
    # anzulegen. Vorher lief der Spaltenblock blind und brach auf einer
    # Datenbank ab, die die Tabelle nicht führt (`test_bs1a2…::
    # test_f6_sqlite_rundlauf_upgrade_downgrade_upgrade`). Derselbe Schutz wie
    # in den BS-1-Migrationen.
    if _hat_tabelle(bind, TABELLE):
        for spalte, typ, default, not_null in NEUE_SPALTEN:
            if not _hat_spalte(bind, TABELLE, spalte):
                op.add_column(
                    TABELLE,
                    sa.Column(spalte, typ, nullable=not not_null, server_default=default),
                )

    if not _hat_tabelle(bind, TABELLE_BEREICHE):
        op.create_table(
            TABELLE_BEREICHE,
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("art", sa.String(length=20), nullable=False),
            sa.Column("funktion", sa.String(length=140), nullable=False),
            sa.Column("bezeichnung", sa.String(length=140), nullable=True),
            sa.Column("postfach", sa.String(length=140), nullable=True),
            sa.Column(
                "sortierung", sa.Integer(), nullable=False, server_default=sa.text("0")
            ),
            sa.PrimaryKeyConstraint("id"),
        )

    if not _hat_index(bind, TABELLE_BEREICHE, INDEX_BEREICHE):
        op.create_index(
            INDEX_BEREICHE,
            TABELLE_BEREICHE,
            ["art", "funktion"],
            unique=True,
        )


def downgrade() -> None:
    bind = op.get_bind()

    if _hat_index(bind, TABELLE_BEREICHE, INDEX_BEREICHE):
        op.drop_index(INDEX_BEREICHE, table_name=TABELLE_BEREICHE)

    if _hat_tabelle(bind, TABELLE_BEREICHE):
        op.drop_table(TABELLE_BEREICHE)

    if _hat_tabelle(bind, TABELLE):
        for spalte, _typ, _default, _not_null in reversed(NEUE_SPALTEN):
            if _hat_spalte(bind, TABELLE, spalte):
                op.drop_column(TABELLE, spalte)
