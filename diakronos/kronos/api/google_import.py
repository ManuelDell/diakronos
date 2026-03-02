"""
Google Kalender Import – Backend API
======================================
Ermöglicht den einmaligen Import von Google Calendar Daten in Kronos.
Unterstützt:
  - OAuth2-Flow (für abonnierte/geteilte Kalender)
  - iCal-Upload (für exportierbare Kalender)

Kein bidirektionaler Sync – Frappe bleibt self-sustained.
"""

import frappe
import requests
import json
import base64
from datetime import datetime, timedelta
from urllib.parse import urlencode

from diakronos.kronos.api.event_crud import parse_iso_datetime_raw


# ── Google API Konstanten ──────────────────────────────────────────────────────
GOOGLE_AUTH_URL  = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_CAL_API   = "https://www.googleapis.com/calendar/v3"
SCOPE            = "https://www.googleapis.com/auth/calendar.readonly"


# ── Interne Hilfsfunktionen ────────────────────────────────────────────────────

def _get_settings():
    """Gibt das Single-DocType-Objekt zurück."""
    return frappe.get_single("Google Kalender Einstellungen")


def _get_valid_access_token():
    """Gibt einen gültigen Access Token zurück – refresh bei Bedarf."""
    settings = _get_settings()
    if not settings.token_data:
        frappe.throw("Kein OAuth-Token vorhanden. Bitte zuerst mit Google verbinden.")

    token_data = frappe.parse_json(settings.token_data)
    expiry_str = token_data.get("expiry")

    # Token abgelaufen? → Refresh
    if expiry_str:
        expiry = datetime.fromisoformat(expiry_str)
        if datetime.now() >= expiry:
            token_data = _refresh_access_token(settings, token_data)

    return token_data.get("access_token")


def _refresh_access_token(settings, token_data):
    """Holt einen neuen Access Token via Refresh Token."""
    refresh_token = token_data.get("refresh_token")
    if not refresh_token:
        frappe.throw("Kein Refresh Token vorhanden. Bitte erneut mit Google verbinden.")

    resp = requests.post(GOOGLE_TOKEN_URL, data={
        "grant_type":    "refresh_token",
        "refresh_token": refresh_token,
        "client_id":     settings.client_id,
        "client_secret": settings.get_password("client_secret"),
    }, timeout=15)

    if not resp.ok:
        frappe.throw(f"Token-Refresh fehlgeschlagen: {resp.text}")

    new_data = resp.json()
    token_data["access_token"] = new_data["access_token"]
    token_data["expiry"] = (
        datetime.now() + timedelta(seconds=new_data.get("expires_in", 3600) - 60)
    ).isoformat()

    # Aktualisiert speichern
    settings.token_data = json.dumps(token_data)
    settings.save(ignore_permissions=True)
    frappe.db.commit()

    return token_data


def _parse_ical(content: str) -> list:
    """
    Einfacher iCal-Parser ohne externe Bibliotheken.
    Gibt eine Liste von Dictionaries zurück (ein Dict pro VEVENT).
    """
    # Zeilenenden normalisieren + Continuation-Lines zusammenführen
    lines = content.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    unfolded = []
    for line in lines:
        if line.startswith((" ", "\t")) and unfolded:
            unfolded[-1] += line[1:]
        else:
            unfolded.append(line)

    events = []
    current = {}
    in_event = False

    for line in unfolded:
        stripped = line.strip()
        if stripped == "BEGIN:VEVENT":
            in_event = True
            current = {}
        elif stripped == "END:VEVENT":
            in_event = False
            if current:
                events.append(current)
        elif in_event and ":" in stripped:
            raw_key, _, value = stripped.partition(":")
            key = raw_key.split(";")[0].upper()   # Parameter wie TZID entfernen
            params_str = raw_key[len(key):]
            current[key] = value
            if "VALUE=DATE" in params_str.upper():
                current[f"{key}_IS_DATE"] = True

    return events


