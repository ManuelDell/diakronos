"""DATEIEN-R: Gruppeneinstellungen im Rechtekern.

Revision ID: dateien_r_gruppeneinstellung
Revises: chat12c_anhang_groesse
Create Date: 2026-11-23

Manuel 21.11.: Gruppendateien „Hochladen = alle Mitglieder, Anpinnen = nur
Verantwortliche, je Gruppe durch HV/MV umstellbar“; Konzept DATEIEN-KONZEPT.md
2.3 Variante b: EINE allgemeine Kern-Tabelle (gruppe, schluessel, wert) statt
Modul-Spalten an ``rechte_modul``.

Keine Datenmigration: keine Zeile heißt Vorgabe (``kern.GRUPPENEINSTELLUNGEN``).
Idempotent: Tabelle nur anlegen, wenn sie fehlt. ``downgrade`` entfernt sie —
danach gelten wieder die Vorgaben.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "dateien_r_gruppeneinstellung"
down_revision: Union[str, None] = "chat12c_anhang_groesse"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABELLE = "rechte_gruppeneinstellung"


def upgrade() -> None:
    if sa.inspect(op.get_bind()).has_table(TABELLE):
        return
    op.create_table(
        TABELLE,
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("gruppe", sa.String(140), nullable=False),
        sa.Column("schluessel", sa.String(80), nullable=False),
        sa.Column("wert", sa.String(200), nullable=False),
    )
    op.create_index("uq_rechte_gruppeneinstellung", TABELLE, ["gruppe", "schluessel"], unique=True)


def downgrade() -> None:
    if sa.inspect(op.get_bind()).has_table(TABELLE):
        op.drop_index("uq_rechte_gruppeneinstellung", table_name=TABELLE)
        op.drop_table(TABELLE)
