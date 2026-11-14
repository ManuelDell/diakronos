"""R-2: HTTP-Endpunkte des EINEN Rechtesystems (Rollen, Module).

Dünne Schicht: jede Funktion reicht an ``diakronos_app.rechte.verwaltung``
weiter, die ueber den Rechte-Kern entscheidet. Alle schreibenden Endpunkte
sind ``POST`` (CSRF wie ueberall), Lesen ist ``GET``/``POST``.

Pfade: ``/api/method/diakronos_app.api.rechte.<funktion>``.
"""

from __future__ import annotations

from typing import Any

from diakronos_app.frappe_compat import whitelist
from diakronos_app.frappe_compat.session import session
from diakronos_app.rechte import kern, verwaltung


def _wahr(wert: Any) -> bool:
    """Formular-/JSON-Wahrheitswert (``true``, ``1``, ``"true"``)."""
    if isinstance(wert, bool):
        return wert
    return str(wert or "").strip().lower() in ("1", "true", "ja", "yes", "on")


@whitelist(allow_guest=False)
def get_gruppenrollen(gruppe: str) -> dict:
    """HV, MV, GL einer Gruppe + was der Aufrufer davon aendern darf."""
    return verwaltung.rollen_der_gruppe(session.user, str(gruppe or ""))


@whitelist(allow_guest=False)
def get_meine_rechte(typ: str, objekt: str | None = None, gruppe: str | None = None,
                     untergruppe: str | None = None) -> dict:
    """Welche Aktionen der Aufrufer an einem Objekt hat (fuer die Oberflaeche).

    Die Oberflaeche blendet damit Knoepfe aus; durchgesetzt wird serverseitig
    in jedem Endpunkt ueber den Kern.
    """
    kw = {"gruppe": gruppe or None, "untergruppe": untergruppe or None}
    return {
        aktion: bool(kern.darf(session.user, aktion, str(typ or ""), objekt or None, **kw))
        for aktion in kern.AKTIONEN
    }


@whitelist(allow_guest=False)
def get_anlegeorte(typ: str) -> dict:
    """Alle Einheiten, in denen der Aufrufer ``typ`` anlegen darf (eine
    Abfrage statt ``get_meine_rechte`` je Gruppe)."""
    return {"orte": verwaltung.anlegeorte(session.user, str(typ or ""))}


@whitelist(allow_guest=False)
def get_sichtbare_module() -> dict:
    """Module fuer die Navigation (ohne Recht erscheint ein Modul nicht)."""
    return {"module": sorted(kern.sichtbare_module(session.user))}


@whitelist(methods=["POST"], allow_guest=False)
def ernenne_mv(gruppe: str, benutzer: str) -> dict:
    return verwaltung.ernenne_mv(session.user, str(gruppe or ""), str(benutzer or ""))


@whitelist(methods=["POST"], allow_guest=False)
def entferne_mv(gruppe: str, benutzer: str) -> dict:
    return verwaltung.entferne_mv(session.user, str(gruppe or ""), str(benutzer or ""))


@whitelist(methods=["POST"], allow_guest=False)
def ernenne_gl(untergruppe: str, benutzer: str) -> dict:
    return verwaltung.ernenne_gl(session.user, str(untergruppe or ""), str(benutzer or ""))


@whitelist(methods=["POST"], allow_guest=False)
def entferne_gl(untergruppe: str, benutzer: str) -> dict:
    return verwaltung.entferne_gl(session.user, str(untergruppe or ""), str(benutzer or ""))


@whitelist(methods=["POST"], allow_guest=False)
def uebertrage_hv(gruppe: str, neuer_hv: str, bestaetigt: Any = False, alter_hv_wird_mv: Any = True) -> dict:
    return verwaltung.uebertrage_hv(
        session.user, str(gruppe or ""), str(neuer_hv or ""),
        bestaetigt=_wahr(bestaetigt), alter_hv_wird_mv=_wahr(alter_hv_wird_mv),
    )


