"""Portierung von `diakronos.caldav.server` (Altcode, Frappe) — 393 LOC.

VORLAGE (READ-ONLY): `referenz/diakronos-frappe/diakronos/caldav/server.py`

Unterstuetzte Methoden (1:1 wie im Original):

    OPTIONS   /dav/                        -> DAV-Kopfzeilen
    PROPFIND  /dav/                        -> Principal-Discovery
    PROPFIND  /dav/{user}/                 -> Calendar-Home (Kalender-Liste)
    PROPFIND  /dav/{user}/{cal}/           -> Kalender-Collection (Event-Liste)
    REPORT    /dav/{user}/{cal}/           -> calendar-query / calendar-multiget
    GET       /dav/{user}/{cal}/{uid}.ics  -> Einzelnes Event
    /.well-known/caldav                    -> 301 auf /dav/

Berechtigung: Nutzer sieht nur Kalender, fuer die er Lese- oder Schreibrecht hat.

Frappe-Aufrufe des Originals -> Compat-Schicht:

    frappe.request.path                -> Request-Pfad (Starlette)
    frappe.request                       -> Request-Parameter (siehe unten)
    frappe.request.data                -> `await request.body()`
    frappe.request.headers.get(...)    -> `request.headers.get(...)`
    werkzeug.wrappers.Response(...)    -> starlette.responses.Response(...)
    werkzeug.exceptions.HTTPException  -> direkter Response-Rueckgabewert
    frappe.get_roles(user)             -> permissions.get_roles(user)
    frappe.get_all("Kalender", ...)    -> query.get_all(...)
    frappe.get_doc("Kalender", name)   -> query.get_doc(...)
    frappe.get_all("Element", ...)     -> query.get_all(...)
    frappe.get_doc("Element", name)    -> query.get_doc(...)
    frappe.db.exists("Element", uid)   -> query.get_all(..., pluck="name")
    frappe.DoesNotExistError           -> exceptions.DoesNotExistError
    frappe.log_error(...)              -> _shared.log_error(...)
    `_get_user_calendars`              -> portiertes Kronos-Modul
                                          `get_accessible_calendars()`
                                          (KEIN Nachbau der Rechtelogik)

ABWEICHUNG (bewusst, begruendet im Punkt 1 unten):

1. `_get_user_calendars` baut die Rechtelogik NICHT nach. Das Original hat dort
   eine eigene (rollenbasierte) Fassung, die die SPA-Rechtepruefung aus
   `kronos.api.permissions` dupliziert. Der Port ruft stattdessen das bereits
   portierte Modul auf — die Karte verlangt das ausdruecklich („Nutze
   frappe_compat.permissions (z.B. get_accessible_calendars) — nichts
   nachbauen"). Feldnamen der Antwort sind identisch (`name`, `title`, `color`).
2. Der `before_request`-Hook entfaellt; die Routen werden explizit registriert
   (`register_dav_routes`). Grund: FastAPI/Starlette kennt den Hook nicht, und
   `PROPFIND`/`REPORT` sind keine Standardmethoden — sie brauchen eigene
   `Route`-Eintraege, sonst antwortet der Router 405.
"""

from __future__ import annotations

import re
from urllib.parse import quote, unquote
from xml.sax.saxutils import escape as _xml_escape

from starlette.responses import Response
from starlette.routing import Route

from diakronos_app.frappe_compat.api_helpers import log_error as _log_error
from diakronos_app.api.kronos.permissions import get_accessible_calendars
from diakronos_app.caldav.auth import get_authenticated_user, unauthorized_response
from diakronos_app.frappe_compat.query import get_all, get_doc

# Original-Modulpfad (Dokumentation; NICHT ueber `/api/method/*` erreichbar —
# CalDAV ist ein eigener HTTP-Baum, kein SPA-Endpunkt. Die Registry von
# `frappe_compat` ist daran unbeteiligt, `register_dav_routes` haengt die Routen
# direkt an die ASGI-Anwendung. Grund fuer das Fehlen von `@whitelist`:
# ein CalDAV-Client schickt OPTIONS/PROPFIND/REPORT — das kann der
# `/api/method`-Router gar nicht bedienen.)
FRAPPE_MODULE = "diakronos.caldav.server"

