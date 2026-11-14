"""R-7b: Gruppenaufgaben bekommen eine Zuweisung.

Manuel 11.11.: „eigene Aufgaben und Aufgaben die man in der Gruppe zuweisen
kann. Abhaken darf der, dem es zugewiesen wurde.“ ``zugewiesen_an`` zeigt auf
das Mitglied; eine Aufgabe ohne Gruppe ist eine eigene Aufgabe ihres
``owner`` (das braucht keine Spalte).

Idempotent; SQLite und PostgreSQL. Den Fremdschluessel legt nur PostgreSQL
an (SQLite kennt kein ALTER TABLE ADD CONSTRAINT, siehe p11).

Revision ID: r7b_aufgaben_zuweisung
Revises: r5_moderation_stufen
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "r7b_aufgaben_zuweisung"
down_revision = "r5_moderation_stufen"
branch_labels = None
depends_on = None

_TABELLE = "gruppen_aufgabe"
_SPALTE = "zugewiesen_an"
_INDEX = "ix_gruppen_aufgabe_zugewiesen_an"
_FK = "fk_gruppen_aufgabe_zugewiesen_an"


def upgrade() -> None:
    bind = op.get_bind()
    ins = sa.inspect(bind)
    if _SPALTE not in {s["name"] for s in ins.get_columns(_TABELLE)}:
        op.add_column(_TABELLE, sa.Column(_SPALTE, sa.String(length=140), nullable=True))
    if _INDEX not in {i["name"] for i in ins.get_indexes(_TABELLE)}:
        op.create_index(_INDEX, _TABELLE, [_SPALTE])
    if bind.dialect.name == "sqlite":
        return
    if not any(fk.get("name") == _FK for fk in sa.inspect(bind).get_foreign_keys(_TABELLE)):
        op.create_foreign_key(_FK, _TABELLE, "mitglied", [_SPALTE], ["name"])


def downgrade() -> None:
    bind = op.get_bind()
    ins = sa.inspect(bind)
    if bind.dialect.name != "sqlite" and any(fk.get("name") == _FK for fk in ins.get_foreign_keys(_TABELLE)):
        op.drop_constraint(_FK, _TABELLE, type_="foreignkey")
    if _INDEX in {i["name"] for i in ins.get_indexes(_TABELLE)}:
        op.drop_index(_INDEX, table_name=_TABELLE)
    if _SPALTE in {s["name"] for s in ins.get_columns(_TABELLE)}:
        with op.batch_alter_table(_TABELLE) as batch:
            batch.drop_column(_SPALTE)
