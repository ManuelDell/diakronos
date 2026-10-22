"""Google calendar import, standalone endpoints at the original Frappe paths."""
from __future__ import annotations
FRAPPE_MODULE = "diakronos.kronos.api.google_import"

import base64
import binascii
import hashlib
import json
import secrets
import uuid

import httpx
from redis import Redis
from redis.exceptions import RedisError
from urllib.parse import urlencode, quote

from diakronos_app.frappe_compat import sitzungen
from diakronos_app.frappe_compat.auth_middleware import sid_aus_headers
from diakronos_app.frappe_compat.queue import enqueue
from diakronos_app.frappe_compat.realtime import publish_realtime
from datetime import date, datetime, timedelta, timezone
from itertools import islice
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from dateutil.rrule import rrulestr
from icalendar import Calendar
from sqlalchemy import select

from diakronos_app.google_secrets import decrypt_secret, encrypt_secret
from diakronos_app.frappe_compat.exceptions import ValidationError

from diakronos_app import db as database
from diakronos_app.frappe_compat.exceptions import PermissionError, throw
from diakronos_app.frappe_compat.permissions import get_roles
from diakronos_app.frappe_compat.registry import whitelist
from diakronos_app.frappe_compat.session import session
from diakronos_app.models.kronos import Element, GoogleKalenderEinstellungen, Kalender
from diakronos_app.models.core import UserRole
from diakronos_app.settings import settings as app_settings

SETTINGS_NAME = "Google Kalender Einstellungen"
IMPORT_ROLES = {"System Manager", "Mitgliederadministrator", "Kalenderadministrator"}


def _require_import_admin():
    if session.user == "Guest" or not (
        session.user == "Administrator" or IMPORT_ROLES.intersection(get_roles())
    ):
        throw("Kalender-Import nur für Administratoren.", PermissionError)


def _get_settings(db):
    return db.scalar(select(GoogleKalenderEinstellungen).where(
        GoogleKalenderEinstellungen.name == SETTINGS_NAME).with_for_update())


@whitelist(allow_guest=False)
def get_credentials_status():
    _require_import_admin()
    with database.SessionLocal() as db:
        settings = _get_settings(db)
        configured = authorized = False
        if settings:
            # Broken/legacy ciphertext is not usable configuration; never echo it.
            try:
                configured = bool(settings.client_id and settings.client_secret
                                  and decrypt_secret(settings.client_secret))
                authorized = bool(settings.authorized and settings.token_data
                                  and decrypt_secret(settings.token_data))
            except ValidationError:
                pass
        return {
            "configured": configured,
            "authorized": authorized,
            "redirect_uri": settings.redirect_uri or "" if settings else "",
        }


@whitelist(allow_guest=False)
def save_credentials(client_id=None, client_secret=None, redirect_uri="", request=None):
    _require_import_admin()
    if request is not None and request.method != "POST":
        throw("Credentials nur per POST speichern.")
    for value, limit in ((client_id, 140), (client_secret, 4096), (redirect_uri, 140)):
        if not isinstance(value, str) or len(value) > limit:
            throw("Ungültige Google-Credentials.")
    if not client_id.strip() or not client_secret:
        throw("Client-ID und Client-Secret fehlen.")
    redirect_uri = redirect_uri or (
        str(request.base_url).rstrip("/") + "/google-calendar-callback" if request
        else ""
    )
    try:
        parsed = urlsplit(redirect_uri)
    except ValueError:
        throw("Ungültige Redirect-URI.")
    if (parsed.scheme not in {"http", "https"} or not parsed.hostname
            or parsed.username or parsed.password or parsed.query or parsed.fragment
            or parsed.path != "/google-calendar-callback" or len(redirect_uri) > 140):
        throw("Ungültige Redirect-URI (Google-Callback erforderlich).")
    encrypted = encrypt_secret(client_secret)
    with database.SessionLocal.begin() as db:
        settings = _get_settings(db)
        if settings is None:
            settings = GoogleKalenderEinstellungen(name=SETTINGS_NAME)
            db.add(settings)
        settings.client_id = client_id.strip()
        settings.client_secret = encrypted
        settings.redirect_uri = redirect_uri
        settings.authorized = False
        settings.token_data = ""
    return {"success": True, "redirect_uri": redirect_uri}


GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_CAL_API = "https://www.googleapis.com/calendar/v3"
SCOPE = "https://www.googleapis.com/auth/calendar.readonly"


def _http_client():
    return httpx.Client(timeout=30, follow_redirects=False, trust_env=False)


def _state_store():
    return Redis.from_url(app_settings.redis_url, socket_timeout=5, socket_connect_timeout=5)


def _session_binding(request):
    sid = sid_aus_headers(request.headers) if request else None
    try:
        data = sitzungen.lesen(sid) if sid else None
    except RedisError:
        throw("Google-OAuth derzeit nicht verfügbar.")
    if not data or data.get("user") != session.user:
        throw("Gültige Sitzung für Google-OAuth erforderlich.", PermissionError)
    return hashlib.sha256((session.user + "\0" + sid).encode()).hexdigest()


def _credentials_fingerprint(settings):
    return hashlib.sha256((settings.client_id + "\0" + settings.client_secret + "\0"
                           + settings.redirect_uri).encode()).hexdigest()


def _configured_settings(db):
    settings = _get_settings(db)
    if not settings or not settings.client_id or not settings.client_secret or not settings.redirect_uri:
        throw("Bitte zuerst Google-Zugangsdaten konfigurieren.")
    decrypt_secret(settings.client_secret)
    return settings


@whitelist(allow_guest=False)
def get_oauth_url(request=None):
    _require_import_admin()
    binding = _session_binding(request)
    with database.SessionLocal() as db:
        settings = _configured_settings(db)
        state = secrets.token_urlsafe(32)
        key = "gcal:oauth:" + binding + ":" + hashlib.sha256(state.encode()).hexdigest()
        try:
            _state_store().set(key, _credentials_fingerprint(settings), ex=600)
        except RedisError:
            throw("Google-OAuth derzeit nicht verfügbar.")
        return {"url": GOOGLE_AUTH_URL + "?" + urlencode({
            "client_id": settings.client_id, "redirect_uri": settings.redirect_uri,
            "response_type": "code", "scope": SCOPE, "access_type": "offline",
            "prompt": "consent", "state": state,
        }), "redirect_uri": settings.redirect_uri}


def _google_json(method, url, **kwargs):
    # Never expose response bodies, URLs, authorization codes or transport exceptions.
    try:
        with _http_client() as client:
            response = client.request(method, url, **kwargs)
        if response.status_code != 200:
            throw("Google-Anfrage fehlgeschlagen (HTTP %s)." % response.status_code)
        result = response.json()
        if not isinstance(result, dict):
            raise ValueError
        return result
    except (httpx.HTTPError, ValueError):
        throw("Google-Anfrage fehlgeschlagen. Bitte erneut versuchen.")


def _token_payload(data, previous=None):
    try:
        access = data["access_token"]
        refresh = data.get("refresh_token") or (previous or {}).get("refresh_token")
        lifetime = int(data.get("expires_in", 3600))
        if (not isinstance(access, str) or not access or len(access) > 8192
                or lifetime <= 0 or lifetime > 31536000
                or (refresh is not None and (not isinstance(refresh, str) or len(refresh) > 8192))):
            raise ValueError
        return {"access_token": access, "refresh_token": refresh,
                "expiry": (datetime.now(timezone.utc) + timedelta(seconds=max(1, lifetime - 60))).isoformat()}
    except (KeyError, TypeError, ValueError, OverflowError):
        throw("Ungültige Google-Tokenantwort.")


