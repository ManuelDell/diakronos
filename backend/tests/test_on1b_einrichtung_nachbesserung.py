"""ON-1b — Nachbesserungen am Einrichtungslink (Opus-Review F1–F7).

Warum diese Datei
-----------------
ON-1 hat den Einrichtungslink gebaut; das Review fand sieben Punkte, die im
Betrieb weh tun. Jeder Punkt steht hier als Test — rot vor der Korrektur,
gruen danach:

  F1  Der Token steht im Zugriffsprotokoll (`uvicorn.access`), weil uvicorn
      den vollen Pfad schreibt und der Pfad HIER das Geheimnis ist.
      -> Filter schreibt `/einrichtung/***`.
  F2  Nach einem Validierungsfehler war das Formular nicht erneut absendbar:
      die Fehlerseite lieferte `csrf_token=""`, der Browser schickte einen
      leeren Masken-Token und bekam 403.
  F3  Der GET schrieb (Diagnose-Zaehler `aufrufe`) — ein schreibender GET.
  F4  Die Sitzung nach dem Anlegen war als SSO gekennzeichnet und umging
      damit die Pruefung „Passwortwechsel noetig".
  F5  Tote Konstanten `CSP`/`ANTWORT_KOPFZEILEN` in `einrichtung_seiten`.
  F6  Ungueltiger Token + ungueltige Formularfelder zeigte die Formularseite
      mit 417 statt „Link ungueltig" (Orakel + falscher Status).
  F7  Zwei parallele POSTs auf PostgreSQL legen genau EINEN Benutzer an.

F7 laeuft nur mit `ON1B_POSTGRES_URL` (Wegwerf-PostgreSQL, Name endet auf
`_test`); ohne die Variable wird der Test uebersprungen — SQLite kann die
Zeilensperre (`SELECT … FOR UPDATE`) nicht pruefen.
"""

from __future__ import annotations

import hashlib
import logging
import os
import threading

import pytest

from diakronos_app import einrichtung
from diakronos_app.models.einrichtung import EINRICHTUNG_TOKEN_NAME, EinrichtungToken

PASSWORT = "EinSicheres12"


# ── Helfer (gleiche Formen wie test_on1_einrichtung) ───────────────────────


@pytest.fixture()
def ohne_adminwerte(monkeypatch):
    from diakronos_app.settings import settings as settings_obj

    monkeypatch.setattr(settings_obj, "admin_email", None)
    monkeypatch.setattr(settings_obj, "admin_password", None)
    return settings_obj


@pytest.fixture()
def client(patched_db, fake_redis):
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


def _aufrufe(session_factory) -> int | None:
    """Der Diagnose-Zaehler der einzigen Token-Zeile (None = keine Zeile)."""
    zeilen = _zeilen(session_factory)
    if not zeilen:
        return None
    return int(zeilen[0].aufrufe or 0)


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


def _csrf_aus(html: str) -> str:
    """Der Masken-Token, wie ihn die Seite in das Formular schreibt."""
    import re

    treffer = re.search(r'name="_csrf"\s+value="([^"]*)"', html)
    return treffer.group(1) if treffer else ""


# ── F1: kein Token im Zugriffsprotokoll ────────────────────────────────────


def _zugriffszeile(pfad: str, status: int = 200) -> logging.LogRecord:
    """Eine `uvicorn.access`-Zeile bauen — genau in uvicorns Form.

    ``uvicorn.protocols.utils.get_path_with_query_string`` liefert den vollen
    Pfad samt Query; ``AccessFormatter`` setzt ihn als ``args[2]`` ein.
    """
    record = logging.LogRecord(
        name="uvicorn.access",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg='%s - "%s %s HTTP/%s" %d',
        args=("192.0.2.7:5555", "GET", pfad, "1.1", status),
        exc_info=None,
    )
    return record


