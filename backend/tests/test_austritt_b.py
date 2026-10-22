"""AUSTRITT-b — Nacharbeit zum Opus-Review (B1-B4, M2, M3, N).

Jeder Befund hat hier seine Probe. Gegen den Stand vor der Nacharbeit sind
diese Tests ROT (Klarname im Antwortkoerper,
ausgeschlossene Person fehlt in der Liste, Ausgetretene im Personenpool,
Grund auf oberster Ebene, falsche Initiale in Beziehungen) und nach der
Nacharbeit gruen. Deshalb eine eigene Datei: ``test_austritt.py`` beschreibt
die Abnahme der ersten Karte und bleibt unveraendert.

Die Namen der Zusagen sind die Kuerzel des Review-Befundberichts,
damit Kommentar, Commit und Test zusammenpassen.
"""
from __future__ import annotations

import json

import pytest

from diakronos_app.frappe_compat.exceptions import ValidationError
from diakronos_app.frappe_compat.session import set_user
from diakronos_app.models.core import HasRole, User
from diakronos_app.models.diakonos import (
    Gruppenmitgliedschaft,
    Gruppe,
    GruppeVerantwortlicher,
    Mitglied,
    MitgliedBeziehung,
    Untergruppe,
)

MA = "Mitgliederadministrator"

#: Elvira Dorn — die Person, die austritt. Kontoname = E-Mail (wie im
#: Betrieb), deshalb steht hier der Mitglieds-Schluessel „M-ziel" (ohne „@").
ZIEL = "M-ziel"
#: Wer die Gruppe sehen darf, aber kein Administrator ist.
LESER = "leser@x.org"
#: Das Verwaltungskonto. Kontoname = E-Mail (wie im Betrieb) — deshalb heisst
#: das Ziel „M-ziel" ohne „@": kein Praefix-Schluessel kann einen anderen in
#: einer `name IN (...)`-Abfrage verdecken.
ADMIN = "verwaltung@x.org"


def _konto(sess, kennung: str, rolle: str | None = None, *,
           vorname: str = "Lena", nachname: str = "Leser",
           konto: str | None = None) -> None:
    """Konto + Mitglied in EINEM Schritt (die Fixture braucht beides).

    ``konto`` ist der Kontoname, wenn er sich vom Mitglieds-Schluessel
    unterscheidet (im Betrieb: Konto = E-Mail, Mitglied = „M-…").
    """
    konto = konto or kennung
    sess.add(User(name=konto, email=konto, full_name=konto,
                  enabled=True))
    if rolle:
        sess.add(HasRole(name=f"HR-{kennung}-{rolle}", parent=konto,
                         parenttype="User", parentfield="roles", role=rolle,
                         docstatus=0, idx=1))
    sess.add(Mitglied(
        name=f"M-{kennung}", vorname=vorname, nachname=nachname,
        email=konto, status="Mitglied", user=konto,
        ausgeschlossen=0, docstatus=0, idx=0,
    ))
    sess.commit()


@pytest.fixture()
def welt(patched_db):
    """Leser, Mitgliederadministrator, Ziel und die gemeinsame Gruppe G-1."""
    sess = patched_db()
    _konto(sess, ADMIN, MA)
    _konto(sess, LESER)
    _konto(sess, "ziel", vorname="Elvira", nachname="Dorn", konto="ziel@x.org")
    sess.add_all([
        Gruppe(name="G-1", gruppenname="Chor", ancestor_path="/G-1/|/DB-A/",
               dienstbereich="DB-A", docstatus=0, idx=0),
        Untergruppe(name="UG-1", untergruppenname="Sopran", gruppe="G-1",
                    ancestor_path="/UG-1/G-1/|/DB-A/", docstatus=0, idx=0),
    ])
    sess.flush()
    for kennung in (ADMIN, LESER, "ziel"):
        sess.get(Mitglied, f"M-{kennung}").ancestor_path = "/G-1/|/DB-A/"
    sess.add_all([
        Gruppenmitgliedschaft(name="GM-ziel", parent="G-1", parenttype="Gruppe",
                              parentfield="mitglieder", mitglied=ZIEL,
                              docstatus=0, idx=1),
        Gruppenmitgliedschaft(name="GM-leser", parent="G-1", parenttype="Gruppe",
                              parentfield="mitglieder", mitglied=f"M-{LESER}",
                              docstatus=0, idx=2),
    ])
    sess.commit()
    yield sess
    sess.close()
    set_user("Administrator")


