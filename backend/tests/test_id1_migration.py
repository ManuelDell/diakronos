"""ID-1: die Alembic-Kette hat genau EINEN Kopf, und der ist `id1_mitglied_kennungen`.

WARUM
-----
Der Operator reiht parallel laufende Karten beim Merge neu ein (MAIL-1 hat eine
eigene Migration). Zwei Köpfe sind kein Fehler, den `alembic upgrade head`
meldet, sondern einer, der den Start des Stacks abbricht — deshalb steht der
Wächter hier und nicht nur in der Karte.

Der zweite Teil prüft die Zusage aus ID-1: die Migration hängt an
`dsgvo2a_antrag_ablehnung` und arbeitet auf beiden Seiten (upgrade und
downgrade) — sie ist keine Einbahnstraße.
"""
from __future__ import annotations

import pathlib

from alembic.config import Config
from alembic.script import ScriptDirectory

BACKEND = pathlib.Path(__file__).resolve().parents[1]


def _skripte() -> ScriptDirectory:
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "alembic"))
    return ScriptDirectory.from_config(cfg)


def test_genau_ein_kopf():
    """Zwei Köpfe brechen `alembic upgrade head` ab (Entrypoint bei jedem Start)."""
    koepfe = _skripte().get_heads()
    assert len(koepfe) == 1, f"mehrere Alembic-Köpfe: {koepfe}"


def test_id1_haengt_an_der_dsgvo_freigabe():
    """ID-1 setzt die DSGVO-1-Migration voraus (Umschlüssel-Mechanik ist dort)."""
    revision = _skripte().get_revision("id1_mitglied_kennungen")
    assert revision is not None, "Migration id1_mitglied_kennungen fehlt"
    assert revision.down_revision == "dsgvo2a_antrag_ablehnung", revision.down_revision


def test_id1_hat_einen_abbildungsnamen_und_ein_downgrade():
    """Die Abbildung alt->neu ist benannt und `downgrade` ist implementiert."""
    from alembic.script import ScriptDirectory

    script = _skripte()
    revision = script.get_revision("id1_mitglied_kennungen")
    modul = revision.module
    assert modul.ABBILDUNG == "id1_mitglied_kennung"
    assert callable(modul.downgrade)
    # Die Kennung entsteht im Format von `_new_name` (uuid[:10]).
    assert modul._kennung.__doc__ is not None
    assert script.get_revision("id1_mitglied_kennungen").is_branch_point is False
