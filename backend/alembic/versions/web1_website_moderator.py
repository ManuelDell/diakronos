"""WEB-1 — Alembic-Migration: Rolle "Website-Moderator".

Was diese Migration tut
-----------------------
1. Setzt den Vermerk `web1_website_moderator` in `schema_stand` (Tabelle aus
   SEC-3, wird bei Bedarf angelegt). Der Vermerk sagt: diese Installation
   kennt die Rolle.
2. Fuegt die Rolle in die Rollen-Auswahlliste des DocType `User`
   (`tabDocField` -> `Has Role` -> `role`) ein — nur wenn der DocType bzw. das
   Feld vorhanden ist. Der Constraint `tabHas Role.role` ist ein `link`, also
   ein FREIES Textfeld; ein Rollenname funktioniert auch ohne Eintrag in der
   Auswahlliste. Die Liste ist damit reine Oberflaechen-Hilfe, keine
   Voraussetzung.
3. Aendert KEINE Benutzerdaten: es wird niemandem die neue Rolle gegeben.
   Die Vergabe ist eine Administrations-Handlung (Oberflaeche), kein
   Migrationsschritt — eine Migration, die Rechte verteilt, waere ein
   Sicherheitsrisiko ohne Not.

Idempotent
----------
`upgrade` legt `schema_stand` nur an, wenn sie fehlt, setzt den Vermerk nur,
wenn er fehlt, und ergaenzt die Auswahlliste nur, wenn sie den Namen noch
nicht enthaelt. `downgrade` entfernt Vermerk und Auswahllisten-Eintrag wieder
— die (leere) Tabelle `schema_stand` bleibt stehen, weil sie anderen Karten
gehoert (gleiche Begruendung wie in `sec3_reglink_token`).

Einziger Head
-------------
`down_revision = "sec3_reglink_token"` — die Kette hat genau einen Kopf.

Revision ID: web1_website_moderator
Revises: sec3_reglink_token
Create Date: 2026-10-30
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "web1_website_moderator"
down_revision: Union[str, None] = "sec3_reglink_token"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABELLE = "schema_stand"
VERMERK = "web1_website_moderator"
BESCHREIBUNG = (
    "Website-Moderator: Rolle fuer das optionale Website-Modul (WEB-1) — "
    "Zugriff auf Primo-Status und Login-Uebergabe; Vergabe nur durch Admins"
)

ROLLE = "Website-Moderator"
# DocType/Feld der Rollen-Auswahlliste (Frappe-Struktur, wie importiert).
DOCFIELD_TABELLE = "tabDocField"
DOCFIELD_PARENT = "User"
DOCFIELD_FELD = "role"
DOCFIELD_OPTIONEN_SPALTE = "options"


def _tabelle_names(bind) -> set[str]:
    """Vorhandene Tabellennamen in den durchsuchten Schemata (klein)."""
    insp = sa.inspect(bind)
    return {
        str(name).lower()
        for name in insp.get_table_names()
        + insp.get_table_names(schema="public")
    }


def _hat_tabelle(bind, name: str) -> bool:
    """Case-insensibler Tabellentest.

    `inspect().has_table` vergleicht EXAKT: auf PostgreSQL legt Frappe die
    Tabellen syntaktisch unquoted an, der Katalog speichert sie also klein
    (`has_role`), waehrend Modelle/Code `Has Role` schreiben. Ein exakter
    Vergleich meldet dann "fehlt", obwohl die Tabelle existiert — die
    Migration haette die Rollenliste stillschweigend nicht ergaenzt.
    """
    return str(name).lower() in _tabelle_names(bind)


def _echter_name(bind, name: str) -> str:
    """Katalogschreibweise eines Tabellennamens (fuer SQL-Aufrufe)."""
    insp = sa.inspect(bind)
    for kandidat in insp.get_table_names() + insp.get_table_names(schema="public"):
        if str(kandidat).lower() == str(name).lower():
            return str(kandidat)
    return name


def _hat_spalte(bind, tabelle: str, spalte: str) -> bool:
    insp = sa.inspect(bind)
    return any(
        str(s["name"]).lower() == str(spalte).lower()
        for s in insp.get_columns(_echter_name(bind, tabelle))
    )


def _optionen(bind) -> list[str]:
    if not _hat_tabelle(bind, DOCFIELD_TABELLE):
        return []
    if not _hat_spalte(bind, DOCFIELD_TABELLE, DOCFIELD_OPTIONEN_SPALTE):
        return []
    # Frappe speichert Select-Optionen zeilenweise getrennt (\n, bei einem
    # Windows-Export auch \r\n). Beide Trenner werden aufgeloest, damit ein
    # Eintrag nicht als eine einzige Zeile "A\r\nB" zurueckkommt — das waere
    # eine stille Nicht-Ergaenzung.
    roh = bind.execute(
        sa.text(
            f"SELECT {DOCFIELD_OPTIONEN_SPALTE} FROM {_echter_name(bind, DOCFIELD_TABELLE)} "
            "WHERE lower(parent) = lower(:p) AND lower(fieldname) = lower(:f)"
        ),
        {"p": DOCFIELD_PARENT, "f": DOCFIELD_FELD},
    ).scalar()
    if not roh:
        return []
    return [
        zeile.strip()
        for zeile in str(roh).replace("\r\n", "\n").replace("\r", "\n").split("\n")
        if zeile.strip()
    ]


def _optionen_schreiben(bind, werte: list[str]) -> None:
    bind.execute(
        sa.text(
            f"UPDATE {_echter_name(bind, DOCFIELD_TABELLE)} "
            f"SET {DOCFIELD_OPTIONEN_SPALTE} = :o "
            "WHERE lower(parent) = lower(:p) AND lower(fieldname) = lower(:f)"
        ),
        {"o": "\n".join(werte), "p": DOCFIELD_PARENT, "f": DOCFIELD_FELD},
    )


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

    # Auswahlliste der Rolle ergaenzen (nur Oberflaechen-Hilfe).
    optionen = _optionen(bind)
    if optionen and ROLLE not in optionen:
        _optionen_schreiben(bind, [*optionen, ROLLE])


def downgrade() -> None:
    bind = op.get_bind()

    optionen = _optionen(bind)
    if ROLLE in optionen:
        _optionen_schreiben(bind, [o for o in optionen if o != ROLLE])

    if not _hat_tabelle(bind, TABELLE):
        return
    bind.execute(sa.text(f"DELETE FROM {TABELLE} WHERE vermerk = :v"), {"v": VERMERK})