"""P1-9 — Mitglieder-Kern: Nachweis-Tests fuer die Reparaturen.

Deckt die Befunde der Nachtpruefung ab (GESAMTBERICHT, Paket P1-9):
  UXD-R6  Leeres Geburtsdatum (SPA sendet '') liess Speichern/Leeren scheitern.
  UXD-R8  Zu lange Eingaben ergaben rohe DB-Fehler.
  UXD-R15 Anlegen/Status/Ausschliessen ueber die API (create_mitglied-Validierung).
  UXD-R24 Pflichtfelder + E-Mail-Format.
  OP-ADMIN-7 Genehmigen erkennt Dubletten (gleiche E-Mail).
  OP-ADMIN-8 Anmeldungs-Details liefern Telefon/Geburtstag/Kommentar.

Jeder Test ist zuerst rot gelaufen (Reproduktion) und danach gruen.
"""

from __future__ import annotations

import json
from typing import Any

import pytest


@pytest.fixture()
def rollen(monkeypatch):
    """Admin-Rollen fuer die Mitglieder-Endpunkte (Muster test_mitglieder_p4k).

    `admin_hub` bindet `get_roles`/`is_guest` per `from ... import` — dort
    greift ein Patch auf `permissions` allein nicht, deshalb mitpatchen.
    """
    from diakronos_app.api import admin_hub, mitglieder
    from diakronos_app.frappe_compat import permissions

    halt: dict[str, Any] = {"roles": ["Mitgliederadministrator"], "user": "admin@example.org"}
    hole = lambda user=None: list(halt["roles"])  # noqa: E731
    kein_gast = lambda user=None: False  # noqa: E731
    for mod in (permissions, mitglieder, admin_hub):
        if hasattr(mod, "get_roles"):
            monkeypatch.setattr(mod, "get_roles", hole)
        if hasattr(mod, "is_guest"):
            monkeypatch.setattr(mod, "is_guest", kein_gast)
    monkeypatch.setattr(mitglieder, "_is_admin", lambda: True)
    return halt


@pytest.fixture()
def sess(patched_db):
    s = patched_db()
    yield s
    s.close()


# ── UXD-R6: Geburtstag '' -> NULL ───────────────────────────────────────────


def test_update_mitglied_leeres_geburtsdatum_wird_null(client, seed_mitglieder, rollen, sess):
    """UXD-R6: Ein Mitglied ohne Geburtstag (11 von 24) laesst sich speichern."""
    from diakronos_app.models.diakonos import Mitglied

    m = sess.get(Mitglied, "M-0001")
    assert m.geburtstag is None

    r = client.post(
        "/api/method/mitglieder.update_mitglied",
        json={"mitglied_id": "M-0001", "data": json.dumps({"telefonnummer": "0700", "geburtstag": ""})},
    )
    assert r.status_code == 200, r.text
    sess.expire_all()
    m2 = sess.get(Mitglied, "M-0001")
    assert m2.telefonnummer == "0700"
    assert m2.geburtstag is None


def test_update_mitglied_geburtsdatum_laesst_sich_leeren(client, seed_mitglieder, rollen, sess):
    """UXD-R6: Nach dem Setzen laesst sich der Geburtstag wieder leeren."""
    from diakronos_app.models.diakonos import Mitglied

    m = sess.get(Mitglied, "M-0001")
    m.geburtstag = __import__("datetime").date(1975, 3, 14)
    sess.commit()

    r = client.post(
        "/api/method/mitglieder.update_mitglied",
        json={"mitglied_id": "M-0001", "data": json.dumps({"geburtstag": ""})},
    )
    assert r.status_code == 200, r.text
    sess.expire_all()
    assert sess.get(Mitglied, "M-0001").geburtstag is None


# ── UXD-R8: zu lange Eingaben -> Klartext statt SQL ─────────────────────────


def test_update_mitglied_zu_lange_eingabe_klartext(client, seed_mitglieder, rollen):
    """UXD-R8: 200 Zeichen im Ort ergeben eine verstaendliche Meldung, kein SQL."""
    r = client.post(
        "/api/method/mitglieder.update_mitglied",
        json={"mitglied_id": "M-0001", "data": json.dumps({"wohnort": "x" * 200})},
    )
    assert r.status_code >= 400
    text = r.text
    assert "SQL" not in text and "psycopg" not in text and "parameters" not in text
    assert "zu lang" in text.lower()


