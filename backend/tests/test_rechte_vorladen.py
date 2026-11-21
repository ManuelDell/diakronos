"""PERF-K1 für Listen: ``rechte.rollen_vorladen`` legt nur DIESELBEN Antworten ab.

Die Funktion liest Rollen, Mitgliedschaften und Module vieler Einheiten in
wenigen Sammelabfragen und legt sie im Merker unter den Schlüsseln der
Einzelfragen ab. Sie darf keine Entscheidung ändern: dieser Test vergleicht
für jede Person und jede Einheit die Antwort MIT Vorladen gegen die Antwort
OHNE Merker (jede Frage frisch gerechnet).
"""
from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy import event

from diakronos_app.models.core import HasRole, User
from diakronos_app.models.diakonos import (
    Gruppe,
    Gruppenmitgliedschaft,
    Mitglied,
    Untergruppe,
    Untergruppenmitgliedschaft,
)
from diakronos_app.models.rechte import RechteGruppenrolle, RechteModul
from diakronos_app import rechte as R
from diakronos_app.rechte import kern as K

PERSONEN = {
    "admin@x.org": "Ad",
    "hv@x.org": "Hv",          # HV Chor
    "mv@x.org": "Mv",          # MV Chor
    "gl@x.org": "Gl",          # GL UG-Noten, sonst nichts
    "saenger@x.org": "Sa",     # Mitglied Chor
    "noten@x.org": "No",       # nur Mitglied UG-Noten
    "inaktiv@x.org": "In",     # Mitglied Chor, Status Inaktiv
    "alt@x.org": "Al",         # HV einer gelöschten Gruppe + Mitglied ihrer UG
    "leer@x.org": "Le",        # Rollenzeile mit untergruppe "" (Bestand)
    "jugend@x.org": "Ju",      # Mitglied Jugend (ohne Chat-Modul)
    "fremd@x.org": "Fr",       # nirgends
}
GRUPPEN = ["Chor", "Jugend", "Alt", "Gibtsnicht"]
UNTERGRUPPEN = ["UG-Noten", "UG-Sopran", "UG-Alt", "UG-Gibtsnicht"]
MODULE = ["chat", "kalender"]


@pytest.fixture()
def welt(patched_db):
    s = patched_db()
    for user, kurz in PERSONEN.items():
        s.add(User(name=user, email=user, enabled=1))
        s.add(Mitglied(name=f"M-{kurz}", vorname=kurz, nachname="X", email=user, user=user))
    s.add(HasRole(name="hr-admin", parent="admin@x.org", parenttype="User", role="System Manager"))
    s.add(Gruppe(name="Chor", gruppenname="Chor"))
    s.add(Gruppe(name="Jugend", gruppenname="Jugend"))
    s.add(Gruppe(name="Alt", gruppenname="Alt", geloescht_am=dt.datetime(2026, 11, 1)))
    s.add(Untergruppe(name="UG-Noten", untergruppenname="Noten", gruppe="Chor"))
    s.add(Untergruppe(name="UG-Sopran", untergruppenname="Sopran", gruppe="Chor"))
    s.add(Untergruppe(name="UG-Alt", untergruppenname="Alt-UG", gruppe="Alt"))
    s.add_all([
        Gruppenmitgliedschaft(name="gm-sa", parent="Chor", parentfield="mitglieder", mitglied="M-Sa"),
        Gruppenmitgliedschaft(name="gm-in", parent="Chor", parentfield="mitglieder", mitglied="M-In",
                              status="Inaktiv"),
        Gruppenmitgliedschaft(name="gm-ju", parent="Jugend", parentfield="mitglieder", mitglied="M-Ju"),
        Untergruppenmitgliedschaft(name="ugm-no", parent="UG-Noten", parentfield="mitglieder",
                                   mitglied="M-No"),
        Untergruppenmitgliedschaft(name="ugm-al", parent="UG-Alt", parentfield="mitglieder",
                                   mitglied="M-Al"),
        RechteGruppenrolle(gruppe="Chor", benutzer="hv@x.org", rolle="HV"),
        RechteGruppenrolle(gruppe="Chor", benutzer="mv@x.org", rolle="MV"),
        RechteGruppenrolle(gruppe="Chor", untergruppe="UG-Noten", benutzer="gl@x.org", rolle="GL"),
        RechteGruppenrolle(gruppe="Alt", benutzer="alt@x.org", rolle="HV"),
        RechteGruppenrolle(gruppe="Chor", untergruppe="", benutzer="leer@x.org", rolle="GL"),
        RechteModul(gruppe="Chor", modul="chat"),
        RechteModul(gruppe="Alt", modul="chat"),
        RechteModul(gruppe="Jugend", modul="kalender"),
    ])
    s.commit()
    yield s
    s.close()


