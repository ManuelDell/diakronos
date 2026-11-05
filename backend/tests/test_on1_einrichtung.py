"""ON-1 — Einrichtungslink beim ersten Start + Seite „Administrator anlegen".

Was diese Datei festhaelt (Karte ON-1, Vorgaben E1–E5):

  E1  Kein Benutzer + kein ADMIN_EMAIL/ADMIN_PASSWORD -> beim Start entsteht
      ein Einrichtungs-Token; in der DB steht NUR sein SHA-256-Hash mit Ablauf;
      der Link steht im Startkasten. Der ADMIN_EMAIL-Weg bleibt unveraendert
      und erzeugt KEINEN Link.
  E2  Neuerzeugen von Hand (`neuer_einrichtungslink` / `python -m … link`)
      macht den alten Token ungueltig und wirkt nur ohne Benutzer.
  E3  GET: gueltig -> Seite „Administrator anlegen"; ungueltig/abgelaufen/
      schon eingerichtet -> „Link ungueltig" mit 404 und IDENTISCHEM Text
      (kein Orakel).
  E4  POST: Herkunft/Masken-Token (SEC-4), Ratenbegrenzung, Passwortregeln,
      Anlegen in EINER Transaktion (Benutzer + ADMIN_ROLES + Mitglied),
      Wettlauf, Sitzung aktiv, Weiterleitung in die App.
  E5  Logs: nie Token, nie Passwort.

Dazu: mit und ohne DIAKRONOS_BASE_PATH, und der Waechter aus ON-0a bleibt
gruen (keine Farbwerte in den neuen Seiten).
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timedelta

import pytest

from diakronos_app import base_path, einrichtung
from diakronos_app.models.einrichtung import EINRICHTUNG_TOKEN_NAME, EinrichtungToken

PASSWORT = "EinSicheres12"


# ── Helfer ─────────────────────────────────────────────────────────────────


@pytest.fixture()
def ohne_adminwerte(monkeypatch):
    """Keine Kopflinie-Installation: ADMIN_EMAIL/ADMIN_PASSWORD leer."""
    from diakronos_app.settings import settings as settings_obj

    monkeypatch.setattr(settings_obj, "admin_email", None)
    monkeypatch.setattr(settings_obj, "admin_password", None)
    return settings_obj


@pytest.fixture()
def basis(monkeypatch):
    """APP_BASE_URL fuer absolute Links (Kasten/Anzeige)."""
    from diakronos_app.settings import settings as settings_obj

    monkeypatch.setattr(settings_obj, "app_base_url", "https://gemeinde.example.org")
    return settings_obj


@pytest.fixture()
def client(patched_db, fake_redis):
    """TestClient der echten App (Router, Middleware, Breakern)."""
    from fastapi.testclient import TestClient

    from diakronos_app.main import app

    with TestClient(app) as c:
        yield c


def _zeilen(session_factory) -> list[EinrichtungToken]:
    sess = session_factory()
    try:
        return list(sess.query(EinrichtungToken).all())
    finally:
        sess.close()


def _zaehle_benutzer(session_factory) -> int:
    from diakronos_app.models.core import User

    sess = session_factory()
    try:
        return sess.query(User).count()
    finally:
        sess.close()


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _neuer_token(**kw) -> str:
    token, _bis = einrichtung.erzeuge_token(**kw)
    return token


def _formular(**abweichungen) -> dict:
    werte = {
        "vorname": "Mara",
        "nachname": "Beispiel",
        "email": "admin@gemeinde.example",
        "passwort": PASSWORT,
        "wiederholung": PASSWORT,
    }
    werte.update(abweichungen)
    return werte


# ── E1: Token beim Start ───────────────────────────────────────────────────


def test_token_wird_nur_als_hash_mit_ablauf_gespeichert(patched_db):
    """E1: 43 Zeichen, ~256 Bit; in der DB steht NUR der SHA-256-Hash."""
    token, bis = einrichtung.erzeuge_token()

    assert len(token) == einrichtung.TOKEN_LAENGE == 43
    assert token == token.strip()
    zeilen = _zeilen(patched_db)
    assert len(zeilen) == 1
    zeile = zeilen[0]
    assert zeile.name == EINRICHTUNG_TOKEN_NAME
    # Kein Klartext — weder der Token selbst noch ein Teil davon.
    assert zeile.token_hash == _hash(token)
    assert token not in (zeile.token_hash or "")
    # Ablauf: 7 Tage, in der Zukunft.
    jetzt = einrichtung._jetzt()
    assert zeile.gueltig_bis > jetzt
    assert abs((zeile.gueltig_bis - bis).total_seconds()) < 1
    assert (bis - zeile.angelegt_am).days == einrichtung.GUELTIG_TAGE == 7


def test_start_ohne_adminwerte_gibt_kasten_aus(patched_db, ohne_adminwerte, basis, capsys):
    """E1: ohne ADMIN_EMAIL/ADMIN_PASSWORD entsteht der Link samt Kasten."""
    from diakronos_app.erstinstallation import bootstrap_erstinstallation

    assert bootstrap_erstinstallation() is None

    ausgabe = capsys.readouterr().out
    zeilen = _zeilen(patched_db)
    assert len(zeilen) == 1
    # Der Kasten nennt den Link, den Befehl und den Hinweis (Entwurf 01).
    assert "Kein Systemadministrator vorhanden" in ausgabe
    assert "ERSTEINRICHTUNG" in ausgabe
    assert "Es gibt noch keinen Systemadministrator." in ausgabe
    assert "einmalig gültig, 7 Tage" in ausgabe
    assert "https://gemeinde.example.org/einrichtung/" in ausgabe
    assert "docker compose exec app diakronos einrichtungslink" in ausgabe
    assert "Ein neuer Link macht den alten ungültig." in ausgabe
    assert "bis ein Systemadministrator angelegt ist" in ausgabe
    # Kein Klartext ausserhalb des Kastens: der Token steht NICHT in der DB,
    # aber im Link des Kastens — genau EINMAL.
    token = re.search(r"/einrichtung/([A-Za-z0-9_\-]+)", ausgabe).group(1)
    assert len(token) == 43
    assert zeilen[0].token_hash == _hash(token)
    assert ausgabe.count(token) == 1


def test_start_ohne_app_base_url_zeigt_relativen_pfad_und_hinweis(
    patched_db, ohne_adminwerte, monkeypatch, capsys
):
    """E1: fehlende APP_BASE_URL -> relativer Pfad + ausdruecklicher Hinweis."""
    from diakronos_app.settings import settings as settings_obj

    monkeypatch.setattr(settings_obj, "app_base_url", "")
    from diakronos_app.erstinstallation import bootstrap_erstinstallation

    bootstrap_erstinstallation()
    ausgabe = capsys.readouterr().out
    assert "APP_BASE_URL ist nicht gesetzt" in ausgabe
    assert re.search(r"│\s+/einrichtung/[A-Za-z0-9_\-]{43}\b", ausgabe)
    # Kein absoluter Link (nur der Beispiel-Hinweis nennt eine Adresse).
    assert "example.org/einrichtung/" not in ausgabe


def test_start_mit_admin_email_bleibt_unveraendert(patched_db, monkeypatch, capsys):
    """E1: der ADMIN_EMAIL-Weg legt den Benutzer an — und erzeugt KEINEN Link."""
    from diakronos_app.models.core import User
    from diakronos_app.settings import settings as settings_obj

    monkeypatch.setattr(settings_obj, "admin_email", "chef@example.org")
    monkeypatch.setattr(settings_obj, "admin_password", "erst-geheim-123")
    from diakronos_app.erstinstallation import bootstrap_erstinstallation

    assert bootstrap_erstinstallation() == "chef@example.org"
    assert _zeilen(patched_db) == []
    assert "ERSTEINRICHTUNG" not in capsys.readouterr().out

    sess = patched_db()
    try:
        assert sess.get(User, "chef@example.org") is not None
    finally:
        sess.close()


def test_zweiter_start_macht_den_link_nicht_ungueltig(patched_db, ohne_adminwerte, capsys):
    """E1: app/worker/scheduler starten nacheinander — der Link bleibt gueltig."""
    from diakronos_app.erstinstallation import bootstrap_erstinstallation

    bootstrap_erstinstallation()
    token = re.search(r"/einrichtung/([A-Za-z0-9_\-]+)", capsys.readouterr().out).group(1)
    assert einrichtung.pruefe_token(token)

    bootstrap_erstinstallation()  # zweiter Start
    assert einrichtung.pruefe_token(token)
    assert len(_zeilen(patched_db)) == 1


def test_mit_benutzer_entsteht_kein_link(patched_db, ohne_adminwerte):
    """E1: existiert schon ein Benutzer, ist die Ersteinrichtung abgeschlossen."""
    from diakronos_app.erstinstallation import _startlink_ausgeben
    from diakronos_app.models.core import User

    sess = patched_db()
    try:
        sess.add(User(name="wer@example.org", email="wer@example.org", enabled=True))
        sess.commit()
    finally:
        sess.close()
    assert _startlink_ausgeben() is None
    assert _zeilen(patched_db) == []


# ── E2: Neuerzeugen ────────────────────────────────────────────────────────


def test_neuer_link_macht_alten_ungueltig(patched_db, ohne_adminwerte, capsys):
    from diakronos_app.erstinstallation import neuer_einrichtungslink

    alt = _neuer_token()
    assert einrichtung.pruefe_token(alt)
    neu = neuer_einrichtungslink(ausgeben=False)
    assert neu and neu != alt
    assert not einrichtung.pruefe_token(alt)
    assert einrichtung.pruefe_token(neu)
    assert len(_zeilen(patched_db)) == 1


def test_neuerzeugen_nach_einrichtung_wird_abgelehnt(patched_db, ohne_adminwerte, capsys):
    from diakronos_app.erstinstallation import neuer_einrichtungslink
    from diakronos_app.models.core import User

    sess = patched_db()
    try:
        sess.add(User(name="wer@example.org", email="wer@example.org", enabled=True))
        sess.commit()
    finally:
        sess.close()

    assert neuer_einrichtungslink(ausgeben=True) is None
    assert "Einrichtung bereits abgeschlossen." in capsys.readouterr().out
    assert _zeilen(patched_db) == []


def test_kommandozeile_link(patched_db, ohne_adminwerte, capsys):
    """E2: `python -m diakronos_app.einrichtung link` gibt den Kasten aus."""
    assert einrichtung._main(["link"]) == 0
    ausgabe = capsys.readouterr().out
    assert "ERSTEINERHICHTUNG" not in ausgabe  # Tippfehler-Waechter
    assert "ERSTEINRICHTUNG" in ausgabe
    assert einrichtung._main(["quatsch"]) == 2


# ── E3: GET ────────────────────────────────────────────────────────────────


def test_get_gueltig_zeigt_die_maske(client, patched_db, fake_redis):
    token = _neuer_token()
    antwort = client.get(f"/einrichtung/{token}")
    assert antwort.status_code == 200, antwort.text
    seite = antwort.text
    # Wortlaut aus dem Entwurf (Frame 02/13).
    assert "Willkommen bei Diakronos" in seite
    assert "Legen Sie den Systemadministrator an." in seite
    for feld in ("vorname", "nachname", "email", "passwort", "wiederholung"):
        assert f'name="{feld}"' in seite, feld
    assert "Administrator anlegen" in seite
    assert "Dieser Link ist danach ungültig." in seite
    assert "Mindestens 12 Zeichen, ein Großbuchstabe und eine Zahl." in seite
    # ON-0a: Token-Datei + Grund-Stylesheet, kein eigener Farbwert.
    assert "diakronos-tokens.css" in seite
    assert "diakronos-seiten.css" in seite
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b|\brgba?\s*\(", seite)
    # CSRF-Masken-Token im Formular (SEC-4).
    assert 'name="_csrf"' in seite
    assert 'name="_csrf" value=""' not in seite


def test_get_ungueltig_abgelaufen_und_eingerichtet_sind_identisch(
    client, patched_db, fake_redis
):
    """E3: kein Orakel — gleicher Status, gleicher Text."""
    ungueltig = client.get("/einrichtung/" + "A" * 43)
    assert ungueltig.status_code == 404

    alt = _neuer_token(jetzt=einrichtung._jetzt() - timedelta(days=8))
    abgelaufen = client.get(f"/einrichtung/{alt}")
    assert abgelaufen.status_code == 404

    from diakronos_app.models.core import User

    token = _neuer_token()
    sess = patched_db()
    try:
        sess.add(User(name="wer@example.org", email="wer@example.org", enabled=True))
        sess.commit()
    finally:
        sess.close()
    eingerichtet = client.get(f"/einrichtung/{token}")
    assert eingerichtet.status_code == 404

    assert ungueltig.text == abgelaufen.text == eingerichtet.text
    assert "Dieser Einrichtungslink ist nicht mehr gültig" in ungueltig.text
    assert "docker compose exec app diakronos einrichtungslink" in ungueltig.text
    assert "Zur Anmeldung" in ungueltig.text


def test_get_mit_praefix(patched_db, fake_redis, monkeypatch):
    """E3/WEB-5a: mit DIAKRONOS_BASE_PATH liegen Seite und Formularziel darunter.

    Der Praefix wird beim BAU der Anwendung gesetzt (`erstelle_app`) — ein
    `setze_praefix` allein haengt die Routen nicht um (dieselbe Regel wie in
    `test_on0b_schriften.py`).
    """
    from fastapi.testclient import TestClient

    from diakronos_app.main import erstelle_app
    from diakronos_app.settings import settings as settings_obj

    token = _neuer_token()
    alt = base_path.aktiver_praefix()
    monkeypatch.setattr(settings_obj, "diakronos_base_path", "/diakronos")
    try:
        with TestClient(erstelle_app()) as c:
            antwort = c.get(f"/diakronos/einrichtung/{token}")
            assert antwort.status_code == 200, antwort.text
            assert 'action="/diakronos/einrichtung/' in antwort.text
            assert "/diakronos/diakonos/assets/diakronos-tokens.css" in antwort.text
    finally:
        base_path.setze_praefix(alt)


# ── E4: POST ───────────────────────────────────────────────────────────────


def test_post_legt_admin_mit_rollen_und_mitglied_an(client, patched_db, fake_redis):
    """E4: Rollen aus erstinstallation.ADMIN_ROLES + verknuepftes Mitglied."""
    from diakronos_app.frappe_compat.passwoerter import pruefe
    from diakronos_app.models.core import HasRole, User
    from diakronos_app.models.diakonos import Mitglied

    token = _neuer_token()
    antwort = client.post(
        f"/einrichtung/{token}",
        data={**_formular(), "_csrf": ""},
        follow_redirects=False,
    )
    # Ein Skript-Aufruf (keine Herkunftskopfzeilen) ist wie bei der Anmeldung
    # erlaubt; die Weiterleitung fuehrt in die App.
    assert antwort.status_code == 303, antwort.text
    assert antwort.headers["location"] == "/diakonos#/einrichtung"
    assert "sid=" in antwort.headers.get("set-cookie", "")

    sess = patched_db()
    try:
        konto = sess.get(User, "admin@gemeinde.example")
        assert konto is not None
        assert konto.enabled is True
        assert konto.full_name == "Mara Beispiel"
        assert konto.password_hash.startswith("$argon2")
        assert pruefe(PASSWORT, konto.password_hash)

        rollen = {
            r.role
            for r in sess.query(HasRole).filter(
                HasRole.parent == "admin@gemeinde.example"
            )
        }
        assert rollen == {"System Manager", "Mitgliederadministrator"}

        mitglieder = sess.query(Mitglied).all()
        assert len(mitglieder) == 1
        mitglied = mitglieder[0]
        assert mitglied.user == "admin@gemeinde.example"
        assert mitglied.vorname == "Mara"
        assert mitglied.nachname == "Beispiel"
        assert mitglied.email == "admin@gemeinde.example"
        # ID-1d: die Kennung vergibt der Server, nie ein Klarname.
        assert re.fullmatch(r"[0-9a-f]{8}-[0-9a-f]", mitglied.name), mitglied.name

        # Token verbraucht.
        assert sess.query(EinrichtungToken).count() == 0
    finally:
        sess.close()


def test_sitzung_ist_aktiv_und_der_link_danach_ungueltig(client, patched_db, fake_redis):
    """E4: nach dem Anlegen angemeldet in der App; Link ungueltig."""
    token = _neuer_token()
    antwort = client.post(
        f"/einrichtung/{token}", data=_formular(), follow_redirects=False
    )
    assert antwort.status_code == 303

    # Die Sitzung traegt den neuen Benutzer. Lesende Methode (GET) — ohne
    # CSRF-Pflicht und ohne Kopfzeilen-Token, genau wie die SPA beim Boot.
    kontext = client.get("/api/method/session.get_current_user_context")
    assert kontext.status_code == 200, kontext.text
    daten = kontext.json().get("message", kontext.json())
    if isinstance(daten, str):
        import json

        daten = json.loads(daten)
    assert daten["user"] == "admin@gemeinde.example", daten
    assert daten["is_admin"] is True

    assert client.get(f"/einrichtung/{token}").status_code == 404


def test_zweiter_post_ist_ungueltig(client, patched_db, fake_redis):
    """E4: Wettlauf — der zweite POST bekommt „Link ungueltig"."""
    token = _neuer_token()
    assert client.post(
        f"/einrichtung/{token}", data=_formular(), follow_redirects=False
    ).status_code == 303
    zweite = client.post(
        f"/einrichtung/{token}", data=_formular(email="zwei@gemeinde.example"),
        follow_redirects=False,
    )
    assert zweite.status_code == 404
    assert "Dieser Einrichtungslink ist nicht mehr gültig" in zweite.text
    assert _zaehle_benutzer(patched_db) == 1


