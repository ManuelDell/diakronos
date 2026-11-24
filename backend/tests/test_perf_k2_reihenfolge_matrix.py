"""PERF-K2b — Reihenfolge-Matrix: Einzelfrage, dann Liste, dann Rechte.

BEFUND (Review R2, MUSS 1): `vorladen.kalender_rechte_merken_aus_liste` legte
die FERTIGEN Eintraege von `get_accessible_calendars` als `darf`-Antworten ab
(`SCHREIBEN`/`VORSCHLAGEN` = `write or pruefstufen`). Das war eine ZWEITE
RECHTEREGEL, und der Merker vergiftete damit die Reihenfolge

    Einzelfrage (`ist_moderator`) -> Liste -> darf(SCHREIBEN/VORSCHLAGEN)

weil das Vorabladen Kalender mit vorhandenem `objekt_kontext` ueberspringt und
der Kurzschluss im Oder der Liste `darf(SCHREIBEN)` nie gefragt hat. Betroffen:
Kalenderadministrator auf einem oeffentlichen Kalender, ein Mitglied mit
Einzelfreigabe „moderieren“, Kalenderadministrator auf einem
untergruppen-oeffentlichen Kalender — und darueber `kern._darf_roh` (Lesen des
Dienstplans ueber den Eltern-Kalender) sowie `planrahmen/rechte.py` (fail open).

Dieser Test haelt BEIDE Reihenfolgen fest (Liste zuerst, Einzelfrage zuerst)
und vergleicht das Ergebnis mit der frischen Frage ohne Merker. Er ist die
Uebernahme des Pruefertests aus dem Review, ergaenzt um den Moderator ohne
Schreibrecht (SOLL 2) und die Welt von `test_perf_k2_vorladen.py`.
"""
from __future__ import annotations

from datetime import datetime

import pytest

import diakronos_app.api  # noqa: F401 — Dekoratoren/Registrierung
from diakronos_app import rechte as R
from diakronos_app.frappe_compat.session import set_user
from diakronos_app.models.core import HasRole, User
from diakronos_app.models.diakonos import (Gruppe, Gruppenmitgliedschaft, Mitglied,
                                           Untergruppe, Untergruppenmitgliedschaft)
from diakronos_app.models.kronos import Kalender
from diakronos_app.models.rechte import (RechteFreigabe, RechteGruppenrolle, RechteModul,
                                         RechteObjekt)

NUTZER = ["Administrator", "hv@x", "gl@x", "mit@x", "ugmit@x", "fremd@x", "ohne@x",
          "aus@x", "kadm@x", "pers@x", "gast@x", "mvdel@x"]
KAL = ["K-A", "K-UG", "K-UG2", "K-DEL", "K-OFF", "K-GEM", "K-GEM2", "K-PUB", "K-NOOBJ",
       "K-PERS", "K-UGPUB"]
ALLE = KAL + ["K-WAISE", "K-GIBTSNICHT"]


