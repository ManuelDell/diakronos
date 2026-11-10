"""SEC-DEF1 — Startpruefung auf unsichere Standardwerte.

Befund (Secret-Scan der oeffentlichen Repos, 10.11.): `settings.py` hatte
einen einkompilierten Platzhalter-Schluessel (`insecure-dev-key`) und eine
`DATABASE_URL` mit bekanntem Passwort. Wer ohne `.env` startet, bekommt
faelschbare Sitzungs-Tokens und eine Datenbank mit oeffentlich bekanntem
Passwort — ohne dass es auffaellt.

Erwartung:
  * Betrieb (`APP_ENV=production`/`prod`) + Platzhalter  -> Abbruch
  * Betrieb + zu kurzer Schluessel                        -> Abbruch
  * Betrieb + Default-DB-Passwort                         -> Abbruch
  * Betrieb + starker Schluessel + eigenes Passwort       -> ok
  * `development`/`test`                                  -> ok (Defaults erlaubt)

Geprueft wird an drei Stellen, weil alle drei im Betrieb greifen:
  1. `Settings(...)` selbst (Modellpruefung) — keine Instanz entsteht.
  2. der Entrypoint-Aufruf `python -m diakronos_app.anmeldung.startup`
     (Exit-Code 1 mit deutscher Meldung).
  3. die reine Funktion `unsichere_standardwerte`.
"""

from __future__ import annotations

import os

import pytest
from pydantic import ValidationError

STARKER_SCHLUESSEL = (
    "9f2c4b6d8a0e1c3f5b7d9a2c4e6f81023b5d7f9a1c3e5b7d9f0a2c4e6b8d1f3a"
)
STARKES_DB_PASSWORT = "Qx7-vN2_Lm9tR4zP"
STARKER_DB_URL = (
    f"postgresql+psycopg://diakronos:{STARKES_DB_PASSWORT}@db:5432/diakronos"
)
DEFAULT_DB_URL = "postgresql+psycopg://diakronos:diakronos@db:5432/diakronos"


def _settings(monkeypatch, **werte):
    """Baut fresh Settings OHNE `.env`-Datei (nur die uebergebenen Werte).

    Vorher werden die sechs beteiligten Variablen GELOESCHT: der Testlauf setzt
    `SECRET_KEY` global (conftest) und die Umgebung des Containers traegt
    `APP_ENV`/`DATABASE_URL` — ohne das Loeschen wuerde ein Test die Werte des
    anderen sehen (`monkeypatch.setenv` ueberschreibt nur, was es nennt).
    """
    from diakronos_app.settings import Settings

    for name in ("APP_ENV", "SECRET_KEY", "DATABASE_URL"):
        monkeypatch.delenv(name, raising=False)
    for name, wert in werte.items():
        monkeypatch.setenv(name, wert)
    return Settings(_env_file=None)


# ── 1) Settings selbst: Betrieb mit Platzhalter bricht ab ───────────────────


def test_prod_mit_platzhalter_schluessel_bricht_ab(monkeypatch):
    with pytest.raises(ValidationError) as fehler:
        _settings(
            monkeypatch,
            APP_ENV="production",
            SECRET_KEY="insecure-dev-key",
            DATABASE_URL=STARKER_DB_URL,
        )
    assert "SECRET_KEY" in str(fehler.value)


def test_prod_mit_default_db_passwort_bricht_ab(monkeypatch):
    with pytest.raises(ValidationError) as fehler:
        _settings(
            monkeypatch,
            APP_ENV="production",
            SECRET_KEY=STARKER_SCHLUESSEL,
            DATABASE_URL=DEFAULT_DB_URL,
        )
    assert "Standard-Passwort" in str(fehler.value)
    # Kein Passwort in der Meldung: das Wort steht als Befund, aber die
    # Verbindungszeichenfolge selbst darf nicht auftauchen.
    assert STARKES_DB_PASSWORT not in str(fehler.value)


def test_prod_mit_kurzem_schluessel_bricht_ab(monkeypatch):
    with pytest.raises(ValidationError) as fehler:
        _settings(
            monkeypatch,
            APP_ENV="production",
            SECRET_KEY="zu-kurz",
            DATABASE_URL=STARKER_DB_URL,
        )
    assert "zu kurz" in str(fehler.value)


def test_prod_mit_starken_werten_startet(monkeypatch):
    s = _settings(
        monkeypatch,
        APP_ENV="production",
        SECRET_KEY=STARKER_SCHLUESSEL,
        DATABASE_URL=STARKER_DB_URL,
    )
    assert s.secret_key == STARKER_SCHLUESSEL
    assert s.app_env == "production"


