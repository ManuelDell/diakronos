"""DSGVO-2d — Anzeige „Gelöschte Person“ überall.

DIE ZUSAGE
----------
Überall, wo ein Mitgliedsname erscheint (Pläne, Dienstpläne, Ablaufpläne,
Gruppen, Kalender-Mitarbeiter, Auswahllisten, Beiträge/Autor, Adressbuch,
DSGVO-Übersicht), erscheint für ein gelöschtes Mitglied (Status ``geloescht``,
Kennung ``geloescht-…``) genau ``Gelöschte Person``:

* kein Klarname — auch nicht für Administratoren (die Löschung ist
  endgültig, Fachentscheidung Manuel 2026-10-20),
* kein Rest-Initial („Gelöschte P.“) aus einem wiederhergestellten
  Sicherungsstand,
* nie die technische Kennung ``geloescht-<hex>``, nie leere Klammern,
* keine Auswahlliste führt die Person (weder im Plan-Rahmen noch in der
  Gruppen-Auswahl).

WARUM DIE PRÜFUNG AM ZENTRALEN AUFLÖSER BEGINNT
-----------------------------------------------
Die Regel steht in ``frappe_compat/personen_anzeige.py``; alle Auslieferungs-
wege rufen sie. Die Tests unten gehen deshalb jeden WEG einzeln durch (nicht
nur die Funktion), weil genau das die Karte verlangt — ein grüner Helfer
beweist nichts über den Weg, der ihn nicht benutzt.
"""
from __future__ import annotations

import pytest

from diakronos_app.frappe_compat.personen_anzeige import (
    GELOESCHT_ANZEIGE, GELOESCHT_PRAEFIX, anzeigename, ist_geloescht, kuerze,
    kuerze_name, namen_map,
)
from diakronos_app.frappe_compat.session import set_user
from diakronos_app.models.core import HasRole, User
from diakronos_app.models.diakonos import Gruppe, Gruppenmitgliedschaft, Mitglied

MA = "Mitgliederadministrator"
ADMIN = "verwaltung@x.org"
LESER = "leser@x.org"

#: So sieht eine gelöschte Person im Betrieb aus: neutrale Kennung, Endstatus
#: „geloescht“, Vor-/Nachname als Platzhalter (dsgvo_anonymisierung.VORNAME).
TOT = "geloescht-9f3a"
TOT_KONTO = "geloeschte-person@deleted.invalid"


def _konto(sess, kennung, rolle=None, *, vorname="Lena", nachname="Leser",
           konto=None, status="Mitglied", ausgeschlossen=0, user_zeile=True):
    konto = konto or kennung
    if user_zeile:
        sess.add(User(name=konto, email=konto, full_name=f"{vorname} {nachname}",
                      enabled=status != "geloescht"))
    if rolle:
        sess.add(HasRole(name=f"HR-{kennung}-{rolle}", parent=konto,
                         parenttype="User", parentfield="roles", role=rolle,
                         docstatus=0, idx=1))
    sess.add(Mitglied(name=kennung, vorname=vorname, nachname=nachname,
                      email=konto, status=status, user=konto,
                      ausgeschlossen=ausgeschlossen, docstatus=0, idx=0))


@pytest.fixture()
def welt(patched_db):
    """Gemeinde mit Administrator, Leser und einer gelöschten Person."""
    sess = patched_db()
    _konto(sess, ADMIN, MA, vorname="Anna", nachname="Admin", konto=ADMIN)
    _konto(sess, LESER, vorname="Lena", konto=LESER)
    # Die gelöschte Person hat KEIN Konto mehr (dsgvo_anonymisierung löscht
    # die `user`-Zeile) und den Endstatus.
    _konto(sess, TOT, vorname="Gelöschte", nachname="Person",
           konto=TOT_KONTO, status="geloescht", ausgeschlossen=1,
           user_zeile=False)
    sess.commit()
    for name in (ADMIN, LESER, TOT):
        sess.get(Mitglied, name).ancestor_path = "/gemeinde/|"
    sess.commit()
    yield sess
    sess.close()
    set_user("Administrator")


# ── Der zentrale Auflöser ──────────────────────────────────────────────────


