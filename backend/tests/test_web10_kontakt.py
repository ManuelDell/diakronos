"""WEB-10 — Oeffentliches Kontaktformular: sendet NUR eine Mail.

Die Karte verlangt Test-vorher-rot. Diese Datei deckt den ganzen Vertrag ab:

  (K1) `POST {Praefix}/api/method/website.kontakt_senden`, `allow_guest=True`,
       JSON `{name, email, nachricht, einwilligung, website}`. Ist `website`
       (Honeypot) gefuellt: 200 `{"ok": true}` und **keine** Mail.
  (K2) Validierung: name 1..100, email gueltig (<=254), nachricht 10..5000,
       `einwilligung is True`; sonst **400** mit generischer Meldung je Feld.
  (K3) Schutz: nur POST (alles andere -> **403**), Herkunft muss die eigene
       Domain sein (Origin/Referer, fremd -> **403**), Ratenbegrenzung ueber
       die vorhandene Bremse (Adresse 5/h, global 50/h -> **429**),
       Header-Injection unmoeglich (keine Zeilenumbrueche, Betreff fest).
  (K4) An = `WEBSITE_KONTAKT_EMPFAENGER`; fehlt sie -> **503**. Betreff fest,
       Reply-To = Absenderadresse, Text traegt Name/Adresse/Nachricht/Zeit.
       Nichts in der DB, nichts mit Inhalt ins Log.
  (K5) Doku: BETRIEBSANLEITUNG traegt den Abschnitt (eigener Test unten).

**Netz**: `--network none` (Kartenregel 11). Mail geht ueber die Testnaht
`mailversand.VERBINDUNG` (Fake-SMTP), Redis ueber den `fake_redis`-Stub,
DB ueber `patched_db`. Kein Test beruehrt `settings.database_url`, kein Test
spricht einen echten Host an.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

import pytest

import diakronos_app.api  # noqa: F401 — registriert alle portierten Endpunkte
from diakronos_app.mailversand import Mail, MailVersandFehler, MailNichtEingerichtet
from diakronos_app.settings import settings
from diakronos_app.website import kontakt

PFAD = "/api/method/website.kontakt_senden"
PFAD_VOLL = "/api/method/diakronos_app.api.website.kontakt_senden"
PFAD_DIAKRONOS = "/api/method/diakronos.diakronos.api.website.kontakt_senden"

EMPFAENGER = "kontakt@gemeinde.example.org"
ABSENDER_MAIL = "besucher@example.org"

GUELTIG = {
    "name": "Erika Beispiel",
    "email": ABSENDER_MAIL,
    "nachricht": "Bitte melden Sie sich bei mir wegen des Gemeindefestes.",
    "einwilligung": True,
    "website": "",
}


def setze_setting(name: str, wert) -> None:
    """Setzt eine Einstellung fuer die Dauer des Tests.

    `settings` ist eine pydantic-Instanz: `monkeypatch.setattr` scheitert dort
    an der Validierung, und Felder mit `validation_alias` greifen nicht auf
    den Feldnamen. `object.__setattr__` schreibt direkt; das Zuruecksetzen
    erledigt `monkeypatch.setattr` ueber denselben Umweg — deshalb wird der
    alte Wert hier gemerkt und am Ende zurueckgeschrieben (Fixture unten).
    """
    object.__setattr__(settings, name, wert)


@pytest.fixture(autouse=True)
def _settings_zuruecksetzen():
    """Stellt alle von den Tests veraenderten Einstellungen wieder her."""
    alt = {name: getattr(settings, name) for name in (
        "website_kontakt_empfaenger", "website_kontakt_max_ip",
        "website_kontakt_max_gesamt", "website_kontakt_fenster_sekunden",
    )}
    yield
    for name, wert in alt.items():
        object.__setattr__(settings, name, wert)


# ── Attrappen ──────────────────────────────────────────────────────────────


class FakeSMTP:
    """Minimaler SMTP-Ersatz mit derselben Schnittstelle wie `smtplib.SMTP`.

    `mailversand.sende(..., verbindung=<das hier>)` baut die Nachricht selbst
    und ruft `send_message`. Nur was der Versandpfad anfasst, ist hier da.
    """

    def __init__(self, scheitern: Exception | None = None) -> None:
        self.nachrichten: list = []
        self.scheitern = scheitern

    def ehlo(self):
        return (250, b"ok")

    def has_extn(self, name):
        return str(name).lower() == "starttls"

    def starttls(self, context=None):
        return (220, b"ok")

    def login(self, benutzer, passwort):
        return (235, b"ok")

    def send_message(self, nachricht):
        if self.scheitern is not None:
            raise self.scheitern
        self.nachrichten.append(nachricht)
        return {}

    def quit(self):
        return (221, b"bye")


@pytest.fixture()
def mail_fach(monkeypatch):
    """Eingerichteter Mailversand mit SMTP-Attrappe (Testnaht `VERBINDUNG`)."""
    from diakronos_app import mailversand

    smtp = FakeSMTP()
    monkeypatch.setattr(mailversand, "VERBINDUNG", smtp, raising=False)
    monkeypatch.setattr(
        mailversand,
        "einstellungen_lesen",
        lambda: mailversand.Einstellungen(
            host="smtp.example.org",
            port=587,
            sicherheit="starttls",
            absender=EMPFAENGER,
            absender_name="Gemeinde Musterhausen",
        ),
    )
    setze_setting("website_kontakt_empfaenger", EMPFAENGER)
    return smtp


@pytest.fixture()
def ohne_empfaenger(mail_fach):
    """Mailversand steht, aber `WEBSITE_KONTAKT_EMPFAENGER` ist leer (K4)."""
    setze_setting("website_kontakt_empfaenger", "")
    return mail_fach


@pytest.fixture()
def client(fake_redis, patched_db, monkeypatch):
    """Gast-Client gegen die echte App (kein Cookie, keine Sitzung).

    `fake_redis` haengt auch die Bremse an den In-Memory-Store — ohne das
    zaehlten die Tests im Redis des laufenden Stacks (Kartenregel 11).
    """
    from diakronos_app.anmeldung import kontaktbremse

    monkeypatch.setattr(kontaktbremse, "_client", lambda: fake_redis)
    from fastapi.testclient import TestClient

    from diakronos_app.main import app

    c = TestClient(app)
    c.__enter__()
    c.headers["Origin"] = "http://testserver"
    yield c
    c.__exit__(None, None, None)


def _post(client, daten=None, **kwargs):
    return client.post(PFAD, json=GUELTIG if daten is None else daten, **kwargs)


# ── K1: Endpunkt, Naht, Honeypot ───────────────────────────────────────────


def test_gueltige_anfrage_sendet_genau_eine_mail(client, mail_fach):
    antwort = _post(client)
    assert antwort.status_code == 200, antwort.text
    assert antwort.json()["message"] == {"ok": True}
    assert len(mail_fach.nachrichten) == 1


def test_mail_traegt_empfaenger_betreff_absender_und_inhalt(client, mail_fach):
    _post(client)
    nachricht = mail_fach.nachrichten[0]
    assert nachricht["To"] == EMPFAENGER
    assert nachricht["Subject"] == kontakt.BETREFF
    # Reply-To ist die Adresse des Besuchers — nur nach bestandener Pruefung.
    assert ABSENDER_MAIL in str(nachricht["Reply-To"])
    text = nachricht.get_content()
    assert "Erika Beispiel" in text
    assert ABSENDER_MAIL in text
    assert GUELTIG["nachricht"] in text
    # Zeitpunkt steht im Text (Datum + Uhrzeit, deutsche Schreibweise).
    assert re.search(r"\d{2}\.\d{2}\.\d{4}", text)


def test_honeypot_gefuellt_sendet_nichts_und_antwortet_ok(client, mail_fach):
    assert kontakt.honeypot_gefuellt({"website": "http://spam.example.org"}) is True
    antwort = _post(client, {**GUELTIG, "website": "http://spam.example.org"})
    assert antwort.status_code == 200, antwort.text
    assert antwort.json()["message"] == {"ok": True}
    assert mail_fach.nachrichten == []


def test_honeypot_mit_nur_leerzeichen_gilt_als_gefuellt(client, mail_fach):
    """JEDER nicht-leere Wert ist „gefuellt" — auch ein Leerzeichen.

    Die Entscheidung ist billig zu pruefen und fuer den Menschen eindeutig:
    das Feld ist unsichtbar, niemand tippt dort ein Leerzeichen ein. Ein
    Skript, das „zur Sicherheit" eines setzt, ist kein Mensch.
    """
    assert kontakt.honeypot_gefuellt({"website": "   "}) is True
    assert kontakt.honeypot_gefuellt({"website": ""}) is False
    assert kontakt.honeypot_gefuellt({}) is False
    antwort = _post(client, {**GUELTIG, "website": "   "})
    assert antwort.status_code == 200, antwort.text
    assert antwort.json()["message"] == {"ok": True}
    assert mail_fach.nachrichten == []


def test_honeypot_greift_vor_der_validierung(client, mail_fach):
    """Ein Bot mit Muell im Honeypot soll kein Feld-Feedback bekommen."""
    antwort = _post(client, {"name": "", "email": "keine-adresse", "nachricht": "x",
                             "einwilligung": False, "website": "bot"})
    assert antwort.status_code == 200, antwort.text
    assert mail_fach.nachrichten == []


@pytest.mark.parametrize("pfad", [PFAD, PFAD_VOLL, PFAD_DIAKRONOS])
def test_endpunkt_ist_unter_allen_registrierten_pfaden_erreichbar(client, mail_fach, pfad):
    """WEB-9b baut das Formular gegen den Frappe-Pfad — alle muessen gehen."""
    antwort = client.post(pfad, json=GUELTIG)
    assert antwort.status_code == 200, antwort.text
    assert len(mail_fach.nachrichten) == 1


# ── K2: Validierung ────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "aenderung, feld",
    [
        ({"name": ""}, "name"),
        ({"name": "   "}, "name"),
        ({"name": "x" * 101}, "name"),
        ({"email": ""}, "email"),
        ({"email": "keine-adresse"}, "email"),
        ({"email": "a@" + "b" * 250 + ".de"}, "email"),
        ({"email": "erika@example.org\r\nBcc: fremd@example.org"}, "email"),
        ({"email": "erika@example.org\nX-Boese: 1"}, "email"),
        ({"nachricht": "zu kurz"}, "nachricht"),
        ({"nachricht": "x" * 5001}, "nachricht"),
        ({"einwilligung": False}, "einwilligung"),
        ({"einwilligung": "true"}, "einwilligung"),
        ({"einwilligung": 1}, "einwilligung"),
    ],
)
def test_ungueltige_eingabe_gibt_400_mit_feldmeldung(client, mail_fach, aenderung, feld):
    antwort = _post(client, {**GUELTIG, **aenderung})
    assert antwort.status_code == 400, antwort.text
    daten = antwort.json()
    # Generische Meldung je Feld, keine Stacktraces/Interna (SEC-7/8).
    assert daten["felder"] == {feld: daten["felder"][feld]}
    assert daten["felder"][feld].strip()
    assert "Traceback" not in antwort.text
    assert mail_fach.nachrichten == []


def test_fehlende_felder_geben_400(client, mail_fach):
    antwort = client.post(PFAD, json={"name": "Erika"}, headers={"Origin": "http://testserver"})
    assert antwort.status_code == 400, antwort.text
    felder = antwort.json()["felder"]
    assert set(felder) == {"email", "nachricht", "einwilligung"}
    assert mail_fach.nachrichten == []


def test_kein_json_gibt_400(client, mail_fach):
    antwort = client.post(PFAD, content=b"name=Erika",
                          headers={"Content-Type": "text/plain", "Origin": "http://testserver"})
    assert antwort.status_code == 400, antwort.text
    assert mail_fach.nachrichten == []


def test_grenzlaengen_sind_erlaubt(client, mail_fach):
    antwort = _post(client, {**GUELTIG, "name": "n" * 100, "nachricht": "m" * 10})
    assert antwort.status_code == 200, antwort.text
    antwort = _post(client, {**GUELTIG, "nachricht": "m" * 5000})
    assert antwort.status_code == 200, antwort.text
    assert len(mail_fach.nachrichten) == 2


# ── K3: Schutz ─────────────────────────────────────────────────────────────


@pytest.mark.parametrize("methode", ["get", "put", "patch", "delete"])
def test_nur_post(client, mail_fach, methode):
    antwort = getattr(client, methode)(PFAD)
    assert antwort.status_code in (403, 405), antwort.text
    assert mail_fach.nachrichten == []


def test_fremde_herkunft_gibt_403(client, mail_fach):
    antwort = _post(client, headers={"Origin": "https://fremde-seite.example.net"})
    assert antwort.status_code == 403, antwort.text
    assert mail_fach.nachrichten == []


def test_referer_statt_origin_wird_geprueft(client, mail_fach):
    antwort = _post(
        client,
        headers={"Origin": "", "Referer": "https://fremde-seite.example.net/formular"},
    )
    assert antwort.status_code == 403, antwort.text
    assert mail_fach.nachrichten == []


def test_referer_der_eigenen_domain_ist_erlaubt(client, mail_fach):
    antwort = _post(
        client,
        headers={"Origin": "", "Referer": "http://testserver/kontakt"},
    )
    assert antwort.status_code == 200, antwort.text
    assert len(mail_fach.nachrichten) == 1


def test_ohne_herkunft_gibt_403(client, mail_fach):
    """Ohne Origin UND ohne Referer ist die Herkunft nicht belegt (fail closed)."""
    antwort = _post(client, headers={"Origin": ""})
    assert antwort.status_code == 403, antwort.text
    assert mail_fach.nachrichten == []


def test_ratenbegrenzung_je_adresse_ist_429(client, mail_fach, monkeypatch):
    setze_setting("website_kontakt_max_ip", 5)
    setze_setting("website_kontakt_max_gesamt", 50)
    codes = [_post(client).status_code for _ in range(6)]
    assert codes[:5] == [200] * 5, codes
    assert codes[5] == 429, codes
    assert len(mail_fach.nachrichten) == 5


def test_ratenbegrenzung_gesamt_ist_429(client, mail_fach):
    """Das Gesamtfenster greift auch hinter einem Proxy (Adresse nicht zaehlbar).

    Hier wird NUR die Gesamtgrenze geprueft: die Adresse kommt aus dem
    Testserver (Loopback) und ist damit bewusst vom Adresszaehler ausgenommen —
    genau der Fall „alle Besucher sehen dieselbe Proxy-Adresse".
    """
    setze_setting("website_kontakt_max_ip", 5)
    setze_setting("website_kontakt_max_gesamt", 2)
    codes = [_post(client).status_code for _ in range(3)]
    assert codes == [200, 200, 429], codes
    assert len(mail_fach.nachrichten) == 2


def test_ratenbegrenzung_schont_den_honeypot_nicht(client, mail_fach, monkeypatch):
    """Auch Honeypot-Treffer zaehlen — sonst waere die Bremse gratis umgehbar."""
    setze_setting("website_kontakt_max_ip", 1)
    assert _post(client, {**GUELTIG, "website": "bot"}).status_code == 200
    assert _post(client).status_code == 429
    assert mail_fach.nachrichten == []


def test_header_injection_im_namen_erzeugt_keine_kopfzeilen(client, mail_fach):
    name = "Erika\r\nBcc: sammler@example.org"
    antwort = _post(client, {**GUELTIG, "name": name})
    # Entweder abgelehnt (400) oder bereinigt — nie ein zusaetzlicher Header.
    assert antwort.status_code in (200, 400), antwort.text
    for nachricht in mail_fach.nachrichten:
        assert "sammler@example.org" not in str(nachricht["Bcc"] or "")
        assert len(nachricht["Bcc"] or []) == 0
        assert "\r" not in str(nachricht["Subject"])
        assert "\n" not in str(nachricht["Subject"])
        assert "Bcc" not in str(nachricht["Subject"])


def test_umbrueche_in_der_nachricht_bleiben_text(client, mail_fach):
    nachricht = "Zeile eins\r\nBcc: sammler@example.org\r\nZeile drei"
    antwort = _post(client, {**GUELTIG, "nachricht": nachricht})
    assert antwort.status_code == 200, antwort.text
    mail = mail_fach.nachrichten[0]
    assert list(mail["Bcc"] or []) == []
    assert "Zeile drei" in mail.get_content()


# ── K4: Empfaenger fehlt, Fehler, Datenschutz ──────────────────────────────


def test_ohne_empfaenger_gibt_503(client, ohne_empfaenger):
    antwort = _post(client)
    assert antwort.status_code == 503, antwort.text
    assert "nicht eingerichtet" in antwort.json()["message"].lower()
    assert ohne_empfaenger.nachrichten == []


def test_mailfehler_gibt_503_ohne_internum(client, mail_fach):
    mail_fach.scheitern = MailVersandFehler("Server sagt: 550 abgelehnt", art="abgelehnt")
    antwort = _post(client)
    assert antwort.status_code == 503, antwort.text
    assert "550" not in antwort.text


def test_nichts_wird_in_der_datenbank_gespeichert(client, mail_fach, patched_db):
    """KEINE Speicherung von Anfragen — die Karte sagt das ausdruecklich."""
    from sqlalchemy import inspect as sa_inspect, text

    engine = patched_db.kw["bind"]
    tabellen = sa_inspect(engine).get_table_names()

    def _zaehle() -> dict[str, int]:
        with engine.connect() as conn:
            return {t: conn.execute(text(f'SELECT COUNT(*) FROM "{t}"')).scalar()
                    for t in tabellen}

    vorher = _zaehle()
    assert _post(client).status_code == 200
    assert _zaehle() == vorher


def test_log_enthaelt_keine_inhalte(client, mail_fach, caplog):
    caplog.set_level(logging.DEBUG)
    _post(client)
    text = "\n".join(rec.getMessage() for rec in caplog.records)
    assert GUELTIG["nachricht"] not in text
    assert ABSENDER_MAIL not in text
    assert "Erika Beispiel" not in text
    assert "Kontaktmail" in text


def test_log_nennt_bei_fehler_nur_den_typ(client, mail_fach, monkeypatch, caplog):
    caplog.set_level(logging.DEBUG)

    # Der Fehler entsteht im Versand, NICHT in der Benachrichtigung — der
    # Testfall soll „Versand scheitert" pruefen, nicht „sende() wirft".
    mail_fach.scheitern = MailVersandFehler("Server sagt: 550 abgelehnt", art="abgelehnt")
    _post(client)
    text = "\n".join(rec.getMessage() for rec in caplog.records)
    assert "MailVersandFehler" in text
    assert ABSENDER_MAIL not in text
    assert GUELTIG["nachricht"] not in text


# ── Praefix (DIAKRONOS_BASE_PATH) ──────────────────────────────────────────


@pytest.fixture()
def mit_praefix(monkeypatch):
    """Baut die Anwendung mit `/diakronos` und dessen EIGENEM Client.

    BS-1c: `patched_db` und die Bremse-Attrappe gelten AUCH hier — sonst
    spraeche dieser Client die echte `database_url` an (Kartenregel 11).
    BS-1bc: die Einstellung wird im `finally` ZURUECKGESTELLT. Ohne das blieb
    `diakronos_base_path == "/diakronos"` nach diesem Test stehen, und
    `test_web5a_base_path.py::test_default_ist_leer_und_aendert_nichts`
    scheiterte in der Vollsuite (isoliert gruen) — ein Test, der eine globale
    Einstellung setzt, muss sie zurueckgeben.
    """
    from fastapi.testclient import TestClient

    from diakronos_app import base_path
    from diakronos_app.main import erstelle_app
    from diakronos_app.settings import settings

    alt = base_path.aktiver_praefix()
    alt_wert = settings.diakronos_base_path
    # WEB-5a: der Praefix kommt aus der Einstellung — hier fuer die Dauer des
    # Tests gesetzt (der Prozess-Praefix wird danach zurueckgestellt).
    setze_setting("diakronos_base_path", "/diakronos")
    try:
        app = erstelle_app()
        c = TestClient(app)
        c.__enter__()
        c.headers["Origin"] = "http://testserver"
        yield c
        c.__exit__(None, None, None)
    finally:
        setze_setting("diakronos_base_path", alt_wert)
        base_path.setze_praefix(alt)


def test_endpunkt_mit_praefix(mit_praefix, mail_fach, fake_redis, patched_db):
    antwort = mit_praefix.post("/diakronos" + PFAD, json=GUELTIG)
    assert antwort.status_code == 200, antwort.text
    assert len(mail_fach.nachrichten) == 1


def test_endpunkt_ohne_praefix_ist_404_wenn_praefix_gesetzt(mit_praefix, mail_fach):
    antwort = mit_praefix.post(PFAD, json=GUELTIG)
    assert antwort.status_code == 404, antwort.text
    assert mail_fach.nachrichten == []


# ── K5: Doku ───────────────────────────────────────────────────────────────


def test_betriebsanleitung_hat_den_abschnitt():
    """Die Einrichtung muss dort stehen, wo ein Betreiber nachsieht.

    SEC-11c (R4): `docs/` steht in `.dockerignore` und ist im App-Image NICHT
    vorhanden. Der Test las die Datei mit einem festen Pfad und brach dort mit
    `FileNotFoundError` ab — die Suite war im Image rot, obwohl der Inhalt in
    Ordnung ist. Er verhaelt sich jetzt wie `test_sec4_waechter` und
    `test_login3_doku_caldav`: liegt `docs/` nicht vor, wird er mit Begruendung
    UEBERSPRUNGEN (nie still bestanden), statt den Lauf zu reissen.
    """
    anleitung = Path(__file__).resolve().parents[2] / "docs" / "BETRIEBSANLEITUNG.md"
    if not anleitung.is_file():
        pytest.skip(
            "docs/ ist im Image nicht vorhanden (.dockerignore) — die Pruefung "
            f"der Betriebsdoku entfaellt; erwartet unter {anleitung}"
        )
    text = anleitung.read_text(encoding="utf-8")
    assert "WEBSITE_KONTAKT_EMPFAENGER" in text
    assert "Kontaktformular" in text
    # Datenschutz-Hinweis: Daten gehen nur per Mail weiter, nichts in der DB.
    assert "nicht gespeichert" in text.lower() or "keine Speicherung" in text.lower()


@pytest.mark.parametrize("pfad", [
    "/api/method/website.kontakt_senden",
    "/api/method/kontakt.kontakt_senden",
    "/api/method/diakronos.diakronos.api.website.kontakt_senden",
])
def test_integration_kontakt_ohne_sitzungs_csrf(pfad, monkeypatch):
    """Integration (Orchestrator): angemeldete Besucher dürfen das Website-Formular
    nutzen — der Endpunkt hat eigene Herkunftsprüfung, keine Sitzungs-CSRF."""
    from diakronos_app.frappe_compat.auth_middleware import ist_csrf_ausgenommen
    assert ist_csrf_ausgenommen(pfad) is True


@pytest.mark.parametrize("pfad", ["/api/method/website.kontakt_senden_x", "/api/method/x.kontakt_senden"])
def test_integration_kontakt_ausnahme_ist_exakt(pfad):
    from diakronos_app.frappe_compat.auth_middleware import ist_csrf_ausgenommen
    assert ist_csrf_ausgenommen(pfad) is False
