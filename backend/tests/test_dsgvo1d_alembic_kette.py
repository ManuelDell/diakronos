"""DSGVO-1d — genau EIN Alembic-Head, und die DSGVO-Migration haengt hinter Sicherung.

Der Betrieb startet mit ``alembic upgrade head`` (``docker-entrypoint.sh:65``).
Bei zwei Heads bricht dieser Aufruf ab und die App startet nicht. Das ist beim
Merge von DSGVO-1c gegen BACKUP-1 tatsaechlich passiert: ``bk1_sicherung`` und
``dsgvo1_loeschantrag_freigabe`` hingen beide an ``austritt_merkmale``.

Der Test ist absichtlich dumm gehalten (zwei Zusagen, keine Ableitung): er soll
auch beim naechsten Merge mit doppeltem Head anschlagen, ohne dass jemand die
Head-Namen nachtraegt.
"""

from __future__ import annotations

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

BACKEND = Path(__file__).resolve().parents[1]


def _skripte() -> ScriptDirectory:
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "alembic"))
    return ScriptDirectory.from_config(cfg)


def test_genau_ein_head():
    heads = _skripte().get_heads()
    assert len(heads) == 1, f"{len(heads)} Heads statt 1: {sorted(heads)}"


def test_dsgvo_migration_haengt_hinter_bk1_sicherung():
    revision = _skripte().get_revision("dsgvo1_loeschantrag_freigabe")
    assert revision is not None
    assert revision.down_revision == "bk1_sicherung", revision.down_revision
    quelle = Path(revision.path).read_text(encoding="utf-8")
    assert "Revises: bk1_sicherung" in quelle


def test_dsgvo2a_migration_haengt_hinter_ma1_smtp():
    """DSGVO-2a steht hinter MAIL-1 — und bleibt die einzige Spitze.

    Der Test haelt die Stelle fest, weil ein zweiter Head den Start bricht
    (``alembic upgrade head`` in ``docker-entrypoint.sh``).
    """
    revision = _skripte().get_revision("dsgvo2a_antrag_ablehnung")
    assert revision is not None
    assert revision.down_revision == "ma1_smtp", revision.down_revision
    quelle = Path(revision.path).read_text(encoding="utf-8")
    assert "Revises: ma1_smtp" in quelle
    assert "ck_loeschantrag_status" in quelle