def _austritt(begruendung: str = "Austritt auf eigenen Wunsch") -> None:
    from diakronos_app.api.austritt import mitglied_austritt

    set_user(ADMIN)
    mitglied_austritt(ZIEL, begruendung, "2026-10-01")


# ── B1: Klarname Ausgetretener an Nicht-Admins ──────────────────────────────
#
# Ein Test je Auslieferungsweg aus dem Review. Jeder prueft BEIDE Seiten:
# der Nicht-Admin sieht „Elvira D.", der Admin „Elvira Dorn" — eine Kuerzung,
# die auch den Admin trifft, waere ein eigener Fehler.


def test_b1_anzeigename_ist_die_eine_regel(patched_db) -> None:
    """Die zentrale Funktion, auf der alle Wege aufsetzen."""
    from diakronos_app.frappe_compat.personen_anzeige import anzeigename

    sess = patched_db()
    _konto(sess, ADMIN, MA)
    _konto(sess, LESER)
    _konto(sess, "ziel", vorname="Elvira", nachname="Dorn", konto="ziel@x.org")
    _austritt()

    # AUSTRITT-c (N3) fuehrt die Kuerzung auf das Austrittsmerkmal (Status
    # „Ausgetreten“ / `austritt_datum`), nicht mehr auf die Marke
    # `ausgeschlossen` (die beiden Faelle Austritt und Ausschluss
    # unterscheidet). Deshalb traegt die Probe-Zeile das Merkmal selbst.
    zeile = {"name": ZIEL, "vorname": "Elvira", "nachname": "Dorn",
             "ausgeschlossen": True, "status": "Ausgetreten",
             "austritt_datum": "2026-10-01"}
    set_user(LESER)
    assert anzeigename(zeile) == "Elvira D."
    assert anzeigename(ZIEL) == "Elvira D.", "Kennung allein: Namen nachlesen"
    set_user(ADMIN)
    assert anzeigename(zeile) == "Elvira Dorn"
    # Nicht ausgetreten: Vor-/Nachname kommen durch, die Kuerzung greift nicht.
    assert anzeigename({"name": LESER, "vorname": "Lena", "nachname": "Leser",
                        "ausgeschlossen": False}) == "Lena Leser"


def test_b1_gruppenhistorie_ohne_klarnamen(welt) -> None:
    """`api/gruppen.get_gruppe_detail` — Mitglieder und Verantwortliche."""
    from diakronos_app.api.gruppen import get_gruppe_detail

    sess = welt
    sess.add(GruppeVerantwortlicher(
        name="GRV-1", parent="G-1", parenttype="Gruppe",
        parentfield="verantwortliche", user="ziel@x.org", docstatus=0, idx=1,
    ))
    sess.commit()
    _austritt(begruendung="Krankheit: Depression")

    set_user(LESER)
    antwort = get_gruppe_detail("G-1")
    assert "Dorn" not in repr(antwort), "Klarname in der Gruppenansicht (Leser)"
    assert "Elvira D." in {z["name"] for z in antwort["mitglieder"]}
    assert [v["name"] for v in antwort["verantwortliche"]] == ["Elvira D."]

    set_user(ADMIN)
    assert "Elvira Dorn" in {z["name"] for z in get_gruppe_detail("G-1")["mitglieder"]}