@pytest.fixture()
def welt(patched_db):
    """Die Welt von `test_perf_k2_vorladen.py`, erweitert um die Faelle aus R2.

    Kalenderadministrator (`kadm@x`, Systemrolle), Mitglied mit
    Einzelfreigabe „moderieren“ auf K-PUB (`mit@x`), oeffentlicher Kalender
    (K-PUB, K-UGPUB, K-GEM), verwaister Rechte-Eintrag ohne Kalender-Zeile
    (K-WAISE), geloeschte Gruppe, ausgeschlossenes Mitglied, persoenliche
    Freigaben.
    """
    s = patched_db()
    for n in NUTZER[1:]:
        if n == "gast@x":
            continue
        s.add(User(name=n, email=n, enabled=(0 if n == "aus@x" else 1), user_type="System User"))
    s.commit()
    for n in NUTZER[1:]:
        if n in ("gast@x", "ohne@x"):
            continue
        s.add(Mitglied(name=f"M-{n}", vorname="a", nachname="b", email=n, user=n,
                       status="Aktiv", ausgeschlossen=0))
    s.add(HasRole(name="HR-k", parent="kadm@x", parenttype="User", parentfield="roles",
                  role="Kalenderadministrator", docstatus=0, idx=1))
    s.add_all([Gruppe(name="G-A", gruppenname="A"),
               Gruppe(name="G-DEL", gruppenname="D", geloescht_am=datetime(2026, 1, 1)),
               Gruppe(name="G-OFF", gruppenname="O")])
    s.flush()
    s.add(Untergruppe(name="UG-1", untergruppenname="U", gruppe="G-A"))
    s.flush()
    for i, (g, n) in enumerate([("G-A", "hv@x"), ("G-A", "mit@x"), ("G-DEL", "fremd@x"),
                                ("G-A", "aus@x"), ("G-OFF", "pers@x"), ("G-DEL", "mvdel@x")]):
        s.add(Gruppenmitgliedschaft(name=f"gm{i}", parent=g, parentfield="mitglieder",
                                    parenttype="Gruppe", mitglied=f"M-{n}", status="Aktiv"))
    s.add(Untergruppenmitgliedschaft(name="ugm1", parent="UG-1", parenttype="Untergruppe",
                                     parentfield="mitglieder", mitglied="M-ugmit@x", status="Aktiv"))
    s.add_all([
        RechteGruppenrolle(gruppe="G-A", untergruppe=None, benutzer="hv@x", rolle="HV"),
        RechteGruppenrolle(gruppe="G-A", untergruppe="UG-1", benutzer="gl@x", rolle="GL"),
        RechteGruppenrolle(gruppe="G-DEL", untergruppe=None, benutzer="mvdel@x", rolle="MV"),
        RechteModul(gruppe="G-A", modul="kalender"),
        RechteModul(gruppe="G-DEL", modul="kalender"),
    ])
    s.add_all([Kalender(name=k, calendar_name=k) for k in KAL])
    s.flush()
    s.add_all([
        RechteObjekt(typ="kalender", objekt="K-A", gruppe="G-A"),
        RechteObjekt(typ="kalender", objekt="K-UG", gruppe="G-A", untergruppe="UG-1",
                     gruppe_status="aktiv"),
        RechteObjekt(typ="kalender", objekt="K-UG2", gruppe="G-A", untergruppe="UG-1",
                     standard_gruppe_lesen=False),
        RechteObjekt(typ="kalender", objekt="K-UGPUB", gruppe="G-A", untergruppe="UG-1",
                     gemeinde_status="aktiv"),
        RechteObjekt(typ="kalender", objekt="K-DEL", gruppe="G-DEL"),
        RechteObjekt(typ="kalender", objekt="K-OFF", gruppe="G-OFF"),
        RechteObjekt(typ="kalender", objekt="K-GEM", gemeinde_status="aktiv"),
        RechteObjekt(typ="kalender", objekt="K-GEM2"),
        RechteObjekt(typ="kalender", objekt="K-PUB", gruppe="G-A", gemeinde_status="aktiv"),
        RechteObjekt(typ="kalender", objekt="K-PERS", gruppe="G-A", standard_gruppe_lesen=False),
        # verwaister Rechte-Eintrag ohne Kalender-Zeile
        RechteObjekt(typ="kalender", objekt="K-WAISE", gruppe="G-A"),
    ])
    s.add_all([
        RechteFreigabe(typ="kalender", objekt="K-GEM2", gruppe="G-A", lesen=True, schreiben=True),
        RechteFreigabe(typ="kalender", objekt="K-GEM2", gruppe="G-DEL", lesen=True, schreiben=True,
                       moderieren=True),
        RechteFreigabe(typ="kalender", objekt="K-PERS", benutzer="pers@x", lesen=True,
                       schreiben=True, moderieren=True),
        RechteFreigabe(typ="kalender", objekt="K-OFF", benutzer="pers@x", lesen=True,
                       schreiben=True, moderieren=True),
        # Moderation OHNE Schreibfreigabe — der Fall aus R2 (MUSS 1, SOLL 2)
        RechteFreigabe(typ="kalender", objekt="K-PUB", benutzer="mit@x", moderieren=True),
        RechteFreigabe(typ="kalender", objekt="K-A", benutzer="aus@x", lesen=True, schreiben=True),
    ])
    s.commit()
    return s


