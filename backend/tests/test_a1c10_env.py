"""A1c10 — die ENV-Schaltbarkeit der zwei neuen Settings.

DIE LEHRE VON A1c3, WIEDERHOLT
-------------------------------
`pydantic-settings` findet eine Umgebungsvariable ueber den **Feldnamen**,
und `case_sensitive=False` vergleicht dabei nur die Schreibweise — es setzt
**kein** Trennzeichen dazwischen. Gemessen wurde dort:

    LOG_LEVEL=DEBUG              -> log_level == "DEBUG"              (trifft)
    LOGIN_MAX_VERSUCHE=9         -> login_max_versuche == 9           (trifft)
    WERKZEUGLIMIT_ENTSPRERREN=7  -> werkzeuglimit_entsperren == 10    (GREIFT NICHT)

Der dritte Fall ist der Grund fuer die `validation_alias`-Aliasse. Ohne
sie waere eine in `.env` gesetzte Variable **still unwirksam**, und der
Betreiber haelt sie fuer gesetzt, weil die Doku sie erwaehnt — der
schlimmste Fall, weil er nicht auffaellt.

A1c10 fuegt zwei Felder hinzu, die in genau diese Falle gehoeren:
`LOGIN_MAX_VERSUCHE_IP` und `LOGIN_IP_SPERRE_AUCH_PRIVAT`. Ohne Aliase
waere die Adressschwelle **immer** 5 — und die Karte waere zur Haelfte
wirkungslos, ohne dass irgendjemand es bemerkte.

Diese Datei steht bewusst neben `test_a1c6_werkzeuglimit_env.py` und nicht
im Modul-Test: es geht um die Verkabelung der Konfiguration, nicht um die
Sperrlogik (`test_a1c10_sperren.py`).
"""

from __future__ import annotations

import pytest

from diakronos_app.settings import Settings

GROSS_IP = "LOGIN_MAX_VERSUCHE_IP"
KLEIN_IP = "login_max_versuche_ip"
GROSS_PRIVAT = "LOGIN_IP_SPERRE_AUCH_PRIVAT"
KLEIN_PRIVAT = "login_ip_sperre_auch_privat"


@pytest.fixture(autouse=True)
def _ohne_umgebung(monkeypatch):
    """Beide Schreibweisen entfernt — sonst erbt der Test die Umgebung des
    Containers, und ein Rest von `LOGIN_MAX_VERSUCHE_IP` wuerde den
    Default-Test stillschweigend gruen machen."""
    for name in (GROSS_IP, KLEIN_IP, GROSS_PRIVAT, KLEIN_PRIVAT,
                 "LOGIN_MAX_VERSUCHE", "login_max_versuche"):
        monkeypatch.delenv(name, raising=False)


# ── Die Defaults: eine bestehende Installation startet ohne Aenderung ──────


def test_der_default_greift_ohne_umgebung():
    """Ohne `.env`: 5 am Konto, 25 an der Adresse, Proxy-Regel an.

    Genau das ist die Vorgabe der Karte — und die Bedingung dafuer, dass
    eine bestehende Installation ohne Aenderung startet und trotzdem
    sperrt. Faellt einer dieser drei Werte aus, ist das ein Ausfall, kein
    Detail.
    """
    s = Settings()

    assert s.login_max_versuche == 5, "die Kontosperre wurde verschoben"
    assert s.login_max_versuche_ip == 25, "die Adressschwelle ist nicht 25"
    assert s.login_ip_sperre_auch_privat is False, (
        "die Proxy-Regel ist per Default AUS — die Karte will sie AN"
    )


def test_der_default_ist_auch_am_Store_der_wirksame_wert(fake_redis):
    """Nicht nur die Settings-Felder, sondern der **angewendete** Wert.

    Ein Default im Settings-Objekt, den der Store nicht liest, waere genau
    die stille Unwirksamkeit, die diese Datei verhindert. Deshalb wird
    hier die echte Schwelle des Stores gemessen — nicht die Konfiguration.
    """
    from diakronos_app.frappe_compat import loginversuche as lv

    assert lv._max_versuche("u") == 5
    assert lv._max_versuche("ip") == 25
    assert lv._ist_eigene_adresse("127.0.0.1") is True


