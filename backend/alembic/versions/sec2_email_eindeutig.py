"""SEC: E-Mail-Adresse eindeutig je Mitglied (partieller Unique-Index)

Revision ID: sec2_email_eindeutig
Revises: p25_anmeldeformular_parenttype
Create Date: 2026-10-19

FACHENTSCHEIDUNG (Manuel, 2026-10-19, verbindlich): JEDE PERSON BRAUCHT EINE
EIGENE E-MAIL-ADRESSE. Eine Adresse gehoert hoechstens zu EINEM Mitglied
(Vergleich getrimmt + kleingeschrieben); Familienpostfaecher gibt es nicht
mehr. Vorher stand die Eindeutigkeit nur im Anwendungscode — der liess sich
umgehen (Race, Import, direkter Schreibweg). Der Index ist die letzte Instanz.

Der Index ist PARTIELL: Mitglieder OHNE E-Mail (leer oder NULL) bleiben
erlaubt. Verglichen wird `lower(trim(email))`, genau wie in
`email_belegung.belegung` und `email_belegung.normalisiere`.

Vor dem Anlegen des Index laeuft eine Bestandspruefung. Findet sie Dubletten,
bricht die Migration mit Klartext ab (fail closed) — sie raet nicht und
loescht nichts. Der Betrieb hat aktuell 0 Dubletten und 0 leere Adressen
(geprueft 2026-10-19); der Abbruchpfad bleibt trotzdem drin, weil die
Migration auf JEDER Installation laufen muss.

Idempotent: `upgrade` und `downgrade` pruefen zuerst, ob der Index schon
existiert bzw. noch fehlt.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "sec2_email_eindeutig"
down_revision: Union[str, None] = "p25_anmeldeformular_parenttype"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

#: Name des Index — auch in `frappe_compat/api_helpers.py` benutzt, um die
#: Verletzung als fachlichen Fehler („Adresse gehoert bereits zu …") zu melden.
INDEX_NAME = "uq_mitglied_email_normalisiert"


def _index_existiert() -> bool:
    """Traegt die Tabelle `mitglied` den Index schon?"""
    bind = op.get_bind()
    vorhanden = bind.execute(
        sa.text(
            "SELECT 1 FROM pg_indexes WHERE tablename = 'mitglied' AND indexname = :n"
        ),
        {"n": INDEX_NAME},
    ).first()
    return vorhanden is not None


def _dubletten() -> list[tuple[str, int]]:
    """Doppelt belegte Adressen als (normalisierte Adresse, Anzahl)."""
    bind = op.get_bind()
    return [
        (str(adresse), int(anzahl))
        for adresse, anzahl in bind.execute(
            sa.text(
                "SELECT lower(trim(email)) AS adresse, count(*) AS anzahl "
                "FROM mitglied "
                "WHERE coalesce(trim(email), '') <> '' "
                "GROUP BY lower(trim(email)) "
                "HAVING count(*) > 1 "
                "ORDER BY anzahl DESC, adresse"
            )
        ).fetchall()
    ]


def upgrade() -> None:
    if _index_existiert():
        return
    # Fail closed: keine erfundene Bereinigung. Wer eine Dublette im Bestand
    # hat, muss sie zuerst aufloesen (die Adresse gehoert zu genau einer
    # Person) — sonst bliebe unklar, welches Mitglied gemeint ist.
    doppelt = _dubletten()
    if doppelt:
        beschreibung = ", ".join(f"{adresse} ({anzahl}x)" for adresse, anzahl in doppelt[:10])
        raise RuntimeError(
            "SEC-Migration abgebrochen (fail closed): es gibt Mitglieder mit "
            "derselben E-Mail-Adresse und jede Adresse darf nur zu EINEM "
            f"Mitglied gehoeren. Bitte zuerst aufloesen: {beschreibung}"
        )
    # Partieller Unique-Index: zwei Mitglieder ohne Adresse (NULL oder leer)
    # sind weiterhin erlaubt — der Index greift nur fuer echte Adressen.
    # Der Ausdruck muss ZEICHENGLEICH zur Deklaration im Modell
    # (`models/diakronos.py::Mitglied.__table_args__`) sein, sonst meldet
    # `alembic check` einen Unterschied.
    op.create_index(
        INDEX_NAME,
        "mitglied",
        [sa.text("lower(trim(email))")],
        unique=True,
        postgresql_where=sa.text("coalesce(trim(email), '') <> ''"),
    )


def downgrade() -> None:
    if not _index_existiert():
        return
    op.drop_index(INDEX_NAME, table_name="mitglied")