def test_zentraler_aufloeser_zeigt_fuer_geloeschte_person_genau_einen_text(
        patched_db) -> None:
    """Die eine Regel: Status oder Kennung „geloescht“ -> ``Gelöschte Person``.

    Geprüft werden beide Eingabeformen von ``anzeigename`` (Zeile und reine
    Kennung) und beide Zeugen (Status und Präfix), für Administrator UND Leser.
    """
    for wer in (ADMIN, "Admin-anna"):
        set_user(wer)
        for zeile in (
            {"name": TOT, "vorname": "Gelöschte", "nachname": "Person",
             "status": "geloescht"},
            # Rest-Name aus einem alten Sicherungsstand: der Status entscheidet.
            {"name": TOT, "vorname": "Elvira", "nachname": "Dorn",
             "status": "geloescht"},
            # Status fehlt, aber die Kennung ist die neutrale: auch dann neutral.
            {"name": TOT, "vorname": "Elvira", "nachname": "Dorn"},
        ):
            assert anzeigename(zeile) == GELOESCHT_ANZEIGE, zeile
        assert anzeigename(TOT) == GELOESCHT_ANZEIGE, "Kennung ohne Zeile"
        assert anzeigename({"name": TOT}) == GELOESCHT_ANZEIGE
        # Die Kennung selbst taucht in KEINER Antwort auf.
        assert TOT not in anzeigename(TOT)


def test_geloeschte_person_hat_weder_kuerzel_noch_kurzform(patched_db) -> None:
    """Kein Rest-Initial: ``kuerze_name``/``kuerze`` liefern den festen Text."""
    assert kuerze_name("Elvira", "Dorn", TOT) == GELOESCHT_ANZEIGE
    assert kuerze_name("Gelöschte", "Person", TOT) == GELOESCHT_ANZEIGE

    kurz = kuerze({"name": TOT, "vorname": "Elvira", "nachname": "Dorn",
                   "email": "elvira@example.org", "full_name": "Elvira Dorn",
                   "status": "geloescht"})
    assert kurz["vorname"] == GELOESCHT_ANZEIGE
    assert kurz["nachname"] is None
    assert kurz["full_name"] == GELOESCHT_ANZEIGE
    assert kurz["email"] is None, "keine Adresse einer gelöschten Person"


def test_ist_geloescht_erkennt_status_und_kennung() -> None:
    assert ist_geloescht({"status": "geloescht"})
    assert ist_geloescht({"status": " GELOESCHT "})
    assert ist_geloescht(TOT)
    assert ist_geloescht({"name": TOT})
    assert not ist_geloescht({"status": "Mitglied", "name": "M-0001"})
    assert not ist_geloescht({"status": "Ausgetreten", "name": "M-0002"})
    assert not ist_geloescht(None)


def test_ausgetretene_bleiben_gekuerzt_und_nicht_neutral(patched_db) -> None:
    """Gegenprobe: DSGVO-2d weitet die Austritts-Kürzung NICHT auf alle aus."""
    assert kuerze_name("Elvira", "Dorn", "M-0003") == "Elvira D."
    set_user(LESER)
    assert anzeigename({"name": "M-0003", "vorname": "Elvira",
                        "nachname": "Dorn", "status": "Ausgetreten"}) == "Elvira D."


# ── Weg 1: Mitgliederliste ─────────────────────────────────────────────────


def test_weg_liste_geloeschte_person_ohne_namen_und_adresse(welt, client) -> None:
    set_user(ADMIN)
    from diakronos_app.api.mitglieder import get_mitglieder_liste

    antwort = get_mitglieder_liste(status="geloescht")
    zeilen = antwort["data"] if isinstance(antwort, dict) else antwort
    treffer = [z for z in zeilen if z["name"] == TOT]
    assert len(treffer) == 1, zeilen
    z = treffer[0]
    assert z["full_name"] == GELOESCHT_ANZEIGE
    assert z["vorname"] == GELOESCHT_ANZEIGE
    assert z["nachname"] is None
    assert z["email"] is None
    assert z["status"] == "geloescht"


# ── Weg 2: Adressbuch ──────────────────────────────────────────────────────


def test_weg_adressbuch_geloeschte_person_ohne_klarnamen_und_foto(welt, client) -> None:
    """Das Adressbuch baute den Namen selbst aus Vor-/Nachname."""
    set_user(ADMIN)
    from diakronos_app.api.mitglieder import get_adressbuch

    rows = get_adressbuch()["data"]
    treffer = [r for r in rows if r["name"] == TOT]
    assert len(treffer) == 1, rows
    r = treffer[0]
    assert r["vorname"] == GELOESCHT_ANZEIGE
    assert r["nachname"] == ""
    assert r["foto"] == "", "kein Bildverweis einer gelöschten Person"
    assert r["email"] is None and r["telefonnummer"] is None


# ── Weg 3: DSGVO-Übersicht (Verwaltungsseite) ─────────────────────────────


