"""P3-1: Texte der Bedarfsprüfung — Numerus, Umlaute, Anzeigenamen.

Reproduziert zuvor (OP-CHOR-12, UXP-R23):
  * „1 Personen mit klavier“ — falscher Numerus, Merkmals-Kennung statt Name.
  * „3 Eintraege“ / „2/3 Eintraege vollstaendig“ — ae statt Umlaut, kein Numerus.
  * „1 Personen erfuellen Rolle dirigent“ — Numerus und Kennung.
"""

from __future__ import annotations

import re

from diakronos_app.planrahmen import ressourcen
from diakronos_app.planrahmen.engine.bedarf import _zahlwort, bedarfspruefung
from diakronos_app.planrahmen.engine.datenquelle import (
    InMemoryDatenquelle,
    Person,
    Sammlungseintrag,
)


def test_zahlwort_setzt_den_numerus():
    assert _zahlwort(1, "Person", "Personen") == "1 Person"
    assert _zahlwort(2, "Person", "Personen") == "2 Personen"
    assert _zahlwort(1, "Eintrag", "Einträge") == "1 Eintrag"
    assert _zahlwort(0, "Eintrag", "Einträge") == "0 Einträge"


def _quelle_mit_einem_lied(vollstaendig: bool) -> InMemoryDatenquelle:
    """Sammlung 'lieder' mit genau einem Eintrag (wahlweise unvollständig)."""
    eintrag = Sammlungseintrag(
        kennung="l1",
        sammlung="lieder",
        titel="Komm, sag es allen weiter",
        merkmale={"heft": "FJ"} if vollstaendig else {},
    )
    return InMemoryDatenquelle(sammlungen={"lieder": [eintrag]})


def _bedarf_fuer(quelle, **plantyp):
    typ = {"id": "t1"}
    typ.update(plantyp)
    return {b.kennung: b for b in bedarfspruefung(typ, quelle)}


def _merkmal_feld(kennung: str) -> dict:
    """Ein Feld, das ein Personen-Merkmal benutzt (so entsteht der Bedarf)."""
    return {"id": kennung, "art": "person", "rolle": {"merkmal": kennung}}


def test_einziger_vollstaendiger_eintrag_ist_einzahl_mit_umlaut():
    bedarf = _bedarf_fuer(
        _quelle_mit_einem_lied(True),
        felder=[{
            "id": "lieder", "art": "eintrag", "sammlung": "lieder", "anzahl": 1,
            "inhalt": [{"id": "heft", "art": "text"}],
        }],
    )
    abdeckung = bedarf["lieder"].abdeckung
    assert abdeckung == "1 Eintrag", f"Numerus/Umlaut falsch: {abdeckung!r}"
    assert "Eintraege" not in abdeckung


def test_merkmal_nennt_den_anzeigenamen_statt_der_kennung():
    """UXP-R23: im Bedarfsdialog heißt es „Klavier“, nicht „klavier“."""
    quelle = InMemoryDatenquelle(
        personen_liste=[Person("p1", name="Anna")],
        merkmale={"klavier": {"p1": True}},
    )
    bedarf = _bedarf_fuer(
        quelle,
        merkmale={"person": [{"id": "klavier", "name": "Klavier", "art": "tag"}]},
        felder=[_merkmal_feld("klavier")],
    )
    eintrag = bedarf["klavier"]
    assert eintrag.name == "Klavier"
    assert "Klavier" in eintrag.abdeckung
    # Die reine Kennung „klavier“ (klein) erscheint nicht mehr im Satz.
    assert " mit klavier" not in eintrag.abdeckung
    # Einzahl, nicht „1 Personen“.
    assert "1 Person " in eintrag.abdeckung


def test_merkmal_ohne_namen_faellt_auf_die_kennung_zurueck():
    quelle = InMemoryDatenquelle()
    bedarf = _bedarf_fuer(
        quelle,
        merkmale={"person": [{"id": "einsingen", "art": "tag"}]},
        felder=[_merkmal_feld("einsingen")],
    )
    assert bedarf["einsingen"].name == "einsingen"
    assert "0 Personen" in bedarf["einsingen"].abdeckung


# --------------------------------------------------------------------------- #
# UXP-R23: Die Kochbuch-Vorlagen tragen die Texte, die die Oberfläche zeigt
# (Beschreibung, Anzeigenamen, Auswahlwerte). Dort gehoeren Umlaute hin —
# Kennungen (id, baustein, feld) bleiben ASCII.
# --------------------------------------------------------------------------- #

# Ersatzschreibweisen, die als ANZEIGETEXT ein Fehler sind.
_FALSCH = (
    "Waehl", "waehl", "laeuft", "Anlaess", "koenn", "befuell", "Begruess",
    "Saenger", "eingefuehrt", "Verfuegbar", "muess", "Einueb", "Floete",
    "Maennerchor", "Wochentlich", "uebersprungen",
    # K3: diese beiden fehlten und standen sichtbar im Bedarfsdialog
    # (gottesdienstablauf.json „haelt die Predigt“, predigerplan.json
    # „predigt regulaer“).
    "haelt", "regulaer",
)

# Kennungen in Anfuehrungszeichen sind KEIN Anzeigetext: die Beschreibungen
# verweisen bewusst auf Regeln wie 'vorher_geuebt' (siehe programm.json).
_KENNUNG = re.compile(r"'[a-z_]+'")

_ANZEIGE_FELDER = ("beschreibung", "name", "werte", "titel", "hinweis")

