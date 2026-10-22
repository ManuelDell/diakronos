"""MAIL-1: SMTP-Einstellungen in der Datenbank (Oberflaeche statt .env).

Revision ID: ma1_smtp
Revises: dsgvo1_loeschantrag_freigabe
Create Date: 2026-10-21

Eine neue Tabelle (kein Frappe-DocType, Handmodell wie ``bk1_sicherung``):
``smtp_einstellungen`` — Single-Zeile mit Server, Port, Sicherheit, Zugang,
Absender und dem VERSCHLUESSELTEN Passwort. Bis hier kam die Konfiguration aus
``SMTP_*`` in der ``.env``; Manuel hat entschieden, dass das Postfach bei der
Einrichtung in der Oberflaeche bestimmt wird (S1/S4).

Idempotent: ``upgrade`` prueft zuerst, ob die Tabelle schon existiert (Lehre
P3-2 — der Entrypoint migriert bei JEDEM Start, auch auf einer bestehenden DB).
``downgrade`` entfernt nur diese eine Tabelle; die ``.env`` bleibt unberuehrt.

Es wird bewusst KEINE Zeile angelegt: „nicht eingerichtet\" ist ein gueltiger
Zustand, und die Migration soll keinen Standard-Absender erfinden.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "ma1_smtp"
down_revision: Union[str, None] = "dsgvo1_loeschantrag_freigabe"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABELLE = "smtp_einstellungen"


def _hat(name: str) -> bool:
	return sa.inspect(op.get_bind()).has_table(name)


def upgrade() -> None:
	if _hat(TABELLE):
		return
	op.create_table(
		TABELLE,
		sa.Column("name", sa.String(length=140), primary_key=True),
		sa.Column("host", sa.String(length=255), nullable=False),
		sa.Column("port", sa.Integer(), nullable=False),
		sa.Column("sicherheit", sa.String(length=20), nullable=False,
		          server_default="starttls"),
		sa.Column("benutzername", sa.String(length=255), nullable=True),
		# Fernet-Geheimtext (Praefix ``fernet:v1:``) — nie Klartext.
		sa.Column("passwort_verschluesselt", sa.String(length=1024), nullable=True),
		sa.Column("absender", sa.String(length=255), nullable=False),
		sa.Column("absender_name", sa.String(length=140), nullable=True),
		sa.Column("timeout", sa.Integer(), nullable=False, server_default="15"),
		sa.Column("created", sa.DateTime(), nullable=True),
		sa.Column("modified", sa.DateTime(), nullable=True),
		sa.Column("modified_by", sa.String(length=140), nullable=True),
		sa.Column("created_by", sa.String(length=140), nullable=True),
		sa.Column("eingerichtet", sa.Boolean(), nullable=False,
		          server_default=sa.true()),
	)


def downgrade() -> None:
	if _hat(TABELLE):
		op.drop_table(TABELLE)
