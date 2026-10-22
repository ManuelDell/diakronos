"""G1a: widen client_secret for Fernet and encrypt legacy secrets/tokens.

Downgrade deliberately clears credentials instead of restoring plaintext.
SECRET_KEY must remain stable (and be backed up with the database).
"""
from alembic import op
import sqlalchemy as sa

revision = "g1a_google_secrets"
down_revision = "a1a_password"
branch_labels = None
depends_on = None


def upgrade():
    from diakronos_app.google_secrets import PREFIX, decrypt_secret, encrypt_secret

    op.alter_column("google_kalender_einstellungen", "client_secret",
                    existing_type=sa.String(255), type_=sa.Text(), existing_nullable=True)
    table = sa.table("google_kalender_einstellungen", sa.column("name", sa.String),
                     sa.column("client_secret", sa.Text), sa.column("token_data", sa.Text))
    connection = op.get_bind()
    for row in connection.execute(sa.select(table)).mappings():
        values = {}
        for field in ("client_secret", "token_data"):
            value = row[field]
            if value:
                if value.startswith(PREFIX):
                    decrypt_secret(value)  # Wrong key/corrupt ciphertext: fail closed.
                else:
                    values[field] = encrypt_secret(value)
        if values:
            connection.execute(table.update().where(table.c.name == row["name"]).values(**values))


def downgrade():
    table = sa.table("google_kalender_einstellungen", sa.column("client_secret", sa.Text),
                     sa.column("token_data", sa.Text), sa.column("authorized", sa.Boolean))
    op.get_bind().execute(table.update().values(client_secret=None, token_data=None, authorized=False))
    op.alter_column("google_kalender_einstellungen", "client_secret",
                    existing_type=sa.Text(), type_=sa.String(255), existing_nullable=True)
