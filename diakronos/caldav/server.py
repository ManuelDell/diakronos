# diakronos/caldav/server.py – minimaler CalDAV-Server (read-only)
#
# Unterstützte Methoden:
#   OPTIONS   /dav/
#   PROPFIND  /dav/                        → Principal-Discovery
#   PROPFIND  /dav/{user}/                 → Calendar-Home (Kalender-Liste)
#   PROPFIND  /dav/{user}/{cal}/           → Kalender-Collection (Event-Liste)
#   REPORT    /dav/{user}/{cal}/           → calendar-query / calendar-multiget
#   GET       /dav/{user}/{cal}/{uid}.ics  → Einzelnes Event
#
# Berechtigung: Nutzer sieht nur Kalender, für die er Lese- oder Schreibrecht hat.

import re
import frappe
from werkzeug.exceptions import HTTPException
from werkzeug.wrappers import Response

_DAV = 'DAV:'
_CAL = 'urn:ietf:params:xml:ns:caldav'
_XML_HDR = '<?xml version="1.0" encoding="UTF-8"?>'


# ─────────────────────────────────────────────────────────────────────────────
# before_request Hook – einziger Einstiegspunkt
# ─────────────────────────────────────────────────────────────────────────────

def intercept():
    """
    Frappe before_request-Hook.
    Alle Anfragen an /dav/* und /.well-known/caldav werden hier abgefangen.
    """
    path = frappe.request.path

    # /.well-known/caldav → 301 nach /dav/
    if path == '/.well-known/caldav':
        _raise(Response('', status=301, headers={'Location': '/dav/'}))

    if not path.startswith('/dav'):
        return  # Frappe normal weiterleiten

    # Basic Auth
    from .auth import get_authenticated_user
    user = get_authenticated_user(frappe.request)
    if not user:
        _raise(Response(
            'Authentication required',
            status=401,
            headers={'WWW-Authenticate': 'Basic realm="Diakronos CalDAV"'}
        ))

    # Request routen und Antwort als HTTPException zurückwerfen
    # (Frappe fängt HTTPException ab und gibt sie direkt zurück)
    resp = _route(frappe.request, user, path)
    _raise(resp)


def _raise(response):
    raise HTTPException(response=response)


# ─────────────────────────────────────────────────────────────────────────────
# Router
# ─────────────────────────────────────────────────────────────────────────────

def _route(request, user, path):
    method = request.method.upper()

    # /dav  oder  /dav/
    rest  = path[4:].strip('/')          # alles nach /dav/
    parts = rest.split('/') if rest else []

    if method == 'OPTIONS':
        return _options()

    # /dav/
    if len(parts) == 0:
        if method == 'PROPFIND':
            return _propfind_root(user)
        return _method_not_allowed()

    # Sicherheitscheck: URL-User muss dem angemeldeten User entsprechen
    url_user = parts[0]
    if url_user.lower() != user.lower():
        return Response('Forbidden', status=403)

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
            return _report_calendar(user, cal_name, request)
        return _method_not_allowed()

    # /dav/{user}/{cal}/{uid}.ics
    uid = parts[2].removesuffix('.ics')
    if method == 'GET':
        return _get_event(user, cal_name, uid)

    return _method_not_allowed()


# ─────────────────────────────────────────────────────────────────────────────
# Berechtigungen
# ─────────────────────────────────────────────────────────────────────────────

def _get_user_calendars(user):
    """
    Gibt Liste der Kalender zurück, auf die der User Lese- oder Schreibrecht hat.
    Orientiert sich an der Rollen-basierten Logik aus permissions.py.
    """
    try:
        user_roles = set(frappe.get_roles(user))
        calendars  = frappe.get_all(
            'Kalender',
            fields=['name', 'calendar_name', 'calendar_color'],
            ignore_permissions=True
        )
        result = []
        for cal in calendars:
            doc = frappe.get_doc('Kalender', cal.name)
            can_read = any(
                r.role in user_roles
                for r in (doc.get('leserechte') or []) + (doc.get('schreibrechte') or [])
            )
            if can_read:
                result.append({
                    'name':  doc.name,
                    'title': doc.calendar_name or doc.name,
                    'color': doc.calendar_color or '#4f7cff',
                })
        return result
    except Exception as e:
        frappe.log_error(str(e), 'CalDAV get_user_calendars')
        return []