_DAV = 'DAV:'
_CAL = 'urn:ietf:params:xml:ns:caldav'
_XML_HDR = '<?xml version="1.0" encoding="UTF-8"?>'


# ─────────────────────────────────────────────────────────────────────────────
# Antwort-Helfer
# ─────────────────────────────────────────────────────────────────────────────
#
# Das Original wirft `HTTPException(response=resp)` (Werkzeug), Frappe faengt
# das ab und gibt `resp` direkt zurueck. Hier IST der Handler bereits der
# Endpunkt — die Response wird einfach zurueckgegeben. Status, Body und
# Kopfzeilen sind identisch.


def _response(body='', status=200, headers=None, content_type=None):
    """`werkzeug.wrappers.Response` -> `starlette.responses.Response`."""
    kwargs = {}
    if content_type:
        kwargs['media_type'] = content_type
    return Response(body, status_code=status, headers=headers or {}, **kwargs)


def _xml(body):
    """Antwortform des Originals: 207 Multi-Status mit XML-Prolog."""
    return Response(
        _XML_HDR + '\n' + body,
        status_code=207,
        media_type='text/xml; charset=utf-8',
    )


def _options():
    return _response('', status=200, headers={
        'Allow': 'OPTIONS, PROPFIND, REPORT, GET',
        'DAV':   '1, 2, calendar-access',
        'Content-Length': '0',
    })


def _method_not_allowed():
    return _response('Method Not Allowed', status=405)


# ─────────────────────────────────────────────────────────────────────────────
# XML-Sicherheit
# ─────────────────────────────────────────────────────────────────────────────
#
# OP-HANDY-2: Das Original setzte Werte roh in die XML-Vorlagen. Ein Kalender
# "Musik & Chor" ergab `<D:href>/dav/x/Musik & Chor/</D:href>` -> rohes "&",
# damit ungueltiges XML. DAVx⁵, iOS-Kalender und Thunderbird parsen strikt und
# verwerfen die GANZE Antwort ("not well-formed (invalid token)"). Zwei Regeln:
#
#   * Werte, die in einen PFAD gehoeren (href), werden prozentkodiert (siehe
#     `_HREF_SAFE` unten). Der Client dekodiert beim Aufloesen; Starlette
#     dekodiert den eingehenden Pfad bereits, der Weg hin und zurueck bleibt
#     also symmetrisch.
#   * Werte in TEXTKNOTEN (displayname, calendar-data, etag) werden XML-escaped.
#   * Werte in KOPFZEILEN (Content-Disposition-Dateiname) sind kein XML: dort
#     zaehlt, dass kein `"`/Steuerzeichen die Kopfzeile sprengt.


# Zeichen, die in einem Pfadsegment zulaessig sind UND in einem XML-Textknoten
# nicht stoeren. Bewusst NICHT enthalten: `&`, `<`, `>`, `"`, `'`(bleibt),
# Leerzeichen, `/` — genau die Zeichen, an denen die Antwort vorher zerbrach.
# `@` bleibt erhalten, damit die hrefs der Bestandsnutzer (E-Mail-Konten) sich
# nicht unnoetig aendern. `quote(..., safe="")` waere strenger, kodierte aber
# auch `@` und `:` und braeche damit die bestehenden Zusagen des Baums.
_HREF_SAFE = "@:+$,;=!*'()-._~"

# XML 1.0 verbietet diese Zeichen KOMPLETT (`Char ::= #x9 | #xA | #xD |
# [#x20-#xD7FF] | ...`), auch als Entitaet. `saxutils.escape` laesst sie
# unangetastet — ein Titel mit Vertikal-Tab (`\x0b`, typisch beim Einfuegen aus
# Word/PDF) oder einem Nullbyte machte damit den GANZEN REPORT unparsebar
# ("not well-formed"). Erlaubt bleiben nur Tabulator, Zeilenumbruch und
# Wagenruecklauf.
_XML_VERBOTEN = re.compile(
    "["
    "\x00-\x08"
    "\x0b\x0c"
    "\x0e-\x1f"
    "\x7f"          # DEL: in XML 1.0 formal erlaubt, in Textknoten aber Muell
    "\u0085\u2028\u2029"  # C1-Grenzen: in XML 1.0 nicht erlaubt (P1-8 K-1)
    "\ud800-\udfff"  # alleinstehende Surrogate: XML-verboten UND nicht UTF-8-faehig
    "\ufffe\uffff"  # Unicode non-characters
    "]"
)


