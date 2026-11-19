"""CHAT-4a: Tabelle ``chat_glocke`` (gebündelte Chat-Glocke).

Revision ID: chat4a_glocke
Revises: chat5_umfrage
Create Date: 2026-11-18

Konzept ``docs/konzepte/CHAT-KONZEPT.md`` Abschnitt 1/S1 („eine In-App-Meldung
(Glocke) gebündelt: ‚Chor: 3 neue Nachrichten' nach 5 Minuten Ruhe, nicht je
Nachricht“; „Stumm schalten je Person je Gespräch: keine Glocke mehr, Zähler
bleibt“), 3.1 (Zustellung) und 4.5 (was NICHT gespeichert wird). Karte CHAT-4a.

Angelegt wird GENAU EINE Tabelle:

    chat_glocke   PK (gespraech, benutzer)
                  stand, stand_am, stand_nachricht   — Anker (Lesestand beim
                                                        Glocken bzw. Beitritt)
                  merker_am                           — neueste schon geglockte
                                                        Nachricht
                  geglockt_am, gelesen_am

Der Merker ist der Grund für die Tabelle: er verhindert, dass der
1–2‑Minuten-Job dieselbe Nachricht mehrfach glockt, und er sagt, AB WANN das
nächste Bündel zählt. Er ist KEIN Lesestand — dieser bleibt
``chat_teilnehmer.letzter_lesestand``.

Fremdschlüssel: ``gespraech`` → ``chat_gespraech``, ``benutzer`` → ``user``,
``stand`` → ``chat_nachricht`` **ON DELETE SET NULL** (Review R1/f: CHAT-8
löscht Nachrichten; der Merker darf dabei nicht mitgerissen werden — die
Zeitangabe ``stand_am`` bleibt, deshalb ist ``stand`` entbehrlich).
``stand_nachricht`` ist bewusst KEIN Fremdschlüssel (reine Kopie der Kennung).

Revision-Kette: Kopf auf main war ``chat6_meldung`` (geprüft über
``alembic/versions/*.py`` — alle ``revision``/``down_revision``-Paare
ausgewertet, NICHT angenommen). ``alembic upgrade head`` im Entrypoint braucht
genau einen Kopf; dieser hier ist der neue.

Idempotent in beide Richtungen: die Tabelle wird nur angelegt, wenn sie fehlt;
fehlende Spalten und Indizes werden ergänzt, wenn die Tabelle schon steht
(so kommt eine Datenbank, die die erste Fassung dieser Migration bereits
angewandt hat, ohne Handarbeit auf den Stand). ``downgrade`` entfernt den
Index mit der Tabelle — es bleibt nichts zurück, was ein erneutes ``upgrade``
stören könnte (up/down/up).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "chat4a_glocke"
down_revision: Union[str, None] = "chat5_umfrage"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _tabelle_existiert(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def _indizes(tabelle: str) -> set[str]:
    """Namen der vorhandenen Indizes — ein zweiter Lauf darf nichts doppeln."""
    return {str(i["name"]) for i in sa.inspect(op.get_bind()).get_indexes(tabelle)}


def _spalten(tabelle: str) -> set[str]:
    return {str(c["name"]) for c in sa.inspect(op.get_bind()).get_columns(tabelle)}


def upgrade() -> None:
    if not _tabelle_existiert("chat_glocke"):
        op.create_table(
            "chat_glocke",
            sa.Column("gespraech", sa.String(length=140), primary_key=True),
            # Konto der Person — `user_null`/`zeile_loeschen` in
            # dsgvo_anonymisierung.
            sa.Column("benutzer", sa.String(length=140), primary_key=True),
            # Anker: Lesestand beim Glocken (bzw. Beitritt) — Kennung und
            # Zeitstempel getrennt, weil `stand` bei einer Löschung der
            # Nachricht NULL wird (ON DELETE SET NULL).
            sa.Column("stand", sa.String(length=140), nullable=True),
            sa.Column("stand_am", sa.DateTime(), nullable=True),
            sa.Column("stand_nachricht", sa.String(length=140), nullable=True),
            # Die neueste Nachricht, die beim letzten Glocken schon da war.
            sa.Column("merker_am", sa.DateTime(), nullable=True),
            sa.Column("geglockt_am", sa.DateTime(), nullable=True),
            sa.Column("gelesen_am", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(
                ["gespraech"], ["chat_gespraech.name"],
                name="fk_chat_glocke_gespraech_chat_gespraech",
            ),
            sa.ForeignKeyConstraint(
                ["benutzer"], ["user.name"], name="fk_chat_glocke_benutzer_user",
            ),
            sa.ForeignKeyConstraint(
                ["stand"], ["chat_nachricht.name"],
                name="fk_chat_glocke_stand_chat_nachricht",
                ondelete="SET NULL",
            ),
        )
    else:
        # Zweite Fassung: eine Datenbank mit der ersten Fassung dieser
        # Migration bekommt die neuen Spalten hier nachgezogen.
        #
        # BEKANNTE LUECKE (CHAT-4b, Restpunkt c aus dem CHAT-4a-Review): dieser
        # Zweig baut einen in der ersten Fassung angelegten Fremdschluessel
        # ``fk_chat_glocke_stand_chat_nachricht`` NICHT auf ``ON DELETE SET
        # NULL`` um. Bewusst NICHT geaendert: ``chat4a_glocke`` kam in EINEM
        # Stueck nach main (``down_revision = chat5_umfrage``, der Kopf davor),
        # es gibt keine Datenbank, die die erste Fassung je gesehen hat — und
        # ein Umbau des FK (drop + neu) waere auf SQLite gar nicht moeglich
        # (``backend does not support ALTER``). Sollte wider Erwarten doch eine
        # Installation mit der alten Spaltenmenge auftauchen, gehoert der Umbau
        # in eine EIGENE Migration: ``ALTER TABLE … DROP CONSTRAINT`` +
        # ``ADD CONSTRAINT … ON DELETE SET NULL`` auf PostgreSQL.
        vorhanden = _spalten("chat_glocke")
        if "stand_am" not in vorhanden:
            op.add_column("chat_glocke", sa.Column("stand_am", sa.DateTime(), nullable=True))
        if "stand_nachricht" not in vorhanden:
            op.add_column("chat_glocke",
                          sa.Column("stand_nachricht", sa.String(length=140), nullable=True))
        if "merker_am" not in vorhanden:
            op.add_column("chat_glocke", sa.Column("merker_am", sa.DateTime(), nullable=True))

    if "ix_chat_glocke_gespraech" not in _indizes("chat_glocke"):
        op.create_index("ix_chat_glocke_gespraech", "chat_glocke", ["gespraech"])
    # Review R1 (MUSS 2): der Job steigt über den Merker in die Paare ein.
    if "ix_chat_glocke_benutzer" not in _indizes("chat_glocke"):
        op.create_index("ix_chat_glocke_benutzer", "chat_glocke", ["benutzer"])


def downgrade() -> None:
    # Der Index fällt mit der Tabelle (Alembic entfernt ihn mit `drop_table`).
    if _tabelle_existiert("chat_glocke"):
        op.drop_table("chat_glocke")