def test_b1_kalender_mitarbeiter_ohne_klarnamen(welt) -> None:
    """`api/kronos/calendar_get._attach_mitarbeiter` (Termin-Mitarbeiter)."""
    from diakronos_app.api.kronos.calendar_get import _attach_mitarbeiter

    _austritt()
    formatiert = [{"id": "E-1", "extendedProps": {}}]

    set_user(LESER)
    _attach_mitarbeiter(formatiert, ["E-1"])
    assert formatiert[0]["extendedProps"]["mitarbeiter"] == []

    from diakronos_app.models.kronos import ElementMitarbeiter

    sess = welt
    sess.add(ElementMitarbeiter(
        name="EM-1", parent="E-1", parenttype="Element", parentfield="mitarbeiter",
        mitglied=ZIEL, dienstrolle=None, bestaetigt=1, docstatus=0, idx=1,
    ))
    sess.commit()

    formatiert = [{"id": "E-1", "extendedProps": {}}]
    set_user(LESER)
    _attach_mitarbeiter(formatiert, ["E-1"])
    assert formatiert[0]["extendedProps"]["mitarbeiter"][0]["mitglied_name"] == "Elvira D."

    formatiert = [{"id": "E-1", "extendedProps": {}}]
    set_user(ADMIN)
    _attach_mitarbeiter(formatiert, ["E-1"])
    assert formatiert[0]["extendedProps"]["mitarbeiter"][0]["mitglied_name"] == "Elvira Dorn"


def test_b1_dienstplan_mitarbeiter_ohne_klarnamen(welt) -> None:
    """`api/dienstplan._resolve_mitarbeiter` ueber die gemeinsame Namensregel."""
    from diakronos_app.api.dienstplan import _resolve_mitarbeiter
    from diakronos_app.models.kronos import ElementMitarbeiter

    sess = welt
    sess.add(ElementMitarbeiter(
        name="EM-1", parent="E-1", parenttype="Element", parentfield="mitarbeiter",
        mitglied=ZIEL, dienstrolle=None, bestaetigt=1, docstatus=0, idx=1,
    ))
    sess.commit()
    _austritt()

    set_user(LESER)
    zeile = _resolve_mitarbeiter(["E-1"])["E-1"][0]
    assert zeile["mitglied_name"] == "Elvira D."
    set_user(ADMIN)
    assert _resolve_mitarbeiter(["E-1"])["E-1"][0]["mitglied_name"] == "Elvira Dorn"


def test_b1_planung_mitglied_name_ohne_klarnamen(welt) -> None:
    """`api/planung._mitglied_name` (Planuebersicht/Positionen)."""
    from diakronos_app.api.planung import _mitglied_name

    _austritt()
    set_user(LESER)
    assert _mitglied_name(ZIEL) == "Elvira D."
    set_user(ADMIN)
    assert _mitglied_name(ZIEL) == "Elvira Dorn"


def test_b1_verantwortliche_ohne_klarnamen(welt) -> None:
    """`api/verantwortliche` — Pflegezeilen und Personenauswahl."""
    from diakronos_app.api.verantwortliche import get_verantwortliche

    sess = welt
    sess.add(GruppeVerantwortlicher(
        name="GRV-1", parent="G-1", parenttype="Gruppe",
        parentfield="verantwortliche", user="ziel@x.org", docstatus=0, idx=1,
    ))
    sess.commit()
    _austritt()

    set_user(LESER)
    assert [z["anzeige"] for z in get_verantwortliche("Gruppe", "G-1")["verantwortliche"]] \
        == ["Elvira D."]
    set_user(ADMIN)
    assert [z["anzeige"] for z in get_verantwortliche("Gruppe", "G-1")["verantwortliche"]] \
        == ["Elvira Dorn"]


def test_b1_orgchart_ohne_klarnamen(welt) -> None:
    """`api/orgchart_api._sorted_member_rows` — `full_name` im Organigramm."""
    from diakronos_app.api.orgchart_api import _sorted_member_rows

    _austritt()
    zeilen = [{"parent": "G-1", "mitglied": ZIEL, "rolle": "Leitung"}]
    set_user(LESER)
    assert _sorted_member_rows(list(zeilen), "gruppe")[0]["full_name"] == "Elvira D."
    set_user(ADMIN)
    assert _sorted_member_rows(list(zeilen), "gruppe")[0]["full_name"] == "Elvira Dorn"


