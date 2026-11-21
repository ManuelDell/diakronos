"""CHAT-12c: Anhanggröße des Chats je Gemeinde einstellbar.

Revision ID: chat12c_anhang_groesse
Revises: r_chat_standard
Create Date: 2026-11-21

Manuel 21.11.: „Lass die Anhanggröße in den Admineinstellungen einstellbar
sein.“ Konzept ``docs/konzepte/CHAT-KONZEPT.md`` S4 („10 MB je Datei“) und
Entscheidung **F9** („ein Wert“ — dieselbe Grenze gilt später auch für
Gruppendateien); Karte CHAT-12c.

Angelegt wird EINE Spalte an der BESTEHENDEN Gemeinde-Single
``gemeinde_einstellungen`` (Tabelle aus ``n9_gemeinde``):

    anhang_max_mb   Integer, NULL erlaubt — Standard 10, gültig 1…50

NULLBAR und OHNE ``server_default``: NULL heißt „noch nie eingestellt“ und der
Code nimmt dann den Standard (``models.chat.ANHANG_MAX_MB_STANDARD``). Damit ist
die Reihenfolge von Migration und Anwendung egal, und ein späterer
Standardwechsel braucht keine Datenmigration. Die Grenzen prüft
``chat_anhanggrenze._pruefe_mb`` für Endpunkt UND Upload — die Datenbank muss
sie nicht kennen.

Bauform genau wie ``chat8_fristen`` (die Fristen-Spalten daneben): eine
Einstellung an der Single, kein zweiter Einstellungs-Speicher.

Revision-Kette: der Kopf auf main (1012e16c) war ``r_chat_standard``; diese
Revision hängt direkt dahinter — LINEAR, kein Merge-Head (geprüft über
``alembic/versions/*.py``: alle ``revision``/``down_revision``-Paare
ausgewertet, NICHT angenommen). ``alembic upgrade head`` im Entrypoint braucht
genau einen Kopf; dieser hier ist der neue.

Idempotent: die Spalte wird nur ergänzt, wenn sie fehlt.
``downgrade`` entfernt sie — danach gilt wieder der Standard, es geht kein
Fachdatum verloren (eine Einstellung, kein Beleg).

DSGVO-Inventar: keine neue Tabelle, keine Personendaten (eine Zahl an der
Gemeinde-Single). Das Inventar ``dsgvo_anonymisierung.AUFBEWAHRUNG_FRISTEN``
nennt nur Fristen — hier ist keine Aufbewahrung, deshalb keine Ergänzung.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "chat12c_anhang_groesse"
down_revision: Union[str, None] = "r_chat_standard"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABELLE = "gemeinde_einstellungen"
SPALTE = "anhang_max_mb"


def _spalte_existiert(tabelle: str, spalte: str) -> bool:
    insp = sa.inspect(op.get_bind())
    if not insp.has_table(tabelle):
        return False
    return spalte in {s["name"] for s in insp.get_columns(tabelle)}


def upgrade() -> None:
    if not _spalte_existiert(TABELLE, SPALTE):
        op.add_column(TABELLE, sa.Column(SPALTE, sa.Integer(), nullable=True))


def downgrade() -> None:
    if _spalte_existiert(TABELLE, SPALTE):
        op.drop_column(TABELLE, SPALTE)