def test_post_bei_schon_eingerichteter_installation(client, patched_db, fake_redis):
    from diakronos_app.models.core import User

    token = _neuer_token()
    sess = patched_db()
    try:
        sess.add(User(name="wer@example.org", email="wer@example.org", enabled=True))
        sess.commit()
    finally:
        sess.close()
    antwort = client.post(
        f"/einrichtung/{token}", data=_formular(), follow_redirects=False
    )
    assert antwort.status_code == 404
    assert _zaehle_benutzer(patched_db) == 1


@pytest.mark.parametrize(
    "abweichung, erwartet",
    [
        ({"passwort": "kurz1A", "wiederholung": "kurz1A"}, "mindestens 12 Zeichen"),
        ({"passwort": "ohnegross1zeichen", "wiederholung": "ohnegross1zeichen"},
         "Großbuchstaben"),
        ({"passwort": "OhneZahlBitte", "wiederholung": "OhneZahlBitte"}, "Zahl"),
        ({"wiederholung": "AnderesSicheres12"}, "stimmen nicht überein"),
        ({"email": "keine-adresse"}, "gültige E-Mail-Adresse"),
        ({"vorname": ""}, "Vor- und Nachnamen"),
        ({"nachname": ""}, "Vor- und Nachnamen"),
    ],
)
def test_post_validierung(client, patched_db, fake_redis, abweichung, erwartet):
    """E4: Validierung mit verstaendlicher Meldung — der Link bleibt gueltig."""
    token = _neuer_token()
    antwort = client.post(
        f"/einrichtung/{token}", data=_formular(**abweichung), follow_redirects=False
    )
    assert antwort.status_code == 417, antwort.text
    assert erwartet in antwort.text
    # Nichts angelegt, Token NICHT verbraucht (Transaktion zurueckgerollt).
    assert _zaehle_benutzer(patched_db) == 0
    assert einrichtung.pruefe_token(token)


