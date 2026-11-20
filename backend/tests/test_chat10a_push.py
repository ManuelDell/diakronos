"""CHAT-10a: Web-Push (VAPID) — Abonnements + Versand OHNE Inhalt.

Geprüft wird gegen die ECHTEN Wege — ``api.push`` (Endpunkte), die ECHTE
Tabelle ``push_abonnement``, die ECHTE Glocke (``api.chat``), den ECHTEN
rq-Einreihweg und die ECHTE Migration:

  * OHNE VAPID-Werte ist Push AUS: ``schluessel`` → ``{"aktiv": false}``,
    ``anmelden``/``abmelden`` schreiben nichts, KEIN Versandauftrag
  * ``anmelden`` legt an / aktualisiert (gleicher endpoint = selbe Zeile),
    Umhängen bei Gerätewechsel (andere Person auf demselben Browser)
  * ``abmelden`` löscht NUR eigene; ein fremder endpoint bleibt stehen
  * Gast wird abgewiesen (403)
  * SSRF: http, loopback, private und nicht auflösbare Hosts abgewiesen
  * Länge begrenzt, Schlüssel als Base64url geprüft
  * Chat-Glocke (gebündelt) → Versandauftrag mit Nutzlast OHNE Inhalt
  * stumm → KEIN Auftrag; Erwähnung → Auftrag TROTZ stumm
  * ``nur_zahl`` (teilweises Lesen) → KEIN Auftrag
  * Versand: 2xx → ``zuletzt_ok_am``, 410 → Zeile weg, 5 Fehlversuche → weg
  * DSGVO-Inventar: Zeile fällt mit der Person (Wächter-Test grün)
  * Migration ``chat10a_push``: genau ein Kopf, Kante hinter
    ``chat9a_erwaehnung``, up/down/up auf SQLite
  * SEC-11: ``schluessel`` GET, ``anmelden``/``abmelden`` POST-only

Aufruf (Karte):
    docker run --rm --network none --entrypoint python -v <wt>:/repo:ro \\\\
      -w /repo/backend -e PYTHONPATH=/repo/backend/src:/repo/backend/tests:/repo/tools \\\\
      -e PYTHONDONTWRITEBYTECODE=1 <vorbau> -m pytest -q -p no:cacheprovider \\\\
      tests/test_chat10a_push.py
"""

from __future__ import annotations

import importlib
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory

from diakronos_app import db as dbmod
from diakronos_app.api import push as P
from diakronos_app.models.push import MAX_FEHLVERSUCHE, PushAbonnement

#: Die Test-Naht liegt im MODUL ``frappe_compat.session`` (wie ``test_chat2_api``).
_session_mod = importlib.import_module("diakronos_app.frappe_compat.session")

#: Dieselbe Welt wie ``test_chat4a_glocke`` (Chor, Untergruppe, Konten).
from test_chat4a_glocke import (  # noqa: E402,F401 — Fixture/Konten teilen
    ADMIN,
    FREMD,
    GL,
    HV,
    MV,
    NOTEN,
    SAENGER,
    SAENGER2,
    _teilnahme,
    gespraech,
    welt,
)
#: Dieselbe Runden-Welt wie ``test_chat9a_erwaehnung`` (Anna/Bert/Clara).
#: Die Fixture heißt dort ``welt`` — hier unter eigenem Namen, weil die
#: Glocken-Welt oben bereits ``welt`` ist (pytest nimmt die zuletzt definierte).
from test_chat7b_runden import welt as runden_welt  # noqa: E402,F401

BACKEND = Path(__file__).resolve().parents[1]

#: Ein echter Push-Endpunkt sieht so aus: https, fremder Dienst, langer Query.
#: Seit Review R1/2 gilt eine ALLOWLIST — der Host muss ein Push-Dienst sein.
_FCM_HOST = "fcm.googleapis.com"
ENDPOINT = f"https://{_FCM_HOST}/fcm/send/abc123def456?token=xyz"
ENDPOINT_2 = f"https://{_FCM_HOST}/fcm/send/zweitesgeraet?token=abc"
#: Ein zweiter erlaubter Dienst (Suffix-Form).
MOZILLA = "https://updates.push.services.mozilla.com/wpush/v2/AAA?x=1"
#: Ein ECHTER, gültiger P-256-Punkt (65 Byte, ``0x04``). Seit CHAT-10a-2/5
#: prüft der Versand das Gerät vorab — ein erfundenes Feld gilt als
#: Fehlversuch und ließe die Fehlerfall-Tests am Gerät scheitern statt am
#: geprüften Fehler.
P256DH = "BLhfpIGufXWtRv_ZGvpB6ursyPg2L5NuC-GTY7i78HdNWj6REbVE1GMQUkC1yIu8dGNxife6W7lLC2arLrQN31U"
AUTH = "kMXL8bTQnOcvNwZC0vHb1g"

#: Ein Gast ist der Name ``"Guest"`` — derselbe Wert wie im Rechte-Kern.
GAST = "Guest"


def _set_user(konto: str) -> None:
    _session_mod.set_user(konto)


@pytest.fixture()
def _aufloesung(monkeypatch):
    """DNS im Test: die erlaubten Push-Dienste → eine ÖFFENTLICHE Adresse.

    Der Testlauf läuft ``--network none``; ``getaddrinfo`` scheitert dort für
    JEDEN Namen. Die zweite Grenze (``_host_ist_oeffentlich``, nur beim
    ANMELDEN) ist fail-closed und wiese damit auch den guten Endpunkt ab — der
    Test prüfte dann die Testumgebung, nicht den Code.

    Nachgebildet wird nur die Auflösung, NICHT die Bewertung: die Adresse ist
    eine echte öffentliche (93.184.216.34), und die Prüfung selbst
    (``ipaddress``) läuft unverändert. Die abgewiesenen Fälle sind Namen, die
    AUCH diese Attrappe nicht kennt bzw. auf 127.0.0.1 zeigt — für die
    entscheidet weiterhin der Code.
    """
    import socket as _socket

    echt = _socket.getaddrinfo

    def _fake(host, port, *args, **kwargs):
        name = str(host).lower()
        # Jeder Host, den die Allowlist kennt, löst auf eine öffentliche
        # Adresse auf (Attrappe) — die Bewertung selbst bleibt im Code.
        if P._host_erlaubt(name) or name == "evil.fcm.googleapis.com":
            return [(2, 1, 6, "", ("93.184.216.34", port or 0))]
        if name in ("localhost",):
            return [(2, 1, 6, "", ("127.0.0.1", port or 0))]
        raise _socket.gaierror(-2, "Name or service not known")

    monkeypatch.setattr(_socket, "getaddrinfo", _fake)
    yield
    monkeypatch.setattr(_socket, "getaddrinfo", echt)


#: Rohformat wie tools/vapid_schluessel.py: 32 Byte Base64url, Skalar d = 1.
GUELTIGER_PRIVAT = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAE"


@pytest.fixture()
def vapid(monkeypatch):
    """VAPID-Werte setzen — Push ist damit AN (Default der Tests)."""
    from diakronos_app.settings import settings

    monkeypatch.setattr(settings, "vapid_public", "oeffentlich-test", raising=False)
    monkeypatch.setattr(settings, "vapid_private", GUELTIGER_PRIVAT, raising=False)
    monkeypatch.setattr(settings, "vapid_kontakt", "mailto:test@example.invalid",
                        raising=False)
    return settings


@pytest.fixture()
def ohne_vapid(monkeypatch):
    """Push ist AUS — keine Schlüssel in der Umgebung."""
    from diakronos_app.settings import settings

    monkeypatch.setattr(settings, "vapid_public", "", raising=False)
    monkeypatch.setattr(settings, "vapid_private", "", raising=False)
    monkeypatch.setattr(settings, "vapid_kontakt", "", raising=False)
    return settings


@pytest.fixture()
def eingereiht(monkeypatch):
    """Ersetzt ``enqueue`` durch eine Liste — KEIN Redis im Test.

    Die Naht ist ABSICHTLICH ``frappe_compat.queue.enqueue`` (der einzige Weg
    aus der App zum Worker): so ist belegt, dass der Auftrag über den
    vorhandenen rq-Pfad geht, und nicht über einen zweiten im Push-Modul.

    ``_pywebpush_da`` wird auf ``True`` gesetzt: das Test-Image hat das Paket
    nicht, und der Auftrag darf (Review R1/3) nur entstehen, wenn es da ist.
    Das Fehlen wird eigens geprüft (``test_ohne_pywebpush_...``).
    """
    from diakronos_app.frappe_compat import queue as qmod

    monkeypatch.setattr(P, "_pywebpush_da", lambda: True)
    auftraege: list[dict] = []

    def _merken(func, queue=None, timeout=None, **kwargs):
        auftraege.append({"func": func, "queue": queue, "timeout": timeout,
                          **kwargs})
        return None

    monkeypatch.setattr(qmod, "enqueue", _merken)
    return auftraege