def _antworten(n, namen):
    out = {}
    for k in namen:
        for a in (R.LESEN, R.SCHREIBEN, R.VORSCHLAGEN, R.MODERIEREN, R.VERWALTEN):
            e = R.darf(n, a, "kalender", k)
            out[(k, a)] = (bool(e), getattr(e, "grund", None))
        out[(k, "pruef")] = list(R.pruefstufen(n, "kalender", k))
        out[(k, "mod")] = list(R.moderationsstufen(n, "kalender", k))
    return out


@pytest.mark.parametrize("n", NUTZER)
def test_matrix_vorladen_gleich_einzelfrage(welt, n):
    """Der Vorrat selbst: was `kalender_rechte_vorladen` merkt, ist die
    frische Antwort des Kerns — Feld fuer Feld (R1-Gleichheit, wiederholt)."""
    from diakronos_app.db import als_aktuelle_sitzung
    from diakronos_app.rechte.kern import merkungsrahmen
    from diakronos_app.rechte.vorladen import kalender_rechte_vorladen

    set_user(n)
    with als_aktuelle_sitzung(welt):
        frisch = _antworten(n, ALLE)  # ohne Merker
        with merkungsrahmen():
            kalender_rechte_vorladen(n, ALLE)
            vor = _antworten(n, ALLE)
    assert vor == frisch


@pytest.mark.parametrize("n", NUTZER)
def test_matrix_alt_vs_neu(welt, n):
    """Die LISTE und die Einzelfragen danach (alt = ohne Merker) sind gleich."""
    from diakronos_app.api.kronos.moderation import ist_moderator, schreibt_direkt
    from diakronos_app.api.kronos.permissions import get_accessible_calendars, hat_leserecht
    from diakronos_app.db import als_aktuelle_sitzung
    from diakronos_app.rechte.kern import merkungsrahmen

    set_user(n)
    abw = []
    with als_aktuelle_sitzung(welt):
        alt_liste = {c["name"]: c for c in get_accessible_calendars()}  # ohne Merker = alt
        with merkungsrahmen():
            neu_liste = {c["name"]: c for c in get_accessible_calendars()}
            assert neu_liste == alt_liste
            for k in ALLE:
                alt = alt_liste.get(k, {})
                neu = (hat_leserecht(k), ist_moderator(k), schreibt_direkt(k),
                       schreibt_direkt(k, aenderung=True))
                erw = (k in alt_liste, bool(alt.get("is_moderator")), bool(alt.get("direkt")),
                       bool(alt.get("aendert_direkt")))
                if neu != erw:
                    abw.append((k, "neu", neu, "alt", erw))
    assert not abw, abw


# (Nutzer, Kalender): die drei Faelle aus R2 plus der Moderator ohne Schreibrecht
# auf einem NICHT oeffentlichen Kalender (SOLL 2).
VERGIFTUNGS_FAELLE = [
    ("kadm@x", "K-PUB"),     # Kalenderadministrator auf oeffentlichem Kalender
    ("mit@x", "K-PUB"),      # Einzelfreigabe „moderieren“, ohne Schreibrecht
    ("kadm@x", "K-UGPUB"),   # Kalenderadministrator auf untergruppen-oeffentlichem Kalender
    ("mit@x", "K-GEM2"),     # Schreibfreigabe ueber die Gruppe (Gegenprobe: bleibt ja)
]


