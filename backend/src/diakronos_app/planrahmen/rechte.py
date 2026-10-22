"""Fail-closed Objekt-Rechte innerhalb derselben Diensttransaktion."""
from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from diakronos_app.frappe_compat.exceptions import PermissionError
from diakronos_app.models.core import HasRole, User
from diakronos_app.models.diakonos import DienstbereichVerantwortlicher, GruppeVerantwortlicher, Mitglied
from diakronos_app.models.planrahmen import Plan, Plantyp, PlantypVersion


def _plantyp_gruppen(session: Session, plantyp_id: str) -> set[str]:
    """Gebundene Gruppen einer Vorlage aus der jüngsten Definition (ST3).

    Reine Lesefunktion ohne Rechtebezug — sie liefert nur die Kennungen der
    ``gruppen`` aus ``pr_plantyp_version.definition`` (hoechste
    Versionsnummer). Fehlt eine Version oder die Liste, ist das Ergebnis leer.
    """
    letzte = session.scalars(select(PlantypVersion).where(
        PlantypVersion.plantyp == plantyp_id).order_by(
        PlantypVersion.versionsnummer.desc())).first()
    if letzte is None or not isinstance(letzte.definition, dict):
        return set()
    return {g for g in (letzte.definition.get("gruppen") or []) if isinstance(g, str)}