def test_create_mitglied_zu_langer_nachname_klartext(client, seed_mitglieder, rollen):
    r = client.post(
        "/api/method/mitglieder.create_mitglied",
        json={"vorname": "A", "nachname": "n" * 141},
    )
    assert r.status_code >= 400
    assert "SQL" not in r.text and "psycopg" not in r.text
    assert "zu lang" in r.text.lower()


# ── UXD-R24: Pflichtfelder + E-Mail-Format ──────────────────────────────────


def test_create_mitglied_verlangt_namen(client, seed_mitglieder, rollen):
    r = client.post(
        "/api/method/mitglieder.create_mitglied",
        json={"vorname": "  ", "nachname": ""},
    )
    assert r.status_code >= 400
    assert "pflicht" in r.text.lower()


def test_create_mitglied_weist_ungueltige_email_ab(client, seed_mitglieder, rollen):
    r = client.post(
        "/api/method/mitglieder.create_mitglied",
        json={"vorname": "Egon", "nachname": "Eilig", "email": "keine-mail"},
    )
    assert r.status_code >= 400
    assert "gültige E-Mail" in r.text


def test_create_mitglied_weist_doppelte_email_ab(client, seed_mitglieder, rollen):
    """UXD-R15/OP-ADMIN-7: dieselbe E-Mail wird nicht zweimal Mitglied."""
    r = client.post(
        "/api/method/mitglieder.create_mitglied",
        json={"vorname": "Anna", "nachname": "Zweit", "email": "anna@example.org"},
    )
    assert r.status_code >= 400
    assert "bereits" in r.text.lower()


def test_create_mitglied_normalisiert_email_zu_kleinbuchstaben(client, seed_mitglieder, rollen, sess):
    from diakronos_app.models.diakonos import Mitglied

    r = client.post(
        "/api/method/mitglieder.create_mitglied",
        json={"vorname": "Neo", "nachname": "Neu", "email": "Neo.Neu@Example.ORG", "status": "Mitglied"},
    )
    assert r.status_code == 200, r.text
    mid = r.json()["message"]["mitglied_id"]
    sess.expire_all()
    assert sess.get(Mitglied, mid).email == "neo.neu@example.org"


def test_create_mitglied_akzeptiert_leeres_geburtsfeld(client, seed_mitglieder, rollen):
    """Ein Mitglied ohne Angaben (nur Name) bleibt anlegbar."""
    r = client.post(
        "/api/method/mitglieder.create_mitglied",
        json={"vorname": "Ohne", "nachname": "Alles", "email": ""},
    )
    assert r.status_code == 200, r.text


# ── OP-ADMIN-7: Dublettenpruefung beim Genehmigen ───────────────────────────


def _anmeldung(sess, name, **werte):
    from diakronos_app.models.diakonos import Anmeldung

    a = Anmeldung(
        name=name,
        vorname=werte.get("vorname", "Dup"),
        nachname=werte.get("nachname", "Likate"),
        email=werte.get("email", ""),
        telefon=werte.get("telefon", ""),
        geburtstag=werte.get("geburtstag"),
        kommentar=werte.get("kommentar", ""),
        status="Anmeldeanfrage",
        anmeldungstyp=werte.get("anmeldungstyp", "Mitglied-Registrierung"),
        verarbeitet=0,
    )
    sess.add(a)
    sess.commit()
    return name


def test_genehmigen_warnung_bei_dublette(client, seed_mitglieder, rollen, sess):
    """OP-ADMIN-7: gleiche E-Mail wie ein bestehendes Mitglied -> Warnung, KEIN neues Mitglied."""
    from diakronos_app.models.diakonos import Mitglied

    _anmeldung(sess, "A-DUP1", email="anna@example.org")
    vorher = sess.query(Mitglied).count()

    r = client.post(
        "/api/method/admin_hub.genehmige_anmeldung",
        json={"anmeldung_id": "A-DUP1"},
    )
    assert r.status_code >= 400
    assert "bereits" in r.text.lower() or "dublette" in r.text.lower()
    sess.expire_all()
    assert sess.query(Mitglied).count() == vorher


def test_genehmigen_ohne_dublette_legt_mitglied_an(client, seed_mitglieder, rollen, sess):
    from diakronos_app.models.diakonos import Mitglied

    _anmeldung(sess, "A-OK1", email="neu@example.org", vorname="Neu", nachname="Person")
    vorher = sess.query(Mitglied).count()

    r = client.post(
        "/api/method/admin_hub.genehmige_anmeldung",
        json={"anmeldung_id": "A-OK1"},
    )
    assert r.status_code == 200, r.text
    sess.expire_all()
    assert sess.query(Mitglied).count() == vorher + 1