def test_fremde_herkunft_wird_abgewiesen(client, patched_db, fake_redis):
    """E4/SEC-4: fremder Origin -> 403, kein Benutzer, Token bleibt."""
    token = _neuer_token()
    antwort = client.post(
        f"/einrichtung/{token}",
        data=_formular(),
        headers={"Origin": "https://boese.example"},
        follow_redirects=False,
    )
    assert antwort.status_code == 403
    assert _zaehle_benutzer(patched_db) == 0
    assert einrichtung.pruefe_token(token)


def test_cross_site_fetch_wird_abgewiesen(client, patched_db, fake_redis):
    token = _neuer_token()
    antwort = client.post(
        f"/einrichtung/{token}",
        data=_formular(),
        headers={"Sec-Fetch-Site": "cross-site"},
        follow_redirects=False,
    )
    assert antwort.status_code == 403
    assert _zaehle_benutzer(patched_db) == 0


def test_browser_ohne_maskentoken_wird_abgewiesen(client, patched_db, fake_redis):
    """E4: ein Browser-Aufruf mit falschem `_csrf` ist kein Aufruf unserer Maske."""
    token = _neuer_token()
    antwort = client.post(
        f"/einrichtung/{token}",
        data={**_formular(), "_csrf": "1700000000:deadbeef"},
        headers={"Origin": "http://testserver"},
        follow_redirects=False,
    )
    assert antwort.status_code == 403
    assert _zaehle_benutzer(patched_db) == 0