def test_f1_zugriffsprotokoll_zeigt_sternchen_statt_token():
    """F1: `/einrichtung/<token>` wird zu `/einrichtung/***` umgeschrieben."""
    from diakronos_app.anmeldung.einrichtung_routen import EinrichtungsAccessLogFilter

    token = "k7Qe8vT2AbCdEfGhIjKlMnOpQrStUvWxYz012345678"
    filter_ = EinrichtungsAccessLogFilter()

    record = _zugriffszeile(f"/einrichtung/{token}")
    assert filter_.filter(record) is True  # Nie verwerfen — nur umschreiben.
    zeile = record.getMessage()
    assert token not in zeile
    assert "/einrichtung/***" in zeile
    # Methode, Status und Client bleiben lesbar.
    assert "GET" in zeile and "200" in zeile and "192.0.2.7:5555" in zeile


def test_f1_praefix_bleibt_vor_dem_platzhalter(monkeypatch):
    """F1: mit `DIAKRONOS_BASE_PATH` steht der Praefix weiter davor."""
    from diakronos_app.anmeldung.einrichtung_routen import EinrichtungsAccessLogFilter
    from diakronos_app.settings import settings as settings_obj

    monkeypatch.setattr(settings_obj, "diakronos_base_path", "/diakronos")
    token = "k7Qe8vT2AbCdEfGhIjKlMnOpQrStUvWxYz012345678"
    record = _zugriffszeile(f"/diakronos/einrichtung/{token}")
    EinrichtungsAccessLogFilter().filter(record)
    zeile = record.getMessage()
    assert token not in zeile
    assert "/diakronos/einrichtung/***" in zeile


def test_f1_query_string_und_fremde_pfade_unveraendert():
    """F1: der Filter fasst nur den Einrichtungspfad an."""
    from diakronos_app.anmeldung.einrichtung_routen import EinrichtungsAccessLogFilter

    filter_ = EinrichtungsAccessLogFilter()
    token = "k7Qe8vT2AbCdEfGhIjKlMnOpQrStUvWxYz012345678"

    # Query bleibt: Interesse der Diagnose, kein Geheimnis.
    record = _zugriffszeile(f"/einrichtung/{token}?x=1")
    filter_.filter(record)
    zeile = record.getMessage()
    assert token not in zeile
    assert "/einrichtung/***?x=1" in zeile

    # Andere Pfade bleiben Byte fuer Byte gleich.
    fremd = _zugriffszeile("/api/method/ping")
    vorher = fremd.args
    filter_.filter(fremd)
    assert fremd.args == vorher

    # Pfade, die nur so AUSSEHEN, als haetten sie den Praefix, werden nicht
    # mitgeschnitten (kein versehentliches Umschreiben von `/x/einrichtung/`).
    kein_einrichtung = _zugriffszeile("/diakonos/einrichtungsplan")
    vorher = kein_einrichtung.args
    filter_.filter(kein_einrichtung)
    assert kein_einrichtung.args == vorher


def test_f1_filter_ist_am_uvicorn_zugriffslogger_haengt():
    """F1: der Filter wird beim Import EINMAL installiert (nicht doppelt)."""
    import diakronos_app.anmeldung.einrichtung_routen as routen

    routen.installiere_log_filter()
    routen.installiere_log_filter()
    zugriff = logging.getLogger("uvicorn.access")
    treffer = [
        f for f in zugriff.filters if isinstance(f, routen.EinrichtungsAccessLogFilter)
    ]
    assert len(treffer) == 1, treffer


def test_f1_echter_aufruf_loggt_ohne_token(client, patched_db, fake_redis, caplog):
    """F1: der Weg durch die App — die Zeile mit dem Link traegt kein Token.

    Gebaut wird die Zeile wie uvicorn sie baut; geprueft wird, dass der
    installierte Filter sie faengt, obwohl er an `uvicorn.access` haengt und
    der Test-Logger nicht uvicorn ist.
    """
    token = _neuer_token()
    assert client.get(f"/einrichtung/{token}").status_code == 200

    zugriff = logging.getLogger("uvicorn.access")
    record = _zugriffszeile(f"/einrichtung/{token}")
    with caplog.at_level(logging.INFO, logger="uvicorn.access"):
        for filter_ in zugriff.filters:
            filter_.filter(record)
        zugriff.handle(record)

    text = "\n".join(r.getMessage() for r in caplog.records)
    assert text, "keine Zugriffszeile aufgezeichnet"
    assert token not in text
    assert "/einrichtung/***" in text


# ── F2: Formular nach Fehler erneut absendbar ──────────────────────────────


