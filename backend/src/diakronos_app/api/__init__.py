"""Paket der portierten API-Module.

`diakronos_app.api.<modul>.<funktion>` wird ueber
`/api/method/<modul>.<funktion>` erreichbar.

Die portierten Endpunkte liegen in eigenen Modulen, damit die dotted paths
denen des Originals entsprechen:

  api/mitglieder.py  -> mitglieder.get_mitglieder_liste, .get_mitglied_detail
  api/admin_hub.py   -> admin_hub.get_statistik

Die Importe hier sind noetig, damit der Router die Funktionen registriert.
`ping`/`fail_validation` bleiben als Envelope-Testbieger (P2a).
Der frueher hier liegende P2a-Platzhalter `get_mitglieder_liste` wurde in P1d
entfernt — die echte Portierung liegt in `api/mitglieder.py`.
"""

from __future__ import annotations

from diakronos_app.frappe_compat import whitelist
from diakronos_app.frappe_compat.exceptions import ValidationError

# Portierte Endpunkte der echten App. Import hier, damit `mount()` und der
# Modul-Import-Fallback im Router sie registrieren.
from diakronos_app.anmeldung import einstellungen_api  # noqa: F401 — SEC1: Anmeldeeinstellungen
from diakronos_app.api import admin_hub  # noqa: F401
from diakronos_app.api import austritt  # noqa: F401 — AUSTRITT: Austritt/Reaktivieren (2 Pfade)
from diakronos_app.api import audit  # noqa: F401 — P4g: Audit/Notifications (4 Pfade)
from diakronos_app.api import auth  # noqa: F401 — A1b1: login/logout
from diakronos_app.api import auswahl  # noqa: F401 — P4g: Suchdropdowns (4 Pfade)
from diakronos_app.api import beitraege  # noqa: F401 — P4f: Beitraege (6 Pfade)
from diakronos_app.api import bugreport  # noqa: F401 — P4j: Dev-Bugmelder (4 Pfade)
from diakronos_app.api import dashboard  # noqa: F401 — P4h: Dashboard (11 Pfade)
from diakronos_app.api import datenschutz  # noqa: F401 — N6: Auskunft/Anträge/Anonymisierung
from diakronos_app.api import dienstplan  # noqa: F401 — P4h: Dienstplan-Sicht (3 Pfade)
from diakronos_app.api import entsperren  # noqa: F401 — A1c6: Konto freigeben (Admin)
from diakronos_app.api import frappe_core  # noqa: F401 — P2c: Frappe-Core-Methoden
from diakronos_app.api import gruppen  # noqa: F401 — P4a: Gruppen (19 Pfade)
from diakronos_app.api import gemeinde  # noqa: F401 — N9: Gemeinde/Datenschutz-Texte
from diakronos_app.api import sicherung  # noqa: F401 — BACKUP-1: Datensicherung (System Manager)
from diakronos_app.api import mailversand  # noqa: F401 — MAIL-1: SMTP-Einstellungen (System Manager)
from diakronos_app.api import kronos  # noqa: F401 — P4b: Kronos-Kern (13 Pfade)
from diakronos_app.api import mitglieder  # noqa: F401
from diakronos_app.api import orgchart_api  # noqa: F401 — P4a: Organigramm
from diakronos_app.api import planung  # noqa: F401 — P4d1: Dienstplanung (17 Pfade)
from diakronos_app.api import planrahmen  # noqa: F401 — generischer Plan-Rahmen
from diakronos_app.api import profile  # noqa: F401 — P4n: Profilseite (6 Pfade)
from diakronos_app.api import psalmos  # noqa: F401 — P4i: Psalmos/Musik (8 Pfade)
from diakronos_app.api import registrierung  # noqa: F401 — P4e: Registrierung (allow_guest!)
from diakronos_app.api import registrierungslink_api  # noqa: F401 — P4e: Link-Verwaltung (Admin)
from diakronos_app.api import veranstaltungsanmeldung  # noqa: F401 — P4e: Veranstaltungs-Anmeldung
from diakronos_app.api import verantwortliche  # noqa: F401 — P1-8: Verantwortliche/Rollen pflegbar
from diakronos_app.api import zugang  # noqa: F401 — P1-8: Zugang (Konto/Rollen/Sperren)
from diakronos_app.api import ressourcen  # noqa: F401 — P4c2: Ressourcen-Buchung (9 Pfade)
from diakronos_app.api import session  # noqa: F401 — P4g: User-Context (3 Pfade)
from diakronos_app.api import wiki  # noqa: F401 — P4f: Wiki-Artikel (7 Pfade)


@whitelist()
def ping() -> str:
	"""Trivialer Endpunkt fuer den Envelope-Test."""
	return "pong"


@whitelist()
def fail_validation(msg: str = "kaputt") -> None:
	"""Endpunkt, der einen fachlichen Fehler wirft (417)."""
	raise ValidationError(msg)


# Nachregistrierung: traegt fuer alle bereits bekannten Funktionen den
# Original-Frappe-Pfad (`diakronos.diakonos.api.<modul>.<funktion>`) nach.
# Noetig, weil ein frueherer Import eines Untermoduls (z. B. aus `main.py`)
# das Paket halb geladen lassen kann — dann fehlt der Original-Pfad und die
# SPA erhaelt 404, obwohl die Kurzform aufloest. Idempotent.
from diakronos_app.frappe_compat.registry import nachregistrieren as _nachregistrieren

_nachregistrieren()
