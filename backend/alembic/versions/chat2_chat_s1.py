"""CHAT-2 (S1): Tabellen des Gruppen-/Untergruppenchats.

Revision ID: chat2_chat_s1
Revises: tg1_element_gruppe_kalender
Create Date: 2026-11-18

Konzept ``docs/konzepte/CHAT-KONZEPT.md`` Abschnitt 3.3 (Entwurf) und die
Entscheidungen Manuel 17.11.2026 (Abschnitt 9). Angelegt werden nur die vier
Tabellen der Stufe S1:

    chat_gespraech   ein Gespräch je Gruppe bzw. Untergruppe (F4: getrennt,
                     lazy beim ersten Zugriff — diese Migration legt KEINE
                     Zeilen an); die Eindeutigkeit sichern zwei PARTIELLE
                     Unique-Indizes (untergruppe IS NULL / IS NOT NULL)
    chat_teilnehmer  PK (gespraech, benutzer); `stumm` (F3), `letzter_lesestand`
                     als Spalte — keine eigene Lesestand-Tabelle (3.3)
    chat_nachricht   Index (gespraech, erstellt_am) — „neueste zuerst“ und
                     „seit X“ laufen über denselben Index; Soft-Delete-Spalten
    chat_reaktion    PK (nachricht, benutzer) — EINE Reaktion je Person

Bewusst NICHT in dieser Karte (spätere Karten): `chat_umfrage`/`chat_option`/
`chat_stimme` (S2, CHAT-5), `chat_meldung` (CHAT-6), `chat_push_abo`
(CHAT-10).

Revision-Kette: `tg1_element_gruppe_kalender` war der EINZIGE Kopf der Kette
(geprüft über `alembic/versions/*.py`, nicht angenommen). `alembic upgrade
head` im Entrypoint braucht genau einen Kopf — dieser hier ist der neue.

Idempotent: jede Tabelle wird nur angelegt, wenn sie fehlt. `downgrade`
entfernt die vier Tabellen in umgekehrter Reihenfolge (Kinder zuerst).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "chat2_chat_s1"
down_revision: Union[str, None] = "tg1_element_gruppe_kalender"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _tabelle_existiert(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def upgrade() -> None:
    if not _tabelle_existiert("chat_gespraech"):
        op.create_table(
            "chat_gespraech",
            sa.Column("name", sa.String(length=140), primary_key=True),
            # `gruppe` / `untergruppe` (S1); `direkt`/`runde` = S3 (CHAT-7).
            sa.Column("art", sa.String(length=20), nullable=False),
            sa.Column("gruppe", sa.String(length=140), nullable=False),
            sa.Column("untergruppe", sa.String(length=140), nullable=True),
            sa.Column("titel", sa.String(length=140), nullable=True),
            sa.Column("angelegt_von", sa.String(length=140), nullable=True),
            sa.Column("angelegt_am", sa.DateTime(), nullable=True),
            sa.Column("geloescht_am", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(
                ["angelegt_von"], ["user.name"],
                name="fk_chat_gespraech_angelegt_von_user",
            ),
        )
        op.create_index("ix_chat_gespraech_gruppe", "chat_gespraech", ["gruppe"])
        op.create_index("ix_chat_gespraech_untergruppe", "chat_gespraech", ["untergruppe"])
        # EIN Gespräch je Einheit — die Regel steht in der Datenbank, nicht nur
        # im Lazy-Anlegen. ZWEI PARTIELLE Indizes: ein UniqueConstraint über
        # (art, gruppe, untergruppe) griffe bei `untergruppe IS NULL` nicht
        # (NULL ist nie gleich NULL), und es könnten beliebig viele
        # Gruppen-Gespräche derselben Gruppe entstehen (Review CHAT-2, Punkt 2).
        op.create_index(
            "uq_chat_gespraech_einheit", "chat_gespraech", ["art", "gruppe"],
            unique=True, postgresql_where=sa.text("untergruppe IS NULL"),
            sqlite_where=sa.text("untergruppe IS NULL"),
        )
        op.create_index(
            "uq_chat_gespraech_einheit_ug", "chat_gespraech",
            ["art", "gruppe", "untergruppe"],
            unique=True, postgresql_where=sa.text("untergruppe IS NOT NULL"),
            sqlite_where=sa.text("untergruppe IS NOT NULL"),
        )

    if not _tabelle_existiert("chat_teilnehmer"):
        op.create_table(
            "chat_teilnehmer",
            sa.Column("gespraech", sa.String(length=140), nullable=False),
            sa.Column("benutzer", sa.String(length=140), nullable=False),
            sa.Column("stumm", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("hinzugefuegt_am", sa.DateTime(), nullable=True),
            # Lesestand: Zeitstempel UND Kennung der zuletzt gelesenen
            # Nachricht (zwei Nachrichten können denselben Zeitstempel tragen).
            sa.Column("letzter_lesestand", sa.DateTime(), nullable=True),
            sa.Column("letzter_lesestand_nachricht", sa.String(length=140), nullable=True),
            sa.ForeignKeyConstraint(
                ["gespraech"], ["chat_gespraech.name"],
                name="fk_chat_teilnehmer_gespraech_gespraech",
            ),
            sa.ForeignKeyConstraint(
                ["benutzer"], ["user.name"],
                name="fk_chat_teilnehmer_benutzer_user",
            ),
            sa.PrimaryKeyConstraint("gespraech", "benutzer", name="pk_chat_teilnehmer"),
        )
        op.create_index("ix_chat_teilnehmer_benutzer", "chat_teilnehmer", ["benutzer"])

    if not _tabelle_existiert("chat_nachricht"):
        op.create_table(
            "chat_nachricht",
            sa.Column("name", sa.String(length=140), primary_key=True),
            sa.Column("gespraech", sa.String(length=140), nullable=False),
            sa.Column("autor", sa.String(length=140), nullable=True),
            # Besitz (Konto) — entscheidet über die Rechte; verschwindet mit dem
            # Konto (`user_null` in dsgvo_anonymisierung). Review CHAT-2, Punkt 4.
            sa.Column("autor_benutzer", sa.String(length=140), nullable=True),
            sa.Column("text", sa.Text(), nullable=False),
            sa.Column("antwort_auf", sa.String(length=140), nullable=True),
            sa.Column("erstellt_am", sa.DateTime(), nullable=False),
            sa.Column("bearbeitet_am", sa.DateTime(), nullable=True),
            # Soft-Delete: der Verlauf behält die Zeile („Nachricht gelöscht“).
            sa.Column("geloescht_am", sa.DateTime(), nullable=True),
            sa.Column("geloescht_von", sa.String(length=140), nullable=True),
            sa.Column("entfernt_grund", sa.Text(), nullable=True),
            sa.ForeignKeyConstraint(
                ["gespraech"], ["chat_gespraech.name"],
                name="fk_chat_nachricht_gespraech_gespraech",
            ),
            # Autor = VERWEIS auf die Person (Mitglied-Kennung), keine
            # Kontokennung: nach Art. 17 hängt die Anonymisierung sie auf die
            # neutrale Kennung um und der Verlauf bleibt lesbar (Konzept 4.3).
            sa.ForeignKeyConstraint(
                ["autor"], ["mitglied.name"], name="fk_chat_nachricht_autor_mitglied",
            ),
            sa.ForeignKeyConstraint(
                ["autor_benutzer"], ["user.name"],
                name="fk_chat_nachricht_autor_benutzer_user",
            ),
            sa.ForeignKeyConstraint(
                ["antwort_auf"], ["chat_nachricht.name"],
                name="fk_chat_nachricht_antwort_auf_chat_nachricht",
            ),
            sa.ForeignKeyConstraint(
                ["geloescht_von"], ["user.name"],
                name="fk_chat_nachricht_geloescht_von_user",
            ),
        )
        # Ein Index für beide Leserichtungen (3.3): rückwärts = neueste zuerst,
        # vorwärts mit `erstellt_am > X` = „seit X“.
        op.create_index(
            "ix_chat_nachricht_gespraech_erstellt", "chat_nachricht",
            ["gespraech", "erstellt_am"],
        )
        op.create_index(
            "ix_chat_nachricht_antwort_auf", "chat_nachricht", ["antwort_auf"]
        )

    if not _tabelle_existiert("chat_reaktion"):
        op.create_table(
            "chat_reaktion",
            sa.Column("nachricht", sa.String(length=140), nullable=False),
            sa.Column("benutzer", sa.String(length=140), nullable=False),
            sa.Column("reaktion", sa.String(length=8), nullable=False),
            sa.Column("erstellt_am", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(
                ["nachricht"], ["chat_nachricht.name"],
                name="fk_chat_reaktion_nachricht_chat_nachricht",
            ),
            sa.ForeignKeyConstraint(
                ["benutzer"], ["user.name"], name="fk_chat_reaktion_benutzer_user",
            ),
            # EINE Reaktion je Person und Nachricht.
            sa.PrimaryKeyConstraint("nachricht", "benutzer", name="pk_chat_reaktion"),
        )


def downgrade() -> None:
    # Kinder zuerst: Reaktion -> Nachricht -> Teilnehmer -> Gespräch.
    for name in ("chat_reaktion", "chat_nachricht", "chat_teilnehmer", "chat_gespraech"):
        if _tabelle_existiert(name):
            op.drop_table(name)
