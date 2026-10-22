"""Geprüfte HTTP-Endpunkte unter diakronos.planrahmen.api.<fn>.

Alle Schreiber sind POST-only und verwenden die bestehende Session-/CSRF-
Middleware. Ein Aufruf ist eine DB-Transaktion; Fachfehler rollen vollständig
zurück und liefern die strukturierten Meldungen der Plantyp-Prüfung.
"""
from __future__ import annotations

FRAPPE_MODULE = "diakronos.planrahmen.api"

from datetime import date
from functools import wraps
from inspect import Parameter, signature
from typing import Any, Callable, get_type_hints

from pydantic import TypeAdapter, ValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import select

from diakronos_app import db
from diakronos_app.frappe_compat import whitelist
from diakronos_app.frappe_compat.session import session
from diakronos_app.models.planrahmen import Plan, Plantyp
from diakronos_app.planrahmen.dienste import Dienste, DienstFehler, fehler
from diakronos_app.planrahmen import feiertage, ressourcen


def _datum(wert: Any) -> date:
    if not isinstance(wert, str):
        fehler("/datum", "ISO-Datum erwartet.")
    try:
        return date.fromisoformat(wert)
    except ValueError:
        fehler("/datum", "ISO-Datum erwartet.")


def _bool(wert: Any) -> bool:
    if not isinstance(wert, bool):
        fehler("/nur_vorschau", "JSON-Bool erwartet.")
    return wert


def _endpunkt(schreiben: bool = False) -> Callable:
    """Registriert eine Funktion mit expliziter, nicht umgehbarer Request-Grenze."""
    def dekorator(fn: Callable) -> Callable:
        sig = signature(fn)
        # Interner Dienste-Parameter wird nicht aus Benutzerargumenten übernommen.
        params = [p for n, p in sig.parameters.items() if n != "dienst"]
        params.append(Parameter("request", Parameter.KEYWORD_ONLY, default=None))
        api_sig = sig.replace(parameters=params)

        @wraps(fn)
        def aufruf(*args: Any, **kwargs: Any) -> Any:
            request = kwargs.pop("request", None)
            if schreiben and (request is None or request.method != "POST"):
                return JSONResponse(status_code=405, content={"message": "Schreibdienst benötigt POST.",
                                                               "exc_type": "MethodNotAllowed"}, headers={"Allow": "POST"})
            try:
                try:
                    api_sig.bind(*args, **kwargs)
                except TypeError:
                    fehler("/argumente", "Erforderliche Argumente fehlen oder sind ungültig.")
                for name, wert in kwargs.items():
                    annotation = get_type_hints(fn).get(name, Any)
                    if annotation is not Any:
                        try:
                            TypeAdapter(annotation).validate_python(wert, strict=True)
                        except ValidationError:
                            fehler("/" + name, "Argument hat nicht den erwarteten JSON-Typ.")
                with db.SessionLocal.begin() as s:
                    with db.als_aktuelle_sitzung(s):
                        return fn(Dienste(s, session.user), *args, **kwargs)
            except DienstFehler as exc:
                return JSONResponse(status_code=417, content={"message": str(exc), "exc_type": "ValidationError",
                                                               "exception": "ValidationError", "meldungen": exc.meldungen})
        aufruf.__signature__ = api_sig
        return whitelist(allow_guest=False)(aufruf)
    return dekorator


@_endpunkt()
def schema_holen(dienst: Dienste) -> dict[str, Any]:
    """Liefert das mitgelieferte JSON-Schema."""
    return {**ressourcen.schema_daten(), "x-regel-bausteine": ressourcen.regel_bausteine()}


@_endpunkt()
def feiertage_holen(dienst: Dienste) -> list[dict[str, str]]:
    """Der Feiertags-Katalog des Servers (EINE Quelle für die Oberfläche).

    K4 der Nachtprüfung: die Oberfläche führte den Katalog in zwei eigenen,
    leicht abweichenden Listen („Gruendonnerstag“/„Gründonnerstag“,
    „Buss-“/„Buß-“). Hier kommt er aus `planrahmen/feiertage.py` — dieselbe
    Deklaration, gegen die Prüfung und Engine arbeiten.
    """
    return [{"schluessel": f.schluessel, "name": f.name, "art": f.art}
            for f in feiertage.FEIERTAGE]


@_endpunkt()
def doku_holen(dienst: Dienste, name: str = "REFERENZ") -> str:
    """Whitelist statt benutzergesteuerter Ressourcenpfade."""
    if name not in {"REFERENZ", "LEITFADEN", "KONZEPT", "KOCHBUCH", "AGENT-ONBOARDING", "API"}:
        fehler("/name", "Unbekanntes Dokument.")
    return ressourcen.doku_text(name + ".md")


