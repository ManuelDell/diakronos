"""Plan-Rahmen: Tabellen pr_* (PR3)

Revision ID: pr3_planrahmen
Revises: g1a_google_secrets
Create Date: 2026-10-07

Legt die generischen Plan-Rahmen-Tabellen an (Chorplan, Freizeitplan,
Predigerplan ...). Sie sind NICHT von `tools/gen_models.py` erzeugt und werden
nicht ueber den generischen Frappe-Resource-CRUD erreichbar sein (Modul
`diakronos_app/models/planrahmen.py` + Sperre in `frappe_compat/router.py`).

JSON-Spalten sind hier echtes JSONB (PostgreSQL); die Modelle fallen fuer die
In-Memory-SQLite-Testsuite auf generisches JSON zurueck.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from datetime import datetime


# revision identifiers, used by Alembic.
revision: str = "pr3_planrahmen"
down_revision: Union[str, None] = "g1a_google_secrets"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _stempel() -> list:
    """Gemeinsamer created/modified/created_by-Block der pr_*-Tabellen."""
    return [
        sa.Column("created", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("modified", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.String(length=140), nullable=True),
    ]


def upgrade() -> None:
    op.create_table(
        "pr_plantyp",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("schluessel", sa.String(length=140), nullable=False),
        sa.Column("name", sa.String(length=140), nullable=False),
        sa.Column("bereich", sa.String(length=140), nullable=True),
        sa.Column("aktiv", sa.Boolean(), nullable=False),
        *_stempel(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("schluessel", name="uq_pr_plantyp_schluessel"),
    )

    op.create_table(
        "pr_plantyp_version",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("plantyp", sa.String(length=36), nullable=False),
        sa.Column("versionsnummer", sa.Integer(), nullable=False),
        sa.Column("gueltig_ab", sa.Date(), nullable=False),
        sa.Column("definition", postgresql.JSONB(), nullable=False),
        sa.Column("schema_version", sa.String(length=40), nullable=False),
        sa.Column("erstellt_von", sa.String(length=140), nullable=True),
        sa.Column("kommentar", sa.Text(), nullable=True),
        *_stempel(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("plantyp", "versionsnummer", name="uq_pr_plantyp_version_plantyp_nr"),
    )
    op.create_index(op.f("ix_pr_plantyp_version_plantyp"), "pr_plantyp_version", ["plantyp"], unique=False)

    op.create_table(
        "pr_plan",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("plantyp", sa.String(length=36), nullable=False),
        sa.Column("titel", sa.String(length=280), nullable=False),
        sa.Column("zeitraum_von", sa.Date(), nullable=True),
        sa.Column("zeitraum_bis", sa.Date(), nullable=True),
        sa.Column("parameter", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("verantwortlich", sa.String(length=140), nullable=True),
        *_stempel(),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_pr_plan_plantyp"), "pr_plan", ["plantyp"], unique=False)

    op.create_table(
        "pr_termin",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("plan", sa.String(length=36), nullable=False),
        sa.Column("datum", sa.Date(), nullable=False),
        sa.Column("uhrzeit", sa.Time(), nullable=True),
        sa.Column("titel", sa.String(length=280), nullable=True),
        sa.Column("anlaesse", postgresql.JSONB(), nullable=False),
        sa.Column("quelle", sa.String(length=40), nullable=False),
        sa.Column("kronos_element", sa.String(length=140), nullable=True),
        sa.Column("plantyp_version", sa.String(length=36), nullable=True),
        sa.Column("entfaellt", sa.Boolean(), nullable=False),
        *_stempel(),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_pr_termin_plan"), "pr_termin", ["plan"], unique=False)
    op.create_index(op.f("ix_pr_termin_datum"), "pr_termin", ["datum"], unique=False)

    op.create_table(
        "pr_eintrag",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("termin", sa.String(length=36), nullable=False),
        sa.Column("feld_pfad", sa.Text(), nullable=False),
        sa.Column("index", sa.Integer(), nullable=True),
        sa.Column("variante", sa.String(length=140), nullable=True),
        sa.Column("wert", postgresql.JSONB(), nullable=False),
        sa.Column("fixiert", sa.Boolean(), nullable=False),
        sa.Column("quelle", sa.String(length=40), nullable=False),
        sa.Column("meldungen", postgresql.JSONB(), nullable=False),
        *_stempel(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("termin", "feld_pfad", name="uq_pr_eintrag_termin_feld"),
    )
    op.create_index(op.f("ix_pr_eintrag_termin"), "pr_eintrag", ["termin"], unique=False)

    op.create_table(
        "pr_verlauf",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("plan", sa.String(length=36), nullable=False),
        sa.Column("zeitpunkt", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("benutzer", sa.String(length=140), nullable=True),
        sa.Column("aktion", sa.String(length=80), nullable=False),
        sa.Column("vorher", postgresql.JSONB(), nullable=True),
        sa.Column("nachher", postgresql.JSONB(), nullable=True),
        sa.Column("gruppe_id", sa.String(length=36), nullable=True),
        *_stempel(),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_pr_verlauf_plan"), "pr_verlauf", ["plan"], unique=False)
    op.create_index(op.f("ix_pr_verlauf_gruppe_id"), "pr_verlauf", ["gruppe_id"], unique=False)

    op.create_table(
        "pr_merkmal",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("ziel", sa.String(length=140), nullable=False),
        sa.Column("schluessel", sa.String(length=140), nullable=False),
        sa.Column("art", sa.String(length=40), nullable=False),
        sa.Column("definition", postgresql.JSONB(), nullable=False),
        sa.Column("angelegt_durch_plantyp", sa.String(length=36), nullable=True),
        *_stempel(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ziel", "schluessel", name="uq_pr_merkmal_ziel_schluessel"),
    )

    op.create_table(
        "pr_merkmal_wert",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("merkmal", sa.String(length=36), nullable=False),
        sa.Column("ziel_id", sa.String(length=140), nullable=False),
        sa.Column("wert", postgresql.JSONB(), nullable=False),
        *_stempel(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("merkmal", "ziel_id", name="uq_pr_merkmal_wert_merkmal_ziel"),
    )
    op.create_index(op.f("ix_pr_merkmal_wert_merkmal"), "pr_merkmal_wert", ["merkmal"], unique=False)

    op.create_table(
        "pr_sammlung",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("schluessel", sa.String(length=140), nullable=False),
        sa.Column("name", sa.String(length=280), nullable=False),
        sa.Column("definition", postgresql.JSONB(), nullable=False),
        sa.Column("eingebaut", sa.Boolean(), nullable=False),
        *_stempel(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("schluessel", name="uq_pr_sammlung_schluessel"),
    )

    op.create_table(
        "pr_sammlung_eintrag",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("sammlung", sa.String(length=36), nullable=False),
        sa.Column("reihenfolge", sa.Integer(), nullable=False),
        sa.Column("daten", postgresql.JSONB(), nullable=False),
        sa.Column("aktiv", sa.Boolean(), nullable=False),
        *_stempel(),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_pr_sammlung_eintrag_sammlung"), "pr_sammlung_eintrag", ["sammlung"], unique=False)

    op.create_table(
        "pr_abwesenheit",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("mitglied", sa.String(length=140), nullable=False),
        sa.Column("von", sa.Date(), nullable=False),
        sa.Column("bis", sa.Date(), nullable=False),
        sa.Column("grund", sa.Text(), nullable=True),
        sa.Column("nur_plantyp", sa.String(length=140), nullable=True),
        *_stempel(),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_pr_abwesenheit_mitglied"), "pr_abwesenheit", ["mitglied"], unique=False)
    op.create_index(op.f("ix_pr_abwesenheit_von"), "pr_abwesenheit", ["von"], unique=False)
    op.create_index(op.f("ix_pr_abwesenheit_bis"), "pr_abwesenheit", ["bis"], unique=False)

    # ── Foreign Keys (nach allen Tabellen, wie im env.py-Hook ueblich) ──────
    op.create_foreign_key(
        "fk_pr_plantyp_bereich_dienstbereich",
        "pr_plantyp", "dienstbereich", ["bereich"], ["name"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_pr_plantyp_version_plantyp",
        "pr_plantyp_version", "pr_plantyp", ["plantyp"], ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_pr_plan_plantyp",
        "pr_plan", "pr_plantyp", ["plantyp"], ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_pr_plan_verantwortlich_mitglied",
        "pr_plan", "mitglied", ["verantwortlich"], ["name"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_pr_termin_plan",
        "pr_termin", "pr_plan", ["plan"], ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_pr_termin_plantyp_version",
        "pr_termin", "pr_plantyp_version", ["plantyp_version"], ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_pr_eintrag_termin",
        "pr_eintrag", "pr_termin", ["termin"], ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_pr_verlauf_plan",
        "pr_verlauf", "pr_plan", ["plan"], ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_pr_merkmal_plantyp",
        "pr_merkmal", "pr_plantyp", ["angelegt_durch_plantyp"], ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_pr_merkmal_wert_merkmal",
        "pr_merkmal_wert", "pr_merkmal", ["merkmal"], ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_pr_sammlung_eintrag_sammlung",
        "pr_sammlung_eintrag", "pr_sammlung", ["sammlung"], ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_pr_abwesenheit_mitglied",
        "pr_abwesenheit", "mitglied", ["mitglied"], ["name"],
        ondelete="CASCADE",
    )

    # Seed: eingebaute Sammlung 'lieder' (B5). Der Adapter auf die bestehende
    # Tabelle `lied` kommt in einem spaeteren Schritt; hier nur der Datensatz.
    sammlung = sa.table(
        "pr_sammlung",
        sa.column("id", sa.String),
        sa.column("schluessel", sa.String),
        sa.column("name", sa.String),
        sa.column("definition", postgresql.JSONB),
        sa.column("eingebaut", sa.Boolean),
        sa.column("created", sa.DateTime),
        sa.column("modified", sa.DateTime),
        sa.column("created_by", sa.String),
    )
    op.bulk_insert(
        sammlung,
        [
            {
                "id": "00000000-0000-0000-0000-000000000001",
                "schluessel": "lieder",
                "name": "Lieder",
                "definition": {"quelle": "lied", "beschreibung": "Eingebaute Sammlung der Lieder (Psalmos)."},
                "eingebaut": True,
                "created": datetime.now(),
                "modified": datetime.now(),
                "created_by": None,
            }
        ],
    )


def downgrade() -> None:
    op.drop_constraint("fk_pr_abwesenheit_mitglied", "pr_abwesenheit", type_="foreignkey")
    op.drop_constraint("fk_pr_sammlung_eintrag_sammlung", "pr_sammlung_eintrag", type_="foreignkey")
    op.drop_constraint("fk_pr_merkmal_wert_merkmal", "pr_merkmal_wert", type_="foreignkey")
    op.drop_constraint("fk_pr_merkmal_plantyp", "pr_merkmal", type_="foreignkey")
    op.drop_constraint("fk_pr_verlauf_plan", "pr_verlauf", type_="foreignkey")
    op.drop_constraint("fk_pr_eintrag_termin", "pr_eintrag", type_="foreignkey")
    op.drop_constraint("fk_pr_termin_plantyp_version", "pr_termin", type_="foreignkey")
    op.drop_constraint("fk_pr_termin_plan", "pr_termin", type_="foreignkey")
    op.drop_constraint("fk_pr_plan_verantwortlich_mitglied", "pr_plan", type_="foreignkey")
    op.drop_constraint("fk_pr_plan_plantyp", "pr_plan", type_="foreignkey")
    op.drop_constraint("fk_pr_plantyp_version_plantyp", "pr_plantyp_version", type_="foreignkey")
    op.drop_constraint("fk_pr_plantyp_bereich_dienstbereich", "pr_plantyp", type_="foreignkey")

    op.drop_index(op.f("ix_pr_abwesenheit_bis"), table_name="pr_abwesenheit")
    op.drop_index(op.f("ix_pr_abwesenheit_von"), table_name="pr_abwesenheit")
    op.drop_index(op.f("ix_pr_abwesenheit_mitglied"), table_name="pr_abwesenheit")
    op.drop_table("pr_abwesenheit")
    op.drop_index(op.f("ix_pr_sammlung_eintrag_sammlung"), table_name="pr_sammlung_eintrag")
    op.drop_table("pr_sammlung_eintrag")
    op.drop_table("pr_sammlung")
    op.drop_index(op.f("ix_pr_merkmal_wert_merkmal"), table_name="pr_merkmal_wert")
    op.drop_table("pr_merkmal_wert")
    op.drop_table("pr_merkmal")
    op.drop_index(op.f("ix_pr_verlauf_gruppe_id"), table_name="pr_verlauf")
    op.drop_index(op.f("ix_pr_verlauf_plan"), table_name="pr_verlauf")
    op.drop_table("pr_verlauf")
    op.drop_index(op.f("ix_pr_eintrag_termin"), table_name="pr_eintrag")
    op.drop_table("pr_eintrag")
    op.drop_index(op.f("ix_pr_termin_datum"), table_name="pr_termin")
    op.drop_index(op.f("ix_pr_termin_plan"), table_name="pr_termin")
    op.drop_table("pr_termin")
    op.drop_index(op.f("ix_pr_plan_plantyp"), table_name="pr_plan")
    op.drop_table("pr_plan")
    op.drop_index(op.f("ix_pr_plantyp_version_plantyp"), table_name="pr_plantyp_version")
    op.drop_table("pr_plantyp_version")
    op.drop_table("pr_plantyp")
