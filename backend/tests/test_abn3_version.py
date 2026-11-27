"""ABN-3 — Version: EINE Quelle, sichtbar in /healthz und im Boot-Objekt.

Was hier festgehalten wird (die Zusagen der Karte ABN-3):

1. **EINE Quelle.** Die Versionsnummer steht in der Paketdatei ``VERSION``;
   ``diakronos_app.__version__`` liest sie ein, statt sie abzutippen.
   ``backend/pyproject.toml`` fuehrt keine eigene Zahl mehr
   (``dynamic = ["version"]``) und zieht denselben Dateiinhalt.
2. **Sichtbar, wo der Betreiber nachsieht.** ``/healthz`` meldet ``version``
   und ``git``; das Boot-Objekt der SPA dieselben zwei Felder aus DERSELBEN
   Funktion. Die Oberflaeche (Fusszeile, "Einstellungen -> Ueber Diakronos")
   bekommt damit nie eine andere Nummer als der Zustandspruefer.
3. **Der Git-Hash wird nicht geraten.** Er kommt ausschliesslich aus der
   Build-Variable ``DIAKRONOS_GIT_COMMIT`` (Dockerfile-``ARG GIT_COMMIT``);
   ohne sie ist das Feld leer — nicht "unbekannt", nicht der Stand irgendeines
   Arbeitsbaums.

Der Wert wird NICHT fest auf "2.0.0" geprueft: die Karte verlangt SemVer mit
Startwert 2.0.0, aber ein spaeteres Update aendert genau diese Datei. Geprueft
wird die Form (SemVer) und die Gleichheit aller Ausgabewege.
"""

from __future__ import annotations

import re
from pathlib import Path

import diakronos_app
from diakronos_app import GIT_COMMIT_ENV, UNBEKANNTE_VERSION, git_kurz_hash, lade_version, version_auskunft

