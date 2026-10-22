"""A1a passwort_hash an der user-Tabelle

Revision ID: a1a_password
Revises: 5d5b8cb2204a
Create Date: 2026-09-25 11:50:00.000000

Legt die Spalte `user.password_hash` an. Sie nimmt die aus Frappe
uebernommenen Passworthashes auf (`__Auth`, doctype='User',
fieldname='password', encrypted=0) sowie spaeter Argon2-Hashes fuer neu
gesetzte Passwoerter.

Kein Klartext, keine Fernet-Verschluesselung — `Text` ist ausreichend und
grosszuegig fuer beide Hashformate.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1a_password'
down_revision: Union[str, None] = '5d5b8cb2204a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('user', sa.Column('password_hash', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('user', 'password_hash')
