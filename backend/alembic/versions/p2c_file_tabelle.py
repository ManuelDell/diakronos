"""file-tabelle fuer hochgeladene Anhaenge

Revision ID: p2c_file
Revises: p1bmodelle
Create Date: 2026-09-24 22:05:00.000000

P2c: `/api/method/upload_file` legt ein Frappe-`File`-Dokument an. Die Datei
selbst liegt im Dateisystem (Volume, `settings.files_dir`); diese Tabelle haelt
nur die Metadaten. `File` ist ein Frappe-Core-DocType und daher nicht Teil der
73 DocTypes des Frappe-Originals — die Tabelle wird deshalb hier explizit
angelegt und nicht vom Generator erzeugt.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'p2c_file'
down_revision: Union[str, None] = "3f4d296602ab"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'file',
        sa.Column('name', sa.String(length=140), nullable=False),
        sa.Column('file_name', sa.String(length=255), nullable=False),
        sa.Column('file_url', sa.String(length=512), nullable=False),
        sa.Column('is_private', sa.Boolean(), nullable=False),
        sa.Column('attached_to_doctype', sa.String(length=140), nullable=True),
        sa.Column('attached_to_name', sa.String(length=140), nullable=True),
        sa.Column('attached_to_field', sa.String(length=140), nullable=True),
        sa.Column('file_size', sa.Integer(), nullable=True),
        sa.Column('content_hash', sa.String(length=64), nullable=True),
        sa.Column('folder', sa.String(length=140), nullable=True),
        sa.Column('creation', sa.DateTime(), nullable=True),
        sa.Column('modified', sa.DateTime(), nullable=True),
        sa.Column('modified_by', sa.String(length=140), nullable=True),
        sa.Column('owner', sa.String(length=140), nullable=True),
        sa.Column('docstatus', sa.Integer(), nullable=False),
        sa.Column('idx', sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint('name'),
    )
    op.create_index(op.f('ix_file_attached_to_doctype'), 'file', ['attached_to_doctype'], unique=False)
    op.create_index(op.f('ix_file_attached_to_name'), 'file', ['attached_to_name'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_file_attached_to_name'), table_name='file')
    op.drop_index(op.f('ix_file_attached_to_doctype'), table_name='file')
    op.drop_table('file')
