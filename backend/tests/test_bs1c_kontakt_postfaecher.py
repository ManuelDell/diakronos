"""BS-1c — Kontaktformular: mehrere Postfaecher + Herkunft Primo.

Die Karte verlangt Test-vorher-rot. Diese Datei deckt die vier Pflichtpunkte
gegen den in WEB-10 gebauten Endpunkt `website.kontakt_senden` ab:

  (K1) Optionales Feld ``postfach`` (Slug). Fehlt es: Postfach ``standard``
       bzw. das erste AKTIVE nach ``sortierung``, danach ohne Zeilen der
       Rueckfall auf ``WEBSITE_KONTAKT_EMPFAENGER``. Unbekannter oder
       inaktiver Slug -> **400** (generisch, ohne Kandidatenliste). Die
       Ziel-E-Mail-Adresse steht in KEINER Antwort.
  (K2) ``website.oeffentlich.postfaecher`` -> ``[{slug, bezeichnung}]`` der
       AKTIVEN Postfaecher, ohne E-Mail-Adresse (allow_guest, GET).
  (K3) Optionales Feld ``betreff_zusatz`` (max. 100, keine Zeilenumbrueche)
       wird an den festen Betreff gehaengt: ``Kontaktformular Website - …``.
       Ein Zusatz mit ``\\r\\n`` fuehrt zu **400** und KEINEM Versand; ein
       Zusatz aus reinen Steuerzeichen ebenso.
  (K4) Herkunft: zusaetzlich zur eigenen Domain ist die Herkunft aus
       ``PRIMO_PUBLIC_URL`` zugelassen (falls abweichend); Antworten an genau
       diese Herkunft tragen ``Access-Control-Allow-Origin`` — ohne
       ``Access-Control-Allow-Credentials``. OPTIONS (Preflight) auf denselben
       Pfad antwortet 204 mit den CORS-Kopfzeilen. Fremde Herkunft bleibt 403,
       Honeypot, Bremse und die CSRF-Ausnahme aus WEB-10 unveraendert.

**Netz**: ``--network none`` (Kartenregel 11). Mail geht ueber die Testnaht
``mailversand.VERBINDUNG`` (Fake-SMTP), Redis ueber den ``fake_redis``-Stub,
DB ueber ``patched_db``. Kein Test beruehrt ``settings.database_url`` und
keiner spricht einen echten Host an.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import diakronos_app.api  # noqa: F401 — registriert alle portierten Endpunkte
from diakronos_app.settings import settings
from diakronos_app.website import kontakt

PFAD = "/api/method/website.kontakt_senden"
PFAD_OEFFENTLICH = "/api/method/website.oeffentlich.postfaecher"

EMPFAENGER = "kontakt@gemeinde.example.org"
ABSENDER_MAIL = "besucher@example.org"
PRIMO_PUBLIC = "https://website.example.org"

GUELTIG = {
    "name": "Erika Beispiel",
    "email": ABSENDER_MAIL,
    "nachricht": "Bitte melden Sie sich bei mir wegen des Gemeindefestes.",
    "einwilligung": True,
    "website": "",
}


def setze_setting(name: str, wert) -> None:
    """Setzt eine Einstellung fuer die Dauer des Tests (siehe WEB-10-Tests)."""
    object.__setattr__(settings, name, wert)


@pytest.fixture(autouse=True)
def _settings_zuruecksetzen():
    """Stellt alle von den Tests veraenderten Einstellungen wieder her."""
    namen = (
        "website_kontakt_empfaenger",
        "website_kontakt_max_ip",
        "website_kontakt_max_gesamt",
        "website_kontakt_fenster_sekunden",
        "website_kontakt_liste_max_ip",
        "website_kontakt_liste_max_gesamt",
        "primo_public_url",
        "primo_url",
        "diakronos_base_path",
        "behind_proxy",
    )
    alt = {name: getattr(settings, name) for name in namen}
    yield
    for name, wert in alt.items():
        object.__setattr__(settings, name, wert)


# ── Attrappen ──────────────────────────────────────────────────────────────


class FakeSMTP:
    """Minimaler SMTP-Ersatz mit derselben Schnittstelle wie `smtplib.SMTP`."""

    def __init__(self) -> None:
        self.nachrichten: list = []

    def ehlo(self):
        return (250, b"ok")

    def has_extn(self, name):
        return str(name).lower() == "starttls"

    def starttls(self, context=None):
        return (220, b"ok")

    def login(self, benutzer, passwort):
        return (235, b"ok")

    def send_message(self, nachricht):
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
    # Ohne eigene Primo-Adresse ist die eigene Domain die einzige Herkunft;
    # Prufungen auf die Primo-Herkunft setzen die Einstellung selbst.
    setze_setting("primo_public_url", "")
    setze_setting("primo_url", "")
    return smtp


@pytest.fixture()
def client(fake_redis, patched_db, monkeypatch):
    """Gast-Client gegen die echte App (kein Cookie, keine Sitzung).

    `fake_redis` deckt nur die Sitzungs-/Benutzerschicht ab; die KONTAKTBREMSE
    haengt an ihrem eigenen Modul (`anmeldung.kontaktbremse._client`) und
    zaehlte sonst im echten Redis des Prozesses — genau der Fall, in dem die
    Tests einander die Grenze wegnehmen (WEB-10 macht das genauso).
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


