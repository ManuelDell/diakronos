"""UX3g — Such-Endpunkt fuer die Befehlspalette (Strg+K).

Ein Endpunkt, sieben Quellen:

    suche.global(q, limit)      GET, nur angemeldet

Trefferform (je Treffer, MEHR gibt es nicht):

    {"art": "<Quellenart>", "titel": "<Anzeigetext>", "ort": "<Brotkrumen-Text>",
     "ziel": "#/<route>"}

`art` ist eine der Konstanten aus `ARTEN` (person/gruppe/termin/lied/wiki/
beitrag/einstellung). Die SPA gruppiert danach in Abschnitte (Entwurf A5:
„Personen“, „Termine“ …) und zeigt `ort` rechts in der Zeile.

WARUM EIN EIGENER ENDPUNKT UND KEINE SIEBEN AUFRUFE
Die Palette fragt bei jedem Tastendruck; sieben Aufrufe je Zeichen waeren
sieben Rundenzeit en und sieben Rechtepruefungen. Hier laufen dieselben
Pruefungen wie in den Einzelseiten — aber einmal je Quelle.

RECHTE (die eine Regel: jede Quelle benutzt IHRE vorhandene Pruefung, keine
zweite Fassung in dieser Datei)

  Personen  `get_adressbuch`-Sichtbarkeit (B2): Admins alles, sonst
            alle Namen fuer Gemeindemitglieder (R-9), sonst nur das eigene Profil.
            Ausgetretene Namen kommen gekuerzt („Mirko A.“) — je Zeile nach
            `PersonenSicht` (personen_anzeige, ID-1-Regel).
  Gruppen   `status = 'Aktiv'`; `sichtbarkeit = 'Versteckt'` NIE,
            `'Intern'` nur fuer eigene Gruppen bzw. Admins (get_gruppen_page_data).
            Die Gruppenansicht der Palette ist damit eine Teilmenge von
            „Meine Gruppen“ (UX3g2/F4).
  Termine   `permissions.get_accessible_calendars()` — dieselbe Liste, die auch
            den Kalender oeffnet (OP-EVENT-R1). Je Kalender gilt die
            Statusregel aus `calendar_get`: Nicht-Moderatoren sehen nur
            `status = 'Festgelegt'`, Moderatoren alles AUSSER `'Abgelehnt'`
            (UX3g2/F1 — sonst stuenden Vorschlags- und abgelehnte Titel in
            der Palette eines jeden Lesers).
  Lieder    `lied.aktiv` (stillgelegte Lieder stehen nicht in der Auswahl).
  Wiki      nur angemeldet (wie `get_wiki_artikel_liste`).
  Beitraege `veroeffentlicht = 1` (wie `get_beitraege_liste`).
  Einstellungen
            nur Administratoren (`permissions.is_admin`) — jeder Abschnitt der
            Einstellungsseite prueft das serverseitig ebenso.

PERSOENLICHE DATEN
Die Namenssuche darf KEINE Adressbuch-Freigabe verraten: gesucht wird nur auf
Vor-/Nachname, das E-Mail-Glied der Suche fehlt deshalb grundsaetzlich (anders
als bei Admins in `get_adressbuch`). Ausgegeben werden nur Name und Route —
keine E-Mail, keine Telefonnummer, kein Geburtstag. Fuer ausgetretene und
geloeschte Personen gilt `personen_anzeige` (kuerzt den Namen) — dieselbe
Regel wie Liste/Adressbuch.

GRENZEN
  * `q` wird getrimmt; unter `MIN_ZEICHEN = 2` antwortet der Endpunkt leer
    (kein Fehler — die Palette tippt Zeichen fuer Zeichen).
  * `limit` gilt JE QUELLE (1..`MAX_LIMIT`), Vorgabe `STANDARD_LIMIT`.
  * `q` ueber `MAX_ZEICHEN` Zeichen wird abgeschnitten, nicht abgelehnt.
  * Ratenbegrenzung: `suche_bremse.pruefe()` (Redis-Fenster je Benutzer) —
    `SUCHE_MAX = 0` schaltet sie ausdruecklich ab.

Papierkorb: die App kennt keinen Papierkorb (`_delete_doc` loescht die Zeile);
`docstatus = 2` (storniert/geloescht) wird trotzdem auf jeder Quelle
ausgeschlossen, damit eine kuenftige Papierkorb-Spalte nicht still durchfaellt.
"""

