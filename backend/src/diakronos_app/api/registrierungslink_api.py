"""Portierung von `diakronos.diakonos.api.registrierungslink_api` (Altcode, Frappe).

VORLAGE (READ-ONLY): `referenz/diakronos-frappe/diakronos/diakonos/api/registrierungslink_api.py`

Portierte Endpunkte (Original-dotted paths ueber `FRAPPE_MODULE`):

    create_link    update_link    delete_link    toggle_link

**NUR FUER MITGLIEDERADMINISTRATOREN.** Alle vier tragen im Original
`@frappe.whitelist(allow_guest=False)` und rufen `_require_admin()` auf.
Die Compat-Schicht hat denselben Guard bereits 1:1 portiert
(`permissions.require_admin`, Quelle `api/admin_hub.py:_require_admin`) —
inklusive der Sonderbehandlung von `Guest` mit derselben Meldung und der
Rollen `System Manager` / `Mitgliederadministrator`. Deshalb wird hier
`require_admin()` benutzt statt eines zweiten, driftenden Duplikats.

Frappe-Aufruf -> Compat-Schicht:

    frappe.session.user == "Guest"  -> permissions.require_admin()
    frappe.get_roles()              -> permissions.require_admin()
    frappe.get_doc({...}).insert()  -> _create(...)
    frappe.get_doc(dt, name)        -> get_doc(...) -> Document
    doc.save(ignore_permissions=1)  -> _update_doc(...)
    frappe.db.exists(dt, filters)   -> _exists(...)
    frappe.get_all(dt, pluck=...)   -> get_all(..., pluck=...)
    frappe.delete_doc(...)          -> _delete_doc(...)
    frappe.db.commit()              -> no-op (die Helfer committen je Operation)
    frappe.throw(msg, exc)          -> throw(msg, exc)
    nowdate()/getdate()             -> _today()/date.fromisoformat

Slug/Anzeige: `slug` und `link_anzeige` sind echte Spalten
(`Spaltenabzug der Betriebs-DB`: `tabRegistrierungslink` hat `bezeichnung`,
`typ`, `slug`, `link_anzeige`, `gueltig_bis`, `max_anmeldungen`,
`anmeldeformular`, `element`, `aktiv`, `anmeldungen_count`). Im
Frappe-Original vergab `autoname` einen Zufalls-Slug; der Port schrieb die
beiden Felder nicht und erzeugte damit unbrauchbare Links (UXD-R2). Jetzt
vergibt `create_link` den Token selbst und bildet die Anzeige als
`/diakonos/<seite>?token=<slug>` (UXD-R3).
"""

from __future__ import annotations

# Original-Frappe-Pfad der SPA (Registry-Schluessel, s. registry.py).
FRAPPE_MODULE = "diakronos.diakonos.api.registrierungslink_api"

import datetime as _dt
from typing import Any

from diakronos_app.frappe_compat.exceptions import ValidationError
from diakronos_app.frappe_compat.permissions import require_admin
from diakronos_app.frappe_compat.query import get_all
from diakronos_app.frappe_compat.registry import whitelist

from diakronos_app.frappe_compat.api_helpers import (
    _create,
    _delete_doc,
    _today,
    _update_doc,
    get_doc,
    throw,
)

# Felder, die `update_link` uebernehmen darf (Original: `allowed`).
_ALLOWED_UPDATE_FIELDS = frozenset(
    {
        "bezeichnung",
        "gueltig_bis",
        "max_anmeldungen",
        "anmeldeformular",
        "element",
        "aktiv",
    }
)

# Felder, die `create_link` in die Antwort legt (Original: Rueckgabe-dict).
_LINK_RESPONSE_FIELDS = (
    "name",
    "bezeichnung",
    "typ",
    "aktiv",
    "gueltig_bis",
    "max_anmeldungen",
    "anmeldungen_count",
    "anmeldeformular",
    "element",
)


def _exists(doctype: str, filters: dict[str, Any]) -> bool:
    """`frappe.db.exists(doctype, {..})` — gibt es mindestens eine Zeile?"""
    return bool(
        get_all(doctype, filters=filters, fields=["name"], limit_page_length=1)
    )


