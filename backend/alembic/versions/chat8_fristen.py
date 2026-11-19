"""CHAT-8: Aufbewahrungsfristen des Chats je Gemeinde.

Revision ID: chat8_fristen
Revises: chat4a_glocke
Create Date: 2026-11-19

Konzept ``docs/konzepte/CHAT-KONZEPT.md`` 4.2 (Tabelle Fristen), 4.3 und die
Entscheidung **F8** (Abschnitt 9): *„Aufbewahrungsfristen pro Gemeinde
einstellbar (Einstellung des Administrators), Standard 24 Monate Gruppe / 12
Monate Direkt; Loeschung automatisch.“* Karte CHAT-8.

Angelegt werden ZWEI Spalten an der BESTEHENDEN Gemeinde-Single
``gemeinde_einstellungen`` (Tabelle aus ``n9_gemeinde``):

    chat_frist_gruppe_monate   Integer, NULL erlaubt — Standard 24
    chat_frist_direkt_monate   Integer, NULL erlaubt — Standard 12

Beide sind NULLBAR und tragen KEINEN ``server_default``: NULL heisst „noch nie
eingestellt“ und der Code nimmt dann den Standard (``chat_aufbewahrung
.FRIST_STANDARD``). Damit ist die Reihenfolge von Migration und Anwendung egal,
und ein spaeterer Standardwechsel braucht keine Datenmigration. Die Grenzen
(1–120 Monate) prueft ``chat_aufbewahrung._pruefe_monate`` fuer Endpunkt UND
Scheduler — die Datenbank muss sie nicht kennen.

Die Spalten gehoeren bewusst an die Gemeinde-Single und nicht in eine eigene
Tabelle: es gibt genau eine Gemeinde, die Frist ist eine Einstellung wie
``link_laufzeit_tage`` daneben, und ein zweiter Einstellungs-Speicher waere
eine zweite Wahrheit ueber dieselbe Frage.

Revision-Kette: Kopf auf main war ``chat5_umfrage``; CHAT-4a bringt
``chat4a_glocke`` direkt dahinter (``chat5_umfrage -> chat4a_glocke``), deshalb
steht ``down_revision`` hier auf ``chat4a_glocke`` (geprueft ueber
``alembic/versions/*.py`` — alle ``revision``/``down_revision``-Paare
ausgewertet, NICHT angenommen). ``alembic upgrade head`` im Entrypoint braucht
genau einen Kopf; dieser hier ist der neue.

Idempotent: jede Spalte wird nur ergaenzt, wenn sie fehlt (eine Datenbank, die
diese Migration schon angewandt hat, bleibt unveraendert stehen).
``downgrade`` entfernt beide Spalten — danach liest der Code wieder die
Standardwerte, es geht kein Fachdatum verloren (die Frist ist eine Einstellung,
kein Beleg).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "chat8_fristen"
down_revision: Union[str, None] = "chat4a_glocke"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABELLE = "gemeinde_einstellungen"
SPALTEN = ("chat_frist_gruppe_monate", "chat_frist_direkt_monate")


def _spalte_existiert(tabelle: str, spalte: str) -> bool:
    insp = sa.inspect(op.get_bind())
    if not insp.has_table(tabelle):
        return False
    return spalte in {s["name"] for s in insp.get_columns(tabelle)}


def upgrade() -> None:
    for spalte in SPALTEN:
        if not _spalte_existiert(TABELLE, spalte):
            op.add_column(TABELLE, sa.Column(spalte, sa.Integer(), nullable=True))


def downgrade() -> None:
    for spalte in SPALTEN:
        if _spalte_existiert(TABELLE, spalte):
            op.drop_column(TABELLE, spalte)
