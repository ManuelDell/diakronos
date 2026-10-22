"""N9: Gemeinde- und Datenschutz-Einstellungen pflegbar machen.

Revision ID: n9_gemeinde
Revises: n6_loeschantrag
Create Date: 2026-10-18

Zwei neue Single-Zeilen-Tabellen (kein Frappe-DocType):

1. ``gemeinde_einstellungen`` — Kontakt-E-Mail, öffentliche Adresse,
   Willkommenstext und die Standardwerte neuer Registrierungslinks.
2. ``datenschutz_text`` — die pflegbaren Einwilligungs-, Datenschutz- und
   Aufbewahrungstexte samt Versionszähler (Beleg der akzeptierten Fassung).

Der Gemeindename und die Modul-Sichtbarkeit bleiben in der portierten Single
``diakronos_einstellungen`` unverändert — dafür braucht es keine Migration.

Idempotent: jede Operation prüft zuerst, ob die Tabelle schon existiert.
``downgrade`` entfernt nur diese beiden Tabellen wieder.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "n9_gemeinde"
down_revision: Union[str, None] = "n6_loeschantrag"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _hat(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def upgrade() -> None:
    if not _hat("gemeinde_einstellungen"):
        op.create_table(
            "gemeinde_einstellungen",
            sa.Column("name", sa.String(length=140), primary_key=True),
            sa.Column("kontakt_email", sa.String(length=255), nullable=True),
            sa.Column("oeffentliche_adresse", sa.String(length=255), nullable=True),
            sa.Column("willkommenstext", sa.Text(), nullable=True),
            sa.Column("link_laufzeit_tage", sa.Integer(), nullable=False, server_default="30"),
            sa.Column("link_max_anmeldungen", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created", sa.DateTime(), nullable=True),
            sa.Column("modified", sa.DateTime(), nullable=True),
            sa.Column("modified_by", sa.String(length=140), nullable=True),
            sa.Column("created_by", sa.String(length=140), nullable=True),
        )

    if not _hat("datenschutz_text"):
        op.create_table(
            "datenschutz_text",
            sa.Column("name", sa.String(length=140), primary_key=True),
            sa.Column("einwilligung", sa.Text(), nullable=True),
            sa.Column("datenschutzerklaerung", sa.Text(), nullable=True),
            sa.Column("aufbewahrung", sa.Text(), nullable=True),
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("veroeffentlicht", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("created", sa.DateTime(), nullable=True),
            sa.Column("modified", sa.DateTime(), nullable=True),
            sa.Column("modified_by", sa.String(length=140), nullable=True),
            sa.Column("created_by", sa.String(length=140), nullable=True),
        )


def downgrade() -> None:
    if _hat("datenschutz_text"):
        op.drop_table("datenschutz_text")
    if _hat("gemeinde_einstellungen"):
        op.drop_table("gemeinde_einstellungen")