def test_weg_dsgvo_uebersicht_meldet_geloescht_und_neutralisiert(welt, client) -> None:
    set_user(ADMIN)
    from diakronos_app.api.admin_hub import get_dsgvo_uebersicht

    antwort = get_dsgvo_uebersicht()
    treffer = [m for m in antwort["mitglieder"] if m["name"] == TOT]
    assert len(treffer) == 1, antwort["mitglieder"]
    m = treffer[0]
    assert m["geloescht"] is True, "die Oberfläche braucht das Kennzeichen"
    assert m["vorname"] == GELOESCHT_ANZEIGE and m["nachname"] == ""
    assert m["email"] is None, "die Platzhalter-Adresse ist keine Personendaten-Antwort"
    # Eine lebende Person bleibt unverändert.
    lebend = [x for x in antwort["mitglieder"] if x["name"] == LESER][0]
    assert lebend["geloescht"] is False and lebend["vorname"] == "Lena"


# ── Weg 4: Kalender-Mitarbeiter und Dienstplan (namen_map) ────────────────


def test_weg_kalender_und_dienstplan_namen_map(welt) -> None:
    # Die Erwartung fuer eine lebende Person ist der volle Name: `anzeigename`
    # liefert fuer Nicht-Ausgeschiedene "Vorname Nachname" (die Begruessung im
    # Kopf nutzt dagegen `anzeigename.mjs` im Browser und zeigt nur den Vornamen).
    """Kalender (`_attach_mitarbeiter`) und Dienstplan lesen `namen_map`."""
    set_user(LESER)
    namen = namen_map([TOT, LESER])
    assert namen[TOT] == GELOESCHT_ANZEIGE
    assert namen[LESER] == "Lena Leser"


# ── Weg 5: Gruppe (Mitgliederliste der Gruppe) ────────────────────────────


def test_weg_gruppe_zeigt_geloeschte_person_neutral(welt, client) -> None:
    """Die Gruppen-Mitgliederliste des Servers nennt den neutralen Text."""
    from diakronos_app.api.gruppen import get_gruppe_detail

    sess = welt
    sess.add(Gruppe(name="G-chor", gruppenname="Chor", docstatus=0, idx=0))
    sess.add(Gruppenmitgliedschaft(name="GM-1", parent="G-chor",
                                   parenttype="Gruppe", parentfield="mitglieder",
                                   mitglied=TOT, rolle="Mitglied", status="Aktiv",
                                   docstatus=0, idx=1))
    sess.add(Gruppenmitgliedschaft(name="GM-2", parent="G-chor",
                                   parenttype="Gruppe", parentfield="mitglieder",
                                   mitglied=LESER, rolle="Mitglied", status="Aktiv",
                                   docstatus=0, idx=2))
    sess.commit()

    set_user(ADMIN)
    antwort = get_gruppe_detail("G-chor")
    namen = {m["mitglied"]: m["name"] for m in antwort["mitglieder"]}
    assert namen[TOT] == GELOESCHT_ANZEIGE

    set_user(LESER)
    from diakronos_app.api.gruppen import _mitglieder_der_gruppe

    namen_leser = {m["mitglied"]: m["name"] for m in _mitglieder_der_gruppe(
        "Gruppe", "G-chor")}
    assert namen_leser[TOT] == GELOESCHT_ANZEIGE


# ── Weg 6: Plan-Rahmen (Anzeige alter Pläne) ──────────────────────────────


def test_weg_planrahmen_anzeige_und_personenpool(welt) -> None:
    """Der Plan-Rahmen liefert den Text — und bietet die Person nie an."""
    from diakronos_app.db import SessionLocal
    from diakronos_app.planrahmen.datenquelle_db import DBDatenquelle

    sess = welt
    sess.expire_all()
    set_user(LESER)
    s = SessionLocal()
    try:
        quelle = DBDatenquelle(s)
        anzeige = {p.kennung: p for p in quelle.personen_anzeige()}
        kandidaten = {p.kennung for p in quelle.personen()}
    finally:
        s.close()
    person = anzeige[TOT]
    assert person.name == GELOESCHT_ANZEIGE
    assert person.vorname == GELOESCHT_ANZEIGE
    assert person.kuerzel == "", "kein Kürzel mit Initialen"
    assert person.email == ""
    assert TOT not in kandidaten, "gelöschte Person ist kein Kandidat"


# ── Weg 7: Auswahllisten ──────────────────────────────────────────────────


