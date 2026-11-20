"""CHAT-9a: Erwähnungen (@Name) an einer Nachricht.

Revision ID: chat9a_erwaehnung
Revises: chat7b_runden
Create Date: 2026-11-20

Konzept ``docs/konzepte/CHAT-KONZEPT.md`` S4 (Zeile „Erwähnung“): „die
erwähnte Person bekommt eine **eigene** Glocke (nicht gebündelt), nicht aber
eine Mail“. Karte CHAT-9a (Backend; Anhänge und Suche sind NICHT Teil dieser
Karte).

EINE ÄNDERUNG, keine zweite:

  ``chat_erwaehnung`` (NEUE Tabelle) — ``nachricht, mitglied, angelegt_am``.
  Primärschlüssel ``(nachricht, mitglied)``: EINE Erwähnung je Nachricht und
  Person (Duplikate verwirft schon der Endpunkt; der Schlüssel macht es
  unumstößlich). ``nachricht`` trägt ``ON DELETE CASCADE``: eine ENDGÜLTIG
  gelöschte Nachricht (CHAT-8-Aufbewahrung) nimmt ihre Erwähnungen mit. Das
  SOFT-Delete räumt sie vorher über ``api.chat.loeschen`` ab — die Glocke
  hängt dann nicht mehr an einer Lücke. ``mitglied`` ist eine MITGLIED-Kennung
  OHNE FK, dieselbe Form wie ``chat_runde_vorschlag.mitglied``; die
  Anonymisierung (Art. 17) räumt die Zeile ab (``dsgvo_anonymisierung``:
  ``ZEILEN_LOESCHEN``).

  Zwei Indizes: ``ix_chat_erwaehnung_nachricht`` („wer ist auf dieser
  Verlaufsseite erwähnt?“ — EIN Abruf je Seite) und
  ``ix_chat_erwaehnung_mitglied`` (Glocken dieser Person beim Lesen).

Kein DDL an bestehenden Tabellen, KEINE neue Spalte: die Glocke selbst steht
im vorhandenen ``Notification Log`` (``benachrichtigungen.glocke_setzen``),
getrennt von der gebündelten Gesprächs-Glocke über einen EIGENEN
``document_type`` (``api.chat.CHAT_ERWAEHNUNG_GLOCKE_DOCTYPE``). Der Merker
``chat_glocke`` bleibt unberührt — die Erwähnungs-Glocke wird nicht gebündelt
und nicht fortgeschrieben.

Revision-Kette: Kopf beim Schreiben war ``chat7b_runden`` — geprüft über
``alembic/versions/*.py`` (alle ``revision``/``down_revision``-Paare
ausgewertet, NICHT angenommen). Der neue Kopf ist diese Revision; es gibt
weiterhin genau EINEN.

Idempotent: ``upgrade`` prüft zuerst den Ist-Zustand (Tabelle vorhanden?
Index vorhanden?). ``downgrade`` entfernt die Tabelle; sie trägt kein Wissen,
das woanders fehlt (Text der Nachricht und Glocken bleiben, letztere ohne den
``document_type`` dieser Karte — bewusst laut: erst prüfen, dann anfassen).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "chat9a_erwaehnung"
down_revision: Union[str, None] = "chat7b_runden"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABELLE = "chat_erwaehnung"
NACHRICHT = "chat_nachricht"
INDEX_NACHRICHT = "ix_chat_erwaehnung_nachricht"
INDEX_MITGLIED = "ix_chat_erwaehnung_mitglied"


def _tabelle_existiert(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def _indizes(tabelle: str) -> set[str]:
    return {str(i["name"]) for i in sa.inspect(op.get_bind()).get_indexes(tabelle)}


def upgrade() -> None:
    if not _tabelle_existiert(TABELLE):
        op.create_table(
            TABELLE,
            sa.Column("nachricht", sa.String(length=140),
                      sa.ForeignKey(f"{NACHRICHT}.name", ondelete="CASCADE"),
                      primary_key=True),
            sa.Column("mitglied", sa.String(length=140), primary_key=True),
            sa.Column("angelegt_am", sa.DateTime(), nullable=False),
        )
    indizes = _indizes(TABELLE) if _tabelle_existiert(TABELLE) else set()
    if INDEX_NACHRICHT not in indizes:
        op.create_index(INDEX_NACHRICHT, TABELLE, ["nachricht"])
    if INDEX_MITGLIED not in indizes:
        op.create_index(INDEX_MITGLIED, TABELLE, ["mitglied"])


def downgrade() -> None:
    # Laut und früh: gibt es Erwähnungen, verschwände mit der Tabelle auch die
    # Spur, wer gemeint war — die Glocken dazu blieben aber stehen. Erst
    # leeren (oder bewusst löschen), dann zurücknehmen.
    if not _tabelle_existiert(TABELLE):
        return
    anzahl = op.get_bind().execute(
        sa.text(f"SELECT count(*) FROM {TABELLE}")
    ).scalar_one()
    if anzahl:
        raise RuntimeError(
            "Rücknahme nicht möglich: es gibt Erwähnungen "
            f"({anzahl} Zeile(n)). Erst leeren, dann downgrade."
        )
    op.drop_table(TABELLE)