def test_genehmigen_dublette_auch_mit_kraft_nicht_angelegt(client, seed_mitglieder, rollen, sess):
    """SEC-b: Auch MIT Bestaetigung entsteht keine zweite Person je Adresse.

    Fachentscheidung (Manuel 2026-10-19): Jede Person hat eine eigene
    E-Mail-Adresse; Familienpostfaecher gibt es nicht mehr. Die Freigabe einer
    Anmeldung mit bereits belegter Adresse wird deshalb IMMER abgelehnt — auch
    mit `dublette_bestaetigt`. Die Meldung nennt den Grund in Klartext.
    """
    from diakronos_app.models.diakonos import Mitglied

    _anmeldung(sess, "A-DUP2", email="anna@example.org")
    vorher = sess.query(Mitglied).count()

    r = client.post(
        "/api/method/admin_hub.genehmige_anmeldung",
        json={"anmeldung_id": "A-DUP2", "dublette_bestaetigt": True},
    )
    assert r.status_code == 417, r.text
    assert "bereits" in r.json()["message"]
    sess.expire_all()
    assert sess.query(Mitglied).count() == vorher  # nichts angelegt


# ── OP-ADMIN-8: Anmeldungs-Details vollstaendig ─────────────────────────────


def test_anmeldungen_hub_liefert_kontaktfelder(client, seed_mitglieder, rollen, sess):
    """OP-ADMIN-8: Telefon, Geburtstag, Kommentar kommen mit."""
    import datetime

    _anmeldung(
        sess, "A-DET1",
        telefon="0151 2345678",
        geburtstag=datetime.date(1975, 3, 14),
        kommentar="Gruppe laut Liste: Chor",
    )

    r = client.post("/api/method/admin_hub.get_anmeldungen_hub")
    assert r.status_code == 200, r.text
    eintrag = next(a for a in r.json()["message"]["anmeldungen"] if a["name"] == "A-DET1")
    assert eintrag["telefon"] == "0151 2345678"
    assert str(eintrag["geburtstag"]).startswith("1975-03-14")
    assert eintrag["kommentar"] == "Gruppe laut Liste: Chor"


# ── UXD-R15: Status setzen / ausschliessen (Backend) ────────────────────────


def test_set_mitglied_status_aendert_status(client, seed_mitglieder, rollen, sess):
    from diakronos_app.models.diakonos import Mitglied

    r = client.post(
        "/api/method/mitglieder.set_mitglied_status",
        json={"mitglied_id": "M-0001", "status": "Passives Mitglied"},
    )
    assert r.status_code == 200, r.text
    sess.expire_all()
    assert sess.get(Mitglied, "M-0001").status == "Passives Mitglied"


def test_set_mitglied_status_weist_ungueltigen_status_ab(client, seed_mitglieder, rollen, sess):
    from diakronos_app.models.diakonos import Mitglied

    r = client.post(
        "/api/method/mitglieder.set_mitglied_status",
        json={"mitglied_id": "M-0001", "status": "Kind"},
    )
    assert r.status_code >= 400
    assert "unbekannter status" in r.text.lower()
    sess.expire_all()
    assert sess.get(Mitglied, "M-0001").status == "Mitglied"


def test_schliesse_mitglied_aus_setzt_merkmal_und_datum(client, seed_mitglieder, rollen, sess):
    from diakronos_app.models.diakonos import Mitglied

    r = client.post(
        "/api/method/mitglieder.schliesse_mitglied_aus",
        json={"mitglied_id": "M-0001", "begruendung": "Austritt"},
    )
    assert r.status_code == 200, r.text
    sess.expire_all()
    m = sess.get(Mitglied, "M-0001")
    assert m.ausgeschlossen is True
    assert m.ausgeschlossen_seit is not None
    assert m.status == "Passiver Gast"


# ── Import (Backend; Oberflaeche in N11) ────────────────────────────────────

