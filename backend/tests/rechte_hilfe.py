"""Testhilfe R-4: Bestand einer Test-DB ins EINE Rechtesystem uebernehmen.

Viele Bestandstests legen Rechte im Altmodell an (``Gruppe Verantwortlicher``,
``Dienstbereich Verantwortlicher``, ``Untergruppe Verantwortlicher``,
``mitglied.ancestor_path``). Der Rechte-Kern liest nur noch seine eigenen
Tabellen. Diese Hilfe fuehrt GENAU die Bestandsuebernahme der Migration
``r1_rechte_kern`` auf der Test-DB aus — dieselbe Abbildung wie im Betrieb:

  * Gruppen-Verantwortliche -> HV/MV, Untergruppen-Verantwortliche -> GL,
  * Dienstbereich-Verantwortliche -> MV der Gruppen des Bereichs,
  * Pfad-Mitgliedschaften -> Mitgliedschafts-Zeilen,
  * Module beitraege/aufgaben/wiki je Gruppe (+ kalender/dienstplaene nach Bestand),
  * Objekte (Kalender, Dienstplaene, Beitraege, Wiki, Ankuendigungen, Aufgaben).
"""

from __future__ import annotations

from diakronos_app.rechte import bestand as _bestand


def uebernehmen(sess) -> dict:
    """Bestandsuebernahme auf der Verbindung der Sitzung; committet."""
    zaehler = _bestand.uebernehmen(sess)
    sess.commit()
    return zaehler


def uebernehmen_mit(sf) -> dict:
    """Wie :func:`uebernehmen`, fuer Tests mit Session-Factory (``with sf.begin()``)."""
    s = sf()
    try:
        return uebernehmen(s)
    finally:
        s.close()


def planrahmen_rechte(sf, *, bereich: str | None = None, gruppe: str | None = None,
                      hv: str | None = None, mv=(), leser=(),
                      module=("dienstplaene", "kalender")) -> str:
    """R-6: Plan-Rahmen-Rechte im EINEN Rechtesystem fuer Testwelten.

    Ersetzt die fruehere Bereichsverantwortung: eine Gruppe (im Bereich der
    Vorlage — sie ist dann deren einzige Gruppe), HV/MV, Module „Dienstplaene“
    und „Kalender“, dazu ein Gruppenkalender, in den ``leser`` schreiben
    duerfen (wer dort schreibt, sieht den ganzen Plan; Manuel 11.11.).
    ``sf`` ist eine Session-Factory oder eine Sitzung. Liefert die Gruppe.
    """
    from sqlalchemy import select

    from diakronos_app.models.diakonos import Gruppe
    from diakronos_app.models.kronos import Kalender
    from diakronos_app.models.rechte import RechteFreigabe, RechteGruppenrolle, RechteModul, RechteObjekt

    eigene = not hasattr(sf, "add")
    s = sf() if eigene else sf
    try:
        if gruppe is None and bereich:
            vorhanden = s.execute(select(Gruppe.name).where(Gruppe.dienstbereich == bereich)).scalars().all()
            gruppe = vorhanden[0] if len(vorhanden) == 1 else f"G-{bereich}"
        gruppe = gruppe or "G-plan"
        if s.get(Gruppe, gruppe) is None:
            s.add(Gruppe(name=gruppe, gruppenname=gruppe, dienstbereich=bereich, docstatus=0, idx=0))
        for modul in module:
            if s.execute(select(RechteModul).where(RechteModul.gruppe == gruppe,
                                                   RechteModul.modul == modul)).first() is None:
                s.add(RechteModul(gruppe=gruppe, modul=modul))
        for benutzer, rolle in ([(hv, "HV")] if hv else []) + [(m, "MV") for m in mv]:
            if s.execute(select(RechteGruppenrolle).where(
                    RechteGruppenrolle.gruppe == gruppe, RechteGruppenrolle.benutzer == benutzer,
                    RechteGruppenrolle.untergruppe.is_(None))).first() is None:
                s.add(RechteGruppenrolle(gruppe=gruppe, benutzer=benutzer, rolle=rolle))
        kal = f"K-{gruppe}"
        if s.get(Kalender, kal) is None:
            s.add(Kalender(name=kal, calendar_name=kal, selbstverwaltet=0, docstatus=0, idx=0))
            s.add(RechteObjekt(typ="kalender", objekt=kal, gruppe=gruppe))
        for benutzer in leser:
            s.add(RechteFreigabe(typ="kalender", objekt=kal, benutzer=benutzer, lesen=True, schreiben=True))
        s.commit()
        return gruppe
    finally:
        if eigene:
            s.close()