@pytest.mark.parametrize("umgebung", ["development", "test"])
def test_entwicklung_und_test_erlauben_die_defaults(monkeypatch, umgebung):
    s = _settings(
        monkeypatch,
        APP_ENV=umgebung,
        SECRET_KEY="insecure-dev-key",
        DATABASE_URL=DEFAULT_DB_URL,
    )
    assert s.secret_key == "insecure-dev-key"


# ── 2) Reine Funktion (auch die Grundlage des Entrypoint-Aufrufs) ──────────


def test_funktion_meldet_beide_befunde():
    from diakronos_app.konfigurationsschutz import unsichere_standardwerte

    probleme = unsichere_standardwerte("production", "insecure-dev-key", DEFAULT_DB_URL)
    assert len(probleme) == 2
    assert any("SECRET_KEY" in p for p in probleme)
    assert any("Standard-Passwort" in p for p in probleme)


def test_funktion_ist_in_entwicklung_still():
    from diakronos_app.konfigurationsschutz import unsichere_standardwerte

    assert unsichere_standardwerte("development", "insecure-dev-key", DEFAULT_DB_URL) == []
    assert unsichere_standardwerte("TEST", "", "") == []


def test_leerer_schluessel_ist_zu_kurz():
    from diakronos_app.konfigurationsschutz import unsichere_standardwerte

    probleme = unsichere_standardwerte("prod", "", STARKER_DB_URL)
    assert len(probleme) == 1
    assert "zu kurz" in probleme[0]


def test_url_kodiertes_default_passwort_wird_erkannt():
    from diakronos_app.konfigurationsschutz import database_url_hat_default_passwort

    assert database_url_hat_default_passwort(
        "postgresql+psycopg://diakronos:diakron%6Fs@db:5432/diakronos"
    )


def test_anderes_passwort_gilt_als_sicher():
    from diakronos_app.konfigurationsschutz import database_url_hat_default_passwort

    assert not database_url_hat_default_passwort(STARKER_DB_URL)
    assert not database_url_hat_default_passwort("sqlite:////tmp/test.db")
    assert not database_url_hat_default_passwort("")


# ── 3) Entrypoint: Exit-Code und deutsche Meldung ──────────────────────────


def _startup_mit(monkeypatch, env: dict) -> int:
    """Ruft `startup.main()` mit gesetzter Umgebung; gibt den Exit-Code zurueck."""
    from diakronos_app.anmeldung import startup

    for name in ("APP_ENV", "SECRET_KEY", "DATABASE_URL"):
        monkeypatch.delenv(name, raising=False)
    for name, wert in env.items():
        monkeypatch.setenv(name, wert)
    return startup.main()


def test_entrypoint_bricht_im_betrieb_mit_platzhalter_ab(monkeypatch, caplog):
    with caplog.at_level("ERROR"):
        code = _startup_mit(
            monkeypatch,
            {
                "APP_ENV": "production",
                "SECRET_KEY": "insecure-dev-key",
                "DATABASE_URL": STARKER_DB_URL,
            },
        )
    assert code == 1
    assert "Start verweigert" in caplog.text
    assert "openssl rand -hex 32" in caplog.text


def test_entrypoint_bricht_im_betrieb_mit_default_db_passwort_ab(monkeypatch, caplog):
    with caplog.at_level("ERROR"):
        code = _startup_mit(
            monkeypatch,
            {
                "APP_ENV": "production",
                "SECRET_KEY": STARKER_SCHLUESSEL,
                "DATABASE_URL": DEFAULT_DB_URL,
            },
        )
    assert code == 1
    assert "Standard-Passwort" in caplog.text


def test_entrypoint_erlaubt_entwicklung_mit_platzhalter(monkeypatch):
    # OIDC/Forward-Auth sind im Testlauf aus -> nur Warnungen, Exit 0.
    code = _startup_mit(
        monkeypatch,
        {
            "APP_ENV": "development",
            "SECRET_KEY": "insecure-dev-key",
            "DATABASE_URL": DEFAULT_DB_URL,
        },
    )
    assert code == 0


def test_entrypoint_erlaubt_betrieb_mit_starken_werten(monkeypatch):
    code = _startup_mit(
        monkeypatch,
        {
            "APP_ENV": "production",
            "SECRET_KEY": STARKER_SCHLUESSEL,
            "DATABASE_URL": STARKER_DB_URL,
        },
    )
    assert code == 0