# ── B2: austritt_grund / vor_austritt_status im obersten Objekt ─────────────


def test_b2_detail_verbirgt_grund_und_vorstatus_auf_oberster_ebene(welt) -> None:
    """Der Review-Befund: geprueft war nur `daten["austritt"]`."""
    from diakronos_app.api.mitglieder import get_mitglied_detail

    _austritt(begruendung="Krankheit: Depression")
    set_user(LESER)
    daten = get_mitglied_detail(ZIEL)["data"]
    assert "Depression" not in repr(daten)
    assert daten.get("austritt_grund") is None
    assert daten.get("vor_austritt_status") is None
    assert daten["austritt"]["grund"] is None

    set_user(ADMIN)
    daten = get_mitglied_detail(ZIEL)["data"]
    assert daten["austritt_grund"] == "Krankheit: Depression"
    assert daten["austritt"]["grund"] == "Krankheit: Depression"


# ── B3: Mitgliederliste — nur Ausgetretene ausblenden ──────────────────────


def test_b3_ausgeschlossene_bleiben_in_der_liste_findbar(welt) -> None:
    """Ein Ausschluss („Passiver Gast") versteckt die Person NICHT mehr."""
    from diakronos_app.api.mitglieder import get_mitglieder_liste, schliesse_mitglied_aus

    sess = welt
    set_user(ADMIN)
    schliesse_mitglied_aus(ZIEL)
    sess.expire_all()
    assert sess.get(Mitglied, ZIEL).status == "Passiver Gast"

    namen = {z["name"] for z in get_mitglieder_liste()["data"]}
    assert ZIEL in namen
    assert ZIEL in {z["name"] for z in get_mitglieder_liste(status="Passiver Gast")["data"]}
    assert get_mitglieder_liste()["total"] == len(namen)


def test_b3_nur_ausgetretene_sind_standardmaessig_ausgeblendet(welt) -> None:
    """Gegenprobe: der Austritt blendet aus, der Ausschluss nicht."""
    from diakronos_app.api.mitglieder import get_mitglieder_liste

    _austritt()
    set_user(ADMIN)
    assert ZIEL not in {z["name"] for z in get_mitglieder_liste()["data"]}
    assert ZIEL in {z["name"] for z in get_mitglieder_liste(status="Ausgetreten")["data"]}


# ── B4: Zuteilbarkeit getrennt von der Anzeige ─────────────────────────────


def test_b4_ausgetretene_sind_fuer_niemanden_zuteilbar(welt) -> None:
    """Admin und Leser bekommen DIESELBE Kandidatenmenge."""
    from diakronos_app.db import SessionLocal
    from diakronos_app.planrahmen.datenquelle_db import DBDatenquelle

    _austritt()

    mengen = {}
    for wer in (ADMIN, LESER):
        set_user(wer)
        s = SessionLocal()
        try:
            mengen[wer] = {p.kennung for p in DBDatenquelle(s).personen()}
        finally:
            s.close()
    assert ZIEL not in mengen[ADMIN], "Admin bekommt die Ausgetretene angeboten"
    assert ZIEL not in mengen[LESER]
    assert mengen[ADMIN] == mengen[LESER], "Kandidatenmenge haengt von der Rolle ab"


