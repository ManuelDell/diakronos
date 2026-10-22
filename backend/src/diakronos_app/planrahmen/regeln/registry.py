"""Registry der Plan-Rahmen-Bausteine (Regeln, Feldarten, Fuellstrategien).

Diese Registry ist die *eine* Quelle, aus der Pruefung (`pruefung.py`) und
Dokumentation (`referenz.py`) schoepfen. Sie deklariert, WAS es gibt — die
ausfuehrliche Logik der Regel-Bausteine kommt in einer spaeteren Karte
(Engine). Damit neue Bausteine ohne Schema-Bruch dazukommen (Konzept P11),
haelt das Hauptschema keine Regelparameter fest: Die Pruefung der
Regelparameter laeuft hier gegen die Parameter-JSON-Schemas der Bausteine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

# --------------------------------------------------------------------------- #
# Regel-Bausteine
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class RegelBaustein:
    """Deklaration eines Regel-Bausteins (Startkatalog B8, erweiterbar)."""

    schluessel: str
    kurz: str
    doku: str
    parameter_schema: dict[str, Any]
    beispiel: dict[str, Any]

    def parameternamen(self) -> set[str]:
        """Namen der erlaubten Parameter-Schluessel (ohne baustein/stufe/gewicht)."""
        return set(self.parameter_schema.get("properties", {}).keys())


def _param(required: list[str], props: dict[str, Any]) -> dict[str, Any]:
    """Kleiner Helfer: ein straffes Parameter-JSON-Schema (2020-12).

    Reicht die gemeinsamen $defs (rolfen_filter) mit hinein, damit ein
    ``$ref: "#/$defs/rollen_filter"`` innerhalb der Parameter-Schemas aufloest.
    """
    schema = {
        "type": "object",
        "required": required,
        "additionalProperties": False,
        "properties": props,
    }
    if "$defs" not in schema:
        schema["$defs"] = _ROLLEN_FILTER_SCHEMA["$defs"]
    return schema


# Gemeinsame Parameter-Schemateile fuer die Bausteine.
_p_feld = {
    "feld": {
        "type": "string",
        "description": "Kennung des Felds (oder Feld-Pfads), auf das die Regel wirkt.",
        "examples": ["lieder", "einsingen"],
    }
}
_p_rolle = {
    "rolle": {
        "description": "Rolle bzw. Personen-Filter, auf den die Regel wirkt (Objekt-Filter oder '@'-Referenz).",
        "oneOf": [
            {"$ref": "#/$defs/rollen_filter"},
            {
                "type": "string",
                "pattern": "^@[a-z0-9][a-z0-9_\\-]*$",
            },
        ],
    }
}
# Selbst-tragender (in sich geschlossener) Rollen-Filter fuer die
# Parameter-Schemas der Bausteine. Die Parameter-Schemas werden eigenstaendig
# validiert (ohne das Hauptschema), deshalb darf hier kein $ref auf
# '#/$defs/...' des Hauptschemas stehen.
_ROLLEN_FILTER_SCHEMA = {
    "$defs": {
        "rollen_filter": {
            "type": "object",
            "additionalProperties": False,
            "minProperties": 1,
            "maxProperties": 1,
            "properties": {
                "alle": {"type": "array", "items": {"$ref": "#/$defs/rollen_filter"}},
                "eine": {"type": "array", "items": {"$ref": "#/$defs/rollen_filter"}},
                "nicht": {"$ref": "#/$defs/rollen_filter"},
                "merkmal": {"type": "string"},
                "gruppe": {"type": "string"},
                "anmeldung": {"type": "string"},
                "person": {"type": "string"},
            },
        },
        "fremd_feld": {
            "type": "object",
            "required": ["plantyp", "feld"],
            "additionalProperties": False,
            "properties": {
                "plantyp": {"type": "string"},
                "feld": {"type": "string"},
            },
        },
    },
    "oneOf": [
        {"$ref": "#/$defs/rollen_filter"},
        {"type": "string", "pattern": "^@[a-z0-9][a-z0-9_\\-]*$"},
    ],
}
_p_zeitraum = {
    "zeitraum": {
        "type": "string",
        "enum": ["termin", "woche", "monat", "jahr"],
        "description": "Bezugszeitraum fuer die Hoechst-/Mindestzahl.",
        "examples": ["monat", "woche"],
    }
}
_p_anzahl = {
    "anzahl": {
        "type": "integer",
        "minimum": 0,
        "description": "Anzahl (z. B. Hoechstzahl oder Mindestzahl).",
        "examples": [2],
    }
}


REGEL_BAUSTEINE: list[RegelBaustein] = [
    RegelBaustein(
        schluessel="abwesenheit_beachten",
        kurz="Abwesenheiten respektieren (Urlaub, Krankheit, abgemeldet).",
        doku=(
            "Personen, die im fraglichen Zeitraum abwesend sind, werden nicht "
            "eingeplant. Ist das Feld ein Pflichtfeld und es findet sich kein "
            "Ersatz, bleibt es leer und es erscheint eine verstaendliche "
            "Meldung — nie ein Absturz."
        ),
        parameter_schema=_param([], {}),
        beispiel={"baustein": "abwesenheit_beachten", "stufe": "muss"},
    ),
    RegelBaustein(
        schluessel="mindestabstand",
        kurz="Gleicher Eintrag / gleiche Person nicht oefter als im Mindestabstand.",
        doku=(
            "Haelt einen zeitlichen Mindestabstand zwischen Wiederholungen "
            "desselben Eintrags bzw. derselben Person ein (z. B. ein Lied "
            "nicht oefter als alle 8 Wochen)."
        ),
        parameter_schema=_param(
            ["feld", "wochen"],
            {
                **_p_feld,
                "wochen": {
                    "type": "integer",
                    "minimum": 1,
                    "description": "Mindestabstand in Wochen.",
                    "examples": [8],
                },
                "fuer": {
                    "type": "string",
                    "enum": ["eintrag", "person"],
                    "default": "eintrag",
                    "description": "Ob der Abstand je Eintrag oder je Person gilt.",
                },
                "auch_in": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Kennungen weiterer Plantypen, deren gleiche Eintraege in die gemeinsame Abstands-Historie mitzaehlen (z. B. ein Lied im Programm zaehlt fuer den Chorplan-Abstand).",
                },
            },
        ),
        beispiel={"baustein": "mindestabstand", "feld": "lieder", "wochen": 8, "stufe": "sollte"},
    ),
    RegelBaustein(
        schluessel="max_pro_zeitraum",
        kurz="Hoechstzahl je Zeitraum (z. B. max. 2 Predigten/Monat).",
        doku=(
            "Begrenzt, wie oft eine Person (oder eine Rolle insgesamt) in einem "
            "Zeitraum eingeplant werden darf."
        ),
        parameter_schema=_param(
            ["anzahl", "zeitraum"],
            {
                **_p_anzahl,
                **_p_zeitraum,
                **_p_rolle,
                "person": {
                    "type": "string",
                    "description": "Kennung einer einzelnen Person (alternativ zu 'rolle').",
                },
            },
        ),
        beispiel={"baustein": "max_pro_zeitraum", "anzahl": 2, "zeitraum": "monat", "stufe": "sollte"},
    ),
    RegelBaustein(
        schluessel="min_pro_zeitraum",
        kurz="Mindestzahl je Zeitraum (z. B. mind. 1 Diensterfahrung/Monat).",
        doku=(
            "Stellt sicher, dass eine Person (oder Rolle) in einem Zeitraum "
            "mindestens eine bestimmte Anzahl Dienste uebernimmt."
        ),
        parameter_schema=_param(
            ["anzahl", "zeitraum"],
            {**_p_anzahl, **_p_zeitraum, **_p_rolle},
        ),
        beispiel={"baustein": "min_pro_zeitraum", "anzahl": 1, "zeitraum": "monat", "stufe": "sollte"},
    ),
    RegelBaustein(
        schluessel="gleich_verteilen",
        kurz="Fairness: Dienste moeglichst gleichmaessig verteilen (Rolle oder Team-Feld).",
        doku=(
            "Sorgt dafuer, dass die Dienste gleichmaessig verteilt werden — "
            "entweder ueber eine Rolle (Filter ueber Personen) oder ueber ein "
            "Feld (z. B. ein 'team'-Feld, dessen Teams fair rotieren). "
            "Vorbelegte/abgeleitete Eintraege zaehlen standardmaessig nicht; "
            "vorbelegte_mitzaehlen=true schliesst diese Kopien ein. Historie ohne "
            "Herkunftsangabe zaehlt als eigene Entscheidung."
        ),
        parameter_schema=_param(
            [],
            {
                "rolle": {"description": "Rolle bzw. Personen-Filter, der fair verteilt wird (alternative zu 'feld').",
                          "oneOf": [{"$ref": "#/$defs/rollen_filter"},
                                    {"type": "string", "pattern": "^@[a-z0-9][a-z0-9_\\-]*$"}]},
                "feld": {"type": "string",
                         "description": "Feld-Kennung (z. B. ein 'team'-Feld), das fair verteilt wird (alternative zu 'rolle')."},
                "vorbelegte_mitzaehlen": {"type": "boolean", "default": False,
                    "description": "Auch vorbelegte und abgeleitete Eintraege als Dienste zaehlen (Standard: nur eigene Entscheidungen)."},
            },
        ),
        beispiel={"baustein": "gleich_verteilen", "rolle": {"anmeldung": "mitarbeiter"}, "stufe": "sollte"},
    ),
    RegelBaustein(
        schluessel="nicht_gleichzeitig",
        kurz="Zwei Felder nicht von derselben Person gleichzeitig (z. B. Dirigat + Klavier).",
        doku=(
            "Verhindert, dass dieselbe Person in einem Termin zwei benannte "
            "Felder zugleich besetzt."
        ),
        parameter_schema=_param(
            ["felder"],
            {
                "felder": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 2,
                    "description": "Die Feld-Kennungen, die nicht dieselbe Person tragen duerfen.",
                }
            },
        ),
        beispiel={"baustein": "nicht_gleichzeitig", "felder": ["dirigent", "klavier"], "stufe": "muss"},
    ),
    RegelBaustein(
        schluessel="zusammen",
        kurz="Personen immer gemeinsam einteilen (z. B. Ehepaar).",
        doku=(
            "Haelt zwei Personen immer zusammen: wird die eine eingeplant, "
            "auch die andere."
        ),
        parameter_schema=_param(
            ["personen"],
            {
                "personen": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 2,
                    "description": "Die Kennungen der Personen, die zusammen bleiben.",
                }
            },
        ),
        beispiel={"baustein": "zusammen", "personen": ["anna", "bruno"], "stufe": "muss"},
    ),
    RegelBaustein(
        schluessel="nicht_zusammen",
        kurz="Personen nie gemeinsam einteilen.",
        doku="Verhindert, dass zwei Personen im selben Termin eingeplant werden.",
        parameter_schema=_param(
            ["personen"],
            {
                "personen": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 2,
                    "description": "Die Kennungen der Personen, die sich ausschliessen.",
                }
            },
        ),
        beispiel={"baustein": "nicht_zusammen", "personen": ["anna", "bruno"], "stufe": "muss"},
    ),
    RegelBaustein(
        schluessel="vorher_geuebt",
        kurz="Ein Eintrag muss erst N mal geuebt sein, bevor er gesungen/gespielt wird.",
        doku=(
            "Erlaubt einen Eintrag erst, wenn er zuvor eine bestimmte Anzahl "
            "Mal in einem Uebungsfeld erschienen ist. Die Uebung kann im selben "
            "Plantyp liegen ('uebungsfeld') ODER in einem ANDEREN Plantyp "
            "('uebung', planuebergreifend, z. B. die Lieder eines Programms "
            "muessen zuvor im Chorplan geuebt sein — {'plantyp': 'chorplan', "
            "'feld': 'einueben'}). 'auch_in' zaehlt zusaetzlich gleiche "
            "Eintraege in anderen Plantypen zur gemeinsamen Historie (z. B. ein "
            "Lied im Programm zaehlt fuer den Chorplan-Abstand). Der Generator "
            "fuellt optimierte Uebungsfelder vorausschauend anhand der festgelegten "
            "Einsaetze (auch aus expliziten Bezugsplaenen), priorisiert nach Frist. "
            "vorlauf_wochen begrenzt neue Uebungen; Vorgabe max(4, mindestens)."
        ),
        parameter_schema=_param(
            ["feld", "mindestens"],
            {
                **_p_feld,
                "uebungsfeld": {
                    "type": "string",
                    "description": "Kennung des Felds im SELBEN Plantyp, das als Uebung zaehlt (Alternative zu 'uebung').",
                },
                "uebung": {
                    "description": "Planuebergreifender Verweis auf das Uebungsfeld in einem anderen Plantyp (Alternative zu 'uebungsfeld').",
                    "$ref": "#/$defs/fremd_feld",
                },
                "auch_in": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Kennungen weiterer Plantypen, deren gleiche Eintraege mitzaehlen.",
                },
                "mindestens": {
                    "type": "integer",
                    "minimum": 1,
                    "description": "Mindestzahl der Uebungen vor dem Einsatz.",
                },
                "vorlauf_wochen": {
                    "type": "integer", "minimum": 1,
                    "description": "Neue Uebungen in diesem Vorlauf vor dem Einsatz planen; Vorgabe max(4, mindestens) Wochen. Vorhandene aeltere Uebungen zaehlen weiterhin.",
                },
            },
        ),
        beispiel={"baustein": "vorher_geuebt", "feld": "lieder", "uebungsfeld": "einueben", "mindestens": 2},
    ),
    RegelBaustein(
        schluessel="passend_zum_anlass",
        kurz="Nur Eintraege mit passendem Merkmal am entsprechenden Anlass.",
        doku=(
            "Beschraenkt die Auswahl an einem Anlass auf Eintraege, deren "
            "Merkmal zum Anlass passt (z. B. Erntedank-Lied an Erntedank)."
        ),
        parameter_schema=_param(
            ["feld", "merkmal"],
            {
                **_p_feld,
                "merkmal": {
                    "type": "string",
                    "description": "Merkmal des Eintrags, das zum Anlass passen muss.",
                },
            },
        ),
        beispiel={"baustein": "passend_zum_anlass", "feld": "lieder", "merkmal": "thema"},
    ),
    RegelBaustein(
        schluessel="verfuegbarkeit",
        kurz="Feste Verfuegbarkeitsmuster einer Person oder eines Teams beachten.",
        doku=(
            "Beruecksichtigt ein festes zeitliches Muster, wann eine Person ODER "
            "ein Team verfuegbar ist (z. B. nur 1. Sonntag im Monat). Das Muster "
            "ist entweder ein kurzes Kuerzel wie '1.So' oder ein strukturiertes "
            "Objekt, z. B. {'termin_im_monat': 1} (jeder 1. Termin der Reihe im "
            "Monat)."
        ),
        parameter_schema=_param(
            ["muster"],
            {
                "person": {
                    "type": "string",
                    "description": "Kennung der Person (alternative zu 'team').",
                },
                "team": {
                    "type": "string",
                    "description": "Kennung des Teams (alternative zu 'person').",
                },
                "muster": {
                    "description": "Verfuegbarkeitsmuster: Kurzform-String ('1.So') oder Objekt {'termin_im_monat': n}.",
                    "oneOf": [
                        {"type": "string"},
                        {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {"termin_im_monat": {"type": "integer"}},
                            "required": ["termin_im_monat"],
                        },
                    ],
                    "examples": ["1.So", {"termin_im_monat": 1}],
                },
            },
        ),
        beispiel={"baustein": "verfuegbarkeit", "team": "Gruppe 3", "muster": {"termin_im_monat": 1}, "stufe": "muss"},
    ),
]


REGEL_BAUSTEINE_NA = {
    b.schluessel: b for b in REGEL_BAUSTEINE
}


def bekannte_bausteine() -> list[str]:
    """Kennungen aller deklarierten Regel-Bausteine."""
    return [b.schluessel for b in REGEL_BAUSTEINE]


def hole_baustein(schluessel: str) -> RegelBaustein:
    """Liefert die Deklaration zu einer Baustein-Kennung."""
    return REGEL_BAUSTEINE_NA[schluessel]


# --------------------------------------------------------------------------- #
# Feldarten
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Feldart:
    """Deklaration einer Feldart (B3)."""

    schluessel: str
    bedeutung: str
    beispiele: tuple[str, ...] = ()


FELDARTEN: list[Feldart] = [
    Feldart("person", "genau eine Person in einer Rolle (z. B. Einsingen leiten).", ("Einsingen", "Tagesleitung")),
    Feldart("personen", "eine oder mehrere Personen in einer Rolle (Anzahl steuerbar).", ("Solo", "Leitung")),
    Feldart("eintrag", "ein Element aus einer Sammlung (z. B. ein Lied, eine Bibelarbeit).", ("Lied", "Bibelarbeit", "Spiel")),
    Feldart("text", "freier Text (z. B. Thema, Bibelstelle).", ("Thema", "Bibelstelle", "Raum")),
    Feldart("zahl", "eine Zahl.", ("Anzahl Stuehle",)),
    Feldart("datum", "ein Datum.", ("Frist",)),
    Feldart("auswahl", "genau ein Wert aus einer festen Liste (`werte`).", ("Ort",)),
    Feldart("gruppe", "tragendes Untergeruest: enthaelt Unterfelder (`inhalt`), optional `varianten` und `teile`.", ("Frohe Stunde",)),
    Feldart("team", "eine Gruppe von Personen (Diakonos-Gruppe), ausgewaehlt ueber `teams`; optional `mitglieder` als Teilmenge.", ("Musikteam", "Saenger")),
    Feldart("ablauf", "geordnete, frei sortierbare Liste heterogener Elemente (`elemente`, je Typ mit eigenem `inhalt` und optional `nummeriert`); offenes Ende via `anzahl: '1..*'`.", ("Programmablauf", "Gottesdienst-Ablauf")),
]

FELDARTEN_NA = {f.schluessel: f for f in FELDARTEN}


def bekannte_feldarten() -> list[str]:
    """Kennungen aller Feldarten."""
    return [f.schluessel for f in FELDARTEN]


# --------------------------------------------------------------------------- #
# Fuellstrategien
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Fuellstrategie:
    """Deklaration einer Fuellstrategie (B7)."""

    schluessel: str
    wirkung: str
    beispiel: str


FUELLSTRATEGIEN: list[Fuellstrategie] = [
    Fuellstrategie("manuell", "nie automatisch — nur von Hand.", "Lieder, die neu eingeuebt werden"),
    Fuellstrategie("reihum", "Personen der Rolle der Reihe nach, Abwesende werden uebersprungen.", "Einsingen, Tagesleitung"),
    Fuellstrategie("der_reihe_nach", "Sammlungseintraege in ihrer Reihenfolge.", "Bibelarbeit Tag 1..n"),
    Fuellstrategie("vorbelegen", "Wert aus einem anderen Feld/Merkmal uebernehmen (`aus`).", "Lied → Dirigent/Klavier"),
    Fuellstrategie("optimieren", "bestmoegliche Wahl nach allen Regeln (Standard).", "Liedauswahl, Prediger"),
]

FUELLSTRATEGIEN_NA = {f.schluessel: f for f in FUELLSTRATEGIEN}


def bekannte_fuellstrategien() -> list[str]:
    """Kennungen aller Fuellstrategien."""
    return [f.schluessel for f in FUELLSTRATEGIEN]


# --------------------------------------------------------------------------- #
# Eingebaute Attribute (Stammdaten-Schluessel, die ohne Deklaration existieren)
# --------------------------------------------------------------------------- #


# Eingebaute Attribute sind die fest vorgegebenen Datenfelder, die jeder
# Personen- bzw. Sammlungseintrag von sich aus traegt — sie brauchen KEINE
# Merkmal-Deklaration im Plantyp und duerfen durch eigene Merkmale weder
# verdeckt noch umbenannt werden (die Pruefung meldet ein ueberschattendes
# Merkmal als Fehler). Formatvorlagen ({eintrag.titel}, {dirigent.kuerzel}) und
# aus-Referenzen duerfen auf sie zeigen.


# Personen: name, vorname, nachname, kuerzel, email sind immer vorhanden.
# (Orientierung am Stammdaten-Bild der App; 'kuerzel' ist hier das eingebaute
# Kuerzel — der Chorplan deklariert es NICHT als eigenes Merkmal.)
PERSON_ATTRIBUTE: dict[str, str] = {
    "name": "Vollstaendiger Anzeigename (Nachname, Vorname) der Person.",
    "vorname": "Vorname der Person.",
    "nachname": "Nachname der Person.",
    "kuerzel": "Kurzes Kuerzel der Person (z. B. fuer Formatvorlagen).",
    "email": "E-Mail-Adresse der Person.",
}

# Eingebaute Sammlung 'lieder' (Psalmos-Liedgut): orientiert an der echten
# Tabelle `models/psalmos.py` (Klasse `Lied`).
LIEDER_ATTRIBUTE: dict[str, str] = {
    "titel": "Titel des Liedes (Psalmos: `titel`).",
    "alternativtitel": "Alternativer Titel des Liedes (`alternativtitel`).",
    "buch": "Gesangbuch des Liedes (Psalmos: `gesangbuch_nummer`-Grundlage).",
    "nummer": "Nummer des Liedes im Gesangbuch (`gesangbuch_nummer`).",
    "seite": "Seite im Gesangbuch/Heft, auf der das Lied steht (C4; darf fehlen — viele Programmhefte nennen keine Seite).",
    "quelle": "Woher das Lied stammt: 'buch' (Liederbuch/Heft, mit Nummer/Seite), 'kopie' (Kopie/Einzelblatt, keine Nummer) oder 'ohne' (noch nichts gepflegt). Formatvorlagen nutzen das, um 'Nr.' nur bei einer echten Nummer zu zeigen.",
    "anzeige": "Fertige, menschenlesbare Kennung des Liedes: 'Kopie', 'JN 1297', 'WH S. 150' — oder leer, wenn es keine Angabe gibt. Nie ein 'Nr.' ohne Nummer; die Formatvorlagen nutzen diesen Platzhalter (z. B. `{eintrag.anzeige}`).",
    "ccli": "CCLI-Nummer (`ccli_nummer`).",
    "zuletzt_gesungen": "Datum, wann das Lied zuletzt gesungen wurde (`zuletzt_gesungen`).",
    "anzahl_gesungen": "Wie oft das Lied bereits gesungen wurde (`anzahl_gesungen`).",
    "notiz": "Freie Notiz zum Lied (`notiz`).",
}

# Jede Sammlung (eingebaut wie 'lieder' oder selbst deklariert) traegt von
# sich aus einen Titel und eine Reihenfolge.
SAMMLUNG_ATTRIBUTE: dict[str, str] = {
    "titel": "Titel des Sammlungseintrags.",
    "reihenfolge": "Position des Eintrags in seiner Sammlung (fuer 'der_reihe_nach').",
}


def eingebaute_attribute_person() -> dict[str, str]:
    """Eingebaute Attribute einer Person (Schluessel -> Bedeutung)."""
    return dict(PERSON_ATTRIBUTE)


def eingebaute_attribute_lieder() -> dict[str, str]:
    """Eingebaute Attribute der Sammlung 'lieder' (Schluessel -> Bedeutung)."""
    return dict(LIEDER_ATTRIBUTE)


def eingebaute_attribute_sammlung() -> dict[str, str]:
    """Eingebaute Attribute, die jede Sammlung traegt (Schluessel -> Bedeutung)."""
    return dict(SAMMLUNG_ATTRIBUTE)


def eingebaute_attribut_schluessel(sammlung: str) -> set[str]:
    """Alle eingebauten Attribut-Schluessel fuer eine Sammlung.

    Fuer 'person' die Personen-Attribute; fuer 'lieder' die Lied-Attribute
    ergaenzt um die allgemeinen Sammlungs-Attribute; fuer jede andere (eigene)
    Sammlung nur die allgemeinen Sammlungs-Attribute. Eingebaute Attribute
    ueberlappen damit bewusst zwischen 'lieder' und den Sammlungen: 'titel' und
    'reihenfolge' gehoeren zu beiden.
    """
    if sammlung == "person":
        return set(PERSON_ATTRIBUTE)
    if sammlung == "lieder":
        return set(LIEDER_ATTRIBUTE) | set(SAMMLUNG_ATTRIBUTE)
    return set(SAMMLUNG_ATTRIBUTE)


# --------------------------------------------------------------------------- #
# gemeinsamer Zugriff
# --------------------------------------------------------------------------- #


def alle_bausteine() -> Iterable[str]:
    """Alle Kennungen der Regel-Bausteine (fuer Tippfehler-Vorschlaege)."""
    return REGEL_BAUSTEINE_NA.keys()


# --------------------------------------------------------------------------- #
# Logik-Registrierung (Engine, P2)
# --------------------------------------------------------------------------- #


# Die Logik der Bausteine lebt in ``regeln/auswertung.py``; dort wird jede
# Funktion unter demselben Schluessel wie die Deklaration registriert. Die
# Registry hält dieses Abbild, damit Deklaration und Logik nicht
# auseinanderlaufen (die Vollstaendigkeit prueft ein Test).
LOGIK_REGISTRY: dict[str, object] = {}


def registriere_logik(schluessel: str, fabrik: object) -> None:
    """Registriert die Logik-Fabrik zu einem Baustein-Schluessel."""
    LOGIK_REGISTRY[schluessel] = fabrik


def logik_fabrik(schluessel: str) -> object | None:
    """Die registrierte Logik-Fabrik eines Bausteins (oder None)."""
    return LOGIK_REGISTRY.get(schluessel)
