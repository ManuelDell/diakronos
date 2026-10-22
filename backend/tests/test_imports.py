"""Stellt sicher, dass alle Kernabhaengigkeiten importierbar sind.

Schlaegt fehl, wenn eine der Bibliotheken nicht installiert wurde — genau der
Fehler, den ein unvollstaendiger pip-install sonst erst zur Laufzeit zeigt.
"""

import importlib
import importlib.metadata as md
import pathlib
import tomllib

import pytest

REQUIRED_MODULES = [
    "sqladmin",
    "sqlalchemy_continuum",
    # A1a: `argon2-cffi` macht die NEUEN Passwort-Hashes (Modulname `argon2`).
    # `fastapi-users` wurde entfernt (Routen/Hash-Backend passten nicht zur
    # SPA; pbkdf2 kann es ohnehin nicht). `pwdlib` war entgegen der
    # Kartenannahme NIE im Image.
    "argon2",
]


@pytest.mark.parametrize("module_name", REQUIRED_MODULES)
def test_required_module_imports(module_name):
    module = importlib.import_module(module_name)
    assert module is not None, f"{module_name} liess sich importieren, ist aber None"


def test_core_modules_import():
    for module_name in ("fastapi", "sqlalchemy", "redis", "rq", "apscheduler", "alembic"):
        importlib.import_module(module_name)


# ── Packaging-Vertrag ─────────────────────────────────────────────────────
# `test_required_module_imports[sqladmin]` oben faellt zwar, sagt aber nicht
# WARUM. Diese Tests benennen die Ursache, damit der Fehler nicht durch eine
# Aenderung an irgendeiner anderen Stelle zurueckkommt.


def _pyproject() -> dict:
    # Im Image liegt pyproject.toml unter /app, im Repo unter backend/.
    kandidaten = [pathlib.Path("/app/pyproject.toml"), pathlib.Path(__file__).resolve().parents[1] / "pyproject.toml"]
    vorhanden = [k for k in kandidaten if k.is_file()]
    if not vorhanden:
        pytest.skip("pyproject.toml weder unter /app noch neben tests/ gefunden")
    return tomllib.loads(vorhanden[0].read_text(encoding="utf-8"))


def _deps() -> list[str]:
    return _pyproject()["project"]["dependencies"]


def _name(req: str) -> str:
    """Paketname aus einer Anforderung, ohne Extras/Versionen/Marker.

    Handgeschrieben statt `packaging.requirements`: das waere eine zusaetzliche
    Testabhaengigkeit nur fuer einen Namensvergleich.
    """
    for trenner in (";", ",", "[", ">", "=", "<", " "):
        req = req.split(trenner, 1)[0]
    return req.strip().lower()


def test_sqlalchemy_asyncio_extra_ist_deklariert():
    """sqladmin zieht sqlalchemy.ext.asyncio unbedingt; das Extra ist Pflicht.

    Ohne `[asyncio]` fehlt greenlet und der sqladmin-Import bricht beim Laden
    ab — im Image und in jeder frischen Installation.
    """
    sqlalchemy_zeilen = [d for d in _deps() if _name(d) == "sqlalchemy"]
    assert sqlalchemy_zeilen, "sqlalchemy fehlt in den dependencies"
    assert any("[asyncio]" in d for d in sqlalchemy_zeilen), (
        f"sqlalchemy muss mit [asyncio] deklariert sein, gefunden: {sqlalchemy_zeilen}"
    )


def test_greenlet_hat_cp312_faehige_untergrenze():
    """greenlet <3.0 liefert fuer cp312 kein manylinux-Rad, nur sdist.

    Das Image baut auf python:3.12-slim; ein Resolver-Pfad ohne diese Untergrenze
    muesste dort aus Quelltext kompilieren. Geprueft wird die DEKLARIERTE Unter-
    grenze, nicht die installierte Version — das ist der Vertrag, den die
    Kartenabnahme sichern soll.
    """
    zeile = next((d for d in _deps() if _name(d) == "greenlet"), None)
    assert zeile is not None, "greenlet fehlt in den dependencies"
    # ">=" bzw. "==" aus der Anforderung herausziehen.
    operator = next((z for z in (">=", "==", "~=") if z in zeile), None)
    assert operator, f"greenlet ohne Untergrenze deklariert: {zeile}"
    untergrenze = zeile.split(operator, 1)[1].split(",", 1)[0].split(";", 1)[0].strip()
    assert untergrenze, f"greenlet-Untergrenze nicht lesbar: {zeile}"
    assert tuple(int(t) for t in untergrenze.split(".")[:2]) >= (3, 0), (
        f"greenlet-Untergrenze {untergrenze} hat kein cp312-manylinux-Rad; ab 3.0.0 gibt es eins"
    )


def test_installiertes_greenlet_erfuellt_die_untergrenze():
    """Gegenprobe: das, was im Image wirklich installiert ist."""
    installiert = md.version("greenlet")
    assert tuple(int(t) for t in installiert.split(".")[:2]) >= (3, 0), (
        f"installiertes greenlet {installiert} ist aelter als die Untergrenze 3.0"
    )
