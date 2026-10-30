"""SEC-7 — Fehler-/Signatur-Leak und Pfad-Traversal im Method-Router.

Befunde aus dem autorisierten Pentest Runde 2 (N4/N5, NIEDRIG/INFO):

  (N4) `POST /api/method/submit_registrierung` mit leerem Body antwortete mit
       417 und der Python-Signatur im Klartext —
       „submit_registrierung() missing 3 required positional arguments:
       token, vorname, nachname". Zusammen mit dem 404 fuer unbekannte Pfade
       liess sich damit die Methoden-/Signatur-Flaeche der Installation
       aufzaehlen (404 = gibt es nicht, 417 = gibt es, diese Argumente fehlen).

  (N5) `POST /api/method/..%2F..%2Fetc%2Fpasswd` endete in einem
       unbehandelten 500 (TypeError aus dem relativen Import). Ein Fehlerbild,
       das nach Programmfehler aussieht, obwohl es nur ein unsinniger Pfad ist.

Zusagen dieser Karte:

  S1 — Fehlerantworten des Method-Routers sind generisch: weder die
       Python-Signatur noch ein interner Funktions-/Modul-/Exceptionname
       stehen im Body; die Einzelheiten gehen ins Log. Alle Argumentfehler
       enden mit DEMSELBEN Status (417) und DERSELBEN Meldung, damit sich
       daran nichts mehr unterscheiden laesst. Fachliche Fehler
       (`FrappeCompatError`) behalten ihre Meldung — sie ist Inhalt, nicht
       Diagnose.

  S2 — Der Methodenpfad wird VOR jeder Aufloesung gegen eine Whitelist
       geprueft (dotted name aus `[A-Za-z0-9_]`, Punkte nur als Trenner).
       Alles andere — `..`, `/`, `%`, Leerraum, Backslash, fuehrender oder
       doppelter Punkt — ist 404 mit derselben generischen Meldung wie ein
       unbekannter Name. Kein 500, keine Importversuche.
"""

from __future__ import annotations

import logging

import pytest

import diakronos_app.api  # noqa: F401 — registriert alle portierten Endpunkte

REGISTRIERUNG = "diakronos.diakonos.api.registrierung"

#: Was in einer Fehlerantwort NIE stehen darf (S1) — Signatur- und
#: Modulinterna. `submit_registrierung` selbst ist ein oeffentlicher
#: Methodenname und steht hier bewusst NICHT (er waere im Pfad sichtbar).
INTERN = (
    "missing",
    "required positional",
    "positional argument",
    "unexpected keyword",
    "Traceback",
    "diakronos_app",
    "__",
    "TypeError",
    "TypeError:",
    "ImportError",
    "importlib",
    "relative import",
    "package",
)

#: Traversal- und Aufbau-Varianten, die der Router vor der Aufloesung abweisen
#: muss (S2). `None` = der TestClient loest den Pfad nicht selbst auf; die
#: kodierte Form erreicht den Router garantiert als ein Segment.
TRAVERSAL = [
    "..%2F..%2Fetc%2Fpasswd",
    "%2E%2E%2F%2E%2E%2Fetc%2Fpasswd",
    "..%5C..%5Cwindows%5Cwin.ini",
    "%2Fetc%2Fpasswd",
    "%252E%252E%252Fetc%252Fpasswd",
    "..",
    ".",
    "%00",
    "admin_hub%00.get_statistik",
    "admin_hub.get_statistik%2F..%2F",
    "admin_hub..get_statistik",
    ".admin_hub.get_statistik",
    "admin_hub.get_statistik.",
    "admin_hub get_statistik",
    "admin_hub%20.get_statistik",
    "admin_hub;get_statistik",
    "admin hub.get_statistik",
    "mitglieder/get_mitglieder_liste",
]


def _kein_intern(body: str, *, erlaubt: tuple[str, ...] = ()) -> None:
    """S1-Waechter: keine Signatur, kein Modulpfad, kein Exception-Name."""
    for wort in INTERN:
        if wort in erlaubt:
            continue
        assert wort not in body, f"interner Begriff {wort!r} in der Antwort: {body}"


# ── (S1) Fehlende Argumente: generisch, ohne Signatur ──────────────────────


def test_leerer_body_verraet_die_signatur_nicht(client):
    """N4 im Original: 417 mit „missing 3 required positional arguments …"."""
    r = client.post(f"/api/method/{REGISTRIERUNG}.submit_registrierung")

    assert r.status_code == 417, r.text
    body = r.json()
    assert body["message"] == "Ungueltige Anfrage"
    assert body["exc_type"] == body["exception"] == "ValidationError"
    _kein_intern(r.text)
    # Die Parameternamen des Endpunkts sind Teil der Signatur.
    for name in ("token", "vorname", "nachname", "dsgvo"):
        assert name not in r.text, f"Parametername {name!r} in der Antwort: {r.text}"


def test_teilweise_argumente_verraten_die_signatur_nicht(client):
    """Ein Teil der Argumente: derselbe Status, DIESELBE Meldung (S1)."""
    r = client.post(f"/api/method/{REGISTRIERUNG}.submit_registrierung", json={"token": "x"})

    assert r.status_code == 417, r.text
    assert r.json()["message"] == "Ungueltige Anfrage"
    _kein_intern(r.text)