from __future__ import annotations

# Original-Frappe-Pfad-Muster der SPA. Die Palette ruft
# `diakronos.diakonos.api.suche.global`; dieser Endpunkt ist NEU (kein
# Altcode-Original), deshalb fuehrt die Konstante den Pfad selbst ein.
FRAPPE_MODULE = "diakronos.diakonos.api.suche"

import logging
import unicodedata
from typing import Any

from sqlalchemy import text

from diakronos_app.frappe_compat import whitelist
from diakronos_app.frappe_compat import permissions
from diakronos_app.frappe_compat.exceptions import PermissionError as FrappePermissionError
from diakronos_app.frappe_compat.exceptions import RateLimitError
from diakronos_app.frappe_compat.exceptions import throw
from diakronos_app.frappe_compat.session import session

logger = logging.getLogger("diakronos_app.api.suche")

__all__ = ["ARTEN", "MAX_LIMIT", "MAX_ZEICHEN", "MIN_ZEICHEN", "STANDARD_LIMIT", "global_", "suche_global"]

#: Die Quellenarten in der Reihenfolge, in der die Palette sie anzeigt.
ARTEN = (
    "person",
    "gruppe",
    "termin",
    "lied",
    "wiki",
    "beitrag",
    "einstellung",
)

MIN_ZEICHEN = 2
MAX_ZEICHEN = 100
STANDARD_LIMIT = 5
MAX_LIMIT = 20

# Schrittspalten, in denen die Personensuche sucht. `email` fehlt ABSICHTLICH
# (Adressbuch-Feld, siehe Modul-Docstring). `suche` ist nie Nutzereingabe.
_PERSON_SPALTEN = ("vorname", "nachname")

# Einstellungs-Abschnitte: (Stichwort, Anzeigetext, Route). Die Liste ist die
# der Einstellungsseite; Tester-Eintraege (Dev-Modus) fehlen bewusst.
_EINSTELLUNGEN = (
    ("Gemeinde", "Gemeinde", "#/einstellungen/gemeinde"),
    ("Anmeldung Login", "Anmeldung (Login)", "#/einstellungen/anmeldung"),
    ("Rollen Rechte", "Rollen & Rechte", "#/einstellungen/rollen"),
    ("Registrierung", "Registrierung", "#/einstellungen/registrierung"),
    ("Datenschutz Texte", "Datenschutz-Texte", "#/einstellungen/datenschutz"),
    ("Datensicherung", "Datensicherung", "#/einstellungen/datensicherung"),
    ("Mailversand", "Mailversand", "#/einstellungen/mailversand"),
    ("Website", "Website-Baukasten", "#/einstellungen/website"),
)


# ── Hilfen ──────────────────────────────────────────────────────────────────


def _normalisiere(text_wert: Any) -> str:
    """Klein, getrimmt, Umlaute aufgeloest — die Regel aus `api.mitglieder`.

    Dieselbe Faltung wie `_suche_normalisieren` (BF1-J), bewusst hier
    gespiegelt statt importiert: dort haengt sie an Personen-SQL, hier am
    Python-Vergleich. Die Zusage ist identisch („weiss“ findet „Weiß“).
    """
    wert = unicodedata.normalize("NFC", str(text_wert or "")).strip().lower()
    for von, nach in (("ß", "ss"), ("ä", "ae"), ("ö", "oe"), ("ü", "ue")):
        wert = wert.replace(von, nach)
    return wert


def _trifft(begriff: str, *felder: Any) -> bool:
    """Enthaelt EINES der Felder den (bereits normalisierten) Begriff?"""
    return any(begriff in _normalisiere(f) for f in felder if f)


