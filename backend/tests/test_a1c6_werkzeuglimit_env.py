"""A1c6 — die beiden Entscherr-Schalter sind wirklich ENV-schaltbar.

Die Karte verlangt fuer das Rate-Limit des Werkzeugs ausdruecklich:
„Maessig, mit Default, **ENV-schaltbar**."

GEMESSENER BEFUND, warum es diese Datei gibt
--------------------------------------------
`pydantic-settings` findet eine Umgebungsvariable ueber den **Feldnamen**.
`case_sensitive=False` vergleicht nur die Gross-/Kleinschreibung und setzt
**kein** Trennzeichen dazwischen. Welche Schreibweise ein Feld dadurch
tatsaechlich erwischt, ist nicht vorhersehbar. An dieser Klasse gemessen:

    LOG_LEVEL=DEBUG              -> log_level == "DEBUG"              (trifft)
    LOGIN_MAX_VERSUCHE=9         -> login_max_versuche == 9          (trifft)
    WERKZEUGLIMIT_ENTSPRERREN=7  -> werkzeuglimit_entsperren == 10   (GREIFT NICHT)

Der dritte Fall waere still: der Betreiber schraerkt das Limit im `.env`,
der Wert kommt nicht an, und **nichts** zeigt den Fehler. Ein Limit, das
man nicht setzen kann, ist aber nicht schlimmer als gar keins — es ist
schlimmer, weil es in der Dokumentation existiert.

Deshalb stehen hier die Aliase fest. Wer sie entfernt, bricht diese Tests —
nicht die Doku.

Die Aliase sind ueber `AliasChoices` gesetzt, nicht ueber `env_prefix`:
`env_prefix` muesste fuer **alle** Felder gelten und wuerde die bestehenden
Schreibweisen (`LOG_LEVEL` ohne Praefix) brechen. `AliasChoices` laesst beide
Formen zu.
"""

from __future__ import annotations

import pytest

from diakronos_app.settings import Settings

GROSS = "WERKZEUGLIMIT_ENTSPRERREN"
KLEIN = "werkzeuglimit_entsperren"
GROSS_FENSTER = "WERKZEUGLIMIT_ENTSPRERREN_FENSTER"
KLEIN_FENSTER = "werkzeuglimit_entsperren_fenster"


@pytest.fixture(autouse=True)
def _saubere_umgebung(monkeypatch):
    """Beide Schreibweisen entfernen, damit kein Test vom anderen erbt.

    Ohne das wuerde ein frueherer Test den Wert setzen und der naechste
    glaubte, er habe ihn selbst gesetzt — und der Test waere gruen, ohne
    etwas zu pruefen.
    """
    for name in (GROSS, KLEIN, GROSS_FENSTER, KLEIN_FENSTER):
        monkeypatch.delenv(name, raising=False)


def test_der_default_greift_ohne_umgebung():
    """Ohne ENV: die dokumentierten Defaults (fail closed, nicht 0)."""
    s = Settings()

    assert s.werkzeuglimit_entsperren == 10
    assert s.werkzeuglimit_entsperren_fenster == 600


def test_das_limit_ist_ueber_env_setzbar(monkeypatch):
    """Der Kern der Karte: **ENV-schaltbar**, in der Schreibweise aus dem Compose."""
    monkeypatch.setenv(GROSS, "3")

    assert Settings().werkzeuglimit_entsperren == 3


def test_der_exakte_regressionsfall(monkeypatch):
    """Der Befund als Test: `WERKZEUGLIMIT_ENTSPRERREN=7` blieb wirkungslos.

    Ohne `validation_alias` liefert `Settings()` hier 10 und der Test
    schlaegt fehl. Genau das ist der Fehler, den diese Karte nicht
    zurueckbringen darf — ein still wirkungsloses Limit.
    """
    monkeypatch.setenv(GROSS, "7")

    assert Settings().werkzeuglimit_entsperren == 7


def test_auch_die_fensterlaenge_ist_setzbar(monkeypatch):
    """Beide Schalter, nicht nur der Zaehler — sonst laesst sich die
    Begrenzung nicht sinnvoll justieren (10 Freigaben in 5 Sekunden ist
    strenger als 10 in 10 Minuten)."""
    monkeypatch.setenv(GROSS, "5")
    monkeypatch.setenv(GROSS_FENSTER, "30")

    s = Settings()

    assert s.werkzeuglimit_entsperren == 5
    assert s.werkzeuglimit_entsperren_fenster == 30


def test_die_kleinschreibung_funktioniert_weiterhin(monkeypatch):
    """`.env` und direkter Zugriff nutzen die Kleinschreibung.

    `AliasChoices` nennt beide Reihenfolgen; waere nur die Grossschreibung
    im Alias, wuerde ein `.env` mit `werkzeuglimit_entsperren=…` still
    ignoriert — dieselbe Falle, eine Ebene tiefer.
    """
    monkeypatch.setenv(KLEIN, "4")
    monkeypatch.setenv(KLEIN_FENSTER, "45")

    s = Settings()

    assert s.werkzeuglimit_entsperren == 4
    assert s.werkzeuglimit_entsperren_fenster == 45


def test_die_grossschreibung_hat_vorrang_wenn_beide_da_sind(monkeypatch):
    """Beide gesetzt: der Compose-Weg gewinnt.

    Wer `WERKZEUGLIMIT_ENTSPRERREN` schreibt, meint die Betriebs-
    umgebung; wer `werkzeuglimit_entsperren` schreibt, meist die `.env`.
    `AliasChoices` nimmt die **erste** passende — deshalb steht die
    Grossschreibung vorn.
    """
    monkeypatch.setenv(KLEIN, "4")
    monkeypatch.setenv(GROSS, "8")

    assert Settings().werkzeuglimit_entsperren == 8


def test_der_gesperrte_wert_wird_nicht_verschluckt(monkeypatch):
    """Unsinn wird abgelehnt, nicht still auf den Default zurueckgefallen.

    Ein Tippfehler in der `.env` darf nicht dazu fuehren, dass das
    Werkzeug unbegrenzt ist: `pydantic` wirft, und der Container startet
    nicht. Das ist der fail-closed-Weg fuer diesen Schalter.
    """
    monkeypatch.setenv(GROSS, "viel-zu-viel")

    with pytest.raises(ValueError):
        Settings()


def test_null_ist_erlaubt_und_bedeutet_keine_grenze(monkeypatch):
    """0 = ausgeschaltet. Ausdruecklich, mit Default **nicht** 0.

    Das ist die dokumentierte Entscheidung: der Default begrenzt, und wer
    abschaltet, muss es sagen. Der Test haelt beides fest — ein Umbau,
    der den Default auf 0 setzt, faellt hier auf.
    """
    monkeypatch.setenv(GROSS, "0")
    assert Settings().werkzeuglimit_entsperren == 0

    monkeypatch.delenv(GROSS)
    assert Settings().werkzeuglimit_entsperren != 0