# P3-1b (W3): Auswahlwerte sind GESPEICHERTE Kennungen (ASCII, ohne Umlaute:
# „Maennerchor“, „Floete“). Sie werden nie umbenannt, sonst passen gespeicherte
# Plaene nicht mehr. Angezeigt wird der Anzeigename aus `anzeigenamen` — und der
# wird hier geprueft. Nur dieser eine Fall ist ausgenommen.
_KENNUNGS_FELDER = ("werte",)


def _anzeigetexte(obj, pfad="", kennungsliste=False):
    """Alle Anzeigetexte einer Vorlage (ohne Kennungen) als (pfad, text).

    K3: Strings in Listen zaehlen ebenfalls — ``werte`` ist eine LISTE text-
    foermiger Eintraege, vorher fielen genau diese Werte durch (``"Floete"``
    und ``"Maennerchor"`` in ``_FALSCH`` waren wirkungslos).

    P3-1b (W3): Innerhalb von ``werte`` stehen Kennungen; dort wird NICHT auf
    Ersatzschreibung geprueft. Die Anzeigenamen daneben (``anzeigenamen``)
    werden geprueft.
    """
    if isinstance(obj, dict):
        for key, wert in obj.items():
            neuer = f"{pfad}/{key}"
            if key == "anzeigenamen" and isinstance(wert, dict):
                for kennung, anzeige in wert.items():
                    yield f"{neuer}[{kennung}]", str(anzeige)
            elif key in _ANZEIGE_FELDER and isinstance(wert, str):
                yield neuer, wert
            elif key in _ANZEIGE_FELDER and isinstance(wert, list):
                for i, eintrag in enumerate(wert):
                    if isinstance(eintrag, str):
                        yield f"{neuer}[{i}]", eintrag
                    else:
                        yield from _anzeigetexte(eintrag, f"{neuer}[{i}]")
            else:
                yield from _anzeigetexte(wert, neuer)
    elif isinstance(obj, list):
        for i, wert in enumerate(obj):
            yield from _anzeigetexte(wert, f"{pfad}[{i}]")


def _kennungspfade(obj, pfad=""):
    """Pfade aller ``werte``-Listen (dort stehen Kennungen, kein Anzeigetext)."""
    if isinstance(obj, dict):
        for key, wert in obj.items():
            neuer = f"{pfad}/{key}"
            if key in _KENNUNGS_FELDER and isinstance(wert, list):
                yield neuer
            else:
                yield from _kennungspfade(wert, neuer)
    elif isinstance(obj, list):
        for i, wert in enumerate(obj):
            yield from _kennungspfade(wert, f"{pfad}[{i}]")


def _auswahlfelder(obj, pfad=""):
    """Alle Felder/Merkmale/Parameter mit einer ``werte``-Liste: (pfad, objekt)."""
    if isinstance(obj, dict):
        for key, wert in obj.items():
            neuer = f"{pfad}/{key}"
            if key == "werte" and isinstance(wert, list):
                yield pfad, obj
            yield from _auswahlfelder(wert, neuer)
    elif isinstance(obj, list):
        for i, wert in enumerate(obj):
            yield from _auswahlfelder(wert, f"{pfad}[{i}]")


def test_kochbuch_anzeigetexte_haben_umlaute():
    """UXP-R23: keine ae/oe/ue-Ersatzschreibung in sichtbaren Texten."""
    befunde = []
    for name in ressourcen.kochbuch_dateinamen():
        vorlage = ressourcen.kochbuch_laden(name)
        kennungen = set(_kennungspfade(vorlage))
        for pfad, text in _anzeigetexte(vorlage):
            if any(pfad == k or pfad.startswith(k + "[") for k in kennungen):
                continue   # Auswahl-Kennung, kein Anzeigetext (W3)
            ohne_kennungen = _KENNUNG.sub("", text)
            for falsch in _FALSCH:
                if falsch in ohne_kennungen:
                    befunde.append(f"{name}{pfad}: „{falsch}“ in {text[:60]!r}")
    assert not befunde, "Umlaut-Ersatzschreibung in Anzeigetexten:\n" + "\n".join(befunde)


def test_auswahlkennung_mit_ersatzschreibung_hat_anzeigenamen():
    """UXP-R23/W3: ein ASCII-Kennungswert braucht einen Namen mit Umlaut.

    Die Kennung bleibt absichtlich „Maennerchor“/„Floete“ (sie ist in Plaenen
    gespeichert); damit die Oberflaeche sauber Deutsch zeigt, MUSS ein
    Anzeigename daneben stehen.
    """
    befunde = []
    for name in ressourcen.kochbuch_dateinamen():
        vorlage = ressourcen.kochbuch_laden(name)
        for pfad, feld in _auswahlfelder(vorlage):
            namen = feld.get("anzeigenamen") or {}
            for wert in feld.get("werte") or []:
                if not isinstance(wert, str):
                    continue
                ersatz = any(falsch in wert for falsch in _FALSCH)
                if ersatz and not namen.get(wert):
                    befunde.append(f"{name}{pfad}: Kennung {wert!r} ohne Anzeigenamen")
    assert not befunde, "Auswahlwerte ohne Anzeigenamen:\n" + "\n".join(befunde)


def test_kochbuch_beschreibung_nutzt_umlaute():
    """Stichprobe: die Beschreibung des Chorplans ist lesbarer Klartext."""
    text = ressourcen.kochbuch_laden("chorplan")["beschreibung"]
    assert "Wöchentlicher" in text
    assert "wählt" in text
    assert "Anlässe" in text
    assert "Wochentlicher" not in text
