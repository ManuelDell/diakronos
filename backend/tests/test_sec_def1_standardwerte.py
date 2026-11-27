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
  * Betrieb + starke Werte + eigenes Passwort             -> ok
  * `development`/`test`                                  -> ok (Defaults erlaubt)

SEC-DEF2 (26.11.): Der Betriebsmodus ist der STANDARD. Fehlt `APP_ENV` (oder
ist es leer), prueft die App wie im Betrieb — vorher fiel der Wert still auf
`development` zurueck und die Pruefung war in jeder Standardinstallation
wirkungslos. Die Ausnahme gilt nur bei AUSDRUECKLICH gesetztem
`development`/`test`/`dev`.

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


@pytest.mark.parametrize("umgebung", ["development", "test", "dev", " DEV "])
def test_entwicklung_und_test_erlauben_die_defaults(monkeypatch, umgebung):
    s = _settings(
        monkeypatch,
        APP_ENV=umgebung,
        SECRET_KEY="insecure-dev-key",
        DATABASE_URL=DEFAULT_DB_URL,
    )
    assert s.secret_key == "insecure-dev-key"


# ── 1b) SEC-DEF2: fehlendes APP_ENV ist BETRIEB ────────────────────────────


def test_ohne_app_env_prueft_settings_wie_betrieb(monkeypatch):
    """SEC-DEF2: kein APP_ENV -> Betrieb -> Platzhalter wird verweigert."""
    with pytest.raises(ValidationError) as fehler:
        _settings(
            monkeypatch,
            SECRET_KEY="insecure-dev-key",
            DATABASE_URL=STARKER_DB_URL,
        )
    meldung = str(fehler.value)
    assert "SECRET_KEY" in meldung
    # Der Betriebsmodus steht in der Meldung und ist der Default, nicht "development".
    assert "APP_ENV=production" in meldung


def test_ohne_app_env_und_starken_werten_startet_settings(monkeypatch):
    s = _settings(
        monkeypatch,
        SECRET_KEY=STARKER_SCHLUESSEL,
        DATABASE_URL=STARKER_DB_URL,
    )
    assert s.app_env == "production"


def test_leeres_app_env_gilt_wie_fehlend(monkeypatch):
    """Compose gibt bei `APP_ENV=` einen LEEREN Wert durch — der ist Betrieb."""
    with pytest.raises(ValidationError):
        _settings(
            monkeypatch,
            APP_ENV="",
            SECRET_KEY="insecure-dev-key",
            DATABASE_URL=STARKER_DB_URL,
        )


def test_ist_entwicklung_lehnt_leeren_und_fremden_wert_ab():
    from diakronos_app.konfigurationsschutz import ist_entwicklung

    assert ist_entwicklung("development")
    assert ist_entwicklung(" TEST ")
    assert ist_entwicklung("dev")
    assert not ist_entwicklung("")
    assert not ist_entwicklung("   ")
    assert not ist_entwicklung("production")
    assert not ist_entwicklung("staging")


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


def test_funktion_prueft_bei_fehlendem_app_env():
    """SEC-DEF2: ohne APP_ENV ist das Betrieb — die Beanstandungen kommen."""
    from diakronos_app.konfigurationsschutz import unsichere_standardwerte

    for ohne in ("", "   ", None):
        probleme = unsichere_standardwerte(ohne, "insecure-dev-key", DEFAULT_DB_URL)
        assert len(probleme) == 2, ohne
    assert unsichere_standardwerte("", STARKER_SCHLUESSEL, STARKER_DB_URL) == []


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


# ── 2b) M3 (ABN-1b): Passwort OHNE Wert / als Query-Parameter / Grossschreibung ──


def test_benutzer_ohne_passwort_wird_erkannt():
    """`postgresql://diakronos@db/x` — Benutzer ohne Doppelpunkt ist ein
    Datenbankbenutzer ohne Passwort. Vorher blieb der Fall unbeanstandet."""
    from diakronos_app.konfigurationsschutz import database_url_hat_default_passwort

    for url in (
        "postgresql://diakronos@db:5432/diakronos",
        "postgresql+psycopg://diakronos@db/x",
        "postgres://diakronos@db/x",
    ):
        assert database_url_hat_default_passwort(url), url


