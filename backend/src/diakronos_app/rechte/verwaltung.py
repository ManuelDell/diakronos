"""R-2: Rollen und Module verwalten — schreibende Seite des EINEN Rechtesystems.

Jede Funktion entscheidet ueber :func:`diakronos_app.rechte.kern.pruefe`
(niemals eigene Regeln) und protokolliert die Aenderung im Audit-Log
(``Berechtigungsänderung``).

Regeln (Plan ``diakronos-rechte``, Manuel 11.11.)
  * HV/MV ernennen und entfernen: nur der HV (Aktion ``rollen`` an der Gruppe).
  * GL einer Untergruppe ernennen/entfernen: HV und MV (``rollen`` an der Untergruppe).
  * HV-Amt uebertragen: nur der HV, nur mit ausdruecklicher Bestaetigung;
    der bisherige HV wird MV (abwaehlbar).
  * Den ersten HV einer Gruppe setzt der Administrator; ebenso die Module.
  * Der HV kann nicht „entfernt“ werden — nur uebertragen.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
from typing import Iterator

from sqlalchemy import delete, select

from diakronos_app.db import aktuelle_sitzung, lesesitzung
from diakronos_app.frappe_compat.exceptions import DoesNotExistError, ValidationError, throw
from diakronos_app.models.rechte import (
    ROLLE_GL,
    ROLLE_HV,
    ROLLE_MV,
    RechteGruppenrolle,
    RechteModul,
)
from diakronos_app.rechte import kern
from diakronos_app.rechte.kern import MODULE, ROLLEN, pruefe


@contextmanager
def _schreibsitzung() -> Iterator:
    """Die Aufruf-Sitzung (Request-Rahmen) — sonst eine eigene mit Commit."""
    vorhanden = aktuelle_sitzung.get()
    if vorhanden is not None:
        yield vorhanden
        vorhanden.flush()
        return
    from diakronos_app import db

    sess = db.SessionLocal()
    try:
        yield sess
        sess.commit()
    except Exception:
        sess.rollback()
        raise
    finally:
        sess.close()


def _jetzt() -> datetime:
    return datetime.utcnow().replace(microsecond=0)


def _audit(gruppe: str, text: str) -> None:
    try:
        from diakronos_app.api import audit

        audit.log("Berechtigungsänderung", "Gruppe", gruppe, text)
    except Exception:  # noqa: BLE001 — Protokoll darf die Aenderung nicht verhindern
        from diakronos_app.frappe_compat.api_helpers import log_error

        log_error("rechte: Audit-Eintrag fehlgeschlagen")


def _pruefe_konto(benutzer: str) -> None:
    """Nur aktive Konten bekommen Rollen (fail closed)."""
    if not kern._ist_angemeldetes_mitglied(benutzer):  # noqa: SLF001 — eine Wahrheit
        throw("Diese Person hat kein aktives Konto.", ValidationError)


def _gruppe_existiert(gruppe: str) -> None:
    from diakronos_app.models.diakonos import Gruppe

    with lesesitzung() as sess:
        if sess.get(Gruppe, gruppe) is None:
            throw("Die Gruppe wurde nicht gefunden.", DoesNotExistError)


def _hauptgruppe_von(untergruppe: str) -> str:
    with lesesitzung() as sess:
        gruppe = kern._hauptgruppe(sess, untergruppe)  # noqa: SLF001
    if not gruppe:
        throw("Die Untergruppe wurde nicht gefunden.", DoesNotExistError)
    return str(gruppe)


def _zeile(sess, gruppe: str, benutzer: str, untergruppe: str | None = None) -> RechteGruppenrolle | None:
    bedingung = [RechteGruppenrolle.gruppe == gruppe, RechteGruppenrolle.benutzer == benutzer]
    bedingung.append(
        RechteGruppenrolle.untergruppe == untergruppe if untergruppe else RechteGruppenrolle.untergruppe.is_(None)
    )
    return sess.execute(select(RechteGruppenrolle).where(*bedingung)).scalar_one_or_none()


def _hv(sess, gruppe: str) -> RechteGruppenrolle | None:
    return sess.execute(select(RechteGruppenrolle).where(
        RechteGruppenrolle.gruppe == gruppe, RechteGruppenrolle.rolle == ROLLE_HV
    )).scalar_one_or_none()


# ── Lesen ───────────────────────────────────────────────────────────────────


def rollen_der_gruppe(ausfuehrender: str, gruppe: str) -> dict:
    """HV, MV und GL einer Gruppe (fuer die Gruppen-Einstellungsseite).

    Sichtbar fuer jeden, der die Gruppe lesen darf; die Rechte des
    Ausfuehrenden stehen dabei, damit die Oberflaeche nur erlaubte Knoepfe zeigt.
    """
    pruefe(ausfuehrender, kern.LESEN, "gruppe", gruppe=gruppe)
    darf_ernennen = bool(kern.darf(ausfuehrender, ROLLEN, "gruppe", gruppe=gruppe))
    darf_verwalten = bool(kern.darf(ausfuehrender, kern.VERWALTEN, "gruppe", gruppe=gruppe))
    with lesesitzung() as sess:
        zeilen = sess.execute(
            select(RechteGruppenrolle).where(RechteGruppenrolle.gruppe == gruppe)
            .order_by(RechteGruppenrolle.rolle, RechteGruppenrolle.benutzer)
        ).scalars().all()
        rohdaten = [(z.benutzer, z.rolle, z.untergruppe) for z in zeilen]
    # UI-R1: ANZEIGENAME fuer alle (R-9: Namen sieht jedes Mitglied). Die
    # Kontokennung (oft die E-Mail) nur fuer die Leitung, die sie fuer die
    # Knoepfe braucht — Lesende bekommen sie nicht.
    eintraege = [
        {"benutzer": benutzer if darf_verwalten else None, "rolle": rolle, "untergruppe": ug,
         "name": _anzeigename_konto(benutzer),
         "untergruppe_name": _untergruppenname(ug)}
        for benutzer, rolle, ug in rohdaten
    ]
    return {
        "gruppe": gruppe,
        "rollen": eintraege,
        "darf_hv_mv_ernennen": darf_ernennen,
        "darf_verwalten": darf_verwalten,
    }


def _anzeigename_konto(benutzer: str) -> str:
    """Anzeigename der Person hinter einem Konto (eine Regel: personen_anzeige)."""
    from diakronos_app.frappe_compat.personen_anzeige import PersonenSicht, anzeigename
    from diakronos_app.frappe_compat.query import get_value

    zeile = get_value("Mitglied", {"user": benutzer},
                      ["name", "vorname", "nachname", "ausgeschlossen", "status", "austritt_datum"],
                      as_dict=True)
    if isinstance(zeile, list):
        zeile = zeile[0] if zeile else None
    if zeile:
        return anzeigename(zeile, sicht=PersonenSicht.aus())
    voll = get_value("User", benutzer, "full_name")
    return str(voll or "Konto ohne Person")


def _untergruppenname(untergruppe: str | None) -> str | None:
    if not untergruppe:
        return None
    from diakronos_app.frappe_compat.query import get_value

    return str(get_value("Untergruppe", untergruppe, "untergruppenname") or untergruppe)


# ── MV ──────────────────────────────────────────────────────────────────────


def ernenne_mv(ausfuehrender: str, gruppe: str, benutzer: str) -> dict:
    _gruppe_existiert(gruppe)
    pruefe(ausfuehrender, ROLLEN, "gruppe", gruppe=gruppe)
    _pruefe_konto(benutzer)
    with _schreibsitzung() as sess:
        z = _zeile(sess, gruppe, benutzer)
        if z is not None:
            if z.rolle == ROLLE_HV:
                throw("Diese Person ist bereits Hauptverantwortliche(r).", ValidationError)
            return {"success": True, "bestand": True}
        sess.add(RechteGruppenrolle(gruppe=gruppe, benutzer=benutzer, rolle=ROLLE_MV,
                                    erteilt_von=ausfuehrender, erteilt_am=_jetzt()))
    _audit(gruppe, f"Mitverantwortliche(r) ernannt: {benutzer}")
    return {"success": True, "bestand": False}


def entferne_mv(ausfuehrender: str, gruppe: str, benutzer: str) -> dict:
    pruefe(ausfuehrender, ROLLEN, "gruppe", gruppe=gruppe)
    with _schreibsitzung() as sess:
        z = _zeile(sess, gruppe, benutzer)
        if z is None:
            return {"success": True, "bestand": False}
        if z.rolle == ROLLE_HV:
            throw("Das HV-Amt kann nur übertragen, nicht entfernt werden.", ValidationError)
        sess.delete(z)
    _audit(gruppe, f"Mitverantwortliche(r) entfernt: {benutzer}")
    return {"success": True, "bestand": True}


# ── GL (Untergruppe) ────────────────────────────────────────────────────────


def ernenne_gl(ausfuehrender: str, untergruppe: str, benutzer: str) -> dict:
    gruppe = _hauptgruppe_von(untergruppe)
    pruefe(ausfuehrender, ROLLEN, "untergruppe", untergruppe=untergruppe)
    _pruefe_konto(benutzer)
    with _schreibsitzung() as sess:
        if _zeile(sess, gruppe, benutzer, untergruppe) is not None:
            return {"success": True, "bestand": True}
        sess.add(RechteGruppenrolle(gruppe=gruppe, untergruppe=untergruppe, benutzer=benutzer, rolle=ROLLE_GL,
                                    erteilt_von=ausfuehrender, erteilt_am=_jetzt()))
    _audit(gruppe, f"Gruppenleitung der Untergruppe {untergruppe} ernannt: {benutzer}")
    return {"success": True, "bestand": False}


def entferne_gl(ausfuehrender: str, untergruppe: str, benutzer: str) -> dict:
    gruppe = _hauptgruppe_von(untergruppe)
    pruefe(ausfuehrender, ROLLEN, "untergruppe", untergruppe=untergruppe)
    with _schreibsitzung() as sess:
        z = _zeile(sess, gruppe, benutzer, untergruppe)
        if z is None:
            return {"success": True, "bestand": False}
        sess.delete(z)
    _audit(gruppe, f"Gruppenleitung der Untergruppe {untergruppe} entfernt: {benutzer}")
    return {"success": True, "bestand": True}


# ── HV ──────────────────────────────────────────────────────────────────────


def uebertrage_hv(
    ausfuehrender: str,
    gruppe: str,
    neuer_hv: str,
    *,
    bestaetigt: bool,
    alter_hv_wird_mv: bool = True,
) -> dict:
    """HV-Amt uebertragen (Sicherheitsabfrage: ``bestaetigt`` muss True sein).

    Darf: der amtierende HV oder der Administrator. Hat die Gruppe noch keinen
    HV, setzt ihn nur der Administrator (gleiche Funktion).
    """
    _gruppe_existiert(gruppe)
    pruefe(ausfuehrender, ROLLEN, "gruppe", gruppe=gruppe)
    if bestaetigt is not True:
        throw("Bitte bestätige die Übertragung des HV-Amts.", ValidationError)
    _pruefe_konto(neuer_hv)
    with _schreibsitzung() as sess:
        alt = _hv(sess, gruppe)
        if alt is None and not kern.ist_admin(ausfuehrender):
            throw("Den ersten Hauptverantwortlichen setzt der Administrator.", ValidationError)
        if alt is not None and alt.benutzer == neuer_hv:
            return {"success": True, "bestand": True}
        alter_name = alt.benutzer if alt is not None else None
        # Reihenfolge wegen des „genau ein HV“-Index: erst den alten HV abgeben.
        if alt is not None:
            if alter_hv_wird_mv:
                alt.rolle = ROLLE_MV
                alt.erteilt_von, alt.erteilt_am = ausfuehrender, _jetzt()
            else:
                sess.delete(alt)
            sess.flush()
        neu = _zeile(sess, gruppe, neuer_hv)
        if neu is not None:
            neu.rolle = ROLLE_HV
            neu.erteilt_von, neu.erteilt_am = ausfuehrender, _jetzt()
        else:
            sess.add(RechteGruppenrolle(gruppe=gruppe, benutzer=neuer_hv, rolle=ROLLE_HV,
                                        erteilt_von=ausfuehrender, erteilt_am=_jetzt()))
    if alter_name:
        nachher = "Mitverantwortliche(r)" if alter_hv_wird_mv else "ohne Rolle"
        _audit(gruppe, f"HV-Amt übertragen: {alter_name} -> {neuer_hv} (bisheriger HV jetzt {nachher})")
    else:
        _audit(gruppe, f"Erster Hauptverantwortlicher gesetzt: {neuer_hv}")
    return {"success": True, "bestand": False, "vorher": alter_name}


# ── Objekte registrieren (Aufruf NACH der Rechtepruefung des Anlegens) ────


def registriere_objekt(
    typ: str,
    objekt: str,
    *,
    gruppe: str | None = None,
    untergruppe: str | None = None,
    standard_gruppe_lesen: bool = True,
    eltern_typ: str | None = None,
    eltern_objekt: str | None = None,
) -> None:
    """Neues Modul-Objekt im Rechtesystem anmelden (idempotent).

    Ohne Eintrag verweigert der Kern jeden Zugriff ausser dem Administrator
    (fail closed). Deshalb ruft JEDER Anlege-Endpunkt diese Funktion — nach
    seiner eigenen ``pruefe(..., ANLEGEN, ...)``. Bei einer Untergruppe wird
    die Hauptgruppe selbst ermittelt.
    """
    from diakronos_app.models.rechte import RechteObjekt

    if untergruppe and not gruppe:
        gruppe = _hauptgruppe_von(untergruppe)
    with _schreibsitzung() as sess:
        vorhanden = sess.execute(select(RechteObjekt).where(
            RechteObjekt.typ == typ, RechteObjekt.objekt == objekt)).scalar_one_or_none()
        if vorhanden is not None:
            return
        sess.add(RechteObjekt(typ=typ, objekt=objekt, gruppe=gruppe or None, untergruppe=untergruppe or None,
                              standard_gruppe_lesen=standard_gruppe_lesen,
                              eltern_typ=eltern_typ, eltern_objekt=eltern_objekt))


def entferne_objekt(typ: str, objekt: str) -> None:
    """Objekt endgueltig aus dem Rechtesystem nehmen (samt Freigaben/Gast-Links)."""
    from diakronos_app.models.rechte import RechteFreigabe, RechteGastlink, RechteObjekt

    with _schreibsitzung() as sess:
        for modell in (RechteFreigabe, RechteGastlink, RechteObjekt):
            sess.execute(delete(modell).where(modell.typ == typ, modell.objekt == objekt))


# ── Module (Administrator) ──────────────────────────────────────────────────


def setze_module(ausfuehrender: str, gruppe: str, module: list[str] | tuple[str, ...]) -> dict:
    """Module einer Gruppe festlegen — nur der Administrator (beim Anlegen der Gruppe)."""
    _gruppe_existiert(gruppe)
    if not kern.ist_admin(ausfuehrender):
        from diakronos_app.frappe_compat.exceptions import PermissionError

        throw("Module einer Gruppe legt der Administrator fest.", PermissionError)
    gewuenscht = {str(m) for m in (module or [])}
    unbekannt = gewuenscht - set(MODULE)
    if unbekannt:
        throw(f"Unbekanntes Modul: {', '.join(sorted(unbekannt))}", ValidationError)
    with _schreibsitzung() as sess:
        vorhanden = set(sess.execute(select(RechteModul.modul).where(RechteModul.gruppe == gruppe)).scalars())
        for m in sorted(gewuenscht - vorhanden):
            sess.add(RechteModul(gruppe=gruppe, modul=m))
        weg = vorhanden - gewuenscht
        if weg:
            sess.execute(delete(RechteModul).where(RechteModul.gruppe == gruppe, RechteModul.modul.in_(weg)))
    if gewuenscht != vorhanden:
        _audit(gruppe, f"Module: {', '.join(sorted(gewuenscht)) or '(keine)'}")
    return {"success": True, "module": sorted(gewuenscht)}


__all__ = [
    "entferne_objekt",
    "registriere_objekt",
    "entferne_gl",
    "entferne_mv",
    "ernenne_gl",
    "ernenne_mv",
    "rollen_der_gruppe",
    "setze_module",
    "uebertrage_hv",
]


# ── Freigaben und Sichtbarkeit von Objekten (R-5, fuer alle Module) ────────


def _audit_objekt(typ: str, objekt: str, text: str) -> None:
    try:
        from diakronos_app.api import audit

        audit.log("Berechtigungsänderung", typ.capitalize(), objekt, text)
    except Exception:  # noqa: BLE001 — Protokoll darf die Aenderung nicht verhindern
        from diakronos_app.frappe_compat.api_helpers import log_error

        log_error("rechte: Audit-Eintrag fehlgeschlagen")


def _objekt_zeile(sess, typ: str, objekt: str):
    from diakronos_app.models.rechte import RechteObjekt

    eintrag = sess.execute(select(RechteObjekt).where(
        RechteObjekt.typ == typ, RechteObjekt.objekt == objekt)).scalar_one_or_none()
    if eintrag is None:
        throw("Dieses Element ist im Rechtesystem nicht angemeldet.", DoesNotExistError)
    return eintrag


def setze_freigabe(
    ausfuehrender: str,
    typ: str,
    objekt: str,
    *,
    benutzer: str | None = None,
    gruppe: str | None = None,
    lesen: bool = False,
    schreiben: bool = False,
    moderieren: bool = False,
) -> dict:
    """Freigabe an EINE Person oder EINE Gruppe setzen — sofort wirksam.

    Manuel 11.11.: Freigaben an Einzelpersonen durch HV/MV gelten ohne
    Moderation. Recht: ``verwalten`` am Objekt (HV/MV/GL der Gruppe, bei
    Gemeinde-Objekten Admin/Fachverwaltung). „Moderieren“ gibt es nur am
    Kalender. Alles ``False`` entfernt die Freigabe.
    """
    from diakronos_app.models.rechte import RechteFreigabe

    pruefe(ausfuehrender, kern.VERWALTEN, typ, objekt)
    if bool(benutzer) == bool(gruppe):
        throw("Bitte genau eine Person oder eine Gruppe angeben.", ValidationError)
    if moderieren and typ != "kalender":
        throw("Moderieren gibt es nur bei Kalendern.", ValidationError)
    if moderieren:
        # Moderationsrecht vergeben HV/MV (Gemeinde-Objekt: Admin/Fachverwaltung)
        # — keine GL: sonst koennte die Untergruppe ihre eigene Pruefung besetzen.
        with lesesitzung() as sess:
            gruppe_des_objekts = _objekt_zeile(sess, typ, objekt).gruppe
        stufe = kern.STUFE_GRUPPE if gruppe_des_objekts else kern.STUFE_GEMEINDE
        if not kern.darf(ausfuehrender, kern.MODERIEREN, typ, objekt, stufe=stufe):
            from diakronos_app.frappe_compat.exceptions import PermissionError

            throw("Das Moderationsrecht vergeben nur HV und MV.", PermissionError)
    if benutzer:
        _pruefe_konto(benutzer)
    else:
        _gruppe_existiert(str(gruppe))
    with _schreibsitzung() as sess:
        _objekt_zeile(sess, typ, objekt)
        bedingung = [RechteFreigabe.typ == typ, RechteFreigabe.objekt == objekt]
        bedingung.append(RechteFreigabe.benutzer == benutzer if benutzer else RechteFreigabe.gruppe == gruppe)
        zeile = sess.execute(select(RechteFreigabe).where(*bedingung)).scalar_one_or_none()
        if not (lesen or schreiben or moderieren):
            if zeile is not None:
                sess.delete(zeile)
        else:
            if zeile is None:
                zeile = RechteFreigabe(typ=typ, objekt=objekt, benutzer=benutzer or None, gruppe=gruppe or None)
                sess.add(zeile)
            zeile.lesen, zeile.schreiben, zeile.moderieren = bool(lesen), bool(schreiben), bool(moderieren)
            zeile.erteilt_von, zeile.erteilt_am = ausfuehrender, _jetzt()
    ziel = f"Person {benutzer}" if benutzer else f"Gruppe {gruppe}"
    rechte = ", ".join(n for n, w in (("lesen", lesen), ("schreiben", schreiben), ("moderieren", moderieren)) if w)
    _audit_objekt(typ, objekt, f"Freigabe {ziel}: {rechte or 'entfernt'}")
    return {"success": True}


def freigaben_des_objekts(ausfuehrender: str, typ: str, objekt: str) -> dict:
    """Freigaben + Sichtbarkeit eines Objekts (fuer die Einstellungsseite; ``verwalten``)."""
    from diakronos_app.models.rechte import RechteFreigabe

    pruefe(ausfuehrender, kern.VERWALTEN, typ, objekt)
    with lesesitzung() as sess:
        eintrag = _objekt_zeile(sess, typ, objekt)
        zeilen = sess.execute(select(RechteFreigabe).where(
            RechteFreigabe.typ == typ, RechteFreigabe.objekt == objekt)).scalars().all()
        return {
            "typ": typ, "objekt": objekt,
            "gruppe": eintrag.gruppe, "untergruppe": eintrag.untergruppe,
            "standard_gruppe_lesen": bool(eintrag.standard_gruppe_lesen),
            "gemeinde_status": eintrag.gemeinde_status, "gruppe_status": eintrag.gruppe_status,
            "freigaben": [
                {"benutzer": z.benutzer, "gruppe": z.gruppe, "lesen": bool(z.lesen),
                 "schreiben": bool(z.schreiben), "moderieren": bool(z.moderieren)}
                for z in zeilen
            ],
        }


def setze_standard_gruppe_lesen(ausfuehrender: str, typ: str, objekt: str, wert: bool) -> dict:
    """„Gruppenmitglieder duerfen standardmaessig lesen“ (Frage beim Anlegen)."""
    pruefe(ausfuehrender, kern.VERWALTEN, typ, objekt)
    with _schreibsitzung() as sess:
        _objekt_zeile(sess, typ, objekt).standard_gruppe_lesen = bool(wert)
    _audit_objekt(typ, objekt, f"Gruppe liest standardmäßig: {'ja' if wert else 'nein'}")
    return {"success": True}


def beantrage_sichtbarkeit(ausfuehrender: str, typ: str, objekt: str, ziel: str) -> dict:
    """Objekt fuer die ganze Gruppe (``ziel='gruppe'``, nur Untergruppen-Objekte)
    oder alle Mitglieder der Gemeinde (``ziel='gemeinde'``) freigeben.

    Die Stufen bestimmt der Kern (:func:`kern.freigabe_stufen`): ohne Stufe
    sofort ``aktiv`` (z. B. HV ist Admin), sonst ``beantragt`` — zuerst die
    Gruppenstufe (``gruppe_status``), dann die Gemeinde-Moderation.
    """
    from diakronos_app.models.rechte import GEMEINDE_AKTIV, GEMEINDE_BEANTRAGT

    if ziel not in (kern.STUFE_GRUPPE, kern.STUFE_GEMEINDE):
        throw("Unbekanntes Freigabe-Ziel.", ValidationError)
    pruefe(ausfuehrender, kern.VERWALTEN, typ, objekt)
    stufen = kern.freigabe_stufen(ausfuehrender, typ, objekt, ziel)
    with _schreibsitzung() as sess:
        eintrag = _objekt_zeile(sess, typ, objekt)
        if ziel == kern.STUFE_GRUPPE and not eintrag.untergruppe:
            throw("Nur Elemente einer Untergruppe werden an die Gruppe freigegeben.", ValidationError)
        if eintrag.untergruppe and eintrag.gruppe_status != GEMEINDE_AKTIV:
            eintrag.gruppe_status = GEMEINDE_BEANTRAGT if kern.STUFE_GRUPPE in stufen else GEMEINDE_AKTIV
        if ziel == kern.STUFE_GEMEINDE:
            eintrag.gemeinde_status = GEMEINDE_BEANTRAGT if kern.STUFE_GEMEINDE in stufen else GEMEINDE_AKTIV
        ergebnis = {"success": True, "gruppe_status": eintrag.gruppe_status,
                    "gemeinde_status": eintrag.gemeinde_status}
    _audit_objekt(typ, objekt, f"Sichtbarkeit {ziel} beantragt: {ergebnis}")
    return ergebnis


def entscheide_sichtbarkeit(ausfuehrender: str, typ: str, objekt: str, stufe: str, annehmen: bool) -> dict:
    """Antrag einer Stufe annehmen oder ablehnen (Pruefer dieser Stufe, Kern).

    Die Gemeinde-Stufe ist erst dran, wenn die Gruppenstufe erledigt ist.
    Ablehnen setzt die Stufe auf ``aus``.
    """
    from diakronos_app.models.rechte import GEMEINDE_AKTIV, GEMEINDE_AUS, GEMEINDE_BEANTRAGT

    with _schreibsitzung() as sess:
        eintrag = _objekt_zeile(sess, typ, objekt)
        if stufe == kern.STUFE_GRUPPE:
            if eintrag.gruppe_status != GEMEINDE_BEANTRAGT:
                throw("Hier ist keine Freigabe an die Gruppe beantragt.", ValidationError)
            if not kern.darf_stufe(ausfuehrender, typ, objekt, kern.STUFE_GRUPPE):
                from diakronos_app.frappe_compat.exceptions import PermissionError

                throw("Dafür fehlt dir die Berechtigung.", PermissionError)
            eintrag.gruppe_status = GEMEINDE_AKTIV if annehmen else GEMEINDE_AUS
            if not annehmen and eintrag.gemeinde_status == GEMEINDE_BEANTRAGT:
                eintrag.gemeinde_status = GEMEINDE_AUS
        elif stufe == kern.STUFE_GEMEINDE:
            if eintrag.gemeinde_status != GEMEINDE_BEANTRAGT:
                throw("Hier ist keine Freigabe für die Gemeinde beantragt.", ValidationError)
            if eintrag.untergruppe and eintrag.gruppe_status == GEMEINDE_BEANTRAGT:
                throw("Zuerst muss die Gruppenleitung zustimmen.", ValidationError)
            # Die Gemeinde-Stufe eines (noch) nicht freigegebenen Objekts:
            # pruefen darf Admin, Kalender-Moderation oder Freigabe „moderieren“.
            if not (kern.ist_admin(ausfuehrender)
                    or kern.darf(ausfuehrender, kern.MODERIEREN, typ, objekt, stufe=kern.STUFE_GEMEINDE)):
                from diakronos_app.frappe_compat.exceptions import PermissionError

                throw("Dafür fehlt dir die Berechtigung.", PermissionError)
            eintrag.gemeinde_status = GEMEINDE_AKTIV if annehmen else GEMEINDE_AUS
        else:
            throw("Unbekannte Stufe.", ValidationError)
        ergebnis = {"success": True, "gruppe_status": eintrag.gruppe_status,
                    "gemeinde_status": eintrag.gemeinde_status}
    _audit_objekt(typ, objekt, f"Sichtbarkeit Stufe {stufe}: {'angenommen' if annehmen else 'abgelehnt'}")
    return ergebnis


def nimm_sichtbarkeit_zurueck(ausfuehrender: str, typ: str, objekt: str, ziel: str) -> dict:
    """Freigabe an Gruppe/Gemeinde zuruecknehmen (``verwalten``; sofort)."""
    from diakronos_app.models.rechte import GEMEINDE_AUS

    pruefe(ausfuehrender, kern.VERWALTEN, typ, objekt)
    with _schreibsitzung() as sess:
        eintrag = _objekt_zeile(sess, typ, objekt)
        if ziel == kern.STUFE_GEMEINDE:
            eintrag.gemeinde_status = GEMEINDE_AUS
        elif ziel == kern.STUFE_GRUPPE:
            eintrag.gruppe_status = GEMEINDE_AUS
        else:
            throw("Unbekanntes Freigabe-Ziel.", ValidationError)
    _audit_objekt(typ, objekt, f"Sichtbarkeit {ziel} zurückgenommen")
    return {"success": True}


def offene_sichtbarkeits_antraege(benutzer: str, typ: str | None = None) -> list[dict]:
    """Antraege, die ``benutzer`` JETZT entscheiden darf (fuer die Pruefliste)."""
    from diakronos_app.models.rechte import GEMEINDE_BEANTRAGT, RechteObjekt

    with lesesitzung() as sess:
        bedingung = [(RechteObjekt.gruppe_status == GEMEINDE_BEANTRAGT)
                     | (RechteObjekt.gemeinde_status == GEMEINDE_BEANTRAGT)]
        if typ:
            bedingung.append(RechteObjekt.typ == typ)
        zeilen = [(z.typ, z.objekt, z.gruppe, z.untergruppe, z.gruppe_status, z.gemeinde_status)
                  for z in sess.execute(select(RechteObjekt).where(*bedingung)).scalars()]
    out: list[dict] = []
    for z_typ, z_obj, z_gr, z_ug, g_status, gem_status in zeilen:
        # UI-R4: Anzeige ohne technische Schluessel — Titel des Inhalts, Namen
        # der (Unter-)Gruppe und das ZIEL des Antrags (eine Untergruppe, die
        # „fuer alle Mitglieder der Gemeinde“ beantragt, durchlaeuft zuerst die
        # Gruppenstufe; das Ziel bleibt dabei „gemeinde“).
        anzeige = {"titel": _objekt_titel(z_typ, z_obj), "gruppe_name": _name("Gruppe", z_gr),
                   "untergruppe_name": _name("Untergruppe", z_ug),
                   "ziel": "gemeinde" if gem_status == GEMEINDE_BEANTRAGT else "gruppe"}
        if g_status == GEMEINDE_BEANTRAGT:
            if kern.darf_stufe(benutzer, z_typ, z_obj, kern.STUFE_GRUPPE):
                out.append({"typ": z_typ, "objekt": z_obj, "gruppe": z_gr, "untergruppe": z_ug,
                            "stufe": kern.STUFE_GRUPPE, **anzeige})
            continue
        if gem_status == GEMEINDE_BEANTRAGT and (
            kern.ist_admin(benutzer)
            or kern.darf(benutzer, kern.MODERIEREN, z_typ, z_obj, stufe=kern.STUFE_GEMEINDE)
        ):
            out.append({"typ": z_typ, "objekt": z_obj, "gruppe": z_gr, "untergruppe": z_ug,
                        "stufe": kern.STUFE_GEMEINDE, **anzeige})
    return out


#: Typ im Rechtesystem -> (DocType, Titelfeld) fuer die Anzeige.
_TITEL_QUELLE = {
    "kalender": ("Kalender", "calendar_name"),
    "beitrag": ("Beitrag", "titel"),
    "wiki": ("Wiki Artikel", "titel"),
    "aufgabe": ("Gruppen Aufgabe", "titel"),
}


def _objekt_titel(typ: str, objekt: str) -> str:
    """Anzeigetitel eines Inhalts; Fallback ist die Kennung (nie ein Fehler)."""
    from diakronos_app.frappe_compat.query import get_value

    quelle = _TITEL_QUELLE.get(typ)
    if not quelle:
        return objekt
    try:
        return str(get_value(quelle[0], objekt, quelle[1]) or objekt)
    except Exception:  # noqa: BLE001 — Anzeige darf die Liste nicht brechen
        return objekt


def _name(doctype: str, kennung: str | None) -> str | None:
    if not kennung:
        return None
    from diakronos_app.frappe_compat.query import get_value

    feld = "gruppenname" if doctype == "Gruppe" else "untergruppenname"
    try:
        return str(get_value(doctype, kennung, feld) or kennung)
    except Exception:  # noqa: BLE001
        return kennung


# ── Inhalte anlegen (Beitraege, Wiki …) — R-7 ──────────────────────────────


def pruefe_inhalt_anlegen(ausfuehrender: str, typ: str, gruppe: str | None, untergruppe: str | None) -> None:
    """Anlegen eines Inhalts: in einer (Unter-)Gruppe die Leitung (HV/MV, GL;
    Modul aktiv), gemeindeweit nur der Admin (Manuel 11.11.: Beitraege und
    Wiki sind gruppengebunden)."""
    if gruppe or untergruppe:
        pruefe(ausfuehrender, kern.ANLEGEN, typ, gruppe=gruppe or None, untergruppe=untergruppe or None)
        return
    if not kern.ist_admin(ausfuehrender):
        from diakronos_app.frappe_compat.exceptions import PermissionError

        throw("Inhalte für die ganze Gemeinde legt der Administrator an. "
              "Bitte eine Gruppe wählen.", PermissionError)


def anlegeorte(benutzer: str, typ: str) -> list[dict]:
    """Wo darf ``benutzer`` einen Inhalt ``typ`` anlegen? Dieselbe Regel wie
    :func:`pruefe_inhalt_anlegen`, fuer alle Einheiten in EINER Abfrage.

    Reihenfolge: Gemeinde (nur Admin), dann je Gruppe die Gruppe und ihre
    Untergruppen (nach Namen). ``tiefe`` 0 = Gemeinde/Gruppe, 1 = Untergruppe.
    """
    from diakronos_app.models.diakonos import Gruppe, Untergruppe
    from diakronos_app.rechte.erklaerung import STUFEN_TITEL

    admin = kern.ist_admin(benutzer)
    kandidaten = None if admin else kern.eigene_gruppen(benutzer)
    if kandidaten is not None and not kandidaten:
        return []
    with lesesitzung() as sess:
        abfrage = select(Gruppe.name, Gruppe.gruppenname).where(Gruppe.geloescht_am.is_(None))
        if kandidaten is not None:
            abfrage = abfrage.where(Gruppe.name.in_(kandidaten))
        gruppen = sess.execute(abfrage).all()
        untergruppen = sess.execute(
            select(Untergruppe.name, Untergruppe.untergruppenname, Untergruppe.gruppe)
            .where(Untergruppe.gruppe.in_([g.name for g in gruppen]))
        ).all() if gruppen else []

    orte: list[dict] = []
    if admin:
        orte.append({"gruppe": None, "untergruppe": None, "titel": STUFEN_TITEL[kern.STUFE_GEMEINDE],
                     "tiefe": 0, "gemeinde": True})
    for g in sorted(gruppen, key=lambda z: str(z.gruppenname or z.name).casefold()):
        if kern.darf(benutzer, kern.ANLEGEN, typ, None, gruppe=g.name):
            orte.append({"gruppe": g.name, "untergruppe": None, "titel": str(g.gruppenname or g.name),
                         "tiefe": 0, "gemeinde": False})
        eigene = [u for u in untergruppen if u.gruppe == g.name]
        for u in sorted(eigene, key=lambda z: str(z.untergruppenname or z.name).casefold()):
            if kern.darf(benutzer, kern.ANLEGEN, typ, None, gruppe=g.name, untergruppe=u.name):
                orte.append({"gruppe": g.name, "untergruppe": u.name,
                             "titel": str(u.untergruppenname or u.name), "tiefe": 1, "gemeinde": False})
    return orte


def inhalt_anmelden(ausfuehrender: str, typ: str, objekt: str, gruppe: str | None,
                    untergruppe: str | None) -> None:
    """Neuen Inhalt im Rechtesystem anmelden. Gemeinde-Inhalt (nur Admin legt
    ihn an) ist sofort fuer alle Mitglieder sichtbar."""
    from diakronos_app.models.rechte import GEMEINDE_AKTIV, RechteObjekt

    registriere_objekt(typ, objekt, gruppe=gruppe or None, untergruppe=untergruppe or None)
    if not (gruppe or untergruppe):
        with _schreibsitzung() as sess:
            eintrag = sess.execute(select(RechteObjekt).where(
                RechteObjekt.typ == typ, RechteObjekt.objekt == objekt)).scalar_one()
            eintrag.gemeinde_status = GEMEINDE_AKTIV