def test_f2_frische_csrf_auf_der_fehlerseite(client, patched_db, fake_redis):
    """F2: die Fehlerseite traegt einen BENUTZBAREN Masken-Token."""
    token = _neuer_token()
    antwort = client.post(
        f"/einrichtung/{token}",
        data=_formular(passwort="kurz1A", wiederholung="kurz1A"),
        follow_redirects=False,
    )
    assert antwort.status_code == 417
    csrf = _csrf_aus(antwort.text)
    assert csrf, "Fehlerseite ohne Masken-Token — Formular waere nicht absendbar"

    from diakronos_app.anmeldung.maske_token import token_ist_gueltig

    assert token_ist_gueltig(csrf)


def test_f2_falsches_passwort_dann_erneut_mit_origin(client, patched_db, fake_redis):
    """F2 (der Befund im Browser): Fehler -> nochmal absenden -> Erfolg.

    Genau der Ablauf, der vorher mit 403 endete: Origin wie ein Browser,
    `_csrf` aus der Fehlerseite, gueltige Werte beim zweiten Versuch.
    """
    token = _neuer_token()
    # Wie im Browser: Maske laden, deren `_csrf` absenden, Fehler bekommen.
    maske = client.get(f"/einrichtung/{token}")
    assert maske.status_code == 200
    maske_csrf = _csrf_aus(maske.text)
    assert maske_csrf

    erste = client.post(
        f"/einrichtung/{token}",
        data={**_formular(passwort="kurz1A", wiederholung="kurz1A"), "_csrf": maske_csrf},
        headers={"Origin": "http://testserver", "Sec-Fetch-Site": "same-origin"},
        follow_redirects=False,
    )
    assert erste.status_code == 417, erste.text
    csrf = _csrf_aus(erste.text)
    assert csrf
    assert csrf != "", "Fehlerseite ohne frischen Masken-Token"

    zweite = client.post(
        f"/einrichtung/{token}",
        data={**_formular(), "_csrf": csrf},
        headers={"Origin": "http://testserver", "Sec-Fetch-Site": "same-origin"},
        follow_redirects=False,
    )
    assert zweite.status_code == 303, zweite.text
    assert _zaehle_benutzer(patched_db) == 1


def test_f2_auch_die_email_meldung_ist_neu_absendbar(client, patched_db, fake_redis):
    """F2: gilt fuer JEDE Fehlerseite, nicht nur die Passwortpruefung.

    Die Meldung „Adresse bereits vergeben" entsteht nach dem Rollback — auch
    von dort muss das Formular noch einmal gehen.
    """
    from diakronos_app.models.diakonos import Mitglied

    sess = patched_db()
    try:
        sess.add(
            Mitglied(
                name="aaaa1111-b",
                vorname="Alt",
                nachname="Bestand",
                email="admin@gemeinde.example",
            )
        )
        sess.commit()
    finally:
        sess.close()

    token = _neuer_token()
    maske_csrf = _csrf_aus(client.get(f"/einrichtung/{token}").text)
    assert maske_csrf

    erste = client.post(
        f"/einrichtung/{token}",
        data={**_formular(), "_csrf": maske_csrf},
        headers={"Origin": "http://testserver", "Sec-Fetch-Site": "same-origin"},
        follow_redirects=False,
    )
    assert erste.status_code == 417, erste.text
    csrf = _csrf_aus(erste.text)
    assert csrf

    zweite = client.post(
        f"/einrichtung/{token}",
        data={**_formular(email="frei@gemeinde.example"), "_csrf": csrf},
        headers={"Origin": "http://testserver", "Sec-Fetch-Site": "same-origin"},
        follow_redirects=False,
    )
    assert zweite.status_code == 303, zweite.text


# ── F3: der GET schreibt nicht ─────────────────────────────────────────────


def test_f3_get_zaehlt_nicht(client, patched_db, fake_redis):
    """F3: mehrfaches Laden aendert `aufrufe` nicht."""
    token = _neuer_token()
    assert _aufrufe(patched_db) == 0
    for _ in range(3):
        assert client.get(f"/einrichtung/{token}").status_code == 200
    assert _aufrufe(patched_db) == 0


