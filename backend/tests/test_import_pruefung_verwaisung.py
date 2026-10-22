"""A1c3, Punkt 4: Der Verwaisungs-Test darf die Collection NICHT abbrechen.

Problem (Karte A1c3): `tools/import_pruefung.py` ist ein **Werkzeug** und
liegt im Repo, aber NICHT im Image (der `Dockerfile` kopiert nur `backend/`,
und `tools/` ist auch nicht im `.dockerignore` ausgenommen — es wird schlicht
nicht kopiert). `import_pruefung` und `import_aus_frappe` fehlen im Container
deshalb komplett.

Folge: `import import_pruefung` am Modul-Anfang dieser Datei wirft
`ModuleNotFoundError` — und weil das ein **Collection-Fehler** ist, bricht
`python -m pytest` im Image mit `Interrupted: 1 error during collection` ab.
Seit P7 wird der Test deshalb per `--ignore` umgangen, d.h. im Container laeuft
er seit Wochen gar nicht, ohne dass es auffaellt.

Diese Datei loest das so, dass `python -m pytest` **im Container ohne
Zusatzargument** durchlaeuft:
  * im Repo (mit `tools/`) laufen die Tests — der Import passiert unten
    bedingt, nicht global;
  * im Image (ohne `tools/`) wird die ganze Datei uebersprungen, mit einem
    benannten Grund (`A1C3_TOOLS_FEHLT`), nicht still.

Der Skip darf NICHT ueberall greifen: `test_diese_datei_ist_kein_stiller_skip`
stellt das sicher und schlaegt um, sobald jemand den Import wieder
unbedingt macht.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[2] / "tools"
IN_REPO = TOOLS.is_dir()

# `import_pruefung` ist nur importierbar, wenn `tools/` im Suchpfad liegt. Das
# ist im Repo der Fall (sys.path-Eintrag unten), im Image nicht (`/app/tools`
# existiert nicht).
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

_MODUL = "import_pruefung"

_WARUM = (
    "A1C3_TOOLS_FEHLT: tools/import_pruefung.py liegt im Repo, ist aber nicht "
    "im Image (der Dockerfile kopiert nur backend/). Die Verwaisungs-Pruefung "
    "ist ein Import-Werkzeug und laeuft im Repo-/CI-Kontext, nicht im "
    "Container. Der Test wird hier nur uebersprungen, damit `python -m "
    "pytest` im Image durchlaeuft — das ist ein SKIP, kein bestandener Test."
)

# `pytest.skip` kennt kein `mark=`-Argument (das hat nur `skipif`). Der Grund
# steht deshalb im Klartext im Skip-Text und wird mit `-rs` sichtbar.
if not IN_REPO or importlib.util.find_spec(_MODUL) is None:
    pytest.skip(_WARUM, allow_module_level=True)

# Ab hier: der Import ist bedingt und laeuft nur, wenn das Modul wirklich da
# ist. Im Repo fuehrt der Pfad darueber, im Image greift der Skip.
import import_pruefung as ip  # noqa: E402
from import_aus_frappe import Column, DocTypeTarget, TableData  # noqa: E402


class _EmptyResult:
    def scalars(self):
        return self

    def all(self):
        return []

    def fetchall(self):
        return []


class _FakeConn:
    """Minimal-Conn: tut so, als haette jede Tabelle null Zeilen."""

    def execute(self, *_a, **_k):
        return _EmptyResult()


def _target(doctype: str, table: str, cols: list[str]) -> DocTypeTarget:
    return DocTypeTarget(
        doctype=doctype,
        table=table,
        istable=False,
        issingle=False,
        columns=[Column(c, "text") for c in cols],
    )


def _audit_log_rows() -> TableData:
    return TableData(columns=["name", "actor"], rows=[["AUDIT-1", "Administrator"]])


TARGETS = [_target("Audit Log", "audit_log", ["name", "actor"])]
CORE_USER = _target("User", "user", ["name"])


@pytest.fixture(autouse=True)
def _only_audit_log_link_field(monkeypatch):
    """Nur das eine Link-Feld pruefen, um den Test isoliert zu halten."""
    monkeypatch.setattr(ip, "load_link_fields", lambda: [("Audit Log", "actor", "User")])


def test_quelle_nicht_geladen_ist_unpruefbar_und_faellt_durch():
    """Fehlt die User-Quelltabelle, darf das NICHT stillschweigend gruen sein."""
    res = ip.check_links({"tabAudit Log": _audit_log_rows()}, TARGETS, _FakeConn(), core=[])

    assert res.numbers["unpruefbar"] == 1
    assert res.numbers["quelle_verwaist"] == 0
    assert res.passed is False
    # Das Pruefloch muss im Klartext benannt sein, nicht nur als Zaehler.
    assert any("unpruefbar" in d or "Audit Log" in d for d in res.details)


def test_quelle_geladen_aber_leer_ist_nachgewiesen_verwaist():
    """Eine geladene, leere Quelltabelle ist ein echter, belegbarer Befund."""
    res = ip.check_links(
        {"tabAudit Log": _audit_log_rows(), "tabUser": TableData(columns=["name"], rows=[])},
        TARGETS,
        _FakeConn(),
        core=[CORE_USER],
    )

    assert res.numbers["quelle_verwaist"] == 1
    assert res.numbers["unpruefbar"] == 0
    assert res.passed is True


def test_diese_datei_ist_kein_stiller_skip():
    """Gegenprobe: Diese Datei prueft sich selbst.

    Sie laeuft nur in einer Umgebung MIT dem Modul (alles davor waere sonst
    ein Modul-Skip). Der Test schlaegt um, wenn jemand den bedingten Import
    wieder unbedingt macht — dann waere die Collection wieder kaputt, nur eben
    hinter einem `ImportError`, den man beim gruenen Lauf nicht sieht.
    """
    assert ip is not None
    assert callable(ip.check_links)
    # Der bedingte Import muss wirklich ausgefuehrt worden sein.
    assert _MODUL in sys.modules, (
        "import_pruefung wurde nicht importiert — der Import ist nicht mehr bedingt"
    )
