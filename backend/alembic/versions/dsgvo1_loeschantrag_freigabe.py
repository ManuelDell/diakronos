"""DSGVO-1: Löschantrag bekommt Status, Freigabe und Nachweis-Zeitpunkte

Revision ID: dsgvo1_loeschantrag_freigabe
Revises: bk1_sicherung
Create Date: 2026-10-20

Fachentscheidung Manuel 2026-10-20: „Löschung auf Antrag (DSGVO)“ stellt das
Mitglied selbst, ein Administrator bestätigt; danach wird vollständig
anonymisiert. Der Antrag ist der NACHWEIS, dass gelöscht wurde — er muss den
Vorgang also überleben und darf selbst nichts Personenbezogenes tragen.

Neue Spalten auf `loeschantrag`:

  status            'offen' | 'zurueckgezogen' | 'ausgefuehrt' (NOT NULL,
                    Default 'offen'). Bestandszeilen mit `erledigt_am` werden
                    truthfully auf 'ausgefuehrt' gesetzt — sie waren erledigt,
                    bevor es den Status gab.
  zurueckgezogen_am Zeitpunkt des Widerrufs durch die Person.
  freigegeben_am    Zeitpunkt der Bestätigung durch den Administrator.
  freigegeben_von   KONTO des bestätigenden Administrators (kein Name einer
                    betroffenen Person — der Admin ist der Verantwortliche,
                    nicht das Datensubjekt).
  benachrichtigt_am Zeitpunkt der Meldung an die Person (D4: Mail VOR der
                    Anonymisierung; das Feld belegt die Reihenfolge).
  anonymisiert_am   Zeitpunkt der vollständigen Anonymisierung.

Dazu ein Index (`ix_loeschantrag_status_beantragt`) und ein CHECK auf die drei
Statuswerte — ein Tippfehler im Status darf einen Antrag nicht unsichtbar
machen.

Reihenfolge und Idempotenz: alle Schritte prüfen den Bestand, `upgrade` und
`downgrade` sind wiederholbar. Der CHECK wird nur angelegt, wenn er fehlt, und
VOR dem Setzen des Status geprüft/entfernt, damit bestehende Zeilen mit einem
unbekannten Wert die Migration nicht mit einem unverständlichen
Integritätsfehler abbrechen: solche Zeilen werden nicht geraten, sondern auf
'offen' gesetzt (ihr `erledigt_am` ist NULL) — die Fachlogik listet sie
weiterhin als offen, also fail open gegenüber der betroffenen Person.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "dsgvo1_loeschantrag_freigabe"
down_revision: Union[str, None] = "bk1_sicherung"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

CHECK_NAME = "ck_loeschantrag_status"
INDEX_NAME = "ix_loeschantrag_status_beantragt"
CHECK_AUSDRUCK = "status IN ('offen', 'zurueckgezogen', 'ausgefuehrt')"

NEUE_SPALTEN = (
    ("zurueckgezogen_am", sa.DateTime()),
    ("freigegeben_am", sa.DateTime()),
    ("freigegeben_von", sa.String(140)),
    ("benachrichtigt_am", sa.DateTime()),
    ("anonymisiert_am", sa.DateTime()),
)


def _spalten(bind) -> set[str]:
    return {
        str(zeile[0])
        for zeile in bind.execute(
            sa.text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = current_schema() AND table_name = 'loeschantrag'"
            )
        )
    }


def _check_existiert(bind) -> bool:
    return bind.execute(
        sa.text(
            "SELECT 1 FROM pg_constraint WHERE conname = :n "
            "AND conrelid = 'loeschantrag'::regclass"
        ),
        {"n": CHECK_NAME},
    ).first() is not None


def upgrade() -> None:
    bind = op.get_bind()
    vorhanden = _spalten(bind)

    if "status" not in vorhanden:
        # Erst nullable anlegen, Bestand fuellen, dann NOT NULL: auf einer
        # Tabelle mit Zeilen scheitert eine NOT-NULL-Spalte ohne Default.
        op.add_column("loeschantrag", sa.Column("status", sa.String(20), nullable=True))
        bind.execute(
            sa.text(
                "UPDATE loeschantrag SET status = CASE "
                "WHEN erledigt_am IS NOT NULL THEN 'ausgefuehrt' ELSE 'offen' END "
                "WHERE status IS NULL OR status NOT IN ('offen', 'zurueckgezogen', 'ausgefuehrt')"
            )
        )
        op.alter_column(
            "loeschantrag", "status",
            existing_type=sa.String(20), nullable=False,
            server_default=sa.text("'offen'"),
        )

    for name, typ in NEUE_SPALTEN:
        if name not in _spalten(bind):
            op.add_column("loeschantrag", sa.Column(name, typ, nullable=True))

    if not _check_existiert(bind):
        op.create_check_constraint(CHECK_NAME, "loeschantrag", CHECK_AUSDRUCK)

    indizes = {
        str(zeile[0])
        for zeile in bind.execute(
            sa.text("SELECT indexname FROM pg_indexes WHERE tablename = 'loeschantrag'")
        )
    }
    if INDEX_NAME not in indizes:
        op.create_index(INDEX_NAME, "loeschantrag", ["status", "beantragt_am"])


def downgrade() -> None:
    bind = op.get_bind()
    indizes = {
        str(zeile[0])
        for zeile in bind.execute(
            sa.text("SELECT indexname FROM pg_indexes WHERE tablename = 'loeschantrag'")
        )
    }
    if INDEX_NAME in indizes:
        op.drop_index(INDEX_NAME, table_name="loeschantrag")

    if _check_existiert(bind):
        op.drop_constraint(CHECK_NAME, "loeschantrag", type_="check")

    vorhanden = _spalten(bind)
    for name, _typ in reversed(NEUE_SPALTEN):
        if name in vorhanden:
            op.drop_column("loeschantrag", name)
    if "status" in vorhanden:
        op.drop_column("loeschantrag", "status")
