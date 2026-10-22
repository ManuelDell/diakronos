"""DM1 — Migration ``dm1_devmodus``: Tabellen, Modelle, Reihenfolge, downgrade.

Der Test prueft, dass das Migrationsskript und die ORM-Modelle nicht
auseinanderlaufen und dass die Reihenfolge (Uebernahme VOR dem Loeschen der
Testsuite-Tabellen) stimmt.
"""

from __future__ import annotations

import re
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory


def _quelle() -> str:
    ini = Path(__file__).resolve().parents[1] / "alembic.ini"
    cfg = Config(str(ini))
    cfg.set_main_option("script_location", str(ini.parent / "alembic"))
    revision = ScriptDirectory.from_config(cfg).get_revision("dm1_devmodus")
    assert revision is not None
    return Path(revision.path).read_text(encoding="utf-8")


def test_revision_kette():
    ini = Path(__file__).resolve().parents[1] / "alembic.ini"
    cfg = Config(str(ini))
    cfg.set_main_option("script_location", str(ini.parent / "alembic"))
    revision = ScriptDirectory.from_config(cfg).get_revision("dm1_devmodus")
    assert revision.down_revision == "ts1_testsuite"


def test_migration_nennt_tabellen_und_funktionen():
    quelle = _quelle()
    for name in ("dm_sitzung", "dm_ereignis", "dm_befund"):
        assert name in quelle, name
    assert "def upgrade" in quelle and "def downgrade" in quelle
    # Uebernahme MUSS vor dem Loeschen stehen.
    assert quelle.index("_befunde_uebernehmen()") < quelle.index("_testsuite_tabellen_entfernen()")
    for alt in ("ts_befund", "ts_kommentar", "ts_szenario", "ts_ereignis", "ts_sitzung"):
        assert alt in quelle, alt


def test_modelle_passen_zu_den_migrationstabellen():
    from diakronos_app.models.devmodus import DevBefund, DevEreignis, DevSitzung

    quelle = _quelle()
    for modell, tabelle in ((DevSitzung, "dm_sitzung"), (DevEreignis, "dm_ereignis"),
                            (DevBefund, "dm_befund")):
        assert modell.__tablename__ == tabelle
        block_start = quelle.index(f'"{tabelle}"')
        for spalte in modell.__table__.columns.keys():
            if modell.__table__.columns[spalte].primary_key:
                continue
            assert re.search(rf'"{spalte}"', quelle[block_start:block_start + 4000]), \
                f"{tabelle}.{spalte} fehlt in der Migration"


def test_testsuite_tabellen_fallen_im_upgrade():
    quelle = _quelle()
    # Die alten Tabellen werden GEDROPPT (nicht angelegt).
    assert 'for tabelle in ("ts_szenario", "ts_kommentar", "ts_ereignis", "ts_befund", "ts_sitzung"):' in quelle
