"""Transaktionale Plan-Rahmen-Dienste; Commit/Rollback gehört dem Aufrufer.

Plan-Schreiber sperren den Plan vor dem Lesen des Zustands. Jeder erfolgreiche
Schreibdienst erhält eine Verlaufsgruppe. Undo stellt vollständige Plan-Snapshots
wieder her, ohne unveränderliche Plantyp-Versionen zu löschen oder zu verändern.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
from datetime import date, datetime, time
import hashlib
import json
import re
from typing import Any, NoReturn
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from diakronos_app.models.diakonos import Dienstbereich, DienstbereichVerantwortlicher, Mitglied
from diakronos_app.models.psalmos import Lied, Liedfassung, LiedMaterial
from diakronos_app.models.planrahmen import (
    Abwesenheit, Eintrag, Merkmal, MerkmalWert, Plan, Plantyp, PlantypVersion,
    Sammlung, SammlungEintrag, Termin, Verlauf,
)
from . import speicher
from .engine.bedarf import bedarfspruefung
from .engine.generator import generiere
from .engine.modell import Eintrag as EngineEintrag, Termin as EngineTermin
from .engine.struktur import aufloesen_mit_eintraegen
from .engine.termine import TerminLimitUeberschritten, erzeuge_termine
from .engine.trockenlauf import trockenlauf as engine_trockenlauf
from .pruefung import pruefe_plantyp
from .rechte import Rechte, _plantyp_gruppen
from .regeln.auswertung import pruefe_plan


class DienstFehler(Exception):
    """Strukturierte, öffentlich lesbare Fachmeldungen (ohne interne Daten)."""

    def __init__(self, meldungen: list[dict[str, Any]]):
        super().__init__("Plan-Rahmen-Prüfung fehlgeschlagen.")
        self.meldungen = meldungen

    @classmethod
    def aus_terminlimit(cls, exc: TerminLimitUeberschritten) -> "DienstFehler":
        """Wandelt eine Engine-Grenzverletzung (BLD-R2) in eine Fachmeldung.

        Damit antwortet die API auch bei einer zu grossen/unbegrenzten
        Wiederholungsregel mit einer verstaendlichen Meldung (HTTP 417) statt
        mit einem haengenden Prozess.

        Befund N2 (P0-4b): ``exc.reihe`` traegt BEREITS einen vollstaendigen
        Pfad — die Engine setzt ihn ueber ``_pfad(kennung)`` auf
        ``/termine/regel`` (Kurzform) bzw. ``/terminreihen/<index>/termine/regel``
        (Reihe). Vorher wurde hier noch einmal ``/terminreihen/…/termine/regel``
        darum gebaut, was den Pfad verdoppelte
        (``/terminreihen//terminreihen/0/termine/regel/termine/regel``) und die
        Oberflaeche das Feld nicht mehr zuordnen liess. Deshalb: ist der Wert
        ein Pfad (beginnt mit ``/``), wird er unveraendert uebernommen; nur ein
        leerer Wert faellt auf den allgemeinen Regel-Pfad zurueck.
        """
        reihe = str(exc.reihe or "").strip()
        pfad = reihe if reihe.startswith("/") else "/termine/regel"
        return cls([{
            "pfad": pfad,
            "code": "terminlimit_ueberschritten",
            "meldung": exc.meldung,
            "hinweis": "Wiederholungsregel grober fassen (z. B. FREQ=WEEKLY, INTERVAL>=1) "
                       "oder den Zeitraum verkleinern.",
            "stufe": "fehler",
        }])


def fehler(pfad: str, meldung: str, code: str = "dienst.ungueltig",
           hinweis: str = "Bitte prüfe die markierten Eingaben und versuche es erneut.") -> NoReturn:
    """Einheitliches Fehlerformat auch für Dienstargumente.

    ``code`` trägt entweder den stablen Fehlercode oder — bei direkt
    geschriebenen Aufrufen im Bestand — den ``hinweis``-Text. Ein Aufruf mit
    drei Argumenten bleibt daher unverändert gültig.
    """
    raise DienstFehler([{"pfad": pfad, "code": code, "meldung": meldung,
                         "hinweis": hinweis, "stufe": "fehler"}])


def jsonwert(wert: Any) -> Any:
    """JSON-Snapshot ohne ORM-/Engine-Identitäten und zyklische Bezüge."""
    if isinstance(wert, (date, datetime, time)):
        return wert.isoformat()
    if isinstance(wert, dict):
        return {k: jsonwert(v) for k, v in wert.items()}
    if isinstance(wert, (list, tuple, set, frozenset)):
        return [jsonwert(v) for v in wert]
    return deepcopy(wert)


def zeile(objekt: Any) -> dict[str, Any]:
    """Nur persistierte Spalten eines Datensatzes als Snapshot."""
    return {c.name: jsonwert(getattr(objekt, c.name)) for c in objekt.__table__.columns}


class Dienste:
    """Fachoperationen auf einer einzigen Session und geprüften Identität."""

    def __init__(self, session: Session, benutzer: str):
        self.s = session
        self.benutzer = benutzer
        self.rechte = Rechte(session, benutzer)
        self.rechte.angemeldet()

    def _typ(self, kennung: str, schreiben: bool = True) -> Plantyp:
        typ = self.s.scalar(select(Plantyp).where(
            (Plantyp.id == kennung) | (Plantyp.schluessel == kennung)).with_for_update())
        if typ is None:
            fehler("/plantyp", "Diese Planvorlage wurde nicht gefunden.",
                   hinweis="Bitte öffne die Übersicht der Planvorlagen und wähle die Vorlage erneut aus.")
        if schreiben:
            self.rechte.plantyp(typ)
        return typ

    def _plan(self, kennung: str, schreiben: bool = True,
              archiv_erlaubt: bool = False) -> tuple[Plan, Plantyp, bool]:
        """Laedt einen Plan samt Rechten; archivierte Plaene sind gesperrt.

        P1-14b: Jeder SCHREIBENDE Zugriff auf einen archivierten Plan wird an
        der Wurzel abgewiesen. Vorher setzten ``termin_aendern``/
        ``termin_hinzufuegen``/``termin_entfernen``/``plan_aendern`` (und jeder
        weitere Schreibweg ueber ``_schreibabschluss``) einen veroeffentlichten
        Plan still auf ``entwurf`` — ein archivierter Plan verschwand damit
        unbemerkt aus dem Archiv und der Aushang war wieder sichtbar. Der
        einzige erlaubte Weg zurueck ist ``plan_archivieren`` — deshalb darf
        nur dieser Dienst ``archiv_erlaubt=True`` setzen.
        """
        p = self.s.scalar(select(Plan).where(Plan.id == kennung).with_for_update())
        if p is None:
            from diakronos_app.frappe_compat.exceptions import PermissionError
            raise PermissionError("Zugriff verweigert.")
        typ = self.s.get(Plantyp, p.plantyp)
        bearbeiten = self.rechte.plan(p, typ, schreiben)
        if schreiben and bearbeiten and not archiv_erlaubt:
            self._nicht_archiviert(p)
        return p, typ, bearbeiten

    @staticmethod
    def _nicht_archiviert(p: Plan) -> None:
        """Archivierte Plaene sind schreibgeschuetzt (P1-14b).

        Vorher setzten ``termin_aendern``/``termin_hinzufuegen``/
        ``termin_entfernen``/``plan_aendern`` einen veroeffentlichten Plan
        still auf ``entwurf`` — auch wenn er archiviert war. Damit verschwand
        er unbemerkt aus dem Archiv und Mitglieder sahen den Aushang wieder.
        Stattdessen wird die Aenderung klar abgelehnt; der Weg zurueck ist
        ausdruecklich ``plan_archivieren(archivieren=False)``.
        """
        if p.status == "archiviert":
            fehler("/status",
                   "Dieser Plan ist archiviert. Hol ihn zuerst mit „Aus dem Archiv "
                   "holen“ zurueck, bevor du ihn änderst.",
                   "plan.archiviert")


    def _quelle(self, typ: Plantyp | str, plan: Plan | None = None) -> Any:
        """Lädt den DB-Adapter nur bei Bedarf (keine globalen DB-Verbindungen).

        ``typ`` ist ein Plantyp oder dessen Definitionsschlüssel — der
        Trockenlauf neuer, noch nicht gespeicherter Definitionen bindet die
        Abwesenheits-Sichtbarkeit damit an genau diesen (bislang leeren)
        Schlüssel, ohne eine Plantyp-Zeile anzulegen.

        ST3: Die an die Vorlage gebundenen Gruppen (``gruppen`` /
        ``inkl_untergruppen`` der jüngsten Definition) werden als
        PERSONENPOOL an die Datenquelle gereicht — zentral hier, nicht in
        jeder Komponente.
        """
        from .datenquelle_db import DBDatenquelle
        pool, inkl = self._pool_gruppen(typ)
        return DBDatenquelle(self.s, plantyp=typ.schluessel if isinstance(typ, Plantyp) else typ,
                            plan_id=plan.id if plan else None,
                            veranstaltung=(plan.parameter or {}).get("veranstaltung", "") if plan else "",
                            pool_gruppen=pool, pool_inkl_untergruppen=inkl)

    def _pool_gruppen(self, typ: Plantyp | str) -> tuple[frozenset[str], bool]:
        """Gebundene Gruppen der Vorlage (ST3) aus der jüngsten Definition.

        Liefert ``(gruppen, inkl_untergruppen)``. Eine Plantyp-Zeile ist
        vorhanden, wenn ``typ`` ein ``Plantyp`` ist oder eine ID; ein reiner
        Definitionsschlüssel (Trockenlauf) hat noch keine Versionen — dann
        sind keine Gruppen gebunden.
        """
        if isinstance(typ, Plantyp):
            plantyp_id = typ.id
        else:
            plantyp_id = self.s.scalar(select(Plantyp.id).where(
                (Plantyp.id == typ) | (Plantyp.schluessel == typ)))
        if not plantyp_id:
            return frozenset(), False
        letzte = self.s.scalars(select(PlantypVersion).where(
            PlantypVersion.plantyp == plantyp_id).order_by(
            PlantypVersion.versionsnummer.desc())).first()
        if letzte is None or not isinstance(letzte.definition, dict):
            return frozenset(), False
        gruppen = letzte.definition.get("gruppen") or []
        return (frozenset(g for g in gruppen if isinstance(g, str)),
                bool(letzte.definition.get("inkl_untergruppen")))

    def _verlauf(self, aktion: str, vorher: Any, nachher: Any,
                 plan: Plan | None = None, typ: Plantyp | None = None) -> str:
        """Monotone Aufrufzeit statt transaktionsstabilem PostgreSQL now()."""
        gruppe = str(uuid4())
        self.s.add(Verlauf(plan=plan.id if plan else None,
                           plantyp=typ.id if typ else (plan.plantyp if plan else None),
                           benutzer=self.benutzer, aktion=aktion, gruppe_id=gruppe,
                           zeitpunkt=datetime.now(), vorher=jsonwert(vorher), nachher=jsonwert(nachher)))
        self.s.flush()
        return gruppe

    def _stand(self, p: Plan) -> dict[str, Any]:
        self.s.flush()
        ts = self.s.scalars(select(Termin).where(Termin.plan == p.id).order_by(Termin.datum, Termin.reihe, Termin.id)).all()
        es = self.s.scalars(select(Eintrag).join(Termin, Eintrag.termin == Termin.id).where(
            Termin.plan == p.id).order_by(Eintrag.termin, Eintrag.feld_pfad)).all()
        sammlungen = self.s.scalars(select(Sammlung).where(Sammlung.plan == p.id)).all()
        sam_ids = [s.id for s in sammlungen]
        sam_eintraege = self.s.scalars(select(SammlungEintrag).where(SammlungEintrag.sammlung.in_(sam_ids))).all()
        return {"plan": zeile(p), "termine": [zeile(t) for t in ts], "eintraege": [zeile(e) for e in es],
                "sammlungen": [zeile(s) for s in sammlungen], "sammlung_eintraege": [zeile(e) for e in sam_eintraege]}

    def _schreibabschluss(self, p: Plan, vorher: Any, aktion: str) -> str:
        if aktion != "veroeffentlichen" and p.veroeffentlichter_stand is not None:
            p.status = "entwurf"
        return self._verlauf(aktion, vorher, self._stand(p), plan=p)

    def plantyp_pruefen(self, definition: Any) -> dict[str, Any]:
        """Validiert ohne Schreibzugriff; Warnungen verhindern das Speichern nicht."""
        meldungen = [m.als_dict() for m in pruefe_plantyp(deepcopy(definition))]
        return {"gueltig": not any(m["stufe"] == "fehler" for m in meldungen), "meldungen": meldungen}

    def _erzeuge_termine(self, definition: dict[str, Any], parameter: dict[str, Any], quelle: Any,
                         *, von: date | None = None, bis: date | None = None) -> Any:
        """Termine erzeugen; harte Engine-Grenzen werden zur Fachmeldung (BLD-R2).

        Ohne diese Uebersetzung schluege ein ``TerminLimitUeberschritten``
        als unbehandelter 500er durch. Stattdessen erhaelt der Aufrufer eine
        strukturierte, verstaendliche Meldung (HTTP 417).
        """
        try:
            return erzeuge_termine(definition, parameter, quelle, von=von, bis=bis)
        except TerminLimitUeberschritten as exc:
            raise DienstFehler.aus_terminlimit(exc) from exc

    def _definition(self, definition: Any) -> dict[str, Any]:
        ergebnis = self.plantyp_pruefen(definition)
        if not ergebnis["gueltig"]:
            raise DienstFehler(ergebnis["meldungen"])
        return deepcopy(definition)

    def plantyp_speichern(self, definition: dict[str, Any], gueltig_ab: date,
                          kommentar: str | None = None,
                          bestehende_erlauben: bool = True) -> dict[str, Any]:
        """Neue unveränderliche Version; Termine vor gueltig_ab bleiben gebunden.

        UXP-R5: Eine Kennung darf NICHT still eine BESTEHENDE Vorlage
        überschreiben, wenn die Anlage ausdrücklich als „neue Planvorlage“
        gedacht ist. Der Aufruf aus dem Anlege-Weg übergibt dafür
        ``bestehende_erlauben=False``; dann bricht ein bereits vergebener
        Schlüssel mit verständlicher Meldung ab (inkl. Name der Vorlage).
        Der Standard bleibt ``True`` — der reguläre „Version speichern“-Weg
        (und der Bestand) verhält sich unverändert.
        """
        definition = self._definition(definition)
        typ = self.s.scalar(select(Plantyp).where(Plantyp.schluessel == definition["id"]).with_for_update())
        if typ is not None and not bestehende_erlauben:
            fehler("/id", f"Die Kennung {definition['id']!r} gehört bereits zur Planvorlage "
                          f"„{typ.name}“. Eine neue Version würde diese Vorlage ab dem "
                          "Stichtag verändern.",
                   "Wähle eine andere Kennung oder öffne die bestehende Vorlage unter "
                   "„Einrichten“, um dort eine neue Version anzulegen.")
        bereich = definition.get("bereich")
        if typ:
            self.rechte.plantyp(typ)
            if typ.bereich != bereich and not self.rechte.admin():
                from diakronos_app.frappe_compat.exceptions import PermissionError
                raise PermissionError("Bereichswechsel erfordert Administratorrechte.")
        elif not self.rechte.bereich(bereich):
            from diakronos_app.frappe_compat.exceptions import PermissionError
            raise PermissionError("Zugriff verweigert.")
        if bereich and self.s.get(Dienstbereich, bereich) is None:
            fehler("/bereich", "Dienstbereich nicht gefunden.")
        if typ is None:
            typ = Plantyp(schluessel=definition["id"], name=definition["name"], bereich=bereich,
                          created_by=self.benutzer)
            self.s.add(typ)
            self.s.flush()
        typ.name, typ.bereich = definition["name"], bereich
        version = speicher.version_anlegen(self.s, plantyp_id=typ.id, definition=definition,
                                           gueltig_ab=gueltig_ab, erstellt_von=self.benutzer,
                                           kommentar=kommentar)
        for ziel, merkmale in definition.get("merkmale", {}).items():
            ziel = "person" if ziel == "person" else "sammlung:" + ziel
            for m in merkmale:
                alt = self.s.scalar(select(Merkmal).where(Merkmal.ziel == ziel, Merkmal.schluessel == m["id"]))
                if alt and alt.art != m["art"]:
                    fehler("/merkmale", "Bestehender Merkmalschlüssel hat eine andere Art.")
                if alt is None:
                    self.s.add(Merkmal(ziel=ziel, schluessel=m["id"], art=m["art"], definition=m,
                                       angelegt_durch_plantyp=typ.id, created_by=self.benutzer))
                    self.s.flush()
        for sam in definition.get("sammlungen", []):
            if sam.get("umfang", "gemeinde") == "gemeinde":
                self._sammlung_anlegen(sam)
        self._verlauf("plantyp_speichern", None, zeile(version), typ=typ)
        # Alle betroffenen Pläne sperren; ihre Historie bleibt separat undo-fähig.
        for p in self.s.scalars(select(Plan).where(Plan.plantyp == typ.id).order_by(Plan.id).with_for_update()).all():
            vorher = self._stand(p)
            geaendert = False
            for t in self.s.scalars(select(Termin).where(Termin.plan == p.id, Termin.datum >= gueltig_ab)).all():
                aktuell = speicher.gueltige_version_zu_datum(self.s, typ.id, t.datum)
                if t.plantyp_version != aktuell.id:
                    t.plantyp_version = aktuell.id
                    geaendert = True
            if geaendert:
                self._schreibabschluss(p, vorher, "version_anwenden")
        return zeile(version)

    def _sammlung_anlegen(self, definition: dict[str, Any], plan: Plan | None = None) -> Sammlung:
        umfang = definition.get("umfang", "gemeinde")
        plan_id = plan.id if umfang == "plan" and plan else None
        sam = self.s.scalar(select(Sammlung).where(Sammlung.schluessel == definition["id"],
                                                   Sammlung.plan == plan_id))
        if sam is None:
            sam = Sammlung(schluessel=definition["id"], name=definition.get("name", definition["id"]),
                           umfang=umfang, plan=plan_id, definition=definition, created_by=self.benutzer)
            self.s.add(sam)
            self.s.flush()
        return sam

    def plantyp_versionen_liste(self, plantyp: str) -> list[dict[str, Any]]:
        typ = self._typ(plantyp)
        return [zeile(v) for v in self.s.scalars(select(PlantypVersion).where(
            PlantypVersion.plantyp == typ.id).order_by(PlantypVersion.versionsnummer)).all()]

    def plantyp_auswirkung(self, plantyp: str, gueltig_ab: str | date) -> dict[str, Any]:
        """UXP-R12: Zahl der Termine und Pläne, die eine neue Version umbindet.

        Der Versionsdialog behauptete früher, bereits angelegte Termine
        behielten ihre Struktur; tatsächlich werden ALLE Termine ab dem
        Stichtag auf die neue Version umgebunden. Damit die Planerin das
        vorher sieht, nennt dieser Lesezugriff genau die betroffenen Zahlen.
        """
        von = gueltig_ab if isinstance(gueltig_ab, date) else date.fromisoformat(str(gueltig_ab))
        typ = self._typ(plantyp, schreiben=False)
        plan_ids = [p.id for p in self.s.scalars(
            select(Plan).where(Plan.plantyp == typ.id)).all()]
        if not plan_ids:
            return {"plantyp": typ.id, "gueltig_ab": von.isoformat(),
                    "termine": 0, "plaene": 0}
        betroffene = self.s.execute(
            select(func.count(Termin.id), func.count(func.distinct(Termin.plan))).where(
                Termin.plan.in_(plan_ids), Termin.datum >= von)).one()
        return {"plantyp": typ.id, "gueltig_ab": von.isoformat(),
                "termine": betroffene[0] or 0, "plaene": betroffene[1] or 0}

    def _verantwortungen(self) -> tuple[bool, set[str], set[str]]:
        """Admin-, Bereichs- und Plantyp-Verantwortung des Aufrufenden.

        Plantyp-Verantwortung entsteht durch eigene Planverantwortung
        (``plan.verantwortlich``) an mindestens einem Plan des Plantyps
        **oder** (ST3) durch Gruppenverantwortung einer an den Plantyp
        gebundenen Gruppe.
        """
        admin = self.rechte.admin()
        eigene_bereiche: set[str] = set()
        eigene_plantypen: set[str] = set()
        if not admin:
            eigene_bereiche = set(self.s.scalars(select(DienstbereichVerantwortlicher.parent).where(
                DienstbereichVerantwortlicher.user == self.benutzer,
                DienstbereichVerantwortlicher.parenttype == "Dienstbereich",
                DienstbereichVerantwortlicher.parentfield == "verantwortliche").distinct()).all())
            eigene_mitglied = self.rechte.eigenes_mitglied()
            if eigene_mitglied:
                eigene_plantypen |= set(self.s.scalars(select(Plan.plantyp).where(
                    Plan.verantwortlich == eigene_mitglied).distinct()).all())
            eigene_plantypen |= self._plantypen_meiner_gruppen()
        return admin, eigene_bereiche, eigene_plantypen

    def _plantypen_meiner_gruppen(self) -> set[str]:
        """Plantypen, an die eine Gruppe gebunden ist, die ich verantworte (ST3).

        Liest die jüngste Definition jedes Plantyps und prueft deren
        ``gruppen`` gegen die eigenen Gruppenverantwortungen.
        """
        meine = self.rechte.eigene_gruppen_verantwortung()
        if not meine:
            return set()
        treffer: set[str] = set()
        for typ_id in self.s.scalars(select(Plantyp.id)).all():
            if _plantyp_gruppen(self.s, typ_id) & meine:
                treffer.add(typ_id)
        return treffer

    def _bereichsnamen(self) -> dict[str, str]:
        """Kennung → Anzeigename der Dienstbereiche (UXP-R13).

        Neu in der App angelegte Dienstbereiche tragen die interne ID als
        ``name`` und den lesbaren Text in ``ministry``; alte Bereiche haben
        beides gleich. Die UI zeigt deshalb nie mehr eine interne ID
        („e9bf5dbe-b“), sondern den Anzeigenamen.
        """
        return {b.name: (b.ministry or b.name)
                for b in self.s.scalars(select(Dienstbereich)).all()}

    def plantypen_liste(self) -> list[dict[str, Any]]:
        """Neueste Definition je Plantyp mit Rechte-Flags (UI1/UI2).

        Sichtbar: eigene Dienstbereiche (Admin: alle) plus die Plantypen,
        für die der Aufrufende Planverantwortlicher mindestens eines Plans
        ist oder (ST3) Gruppenverantwortlicher einer gebundenen Gruppe.
        Flags je Plantyp: `darf_plantyp_bearbeiten` (Plantyp-Edit — Admin
        oder Bereichsverantwortung, entspricht `rechte.plantyp`),
        `darf_plan_anlegen` (Bereichs- ODER Gruppenverantwortung, ST3) und
        `darf_bearbeiten` (zusätzlich eigene Planverantwortung — Plan-
        Stammdaten). Ohne jede Verantwortung gibt es keinerlei
        Plantyp-Auskunft (403).
        """
        admin, eigene_bereiche, eigene_plantypen = self._verantwortungen()
        if not admin and not eigene_bereiche and not eigene_plantypen:
            from diakronos_app.frappe_compat.exceptions import PermissionError
            raise PermissionError("Zugriff verweigert.")
        if admin:
            typen = self.s.scalars(select(Plantyp).order_by(Plantyp.schluessel)).all()
        else:
            typen = self.s.scalars(select(Plantyp).where(
                Plantyp.bereich.in_(eigene_bereiche) | Plantyp.id.in_(eigene_plantypen)
                if eigene_bereiche else Plantyp.id.in_(eigene_plantypen)
            ).order_by(Plantyp.schluessel)).all()
        result = []
        bereichsnamen = self._bereichsnamen()
        for typ in typen:
            letzte = self.s.scalars(select(PlantypVersion).where(
                PlantypVersion.plantyp == typ.id).order_by(
                PlantypVersion.versionsnummer.desc())).first()
            darf_anlegen = self.rechte.darf_plan_anlegen(typ)
            darf_vorlage = self.rechte.darf_plantyp_bearbeiten(typ)
            result.append({**zeile(typ), "letzte_version": zeile(letzte) if letzte else None,
                           "bereich_name": bereichsnamen.get(typ.bereich or "", typ.bereich or ""),
                           "darf_plan_anlegen": darf_anlegen,
                           "darf_plantyp_bearbeiten": darf_vorlage,
                           "darf_bearbeiten": darf_anlegen or typ.id in eigene_plantypen})
        return result

    def einrichten_rechte(self) -> dict[str, Any]:
        """Einrichtungs-Rechte des UI2-Editors — auch bei leerer Liste (UI2).

        Der Editor muss einen neuen leeren Plantyp anlegen können, bevor die
        Plantyp-Liste überhaupt Einträge hat. Deshalb beantwortet dieser
        Dienst unabhängig von `plantypen_liste`: `darf_anlegen` gilt bei
        Admin oder Dienstbereichsverantwortung, `bereiche` nennt die
        wählbaren Bereiche (Admin: alle, sonst: eigene), `admin` den
        Admin-Status. Ohne jede Verantwortung gibt es 403 (kein Info-Leak).
        Gruppenverantwortliche allein duerfen keine Vorlage anlegen (ST3):
        dann bleibt `darf_anlegen` False, aber die Antwort ist erlaubt, damit
        die UI ihre lesenden Bereiche zeigen kann.
        """
        admin, eigene_bereiche, eigene_plantypen = self._verantwortungen()
        if not admin and not eigene_bereiche and not eigene_plantypen:
            from diakronos_app.frappe_compat.exceptions import PermissionError
            raise PermissionError("Zugriff verweigert.")
        darf_vorlage_anlegen = admin or bool(eigene_bereiche)
        # UXP-R9: Bereiche mit Anzeigename statt interner Kennung — der Editor
        # bietet sie als Auswahlliste an (kein Freitext, keine Jargon-Meldung).
        # UXP-R13: neue Bereiche tragen die ID als name, den Text in ministry.
        bereichsnamen = self._bereichsnamen()
        if admin:
            kennungen = [b for b in self.s.scalars(
                select(Dienstbereich.name).order_by(Dienstbereich.name)).all()]
        else:
            kennungen = sorted(eigene_bereiche)
        # `bereiche` bleibt die reine Kennungsliste (Bestand), `bereich_liste`
        # nennt Kennung UND Anzeigename für die Auswahlliste (UXP-R9/R13).
        bereiche = kennungen
        bereich_liste = [{"kennung": k, "name": bereichsnamen.get(k, k)} for k in kennungen]
        # ST3: waehlbare Diakonos-Gruppen fuer die Gruppenbindung der Vorlage.
        from diakronos_app.models.diakonos import Gruppe
        gruppen = [{"kennung": g.name, "name": g.gruppenname or g.name}
                   for g in self.s.scalars(select(Gruppe).where(
                       Gruppe.docstatus < 2).order_by(Gruppe.name)).all()]
        return {"darf_anlegen": darf_vorlage_anlegen,
                "bereiche": bereiche,
                "bereich_liste": bereich_liste,
                "gruppen": gruppen, "admin": admin}

    def _darf_stammdaten_lesen(self, typ: Plantyp, p: Plan | None = None) -> bool:
        """Leserecht auf Stammdaten/Personenpool einer Vorlage (ST3).

        Admin, Bereichsverantwortliche, Planverantwortliche eines Plans dieser
        Vorlage sowie Gruppenverantwortliche einer gebundenen Gruppe. Wird
        von `stammdaten_holen`, `merkmal_kandidaten` und `bedarf` genutzt,
        damit Gruppenverantwortliche ihre Stammdaten sehen, ohne die Vorlage
        aendern zu duerfen.
        """
        if self.rechte.bereich(typ.bereich):
            return True
        if p is not None and self.rechte.darf_plan_bearbeiten(p, typ):
            return True
        return self.rechte.gruppen_verantwortlich(_plantyp_gruppen(self.s, typ.id))

    def stammdaten_holen(self, plantyp: str, plan: str | None = None) -> dict[str, Any]:
        """Stammdaten des Plantyps für den UI2-Editor — ohne PII (UI2).

        Rechte (ST3): Admin, Bereichsverantwortliche des Plantyps; mit
        konkreter Plan-ID zusätzlich Planverantwortliche; sonst Gruppen-
        verantwortliche einer an die Vorlage gebundenen Gruppe (lesend).
        Ausgeliefert werden ausschliesslich
        **deklarierte** Merkmale samt Werten (Union aller Versionen,
        jüngste Definition gewinnt je Schlüssel — genau was
        `merkmale_pflegen` als deklariert anerkennt), Personen mit
        Anzeigename, Kürzel und Gruppen, die eigenen Sammlungen und die
        eingebaute Sammlung `lieder` (ID, Titel, deklarierte Werte). Keine
        E-Mail-Adressen, keine Abwesenheitsgründe, keine nicht
        deklarierten Merkmale/Attribute. Planbezogene Sammlungen
        (Umfang `plan`) erscheinen nur mit ihrer konkreten Plan-ID und
        zeigen ausschliesslich die Einträge dieses Plans.
        ST3: Der Personenpool ist auf die gebundenen Gruppen beschränkt
        (siehe `DBDatenquelle`); `darf_vorlage_bearbeiten` sagt der UI, ob
        die Vorlage selbst geaendert werden darf.
        """
        typ = self._typ(plantyp, schreiben=False)
        # P1-14b: reiner LESEZUGRIFF — der Archiv-Schreibschutz in `_plan` darf
        # hier nicht greifen (sonst waere ein archivierter Plan unlesbar).
        p = self._plan(plan, schreiben=False)[0] if plan else None
        if not self._darf_stammdaten_lesen(typ, p):
            from diakronos_app.frappe_compat.exceptions import PermissionError
            raise PermissionError("Zugriff verweigert.")
        if p and p.plantyp != typ.id:
            fehler("/plan", "Plan und Plantyp passen nicht zusammen.")
        versionen = self.s.scalars(select(PlantypVersion).where(
            PlantypVersion.plantyp == typ.id).order_by(PlantypVersion.versionsnummer)).all()
        merkmale: dict[str, dict[str, dict[str, Any]]] = {}
        sammlungsdefs: dict[str, dict[str, Any]] = {}
        for v in versionen:  # aufsteigend: die jüngste Definition gewinnt je Schlüssel
            for ziel, ms in (v.definition.get("merkmale") or {}).items():
                if not isinstance(ziel, str) or not isinstance(ms, list):
                    continue
                ziel_map = merkmale.setdefault(ziel, {})
                for m in ms:
                    if isinstance(m, dict) and isinstance(m.get("id"), str):
                        ziel_map[m["id"]] = m
            for sam in v.definition.get("sammlungen") or []:
                if isinstance(sam, dict) and isinstance(sam.get("id"), str):
                    sammlungsdefs[sam["id"]] = sam
        quelle = self._quelle(typ, p)

        # UXP-R6: Auswahl-/Tag-Werte, die im Stammdaten-Panel unter
        # „Einstellungen → Hinzufügen" gepflegt wurden, liegen gemeindeweit in
        # ``pr_merkmal.definition.werte`` (der Plantyp liefert nur Startwerte).
        # Ohne diese Zusammenführung verschwand ein neu angelegter Wert („Cello")
        # nach dem Neuladen wieder, weil `stammdaten_holen` die Merkmale allein
        # aus den Plantyp-Versionen baute. Die gepflegte Gemeindeliste gewinnt;
        # die Startwerte kommen nur hinzu, wenn sie dort noch fehlen.
        gepflegte_werte: dict[tuple[str, str], list[Any]] = {}
        for m in self.s.scalars(select(Merkmal).where(
                Merkmal.ziel.like("sammlung:%"))).all():
            werte = (m.definition or {}).get("werte")
            if isinstance(werte, list):
                gepflegte_werte[(m.ziel.removeprefix("sammlung:"), m.schluessel)] = werte

        def werte_zusammenfuehren(sammlung: str, merkmal: dict[str, Any]) -> dict[str, Any]:
            gepflegt = gepflegte_werte.get((sammlung, merkmal.get("id", "")))
            if gepflegt is None:
                return merkmal
            start = merkmal.get("werte") if isinstance(merkmal.get("werte"), list) else []
            zusammengefuehrt = list(gepflegt) + [w for w in start if w not in gepflegt]
            return {**merkmal, "werte": zusammengefuehrt}

        def eigene_eintraege(key: str, samdef: dict[str, Any]) -> list[dict[str, Any]]:
            scope = p.id if samdef.get("umfang") == "plan" and p else None
            sam = self.s.scalar(select(Sammlung).where(
                Sammlung.schluessel == key, Sammlung.plan == scope))
            if sam is None:
                return []
            werte = {m.id: m.schluessel for m in self.s.scalars(select(Merkmal).where(
                Merkmal.ziel == "sammlung:" + key,
                Merkmal.schluessel.in_(list(merkmale.get(key, {}))))).all()}
            eintragswerte = {}
            if werte:
                for w in self.s.scalars(select(MerkmalWert).where(MerkmalWert.merkmal.in_(werte))).all():
                    eintragswerte.setdefault(w.ziel_id, {})[werte[w.merkmal]] = w.wert
            return [{"kennung": e.id, "titel": (e.daten or {}).get("titel", ""),
                     "daten": {"titel": (e.daten or {}).get("titel", "")},
                     "aktiv": e.aktiv, "reihenfolge": e.reihenfolge,
                     "merkmale": eintragswerte.get(e.id, {})}
                    for e in self.s.scalars(select(SammlungEintrag).where(
                        SammlungEintrag.sammlung == sam.id).order_by(
                        SammlungEintrag.reihenfolge, SammlungEintrag.id)).all()]

        def eintraege(schluessel: str) -> list[dict[str, Any]]:
            deklariert = set(merkmale.get(schluessel, {}))
            return [{"kennung": e.kennung, "titel": e.titel or "",
                     # ST2: eingebaute Attribute (Nummer/Buch/Seite) mitliefern,
                     # damit die Lieder-Pflege Titel und Nummer vorbelegen kann.
                     # LN1: zusaetzlich die Quelle (buch/kopie/ohne), damit die
                     # Pflege die richtige Auswahl vorbelegen kann.
                     "daten": {"titel": e.titel or "",
                               "gesangbuch_nummer": e.attribut("gesangbuch_nummer") or e.attribut("nummer") or "",
                               "buch": e.attribut("buch") or "",
                               "seite": e.attribut("seite") or "",
                               "quelle": e.attribut("quelle") or ""},
                     "merkmale": {k: w for k, w in e.merkmale.items()
                                  if k in deklariert and w is not None}}
                    for e in quelle.sammlung(schluessel)]
        deklariert_person = set(merkmale.get("person", {}))
        pool_keys, pool_inkl = self._pool_gruppen(typ)
        gruppen_namen = {g.kennung: (g.name or g.kennung) for g in quelle.gruppen()}

        def merkmale_je_ziel(ziel: str) -> list[dict[str, Any]]:
            """Merkmalsdeklarationen eines Ziels, Werte mit der Gemeindeliste gemischt."""
            liste = list(merkmale.get(ziel, {}).values())
            if ziel == "person":
                return liste
            return [werte_zusammenfuehren(ziel, m) for m in liste]

        return {
            "plantyp": {"id": typ.id, "name": typ.name, "bereich": typ.bereich},
            "darf_bearbeiten": True,
            "darf_vorlage_bearbeiten": self.rechte.darf_plantyp_bearbeiten(typ),
            "darf_globale_stammdaten_bearbeiten": self.rechte.bereich(typ.bereich),
            # ST3: Link 'Mitglieder der Gruppe verwalten' zeigt die UI nur
            # Berechtigten — Admin, Bereichsverantwortliche oder Gruppen-
            # verantwortliche einer gebundenen Gruppe.
            "darf_gruppen_verwalten": self.rechte.bereich(typ.bereich)
                or self.rechte.gruppen_verantwortlich(pool_keys),
            # ST3: an die Vorlage gebundene Gruppen (Personenpool) fuer den
            # Hinweis „Personen aus Gruppe … (n)" in der UI.
            "pool": {
                "gruppen": sorted(pool_keys),
                "namen": [gruppen_namen.get(g, g) for g in sorted(pool_keys)],
                "inkl_untergruppen": pool_inkl,
                "anzahl": len(quelle.personen()),
            },
            "definition": {"name": typ.name,
                           "merkmale": {ziel: merkmale_je_ziel(ziel) for ziel in merkmale},
                           "sammlungen": list(sammlungsdefs.values())},
            "merkmale": {ziel: merkmale_je_ziel(ziel) for ziel in merkmale},
            "personen": [{"kennung": x.kennung, "anzeige": x.name or x.kennung, "name": x.name,
                          "vorname": x.vorname, "nachname": x.nachname,
                          "kuerzel": x.kuerzel or x.merkmale.get("kuerzel") or "",
                          "gruppen": sorted(x.gruppen),
                          "merkmale": {k: w for k, w in x.merkmale.items()
                                       if k in deklariert_person and w is not None}}
                         for x in quelle.personen()],
            "gruppen": [{"kennung": g.kennung, "name": g.name or g.kennung,
                         "obergruppe": g.obergruppe or "", "mitglieder": sorted(g.mitglieder)}
                        for g in quelle.gruppen()],
            "sammlungen": [{"schluessel": key, "name": sam.get("name") or key,
                            "umfang": sam.get("umfang", "gemeinde"), "eintraege": eigene_eintraege(key, sam)}
                           for key, sam in sorted(sammlungsdefs.items())
                           # Plansammlung ohne Plan-ID bleibt unsichtbar (strict).
                           if p is not None or sam.get("umfang", "gemeinde") != "plan"],
            "lieder": self._lieder_mit_material(eintraege("lieder")),
            "plan": p.id if p else None,
        }

    def _lieder_mit_material(self, lieder: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """ST2: je Lied das Material der Standardfassung anhaengen.

        Die UI zeigt die Materialliste direkt in der Lieder-Pflege. Die Quelle
        bleibt Psalmos (``Lied Material`` an der Standardfassung); es werden
        nur Art, Stimme, Beschreibung und die Datei-URL/Name/Typ ausgeliefert.
        """
        from diakronos_app.models.diakonos import SichererAnhang
        if not lieder:
            return lieder
        namen = [l["kennung"] for l in lieder]
        fassungen = self.s.scalars(select(Liedfassung).where(
            Liedfassung.lied.in_(namen)).order_by(Liedfassung.lied, Liedfassung.ist_standard.desc())).all()
        # erste (Standard-)Fassung je Lied
        standard: dict[str, str] = {}
        for f in fassungen:
            standard.setdefault(f.lied, f.name)
        fassungs_ids = list(standard.values())
        if not fassungs_ids:
            for l in lieder:
                l["material"] = []
            return lieder
        # material_je_lied: Fassung -> Lied (statt lineare Suche je Zeile).
        lied_je_fassung = {fid: lied for lied, fid in standard.items()}
        # EINMAL lesen: die Zeilen tragen die Anhang-Kennungen bereits; ein
        # zweiter Lauf derselben Abfrage war unnoetig.
        material_zeilen = self.s.scalars(select(LiedMaterial).where(
            LiedMaterial.parent.in_(fassungs_ids),
            LiedMaterial.parentfield == "material").order_by(
            LiedMaterial.parent, LiedMaterial.idx)).all()
        anhang_namen = [r.anhang for r in material_zeilen if r.anhang]
        anhaenge = {a.name: a for a in self.s.scalars(select(SichererAnhang).where(
            SichererAnhang.name.in_(anhang_namen))).all()} if anhang_namen else {}
        material_je_lied: dict[str, list[dict[str, Any]]] = {}
        for r in material_zeilen:
            lied = lied_je_fassung.get(r.parent)
            if lied is None:
                continue
            a = anhaenge.get(r.anhang) if r.anhang else None
            material_je_lied.setdefault(lied, []).append({
                "art": r.art, "stimme": r.stimme, "beschreibung": r.beschreibung,
                # UXM-R8: Kennung der Kind-Zeile — das ist der Wert, den
                # lied_material_loeschen erwartet (nicht die Anhang-UUID).
                "material": r.name,
                "anhang": r.anhang,
                "dateiname": (a.dateiname if a else "") or "",
                "dateityp": (a.dateityp if a else "") or "",
                "datei": {"datei_url": (a.datei if a else "") or "",
                          "dateiname": (a.dateiname if a else "") or "",
                          "dateityp": (a.dateityp if a else "") or ""},
            })
        for l in lieder:
            l["material"] = material_je_lied.get(l["kennung"], [])
        return lieder

    def merkmal_kandidaten(self, plantyp: str, schluessel: str, plan: str | None = None) -> dict[str, Any]:
        """Personen-Kandidaten eines deklarierten Listen-Merkmals (ST2, Aufgabe 1).

        Ein Listen-Merkmal (z. B. ``merkmale.lieder.dirigent``) der Art
        ``person`` traegt eine ``rolle`` (z. B. ``{merkmal: 'dirigent'}``). Als
        Auswahl duerfen nur Personen erscheinen, die diese Rolle erfuellen —
        serverseitig gefiltert, damit die UI nichts Faelschliches anbietet.

        Rechte wie ``stammdaten_holen``: Admin bzw. Bereichsverantwortung des
        Plantyps, mit konkreter Plan-ID zusaetzlich der eigene
        Planverantwortliche. Ausgeliefert werden nur Name/Kuerzel/Gruppen und
        die deklarierten Personenmerkmale (keine E-Mail, keine Abwesenheits-
        gruende). Ist die Rolle keine Personen-Rolle oder gibt es niemanden,
        kommt eine leere Liste mit einem verstaendlichen ``hinweis`` zurueck.
        """
        typ = self._typ(plantyp, schreiben=False)
        # P1-14b: reiner LESEZUGRIFF (siehe `stammdaten_holen`).
        p = self._plan(plan, schreiben=False)[0] if plan else None
        if not self._darf_stammdaten_lesen(typ, p):
            from diakronos_app.frappe_compat.exceptions import PermissionError
            raise PermissionError("Zugriff verweigert.")
        if p and p.plantyp != typ.id:
            fehler("/plan", "Plan und Plantyp passen nicht zusammen.")

        sammlungsdefs: dict[str, dict[str, Any]] = {}
        person_merkmale: dict[str, dict[str, Any]] = {}
        for v in self.s.scalars(select(PlantypVersion).where(
                PlantypVersion.plantyp == typ.id).order_by(PlantypVersion.versionsnummer)).all():
            for sam in v.definition.get("sammlungen") or []:
                if isinstance(sam, dict) and isinstance(sam.get("id"), str):
                    sammlungsdefs[sam["id"]] = sam
            for m in (v.definition.get("merkmale") or {}).get("person") or []:
                if isinstance(m, dict) and isinstance(m.get("id"), str):
                    person_merkmale[m["id"]] = m

        # Definition des gesuchten Merkmals: der jüngste Eintrag je Schluessel gewinnt.
        definition_fuer: dict[str, Any] | None = None
        ziel = None
        for v in self.s.scalars(select(PlantypVersion).where(
                PlantypVersion.plantyp == typ.id).order_by(PlantypVersion.versionsnummer)).all():
            for ziel_key, ms in (v.definition.get("merkmale") or {}).items():
                if ziel_key == "person":
                    continue
                for m in ms or []:
                    if isinstance(m, dict) and m.get("id") == schluessel:
                        definition_fuer = m
                        ziel = ziel_key
        if definition_fuer is None:
            fehler("/schluessel", "Dieses Listen-Merkmal ist im Plantyp nicht deklariert.")
        art = definition_fuer.get("art")
        if art != "person":
            fehler("/schluessel", "Nur Personen-Merkmale haben Personenkandidaten.")
        rolle = definition_fuer.get("rolle")
        if not rolle:
            fehler("/schluessel", "Dieses Merkmal hat keine Rolle — es ist unklar, wer in Frage kommt.")

        from .engine.rollen import kandidaten as rollen_kandidaten
        quelle = self._quelle(typ, p)
        deklariert_person = set(person_merkmale)
        personen = rollen_kandidaten(rolle, quelle, self._neueste_definition(typ))

        # Verstaendlicher Hinweis bei leerer Auswahl (ST2, Aufgabe 1):
        # die UI zeigt ihn, statt ein leeres Auswahlfeld zu praesentieren.
        hinweis = ""
        if not personen:
            merkmal_id = rolle.get("merkmal") if isinstance(rolle, dict) else None
            mk = person_merkmale.get(merkmal_id, {}) if isinstance(merkmal_id, str) else {}
            merkmal_name = (mk or {}).get("name")
            hinweis = ("Noch niemand ist als " + (merkmal_name or "passend") +
                       " markiert — bitte zuerst die Fähigkeiten der Personen pflegen.")
        return {
            "schluessel": schluessel,
            "ziel": ziel,
            "art": art,
            "rolle": rolle,
            "kandidaten": [{
                "kennung": x.kennung,
                "anzeige": x.name or x.kennung,
                "name": x.name, "vorname": x.vorname, "nachname": x.nachname,
                "kuerzel": x.kuerzel or x.merkmale.get("kuerzel") or "",
                "gruppen": sorted(x.gruppen),
                "merkmale": {k: w for k, w in x.merkmale.items()
                             if k in deklariert_person and w is not None},
            } for x in personen],
            "hinweis": hinweis,
        }

    def _neueste_definition(self, typ: Plantyp) -> dict[str, Any]:
        """Jüngste Plantyp-Definition (fuer die Rollenauflösung)."""
        letzte = self.s.scalars(select(PlantypVersion).where(
            PlantypVersion.plantyp == typ.id).order_by(
            PlantypVersion.versionsnummer.desc())).first()
        return letzte.definition if letzte else {}

    # ── ST2: Lieder pflegen (Titel/Buch/Seite, Material, Tags) ─────────────

    def lied_rechte(self, plantyp: str | None = None,
                    plan: str | None = None) -> dict[str, Any]:
        """Schreibrecht für Lieder — EINE Wahrheit für die Sichtbarkeit der Knöpfe.

        ``lied_speichern`` prüft dieselbe Regel (``_darf_lieder_pflegen``).
        Die UI blendet damit nur aus, was der Server ohnehin verweigert; sie
        entscheidet nichts selbst. Bei plantyp UND plan wird der Kontext wie
        beim Lesen geprüft: fehlende oder unpassende Pläne sowie fehlende
        Leserechte liefern die üblichen 417/403-Fehler. Ohne Planbindung bleibt
        die Auskunft konservativ und verspricht kein abgelehntes Schreibrecht.
        """
        typ = None
        p = None
        if plantyp and plan:
            # Kontextgebundene Auskunft: Rechte vor Zuordnungsdetails pruefen.
            # Ohne Plan bleibt die bisherige konservative Knopf-Auskunft erhalten.
            typ = self._typ(plantyp, schreiben=False)
            p = self._plan(plan, schreiben=False)[0]
            if not self._darf_stammdaten_lesen(typ, p):
                from diakronos_app.frappe_compat.exceptions import PermissionError
                raise PermissionError("Zugriff verweigert.")
            if p.plantyp != typ.id:
                fehler("/plan", "Plan und Plantyp passen nicht zusammen.")
        elif plantyp:
            try:
                typ = self._typ(plantyp, schreiben=False)
            except DienstFehler:
                typ = None
        if typ is not None:
            try:
                self._darf_lieder_pflegen(typ, p)
                darf = True
            except Exception:  # noqa: BLE001
                darf = False
            hinweis = "" if darf else (
                "Für diese Lieder fehlt dir die Berechtigung. "
                "Schreibberechtigt sind Verantwortliche für Musik und Worship "
                "sowie Verantwortliche des Bereichs oder des Plans.")
        else:
            # Ohne Plantyp-Kontext: nur die Psalmos-Pflege zählt (die
            # Plandatenbank kann hier nicht befragt werden).
            from diakronos_app.api.psalmos.musik import _is_admin, _is_musikverantwortlicher
            darf = bool(_is_admin(self.benutzer) or _is_musikverantwortlicher(self.benutzer))
            hinweis = "" if darf else (
                "Für das Bearbeiten von Liedern fehlt dir die Berechtigung. "
                "Schreibberechtigt sind Verantwortliche für Musik und Worship.")
        return {"darf_schreiben": darf, "plantyp": typ.id if typ else None,
                "hinweis": hinweis}

    def _darf_lieder_pflegen(self, typ: Plantyp, p: Plan | None = None) -> None:
        """Recht zum Pflegen der Lieder einer Planvorlage (ST2, Aufgabe 2).

        Wie Psalmos-Liedpflege ODER Bereichsverantwortung der Planvorlage:
        erlaubt sind Musikverantwortliche (Psalmos) sowie Bereichs-/Plan-
        verantwortliche des Plantyps. Sonst 417 mit klarer Meldung.
        """
        from diakronos_app.api.psalmos.musik import _is_admin, _is_musikverantwortlicher
        if _is_admin(self.benutzer) or _is_musikverantwortlicher(self.benutzer):
            return
        if p is not None:
            if self.rechte.darf_plan_bearbeiten(p, typ):
                return
        elif self.rechte.bereich(typ.bereich):
            return
        fehler("/lied", "Keine Berechtigung zur Liedpflege.",
               code="rechte.lied")

    def _darf_lieder_pflegen_ohne_plantyp(self) -> None:
        """Liedpflege-Recht OHNE Planvorlage (UXM-R7).

        Genau die Psalmos-Regel, die `save_lied` prueft: Musikverantwortliche
        (Dienstbereich/Gruppe „Musik und Worship") oder Admins. Ein Plan-/
        Bereichsrecht gibt es hier nicht, weil kein Plantyp bekannt ist.
        """
        from diakronos_app.api.psalmos.musik import _is_admin, _is_musikverantwortlicher
        if _is_admin(self.benutzer) or _is_musikverantwortlicher(self.benutzer):
            return
        fehler("/lied", "Keine Berechtigung zur Liedpflege. Schreibberechtigt "
                        "sind Verantwortliche für Musik und Worship.",
               code="rechte.lied")

    def _datei_an_liedfassung_binden(self, datei_url: str, fassung: str) -> None:
        """Hochgeladene Datei an die Liedfassung haengen (UXM-R5).

        Der Upload (``upload_file``) legt die Datei ohne Bezug an; sie ist
        privat und damit nur fuer den Hochlader/Admin abrufbar. Mit
        ``attached_to_doctype='Liedfassung'`` erlaubt `files.serve_file` sie
        jedem, der das Lied sehen darf.

        Sicherheit (Review P1-10, Befund M1): Es wird NUR eine Datei gebunden,
        die im selben Vorgang vom angemeldeten Benutzer hochgeladen wurde.
        Sonst koennte jeder mit Musik-Schreibrecht eine fremde private Datei
        (deren URL er kennt) fuer alle angemeldeten Personen lesbar machen.
        Eine bereits anderweitig gebundene Datei bleibt unangetastet; ein
        Altbestand ohne Zuordnung wird ebenfalls nicht stillschweigend
        uebernommen (dort greift der Owner-Vergleich genauso).
        """
        from diakronos_app.models.core import FileModel
        zeile = self.s.scalar(select(FileModel).where(
            FileModel.file_url.in_([str(datei_url), "/private/files/" + str(datei_url).rsplit("/", 1)[-1]])))
        if zeile is None:
            return
        # Eigentuemerpruefung: nur die eigene Datei, Admin ausgenommen.
        from diakronos_app.api.psalmos.musik import _is_admin
        if not zeile.owner or (zeile.owner != self.benutzer and not _is_admin(self.benutzer)):
            fehler("/datei", "Diese Datei gehört nicht dir.",
                   code="datei.fremd")
        # Fremdzuordnung nicht ueberschreiben (eine Datei gehoert einer Sache).
        if ((zeile.attached_to_doctype and zeile.attached_to_doctype != "Liedfassung")
                or (zeile.attached_to_name and zeile.attached_to_name != fassung)):
            fehler("/datei", "Diese Datei ist bereits anderweitig zugeordnet.",
                   code="datei.gebunden")
        zeile.attached_to_doctype = "Liedfassung"
        zeile.attached_to_name = fassung

    def lied_speichern(self, plantyp: str, lied: str, daten: dict[str, Any],
                       plan: str | None = None) -> dict[str, Any]:
        """Lied umbenennen bzw. Nummer/Buch/Seite aendern (Psalmos = eine Wahrheit).

        Schreibt ausschliesslich die Psalmos-Lied-Tabelle. Erlaubte Felder:
        ``titel``, ``gesangbuch_nummer`` (Nummer), ``buch``, ``seite``,
        ``alternativtitel``, ``ccli_nummer``, ``notiz``. Ein leerer Titel wird
        abgelehnt.
        """
        from diakronos_app.frappe_compat import api_helpers as _sh
        typ = self._typ(plantyp, schreiben=False)
        p = self._plan(plan)[0] if plan else None
        if p and p.plantyp != typ.id:
            fehler("/plan", "Plan und Plantyp passen nicht zusammen.")
        self._darf_lieder_pflegen(typ, p)
        if self.s.get(Lied, lied) is None:
            fehler("/lied", "Lied nicht gefunden.")
        daten = daten or {}
        if "titel" in daten and not str(daten.get("titel") or "").strip():
            fehler("/titel", "Der Titel darf nicht leer sein.")
        # LN1: Quelle validieren, falls angegeben.
        if "quelle" in daten and daten.get("quelle") is not None:
            from . import lieder_pflege as _lp
            _lp.quelle_pruefen(daten.get("quelle"))
        erlaubt = ["titel", "alternativtitel", "gesangbuch_nummer", "buch",
                   "seite", "quelle", "ccli_nummer", "notiz"]
        werte = {k: daten[k] for k in erlaubt if k in daten}
        # ST3/Themen: Liedkategorien (Psalmos) setzen — eine Wahrheit. Sie
        # sind kein Freitextfeld der Lied-Tabelle, sondern Zuordnungen in
        # 'lied_kategorie'; deshalb hier separat behandelt.
        kategorien_gesetzt = "kategorien" in daten
        if not werte and not kategorien_gesetzt:
            fehler("/daten", "Keine aenderbaren Felder uebergeben.")
        if werte:
            _sh._update_doc("Lied", lied, werte)
        if kategorien_gesetzt:
            rohe = daten.get("kategorien")
            if not isinstance(rohe, list):
                fehler("/kategorien", "Kategorien als Liste erwarten.")
            self._lied_kategorien_setzen(lied, [str(k) for k in rohe])
        doc = _sh.get_doc("Lied", lied)
        return {"success": True, "lied": lied, "titel": doc.titel,
                "gesangbuch_nummer": doc.gesangbuch_nummer,
                "buch": doc.get("buch"), "seite": doc.get("seite"),
                "quelle": doc.get("quelle"),
                "kategorien": self._lied_kategorien(lied)}

    def _standardfassung(self, lied: str) -> Any:
        """Standardfassung eines Liedes; legt eine leere an, falls keine existiert."""
        from diakronos_app.frappe_compat import api_helpers as _sh
        fassungen = _sh.get_all("Liedfassung", filters={"lied": lied},
                                fields=["name"], order_by="ist_standard desc, name asc") or []
        for f in fassungen:
            doc = _sh.get_doc("Liedfassung", f["name"])
            if bool(doc.get("ist_standard")):
                return str(f["name"])
        if fassungen:
            return str(fassungen[0]["name"])
        return _sh._create("Liedfassung", {"lied": lied, "fassungsname": "Standardsatz",
                                           "ist_standard": True})

    def lied_material_hinzufuegen(self, plantyp: str | None, lied: str, art: str,
                                  dateiname: str, datei_url: str,
                                  stimme: str = "", beschreibung: str = "",
                                  plan: str | None = None) -> dict[str, Any]:
        """Material (Noten/Audio/Notensatz) an ein Lied haengen (ST2, Aufgabe 3).

        ``datei_url`` stammt aus einem vorherigen ``upload_file``. Es entsteht
        eine Child-Zeile ``Lied Material`` an der **Standardfassung** des
        Liedes (wird bei Bedarf angelegt) plus ein ``SichererAnhang``-Datensatz
        (Rueckverweis fuer die Loeschung). Die Datei selbst liegt bereits unter
        ``files_dir`` und wird ueber ``/files/<name>`` ausgeliefert.

        UXM-R7: OHNE Plantyp-Kontext (Aufruf aus dem Lied-Detail) prueft die
        Methode die Psalmos-Regel — dieselbe, die `save_lied` verwendet. Damit
        funktioniert „Hochladen" auch ohne Planvorlage.

        UXM-R5: Die hochgeladene Datei wird an die Liedfassung gebunden
        (``attached_to_doctype='Liedfassung'``), damit sie von allen, die das
        Lied sehen duerfen, geoeffnet werden kann (nicht nur vom Hochlader).
        """
        from diakronos_app.frappe_compat import api_helpers as _sh
        from diakronos_app.models.diakonos import SichererAnhang
        from . import lieder_pflege as lp

        typ = None
        p = None
        if plantyp:
            typ = self._typ(plantyp, schreiben=False)
            p = self._plan(plan)[0] if plan else None
            if p and p.plantyp != typ.id:
                fehler("/plan", "Plan und Plantyp passen nicht zusammen.")
            self._darf_lieder_pflegen(typ, p)
        else:
            self._darf_lieder_pflegen_ohne_plantyp()
        if self.s.get(Lied, lied) is None:
            fehler("/lied", "Lied nicht gefunden.")
        lp.material_art_pruefen(art)
        if not dateiname or not str(datei_url or "").strip():
            fehler("/datei", "Dateiname und Datei-URL sind erforderlich.")
        if lp.endung_von(dateiname) not in lp.MATERIAL_ARTEN[art]:
            fehler("/dateiname", f"Dateiendung passt nicht zur Material-Art {art!r}.")

        fassung = self._standardfassung(lied)
        self._datei_an_liedfassung_binden(datei_url, fassung)
        mime = lp.MATERIAL_MIME.get(lp.endung_von(dateiname), "")
        anhang = SichererAnhang(name=str(uuid4()), datei=str(datei_url),
                                dateiname=lp.dateiname_saeubern(dateiname),
                                dateityp=mime, beschreibung=beschreibung or None,
                                sichtbarkeits_ebene="Lieder",
                                owner=self.benutzer, modified_by=self.benutzer)
        self.s.add(anhang)
        self.s.flush()
        # Child-Zeile direkt anlegen (Frappe-Namen: <parent>-<hash>).
        zeilen = self.s.scalars(select(LiedMaterial).where(
            LiedMaterial.parent == fassung, LiedMaterial.parentfield == "material")).all()
        idx = (max([z.idx for z in zeilen], default=0) or 0) + 1
        row = LiedMaterial(name=f"{fassung}-m{idx}-{uuid4().hex[:6]}", parent=fassung,
                           parenttype="Liedfassung", parentfield="material", idx=idx,
                           art=art, stimme=stimme or None, anhang=anhang.name,
                           beschreibung=beschreibung or None, owner=self.benutzer)
        self.s.add(row)
        self.s.flush()
        return {"success": True, "fassung": fassung, "material": row.name,
                "art": art, "dateiname": anhang.dateiname, "datei_url": anhang.datei,
                "dateityp": mime, "stimme": row.stimme, "beschreibung": row.beschreibung}

    def lied_material_loeschen(self, plantyp: str | None, lied: str, material: str,
                               plan: str | None = None) -> dict[str, Any]:
        """Material eines Liedes entfernen (Child-Zeile + SichererAnhang-Spur).

        UXM-R7: Auch hier ist der Plantyp optional (Aufruf aus dem Lied-Detail);
        ohne ihn gilt die Psalmos-Regel.
        """
        from diakronos_app.models.diakonos import SichererAnhang
        if plantyp:
            typ = self._typ(plantyp, schreiben=False)
            p = self._plan(plan)[0] if plan else None
            if p and p.plantyp != typ.id:
                fehler("/plan", "Plan und Plantyp passen nicht zusammen.")
            self._darf_lieder_pflegen(typ, p)
        else:
            self._darf_lieder_pflegen_ohne_plantyp()
        zeile_m = self.s.get(LiedMaterial, material)
        if zeile_m is None:
            fehler("/material", "Material nicht gefunden.")
        fassung = self.s.get(Liedfassung, zeile_m.parent)
        if fassung is None or fassung.lied != lied:
            fehler("/material", "Material gehoert nicht zu diesem Lied.")
        anhang_name = zeile_m.anhang
        self.s.delete(zeile_m)
        self.s.flush()
        if anhang_name:
            rest = self.s.scalars(select(LiedMaterial).where(
                LiedMaterial.anhang == anhang_name)).first()
            if rest is None:
                anhang = self.s.get(SichererAnhang, anhang_name)
                if anhang is not None:
                    self.s.delete(anhang)
        return {"success": True}

    def sammlungsmerkmal_werte_pflegen(self, plantyp: str, schluessel: str, aktion: str,
                                       wert: str, neu: str | None = None,
                                       plan: str | None = None) -> dict[str, Any]:
        """Auswahl-/Tag-Werte eines Listen-Merkmals pflegen (ST2, Aufgabe 4).

        ``aktion`` ist ``hinzufuegen`` | ``umbenennen`` | ``entfernen``.
        Werte liegen gemeindeweit in ``pr_merkmal.definition.werte`` (der
        Plantyp liefert nur Startwerte). Umbenennen aktualisiert vorhandene
        Zuordnungen (``pr_merkmal_wert.wert``); Entfernen meldet, bei wie
        vielen Liedern der Wert noch verwendet wurde, und loescht die
        Zuordnungen. Aenderung wirkt auf alle Plantypen mit demselben
        Merkmals-Schluessel (gemeindeweit).
        """
        from . import lieder_pflege as lp
        typ = self._typ(plantyp, schreiben=False)
        p = self._plan(plan)[0] if plan else None
        if p is None:
            self.rechte.plantyp(typ)
        else:
            self._darf_lieder_pflegen(typ, p)
        # Merkmals-Schluessel und Sammlung aufloesen: das Listen-Merkmal
        # 'instrument' gehoert zur Sammlung 'lieder' (pr_merkmal.ziel =
        # 'sammlung:lieder'). Der Aufrufer nennt nur den Merkmals-Schluessel.
        mdef = None
        sammlung_key = None
        for v in self.s.scalars(select(PlantypVersion).where(
                PlantypVersion.plantyp == typ.id).order_by(PlantypVersion.versionsnummer)).all():
            for ziel_key, ms in (v.definition.get("merkmale", {}) or {}).items():
                if ziel_key == "person":
                    continue
                for mk in ms or []:
                    if isinstance(mk, dict) and mk.get("id") == schluessel:
                        mdef = mk
                        sammlung_key = ziel_key
        if mdef is None or sammlung_key is None:
            fehler("/schluessel", "Dieses Listen-Merkmal ist im Plantyp nicht deklariert.")
        # ST3-Themen-Vereinheitlichung: ein Merkmal mit quelle='psalmos.kategorie'
        # ist eine SICHT auf die Psalmos-Liedkategorien. Werte = Katalog
        # 'liedkategorie', Zuordnung = 'lied_kategorie' (eine Wahrheit).
        if mdef.get("quelle") == "psalmos.kategorie":
            return self._kategorie_werte_pflegen(schluessel, aktion, wert, neu)
        ziel = "sammlung:" + sammlung_key
        m = self.s.scalar(select(Merkmal).where(Merkmal.ziel == ziel, Merkmal.schluessel == schluessel))
        if m is None:
            m = Merkmal(ziel=ziel, schluessel=schluessel, art=mdef.get("art", "auswahl"),
                        definition=mdef, angelegt_durch_plantyp=typ.id, created_by=self.benutzer)
            self.s.add(m)
            self.s.flush()
        if m.art not in lp.WERT_ARTEN:
            fehler("/schluessel", "Nur Auswahl-/Tag-Merkmale haben pflegbare Werte.")
        definition = dict(m.definition or {})
        betroffen = 0

        def werte_im_wert(wert: Any) -> list[Any]:
            return list(wert) if isinstance(wert, list) else [wert]

        if aktion == "hinzufuegen":
            m.definition = lp.wert_hinzufuegen(definition, wert)
        elif aktion == "umbenennen":
            if not (neu or "").strip():
                fehler("/neu", "Der neue Wert darf nicht leer sein.")
            m.definition = lp.wert_umbenennen(definition, wert, str(neu))
            for w in self.s.scalars(select(MerkmalWert).where(MerkmalWert.merkmal == m.id)).all():
                enthalten = werte_im_wert(w.wert)
                if wert in enthalten:
                    betroffen += 1
                    # Mehrfach: nur den einen Wert ersetzen; Einzelwert: direkt.
                    if isinstance(w.wert, list):
                        w.wert = [str(neu) if x == wert else x for x in w.wert]
                    else:
                        w.wert = str(neu)
        elif aktion == "entfernen":
            m.definition = lp.wert_entfernen(definition, wert)
            for w in self.s.scalars(select(MerkmalWert).where(MerkmalWert.merkmal == m.id)).all():
                enthalten = werte_im_wert(w.wert)
                if wert in enthalten:
                    betroffen += 1
                    if isinstance(w.wert, list):
                        rest = [x for x in w.wert if x != wert]
                        if rest:
                            w.wert = rest
                        else:
                            self.s.delete(w)
                    else:
                        self.s.delete(w)
        else:
            fehler("/aktion", "Unbekannte Aktion. Erlaubt: hinzufuegen, umbenennen, entfernen.")
        self.s.flush()
        hinweis = ""
        if aktion == "entfernen" and betroffen:
            hinweis = (f"Der Wert wurde bei {betroffen} "
                       f"{'Lied' if betroffen == 1 else 'Liedern'} verwendet und dort entfernt.")
        return {"schluessel": schluessel, "art": m.art,
                "werte": list((m.definition or {}).get("werte") or []),
                "betroffen": betroffen, "hinweis": hinweis}

    def _kategorie_werte_pflegen(self, schluessel: str, aktion: str, wert: str,
                                 neu: str | None) -> dict[str, Any]:
        """Wertekatalog eines Kategorie-Merkmals pflegen (ST3/Themen).

        Werte sind die Psalmos-Liedkategorien (``liedkategorie``); die
        Zuordnung eines Liedes liegt in ``lied_kategorie``. Damit ist die
        Themen-Pflege in den Stammdaten EINE Wahrheit mit Psalmos:
        ``hinzufuegen`` legt eine Kategorie an, ``umbenennen`` benennt sie um
        (Zuordnungen bleiben), ``entfernen`` loescht Kategorie und
        Zuordnungen und meldet betroffene Lieder. Rechte: Liedpflege der
        Vorlage (siehe ``_darf_lieder_pflegen``).
        """
        import uuid as _uuid
        from diakronos_app.models.psalmos import LiedKategorie, Liedkategorie

        def katalog() -> list[str]:
            return [k.kategoriename or k.name for k in self.s.scalars(
                select(Liedkategorie).order_by(Liedkategorie.kategoriename)).all()]

        def finde_kategorie(name: str) -> Liedkategorie | None:
            return next((k for k in self.s.scalars(select(Liedkategorie)).all()
                         if (k.kategoriename or k.name) == name), None)

        if aktion == "hinzufuegen":
            wert = (wert or "").strip()
            if not wert:
                fehler("/wert", "Der Wert darf nicht leer sein.")
            if finde_kategorie(wert) is None:
                self.s.add(Liedkategorie(name=str(_uuid.uuid4()),
                                         kategoriename=wert, owner=self.benutzer))
                self.s.flush()
        elif aktion == "umbenennen":
            neu = (neu or "").strip()
            if not neu:
                fehler("/neu", "Der neue Wert darf nicht leer sein.")
            k = finde_kategorie(wert)
            if k is None:
                fehler("/wert", "Der Wert ist nicht vorhanden.")
            if finde_kategorie(neu) is not None and neu != wert:
                fehler("/neu", "Der neue Wert ist bereits vorhanden.")
            k.kategoriename = neu
        elif aktion == "entfernen":
            k = finde_kategorie(wert)
            if k is None:
                fehler("/wert", "Der Wert ist nicht vorhanden.")
            for zu in self.s.scalars(select(LiedKategorie).where(
                    LiedKategorie.kategorie == k.name)).all():
                self.s.delete(zu)
            self.s.delete(k)
        else:
            fehler("/aktion", "Unbekannte Aktion. Erlaubt: hinzufuegen, umbenennen, entfernen.")
        self.s.flush()
        return {"schluessel": schluessel, "art": "auswahl", "quelle": "psalmos.kategorie",
                "werte": [w for w in katalog() if w], "betroffen": 0, "hinweis": ""}

    def _lied_kategorien(self, lied: str) -> list[str]:
        """Aktuelle Liedkategorien-Namen eines Liedes (Psalmos)."""
        from diakronos_app.models.psalmos import LiedKategorie, Liedkategorie
        return [k.kategoriename for k in self.s.scalars(
            select(Liedkategorie).join(LiedKategorie, LiedKategorie.kategorie == Liedkategorie.name)
            .where(LiedKategorie.parent == lied,
                   LiedKategorie.parentfield == "kategorien")).all() if k]

    def _lied_kategorien_setzen(self, lied: str, kategorien: list[str]) -> None:
        """Setzt die Liedkategorien eines Liedes (Psalmos, eine Wahrheit).

        Vorhandene Zuordnungen des Liedes werden ersetzt; unbekannte
        Kategorienamen werden im Katalog angelegt (wie die Stammdaten-Pflege).
        """
        import uuid as _uuid
        from diakronos_app.models.psalmos import LiedKategorie, Liedkategorie

        def katalog() -> dict[str, Liedkategorie]:
            return {(k.kategoriename or k.name): k for k in self.s.scalars(select(Liedkategorie)).all()}

        namen = [str(k) for k in (kategorien or []) if str(k).strip()]
        kat = katalog()
        for n in namen:
            if n not in kat:
                neu = Liedkategorie(name=str(_uuid.uuid4()), kategoriename=n, owner=self.benutzer)
                self.s.add(neu)
                self.s.flush()
                kat[n] = neu
        for zu in self.s.scalars(select(LiedKategorie).where(
                LiedKategorie.parent == lied, LiedKategorie.parentfield == "kategorien")).all():
            self.s.delete(zu)
        self.s.flush()
        for idx, n in enumerate(namen):
            self.s.add(LiedKategorie(
                name=f"{lied}-kat{idx}-{_uuid.uuid4().hex[:6]}", parent=lied, parenttype="Lied",
                parentfield="kategorien", idx=idx, kategorie=kat[n].name, owner=self.benutzer))
        self.s.flush()

    def plan_anlegen(self, plantyp: str, titel: str, von: date, bis: date,
                     parameter: dict[str, Any] | None = None, verantwortlich: str | None = None) -> dict[str, Any]:
        """Erzeugt Termine je Gültigkeitsintervall und fixiert deren Versionsbindung."""
        # ST3: Plan anlegen reicht mit Bereichsverantwortung ODER Gruppen-
        # verantwortung der gebundenen Gruppe(n); die Vorlage selbst zu
        # aendern bleibt Bereich/Admin vorbehalten.
        typ = self._typ(plantyp, schreiben=False)
        if not self.rechte.darf_plan_anlegen(typ):
            from diakronos_app.frappe_compat.exceptions import PermissionError
            raise PermissionError("Zugriff verweigert.")
        if bis < von or (bis - von).days > 3660:
            fehler("/zeitraum", "Zeitraum muss geordnet und höchstens zehn Jahre lang sein.")
        if not isinstance(parameter or {}, dict) or not isinstance(titel, str) or not titel or len(titel) > 280:
            fehler("/plan", "Titel und Parameter sind ungültig.")
        if verantwortlich and self.s.get(Mitglied, verantwortlich) is None:
            fehler("/verantwortlich", "Mitglied nicht gefunden.")
        versionen = self.s.scalars(select(PlantypVersion).where(PlantypVersion.plantyp == typ.id).order_by(
            PlantypVersion.gueltig_ab, PlantypVersion.versionsnummer)).all()
        if speicher.gueltige_version_zu_datum(self.s, typ.id, von) is None:
            fehler("/von", "Keine Plantyp-Version zu Beginn gültig.")
        p = Plan(plantyp=typ.id, titel=titel, zeitraum_von=von, zeitraum_bis=bis,
                 parameter=parameter or {}, verantwortlich=verantwortlich, created_by=self.benutzer)
        self.s.add(p)
        self.s.flush()
        quelle = self._quelle(typ, p)
        paare: list[tuple[EngineTermin, Termin]] = []
        for v in versionen:
            for sam in v.definition.get("sammlungen", []):
                if sam.get("umfang") == "plan":
                    self._sammlung_anlegen(sam, p)
            for ts in self._erzeuge_termine(v.definition, p.parameter, quelle, von=von, bis=bis).values():
                for t in ts:
                    if not von <= t.datum <= bis:
                        continue
                    if speicher.gueltige_version_zu_datum(self.s, typ.id, t.datum).id != v.id:
                        continue
                    dbt = Termin(plan=p.id, datum=t.datum, uhrzeit=t.uhrzeit, titel=t.name,
                                 anlaesse=t.anlass_liste, quelle=t.quelle or "manuell", plantyp_version=v.id,
                                 reihe=t.reihe, index=t.index, positionsnr_im_monat=t.positionsnr_im_monat,
                                 position_von_hinten=t.position_von_hinten, ablauf=t.ablauf, created_by=self.benutzer)
                    self.s.add(dbt)
                    paare.append((t, dbt))
        self.s.flush()
        zuordnung = {t: dbt for t, dbt in paare}
        for t, dbt in paare:
            dbt.bezug = zuordnung[t.bezug].id if t.bezug in zuordnung else None
        self._verlauf("plan_anlegen", None, self._stand(p), plan=p)
        return zeile(p)

    def _kontext(self, p: Plan) -> tuple[list[Termin], dict[str, EngineTermin], list[EngineEintrag]]:
        ts = self.s.scalars(select(Termin).where(Termin.plan == p.id).order_by(Termin.datum, Termin.reihe)).all()
        em = {t.id: EngineTermin(t.datum, t.reihe, t.uhrzeit, t.titel or "", frozenset(t.anlaesse),
                                index=t.index, quelle=t.quelle, positionsnr_im_monat=t.positionsnr_im_monat,
                                position_von_hinten=t.position_von_hinten, ablauf=deepcopy(t.ablauf),
                                variante=t.variante) for t in ts}
        for t in ts:
            em[t.id].bezug = em.get(t.bezug)
        es = self.s.scalars(select(Eintrag).join(Termin, Eintrag.termin == Termin.id).where(Termin.plan == p.id)).all()
        return ts, em, [EngineEintrag(e.feld_pfad, e.wert, "text", em[e.termin], e.fixiert,
                                     e.quelle if e.fixiert else "generator") for e in es]

    def termin_struktur(self, plan: str, termin: str) -> dict[str, Any]:
        p, _, bearbeiten = self._plan(plan, False)
        if not bearbeiten:
            stand = p.veroeffentlichter_stand
            t = next((t for t in stand["termine"] if t["id"] == termin), None)
            if t is None:
                fehler("/termin", "Termin nicht gefunden.")
            return {"termin": t, "version": zeile(self.s.get(PlantypVersion, t["plantyp_version"]))}
        ts, em, es = self._kontext(p)
        t = next((t for t in ts if t.id == termin), None)
        if t is None:
            fehler("/termin", "Termin gehört nicht zum Plan.")
        v = self.s.get(PlantypVersion, t.plantyp_version)
        return {"termin": zeile(t), "version": zeile(v), "slots": [asdict(s) for s in
                aufloesen_mit_eintraegen(v.definition, em[t.id], es, parameter=p.parameter)]}

    def termin_strukturen(self, plan: str) -> dict[str, Any]:
        """Alle Termin-Strukturen eines Plans in EINEM Aufruf (PF1).

        Die Planseite brauchte je Termin einen eigenen ``termin_struktur``-
        Aufruf; jeder lud den kompletten Plan-Kontext neu (Termine, Eintraege,
        Version). Bei 56 Terminen waren das 56 HTTP-Runden und 56x dieselbe
        Arbeit. Hier wird der Kontext EINMAL geladen und je Termin nur noch
        aufgeloest. Ergebnisform je Eintrag ist identisch zu
        ``termin_struktur`` (``termin``/``version``/``slots``), damit die
        Oberflaeche nichts umbauen muss.
        """
        p, _, bearbeiten = self._plan(plan, False)
        if not bearbeiten:
            stand = p.veroeffentlichter_stand or {}
            versionen: dict[Any, Any] = {}
            strukturen: list[dict[str, Any]] = []
            for t in stand.get("termine") or []:
                vid = t.get("plantyp_version")
                if vid not in versionen:
                    versionen[vid] = zeile(self.s.get(PlantypVersion, vid))
                strukturen.append({"termin": t, "version": versionen[vid]})
            return {"plan": p.id, "strukturen": strukturen}
        ts, em, es = self._kontext(p)
        # Version einmal je plantyp_version laden (nicht je Termin).
        versionen = {v.id: zeile(v) for v in self.s.scalars(select(PlantypVersion).where(
            PlantypVersion.id.in_({t.plantyp_version for t in ts}))).all()}
        strukturen = []
        for t in ts:
            von = versionen.get(t.plantyp_version) or {}
            definition = von.get("definition")
            slots = [asdict(s) for s in
                     aufloesen_mit_eintraegen(definition, em[t.id], es, parameter=p.parameter)] \
                if definition else []
            strukturen.append({"termin": zeile(t), "version": von, "slots": slots})
        return {"plan": p.id, "strukturen": strukturen}

    def plan_stand_version(self, plan: str) -> dict[str, Any]:
        """Billiger Versionsstempel des Plan-Stands (PF1, Browser-Cache).

        Liefert einen Hash aus ``modified`` aller Termine/Einträge des Plans
        plus deren Anzahl. Der Browser vergleicht damit seinen Cache-Stand und
        laedt nur bei echter Aenderung neu (stale-while-revalidate). Kosten:
        zwei Zaehl-/Maximalabfragen statt des vollen ``plan_holen``.
        """
        p, _, bearbeiten = self._plan(plan, False)
        if not bearbeiten:
            stand = p.veroeffentlichter_stand or {}
            plan_teil = stand.get("plan") or {}
            roh = jsonwert({
                "p": p.id, "m": plan_teil.get("modified"), "st": plan_teil.get("status"),
                "n": len(stand.get("termine") or []), "e": len(stand.get("eintraege") or []),
            })
        else:
            termin_max, termin_n = self.s.execute(
                select(func.max(Termin.modified), func.count(Termin.id)).where(Termin.plan == p.id)
            ).one()
            eintrag_max, eintrag_n = self.s.execute(
                select(func.max(Eintrag.modified), func.count(Eintrag.id))
                .join(Termin, Eintrag.termin == Termin.id).where(Termin.plan == p.id)
            ).one()
            roh = jsonwert({"p": p.id, "m": p.modified, "st": p.status,
                            "tm": termin_max, "tn": termin_n or 0,
                            "em": eintrag_max, "en": eintrag_n or 0})
        version = hashlib.sha256(
            json.dumps(roh, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:32]
        return {"plan": p.id, "version": version, "darf_bearbeiten": bearbeiten}

    def plan_holen(self, plan: str) -> dict[str, Any]:
        p, typ, bearbeiten = self._plan(plan, False)
        # P1-14b: Ein archivierter Plan ist auch fuer Mitglieder nicht mehr
        # sichtbar — der Aushang ist abgehaengt. Bearbeiter (Planer) sehen ihn
        # weiterhin, damit sie ihn zurueckholen oder einsehen koennen.
        if p.status == "archiviert" and not bearbeiten:
            fehler("/plan", "Dieser Plan ist archiviert und nicht mehr einsehbar.",
                   "plan.archiviert")
        stand = {**zeile(p), **self._stand(p)} if bearbeiten else deepcopy(p.veroeffentlichter_stand)
        # P1-11b M1/UXP-R19: Bei aelteren, schon veroeffentlichten Staenden (vor
        # der Schwärzung beim Veroeffentlichen) kann die Spalte `meldungen`
        # noch im Snapshot stehen. Hier defensiv entfernen, damit kein
        # Nicht-Bearbeitungs-Zugriff interne Regelpruefungen leckt.
        if not bearbeiten and stand:
            for e in stand.get("eintraege", ()):
                e.pop("meldungen", None)
        quelle = self._quelle(typ, p)
        paare: list[tuple[EngineTermin, dict[str, Any]]] = []
        eintraege: list[EngineEintrag] = []
        # Versionen gebuendelt laden: die Definition haengt nur an der Version,
        # nicht am Termin. Vorher lief je Termin ein eigenes `get` (N+1).
        versionen = {v.id: v.definition for v in self.s.scalars(select(PlantypVersion).where(
            PlantypVersion.id.in_({t["plantyp_version"] for t in stand["termine"]}))).all()}
        # Eintraege einmal nach Termin indexieren: der innere Vergleich war
        # vorher O(Termine x Eintraege) (56 x 840 = 47k Vergleiche).
        eintraege_je_termin: dict[Any, list[dict[str, Any]]] = {}
        for e in stand["eintraege"]:
            eintraege_je_termin.setdefault(e["termin"], []).append(e)
        for t in stand["termine"]:
            definition = versionen[t["plantyp_version"]]
            et = EngineTermin(date.fromisoformat(t["datum"]), t["reihe"],
                              anlaesse=frozenset(t["anlaesse"]), index=t["index"],
                              positionsnr_im_monat=t["positionsnr_im_monat"],
                              position_von_hinten=t["position_von_hinten"], ablauf=deepcopy(t["ablauf"]),
                              variante=t.get("variante"))
            paare.append((et, definition))
            eintraege.extend(EngineEintrag(e["feld_pfad"], e["wert"], "text", et)
                             for e in eintraege_je_termin.get(t["id"], ()))
        anzeige = self._anzeige_aus(paare, eintraege, quelle, stand["plan"]["parameter"])
        return {**stand, "darf_bearbeiten": bearbeiten, "anzeige": anzeige}

    def _anzeige_aus(self, paare: list[tuple[Any, dict[str, Any]]], eintraege: list[Any],
                     quelle: Any, parameter: dict[str, Any]) -> dict[str, Any]:
        """Kennungsmap für eingeteilte Werte — Plan-Stand und Trockenlauf.

        ``paare`` sind Engine-Termine mit ihrer aktiven Definition,
        ``eintraege`` die zugehörigen Engine-Einträge. Personen liefern
        Name und Kürzel, Teams ihren Namen, Sammlungseinträge den
        minimierten Formatkontext (deklarierte Attribute) — identisch zu
        `plan_holen` (UI1) und ohne PII.
        """
        # AUSTRITT-d (NB1): ANZEIGE, nicht Zuteilbarkeit — die Namen der
        # Ausgetretenen gehoeren hierher, sonst faellt die Oberflaeche auf die
        # Kennung zurueck. Gekuerzt sind sie schon in der Person.
        personen = {x.kennung: x for x in quelle.personen_anzeige()}
        teams = {x.kennung: x for x in quelle.gruppen()}
        anzeige: dict[str, Any] = {}
        # Eintraege je Termin einmal indexieren (vorher: O(Paare x Eintraege)).
        nach_termin: dict[Any, list[Any]] = {}
        for e in eintraege:
            nach_termin.setdefault(e.termin, []).append(e)
        # Sammlungsnachschlag einmal je Sammlung aufbauen (vorher: lineare Suche
        # je Wert — O(Werte x Sammlungseintraege)).
        sammlung_index: dict[str, dict[str, Any]] = {}
        for et, definition in paare:
            eigene = nach_termin.get(et, [])
            slots = {s.feld_pfad: s for s in aufloesen_mit_eintraegen(
                definition, et, eigene, parameter=parameter)}
            for e in eigene:
                slot = slots.get(e.feld_pfad)
                if slot is None:
                    continue
                for wert in (e.wert if isinstance(e.wert, list) else [e.wert]):
                    if not isinstance(wert, str):
                        continue
                    if slot.art in ("person", "personen") and wert in personen:
                        x = personen[wert]
                        anzeige[wert] = {"kennung": wert, "name": x.name, "anzeige": x.name,
                                         "vorname": x.vorname,
                                         "kuerzel": x.kuerzel or x.merkmale.get("kuerzel") or ""}
                    elif slot.art == "team" and wert in teams:
                        anzeige[wert] = {"kennung": wert, "name": teams[wert].name}
                    elif slot.art == "eintrag":
                        schluessel = slot.sammlung or ""
                        if schluessel not in sammlung_index:
                            sammlung_index[schluessel] = {
                                x.kennung: x for x in quelle.sammlung(schluessel)}
                        x = sammlung_index[schluessel].get(wert)
                        if x:
                            anzeige[wert] = self._sammlungsanzeige(x, definition, slot.sammlung)
        return anzeige

    def ablauf_aendern(self, plan: str, termin: str, feld: str, aktion: str,
                       element_typ: str | None = None, element_id: str | None = None,
                       position: int | None = None) -> dict[str, Any]:
        """Ändert aktive Ablauf-Strukturen mit stabilen IDs und gemeinsamem Undo."""
        p, _, _ = self._plan(plan)
        ts, em, es = self._kontext(p)
        t = next((t for t in ts if t.id == termin), None)
        if t is None:
            fehler("/termin", "Termin gehört nicht zum Plan.")
        definition = self.s.get(PlantypVersion, t.plantyp_version).definition
        def ablaeufe(felder: list[dict[str, Any]]) -> list[dict[str, Any]]:
            result = []
            for f in felder:
                if f.get("art") == "ablauf":
                    result.append(f)
                result.extend(ablaeufe(f.get("inhalt", [])))
                for zweig in f.get("varianten", []) + f.get("teile", []):
                    if isinstance(zweig, dict):
                        result.extend(ablaeufe(zweig.get("inhalt", [])))
            return result

        felder = list(definition.get("felder", []))
        for reihe in definition.get("terminreihen", []):
            felder.extend(reihe.get("felder", []))
        deklaration = next((f for f in ablaeufe(felder) if f["id"] == feld.split(":")[-1].split(".")[-1]), None)
        if deklaration is None:
            fehler("/feld", "Aktives Ablauf-Feld erforderlich.")
        probe = deepcopy(em[t.id])
        probe.ablauf[feld] = [{"id": "ui1-probe-" + str(i), "typ": e["typ"]}
                             for i, e in enumerate(deklaration["elemente"])]
        if not any(s.feld_pfad.startswith(feld + "/ui1-probe-") for s in
                   aufloesen_mit_eintraegen(definition, probe, [], parameter=p.parameter)):
            fehler("/feld", "Ablauf ist in dieser Terminstruktur nicht aktiv.")
        vorher = self._stand(p)
        ablauf = deepcopy(t.ablauf or {})
        elemente = ablauf.setdefault(feld, [])
        if position is not None and (isinstance(position, bool) or not isinstance(position, int)
                                     or not 0 <= position <= len(elemente)):
            fehler("/position", "Position liegt außerhalb des Ablaufs.")
        if aktion == "hinzufuegen":
            if element_typ not in {e["typ"] for e in deklaration.get("elemente", [])}:
                fehler("/element_typ", "Elementtyp ist nicht deklariert.")
            element_id = str(uuid4())
            elemente.insert(len(elemente) if position is None else position,
                            {"id": element_id, "typ": element_typ})
        elif aktion in ("verschieben", "loeschen"):
            element = next((e for e in elemente if e["id"] == element_id), None)
            if element is None:
                fehler("/element_id", "Element gehört nicht zum Ablauf.")
            if aktion == "verschieben" and position is None:
                fehler("/position", "Zielposition erforderlich.")
            elemente.remove(element)
            if aktion == "verschieben":
                elemente.insert(position, element)
            else:
                prefix = feld + "/" + element_id + "."
                for e in self.s.scalars(select(Eintrag).where(Eintrag.termin == t.id)).all():
                    if e.feld_pfad.startswith(prefix):
                        self.s.delete(e)
        else:
            fehler("/aktion", "Unbekannte Ablauf-Aktion.")
        t.ablauf = ablauf
        gruppe = self._schreibabschluss(p, vorher, "ablauf_aendern")
        return {"element_id": element_id, "ablauf": ablauf, "gruppe_id": gruppe}

    #: Einstufung der Bedarfsprüfung -> öffentliche Stufe (UI1).
    _BEDARF_STUFEN = {"ok": "hinweis", "eingeschraenkt": "sollte", "blockiert_automatik": "muss"}

    def feld_kandidaten(self, plan: str, termin: str, feld_pfad: str) -> dict[str, Any]:
        """Rollengefilterte Kandidaten mit sicheren Anzeigedaten (UI1).

        Nur Plan-Editor (sonst 403). Jeder Kandidat trägt die Engine-
        Regelbewertung (``regeln.auswertung.bewerte_alle``) dieses Slots;
        Personen zusätzlich den Abwesenheits-Status **ohne** Grund. Es
        verlassen keine E-Mail-Adressen, keine nicht deklarierten
        Merkmalsinhalte und keine Abwesenheitsgründe die Antwort.
        """
        p, typ, _ = self._plan(plan)  # Bearbeitungsrecht, sonst 403.
        ts, em, es = self._kontext(p)
        t = next((t for t in ts if t.id == termin), None)
        if t is None:
            fehler("/termin", "Termin gehört nicht zum Plan.")
        definition = self.s.get(PlantypVersion, t.plantyp_version).definition
        slots = aufloesen_mit_eintraegen(definition, em[t.id], es, parameter=p.parameter)
        slot = next((s for s in slots if s.feld_pfad == feld_pfad), None)
        if slot is None:
            fehler("/feld_pfad", "Feldpfad ist in der aktiven Terminstruktur nicht vorhanden.")
        quelle = self._quelle(typ, p)
        kandidaten = self._feld_kandidaten(slot, definition, quelle, em[t.id], es, p)
        meldungen = self._feld_meldungen(definition, quelle, slot)
        if not kandidaten and slot.art in ("person", "personen", "team", "eintrag"):
            meldungen.append({"stufe": "sollte", "code": "kandidaten.leer",
                              "meldung": f"Feld {feld_pfad!r} hat keine Kandidaten."})
        return {"feld_pfad": feld_pfad, "art": slot.art,
                "kandidaten": kandidaten, "meldungen": meldungen}

    def _feld_kandidaten(self, slot: Any, definition: dict[str, Any], quelle: Any,
                         em_termin: Any, es: list[Any], p: Plan) -> list[dict[str, Any]]:
        from .engine.rollen import kandidaten as rollen_kandidaten
        from .regeln.auswertung import Kontext, bewerte_alle, historie_laden, index_aufbauen

        if slot.art == "auswahl":
            return [w for w in slot.feld.get("werte", [])]
        if slot.art not in ("person", "personen", "team", "eintrag"):
            return []
        # Globale Zeitraumregeln brauchen den ganzen Plan und sind hier nicht
        # je Kandidat sinnvoll — dieselben Ausnahmen wie pruefe_plan.
        regeln = [r for r in definition.get("regeln", []) if isinstance(r, dict)
                  and r.get("baustein") not in ("min_pro_zeitraum", "gleich_verteilen")]
        historie = historie_laden(definition, quelle, em_termin.datum)
        basis = Kontext(definition, em_termin, quelle, p.parameter or {}, es, historie)
        index_aufbauen(basis)
        vorhanden = next((e for e in es if e.termin is em_termin and e.feld_pfad == slot.feld_pfad), None)

        def bewerten(wert: Any) -> dict[str, Any]:
            k = Kontext(definition, em_termin, quelle, p.parameter or {}, es, historie)
            k.historie_werte, k.haeufigkeit = basis.historie_werte, basis.haeufigkeit
            k.historie_fremd = basis.historie_fremd
            k.sammlungsindex, k.ausgeschlossen = basis.sammlungsindex, vorhanden
            b = bewerte_alle(wert, slot, k, regeln)
            return {"zulaessig": b.zulaessig, "strafe": round(b.strafe, 3), "meldungen": list(b.meldungen)}

        if slot.art in ("person", "personen"):
            deklariert = {m.get("id") for m in (definition.get("merkmale", {}).get("person") or [])
                          if isinstance(m, dict)}
            abwesende = {a.person for a in quelle.abwesenheiten(em_termin.datum, em_termin.datum)}
            return [{"kennung": x.kennung, "anzeige": x.name or x.kennung,
                     "name": x.name, "vorname": x.vorname, "nachname": x.nachname,
                     "kuerzel": x.kuerzel or x.merkmale.get("kuerzel") or "",
                     "abwesend": x.kennung in abwesende,
                     "merkmale": {k: w for k, w in x.merkmale.items() if k in deklariert and w is not None},
                     "bewertung": bewerten(x.kennung)}
                    for x in rollen_kandidaten(slot.rolle, quelle, definition, parameter=p.parameter)]
        if slot.art == "team":
            return [{"kennung": g.kennung, "anzeige": g.name or g.kennung,
                     "mitglieder": len(g.mitglieder), "bewertung": bewerten(g.kennung)}
                    for g in self._team_kandidaten(slot, quelle)]
        # eintrag: Anzeigedaten des Sammlungseintrags, Merkmale nur deklariert.
        deklariert = {m.get("id") for m in (definition.get("merkmale", {}).get(
            slot.sammlung or "") or []) if isinstance(m, dict)}
        return [{**self._sammlungsanzeige(e, definition, slot.sammlung),
                 "anzeige": e.titel or e.kennung,
                 "merkmale": {k: w for k, w in e.merkmale.items() if k in deklariert and w is not None},
                 "bewertung": bewerten(e.kennung)}
                for e in quelle.sammlung(slot.sammlung or "")]

    @staticmethod
    def _sammlungsanzeige(e: Any, definition: dict[str, Any], sammlung: str | None) -> dict[str, Any]:
        """Gleicher, minimierter Formatkontext für Kandidaten und eingeteilte Werte.

        Freie Attribute nur bei Deklaration als Sammlungsmerkmal; kein
        ungefiltertes Attribut-/Merkmalsobjekt. attribut() gibt gepflegten
        Merkmalen Vorrang vor Stammdaten. Personenmerkmale bleiben unberührt.
        """
        deklariert = {m["id"] for m in (definition.get("merkmale", {}).get(sammlung or "") or [])
                      if isinstance(m, dict) and isinstance(m.get("id"), str)}
        reserviert = {"kennung", "titel", "anzeige", "merkmale", "bewertung"}
        buch = e.attribut("buch") or ""
        nummer = e.attribut("nr") or e.attribut("nummer") or e.attribut("gesangbuch_nummer") or ""
        seite = e.attribut("seite") or ""
        quelle = e.attribut("quelle") or ""
        from .lieder_pflege import anzeige_text
        return {**{k: e.attribut(k) for k in deklariert - reserviert if e.attribut(k) is not None},
                "kennung": e.kennung, "titel": e.titel or "",
                "buch": buch,
                "quelle": quelle,
                # LN1: fertige Kennung ('Kopie'/'JN 1297'/'WH S. 150'/'') —
                # nie ein 'Nr.' ohne Nummer.
                "anzeige": anzeige_text(quelle, buch, nummer, seite, e.titel),
                "nr": nummer,
                "seite": seite}

    @staticmethod
    def _team_kandidaten(slot: Any, quelle: Any) -> list[Any]:
        """Team-Quellen wie der Generator (engine/fuellen.py): Liste oder Untergruppe."""
        if isinstance(slot.teams, list):
            bekannt = {g.kennung: g for g in quelle.gruppen()}
            return [bekannt[str(k)] for k in slot.teams if str(k) in bekannt]
        if isinstance(slot.teams, dict):
            return [g for g in quelle.gruppen() if g.obergruppe == slot.teams.get("gruppe_unter")]
        return []

    def _feld_meldungen(self, definition: dict[str, Any], quelle: Any, slot: Any) -> list[dict[str, Any]]:
        """Bedarfswarnungen der Engine (bedarfspruefung), auf das Feld begrenzt."""
        from .engine.bedarf import bedarfspruefung
        relevant: set[tuple[str, str]] = set()
        if slot.art == "eintrag":
            relevant.add(("sammlung", slot.sammlung or ""))
        elif slot.art in ("person", "personen"):
            relevant |= self._rollen_bedarfe(slot.rolle, definition)
        return [{"stufe": self._BEDARF_STUFEN.get(b.einstufung, "hinweis"),
                 "code": f"bedarf.{b.art}",
                 "meldung": b.abdeckung + (f" — {b.detail}" if b.detail else ""),
                 "art": b.art, "kennung": b.kennung, "einstufung": b.einstufung}
                for b in bedarfspruefung(definition, quelle) if (b.art, b.kennung) in relevant]

    @staticmethod
    def _rollen_bedarfe(rolle: Any, definition: dict[str, Any]) -> set[tuple[str, str]]:
        """Rollen- und Merkmalsbedarfe einer Feld-Rolle (inkl. @Referenzen)."""
        bedarfe: set[tuple[str, str]] = set()
        gesehen: set[str] = set()

        def sammle(f: Any) -> None:
            if isinstance(f, str) and f.startswith("@"):
                if f[1:] not in gesehen:
                    gesehen.add(f[1:])
                    bedarfe.add(("rolle", f[1:]))
                    for r in definition.get("rollen") or []:
                        if isinstance(r, dict) and r.get("id") == f[1:]:
                            sammle(r.get("filter"))
            elif isinstance(f, dict):
                if isinstance(f.get("merkmal"), str):
                    bedarfe.add(("merkmal", f["merkmal"]))
                for kind in list(f.get("alle") or []) + list(f.get("eine") or []):
                    sammle(kind)
                sammle(f.get("nicht"))

        sammle(rolle)
        return bedarfe

    def plan_generieren(self, plan: str, nur_vorschau: bool = False, seed: int = 0,
                        nur_luecken: bool = False) -> dict[str, Any]:
        """Nur Entwurf generieren; fixierte Slots und Vorschau bleiben unangetastet.

        UXP-R16: ``nur_luecken`` laesst gefuellte, regelkonforme Werte
        unangetastet und aendert nur, was fehlt oder eine Regel verletzt — der
        Planer aendert nach einer Abwesenheit nicht mehr den ganzen Plan.
        ``plan_entwurf`` oeffnet einen veroeffentlichten Plan als Entwurf (dafuer
        macht man sonst irgendeine kleine Aenderung von Hand).
        """
        p, typ, _ = self._plan(plan)
        if p.status != "entwurf":
            fehler("/status", "Veröffentlichten Plan zuerst durch manuelle Bearbeitung zum Entwurf machen.")
        vorher = self._stand(p)
        ts, em, es = self._kontext(p)
        quelle = self._quelle(typ, p)
        diff, meldungen, verstoesse = [], [], []
        alt = {(e["termin"], e["feld_pfad"]): e for e in vorher["eintraege"]}
        for vid in dict.fromkeys(t.plantyp_version for t in ts):
            v = self.s.get(PlantypVersion, vid)
            teil = [em[t.id] for t in ts if t.plantyp_version == vid and not t.entfaellt]
            ids = {em[t.id]: t.id for t in ts}
            vorschlag = generiere(v.definition, p.parameter, teil, [e for e in es if e.termin in teil and e.fixiert], quelle, seed)
            meldungen.extend(vorschlag.meldungen)
            # UXP-R16 „nur Lücken/Verstöße": belegte Plaetze, die keine Regel
            # verletzen, bleiben stehen. Ein Verstoss wird am betroffenen
            # Feldpfad des Termins erkannt (Vorschlags- und Endpruefung).
            beanstandet = {
                (ids[x.termin], x.feld_pfad)
                for x in vorschlag.verstoesse
                if x.termin in ids and x.feld_pfad
            }
            verstoesse.extend({"stufe": x.stufe, "baustein": x.baustein, "feld_pfad": x.feld_pfad,
                               "meldung": x.meldung, "termin": ids.get(x.termin)} for x in vorschlag.verstoesse)
            neu = {(ids[e.termin], e.feld_pfad): e for e in vorschlag.eintraege}
            betroffen = {ids[t] for t in teil}
            for key in set(neu) | {k for k in alt if k[0] in betroffen}:
                a, n = alt.get(key), neu.get(key)
                if a and a["fixiert"]:
                    continue
                # UXP-R16 „nur Lücken“: belegte, regelkonforme Werte bleiben stehen.
                if (nur_luecken and a and a.get("wert") is not None and key not in beanstandet
                        and (n is None or a["wert"] != n.wert)):
                    continue
                if a and n and a["wert"] == n.wert and a["quelle"] == n.quelle:
                    continue
                diff.append({"termin": key[0], "feld_pfad": key[1], "vorher": a["wert"] if a else None,
                             "nachher": n.wert if n else None})
                if not nur_vorschau:
                    db = self.s.scalar(select(Eintrag).where(Eintrag.termin == key[0], Eintrag.feld_pfad == key[1]))
                    if n is None:
                        if db is not None:
                            self.s.delete(db)
                    else:
                        if db is None:
                            db = Eintrag(termin=key[0], feld_pfad=key[1], created_by=self.benutzer)
                            self.s.add(db)
                        db.wert, db.fixiert, db.quelle = n.wert, False, n.quelle
                        db.meldungen = [x for x in verstoesse if x["termin"] == key[0] and x["feld_pfad"] == key[1]]
        gruppe = None if nur_vorschau else self._schreibabschluss(p, vorher, "plan_generieren")
        return {"diff": sorted(diff, key=lambda d: (d["termin"], d["feld_pfad"])),
                "meldungen": meldungen, "verstoesse": verstoesse, "gruppe_id": gruppe}

    def eintrag_setzen(self, plan: str, termin: str, feld_pfad: str, wert: Any) -> dict[str, Any]:
        """Manuell gesetzte gültige Werte sind fixiert; Regelverstöße sind Meldungen."""
        p, typ, _ = self._plan(plan)
        vorher = self._stand(p)
        ts, em, es = self._kontext(p)
        t = next((t for t in ts if t.id == termin), None)
        if t is None:
            fehler("/termin", "Termin gehört nicht zum Plan.")
        definition = self.s.get(PlantypVersion, t.plantyp_version).definition
        slots = aufloesen_mit_eintraegen(definition, em[t.id], es, parameter=p.parameter)
        slot = next((s for s in slots if s.feld_pfad == feld_pfad), None)
        if slot is None:
            fehler("/feld_pfad", "Feldpfad ist in der aktiven Terminstruktur nicht vorhanden.")
        self._wert_pruefen(slot.art, wert, slot.feld, slot.sammlung, typ, p)
        db = self.s.scalar(select(Eintrag).where(Eintrag.termin == termin, Eintrag.feld_pfad == feld_pfad))
        if db is None:
            db = Eintrag(termin=termin, feld_pfad=feld_pfad, created_by=self.benutzer)
            self.s.add(db)
        db.wert, db.fixiert, db.quelle = wert, True, "manuell"
        es = [e for e in es if not (e.termin is em[t.id] and e.feld_pfad == feld_pfad)]
        es.append(EngineEintrag(feld_pfad, wert, slot.art, em[t.id], True, "manuell"))
        ids = {em[t.id]: t.id for t in ts}
        meldungen = [{"stufe": v.stufe, "baustein": v.baustein, "feld_pfad": v.feld_pfad,
                      "meldung": v.meldung, "termin": ids.get(v.termin) if v.termin is not None else None} for v in pruefe_plan(
                          definition, list(em.values()), es, self._quelle(typ, p), parameter=p.parameter)]
        db.meldungen = [m for m in meldungen if m["termin"] == termin and m["feld_pfad"] == feld_pfad]
        gruppe = self._schreibabschluss(p, vorher, "eintrag_setzen")
        return {"eintrag": zeile(db), "meldungen": meldungen, "gruppe_id": gruppe}

    def _wert_pruefen(self, art: str, wert: Any, definition: dict[str, Any],
                      sammlung: str | None, typ: Plantyp, plan: Plan | None) -> None:
        if wert is None:
            return
        if art in ("person", "personen", "team", "eintrag"):
            werte = wert if isinstance(wert, list) else [wert]
            if art != "personen" and isinstance(wert, list):
                fehler("/wert", "Einzelwert erwartet.")
            quelle = self._quelle(typ, plan)
            # AUSTRITT-d (NB1): eine BESTEHENDE Zuteilung muss auch dann
            # bestaetigt werden koennen, wenn die Person inzwischen
            # ausgetreten ist (die Kandidatenmenge bleibt gefiltert, siehe B4).
            bekannt = ({p.kennung for p in quelle.personen_anzeige()} if art in ("person", "personen") else
                       {g.kennung for g in quelle.gruppen()} if art == "team" else
                       {e.kennung for e in quelle.sammlung(sammlung or "")})
            if any(not isinstance(w, str) or w not in bekannt for w in werte):
                fehler("/wert", "Unbekannte Person, Gruppe oder Sammlungseintrag.")
        elif art == "tag" and not isinstance(wert, bool):
            fehler("/wert", "Boolescher Merkmalswert erwartet.")
        elif art == "zahl" and (isinstance(wert, bool) or not isinstance(wert, (int, float))):
            fehler("/wert", "Zahl erwartet.")
        elif art in ("text", "datum") and not isinstance(wert, str):
            fehler("/wert", "Text erwartet.")
        elif art == "auswahl":
            werte = wert if definition.get("mehrfach") and isinstance(wert, list) else [wert]
            if definition.get("werte") and any(w not in definition["werte"] for w in werte):
                fehler("/wert", "Wert ist nicht in der deklarierten Auswahl.")
        if art == "datum":
            try:
                date.fromisoformat(wert)
            except ValueError:
                fehler("/wert", "ISO-Datum erwartet.")

    def eintrag_loesen(self, plan: str, termin: str, feld_pfad: str) -> dict[str, Any]:
        p, _, _ = self._plan(plan)
        vorher = self._stand(p)
        e = self.s.scalar(select(Eintrag).join(Termin, Eintrag.termin == Termin.id).where(
            Termin.plan == p.id, Eintrag.termin == termin, Eintrag.feld_pfad == feld_pfad))
        if e is None:
            fehler("/eintrag", "Eintrag nicht gefunden.")
        e.fixiert, e.quelle = False, "geloest"
        return {"gruppe_id": self._schreibabschluss(p, vorher, "eintrag_loesen")}

    def platz_hinzufuegen(self, plan: str, termin: str, feld_pfad: str) -> dict[str, Any]:
        """Optionalen Mehrfachplatz eines Felds vor dem Generieren anlegen.

        Optionale Felder mit ``anzahl`` ``min..max`` (z. B. ``einueben`` mit
        ``0..2``) entfalten ohne Bedarf keine Slots und sind im Editor deshalb
        nicht waehlbar. Dieser Dienst legt serverseitig den naechsten freien
        Platz ``<feld>[n]`` an (leer, von Hand festgelegt), sodass er danach
        ueber ``eintrag_setzen`` normal bearbeitet werden kann. Rechte wie
        ``eintrag_setzen`` (Planbearbeitung), Verlauf/Undo wie jeder
        Schreibdienst. Ueberschreitung der Obergrenze ist ein Fachfehler (417).
        """
        p, _, _ = self._plan(plan)
        vorher = self._stand(p)
        ts = self.s.scalars(select(Termin).where(Termin.plan == p.id)).all()
        t = next((t for t in ts if t.id == termin), None)
        if t is None:
            fehler("/termin", "Termin gehört nicht zum Plan.")
        definition = self.s.get(PlantypVersion, t.plantyp_version).definition
        basis, deklaration = self._mehrfach_feld(definition, feld_pfad)
        if deklaration is None:
            fehler("/feld_pfad", "Dieses Feld kennt keine zusaetzlichen Plaetze.")
        obergrenze = self._obergrenze(deklaration.get("anzahl"))
        if obergrenze is None:
            fehler("/feld_pfad", "Dieses Feld hat keine feste Obergrenze.")
        vorhanden = {e.feld_pfad for e in
                     self.s.scalars(select(Eintrag).where(Eintrag.termin == termin)).all()
                     if e.feld_pfad == basis or e.feld_pfad.startswith(basis + "[")}
        indizes = {int(m.group(1)) for pfad in vorhanden
                   for m in [re.match(re.escape(basis) + r"\[(\d+)\]", pfad)] if m}
        # Naechster freier Index ab der hoechsten belegten Stelle; nie ueber max.
        naechster = (max(indizes) + 1) if indizes else 0
        if naechster >= obergrenze:
            fehler("/feld_pfad", f"Höchstens {obergrenze} Plätze für dieses Feld.")
        neuer_pfad = f"{basis}[{naechster}]"
        db = self.s.scalar(select(Eintrag).where(Eintrag.termin == termin, Eintrag.feld_pfad == neuer_pfad))
        if db is None:
            db = Eintrag(termin=termin, feld_pfad=neuer_pfad, created_by=self.benutzer)
            self.s.add(db)
        db.wert, db.fixiert, db.quelle = None, True, "manuell"
        db.meldungen = []
        gruppe = self._schreibabschluss(p, vorher, "platz_hinzufuegen")
        return {"feld_pfad": neuer_pfad, "art": deklaration.get("art", ""),
                "gruppe_id": gruppe}

    @staticmethod
    def _mehrfach_feld(definition: dict[str, Any], feld_pfad: str) -> tuple[str, dict[str, Any] | None]:
        """Felddeklaration zu einem Basis-Pfad finden (rekursiv, ohne Instanz)."""
        treffer: dict[str, Any] | None = None
        basis = feld_pfad.split(":")[-1].split("[")[0].split("/")[-1]
        reihe = feld_pfad.split(":", 1)[0] if ":" in feld_pfad else None

        def suche(felder: Any, praefix: str) -> None:
            nonlocal treffer
            for f in felder or []:
                if not isinstance(f, dict) or not isinstance(f.get("id"), str):
                    continue
                pfad = praefix + f["id"]
                if f["id"] == basis:
                    treffer = f
                suche(f.get("inhalt"), pfad + ".")
                for zweig in (f.get("varianten") or []) + (f.get("teile") or []):
                    if isinstance(zweig, dict):
                        suche(zweig.get("inhalt"), pfad + ".")
        for r in definition.get("terminreihen") or []:
            if isinstance(r, dict) and ((reihe and r.get("id") == reihe) or not reihe):
                suche(r.get("felder"), (r.get("id", "standard") + ":") if r.get("id") not in (None, "standard") else "")
        if not reihe or reihe == "standard":
            suche(definition.get("felder"), "")
        if treffer is None:
            return feld_pfad, None
        if treffer.get("art") not in ("eintrag", "personen", "team", "gruppe", "text", "zahl"):
            return feld_pfad, None
        return feld_pfad.split("[")[0], treffer

    @staticmethod
    def _obergrenze(anzahl: Any) -> int | None:
        """Obergrenze eines ``min..max``-Bereichs; None, wenn kein Bereich.

        Nur ein *Bereich* (``"0..2"``) kennt zusaetzliche Plaetze. Eine feste
        Zahl (``3``) ist eine feste Slotzahl — dort gibt es nichts hinzuzufuegen.
        Ein offenes Ende (``"1..*"``) ist variabel, aber ohne feste Grenze.
        """
        if isinstance(anzahl, str) and ".." in anzahl:
            rechts = anzahl.split("..", 1)[1]
            return int(rechts) if rechts.isdigit() else None
        return None

    def plan_entwurf(self, plan: str) -> dict[str, Any]:
        """Veroeffentlichten Plan als Entwurf oeffnen (UXP-R16).

        Bisher musste der Planer irgendeinen Wert von Hand aendern, damit
        „Vorschlag erzeugen" nicht mit einer kryptischen Meldung abbricht
        („Veröffentlichten Plan zuerst durch manuelle Bearbeitung zum Entwurf
        machen."). Dieser Dienst macht genau das — im Verlauf, damit
        ``undo`` es zuruecknehmen kann. Der eingefrorene Stand
        (``veroeffentlichter_stand``) bleibt unberuehrt, Mitglieder sehen also
        weiter den alten Stand.
        """
        p, _, _ = self._plan(plan)
        if p.status == "entwurf":
            return {"status": p.status, "schon_entwurf": True}
        vorher = self._stand(p)
        p.status = "entwurf"
        gruppe = self._schreibabschluss(p, vorher, "plan_entwurf")
        return {"status": p.status, "schon_entwurf": False, "gruppe_id": gruppe}

    #: Aktionen, die ein Rückgängig NICHT still zurücknehmen darf (UXP-R20).
    #: Die Veröffentlichung ist für Mitglieder sichtbar — sie still
    #: zurückzunehmen hiesse, dass der Aushang unbemerkt wieder verschwindet.
    #: Der Versionswechsel (``version_anwenden``) gehört ebenfalls nicht an den
    #: Eintrags-Undo-Knopf.
    _UNDO_GESPERRT = frozenset({"veroeffentlichen", "version_anwenden",
                                "plan_archivieren", "plan_wiederherstellen",
                                "plan_kopieren"})

    def _undo_ziel(self, p: Plan) -> Any:
        """Nächste rückgängig machbare Verlaufsgruppe samt lesbarer Beschreibung.

        UXP-R20: ``undo`` nahm bisher JEDE Gruppe zurück — auch die
        Veröffentlichung und den Versionswechsel. Beide sind mit
        :attr:`_UNDO_GESPERRT` ausgeschlossen. Der Aufrufer erhält den
        Zieltext („Vorschlag vom 15.10. 19:07 zurücknehmen“), damit der Knopf
        ehrlich beschriftet werden kann.
        """
        verlaeufe = self.s.scalars(select(Verlauf).where(Verlauf.plan == p.id).order_by(
            Verlauf.zeitpunkt.desc(), Verlauf.id.desc())).all()
        erledigt = {v.nachher["gruppe"] for v in verlaeufe if v.aktion == "undo"}
        return next((v for v in verlaeufe
                     if v.aktion not in ("undo",) and v.aktion not in self._UNDO_GESPERRT
                     and v.gruppe_id not in erledigt
                     and isinstance(v.vorher, dict) and "plan" in v.vorher), None)

    def undo(self, plan: str) -> dict[str, Any]:
        """Letzte noch nicht rückgängig gemachte Plan-Gruppe; mehrfach möglich.

        UXP-R20: Veröffentlichung und Versionswechsel sind ausgenommen (siehe
        :attr:`_UNDO_GESPERRT`); die Antwort nennt Aktion, Zeitpunkt und einen
        verständlichen Text, was zurückgenommen wurde.
        """
        p, _, _ = self._plan(plan)
        ziel = self._undo_ziel(p)
        if ziel is None:
            fehler("/undo", "Keine weitere rückgängig machbare Planänderung.")
        self._wiederherstellen(p, ziel.vorher)
        gruppe = self._verlauf("undo", None, {"gruppe": ziel.gruppe_id}, plan=p)
        return {"gruppe_id": gruppe, "rueckgaengig": ziel.gruppe_id,
                "aktion": ziel.aktion, "zeitpunkt": jsonwert(ziel.zeitpunkt),
                "beschreibung": self._undo_beschreibung(ziel.aktion)}

    @staticmethod
    def _undo_beschreibung(aktion: str) -> str:
        """Klartext, WAS ein „Rückgängig“ zurücknimmt (UXP-R20)."""
        return {
            "plan_generieren": "den letzten Vorschlag",
            "eintrag_setzen": "die letzte Handänderung",
            "eintrag_loesen": "das Lösen einer Festlegung",
            "ablauf_aendern": "die letzte Ablaufänderung",
            "plan_aendern": "die letzte Planänderung",
            "platz_hinzufuegen": "den zuletzt angelegten Zusatzplatz",
            "termin_aendern": "die letzte Terminänderung",
            "termin_hinzufuegen": "den zuletzt hinzugefügten Termin",
            "termin_entfernen": "den zuletzt entfernten Termin",
            "plan_entwurf": "das Öffnen des Plans als Entwurf",
        }.get(aktion, "die letzte Planänderung")

    def undo_vorschau(self, plan: str) -> dict[str, Any]:
        """UXP-R20: Was würde „Rückgängig“ zurücknehmen? (nur lesend)"""
        p, _, bearbeiten = self._plan(plan, False)
        if not bearbeiten:
            return {"moeglich": False, "beschreibung": ""}
        ziel = self._undo_ziel(p)
        if ziel is None:
            return {"moeglich": False, "beschreibung": ""}
        return {"moeglich": True, "aktion": ziel.aktion,
                "zeitpunkt": jsonwert(ziel.zeitpunkt),
                "beschreibung": self._undo_beschreibung(ziel.aktion)}

    def _wiederherstellen(self, p: Plan, stand: dict[str, Any]) -> None:
        """Snapshot ersetzt Planinhalt in FK-sicherer Reihenfolge."""
        for e in self.s.scalars(select(Eintrag).join(Termin, Eintrag.termin == Termin.id).where(Termin.plan == p.id)).all():
            self.s.delete(e)
        self.s.flush()
        vorhanden = {t.id: t for t in self.s.scalars(select(Termin).where(Termin.plan == p.id)).all()}
        for daten in stand["termine"]:
            t = vorhanden.pop(daten["id"], None)
            if t is None:
                t = Termin(id=daten["id"])
                self.s.add(t)
            self._spalten_setzen(t, daten)
        for t in vorhanden.values():
            self.s.delete(t)
        self.s.flush()
        for daten in stand["eintraege"]:
            e = Eintrag(id=daten["id"])
            self._spalten_setzen(e, daten)
            self.s.add(e)
        self._spalten_setzen(p, stand["plan"])
        sammlungen = self.s.scalars(select(Sammlung).where(Sammlung.plan == p.id)).all()
        sam_ids = [s.id for s in sammlungen]
        for e in self.s.scalars(select(SammlungEintrag).where(SammlungEintrag.sammlung.in_(sam_ids))).all():
            self.s.delete(e)
        self.s.flush()
        for sam in sammlungen:
            self.s.delete(sam)
        self.s.flush()
        for daten in stand.get("sammlungen", []):
            sam = Sammlung(id=daten["id"])
            self._spalten_setzen(sam, daten)
            self.s.add(sam)
        self.s.flush()
        for daten in stand.get("sammlung_eintraege", []):
            e = SammlungEintrag(id=daten["id"])
            self._spalten_setzen(e, daten)
            self.s.add(e)
        self.s.flush()

    @staticmethod
    def _spalten_setzen(objekt: Any, daten: dict[str, Any]) -> None:
        for c in objekt.__table__.columns:
            if c.name not in daten:
                continue
            v = deepcopy(daten[c.name])
            if v is not None and isinstance(v, str):
                from sqlalchemy import Date, DateTime, Time
                if isinstance(c.type, DateTime):
                    v = datetime.fromisoformat(v)
                elif isinstance(c.type, Date):
                    v = date.fromisoformat(v)
                elif isinstance(c.type, Time):
                    v = time.fromisoformat(v)
            setattr(objekt, c.name, v)

    def termin_aendern(self, plan: str, termin: str, *, datum: str | None = None,
                       uhrzeit: str | None = None, entfaellt: bool | None = None,
                       titel: str | None = None, anlaesse: list[str] | None = None,
                       variante: str | None = None, variante_setzen: bool = False) -> dict[str, Any]:
        """Ändert einen bestehenden Termin (OP-CHOR-1, OP-EVENT-18).

        Bisher entstanden Termine nur beim Anlegen eines Plans; verschieben,
        Uhrzeit, absagen oder die geltende Sonne/Regen-Variante liessen sich
        danach nicht mehr ändern. Dieser Dienst ändert (nur) die übergebenen
        Felder an der Ursache — mit Verlauf/Undo wie jeder andere Schreibweg.

        ``variante_setzen`` unterscheidet „nicht übergeben“ von „ausdrücklich
        auf die erste Variante zurückstellen“ (leer).
        """
        p, _typ, _ = self._plan(plan)
        t = self.s.scalar(select(Termin).where(Termin.id == termin, Termin.plan == p.id))
        if t is None:
            fehler("/termin", "Termin gehört nicht zum Plan.")
        vorher = self._stand(p)
        if datum is not None:
            from datetime import date as _d
            try:
                t.datum = _d.fromisoformat(str(datum))
            except ValueError:
                fehler("/datum", "ISO-Datum erwartet.")
        if uhrzeit is not None:
            from datetime import time as _t
            roh = str(uhrzeit).strip()
            if not roh:
                t.uhrzeit = None
            else:
                try:
                    t.uhrzeit = _t.fromisoformat(roh)
                except ValueError:
                    fehler("/uhrzeit", "Uhrzeit im Format HH:MM erwartet.")
        if entfaellt is not None:
            t.entfaellt = bool(entfaellt)
        if titel is not None:
            t.titel = str(titel)[:280] or None
        if anlaesse is not None:
            t.anlaesse = list(anlaesse)
        if variante_setzen:
            t.variante = (variante or None)
        if p.veroeffentlichter_stand is not None:
            p.status = "entwurf"
        gruppe = self._schreibabschluss(p, vorher, "termin_aendern")
        return {"termin": zeile(t), "gruppe_id": gruppe}

    def termin_hinzufuegen(self, plan: str, datum: str, uhrzeit: str | None = None,
                           titel: str | None = None, anlaesse: list[str] | None = None,
                           reihe: str | None = None) -> dict[str, Any]:
        """Fügt einen manuellen Sondertermin zu einem Plan hinzu (OP-CHOR-1).

        Der Termin übernimmt die am Datum gültige Plantyp-Version; die Reihe
        ist entweder ausdrücklich gewählt oder die Kurzform 'standard'.
        """
        from datetime import date as _d, time as _t
        p, typ, _ = self._plan(plan)
        try:
            d = _d.fromisoformat(str(datum))
        except ValueError:
            fehler("/datum", "ISO-Datum erwartet.")
        version = speicher.gueltige_version_zu_datum(self.s, typ.id, d)
        if version is None:
            fehler("/datum", "Zu diesem Datum gibt es keine gültige Planvorlagen-Version.")
        uhr = None
        if uhrzeit:
            try:
                uhr = _t.fromisoformat(str(uhrzeit).strip())
            except ValueError:
                fehler("/uhrzeit", "Uhrzeit im Format HH:MM erwartet.")
        vorher = self._stand(p)
        t = Termin(plan=p.id, datum=d, reihe=reihe or "standard", uhrzeit=uhr,
                   titel=(str(titel)[:280] if titel else None),
                   anlaesse=list(anlaesse or []), quelle="manuell", plantyp_version=version.id)
        self.s.add(t)
        self.s.flush()
        if p.veroeffentlichter_stand is not None:
            p.status = "entwurf"
        gruppe = self._schreibabschluss(p, vorher, "termin_hinzufuegen")
        return {"termin": zeile(t), "gruppe_id": gruppe}

    def termin_entfernen(self, plan: str, termin: str) -> dict[str, Any]:
        """Entfernt einen Termin samt seiner Einträge (OP-CHOR-1), mit Undo."""
        p, _, _ = self._plan(plan)
        t = self.s.scalar(select(Termin).where(Termin.id == termin, Termin.plan == p.id))
        if t is None:
            fehler("/termin", "Termin gehört nicht zum Plan.")
        vorher = self._stand(p)
        for e in self.s.scalars(select(Eintrag).where(Eintrag.termin == t.id)).all():
            self.s.delete(e)
        self.s.flush()
        self.s.delete(t)
        self.s.flush()
        if p.veroeffentlichter_stand is not None:
            p.status = "entwurf"
        gruppe = self._schreibabschluss(p, vorher, "termin_entfernen")
        return {"entfernt": termin, "gruppe_id": gruppe}

    def _plan_entfernen(self, p: Plan) -> None:
        """Löscht Planinhalt in FK-sicherer Reihenfolge (OP-UI-12).

        Erst Einträge, dann Termine, dann planbezogene Sammlungen samt
        Einträgen, zuletzt den Plan. Die unveränderlichen Plantyp-Versionen,
        gemeindeweite Merkmale und Verlaufshistorie anderer Pläne bleiben
        unberührt.
        """
        self.s.flush()
        termin_ids = [t.id for t in self.s.scalars(
            select(Termin).where(Termin.plan == p.id)).all()]
        if termin_ids:
            for e in self.s.scalars(select(Eintrag).where(
                    Eintrag.termin.in_(termin_ids))).all():
                self.s.delete(e)
        self.s.flush()
        for t in self.s.scalars(select(Termin).where(Termin.plan == p.id)).all():
            self.s.delete(t)
        self.s.flush()
        sam_ids = [s.id for s in self.s.scalars(
            select(Sammlung).where(Sammlung.plan == p.id)).all()]
        if sam_ids:
            for se in self.s.scalars(select(SammlungEintrag).where(
                    SammlungEintrag.sammlung.in_(sam_ids)).all()):
                self.s.delete(se)
            self.s.flush()
            for sam in self.s.scalars(select(Sammlung).where(
                    Sammlung.plan == p.id)).all():
                self.s.delete(sam)
        # Verlaufseinträge des Plans mitentfernen (kein Waisen-Verlauf).
        for v in self.s.scalars(select(Verlauf).where(Verlauf.plan == p.id)).all():
            self.s.delete(v)
        self.s.flush()
        self.s.delete(p)
        self.s.flush()

    def plan_loeschen(self, plan: str, bestaetigt: bool = False) -> dict[str, Any]:
        """Löscht einen ENTWURF endgültig (OP-UI-12).

        Ein veröffentlichter Plan darf nicht still verschwinden — er würde
        bei Mitgliedern zu einem „verschwundenen Aushang“. Er wird stattdessen
        archiviert (``plan_archivieren``).

        P1-14b: Die Löschung ist unwiderruflich. Deshalb verlangt der Server
        die ausdrückliche Bestätigung ``bestaetigt=True`` (die Oberfläche
        fragt über einen Dialog nach) und hinterlässt eine PLANUNABHÄNGIGE
        Spur in ``pr_verlauf`` — sonst fiele mit ``ON DELETE CASCADE`` auch
        der Verlauf und niemand könnte nachvollziehen, wer welchen Plan
        gelöscht hat.
        """
        p, typ, _ = self._plan(plan)
        if p.veroeffentlichter_stand is not None or p.status != "entwurf":
            fehler("/status", "Nur ein Entwurf lässt sich löschen. Veröffentlichte "
                              "Pläne bitte archivieren.", "plan.nicht_entwurf")
        if not bestaetigt:
            fehler("/bestaetigt",
                   "Das endgültige Löschen muss bestätigt werden.",
                   "plan.bestaetigung_fehlt")
        titel = p.titel
        # Spur VOR dem Löschen: plan=None (überlebt CASCADE), Aufbewahrung im
        # JSON (Titel/Plantyp/Kennung), Zeitpunkt und Benutzer kommen aus der
        # Verlaufszeile.
        self._verlauf("plan_loeschen", {"plan": p.id, "titel": titel,
                                        "plantyp": typ.id if typ else None,
                                        "status": p.status},
                      {"geloescht": p.id, "titel": titel}, plan=None, typ=typ)
        self._plan_entfernen(p)
        return {"geloescht": plan, "titel": titel, "bestaetigt": True}

    def plan_archivieren(self, plan: str, archivieren: bool = True) -> dict[str, Any]:
        """Setzt einen Plan auf „archiviert“ bzw. zurück auf „entwurf“ (OP-UI-12).

        Archivieren ist der rückgängige Weg für veröffentlichte Pläne: die
        Mitglieder sehen den letzten veröffentlichten Stand nicht mehr in der
        Liste, die Daten bleiben erhalten.
        """
        p, _, _ = self._plan(plan, archiv_erlaubt=True)
        vorher = self._stand(p)
        if archivieren:
            if p.status == "archiviert":
                fehler("/status", "Der Plan ist bereits archiviert.", "plan.schon_archiviert")
            p.status = "archiviert"
        else:
            if p.status != "archiviert":
                fehler("/status", "Nur ein archivierter Plan lässt sich zurückholen.",
                       "plan.nicht_archiviert")
            p.status = "veroeffentlicht" if p.veroeffentlichter_stand is not None else "entwurf"
        self._verlauf("plan_archivieren" if archivieren else "plan_wiederherstellen",
                      vorher, self._stand(p), plan=p)
        return {"plan": p.id, "status": p.status}

    def plan_kopieren(self, plan: str, titel: str, mit_eintraegen: bool = True,
                      von: date | None = None, bis: date | None = None) -> dict[str, Any]:
        """Kopiert einen Plan samt Terminen (und optional Einträgen) (OP-UI-12).

        Der neue Plan ist immer ein Entwurf und trägt keine Veröffentlichung.
        Ohne neue Zeitraumangaben erbt er den Zeitraum der Vorlage; bei einem
        abweichenden Zeitraum werden die Termine NICHT verschoben (die Struktur
        hängt an den bestehenden Tagen) — die Kopie behält die Termine.
        """
        p, typ, _ = self._plan(plan)
        if not titel or not str(titel).strip():
            fehler("/titel", "Ein Titel für die Kopie ist erforderlich.")
        # P1-14b: Eine Kopie ist ein NEUER Plan — wer ihn anlegen darf, muss
        # auch das Anlegerecht an der Vorlage haben (nicht nur das
        # Bearbeitungsrecht am Quellplan).
        if not self.rechte.darf_plan_anlegen(typ):
            fehler("/plan", "Kein Recht, einen Plan dieser Vorlage anzulegen.",
                   "plan.anlegen_verweigert")
        neu = Plan(plantyp=typ.id, titel=str(titel).strip(),
                   zeitraum_von=von or p.zeitraum_von, zeitraum_bis=bis or p.zeitraum_bis,
                   parameter=deepcopy(p.parameter or {}), status="entwurf",
                   verantwortlich=p.verantwortlich, created_by=self.benutzer)
        self.s.add(neu)
        self.s.flush()
        alt_termin_ids = {t.id for t in self.s.scalars(
            select(Termin).where(Termin.plan == p.id)).all()}
        # Planbezogene Sammlungen mitkopieren (Eintragskennungen bleiben stabil).
        for sam in self.s.scalars(select(Sammlung).where(Sammlung.plan == p.id)).all():
            neue_sam = Sammlung(schluessel=sam.schluessel, umfang=sam.umfang, plan=neu.id)
            self.s.add(neue_sam)
            self.s.flush()
            for se in self.s.scalars(select(SammlungEintrag).where(
                    SammlungEintrag.sammlung == sam.id)).all():
                self.s.add(SammlungEintrag(id=se.id, sammlung=neue_sam.id, daten=deepcopy(se.daten),
                                           reihenfolge=se.reihenfolge, aktiv=se.aktiv))
            self.s.flush()
        # Termine 1:1 kopieren; die Eintrags-IDs der alten Termine werden auf
        # die neuen abgebildet, damit `feld_pfad`-Zuordnungen erhalten bleiben.
        termin_map: dict[str, str] = {}
        for t in self.s.scalars(select(Termin).where(Termin.plan == p.id)).all():
            neu_t = Termin(plan=neu.id, datum=t.datum, reihe=t.reihe, uhrzeit=t.uhrzeit,
                           titel=t.titel, entfaellt=t.entfaellt, anlaesse=deepcopy(t.anlaesse),
                           ablauf=deepcopy(t.ablauf), index=t.index, quelle=t.quelle,
                           positionsnr_im_monat=t.positionsnr_im_monat,
                           position_von_hinten=t.position_von_hinten,
                           variante=t.variante, plantyp_version=t.plantyp_version)
            self.s.add(neu_t)
            self.s.flush()
            termin_map[t.id] = neu_t.id
        if mit_eintraegen and alt_termin_ids:
            for e in self.s.scalars(select(Eintrag).where(
                    Eintrag.termin.in_(alt_termin_ids))).all():
                self.s.add(Eintrag(termin=termin_map.get(e.termin), feld_pfad=e.feld_pfad,
                                   wert=deepcopy(e.wert), fixiert=e.fixiert, quelle=e.quelle))
        self.s.flush()
        self._verlauf("plan_kopieren", None, self._stand(neu), plan=neu)
        return {"plan": neu.id, "titel": neu.titel, "termine": len(termin_map),
                "eintraege": (0 if not mit_eintraegen else len(
                    self.s.scalars(select(Eintrag).where(
                        Eintrag.termin.in_(list(termin_map.values())))).all()))}

    def plan_aendern(self, plan: str, titel: str | None = None,
                     von: date | None = None, bis: date | None = None,
                     parameter: dict[str, Any] | None = None) -> dict[str, Any]:
        """Ändert Titel/Zeitraum/Parameter eines Plans (OP-UI-12).

        Bei geändertem Zeitraum werden Termine ausserhalb neu erzeugt: die
        Beschreibung ist bewusst konservativ — wir löschen keine bestehenden
        Termine, sondern melden die Zahl der Termine, die ausserhalb des neuen
        Zeitraums liegen, damit die Planerin selbst entscheiden kann.
        """
        p, typ, _ = self._plan(plan)
        vorher = self._stand(p)
        if titel is not None:
            if not str(titel).strip() or len(str(titel)) > 280:
                fehler("/titel", "Titel ist ungültig.")
            p.titel = str(titel).strip()
        if von is not None:
            p.zeitraum_von = von
        if bis is not None:
            p.zeitraum_bis = bis
        if p.zeitraum_von and p.zeitraum_bis and (p.zeitraum_bis < p.zeitraum_von
                                                  or (p.zeitraum_bis - p.zeitraum_von).days > 3660):
            fehler("/zeitraum", "Zeitraum muss geordnet und höchstens zehn Jahre lang sein.")
        if parameter is not None:
            if not isinstance(parameter, dict):
                fehler("/parameter", "Parameter müssen ein JSON-Objekt sein.")
            p.parameter = parameter
        ausserhalb = self.s.scalars(select(Termin).where(
            Termin.plan == p.id,
            (Termin.datum < p.zeitraum_von) | (Termin.datum > p.zeitraum_bis))).all() \
            if p.zeitraum_von and p.zeitraum_bis else []
        if p.veroeffentlichter_stand is not None:
            p.status = "entwurf"
        self._verlauf("plan_aendern", vorher, self._stand(p), plan=p)
        return {"plan": p.id, "titel": p.titel, "termine_ausserhalb": len(ausserhalb), "status": p.status}

    def veroeffentlichen(self, plan: str) -> dict[str, Any]:
        p, _, _ = self._plan(plan)
        vorher = self._stand(p)
        # K1: „Erstveroeffentlichung“ heisst, dass es NOCH NIE einen
        # veroeffentlichten Stand gab — nicht, dass der alte Stand leer war.
        # Ein frueherer Stand ohne Eintraege ist trotzdem eine Veroeffentlichung.
        war_je_veroeffentlicht = p.veroeffentlichter_stand is not None
        alt = (p.veroeffentlichter_stand or {}).get("eintraege", [])
        p.status = "veroeffentlicht"
        stand = self._stand(p)
        # Kein rekursiver Snapshot im Snapshot.
        stand["plan"].pop("veroeffentlichter_stand", None)
        stand.pop("sammlungen", None)
        stand.pop("sammlung_eintraege", None)
        # P1-11b M1/UXP-R19: Regelpruefungen sind internes Planerwissen. Der
        # Snapshot wird (ueber `zeile`) aus ALLEN Spalten gebaut und trug damit
        # die Spalte `meldungen` in jeden Nicht-Bearbeitungs-Zugriff. Schon hier
        # an der Wurzel entfernen, damit jede Ansicht auf den veroeffentlichten
        # Stand frei davon ist — nicht nur die, die man gerade kennt.
        for e in stand["eintraege"]:
            e.pop("meldungen", None)
        p.veroeffentlichter_stand = stand
        gruppe = self._schreibabschluss(p, vorher, "veroeffentlichen")
        # BF1-B: Der Diff vergleicht ANWESENHEIT, nicht nur den Wert. Vorher war
        # er ein Dict `(termin, feld_pfad) -> wert` und die Schleife pruefte
        # `a.get(k) != b.get(k)`. Beim ERSTEN Veroeffentlichen ist `alt` leer,
        # also war `a.get(k)` fuer jeden Schluessel `None` — und `b.get(k)`
        # ebenso, solange der Wert noch nicht belegt ist. Ergebnis: Diff leer,
        # die SPA meldete „keine Wertänderungen“ / „0 Änderungen öffentlich“
        # und der Planer sah „nichts passiert“ (Live-Befund BF1-B).
        a = {(e["termin"], e["feld_pfad"]): e.get("wert") for e in alt}
        b = {(e["termin"], e["feld_pfad"]): e.get("wert") for e in stand["eintraege"]}
        neu: list[dict[str, Any]] = []
        for k in sorted(set(a) | set(b)):
            drin_alt, drin_neu = k in a, k in b
            if a.get(k) == b.get(k):
                # Auch ein entfernter leerer Eintrag ändert keinen Wert.
                continue
            # K1: Ein Eintrag, der jetzt existiert aber keinen Wert traegt
            # (`nachher is None`) und vorher gar nicht da war, ist KEINE
            # Aenderung — sonst meldet die SPA „120 Werte sind jetzt sichtbar“
            # fuer lauter leere Plaetze. Der Vertrag von BF1-B («Diff-Zahl =
            # Eintragszahl bei Erstveroeffentlichung») gilt fuer BELEGTE
            # Eintraege; leere sind keine Aenderung.
            if not drin_alt and not b.get(k):
                continue
            neu.append({
                "termin": k[0], "feld_pfad": k[1],
                "vorher": a.get(k) if drin_alt else None,
                "nachher": b.get(k) if drin_neu else None,
                "neu": drin_neu and not drin_alt,
            })
        # OP-HANDY-6 / Konzept B10: „Änderungen erzeugen sichtbaren Diff +
        # Benachrichtigung der Betroffenen.“ Betroffen sind die Personen, deren
        # Zuordnung sich geändert hat — alt ODER neu (eine Umbesetzung trifft
        # beide Seiten). Beim ERSTEN Veroeffentlichen gibt es keinen Bezug, auf
        # den sich eine „Aenderung“ beziehen koennte; dann werden alle
        # eingeteilten Personen einmal informiert.
        self._benachrichtige_veroeffentlichung(p, alt, stand, neu, not war_je_veroeffentlicht)
        return {"gruppe_id": gruppe, "diff": neu,
                "erstveroeffentlichung": not war_je_veroeffentlicht}

    def _benachrichtige_veroeffentlichung(self, p: Plan, alt: list[dict[str, Any]],
                                          stand: dict[str, Any], neu: list[dict[str, Any]],
                                          erstveroeffentlichung: bool) -> None:
        """Schreibt eine Benachrichtigung je betroffener Person (Beiwerk).

        Kein Fehler darf die Veroeffentlichung scheitern lassen — deshalb ist
        diese Funktion in sich abgesichert und die Empfaenger werden aus den
        Eintraegen abgeleitet, nicht aus einer zweiten Abfrage, die scheitern
        koennte.
        """
        from . import benachrichtigung
        try:
            if erstveroeffentlichung:
                quellen: list[Any] = [e.get("wert") for e in stand["eintraege"]]
            else:
                beruehrt = {(d["termin"], d["feld_pfad"]) for d in neu}
                quellen = [e.get("wert") for e in alt if (e.get("termin"), e.get("feld_pfad")) in beruehrt]
                quellen += [e.get("wert") for e in stand["eintraege"]
                            if (e.get("termin"), e.get("feld_pfad")) in beruehrt]
            mitglieder: set[str] = set()
            for wert in quellen:
                mitglieder |= benachrichtigung.empfaenger_aus_eintraegen(self.s, wert)
            # Wer den Plan veroeffentlicht, muss sich nicht selbst anmailen.
            eigene = self.rechte.eigenes_mitglied()
            mitglieder.discard(eigene)
            if not mitglieder:
                return
            users = [benachrichtigung.user_zu_mitglied(self.s, m) for m in mitglieder]
            betreff, inhalt = benachrichtigung.meldung_plan_veroeffentlicht(
                p.titel, len(neu), erstveroeffentlichung)
            benachrichtigung.benachrichtige(
                self.s, users, subject=betreff, inhalt=inhalt,
                document_type="Plan", document_name=p.id)
        except Exception as ex:  # noqa: BLE001 — Benachrichtigung ist Beiwerk
            from diakronos_app.frappe_compat.api_helpers import log_error
            log_error(str(ex), f"plan_veroeffentlicht {p.id}")

    def bedarf(self, plantyp: str, plan: str | None = None) -> list[dict[str, Any]]:
        typ = self._typ(plantyp, schreiben=False)
        # P1-14b: reiner LESEZUGRIFF — der Archiv-Schreibschutz in `_plan` darf
        # hier nicht greifen (sonst scheitert die Planansicht eines archivierten
        # Plans an dieser Datenabdeckung mit 417).
        p = self._plan(plan, schreiben=False)[0] if plan else None
        if not self._darf_stammdaten_lesen(typ, p):
            from diakronos_app.frappe_compat.exceptions import PermissionError
            raise PermissionError("Zugriff verweigert.")
        if p and p.plantyp != typ.id:
            fehler("/plantyp", "Plan und Plantyp passen nicht zusammen.")
        v = speicher.gueltige_version_zu_datum(self.s, typ.id, p.zeitraum_von if p else date.max)
        return [asdict(b) for b in bedarfspruefung(v.definition, self._quelle(typ, p))]

    def trockenlauf(self, definition: dict[str, Any], parameter: dict[str, Any] | None = None,
                     ab: date | None = None, wochen: int = 8, seed: int = 0) -> dict[str, Any]:
        """Vorschlag ohne Persistenz — neue Definitionen nur im eigenen Bereich (UI2).

        Eine noch nicht gespeicherte Definition darf nur Admin oder
        Verantwortung im `definition.bereich` trockenlaufen lassen. Bei
        einem bereits gespeicherten Plantyp gilt dessen gespeicherter
        Bereich sowie die Regel des `plantyp_speichern`: ein Bereichswechsel
        der Definition umgeht den Typscope nicht und erfordert Admin.
        Das Ergebnis ist UI1-Sicht-tauglich: Termine mit stabilen IDs,
        Einträge mit `termin`-Verweis (zusätzlich zu datum/reihe) und eine
        `anzeige`-Map wie in `plan_holen`.
        """
        definition = self._definition(definition)
        if not 1 <= wochen <= 52:
            fehler("/wochen", "Trockenlauf umfasst 1 bis 52 Wochen.")
        bereich = definition.get("bereich")
        typ = self.s.scalar(select(Plantyp).where(
            Plantyp.schluessel == definition["id"]))
        if typ is not None:
            self.rechte.plantyp(typ)
            if typ.bereich != bereich and not self.rechte.admin():
                from diakronos_app.frappe_compat.exceptions import PermissionError
                raise PermissionError("Bereichswechsel erfordert Administratorrechte.")
        else:
            if not self.rechte.bereich(bereich):
                from diakronos_app.frappe_compat.exceptions import PermissionError
                raise PermissionError("Zugriff verweigert.")
            if bereich and self.s.get(Dienstbereich, bereich) is None:
                fehler("/bereich", "Dienstbereich nicht gefunden.")
        quelle = self._quelle(typ or definition["id"])
        try:
            ergebnis = engine_trockenlauf(definition, parameter or {}, quelle, wochen, seed, ab)
        except TerminLimitUeberschritten as exc:
            raise DienstFehler.aus_terminlimit(exc) from exc
        ids = {t: f"tl-{i}" for i, t in enumerate(ergebnis.termine)}
        eintraege = [e for e in ergebnis.vorschlag.eintraege if e.termin in ids]
        return {"bedarf": [asdict(b) for b in ergebnis.bedarf], "meldungen": ergebnis.meldungen,
                "termine": [{"id": ids[t], "plantyp_version": "probelauf",
                             "datum": t.datum.isoformat(), "reihe": t.reihe,
                             "titel": t.name or "",
                             "uhrzeit": t.uhrzeit.isoformat() if t.uhrzeit else None,
                             "anlaesse": t.anlass_liste,
                             **({"ablauf": jsonwert(t.ablauf)} if t.ablauf else {})}
                            for t in ergebnis.termine],
                "eintraege": [{"termin": ids[e.termin], "datum": e.termin.datum.isoformat(),
                               "reihe": e.termin.reihe, "feld_pfad": e.feld_pfad,
                               "wert": e.wert, "quelle": e.quelle} for e in eintraege],
                "verstoesse": [{"stufe": v.stufe, "baustein": v.baustein, "feld_pfad": v.feld_pfad,
                                "meldung": v.meldung,
                                "termin": ids.get(v.termin) if v.termin is not None else None}
                               for v in ergebnis.verstoesse],
                "anzeige": self._anzeige_aus([(t, definition) for t in ergebnis.termine],
                                             eintraege, quelle, parameter or {})}

    def merkmale_pflegen(self, plantyp: str, werte: list[dict[str, Any]], plan: str | None = None) -> dict[str, Any]:
        """Pflegt deklarierte Merkmalswerte (ST2/ST3).

        ST3: Person-Merkmale (Fähigkeiten) darf auch ein Gruppenverantwortlicher
        einer an die Vorlage gebundenen Gruppe pflegen — allerdings nur fuer
        Personen **des Personenpools**. Sammlungsmerkmale und globale
        Stammdaten bleiben Bereichs-/Admin-Sache. Mit konkreter Plan-ID gilt
        zusaetzlich das Planbearbeitungsrecht.
        """
        typ = self._typ(plantyp, schreiben=False)
        p = self._plan(plan)[0] if plan else None
        if p and p.plantyp != typ.id:
            fehler("/plan", "Plan und Plantyp passen nicht zusammen.")
        # Vorlagenrecht = Admin/Bereich. ST3: zusaetzlich Gruppenverantwortliche
        # der gebundenen Gruppe(n) — aber NUR fuer Person-Faehigkeiten. Ein
        # blosser Planverantwortlicher erhaelt hier bewusst kein Recht (der
        # bestehende Vertrag erwartet 403; Planverantwortung deckt Planaenderungen,
        # nicht die gemeindeweiten Faehigkeiten).
        vorlage_recht = self.rechte.darf_plantyp_bearbeiten(typ)
        personen_recht = vorlage_recht or self.rechte.gruppen_verantwortlich(
            _plantyp_gruppen(self.s, typ.id))
        if not personen_recht:
            from diakronos_app.frappe_compat.exceptions import PermissionError
            raise PermissionError("Zugriff verweigert.")
        pool_keys, pool_inkl = self._pool_gruppen(typ)
        pool_personen = ({x.kennung for x in self._quelle(typ, p).personen()}
                         if pool_keys else None)
        versionen = self.s.scalars(select(PlantypVersion).where(PlantypVersion.plantyp == typ.id).order_by(
            PlantypVersion.versionsnummer.desc())).all()
        deklariert = {(('person' if ziel == 'person' else 'sammlung:' + ziel), m['id'])
                      for v in versionen for ziel, ms in v.definition.get('merkmale', {}).items() for m in ms}
        vorher = []
        for w in werte:
            ziel, key, ziel_id = w.get("ziel"), w.get("schluessel"), w.get("ziel_id")
            samdef = next((sam for v in versionen for sam in v.definition.get("sammlungen", [])
                           if ziel == "sammlung:" + sam["id"]), None)
            eigene_sammlung = p is not None and samdef is not None and samdef.get("umfang") == "plan"
            if ziel == "person":
                # Faehigkeiten: Personenpool-Recht (ST3); ohne Pool-Recht nur
                # mit Vorlagen-/Planrecht.
                if not personen_recht:
                    self.rechte.plantyp(typ)
                if pool_personen is not None and ziel_id not in pool_personen:
                    fehler("/ziel_id", "Person gehoert nicht zum Personenpool der Vorlage.",
                           code="rechte.pool")
            elif not eigene_sammlung:
                self.rechte.plantyp(typ)
            if (ziel, key) not in deklariert:
                fehler("/werte", "Merkmal gehört nicht zum Plantyp.")
            m = self.s.scalar(select(Merkmal).where(Merkmal.ziel == ziel, Merkmal.schluessel == key))
            if ziel == "person":
                if self.s.get(Mitglied, ziel_id) is None:
                    fehler("/ziel_id", "Mitglied nicht gefunden.")
            elif not any(e.kennung == ziel_id for e in self._quelle(typ, p).sammlung(ziel.removeprefix("sammlung:"))):
                fehler("/ziel_id", "Sammlungseintrag nicht gefunden.")
            self._wert_pruefen(m.art, w.get("wert"), m.definition, None, typ, p)
            alt = self.s.scalar(select(MerkmalWert).where(MerkmalWert.merkmal == m.id, MerkmalWert.ziel_id == ziel_id))
            vorher.append(zeile(alt) if alt else None)
            if alt is None:
                alt = MerkmalWert(merkmal=m.id, ziel_id=ziel_id, created_by=self.benutzer)
                self.s.add(alt)
            alt.wert = w.get("wert")
            self.s.flush()
        return {"gruppe_id": self._verlauf("merkmale_pflegen", vorher, werte, typ=typ)}

    def sammlung_pflegen(self, plantyp: str, sammlung: str, eintraege: list[dict[str, Any]],
                          plan: str | None = None) -> dict[str, Any]:
        typ = self._typ(plantyp, schreiben=False)
        p = self._plan(plan)[0] if plan else None
        if p is None:
            self.rechte.plantyp(typ)
        if p and p.plantyp != typ.id:
            fehler("/plan", "Plan und Plantyp passen nicht zusammen.")
        vs = self.s.scalars(select(PlantypVersion).where(PlantypVersion.plantyp == typ.id).order_by(
            PlantypVersion.versionsnummer.desc())).all()
        samdef = next((s for v in vs for s in v.definition.get("sammlungen", []) if s["id"] == sammlung), None)
        if samdef is None or sammlung == "lieder" or (samdef.get("umfang") == "plan" and p is None):
            fehler("/sammlung", "Eigene deklarierte Sammlung und gegebenenfalls Plan erforderlich.")
        if samdef.get("umfang", "gemeinde") != "plan":
            self.rechte.plantyp(typ)
        sam = self._sammlung_anlegen(samdef, p)
        plan_vorher = self._stand(p) if sam.umfang == "plan" else None
        vorher, result = [], []
        for e in eintraege:
            alt = self.s.get(SammlungEintrag, e["id"]) if e.get("id") else None
            if alt and alt.sammlung != sam.id:
                fehler("/eintraege", "Eintrag gehört zu einer anderen Sammlung.")
            vorher.append(zeile(alt) if alt else None)
            if alt is None:
                alt = SammlungEintrag(sammlung=sam.id, created_by=self.benutzer)
                self.s.add(alt)
            # Die UI erhält nur deklarierte Anzeigeattribute. Verborgene
            # Bestandsattribute dürfen bei Titelpflege nicht verloren gehen.
            alt.daten = {**(alt.daten or {}), **e.get("daten", {})}
            alt.reihenfolge = e.get("reihenfolge", 0)
            alt.aktiv = e.get("aktiv", True)
            self.s.flush()
            result.append(zeile(alt))
        gruppe = (self._schreibabschluss(p, plan_vorher, "sammlung_pflegen") if plan_vorher is not None else
                  self._verlauf("sammlung_pflegen", vorher, result, typ=typ))
        return {"eintraege": result, "gruppe_id": gruppe}

    def _abwesenheit_recht(self, mitglied: str, typ: Plantyp | None, p: Plan | None) -> None:
        """Darf der aufrufende Benutzer fuer dieses Mitglied Abwesenheit pflegen?

        Eigenes Mitglied immer; fremde nur mit Bereichsverantwortung (oder
        Gruppenverantwortung ueber den Personenpool). Ohne Plantyp/Plan bleibt
        fuer Fremde nur die Bereichsverantwortung — sonst 403.
        """
        if mitglied == self.rechte.eigenes_mitglied() or self.rechte.admin():
            return
        if typ is None:
            from diakronos_app.frappe_compat.exceptions import PermissionError
            raise PermissionError("Fremde Abwesenheit benötigt Bereichsverantwortung.")
        if self.rechte.bereich(typ.bereich):
            return
        # ST3: Gruppenverantwortliche duerfen fuer Personen ihres
        # Personenpools eine (plantypgebundene) Abwesenheit melden.
        pool, _ = self._pool_gruppen(typ)
        if pool and self.rechte.gruppen_verantwortlich(pool):
            if any(x.kennung == mitglied for x in self._quelle(typ, p).personen()):
                return
        self.rechte.plantyp(typ)

    def meine_dienste(self) -> list[dict[str, Any]]:
        """Eigene Zuordnungen aus veroeffentlichten Staenden (OP-CHOR-7, OP-HANDY-18).

        Reicht pro Zuordnung mehr als nur den Feldpfad durch, damit die
        Mitglieder-Sicht verstaendlich ist:

        * ``termin``, ``uhrzeit``, ``anlass`` — wann und wozu,
        * ``lied_titel`` — bei einem Lied-Feld der Titel/die Nummer des Lieds,
        * ``mitwirkende`` — die uebrigen Namen derselben Zelle,
        * ``abwesend`` — die Zuordnung faellt in eine gemeldete Abwesenheit.

        Sichtbarkeit unveraendert: ausschliesslich die eigenen Eintraege aus
        ``veroeffentlichter_stand``; keine Entwuerfe, kein fremdes Mitglied.
        """
        mitglied = self.rechte.eigenes_mitglied()
        if not mitglied:
            return []
        # P1-14b: Ein archivierter Plan ist abgehaengt — seine Zuordnungen
        # gehoeren nicht mehr in „Meine Dienste“ (sonst stuenden Dienste in der
        # Liste, die es nicht mehr gibt).
        planzeilen = self.s.scalars(select(Plan).where(
            Plan.veroeffentlichter_stand.is_not(None),
            Plan.status != "archiviert").order_by(Plan.titel, Plan.id)).all()
        abwesend = self.s.scalars(select(Abwesenheit).where(
            Abwesenheit.mitglied == mitglied)).all()
        ergebnis: list[dict[str, Any]] = []
        for p in planzeilen:
            stand = p.veroeffentlichter_stand
            typ = self.s.get(Plantyp, p.plantyp)
            ts = {t["id"]: t for t in stand["termine"]}
            versionen = {v.id: v.definition for v in self.s.scalars(select(PlantypVersion).where(
                PlantypVersion.id.in_({t["plantyp_version"] for t in stand["termine"]}))).all()}
            # Anzeigemap (Personen, Lieder) — gleiche Quelle wie plan_holen.
            quelle = self._quelle(typ, p) if typ else None
            anzeige: dict[str, Any] = {}
            if quelle is not None:
                # Ein Engine-Termin je Snapshot-Termin (mit gebundener Version).
                for t in stand["termine"]:
                    definition = versionen.get(t["plantyp_version"]) or {}
                    et = EngineTermin(date.fromisoformat(t["datum"]), t["reihe"],
                                      anlaesse=frozenset(t["anlaesse"]), index=t["index"],
                                      positionsnr_im_monat=t["positionsnr_im_monat"],
                                      position_von_hinten=t["position_von_hinten"],
                                      ablauf=deepcopy(t["ablauf"]),
                                      variante=t.get("variante"))
                    eigene = [EngineEintrag(e["feld_pfad"], e["wert"], "text", et)
                              for e in stand["eintraege"] if e["termin"] == t["id"]]
                    anzeige.update(self._anzeige_aus([(et, definition)], eigene, quelle,
                                                     stand["plan"].get("parameter", {})))
            eintraege_je_termin: dict[Any, list[dict[str, Any]]] = {}
            for e in stand["eintraege"]:
                eintraege_je_termin.setdefault(e["termin"], []).append(e)
            # OP-HANDY-18: eigene Absagen liegen im Entwurf, nicht im
            # eingefrorenen Stand. Wer abgesagt hat, sieht die Zuordnung nicht
            # mehr — sonst wirkte die Absage folgenlos, bis der Planer neu
            # veroeffentlicht.
            #
            # P1-11b M2: Die Absage gilt PRO MITGLIED. Der fruehere Filter
            # ueber `(termin, feld_pfad)` traf die ganze Zelle: standen A und B
            # in `lieder.solo` und sagte A ab, verschwand der Dienst auch bei B.
            # Richtig ist der Blick auf den AKTUELLEN Entwurfseintrag und dessen
            # Quelle: nur eine ABSAGE (quelle == "abgesagt") an dieser Zelle,
            # in der das Mitglied nicht mehr steht, blendet die eigene Zuordnung
            # aus. Eine gewoehnliche Planer-Umbesetzung des Entwurfs laesst den
            # veroeffentlichten Stand unberuehrt — erst die Neuveroeffentlichung
            # wirkt (sonst verschwaende die Anzeige ohne Absage).
            abgesagt: set[tuple[Any, Any]] = set()
            for x in self.s.scalars(select(Eintrag).join(
                    Termin, Eintrag.termin == Termin.id).where(
                    Termin.plan == p.id, Eintrag.quelle == "abgesagt")).all():
                entwurf = list(x.wert) if isinstance(x.wert, list) else [x.wert]
                if mitglied not in entwurf:
                    abgesagt.add((x.termin, x.feld_pfad))
            for e in stand["eintraege"]:
                wert = e["wert"]
                if not (wert == mitglied or (isinstance(wert, list) and mitglied in wert)):
                    continue
                if (e["termin"], e["feld_pfad"]) in abgesagt:
                    continue          # eigene Absage — nur diese Zuordnung
                t = ts.get(e["termin"])
                if t is None:
                    continue
                feldname = str(e["feld_pfad"]).split(".")[-1].split("[")[0]
                ergebnis.append({
                    "plan": p.id,
                    "titel": stand["plan"]["titel"],
                    "plan_titel": stand["plan"]["titel"],
                    # OP-HANDY-6: „geändert am“-Marker — Zeitpunkt, zu dem der
                    # veroeffentlichte Stand eingefroren wurde. `modified` im
                    # Snapshot ist genau dieser Zeitpunkt.
                    "plan_geaendert": stand["plan"].get("modified"),
                    "termin": t["datum"],
                    "termin_id": t["id"],
                    "uhrzeit": t.get("uhrzeit"),
                    "anlass": ", ".join(t.get("anlaesse") or []),
                    "termin_titel": t.get("titel") or "",
                    "feld_pfad": e["feld_pfad"],
                    "feld_name": feldname,
                    "wert": wert,
                    "lied_titel": self._lied_titel(e["feld_pfad"], eintraege_je_termin.get(t["id"], []), anzeige),
                    "mitwirkende": self._mitwirkende(e["feld_pfad"], eintraege_je_termin.get(t["id"], []), anzeige),
                    "abwesend": any(a.von <= date.fromisoformat(t["datum"]) <= a.bis for a in abwesend),
                })
        return ergebnis

    @staticmethod
    def _finde_zeile(feld_pfad: str, eintraege: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]]]:
        """Wurzelpfad und Geschwister einer Zelle ('lieder[1].solo' → 'lieder[1]')."""
        pfad = str(feld_pfad)
        index = pfad.find("[")
        if index != -1:
            ende = pfad.find("]", index)
            wurzel = pfad[:ende + 1] if ende != -1 else pfad
        else:
            wurzel = pfad.split(".")[0]
        punkt = wurzel + "."
        geschwister = [x for x in eintraege
                       if x["feld_pfad"] == wurzel or x["feld_pfad"].startswith(punkt)]
        return wurzel, geschwister

    def _lied_titel(self, feld_pfad: str, eintraege: list[dict[str, Any]],
                    anzeige: dict[str, Any]) -> str:
        """Titel der Lied-Zelle über der eigenen Zuordnung (leer, wenn keine)."""
        wurzel, geschwister = self._finde_zeile(feld_pfad, eintraege)
        for x in geschwister:
            if x["feld_pfad"] == wurzel and x.get("wert"):
                a = anzeige.get(x["wert"])
                if isinstance(a, dict):
                    return a.get("anzeige") or a.get("titel") or a.get("name") or ""
                return str(a or "")
        return ""

    def _mitwirkende(self, feld_pfad: str, eintraege: list[dict[str, Any]],
                     anzeige: dict[str, Any]) -> list[dict[str, Any]]:
        """Die uebrigen Namen derselben Zelle mit ihrer Rolle (Unterfeld)."""
        wurzel, geschwister = self._finde_zeile(feld_pfad, eintraege)
        namen = []
        for x in geschwister:
            if x["feld_pfad"] == wurzel:
                continue
            rolle = str(x["feld_pfad"])[len(wurzel):].lstrip(".").split("[")[0]
            for w in (x["wert"] if isinstance(x["wert"], list) else [x["wert"]]):
                a = anzeige.get(w)
                name = (a.get("anzeige") or a.get("name")) if isinstance(a, dict) else None
                if name:
                    namen.append({"name": name, "rolle": rolle})
        return namen

    def abwesenheit_melden(self, mitglied: str, von: date, bis: date, grund: str = "",
                           plantyp: str | None = None, plan: str | None = None) -> dict[str, Any]:
        p = self._plan(plan)[0] if plan else None
        typ = self._typ(plantyp, False) if plantyp else (self.s.get(Plantyp, p.plantyp) if p else None)
        self._abwesenheit_recht(mitglied, typ, p)
        if self.s.get(Mitglied, mitglied) is None or bis < von:
            fehler("/abwesenheit", "Mitglied oder Zeitraum ungültig.")
        a = Abwesenheit(mitglied=mitglied, von=von, bis=bis, grund=grund,
                        nur_plantyp=typ.schluessel if typ else None, created_by=self.benutzer)
        self.s.add(a)
        self.s.flush()
        return {"abwesenheit": zeile(a), "gruppe_id": self._verlauf("abwesenheit_melden", None, zeile(a), typ=typ)}

    def abwesenheiten_liste(self, mitglied: str | None = None,
                            plantyp: str | None = None, plan: str | None = None) -> list[dict[str, Any]]:
        """Abwesenheiten eines Mitglieds (UXP-R17).

        Ohne ``mitglied`` die eigenen; ein fremdes Mitglied nur mit
        Bereichs-/Gruppenverantwortung (dieselbe Schranke wie beim Melden).
        Geliefert werden ausschliesslich die eigenen Spalten — kein PII Dritter.
        """
        p = self._plan(plan, schreiben=False)[0] if plan else None
        typ = self._typ(plantyp, False) if plantyp else (self.s.get(Plantyp, p.plantyp) if p else None)
        ziel = mitglied or self.rechte.eigenes_mitglied()
        if not ziel:
            return []
        self._abwesenheit_recht(ziel, typ, p)
        zeilen = self.s.scalars(select(Abwesenheit).where(
            Abwesenheit.mitglied == ziel).order_by(
            Abwesenheit.von, Abwesenheit.bis, Abwesenheit.id)).all()
        # AUSTRITT A3: Der Grund einer ABWESENHEIT kann eine Krankheit nennen.
        # Fuer eine ausgetretene Person sehen ihn nur noch die Person selbst
        # und Administratoren — fuer alle anderen bleibt die Zeile (der Plan
        # braucht sie), aber ohne Grund.
        from diakronos_app.frappe_compat.personen_anzeige import (
            PersonenSicht, ist_ausgeschieden,
        )

        ergebnis = [zeile(a) for a in zeilen]
        # AUSTRITT-c (N3): der Abwesenheits-Grund wird nur beim AUSTRITT
        # verborgen — ein Ausschluss laesst die Zeile voll sichtbar.
        person = self.s.get(Mitglied, ziel)
        if (person is not None and ist_ausgeschieden({
                "status": person.status, "austritt_datum": person.austritt_datum,
            }) and not PersonenSicht.aus().darf_vollstaendig(ziel)):
            for x in ergebnis:
                x["grund"] = ""
        return ergebnis

    def abwesenheit_loeschen(self, abwesenheit: str) -> dict[str, Any]:
        """Eigene Abwesenheit zuruecknehmen (Fehleingabe korrigieren, UXP-R17).

        Fremde nur mit derselben Verantwortung wie beim Melden. Loeschen ist
        eng begrenzt: die Zeile gehoert dem eigenen Mitglied oder der Benutzer
        ist (Bereichs-/Gruppen-)Verantwortlicher des gebundenen Plantyps.
        """
        a = self.s.get(Abwesenheit, abwesenheit)
        if a is None:
            fehler("/abwesenheit", "Abwesenheit nicht gefunden.")
        typ = (self.s.scalar(select(Plantyp).where(Plantyp.schluessel == a.nur_plantyp))
               if a.nur_plantyp else None)
        self._abwesenheit_recht(a.mitglied, typ, None)
        daten = zeile(a)
        self.s.delete(a)
        self.s.flush()
        return {"abwesenheit": daten, "gruppe_id": self._verlauf("abwesenheit_loeschen", daten, None, typ=typ)}

    def dienst_absagen(self, plan: str, termin: str, feld_pfad: str) -> dict[str, Any]:
        """Eigene Einteilung im veroeffentlichten Plan absagen (OP-HANDY-18).

        Der Rahmen organisiert Dienst, er ersetzt ihn nicht (Konzept P9):
        wer nicht kann, gibt seinen Platz frei. Der Eintrag wird geleert —
        nicht geloescht — damit der Planer die Absage im Verlauf sieht und
        der Platz wieder besetzbar ist. Nur das EIGENE Mitglied darf absagen;
        Planer nutzen weiterhin den Editor.
        """
        p, _, _ = self._plan(plan, schreiben=False)
        mitglied = self.rechte.eigenes_mitglied()
        if not mitglied:
            from diakronos_app.frappe_compat.exceptions import PermissionError
            raise PermissionError("Zugriff verweigert.")
        vorher = self._stand(p)
        e = self.s.scalar(select(Eintrag).join(Termin, Eintrag.termin == Termin.id).where(
            Termin.plan == p.id, Eintrag.termin == termin, Eintrag.feld_pfad == feld_pfad))
        if e is None:
            fehler("/eintrag", "Eintrag nicht gefunden.")
        wert = e.wert
        if not (wert == mitglied or (isinstance(wert, list) and mitglied in wert)):
            from diakronos_app.frappe_compat.exceptions import PermissionError
            raise PermissionError("Nur die eigene Einteilung kann abgesagt werden.")
        if isinstance(wert, list):
            e.wert = [w for w in wert if w != mitglied]
        else:
            e.wert = None
        e.fixiert, e.quelle = True, "abgesagt"
        # Anders als bei Planer-Schreibdiensten darf eine Absage den Plan NICHT
        # auf Entwurf zuruecksetzen: der veroeffentlichte Stand bleibt gueltig,
        # die Absage wird urspruenglich als Verlaufseintrag festgehalten.
        self.s.flush()
        gruppe = self._verlauf("dienst_absagen", dict(vorher), self._stand(p), plan=p)
        return {"feld_pfad": feld_pfad, "termin": termin, "gruppe_id": gruppe}
