"""Anlegen der Demo-Gemeinde „Evangelische Gemeinde Musterhausen“ (PUB-2).

Alle Schreibvorgaenge laufen ueber die echten Schnittstellen der App:

* Stammdaten (Konten, Rollen, Mitglieder, Gruppen, Kalender, Ressourcen, Lieder,
  Termine, Dienst- und Ablaufplaene) ueber ``frappe_compat.api_helpers._create``
  — derselbe Weg, den ``/api/resource`` und ``frappe.client.insert`` nehmen
  (inklusive aller Schranken: E-Mail-Eindeutigkeit, Verwaltungsrechte).
* Plan-Rahmen-Plaene ueber ``planrahmen.dienste.Dienste`` (Plantyp anlegen,
  Plan anlegen, Eintraege setzen) — nicht per Roh-SQL.

Idempotenz: jeder Datensatz hat eine FESTE Kennung. Vor dem Anlegen wird
geprueft, ob es ihn schon gibt; wenn ja, bleibt er unveraendert. Ein zweiter
Lauf meldet „vorhanden“ und schreibt nichts.

Aufruf im app-Image (Datenbank frisch migriert und LEER)::

    python tools/demo/musterhausen.py
    python tools/demo/musterhausen.py --pruefen
    python tools/demo/musterhausen.py --entfernen

Rueckgabe: Exitcode 0 = fertig, 2 = Fehler (Meldung auf stderr).
"""

from __future__ import annotations

import argparse
import re
import sys
from contextlib import contextmanager
from datetime import date, datetime, time, timedelta
from typing import Any, Iterable, Iterator

from sqlalchemy import bindparam, select

from diakronos_app.db import als_aktuelle_sitzung
from diakronos_app.models.core import HasRole, Role, User
from diakronos_app.models.diakonos import (
    Beitrag,
    BeitragKommentar,
    DashboardWidget,
    Dienstbereich,
    Dienstplan,
    DienstplanPosition,
    DienstplanTermin,
    Dienstrolle,
    Gruppe,
    Gruppenmitgliedschaft,
    Gruppentyp,
    Gruppenrolle,
    GruppeVerantwortlicher,
    Mitglied,
    MitgliedBeziehung,
    RessourcenBuchung,
    Untergruppe,
    Untergruppenmitgliedschaft,
    WikiArtikel,
)
from diakronos_app.models.diakronos import DiakronosEinstellungen
from diakronos_app.models.kronos import (
    Ablaufplan,
    AblaufplanPosition,
    Element,
    ElementMitarbeiter,
    Eventkategorie,
    Kalender,
    KalenderModerator,
    Ressource,
)
from diakronos_app.models.psalmos import (  # noqa: F401 — auch fuer Tests
    Lied,
    LiedAnlass,
    Liedanlass,
    LiedGruppenzuordnung,
    LiedKategorie,
    Liedkategorie,
)
from diakronos_app.models.planrahmen import (  # noqa: F401 — auch fuer Tests
    Eintrag,
    Merkmal,
    MerkmalWert,
    Plan,
    Plantyp,
    Sammlung,
    SammlungEintrag,
)

try:  # als Paket (``python -m demo.musterhausen``) …
    from . import musterhausen_daten as daten
except ImportError:  # … oder direkt als Skript (``python tools/demo/musterhausen.py``).
    import musterhausen_daten as daten  # type: ignore[no-redef]

#: Konten der Demo. Die Passwoerter sind ABSICHTLICH oeffentlich: es sind
#: Demo-Konten einer erfundenen Gemeinde, keine Zugangsdaten einer Anlage.
KONTEN: dict[str, str] = {
    daten.ADMIN_EMAIL: daten.ADMIN_PASSWORT,
    daten.MITGLIED_EMAIL: daten.MITGLIED_PASSWORT,
}
ROLLEN_ADMIN = ("System Manager", "Mitgliederadministrator", "Kalenderadministrator", "Ressourcenmoderator")
ROLLEN_MITGLIED = ("Mitglied",)

#: Rollen, die es in der Demo geben muss (die Konten tragen sie).
ROLLEN: tuple[str, ...] = (
    "System Manager",
    "Mitglied",
    "Mitgliederadministrator",
    "Kalenderadministrator",
    "Ressourcenmoderator",
)


class DemoFehler(RuntimeError):
    """Fachlicher Abbruch mit verstaendlicher Meldung."""


def _meldung(text: str) -> None:
    print(f"[musterhausen] {text}", flush=True)


#: Im Lauf vergebene Mitglied-Kennungen („Anna Beispiel“ -> Server-Kennung).
#: ID-1d: `_create` vergibt die Kennung jeder neuen Person selbst; die feste
#: Kennung aus `daten.person()` gibt es in der App nicht mehr. Alle spaeteren
#: Schritte (Beziehungen, Dienste, Abwesenheiten, Austritt, Aufraeumen) lesen
#: die Zuordnung hier, statt den Namen als Kennung zu benutzen.
_KENNUNGEN: dict[str, str] = {}


def person_kennung(name: str) -> str:
    """Gespeicherte Mitglied-Kennung zu einem Anzeigenamen (ID-1d)."""
    return _KENNUNGEN.get(name, name)


def _jetzt() -> datetime:
    """Erstellzeitpunkt der Demo-Datensaetze (naive Ortszeit, wie die App)."""
    return datetime.now().replace(microsecond=0)


def _uhr(wert: str) -> time:
    """``"19:30"`` -> ``time(19, 30)``."""
    stunde, minute = wert.split(":")
    return time(int(stunde), int(minute))


class Anleger:
    """Duenne Huelle mit Zaehlern: jeder Schreibvorgang geht durch die App.

    ``nur_pruefen`` laesst am Ende alles zurueckrollen — das Skript meldet
    dann nur, was fehlt.
    """

    def __init__(self, session, nur_pruefen: bool = False) -> None:
        self.s = session
        self.nur_pruefen = nur_pruefen
        self.angelegt: dict[str, int] = {}
        self.vorhanden: dict[str, int] = {}
        self.zeitpunkt = _jetzt()
        # Die App-Funktionen (`_create`, `Dienste`, `mitglied_austritt` …) holen
        # sich ihre Sitzung ueber `diakronos_app.db.sitzung_fuer_lesen()`. Im
        # Request-Rahmen ist das die Sitzung des Aufrufs (`als_aktuelle_sitzung`);
        # hier wird DIESELBE Sitzung hinterlegt. Sonst schriebe jeder Aufruf
        # ueber eine ZWEITE Sitzung, waehrend das Skript seine eigene weiterbenutzt
        # — auf SQLite bliebe die zweite Sitzung an den offenen Zeilen der ersten
        # haengen („database is locked“), und „ist schon da?“ wuerde in einer
        # anderen Transaktion beantwortet als „jetzt anlegen“.
        self._sitzung_rahmen = als_aktuelle_sitzung(session)
        self._sitzung_rahmen.__enter__()

    def schliessen(self) -> None:
        """Den Sitzungs-Rahmen wieder abgeben (muss der Aufrufer tun)."""
        rahmen = getattr(self, "_sitzung_rahmen", None)
        if rahmen is not None:
            self._sitzung_rahmen = None
            rahmen.__exit__(None, None, None)

    # -- Zaehler -------------------------------------------------------
    def zaehle(self, art: str, neu: bool) -> None:
        ziel = self.angelegt if neu else self.vorhanden
        ziel[art] = ziel.get(art, 0) + 1

    def merke(self, art: str) -> None:
        self.zaehle(art, False)

    # -- Schreiben -----------------------------------------------------
    def neu(self, doctype: str, werte: dict[str, Any]) -> str:
        """Einen Datensatz ueber den App-Weg anlegen (``_create`` committet)."""
        from diakronos_app.frappe_compat.api_helpers import _create

        # Offene ORM-Zeilen zuerst schreiben: `_create` committet auf derselben
        # Verbindung und wuerde sie sonst mitnehmen (vorzeitiger Commit).
        self.s.flush()
        name = _create(doctype, dict(werte))
        self.zaehle(doctype, True)
        return name

    def kind(self, art: str, instanz: Any) -> Any:
        """Kindzeile an die offene Transaktion haengen (Commit macht der Aufrufer)."""
        self.s.add(instanz)
        self.zaehle(art, True)
        return instanz

    def abschluss(self) -> None:
        if self.nur_pruefen:
            self.s.rollback()
        else:
            self.s.commit()

    def bericht(self) -> str:
        teile = []
        for art in sorted(self.angelegt):
            teile.append(f"{art}: {self.angelegt[art]} neu")
        if self.vorhanden:
            teile.append(
                "bereits vorhanden: "
                + ", ".join(f"{art} {n}" for art, n in sorted(self.vorhanden.items()))
            )
        return "; ".join(teile) if teile else "nichts zu tun"


# ── Konten und Rollen ───────────────────────────────────────────────────────


def _rolle_anlegen(a: Anleger, name: str) -> None:
    if a.s.get(Role, name) is not None:
        a.merke("Rolle")
        return
    if a.nur_pruefen:
        a.zaehle("Rolle", True)
        return
    a.s.add(Role(name=name))
    a.s.flush()
    a.zaehle("Rolle", True)


def _benutzer_anlegen(a: Anleger, email: str, passwort: str, voller_name: str) -> None:
    """Ein Konto anlegen — ueber den regulaeren Schreibweg (``_create``).

    ``user.enabled`` ist die Schranke, an der die Plan-Rahmen-Rechte pruefen
    (``planrahmen/rechte.py``: ein deaktiviertes Konto hat keine Rechte, auch
    nicht mit der Rolle). Ein direkt per ORM eingefuegtes Konto blieb dort
    „aus“ — die Plaene liessen sich dann nicht mehr anlegen.
    """
    from diakronos_app.frappe_compat.passwoerter import neuer_hash

    a.neu("User", {
        "name": email,
        "email": email,
        "full_name": voller_name,
        "enabled": 1,
        "user_type": "System User",
        "password_hash": neuer_hash(passwort),
    })


def konten_anlegen(a: Anleger) -> None:
    """Rollen und die beiden Demo-Konten (Admin + Mitglied)."""
    for name in ROLLEN:
        _rolle_anlegen(a, name)

    from diakronos_app.models.core import HasRole

    for email, passwort in KONTEN.items():
        vorhanden = a.s.get(User, email)
        if vorhanden is None:
            if a.nur_pruefen:
                a.zaehle("Konto", True)
            else:
                # Der Anzeigename des Kontos ist die PERSON, nicht „Administrator“:
                # die Seitenleiste und „Meine Dienste“ zeigen `user.full_name`,
                # und ein Konto namens „Administrator“ neben einer verknuepften
                # Gemeindeleitung sieht aus wie „kein Mitglied“ (Befund PUB-2b/B2).
                _benutzer_anlegen(
                    a, email, passwort,
                    daten.ADMIN_PERSON if email == daten.ADMIN_EMAIL
                    else daten.MITGLIED_PERSON,
                )
        else:
            a.merke("Konto")

    # Rollen: Admin bekommt alle Verwaltungsrollen, das Mitglied nur „Mitglied“.
    for email, rollen in (
        (daten.ADMIN_EMAIL, ROLLEN_ADMIN),
        (daten.MITGLIED_EMAIL, ROLLEN_MITGLIED),
    ):
        for idx, rolle in enumerate(rollen, start=1):
            name = f"{email}-{rolle}"
            if a.s.get(HasRole, name) is not None:
                a.merke("Rollenzeile")
                continue
            a.kind("Rollenzeile", HasRole(
                name=name, parent=email, parenttype="User", parentfield="roles",
                role=rolle, docstatus=0, idx=idx, creation=a.zeitpunkt,
                modified=a.zeitpunkt, owner="Administrator", modified_by="Administrator",
            ))


# ── Gemeinde-Einstellungen ──────────────────────────────────────────────────


def einstellungen_anlegen(a: Anleger) -> None:
    """Gemeindename und Modulsichtbarkeit (DocType „Diakronos Einstellungen“)."""
    name = "Diakronos Einstellungen"
    if a.nur_pruefen:
        a.merke("Einstellungen")
        return
    vorhanden = a.s.get(DiakronosEinstellungen, name)
    if vorhanden is not None:
        a.merke("Einstellungen")
        return
    # Die Einstellungen sind eine SINGLE-Zeile: das DocType schreibt sie ueber
    # den regulaeren Schreibweg (``_create``), nicht als direkte ORM-Zeile —
    # ein ``session.add`` waere am Ende der einzige Datensatz, den ein zweiter
    # Lauf nicht findet.
    a.neu("Diakronos Einstellungen", {
        "name": name,
        "organisationsname": daten.GEMEINDE,
        "diakronos_anzeige_name": "Diakronos",
        "diakronos_sichtbar": 1,
        "kronos_anzeige_name": "Kronos",
        "kronos_sichtbar": 1,
        "kronos_kalender_bezeichnung": "Kalender",
        "diakonos_anzeige_name": "Diakonos",
        "diakonos_sichtbar": 1,
        "psalmos_anzeige_name": "Psalmos",
        "psalmos_sichtbar": 1,
        "seelsorge_anzeige_name": "Seelsorge",
        "seelsorge_sichtbar": 0,
        "demodaten_erstellen": 0,
        "demodaten_aktiv": 0,
        "dev_modus": 0,
    })


# ── Mitglieder ──────────────────────────────────────────────────────────────


