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
"""

from __future__ import annotations

import logging

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

__all__ = ["bootstrap_erstinstallation", "ADMIN_ROLLEN"]


def _benutzer_vorhanden(sess) -> bool:
    """True, sobald IRGENDEIN Benutzer existiert (dann nie bootstrappen)."""
    from diakronos_app.models.core import User

    return sess.query(User).first() is not None


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


if __name__ == "__main__":
    # Aufruf im Container-Entrypoint: `python -m diakronos_app.erstinstallation`
    # NACH `alembic upgrade head`. Gibt einen Exitcode 0 zurueck, auch wenn
    # nichts zu tun war — der Start soll nie an der Erstinstallation scheitern.
    logging.basicConfig(level=settings.log_level.upper())
    ergebnis = bootstrap_erstinstallation()
    print(f"[erstinstallation] {'angelegt: ' + ergebnis if ergebnis else 'keine Aenderung'}")
