"""Struktur-Pruefung von Plan-Instanzdaten (Eintraege) gegen einen Plantyp.

Der Plantyp beschreibt die *Struktur*; der konkrete Plan haelt *Eintraege*, die
diese Struktur fuellen. Dieses Modul prueft, dass eine Liste von Eintraegen zu
einem Plantyp *strukturell passt*: jeder Eintrag nennt einen aufloesbaren
``feld_pfad`` und einen ``wert`` mit erkannter ``art``.

Das ist die Gegenstelle zur Plantyp-Pruefung (``pruefung.py``): dort wird die
Datei des *Typs* geprueft, hier die Instanzdaten (Konzept P2: Struktur und
Daten sind getrennt). Bewusst schlank — es werden nur Feldpfade und Wertarten
abgeglichen, keine Regeln, keine Fuellstrategien (das kommt mit der Engine).

Der ``feld_pfad`` folgt dem ueblichen Punkt-Format (``frohe_stunde.leitung``);
fuer Ablauf-Elemente gilt die Element-ID-Form ``ablauf/<element_id>.<innerfeld>``
(dokumentiert im LEITFADEN) — die Element-ID ist eine opaque Laufzeit-Kennung,
die hier nur als ein Segment zwischen ``/`` und ``.`` erkannt, aber nicht
inhaltsgeprueft wird.
"""

from __future__ import annotations

from typing import Any


def _felder_ebene(felder: Any) -> list[dict[str, Any]]:
    """Nur die Objekt-Eintraege einer Feldliste."""
    return [f for f in (felder or []) if isinstance(f, dict)]


def _alle_feld_iden(plantyp: dict[str, Any]) -> set[str]:
    """Alle Feld-Kennungen ueber den gesamten Baum (oberste felder + terminreihen)."""
    result: set[str] = set()

    def sammle(felder: Any) -> None:
        for f in _felder_ebene(felder):
            fid = f.get("id")
            if isinstance(fid, str):
                result.add(fid)
            inhalt = f.get("inhalt")
            if isinstance(inhalt, list):
                sammle(inhalt)
            for elem in _felder_ebene(f.get("elemente")):
                if isinstance(elem.get("inhalt"), list):
                    sammle(elem["inhalt"])

    if isinstance(plantyp.get("felder"), list):
        sammle(plantyp["felder"])
    for reihe in _felder_ebene(plantyp.get("terminreihen")):
        if isinstance(reihe.get("felder"), list):
            sammle(reihe["felder"])
    return result


def _ablauf_innerfelder_und_typen(plantyp: dict[str, Any]) -> tuple[set[str], set[str]]:
    """Sammelt (innerfelder, elementtypen) aller 'ablauf'-Felder des Plantyps."""
    innerfelder: set[str] = set()
    typen: set[str] = set()

    def sammle(felder: Any) -> None:
        for f in _felder_ebene(felder):
            if f.get("art") == "ablauf":
                for elem in _felder_ebene(f.get("elemente")):
                    typ = elem.get("typ")
                    if isinstance(typ, str):
                        typen.add(typ)
                    for inner in _felder_ebene(elem.get("inhalt")):
                        fid = inner.get("id")
                        if isinstance(fid, str):
                            innerfelder.add(fid)
            inhalt = f.get("inhalt")
            if isinstance(inhalt, list):
                sammle(inhalt)

    if isinstance(plantyp.get("felder"), list):
        sammle(plantyp["felder"])
    for reihe in _felder_ebene(plantyp.get("terminreihen")):
        if isinstance(reihe.get("felder"), list):
            sammle(reihe["felder"])
    return innerfelder, typen


# Erkannnte Wert-Arten (der `wert` eines Eintrags traegt eine dieser `art`).
# Entspricht den Feldarten, die fuer einzelne Werte gueltig sind.
_WERT_ARTEN = {
    "person", "personen", "eintrag", "text", "zahl", "datum", "auswahl", "team",
}


