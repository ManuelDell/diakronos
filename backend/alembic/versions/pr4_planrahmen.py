"""Plan-Rahmen: PR4-Erweiterungen (Umfang, Engine-Kontext, globaler Verlauf)

Revision ID: pr4_planrahmen
Revises: pr3_planrahmen
Create Date: 2026-10-08

Vier Bloecke:

1. **pr_sammlung** — `umfang` ('gemeinde' Vorgabe | 'plan') + `plan` (FK auf
   pr_plan, CASCADE). Konsistenz-Check: umfang='plan' genau dann, wenn plan
   gesetzt ist. Der fruehere Unique auf `schluessel` wird ersetzt durch
   Unique `(schluessel, plan)` plus partiellen Unique-Index
   `schluessel WHERE plan IS NULL`.

2. **pr_termin** — Engine-Kontext-Spalten (konsistent zu
   `planrahmen/engine/modell.py::Termin`): `reihe` (default 'standard'),
   `bezug` (Self-FK, SET NULL), `ablauf` (JSONB, default '{}') sowie
   `index` (0) / `positionsnr_im_monat` (1) / `position_von_hinten` (1).
   `plantyp_version` wird NOT NULL: vorhandene NULLs werden anhand
   `pr_plan.plantyp` und der hoechsten Version mit `gueltig_ab <= datum`
   aufgeloest. Nicht aufloesbare Termine brechen die Migration AB (fail
   closed) — es wird keine erfundene Definition vergeben; der ganze Lauf
   rollt transaktionsweise zurueck.

3. **pr_verlauf** — `plan` wird optional (globale Schreibdienste schreiben
   ohne Plan), neue `plantyp`-Spalte (FK auf pr_plantyp, SET NULL).
   `gruppe_id` (Undo-Einheit) besteht unveraendert fuer alle Dienste.

4. **pr_plan** — neue JSONB-Spalte `veroeffentlichter_stand` (nullable):
   beim Veroeffentlichen eingefrorener Schnappschuss, den die API
   Nichtberechtigten immer liefert.

Die Unveraenderlichkeits-RESTRICT-FKs (`pr_termin.plantyp_version` ->
pr_plantyp_version) bleiben unangetastet (Snapshot/Undo, P4).
"""