def test_browser_mit_gueltigem_maskentoken_darf_anlegen(
    client, patched_db, fake_redis
):
    """E4: eigener Origin + Masken-Token = der echte Browser-Weg."""
    from diakronos_app.anmeldung.maske_token import erzeuge_token

    token = _neuer_token()
    antwort = client.post(
        f"/einrichtung/{token}",
        data={**_formular(), "_csrf": erzeuge_token()},
        headers={"Origin": "http://testserver", "Sec-Fetch-Site": "same-origin"},
        follow_redirects=False,
    )
    assert antwort.status_code == 303, antwort.text
    assert _zaehle_benutzer(patched_db) == 1


def test_doppelte_email_wird_abgelehnt_und_link_bleibt(client, patched_db, fake_redis):
    """E4: eine vergebene Adresse ist eine Meldung, kein Verbrauch des Links."""
    from diakronos_app.models.diakonos import Mitglied

    sess = patched_db()
    try:
        sess.add(Mitglied(name="aaaa1111-b", vorname="Alt", nachname="Bestand",
                          email="admin@gemeinde.example"))
        sess.commit()
    finally:
        sess.close()

    token = _neuer_token()
    antwort = client.post(
        f"/einrichtung/{token}", data=_formular(), follow_redirects=False
    )
    assert antwort.status_code == 417
    assert "bereits" in antwort.text
    assert _zaehle_benutzer(patched_db) == 0
    assert einrichtung.pruefe_token(token)

    # Mit freier Adresse geht derselbe Link danach noch.
    antwort = client.post(
        f"/einrichtung/{token}",
        data=_formular(email="frei@gemeinde.example"),
        follow_redirects=False,
    )
    assert antwort.status_code == 303