def mitglieder_anlegen(a: Anleger, stichtag: date) -> None:
    """ca. 40 erfundene Mitglieder mit Adresse, Telefon, Mail und Geburtstag."""
    for i, person in enumerate(list(daten.MITGLIEDER) + list(daten.MITGLIEDER_AUSGETRETEN)):
        name = daten.person(person["vorname"], person["nachname"])
        _KENNUNGEN[name] = name
        # Direkte Abfrage statt `session.get`: der Identity-Map liefert auch
        # Objekte, deren INSERT noch offen ist (nach einem Rollback sind das
        # Geister) — gefragt ist, was in der DATENBANK steht. ID-1d: die
        # Kennung vergibt der Server — gesucht wird deshalb ueber Vor- und
        # Nachname und die gefundene Kennung gemerkt.
        vorhanden = a.s.execute(
            select(Mitglied.name).where(
                Mitglied.vorname == person["vorname"],
                Mitglied.nachname == person["nachname"],
            ).limit(1)
        ).scalar()
        if vorhanden is not None:
            _KENNUNGEN[name] = vorhanden
            a.merke("Mitglied")
            continue
        strasse, nummer = daten.strasse_fuer(i)
        email = daten.email_von(person["vorname"], person["nachname"])
        if person.get("konto"):
            email = daten.MITGLIED_EMAIL
        geburtstag = date(stichtag.year - (28 + (i * 7) % 45), *person["geb"])
        werte = {
            "vorname": person["vorname"],
            "nachname": person["nachname"],
            "email": email,
            "geburtstag": geburtstag.isoformat(),
            "telefonnummer": daten.telefon_fuer(i),
            "straße": strasse,
            "nummer": nummer,
            "postleitzahl": daten.PLZ,
            "wohnort": daten.ORT,
            "mitglied_seit": date(person["seit"], 3, 1).isoformat(),
            "status": person.get("status", "Aktiv"),
            "geschlecht": person.get("geschlecht"),
            "familienstand": person.get("familienstand"),
            "datenschutz_einwilligung": 1,
            "datenschutz_datum": date(stichtag.year, 1, 15).isoformat(),
            "adressbuch_sichtbarkeit": "Alle Mitglieder",
            # Das Konto wird NICHT hier verknuepft: der Benutzer entsteht erst
            # in `konten_anlegen`/dem Entrypoint, und `mitglied.user` ist ein
            # Fremdschluessel. Die Verbindung setzt `mitglied_konten_verknuepfen`.
        }
        _KENNUNGEN[name] = a.neu("Mitglied", werte)


def beziehungen_anlegen(a: Anleger) -> None:
    """Familienbeziehungen in BEIDE Richtungen (Spiegel wie in der App)."""
    for links, rechts, typ in daten.BEZIEHUNGEN:
        # Die Gegenrichtung: „Kind“ bei den Eltern ist „Elternteil“ beim Kind.
        umkehr = {"Ehepartner": "Ehepartner", "Kind": "Elternteil"}.get(typ, typ)
        for parent, ziel, kind_typ in ((links, rechts, typ), (rechts, links, umkehr)):
            parent_id = person_kennung(parent)
            ziel_id = person_kennung(ziel)
            name = f"{parent_id}-beziehung-{ziel_id}"
            if a.s.get(MitgliedBeziehung, name) is not None:
                a.merke("Beziehung")
                continue
            # Die Quelle haelt „Kind“ als eigene Richtung; „Elternteil“ zeichnet
            # den umgekehrten Weg als Spiegel aus.
            a.kind("Beziehung", MitgliedBeziehung(
                name=name, parent=parent_id, parenttype="Mitglied", parentfield="beziehungen",
                beziehung_zu=ziel_id, beziehungstyp=kind_typ,
                ist_spiegel=(kind_typ == "Elternteil"),
                docstatus=0, idx=1, creation=a.zeitpunkt, modified=a.zeitpunkt,
                owner="Administrator", modified_by="Administrator",
            ))


def mitglied_konten_verknuepfen(a: Anleger) -> None:
    """Die beiden Demo-Konten mit ihren Mitgliedern verbinden.

    Zwei Schritte, weil `mitglied.user` ein Fremdschluessel auf `user` ist:
    zuerst muss das Konto existieren (in der Demo bringt es der Entrypoint
    ueber ``ADMIN_EMAIL``/``ADMIN_PASSWORD`` mit, in Tests legt
    ``konten_anlegen`` es an). Fehlt es, wird es hier angelegt — die Demo soll
    auch ohne Entrypoint vollstaendig sein.

    Ohne Zuordnung antwortet ``profile.get_my_profile`` mit 417 („Deinem Konto
    ist noch kein Mitglied zugeordnet“) — die Profilseite bliebe leer. Beide
    Konten (Verwaltung und Mitglied) brauchen deshalb ein Mitglied.
    """
    for email in (daten.MITGLIED_EMAIL, daten.ADMIN_EMAIL):
        if a.s.get(User, email) is None:
            konten_anlegen(a)
            a.abschluss()
            break

    for email, person in ((daten.MITGLIED_EMAIL, daten.MITGLIED_PERSON),
                          (daten.ADMIN_EMAIL, daten.ADMIN_PERSON)):
        # ID-1d: die Kennung vergibt der Server — `person` ist der Anzeigename.
        mitglied = a.s.get(Mitglied, person_kennung(person))
        if mitglied is None:
            a.merke("Mitglied-Konto")
            continue
        # Die ANMELDUNG ordnet ein Konto ueber die E-MAIL des Mitglieds zu
        # (`api/session.py`: `get_value("Mitglied", {"email": user.email})`) —
        # `mitglied.user` ist ein zweiter Weg, aber die Sitzung liest den
        # ersten. Stand dort eine andere Adresse, antwortete die Sitzung mit
        # `mitglied: null`: die Seitenleiste zeigte „Kein Mitglied“ und
        # „Meine Dienste“ blieb leer (Befund PUB-2b/B2).
        geaendert = False
        if not a.nur_pruefen:
            if mitglied.email != email:
                mitglied.email = email
                geaendert = True
            if mitglied.user != email:
                mitglied.user = email
                geaendert = True
            if geaendert:
                a.s.flush()
        if geaendert or mitglied.user != email or mitglied.email != email:
            a.zaehle("Mitglied-Konto", True)
        else:
            a.merke("Mitglied-Konto")


# ── Dienstbereiche, Gruppen, Kalender ───────────────────────────────────────


def dienstbereiche_anlegen(a: Anleger) -> None:
    for i, bereich in enumerate(daten.DIENSTBEREICHE):
        if a.s.get(Dienstbereich, bereich["name"]) is not None:
            a.merke("Dienstbereich")
            continue
        a.neu("Dienstbereich", {
            "name": bereich["name"],
            "ministry": bereich["anzeige"],
            "farbe": bereich["farbe"],
            "beschreibung": bereich["beschreibung"],
            "sortierung": i + 1,
            "ancestor_path": f"/{bereich['anzeige']}/",
        })


def gruppentypen_anlegen(a: Anleger) -> None:
    for typ in daten.GRUPPENTYPEN:
        name = typ["name"]
        vorhanden = a.s.get(Gruppentyp, name)
        if vorhanden is None:
            a.neu("Gruppentyp", {"name": name, "typname": typ["anzeige"]})
        else:
            a.merke("Gruppentyp")
        for idx, rolle in enumerate(typ["rollen"], start=1):
            zeilenname = f"{name}-rolle-{idx}"
            if a.s.get(Gruppenrolle, zeilenname) is not None:
                a.merke("Gruppenrolle")
                continue
            a.kind("Gruppenrolle", Gruppenrolle(
                name=zeilenname, parent=name, parenttype="Gruppentyp", parentfield="rollen",
                rolle=rolle, ist_leitungsrolle=(idx == 1),
                docstatus=0, idx=idx, creation=a.zeitpunkt, modified=a.zeitpunkt,
                owner="Administrator", modified_by="Administrator",
            ))


def kalender_anlegen(a: Anleger) -> None:
    for kal in daten.KALENDER:
        if a.s.get(Kalender, kal["name"]) is not None:
            a.merke("Kalender")
        elif not a.nur_pruefen:
            a.s.add(Kalender(
                name=kal["name"], calendar_name=kal["anzeige"],
                calendar_color=kal["farbe"], calender_details=kal["beschreibung"],
                selbstverwaltet=False, docstatus=0, idx=0,
                creation=a.zeitpunkt, modified=a.zeitpunkt,
                owner="Administrator", modified_by="Administrator",
            ))
            a.s.flush()
            a.zaehle("Kalender", True)

        # Moderator: das Admin-Konto moderiert jeden Kalender (darf damit
        # Termine festlegen — sonst blieben alle Termine „Vorschlag“).
        zeilenname = f"{kal['name']}-moderator-admin"
        if a.s.get(KalenderModerator, zeilenname) is not None:
            a.merke("Kalender-Moderator")
            continue
        a.kind("Kalender-Moderator", KalenderModerator(
            name=zeilenname, parent=kal["name"], parenttype="Kalender",
            parentfield="kalendermoderatoren", user=daten.ADMIN_EMAIL,
            docstatus=0, idx=1, creation=a.zeitpunkt, modified=a.zeitpunkt,
            owner="Administrator", modified_by="Administrator",
        ))


def gruppen_anlegen(a: Anleger) -> None:
    for gruppe in daten.GRUPPEN:
        name = gruppe["name"]
        if a.s.get(Gruppe, name) is not None:
            a.merke("Gruppe")
        elif not a.nur_pruefen:
            bereich = a.s.get(Dienstbereich, gruppe["bereich"])
            a.s.add(Gruppe(
                name=name, gruppenname=gruppe["anzeige"],
                dienstbereich=gruppe["bereich"], gruppentyp=gruppe["typ"],
                status="Aktiv", sichtbarkeit="Alle Mitglieder",
                beschreibung=gruppe["beschreibung"],
                treffpunkt=gruppe["treffpunkt"], treffzeit=gruppe["treffzeit"],
                ancestor_path=f"/{bereich.ministry if bereich else gruppe['anzeige']}/",
                leiter=gruppe["leitung"], kalender="gruppen",
                docstatus=0, idx=0, creation=a.zeitpunkt, modified=a.zeitpunkt,
                owner="Administrator", modified_by="Administrator",
            ))
            a.s.flush()
            a.zaehle("Gruppe", True)

        zeilenname = f"{name}-verantwortlich"
        if a.s.get(GruppeVerantwortlicher, zeilenname) is None:
            leiter = a.s.get(Mitglied, gruppe["leitung"])
            a.kind("Gruppenverantwortung", GruppeVerantwortlicher(
                name=zeilenname, parent=name, parenttype="Gruppe",
                parentfield="verantwortliche",
                user=(leiter.user if leiter is not None and leiter.user else daten.ADMIN_EMAIL),
                docstatus=0, idx=1, creation=a.zeitpunkt, modified=a.zeitpunkt,
                owner="Administrator", modified_by="Administrator",
            ))
        else:
            a.merke("Gruppenverantwortung")

        for idx, anzeige in enumerate(gruppe["mitglieder"], start=1):
            zeilenname = f"{name}-mitglied-{idx}"
            if a.s.get(Gruppenmitgliedschaft, zeilenname) is not None:
                a.merke("Gruppenmitgliedschaft")
                continue
            # ID-1d: die Mitgliedsschaft zeigt auf die SERVER-Kennung.
            mitglied = person_kennung(anzeige)
            a.kind("Gruppenmitgliedschaft", Gruppenmitgliedschaft(
                name=zeilenname, parent=name, parenttype="Gruppe", parentfield="mitglieder",
                mitglied=mitglied, rolle="Mitglied", status="Aktiv",
                beitrittsdatum=date(2021, 1, 1),
                docstatus=0, idx=idx, creation=a.zeitpunkt, modified=a.zeitpunkt,
                owner="Administrator", modified_by="Administrator",
            ))


