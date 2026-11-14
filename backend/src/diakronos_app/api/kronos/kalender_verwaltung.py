"""Kalenderverwaltung (OP-ADMIN-10) — Anlegen, Aendern, Loeschen, Rechte.

VORLAGE (READ-ONLY): `referenz/diakronos-frappe/diakronos/kronos/api/permissions.py`
und das DocType `referenz/diakronos-frappe/diakronos/kronos/doctype/kalender/kalender.json`.

Warum ein eigenes Modul und kein Zusatz in `permissions.py`
-----------------------------------------------------------
`permissions.py` ist die Portierung der Rechte-AUSKUNFT (Lesen). Hier stehen die
SCHREIBENDEN Endpunkte, die es im Altcode gar nicht gab: Kalender liessen sich
nur ueber den iCal-Import anlegen, Rechte und Moderatoren waren in der
Oberflaeche nicht einstellbar (Nachtbefund OP-ADMIN-10). Die Datei liegt
deshalb neben `permissions.py` statt darin — die Rechte-Auskunft bleibt 1:1
die Portierung, die Verwaltung ist eine neue, klar begrenzte Flaeche.

Berechtigung
------------
Genau die Rolle, die auch `get_accessible_calendars` als „global“ behandelt
(`_is_kalenderadministrator`): `Administrator` oder `Kalenderadministrator`.
Ein Kalender-Moderator darf Termine moderieren, aber keine Kalender anlegen
oder loeschen — sonst koennte er sich selbst Rechte verschaffen. Fail closed:
ohne Rolle -> `PermissionError`.

Frappe-Aufrufe des Originals -> Compat-Schicht:

    frappe.get_doc("Kalender", name)   -> get_doc(...)
    frappe.get_all("Kalender", ...)    -> get_all(...)
    doc.insert()/save()                -> _create(...) / _update_doc(...)
    doc.append("kalendermoderatoren",) -> _child_replace(...)
    frappe.delete_doc(...)             -> _delete_doc(...)
    frappe.throw(...)                  -> throw(...)
"""

from __future__ import annotations

# Siehe Modulkopf: fachlich Kalenderverwaltung, deshalb der Kronos-Pfad.
FRAPPE_MODULE = "diakronos.kronos.api.kalender_verwaltung"

import json
from typing import Any

from diakronos_app.frappe_compat.api_helpers import (
    _child_delete,
    _create,
    _delete_doc,
    _update_doc,
    get_all,
    get_doc,
)
from diakronos_app.frappe_compat.exceptions import (
    PermissionError as FrappePermissionError,
    ValidationError,
    throw,
)
from diakronos_app.frappe_compat.registry import whitelist
from diakronos_app.api.farbe import KALENDER_STANDARD_FARBE, KALENDER_STANDARD_FARBE_OHNE
from diakronos_app.frappe_compat.session import session

__all__ = [
    "create_kalender",
    "delete_kalender",
    "get_kalender_verwaltung",
    "update_kalender",
]

#: Farbe, wenn keine angegeben ist — dieselbe Vorgabe wie in
#: `permissions.get_accessible_calendars`. Der Wert steht in `api/farbe.py`
#: (ON-0c, R2: EINE Stelle fuer die Standardfarben, keine Literale verstreut).
STANDARD_FARBE = KALENDER_STANDARD_FARBE_OHNE

#: Beispiel in der Fehlermeldung — ebenfalls zentral (kein Literal im Text).
BEISPIEL_FARBE = KALENDER_STANDARD_FARBE

#: Kind-Tabellen der Kalender und ihre Elternfelder.
MODERATOR_FELD = "kalendermoderatoren"
MODERATOR_TABELLE = "Kalender Moderator"
LESERECHT_FELD = "leserechte"
SCHREIBRECHT_FELD = "schreibrechte"
ROLLE_TABELLE = "User Role"