SEMVER = re.compile(r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")


def test_version_kommt_aus_der_datei():
    """``lade_version()`` liest die Paketdatei — keine zweite Zahl im Modul."""
    datei = Path(diakronos_app.__file__).with_name("VERSION")
    assert datei.is_file(), "backend/src/diakronos_app/VERSION fehlt (EINE Quelle)"
    assert lade_version() == datei.read_text(encoding="utf-8").strip()
    assert diakronos_app.__version__ == lade_version()


def test_version_ist_semver():
    assert SEMVER.match(diakronos_app.__version__), diakronos_app.__version__


def test_startwert_format_ist_gueltig():
    """Die Karte legt 2.0.0 als Startwert fest — geprueft wird die FORM, nicht die Zahl.

    ABN-3b: Ein Test auf ``== "2.0.0"`` bricht beim ersten geplanten Update
    (dann muss niemand einen Test „mitaendern", er darf einfach weiterlaufen).
    Festgehalten wird deshalb, was wirklich gelten muss: SemVer, gleiche
    Schreibweise in Datei, Modul, pyproject-Quelle und der Mindeststand, den
    die Endabnahme verlangt (>= 2.0.0 — eine Rueckwaertsbewegung waere ein
    Fehler, keine Absicht).
    """
    assert SEMVER.match(diakronos_app.__version__), diakronos_app.__version__
    teile = tuple(int(t) for t in diakronos_app.__version__.split(".")[:3])
    assert teile >= (2, 0, 0), f"Version {diakronos_app.__version__} liegt unter dem Abnahmestand 2.0.0"
    # Dieselbe Zeichenkette in allen Quellen — keine fuehrenden Nullen, kein Leerraum.
    datei = Path(diakronos_app.__file__).with_name("VERSION")
    assert datei.read_text(encoding="utf-8").strip() == diakronos_app.__version__


def test_pyproject_hat_keine_eigene_nummer(monkeypatch):
    """Kein zweiter Stand: ``version`` ist dynamisch, die Zahl steht nur in VERSION."""
    pyproject = Path(diakronos_app.__file__).parents[2] / "pyproject.toml"
    if not pyproject.is_file():  # pragma: no cover — Installation ohne Quelle
        return
    text = pyproject.read_text(encoding="utf-8")
    kopf = text.split("[project]", 1)[1].split("\n[", 1)[0]
    assert 'dynamic = ["version"]' in kopf
    assert not re.search(r"^version\s*=", kopf, re.M), "pyproject fuehrt wieder eine eigene Version"
    # und die dynamische Quelle zeigt auf die Paketdatei
    assert "src/diakronos_app/VERSION" in text


def test_git_hash_ohne_build_variable_leer(monkeypatch):
    monkeypatch.delenv(GIT_COMMIT_ENV, raising=False)
    assert git_kurz_hash() == ""
    assert version_auskunft() == {"version": diakronos_app.__version__, "git": ""}


def test_git_hash_aus_der_build_variable(monkeypatch):
    monkeypatch.setenv(GIT_COMMIT_ENV, "3900e4504ed1c34483c739517a959126b7ff2b6c")
    assert git_kurz_hash() == "3900e4504ed1"  # 12 Stellen, wie git rev-parse --short=12


def test_git_hash_leere_variable_bleibt_leer(monkeypatch):
    """``ARG GIT_COMMIT=""`` im Dockerfile: Feld leer, kein Platzhalter."""
    monkeypatch.setenv(GIT_COMMIT_ENV, "   ")
    assert git_kurz_hash() == ""


def test_healthz_meldet_version_ohne_git(monkeypatch):
    """Der Zustandspruefer nennt die Nummer — und NIE den Git-Hash (ABN-3b/N9).

    ``/healthz`` ist oeffentlich (Healthcheck, Betreiber-Skripte, jeder im
    Netz). Der Hash nennt den genauen Quellstand und gehoert nicht in eine
    offene Antwort; er steht nur im Boot-Objekt fuer Administratoren.
    """
    from fastapi.testclient import TestClient

    from diakronos_app.main import app

    monkeypatch.setenv(GIT_COMMIT_ENV, "abcdef0123456789")
    body = TestClient(app).get("/healthz").json()
    assert body["version"] == diakronos_app.__version__
    assert "git" not in body, "der Git-Hash darf nicht oeffentlich sein"


def test_boot_hash_nur_fuer_admins():
    """``version_auskunft_sichtbar`` reicht den Hash nur mit ``mit_hash=True``.

    Der Standard ist absichtlich OHNE Hash: ein vergessener Aufrufer liefert
    dann zu wenig (sichtbar im „Über Diakronos"), nicht zu viel (oeffentlich).
    """
    from diakronos_app import version_auskunft_sichtbar

    assert version_auskunft_sichtbar() == {"version": diakronos_app.__version__}
    mit = version_auskunft_sichtbar(mit_hash=True)
    assert set(mit) == {"version", "git"}
    assert mit["version"] == diakronos_app.__version__


def test_boot_objekt_meldet_dieselben_felder(monkeypatch):
    """Das Boot-Objekt der SPA liest DIESELBE Funktion (kein zweiter Stand)."""
    import inspect

    from diakronos_app import spa

    quelle = inspect.getsource(spa.boot_fuer_request)
    assert "version_auskunft_sichtbar(" in quelle, "Boot muss version_auskunft_sichtbar() einmischen"
    assert "version_auskunft()" not in quelle, "Boot darf den oeffentlichen Weg (mit Hash) nicht nehmen"
    # Dieselbe Nummer wie /healthz, aus derselben Funktion.
    monkeypatch.setenv(GIT_COMMIT_ENV, "1122334455667788")
    from diakronos_app import version_auskunft_sichtbar

    assert version_auskunft_sichtbar(mit_hash=True) == {
        "version": diakronos_app.__version__, "git": "112233445566"}


def test_boot_hash_nur_fuer_angemeldete_admins():
    """Die Rolle entscheidet, nicht der Endpunkt: Gast bekommt KEINEN Hash.

    Das Boot-Objekt geht bei jedem Seitenaufbau an jeden — auch an einen Gast.
    Ein Hash dort waere dieselbe oeffentliche Stand-Auskunft wie in /healthz.
    """
    import ast
    import inspect

    from diakronos_app import spa

    baum = ast.parse(inspect.getsource(spa.boot_fuer_request))
    # Der Schalter kommt aus der Rollenpruefung (ROOT_ROLLE/is_admin), nicht aus
    # einem festen `True`.
    quelle = inspect.getsource(spa.boot_fuer_request)
    assert "darf_hash_sehen" in quelle
    assert "ROOT_ROLLE in rollen" in quelle and "is_admin(user)" in quelle
    assert "user != GUEST" in quelle
    assert ast.parse(inspect.getsource(spa.boot_fuer_request)) is not None and baum is not None


def test_unbekannte_version_ist_kein_stiller_rueckfall():
    """Fehlt die Datei, steht ein sichtbarer Platzhalter — nicht "2.0.0"."""
    assert UNBEKANNTE_VERSION != "2.0.0"
    assert "unbekannt" in UNBEKANNTE_VERSION
