"""Bedarfspruefung (P5): benutzte Quellen und ihre konkrete Datenabdeckung."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .datenquelle import Datenquelle
from .pfade import passt_zu_feld
from .rollen import kandidaten


def _zahlwort(anzahl: int, einzahl: str, mehrzahl: str) -> str:
    """OP-CHOR-12: Zahl mit richtigem Numerus („1 Person“, „2 Personen“)."""
    return f"{anzahl} {einzahl if anzahl == 1 else mehrzahl}"


def _anzeigenamen(plantyp: dict[str, Any]) -> dict[str, str]:
    """Kennung → Anzeigename aus Merkmalen, Feldern und Rollen der Vorlage.

    Die Vorlage führt Merkmale gruppiert (``merkmale.person[]``,
    ``merkmale.lieder[]`` …); zusätzlich werden flache ``merkmale``-Listen und
    die Rollen gelesen.
    """
    namen: dict[str, str] = {}

    def merke(kennung: Any, name: Any) -> None:
        if isinstance(kennung, str) and kennung and isinstance(name, str) and name.strip():
            namen.setdefault(kennung, name.strip())

    def merke_liste(liste: Any) -> None:
        for eintrag in liste or []:
            if isinstance(eintrag, dict):
                merke(eintrag.get("id") or eintrag.get("kennung"), eintrag.get("name"))

    merkmale = plantyp.get("merkmale")
    if isinstance(merkmale, dict):
        # Vorlagenform: nach Zielart gruppiert. K8: bei gleicher Kennung in
        # mehreren Gruppen entscheidet sonst die Reihenfolge der Gruppen —
        # `person` gewinnt, denn der Bedarf meint Personen-Merkmale
        # (Chorplan `dirigent`: „dirigiert“ in person, „Standard-Dirigent“ in
        # lieder). Erst `person`, dann die uebrigen Gruppen.
        for ziel in ("person", "lieder"):
            if ziel in merkmale:
                merke_liste(merkmale[ziel])
        for gruppe, eintraege in merkmale.items():
            if gruppe not in ("person", "lieder"):
                merke_liste(eintraege)
    merke_liste(merkmale)
    merke_liste(plantyp.get("rollen"))
    return namen


@dataclass
class Bedarf:
    """Ein Datenbedarf mit Einrichtungshinweis fuer den Planer."""

    art: str
    kennung: str
    abdeckung: str
    detail: str
    einstufung: str
    # UXP-R23: Anzeigename statt interner Kennung („Klavier“ statt „klavier“).
    # Leer = die Oberfläche zeigt die Kennung (z. B. Sammlungen ohne Namen).
    name: str = ""


def bedarfspruefung(plantyp: dict[str, Any], datenquelle: Datenquelle) -> list[Bedarf]:
    """Folgt benutzten Rollen/Regeln/Quellen, ohne unbenutzte Daten zu fordern.

    Personenmerkmale und Sammlungsmerkmale werden getrennt ausgewertet:
    ``eintrag.dirigent`` fordert Daten des zugehoerigen Katalogs, nicht ein
    Personenmerkmal und nicht Daten aller anderen Sammlungen.

    UXP-R4/OP-EVENT-7: Auch Team- und Anmeldungs-Filter der Rollen werden
    ausgewertet. Fehlt für ein Team (Gruppe/Untergruppe) jede Person oder
    findet ein ``anmeldung``-Filter keine bestätigte Anmeldung, meldet der
    Bedarf das ausdrücklich („Teams unter ‚X': 0 vorhanden“ bzw. „Mitarbeiter
    aus Anmeldungen: 0“) — vorher blieb der Bedarfsdialog stumm und der
    Hinweis „Stammdaten prüfen“ war eine Sackgasse.
    """
    merkmale, sammlungen, rollen = _datenbedarfe(plantyp)
    # UXP-R23: Anzeigenamen aus der Vorlage (Feld „name“), damit im Dialog
    # „Klavier“ statt „klavier“ steht.
    namen = _anzeigenamen(plantyp)
    bedarfe: list[Bedarf] = []
    personen = {p.kennung for p in datenquelle.personen()}
    for merkmal in sorted(merkmale):
        anzahl = sum(1 for p, wert in datenquelle.merkmal_werte(merkmal).items()
                     if p in personen and wert not in (False, None, 0))
        anzeige = namen.get(merkmal, merkmal)
        # UXP-R23: Der Name kann ein Hauptwort („Klavier“) oder eine Tätigkeit
        # („spielt Klavier“) sein — „hat/haben ‚…‘“ passt zu beidem und
        # richtet sich im Numerus nach der Zahl.
        hat = "hat" if anzahl == 1 else "haben"
        bedarfe.append(Bedarf("merkmal", merkmal,
                              f"{_zahlwort(anzahl, 'Person', 'Personen')} {hat} „{anzeige}“",
                              "", _personen_einstufung(anzahl), name=anzeige))
    for sammlung, geforderte in sorted(sammlungen.items()):
        eintraege = datenquelle.sammlung(sammlung)
        gesamt = len(eintraege)
        ohne = sum(1 for e in eintraege if any(e.attribut(m) in (None, "", False) for m in geforderte))
        if not gesamt:
            einstufung, abdeckung = "blockiert_automatik", f"Sammlung {sammlung!r} ist leer"
        elif ohne:
            einstufung, abdeckung = "eingeschraenkt", f"{gesamt - ohne}/{gesamt} Einträge vollständig"
        else:
            einstufung, abdeckung = "ok", f"{_zahlwort(gesamt, 'Eintrag', 'Einträge')}"
        detail = f"{ohne}/{gesamt} ohne {', '.join(sorted(geforderte))}" if geforderte else ""
        bedarfe.append(Bedarf("sammlung", sammlung, abdeckung, detail, einstufung))
    for rolle in sorted(rollen):
        anzahl = len(kandidaten("@" + rolle, datenquelle, plantyp))
        anzeige = namen.get(rolle, rolle)
        bedarfe.append(Bedarf("rolle", rolle,
                              f"{_zahlwort(anzahl, 'Person', 'Personen')} "
                              f"{'erfüllt' if anzahl == 1 else 'erfüllen'} die Rolle {anzeige}",
                              "", _personen_einstufung(anzahl), name=anzeige))
    for team_obergruppe in sorted(_team_filter(plantyp)):
        teams = [g for g in datenquelle.gruppen() if g.obergruppe == team_obergruppe]
        mitglieder = len({m for g in teams for m in g.mitglieder})
        detail = f"Teams unter „{team_obergruppe}“"
        if not teams:
            bedarfe.append(Bedarf("team", team_obergruppe,
                                  f"Teams unter „{team_obergruppe}“: 0 vorhanden", detail,
                                  "blockiert_automatik"))
        elif mitglieder == 0:
            bedarfe.append(Bedarf("team", team_obergruppe,
                                  f"{len(teams)} Teams unter „{team_obergruppe}“, aber ohne Mitglieder",
                                  detail, "blockiert_automatik"))
        else:
            bedarfe.append(Bedarf("team", team_obergruppe,
                                  f"{len(teams)} Teams unter „{team_obergruppe}“ ({mitglieder} Personen)",
                                  detail, _personen_einstufung(mitglieder)))
    for anmeldung in sorted(_anmeldung_filter(plantyp)):
        anzahl = len(datenquelle.anmeldungen(anmeldung))
        bedarfe.append(Bedarf("anmeldung", anmeldung,
                              f"Mitarbeiter aus Anmeldungen: {anzahl}",
                              f"bestätigte Anmeldungen mit Rolle „{anmeldung}“",
                              _personen_einstufung(anzahl)))
    return bedarfe


def _personen_einstufung(anzahl: int) -> str:
    """Kein Traeger blockiert Automatik, ein Traeger schraenkt Auswahl ein."""
    return "ok" if anzahl > 1 else "eingeschraenkt" if anzahl else "blockiert_automatik"


def _datenbedarfe(plantyp: dict[str, Any]) -> tuple[set[str], dict[str, set[str]], set[str]]:
    """Sammelt rekursiv nur tatsaechlich benutzte Daten mit Quellzuordnung."""
    merkmale: set[str] = set()
    sammlungen: dict[str, set[str]] = {}
    rollen: set[str] = set()
    rollenfilter = {r["id"]: r.get("filter") for r in _objekte(plantyp.get("rollen"))}
    eintragsfelder: list[tuple[str, str]] = []

    def filter_bedarf(filter: Any) -> None:
        if isinstance(filter, str) and filter.startswith("@"):
            kennung = filter[1:]
            if kennung not in rollen:
                rollen.add(kennung)
                filter_bedarf(rollenfilter.get(kennung))
        elif isinstance(filter, dict):
            if isinstance(filter.get("merkmal"), str):
                merkmale.add(filter["merkmal"])
            for schluessel in ("alle", "eine"):
                for kind in filter.get(schluessel, []):
                    filter_bedarf(kind)
            filter_bedarf(filter.get("nicht"))

    def sammle(felder: Any, praefix: str = "", sammlung: str | None = None) -> None:
        for f in _objekte(felder):
            fid = f.get("id", "")
            pfad = praefix + fid if praefix.endswith(":") else f"{praefix}.{fid}" if praefix else fid
            quelle = sammlung
            if f.get("art") == "eintrag":
                quelle = f.get("sammlung")
                if isinstance(quelle, str) and not quelle.startswith("{parameter."):
                    sammlungen.setdefault(quelle, set())
                    eintragsfelder.append((pfad, quelle))
                else:
                    quelle = None
            filter_bedarf(f.get("rolle"))
            filter_bedarf(f.get("mitglieder"))
            aus = f.get("aus")
            if quelle and isinstance(aus, str) and aus.startswith("eintrag."):
                sammlungen.setdefault(quelle, set()).add(aus[len("eintrag."):])
            sammle(f.get("inhalt"), pfad, quelle)
            for zweig in _objekte(f.get("varianten")) + _objekte(f.get("teile")):
                sammle(zweig.get("inhalt"), pfad, quelle)
            for element in _objekte(f.get("elemente")):
                inhalt = _objekte(element.get("inhalt"))
                # Ablauf-Besetzung liest den einzigen Eintrag desselben Elements.
                quellen = {kind.get("sammlung") for kind in inhalt if kind.get("art") == "eintrag"}
                element_quelle = next(iter(quellen)) if len(quellen) == 1 else None
                if not isinstance(element_quelle, str) or element_quelle.startswith("{parameter."):
                    element_quelle = None
                sammle(inhalt, pfad, element_quelle)

    sammle(plantyp.get("felder"))
    for reihe in _objekte(plantyp.get("terminreihen")):
        sammle(reihe.get("felder"), reihe["id"] + ":")
    for anlass in _objekte(plantyp.get("anlaesse")):
        sammle((anlass.get("wirkung") or {}).get("mit"))
    for regel in _objekte(plantyp.get("regeln")):
        filter_bedarf(regel.get("rolle"))
        merkmal = regel.get("merkmal")
        if isinstance(merkmal, str):
            felder = [regel["feld"]] if regel.get("feld") else regel.get("felder", [])
            for pfad, quelle in eintragsfelder:
                if not felder or any(passt_zu_feld(pfad, f) for f in felder):
                    sammlungen[quelle].add(merkmal)
    return merkmale, sammlungen, rollen


def _team_filter(plantyp: dict[str, Any]) -> set[str]:
    """Obergruppen-Namen der verwendeten ``team``-Filter (UXP-R4).

    Ein Team-Feld traegt ``teams: {"gruppe_unter": "<Obergruppe>"}`` oder eine
    feste Kennungsliste. Nur die Obergruppen-Variante erzeugt einen
    Einrichtungshinweis — bei fester Liste ist der Planer selbst verantwortlich.
    """
    treffer: set[str] = set()

    def besuche(felder: Any) -> None:
        for f in _objekte(felder):
            if f.get("art") == "team" and isinstance(f.get("teams"), dict):
                unter = f["teams"].get("gruppe_unter")
                if isinstance(unter, str) and unter:
                    treffer.add(unter)
            besuche(f.get("inhalt"))
            for zweig in _objekte(f.get("varianten")) + _objekte(f.get("teile")):
                besuche(zweig.get("inhalt"))
            for element in _objekte(f.get("elemente")):
                besuche(element.get("inhalt"))

    besuche(plantyp.get("felder"))
    for reihe in _objekte(plantyp.get("terminreihen")):
        besuche(reihe.get("felder"))
    return treffer


def _anmeldung_filter(plantyp: dict[str, Any]) -> set[str]:
    """Rollen der verwendeten ``anmeldung``-Filter (OP-EVENT-7)."""
    treffer: set[str] = set()

    def besuche(filter: Any) -> None:
        if isinstance(filter, str) and filter.startswith("@"):
            for r in _objekte(plantyp.get("rollen")):
                if r.get("id") == filter[1:]:
                    besuche(r.get("filter"))
        elif isinstance(filter, dict):
            if isinstance(filter.get("anmeldung"), str):
                treffer.add(filter["anmeldung"])
            for schluessel in ("alle", "eine"):
                for kind in filter.get(schluessel, []):
                    besuche(kind)
            besuche(filter.get("nicht"))

    for feld in _alle_felder(plantyp):
        besuche(feld.get("rolle"))
        besuche(feld.get("mitglieder"))
    for regel in _objekte(plantyp.get("regeln")):
        besuche(regel.get("rolle"))
        besuche(regel.get("mitglieder"))
    return treffer


def _alle_felder(plantyp: dict[str, Any]) -> list[dict[str, Any]]:
    """Alle Feldknoten (Felder, Reihen, Anlasswirkungen) flach (rekursiv)."""
    result: list[dict[str, Any]] = []

    def sammle(felder: Any) -> None:
        for f in _objekte(felder):
            result.append(f)
            sammle(f.get("inhalt"))
            for zweig in _objekte(f.get("varianten")) + _objekte(f.get("teile")):
                sammle(zweig.get("inhalt"))
            for element in _objekte(f.get("elemente")):
                sammle(element.get("inhalt"))

    sammle(plantyp.get("felder"))
    for reihe in _objekte(plantyp.get("terminreihen")):
        sammle(reihe.get("felder"))
    for anlass in _objekte(plantyp.get("anlaesse")):
        sammle((anlass.get("wirkung") or {}).get("mit"))
    return result


def _objekte(items: Any) -> list[dict[str, Any]]:
    """Objekt-Kurzformen aus Feld-/Zweiglisten lesen."""
    return [it for it in (items or []) if isinstance(it, dict)]