def _consume_state(state, request, settings):
    if not isinstance(state, str) or not 40 <= len(state) <= 128:
        throw("OAuth-State ungültig oder abgelaufen. Bitte neu verbinden.")
    binding = _session_binding(request)
    key = "gcal:oauth:" + binding + ":" + hashlib.sha256(state.encode()).hexdigest()
    try:
        # Atomic consumption: concurrent callbacks cannot redeem the same state.
        expected = _state_store().getdel(key)
    except RedisError:
        throw("Google-OAuth derzeit nicht verfügbar.")
    if not expected or expected.decode() != _credentials_fingerprint(settings):
        throw("OAuth-State ungültig oder abgelaufen. Bitte neu verbinden.")


def _exchange_code(code, state, request):
    _require_import_admin()
    if not isinstance(code, str) or not code or len(code) > 4096:
        throw("Ungültiger OAuth-Code.")
    with database.SessionLocal.begin() as db:
        settings = _configured_settings(db)
        _consume_state(state, request, settings)
        data = _google_json("POST", GOOGLE_TOKEN_URL, data={
            "grant_type": "authorization_code", "code": code,
            "redirect_uri": settings.redirect_uri, "client_id": settings.client_id,
            "client_secret": decrypt_secret(settings.client_secret),
        })
        settings.token_data = encrypt_secret(json.dumps(_token_payload(data)))
        settings.authorized = True
    return {"success": True}


@whitelist(allow_guest=False)
def exchange_code(code=None, state=None, request=None):
    _require_import_admin()
    if request is not None and request.method != "POST":
        throw("OAuth-Code nur per POST austauschen.")
    return _exchange_code(code, state, request)


def _refresh_access_token(settings, token_data):
    refresh = token_data.get("refresh_token")
    if not refresh:
        throw("Bitte erneut mit Google verbinden (Refresh-Token fehlt).")
    data = _google_json("POST", GOOGLE_TOKEN_URL, data={
        "grant_type": "refresh_token", "refresh_token": refresh,
        "client_id": settings.client_id, "client_secret": decrypt_secret(settings.client_secret),
    })
    tokens = _token_payload(data, token_data)
    settings.token_data = encrypt_secret(json.dumps(tokens))
    return tokens


def _get_valid_access_token():
    with database.SessionLocal.begin() as db:
        settings = _configured_settings(db)
        if not settings.authorized or not settings.token_data:
            throw("Bitte zuerst mit Google verbinden.")
        try:
            tokens = json.loads(decrypt_secret(settings.token_data))
            expiry = datetime.fromisoformat(tokens["expiry"])
            if expiry.tzinfo is None or not tokens.get("access_token"):
                raise ValueError
        except (ValueError, TypeError, KeyError):
            throw("Ungültiges Google-Token. Bitte erneut verbinden.")
        if datetime.now(timezone.utc) >= expiry:
            tokens = _refresh_access_token(settings, tokens)
        return tokens["access_token"]


def _google_pages(path, token, params=None):
    seen = set()
    params = dict(params or {})
    for _ in range(1000):
        data = _google_json("GET", GOOGLE_CAL_API + path,
                            headers={"Authorization": "Bearer " + token}, params=params)
        items = data.get("items", [])
        if not isinstance(items, list) or any(not isinstance(item, dict) for item in items):
            throw("Ungültige Google-Kalenderantwort.")
        yield items
        page = data.get("nextPageToken")
        if not page:
            return
        if not isinstance(page, str) or len(page) > 4096 or page in seen:
            throw("Ungültige Google-Seitenfolge.")
        seen.add(page)
        params["pageToken"] = page
    throw("Google-Import zu gross. Bitte Zeitfilter einschraenken.")


@whitelist(allow_guest=False)
def get_google_calendars():
    _require_import_admin()
    calendars = []
    for items in _google_pages("/users/me/calendarList", _get_valid_access_token()):
        for cal in items:
            calendars.append({
                "id": cal.get("id"), "summary": cal.get("summary", "(Ohne Titel)"),
                "backgroundColor": cal.get("backgroundColor", "#4285F4"),
                "primary": bool(cal.get("primary", False)),
            })
            if len(calendars) > 10000:
                throw("Zu viele Google-Kalender.")
    return calendars