def _require_kalender_admin() -> str:
    """Nur Administrator / Kalenderadministrator. Fail closed."""
    user = session.user
    if not user or user == "Guest":
        throw("Anmeldung erforderlich.", FrappePermissionError)

    from diakronos_app.api.kronos.permissions import _is_kalenderadministrator

    if not _is_kalenderadministrator(user):
        throw(
            "Nur Kalenderadministratoren dürfen Kalender verwalten.",
            FrappePermissionError,
        )
    return user


def _pruefe_titel(wert: Any) -> str:
    """Anzeigename pruefen: Pflicht, getrimmt, hoechstens 140 Zeichen."""
    text = str(wert or "").strip()
    if not text:
        raise ValidationError("Bitte einen Namen für den Kalender angeben.")
    if len(text) > 140:
        raise ValidationError("Der Name darf höchstens 140 Zeichen lang sein.")
    return text


def _pruefe_farbe(wert: Any) -> str:
    """Kalenderfarbe: leer oder `#rrggbb`, sonst Standardfarbe.

    Die Farbe landet im Frontend in einer CSS-Variable; ein beliebiger Text
    waere dort eine Einladung zum Stilbruch. Geprueft wird deshalb eng.
    """
    text = str(wert or "").strip()
    if not text:
        return STANDARD_FARBE
    if len(text) != 7 or not text.startswith("#"):
        raise ValidationError(f"Farbe bitte als #rrggbb angeben (z.B. {BEISPIEL_FARBE}).")
    try:
        int(text[1:], 16)
    except ValueError as exc:
        raise ValidationError(f"Farbe bitte als #rrggbb angeben (z.B. {BEISPIEL_FARBE}).") from exc
    return text.lower()


def _bekannte_rollen() -> tuple[str, ...]:
    """Rollen, die in einer Rechtezeile stehen duerfen.

    Quelle ist die `role`-Tabelle, wenn sie Zeilen fuehrt; dazu die
    Anwendungsrollen aus `_BEKANNTE_ROLLEN` und die beiden Frappe-Sonderrollen
    `All`/`Guest` — genau die, die `_user_has_role` in `permissions.py`
    auswertet und die im Altcode in echten `leserechte`-Zeilen standen.
    """
    namen: set[str] = {"All", "Guest"}
    from diakronos_app.db import SessionLocal
    from diakronos_app.models.core import Role

    try:
        with SessionLocal() as sess:
            for r in sess.query(Role).all():
                if getattr(r, "name", None):
                    namen.add(str(r.name).strip())
    except Exception:  # noqa: BLE001 — Rollentabelle ist Zusatz, kein Kern
        pass
    from diakronos_app.anmeldung.einstellungen_api import _BEKANNTE_ROLLEN

    namen.update(_BEKANNTE_ROLLEN)
    return tuple(sorted(n for n in namen if n))


def _pruefe_rollen(rollen: Any, feld: str) -> list[str] | None:
    """Rollenliste (Leserecht/Schreibrecht) pruefen.

    `None` bedeutet „nicht mitgeschickt“ — die Liste bleibt dann unveraendert.
    Eine LEERE Liste heisst ausdruecklich „niemand“. `All` ist eine gueltige
    Rolle (jeder angemeldete Nutzer), `Guest` ebenfalls.
    """
    if rollen is None:
        return None
    if isinstance(rollen, str):
        try:
            rollen = json.loads(rollen)
        except (TypeError, ValueError) as exc:
            raise ValidationError(f"{feld}: ungültige Liste.") from exc
    if not isinstance(rollen, list):
        raise ValidationError(f"{feld}: muss eine Liste von Rollen sein.")

    erlaubt = set(_bekannte_rollen())
    ergebnis: list[str] = []
    for eintrag in rollen:
        name = str(eintrag or "").strip()
        if not name or name in ergebnis:
            continue
        if name not in erlaubt:
            raise ValidationError(f"{feld}: unbekannte Rolle „{name}“.")
        ergebnis.append(name)
    return ergebnis