_IMPORT_CSV = (
    "Vorname;Nachname;E-Mail;Telefon;Geburtsdatum;Straße;PLZ;Ort;Gruppe\n"
    "Neu;Person;neu.import@example.org;0151 1;14.03.1975;Hauptstr. 5;71691;Freiberg;Chor\n"
    "Anna;Beispiel;anna@example.org;;;Straße 1;70173;Stuttgart;\n"
    ";Ohne-Vorname;;;                      ;;       ;;\n"
    "Kaputt;Datum;k.datum@example.org;;31.02.1990;;;;\n"
)


#: Dieselbe Liste OHNE die fehlerhaften Zeilen (SEC, W1/W2, Befund).
#: `import_mitglieder_uebernehmen` hat die fehlerhaften Zeilen immer schon
#: uebersprungen (`abgelehnt > 0`, Status 200) — der Import ist „eine Zeile,
#: ein Ergebnis“, kein alles-oder-nichts. Die Fassung mit den Fehlerzeilen
#: steht in `test_sec_ausschluss.py` (dort ueber die Vorschau + Klartext).
_IMPORT_CSV_OK = (
    "Vorname;Nachname;E-Mail;Telefon;Geburtsdatum;Straße;PLZ;Ort;Gruppe\n"
    "Neu;Person;neu.import@example.org;0151 1;14.03.1975;Hauptstr. 5;71691;Freiberg;Chor\n"
    "Anna;Beispiel;anna@example.org;;;Straße 1;70173;Stuttgart;\n"
)


def test_import_vorschau_meldet_neu_dublette_fehler(client, seed_mitglieder, rollen):
    r = client.post(
        "/api/method/mitglieder.import_mitglieder_vorschau",
        json={"csv_inhalt": _IMPORT_CSV},
    )
    assert r.status_code == 200, r.text
    msg = r.json()["message"]
    zus = msg["zusammenfassung"]
    assert zus["gesamt"] == 4
    assert zus["neu"] == 1
    # SEC-c (K-c): eine vergebene ADRESSE ist eine Fehlerzeile, keine Dublette.
    # Fehler = Anna (Adresse vergeben), fehlender Vorname, ungueltiges Datum.
    assert zus["fehler"] >= 3
    anna = next(z for z in msg["zeilen"] if z["felder"].get("email") == "anna@example.org")
    assert anna["status"] == "fehler", anna


def test_import_uebernehmen_legt_neue_an_und_ueberspringt_dubletten(client, seed_mitglieder, rollen, sess):
    from diakronos_app.models.diakonos import Mitglied

    vorher = sess.query(Mitglied).count()
    r = client.post(
        "/api/method/mitglieder.import_mitglieder_uebernehmen",
        json={"csv_inhalt": _IMPORT_CSV_OK},
    )
    assert r.status_code == 200, r.text
    msg = r.json()["message"]
    assert msg["angelegt"] == 1
    # SEC-c (K-c): die Zeile mit der vergebenen Adresse ist ABGELEHNT (nicht
    # uebersprungen) — die Vorschau zeigt sie als Fehler, der Import ebenso.
    assert msg["abgelehnt"] == 1
    assert msg["uebersprungen"] == 0
    sess.expire_all()
    assert sess.query(Mitglied).count() == vorher + 1


def test_import_vorschau_und_uebernehmen_stimmen_ueberein(
    client, seed_mitglieder, rollen, sess,
):
    """SEC (W1/K4): Was die Vorschau ablehnt, darf nicht still angelegt werden.

    Vorher war das ein Auseinanderlaufen, das niemand sah: die Vorschau zeigte
    „fehler“, der Import uebernahm die Zeile trotzdem.
    """
    from diakronos_app.models.diakonos import Mitglied

    vorschau = client.post(
        "/api/method/mitglieder.import_mitglieder_vorschau",
        json={"csv_inhalt": _IMPORT_CSV},
    ).json()["message"]
    vorher = sess.query(Mitglied).count()
    r = client.post(
        "/api/method/mitglieder.import_mitglieder_uebernehmen",
        json={"csv_inhalt": _IMPORT_CSV},
    )
    assert r.status_code == 200, r.text
    msg = r.json()["message"]
    sess.expire_all()
    abgelehnt_in_datei = sum(1 for z in vorschau["zeilen"] if z["status"] == "fehler")
    assert msg["abgelehnt"] == abgelehnt_in_datei
    assert sess.query(Mitglied).count() == vorher + msg["angelegt"]