def _validate_mappings(mappings):
    if not isinstance(mappings, list) or not 1 <= len(mappings) <= 100:
        throw("Bitte 1 bis 100 Kalender auswählen.")
    result = []
    for m in mappings:
        if not isinstance(m, dict):
            throw("Ungültige Kalenderzuordnung.")
        fields = {"google_id": m.get("google_id"), "google_name": m.get("google_name", "Importierter Kalender"),
                  "target_kalender": m.get("target_kalender", ""), "color": m.get("color", "#4285F4"),
                  "time_filter": m.get("time_filter", "all"), "create_new": m.get("create_new", True)}
        if (not all(isinstance(fields[k], str) for k in ("google_id", "google_name", "target_kalender", "color", "time_filter"))
                or not fields["google_id"] or len(fields["google_id"]) > 1024
                or len(fields["google_name"]) > 130 or len(fields["target_kalender"]) > 140
                or type(fields["create_new"]) is not bool
                or fields["time_filter"] not in {"all", "from_today", "last_year", "last_3_years"}
                or len(fields["color"]) != 7 or not fields["color"].startswith("#")):
            throw("Ungültige Kalenderzuordnung.")
        try:
            int(fields["color"][1:], 16)
        except ValueError:
            throw("Ungültige Kalenderfarbe.")
        if not fields["create_new"]:
            with database.SessionLocal() as db:
                if not fields["target_kalender"] or not db.get(Kalender, fields["target_kalender"]):
                    throw("Zielkalender nicht gefunden.")
        result.append(fields)
    return result


@whitelist(allow_guest=False)
def start_import(mappings_json=None, request=None):
    _require_import_admin()
    if request is not None and request.method != "POST":
        throw("Google-Import nur per POST starten.")
    if not isinstance(mappings_json, str) or len(mappings_json) > 200000:
        throw("Ungültige Kalenderzuordnung.")
    try:
        mappings = json.loads(mappings_json)
    except ValueError:
        throw("Ungültige Kalenderzuordnung.")
    mappings = _validate_mappings(mappings)
    # Verify authorization before claiming the job is queued; worker refreshes as needed.
    _get_valid_access_token()
    try:
        enqueue(_do_import, mappings=mappings, user=session.user, queue="default", timeout=600)
    except Exception:
        throw("Import konnte nicht eingereiht werden. Bitte erneut versuchen.")
    return {"queued": True}


def _map_google_event(event, calendar_name):
    try:
        if event.get("status") == "cancelled":
            return None
        start_data, end_data = event["start"], event.get("end", event["start"])
        all_day = "date" in start_data and "dateTime" not in start_data
        if all_day:
            start = date.fromisoformat(start_data["date"])
            end = date.fromisoformat(end_data.get("date", start_data["date"]))
        else:
            start = datetime.fromisoformat(start_data["dateTime"])
            end = datetime.fromisoformat(end_data.get("dateTime", start_data["dateTime"]))
            if start.tzinfo is None:
                start = start.replace(tzinfo=ZoneInfo(start_data.get("timeZone", app_settings.calendar_timezone)))
            if end.tzinfo is None:
                end = end.replace(tzinfo=ZoneInfo(end_data.get("timeZone", start_data.get("timeZone", app_settings.calendar_timezone))))
        if end < start:
            return None
        uid = event.get("id", "")
        if not isinstance(uid, str) or not uid:
            return None
        return {"element_name": str(event.get("summary", "(Ohne Titel)"))[:140],
                "element_start": _ical_dt_to_frappe(start), "element_end": _ical_dt_to_frappe(end),
                "element_calendar": calendar_name, "all_day": all_day,
                "description": str(event.get("description", "")), "status": "Festgelegt",
                "google_event_id": "gcal:" + hashlib.sha256(uid.encode()).hexdigest()}
    except (KeyError, ValueError, TypeError, AttributeError):
        return None