def _ical_dt_to_frappe(value: str, is_date: bool = False) -> str:
    """Konvertiert iCal-Datetime-String in Frappe-Format 'YYYY-MM-DD HH:MM:SS'."""
    if not value:
        return None
    value = value.strip().rstrip("Z")  # UTC-Z entfernen
    if is_date or len(value) == 8:
        # Nur Datum: YYYYMMDD → datetime am Tagesbeginn
        return datetime.strptime(value, "%Y%m%d").strftime("%Y-%m-%d %H:%M:%S")
    # Datetime: YYYYMMDDTHHMMSS
    try:
        return datetime.strptime(value, "%Y%m%dT%H%M%S").strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return datetime.strptime(value[:15], "%Y%m%dT%H%M%S").strftime("%Y-%m-%d %H:%M:%S")


def _create_element_from_dict(fields: dict) -> None:
    """Erstellt ein Element-Dokument aus einem fertigen Felddictionary."""
    doc = frappe.new_doc("Element")
    for key, val in fields.items():
        setattr(doc, key, val)
    doc.save(ignore_permissions=True)


# ── Whitelisted API-Funktionen ─────────────────────────────────────────────────

@frappe.whitelist()
def get_credentials_status():
    """
    Gibt zurück ob OAuth-Credentials konfiguriert und autorisiert sind.
    Response: {configured: bool, authorized: bool, redirect_uri: str}
    """
    settings = _get_settings()
    configured = bool(settings.client_id and settings.client_secret)
    authorized = bool(settings.authorized and settings.token_data)
    return {
        "configured":   configured,
        "authorized":   authorized,
        "redirect_uri": settings.redirect_uri or "",
    }


@frappe.whitelist()
def save_credentials(client_id, client_secret, redirect_uri=""):
    """Speichert Client-ID, Client-Secret und Redirect URI. Setzt authorized zurück."""
    settings = _get_settings()
    settings.client_id = client_id
    settings.client_secret = client_secret
    settings.redirect_uri = redirect_uri or f"{frappe.utils.get_url()}/google-calendar-callback"
    settings.authorized = 0
    settings.token_data = ""
    settings.save(ignore_permissions=True)
    frappe.db.commit()
    return {"success": True, "redirect_uri": settings.redirect_uri}


@frappe.whitelist()
def get_oauth_url():
    """
    Generiert die Google OAuth2 Autorisierungs-URL.
    Speichert einen State-Token im Cache (CSRF-Schutz).
    """
    settings = _get_settings()
    if not settings.client_id:
        frappe.throw("Bitte zuerst Client-ID und Client-Secret konfigurieren.")

    # CSRF-State generieren und im Cache speichern (10 Min.)
    state = frappe.generate_hash(length=20)
    frappe.cache().set_value(
        f"gcal_oauth_state_{frappe.session.user}", state, expires_in_sec=600
    )

    # Gespeicherte Redirect URI verwenden (muss exakt mit Google Console übereinstimmen)
    redirect_uri = settings.redirect_uri or f"{frappe.utils.get_url()}/google-calendar-callback"

    params = {
        "client_id":     settings.client_id,
        "redirect_uri":  redirect_uri,
        "response_type": "code",
        "scope":         SCOPE,
        "access_type":   "offline",   # damit refresh_token mitgeliefert wird
        "prompt":        "consent",   # erzwingt Anzeige + refresh_token
        "state":         state,
    }
    url = f"{GOOGLE_AUTH_URL}?{urlencode(params)}"
    return {"url": url, "redirect_uri": redirect_uri}


