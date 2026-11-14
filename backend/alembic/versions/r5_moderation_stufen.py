"""R-5: offene Moderationsstufen je Termin und je Aenderungsvorschlag.

Ein Vorschlag durchlaeuft bis zu zwei Stufen (Manuel 11.11.): zuerst die
Gruppenleitung (``gruppe``: HV/MV), danach — bei gemeindeweit freigegebenen
Kalendern — die Gemeinde-Moderation (``gemeinde``). Welche Stufen noch offen
sind, steht in ``moderation_offen`` (kommagetrennt, z. B. ``gruppe,gemeinde``).
Leer/NULL = Bestand oder Entwurf: dann gilt die letzte Stufe des Kalenders
(entscheidet der Rechte-Kern, ``rechte.erforderliche_stufen``).

Idempotent; SQLite und PostgreSQL (nur ``add_column``).

Revision ID: r5_moderation_stufen
Revises: r1_rechte_kern
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "r5_moderation_stufen"
down_revision = "r1_rechte_kern"
branch_labels = None
depends_on = None

_TABELLEN = ("element", "element_aenderung")


def _spalten(bind, tabelle: str) -> set[str]:
    return {s["name"] for s in sa.inspect(bind).get_columns(tabelle)}


def upgrade() -> None:
    bind = op.get_bind()
    for tabelle in _TABELLEN:
        if "moderation_offen" not in _spalten(bind, tabelle):
            op.add_column(tabelle, sa.Column("moderation_offen", sa.String(length=40), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    for tabelle in _TABELLEN:
        if "moderation_offen" in _spalten(bind, tabelle):
            with op.batch_alter_table(tabelle) as batch:
                batch.drop_column("moderation_offen")
