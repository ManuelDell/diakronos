"""Erstinstallation — legt den ersten Administrator an (Karte A1b3).

Problem: Eine frische Installation hat eine leere `user`-Tabelle. Ohne Login
gibt es niemanden, der sich anmelden kann — die SPA bleibt beim
`Administrator`-Platzhalter stehen und zeigt keine echten Inhalte.

Loesung: Beim Start liest die App `ADMIN_EMAIL` und `ADMIN_PASSWORD`
(`settings.admin_email` / `settings.admin_password`) und legt daraus den ersten
Benutzer an — MIT einer echten Passwortpruefung (Argon2-Hash ueber
`frappe_compat.passwoerter.neuer_hash`) und der Rolle `System Manager`, damit
`is_admin` in `session.get_current_user_context` greift.

Regeln (fail safe, aus der Karte):

  * **Nur bei leerer Tabelle.** Existiert bereits irgendein Benutzer, passiert
    NICHTS. Ein versehentlich gesetzter `ADMIN_PASSWORD` kann so nie ein
    bestehendes Konto ueberschreiben oder ein zweites anlegen.
  * **Beide Werte noetig.** Fehlt `ADMIN_EMAIL` ODER `ADMIN_PASSWORD`, wird
    kein Benutzer angelegt (nur eine Warnung). Ein halb gesetzter Wert ist
    gefaehrlicher als keiner.
  * **Idempotent.** Mehrfacher Start (app/worker/scheduler parallel) fuehrt
    hoechstens einmal zum Anlegen; ein zweiter Lauf sieht die gefuellte
    Tabelle und tut nichts.
  * **Kein Klartext in Logs.** Es wird nur die E-Mail genannt, nie das
    Passwort und nie ein Hash.

Der Aufruf gehoert NACH `alembic upgrade head` (sonst fehlt die Tabelle) und
ist deshalb ueber `bootstrap_erstinstallation()` an einer Stelle gebuendelt,
die `main.py` beim Import aufruft.

ON-1 — ZWEITER WEG: DER EINRICHTUNGSLINK
----------------------------------------
Sind BEIDE Werte leer, gibt es also keine Kopflinie-Installation, wird KEIN
Benutzer angelegt, sondern ein Einrichtungs-Token erzeugt und als Kasten auf
stdout ausgegeben (``einrichtung.py``; nur der SHA-256-Hash landet in der DB).
Wer den Link oeffnet, legt den Administrator selbst an — das Passwort kennt
dann niemand ausser ihm. Der Weg ueber ``ADMIN_EMAIL``/``ADMIN_PASSWORD``
bleibt UNVERAENDERT (kopflose Installation); dann gibt es keinen Link.
"""

from __future__ import annotations

import logging
import textwrap

from diakronos_app import einrichtung
from diakronos_app.settings import settings

logger = logging.getLogger("diakronos_app.erstinstallation")

# Genau die Rollen, die `permissions.ADMIN_ROLES` als Admin zaehlt — als
# Re-Export, nicht als eigene Liste (A1c3). Bis dahin stand hier eine dritte
# Kopie derselben Wahrheit. Das war riskanter als die Kopie in `spa.py`: sie
# VERGIBT die Rollen, also konnte ein frisch installiertes Konto eine Rolle
# bekommen, die die Kompat-Schicht nicht als Admin kennt — niemand haette
# etwas gemerkt, bis das Menue leer blieb.
#
# `System Manager` reicht; `Mitgliederadministrator` ist die fachliche Rolle
# fuer die Mitgliederverwaltung und wird daher mitvergeben.
from diakronos_app.frappe_compat.permissions import ADMIN_ROLES as ADMIN_ROLLEN

__all__ = [
    "bootstrap_erstinstallation",
    "ADMIN_ROLLEN",
    "neuer_einrichtungslink",
    "startkasten",
    "einrichtungslink_befehl",
]


def _benutzer_vorhanden(sess) -> bool:
    """True, sobald IRGENDEIN Benutzer existiert (dann nie bootstrappen)."""
    from diakronos_app.models.core import User

    return sess.query(User).first() is not None


#: Fehlendes ``APP_BASE_URL``: der Link ist dann nur relativ. Ein relativer
#: Link in einem Terminal ist fuer einen Menschen wertlos, wenn er auf einem
#: anderen Rechner sitzt — deshalb steht der Hinweis direkt daneben.
HINWEIS_OHNE_BASIS = (
    "Hinweis: APP_BASE_URL ist nicht gesetzt. Der Link ist deshalb nur ein "
    "Pfad. Bitte APP_BASE_URL in der .env setzen (z. B. "
    "https://gemeinde.example.org) und den Stack neu starten — oder den Pfad "
    "an die Adresse Ihres Servers anhaengen."
)

#: Abschlusszeile des Kastens (Entwurf, Frame 01).
HINWEIS_JEDER_START = (
    "Hinweis: Diese Ausgabe erscheint bei jedem Start, bis ein "
    "Systemadministrator angelegt ist."
)

