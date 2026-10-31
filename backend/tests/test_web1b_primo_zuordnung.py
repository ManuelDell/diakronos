"""WEB-1b — Nachbesserung der Primo-Anbindung nach Opus-Sicherheitsreview.

Deckt die Punkte der Karte:

  (B1) Konto-ZUORDNUNG statt E-Mail-Uebernahme
       Tabelle `website_primo_konto`; drei Wege (Zuordnung vorhanden /
       kein Konto mit der Mail / Konto mit der Mail existiert schon -> 409);
       Superuser- und geschuetzte Konten sind VOR jedem Primo-Aufruf
       ausgeschlossen.
  (B2) `login_uebergabe` nimmt NUR POST an (alles andere 403, kein
       Primo-Aufruf).
  (B3) Nach SEC-8 geht der Exception-Name nur noch nach Allowlist nach
       aussen; die Oberflaeche unterscheidet per HTTP-Status 503.
  (T)  Gate-Tests: Gast -> 401, Mitgliederadministrator -> 403 auf allen
       drei Endpunkten, Rollenentzug wirkt beim naechsten Aufruf.
  (D)  Token-Dauer 4 h (14400 s), erlaubt 300..43200.
  (H)  `PRIMO_PUBLIC_URL` ohne https -> Warnung im Status, kein Blockieren.

**Netz**: `--network none` ist Pflicht (Kartenregel 11). Primo wird ueber
einen `httpx.MockTransport` bedient; kein Test spricht einen echten Host an,
kein Test greift auf `settings.database_url` zu (DB aus `patched_db`).
"""

from __future__ import annotations

import base64
import json
import logging

import httpx
import pytest

import diakronos_app.api  # noqa: F401 — registriert alle portierten Endpunkte
from diakronos_app.frappe_compat import sitzungen
from diakronos_app.frappe_compat.session import set_user
from diakronos_app.models.core import HasRole, User
from diakronos_app.models.website import PrimoKonto
from diakronos_app.settings import settings
from diakronos_app.website import primo

MODUL = "diakronos_app.api.website"
PFAD_STATUS = f"{MODUL}.status"
PFAD_LOGIN = f"{MODUL}.login_uebergabe"
PFAD_ROLLEN = f"{MODUL}.rollen"

PRIMO_URL = "http://primo.test:8095"
PRIMO_PUBLIC = "https://website.example.org"
SUPERUSER_MAIL = "admin@primo.test"
SUPERUSER_PASSWORT = "superuser-geheim-123"

ADMIN_MAIL = "admin@example.org"
MITGLIEDERADMIN_MAIL = "mitgliederadmin@example.org"
MODERATOR_MAIL = "moderator@example.org"
MITGLIED_MAIL = "mitglied@example.org"

#: Adresse, die in Primo schon existiert, ohne dass Diakronos sie kennt.
FREMD_MAIL = "fremd@example.org"


# ── Primo-Attrappe (httpx-Transport) ────────────────────────────────────────


