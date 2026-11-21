"""Rechte: Chat-Modul für alle bestehenden Gruppen einschalten.

Revision ID: r_chat_standard
Revises: chat12a2_backoff
Create Date: 2026-11-21

Manuel 17.11.: „Chat-Modul automatisch an für alle bestehenden und neuen
Gruppen — einschalten zusammen mit der Chat-Oberfläche.“ Die Oberfläche ist
seit Sammel 9 vollständig (Verlauf, Suche, Anhänge-Backend). Neue Gruppen
bekommen das Modul beim Anlegen (``rechte.verwaltung.standard_module_anlegen``,
Liste ``rechte.kern.STANDARD_MODULE``); diese Revision holt es EINMAL für den
Bestand nach.

Was geschieht: für JEDE Zeile in ``gruppe`` ohne ``rechte_modul``-Zeile
``(gruppe, 'chat')`` wird eine angelegt — auch für Gruppen im Papierkorb, damit
eine wiederhergestellte Gruppe denselben Stand hat wie jede andere
(``kern.modul_aktiv`` sieht gelöschte Gruppen ohnehin nicht). Vorhandene
Zeilen bleiben unberührt; ein Modul, das der Administrator abgeschaltet hat,
gibt es vor dieser Revision nicht (das Modul war bisher nie standardmäßig an).

Idempotent: es wird nur eingefügt, was fehlt (Unique-Index
``uq_rechte_modul_gruppe_modul``).

``downgrade`` tut NICHTS: nach dem Upgrade ist nicht mehr unterscheidbar, ob
der Administrator das Modul selbst eingeschaltet hat. Ein Zurückrollen nimmt
also keinem Gruppenchat das Recht weg (fail safe für die Daten; das Modul
lässt sich in der Oberfläche je Gruppe abschalten).

DSGVO-Inventar: keine neue Tabelle, keine Personendaten.

Ein Kopf: hängt hinter ``chat12a2_backoff``.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "r_chat_standard"
down_revision: Union[str, None] = "chat12a2_backoff"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

MODUL = "chat"


def upgrade() -> None:
    bind = op.get_bind()
    pruefer = sa.inspect(bind)
    if not (pruefer.has_table("gruppe") and pruefer.has_table("rechte_modul")):
        return
    fehlend = [
        str(name) for (name,) in bind.execute(sa.text(
            "SELECT g.name FROM gruppe g WHERE NOT EXISTS ("
            " SELECT 1 FROM rechte_modul m WHERE m.gruppe = g.name AND m.modul = :modul)"
            " ORDER BY g.name"), {"modul": MODUL})
    ]
    if not fehlend:
        return
    modul_t = sa.table("rechte_modul", sa.column("gruppe"), sa.column("modul"))
    op.bulk_insert(modul_t, [{"gruppe": g, "modul": MODUL} for g in fehlend])


def downgrade() -> None:
    # Bewusst leer — siehe Kopf.
    pass
