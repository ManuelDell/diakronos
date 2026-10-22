"""P1-14: geltende Sonne/Regen-Variante je Termin (OP-EVENT-18).

Revision ID: p14_termin_variante
Revises: p11_termindaenderung
Create Date: 2026-10-17

Befund OP-EVENT-18: Bei einer Freizeit mit Sonne/Regen-Varianten liess sich
die je Tag geltende Variante nicht festlegen — der Umschalter im Raster wirkte
nur im eigenen Browser und war nach dem Neuladen wieder auf der ersten
Variante; zudem war der aktive Knopf optisch nicht zu unterscheiden.

Diese Migration legt ``pr_termin.variante`` an: die je Termin gueltige
Variantenkennung (z. B. ``sonne``/``regen``). Leer (NULL) heisst „es gilt die
erste deklarierte Variante“ — das bisherige Verhalten bleibt damit Standard.

Idempotent: ``upgrade`` fuegt die Spalte nur hinzu, wenn sie fehlt; laeuft auf
frischer UND bestehender DB sauber. ``downgrade`` entfernt sie wieder.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "p14_termin_variante"
# Auf den AKTUELLEN main-Kopf aufsetzen. `p15b_ablehnungsgrund` (P1-5b) und
# diese Migration zweigten sonst BEIDE von `p11_termindaenderung` ab — das
# ergaebe ZWEI Alembic-Koepfe und `alembic upgrade head` schluege fehl.
down_revision: Union[str, None] = "p15b_ablehnungsgrund"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABELLE = "pr_termin"
SPALTE = "variante"


def _spalten() -> set[str]:
    bind = op.get_bind()
    return {c["name"] for c in sa.inspect(bind).get_columns(TABELLE)}


def upgrade() -> None:
    if SPALTE in _spalten():
        return
    op.add_column(TABELLE, sa.Column(SPALTE, sa.String(length=140), nullable=True))


def downgrade() -> None:
    if SPALTE not in _spalten():
        return
    op.drop_column(TABELLE, SPALTE)