def _import_events_from_google(google_calendar_id, frappe_calendar_name, access_token,
                               user=None, time_filter="all", db=None):
    if db is None:
        with database.SessionLocal.begin() as transaction:
            return _import_events_from_google(google_calendar_id, frappe_calendar_name, access_token,
                                               user, time_filter, transaction)
    params = {"maxResults": 250, "singleEvents": "true", "orderBy": "startTime"}
    days = {"from_today": 0, "last_year": 365, "last_3_years": 1095}
    if time_filter in days:
        params["timeMin"] = (datetime.now(timezone.utc) - timedelta(days=days[time_filter])).isoformat()
    known = set(db.scalars(select(Element.google_event_id).where(Element.element_calendar == frappe_calendar_name)))
    imported = skipped = seen = 0
    for items in _google_pages("/calendars/" + quote(google_calendar_id, safe="") + "/events", access_token, params):
        if seen == 0 and len(items) == 250:
            publish_realtime("gcal_import_progress", {"status": "warning",
                             "warning": "Grosser Kalender: Import kann laenger dauern."}, user=user or session.user)
        for event in items:
            seen += 1
            if seen > MAX_EVENTS:
                throw("Google-Import zu gross (max. 10000 Termine). Bitte Zeitfilter einschraenken.")
            fields = _map_google_event(event, frappe_calendar_name)
            if not fields or fields["google_event_id"] in known:
                skipped += 1
                continue
            _create_element_from_dict(fields, db)
            known.add(fields["google_event_id"])
            imported += 1
        publish_realtime("gcal_import_progress", {"status": "importing", "calendar_name": frappe_calendar_name,
                         "imported": imported, "skipped": skipped}, user=user or session.user)
    return imported, skipped


def _do_import(mappings, user):
    from diakronos_app.frappe_compat.benutzer_status import ist_aktiv
    previous_user = session.user
    session.user = user
    results = []
    errors = False
    def pub(data):
        publish_realtime("gcal_import_progress", data, user=user)
    try:
        if not ist_aktiv(user):
            throw("Import-Benutzer nicht mehr aktiv.", PermissionError)
        _require_import_admin()  # Recheck privileges after queue delay.
        mappings = _validate_mappings(mappings)
        for idx, mapping in enumerate(mappings):
            try:
                token = _get_valid_access_token()
                with database.SessionLocal.begin() as db:
                    name = (_ensure_kalender(mapping["google_name"], mapping["color"], db)
                            if mapping["create_new"] else mapping["target_kalender"])
                    pub({"status": "starting", "calendar_name": name, "cal_num": idx + 1,
                         "cal_total": len(mappings), "imported": 0})
                    imported, skipped = _import_events_from_google(mapping["google_id"], name, token,
                                                                  user, mapping["time_filter"], db)
                results.append({"google_name": mapping["google_name"], "frappe_kalender": name,
                                "imported": imported, "skipped": skipped})
            except Exception:
                errors = True
                # Transaction rolled back; never report partial writes as successful.
                pub({"status": "error", "error": "Kalender-Import fehlgeschlagen. Bitte Verbindung/Zeitfilter pruefen."})
    except Exception:
        errors = True
    finally:
        pub({"status": "done", "total_imported": sum(r["imported"] for r in results),
             "total_skipped": sum(r["skipped"] for r in results), "calendars": results,
             **({"error": "Mindestens ein Kalender konnte nicht importiert werden."} if errors else {})})
        session.user = previous_user


MAX_EVENTS = 10000