def test_passwort_als_query_parameter_wird_erkannt():
    """`…?password=diakronos` — Passwort nicht in der Benutzerinfo, sondern als
    Abfrage-Parameter. Die Pruefung darf es nicht uebersehen."""
    from diakronos_app.konfigurationsschutz import database_url_hat_default_passwort

    assert database_url_hat_default_passwort(
        "postgresql://diakronos@db/x?password=diakronos"
    )
    # Anderes Passwort als Parameter ist unbeanstandet (sonst waere die Pruefung
    # ein Verbot jeder Parameter-Form).
    assert not database_url_hat_default_passwort(
        "postgresql://diakronos@db/x?password=ein-anderes-geheimnis"
    )
    # Leerer Parameter zaehlt wie ein leeres Passwort.
    assert database_url_hat_default_passwort("postgresql://diakronos@db/x?password=")


def test_standard_passwort_grossschreibung_wird_erkannt():
    from diakronos_app.konfigurationsschutz import database_url_hat_default_passwort

    for url in (
        "postgresql://diakronos:DIAKRONOS@db/x",
        "postgresql://diakronos:Diakronos@db/x",
        "postgresql://diakronos@db/x?password=DIAKRONOS",
    ):
        assert database_url_hat_default_passwort(url), url


def test_benutzer_ohne_passwort_und_leere_benutzerinfo_bleiben_getrennt():
    """Eine URL ganz OHNE Benutzerinfo (`postgresql://db/x`) hat kein Passwort,
    aber auch keinen Benutzer — sie bleibt unbeanstandet (der Server verlangt
    dann selbst Authentifizierung)."""
    from diakronos_app.konfigurationsschutz import database_url_hat_default_passwort

    assert not database_url_hat_default_passwort("postgresql://db:5432/x")


@pytest.mark.parametrize("schluessel", ["a" * 32, "0" * 64, "-" * 40])
def test_wiederholtes_zeichen_ist_kein_schluessel(schluessel):
    """M3: ein einziges wiederholtes Zeichen ist lang genug, aber kein
    Geheimnis — genau so entsteht es, wenn jemand die Laengenpruefung „mit
    Zeichen auffuellen" will."""
    from diakronos_app.konfigurationsschutz import unsichere_standardwerte

    probleme = unsichere_standardwerte("production", schluessel, STARKER_DB_URL)
    assert len(probleme) == 1
    assert "einem einzigen wiederholten Zeichen" in probleme[0]


def test_echter_schluessel_bleibt_erlaubt():
    """Gegenprobe: ein zufaelliger Schluessel mit Wiederholungen ist in Ordnung
    — abgewiesen wird nur der Fall „ausschliesslich EIN Zeichen"."""
    from diakronos_app.konfigurationsschutz import unsichere_standardwerte

    assert unsichere_standardwerte("production", STARKER_SCHLUESSEL, STARKER_DB_URL) == []


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


# ── 4) SEC-DEF2: fehlendes APP_ENV -> Pruefung aktiv ───────────────────────


def test_entrypoint_ohne_app_env_bricht_mit_platzhalter_ab(monkeypatch, caplog):
    """SEC-DEF2: kein APP_ENV -> Betrieb -> aber auch bei starken Werten laeuft
    die Pruefung; mit dem Platzhalter ist der Start verweigert."""
    with caplog.at_level("ERROR"):
        code = _startup_mit(
            monkeypatch,
            {
                "SECRET_KEY": "insecure-dev-key",
                "DATABASE_URL": DEFAULT_DB_URL,
            },
        )
    assert code == 1
    assert "Start verweigert" in caplog.text
    assert "SECRET_KEY" in caplog.text
    assert "Standard-Passwort" in caplog.text


def test_entrypoint_mit_leerem_app_env_bricht_mit_platzhalter_ab(monkeypatch, caplog):
    with caplog.at_level("ERROR"):
        code = _startup_mit(
            monkeypatch,
            {
                "APP_ENV": "",
                "SECRET_KEY": "insecure-dev-key",
                "DATABASE_URL": STARKER_DB_URL,
            },
        )
    assert code == 1
    assert "Start verweigert" in caplog.text


def test_entrypoint_ohne_app_env_mit_starken_werten_ist_ok(monkeypatch):
    code = _startup_mit(
        monkeypatch,
        {
            "SECRET_KEY": STARKER_SCHLUESSEL,
            "DATABASE_URL": STARKER_DB_URL,
        },
    )
    assert code == 0


