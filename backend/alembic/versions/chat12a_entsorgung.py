"""CHAT-12a: Entsorgungsliste und Hochlade-Marken der Chat-Anhänge.

Revision ID: chat12a_entsorgung
Revises: chat12a_anhang
Create Date: 2026-11-20

ZWEI ÄNDERUNGEN (Review R1, Punkte 3 und 4 — beide Pflicht):

  ``chat_anhang_entsorgung`` (NEUE Tabelle) — je Zeile ein AUFTRAG „lösch
  diesen Speicher-Schlüssel“: ``schluessel`` (PK), ``vorgemerkt_am``,
  ``versuche``, ``letzter_fehler`` (kurz). Jeder Weg, der ``chat_anhang``-Zeilen
  löscht, schreibt die Schlüssel in DERSELBEN Transaktion hier hinein; der
  Minuten-Job ``chat_anhang_entsorgung_abarbeiten`` löscht die Datei aus der
  Ablage und danach die Zeile. „Nicht vorhanden“ ist Erfolg, ein Fehler zählt
  ``versuche`` hoch und der nächste Lauf versucht es erneut. Vorher blieb eine
  Datei nach einem gescheiterten Ablage-Löschen für immer liegen.
  Die Wartezeit bis zum nächsten Versuch steht seit ``chat12a2_backoff`` in
  ``naechster_versuch_am`` (Backoff statt Kopfblockade) — DIESE Revision legt
  die Spalte noch nicht an.

  ``chat_anhang_hochladung`` (NEUE Tabelle) — eine Zeile je Hochlade-VERSUCH:
  ``name`` (PK), ``konto`` (FK auf ``user``, ``ON DELETE CASCADE``),
  ``angelegt_am``. Grundlage des Tageskontingents (20 je Person und Tag).
  Gezählt wird bewusst je VERSUCH, nicht je erfolgreichem Upload: die Marke
  entsteht vor der Typ- und Größenprüfung, damit Fehlversuche das Kontingent
  nicht umgehen. Vorher zählte der Endpunkt die vorhandenen
  ``chat_anhang``-Zeilen — wer hochlädt, sendet und die Nachricht löscht,
  hatte ein unbegrenztes Kontingent.
  Die Marke wird beim Löschen einer Nachricht NICHT mitgelöscht; sie fällt mit
  dem Konto (DSGVO) oder nach zwei Tagen (Aufräumjob).

Keine Spalte an bestehenden Tabellen. ``chat_anhang.angelegt_von`` bekommt in
``chat12a_anhang`` bereits ``ON DELETE SET NULL``; das MODELL führt seit dem
Review dieselbe Angabe (vorher Drift, Review R1/2).

DSGVO-Inventar: ``chat_anhang_entsorgung`` trägt keine Personendaten (der
Schlüssel ist eine technische Kennung ohne Kontobezug) und steht deshalb NICHT
im Inventar. ``chat_anhang_hochladung`` ist ein Verhaltensdatum am Konto und
steht dort als ``KONTO_ZEILEN`` (Zeile fällt mit dem Konto).

Idempotent: ``upgrade`` prüft Tabelle und Indizes vor dem Anlegen.
``downgrade`` weist laut ab, solange Zeilen existieren (ein offener Auftrag
darf nicht stillschweigend verschwinden — sonst bliebe die Datei für immer).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "chat12a_entsorgung"
down_revision: Union[str, None] = "chat12a_anhang"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ENTSORGUNG = "chat_anhang_entsorgung"
HOCHLADUNG = "chat_anhang_hochladung"
IDX_ENTSORGUNG_AM = "ix_chat_anhang_entsorgung_am"
IDX_HOCHLADUNG_KONTO = "ix_chat_anhang_hochladung_konto_am"
IDX_HOCHLADUNG_AM = "ix_chat_anhang_hochladung_am"


def _tabelle_existiert(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def _indizes(tabelle: str) -> set[str]:
    return {str(i["name"]) for i in sa.inspect(op.get_bind()).get_indexes(tabelle)}


def upgrade() -> None:
    if not _tabelle_existiert(ENTSORGUNG):
        op.create_table(
            ENTSORGUNG,
            sa.Column("schluessel", sa.String(length=255), primary_key=True),
            sa.Column("vorgemerkt_am", sa.DateTime(), nullable=False),
            sa.Column("versuche", sa.Integer(), nullable=False,
                      server_default=sa.text("0")),
            sa.Column("letzter_fehler", sa.String(length=200), nullable=True),
        )
    if _tabelle_existiert(ENTSORGUNG) and IDX_ENTSORGUNG_AM not in _indizes(ENTSORGUNG):
        op.create_index(IDX_ENTSORGUNG_AM, ENTSORGUNG, ["vorgemerkt_am"])

    if not _tabelle_existiert(HOCHLADUNG):
        op.create_table(
            HOCHLADUNG,
            sa.Column("name", sa.String(length=140), primary_key=True),
            sa.Column(
                "konto",
                sa.String(length=140),
                sa.ForeignKey("user.name", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("angelegt_am", sa.DateTime(), nullable=False),
        )
    indizes = _indizes(HOCHLADUNG) if _tabelle_existiert(HOCHLADUNG) else set()
    if IDX_HOCHLADUNG_KONTO not in indizes:
        op.create_index(IDX_HOCHLADUNG_KONTO, HOCHLADUNG, ["konto", "angelegt_am"])
    if IDX_HOCHLADUNG_AM not in indizes:
        op.create_index(IDX_HOCHLADUNG_AM, HOCHLADUNG, ["angelegt_am"])


def downgrade() -> None:
    # Laut und früh: mit der Entsorgungsliste verschwände der einzige Verweis
    # auf eine Datei, deren Anhang-Zeile schon gelöscht ist — sie bliebe für
    # immer in der Ablage liegen. Erst abarbeiten, dann zurücknehmen.
    if _tabelle_existiert(ENTSORGUNG):
        anzahl = op.get_bind().execute(
            sa.text(f"SELECT count(*) FROM {ENTSORGUNG}")
        ).scalar_one()
        if anzahl:
            raise RuntimeError(
                "Rücknahme nicht möglich: es stehen "
                f"{anzahl} Entsorgungs-Auftrag/-Aufträge offen. Erst abarbeiten "
                "(Job ``chat_anhang_entsorgung_abarbeiten``), dann downgrade."
            )
        indizes = _indizes(ENTSORGUNG)
        if IDX_ENTSORGUNG_AM in indizes:
            op.drop_index(IDX_ENTSORGUNG_AM, table_name=ENTSORGUNG)
        op.drop_table(ENTSORGUNG)

    if _tabelle_existiert(HOCHLADUNG):
        indizes = _indizes(HOCHLADUNG)
        for name in (IDX_HOCHLADUNG_KONTO, IDX_HOCHLADUNG_AM):
            if name in indizes:
                op.drop_index(name, table_name=HOCHLADUNG)
        op.drop_table(HOCHLADUNG)
