"""N9b: veroeffentlichte Fassung der Datenschutz-Texte von Entwurf trennen (M-2).

Revision ID: n9b_datenschutz_pub
Revises: n9b_zuordnung_ablehnung
Create Date: 2026-10-18

Der Entwurf (``datenschutz_text``) und die geltende, veroeffentlichte Fassung
liegen ab jetzt in getrennten Single-Zeilen. Vorher ueberschrieb ein Speichern
OHNE Haken (Entwurf) den Inhalt der einzigen Zeile — ein Entwurf vernichtete
damit die zuletzt veroeffentlichte Fassung, und die oeffentliche Seite fiel auf
den Standardtext zurueck. Das widerspricht der Zusage der Oberflaeche ("Solange
der Haken fehlt, bleibt der bisherige Text stehen").

Die neue Tabelle ``datenschutz_text_veroeffentlicht`` haelt die geltende Fassung.
Der Upgrade kopiert eine bereits veroeffentlichte Bestandszeile hinueber, damit
bestehende Installationen ihren Text nicht verlieren.

Idempotent: prueft zuerst, ob die Tabelle schon existiert; die Datenuebernahme
laeuft nur, wenn noch keine veroeffentlichte Zeile vorhanden ist. ``downgrade``
entfernt nur die neue Tabelle.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "n9b_datenschutz_pub"
down_revision: Union[str, None] = "n9b_zuordnung_ablehnung"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NAME = "Datenschutz Texte veroeffentlicht"


def _hat(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def upgrade() -> None:
    bind = op.get_bind()
    if not _hat("datenschutz_text_veroeffentlicht"):
        op.create_table(
            "datenschutz_text_veroeffentlicht",
            sa.Column("name", sa.String(length=140), primary_key=True),
            sa.Column("einwilligung", sa.Text(), nullable=True),
            sa.Column("datenschutzerklaerung", sa.Text(), nullable=True),
            sa.Column("aufbewahrung", sa.Text(), nullable=True),
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("created", sa.DateTime(), nullable=True),
            sa.Column("modified", sa.DateTime(), nullable=True),
            sa.Column("modified_by", sa.String(length=140), nullable=True),
            sa.Column("created_by", sa.String(length=140), nullable=True),
        )

    # Bestandsinstallationen: war der Entwurf zuletzt veroeffentlicht, ist genau
    # er die geltende Fassung — einmalige Uebernahme. Danach fuehren Entwurf und
    # veroeffentlichte Fassung getrennte Leben.
    if not _hat("datenschutz_text"):
        return
    vorhanden = bind.execute(
        sa.text(
            "SELECT COUNT(*) FROM datenschutz_text_veroeffentlicht "
            "WHERE name = :n"
        ),
        {"n": _NAME},
    ).scalar()
    if vorhanden:
        return
    bind.execute(
        sa.text(
            "INSERT INTO datenschutz_text_veroeffentlicht "
            "(name, einwilligung, datenschutzerklaerung, aufbewahrung, version, "
            " created, modified, modified_by, created_by) "
            "SELECT :neu, einwilligung, datenschutzerklaerung, aufbewahrung, "
            "       version, created, modified, modified_by, created_by "
            "FROM datenschutz_text "
            "WHERE name = :alt AND veroeffentlicht = true"
        ),
        {"neu": _NAME, "alt": "Datenschutz Texte"},
    )


def downgrade() -> None:
    if _hat("datenschutz_text_veroeffentlicht"):
        op.drop_table("datenschutz_text_veroeffentlicht")