def test_ratenbegrenzung_des_abrufs(client, patched_db, fake_redis, monkeypatch):
    """E4: die vorhandene Bremse greift auch hier (eigene Grenze, 429)."""
    from diakronos_app.anmeldung import registrierungsbremse

    monkeypatch.setattr(registrierungsbremse, "_max_valid", lambda: 2)
    token = _neuer_token()
    assert client.get(f"/einrichtung/{token}").status_code == 200
    assert client.get(f"/einrichtung/{token}").status_code == 200
    dritte = client.get(f"/einrichtung/{token}")
    assert dritte.status_code == 429


# ── E5: Logs ───────────────────────────────────────────────────────────────


def test_logs_tragen_weder_token_noch_passwort(client, patched_db, fake_redis, caplog):
    token = _neuer_token()
    with caplog.at_level("DEBUG"):
        client.get(f"/einrichtung/{token}")
        client.post(f"/einrichtung/{token}", data=_formular(), follow_redirects=False)
    # Nur die EIGENEN Logzeilen: der HTTP-Client des Testclients protokolliert
    # jede Anfrage samt Pfad (`httpx`), und der Pfad ist der Link.
    eigen = [
        r.getMessage() for r in caplog.records if not r.name.startswith("httpx")
    ]
    # Unter pytest schluckt der Test-Rahmen Log-Zeilen anderer Handler schon
    # vor `caplog`; bleibt nichts uebrig, wird der Inhalt direkt geprueft.
    if not eigen:
        caplog.clear()
        with caplog.at_level("INFO", logger="diakronos_app.einrichtung.routen"):
            client.post(f"/einrichtung/{token}", data=_formular(), follow_redirects=False)
        eigen = [r.getMessage() for r in caplog.records if not r.name.startswith("httpx")]
    text = "\n".join(eigen)
    assert token not in text
    assert PASSWORT not in text
    assert "Systemadministrator ueber Einrichtungslink angelegt." in text


