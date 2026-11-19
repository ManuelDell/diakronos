"""CHAT-5 (S2): Umfragen im Gruppenchat.

Revision ID: chat5_umfrage
Revises: chat6_meldung
Create Date: 2026-11-18

Konzept ``docs/konzepte/CHAT-KONZEPT.md`` Abschnitt 1/S2 und die Entscheidung
F5 (Abschnitt 9: jedes Mitglied darf starten, Standard ANONYM, je Umfrage
wählbar). Angelegt werden vier Tabellen und EINE Spalte an einer bestehenden:

    chat_umfrage         Frage, mehrfach, anonym (Default TRUE), frist_am,
                         geschlossen_am/geschlossen_von; Index auf (frist_am)
                         für den Scheduler
    chat_umfrage_option  PK (umfrage, nummer); `stimmen` ist der ZÄHLER
    chat_stimme          PK (umfrage, option, benutzer) — NUR bei OFFENER Umfrage
    chat_umfrage_abgabe  PK (umfrage, benutzer) — „hat abgestimmt“, OHNE Option
    chat_nachricht.umfrage      Verweis auf die Umfrage, die an der Nachricht
                                hängt (0..1, UNIQUE-Index)

Die beiden Zählwege sind Absicht und die Kernzusage der Karte: bei einer
ANONYMEN Umfrage existiert KEINE Zeile, die Person und Option verbindet —
weder `chat_stimme` (die Tabelle bleibt für diese Umfrage leer) noch eine
Spalte in `chat_umfrage_abgabe`. Erratbar ist das Ergebnis nur über die Zahl
der Abgegebenen; deshalb steht der Hinweis unter 5 Abgegebenen in der Antwort.

Revision-Kette: ``chat2_chat_s1`` war der Kopf, als dieser Zwischenstand
angelegt wurde. Inzwischen ist ``chat6_meldung`` (CHAT-6) dazugekommen und
hängt ebenfalls an ``chat2_chat_s1`` — deshalb steht ``down_revision`` hier
NICHT mehr auf ``chat2_chat_s1``, sondern auf ``chat6_meldung``: die Kette ist
``chat2_chat_s1 -> chat6_meldung -> chat5_umfrage``. `alembic upgrade head` im
Entrypoint braucht genau einen Kopf; nach dieser Änderung gibt es genau einen.
Die Reihenfolge ist frei wählbar (die beiden Migrationen berühren sich nicht),
aber sie muss EINDEUTIG sein.

Idempotent: jede Tabelle/Spalte wird nur angelegt, wenn sie fehlt. `downgrade`
nimmt die Spalte und die vier Tabellen wieder weg (Kinder zuerst).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "chat5_umfrage"
down_revision: Union[str, None] = "chat6_meldung"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _tabelle_existiert(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def _spalte_existiert(tabelle: str, spalte: str) -> bool:
    insp = sa.inspect(op.get_bind())
    if not insp.has_table(tabelle):
        return False
    return spalte in {s["name"] for s in insp.get_columns(tabelle)}


def upgrade() -> None:
    if not _tabelle_existiert("chat_umfrage"):
        op.create_table(
            "chat_umfrage",
            sa.Column("name", sa.String(length=140), primary_key=True),
            sa.Column("gespraech", sa.String(length=140), nullable=False),
            sa.Column("frage", sa.Text(), nullable=False),
            sa.Column("mehrfach", sa.Boolean(), nullable=False,
                      server_default=sa.text("false")),
            # F5: Standard ANONYM.
            sa.Column("anonym", sa.Boolean(), nullable=False,
                      server_default=sa.text("true")),
            sa.Column("frist_am", sa.DateTime(), nullable=True),
            sa.Column("geschlossen_am", sa.DateTime(), nullable=True),
            sa.Column("geschlossen_von", sa.String(length=140), nullable=True),
            sa.Column("erstellt_am", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(
                ["gespraech"], ["chat_gespraech.name"],
                name="fk_chat_umfrage_gespraech_chat_gespraech",
            ),
            sa.ForeignKeyConstraint(
                ["geschlossen_von"], ["user.name"],
                name="fk_chat_umfrage_geschlossen_von_user",
            ),
        )
        op.create_index("ix_chat_umfrage_gespraech", "chat_umfrage", ["gespraech"])
        # Der Scheduler sucht offene Umfragen mit Frist <= jetzt.
        op.create_index("ix_chat_umfrage_frist", "chat_umfrage", ["frist_am"])

    if not _tabelle_existiert("chat_umfrage_option"):
        op.create_table(
            "chat_umfrage_option",
            sa.Column("umfrage", sa.String(length=140), nullable=False),
            sa.Column("nummer", sa.Integer(), nullable=False),
            sa.Column("text", sa.String(length=140), nullable=False),
            sa.Column("stimmen", sa.Integer(), nullable=False,
                      server_default=sa.text("0")),
            sa.ForeignKeyConstraint(
                ["umfrage"], ["chat_umfrage.name"],
                name="fk_chat_umfrage_option_umfrage_chat_umfrage",
            ),
            # `nummer` ist Reihenfolge UND Kennung.
            sa.PrimaryKeyConstraint("umfrage", "nummer", name="pk_chat_umfrage_option"),
        )

    if not _tabelle_existiert("chat_stimme"):
        op.create_table(
            "chat_stimme",
            sa.Column("umfrage", sa.String(length=140), nullable=False),
            sa.Column("option", sa.Integer(), nullable=False),
            sa.Column("benutzer", sa.String(length=140), nullable=False),
            sa.Column("erstellt_am", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(
                ["umfrage"], ["chat_umfrage.name"],
                name="fk_chat_stimme_umfrage_chat_umfrage",
            ),
            sa.ForeignKeyConstraint(
                ["umfrage", "option"],
                ["chat_umfrage_option.umfrage", "chat_umfrage_option.nummer"],
                name="fk_chat_stimme_option_chat_umfrage_option",
            ),
            sa.ForeignKeyConstraint(
                ["benutzer"], ["user.name"], name="fk_chat_stimme_benutzer_user",
            ),
            sa.PrimaryKeyConstraint("umfrage", "option", "benutzer",
                                    name="pk_chat_stimme"),
        )
        op.create_index("ix_chat_stimme_benutzer", "chat_stimme", ["benutzer"])

    if not _tabelle_existiert("chat_umfrage_abgabe"):
        op.create_table(
            "chat_umfrage_abgabe",
            sa.Column("umfrage", sa.String(length=140), nullable=False),
            sa.Column("benutzer", sa.String(length=140), nullable=False),
            sa.Column("erstellt_am", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(
                ["umfrage"], ["chat_umfrage.name"],
                name="fk_chat_umfrage_abgabe_umfrage_chat_umfrage",
            ),
            sa.ForeignKeyConstraint(
                ["benutzer"], ["user.name"],
                name="fk_chat_umfrage_abgabe_benutzer_user",
            ),
            # Der Primärschlüssel IST die Sperre gegen die zweite Abgabe.
            sa.PrimaryKeyConstraint("umfrage", "benutzer", name="pk_chat_umfrage_abgabe"),
        )
        op.create_index("ix_chat_umfrage_abgabe_benutzer", "chat_umfrage_abgabe",
                        ["benutzer"])

    # Der Verweis Nachricht -> Umfrage. Er kommt NACH den Umfrage-Tabellen:
    # ein Fremdschlüssel auf eine noch fehlende Tabelle ginge nicht durch.
    if not _spalte_existiert("chat_nachricht", "umfrage"):
        # SQLite kann weder eine Spalte MIT Fremdschlüssel per ALTER anlegen
        # noch den Schlüssel danach setzen — dort beides in EINEM
        # batch_alter_table (copy-and-move). PostgreSQL macht es direkt.
        if op.get_bind().dialect.name == "sqlite":
            with op.batch_alter_table("chat_nachricht") as batch:
                batch.add_column(sa.Column("umfrage", sa.String(length=140),
                                           nullable=True))
                batch.create_foreign_key(
                    "fk_chat_nachricht_umfrage_chat_umfrage", "chat_umfrage",
                    ["umfrage"], ["name"],
                )
        else:
            op.add_column(
                "chat_nachricht",
                sa.Column("umfrage", sa.String(length=140), nullable=True),
            )
            op.create_foreign_key(
                "fk_chat_nachricht_umfrage_chat_umfrage", "chat_nachricht",
                "chat_umfrage", ["umfrage"], ["name"],
            )
        # Höchstens EINE Umfrage je Nachricht — in der Datenbank, nicht nur im
        # Endpunkt. NULL gilt nicht als gleich, „keine Umfrage“ bleibt frei.
        op.create_index("uq_chat_nachricht_umfrage", "chat_nachricht", ["umfrage"],
                        unique=True)


def downgrade() -> None:
    # Erst der Verweis (Kind), dann die Tabellen: eine noch zeigende Spalte
    # würde das Löschen von `chat_umfrage` blockieren.
    if _spalte_existiert("chat_nachricht", "umfrage"):
        if "uq_chat_nachricht_umfrage" in {
            i["name"] for i in sa.inspect(op.get_bind()).get_indexes("chat_nachricht")
        }:
            op.drop_index("uq_chat_nachricht_umfrage", table_name="chat_nachricht")
        # SQLite kann einen NAMED CONSTRAINT nicht per ALTER entfernen; dort
        # fällt die Spalte per batch_alter_table (copy-and-move) und nimmt den
        # Fremdschlüssel mit. PostgreSQL kann `drop_constraint` direkt.
        # Dasselbe Muster wie `r7b_aufgaben_zuweisung`.
        bind = op.get_bind()
        if bind.dialect.name != "sqlite" and any(
            fk.get("name") == "fk_chat_nachricht_umfrage_chat_umfrage"
            for fk in sa.inspect(bind).get_foreign_keys("chat_nachricht")
        ):
            op.drop_constraint("fk_chat_nachricht_umfrage_chat_umfrage",
                               "chat_nachricht", type_="foreignkey")
        with op.batch_alter_table("chat_nachricht") as batch:
            batch.drop_column("umfrage")
    for name in ("chat_umfrage_abgabe", "chat_stimme", "chat_umfrage_option",
                 "chat_umfrage"):
        if _tabelle_existiert(name):
            op.drop_table(name)