def _antworten(benutzer: str) -> dict:
    """Alle Fragen, deren Antworten ``rollen_vorladen`` ablegen kann."""
    a: dict = {}
    for g in GRUPPEN:
        a[("gruppenrolle", g)] = R.gruppenrolle(benutzer, g)
        for m in MODULE:
            a[("modul_aktiv", g, m)] = R.modul_aktiv(g, m)
        a[("darf_chat", g, None)] = bool(R.darf(benutzer, R.LESEN, "chat_gespraech", None,
                                                gruppe=g, untergruppe=None))
    for u in UNTERGRUPPEN:
        a[("untergruppenrolle", u)] = R.untergruppenrolle(benutzer, u)
        haupt = {"UG-Noten": "Chor", "UG-Sopran": "Chor", "UG-Alt": "Alt"}.get(u)
        a[("darf_chat", haupt, u)] = bool(R.darf(benutzer, R.LESEN, "chat_gespraech", None,
                                                 gruppe=haupt, untergruppe=u))
    return a


@pytest.mark.parametrize("benutzer", sorted(PERSONEN))
def test_vorladen_aendert_keine_antwort(welt, benutzer):
    ohne = _antworten(benutzer)  # kein Rahmen: jede Frage frisch
    with K.merkungsrahmen():
        R.rollen_vorladen(benutzer, gruppen=GRUPPEN, untergruppen=UNTERGRUPPEN, module=MODULE)
        mit = _antworten(benutzer)
    assert mit == ohne


def test_vorladen_belegt_die_schluessel_wirklich(welt):
    """Sonst wäre der Gleichheitstest leer: die Schlüssel müssen gefüllt sein."""
    with K.merkungsrahmen() as merker:
        R.rollen_vorladen("noten@x.org", gruppen=["Chor"], untergruppen=["UG-Noten"],
                          module=["chat"])
        assert merker[("gruppenrolle", "noten@x.org", "Chor")] == "Mitglied"
        assert merker[("untergruppenrolle", "noten@x.org", "UG-Noten")] == "Mitglied"
        assert merker[("modul_aktiv", "Chor", "chat")] is True


def test_vorladen_ueberschreibt_nichts_und_braucht_einen_rahmen(welt):
    R.rollen_vorladen("hv@x.org", gruppen=["Chor"], module=["chat"])  # ohne Rahmen: nichts
    with K.merkungsrahmen() as merker:
        merker[("gruppenrolle", "hv@x.org", "Chor")] = "VORHER"
        R.rollen_vorladen("hv@x.org", gruppen=["Chor"], module=["chat"])
        assert merker[("gruppenrolle", "hv@x.org", "Chor")] == "VORHER"


def test_vorladen_nach_schreiben_wieder_frisch(welt):
    """Ein Schreibvorgang leert den Merker — eine entzogene Rolle wirkt sofort."""
    with K.merkungsrahmen():
        R.rollen_vorladen("mv@x.org", gruppen=["Chor"], module=["chat"])
        assert R.gruppenrolle("mv@x.org", "Chor") == "MV"
        welt.query(RechteGruppenrolle).filter_by(benutzer="mv@x.org").delete()
        welt.commit()
        assert R.gruppenrolle("mv@x.org", "Chor") is None


def test_wenige_abfragen_fuer_viele_einheiten(welt, engine):
    """Vorladen + Entscheidung für 3 Gruppen/3 Untergruppen: feste kleine Zahl."""
    abfragen: list[str] = []

    def zaehle(_c, _cur, sql, *_a):
        abfragen.append(sql)

    event.listen(engine, "before_cursor_execute", zaehle)
    try:
        with K.merkungsrahmen():
            R.darf("noten@x.org", R.LESEN, "chat_gespraech", None, gruppe="Chor")  # Konto/Rollen
            vorher = len(abfragen)
            R.rollen_vorladen("noten@x.org", gruppen=GRUPPEN[:3], untergruppen=UNTERGRUPPEN[:3],
                              module=["chat"])
            for g in GRUPPEN[:3]:
                R.darf("noten@x.org", R.LESEN, "chat_gespraech", None, gruppe=g)
            for u, g in (("UG-Noten", "Chor"), ("UG-Sopran", "Chor"), ("UG-Alt", "Alt")):
                R.darf("noten@x.org", R.LESEN, "chat_gespraech", None, gruppe=g, untergruppe=u)
            danach = len(abfragen) - vorher
    finally:
        event.remove(engine, "before_cursor_execute", zaehle)
    assert danach <= 7, "\n".join(abfragen[vorher:])