# ── Querschnitt ────────────────────────────────────────────────────────────


def test_erstinstallation_bleibt_nach_anlegen_wirkungslos(client, patched_db, fake_redis,
                                                          ohne_adminwerte, capsys):
    """Nach dem Anlegen darf der Start keinen zweiten Link mehr erzeugen."""
    from diakronos_app.erstinstallation import bootstrap_erstinstallation

    token = _neuer_token()
    assert client.post(
        f"/einrichtung/{token}", data=_formular(), follow_redirects=False
    ).status_code == 303
    capsys.readouterr()
    bootstrap_erstinstallation()
    assert "ERSTEINRICHTUNG" not in capsys.readouterr().out
    assert _zeilen(patched_db) == []


def test_abgelaufener_token_wird_abgewiesen(patched_db):
    alt = _neuer_token(jetzt=einrichtung._jetzt() - timedelta(days=7, minutes=1))
    assert not einrichtung.pruefe_token(alt)


def test_konstanter_vergleich_wird_benutzt():
    """E3: der Vergleich laeuft ueber hmac.compare_digest (Quelltext-Waechter)."""
    from pathlib import Path

    quelle = (Path(einrichtung.__file__)).read_text(encoding="utf-8")
    assert "hmac.compare_digest" in quelle
    # Ablauf ist Pflicht, kein optionales Feld.
    assert "gueltig_bis: Mapped[datetime] = mapped_column(DateTime, nullable=False)" in (
        (Path(einrichtung.__file__).parent / "models" / "einrichtung.py").read_text(
            encoding="utf-8"
        )
    )