@pytest.fixture()
def kein_netz(monkeypatch):
    """``_senden_an`` wird ersetzt — der Test geht NIE ins Netz."""
    monkeypatch.setattr(P, "_pywebpush_da", lambda: True)
    zustand = {"ergebnis": P.VAPID_OK, "aufrufe": []}

    def _senden(abo, nutzlast):
        zustand["aufrufe"].append({"endpoint": abo.endpoint, "nutzlast": nutzlast})
        zustand["ergebnis"] = zustand.get("naechstes", zustand["ergebnis"])
        return zustand["ergebnis"]

    monkeypatch.setattr(P, "_senden_an", _senden)
    return zustand


def _abos(konto: str | None = None) -> list[PushAbonnement]:
    with dbmod.SessionLocal() as s:
        abfrage = s.query(PushAbonnement)
        if konto:
            abfrage = abfrage.filter(PushAbonnement.benutzer == konto)
        return list(abfrage.all())


def _anmelden(endpoint=ENDPOINT, konto=SAENGER, p256dh=P256DH, auth=AUTH) -> dict:
    _set_user(konto)
    return P.anmelden(endpoint, p256dh, auth)


# ── 1. Ohne Schlüssel ist Push AUS (kein Fehler) ────────────────────────────


def test_ohne_schluessel_ist_push_aus(welt, ohne_vapid):
    _set_user(SAENGER)
    assert P.schluessel() == {"aktiv": False}
    assert P.aktiv() is False


def test_ohne_schluessel_schreibt_anmelden_nichts(welt, ohne_vapid):
    assert _anmelden() == {"aktiv": False}
    assert _abos() == []


def test_ohne_schluessel_loescht_abmelden_nichts(welt, ohne_vapid):
    _set_user(SAENGER)
    assert P.abmelden(ENDPOINT) == {"aktiv": False}


def test_ein_fehlender_wert_schaltet_push_aus(welt, vapid, monkeypatch):
    """Kein Teilbetrieb: ohne privaten Schlüssel wäre jedes Abonnement taub."""
    monkeypatch.setattr(vapid, "vapid_private", "", raising=False)
    _set_user(SAENGER)
    assert P.schluessel() == {"aktiv": False}
    assert _anmelden() == {"aktiv": False}
    assert _abos() == []


def test_mit_schluessel_liefert_nur_den_oeffentlichen(welt, vapid):
    _set_user(SAENGER)
    antwort = P.schluessel()
    assert antwort == {"aktiv": True, "public_key": "oeffentlich-test"}
    # Der PRIVATE Schlüssel verlässt die Datei nie.
    assert "privat-test" not in repr(antwort)


# ── 2. Anmelden / Abmelden ──────────────────────────────────────────────────


def test_anmelden_legt_eine_zeile_an(_aufloesung, welt, vapid):
    assert _anmelden() == {"aktiv": True, "angemeldet": True}
    abos = _abos()
    assert len(abos) == 1
    assert abos[0].endpoint == ENDPOINT
    assert abos[0].benutzer == SAENGER
    assert abos[0].p256dh == P256DH and abos[0].auth == AUTH
    assert abos[0].fehlversuche == 0 and abos[0].zuletzt_ok_am is None
    assert abos[0].angelegt_am is not None


def test_anmelden_ist_idempotent_je_endpoint(_aufloesung, welt, vapid):
    _anmelden()
    _anmelden(p256dh=P256DH.rstrip("g") + "h")  # neuer Schlüssel, selbes Gerät
    abos = _abos()
    assert len(abos) == 1
    assert abos[0].p256dh.endswith("h")


def test_geraetewechsel_haengt_die_zeile_um(_aufloesung, welt, vapid):
    """Andere Person auf demselben Browser: EINE Zeile, neuer Besitzer."""
    _anmelden(konto=SAENGER)
    _anmelden(konto=SAENGER2)
    abos = _abos()
    assert len(abos) == 1
    assert abos[0].benutzer == SAENGER2


def test_zwei_geraete_einer_person_sind_zwei_zeilen(_aufloesung, welt, vapid):
    _anmelden(endpoint=ENDPOINT)
    _anmelden(endpoint=ENDPOINT_2)
    assert len(_abos(SAENGER)) == 2


def test_abmelden_loescht_nur_das_eigene(_aufloesung, welt, vapid):
    _anmelden(konto=SAENGER)
    _anmelden(endpoint=ENDPOINT_2, konto=SAENGER2)
    _set_user(SAENGER)
    assert P.abmelden(ENDPOINT) == {"aktiv": True, "abgemeldet": True}
    assert [a.endpoint for a in _abos()] == [ENDPOINT_2]


def test_abmelden_fremdes_geraet_bleibt_stehen_und_verraet_nichts(_aufloesung, welt, vapid):
    """Die Antwort ist dieselbe wie beim eigenen Gerät — keine Sonde."""
    _anmelden(konto=SAENGER2)
    _set_user(SAENGER)
    assert P.abmelden(ENDPOINT) == {"aktiv": True, "abgemeldet": True}
    assert [a.endpoint for a in _abos()] == [ENDPOINT]


def test_gast_wird_abgewiesen(welt, vapid):
    from diakronos_app.frappe_compat.exceptions import PermissionError as FP
    for fn in (P.schluessel, lambda: P.anmelden(ENDPOINT, P256DH, AUTH),
               lambda: P.abmelden(ENDPOINT)):
        _set_user(GAST)
        with pytest.raises(FP):
            fn()
    _set_user("")
    with pytest.raises(FP):
        P.schluessel()
    assert _abos() == []


# ── 3. Endpunkt-Prüfung (Allowlist + SSRF) ──────────────────────────────────


@pytest.mark.parametrize("endpoint", [
    "http://fcm.googleapis.com/x",                   # kein https
    "https://127.0.0.1/x",                           # loopback (IP-Literal)
    "https://localhost/x",                           # loopback per Name
    "https://[::1]/x",                               # loopback IPv6
    "https://10.1.2.3/x",                            # privat
    "https://172.16.0.5/x",                          # privat
    "https://192.168.1.11/x",                        # privates Netz (die App selbst)
    "https://169.254.169.254/latest/meta-data",      # link-lokal (Metadaten)
    "https://0.0.0.0/x",                             # unspecified
    "https://[fe80::1]/x",                           # link-lokal IPv6
    "https://gibt-es-nicht.invalid/x",               # fremder Dienst
    "https://user:pw@fcm.googleapis.com/x",          # Zugangsdaten
    "ftp://fcm.googleapis.com/x",                    # falsches Schema
    "fcm.googleapis.com/x",                          # kein Schema
    "",                                              # leer
    "https://fcm.googleapis.com:8443/x",             # falscher Port (R1/2)
    "https://fcm.googleapis.com.evil.tld/x",         # Suffix-Falle (R1/2)
    "https://evilfcm.googleapis.com.attacker.tld/x",  # Suffix-Falle (R1/2)
    "https://xnotify.windows.com/x",                 # Suffix-Falle (R1/2)
    "https://.push.apple.com/x",                     # Suffix allein
    "https://evil.push.services.mozilla.com.attacker.tld/x",  # Suffix-Falle
])
def test_endpunkt_pruefung_weist_ab(_aufloesung, welt, vapid, endpoint):
    """Ein Ziel außerhalb der Allowlist wird NIE gespeichert.

    Geprüft über den ECHTEN Endpunkt (``anmelden``) — nicht nur über die
    Hilfsfunktion: was nicht durchkommt, steht auch nicht in der Tabelle.
    """
    from diakronos_app.frappe_compat.exceptions import ValidationError

    _set_user(SAENGER)
    with pytest.raises(ValidationError):
        P.anmelden(endpoint, P256DH, AUTH)
    assert _abos() == []


@pytest.mark.parametrize("endpoint", [
    ENDPOINT,
    ENDPOINT_2,
    MOZILLA,
    "https://push.apple.com/x",                     # Suffix-Wurzel selbst? s. u.
    "https://web.push.apple.com/x",
    "https://wns2-par02p.notify.windows.com/x",
    "https://fcm.googleapis.com/x",                 # ohne Port (443)
    "https://fcm.googleapis.com:443/x",             # Port 443 ausdrücklich
])
def test_erlaubte_hosts_kommen_durch(_aufloesung, welt, vapid, endpoint):
    """Gegenprobe: die vier Dienste kommen durch (kein Pauschal-Nein)."""
    if endpoint == "https://push.apple.com/x":
        # Die Allowlist ist ``.push.apple.com`` (Unterdomänen) — die Wurzel
        # ``push.apple.com`` selbst ist KEIN Geräte-Host.
        from diakronos_app.frappe_compat.exceptions import ValidationError

        with pytest.raises(ValidationError):
            P.pruefe_endpoint(endpoint)
        return
    assert P.pruefe_endpoint(endpoint) == endpoint