def _postfaecher(session, *zeilen) -> None:
    """Legt Postfaecher an: ``(slug, bezeichnung, email, aktiv, sortierung)``."""
    from diakronos_app.models.website_kontakt import WebsiteKontaktPostfach

    sess = session()
    for slug, bezeichnung, email, aktiv, sortierung in zeilen:
        sess.add(
            WebsiteKontaktPostfach(
                slug=slug,
                bezeichnung=bezeichnung,
                email=email,
                aktiv=aktiv,
                sortierung=sortierung,
            )
        )
    sess.commit()
    sess.close()


STANDARD_ZEILEN = (
    ("allgemein", "Allgemeine Anfragen", "allgemein@gemeinde.example.org", True, 0),
    ("jugend", "Jugendarbeit", "jugend@gemeinde.example.org", True, 10),
    ("alt", "Stillgelegt", "alt@gemeinde.example.org", False, 20),
)


# ── K1: Postfach-Routing ───────────────────────────────────────────────────


def test_ohne_postfach_geht_die_mail_an_das_erste_aktive(client, mail_fach, patched_db):
    """Ohne Angabe gewinnt das erste AKTIVE Postfach nach `sortierung`."""
    _postfaecher(patched_db, *STANDARD_ZEILEN)
    antwort = _post(client)
    assert antwort.status_code == 200, antwort.text
    assert mail_fach.nachrichten[0]["To"] == "allgemein@gemeinde.example.org"


def test_sortierung_entscheidet_nicht_die_einfuegereihenfolge(client, mail_fach, patched_db):
    _postfaecher(
        patched_db,
        ("zuerst", "Zuerst eingefuegt", "zuerst@gemeinde.example.org", True, 50),
        ("vorne", "Sortierung 1", "vorne@gemeinde.example.org", True, 1),
    )
    assert _post(client).status_code == 200
    assert mail_fach.nachrichten[0]["To"] == "vorne@gemeinde.example.org"


def test_gewaehltes_postfach_bekommt_die_mail(client, mail_fach, patched_db):
    _postfaecher(patched_db, *STANDARD_ZEILEN)
    antwort = _post(client, {**GUELTIG, "postfach": "jugend"})
    assert antwort.status_code == 200, antwort.text
    assert mail_fach.nachrichten[0]["To"] == "jugend@gemeinde.example.org"


def test_inaktives_postfach_ist_unbekannt(client, mail_fach, patched_db):
    """Ein abgeschaltetes Postfach ist wie ein unbekannter Slug: 400."""
    _postfaecher(patched_db, *STANDARD_ZEILEN)
    antwort = _post(client, {**GUELTIG, "postfach": "alt"})
    assert antwort.status_code == 400, antwort.text
    assert "postfach" in antwort.json()["felder"]
    assert mail_fach.nachrichten == []


@pytest.mark.parametrize(
    "slug", ["gibtsnicht", "allgemein2", "ALLGEMEIN", " allgemein ", "a@b", 17, ["allgemein"]]
)
def test_unbekannter_postfach_slug_ist_400_ohne_kandidatenliste(
    slug, client, mail_fach, patched_db
):
    """Generische Meldung (SEC-7/8): kein Hinweis auf vorhandene Slugs."""
    _postfaecher(patched_db, *STANDARD_ZEILEN)
    antwort = _post(client, {**GUELTIG, "postfach": slug})
    if slug == " allgemein ":  # Leerraum wird getrimmt — das ist derselbe Slug
        assert antwort.status_code == 200, antwort.text
        return
    assert antwort.status_code == 400, antwort.text
    meldung = antwort.json()["felder"]["postfach"]
    assert meldung.strip()
    assert "jugend" not in meldung and "allgemein" not in meldung
    assert "Traceback" not in antwort.text
    assert mail_fach.nachrichten == []


def test_ohne_zeile_gilt_das_postfach_standard(client, mail_fach):
    """Abwaertskompatibel zu WEB-10: ohne Tabelle gilt `standard`."""
    antwort = _post(client, {**GUELTIG, "postfach": "standard"})
    assert antwort.status_code == 200, antwort.text
    assert mail_fach.nachrichten[0]["To"] == EMPFAENGER
    # Und ohne Feld genauso.
    assert _post(client).status_code == 200
    assert mail_fach.nachrichten[1]["To"] == EMPFAENGER


def test_leerer_postfach_wert_zaehlt_wie_ohne_angabe(client, mail_fach, patched_db):
    _postfaecher(patched_db, *STANDARD_ZEILEN)
    antwort = _post(client, {**GUELTIG, "postfach": ""})
    assert antwort.status_code == 200, antwort.text
    assert mail_fach.nachrichten[0]["To"] == "allgemein@gemeinde.example.org"


def test_ohne_aktives_postfach_ist_der_endpunkt_nicht_eingerichtet(client, mail_fach, patched_db):
    """Zeilen vorhanden, aber keine aktiv: 503 — kein stiller Rückfall."""
    _postfaecher(patched_db, ("alt", "Stillgelegt", "alt@gemeinde.example.org", False, 0))
    antwort = _post(client)
    assert antwort.status_code == 503, antwort.text
    assert mail_fach.nachrichten == []