def _href(teil):
    """Pfadsegment fuer ein `<D:href>` prozentkodieren (`/` und Sonderzeichen)."""
    return quote(str(teil), safe=_HREF_SAFE)


def _text(wert):
    """Textknoten XML-sicher machen (`&`, `<`, `>`; Anfuehrungszeichen bleiben).

    Vor dem Escapen werden die in XML 1.0 verbotenen Steuerzeichen entfernt —
    sie sind nicht darstellbar und wuerden das ganze Dokument unparsebar
    machen (Review P1-6, W1). P1-8 (K-1) ergaenzt die C1-Grenzen
    U+0085/U+2028/U+2029 und alleinstehende Surrogate: ein solches Zeichen in
    Titel oder Kalendername machte die Antwort ungueltig (Surrogate ergeben
    sogar einen 500 statt eines XML-Fehlers beim Client).
    """
    if wert is None:
        return ""
    return _xml_escape(_XML_VERBOTEN.sub("", str(wert)))


def _kopfzeilen_wert(wert):
    """Wert fuer eine HTTP-Kopfzeile entschaerfen (NICHT XML-escapen).

    Review P1-6, W2: Der `ETag`-Header lief durch `_text` und trug damit bei
    einem Namen mit `&` das literale `&amp;` — waehrend `PROPFIND` nach dem
    XML-Parsen `&` liefert. Beide ETags desselben Termins stimmten nicht
    ueberein (Cache/If-Match). Kopfzeilen sind kein XML: hier zaehlt nur, dass
    kein `"`/Steuerzeichen die Kopfzeile sprengt und der Wert Latin-1-tauglich
    bleibt (sonst 500 aus Starlette).
    """
    text = _XML_VERBOTEN.sub("", str(wert if wert is not None else ""))
    return text.replace('"', "_").replace("\\", "_").encode(
        "latin-1", "replace"
    ).decode("latin-1")


# ─────────────────────────────────────────────────────────────────────────────
# Berechtigungen
# ─────────────────────────────────────────────────────────────────────────────


def _get_user_calendars(user):
    """
    Gibt Liste der Kalender zurueck, auf die der User Lese- oder Schreibrecht hat.

    Original: eigene rollenbasierte Fassung (Duplikat der Rechtepruefung aus
    `permissions.py`). Portierung: Aufruf des bereits portierten Kronos-Moduls
    `get_accessible_calendars()` — EINE Umsetzung der Rechtelogik statt zweier.
    Die Ausgabeform wird auf die drei im CalDAV-Server benutzten Felder
    reduziert; `get_accessible_calendars()` liefert sie zusaetzlich (`write`,
    `is_moderator`, `selbstverwaltet`), das stoert hier nicht.

    Der `try/except` des Originals bleibt: ein Fehler in der Rechtepruefung
    fuehrt zu `[]` (kein Leak), nicht zu einer 500.
    """
    try:
        return [
            {
                'name':  c['name'],
                'title': c.get('title') or c['name'],
                'color': c.get('color') or '#4f7cff',
            }
            for c in (get_accessible_calendars() or [])
        ]
    except Exception as e:  # noqa: BLE001 — Original faengt hier alles und gibt [] zurueck
        _log_error(str(e), 'CalDAV get_user_calendars')
        return []


def _check_access(user, cal_name):
    """Gibt das Kalender-Dict zurueck, wenn der User Zugriff hat, sonst None."""
    return next((c for c in _get_user_calendars(user) if c['name'] == cal_name), None)