#: CHAT-10a-2/1 (SSRF): ``urlsplit`` (geprüft) und ``urllib3`` (angefahren)
#: lesen die Authority unterschiedlich. Jede dieser Adressen bestand die alte
#: Allowlist und wäre an ``127.0.0.1`` bzw. ``evil.tld`` gegangen.
PARSER_FALLEN = [
    "https://127.0.0.1\\.push.apple.com/x",          # Backslash im Host
    "https://evil.tld\\x.notify.windows.com/x",      # Backslash trennt ab
    "https://evil.tld%5cx.notify.windows.com/x",     # kodierter Backslash
    "https://evil%2etld.notify.windows.com/x",       # kodierter Punkt
    "https://fcm.googleapis.com\t/x",                # Tabulator
    "https://fcm.googleapis.com\n/x",                # Zeilenumbruch
    "https://web.push.apple.com\\@evil.tld/x",       # Backslash + Klammeraffe
    "https://fcm.googleapis.com#@evil.tld/x",        # Fragment als Trenner
    "https://fcm.googleapis.com.\u00e4.de/x",         # Unicode im Host
]


@pytest.mark.parametrize("endpoint", PARSER_FALLEN)
def test_parser_differenz_wird_abgewiesen(_aufloesung, welt, vapid, endpoint):
    """Ein Endpunkt, den zwei Parser VERSCHIEDEN lesen, wird abgewiesen.

    Geprüft werden alle drei Wege: die reine Prüfung, ``anmelden`` und
    ``abmelden`` — und dass keine Zeile entsteht.
    """
    from diakronos_app.frappe_compat.exceptions import ValidationError

    with pytest.raises(ValidationError):
        P.pruefe_endpoint(endpoint)
    _set_user(SAENGER)
    with pytest.raises(ValidationError):
        P.anmelden(endpoint, P256DH, AUTH)
    with pytest.raises(ValidationError):
        P.abmelden(endpoint)
    assert _abos() == []


@pytest.mark.parametrize("endpoint", PARSER_FALLEN)
def test_parser_differenz_wird_im_versand_abgewiesen(welt, vapid, kein_netz,
                                                    endpoint):
    """Auch eine ZEILE mit solcher Adresse (Bestand/Import) wird nie angeschrieben."""
    with dbmod.SessionLocal.begin() as s:
        s.add(PushAbonnement(
            endpoint=endpoint, benutzer=SAENGER, p256dh=P256DH, auth=AUTH,
            angelegt_am=datetime(2026, 11, 20, 12, 0, 0),
            zuletzt_ok_am=None, fehlversuche=0,
        ))
    assert P.sende_auftrag(SAENGER, {"titel": "T", "text": "X", "ziel": "#/n/g"}) == 0
    assert _abos(SAENGER) == []
    assert kein_netz["aufrufe"] == []


def test_die_formpruefung_ist_streng():
    """Der Host muss ``[a-z0-9-]+(\.[a-z0-9-]+)*\.?`` erfüllen."""
    for gut in ("fcm.googleapis.com", "wns2-par02p.notify.windows.com",
                "web.push.apple.com", "fcm.googleapis.com."):
        assert P._hostform_streng(gut) is True, gut
    for schlecht in ("", "fcm..googleapis.com", "fcm_googleapis.com",
                     "127.0.0.1\.push.apple.com", "evil tld", "evil%2etld",
                     "fcm.googleapis.com/x"):
        assert P._hostform_streng(schlecht) is False, schlecht


def test_zweiter_parser_muss_zustimmen(monkeypatch):
    """Weicht ``urllib3`` ab, wird abgewiesen — auch wenn die Form passt."""
    import urllib3.util

    monkeypatch.setattr(urllib3.util, "parse_url",
                        lambda *_a, **_kw: urllib3.util.parse_url("https://127.0.0.1/x"))
    from diakronos_app.frappe_compat.exceptions import ValidationError

    with pytest.raises(ValidationError):
        P.pruefe_endpoint("https://fcm.googleapis.com/x", aufloesen=False)


def test_legitime_endpunkte_bleiben_erlaubt():
    """Gegenprobe: die vier Dienste kommen an der Formprüfung vorbei."""
    for gut in (ENDPOINT, MOZILLA, "https://web.push.apple.com/x/y",
                "https://wns2-par02p.notify.windows.com/x"):
        assert P._zerlege_endpoint(gut).host in {
            "fcm.googleapis.com", "updates.push.services.mozilla.com",
            "web.push.apple.com", "wns2-par02p.notify.windows.com"}, gut


def test_endpunkt_zu_lang_wird_abgewiesen(_aufloesung, welt, vapid):
    from diakronos_app.frappe_compat.exceptions import ValidationError

    lang = f"https://{_FCM_HOST}/" + "a" * (P.ENDPOINT_MAX + 1)
    with pytest.raises(ValidationError):
        P.pruefe_endpoint(lang)
    _set_user(SAENGER)
    with pytest.raises(ValidationError):
        P.anmelden(lang, P256DH, AUTH)
    assert _abos() == []


def test_hostname_wird_nicht_mehr_aufgeloest_bei_erlaubtem_dienst(monkeypatch):
    """R1/2: ``socket.setdefaulttimeout`` ist weg — die Auflösung läuft ohne
    prozessweite Frist."""
    import ast
    import inspect

    baum = ast.parse(inspect.getsource(P._host_ist_oeffentlich).lstrip())
    # Nur der CODE zählt, nicht der Docstring (der erklärt, warum es weg ist).
    rumpf = [n for n in ast.walk(baum) if isinstance(n, ast.Call)
             or isinstance(n, ast.Attribute)]
    assert not [n for n in rumpf
                if "setdefaulttimeout" in ast.dump(n)], \
        "setdefaulttimeout ist prozessweit — gehört nicht in die Prüfung"
    # Und der echte Aufruf: ein erlaubter Dienst kommt ohne diese Frist durch.
    import socket as _socket
    import time as _time

    echtes = _socket.getaddrinfo
    monkeypatch.setattr(
        _socket, "getaddrinfo",
        lambda host, port, *a, **kw: [(2, 1, 6, "", ("93.184.216.34", port or 0))])
    vorher = _socket.getdefaulttimeout()
    start = _time.monotonic()
    assert P._host_ist_oeffentlich("fcm.googleapis.com") is True
    assert _socket.getdefaulttimeout() == vorher
    assert _time.monotonic() - start < 5
    monkeypatch.setattr(_socket, "getaddrinfo", echtes)


@pytest.mark.parametrize("feld, wert", [
    ("p256dh", ""),
    ("auth", ""),
    ("p256dh", "kein base64!!! <script>"),
    ("auth", "a" * (P.SCHLUESSEL_MAX + 1)),
])
def test_schluessel_werden_als_base64url_geprueft(_aufloesung, welt, vapid, feld, wert):
    from diakronos_app.frappe_compat.exceptions import ValidationError

    kwargs = {"p256dh": P256DH, "auth": AUTH, feld: wert}
    _set_user(SAENGER)
    with pytest.raises(ValidationError):
        P.anmelden(ENDPOINT, **kwargs)
    assert _abos() == []


def test_fehlender_endpunkt_wird_abgewiesen(_aufloesung, welt, vapid):
    from diakronos_app.frappe_compat.exceptions import ValidationError

    _set_user(SAENGER)
    with pytest.raises(ValidationError):
        P.anmelden(None, P256DH, AUTH)


def test_abmelden_loest_keinen_namen_auf(welt, vapid, monkeypatch):
    """R1/6: ``abmelden`` prüft Syntax/Allowlist, aber KEINE DNS-Auflösung.

    Ein DNS-Ausfall darf das Abmelden nicht blockieren — und ein Gerät, dessen
    Name heute nicht auflöst, soll sich trotzdem abmelden können.
    """
    import socket as _socket

    def _kein_dns(*_args, **_kwargs):
        raise AssertionError("abmelden darf keinen Namen auflösen")

    monkeypatch.setattr(_socket, "getaddrinfo", _kein_dns)
    _set_user(SAENGER)
    with dbmod.SessionLocal.begin() as s:
        s.add(PushAbonnement(
            endpoint=ENDPOINT, benutzer=SAENGER, p256dh=P256DH, auth=AUTH,
            angelegt_am=datetime(2026, 11, 20, 12, 0, 0),
            zuletzt_ok_am=None, fehlversuche=0,
        ))
    assert P.abmelden(ENDPOINT) == {"aktiv": True, "abgemeldet": True}
    assert _abos() == []


def test_abmelden_prueft_die_allowlist_trotzdem(welt, vapid):
    """R1/6: die Allowlist gilt auch beim Abmelden (billig, ohne Netz)."""
    from diakronos_app.frappe_compat.exceptions import ValidationError

    _set_user(SAENGER)
    with pytest.raises(ValidationError):
        P.abmelden("https://127.0.0.1/x")
    with pytest.raises(ValidationError):
        P.abmelden("http://fcm.googleapis.com/x")


# ── 4. Glocke → Versandauftrag (ohne Inhalt) ────────────────────────────────