class PrimoAttrappe:
    """Beantwortet die von `primo.py` benutzten PocketBase-Routen.

    Jede Anfrage wird mitgeschrieben (`anfragen`); `routen()` macht daraus
    lesbare Zeilen. Eine unerwartete Route ist ein Testfehler — der Adapter
    soll keinen Pfad benutzen, den diese Attrappe nicht kennt.
    """

    def __init__(self):
        self.anfragen: list[tuple[str, str, dict]] = []
        self.benutzer: dict[str, dict] = {}   # email -> record
        self.naechste_id = 0
        self.superuser_ok = True
        self.info_antwort = {"version": "v3.3.1", "site_count": 2}
        self.info_status = 200
        self.offline = False
        self.impersonate_status = 200
        self.impersonate_token = "tok-impersonate-123"

    def record(self, email: str, server_rolle: str = "editor", verified: bool = True) -> dict:
        """Legt einen bestehenden Primo-Nutzer an (Bestandskonto)."""
        self.naechste_id += 1
        rec = {
            "id": f"rec{self.naechste_id:04d}",
            "email": email,
            "verified": verified,
            "serverRole": server_rolle,
        }
        self.benutzer[email] = rec
        return rec

    # -- Transport ---------------------------------------------------------
    def handler(self, request: httpx.Request) -> httpx.Response:
        if self.offline:
            raise httpx.ConnectError("offline", request=request)
        pfad = request.url.path
        koerper = {}
        if request.content:
            try:
                koerper = json.loads(request.content)
            except ValueError:
                koerper = {}
        self.anfragen.append((request.method, pfad, koerper))
        auth = request.headers.get("authorization", "")

        if pfad == primo.PFAD_INFO:
            if self.info_status != 200:
                return httpx.Response(self.info_status, json={"message": "kaputt"})
            return httpx.Response(200, json=self.info_antwort)

        if pfad == primo.PFAD_SUPERUSER_AUTH:
            if (
                not self.superuser_ok
                or koerper.get("identity") != SUPERUSER_MAIL
                or koerper.get("password") != SUPERUSER_PASSWORT
            ):
                return httpx.Response(400, json={"message": "Failed to authenticate."})
            return httpx.Response(200, json={"token": "tok-superuser-abc"})

        if pfad == primo.PFAD_USERS and request.method == "GET":
            if auth != "tok-superuser-abc":
                return httpx.Response(401, json={"message": "unauthorized"})
            filter_ausdruck = request.url.params.get("filter", "")
            email = (
                filter_ausdruck.split("=", 1)[1].strip().strip('"')
                if "=" in filter_ausdruck
                else ""
            )
            treffer = self.benutzer.get(email)
            return httpx.Response(200, json={"items": [treffer] if treffer else []})

        # Einzelsatz per id (WEB-1b: Zuordnung zeigt auf eine primo_id).
        if pfad.startswith(primo.PFAD_USERS + "/") and request.method == "GET":
            if auth != "tok-superuser-abc":
                return httpx.Response(401, json={"message": "unauthorized"})
            record_id = pfad.rsplit("/", 1)[-1]
            for rec in self.benutzer.values():
                if rec["id"] == record_id:
                    return httpx.Response(200, json=rec)
            return httpx.Response(404, json={"message": "not found"})

        if pfad == primo.PFAD_USERS and request.method == "POST":
            if auth != "tok-superuser-abc":
                return httpx.Response(401, json={"message": "unauthorized"})
            email = str(koerper.get("email"))
            # Wie PocketBase (live geprueft): passwordConfirm muss gesetzt sein
            # und dem Passwort entsprechen, sonst 400 validation_required.
            if not koerper.get("passwordConfirm") or koerper.get("passwordConfirm") != koerper.get("password"):
                return httpx.Response(400, json={"data": {"passwordConfirm": {"code": "validation_required"}}})
            if email in self.benutzer:
                return httpx.Response(400, json={"message": "email already in use"})
            rec = self.record(email, str(koerper.get("serverRole")), bool(koerper.get("verified")))
            return httpx.Response(200, json=rec)

        if pfad.startswith(primo.PFAD_USERS + "/") and request.method == "PATCH":
            if auth != "tok-superuser-abc":
                return httpx.Response(401, json={"message": "unauthorized"})
            record_id = pfad.rsplit("/", 1)[-1]
            for rec in self.benutzer.values():
                if rec["id"] == record_id:
                    rec.update(koerper)
                    return httpx.Response(200, json=rec)
            return httpx.Response(404, json={"message": "not found"})

        if pfad.startswith("/api/collections/users/impersonate/"):
            if auth != "tok-superuser-abc":
                return httpx.Response(401, json={"message": "unauthorized"})
            if self.impersonate_status != 200:
                return httpx.Response(
                    self.impersonate_status, json={"message": "impersonate verboten"}
                )
            record_id = pfad.rsplit("/", 1)[-1]
            return httpx.Response(
                200,
                json={
                    "token": self.impersonate_token,
                    "record": {"id": record_id},
                    "duration": koerper.get("duration"),
                },
            )

        raise AssertionError(f"Unerwartete Primo-Route: {request.method} {pfad}")

    def routen(self) -> list[str]:
        return [f"{m} {p}" for m, p, _ in self.anfragen]

    def anzahl(self, methode: str, pfad: str) -> int:
        return sum(1 for m, p, _ in self.anfragen if m == methode and p == pfad)