def test_f3_get_ungueltig_zaehlt_ebenfalls_nicht(client, patched_db, fake_redis):
    """F3: auch ein Aufruf mit falschem Token schreibt nichts."""
    token = _neuer_token()
    assert client.get("/einrichtung/falscher-token").status_code == 404
    assert _aufrufe(patched_db) == 0
    # Der gueltige Link lebt weiter.
    assert einrichtung.pruefe_token(token, zaehle=False)


# ── F4: die Sitzung ist keine SSO-Sitzung ──────────────────────────────────


def test_f4_sitzung_nach_anlegen_ist_kein_sso(client, patched_db, fake_redis):
    """F4: `sso` fehlt in der Sitzung — die Wechselpflicht greift wieder."""
    from diakronos_app.frappe_compat import sitzungen

    token = _neuer_token()
    assert client.post(
        f"/einrichtung/{token}", data=_formular(), follow_redirects=False
    ).status_code == 303

    sid = client.cookies.get("sid")
    assert sid
    daten = sitzungen.lesen(sid)
    assert daten is not None and daten["user"] == "admin@gemeinde.example"
    assert daten.get("sso") is not True


def test_f4_wechselpflicht_beendet_die_sitzung(client, patched_db, fake_redis):
    """F4 (die Wirkung): mit Wechselpflicht gilt die Sitzung nicht mehr.

    Mit `sso=True` haette `auth_middleware` die Pruefung uebersprungen und
    den Administrator trotz gesetzter Wechselpflicht hereingelassen.
    """
    from diakronos_app.anmeldung import passwortzugang
    from diakronos_app.models.passwortzugang import Passwortzugang

    token = _neuer_token()
    assert client.post(
        f"/einrichtung/{token}", data=_formular(), follow_redirects=False
    ).status_code == 303
    assert client.get("/api/method/session.get_current_user_context").status_code == 200

    sess = patched_db()
    try:
        sess.add(
            Passwortzugang(user="admin@gemeinde.example", wechsel_noetig=True)
        )
        sess.commit()
    finally:
        sess.close()

    assert passwortzugang.wechsel_noetig("admin@gemeinde.example") is True
    # Der Cache der Middleware kennt den Benutzer schon als „kein Wechsel
    # noetig" (er wurde beim Anlegen befragt) — hier ausdruecklich verwerfen,
    # sonst pruefte der naechste Request den alten Stand.
    from diakronos_app.frappe_compat import benutzer_status as b

    b._client().delete(b._key("admin@gemeinde.example") + ":erstwechsel")
    # Die Sitzung gilt nicht mehr: die Methode verlangt einen angemeldeten
    # Benutzer und antwortet Gast-abweisend (401). Mit `sso=True` waere hier
    # der Administrator durchgekommen — genau der Befund.
    gast = client.get("/api/method/session.get_current_user_context")
    assert gast.status_code == 401, gast.text


# ── F5: keine toten Konstanten ─────────────────────────────────────────────


def test_f5_keine_toten_header_konstanten():
    """F5: `CSP`/`ANTWORT_KOPFZEILEN` sind weg und werden nirgends benutzt."""
    import diakronos_app.einrichtung_seiten as seiten

    assert not hasattr(seiten, "CSP")
    assert not hasattr(seiten, "ANTWORT_KOPFZEILEN")
    assert "CSP" not in seiten.__all__
    quelle = open(seiten.__file__, encoding="utf-8").read()
    # Nur der erklaerende Kommentar darf die Namen noch nennen.
    code = "\n".join(
        zeile for zeile in quelle.splitlines() if not zeile.lstrip().startswith("#")
    )
    assert "ANTWORT_KOPFZEILEN" not in code
    assert "CSP =" not in code


# ── F6: ungueltiger Token gewinnt immer ────────────────────────────────────