@frappe.whitelist()
def exchange_code(code, state):
    """
    Tauscht den Authorization Code gegen Access + Refresh Token.
    Verifiziert den State-Parameter (CSRF-Schutz).
    Wird vom OAuth-Callback aufgerufen.
    """
    # State verifizieren – bei Mismatch oder Cache-Fehler hart abbrechen (CSRF-Schutz)
    try:
        cached_state = frappe.cache().get_value(f"gcal_oauth_state_{frappe.session.user}")
        if cached_state != state:
            frappe.throw("OAuth-State ungültig – möglicher CSRF-Angriff. Bitte Import neu starten.")
        frappe.cache().delete_value(f"gcal_oauth_state_{frappe.session.user}")
    except frappe.ValidationError:
        raise
    except Exception as e:
        frappe.throw(f"OAuth-State konnte nicht verifiziert werden: {e}")

    settings = _get_settings()
    # Dieselbe Redirect URI wie beim Authorize-Request verwenden
    redirect_uri = settings.redirect_uri or f"{frappe.utils.get_url()}/google-calendar-callback"

    resp = requests.post(GOOGLE_TOKEN_URL, data={
        "grant_type":    "authorization_code",
        "code":          code,
        "redirect_uri":  redirect_uri,
        "client_id":     settings.client_id,
        "client_secret": settings.get_password("client_secret"),
    }, timeout=15)

    if not resp.ok:
        frappe.throw(f"Token-Austausch fehlgeschlagen: {resp.text}")

    token_json = resp.json()
    expires_in = token_json.get("expires_in", 3600)
    token_json["expiry"] = (
        datetime.now() + timedelta(seconds=expires_in - 60)
    ).isoformat()

    settings.token_data = json.dumps(token_json)
    settings.authorized = 1
    settings.save(ignore_permissions=True)
    frappe.db.commit()

    return {"success": True}