def test_import_nur_admin(client, seed_mitglieder, monkeypatch, sess):
    """Ohne Admin-Recht ist der Import gesperrt (fail closed)."""
    from diakronos_app.api import mitglieder
    from diakronos_app.frappe_compat import permissions

    monkeypatch.setattr(mitglieder, "_is_admin", lambda: False)
    monkeypatch.setattr(permissions, "is_guest", lambda user=None: False)
    r = client.post(
        "/api/method/mitglieder.import_mitglieder_vorschau",
        json={"csv_inhalt": _IMPORT_CSV},
    )
    assert r.status_code >= 400


# ── P1-9b: Grenzen, Laengen, Dubletten in der Datei (Befund 3/4/5) ──────────


def test_import_groesse_abgewiesen(client, seed_mitglieder, rollen):
    """Befund 3: >1 MB CSV wird abgewiesen, NICHT geparst."""
    grosse = "Vorname;Nachname;E-Mail\n" + "A;B;c@example.org\n" * 60000
    assert len(grosse.encode("utf-8")) > 1_000_000
    r = client.post(
        "/api/method/mitglieder.import_mitglieder_vorschau",
        json={"csv_inhalt": grosse},
    )
    assert r.status_code >= 400, r.text
    assert "zu groß" in r.text.lower() or "groß" in r.text.lower()


def test_import_zeilengrenze_abgewiesen(client, seed_mitglieder, rollen):
    """Befund 3: mehr als 2000 Datenzeilen werden abgewiesen."""
    viele = "Vorname;Nachname;E-Mail\n" + "A;B;c@example.org\n" * 2100
    r = client.post(
        "/api/method/mitglieder.import_mitglieder_vorschau",
        json={"csv_inhalt": viele},
    )
    assert r.status_code >= 400, r.text
    assert "zeilen" in r.text.lower()


def test_import_uebernehmen_grenze_abgewiesen(client, seed_mitglieder, rollen):
    """Befund 3: die Grenze greift auch beim Uebernehmen (nicht nur Vorschau)."""
    viele = "Vorname;Nachname;E-Mail\n" + "A;B;c@example.org\n" * 2100
    r = client.post(
        "/api/method/mitglieder.import_mitglieder_uebernehmen",
        json={"csv_inhalt": viele},
    )
    assert r.status_code >= 400, r.text


def test_import_laengenpruefung_alle_felder(client, seed_mitglieder, rollen, sess):
    """Befund 4: eine zu lange Adress-/Telefonzelle wird VOR dem Schreiben
    abgelehnt (vorher DB-Fehler mitten im Lauf)."""
    from diakronos_app.models.diakonos import Mitglied

    csv = (
        "Vorname;Nachname;E-Mail;Telefon;Straße;PLZ;Ort\n"
        "Gut;Person;gut.p1@example.org;0151;;;;\n"
        "Schlecht;Person;schlecht.p1@example.org;" + "0" * 200 + ";;;;\n"
    )
    vorher = sess.query(Mitglied).count()
    r = client.post(
        "/api/method/mitglieder.import_mitglieder_uebernehmen",
        json={"csv_inhalt": csv},
    )
    assert r.status_code == 200, r.text
    msg = r.json()["message"]
    # Die lange Zeile wird abgelehnt, nicht halb angelegt.
    assert msg["abgelehnt"] >= 1
    assert msg["angelegt"] == 1
    sess.expire_all()
    assert sess.query(Mitglied).count() == vorher + 1


def test_import_dublette_innerhalb_der_datei(client, seed_mitglieder, rollen, sess):
    """Befund 5: zwei gleiche E-Mails IN der Datei -> die zweite ist Dublette.

    SEC-c (K-c): die zweite Zeile ist eine FEHLERZEILE (der Server lehnt sie
    ab) — eine Person je Adresse laesst sich nicht „trotzdem anlegen“. Die
    erste Zeile wird angelegt.
    """
    from diakronos_app.models.diakonos import Mitglied

    csv = (
        "Vorname;Nachname;E-Mail\n"
        "Zwilling;Eins;zwilling.p1@example.org\n"
        "Zwilling;Zwei;zwilling.p1@example.org\n"
    )
    vorher = sess.query(Mitglied).count()
    r = client.post(
        "/api/method/mitglieder.import_mitglieder_uebernehmen",
        json={"csv_inhalt": csv},
    )
    assert r.status_code == 200, r.text
    msg = r.json()["message"]
    assert msg["angelegt"] == 1, msg
    assert msg["abgelehnt"] == 1, msg
    assert "Datei" in msg["zeilen"][1]["fehler"][0], msg
    sess.expire_all()
    assert sess.query(Mitglied).count() == vorher + 1