def _ical_dt_to_frappe(value, is_date=False):
    """Calendar-local naive storage, matching CRUD/read/Vue wall-time semantics.

    Convert aware instants only after RRULE expansion in the source timezone,
    so DST remains correct. Floating times and DATE values stay unchanged.
    """
    if isinstance(value, str):
        fmt = "%Y%m%d" if is_date or len(value) == 8 else "%Y%m%dT%H%M%S"
        utc = value.endswith("Z")
        value = datetime.strptime(value.rstrip("Z"), fmt)
        if utc:
            value = value.replace(tzinfo=timezone.utc)
    if isinstance(value, datetime):
        if value.tzinfo:
            value = value.astimezone(ZoneInfo(app_settings.calendar_timezone)).replace(tzinfo=None)
        return value
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time())
    raise ValueError("Invalid calendar datetime")


def _parse_ical(content: str) -> list[dict]:
    """Strict RFC5545 parsing; bounded RRULEs materialized as individual events.

    Fail the entire file before any writes for invalid/unsupported recurrence.
    No silent truncation: open-ended rules need an UNTIL/COUNT in the export.
    """
    try:
        calendar = Calendar.from_ical(content)
        if calendar.name != "VCALENDAR" or str(calendar.get("VERSION")) != "2.0":
            raise ValueError
        events = []
        for ev in calendar.walk("VEVENT"):
            if ev.errors or ev.get("RECURRENCE-ID") or ev.get("RDATE") or ev.get("EXRULE"):
                raise ValueError
            if str(ev.get("STATUS", "")).upper() == "CANCELLED":
                continue
            start = ev.decoded("DTSTART")
            all_day = isinstance(start, date) and not isinstance(start, datetime)
            end = ev.decoded("DTEND", None)
            if end is None:
                end = start + ev.decoded("DURATION", timedelta(days=1) if all_day else timedelta())
            if type(start) is not type(end) or end < start:
                raise ValueError
            for key in ("DTSTART", "DTEND"):
                prop = ev.get(key)
                if prop and prop.params.get("TZID") and getattr(prop.dt, "tzinfo", None) is None:
                    raise ValueError
            duration = end - start
            starts = [start]
            rule = ev.get("RRULE")
            if rule:
                if (rule.get("FREQ", [None])[0] not in {"DAILY", "WEEKLY", "MONTHLY", "YEARLY"}
                        or not (rule.get("COUNT") or rule.get("UNTIL"))
                        or int(rule.get("INTERVAL", [1])[0]) < 1
                        or int(rule.get("COUNT", [1])[0]) < 1
                        or int(rule.get("COUNT", [1])[0]) > MAX_EVENTS):
                    raise ValueError
                initial = datetime.combine(start, datetime.min.time()) if all_day else start
                until = rule.get("UNTIL", [None])[0]
                if until and _ical_dt_to_frappe(until) > _ical_dt_to_frappe(initial) + timedelta(days=36525):
                    raise ValueError
                starts = list(islice(rrulestr(rule.to_ical().decode(), dtstart=initial), MAX_EVENTS + 1))
                if len(starts) > MAX_EVENTS:
                    raise ValueError
                if all_day:
                    starts = [s.date() for s in starts]
            excluded = set()
            exdates = ev.get("EXDATE", [])
            for group in exdates if isinstance(exdates, list) else [exdates]:
                excluded.update(item.dt for item in group.dts)
            uid = str(ev.get("UID", ""))
            for occurrence in starts:
                if occurrence in excluded:
                    continue
                key = uid + ("/" + occurrence.isoformat() if rule else "")
                # Stable dedupe keys fit the existing String(140), even for long UIDs.
                event_id = "ical:" + hashlib.sha256(key.encode()).hexdigest() if uid else ""
                events.append({
                    "element_name": str(ev.get("SUMMARY", "(Ohne Titel)"))[:140],
                    "element_start": _ical_dt_to_frappe(occurrence),
                    "element_end": _ical_dt_to_frappe(occurrence + duration),
                    "all_day": all_day, "description": str(ev.get("DESCRIPTION", "")),
                    "status": "Festgelegt", "google_event_id": event_id,
                })
                if len(events) > MAX_EVENTS:
                    raise ValueError
        if not events:
            raise ValueError
        return events
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
        throw("Ungültige iCal-Datei oder nicht unterstützte/unbegrenzte Serie (max. 10000 Termine).")