def _get_events(cal_name, start=None, end=None, uids=None):
    """Holt Element-Dokumente eines Kalenders (nur Festgelegt), optional nach Zeitraum gefiltert.

    ABWEICHUNG (Performance/Stabilitaet, Ergebnis identisch): Das Original
    laedt jedes Element mit einem EIGENEN `frappe.get_doc`. In Frappe teilt das
    eine Request-Session, hier oeffnet `get_doc` pro Aufruf eine neue
    SQLAlchemy-Session, die erst beim GC geschlossen wird (siehe
    `frappe_compat.query.get_doc` / `doc.Document.__del__`). Bei einem Kalender
    mit vielen Terminen ist damit der Verbindungspool (size 5 + overflow 10)
    erschoepft, bevor der erste Termin serialisiert ist -> TimeoutError/500.

    Der Port laedt die Dokumente deshalb ueber EINE gemeinsame Session und
    schliesst sie geschlossen nach dem Aufbau der Liste. Rueckgabe und Reihenfolge
    sind unveraendert (Liste von `Document`-Wrappern).
    """
    filters = {'element_calendar': cal_name, 'status': 'Festgelegt'}
    if start:
        filters['element_end']   = ['>=', start]
    if end:
        filters['element_start'] = ['<=', end]

    if uids is not None:
        if not uids:
            return []
        filters['name'] = ['in', uids]
    names = get_all('Element', filters=filters, pluck='name')

    from diakronos_app.db import SessionLocal

    sess = SessionLocal()
    docs = []
    try:
        for n in names:
            docs.append(get_doc('Element', n, session=sess))
    finally:
        sess.close()

    return docs


# ─────────────────────────────────────────────────────────────────────────────
# PROPFIND-Handler
# ─────────────────────────────────────────────────────────────────────────────


def _propfind_root(user):
    """PROPFIND /dav/ -> Principal-Discovery."""
    u = _href(user)
    body = f'''<D:multistatus xmlns:D="{_DAV}" xmlns:C="{_CAL}">
  <D:response>
    <D:href>/dav/</D:href>
    <D:propstat>
      <D:prop>
        <D:resourcetype><D:collection/></D:resourcetype>
        <D:current-user-principal><D:href>/dav/{u}/</D:href></D:current-user-principal>
        <C:calendar-home-set><D:href>/dav/{u}/</D:href></C:calendar-home-set>
        <C:calendar-user-address-set>
          <D:href>mailto:{_text(user)}</D:href>
          <D:href>/dav/{u}/</D:href>
        </C:calendar-user-address-set>
      </D:prop>
      <D:status>HTTP/1.1 200 OK</D:status>
    </D:propstat>
  </D:response>
</D:multistatus>'''
    return _xml(body)


def _propfind_home(user):
    """PROPFIND /dav/{user}/ -> Kalender-Liste des Users."""
    calendars = _get_user_calendars(user)
    u = _href(user)

    entries = ''
    for cal in calendars:
        c = _href(cal["name"])
        entries += f'''  <D:response>
    <D:href>/dav/{u}/{c}/</D:href>
    <D:propstat>
      <D:prop>
        <D:resourcetype><D:collection/><C:calendar/></D:resourcetype>
        <D:displayname>{_text(cal["title"])}</D:displayname>
        <C:supported-calendar-component-set>
          <C:comp name="VEVENT"/>
        </C:supported-calendar-component-set>
        <x:calendar-color xmlns:x="http://apple.com/ns/ical/">{_text(cal["color"])}</x:calendar-color>
      </D:prop>
      <D:status>HTTP/1.1 200 OK</D:status>
    </D:propstat>
  </D:response>\n'''

    body = f'''<D:multistatus xmlns:D="{_DAV}" xmlns:C="{_CAL}">
  <D:response>
    <D:href>/dav/{u}/</D:href>
    <D:propstat>
      <D:prop>
        <D:resourcetype><D:collection/></D:resourcetype>
        <C:calendar-home-set><D:href>/dav/{u}/</D:href></C:calendar-home-set>
      </D:prop>
      <D:status>HTTP/1.1 200 OK</D:status>
    </D:propstat>
  </D:response>
{entries}</D:multistatus>'''
    return _xml(body)