def test_import_dublette_ohne_bestaetigung_abgelehnt(client, seed_mitglieder, rollen, sess):
    """Befund 5: Dubletten ohne ausdrueckliche Bestaetigung -> Ablehnung.

    SEC-c (K-c): eine vergebene ADRESSE ist bereits in der Vorschau eine
    FEHLERZEILE — sie wird abgelehnt (nichts angelegt), der Lauf laeuft als
    solcher aber durch (200) und meldet die Zeile.
    """
    from diakronos_app.models.diakonos import Mitglied

    vorher = sess.query(Mitglied).count()
    r = client.post(
        "/api/method/mitglieder.import_mitglieder_uebernehmen",
        json={
            "csv_inhalt": _IMPORT_CSV,
            "dubletten_ueberspringen": False,
            "bestaetigt": 0,
        },
    )
    assert r.status_code == 200, r.text
    msg = r.json()["message"]
    assert msg["angelegt"] == 1, msg  # nur die fehlerfreie Zeile (Neu Person)
    sess.expire_all()
    assert sess.query(Mitglied).count() == vorher + 1


def test_import_dublette_auch_mit_bestaetigung_nicht_angelegt(client, seed_mitglieder, rollen, sess):
    """SEC-b: Auch MIT Bestaetigung entsteht keine zweite Person je Adresse.

    Fachentscheidung (Manuel 2026-10-19): Jede Person hat eine eigene
    E-Mail-Adresse. Das frueher hier gewaehrte „Dublette bestaetigen“ ist
    damit aufgehoben.

    SEC-c (K-c, Befund): Die Zeile wird ABGELEHNT (HTTP 200, Zeile
    `abgelehnt` mit Klartext), statt den GANZEN Lauf mit 417 abzubrechen. Die
    Oberflaeche sagt „der Server lehnt Zeilen ab“ — und die uebrigen Zeilen
    eines solchen Imports sollen angelegt werden koennen.
    """
    from diakronos_app.models.diakonos import Mitglied

    csv = "Vorname;Nachname;E-Mail\nDup;Likat;anna@example.org\n"
    vorher = sess.query(Mitglied).count()
    r = client.post(
        "/api/method/mitglieder.import_mitglieder_uebernehmen",
        json={"csv_inhalt": csv, "dubletten_ueberspringen": False, "bestaetigt": 1},
    )
    assert r.status_code == 200, r.text
    msg = r.json()["message"]
    assert msg["angelegt"] == 0, msg
    assert msg["abgelehnt"] == 1, msg
    assert "bereits" in msg["zeilen"][0]["fehler"][0], msg
    sess.expire_all()
    assert sess.query(Mitglied).count() == vorher  # nichts angelegt


# ── P1-9b: CSV-Export (Befund 2) ────────────────────────────────────────────


def test_export_entschaerft_formelzellen(client, seed_mitglieder, rollen, sess):
    """Befund 2: Zellen mit =,+,-,@ werden mit ' entschaerft."""
    from diakronos_app.models.diakonos import Mitglied

    sess.add(Mitglied(
        name="M-P1B1", vorname="=cmd|calc", nachname="Person",
        email="p1b@example.org", status="Mitglied",
    ))
    sess.commit()

    r = client.post(
        "/api/method/mitglieder.exportiere_mitglieder_csv",
        json={"suche": "p1b"},
    )
    assert r.status_code == 200, r.text
    csv = r.json()["message"]["csv"]
    assert "'=cmd|calc" in csv, csv
    # Keine ungeschuetzte Formelzelle.
    assert "=cmd|calc" not in csv.replace("'=cmd|calc", "")


def test_export_umfasst_alle_nicht_nur_geladene(client, seed_mitglieder, rollen, sess):
    """Befund 2: Export ist die Gesamtliste, nicht die erste Seite."""
    from diakronos_app.models.diakonos import Mitglied

    # AUSTRITT A5/b (B3): Der Export folgt derselben Sichtbarkeit wie die
    # Liste — Ausgetretene stehen erst hinter dem Statusfilter „Ausgetreten“,
    # also ist die Grundmenge hier die Zahl der NICHT Ausgetretenen.
    vorher = sess.query(Mitglied).filter(Mitglied.status != "Ausgetreten").count()
    r = client.post("/api/method/mitglieder.exportiere_mitglieder_csv", json={})
    assert r.status_code == 200, r.text
    msg = r.json()["message"]
    assert msg["anzahl"] == vorher, (msg["anzahl"], vorher)
    # Kopfzeile + je Mitglied eine Zeile. Die Datei endet mit dem
    # Zeilenumbruch der letzten Zeile (csv.writer) — deshalb zaehlen die
    # nicht-leeren Zeilen, nicht die Stuecke des Splits (N11, Neu A).
    assert len([z for z in msg["csv"].split("\r\n") if z]) == vorher + 1


