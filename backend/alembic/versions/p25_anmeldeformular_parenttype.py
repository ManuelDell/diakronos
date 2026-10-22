"""P2-5/OP-ADMIN-19: `parenttype` der Anmeldeformular-Kindzeilen richtigstellen.

Revision ID: p25_anmeldeformular_parenttype
Revises: n9b_datenschutz_pub
Create Date: 2026-10-18

Befund OP-ADMIN-19 (Nachtpruefung 16.10.): Die Spalte „Felder“ der
Formularliste zeigte immer „–“; ein Formular war nicht zu oeffnen, zu aendern
oder zu loeschen, obwohl der Schreib-Endpunkt existiert.

Ursache: Beim Anlegen der Kindzeilen schrieb `_child_insert`
(`frappe_compat/api_helpers.py`) als `parenttype` den Namen der KIND-Tabelle
(„Anmeldeformular Feld“) statt den des ELTERN-DocTypes („Anmeldeformular“).
Frappe setzt dort immer den Eltern-DocType; die Zeilen waren damit fuer jede
Kind-Tabellen-Abfrage unsichtbar — obwohl sie in der Datenbank standen. Der
Code ist an der Ursache behoben (Zuordnung `_PARENTTYPE`).

Diese Migration raeumt die bereits geschriebenen Zeilen auf: sie setzt
`parenttype` auf den DocType des Elternteils, zu dem die Zeile ueber `parent`
gehoert. Idempotent — ohne falsche Zeilen passiert nichts.

Wichtig: Die Zeilen werden NICHT geloescht. Die `name`-Werte koennen in
`anmeldung_antwort` referenziert sein (Antworten einer Anmeldung zeigen auf
`Anmeldeformular Feld`-Namen); ein Loeschen und Neuanlegen wuerde diese
Verweise brechen.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "p25_anmeldeformular_parenttype"
down_revision: Union[str, None] = "n9b_datenschutz_pub"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

#: Kind-Tabelle -> richtiger `parenttype`. Dieselbe Zuordnung wie in
#: `diakronos_app.frappe_compat.api_helpers._PARENTTYPE`; hier bewusst als
#: eigene Liste, weil eine Migration den Stand von damals festschreibt und
#: nicht von spaeterem Anwendungscode abhaengen darf.
_PARENTTYPE = {
    "anmeldeformular_feld": "Anmeldeformular",
    "anmeldeformular_dokument": "Anmeldeformular",
}

def _hat_tabelle(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def upgrade() -> None:
    verbindung = op.get_bind()
    for tabelle, eltern in _PARENTTYPE.items():
        if not _hat_tabelle(tabelle):
            continue
        verbindung.execute(
            sa.text(
                f"UPDATE {tabelle} SET parenttype = :eltern "  # noqa: S608 — Tabellenname aus fester Liste
                "WHERE parenttype IS DISTINCT FROM :eltern"
            ),
            {"eltern": eltern},
        )


def downgrade() -> None:
    """Keine Umkehrung.

    Der alte Wert (der Name der Kind-Tabelle) ist ein Fehler, nicht ein
    Zustand: ihn wiederherzustellen wuerde die Zeilen erneut unsichtbar
    machen. Die Migration ist insofern einseitig — `downgrade` ist bewusst
    leer, damit ein Ruecklauf die Daten nicht erneut beschaedigt.
    """
    return