def eintraege_pruefen(plantyp: dict[str, Any], eintraege: list[dict[str, Any]]) -> list[str]:
    """Prueft eine Liste von Eintraegen strukturell gegen einen Plantyp.

    Liefert eine (ggf. leere) Liste deutscher Fehlermeldungen, je eine pro
    fehlerhaftem Eintrag, mit Index und Grund. Keine Exception — die Meldungen
    sind (wie bei der Plantyp-Pruefung) darauf ausgelegt, dass ein Agent oder
    Mensch sich selbst korrigiert (P10).

    Geprueft wird je Eintrag:
    * ``feld_pfad`` ist ein String und der erste Abschnitt nennt eine bekannte
      Feld-Kennung (bei Ablauf-Elementen: 'ablauf/<element_id>.<innerfeld>' mit
      einem deklarierten Innerfeld);
    * ``wert`` ist ein Objekt mit einer erkannten ``art``.
    """
    if not isinstance(plantyp, dict):
        return ["Der Plantyp ist kein Objekt."]
    if not isinstance(eintraege, list):
        return ["Die Eintraege sind keine Liste."]

    feld_iden = _alle_feld_iden(plantyp)
    innerfelder, elementtypen = _ablauf_innerfelder_und_typen(plantyp)
    fehler: list[str] = []

    for idx, eintrag in enumerate(eintraege):
        if not isinstance(eintrag, dict):
            fehler.append(f"Eintrag {idx}: kein Objekt.")
            continue
        pfad = eintrag.get("feld_pfad")
        if not isinstance(pfad, str) or not pfad:
            fehler.append(f"Eintrag {idx}: 'feld_pfad' fehlt oder ist kein String.")
            continue
        kopf = pfad.split(".")[0].split("/")[0]
        if kopf not in feld_iden:
            vorschlag = _tipp(kopf, feld_iden)
            zusatz = f" (meinst du {vorschlag!r}?)" if vorschlag else ""
            fehler.append(f"Eintrag {idx}: Feld {kopf!r} ist nicht deklariert.{zusatz}")
            continue
        # Ablauf-Elementpfad 'ablauf/<element_id>.<innerfeld>'?
        if "/" in pfad and not pfad.split("/")[0].startswith("ablauf"):
            fehler.append(f"Eintrag {idx}: Pfad {pfad!r} enthaelt '/', aber nur 'ablauf/<element_id>.<feld>' ist erlaubt.")
            continue
        if "/" in pfad:
            inner = pfad.split(".", 1)[1] if "." in pfad else ""
            if inner and inner not in innerfelder and inner.split(".")[0] not in innerfelder:
                vorschlag = _tipp(inner.split(".")[0], innerfelder)
                zusatz = f" (meinst du {vorschlag!r}?)" if vorschlag else ""
                fehler.append(f"Eintrag {idx}: Innerfeld {inner.split('.')[0]!r} ist in keinem Ablauf-Element deklariert.{zusatz}")
                continue
        wert = eintrag.get("wert")
        if not isinstance(wert, dict) or wert.get("art") not in _WERT_ARTEN:
            fehler.append(f"Eintrag {idx}: 'wert' traegt keine erkannte 'art' ({', '.join(sorted(_WERT_ARTEN))}).")

    return fehler


def _tipp(wert: str, kandidaten: set[str]) -> str | None:
    """Bester aehnlicher Vorschlag (difflib), None bei zu grosser Distanz."""
    import difflib

    nahe = difflib.get_close_matches(wert, sorted(kandidaten), n=1, cutoff=0.6)
    return nahe[0] if nahe else None


# --------------------------------------------------------------------------- #
# Katalogwerte: die Strukturpruefung oben kennt nur Pfade und Wertarten. Ein
# 'auswahl'-Feld traegt aber eine geschlossene Werteliste im Plantyp; ein Wert
# ausserhalb dieser Liste ist ein Datenfehler, den `eintraege_pruefen` nicht
# sieht (Nachtpruefung P3-1, W3: die Instanz trug weiter „Maennerchor“, der
# Katalog heisst „Männerchor“).
# --------------------------------------------------------------------------- #

# Innerfelder eines Ablauf-Elements, deren Wert ein Objekt mit den Angaben des
# Elements ist (``wert`` der Instanz), z. B. ``ablauf/l1.lied``.
def _katalog_je_pfad(plantyp: dict[str, Any]) -> dict[str, set[str]]:
    """Alle geschlossenen Wertelisten des Plantyps: ``pfad -> {werte}``.

    Schluessel sind die Feldpfade, wie sie ein Eintrag nennt — top-level
    (``feld.innerfeld``) und fuer Ablauf-Elemente
    (``ablauf/<element_id>.<innerfeld>``, hier als ``ablauf.*.<innerfeld>``).
    """
    katalog: dict[str, set[str]] = {}

    def merke(pfad: str, feld: dict[str, Any]) -> None:
        if feld.get("art") != "auswahl":
            return
        werte = feld.get("werte")
        if isinstance(werte, list) and werte:
            katalog.setdefault(pfad, set()).update(str(w) for w in werte)

    def sammle(felder: Any, prefix: str = "") -> None:
        for f in _felder_ebene(felder):
            fid = f.get("id")
            pfad = f"{prefix}{fid}" if isinstance(fid, str) else None
            if pfad:
                merke(pfad, f)
            sammle(f.get("inhalt"), f"{pfad}." if pfad else prefix)

    sammle(plantyp.get("felder"))
    for reihe in _felder_ebene(plantyp.get("terminreihen")):
        sammle(reihe.get("felder"), "terminreihe.*.")

    for feld in _felder_ebene(plantyp.get("felder")):
        if feld.get("art") != "ablauf":
            continue
        for element in _felder_ebene(feld.get("elemente")):
            typ = element.get("typ")
            for inneres in _felder_ebene(element.get("inhalt")):
                iid = inneres.get("id")
                if not isinstance(iid, str):
                    continue
                if isinstance(typ, str):
                    merke(f"ablauf.*.{typ}.{iid}", inneres)
                merke(f"ablauf.*.{iid}", inneres)
    return katalog