def _pruefe_moderatoren(moderatoren: Any) -> list[str] | None:
    """Benutzernamen fuer die Moderatorzeilen pruefen.

    Die Zeile zeigt auf `user.name`; ein unbekanntes Konto in der Kind-Tabelle
    waere ein toter Verweis (der Benutzer taucht nie in einer Liste auf und
    kann nie entfernt werden, weil niemand ihn findet).
    """
    if moderatoren is None:
        return None
    if isinstance(moderatoren, str):
        try:
            moderatoren = json.loads(moderatoren)
        except (TypeError, ValueError) as exc:
            raise ValidationError("Moderatoren: ungültige Liste.") from exc
    if not isinstance(moderatoren, list):
        raise ValidationError("Moderatoren: muss eine Liste von Benutzern sein.")

    from diakronos_app.frappe_compat import db

    ergebnis: list[str] = []
    for eintrag in moderatoren:
        name = str(eintrag or "").strip()
        if not name or name in ergebnis:
            continue
        try:
            bekannt = bool(db.exists("User", {"name": name}))
        except Exception:  # noqa: BLE001 — nicht bestaetigt = nicht zulassen
            bekannt = False
        if not bekannt:
            raise ValidationError(f"Moderatoren: „{name}“ ist kein bekanntes Konto.")
        ergebnis.append(name)
    return ergebnis


def _zeilen_zu_namen(zeilen: list[dict[str, Any]], feld: str) -> list[str]:
    """Kind-Zeilen auf den reinen Wert reduzieren (ohne Dubletten)."""
    namen: list[str] = []
    for zeile in zeilen or []:
        wert = str(zeile.get(feld) or "").strip()
        if wert and wert not in namen:
            namen.append(wert)
    return namen


# ── R-5: Kalender im EINEN Rechtesystem ───────────────────────────────────


def _require_angemeldet() -> str:
    user = session.user
    if not user or user == "Guest":
        throw("Anmeldung erforderlich.", FrappePermissionError)
    return str(user)


def _require_kalender_verwalten(name: str) -> str:
    """R-5: Kalender aendern/loeschen darf, wer ihn im Kern ``verwalten`` darf
    (HV/MV der Gruppe, GL der Untergruppe; Gemeinde-Kalender: Admin und
    Kalender-Moderation)."""
    from diakronos_app import rechte

    user = _require_angemeldet()
    if not rechte.darf(user, rechte.VERWALTEN, "kalender", name):
        throw("Diesen Kalender darfst du nicht verwalten.", FrappePermissionError)
    return user


_GEMEINDE_ROLLEN = {"Mitglied", "All"}


def _rechte_aus_alteingaben(name: str, user: str, lese: list[str] | None,
                            mods: list[str] | None) -> None:
    """Uebergang bis die Oberflaeche umgestellt ist (R-5c): die alten Felder
    in das EINE Rechtesystem uebertragen — dieselbe Abbildung wie die
    Migration r1_rechte_kern. Leserecht „Mitglied“/„All“ = fuer die Gemeinde
    freigeben (mit Moderation, ausser Admin); Moderatoren = Einzelfreigabe
    „moderieren“."""
    from diakronos_app.rechte import verwaltung as rv

    if lese is not None:
        ziel = rv.freigaben_des_objekts(user, "kalender", name)["gemeinde_status"]
        if _GEMEINDE_ROLLEN & set(lese):
            if ziel == "aus":
                rv.beantrage_sichtbarkeit(user, "kalender", name, "gemeinde")
        elif ziel != "aus":
            rv.nimm_sichtbarkeit_zurueck(user, "kalender", name, "gemeinde")
    if mods is not None:
        bisher = {f["benutzer"] for f in rv.freigaben_des_objekts(user, "kalender", name)["freigaben"]
                  if f["benutzer"] and f["moderieren"]}
        for person in sorted(set(mods) - bisher):
            rv.setze_freigabe(user, "kalender", name, benutzer=person, lesen=True, moderieren=True)
        for person in sorted(bisher - set(mods)):
            rv.setze_freigabe(user, "kalender", name, benutzer=person)