from datetime import datetime
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "pr4_planrahmen"
down_revision: Union[str, None] = "pr3_planrahmen"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 1. pr_sammlung: Umfang + planbezug ─────────────────────────────────
    op.add_column(
        "pr_sammlung",
        sa.Column("umfang", sa.String(length=40), nullable=False, server_default="gemeinde"),
    )
    op.add_column("pr_sammlung", sa.Column("plan", sa.String(length=36), nullable=True))
    op.create_index(op.f("ix_pr_sammlung_plan"), "pr_sammlung", ["plan"], unique=False)
    op.create_foreign_key(
        "fk_pr_sammlung_plan",
        "pr_sammlung", "pr_plan", ["plan"], ["id"],
        ondelete="CASCADE",
    )
    # Alt-Bestand ist per Definition gemeinde-weit: umfang='gemeinde' (Default),
    # plan=NULL — beide Checks sind damit sofort erfuelbar.
    op.create_check_constraint(
        "ck_pr_sammlung_umfang_werte", "pr_sammlung", "umfang IN ('gemeinde', 'plan')"
    )
    op.create_check_constraint(
        "ck_pr_sammlung_umfang_plan", "pr_sammlung", "(umfang = 'plan') = (plan IS NOT NULL)"
    )
    op.drop_constraint("uq_pr_sammlung_schluessel", "pr_sammlung", type_="unique")
    op.create_unique_constraint(
        "uq_pr_sammlung_schluessel_plan", "pr_sammlung", ["schluessel", "plan"]
    )
    # PostgreSQL laesst NULLs in Unique-Constraints als distinct gelten; der
    # partielle Index schliesst doppelte gemeinde-weite schluessel aus.
    op.create_index(
        "uq_pr_sammlung_schluessel_ohne_plan",
        "pr_sammlung",
        ["schluessel"],
        unique=True,
        postgresql_where=sa.text("plan IS NULL"),
    )

    # ── 2. pr_termin: Engine-Kontext + plantyp_version Pflicht ─────────────
    op.add_column(
        "pr_termin",
        sa.Column("reihe", sa.String(length=140), nullable=False, server_default="standard"),
    )
    op.add_column("pr_termin", sa.Column("bezug", sa.String(length=36), nullable=True))
    op.add_column(
        "pr_termin",
        sa.Column("ablauf", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.add_column(
        "pr_termin", sa.Column("index", sa.Integer(), nullable=False, server_default="0")
    )
    op.add_column(
        "pr_termin",
        sa.Column("positionsnr_im_monat", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "pr_termin",
        sa.Column("position_von_hinten", sa.Integer(), nullable=False, server_default="1"),
    )
    op.create_index(op.f("ix_pr_termin_bezug"), "pr_termin", ["bezug"], unique=False)
    op.create_foreign_key(
        "fk_pr_termin_bezug",
        "pr_termin", "pr_termin", ["bezug"], ["id"],
        ondelete="SET NULL",
    )

    # Backfill: vorhandene NULLs anhand pr_plan.plantyp aufloesen — die hoechste
    # Version mit gueltig_ab <= termin.datum gewinnt (wie
    # planrahmen/speicher.gueltige_version_zu_datum). Danach faellt die
    # Pruefung: was nicht aufloesbar ist, bricht die Migration ab (fail closed,
    # keine erfundene Definition).
    op.execute(
        sa.text(
            """
            UPDATE pr_termin
            SET plantyp_version = (
                SELECT pv.id
                FROM pr_plan p
                JOIN pr_plantyp_version pv ON pv.plantyp = p.plantyp
                WHERE p.id = pr_termin.plan
                  AND pv.gueltig_ab <= pr_termin.datum
                ORDER BY pv.gueltig_ab DESC, pv.versionsnummer DESC
                LIMIT 1
            )
            WHERE pr_termin.plantyp_version IS NULL
            """
        )
    )
    # Offline-SQL-Modus (`alembic upgrade --sql`) kann nicht fetchen; die
    # Pruefung laeuft deshalb nur online und rollt im Fehlerfall alles zurück.
    if not op.get_context().as_sql:
        verwaist = op.get_bind().execute(
            sa.text(
                "SELECT t.id, t.datum, t.plan, p.plantyp "
                "FROM pr_termin t JOIN pr_plan p ON p.id = t.plan "
                "WHERE t.plantyp_version IS NULL ORDER BY t.datum, t.id"
            )
        ).fetchall()
        if verwaist:
            details = ", ".join(
                f"termin={tid} datum={datum} plan={pid} plantyp={ptid}"
                for tid, datum, pid, ptid in verwaist
            )
            raise RuntimeError(
                "PR4-Migration abgebrochen (fail closed): fuer diese Termine "
                "gibt es keine Plantyp-Version mit gueltig_ab <= Datum — "
                f"{details}. Es wird keine erfundene Definition vergeben; "
                "bitte zuerst eine passende Version anlegen bzw. die Termine "
                "bereinigen."
            )
    op.alter_column(
        "pr_termin", "plantyp_version",
        existing_type=sa.String(length=36), nullable=False,
    )
    op.create_index(op.f("ix_pr_termin_plantyp_version"), "pr_termin", ["plantyp_version"], unique=False)

    # ── 3. pr_verlauf: globale Schreibdienste (ohne Plan) ──────────────────
    op.alter_column(
        "pr_verlauf", "plan",
        existing_type=sa.String(length=36), nullable=True,
    )
    op.add_column("pr_verlauf", sa.Column("plantyp", sa.String(length=36), nullable=True))
    op.create_index(op.f("ix_pr_verlauf_plantyp"), "pr_verlauf", ["plantyp"], unique=False)
    op.create_foreign_key(
        "fk_pr_verlauf_plantyp",
        "pr_verlauf", "pr_plantyp", ["plantyp"], ["id"],
        ondelete="SET NULL",
    )

    # ── 4. pr_plan: veroeffentlichter Stand ────────────────────────────────
    op.add_column(
        "pr_plan", sa.Column("veroeffentlichter_stand", postgresql.JSONB(), nullable=True)
    )


def downgrade() -> None:
    """PR3 nur wiederherstellen, wenn dessen Einschränkungen erfüllt sind."""
    bind = op.get_bind()
    globale_verlaeufe = bind.execute(sa.text(
        "SELECT count(*) FROM pr_verlauf WHERE plan IS NULL"
    )).scalar_one()
    doppelte_schluessel = bind.execute(sa.text(
        "SELECT count(*) FROM (SELECT schluessel FROM pr_sammlung "
        "GROUP BY schluessel HAVING count(*) > 1) AS mehrfach"
    )).scalar_one()
    if globale_verlaeufe or doppelte_schluessel:
        raise RuntimeError("PR3: vorhandene PR4-Daten sind nicht darstellbar; Downgrade abgebrochen")
    op.drop_column("pr_plan", "veroeffentlichter_stand")

    op.drop_constraint("fk_pr_verlauf_plantyp", "pr_verlauf", type_="foreignkey")
    op.drop_index(op.f("ix_pr_verlauf_plantyp"), table_name="pr_verlauf")
    op.drop_column("pr_verlauf", "plantyp")
    op.alter_column(
        "pr_verlauf", "plan",
        existing_type=sa.String(length=36), nullable=False,
    )

    op.drop_index(op.f("ix_pr_termin_plantyp_version"), table_name="pr_termin")
    op.alter_column(
        "pr_termin", "plantyp_version",
        existing_type=sa.String(length=36), nullable=True,
    )
    op.drop_constraint("fk_pr_termin_bezug", "pr_termin", type_="foreignkey")
    op.drop_index(op.f("ix_pr_termin_bezug"), table_name="pr_termin")
    for spalte in (
        "bezug", "reihe", "ablauf", "index", "positionsnr_im_monat", "position_von_hinten",
    ):
        op.drop_column("pr_termin", spalte)

    op.drop_index("uq_pr_sammlung_schluessel_ohne_plan", table_name="pr_sammlung")
    op.drop_constraint("uq_pr_sammlung_schluessel_plan", "pr_sammlung", type_="unique")
    # Wiederherstellung des PR3-Zustands: erneut Unique auf schluessel.
    op.create_unique_constraint("uq_pr_sammlung_schluessel", "pr_sammlung", ["schluessel"])
    op.drop_constraint("ck_pr_sammlung_umfang_plan", "pr_sammlung", type_="check")
    op.drop_constraint("ck_pr_sammlung_umfang_werte", "pr_sammlung", type_="check")
    op.drop_constraint("fk_pr_sammlung_plan", "pr_sammlung", type_="foreignkey")
    op.drop_index(op.f("ix_pr_sammlung_plan"), table_name="pr_sammlung")
    op.drop_column("pr_sammlung", "plan")
    op.drop_column("pr_sammlung", "umfang")
