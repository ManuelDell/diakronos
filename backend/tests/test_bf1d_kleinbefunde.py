"""BF1d — Rest-Kleinbefunde K2–K10 aus dem vorausgehenden Review.

Jeder Test ist einem Kleinbefund des Reviews zugeordnet und prueft die
BEHEBUNG (bzw. die bewusst begruendete Entscheidung). Die Frontend-Helfer
(`bf1Anzeige.js`, `KronosDayEventsDialog.formatTimeRange`) liegen als reine
Logik vor und werden von den Node-Tests (`bf1Anzeige.test.mjs`,
`KronosDayEventsDialog`-Test) geprueft; hier stehen die Backend-seitigen
Punkte.

Befunde in dieser Datei:
  K6  Rechte- vor Existenzpruefung in der Gruppen-Auswahl (kein 500)
  K7  Kalender-Zeitparser: ISO/Offsets, kein stilles Verwerfen
  K8  Suche trimmt + NFC-normalisiert (mitglieder + Gruppen-Auswahl)
  K9  Lied-Katalogwerte: Vorkommen ohne Lied bleibt in der Liste
"""
from __future__ import annotations

from datetime import datetime

import pytest

import diakronos_app.api  # noqa: E402,F401 — Dekoratoren laufen beim Import
from diakronos_app.frappe_compat.session import set_user

# Gemeinsame echte DB-Welt (Gruppen/Untergruppen/Verantwortliche).
from test_p4a_gruppen import hierarchie  # noqa: E402,F401
# Lieder-Welt (Katalog + Nutzer) fuer den K9-Test.
from test_p4i_psalmos_musik import MUSIK, als_anna, welt  # noqa: E402,F401

PFAD = "/api/method/diakronos.diakonos.api.gruppen."


def _aufruf(client, name, **daten):
    return client.post(PFAD + name, json=daten)


# ── K6: Rechte- vor Existenzpruefung ───────────────────────────────────────


def test_k6_unbekannte_gruppe_fuer_fremden_ist_403_nicht_404(client, hierarchie):
    """K6: Eine unbekannte Gruppe darf einem Unberechtigten NICHT verraten,
    dass es sie nicht gibt. Vorher lief die Existenzpruefung zuerst und
    antwortete 404 („nicht gefunden“) — das unterschied „verboten“ von
    „gibt es nicht“ und war damit ein kleiner Informationskanal. Jetzt ist die
    Antwort fail closed 403."""
    set_user("mitglied-a@example.org")
    r = _aufruf(client, "get_gruppe_mitglieder_auswahl", gruppe_id="GIBT-ES-NICHT")
    assert r.status_code == 403, f"Erwartet 403 (fail closed), bekam {r.status_code}: {r.text}"


def test_k6_nichtnumerisches_limit_ist_kein_500(client, hierarchie):
    """K6: `int(limit)` mit einer Nicht-Zahl darf keinen Absturz (500) geben.
    Ein unsinniges Limit faellt auf die Vorgabe (keine Grenze) zurueck."""
    set_user("gruppenverantw@example.org")
    r = _aufruf(client, "get_gruppe_mitglieder_auswahl",
                gruppe_id="G-A1", limit="viele")
    assert r.status_code == 200, r.text
    assert isinstance(r.json()["message"], list)


# ── K7: Kalender-Zeitparser ────────────────────────────────────────────────


@pytest.mark.parametrize("wert,erwartet", [
    ("2026-10-15", (2026, 10, 15, 0, 0)),
    ("2026-10-15 13:45:00", (2026, 10, 15, 13, 45)),
    ("2026-10-15T13:45:00", (2026, 10, 15, 13, 45)),
    ("2026-10-15T13:45:00.123456", (2026, 10, 15, 13, 45)),
    ("2026-10-15T13:45:00+02:00", (2026, 10, 15, 13, 45)),
    ("2026-10-15T13:45:00Z", (2026, 10, 15, 13, 45)),
    ("  2026-10-15 13:45  ", (2026, 10, 15, 13, 45)),
])
def test_k7_zeitparser_liest_iso_varianten(wert, erwartet):
    """K7: Der Parser deckt ISO-Varianten mit `T`, Sekundenbruchteilen und
    Zeitzonen-Offset ab (vorher schnitt `text[: len(fmt) + 2]` sie still ab)."""
    from diakronos_app.api.kronos.calendar_get import _als_datetime

    d = _als_datetime(wert)
    assert d is not None, f"{wert!r} wurde nicht gelesen."
    assert (d.year, d.month, d.day, d.hour, d.minute) == erwartet