def _create_element_from_dict(fields: dict, db=None):
    if db is None:
        with database.SessionLocal.begin() as transaction:
            return _create_element_from_dict(fields, transaction)
    from diakronos_app.frappe_compat.api_helpers import _coerce
    fields = _coerce("Element", fields)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    db.add(Element(name=uuid.uuid4().hex, owner=session.user, modified_by=session.user,
                   creation=now, modified=now, **fields))


def _ensure_kalender(name: str, color: str, db=None) -> str:
    if db is None:
        with database.SessionLocal.begin() as transaction:
            return _ensure_kalender(name, color, transaction)
    name = name.strip() or "Importierter Kalender"
    if len(name) > 130 or len(color) != 7 or not color.startswith("#"):
        throw("Ungültiger Kalendername oder Farbe.")
    try:
        int(color[1:], 16)
    except ValueError:
        throw("Ungültige Kalenderfarbe.")
    base, counter = name, 1
    while db.get(Kalender, name):
        name = f"{base} ({counter})"
        counter += 1
    db.add(Kalender(name=name, calendar_name=name, calendar_color=color,
                    owner=session.user, calender_details="Importiert aus Google Kalender"))
    for idx, role in enumerate(("Administrator", "Kalenderadministrator"), 1):
        db.add(UserRole(name=uuid.uuid4().hex, parent=name, parenttype="Kalender",
                        parentfield="leserechte", idx=idx, role=role))
    db.flush()
    return name


@whitelist(allow_guest=False)
def upload_ical(file_content_b64=None, target_kalender="", create_new=True,
                color="#4285F4", calendar_name_new="", request=None):
    _require_import_admin()
    if request is not None and request.method != "POST":
        throw("iCal-Import nur per POST.")
    limit = app_settings.max_upload_bytes
    if (not isinstance(file_content_b64, str) or limit <= 0
            or len(file_content_b64) > 4 * ((limit + 2) // 3)):
        throw("iCal-Datei fehlt oder ist zu gross.")
    try:
        raw = base64.b64decode(file_content_b64, validate=True)
        if len(raw) > limit:
            throw("iCal-Datei ist zu gross.")
        content = raw.decode("utf-8-sig").strip()
    except (binascii.Error, ValueError, UnicodeError):
        throw("iCal-Datei konnte nicht dekodiert werden.")
    if not content.startswith("BEGIN:VCALENDAR") or not content.endswith("END:VCALENDAR"):
        throw("Nur iCal-Dateien (.ics) sind erlaubt.")
    if create_new in (False, 0, "0", "false", "False"):
        create_new = False
    elif create_new in (True, 1, "1", "true", "True"):
        create_new = True
    else:
        throw("Ungültiger create_new-Wert.")
    if not all(isinstance(v, str) for v in (target_kalender, calendar_name_new, color)):
        throw("Ungültige Kalenderauswahl.")
    events = _parse_ical(content)
    imported = skipped = 0
    with database.SessionLocal.begin() as db:
        if create_new:
            calendar_name = _ensure_kalender(calendar_name_new, color, db)
        else:
            if not target_kalender:
                throw("Zielkalender fehlt.")
            if db.get(Kalender, target_kalender) is None:
                from diakronos_app.frappe_compat.exceptions import DoesNotExistError
                throw("Zielkalender nicht gefunden.", DoesNotExistError)
            calendar_name = target_kalender
        known = set(db.scalars(select(Element.google_event_id).where(
            Element.element_calendar == calendar_name, Element.google_event_id.is_not(None))))
        for fields in events:
            uid = fields["google_event_id"]
            if uid and uid in known:
                skipped += 1
                continue
            _create_element_from_dict({**fields, "element_calendar": calendar_name}, db)
            if uid:
                known.add(uid)
            imported += 1
    return {"success": True, "imported": imported, "skipped": skipped, "kalender": calendar_name}