@_endpunkt()
def kochbuch_liste(dienst: Dienste) -> list[str]:
    """Verfügbare geprüfte Beispielkennungen."""
    return ressourcen.kochbuch_dateinamen()


@_endpunkt()
def kochbuch_holen(dienst: Dienste, name: str) -> dict[str, Any]:
    """Nur bekannte Beispielkennungen, niemals frei wählbare Dateipfade."""
    if name not in ressourcen.kochbuch_dateinamen():
        fehler("/name", "Unbekannte Kochbuch-Vorlage.")
    return ressourcen.kochbuch_laden(name)


@_endpunkt()
def einrichten_rechte(dienst: Dienste) -> dict[str, Any]:
    """Anlegerechte auch ohne vorhandene Plantypen."""
    return dienst.einrichten_rechte()


@_endpunkt()
def stammdaten_holen(dienst: Dienste, plantyp: str, plan: str | None = None) -> dict[str, Any]:
    """Deklarierte Stammdaten innerhalb des geprüften Plantyp-/Plan-Kontexts."""
    return dienst.stammdaten_holen(plantyp, plan)


@_endpunkt()
def merkmal_kandidaten(dienst: Dienste, plantyp: str, schluessel: str,
                       plan: str | None = None) -> dict[str, Any]:
    """Personen-Kandidaten eines Listen-Merkmals, serverseitig rollengefiltert (ST2)."""
    return dienst.merkmal_kandidaten(plantyp, schluessel, plan)


@_endpunkt()
def plantyp_pruefen(dienst: Dienste, definition: Any) -> dict[str, Any]:
    """Prüft eine Definition ohne Schreibzugriff."""
    return dienst.plantyp_pruefen(definition)


@_endpunkt(True)
def plantyp_speichern(dienst: Dienste, definition: dict[str, Any], gueltig_ab: str,
                      kommentar: str | None = None,
                      bestehende_erlauben: bool = True) -> dict[str, Any]:
    """Speichert eine neue unveränderliche Plantyp-Version.

    ``bestehende_erlauben=False`` ist der Weg „neue Planvorlage anlegen“: eine
    bereits vergebene Kennung bricht dann mit verständlicher Meldung ab
    (UXP-R5), statt die bestehende Vorlage still zu überschreiben.
    """
    return dienst.plantyp_speichern(definition, _datum(gueltig_ab), kommentar,
                                    _bool(bestehende_erlauben))


@_endpunkt()
def plantyp_auswirkung(dienst: Dienste, plantyp: str, gueltig_ab: str) -> dict[str, Any]:
    """UXP-R12: Zahl der Termine/Pläne, die eine neue Version umbindet."""
    return dienst.plantyp_auswirkung(plantyp, _datum(gueltig_ab))


@_endpunkt()
def plantyp_versionen_liste(dienst: Dienste, plantyp: str) -> list[dict[str, Any]]:
    """Versionen für berechtigte Planer."""
    return dienst.plantyp_versionen_liste(plantyp)


@_endpunkt()
def plantypen_liste(dienst: Dienste) -> list[dict[str, Any]]:
    """Neueste Definition und Serverfähigkeiten — nur für berechtigte Planer."""
    return dienst.plantypen_liste()


@_endpunkt(True)
def plan_anlegen(dienst: Dienste, plantyp: str, titel: str, von: str, bis: str,
                 parameter: dict[str, Any] | None = None, verantwortlich: str | None = None) -> dict[str, Any]:
    """Legt einen Plan mit versionsgebundenen Terminen an."""
    return dienst.plan_anlegen(plantyp, titel, _datum(von), _datum(bis), parameter, verantwortlich)


@_endpunkt()
def plan_holen(dienst: Dienste, plan: str) -> dict[str, Any]:
    """Entwurf für Planer, letzter veröffentlichter Stand für Mitglieder."""
    return dienst.plan_holen(plan)


@_endpunkt()
def plan_stand_version(dienst: Dienste, plan: str) -> dict[str, Any]:
    """Billiger Versionsstempel des Plan-Stands (PF1, Browser-Cache)."""
    return dienst.plan_stand_version(plan)


@_endpunkt()
def feld_kandidaten(dienst: Dienste, plan: str, termin: str, feld_pfad: str) -> dict[str, Any]:
    """Rollengefilterte Kandidaten mit Engine-Bewertung — nur für Plan-Editor."""
    return dienst.feld_kandidaten(plan, termin, feld_pfad)


