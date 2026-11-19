"""CHAT-4b: Spalte ``chat_umfrage.erinnert_am`` (Merker der Frist-Erinnerung).

Revision ID: chat4b_umfrage_erinnerung
Revises: chat7a_direkt
Create Date: 2026-11-19

Konzept ``docs/konzepte/CHAT-KONZEPT.md`` S2 (Zeile ~91): „eine Glocke beim
Start (‚Neue Umfrage im Chor'), eine Erinnerung 24 h vor Frist an die, die noch
nicht abgestimmt haben“. Karte CHAT-4b.

Angelegt wird GENAU EINE Spalte:

    chat_umfrage.erinnert_am   Zeitpunkt der EINEN Erinnerung (``NULL`` = noch
                               nicht erinnert)

Der Merker hängt an der UMFRAGE, nicht an der Person: die Empfängerliste ist
der Rechte-Kern (wer das Gespräch lesen darf), und eine Zeile je (Umfrage,
Person) wäre ein zweiter Personenbezug für dieselbe Aussage („dir wurde
erinnert“ — das steht schon in der ``Notification Log``-Zeile). Zeitpunkt,
keine Kennung: kein neuer Personenbezug, deshalb steht bei der Spalte auch
nichts Neues im DSGVO-Inventar (das Inventar führt Textspalten; ein ``NULL``/
Zeitpunkt ohne Inhalt ist dort keine eigene Entscheidung).

Der Job ``chat_umfrage_erinnerungen`` setzt den Merker im SELBEN Vorgang wie
die Glocken — scheitert das Schreiben, bleibt er leer und der nächste Lauf
holt es nach (idempotent). Geschlossene, gelöschte und fristlose Umfragen
werden nie erinnert.

Revision-Kette: beim Bauen war der Kopf ``chat4a_glocke``; inzwischen ist
``chat8_fristen`` (Löschfristen) auf main integriert und damit der Kopf. Der
Schritt wurde beim Nachziehen von main HINTER ``chat8_fristen`` gehängt —
geprüft über ``alembic/versions/*.py`` (alle ``revision``/``down_revision``-
Paare ausgewertet, NICHT angenommen). ``alembic upgrade head`` im Entrypoint
braucht genau einen Kopf; die beiden Schritte sind unabhängig (CHAT-8 löscht
Nachrichten, hier kommt eine Spalte an ``chat_umfrage``) — die Reihenfolge ist
deshalb beliebig, aber festgelegt.

Im Sammelzweig ``int-c7a`` kam CHAT-7a (``chat7a_direkt``, Direktnachrichten)
ebenfalls hinter ``chat8_fristen``; damit es bei EINEM Kopf bleibt, hängt dieser
Schritt jetzt hinter ``chat7a_direkt``:
``… -> chat8_fristen -> chat7a_direkt -> chat4b_umfrage_erinnerung``. Auch diese
beiden Schritte sind unabhängig (7a ändert ``chat_gespraech``, hier
``chat_umfrage``).

Idempotent in beide Richtungen: die Spalte wird nur ergänzt, wenn sie fehlt;
``downgrade`` entfernt sie wieder (up/down/up läuft rund).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "chat4b_umfrage_erinnerung"
down_revision: Union[str, None] = "chat7a_direkt"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABELLE = "chat_umfrage"
SPALTE = "erinnert_am"


def _spalten(tabelle: str) -> set[str]:
    return {str(c["name"]) for c in sa.inspect(op.get_bind()).get_columns(tabelle)}


def upgrade() -> None:
    if SPALTE not in _spalten(TABELLE):
        op.add_column(TABELLE, sa.Column(SPALTE, sa.DateTime(), nullable=True))


def downgrade() -> None:
    if SPALTE in _spalten(TABELLE):
        op.drop_column(TABELLE, SPALTE)