def _propfind_calendar(user, cal_name, request):
    """PROPFIND /dav/{user}/{cal}/ -> Collection-Info + Event-Liste (Depth:1)."""
    cal = _check_access(user, cal_name)
    if not cal:
        return _response('Not Found', status=404)

    depth = request.headers.get('Depth', '0')
    u = _href(user)
    c = _href(cal_name)

    body = f'''<D:multistatus xmlns:D="{_DAV}" xmlns:C="{_CAL}">
  <D:response>
    <D:href>/dav/{u}/{c}/</D:href>
    <D:propstat>
      <D:prop>
        <D:resourcetype><D:collection/><C:calendar/></D:resourcetype>
        <D:displayname>{_text(cal["title"])}</D:displayname>
        <C:supported-calendar-component-set>
          <C:comp name="VEVENT"/>
        </C:supported-calendar-component-set>
      </D:prop>
      <D:status>HTTP/1.1 200 OK</D:status>
    </D:propstat>
  </D:response>\n'''

    if depth == '1':
        for el in _get_events(cal_name):
            etag = str(el.modified or el.creation)
            body += f'''  <D:response>
    <D:href>/dav/{u}/{c}/{_href(el.name)}.ics</D:href>
    <D:propstat>
      <D:prop>
        <D:resourcetype/>
        <D:getcontenttype>text/calendar;charset=utf-8</D:getcontenttype>
        <D:getetag>"{_text(el.name)}-{_text(etag)}"</D:getetag>
      </D:prop>
      <D:status>HTTP/1.1 200 OK</D:status>
    </D:propstat>
  </D:response>\n'''

    body += '</D:multistatus>'
    return _xml(body)


# ─────────────────────────────────────────────────────────────────────────────
# REPORT-Handler (calendar-query + calendar-multiget)
# ─────────────────────────────────────────────────────────────────────────────


def _report_calendar(user, cal_name, request, body_bytes):
    """REPORT /dav/{user}/{cal}/ -> Events mit iCal-Daten."""
    cal = _check_access(user, cal_name)
    if not cal:
        return _response('Not Found', status=404)

    # Original: `request.data`. Starlette liest den Body asynchron; der Handler
    # uebergibt ihn deshalb als Parameter (gleicher Inhalt, gleiche Semantik).
    xml_body = body_bytes or b''  # `None or b''` -> b'', wie `request.data or b''`

    # calendar-multiget: konkrete UIDs angefragt
    if b'calendar-multiget' in xml_body:
        roh = re.findall(r'/dav/[^/]+/[^/]+/([^<"]+)\.ics', xml_body.decode('utf-8', 'ignore'))
        # OP-HANDY-2: die hrefs kommen prozentkodiert zurueck (so gibt sie der
        # Server aus). Fuer den Datenbankvergleich wieder dekodieren, sonst
        # trifft ein Termin mit "&" im Namen nie.
        uids = [unquote(u) for u in roh]
        # UIDs sind kein Sichtbarkeitsnachweis: exakt dieselbe Auswahl wie
        # calendar-query/PROPFIND, einschliesslich Kalender und Festgelegt.
        events = _get_events(cal_name, uids=uids)
    else:
        # calendar-query: Zeitraum-Filter
        start, end = _parse_time_range(xml_body)
        events = _get_events(cal_name, start, end)

    from diakronos_app.caldav.ical import element_to_ical

    u = _href(user)
    c = _href(cal_name)

    body = f'<D:multistatus xmlns:D="{_DAV}" xmlns:C="{_CAL}">\n'
    for el in events:
        ical = element_to_ical(el)
        etag = str(el.modified or el.creation)
        body += f'''  <D:response>
    <D:href>/dav/{u}/{c}/{_href(el.name)}.ics</D:href>
    <D:propstat>
      <D:prop>
        <D:getcontenttype>text/calendar;charset=utf-8</D:getcontenttype>
        <D:getetag>"{_text(el.name)}-{_text(etag)}"</D:getetag>
        <C:calendar-data>{_text(ical)}</C:calendar-data>
      </D:prop>
      <D:status>HTTP/1.1 200 OK</D:status>
    </D:propstat>
  </D:response>\n'''

    body += '</D:multistatus>'
    return _xml(body)


# ─────────────────────────────────────────────────────────────────────────────
# GET-Handler – einzelnes Event
# ─────────────────────────────────────────────────────────────────────────────