def _glocken_schreiben(gespraech: str, anzahl: int = 3,
                       konto: str = SAENGER2) -> str:
    """Eine GESPRÄCHS-Glocke über den echten Chat-Weg schreiben lassen."""
    from diakronos_app.api import chat as C
    from test_chat4a_glocke import _neueste  # noqa: PLC0415 — Fixture-Hilfe

    return C.chat_glocken_buendeln(
        jetzt=_neueste(gespraech) + timedelta(minutes=10))


def test_chat_glocke_ergibt_einen_auftrag_ohne_inhalt(welt, gespraech,
                                                      vapid, eingereiht,
                                                      monkeypatch):
    """Die gebündelte Glocke reiht GENAU EINEN Versand ein — mit der Glocke,
    nicht mit dem Nachrichtentext."""
    from diakronos_app.api import chat as C

    _teilnahme(gespraech, SAENGER2)
    _set_user(SAENGER)
    for i in range(3):
        C.senden(gespraech, f"Streng geheimer Text {i}")
    _set_user(HV)
    auftraege_vorher = len(eingereiht)
    from test_chat4a_glocke import _neueste

    geschrieben = C.chat_glocken_buendeln(
        jetzt=_neueste(gespraech) + timedelta(minutes=10))
    assert geschrieben >= 1

    neue = [a for a in eingereiht[auftraege_vorher:] if a["func"] is P.sende_auftrag]
    assert neue, "kein Versandauftrag eingereiht"
    # Die Glocke geht an die LESENDEN (Saenger2/MV …) — der Verfasser nicht.
    empfaenger = {a["konto"] for a in neue}
    assert SAENGER not in empfaenger
    assert SAENGER2 in empfaenger
    for a in neue:
        assert a["queue"] == "default"
        nutzlast = a["nutzlast"]
        assert set(nutzlast) == set(P.NUTZLAST_FELDER)
        assert nutzlast["ziel"] == f"#/nachrichten/{gespraech}"
        # KEIN Nachrichteninhalt, KEIN Absendername.
        zusammen = " ".join(nutzlast.values())
        assert "Streng geheimer Text" not in zusammen
        assert SAENGER not in zusammen
        assert "neue Nachrichten" in nutzlast["titel"] or \
            "neue Nachricht" in nutzlast["titel"]


def test_nutzlast_ist_woertlich_die_glocke(welt, gespraech, vapid, eingereiht):
    """``titel``/``text`` sind DIE Glockenzeile — nicht eine zweite Fassung."""
    from diakronos_app.api import chat as C
    from diakronos_app.models.core import NotificationLog
    from test_chat4a_glocke import _neueste

    _teilnahme(gespraech, SAENGER2)
    _set_user(SAENGER)
    C.senden(gespraech, "Hallo")
    _set_user(HV)
    C.chat_glocken_buendeln(jetzt=_neueste(gespraech) + timedelta(minutes=10))

    with dbmod.SessionLocal() as s:
        glocke = s.query(NotificationLog).filter(
            NotificationLog.for_user == SAENGER2,
            NotificationLog.document_type == "chat_gespraech",
        ).one()
        titel, inhalt = glocke.subject, glocke.email_content
    auftrag = next(a for a in eingereiht
                   if a["func"] is P.sende_auftrag and a["konto"] == SAENGER2)
    assert auftrag["nutzlast"] == {"titel": titel, "text": inhalt,
                                   "ziel": f"#/nachrichten/{gespraech}"}


def test_stumm_ergibt_keinen_auftrag(welt, gespraech, vapid, eingereiht):
    from diakronos_app.api import chat as C
    from test_chat4a_glocke import _neueste

    _teilnahme(gespraech, SAENGER2)
    _set_user(SAENGER2)
    C.stumm_setzen(gespraech, True)
    _set_user(SAENGER)
    C.senden(gespraech, "Hallo")
    _set_user(HV)
    C.chat_glocken_buendeln(jetzt=_neueste(gespraech) + timedelta(minutes=10))

    assert not [a for a in eingereiht
                if a["func"] is P.sende_auftrag and a["konto"] == SAENGER2]


def test_ohne_vapid_kein_auftrag(welt, gespraech, ohne_vapid, eingereiht):
    """Push AUS: die Glocke entsteht, der Versand NICHT (kein Fehler)."""
    from diakronos_app.api import chat as C
    from test_chat4a_glocke import _neueste

    _teilnahme(gespraech, SAENGER2)
    _set_user(SAENGER)
    C.senden(gespraech, "Hallo")
    _set_user(HV)
    geschrieben = C.chat_glocken_buendeln(
        jetzt=_neueste(gespraech) + timedelta(minutes=10))
    assert geschrieben >= 1
    assert not [a for a in eingereiht if a["func"] is P.sende_auftrag]


def test_erwaehnung_push_trotz_stumm(runden_welt, vapid, eingereiht):
    """Erwähnung klingelt auch bei stumm — wie die Glocke (Konzept S4).

    Dieselbe Runde und derselbe Weg wie ``test_chat9a_erwaehnung`` (Runde
    Anna/Bert/Clara, Anna legt an) — dort ist belegt, dass die Glocke bei
    stumm geschaltetem Gespräch trotzdem entsteht. Hier folgt der Push.
    """
    from test_chat7b_runden import ANNA, BERT, CLARA, MI
    from test_chat9a_erwaehnung import _runde_anlegen, _senden, _stumm

    runde = _runde_anlegen("Kigo-Vorbereitung", [MI[BERT], MI[CLARA]])
    _stumm(runde["name"], BERT, True)
    _senden(runde["name"], "Hallo @Bert", ANNA, erwaehnt=[MI[BERT]])

    auftraege = [a for a in eingereiht
                 if a["func"] is P.sende_auftrag and a["konto"] == BERT]
    assert auftraege, "Erwähnung bei stumm muss pushen wie die Glocke"
    nutzlast = auftraege[-1]["nutzlast"]
    assert "erwähnt" in nutzlast["titel"].lower() or \
        "erwähnt" in nutzlast["text"].lower()
    assert "Hallo @Bert" not in " ".join(nutzlast.values())
    assert nutzlast["ziel"] == f"#/nachrichten/{runde['name']}"


def test_nur_zahl_ergibt_keinen_auftrag(welt, gespraech, vapid, eingereiht):
    """Teilweises Lesen führt die Zahl nach — es weckt niemanden."""
    from diakronos_app.api import chat as C
    from test_chat4a_glocke import _neueste

    _teilnahme(gespraech, SAENGER2)
    _set_user(SAENGER)
    C.senden(gespraech, "eins")
    C.senden(gespraech, "zwei")
    _set_user(HV)
    C.chat_glocken_buendeln(jetzt=_neueste(gespraech) + timedelta(minutes=10))
    vorher = len([a for a in eingereiht if a["func"] is P.sende_auftrag])

    _set_user(SAENGER2)
    seite = C.verlauf(gespraech)
    aelteste = seite["nachrichten"][0]["name"]
    C.lesestand_setzen(gespraech, aelteste)  # nur bis zur ÄLTESTEN gelesen

    nachher = [a for a in eingereiht if a["func"] is P.sende_auftrag]
    assert len(nachher) == vorher


# ── 4f. Review R1/8: Kontaktsperre und Umfrage ──────────────────────────────


def test_kontaktsperre_erwaehnung_ohne_glocke_ohne_push(runden_welt, vapid,
                                                        eingereiht):
    """R1/8: Sperre → keine Glocke → KEIN Push-Auftrag.

    Die Sperre darf nie erkennbar sein: sie unterdrückt die Glocke, und der
    Push hängt an der Glocke (nicht an der Erwähnung).
    """
    from test_chat7b_runden import ANNA, BERT, CLARA, MI, _sperren
    from test_chat9a_erwaehnung import _runde_anlegen, _senden

    runde = _runde_anlegen("Kigo-Vorbereitung", [MI[BERT], MI[CLARA]])
    _sperren(MI[ANNA], BERT)  # Anna sperrt Bert
    _senden(runde["name"], "Hallo @Bert", ANNA, erwaehnt=[MI[BERT]])

    assert not [a for a in eingereiht
                if a["func"] is P.sende_auftrag and a["konto"] == BERT], \
        "die Sperre darf keinen Push erzeugen"


def test_umfrage_start_ergibt_einen_auftrag(welt, gespraech, vapid, eingereiht):
    """R1/8: die Umfrage-Start-Glocke zieht einen Push nach sich."""
    from test_chat4b_umfrage_glocke import _teilnahme as _t4b, _umfrage

    _t4b(gespraech, SAENGER2)
    _umfrage(gespraech, SAENGER)

    auftraege = [a for a in eingereiht
                 if a["func"] is P.sende_auftrag and a["konto"] == SAENGER2]
    assert auftraege, "Umfrage-Start muss pushen wie die Glocke"
    nutzlast = auftraege[-1]["nutzlast"]
    assert set(nutzlast) == set(P.NUTZLAST_FELDER)
    assert "Umfrage" in nutzlast["titel"]
    assert nutzlast["ziel"].startswith("#/nachrichten/")
    # Kein Fragetext, keine Option, kein Name des Anlegenden.
    zusammen = " ".join(nutzlast.values())
    assert "Wann proben" not in zusammen
    assert SAENGER not in zusammen


