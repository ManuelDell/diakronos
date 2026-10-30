"""WEB-1 — Primo-Anbindung: Rollen-Gate, Status, Uebergabe (alles gemockt).

Die Karte verlangt: Test vorher rot -> Fix -> gruen. Die Datei deckt

  (S2) Status-Zustaende "nicht_konfiguriert" | "nicht_erreichbar" | "verbunden"
  (S3) Rollen-Gate: nur System Manager / Administrator / Website-Moderator,
       alle anderen 403
  (S4) Provisionierung + Rollen-Mapping, impersonate-Aufruf, Fragment-Format
  (S5) kein Secret in Antworten und in keiner Log-Zeile

**Netz**: `--network none` ist Pflicht (Kartenregel 11). Primo wird deshalb
NICHT per respx/HTTP-Stub erreicht, sondern ueber einen `httpx`-Transport-
Stub, der ausschliesslich die drei PocketBase-Routen beantwortet und jede
andere Anfrage als Fehler meldet. Kein Test spricht einen echten Host an,
kein Test greift auf `settings.database_url` zu (DB kommt aus `patched_db`).
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
MODERATOR_MAIL = "moderator@example.org"
MITGLIED_MAIL = "mitglied@example.org"


# ── Primo-Attrappe (httpx-Transport) ────────────────────────────────────────


class PrimoAttrappe:
    """Beantwortet die von `primo.py` benutzten PocketBase-Routen.

    Alles andere ist ein Testfehler: eine unerwartete Route bedeutet, dass der
    Adapter einen Pfad benutzt, den diese Attrappe (und damit der Test) nicht
    kennt — das soll auffallen, nicht stillschweigend 200 liefern.
    """

    def __init__(self):
        self.anfragen: list[tuple[str, str, dict]] = []
        self.benutzer: dict[str, dict] = {}   # email -> record
        self.naechste_id = 0
        self.superuser_ok = True
        self.info_antwort = {
            "version": "v3.3.1",
            "site_count": 2,
            "domain_provider": "manual",
        }
        self.info_status = 200
        self.offline = False
        self.impersonate_status = 200
        self.impersonate_token = "tok-impersonate-123"

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
            if not self.superuser_ok:
                return httpx.Response(
                    400, json={"message": "Failed to authenticate."}
                )
            if (
                koerper.get("identity") != SUPERUSER_MAIL
                or koerper.get("password") != SUPERUSER_PASSWORT
            ):
                return httpx.Response(400, json={"message": "Failed to authenticate."})
            return httpx.Response(200, json={"token": "tok-superuser-abc"})

        if pfad == primo.PFAD_USERS and request.method == "GET":
            if auth != "tok-superuser-abc":
                return httpx.Response(401, json={"message": "unauthorized"})
            filter_ausdruck = request.url.params.get("filter", "")
            email = filter_ausdruck.split("=", 1)[1].strip().strip('"') if "=" in filter_ausdruck else ""
            treffer = self.benutzer.get(email)
            return httpx.Response(200, json={"items": [treffer] if treffer else []})

        # Einzelsatz per id (WEB-1b: die Zuordnung zeigt auf eine primo_id).
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
            self.naechste_id += 1
            record = {
                "id": f"rec{self.naechste_id:04d}",
                "email": koerper.get("email"),
                "verified": koerper.get("verified"),
                "serverRole": koerper.get("serverRole"),
            }
            self.benutzer[str(koerper.get("email"))] = record
            return httpx.Response(200, json=record)

        if pfad.startswith(primo.PFAD_USERS + "/") and request.method == "PATCH":
            if auth != "tok-superuser-abc":
                return httpx.Response(401, json={"message": "unauthorized"})
            record_id = pfad.rsplit("/", 1)[-1]
            for record in self.benutzer.values():
                if record["id"] == record_id:
                    record.update(koerper)
                    return httpx.Response(200, json=record)
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
    monkeypatch.setattr(settings, "primo_token_sekunden", 300, raising=False)

    echter_client = httpx.Client

    def _client(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(attrappe.handler)
        return echter_client(*args, **kwargs)

    monkeypatch.setattr(primo.httpx, "Client", _client)
    return attrappe


@pytest.fixture()
def unkonfiguriert(monkeypatch):
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


# ── S2: Status ─────────────────────────────────────────────────────────────


def test_status_nicht_konfiguriert_ohne_primo(unkonfiguriert, als_benutzer):
    c = als_benutzer(ADMIN_MAIL)
    antwort = c.get(f"/api/method/{PFAD_STATUS}")
    assert antwort.status_code == 200, antwort.text
    daten = antwort.json()["message"]
    assert daten == {
        "status": "nicht_konfiguriert",
        "version": None,
        "site_count": None,
        "url": None,
        # WEB-1b/H: ohne Anbindung gibt es nichts zu warnen.
        "warnung": None,
    }


def test_status_verbunden_liefert_version_und_site_count(primo_attrappe, als_benutzer):
    c = als_benutzer(ADMIN_MAIL)
    antwort = c.get(f"/api/method/{PFAD_STATUS}")
    assert antwort.status_code == 200, antwort.text
    daten = antwort.json()["message"]
    assert daten["status"] == "verbunden"
    assert daten["version"] == "v3.3.1"
    assert daten["site_count"] == 2
    # Browser-Adresse, NICHT die interne Server-Adresse.
    assert daten["url"] == PRIMO_PUBLIC
    assert primo_attrappe.routen() == [f"GET {primo.PFAD_INFO}"]


def test_status_nicht_erreichbar_ist_zustand_und_keine_exception(primo_attrappe, als_benutzer):
    primo_attrappe.offline = True
    c = als_benutzer(ADMIN_MAIL)
    antwort = c.get(f"/api/method/{PFAD_STATUS}")
    assert antwort.status_code == 200, antwort.text
    daten = antwort.json()["message"]
    assert daten["status"] == "nicht_erreichbar"
    assert daten["version"] is None
    assert daten["site_count"] is None
    # Die Browser-Adresse bleibt bekannt (die Einstellung ist gesetzt).
    assert daten["url"] == PRIMO_PUBLIC


def test_status_nicht_erreichbar_auch_bei_fehlerstatus(primo_attrappe, als_benutzer):
    primo_attrappe.info_status = 500
    c = als_benutzer(ADMIN_MAIL)
    daten = c.get(f"/api/method/{PFAD_STATUS}").json()["message"]
    assert daten["status"] == "nicht_erreichbar"


# ── S3: Rollen-Gate ────────────────────────────────────────────────────────


@pytest.mark.parametrize("pfad", [PFAD_STATUS, PFAD_ROLLEN, PFAD_LOGIN])
def test_normales_mitglied_bekommt_403(primo_attrappe, als_benutzer, pfad):
    c = als_benutzer(MITGLIED_MAIL)
    antwort = c.get(f"/api/method/{pfad}")
    assert antwort.status_code == 403, antwort.text
    assert antwort.json()["exc_type"] == "PermissionError"
    # Fail closed: ein abgewiesener Aufruf darf Primo NICHT beruehren.
    assert primo_attrappe.routen() == []


def test_website_moderator_darf_status_und_rollen(primo_attrappe, als_benutzer):
    c = als_benutzer(MODERATOR_MAIL)
    assert c.get(f"/api/method/{PFAD_STATUS}").status_code == 200
    daten = c.get(f"/api/method/{PFAD_ROLLEN}").json()["message"]
    assert daten["berechtigt"] is True
    assert daten["primo_rolle"] == "editor"


@pytest.mark.parametrize("benutzer", [ADMIN_MAIL])
def test_systemmanager_ist_developer(primo_attrappe, als_benutzer, benutzer):
    c = als_benutzer(benutzer)
    daten = c.get(f"/api/method/{PFAD_ROLLEN}").json()["message"]
    assert daten["primo_rolle"] == "developer"


def test_rollen_zuordnung_vollstaendig():
    assert primo.primaere_primo_rolle(["System Manager"]) == "developer"
    assert primo.primaere_primo_rolle(["Administrator"]) == "developer"
    assert primo.primaere_primo_rolle(["Website-Moderator"]) == "editor"
    assert primo.primaere_primo_rolle(["Mitglied"]) is None
    assert primo.darf_website(["Mitglied"]) is False
    assert primo.darf_website(["Website-Moderator"]) is True


# ── S4: Provisionierung, Mapping, Impersonate, Fragment ────────────────────


def _fragment_zerlegen(url: str) -> tuple[str, dict]:
    basis, fragment = url.split("#", 1)
    assert basis == f"{PRIMO_PUBLIC}/diakronos-sso.html"
    teile = dict(stueck.split("=", 1) for stueck in fragment.split("&"))
    roh = teile["record"] + "=" * (-len(teile["record"]) % 4)
    return teile["token"], json.loads(base64.urlsafe_b64decode(roh))


def test_uebergabe_legt_konto_an_und_gibt_fragment(primo_attrappe, als_benutzer):
    c = als_benutzer(MODERATOR_MAIL)
    antwort = c.post(f"/api/method/{PFAD_LOGIN}")
    assert antwort.status_code == 200, antwort.text
    url = antwort.json()["message"]["url"]

    token, record = _fragment_zerlegen(url)
    assert token == primo_attrappe.impersonate_token
    assert record["email"] == MODERATOR_MAIL
    assert record["serverRole"] == "editor"

    # Konto wurde angelegt, mit Zufallspasswort, verified, ohne ServerRolle im Klartext
    konto = primo_attrappe.benutzer[MODERATOR_MAIL]
    assert konto["serverRole"] == "editor"
    assert konto["verified"] is True

    # Reihenfolge der Aufrufe: Superuser-Login -> users GET -> users POST ->
    # impersonate (mit 300 s).
    routen = primo_attrappe.routen()
    assert routen[0] == f"POST {primo.PFAD_SUPERUSER_AUTH}"
    assert f"GET {primo.PFAD_USERS}" in routen
    assert f"POST {primo.PFAD_USERS}" in routen
    assert routen[-1] == f"POST /api/collections/users/impersonate/{konto['id']}"
    impersonate_koerper = primo_attrappe.anfragen[-1][2]
    assert impersonate_koerper == {"duration": 300}


def test_uebergabe_gleicht_rolle_bei_bestehendem_konto_an(primo_attrappe, als_benutzer, welt):
    """WEB-1b: Rollen-Angleich NUR auf einem zugeordneten Konto."""
    from diakronos_app.models.website import PrimoKonto

    konto = {
        "id": "rec0001",
        "email": MODERATOR_MAIL,
        "verified": False,
        "serverRole": "developer",
    }
    primo_attrappe.benutzer[MODERATOR_MAIL] = konto
    welt.add(PrimoKonto(user=MODERATOR_MAIL, primo_id=konto["id"], email=MODERATOR_MAIL))
    welt.commit()

    c = als_benutzer(MODERATOR_MAIL)
    antwort = c.post(f"/api/method/{PFAD_LOGIN}")
    assert antwort.status_code == 200, antwort.text
    assert primo_attrappe.benutzer[MODERATOR_MAIL]["serverRole"] == "editor"
    routen = primo_attrappe.routen()
    assert f"PATCH /api/collections/users/records/{konto['id']}" in routen
    assert f"POST {primo.PFAD_USERS}" not in routen


def test_uebergabe_gleicht_rolle_nach_oben_an(primo_attrappe, als_benutzer, welt):
    """WEB-1b: Hochstufung editor -> developer ebenfalls nur mit Zuordnung."""
    from diakronos_app.models.website import PrimoKonto

    konto = {
        "id": "rec0002",
        "email": ADMIN_MAIL,
        "verified": True,
        "serverRole": "editor",
    }
    primo_attrappe.benutzer[ADMIN_MAIL] = konto
    welt.add(PrimoKonto(user=ADMIN_MAIL, primo_id=konto["id"], email=ADMIN_MAIL))
    welt.commit()

    c = als_benutzer(ADMIN_MAIL)
    assert c.post(f"/api/method/{PFAD_LOGIN}").status_code == 200
    assert primo_attrappe.benutzer[ADMIN_MAIL]["serverRole"] == "developer"


def test_fragment_enthaelt_kein_passwort_und_keine_interne_adresse(primo_attrappe, als_benutzer):
    c = als_benutzer(ADMIN_MAIL)
    roh = c.post(f"/api/method/{PFAD_LOGIN}").text
    assert SUPERUSER_PASSWORT not in roh
    assert "tok-superuser" not in roh
    url = json.loads(roh)["message"]["url"]
    # Token nur im Fragment: vor dem `#` darf kein `token=` stehen, und die
    # interne Server-Adresse taucht nicht auf.
    assert "token=" not in url.split("#", 1)[0]
    assert "#token=" in url
    assert PRIMO_URL not in roh
    assert not roh.lower().count("password")


def test_impersonate_dauer_kommt_aus_der_einstellung(primo_attrappe, als_benutzer, monkeypatch):
    monkeypatch.setattr(settings, "primo_token_sekunden", 120, raising=False)
    c = als_benutzer(ADMIN_MAIL)
    assert c.post(f"/api/method/{PFAD_LOGIN}").status_code == 200
    assert primo_attrappe.anfragen[-1][2] == {"duration": 120}


# ── Fehlerbilder (keine Interna nach aussen) ───────────────────────────────


def test_uebergabe_ohne_konfiguration_ist_503(unkonfiguriert, als_benutzer):
    """WEB-1b/B3: 503 kommt an, der Klassenname aber NICHT (SEC-8-Allowlist).

    Die Oberflaeche unterscheidet am HTTP-Status — `exc_type` ist seit SEC-8
    fuer alles ausserhalb der Allowlist generisch `Error`.
    """
    c = als_benutzer(ADMIN_MAIL)
    antwort = c.post(f"/api/method/{PFAD_LOGIN}")
    assert antwort.status_code == 503, antwort.text
    assert antwort.json()["exc_type"] == "Error"


def test_uebergabe_bei_offline_primo_ist_503(primo_attrappe, als_benutzer):
    primo_attrappe.offline = True
    c = als_benutzer(ADMIN_MAIL)
    antwort = c.post(f"/api/method/{PFAD_LOGIN}")
    assert antwort.status_code == 503, antwort.text


def test_uebergabe_bei_abgelehntem_superuser_ist_503_ohne_detail(primo_attrappe, als_benutzer):
    primo_attrappe.superuser_ok = False
    c = als_benutzer(ADMIN_MAIL)
    antwort = c.post(f"/api/method/{PFAD_LOGIN}")
    assert antwort.status_code == 503, antwort.text
    assert SUPERUSER_PASSWORT not in antwort.text
    assert "Failed to authenticate" not in antwort.text
    # Kein Konto, kein Token: nach dem gescheiterten Login endet der Weg.
    assert primo_attrappe.benutzer == {}


def test_uebergabe_ohne_csrf_token_wird_abgewiesen(primo_attrappe, welt, patched_db, fake_redis):
    """POST ohne `X-Frappe-CSRF-Token` -> 417 `CSRFTokenError` (Karte S4)."""
    from fastapi.testclient import TestClient

    from diakronos_app.main import app

    set_user(ADMIN_MAIL)
    sid, _csrf = sitzungen.anlegen(ADMIN_MAIL)
    c = TestClient(app)
    c.__enter__()
    try:
        c.cookies.set("sid", sid)
        antwort = c.post(f"/api/method/{PFAD_LOGIN}")
    finally:
        c.__exit__(None, None, None)
    assert antwort.status_code == 417, antwort.text
    assert antwort.json()["exc_type"] == "CSRFTokenError"
    assert primo_attrappe.routen() == []


# ── S5: Secrets nie im Log ─────────────────────────────────────────────────


def test_keine_secrets_im_log(primo_attrappe, als_benutzer, caplog):
    caplog.set_level(logging.DEBUG)
    c = als_benutzer(ADMIN_MAIL)
    assert c.post(f"/api/method/{PFAD_LOGIN}").status_code == 200
    primo_attrappe.offline = True
    c.post(f"/api/method/{PFAD_LOGIN}")
    # Nur die EIGENEN Prozess-Logs zaehlen: die httpx-Client-Logs zeigen die
    # aufgerufene URL, und die ist konfiguriert (kein Secret).
    text = "\n".join(
        e.getMessage()
        for e in caplog.records
        if e.name.startswith("diakronos_app.") or e.name.startswith("diakronos_app")
    )
    assert text, "Es wurde gar nichts geloggt — dann misst der Test nichts."
    assert SUPERUSER_PASSWORT not in text
    assert "tok-superuser-abc" not in text
    assert primo_attrappe.impersonate_token not in text
    assert PRIMO_URL not in text


def test_zufallspasswort_wird_nie_zurueckgegeben(primo_attrappe, als_benutzer):
    c = als_benutzer(MODERATOR_MAIL)
    roh = c.post(f"/api/method/{PFAD_LOGIN}").text
    # Der Anlage-Aufruf enthaelt ein Passwort; die Antwort an den Browser nicht.
    anlage = [k for m, p, k in primo_attrappe.anfragen if p == primo.PFAD_USERS and m == "POST"]
    assert anlage and anlage[0]["password"]
    assert anlage[0]["password"] not in roh


# ── Einstellungen (S1) ─────────────────────────────────────────────────────


def test_public_url_faellt_auf_primo_url_zurueck(monkeypatch):
    from diakronos_app.settings import Settings

    werte = Settings(_env_file=None)
    monkeypatch.setenv("PRIMO_URL", "http://primo.intern:8095/")
    monkeypatch.setenv("PRIMO_PUBLIC_URL", "")
    monkeypatch.setenv("PRIMO_SUPERUSER_EMAIL", "a@b.de")
    monkeypatch.setenv("PRIMO_SUPERUSER_PASSWORD", "x")
    frisch = Settings(_env_file=None)
    assert frisch.primo_url_effektiv == "http://primo.intern:8095"
    assert frisch.primo_public_url_effektiv == "http://primo.intern:8095"
    assert frisch.primo_konfiguriert is True
    assert werte.primo_konfiguriert is False


def test_password_file_hat_vorrang(tmp_path, monkeypatch):
    from diakronos_app.settings import Settings

    datei = tmp_path / "primo_superuser"
    datei.write_text("aus-datei\n", encoding="utf-8")
    monkeypatch.setenv("PRIMO_URL", PRIMO_URL)
    monkeypatch.setenv("PRIMO_SUPERUSER_EMAIL", SUPERUSER_MAIL)
    monkeypatch.setenv("PRIMO_SUPERUSER_PASSWORD", "aus-env")
    monkeypatch.setenv("PRIMO_SUPERUSER_PASSWORD_FILE", str(datei))
    frisch = Settings(_env_file=None)
    assert frisch.primo_superuser_password_effektiv == "aus-datei"


def test_token_dauer_ist_begrenzt(monkeypatch):
    from diakronos_app.settings import Settings

    monkeypatch.setenv("PRIMO_TOKEN_SEKUNDEN", "86400")
    with pytest.raises(Exception):
        Settings(_env_file=None)