def _check_access(user, cal_name):
    """Gibt das Kalender-Dict zurück, wenn der User Zugriff hat, sonst None."""
    return next((c for c in _get_user_calendars(user) if c['name'] == cal_name), None)


def _get_events(cal_name, start=None, end=None):
    """Holt Element-Dokumente eines Kalenders (nur Festgelegt), optional nach Zeitraum gefiltert."""
    filters = {'element_calendar': cal_name, 'status': 'Festgelegt'}
    if start:
        filters['element_end']   = ['>=', start]
    if end:
        filters['element_start'] = ['<=', end]

    names = frappe.get_all('Element', filters=filters, pluck='name',
                           ignore_permissions=True)
    return [frappe.get_doc('Element', n) for n in names]


# ─────────────────────────────────────────────────────────────────────────────
# XML-Hilfsfunktionen
# ─────────────────────────────────────────────────────────────────────────────

def _xml(body):
    return Response(
        _XML_HDR + '\n' + body,
        status=207,
        content_type='text/xml; charset=utf-8'
    )


def _options():
    return Response('', status=200, headers={
        'Allow': 'OPTIONS, PROPFIND, REPORT, GET',
        'DAV':   '1, 2, calendar-access',
        'Content-Length': '0',
    })


def _method_not_allowed():
    return Response('Method Not Allowed', status=405)


# ─────────────────────────────────────────────────────────────────────────────
# PROPFIND-Handler
# ─────────────────────────────────────────────────────────────────────────────

def _propfind_root(user):
    """PROPFIND /dav/ → Principal-Discovery."""
    body = f'''<D:multistatus xmlns:D="{_DAV}" xmlns:C="{_CAL}">
  <D:response>
    <D:href>/dav/</D:href>
    <D:propstat>
      <D:prop>
        <D:resourcetype><D:collection/></D:resourcetype>
        <D:current-user-principal><D:href>/dav/{user}/</D:href></D:current-user-principal>
        <C:calendar-home-set><D:href>/dav/{user}/</D:href></C:calendar-home-set>
        <C:calendar-user-address-set>
          <D:href>mailto:{user}</D:href>
          <D:href>/dav/{user}/</D:href>
        </C:calendar-user-address-set>
      </D:prop>
      <D:status>HTTP/1.1 200 OK</D:status>
    </D:propstat>
  </D:response>
</D:multistatus>'''
    return _xml(body)


def _propfind_home(user):
    """PROPFIND /dav/{user}/ → Kalender-Liste des Users."""
    calendars = _get_user_calendars(user)

    entries = ''
    for cal in calendars:
        entries += f'''  <D:response>
    <D:href>/dav/{user}/{cal["name"]}/</D:href>
    <D:propstat>
      <D:prop>
        <D:resourcetype><D:collection/><C:calendar/></D:resourcetype>
        <D:displayname>{cal["title"]}</D:displayname>
        <C:supported-calendar-component-set>
          <C:comp name="VEVENT"/>
        </C:supported-calendar-component-set>
        <x:calendar-color xmlns:x="http://apple.com/ns/ical/">{cal["color"]}</x:calendar-color>
      </D:prop>
      <D:status>HTTP/1.1 200 OK</D:status>
    </D:propstat>
  </D:response>\n'''

    body = f'''<D:multistatus xmlns:D="{_DAV}" xmlns:C="{_CAL}">
  <D:response>
    <D:href>/dav/{user}/</D:href>
    <D:propstat>
      <D:prop>
        <D:resourcetype><D:collection/></D:resourcetype>
        <C:calendar-home-set><D:href>/dav/{user}/</D:href></C:calendar-home-set>
      </D:prop>
      <D:status>HTTP/1.1 200 OK</D:status>
    </D:propstat>
  </D:response>
{entries}</D:multistatus>'''
    return _xml(body)


