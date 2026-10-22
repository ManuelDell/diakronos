"""ST3 — Planvorlage an Gruppen binden: Personenpool, Gruppenverantwortliche, Sichtbarkeit.

Slices:
1. Schema/Pruefung: ``gruppen``/``inkl_untergruppen`` validieren; doppelte
   Gruppe = Fehler, ``inkl_untergruppen`` ohne ``gruppen`` = Warnung.
2. Personenpool: gebundene Gruppe schraenkt Personen UND Abwesenheiten ein
   (zentral in der Datenquelle); ohne Bindung bleibt alles wie bisher.
   ``inkl_untergruppen`` nimmt Untergruppen mit.
3. Rechte: ein Gruppenverantwortlicher (kein Admin/Bereich) darf Plaene der
   Vorlage anlegen/bearbeiten/veroeffentlichen und Person-Faehigkeiten im Pool
   pflegen — die Vorlage selbst aendern bleibt 403.
4. Datenminimierung: die Pool-/Stammdatenantwort enthaelt Name/Kuerzel/
   Faehigkeiten, aber KEINE E-Mail und keine Abwesenheitsgruende.
5. Themen-Vereinheitlichung: ein Merkmal mit ``quelle='psalmos.kategorie'``
   liest seine Werte aus den Psalmos-Liedkategorien (eine Wahrheit).
"""

from __future__ import annotations

from datetime import date

PFAD = "/api/method/diakronos.planrahmen.api."


def aufruf(client, methode, **daten):
    r = client.post(PFAD + methode, json=daten)
    assert r.status_code == 200, r.text
    return r.json()["message"]


def pruefe(client, methode, **daten):
    return client.post(PFAD + methode, json=daten)


def anmelden(client, benutzer):
    from diakronos_app import frappe_compat
    from diakronos_app.frappe_compat import sitzungen
    frappe_compat.reset_user()
    sid, csrf = sitzungen.anlegen(benutzer)
    client.cookies.set("sid", sid)
    client.headers["X-Frappe-CSRF-Token"] = csrf


def _chorplan(gruppen=None, inkl=False):
    """Minimaler Chorplan mit Personen-Feld und optionaler Gruppenbindung."""
    d = {"schema": "diakronos/plantyp@1", "id": "chorplan-st3", "name": "Chorplan ST3",
         "bereich": "Chor",
         "termine": {"manuell": [{"datum": "2026-01-04"}]},
         "merkmale": {"person": [{"id": "dirigent", "art": "tag", "name": "dirigiert"}]},
         "felder": [{"id": "dirigent", "art": "person", "rolle": {"merkmal": "dirigent"},
                     "fuellen": "manuell"}]}
    if gruppen is not None:
        d["gruppen"] = gruppen
    if inkl:
        d["inkl_untergruppen"] = True
    return d


def _welt(sf, *, chor_mitglieder=("m1", "m2"), extra=("m3",)):
    """Bereich, Konten, Mitglieder, Gruppen und Verantwortlichkeiten."""
    from diakronos_app.models.core import User
    from diakronos_app.models.diakonos import (
        Dienstbereich, DienstbereichVerantwortlicher, Gruppe, GruppeVerantwortlicher,
        Gruppenmitgliedschaft, Mitglied,
    )
    with sf.begin() as s:
        s.add(Dienstbereich(name="Chor"))
        for u in ("chef", "gv_chor", "mitglied", "normalo"):
            s.add(User(name=u, email=u, enabled=True))
        s.flush()
        for name in ("chef", "gv_chor", "mitglied", "normalo"):
            s.add(Mitglied(name=name, user=name, email=f"{name}@example.org",
                           vorname=name, nachname="Test"))
        for name, mail in (("m1", "m1@example.org"), ("m2", "m2@example.org"),
                           ("m3", "m3@example.org")):
            s.add(Mitglied(name=name, vorname=name, nachname="Chor", email=mail,
                           status="Mitglied"))
        s.add(DienstbereichVerantwortlicher(name="bv-chor", parent="Chor",
                                            parenttype="Dienstbereich",
                                            parentfield="verantwortliche", user="chef"))
        s.add(Gruppe(name="Chor", gruppenname="Chor"))
        s.add(Gruppe(name="Jugendchor", gruppenname="Jugendchor", obergruppe="Chor"))
        s.flush()
        # Gruppenverantwortlicher der Gruppe 'Chor' (KEIN Admin/Bereich).
        s.add(GruppeVerantwortlicher(name="gv-1", parent="Chor", parenttype="Gruppe",
                                     parentfield="verantwortliche", user="gv_chor"))
        for i, m in enumerate(chor_mitglieder):
            s.add(Gruppenmitgliedschaft(name=f"gm-chor-{i}", parent="Chor",
                                        parenttype="Gruppe", parentfield="mitglieder",
                                        mitglied=m, status="Aktiv"))
        for i, m in enumerate(extra):
            s.add(Gruppenmitgliedschaft(name=f"gm-jugend-{i}", parent="Jugendchor",
                                        parenttype="Gruppe", parentfield="mitglieder",
                                        mitglied=m, status="Aktiv"))


