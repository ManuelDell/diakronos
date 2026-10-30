"""
SEC-4-Waechter: Sicherheits-Kopfzeilen und API-Doku bleiben an EINER Stelle.

Der Pentest vom 2026-10-29 hat zwei Befunde ergeben:

* Antworten ohne HSTS/CSP/X-Frame-Options/X-Content-Type-Options/
  Referrer-Policy (Bericht Punkt 2),
* ``/docs``, ``/redoc`` und ``/openapi.json`` oeffentlich erreichbar
  (Punkt 8).

Behoben ist beides im Backend (``sec_header.py`` und der Doku-Schalter in
``settings.py``/``main.py``). Dieser Test haelt die Stellen fest, die davon
abhaengen und leicht wieder auseinanderlaufen:

* die eine Stelle, die die Kopfzeilen setzt, mit den Werten aus der Karte,
* die Reihenfolge (die Kopfzeilen-Schicht laeuft als erste),
* der Doku-Schalter (Default aus) samt Verdrahtung,
* die Konfigurationsvorlage und die Betriebsanleitung, die den Schalter
  nennen,
* der Proxy, der KEINE zweite Fassung derselben Kopfzeile setzen darf.

Warum die Dateien ueber ``importlib.resources`` gelesen werden: der Test
laeuft IM Image, und dort ist nur das Python-Paket vorhanden (``docs/``
steht in ``.dockerignore``). Was nicht im Paket liegt (``.env.example``,
``nginx/``, die Betriebsanleitung), liegt im Repo; fehlt es, wird der
Teil uebersprungen statt rot zu werden — die Pruefung dieses Teils
uebernimmt ``frontend/tests/sec4-*.test.mjs`` im Frontend-Bau, wo das
Repo vollstaendig vorliegt.
"""

from __future__ import annotations

from importlib import resources
from pathlib import Path

import pytest

PAKET = "diakronos_app"


def _paketdatei(*teile: str) -> str:
    """Inhalt einer Datei IM Python-Paket (funktioniert editable und im Image)."""
    ziel = resources.files(PAKET)
    for teil in teile:
        ziel = ziel / teil
    return ziel.read_text(encoding="utf-8")


def _repodatei(*teile: str) -> str | None:
    """Inhalt einer Datei im REPO — ``None``, wenn sie hier nicht existiert.

    ``backend/tests/`` -> zwei Ebenen hoch ist die Repo-Wurzel (im Image
    ``/app``, im Repo ``<repo>/backend``).
    """
    pfad = Path(__file__).resolve().parents[2].joinpath(*teile)
    if not pfad.is_file():
        return None
    return pfad.read_text(encoding="utf-8")


# ── Die eine Stelle, die Kopfzeilen setzt ─────────────────────────────────


def test_kopfzeilen_stehen_genau_in_sec_header():
    """Alle fuenf Kopfzeilen und ihre Werte stehen in ``sec_header.py``."""
    py = _paketdatei("sec_header.py")
    for name in (
        "Strict-Transport-Security",
        "Content-Security-Policy",
        "X-Frame-Options",
        "X-Content-Type-Options",
        "Referrer-Policy",
    ):
        assert py.count(name) >= 1, f"{name} fehlt in sec_header.py"
    # Die Werte aus der Karte, wortgleich.
    assert "max-age=31536000; includeSubDomains" in py
    assert "frame-ancestors 'none'" in py
    # Kein eval: die SPA braucht es nicht, und es waere der groesste Hebel fuer
    # eingeschleuste Skripte. `unsafe-inline` steht bewusst drin (Boot-Skript
    # der ausgelieferten Seite, Inline-Stile der Anmeldemaske).
    csp = py.split("APP_CSP", 1)[1].split(")", 1)[0]
    assert "unsafe-eval" not in csp


def test_kopfzeilen_middleware_ist_die_aeusserste_schicht():
    """Die Kopfzeilen-Schicht wird ZULETZT hinzugefuegt (laeuft damit zuerst).

    ``add_middleware`` schiebt jede neue Schicht nach vorn; nur als letzte
    hinzugefuegt bekommen auch Antworten die Kopfzeilen, die eine innere
    Schicht selbst abschliesst (CSRF 417, 401, Fehlerseiten).
    """
    main = _paketdatei("main.py")
    letzte = main.rfind("app.add_middleware(")
    assert letzte > 0, "main.py registriert keine Middleware"
    assert "SicherheitsHeaderMiddleware" in main[letzte:], (
        "Die letzte add_middleware-Zeile ist nicht die Kopfzeilen-Schicht"
    )


