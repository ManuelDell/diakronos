"""ST2: Lied um Buch/Seite ergaenzen; Lied-Material (Audio/Notensatz)

Revision ID: st2_lied_material
Revises: pr4_planrahmen
Create Date: 2026-10-09

ST2 — „Lieder richtig pflegen". Zwei Ergaenzungen, die die Psalmos-Tabellen
bestehen lassen (keine Doppelstrukturen):

1. ``lied`` — zwei eingebaute Attribute der Formatvorlagen: ``buch`` (Heft)
   und ``seite`` (Heftseite). Sie existieren in der Alt-DB nicht und werden
   dort auch nicht gebraucht; im Standalone-Rahmen sind sie aber Teil der
   eingebauten Lied-Attribute (``{lied.buch}`` / ``{lied.seite}``).

2. ``lied_material`` — keine neue Tabelle: Material liegt weiterhin als
   Child-Zeilen (``art``, ``stimme``, ``anhang`` → ``sicherer_anhang``,
   ``beschreibung``). Die Material-Arten (Noten-PDF, Audio, MuseScore,
   MusicXML) sind reine Werte in ``art`` und brauchen kein Schema.
   ``sicherer_anhang.datei`` traegt die Datei-URL, ``dateiname`` den
   Anzeigenamen, ``dateityp`` den erkannten MIME-Typ.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "st2_lied_material"
down_revision: Union[str, None] = "pr4_planrahmen"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("lied", sa.Column("buch", sa.String(length=140), nullable=True))
    op.add_column("lied", sa.Column("seite", sa.String(length=140), nullable=True))


def downgrade() -> None:
    op.drop_column("lied", "seite")
    op.drop_column("lied", "buch")