def test_zieladresse_steht_in_keiner_antwort(client, mail_fach, patched_db):
    """G1: E-Mail-Adressen der Postfaecher werden nie an den Client gegeben."""
    _postfaecher(patched_db, *STANDARD_ZEILEN)
    antworten = [
        _post(client),
        _post(client, {**GUELTIG, "postfach": "jugend"}),
        _post(client, {**GUELTIG, "postfach": "alt"}),
        _post(client, {**GUELTIG, "postfach": "gibtsnicht"}),
        client.get(PFAD_OEFFENTLICH),
    ]
    for antwort in antworten:
        for zeile in STANDARD_ZEILEN:
            assert zeile[2] not in antwort.text, antwort.text
        assert EMPFAENGER not in antwort.text, antwort.text
        assert "@gemeinde.example.org" not in antwort.text, antwort.text


def test_postfach_geht_nicht_in_die_mail_als_kopfzeile(client, mail_fach, patched_db):
    """Der Slug ist eine Kennung — er landet NICHT in Betreff oder Adressteil."""
    _postfaecher(patched_db, *STANDARD_ZEILEN)
    _post(client, {**GUELTIG, "postfach": "jugend"})
    nachricht = mail_fach.nachrichten[0]
    assert nachricht["Subject"] == kontakt.BETREFF
    assert "jugend" not in str(nachricht["Subject"])


# ── K2: oeffentliche Postfach-Liste ────────────────────────────────────────


def test_oeffentliche_liste_traegt_slug_und_bezeichnung(client, patched_db):
    from diakronos_app.frappe_compat.registry import options_for

    _postfaecher(patched_db, *STANDARD_ZEILEN)
    antwort = client.get(PFAD_OEFFENTLICH)
    assert antwort.status_code == 200, antwort.text
    assert antwort.json()["message"] == {
        "postfaecher": [
            {"slug": "allgemein", "bezeichnung": "Allgemeine Anfragen"},
            {"slug": "jugend", "bezeichnung": "Jugendarbeit"},
        ]
    }
    # Oeffentlicher Endpunkt: Gast erlaubt, nur lesend.
    fn = kontakt.postfaecher_oeffentlich
    assert options_for(fn).get("allow_guest") is True
    assert options_for(fn).get("methods") == ("GET",)


def test_oeffentliche_liste_ohne_zeile_zeigt_den_rueckfall(client, mail_fach):
    antwort = client.get(PFAD_OEFFENTLICH)
    assert antwort.status_code == 200, antwort.text
    assert antwort.json()["message"] == {
        "postfaecher": [{"slug": "standard", "bezeichnung": "Allgemein"}]
    }


def test_oeffentliche_liste_ist_leer_ohne_einrichtung(client, mail_fach):
    setze_setting("website_kontakt_empfaenger", "")
    antwort = client.get(PFAD_OEFFENTLICH)
    assert antwort.status_code == 200, antwort.text
    assert antwort.json()["message"] == {"postfaecher": []}


def test_oeffentliche_liste_ohne_aktives_postfach_ist_leer(client, patched_db):
    _postfaecher(patched_db, ("alt", "Stillgelegt", "alt@gemeinde.example.org", False, 0))
    antwort = client.get(PFAD_OEFFENTLICH)
    assert antwort.json()["message"] == {"postfaecher": []}


def test_oeffentliche_liste_nur_lesend(client, patched_db):
    _postfaecher(patched_db, *STANDARD_ZEILEN)
    assert client.post(PFAD_OEFFENTLICH, json={}).status_code in (403, 405)


# ── K3: Betreff-Zusatz ─────────────────────────────────────────────────────


def test_betreff_zusatz_wird_angehaengt(client, mail_fach):
    antwort = _post(client, {**GUELTIG, "betreff_zusatz": "Gemeindefest"})
    assert antwort.status_code == 200, antwort.text
    assert mail_fach.nachrichten[0]["Subject"] == f"{kontakt.BETREFF} - Gemeindefest"


def test_betreff_zusatz_laenge_100_ist_erlaubt(client, mail_fach):
    zusatz = "z" * 100
    assert _post(client, {**GUELTIG, "betreff_zusatz": zusatz}).status_code == 200
    assert mail_fach.nachrichten[0]["Subject"] == f"{kontakt.BETREFF} - {zusatz}"


@pytest.mark.parametrize(
    "zusatz",
    [
        "z" * 101,
        "Gemeindefest\r\nBcc: sammler@example.org",
        "Gemeindefest\nX-Boese: 1",
        "\r\n",
        "\x00",
        # BS-1c2 (F6): die VOLLE Steuerzeichenmenge, nicht nur Zeilenumbrueche.
        "Gemeindefest\tTab",
        "Gemeindefest\u2028Trenner",
        "Gemeindefest\u0085NEL",
        "Gemeindefest\x7f",
        "Gemeindefest\x1f",
        "Gemeindefest\x08",
        "Gemeindefest\u2029",
    ],
)
def test_kaputter_betreff_zusatz_wird_abgelehnt(zusatz, client, mail_fach):
    """Zeilenumbruch/Steuerzeichen/zu lang: 400 und KEIN Versand (K3/F6)."""
    antwort = _post(client, {**GUELTIG, "betreff_zusatz": zusatz})
    assert antwort.status_code == 400, antwort.text
    assert "betreff_zusatz" in antwort.json()["felder"]
    assert mail_fach.nachrichten == []


def test_ohne_betreff_zusatz_bleibt_der_betreff_fest(client, mail_fach):
    _post(client)
    assert mail_fach.nachrichten[0]["Subject"] == kontakt.BETREFF


