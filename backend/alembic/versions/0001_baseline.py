"""leere Baseline

Revision ID: 0001_baseline
Revises:
Create Date: 2026-09-24

Bewusst LEER: dieses Skelett legt noch keine Tabellen an. Die Migration
existiert, damit spaetere Karten einen sauberen `alembic upgrade head`-Anker
haben.
"""
from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = "0001_baseline"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