# ── ENV setzt beide Schwellen ──────────────────────────────────────────────


def test_die_adressschwelle_ist_ueber_env_setzbar(monkeypatch):
    """Der Kern: **ENV-schaltbar**, in der Schreibweise aus dem Compose."""
    monkeypatch.setenv(GROSS_IP, "3")

    assert Settings().login_max_versuche_ip == 3


def test_der_exakte_regressionsfall_trifft_auch_hier(monkeypatch):
    """Der Befund aus A1c3 als Test, fuer das **neue** Feld.

    Ohne `validation_alias` liefert `Settings()` hier 25 und der Test
    schlaegt fehl. Genau das ist der Fehler, den diese Karte nicht
    zurueckbringen darf: eine Schwellenzahl, die man einstellt und
    trotzdem nicht bekommt.
    """
    monkeypatch.setenv(GROSS_IP, "7")

    assert Settings().login_max_versuche_ip == 7, (
        "LOGIN_MAX_VERSUCHE_IP greift nicht — der Wert waere still unwirksam"
    )


def test_der_escape_hatch_ist_ueber_env_setzbar(monkeypatch):
    """Auch der Proxy-Schalter muss ENV-wirksam sein.

    Sonst koennte ein Betreiber die Regel nicht aufheben, die diese Karte
    eingefuehrt hat — die Fluchtklappe waere nur auf dem Papier da.
    """
    monkeypatch.setenv(GROSS_PRIVAT, "1")

    assert Settings().login_ip_sperre_auch_privat is True


def test_der_escape_hatch_ist_auch_auf_die_kleinschreibung_setzbar(monkeypatch):
    """Beide Schreibweisen treffen — wie bei `werkzeuglimit_entsperren`.

    Der zweite Alias ist nicht Dekoration: `.env` UND direkter
    Python-Zugriff muessen weiter beide funktionieren, und ein Aufrufer,
    der das Feld in einem Test ueberschreibt, ueberschreibt es auf dem
    Feldnamen.
    """
    monkeypatch.setenv(KLEIN_IP, "9")
    monkeypatch.setenv(KLEIN_PRIVAT, "1")

    s = Settings()

    assert s.login_max_versuche_ip == 9
    assert s.login_ip_sperre_auch_privat is True


def test_die_kontoschwelle_haengt_nicht_an_der_adressschwelle(monkeypatch):
    """Die Schwellen sind **unabhaengig** — eine Karte, zwei Werte.

    Wer `LOGIN_MAX_VERSUCHE_IP` auf 3 stellt, sperrt damit nicht auch
    jedes Konto nach 3 Fehlversuchen. Das waere die Umkehrung der
    Absicht: die Kontosperre soll die mit Abstand engere bleiben.
    """
    monkeypatch.setenv(GROSS_IP, "3")

    s = Settings()

    assert s.login_max_versuche == 5, "die Kontoschwelle wurde mitgezogen"
    assert s.login_max_versuche_ip == 3


def test_der_wirkliche_wert_der_adressschwelle_kommt_aus_der_env(monkeypatch):
    """Und die ENV wirkt auch dort, wo gesperrt wird — nicht nur gelesen.

    Der Store liest `settings` zur **Laufzeit** (nicht beim Import), deshalb
    genuegt `monkeypatch.setenv` plus ein Neusetzen des Settings-Objekts —
    hier wird deshalb direkt am Settings-Objekt gepatcht, wie es der
    Produktivpfad tut.
    """
    from diakronos_app.frappe_compat import loginversuche as lv

    monkeypatch.setattr(lv.settings, "login_max_versuche_ip", 2)

    assert lv._max_versuche("ip") == 2

    # Und gemessen an der Sperre selbst, nicht nur an der Funktion:
    for nummer in range(3):
        lv.pruefe_und_merke(f"opfer{nummer}@example.org", "203.0.113.77")
    assert lv.ist_gesperrt(None, "203.0.113.77") is True, (
        "die gesetzte Schwelle wirkt nicht auf die Sperre"
    )
