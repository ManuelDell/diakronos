"""Portierung von `diakonos/api/dsgvo_log.py` — der Einwilligungs-Log (P4n).

Quelle (READ-ONLY):
`referenz/diakronos-frappe/diakronos/diakonos/api/dsgvo_log.py`

WARUM EIGENES MODUL: `log_einwilligung` wird an FUENF Stellen gebraucht
(`api/profile.py` zweimal, `api/mitglieder.py` zweimal, `api/admin_hub.py`),
und die `referenz/.../AGENTS.md` — das TOM nach Art. 32 DSGVO — verlangt fuer
jede Aenderung an einem der sechs Einwilligungsfelder EINEN Log-Eintrag.
Eine zweite Fassung waere die gefaehrlichste Variante: `api/mitglieder.py`
hatte bereits eine private Kopie, die an `frappe.local.request` las — ein
Namespace, den es im Standalone-Backend nicht gibt. Der Eintrag bekam deshalb
immer eine LEERE IP und einen leeren User-Agent. Das war kein Fehler, den
man bemerkt: das Feld ist nullable und niemand schaut hin. Jetzt steht hier
die EINE Fassung, die den echten Request-Kontext liest.

Frappe-Aufruf -> Compat-Schicht:

    frappe.local.request.environ["REMOTE_ADDR"]
        -> request_context.get_client_ip()      (Middleware, s. request_context.py)
    frappe.local.request.headers["User-Agent"]
        -> request_context.get_user_agent()     (gekuerzt auf 200, wie im Original)
    frappe.get_doc({...}).insert(ignore_permissions=True)
        -> _create("DSGVO Einwilligung", {...})
    frappe.log_error(...) -> log_error(...) (stderr)

Unveraendert uebernommen: der Aufrufer liest NIE direkt in die
Einwilligungsfelder des `Mitglied` (das Original macht das ueber
`frappe.db.set_value` mit anschliessendem Log — genau das ist der Weg, den
`api/profile.py` hier geht). Und: **Exceptions werden geschluckt.** Ein
Log-Fehler darf den primaeren Save nie blockieren, sonst koennte ein
Datenbank-Problem am Log dazu fuehren, dass ein Benutzer seine Einwilligung
nicht mehr setzen kann — das waere die umgekehrte Datenschutzwirkung.
"""

from __future__ import annotations

from diakronos_app.frappe_compat.api_helpers import _create, _now, log_error

__all__ = ["log_einwilligung"]


def log_einwilligung(mitglied, typ, aktion, quelle="selfservice") -> None:
    """Erzeugt einen unveraenderlichen DSGVO-Einwilligung-Log-Eintrag.

    1:1 nach `dsgvo_log.py:4-36`. Der Eintrag referenziert nur
    `mitglied.name` (die technische ID) und keine personenbezogenen Daten —
    genau das ist der Grund, warum er eine Datenloeschung ueberlebt
    (Art. 17 Abs. 3 lit. b DSGVO, AGENTS.md Abschnitt 3).

    Args:
        mitglied: `Mitglied`-Name (technische ID, kein Name der Person).
        typ:       "datenschutz" | "foto" | "werbung".
        aktion:    "erteilt" | "widerrufen".
        quelle:    "selfservice" (Standard) | "admin" | "import" | "api".

    Schluckt absichtlich alle Exceptions — s. Modul-Docstring.
    """
    try:
        from diakronos_app.request_context import get_client_ip, get_user_agent

        # Letztes Oktett anonymisieren (IPv4) — 1:1 wie im Original.
        # Eine IP im Einwilligungs-Log ist Nachweis (Art. 7 Abs. 1), keine
        # Personenakte: das letzte Oktett zu kuerzen erhaelt den Nachweis
        # und nimmt die Zuordnung zu einem Geraet.
        ip = _anonymisieren(get_client_ip())
        ua = get_user_agent(200)

        _create(
            "DSGVO Einwilligung",
            {
                "mitglied": mitglied,
                "typ": typ,
                "aktion": aktion,
                "zeitstempel": _now(),
                "ip_adresse": ip,
                "user_agent": ua,
                "quelle": quelle,
            },
        )
    except Exception:  # noqa: BLE001 — 1:1 das Original
        log_error("Einwilligung Log Fehler", "Einwilligung Log Fehler")


def _anonymisieren(ip: str) -> str:
    """Letztes IPv4-Oktett durch "0" ersetzen. Keine IP -> unveraendert leer.

    1:1 nach `dsgvo_log.py:16-21`. IPv6 wird NICHT angefasst: das Original
    fasst es auch nicht an, und eine "falsch anonymisierte" IPv6 (etwa
    `::1`) waere schlimmer als eine unveraenderte — die Regel lautet hier
    "Oktett 4 auf 0, sonst nichts", nicht "IPv6 erkennen".
    """
    if not ip:
        return ""
    parts = ip.split(".")
    if len(parts) == 4:
        parts[3] = "0"
        return ".".join(parts)
    return ip
