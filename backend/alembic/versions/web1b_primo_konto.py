"""WEB-1b — Alembic-Migration: Tabelle `website_primo_konto`.

Was diese Migration tut
-----------------------
1. Legt die Tabelle `website_primo_konto` an: `user` (PK, Diakronos-Username),
   `primo_id` (UNIQUE, PocketBase-`users.id`), `email`, `angelegt_am`.
2. Aendert KEINE Daten. Die Zuordnung entsteht beim ersten Login ueber den
   Endpunkt (`website/primo.py::konto_sicherstellen`); eine Migration, die
   Konten nach Adressgleichheit verknuepft, waere genau die Uebernahme, die
   WEB-1b abschafft.

Idempotent
----------
`upgrade` legt die Tabelle nur an, wenn sie fehlt, und ergaenzt den
Unique-Index `uq_website_primo_konto_primo_id` nur, wenn er fehlt (der
Constraint aus `create_table` heisst je nach Datenbank anders; der Index
macht den Schutz auf PostgreSQL und SQLite gleich). `downgrade` entfernt
Index und Tabelle; ein fehlender Index ist kein Fehler.

Einziger Head
-------------
`down_revision = "web1_website_moderator"` — die Kette hat genau einen Kopf.

Revision ID: web1b_primo_konto
Revises: web1_website_moderator
Create Date: 2026-10-30
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "web1b_primo_konto"
down_revision: Union[str, None] = "web1_website_moderator"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABELLE = "website_primo_konto"
INDEX_PRIMO_ID = "uq_website_primo_konto_primo_id"


def _hat_tabelle(bind, name: str) -> bool:
    """Case-insensibler Tabellentest (Frappe legt klein an, Modelle schreiben gross)."""
    insp = sa.inspect(bind)
    namen = {
        str(k).lower()
        for k in insp.get_table_names() + insp.get_table_names(schema="public")
    }
    return str(name).lower() in namen


def _hat_index(bind, tabelle: str, index: str) -> bool:
    insp = sa.inspect(bind)
    for kandidat in insp.get_table_names() + insp.get_table_names(schema="public"):
        if str(kandidat).lower() != str(tabelle).lower():
            continue
        if any(
            str(ix.get("name") or "").lower() == str(index).lower()
            for ix in insp.get_indexes(str(kandidat))
        ):
            return True
    return False


def upgrade() -> None:
    bind = op.get_bind()

    if not _hat_tabelle(bind, TABELLE):
        op.create_table(
            TABELLE,
            sa.Column("user", sa.String(length=140), nullable=False),
            sa.Column("primo_id", sa.String(length=140), nullable=False),
            sa.Column("email", sa.String(length=320), nullable=False),
            sa.Column(
                "angelegt_am",
                sa.DateTime(timezone=False),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.PrimaryKeyConstraint("user"),
        )

    if not _hat_index(bind, TABELLE, INDEX_PRIMO_ID):
        op.create_index(INDEX_PRIMO_ID, TABELLE, ["primo_id"], unique=True)


def downgrade() -> None:
    bind = op.get_bind()
    if not _hat_tabelle(bind, TABELLE):
        return
    if _hat_index(bind, TABELLE, INDEX_PRIMO_ID):
        op.drop_index(INDEX_PRIMO_ID, table_name=TABELLE)
    op.drop_table(TABELLE)
