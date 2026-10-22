"""BF1c/W6: Dashboard-Kachel »Zu moderierende Termine« zeigt echte Vorschlaege.

Revision ID: bf1c_moderation_widget
Revises: dm1_devmodus
Create Date: 2026-10-15

Befund (Code-Review R-BF1b, W6): Die Kachel hing an
``ressource_api.get_conflict_events`` — das sind Ressourcen-Doppelbelegungen aus
allen Terminen (jeder Status, auch vergangene), sortiert nach Ressource. Das ist
NICHT die Moderationswarteschlange: ein frisch angelegter Vorschlag erschien dort
nie, obwohl Titel und Sprungziel »Zur Terminmoderation« das Gegenteil versprechen.

Diese Migration zeigt die System-Zeile ``pending-registrations`` auf den neuen
Endpunkt ``dashboard.get_moderation_vorschlaege``, der genau die offenen
Vorschlaege der moderierten Kalender liefert (nach Start sortiert, Vergangenes
ausgeblendet).

Idempotent: laeuft auf frischer UND bestehender DB sauber; beruehrt nur die
System-Zeile mit genau dieser ``widget_id``. ``downgrade`` stellt den alten
Zeiger wieder her. Falls die Zeile fehlt (frische Installation ohne Fixture),
passiert nichts — der Fixture-Seed setzt sie ohnehin schon korrekt.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "bf1c_moderation_widget"
down_revision: Union[str, None] = "dm1_devmodus"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

WIDGET_ID = "pending-registrations"
NEU = "diakronos.diakonos.api.dashboard.get_moderation_vorschlaege"
ALT = "diakronos.kronos.api.ressource_api.get_conflict_events"


def _tabelle_existiert(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def _zeiger_setzen(ziel: str) -> None:
    if not _tabelle_existiert("dashboard_widget"):
        return
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "UPDATE dashboard_widget SET api_method = :m, modified = now()"
            " WHERE widget_id = :w"
        ),
        {"m": ziel, "w": WIDGET_ID},
    )


def upgrade() -> None:
    # Nur umsetzen, wenn die Zeile noch NICHT auf dem neuen Endpunkt steht —
    # so ist der Lauf auf einer frischen DB (Fixture bereits korrekt) ein No-op.
    _zeiger_setzen(NEU)


def downgrade() -> None:
    _zeiger_setzen(ALT)