def _kalender_eintrag(doc) -> dict[str, Any]:
    """Ein Kalender in der Form, die die Verwaltungsseite braucht.

    UX2c-N2: `calender_details` kommt mit, damit die Seite erkennt, ob nach
    dem Loeschen ein „Rueckgaengig“ den Zustand VOLLSTAENDIG herstellt —
    `create_kalender` nimmt das Feld nicht an (es setzt nur der Google-Import).
    """
    return {
        "name": doc.name,
        "titel": doc.get("calendar_name") or doc.name,
        "farbe": doc.get("calendar_color") or STANDARD_FARBE,
        "selbstverwaltet": bool(doc.get("selbstverwaltet")),
        "calender_details": doc.get("calender_details") or "",
        **_alte_felder_aus_rechten(doc.name),
        **_rechte_felder(doc.name),
    }


def _alte_felder_aus_rechten(name: str) -> dict[str, list[str]]:
    """R-11e: die Felder der alten Verwaltungsseite — abgeleitet aus dem EINEN
    Rechtesystem statt aus den Alt-Tabellen (die nicht mehr geschrieben
    werden). Entfaellt mit UI-R3: „Mitglied“ = fuer die Gemeinde freigegeben,
    Moderatoren = Einzelfreigaben „moderieren“."""
    from sqlalchemy import select

    from diakronos_app.db import lesesitzung
    from diakronos_app.models.rechte import RechteFreigabe, RechteObjekt

    with lesesitzung() as sess:
        status = sess.execute(select(RechteObjekt.gemeinde_status).where(
            RechteObjekt.typ == "kalender", RechteObjekt.objekt == name)).scalar_one_or_none()
        mods = sorted(sess.execute(select(RechteFreigabe.benutzer).where(
            RechteFreigabe.typ == "kalender", RechteFreigabe.objekt == name,
            RechteFreigabe.moderieren.is_(True), RechteFreigabe.benutzer.is_not(None))).scalars())
    return {"leserechte": ["Mitglied"] if status and status != "aus" else [],
            "schreibrechte": [], "moderatoren": mods}


def _rechte_felder(name: str) -> dict[str, Any]:
    """R-5: Zuordnung und Sichtbarkeit aus dem Rechtesystem."""
    from sqlalchemy import select

    from diakronos_app.db import lesesitzung
    from diakronos_app.models.rechte import RechteObjekt

    with lesesitzung() as sess:
        e = sess.execute(select(RechteObjekt).where(
            RechteObjekt.typ == "kalender", RechteObjekt.objekt == name)).scalar_one_or_none()
        if e is None:
            return {"gruppe": None, "untergruppe": None, "standard_gruppe_lesen": True,
                    "gemeinde_status": "aus", "gruppe_status": "aus"}
        return {"gruppe": e.gruppe, "untergruppe": e.untergruppe,
                "standard_gruppe_lesen": bool(e.standard_gruppe_lesen),
                "gemeinde_status": e.gemeinde_status, "gruppe_status": e.gruppe_status}