def test_umfrage_start_bei_stumm_kein_auftrag(welt, gespraech, vapid, eingereiht):
    """R1/8: stumm → keine Start-Glocke → kein Auftrag."""
    from diakronos_app.api import chat as C
    from test_chat4b_umfrage_glocke import _teilnahme as _t4b, _reset, _umfrage

    _t4b(gespraech, SAENGER2)
    _set_user(SAENGER2)
    C.stumm_setzen(gespraech, True)
    _reset()
    eingereiht.clear()

    _umfrage(gespraech, SAENGER)

    assert not [a for a in eingereiht
                if a["func"] is P.sende_auftrag and a["konto"] == SAENGER2]


def test_umfrage_erinnerung_ergibt_einen_auftrag(welt, gespraech, vapid,
                                                 eingereiht):
    """R1/8: die Erinnerung vor der Frist pusht wie die Glocke."""
    from test_chat4b_umfrage_glocke import (
        _erinnerung,
        _mit_frist,
        _teilnahme as _t4b,
    )

    _t4b(gespraech, SAENGER2)
    name, frist = _mit_frist(gespraech, stunden=48)
    _erinnerung(jetzt=frist - timedelta(hours=23))

    auftraege = [a for a in eingereiht
                 if a["func"] is P.sende_auftrag and a["konto"] == SAENGER2]
    assert auftraege, "die Umfrage-Erinnerung muss pushen wie die Glocke"
    assert "morgen" in auftraege[-1]["nutzlast"]["titel"].lower() or \
        "endet" in auftraege[-1]["nutzlast"]["titel"].lower()


def test_umfrage_erinnerung_bei_stumm_kein_auftrag(welt, gespraech, vapid,
                                                   eingereiht):
    """R1/8: stumm → die Erinnerung schreibt die Glocke nicht fort → kein Push."""
    from diakronos_app.api import chat as C
    from test_chat4b_umfrage_glocke import (
        _erinnerung,
        _mit_frist,
        _reset,
        _teilnahme as _t4b,
    )

    _t4b(gespraech, SAENGER2)
    name, frist = _mit_frist(gespraech, stunden=48)
    _set_user(SAENGER2)
    C.stumm_setzen(gespraech, True)
    _reset()
    # Die Start-Glocke (und ihr Push) stand vor dem Stummschalten — für die
    # Erinnerung zählt nur, was NACH dem Stummschalten entsteht.
    eingereiht.clear()

    _erinnerung(jetzt=frist - timedelta(hours=23))
    assert not [a for a in eingereiht
                if a["func"] is P.sende_auftrag and a["konto"] == SAENGER2]


def test_versand_auftrag_ohne_empfaenger_ist_erlaubt(welt, vapid, eingereiht):
    """Einen Auftrag auch ohne Abonnement einzureihen ist kein Fehler —
    der Job findet dann einfach nichts (und tut nichts)."""
    assert P.versand_auftrag(SAENGER, {"titel": "T", "text": "X",
                                       "ziel": "#/nachrichten/g"}) is True


@pytest.mark.parametrize("nutzlast", [
    None,
    {},
    {"titel": "T", "text": "X"},                       # ziel fehlt
    {"titel": "T", "text": "X", "ziel": ""},           # leer
    {"titel": "T", "text": "X", "ziel": "#/x", "extra": "y"},
    {"titel": 7, "text": "X", "ziel": "#/x"},
])
def test_kaputte_nutzlast_ergibt_keinen_auftrag(welt, vapid, eingereiht, nutzlast):
    assert P.versand_auftrag(SAENGER, nutzlast) is False
    assert eingereiht == []


# ── 4b. Review R1: pywebpush fehlt (eigener Fehler, zählt nicht) ────────────


def test_ohne_pywebpush_wird_kein_auftrag_eingereiht(welt, vapid, monkeypatch):
    """R1/3: fehlt das Paket, entsteht GAR KEIN Auftrag (eine Warnung)."""
    from diakronos_app.frappe_compat import queue as qmod

    monkeypatch.setattr(P, "_pywebpush_da", lambda: False)
    monkeypatch.setattr(P, "_ohne_pywebpush_gemeldet", False)
    auftraege: list[dict] = []
    monkeypatch.setattr(qmod, "enqueue",
                        lambda *a, **kw: auftraege.append({"a": a, "kw": kw}))
    assert P.versand_auftrag(SAENGER, {"titel": "T", "text": "X",
                                       "ziel": "#/nachrichten/g"}) is False
    assert auftraege == []


def test_ohne_pywebpush_bleiben_abos_bei_zehn_glocken_bestehen(welt, vapid,
                                                               monkeypatch):
    """R1/3: zehn Glocken ohne pywebpush → KEIN Abo gelöscht, kein Zähler.

    Ohne die Trennung "eigener Fehler" zählte jeder Versand als Fehlversuch
    des Geräts, und nach fünf Läufen wäre ein gesundes Abonnement weg.
    """
    _abo()
    monkeypatch.setattr(P, "_pywebpush_da", lambda: True)  # Job läuft an
    # ``_senden_an`` läuft ECHT und findet kein pywebpush → VAPID_KONFIG.
    # Das Paket ausdrücklich verbergen: im gebauten Image ist es installiert.
    import sys
    monkeypatch.setitem(sys.modules, "pywebpush", None)
    nutzlast = {"titel": "T", "text": "X", "ziel": "#/n/g"}
    for _ in range(10):
        assert P.sende_auftrag(SAENGER, nutzlast) == 0
    abos = _abos(SAENGER)
    assert len(abos) == 1, "ein eigener Konfigurationsfehler darf kein Abo löschen"
    assert abos[0].fehlversuche == 0


def test_sende_auftrag_ohne_pywebpush_raeumt_nichts_weg(welt, vapid, monkeypatch):
    """R1/3 (Job-Seite): auch der rq-Job selbst sendet ohne Paket nicht."""
    _abo()
    monkeypatch.setattr(P, "_pywebpush_da", lambda: False)
    assert P.sende_auftrag(SAENGER, {"titel": "T", "text": "X", "ziel": "#/n/g"}) == 0
    assert len(_abos(SAENGER)) == 1


def test_konfigurationsfehler_zaehlt_nicht_als_fehlversuch(welt, vapid, kein_netz):
    """R1/3: ``VAPID_KONFIG``/``VAPID_AUS`` → kein Zähler, kein Löschen."""
    _abo(fehlversuche=2)
    kein_netz["naechstes"] = P.VAPID_KONFIG
    P.sende_auftrag(SAENGER, {"titel": "T", "text": "X", "ziel": "#/n/g"})
    abo = _abos(SAENGER)[0]
    assert abo.fehlversuche == 2
    kein_netz["naechstes"] = P.VAPID_AUS
    P.sende_auftrag(SAENGER, {"titel": "T", "text": "X", "ziel": "#/n/g"})
    assert _abos(SAENGER)[0].fehlversuche == 2


# ── 4c. Review R1/2: Allowlist auch im Versand ──────────────────────────────


def test_abo_ausserhalb_der_allowlist_wird_im_versand_geloescht(welt, vapid,
                                                               kein_netz):
    """Ein Bestands-Abo bei einem fremden Host wird nicht angeschrieben."""
    _abo()
    with dbmod.SessionLocal.begin() as s:
        s.add(PushAbonnement(
            endpoint="https://fremder-dienst.example/x", benutzer=SAENGER,
            p256dh=P256DH, auth=AUTH,
            angelegt_am=datetime(2026, 11, 20, 12, 0, 0),
            zuletzt_ok_am=None, fehlversuche=0,
        ))
    assert P.sende_auftrag(SAENGER, {"titel": "T", "text": "X", "ziel": "#/n/g"}) == 1
    assert [a.endpoint for a in _abos(SAENGER)] == [ENDPOINT]
    assert [a["endpoint"] for a in kein_netz["aufrufe"]] == [ENDPOINT]


def test_abo_mit_redirect_ziel_wird_im_versand_geloescht(welt, vapid, kein_netz):
    """Auch ein Abo, das nur per Suffix-Falle durchkäme, fliegt raus."""
    with dbmod.SessionLocal.begin() as s:
        s.add(PushAbonnement(
            endpoint="https://fcm.googleapis.com.evil.tld/x", benutzer=SAENGER,
            p256dh=P256DH, auth=AUTH,
            angelegt_am=datetime(2026, 11, 20, 12, 0, 0),
            zuletzt_ok_am=None, fehlversuche=0,
        ))
    assert P.sende_auftrag(SAENGER, {"titel": "T", "text": "X", "ziel": "#/n/g"}) == 0
    assert _abos(SAENGER) == []
    assert kein_netz["aufrufe"] == []


