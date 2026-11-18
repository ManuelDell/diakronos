"""CHAT-6: Tabelle ``chat_meldung`` (Melden + Moderation).

Revision ID: chat6_meldung
Revises: chat2_chat_s1
Create Date: 2026-11-18

Konzept ``docs/konzepte/CHAT-KONZEPT.md`` Abschnitt 2.5 (Melde- und
Löschfunktion), 3.3 (Entwurf ``chat_meldung``), 4.5 und 9 (F7: Meldestelle für
Direktnachrichten = nur der Administrator). Karte CHAT-6-API.

Angelegt wird GENAU EINE Tabelle:

    chat_meldung   name (PK), nachricht (FK chat_nachricht), melder (FK user,
                   Konto), grund (festes Set der API), freitext (≤ 500),
                   stand (offen/erledigt/verworfen), bearbeitet_von (FK user),
                   bearbeitet_am, entscheidung_grund, erstellt_am

Zwei Indizes tragen die beiden Zusagen:

  * ``uq_chat_meldung_offen`` — EINE OFFENE Meldung je (nachricht, melder).
    PARTIELL (``stand = 'offen'``): nach einer Entscheidung darf dieselbe
    Person dieselbe Nachricht erneut melden. Ein voller Unique-Constraint
    würde das dauerhaft verbieten (dasselbe Muster wie ``chat2_chat_s1``).
  * ``ix_chat_meldung_stand`` — die Moderationsliste liest „alle offenen“
    in der Reihenfolge des Eingangs.

Revision-Kette: Kopf auf main war ``chat2_chat_s1`` (geprüft über
``alembic/versions/*.py`` — alle ``revision``/``down_revision``-Paare
ausgewertet, NICHT angenommen). ``alembic upgrade head`` im Entrypoint braucht
genau einen Kopf; dieser hier ist der neue.

Idempotent: die Tabelle wird nur angelegt, wenn sie fehlt, die Indizes nur,
wenn sie fehlen. ``downgrade`` entfernt die Indizes mit der Tabelle.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "chat6_meldung"
down_revision: Union[str, None] = "chat2_chat_s1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _tabelle_existiert(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def _indizes(tabelle: str) -> set[str]:
    """Namen der vorhandenen Indizes — ein zweiter Lauf darf nichts doppeln."""
    return {str(i["name"]) for i in sa.inspect(op.get_bind()).get_indexes(tabelle)}


def upgrade() -> None:
    if not _tabelle_existiert("chat_meldung"):
        op.create_table(
            "chat_meldung",
            sa.Column("name", sa.String(length=140), primary_key=True),
            sa.Column("nachricht", sa.String(length=140), nullable=False),
            # Konto der meldenden Person — `user_null` in dsgvo_anonymisierung.
            sa.Column("melder", sa.String(length=140), nullable=True),
            # Einer der fünf Schlüssel aus `models.chat.MELDEGRUENDE`; geprüft
            # wird im Endpunkt (einziger Schreibweg).
            sa.Column("grund", sa.String(length=40), nullable=False),
            sa.Column("freitext", sa.Text(), nullable=True),
            sa.Column("stand", sa.String(length=20), nullable=False,
                      server_default=sa.text("'offen'")),
            sa.Column("bearbeitet_von", sa.String(length=140), nullable=True),
            sa.Column("bearbeitet_am", sa.DateTime(), nullable=True),
            sa.Column("entscheidung_grund", sa.Text(), nullable=True),
            sa.Column("erstellt_am", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(
                ["nachricht"], ["chat_nachricht.name"],
                name="fk_chat_meldung_nachricht_chat_nachricht",
            ),
            sa.ForeignKeyConstraint(
                ["melder"], ["user.name"], name="fk_chat_meldung_melder_user",
            ),
            sa.ForeignKeyConstraint(
                ["bearbeitet_von"], ["user.name"],
                name="fk_chat_meldung_bearbeitet_von_user",
            ),
        )

    vorhanden = _indizes("chat_meldung")
    if "uq_chat_meldung_offen" not in vorhanden:
        # EINE OFFENE Meldung je (nachricht, melder) — partiell, damit nach
        # einer Entscheidung eine erneute Meldung möglich bleibt.
        op.create_index(
            "uq_chat_meldung_offen", "chat_meldung", ["nachricht", "melder"],
            unique=True, postgresql_where=sa.text("stand = 'offen'"),
            sqlite_where=sa.text("stand = 'offen'"),
        )
    if "ix_chat_meldung_stand" not in vorhanden:
        op.create_index(
            "ix_chat_meldung_stand", "chat_meldung", ["stand", "erstellt_am"],
        )


def downgrade() -> None:
    # Die Indizes fallen mit der Tabelle (Alembic entfernt sie mit `drop_table`).
    if _tabelle_existiert("chat_meldung"):
        op.drop_table("chat_meldung")