# ── Der Doku-Schalter ────────────────────────────────────────────────────


def test_doku_schalter_ist_standardmaessig_aus():
    from diakronos_app.settings import Settings

    feld = Settings.model_fields["sec_doku_oeffentlich"]
    assert feld.default is False
    # Die Umgebungsvariable steht als Alias in settings.py (beide Schreibweisen,
    # damit `.env` und Compose gleich funktionieren).
    assert "SEC_DOKU_OEFFENTLICH" in _paketdatei("settings.py")


def test_main_schaltet_doku_nur_mit_schalter_an():
    """``main.py`` nimmt alle drei Adressen aus EINER Quelle."""
    main = _paketdatei("main.py")
    assert "docs_url=" in main and "redoc_url=" in main and "openapi_url=" in main
    assert "sec_doku_oeffentlich" in main
    # Nicht drei eigene Bedingungen, sondern die gemeinsame Hilfsfunktion.
    assert "def _doku_adressen" in main


def test_waechter_prueft_die_netten_dateien_wirklich():
    """Gegenprobe: der Pruefpfad trifft die Dateien — sonst waere der Rest still.

    Rechnet hier auch, was ``test_env_vorlage…``/``test_betriebsanleitung…``
    lesen wuerden. Fehlt eine Datei (z.B. ein anderer Aufhaengepunkt), faellt
    das HIER auf, statt die zwei Pruefungen unbemerkt zu ueberspringen.
    """
    vorhanden = [_repodatei(".env.example"), _repodatei("docs", "BETRIEBSANLEITUNG.md")]
    if all(p is None for p in vorhanden):
        # Wirklich nicht vorhanden (Aufhaengung ausserhalb des Repos): nur
        # dann ist ein Skip richtig — und der Test sagt das ausdruecklich.
        pytest.skip(f"Repo-Wurzel nicht auffindbar (Aufhaengung: {Path(__file__).resolve().parents[2]})")
    assert _repodatei(".env.example") is not None, "Pfad zur Repo-Wurzel stimmt nicht"


# ── Vorlage und Betriebsanleitung ────────────────────────────────────────


def test_env_vorlage_nennt_den_schalter_aus():
    inhalt = _repodatei(".env.example")
    if inhalt is None:
        pytest.skip(".env.example liegt nicht im Image (Frontend-Bau prueft es)")
    treffer = [z for z in inhalt.splitlines() if z.startswith("SEC_DOKU_OEFFENTLICH=")]
    assert treffer == ["SEC_DOKU_OEFFENTLICH=0"], treffer


def test_betriebsanleitung_erklaert_kopfzeilen_und_schalter():
    inhalt = _repodatei("docs", "BETRIEBSANLEITUNG.md")
    if inhalt is None:
        pytest.skip("docs/ liegt nicht im Image (Frontend-Bau prueft es)")
    for wort in (
        "Strict-Transport-Security",
        "includeSubDomains",
        "X-Frame-Options",
        "X-Content-Type-Options",
        "Referrer-Policy",
        "SEC_DOKU_OEFFENTLICH",
        "server_tokens",
        # 8.10.4: der Token der Anmeldemaske (SEC-4, no-referrer).
        "_csrf",
    ):
        assert wort in inhalt, f"BETRIEBSANLEITUNG nennt {wort!r} nicht"


def test_proxy_setzt_keine_zweite_fassung_der_kopfzeilen():
    """nginx: kein HSTS, keine CSP — und keine Versionsnummer.

    Beides setzt die App; zwei Quellen haetten verschiedene Werte ergeben
    (nginx ``Referrer-Policy: same-origin``, App ``no-referrer``) und
    doppelte Kopfzeilen wertet der Browser unvorhersehbar aus.
    """
    teile = [_repodatei("nginx", n) for n in ("default.conf.template", "19-tls.envsh", "40-watch-cert.sh")]
    if all(t is None for t in teile):
        pytest.skip("nginx/ liegt nicht im Image (Frontend-Bau prueft es)")
    for inhalt in teile:
        if inhalt is None:
            continue
        wirksam = "\n".join(z for z in inhalt.splitlines() if not z.strip().startswith("#"))
        assert "add_header Strict-Transport-Security" not in wirksam
        assert "add_header Content-Security-Policy" not in wirksam
    conf = _repodatei("nginx", "default.conf.template")
    if conf is not None:
        assert "server_tokens off;" in conf
