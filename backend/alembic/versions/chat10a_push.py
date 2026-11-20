"""CHAT-10a: Web-Push-Abonnements (Tabelle ``push_abonnement``).

Revision ID: chat10a_push
Revises: chat9a_erwaehnung
Create Date: 2026-11-20

Konzept ``docs/konzepte/CHAT-KONZEPT.md`` Abschnitt 3.2 („Push aufs Handy“) und
Entscheidung F10 (**Web-Push OHNE Inhalt**). Karte CHAT-10a — nur das Backend
(Abonnements + Versand); Service-Worker und Oberfläche sind eine eigene Karte.

EINE ÄNDERUNG, keine zweite:

  ``push_abonnement`` (NEUE Tabelle) — ``endpoint, benutzer, p256dh, auth,
  angelegt_am, zuletzt_ok_am, fehlversuche``. Primärschlüssel ist ``endpoint``
  (der Push-Endpunkt des Geräts): derselbe endpoint kann nicht zweimal
  bestehen, und ein Gerätewechsel (andere Person meldet sich auf demselben
  Browser an) ist ein UPDATE der Zeile — genau die Regel der Karte („ein Gerät
  gehört dem, der gerade angemeldet ist“). Der Primärschlüssel IST damit die
  Eindeutigkeit; ein eigener UNIQUE-Index daneben wäre dieselbe Zusage zweimal
  (Postgres legt für den PK bereits einen Index an).

  ``ix_push_abonnement_benutzer`` — „welche Geräte hat diese Person?“: EIN
  Abruf je Versand.

  ``benutzer`` ist ein KONTONAME (``user.name``) OHNE FK: eine gelöschte
  Kontozeile soll die Abonnement-Zeile nicht per CASCADE mitreißen (die
  Anonymisierung räumt sie ausdrücklich ab, ``ZEILEN_LOESCHEN``/
  ``push_abonnement``). Ein Versand an ein verwaistes Konto findet ohnehin
  nicht statt (gesucht wird je Konto).

Kein DDL an bestehenden Tabellen, KEINE neue Spalte woanders. Die VAPID-Schlüssel
stehen NICHT in der Datenbank, sondern in der Umgebung
(``DIAKRONOS_VAPID_PUBLIC``/``_PRIVATE``/``_KONTAKT``).

Revision-Kette: Kopf beim Schreiben war ``chat9a_erwaehnung`` — geprüft über
``alembic heads`` im Vorbau-Image (NICHT geraten). Der neue Kopf ist diese
Revision; es gibt weiterhin genau EINEN.

Idempotent: ``upgrade`` prüft zuerst den Ist-Zustand (Tabelle/Index vorhanden?).
``downgrade`` entfernt die Tabelle; sie trägt kein Wissen, das woanders fehlt
(Abonnements sind jederzeit im Browser neu anmeldbar) — die Zeilen gehen dabei
verloren, deshalb bricht ``downgrade`` NICHT ab, sondern meldet die Zahl der
verlorenen Abonnements laut ins Log.
"""

import logging
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "chat10a_push"
down_revision: Union[str, None] = "chat9a_erwaehnung"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

logger = logging.getLogger("alembic.runtime.migration")

TABELLE = "push_abonnement"
INDEX_BENUTZER = "ix_push_abonnement_benutzer"


def _tabelle_existiert(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def _indizes(tabelle: str) -> set[str]:
    return {str(i["name"]) for i in sa.inspect(op.get_bind()).get_indexes(tabelle)}


def upgrade() -> None:
    if not _tabelle_existiert(TABELLE):
        op.create_table(
            TABELLE,
            # Der endpoint ist Primärschlüssel UND die Eindeutigkeit (s. oben).
            sa.Column("endpoint", sa.String(length=1000), primary_key=True),
            sa.Column("benutzer", sa.String(length=140), nullable=False),
            sa.Column("p256dh", sa.String(length=255), nullable=False),
            sa.Column("auth", sa.String(length=255), nullable=False),
            sa.Column("angelegt_am", sa.DateTime(), nullable=False),
            sa.Column("zuletzt_ok_am", sa.DateTime(), nullable=True),
            sa.Column("fehlversuche", sa.Integer(), nullable=False,
                      server_default="0"),
        )
    if INDEX_BENUTZER not in (_indizes(TABELLE) if _tabelle_existiert(TABELLE) else set()):
        op.create_index(INDEX_BENUTZER, TABELLE, ["benutzer"])


def downgrade() -> None:
    if not _tabelle_existiert(TABELLE):
        return
    # Laut, aber kein Abbruch: ein Abonnement ist im Browser in einer Sekunde
    # neu angelegt (die Person meldet sich erneut für Push an). Wer die Zahl
    # sehen will, findet sie hier; die übrigen Strukturen (Glocken, Nachrichten)
    # bleiben unberührt.
    anzahl = op.get_bind().execute(
        sa.text(f"SELECT count(*) FROM {TABELLE}")
    ).scalar_one()
    if anzahl:
        logger.warning(
            "CHAT-10a: Rücknahme löscht %s Push-Abonnement(s) — die Geräte "
            "melden sich neu an (kein Datenverlust an Nachrichten/Glocken).",
            anzahl,
        )
    op.drop_table(TABELLE)