def test_b4_kuerzung_aendert_die_planeingaben_nicht(welt) -> None:
    """Die Kuerzung ist Anzeige — Vor-/Nachname bleiben fachlich vollstaendig."""
    from diakronos_app.api.austritt import mitglied_reaktivieren
    from diakronos_app.db import SessionLocal
    from diakronos_app.planrahmen.datenquelle_db import DBDatenquelle

    _austritt()

    def person_von(wer: str):
        set_user(wer)
        s = SessionLocal()
        try:
            return next(p for p in DBDatenquelle(s)._quelle.personen()
                        if p.kennung == ZIEL)
        finally:
            s.close()

    staende = {wer: person_von(wer) for wer in (ADMIN, LESER)}

    # Fachliche Felder identisch — nur die ANZEIGE unterscheidet sich.
    assert staende[ADMIN].gruppen == staende[LESER].gruppen
    assert staende[ADMIN].merkmale == staende[LESER].merkmale
    assert staende[ADMIN].name == "Elvira Dorn"
    assert staende[LESER].name == "Elvira D."
    assert staende[LESER].vorname == "Elvira D."
    assert staende[LESER].nachname == ""

    set_user(ADMIN)
    mitglied_reaktivieren(ZIEL)
    # Nach dem Reaktivieren ist die Person wieder Kandidat und voll sichtbar.
    assert person_von(LESER).name == "Elvira Dorn"
    assert person_von(ADMIN).ausgeschieden is False


# ── M2: Reaktivieren lehnt „geloescht" und Nicht-Ausgetretene hart ab ──────


def test_m2_reaktivieren_lehnt_geloescht_ab(patched_db) -> None:
    """Anonymisierung ist nicht umkehrbar — auch nicht ueber den Endpunkt."""
    from diakronos_app.api.austritt import mitglied_reaktivieren

    sess = patched_db()
    _konto(sess, ADMIN, MA)
    _konto(sess, "ziel", vorname="Elvira", nachname="Dorn", konto="ziel@x.org")
    zeile = sess.get(Mitglied, ZIEL)
    zeile.status = "geloescht"
    zeile.ausgeschlossen = 1
    zeile.austritt_grund = "DSGVO"
    sess.commit()

    set_user(ADMIN)
    with pytest.raises(ValidationError) as fehler:
        mitglied_reaktivieren(ZIEL)
    assert "gel" in str(fehler.value).lower()
    sess.expire_all()
    assert sess.get(Mitglied, ZIEL).ausgeschlossen is True


def test_m2_reaktivieren_lehnt_nicht_ausgetretene_ab(welt) -> None:
    """Ein Ausschluss ist kein Austritt — dafuer gibt es den Status-Weg."""
    from diakronos_app.api.austritt import mitglied_reaktivieren
    from diakronos_app.api.mitglieder import schliesse_mitglied_aus

    sess = welt
    set_user(ADMIN)
    schliesse_mitglied_aus(ZIEL)
    with pytest.raises(ValidationError) as fehler:
        mitglied_reaktivieren(ZIEL)
    assert "usschluss" in str(fehler.value)
    sess.expire_all()
    assert sess.get(Mitglied, ZIEL).ausgeschlossen is True


# ── M3: Kurzname bei Beziehungen aus der ZIELPERSON ────────────────────────


def test_m3_beziehung_kuerzt_aus_der_zielperson(welt) -> None:
    """Vorher kam „E." heraus — die Beziehungszeile traegt keinen Vornamen."""
    from diakronos_app.api.mitglieder import _beziehungen_kuerzen
    from diakronos_app.frappe_compat.personen_anzeige import PersonenSicht

    sess = welt
    sess.add(MitgliedBeziehung(
        name="MBZ-leser-ziel", parent=f"M-{LESER}", parenttype="Mitglied",
        parentfield="beziehungen", beziehung_zu=ZIEL, beziehungstyp="Freund",
        docstatus=0, idx=1,
    ))
    sess.commit()
    _austritt()

    from diakronos_app.api.mitglieder import get_mitglied_detail

    set_user(LESER)
    zeilen = [{"beziehung_zu": ZIEL, "beziehung_zu_name": "Elvira Dorn"}]
    assert _beziehungen_kuerzen(zeilen, PersonenSicht.aus())[0]["beziehung_zu_name"] \
        == "Elvira D."
    # Gegenprobe ohne Sicht-Kuerzung darf nicht kuerzen (Admin), unduer die
    # Detailseite darf der Klarname nicht im Antwortkoerper stehen.
    detail = get_mitglied_detail(f"M-{LESER}")["data"]
    assert "Dorn" not in repr(detail.get("beziehungen") or [])

    # Der Admin bekommt die Zeile UNVERAENDERT zurueck (keine Kuerzung).
    zeile_admin = {"beziehung_zu": ZIEL, "beziehung_zu_name": "Elvira Dorn"}
    set_user(ADMIN)
    assert _beziehungen_kuerzen([zeile_admin], PersonenSicht.aus())[0] == zeile_admin


