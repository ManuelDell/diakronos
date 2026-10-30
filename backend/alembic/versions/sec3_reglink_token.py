"""SEC-3: Registrierungstoken wird serverseitig stark erzeugt (Laenge 43).

Revision ID: sec3_reglink_token
Revises: reg1a_registrierung
Create Date: 2026-10-29

Befund (Pentest dev.ecg-hn.de, MITTEL): `POST /api/resource/Registrierungslink`
nahm einen frei gewaehlten, kurzen `slug` an („pt-mitglied“); zusaetzlich
erzeugte der Server selbst nur `token_urlsafe(10)` (~60 Bit). Registrierungs-
links waren damit erratbar — wer einen Link errät, kann sich selbst
registrieren.

DIESE MIGRATION AENDERT **NICHTS AN DATEN**. Kein Bestands-Token wird
angefasst, gekuerzt oder neu vergeben: ein laufender Link muss nach dem
Deployment weiter funktionieren (Zusage der Karte). Die starke Erzeugung
(`secrets.token_urlsafe(32)` -> 43 Zeichen) und das Verwerfen eines vom Client
gesetzten `slug` passieren im Anwendungscode
(`anmeldung/registrierungslink.neuer_token()` und `frappe_compat/router`).

Warum dann eine Migration? Die neue Tokenform ist eine EIGENSCHAFT der
gespeicherten Zeilen, und sie muss gegen die Datenbank pruefbar sein:
`schema_stand` haelt fest, ob diese Installation die neue Form kennt. Damit
gibt es EINE Stelle, an der eine Installation mit lauter Altzeilen (kurzer
Slug) von einer mit der starken Form unterscheidbar ist — ohne dass der
Anwendungscode die Laenge einzelner Zeilen bewerten muss (das waere eine
zweite Wahrheit, die auseinanderlaufen kann).

Idempotent: `upgrade` legt `schema_stand` nur an, wenn die Tabelle fehlt, und
setzt den Vermerk nur, wenn er fehlt. `downgrade` nimmt die Zeile wieder weg,
laesst die (leere) Tabelle stehen — ein `DROP TABLE` wuerde Zeilen anderer
Karten mitloeschen und ist deshalb nicht Teil dieser Migration.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "sec3_reglink_token"
down_revision: Union[str, None] = "reg1a_registrierung"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABELLE = "schema_stand"
VERMERK = "sec3_reglink_token"
BESCHREIBUNG = (
    "Registrierungslinks: Token wird serverseitig als secrets.token_urlsafe(32) "
    "erzeugt (43 Zeichen); vom Client gesetzter slug wird verworfen"
)


def _hat_tabelle(bind, name: str) -> bool:
    return sa.inspect(bind).has_table(name)


def upgrade() -> None:
    bind = op.get_bind()
    if not _hat_tabelle(bind, TABELLE):
        op.create_table(
            TABELLE,
            sa.Column("vermerk", sa.String(length=140), primary_key=True),
            sa.Column("beschreibung", sa.Text(), nullable=True),
            sa.Column(
                "erfasst_am",
                sa.DateTime(timezone=False),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
        )
    vorhanden = bind.execute(
        sa.text(f"SELECT 1 FROM {TABELLE} WHERE vermerk = :v"), {"v": VERMERK}
    ).first()
    if vorhanden is None:
        bind.execute(
            sa.text(f"INSERT INTO {TABELLE} (vermerk, beschreibung) VALUES (:v, :b)"),
            {"v": VERMERK, "b": BESCHREIBUNG},
        )


def downgrade() -> None:
    bind = op.get_bind()
    if not _hat_tabelle(bind, TABELLE):
        return
    bind.execute(sa.text(f"DELETE FROM {TABELLE} WHERE vermerk = :v"), {"v": VERMERK})
