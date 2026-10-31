"""Inventar der whitelist-Endpunkte (SEC-11/C2) — maschinenlesbar.

`inventar/whitelist.json` und `whitelist.md` werden von
`tools/whitelist_inventar.py` aus dem lebenden Register erzeugt. Sie liegen IM
PYTHON-PAKET (nicht unter `docs/`), weil `docs/` in `.dockerignore` steht und
die Waechter der SPA (Frontend-Node-Test `tests/sec11-get-schreibend.test.mjs`)
die Datei im Image lesen muessen.

Zugriff ausschliesslich ueber `importlib.resources` — keine Pfade relativ zum
Repo, keine absoluten Host-Pfade (Karten-Nachtrag 1).
"""

from __future__ import annotations

import json
from importlib import resources
from typing import Any

__all__ = ["lade_inventar", "text"]


def text() -> str:
	"""Inhalt der Lesefassung (`whitelist.md`)."""
	return resources.files(__name__).joinpath("whitelist.md").read_text(encoding="utf-8")


def lade_inventar() -> dict[str, Any]:
	"""Das Inventar als Dictionary (Zahlen, Eintraege, Widersprueche)."""
	roh = resources.files(__name__).joinpath("whitelist.json").read_text(encoding="utf-8")
	return json.loads(roh)