def _neuer_token() -> str:
    """Zufallstoken fuer einen neuen Registrierungslink (UXD-R2).

    Das Frappe-Original vergab `autoname` einen Zufalls-Slug; der Port schrieb
    weder `slug` noch `link_anzeige`, deshalb war der Link nie benutzbar
    (validate_token sucht `{"slug": token}` und fand nichts).
    Befund 7 (P0-4b): der Token entsteht jetzt im gemeinsamen Modul.
    """
    from diakronos_app.anmeldung.registrierungslink import neuer_token

    return neuer_token()


def _link_seite(typ: Any) -> str:
    """SPA-Seite fuer einen Linktyp (`registrierung` oder `gast`).

    Befund 7 (P0-4b): die Ableitung liegt seit dieser Karte in EINEM Modul
    (`anmeldung/registrierungslink.py`) — vorher gab es drei Kopien.
    """
    from diakronos_app.anmeldung.registrierungslink import link_seite

    return link_seite(typ)


def _link_anzeige(typ: Any, slug: str) -> str:
    """Vollstaendige Adresse des Links fuer Anzeige/Kopieren (UXD-R3).

    Altdaten trugen hier einen relativen Pfad `/registrierung?token=…` aus der
    Frappe-Zeit; im Standalone gibt es die Seite nur unter `/diakonos/…`.
    Befund 7: Ableitung zentral in `anmeldung/registrierungslink.py`.
    """
    from diakronos_app.anmeldung.registrierungslink import link_anzeige

    return link_anzeige(typ, slug)


def _mit_vorgaben(gueltig_bis, max_anmeldungen, *, ohne_ablauf=False, unbegrenzt=False):
    """Setzt leere Linkfelder auf die gepflegten Vorgaben (M-1).

    Bleiben Laufzeit/Platzzahl beim Anlegen leer, gelten die Werte aus
    „Einstellungen → Registrierung“. Wurde ein Wert mitgegeben, bleibt er
    unveraendert — die Verwaltung kann am einzelnen Link immer abweichen.

    M-1 (R-N9b): Ein LEERES Feld ist nicht dasselbe wie „ausdruecklich ohne
    Ablauf“. Deshalb kann die Oberflaeche die Vorgabe ausdruecklich uebersteuern:
      * ``ohne_ablauf=True``  -> der Link bekommt KEIN Ablaufdatum (unbefristet),
        auch wenn die Gemeinde-Vorgabe eine Laufzeit hat.
      * ``unbegrenzt=True``   -> die Platzzahl bleibt 0 (unbegrenzt), auch wenn
        die Gemeinde-Vorgabe eine Hoechstzahl hat.
    Ohne diese ausdruecklichen Angaben gilt weiter: leer = Vorgabe.

    Nie eine Exception: eine fehlende Einstellung darf das Anlegen eines
    Links nicht verhindern (dann bleibt der Wert wie uebergeben).
    """
    vorgabe_gebunden = not ohne_ablauf and not str(gueltig_bis or "").strip()
    vorgabe_plätze = not unbegrenzt and not int(max_anmeldungen or 0)
    if not (vorgabe_gebunden or vorgabe_plätze):
        return gueltig_bis, max_anmeldungen

    try:
        from diakronos_app.db import SessionLocal
        from diakronos_app.models.gemeinde import (
            GEMEINDE_EINSTELLUNGEN_NAME,
            STANDARD_MAX_ANMELDUNGEN,
            STANDARD_LAUFZEIT_TAGE,
            GemeindeEinstellungen,
        )

        with SessionLocal() as sess:
            zeile = sess.get(GemeindeEinstellungen, GEMEINDE_EINSTELLUNGEN_NAME)
            tage = int(zeile.link_laufzeit_tage) if zeile else STANDARD_LAUFZEIT_TAGE
            maximum = int(zeile.link_max_anmeldungen) if zeile else STANDARD_MAX_ANMELDUNGEN
    except Exception:  # noqa: BLE001 — Vorgaben sind optional
        return gueltig_bis, max_anmeldungen

    if vorgabe_gebunden and tage > 0:
        gueltig_bis = (_dt.date.fromisoformat(_today()) + _dt.timedelta(days=tage)).isoformat()
    if vorgabe_plätze and maximum > 0:
        max_anmeldungen = maximum
    return gueltig_bis, max_anmeldungen