@pytest.mark.parametrize(
    "felder",
    [
        {"passwort": "kurz1A", "wiederholung": "kurz1A"},
        {"email": "keine-adresse"},
        {"vorname": ""},
        {"passwort": "OhneZahlBitte", "wiederholung": "OhneZahlBitte", "nachname": ""},
    ],
)
def test_f6_ungueltiger_token_plus_ungueltige_felder_ist_ungueltig(
    client, patched_db, fake_redis, felder
):
    """F6: „Link ungueltig" (404) — nie die Formularseite mit 417.

    Ein Browser-POST OHNE jeden Masken-Token wird schon von der
    Herkunftspruefung abgewiesen (403, CSRF) — das ist gewollt und nicht
    Gegenstand dieses Tests. Hier geht es um den Fall, in dem der Absender
    den CSRF-Teil besteht (gueltiger ``_csrf``) und danach der TOKEN zaehlt.
    """
    from diakronos_app.anmeldung.maske_token import erzeuge_token

    antwort = client.post(
        f"/einrichtung/nie-gueltig-gewesen",
        data={**_formular(**felder), "_csrf": erzeuge_token()},
        headers={"Origin": "http://testserver", "Sec-Fetch-Site": "same-origin"},
        follow_redirects=False,
    )
    assert antwort.status_code == 404, antwort.text
    assert "Dieser Einrichtungslink ist nicht mehr gültig" in antwort.text
    # Keine Formularmaske (kein Feld, keine Meldung ueber dem Formular).
    assert 'name="_csrf"' not in antwort.text


def test_f6_ungueltiger_token_zeigt_dieselbe_seite_wie_der_get(
    client, patched_db, fake_redis
):
    """F6: kein Unterschied zwischen GET und POST bei ungueltigem Token."""
    get = client.get("/einrichtung/nie-gueltig-gewesen")
    post = client.post(
        "/einrichtung/nie-gueltig-gewesen", data=_formular(), follow_redirects=False
    )
    assert get.status_code == post.status_code == 404
    assert get.text == post.text


def test_f6_gueltiger_token_bleibt_bei_ungueltigen_feldern_gueltig(
    client, patched_db, fake_redis
):
    """F6 (Gegenprobe): die Vorpruefung verbraucht den Token NICHT.

    Sonst waere ein Tippfehler im Passwort das Ende des Links.
    """
    token = _neuer_token()
    antwort = client.post(
        f"/einrichtung/{token}",
        data=_formular(passwort="kurz1A", wiederholung="kurz1A"),
        follow_redirects=False,
    )
    assert antwort.status_code == 417
    assert _zeilen(patched_db), "Token-Zeile wurde entfernt"
    assert einrichtung.pruefe_token(token, zaehle=False)


# ── F8 (Betriebsbefund im Wegwerf-Stack): Link MIT Praefix ────────────────


def test_f8_kasten_zeigt_den_link_mit_betriebspraefix(patched_db, fake_redis, monkeypatch):
    """F8: der Startkasten nennt eine Adresse, die im Betrieb auch antwortet.

    Im Wegwerf-Stack mit `DIAKRONOS_BASE_PATH=/diakronos` zeigte der Kasten
    `/einrichtung/<token>` — genau diese Adresse antwortet dort mit 404
    (gemessen). Ursache: der Entrypoint startet
    `python -m diakronos_app.erstinstallation` als EIGENEN Prozess; dort lief
    `main.create_app()` nie, und `base_path.pfad` kannte den Praefix nicht.

    Geprueft wird die ganze Kette Startkasten -> Link -> aktive Route:
    die gebaute Adresse ist praefigiert UND der GET auf denselben Pfad
    liefert die Maske.
    """
    from diakronos_app import base_path
    from diakronos_app.erstinstallation import startkasten
    from diakronos_app.settings import settings as settings_obj

    monkeypatch.setattr(settings_obj, "diakronos_base_path", "/diakronos")
    monkeypatch.setattr(base_path, "_AKTIV", "", raising=False)

    token = _neuer_token()
    kasten = startkasten(token)
    assert f"/diakronos/einrichtung/{token}" in kasten, kasten
    # Der Praefix wird EINMAL gesetzt und danach nicht doppelt angehaengt.
    assert base_path.pfad("/login") == "/diakronos/login"