# ── N: Kleinkram aus dem Bericht ───────────────────────────────────────────


def test_n_begruendung_ist_optional(welt) -> None:
    """N1: A1 verlangt eine OPTIONALE Begruendung."""
    from diakronos_app.api.austritt import mitglied_austritt

    set_user(ADMIN)
    assert mitglied_austritt(ZIEL, "")["success"] is True
    sess = welt
    sess.expire_all()
    zeile = sess.get(Mitglied, ZIEL)
    assert zeile.status == "Ausgetreten"
    assert zeile.austritt_grund is None


def test_n_detail_maskiert_die_email_fuer_nicht_admin(welt) -> None:
    """N2: im Detail dieselbe Maske wie in der Liste."""
    from diakronos_app.api.mitglieder import get_mitglied_detail

    _austritt()
    set_user(LESER)
    assert get_mitglied_detail(ZIEL)["data"]["email"] == "zie*******.org"
    set_user(ADMIN)
    assert get_mitglied_detail(ZIEL)["data"]["email"] == "ziel@x.org"


def test_n_kuerzung_nur_fuer_ausgetretene(welt) -> None:
    """N3 (Fachentscheidung Operator): Ausgeschlossene bleiben voll sichtbar.

    AUSTRITT-e (NR1): Die Probe prueft wieder den NAMEN des Nicht-Admins —
    bisher stand hier nur der Austritts-Block, die Kuerzung selbst blieb
    ungeprueft. Zwei Personen, damit beide Faelle nebeneinander stehen:
    ``ziel`` wird ausgeschlossen, ``ziel2`` tritt aus. „Austritt nach
    Ausschluss“ ist abgelehnt (NH1), „Reaktivieren“ einer Ausgeschlossenen
    ebenfalls (M2) — also kein Hin und Her in einer Probe.
    """
    from diakronos_app.api.austritt import mitglied_austritt
    from diakronos_app.api.mitglieder import get_mitglied_detail, schliesse_mitglied_aus

    sess = welt
    sess.add(Mitglied(
        name="M-ziel2", vorname="Elvira", nachname="Dorn",
        email="ziel2@x.org", status="Mitglied",
        ausgeschlossen=0, docstatus=0, idx=0,
        # Derselbe Pfad wie die uebrigen Personen der Fixture: die
        # Sichtbarkeitsregel (nicht die Kuerzung) haengt daran.
        ancestor_path="/G-1/|/DB-A/",
    ))
    sess.commit()

    set_user(ADMIN)
    schliesse_mitglied_aus(ZIEL)
    mitglied_austritt("M-ziel2", "", "2026-10-01")
    sess.expire_all()

    set_user(LESER)
    # Ausgeschlossen: KEINE Kuerzung — der Klarname steht im Koerper.
    daten = get_mitglied_detail(ZIEL)["data"]
    assert daten["austritt"]["ausgetreten"] is True
    assert daten["austritt"]["grund"] is None
    assert daten.get("austritt_grund") is None
    assert (daten["vorname"], daten["nachname"]) == ("Elvira", "Dorn")

    # Ausgetreten: derselbe Leser sieht die Kurzform.
    kurz = get_mitglied_detail("M-ziel2")["data"]
    assert kurz["vorname"] == "Elvira D."
    assert kurz["nachname"] is None
    assert "Dorn" not in repr(kurz)


