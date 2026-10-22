"""N5: Einmalige Passwort-Links und verpflichtender Erstwechsel."""
from alembic import op
import sqlalchemy as sa

revision = "n5_passwortzugang"
down_revision = "p32_datenbereinigung"
branch_labels = None
depends_on = None


def upgrade():
    if not sa.inspect(op.get_bind()).has_table("passwortzugang"):
        op.create_table(
            "passwortzugang",
            sa.Column("user", sa.String(140), sa.ForeignKey("user.name", ondelete="CASCADE"), primary_key=True),
            sa.Column("wechsel_noetig", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("token_hash", sa.String(64), nullable=True, unique=True),
            sa.Column("gueltig_bis", sa.DateTime(), nullable=True),
        )


def downgrade():
    op.drop_table("passwortzugang")
