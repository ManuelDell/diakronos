"""ZEIT-3 — Waechter: kein neues ``date.today()``/``datetime.now()`` in ``api/``.

Der Container laeuft in **UTC**. ``date.today()`` liefert zwischen 0 und 2 Uhr
Ortszeit den **Vortag** — genau der Befund dieser Karte (Einwilligungsdatum,
Dienstplan-Woche, „Zuletzt bearbeitet“, Monatsanfang). „Heute“ ist seither der
Kalendertag in ``CALENDAR_TIMEZONE``: ``diakronos_app.zeit.heute_gemeinde()``
bzw. ``heute_iso()``; Anzeigen technischer Zeitstempel laufen ueber
``zeit.zeit_text``.

Dieser Test haelt den **Bestand** fest: technische Zeitstempel
(``created``/``modified``/``creation``/``zeitpunkt``) bleiben bewusst bei der
Wanduhr des Containers — DAS ist Frappe-Konvention und Vergleichsbasis fuer
Fristen und Jobs. Der Bestand darf deshalb nur SCHRUMPFEN: wer eine dieser
Stellen in eine fachliche Datumsangabe umbaut, streicht sie aus der Liste;
wer eine neue anlegt, faellt hier auf.

Bewusste Ausnahme der Regel: ``anmeldung.einstellungen_api`` und
``anmeldung.zuordnung`` liegen ausserhalb von ``api/`` und schreiben ebenfalls
technische Zeitstempel (Vorbild fuer diesen Waechter: ``test_aufr1``).
"""

from __future__ import annotations

import inspect
import re
from pathlib import Path

import pytest

API = Path(__file__).resolve().parents[1] / "src/diakronos_app/api"

#: Bestand zum Zeitpunkt der Karte (09.11.2026) als ANZAHL je Datei. Jede
#: Stelle ist eine TECHNISCHE Zeit (Protokoll-/Aenderungszeitstempel), kein
#: fachliches Datum. Bewusst Anzahl statt Zeilennummer (ZEIT-3-Review): eine
#: Zeilenliste brach bei jeder Aenderung oberhalb der Stelle, auch ohne neuen
#: Aufruf.
BESTAND: dict[str, int] = {
    "dienstplan.py": 1,             # _now_str(): Ausgabe-Text fuer Protokolle
    "einrichtung.py": 4,            # created/modified der Einrichtungs-Zeile
    "gemeinde.py": 12,              # created/creation/modified
    "papierkorb.py": 1,             # Papierkorb-Zeitstempel
    "verantwortliche.py": 2,        # creation/modified
}

MUSTER = re.compile(r"date\.today\(\)|datetime\.date\.today\(\)|datetime\.now\(\)")


def _treffer() -> dict[str, set[int]]:
    """Datei -> Zeilennummern mit ``date.today()``/``datetime.now()``.

    Docstrings werden entfernt (sie ERKLAEREN die Regel und nennen die
    verbotenen Aufrufe), damit nur echter Code zaehlt. Die Zeilennummern
    bleiben dabei erhalten (gleiche Zeichenzahl je Zeile).
    """
    gefunden: dict[str, set[int]] = {}
    for pfad in sorted(API.rglob("*.py")):
        roh = pfad.read_text(encoding="utf-8").splitlines()
        zeilen = list(roh)
        # Docstrings (auch Funktions-/Klassen-Docstrings) durch Leerzeilen
        # ersetzen — sie ERKLAEREN die Regel und nennen die verbotenen Aufrufe.
        offen = ""
        for i, zeile in enumerate(roh):
            blank = zeile.replace("\\", "")
            if not offen:
                for anf in ('"""', "'''"):
                    if blank.count(anf) % 2 == 1:
                        offen = anf
                        zeilen[i] = ""
                        break
            else:
                if offen in blank:
                    offen = ""
                zeilen[i] = ""
        nummern = {
            nr for nr, zeile in enumerate(zeilen, 1)
            if MUSTER.search(zeile) and not zeile.strip().startswith("#")
        }
        if nummern:
            gefunden[pfad.relative_to(API).as_posix()] = nummern
    return gefunden


def test_keine_neuen_wanduhr_aufrufe_in_api():
    """Der Bestand darf nur schrumpfen — neue Stellen fallen hier auf."""
    neu = {}
    for datei, nummern in _treffer().items():
        erlaubt = BESTAND.get(datei, 0)
        if len(nummern) > erlaubt:
            neu[datei] = sorted(nummern)
    assert not neu, (
        "Neue Wanduhr-Aufrufe in api/ — „heute“ ist der Kalendertag in "
        "CALENDAR_TIMEZONE (`diakronos_app.zeit.heute_gemeinde()`), „jetzt“ "
        "gegen Termin-Wandzeiten `zeit.jetzt_wanduhr()`: "
        f"{neu}"
    )


def test_bestandsliste_ist_nicht_veraltet():
    """Weniger Stellen als gezaehlt -> Liste nachziehen (sonst deckt sie Neues zu)."""
    gefunden = _treffer()
    veraltet = {
        datei: (anzahl, len(gefunden.get(datei, set())))
        for datei, anzahl in BESTAND.items()
        if len(gefunden.get(datei, set())) < anzahl
    }
    assert not veraltet, (
        "Diese Dateien haben weniger Wanduhr-Aufrufe als BESTAND — bitte die "
        f"Zahl senken (Datei: (Liste, gefunden)): {veraltet}"
    )


def test_zentrale_funktion_ist_die_einzige_rechnung():
    """EINE Rechnung: ``date.today()`` steht nirgends mehr als Fachlogik."""
    from diakronos_app import zeit
    from diakronos_app.anmeldung import registrierungslink

    quelle_zeit = Path(zeit.__file__).read_text(encoding="utf-8")
    assert "datetime.now(" in quelle_zeit
    # Die alte Kopie in `anmeldung/registrierungslink.py` reicht nur noch durch.
    quelle_link = Path(registrierungslink.__file__).read_text(encoding="utf-8")
    assert "from diakronos_app.zeit import jetzt_gemeinde" in quelle_link


def test_heute_und_today_haengen_an_der_gemeindezeit():
    """Die zwei Naehte, ueber die fast alle Portierungen laufen."""
    from diakronos_app.api import gruppen
    from diakronos_app.frappe_compat import api_helpers

    for modul, name in ((api_helpers, "_today"), (gruppen, "_today")):
        # Doktorstring abschneiden (er erklaert, was NICHT mehr gilt).
        body = inspect.getsource(getattr(modul, name))
        code = body.split('"""')[-1] if '"""' in body else body
        assert "date.today()" not in code, (
            f"{modul.__name__}.{name} darf nicht mehr `date.today()` nehmen"
        )


def test_termin_wandzeiten_werden_nicht_umgerechnet():
    """Abgrenzung: ``element_start`` ist Ortszeit — keine Zeitzonen-Rechnung."""
    quelle = (API / "kronos/kalender.py").read_text(encoding="utf-8")
    assert "zeit_text(" not in quelle and "jetzt_gemeinde" not in quelle