@whitelist(methods=["POST"], allow_guest=False)
def setze_module(gruppe: str, module: Any = None) -> dict:
    if isinstance(module, str):
        import json

        try:
            module = json.loads(module)
        except ValueError:
            module = [m.strip() for m in module.split(",") if m.strip()]
    return verwaltung.setze_module(session.user, str(gruppe or ""), list(module or []))


# ── R-5: Freigaben und Sichtbarkeit (alle Module, z. B. Kalender) ───────────


@whitelist(allow_guest=False)
def get_objekt_rechte(typ: str, objekt: str) -> dict:
    """Freigaben + Sichtbarkeit eines Objekts (nur wer es verwalten darf)."""
    return verwaltung.freigaben_des_objekts(session.user, str(typ or ""), str(objekt or ""))


@whitelist(methods=["POST"], allow_guest=False)
def setze_freigabe(typ: str, objekt: str, benutzer: str | None = None, gruppe: str | None = None,
                   lesen: Any = False, schreiben: Any = False, moderieren: Any = False) -> dict:
    return verwaltung.setze_freigabe(
        session.user, str(typ or ""), str(objekt or ""),
        benutzer=benutzer or None, gruppe=gruppe or None,
        lesen=_wahr(lesen), schreiben=_wahr(schreiben), moderieren=_wahr(moderieren),
    )


@whitelist(methods=["POST"], allow_guest=False)
def setze_standard_gruppe_lesen(typ: str, objekt: str, wert: Any = True) -> dict:
    return verwaltung.setze_standard_gruppe_lesen(session.user, str(typ or ""), str(objekt or ""), _wahr(wert))


@whitelist(methods=["POST"], allow_guest=False)
def beantrage_sichtbarkeit(typ: str, objekt: str, ziel: str) -> dict:
    return verwaltung.beantrage_sichtbarkeit(session.user, str(typ or ""), str(objekt or ""), str(ziel or ""))


@whitelist(methods=["POST"], allow_guest=False)
def entscheide_sichtbarkeit(typ: str, objekt: str, stufe: str, annehmen: Any = False) -> dict:
    return verwaltung.entscheide_sichtbarkeit(
        session.user, str(typ or ""), str(objekt or ""), str(stufe or ""), _wahr(annehmen),
    )


@whitelist(methods=["POST"], allow_guest=False)
def nimm_sichtbarkeit_zurueck(typ: str, objekt: str, ziel: str) -> dict:
    return verwaltung.nimm_sichtbarkeit_zurueck(session.user, str(typ or ""), str(objekt or ""), str(ziel or ""))


@whitelist(allow_guest=False)
def get_offene_sichtbarkeits_antraege(typ: str | None = None) -> dict:
    """Freigabe-Antraege, die der Aufrufer jetzt entscheiden darf (Pruefliste)."""
    return {"antraege": verwaltung.offene_sichtbarkeits_antraege(session.user, typ or None)}


@whitelist(allow_guest=False)
def get_personen_auswahl(suche: str = "", limit: Any = 20) -> dict:
    """Personen mit aktivem Konto fuer Freigaben/Rollen (nur Namen, keine Adressen).

    Manuel 11.11.: Vor- und Nachnamen aller Mitglieder sieht jedes
    Gemeindemitglied — mehr liefert diese Auswahl nicht (``benutzer`` ist die
    Kontokennung, die die Schreib-Endpunkte erwarten).
    """
    from sqlalchemy import select

    from diakronos_app.db import lesesitzung
    from diakronos_app.email_belegung import normalisiere
    from diakronos_app.models.core import User
    from diakronos_app.models.diakonos import Mitglied

    if not kern.ist_gemeindemitglied(session.user):
        return {"personen": []}
    try:
        grenze = max(1, min(int(limit or 20), 50))
    except (TypeError, ValueError):
        grenze = 20
    gesucht = normalisiere(str(suche or "")) or ""
    with lesesitzung() as sess:
        aktiv = set(sess.execute(select(User.name).where(User.enabled.is_(True))).scalars())
        zeilen = sess.execute(select(Mitglied.user, Mitglied.vorname, Mitglied.nachname, Mitglied.ausgeschlossen)
                              .where(Mitglied.user.is_not(None))).all()
    personen = []
    for user, vorname, nachname, ausgeschlossen in zeilen:
        if user not in aktiv or ausgeschlossen:
            continue
        name = f"{vorname or ''} {nachname or ''}".strip() or str(user)
        if gesucht and gesucht not in normalisiere(name):
            continue
        personen.append({"benutzer": user, "name": name})
    personen.sort(key=lambda p: p["name"].lower())
    return {"personen": personen[:grenze]}