def _werte_im_eintrag(wert: Any, feld_id: str) -> list[str]:
    """Die gespeicherten Auswahlwerte zu ``feld_id`` aus dem ``wert``-Objekt."""
    if not isinstance(wert, dict):
        return []
    roh = wert.get(feld_id)
    if roh is None:
        return []
    if isinstance(roh, str):
        return [roh]
    if isinstance(roh, list):
        return [str(w) for w in roh if isinstance(w, (str, int, float))]
    return []


def katalogwerte_pruefen(plantyp: dict[str, Any], eintraege: list[dict[str, Any]]) -> list[str]:
    """Prueft die gespeicherten Auswahlwerte einer Instanz gegen den Plantyp.

    Liefert (ggf. leere) deutsche Fehlermeldungen. Geprueft wird nur, was im
    Plantyp eine geschlossene Werteliste hat; freie Texte bleiben unberuehrt.

    Ein Eintrag traegt im ``wert``-Objekt die Angaben des *Elements*
    (z. B. ``ablauf/l7.lied`` mit ``ensemble``, ``begleitung``, ``titel``) —
    deshalb werden alle Auswahlfelder des genannten Elements geprueft, nicht
    nur das Feld im Pfad.
    """
    if not isinstance(plantyp, dict) or not isinstance(eintraege, list):
        return []
    katalog = _katalog_je_pfad(plantyp)
    if not katalog:
        return []
    fehler: list[str] = []
    for idx, eintrag in enumerate(eintraege):
        if not isinstance(eintrag, dict):
            continue
        pfad = eintrag.get("feld_pfad")
        if not isinstance(pfad, str) or "." not in pfad:
            continue
        # Ablauf-Elemente: 'ablauf/<element_id>.<innerfeld>' — der erste
        # Abschnitt ist 'ablauf/<element_id>', nicht ein Feldpfad.
        if pfad.startswith("ablauf/"):
            inner = pfad.split(".", 1)[1]
            elem_typ = eintrag.get("typ")
            praefixe: list[str] = []
            if isinstance(elem_typ, str):
                praefixe.append(f"ablauf.*.{elem_typ}.")
            praefixe.append("ablauf.*.")
        else:
            kopf, inner = pfad.split(".", 1)
            praefixe = [f"{kopf}."]
        # Fachliche Felder: die Auswahlfelder, die zu diesem Pfad passen.
        felder = {
            m.rsplit(".", 1)[-1]
            for m in katalog
            if any(m.startswith(p) for p in praefixe)
        }
        # Die Innerfeld-Kennung des Pfads gilt zusaetzlich (falls sie anders
        # heisst als das Auswahlfeld, z. B. 'ablauf/l1.beginnt').
        felder.add(inner)
        gesehen: set[str] = set()
        for feld_id in sorted(felder):
            for wert in _werte_im_eintrag(eintrag.get("wert"), feld_id):
                erlaubt = next(
                    (katalog[m] for m in sorted(katalog)
                     if m.rsplit(".", 1)[-1] == feld_id
                     and any(m.startswith(p) for p in praefixe)),
                    None,
                )
                if not erlaubt or wert in erlaubt:
                    continue
                schluessel = f"{feld_id}={wert}"
                if schluessel in gesehen:
                    continue
                gesehen.add(schluessel)
                vorschlag = _tipp(wert, erlaubt)
                zusatz = f" (meinst du {vorschlag!r}?)" if vorschlag else ""
                fehler.append(
                    f"Eintrag {idx}: Auswahlwert {wert!r} in {pfad!r} steht nicht im "
                    f"Katalog des Plantyps{zusatz}",
                )
    return fehler
