"""Paket der Psalmos-API-Ports (P4i).

Die Fachmodule liegen unter `diakronos_app.api.psalmos.*`; die ORIGINAL-Pfade
der SPA (`diakronos.psalmos.api.<modul>.<fn>`) entstehen ueber die Konstante
`FRAPPE_MODULE` je Modul, die der Compat-Registry auswertet (registry.py).

Der Verzeichnisname ist bewusst `psalmos` (nicht `psalmos`/`diakonos`):
die SPA ruft `diakronos.psalmos.api.musik.get_lieder` auf
(Aufrufliste des Frappe-Frontends). Ein einziger fehlender Buchstabe im
Originalpfad macht JEDEN Endpunkt fuer die SPA unerreichbar, ohne dass eine
Testsuite das merkt — deshalb steht `FRAPPE_MODULE` in jedem Modul.
"""

from __future__ import annotations

from diakronos_app.api.psalmos import musik  # noqa: F401 — P4i: Liedgut (8 Pfade)
