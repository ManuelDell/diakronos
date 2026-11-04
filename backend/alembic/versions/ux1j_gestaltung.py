"""UX1j — Alembic-Migration: Tabelle `gestaltung_abweichung`.

Was diese Migration tut
-----------------------
Legt die Tabelle `gestaltung_abweichung` an: `token` (PK, CSS-Variablenname),
`wert` (ganze px-Zahl), `geaendert_von`, `geaendert_am`.

Sie ändert KEINE Daten: eine neue Installation hat keine Abweichungen, eine
bestehende behält ihre (keine gibt es noch — die Tabelle ist neu).

Idempotent
----------
`upgrade` legt die Tabelle nur an, wenn sie fehlt. `downgrade` entfernt sie nur,
wenn sie da ist. Damit läuft die Migration auf einer FRISCHEN und auf einer
BESTEHENDEN Datenbank gleich sauber — der Entrypoint ruft sie bei jedem Start.

Einziger Head
-------------
`down_revision = "on1_einrichtung"` — die Kette hat genau einen Kopf.

Revision ID: ux1j_gestaltung
Revises: on1_einrichtung
Create Date: 2026-11-03
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "ux1j_gestaltung"
down_revision: Union[str, None] = "on1_einrichtung"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABELLE = "gestaltung_abweichung"


def _hat_tabelle(bind, name: str) -> bool:
    """Case-insensibler Tabellentest (Frappe legt klein an, Modelle schreiben gross)."""
    insp = sa.inspect(bind)
    namen = {str(k).lower() for k in insp.get_table_names()}
    # Wie on1_einrichtung: das Schema "public" gibt es NUR auf PostgreSQL.
    if bind.dialect.name == "postgresql":
        namen |= {str(k).lower() for k in insp.get_table_names(schema="public")}
    return str(name).lower() in namen


def upgrade() -> None:
    bind = op.get_bind()

    if not _hat_tabelle(bind, TABELLE):
        op.create_table(
            TABELLE,
            sa.Column("token", sa.String(length=40), nullable=False),
            sa.Column("wert", sa.Integer(), nullable=False),
            sa.Column("geaendert_von", sa.String(length=140), nullable=True),
            sa.Column(
                "geaendert_am",
                sa.DateTime(timezone=False),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.PrimaryKeyConstraint("token"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    if not _hat_tabelle(bind, TABELLE):
        return
    op.drop_table(TABELLE)
