"""N6: Löschanträge ohne Sofortlöschung."""
from alembic import op
import sqlalchemy as sa

revision = "n6_loeschantrag"
down_revision = "n5_passwortzugang"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "loeschantrag",
        sa.Column("mitglied", sa.String(140), sa.ForeignKey("mitglied.name"), primary_key=True),
        sa.Column("beantragt_am", sa.DateTime(), nullable=False),
        sa.Column("erledigt_am", sa.DateTime(), nullable=True),
        sa.Column("erledigt_von", sa.String(140), nullable=True),
    )


def downgrade():
    op.drop_table("loeschantrag")
