"""P1-5b W-1: Ablehnungsgrund am Termin (eigenes Feld statt Beschreibung).

Revision ID: p15b_ablehnungsgrund
Revises: p11_termindaenderung
Create Date: 2026-10-17

Nachtbefund (Befund W-1): Beim Ablehnen eines Terminvorschlags schrieb
`kanban_api.resolve_conflict(action="ablehnen")` den Grund in
``element.description`` — damit war er (a) Bestandteil des Nutzertextes und
(b) fuer JEDEN Leser sichtbar. Gefordert: eigener Ort, sichtbar nur fuer
Antragsteller und Moderatoren.

Diese Migration legt dafuer zwei Spalten an, nach demselben Muster wie
``ressourcen_buchung.ablehnungs_grund`` (P1-4):

  * ``element.ablehnungs_grund`` — der Text, den der Moderator eingegeben hat
  * ``element.moderiert_von``    — wer abgelehnt hat

Idempotent: ``ADD COLUMN IF NOT EXISTS``; laeuft auf frischer UND auf
bestehender DB sauber. ``downgrade`` entfernt beide Spalten wieder.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "p15b_ablehnungsgrund"
down_revision: Union[str, None] = "p11_termindaenderung"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE element ADD COLUMN IF NOT EXISTS ablehnungs_grund TEXT")
    op.execute("ALTER TABLE element ADD COLUMN IF NOT EXISTS moderiert_von VARCHAR(140)")


def downgrade() -> None:
    op.execute("ALTER TABLE element DROP COLUMN IF EXISTS moderiert_von")
    op.execute("ALTER TABLE element DROP COLUMN IF EXISTS ablehnungs_grund")