@whitelist(allow_guest=False)
def get_kalender_verwaltung():
    """Alle Kalender mit Rechten und Moderatoren (nur Kalenderadministratoren).

    Die Liste ist bewusst NICHT auf die eigenen Kalender eingeschraenkt: wer
    verwalten darf, sieht alles zu Verwaltende — sonst koennte er einen
    Kalender anlegen, aber nicht mehr bearbeiten.
    """
    # R-5: jeder sieht die Kalender, die er im Rechte-Kern verwalten darf;
    # anlegen in den Gruppen mit ``anlegen`` (HV/MV, GL) — Gemeinde-Kalender
    # nur Admin/Kalender-Moderation.
    from diakronos_app import rechte
    from diakronos_app.api.kronos.permissions import _is_kalenderadministrator

    user = _require_angemeldet()
    namen = get_all("Kalender", fields=["name"], order_by="name asc") or []
    kalender = []
    for eintrag in namen:
        if not rechte.darf(user, rechte.VERWALTEN, "kalender", eintrag["name"]):
            continue
        try:
            kalender.append(_kalender_eintrag(get_doc("Kalender", eintrag["name"])))
        except Exception:  # noqa: BLE001 — eine kaputte Zeile darf die Liste nicht kippen
            continue

    gemeinde = _is_kalenderadministrator(user)
    anlegen = [g["name"] for g in get_all("Gruppe", fields=["name"]) or []
               if rechte.darf(user, rechte.ANLEGEN, "kalender", gruppe=g["name"])]
    anlegen_ug = [u["name"] for u in get_all("Untergruppe", fields=["name"]) or []
                  if rechte.darf(user, rechte.ANLEGEN, "kalender", untergruppe=u["name"])]
    if not (kalender or gemeinde or anlegen or anlegen_ug):
        throw("Nur Kalenderverantwortliche dürfen Kalender verwalten.", FrappePermissionError)

    return {
        "kalender": kalender,
        "rollen": list(_bekannte_rollen()),
        "farbe_standard": STANDARD_FARBE,
        # R-5: wo der Aufrufer neue Kalender anlegen darf
        "darf_gemeinde_kalender": gemeinde,
        "anlegen_gruppen": anlegen,
        "anlegen_untergruppen": anlegen_ug,
    }


@whitelist(methods=["POST"], allow_guest=False)
def create_kalender(titel, farbe="", selbstverwaltet=0, leserechte=None,
                    schreibrechte=None, moderatoren=None, gruppe=None,
                    untergruppe=None, standard_gruppe_lesen=1):
    """Neuen Kalender anlegen.

    Der Name ist frei waehlbar (Frappe-Namenskonvention): Termine zeigen mit
    `element_calendar` als Klartext auf den Namen, ein sprechender Name ist
    also genau richtig. Doppelte Anzeigenamen werden abgelehnt — zwei Kalender
    mit demselben Namen waeren in jeder Auswahlliste nicht unterscheidbar.

    R-5 (Manuel 11.11.): Mit ``gruppe``/``untergruppe`` legt die Leitung
    (HV/MV bzw. GL, Modul Kalender aktiv) einen Gruppenkalender an;
    ``standard_gruppe_lesen`` beantwortet die Frage „Duerfen alle
    Gruppenmitglieder standardmaessig lesen?“. Ohne Gruppe entsteht ein
    Gemeinde-Kalender (Admin/Kalender-Moderation).
    """
    from diakronos_app import rechte
    from diakronos_app.api.kronos.permissions import _is_kalenderadministrator
    from diakronos_app.rechte import verwaltung as rv

    user = _require_angemeldet()
    gruppe = str(gruppe or "").strip() or None
    untergruppe = str(untergruppe or "").strip() or None
    if gruppe or untergruppe:
        rechte.pruefe(user, rechte.ANLEGEN, "kalender", gruppe=gruppe, untergruppe=untergruppe)
    elif not _is_kalenderadministrator(user):
        throw("Gemeinde-Kalender legen Admin und Kalender-Moderation an.", FrappePermissionError)

    name = _pruefe_titel(titel)
    gelesen = _pruefe_rollen(leserechte, "Leserechte")
    _pruefe_rollen(schreibrechte, "Schreibrechte")  # R-11e: nur noch geprueft (Alt-Feld, UI-R3)
    mods = _pruefe_moderatoren(moderatoren)

    from diakronos_app.frappe_compat import db

    if db.exists("Kalender", {"name": name}):
        raise ValidationError(f"Ein Kalender mit dem Namen „{name}“ gibt es schon.")
    doppelt = get_all(
        "Kalender", filters={"calendar_name": name}, fields=["name"], limit_page_length=1
    ) or []
    if doppelt:
        raise ValidationError(f"Ein Kalender mit dem Namen „{name}“ gibt es schon.")

    _create(
        "Kalender",
        {
            "name": name,
            "calendar_name": name,
            "calendar_color": _pruefe_farbe(farbe),
            "selbstverwaltet": 1 if selbstverwaltet else 0,
        },
    )
    # R-5: ohne Anmeldung im Rechtesystem saehe den Kalender niemand (fail closed).
    rv.registriere_objekt(
        "kalender", name, gruppe=gruppe, untergruppe=untergruppe,
        standard_gruppe_lesen=str(standard_gruppe_lesen).strip().lower() not in ("0", "false", "nein", ""),
    )
    _rechte_aus_alteingaben(name, user, gelesen, mods)
    return {"success": True, "name": name}


