"""Der Rechte-Kern — die EINE Stelle, an der Diakronos entscheidet, wer was darf.

Leitregel (Manuel 2026-11-11): ein Rechtesystem, nicht eines je Modul. Module
fragen ausschliesslich ``darf`` / ``pruefe`` / ``moderationsstufen`` /
``freigabe_stufen`` / ``sichtbare_module``; sie fuehren KEINE eigenen Rollen,
Tabellen oder Regeln.

Modell (Plan ``~/.hermes/plans/active/diakronos-rechte/plan.md``)
---------------------------------------------------------------
Ebene 1 — Systemrollen (global)
    * **Administrator** darf alles (System Manager, root, Login ``Administrator``).
    * **Fachverwaltungen** — jede NUR in ihrem Fach: Mitgliederverwaltung,
      Kalender-Moderation, Raumverwaltung, Website-Redaktion.
    * **Mitglied**: Grundzugang. **Gast**: nur ueber einen Gast-Link.

Ebene 2 — Gruppe und Untergruppe (genau zwei Ebenen, mehr gibt es nicht)
    * **HV** (genau einer je Gruppe): alles in Gruppe UND Untergruppen,
      ernennt/entfernt MV, uebertraegt das HV-Amt (der alte HV wird MV).
    * **MV**: wie HV, aber ernennt keine HV/MV.
    * **GL** (Gruppenleiter einer Untergruppe, ernannt von HV/MV): verantwortet
      die Untergruppe. Was eine GL an die Hauptgruppe gibt, wird zuerst von
      HV/MV moderiert (Stufe ``gruppe``); was an die Gemeinde geht, danach
      zusaetzlich von der Gemeinde-Moderation (Stufe ``gemeinde``).
    * **Mitglied** einer Untergruppe ist auch Mitglied der Hauptgruppe.

Ebene 3 — Module je Gruppe
    kalender, beitraege, wiki, aufgaben, lieder, dienstplaene. Ein Objekt
    gehoert einer Gruppe, einer Untergruppe (``untergruppe`` + ihre Gruppe)
    oder der Gemeinde (``gruppe`` leer). Ist das Modul in der Gruppe aus,
    sieht es niemand ausser dem Administrator.

Moderation (zwei Stufen)
    ``gruppe``   — HV/MV der Hauptgruppe moderieren, was aus einer Untergruppe
                   bzw. von einer GL an die Gruppe geht.
    ``gemeinde`` — Kalender-Moderation / Administrator / Einzelfreigabe
                   ``moderieren`` moderieren alles, was an alle Mitglieder der
                   Gemeinde geht. Termine in gemeindeweit freigegebenen
                   Kalendern gehen IMMER durch diese Stufe (auch vom Admin:
                   zweite Freigabeschicht gegen versehentlich veroeffentlichte
                   Serien).
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Iterable

from sqlalchemy import select

from diakronos_app.db import lesesitzung
from diakronos_app.models.rechte import (
    GEMEINDE_AKTIV,
    ROLLE_GL,
    ROLLE_HV,
    ROLLE_MV,
    RechteFreigabe,
    RechteGruppenrolle,
    RechteKontaktsperre,
    RechteModul,
    RechteObjekt,
)

# ── Begriffe ────────────────────────────────────────────────────────────────

#: Module, die eine Gruppe haben kann.
MODULE: tuple[str, ...] = ("kalender", "beitraege", "wiki", "aufgaben", "lieder", "dienstplaene", "chat")

#: Module, die jede NEUE Hauptgruppe von Anfang an hat (Manuel 17.11.: „Chat-Modul
#: automatisch an für alle bestehenden und neuen Gruppen“). Der Administrator kann
#: sie danach wie jedes Modul abschalten (``verwaltung.setze_module``). Bestehende
#: Gruppen bekommen sie EINMAL über die Migration ``r_chat_standard``.
STANDARD_MODULE: tuple[str, ...] = ("chat",)

#: Objekt-Typ -> Modul.
TYP_MODUL: dict[str, str] = {
    "kalender": "kalender",
    "termin": "kalender",
    "beitrag": "beitraege",
    "ankuendigung": "beitraege",
    "wiki": "wiki",
    "aufgabe": "aufgaben",
    "lied": "lieder",
    "dienstplan": "dienstplaene",
    "vorlage": "dienstplaene",
    # Chat (Konzept docs/konzepte/CHAT-KONZEPT.md, Entscheidungen 17.11.2026):
    # Gruppen-/Untergruppenchat; Direktnachrichten fragen `darf_direktnachricht`.
    "chat_gespraech": "chat",
    "chat_nachricht": "chat",
    "chat_umfrage": "chat",
}

#: Chat-Typen — eigene Regel in `darf` (Mitglieder schreiben ohne Einzelfreigabe).
CHAT_TYPEN: frozenset[str] = frozenset({"chat_gespraech", "chat_nachricht", "chat_umfrage"})

#: Typen ohne Gruppenbesitz (gemeinsame Bibliothek eines Moduls).
BIBLIOTHEK_TYPEN: frozenset[str] = frozenset({"lied"})

#: Aktionen.
LESEN = "lesen"
SCHREIBEN = "schreiben"
VORSCHLAGEN = "vorschlagen"  # schreiben mit Moderation (z. B. GL in den Gruppenkalender)
MODERIEREN = "moderieren"
ANLEGEN = "anlegen"          # neues Objekt eines Moduls in einer (Unter-)Gruppe anlegen
VERWALTEN = "verwalten"      # Objekt-/Gruppeneinstellungen, Freigaben vergeben
ROLLEN = "rollen"            # Gruppe: HV/MV ernennen (nur HV); Untergruppe: GL ernennen (HV/MV)
ERLEDIGEN = "erledigen"      # Aufgabe abhaken (Zugewiesener)
AKTIONEN = (LESEN, SCHREIBEN, VORSCHLAGEN, MODERIEREN, ANLEGEN, VERWALTEN, ROLLEN, ERLEDIGEN)

#: Moderationsstufen.
STUFE_UNTERGRUPPE = "untergruppe"  # GL (und HV/MV) — innerhalb der Untergruppe
STUFE_GRUPPE = "gruppe"
STUFE_GEMEINDE = "gemeinde"
STUFEN = (STUFE_UNTERGRUPPE, STUFE_GRUPPE, STUFE_GEMEINDE)  # Reihenfolge der Pruefung

#: Systemrolle (fachlicher Schluessel) -> Rollenname in ``Has Role`` (Bestand).
SYSTEMROLLEN: dict[str, str] = {
    "mitgliederverwaltung": "Mitgliederadministrator",
    "kalender_moderation": "Kalenderadministrator",
    "raumverwaltung": "Ressourcenmoderator",
    "website_redaktion": "Website-Moderator",
}

#: Fachverwaltung, die Gemeinde-Objekte (ohne Gruppe) eines Moduls pflegt.
GEMEINDE_FACH: dict[str, str] = {"kalender": "kalender_moderation"}

#: Rollen, die Administrator bedeuten (Vollzugriff). NICHT mehr
#: ``Mitgliederadministrator`` — die Mitgliederverwaltung ist ein Fach.
ADMIN_ROLLEN: tuple[str, ...] = ("System Manager",)

GAST = "Guest"
_LEITUNG = (ROLLE_HV, ROLLE_MV)


@dataclass(frozen=True)
class Entscheidung:
    erlaubt: bool
    grund: str

    def __bool__(self) -> bool:  # erlaubt `if darf(...):`
        return self.erlaubt


def JA(grund: str) -> Entscheidung:  # noqa: N802
    return Entscheidung(True, grund)


def NEIN(grund: str) -> Entscheidung:  # noqa: N802
    return Entscheidung(False, grund)


# ── Systemebene ─────────────────────────────────────────────────────────────


def _rollen(benutzer: str) -> tuple[str, ...]:
    """Rollen ueber die bestehende, fail-closed Quelle (Ausschluss, root, Guest).

    PERF-K1: je Aufruf EINMAL gefragt — `get_roles` liest den Ausschluss ueber
    `_kontozustand` (ganz `Mitglied` + ganz `User`).
    """
    from diakronos_app.frappe_compat.permissions import get_roles

    return _gemerkt(("rollen", benutzer), lambda: tuple(get_roles(benutzer)))


def ist_admin(benutzer: str | None) -> bool:
    """Vollzugriff: Login ``Administrator``, root oder ``System Manager``."""
    if not benutzer or benutzer == GAST:
        return False
    if benutzer == "Administrator":
        return True
    from diakronos_app.frappe_compat.permissions import ROOT_ROLLE

    rollen = _rollen(benutzer)
    return ROOT_ROLLE in rollen or any(r in rollen for r in ADMIN_ROLLEN)


def hat_systemrolle(benutzer: str | None, schluessel: str) -> bool:
    """Fachverwaltung (``mitgliederverwaltung`` …) — Admin hat jede."""
    if not benutzer or benutzer == GAST:
        return False
    if ist_admin(benutzer):
        return True
    rolle = SYSTEMROLLEN.get(schluessel)
    return bool(rolle) and rolle in _rollen(benutzer)


def _ist_angemeldetes_mitglied(benutzer: str | None) -> bool:
    """Aktives Konto, nicht Gast, nicht ausgeschlossen (fail closed).

    Ein Login, zu dem es kein aktives ``User``-Konto gibt, ist niemand — auch
    wenn der Name in einer Freigabe steht.

    PERF-K1: gemerkt (je Aufruf und Login EINMAL) — die Antwort haengt nur am
    Login, nicht an der Sitzung; der Merker wird nach jedem Schreibvorgang
    geleert.
    """
    if not benutzer or benutzer == GAST:
        return False
    if benutzer == "Administrator":
        return True

    def _lesen() -> bool:
        from diakronos_app.frappe_compat.permissions import mitglied_ausgeschlossen
        from diakronos_app.models.core import User

        with lesesitzung() as sess:
            aktiv = sess.execute(select(User.enabled).where(
                User.name == benutzer)).scalar_one_or_none()
        if not aktiv:
            return False
        return not mitglied_ausgeschlossen(benutzer)

    return bool(_gemerkt(("angemeldet", benutzer), _lesen))


# ── Gruppen- und Untergruppenebene ──────────────────────────────────────────


def _mitglied_von(sess, benutzer: str) -> str | None:
    """Mitglied-Kennung eines Logins (``mitglied.user``, sonst E-Mail normalisiert).

    PERF-K1: gemerkt (je Aufruf und Login EINMAL). Die Antwort haengt nur an
    `benutzer`, nicht an der Sitzung; der Merker wird nach jedem Schreibvorgang
    geleert.
    """
    return _gemerkt(("mitglied_von", benutzer), lambda: _mitglied_von_roh(sess, benutzer))


def _mitglied_von_roh(sess, benutzer: str) -> str | None:
    from diakronos_app.email_belegung import normalisiere
    from diakronos_app.models.core import User
    from diakronos_app.models.diakonos import Mitglied

    treffer = sess.execute(select(Mitglied.name).where(Mitglied.user == benutzer)).scalars().all()
    if len(treffer) == 1:
        return str(treffer[0])
    if len(treffer) > 1:
        return None  # mehrdeutig -> fail closed
    email = sess.execute(select(User.email).where(User.name == benutzer)).scalar_one_or_none() or benutzer
    gesucht = normalisiere(email)
    if not gesucht:
        return None
    zeilen = sess.execute(select(Mitglied.name, Mitglied.email)).all()
    passend = [n for n, e in zeilen if normalisiere(e) == gesucht]
    return str(passend[0]) if len(passend) == 1 else None


# ── Merker je Aufruf (PERF-K1) ──────────────────────────────────────────────
#
# BEFUND (PERF-K1, im Vorbau-Image gemessen: 10 Kalender, 50 Nutzer, 312
# Termine, Monatsansicht): `get_calendar_events` lief durch 110 803
# SQL-Abfragen (~60 s). Ursache war KEINE Rechte-REGEL, sondern die Zahl der
# Aufrufe: der Rechte-Kern wurde JE TERMIN erneut befragt (`_ist_moderator` ->
# `ist_moderator` -> `get_accessible_calendars` -> je Kalender 3x `rechte.*`),
# und jede Frage liest `Mitglied` + `User` VOLLSTAENDIG (`benutzer_status`).
#
# Der Merker aendert KEINE Entscheidung: er haelt nur das Ergebnis DERSELBEN
# Frage fuer DIESELBEN Eingaben innerhalb EINES Aufrufs fest. Er ist bewusst
# nicht dauerhaft (kein Prozess-Cache, kein Redis) — ein waehrend der Anfrage
# gegebenes oder genommenes Recht muss sofort wirken. Deshalb leert
# `merker_leeren()` ihn nach jedem Schreibvorgang (siehe `db.lesesitzung`).
_MERKER: ContextVar[dict | None] = ContextVar("diakronos_rechte_merker", default=None)


@contextmanager
def merkungsrahmen():
    """Einen Merker fuer die Dauer dieses Aufrufs fuehren (idempotent)."""
    vorhanden = _MERKER.get()
    if vorhanden is not None:
        yield vorhanden
        return
    token = _MERKER.set({})
    try:
        yield _MERKER.get()
    finally:
        _MERKER.reset(token)


def merker_leeren() -> None:
    """Alle gemerkten Antworten verwerfen (nach jedem Schreibvorgang).

    Geleert wird das VORHANDENE Woerterbuch (`clear()`), nicht ersetzt: der
    Rahmen (`merkungsrahmen`) haelt dieselbe Instanz, und ein Ersetzen liesse
    ihn auf einem veralteten Stand zurueck (im Test belegt).
    """
    merker = _MERKER.get()
    if merker is not None:
        merker.clear()


def _gemerkt(schluessel, frage):
    """`frage()` einmal je Aufruf; danach dieselbe Antwort (ohne Rahmen: nie)."""
    merker = _MERKER.get()
    if merker is None:
        return frage()
    if schluessel not in merker:
        merker[schluessel] = frage()
    wert = merker[schluessel]
    # Listen nie geteilt herausgeben: ein Aufrufer, der die Antwort veraendert,
    # wuerde sonst den Merker veraendern.
    return list(wert) if isinstance(wert, list) else wert


def ist_gemeindemitglied(benutzer: str | None) -> bool:
    """Gemeinde-weites Lesen (Organigramm, Namen): Admin oder ein aktives
    Konto mit eindeutig zugeordnetem Mitglied — kein Gast, fail closed."""
    if not _ist_angemeldetes_mitglied(benutzer):
        return False
    assert benutzer is not None
    if ist_admin(benutzer):
        return True
    with lesesitzung() as sess:
        return _mitglied_von(sess, benutzer) is not None


def _gruppe_lebt(sess, gruppe: str | None) -> bool:
    """Gruppe existiert und liegt NICHT im Papierkorb — sonst verleiht sie
    keine Rechte (UX2b2/F3: eine geloeschte Gruppe gibt kein Recht mehr).

    PERF-K1: gemerkt (je Aufruf und Gruppe EINMAL) — die Frage haengt nur an
    der Gruppe, nicht an der Sitzung; der Merker wird nach jedem Schreibvorgang
    geleert. Ohne Merkungsrahmen wird wie zuvor jedes Mal gelesen.
    """
    if not gruppe:
        return False

    def _lesen() -> bool:
        from diakronos_app.models.diakonos import Gruppe

        zeile = sess.execute(select(Gruppe.name, Gruppe.geloescht_am).where(
            Gruppe.name == gruppe)).first()
        return zeile is not None and zeile[1] is None

    return bool(_gemerkt(("gruppe_lebt", gruppe), _lesen))


def _rolle_eintrag(sess, benutzer: str, gruppe: str, untergruppe: str | None) -> str | None:
    """Der Rolleneintrag (``HV``/``MV``/``GL``) — PERF-K1: gemerkt.

    Die Frage hängt nur an ``(benutzer, gruppe, untergruppe)``, nicht an der
    Sitzung; der Merker wird nach jedem Schreibvorgang geleert. Ohne
    Merkungsrahmen wird wie zuvor jedes Mal gelesen.
    """
    def _lesen() -> str | None:
        bedingung = [RechteGruppenrolle.gruppe == gruppe,
                     RechteGruppenrolle.benutzer == benutzer]
        if untergruppe:
            bedingung.append(RechteGruppenrolle.untergruppe == untergruppe)
        else:
            bedingung.append(RechteGruppenrolle.untergruppe.is_(None))
        return sess.execute(select(RechteGruppenrolle.rolle).where(*bedingung)).scalar_one_or_none()

    return _gemerkt(("rolle_eintrag", benutzer, gruppe, untergruppe or ""), _lesen)


def _hauptgruppe(sess, untergruppe: str | None) -> str | None:
    if not untergruppe:
        return None
    from diakronos_app.models.diakonos import Untergruppe

    return sess.execute(select(Untergruppe.gruppe).where(Untergruppe.name == untergruppe)).scalar_one_or_none()


def _aktiv(spalte):
    """Mitgliedschaft zaehlt nur mit Status ``Aktiv`` oder ohne Status (Bestand
    der Untergruppen hat keinen). ``Inaktiv`` u. a. zaehlen NICHT (fail closed)."""
    from sqlalchemy import or_

    return or_(spalte.is_(None), spalte == "", spalte == "Aktiv")


def _ist_untergruppenmitglied(sess, mid: str, untergruppe: str) -> bool:
    from diakronos_app.models.diakonos import Untergruppenmitgliedschaft

    return bool(sess.execute(
        select(Untergruppenmitgliedschaft.name).where(
            Untergruppenmitgliedschaft.parent == untergruppe, Untergruppenmitgliedschaft.mitglied == mid,
            _aktiv(Untergruppenmitgliedschaft.status),
        ).limit(1)
    ).first())


def _ist_gruppenmitglied(sess, benutzer: str, gruppe: str) -> bool:
    """Mitglied der Gruppe, einer ihrer Untergruppen oder Rolleninhaber in ihr.

    PERF-K1: gemerkt (je Aufruf und ``(benutzer, gruppe)`` EINMAL) — die
    Frage hängt nur an den beiden Kennungen, nicht an der Sitzung; der Merker
    wird nach jedem Schreibvorgang geleert. Ohne Merkungsrahmen wird wie zuvor
    jedes Mal gelesen.
    """
    def _lesen() -> bool:
        if sess.execute(select(RechteGruppenrolle.id).where(
            RechteGruppenrolle.gruppe == gruppe, RechteGruppenrolle.benutzer == benutzer
        ).limit(1)).first():
            return True
        mid = _mitglied_von(sess, benutzer)
        return bool(mid) and _person_in_gruppe(sess, mid, gruppe)

    return bool(_gemerkt(("ist_gruppenmitglied", benutzer, gruppe), _lesen))


def _person_in_gruppe(sess, mid: str, gruppe: str) -> bool:
    """Aktive Mitgliedschaft der PERSON in der Gruppe oder einer ihrer Untergruppen."""
    from diakronos_app.models.diakonos import (
        Gruppenmitgliedschaft,
        Untergruppe,
        Untergruppenmitgliedschaft,
    )

    if sess.execute(
        select(Gruppenmitgliedschaft.name).where(
            Gruppenmitgliedschaft.parent == gruppe, Gruppenmitgliedschaft.mitglied == mid,
            _aktiv(Gruppenmitgliedschaft.status),
        ).limit(1)
    ).first():
        return True
    return bool(
        sess.execute(
            select(Untergruppenmitgliedschaft.name)
            .join(Untergruppe, Untergruppe.name == Untergruppenmitgliedschaft.parent)
            .where(Untergruppe.gruppe == gruppe, Untergruppenmitgliedschaft.mitglied == mid,
                   _aktiv(Untergruppenmitgliedschaft.status))
            .limit(1)
        ).first()
    )


def gruppenrolle(benutzer: str | None, gruppe: str | None) -> str | None:
    """Rolle in der HAUPTgruppe: ``HV`` / ``MV`` / ``Mitglied`` / ``None``.

    GL und Untergruppen-Mitglieder sind in der Hauptgruppe ``Mitglied``.
    """
    if not benutzer or not gruppe or benutzer == GAST:
        return None
    return _gemerkt(("gruppenrolle", benutzer, gruppe),
                    lambda: _gruppenrolle_roh(benutzer, gruppe))


def _gruppenrolle_roh(benutzer: str, gruppe: str) -> str | None:
    with lesesitzung() as sess:
        if not _gruppe_lebt(sess, gruppe):
            return None
        rolle = _rolle_eintrag(sess, benutzer, gruppe, None)
        if rolle in _LEITUNG:
            return str(rolle)
        if _ist_gruppenmitglied(sess, benutzer, gruppe):
            return "Mitglied"
    return None


def untergruppenrolle(benutzer: str | None, untergruppe: str | None) -> str | None:
    """Rolle in einer UNTERgruppe: ``HV``/``MV`` (geerbt) / ``GL`` / ``Mitglied`` / ``None``."""
    if not benutzer or not untergruppe or benutzer == GAST:
        return None
    return _gemerkt(("untergruppenrolle", benutzer, untergruppe),
                    lambda: _untergruppenrolle_roh(benutzer, untergruppe))


def _untergruppenrolle_roh(benutzer: str, untergruppe: str) -> str | None:
    with lesesitzung() as sess:
        gruppe = _hauptgruppe(sess, untergruppe)
        if not gruppe or not _gruppe_lebt(sess, gruppe):
            return None
        oben = _rolle_eintrag(sess, benutzer, gruppe, None)
        if oben in _LEITUNG:
            return str(oben)
        if _rolle_eintrag(sess, benutzer, gruppe, untergruppe) == ROLLE_GL:
            return ROLLE_GL
        mid = _mitglied_von(sess, benutzer)
        if mid and _ist_untergruppenmitglied(sess, mid, untergruppe):
            return "Mitglied"
    return None


def rollen_vorladen(benutzer: str | None, *, gruppen: Iterable[str] = (),
                    untergruppen: Iterable[str] = (), module: Iterable[str] = ()) -> None:
    """Rollen-, Mitgliedschafts- und Modulantworten für VIELE Einheiten vorab merken.

    PERF-K1 für Listen (Gesprächsliste, Suche): statt je Einheit 3–6
    Einzelabfragen liest diese Funktion in wenigen Sammelabfragen dieselben
    Zeilen und legt die Antworten unter DENSELBEN Merker-Schlüsseln ab, die
    ``gruppenrolle``, ``untergruppenrolle``, ``modul_aktiv``, ``_gruppe_lebt``,
    ``_rolle_eintrag`` und ``_ist_gruppenmitglied`` benutzen. Entschieden wird
    danach unverändert über ``darf`` — hier entsteht KEINE zweite Rechteregel,
    nur ein Vorrat derselben Antworten.

    Gleichheit ist Pflicht: ``test_rechte_vorladen`` vergleicht für jede
    Einheit die vorgeladene Antwort mit der Einzelfrage. Wo die Einzelfrage
    nicht eindeutig nachgebildet werden kann (doppelter Rolleneintrag — dort
    wirft ``scalar_one_or_none``), wird NICHTS gemerkt; die Einzelfrage
    läuft dann wie bisher.

    Ohne Merkungsrahmen tut die Funktion nichts. Vorhandene Merker-Einträge
    werden nie überschrieben.
    """
    merker = _MERKER.get()
    if merker is None or not benutzer or benutzer == GAST:
        return
    from diakronos_app.models.diakonos import (
        Gruppe,
        Gruppenmitgliedschaft,
        Untergruppe,
        Untergruppenmitgliedschaft,
    )

    gruppen_set = {str(g) for g in gruppen if g}
    ug_set = {str(u) for u in untergruppen if u}
    module_set = {str(m) for m in module if m in MODULE}

    with lesesitzung() as sess:
        haupt_von: dict[str, str | None] = {u: None for u in ug_set}
        if ug_set:
            for name, haupt in sess.execute(
                select(Untergruppe.name, Untergruppe.gruppe).where(Untergruppe.name.in_(ug_set))
            ).all():
                haupt_von[str(name)] = str(haupt) if haupt else None
        alle = gruppen_set | {g for g in haupt_von.values() if g}
        if not alle:
            for u in ug_set:
                merker.setdefault(("untergruppenrolle", benutzer, u), None)
            return

        lebt = {g: False for g in alle}
        for name, geloescht in sess.execute(
            select(Gruppe.name, Gruppe.geloescht_am).where(Gruppe.name.in_(alle))
        ).all():
            lebt[str(name)] = geloescht is None

        # Rolleneinträge des Benutzers: (gruppe, untergruppe|None) -> [rollen]
        eintraege: dict[tuple[str, str | None], list[str]] = {}
        hat_eintrag: set[str] = set()
        for g, u, rolle in sess.execute(
            select(RechteGruppenrolle.gruppe, RechteGruppenrolle.untergruppe, RechteGruppenrolle.rolle)
            .where(RechteGruppenrolle.benutzer == benutzer, RechteGruppenrolle.gruppe.in_(alle))
        ).all():
            hat_eintrag.add(str(g))
            if u is None:
                eintraege.setdefault((str(g), None), []).append(rolle)
            elif u:
                eintraege.setdefault((str(g), str(u)), []).append(rolle)
            # untergruppe == "" trifft weder ``is_(None)`` noch eine Kennung

        mid = _mitglied_von(sess, benutzer)
        in_gruppe: set[str] = set()
        in_untergruppe: set[str] = set()
        if mid:
            in_gruppe |= {str(g) for g in sess.execute(
                select(Gruppenmitgliedschaft.parent).where(
                    Gruppenmitgliedschaft.mitglied == mid,
                    Gruppenmitgliedschaft.parent.in_(alle),
                    _aktiv(Gruppenmitgliedschaft.status))
            ).scalars().all() if g}
            for ug, g in sess.execute(
                select(Untergruppenmitgliedschaft.parent, Untergruppe.gruppe)
                .join(Untergruppe, Untergruppe.name == Untergruppenmitgliedschaft.parent)
                .where(Untergruppenmitgliedschaft.mitglied == mid,
                       Untergruppe.gruppe.in_(alle),
                       _aktiv(Untergruppenmitgliedschaft.status))
            ).all():
                if g:
                    in_gruppe.add(str(g))
                if ug:
                    in_untergruppe.add(str(ug))

        modul_an: set[tuple[str, str]] = set()
        if module_set:
            modul_an = {(str(g), str(m)) for g, m in sess.execute(
                select(RechteModul.gruppe, RechteModul.modul).where(
                    RechteModul.gruppe.in_(alle), RechteModul.modul.in_(module_set))
            ).all()}

    def _eintrag(g: str, u: str | None) -> tuple[bool, str | None]:
        """(eindeutig?, rolle) — wie ``_rolle_eintrag``; doppelt = nicht eindeutig."""
        werte = eintraege.get((g, u), [])
        if len(werte) > 1:
            return False, None
        return True, (werte[0] if werte else None)

    for g in alle:
        merker.setdefault(("gruppe_lebt", g), lebt[g])
        for m in module_set:
            merker.setdefault(("modul_aktiv", g, m), lebt[g] and (g, m) in modul_an)
        mitglied = g in hat_eintrag or g in in_gruppe
        merker.setdefault(("ist_gruppenmitglied", benutzer, g), mitglied)
        eindeutig, oben = _eintrag(g, None)
        if not eindeutig:
            continue
        merker.setdefault(("rolle_eintrag", benutzer, g, ""), oben)
        if not lebt[g]:
            rolle = None
        elif oben in _LEITUNG:
            rolle = str(oben)
        else:
            rolle = "Mitglied" if mitglied else None
        merker.setdefault(("gruppenrolle", benutzer, g), rolle)

    for u in ug_set:
        g = haupt_von.get(u)
        if not g or not lebt.get(g):
            merker.setdefault(("untergruppenrolle", benutzer, u), None)
            continue
        eindeutig_oben, oben = _eintrag(g, None)
        eindeutig_unten, unten = _eintrag(g, u)
        if not (eindeutig_oben and eindeutig_unten):
            continue
        merker.setdefault(("rolle_eintrag", benutzer, g, u), unten)
        if oben in _LEITUNG:
            rolle = str(oben)
        elif unten == ROLLE_GL:
            rolle = ROLLE_GL
        elif u in in_untergruppe:
            rolle = "Mitglied"
        else:
            rolle = None
        merker.setdefault(("untergruppenrolle", benutzer, u), rolle)


def eigene_gruppen(benutzer: str | None) -> set[str]:
    """Hauptgruppen, in denen der Benutzer eine Rolle (HV/MV/GL) hat oder
    aktives Mitglied ist (auch ueber eine Untergruppe). Papierkorb: nein."""
    if not benutzer or benutzer == GAST:
        return set()
    from diakronos_app.models.diakonos import (
        Gruppe,
        Gruppenmitgliedschaft,
        Untergruppe,
        Untergruppenmitgliedschaft,
    )

    with lesesitzung() as sess:
        namen = set(sess.execute(
            select(RechteGruppenrolle.gruppe).where(RechteGruppenrolle.benutzer == benutzer)
        ).scalars())
        mid = _mitglied_von(sess, benutzer)
        if mid:
            namen |= set(sess.execute(select(Gruppenmitgliedschaft.parent).where(
                Gruppenmitgliedschaft.mitglied == mid, _aktiv(Gruppenmitgliedschaft.status))).scalars())
            namen |= set(sess.execute(
                select(Untergruppe.gruppe)
                .join(Untergruppenmitgliedschaft, Untergruppenmitgliedschaft.parent == Untergruppe.name)
                .where(Untergruppenmitgliedschaft.mitglied == mid, _aktiv(Untergruppenmitgliedschaft.status))
            ).scalars())
        namen.discard(None)
        if not namen:
            return set()
        return set(sess.execute(select(Gruppe.name).where(
            Gruppe.name.in_(namen), Gruppe.geloescht_am.is_(None))).scalars())


def person_in_einheit(mitglied: str | None, gruppe: str | None = None,
                      untergruppe: str | None = None) -> bool:
    """Gehoert die PERSON (Mitglied-Kennung, auch ohne Konto) zur (Unter-)Gruppe?

    Fuer Zuweisungen (R-7b): aktive Mitgliedschaft oder eine Rolle ueber ihr
    Konto. Bei einer Untergruppe zaehlen nur deren Mitglieder und Leitung
    (GL, HV/MV der Gruppe). Gruppe im Papierkorb: niemand (fail closed).
    """
    if not mitglied or not (gruppe or untergruppe):
        return False
    from diakronos_app.models.diakonos import Mitglied

    with lesesitzung() as sess:
        hauptgruppe = _hauptgruppe(sess, untergruppe) if untergruppe else gruppe
        if not hauptgruppe or (gruppe and gruppe != hauptgruppe) or not _gruppe_lebt(sess, hauptgruppe):
            return False
        if untergruppe:
            if _ist_untergruppenmitglied(sess, mitglied, untergruppe):
                return True
        elif _person_in_gruppe(sess, mitglied, hauptgruppe):
            return True
        konto = sess.execute(select(Mitglied.user).where(Mitglied.name == mitglied)).scalar_one_or_none()
    if not konto:
        return False
    if untergruppe:
        return untergruppenrolle(konto, untergruppe) is not None
    return gruppenrolle(konto, hauptgruppe) is not None


def ist_gl_in_gruppe(benutzer: str | None, gruppe: str | None) -> bool:
    """Ist der Benutzer GL irgendeiner Untergruppe dieser Hauptgruppe?"""
    if not benutzer or not gruppe:
        return False
    with lesesitzung() as sess:
        return bool(sess.execute(select(RechteGruppenrolle.id).where(
            RechteGruppenrolle.gruppe == gruppe, RechteGruppenrolle.benutzer == benutzer,
            RechteGruppenrolle.rolle == ROLLE_GL,
        ).limit(1)).first())


def modul_aktiv(gruppe: str | None, modul: str) -> bool:
    """Ist ``modul`` in dieser Gruppe an? PERF-K1: gemerkt (je Aufruf EINMAL).

    Die Antwort haengt nur an ``(gruppe, modul)``, nicht an der Sitzung; der
    Merker wird nach jedem Schreibvorgang geleert. Ohne Merkungsrahmen wird wie
    zuvor jedes Mal gelesen.
    """
    if not gruppe or modul not in MODULE:
        return False

    def _lesen() -> bool:
        with lesesitzung() as sess:
            return _gruppe_lebt(sess, gruppe) and bool(
                sess.execute(
                    select(RechteModul.id).where(
                        RechteModul.gruppe == gruppe,
                        RechteModul.modul == modul).limit(1)
                ).first()
            )

    return bool(_gemerkt(("modul_aktiv", gruppe, modul), _lesen))


def _darf_gruppe(benutzer: str, aktion: str, gruppe: str) -> Entscheidung:
    """Aktionen an der Hauptgruppe selbst (Daten, Module, Mitglieder, HV/MV)."""
    rolle = gruppenrolle(benutzer, gruppe)
    if aktion == LESEN:
        return JA(f"gruppe_{rolle.lower()}") if rolle else NEIN("kein_gruppenmitglied")
    if aktion in (SCHREIBEN, VERWALTEN, ANLEGEN, MODERIEREN):
        return JA(f"gruppe_{rolle.lower()}") if rolle in _LEITUNG else NEIN("nicht_verantwortlich")
    if aktion == ROLLEN:
        return JA("gruppe_hv") if rolle == ROLLE_HV else NEIN("nur_hv")
    return NEIN("aktion_nicht_fuer_gruppe")


def _darf_untergruppe(benutzer: str, aktion: str, untergruppe: str) -> Entscheidung:
    """Aktionen an der Untergruppe selbst (Daten, Mitglieder, GL)."""
    rolle = untergruppenrolle(benutzer, untergruppe)
    if aktion == LESEN:
        return JA(f"untergruppe_{rolle.lower()}") if rolle else NEIN("kein_untergruppenmitglied")
    if aktion in (SCHREIBEN, VERWALTEN, ANLEGEN):
        if rolle in (ROLLE_HV, ROLLE_MV, ROLLE_GL):
            return JA(f"untergruppe_{rolle.lower()}")
        return NEIN("nicht_verantwortlich")
    if aktion == ROLLEN:  # GL ernennen/entfernen
        return JA(f"gruppe_{rolle.lower()}") if rolle in _LEITUNG else NEIN("nur_hv_mv")
    return NEIN("aktion_nicht_fuer_untergruppe")


# ── Objektebene ─────────────────────────────────────────────────────────────


def _objekt(sess, typ: str, objekt: str) -> RechteObjekt | None:
    return sess.execute(
        select(RechteObjekt).where(RechteObjekt.typ == typ, RechteObjekt.objekt == objekt)
    ).scalar_one_or_none()


def _freigaben(sess, typ: str, objekt: str, benutzer: str) -> tuple[bool, bool, bool, bool]:
    """(lesen, schreiben, moderieren, vorschlagen) — gemerkt (PERF-K1)."""
    return _gemerkt(("freigaben", typ, objekt, benutzer),
                    lambda: _freigaben_roh(sess, typ, objekt, benutzer))


def _freigaben_roh(sess, typ: str, objekt: str, benutzer: str) -> tuple[bool, bool, bool, bool]:
    """(lesen, schreiben, moderieren, vorschlagen) aus Personen- UND Gruppen-Freigaben.

    Gruppen-Freigabe: ``lesen`` gilt fuer jedes Gruppenmitglied (inkl. GL,
    HV/MV), ``schreiben``/``moderieren`` fuer HV und MV der Gruppe;
    GL der Gruppe duerfen bei ``schreiben`` VORSCHLAGEN (Stufe ``gruppe``).
    """
    lesen = schreiben = moderieren = vorschlagen = False
    zeilen = sess.execute(
        select(RechteFreigabe).where(RechteFreigabe.typ == typ, RechteFreigabe.objekt == objekt)
    ).scalars().all()
    for fg in zeilen:
        if fg.benutzer == benutzer:
            lesen |= bool(fg.lesen or fg.schreiben or fg.moderieren)
            schreiben |= bool(fg.schreiben)
            moderieren |= bool(fg.moderieren)
        elif fg.gruppe:
            rolle = gruppenrolle(benutzer, fg.gruppe)
            if not rolle:
                continue
            lesen |= bool(fg.lesen or fg.schreiben or fg.moderieren)
            if rolle in _LEITUNG:
                schreiben |= bool(fg.schreiben)
                moderieren |= bool(fg.moderieren)
            elif fg.schreiben and ist_gl_in_gruppe(benutzer, fg.gruppe):
                vorschlagen = True
    return lesen, schreiben, moderieren, vorschlagen or schreiben


def _gruppen_mit_modul(modul: str) -> list[str]:
    with lesesitzung() as sess:
        return [str(g) for g in sess.execute(select(RechteModul.gruppe).where(RechteModul.modul == modul)).scalars()]


def _darf_bibliothek(benutzer: str, aktion: str, modul: str) -> Entscheidung:
    rollen = [gruppenrolle(benutzer, g) for g in _gruppen_mit_modul(modul)]
    if aktion == LESEN:
        return JA("modul_in_gruppe") if any(rollen) else NEIN("modul_nicht_in_eigener_gruppe")
    if aktion in (SCHREIBEN, ANLEGEN, VERWALTEN):
        if any(r in _LEITUNG for r in rollen):
            return JA("verantwortlich_in_modulgruppe")
        return NEIN("nicht_verantwortlich")
    return NEIN("aktion_nicht_fuer_bibliothek")


def _gemeinde_moderation(benutzer: str, typ: str, freigabe_moderieren: bool) -> Entscheidung:
    if typ in ("kalender", "termin") and hat_systemrolle(benutzer, "kalender_moderation"):
        return JA("kalender_moderation")
    return JA("freigabe_moderieren") if freigabe_moderieren else NEIN("kein_moderationsrecht")


def _darf_roh(
    benutzer: str | None,
    aktion: str,
    typ: str,
    objekt: str | None = None,
    *,
    gruppe: str | None = None,
    untergruppe: str | None = None,
    besitzer: str | None = None,
    zugewiesen: Iterable[str] = (),
    stufe: str = STUFE_GEMEINDE,
) -> Entscheidung:
    """Die EINE Rechtefrage.

    ``typ``: ``gruppe``, ``untergruppe`` oder ein Objekt-Typ aus :data:`TYP_MODUL`.
    ``objekt``: Kennung des Objekts (bei ``anlegen`` leer; dann ``gruppe``
    bzw. ``untergruppe``). ``besitzer``/``zugewiesen``: Aufgaben.
    ``stufe``: bei ``moderieren`` die Moderationsstufe (``gruppe``/``gemeinde``).
    """
    if aktion not in AKTIONEN:
        return NEIN("aktion_unbekannt")
    if not _ist_angemeldetes_mitglied(benutzer):
        return NEIN("nicht_angemeldet")
    assert benutzer is not None
    if ist_admin(benutzer):
        return JA("admin")

    if typ == "gruppe":
        return _darf_gruppe(benutzer, aktion, gruppe or objekt or "")
    if typ == "untergruppe":
        return _darf_untergruppe(benutzer, aktion, untergruppe or objekt or "")

    modul = TYP_MODUL.get(typ)
    if not modul:
        return NEIN("typ_unbekannt")

    zugewiesen_set = set(zugewiesen)

    if typ in CHAT_TYPEN:
        return _darf_chat(benutzer, aktion, gruppe=gruppe, untergruppe=untergruppe,
                          besitzer=besitzer)

    # Eigene (persoenliche) Aufgabe: keine Gruppe, gehoert dem Besitzer.
    if typ == "aufgabe" and not gruppe and not untergruppe and besitzer:
        if benutzer == besitzer:
            return JA("eigene_aufgabe")
        if aktion in (LESEN, ERLEDIGEN) and benutzer in zugewiesen_set:
            return JA("zugewiesen")
        return NEIN("fremde_aufgabe")

    if typ in BIBLIOTHEK_TYPEN:
        return _darf_bibliothek(benutzer, aktion, modul)

    with lesesitzung() as sess:
        eintrag = _objekt(sess, typ, objekt) if objekt else None
        if objekt and eintrag is None:
            return NEIN("objekt_unbekannt")  # fail closed: nicht registriert
        zuntergruppe = (eintrag.untergruppe if eintrag else None) or untergruppe
        zgruppe = (eintrag.gruppe if eintrag else None) or gruppe or _hauptgruppe(sess, zuntergruppe)
        lesen, schreiben, moderieren, vorschlagen = (
            _freigaben(sess, typ, eintrag.objekt, benutzer) if eintrag else (False, False, False, False)
        )

        # ── Gemeinde-Objekt (keine Gruppe): Admin + Fachverwaltung pflegen ──
        if not zgruppe:
            if not eintrag:
                return NEIN("keine_gruppe")
            fach = GEMEINDE_FACH.get(modul)
            fachrolle = bool(fach) and hat_systemrolle(benutzer, fach)
            if aktion == MODERIEREN:
                if stufe == STUFE_GRUPPE:
                    return NEIN("gemeinde_objekt_ohne_gruppenstufe")
                return _gemeinde_moderation(benutzer, typ, moderieren)
            if aktion in (ANLEGEN, VERWALTEN, SCHREIBEN, VORSCHLAGEN) and fachrolle:
                return JA(f"fach_{fach}")
            if aktion in (ANLEGEN, VERWALTEN, ROLLEN):
                return NEIN("nur_admin_oder_fach")
            if aktion == SCHREIBEN:
                return JA("freigabe_schreiben") if schreiben else NEIN("kein_schreibrecht")
            if aktion == VORSCHLAGEN:
                return JA("freigabe_vorschlagen") if vorschlagen else NEIN("kein_vorschlagsrecht")
            if aktion == ERLEDIGEN:
                return JA("zugewiesen") if benutzer in zugewiesen_set else NEIN("nicht_zugewiesen")
            if lesen or fachrolle:
                return JA("freigabe")
            if eintrag.gemeinde_status == GEMEINDE_AKTIV and _mitglied_von(sess, benutzer):
                return JA("gemeinde")
            return NEIN("kein_leserecht")

        # ── Gruppen- oder Untergruppen-Objekt ──
        if not modul_aktiv(zgruppe, modul):
            return NEIN("modul_aus")
        hrolle = gruppenrolle(benutzer, zgruppe)
        urolle = untergruppenrolle(benutzer, zuntergruppe) if zuntergruppe else None
        hauptleitung = hrolle in _LEITUNG
        leitung = hauptleitung or urolle == ROLLE_GL
        rolle_name = (urolle if urolle == ROLLE_GL else hrolle) or ""

        if aktion == MODERIEREN:
            if stufe == STUFE_GRUPPE:
                return JA(f"gruppe_{hrolle.lower()}") if hauptleitung else NEIN("nur_hv_mv")
            return _gemeinde_moderation(benutzer, typ, moderieren)

        if aktion in (ANLEGEN, VERWALTEN):
            return JA(f"leitung_{rolle_name.lower()}") if leitung else NEIN("nicht_verantwortlich")
        if aktion == ROLLEN:
            return NEIN("rollen_nur_an_der_gruppe")

        if aktion == ERLEDIGEN:
            if benutzer in zugewiesen_set:
                return JA("zugewiesen")
            return JA(f"leitung_{rolle_name.lower()}") if leitung else NEIN("nicht_zugewiesen")

        # Abhaengiges Objekt (Dienstplan eines Kalenders): sichtbar nur mit
        # Schreibrecht am Eltern-Objekt; bearbeiten nur die Leitung.
        if eintrag and eintrag.eltern_typ and eintrag.eltern_objekt and not leitung:
            if aktion == LESEN:
                e = darf(benutzer, SCHREIBEN, eintrag.eltern_typ, eintrag.eltern_objekt)
                return JA("eltern_schreiben") if e else NEIN("eltern_ohne_schreibrecht")
            return NEIN("nicht_verantwortlich")

        if leitung:
            return JA(f"leitung_{rolle_name.lower()}")

        if aktion == SCHREIBEN:
            return JA("freigabe_schreiben") if schreiben else NEIN("kein_schreibrecht")
        if aktion == VORSCHLAGEN:
            # GL einer Untergruppe schlaegt im Objekt der Hauptgruppe vor (Stufe gruppe).
            if schreiben or vorschlagen:
                return JA("freigabe_vorschlagen")
            if not zuntergruppe and ist_gl_in_gruppe(benutzer, zgruppe):
                return JA("gl_vorschlag")
            return NEIN("kein_vorschlagsrecht")

        # LESEN
        if lesen:
            return JA("freigabe")
        if eintrag is None or eintrag.standard_gruppe_lesen:
            if zuntergruppe and urolle == "Mitglied":
                return JA("untergruppe_mitglied")
            if not zuntergruppe and hrolle == "Mitglied":
                return JA("gruppe_mitglied")
        if zuntergruppe and eintrag and eintrag.gruppe_status == GEMEINDE_AKTIV and hrolle:
            return JA("gruppe_freigabe")
        if eintrag and eintrag.gemeinde_status == GEMEINDE_AKTIV and _mitglied_von(sess, benutzer):
            return JA("gemeinde")
        return NEIN("kein_leserecht")


def _stufen_kontext(sess, benutzer: str, typ: str, eintrag) -> dict:
    """Bausteine fuer die Stufen-Entscheidung (eine Sitzung, keine Rekursion)."""
    admin = ist_admin(benutzer)
    _l, schreiben, moderieren, vorschlagen = _freigaben(sess, typ, eintrag.objekt, benutzer)
    hauptleitung = bool(eintrag.gruppe) and gruppenrolle(benutzer, eintrag.gruppe) in _LEITUNG
    gl = bool(eintrag.untergruppe) and untergruppenrolle(benutzer, eintrag.untergruppe) == ROLLE_GL
    modul_an = not eintrag.gruppe or modul_aktiv(eintrag.gruppe, TYP_MODUL.get(typ, ""))
    fach = GEMEINDE_FACH.get(TYP_MODUL.get(typ, ""))
    return {
        "admin": admin, "schreiben": schreiben, "moderieren": moderieren,
        "vorschlagen": vorschlagen, "hauptleitung": hauptleitung, "gl": gl,
        "modul_an": modul_an,
        "fach": bool(fach) and hat_systemrolle(benutzer, fach),
        "gl_gruppenfreigabe": (not eintrag.gruppe and not admin
                               and _leitung_mit_gruppenfreigabe(sess, typ, eintrag.objekt, benutzer)),
        "oeffentlich": eintrag.gemeinde_status == GEMEINDE_AKTIV,
        "an_gruppe": bool(eintrag.untergruppe) and eintrag.gruppe_status == GEMEINDE_AKTIV,
    }


def _objekt_und_kontext(typ: str, objekt: str, benutzer: str):
    """`(eintrag, stufen-kontext)` eines Objekts — gemerkt (PERF-K1).

    `pruefstufen` und `moderationsstufen` lesen dieselbe Zeile und rechnen
    denselben Kontext; im Kalender-Endpunkt wurde das je Termin wiederholt.
    """

    def frage():
        with lesesitzung() as sess:
            eintrag = _objekt(sess, typ, objekt)
            if eintrag is None:
                return None
            return eintrag, _stufen_kontext(sess, benutzer, typ, eintrag)

    return _gemerkt(("objekt_kontext", typ, objekt, benutzer), frage)


def _pruefstufen_roh(benutzer: str | None, typ: str, objekt: str | None) -> list[str]:
    """Moderationsstufen, die ``benutzer`` an ``objekt`` PRUEFEN darf.

    Reihenfolge ``untergruppe`` -> ``gruppe`` -> ``gemeinde`` (Manuel 11.11.):
      * ``untergruppe`` — Untergruppen-Objekt: ihre GL und HV/MV der Gruppe.
      * ``gruppe``      — HV/MV der Gruppe; bei Objekten der Hauptgruppe auch,
        wem HV/MV „moderieren“ freigegeben haben. Gemeinde-Objekt: die Leitung
        einer Gruppe mit Schreib-Freigabe (deren GL schlagen dort vor).
      * ``gemeinde``    — gibt es nur bei Gemeinde-Objekten und gemeindeweit
        freigegebenen Objekten: Admin, Fachverwaltung (Kalender-Moderation),
        Freigabe „moderieren“ (Plan Abschnitt 4).
    Der Admin prueft jede vorhandene Stufe. Nicht registriert: nur Admin.
    """
    if not objekt or not _ist_angemeldetes_mitglied(benutzer):
        return []
    assert benutzer is not None
    ausgang = _objekt_und_kontext(typ, objekt, benutzer)
    if ausgang is None:
        return [STUFE_GEMEINDE] if ist_admin(benutzer) else []
    eintrag, k = ausgang
    if not k["modul_an"] and not k["admin"]:
        return []
    stufen: list[str] = []
    if eintrag.gruppe:
        if eintrag.untergruppe and (k["admin"] or k["gl"] or k["hauptleitung"]):
            stufen.append(STUFE_UNTERGRUPPE)
        if k["admin"] or k["hauptleitung"] or (k["moderieren"] and not eintrag.untergruppe):
            stufen.append(STUFE_GRUPPE)
    elif k["admin"] or k["gl_gruppenfreigabe"]:
        stufen.append(STUFE_GRUPPE)
    if (not eintrag.gruppe or k["oeffentlich"]) and (k["admin"] or k["fach"] or k["moderieren"]):
        stufen.append(STUFE_GEMEINDE)
    return stufen


def _moderationsstufen_roh(benutzer: str | None, typ: str, objekt: str) -> list[str]:
    """Welche Stufen ein Beitrag von ``benutzer`` in ``objekt`` durchlaeuft.

    Grundsatz (P0-3, bestaetigt im Konzept 11.11.): Freigeben ist eine
    Moderationshandlung, kein Schreibrecht. Wer die EIGENE Stufe des Objekts
    nicht pruefen darf, schlaegt vor:
      * Objekt der Hauptgruppe: eigene Stufe ``gruppe`` (HV/MV, Moderierende).
      * Untergruppen-Objekt: eigene Stufe ``untergruppe`` (GL, HV/MV); ist es
        der ganzen Gruppe freigegeben, zusaetzlich ``gruppe`` (Manuel: was an
        die Gruppe geht, moderiert zuerst die Gruppenleitung).
      * Gemeinde-Objekt: eigene Stufe ``gemeinde``; eine GL ueber die
        Gruppen-Freigabe vorher ``gruppe``.
    Gemeindeweit freigegebene Objekte: ``gemeinde`` IMMER — auch fuer den
    Admin (zweite Freigabeschicht gegen versehentlich veroeffentlichte Serien).
    ``[]`` heisst: wirkt sofort. Wer weder schreiben, vorschlagen noch pruefen
    darf, bekommt ``[]`` (``darf`` verweigert ohnehin vorher).
    """
    pruef = pruefstufen(benutzer, typ, objekt)
    if not (pruef or darf(benutzer, SCHREIBEN, typ, objekt) or darf(benutzer, VORSCHLAGEN, typ, objekt)):
        return []
    ausgang = _objekt_und_kontext(typ, objekt, benutzer or "")
    if ausgang is None:
        return []
    eintrag, k = ausgang
    stufen: list[str] = []
    if eintrag.gruppe:
        eigene = STUFE_UNTERGRUPPE if eintrag.untergruppe else STUFE_GRUPPE
        if eigene not in pruef:
            stufen.append(eigene)
        if k["an_gruppe"] and STUFE_GRUPPE not in pruef:
            stufen.append(STUFE_GRUPPE)
        if k["oeffentlich"]:
            stufen.append(STUFE_GEMEINDE)
    else:
        if not k["schreiben"] and not pruef and k["vorschlagen"]:
            stufen.append(STUFE_GRUPPE)
        if STUFE_GEMEINDE not in pruef or k["oeffentlich"]:
            stufen.append(STUFE_GEMEINDE)
    return stufen


def _leitung_mit_gruppenfreigabe(sess, typ: str, objekt: str, benutzer: str) -> bool:
    """HV/MV einer Gruppe, die am (Gemeinde-)Objekt eine Schreib-Freigabe hat.

    Deren GL schlagen dort nur vor (Stufe ``gruppe``) — pruefen muss diese
    Stufe die Leitung einer solchen Gruppe.
    """
    gruppen = sess.execute(select(RechteFreigabe.gruppe).where(
        RechteFreigabe.typ == typ, RechteFreigabe.objekt == objekt,
        RechteFreigabe.gruppe.is_not(None), RechteFreigabe.schreiben.is_(True),
    )).scalars().all()
    return any(gruppenrolle(benutzer, g) in _LEITUNG for g in gruppen if g)


def erforderliche_stufen(typ: str, objekt: str | None) -> list[str]:
    """Die LETZTE Stufe eines Objekts — fuer Vorschlaege ohne gespeicherte
    Stufen (Bestand, Entwuerfe): gemeindeweit/Gemeinde-Objekt ``gemeinde``,
    Untergruppen-Objekt ``untergruppe`` (an die Gruppe freigegeben:
    ``gruppe``), sonst ``gruppe``."""
    with lesesitzung() as sess:
        eintrag = _objekt(sess, typ, objekt) if objekt else None
    if eintrag is None or not eintrag.gruppe or eintrag.gemeinde_status == GEMEINDE_AKTIV:
        return [STUFE_GEMEINDE]
    if eintrag.untergruppe and eintrag.gruppe_status != GEMEINDE_AKTIV:
        return [STUFE_UNTERGRUPPE]
    return [STUFE_GRUPPE]


def darf_stufe(benutzer: str | None, typ: str, objekt: str | None, stufe: str) -> Entscheidung:
    """Darf ``benutzer`` die Moderationsstufe ``stufe`` an ``objekt`` freigeben?"""
    if stufe not in STUFEN:
        return NEIN("stufe_unbekannt")
    if stufe in pruefstufen(benutzer, typ, objekt):
        return JA(f"pruefstufe_{stufe}")
    return NEIN(f"keine_pruefstufe_{stufe}")


def freigabe_stufen(benutzer: str | None, typ: str, objekt: str, ziel: str) -> list[str]:
    """Moderationsstufen fuer das FREIGEBEN eines Objekts an ``ziel``.

    ``ziel='gruppe'``   — Untergruppen-Objekt an die ganze Hauptgruppe:
                          GL -> Stufe ``gruppe``; HV/MV/Admin -> sofort.
    ``ziel='gemeinde'`` — an alle Mitglieder der Gemeinde: Stufe ``gemeinde``
                          (entfaellt, wenn der Freigebende Admin ist); kommt
                          es von einer GL, vorher Stufe ``gruppe``.
    Ohne ``verwalten``-Recht am Objekt: leere Liste (``darf`` verweigert ohnehin).
    """
    if not darf(benutzer, VERWALTEN, typ, objekt):
        return []
    with lesesitzung() as sess:
        eintrag = _objekt(sess, typ, objekt)
    if eintrag is None:
        return []
    admin = ist_admin(benutzer)
    gl = bool(eintrag.untergruppe) and not admin and gruppenrolle(benutzer, eintrag.gruppe) not in _LEITUNG
    stufen: list[str] = []
    if gl:
        stufen.append(STUFE_GRUPPE)
    if ziel == STUFE_GEMEINDE and not admin:
        stufen.append(STUFE_GEMEINDE)
    return stufen


class KeinRecht(Exception):
    """Wird von :func:`pruefe` geworfen; die Schnittstelle macht daraus 403."""

    def __init__(self, entscheidung: Entscheidung):
        super().__init__(entscheidung.grund)
        self.entscheidung = entscheidung


def pruefe(benutzer: str | None, aktion: str, typ: str, objekt: str | None = None, **kw) -> Entscheidung:
    """Wie :func:`darf`, wirft aber bei Nein (fuer Endpunkte)."""
    e = darf(benutzer, aktion, typ, objekt, **kw)
    if not e:
        from diakronos_app.frappe_compat.exceptions import PermissionError, throw

        throw("Dafür fehlt dir die Berechtigung.", PermissionError)
    return e


def sichtbare_module(benutzer: str | None) -> set[str]:
    """Module, die im Menue erscheinen (Admin: alle).

    Ein Modul ist sichtbar, wenn der Benutzer darin ueberhaupt etwas lesen
    kann:
      * eine seiner Gruppen (Mitglied/GL/HV/MV) hat das Modul, oder
      * ihm bzw. einer seiner Gruppen ist ein Objekt des Moduls freigegeben, oder
      * es gibt ein Objekt des Moduls, das allen Mitgliedern der Gemeinde
        freigegeben ist (und er ist einem Mitglied zugeordnet).
    """
    if not _ist_angemeldetes_mitglied(benutzer):
        return set()
    assert benutzer is not None
    if ist_admin(benutzer):
        return set(MODULE)
    with lesesitzung() as sess:
        zeilen = sess.execute(select(RechteModul.gruppe, RechteModul.modul)).all()
        gemeinde_typen = set(sess.execute(
            select(RechteObjekt.typ).where(RechteObjekt.gemeinde_status == GEMEINDE_AKTIV).distinct()
        ).scalars())
        freigaben = sess.execute(select(RechteFreigabe.typ, RechteFreigabe.benutzer, RechteFreigabe.gruppe)).all()
        ist_mitglied = _mitglied_von(sess, benutzer) is not None
    ergebnis: set[str] = set()
    for gruppe, modul in zeilen:
        if modul not in ergebnis and gruppenrolle(benutzer, gruppe):
            ergebnis.add(modul)
    if ist_mitglied:
        ergebnis |= {TYP_MODUL[t] for t in gemeinde_typen if t in TYP_MODUL}
    for typ, fbenutzer, fgruppe in freigaben:
        modul = TYP_MODUL.get(typ)
        if not modul or modul in ergebnis:
            continue
        if fbenutzer == benutzer or (fgruppe and gruppenrolle(benutzer, fgruppe)):
            ergebnis.add(modul)
    return ergebnis


# ── Personen: Beziehungen (Manuel 17.11.2026) ──────────────────────────────
#
# Beziehungen pflegt die Mitgliederverwaltung. Ein Mitglied darf SELBST nur
# an seinem eigenen Profil Beziehungen eintragen, und nur zu Personen im
# selben Haushalt. Haushalt = gleiche Anschrift (Strasse, Hausnummer, PLZ,
# Ort — normalisiert, alle vier muessen gefuellt sein). Entfernen darf das
# Mitglied jede Beziehung des eigenen Profils (auch nach einem Umzug).


def _adressteil(wert) -> str:
    """Anschriftsteil vergleichbar machen (Gross/klein, ß, Str./Strasse, Leerraum)."""
    import re

    t = str(wert or "").casefold().replace("ß", "ss")
    t = re.sub(r"strasse\b|str\.", "str", t)
    return re.sub(r"[\s.\-]+", "", t)


def _haushalt(sess, mitglied: str) -> tuple[str, str, str, str] | None:
    """Normalisierte Anschrift einer Person; ``None``, wenn ein Teil fehlt."""
    from diakronos_app.models.diakonos import Mitglied

    zeile = sess.execute(
        select(Mitglied.straße, Mitglied.nummer, Mitglied.postleitzahl, Mitglied.wohnort)
        .where(Mitglied.name == mitglied)
    ).one_or_none()
    if zeile is None:
        return None
    teile = tuple(_adressteil(w) for w in zeile)
    return teile if all(teile) else None  # type: ignore[return-value]


def gleicher_haushalt(a: str | None, b: str | None) -> bool:
    """Wohnen ``a`` und ``b`` unter derselben (vollstaendigen) Anschrift?"""
    if not a or not b or a == b:
        return False
    with lesesitzung() as sess:
        ha = _haushalt(sess, a)
        return ha is not None and ha == _haushalt(sess, b)


def eigenes_mitglied(benutzer: str | None) -> str | None:
    """Mitglied-Kennung des Logins (dieselbe Aufloesung wie die Gruppenrechte)."""
    if not _ist_angemeldetes_mitglied(benutzer):
        return None
    assert benutzer is not None
    with lesesitzung() as sess:
        return _mitglied_von(sess, benutzer)


def darf_beziehung(benutzer: str | None, aktion: str, mitglied: str | None,
                   ziel: str | None = None) -> Entscheidung:
    """Darf ``benutzer`` Beziehungen am Profil ``mitglied`` lesen/eintragen/entfernen?

    ``aktion``: ``lesen`` (Auswahlliste), ``anlegen`` (``ziel`` = andere
    Person) oder ``schreiben`` (entfernen). Verwaltung (Fach
    ``mitgliederverwaltung``, Admin) darf alles; sonst nur das eigene Profil,
    Eintragen nur zu Personen im selben Haushalt.
    """
    if aktion not in (LESEN, ANLEGEN, SCHREIBEN):
        return NEIN("aktion_unbekannt")
    if not _ist_angemeldetes_mitglied(benutzer):
        return NEIN("nicht_angemeldet")
    if hat_systemrolle(benutzer, "mitgliederverwaltung"):
        return JA("verwaltung")
    if not mitglied or eigenes_mitglied(benutzer) != mitglied:
        return NEIN("fremdes_profil")
    if aktion == ANLEGEN:
        if ziel and gleicher_haushalt(mitglied, ziel):
            return JA("haushalt")
        return NEIN("anderer_haushalt")
    return JA("eigenes_profil")


def darf(  # noqa: F811 — Merker VOR der Rechnung (PERF-K1)
    benutzer: str | None,
    aktion: str,
    typ: str,
    objekt: str | None = None,
    *,
    gruppe: str | None = None,
    untergruppe: str | None = None,
    besitzer: str | None = None,
    zugewiesen: Iterable[str] = (),
    stufe: str = STUFE_GEMEINDE,
) -> Entscheidung:
    """Die EINE Rechtefrage — je Aufruf aber nur EINMAL gerechnet (PERF-K1).

    Die Entscheidung selbst trifft unveraendert `_darf_roh`; gemerkt wird nur
    das Ergebnis fuer dieselben Eingaben innerhalb EINES Aufrufs (`_gemerkt`).
    Ohne Merkungsrahmen (`merkungsrahmen`) wird wie zuvor jedes Mal gerechnet.
    """
    return _gemerkt(
        ("darf", benutzer, aktion, typ, objekt, gruppe, untergruppe, besitzer,
         tuple(zugewiesen or ()), stufe),
        lambda: _darf_roh(benutzer, aktion, typ, objekt, gruppe=gruppe,
                          untergruppe=untergruppe, besitzer=besitzer,
                          zugewiesen=zugewiesen or (), stufe=stufe))


def pruefstufen(  # noqa: F811 — Merker (PERF-K1)
    benutzer: str | None, typ: str, objekt: str | None,
) -> list[str]:
    """Moderationsstufen, die `benutzer` pruefen darf — gemerkt (PERF-K1)."""
    return _gemerkt(("pruefstufen", benutzer, typ, objekt),
                    lambda: _pruefstufen_roh(benutzer, typ, objekt))


def moderationsstufen(  # noqa: F811 — Merker (PERF-K1)
    benutzer: str | None, typ: str, objekt: str,
) -> list[str]:
    """Stufen, die ein Beitrag durchlaeuft — gemerkt (PERF-K1)."""
    return _gemerkt(("moderationsstufen", benutzer, typ, objekt),
                    lambda: _moderationsstufen_roh(benutzer, typ, objekt))


# ── Chat (Manuel 17.11.2026, Konzept CHAT-KONZEPT.md Abschnitt 2/9/10) ──────
#
# Gruppen-/Untergruppenchat: lesen, schreiben und Umfragen starten (ANLEGEN)
# darf jedes Mitglied der Einheit; die Untergruppe ist ein eigener Raum (nur
# ihre Mitglieder, ihre GL und HV/MV der Hauptgruppe). Fremde Nachrichten
# entfernen / Meldungen bearbeiten (MODERIEREN) und Einstellungen (VERWALTEN):
# HV/MV, in der Untergruppe auch GL. Eigene Nachricht/Umfrage: SCHREIBEN mit
# ``besitzer`` = Benutzer. Modul ``chat`` muss in der Gruppe an sein.
# Direktnachrichten: ``darf_person_finden`` / ``darf_direktnachricht``;
# Meldestelle fuer Direktnachrichten ist nur der Administrator (F7).


def _darf_chat(benutzer: str, aktion: str, *, gruppe: str | None,
               untergruppe: str | None, besitzer: str | None) -> Entscheidung:
    with lesesitzung() as sess:
        zgruppe = gruppe or _hauptgruppe(sess, untergruppe)
    if not zgruppe:
        return NEIN("keine_gruppe")
    if not modul_aktiv(zgruppe, "chat"):
        return NEIN("modul_aus")
    if untergruppe:
        rolle = untergruppenrolle(benutzer, untergruppe)
        leitung = rolle in (ROLLE_HV, ROLLE_MV, ROLLE_GL)
    else:
        rolle = gruppenrolle(benutzer, zgruppe)
        leitung = rolle in _LEITUNG
    if not rolle:
        return NEIN("kein_mitglied")
    if aktion in (LESEN, VORSCHLAGEN, ANLEGEN):
        return JA(f"chat_{rolle.lower()}")
    if aktion == SCHREIBEN:
        if besitzer is None or besitzer == benutzer:
            return JA("chat_eigenes")
        return JA(f"chat_leitung_{rolle.lower()}") if leitung else NEIN("fremde_nachricht")
    if aktion in (MODERIEREN, VERWALTEN):
        return JA(f"chat_leitung_{rolle.lower()}") if leitung else NEIN("nicht_verantwortlich")
    return NEIN("aktion_nicht_fuer_chat")


def chat_moderatoren(gruppe: str | None, untergruppe: str | None = None) -> list[str]:
    """Konten, die im Chat dieser Einheit MODERIEREN duerfen (CHAT-6, Glocke).

    Kandidaten sind die Leitungs-Eintraege der Einheit (HV/MV der Hauptgruppe,
    bei einer Untergruppe zusaetzlich deren GL); entschieden wird fuer JEDEN
    Kandidaten ueber `darf` — dieselbe Frage wie bei Liste und Entscheidung,
    keine zweite Regel. Administratoren stehen NICHT darin: sie sehen die
    Meldungen ueber die Liste, bekommen aber nicht jede Gruppenmeldung als
    Glocke. Sortiert, ohne Doppelte.
    """
    with lesesitzung() as sess:
        zgruppe = gruppe or _hauptgruppe(sess, untergruppe)
        if not zgruppe:
            return []
        oben = (RechteGruppenrolle.untergruppe.is_(None)) & (RechteGruppenrolle.rolle.in_(_LEITUNG))
        bedingung = oben
        if untergruppe:
            bedingung = oben | ((RechteGruppenrolle.untergruppe == untergruppe)
                                & (RechteGruppenrolle.rolle == ROLLE_GL))
        kandidaten = sess.execute(
            select(RechteGruppenrolle.benutzer).where(RechteGruppenrolle.gruppe == zgruppe, bedingung)
        ).scalars().all()
    return sorted({
        str(k) for k in kandidaten
        if k and darf(str(k), MODERIEREN, "chat_gespraech", gruppe=zgruppe, untergruppe=untergruppe)
    })


def darf_chat_irgendwo_moderieren(benutzer: str | None) -> bool:
    """Darf ``benutzer`` IRGENDWO Chat-Meldungen bearbeiten? (Kopf/Reiter „Chat“)

    Nur fuer die Anzeige des Einstiegs — jede Liste und jede Entscheidung fragt
    weiter je Gespraech ``darf(..., MODERIEREN, "chat_gespraech", ...)``. Keine
    zweite Regel: die Meldestelle (1:1/Runden) ist ``ist_meldestelle``; fuer
    Gruppengespraeche werden nur die EIGENEN Leitungs-Eintrage (HV/MV, GL der
    Untergruppe) als Kandidaten gelesen und jeder ueber ``darf`` entschieden
    (Modul an, Gruppe lebt, Mitglied aktiv) — fruehes Ende beim ersten „ja“.
    """
    if not benutzer or benutzer == GAST:
        return False
    if ist_meldestelle(benutzer):
        return True
    with lesesitzung() as sess:
        zeilen = sess.execute(
            select(RechteGruppenrolle.gruppe, RechteGruppenrolle.untergruppe, RechteGruppenrolle.rolle)
            .where(RechteGruppenrolle.benutzer == benutzer)
        ).all()
    for gruppe, untergruppe, rolle in zeilen:
        if untergruppe:
            if rolle != ROLLE_GL:
                continue
        elif rolle not in _LEITUNG:
            continue
        if darf(benutzer, MODERIEREN, "chat_gespraech", gruppe=gruppe, untergruppe=untergruppe or None):
            return True
    return False


#: Status, mit denen eine Person nicht mehr auffindbar ist (wie die
#: Personenauswahl `api.gruppen_auswahl.AUSGESCHIEDEN`).
_NICHT_AUFFINDBAR = frozenset({"ausgetreten", "verstorben", "verstorben/ausgetreten", "geloescht"})


def _auffindbar(sess, mitglied: str) -> tuple[bool, bool]:
    """(auffindbar, hat_konto) der Person ``mitglied`` — fail closed."""
    from diakronos_app.models.core import User
    from diakronos_app.models.diakonos import Mitglied

    zeile = sess.execute(
        select(Mitglied.status, Mitglied.ausgeschlossen, Mitglied.austritt_datum, Mitglied.user)
        .where(Mitglied.name == mitglied)
    ).one_or_none()
    if zeile is None:
        return False, False
    status, ausgeschlossen, austritt, konto = zeile
    if str(mitglied).startswith("geloescht-"):
        return False, False
    if str(status or "").strip().casefold() in _NICHT_AUFFINDBAR or austritt or ausgeschlossen:
        return False, False
    hat_konto = False
    if konto:
        hat_konto = bool(sess.execute(
            select(User.enabled).where(User.name == konto)).scalar_one_or_none())
    return True, hat_konto


def darf_person_finden(benutzer: str | None, ziel: str | None) -> Entscheidung:
    """Darf ``benutzer`` die Person ``ziel`` unter „Nachrichten“ finden?

    Entscheidung Manuel 17.11.2026: alle aktiven Gemeindemitglieder sind fuer
    jedes Gemeindemitglied auffindbar (Name + Bild; Kontaktdaten weiter nach
    der Sichtbarkeitseinstellung der Person). Nie Gaeste, nie Ausgetretene,
    Ausgeschlossene, Verstorbene oder Geloeschte. Personen ohne Konto sind
    auffindbar (die Oberflaeche graut sie aus) — siehe ``darf_direktnachricht``.
    """
    if not ziel or not ist_gemeindemitglied(benutzer):
        return NEIN("nicht_angemeldet")
    with lesesitzung() as sess:
        auffindbar, _konto = _auffindbar(sess, ziel)
    return JA("gemeinde") if auffindbar else NEIN("nicht_auffindbar")


def person_hat_konto(ziel: str | None) -> bool:
    """Hat die Person ``ziel`` ein AKTIVES Konto? (fuer „hat kein Konto“).

    Dieselbe Quelle wie ``darf_direktnachricht`` (``_auffindbar``): ein
    deaktiviertes Konto zaehlt als kein Konto — sonst zeigte die Oberflaeche
    einen Schreib-Knopf, den der Server ablehnt. Fail closed.
    """
    if not ziel:
        return False
    with lesesitzung() as sess:
        return _auffindbar(sess, str(ziel))[1]


def darf_direktnachricht(benutzer: str | None, ziel: str | None) -> Entscheidung:
    """Darf ``benutzer`` der Person ``ziel`` eine Direktnachricht schreiben?

    Nur an auffindbare Personen MIT aktivem Konto, nicht an sich selbst.
    Auch die schreibende Person selbst muss ein auffindbares Mitglied sein:
    wer ausgetreten ist (Konto noch aktiv) oder als Konto kein Mitglied hat
    (z. B. ``Administrator``), beginnt keine Direktgespraeche — sonst
    entstuenden Gespraeche, auf die das Gegenueber nie antworten kann.
    """
    gefunden = darf_person_finden(benutzer, ziel)
    if not gefunden:
        return gefunden
    with lesesitzung() as sess:
        eigen = _mitglied_von(sess, str(benutzer))
        if not eigen or not _auffindbar(sess, eigen)[0]:
            return NEIN("selbst_nicht_aktiv")
        if eigen == ziel:
            return NEIN("selbst")
        if _kontakt_gesperrt(sess, str(benutzer), _konto_von(sess, str(ziel))):
            # Gleiche Auskunft wie „nicht erreichbar“ nach aussen; der Grund
            # bleibt intern (die andere Seite erfaehrt nichts von der Sperre).
            return NEIN("gesperrt")
        _auffindbar_ja, konto = _auffindbar(sess, str(ziel))
    return JA("gemeinde") if konto else NEIN("kein_konto")


def _konto_von(sess, mitglied: str | None) -> str | None:
    """Login-Konto eines Mitglieds (``Mitglied.user``) — nur zum Nachschlagen."""
    from diakronos_app.models.diakonos import Mitglied

    if not mitglied:
        return None
    return sess.execute(
        select(Mitglied.user).where(Mitglied.name == mitglied)).scalar_one_or_none()


def _kontakt_gesperrt(sess, a: str | None, b: str | None) -> bool:
    """Hat ``a`` ``b`` gesperrt ODER ``b`` ``a``? (CHAT-7b, beide Richtungen)."""
    if not a or not b or a == b:
        return False
    zeile = sess.execute(
        select(RechteKontaktsperre.id).where(
            ((RechteKontaktsperre.benutzer == a) & (RechteKontaktsperre.gesperrt == b))
            | ((RechteKontaktsperre.benutzer == b) & (RechteKontaktsperre.gesperrt == a))
        ).limit(1)
    ).first()
    return zeile is not None


def _sperre_unter(konten, *, nur_mit: str | None = None) -> bool:
    """Gibt es unter ``konten`` ein Paar mit Kontaktsperre (eine Richtung reicht)?

    ``nur_mit``: nur Paare, an denen dieses Konto beteiligt ist (Vorschlag).
    Eine Abfrage, keine Schleife ueber Paare.
    """
    menge = {str(k) for k in konten if k}
    if len(menge) < 2:
        return False
    with lesesitzung() as sess:
        q = select(RechteKontaktsperre.benutzer, RechteKontaktsperre.gesperrt).where(
            RechteKontaktsperre.benutzer.in_(menge), RechteKontaktsperre.gesperrt.in_(menge))
        for a, b in sess.execute(q):
            if a != b and (nur_mit is None or nur_mit in (a, b)):
                return True
    return False


def darf_kontakt_sperren(benutzer: str | None, ziel: str | None) -> Entscheidung:
    """Darf ``benutzer`` die Person ``ziel`` (Mitglied) sperren bzw. entsperren?

    Jedes angemeldete Gemeindemitglied darf JEDE Person sperren, die es finden
    darf, oder mit der es schon ein Direktgespraech hat — nur nicht sich selbst.
    Gesperrt wird das Konto der Person; ohne Konto gibt es nichts zu sperren.
    """
    if not ziel or not ist_gemeindemitglied(benutzer):
        return NEIN("nicht_angemeldet")
    with lesesitzung() as sess:
        eigen = _mitglied_von(sess, str(benutzer))
        if eigen and eigen == ziel:
            return NEIN("selbst")
        konto = _konto_von(sess, str(ziel))
    if not konto:
        return NEIN("kein_konto")
    if konto == benutzer:
        return NEIN("selbst")
    return JA("eigene_sperre")


def darf_runde_anlegen(benutzer: str | None, ziele) -> Entscheidung:
    """Runde (CHAT-7b, Konzept S3): 3–8 Beteiligte INKLUSIVE ``benutzer``.

    ``ziele`` = Mitglieds-Kennungen der ANDEREN (2–7, ohne Doppel, ohne sich
    selbst). Anlegen darf, wer ALLE Beteiligten per ``darf_direktnachricht``
    erreichen darf (also auch: niemand hat ihn gesperrt, er niemanden).
    """
    liste = [str(z) for z in (ziele or ()) if z]
    if len(set(liste)) != len(liste):
        return NEIN("doppelt")
    if not 2 <= len(liste) <= 7:
        return NEIN("groesse")
    for ziel in liste:
        e = darf_direktnachricht(benutzer, ziel)
        if not e:
            return NEIN("nicht_erreichbar" if e.grund not in ("nicht_angemeldet", "selbst_nicht_aktiv", "selbst")
                        else e.grund)
    # Niemand wird mit einer Person in eine Runde gezogen, die er gesperrt
    # hat (oder die ihn gesperrt hat) — auch nicht durch Dritte (Entscheidung
    # Operator 19.11., Review CHAT-7b). Nach aussen „nicht erreichbar“.
    with lesesitzung() as sess:
        konten = [_konto_von(sess, z) for z in liste]
    if _sperre_unter(konten):
        return NEIN("nicht_erreichbar")
    return JA("alle_erreichbar")


def darf_runde_erweitern(benutzer: str | None, *, teilnehmer, ziel: str | None) -> Entscheidung:
    """Darf ``benutzer`` VORSCHLAGEN, ``ziel`` (Mitglied) in die Runde zu holen?

    Nur Teilnehmende, nur bis 8 Beteiligte, nur wen sie selbst erreichen
    dürfen, und wer die Runde nicht schon teilt. Hinzugefuegt wird erst mit
    Zustimmung der Runde (Konzept S3) — das regelt das Modul, nicht der Kern.
    """
    lesen = darf_direktgespraech(benutzer, LESEN, teilnehmer=teilnehmer)
    if not lesen:
        return lesen
    konten = {str(k) for k in (teilnehmer or ()) if k}
    if len(konten) >= 8:
        return NEIN("groesse")
    with lesesitzung() as sess:
        konto = _konto_von(sess, str(ziel)) if ziel else None
    if konto and konto in konten:
        return NEIN("schon_dabei")
    e = darf_direktnachricht(benutzer, ziel)
    if not e:
        return NEIN("nicht_erreichbar")
    if konto and _sperre_unter(sorted(konten) + [konto], nur_mit=konto):
        return NEIN("nicht_erreichbar")
    return JA("vorschlag")


def ist_meldestelle(benutzer: str | None) -> bool:
    """Meldestelle fuer Direktnachrichten/Runden: nur der Administrator (F7)."""
    return ist_admin(benutzer)


def darf_direktgespraech(benutzer: str | None, aktion: str, *, teilnehmer,
                         besitzer: str | None = None,
                         meldeweg: bool = False) -> Entscheidung:
    """Direktgespraech oder Runde (CHAT-7): wer darf was?

    Ein Direktgespraech hat keine Gruppe; der Raum sind die Teilnehmenden
    (``teilnehmer`` = Konten). Regeln:

    * LESEN: nur Teilnehmende mit gueltigem Konto (Admin ist KEIN stiller
      Mitleser — auch nicht als Meldestelle, die bekommt nur die gemeldete
      Nachricht samt Kontext ueber die Meldung).
    * ANLEGEN (Nachricht/Gespraech starten): Teilnehmende, und mindestens
      EINE andere teilnehmende Person ist fuer sie per
      ``darf_direktnachricht`` erreichbar. Ist niemand mehr erreichbar
      (ausgetreten, Konto gesperrt), bleibt der Verlauf lesbar, aber
      stumm. Dasselbe gilt, wenn die Person selbst ausgetreten ist.
    * SCHREIBEN: nur die eigene Nachricht (``besitzer``).
    * MODERIEREN: nur die Meldestelle (F7: Administrator) und NUR auf dem
      Meldeweg (``meldeweg=True``: Meldungen ansehen/entscheiden, Glocke an
      die Meldestelle). Ohne ``meldeweg`` ist MODERIEREN hier immer NEIN —
      fail closed, damit kein Modulpfad (Loeschen, Umfrage schliessen …)
      dem Admin in einem 1:1 oder einer Runde still Moderation gibt
      (Review CHAT-7b, MUSS 1). Eine fremde Nachricht loeschen ist SCHREIBEN
      mit ``besitzer`` und damit NEIN, auch fuer einen teilnehmenden Admin.
    * alles andere: NEIN. Fail closed.
    """
    if not _ist_angemeldetes_mitglied(benutzer):
        return NEIN("nicht_angemeldet")
    assert benutzer is not None
    if aktion == MODERIEREN:
        if not meldeweg:
            return NEIN("nur_meldeweg")
        return JA("meldestelle") if ist_meldestelle(benutzer) else NEIN("nicht_meldestelle")
    konten = {str(k) for k in (teilnehmer or ()) if k}
    if benutzer not in konten:
        return NEIN("kein_teilnehmer")
    if not ist_gemeindemitglied(benutzer):
        return NEIN("kein_mitglied")
    if aktion == LESEN:
        return JA("teilnehmer")
    if aktion in (ANLEGEN, VORSCHLAGEN):
        with lesesitzung() as sess:
            ziele = [_mitglied_von(sess, k) for k in sorted(konten - {benutzer})]
        if any(z and darf_direktnachricht(benutzer, z) for z in ziele):
            return JA("teilnehmer")
        return NEIN("niemand_erreichbar")
    if aktion == SCHREIBEN:
        if besitzer is None or besitzer == benutzer:
            return JA("eigenes")
        return NEIN("fremde_nachricht")
    return NEIN("aktion_nicht_fuer_direkt")


__all__ = [
    "darf_kontakt_sperren",
    "darf_runde_anlegen",
    "darf_runde_erweitern",
    "AKTIONEN",
    "ANLEGEN",
    "ERLEDIGEN",
    "Entscheidung",
    "KeinRecht",
    "LESEN",
    "MODERIEREN",
    "MODULE",
    "STANDARD_MODULE",
    "ROLLEN",
    "SCHREIBEN",
    "STUFEN",
    "STUFE_GEMEINDE",
    "STUFE_GRUPPE",
    "STUFE_UNTERGRUPPE",
    "SYSTEMROLLEN",
    "TYP_MODUL",
    "VERWALTEN",
    "VORSCHLAGEN",
    "darf",
    "ADMIN_ROLLEN",
    "darf_stufe",
    "erforderliche_stufen",
    "freigabe_stufen",
    "gruppenrolle",
    "hat_systemrolle",
    "ist_admin",
    "ist_gemeindemitglied",
    "eigene_gruppen",
    "ist_gl_in_gruppe",
    "person_in_einheit",
    "merkungsrahmen",
    "merker_leeren",
    "moderationsstufen",
    "modul_aktiv",
    "pruefe",
    "pruefstufen",
    "sichtbare_module",
    "darf_beziehung",
    "CHAT_TYPEN",
    "chat_moderatoren",
    "darf_person_finden",
    "person_hat_konto",
    "darf_direktgespraech",
    "darf_direktnachricht",
    "darf_chat_irgendwo_moderieren",
    "ist_meldestelle",
    "eigenes_mitglied",
    "gleicher_haushalt",
    "untergruppenrolle",
    "rollen_vorladen",
]