def _get_event(user, cal_name, uid):
    """GET /dav/{user}/{cal}/{uid}.ics -> iCal-Datei."""
    if not _check_access(user, cal_name):
        return _response('Forbidden', status=403)

    events = _get_events(cal_name, uids=[uid])
    if not events:
        return _response('Not Found', status=404)
    el = events[0]

    from diakronos_app.caldav.ical import element_to_ical
    etag = str(el.modified or el.creation)

    # OP-HANDY-2: `uid` kommt aus dem Pfad und darf weder die ETag-Anfuehrung
    # noch die Kopfzeilen sprengen. Fuer den Dateinamen deshalb kodieren,
    # Anfuehrungszeichen/Steuerzeichen vorher entfernen (Kopfzeilen sind kein
    # XML — `escape` hilft hier nicht).
    dateiname = quote(uid.replace('"', '_'), safe='')

    return Response(
        element_to_ical(el),
        status_code=200,
        media_type='text/calendar;charset=utf-8',
        headers={
            # P1-6 W2: NICHT `_text` — ein XML-Escape im Header ergaebe fuer
            # einen Namen mit `&` ein `&amp;` und damit einen anderen ETag als
            # in der PROPFIND-Antwort (nach dem XML-Parsen).
            'ETag':                f'"{_kopfzeilen_wert(el.name)}-{_kopfzeilen_wert(etag)}"',
            'Content-Disposition': f"attachment; filename=\"{dateiname}.ics\"",
        },
    )


# ─────────────────────────────────────────────────────────────────────────────
# Hilfsfunktion: Zeitraum aus REPORT-Body extrahieren
# ─────────────────────────────────────────────────────────────────────────────


def _parse_time_range(xml_bytes):
    """Liest start/end aus einem CalDAV calendar-query REPORT-Body.

    `time-range` traegt iCal-Zeitstempel: `20260901T000000Z` oder (ganztaegig)
    `20260901`. Beide Formen sind erlaubt; ein unparsbarer Wert fuehrt zu
    `None` (kein Filter), NICHT zu einem Fehler — genau wie im Original, das
    den Zeitraum nur als optionale Einschraenkung behandelt.
    """
    if not xml_bytes:
        return None, None
    try:
        text    = xml_bytes.decode('utf-8', errors='ignore')
        start_m = re.search(r'time-range[^>]+start="([^"]+)"', text)
        end_m   = re.search(r'time-range[^>]+end="([^"]+)"',   text)

        return (
            _parse_ical_dt(start_m.group(1)) if start_m else None,
            _parse_ical_dt(end_m.group(1))   if end_m   else None,
        )
    except Exception:
        return None, None


def _parse_ical_dt(raw):
    """`20260901T120000Z` / `20260901` -> `datetime`, sonst `None`."""
    from datetime import datetime

    s = (raw or '').strip().rstrip('Z')
    for fmt in ('%Y%m%dT%H%M%S', '%Y%m%d'):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Router — Ersatz fuer den `before_request`-Hook
# ─────────────────────────────────────────────────────────────────────────────


async def _dav_dispatch(request):
    """Einziger Einstiegspunkt fuer `/dav/*` (Ersatz fuer `intercept()`).

    Entspricht `intercept()` + `_route()` des Originals:

      1. `OPTIONS` beantworten — VOR der Auth. Ein Kalender-Client schickt
         OPTIONS als Vorabanfrage ohne Zugangsdaten; das Original kommt hier
         nur deshalb durch, weil Frappe `OPTIONS` gar nicht erst an den Hook
         gibt. Ohne diese Ausnahme waere die Faehigkeitsabfrage 401.
      2. Basic Auth (fail closed -> 401 mit `WWW-Authenticate`)
      3. Methode + Pfad auswerten
      4. URL-User muss dem angemeldeten User entsprechen (sonst 403)
      5. Antwort zurueckgeben

    WICHTIG: `get_accessible_calendars()` liest den Benutzer aus
    `frappe.session` (ContextVar). Der CalDAV-Login setzt ihn deshalb hier —
    sonst filtert die Rechtepruefung gegen `Administrator` und jeder Nutzer
    saehe entweder alles oder nichts.
    """
    path = request.url.path

    # OPTIONS ist eine Vorabanfrage und braucht keine Credentials.
    if request.method.upper() == 'OPTIONS':
        return _options()

    # Basic Auth
    user = get_authenticated_user(request)
    if not user:
        return unauthorized_response()

    # Frappe-Session an den CalDAV-Benutzer binden, damit die portierte
    # Rechtepruefung (`get_accessible_calendars` -> `session.user`) den
    # RICHTIGEN Nutzer sieht.
    from diakronos_app.frappe_compat.session import session
    session.user = user

    # Request routen
    return await _route(request, user, path)