@pytest.mark.parametrize("n,k", VERGIFTUNGS_FAELLE)
def test_vergiftung_darf_schreiben_reihenfolge_einzelfrage_zuerst(welt, n, k):
    """R2 MUSS 1: Einzelfrage zuerst, DANN die Liste — danach dieselbe Antwort.

    Genau diese Reihenfolge vergiftete der Nachtrag aus R1: `ist_moderator`
    setzt `objekt_kontext`, das Vorabladen ueberspringt den Kalender, und der
    Kurzschluss im Oder der Liste fragt `darf(SCHREIBEN)` nie — der Nachtrag
    legte trotzdem `write` als `darf(SCHREIBEN)` ab.
    """
    from diakronos_app.api.kronos.moderation import ist_moderator
    from diakronos_app.api.kronos.permissions import get_accessible_calendars
    from diakronos_app.db import als_aktuelle_sitzung
    from diakronos_app.rechte.kern import merkungsrahmen

    set_user(n)
    with als_aktuelle_sitzung(welt):
        frisch = (bool(R.darf(n, R.SCHREIBEN, "kalender", k)),
                  bool(R.darf(n, R.VORSCHLAGEN, "kalender", k)),
                  list(R.pruefstufen(n, "kalender", k)))
        with merkungsrahmen():
            ist_moderator(k)            # Einzelfrage zuerst (setzt objekt_kontext)
            get_accessible_calendars()  # Liste danach
            danach = (bool(R.darf(n, R.SCHREIBEN, "kalender", k)),
                      bool(R.darf(n, R.VORSCHLAGEN, "kalender", k)),
                      list(R.pruefstufen(n, "kalender", k)))
    assert danach == frisch, (frisch, danach)


@pytest.mark.parametrize("n,k", VERGIFTUNGS_FAELLE)
def test_vergiftung_darf_schreiben_reihenfolge_liste_zuerst(welt, n, k):
    """Zweite Reihenfolge: Liste zuerst, danach die Einzelfrage.

    Der Weg, den `get_calendar_events` geht (Liste, dann je Termin
    `ist_moderator`/`schreibt_direkt`) — und der Weg, den der Waechtertest in
    `test_perf_k2_vorladen.py` prueft. Beide muessen zur frischen Antwort
    passen, sonst haengt die Antwort an der Reihenfolge.
    """
    from diakronos_app.api.kronos.moderation import ist_moderator, schreibt_direkt
    from diakronos_app.api.kronos.permissions import get_accessible_calendars, hat_leserecht
    from diakronos_app.db import als_aktuelle_sitzung
    from diakronos_app.rechte.kern import merkungsrahmen

    set_user(n)
    with als_aktuelle_sitzung(welt):
        frisch = (bool(R.darf(n, R.SCHREIBEN, "kalender", k)),
                  bool(R.darf(n, R.VORSCHLAGEN, "kalender", k)),
                  list(R.pruefstufen(n, "kalender", k)),
                  bool(R.darf(n, R.LESEN, "kalender", k)))
        with merkungsrahmen():
            get_accessible_calendars()   # Liste zuerst
            danach = (bool(R.darf(n, R.SCHREIBEN, "kalender", k)),
                      bool(R.darf(n, R.VORSCHLAGEN, "kalender", k)),
                      list(R.pruefstufen(n, "kalender", k)),
                      bool(R.darf(n, R.LESEN, "kalender", k)))
            # und die Einzelfragen obendrauf (der Terminweg)
            ist_moderator(k)
            schreibt_direkt(k)
            hat_leserecht(k)
            zuletzt = (bool(R.darf(n, R.SCHREIBEN, "kalender", k)),
                       bool(R.darf(n, R.VORSCHLAGEN, "kalender", k)),
                       list(R.pruefstufen(n, "kalender", k)),
                       bool(R.darf(n, R.LESEN, "kalender", k)))
    assert danach == frisch, (frisch, danach)
    assert zuletzt == frisch, (frisch, zuletzt)