def _spalte(spalte: str) -> str:
    """SQL-Ausdruck einer Spalte klein- und umlautgefaltet (BF1-J-Regel).

    `spalte` ist ein fester Bezeichner aus DIESER Datei, nie Nutzereingabe.
    """
    ausdruck = spalte
    for von, nach in (("Ä", "Ae"), ("Ö", "Oe"), ("Ü", "Ue"), ("ß", "ss"),
                      ("ä", "ae"), ("ö", "oe"), ("ü", "ue")):
        ausdruck = f"REPLACE({ausdruck}, '{von}', '{nach}')"
    return f"LOWER({ausdruck})"


def _treffer(art: str, titel: Any, ort: Any, ziel: str) -> dict[str, str]:
    """Ein Treffer in der Vertragsform — nicht mehr und nicht weniger Felder."""
    return {
        "art": art,
        "titel": str(titel or ""),
        "ort": str(ort or ""),
        "ziel": ziel,
    }


def _gekuerztes_limit(limit: Any) -> int:
    try:
        wert = int(limit)
    except (TypeError, ValueError):
        return STANDARD_LIMIT
    if wert < 1:
        return STANDARD_LIMIT
    return min(wert, MAX_LIMIT)


def _like_wert(wort: str) -> str:
    """Suchmuster fuer `LIKE … ESCAPE '\\'` — Platzhalter der Eingabe entschaerfen.

    UX3g2 (F3): `%` und `_` in `q` sind fuer den Nutzer Text, keine Muster.
    Ohne Entschaerfung waere `q="__"` ein Zwei-Zeichen-Joker und traefe jeden
    Datensatz mit zwei Zeichen — die Palette wuerde mehr verraten, als der
    Nutzer gesucht hat. `\\` selbst entschaerft den Fluchtzeichen-Pfad.
    """
    entschaerft = wort.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{entschaerft}%"


def _begriff_sql(begriff: str, praefix: str, params: dict[str, Any], spalten) -> str:
    """AND-Glied: JEDES Wort muss in einer der Spalten vorkommen."""
    glieder = []
    for i, wort in enumerate(begriff.split()):
        key = f"{praefix}{i}"
        params[key] = _like_wert(wort)
        glieder.append(
            "(" + " OR ".join(f"{_spalte(s)} LIKE :{key} ESCAPE '\\'" for s in spalten) + ")"
        )
    return " AND ".join(glieder) if glieder else "1=1"


def _db():
    from diakronos_app.db import engine

    return engine


# ── Quellen ─────────────────────────────────────────────────────────────────


def _personen(begriff: str, limit: int, user: str) -> list[dict[str, str]]:
    """Personen nach Vor-/Nachname — Sichtbarkeit wie `get_adressbuch` (B2).

    UX3g2 (F2): Der Anzeigename kommt aus `personen_anzeige.anzeigename` —
    DIE eine Stelle fuer ausgetretene („Mirko A.“) und geloeschte
    („Gelöschte Person“) Personen (ID-1-Regel). Vorher stand hier der
    Klarname an jedem Nicht-Admin vorbei.
    """
    from diakronos_app.frappe_compat.personen_anzeige import (
        PersonenSicht,
        anzeigename,
        ist_geloescht,
    )

    params: dict[str, Any] = {}
    where = ["m.docstatus <> 2"]
    # R-9/R-11b (Manuel 11.11.): Vor- und Nachnamen ALLER Mitglieder sieht
    # jedes Gemeindemitglied — dieselbe Regel wie `get_adressbuch`. Wer kein
    # Gemeindemitglied ist (Gast, Konto ohne Mitglied-Datensatz), findet
    # niemanden; das eigene Profil bleibt findbar.
    from diakronos_app import rechte

    if not (permissions.ist_mitgliederverwaltung(user) or rechte.ist_gemeindemitglied(user)):
        where.append("1=0")
        eigene_id = _eigenes_mitglied(user)
        if eigene_id:
            params["own_mid"] = eigene_id
            where[-1] = "(1=0 OR m.name = :own_mid)"

    params["limit"] = limit
    sql = (
        "SELECT m.name, m.vorname, m.nachname, m.status, m.austritt_datum, "
        "m.austritt_grund, m.wohnort "
        "FROM mitglied m WHERE "
        + " AND ".join(where)
        + " AND "
        + _begriff_sql(begriff, "p", params, _PERSON_SPALTEN)
        + " ORDER BY m.nachname, m.vorname LIMIT :limit"
    )
    with _db().connect() as conn:
        zeilen = conn.execute(text(sql), params).mappings().all()

    treffer = []
    # EINE Sicht je Aufruf: wer alles sieht (Admin, eigenes Profil) und wer
    # gekuerzt bekommt, entscheidet `personen_anzeige` — nicht diese Datei.
    sicht = PersonenSicht.aus(permissions._get_current_user_mitglied())
    for zeile in zeilen:
        datensatz = dict(zeile)
        name = anzeigename(datensatz, sicht=sicht)
        geloescht = ist_geloescht(datensatz)
        ausgetreten = (
            _normalisiere(zeile["status"]) == "ausgetreten"
            or bool(zeile["austritt_datum"])
            or bool(zeile["austritt_grund"])
        )
        ort = "Person · Ausgetreten" if ausgetreten and not geloescht else "Person"
        treffer.append(_treffer("person", name, ort, f"#/mitglied/{zeile['name']}"))
    return treffer