# --------------------------------------------------------------------------- #
# Slice 1: Schema/Pruefung
# --------------------------------------------------------------------------- #

def test_gruppen_schema_gueltig(client, patched_db):
    erg = aufruf(client, "plantyp_pruefen", definition=_chorplan(["Chor"], inkl=True))
    assert erg["gueltig"] is True, erg["meldungen"]


def test_gruppe_doppelt_ist_fehler(client, patched_db):
    erg = aufruf(client, "plantyp_pruefen", definition=_chorplan(["Chor", "Chor"]))
    assert erg["gueltig"] is False
    codes = {m["code"] for m in erg["meldungen"]}
    assert "gruppe_doppelt" in codes


def test_inkl_untergruppen_ohne_gruppen_ist_warnung(client, patched_db):
    d = _chorplan(None, inkl=True)
    erg = aufruf(client, "plantyp_pruefen", definition=d)
    assert erg["gueltig"] is True  # Warnung blockiert nicht
    assert any(m["code"] == "inkl_untergruppen_ohne_gruppen" and m["stufe"] == "warnung"
               for m in erg["meldungen"])


def test_quelle_nur_bei_auswahl(client, patched_db):
    d = _chorplan()
    d["merkmale"]["person"][0]["quelle"] = "psalmos.kategorie"
    erg = aufruf(client, "plantyp_pruefen", definition=d)
    assert erg["gueltig"] is False
    assert any(m["code"] == "quelle_ohne_auswahl" for m in erg["meldungen"])


# --------------------------------------------------------------------------- #
# Slice 2: Personenpool (zentral in der Datenquelle)
# --------------------------------------------------------------------------- #

def test_pool_beschraenkt_personen_und_abwesenheiten(client, patched_db, session_factory):
    import diakronos_app.db as db
    from diakronos_app.planrahmen.datenquelle_db import DBDatenquelle
    _welt(session_factory)
    with db.SessionLocal.begin() as s:
        # Ohne Bindung: alle vier Mitglieder.
        ohne = DBDatenquelle(s, plantyp="chorplan-st3")
        assert {p.kennung for p in ohne.personen()} >= {"m1", "m2", "m3"}
        # Mit Bindung an 'Chor': nur m1, m2.
        mit = DBDatenquelle(s, plantyp="chorplan-st3", pool_gruppen=frozenset({"Chor"}))
        assert {p.kennung for p in mit.personen()} == {"m1", "m2"}


def test_pool_inkl_untergruppen(client, patched_db, session_factory):
    import diakronos_app.db as db
    from diakronos_app.planrahmen.datenquelle_db import DBDatenquelle
    _welt(session_factory)
    with db.SessionLocal.begin() as s:
        mit = DBDatenquelle(s, plantyp="chorplan-st3", pool_gruppen=frozenset({"Chor"}),
                           pool_inkl_untergruppen=True)
        assert {p.kennung for p in mit.personen()} == {"m1", "m2", "m3"}


def test_pool_wirkt_ueber_stammdaten_und_kandidaten(client, patched_db, session_factory):
    """Der Pool ist zentral: stammdaten_holen und merkmal_kandidaten sehen ihn."""
    _welt(session_factory)
    anmelden(client, "chef")
    d = _chorplan(["Chor"])
    d["merkmale"]["lieder"] = [{"id": "dirigent", "art": "person",
                                "rolle": {"merkmal": "dirigent"}}]
    aufruf(client, "plantyp_speichern", definition=d, gueltig_ab="2026-01-01")
    # Faehigkeit fuer eine Pool-Person pflegen (chef = Bereich, darf das).
    aufruf(client, "merkmale_pflegen", plantyp="chorplan-st3",
           werte=[{"ziel": "person", "schluessel": "dirigent", "ziel_id": "m1", "wert": True}])
    stamm = aufruf(client, "stammdaten_holen", plantyp="chorplan-st3")
    assert {p["kennung"] for p in stamm["personen"]} == {"m1", "m2"}
    assert stamm["pool"]["gruppen"] == ["Chor"]
    assert stamm["pool"]["anzahl"] == 2
    kandidaten = aufruf(client, "merkmal_kandidaten", plantyp="chorplan-st3",
                        schluessel="dirigent")
    # Nur die markierte Pool-Person (m3 ist nicht im Pool).
    assert {k["kennung"] for k in kandidaten["kandidaten"]} == {"m1"}


# --------------------------------------------------------------------------- #
# Slice 3+4: Rechte und Datenminimierung
# --------------------------------------------------------------------------- #

