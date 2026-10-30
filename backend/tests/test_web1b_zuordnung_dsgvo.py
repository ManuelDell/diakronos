"""WEB-1b: die Zuordnung faellt mit dem Konto (DSGVO-1 / Art. 17).

Die Zuordnung `website_primo_konto` enthaelt die Mail-Adresse der Person und
die fremde Konto-ID. Sie steht deshalb in `dsgvo_anonymisierung.ZEILEN_LOESCHEN`
— dieser Test haelt fest, dass das nicht nur ein Inventar-Eintrag ist, sondern
die Zeile beim Loeschen WIRKLICH verschwindet (sonst waere der Eintrag ein
toter Buchstabe, und die Adresse bliebe nach der Loeschung stehen).

Zusaetzlich: nach der Loeschung entsteht beim naechsten Login KEINE neue
Zuordnung auf ein bestehendes Primo-Konto — der Weg zu 409 (Karte B1) bleibt
also auch fuer den geloeschten Fall geschlossen.

**Netz**: `--network none` (Kartenregel 11); Primo ist ein httpx-Stub,
die DB kommt aus `patched_db`.
"""

from __future__ import annotations

import json

import httpx
import pytest

import diakronos_app.api  # noqa: F401
from diakronos_app.models.core import HasRole, User
from diakronos_app.models.website import PrimoKonto

MODERATOR_MAIL = "moderator@example.org"


def _benutzer(sess, email: str, rollen=("Website-Moderator",)) -> str:
    sess.add(User(name=email, email=email, full_name="Test Person", enabled=True))
    for idx, rolle in enumerate(rollen, start=1):
        sess.add(
            HasRole(
                name=f"{email}-{rolle}",
                parent=email,
                parenttype="User",
                parentfield="roles",
                role=rolle,
                docstatus=0,
                idx=idx,
            )
        )
    sess.commit()
    return email


def test_zuordnung_verschwindet_mit_dem_konto(patched_db):
    from diakronos_app import dsgvo_anonymisierung as dsgvo

    sess = patched_db()
    try:
        _benutzer(sess, MODERATOR_MAIL)
        sess.add(
            PrimoKonto(user=MODERATOR_MAIL, primo_id="rec-42", email=MODERATOR_MAIL)
        )
        sess.commit()

        # Die Tabelle steht im Inventar (sonst waere dieser Test sinnlos).
        assert "website_primo_konto" in {name for name, _ in dsgvo.ZEILEN_LOESCHEN}

        # Die Loeschroutine des Moduls ueber die Zeilen-Loeschung ausfuehren:
        # dieselbe Funktion, die die echte Loeschung benutzt.
        bestand = dsgvo.Bestand(
            mitglied=MODERATOR_MAIL,
            konten={MODERATOR_MAIL},
            namen={"Test Person"},
            adressen={MODERATOR_MAIL},
        )
        dsgvo._zeilen_loeschen(sess, bestand, MODERATOR_MAIL)
        sess.commit()

        assert sess.get(PrimoKonto, MODERATOR_MAIL) is None
    finally:
        sess.close()


def test_nach_loeschung_keine_neue_zuordnung_auf_bestehendes_konto(
    patched_db, monkeypatch
):
    """Bestehendes Primo-Konto + keine Zuordnung -> 409 (Karte B1, Fall 3)."""
    from fastapi.testclient import TestClient

    from diakronos_app.frappe_compat import sitzungen
    from diakronos_app.frappe_compat.session import set_user
    from diakronos_app.main import app
    from diakronos_app.settings import settings
    from diakronos_app.website import primo

    assert primo.KONFLIKT_KONTO_EXISTIERT  # Konstante existiert und wird geprueft

    sess = patched_db()
    _benutzer(sess, MODERATOR_MAIL)
    # Keine Zuordnung in der DB — aber in Primo liegt ein Konto mit der Mail.
    attrappe = {
        primo.PFAD_INFO: {"version": "v3.3.1", "site_count": 1},
        primo.PFAD_SUPERUSER_AUTH: {"token": "tok-superuser-abc"},
        primo.PFAD_USERS: {
            "items": [
                {
                    "id": "rec-99",
                    "email": MODERATOR_MAIL,
                    "verified": True,
                    "serverRole": "editor",
                }
            ]
        },
    }
    aufrufe: list[str] = []

    def handler(request: httpx.Request):
        aufrufe.append(f"{request.method} {request.url.path}")
        antwort = attrappe.get(request.url.path)
        if antwort is None:
            return httpx.Response(404, json={"message": "not found"})
        return httpx.Response(200, json=antwort)

    monkeypatch.setattr(settings, "primo_url", "http://primo.test:8095", raising=False)
    monkeypatch.setattr(settings, "primo_public_url", "https://w.example.org", raising=False)
    monkeypatch.setattr(settings, "primo_superuser_email", "a@primo.test", raising=False)
    monkeypatch.setattr(settings, "primo_superuser_password", "x", raising=False)
    monkeypatch.setattr(settings, "primo_superuser_password_file", "", raising=False)
    monkeypatch.setattr(settings, "primo_timeout_sekunden", 2.0, raising=False)

    echter = httpx.Client

    def _client(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return echter(*args, **kwargs)

    monkeypatch.setattr(primo.httpx, "Client", _client)

    set_user(MODERATOR_MAIL)
    sid, csrf = sitzungen.anlegen(MODERATOR_MAIL)
    c = TestClient(app)
    c.__enter__()
    try:
        c.cookies.set("sid", sid)
        c.headers["X-Frappe-CSRF-Token"] = csrf
        antwort = c.post("/api/method/diakronos_app.api.website.login_uebergabe")
    finally:
        c.__exit__(None, None, None)

    assert antwort.status_code == 409, antwort.text
    # Kein PATCH, kein impersonate, kein Anlegen.
    assert not any(a.startswith(("PATCH", "POST /api/collections/users/impersonate")) for a in aufrufe), aufrufe
    assert not any(a == f"POST {primo.PFAD_USERS}" for a in aufrufe), aufrufe
    with patched_db() as sess2:
        assert sess2.get(PrimoKonto, MODERATOR_MAIL) is None
