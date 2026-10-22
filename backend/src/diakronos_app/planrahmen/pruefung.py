"""Pruefung einer Plantyp-Datei: Schema + Semantik.

`pruefe_plantyp(daten)` liefert eine Liste von Meldungen. Jede Meldung ist so
formuliert, dass ein KI-Agent (oder ein Mensch) sich im naechsten Versuch
selbst korrigieren kann (Konzept P10): Pfad (JSON-Pointer), Stufe, Code,
verstaendliche deutsche Meldung, konkreter Korrekturhinweis mit Mini-Beispiel
und Verweis (Doku-Anker).

Zwei Stufen:
1. Schema-Validierung gegen `plantyp-1.json` (jsonschema, Drum 2020-12),
   **alle** Fehler werden gesammelt, nicht nur der erste.
2. Semantische Pruefung: eindeutige Feld-Kennungen je Ebene, vorhandene
   Verweise (aus-Referenzen, Sammlungen, Anlass-Wirkungen, Regel-Felder,
   Parameter-Referenzen), Regelparameter gegen die Baustein-Registry,
   unbekannter Baustein mit Tippfehler-Vorschlag (difflib), widerspruechliche
   Angaben (anzahl min > max, varianten ohne gruppe), RRULE-Syntax (dateutil).
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field
from typing import Any, Iterable

import jsonschema
from dateutil.rrule import rrulestr

from . import ressourcen
from .rrule import rrule_problem
from .regeln.registry import (
    REGEL_BAUSTEINE_NA,
    bekannte_fuellstrategien,
    eingebaute_attribut_schluessel,
)

# --------------------------------------------------------------------------- #
# Meldung
# --------------------------------------------------------------------------- #


@dataclass
class Meldung:
    """Eine einzelne Pruef-Meldung (Ergebnis von `pruefe_plantyp`)."""

    pfad: str  # JSON-Pointer, z. B. "/felder/0/sammlung"
    stufe: str  # "fehler" oder "warnung"
    code: str
    meldung: str
    hinweis: str
    doku_anker: str = ""
    detail: Any = None

    def als_dict(self) -> dict[str, Any]:
        """Meldung als einfaches dict (fuer Agenten-Werkzeuge/Ausgabe)."""
        d = {
            "pfad": self.pfad,
            "stufe": self.stufe,
            "code": self.code,
            "meldung": self.meldung,
            "hinweis": self.hinweis,
            "doku_anker": self.doku_anker,
        }
        if self.detail is not None:
            d["detail"] = self.detail
        return d


def _fehler(pfad: str, code: str, meldung: str, hinweis: str, anker: str = "", detail: Any = None) -> Meldung:
    return Meldung(pfad, "fehler", code, meldung, hinweis, anker or _anker_je_code(code), detail)


def _warnung(pfad: str, code: str, meldung: str, hinweis: str, anker: str = "", detail: Any = None) -> Meldung:
    return Meldung(pfad, "warnung", code, meldung, hinweis, anker or _anker_je_code(code), detail)


def _anker_je_code(code: str) -> str:
    """Standard-Doku-Anker fuer einen Meldungscode (Referenz 'Meldungs-Codes').

    Jeder Meldungscode hat in der generierten REFERENZ.md einen Abschnitt mit
    ``<a id=\"meldung-<code>\">``; darauf zeigt ``doku_anker`` (Konzept P10: jede
    Ablehnung nennt einen Verweis in die Doku — nie leer). Ein Test prueft, dass
    jeder Code einen existierenden Anker hat.
    """
    return f"meldung-{code}"


# Kanonischer Katalog aller Meldungscodes -> kurze deutsche Beschreibung.
# EINE Quelle (P12): `referenz.py` erzeugt daraus den Abschnitt 'Meldungs-Codes'
# der Referenz; `_anker_je_code` bildet jeden Code auf seinen Anker ab. Neue
# Pruefregeln tragen ihren Code HIER ein (der Doku-Test faellt sonst rot).
MELDUNGS_CODES: dict[str, str] = {
    "kein_objekt": "Die Datei ist kein JSON-Objekt.",
    "schema": "Die Datei verletzt das JSON-Schema (Typ/Enum/Pflicht/Pattern).",
    "doppelte_id": "Eine Kennung ist auf derselben Ebene mehrfach vergeben.",
    "person_ohne_rolle": "Ein Personen-Merkmal hat keine Rolle gesetzt.",
    "attribut_ueberschattet": "Ein Merkmal verdeckt ein eingebautes Attribut.",
    "unbekannte_sammlung": "Ein eintrag verweist auf eine unbekannte Sammlung.",
    "unbekanntes_feld": "Eine Anlass-Wirkung blendet ein unbekanntes Feld aus.",
    "unbekanntes_merkmal": "Eine aus-Referenz verweist auf ein unbekanntes Merkmal.",
    "anzahl_umgekehrt": "Ein anzahl-Bereich hat min > max.",
    "varianten_ohne_gruppe": "'varianten' an einem Nicht-Gruppen-Feld.",
    "teile_ohne_gruppe": "'teile' an einem Nicht-Gruppen-Feld.",
    "inhalt_ohne_gruppe": "'inhalt' an einem Feld, das weder gruppe noch eintrag ist.",
    "unbekannte_fuellstrategie": "Eine nicht deklarierte Fuellstrategie.",
    "rolle_ohne_person": "Eine 'rolle' an einem Nicht-Personen-Feld.",
    "rolle_ohne_filter": "Eine benannte Rolle ohne Filter.",
    "unbekannter_baustein": "Ein nicht deklarierter Regel-Baustein.",
    "unbekannter_parameter": "Ein für den Baustein nicht erlaubter Regelparameter.",
    "regel_parameter": "Ein Regelparameter verletzt das Baustein-Schema.",
    "unbekanntes_regel_feld": "Eine Regel verweist auf ein unbekanntes Feld.",
    "rrule_unvollstaendig": "Eine Wiederholungsregel ohne FREQ=.",
    "rrule_unlesbar": "Eine syntaktisch ungültige RRULE.",
    "rrule_freq_zu_fein": "Eine Wiederholungsregel wiederholt sich öfter als täglich.",
    "rrule_interval_ungueltig": "Ein Wiederholungs-Abstand (INTERVAL) ist keine Zahl >= 1.",
    "rrule_mehrzeilig": "Eine Wiederholungsregel umfasst mehr als eine Zeile bzw. eine RRULE/EXRULE/RDATE-Kennung.",
    "rrule_expansion_zu_fein": "Eine Wiederholungsregel vervielfacht die Termine je Tag (BYHOUR/BYMINUTE/BYSECOND/BYSETPOS).",
    "unbekannter_feiertag": "Ein Feiertag ist nicht im Katalog.",
    "unbekannter_anlass": "Eine Bedingung verweist auf einen unbekannten Anlass.",
    "unbekannte_variante": "Eine Bedingung verweist auf eine unbekannte Variante.",
    "variante_ohne_gruppe": "Eine Varianten-Bedingung ausserhalb einer Varianten-Gruppe.",
    "unbekannter_parameter_bedingung": "Eine Bedingung verweist auf einen unbekannten Parameter.",
    "unbekanntes_feld_bedingung": "Eine Bedingung verweist auf einen unbekannten Feld-Pfad.",
    "format_platzhalter_unvollstaendig": "Ein Format-Platzhalter nennt kein Attribut.",
    "format_unbekanntes_attribut": "Ein Format-Platzhalter zeigt auf ein unbekanntes Attribut.",
    "format_unbekannter_parameter": "Ein Format-Platzhalter zeigt auf einen unbekannten Parameter.",
    "format_unbekannter_termin": "Ein Format-Platzhalter zeigt auf ein unbekanntes Termin-Feld.",
    "format_unbekanntes_feld": "Ein Format-Platzhalter zeigt auf ein unbekanntes Feld.",
    "merkmal_nicht_deklariert": "Ein Rollenfilter verweist auf ein nicht deklariertes Merkmal.",
    "terminreihen_und_kurzform": "'terminreihen' und die Kurzform 'termine'/'felder' stehen zugleich.",
    "unbekannte_reihe": "Eine abgeleitete Reihe verweist auf eine unbekannte Reihe.",
    "ableitung_zyklus": "Eine Reihe leitet sich von sich selbst ab.",
    "versatz_unlesbar": "Der Versatz eines abgeleiteten Termins ist keine gültige Dauer.",
    "team_ohne_teams": "Ein 'team'-Feld hat keine 'teams'-Angabe.",
    "unbekanntes_bezugsfeld": "Eine vorbelegen-Referenz 'bezug.<feld>' zeigt auf kein bekanntes Feld.",
    "wochentag_langname": "Ein Wochentag ist als langer Name statt als Kurzform geschrieben.",
    "ablauf_ohne_elemente": "Ein 'ablauf'-Feld hat keine 'elemente'-Deklaration.",
    "elemente_ohne_ablauf": "'elemente' steht an einem Feld, das kein 'ablauf' ist.",
    "doppelter_elementtyp": "Ein Elementtyp ist innerhalb desselben Ablaufs mehrfach deklariert.",
    "unbekannter_elementtyp": "Ein Verweis (Regel/Format) nennt einen nicht deklarierten Elementtyp.",
    "fremder_plantyp": "Ein planübergreifender Verweis nennt den eigenen Plantyp.",
    "fremder_plantyp_ungeprueft": "Ein planübergreifender Verweis auf einen fremden Plantyp ist zur Prüfzeit nicht auflösbar.",
    "inkl_untergruppen_ohne_gruppen": "Ein 'inkl_untergruppen' ohne gebundene 'gruppen' hat keine Wirkung.",
    "gruppe_doppelt": "Dieselbe Gruppe ist mehrfach an die Vorlage gebunden.",
    "quelle_ohne_auswahl": "Eine 'quelle' steht an einem Merkmal, das keine 'auswahl' ist.",
}


# --------------------------------------------------------------------------- #
# Laden des Schemas
# --------------------------------------------------------------------------- #


def schema_laden() -> dict[str, Any]:
    """Liest das Plantyp-Schema aus dem Paket (einmalig, dann gecacht).

    Zugriff ueber :mod:`importlib.resources` (``.ressourcen``), damit das Schema
    auch im Image bzw. bei Nicht-Editable-Install vorhanden ist — nie ueber
    ``Path(__file__)``.
    """
    return ressourcen.schema_daten()


_SCHEMA: dict[str, Any] | None = None


def _schema() -> dict[str, Any]:
    global _SCHEMA
    if _SCHEMA is None:
        _SCHEMA = schema_laden()
    return _SCHEMA


# RRULE zulaessige FREQ-Werte. Die Engine erzeugt Termine auf Tagesbasis —
# stuendliche, minuetliche oder sekundenweise Wiederholungen sind ohne Nutzen
# und rufen bei grossen Zeitraeumen eine praktisch unbegrenzte Anzahl Termine
# ab (BLD-R2: FREQ=SECONDLY blockierte die ganze App). Deshalb hier nur die
# vier groben Frequenzen.
_FREQ = {"YEARLY", "MONTHLY", "WEEKLY", "DAILY"}

_RRULE_RE = re.compile(r"(?<![A-Z])FREQ\s*=")

# Versatz-Syntax eines abgeleiteten Termins: [+-]Zahl + Einheit (T/W/h/min).
_VERSATZ_RE = re.compile(r"^[+-][0-9]+(T|W|h|min)$")

# Wochentage: Lange Namen -> Kurzform (fuer die gutmuetige Normalisierung, P10).
# Die Kurzform ist zweibuchstabig und kleingeschrieben; Gross-/Kleinschreibung
# und lange Namen werden im Eingang toleriert und auf die Kurzform gebracht.
_WOCHENTAG_KURZFORM: dict[str, str] = {
    "mo": "mo", "di": "di", "mi": "mi", "do": "do", "fr": "fr", "sa": "sa", "so": "so",
    "montag": "mo", "dienstag": "di", "mittwoch": "mi", "donnerstag": "do",
    "freitag": "fr", "samstag": "sa", "sonntag": "so",
}

_WOCHENTAG_KEYS = ("wochentag", "wochentage")


def _normalisiere_wochentage(daten: Any) -> list[Meldung]:
    """Normalisiert Wochentags-Angaben gutmuetig (Review PR1, Befund B).

    RRULE- und Agent-typische Schreibweisen wie 'SA'/'Sa' (grosse Buchstaben)
    und lange Namen ('samstag') werden toleriert: Gross-/Kleinschreibung wird
    ohne Meldung auf die Kurzform gebracht, ein langer Name wird auf die
    Kurzform abgebildet und erzeugt eine WARNUNG (Hinweis auf die Kurzform).

    Wirkt rekursiv auf die Schluessel 'wochentag'/'wochentage' (Feldwert ist
    ein String ODER eine Liste von Strings, z. B. in `termine.wochentage` und
    `bedingung.wochentag`).
    """
    meldungen: list[Meldung] = []

    def normalisiere_wert(wert: Any, pfad: str) -> Any:
        if isinstance(wert, str):
            niedrig = wert.lower()
            kurzform = _WOCHENTAG_KURZFORM.get(niedrig)
            if kurzform is None:
                return wert  # unbekannt -> unveraendert, Schema meldet es
            if niedrig != kurzform:
                # langer Name ('montag') -> auf Kurzform, mit Warnung.
                meldungen.append(_warnung(
                    pfad, "wochentag_langname",
                    f"Wochentag {wert!r} ist ein langer Name; verwendet wird die Kurzform {kurzform!r}.",
                    f"Nutze die zweibuchstabige Kurzform ('mo','di','mi','do','fr','sa','so'), z. B. {kurzform!r}.",
                ))
                return kurzform
            # Kurzform, aber evtl. in anderer Gross-/Kleinschreibung ('SA'/'Sa').
            return kurzform  # 'sa' (normalisiert, ohne Meldung)
        return wert

    def gehe(knoten: Any, pfad: str) -> Any:
        if isinstance(knoten, dict):
            for schluessel, wert in knoten.items():
                if schluessel in _WOCHENTAG_KEYS:
                    subpfad = f"{pfad}/{schluessel}"
                    if isinstance(wert, list):
                        knoten[schluessel] = [
                            normalisiere_wert(w, f"{subpfad}/{k}") for k, w in enumerate(wert)
                        ]
                    else:
                        knoten[schluessel] = normalisiere_wert(wert, subpfad)
                else:
                    gehe(wert, f"{pfad}/{schluessel}")
        elif isinstance(knoten, list):
            for k, item in enumerate(knoten):
                gehe(item, f"{pfad}/{k}")
        return knoten

    if isinstance(daten, dict):
        gehe(daten, "")
    return meldungen


# --------------------------------------------------------------------------- #
# Parameter-Referenzen-Finder
# --------------------------------------------------------------------------- #

_PARAM_REF_RE = re.compile(r"\{parameter\.([a-z0-9_\-]+)\}")


def _param_referenzen(text: str) -> list[str]:
    """Alle Parameter-Kennungen, die in einem Text referenziert werden."""
    return _PARAM_REF_RE.findall(text or "")


# --------------------------------------------------------------------------- #
# Hilfsfunktionen zum Durchwandern der Feldstruktur
# --------------------------------------------------------------------------- #


def _felder_ebene(felder: list[Any]) -> Iterable[tuple[int, dict[str, Any]]]:
    """Indizes + Feld-Dicts einer Feldebene."""
    for i, f in enumerate(felder or []):
        if isinstance(f, dict):
            yield i, f


def _alle_felder_rekursiv(felder: list[Any], basis: str = "felder") -> Iterable[tuple[str, dict[str, Any]]]:
    """Durchwandert den Feldbaum Tiefe-fuer-Tiefe; liefert (Pointer-Basis, Feld)."""
    for i, f in _felder_ebene(felder):
        pfad = f"{basis}/{i}"
        yield pfad, f
        # 'gruppe' und 'eintrag' koennen Unterfelder tragen (Konzept B3: ein
        # eintrag kann eigene Unterfelder haben, z. B. Lied -> Dirigent/Klavier).
        if f.get("art") in ("gruppe", "eintrag") and isinstance(f.get("inhalt"), list):
            yield from _alle_felder_rekursiv(f["inhalt"], f"{pfad}/inhalt")
        # 'ablauf' traegt seine (heterogenen) Felder in `elemente[].inhalt`.
        if f.get("art") == "ablauf" and isinstance(f.get("elemente"), list):
            for e, elem in _felder_ebene(f["elemente"]):
                if isinstance(elem.get("inhalt"), list):
                    yield from _alle_felder_rekursiv(elem["inhalt"], f"{pfad}/elemente/{e}/inhalt")


# --------------------------------------------------------------------------- #
# Einstieg
# --------------------------------------------------------------------------- #


def pruefe_plantyp(daten: Any) -> list[Meldung]:
    """Prueft eine Plantyp-Datei und liefert alle Meldungen (Fehler + Warnungen).

    Reihenfolge: erst Schema (alle Fehler sammeln), dann Semantik. Ist die Datei
    kein Objekt, kommen nur die nicht-abfangbaren Meldungen zurueck (pfad "").
    """
    meldungen: list[Meldung] = []

    if not isinstance(daten, dict):
        meldungen.append(
            _fehler("", "kein_objekt",
                    "Die Plantyp-Datei ist kein JSON-Objekt.",
                    "Lege die Datei als JSON-Objekt an: { \"schema\": \"diakronos/plantyp@1\", \"id\": \"...\" }.")
        )
        return meldungen

    # Gutmuetige Normalisierung VOR der Schema-Validierung: Wochentage in
    # beliebiger Gross-/Kleinschreibung ('Sa'/'SA') und als lange Namen
    # ('samstag') auf die Kurzform bringen (Review PR1, Befund B). Der lange
    # Name erzeugt eine Warnung, damit der Eingang sich korrigieren kann.
    meldungen.extend(_normalisiere_wochentage(daten))

    # ---- Stufe 1: Schema-Validierung, alle Fehler sammeln -----------------
    validator = jsonschema.Draft202012Validator(_schema())
    for fehlerobjekt in validator.iter_errors(daten):
        pfad = _json_pointer(fehlerobjekt)
        meldungen.append(
            _fehler(
                pfad,
                "schema",
                _schema_meldung(fehlerobjekt),
                _schema_hinweis(fehlerobjekt, pfad),
            )
        )

    # ---- Stufe 2: Semantik (nur sinnvoll, wenn Grundstruktur steht) -------
    meldungen.extend(_semantische_pruefung(daten))

    # Fehler zuerst, dann Warnungen; stabile Ordnung nach Pfad.
    meldungen.sort(key=lambda m: (0 if m.stufe == "fehler" else 1, m.pfad))
    return meldungen


# --------------------------------------------------------------------------- #
# Stufe 1: Schema-Helfer
# --------------------------------------------------------------------------- #


def _json_pointer(fehlerobjekt: jsonschema.ValidationError) -> str:
    """Baut einen JSON-Pointer aus dem Fehlerpfad (z. B. '/felder/0/sammlung')."""
    teile = [str(p) for p in fehlerobjekt.absolute_path]
    return "/" + "/".join(teile) if teile else "/"


def _schema_meldung(fehlerobjekt: jsonschema.ValidationError) -> str:
    """Verstaendliche, deutsche Meldung fuer einen Schema-Fehler."""
    pfad = _json_pointer(fehlerobjekt)
    valid = fehlerobjekt.validator
    msg = fehlerobjekt.message
    if valid == "required":
        fehlend = ", ".join(repr(k) for k in fehlerobjekt.validator_value)
        return f"Pflichteigenschaft(en) fehlen: {fehlend}."
    if valid == "additionalProperties":
        erlaubt = set(fehlerobjekt.schema.get("properties", {})) if isinstance(fehlerobjekt.schema, dict) else set()
        vorhanden = set(fehlerobjekt.instance.keys()) if isinstance(fehlerobjekt.instance, dict) else set()
        unerlaubt = vorhanden - erlaubt
        extras = ", ".join(repr(k) for k in sorted(unerlaubt))
        return f"Unbekannte Eigenschaft(en) {extras} (hier nicht erlaubt)."
    if valid == "const":
        return f"Wert muss exakt {fehlerobjekt.validator_value!r} sein, ist aber {fehlerobjekt.instance!r}."
    if valid == "enum":
        options = ", ".join(repr(o) for o in fehlerobjekt.validator_value)
        return f"Wert {fehlerobjekt.instance!r} ist nicht erlaubt; erlaubt sind: {options}."
    if valid == "type":
        return f"Falscher Typ: {msg}."
    if valid == "pattern":
        return f"Wert {fehlerobjekt.instance!r} passt nicht zum erlaubten Muster."
    if valid == "oneOf":
        return "Wert passt in keine der erlaubten Formen (oder in mehrere zugleich)."
    return f"{msg} (Pfad {pfad})."


def _schema_hinweis(fehlerobjekt: jsonschema.ValidationError, pfad: str) -> str:
    """Konkreter Korrekturhinweis mit Mini-Beispiel."""
    valid = fehlerobjekt.validator
    if valid == "required":
        fehlend = ", ".join(repr(k) for k in fehlerobjekt.validator_value)
        return f"Ergaenze die fehlende Eigenschaft, z. B. {fehlend.split(',')[0]} bei {pfad}."
    if valid == "additionalProperties":
        return "Entferne die unbekannte(n) Eigenschaft(en) oder prüfe die Schreibweise (Tippfehler?)."
    if valid == "const":
        return f"Setze den Wert auf {fehlerobjekt.validator_value!r}."
    if valid == "enum":
        options = ", ".join(repr(o) for o in fehlerobjekt.validator_value)
        return f"Setze einen der erlaubten Werte: {options}."
    if valid == "type":
        return f"Setze den Wert in den erwarteten Typ ({fehlerobjekt.validator_value!r})."
    if valid == "pattern":
        return "Passe den Wert an das erlaubte Muster an (Kleinbuchstaben, Ziffern, _ und -)."
    if valid == "format":
        return "Nutze das erwartete Format (z. B. Datum als JJJJ-MM-TT)."
    return "Siehe REFERENZ.md, Abschnitt 'Schema'."


# --------------------------------------------------------------------------- #
# Stufe 2: Semantische Pruefung
# --------------------------------------------------------------------------- #


def _semantische_pruefung(d: dict[str, Any]) -> list[Meldung]:
    m: list[Meldung] = []
    _pruefe_parameter(m, d)
    _pruefe_gruppen(m, d)
    _pruefe_merkmale(m, d)
    _pruefe_sammlungen(m, d)
    _pruefe_anlaesse(m, d)
    _pruefe_felder(m, d)
    _pruefe_rollen(m, d)
    _pruefe_regeln(m, d)
    _pruefe_termine(m, d)
    _pruefe_ansichten(m, d)
    _pruefe_terminreihen(m, d)
    return m


def _pruefe_parameter(m: list[Meldung], d: dict[str, Any]) -> None:
    params = d.get("parameter") or []
    kennungen: set[str] = set()
    for i, p in _felder_ebene(params):
        pid = p.get("id")
        if not isinstance(pid, str):
            continue
        if pid in kennungen:
            m.append(_fehler(f"/parameter/{i}/id", "doppelte_id",
                             f"Die Parameter-Kennung {pid!r} ist mehrfach vergeben.",
                             f"Vergebe eindeutige Kennungen, z. B. {pid!r} nur einmal."))
        kennungen.add(pid)


def _pruefe_gruppen(m: list[Meldung], d: dict[str, Any]) -> None:
    """Gebundene Gruppen der Vorlage (PERSONENPOOL) pruefen.

    ``gruppen`` ist eine Liste von Gruppen-Kennungen; eine doppelte Kennung ist
    ein Fehler. ``inkl_untergruppen`` ist nur zusammen mit ``gruppen`` sinnvoll
    (sonst Warnung — die Angabe haette keine Wirkung).
    """
    gruppen = d.get("gruppen")
    if gruppen is not None and isinstance(gruppen, list):
        gesehen: set[str] = set()
        for i, g in enumerate(gruppen):
            if not isinstance(g, str):
                continue  # Schema meldet den Typfehler
            if g in gesehen:
                m.append(_fehler(f"/gruppen/{i}", "gruppe_doppelt",
                                 f"Die Gruppe {g!r} ist mehrfach gebunden.",
                                 "Nenne jede Gruppe nur einmal."))
            gesehen.add(g)
    if d.get("inkl_untergruppen") is True and not gruppen:
        m.append(_warnung("/inkl_untergruppen", "inkl_untergruppen_ohne_gruppen",
                          "'inkl_untergruppen' ist gesetzt, aber keine 'gruppen'.",
                          "Ergaenze 'gruppen' oder entferne 'inkl_untergruppen'."))


def _pruefe_merkmale(m: list[Meldung], d: dict[str, Any]) -> None:
    merkmale = d.get("merkmale") or {}
    if not isinstance(merkmale, dict):
        return
    for schluessel, gruppe in merkmale.items():
        if not isinstance(gruppe, list):
            continue
        kennungen: set[str] = set()
        for i, mk in _felder_ebene(gruppe):
            mid = mk.get("id")
            if not isinstance(mid, str):
                continue
            if mid in kennungen:
                m.append(_fehler(f"/merkmale/{schluessel}/{i}/id", "doppelte_id",
                                 f"Die Merkmal-Kennung {mid!r} ist in {schluessel!r} mehrfach vergeben.",
                                 f"Vergebe eindeutige Kennungen innerhalb jeder Merkmal-Gruppe."))
            kennungen.add(mid)
            # eingebaute Attribute duerfen nicht ueberschattet werden (Person:
            # name/vorname/nachname/kuerzel/email; Sammlung: titel/reihenfolge; ...
            # immer vorhanden). Ein Merkmal gleichen Namens wuerde sie verdecken.
            eingebaut = eingebaute_attribut_schluessel(schluessel)
            if mid in eingebaut:
                m.append(_fehler(f"/merkmale/{schluessel}/{i}/id", "attribut_ueberschattet",
                                 f"Merkmal {mid!r} überschattet das eingebaute Attribut {mid!r} ({schluessel}).",
                                 f"Eingebaute Attribute ({', '.join(sorted(eingebaut))}) sind immer vorhanden und brauchen keine Deklaration — benenne das Merkmal um (z. B. {mid}_extra) oder entferne es."))
            # art 'person' braucht eine rolle (bzw. rollen-filter)
            if mk.get("art") == "person" and not mk.get("rolle"):
                m.append(_warnung(f"/merkmale/{schluessel}/{i}", "person_ohne_rolle",
                                  "Merkmal mit art 'person' hat keine Rolle gesetzt.",
                                  "Ergaenze eine 'rolle', damit klar ist, welche Personen als Wert in Frage kommen."))
            # 'quelle' nur bei art 'auswahl' (ST3: Themen = Psalmos-Kategorien).
            if mk.get("quelle") and mk.get("art") != "auswahl":
                m.append(_fehler(f"/merkmale/{schluessel}/{i}/quelle", "quelle_ohne_auswahl",
                                 f"'quelle' ist nur bei art 'auswahl' erlaubt, nicht bei {mk.get('art')!r}.",
                                 "Entferne 'quelle' oder setze art auf 'auswahl'."))


def _pruefe_sammlungen(m: list[Meldung], d: dict[str, Any]) -> None:
    sammlungen = d.get("sammlungen") or []
    if not isinstance(sammlungen, list):
        return
    kennungen: set[str] = set()
    for i, s in _felder_ebene(sammlungen):
        sid = s.get("id")
        if not isinstance(sid, str):
            continue
        if sid in kennungen:
            m.append(_fehler(f"/sammlungen/{i}/id", "doppelte_id",
                             f"Die Sammlung-Kennung {sid!r} ist mehrfach vergeben.",
                             f"Vergebe eindeutige Sammlung-Kennungen."))
        kennungen.add(sid)


def _bekannte_sammlungen(d: dict[str, Any]) -> set[str]:
    """Kennungen eigener Sammlungen + eingebaute 'lieder'."""
    result = {"lieder"}
    for _, s in _felder_ebene(d.get("sammlungen") or []):
        if isinstance(s.get("id"), str):
            result.add(s["id"])
    return result


def _bekannte_merkmale(d: dict[str, Any]) -> dict[str, set[str]]:
    """Kennungen der Merkmale, je Gruppe (person/lieder/eigene Sammlung)."""
    merkmale = d.get("merkmale") or {}
    result: dict[str, set[str]] = {}
    if isinstance(merkmale, dict):
        for schluessel, gruppe in merkmale.items():
            if isinstance(gruppe, list):
                result[schluessel] = {
                    mk["id"] for _, mk in _felder_ebene(gruppe) if isinstance(mk.get("id"), str)
                }
    return result


def _bekannte_feldkennungen_oberebene(d: dict[str, Any]) -> set[str]:
    return {
        f["id"] for _, f in _felder_ebene(d.get("felder") or []) if isinstance(f.get("id"), str)
    }


def _alle_feldlisten(d: dict[str, Any]) -> list[list[Any]]:
    """Alle Feldlisten: die oberste `felder`-Liste UND die `felder` aller Terminreihen.

    Die Kurzform (`felder`) und `terminreihen[].felder` koennen nicht gleichzeitig
    stehen (die Pruefung erlaubt nur eine Form), aber diese Sammel-Funktion deckt
    beide ab, damit Verweis-Pruefungen (regel-feld, format, feld_gesetzt) ueber
    alle Felder sehen.
    """
    listen: list[list[Any]] = []
    felder = d.get("felder")
    if isinstance(felder, list):
        listen.append(felder)
    reihen = d.get("terminreihen")
    if isinstance(reihen, list):
        for _, r in _felder_ebene(reihen):
            if isinstance(r.get("felder"), list):
                listen.append(r["felder"])
    return listen


def _anlass_kennungen(d: dict[str, Any]) -> set[str]:
    """Alle gueltigen Anlass-Kennungen: deklarierte Anlaesse + Feiertage.

    Feiertage in `termine.feiertage` (und der Katalog) setzen automatisch einen
    Anlass ihres Namens — deshalb zaehlen sie hier als gueltige Verweise.
    """
    result: set[str] = {
        a["id"] for _, a in _felder_ebene(d.get("anlaesse") or [])
        if isinstance(a.get("id"), str)
    }
    from .feiertage import feiertage_katalog

    result |= feiertage_katalog()
    # Sammelanlass 'feiertag': jeder Feiertagstermin bekommt ihn zusaetzlich.
    result.add("feiertag")
    return result


def _alle_feldpfade(d: dict[str, Any]) -> set[str]:
    """Alle gueltigen Feld-Pfade (punktgetrennt) — fuer feld_gesetzt/format.

    Erzeugt fuer jeden Feld die Pfade relativ zur Oberebene: `frohe_stunde`,
    `abend.leitung`; Varianten als `gruppe@variante`, Teile als `gruppe#teil`.
    Beruecksichtigt Felder der Kurzform UND aller `terminreihen`.
    """
    pfade: set[str] = set()
    for felder in _alle_feldlisten(d):
        pfade |= _sammle_feldpfade(felder, "")
    return pfade


def _sammle_feldpfade(felder: list[Any], praefix: str) -> set[str]:
    pfade: set[str] = set()
    for _, f in _felder_ebene(felder):
        fid = f.get("id")
        if not isinstance(fid, str):
            continue
        p = f"{praefix}.{fid}" if praefix else fid
        pfade.add(p)
        inhalt = f.get("inhalt")
        if isinstance(inhalt, list):
            pfade |= _sammle_feldpfade(inhalt, p)
        for v in _objekt_eintraege(f.get("varianten")):
            wid = v.get("id")
            if isinstance(wid, str):
                pfade |= _sammle_feldpfade(v.get("inhalt") or [], f"{p}@{wid}")
        for t in _objekt_eintraege(f.get("teile")):
            tid = t.get("id")
            if isinstance(tid, str):
                pfade |= _sammle_feldpfade(t.get("inhalt") or [], f"{p}#{tid}")
        # ablauf: pro Elementtyp ein Sammelpfad 'ablauf.<typ>' plus die Felder
        # des Elements als 'ablauf.<typ>.<innerfeld>' (fuer Verweise/Formate).
        if f.get("art") == "ablauf" and isinstance(f.get("elemente"), list):
            for elem in _objekt_eintraege(f.get("elemente")):
                typ = elem.get("typ")
                if not isinstance(typ, str):
                    continue
                typ_pfad = f"{p}.{typ}"
                pfade.add(typ_pfad)
                pfade |= _sammle_feldpfade(elem.get("inhalt") or [], typ_pfad)
    return pfade


def _objekt_eintraege(items: Any) -> Iterable[dict[str, Any]]:
    """Nur die Objekt-Form einer Varianten-/Teile-Liste (ueberspringt Kurzform-Strings)."""
    for it in items or []:
        if isinstance(it, dict):
            yield it


def _pruefe_anlaesse(m: list[Meldung], d: dict[str, Any]) -> None:
    anlaesse = d.get("anlaesse") or []
    if not isinstance(anlaesse, list):
        return
    kennungen: set[str] = set()
    bekannte_felder = _bekannte_feldkennungen_oberebene(d)
    for i, a in _felder_ebene(anlaesse):
        aid = a.get("id")
        if not isinstance(aid, str):
            continue
        if aid in kennungen:
            m.append(_fehler(f"/anlaesse/{i}/id", "doppelte_id",
                             f"Die Anlass-Kennung {aid!r} ist mehrfach vergeben.",
                             f"Vergebe eindeutige Anlass-Kennungen."))
        kennungen.add(aid)
        wirkung = a.get("wirkung")
        if isinstance(wirkung, dict):
            # ohne -> existierende Felder der Oberebene
            for j, feld in enumerate(wirkung.get("ohne") or []):
                if isinstance(feld, str) and feld not in bekannte_felder:
                    m.append(_fehler(f"/anlaesse/{i}/wirkung/ohne/{j}", "unbekanntes_feld",
                                     f"Anlass {aid!r} blendet Feld {feld!r} aus, aber ein solches Feld ist nicht deklariert.",
                                     "Verweise nur auf Felder der obersten Feldebene (oder lege das Feld erst an)."))
            # mit -> eigene Felder (rekursiv pruefen auf strukturelle Konsistenz)
            mit_felder = wirkung.get("mit")
            if isinstance(mit_felder, list):
                _pruefe_feldbaum(m, mit_felder, f"/anlaesse/{i}/wirkung/mit", d, None)
            # wirkung -> optionale strukturierte Bedingung pruefen
            _pruefe_bedingung(m, f"/anlaesse/{i}/wirkung/bedingung", wirkung.get("bedingung"), d, None)


def _pruefe_felder(m: list[Meldung], d: dict[str, Any]) -> None:
    _pruefe_feldbaum(m, d.get("felder") or [], "/felder", d, None)


def _pruefe_feldbaum(
    m: list[Meldung],
    felder: list[Any],
    basis: str,
    d: dict[str, Any],
    sammlung_kontext: str | None,
    varianten_ids: frozenset[str] | None = None,
) -> None:
    """Rekursiv: eindeutige Kennungen je Ebene + feldbezogene Verweise.

    `sammlung_kontext` ist die Sammlung des umgebenden `eintrag`-Felds (fuer die
    Aufloesung von `aus='eintrag.<merkmal>'` in dessen Unterfeldern).

    `varianten_ids` sind die Kennungen der Varianten der umgebenden Gruppe
    (fuer die Pruefung von `bedingung.variante`); ausserhalb einer Gruppe None.
    """
    kennungen: set[str] = set()
    bekannte_sammlungen = _bekannte_sammlungen(d)
    for i, f in _felder_ebene(felder):
        pfad = f"{basis}/{i}"
        fid = f.get("id")
        art = f.get("art")
        if isinstance(fid, str):
            if fid in kennungen:
                m.append(_fehler(f"{pfad}/id", "doppelte_id",
                                 f"Die Feld-Kennung {fid!r} ist auf dieser Ebene mehrfach vergeben.",
                                 f"Kennungen muessen innerhalb einer Ebene eindeutig sein; benenne eins um, z. B. {fid}2."))
            kennungen.add(fid)
        # sammlung existiert?
        eigene_sammlung = f.get("sammlung")
        if art == "eintrag":
            if isinstance(eigene_sammlung, str) and not eigene_sammlung.startswith("{parameter."):
                if eigene_sammlung not in bekannte_sammlungen:
                    tipp = _tipp_vorschlag(eigene_sammlung, bekannte_sammlungen)
                    zusatz = f" Meinten Sie {tipp!r}?" if tipp else ""
                    m.append(_fehler(f"{pfad}/sammlung", "unbekannte_sammlung",
                                     f"Sammlung {eigene_sammlung!r} ist weder eingebaut noch deklariert.{zusatz}",
                                     "Verweise nur auf 'lieder' oder eine selbst deklarierte Sammlung (unter 'sammlungen')."))
        # team-Feld braucht eine teams-Angabe (Gruppen-Quelle) — ausser es ist
        # aus 'bezug.<feld>' vorbelegt (dann stammt das Team vom Ursprungstermin).
        if art == "team" and f.get("teams") is None:
            aus = f.get("aus")
            if not (isinstance(aus, str) and aus.startswith("bezug.")):
                m.append(_fehler(f"{pfad}/teams", "team_ohne_teams",
                                 f"Feld {fid!r} ist ein 'team', hat aber keine 'teams'-Angabe.",
                                 "Lege 'teams' fest: entweder ein Objekt {gruppe_unter: '...'} oder eine Liste von Team-Kennungen."))
        # rollen_filter im mitglieder eines team-Felds pruefen (merkmal-Verweise)
        if art == "team" and isinstance(f.get("mitglieder"), dict):
            _pruefe_rollen_filter_merkmale(m, f"{pfad}/mitglieder", f["mitglieder"], d)
        # ablauf: braucht 'elemente'; 'elemente' nur bei art 'ablauf'; je Element
        # eindeutiger typ + rekursiv gueltiger inhalt + bedingung.
        elemente = f.get("elemente")
        if art == "ablauf":
            if not isinstance(elemente, list) or not elemente:
                m.append(_fehler(f"{pfad}/elemente", "ablauf_ohne_elemente",
                                 f"Feld {fid!r} ist ein 'ablauf', hat aber keine 'elemente'-Deklaration.",
                                 "Deklariere die erlaubten Elementtypen in 'elemente' (z. B. [{\"typ\": \"lied\", \"inhalt\": [...]}, {\"typ\": \"szene\", \"inhalt\": [...]}])."))
            else:
                _pruefe_ablauf_elemente(m, f"{pfad}/elemente", elemente, d)
        elif isinstance(elemente, list):
            m.append(_warnung(f"{pfad}/elemente", "elemente_ohne_ablauf",
                              f"Feld {fid!r} hat 'elemente', ist aber kein 'ablauf'.",
                              "'elemente' wirkt nur bei Feldern der art 'ablauf' — entferne es oder stelle art auf 'ablauf'."))
        # aus-Referenz (vorbelegen)
        aus = f.get("aus")
        if isinstance(aus, str):
            # Das wirksame Sammlungs-Merkmal kommt vom umgebenden eintrag; mit
            # der eigenen Sammlung, falls dieses Feld selbst ein eintrag ist.
            wirksame_sammlung = eigene_sammlung if isinstance(eigene_sammlung, str) else sammlung_kontext
            _pruefe_aus_referenz(m, pfad, aus, wirksame_sammlung, d)
        # anzahl widerspruechlich?
        anzahl = f.get("anzahl")
        if isinstance(anzahl, str) and ".." in anzahl:
            links, rechts = anzahl.split("..", 1)
            if rechts.isdigit() and links.isdigit() and int(links) > int(rechts):
                m.append(_fehler(f"{pfad}/anzahl", "anzahl_umgekehrt",
                                 f"Anzahl-Bereich {anzahl!r} ist widerspruechlich (min > max).",
                                 f"Schreibe min..max mit min <= max, z. B. '0..2'."))
        # varianten/teile nur bei gruppe
        if f.get("varianten") and art != "gruppe":
            m.append(_warnung(f"{pfad}/varianten", "varianten_ohne_gruppe",
                              f"Feld {fid!r} hat 'varianten', ist aber keine 'gruppe'.",
                              "'varianten' wirkt nur bei Feldern der art 'gruppe' — entferne es oder stelle art auf 'gruppe'."))
        if f.get("teile") and art != "gruppe":
            m.append(_warnung(f"{pfad}/teile", "teile_ohne_gruppe",
                              f"Feld {fid!r} hat 'teile', ist aber keine 'gruppe'.",
                              "'teile' wirkt nur bei Feldern der art 'gruppe' — entferne es oder stelle art auf 'gruppe'."))
        # inhalt nur bei gruppe (ggf. auch bei eintrag erlaubt laut Konzept B3)
        if isinstance(f.get("inhalt"), list):
            if art not in ("gruppe", "eintrag"):
                m.append(_warnung(f"{pfad}/inhalt", "inhalt_ohne_gruppe",
                                  f"Feld {fid!r} hat 'inhalt', ist aber weder 'gruppe' noch 'eintrag'.",
                                  "Unterfelder ('inhalt') tragen nur 'gruppe' oder 'eintrag' — entferne es oder ändere die art."))
            else:
                # Unterfelder eines eintrag erben dessen Sammlung als Kontext.
                kind_kontext = eigene_sammlung if art == "eintrag" and isinstance(eigene_sammlung, str) else sammlung_kontext
                # Unterfelder einer gruppe sehen deren Varianten (fuer bedingung.variante).
                kind_varianten = frozenset(_varianten_kennung_je_eintrag(f.get("varianten"))) if art == "gruppe" else None
                _pruefe_feldbaum(m, f["inhalt"], f"{pfad}/inhalt", d, kind_kontext, kind_varianten)
        # variante_teile: Objekt-/Kurzform, eindeutige Kennungen, eigene inhalt +
        # bedingung pruefen.
        _pruefe_varianten(m, pfad, f, d)
        _pruefe_parten_teile(m, pfad, f, d)
        # bedingung (strukturiert) semantisch pruefen
        _pruefe_bedingung(m, f"{pfad}/bedingung", f.get("bedingung"), d, varianten_ids)
        # fuellen-strategie bekannt?
        fuellen = f.get("fuellen")
        if isinstance(fuellen, str) and fuellen not in bekannte_fuellstrategien():
            tipp = _tipp_vorschlag(fuellen, bekannte_fuellstrategien())
            zusatz = f" Meinten Sie {tipp!r}?" if tipp else ""
            m.append(_fehler(f"{pfad}/fuellen", "unbekannte_fuellstrategie",
                             f"Fuellstrategie {fuellen!r} ist unbekannt.{zusatz}",
                             "Erlaubt sind: manuell, reihum, der_reihe_nach, vorbelegen, optimieren."))
        # rolle nur bei person/personen (als Referenz @oder Filter)
        if f.get("rolle") is not None and art not in ("person", "personen"):
            m.append(_warnung(f"{pfad}/rolle", "rolle_ohne_person",
                              f"Feld {fid!r} hat eine 'rolle', ist aber keine Person-Rolle.",
                              "'rolle' wirkt nur bei art 'person'/'personen'."))
        # merkmal-Verweise im inline-Rollenfilter pruefen (Warnung bei fehlender Deklaration)
        rollen_filter = f.get("rolle")
        if isinstance(rollen_filter, dict):
            _pruefe_rollen_filter_merkmale(m, f"{pfad}/rolle", rollen_filter, d)


def _varianten_kennung_je_eintrag(varianten: Any) -> list[str]:
    """Kennungen aller Varianten (Kurzform-Strings und Objekt-'id') in Reihenfolge."""
    result: list[str] = []
    for v in varianten or []:
        if isinstance(v, str):
            result.append(v)
        elif isinstance(v, dict) and isinstance(v.get("id"), str):
            result.append(v["id"])
    return result


def _teil_kennung_je_eintrag(teile: Any) -> list[str]:
    """Kennungen aller Teile (Kurzform-Strings und Objekt-'id') in Reihenfolge."""
    result: list[str] = []
    for t in teile or []:
        if isinstance(t, str):
            result.append(t)
        elif isinstance(t, dict) and isinstance(t.get("id"), str):
            result.append(t["id"])
    return result


def _pruefe_ablauf_elemente(m: list[Meldung], basis: str, elemente: list[Any], d: dict[str, Any]) -> None:
    """Ablauf-Elemente: eindeutige Typen + rekursiv gueltiger inhalt + bedingung.

    Jeder Elementtyp traegt einen `inhalt` (eine Feldliste), der wie ein
    Feldbaum geprueft wird. Der `typ` muss innerhalb desselben Ablaufs eindeutig
    sein (P3: Elementtypen werden ueber stabile Kennungen angesprochen).
    """
    gesehen: set[str] = set()
    for e, elem in _felder_ebene(elemente):
        ebasis = f"{basis}/{e}"
        typ = elem.get("typ")
        if isinstance(typ, str):
            if typ in gesehen:
                m.append(_fehler(f"{ebasis}/typ", "doppelter_elementtyp",
                                 f"Elementtyp {typ!r} ist in diesem Ablauf mehrfach deklariert.",
                                 f"Vergebe eindeutige Elementtyp-Kennungen innerhalb eines Ablaufs."))
            gesehen.add(typ)
        # inhalt des Elements rekursiv pruefen (kontext der eigenen Sammlung,
        # falls das Element selbst ein eintrag ist — hier nicht der Fall, da
        # ein Element nur ein Container ist).
        inhalt = elem.get("inhalt")
        if isinstance(inhalt, list):
            _pruefe_feldbaum(m, inhalt, f"{ebasis}/inhalt", d, None)
        else:
            # Schema erzwingt inhalt (required), diese Zeile deckt nur Nicht-Dicts ab.
            pass
        _pruefe_bedingung(m, f"{ebasis}/bedingung", elem.get("bedingung"), d, None)


def _pruefe_varianten(m: list[Meldung], pfad: str, f: dict[str, Any], d: dict[str, Any]) -> None:
    """Varianten: eindeutige Kennungen + eigene inhalt/bedingung der Objektform."""
    varianten = f.get("varianten")
    if not isinstance(varianten, list):
        return
    gesehen: set[str] = set()
    for j, v in enumerate(varianten):
        basis = f"{pfad}/varianten/{j}"
        if isinstance(v, str):
            vid = v
        elif isinstance(v, dict):
            vid = v.get("id")
            if isinstance(vid, str):
                if vid in gesehen:
                    m.append(_fehler(f"{basis}/id", "doppelte_id",
                                     f"Die Varianten-Kennung {vid!r} ist mehrfach vergeben.",
                                     f"Kennungen der Varianten muessen eindeutig sein."))
                gesehen.add(vid)
            # eigenes inhalt der Variante rekursiv pruefen (ohne eigene Varianten
            # wird es ersetzt; bedingung der Variante pruefen)
            if isinstance(v.get("inhalt"), list):
                _pruefe_feldbaum(m, v["inhalt"], f"{basis}/inhalt", d, None, None)
            _pruefe_bedingung(m, f"{basis}/bedingung", v.get("bedingung"), d, None)
            continue
        else:
            continue
        if vid in gesehen:
            m.append(_fehler(f"{basis}", "doppelte_id",
                             f"Die Varianten-Kennung {vid!r} ist mehrfach vergeben.",
                             f"Kennungen der Varianten muessen eindeutig sein."))
        gesehen.add(vid)


def _pruefe_parten_teile(m: list[Meldung], pfad: str, f: dict[str, Any], d: dict[str, Any]) -> None:
    """Teile: eindeutige Kennungen + eigene inhalt/bedingung der Objektform."""
    teile = f.get("teile")
    if not isinstance(teile, list):
        return
    gesehen: set[str] = set()
    for j, t in enumerate(teile):
        basis = f"{pfad}/teile/{j}"
        if isinstance(t, str):
            tid = t
        elif isinstance(t, dict):
            tid = t.get("id")
            if isinstance(tid, str):
                if tid in gesehen:
                    m.append(_fehler(f"{basis}/id", "doppelte_id",
                                     f"Die Teil-Kennung {tid!r} ist mehrfach vergeben.",
                                     f"Kennungen der Teile muessen eindeutig sein."))
                gesehen.add(tid)
            if isinstance(t.get("inhalt"), list):
                _pruefe_feldbaum(m, t["inhalt"], f"{basis}/inhalt", d, None, None)
            _pruefe_bedingung(m, f"{basis}/bedingung", t.get("bedingung"), d, None)
            continue
        else:
            continue
        if tid in gesehen:
            m.append(_fehler(f"{basis}", "doppelte_id",
                             f"Die Teil-Kennung {tid!r} ist mehrfach vergeben.",
                             f"Kennungen der Teile muessen eindeutig sein."))
        gesehen.add(tid)


def _pruefe_bedingung(
    m: list[Meldung],
    basis: str,
    knoten: Any,
    d: dict[str, Any],
    varianten_ids: frozenset[str] | None,
) -> None:
    """Semantische Pruefung eines strukturierten Bedingungs-Knotens.

    Der Knoten hat genau eine Eigenschaft (Schema: maxProperties 1). Blattknoten
    werden gegen die deklarierten Referenzen geprueft (Anlass, Parameter,
    Variante, Feld-Pfad); die zusammengesetzten `alle`/`eine`/`nicht` werden
    rekursiv abgestiegen.
    """
    if not isinstance(knoten, dict):
        return
    for schluessel, wert in knoten.items():
        if schluessel in ("alle", "eine"):
            for k, kind in enumerate(wert or []):
                _pruefe_bedingung(m, f"{basis}/{schluessel}/{k}", kind, d, varianten_ids)
        elif schluessel == "nicht":
            _pruefe_bedingung(m, f"{basis}/nicht", wert, d, varianten_ids)
        elif schluessel == "anlass":
            if isinstance(wert, str):
                bekannte = _anlass_kennungen(d)
                if wert not in bekannte:
                    tipp = _tipp_vorschlag(wert, bekannte)
                    zusatz = f" Meinten Sie {tipp!r}?" if tipp else ""
                    m.append(_fehler(f"{basis}/anlass", "unbekannter_anlass",
                                     f"Bedingung verweist auf Anlass {wert!r}, der nicht deklariert ist.{zusatz}",
                                     "Deklariere den Anlass unter 'anlaesse' (Feiertage setzen automatisch einen Anlass ihres Namens)."))
        elif schluessel == "variante":
            if isinstance(wert, str):
                if varianten_ids is None:
                    m.append(_warnung(f"{basis}/variante", "variante_ohne_gruppe",
                                      f"Bedingung prüft Variante {wert!r}, steht aber außerhalb einer Varianten-Gruppe.",
                                      "'variante' ist nur innerhalb eines 'gruppe'-Felds mit Varianten sinnvoll."))
                elif wert not in varianten_ids:
                    tipp = _tipp_vorschlag(wert, varianten_ids)
                    zusatz = f" Meinten Sie {tipp!r}?" if tipp else ""
                    m.append(_fehler(f"{basis}/variante", "unbekannte_variante",
                                     f"Bedingung verweist auf Variante {wert!r}, die diese Gruppe nicht deklariert.{zusatz}",
                                     f"Deklarierte Varianten: {', '.join(sorted(varianten_ids)) or '(keine)'}."))
        elif schluessel == "parameter":
            if isinstance(wert, dict) and isinstance(wert.get("id"), str):
                pid = wert["id"]
                parameter_kennungen = _parameter_kennungen(d)
                if pid not in parameter_kennungen:
                    tipp = _tipp_vorschlag(pid, parameter_kennungen)
                    zusatz = f" Meinten Sie {tipp!r}?" if tipp else ""
                    m.append(_fehler(f"{basis}/parameter/id", "unbekannter_parameter_bedingung",
                                     f"Bedingung verweist auf Parameter {pid!r}, der nicht deklariert ist.{zusatz}",
                                     "Deklariere den Parameter unter 'parameter'."))
        elif schluessel == "feld_gesetzt":
            if isinstance(wert, str):
                pfade = _alle_feldpfade(d)
                if wert not in pfade:
                    tipp = _tipp_vorschlag(wert, pfade)
                    zusatz = f" Meinten Sie {tipp!r}?" if tipp else ""
                    m.append(_fehler(f"{basis}/feld_gesetzt", "unbekanntes_feld_bedingung",
                                     f"Bedingung verweist auf Feld-Pfad {wert!r}, der nicht existiert.{zusatz}",
                                     f"Gültige Feld-Pfade: {', '.join(sorted(pfade)) or '(keine)'}."))
        # wochentag/datum_ab/datum_bis/termin_nr: Schema deckt Format ab, keine
        # weiteren Referenzen.



def _pruefe_aus_referenz(
    m: list[Meldung],
    pfad: str,
    aus: str,
    sammlung: str | None,
    d: dict[str, Any],
) -> None:
    """Prueft die 'aus'-Referenz eines vorbelegen-Felds.

    Erlaubte Formen: 'eintrag.<merkmal>' (Merkmal der Sammlung, aus der dieses
    Person-Feld schoepft), ein anderer feld_pfad oder eine Parameterreferenz.
    `sammlung` ist die Sammlung des umgebenden eintrag (oder None).
    """
    # bezug.<feld> -> Feld des Ursprungstermins (abgeleitete Reihe).
    if aus.startswith("bezug."):
        ziel = aus[len("bezug."):]
        bekannte_felder = _alle_feldkennungen(d)
        if ziel and ziel not in bekannte_felder:
            tipp = _tipp_vorschlag(ziel, bekannte_felder)
            zusatz = f" Meinten Sie {tipp!r}?" if tipp else ""
            m.append(_warnung(f"{pfad}/aus", "unbekanntes_bezugsfeld",
                              f"Vorbelegen-Referenz 'bezug.{ziel}' zeigt auf kein bekanntes Feld.{zusatz}",
                              "bezug.<feld> liest ein Feld des Ursprungstermins der abgeleiteten Reihe."))
        return

    # eintrag.<merkmal> -> Merkmal der Sammlung deklariert ODER eingebautes Attribut?
    if aus.startswith("eintrag."):
        merkmal = aus[len("eintrag."):]
        merkmale = _bekannte_merkmale(d)
        if isinstance(sammlung, str) and sammlung in merkmale:
            if merkmal not in merkmale[sammlung]:
                # eingebautes Attribut der Sammlung? (z. B. 'eintrag.titel')
                if merkmal in eingebaute_attribut_schluessel(sammlung):
                    return
                tipp = _tipp_vorschlag(merkmal, merkmale[sammlung] | eingebaute_attribut_schluessel(sammlung))
                zusatz = f" Meinten Sie {tipp!r}?" if tipp else ""
                m.append(_fehler(f"{pfad}/aus", "unbekanntes_merkmal",
                                 f"Merkmal {merkmal!r} der Sammlung {sammlung!r} ist nicht deklariert.{zusatz}",
                                 f"Lege das Merkmal unter 'merkmale.{sammlung}' an oder korrigiere die Kennung."))
        elif isinstance(sammlung, str) and not sammlung.startswith("{parameter."):
            if merkmal in eingebaute_attribut_schluessel(sammlung):
                return
            # Sammlung ist deklariert, aber es gibt keine Merkmal-Gruppe dazu.
            m.append(_fehler(f"{pfad}/aus", "unbekanntes_merkmal",
                             f"Merkmal {merkmal!r}: Für die Sammlung {sammlung!r} sind keine Merkmale deklariert.",
                             f"Lege die Merkmal-Gruppe 'merkmale.{sammlung}' mit dem Merkmal {merkmal!r} an."))
        return


def _pruefe_rollen(m: list[Meldung], d: dict[str, Any]) -> None:
    rollen = d.get("rollen") or []
    if not isinstance(rollen, list):
        return
    kennungen: set[str] = set()
    for i, r in _felder_ebene(rollen):
        rid = r.get("id")
        if not isinstance(rid, str):
            continue
        if rid in kennungen:
            m.append(_fehler(f"/rollen/{i}/id", "doppelte_id",
                             f"Die Rollen-Kennung {rid!r} ist mehrfach vergeben.",
                             f"Vergebe eindeutige Rollen-Kennungen."))
        kennungen.add(rid)
        # filter vorhanden?
        if not r.get("filter"):
            m.append(_warnung(f"/rollen/{i}", "rolle_ohne_filter",
                              f"Rolle {rid!r} hat keinen Filter.",
                              "Ergaenze einen 'filter' (merkmal/gruppe/anmeldung/person/alle/eine/nicht)."))
        else:
            _pruefe_rollen_filter_merkmale(m, f"/rollen/{i}/filter", r["filter"], d)


def _pruefe_regeln(m: list[Meldung], d: dict[str, Any]) -> None:
    regeln = d.get("regeln") or []
    if not isinstance(regeln, list):
        return
    bekannte = set(REGEL_BAUSTEINE_NA)
    parameter_kennungen = _parameter_kennungen(d)
    for i, r in _felder_ebene(regeln):
        pfad = f"/regeln/{i}"
        baustein = r.get("baustein")
        if not isinstance(baustein, str):
            continue
        if baustein not in bekannte:
            tipp = _tipp_vorschlag(baustein, bekannte)
            zusatz = f" Meinten Sie {tipp!r}?" if tipp else ""
            liste = ", ".join(sorted(bekannte))
            m.append(_fehler(f"{pfad}/baustein", "unbekannter_baustein",
                             f"Regel-Baustein {baustein!r} ist unbekannt.{zusatz}",
                             f"Bekannte Bausteine: {liste}. Neuer Baustein braucht eine Eintragung in der Registry (P11)."))
            continue
        # Parameter gegen das Baustein-Schema pruefen
        deklar = REGEL_BAUSTEINE_NA[baustein]
        param_schema = deklar.parameter_schema
        # nur die Parameter-Schluessel pruefen (ohne baustein/stufe/gewicht)
        param_obj = {k: v for k, v in r.items() if k not in ("baustein", "stufe", "gewicht")}
        # unbekannte Schluessel (Tippfehler) melden
        erlaubt = deklar.parameternamen()
        for k in param_obj:
            if k not in erlaubt:
                tipp = _tipp_vorschlag(k, erlaubt)
                zusatz = f" Meinten Sie {tipp!r}?" if tipp else ""
                m.append(_fehler(f"{pfad}/{k}", "unbekannter_parameter",
                                 f"Parameter {k!r} ist für Baustein {baustein!r} nicht erlaubt.{zusatz}",
                                 f"Erlaubte Parameter für {baustein!r}: {', '.join(sorted(erlaubt)) or '(keine)'}."))
        # JSON-Schema-Validierung der Parameter (Rollen-Referenz umbiegen)
        try:
            validator = jsonschema.Draft202012Validator(param_schema)
            for fehlerobjekt in validator.iter_errors(param_obj):
                pp = _json_pointer(fehlerobjekt)
                m.append(_fehler(
                    f"{pfad}{('' if pp == '/' else pp)}", "regel_parameter",
                    f"Parameter für {baustein!r} ungültig: {fehlerobjekt.message}.",
                    "Siehe REFERENZ.md, Abschnitt zu diesem Baustein.",
                ))
        except jsonschema.SchemaError:
            # Registry-Schema selbst fehlerhaft — das ist ein Programmierfehler,
            # keine Plantyp-Prüfung; hier bewusst ignorieren (Test deckt es ab).
            pass
        # regel-feld verweist auf existierendes Feld?
        for key, val in r.items():
            if key in erlaubt and key in ("feld", "uebungsfeld"):
                _pruefe_regel_feldreferenz(m, pfad, key, val, d, parameter_kennungen)
        # planuebergreifender Verweis 'uebung' ({plantyp, feld}): Existenz des
        # fremden Plantyps ist zur Pruefzeit unbekannt -> Warnung statt Fehler.
        uebung = r.get("uebung")
        if isinstance(uebung, dict) and isinstance(uebung.get("plantyp"), str):
            fremd_plantyp = uebung["plantyp"]
            if fremd_plantyp == d.get("id"):
                m.append(_fehler(f"{pfad}/uebung/plantyp", "fremder_plantyp",
                                 f"Der planübergreifende Verweis nennt den eigenen Plantyp {fremd_plantyp!r}.",
                                 "Ein 'uebung'-Verweis zeigt auf einen ANDEREN Plantyp; für Übung im selben Plantyp nutze 'uebungsfeld'."))
            else:
                m.append(_warnung(f"{pfad}/uebung/plantyp", "fremder_plantyp_ungeprueft",
                                  f"Planübergreifender Verweis auf Plantyp {fremd_plantyp!r} kann zur Prüfzeit nicht aufgelöst werden.",
                                  "Die Engine/API loest den Verweis zur Laufzeit auf; prüfe dort, ob der Plantyp und sein Feld existieren."))
        # merkmal-Verweise im rolle-Parameter pruefen (Warnung bei fehlender Deklaration)
        rolle_param = r.get("rolle")
        if isinstance(rolle_param, dict):
            _pruefe_rollen_filter_merkmale(m, f"{pfad}/rolle", rolle_param, d)


def _pruefe_regel_feldreferenz(m: list[Meldung], pfad: str, key: str, val: Any, d: dict[str, Any], parameter_kennungen: set[str]) -> None:
    """Prueft, dass eine Feld-Referenz in einer Regel auf ein existierendes Feld zeigt.

    Akzeptiert neben schlichten Feld-Kennungen auch Feld-Pfade ('abend.leitung')
    und ablauf-Elementpfade ('ablauf.lied' = alle Elemente des Typs 'lied').
    """
    if not isinstance(val, str):
        return
    if val in parameter_kennungen or val.startswith("{parameter."):
        return
    bekannte = _alle_feldkennungen(d) | _alle_feldpfade(d)
    if val not in bekannte:
        tipp = _tipp_vorschlag(val, bekannte)
        zusatz = f" Meinten Sie {tipp!r}?" if tipp else ""
        m.append(_fehler(f"{pfad}/{key}", "unbekanntes_regel_feld",
                         f"Regel verweist auf Feld {val!r}, das nicht deklariert ist.{zusatz}",
                         f"Deklarierte Felder: {', '.join(sorted(bekannte)) or '(keine)'}."))


def _alle_feldkennungen(d: dict[str, Any]) -> set[str]:
    """Alle Feld-Kennungen ueber den gesamten Baum (fuer Verweis-Pruefung).

    Deckt die oberste `felder`-Liste UND die `felder` aller `terminreihen` ab.
    """
    result: set[str] = set()
    for felder in _alle_feldlisten(d):
        for _, f in _alle_felder_rekursiv(felder):
            if isinstance(f.get("id"), str):
                result.add(f["id"])
    return result


def _parameter_kennungen(d: dict[str, Any]) -> set[str]:
    return {
        p["id"] for _, p in _felder_ebene(d.get("parameter") or []) if isinstance(p.get("id"), str)
    }


def _pruefe_termine(m: list[Meldung], d: dict[str, Any]) -> None:
    termine = d.get("termine")
    if not isinstance(termine, dict):
        return
    regel = termine.get("regel")
    if isinstance(regel, str):
        # Parameterreferenz in RRULE? dann nicht syntaktisch pruefen.
        if "{parameter." not in regel:
            _pruefe_rrule(m, regel)
    # manuell -> daten pruefen (schema deckt format; hier nichts extra)
    # feiertage -> nur gutartig (bekannte Schluessel, um Tippfehler zu melden)
    feiertage = termine.get("feiertage")
    if isinstance(feiertage, list):
        from .feiertage import feiertage_katalog

        katalog = feiertage_katalog()
        for j, f in enumerate(feiertage):
            if isinstance(f, str) and f not in katalog:
                tipp = _tipp_vorschlag(f, katalog)
                zusatz = f" Meinten Sie {tipp!r}?" if tipp else ""
                m.append(_warnung(f"/termine/feiertage/{j}", "unbekannter_feiertag",
                                  f"Feiertag {f!r} ist nicht im Katalog.{zusatz}",
                                  "Siehe REFERENZ.md, Abschnitt 'Feiertage'."))


def _pruefe_rrule(m: list[Meldung], regel: str, pfad: str = "/termine/regel") -> None:
    """Syntax UND Semantik einer Wiederholungsregel pruefen.

    Die konkrete Fachpruefung liegt in ``_rrule_problem`` — dieselbe Funktion
    nutzt die Engine als harte Grenze (Befund B1). Hier nur noch Fehler
    melden, Syntaxpruefung ergaenzen und nichts doppelt formulieren.
    """
    problem = rrule_problem(regel)
    if problem is not None:
        code, meldung, hinweis = problem
        m.append(_fehler(pfad, code, meldung, hinweis))
        return

    try:
        rrulestr(regel, forceset=True)
    except Exception as e:  # noqa: BLE001 — syntaktischer Fehler, egal welcher
        m.append(_fehler(pfad, "rrule_unlesbar",
                         f"Die Wiederholungsregel {regel!r} ist syntaktisch ungültig: {e}",
                         "Siehe iCalendar-RRULE-Syntax, z. B. 'FREQ=WEEKLY;BYDAY=SU'."))


# --------------------------------------------------------------------------- #
# Tippfehler-Vorschlag
# --------------------------------------------------------------------------- #


def _pruefe_terminreihen(m: list[Meldung], d: dict[str, Any]) -> None:
    """Terminreihen: Exklusivitaet zur Kurzform, eindeutige Reihen, abgeleitet-Zyklen."""
    reihen = d.get("terminreihen")
    if not isinstance(reihen, list) or not reihen:
        return

    # Exklusivitaet: terminreihen darf nicht zusammen mit termine/felder stehen.
    if d.get("termine") is not None or d.get("felder"):
        m.append(_fehler("/terminreihen", "terminreihen_und_kurzform",
                         "'terminreihen' und die Kurzform 'termine'/'felder' schliessen sich aus.",
                         "Nutze ENTWEDER die obersten 'termine' + 'felder' (Kurzform fuer eine Reihe 'standard') ODER 'terminreihen' mit mehreren Reihen — nicht beides."))

    # Erst ALLE Kennungen sammeln, dann pruefen — ein Vorwaertsverweis (Reihe a
    # abgeleitet von einer spaeter definierten Reihe b) darf nicht faelschlich als
    # 'unbekannte_reihe' gemeldet werden (Review PR1, Befund A).
    reihen_kennungen: set[str] = set()
    for i, r in _felder_ebene(reihen):
        rid = r.get("id")
        if isinstance(rid, str):
            if rid in reihen_kennungen:
                m.append(_fehler(f"/terminreihen/{i}/id", "doppelte_id",
                                 f"Die Terminreihen-Kennung {rid!r} ist mehrfach vergeben.",
                                 f"Vergebe eindeutige Reihen-Kennungen."))
            reihen_kennungen.add(rid)

    for i, r in _felder_ebene(reihen):
        rid = r.get("id")
        if not isinstance(rid, str):
            continue

        # eigene Felder der Reihe rekursiv pruefen
        if isinstance(r.get("felder"), list):
            _pruefe_feldbaum(m, r["felder"], f"/terminreihen/{i}/felder", d, None)

        # abgeleitet: von existiert (gegen die VOLLSTAENDIGE Kennungsmenge),
        # versatz-Syntax, keine Selbstreferenz.
        termine = r.get("termine")
        if isinstance(termine, dict):
            abg = termine.get("abgeleitet")
            if isinstance(abg, dict):
                _pruefe_abgeleitet(m, f"/terminreihen/{i}/termine/abgeleitet", abg, rid, reihen_kennungen)
                _pruefe_bedingung(m, f"/terminreihen/{i}/termine/abgeleitet/nur_wenn", abg.get("nur_wenn"), d, None)
            # Wiederholungsregel je Reihe genauso pruefen wie in der Kurzform
            # (BLD-R2: eine unbegrenzte RRULE in einer Reihe legt die App
            # gleichermassen lahm).
            regel = termine.get("regel")
            if isinstance(regel, str) and "{parameter." not in regel:
                _pruefe_rrule(m, regel, pfad=f"/terminreihen/{i}/termine/regel")

    # Der Ableitungsgraph wird ueber ALLE Reihen gebildet und auf (mittelbare)
    # Zyklen geprueft — nicht nur auf die direkte Selbstreferenz. Ein Zyklus
    # A->B->A (beliebige Laenge) wird mit dem konkreten Zykluspfad gemeldet.
    _pruefe_ableitungs_zyklen(m, reihen, reihen_kennungen, d)


def _pruefe_ableitungs_zyklen(
    m: list[Meldung],
    reihen: list[Any],
    reihen_kennungen: set[str],
    d: dict[str, Any],
) -> None:
    """Erkennt Zyklen im Ableitungsgraphen beliebiger Laenge.

    Baut aus den 'abgeleitet.von'-Angaben einen gerichteten Graphen (Ziel -> Quelle
    ist eine Gueltigkeits-Nebenbedingung, aber fuer den Zyklustest genuegt die
    Kantenrichtung 'Quelle des Verweises -> verwiesene Reihe'). Ein Zyklus
    A->B->...->A wird mit dem konkreten Pfad als `ableitung_zyklus` gemeldet.
    'standard' ist als Verwiesziel nur in der Kurzform gueltig (keine
    `terminreihen`), deshalb hier nicht Teil des Graphen — ein Verweis auf
    'standard' in einer `terminreihen`-Datei wird bereits als 'unbekannte_reihe'
    bzw. hier als Warnung eingeordnet; dennoch wird er nicht als Zykluskante
    behandelt.
    """
    # -> Kanten: Reihe (deren abgeleitet.von) verweist auf Ziel-Reihe.
    kanten: dict[str, str] = {}
    zeiger: dict[str, str] = {}  # Reihen-Kennung -> JSON-Pointer-Basis der 'von'-Angabe
    for i, r in _felder_ebene(reihen):
        rid = r.get("id")
        termine = r.get("termine")
        if not isinstance(rid, str) or not isinstance(termine, dict):
            continue
        abg = termine.get("abgeleitet")
        if not isinstance(abg, dict):
            continue
        von = abg.get("von")
        if isinstance(von, str):
            kanten[rid] = von
            zeiger[rid] = f"/terminreihen/{i}/termine/abgeleitet/von"

    # Zyklen durch DFS mit Farbmarkierung (0=unbesucht, 1=im aktuellen Pfad, 2=fertig).
    farbe: dict[str, int] = {k: 0 for k in kanten}

    def besuche(knoten: str, pfad: list[str]) -> None:
        farbe[knoten] = 1
        pfad.append(knoten)
        ziel = kanten.get(knoten)
        if ziel in reihen_kennungen:  # nur echte Reihen, nicht 'standard'
            if farbe.get(ziel) == 0:
                besuche(ziel, pfad)
            elif farbe.get(ziel) == 1:
                # Zyklus gefunden: den Teilpfad ab dem Ziel ausschneiden.
                start = pfad.index(ziel) if ziel in pfad else 0
                zyklus = pfad[start:] + [ziel]
                ketten = " -> ".join(zyklus)
                m.append(_fehler(
                    zeiger.get(zyklus[0], "/terminreihen"),
                    "ableitung_zyklus",
                    f"Zyklus im Ableitungsgraphen erkannt: {ketten}.",
                    f"Eine Terminreihe darf sich nicht (auch nicht mittelbar) von sich selbst ableiten. Unterbreche den Zyklus, z. B. indem die Reihe {zyklus[-1]!r} von einer unabhaengigen Reihe stammt.",
                ))
        farbe[knoten] = 2
        pfad.pop()

    for startknoten in list(kanten):
        if farbe[startknoten] == 0:
            besuche(startknoten, [])


def _pruefe_abgeleitet(
    m: list[Meldung],
    pfad: str,
    abg: dict[str, Any],
    eigene_reihe: str,
    reihen_kennungen: set[str],
) -> None:
    """Prueft eine 'abgeleitet'-Angabe: von existiert, kein Selbst-/Zyklus, versatz lesbar."""
    von = abg.get("von")
    if isinstance(von, str):
        kandidaten = reihen_kennungen | {"standard"}
        if von not in kandidaten:
            tipp = _tipp_vorschlag(von, kandidaten)
            zusatz = f" Meinten Sie {tipp!r}?" if tipp else ""
            m.append(_fehler(f"{pfad}/von", "unbekannte_reihe",
                             f"Abgeleitete Terminreihe verweist auf Reihe {von!r}, die nicht existiert.{zusatz}",
                             f"Bekannte Reihen: {', '.join(sorted(kandidaten)) or '(keine)'} — plus 'standard' für die Kurzform."))
        # 'standard' ist nur als Verwiesziel der KURZFORM gueltig; in einer
        # `terminreihen`-Datei gibt es keine Kurzform-Reihe 'standard'.
        if von == "standard":
            m.append(_fehler(f"{pfad}/von", "unbekannte_reihe",
                             f"Verweis auf Reihe 'standard' ist nur in der Kurzform (eine Reihe) gültig, nicht unter 'terminreihen'.",
                             "Nutze die Kennung einer echten Reihe aus 'terminreihen' (oder lege die Kurzform 'termine'/'felder' an)."))
        if von == eigene_reihe:
            m.append(_fehler(f"{pfad}/von", "ableitung_zyklus",
                             f"Terminreihe {eigene_reihe!r} leitet sich von sich selbst ab.",
                             f"Verweise auf eine ANDERE Reihe; die Engine prueft zudem auf mittelbare Zyklen (A von B von A)."))
    versatz = abg.get("versatz")
    if isinstance(versatz, str) and not _VERSATZ_RE.match(versatz):
        m.append(_fehler(f"{pfad}/versatz", "versatz_unlesbar",
                         f"Versatz {versatz!r} ist keine gültige Dauer.",
                         f"Schreibe +/- Zahl + Einheit, z. B. '-2T', '+1W', '-3h' oder '+30min'."))


def _ablauf_elementtypen_aller_felder(d: dict[str, Any]) -> set[str]:
    """Alle deklarierten Elementtypen ueber alle 'ablauf'-Felder (fuer programm-Ansichten)."""
    result: set[str] = set()
    for felder in _alle_feldlisten(d):
        for _, f in _alle_felder_rekursiv(felder):
            if f.get("art") == "ablauf":
                for elem in _objekt_eintraege(f.get("elemente")):
                    if isinstance(elem.get("typ"), str):
                        result.add(elem["typ"])
    return result


def _pruefe_ansichten(m: list[Meldung], d: dict[str, Any]) -> None:
    """Formatvorlagen in `ansichten`: Platzhalter muessen auf etwas zeigen."""
    ansichten = d.get("ansichten") or []
    if not isinstance(ansichten, list):
        return
    bekannte_felder = _alle_feldkennungen(d)
    bekannte_parameter = _parameter_kennungen(d)
    bekannte_merkmale = _bekannte_merkmale(d)
    elementtypen = _ablauf_elementtypen_aller_felder(d)
    for i, a in _felder_ebene(ansichten):
        art = a.get("art")
        # kopf/fuss der 'programm'-Ansicht: Platzhalter auf plan/termin/parameter.
        if art == "programm":
            for schluessel in ("kopf", "fuss"):
                text = a.get(schluessel)
                if isinstance(text, str):
                    for platz in _scan_format(text):
                        _pruefe_platzhalter(
                            m, d, f"/ansichten/{i}/{schluessel}",
                            platz, bekannte_felder, bekannte_parameter, bekannte_merkmale,
                        )
        fmt = a.get("format")
        if not isinstance(fmt, dict):
            continue
        for feldname, muster in fmt.items():
            if not isinstance(muster, str):
                continue
            # Bei 'programm' sind die format-Keys ELEMENTTYPEN (nicht Feld-Kennungen).
            if art == "programm" and elementtypen and feldname not in elementtypen:
                tipp = _tipp_vorschlag(feldname, elementtypen)
                zusatz = f" Meinten Sie {tipp!r}?" if tipp else ""
                m.append(_warnung(f"/ansichten/{i}/format/{feldname}", "unbekannter_elementtyp",
                                  f"Format-Schluessel {feldname!r} ist kein deklarierter Elementtyp des Ablaufs.{zusatz}",
                                  f"Deklarierte Elementtypen: {', '.join(sorted(elementtypen)) or '(keine)'}."))
                continue
            for platz in _scan_format(muster):
                _pruefe_platzhalter(
                    m, d, f"/ansichten/{i}/format/{feldname}",
                    platz, bekannte_felder, bekannte_parameter, bekannte_merkmale,
                )


# Alte, einfache Platzhalter-Suche bleibt als Referenz; der Scanner darunter
# behandelt zusaetzlich die bedingte Form '{feld: körper}' mit Verschachtelung.
_PLATZHALTER_RE = re.compile(r"\{([^{}]+)\}")


def _scan_format(muster: str) -> list[str]:
    """Extrahiert alle Platzhalter einer Formatvorlage.

    Versteht die bedingte Form '{feld: körper}': das Bedingungsfeld vor dem
    Doppelpunkt wird wie ein Platzhalter validiert, der körper (der auch
    verschachtelte Platzhalter enthalten darf) wird weiter durchsucht. Liefert
    damit eine flache Liste einfacher Platzhalter-Köpfe (z. B. 'gaeste',
    'gaeste.vorname', 'team.name').
    """
    ergebnis: list[str] = []
    i = 0
    n = len(muster)
    while i < n:
        if muster[i] == "{":
            tiefe = 1
            j = i + 1
            while j < n and tiefe > 0:
                if muster[j] == "{":
                    tiefe += 1
                elif muster[j] == "}":
                    tiefe -= 1
                j += 1
            inner = muster[i + 1 : j - 1]
            doppelpunkt = _top_level_doppelpunkt(inner)
            if doppelpunkt >= 0:
                beding = inner[:doppelpunkt].strip()
                koerper = inner[doppelpunkt + 1 :]
                if beding:
                    ergebnis.append(beding)
                ergebnis.extend(_scan_format(koerper))
            else:
                kopf = inner.strip()
                if kopf:
                    ergebnis.append(kopf)
            i = j
        else:
            i += 1
    return ergebnis


def _top_level_doppelpunkt(text: str) -> int:
    """Index des ersten ':' ausserhalb geschachtelter Klammern (oder -1)."""
    tiefe = 0
    for idx, c in enumerate(text):
        if c == "{":
            tiefe += 1
        elif c == "}":
            tiefe -= 1
        elif c == ":" and tiefe == 0:
            return idx
    return -1


def _pruefe_platzhalter(
    m: list[Meldung],
    d: dict[str, Any],
    pfad: str,
    platz: str,
    bekannte_felder: set[str],
    bekannte_parameter: set[str],
    bekannte_merkmale: dict[str, set[str]],
) -> None:
    """Ein einzelner Platzhalter {a.b} in einer Formatvorlage."""
    teile = platz.split(".", 1)
    kopf = teile[0].strip()
    rest = teile[1].strip() if len(teile) > 1 else None

    if kopf == "eintrag":
        erlaubt = eingebaute_attribut_schluessel("lieder") | eingebaute_attribut_schluessel("")
        # eingebaute_attribut_schluessel("") liefert die allgemeinen Sammlungsattribute.
        alle_merkmale = {mk for gruppe in bekannte_merkmale.values() for mk in gruppe}
        if rest is None:
            m.append(_warnung(f"{pfad}", "format_platzhalter_unvollstaendig",
                              f"Platzhalter {{eintrag}} nennt kein Attribut.",
                              "Schreibe z. B. {eintrag.titel} oder {eintrag.buch}."))
        elif rest not in erlaubt and rest not in alle_merkmale:
            tipp = _tipp_vorschlag(rest, erlaubt | alle_merkmale)
            zusatz = f" Meinten Sie {tipp!r}?" if tipp else ""
            m.append(_warnung(f"{pfad}", "format_unbekanntes_attribut",
                              f"Platzhalter {{eintrag.{rest}}} zeigt auf unbekanntes Attribut {rest!r}.{zusatz}",
                              f"Eingebaute Attribute: {', '.join(sorted(erlaubt))}; oder ein deklariertes Merkmal."))
        return

    if kopf == "parameter":
        if rest is None:
            m.append(_warnung(f"{pfad}", "format_platzhalter_unvollstaendig",
                              f"Platzhalter {{parameter}} nennt keine Kennung.",
                              "Schreibe z. B. {parameter.thema}."))
        elif rest not in bekannte_parameter:
            tipp = _tipp_vorschlag(rest, bekannte_parameter)
            zusatz = f" Meinten Sie {tipp!r}?" if tipp else ""
            m.append(_warnung(f"{pfad}", "format_unbekannter_parameter",
                              f"Platzhalter {{parameter.{rest}}} zeigt auf nicht deklarierten Parameter.{zusatz}",
                              f"Deklarierte Parameter: {', '.join(sorted(bekannte_parameter)) or '(keine)'}."))
        return

    if kopf == "termin":
        erlaubt_termin = {"datum", "datum_ab", "datum_bis", "uhrzeit", "name", "anlass", "wochentag", "nr"}
        if rest is None or rest not in erlaubt_termin:
            m.append(_warnung(f"{pfad}", "format_unbekannter_termin",
                              f"Platzhalter {{termin.{rest or ''}}} ist kein bekanntes Termin-Feld.",
                              f"Bekannte Termin-Felder: {', '.join(sorted(erlaubt_termin))}."))
        return

    if kopf == "plan":
        # Plan-Attribute (immer vorhanden), z. B. {plan.titel} im kopf/fuss einer
        # 'programm'-Ansicht. Der Plan haelt Titel, Zeitraum, Parameterwerte, Status.
        erlaubt_plan = {"titel", "zeitraum", "status"}
        if rest is None or rest not in erlaubt_plan:
            m.append(_warnung(f"{pfad}", "format_unbekannter_termin",
                              f"Platzhalter {{plan.{rest or ''}}} ist kein bekanntes Plan-Feld.",
                              f"Bekannte Plan-Felder: {', '.join(sorted(erlaubt_plan))}."))
        return

    # Nummer eines nummerierten Ablauf-Elements ('nr'): die laufende Nummer
    # innerhalb des Elementtyps (C4: nummerierte Lieder). Nur in der
    # 'programm'-Ansicht sinnvoll; hier als gueltig durchgelassen.
    if kopf == "nr" and rest is None:
        return

    if kopf == "anlass":
        # 'anlass' ist ein Termin-Feld-Keyword: {anlass} bzw. {anlass:<name>}.
        # Ohne Attribut ist es gueltig; der Name ist frei.
        return

    # sonst: {feld.<attr>} -> feld muss existieren, attr ein Personen-/Sammlungsattribut
    if kopf not in bekannte_felder:
        tipp = _tipp_vorschlag(kopf, bekannte_felder)
        zusatz = f" Meinten Sie {tipp!r}?" if tipp else ""
        m.append(_warnung(f"{pfad}", "format_unbekanntes_feld",
                          f"Platzhalter {{{kopf}}} zeigt auf unbekanntes Feld {kopf!r}.{zusatz}",
                          f"Bekannte Felder: {', '.join(sorted(bekannte_felder)) or '(keine)'}."))
        return
    if rest is not None:
        erlaubt = eingebaute_attribut_schluessel("person") | eingebaute_attribut_schluessel("lieder") | eingebaute_attribut_schluessel("")
        alle_merkmale = {mk for gruppe in bekannte_merkmale.values() for mk in gruppe}
        if rest not in erlaubt and rest not in alle_merkmale:
            tipp = _tipp_vorschlag(rest, erlaubt | alle_merkmale)
            zusatz = f" Meinten Sie {tipp!r}?" if tipp else ""
            m.append(_warnung(f"{pfad}", "format_unbekanntes_attribut",
                              f"Platzhalter {{{kopf}.{rest}}} zeigt auf unbekanntes Attribut {rest!r}.{zusatz}",
                              f"Eingebaute Attribute: {', '.join(sorted(erlaubt))}; oder ein deklariertes Merkmal."))


def _pruefe_rollen_filter_merkmale(
    m: list[Meldung],
    basis: str,
    filter_: Any,
    d: dict[str, Any],
) -> None:
    """Meldet `merkmal`-Verweise in Rollen-Filtern, die nirgends deklariert sind.

    Eine WARNUNG (kein Fehler): Merkmale sind gemeindeweit geteilt und koennen
    aus einem anderen Plantyp stammen (Konzept B5). Der Hinweis nennt darum die
    Deklarationsstelle, nicht nur den Fehler.
    """
    if not isinstance(filter_, dict):
        return
    person_merkmale = _bekannte_merkmale(d).get("person", set())
    for schluessel, wert in filter_.items():
        if schluessel in ("alle", "eine"):
            for k, kind in enumerate(wert or []):
                _pruefe_rollen_filter_merkmale(m, f"{basis}/{schluessel}/{k}", kind, d)
        elif schluessel == "nicht":
            _pruefe_rollen_filter_merkmale(m, f"{basis}/nicht", wert, d)
        elif schluessel == "merkmal":
            if isinstance(wert, str) and wert not in person_merkmale:
                tipp = _tipp_vorschlag(wert, person_merkmale)
                zusatz = f" Meinten Sie {tipp!r}?" if tipp else ""
                m.append(_warnung(f"{basis}/merkmal", "merkmal_nicht_deklariert",
                                  f"Filter verweist auf Merkmal {wert!r}, das dieser Plantyp nicht deklariert.{zusatz}",
                                  f"Merkmale sind gemeindeweit geteilt und duerfen aus einem anderen Plantyp stammen; deklariere es bei Bedarf unter 'merkmale.person' (z. B. {{\"id\": {wert!r}, \"art\": \"tag\"}})."))


# --------------------------------------------------------------------------- #
# Tippfehler-Vorschlag
# --------------------------------------------------------------------------- #


def _tipp_vorschlag(wert: str, kandidaten: Iterable[str]) -> str | None:
    """Bester aehnlicher Vorschlag (difflib), fall-back None bei zu grosser Distanz."""
    k = sorted(kandidaten)
    if not k:
        return None
    nahe = difflib.get_close_matches(wert, k, n=1, cutoff=0.6)
    return nahe[0] if nahe else None
