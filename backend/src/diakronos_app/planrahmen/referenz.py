"""Dokumentations-Generator: erzeugt REFERENZ.md aus Schema + Registries.

Die Referenz ist **generiert** und nie von Hand gepflegt (Konzept P12: eine
Quelle). Ein Test prueft, dass die eingecheckte REFERENZ.md zum aktuellen
Schema und zu den aktuellen Registries passt — aendert sich eine Deklaration,
muss die Doku neu erzeugt werden.

`erzeuge_referenz()` liefert den vollstaendigen Markdown-Text; das Skript
`backend/scripts/planrahmen_doku.py` schreibt ihn nach
`diakronos_app/planrahmen/doku/REFERENZ.md` (im Paket, damit er im Image
vorhanden ist — ``docs/`` fehlt dort, NACHTRAG DOCKER).

Hinweis zur Benennung: dieses Modul heisst bewusst ``referenz.py`` und nicht
``doku.py``, weil ``planrahmen/doku/`` ein *Paket* mit den mitgelieferten
Dokumenten ist — ein gleichnamiges Modul wuerde es verdecken.
"""

from __future__ import annotations

import json
from typing import Any

from . import ressourcen
from .feiertage import FEIERTAGE
from .pruefung import MELDUNGS_CODES
from .regeln.registry import (
    FELDARTEN,
    FUELLSTRATEGIEN,
    LIEDER_ATTRIBUTE,
    PERSON_ATTRIBUTE,
    REGEL_BAUSTEINE,
    SAMMLUNG_ATTRIBUTE,
)


def _ueber(kopf: str, text: str) -> str:
    """Ein Abschnitt mit Ueberschrift."""
    return f"\n## {kopf}\n\n{text}\n"


def _properties(schema: dict[str, Any]) -> dict[str, Any]:
    return schema.get("properties", {}) or {}


def _beschreibe_prop(prop: dict[str, Any], name: str) -> str:
    """Ein Eintrag fuer eine Eigenschaft: Name, Pflicht?, Beschreibung, Beispiele.

    `prop` ist das Eigenschafts-Schema (nicht das umgebende Objekt)."""
    # Reine $ref-Eigenschaft: die Beschreibung steht im referenzierten $def,
    # der unten als eigener Abschnitt erscheint. Wir verweisen dorthin.
    if set(prop.keys()) == {"$ref"}:
        ziel = prop["$ref"].rsplit("/", 1)[-1]
        titel = _DEF_TITEL.get(ziel, ziel)
        return f"**`{name}`** — siehe Abschnitt *{titel}*."
    beschr = prop.get("description", "")
    zeile = f"**`{name}`**"
    if "default" in prop:
        zeile += f" (Vorgabe: `{prop['default']}`)"
    zeile += f" — {beschr}"
    if prop.get("examples"):
        zeile += "\n\nBeispiele: `" + "`, `".join(json.dumps(e, ensure_ascii=False) for e in prop["examples"]) + "`."
    return zeile


# $defs-Schluessel -> Abschnittstitel in der generierten Referenz.
_DEF_TITEL: dict[str, str] = {
    "parameter": "Parameter",
    "merkmal": "Merkmale",
    "merkmale": "Merkmale",
    "sammlung": "Sammlung",
    "termine": "Termine",
    "manueller_termin": "Manueller Termin",
    "ausnahme": "Ausnahme",
    "anlass": "Anlass",
    "wirkung": "Wirkung (eines Anlasses)",
    "feld": "Feld (rekursiv)",
    "feldliste": "Feld (rekursiv)",
    "rollen_knoten": "Rollen-Filter",
    "rollen_filter": "Rollen-Filter",
    "benannte_rolle": "Benannte Rolle",
    "regel": "Regel",
    "ansicht": "Ansicht",
    "feld_id": "Feld-Kennung",
    "bedingung_knoten": "Bedingung (strukturiert)",
    "bedingung_parameter": "Bedingung: Parameter-Vergleich",
    "bedingung_termin_nr": "Bedingung: Termin-Nummer (jeder n-te)",
    "variante": "Variante",
    "variante_objekt": "Variante (Objektform)",
    "teil": "Teil",
    "teil_objekt": "Teil (Objektform)",
    "terminreihe": "Terminreihe",
    "abgeleitet": "Abgeleitete Termine",
    "ablauf_element": "Ablauf-Element",
    "fremd_feld": "Fremdes Feld (planuebergreifend)",
    "uebernahme": "Uebernahme (aus anderem Plan)",
}