@_endpunkt()
def plaene_liste(dienst: Dienste) -> list[dict[str, Any]]:
    """Listet ausschließlich sichtbare Pläne; keine Entwurfs-Titel lecken.

    P1-14b: Ein archivierter Plan ist fuer Nicht-Bearbeiter gar nicht mehr in
    der Liste (der Aushang ist abgehaengt). Fuer Bearbeiter steht dort der
    ECHTE Status — vorher meldete die Liste Nicht-Bearbeitern hart
    ``veroeffentlicht`` und liess archivierte Plaene stehen.
    """
    result = []
    for p, typ in dienst.s.execute(select(Plan, Plantyp).join(Plantyp, Plantyp.id == Plan.plantyp)).all():
        bearbeiten = dienst.rechte.darf_plan_bearbeiten(p, typ)
        if bearbeiten:
            kopf = {"titel": p.titel, "status": p.status,
                    "zeitraum_von": p.zeitraum_von.isoformat() if p.zeitraum_von else None,
                    "zeitraum_bis": p.zeitraum_bis.isoformat() if p.zeitraum_bis else None}
        elif p.status == "archiviert":
            continue
        elif p.veroeffentlichter_stand and dienst.rechte.eigenes_mitglied():
            kopf = p.veroeffentlichter_stand["plan"]
        else:
            continue
        result.append({"id": p.id, "titel": kopf["titel"],
                       "status": kopf["status"] if bearbeiten else "veroeffentlicht",
                       "zeitraum_von": kopf["zeitraum_von"], "zeitraum_bis": kopf["zeitraum_bis"],
                       "plantyp": typ.id, "plantyp_name": typ.name, "bereich": typ.bereich,
                       "darf_bearbeiten": bearbeiten})
    return result


@_endpunkt()
def meine_dienste(dienst: Dienste) -> list[dict[str, Any]]:
    """Eigene Personenzuordnungen ausschließlich aus veröffentlichten Ständen."""
    return dienst.meine_dienste()


@_endpunkt()
def termin_struktur(dienst: Dienste, plan: str, termin: str) -> dict[str, Any]:
    """Versionsdefinition und aktive Slots eines Termins."""
    return dienst.termin_struktur(plan, termin)


@_endpunkt()
def termin_strukturen(dienst: Dienste, plan: str) -> dict[str, Any]:
    """Alle Termin-Strukturen eines Plans in EINEM Aufruf (PF1).

    Ersetzt die N+1-Abfolge der Planseite (je Termin ein ``termin_struktur``).
    Rueckgabe: ``{"plan": ..., "strukturen": [{"termin", "version", "slots"}, …]}``.
    """
    return dienst.termin_strukturen(plan)


@_endpunkt(True)
def plan_generieren(dienst: Dienste, plan: str, nur_vorschau: bool = False, seed: int = 0,
                    nur_luecken: bool = False) -> dict[str, Any]:
    """Generiert Entwurfs-Slots, optional ohne Speichern (UXP-R16: nur Luecken)."""
    return dienst.plan_generieren(plan, _bool(nur_vorschau), seed, _bool(nur_luecken))


@_endpunkt(True)
def plan_entwurf(dienst: Dienste, plan: str) -> dict[str, Any]:
    """Oeffnet einen veroeffentlichten Plan als Entwurf (UXP-R16)."""
    return dienst.plan_entwurf(plan)


@_endpunkt(True)
def ablauf_aendern(dienst: Dienste, plan: str, termin: str, feld: str, aktion: str,
                   element_typ: str | None = None, element_id: str | None = None,
                   position: int | None = None) -> dict[str, Any]:
    """Ablaufelemente mit stabilen Kennungen bearbeiten, einschließlich Undo."""
    return dienst.ablauf_aendern(plan, termin, feld, aktion, element_typ, element_id, position)


@_endpunkt(True)
def eintrag_setzen(dienst: Dienste, plan: str, termin: str, feld_pfad: str, wert: Any) -> dict[str, Any]:
    """Manuelle Bearbeitung mit Fixierung und Regelmeldungen."""
    return dienst.eintrag_setzen(plan, termin, feld_pfad, wert)


@_endpunkt(True)
def eintrag_loesen(dienst: Dienste, plan: str, termin: str, feld_pfad: str) -> dict[str, Any]:
    """Hebt die Fixierung auf."""
    return dienst.eintrag_loesen(plan, termin, feld_pfad)