def test_entrypoint_leeres_db_passwort_bricht_ab(monkeypatch, caplog):
    """Compose baut die URL aus POSTGRES_PASSWORD — ein leeres Passwort ergibt
    `diakronos:@db` und damit denselben bekannten Zugang wie das Default-Passwort."""
    with caplog.at_level("ERROR"):
        code = _startup_mit(
            monkeypatch,
            {
                "APP_ENV": "production",
                "SECRET_KEY": STARKER_SCHLUESSEL,
                "DATABASE_URL": "postgresql+psycopg://diakronos:@db:5432/diakronos",
            },
        )
    assert code == 1
    assert "Standard-Passwort" in caplog.text


# ── 5) SEC-DEF2: Demo-/Diagnose-Schalter im Betrieb (Meldung, kein Verbot) ─


def test_demo_schalter_funktion_meldet_im_betrieb():
    from diakronos_app.konfigurationsschutz import demo_schalter_im_betrieb

    hinweise = demo_schalter_im_betrieb("production", True, True)
    assert len(hinweise) == 2
    assert any("DEVMODE_ENABLED" in h for h in hinweise)
    assert any("SEC_DOKU_OEFFENTLICH" in h for h in hinweise)
    # Ein ausgeschalteter Schalter meldet nichts; in Entwicklung meldet nichts.
    assert demo_schalter_im_betrieb("production", False, False) == []
    assert demo_schalter_im_betrieb("development", True, True) == []
    assert demo_schalter_im_betrieb("", True, False) != []


def test_entrypoint_warnt_ueber_devmode_im_betrieb(monkeypatch, caplog):
    with caplog.at_level("WARNING"):
        code = _startup_mit(
            monkeypatch,
            {
                "APP_ENV": "production",
                "SECRET_KEY": STARKER_SCHLUESSEL,
                "DATABASE_URL": STARKER_DB_URL,
                "DEVMODE_ENABLED": "1",
                "SEC_DOKU_OEFFENTLICH": "1",
            },
        )
    assert code == 0  # nur Meldung, KEIN Startverbot
    assert "DEVMODE_ENABLED=1 ist im BETRIEB eingeschaltet" in caplog.text
    assert "SEC_DOKU_OEFFENTLICH=1 ist im BETRIEB eingeschaltet" in caplog.text


def test_entrypoint_schweigt_ueber_devmode_in_entwicklung(monkeypatch, caplog):
    with caplog.at_level("WARNING"):
        code = _startup_mit(
            monkeypatch,
            {
                "APP_ENV": "development",
                "SECRET_KEY": "insecure-dev-key",
                "DATABASE_URL": DEFAULT_DB_URL,
                "DEVMODE_ENABLED": "1",
            },
        )
    assert code == 0
    assert "DEVMODE_ENABLED=1 ist im BETRIEB" not in caplog.text


def _repo_datei(relativ: str):
    """Sucht eine Repo-Datei AUSSERHALB des Pakets (Vorlage, Compose).

    Zwei Orte: (a) der Nachbar des Backend-Ordners — im Image liegt das Backend
    als `/app`; (b) der Git-Wurzelordner des Worktrees. Fehlt beides (z. B. ein
    Lauf, der nur `backend/` einhaengt), wird der Test uebersprungen statt rot:
    die Doku-Pruefung darf nicht davon abhaengen, wie der Lauf eingehaengt ist.
    """
    from pathlib import Path

    import pytest as _pytest

    hier = Path(__file__).resolve()
    for eltern in (2, 3):
        if len(hier.parents) <= eltern:
            continue  # /app/tests/... im Image hat nur zwei Eltern
        kandidat = hier.parents[eltern] / relativ
        if kandidat.is_file():
            return kandidat.read_text("utf-8")
    import os

    kandidat = Path(os.environ.get("DIAKRONOS_REPO", "/repo")) / relativ
    if kandidat.is_file():
        return kandidat.read_text("utf-8")
    _pytest.skip(f"{relativ} ist in diesem Lauf nicht eingehaengt")


def test_dotenv_beispiel_traegt_production_als_standard():
    """SEC-DEF2: die Vorlage darf die Pruefung nicht wieder aushebeln."""
    vorlage = _repo_datei(".env.example")
    zeilen = [
        z.strip()
        for z in vorlage.splitlines()
        if z.strip().startswith("APP_ENV=")
    ]
    assert zeilen == ["APP_ENV=production"], zeilen


def test_compose_vorgabe_ist_production():
    """SEC-DEF2: auch die Compose-Vorgabe ist Betrieb (nicht development)."""
    stack = _repo_datei("compose/stack.yml")
    assert "${APP_ENV:-production}" in stack
    assert "${APP_ENV:-development}" not in stack

