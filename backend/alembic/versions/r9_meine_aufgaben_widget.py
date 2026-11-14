"""R-9 (UI-R9): Startseiten-Kachel »Meine Aufgaben«.

Revision ID: r9_meine_aufgaben_widget
Revises: r7b_aufgaben_zuweisung
Create Date: 2026-11-13

Die Kacheln der Startseite kommen aus ``dashboard_widget``; ohne Zeile bleibt
eine Kachel unsichtbar (PUB-2b/B3). Die Kachel holt ihre Daten selbst
(``gruppen.get_meine_aufgaben``), deshalb kein ``api_method``. Position 14:
hinter den vorhandenen dreizehn, damit gespeicherte Nutzerreihenfolgen bleiben.

Idempotent: legt die Zeile nur an, wenn es noch keine mit dieser ``widget_id``
gibt (der Demo-Seed kann sie schon haben). ``downgrade`` entfernt nur die von
hier angelegte Zeile samt Nutzer-Einstellungen.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "r9_meine_aufgaben_widget"
down_revision: Union[str, None] = "r7b_aufgaben_zuweisung"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

WIDGET_ID = "my-tasks"
NAME = "my-tasks"


def upgrade() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table("dashboard_widget"):
        return
    vorhanden = bind.execute(
        sa.text("SELECT 1 FROM dashboard_widget WHERE widget_id = :w"), {"w": WIDGET_ID}
    ).first()
    if vorhanden:
        return
    bind.execute(
        sa.text(
            "INSERT INTO dashboard_widget (name, creation, modified, docstatus, idx, widget_id,"
            " label, widget_type, category, grid_size, default_position, default_visible,"
            " refresh_interval, enabled, is_system, empty_state_mode, empty_state_message)"
            " VALUES (:n, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 0, 0, :w, :label, 'list_card',"
            " 'personal', 'medium', 14, :ja, 60, :ja, :ja, 'show_message', :leer)"
        ),
        {"n": NAME, "w": WIDGET_ID, "label": "Meine Aufgaben", "ja": True,
         "leer": "Keine offenen Aufgaben."},
    )


def downgrade() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table("dashboard_widget"):
        return
    if sa.inspect(bind).has_table("dashboard_widget_user_config"):
        bind.execute(sa.text("DELETE FROM dashboard_widget_user_config WHERE widget = :n"),
                     {"n": NAME})
    bind.execute(sa.text("DELETE FROM dashboard_widget WHERE name = :n"), {"n": NAME})