def test_k7_unlesbarer_start_wird_angezeigt_nicht_verworfen():
    """K7: Ein Termin mit unlesbarem Start darf nicht stillschweigend
    verschwinden. Die SQL-Abfrage hat ihn bereits als Treffer geliefert; die
    Anzeige-Pruefung gibt ihn dann frei (fail open in der ANZEIGE)."""
    from diakronos_app.api.kronos.calendar_get import _ueberlappt_fenster

    assert _ueberlappt_fenster("kein-datum", None, "2026-10-01 00:00:00",
                               "2026-10-31 23:59:59") is True


def test_k7_gueltiger_termin_ausserhalb_bleibt_ausgeschlossen():
    """K7 (Gegenprobe): Ein lesbarer Termin weit ausserhalb des Fensters bleibt
    draussen — die Fail-open-Aenderung greift nur bei unlesbaren Werten."""
    from diakronos_app.api.kronos.calendar_get import _ueberlappt_fenster

    assert _ueberlappt_fenster("2001-01-01 10:00:00", "2001-01-01 11:00:00",
                               "2026-10-01 00:00:00", "2026-10-31 23:59:59") is False


def test_k7_mitternachtsende_reicht_nicht_in_den_folgetag():
    """K7 (Regression): Das Mitternachtsende wird weiterhin um 1 s
    zurueckgenommen — der Termin endet am Vortag."""
    from diakronos_app.api.kronos.calendar_get import _ueberlappt_fenster

    # Ende 04.10. 00:00 -> darf am 04.10. NICHT auftauchen.
    assert _ueberlappt_fenster("2026-10-03 20:00:00", "2026-10-04 00:00:00",
                               "2026-10-04 00:00:00", "2026-10-04 23:59:59") is False
    # Am 03.10. schon.
    assert _ueberlappt_fenster("2026-10-03 20:00:00", "2026-10-04 00:00:00",
                               "2026-10-03 00:00:00", "2026-10-03 23:59:59") is True


# ── K8: Suche trimmt + NFC ─────────────────────────────────────────────────


def test_k8_suche_normalisieren_trimmt_und_nfc():
    """K8: `_suche_normalisieren` trimmt (vorher lieferte „müller “ nichts)
    und normalisiert auf NFC (zerlegtes „u + Trema“ passt sonst nicht zur
    REPLACE-Kette)."""
    import unicodedata

    from diakronos_app.api.mitglieder import _suche_normalisieren

    assert _suche_normalisieren("Müller ") == _suche_normalisieren("müller")
    assert _suche_normalisieren("  Müller  ") == "mueller"
    zerlegt = unicodedata.normalize("NFD", "Müller")  # u + Trema
    assert _suche_normalisieren(zerlegt) == "mueller"


def test_k8_gruppen_auswahl_normalisiert_ebenfalls():
    """K8: Dieselbe Normalisierung in der Gruppen-Auswahl (sonst laufen
    server- und SPA-Feinfilter auseinander)."""
    import unicodedata

    from diakronos_app.api.gruppen_auswahl import _normalisieren

    assert _normalisieren("  Müller ") == "mueller"
    assert _normalisieren(unicodedata.normalize("NFD", "Weiß")) == "weiss"


# ── K9: Lied-Katalogwerte ohne Lied ────────────────────────────────────────


def test_k9_katalog_ohne_lied_bleibt_in_der_liste(client, als_anna, welt):
    """K9: Ein Katalogwert (Anlass), der als Stammdatum existiert, aber keinem
    Lied zugeordnet ist, bleibt in der Filterliste — sonst waere der Filter
    praktisch blind. Das ist der Kern der BF1-Aenderung an `musik.py`
    (vorher summierte die Liste nur die an Liedern haengenden Zuordnungen)."""
    from diakronos_app.models.psalmos import Liedanlass

    sess = welt
    sess.add(Liedanlass(name="LA-K9-LEER", anlassname="OhneLied"))
    sess.commit()

    r = client.get(f"/api/method/{MUSIK}.get_lied_filteroptionen")
    assert r.status_code == 200, r.text
    anlaesse = r.json()["message"]["anlaesse"]
    assert "OhneLied" in anlaesse, (
        "Katalogwert ohne Lied fehlt in den Filteroptionen — der Filter waere blind."
    )