def test_f8_link_anzeige_praefigiert_auch_ohne_gesetzten_prozess(patched_db, fake_redis, monkeypatch):
    """F8: `link_anzeige` holt den Praefix selbst aus den Einstellungen."""
    from diakronos_app import base_path, einrichtung as einrichtung_modul
    from diakronos_app.settings import settings as settings_obj

    monkeypatch.setattr(settings_obj, "diakronos_base_path", "/diakronos")
    monkeypatch.setattr(settings_obj, "app_base_url", "")
    monkeypatch.setattr(base_path, "_AKTIV", "", raising=False)

    anzeige = einrichtung_modul.link_anzeige("TOKEN-XYZ")
    assert anzeige == "/diakronos/einrichtung/TOKEN-XYZ", anzeige
    # Idempotent: ein zweiter Aufruf haengt nichts an.
    assert einrichtung_modul.link_anzeige("TOKEN-XYZ") == anzeige


# ── F7: zwei parallele POSTs auf PostgreSQL -> genau ein Benutzer ──────────

_F7_URL = os.environ.get("ON1B_POSTGRES_URL")

pytestmark_f7 = pytest.mark.skipif(
    not _F7_URL,
    reason="nur mit ON1B_POSTGRES_URL (Wegwerf-PostgreSQL, Name endet auf _test)",
)


def _f7_url() -> str:
    url = str(_F7_URL)
    assert url.rsplit("/", 1)[-1].split("?")[0].endswith("_test"), (
        "ON1B_POSTGRES_URL muss eine Wegwerf-Datenbank sein (*_test)"
    )
    return url


@pytestmark_f7
def test_f7_zwei_parallele_posts_legen_genau_einen_benutzer_an(monkeypatch):
    """F7: `SELECT … FOR UPDATE` haelt den Wettlauf aus (PostgreSQL).

    Der eigentliche Beleg fuer `verbrauche_mit`: der zweite Thread wartet auf
    die Zeilensperre, sieht die Zeile danach nicht mehr und bekommt
    „ungueltig". Auf SQLite ist `with_for_update` ein No-op — deshalb hier
    ein echter PostgreSQL.
    """
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    import diakronos_app.db as dbmod
    import diakronos_app.models  # noqa: F401 — Modelle registrieren
    from diakronos_app.anmeldung import einrichtung_routen
    from diakronos_app.models.base import Base
    from diakronos_app.models.core import User

    from alembic import command
    from alembic.config import Config
    from pathlib import Path

    url = _f7_url()
    eng = create_engine(url, future=True)
    try:
        # Schema ueber die Migrationen aufbauen (kein `create_all`: die Kette
        # ist die Wahrheit, und on1_einrichtung legt genau diese Tabelle an).
        ini = Path(__file__).resolve().parents[1] / "alembic.ini"
        cfg = Config(str(ini))
        cfg.set_main_option("script_location", str(ini.parent / "alembic"))
        monkeypatch.setattr(
            "diakronos_app.settings.settings.database_url", url, raising=False
        )
        command.upgrade(cfg, "head")

        factory = sessionmaker(bind=eng, autoflush=False, autocommit=False, future=True)
        monkeypatch.setattr(dbmod, "engine", eng)
        monkeypatch.setattr(dbmod, "SessionLocal", factory)

        token, _bis = einrichtung.erzeuge_token()

        ergebnisse: list[bool] = []
        sperre = threading.Lock()
        start = threading.Barrier(2)

        def absenden(warten: int) -> None:
            start.wait()
            sess = factory()
            try:
                ok = einrichtung.verbrauche_mit(sess, token)
                if ok:
                    import time

                    # Fenster, in dem beide Threads gleichzeitig „drin" waeren.
                    time.sleep(0.2)
                    sess.add(
                        User(
                            name=f"admin{warten}@gemeinde.example",
                            email=f"admin{warten}@gemeinde.example",
                            enabled=True,
                        )
                    )
                sess.commit()
            except Exception:  # noqa: BLE001 — ein Konflikt ist hier erlaubt
                sess.rollback()
                ok = False
            finally:
                sess.close()
            with sperre:
                ergebnisse.append(ok)

        threads = [threading.Thread(target=absenden, args=(i,)) for i in (0, 1)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)
        assert not any(t.is_alive() for t in threads), "Thread haengt (Sperre?)"

        assert ergebnisse.count(True) == 1, ergebnisse
        with factory() as s:
            assert s.query(User).count() == 1
            assert s.get(EinrichtungToken, EINRICHTUNG_TOKEN_NAME) is None
    finally:
        eng.dispose()