# ── 4d. Review R1/4: höchstens zehn Geräte je Konto ─────────────────────────


def test_hoechstens_zehn_abos_je_konto(welt, vapid, _aufloesung):
    """Das ÄLTESTE Gerät wird verdrängt — das neue bleibt, zehn stehen."""
    for i in range(P.MAX_ABOS_JE_KONTO):
        _anmelden(endpoint=f"https://{_FCM_HOST}/gerät{i}", p256dh=P256DH)
    assert len(_abos(SAENGER)) == P.MAX_ABOS_JE_KONTO
    _anmelden(endpoint=f"https://{_FCM_HOST}/gerät{99}", p256dh=P256DH)
    abos = sorted(_abos(SAENGER), key=lambda a: a.endpoint)
    assert len(abos) == P.MAX_ABOS_JE_KONTO
    assert f"https://{_FCM_HOST}/gerät0" not in [a.endpoint for a in abos]
    assert f"https://{_FCM_HOST}/gerät99" in [a.endpoint for a in abos]


def test_die_grenze_gilt_je_konto(welt, vapid, _aufloesung):
    """Zwei Konten haben je zehn Plätze — das eine verdrängt das andere nicht."""
    for i in range(P.MAX_ABOS_JE_KONTO):
        _anmelden(endpoint=f"https://{_FCM_HOST}/a{i}", konto=SAENGER)
        _anmelden(endpoint=f"https://{_FCM_HOST}/b{i}", konto=SAENGER2)
    _anmelden(endpoint=f"https://{_FCM_HOST}/neu", konto=SAENGER)
    assert len(_abos(SAENGER)) == P.MAX_ABOS_JE_KONTO
    assert len(_abos(SAENGER2)) == P.MAX_ABOS_JE_KONTO


# ── 4e. Review R1/7: Push erst NACH dem Commit ──────────────────────────────


def test_push_erst_nach_dem_commit(welt, gespraech, vapid, eingereiht):
    """Während der Transaktion steht kein Auftrag — nach dem Commit schon."""
    from diakronos_app.api import chat as C
    from test_chat4a_glocke import _neueste

    _teilnahme(gespraech, SAENGER2)
    _set_user(SAENGER)
    C.senden(gespraech, "Hallo")
    _set_user(HV)
    vorher = len(eingereiht)
    C.chat_glocken_buendeln(jetzt=_neueste(gespraech) + timedelta(minutes=10))
    # Nach dem Commit der Glocken-Transaktion ist der Auftrag da.
    assert [a for a in eingereiht[vorher:] if a["func"] is P.sende_auftrag]


def test_rollback_ergibt_keinen_push(welt, gespraech, vapid, eingereiht):
    """R1/7: eine zurückgerollte Glocke hinterlässt KEINEN Push."""
    from diakronos_app.api import chat as C
    from diakronos_app.models.chat import ChatGespraech

    _teilnahme(gespraech, SAENGER2)
    _set_user(HV)
    vorher = len(eingereiht)
    with pytest.raises(RuntimeError):
        with dbmod.SessionLocal.begin() as s:
            g = s.get(ChatGespraech, gespraech)
            C._push_nach_glocke(s, SAENGER2, titel="T", inhalt="X",
                                gespraech=g.name)
            raise RuntimeError("Fachfehler — Rollback")
    assert not [a for a in eingereiht[vorher:] if a["func"] is P.sende_auftrag]


# ── 4f. CHAT-10a-2/2: Merker je Transaktion (Savepoint, close) ──────────────


def _push_auftraege(auftraege) -> list[str]:
    return [a["konto"] for a in auftraege if a["func"] is P.sende_auftrag]


def test_savepoint_rollback_behaelt_das_erste_paar(welt, gespraech, vapid,
                                                   eingereiht):
    """2a: ein zurückgenommener Savepoint nimmt NUR seine eigenen Aufträge mit."""
    from diakronos_app.api import chat as C
    from diakronos_app.models.chat import ChatGespraech

    with dbmod.SessionLocal.begin() as s:
        g = s.get(ChatGespraech, gespraech)
        C._push_nach_glocke(s, SAENGER, titel="T1", inhalt="X", gespraech=g.name)
        with pytest.raises(RuntimeError):
            with s.begin_nested():
                C._push_nach_glocke(s, SAENGER2, titel="T2", inhalt="X",
                                    gespraech=g.name)
                raise RuntimeError("Fachfehler im Savepoint")
    # Der Commit der äußeren Transaktion reicht genau den ERSTEN Auftrag ein.
    assert _push_auftraege(eingereiht) == [SAENGER]


def test_savepoint_commit_gibt_an_die_aeussere_transaktion(welt, gespraech,
                                                           vapid, eingereiht):
    """Ein GUT ausgegangener Savepoint gibt seine Aufträge nach außen ab."""
    from diakronos_app.api import chat as C
    from diakronos_app.models.chat import ChatGespraech

    with dbmod.SessionLocal.begin() as s:
        g = s.get(ChatGespraech, gespraech)
        with s.begin_nested():
            C._push_nach_glocke(s, SAENGER, titel="T1", inhalt="X",
                                gespraech=g.name)
        assert _push_auftraege(eingereiht) == [], "noch nicht committet"
    assert _push_auftraege(eingereiht) == [SAENGER]


def test_close_ohne_commit_hinterlaesst_keinen_merker(welt, gespraech, vapid,
                                                      eingereiht):
    """2b: ``close()`` ohne Commit — nichts eingereiht UND nichts gemerkt.

    Danach muss eine NEUE Sitzung wieder pushen können. Mit dem alten
    ``id(session)``-Merker blieb ein Eintrag stehen, der bei wiederverwendeter
    Adresse den Listener der nächsten Sitzung verhinderte.
    """
    from diakronos_app.api import chat as C
    from diakronos_app.models.chat import ChatGespraech

    s = dbmod.SessionLocal()
    s.begin()
    g = s.get(ChatGespraech, gespraech)
    C._push_nach_glocke(s, SAENGER, titel="T1", inhalt="X", gespraech=g.name)
    s.close()
    assert _push_auftraege(eingereiht) == []

    # Dieselbe Adresse, neue Sitzung: der Listener muss greifen.
    s2 = dbmod.SessionLocal()
    s2.begin()
    g2 = s2.get(ChatGespraech, gespraech)
    C._push_nach_glocke(s2, SAENGER2, titel="T2", inhalt="X", gespraech=g2.name)
    s2.commit()
    s2.close()
    assert _push_auftraege(eingereiht) == [SAENGER2]


def test_voller_rollback_ergibt_nichts(welt, gespraech, vapid, eingereiht):
    """Voller Rollback: kein Auftrag — auch nicht nach einer weiteren Sitzung."""
    from diakronos_app.api import chat as C
    from diakronos_app.models.chat import ChatGespraech

    with pytest.raises(RuntimeError):
        with dbmod.SessionLocal.begin() as s:
            g = s.get(ChatGespraech, gespraech)
            C._push_nach_glocke(s, SAENGER, titel="T1", inhalt="X",
                                gespraech=g.name)
            raise RuntimeError("Fachfehler — Rollback")
    assert _push_auftraege(eingereiht) == []
    # Und die Sitzung hat nichts zurückgelassen.
    s = dbmod.SessionLocal()
    assert C._AUFTRAG_INFO_SCHLUESSEL not in s.info
    assert C._LISTENER_INFO_SCHLUESSEL not in s.info
    s.close()


def test_merker_haengt_an_der_sitzung_nicht_an_der_adresse():
    """Kein Modul-Dict über ``id(session)`` mehr (Ursache von 2a/2b)."""
    from diakronos_app.api import chat as C

    assert not hasattr(C, "_PUSH_AUF_COMMIT")
    assert not hasattr(C, "_PUSH_LISTENER")


# ── 5. Versand (ohne Netz) ──────────────────────────────────────────────────


def _abo(konto=SAENGER, endpoint=ENDPOINT, fehlversuche=0,
         zuletzt_ok_am=None) -> None:
    with dbmod.SessionLocal.begin() as s:
        s.add(PushAbonnement(
            endpoint=endpoint, benutzer=konto, p256dh=P256DH, auth=AUTH,
            angelegt_am=datetime(2026, 11, 20, 12, 0, 0),
            zuletzt_ok_am=zuletzt_ok_am, fehlversuche=fehlversuche,
        ))


def test_versand_setzt_zuletzt_ok(welt, vapid, kein_netz):
    _abo()
    assert P.sende_auftrag(SAENGER, {"titel": "T", "text": "X", "ziel": "#/n/g"}) == 1
    abo = _abos(SAENGER)[0]
    assert abo.zuletzt_ok_am is not None
    assert abo.fehlversuche == 0
    assert kein_netz["aufrufe"][0]["nutzlast"] == {"titel": "T", "text": "X",
                                                   "ziel": "#/n/g"}


