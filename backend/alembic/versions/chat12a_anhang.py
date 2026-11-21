"""CHAT-12a: Anhänge an Chat-Nachrichten (über das Speicher-Backend SPEICHER-1).

Revision ID: chat12a_anhang
Revises: chat11a_suche
Create Date: 2026-11-20

Konzept ``docs/konzepte/CHAT-KONZEPT.md`` S4 (Zeile „Anhänge“) und F11: „Anhänge
erst mit SPEICHER-1“. Karte CHAT-12a (Backend; Vorschaubilder und Frontend sind
NICHT Teil dieser Karte).

EINE ÄNDERUNG, keine zweite:

  ``chat_anhang`` (NEUE Tabelle) — ``name`` (PK), ``nachricht`` (FK, NULL solange
  offen), ``gespraech`` (FK), ``schluessel``, ``dateiname``, ``mime``,
  ``groesse``, ``angelegt_am``, ``angelegt_von`` (Konto).

  ``nachricht`` trägt ``ON DELETE CASCADE``: eine ENDGÜLTIG gelöschte Nachricht
  (CHAT-8-Aufbewahrung) nimmt ihre Anhang-Zeilen mit. Die DATEI räumt der
  Löschweg vorher über die Ablage ab (``api.chat``/``chat_aufbewahrung``/
  ``dsgvo_anonymisierung`` — nach dem Commit, damit ein Rollback keine Datei
  gelöscht hat). ``angelegt_von`` ist ein Konto-Verweis mit ``ON DELETE SET
  NULL``: das Konto verschwindet, die Anhang-Zeile fällt über die DSGVO
  (``ZEILEN_LOESCHEN``) — der SET NULL ist nur der Netz darunter.

  ``gespraech`` steht neben ``nachricht``, weil der Upload das Gespräch braucht,
  bevor es eine Nachricht gibt (Rechtefrage und Tagesgrenze je Person).

  Drei Indizes: ``ix_chat_anhang_nachricht`` („Anhänge dieser Verlaufsseite“ —
  EIN Abruf je Seite, kein N+1), ``ix_chat_anhang_angelegt_von_am`` (Tagesgrenze
  je Person und Aufräumen offener Anhänge) und ``ix_chat_anhang_gespraech``.

Kein DDL an bestehenden Tabellen, KEINE neue Spalte: die Ablage bleibt die
vorhandene (``diakronos_app.speicher``), es entsteht kein zweiter Speicherweg.

Revision-Kette: Kopf beim Schreiben war ``chat9a_erwaehnung``; seit dem Merge
des Web-Push-Zweigs (``fix-10a2``, Sammel 8) hängt dieser hier an
``chat10a_push``; in Sammel 9 (Zusammenführen mit CHAT-11a) hängt er hinter
``chat11a_suche``, damit die Kette EINE Linie bleibt — geprüft über
``alembic/versions/*.py`` (alle ``revision``/``down_revision``-Paare
ausgewertet, NICHT angenommen). Der neue
Kopf ist ``chat12a_entsorgung`` (Entsorgungsliste + Hochlade-Marken); es gibt
weiterhin genau EINEN.

Idempotent: ``upgrade`` prüft zuerst den Ist-Zustand (Tabelle vorhanden? Index
vorhanden?). ``downgrade`` entfernt die Tabelle; die DATEIEN in der Ablage
bleiben dabei absichtlich stehen — sie sind ohne ihre Zeile nicht mehr
erreichbar und werden vom Aufräumlauf der Ablage bzw. vom Betrieb entfernt;
laut und früh wird abgewiesen, solange noch Zeilen existieren (erst leeren,
dann zurücknehmen).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "chat12a_anhang"
down_revision: Union[str, None] = "chat11a_suche"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABELLE = "chat_anhang"
INDEX_NACHRICHT = "ix_chat_anhang_nachricht"
INDEX_KONTO = "ix_chat_anhang_angelegt_von_am"
INDEX_GESPRAECH = "ix_chat_anhang_gespraech"


def _tabelle_existiert(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def _indizes(tabelle: str) -> set[str]:
    return {str(i["name"]) for i in sa.inspect(op.get_bind()).get_indexes(tabelle)}


def upgrade() -> None:
    if not _tabelle_existiert(TABELLE):
        op.create_table(
            TABELLE,
            sa.Column("name", sa.String(length=140), primary_key=True),
            sa.Column(
                "nachricht",
                sa.String(length=140),
                sa.ForeignKey("chat_nachricht.name", ondelete="CASCADE"),
                nullable=True,
            ),
            sa.Column(
                "gespraech",
                sa.String(length=140),
                sa.ForeignKey("chat_gespraech.name"),
                nullable=False,
            ),
            sa.Column("schluessel", sa.String(length=255), nullable=False),
            sa.Column("dateiname", sa.String(length=120), nullable=False),
            sa.Column("mime", sa.String(length=60), nullable=False),
            sa.Column("groesse", sa.Integer(), nullable=False),
            sa.Column("angelegt_am", sa.DateTime(), nullable=False),
            sa.Column(
                "angelegt_von",
                sa.String(length=140),
                sa.ForeignKey("user.name", ondelete="SET NULL"),
                nullable=True,
            ),
        )
    indizes = _indizes(TABELLE) if _tabelle_existiert(TABELLE) else set()
    if INDEX_NACHRICHT not in indizes:
        op.create_index(INDEX_NACHRICHT, TABELLE, ["nachricht"])
    if INDEX_KONTO not in indizes:
        op.create_index(INDEX_KONTO, TABELLE, ["angelegt_von", "angelegt_am"])
    if INDEX_GESPRAECH not in indizes:
        op.create_index(INDEX_GESPRAECH, TABELLE, ["gespraech"])


def downgrade() -> None:
    # Laut und früh: mit der Tabelle verschwände die Spur, welche Datei zu
    # welcher Nachricht gehört — die Dateien selbst blieben in der Ablage
    # liegen, ohne dass jemand sie noch zuordnen könnte. Erst leeren (und die
    # Dateien bewusst entfernen), dann zurücknehmen.
    if not _tabelle_existiert(TABELLE):
        return
    anzahl = op.get_bind().execute(
        sa.text(f"SELECT count(*) FROM {TABELLE}")
    ).scalar_one()
    if anzahl:
        raise RuntimeError(
            "Rücknahme nicht möglich: es gibt Anhänge "
            f"({anzahl} Zeile(n)). Erst leeren, dann downgrade."
        )
    op.drop_table(TABELLE)
