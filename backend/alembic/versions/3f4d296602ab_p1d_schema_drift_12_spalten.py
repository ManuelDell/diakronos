"""p1d schema drift 12 spalten

Revision ID: 3f4d296602ab
Revises: p1bmodelle
Create Date: 2026-09-24 21:49:09.791540

Bringt das Ziel-Schema auf den Stand der laufenden Frappe-DB: die 12 Spalten
aus Schema-Nachtrag der Portierung (siehe Schema-Drift-Nachtrag).

Erzeugt per `alembic revision --autogenerate` gegen eine Wegwerf-DB, die
vorher auf `p1bmodelle` stand — das Diff enthielt exakt diese 12 Spalten und
2 Fremdschluessel, sonst nichts.

Von Hand ergaenzt (kann Autogenerate nicht sehen):
  * Fremdschluessel-Namen `fk_gruppe_kalender`, `fk_gruppe_obergruppe`
    (das generierte `None` waere im `downgrade()` nicht lauffaehig gewesen), und
  * die Umbenennung `mitglied.stra_e` -> `mitglied.straße`. Autogenerate
    deutet das als Drop+Add und wuerde die Adressdaten wegwerfen; die
    Live-DB fuehrt die Spalte wortgleich `straße` (siehe SCHEMA_DRIFT.md).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "3f4d296602ab"
down_revision: Union[str, None] = "p1bmodelle"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("anmeldung", sa.Column("name_freitext", sa.Text(), nullable=True))
    op.add_column("anmeldung", sa.Column("email_freitext", sa.Text(), nullable=True))

    op.add_column(
        "dienstbereich",
        sa.Column("ministry_leader", sa.String(length=140), nullable=True),
    )
    op.add_column(
        "dienstbereich",
        sa.Column("ministry_read_role", sa.String(length=140), nullable=True),
    )

    # `widerrufen` ist eine echte Ja/Nein-Spalte. NOT NULL braucht einen
    # server_default, sonst scheitert das ALTER auf gefuellter Tabelle.
    op.add_column(
        "dsgvo_einwilligung",
        sa.Column("einwilligungstext", sa.Text(), nullable=True),
    )
    op.add_column(
        "dsgvo_einwilligung",
        sa.Column(
            "widerrufen",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "dsgvo_einwilligung",
        sa.Column("widerruf_datum", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "dsgvo_einwilligung",
        sa.Column("widerruf_begruendung", sa.Text(), nullable=True),
    )

    op.add_column("element", sa.Column("auto_repeat", sa.String(length=140), nullable=True))

    op.add_column("gruppe", sa.Column("leiter", sa.String(length=140), nullable=True))
    op.add_column("gruppe", sa.Column("obergruppe", sa.String(length=140), nullable=True))
    op.add_column("gruppe", sa.Column("kalender", sa.String(length=140), nullable=True))

    op.create_foreign_key(
        "fk_gruppe_kalender", "gruppe", "kalender", ["kalender"], ["name"]
    )
    op.create_foreign_key(
        "fk_gruppe_obergruppe", "gruppe", "gruppe", ["obergruppe"], ["name"]
    )

    # Umlaut-Spalte: der Generator hat `straße` frueher zu `stra_e`
    # verstuemmelt (siehe SCHEMA_DRIFT.md). Die Live-DB fuehrt `straße` —
    # umbenennen, nicht neu anlegen, damit die Adressdaten erhalten bleiben.
    op.alter_column("mitglied", "stra_e", new_column_name="straße")


def downgrade() -> None:
    op.alter_column("mitglied", "straße", new_column_name="stra_e")

    op.drop_constraint("fk_gruppe_obergruppe", "gruppe", type_="foreignkey")
    op.drop_constraint("fk_gruppe_kalender", "gruppe", type_="foreignkey")

    op.drop_column("gruppe", "kalender")
    op.drop_column("gruppe", "obergruppe")
    op.drop_column("gruppe", "leiter")

    op.drop_column("element", "auto_repeat")

    op.drop_column("dsgvo_einwilligung", "widerruf_begruendung")
    op.drop_column("dsgvo_einwilligung", "widerruf_datum")
    op.drop_column("dsgvo_einwilligung", "widerrufen")
    op.drop_column("dsgvo_einwilligung", "einwilligungstext")

    op.drop_column("dienstbereich", "ministry_read_role")
    op.drop_column("dienstbereich", "ministry_leader")

    op.drop_column("anmeldung", "email_freitext")
    op.drop_column("anmeldung", "name_freitext")
