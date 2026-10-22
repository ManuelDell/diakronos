"""Wurzel-Conftest des Backends.

Der Test fuer die Demo-Daten (PUB-2) importiert ``musterhausen`` aus
``tools/demo/``. Das Verzeichnis ist ein Werkzeug und KEIN Teil des
App-Pakets — deshalb wird der Pfad hier einmal bekannt gemacht, statt das
Backend-Paket mit Demo-Code zu fuellen.

Zwei Lagen, ein Pfad:

* im Image liegt das Backend unter ``/app`` und die Werkzeuge unter
  ``/app/tools/demo`` (siehe ``backend/Dockerfile``) — dort ist der Testlauf
  laut Makefile zu Hause;
* im Repo ist dieser Conftest in ``backend/`` verankert, die Werkzeuge liegen
  eine Ebene hoeher unter ``tools/demo``.
"""
from __future__ import annotations

import sys
from pathlib import Path

_HIER = Path(__file__).resolve().parent
for _TOOLS in (_HIER / "tools" / "demo", _HIER.parent / "tools" / "demo"):
    if _TOOLS.is_dir() and str(_TOOLS) not in sys.path:
        sys.path.insert(0, str(_TOOLS))
