"""CHAT-12a-2: Entsorgungsliste ohne Kopfblockade — Spalte ``naechster_versuch_am``.

Revision ID: chat12a2_backoff
Revises: chat12a_entsorgung
Create Date: 2026-11-20

EINE ÄNDERUNG (Karte CHAT-12a-2, Punkt 1):

``chat_anhang_entsorgung.naechster_versuch_am`` — der Minuten-Job nahm bisher
die 100 ÄLTESTEN Aufträge (``vorgemerkt_am``). Scheiterten 100 Schlüssel
dauerhaft (403, kaputter Pfad), waren diese 100 in jedem Lauf wieder die
Auswahl und neuere Aufträge kamen NIE dran (per Probe belegt). Jetzt wählt der
Job nur Aufträge mit ``naechster_versuch_am <= jetzt``, den frühesten zuerst;
bei einem Fehlschlag rückt der Zeitpunkt nach hinten (1, 5, 30 Minuten, danach
6 Stunden — ``api.chat.ENTSORGUNG_BACKOFF_MINUTEN``).

Die Spalte ist ``NOT NULL``: bestehende Zeilen bekommen den Wert von
``vorgemerkt_am`` („war schon fällig“) — so ist kein Alt-Auftrag durch die
Migration blockiert, und der Job verhält sich beim ersten Lauf wie vorher
(alle fälligen Aufträge, früheste zuerst).

Idempotent: ``upgrade`` prüft Spalte und Index vor dem Anlegen, ``downgrade``
prüft vor dem Entfernen.

DSGVO-Inventar: keine neue Tabelle und keine Personendaten — die Spalte
beschreibt nur, wann der Löschauftrag das nächste Mal versucht wird. Das
Inventar bleibt unverändert (``chat_anhang_entsorgung`` steht dort als
``struktur``).

Ein Kopf: Diese Revision hängt hinter ``chat12a_entsorgung``; weitere
Änderungen hängen HINTER dieser (nicht daneben).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "chat12a2_backoff"
down_revision: Union[str, None] = "chat12a_entsorgung"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ENTSORGUNG = "chat_anhang_entsorgung"
SPALTE = "naechster_versuch_am"
IDX_NAECHSTER = "ix_chat_anhang_entsorgung_naechster"


def _spalten(tabelle: str) -> set[str]:
    return {str(c["name"]) for c in sa.inspect(op.get_bind()).get_columns(tabelle)}


def _indizes(tabelle: str) -> set[str]:
    return {str(i["name"]) for i in sa.inspect(op.get_bind()).get_indexes(tabelle)}


def upgrade() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table(ENTSORGUNG):  # pragma: no cover — Kette kaputt
        raise RuntimeError(
            f"Tabelle {ENTSORGUNG!r} fehlt — die Revision 'chat12a_entsorgung' "
            "muss zuerst gelaufen sein."
        )
    if SPALTE not in _spalten(ENTSORGUNG):
        # Erst NULL-fähig anlegen, aus ``vorgemerkt_am`` füllen, dann NOT NULL:
        # drei Schritte, damit auch eine gefüllte Tabelle ohne Tabellensperre
        # für lange Zeit umgestellt wird (SQLite kann kein ADD COLUMN mit
        # DEFAULT für eine bestehende Zeile, ohne die Tabelle neu zu bauen).
        op.add_column(
            ENTSORGUNG,
            sa.Column(SPALTE, sa.DateTime(), nullable=True),
        )
        op.execute(
            sa.text(
                f"UPDATE {ENTSORGUNG} SET {SPALTE} = vorgemerkt_am "
                f"WHERE {SPALTE} IS NULL"
            )
        )
        with op.batch_alter_table(ENTSORGUNG) as batch:
            batch.alter_column(
                SPALTE,
                existing_type=sa.DateTime(),
                nullable=False,
            )
    if IDX_NAECHSTER not in _indizes(ENTSORGUNG):
        op.create_index(IDX_NAECHSTER, ENTSORGUNG, [SPALTE])


def downgrade() -> None:
    # Kein lautes Abweisen: die Spalte trägt kein Datum, das verloren ginge —
    # ein offener Auftrag bleibt offen, er ist nach der Rücknahme nur wieder
    # „sofort fällig“ (das alte Verhalten nimmt die ältesten zuerst).
    if not sa.inspect(op.get_bind()).has_table(ENTSORGUNG):  # pragma: no cover
        return
    if IDX_NAECHSTER in _indizes(ENTSORGUNG):
        op.drop_index(IDX_NAECHSTER, table_name=ENTSORGUNG)
    if SPALTE in _spalten(ENTSORGUNG):
        with op.batch_alter_table(ENTSORGUNG) as batch:
            batch.drop_column(SPALTE)
