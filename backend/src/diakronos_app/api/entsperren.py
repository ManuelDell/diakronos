"""`/api/method/...entsperren` — gesperrte Konten manuell freigeben (A1c6).

DER WEG, DER ZUERST GEBRACHT WIRD, ist nicht dieser: der Notfallweg ist die
CLI im Container (`python -m diakronos_app.loginversuche --entsperren …`).
Siehe README. Wer den einzigen Administrator freigeben muss, hat keine
Sitzung — und ohne Sitzung kann dieser Endpunkt nichts.

WARUM DER WEB-WEG TROTZDEM DA IST
---------------------------------
Der Normalfall ist harmlos: ein Mitglied hat sich im Browser dreimal
vertippt, jemand hat den Rechner mitgenommen, und ein **anderer**
Administrator schaltet es frei. Das ist ein Verwaltungsakt, kein Notfall —
und dafuer ist eine Oberflaeche richtig.

DREI EIGENTUMLICHKEITEN, die diesen Endpunkt von einem normalen Admin-Button
unterscheiden:

1. **Keine IP.** Der Web-Weg loest ausschliesslich das genannte Konto. Die
   IP-Sperre gehoert dem Absender, nicht dem Konto: wer hier auf „Konto
   freigeben" klickt, will nicht ungefragt das halbe Buero ueber denselben
   Gemeindesanschluss mitsperren. Das ist die Entscheidung aus A1c2 und
   dieser Endpunkt darf sie nicht versehentlich aufweichen. Der Notfall,
   in dem die IP mitfreigegeben werden MUSS (der einzige Admin ist selbst
   gesperrt), laeuft deshalb ueber die CLI — dort ist es ein sichtbarer,
   bestaetigter zweiter Schritt.

2. **Die Antwortform gleich, egal ob es das Konto gibt.** Ein Admin darf
   hier Bestandswissen haben, aber das Werkzeug soll kein
   Benutzer-Enumerations-Werkzeug fuer den Fall sein, dass jemand
   Admin-Rechte hat, aber die Liste nicht kennt. Beide Faelle antworten
   gleich, es werden **keine** Zaehlerstaende, Sperrzeiten oder Trefferzahlen
   zurueckgegeben. Wer mehr wissen will, hat die CLI.

3. **Das Werkzeug ist selbst begrenzt.** `pruefe_werkzeugbudget()`
   zaehlt je Administrator-Konto; ein uebernommenes Admin-Konto darf nicht
   der Knopfdruck fuer die Wiederfreigabe sein.

FAIL CLOSED, wie ueberall: `allow_guest=False` (der Compat-Router lehnt
`Guest` mit 403 ab) **und** `permissions.require_admin()` (Guest und
Nicht-Admin werden mit 403 abgewiesen). Beides wird getestet — eine
Berechtigungspruefung, die nur eine der beiden Schichten kennt, waere eine,
die eine andereSchicht aufheben kann.

CSRF NICHT AUSGENOMMEN: der Aufruf schreibt, laeuft also durch die normale
`CsrfMiddleware`. `X-Frappe-CSRF-Token` ist Pflicht. Ein Eintrag in
`CSRF_EXEMPT_PATHS` waere hier genau die falsche Entscheidung: damit waere
eine fremde Seite in der Lage, einem eingeloggten Administrator fremde
Konten freizugeben.

AUDIT (wie A1c1, siehe `api/auth.py::_audit_gesperrt`): Pseudonyme statt
Klartext. Der **freigegebene Benutzer** und der **ausfuehrende Admin** stehen
pseudonymisiert im selben Eintrag, dazu welcher Bereich geraeumt wurde und ob
etwas zu tun war. Kein Passwort, kein Hash, kein `sid`, kein CSRF-Token.
"""

from __future__ import annotations

FRAPPE_MODULE = "diakronos.diakonos.api.entsperren"

import hashlib
import logging
from typing import Any

from diakronos_app.frappe_compat import loginversuche
from diakronos_app.frappe_compat.exceptions import PermissionError, ValidationError, throw
from diakronos_app.frappe_compat.permissions import require_admin
from diakronos_app.frappe_compat.registry import whitelist
from diakronos_app.frappe_compat.session import session
from diakronos_app.settings import settings

logger = logging.getLogger("diakronos_app.auth")

