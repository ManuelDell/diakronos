"""N9b: abgelehnte E-Mail-Zuordnungen sichtbar machen (R-N8, Punkt 2).

Revision ID: n9b_zuordnung_ablehnung
Revises: n9_gemeinde
Create Date: 2026-10-18

Neue Tabelle ``auth_zuordnung_ablehnung``: trifft ein Anbieter-Konto ueber die
E-Mail auf eine Person, deren Zuordnung nicht eindeutig/verifiziert/freigegeben
ist, wird der Login abgelehnt. Bisher sah das nur der abgewiesene Mensch; die
Verwaltung erfuhr nichts. Diese Zeile macht den Fall unter „wartende Konten“
sichtbar — mit Grund. ``(issuer, sub)`` ist eindeutig (upsert, kein Spam).

Idempotent: prueft zuerst, ob die Tabelle schon existiert. ``downgrade``
entfernt nur diese Tabelle wieder.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "n9b_zuordnung_ablehnung"
down_revision: Union[str, None] = "n9_gemeinde"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _hat(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def upgrade() -> None:
    if not _hat("auth_zuordnung_ablehnung"):
        op.create_table(
            "auth_zuordnung_ablehnung",
            sa.Column("name", sa.String(length=36), primary_key=True),
            sa.Column("issuer", sa.String(length=255), nullable=False),
            sa.Column("sub", sa.String(length=255), nullable=False),
            sa.Column("email", sa.String(length=255), nullable=True),
            sa.Column("name_anzeige", sa.String(length=255), nullable=True),
            sa.Column("grund", sa.String(length=60), nullable=False),
            sa.Column("meldung", sa.Text(), nullable=True),
            sa.Column("versuche", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("zuletzt", sa.DateTime(), nullable=True),
            sa.Column("created", sa.DateTime(), nullable=True),
            sa.UniqueConstraint(
                "issuer", "sub", name="uq_auth_zuordnung_ablehnung_issuer_sub"
            ),
        )


def downgrade() -> None:
    if _hat("auth_zuordnung_ablehnung"):
        op.drop_table("auth_zuordnung_ablehnung")
