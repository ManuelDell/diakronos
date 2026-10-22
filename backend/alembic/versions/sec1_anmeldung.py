"""SEC1: Anmeldung ueber Authentik — Identitaeten + Admin-Einstellungen

Revision ID: sec1_anmeldung
Revises: ln1_lied_quelle
Create Date: 2026-10-12

Legt drei Tabellen an:

1. ``auth_oidc_identitaet`` — stabile Zuordnung ``(issuer, sub)`` -> Diakronos-
   Benutzer. Eindeutig ueber ``(issuer, sub)``; ``user`` mit ON DELETE CASCADE,
   damit das Loeschen eines Benutzers die Zuordnung mitnimmt.

2. ``auth_einstellungen`` — ``Single``-Zeile (Default ``abweisen``). Wird von
   der Anwendung bei Bedarf angelegt; die Migration legt KEINE Zeile an, damit
   eine bestehende Installation nichts Zusaetzliches bekommt.

3. ``auth_gruppen_rolle`` — Kind-Baum Authentik-Gruppe -> Diakronos-Rolle,
   eindeutig ueber ``(parent, gruppe)``.

Idempotent: jede Operation prueft zuerst, ob das Objekt schon existiert (fuer
den Fall, dass die Migration auf einer DB laeuft, in der die Tabellen z. B.
durch einen Testlauf bereits bestehen). ``downgrade`` raeumt in umgekehrter
Reihenfolge auf.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "sec1_anmeldung"
down_revision: Union[str, None] = "ln1_lied_quelle"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _tabelle_existiert(name: str) -> bool:
    """True, wenn die Tabelle laut aktueller Verbindung schon da ist."""
    bind = op.get_bind()
    return sa.inspect(bind).has_table(name)


def upgrade() -> None:
    if not _tabelle_existiert("auth_oidc_identitaet"):
        op.create_table(
            "auth_oidc_identitaet",
            sa.Column("name", sa.String(length=36), primary_key=True),
            sa.Column("issuer", sa.String(length=255), nullable=False),
            sa.Column("sub", sa.String(length=255), nullable=False),
            sa.Column("user", sa.String(length=140), nullable=False),
            sa.Column("email", sa.String(length=255), nullable=True),
            sa.Column("zuletzt_gesehen", sa.DateTime(), nullable=True),
            sa.Column("created", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.Column("modified", sa.DateTime(), nullable=True),
            sa.Column("created_by", sa.String(length=140), nullable=True),
            sa.ForeignKeyConstraint(
                ["user"], ["user.name"], name="fk_auth_oidc_identitaet_user",
                ondelete="CASCADE",
            ),
            sa.UniqueConstraint(
                "issuer", "sub", name="uq_auth_oidc_identitaet_issuer_sub"
            ),
        )
        op.create_index(
            "ix_auth_oidc_identitaet_user", "auth_oidc_identitaet", ["user"]
        )

    if not _tabelle_existiert("auth_einstellungen"):
        op.create_table(
            "auth_einstellungen",
            sa.Column("name", sa.String(length=140), primary_key=True),
            sa.Column(
                "unbekannte_nutzer",
                sa.String(length=40),
                nullable=False,
                server_default="abweisen",
            ),
            sa.Column(
                "admin_ueber_gruppen",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
            sa.Column(
                "aktiv", sa.Boolean(), nullable=False, server_default=sa.false()
            ),
            sa.Column("created", sa.DateTime(), nullable=True),
            sa.Column("modified", sa.DateTime(), nullable=True),
            sa.Column("created_by", sa.String(length=140), nullable=True),
        )

    if not _tabelle_existiert("auth_gruppen_rolle"):
        op.create_table(
            "auth_gruppen_rolle",
            sa.Column("name", sa.String(length=36), primary_key=True),
            sa.Column("parent", sa.String(length=140), nullable=True),
            sa.Column("parenttype", sa.String(length=140), nullable=True),
            sa.Column("parentfield", sa.String(length=140), nullable=True),
            sa.Column("idx", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("gruppe", sa.String(length=255), nullable=False),
            sa.Column("rolle", sa.String(length=140), nullable=False),
            sa.Column("created", sa.DateTime(), nullable=True),
            sa.Column("modified", sa.DateTime(), nullable=True),
            sa.Column("modified_by", sa.String(length=140), nullable=True),
            sa.UniqueConstraint(
                "parent", "gruppe", name="uq_auth_gruppen_rolle_parent_gruppe"
            ),
        )
        op.create_index("ix_auth_gruppen_rolle_parent", "auth_gruppen_rolle", ["parent"])


def downgrade() -> None:
    if _tabelle_existiert("auth_gruppen_rolle"):
        op.drop_index("ix_auth_gruppen_rolle_parent", table_name="auth_gruppen_rolle")
        op.drop_table("auth_gruppen_rolle")
    if _tabelle_existiert("auth_einstellungen"):
        op.drop_table("auth_einstellungen")
    if _tabelle_existiert("auth_oidc_identitaet"):
        op.drop_index("ix_auth_oidc_identitaet_user", table_name="auth_oidc_identitaet")
        op.drop_table("auth_oidc_identitaet")
