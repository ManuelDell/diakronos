"""Run ONLY against a disposable PostgreSQL DB (G1a migration acceptance).

    DATABASE_URL=... G1A_DISPOSABLE_DB=1 PYTHONPATH=src python scripts/g1a_migration_check.py

No entrypoint, live database, Redis, or Google traffic. Contains only test values.
"""
import os
import subprocess

from sqlalchemy import create_engine, text

assert os.environ.get("G1A_DISPOSABLE_DB") == "1", "Disposable DB confirmation missing"
assert "g1a-postgres" in os.environ["DATABASE_URL"], "Not the isolated G1a test DB"


def migrate(*args):
    subprocess.run(["alembic", *args], check=True)


engine = create_engine(os.environ["DATABASE_URL"])
migrate("upgrade", "a1a_password")
with engine.begin() as db:
    db.execute(text("DELETE FROM google_kalender_einstellungen"))
    db.execute(text("""INSERT INTO google_kalender_einstellungen
        (name, docstatus, idx, authorized, client_id, client_secret, token_data)
        VALUES ('Google Kalender Einstellungen', 0, 0, true, 'test-client',
                'test-legacy-secret', '{"access_token":"test-legacy-token"}')"""))
migrate("upgrade", "head")
from diakronos_app.google_secrets import decrypt_secret
with engine.connect() as db:
    row = db.execute(text("SELECT client_secret, token_data FROM google_kalender_einstellungen")).one()
    assert row.client_secret.startswith("fernet:v1:") and row.token_data.startswith("fernet:v1:")
    assert decrypt_secret(row.client_secret) == "test-legacy-secret"
    assert decrypt_secret(row.token_data) == '{"access_token":"test-legacy-token"}'
migrate("check")
migrate("downgrade", "a1a_password")
with engine.connect() as db:
    row = db.execute(text("SELECT client_secret, token_data, authorized FROM google_kalender_einstellungen")).one()
    assert row.client_secret is None and row.token_data is None and not row.authorized
migrate("upgrade", "head")
migrate("check")
print("G1a PostgreSQL: legacy encryption, upgrade, downgrade without plaintext, alembic check OK")
