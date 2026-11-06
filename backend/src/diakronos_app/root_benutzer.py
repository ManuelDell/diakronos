"""ON-6 — der ERSTE Administrator ist ``root`` fuer Diakronos.

FACHENTSCHEIDUNG (Manuel, 2026-11-05)
-------------------------------------
    „Der erste Admin soll alle Rechte haben, er ist root/sudo fuer Diakronos.“

DER BEFUND, DER DIESE KARTE AUSGELOEST HAT
------------------------------------------
Wer sich ueber den Ersteinrichtungs-Link (ON-0/ON-1) anlegt, bekommt genau
``permissions.ADMIN_ROLES`` — also ``System Manager`` und
``Mitgliederadministrator``. Damit ist er Admin der Mitgliederverwaltung, aber
NICHT ``Kalenderadministrator``: Onboarding-Schritt 5 („Kalender anlegen“)
scheiterte deshalb bei JEDER Neuinstallation mit „Nur
Kalenderadministratoren duerfen Kalender verwalten.“ Dieselbe Luecke traf
jede weitere Rolle, die eine Karte spaeter hinzufuegt.

DIE ANTWORT: EINE ROOT-KENNZEICHNUNG, EIN PRUEFPUNKT
----------------------------------------------------
Root ist kein neuer Rollenname in der ``Has Role``-Tabelle, sondern eine
Tatsache am KONTO: der Name steht in der Single-Zeile ``gemeinde_einstellungen``
(``root_benutzer``), und die einzige Kennzeichnung ist die semantisch
eindeutige Rolle ``root`` — gefuehrt in ``frappe_compat.gruppen.RootUser``
(Tabelle ``gruppen_root_user``, Migration ``on6_root_benutzer``). Die Rolle
``root`` steht AUSSCHLIESSLICH dann dort, wenn das Konto auch eingetragen ist;
beides wird in derselben Transaktion geschrieben (``markiere`` /
``entferne``), damit es nie zwei Wahrheiten gibt.

Geprueft wird an EINER Stelle: :func:`frappe_compat.permissions.ist_root`.
``get_roles()`` liefert Root ALLE Rollen (:data:`ALLE_ROLLEN`) — damit bestehen
root und jede kuenftige Rolle in jeder vorhandenen Rollenpruefung, ohne dass
eine Karte die 128 Aufrufstellen anfassen muss. ``session.get_current_user_context``
liefert Overlay-Rollen und ``is_root`` fuer die Oberflaeche mit.

WARUM NICHT ``Administrator``
-----------------------------
Der Frappe-Superuser ``Administrator`` ist in mehreren Pfaden gesperrt
(CalDAV: ``caldav.auth._BLOCKED_USERS``) und in ``benutzer_status`` ein
Sonderfall. Root ist ein NORMALES Konto mit Passwort, Sitzung und Rollen — es
hat nur keine Grenze.

SCHUTZ (Karte Punkt 3)
----------------------
* Root kann von NIEMANDEM herabgestuft, gesperrt oder geloescht werden
  (``api/zugang.py``, ``api/datenschutz.py``).
* Die Uebertragung von root laeuft ausschliesslich ueber den eigenen Endpunkt
  ``api/root.root_uebertragen`` — POST, nur root selbst, mit Bestaetigung und
  dem Passwort von Root.

WO DIE ROOT-KENNUNG STEHT
-------------------------
``gemeinde_einstellungen.root_benutzer`` (eine Zeile, ``name`` =
``GEMEINDE_EINSTELLUNGEN_NAME``). Dieselbe Tabelle traegt schon die
Gemeinde-Angaben; eine eigene Single-Zeile fuer EIN Feld waere eine zweite
Stelle fuer dieselbe Frage. Fehlt die Zeile oder ist das Feld leer, gibt es
keinen root — fail closed, wie jede andere Rechtepruefung dieses Projekts.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("diakronos_app.root_benutzer")

__all__ = [
    "ROOT_ROLLE",
    "ALLE_ROLLEN",
    "ist_root",
    "ist_root_in",
    "root_name",
    "markiere",
    "entferne",
    "roote_namen",
]


#: Der EINE Rollenname der Kennzeichnung. Bewusst klein geschrieben und nicht
#: in ``Has Role`` gesucht, sondern ueber ``gruppen.RootUser`` gefuehrt — der
#: Name erscheint in Rollenlisten der Oberflaeche, damit ein root sichtbar ist.
ROOT_ROLLE = "root"

#: Rollen, die ``get_roles`` fuer Root zusaetzlich liefert. Wird aus den
#: vorhandenen Quellen abgeleitet (Admin-Rollen, Zugangs-Rollen, Kalender- und
#: Moderationsrollen) — und um die eine Kennung ``root`` ergaenzt. Neue Rollen
#: gelten fuer root automatisch, weil :func:`ist_root` als Kurzschluss in
#: ``get_roles`` sitzt und dort die ROLLE selbst prueft (nicht diese Liste):
#: ``has_role("Irgendwas")`` ist fuer root immer wahr.
ALLE_ROLLEN: tuple[str, ...] = ()


def _alle_rollen() -> tuple[str, ...]:
    """Alle bekannten Rollen + ``root`` (einmal berechnet, dann konstant).

    Quellen sind die vorhandenen Rollenlisten des Projekts — keine erfundene
    eigene Aufzaehlung. Die Liste dient NUR der Anzeige (Oberflaeche zeigt
    „alle Rechte“); die Rechtepruefung selbst ist der Kurzschluss in
    ``permissions.get_roles``.
    """
    global ALLE_ROLLEN
    if ALLE_ROLLEN:
        return ALLE_ROLLEN
    rollen: set[str] = {ROOT_ROLLE}
    try:
        from diakronos_app.frappe_compat.permissions import ADMIN_ROLES

        rollen.update(ADMIN_ROLES)
    except Exception:  # noqa: BLE001 — Anzeigeliste, nie eine Rechtequelle
        pass
    try:
        from diakronos_app.api.verantwortliche import ZUGANGS_ROLLEN

        rollen.update(ZUGANGS_ROLLEN)
    except Exception:  # noqa: BLE001
        pass
    rollen.update({
        "Kalenderadministrator",
        "Ressourcenmoderator",
        "Website-Moderator",
        "Mitglied",
    })
    ALLE_ROLLEN = tuple(sorted(r for r in rollen if r))
    return ALLE_ROLLEN


def root_name() -> str | None:
    """Der eingetragene root-Benutzer oder ``None``.

    Liest die Single-Zeile ``gemeinde_einstellungen``; fehlt sie (frische DB
    vor der Migration, Test-DB ohne Seed), gibt es keinen root. Der Import von
    ``SessionLocal`` steht im Rumpf, damit die Test-Fixture ``patched_db``
    greift (dieselbe Regel wie in ``benutzer_status._aus_db``).

    ON-6c — Sitzung des Aufrufers statt eigener Sitzung
    --------------------------------------------------
    Frueher oeffnete diese Funktion IMMER eine eigene ``SessionLocal()`` und
    schloss sie wieder. Auf einer Datenbank mit EINER Verbindung je Engine
    (SQLite-``StaticPool`` im Test, aber auch ein Pool von genau einer
    Verbindung) reisst das ``close()`` die offene Transaktion des Aufrufers
    mit: die App sah den gerade geflushten Plan nicht mehr und committete
    nichts (Regression aus ON-6: ``plan_anlegen`` antwortete 200, der Plan war
    weg — 6 Fehler in ``test_plan_w1_warnungen_nur_planer.py``, auf main gruen).

    Deshalb dieselbe Regel wie in ``benutzer_status._kontozustand``: liegt eine
    Aufruf-Sitzung an (``db.aktuelle_sitzung``, gesetzt im Request-Rahmen von
    ``_endpunkt``), wird DIESE gelesen und NICHT geschlossen. Ausserhalb eines
    Request-Rahmens bleibt es bei einer eigenen, die geschlossen wird.
    """
    try:
        from diakronos_app.db import SessionLocal, aktuelle_sitzung
        from diakronos_app.models.gemeinde import (
            GEMEINDE_EINSTELLUNGEN_NAME,
            GemeindeEinstellungen,
        )

        eigene = aktuelle_sitzung.get()
        if eigene is not None:
            zeile = eigene.get(GemeindeEinstellungen, GEMEINDE_EINSTELLUNGEN_NAME)
            wert = str(getattr(zeile, "root_benutzer", None) or "").strip()
            return wert or None
        with SessionLocal() as sess:
            zeile = sess.get(GemeindeEinstellungen, GEMEINDE_EINSTELLUNGEN_NAME)
            if zeile is None:
                return None
            wert = str(zeile.root_benutzer or "").strip()
            return wert or None
    except Exception:  # noqa: BLE001 — fail closed: kein root bei Lesefehler
        logger.warning("root-Benutzer nicht lesbar — es gilt kein root.", exc_info=True)
        return None


def ist_root(user: str | None) -> bool:
    """True, wenn dieses Konto der eingetragene root ist. Fail closed."""
    name = str(user or "").strip()
    if not name or name.lower() == "guest":
        return False
    eingetragen = root_name()
    if not eingetragen:
        return False
    return name == eingetragen


def ist_root_in(sess: Any, user: str | None) -> bool:
    """Wie :func:`ist_root`, aber in der SESSION des Aufrufers (ON-6b).

    Fuer Pruefungen, die in derselben Transaktion entscheiden und schreiben
    muessen (``api/root.root_uebertragen``): :func:`root_name` oeffnet eine
    EIGENE Sitzung und saehe eine gerade committete Aenderung erst nach dem
    Ende der umgebenden Transaktion — die Pruefung waere dann alt.

    Die Sperre selbst setzt der Aufrufer (``with_for_update`` auf der
    Gemeinde-Zeile); hier wird nur GELESEN. Eine fehlende Zeile heisst wie
    ueberall: kein root (fail closed).
    """
    from diakronos_app.models.gemeinde import (
        GEMEINDE_EINSTELLUNGEN_NAME,
        GemeindeEinstellungen,
    )

    name = str(user or "").strip()
    if not name or name.lower() == "guest":
        return False
    zeile = sess.get(GemeindeEinstellungen, GEMEINDE_EINSTELLUNGEN_NAME)
    if zeile is None:
        return False
    eingetragen = str(zeile.root_benutzer or "").strip()
    return bool(eingetragen) and name == eingetragen


def markiere(sess: Any, user: str) -> None:
    """Setzt ``user`` als root — Eintrag UND Kennrolle in EINER Transaktion.

    Der Aufrufer committet. Wird beim Anlegen des ersten Administrators
    (``erstinstallation`` / ``einrichtung_routen``) und bei der Uebertragung
    (``api/root.root_uebertragen``) benutzt. Ein vorhandener root wird dabei
    NICHT stillschweigend ersetzt: die Uebertragung entfernt ihn vorher
    ausdruecklich (:func:`entferne`).
    """
    from diakronos_app.models.gemeinde import (
        GEMEINDE_EINSTELLUNGEN_NAME,
        GemeindeEinstellungen,
    )
    from diakronos_app.models.root_benutzer import RootUser

    name = str(user or "").strip()
    if not name:
        raise ValueError("root ohne Kontonamen geht nicht.")

    zeile = sess.get(GemeindeEinstellungen, GEMEINDE_EINSTELLUNGEN_NAME)
    if zeile is None:
        zeile = GemeindeEinstellungen(name=GEMEINDE_EINSTELLUNGEN_NAME)
        sess.add(zeile)
        sess.flush()
    zeile.root_benutzer = name

    if sess.get(RootUser, name) is None:
        sess.add(RootUser(konto=name))
        sess.flush()
    _rolle_setzen(sess, name, True)


def entferne(sess: Any, user: str) -> None:
    """Nimmt ``user`` die root-Kennzeichnung (Eintrag UND Kennrolle)."""
    from diakronos_app.models.gemeinde import (
        GEMEINDE_EINSTELLUNGEN_NAME,
        GemeindeEinstellungen,
    )
    from diakronos_app.models.root_benutzer import RootUser

    name = str(user or "").strip()
    zeile = sess.get(GemeindeEinstellungen, GEMEINDE_EINSTELLUNGEN_NAME)
    if zeile is not None and str(zeile.root_benutzer or "").strip() == name:
        zeile.root_benutzer = None
    vorhanden = sess.get(RootUser, name)
    if vorhanden is not None:
        sess.delete(vorhanden)
        sess.flush()
    _rolle_setzen(sess, name, False)


def roote_namen(sess: Any) -> set[str]:
    """Alle Konten mit der Kennrolle ``root`` (fuer Inventar und Aufraeumen)."""
    from diakronos_app.models.root_benutzer import RootUser

    return {str(k) for (k,) in sess.query(RootUser.konto)}


def _rolle_setzen(sess: Any, name: str, an: bool) -> None:
    """Zeile ``root`` in ``has_role`` setzen bzw. entfernen (idempotent)."""
    from diakronos_app.models.core import HasRole

    zeilen = [
        z for z in sess.query(HasRole).filter(HasRole.parent == name).all()
        if str(z.role or "") == ROOT_ROLLE
    ]
    if an:
        if not zeilen:
            sess.add(HasRole(
                name=f"{name}-{ROOT_ROLLE}",
                parent=name,
                parenttype="User",
                parentfield="roles",
                role=ROOT_ROLLE,
                docstatus=0,
                idx=0,
            ))
            sess.flush()
    else:
        for z in zeilen:
            sess.delete(z)
        if zeilen:
            sess.flush()
