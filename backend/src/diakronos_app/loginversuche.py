"""Einstieg fuer `python -m diakronos_app.loginversuche` — der Notweg (A1c6).

    docker compose exec app python -m diakronos_app.loginversuche --entsperren <user>

WARUM DIESE DATEI UND NICHT `frappe_compat.loginversuche.py` direkt
-------------------------------------------------------------------
Der Store liegt in `diakronos_app/frappe_compat/loginversuche.py` — dort gehoert
die Logik hin, denn die Laufzeit (`pruefe_und_merke`) hat dort zu stehen. Als
**Modul aufrufbar** ist aber genau der Pfad, den ein Mensch im Notfall
abtippt, und der ist in der Karte festgeschrieben:

    python -m diakronos_app.loginversuche --entsperren <user>

Diese eine Datei macht daraus den Aufruf, ohne dem Store irgendeine
Eigenstaendigkeit zu geben: kein `argparse` im Store, kein weiterer
`__main__`-Block, der beim Import von `frappe_compat.loginversuche` durch
irgendeinen anderen Weg mitlaeuft. Sie ist ein reiner Verweis.

`python -m diakronos_app.frappe_compat.loginversuche` funktioniert
deshalb **nicht** — absichtlich. Zwei Wege fuer denselben Notfall waeren zwei
Dinge, die auseinanderlaufen koennen; wovor man in einer Fuelle steht, ist der
kuerzere Pfad, und der ist der dokumentierte.

Die Logik steht in `cli_entsperren.py` (dort auch die ausfuehrliche
Begruendung der einzelnen Schalter).
"""

from __future__ import annotations

import sys

from diakronos_app.cli_entsperren import main

__all__ = ["main"]

if __name__ == "__main__":  # pragma: no cover — Container-Einstieg
    sys.exit(main())
