"""Original OAuth callback path, without Frappe Desk or sensitive errors."""
from __future__ import annotations

import logging
from urllib.parse import urlencode

from fastapi import APIRouter, Request
from starlette.responses import JSONResponse, RedirectResponse

from diakronos_app.api.kronos.google_import import (
    _configured_settings, _consume_state, _exchange_code, _require_import_admin,
)
from diakronos_app import db as database
from diakronos_app.frappe_compat.exceptions import PermissionError, ValidationError

router = APIRouter()


class OAuthAccessLogFilter(logging.Filter):
    """Uvicorn normally logs query strings including authorization codes."""
    def filter(self, record):
        if isinstance(record.args, tuple) and len(record.args) == 5:
            args = list(record.args)
            target = str(args[2])
            if target.split("?", 1)[0] in {
                "/google-calendar-callback",
                "/api/method/diakronos.kronos.api.google_import.exchange_code",
                "/api/method/diakronos_app.api.kronos.google_import.exchange_code",
            }:
                args[2] = target.split("?", 1)[0]
                record.args = tuple(args)
        return True


logging.getLogger("uvicorn.access").addFilter(OAuthAccessLogFilter())


@router.get("/google-calendar-callback")
def google_calendar_callback(request: Request):
    headers = {"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"}
    try:
        _require_import_admin()
    except PermissionError:
        return JSONResponse({"error": "Kalender-Import nur fuer Administratoren."}, status_code=403, headers=headers)
    try:
        if request.query_params.get("error"):
            # Consume cancellation state as well. Never reflect Google's error text.
            with database.SessionLocal() as db:
                _consume_state(request.query_params.get("state"), request, _configured_settings(db))
            params = {"gcal_error": "Google-Autorisierung abgebrochen. Bitte erneut verbinden."}
        else:
            _exchange_code(request.query_params.get("code"), request.query_params.get("state"), request)
            params = {"gcal_step": "2"}
    except (ValidationError, PermissionError):
        params = {"gcal_error": "Google-Verbindung fehlgeschlagen oder abgelaufen. Bitte erneut verbinden."}
    return RedirectResponse("/diakonos?" + urlencode(params) + "#/kalender/import", status_code=303, headers=headers)
