"""PF2: Indizes fuer die Lieder-Liste (Sortierung, Kind-Filter, Suche)

Revision ID: pf2_lied_indizes
Revises: sec1_anmeldung
Create Date: 2026-10-13

Die Lieder-Liste sortiert nach ``lied.titel`` und filtert ueber Kind-Tabellen
(``lied_gruppenzuordnung.gruppe``, ``lied_kategorie.kategorie``,
``lied_anlass.anlass``). ``get_lieder`` laedt Fassungen gebuendelt ueber
``liedfassung.lied``. Diese Spalten tragen bisher KEINEN Index (nur die
``parent``-Spalte der Kind-Tabellen ist indiziert; Postgres legt fuer
Fremdschluessel-Kinder von sich aus keinen an). Bei 134 Liedern faellt das
kaum auf, waechst aber mit jeder Gemeinde linear mit.

Alle Indizes sind ``IF NOT EXISTS`` und der ganze Lauf ist idempotent —
ein erneutes ``upgrade`` aendert nichts. ``downgrade`` entfernt genau diese
Indizes wieder.

Bewusst NICHT dabei: ein Index auf ``liedstrophe.text`` fuer die Suche. Die
Suche nutzt ``LIKE '%…%'``; ein Btree-Index hilft dabei nicht (nur ein
GIN/Trigramm-Index taete das, braucht aber die ``pg_trgm``-Erweiterung und
gehoert in eine eigene Karte). Die Suche ist bei dieser Datenmenge ohnehin
nicht der Engpass (Messung PF2).
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "pf2_lied_indizes"
down_revision: Union[str, None] = "sec1_anmeldung"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# (Indexname, Tabelle, Spalte)
INDIZES: list[tuple[str, str, str]] = [
    ("ix_lied_titel", "lied", "titel"),
    ("ix_liedfassung_lied", "liedfassung", "lied"),
    ("ix_liedgruppe_lied_lied", "liedgruppe_lied", "lied"),
    ("ix_lied_gruppenzuordnung_gruppe", "lied_gruppenzuordnung", "gruppe"),
    ("ix_lied_kategorie_kategorie", "lied_kategorie", "kategorie"),
    ("ix_lied_anlass_anlass", "lied_anlass", "anlass"),
]


def upgrade() -> None:
    bind = op.get_bind()
    for name, tabelle, spalte in INDIZES:
        # Idempotent: nur anlegen, wenn noch nicht vorhanden. So laeuft die
        # Migration auch auf einer DB sauber, die den Index schon traegt.
        vorhanden = bind.execute(
            sa.text("SELECT 1 FROM pg_indexes WHERE schemaname = 'public' "
                    "AND indexname = :n"), {"n": name}).first()
        if vorhanden is None:
            op.create_index(name, tabelle, [spalte], unique=False)


def downgrade() -> None:
    for name, _tabelle, _spalte in reversed(INDIZES):
        op.drop_index(name, table_name=_tabelle, if_exists=True)