def test_betreff_zusatz_erzeugt_keine_zusatz_kopfzeilen(client, mail_fach):
    antwort = _post(client, {**GUELTIG, "betreff_zusatz": "Test"})
    assert antwort.status_code == 200, antwort.text
    nachricht = mail_fach.nachrichten[0]
    assert list(nachricht["Bcc"] or []) == []
    assert "\r" not in str(nachricht["Subject"])
    assert "\n" not in str(nachricht["Subject"])


# ── K4: Herkunft Primo + CORS ──────────────────────────────────────────────


def test_primo_herkunft_wird_angenommen(client, mail_fach):
    setze_setting("primo_public_url", PRIMO_PUBLIC)
    antwort = _post(client, headers={"Origin": PRIMO_PUBLIC})
    assert antwort.status_code == 200, antwort.text
    assert antwort.headers["access-control-allow-origin"] == PRIMO_PUBLIC
    assert "access-control-allow-credentials" not in antwort.headers
    assert len(mail_fach.nachrichten) == 1


def test_eigene_herkunft_bekommt_kein_cors_fuer_primo(client, mail_fach):
    """Antworten der eigenen Herkunft brauchen keinen CORS-Kopf."""
    setze_setting("primo_public_url", PRIMO_PUBLIC)
    antwort = _post(client)
    assert antwort.status_code == 200, antwort.text
    assert "access-control-allow-origin" not in antwort.headers


def test_primo_herkunft_mit_pfad_und_port_zaehlt(client, mail_fach):
    setze_setting("primo_public_url", PRIMO_PUBLIC + "/")
    antwort = _post(client, headers={"Origin": PRIMO_PUBLIC})
    assert antwort.status_code == 200, antwort.text


def test_fremde_herkunft_bleibt_403_ohne_cors(client, mail_fach):
    setze_setting("primo_public_url", PRIMO_PUBLIC)
    antwort = _post(client, headers={"Origin": "https://fremde-seite.example.net"})
    assert antwort.status_code == 403, antwort.text
    assert "access-control-allow-origin" not in antwort.headers
    assert mail_fach.nachrichten == []


def test_primo_referer_ohne_origin_ist_erlaubt(client, mail_fach):
    setze_setting("primo_public_url", PRIMO_PUBLIC)
    antwort = _post(
        client, headers={"Origin": "", "Referer": PRIMO_PUBLIC + "/kontakt"}
    )
    assert antwort.status_code == 200, antwort.text
    # Ohne `Origin` schickt der Browser keinen CORS-Bedarf — kein Kopf noetig,
    # aber auch nicht schaedlich; er darf fehlen.
    assert antwort.headers.get("access-control-allow-origin") in (None, PRIMO_PUBLIC)