def _eigenes_mitglied(user: str) -> str | None:
    """Kennung des eigenen Mitglieds (sonst None) — ueber die eine Regel."""
    from diakronos_app.frappe_compat.mitglied_sichtbarkeit import eigenes_mitglied_id

    return eigenes_mitglied_id()


def _gruppen(begriff: str, limit: int, user: str, eigene: set[str]) -> list[dict[str, str]]:
    """Aktive Gruppen; fremde „Versteckt“/„Intern“ nie, eigene immer.

    UX3g2 (F4): „Versteckt“ heisst in `get_gruppen_page_data` „nicht im
    Verzeichnis“, nicht „fuer Mitglieder unauffindbar“ — die Gruppenansicht
    zeigt die eigenen Gruppen IMMER („Meine Gruppen“ filtert nur auf
    `status = 'Aktiv'`, ohne Sichtbarkeitspruefung). Die Palette folgt dem:
    eigene und selbstverwaltete Gruppen sind findbar, fremde versteckte und
    fremde interne nicht.
    """
    is_admin = permissions.is_admin(user)
    params: dict[str, Any] = {"limit": limit}
    # UX2b2 (F3): geloeschte Gruppen (Papierkorb) sind nicht auffindbar.
    where = ["g.docstatus <> 2", "COALESCE(g.status, '') = 'Aktiv'",
             "g.geloescht_am IS NULL"]
    if not is_admin:
        eigene_liste = sorted(eigene)
        if eigene_liste:
            keys = []
            for i, name in enumerate(eigene_liste):
                key = f"grp_{i}"
                params[key] = name
                keys.append(f":{key}")
            eigene_sql = ", ".join(keys)
            # „Intern“ bleibt eigenen Gruppen vorbehalten …
            where.append(
                "(COALESCE(g.sichtbarkeit, '') <> 'Intern' OR g.name IN ("
                + eigene_sql + "))"
            )
            # … „Versteckt“ steht nicht im Verzeichnis, ist aber fuer das
            # eigene Mitglied auffindbar (F4).
            where.append(
                "(COALESCE(g.sichtbarkeit, '') <> 'Versteckt' OR g.name IN ("
                + eigene_sql + "))"
            )
        else:
            where.append("COALESCE(g.sichtbarkeit, '') <> 'Intern'")
            where.append("COALESCE(g.sichtbarkeit, '') <> 'Versteckt'")

    sql = (
        "SELECT g.name, g.gruppenname, g.sichtbarkeit, "
        "d.ministry AS dienstbereich_name "
        "FROM gruppe g LEFT JOIN dienstbereich d ON d.name = g.dienstbereich "
        "WHERE " + " AND ".join(where) + " AND "
        + _begriff_sql(begriff, "gr", params, ("g.gruppenname",))
        + " ORDER BY g.gruppenname LIMIT :limit"
    )
    with _db().connect() as conn:
        zeilen = conn.execute(text(sql), params).mappings().all()

    treffer = []
    for zeile in zeilen:
        teile = ["Gruppe"]
        if zeile["dienstbereich_name"]:
            teile.append(str(zeile["dienstbereich_name"]))
        if _normalisiere(zeile["sichtbarkeit"]) == "intern":
            teile.append("Intern")
        titel = zeile["gruppenname"] or zeile["name"]
        treffer.append(_treffer("gruppe", titel, " · ".join(teile), f"#/gruppe/{zeile['name']}"))
    return treffer


