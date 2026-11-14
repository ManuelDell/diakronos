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
    RechteModul,
    RechteObjekt,
)

# ── Begriffe ────────────────────────────────────────────────────────────────

#: Module, die eine Gruppe haben kann.
MODULE: tuple[str, ...] = ("kalender", "beitraege", "wiki", "aufgaben", "lieder", "dienstplaene")

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
}

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
    """Rollen ueber die bestehende, fail-closed Quelle (Ausschluss, root, Guest)."""
    from diakronos_app.frappe_compat.permissions import get_roles

    return tuple(get_roles(benutzer))


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
    """
    if not benutzer or benutzer == GAST:
        return False
    if benutzer == "Administrator":
        return True
    from diakronos_app.frappe_compat.permissions import mitglied_ausgeschlossen
    from diakronos_app.models.core import User

    with lesesitzung() as sess:
        aktiv = sess.execute(select(User.enabled).where(User.name == benutzer)).scalar_one_or_none()
    if not aktiv:
        return False
    return not mitglied_ausgeschlossen(benutzer)


# ── Gruppen- und Untergruppenebene ──────────────────────────────────────────


def _mitglied_von(sess, benutzer: str) -> str | None:
    """Mitglied-Kennung eines Logins (``mitglied.user``, sonst E-Mail normalisiert)."""
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
    keine Rechte (UX2b2/F3: eine geloeschte Gruppe gibt kein Recht mehr)."""
    if not gruppe:
        return False
    from diakronos_app.models.diakonos import Gruppe

    zeile = sess.execute(select(Gruppe.name, Gruppe.geloescht_am).where(Gruppe.name == gruppe)).first()
    return zeile is not None and zeile[1] is None


def _rolle_eintrag(sess, benutzer: str, gruppe: str, untergruppe: str | None) -> str | None:
    bedingung = [RechteGruppenrolle.gruppe == gruppe, RechteGruppenrolle.benutzer == benutzer]
    if untergruppe:
        bedingung.append(RechteGruppenrolle.untergruppe == untergruppe)
    else:
        bedingung.append(RechteGruppenrolle.untergruppe.is_(None))
    return sess.execute(select(RechteGruppenrolle.rolle).where(*bedingung)).scalar_one_or_none()


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
    """Mitglied der Gruppe, einer ihrer Untergruppen oder Rolleninhaber in ihr."""
    if sess.execute(select(RechteGruppenrolle.id).where(
        RechteGruppenrolle.gruppe == gruppe, RechteGruppenrolle.benutzer == benutzer
    ).limit(1)).first():
        return True
    mid = _mitglied_von(sess, benutzer)
    return bool(mid) and _person_in_gruppe(sess, mid, gruppe)


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
    if not gruppe or modul not in MODULE:
        return False
    with lesesitzung() as sess:
        return _gruppe_lebt(sess, gruppe) and bool(
            sess.execute(
                select(RechteModul.id).where(RechteModul.gruppe == gruppe, RechteModul.modul == modul).limit(1)
            ).first()
        )


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


def darf(
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


def pruefstufen(benutzer: str | None, typ: str, objekt: str | None) -> list[str]:
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
    with lesesitzung() as sess:
        eintrag = _objekt(sess, typ, objekt)
        if eintrag is None:
            return [STUFE_GEMEINDE] if ist_admin(benutzer) else []
        k = _stufen_kontext(sess, benutzer, typ, eintrag)
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


def moderationsstufen(benutzer: str | None, typ: str, objekt: str) -> list[str]:
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
    with lesesitzung() as sess:
        eintrag = _objekt(sess, typ, objekt)
        if eintrag is None:
            return []
        k = _stufen_kontext(sess, benutzer or "", typ, eintrag)
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


__all__ = [
    "AKTIONEN",
    "ANLEGEN",
    "ERLEDIGEN",
    "Entscheidung",
    "KeinRecht",
    "LESEN",
    "MODERIEREN",
    "MODULE",
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
    "moderationsstufen",
    "modul_aktiv",
    "pruefe",
    "pruefstufen",
    "sichtbare_module",
    "untergruppenrolle",
]