@whitelist(methods=["POST"], allow_guest=False)
def update_kalender(name, titel=None, farbe=None, selbstverwaltet=None,
                    leserechte=None, schreibrechte=None, moderatoren=None):
    """Kalender aendern: Anzeigename, Farbe, Selbstverwaltung, Rechte, Moderatoren.

    Nicht mitgeschickte Felder bleiben unveraendert (`None`). Fuer die Listen
    heisst eine LEERE Liste ausdruecklich „niemand“ — das ist der Unterschied
    zwischen „Feld nicht gesendet“ und „bewusst geleert“.

    Umbenennen betrifft nur den ANZEIGENAMEN (`calendar_name`). Der Schluessel
    `name` bleibt: auf ihn zeigen die Termine (`element_calendar`), ein
    Umbenennen wuerde jeden Termin vom Kalender trennen.
    """
    user = _require_kalender_verwalten(str(name or "").strip())

    doc = get_doc("Kalender", str(name or "").strip())
    if doc is None:
        raise ValidationError("Kalender nicht gefunden.")

    werte: dict[str, Any] = {}
    if titel is not None:
        neu = _pruefe_titel(titel)
        if neu != (doc.get("calendar_name") or doc.name):
            doppelt = get_all(
                "Kalender", filters={"calendar_name": neu}, fields=["name"], limit_page_length=5
            ) or []
            if any(z.get("name") != doc.name for z in doppelt):
                raise ValidationError(f"Ein Kalender mit dem Namen „{neu}“ gibt es schon.")
        werte["calendar_name"] = neu
    if farbe is not None:
        werte["calendar_color"] = _pruefe_farbe(farbe)
    if selbstverwaltet is not None:
        werte["selbstverwaltet"] = 1 if selbstverwaltet else 0

    # R-P2-5 (klein 3): Rechte und Moderatoren VOR dem Schreiben pruefen. Vorher
    # lief `_pruefe_rollen`/`_pruefe_moderatoren` erst nach `_update_doc`; ein
    # ungueltiger Wert hat den Titel/Farbe-Teil zwar per Request-Transaktion
    # zurueckgerollt, aber die Reihenfolge erzeugte unnoetige Schreibversuche
    # und liess Fehler in falscher Reihenfolge auflaufen.
    lese = _pruefe_rollen(leserechte, "Leserechte")
    _pruefe_rollen(schreibrechte, "Schreibrechte")  # R-11e: nur noch geprueft (Alt-Feld, UI-R3)
    mods = _pruefe_moderatoren(moderatoren)

    if werte:
        _update_doc("Kalender", doc.name, werte)

    _rechte_aus_alteingaben(doc.name, user, lese, mods)
    return {"success": True, "name": doc.name}


