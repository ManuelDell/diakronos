"""Paket der Audit-Policy-Jobs (P6a).

Entspricht dem Originalpaket `diakonos/api/audit_policy/`. Im Altcode enthaelt es
`anonymize.py` (taeglicher DSGVO-Job) und `decorator.py` (Policy-Hook). Portiert
ist bisher nur `anonymize.py` — der Policy-Decorator haengt an der
Audit-Policy-Auswertung, die im Standalone-Backend nicht existiert
(s. `api/audit.py`, Helfer `_policy_geloggt`).
"""

from __future__ import annotations

__all__: list[str] = []