def test_versand_410_loescht_das_abonnement(welt, vapid, kein_netz):
    _abo()
    kein_netz["naechstes"] = P.VAPID_WEG
    P.sende_auftrag(SAENGER, {"titel": "T", "text": "X", "ziel": "#/n/g"})
    assert _abos() == []


def test_versand_zaehlt_fehlversuche_und_loescht_ab_fuenf(welt, vapid, kein_netz):
    _abo()
    kein_netz["naechstes"] = P.VAPID_FEHLER
    nutzlast = {"titel": "T", "text": "X", "ziel": "#/n/g"}
    for _ in range(MAX_FEHLVERSUCHE - 1):
        P.sende_auftrag(SAENGER, nutzlast)
        assert len(_abos(SAENGER)) == 1
    assert _abos(SAENGER)[0].fehlversuche == MAX_FEHLVERSUCHE - 1
    P.sende_auftrag(SAENGER, nutzlast)
    assert _abos() == []


def test_versand_ohne_schluessel_sendet_nicht(welt, ohne_vapid, kein_netz):
    _abo()
    assert P.sende_auftrag(SAENGER, {"titel": "T", "text": "X", "ziel": "#/n/g"}) == 0
    assert kein_netz["aufrufe"] == []
    assert len(_abos(SAENGER)) == 1  # nichts gelöscht


def test_versand_geht_nur_an_die_eigene_person(welt, vapid, kein_netz):
    _abo(konto=SAENGER)
    _abo(konto=SAENGER2, endpoint=ENDPOINT_2)
    P.sende_auftrag(SAENGER, {"titel": "T", "text": "X", "ziel": "#/n/g"})
    assert [a["endpoint"] for a in kein_netz["aufrufe"]] == [ENDPOINT]


def test_anmelden_nach_fehlversuchen_setzt_zaehler_zurueck(_aufloesung, welt, vapid):
    _abo(fehlversuche=MAX_FEHLVERSUCHE - 1)
    _anmelden()
    assert _abos(SAENGER)[0].fehlversuche == 0


# ── 5b. Review R1/1: keine Redirects in ``_senden_an`` ──────────────────────


@pytest.fixture()
def fake_pywebpush(monkeypatch):
    """Ein stehendes ``pywebpush`` im ``sys.modules`` — KEIN Netz.

    Damit läuft ``_senden_an`` ECHT (inklusive Sitzungs-Aufbau) und der Test
    kann prüfen, WAS an ``webpush`` übergeben wird.
    """
    import sys
    import types

    import requests

    modul = types.ModuleType("pywebpush")

    class WebPushException(Exception):
        def __init__(self, message="", response=None):
            super().__init__(message)
            self.response = response

    aufrufe: list[dict] = []

    class _Antwort:
        def __init__(self, status_code):
            self.status_code = status_code

    def webpush(**kwargs):
        aufrufe.append(kwargs)
        zustand = fake_pywebpush.zustand.pop(0) if fake_pywebpush.zustand else 201
        if isinstance(zustand, Exception):
            raise zustand
        # Wie das echte ``pywebpush``: es postet ÜBER die übergebene Sitzung
        # (``self.mod_or_session.post``) — nur so ist ``max_redirects = 0``
        # eine Zusage und keine Attrappe.
        sitzung = kwargs.get("requests_session")
        if sitzung is not None:
            fake_pywebpush.gepostet.append(
                (kwargs["subscription_info"]["endpoint"], sitzung))
            sitzung.post(kwargs["subscription_info"]["endpoint"],
                         data=b"x", headers={})
        return _Antwort(zustand)

    modul.WebPushException = WebPushException
    modul.webpush = webpush
    monkeypatch.setitem(sys.modules, "pywebpush", modul)
    monkeypatch.setattr(P, "_pywebpush_da", lambda: True)
    fake_pywebpush.aufrufe = aufrufe  # type: ignore[attr-defined]
    fake_pywebpush.gepostet = []  # type: ignore[attr-defined]
    fake_pywebpush.zustand = []  # type: ignore[attr-defined]
    fake_pywebpush.WebPushException = WebPushException  # type: ignore[attr-defined]
    fake_pywebpush.requests = requests  # type: ignore[attr-defined]
    return fake_pywebpush


def test_senden_an_uebergibt_eine_sitzung_ohne_redirects(welt, vapid,
                                                         fake_pywebpush):
    """R2: der POST geht ÜBER die Sitzung — und die folgt KEINEM Redirect.

    Runde 1 prüfte nur die Eigenschaft ``max_redirects == 0`` an der Sitzung,
    die ``pywebpush`` bekommt. Das belegt nicht, dass der POST überhaupt über
    sie läuft (``requests_session`` könnte ignoriert werden, und der Weg ginge
    wieder über ``requests.post``). Die Attrappe postet deshalb wie das echte
    Paket (``self.mod_or_session.post``); der „Server“ ist ein Ersatz, der
    jeden Request festhält und beweisbar KEINE Umleitung verfolgt. Erwartung:
    genau EIN Request, an den Endpunkt des Abonnements.
    """
    _abo()
    abo = _abos(SAENGER)[0]
    gesehen: list[str] = []
    umleitung = "https://evil.example.net/geraet/geklaut"

    def fake_send(session, method, url, **kwargs):
        gesehen.append(str(url))
        assert session.max_redirects == 0
        return fake_pywebpush.requests.Response()  # leer, nie gefolgt

    sitzung0 = fake_pywebpush.requests.Session
    fake_pywebpush.requests.Session = lambda: _SitzungMitAttrappe(
        fake_send, sitzung0)
    try:
        assert P._senden_an(abo, {"titel": "T", "text": "X",
                                  "ziel": "#/n/g"}) == P.VAPID_OK
    finally:
        fake_pywebpush.requests.Session = sitzung0

    assert gesehen == [abo.endpoint], gesehen
    assert umleitung not in gesehen
    sitzung = fake_pywebpush.aufrufe[0]["requests_session"]
    assert sitzung.max_redirects == 0


class _SitzungMitAttrappe:
    """Eine ``requests.Session``, deren ``post`` nicht ins Netz geht."""

    def __init__(self, send, basis):
        self._send = send
        self.max_redirects = basis().max_redirects
        self.closed = False

    def post(self, url, **kwargs):
        return self._send(self, "POST", url, **kwargs)

    def close(self):
        self.closed = True


def test_redirect_ist_ein_fehlversuch(welt, vapid, fake_pywebpush):
    """R1/1: eine 3xx-Antwort wird NICHT gefolgt, sondern zählt als Fehler."""
    exc = fake_pywebpush.WebPushException("Redirect", response=type(
        "R", (), {"status_code": 302})())
    fake_pywebpush.zustand = [exc]
    _abo()
    assert P._senden_an(_abos(SAENGER)[0], {"titel": "T", "text": "X",
                                           "ziel": "#/n/g"}) == P.VAPID_FEHLER


def test_410_ist_weg_und_500_ist_fehler(welt, vapid, fake_pywebpush):
    """R1: 404/410 → ``VAPID_WEG``; 500 → ``VAPID_FEHLER``."""
    for status, erwartet in ((410, P.VAPID_WEG), (404, P.VAPID_WEG),
                             (500, P.VAPID_FEHLER), (400, P.VAPID_FEHLER)):
        # Je Fall ein eigenes Abo: ``_abos`` wird über dieselbe Sitzung neu
        # gelesen, ein gelöschtes Objekt taugt nicht für den nächsten Durchlauf.
        _abo(endpoint=f"https://{_FCM_HOST}/status{status}", 
             zuletzt_ok_am=None)
        abo = next(a for a in _abos(SAENGER) if a.endpoint.endswith(str(status)))
        exc = fake_pywebpush.WebPushException("x", response=type(
            "R", (), {"status_code": status})())
        fake_pywebpush.zustand = [exc]
        assert P._senden_an(abo, {"titel": "T", "text": "X",
                                  "ziel": "#/n/g"}) == erwartet


def test_netzfehler_zaehlt_schluesselfehler_nicht(welt, vapid, fake_pywebpush):
    """R1/3 auf der ``_senden_an``-Ebene: Transport vs. eigener Fehler."""
    _abo()
    abo = _abos(SAENGER)[0]
    fake_pywebpush.zustand = [fake_pywebpush.requests.ConnectionError("weg")]
    assert P._senden_an(abo, {"titel": "T", "text": "X", "ziel": "#/n/g"}) == P.VAPID_FEHLER
    # Ein kaputter EIGENER Schlüssel kommt nicht mehr bis hierher (``_vapid``
    # schaltet Push dann ab, Review CHAT-10a-2/3). Mit gültigem Schlüssel ist
    # ein ValueError ein Fehler des Versuchs ...
    fake_pywebpush.zustand = [ValueError("Gerät liefert Unsinn")]
    assert P._senden_an(abo, {"titel": "T", "text": "X", "ziel": "#/n/g"}) == P.VAPID_FEHLER
    # ... py_vapids VapidException (z. B. ``sub``) ist dagegen UNSERE Konfiguration.
    VapidException = type("VapidException", (Exception,), {})
    fake_pywebpush.zustand = [VapidException("sub")]
    assert P._senden_an(abo, {"titel": "T", "text": "X", "ziel": "#/n/g"}) == P.VAPID_KONFIG