__all__ = ["FRAPPE_MODULE", "WORKZUG_ENTSPRERREN", "entsperren_konto"]

# Bezeichner fuer das Budget dieses Werkzeugs im Rate-Limit (Redis).
WORKZUG_ENTSPRERREN = "entsperren"

# Antwortform — **identisch in jedem Fall**: Konto existierte und war
# gesperrt, Konto existierte und war nie gesperrt, Konto existiert nicht.
#
# Es gab hier eine Fassung mit zwei Texten ("freigegeben" / "war nichts zu
# loesen"). Die ist falsch: sie beantwortet einem Administrator ohne
# Bestandswissen die Frage "ist dieses Konto gerade gesperrt?" — und genau das
# macht das Werkzeug zum Benutzer-Enumerations-Werkzeug fuer den Fall, dass
# jemand Admin-Rechte hat, aber die Liste nicht kennt. Der Weg, auf dem man
# "es war etwas zu tun" erfahren darf, ist die CLI (siehe dort: die Konsole
# steht dem Angreifer nicht zur Verfuegung).
_ANTWORT = "Konto freigegeben."


@whitelist(allow_guest=False)
def entsperren_konto(user: str | None = None, **kwargs: Any) -> str:
    """Gibt **ein** Konto in beiden Bereichen (Login, CalDAV) frei.

    `user` ist der Frappe-Benutzername, also die E-Mail-Adresse
    (`User.name`). Gross-/Kleinschreibung und Umraum sind egal — die
    Normalisierung ist dieselbe wie im Anmeldepfad, damit die Freigabe auch
    dann trifft, wenn die Anmeldung mit `Foo@Beispiel.Org` kam.

    Gibt **immer** dieselbe Antwort zurueck (siehe `_ANTWORT`) — egal ob es
    das Konto gibt, ob es gesperrt war und ob etwas geloescht wurde. Nur der
    **Audit-Log** unterscheidet die Faelle, und der traegt Pseudonyme statt
    Adressen.

    `ip` ist hier bewusst **kein** Parameter. Siehe Modulkopf, Punkt 1.
    """
    # Beide Berechtigungsschichten, in dieser Reihenfolge. `require_admin()`
    # wirft `PermissionError` (HTTP 403) fuer Gast und Nicht-Admin; der
    # `allow_guest=False` im Dekorator ist die Schicht darueber, die auch
    # dann greift, wenn jemand die Funktion einmal ohne den Aufruf von
    # `require_admin()` benutzt.
    require_admin()

    ziel = str(user or "").strip()
    if not ziel:
        throw("Bitte den Benutzernamen angeben.", ValidationError)

    _budget_pruefen()

    # `zuruecksetzen_alles` kennt die Bereichsliste selbst (`BEREICHE`) — eine
    # dritte Benutzeroberflaeche kann hier also nicht vergessen werden. Wir
    # brauchen nur den Bericht "ob es etwas zu tun war"; der kommt aus
    # `gib_bericht`, ebenfalls ueber `BEREICHE`.
    bericht = loginversuche.gib_bericht(ziel, None)
    loginversuche.zuruecksetzen_alles(ziel)

    _audit_entsperrt(ziel, bericht)

    # Ein reiner String als Rueckgabe: der Compat-Router verpackt ihn in den
    # Frappe-Envelope `{"message": …}`. Ein eigenes Feld (`"erfolg"`, `"u"`)
    # wuerde unterm Envelope verschwinden und die Antwort erhaelt eine
    # Moeglichkeit mehr, den Zustand zu verraten.
    return _ANTWORT


def _budget_pruefen() -> None:
    """Das Werkzeug gegen Dauerfeuer schuetzen.

    Wirft `PermissionError` (403), wenn das Budget des Administrators
    erschoepft ist. Der Aufrufer sieht damit dieselbe Form wie bei jedem
    anderen verbotenen Zugriff — keine neue Fehlerklasse, die nur hier
    auftaucht und einem Angreifer sagt, dass er richtig liegt.
    """
    erlaubt, _verbleibend = loginversuche.pruefe_werkzeugbudget(
        WORKZUG_ENTSPRERREN,
        session.user,
        settings.werkzeuglimit_entsperren,
        settings.werkzeuglimit_entsperren_fenster,
    )
    if not erlaubt:
        # NUR die Tatsache, kein Klartext: der Admin-Name steht nicht im Log.
        logger.warning("Werkzeugbudget erschoepft (Admin=Pseudonym %s).", _pseudo(session.user))
        throw("Zu viele Freigaben in kurzer Zeit. Bitte kurz warten.", PermissionError)