def _propfind_calendar(user, cal_name, request):
    """PROPFIND /dav/{user}/{cal}/ → Collection-Info + Event-Liste (Depth:1)."""
    cal = _check_access(user, cal_name)
    if not cal:
        return Response('Not Found', status=404)

    depth = request.headers.get('Depth', '0')

    body = f'''<D:multistatus xmlns:D="{_DAV}" xmlns:C="{_CAL}">
  <D:response>
    <D:href>/dav/{user}/{cal_name}/</D:href>
    <D:propstat>
      <D:prop>
        <D:resourcetype><D:collection/><C:calendar/></D:resourcetype>
        <D:displayname>{cal["title"]}</D:displayname>
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
    <D:href>/dav/{user}/{cal_name}/{el.name}.ics</D:href>
    <D:propstat>
      <D:prop>
        <D:resourcetype/>
        <D:getcontenttype>text/calendar;charset=utf-8</D:getcontenttype>
        <D:getetag>"{el.name}-{etag}"</D:getetag>
      </D:prop>
      <D:status>HTTP/1.1 200 OK</D:status>
    </D:propstat>
  </D:response>\n'''

    body += '</D:multistatus>'
    return _xml(body)


# ─────────────────────────────────────────────────────────────────────────────
# REPORT-Handler (calendar-query + calendar-multiget)
# ─────────────────────────────────────────────────────────────────────────────

def _report_calendar(user, cal_name, request):
    """REPORT /dav/{user}/{cal}/ → Events mit iCal-Daten."""
    cal = _check_access(user, cal_name)
    if not cal:
        return Response('Not Found', status=404)

    xml_body = request.data or b''

    # calendar-multiget: konkrete UIDs angefragt
    if b'calendar-multiget' in xml_body:
        uids = re.findall(r'/dav/[^/]+/[^/]+/([^<"]+)\.ics', xml_body.decode('utf-8', 'ignore'))
        events = [frappe.get_doc('Element', uid) for uid in uids
                  if frappe.db.exists('Element', uid)]
    else:
        # calendar-query: Zeitraum-Filter
        start, end = _parse_time_range(xml_body)
        events = _get_events(cal_name, start, end)

    from .ical import element_to_ical

    body = f'<D:multistatus xmlns:D="{_DAV}" xmlns:C="{_CAL}">\n'
    for el in events:
        ical = element_to_ical(el)
        etag = str(el.modified or el.creation)
        body += f'''  <D:response>
    <D:href>/dav/{user}/{cal_name}/{el.name}.ics</D:href>
    <D:propstat>
      <D:prop>
        <D:getcontenttype>text/calendar;charset=utf-8</D:getcontenttype>
        <D:getetag>"{el.name}-{etag}"</D:getetag>
        <C:calendar-data>{ical}</C:calendar-data>
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
    """GET /dav/{user}/{cal}/{uid}.ics → iCal-Datei."""
    if not _check_access(user, cal_name):
        return Response('Forbidden', status=403)

    try:
        el = frappe.get_doc('Element', uid)
        if el.element_calendar != cal_name:
            return Response('Not Found', status=404)
    except frappe.DoesNotExistError:
        return Response('Not Found', status=404)

    from .ical import element_to_ical
    etag = str(el.modified or el.creation)

    return Response(
        element_to_ical(el),
        status=200,
        content_type='text/calendar;charset=utf-8',
        headers={
            'ETag':                f'"{uid}-{etag}"',
            'Content-Disposition': f'attachment; filename="{uid}.ics"',
        }
    )


# ─────────────────────────────────────────────────────────────────────────────
# Hilfsfunktion: Zeitraum aus REPORT-Body extrahieren
# ─────────────────────────────────────────────────────────────────────────────

def _parse_time_range(xml_bytes):
    """Liest start/end aus einem CalDAV calendar-query REPORT-Body."""
    if not xml_bytes:
        return None, None
    try:
        text    = xml_bytes.decode('utf-8', errors='ignore')
        start_m = re.search(r'time-range[^>]+start="([^"]+)"', text)
        end_m   = re.search(r'time-range[^>]+end="([^"]+)"',   text)

        def _parse(s):
            from datetime import datetime
            s = s.rstrip('Z')
            for fmt in ('%Y%m%dT%H%M%S', '%Y%m%d'):
                try:
                    return datetime.strptime(s[:len(fmt.replace('%', 'XX').replace('X', '0'))], fmt)
                except ValueError:
                    continue
            return None

        return (
            _parse(start_m.group(1)) if start_m else None,
            _parse(end_m.group(1))   if end_m   else None,
        )
    except Exception:
        return None, None
