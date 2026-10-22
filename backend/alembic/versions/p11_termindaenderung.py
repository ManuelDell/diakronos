"""P1-1: offener Aenderungsvorschlag zu einem festgelegten Termin.

Revision ID: p11_termindaenderung
Revises: p04_reglink_token
Create Date: 2026-10-16

Operator-Entscheidung 16.10. (P1-1, verbindlich): Ein Nicht-Moderator mit
Schreibrecht darf einen bereits FESTGELEGTEN Termin nur in Kleinigkeiten
(Beschreibung, Notiz) sofort aendern. Aenderungen an Datum, Uhrzeit, Ort/
Ressource oder Kalender bleiben am Termin unwirksam — der Termin bleibt in
der alten Fassung sichtbar, die Aenderung wartet als Vorschlag auf die
Freigabe (Moderator sieht alt/neu, Freigabe uebernimmt, Ablehnung verwirft).

Dafuer legt diese Migration die Tabelle ``element_aenderung`` an (ein offener
Vorschlag je Termin; der neuere ersetzt den aelteren).

P1-1b (Befund W3): Die Zeile traegt jetzt einen Fremdschluessel auf
``element.name`` mit ``ON DELETE CASCADE`` — Modell und Migration waren sich
vorher uneinig (Modell: FK ohne Regel, Migration: gar kein FK). Damit
verschwindet ein offener Vorschlag mit seinem Termin; das ausdrueckliche
Aufraeumen in `delete_event`/Serien-Loeschung bleibt als zweite Linie.

Idempotent: laeuft auf frischer UND bestehender DB sauber (``IF NOT EXISTS``
fuer Tabelle und Indizes; der FK wird nur angelegt, wenn die Tabelle neu
entsteht oder er fehlt). ``downgrade`` entfernt die Tabelle wieder.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "p11_termindaenderung"
down_revision: Union[str, None] = "p04_reglink_token"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _tabelle_existiert(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def _fremdschluessel_existiert(tabelle: str, name: str) -> bool:
    """Traegt `tabelle` schon einen Fremdschluessel `name`?"""
    if not _tabelle_existiert(tabelle):
        return False
    for fk in sa.inspect(op.get_bind()).get_foreign_keys(tabelle):
        if fk.get("name") == name:
            return True
    return False


_FK_NAME = "fk_element_aenderung_element"
_FK_KALENDER_NAME = "fk_element_aenderung_element_calendar"


def upgrade() -> None:
    if _tabelle_existiert("element_aenderung"):
        pass
    else:
        op.create_table(
            "element_aenderung",
            sa.Column("name", sa.String(length=140), primary_key=True),
            sa.Column("creation", sa.DateTime(timezone=False), nullable=True),
            sa.Column("modified", sa.DateTime(timezone=False), nullable=True),
            sa.Column("modified_by", sa.String(length=140), nullable=True),
            sa.Column("owner", sa.String(length=140), nullable=True),
            sa.Column("docstatus", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("idx", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("element", sa.String(length=140), nullable=True),
            sa.Column("element_calendar", sa.String(length=140), nullable=True),
            sa.Column("antragsteller", sa.String(length=140), nullable=True),
            sa.Column("vorschlag", sa.Text(), nullable=True),
        )
        op.create_index(
            "ix_element_aenderung_element", "element_aenderung", ["element"]
        )

    # P1-1b (Befund W3): Fremdschluessel wie im Modell. Auf einer frischen DB
    # ueber create_foreign_key, auf einer bestehenden (Tabelle aus dem
    # P1-1-Stand) ebenfalls nachziehbar. SQLite kennt kein ALTER TABLE ADD
    # CONSTRAINT; dort ist der FK ohnehin nur mit aktivierter FKs wirksam —
    # das ausdrueckliche Aufraeumen deckt diesen Fall ab.
    if op.get_bind().dialect.name == "sqlite":
        return
    # N4: Auf einer bestehenden P1-1-Tabelle koennen Waisen stehen (der Termin
    # wurde vor dem FK geloescht). Postgres lehnt die FK-Anlage dann ab;
    # vorher aufraeumen.
    op.execute(
        "DELETE FROM element_aenderung WHERE element IS NOT NULL "
        "AND element NOT IN (SELECT name FROM element)"
    )
    op.execute(
        "DELETE FROM element_aenderung WHERE element_calendar IS NOT NULL "
        "AND element_calendar NOT IN (SELECT name FROM kalender)"
    )
    if not _fremdschluessel_existiert("element_aenderung", _FK_NAME):
        op.create_foreign_key(
            _FK_NAME,
            "element_aenderung",
            "element",
            ["element"],
            ["name"],
            ondelete="CASCADE",
        )
    if not _fremdschluessel_existiert("element_aenderung", _FK_KALENDER_NAME):
        op.create_foreign_key(
            _FK_KALENDER_NAME,
            "element_aenderung",
            "kalender",
            ["element_calendar"],
            ["name"],
        )


def downgrade() -> None:
    if not _tabelle_existiert("element_aenderung"):
        return
    if op.get_bind().dialect.name != "sqlite":
        for fk_name in (_FK_KALENDER_NAME, _FK_NAME):
            if _fremdschluessel_existiert("element_aenderung", fk_name):
                op.drop_constraint(fk_name, "element_aenderung", type_="foreignkey")
    op.drop_index("ix_element_aenderung_element", table_name="element_aenderung")
    op.drop_table("element_aenderung")