def _pseudo(roh: str) -> str:
    """Pseudonym eines Bezeichners fuer das Audit-Log — `sha256:<hex>`.

    Dieselbe Form wie `api/auth.py::_pseudo` und
    `api/audit_policy/anonymize.py::_hash_identifier`, damit ein Eintrag aus
    dem Login und einer aus dieser Freigabe nicht unterscheidbar sind. Gesalzen
    mit `secret_key`: wer das Audit-Log liest, kann die Liste der Benutzer
    nicht gegen eine E-Mail-Liste testen.
    """
    if not roh:
        return ""
    salz = str(getattr(settings, "secret_key", "") or "")
    return "sha256:" + hashlib.sha256(f"{salz}|{roh.strip().lower()}".encode()).hexdigest()


def _audit_entsperrt(ziel: str, bericht: dict[str, int]) -> None:
    """Audit-Eintrag ueber die Freigabe — Pseudonyme, keine Adressen.

    Steht drin:

      * **wer** freigegeben hat — der Administrator, pseudonymisiert,
      * **wen** — das Zielkonto, ebenfalls pseudonymisiert,
      * **welcher Bereich** — aus `loginversuche.BEREICHE`, damit aus dem
        Log hervorgeht, dass BEIDE Oberflaechen geraeumt wurden,
      * **ob** etwas zu tun war — `bericht["u"]` als Ja/Nein.

    Steht **nicht** drin: E-Mail-Klartext, Passwort, Hash, `sid`,
    CSRF-Token, Zaehlerstaende, Sperrzeiten.

    `actor` ist der ausfuehrende Administrator (Fremdschluessel auf
    `user.name`, wie in `api/auth.py` stehend `Guest`); pseudonymisiert steht
    er im Text. Der Grund dafuer: `actor` und `target_name` sind echte
    Fremdschluessel — ein Pseudonym in `actor` waere ein Verweis auf eine
    `user.name`, die es nicht gibt, und der Eintrag kaeme nicht mehr zustande.
    `target_name` ist frei und traegt das Pseudonym des Zielkontos.
    """
    try:
        from diakronos_app.frappe_compat.api_helpers import _create, _now

        bereiche = ", ".join(loginversuche.BEREICHE)
        getan = "ja" if bericht["u"] else "nein"
        _create(
            "Audit Log",
            {
                "zeitstempel": _now(),
                # "Sonstiges" ist der einzige zulaessige Typ fuer diesen Fall
                # (siehe `api/audit.py::VALID_ACTIONS`).
                "action_typ": "Sonstiges",
                "actor": session.user,
                "target_doctype": "User",
                "target_name": _pseudo(ziel) or "unbekannt",
                "begruendung": (
                    "Konto manuell freigegeben: Brute-Force-Sperre und "
                    f"Fehlversuchszaehler geloescht (Bereiche={bereiche}, "
                    f"hat_gesperrt_gehabt={getan}, "
                    f"freigegeben_von={_pseudo(session.user) or 'unbekannt'}, "
                    f"Ziel={_pseudo(ziel) or 'unbekannt'})"
                ),
                "ip_address": _pseudo(_client_ip()) or None,
                "notification_gesendet": 0,
            },
        )
    except Exception as exc:  # noqa: BLE001 — Freigabe darf nicht an der Logbuchhaltung haengen
        # Die Freigabe ist erfolgt und gilt. Ein fehlgeschlagener Eintrag ist
        # ein Beobachtungsfehler, kein Sperrvorfall — anders als bei der
        # Anmeldung, wo der Eintrag die Sperre dokumentiert.
        logger.warning("Audit-Eintrag fuer Kontofreigabe nicht moeglich: %s", exc.__class__.__name__)


def _client_ip() -> str:
    """Die IP des Administrators — nur pseudonymisiert im Log.

    Bewusst dieselbe Quelle wie im Anmeldepfad
    (`request_context.zaehler_client_ip()`), damit Admin und Angreifer in
    einem Log vergleichbar sind.
    """
    from diakronos_app import request_context

    return (request_context.zaehler_client_ip() or "").strip()