def musikteams_anlegen(a: Anleger) -> None:
    """Die Musikteams als UNTERgruppen der Gruppe „Musikteams“ anlegen.

    Das Kochbuch-Feld ``team`` waehlt über ``teams: {gruppe_unter: "Musikteams"}``
    — die Engine sucht also Gruppen, deren ``obergruppe`` genau so heisst. Ohne
    diese Obergruppe bleibt das Teamfeld leer und der Plan ohne Werte.
    """
    obergruppe = daten.MUSIKTEAMS_OBERGRUPPE
    if a.s.get(Gruppe, obergruppe) is not None:
        a.merke("Musikteam-Obergruppe")
    elif not a.nur_pruefen:
        a.s.add(Gruppe(
            name=obergruppe, gruppenname=obergruppe, dienstbereich="musik",
            gruppentyp="team", status="Aktiv", sichtbarkeit="Alle Mitglieder",
            beschreibung="Dachgruppe der Musikteams (je Team ein Gottesdienst).",
            treffpunkt="Gemeindesaal", treffzeit="nach Absprache",
            ancestor_path="/Musik/", kalender="gruppen",
            docstatus=0, idx=0, creation=a.zeitpunkt, modified=a.zeitpunkt,
            owner="Administrator", modified_by="Administrator",
        ))
        a.s.flush()
        a.zaehle("Musikteam-Obergruppe", True)

    for team in daten.MUSIKTEAMS:
        name = team["name"]
        if a.s.get(Untergruppe, name) is not None:
            a.merke("Musikteam")
        elif not a.nur_pruefen:
            a.s.add(Untergruppe(
                name=name, untergruppenname=team["anzeige"], gruppe=obergruppe,
                status="Aktiv", sichtbarkeit="Alle Mitglieder",
                beschreibung=f"Musikteam für die Gottesdienste ({name}).",
                treffpunkt="Gemeindesaal", treffzeit="Freitag 18:30",
                ancestor_path="/Musik/", docstatus=0, idx=0,
                creation=a.zeitpunkt, modified=a.zeitpunkt,
                owner="Administrator", modified_by="Administrator",
            ))
            a.s.flush()
            a.zaehle("Musikteam", True)
        for idx, anzeige in enumerate(team["mitglieder"], start=1):
            zeilenname = f"{name}-mitglied-{idx}"
            if a.s.get(Untergruppenmitgliedschaft, zeilenname) is not None:
                a.merke("Musikteam-Mitglied")
                continue
            if a.nur_pruefen:
                a.zaehle("Musikteam-Mitglied", True)
                continue
            # ID-1d: die Mitgliedsschaft zeigt auf die SERVER-Kennung.
            mitglied = person_kennung(anzeige)
            a.kind("Musikteam-Mitglied", Untergruppenmitgliedschaft(
                name=zeilenname, parent=name, parenttype="Untergruppe",
                parentfield="mitglieder", mitglied=mitglied,
                docstatus=0, idx=idx, creation=a.zeitpunkt, modified=a.zeitpunkt,
                owner="Administrator", modified_by="Administrator",
            ))


def ressourcen_anlegen(a: Anleger) -> None:
    for res in daten.RESSOURCEN:
        if a.s.get(Ressource, res["name"]) is not None:
            a.merke("Ressource")
            continue
        a.neu("Ressource", {
            "name": res["name"],
            "ressource_name": res["name"],
            "typ": res["typ"],
            "kapazitaet": res["kapazitaet"],
            "beschreibung": res["beschreibung"],
            "tags": res["tags"],
            "wartung": 0,
        })


def dienstrollen_anlegen(a: Anleger) -> None:
    for rolle in daten.DIENSTROLLEN:
        if a.s.get(Dienstrolle, rolle["name"]) is not None:
            a.merke("Dienstrolle")
            continue
        a.neu("Dienstrolle", {"name": rolle["name"], "rollenname": rolle["name"], "farbe": rolle["farbe"]})


def terminarten_anlegen(a: Anleger) -> None:
    for art in daten.TERMINKATEGORIEN:
        if a.s.get(Eventkategorie, art["name"]) is not None:
            a.merke("Terminart")
            continue
        a.neu("Eventkategorie", {
            "name": art["name"],
            "event_category_name": art["anzeige"],
            "terminart": art["terminart"],
            "farbe": art["farbe"],
            "betrifft": art["betrifft"],
        })


# ── Lieder ──────────────────────────────────────────────────────────────────


def lieder_anlegen(a: Anleger) -> None:
    """Lieder mit Kategorie und Anlass (Stammdaten der Sammlung „lieder“)."""
    kategorien = sorted({k for lied in daten.LIEDER for k in lied["kategorien"]})
    anlaesse = sorted({an for lied in daten.LIEDER for an in lied["anlaesse"]})

    for name in kategorien:
        if a.s.get(Liedkategorie, name) is not None:
            a.merke("Liedkategorie")
            continue
        a.neu("Liedkategorie", {"name": name, "kategoriename": name})
    for name in anlaesse:
        if a.s.get(Liedanlass, name) is not None:
            a.merke("Liedanlass")
            continue
        a.neu("Liedanlass", {"name": name, "anlassname": name})

    for lied in daten.LIEDER:
        name = lied["titel"]
        if a.s.get(Lied, name) is not None:
            a.merke("Lied")
        else:
            a.neu("Lied", {
                "name": name,
                "titel": lied["titel"],
                "gesangbuch_nummer": lied["nummer"],
                "aktiv": 1 if lied["aktiv"] else 0,
                "rechte_status": lied["rechte_status"],
            })

        for feld, werte, modell, art in (
            ("kategorien", lied["kategorien"], LiedKategorie, "Liedkategorie-Zeile"),
            ("anlaesse", lied["anlaesse"], LiedAnlass, "Liedanlass-Zeile"),
            ("gruppen", ["Chor"], LiedGruppenzuordnung, "Liedgruppe-Zeile"),
        ):
            for idx, wert in enumerate(werte, start=1):
                zeilenname = f"{name}-{feld}-{idx}"
                if a.s.get(modell, zeilenname) is not None:
                    a.merke(art)
                    continue
                if feld == "gruppen" and a.s.get(Gruppe, wert) is None:
                    # Gruppe (noch) nicht vorhanden — die Zuordnung folgt im
                    # naechsten Lauf (idempotent, kein toter Fremdschluessel).
                    continue
                kwargs = {"kategorie": wert} if feld == "kategorien" else (
                    {"anlass": wert} if feld == "anlaesse" else {"gruppe": wert})
                a.kind(art, modell(
                    name=zeilenname, parent=name, parenttype="Lied", parentfield=feld,
                    docstatus=0, idx=idx, creation=a.zeitpunkt, modified=a.zeitpunkt,
                    owner="Administrator", modified_by="Administrator", **kwargs,
                ))


# ── Kalender-Termine ────────────────────────────────────────────────────────