def _link_antwort(link: dict[str, Any]) -> dict[str, Any]:
    """Antwort-dict eines Registrierungslink (Original: Rueckgabe von create)."""
    gueltig = link.get("gueltig_bis")
    slug = link.get("slug") or ""
    return {
        "name": link.get("name"),
        "bezeichnung": link.get("bezeichnung"),
        "typ": link.get("typ"),
        "slug": slug,
        "aktiv": link.get("aktiv"),
        # UXD-R3: absolute Adresse inkl. `/diakonos/…`; Altdaten tragen hier
        # noch den relativen Frappe-Pfad, deshalb wird der Wert neu gebildet.
        "link_anzeige": _link_anzeige(link.get("typ"), slug) if slug else "",
        "gueltig_bis": str(gueltig) if gueltig else None,
        "max_anmeldungen": link.get("max_anmeldungen"),
        "anmeldungen_count": link.get("anmeldungen_count"),
        "anmeldeformular": link.get("anmeldeformular"),
        "element": link.get("element"),
    }


@whitelist(allow_guest=False)
def create_link(
    bezeichnung,
    typ,
    gueltig_bis="",
    max_anmeldungen=0,
    anmeldeformular_id="",
    element_id="",
    ohne_ablauf=False,
    unbegrenzt=False,
):
    """Erstellt einen neuen Registrierungslink (nur Admin).

    UXD-R2: `slug` (Zufallstoken), `link_anzeige` und `anmeldungen_count`
    werden mitgeschrieben. Ohne den Slug war der Link unbrauchbar —
    `validate_token` sucht `{"slug": token}` und jede neu angelegte Adresse
    blieb leer.

    M-1: bleiben `gueltig_bis`/`max_anmeldungen` leer, gelten die unter
    „Einstellungen → Registrierung“ gepflegten Vorgaben (Laufzeit in Tagen,
    Hoechstzahl). Die Oberflaeche darf weiter abweichen — sie uebersteuert die
    Vorgabe dann mit einem eingetragenen Wert. Ausdruecklich UNBEFRISTET bzw.
    UNBEGRENZT geht ueber `ohne_ablauf`/`unbegrenzt` (M-1, R-N9b): ein leeres
    Feld heisst Vorgabe, ein ausdrueckliches „ohne Ablauf“ heisst ohne Ablauf.
    """
    require_admin()

    gueltig_bis, max_anmeldungen = _mit_vorgaben(
        gueltig_bis, max_anmeldungen, ohne_ablauf=ohne_ablauf, unbegrenzt=unbegrenzt,
    )
    slug = _neuer_token()
    name = _create(
        "Registrierungslink",
        {
            "bezeichnung": bezeichnung,
            "typ": typ,
            "slug": slug,
            "link_anzeige": _link_anzeige(typ, slug),
            "anmeldungen_count": 0,
            "gueltig_bis": gueltig_bis or None,
            "max_anmeldungen": int(max_anmeldungen or 0),
            "anmeldeformular": anmeldeformular_id or None,
            "element": element_id or None,
            "aktiv": 1,
        },
    )

    doc = get_doc("Registrierungslink", name)
    felder = [*_LINK_RESPONSE_FIELDS, "slug", "link_anzeige"]
    return {"success": True, "link": _link_antwort({f: doc.get(f) for f in dict.fromkeys(felder)})}


@whitelist(allow_guest=False)
def update_link(link_id, **kwargs):
    """Aktualisiert einen Registrierungslink (nur Admin)."""
    require_admin()

    doc = get_doc("Registrierungslink", link_id)

    werte = {k: v for k, v in kwargs.items() if k in _ALLOWED_UPDATE_FIELDS}
    if werte:
        _update_doc("Registrierungslink", doc.name, werte)

    return {"success": True, "link_id": doc.name}


@whitelist(allow_guest=False)
def delete_link(link_id):
    """Loescht einen Link nur, wenn keine bestaetigten Anmeldungen existieren."""
    require_admin()

    # Bestaetigte Anmeldungen blockieren das Loeschen.
    if _exists("Anmeldung", {"registrierungslink": link_id, "status": "Bestätigt"}):
        throw(
            "Link kann nicht gelöscht werden: Es existieren bestätigte Anmeldungen.",
            ValidationError,
        )

    # Ausstehende Anmeldungen mitloeschen (Original: frappe.delete_doc je Zeile).
    for anm_id in get_all(
        "Anmeldung",
        filters={"registrierungslink": link_id},
        pluck="name",
    ):
        _delete_doc("Anmeldung", str(anm_id))

    _delete_doc("Registrierungslink", link_id)

    return {"success": True}