def test_unerwartetes_argument_verraet_die_signatur_nicht(client):
    """Unbekanntes Keyword: auch das warf bisher `TypeError` im Klartext."""
    r = client.post("/api/method/frappe.client.insert", json={"voellig": "falsch"})

    assert r.status_code in (417, 400), r.text
    _kein_intern(r.text, erlaubt=("package",))


@pytest.mark.parametrize(
    "pfad",
    [
        f"{REGISTRIERUNG}.submit_registrierung",
        f"{REGISTRIERUNG}.submit_gast",
        "frappe.client.insert",
        "session.check_permission",
    ],
)
def test_argumentfehler_sind_nicht_unterscheidbar(client, pfad):
    """Die Enumeration lebt von UNTERSCHIEDEN — hier gibt es keine mehr.

    Unbekannter Name -> 404 + generische Meldung; bekannter Name ohne
    Argumente -> 417 + generische Meldung. Entscheidend: alle Varianten des
    Argumentfehlers sehen gleich aus (Status UND Text), und im Text steht
    nichts, was den Endpunkt beschreibt.
    """
    leer = client.post(f"/api/method/{pfad}")
    halb = client.post(f"/api/method/{pfad}", json={"gibtsnicht": 1})

    assert leer.status_code == halb.status_code == 417, (leer.text, halb.text)
    assert leer.json() == halb.json()
    _kein_intern(leer.text)


def test_signatur_und_ursache_stehen_im_log(client, caplog):
    """S1 zweite Haelfte: was der Client nicht sieht, muss diagnostizierbar sein."""
    with caplog.at_level(logging.WARNING, logger="diakronos_app.frappe_compat.router"):
        r = client.post(f"/api/method/{REGISTRIERUNG}.submit_registrierung")

    assert r.status_code == 417
    protokoll = "\n".join(rec.getMessage() for rec in caplog.records)
    assert f"{REGISTRIERUNG}.submit_registrierung" in protokoll
    assert "missing" in protokoll, protokoll


# ── (S2) Traversal: vor der Aufloesung abweisen ────────────────────────────


@pytest.mark.parametrize("pfad", TRAVERSAL)
def test_traversal_ist_404_und_niemals_500(client, pfad):
    """N5 im Original: `..%2F..%2Fetc%2Fpasswd` -> unbehandelter 500."""
    r = client.post(f"/api/method/{pfad}")

    assert r.status_code in (400, 404), f"{pfad}: {r.status_code} {r.text[:200]}"
    assert r.status_code != 500
    _kein_intern(r.text, erlaubt=("package",))


@pytest.mark.parametrize("pfad", TRAVERSAL)
def test_traversal_wird_vor_der_aufloesung_abgewiesen(client, pfad, monkeypatch):
    """Der Pfad erreicht Register und Import NIE — keine Sonde moeglich.

    Ohne diese Zusage waere die Whitelist nur Kosmetik: ein Traversal-Pfad,
    der bis in `importlib` laeuft, verraet ueber Ja/Nein-Antworten wieder die
    Verzeichnisstruktur.
    """
    from diakronos_app.frappe_compat import registry, router

    gerufen: list[str] = []

    def _kein_import(name, *args, **kwargs):  # pragma: no cover — darf nicht greifen
        gerufen.append(str(name))
        raise AssertionError(f"Importversuch fuer {name!r}")

    monkeypatch.setattr(registry, "lookup", lambda p: gerufen.append(p) or None)
    monkeypatch.setattr(router, "_maybe_import", _kein_import)

    r = client.post(f"/api/method/{pfad}")

    assert r.status_code in (400, 404), r.text
    assert gerufen == [], f"Pfad wurde aufgeloest: {gerufen}"


def test_traversal_antwort_ist_die_generische_404(client):
    """Gleiche Meldung wie „gibt es nicht" — kein zweites Fehlerbild."""
    traversal = client.get("/api/method/..%2F..%2Fetc%2Fpasswd")
    unbekannt = client.get("/api/method/gibt.es.nicht")

    assert traversal.status_code == unbekannt.status_code == 404
    assert traversal.json() == unbekannt.json()


# ── Was unveraendert bleiben MUSS ──────────────────────────────────────────


def test_gueltige_methode_bleibt_gueltig(client):
    r = client.get("/api/method/ping")
    assert r.status_code == 200
    assert r.json() == {"message": "pong"}


def test_gueltige_methoden_mit_originalpfad_bleiben_gueltig(client):
    """Die SPA ruft ausschliesslich `diakronos.diakonos.api.<modul>.<fn>`."""
    r = client.get(
        f"/api/method/{REGISTRIERUNG}.validate_token",
        params={"token": "gibtsnicht"},
    )
    # Fachlich abgelehnt (unbekannter Token) — aber ROUTING und Meldung der
    # Fachfunktion bleiben unveraendert erreichbar.
    assert r.status_code != 404, r.text
    assert "nicht gefunden" not in r.text.lower() or "token" in r.text.lower()


def test_fachfehler_behalten_ihre_meldung(client):
    """S1 betrifft NUR Diagnosetexte — `frappe.throw(...)` bleibt lesbar."""
    r = client.post("/api/method/fail_validation", json={"msg": "zu jung"})

    assert r.status_code == 417
    assert r.json()["message"] == "zu jung"
    assert r.json()["exc_type"] == "ValidationError"
