"""TERMIN-GRUPPE: `element.gruppe` aus dem Kalender nachtragen (BUG-T1).

Revision ID: tg1_element_gruppe_kalender
Revises: r9_meine_aufgaben_widget
Create Date: 2026-11-17

Befund (BUG-T1, Manuel 17.11.): `element.gruppe` (FK -> `gruppe.name`, also
nur Hauptgruppen) wurde von keinem Schreibweg gesetzt — auf jedem regulär
angelegten Termin war das Feld leer, obwohl `planrahmen` und die Gruppenseite
es lesen. Ab jetzt setzt `diakronos_app.termin_gruppe` es beim Schreiben aus
dem Kalender. Diese Migration trägt den BESTAND nach.

DIE ZUORDNUNG
-------------
`element.element_calendar` -> `rechte_objekt` (`typ='kalender'`,
`objekt=<kalender>`). Dort steht bei Untergruppen-Kalendern bereits die
HAUPTgruppe (`untergruppe` nennt die Untergruppe) — genau das, was der FK
zulässt.

DIE GRENZE (Review 17.11.)
--------------------------
Geschrieben wird AUSSCHLIESSLICH in LEERE Felder:

    UPDATE element SET gruppe = <Ziel>
     WHERE gruppe IS NULL AND <Ziel> IS NOT NULL

Damit gilt: nie NULL schreiben (ein Kalender ohne Gruppenzuordnung — Gemeinde-
Kalender, Kalender ohne `rechte_objekt`-Zeile — ist keine Aussage über den
Termin), nie einen vorhandenen Wert überschreiben (Altbestand aus der Zeit vor
dieser Regel, bewusst gesetzte Sonderfälle; das wäre Datenverlust). Dieselbe
Regel wie beim Schreiben (`termin_gruppe.ergaenze_gruppe`): die Ableitung
ergänzt, sie löscht nicht. Termine ohne Kalender bleiben unberührt.

Idempotent: schreibt nur, wo `gruppe` leer ist und der Kalender eine Gruppe
hat — ein zweiter Lauf ändert nichts (die geschriebenen Zeilen sind nicht mehr
NULL).

downgrade: bewusst ein NO-OP. Die Migration hat nur LEERE Felder gefüllt; der
alte Zustand („leer“) ist ohne Informationsverlust rekonstruierbar, aber ein
automatisches Zurücksetzen müsste raten, welche Zeile vorher schon einen Wert
trug (die Migration hat das nicht protokolliert). Ein pauschales „alles auf
NULL“ wäre genau der Datenverlust, den das Upgrade vermeidet.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "tg1_element_gruppe_kalender"
down_revision: Union[str, None] = "r9_meine_aufgaben_widget"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

#: Ziel-Ausdruck: Hauptgruppe des Kalenders (NULL, wenn es keine gibt).
_ZIEL = """(
    SELECT NULLIF(trim(ro.gruppe), '')
      FROM rechte_objekt ro
     WHERE ro.typ = 'kalender'
       AND ro.objekt = element.element_calendar
)"""


def _tabellen_da() -> bool:
    insp = sa.inspect(op.get_bind())
    return insp.has_table("element") and insp.has_table("rechte_objekt")


def upgrade() -> None:
    if not _tabellen_da():
        return
    bind = op.get_bind()
    bind.execute(
        sa.text(
            f"UPDATE element SET gruppe = {_ZIEL}"
            f" WHERE gruppe IS NULL AND {_ZIEL} IS NOT NULL"
        )
    )


def downgrade() -> None:
    """No-op mit Begründung (siehe Modul-Docstring)."""
    return