#: Warnzeile ueber dem Kasten (Entwurf, Frame 01: „WARN Kein
#: Systemadministrator vorhanden"). Dieselbe Form, die auch der Betrieb im
#: Container-Log zeigt (Zeitstempel, Level, Meldung).
LOGFORMAT_WARN = "{zeit}  WARN  {meldung}"


def _warnzeile(meldung: str) -> str:
    """Warnzeile mit Zeitstempel der Gemeinde (Ortszeit, nicht UTC)."""
    from zoneinfo import ZoneInfo

    from diakronos_app.anmeldung.registrierungslink import jetzt_gemeinde

    return LOGFORMAT_WARN.format(
        zeit=jetzt_gemeinde().astimezone(ZoneInfo("localtime")).strftime("%H:%M:%S"),
        meldung=meldung,
    )


def einrichtungslink_befehl() -> str:
    """Der Befehl, der einen neuen Link erzeugt (Text aus dem Entwurf).

    Kompakter Container-Einstiegspunkt ``diakronos einrichtungslink`` (siehe
    ``backend/bin/diakronos``). Der laengere Weg
    (``python -m diakronos_app.einrichtung link``) steht in der
    Betriebsanleitung.
    """
    return "docker compose exec app diakronos einrichtungslink"


def startkasten(token: str) -> str:
    """Der Einrichtungs-Kasten fuer stdout — Wortlaut aus dem Entwurf (Frame 01).

    Zeigt den Link, den Befehl zum Neuerzeugen und die beiden Hinweise. Der
    Kasten ist die EINZIGE Stelle, an der der Klartext-Token ausgegeben wird.
    """
    link = einrichtung.link_anzeige(token)
    basis = str(getattr(settings, "app_base_url", "") or "").strip()
    zeilen = [
        "",
        "  ┌─ ERSTEINRICHTUNG " + "─" * 60,
        "  │",
        "  │  Es gibt noch keinen Systemadministrator.",
        "  │",
        "  │  Öffnen Sie diesen Link, um ihn anzulegen",
        f"  │  (einmalig gültig, {einrichtung.GUELTIG_TAGE} Tage):",
        "  │",
        f"  │  {link}",
        "  │",
    ]
    if not basis:
        zeilen += textwrap.wrap(
            f"  │  {HINWEIS_OHNE_BASIS}",
            width=120,
            subsequent_indent="  │  ",
        )
        zeilen.append("  │")
    zeilen += [
        "  │  " + "─" * 66,
        "  │",
        "  │  Neuen Link erzeugen:",
        f"  │    {einrichtungslink_befehl()}",
        "  │",
    ]
    zeilen += textwrap.wrap(
        "  │  Der Link erscheint nur, solange kein Systemadministrator besteht. "
        "Ein neuer Link macht den alten ungültig.",
        width=120,
        subsequent_indent="  │  ",
    )
    zeilen += [
        "  │",
        "  └" + "─" * 78,
        "",
        HINWEIS_JEDER_START,
        "",
    ]
    return "\n".join(zeilen)


def neuer_einrichtungslink(*, ausgeben: bool = True) -> str | None:
    """Erzeugt einen neuen Einrichtungs-Token — nur solange es keinen Benutzer gibt.

    Rueckgabe: der Klartext-Token oder ``None``, wenn die Einrichtung
    abgeschlossen ist (Meldung „Einrichtung bereits abgeschlossen.“). Der alte
    Token wird dabei ungueltig (Single-Zeile, ``einrichtung.erzeuge_token``).
    """
    from diakronos_app.db import SessionLocal

    with SessionLocal() as sess:
        if _benutzer_vorhanden(sess):
            if ausgeben:
                print(
                    "[einrichtung] Einrichtung bereits abgeschlossen. "
                    "Ein neuer Link wird nicht erzeugt."
                )
            return None

    token, _bis = einrichtung.erzeuge_token()
    if ausgeben:
        print(startkasten(token))
    return token


def _startlink_ausgeben() -> str | None:
    """ON-1 (E1): erzeugt den Einrichtungs-Link, falls noch niemand existiert.

    Laeuft beim Start NACH den Migrationen. Existiert schon ein Benutzer, ist
    die Ersteinrichtung abgeschlossen — dann passiert NICHTS (kein Link, keine
    Zeile). Ein vorhandener, noch gueltiger Token wird NICHT ersetzt: sonst
    wuerde jeder Neustart (app, worker, scheduler) den Link ungueltig machen,
    den der Betreiber gerade kopiert hat. Genau deshalb wird hier nur erzeugt,
    wenn es noch keinen gueltigen gibt — das Neuerzeugen von Hand
    (``neuer_einrichtungslink``) ersetzt ihn bewusst.

    Fehler werden geschluckt (wie der ganze Bootstrap): ein Start darf nicht
    an der Ausgabe eines Links scheitern.
    """
    try:
        from diakronos_app.db import SessionLocal

        with SessionLocal() as sess:
            if _benutzer_vorhanden(sess):
                logger.info("Einrichtung abgeschlossen — kein Einrichtungs-Link.")
                return None
        if not einrichtung.gueltiger_token_vorhanden():
            token, _bis = einrichtung.erzeuge_token()
        else:
            token = None
        print(_warnzeile("Kein Systemadministrator vorhanden"))
        if token:
            print(startkasten(token))
        else:
            print(
                "Es gibt bereits einen Einrichtungs-Link. Er bleibt gueltig, bis er "
                "verbraucht ist oder ersetzt wird.\n"
                "Neuen Link erzeugen:\n  " + einrichtungslink_befehl()
            )
        return token
    except Exception as exc:  # noqa: BLE001 — Start nie durch den Link kippen
        logger.warning("Einrichtungs-Link nicht erzeugt: %s", exc.__class__.__name__)
        return None


