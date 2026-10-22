"""DSGVO-2a: Löschantrag kann abgelehnt werden (Status, Grund, wer/wann)

Revision ID: dsgvo2a_antrag_ablehnung
Revises: ma1_smtp
Create Date: 2026-10-21

Die Verwaltung lehnt einen Löschantrag ab (z. B. weil noch offene Pflichten
bestehen oder die Anfrage nicht von der Person stammt). Der Vorgang ist damit
abgeschlossen, aber nicht ausgeführt: Die Person behält alle Daten, wird per
Mail informiert — mit Begründung und dem Hinweis, dass sie es erneut beantragen
und sich bei der Datenschutz-Aufsichtsbehörde beschweren darf — und kann
danach einen neuen Antrag stellen.

Neue Spalten auf `loeschantrag`:

  abgelehnt_am      Zeitpunkt der Ablehnung durch die Verwaltung.
  abgelehnt_von     KONTO des ablehnenden Administrators (der Verantwortliche,
                    nicht das Datensubjekt — wie `freigegeben_von`).
  ablehnung_grund   Die Begründung im Wortlaut (Pflichtfeld der API). Sie ist
                    für die betroffene Person bestimmt und steht deshalb am
                    Antrag; im Audit-Log erscheint sie NICHT (sie kann
                    Gesundheitsdaten enthalten, Art. 9 DSGVO).

`status` bekommt den vierten Wert `abgelehnt`. Der CHECK
`ck_loeschantrag_status` wird dafür erweitert (drop + create, weil PostgreSQL
einen CHECK nicht ändern kann). Vor dem Anlegen werden Bestandszeilen mit einem
unbekannten Status auf 'offen' gesetzt — wie in `dsgvo1_loeschantrag_freigabe`,
damit die Migration nicht an einer Altzeile scheitert.

Reihenfolge und Idempotenz: jeder Schritt prüft den Bestand; `upgrade` und
`downgrade` sind wiederholbar. `downgrade` entfernt abgelehnte Anträge nicht —
sie werden zu 'offen' (fail open gegenüber der betroffenen Person: der Antrag
gilt danach wieder als unbearbeitet) und die drei Spalten fallen weg.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "dsgvo2a_antrag_ablehnung"
down_revision: Union[str, None] = "ma1_smtp"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

CHECK_NAME = "ck_loeschantrag_status"
CHECK_AUSDRUCK = "status IN ('offen', 'zurueckgezogen', 'ausgefuehrt', 'abgelehnt')"
CHECK_AUSDRUCK_ALT = "status IN ('offen', 'zurueckgezogen', 'ausgefuehrt')"

NEUE_SPALTEN = (
    ("abgelehnt_am", sa.DateTime()),
    ("abgelehnt_von", sa.String(140)),
    ("ablehnung_grund", sa.Text()),
)


def _spalten(bind) -> set[str]:
    return {
        str(zeile[0])
        for zeile in bind.execute(
            sa.text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'loeschantrag'"
            )
        )
    }


def _check_vorhanden(bind) -> bool:
    return bool(bind.execute(
        sa.text("SELECT 1 FROM pg_constraint WHERE conname = :n"),
        {"n": CHECK_NAME},
    ).first())


def _check_entfernen(bind) -> None:
    if _check_vorhanden(bind):
        op.drop_constraint(CHECK_NAME, "loeschantrag", type_="check")


def _check_anlegen(bind, ausdruck: str) -> None:
    _check_entfernen(bind)
    op.create_check_constraint(CHECK_NAME, "loeschantrag", ausdruck)


def upgrade() -> None:
    bind = op.get_bind()

    # Erst den alten CHECK weg: sonst scheitert das Setzen eines unbekannten
    # Status auf 'offen' an genau dem Constraint, das wir erweitern wollen.
    _check_entfernen(bind)
    bind.execute(sa.text(
        "UPDATE loeschantrag SET status = 'offen' "
        "WHERE status IS NULL OR status NOT IN "
        "('offen', 'zurueckgezogen', 'ausgefuehrt', 'abgelehnt')"
    ))

    vorhanden = _spalten(bind)
    for name, typ in NEUE_SPALTEN:
        if name not in vorhanden:
            op.add_column("loeschantrag", sa.Column(name, typ, nullable=True))

    _check_anlegen(bind, CHECK_AUSDRUCK)


def downgrade() -> None:
    bind = op.get_bind()

    # Abgelehnte Anträge überleben den Rückbau als offene: der Vorgang war
    # nicht ausgeführt, und die Person soll nicht ohne Antrag dastehen.
    _check_entfernen(bind)
    bind.execute(sa.text(
        "UPDATE loeschantrag SET status = 'offen' WHERE status = 'abgelehnt'"
    ))
    _check_anlegen(bind, CHECK_AUSDRUCK_ALT)

    vorhanden = _spalten(bind)
    for name, _typ in reversed(NEUE_SPALTEN):
        if name in vorhanden:
            op.drop_column("loeschantrag", name)