async def _route(request, user, path):
    method = request.method.upper()

    # /dav  oder  /dav/
    rest  = path[4:].strip('/')          # alles nach /dav/
    parts = rest.split('/') if rest else []

    # /dav/
    if len(parts) == 0:
        if method == 'PROPFIND':
            return _propfind_root(user)
        return _method_not_allowed()

    # Sicherheitscheck: URL-User muss dem angemeldeten User entsprechen
    url_user = parts[0]
    if url_user.lower() != user.lower():
        return _response('Forbidden', status=403)

    # /dav/{user}/
    if len(parts) == 1:
        if method == 'PROPFIND':
            return _propfind_home(user)
        return _method_not_allowed()

    cal_name = parts[1]

    # /dav/{user}/{cal}/
    if len(parts) == 2:
        if method == 'PROPFIND':
            return _propfind_calendar(user, cal_name, request)
        if method == 'REPORT':
            # `request.data` des Originals == kompletter Body.
            return _report_calendar(user, cal_name, request, await request.body())
        return _method_not_allowed()

    # /dav/{user}/{cal}/{uid}.ics
    uid = parts[2].removesuffix('.ics')
    if method == 'GET':
        return _get_event(user, cal_name, uid)

    return _method_not_allowed()


async def _well_known_caldav(request):
    """`/.well-known/caldav` -> 301 auf `/dav/` (wie im Original)."""
    return _response('', status=301, headers={'Location': '/dav/'})


# Methoden, die der DAV-Baum bedient. `PROPFIND`/`REPORT`/`OPTIONS` sind keine
# Standardmethoden; und `PUT`/`DELETE`/`PROPPATCH`/`MKCALENDAR`/`POST` muessen
# mit dabei sein, damit Starlette die Anfrage an den Dispatcher durchlaesst —
# der antwortet darauf mit 405 (der Server ist READ-ONLY). Stuenden sie nicht in
# der Liste, wuerde Starlette selbst 405 liefern; das Verhalten waere gleich,
# die Quelle der Antwort aber nicht mehr die portierte Logik.
#
# `methods=None` ist KEIN "alle Methoden": Starlette ersetzt das still durch
# {GET, HEAD}. Genau daran sind die ersten 19 Testlaeufe gescheitert (405 fuer
# jeden PROPFIND/REPORT) — deshalb hier die explizite Liste.
_DAV_METHODS = [
    "OPTIONS", "PROPFIND", "REPORT", "GET", "HEAD",
    "PUT", "DELETE", "POST", "PROPPATCH", "MKCALENDAR",
]


def register_dav_routes(app) -> None:
    """Haengt `/dav/*` und `/.well-known/caldav` in die FastAPI-Anwendung.

    MUSS VOR `mount_spa(app)` aufgerufen werden: der SPA-Catch-all unter
    `/diakonos/...` wuerde sonst spaeter definierte Routen verdecken.

    Beide `/dav`-Routen laufen in EINEN Dispatcher (`_dav_dispatch`) — das ist
    1:1 das `intercept()` + `_route()` des Originals, nur ohne Frappe-Hook.
    """
    app.router.routes.append(
        Route("/dav", endpoint=_dav_dispatch, methods=_DAV_METHODS)
    )
    app.router.routes.append(
        Route("/dav/{rest:path}", endpoint=_dav_dispatch, methods=_DAV_METHODS)
    )
    # /.well-known/caldav -> 301 (nur lesend, keine DAV-Methoden noetig)
    app.router.routes.append(
        Route("/.well-known/caldav", endpoint=_well_known_caldav, methods=["GET", "HEAD"])
    )


__all__ = [
    "register_dav_routes",
]