def test_export_nur_admin(client, seed_mitglieder, monkeypatch):
    """Befund 2: Export ist Administratoren vorbehalten (fail closed)."""
    from diakronos_app.api import mitglieder
    from diakronos_app.frappe_compat import permissions

    monkeypatch.setattr(mitglieder, "_has_admin_role", lambda user, roles=None: False)
    monkeypatch.setattr(permissions, "is_guest", lambda user=None: False)
    r = client.post("/api/method/mitglieder.exportiere_mitglieder_csv", json={})
    assert r.status_code >= 400


# ── P1-9b: Dublettenhinweis serverseitig (Befund 6) ─────────────────────────


def test_anmeldungen_hub_meldet_email_vorhanden(client, seed_mitglieder, rollen, sess):
    """Befund 6: der Server liefert je Anmeldung `email_vorhanden`."""
    _anmeldung(sess, "A-HUB1", email="anna@example.org")   # existiert
    _anmeldung(sess, "A-HUB2", email="ganz.neu@example.org")  # neu

    r = client.post("/api/method/admin_hub.get_anmeldungen_hub")
    assert r.status_code == 200, r.text
    nach_name = {a["name"]: a for a in r.json()["message"]["anmeldungen"]}
    assert nach_name["A-HUB1"]["email_vorhanden"] == 1
    assert nach_name["A-HUB2"]["email_vorhanden"] == 0


def test_genehmigen_dublette_gross_klein_unabhaengig(client, seed_mitglieder, rollen, sess):
    """Befund 6: Bestands-E-Mail mit Grossbuchstaben wird erkannt."""
    from diakronos_app.models.diakonos import Mitglied

    sess.add(Mitglied(
        name="M-P1B2", vorname="Max", nachname="Gross",
        email="Max.Gross@Example.ORG", status="Mitglied",
    ))
    sess.commit()
    _anmeldung(sess, "A-CASE1", email="max.gross@example.org")
    vorher = sess.query(Mitglied).count()

    r = client.post(
        "/api/method/admin_hub.genehmige_anmeldung",
        json={"anmeldung_id": "A-CASE1"},
    )
    assert r.status_code >= 400, r.text
    sess.expire_all()
    assert sess.query(Mitglied).count() == vorher


# ── P1-9b: Audit-Log Status/Ausschluss (Befund 7) ───────────────────────────


def test_status_aenderung_wird_protokolliert(client, seed_mitglieder, rollen, sess):
    """Befund 7: set_mitglied_status schreibt einen Audit-Eintrag."""
    from diakronos_app.models.diakonos import AuditLog

    r = client.post(
        "/api/method/mitglieder.set_mitglied_status",
        json={"mitglied_id": "M-0001", "status": "Gast"},
    )
    assert r.status_code == 200, r.text
    sess.expire_all()
    eintraege = sess.query(AuditLog).filter(
        AuditLog.target_name == "M-0001",
        AuditLog.target_doctype == "Mitglied",
    ).all()
    assert any("status" in (e.field_changed or "").lower()
               for e in eintraege), [(e.field_changed, e.new_value) for e in eintraege]


def test_ausschluss_ohne_begruendung_wird_protokolliert(client, seed_mitglieder, rollen, sess):
    """Befund 7: der Ausschluss selbst ist der Eintrag (nicht der Freitext)."""
    from diakronos_app.models.diakonos import AuditLog

    r = client.post(
        "/api/method/mitglieder.schliesse_mitglied_aus",
        json={"mitglied_id": "M-0001"},
    )
    assert r.status_code == 200, r.text
    sess.expire_all()
    eintraege = sess.query(AuditLog).filter(
        AuditLog.target_name == "M-0001",
        AuditLog.target_doctype == "Mitglied",
    ).all()
    assert any((e.field_changed or "") == "ausgeschlossen" for e in eintraege), \
        [(e.field_changed, e.old_value, e.new_value) for e in eintraege]


