"""UX2b: Papierkorb — ``geloescht_am`` / ``geloescht_von`` an fuenf Tabellen.

WAS DIESE MIGRATION TUT
-----------------------
Legt das weiche Loeschen an: fuenf Tabellen bekommen zwei nullable Spalten

  * ``geloescht_am``  TIMESTAMP — gesetzt = Zeile liegt im Papierkorb.
  * ``geloescht_von`` VARCHAR(140) — wer geloescht hat (Konto).

Betroffene Tabellen (Karte UX2b, P1):

  * ``beitrag``       — Beitrag (Gemeinde-Feed, Website)
  * ``element``       — Termin (Kalender, CalDAV, iCal, Website, Planrahmen)
  * ``gruppe``        — Gruppe (Organigramm, Website)
  * ``wiki_artikel``  — Wiki-Seite
  * ``lied``          — Lied (Psalmos, Planrahmen-Sammlung)

Bewusst KEIN Index: jede Leseabfrage filtert ohnehin auf einen kleinen
Bestand (Liste, Zeitfenster, Slug) und ``geloescht_am IS NULL`` trifft fast
alle Zeilen — ein Index darauf bringt nichts, ein Teilindex waere eine zweite
Wahrheit ueber die Aufbewahrung. Die Frist steht im Code
(``diakronos_app.papierkorb.AUFBEWAHRUNG_TAGE``).

Idempotent
----------
Jeder Schritt prueft den Bestand (Spalte vorhanden?) — ein zweiter Lauf
aendert nichts. Das Muster ist dasselbe wie in ``p15b_ablehnungsgrund`` und
``bs1a_website_freigaben``; es funktioniert auf PostgreSQL (Betrieb) und auf
SQLite (Test-Rundlauf).

Einziger Head
-------------
``down_revision = "ux1j_gestaltung"`` — die Kette hat genau einen Kopf.

Revision ID: ux2b_papierkorb
Revises: ux1j_gestaltung
Create Date: 2026-11-04
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "ux2b_papierkorb"
down_revision: Union[str, None] = "ux1j_gestaltung"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

#: Tabellen, die den Papierkorb bekommen (Reihenfolge = Reihenfolge im Lauf).
TABELLEN = ("beitrag", "element", "gruppe", "wiki_artikel", "lied")

#: Neue Spalten: (Name, Typ).
SPALTEN = (
    ("geloescht_am", sa.DateTime(timezone=False)),
    ("geloescht_von", sa.String(length=140)),
)


def _tabelle_names(bind) -> set[str]:
    """Vorhandene Tabellennamen in den durchsuchten Schemata (klein).

    SQLite kennt kein Schema ``public``; dort wird nur das Hauptschema gelesen
    (Muster aus ``bs1a_website_freigaben``).
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


def upgrade() -> None:
    bind = op.get_bind()
    vorhanden = _tabelle_names(bind)
    for tabelle in TABELLEN:
        if tabelle not in vorhanden:
            # Fehlende Tabelle ist kein Fehler: die Migration legt nur Spalten
            # an bestehenden Tabellen an (die Modelle erzeugen die Tabellen).
            continue
        for spalte, typ in SPALTEN:
            if not _hat_spalte(bind, tabelle, spalte):
                op.add_column(tabelle, sa.Column(spalte, typ, nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    vorhanden = _tabelle_names(bind)
    for tabelle in TABELLEN:
        if tabelle not in vorhanden:
            continue
        for spalte, _typ in reversed(SPALTEN):
            if _hat_spalte(bind, tabelle, spalte):
                op.drop_column(tabelle, spalte)