def _termine(begriff: str, limit: int) -> list[dict[str, str]]:
    """Termine aus Kalendern MIT Leserecht (`get_accessible_calendars`).

    UX3g2 (F1): Leserecht allein genuegt nicht — sonst stuenden die Titel
    von Vorschlaegen und abgelehnten Terminen in der Palette jedes Lesers.
    Es gilt dieselbe Statusregel wie in `api/kronos/calendar_get.py`
    (Bearbeitungsmodus): je Kalender mit `is_moderator` alles AUSSER
    „Abgelehnt“, sonst nur „Festgelegt“. Die Aufteilung laeuft in Python
    ueber `get_accessible_calendars()` (dort steht `is_moderator`), die
    Kalenderliste bleibt SQL-Parameter.
    """
    from diakronos_app.api.kronos.permissions import get_accessible_calendars

    mod_cals: list[str] = []
    lese_cals: list[str] = []
    for eintrag in get_accessible_calendars() or []:
        if not eintrag.get("name"):
            continue
        (mod_cals if eintrag.get("is_moderator") else lese_cals).append(eintrag["name"])
    if not mod_cals and not lese_cals:
        return []

    params: dict[str, Any] = {"limit": limit}

    def kalender_keys(namen: list[str], praefix: str) -> str:
        keys = []
        for i, name in enumerate(namen):
            key = f"{praefix}{i}"
            params[key] = name
            keys.append(f":{key}")
        return ", ".join(keys)

    status_glieder = []
    if mod_cals:
        status_glieder.append(
            "(e.element_calendar IN (" + kalender_keys(mod_cals, "modkal_") + ")"
            " AND COALESCE(e.status, '') <> 'Abgelehnt')"
        )
    if lese_cals:
        status_glieder.append(
            "(e.element_calendar IN (" + kalender_keys(lese_cals, "lesekal_") + ")"
            " AND COALESCE(e.status, '') = 'Festgelegt')"
        )

    sql = (
        "SELECT e.name, e.element_name, e.element_start, e.element_calendar, "
        "k.calendar_name "
        "FROM element e LEFT JOIN kalender k ON k.name = e.element_calendar "
        "WHERE e.docstatus <> 2 AND e.geloescht_am IS NULL AND ("
        + " OR ".join(status_glieder) + ") AND "
        + _begriff_sql(begriff, "t", params, ("e.element_name",))
        + " ORDER BY e.element_start DESC, e.element_name LIMIT :limit"
    )
    with _db().connect() as conn:
        zeilen = conn.execute(text(sql), params).mappings().all()

    treffer = []
    for zeile in zeilen:
        ort_teile = ["Termin"]
        if zeile["calendar_name"]:
            ort_teile.append(str(zeile["calendar_name"]))
        ort = " · ".join(ort_teile)
        titel = zeile["element_name"] or zeile["name"]
        treffer.append(_treffer("termin", titel, ort, f"#/kalender?termin={zeile['name']}"))
    return treffer


def _lieder(begriff: str, limit: int) -> list[dict[str, str]]:
    """Nur aktive Lieder — stillgelegte stehen auch nicht in der Auswahl."""
    params: dict[str, Any] = {"limit": limit}
    # UX3g2 (F3): Platzhalter der Eingabe entschaerfen (wie `_begriff_sql`).
    params["p0"] = _like_wert(begriff)
    sql = (
        "SELECT l.name, l.titel, l.alternativtitel, l.gesangbuch_nummer "
        "FROM lied l WHERE l.docstatus <> 2 AND l.geloescht_am IS NULL "
        "AND COALESCE(l.aktiv, FALSE) = TRUE "
        "AND (" + _spalte("l.titel") + " LIKE :p0 ESCAPE '\\' "
        "OR " + _spalte("COALESCE(l.alternativtitel, '')") + " LIKE :p0 ESCAPE '\\' "
        "OR " + _spalte("COALESCE(l.gesangbuch_nummer, '')") + " LIKE :p0 ESCAPE '\\') "
        "ORDER BY l.titel LIMIT :limit"
    )
    with _db().connect() as conn:
        zeilen = conn.execute(text(sql), params).mappings().all()

    treffer = []
    for zeile in zeilen:
        ort = "Lied"
        if zeile["gesangbuch_nummer"]:
            ort = f"Lied · Nr. {zeile['gesangbuch_nummer']}"
        treffer.append(_treffer("lied", zeile["titel"] or zeile["name"], ort, f"#/lieder/{zeile['name']}"))
    return treffer