def test_protokoll_enthaelt_den_endpunkt_nicht_vollstaendig(welt, vapid,
                                                            fake_pywebpush,
                                                            caplog):
    """R1/5: Warnungen nennen nur ``_kurz(endpoint)`` — nie das Token."""
    import logging as _logging

    _abo()
    abo = _abos(SAENGER)[0]
    fake_pywebpush.zustand = [fake_pywebpush.requests.ConnectionError(
        "kaputt " + abo.endpoint)]
    with caplog.at_level(_logging.WARNING, logger="diakronos_app.api.push"):
        P._senden_an(abo, {"titel": "T", "text": "X", "ziel": "#/n/g"})
    zusammen = "\n".join(r.getMessage() for r in caplog.records)
    assert abo.endpoint not in zusammen
    assert abo.endpoint[:32] in zusammen


def test_push_modul_loggt_nirgends_die_volle_url():
    """R1/5 (statisch): im Push-Modul steht kein ``%s`` auf ``abo.endpoint``."""
    quelle = (BACKEND / "src" / "diakronos_app" / "api" / "push.py").read_text(
        encoding="utf-8")
    for zeile in quelle.splitlines():
        if "logger." in zeile and "endpoint" in zeile:
            assert "_kurz(" in zeile, zeile


# ── 6. DSGVO ────────────────────────────────────────────────────────────────


def test_dsgvo_inventar_deckt_das_abonnement():
    from diakronos_app import dsgvo_anonymisierung as D

    assert {"endpoint", "benutzer", "p256dh", "auth"} <= set(
        D.SPALTEN["push_abonnement"])
    assert D.SPALTEN["push_abonnement"]["benutzer"][0] == "zeile_loeschen"
    loeschzeilen = {name for name, _ in D.ZEILEN_LOESCHEN}
    assert "push_abonnement" in loeschzeilen
    assert "push_abonnement" in D.KONTO_ZEILEN


# ── 7. Migration ────────────────────────────────────────────────────────────


def _skripte() -> ScriptDirectory:
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "alembic"))
    return ScriptDirectory.from_config(cfg)


def test_genau_ein_kopf_und_chat10a_haengt_hinter_chat9a():
    skripte = _skripte()
    heads = skripte.get_heads()
    assert len(heads) == 1, f"Kopf(e): {heads}"
    revision = skripte.get_revision("chat10a_push")
    assert revision is not None
    assert revision.down_revision == "chat9a_erwaehnung", revision.down_revision
    assert "Revises: chat9a_erwaehnung" in Path(revision.path).read_text(encoding="utf-8")


@pytest.fixture()
def fresh_engine():
    """Leere SQLite-Engine ohne die Tabelle dieser Karte."""
    from sqlalchemy import create_engine
    from sqlalchemy.pool import StaticPool

    from diakronos_app.models.base import Base

    eng = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(eng)
    with eng.begin() as verbindung:
        verbindung.exec_driver_sql('DROP TABLE IF EXISTS "push_abonnement"')
    yield eng
    eng.dispose()


def test_migration_upgrade_downgrade_upgrade(fresh_engine):
    import importlib.util

    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy import inspect

    pfad = BACKEND / "alembic" / "versions" / "chat10a_push.py"
    spec = importlib.util.spec_from_file_location("chat10a_push", pfad)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)

    with fresh_engine.begin() as verbindung:
        with Operations.context(MigrationContext.configure(verbindung)):
            modul.upgrade()
        insp = inspect(verbindung)
        assert insp.has_table("push_abonnement")
        spalten = {c["name"] for c in insp.get_columns("push_abonnement")}
        for name in ("endpoint", "benutzer", "p256dh", "auth", "angelegt_am",
                     "zuletzt_ok_am", "fehlversuche"):
            assert name in spalten, name
        assert insp.get_pk_constraint("push_abonnement")["constrained_columns"] ==             ["endpoint"]
        namen = {i["name"]: i for i in insp.get_indexes("push_abonnement")}
        assert namen["ix_push_abonnement_benutzer"]["column_names"] == ["benutzer"]

    with fresh_engine.begin() as verbindung:
        with Operations.context(MigrationContext.configure(verbindung)):
            modul.downgrade()
        assert not inspect(verbindung).has_table("push_abonnement")
    with fresh_engine.begin() as verbindung:
        with Operations.context(MigrationContext.configure(verbindung)):
            modul.upgrade()
            modul.upgrade()  # idempotent
        assert inspect(verbindung).has_table("push_abonnement")


# ── 8. SEC-11 ───────────────────────────────────────────────────────────────


def test_sec11_methoden_der_drei_endpunkte():
    from diakronos_app.frappe_compat import registry

    assert registry.methoden_fuer(P.schluessel) == ("GET",)
    assert registry.methoden_fuer(P.anmelden) == ("POST",)
    assert registry.methoden_fuer(P.abmelden) == ("POST",)
    for fn in (P.schluessel, P.anmelden, P.abmelden):
        assert registry.options_for(fn).get("allow_guest") is False


def test_sec11_frappe_pfade_sind_registriert():
    """Die SPA ruft ``diakronos.diakonos.api.push.<name>``."""
    from diakronos_app.frappe_compat import registry

    for name in ("schluessel", "anmelden", "abmelden"):
        assert registry.lookup(f"diakronos.diakonos.api.push.{name}") is not None, name


# ── 9. Werkzeug ─────────────────────────────────────────────────────────────


def test_werkzeug_erzeugt_ein_brauchbares_paar():
    """``tools/vapid_schluessel.py``: 65-Byte-Punkt und 32-Byte-Skalar."""
    import base64
    import subprocess
    import sys

    werkzeug = BACKEND.parent / "tools" / "vapid_schluessel.py"
    if not werkzeug.is_file():  # Image: /app/tools
        werkzeug = Path("/app/tools/vapid_schluessel.py")
    assert werkzeug.is_file(), werkzeug
    ergebnis = subprocess.run(
        [sys.executable, str(werkzeug), "--kontakt", "mailto:test@example.invalid"],
        capture_output=True, text=True, timeout=120, check=True,
    )
    werte = dict(zeile.split("=", 1) for zeile in ergebnis.stdout.splitlines() if "=" in zeile)
    oeffentlich = werte["DIAKRONOS_VAPID_PUBLIC"]
    privat = werte["DIAKRONOS_VAPID_PRIVATE"]
    assert werte["DIAKRONOS_VAPID_KONTAKT"] == "mailto:test@example.invalid"
    punkt = base64.urlsafe_b64decode(oeffentlich + "=" * (-len(oeffentlich) % 4))
    skalar = base64.urlsafe_b64decode(privat + "=" * (-len(privat) % 4))
    assert len(punkt) == 65 and punkt[0] == 0x04
    assert len(skalar) == 32
    # Aus dem privaten Schlüssel muss DERSELBE Punkt folgen.
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

    schluessel = ec.derive_private_key(int.from_bytes(skalar, "big"), ec.SECP256R1())
    abgeleitet = schluessel.public_key().public_bytes(
        Encoding.X962, PublicFormat.UncompressedPoint)
    assert abgeleitet == punkt


# ── Review CHAT-10a-2: Umhängen, Kontakt, Schlüsselformat ──────────────────


def test_umhaengen_verdraengt_nie_das_umgehaengte_geraet(welt, vapid, _aufloesung):
    """Befund 1: das früh angelegte Familiengerät bleibt beim neuen Konto."""
    alt = f"https://{_FCM_HOST}/altgeraet"
    _anmelden(endpoint=alt, konto=SAENGER)
    for i in range(P.MAX_ABOS_JE_KONTO):
        _anmelden(endpoint=f"https://{_FCM_HOST}/b{i}", konto=SAENGER2)
    _anmelden(endpoint=alt, konto=SAENGER2)
    eps = [a.endpoint for a in _abos(SAENGER2)]
    assert alt in eps
    assert len(eps) == P.MAX_ABOS_JE_KONTO


@pytest.mark.parametrize("kontakt", ["admin@gemeinde.de", "http://x.de", "mailto:"])
def test_falscher_kontakt_schaltet_push_ab(vapid, monkeypatch, kontakt):
    """Befund 2: ohne mailto:/https:// ist Push AUS — kein Gerätefehler beim Senden."""
    monkeypatch.setattr(vapid, "vapid_kontakt", kontakt, raising=False)
    assert P._vapid() is None
    assert P.aktiv() is False


@pytest.mark.parametrize("privat", ["privat-test", "AAAA",
                                    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"])
def test_privater_schluessel_nur_im_rohformat(vapid, monkeypatch, privat):
    """Befund 3: kein 32-Byte-Skalar (auch d = 0) → Push AUS."""
    monkeypatch.setattr(vapid, "vapid_private", privat, raising=False)
    assert P._vapid() is None

