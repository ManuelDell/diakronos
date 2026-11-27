"""Diakronos — FastAPI-Backend.

ABN-3: **EINE** Quelle der Versionsnummer ist die Datei ``VERSION`` in diesem
Paket (Inhalt ``2.0.0``). Sie wird hier eingelesen — nicht abgetippt.
``backend/pyproject.toml`` liest dieselbe Datei ueber ``dynamic = ["version"]``;
Oberflaeche und ``/healthz`` bekommen den Wert aus diesem Modul. Damit gibt es
keinen zweiten Stand, der auseinanderlaufen kann.

Der Git-Kurz-Hash kommt aus dem Build (``ARG GIT_COMMIT`` in
``backend/Dockerfile``, zur Laufzeit ``DIAKRONOS_GIT_COMMIT``); ausserhalb
eines Images bleibt er leer — dann steht ``"git": ""`` statt eines geratenen
Werts.
"""

from __future__ import annotations

import os
from importlib.resources import files as _resources_files

#: Platzhalter, wenn die Versionsdatei fehlt oder leer ist. Bewusst sichtbar
#: und NICHT ``2.0.0``: ein stiller Rueckfall auf eine plausible Nummer waere
#: eine zweite Wahrheit — und im Betrieb nicht als Fehler erkennbar.
UNBEKANNTE_VERSION = "0.0.0-unbekannt"

#: Umgebungsvariable des Builds (siehe ``backend/Dockerfile``, ``ARG GIT_COMMIT``).
GIT_COMMIT_ENV = "DIAKRONOS_GIT_COMMIT"

#: Laenge des Kurz-Hashs (wie ``git rev-parse --short`` mit 12 Stellen).
KURZ_HASH_ZEICHEN = 12


def lade_version() -> str:
    """Die Version aus der Paketdatei ``VERSION`` (ohne Zeilenumbruch)."""
    try:
        roh = _resources_files(__name__).joinpath("VERSION").read_text(encoding="utf-8")
    except (FileNotFoundError, ModuleNotFoundError, OSError):  # pragma: no cover — Paket ohne Datei
        return UNBEKANNTE_VERSION
    wert = roh.strip()
    return wert or UNBEKANNTE_VERSION


def git_kurz_hash() -> str:
    """Build-Kennung des Images — ``""``, wenn sie beim Bauen nicht gesetzt war.

    Nur der Build setzt sie. Zur Laufzeit wird nichts ermittelt und nichts aus
    ``.git`` gelesen: das Image hat keines, und ein gefundener Arbeitsbaum
    waere der Stand des Hosts, nicht der des laufenden Containers.
    """
    return os.environ.get(GIT_COMMIT_ENV, "").strip()[:KURZ_HASH_ZEICHEN]


def version_auskunft_sichtbar(*, mit_hash: bool = False) -> dict[str, str]:
    """Das Boot-Objekt der SPA: Version immer, Hash nur fuer angemeldete Admins.

    ABN-3b/N9: ``/healthz`` ist OEFFENTLICH — der Git-Hash gehoert nicht
    dorthin. Er nennt den genauen Quellstand und damit angreifbare Stellen.
    Die Version darf bleiben (sie beantwortet „laeuft der neue Stand?").

    Das Boot-Objekt wird bei JEDEM Seitenaufbau ausgeliefert, auch an Gaeste.
    Deshalb entscheidet hier die Rolle, nicht der Endpunkt:
    ``mit_hash=True`` nur fuer ``is_admin``/``root`` (Aufrufer:
    ``spa.boot_fuer_request``). Fuer alle anderen bleibt der Schluessel ganz
    weg — nicht leer, denn ein leeres Feld saehe nach einem Build ohne
    Kennung aus.
    """
    auskunft: dict[str, str] = {"version": __version__}
    if mit_hash:
        auskunft["git"] = git_kurz_hash()
    return auskunft


def version_auskunft() -> dict[str, str]:
    """Version UND Build-Kennung — nur fuer ``/healthz`` intern/Diagnose-Tools.

    Der Oeffentlichkeit wird das NICHT gezeigt (siehe
    :func:`version_auskunft_sichtbar`).
    """
    return {"version": __version__, "git": git_kurz_hash()}


__version__ = lade_version()
