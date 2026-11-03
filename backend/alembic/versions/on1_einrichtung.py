"""ON-1 — Alembic-Migration: Tabelle `einrichtung_token`.

Was diese Migration tut
-----------------------
Legt die Tabelle `einrichtung_token` an: den EINRICHTUNGS-Token der
Ersteinrichtung (Karte ON-1). Gespeichert wird nur `sha256(<Token>)`; die
Tabelle hat hoechstens EINE Zeile (fester `name` = ``Ersteinrichtung``), weil
der fachliche Zustand „es gibt einen gueltigen Link oder keinen" ist.

Sie legt KEINE Zeile an: existiert kein Token, ist der Einrichtungsweg einfach
noch nicht beschritten. Der Token entsteht beim Start
(`erstinstallation.bootstrap_erstinstallation`) oder ueber
`python -m diakronos_app.einrichtung link`.

Idempotent
----------
`upgrade` legt die Tabelle nur an, wenn sie fehlt (mit dem Unique-Constraint
`uq_einrichtung_token_hash`) und ergaenzt ihn nur, wenn er fehlt. `downgrade`
entfernt beides; ein fehlender Index ist kein Fehler. Eine bestehende
Installation (Benutzer vorhanden) bekommt die leere Tabelle und merkt sonst
nichts.

Einziger Head
-------------
`down_revision = "on2_einrichtung"` — ON-2b liegt seit dem Merge in main davor,
die Kette hat weiterhin genau einen Kopf.

Revision ID: on1_einrichtung
Revises: on2_einrichtung
Create Date: 2026-11-01
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "on1_einrichtung"
down_revision: Union[str, None] = "on2_einrichtung"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABELLE = "einrichtung_token"
INDEX_HASH = "uq_einrichtung_token_hash"


def _tabelle_namen(insp) -> set[str]:
    """Alle Tabellennamen der Datenbank, klein geschrieben.

    ON-1: ``get_table_names(schema="public")`` NUR auf PostgreSQL. Auf SQLite
    gibt es kein Schema `public`; SQLAlchemy uebersetzt es zu
    ``public.sqlite_master`` und die Abfrage scheitert mit
    ``no such table: public.sqlite_master`` (im Rundlauf-Test aufgefallen).
    """
    namen = {str(k).lower() for k in insp.get_table_names()}
    if insp.bind is not None and insp.bind.dialect.name == "postgresql":
        namen |= {str(k).lower() for k in insp.get_table_names(schema="public")}
    return namen


def _hat_tabelle(bind, name: str) -> bool:
    """Case-insensibler Tabellentest (Frappe legt klein an, Modelle schreiben gross)."""
    return str(name).lower() in _tabelle_namen(sa.inspect(bind))


def _hat_eindeutigkeit(bind, tabelle: str, name: str) -> bool:
    """Gibt es Constraint ODER Index dieses Namens schon? (Namensraum teilen sie)

    PostgreSQL legt den Index eines Unique-Constraints unter DEMSELBEN Namen
    an — ein zweites `ADD CONSTRAINT` scheitert mit „relation … already
    exists“. Deshalb zaehlt jede Fundstelle als „schon da“.
    """
    insp = sa.inspect(bind)
    for kandidat in insp.get_table_names():
        if str(kandidat).lower() != str(tabelle).lower():
            continue
        if any(
            str(ix.get("name") or "").lower() == str(name).lower()
            for ix in insp.get_indexes(str(kandidat))
        ):
            return True
        if any(
            str(c.get("name") or "").lower() == str(name).lower()
            for c in insp.get_unique_constraints(str(kandidat))
        ):
            return True
    return False


def _hat_eigenen_index(bind, tabelle: str, name: str) -> bool:
    """Steht ein SELBSTSTAENDIGER Index (ohne Constraint) dieses Namens da?"""
    insp = sa.inspect(bind)
    for kandidat in insp.get_table_names():
        if str(kandidat).lower() != str(tabelle).lower():
            continue
        if any(
            str(ix.get("name") or "").lower() == str(name).lower()
            for ix in insp.get_indexes(str(kandidat))
            if ix.get("duplicates_constraint") in (None, "")
        ):
            return True
    return False


def upgrade() -> None:
    bind = op.get_bind()

    if not _hat_tabelle(bind, TABELLE):
        op.create_table(
            TABELLE,
            sa.Column("name", sa.String(length=140), nullable=False),
            sa.Column("token_hash", sa.String(length=64), nullable=False),
            sa.Column("gueltig_bis", sa.DateTime(timezone=False), nullable=False),
            sa.Column("angelegt_am", sa.DateTime(timezone=False), nullable=False),
            sa.Column(
                "aufrufe",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("0"),
            ),
            sa.PrimaryKeyConstraint("name"),
            # Der Hash ist eindeutig UND der Suchschluessel. Bewusst als
            # TABLE-CONSTRAINT (wie im Modell, `__table_args__`): ein
            # `create_index(unique=True)` legt einen INDEX an, das Modell sagt
            # „UniqueConstraint“ — `alembic check` meldete dann dauerhaft
            # „remove_index + add_constraint“ (im Rundlauf gegen PostgreSQL
            # gemessen). Auf beiden Datenbanken ist der Effekt derselbe.
            sa.UniqueConstraint("token_hash", name=INDEX_HASH),
        )

    # Nachziehen fuer Datenbanken, auf denen eine fruehere Fassung dieser
    # Migration schon lief (dort steht noch ein selbststaendiger INDEX statt
    # des Constraints). Auf PostgreSQL meldet `get_indexes` den Index eines
    # Constraints als „duplicates_constraint" — dieselbe Kennung heisst dort
    # also „Constraint schon da“, deshalb der zweite Blick.
    if not _hat_eindeutigkeit(bind, TABELLE, INDEX_HASH):
        op.create_unique_constraint(INDEX_HASH, TABELLE, ["token_hash"])


def downgrade() -> None:
    """Nimmt die Tabelle samt Eindeutigkeit zurueck.

    Der Unique-Constraint verschwindet MIT der Tabelle — ein zusaetzliches
    `drop_index` scheitert auf PostgreSQL („cannot drop index … because
    constraint … requires it“, im Rundlauf gemessen). Nur eine ALTE Fassung
    dieser Migration legte einen selbststaendigen INDEX an; ein solcher wird
    vorher entfernt.
    """
    bind = op.get_bind()
    if not _hat_tabelle(bind, TABELLE):
        return
    insp = sa.inspect(bind)
    if insp.dialect.name != "postgresql":
        # SQLite kennt keine benannten Constraints: dort ist der Index das
        # Objekt, das vor dem Loeschen der Tabelle weg muss.
        if _hat_eigenen_index(bind, TABELLE, INDEX_HASH):
            op.drop_index(INDEX_HASH, table_name=TABELLE)
    op.drop_table(TABELLE)