@pytest.fixture()
def primo_attrappe(monkeypatch):
    """Konfiguriert `settings` auf die Attrappe und lenkt httpx dorthin."""
    attrappe = PrimoAttrappe()

    monkeypatch.setattr(settings, "primo_url", PRIMO_URL, raising=False)
    monkeypatch.setattr(settings, "primo_public_url", PRIMO_PUBLIC, raising=False)
    monkeypatch.setattr(settings, "primo_superuser_email", SUPERUSER_MAIL, raising=False)
    monkeypatch.setattr(settings, "primo_superuser_password", SUPERUSER_PASSWORT, raising=False)
    monkeypatch.setattr(settings, "primo_superuser_password_file", "", raising=False)
    monkeypatch.setattr(settings, "primo_timeout_sekunden", 2.0, raising=False)
    monkeypatch.setattr(settings, "primo_token_sekunden", 14400, raising=False)
    monkeypatch.setattr(settings, "primo_geschuetzte_konten", "", raising=False)

    echter_client = httpx.Client

    def _client(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(attrappe.handler)
        return echter_client(*args, **kwargs)

    monkeypatch.setattr(primo.httpx, "Client", _client)
    return attrappe


@pytest.fixture()
def unkonfiguriert(monkeypatch):
    """Primo ohne Adresse und ohne Superuser-Zugang (Modul schlaeft)."""
    for feld in (
        "primo_url",
        "primo_public_url",
        "primo_superuser_email",
        "primo_superuser_password",
        "primo_superuser_password_file",
    ):
        monkeypatch.setattr(settings, feld, "", raising=False)
    return settings


# ── Benutzer/Rollen ────────────────────────────────────────────────────────


def _benutzer_anlegen(sess, email: str, rollen=()) -> str:
    if sess.get(User, email) is None:
        sess.add(User(name=email, email=email, full_name=email, enabled=True))
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


@pytest.fixture()
def welt(patched_db):
    sess = patched_db()
    _benutzer_anlegen(sess, ADMIN_MAIL, ("System Manager", "Administrator"))
    _benutzer_anlegen(sess, MITGLIEDERADMIN_MAIL, ("Mitgliederadministrator",))
    _benutzer_anlegen(sess, MODERATOR_MAIL, ("Website-Moderator",))
    _benutzer_anlegen(sess, MITGLIED_MAIL, ("Mitglied",))
    yield sess
    sess.close()


@pytest.fixture()
def als_benutzer(welt, patched_db, fake_redis, monkeypatch):
    """Factory: HTTP-Client mit echter Sitzung fuer den genannten Benutzer."""
    from fastapi.testclient import TestClient

    from diakronos_app.main import app

    erzeugt: list[TestClient] = []

    def _bauen(benutzer: str) -> TestClient:
        set_user(benutzer)  # setzt die Identitaet (Naht ist an)
        sid, csrf = sitzungen.anlegen(benutzer)
        c = TestClient(app)
        c.__enter__()
        c.cookies.set("sid", sid)
        c.headers["X-Frappe-CSRF-Token"] = csrf
        erzeugt.append(c)
        return c

    yield _bauen
    for c in erzeugt:
        c.__exit__(None, None, None)


def _zuordnung(sess, user: str, primo_id: str, email: str) -> None:
    sess.add(PrimoKonto(user=user, primo_id=primo_id, email=email))
    sess.commit()


def _fragment_zerlegen(url: str) -> tuple[str, dict]:
    basis, fragment = url.split("#", 1)
    assert basis == f"{PRIMO_PUBLIC}/diakronos-sso.html"
    teile = dict(stueck.split("=", 1) for stueck in fragment.split("&"))
    roh = teile["record"] + "=" * (-len(teile["record"]) % 4)
    return teile["token"], json.loads(base64.urlsafe_b64decode(roh))


# ── (B1) Konto-Zuordnung ───────────────────────────────────────────────────


def test_zuordnung_vorhanden_nutzt_nur_diese_primo_id(primo_attrappe, welt, als_benutzer):
    """Fall 1: Zuordnung da -> nur DIESE primo_id, auch bei abweichender Mail."""
    konto = primo_attrappe.record("primo-konto@primo.test", "editor")
    _zuordnung(welt, MODERATOR_MAIL, konto["id"], "primo-konto@primo.test")

    c = als_benutzer(MODERATOR_MAIL)
    antwort = c.post(f"/api/method/{PFAD_LOGIN}")
    assert antwort.status_code == 200, antwort.text
    url = antwort.json()["message"]["url"]

    token, record = _fragment_zerlegen(url)
    assert token == primo_attrappe.impersonate_token
    assert record["id"] == konto["id"]
    # Kein Konto zur Diakronos-Mail und keine Suche danach.
    assert MODERATOR_MAIL not in primo_attrappe.benutzer
    routen = primo_attrappe.routen()
    assert f"GET {primo.PFAD_USERS}" not in routen
    assert f"POST {primo.PFAD_USERS}" not in routen
    assert routen[-1] == f"POST /api/collections/users/impersonate/{konto['id']}"


def test_zuordnung_mit_abweichender_mail_ist_409_und_aendert_nichts(
    primo_attrappe, welt, als_benutzer
):
    """Fall 1b: Mail in Primo weicht ab -> 409, KEIN PATCH, kein Token."""
    konto = primo_attrappe.record("primo-konto@primo.test", "editor")
    _zuordnung(welt, MODERATOR_MAIL, konto["id"], MODERATOR_MAIL)

    c = als_benutzer(MODERATOR_MAIL)
    antwort = c.post(f"/api/method/{PFAD_LOGIN}")
    assert antwort.status_code == 409, antwort.text
    assert primo_attrappe.benutzer["primo-konto@primo.test"]["serverRole"] == "editor"
    routen = primo_attrappe.routen()
    assert not any(r.startswith("PATCH") for r in routen), routen
    assert not any("impersonate" in r for r in routen), routen


def test_ohne_zuordnung_und_ohne_konto_wird_angelegt_und_zugeordnet(
    primo_attrappe, welt, als_benutzer
):
    """Fall 2: kein Konto mit der Mail -> anlegen, Zuordnung speichern."""
    c = als_benutzer(MODERATOR_MAIL)
    antwort = c.post(f"/api/method/{PFAD_LOGIN}")
    assert antwort.status_code == 200, antwort.text

    konto = primo_attrappe.benutzer[MODERATOR_MAIL]
    assert konto["serverRole"] == "editor"
    assert konto["verified"] is True

    zeile = welt.get(PrimoKonto, MODERATOR_MAIL)
    assert zeile is not None, "Zuordnung wurde nicht gespeichert"
    assert zeile.primo_id == konto["id"]
    assert zeile.email == MODERATOR_MAIL
    assert zeile.angelegt_am is not None


def test_ohne_zuordnung_aber_konto_existiert_ist_409_ohne_patch_und_impersonate(
    primo_attrappe, welt, als_benutzer
):
    """Fall 3: Primo-Konto mit der Mail existiert, Diakronos kennt es nicht.

    Dann ist die Adresse NICHT vertrauenswuerdig zugeordnet: kein Uebernehmen
    per Mail-Gleichheit, kein PATCH (Rollen-Angleich), kein impersonate.
    """
    primo_attrappe.record(FREMD_MAIL, "developer")
    c = als_benutzer(MODERATOR_MAIL)
    # Die Diakronos-Mail existiert in Primo bereits (z. B. von Hand angelegt).
    primo_attrappe.record(MODERATOR_MAIL, "developer")

    antwort = c.post(f"/api/method/{PFAD_LOGIN}")
    assert antwort.status_code == 409, antwort.text
    assert "Verknüpfung" in antwort.text or "verknuepfung" in antwort.text.lower()

    # Nichts geaendert: Rolle unveraendert, kein Token, keine Zuordnung.
    assert primo_attrappe.benutzer[MODERATOR_MAIL]["serverRole"] == "developer"
    routen = primo_attrappe.routen()
    assert not any(r.startswith("PATCH") for r in routen), routen
    assert not any("impersonate" in r for r in routen), routen
    assert welt.get(PrimoKonto, MODERATOR_MAIL) is None


def test_rolle_wird_nur_auf_zugeordneten_konten_angeglichen(
    primo_attrappe, welt, als_benutzer
):
    """Rollen-Angleich (serverRole) NUR auf einer bestehenden Zuordnung."""
    konto = primo_attrappe.record(MODERATOR_MAIL, "developer")
    _zuordnung(welt, MODERATOR_MAIL, konto["id"], MODERATOR_MAIL)

    c = als_benutzer(MODERATOR_MAIL)
    assert c.post(f"/api/method/{PFAD_LOGIN}").status_code == 200
    assert primo_attrappe.benutzer[MODERATOR_MAIL]["serverRole"] == "editor"
    assert f"PATCH {primo.PFAD_USERS}/{konto['id']}" in primo_attrappe.routen()


def test_superuser_mail_ist_hart_ausgeschlossen(primo_attrappe, welt, als_benutzer):
    """Superuser-Adresse: 409 VOR jedem Primo-Aufruf."""
    _benutzer_anlegen(welt, SUPERUSER_MAIL, ("System Manager", "Administrator"))
    c = als_benutzer(SUPERUSER_MAIL)
    antwort = c.post(f"/api/method/{PFAD_LOGIN}")
    assert antwort.status_code == 409, antwort.text
    assert primo_attrappe.routen() == []


def test_geschuetzte_konten_sind_ausgeschlossen(primo_attrappe, welt, als_benutzer, monkeypatch):
    """`PRIMO_GESCHUETZTE_KONTEN` (kommagetrennt) -> 409 ohne Primo-Aufruf."""
    monkeypatch.setattr(
        settings,
        "primo_geschuetzte_konten",
        "diakronos-integration@diedells.de, service@example.org",
        raising=False,
    )
    _benutzer_anlegen(welt, "service@example.org", ("System Manager", "Administrator"))
    c = als_benutzer("service@example.org")
    antwort = c.post(f"/api/method/{PFAD_LOGIN}")
    assert antwort.status_code == 409, antwort.text
    assert primo_attrappe.routen() == []


def test_geschuetzte_konten_default_ist_diakronos_integration(monkeypatch):
    """Der Default schuetzt das Integrationskonto ohne weitere Einstellung."""
    from diakronos_app.settings import Settings

    monkeypatch.delenv("PRIMO_GESCHUETZTE_KONTEN", raising=False)
    frisch = Settings(_env_file=None)
    assert frisch.primo_geschuetzte_konten_liste == ["diakronos-integration@diedells.de"]
    assert frisch.primo_ist_geschuetzt("diakronos-integration@diedells.de") is True
    assert frisch.primo_ist_geschuetzt("diakronos-integration@DIEDELLS.de") is True
    assert frisch.primo_ist_geschuetzt(MODERATOR_MAIL) is False


# ── (B2) Nur POST ──────────────────────────────────────────────────────────


def test_login_uebergabe_nur_post(primo_attrappe, als_benutzer):
    """GET/PUT/PATCH -> 405 MethodNotAllowed, Primo wird nicht angesprochen.

    SEC-11: Der Endpunkt traegt jetzt `@whitelist(methods=["POST"])` — die
    Methode wird VOR der Fachfunktion abgewiesen (vorher entschied der Rumpf
    selbst mit 403 PermissionError). Ergebnis gleich: keine Uebergabe.
    """
    c = als_benutzer(ADMIN_MAIL)
    for methode in ("get", "put", "patch"):
        antwort = getattr(c, methode)(f"/api/method/{PFAD_LOGIN}")
        assert antwort.status_code == 405, (methode, antwort.text)
        assert antwort.headers["allow"] == "POST"
    assert primo_attrappe.anzahl("POST", primo.PFAD_SUPERUSER_AUTH) == 0
    assert primo_attrappe.routen() == []


# ── (B3) 503 ohne Exc-Namen (SEC-8-Allowlist nicht erweitert) ──────────────


def test_nicht_konfiguriert_ist_503_mit_generischem_exc_namen(unkonfiguriert, als_benutzer):
    c = als_benutzer(ADMIN_MAIL)
    antwort = c.post(f"/api/method/{PFAD_LOGIN}")
    assert antwort.status_code == 503, antwort.text
    assert antwort.json()["exc_type"] == "Error"


# ── (T) Gate-Tests ─────────────────────────────────────────────────────────


@pytest.mark.parametrize("pfad", [PFAD_STATUS, PFAD_ROLLEN, PFAD_LOGIN])
def test_gast_bekommt_401_ohne_primo_aufruf(primo_attrappe, welt, als_benutzer, pfad):
    """Ohne Anmeldung: 401 — und kein einziger Primo-Aufruf."""
    from fastapi.testclient import TestClient

    from diakronos_app.main import app

    c = TestClient(app)
    c.__enter__()
    try:
        # SEC-11: der schreibende `login_uebergabe` ist POST-only — GET endet
        # mit 405, und zwar VOR der Anmelde-Pruefung. Die 401 („ohne Sitzung")
        # gilt fuer die erlaubte Methode, deshalb hier GET und POST zusammen.
        per_get = c.get(f"/api/method/{pfad}")
        antwort = c.post(f"/api/method/{pfad}")
    finally:
        c.__exit__(None, None, None)
    if pfad == PFAD_LOGIN:
        assert per_get.status_code == 405, per_get.text
        assert per_get.headers["allow"] == "POST"
    assert antwort.status_code == 401, antwort.text
    assert primo_attrappe.routen() == []


@pytest.mark.parametrize("pfad", [PFAD_STATUS, PFAD_ROLLEN, PFAD_LOGIN])
def test_mitgliederadministrator_bekommt_403_auf_allen_drei(
    primo_attrappe, als_benutzer, pfad
):
    c = als_benutzer(MITGLIEDERADMIN_MAIL)
    # SEC-11: `login_uebergabe` ist POST-only — die Rollenpruefung gilt fuer POST.
    if pfad == PFAD_LOGIN:
        assert c.get(f"/api/method/{pfad}").status_code == 405
        antwort = c.post(f"/api/method/{pfad}")
    else:
        antwort = c.get(f"/api/method/{pfad}")
    assert antwort.status_code == 403, antwort.text
    assert antwort.json()["exc_type"] == "PermissionError"
    assert primo_attrappe.routen() == []


def test_rollenentzug_wirkt_beim_naechsten_aufruf(primo_attrappe, welt, als_benutzer):
    """Rolle weg -> der naechste Aufruf ist 403 (auch wenn das Konto existiert)."""
    c = als_benutzer(MODERATOR_MAIL)
    assert c.post(f"/api/method/{PFAD_LOGIN}").status_code == 200
    vorher = len(primo_attrappe.anfragen)

    for zeile in welt.query(HasRole).filter(HasRole.parent == MODERATOR_MAIL).all():
        welt.delete(zeile)
    welt.commit()

    antwort = c.post(f"/api/method/{PFAD_LOGIN}")
    assert antwort.status_code == 403, antwort.text
    assert antwort.json()["exc_type"] == "PermissionError"
    assert len(primo_attrappe.anfragen) == vorher, "Nach dem Entzug darf Primo nicht mehr gefragt werden"


# ── (D) Token-Dauer ────────────────────────────────────────────────────────


def test_token_dauer_default_ist_vier_stunden(monkeypatch):
    from diakronos_app.settings import Settings

    monkeypatch.delenv("PRIMO_TOKEN_SEKUNDEN", raising=False)
    assert Settings(_env_file=None).primo_token_sekunden == 14400


@pytest.mark.parametrize("wert", ["14400", "300", "43200"])
def test_token_dauer_erlaubter_bereich(monkeypatch, wert):
    from diakronos_app.settings import Settings

    monkeypatch.setenv("PRIMO_TOKEN_SEKUNDEN", wert)
    assert Settings(_env_file=None).primo_token_sekunden == int(wert)


@pytest.mark.parametrize("wert", ["299", "43201", "86400", "0", "-1"])
def test_token_dauer_ausserhalb_wird_abgelehnt(monkeypatch, wert):
    from diakronos_app.settings import Settings

    monkeypatch.setenv("PRIMO_TOKEN_SEKUNDEN", wert)
    with pytest.raises(Exception):
        Settings(_env_file=None)


def test_impersonate_dauer_ist_vier_stunden(primo_attrappe, als_benutzer):
    c = als_benutzer(MODERATOR_MAIL)
    assert c.post(f"/api/method/{PFAD_LOGIN}").status_code == 200
    assert primo_attrappe.anfragen[-1][2] == {"duration": 14400}


# ── (H) PRIMO_PUBLIC_URL ohne https ────────────────────────────────────────


def test_public_url_ohne_https_erzeugt_warnung(primo_attrappe, als_benutzer, monkeypatch):
    monkeypatch.setattr(settings, "primo_public_url", "http://website.example.org", raising=False)
    c = als_benutzer(ADMIN_MAIL)
    daten = c.get(f"/api/method/{PFAD_STATUS}").json()["message"]
    assert daten["status"] == "verbunden"
    assert "https" in str(daten["warnung"]).lower()


def test_public_url_mit_https_hat_keine_warnung(primo_attrappe, als_benutzer):
    c = als_benutzer(ADMIN_MAIL)
    daten = c.get(f"/api/method/{PFAD_STATUS}").json()["message"]
    assert daten["warnung"] is None


def test_public_url_ohne_https_blockiert_nicht(primo_attrappe, als_benutzer, monkeypatch):
    """LAN-Test ueber http bleibt erlaubt: Warnung, aber 200 und Token."""
    monkeypatch.setattr(settings, "primo_public_url", "http://website.example.org", raising=False)
    c = als_benutzer(ADMIN_MAIL)
    antwort = c.post(f"/api/method/{PFAD_LOGIN}")
    assert antwort.status_code == 200, antwort.text


# ── Vertrag: keine Secrets ─────────────────────────────────────────────────


def test_keine_secrets_im_log(primo_attrappe, als_benutzer, caplog):
    caplog.set_level(logging.DEBUG)
    c = als_benutzer(ADMIN_MAIL)
    assert c.post(f"/api/method/{PFAD_LOGIN}").status_code == 200
    primo_attrappe.offline = True
    c.post(f"/api/method/{PFAD_LOGIN}")
    text = "\n".join(
        e.getMessage() for e in caplog.records if e.name.startswith("diakronos_app")
    )
    assert text, "Es wurde gar nichts geloggt — dann misst der Test nichts."
    assert SUPERUSER_PASSWORT not in text
    assert "tok-superuser-abc" not in text
    assert primo_attrappe.impersonate_token not in text
    assert PRIMO_URL not in text