def _liste_props(schema: dict[str, Any], erforderlich: list[str]) -> str:
    """Beschreibt die Eigenschaften eines Objekt-Schemas als Aufzaehlung."""
    props = _properties(schema)
    zeilen = []
    for name, prop in props.items():
        pflicht = " (Pflicht)" if name in (erforderlich or []) else ""
        zeilen.append(f"- {_beschreibe_prop(prop, name)}{pflicht}")
    return "\n".join(zeilen)


def _feldarten_tabelle() -> str:
    zeilen = ["| art | Bedeutung | Beispiele |", "|---|---|---|"]
    for f in FELDARTEN:
        beispiele = ", ".join(f.beispiele) if f.beispiele else "—"
        zeilen.append(f"| `{f.schluessel}` | {f.bedeutung} | {beispiele} |")
    return "\n".join(zeilen)


def _strategien_tabelle() -> str:
    zeilen = ["| strategie | Wirkung | Beispiel |", "|---|---|---|"]
    for s in FUELLSTRATEGIEN:
        zeilen.append(f"| `{s.schluessel}` | {s.wirkung} | {s.beispiel} |")
    return "\n".join(zeilen)


def _feiertage_tabelle() -> str:
    zeilen = ["| Schluessel | Name | Art |", "|---|---|---|"]
    for f in FEIERTAGE:
        zeilen.append(f"| `{f.schluessel}` | {f.name} | {f.art} |")
    return "\n".join(zeilen)


def _attribute_abschnitt() -> str:
    """Eingebaute Attribute (immer vorhanden, brauchen keine Deklaration)."""

    def zeilen(d: dict[str, str], titel: str) -> str:
        rows = [f"**{titel}** (immer vorhanden, brauchen keine Merkmal-Deklaration):", ""]
        for schluessel, bedeutung in d.items():
            rows.append(f"- `{schluessel}` — {bedeutung}")
        return "\n".join(rows)

    teile = [
        zeilen(PERSON_ATTRIBUTE, "Person"),
        "",
        zeilen(LIEDER_ATTRIBUTE, "Sammlung `lieder` (Psalmos-Liedgut)"),
        "",
        zeilen(SAMMLUNG_ATTRIBUTE, "Jede Sammlung (Lieder und eigene)"),
    ]
    return "\n".join(teile)


def _meldungs_codes_abschnitt() -> str:
    """Jeder Meldungscode mit einem HTML-Anker, auf den `doku_anker` zeigt.

    Die Pruefung (`pruefe_plantyp`) setzt `doku_anker` auf `meldung-<code>`; dieser
    Abschnitt erzeugt zu jedem Code einen Anker `<a id="meldung-<code>">`, damit
    kein Hinweis ins Leere verweist (Konzept P10). Ein Test prueft, dass jeder
    Code hier einen Anker hat.
    """
    zeilen: list[str] = []
    for code in sorted(MELDUNGS_CODES):
        beschr = MELDUNGS_CODES[code]
        zeilen.append(f"- `<a id=\"meldung-{code}\"></a>` `{code}` — {beschr}")
    return "\n".join(zeilen)


def _baustein_abschnitt(b: Any) -> str:
    """Markdown-Abschnitt fuer einen Regel-Baustein (mit Parameter-Schema)."""
    props = b.parameter_schema.get("properties", {}) or {}
    params = []
    for name, pschema in props.items():
        pflicht = " (Pflicht)" if name in (b.parameter_schema.get("required") or []) else ""
        beschr = pschema.get("description", "")
        params.append(f"`{name}`{pflicht}: {beschr}")
    param_text = "\n".join(f"- {p}" for p in params) if params else "- (keine Parameter)"
    beispiel = json.dumps(b.beispiel, ensure_ascii=False, indent=2)
    return (
        f"### `{b.schluessel}`\n\n"
        f"{b.kurz}\n\n"
        f"{b.doku}\n\n"
        f"**Parameter:**\n\n{param_text}\n\n"
        f"**Beispiel:**\n\n```json\n{beispiel}\n```\n"
    )


