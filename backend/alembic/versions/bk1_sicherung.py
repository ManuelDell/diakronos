"""BACKUP-1: Einstellungen und Protokoll der eigenen Datensicherung.

Revision ID: bk1_sicherung
Revises: austritt_merkmale
Create Date: 2026-10-20

Zwei neue Tabellen (kein Frappe-DocType, Handmodell wie ``n9_gemeinde``):

1. ``sicherungseinstellungen`` — Single-Zeile mit automatisch an/aus,
   Uhrzeit und Aufbewahrung in Tagen (Standard 30, Minimum 1).
2. ``sicherungslauf`` — je Sicherungslauf eine Zeile (Zeitpunkt, Groesse,
   Status, Meldung). Die Liste in der Oberflaeche liest daraus.

Idempotent: jede Operation prueft zuerst, ob die Tabelle schon existiert
(Lehre P3-2 — der Entrypoint migriert bei JEDEM Start, auch auf einer
bestehenden DB). ``downgrade`` entfernt nur diese beiden Tabellen.

Die Erstbelegung der Einstellungszeile macht ``sicherung/einstellungen.py``
beim ersten Lesen (``holen_oder_anlegen``) — die Migration legt bewusst KEINE
Zeile mit festem Standard an, damit ``BACKUP_AUFBEWAHRUNG_TAGE`` aus der
``.env`` beim ersten Start greift und nicht von einem Migrationswert
ueberstimmt wird.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "bk1_sicherung"
down_revision: Union[str, None] = "austritt_merkmale"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _hat(name: str) -> bool:
	return sa.inspect(op.get_bind()).has_table(name)


def upgrade() -> None:
	if not _hat("sicherungseinstellungen"):
		op.create_table(
			"sicherungseinstellungen",
			sa.Column("name", sa.String(length=140), primary_key=True),
			sa.Column("automatisch", sa.Boolean(), nullable=False, server_default=sa.true()),
			sa.Column("uhrzeit", sa.String(length=5), nullable=False, server_default="03:00"),
			sa.Column("aufbewahrung_tage", sa.Integer(), nullable=False, server_default="30"),
			sa.Column("created", sa.DateTime(), nullable=True),
			sa.Column("modified", sa.DateTime(), nullable=True),
			sa.Column("modified_by", sa.String(length=140), nullable=True),
			sa.Column("created_by", sa.String(length=140), nullable=True),
		)

	if not _hat("sicherungslauf"):
		op.create_table(
			"sicherungslauf",
			sa.Column("name", sa.String(length=140), primary_key=True),
			sa.Column("begonnen_am", sa.DateTime(), nullable=False),
			sa.Column("beendet_am", sa.DateTime(), nullable=True),
			sa.Column("status", sa.String(length=20), nullable=False, server_default="laeuft"),
			sa.Column("groesse_bytes", sa.Integer(), nullable=True),
			sa.Column("ausloeser", sa.String(length=20), nullable=False, server_default="automatisch"),
			sa.Column("meldung", sa.Text(), nullable=True),
			sa.Column("benachrichtigt", sa.Text(), nullable=True),
		)


def downgrade() -> None:
	if _hat("sicherungslauf"):
		op.drop_table("sicherungslauf")
	if _hat("sicherungseinstellungen"):
		op.drop_table("sicherungseinstellungen")