@frappe.whitelist()
def get_google_calendars():
    """
    Gibt alle Google Kalender des angemeldeten Accounts zurück.
    Response: [{id, summary, backgroundColor, primary}, ...]
    """
    token = _get_valid_access_token()
    resp = requests.get(
        f"{GOOGLE_CAL_API}/users/me/calendarList",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    if not resp.ok:
        frappe.throw(f"Google API Fehler: {resp.status_code} – {resp.text}")

    items = resp.json().get("items", [])
    return [
        {
            "id":              cal.get("id"),
            "summary":         cal.get("summary", "(Ohne Titel)"),
            "backgroundColor": cal.get("backgroundColor", "#4285F4"),
            "primary":         cal.get("primary", False),
        }
        for cal in items
    ]


@frappe.whitelist()
def start_import(mappings_json):
    """Stellt den Import in die Hintergrundwarteschlange. Fortschritt via Realtime."""
    mappings = frappe.parse_json(mappings_json)
    user = frappe.session.user
    frappe.enqueue(
        "diakronos.kronos.api.google_import._do_import",
        mappings=mappings,
        user=user,
        queue="long",
        timeout=600,
        enqueue_after_commit=False,
    )
    return {"queued": True}


def _do_import(mappings, user):
    """Hintergrundauftrag: importiert alle Kalender und sendet Fortschritt via Realtime."""
    def _pub(data):
        frappe.publish_realtime("gcal_import_progress", data, user=user)

    try:
        token = _get_valid_access_token()
    except Exception as e:
        _pub({"status": "done", "error": str(e)})
        return

    total_imported = 0
    total_skipped  = 0
    results        = []
    total_cals     = len(mappings)

    for idx, mapping in enumerate(mappings):
        google_id       = mapping.get("google_id")
        google_name     = mapping.get("google_name", google_id)
        target_kalender = mapping.get("target_kalender")
        create_new      = mapping.get("create_new", True)
        color           = mapping.get("color", "#4285F4")

        try:
            if create_new or not target_kalender:
                calendar_name = _ensure_kalender(google_name, color)
            else:
                calendar_name = target_kalender
        except Exception as e:
            _pub({"status": "error", "error": f"Kalender '{google_name}' konnte nicht angelegt werden: {e}"})
            continue

        time_filter = mapping.get("time_filter", "all")

        _pub({
            "status":        "starting",
            "calendar_name": calendar_name,
            "cal_num":       idx + 1,
            "cal_total":     total_cals,
            "imported":      0,
        })

        imported, skipped = _import_events_from_google(
            google_id, calendar_name, token, user=user, time_filter=time_filter
        )
        total_imported += imported
        total_skipped  += skipped
        results.append({
            "google_name":     google_name,
            "frappe_kalender": calendar_name,
            "imported":        imported,
            "skipped":         skipped,
        })
        # Nach jedem Kalender sichern
        frappe.db.commit()

    _pub({
        "status":         "done",
        "total_imported": total_imported,
        "total_skipped":  total_skipped,
        "calendars":      results,
    })


@frappe.whitelist()
def upload_ical(file_content_b64, target_kalender="", create_new=True, color="#4285F4", calendar_name_new=""):
    """
    Importiert Events aus einer base64-kodierten iCal-Datei.

    file_content_b64: base64-kodierter .ics Dateiinhalt
    target_kalender:  Name eines bestehenden Frappe-Kalenders (wenn create_new=False)
    create_new:       Neuen Kalender anlegen?
    color:            Farbe für neuen Kalender
    calendar_name_new: Name für den neuen Kalender
    """
    try:
        content = base64.b64decode(file_content_b64).decode("utf-8", errors="replace")
    except Exception:
        frappe.throw("iCal-Datei konnte nicht dekodiert werden.")

    events = _parse_ical(content)
    if not events:
        frappe.throw("Keine Termine in der iCal-Datei gefunden.")

    if create_new or not target_kalender:
        name_for_cal = calendar_name_new or "Importierter Kalender"
        calendar_name = _ensure_kalender(name_for_cal, color)
    else:
        calendar_name = target_kalender

    imported = 0
    skipped  = 0

    for ev in events:
        uid = ev.get("UID", "")

        # Duplikat-Check via google_event_id (nutzen wir auch für iCal-UID)
        if uid and frappe.db.exists("Element", {"google_event_id": uid}):
            skipped += 1
            continue

        summary = ev.get("SUMMARY", "(Ohne Titel)")
        dtstart_raw = ev.get("DTSTART", "")
        dtend_raw   = ev.get("DTEND",   dtstart_raw)
        is_date     = ev.get("DTSTART_IS_DATE", False)

        start_str = _ical_dt_to_frappe(dtstart_raw, is_date)
        end_str   = _ical_dt_to_frappe(dtend_raw,   ev.get("DTEND_IS_DATE", is_date))

        if not start_str:
            skipped += 1
            continue

        fields = {
            "element_name":     summary,
            "element_start":    start_str,
            "element_end":      end_str or start_str,
            "element_calendar": calendar_name,
            "all_day":          1 if is_date else 0,
            "description":      ev.get("DESCRIPTION", ""),
            "status":           "Festgelegt",
            "google_event_id":  uid,
        }
        _create_element_from_dict(fields)
        imported += 1

    frappe.db.commit()
    return {
        "success":       True,
        "imported":      imported,
        "skipped":       skipped,
        "kalender":      calendar_name,
    }


# ── Interne Import-Hilfsfunktionen ─────────────────────────────────────────────

def _ensure_kalender(name: str, color: str) -> str:
    """
    Legt einen Frappe-Kalender an, falls noch nicht vorhanden.
    Gibt den Namen des Kalenders zurück.
    """
    # Name eindeutig machen falls nötig
    base_name = name
    counter = 1
    while frappe.db.exists("Kalender", name):
        name = f"{base_name} ({counter})"
        counter += 1

    doc = frappe.new_doc("Kalender")
    doc.calendar_name    = name
    doc.calendar_color   = color or "#4285F4"
    doc.calender_details = "Importiert aus Google Kalender"
    # Leserechte: Administrator und Kalenderguru standardmäßig
    for rolle in ("Administrator", "Kalenderguru"):
        doc.append("leserechte", {"role": rolle})
    doc.save(ignore_permissions=True)
    return name


def _import_events_from_google(google_calendar_id: str, frappe_calendar_name: str, access_token: str, user: str = None, time_filter: str = "all"):
    """
    Lädt alle Events eines Google-Kalenders und legt sie als Element an.
    Gibt (imported_count, skipped_count) zurück.
    time_filter: "all" | "from_today" | "last_year" | "last_3_years"
    """
    from datetime import timezone

    imported      = 0
    skipped       = 0
    page_token    = None
    _user         = user or frappe.session.user
    warned_large  = False
    first_page    = True

    # Zeitfilter → timeMin
    now = datetime.now(timezone.utc)
    time_min = None
    if time_filter == "from_today":
        time_min = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    elif time_filter == "last_year":
        time_min = (now - timedelta(days=365)).strftime("%Y-%m-%dT%H:%M:%SZ")
    elif time_filter == "last_3_years":
        time_min = (now - timedelta(days=365 * 3)).strftime("%Y-%m-%dT%H:%M:%SZ")

    while True:
        params = {
            "maxResults":   250,
            "singleEvents": "true",
            "orderBy":      "startTime",
        }
        if time_min:
            params["timeMin"] = time_min
        if page_token:
            params["pageToken"] = page_token

        resp = requests.get(
            f"{GOOGLE_CAL_API}/calendars/{google_calendar_id}/events",
            headers={"Authorization": f"Bearer {access_token}"},
            params=params,
            timeout=30,
        )
        if not resp.ok:
            frappe.log_error(
                f"Google API Fehler für Kalender {google_calendar_id}: {resp.text}",
                "google_import"
            )
            frappe.publish_realtime("gcal_import_progress", {
                "status": "error",
                "error":  f"Google API Fehler für '{frappe_calendar_name}': {resp.status_code}",
            }, user=_user)
            break

        data  = resp.json()
        items = data.get("items", [])

        # Warnung bei großen Kalendern (nach erster Seite mit nextPageToken)
        if first_page and not warned_large and data.get("nextPageToken") and len(items) == 250:
            frappe.publish_realtime("gcal_import_progress", {
                "status":  "warning",
                "warning": f"Kalender '{frappe_calendar_name}' hat über 250 Termine – Import kann länger dauern.",
            }, user=_user)
            warned_large = True
        first_page = False

        for event in items:
            event_id = event.get("id", "")
            status   = event.get("status", "confirmed")

            if status == "cancelled":
                skipped += 1
                continue

            if event_id and frappe.db.exists("Element", {"google_event_id": event_id}):
                skipped += 1
                continue

            fields = _map_google_event(event, frappe_calendar_name)
            if not fields:
                skipped += 1
                continue

            _create_element_from_dict(fields)
            imported += 1

            # Fortschritt nach jedem importierten Termin senden
            frappe.publish_realtime("gcal_import_progress", {
                "status":        "importing",
                "calendar_name": frappe_calendar_name,
                "imported":      imported,
                "skipped":       skipped,
            }, user=_user)

            # Zwischenspeichern alle 1000 Termine
            if imported % 1000 == 0:
                frappe.db.commit()

        page_token = data.get("nextPageToken")
        if not page_token:
            break

    return imported, skipped


def _map_google_event(event: dict, calendar_name: str) -> dict | None:
    """
    Konvertiert ein Google-Event-Objekt in Frappe Element-Felder.
    Gibt None zurück wenn das Event übersprungen werden soll.
    """
    start_data = event.get("start", {})
    end_data   = event.get("end",   {})

    all_day = "date" in start_data and "dateTime" not in start_data

    if all_day:
        start_str = start_data.get("date", "")
        end_str   = end_data.get("date",   start_str)
        # Nur-Datum in Frappe Datetime umwandeln
        try:
            start_str = datetime.strptime(start_str, "%Y-%m-%d").strftime("%Y-%m-%d %H:%M:%S")
            end_str   = datetime.strptime(end_str,   "%Y-%m-%d").strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            return None
    else:
        start_str = start_data.get("dateTime", "")
        end_str   = end_data.get("dateTime",   start_str)
        start_str = parse_iso_datetime_raw(start_str)
        end_str   = parse_iso_datetime_raw(end_str) if end_str else start_str

    if not start_str:
        return None

    return {
        "element_name":     event.get("summary", "(Ohne Titel)"),
        "element_start":    start_str,
        "element_end":      end_str or start_str,
        "element_calendar": calendar_name,
        "all_day":          1 if all_day else 0,
        "description":      event.get("description", ""),
        "status":           "Festgelegt",
        "google_event_id":  event.get("id", ""),
    }