@_endpunkt(True)
def platz_hinzufuegen(dienst: Dienste, plan: str, termin: str, feld_pfad: str) -> dict[str, Any]:
    """Optionalen Mehrfachplatz eines Felds anlegen (vor dem Generieren)."""
    return dienst.platz_hinzufuegen(plan, termin, feld_pfad)


@_endpunkt(True)
def undo(dienst: Dienste, plan: str) -> dict[str, Any]:
    """Macht die letzte aktive Verlaufsgruppe rückgängig."""
    return dienst.undo(plan)


@_endpunkt()
def undo_vorschau(dienst: Dienste, plan: str) -> dict[str, Any]:
    """UXP-R20: Was würde „Rückgängig“ zurücknehmen? (nur lesend)"""
    return dienst.undo_vorschau(plan)


@_endpunkt(True)
def termin_aendern(dienst: Dienste, plan: str, termin: str, datum: str | None = None,
                   uhrzeit: str | None = None, entfaellt: bool | None = None,
                   titel: str | None = None, anlaesse: list[str] | None = None,
                   variante: str | None = None,
                   variante_setzen: bool = False) -> dict[str, Any]:
    """OP-CHOR-1/OP-EVENT-18: Datum, Uhrzeit, Absage, Anlass, Variante ändern."""
    return dienst.termin_aendern(plan, termin, datum=datum, uhrzeit=uhrzeit,
                                 entfaellt=entfaellt, titel=titel, anlaesse=anlaesse,
                                 variante=variante, variante_setzen=variante_setzen)


@_endpunkt(True)
def termin_hinzufuegen(dienst: Dienste, plan: str, datum: str, uhrzeit: str | None = None,
                       titel: str | None = None, anlaesse: list[str] | None = None,
                       reihe: str | None = None) -> dict[str, Any]:
    """OP-CHOR-1: manuellen Sondertermin zu einem Plan hinzufügen."""
    return dienst.termin_hinzufuegen(plan, datum, uhrzeit, titel, anlaesse, reihe)


@_endpunkt(True)
def termin_entfernen(dienst: Dienste, plan: str, termin: str) -> dict[str, Any]:
    """OP-CHOR-1: Termin samt Einträgen entfernen (mit Undo)."""
    return dienst.termin_entfernen(plan, termin)


@_endpunkt(True)
def plan_loeschen(dienst: Dienste, plan: str, bestaetigt: bool = False) -> dict[str, Any]:
    """OP-UI-12: Entwurf endgültig löschen (veröffentlichte nur archivieren).

    P1-14b: ``bestaetigt=True`` ist Pflicht — die Löschung ist unwiderruflich.
    """
    return dienst.plan_loeschen(plan, _bool(bestaetigt))


@_endpunkt(True)
def plan_archivieren(dienst: Dienste, plan: str, archivieren: bool = True) -> dict[str, Any]:
    """OP-UI-12: Plan archivieren bzw. zurückholen."""
    return dienst.plan_archivieren(plan, _bool(archivieren))


@_endpunkt(True)
def plan_kopieren(dienst: Dienste, plan: str, titel: str, mit_eintraegen: bool = True,
                  von: str | None = None, bis: str | None = None) -> dict[str, Any]:
    """OP-UI-12: Plan samt Terminen (und optional Einträgen) kopieren."""
    return dienst.plan_kopieren(plan, titel, _bool(mit_eintraegen),
                                _datum(von) if von else None, _datum(bis) if bis else None)


@_endpunkt(True)
def plan_aendern(dienst: Dienste, plan: str, titel: str | None = None,
                 von: str | None = None, bis: str | None = None,
                 parameter: dict[str, Any] | None = None) -> dict[str, Any]:
    """OP-UI-12: Titel/Zeitraum/Parameter eines Plans ändern."""
    return dienst.plan_aendern(plan, titel, _datum(von) if von else None,
                               _datum(bis) if bis else None, parameter)


@_endpunkt(True)
def veroeffentlichen(dienst: Dienste, plan: str) -> dict[str, Any]:
    """Speichert einen veröffentlichten Stand mit Wert-Diff."""
    return dienst.veroeffentlichen(plan)


@_endpunkt()
def bedarf(dienst: Dienste, plantyp: str, plan: str | None = None) -> list[dict[str, Any]]:
    """Datenabdeckung mit echter Datenquelle."""
    return dienst.bedarf(plantyp, plan)


@_endpunkt()
def trockenlauf(dienst: Dienste, definition: dict[str, Any], parameter: dict[str, Any] | None = None,
                ab: str | None = None, wochen: int = 8, seed: int = 0) -> dict[str, Any]:
    """Vorschlag ohne Persistenz."""
    return dienst.trockenlauf(definition, parameter, _datum(ab) if ab else None, wochen, seed)