def _wiki(begriff: str, limit: int) -> list[dict[str, str]]:
    """Wiki-Artikel (Titel, Kategorie, Tags) — nur angemeldet, wie die Seite."""
    params: dict[str, Any] = {"limit": limit}
    sql = (
        "SELECT w.name, w.titel, w.kategorie, w.tags FROM wiki_artikel w "
        "WHERE w.docstatus <> 2 AND w.geloescht_am IS NULL AND "
        + _begriff_sql(begriff, "w", params, ("w.titel", "w.kategorie", "w.tags"))
        + " ORDER BY w.modified DESC, w.titel LIMIT :limit"
    )
    try:
        with _db().connect() as conn:
            zeilen = conn.execute(text(sql), params).mappings().all()
    except Exception:  # noqa: BLE001 — Quelle darf die Palette nie anhalten
        logger.warning("suche: Wiki-Quelle nicht lesbar", exc_info=True)
        return []

    treffer = []
    for zeile in zeilen:
        ort = "Wiki"
        if zeile["kategorie"]:
            ort = f"Wiki · {str(zeile['kategorie']).capitalize()}"
        treffer.append(_treffer("wiki", zeile["titel"] or zeile["name"], ort, f"#/wiki/{zeile['name']}"))
    return treffer


def _beitraege(begriff: str, limit: int) -> list[dict[str, str]]:
    """Nur veroeffentlichte Beitraege — wie `get_beitraege_liste`."""
    params: dict[str, Any] = {"limit": limit}
    sql = (
        "SELECT b.name, b.titel, b.kategorie FROM beitrag b "
        "WHERE b.docstatus <> 2 AND b.geloescht_am IS NULL "
        "AND COALESCE(b.veroeffentlicht, FALSE) = TRUE AND "
        + _begriff_sql(begriff, "b", params, ("b.titel", "b.kategorie"))
        + " ORDER BY b.datum DESC, b.titel LIMIT :limit"
    )
    try:
        with _db().connect() as conn:
            zeilen = conn.execute(text(sql), params).mappings().all()
    except Exception:  # noqa: BLE001
        logger.warning("suche: Beitrags-Quelle nicht lesbar", exc_info=True)
        return []

    treffer = []
    for zeile in zeilen:
        ort = "Beitrag"
        if zeile["kategorie"]:
            ort = f"Beitrag · {str(zeile['kategorie']).capitalize()}"
        treffer.append(_treffer("beitrag", zeile["titel"] or zeile["name"], ort, f"#/beitraege?id={zeile['name']}"))
    return treffer


def _einstellungen(begriff: str, limit: int) -> list[dict[str, str]]:
    """Stichworte der Einstellungs-Abschnitte — nur fuer Administratoren."""
    treffer = []
    for stichworte, anzeige, ziel in _EINSTELLUNGEN:
        if _normalisiere(begriff) in _normalisiere(stichworte) or _normalisiere(begriff) in _normalisiere(anzeige):
            treffer.append(_treffer("einstellung", anzeige, "Einstellungen", ziel))
        if len(treffer) >= limit:
            break
    return treffer


# ── Endpunkt ────────────────────────────────────────────────────────────────