@whitelist(methods=["POST"], allow_guest=False)
def delete_kalender(name, bestaetigt=0):
    """Kalender loeschen — nur ohne Verweise, und nur mit Rueckfrage.

    Ein Kalender, auf den noch etwas zeigt, wird NICHT geloescht: ein Loeschen
    liesse die Verweise ins Leere zeigen (Termin im Kalender unsichtbar,
    Standardkalender einer Vorlage unaufloesbar). Geprueft werden ALLE Verweise:

      * `Element.element_calendar` — AUCH stornierte Termine (docstatus 2).
        Sie sind unsichtbar, aber ein Loeschen laesst sie als Waisen stehen
        und die Fremdschluessel-Pruefung antwortet mit 417 und rohem SQL-Text
        (R-P2-5, klein 1).
      * `DienstplanVorlage.standard_kalender`
      * `Dienstplan.kalender`
      * `Gruppe.kalender`

    Die Antwort nennt die Zahl, damit die Oberflaeche sagen kann, was im Weg
    steht — statt eines technischen Fremdschluessel-Textes.
    """
    _require_kalender_verwalten(str(name or "").strip())

    doc = get_doc("Kalender", str(name or "").strip())
    if doc is None:
        raise ValidationError("Kalender nicht gefunden.")

    # ALLE Termine, auch stornierte: ein Loeschen scheiterte sonst an der FK.
    termine = get_all(
        "Element", filters={"element_calendar": doc.name}, fields=["name"],
    ) or []
    if termine:
        raise ValidationError(
            f"Dieser Kalender enthält noch {len(termine)} Termine (auch "
            "stornierte zählen). Bitte zuerst die Termine verschieben oder "
            "endgültig löschen."
        )

    verweise = _kalender_verweise(doc.name)
    if verweise:
        raise ValidationError(
            f"Dieser Kalender wird noch verwendet ({', '.join(verweise)}). "
            "Bitte zuerst dort einen anderen Kalender wählen."
        )

    if not int(bestaetigt or 0):
        raise ValidationError("Zum Löschen bitte bestätigen.")

    _child_delete(ROLLE_TABELLE, doc.name, LESERECHT_FELD)
    _child_delete(ROLLE_TABELLE, doc.name, SCHREIBRECHT_FELD)
    _child_delete(MODERATOR_TABELLE, doc.name, MODERATOR_FELD)
    _delete_doc("Kalender", doc.name)
    from diakronos_app.rechte import verwaltung as rv

    rv.entferne_objekt("kalender", doc.name)
    return {"success": True, "name": doc.name}


# Doctype -> Feld, das auf `kalender.name` zeigt, + deutsche Bezeichnung.
_KALENDER_VERWEISE: tuple[tuple[str, str, str], ...] = (
    ("DienstplanVorlage", "standard_kalender", "Standardkalender einer Dienstplan-Vorlage"),
    ("Dienstplan", "kalender", "Dienstplan"),
    ("Gruppe", "kalender", "Gruppe"),
)


def _kalender_verweise(kalender: str) -> list[str]:
    """Alle Stellen ausser `Element`, die auf diesen Kalender zeigen (Friendly-Text).

    N12b (R-N12, klein): Die Karte fragte, ob ein REGISTRIERUNGSLINK als
    Kalender-Verweis zaehlt. Er tut es nicht — und muss es auch nicht:
    `Registrierungslink.element` zeigt auf einen TERMIN, nicht auf einen
    Kalender. Ein Link kann deshalb nur dann im Weg stehen, wenn ein Termin im
    Weg steht, und den faengt die Pruefung in `delete_kalender` bereits ab
    (`Element.element_calendar`, samt stornierter Termine). Waere hier ein
    eigener Zweig, wuerde er nie greifen; er waere toter Code.

    `ElementAenderung.element_calendar` (offener Aenderungsvorschlag) ist
    ebenfalls kein eigener Verweis: der Vorschlag haengt an einem `element`,
    und dieses Element haelt den Kalender bereits.
    """
    treffer: list[str] = []
    for doctype, feld, label in _KALENDER_VERWEISE:
        try:
            zeilen = get_all(doctype, filters={feld: kalender}, fields=["name"]) or []
        except Exception:  # noqa: BLE001 — fehlende Tabelle ist kein Verweis
            continue
        if zeilen:
            treffer.append(f"{label}: {len(zeilen)}")
    return treffer