def bootstrap_erstinstallation() -> str | None:
    """Legt den Erst-Administrator an, falls noetig.

    Rueckgabe: die E-Mail des angelegten Benutzers oder `None`, wenn nichts zu
    tun war (Tabelle nicht leer, Werte fehlen). Wirft nie — ein Fehler beim
    Bootstrap darf den Start nicht verhindern.
    """
    email = (settings.admin_email or "").strip()
    passwort = settings.admin_password or ""

    if not email or not passwort:
        # Bewusst leise: der Normalfall einer bestehenden Installation ist
        # genau das (beide Werte leer). Nur wenn EINES gesetzt ist, wird es
        # interessant -> Warnung.
        if email or passwort:
            logger.warning(
                "Erstinstallation uebersprungen: ADMIN_EMAIL und ADMIN_PASSWORD "
                "muessen BEIDE gesetzt sein (nur %s gesetzt).",
                "ADMIN_EMAIL" if email else "ADMIN_PASSWORD",
            )
            # Ein halb gesetzter Wert ist gefaehrlicher als keiner: der
            # Betreiber glaubt, es sei eingerichtet. Der Einrichtungs-Link
            # wird dann NICHT erzeugt — die Warnung ist die Meldung.
            return None
        # ON-1 (E1): keine Kopflinie-Installation -> Einrichtungs-Link.
        _startlink_ausgeben()
        return None

    from diakronos_app.db import SessionLocal
    from diakronos_app.frappe_compat.passwoerter import neuer_hash
    from diakronos_app.models.core import HasRole, User

    sess = SessionLocal()
    try:
        if _benutzer_vorhanden(sess):
            logger.info("Erstinstallation: Benutzer vorhanden — kein Bootstrap.")
            return None

        sess.add(User(
            name=email,
            email=email,
            full_name=email,
            enabled=True,
            # Argon2: der Erst-Admin hat kein importiertes Frappe-Passwort.
            password_hash=neuer_hash(passwort),
        ))
        for idx, rolle in enumerate(ADMIN_ROLLEN, start=1):
            sess.add(HasRole(
                name=f"{email}-{rolle}",
                parent=email,
                parenttype="User",
                parentfield="roles",
                role=rolle,
                docstatus=0,
                idx=idx,
            ))
        sess.commit()
        logger.info("Erstinstallation: Administrator %s angelegt.", email)
        return email
    except Exception as exc:  # noqa: BLE001 — Start nie durch Bootstrap kippen
        sess.rollback()
        logger.exception("Erstinstallation fehlgeschlagen: %s", exc)
        return None
    finally:
        sess.close()


def _praefix_setzen() -> str:
    """Setzt den Prozess-Praefix, bevor eine Adresse gebaut wird.

    ON-1b: Dieses Modul laeuft im Container-Entrypoint als EIGENER Prozess
    (`python -m diakronos_app.erstinstallation`) — also VOR und unabhaengig
    von `main.create_app()`, wo `base_path.setze_praefix` sonst gesetzt wird.
    Ohne diesen Aufruf baute `einrichtung.link_anzeige()` den Link OHNE
    `DIAKRONOS_BASE_PATH`: der Kasten zeigte `/einrichtung/<token>`, und
    genau diese Adresse antwortet im Betrieb mit 404 (im Wegwerf-Stack mit
    `/diakronos` gemessen). Der Praefix aus den Einstellungen ist hier die
    einzige Wahrheit — dieselbe Quelle wie in `main`.
    """
    from diakronos_app import base_path
    from diakronos_app.settings import settings

    return base_path.setze_praefix(getattr(settings, "diakronos_base_path", ""))


if __name__ == "__main__":
    # Aufruf im Container-Entrypoint: `python -m diakronos_app.erstinstallation`
    # NACH `alembic upgrade head`. Gibt einen Exitcode 0 zurueck, auch wenn
    # nichts zu tun war — der Start soll nie an der Erstinstallation scheitern.
    #
    # ON-1: Ohne ADMIN_EMAIL/ADMIN_PASSWORD wird hier der Einrichtungs-Link
    # erzeugt und als Kasten ausgegeben (siehe `_startlink_ausgeben`). Der
    # Klartext-Token steht NUR in dieser Ausgabe — nicht im Log, nicht in der DB.
    logging.disable(logging.CRITICAL)  # nur der Kasten, kein doppeltes Log
    _praefix_setzen()
    ergebnis = bootstrap_erstinstallation()
    if ergebnis:
        print(f"[erstinstallation] angelegt: {ergebnis}")