def erzeuge_referenz() -> str:
    """Erzeugt den vollstaendigen REFERENZ.md-Text (einheitlich, deterministisch)."""
    schema = ressourcen.schema_daten()
    top = _properties(schema)
    erforderlich_top = schema.get("required", [])

    teile: list[str] = []
    teile.append("# Plantyp-Referenz (Version 1)\n")
    teile.append(
        "**Automatisch erzeugt aus `schema/plantyp-1.json` und der "
        "Baustein-Registry — nicht von Hand aendern.** Jede Eigenschaft des "
        "Schemas ist hier aufgefuehrt, dazu die Regel-Bausteine, Feldarten, "
        "Fuellstrategien und der Feiertags-Katalog. Der Einstieg fuer "
        "Menschen ist `LEITFADEN.md`, das Kochen nach Beispielen im "
        "`KOCHBUCH.md`.\n"
    )

    # ---- Oberebene ----------------------------------------------------------
    teile.append(_ueber("Datei (oberste Ebene)", _liste_props(schema, erforderlich_top)))

    # ---- Unter-Strukturen ($defs) ------------------------------------------
    defs = schema.get("$defs", {})
    abschnitte: list[tuple[str, str]] = [
        ("Parameter", "parameter"),
        ("Merkmale", "merkmal"),
        ("Sammlung", "sammlung"),
        ("Termine", "termine"),
        ("Manueller Termin", "manueller_termin"),
        ("Ausnahme", "ausnahme"),
        ("Anlass", "anlass"),
        ("Wirkung (eines Anlasses)", "wirkung"),
        ("Feld (rekursiv)", "feld"),
        ("Rollen-Filter", "rollen_knoten"),
        ("Benannte Rolle", "benannte_rolle"),
        ("Bedingung (strukturiert)", "bedingung_knoten"),
        ("Bedingung: Parameter-Vergleich", "bedingung_parameter"),
        ("Bedingung: Termin-Nummer", "bedingung_termin_nr"),
        ("Variante", "variante"),
        ("Variante (Objektform)", "variante_objekt"),
        ("Teil", "teil"),
        ("Teil (Objektform)", "teil_objekt"),
        ("Terminreihe", "terminreihe"),
        ("Abgeleitete Termine", "abgeleitet"),
        ("Ablauf-Element", "ablauf_element"),
        ("Fremdes Feld (planuebergreifend)", "fremd_feld"),
        ("Uebernahme (aus anderem Plan)", "uebernahme"),
        ("Regel", "regel"),
        ("Ansicht", "ansicht"),
        ("Feld-Kennung", "feld_id"),
    ]
    for titel, schluessel in abschnitte:
        if schluessel in defs:
            sub = defs[schluessel]
            teile.append(_ueber(titel, _liste_props(sub, sub.get("required", []))))

    # ---- eingebaute Attribute ---------------------------------------------
    teile.append(_ueber("Eingebaute Attribute (Stammdaten)", _attribute_abschnitt()))

    # ---- Meldungs-Codes (jeder Code mit Anker) ---------------------------
    teile.append(_ueber("Meldungs-Codes", _meldungs_codes_abschnitt()))

    # ---- Feldarten ----------------------------------------------------------
    teile.append(_ueber("Feldarten (B3)", _feldarten_tabelle()))

    # ---- Fuellstrategien ----------------------------------------------------
    teile.append(_ueber("Fuellstrategien (B7)", _strategien_tabelle()))

    # ---- Feiertage ----------------------------------------------------------
    teile.append(_ueber("Feiertage (Katalog)", _feiertage_tabelle()))

    # ---- Regel-Bausteine ----------------------------------------------------
    baustein_teile = ["\n## Regel-Bausteine (B8)\n"]
    baustein_teile.append(
        "Jeder Baustein hat eine Stufe (`muss`/`sollte`/`hinweis`) und optional "
        "ein `gewicht`. Die unten genannten Parameter werden gegen die "
        "Registry geprueft — neue Bausteine kommen in der Registry hinzu, "
        "ohne das Hierarchie-Schema zu brechen.\n"
    )
    for b in REGEL_BAUSTEINE:
        baustein_teile.append(_baustein_abschnitt(b))
    teile.append("\n".join(baustein_teile))

    return "\n".join(teile) + "\n"


__all__ = ["erzeuge_referenz"]