def test_preflight_auf_dem_kontaktpfad(client, mail_fach):
    setze_setting("primo_public_url", PRIMO_PUBLIC)
    antwort = client.options(
        PFAD,
        headers={
            "Origin": PRIMO_PUBLIC,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert antwort.status_code in (200, 204), antwort.text
    assert antwort.headers["access-control-allow-origin"] == PRIMO_PUBLIC
    assert "POST" in antwort.headers["access-control-allow-methods"]
    assert "access-control-allow-credentials" not in antwort.headers
    kopf = antwort.headers.get("access-control-allow-headers", "").lower()
    assert "content-type" in kopf
    assert mail_fach.nachrichten == []


def test_preflight_von_fremder_herkunft_ist_403(client, mail_fach):
    setze_setting("primo_public_url", PRIMO_PUBLIC)
    antwort = client.options(
        PFAD,
        headers={
            "Origin": "https://fremde-seite.example.net",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert antwort.status_code == 403, antwort.text
    assert antwort.headers.get("access-control-allow-origin") is None


def test_preflight_verlangt_keinen_kontakt(client, mail_fach):
    """Der Preflight ist ein GET-artiger Aufruf: Bremse/Honeypot greifen nicht."""
    setze_setting("primo_public_url", PRIMO_PUBLIC)
    setze_setting("website_kontakt_max_ip", 1)
    for _ in range(3):
        antwort = client.options(
            PFAD,
            headers={"Origin": PRIMO_PUBLIC, "Access-Control-Request-Method": "POST"},
        )
        assert antwort.status_code in (200, 204), antwort.text
    assert mail_fach.nachrichten == []


def test_herkunft_funktion_kennt_beide_domains(monkeypatch):
    """`herkunft_ist_eigen` nimmt die eigene UND die Primo-Herkunft an (K4/F2)."""
    from types import SimpleNamespace

    setze_setting("primo_public_url", PRIMO_PUBLIC)

    def anfrage(origin: str, host: str = "diakronos.example.org", schema: str = "https"):
        return SimpleNamespace(
            headers={"host": host, "origin": origin},
            url=SimpleNamespace(scheme=schema),
        )

    assert kontakt.herkunft_ist_eigen(anfrage("https://diakronos.example.org")) is True
    assert kontakt.herkunft_ist_eigen(anfrage(PRIMO_PUBLIC)) is True
    assert kontakt.herkunft_ist_eigen(anfrage("https://fremde-seite.example.net")) is False
    assert kontakt.herkunft_ist_eigen(anfrage("null")) is False
    assert kontakt.herkunft_ist_eigen(anfrage("")) is False
    # F2: EXAKT — falsches Schema zum eigenen Host ist keine eigene Herkunft.
    assert kontakt.herkunft_ist_eigen(anfrage("http://diakronos.example.org")) is False
    # F2: Standardport in der Anfrage stoert nicht (Normalisierung).
    assert kontakt.herkunft_ist_eigen(anfrage("https://diakronos.example.org:443")) is True


def test_honeypot_und_bremse_bleiben_unveraendert(client, mail_fach, patched_db):
    """K4 laesst alles andere unveraendert: Bot bekommt 200 ohne Mail."""
    _postfaecher(patched_db, *STANDARD_ZEILEN)
    setze_setting("primo_public_url", PRIMO_PUBLIC)
    antwort = _post(client, {**GUELTIG, "website": "bot"}, headers={"Origin": PRIMO_PUBLIC})
    assert antwort.status_code == 200, antwort.text
    assert mail_fach.nachrichten == []


def test_bremse_gilt_auch_fuer_die_primo_herkunft(client, mail_fach):
    setze_setting("primo_public_url", PRIMO_PUBLIC)
    setze_setting("website_kontakt_max_ip", 2)
    setze_setting("website_kontakt_max_gesamt", 50)
    codes = [
        _post(client, headers={"Origin": PRIMO_PUBLIC}).status_code for _ in range(3)
    ]
    assert codes == [200, 200, 429], codes
    assert len(mail_fach.nachrichten) == 2


def test_herkunftsschranke_der_middleware_bleibt_ausgenommen(monkeypatch):
    """SEC-11/C4: der oeffentliche Website-Endpunkt bleibt von der
    Middleware-Schranke ausgenommen (er hat seine eigene Pruefung)."""
    from types import SimpleNamespace

    from diakronos_app.frappe_compat.auth_middleware import fremde_herkunft_abgewiesen

    request = SimpleNamespace(
        url=SimpleNamespace(path=PFAD),
        headers={"sec-fetch-site": "cross-site", "origin": PRIMO_PUBLIC},
    )
    assert fremde_herkunft_abgewiesen(request) is False


# ── BS-1c2: Nachbesserung (F1-F7) ──────────────────────────────────────────


def _middleware_abgewiesen(pfad: str, herkunft: str = "cross-site") -> bool:
    from types import SimpleNamespace

    from diakronos_app.frappe_compat.auth_middleware import fremde_herkunft_abgewiesen

    request = SimpleNamespace(
        url=SimpleNamespace(path=pfad),
        headers={"sec-fetch-site": herkunft, "origin": PRIMO_PUBLIC},
    )
    return fremde_herkunft_abgewiesen(request)


def test_f1_postfach_liste_ist_von_der_middleware_ausgenommen():
    """F1: die Liste steht in der EXAKTEN Ausnahmemenge — samt Aliassen."""
    for pfad in (
        "/api/method/website.oeffentlich.postfaecher",
        "/api/method/kontakt.postfaecher_oeffentlich",
        "/api/method/diakronos.diakronos.api.website.postfaecher_oeffentlich",
    ):
        assert _middleware_abgewiesen(pfad) is False, pfad
    # Das Formular bleibt ebenfalls ausgenommen (BS-1c).
    assert _middleware_abgewiesen(PFAD) is False


def test_f1_andere_oeffentliche_namen_bleiben_gesperrt():
    """F1 verschaerft nicht: fremde/unbekannte Namen bleiben abgewiesen."""
    for pfad in (
        "/api/method/website.oeffentlich.irgendwas",
        "/api/method/website.postfach_speichern",
        "/api/method/mitglieder.get_mitglieder_liste",
    ):
        assert _middleware_abgewiesen(pfad) is True, pfad


def test_f1_liste_von_primo_herkunft_antwortet_200(client, patched_db):
    """F1 + G4: cross-site-Aufruf aus der Primo-Herkunft bekommt die Liste."""
    setze_setting("primo_public_url", PRIMO_PUBLIC)
    _postfaecher(patched_db, *STANDARD_ZEILEN)
    antwort = client.get(
        PFAD_OEFFENTLICH,
        headers={
            "Origin": PRIMO_PUBLIC,
            "Sec-Fetch-Site": "cross-site",
            "Sec-Fetch-Mode": "cors",
        },
    )
    assert antwort.status_code == 200, antwort.text
    assert antwort.headers["access-control-allow-origin"] == PRIMO_PUBLIC
    assert antwort.json()["message"]["postfaecher"][0]["slug"] == "allgemein"


@pytest.mark.parametrize(
    "primo, origin",
    [
        # F2: falsches Schema ist eine fremde Herkunft.
        ("https://website.example.org", "http://website.example.org"),
        ("http://website.example.org", "https://website.example.org"),
        # F2: falscher Port ist eine fremde Herkunft.
        ("https://website.example.org:8443", "https://website.example.org"),
        ("https://website.example.org", "https://website.example.org:8443"),
    ],
)
def test_f2_falsches_schema_oder_falscher_port_ist_403(primo, origin, client, mail_fach):
    setze_setting("primo_public_url", primo)
    antwort = _post(client, headers={"Origin": origin})
    assert antwort.status_code == 403, antwort.text
    assert "access-control-allow-origin" not in antwort.headers
    assert mail_fach.nachrichten == []


def test_f2_positivtest_mit_pfad_in_primo_public_url(client, mail_fach):
    """F2: Pfad/Slash/Standardport in `PRIMO_PUBLIC_URL` stoeren nicht."""
    setze_setting("primo_public_url", "HTTPS://Website.Example.org:443/diakronos/")
    antwort = _post(client, headers={"Origin": "https://website.example.org"})
    assert antwort.status_code == 200, antwort.text
    # Zurueck kommt die NORMALISIERTE Herkunft — kein Pfad, kein Standardport.
    assert antwort.headers["access-control-allow-origin"] == "https://website.example.org"


def test_f2_normalisierung_ist_eine_funktion():
    """F2: eine Stelle normalisiert — Schema/Host klein, Port, Pfad."""
    norm = kontakt._normalisiere_herkunft  # noqa: SLF001
    assert norm("https://Example.ORG/pfad?x=1#f") == "https://example.org"
    assert norm("https://example.org:443") == "https://example.org"
    assert norm("http://example.org:80/") == "http://example.org"
    assert norm("https://example.org:8443/pfad") == "https://example.org:8443"
    assert norm("ftp://example.org") == ""
    assert norm("example.org") == ""
    assert norm("null") == ""
    assert norm("https://example.org:abc") == ""


def test_f3_preflight_ist_ausdruecklich_angemeldet():
    """F3: nur `preflight="self"` bekommt den Preflight — nicht die Gestalt."""
    from diakronos_app.frappe_compat import registry
    from diakronos_app.frappe_compat.router import _beantwortet_preflight_selbst

    assert registry.options_for(kontakt.kontakt_senden).get("preflight") == "self"
    assert _beantwortet_preflight_selbst(kontakt.kontakt_senden) is True

    async def anderer(request=None):  # async + request, aber NICHT angemeldet
        raise AssertionError("diese Funktion darf beim Preflight nicht laufen")

    # Bewusst OHNE `@whitelist`: der Dekorator traegt die Funktion ins Register
    # ein (und damit ins Inventar). Hier genuegt die Optionstabelle.
    async def _fremder_async_endpunkt(request=None):
        raise AssertionError("diese Funktion darf beim Preflight nicht laufen")

    registry._OPTIONS[id(_fremder_async_endpunkt)] = {  # noqa: SLF001
        "allow_guest": True,
        "methods": ("POST",),
    }
    try:
        assert _beantwortet_preflight_selbst(_fremder_async_endpunkt) is False
    finally:
        registry._OPTIONS.pop(id(_fremder_async_endpunkt), None)  # noqa: SLF001
    assert _beantwortet_preflight_selbst(anderer) is False


def test_f3_anderer_async_endpunkt_wird_bei_options_nicht_ausgefuehrt(client, mail_fach):
    """F3: OPTIONS auf einen fremden async-Endpunkt -> 204, Funktion laeuft NICHT.

    Registriert wird NUR ueber `registry._OPTIONS` (Optionen), NICHT ueber
    `_REGISTRY`: ein Eintrag im Register waere ein neuer Endpunkt und wuerde
    die SEC-11-Waechter (Inventar/whitelist.json) umstoßen. Fuer diesen Test
    genuegt die Optionstabelle — der Router loest den Pfad ueber das Register
    auf, die Preflight-Entscheidung haengt an `options_for`.
    """
    from diakronos_app.frappe_compat import registry

    aufgerufen: list[str] = []

    async def fremder_async_endpunkt(request=None):
        aufgerufen.append("ja")

    # `__module__`/`__name__` bestimmen die Register-Aliasse (`registry.
    # _register` → `modul.name`) und damit das Inventar. Der Testname selbst
    # (Kurzname `_fremder_async_endpunkt`) darf dort NIE auftauchen — sonst
    # stoesst der SEC-11-Waechter um. Deshalb vor der Registrierung umbenennen.
    fremder_async_endpunkt.__name__ = "fremder_async_endpunkt_bs1c2"
    fremder_async_endpunkt.__qualname__ = "fremder_async_endpunkt_bs1c2"
    fremder_async_endpunkt.__module__ = "bs1c2_test"

    pfad = "/api/method/bs1c2_test.fremder_async_endpunkt"
    registry._REGISTRY["bs1c2_test.fremder_async_endpunkt"] = fremder_async_endpunkt  # noqa: SLF001
    registry._OPTIONS[id(fremder_async_endpunkt)] = {  # noqa: SLF001
        "allow_guest": True,
        "methods": ("POST",),
    }
    try:
        antwort = client.options(
            pfad,
            headers={"Origin": "http://testserver", "Access-Control-Request-Method": "POST"},
        )
        # `_maybe_import` hat `nachregistrieren()` laufen lassen und dabei
        # Aliasse aus `__module__`/`__name__` gezogen — die wuerden die
        # SEC-11-Waechter (Inventar) umstossen. Rueckstand gezielt entfernen.
        for name, fn in list(registry._REGISTRY.items()):  # noqa: SLF001
            if fn is fremder_async_endpunkt:
                del registry._REGISTRY[name]  # noqa: SLF001
    finally:
        for name, fn in list(registry._REGISTRY.items()):  # noqa: SLF001
            if fn is fremder_async_endpunkt:
                del registry._REGISTRY[name]  # noqa: SLF001
        registry._OPTIONS.pop(id(fremder_async_endpunkt), None)  # noqa: SLF001
    assert antwort.status_code == 204, antwort.text
    assert aufgerufen == []
    assert "access-control-allow-origin" not in antwort.headers

def test_f4_vary_origin_auf_allen_kontakt_antworten(client, mail_fach):
    """F4: `Vary: Origin` IMMER — Liste, jeder Formular-Status, Preflight."""
    antworten = [
        client.get(PFAD_OEFFENTLICH),
        _post(client),
        _post(client, {**GUELTIG, "name": ""}),                      # 400
        _post(client, headers={"Origin": "https://fremde.example.net"}),  # 403
        client.options(PFAD, headers={"Origin": "http://testserver"}),
    ]
    for antwort in antworten:
        assert "origin" in antwort.headers.get("vary", "").lower(), (
            antwort.status_code,
            antwort.headers,
        )


def test_f4_vary_origin_auch_mit_primo_herkunft(client, mail_fach):
    setze_setting("primo_public_url", PRIMO_PUBLIC)
    antwort = client.get(PFAD_OEFFENTLICH, headers={"Origin": PRIMO_PUBLIC})
    assert antwort.headers["access-control-allow-origin"] == PRIMO_PUBLIC
    assert "origin" in antwort.headers.get("vary", "").lower()


def test_f5_liste_hat_einen_eigenen_bremseimer(client, mail_fach, patched_db):
    """F5: viele Listen-Abrufe sperren NICHT das Formular.

    BS-1bc/Regel 11: Die Adresse steht EXPLIZIT in `X-Forwarded-For` (mit
    `BEHIND_PROXY=1`), weil sie sonst aus dem Test-Peer kam — der ist Loopback
    und damit von der Adressbremse ausgenommen (dort steht der Proxy). Der
    Proxy-Fix ordnet ausserdem Adresse VOR gesamt: nach dem Limit zaehlt die
    Adresse weiter, GESAMT nicht mehr.
    """
    setze_setting("behind_proxy", True)
    setze_setting("website_kontakt_liste_max_ip", 2)
    setze_setting("website_kontakt_max_ip", 5)
    setze_setting("website_kontakt_liste_max_gesamt", 1000)
    adresse = {"X-Forwarded-For": "203.0.113.42"}
    codes = [
        client.get(PFAD_OEFFENTLICH, headers=adresse).status_code for _ in range(3)
    ]
    assert codes == [200, 200, 429], codes
    # Das Formular bleibt unberuehrt (eigener Eimer -> eigenes Kontingent).
    assert _post(client).status_code == 200


def test_f5_formular_bremse_sperrt_nicht_die_liste(client, mail_fach, patched_db):
    """F5: das Kontaktkontingent ist nicht das Listen-Kontingent."""
    setze_setting("website_kontakt_max_ip", 1)
    setze_setting("website_kontakt_liste_max_ip", 30)
    assert [_post(client).status_code for _ in range(2)] == [200, 429]
    assert client.get(PFAD_OEFFENTLICH).status_code == 200


def test_f5_liste_faellt_bei_ausfall_der_bremse_aus(client, monkeypatch):
    """F5/Fail closed: ohne Redis antwortet die Liste 503."""
    from diakronos_app.anmeldung import kontaktbremse

    def kaputt(ip, client=None):
        raise RuntimeError("kein Redis")

    monkeypatch.setattr(kontaktbremse, "pruefe_liste", kaputt)
    antwort = client.get(PFAD_OEFFENTLICH)
    assert antwort.status_code == 503, antwort.text
    assert "Traceback" not in antwort.text


def test_f7_kein_aktives_postfach_bleibt_503_und_liste_leer(client, mail_fach, patched_db):
    """F7 (Orchestrator-Entscheidung): abgeschaltet ist abgeschaltet."""
    _postfaecher(patched_db, ("alt", "Stillgelegt", "alt@gemeinde.example.org", False, 0))
    assert _post(client).status_code == 503
    assert _post(client, {**GUELTIG, "postfach": "alt"}).status_code == 400
    assert client.get(PFAD_OEFFENTLICH).json()["message"] == {"postfaecher": []}
    assert mail_fach.nachrichten == []


# ── BS-1bc: Proxy-Fix + Bremse der Liste (P) ───────────────────────────────


def test_bs1bc_proxy_formular_von_eigener_herkunft_wird_nicht_abgewiesen(
    client, mail_fach, patched_db
):
    """BS-1bc (Proxy-Fix): hinter TLS-Vorbau weist das EIGENE Formular nicht 403.

    Der Proxy (Eingang/nginx, NPM) fuehrt die Verbindung zum Backend ueber
    HTTP; der Browser meldet `https`. `request.url.scheme` ist dann `http`,
    `Origin` aber `https://<host>` — mit dem alten Code galt die eigene Seite
    als fremd und antwortete 403 (kein gefaelschtes `https` im Test: das
    Schema der Anfrage bleibt `http`, nur `X-Forwarded-Proto` und
    `BEHIND_PROXY` kommen dazu, genau wie im Betrieb).
    """
    _postfaecher(patched_db, *STANDARD_ZEILEN)
    setze_setting("behind_proxy", True)
    antwort = client.post(
        PFAD,
        json=GUELTIG,
        headers={
            "Origin": "https://diakronos.example.org",
            "Host": "diakronos.example.org",
            "X-Forwarded-Proto": "https",
        },
    )
    assert antwort.status_code == 200, antwort.text
    assert len(mail_fach.nachrichten) == 1


def test_bs1bc_ohne_behind_proxy_zaehlt_der_weiterleitungskopf_nicht(
    client, mail_fach, patched_db
):
    """Ohne `BEHIND_PROXY` bleibt `X-Forwarded-Proto` unbeachtet (fail closed).

    Der Kopf ist frei setzbar; ohne die Zusage ueber den Proxy darf ihn
    niemand ausnutzen, um `https` vorzutaeuschen.
    """
    _postfaecher(patched_db, *STANDARD_ZEILEN)
    setze_setting("behind_proxy", False)
    antwort = client.post(
        PFAD,
        json=GUELTIG,
        headers={
            "Origin": "https://diakronos.example.org",
            "Host": "diakronos.example.org",
            "X-Forwarded-Proto": "https",
        },
    )
    assert antwort.status_code == 403, antwort.text
    assert mail_fach.nachrichten == []


def test_bs1bc_fremde_herkunft_bleibt_auch_mit_proxy_403(
    client, mail_fach, patched_db
):
    """Der Proxy-Fix oeffnet KEINE fremde Herkunft."""
    _postfaecher(patched_db, *STANDARD_ZEILEN)
    setze_setting("behind_proxy", True)
    antwort = client.post(
        PFAD,
        json=GUELTIG,
        headers={
            "Origin": "https://fremde-seite.example.net",
            "Host": "diakronos.example.org",
            "X-Forwarded-Proto": "https",
        },
    )
    assert antwort.status_code == 403, antwort.text
    assert mail_fach.nachrichten == []


def test_bs1bc_bremse_liste_adresse_vor_gesamt(fake_redis, monkeypatch):
    """BS-1bc: erst die Adresse, dann global — ein gesperrter Client nicht global.

    Vorher lief GESAMT zuerst: ein Client, der seine Adressgrenze aufgebraucht
    hatte, verbrannte bei JEDEM weiteren Abruf zusaetzlich das
    Gesamtkontingent der Gemeinde und konnte die Liste fuer alle sperren.
    """
    from diakronos_app.anmeldung import kontaktbremse

    monkeypatch.setattr(kontaktbremse, "_client", lambda: fake_redis)
    setze_setting("website_kontakt_liste_max_ip", 2)
    setze_setting("website_kontakt_liste_max_gesamt", 10)

    adresse = "203.0.113.7"
    assert [kontaktbremse.pruefe_liste(adresse) for _ in range(2)] == [
        (True, ""),
        (True, ""),
    ]
    # Dritte Anfrage: Adresse am Limit, GESAMT bleibt bei 2.
    assert kontaktbremse.pruefe_liste(adresse)[0] is False
    stand = kontaktbremse.liste_zaehler_stand(adresse)
    assert stand == {"ip": 3, "gesamt": 2}, stand
    # Weitere Anfragen derselben Adresse ruehren GESAMT nicht an.
    for _ in range(5):
        assert kontaktbremse.pruefe_liste(adresse)[0] is False
    assert kontaktbremse.liste_zaehler_stand(adresse)["gesamt"] == 2
    # Eine ANDERE Adresse kommt weiterhin durch (Gesamtgrenze gilt).
    assert kontaktbremse.pruefe_liste("198.51.100.9") == (True, "")


def test_bs1bc_bremse_liste_gesamt_greift_weiterhin(fake_redis, monkeypatch):
    """Die Gesamtgrenze der Liste bleibt fuer wechselnde Adressen gueltig."""
    from diakronos_app.anmeldung import kontaktbremse

    monkeypatch.setattr(kontaktbremse, "_client", lambda: fake_redis)
    setze_setting("website_kontakt_liste_max_ip", 5)
    setze_setting("website_kontakt_liste_max_gesamt", 2)

    assert kontaktbremse.pruefe_liste("203.0.113.1")[0] is True
    assert kontaktbremse.pruefe_liste("203.0.113.2")[0] is True
    assert kontaktbremse.pruefe_liste("203.0.113.3") == (False, "gesamt")


def test_bs1bc_alle_postfaecher_inaktiv_und_empfaenger_gesetzt_ist_503(
    client, mail_fach, patched_db
):
    """BS-1bc: alle Postfaecher inaktiv + `WEBSITE_KONTAKT_EMPFAENGER` -> 503.

    Ein gesetzter Rueckfall-Empfaenger darf die Abschaltung NICHT aushebeln:
    die F7-Entscheidung („abgeschaltet ist abgeschaltet") gilt unabhaengig
    davon, ob eine Adresse konfiguriert ist.
    """
    _postfaecher(
        patched_db,
        ("alt", "Stillgelegt", "alt@gemeinde.example.org", False, 0),
        ("auch-aus", "Ebenfalls aus", "aus@gemeinde.example.org", False, 10),
    )
    setze_setting("website_kontakt_empfaenger", EMPFAENGER)
    antwort = _post(client)
    assert antwort.status_code == 503, antwort.text
    assert mail_fach.nachrichten == []


# ── Vertragsdoku ───────────────────────────────────────────────────────────


def test_betriebsanleitung_beschreibt_postfaecher_und_primo_herkunft():
    anleitung = Path(__file__).resolve().parents[2] / "docs" / "BETRIEBSANLEITUNG.md"
    text = anleitung.read_text(encoding="utf-8")
    assert "betreff_zusatz" in text
    assert "PRIMO_PUBLIC_URL" in text
    assert "postfaecher" in text