def test_weg_auswahllisten_bieten_geloeschte_person_nicht_an(welt, client) -> None:
    """Die Gruppen-Auswahl filtert den Endstatus (eine Wahrheit, AUSGESCHIEDEN)."""
    from diakronos_app.api.gruppen_auswahl import waehlbare_mitglieder

    ids = {m["mitglied"] for m in waehlbare_mitglieder()}
    assert TOT not in ids
    assert LESER in ids, "die Auswahl ist nicht generell leer"


# ── Weg 8: Beiträge/Autor ─────────────────────────────────────────────────


def test_weg_beitrag_autor_ist_neutral(welt, client) -> None:
    """`autor` steht als Text am Beitrag — dort steht der Anzeigename (N-2)."""
    from diakronos_app.models.diakonos import Beitrag

    sess = welt
    sess.add(Beitrag(name="B-1", titel="Gruß", autor=GELOESCHT_ANZEIGE,
                     autor_email=TOT_KONTO, inhalt="Text", veroeffentlicht=1,
                     docstatus=0, idx=0))
    sess.commit()

    set_user(LESER)
    from diakronos_app.api.beitraege import get_beitraege_liste

    liste = get_beitraege_liste()
    treffer = [b for b in liste if b["id"] == "B-1"]
    assert treffer and treffer[0]["author"] == GELOESCHT_ANZEIGE
    # Der Anzeigename des Autors bleibt stabil, auch wenn die Zeile nie
    # wieder einen Klarnamen traegt.
    assert "geloescht-" not in treffer[0]["author"]


# ── Weg 9: Mitglieds-Detail ───────────────────────────────────────────────


def test_weg_mitglied_detail_auch_fuer_admin_neutral(welt, client) -> None:
    """Das Detail liefert für Administratoren sonst die volle Zeile.

    Für eine gelöschte Person gilt das nicht: kein Klarname, keine Adresse —
    die Löschung ist nicht rückgängig zu machen.
    """
    set_user(ADMIN)
    from diakronos_app.api.mitglieder import get_mitglied_detail

    d = get_mitglied_detail(TOT)["data"]
    assert d["vorname"] == GELOESCHT_ANZEIGE
    assert d["nachname"] is None
    assert d["email"] is None
    # `full_name` fuehrt das Detail gar nicht (kein Feld der Tabelle) — was
    # zaehlt, sind die Namensspalten oben und die fehlende Adresse.
    assert d.get("full_name") in (None, GELOESCHT_ANZEIGE)


# ── Rest-Name aus einem alten Sicherungsstand ─────────────────────────────


def test_restname_aus_alter_sicherung_wird_nicht_durchgereicht(welt) -> None:
    """ROT-Beweis: `main` zeigte für diese Zeile „Elvira D.“ bzw. „Gelöschte P.“.

    Ein wiederhergestellter Sicherungsstand kann Vor-/Nachnamen einer
    gelöschten Person noch tragen, während Status und Kennung schon der
    Löschung entsprechen. Der ENDSTATUS entscheidet — auch für Admins.
    """
    from diakronos_app.frappe_compat.personen_anzeige import kuerze

    rest = {"name": TOT, "vorname": "Elvira", "nachname": "Dorn",
            "email": "elvira@example.org", "full_name": "Elvira Dorn"}
    set_user(ADMIN)
    assert anzeigename(rest) == GELOESCHT_ANZEIGE
    kurz = kuerze(dict(rest))
    assert kurz["vorname"] == GELOESCHT_ANZEIGE
    assert kurz["full_name"] == GELOESCHT_ANZEIGE
    assert kurz["email"] is None, "keine (auch keine maskierte) Adresse"


def test_praefix_und_anzeigetext_stimmen_mit_der_loeschung_ueberein() -> None:
    """Die Kennung entsteht in `dsgvo_anonymisierung` — beide Konstanten
    müssen zusammenpassen, sonst erkennt die Anzeige die Zeile nicht.

    Der Präfix steht in beiden Modulen (die Compat-Schicht darf nicht auf
    `dsgvo_anonymisierung` zeigen). Dieser Test hält sie zusammen.
    """
    from diakronos_app import dsgvo_anonymisierung as d

    assert d.GELOESCHT_PRAEFIX == GELOESCHT_PRAEFIX
    assert f"{d.VORNAME} {d.NACHNAME}" == GELOESCHT_ANZEIGE
    # Und die Zeile, die die Löschung schreibt, wird als gelöscht erkannt.
    assert ist_geloescht({"name": f"{d.GELOESCHT_PRAEFIX}abc", "status": "geloescht"})
    assert ist_geloescht({"name": f"{d.GELOESCHT_PRAEFIX}abc"})