def test_n_caldav_nach_austritt_abgewiesen_und_nach_reaktivieren_offen(welt) -> None:
    """N7: CalDAV prüft das Konto — Austritt zu, Reaktivieren wieder auf."""
    from diakronos_app.api.austritt import mitglied_reaktivieren
    from diakronos_app.caldav.auth import _check_credentials

    _austritt()
    from diakronos_app.frappe_compat import benutzer_status

    # Nach dem Austritt ist der Widerruf gelaufen (`widerrufe_sitzungen`).
    benutzer_status.vergiss("ziel@x.org")
    assert _check_credentials("ziel@x.org", "egal") is False
    assert benutzer_status.ist_aktiv("ziel@x.org") is False, "Austritt sperrt das Konto"
    set_user(ADMIN)
    mitglied_reaktivieren(ZIEL)
    # Reaktivieren vergisst den Cache (`vergiss`); danach liest die Pruefung
    # wieder die Datenbank — das Konto ist frei, auch ohne Passwort.
    assert benutzer_status.ist_aktiv("ziel@x.org") is True
    assert _check_credentials("ziel@x.org", "egal") is False, (
        "weiterhin kein Login — aber wegen des fehlenden Passworts, nicht wegen "
        "des Austritts")


def test_n_docstring_ohne_erfundene_funktion() -> None:
    """N6: kein Verweis auf eine nicht existierende Funktion."""
    import inspect

    from diakronos_app.api import austritt

    quelle = inspect.getsource(austritt)
    assert "_pruefe_austritt" not in quelle
    assert "wird deshalb vor der Pruefung geschrieben? Nein" not in quelle

def test_b1_konto_freitext_ohne_klarnamen(welt) -> None:
    """Zusatzbefund aus dem grep-Sweep der Karte (B1 „weitere Stellen“).

    Die Personenlisten in `api/zugang.py` zeigen den FREITEXT `User.full_name`
    — im Betrieb steht dort der Klarname des Mitglieds. Die Kuerzung an
    `Mitglied` allein erfasst diesen Weg nicht.

    Der Endpunkt ist Administratoren vorbehalten — die Kuerzung greift
    deshalb an zwei Stellen: die „anzeige“ stammt aus dem (gekuerzten)
    Mitglied, und wo nur der Konto-Freitext bleibt (Konto ohne lesbare
    Mitgliedszeile), kuerzt `_konto_name` ihn ueber die zentrale Regel.
    """
    from diakronos_app.api import zugang
    from diakronos_app.db import SessionLocal
    from diakronos_app.models.core import User

    sess = SessionLocal()
    try:
        sess.get(User, "ziel@x.org").full_name = "Elvira Dorn"
        sess.commit()
    finally:
        sess.close()
    _austritt()

    set_user(ADMIN)
    zeilen = zugang.get_rollen_uebersicht()["konten"]
    assert "Elvira Dorn" in {z["anzeige"] for z in zeilen}
    # Weg 2: derselbe Freitext ueber den zentralen Helfer (die drei
    # Konto-Listen rufen ihn so auf) — ein ausgeschiedenes Konto zeigt dort
    # die Kurzform, ein aktives den Klarnamen.
    assert zugang._konto_name("Elvira Dorn", "ziel@x.org", ausgeschieden=True) == "Elvira D."
    assert zugang._konto_name("Elvira Dorn", "ziel@x.org", ausgeschieden=False) == "Elvira Dorn"
    # Die Regel kommt aus `benutzer_status` (eine Wahrheit), nicht aus einer
    # zweiten Aufloesung im Modul. AUSTRITT-d (NM2): die Frage lautet
    # „ausgetreten?“ — die Marke allein traegt auch den Ausschluss.
    from diakronos_app.frappe_compat import benutzer_status

    mitglieder, konten = benutzer_status._kontozustand()
    assert "ziel@x.org" in benutzer_status.ausgetretene_konten(mitglieder, konten)
