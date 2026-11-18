"""SPEICHER-1 — Einstellungen der Datei-Ablage.

Der Standard ist und bleibt ``lokal``: eine bestehende Installation darf durch
ein Update nicht anfangen, ihre Dateien woanders abzulegen (Kartenvorgabe 3
„Ohne Einstellung bleibt alles exakt wie heute“).

Geprueft wird ausserdem, dass ein Tippfehler den Start BRICHT statt still auf
``lokal`` zurueckzufallen, und dass das App-Passwort nur aus der Umgebung
kommt, nie protokolliert wird und in keiner Meldung erscheint.
"""

from __future__ import annotations

import logging

import pytest

from diakronos_app.settings import Settings

#: Alle Werte, die eine .env mitbringen kann — hier explizit leer, damit die
#: Umgebung des Testlaufs das Ergebnis nicht verfaelscht.
LEER = {
    "SPEICHER_BACKEND": "",
    "NEXTCLOUD_URL": "",
    "NEXTCLOUD_BENUTZER": "",
    "NEXTCLOUD_APP_PASSWORT": "",
    "NEXTCLOUD_ORDNER": "",
}


def _bauen(monkeypatch, **werte) -> Settings:
    for name, wert in {**LEER, **werte}.items():
        if wert == "":
            monkeypatch.delenv(name, raising=False)
        else:
            monkeypatch.setenv(name, str(wert))
    return Settings()


# ── Der Standard ───────────────────────────────────────────────────────────


def test_ohne_einstellung_bleibt_alles_lokal(monkeypatch):
    einstellungen = _bauen(monkeypatch)
    assert einstellungen.speicher_backend == "lokal"
    assert einstellungen.files_dir == "/data/files"


def test_backend_wird_kleingeschrieben(monkeypatch):
    assert _bauen(monkeypatch, SPEICHER_BACKEND="NextCloud").speicher_backend == "nextcloud"


def test_unbekanntes_backend_bricht_den_start(monkeypatch):
    """`nextclod` darf NICHT still auf `lokal` zurueckfallen.

    Sonst schreibt die Gemeinde weiter in den Container und haelt ihre
    Dateien fuer „in der Nextcloud“ — der schlimmste Zustand, weil er nicht
    auffaellt.
    """
    with pytest.raises(ValueError) as fehler:
        _bauen(monkeypatch, SPEICHER_BACKEND="nextclod")
    text = str(fehler.value)
    assert "SPEICHER_BACKEND" in text
    assert "'lokal'" in text and "'nextcloud'" in text


# ── Nextcloud-Werte ────────────────────────────────────────────────────────


def test_ordner_wird_normalisiert(monkeypatch):
    einstellungen = _bauen(monkeypatch, NEXTCLOUD_ORDNER="Diakronos/Bilder/")
    assert einstellungen.nextcloud_ordner == "/Diakronos/Bilder"


def test_leerer_ordner_ist_erlaubt(monkeypatch):
    """Leer = Wurzel des Benutzers — das ist der Default-Wert des Feldes.

    Eine GESETZTE leere ENV zaehlt bei pydantic-settings als „nicht gesetzt“
    (der Feld-Default `/Diakronos` gilt) — deshalb hier direkt der Default.
    """
    assert Settings().nextcloud_ordner == "/Diakronos"
    # Ausdruecklich auf die Wurzel stellen geht ueber einen Schraegstrich.
    assert _bauen(monkeypatch, NEXTCLOUD_ORDNER="/").nextcloud_ordner == ""


@pytest.mark.parametrize("ordner", ["/Diakronos/../etc", "/a/./b", "a\\\\b"])
def test_unsicherer_ordner_bricht_den_start(monkeypatch, ordner):
    with pytest.raises(ValueError) as fehler:
        _bauen(monkeypatch, NEXTCLOUD_ORDNER=ordner)
    assert "NEXTCLOUD_ORDNER" in str(fehler.value)


def test_halb_gesetzter_zugang_gilt_als_nicht_konfiguriert(monkeypatch):
    einstellungen = _bauen(monkeypatch, NEXTCLOUD_URL="https://cloud.example.org",
                           NEXTCLOUD_BENUTZER="diakronos")
    assert einstellungen.nextcloud_konfiguriert is False
    vollstaendig = _bauen(monkeypatch, NEXTCLOUD_URL="https://cloud.example.org",
                          NEXTCLOUD_BENUTZER="diakronos",
                          NEXTCLOUD_APP_PASSWORT="x")
    assert vollstaendig.nextcloud_konfiguriert is True


@pytest.mark.parametrize("wert", [0, -1, 3601, "viel"])
def test_zeitlimit_ausserhalb_der_grenzen_bricht_den_start(monkeypatch, wert):
    """0 waere in httpx „kein Limit“ — eine haengende Nextcloud blockiert dann."""
    with pytest.raises(ValueError):
        _bauen(monkeypatch, NEXTCLOUD_TIMEOUT_SEKUNDEN=wert)


def test_versuche_sind_begrenzt(monkeypatch):
    assert _bauen(monkeypatch, NEXTCLOUD_VERSUCHE=1).nextcloud_versuche == 1
    with pytest.raises(ValueError):
        _bauen(monkeypatch, NEXTCLOUD_VERSUCHE=0)


# ── Das Geheimnis ──────────────────────────────────────────────────────────


def test_app_passwort_kommt_aus_der_umgebung(monkeypatch):
    einstellungen = _bauen(monkeypatch, NEXTCLOUD_APP_PASSWORT="geheim-123")
    assert einstellungen.nextcloud_app_passwort_effektiv == "geheim-123"


def test_app_passwort_steht_in_keiner_meldung(monkeypatch, caplog):
    """Auch bei einem kaputten Nachbarwert darf das Passwort nicht auftauchen."""
    caplog.set_level(logging.DEBUG)
    with pytest.raises(ValueError) as fehler:
        _bauen(monkeypatch, SPEICHER_BACKEND="nextclod",
               NEXTCLOUD_APP_PASSWORT="streng-geheim-4711")
    assert "streng-geheim-4711" not in str(fehler.value)
    assert "streng-geheim-4711" not in caplog.text


def test_repr_enthaelt_kein_passwort(monkeypatch):
    """``repr`` einer Instanz darf das Secret nicht tragen (Logs, Fehlerberichte).

    ``settings`` wird an vielen Stellen geloggt und in Ausnahmen
    mitgeschleppt; ohne ``Field(repr=False)`` stand das App-Passwort im
    Klartext im ``repr`` — im Test aufgefallen, hier festgehalten.
    """
    einstellungen = _bauen(monkeypatch, NEXTCLOUD_APP_PASSWORT="streng-geheim-4711")
    assert "streng-geheim-4711" not in repr(einstellungen)
    assert "streng-geheim-4711" not in str(einstellungen)
    # Der Wert selbst ist natuerlich weiter da (die Ablage braucht ihn).
    assert einstellungen.nextcloud_app_passwort_effektiv == "streng-geheim-4711"