@_endpunkt(True)
def merkmale_pflegen(dienst: Dienste, plantyp: str, werte: list[dict[str, Any]],
                      plan: str | None = None) -> dict[str, Any]:
    """Planer pflegen die deklarierten Merkmalswerte."""
    return dienst.merkmale_pflegen(plantyp, werte, plan)


@_endpunkt(True)
def sammlung_pflegen(dienst: Dienste, plantyp: str, sammlung: str, eintraege: list[dict[str, Any]],
                      plan: str | None = None) -> dict[str, Any]:
    """Pflegt eigene Sammlungen, getrennt nach Gemeinde/Plan."""
    return dienst.sammlung_pflegen(plantyp, sammlung, eintraege, plan)


@_endpunkt(True)
def abwesenheit_melden(dienst: Dienste, mitglied: str, von: str, bis: str, grund: str = "",
                       plantyp: str | None = None, plan: str | None = None) -> dict[str, Any]:
    """Eigene Abwesenheiten, fremde nur mit expliziter Planer-Berechtigung."""
    return dienst.abwesenheit_melden(mitglied, _datum(von), _datum(bis), grund, plantyp, plan)


@_endpunkt()
def abwesenheiten_liste(dienst: Dienste, mitglied: str | None = None,
                        plantyp: str | None = None, plan: str | None = None) -> list[dict[str, Any]]:
    """Abwesenheiten lesen (UXP-R17) — ohne `mitglied` die eigenen."""
    return dienst.abwesenheiten_liste(mitglied, plantyp, plan)


@_endpunkt(True)
def abwesenheit_loeschen(dienst: Dienste, abwesenheit: str) -> dict[str, Any]:
    """Eigene Abwesenheit zuruecknehmen (UXP-R17)."""
    return dienst.abwesenheit_loeschen(abwesenheit)


@_endpunkt(True)
def dienst_absagen(dienst: Dienste, plan: str, termin: str, feld_pfad: str) -> dict[str, Any]:
    """Eigene Einteilung absagen — der Platz wird wieder frei (OP-HANDY-18)."""
    return dienst.dienst_absagen(plan, termin, feld_pfad)


# ── ST2: Lieder pflegen ──────────────────────────────────────────────────────


@_endpunkt()
def lied_rechte(dienst: Dienste, plantyp: str | None = None,
                plan: str | None = None) -> dict[str, Any]:
    """Schreibrecht für Lieder — die UI blendet nur aus, was der Server verweigert."""
    return dienst.lied_rechte(plantyp, plan)


@_endpunkt(True)
def lied_speichern(dienst: Dienste, plantyp: str, lied: str, daten: dict[str, Any],
                   plan: str | None = None) -> dict[str, Any]:
    """Lied umbenennen / Nummer/Buch/Seite aendern (Psalmos = eine Wahrheit)."""
    return dienst.lied_speichern(plantyp, lied, daten, plan)


@_endpunkt(True)
def lied_material_hinzufuegen(dienst: Dienste, lied: str, art: str,
                              dateiname: str, datei_url: str, stimme: str = "",
                              beschreibung: str = "", plantyp: str | None = None,
                              plan: str | None = None) -> dict[str, Any]:
    """Material (Noten/Audio/Notensatz) an ein Lied haengen.

    ``plantyp`` ist optional: Aufrufe aus dem Lied-Detail (ohne Planvorlage)
    pruefen die Psalmos-Regel (UXM-R7).
    """
    return dienst.lied_material_hinzufuegen(plantyp, lied, art, dateiname, datei_url,
                                            stimme, beschreibung, plan)


@_endpunkt(True)
def lied_material_loeschen(dienst: Dienste, lied: str, material: str,
                           plantyp: str | None = None,
                           plan: str | None = None) -> dict[str, Any]:
    """Material eines Liedes entfernen (plantyp optional, UXM-R7)."""
    return dienst.lied_material_loeschen(plantyp, lied, material, plan)


@_endpunkt(True)
def sammlungsmerkmal_werte_pflegen(dienst: Dienste, plantyp: str, schluessel: str, aktion: str,
                                   wert: str, neu: str | None = None,
                                   plan: str | None = None) -> dict[str, Any]:
    """Auswahl-/Tag-Werte eines Listen-Merkmals pflegen (hinzufuegen/umbenennen/entfernen)."""
    return dienst.sammlungsmerkmal_werte_pflegen(plantyp, schluessel, aktion, wert, neu, plan)
