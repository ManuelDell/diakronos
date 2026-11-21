"""CHAT-11a: Volltextsuche über Chat-Nachrichten (PostgreSQL GIN-Index).

Revision ID: chat11a_suche
Revises: chat10a_push
Create Date: 2026-11-20

Konzept ``docs/konzepte/CHAT-KONZEPT.md`` S4 (Zeile „Suche“): „Volltext über
die Nachrichten, die man lesen darf; PostgreSQL ``tsvector`` + deutscher
Konfiguration, Ergebnis mit Sprung in den Verlauf. Kein Elasticsearch.“
Karte CHAT-11a (nur Backend).

EINE ÄNDERUNG, keine zweite
---------------------------
Ein **GIN-Ausdrucksindex** über
``to_tsvector('german', coalesce(chat_nachricht.text, ''))``:

* KEINE neue Spalte, KEIN Trigger, KEINE Datenänderung — der Index rechnet
  den Vektor aus dem vorhandenen Text. Damit kann er nicht veralten.
* Der Ausdruck ist ``IMMUTABLE`` (``to_tsvector(regconfig, text)``), also
  indexierbar — anders als die Ein-Argument-Fassung, die von
  ``default_text_search_config`` abhinge.
* ``coalesce`` ist nötig, obwohl ``text`` ``NOT NULL`` ist: der Ausdruck muss
  ZEICHENGLEICH derselbe sein, den ``api.chat`` in der ``WHERE``-Klausel
  benutzt, sonst greift der Index nicht.
* ``text`` deckt sich mit dem, was ``verlauf``/``_darf_lesen`` ausliefern —
  die Rechte entscheidet weiterhin die Suchabfrage, nicht der Index.

Auf SQLite passiert NICHTS: die Tests laufen dort (``LIKE``-Rückfall in
``api.chat``), und SQLite kennt weder ``to_tsvector`` noch GIN. ``upgrade``
prüft deshalb den Dialekt UND den Ist-Zustand (Index vorhanden?) — zweimal
anwenden ändert nichts.

``downgrade`` entfernt NUR den Index. Kein Wissen geht verloren (der Index
ist eine Ableitung des Textes); er wird still weggelassen, wenn er fehlt.

Revision-Kette
--------------
Kopf beim Schreiben war ``chat9a_erwaehnung`` — geprüft über
``alembic/versions/*.py`` (alle ``revision``/``down_revision``-Paare
ausgewertet, NICHT angenommen). Der neue Kopf ist diese Revision; es gibt
weiterhin genau EINEN (``test_dsgvo1d_alembic_kette``).

Beim Zusammenführen mit ``rechte-vorladen`` (CHAT-PERF-1) standen
vorübergehend ZWEI Köpfe nebeneinander: ``chat10a_push`` (Web-Push) hing
ebenfalls an ``chat9a_erwaehnung``. Diese Revision hängt deshalb hinter
``chat10a_push`` — die Kette bleibt eine Linie, der Suchindex kommt als
LETZTER Schritt dazu (er berührt ``chat_nachricht`` unabhängig von der
Push-Tabelle).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "chat11a_suche"
down_revision: Union[str, None] = "chat10a_push"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABELLE = "chat_nachricht"
INDEX = "ix_chat_nachricht_tsv"
#: Der Ausdruck, den ``api.chat.NACHRICHT_TSVECTOR`` (bzw. die SQL-Abfrage)
#: zeichengleich benutzt — EINE Form, zwei Stellen.
AUSDRUCK = "to_tsvector('german', coalesce(text, ''))"


def _ist_postgresql() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def _index_existiert() -> bool:
    insp = sa.inspect(op.get_bind())
    try:
        namen = {str(i.get("name") or "") for i in insp.get_indexes(TABELLE)}
    except Exception:  # noqa: BLE001 — Tabelle fehlt/sperrt ⇒ es gibt ihn nicht
        return False
    return INDEX in namen


def upgrade() -> None:
    if not _ist_postgresql():
        # SQLite (Tests, Entwicklung): der Suchweg läuft dort über LIKE.
        return
    if _index_existiert():
        return
    op.execute(
        sa.text(f"CREATE INDEX {INDEX} ON {TABELLE} USING gin ({AUSDRUCK})")
    )


def downgrade() -> None:
    if not _ist_postgresql():
        return
    if not _index_existiert():
        return
    op.execute(sa.text(f"DROP INDEX {INDEX}"))