# ── R-8: Gast-Links (Wiki, Beitraege) ───────────────────────────────────────


@whitelist(methods=["POST"], allow_guest=False)
def gastlink_erstellen(typ: str, objekt: str, passwort: str, tage: Any = None) -> dict:
    """Gast-Link anlegen (verwalten am Inhalt). Das Token kommt NUR jetzt."""
    from diakronos_app.rechte import gastlinks

    return gastlinks.erstellen(session.user, str(typ or ""), str(objekt or ""), str(passwort or ""), tage)


@whitelist(allow_guest=False)
def get_gastlinks(typ: str, objekt: str) -> dict:
    from diakronos_app.rechte import gastlinks

    return {"links": gastlinks.liste(session.user, str(typ or ""), str(objekt or ""))}


@whitelist(methods=["POST"], allow_guest=False)
def gastlink_widerrufen(link_id: Any) -> dict:
    from diakronos_app.rechte import gastlinks

    try:
        kennung = int(link_id)
    except (TypeError, ValueError):
        from diakronos_app.frappe_compat.exceptions import ValidationError, throw

        throw("Ungültiger Gast-Link.", ValidationError)
    return gastlinks.widerrufen(session.user, kennung)


@whitelist(methods=["POST"], allow_guest=True)
def gast_inhalt(token: str, passwort: str) -> dict:
    """Oeffentlich: Inhalt eines Gast-Links (Token + Passwort, POST).

    Liefert nur Titel, bereinigtes HTML und Datum — keine internen Felder.
    Ungueltig/abgelaufen/widerrufen/geloescht: dieselbe Antwort (404).
    """
    from diakronos_app.frappe_compat.exceptions import DoesNotExistError, PermissionError, throw
    from diakronos_app.frappe_compat.query import get_value
    from diakronos_app.rechte import gastlinks
    from diakronos_app.website.oeffentlich_inhalt import html_erlaubt

    try:
        typ, objekt = gastlinks.oeffnen(str(token or ""), str(passwort or ""))
    except gastlinks.GastLinkUngueltig:
        throw("Dieser Link ist ungültig oder abgelaufen.", DoesNotExistError)
    except gastlinks.GastLinkGesperrt:
        throw("Zu viele Versuche. Bitte versuche es später erneut.", PermissionError)
    doctype = "Beitrag" if typ == "beitrag" else "Wiki Artikel"
    felder = ["titel", "inhalt", "geloescht_am"] + (["datum"] if typ == "beitrag" else ["modified"])
    zeile = get_value(doctype, objekt, felder, as_dict=True)
    if not zeile or zeile.get("geloescht_am") is not None:
        throw("Dieser Link ist ungültig oder abgelaufen.", DoesNotExistError)
    datum = zeile.get("datum") or zeile.get("modified")
    return {"typ": typ, "titel": zeile.get("titel") or "", "inhalt": html_erlaubt(zeile.get("inhalt")),
            "datum": str(datum) if datum else None}


# ── R-10: Rollen-Erklaerungen (ⓘ) ───────────────────────────────────────────


@whitelist(allow_guest=False)
def get_rollen_erklaerung() -> dict:
    """Was bewirkt welche Rolle / welches Modul — EINE Quelle neben dem Kern."""
    from diakronos_app.rechte import erklaerung

    return erklaerung.alles()