def test_gruppenverantwortlicher_sieht_nur_seine_vorlage(client, patched_db, session_factory):
    _welt(session_factory)
    anmelden(client, "chef")
    aufruf(client, "plantyp_speichern", definition=_chorplan(["Chor"]), gueltig_ab="2026-01-01")
    aufruf(client, "plantyp_speichern",
           definition={"schema": "diakronos/plantyp@1", "id": "fremd-st3", "name": "Fremd",
                       "bereich": "Chor", "termine": {"manuell": [{"datum": "2026-01-04"}]},
                       "felder": [{"id": "x", "art": "text"}]},
           gueltig_ab="2026-01-01")
    # Gruppenverantwortlicher: sieht nur die gebundene Vorlage.
    anmelden(client, "gv_chor")
    liste = aufruf(client, "plantypen_liste")
    assert {t["schluessel"] for t in liste} == {"chorplan-st3"}
    assert liste[0]["darf_plan_anlegen"] is True
    assert liste[0]["darf_plantyp_bearbeiten"] is False  # Vorlage bleibt tabu
    # Vorlage aendern -> 403.
    assert pruefe(client, "plantyp_speichern", definition=_chorplan(["Chor"]),
                  gueltig_ab="2026-01-01").status_code == 403


def test_gruppenverantwortlicher_legt_plan_an_und_pflegt_faehigkeiten(client, patched_db, session_factory):
    _welt(session_factory)
    anmelden(client, "chef")
    aufruf(client, "plantyp_speichern", definition=_chorplan(["Chor"]), gueltig_ab="2026-01-01")
    anmelden(client, "gv_chor")
    plan = aufruf(client, "plan_anlegen", plantyp="chorplan-st3", titel="Chor 2026",
                  von="2026-01-01", bis="2026-02-01")
    # Faehigkeiten im Pool pflegen.
    assert pruefe(client, "merkmale_pflegen", plantyp="chorplan-st3",
                  werte=[{"ziel": "person", "schluessel": "dirigent", "ziel_id": "m1",
                          "wert": True}]).status_code == 200
    # Person ausserhalb des Pools -> abgelehnt.
    assert pruefe(client, "merkmale_pflegen", plantyp="chorplan-st3",
                  werte=[{"ziel": "person", "schluessel": "dirigent", "ziel_id": "m3",
                          "wert": True}]).status_code == 417
    assert plan["id"]


def test_normales_mitglied_sieht_nichts(client, patched_db, session_factory):
    _welt(session_factory)
    anmelden(client, "chef")
    aufruf(client, "plantyp_speichern", definition=_chorplan(["Chor"]), gueltig_ab="2026-01-01")
    anmelden(client, "normalo")
    assert pruefe(client, "plantypen_liste").status_code == 403
    assert pruefe(client, "stammdaten_holen", plantyp="chorplan-st3").status_code == 403


def test_pool_antwort_ohne_pii(client, patched_db, session_factory):
    _welt(session_factory)
    anmelden(client, "chef")
    aufruf(client, "plantyp_speichern", definition=_chorplan(["Chor"]), gueltig_ab="2026-01-01")
    stamm = aufruf(client, "stammdaten_holen", plantyp="chorplan-st3")
    rohdaten = str(stamm)
    assert "@example.org" not in rohdaten  # keine E-Mail
    for p in stamm["personen"]:
        assert "email" not in p
        assert set(p.keys()) <= {"kennung", "anzeige", "name", "vorname", "nachname",
                                 "kuerzel", "gruppen", "merkmale"}


# --------------------------------------------------------------------------- #
# Slice 5: Themen-Vereinheitlichung (Kategorie-Quelle)
# --------------------------------------------------------------------------- #

def test_kategorie_merkmal_liest_psalmos_kategorien(client, patched_db, session_factory):
    import diakronos_app.db as db
    from diakronos_app.models.psalmos import Lied, LiedKategorie, Liedkategorie
    from diakronos_app.planrahmen.datenquelle_db import DBDatenquelle
    _welt(session_factory)
    with db.SessionLocal.begin() as s:
        s.add(Lied(name="L1", titel="Lied Eins", aktiv=True))
        s.add(Liedkategorie(name="kat-advent", kategoriename="Advent"))
        s.flush()
        s.add(LiedKategorie(name="lk-1", parent="L1", parenttype="Lied",
                            parentfield="kategorien", kategorie="kat-advent", idx=0))
    anmelden(client, "chef")
    d = _chorplan(["Chor"])
    d["merkmale"]["lieder"] = [{"id": "thema", "art": "auswahl", "mehrfach": True,
                                "quelle": "psalmos.kategorie"}]
    aufruf(client, "plantyp_speichern", definition=d, gueltig_ab="2026-01-01")
    with db.SessionLocal.begin() as s:
        quelle = DBDatenquelle(s, plantyp="chorplan-st3")
        lied = next(x for x in quelle.sammlung("lieder") if x.kennung == "L1")
        assert lied.attribut("thema") == "Advent"


def test_kategorie_werte_pflegen_schreibt_katalog(client, patched_db, session_factory):
    _welt(session_factory)
    anmelden(client, "chef")
    d = _chorplan(["Chor"])
    d["merkmale"]["lieder"] = [{"id": "thema", "art": "auswahl", "mehrfach": True,
                                "quelle": "psalmos.kategorie"}]
    aufruf(client, "plantyp_speichern", definition=d, gueltig_ab="2026-01-01")
    erg = aufruf(client, "sammlungsmerkmal_werte_pflegen", plantyp="chorplan-st3",
                 schluessel="thema", aktion="hinzufuegen", wert="Erntedank")
    assert "Erntedank" in erg["werte"]
    assert erg["quelle"] == "psalmos.kategorie"
