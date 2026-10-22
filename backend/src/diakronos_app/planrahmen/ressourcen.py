"""Zugriff auf die mitgelieferten Dateien des Plan-Rahmens (Schema, Doku, Kochbuch).

Alle Dateien, die zur Laufzeit oder in Tests gebraucht werden, liegen IM
Python-Paket und werden ueber :mod:`importlib.resources` gelesen — nie ueber
Pfade relativ zum Repo und nie ueber absolute Host-Pfade (NACHTRAG DOCKER).
Damit funktionieren Schema, Pruefung und Dokumentation sowohl bei der
Editable-Install im Image als auch bei einer Nicht-Editable-Install
(``[tool.setuptools.package-data]`` in ``pyproject.toml``).

:func:`importlib.resources.files` ist ab Python 3.9 verfuegbar; die Fallbacks
sind hier bewusst nicht noetig, weil das Projekt ``requires-python >= 3.12``
vorgibt.
"""

from __future__ import annotations

import json
from importlib import resources
from typing import Any


def _paket() -> Any:
    """Das Anker-Paket fuer die Ressourcenpfade (``diakronos_app.planrahmen``)."""
    import diakronos_app.planrahmen

    return diakronos_app.planrahmen


def schema_text() -> str:
    """Liest das Plantyp-Schema ``schema/plantyp-1.json`` als Text."""
    return (resources.files(_paket()) / "schema" / "plantyp-1.json").read_text(encoding="utf-8")


def schema_daten() -> dict[str, Any]:
    """Liest das Plantyp-Schema als Python-Objekt (JSON)."""
    return json.loads(schema_text())


def doku_text(name: str) -> str:
    """Liest ein Dokument aus ``planrahmen/doku/`` (z. B. ``REFERENZ.md``).

    ``name`` ist der Dateiname ohne Verzeichnis, z. B. ``"REFERENZ.md"``.
    """
    return (resources.files(_paket()) / "doku" / name).read_text(encoding="utf-8")


def regel_bausteine() -> dict[str, Any]:
    """Registry der Regel-Bausteine als ``{name: {beschreibung, parameter_schema}}``.

    Die UI (Schema-Editor) baut daraus Auswahl und Parameterformulare. Die
    Registry wird ausschliesslich als Antwort mitgeliefert (x-Erweiterung von
    ``schema_holen``) — das Hauptschema ``schema/plantyp-1.json`` bleibt
    unveraendert, die Pruefung daraus laeuft unbeeinflusst weiter.
    """
    from .regeln.registry import REGEL_BAUSTEINE

    return {b.schluessel: {"beschreibung": b.kurz, "parameter_schema": b.parameter_schema}
            for b in REGEL_BAUSTEINE}


def kochbuch_dateinamen() -> list[str]:
    """Kennungen (Dateinamen) aller Kochbuch-Beispiele, sortiert ohne Endung.

    Liefert z. B. ``["chorplan", "freizeit", ...]`` — die Datei liegt dann unter
    ``kochbuch/<name>.json``.
    """
    verzeichnis = resources.files(_paket()) / "doku" / "kochbuch"
    namen = [e.name for e in verzeichnis.iterdir() if e.name.endswith(".json")]
    return sorted(n[:-5] for n in namen)


def kochbuch_laden(name: str) -> dict[str, Any]:
    """Liest ein Kochbuch-Beispiel ``kochbuch/<name>.json`` als Objekt."""
    pfad = resources.files(_paket()) / "doku" / "kochbuch" / f"{name}.json"
    return json.loads(pfad.read_text(encoding="utf-8"))


def instanz_dateinamen() -> list[str]:
    """Kennungen aller Instanz-Beispiele (``instanzen/<name>.json``), sortiert.

    Instanz-Beispiele sind konkrete Eintraege eines Plans (z. B. der konkrete
    Programmablauf des Adventssingens), KEINE Plantyp-Dateien. Sie liegen unter
    ``doku/instanzen/`` und werden von ``eintraege.py`` strukturell gegen ihren
    Plantyp geprueft.
    """
    verzeichnis = resources.files(_paket()) / "doku" / "instanzen"
    namen = [e.name for e in verzeichnis.iterdir() if e.name.endswith(".json")]
    return sorted(n[:-5] for n in namen)


def instanz_laden(name: str) -> dict[str, Any]:
    """Liest ein Instanz-Beispiel ``instanzen/<name>.json`` als Objekt."""
    pfad = resources.files(_paket()) / "doku" / "instanzen" / f"{name}.json"
    return json.loads(pfad.read_text(encoding="utf-8"))
