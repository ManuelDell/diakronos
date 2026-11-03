"""BS-1b — Datenzugriff der oeffentlichen Website-Ausgabe (ohne HTTP).

Dieses Modul beantwortet EINE Frage: welche Zeilen sind ueberhaupt
oeffentlich? Alles andere (HTTP, CORS, Bremse, Cache) steht im Endpunkt.

Freigabe-Filter (G1) — was hier entschieden wird
================================================
Ein Kalender ist oeffentlich, wenn ``website_freigabe`` gesetzt ist UND ein
``website_slug`` existiert (ohne Slug waere er nicht adressierbar; der
Freigabe-Endpunkt aus BS-1a legt ihn beim Freigeben an). Ein Termin ist
oeffentlich, wenn

  * sein Kalender freigegeben ist,
  * sein Status ``"Festgelegt"`` lautet, und
  * bei ``website_nur_oeffentliche_kategorien`` seine Eventkategorie
    ``oeffentlich`` traegt.

Statuswerte (per grep belegt, ``Element.status`` ist ein Frappe-Select mit
``Vorschlag\\nFestgelegt\\nKonflikt``; ``Abgelehnt`` und ``Bestätigt`` kommen
zusaetzlich im Bestand vor — siehe ``api/kronos/calendar_get.py:255``
(„Lesemodus: nur Festgelegt“), ``kanban_api`` (Vorschlag/Konflikt/Abgelehnt)
und ``ablaufplan_api``/``moderation`` (Abgelehnt/Bestätigt)). Fuer die
oeffentliche Ausgabe gilt deshalb GENAU EIN Wert als oeffentlich:
``"Festgelegt"``. ``"Bestätigt"`` ist eine Zusage im Anmeldeprozess, nicht
der Freigabe-Status des Termins — ein Entwurf (``Vorschlag``), ein
Konflikt-Termin und ein abgelehnter Termin bleiben draussen.

Eine Gruppe ist oeffentlich, wenn ``website_freigabe`` gesetzt ist und ein
Slug existiert; ``sichtbarkeit == "Versteckt"`` schliesst zusaetzlich aus
(dieselbe Regel wie ``api/gruppen.py:1492`` — eine versteckte Gruppe ist
auch in der Verwaltung unsichtbar, dann erst recht auf der Website).
Ein Beitrag ist oeffentlich, wenn ``veroeffentlicht`` UND ``auf_website``
gesetzt sind.

Wiederholungen
==============
Serien sind im Bestand EINZELZEILEN: ``create_series`` legt je Termin eine
``Element``-Zeile mit gemeinsamem ``series_id`` an (max. 100 Stueck,
``repeat_this_event=1``). Es gibt keine RRULE. Deshalb gibt L2 die einzelnen
Zeilen aus, wie sie gespeichert sind — kein Zusammenfassen, keine erfundene
Wiederholungsregel.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

from sqlalchemy import and_, or_, select

from diakronos_app.db import lesesitzung
from diakronos_app.models.diakonos import Beitrag, Gruppe, Registrierungslink
from diakronos_app.models.kronos import Element, Eventkategorie, Kalender, Ressource
from diakronos_app.website import freigaben as freigabe_regeln
from diakronos_app.website import oeffentlich_auswahl as auswahl
from diakronos_app.website import oeffentlich_inhalt as inhalt

__all__ = [
    "ANMELDUNG_SPALTEN",
    "BEITRAEGE_LIMIT_MAX",
    "BEITRAEGE_LIMIT_STANDARD",
    "GRUPPE_TERMINE_MAX",
    "ICAL_VERGANGEN_TAGE",
    "LIMIT_MAX",
    "LIMIT_STANDARD",
    "STATUS_OEFFENTLICH",
    "TAGE_MAX_BIS",
    "TAGE_STANDARD_BIS",
    "beitraege_oeffentlich",
    "freigegebene_gruppe",
    "freigegebene_kalender",
    "fristen",
    "gruppe_detail",
    "gruppen",
    "ical_termine",
    "kalender",
    "kalender_gespeist",
    "naechste_termine",
    "oeffentlicher_beitrag",
    "termine",
]

#: Der EINE oeffentliche Termin-Status (siehe Modulkopf).
STATUS_OEFFENTLICH = "Festgelegt"
#: Zusaetzlich ausgeschlossene Sichtbarkeit einer Gruppe (wie `api/gruppen`).
SICHTBARKEIT_VERSTECKT = "Versteckt"

#: Grenzen der Terminabfrage (Karte L2).
TAGE_STANDARD_BIS = 90
TAGE_MAX_BIS = 400
LIMIT_STANDARD = 50
LIMIT_MAX = 500
#: Grenzen der Beitraege (Karte L5: ``limit`` ohne Vorgabe, hier 10).
BEITRAEGE_LIMIT_STANDARD = 10
BEITRAEGE_LIMIT_MAX = 50
#: Grenzen der iCal-Ausgabe (L7): kuenftig + 30 Tage vergangen.
ICAL_VERGANGEN_TAGE = 30
#: Naechste Termine einer Gruppe (L4).
GRUPPE_TERMINE_MAX = 10


# ── Freigegebene Stammdaten ────────────────────────────────────────────────


def freigegebene_kalender(sess) -> list[dict]:
    """Alle freigegebenen Kalender, nach Anzeigename sortiert (L1)."""
    zeilen = sess.execute(
        select(Kalender).where(
            Kalender.website_freigabe.is_(True),
            Kalender.website_slug.is_not(None),
            Kalender.website_slug != "",
        )
    ).scalars().all()
    ergebnis = [
        {
            "name": z.name,
            "slug": z.website_slug,
            "titel": z.calendar_name,
            "farbe": z.calendar_color,
            "nur_oeffentliche_kategorien": bool(z.website_nur_oeffentliche_kategorien),
        }
        for z in zeilen
    ]
    ergebnis.sort(key=lambda k: (str(k["titel"] or "").lower(), str(k["slug"])))
    return ergebnis


def _kalender_index(sess) -> dict[str, dict]:
    """Freigegebene Kalender nach Slug."""
    return {k["slug"]: k for k in freigegebene_kalender(sess)}


def freigegebene_gruppe(sess, slug: str) -> dict | None:
    """Eine freigegebene Gruppe nach Slug (``None``, wenn nicht oeffentlich)."""
    kennung = str(slug or "").strip()
    if not kennung:
        return None
    zeile = sess.execute(
        select(Gruppe).where(
            Gruppe.website_slug == kennung,
            Gruppe.website_freigabe.is_(True),
        )
    ).scalars().first()
    if zeile is None:
        return None
    if str(zeile.sichtbarkeit or "") == SICHTBARKEIT_VERSTECKT:
        return None
    return _gruppe_zeile(sess, zeile)


def _gruppe_zeile(sess, zeile: Gruppe) -> dict:
    """Gruppen-Zeile plus Anzeigenamen des Gruppentyps (nur der Name)."""
    typname = ""
    if zeile.gruppentyp:
        typ = sess.get(_modell("Gruppentyp"), zeile.gruppentyp)
        typname = _attribut(typ, "typname") or str(zeile.gruppentyp)
    return {
        "name": zeile.name,
        "website_slug": zeile.website_slug or "",
        "gruppenname": zeile.gruppenname,
        "typname": typname,
        "beschreibung": zeile.beschreibung,
        "treffzeit": zeile.treffzeit,
        "treffpunkt": zeile.treffpunkt,
        "bild": zeile.bild,
        "sichtbarkeit": zeile.sichtbarkeit,
    }


def _modell(name: str):
    from diakronos_app.frappe_compat.registry_gen import model_for

    return model_for(name)


def _attribut(obj, name: str):
    return getattr(obj, name, None) if obj is not None else None


# ── Zeitfenster ────────────────────────────────────────────────────────────


def _heute() -> date:
    """Heute in der Zeitzone der Gemeinde (Community-Zeit, nicht UTC)."""
    from zoneinfo import ZoneInfo

    try:
        return datetime.now(tz=ZoneInfo(inhalt.ZEITZONE)).date()
    except Exception:  # noqa: BLE001 — ohne tzdata gilt UTC
        return datetime.utcnow().date()


def _als_datum(wert) -> date | None:
    """``"2026-11-01"``/``date``/``datetime`` -> ``date`` (sonst ``None``)."""
    if wert is None or wert == "":
        return None
    if isinstance(wert, datetime):
        return wert.date()
    if isinstance(wert, date):
        return wert
    text = str(wert).strip()[:10]
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        return None


def fristen(von=None, bis=None) -> tuple[date, date]:
    """Zeitfenster der Terminabfrage (Vorgabe heute .. +90 Tage, max. 400).

    Ein ``bis`` VOR ``von`` wird auf ``von`` gezogen, ein Fenster laenger als
    :data:`TAGE_MAX_BIS` auf die Grenze gekuerzt — nie ein Fehler: eine
    Website-Anfrage mit unsinnigem Fenster soll eine (leere) Liste bekommen,
    keine Fehlerseite.
    """
    start = _als_datum(von) or _heute()
    ende = _als_datum(bis)
    if ende is None:
        ende = start + timedelta(days=TAGE_STANDARD_BIS)
    if ende < start:
        ende = start
    if (ende - start).days > TAGE_MAX_BIS:
        ende = start + timedelta(days=TAGE_MAX_BIS)
    return start, ende


def _grenzen(start: date, ende: date) -> tuple[datetime, datetime]:
    """Datumsfenster als Zeitgrenzen (``bis`` ist einschliesslich)."""
    return (
        datetime.combine(start, time.min),
        datetime.combine(ende, time.max),
    )


# ── Termine ────────────────────────────────────────────────────────────────


def _termin_zeilen(
    sess,
    kalender_slugs: list[str],
    start: date,
    ende: date,
    *,
    kategorie: str | None = None,
    gruppe_slug: str | None = None,
    limit: int = LIMIT_STANDARD,
) -> list[dict]:
    """Oeffentliche Termin-Zeilen im Fenster (nach Beginn sortiert)."""
    index = _kalender_index(sess)
    gewaehlt = [s for s in kalender_slugs if s in index]
    if not gewaehlt:
        return []
    namen = [index[s]["name"] for s in gewaehlt]
    nur_oeffentliche = {
        index[s]["name"] for s in gewaehlt if index[s]["nur_oeffentliche_kategorien"]
    }
    von_dt, bis_dt = _grenzen(start, ende)

    bedingungen = [
        Element.element_calendar.in_(namen),
        Element.status == STATUS_OEFFENTLICH,
        # BS-1b2 (F7): geloeschte Termine (docstatus 2) NIE oeffentlich —
        # dieselbe Schranke wie in der Verwaltung, nur im SQL statt in Python.
        Element.docstatus != 2,
        Element.element_start.is_not(None),
        Element.element_start <= bis_dt,
        # Ein Termin, der im Fenster beginnt ODER hineinreicht (mehrtägig).
        or_(
            Element.element_end.is_(None),
            Element.element_end >= von_dt,
        ),
    ]
    if nur_oeffentliche:
        # Kalender mit Einschraenkung: nur Termine mit oeffentlicher Kategorie.
        oeffentliche_kategorien = select(Eventkategorie.name).where(
            Eventkategorie.oeffentlich.is_(True)
        )
        bedingungen.append(
            or_(
                Element.element_calendar.not_in(sorted(nur_oeffentliche)),
                and_(
                    Element.element_calendar.in_(sorted(nur_oeffentliche)),
                    Element.element_category.in_(oeffentliche_kategorien),
                ),
            )
        )

    if kategorie:
        kennung = str(kategorie).strip()
        treffer = sess.execute(
            select(Eventkategorie).where(
                or_(
                    Eventkategorie.name == kennung,
                    Eventkategorie.event_category_name == kennung,
                )
            )
        ).scalars().first()
        if treffer is None or not bool(treffer.oeffentlich):
            return []
        bedingungen.append(Element.element_category == treffer.name)

    if gruppe_slug:
        gruppe = freigegebene_gruppe(sess, gruppe_slug)
        if gruppe is None:
            return []
        bedingungen.append(Element.gruppe == gruppe["name"])

    zeilen = sess.execute(
        select(Element)
        .where(and_(*bedingungen))
        .order_by(Element.element_start, Element.name)
        .limit(max(1, int(limit)))
    ).scalars().all()
    return [_termin_aus_zeile(zeile) for zeile in zeilen]


def _ressource_namen(sess, kennungen) -> dict[str, str]:
    """Ressourcen-Kennung -> Anzeigename (nur der Name, nie die Kennung)."""
    namen = [k for k in {str(x or "") for x in kennungen} if k]
    if not namen:
        return {}
    zeilen = sess.execute(
        select(Ressource).where(Ressource.name.in_(namen))
    ).scalars().all()
    return {
        z.name: (str(z.ressource_name or "").strip() or z.name)
        for z in zeilen
    }


def _kategorie_namen(sess, kennungen) -> dict[str, str]:
    """Eventkategorie-Kennung -> Anzeigename."""
    namen = [k for k in {str(x or "") for x in kennungen} if k]
    if not namen:
        return {}
    zeilen = sess.execute(
        select(Eventkategorie).where(Eventkategorie.name.in_(namen))
    ).scalars().all()
    return {
        z.name: (str(z.event_category_name or "").strip() or z.name) for z in zeilen
    }


def _termin_aus_zeile(zeile: Element) -> dict:
    """Rohe Termin-Zeile (spaeter mit Anzeigenamen angereichert)."""
    return {
        "name": zeile.name,
        "element_name": zeile.element_name,
        "element_start": zeile.element_start,
        "element_end": zeile.element_end,
        "all_day": bool(zeile.all_day),
        "description": zeile.description,
        "element_color": zeile.element_color,
        "element_category": zeile.element_category,
        "ressource": zeile.ressource,
        "kalender": zeile.element_calendar,
        "gruppe": zeile.gruppe,
        "anmeldung_aktiv": bool(zeile.anmeldung_aktiv),
        "registrierungslink": zeile.registrierungslink,
        # BS-1b2 (F4): Stand der Zeile — wird zum iCal-DTSTAMP. Bleibt in
        # der internen Zeile (die Positivliste fuer die JSON-Ausgabe ist
        # `oeffentlich_auswahl`), geht also NICHT nach aussen.
        "modified": zeile.modified,
    }


def _anreichern(sess, zeilen: list[dict]) -> list[dict]:
    """Anzeigenamen fuer Ressource/Kategorie/Gruppe einsetzen (kein HTTP)."""
    ressourcen = _ressource_namen(sess, [z.get("ressource") for z in zeilen])
    kategorien = _kategorie_namen(sess, [z.get("element_category") for z in zeilen])
    for zeile in zeilen:
        zeile["ressource_name"] = ressourcen.get(str(zeile.get("ressource") or ""), "")
        zeile["kategorie_name"] = kategorien.get(
            str(zeile.get("element_category") or ""), ""
        )
    return zeilen


def _oeffentliche_gruppen(sess, kennungen) -> dict[str, dict]:
    """``{kennung: {slug, name}}`` fuer MEHRERE Termine in EINER Abfrage (L2).

    Dieselbe Positivliste wie :func:`_oeffentliche_gruppe` (nur freigegeben,
    Slug vorhanden, nicht versteckt); Kennungen ohne Treffer fehlen im
    Ergebnis — der Aufrufer setzt dann ``None``.
    """
    gewuenscht = sorted({str(k or "").strip() for k in kennungen} - {""})
    if not gewuenscht:
        return {}
    zeilen = sess.execute(
        select(Gruppe).where(
            Gruppe.name.in_(gewuenscht),
            Gruppe.website_freigabe.is_(True),
            Gruppe.website_slug.is_not(None),
            Gruppe.website_slug != "",
        )
    ).scalars().all()
    ergebnis: dict[str, dict] = {}
    for zeile in zeilen:
        if str(zeile.sichtbarkeit or "") == SICHTBARKEIT_VERSTECKT:
            continue
        ergebnis[str(zeile.name)] = {
            "slug": zeile.website_slug,
            "name": inhalt.klartext(zeile.gruppenname) or str(zeile.website_slug),
        }
    return ergebnis


def _oeffentliche_gruppe(sess, kennung) -> dict | None:
    """``{slug, name}`` einer freigegebenen Gruppe ODER ``None``.

    Die Zuordnung Termin -> Gruppe laeuft ueber ``element.gruppe`` (interne
    Kennung). Ausgegeben wird nur der Slug und der Anzeigename — und nur,
    wenn die Gruppe freigegeben ist (G1: „gruppe nur wenn Gruppe freigegeben“).
    """
    kennung = str(kennung or "").strip()
    if not kennung:
        return None
    zeile = sess.execute(
        select(Gruppe).where(
            Gruppe.name == kennung,
            Gruppe.website_freigabe.is_(True),
            Gruppe.website_slug.is_not(None),
            Gruppe.website_slug != "",
        )
    ).scalars().first()
    if zeile is None or str(zeile.sichtbarkeit or "") == SICHTBARKEIT_VERSTECKT:
        return None
    return {
        "slug": zeile.website_slug,
        "name": inhalt.klartext(zeile.gruppenname) or str(zeile.website_slug),
    }


def _anmeldung_links(sess, kennungen) -> dict[str, str]:
    """Anmeldeadressen fuer MEHRERE Termine in EINER Abfrage (L2, N+1-Fix).

    Rueckgabe: ``registrierungslink``-Kennung -> fertige Adresse (``""``,
    wenn der Link nicht taugt). Die Regeln sind DIESELBEN wie in
    :func:`_anmeldung_url` — nur ohne eine Abfrage je Zeile.

    BS-1b2 (F2): ``termine()`` fragte vorher je Zeile zwei Mal (Gruppe UND
    Registrierungslink), und ``link_anzeige`` oeffnete je Link eine EIGENE
    Sitzung fuer die Gemeinde-Einstellung. Jetzt eine ``IN (…)``-Abfrage fuer
    alle Links; die Zahl der Abfragen haengt damit nicht mehr an der
    Zeilenzahl.
    """
    gewuenscht = sorted({str(k or "").strip() for k in kennungen} - {""})
    if not gewuenscht:
        return {}
    zeilen = sess.execute(
        select(Registrierungslink).where(Registrierungslink.name.in_(gewuenscht))
    ).scalars().all()
    heute = _heute()
    # EINMAL je Aufruf, nicht je Link (BS-1b2/F2): `link_anzeige` liest die
    # Gemeinde-Adresse; ohne Vorgabe fragt jede Zeile die Einstellung neu ab.
    basis = _oeffentliche_basis(sess)
    ergebnis: dict[str, str] = {}
    for link in zeilen:
        ergebnis[str(link.name)] = _link_adresse(link, heute, sess, basis)
    return ergebnis


def _oeffentliche_basis(sess) -> str:
    """Gepflegte oeffentliche Adresse der Gemeinde (``""`` wenn leer)."""
    try:
        from diakronos_app.anmeldung.registrierungslink import oeffentliche_basis

        return str(oeffentliche_basis(sess) or "")
    except Exception:  # noqa: BLE001 — eine fehlende Einstellung ist kein Fehler
        return ""


def _link_adresse(link, heute: date, sess=None, basis: str | None = None) -> str:
    """Fertige Anmeldeadresse EINES Registrierungslink — oder ``""``.

    BS-1b2 (F1): Der Link-Typ MUSS die Gast-Anmeldung sein
    (``anmeldung.registrierungslink.TYPG_GAST``, derselbe Vergleich wie
    ``api/registrierung.submit_gast``). Ein Mitglieds-Registrierungslink ist
    eine Einladung in die Mitgliederverwaltung und gehoert NICHT auf die
    oeffentliche Website.

    ``sess``/``basis`` (BS-1b2/F2): offene Lesesitzung und die bereits
    gelesene oeffentliche Adresse — sonst fragt ``link_anzeige`` beides je
    Link neu ab.
    """
    if link is None or not bool(link.aktiv):
        return ""
    try:
        from diakronos_app.anmeldung.registrierungslink import TYPG_GAST

        if str(link.typ or "") != str(TYPG_GAST):
            return ""
    except Exception:  # noqa: BLE001 — unklarer Typ ist kein oeffentlicher Link
        return ""
    token = str(link.slug or "").strip()
    if not token:
        return ""
    ab = _als_datum(link.gueltig_ab)
    bis = _als_datum(link.gueltig_bis)
    if ab is not None and heute < ab:
        return ""
    if bis is not None and heute > bis:
        return ""
    try:
        from diakronos_app.anmeldung.registrierungslink import link_anzeige

        if basis is None:
            basis = _oeffentliche_basis(sess)
        return str(link_anzeige(link.typ, token, basis=basis) or "")
    except Exception:  # noqa: BLE001 — ein kaputter Link ist kein 500
        return ""


def _anmeldung_url(sess, zeile: dict) -> str:
    """Praefixbewusste Adresse der bestehenden Gast-Anmeldung (oder ``""``).

    Regeln (Karte L2: „nur wenn ``anmeldung_aktiv`` und Registrierungslink
    gueltig/oeffentlich“):

      * ``anmeldung_aktiv`` muss gesetzt sein,
      * der Registrierungslink muss existieren, ``aktiv`` sein und ein Token
        tragen (ohne Slug ist er nie nutzbar — SEC-3),
      * er muss vom Typ Gast-Anmeldung sein (BS-1b2/F1 — ein
        Mitglieds-Registrierungslink ist NIE oeffentlich),
      * er muss heute im Gueltigkeitsfenster liegen (``gueltig_ab`` /
        ``gueltig_bis``; ``api/registrierung`` rechnet genauso),
      * die Adresse kommt aus ``anmeldung.registrierungslink.link_anzeige``
        — DIESELBE Funktion wie die Verwaltung und der Teilen-Link, damit
        Praefix (``DIAKRONOS_BASE_PATH``) und oeffentliche Adresse der
        Gemeinde nicht auseinanderlaufen.

    Ohne gepflegte oeffentliche Adresse ist das Ergebnis ein RELATIVER Pfad
    (``/diakonos/gast?token=…``); die Website setzt den eigenen Ursprung
    davor. Das ist so gewollt und im Vertrag dokumentiert.

    Fuer MEHRERE Zeilen nimmt :func:`_anmeldung_links` die Arbeit in einer
    Abfrage — diese Funktion ist der Einzelweg (und der Bezug der Regeln).
    """
    if not zeile.get("anmeldung_aktiv"):
        return ""
    kennung = str(zeile.get("registrierungslink") or "").strip()
    if not kennung:
        return ""
    link = sess.execute(
        select(Registrierungslink).where(Registrierungslink.name == kennung)
    ).scalars().first()
    return _link_adresse(link, _heute(), sess)


def termine(
    sess,
    *,
    kalender: list[str] | None = None,
    von=None,
    bis=None,
    kategorie: str | None = None,
    gruppe: str | None = None,
    limit: int = LIMIT_STANDARD,
) -> list[dict]:
    """Oeffentliche Termine (L2), fertig serialisiert.

    Ohne ``kalender``-Angabe gelten ALLE freigegebenen Kalender. Ein
    angegebener, aber nicht freigegebener Slug wird still verworfen — die
    Antwort verraet damit nicht, dass es den Kalender gibt. Bleibt nichts
    uebrig, ist die Liste LEER (kein Rueckfall auf „alle“).
    """
    start, ende = fristen(von, bis)
    anzahl = max(1, min(int(limit or LIMIT_STANDARD), LIMIT_MAX))
    gewuenscht = [s for s in (kalender or []) if str(s or "").strip()]
    if not gewuenscht:
        gewuenscht = [k["slug"] for k in freigegebene_kalender(sess)]
    zeilen = _termin_zeilen(
        sess,
        [str(s).strip() for s in gewuenscht],
        start,
        ende,
        kategorie=kategorie,
        gruppe_slug=gruppe,
        limit=anzahl,
    )
    _anreichern(sess, zeilen)
    # BS-1b2 (F2): Gruppen und Anmeldelinks JE EINE Abfrage, nicht je Zeile.
    gruppen = _oeffentliche_gruppen(
        sess, [z.get("gruppe") for z in zeilen]
    )
    links = _anmeldung_links(
        sess,
        [
            z.get("registrierungslink")
            for z in zeilen
            if z.get("anmeldung_aktiv")
        ],
    )
    ergebnis: list[dict] = []
    for zeile in zeilen:
        kennung = str(zeile.get("registrierungslink") or "").strip()
        ergebnis.append(
            auswahl.termin_oeffentlich(
                zeile,
                gruppe=gruppen.get(str(zeile.get("gruppe") or "").strip()),
                anmeldung_url=(links.get(kennung) or "")
                if zeile.get("anmeldung_aktiv")
                else "",
            )
        )
    return ergebnis


def naechste_termine(
    sess,
    *,
    kategorie: str | None = None,
    kalender: str | None = None,
    gruppe: str | None = None,
    limit: int = 1,
) -> list[dict]:
    """Die naechsten Termine ab heute (L3/L4) — Liste, hoechstens ``limit``."""
    return termine(
        sess,
        kalender=[kalender] if kalender else None,
        von=_heute(),
        bis=_heute() + timedelta(days=TAGE_STANDARD_BIS),
        kategorie=kategorie,
        gruppe=gruppe,
        limit=max(1, min(int(limit or 1), GRUPPE_TERMINE_MAX)),
    )


def kalender_gespeist(sess, slug: str) -> dict | None:
    """Ein freigegebener Kalender nach Slug (``None`` = 404)."""
    return _kalender_index(sess).get(str(slug or "").strip())


def kalender(sess) -> list[dict]:
    """Oeffentliche Kalender-Liste (L1)."""
    return [
        auswahl.kalender_oeffentlich(k["slug"], k["titel"], k["farbe"])
        for k in freigegebene_kalender(sess)
    ]


def ical_termine(sess, kalender_slug: str) -> dict | None:
    """Zeilen fuer den iCal-Feed eines Kalenders (``None`` = nicht freigegeben).

    Gleiche Filter wie L2 (Status, Kategorie-Einschraenkung), Zeitfenster:
    30 Tage vergangen bis 400 Tage kuenftig (harte Obergrenze der Terminabfrage).
    """
    info = kalender_gespeist(sess, kalender_slug)
    if info is None:
        return None
    start = _heute() - timedelta(days=ICAL_VERGANGEN_TAGE)
    ende = _heute() + timedelta(days=TAGE_MAX_BIS)
    zeilen = _termin_zeilen(
        sess,
        [info["slug"]],
        start,
        ende,
        limit=LIMIT_MAX,
    )
    _anreichern(sess, zeilen)
    return {"kalender": info, "termine": zeilen}


# ── Gruppen ────────────────────────────────────────────────────────────────


def gruppen(sess, *, typ: str | None = None) -> list[dict]:
    """Alle freigegebenen Gruppen (L4), nach Anzeigename sortiert."""
    zeilen = sess.execute(
        select(Gruppe).where(
            Gruppe.website_freigabe.is_(True),
            Gruppe.website_slug.is_not(None),
            Gruppe.website_slug != "",
        )
    ).scalars().all()
    ergebnis = []
    for zeile in zeilen:
        if str(zeile.sichtbarkeit or "") == SICHTBARKEIT_VERSTECKT:
            continue
        daten = _gruppe_zeile(sess, zeile)
        if typ and str(daten["typname"]).strip().lower() != str(typ).strip().lower() \
                and str(zeile.gruppentyp or "").strip().lower() != str(typ).strip().lower():
            continue
        ergebnis.append(daten)
    ergebnis.sort(key=lambda g: (str(g["gruppenname"] or "").lower(), str(g["website_slug"])))
    return ergebnis


def gruppe_detail(sess, slug: str) -> dict | None:
    """Eine freigegebene Gruppe samt naechsten Terminen (L4)."""
    daten = freigegebene_gruppe(sess, slug)
    if daten is None:
        return None
    daten["naechste_termine"] = naechste_termine(
        sess, gruppe=daten["website_slug"], limit=GRUPPE_TERMINE_MAX
    )
    return daten


# ── Beitraege ──────────────────────────────────────────────────────────────


def beitraege_oeffentlich(
    sess, *, limit: int = BEITRAEGE_LIMIT_STANDARD, kategorie: str | None = None
) -> list[dict]:
    """Veroeffentlichte Beitraege, die auf der Website stehen (L5)."""
    anzahl = max(1, min(int(limit or BEITRAEGE_LIMIT_STANDARD), BEITRAEGE_LIMIT_MAX))
    bedingungen = [
        Beitrag.veroeffentlicht.is_(True),
        Beitrag.auf_website.is_(True),
    ]
    if kategorie:
        bedingungen.append(Beitrag.kategorie == str(kategorie).strip())
    zeilen = sess.execute(
        select(Beitrag)
        .where(and_(*bedingungen))
        .order_by(Beitrag.datum.desc().nullslast(), Beitrag.name.desc())
        .limit(anzahl)
    ).scalars().all()
    return [_beitrag_zeile(z) for z in zeilen]


def oeffentlicher_beitrag(sess, kennung: str) -> dict | None:
    """Ein Beitrag nach oeffentlicher Kennung (``None``, wenn nicht oeffentlich).

    Sucht ueber :func:`oeffentlich_auswahl.oeffentliche_kennung` — die
    interne Kennung selbst ist nicht von aussen waehlbar.
    """
    gesucht = str(kennung or "").strip()
    if not gesucht:
        return None
    zeilen = sess.execute(
        select(Beitrag).where(
            Beitrag.veroeffentlicht.is_(True),
            Beitrag.auf_website.is_(True),
        )
    ).scalars().all()
    for zeile in zeilen:
        if auswahl.oeffentliche_kennung("beitrag", zeile.name) == gesucht:
            return _beitrag_zeile(zeile)
    return None


def _beitrag_zeile(zeile: Beitrag) -> dict:
    return {
        "name": zeile.name,
        "titel": zeile.titel,
        "datum": zeile.datum,
        "kategorie": zeile.kategorie,
        "auszug": zeile.auszug,
        "inhalt": zeile.inhalt,
        "bild": zeile.bild,
    }


def beitraege(sess) -> list[dict]:
    """Kurzform fuer Aufrufer, die nur die Listensicht brauchen."""
    return beitraege_oeffentlich(sess)


def mit_lesesitzung(fn, *args, **kwargs):
    """Fuehrt ``fn(sess, *args)`` in einer Lesesitzung aus (schliesst nur eigene)."""
    with lesesitzung() as sess:
        return fn(sess, *args, **kwargs)


def als_beitrag(daten: dict, *, bild_url: str = "") -> dict:
    """Rohzeile -> oeffentliche Beitrags-Ausgabe (Feld-Positivliste)."""
    return auswahl.beitrag_oeffentlich(daten, bild_url=bild_url)


def als_gruppe(daten: dict, *, bild_url: str = "") -> dict:
    """Rohzeile -> oeffentliche Gruppen-Ausgabe (Feld-Positivliste)."""
    return auswahl.gruppe_oeffentlich(daten, bild_url=bild_url)


__all__ += [
    "als_beitrag",
    "als_gruppe",
    "kalender_gespeist",
    "ical_termine",
    "mit_lesesitzung",
]