@whitelist(allow_guest=False)
def toggle_link(link_id):
    """Schaltet einen Link aktiv/inaktiv um (nur Admin)."""
    require_admin()

    doc = get_doc("Registrierungslink", link_id)
    neu = 0 if doc.aktiv else 1
    _update_doc("Registrierungslink", doc.name, {"aktiv": neu})

    return {"success": True, "aktiv": bool(neu)}


@whitelist(allow_guest=False)
def verlaengern_link(link_id, gueltig_bis="", max_anmeldungen=None):
    """Verlaengert einen abgelaufenen oder vollen Link (N3, nur Admin).

    Konzept Abschnitt 5: „Abgelaufen oder voll: Karte grau mit Schild
    ‚Abgelaufen' / ‚Voll' und Knopf ‚Verlängern'“. Ohne diesen Weg gaebe es
    keinen: `update_link` kennt zwar `gueltig_bis`, aber `max_anmeldungen`
    liesse sich nur erhoehen, wenn der Aufrufer den Sollwert kennt, und der
    Zustand der Karte bliebe in der Antwort unsichtbar.

    `gueltig_bis` leer = kein Ablaufdatum (offen). `max_anmeldungen` fehlt =
    unveraendert; 0 = unbegrenzt. Der Link wird dabei wieder eingeschaltet
    (`aktiv = 1`), weil sonst die Verlaengerung nichts bewirkt.

    Rueckgabe: `{"success": True, "link": <Zeile mit Zustand>}` — dieselbe
    Form wie die Linkliste (`_link_antwort` + Zustandsfelder), damit die Karte
    ohne Neuladen stimmt.

    Nacharbeit (R-N3-main-commits): die Eingaben werden geprueft, BEVOR sie an
    die Datenbank gehen. Sonst ergab `int("drei")` einen 500er und ein
    ungueltiges Datum einen rohen DB-Fehler in der Antwort (vgl. OP-ADMIN-9
    beim Geburtsdatum). Nur Administratoren erreichen den Endpunkt, saubere
    Meldungen sind trotzdem Pflicht.
    """
    require_admin()

    doc = get_doc("Registrierungslink", link_id)

    ablauf = str(gueltig_bis or "").strip()
    if ablauf:
        try:
            ablauf = _dt.date.fromisoformat(ablauf).isoformat()
        except ValueError:
            throw(
                f"Ungültiges Ablaufdatum „{gueltig_bis}“. Erwartet JJJJ-MM-TT.",
                ValidationError,
            )

    plaetze: int | None = None
    if max_anmeldungen is not None and max_anmeldungen != "":
        try:
            plaetze = int(max_anmeldungen)
        except (TypeError, ValueError):
            throw(
                f"Ungültige Platzzahl „{max_anmeldungen}“. Erwartet eine ganze Zahl.",
                ValidationError,
            )
        if plaetze < 0:
            throw(
                f"Ungültige Platzzahl „{plaetze}“. Sie darf nicht negativ sein.",
                ValidationError,
            )

    werte: dict[str, Any] = {"aktiv": 1, "gueltig_bis": ablauf or None}
    if plaetze is not None:
        werte["max_anmeldungen"] = plaetze

    _update_doc("Registrierungslink", doc.name, werte)

    frisch = get_doc("Registrierungslink", doc.name)
    felder = [*_LINK_RESPONSE_FIELDS, "slug", "link_anzeige", "creation"]
    link = _link_antwort({f: frisch.get(f) for f in dict.fromkeys(felder)})

    from diakronos_app.anmeldung.registrierungslink import zustand

    link.update(zustand(link, offene_anfragen=_offene_anfragen(doc.name)))
    return {"success": True, "link": link}


def _offene_anfragen(link_name: str) -> int:
    """Zahl der offenen Anfragen eines Links (fuer die Zustandskarte)."""
    from diakronos_app.anmeldung.registrierungslink import OFFENE_ANMELDESTATI

    return len(
        get_all(
            "Anmeldung",
            filters={
                "registrierungslink": link_name,
                "status": ["in", list(OFFENE_ANMELDESTATI)],
            },
            pluck="name",
        )
    )
