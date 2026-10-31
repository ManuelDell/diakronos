"""BS-1a: Freigaben fuer die Website — Spalten an Kalender/Gruppe/Beitrag.

Was diese Migration tut
-----------------------
Legt die drei Freigabe-Schalter und den URL-Slug an, mit denen die
Verwaltung bestimmt, WAS auf der oeffentlichen Website erscheinen darf
(Grundsatz G1: nichts ist oeffentlich, solange es nicht ausdruecklich
freigegeben ist — jeder neue Schalter steht deshalb auf AUS):

  1. ``kalender.website_freigabe``            BOOLEAN NOT NULL DEFAULT false
     ``kalender.website_slug``                 VARCHAR(140), NULL, UNIQUE
     ``kalender.website_nur_oeffentliche_kategorien``
                                               BOOLEAN NOT NULL DEFAULT false
  2. ``gruppe.website_freigabe``              BOOLEAN NOT NULL DEFAULT false
     ``gruppe.website_slug``                   VARCHAR(140), NULL, UNIQUE
  3. ``beitrag.auf_website``                  BOOLEAN NOT NULL DEFAULT false

Der Slug wird NICHT in der Migration vergeben: es gibt keine Zeile, die ohne
ausdrueckliche Freigabe einen oeffentlichen Namen braucht, und eine Migration
darf keine Oeffentlichkeit erzeugen. Die API leitet ihn beim Freigeben aus
``calendar_name`` bzw. ``gruppenname`` ab (``website/freigaben.py``).

Eindeutigkeit
-------------
Je Tabelle ein PARTIELLER Unique-Index (``WHERE website_slug IS NOT NULL``):
mehrere Zeilen ohne Slug sind erlaubt (PostgreSQL wertet NULLs im
Unique-Index zwar ohnehin als verschieden, der partielle Index macht die
Absicht aber sichtbar und ist auf SQLite gleich streng). Beim Anlegen wird
ein bereits vergebener Slug NICHT still umbenannt, sondern die Migration
bricht mit einer Meldung ab — Doppel-Slugs im Bestand sind ein Datenfehler,
den ein Mensch entscheiden muss (die Migration ist auf einer frischen und
einer bestehenden DB idempotent, siehe ``upgrade``).

Idempotent
----------
Jeder Schritt prueft den Bestand (Spalte vorhanden? Index vorhanden?); ein
zweiter Lauf aendert nichts. ``downgrade`` entfernt Index und Spalten wieder,
vorhandene Daten in anderen Spalten bleiben unberuehrt.

SQLite (Test-Rundlauf, BS-1a2/F6)
---------------------------------
Die Bestandspruefungen lesen nur dann ``schema="public"``, wenn der Dialekt es
kennt: ``SELECT … FROM "public".sqlite_master`` endet auf SQLite in
``no such table`` und liess bisher jeden SQLite-Lauf dieser Migration
scheitern. Auf SQLite ist die Migration damit fahrbar (``upgrade`` ->
``downgrade`` -> ``upgrade`` mit partiellem Unique-Index); im Betrieb
(PostgreSQL) bleibt alles wie vorher.

Einziger Head
-------------
``down_revision = "web1b_primo_konto"`` — die Kette hat genau einen Kopf.

Revision ID: bs1a_website_freigaben
Revises: web1b_primo_konto
Create Date: 2026-10-31
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "bs1a_website_freigaben"
down_revision: Union[str, None] = "web1b_primo_konto"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

#: (Tabelle, Spalte, Typ, serverseitiger Default, NOT NULL)
NEUE_SPALTEN = (
    ("kalender", "website_freigabe", sa.Boolean(), sa.text("false"), True),
    ("kalender", "website_slug", sa.String(length=140), None, False),
    (
        "kalender",
        "website_nur_oeffentliche_kategorien",
        sa.Boolean(),
        sa.text("false"),
        True,
    ),
    ("gruppe", "website_freigabe", sa.Boolean(), sa.text("false"), True),
    ("gruppe", "website_slug", sa.String(length=140), None, False),
    ("beitrag", "auf_website", sa.Boolean(), sa.text("false"), True),
)

#: Partielle Unique-Indizes auf den Slugs.
SLUG_INDIZES = (
    ("uq_kalender_website_slug", "kalender", "website_slug"),
    ("uq_gruppe_website_slug", "gruppe", "website_slug"),
)

#: Tabelle der Kontakt-Postfaecher (Handmodell ``models/website_kontakt.py``).
TABELLE_POSTFACH = "website_kontakt_postfach"


def _hat_tabelle(bind, name: str) -> bool:
    """Case-insensibler Tabellentest (Frappe legt klein an, Modelle schreiben gross)."""
    return str(name).lower() in _tabelle_names(bind)


def _tabelle_names(bind) -> set[str]:
    """Vorhandene Tabellennamen in den durchsuchten Schemata (klein).

    SQLite kennt kein Schema ``public`` (``SELECT … FROM "public".sqlite_master``
    endet in ``no such table``) — dort wird nur das Hauptschema gelesen
    (BS-1a2/F6: der SQLite-Rundlauf).
    """
    insp = sa.inspect(bind)
    namen = insp.get_table_names()
    if bind.dialect.name != "sqlite":
        namen = namen + insp.get_table_names(schema="public")
    return {str(name).lower() for name in namen}


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


def _doppelte_slugs(bind, tabelle: str, spalte: str) -> list[str]:
    """Slugs, die in ``tabelle`` mehr als einmal vorkommen (ohne NULL)."""
    zeilen = bind.execute(
        sa.text(
            f"SELECT {spalte} FROM {_echter_name(bind, tabelle)} "
            f"WHERE {spalte} IS NOT NULL "
            f"GROUP BY {spalte} HAVING COUNT(*) > 1"
        )
    ).scalars().all()
    return [str(z) for z in zeilen]


def upgrade() -> None:
    bind = op.get_bind()

    for tabelle, spalte, typ, default, not_null in NEUE_SPALTEN:
        if not _hat_spalte(bind, tabelle, spalte):
            op.add_column(
                tabelle,
                sa.Column(
                    spalte,
                    typ,
                    nullable=not not_null,
                    server_default=default,
                ),
            )

    for index, tabelle, spalte in SLUG_INDIZES:
        if not _hat_index(bind, tabelle, index):
            doppelt = _doppelte_slugs(bind, tabelle, spalte)
            if doppelt:
                raise RuntimeError(
                    f"{tabelle}.{spalte}: Slug mehrfach vergeben "
                    f"({', '.join(sorted(doppelt))}) — vor der Migration "
                    "bereinigen (kein automatisches Umbenennen)."
                )
            op.create_index(
                index,
                tabelle,
                [spalte],
                unique=True,
                postgresql_where=sa.text(f"{spalte} IS NOT NULL"),
                sqlite_where=sa.text(f"{spalte} IS NOT NULL"),
            )

    # Neue Tabelle: die Postfaecher des Kontaktformulars.
    if not _hat_tabelle(bind, TABELLE_POSTFACH):
        op.create_table(
            TABELLE_POSTFACH,
            sa.Column("slug", sa.String(length=140), nullable=False),
            sa.Column("bezeichnung", sa.String(length=140), nullable=False),
            sa.Column("email", sa.String(length=320), nullable=False),
            sa.Column(
                "aktiv", sa.Boolean(), nullable=False, server_default=sa.text("true")
            ),
            sa.Column(
                "sortierung", sa.Integer(), nullable=False, server_default=sa.text("0")
            ),
            sa.PrimaryKeyConstraint("slug"),
        )


def downgrade() -> None:
    bind = op.get_bind()

    if _hat_tabelle(bind, TABELLE_POSTFACH):
        op.drop_table(TABELLE_POSTFACH)

    for index, tabelle, spalte in reversed(SLUG_INDIZES):
        if _hat_index(bind, tabelle, index):
            op.drop_index(index, table_name=tabelle)

    for tabelle, spalte, _typ, _default, _not_null in reversed(NEUE_SPALTEN):
        if _hat_spalte(bind, tabelle, spalte):
            op.drop_column(tabelle, spalte)