@whitelist(allow_guest=False, methods=["GET"])
def global_(q: str = "", limit: int = STANDARD_LIMIT) -> dict[str, Any]:
    """Treffer aus allen Quellen fuer die Befehlspalette. **ABNAHMESCHNITTSTELLE.**

    Rueckgabe::

        {"q": "<getrimmter Begriff>", "treffer": [{art, titel, ort, ziel}, …],
         "quellen": {art: <Anzahl>}}

    Die Palette entscheidet nur noch ueber die Anzeige, nicht ueber Rechte:
    was hier nicht steht, darf der Aufrufer nicht sehen.

    `limit` gilt JE QUELLE. Die Reihenfolge der Treffer ist die Reihenfolge von
    `ARTEN`; innerhalb einer Quelle sortiert die Quelle selbst (Personen nach
    Nachname, Termine nach Datum absteigend).
    """
    user = session.user
    if not user or user == "Guest":
        throw("Anmeldung erforderlich.", FrappePermissionError)

    begriff = unicodedata.normalize("NFC", str(q or "")).strip()
    grenze = _gekuerztes_limit(limit)

    if len(begriff) < MIN_ZEICHEN:
        return {"q": begriff, "treffer": [], "quellen": {}}

    begriff = begriff[:MAX_ZEICHEN]
    _bremse(user)

    normalisiert = _normalisiere(begriff)
    eigene = _eigene_gruppen(user)
    is_admin = permissions.is_admin(user)

    quellen: dict[str, list[dict[str, str]]] = {}
    # Jede Quelle einzeln abgesichert: ein Lesefehler in einer Quelle (fehlende
    # Tabelle in einer alten DB) darf die Palette nicht komplett ausfallen
    # lassen — die uebrigen Treffer bleiben sichtbar.
    for art, funktion in (
        ("person", lambda: _personen(normalisiert, grenze, user)),
        ("gruppe", lambda: _gruppen(normalisiert, grenze, user, eigene)),
        ("termin", lambda: _termine(normalisiert, grenze)),
        ("lied", lambda: _lieder(normalisiert, grenze)),
        ("wiki", lambda: _wiki(normalisiert, grenze)),
        ("beitrag", lambda: _beitraege(normalisiert, grenze)),
        ("einstellung", lambda: _einstellungen(normalisiert, grenze) if is_admin else []),
    ):
        try:
            quellen[art] = funktion()
        except FrappePermissionError:
            raise
        except Exception:  # noqa: BLE001
            logger.warning("suche: Quelle %s fehlgeschlagen", art, exc_info=True)
            quellen[art] = []

    treffer = [t for art in ARTEN for t in quellen.get(art, [])]
    return {
        "q": begriff,
        "treffer": treffer,
        "quellen": {art: len(quellen.get(art, [])) for art in ARTEN},
    }


# Der Name der SPA: `diakronos.diakonos.api.suche.global` ist in Python ein
# Schluesselwort — der Endpunkt heisst hier `global_` und wird unter dem
# Originalpfad `…suche.global` registriert (siehe `registriere_namen`).
def suche_global(q: str = "", limit: int = STANDARD_LIMIT) -> dict[str, Any]:
    """Alias fuer Aufrufer, die kein Schluesselwort als Namen wollen."""
    return global_(q=q, limit=limit)


def _eigene_gruppen(user: str) -> set[str]:
    """Gruppen, in denen der Aufrufer Mitglied oder HV/MV/GL ist (R-11d: der
    EINE Rechte-Kern statt der Alt-Tabelle „Gruppe Verantwortlicher“)."""
    from diakronos_app import rechte

    try:
        return rechte.eigene_gruppen(user)
    except Exception:  # noqa: BLE001 — fail closed: keine „Intern“-Gruppen
        logger.warning("suche: eigene Gruppen nicht ermittelbar", exc_info=True)
        return set()


def _bremse(user: str) -> None:
    """Ratenbegrenzung je Benutzer (Redis-Fenster). `0` = aus."""
    from diakronos_app.suche_bremse import bremse

    bremse.pruefe_oder_werfen(user)


def registriere_namen() -> None:
    """Traegt den Originalpfad `…suche.global` zusaetzlich ein.

    `@whitelist` registriert den blossen Funktionsnamen `global_`. Die SPA ruft
    aber `diakronos.diakonos.api.suche.global`; der Router probiert fuer jede
    Anfrage auch `suche.<name>` — dieses Alias macht daraus den Treffer.
    Idempotent.
    """
    from diakronos_app.frappe_compat.registry import register_with_frappe_module

    register_with_frappe_module(FRAPPE_MODULE, "global", global_)


registriere_namen()