def _himmelfahrt(jahr: int) -> date:
    """Christi Himmelfahrt = Ostersonntag + 39 Tage (Gauss/Meeus)."""
    a = jahr % 19
    b, c = divmod(jahr, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    monat = (h + l - 7 * m + 114) // 31
    tag = ((h + l - 7 * m + 114) % 31) + 1
    ostern = date(jahr, monat, tag)
    return ostern + timedelta(days=39)


def _gottesdienst_sonntage(stichtag: date) -> list[date]:
    """Alle Sonntage des Beispielzeitraums (zwei Monate)."""
    ende = stichtag + timedelta(days=62)
    erster = stichtag + timedelta(days=(6 - stichtag.weekday()) % 7)
    tage = []
    tag = erster
    while tag <= ende:
        tage.append(tag)
        tag += timedelta(days=7)
    return tage


def _gottesdienst_titel(tag: date) -> str:
    """Titel eines Sonntagsgottesdienstes — ohne Konfessionsangabe.

    Die Demo laeuft ueber zwei Monate ab dem Stichtag und beruehrt damit
    Advent, Weihnachten und die Zeit danach. Fuer diese Fenster gibt es
    eindeutige, immer richtige Bezeichnungen. Ausserhalb (Sommer, Herbst)
    steht bewusst KEIN erfundenes liturgisches Etikett, sondern das Datum —
    „3. Sonntag nach Trinitatis“ waere hier nur geraten.
    """
    def erster_advent(j: int) -> date:
        # 4. Advent = letzter Sonntag VOR dem 24.12.; der 1. Advent liegt drei
        # Wochen davor. Faellt Heiligabend auf einen Sonntag, ist er selbst der
        # 4. Advent (vorher entstand daraus der 5.).
        vierter = date(j, 12, 24)
        while vierter.weekday() != 6:      # 4. Advent: Sonntag vor dem 24.
            vierter -= timedelta(days=1)
        if vierter == date(j, 12, 24):     # 24.12. ist Sonntag -> 4. Advent
            vierter -= timedelta(days=7)
        return vierter - timedelta(days=21)

    if tag == date(tag.year, 12, 24):
        return "Christvesper"
    if tag == date(tag.year, 12, 25):
        return "Gottesdienst am 1. Christfesttag"
    if tag == date(tag.year, 12, 26):
        return "Gottesdienst am 2. Christfesttag"

    start = erster_advent(tag.year)
    if tag < start:
        start = erster_advent(tag.year - 1)
    abstand = (tag - start).days // 7

    if 0 <= abstand <= 3:
        return f"Gottesdienst am {abstand + 1}. Advent"
    if abstand == 4 and tag < date(tag.year, 12, 24):
        return "Gottesdienst am 4. Advent"
    # Zwischen den Jahren: der Sonntag nach dem Christfest und danach.
    weihnachten = date(tag.year, 12, 25) if tag.month == 12 else date(tag.year - 1, 12, 25)
    if weihnachten < tag <= weihnachten + timedelta(days=6):
        return "Gottesdienst am Sonntag nach dem Christfest"
    if tag == erster_advent(tag.year) - timedelta(days=7):
        return "Gottesdienst am Christkoenigssonntag"
    # Alles andere (Epiphaniaszeit, Fastenzeit, Sommer): Datum statt Etikett.
    return f"Gottesdienst am {tag.strftime('%d.%m.%Y')}"


def termine_anlegen(a: Anleger, stichtag: date) -> None:
    """Gottesdienste (2 Monate) und feste Gemeindetermine."""
    bestehende = {
        name for (name,) in a.s.execute(select(Element.name)).all()
    }

    # Gottesdienste: Sonntag 10:00, 90 Minuten.
    for tag in _gottesdienst_sonntage(stichtag):
        name = f"gottesdienst-{tag.isoformat()}"
        if name in bestehende:
            a.merke("Termin")
            continue
        start = datetime.combine(tag, time(10, 0))
        a.neu("Element", {
            "name": name,
            "element_name": _gottesdienst_titel(tag),
            "element_start": start.strftime("%Y-%m-%d %H:%M:%S"),
            "element_end": (start + timedelta(minutes=90)).strftime("%Y-%m-%d %H:%M:%S"),
            "element_calendar": "gottesdienste",
            "element_category": "gottesdienst",
            "status": "Festgelegt",
            "gruppe": "Chor" if tag.day < 15 else None,
            "description": "Gottesdienst mit Predigt, Musik und Kinderprogramm.",
        })

    # Feste Termine (Proben, Kreise, Feste) rund um den Stichtag.
    for i, termin in enumerate(daten.TERMINE_FEST):
        tag = stichtag + timedelta(days=termin["tag"])
        name = f"termin-{tag.isoformat()}-{i:02d}"
        if name in bestehende:
            a.merke("Termin")
            continue
        start = datetime.combine(tag, _uhr(termin["start"]))
        a.neu("Element", {
            "name": name,
            "element_name": termin["titel"],
            "element_start": start.strftime("%Y-%m-%d %H:%M:%S"),
            "element_end": (start + timedelta(minutes=termin["dauer"])).strftime("%Y-%m-%d %H:%M:%S"),
            "element_calendar": termin["kalender"],
            "element_category": termin["kategorie"],
            "status": "Festgelegt",
            "description": f"Treffpunkt: {termin['ort']}",
        })


def ressourcenbuchungen_anlegen(a: Anleger, stichtag: date) -> None:
    """Buchungen aus Sicht BEIDER Demo-Konten.

    „Meine Buchungen“ auf der Startseite zeigt die Buchungen des angemeldeten
    Kontos. Lagen alle bei „Anna Beispiel“, war die Kachel fuer die
    Gemeindeleitung dauerhaft leer (Sichtpruefung PUB-2b/B3) — deshalb bucht
    das Verwaltungskonto den Gemeindesaal fuer das Gemeindefest mit.
    """
    buchungen = [
        ("buchung-gemeindefest", "Gemeindesaal", "Gemeindefest mit Mittagessen",
         stichtag + timedelta(days=35, hours=13), stichtag + timedelta(days=35, hours=20),
         "Bestätigt", daten.ADMIN_EMAIL, daten.ADMIN_PERSON),
        ("buchung-jugendraum", "Jugendraum", "Adventsbasteln",
         stichtag + timedelta(days=49, hours=14), stichtag + timedelta(days=49, hours=18),
         "Bestätigt", daten.MITGLIED_EMAIL, daten.MITGLIED_PERSON),
        ("buchung-gemeindebus", "Gemeindebus", "Ausflug der Jugend",
         stichtag + timedelta(days=56, hours=9), stichtag + timedelta(days=56, hours=19),
         "Angefragt", daten.MITGLIED_EMAIL, daten.MITGLIED_PERSON),
        ("buchung-technikraum", "Technikraum", "Einweisung Ton und Beamer",
         stichtag + timedelta(days=12, hours=17), stichtag + timedelta(days=12, hours=19),
         "Bestätigt", daten.ADMIN_EMAIL, daten.ADMIN_PERSON),
    ]
    for name, ressource, zweck, von, bis, status, konto, person in buchungen:
        if a.s.get(RessourcenBuchung, name) is not None:
            a.merke("Ressourcenbuchung")
            continue
        a.neu("Ressourcen Buchung", {
            "name": name,
            "ressource": ressource,
            "zweck": zweck,
            "datum_von": von.strftime("%Y-%m-%d %H:%M:%S"),
            "datum_bis": bis.strftime("%Y-%m-%d %H:%M:%S"),
            "gebucht_von": konto,
            "gebucht_von_name": person,
            "status": status,
            "moderiert_von": daten.ADMIN_EMAIL if status == "Bestätigt" else None,
            "notizen": "Demo-Buchung.",
        })


# ── Dienstplan (Element-Mitarbeiter) ────────────────────────────────────────


def _prediger_reihum(stichtag: date) -> Iterable[str]:
    reihum = daten.MERKMALE_PERSON["prediger"]
    for i, _ in enumerate(_gottesdienst_sonntage(stichtag)):
        yield reihum[i % len(reihum)]


def dienstplan_anlegen(a: Anleger, stichtag: date) -> None:
    """Einteilungen an den Gottesdiensten (Mitglied + Dienstrolle)."""
    from diakronos_app.models.kronos import ElementMitarbeiter

    prediger = list(_prediger_reihum(stichtag))
    moderatoren = daten.MERKMALE_PERSON["moderator"]
    ton = daten.MERKMALE_PERSON["erfahren_ton"]
    beamer = daten.MERKMALE_PERSON["erfahren_beamer"]
    kinder = ["Susanne Gerlach", "Clara Imhof", "Marta Haas", "Leonie Uhl"]

    for i, tag in enumerate(_gottesdienst_sonntage(stichtag)):
        element = f"gottesdienst-{tag.isoformat()}"
        besetzung = [
            ("Predigt", prediger[i % len(prediger)]),
            ("Moderation", moderatoren[i % len(moderatoren)]),
            ("Technik Ton", ton[i % len(ton)]),
            ("Technik Beamer", beamer[i % len(beamer)]),
            ("Kinderdienst", kinder[i % len(kinder)]),
        ]
        for idx, (rolle, mitglied) in enumerate(besetzung, start=1):
            name = f"{element}-mitarbeiter-{idx}"
            if a.s.get(ElementMitarbeiter, name) is not None:
                a.merke("Element-Mitarbeiter")
                continue
            a.kind("Element-Mitarbeiter", ElementMitarbeiter(
                name=name, parent=element, parenttype="Element",
                parentfield="mitarbeiter", mitglied=person_kennung(mitglied),
                dienstrolle=rolle,
                bestaetigt=(idx <= 3),
                docstatus=0, idx=idx, creation=a.zeitpunkt, modified=a.zeitpunkt,
                owner="Administrator", modified_by="Administrator",
            ))


def ablaufplaene_anlegen(a: Anleger, stichtag: date) -> None:
    """Ablaufplan (Positionen) fuer die ersten Gottesdienste."""
    lieder = [lied["titel"] for lied in daten.LIEDER[:6]]
    for i, tag in enumerate(_gottesdienst_sonntage(stichtag)[:4]):
        element = f"gottesdienst-{tag.isoformat()}"
        name = f"ablauf-{tag.isoformat()}"
        if a.s.get(Ablaufplan, name) is not None:
            a.merke("Ablaufplan")
        elif not a.nur_pruefen:
            a.s.add(Ablaufplan(
                name=name, titel=f"Gottesdienst {tag.isoformat()}",
                element=element, datum=tag,
                notizen="Ablauf nach dem Kochbuch-Beispiel „Gottesdienst-Ablauf“.",
                docstatus=0, idx=0, creation=a.zeitpunkt, modified=a.zeitpunkt,
                owner="Administrator", modified_by="Administrator",
            ))
            a.s.flush()
            a.zaehle("Ablaufplan", True)

        positionen = [
            ("Begrüßung", 5, "Moderation", None, "Willkommen und Wochenspruch"),
            ("Lied", 5, None, lieder[(i * 2) % len(lieder)], "Eröffnungslied"),
            ("Predigt", 20, "Predigt", None, daten.PREDIGTREIHE[i % len(daten.PREDIGTREIHE)]),
            ("Lied", 5, None, lieder[(i * 2 + 1) % len(lieder)], "Lied zur Predigt"),
            ("Fürbitten", 10, "Moderation", None, "Fürbitte und Vaterunser"),
            ("Segen und Sendung", 5, "Moderation", None, "Segen"),
        ]
        for nr, (bezeichnung, dauer, rolle, lied, detail) in enumerate(positionen, start=1):
            zeilenname = f"{name}-pos-{nr}"
            if a.s.get(AblaufplanPosition, zeilenname) is not None:
                a.merke("Ablaufplan-Position")
                continue
            mitglied = None
            if rolle == "Predigt":
                mitglied = list(_prediger_reihum(stichtag))[i]
            elif rolle == "Moderation":
                mitglied = daten.MERKMALE_PERSON["moderator"][i % 5]
            a.kind("Ablaufplan-Position", AblaufplanPosition(
                name=zeilenname, parent=name, parenttype="Ablaufplan",
                parentfield="positionen", reihenfolge=nr, bezeichnung=bezeichnung,
                dauer_minuten=dauer,
                verantwortlicher=(person_kennung(mitglied) if mitglied else None),
                referenz_doctype=None, referenz_name=None, detail=detail,
                notiz=(f"Lied: {lied}" if lied else None),
                docstatus=0, idx=nr, creation=a.zeitpunkt, modified=a.zeitpunkt,
                owner="Administrator", modified_by="Administrator",
            ))


def dienstplaene_anlegen(a: Anleger, stichtag: date) -> None:
    """Zwei Dienstplaene (Gottesdienst, Kinderdienst) mit Terminen.

    Die Sicht „Dienstplan“ der SPA liest Elemente + deren Mitarbeiter; die
    Datensaetze hier sind die PLANUNG dahinter (Vorlage, Zeitraum, Positionen,
    Termine) und machen den Bereich vollstaendig.
    """
    ende = stichtag + timedelta(days=62)
    # Gruppe = Kennung aus `daten.GRUPPEN` (die Anzeigenamen „Chor“/
    # „Kinderdienstteam“ sind NICHT die docnames), Leitung = Mitgliedsname.
    plaene = [
        ("Dienstplan Gottesdienst", "gottesdienst", "Chor", "Predigt und Moderation"),
        ("Dienstplan Kinderdienst", "kinder", "kinderdienst", "Einteilung im Kindergottesdienst"),
    ]
    for name, bereich, gruppe, beschreibung in plaene:
        if a.s.get(Dienstplan, name) is not None:
            a.merke("Dienstplan")
            continue
        a.neu("Dienstplan", {
            "name": name,
            "plantitel": name,
            "beschreibung": beschreibung,
            "dienstbereich": bereich,
            "gruppe": gruppe,
            "jahr": stichtag.year,
            "status": "Aktiv",
            "ist_entwurf": 0,
            "start_datum": stichtag.isoformat(),
            "ende_datum": ende.isoformat(),
            "leitung": (person_kennung("Anna Beispiel") if bereich == "gottesdienst"
                        else person_kennung("Susanne Gerlach")),
            "kalender": "gottesdienste",
            "plan_anzahl_positionen": 3,
        })


def dienstplan_positionen_anlegen(a: Anleger, stichtag: date) -> None:
    """Positionen der beiden Dienstplaene (wer wird wofuer eingeteilt)."""
    positionen = {
        "Dienstplan Gottesdienst": [
            ("Predigt", "Predigt", "Matthias Reuter"),
            ("Moderation", "Moderation", "Anna Beispiel"),
            ("Technik Ton", "Technik Ton", "Tobias Gerlach"),
        ],
        "Dienstplan Kinderdienst": [
            ("Kinderdienst", "Kinderdienst", "Susanne Gerlach"),
            ("Kinderdienst", "Kinderdienst", "Marta Haas"),
        ],
    }
    for plan, zeilen in positionen.items():
        for nr, (bezeichnung, rolle, mitglied) in enumerate(zeilen, start=1):
            name = f"{plan}-position-{nr}"
            if a.s.get(DienstplanPosition, name) is not None:
                a.merke("Dienstplan-Position")
                continue
            a.kind("Dienstplan-Position", DienstplanPosition(
                name=name, parent=plan, parenttype="Dienstplan", parentfield="positionen",
                reihenfolge=nr, bezeichnung=bezeichnung, dienstrolle=rolle,
                verantwortlicher=person_kennung(mitglied), status="Geplant", faellig_ab=stichtag,
                docstatus=0, idx=nr, creation=a.zeitpunkt, modified=a.zeitpunkt,
                owner="Administrator", modified_by="Administrator",
            ))

    for plan in positionen:
        for nr, tag in enumerate(_gottesdienst_sonntage(stichtag)[:4], start=1):
            zeilenname = f"{plan}-termin-{nr}"
            if a.s.get(DienstplanTermin, zeilenname) is not None:
                a.merke("Dienstplan-Termin")
                continue
            a.kind("Dienstplan-Termin", DienstplanTermin(
                name=zeilenname, parent=plan, parenttype="Dienstplan", parentfield="termine",
                datum=tag, ressource="Gemeindesaal", notiz="Sonntagsgottesdienst",
                element=f"gottesdienst-{tag.isoformat()}",
                docstatus=0, idx=nr, creation=a.zeitpunkt, modified=a.zeitpunkt,
                owner="Administrator", modified_by="Administrator",
            ))


# ── Plan-Rahmen ─────────────────────────────────────────────────────────────


def merkmal_person_anlegen(a: Anleger, schluessel: str, anzeige: str,
                           art: str = "tag") -> str:
    """Personen-Merkmal („dirigiert“, „hält die Predigt“ …) — einmal je Schluessel.

    Die Merkmale werden HIER und nicht vom Plantyp angelegt: `plantyp_speichern`
    traegt je Definition nur die in `merkmale.person` deklarierten Schluessel
    ein, und das Kochbuch deklariert je Plantyp andere (Chorplan: `dirigent`,
    `klavier`, `einsingen`; Predigerplan: `prediger` …). Die Merkmalswerte
    muessen aber VOR dem Speichern der Vorlage existieren — sonst kennt die
    Engine beim Einteilen keinen Traeger und die Plaene bleiben leer.
    """
    vorhanden = a.s.scalar(select(Merkmal).where(
        Merkmal.ziel == "person", Merkmal.schluessel == schluessel))
    if vorhanden is not None:
        a.merke("Merkmal")
        return vorhanden.id
    if a.nur_pruefen:
        a.zaehle("Merkmal", True)
        return ""
    # `art` kommt aus der Merkmalsliste des Plantyps: wer das Merkmal schon
    # eingetragen hat, hat es mit SEINER Art getan. Weicht die hier gesetzte
    # Art ab, lehnt `plantyp_speichern` die Vorlage ab („Bestehender
    # Merkmalschlüssel hat eine andere Art“).
    merkmal = Merkmal(
        ziel="person", schluessel=schluessel, art=art,
        definition={"id": schluessel, "art": art, "name": anzeige},
        created_by=daten.ADMIN_EMAIL,
    )
    a.s.add(merkmal)
    a.s.flush()
    a.zaehle("Merkmal", True)
    return merkmal.id


def merkmalwerte_anlegen(a: Anleger) -> None:
    """Personen-Merkmale (Prediger, Dirigent …) fuer die Plan-Rahmen-Engine."""
    # Art der Merkmale wie im Kochbuch (der Plantyp prueft sie beim Speichern
    # gegen die schon vorhandene Zeile): alles `tag` ausser `instrument`
    # (Auswahl aus Floete/Geige/Gitarre).
    anzeigen = {
        # Putzplan: das Kochbuch fuehrt das Merkmal als Auswahl „Familie“.
        "familie": "Familie",
        "prediger": "hält die Predigt",
        "moderator": "moderiert den Gottesdienst",
        "dirigent": "dirigiert",
        "klavier": "spielt Klavier",
        "einsingen": "leitet Einsingen",
        "erfahren_beamer": "erfahren mit Beamer",
        "erfahren_ton": "erfahren mit Ton",
        "technik_helfer": "hilft in der Technik",
        "leiter": "leitet eine Gruppe",
        "helfer": "hilft mit",
        "saenger": "singt im Musikteam",
    }
    instrumente = ("Floete", "Geige", "Gitarre")

    def art_von(schluessel: str) -> str:
        return "auswahl" if schluessel in ("instrument", "familie") else "tag"

    for schluessel, mitglieder in daten.MERKMALE_PERSON.items():
        art = art_von(schluessel)
        merkmal_id = merkmal_person_anlegen(a, schluessel, anzeigen.get(schluessel, schluessel),
                                            art=art)
        for person_nr, anzeige in enumerate(mitglieder):
            # ID-1d: `ziel_id` ist die SERVER-Kennung der Person, nicht der
            # Anzeigename — sonst findet die Engine keinen Traeger fuer das
            # Merkmal (Befund: Plaene ohne Inhalt).
            mitglied = person_kennung(anzeige)
            wert = {"wert": True}
            if schluessel == "familie":
                # Putzplan: die Auswahl traegt den NACHNAMEN der Familie
                # (die zulaessigen Werte des Kochbuchs).
                wert = {"wert": [anzeige.split()[-1]]}
            elif art == "auswahl":
                wert = {"wert": [instrumente[person_nr % len(instrumente)]]}
            vorhanden = a.s.scalar(select(MerkmalWert).where(
                MerkmalWert.merkmal == merkmal_id, MerkmalWert.ziel_id == mitglied))
            if vorhanden is not None:
                a.merke("Merkmalwert")
                continue
            if a.nur_pruefen:
                a.zaehle("Merkmalwert", True)
                continue
            a.s.add(MerkmalWert(
                merkmal=merkmal_id, ziel_id=mitglied, wert=wert,
                created_by=daten.ADMIN_EMAIL,
            ))
            a.s.flush()
            a.zaehle("Merkmalwert", True)


def plantypen_anlegen(a: Anleger, stichtag: date) -> dict[str, str]:
    """Die Kochbuch-Plantypen einrichten (neue Version je Vorlage).

    Rueckgabe: ``{schluessel: plantyp_id}``.
    """
    from diakronos_app.planrahmen import ressourcen
    from diakronos_app.planrahmen.dienste import Dienste, DienstFehler

    dienst = Dienste(a.s, daten.ADMIN_EMAIL)
    ids: dict[str, str] = {}
    # `plantyp.bereich` verweist auf `dienstbereich.name` (die Kennung). Das
    # Kochbuch nennt in `bereich` dagegen frei gewaehlte Beispiel-Bereiche
    # („Chor“, „Lobpreis“, „Freizeit“ sind ausdruecklich Beispieldaten laut
    # KOCHBUCH.md, keine eingebauten Sonderfaelle). Diese werden hier auf die
    # in dieser Gemeinde vorhandenen Dienstbereiche abgebildet; ein unbekannter
    # Bereich ist ein Fehler und wird NICHT stillschweigend uebernommen
    # (`plantyp_speichern` lehnt ihn mit „Dienstbereich nicht gefunden“ ab).
    kochbuch_bereiche = {
        "Gottesdienst": "gottesdienst",
        "Musik": "musik",
        "Chor": "musik",
        "Lobpreis": "musik",
        "Kinder": "kinder",
        "Jugend": "jugend",
        "Technik": "technik",
        "Haus": "haus",
        "Freizeit": "jugend",
    }
    bekannt = {bereich["name"] for bereich in daten.DIENSTBEREICHE}
    for schluessel in daten.PLANTYPEN:
        definition = ressourcen.kochbuch_laden(schluessel)
        roh = definition.get("bereich")
        if roh:
            ziel = kochbuch_bereiche.get(roh)
            if ziel is None or ziel not in bekannt:
                raise DemoFehler(
                    f"Kochbuch-Bereich {roh!r} von {schluessel!r} ist keinem "
                    "Dienstbereich dieser Gemeinde zugeordnet.")
            definition["bereich"] = ziel
        vorhanden = a.s.scalar(select(Plantyp).where(Plantyp.schluessel == schluessel))
        if vorhanden is not None:
            a.merke("Plantyp")
            ids[schluessel] = vorhanden.id
            continue
        if a.nur_pruefen:
            a.zaehle("Plantyp", True)
            ids[schluessel] = ""
            continue
        try:
            ergebnis = dienst.plantyp_speichern(definition, gueltig_ab=stichtag)
        except DienstFehler as exc:
            meldungen = "; ".join(m.get("meldung", "") for m in exc.meldungen)
            raise DemoFehler(f"Plantyp {schluessel!r} abgelehnt: {meldungen}") from exc
        a.s.commit()
        a.zaehle("Plantyp", True)
        ids[schluessel] = ergebnis["plantyp"] if isinstance(ergebnis, dict) else ""
    return ids


def plaene_anlegen(a: Anleger, stichtag: date, plantyp_ids: dict[str, str]) -> dict[str, str]:
    """Je Kochbuch-Plantyp einen Plan ueber zwei Monate anlegen."""
    from diakronos_app.planrahmen.dienste import Dienste, DienstFehler

    dienst = Dienste(a.s, daten.ADMIN_EMAIL)
    von_monat, bis_monat = daten.zeitraum_text(stichtag)
    ende = stichtag + timedelta(days=62)
    ids: dict[str, str] = {}

    for schluessel in daten.PLANTYPEN:
        titel = daten.PLAN_TITEL[schluessel].format(monat=von_monat)
        vorhanden = a.s.scalar(select(Plan).where(
            Plan.plantyp == plantyp_ids.get(schluessel, ""), Plan.titel == titel))
        if vorhanden is not None:
            a.merke("Plan")
            ids[schluessel] = vorhanden.id
            continue
        if a.nur_pruefen or not plantyp_ids.get(schluessel):
            a.zaehle("Plan", True)
            continue
        try:
            ergebnis = dienst.plan_anlegen(
                plantyp=plantyp_ids[schluessel],
                titel=titel,
                von=stichtag,
                bis=ende,
                parameter=dict(daten.PLAN_PARAMETER.get(schluessel, {})),
                # ID-1d: Kennung, nicht Anzeigename.
                verantwortlich=person_kennung("Anna Beispiel"),
            )
        except DienstFehler as exc:
            meldungen = "; ".join(m.get("meldung", "") for m in exc.meldungen)
            raise DemoFehler(f"Plan {titel!r} abgelehnt: {meldungen}") from exc
        a.s.commit()
        a.zaehle("Plan", True)
        ids[schluessel] = ergebnis["id"]
    return ids


def predigtreihe_fuellen(a: Anleger, plan_id: str) -> None:
    """Die Plansammlung „predigtreihe“ des Ablaufplans der Reihe nach fuellen."""
    if not plan_id:
        a.zaehle("Predigtreihe", True)
        return
    from diakronos_app.models.planrahmen import Sammlung

    sammlung = a.s.scalar(select(Sammlung).where(
        Sammlung.schluessel == "predigtreihe", Sammlung.plan == plan_id))
    if sammlung is None:
        a.merke("Predigtreihe")
        return
    vorhanden = a.s.scalar(select(SammlungEintrag).where(
        SammlungEintrag.sammlung == sammlung.id).limit(1))
    if vorhanden is not None:
        a.merke("Predigtreihe")
        return
    for nr, thema in enumerate(daten.PREDIGTREIHE):
        if a.nur_pruefen:
            a.zaehle("Predigtreihe", True)
            continue
        a.s.add(SammlungEintrag(
            sammlung=sammlung.id, reihenfolge=nr, daten={"titel": thema},
            aktiv=True, created_by=daten.ADMIN_EMAIL,
        ))
        a.zaehle("Predigtreihe", True)
    a.s.flush()


def programme_fuellen(a: Anleger) -> None:
    """Die Sammlung „programme“ (Kindergottesdienst) mit Bausteinen fuellen.

    Wie ``predigtreihe_fuellen``: Die Sammlung gehoert dem Plantyp (Umfang
    „gemeinde“) und wird beim Speichern der Vorlage leer angelegt. Ohne
    Eintraege meldet die Engine „Quelle leer“ und der Plan bleibt leer.
    """
    sammlung = a.s.scalar(select(Sammlung).where(
        Sammlung.schluessel == "programme", Sammlung.plan.is_(None)))
    if sammlung is None:
        a.merke("Programm")
        return
    vorhanden = a.s.scalar(select(SammlungEintrag).where(
        SammlungEintrag.sammlung == sammlung.id).limit(1))
    if vorhanden is not None:
        a.merke("Programm")
        return
    for nr, baustein in enumerate(daten.PROGRAMME):
        if a.nur_pruefen:
            a.zaehle("Programm", True)
            continue
        a.s.add(SammlungEintrag(
            sammlung=sammlung.id, reihenfolge=nr, daten=dict(baustein),
            aktiv=True, created_by=daten.ADMIN_EMAIL,
        ))
        a.zaehle("Programm", True)
    a.s.flush()


def plan_eintraege_fuellen(a: Anleger, stichtag: date, plan_ids: dict[str, str]) -> None:
    """Ein paar Eintraege in den Plaenen, damit sie nicht leer aussehen.

    Bewusst minimal: ein Eintrag ist ein FACHWERT am Termin („dieses Lied“,
    „diese Person“). Die Engine kann ihn selbst vorschlagen; hier werden nur
    bereits getroffene Entscheidungen abgebildet.
    """
    from diakronos_app.models.planrahmen import Termin

    chorplan = plan_ids.get("chorplan")
    if not chorplan or a.nur_pruefen:
        a.zaehle("Planeintrag", True) if not chorplan else None
        return

    lieder = [lied["titel"] for lied in daten.LIEDER]
    # Feldpfad am echten Chorplan-Slot ausrichten (die Kennung der Sammlung,
    # nicht der Anzeigename): Slot „lieder“ -> Sammlung „lieder“.
    termine = a.s.scalars(select(Termin).where(Termin.plan == chorplan).order_by(
        Termin.datum).limit(4)).all()
    for nr, termin in enumerate(termine):
        feld = "lieder.0"
        vorhanden = a.s.scalar(select(Eintrag).where(
            Eintrag.termin == termin.id, Eintrag.feld_pfad == feld, Eintrag.index.is_(None)))
        if vorhanden is not None:
            a.merke("Planeintrag")
            continue
        a.s.add(Eintrag(
            termin=termin.id, feld_pfad=feld, index=0,
            wert={"sammlung": "lieder", "titel": lieder[nr % len(lieder)]},
            quelle="manuell", meldungen=[], created_by=daten.ADMIN_EMAIL,
        ))
        a.zaehle("Planeintrag", True)
    a.s.flush()


def plan_vorschlaege_erzeugen(a: Anleger, stichtag: date,
                              plan_ids: dict[str, str]) -> dict[str, str]:
    """Fuellt die Plaene ueber die Engine — derselbe Aufruf wie in der Oberflaeche.

    „Automatisch einteilen“ ruft ``Dienste.plan_generieren`` (siehe
    ``api/planrahmen.py::plan_generieren``). Die Demo nutzt genau diesen Weg,
    damit in den Plaenen steht, was die App selbst vorschlaegt — und nicht, was
    das Seed-Skript von Hand zusammenbaut (Fachlogik bleibt in der App).

    Der Ablaufplan (Feldart ``ablauf``) wird von der Engine nicht gefuellt: dort
    werden die Elemente ueber ``ablauf_aendern`` gesetzt, wie beim Klicken in
    der Oberflaeche.
    """
    from diakronos_app.planrahmen.dienste import Dienste, DienstFehler

    dienst = Dienste(a.s, daten.ADMIN_EMAIL)
    offen: list[str] = []
    for schluessel, plan_id in plan_ids.items():
        if not plan_id:
            continue
        if a.nur_pruefen:
            a.zaehle("Planvorschlag", True)
            continue
        try:
            dienst.plan_generieren(plan_id)
        except DienstFehler:
            # Kein Vorschlag moeglich (z. B. weil eine Vorlage ohne Personen
            # ausgelegt ist) — kein Grund, die ganze Demo abzubrechen.
            offen.append(schluessel)
            continue
        a.s.commit()
        a.zaehle("Planvorschlag", True)

    # Ablaufplan: je Termin die Standardelemente des Kochbuchs anlegen.
    ablauf_id = plan_ids.get("gottesdienstablauf")
    if ablauf_id and not a.nur_pruefen:
        from diakronos_app.models.planrahmen import Termin

        elemente = ("begruessung", "lied", "predigt", "lied")
        # ALLE Termine des Plans, nicht nur die ersten: ein Aushang, der nur
        # die halbe Zeit einen Ablauf hat, ist kein Beispiel (die restlichen
        # Sonntage zeigten in der Sichtpruefung leere Blaetter).
        for termin in a.s.scalars(select(Termin).where(Termin.plan == ablauf_id)
                                  .order_by(Termin.datum)).all():
            vorhanden = bool(termin.ablauf and termin.ablauf.get("ablauf"))
            if vorhanden:
                a.merke("Ablaufelement")
                continue
            for typ in elemente:
                try:
                    dienst.ablauf_aendern(ablauf_id, termin.id, "ablauf",
                                          "hinzufuegen", typ)
                except DienstFehler:
                    continue
            a.s.commit()
            a.zaehle("Ablaufelement", True)

    if offen:
        _meldung("ohne Vorschlag (keine Personen/Regeln erfuellt): " + ", ".join(sorted(offen)))
    return plan_ids


def pfade_stelle(feld_pfad: str) -> int:
    """Stelle eines Sammlungsplatzes (``lieder[2].klavier`` -> ``2``), sonst 0."""
    treffer = re.search(r"\[(\d+)\]", feld_pfad or "")
    return int(treffer.group(1)) if treffer else 0


def dienste_der_gemeindeleitung(dienst, plan_ids: dict[str, str],
                                a: Anleger, fehler: list[str]) -> None:
    """Gibt der Gemeindeleitung (Admin-Konto) mehrere anstehende Dienste.

    Befund PUB-2b/B2: „Meine Dienste“, der Dienstplan und die Startseiten-Kachel
    sind fuer das Verwaltungskonto leer, wenn es nur EINEN Einsatz hat. Eine
    Gemeindeleitung moderiert und leitet das Einsingen — abwechselnd ueber die
    Termine, ueber denselben Schreibweg wie der Plan-Editor.
    """
    from diakronos_app.models.planrahmen import Termin

    # ID-1d: im Plan-Rahmen steht die SERVER-Kennung der Person, nicht der
    # Anzeigename (der Rahmen prueft „Mitglied nicht gefunden“).
    person = person_kennung(daten.ADMIN_PERSON)
    # Einsingen im Chorplan: jeder zweite Termin.
    chorplan = plan_ids.get("chorplan")
    if chorplan:
        termine = a.s.scalars(select(Termin).where(Termin.plan == chorplan)
                              .order_by(Termin.datum)).all()
        for nr, termin in enumerate(termine):
            if nr % 2:
                continue
            pfade = {s.feld_pfad for s in _slots(dienst, a, chorplan, termin.id)}
            if "einsingen" in pfade:
                _setzen(dienst, chorplan, termin.id, "einsingen", person, a, fehler)
        a.s.commit()
    # Moderation im Gottesdienst-Ablauf: die ersten beiden Elemente „begruessung“.
    ablauf = plan_ids.get("gottesdienstablauf")
    if ablauf:
        termine = a.s.scalars(select(Termin).where(Termin.plan == ablauf)
                              .order_by(Termin.datum)).all()
        for termin in termine[:3]:
            for slot in _slots(dienst, a, ablauf, termin.id):
                if slot.feld_pfad.endswith(".moderator"):
                    _setzen(dienst, ablauf, termin.id, slot.feld_pfad, person, a, fehler)
        a.s.commit()


def _slots(dienst, a: Anleger, plan_id: str, termin_id: str) -> list:
    """Die tatsaechlichen Feldpfade dieses Termins (aus der Terminstruktur).

    Feldpfade werden NICHT aus dem Kochbuch erraten: bei Ablauf-Feldern
    enthaelt der Pfad die Element-Kennung (``ablauf/<uuid>.lied``) und bei
    Sammlungen steht die Stelle als Index (``lieder[0]``). Diese Liste ist
    die eine Wahrheit — genau derselbe Aufruf wie in ``eintrag_setzen``.
    """
    from diakronos_app.models.planrahmen import PlantypVersion
    from diakronos_app.planrahmen.engine.struktur import aufloesen_mit_eintraegen

    p, _, _ = dienst._plan(plan_id)
    ts, em, es = dienst._kontext(p)
    t = next((x for x in ts if x.id == termin_id), None)
    if t is None:
        return []
    definition = a.s.get(PlantypVersion, t.plantyp_version).definition
    return aufloesen_mit_eintraegen(definition, em[t.id], es, parameter=p.parameter)


def _setzen(dienst, plan_id: str, termin_id: str, feld_pfad: str,
            wert, a: Anleger, fehler: list[str]) -> bool:
    """Ein Wert ueber den echten Schreibweg; Ablehnungen werden gesammelt."""
    from diakronos_app.planrahmen.dienste import DienstFehler

    try:
        dienst.eintrag_setzen(plan_id, termin_id, feld_pfad, wert)
    except DienstFehler as exc:
        meldungen = "; ".join(m.get("meldung", "") for m in exc.meldungen) or str(exc)
        fehler.append(f"{feld_pfad}: {meldungen}")
        return False
    a.zaehle("Planbesetzung", True)
    return True


def plan_besetzen_und_veroeffentlichen(a: Anleger, plan_ids: dict[str, str]) -> dict[str, str]:
    """Besetzt die Plaene von Hand und veroeffentlicht sie (Befund PUB-2b/B4).

    Die Engine (``plan_generieren``) fuellt nur die Felder, fuer die sie eine
    Regel kennt — beim Kochbuch-Chorplan bleibt deshalb „Dirigent“/„Klavier“
    leer (die Rolle ist am Sammlungseintrag deklariert, nicht am Feld). Ein
    Plan, in dem niemand steht, taugt nicht als Beispielbild. Was hier gesetzt
    wird, geht durch ``Dienste.eintrag_setzen`` — derselbe Aufruf wie das
    Klicken im Plan-Editor (Wertpruefung, Fixierung, Regelbewertung).

    Veroeffentlicht werden zwei Plaene (Chorplan und Gottesdienst-Ablauf); die
    uebrigen bleiben Entwurf — so zeigt die Uebersicht beide Zustaende.

    Rueckgabe: ``{schluessel: status}`` der behandelten Plaene.
    """
    from diakronos_app.models.planrahmen import Termin
    from diakronos_app.planrahmen.dienste import Dienste, DienstFehler

    def slots_von(dienst, plan_id: str, termin_id: str) -> list:
        return _slots(dienst, a, plan_id, termin_id)

    def setzen(dienst, plan_id: str, termin_id: str, feld_pfad: str,
               wert, fehler: list[str]) -> bool:
        return _setzen(dienst, plan_id, termin_id, feld_pfad, wert, a, fehler)

    dienst = Dienste(a.s, daten.ADMIN_EMAIL)
    stand: dict[str, str] = {}
    chorplan = plan_ids.get("chorplan")
    if chorplan:
        dirigenten = daten.MERKMALE_PERSON["dirigent"]
        klaviere = daten.MERKMALE_PERSON["klavier"]
        einsingen = daten.MERKMALE_PERSON["einsingen"]
        lieder = [lied["titel"] for lied in daten.LIEDER]
        termine = a.s.scalars(select(Termin).where(Termin.plan == chorplan)
                              .order_by(Termin.datum)).all()
        for nr, termin in enumerate(termine):
            if a.nur_pruefen:
                a.zaehle("Planbesetzung", True)
                continue
            pfade = {s.feld_pfad: s.art for s in slots_von(dienst, chorplan, termin.id)}
            offen: list[str] = []
            for feld_pfad, art in pfade.items():
                if art == "person":
                    # Personenfelder: „einsingen“, `lieder[n].dirigent`,
                    # `lieder[n].klavier` — je Platz eine passende Person.
                    if feld_pfad.endswith(".klavier") or feld_pfad == "klavier":
                        wert = klaviere[(nr + pfade_stelle(feld_pfad)) % len(klaviere)]
                    elif feld_pfad.endswith(".dirigent") or feld_pfad == "dirigent":
                        wert = dirigenten[nr % len(dirigenten)]
                    else:
                        wert = einsingen[nr % len(einsingen)]
                    # ID-1d: im Plan steht die Server-Kennung der Person.
                    wert = person_kennung(wert)
                elif art == "eintrag":
                    stelle = pfade_stelle(feld_pfad)
                    wert = lieder[(nr + 3 * stelle) % len(lieder)]
                else:
                    continue
                setzen(dienst, chorplan, termin.id, feld_pfad, wert, offen)
            if offen:
                _meldung(f"Chorplan {termin.datum}: {len(offen)} Felder abgelehnt ("
                         + "; ".join(offen[:3]) + ")")
            a.s.commit()

    # Ablauf der Gottesdienste mit Liedern hinterlegen (B4: „mit Liedern“).
    ablauf_id = plan_ids.get("gottesdienstablauf")
    if ablauf_id and not a.nur_pruefen:
        lieder = [lied["titel"] for lied in daten.LIEDER]
        prediger = daten.MERKMALE_PERSON["prediger"]
        moderatoren = daten.MERKMALE_PERSON["moderator"]
        # Die Themen der Predigtreihe kommen aus der PLAN-Sammlung (die
        # `predigtreihe_fuellen` zuvor belegt hat).
        sammlung = a.s.scalar(select(Sammlung).where(
            Sammlung.schluessel == "predigtreihe", Sammlung.plan == ablauf_id))
        # Die Wertpruefung von `eintrag_setzen` vergleicht mit der KENNUNG
        # des Sammlungseintrags (= `pr_sammlung_eintrag.id`), nicht mit dem
        # Titel — der Anzeigename kommt erst aus `daten['titel']`.
        themen = [e.id for e in sorted(
            (a.s.scalars(select(SammlungEintrag).where(
                SammlungEintrag.sammlung == sammlung.id)).all() if sammlung else []),
            key=lambda e: (e.reihenfolge or 0, e.id))]
        if not themen:
            themen = list(daten.PREDIGTREIHE)
        termine = a.s.scalars(select(Termin).where(Termin.plan == ablauf_id)
                              .order_by(Termin.datum)).all()
        for nr, termin in enumerate(termine):
            offen = []
            nr_lied = 0
            for slot in slots_von(dienst, ablauf_id, termin.id):
                # Die Elemente des Ablaufs stehen als Liste am Termin; ein Lied
                # haengt an seinem Element (`ablauf/<id>.lied`), die Begruessung
                # an einer moderierenden Person, die Predigt an einer Predigerin.
                if slot.feld_pfad.endswith(".lied"):
                    # Je Termin ANDERE Lieder: `len(offen)` allein zaehlt nur
                    # die bisher abgelehnten Felder, deshalb stand in beiden
                    # Lied-Elementen desselben Gottesdienstes dasselbe Lied.
                    wert = lieder[(nr * 2 + nr_lied) % len(lieder)]
                    nr_lied += 1
                elif slot.feld_pfad.endswith(".moderator"):
                    wert = moderatoren[nr % len(moderatoren)]
                elif slot.feld_pfad.endswith(".prediger"):
                    wert = prediger[nr % len(prediger)]
                elif slot.feld_pfad.endswith(".thema"):
                    # Die Predigtreihe ist eine PLAN-Sammlung (Kochbuch:
                    # ``umfang: plan``) mit genau einem Eintrag je Termin;
                    # feste Titel aus dem Skript passen nicht (bei mehr
                    # Terminen als Themen lehnt die Wertpruefung ab).
                    wert = themen[nr % len(themen)] if themen else None
                    if wert is None:
                        continue
                else:
                    continue
                setzen(dienst, ablauf_id, termin.id, slot.feld_pfad, wert, offen)
            if offen:
                _meldung(f"Ablauf {termin.datum}: {len(offen)} Felder abgelehnt ("
                         + "; ".join(offen[:3]) + ")")
            a.s.commit()

    # Programmablauf (Adventssingen): Ein Ablauf-Feld braucht seine Elemente,
    # bevor Werte daran haengen. Wie beim Gottesdienst-Ablauf ueber
    # `ablauf_aendern` — derselbe Weg wie das Klicken im Plan-Editor.
    programm_id = plan_ids.get("programm")
    if programm_id and not a.nur_pruefen:
        lieder = [lied["titel"] for lied in daten.LIEDER]
        termine = a.s.scalars(select(Termin).where(Termin.plan == programm_id)
                              .order_by(Termin.datum)).all()
        for nr, termin in enumerate(termine):
            if not (termin.ablauf or {}).get("ablauf"):
                for typ in ("lied", "szene", "lied", "predigt", "lied"):
                    try:
                        dienst.ablauf_aendern(programm_id, termin.id, "ablauf",
                                              "hinzufuegen", typ)
                    except DienstFehler as exc:
                        _meldung(f"Programmablauf: Element {typ} nicht angelegt "
                                 f"({exc})")
                        break
                a.s.commit()
            offen: list[str] = []
            for slot in slots_von(dienst, programm_id, termin.id):
                if slot.feld_pfad.endswith(".lied"):
                    wert = lieder[(nr * 3 + len(offen)) % len(lieder)]
                elif slot.feld_pfad.endswith(".verantwortlich"):
                    wert = daten.MERKMALE_PERSON["dirigent"][0]
                elif slot.feld_pfad.endswith(".beginn"):
                    wert = f"{18 + len(offen)}:00"
                elif slot.feld_pfad.endswith(".dauer"):
                    wert = 5
                else:
                    continue
                setzen(dienst, programm_id, termin.id, slot.feld_pfad, wert, offen)
            if offen:
                _meldung(f"Programmablauf {termin.datum}: {len(offen)} Felder abgelehnt ("
                         + "; ".join(offen[:3]) + ")")
            a.s.commit()

    # Veroeffentlichen: nur die zwei Plaene, die es zeigen sollen.
    # Vorher die Dienste der Gemeindeleitung setzen — sie gehoeren in den
    # veroeffentlichten Stand (Befund B2: sonst ist „Meine Dienste“ leer).
    dienste_der_gemeindeleitung(dienst, plan_ids, a, [])
    for schluessel in daten.VEROEFFENTLICHTE_PLAENE:
        plan_id = plan_ids.get(schluessel)
        if not plan_id:
            continue
        if a.nur_pruefen:
            a.zaehle("Veroeffentlichung", True)
            continue
        try:
            dienst.veroeffentlichen(plan_id)
        except DienstFehler as exc:
            meldungen = "; ".join(m.get("meldung", "") for m in exc.meldungen)
            _meldung(f"Plan {schluessel} NICHT veroeffentlicht: {meldungen}")
            stand[schluessel] = "entwurf"
            continue
        a.s.commit()
        a.zaehle("Veroeffentlichung", True)
        stand[schluessel] = "veroeffentlicht"
    return stand


# ── Austritte (PUB-2b/B1) ───────────────────────────────────────────────────


@contextmanager
def _als_konto(email: str) -> Iterator[None]:
    """Fuehrt die App-Aufrufe als dieses Konto aus (dieselbe Rolle wie eine Sitzung).

    Die Funktionen der App lesen ihre Identitaet aus ``frappe_compat.session``.
    Im Betrieb setzt das die ``SessionMiddleware`` aus dem ``sid``-Cookie; hier
    gibt es keinen Request, also wird die Identitaet fuer die Dauer des Aufrufs
    gesetzt. Sie wird danach ZURUECKGESETZT — ein Skript hinterlaesst keine
    angemeldete Identitaet.
    """
    from diakronos_app.frappe_compat.session import session

    vorher = session.user
    session.user = email
    try:
        yield
    finally:
        session.user = vorher


def austritte_erfassen(a: Anleger, stichtag: date) -> None:
    """Ein bis zwei Personen ueber den ECHTEN Austritts-Weg austragen.

    Status „Ausgetreten“ entsteht ausschliesslich durch
    ``api/austritt.py: mitglied_austritt`` (setzt Status, Datum, Grund und
    sperrt die Konten). Ein direkt gesetzter Status waere ein Bypass an dieser
    Logik vorbei — und der Statusfilter der Mitgliederliste zeigte eine Zahl,
    die es so nie gaebe.
    """
    from diakronos_app.api.austritt import mitglied_austritt

    for person in daten.MITGLIEDER_AUSGETRETEN:
        anzeige = daten.person(person["vorname"], person["nachname"])
        kennung = person_kennung(anzeige)
        zeile = a.s.get(Mitglied, kennung)
        if zeile is None:
            a.merke("Austritt")
            continue
        if (zeile.status or "").strip().casefold() == "ausgetreten":
            a.merke("Austritt")
            continue
        if a.nur_pruefen:
            a.zaehle("Austritt", True)
            continue
        with _als_konto(daten.ADMIN_EMAIL):
            mitglied_austritt(
                mitglied_id=kennung,
                begruendung="Wegzug aus Musterhausen (Beispieldaten)",
                datum=(stichtag - timedelta(days=45)).isoformat(),
            )
        a.zaehle("Austritt", True)


# ── Beitraege, Wiki, Uebersicht (PUB-2b/B3, B5) ────────────────────────────


def beitraege_anlegen(a: Anleger, stichtag: date) -> None:
    """Drei veroeffentlichte Beitraege ueber ``api/beitraege.create_beitrag``.

    Der echte Weg (Rollenpruefung, Autor, Veroeffentlichungsdatum) — nicht
    ``_create``: sonst fehlten Autor und ``veroeffentlicht``, und die Kachel
    „Beiträge“ bliebe leer.
    """
    from diakronos_app.api.beitraege import create_beitrag

    for nr, beitrag in enumerate(daten.BEITRAEGE):
        vorhanden = a.s.scalar(select(Beitrag).where(Beitrag.titel == beitrag["titel"]))
        if vorhanden is not None:
            a.merke("Beitrag")
            continue
        if a.nur_pruefen:
            a.zaehle("Beitrag", True)
            continue
        with _als_konto(daten.ADMIN_EMAIL):
            ergebnis = create_beitrag(
                titel=beitrag["titel"],
                inhalt=beitrag["inhalt"],
                kategorie=beitrag["kategorie"],
                auszug=beitrag["auszug"],
                bild="",
            )
        # Die Beitraege sollen im Beispielzeitraum liegen („neueste zuerst“) —
        # das Datum setzt der Endpunkt auf heute. Ein paar Tage Abstand, damit
        # die Reihenfolge im Bild eine Geschichte erzaehlt.
        if ergebnis.get("beitrag_id"):
            daten_satz = a.s.get(Beitrag, ergebnis["beitrag_id"])
            if daten_satz is not None:
                daten_satz.datum = stichtag - timedelta(days=2 * nr)
        a.s.commit()
        a.zaehle("Beitrag", True)


def wiki_anlegen(a: Anleger) -> None:
    """Drei Wiki-Artikel ueber ``api/wiki.create_wiki_artikel``."""
    from diakronos_app.api.wiki import create_wiki_artikel

    for artikel in daten.WIKI_ARTIKEL:
        vorhanden = a.s.scalar(select(WikiArtikel).where(WikiArtikel.titel == artikel["titel"]))
        if vorhanden is not None:
            a.merke("Wiki")
            continue
        if a.nur_pruefen:
            a.zaehle("Wiki", True)
            continue
        with _als_konto(daten.ADMIN_EMAIL):
            create_wiki_artikel(
                titel=artikel["titel"],
                inhalt=artikel["inhalt"],
                kategorie=artikel["kategorie"],
                tags=artikel["tags"],
                auszug=artikel["auszug"],
            )
        a.s.commit()
        a.zaehle("Wiki", True)


def widgets_anlegen(a: Anleger) -> None:
    """Die Startseiten-Kacheln der App eintragen (Tabelle ``dashboard_widget``).

    Ohne diese Zeilen ist die Uebersicht LEER (Befund PUB-2b/B3): die SPA fragt
    ``dashboard.get_available_widgets`` und zeigt, was dort steht. Die Zeilen
    sind die Kacheln des Programms (``frontend/src/diakonos/composables/
    useWidgetRegistry.js``); ``api_method`` nennt den Endpunkt, den die Kachel
    selbst aufruft. Eine Zeile OHNE ``api_method`` bleibt sichtbar, auch wenn
    der Endpunkt fehlt — deshalb steht nur dort etwas, wo die Zuordnung sicher
    ist.
    """
    for eintrag in daten.WIDGETS:
        vorhanden = a.s.scalar(select(DashboardWidget).where(
            DashboardWidget.widget_id == eintrag["widget_id"]))
        if vorhanden is not None:
            a.merke("Widget")
            continue
        werte = dict(eintrag)
        werte.setdefault("enabled", 1)
        werte.setdefault("is_system", 1)
        werte.setdefault("required_role", None)
        werte.setdefault("required_permission", None)
        werte.setdefault("empty_state_mode", None)
        werte.setdefault("empty_state_message", None)
        a.neu("Dashboard Widget", werte)


def platzhalter_pruefen(a: Anleger) -> None:
    """Meldet Stellen, an denen die Oberflaeche „undefined“/„null“ zeigte.

    Reiner Leseschritt: die Bilder in der README sollen keine Platzhalter
    tragen (Kartenvorgabe D3). Gefunden wird, was in den Beispieldaten selbst
    leer geblieben ist.
    """
    fehlend: list[str] = []
    for person in list(daten.MITGLIEDER) + list(daten.MITGLIEDER_AUSGETRETEN):
        name = daten.person(person["vorname"], person["nachname"])
        zeile = a.s.get(Mitglied, person_kennung(name))
        if zeile is None:
            continue
        for feld in ("vorname", "nachname", "email", "straße", "postleitzahl", "wohnort"):
            if not (getattr(zeile, feld, None) or "").strip():
                fehlend.append(f"{name}.{feld}")
    if fehlend:
        _meldung("leere Pflichtangaben: " + ", ".join(fehlend))


# ── Steuerung ───────────────────────────────────────────────────────────────


def pruefe_leere_datenbank(session) -> None:
    """Abbruch, wenn die Datenbank schon echte Daten enthaelt.

    Schutz gegen den teuersten Fehler: Demo-Daten in eine BETRIEBS-Datenbank
    schreiben. Die Demo duldet nur eine Datenbank ohne Mitglieder.

    Gelesen wird ueber die SITZUNG DES SKRIPTS (``session``), nicht ueber eine
    zweite: auf einer Datenbank mit nur EINER Verbindung (SQLite mit
    ``StaticPool`` in den Tests) wuerde eine parallele Sitzung die offene
    Transaktion des Skripts als fremden Schreiber sehen — und ein
    ``--pruefen``-Lauf, der alles zurueckrollt, meldete danach faelschlich
    „nicht leer“.
    """
    anzahl = session.scalar(select(Mitglied.name).limit(1))
    if anzahl is not None:
        raise DemoFehler(
            "Die Datenbank enthaelt bereits Mitglieder. Die Demo fuellt nur eine "
            "LEERE Datenbank (Wegwerf-Stack) — Abbruch."
        )


def anlegen(nur_pruefen: bool = False, stichtag: date | None = None) -> str:
    """Legt die Demo-Gemeinde an (idempotent) und liefert einen Kurzbericht."""
    from diakronos_app.db import SessionLocal

    tag = stichtag or daten.stichtag_aus_umgebung()
    session = SessionLocal()
    a = None
    try:
        if not nur_pruefen:
            pruefe_leere_datenbank(session)
        a = Anleger(session, nur_pruefen=nur_pruefen)

        einstellungen_anlegen(a)
        konten_anlegen(a)
        a.abschluss()
        mitglieder_anlegen(a, tag)
        mitglied_konten_verknuepfen(a)
        beziehungen_anlegen(a)
        dienstbereiche_anlegen(a)
        gruppentypen_anlegen(a)
        kalender_anlegen(a)
        gruppen_anlegen(a)
        musikteams_anlegen(a)
        ressourcen_anlegen(a)
        dienstrollen_anlegen(a)
        terminarten_anlegen(a)
        lieder_anlegen(a)
        widgets_anlegen(a)
        a.abschluss()

        termine_anlegen(a, tag)
        ressourcenbuchungen_anlegen(a, tag)
        dienstplan_anlegen(a, tag)
        ablaufplaene_anlegen(a, tag)
        dienstplaene_anlegen(a, tag)
        dienstplan_positionen_anlegen(a, tag)
        a.abschluss()

        merkmalwerte_anlegen(a)
        a.abschluss()

        plantyp_ids = plantypen_anlegen(a, tag)
        programme_fuellen(a)
        plan_ids = plaene_anlegen(a, tag, plantyp_ids)
        predigtreihe_fuellen(a, plan_ids.get("gottesdienstablauf", ""))
        plan_eintraege_fuellen(a, tag, plan_ids)
        a.abschluss()

        # Plaene mit der ECHTEN Engine fuellen (derselbe Weg wie „Automatisch
        # einteilen“ in der Oberflaeche). Ohne diesen Schritt stehen die Plaene
        # als leere Huelle da — fuer eine Demo unbrauchbar. Ein Fehler hier
        # bricht NICHT ab: die Stammdaten sind dann trotzdem vollstaendig, und
        # der Bericht nennt die Plaene ohne Vorschlag.
        plan_ids = plan_vorschlaege_erzeugen(a, tag, plan_ids)
        a.abschluss()

        # Besetzung von Hand (das, was die Engine nicht kennt) und
        # Veroeffentlichung der zwei Beispielplaene (Befund PUB-2b/B4).
        plan_besetzen_und_veroeffentlichen(a, plan_ids)
        a.abschluss()

        # Status „Ausgetreten“ entsteht nur ueber den echten Austritts-Weg
        # (Befund PUB-2b/B1) — nach den Plaenen, damit die Personen vorher
        # ueberall normal zugeteilt werden koennen.
        austritte_erfassen(a, tag)
        a.abschluss()

        beitraege_anlegen(a, tag)
        wiki_anlegen(a)
        a.abschluss()

        platzhalter_pruefen(a)

        bericht = a.bericht()
        _meldung(bericht)
        return bericht
    finally:
        if a is not None:
            a.schliessen()
        session.close()


def entfernen() -> str:
    """Entfernt die Demo-Datensaetze wieder (nur die eigenen Kennungen).

    Reihenfolge: erst die Kinder, dann die Eltern. Es werden ausschliesslich
    Datensaetze mit den hier vergebenen Kennungen geloescht — nichts anderes.
    """
    from sqlalchemy import text

    from diakronos_app.db import SessionLocal
    from diakronos_app.models.planrahmen import (
        Abwesenheit, Eintrag as PlanEintrag, PlantypVersion, Sammlung,
        Termin as PlanTermin, Verlauf as PlanVerlauf,
    )

    session = SessionLocal()
    geloescht: dict[str, int] = {}
    try:
        def weg(art: str, instanz: Any) -> None:
            session.delete(instanz)
            geloescht[art] = geloescht.get(art, 0) + 1

        # Plan-Rahmen: Plaene der Demo-Plantypen samt Terminen und Eintraegen.
        plantyp_ids = [p for (p,) in session.execute(select(Plantyp.id).where(
            Plantyp.schluessel.in_(daten.PLANTYPEN))).all()]
        plan_ids = [p for (p,) in session.execute(select(Plan.id).where(
            Plan.plantyp.in_(plantyp_ids))).all()] if plantyp_ids else []
        if plan_ids:
            termin_ids = [t for (t,) in session.execute(select(PlanTermin.id).where(
                PlanTermin.plan.in_(plan_ids))).all()]
            for zeile in session.scalars(select(PlanEintrag).where(
                    PlanEintrag.termin.in_(termin_ids))).all() if termin_ids else []:
                weg("Planeintrag", zeile)
            for zeile in session.scalars(select(PlanTermin).where(
                    PlanTermin.plan.in_(plan_ids))).all():
                weg("Plan-Termin", zeile)
            for zeile in session.scalars(select(Sammlung).where(
                    Sammlung.plan.in_(plan_ids))).all():
                weg("Plansammlung", zeile)
            for zeile in session.scalars(select(Plan).where(Plan.id.in_(plan_ids))).all():
                weg("Plan", zeile)
        _alle_namen = [person_kennung(daten.person(p["vorname"], p["nachname"]))
                       for p in list(daten.MITGLIEDER) + list(daten.MITGLIEDER_AUSGETRETEN)]
        for zeile in session.scalars(select(Abwesenheit).where(
                Abwesenheit.mitglied.in_(_alle_namen))).all():
            weg("Abwesenheit", zeile)
        # Versionen und Verlauf haengen an den Plantypen (RESTRICT bzw. SET NULL).
        for zeile in session.scalars(select(PlanVerlauf).where(
                PlanVerlauf.plantyp.in_(plantyp_ids))).all() if plantyp_ids else []:
            weg("Plan-Verlauf", zeile)
        for zeile in session.scalars(select(PlantypVersion).where(
                PlantypVersion.plantyp.in_(plantyp_ids))).all() if plantyp_ids else []:
            weg("Plantyp-Version", zeile)
        for zeile in session.scalars(select(Plantyp).where(
                Plantyp.schluessel.in_(daten.PLANTYPEN))).all():
            weg("Plantyp", zeile)

        # Merkmale und Werte (Personen-Merkmale der Demo).
        merkmal_ids = [m for (m,) in session.execute(select(Merkmal.id).where(
            Merkmal.ziel == "person",
            Merkmal.schluessel.in_(list(daten.MERKMALE_PERSON)))).all()]
        if merkmal_ids:
            for zeile in session.scalars(select(MerkmalWert).where(
                    MerkmalWert.merkmal.in_(merkmal_ids))).all():
                weg("Merkmalwert", zeile)
            for zeile in session.scalars(select(Merkmal).where(
                    Merkmal.id.in_(merkmal_ids))).all():
                weg("Merkmal", zeile)

        # Dienstplaene, Ablaufplaene, Termine, Buchungen.
        for zeile in session.scalars(select(DienstplanPosition)).all():
            if zeile.parent in ("Dienstplan Gottesdienst", "Dienstplan Kinderdienst"):
                weg("Dienstplan-Position", zeile)
        for zeile in session.scalars(select(DienstplanTermin)).all():
            if zeile.parent in ("Dienstplan Gottesdienst", "Dienstplan Kinderdienst"):
                weg("Dienstplan-Termin", zeile)
        for name in ("Dienstplan Gottesdienst", "Dienstplan Kinderdienst"):
            zeile = session.get(Dienstplan, name)
            if zeile is not None:
                weg("Dienstplan", zeile)

        # Ablaufplaene zeigen mit `ablaufplan.element` auf die Termine und
        # muessen daher VOR diesen weg. Bewusst als Statement: ueber ORM-Objekte
        # verschiebt die Unit of Work das DELETE und die Element-Loeschung
        # scheitert dann am Fremdschluessel `ablaufplan_element_fkey`.
        _res = session.execute(
            text("DELETE FROM ablaufplan_position WHERE parent LIKE 'ablauf-%'"))
        if _res.rowcount:
            geloescht["Ablaufplan-Position"] = geloescht.get("Ablaufplan-Position", 0) + _res.rowcount
        _res = session.execute(text("DELETE FROM ablaufplan WHERE name LIKE 'ablauf-%'"))
        if _res.rowcount:
            geloescht["Ablaufplan"] = geloescht.get("Ablaufplan", 0) + _res.rowcount
        session.flush()

        demo_elemente = (
            [f"gottesdienst-{t.isoformat()}" for t in _gottesdienst_sonntage(daten.stichtag_aus_umgebung())]
            + [f"termin-{(daten.stichtag_aus_umgebung() + timedelta(days=t['tag'])).isoformat()}-{i:02d}"
               for i, t in enumerate(daten.TERMINE_FEST)]
        )
        # Termine als Statement: die Elemente verweisen auf Gruppen/Kalender/
        # Kategorien und werden gleich als deren Eltern geloescht — ueber ORM
        # Objekte wuerde die Unit of Work das DELETE still ueberspringen.
        _res = session.execute(
            text("DELETE FROM element_mitarbeiter WHERE parent IN :p").bindparams(bindparam("p", expanding=True)), {"p": demo_elemente})
        if _res.rowcount:
            geloescht["Element-Mitarbeiter"] = geloescht.get("Element-Mitarbeiter", 0) + _res.rowcount
        _res = session.execute(
            text("DELETE FROM element WHERE name IN :p").bindparams(bindparam("p", expanding=True)), {"p": demo_elemente})
        if _res.rowcount:
            geloescht["Termin"] = geloescht.get("Termin", 0) + _res.rowcount
        session.flush()

        for name in ("buchung-gemeindefest", "buchung-jugendraum", "buchung-gemeindebus"):
            zeile = session.get(RessourcenBuchung, name)
            if zeile is not None:
                weg("Ressourcenbuchung", zeile)

        # Lieder (mit Kindzeilen).
        for lied in daten.LIEDER:
            for modell, art in ((LiedKategorie, "Liedkategorie-Zeile"),
                                (LiedAnlass, "Liedanlass-Zeile"),
                                (LiedGruppenzuordnung, "Liedgruppe-Zeile")):
                for zeile in session.scalars(select(modell).where(modell.parent == lied["titel"])).all():
                    weg(art, zeile)
            zeile = session.get(Lied, lied["titel"])
            if zeile is not None:
                weg("Lied", zeile)

        # Musikteams: erst die Mitglieder/Untergruppen, dann die Obergruppe.
        _teams = [t["name"] for t in daten.MUSIKTEAMS]
        _res = session.execute(
            text("DELETE FROM untergruppenmitgliedschaft WHERE parent IN :p")
            .bindparams(bindparam("p", expanding=True)), {"p": _teams})
        if _res.rowcount:
            geloescht["Musikteam-Mitglied"] = geloescht.get("Musikteam-Mitglied", 0) + _res.rowcount
        for team in daten.MUSIKTEAMS:
            zeile = session.get(Untergruppe, team["name"])
            if zeile is not None:
                weg("Musikteam", zeile)
        zeile = session.get(Gruppe, daten.MUSIKTEAMS_OBERGRUPPE)
        if zeile is not None:
            weg("Musikteam-Obergruppe", zeile)
        session.flush()

        # Sammlung „programme“ der Demo (Kochbuch-Bausteine, Umfang gemeinde).
        _res = session.execute(
            text("DELETE FROM pr_sammlung_eintrag WHERE sammlung IN ("
                 "SELECT id FROM pr_sammlung WHERE schluessel = 'programme')"))
        if _res.rowcount:
            geloescht["Programm"] = geloescht.get("Programm", 0) + _res.rowcount
        _res = session.execute(
            text("DELETE FROM pr_sammlung WHERE schluessel = 'programme'"))
        if _res.rowcount:
            geloescht["Programm-Sammlung"] = geloescht.get("Programm-Sammlung", 0) + _res.rowcount
        session.flush()

        # Gruppen, Beziehungen, Mitglieder.
        # Gruppenmitgliedschaften als Statement: der Parent (die Gruppe) wird
        # hier geloescht, die Unit of Work ueberspringt sonst das DELETE der
        # Kindzeilen (NULL-Primaerschluessel) — sie blieben stehen.
        _gruppen = [g["name"] for g in daten.GRUPPEN]
        _res = session.execute(
            text("DELETE FROM gruppenmitgliedschaft WHERE parent IN :p").bindparams(bindparam("p", expanding=True)), {"p": _gruppen})
        if _res.rowcount:
            geloescht["Gruppenmitgliedschaft"] = geloescht.get("Gruppenmitgliedschaft", 0) + _res.rowcount
        for gruppe in daten.GRUPPEN:
            zeile = session.get(Gruppe, gruppe["name"])
            if zeile is not None:
                weg("Gruppe", zeile)
        # Termine zuerst wirklich entfernen (sie verweisen auf die Gruppen),
        # sonst haengt die Gruppen-Loeschung am Fremdschluessel.
        session.flush()

        # `mitglied.user` zeigt auf die Konten — vor deren Loeschung aufheben.
        _res = session.execute(
            text('UPDATE mitglied SET "user" = NULL WHERE "user" IN :p')
            .bindparams(bindparam("p", expanding=True)),
            {"p": list(KONTEN)},
        )
        if _res.rowcount:
            geloescht["Mitglied-Konto"] = geloescht.get("Mitglied-Konto", 0) + _res.rowcount

        _personen = [person_kennung(daten.person(p["vorname"], p["nachname"]))
                     for p in list(daten.MITGLIEDER) + list(daten.MITGLIEDER_AUSGETRETEN)]
        _res = session.execute(
            text("DELETE FROM mitglied_beziehung WHERE parent IN :p").bindparams(bindparam("p", expanding=True)), {"p": _personen})
        if _res.rowcount:
            geloescht["Beziehung"] = geloescht.get("Beziehung", 0) + _res.rowcount
        # Auch die ueber den echten Austritts-Weg ausgetragenen Personen
        # (Befund PUB-2b/B1) gehoeren zur Demo und muessen weg.
        for person in list(daten.MITGLIEDER) + list(daten.MITGLIEDER_AUSGETRETEN):
            anzeige = daten.person(person["vorname"], person["nachname"])
            zeile = session.get(Mitglied, person_kennung(anzeige))
            if zeile is not None:
                weg("Mitglied", zeile)

        _kal = [k["name"] for k in daten.KALENDER]
        _res = session.execute(
            text("DELETE FROM kalender_moderator WHERE parent IN :p").bindparams(bindparam("p", expanding=True)), {"p": _kal})
        if _res.rowcount:
            geloescht["Kalender-Moderator"] = geloescht.get("Kalender-Moderator", 0) + _res.rowcount
        for kal in daten.KALENDER:
            zeile = session.get(Kalender, kal["name"])
            if zeile is not None:
                weg("Kalender", zeile)

        for res in daten.RESSOURCEN:
            zeile = session.get(Ressource, res["name"])
            if zeile is not None:
                weg("Ressource", zeile)
        for rolle in daten.DIENSTROLLEN:
            zeile = session.get(Dienstrolle, rolle["name"])
            if zeile is not None:
                weg("Dienstrolle", zeile)
        for art in daten.TERMINKATEGORIEN:
            zeile = session.get(Eventkategorie, art["name"])
            if zeile is not None:
                weg("Terminart", zeile)
        # Gruppentypen zeigen mit `gruppe.gruppentyp` auf sie — die Gruppen sind
        # oben schon entfernt, deshalb erst hier.
        for typ in daten.GRUPPENTYPEN:
            for zeile in session.scalars(select(Gruppenrolle).where(
                    Gruppenrolle.parent == typ["name"])).all():
                weg("Gruppenrolle", zeile)
            zeile = session.get(Gruppentyp, typ["name"])
            if zeile is not None:
                weg("Gruppentyp", zeile)
        # Dienstbereiche zuletzt: `gruppe.dienstbereich` verweist darauf.
        for bereich in daten.DIENSTBEREICHE:
            zeile = session.get(Dienstbereich, bereich["name"])
            if zeile is not None:
                weg("Dienstbereich", zeile)

        # Gruppenverantwortungen zeigen auf `user` — VOR den Konten entfernen.
        # Bewusst als Statement und NICHT ueber ORM-Objekte: die Zeilen haengen
        # an einer Kind-Tabelle, deren Eigentuemer (Gruppe/Konto) hier schon
        # geloescht ist. Die Unit of Work ueberspringt das DELETE dann still
        # (kein Fehler, keine Zeile weg) und die Konten-Loeschung scheitert
        # danach am Fremdschluessel. `parent` (Gruppenname) ist die verlaessliche
        # Zuordnung — eine Fernbeziehung auf `user` gibt es hier nicht.
        _namen = [g["name"] for g in daten.GRUPPEN]
        _res = session.execute(
            text("DELETE FROM gruppe_verantwortlicher WHERE parent IN :p").bindparams(bindparam("p", expanding=True)),
            {"p": _namen},
        )
        if _res.rowcount:
            geloescht["Gruppenverantwortung"] = geloescht.get("Gruppenverantwortung", 0) + _res.rowcount

        # Konten zuletzt (Rollen haengen daran).
        for email in KONTEN:
            for zeile in session.scalars(select(HasRole).where(HasRole.parent == email)).all():
                weg("Rollenzeile", zeile)
            zeile = session.get(User, email)
            if zeile is not None:
                weg("Konto", zeile)

        # Uebersicht, Beitraege und Wiki (PUB-2b/B3, B5). Die Reihenfolge ist
        # egal — keine der drei Tabellen zeigt auf die anderen.
        for widget in daten.WIDGETS:
            zeile = session.scalar(select(DashboardWidget).where(
                DashboardWidget.widget_id == widget["widget_id"]))
            if zeile is not None:
                weg("Widget", zeile)
        for beitrag in daten.BEITRAEGE:
            for zeile in session.scalars(select(BeitragKommentar).where(
                    BeitragKommentar.parent == beitrag["titel"])).all():
                weg("Beitrag-Kommentar", zeile)
            zeile = session.scalar(select(Beitrag).where(Beitrag.titel == beitrag["titel"]))
            if zeile is not None:
                weg("Beitrag", zeile)
        for artikel in daten.WIKI_ARTIKEL:
            zeile = session.scalar(select(WikiArtikel).where(
                WikiArtikel.titel == artikel["titel"]))
            if zeile is not None:
                weg("Wiki-Artikel", zeile)

        einst = session.get(DiakronosEinstellungen, "Diakronos Einstellungen")
        if einst is not None:
            weg("Einstellungen", einst)

        session.commit()
        bericht = ", ".join(f"{art}: {n}" for art, n in sorted(geloescht.items())) or "nichts gefunden"
        _meldung(f"entfernt — {bericht}")
        return bericht
    finally:
        session.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="musterhausen.py",
        description="Demo-Daten „Evangelische Gemeinde Musterhausen“ anlegen (nur leere DB).",
    )
    gruppe = parser.add_mutually_exclusive_group()
    gruppe.add_argument("--pruefen", action="store_true",
                        help="nur pruefen, was fehlt — nichts schreiben")
    gruppe.add_argument("--entfernen", action="store_true",
                        help="Demo-Daten wieder entfernen")
    parser.add_argument("--stichtag", default=None,
                        help="Referenztag JJJJ-MM-TT (Vorgabe: %s)" % daten.STANDARD_STICHTAG)
    args = parser.parse_args(argv)

    try:
        if args.entfernen:
            entfernen()
            return 0
        tag = date.fromisoformat(args.stichtag) if args.stichtag else None
        anlegen(nur_pruefen=args.pruefen, stichtag=tag)
        if args.pruefen:
            _meldung("Prueflauf ohne Schreibzugriff (alles zurueckgerollt).")
        return 0
    except DemoFehler as exc:
        print(f"[musterhausen] FEHLER {exc}", file=sys.stderr, flush=True)
        return 2
    except Exception as exc:  # noqa: BLE001 — klare Meldung statt Traceback-Rauschen
        print(f"[musterhausen] FEHLER {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