class Rechte:
    """Identität kommt ausschließlich aus der geprüften HTTP-Sitzung."""

    def __init__(self, session: Session, benutzer: str):
        self.session = session
        self.benutzer = benutzer

    def angemeldet(self) -> None:
        """Anonyme, deaktivierte und ausgeschlossene Konten haben keine Rechte.

        P1-8 (Nachtrag R-P1-9b): Der Ausschluss (`Mitglied.ausgeschlossen`)
        gilt auch hier — sonst hätte eine ausgeschlossene Person im
        Plan-Rahmen weiter Planrechte, obwohl ihre Rollen anderswo schon
        entzogen sind. Die Prüfung steht an derselben Stelle wie `enabled`,
        damit sie kein Aufrufpfad vergessen kann.

        R-P1-8/B3: Der Ausschluss wird über `self.session` gelesen, NICHT über
        eine zweite `SessionLocal()`-Sitzung. Die zweite Sitzung sah die noch
        nicht committeten Zeilen der laufenden Transaktion nicht (und rollte
        bei In-Memory-SQLite die gemeinsame Verbindung zurück) — dieselbe
        Transaktion, dieselbe Verbindung, dieselbe Sicht.
        """
        konto = self.session.get(User, self.benutzer)
        if self.benutzer == "Guest" or (self.benutzer != "Administrator" and
                                         (konto is None or not konto.enabled)):
            raise PermissionError("Zugriff verweigert.")
        if self.benutzer != "Administrator" and self.ausgeschlossen():
            raise PermissionError("Zugriff verweigert.")

    def ausgeschlossen(self) -> bool:
        """Ist das Mitglied dieses Kontos ausgeschlossen? — in DIESER Sitzung.

        Dieselbe Regel wie `frappe_compat.benutzer_status._mitglied_ausgeschlossen`
        (mehrere Mitglieder an einem Konto: ausschliessen, sobald EINES
        markiert ist), nur ohne zweite DB-Verbindung: die Prüfung läuft
        innerhalb der Transaktion, die der Aufrufer ohnehin hält.
        """
        return bool(self.session.scalar(
            select(Mitglied.ausgeschlossen).where(
                Mitglied.user == self.benutzer,
                Mitglied.ausgeschlossen.is_(True),
            ).limit(1)
        ))

    def admin(self) -> bool:
        """Nur Administrator/System Manager, nicht weitere Verwaltungsrollen.

        N12b (R-N10 Punkt 7): `Has Role` enthaelt auch Zeilen fuer andere
        Eltern-DocTypes (Seiten, Berichte). Ohne den `parenttype`-Filter waere
        ein Konto, das zufaellig wie eine Seite heisst, hier Plan-Administrator.
        """
        self.angemeldet()
        # Altdaten tragen `parenttype` NULL oder leer — beides zaehlt als
        # Benutzerzeile (dieselbe Regel wie `permissions.ist_user_zeile`).
        # Ohne IS NULL haetten genau die Altzeilen ihre Rechte verloren.
        return self.benutzer == "Administrator" or bool(self.session.scalar(
            select(HasRole.name).where(HasRole.parent == self.benutzer,
                                      HasRole.role.in_(["Administrator", "System Manager"]),
                                      or_(HasRole.parenttype.is_(None),
                                          HasRole.parenttype == "",
                                          HasRole.parenttype == "User"))
        ))

    def eigenes_mitglied(self) -> str | None:
        """Eindeutige Bindung; E-Mail-Fallback übernimmt keine fremde Bindung."""
        self.angemeldet()
        treffer = self.session.scalars(select(Mitglied.name).where(
            Mitglied.user == self.benutzer)).all()
        if treffer:
            return treffer[0] if len(treffer) == 1 else None
        konto = self.session.get(User, self.benutzer)
        email = konto.email if konto else self.benutzer
        treffer = self.session.scalars(select(Mitglied.name).where(
            Mitglied.email == email, Mitglied.user.is_(None))).all()
        return treffer[0] if len(treffer) == 1 else None

    def bereich(self, bereich: str | None) -> bool:
        """Verantwortung muss ausdrücklich dem Dienstbereich zugeordnet sein."""
        if self.admin():
            return True
        return bool(bereich and self.session.scalar(select(DienstbereichVerantwortlicher.name).where(
            DienstbereichVerantwortlicher.parent == bereich,
            DienstbereichVerantwortlicher.parenttype == "Dienstbereich",
            DienstbereichVerantwortlicher.parentfield == "verantwortliche",
            DienstbereichVerantwortlicher.user == self.benutzer)))

    def eigene_gruppen_verantwortung(self) -> set[str]:
        """Kennungen der Gruppen, fuer die der Benutzer Gruppenverantwortlicher ist.

        Grundlage ist ``gruppe_verantwortlicher`` (Child-Tabelle der Gruppe,
        ``parentfield='verantwortliche'``, ``user`` = Benutzername). Admin
        bekommt eine leere Menge — Admins sind ohnehin umfassend berechtigt.
        """
        self.angemeldet()
        if self.admin():
            return set()
        return set(self.session.scalars(select(GruppeVerantwortlicher.parent).where(
            GruppeVerantwortlicher.user == self.benutzer,
            GruppeVerantwortlicher.parenttype == "Gruppe",
            GruppeVerantwortlicher.parentfield == "verantwortliche",
            GruppeVerantwortlicher.docstatus < 2)).all())

    def gruppen_verantwortlich(self, gruppen: set[str] | frozenset[str]) -> bool:
        """True, wenn der Benutzer Gruppenverantwortlicher einer der Gruppen ist.

        ST3: Gruppenverantwortliche der an eine Planvorlage gebundenen
        Gruppe(n) duerfen Plaene dieser Vorlage anlegen/bearbeiten/
        veroeffentlichen — nicht jedoch die Vorlage selbst aendern.
        """
        if self.admin():
            return True
        if not gruppen:
            return False
        return bool(self.eigene_gruppen_verantwortung() & set(gruppen))

    def plantyp(self, plantyp: Plantyp) -> None:
        """Plantyp-/Stammdatenpflege nur Bereichsverantwortliche und Admins."""
        if not self.bereich(plantyp.bereich):
            raise PermissionError("Zugriff verweigert.")

    def darf_plan_bearbeiten(self, plan: Plan, plantyp: Plantyp) -> bool:
        """Ein Planverantwortlicher darf ausschließlich seinen eigenen Plan ändern.

        ST3: Zusaetzlich duerfen Gruppenverantwortliche der an die Vorlage
        gebundenen Gruppe(n) den Plan bearbeiten.
        """
        if self.bereich(plantyp.bereich) or bool(
                plan.verantwortlich and plan.verantwortlich == self.eigenes_mitglied()):
            return True
        return self.gruppen_verantwortlich(_plantyp_gruppen(self.session, plantyp.id))

    def darf_plantyp_bearbeiten(self, plantyp: Plantyp) -> bool:
        """Vorlage/globale Stammdaten aendern: Admin oder Bereichsverantwortung.

        Gruppenverantwortliche duerfen die Vorlage NICHT aendern (ST3).
        """
        return self.bereich(plantyp.bereich)

    def darf_plan_anlegen(self, plantyp: Plantyp) -> bool:
        """Plan dieser Vorlage anlegen: Bereichs- ODER Gruppenverantwortung (ST3)."""
        return self.bereich(plantyp.bereich) or self.gruppen_verantwortlich(
            _plantyp_gruppen(self.session, plantyp.id))

    def plan(self, plan: Plan, plantyp: Plantyp, schreiben: bool = False) -> bool:
        """Liefert Bearbeitungsrecht; Mitglieder lesen nur veröffentlichten Snapshot."""
        bearbeiten = self.darf_plan_bearbeiten(plan, plantyp)
        if bearbeiten:
            return True
        if not schreiben and plan.veroeffentlichter_stand is not None and self.eigenes_mitglied():
            return False
        raise PermissionError("Zugriff verweigert.")