def test_migration_ist_genau_ein_head_und_haengt_an_on2():
    """ON-1b: on1_einrichtung haengt seit dem Merge auf on2_einrichtung.

    Die Kette hat weiterhin genau EINEN Kopf; ON-2b liegt unmittelbar davor,
    damit `alembic heads` nicht gabelt. Der Kopf selbst wandert mit jeder
    neuen Migration weiter (UX2b: `ux2b_papierkorb`), deshalb wird die
    VERKETTUNG geprueft, nicht ein fest verdrahteter Name: jede Nachfolge-
    Revision von `on1_einrichtung` muss eine gerade Linie ohne Gabelung
    bilden.
    """
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    from pathlib import Path

    ini = Path(__file__).resolve().parents[1] / "alembic.ini"
    cfg = Config(str(ini))
    cfg.set_main_option("script_location", str(ini.parent / "alembic"))
    script = ScriptDirectory.from_config(cfg)
    heads = script.get_heads()
    assert len(heads) == 1, heads          # genau ein Kopf, keine Gabelung
    rev = script.get_revision("on1_einrichtung")
    assert rev.down_revision == "on2_einrichtung"
    # Vom einzigen Kopf zurueck bis on1_einrichtung: erreichbar, lueckenlos.
    kette = [r.revision for r in script.iterate_revisions(heads[0], "on1_einrichtung",
                                                          inclusive=True)]
    assert kette[-1] == "on1_einrichtung", kette
    for a, b in zip(kette, kette[1:]):
        assert script.get_revision(a).down_revision == b, (a, b)
