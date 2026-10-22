"""Feldbaum-Aufloesung: Plantyp-Felder -> flache Liste von Slots (B3).

`aufloesen` nimmt den Feldbaum eines Plantyps (mit Anlass-Wirkungen) und einen
Termin und erzeugt die flache Liste der zu planenden **Slots**, jeder mit einem
*stabilen* Feld-Pfad. Pfad-Format (dokumentiert im LEITFADEN):

- ``lieder[0].dirigent``  — anzahl-Instanz (Index ab 0),
- ``abend@regen#programm.leitung`` — Variante (``@``) vor Teil (``#``),
- ``gottesdienst:team`` — Reihen-Praefix (bei ``terminreihen``),
- ``ablauf/<element_id>.<feld`` — Ablauf-Element (variable Liste, keine festen
  Slots; siehe unten).

Regeln:

- ``anzahl`` n (fest) erzeugt n Instanzen ``feld[i]``; ein Bereich ``min..max``
  erzeugt den *Pflicht*-Umfang `min` (der Generator kann auf `max` erweitern) —
  ein offenes Ende ``1..*`` (Ablauf) wird als variable Elementliste behandelt.
- ``varianten`` (``@sonne``, ``@regen``) erzeugen je Variante einen eigenen
  Unterbaum; ohne eigenes ``inhalt`` gilt das der Gruppe.
- ``teile`` (``#programm``, ``#abschluss``) ebenso (nacheinander, aber eigene
  Pfade).
- ``bedingung`` (strukturiert) blendet ein Feld aus, wenn sie nicht zutrifft.
- Anlass-Wirkung ``ohne`` blendet Felder der Oberebene aus, ``mit`` fuegt hinzu.
- ``ablauf``-Felder erzeugen KEINE festen Slots, sondern eine geordnete,
  frei sortierbare Elementliste (siehe ``ablauf_elemente``). Die Nummerierung
  eines nummerierten Typs wird berechnet, nicht gespeichert.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Callable

from .modell import Eintrag, Slot, Termin
from .pfade import feld_bezug_passt


# --------------------------------------------------------------------------- #
# Bedingung (vollstaendig, mit variante/parameter/feld_gesetzt)
# --------------------------------------------------------------------------- #


def feld_abhaengigkeiten(bedingung: Any) -> set[str]:
    """Alle Feldbezuege einer Bedingung, auch unter Negation/Verknuepfungen."""
    if not isinstance(bedingung, dict):
        return set()
    result = {bedingung["feld_gesetzt"]} if "feld_gesetzt" in bedingung else set()
    for schluessel in ("alle", "eine"):
        for kind in bedingung.get(schluessel, []):
            result |= feld_abhaengigkeiten(kind)
    return result | feld_abhaengigkeiten(bedingung.get("nicht"))


def bedingung_erfuellt(
    bedingung: Any,
    termin: Termin,
    *,
    parameter: dict[str, Any] | None = None,
    variante: str | None = None,
    feld_gesetzt: Callable[[str], bool] | None = None,
    feld_bereit: Callable[[str], bool] | None = None,
) -> bool:
    """Wertet eine strukturierte Bedingung vollstaendig aus.

    ``parameter`` liefert Plan-Parameterwerte (bedingung.parameter).
    ``variante`` ist die aktive Variante (bedingung.variante).
    ``feld_gesetzt(pfad)`` prueft, ob ein Feld(-pfad) bereits gefuellt ist.
    ``feld_bereit`` verschiebt Feldbezuege bis zum Fuellversuch der Quelle;
    insbesondere darf eine Negation nicht einen noch ausstehenden Wert nutzen.
    """
    if not isinstance(bedingung, dict) or not bedingung:
        return True
    if feld_bereit and not all(feld_bereit(p) for p in feld_abhaengigkeiten(bedingung)):
        return False
    for schluessel, wert in bedingung.items():
        if schluessel == "alle":
            return all(
                bedingung_erfuellt(k, termin, parameter=parameter, variante=variante, feld_gesetzt=feld_gesetzt)
                for k in (wert or [])
            )
        if schluessel == "eine":
            return any(
                bedingung_erfuellt(k, termin, parameter=parameter, variante=variante, feld_gesetzt=feld_gesetzt)
                for k in (wert or [])
            )
        if schluessel == "nicht":
            return not bedingung_erfuellt(wert, termin, parameter=parameter, variante=variante, feld_gesetzt=feld_gesetzt)
        if schluessel == "anlass":
            return wert in termin.anlaesse
        if schluessel == "wochentag":
            wd = ("mo", "di", "mi", "do", "fr", "sa", "so")[termin.datum.weekday()]
            return wd in (wert or [])
        if schluessel == "datum_ab":
            d = _datum(wert)
            return d is None or termin.datum >= d
        if schluessel == "datum_bis":
            d = _datum(wert)
            return d is None or termin.datum <= d
        if schluessel == "termin_nr":
            jede = (wert or {}).get("jede")
            return bool(jede) and termin.index % jede == 0
        if schluessel == "termin_im_monat":
            return (termin.positionsnr_im_monat if wert > 0 else termin.position_von_hinten) == abs(wert)
        if schluessel == "variante":
            return variante == wert
        if schluessel == "parameter":
            knoten = wert or {}
            pid = knoten.get("id")
            gleich = knoten.get("gleich")
            if parameter is None or pid not in parameter:
                return gleich is None
            return parameter[pid] == gleich
        if schluessel == "feld_gesetzt":
            if feld_gesetzt is None:
                return False
            return feld_gesetzt(wert)
    return True


def _datum(wert: Any) -> date | None:
    if isinstance(wert, datetime):
        return wert.date()
    if isinstance(wert, date):
        return wert
    if isinstance(wert, str):
        try:
            return date.fromisoformat(wert.strip())
        except ValueError:
            return None
    return None


# --------------------------------------------------------------------------- #
# Ablauf-Elemente (variable Liste)
# --------------------------------------------------------------------------- #


def ablauf_elemente(plantyp: dict[str, Any], termin: Termin) -> list[dict[str, Any]]:
    """Konkrete manuelle Elementliste mit abgeleiteter Nummer je Elementtyp.

    ``Termin.ablauf`` ordnet einem Feldpfad eine Liste ``{id, typ}`` zu.
    Reihenfolge und IDs werden niemals vom Generator angelegt oder veraendert.
    """
    result: list[dict[str, Any]] = []
    def sammle(felder: list[Any]) -> None:
        for f in _objekte(felder):
            if f.get("art") == "ablauf":
                typen = {e["typ"]: e for e in _objekte(f.get("elemente"))}
                nummern: dict[str, int] = {}
                for pfad, elemente in termin.ablauf.items():
                    if pfad.split(":")[-1].split(".")[-1] != f["id"]:
                        continue
                    for e in elemente:
                        typ = typen.get(e["typ"])
                        if typ is None:
                            raise ValueError(f"Unbekannter Elementtyp {e['typ']!r} in {pfad}.")
                        neu = dict(e, feld_pfad=pfad)
                        if typ.get("nummeriert"):
                            nummern[e["typ"]] = nummern.get(e["typ"], 0) + 1
                            neu["nr"] = nummern[e["typ"]]
                        result.append(neu)
            sammle(f.get("inhalt") or [])
            for zweig in _objekte(f.get("varianten")) + _objekte(f.get("teile")):
                sammle(zweig.get("inhalt") or [])
    felder, _ = _wirksame_felder(plantyp, termin)
    sammle(felder)
    return result


# --------------------------------------------------------------------------- #
# Kern: Baum -> Slots
# --------------------------------------------------------------------------- #


def aufloesen(
    plantyp: dict[str, Any],
    termin: Termin,
    *,
    parameter: dict[str, Any] | None = None,
    feld_gesetzt: Callable[[str], bool] | None = None,
    feld_bereit: Callable[[str], bool] | None = None,
    bestehende_eintraege: list[Any] | None = None,
    inaktive_felder: set[str] | None = None,
    offene_felder: set[str] | None = None,
    ablauf_typen: dict[str, str] | None = None,
    sammlungsquellen: set[str] | None = None,
    fuellumfang: dict[str, int] | None = None,
) -> list[Slot]:
    """Erzeugt die flache Slot-Liste fuer einen Termin.

    ``inaktive_felder`` sammelt sicher ausgeblendete Pfade/Unterbaeume fuer
    den Generator. Noch ungeklaerte Feldbedingungen werden nicht als inaktiv
    markiert; ``offene_felder`` haelt ihre Unterbaeume bis zur Klaerung offen.
    ``ablauf_typen`` sammelt die tatsaechliche ID-zu-Typ-Zuordnung, einschliesslich
    eindeutiger Inferenz aus flachen Daten, ohne ``Termin.ablauf`` zu veraendern.
    ``sammlungsquellen`` sammelt deklarierte Wertepfade vor ihrer Bedingung,
    damit Vorbelegung auch auf noch nicht aktive Eintrag-Geschwister wartet.
    """
    slots: list[Slot] = []
    inaktive_felder = inaktive_felder if inaktive_felder is not None else set()
    parameter = parameter or {}
    ablauf_typen = ablauf_typen if ablauf_typen is not None else {}
    offene_felder = offene_felder if offene_felder is not None else set()

    felder, reihen_praefix = _wirksame_felder(plantyp, termin)
    geblendet: set[str] = _geblendete_felder(plantyp, termin)
    for anlass in _reihen_anlaesse(plantyp, termin.reihe):
        if anlass.get("id") in termin.anlaesse and bedingung_erfuellt(anlass.get("bedingung"), termin, parameter=parameter, feld_gesetzt=feld_gesetzt, feld_bereit=feld_bereit):
            felder = list(felder) + _objekte((anlass.get("wirkung") or {}).get("mit"))

    def feld_ist_gesetzt(pfad: str) -> bool:
        return bool(feld_gesetzt and feld_gesetzt(pfad))

    def instanzenzahl(feld: dict[str, Any], basis: str) -> int:
        """Optionale Plaetze nur nach Bedarf oder vorhandenen Werten entfalten."""
        anzahl = feld.get("anzahl")
        minimum = _instanzenzahl(feld)
        if not isinstance(anzahl, str) or ".." not in anzahl:
            return minimum
        import re
        vorhanden = max((int(m[1]) + 1 for e in bestehende_eintraege or []
                         if e.termin is termin and (m := re.match(re.escape(basis) + r"\[(\d+)\]", e.feld_pfad))), default=0)
        gewuenscht = max([n for pfad, n in (fuellumfang or {}).items()
                         if feld_bezug_passt(basis, pfad, termin)] + [vorhanden, minimum])
        obergrenze = anzahl.split("..", 1)[1]
        return min(gewuenscht, int(obergrenze)) if obergrenze.isdigit() else gewuenscht

    # ``entfalte`` liefert die Slots eines Unterbaums relativ zu ``pfad``.
    def entfalte(felder_liste: list[Any], pfad: str, sammlung_kontext: str | None) -> None:
        for f in _objekte(felder_liste):
            fid = f.get("id")
            art = f.get("art")
            if not isinstance(fid, str):
                continue
            basis = _join(pfad, fid)
            # Wertequellen auch vor ihrer Bedingungsentscheidung deklarieren.
            # Ihr Unterbaum darf den Verbraucher selbst enthalten und muss
            # deshalb nicht vollstaendig bearbeitet sein.
            if art == "eintrag" and sammlungsquellen is not None:
                for i in range(instanzenzahl(f, basis)):
                    sammlungsquellen.add(f"{basis}[{i}]" if "anzahl" in f else basis)

            # Anlass-Wirkung 'ohne' nur auf der Oberebene (pfad leer, kein
            # index-/varianten-/teil-Anteil).
            if pfad in ("", f"{reihen_praefix}:") and fid in geblendet:
                inaktive_felder.add(basis)
                continue

            # Bedingung des Felds.
            if not bedingung_erfuellt(
                f.get("bedingung"), termin, parameter=parameter,
                variante=pfad.rsplit("@", 1)[1].split("#")[0].split(".")[0] if "@" in pfad else None,
                feld_gesetzt=feld_ist_gesetzt, feld_bereit=feld_bereit,
            ):
                if feld_bereit is None or all(feld_bereit(p) for p in feld_abhaengigkeiten(f.get("bedingung"))):
                    inaktive_felder.add(basis)
                else:
                    offene_felder.add(basis)
                continue

            if art != "ablauf" and instanzenzahl(f, basis) == 0:
                inaktive_felder.add(basis)
                continue

            if art == "ablauf":
                typen = _objekte(f.get("elemente"))
                elemente = list(termin.ablauf.get(basis, []))
                if not elemente:
                    # Bestehende flache Daten ohne Metadaten: Typ nur bei
                    # eindeutigem Innerfeld ableiten, niemals aus der ID raten.
                    gefunden: dict[str, str] = {}
                    for e in bestehende_eintraege or []:
                        if e.termin is not termin or not e.feld_pfad.startswith(basis + "/"):
                            continue
                        rest = e.feld_pfad[len(basis) + 1:]
                        eid, _, inner = rest.partition(".")
                        passend = [typ for typ in typen if inner.split(".")[0] in {kind.get("id") for kind in _objekte(typ.get("inhalt"))}]
                        if len(passend) == 1:
                            gefunden[eid] = passend[0]["typ"]
                    elemente = [{"id": eid, "typ": typ} for eid, typ in gefunden.items()]
                if not elemente:
                    inaktive_felder.add(basis)
                for typ in typen:
                    if not any(e["typ"] == typ["typ"] for e in elemente):
                        inaktive_felder.add(f"{basis}.{typ['typ']}")
                for element in elemente:
                    ablauf_typen[f"{basis}/{element['id']}"] = f"{basis}.{element['typ']}"
                for element in elemente:
                    typ = next((typ for typ in typen if typ["typ"] == element["typ"]), None)
                    if typ is None:
                        raise ValueError(f"Unbekannter Ablauf-Typ {element['typ']!r}.")
                    if bedingung_erfuellt(typ.get("bedingung"), termin, parameter=parameter, feld_gesetzt=feld_ist_gesetzt, feld_bereit=feld_bereit):
                        inhalt = _objekte(typ.get("inhalt"))
                        sammlungen = [kind.get("sammlung") for kind in inhalt if kind.get("art") == "eintrag"]
                        entfalte(inhalt, f"{basis}/{element['id']}", sammlungen[0] if len(sammlungen) == 1 else None)
                    elif feld_bereit is None or all(feld_bereit(p) for p in feld_abhaengigkeiten(typ.get("bedingung"))):
                        inaktive_felder.add(f"{basis}/{element['id']}")
                    else:
                        offene_felder.add(f"{basis}/{element['id']}")
                continue

            inhalt = f.get("inhalt")
            hat_unterfelder = isinstance(inhalt, list) and bool(_objekte(inhalt))

            if art == "gruppe":
                # Reiner Container: varianten/teile verzweigen, sonst sich selbst.
                instanzen = instanzenzahl(f, basis)
                for i in range(instanzen):
                    inst_pfad = f"{basis}[{i}]" if "anzahl" in f else basis
                    _entfalte_container(f, inst_pfad, inhalt or [], entfalte, termin, parameter,
                                        feld_ist_gesetzt, sammlung_kontext, feld_bereit, inaktive_felder, offene_felder)
                continue

            if art == "eintrag":
                # Eintrag traegt seinen eigenen Wert-Slot UND ggf. Unterfelder.
                instanzen = instanzenzahl(f, basis)
                for i in range(instanzen):
                    inst_pfad = f"{basis}[{i}]" if "anzahl" in f else basis
                    slots.append(_baue_slot(f, inst_pfad, i, instanzen, sammlung_kontext, parameter, force_art="eintrag"))
                    if hat_unterfelder:
                        eigene_sammlung = f.get("sammlung")
                        # Unterfelder eines eintrag erben dessen Sammlung
                        # (fuer aus='eintrag.<merkmal>').
                        for kind in _objekte(inhalt):
                            entfalte([kind], inst_pfad, eigene_sammlung if isinstance(eigene_sammlung, str) else sammlung_kontext)
                continue

            # Blatt-Felder (person/personen/team/text/zahl/datum/auswahl).
            instanzen = instanzenzahl(f, basis)
            for i in range(instanzen):
                inst_pfad = f"{basis}[{i}]" if "anzahl" in f else basis
                slots.append(_baue_slot(f, inst_pfad, i, instanzen, sammlung_kontext, parameter))

    entfalte(felder, f"{reihen_praefix}:" if reihen_praefix else "", None)
    return slots


def aufloesen_mit_eintraegen(
    plantyp: dict[str, Any], termin: Termin, eintraege: list[Eintrag],
    *, parameter: dict[str, Any] | None = None,
) -> list[Slot]:
    """Finalen Zustand mit derselben Ablauf-Typinferenz wie den Feldbaum lesen.

    Die aufruflokale Zuordnung wird bis zur Stabilitaet gesammelt: ein bedingter
    Ablauf kann weitere Typbezuege freigeben, ohne Termin-Metadaten zu veraendern.
    """
    ablauf_typen: dict[str, str] = {}
    while True:
        vorher = dict(ablauf_typen)
        slots = aufloesen(
            plantyp, termin, parameter=parameter, bestehende_eintraege=eintraege,
            ablauf_typen=ablauf_typen,
            feld_gesetzt=lambda pfad: any(
                e.termin is termin and e.wert is not None
                and feld_bezug_passt(e.feld_pfad, pfad, termin, unterfelder=True,
                                     ablauf_typen=ablauf_typen)
                for e in eintraege
            ),
        )
        if vorher == ablauf_typen:
            return slots


def _entfalte_container(
    f: dict[str, Any],
    basis: str,
    inhalt: list[Any],
    entfalte: Callable[..., None],
    termin: Termin,
    parameter: dict[str, Any],
    feld_ist_gesetzt: Callable[[str], bool],
    sammlung_kontext: str | None,
    feld_bereit: Callable[[str], bool] | None = None,
    inaktive_felder: set[str] | None = None,
    offene_felder: set[str] | None = None,
) -> None:
    """Verzweigt einen ``gruppe``-Container in Varianten und/oder Teile.

    Kombinatorik: Varianten (aeussere Ebene, ``@``) mal Teile (innere Ebene,
    ``#``). Ohne eigenes ``inhalt`` der Variante/des Teils gilt das der Gruppe.
    """
    vs = [v for v in f.get("varianten") or []]
    ts = [t for t in f.get("teile") or []]

    def inhalt_von(eintrag: Any, fallback: list[Any]) -> list[Any]:
        if isinstance(eintrag, dict) and isinstance(eintrag.get("inhalt"), list):
            return eintrag["inhalt"]
        return fallback

    def bedingung_ok(eintrag: Any, variante: str | None) -> bool:
        if isinstance(eintrag, dict) and eintrag.get("bedingung") is not None:
            return bedingung_erfuellt(
                eintrag["bedingung"], termin, parameter=parameter,
                variante=variante, feld_gesetzt=feld_ist_gesetzt, feld_bereit=feld_bereit,
            )
        return True

    def entfalte_teile(pfad: str, variante: str | None, inhalt_v: list[Any]) -> None:
        if ts:
            for t in ts:
                tid = t if isinstance(t, str) else t.get("id")
                t_inhalt = inhalt_von(t, inhalt_v) if isinstance(t, dict) else inhalt_v
                if not bedingung_ok(t, variante):
                    if isinstance(t, dict) and inaktive_felder is not None and (feld_bereit is None or all(feld_bereit(p) for p in feld_abhaengigkeiten(t.get("bedingung")))):
                        inaktive_felder.add(f"{pfad}#{tid}")
                    elif offene_felder is not None:
                        offene_felder.add(f"{pfad}#{tid}")
                    continue
                entfalte(t_inhalt, f"{pfad}#{tid}", sammlung_kontext)
        else:
            entfalte(inhalt_v, pfad, sammlung_kontext)

    if vs:
        gewaehlt = getattr(termin, "variante", None)
        for v in vs:
            vid = v if isinstance(v, str) else v.get("id")
            # OP-EVENT-18: Ist am Termin eine Variante festgelegt, gilt NUR
            # diese (die andere wird als inaktiv geführt — sie erscheint nicht
            # mehr als zweiter Unterbaum). Ohne Auswahl bleibt es beim
            # bisherigen Verhalten: alle Varianten werden erzeugt, die
            # Bedingung.variante der jeweiligen Variante entscheidet.
            if gewaehlt and vid != gewaehlt:
                if inaktive_felder is not None:
                    inaktive_felder.add(f"{basis}@{vid}")
                elif offene_felder is not None:
                    offene_felder.add(f"{basis}@{vid}")
                continue
            v_inhalt = inhalt_von(v, inhalt) if isinstance(v, dict) else inhalt
            if isinstance(v, dict) and v.get("bedingung") is not None and not bedingung_erfuellt(
                v["bedingung"], termin, parameter=parameter, variante=vid, feld_gesetzt=feld_ist_gesetzt, feld_bereit=feld_bereit
            ):
                if inaktive_felder is not None and (feld_bereit is None or all(feld_bereit(p) for p in feld_abhaengigkeiten(v.get("bedingung")))):
                    inaktive_felder.add(f"{basis}@{vid}")
                elif offene_felder is not None:
                    offene_felder.add(f"{basis}@{vid}")
                continue
            entfalte_teile(f"{basis}@{vid}", vid, v_inhalt)
    else:
        entfalte_teile(basis, None, inhalt)


# --------------------------------------------------------------------------- #
# Helfer
# --------------------------------------------------------------------------- #


def _objekte(items: Any) -> list[dict[str, Any]]:
    return [it for it in (items or []) if isinstance(it, dict)]


def _join(praefix: str, seg: str) -> str:
    # Reihen-Praefix endet auf ':'; dort direkt anhaengen, sonst mit '.'.
    if praefix.endswith(":"):
        return f"{praefix}{seg}"
    return f"{praefix}.{seg}" if praefix else seg


def _alle_feldlisten(plantyp: dict[str, Any]) -> list[list[Any]]:
    listen: list[list[Any]] = []
    if isinstance(plantyp.get("felder"), list):
        listen.append(plantyp["felder"])
    for reihe in _objekte(plantyp.get("terminreihen")):
        if isinstance(reihe.get("felder"), list):
            listen.append(reihe["felder"])
    return listen


def _reihen_anlaesse(plantyp: dict[str, Any], reihe: str) -> list[dict[str, Any]]:
    anlaesse = _objekte(plantyp.get("anlaesse"))
    for r in _objekte(plantyp.get("terminreihen")):
        if r.get("id") == reihe:
            anlaesse += _objekte(r.get("anlaesse"))
            break
    return anlaesse


def _wirksame_felder(plantyp: dict[str, Any], termin: Termin) -> tuple[list[Any], str | None]:
    if termin.reihe == "standard":
        return (plantyp.get("felder") or []), None
    for r in _objekte(plantyp.get("terminreihen")):
        if r.get("id") == termin.reihe:
            return (r.get("felder") or []), termin.reihe
    return [], None


def _geblendete_felder(plantyp: dict[str, Any], termin: Termin) -> set[str]:
    geblendet: set[str] = set()
    for anlass in _reihen_anlaesse(plantyp, termin.reihe):
        if anlass.get("id") not in termin.anlaesse:
            continue
        wirkung = anlass.get("wirkung")
        if isinstance(wirkung, dict):
            for feld in wirkung.get("ohne") or []:
                if isinstance(feld, str):
                    geblendet.add(feld)
    return geblendet


def _instanzenzahl(f: dict[str, Any]) -> int:
    anzahl = f.get("anzahl", 1)
    if isinstance(anzahl, int):
        return max(anzahl, 0)
    if isinstance(anzahl, str) and ".." in anzahl:
        links = anzahl.split("..", 1)[0]
        if links.isdigit():
            return int(links)
    return 1


def _baue_slot(
    f: dict[str, Any],
    pfad: str,
    index: int,
    gesamt: int,
    sammlung_kontext: str | None,
    parameter: dict[str, Any],
    force_art: str | None = None,
) -> Slot:
    art = force_art or f.get("art", "text")

    sammlung = f.get("sammlung")
    if isinstance(sammlung, str) and sammlung.startswith("{parameter."):
        kennung = sammlung.removeprefix("{parameter.").removesuffix("}")
        sammlung = str(parameter.get(kennung, sammlung))

    return Slot(
        feld_pfad=pfad,
        art=art,
        feld=f,
        anzahl=gesamt,
        pflicht=bool(f.get("pflicht", True)),
        bedingung=f.get("bedingung"),
        rolle=f.get("rolle"),
        sammlung=sammlung or sammlung_kontext,
        fuellen=f.get("fuellen", "optimieren" if art in ("person", "personen", "eintrag", "team") else "manuell"),
        aus=f.get("aus"),
        mitglieder=f.get("mitglieder"),
        teams=f.get("teams"),
    )
