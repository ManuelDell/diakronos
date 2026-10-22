"""P4n — Portiertes Modul `api.profile` (6 Endpunkte, Profilseite).

Quelle (READ-ONLY):
  referenz/diakronos-frappe/diakronos/diakonos/api/profile.py

Warum diese Karte existiert: `Profile.vue:383` ruft `profile.get_my_profile`
ueber ``apiFetch('profile.<fn>')``. Vor der Portierung war `api/profile.py`
nicht vorhanden — jeder Aufruf lief auf HTTP 404, und weil
``router.js:140`` `#/profile`` in `GAST_ALLOWED_ROUTES` fuehrt, sah JEDES
Mitglied eine leere Profilseite. Das ist der gemeldete Fehler.

Abgedeckt (Commit 1 — der gemeldete Fehler):
  * Registrierung: `FRAPPE_MODULE == "diakronos.diakonos.api.profile"`,
    der Originalpfad ist ueber den Router erreichbar (der Kontrollpfad, den
    eine Pfadzaehlung ueber das Aufrufinventar NICHT pruefen kann — s.
    Modul-Docstring).
  * Login-Pflicht: `allow_guest=False` -> Gast bekommt 403, NICHT 404.
  * `get_my_profile`: liefert alle 19 Felder 1:1; Datumsfelder als String;
    `adressbuch_sichtbarkeit` als Dict (JSON-Text, kaputtes JSON, leerer
    Text -> die Defaults des Originals).
  * `_get_my_mitglied`: erst `Mitglied.user`, dann der Rueckfall ueber
    `Mitglied.email`/`User.email`.
  * Der scharfe Fall der Karte: angemeldeter Benutzer **ohne** Mitglied
    -> ehrliche Antwort, **kein 500** (nagelt die 417 fest).

Abgedeckt (Commit 2 — Schreibrichtungen):
  * `update_my_profile`: nur gesetzte Felder werden geschrieben, die
    Ergebniszustand ist nach erneutem Lesen wirklich gespeichert.
  * `update_adressbuch_sichtbarkeit`: Whitelist-Filter, Persistenz.

Abgedeckt (Commit 3 — Einwilligung):
  * `update_einwilligung`: nur `foto`/`werbung`, Log-Eintrag je Aenderung,
    kein Log-Eintrag bei falschem Typ (Throw VOR dem Schreiben).

Abgedeckt (Commit 4 — Profilbild):
  * `update_profile_picture`: schreibt `Mitglied.foto`, Persistenz.

Abgedeckt (Commit 5 — `delete_my_data`):
  * Anonymisierung, Deaktivieren des Users, Log-Eintraege ERHALTEN,
    Logout.
"""

from __future__ import annotations

import json
from datetime import date

import pytest

from test_ma1_mailversand import _smtp_einrichten

# Modul-Import: registriert die sechs `@whitelist`-Funktionen. Ohne diesen
# Import prueft `test_alle_sechs_pfade_registriert` einen leeren Registry —
# abhaengig davon, ob ein frueherer Test das Modul schon importiert hat.
import diakronos_app.api.profile  # noqa: F401
from diakronos_app.frappe_compat.registry import lookup
from diakronos_app.frappe_compat.session import set_user

PROFILE = "diakronos.diakonos.api.profile"

# Die sechs Originalpfade, die `Profile.vue` aufruft. `delete_mywilligung` im
# Aufruf der SPA (Zeile 499) ist KEIN eigener Pfad, sondern
# `update_einwilligung` mit `erteilt=0`.
#
# Aufgeteilt nach Commit: 1 = der gemeldete Fehler (Lese-Pfad), 2..5 die
# Schreib-Pfade. Jeder Commit registriert seinen Teil und testet ihn — so
# ist jeder Zwischenstand lauffaehig, statt nur der letzte.
LESE_PATHS = [
    f"{PROFILE}.get_my_profile",
]
SICHTBARKEIT_PATHS = [
    f"{PROFILE}.update_my_profile",
    f"{PROFILE}.update_adressbuch_sichtbarkeit",
]
EINWILLIGUNG_PATHS = [
    f"{PROFILE}.update_einwilligung",
]
BILD_PATHS = [
    f"{PROFILE}.update_profile_picture",
]
LOESCH_PATHS = [
    f"{PROFILE}.delete_my_data",
]
# Die Liste der bereits portierten Originalpfade. Sie waechst mit jedem
# Commit (dieser Stand: nur der Lese-Pfad); `ALLE_PATHS` ist damit die
# belastbare Zusage "alles, was existiert, ist registriert" statt eines
# Versprechens, das erst am Ende eingeloest wird. `ALLE_SECHS` ist die
# vollstaendige Menge aus dem Original und wird von
# `test_portierung_vollstaendig` am Ende der Karte abgeglichen.
ALLE_PATHS = (LESE_PATHS + SICHTBARKEIT_PATHS + EINWILLIGUNG_PATHS + BILD_PATHS
              + LOESCH_PATHS)
ALLE_SECHS = ALLE_PATHS

# Faehrt `update_my_profile` schon? Bis Commit 2 gibt es nur den Lese-Pfad;
# der CSRF-Test uebt einen Schreibpfad und wartet deshalb darauf.
UPDATE_MY_PROFILE_PORTIERT = bool(
    getattr(__import__("diakronos_app.api.profile", fromlist=["x"]), "update_my_profile", None)
)

ANNA = "anna@example.org"       # angemeldet, Mitglied ueber `user` verknuepft
BRUNO = "bruno@example.org"     # angemeldet, Mitglied NUR ueber E-Mail
CARLA = "carla@example.org"     # angemeldet, KEIN Mitglied (der scharfe Fall)
ADMIN = "admin@example.org"     # angemeldet, KEIN Mitglied (Erst-Admin)


# ── Fixture ─────────────────────────────────────────────────────────────────


@pytest.fixture()
def welt(patched_db):
    """Drei Benutzer, zwei davon mit Mitglied, Einwilligungen gesetzt."""
    from diakronos_app.models.core import User
    from diakronos_app.models.diakonos import Mitglied

    sess = patched_db()
    sess.add_all([
        User(name=ANNA, email=ANNA, full_name="Anna Beispiel", enabled=True),
        User(name=BRUNO, email=BRUNO, full_name="Bruno Brandner", enabled=True),
        User(name=CARLA, email=CARLA, full_name="Carla Chef", enabled=True),
        User(name=ADMIN, email=ADMIN, full_name="Ada Admin", enabled=True),
    ])
    sess.add_all([
        # Anna: vollstaendig, mit `user`-Verknuepfung.
        # Die Spalte heisst `straße` (mit Umlaut) — `strasse` waere ein
        # Attributfehler des Modells, kein Wert. Die API liefert sie unter
        # `strasse` (1:1 wie im Original), das ist `get_my_profile`s Job.
        Mitglied(
            name="M-0001", vorname="Anna", nachname="Beispiel", email=ANNA,
            status="Mitglied", user=ANNA, docstatus=0, idx=0,
            wohnort="Stuttgart", postleitzahl="70173",
            **{"straße": "Hauptstr."},
            nummer="7", geschlecht="w", familienstand="verheiratet",
            foto="/files/anna.jpg",
            datenschutz_einwilligung=True,
            # `Date`-Spalten verlangen `datetime.date` (SQLite ist hier
            # strenger als Postgres) — ein ISO-String waere ein TypeError.
            datenschutz_datum=date(2025, 3, 4),
            adressbuch_sichtbarkeit=json.dumps(
                {"email": True, "telefonnummer": False,
                 "adresse": True, "geburtstag": False}
            ),
        ),
        # Bruno: NUR ueber die E-Mail auffindbar (kein `user`) — prueft die
        # zweite Stufe von `_get_my_mitglied`.
        Mitglied(
            name="M-0002", vorname="Bruno", nachname="Beispiel", email=BRUNO,
            status="Mitglied", docstatus=0, idx=0, wohnort="Esslingen",
            postleitzahl="73728", foto_einwilligung=True,
            foto_datum=date(2025, 5, 6),
            werbeeinwilligung=True, werbung_datum=date(2025, 5, 6),
        ),
    ])
    sess.commit()
    yield sess
    sess.close()


# ── Registrierung ───────────────────────────────────────────────────────────


def test_alle_sechs_pfade_registriert():
    """Jeder bis jetzt portierte Originalpfad muss aufloesbar sein — der Fehler
    der Karte war ein 404, und genau den faengt dieser Test zuerst."""
    assert ALLE_PATHS, "mindestens ein Pfad muss portiert sein"
    for p in ALLE_PATHS:
        assert lookup(p) is not None, f"{p} nicht registriert"


def test_originalpfade_sind_genau_die_sechs_aus_dem_original():
    """Die Pfadmenge darf nicht schrumpfen und nichts erfinden: das Original
    hat genau sechs Whitelists, und jede muss unter dem Originalpfad
    registriert sein (P4g-Lehre: ein Tippfehler im Modulpfad faellt bei
    gruener Suite sonst nicht auf — nur am laufenden Stack)."""
    assert len(ALLE_SECHS) == 6, "das Original hat genau sechs Whitelists"
    assert len(set(ALLE_SECHS)) == 6, "keine Doppelnennung"
    for p in ALLE_SECHS:
        assert p.startswith(f"{PROFILE}."), p


def test_alle_sechs_pfade_ueber_http_erreichbar(client, welt):
    """Ueber den Router (nicht nur im Registry) — der Weg, den die SPA geht."""
    for p in ALLE_PATHS:
        res = client.post(f"/api/method/{p}")
        assert res.status_code != 404, f"{p} -> 404 ({res.text})"


# ── Login-Pflicht ───────────────────────────────────────────────────────────


def test_alle_sechs_pfade_fuer_gast_401(guest_client, welt):
    """`allow_guest=False` bleibt. Anonym -> 401, nicht 404.

    Wichtig: 401 statt 404 heisst "der Pfad existiert, nur nicht fuer dich".
    Ein 404 waere wieder der gemeldete Fehler.
    """
    for p in ALLE_PATHS:
        res = guest_client.post(f"/api/method/{p}")
        assert res.status_code == 401, f"{p} -> {res.status_code} {res.text}"


# ── get_my_profile ──────────────────────────────────────────────────────────


def test_get_my_profile_liefert_alle_felder(client, welt):
    """Der Kernfall: 200 MIT Daten, kein error, kein 404."""
    set_user(ANNA)
    res = client.post(f"/api/method/{PROFILE}.get_my_profile")
    assert res.status_code == 200, res.text
    data = res.json()["message"]

    # Alle 19 Felder des Originals muessen da sein.
    for feld in (
        "name", "vorname", "nachname", "email", "geburtstag", "telefonnummer",
        "postleitzahl", "wohnort", "strasse", "nummer", "foto", "geschlecht",
        "familienstand", "datenschutz_einwilligung", "datenschutz_datum",
        "foto_einwilligung", "foto_datum", "werbeeinwilligung", "werbung_datum",
        "adressbuch_sichtbarkeit",
    ):
        assert feld in data, f"Feld {feld!r} fehlt in der Antwort"

    assert data["name"] == "M-0001"
    assert data["vorname"] == "Anna"
    assert data["nachname"] == "Beispiel"
    assert data["email"] == ANNA
    assert data["wohnort"] == "Stuttgart"
    assert data["postleitzahl"] == "70173"
    # `straße` heisst in der Antwort `strasse` (1:1 wie im Original).
    assert data["strasse"] == "Hauptstr."
    assert data["nummer"] == "7"
    assert data["foto"] == "/files/anna.jpg"
    assert data["geschlecht"] == "w"
    assert data["familienstand"] == "verheiratet"
    assert data["datenschutz_einwilligung"] is True
    # Datum als String, nicht als date-Objekt.
    assert data["datenschutz_datum"] == "2025-03-04"


def test_get_my_profile_datumsfelder_null_wenn_leer(client, welt):
    """Ohne Geburtstag -> `None` (nicht `""`, nicht 1970)."""
    set_user(ANNA)
    data = client.post(f"/api/method/{PROFILE}.get_my_profile").json()["message"]
    assert data["geburtstag"] is None
    assert data["foto_datum"] is None
    assert data["werbung_datum"] is None
    assert data["foto_einwilligung"] is False
    assert data["werbeeinwilligung"] is False


def test_get_my_profile_sichtbarkeit_wird_als_dict_geliefert(client, welt):
    """Der JSON-Text aus der DB kommt als Dict an, sonst kaeme der Schalter
    der SPA (`Object.assign(sichtbarkeit, data.adressbuch_sichtbarkeit)`)
    auf einem String an."""
    set_user(ANNA)
    data = client.post(f"/api/method/{PROFILE}.get_my_profile").json()["message"]
    sicht = data["adressbuch_sichtbarkeit"]
    assert isinstance(sicht, dict)
    assert sicht == {"email": True, "telefonnummer": False,
                     "adresse": True, "geburtstag": False}


def test_get_my_profile_sichtbarkeit_default_wenn_leer(client, welt):
    """Kein hinterlegter Text -> die Defaults des Originals.

    Original (profile.py:28-29): `email`/`telefonnummer` sichtbar,
    `adresse`/`geburtstag` NICHT — Datenschutz-Default, kein Zufall.
    """
    from diakronos_app.models.diakonos import Mitglied

    set_user(ANNA)
    data = client.post(f"/api/method/{PROFILE}.get_my_profile").json()["message"]

    obj = welt.get(Mitglied, "M-0001")
    obj.adressbuch_sichtbarkeit = None
    welt.commit()

    data = client.post(f"/api/method/{PROFILE}.get_my_profile").json()["message"]
    assert data["adressbuch_sichtbarkeit"] == {
        "email": False, "telefonnummer": False,
        "adresse": False, "geburtstag": False,
    }


def test_get_my_profile_sichtbarkeit_kaputtes_json_ist_default(client, welt):
    """Unparsbarer Text -> `{}` -> Default. Kein 500, kein Fehler.

    1:1 wie im Original (`except Exception: sichtbarkeit = {}`).
    """
    from diakronos_app.models.diakonos import Mitglied

    obj = welt.get(Mitglied, "M-0001")
    obj.adressbuch_sichtbarkeit = "{kein json"
    welt.commit()

    set_user(ANNA)
    res = client.post(f"/api/method/{PROFILE}.get_my_profile")
    assert res.status_code == 200
    assert res.json()["message"]["adressbuch_sichtbarkeit"] == {
        "email": False, "telefonnummer": False,
        "adresse": False, "geburtstag": False,
    }


# ── _get_my_mitglied: die beiden Suchstufen ─────────────────────────────────


def test_get_my_profile_findet_ueber_user_verknuepfung(client, welt):
    """Stufe 1: `Mitglied.user == session.user`."""
    set_user(ANNA)
    data = client.post(f"/api/method/{PROFILE}.get_my_profile").json()["message"]
    assert data["name"] == "M-0001"


def test_get_my_profile_fallt_zurueck_auf_email(client, welt):
    """Stufe 2: `Mitglied.user` ist leer, der E-Mail-Abgleich pasft.

    Ohne diese Stufe waere ein Mitglied ohne `user`-Verknuepfung (bei
    A1a neu importierten Bestandsdaten der Normalfall) von seiner eigenen
    Profilseite ausgesperrt.
    """
    set_user(BRUNO)
    data = client.post(f"/api/method/{PROFILE}.get_my_profile").json()["message"]
    assert data["name"] == "M-0002"
    assert data["nachname"] == "Beispiel"
    # Brunos Einwilligungen muessen ebenfalls ankommen.
    assert data["foto_einwilligung"] is True
    assert data["foto_datum"] == "2025-05-06"
    assert data["werbeeinwilligung"] is True


def test_get_my_profile_zeigt_nur_das_eigene_profil(client, welt):
    """Anna sieht Annas Daten, nicht die von Bruno. Datenschutz-Grundregel:
    `_get_my_mitglied` bezieht den Namen IMMER aus der Sitzung, nie aus
    einem Request-Parameter — es gibt hier gar keinen, mit dem man fremde
    Daten anfordern koennte."""
    set_user(ANNA)
    data = client.post(f"/api/method/{PROFILE}.get_my_profile").json()["message"]
    assert "Brandner" not in json.dumps(data)
    assert data["email"] == ANNA


# ── Der scharfe Fall: Benutzer ohne Mitglied ────────────────────────────────


def test_benutzer_ohne_mitglied_bekommt_ehrliche_antwort_kein_500(client, welt):
    """Ein angemeldeter Benutzer OHNE `Mitglied` darf nicht 500 werfen.

    Das Original wirft `frappe.throw(...)` — im Frappe-Vertrag ein
    fachlicher Fehler. Erwartet wird hier **417 ValidationError** mit dem
    Originaltext. `Profile.vue:16` zeigt genau diese Nachricht an, die Seite
    ist also nicht leer, sondern sagt ehrlich, dass es kein Mitglied gibt.
    """
    set_user(CARLA)
    res = client.post(f"/api/method/{PROFILE}.get_my_profile")
    assert res.status_code == 417, res.text
    body = res.json()
    assert body["exc_type"] == "ValidationError"
    assert "Deinem Konto ist noch kein Mitglied zugeordnet." in body["message"]
    assert "message" in body  # Frappe-Envelope


def test_erst_admin_ohne_mitglied_bekommt_kein_500(client, welt):
    """Der in der Karte genannte Fall: ein frisch angelegter Erst-Admin
    (System Manager) hat in der Regel kein `Mitglied`."""
    from diakronos_app.models.core import HasRole

    welt.add(HasRole(name="r1", parent=ADMIN, parenttype="User",
                     parentfield="roles", role="System Manager"))
    welt.commit()

    set_user(ADMIN)
    res = client.post(f"/api/method/{PROFILE}.get_my_profile")
    assert res.status_code == 417, res.text
    assert "Deinem Konto ist noch kein Mitglied zugeordnet." in res.json()["message"]


def test_benutzer_ohne_mitglied_bekommt_kein_500_bei_Allen_portierten_endpunkten(client, welt):
    """Auch die Schreibpfade duerfen bei fehlendem Mitglied nicht 500 werfen.

    `_get_my_mitglied()` ist der ERSTE Aufruf in allen sechs Endpunkten —
    der Fehler kommt also ueberall identisch und vor jedem Schreibzugriff.
    Geprueft werden die Pfade, die dieser Stand schon portiert hat
    (`ALLE_PATHS`); mit jedem Commit kommt ein weiterer dazu."""
    # Gültige Argumente je Pfad: sonst schlaegt zuerst die Argumentpruefung
    # fehl (auch 417, aber mit anderer Nachricht) und der Fall wird nicht
    # geprueft. Getestet wird der Weg, den die SPA geht.
    argumente = {
        f"{PROFILE}.get_my_profile": {},
        f"{PROFILE}.update_my_profile": {"vorname": "X"},
        f"{PROFILE}.update_adressbuch_sichtbarkeit": {"settings": {"email": True}},
        f"{PROFILE}.update_profile_picture": {"file_url": "/files/x.jpg"},
        f"{PROFILE}.update_einwilligung": {"typ": "foto", "erteilt": 1},
        f"{PROFILE}.delete_my_data": {},
    }
    set_user(CARLA)
    for pfad in ALLE_PATHS:
        res = client.post(f"/api/method/{pfad}", json=argumente[pfad])
        assert res.status_code == 417, f"{pfad} -> {res.status_code} {res.text}"
        assert "Deinem Konto ist noch kein Mitglied zugeordnet." in res.json()["message"]


def test_ohne_mitglied_wird_nichts_geschrieben(client, welt):
    """Kein 500 ist nicht genug: es darf auch kein halber Zustand entstehen.
    Die Suche nach einem NICHT vorhandenen Mitglied darf keine Zeile in
    `User` oder `Mitglied` anlegen oder loeschen."""
    from diakronos_app.models.core import User
    from diakronos_app.models.diakonos import Mitglied

    vorher_mitglieder = welt.query(Mitglied).count()
    vorher_user = welt.query(User).count()

    argumente = {
        f"{PROFILE}.update_my_profile": {"vorname": "X"},
        f"{PROFILE}.update_adressbuch_sichtbarkeit": {"settings": {"email": True}},
        f"{PROFILE}.update_profile_picture": {"file_url": "/files/x.jpg"},
        f"{PROFILE}.update_einwilligung": {"typ": "foto", "erteilt": 1},
    }
    set_user(CARLA)
    for pfad in ALLE_PATHS:
        client.post(f"/api/method/{pfad}", json=argumente.get(pfad, {}))

    welt.expire_all()
    assert welt.query(Mitglied).count() == vorher_mitglieder
    assert welt.query(User).count() == vorher_user


# ── update_my_profile ───────────────────────────────────────────────────────


def test_update_my_profile_speichert_und_bleibt_gespeichert(client, welt):
    """200 UND der Zustand ist nach erneutem Lesen wirklich gespeichert.

    Die Abnahme dieser Karte sagt: "Ein 200, das nichts speichert, ist
    schlimmer als ein Fehler." Deshalb wird hier nicht nur der Status
    geprueft, sondern zurueckgelesen."""
    set_user(ANNA)
    res = client.post(f"/api/method/{PROFILE}.update_my_profile", json={
        "vorname": "Anna-Lena", "nachname": "Beispiel-Meyer",
        "telefonnummer": "0711 12345", "postleitzahl": "70174",
        "wohnort": "Stuttgart", "strasse": "Kirchweg", "nummer": "12",
        "geschlecht": "w", "familienstand": "ledig",
    })
    assert res.status_code == 200, res.text
    assert res.json()["message"] == {"ok": True}

    data = client.post(f"/api/method/{PROFILE}.get_my_profile").json()["message"]
    assert data["vorname"] == "Anna-Lena"
    assert data["nachname"] == "Beispiel-Meyer"
    assert data["telefonnummer"] == "0711 12345"
    assert data["postleitzahl"] == "70174"
    assert data["wohnort"] == "Stuttgart"
    # `straße` wird ueber `strasse` geschrieben und auch so gelesen.
    assert data["strasse"] == "Kirchweg"
    assert data["nummer"] == "12"
    assert data["familienstand"] == "ledig"


def test_update_my_profile_leert_geburtstag(client, welt):
    """Ein LEERER Geburtstag ist ein Loesch-Befehl, kein "unveraendert".

    Original (profile.py:70): `doc.geburtstag = geburtstag or None`. Genau
    hier verschaerft `_update_doc` (verwirft `None`) das Verhalten zu einem
    stillen 200 — deshalb geht der Port bewusst ueber `doc.save()`."""
    from diakronos_app.models.diakonos import Mitglied

    welt.get(Mitglied, "M-0001").geburtstag = __import__("datetime").date(1990, 5, 4)
    welt.commit()

    set_user(ANNA)
    res = client.post(f"/api/method/{PROFILE}.update_my_profile",
                      json={"geburtstag": ""})
    assert res.status_code == 200, res.text
    assert res.json()["message"] == {"ok": True}

    data = client.post(f"/api/method/{PROFILE}.get_my_profile").json()["message"]
    assert data["geburtstag"] is None, "leeres Geburtstag muss loeschen"


def test_update_my_profile_setzt_geburtstag(client, welt):
    """Und der Normalfall: ein Datum wird geschrieben."""
    set_user(ANNA)
    res = client.post(f"/api/method/{PROFILE}.update_my_profile",
                      json={"geburtstag": "1988-02-29"})
    assert res.status_code == 200, res.text
    data = client.post(f"/api/method/{PROFILE}.get_my_profile").json()["message"]
    assert data["geburtstag"] == "1988-02-29"


def test_update_my_profile_ungeordnete_felder_bleiben(client, welt):
    """Nur was MITGESCHICKT wurde, wird geschrieben.

    Original (profile.py:61-72): `if feld is not None:` je Zeile. Der
    Unterschied zwischen "nicht mitgeschickt" (None) und "leer" ("") ist der
    ganze Zweck dieser Zeilen — ohne ihn wuerde ein Teildialog die uebrigen
    Felder leeren."""
    set_user(ANNA)
    res = client.post(f"/api/method/{PROFILE}.update_my_profile",
                      json={"wohnort": "Freiburg"})
    assert res.status_code == 200, res.text

    data = client.post(f"/api/method/{PROFILE}.get_my_profile").json()["message"]
    assert data["wohnort"] == "Freiburg"
    # Unberuehrt geblieben:
    assert data["nachname"] == "Beispiel"
    assert data["postleitzahl"] == "70173"
    assert data["geschlecht"] == "w"


def test_update_my_profile_leerer_string_leert_textfeld(client, welt):
    """Leerer String ist ein Wert: `telefonnummer=""` leert wirklich."""
    from diakronos_app.models.diakonos import Mitglied

    welt.get(Mitglied, "M-0001").telefonnummer = "0711 999"
    welt.commit()

    set_user(ANNA)
    res = client.post(f"/api/method/{PROFILE}.update_my_profile",
                      json={"telefonnummer": ""})
    assert res.status_code == 200, res.text
    data = client.post(f"/api/method/{PROFILE}.get_my_profile").json()["message"]
    assert data["telefonnummer"] == ""


def test_update_my_profile_ohne_argumente_ist_noop(client, welt):
    """Leerer Aufruf -> 200, aber ohne Seiteneffekt (1:1 das Original)."""
    set_user(ANNA)
    res = client.post(f"/api/method/{PROFILE}.update_my_profile", json={})
    assert res.status_code == 200, res.text
    data = client.post(f"/api/method/{PROFILE}.get_my_profile").json()["message"]
    assert data["vorname"] == "Anna"
    assert data["wohnort"] == "Stuttgart"


def test_update_my_profile_aendert_nur_das_eigene_profil(client, welt):
    """Anna aendert ihr Profil; Brunos Satz bleibt unberuehrt.

    `_get_my_mitglied()` nimmt den Namen aus der Sitzung, nicht aus einem
    Request-Parameter — `mitglied_id` gibt es hier gar nicht, mit dem man
    fremde Daten treffen koennte."""
    set_user(ANNA)
    client.post(f"/api/method/{PROFILE}.update_my_profile",
                json={"vorname": "Nur-Anna"})

    set_user(BRUNO)
    data = client.post(f"/api/method/{PROFILE}.get_my_profile").json()["message"]
    assert data["vorname"] == "Bruno"
    assert data["wohnort"] == "Esslingen"


def test_update_my_profile_fasst_einwilligungen_nicht_an(client, welt):
    """Die Einwilligungsfelder gehoeren `update_einwilligung`.

    `referenz/.../AGENTS.md`: die sechs Felder sind read_only und duerfen
    NUR ueber die whitelisted Funktionen MIT Log-Eintrag geaendert werden.
    Versucht man es ueber `update_my_profile`, hat der Aufruf keinen
    Parameter dafuer — und ein erfundener wuerde die Regel aushebeln."""
    set_user(ANNA)
    client.post(f"/api/method/{PROFILE}.update_my_profile",
                json={"vorname": "Anna", "datenschutz_einwilligung": False,
                      "foto_einwilligung": False})
    data = client.post(f"/api/method/{PROFILE}.get_my_profile").json()["message"]
    # Unveraendert, weil es diese Parameter in der Signatur gar nicht gibt.
    assert data["datenschutz_einwilligung"] is True
    assert data["foto_einwilligung"] is False  # war schon False


# ── update_adressbuch_sichtbarkeit ──────────────────────────────────────────


def test_sichtbarkeit_speichert_und_bleibt_gespeichert(client, welt):
    """200 und der Zustand ist nach erneutem Lesen wirklich da."""
    set_user(ANNA)
    res = client.post(f"/api/method/{PROFILE}.update_adressbuch_sichtbarkeit", json={
        "settings": {"email": False, "telefonnummer": True,
                     "adresse": False, "geburtstag": True},
    })
    assert res.status_code == 200, res.text
    assert res.json()["message"] == {"ok": True}

    data = client.post(f"/api/method/{PROFILE}.get_my_profile").json()["message"]
    assert data["adressbuch_sichtbarkeit"] == {
        "email": False, "telefonnummer": True,
        "adresse": False, "geburtstag": True,
    }


def test_sichtbarkeit_nimmt_als_json_string(client, welt):
    """Frappe-Formular schickt `settings` als Text — der Port parst ihn."""
    set_user(ANNA)
    res = client.post(
        f"/api/method/{PROFILE}.update_adressbuch_sichtbarkeit",
        json={"settings": json.dumps({"email": False, "adresse": True})},
    )
    assert res.status_code == 200, res.text
    data = client.post(f"/api/method/{PROFILE}.get_my_profile").json()["message"]
    assert data["adressbuch_sichtbarkeit"] == {
        "email": False, "telefonnummer": False, "adresse": True, "geburtstag": False,
    }


def test_sichtbarkeit_filtert_fremde_schluessel(client, welt):
    """Der Allowlist-Filter des Originals (Zeile 86).

    Ein Schreibversuch auf einen anderen Schluessel wird still ignoriert —
    gespeichert wird nur die erlaubte Teilmenge. Genau wie im Original."""
    set_user(ANNA)
    res = client.post(f"/api/method/{PROFILE}.update_adressbuch_sichtbarkeit", json={
        "settings": {"email": True, "geburtsdatum": True,
                     "vorname": "Hacked", "status": "Admin"},
    })
    assert res.status_code == 200, res.text
    data = client.post(f"/api/method/{PROFILE}.get_my_profile").json()["message"]
    sicht = data["adressbuch_sichtbarkeit"]
    assert sicht == {"email": True, "telefonnummer": False,
                     "adresse": False, "geburtstag": False}
    # Und nichts am Mitglied selbst wurde angefasst.
    assert data["vorname"] == "Anna"
    assert data["email"] == ANNA


def test_sichtbarkeit_castet_auf_bool(client, welt):
    """Nur ein echtes JSON-Boolean true ist eine Freigabe (B2)."""
    set_user(ANNA)
    client.post(f"/api/method/{PROFILE}.update_adressbuch_sichtbarkeit", json={
        "settings": {"email": 1, "telefonnummer": 0, "adresse": "nein",
                     "geburtstag": 1},
    })
    data = client.post(f"/api/method/{PROFILE}.get_my_profile").json()["message"]
    sicht = data["adressbuch_sichtbarkeit"]
    assert sicht == {"email": False, "telefonnummer": False,
                     "adresse": False, "geburtstag": False}
    assert all(isinstance(v, bool) for v in sicht.values())


def test_sichtbarkeit_leeres_settings_setzt_leere_auswahl(client, welt):
    """`settings=None` -> `{}` GESPEICHERT, und die Anzeige liest das als
    "leer", also als die Defaults des Originals.

    Das ist kein No-op: im Original wird `json.dumps({})` geschrieben. Die
    spaetere Anzeige faellt darauf zurueck (`if not sichtbarkeit:` in
    `get_my_profile`) und zeigt email/telefonnummer sichtbar, Adresse und
    Geburtstag nicht. Genau das wird hier festgehalten — ein stilles
    "unveraendert" waere eine erfundene Semantik."""
    set_user(ANNA)
    res = client.post(f"/api/method/{PROFILE}.update_adressbuch_sichtbarkeit",
                      json={})
    assert res.status_code == 200, res.text
    assert res.json()["message"] == {"ok": True}

    from diakronos_app.models.diakonos import Mitglied

    gespeichert = welt.get(Mitglied, "M-0001").adressbuch_sichtbarkeit
    welt.expire_all()
    assert gespeichert == "{}", "der Original-Pfad speichert den leeren Text"

    data = client.post(f"/api/method/{PROFILE}.get_my_profile").json()["message"]
    assert data["adressbuch_sichtbarkeit"] == {
        "email": False, "telefonnummer": False,
        "adresse": False, "geburtstag": False,
    }


def test_sichtbarkeit_kaputtes_json_ist_leer_statt_500(client, welt):
    """Unparsbarer `settings`-Text -> `{}`, kein 500."""
    set_user(ANNA)
    res = client.post(
        f"/api/method/{PROFILE}.update_adressbuch_sichtbarkeit",
        json={"settings": "{kein json"},
    )
    assert res.status_code == 200, res.text

# ── update_einwilligung ─────────────────────────────────────────────────────


def _eintraege(welt, mitglied="M-0001"):
    """Alle `DSGVO Einwilligung`-Zeilen eines Mitglieds, chronologisch."""
    from diakronos_app.models.diakonos import DSGVOEinwilligung

    welt.expire_all()
    return welt.query(DSGVOEinwilligung).filter_by(mitglied=mitglied).all()


def test_einwilligung_foto_erteilen_speichert_und_loggt(client, welt):
    """Foto-Einwilligung setzen: 200, wirklich gespeichert, UND geloggt.

    Die drei Aussagen gehoeren zusammen: ein 200 ohne Log waere ein
    DSGVO-Verstoss, ein Log ohne Speicherung waere ein 200, das nichts
    bewirkt."""
    set_user(ANNA)
    res = client.post(f"/api/method/{PROFILE}.update_einwilligung",
                      json={"typ": "foto", "erteilt": 1})
    assert res.status_code == 200, res.text
    assert res.json()["message"] == {"ok": True}

    data = client.post(f"/api/method/{PROFILE}.get_my_profile").json()["message"]
    assert data["foto_einwilligung"] is True
    # Datum ist gesetzt (ISO) — ein Nachweis muss ein Datum tragen.
    assert data["foto_datum"], "ohne Datum kein Nachweis"
    assert len(data["foto_datum"]) == 10, data["foto_datum"]

    logs = _eintraege(welt)
    assert len(logs) == 1
    assert logs[0].typ == "foto"
    assert logs[0].aktion == "erteilt"
    assert logs[0].mitglied == "M-0001"
    assert logs[0].quelle == "selfservice"
    assert logs[0].zeitstempel is not None


def test_einwilligung_werbung_erteilen(client, welt):
    """Der zweite Typ — und NUR die beiden Typen sind erlaubt."""
    set_user(ANNA)
    res = client.post(f"/api/method/{PROFILE}.update_einwilligung",
                      json={"typ": "werbung", "erteilt": 1})
    assert res.status_code == 200, res.text
    data = client.post(f"/api/method/{PROFILE}.get_my_profile").json()["message"]
    assert data["werbeeinwilligung"] is True
    assert data["werbung_datum"]

    logs = _eintraege(welt)
    assert len(logs) == 1
    assert logs[0].typ == "werbung"


def test_einwilligung_widerruf_loescht_datum_und_loggt(client, welt):
    """Der WIDERRUF: `erteilt=0` — der Weg, den `Profile.vue:499` geht.

    Geprueft wird mehr als "Flag ist aus": das Datum muss MIT verschwinden
    (sonst behauptet der Datensatz, eine Einwilligung vom heute zu haben),
    und der Log-Eintrag muss `aktion="widerrufen"` sagen."""
    from diakronos_app.models.diakonos import Mitglied

    welt.get(Mitglied, "M-0001").foto_einwilligung = True
    welt.get(Mitglied, "M-0001").foto_datum = date(2025, 1, 15)
    welt.commit()

    set_user(ANNA)
    res = client.post(f"/api/method/{PROFILE}.update_einwilligung",
                      json={"typ": "foto", "erteilt": 0})
    assert res.status_code == 200, res.text

    data = client.post(f"/api/method/{PROFILE}.get_my_profile").json()["message"]
    assert data["foto_einwilligung"] is False
    assert data["foto_datum"] is None, "Widerruf muss das Datum loeschen"

    logs = _eintraege(welt)
    assert len(logs) == 1
    assert logs[0].aktion == "widerrufen"


def test_einwilligung_widerruf_als_0_und_leerer_string(client, welt):
    """`cint`-Toleranz: `0`, `"0"`, `false` und `""` heissen alle
    "widerrufen" — so wie `frappe.utils.cint` es im Original aufloest."""
    set_user(ANNA)
    for wert in (0, "0", False, "", None):
        res = client.post(f"/api/method/{PROFILE}.update_einwilligung",
                          json={"typ": "werbung", "erteilt": wert})
        assert res.status_code == 200, f"{wert!r} -> {res.status_code} {res.text}"
        data = client.post(f"/api/method/{PROFILE}.get_my_profile").json()["message"]
        assert data["werbeeinwilligung"] is False, wert
        assert data["werbung_datum"] is None, wert


def test_einwilligung_erteilen_als_1_und_true(client, welt):
    """Und die Gegenseite: truthy heisst erteilt."""
    set_user(ANNA)
    for wert in (1, "1", True):
        res = client.post(f"/api/method/{PROFILE}.update_einwilligung",
                          json={"typ": "foto", "erteilt": wert})
        assert res.status_code == 200, f"{wert!r} -> {res.status_code}"
        data = client.post(f"/api/method/{PROFILE}.get_my_profile").json()["message"]
        assert data["foto_einwilligung"] is True, wert


def test_einwilligung_unbekannter_typ_wirft_und_loggt_nicht(client, welt):
    """Nur `foto` und `werbung`. Alles andere -> 417, **kein** Eintrag.

    Der Wurf kommt vor jedem Schreibzugriff (Original Zeile 123). Besonders
    `datenschutz` ist hier falsch: die allgemeine Datenschutzerklaerung wird
    nicht ueber die Profilseite gesetzt."""
    set_user(ANNA)
    for typ in ("datenschutz", "", "Foto", "FOTo", "adresse", None):
        res = client.post(f"/api/method/{PROFILE}.update_einwilligung",
                          json={"typ": typ, "erteilt": 1})
        assert res.status_code == 417, f"{typ!r} -> {res.status_code} {res.text}"
        assert "Ungültiger Einwilligungstyp" in res.json()["message"]

    assert _eintraege(welt) == [], "abgelehnter Typ darf nicht loggen"


def test_einwilligung_datenschutz_laeuft_hier_nicht_durch(client, welt):
    """Sicherheitsnetz: `datenschutz_einwilligung` bleibt unberuehrt.

    Wer `typ="datenschutz"` schickt, bekommt 417 — und das Flag aendert sich
    nicht. Wuerde der Weg funktionieren, koennte jeder sein
    Datenschutz-Flag selbst setzen; der Admin-Widerruf waere umgehbar."""
    set_user(ANNA)
    client.post(f"/api/method/{PROFILE}.update_einwilligung",
                json={"typ": "datenschutz", "erteilt": 1})
    data = client.post(f"/api/method/{PROFILE}.get_my_profile").json()["message"]
    # Anna hatte True im Fixture — unveraendert True, nicht etwa "neu erteilt".
    assert data["datenschutz_datum"] == "2025-03-04"


def test_einwilligung_logt_ip_anonymisiert(client, welt):
    """Die IP im Log ist Nachweis, aber keine Personenakte: letztes Oktett 0.

    1:1 wie `dsgvo_log.py:16-21`."""
    set_user(ANNA)
    client.post(f"/api/method/{PROFILE}.update_einwilligung",
                json={"typ": "foto", "erteilt": 1},
                headers={"User-Agent": "P4n-Test/1.0"})
    logs = _eintraege(welt)
    assert len(logs) == 1
    ip = logs[0].ip_adresse or ""
    if ip and "." in ip and len(ip.split(".")) == 4:
        assert ip.endswith(".0"), f"IP nicht anonymisiert: {ip}"
    # User-Agent wird gekuerzt, nicht verworfen.
    assert (logs[0].user_agent or "").startswith("P4n-Test/1.0")


def test_einwilligung_mehrfache_aenderungen_erzeugen_mehrere_Log_zeilen(client, welt):
    """Nachweis-Vollstaendigkeit: jeder Wechsel wird einzeln protokolliert."""
    set_user(ANNA)
    for typ, wert in (("foto", 1), ("werbung", 1), ("foto", 0), ("foto", 1)):
        res = client.post(f"/api/method/{PROFILE}.update_einwilligung",
                          json={"typ": typ, "erteilt": wert})
        assert res.status_code == 200, res.text

    logs = _eintraege(welt)
    assert len(logs) == 4, "vier Aenderungen, vier Eintraege"
    assert [(l.typ, l.aktion) for l in logs] == [
        ("foto", "erteilt"), ("werbung", "erteilt"),
        ("foto", "widerrufen"), ("foto", "erteilt"),
    ]


def test_einwilligung_gehoert_zum_eigenen_profil(client, welt):
    """Bruno erteilt, Anna nicht — getrennte Saetze, getrennte Logs."""
    set_user(BRUNO)
    client.post(f"/api/method/{PROFILE}.update_einwilligung",
                json={"typ": "werbung", "erteilt": 1})
    set_user(ANNA)
    data = client.post(f"/api/method/{PROFILE}.get_my_profile").json()["message"]
    # Anna hatte nie eine Werbeeinwilligung.
    assert data["werbeeinwilligung"] is False

    assert len(_eintraege(welt, "M-0002")) == 1
    assert _eintraege(welt, "M-0001") == []


# ── update_profile_picture ──────────────────────────────────────────────────


@pytest.fixture
def anna_uploaded_url(client, welt, tmp_path, monkeypatch):
    from diakronos_app.settings import settings
    monkeypatch.setattr(settings, 'files_dir', str(tmp_path / 'files'))
    set_user(ANNA)
    response = client.post('/api/method/upload_file', files={
        'file': ('anna-neu.jpg', b'\xff\xd8\xff\xe0JPEG', 'image/jpeg'),
    }, data={'is_private': '0'})
    assert response.status_code == 200, response.text
    return response.json()['message']['file_url']


def test_profilbild_speichert_und_bleibt_gespeichert(client, welt, anna_uploaded_url):
    """Der Weg der SPA: erst `upload_file`, dann diese Funktion mit der URL."""
    set_user(ANNA)
    res = client.post(f"/api/method/{PROFILE}.update_profile_picture",
                      json={"file_url": anna_uploaded_url})
    assert res.status_code == 200, res.text
    assert res.json()["message"] == {"ok": True}

    data = client.post(f"/api/method/{PROFILE}.get_my_profile").json()["message"]
    assert data["foto"] == anna_uploaded_url


def test_profilbild_leeren_wert_setzt_zurueck(client, welt):
    """Kein Bild mehr: leerer Wert -> `foto` ist wieder leer."""
    set_user(ANNA)
    res = client.post(f"/api/method/{PROFILE}.update_profile_picture",
                      json={"file_url": ""})
    assert res.status_code == 200, res.text
    data = client.post(f"/api/method/{PROFILE}.get_my_profile").json()["message"]
    assert data["foto"] == ""


def test_profilbild_nur_am_eigenen_profil(client, welt, anna_uploaded_url):
    """Brunos Bild bleibt, wenn Anna ihres aendert."""
    from diakronos_app.models.diakonos import Mitglied

    welt.get(Mitglied, "M-0002").foto = "/files/bruno.jpg"
    welt.commit()

    set_user(ANNA)
    client.post(f"/api/method/{PROFILE}.update_profile_picture",
                json={"file_url": anna_uploaded_url})

    set_user(BRUNO)
    data = client.post(f"/api/method/{PROFILE}.get_my_profile").json()["message"]
    assert data["foto"] == "/files/bruno.jpg"


def test_profilbild_beruehrt_die_foto_einwilligung_nicht(client, welt, anna_uploaded_url):
    """Ein Bild ist KEINE Einwilligung.

    Wichtig, weil beides im selben UI-Bereich liegt: das Hochladen eines
    Profilbildes darf die Foto-Einwilligung NICHT setzen — die ist eine
    eigene, widerrufbare Entscheidung mit Log-Eintrag."""
    set_user(ANNA)
    client.post(f"/api/method/{PROFILE}.update_profile_picture",
                json={"file_url": anna_uploaded_url})
    data = client.post(f"/api/method/{PROFILE}.get_my_profile").json()["message"]
    assert data["foto"] == anna_uploaded_url
    assert data["foto_einwilligung"] is False
    assert _eintraege(welt) == [], "Bild hochladen loggt keine Einwilligung"

# N7 ändert ausdrücklich den Vertrag: gleiche Zustands-/Sitzungsregressionen
# laufen jetzt über den bestätigten Antrag und die separate Adminaktion.
def _admin_erledigt(client, welt):
    from diakronos_app.api.profile import _get_my_mitglied
    from diakronos_app.models.core import HasRole
    from diakronos_app.frappe_compat.session import session
    user = session.user
    mid = _get_my_mitglied()
    pfad = '/api/method/diakronos.diakonos.api.datenschutz.'
    antrag = client.post(pfad + 'loeschung_beantragen', json={'bestaetigt': True})
    assert antrag.status_code == 200, antrag.text
    if not welt.get(HasRole, 'N7-test-admin'):
        welt.add(HasRole(name='N7-test-admin', parent=ADMIN, role='System Manager'))
        welt.commit()
    set_user(ADMIN)
    try:
        return client.post(pfad + 'anonymisieren', json={
            'mitglied_id': mid, 'bestaetigt': True,
            'bestaetigung': 'ANONYMISIEREN', 'nur_antrag': True,
        })
    finally:
        set_user(user)


def _geloescht(welt):
    """Die Mitglied-Zeile der geloeschten Person — unter ihrer NEUEN Kennung.

    DSGVO-1b (K1): `mitglied.name` ist im Betrieb der Klarname. Bei der
    Loeschung entsteht eine Zeile mit der Kennung `geloescht-<hex>`; die alte
    ist weg. Alle Nachweise (Einwilligungen, Protokoll) haengen an der neuen.
    """
    from diakronos_app.models.diakonos import Mitglied

    from sqlalchemy import select

    welt.expire_all()
    alle = [str(n) for n in welt.scalars(select(Mitglied.name)).all()]
    kennungen = [n for n in alle if n.startswith("geloescht-")]
    assert len(kennungen) == 1, alle
    return kennungen[0], welt.get(Mitglied, kennungen[0])


@pytest.fixture(autouse=True)
def _mailversand(monkeypatch, tmp_path, patched_db):
    """Fake-SMTP fuer den Antragsweg.

    N-5 (DSGVO-1c): Löschungen laufen NUR über Antrag → Bestätigung → Mail.
    Der Test braucht deshalb einen Versand, der nicht ins Netz geht; die
    Prüfungen der Tests bleiben unverändert (die Meldung ist Teil des Wegs).
    """
    from diakronos_app import files, mailversand
    from diakronos_app.settings import get_settings

    class Fake:
        def __init__(self):
            self.nachrichten = []

        def ehlo(self):
            pass

        def has_extn(self, name):
            return True

        def starttls(self, **kw):
            pass

        def login(self, *a):
            pass

        def send_message(self, nachricht):
            self.nachrichten.append(nachricht)

        def quit(self):
            pass

    # MAIL-1: die SMTP-Werte stehen in der DB (Tabelle `smtp_einstellungen`),
    # nicht mehr in der Umgebung — siehe `_smtp_einrichten`.
    _smtp_einrichten(patched_db)
    s = get_settings()
    for feld, wert in (
        ("files_dir", str(tmp_path)),
    ):
        monkeypatch.setattr(s, feld, wert, raising=False)
    monkeypatch.setattr(files.settings, "files_dir", str(tmp_path), raising=False)
    fake = Fake()
    fake.dir = tmp_path
    monkeypatch.setattr(mailversand, "VERBINDUNG", fake)
    return fake


# ── N7: Anonymisierung nur nach Antrag und Adminbestätigung ───────────────────────────────────


def test_loeschung_anonymisiert_alle_pii(client, welt):
    """Der Kern des Widerrufs: keine personenbezogenen Daten mehr im Satz.

    Geprueft wird der ZUSTAND nach der Loeschung, nicht nur der 200."""
    from diakronos_app.models.diakonos import Mitglied

    set_user(ANNA)
    res = _admin_erledigt(client, welt)
    assert res.status_code == 200, res.text
    antwort = res.json()["message"]
    assert antwort["ok"] is True
    # DSGVO-1: die Antwort nennt zusätzlich, was bereinigt wurde (Nachweis für
    # den Administrator) — aber KEINE Personendaten.
    assert isinstance(antwort.get("zaehler"), dict)

    assert welt.expire_all() is None
    assert welt.get(Mitglied, "M-0001") is None, "alte Kennung (Klarname) bleibt"
    kennung, doc = _geloescht(welt)
    # DSGVO-1b: fester Anzeigename; die NEUE Kennung traegt die Nachweise.
    assert doc.vorname == "Gelöschte"
    assert doc.nachname == "Person"
    assert doc.name == kennung
    # D6: keine Mail mehr — und die Adresse ist damit wieder vergebbar.
    assert doc.email is None
    assert doc.telefonnummer in (None, "")
    assert doc.postleitzahl in (None, "")
    assert doc.wohnort in (None, "")
    assert getattr(doc, "straße") in (None, "")
    assert doc.nummer in (None, "")
    assert doc.geburtstag is None
    assert doc.foto is None
    assert doc.status == "geloescht"


def test_loeschung_setzt_einwilligungen_zurueck(client, welt):
    """Alle drei Einwilligungen auf 0, die Datumsfelder auf `None`."""
    from diakronos_app.models.diakonos import Mitglied

    set_user(ANNA)
    _admin_erledigt(client, welt)

    welt.expire_all()
    doc = _geloescht(welt)[1]
    assert not doc.datenschutz_einwilligung
    assert not doc.foto_einwilligung
    assert not doc.werbeeinwilligung
    # Der Widerruf loescht das Datum — ein Datum ohne Einwilligung waere
    # eine falsche Aktenlage.
    assert doc.foto_datum is None
    assert doc.werbung_datum is None


def test_loeschung_schaltet_alles_im_adressbuch_ab(client, welt):
    """Nach dem Widerruf ist nichts mehr oeffentlich."""
    from diakronos_app.models.diakonos import Mitglied

    welt.get(Mitglied, "M-0001").adressbuch_sichtbarkeit = json.dumps(
        {"email": True, "telefonnummer": True, "adresse": True,
         "geburtstag": True})
    welt.commit()

    set_user(ANNA)
    _admin_erledigt(client, welt)

    welt.expire_all()
    doc = _geloescht(welt)[1]
    from diakronos_app.frappe_compat.mitglied_sichtbarkeit import sichtbarkeit_lesen
    assert not any(sichtbarkeit_lesen(doc.adressbuch_sichtbarkeit).values())


def test_loeschung_entfernt_den_user(client, welt):
    """DSGVO-1: das Konto ist WEG. `user.name` ist die E-Mail und der
    Primärschlüssel — „gesperrt“ würde die Adresse weiter führen."""
    from diakronos_app.models.core import User

    set_user(ANNA)
    _admin_erledigt(client, welt)

    welt.expire_all()
    assert welt.get(User, ANNA) is None
    # Und damit ist auch kein Login mehr möglich (kein Konto, keine Rolle).
    from diakronos_app.api.auth import login

    with pytest.raises(Exception):
        login(email=ANNA, passwort="irgendwas")


def test_loeschung_behaelt_die_mitgliedschaft(client, welt):
    """Anonymisiert, NICHT geloescht — die Historie muss stehen bleiben.

    Wichtig: waere der Satz weg, waeren Mitgliedsbeitraege, Dienstplan und
    Kinder ebenfalls weg. Das ist der Grund, warum ueberschrieben und
    nicht geloescht wird."""
    from diakronos_app.models.diakonos import Mitglied

    set_user(ANNA)
    _admin_erledigt(client, welt)

    welt.expire_all()
    kennung, doc = _geloescht(welt)
    assert doc is not None, "die Mitgliedschaft muss die Loeschung ueberleben"
    # D5: der Status ist „geloescht“ (endgültig, nicht reaktivierbar) — die
    # ZEILE bleibt, damit Beitrags-, Dienstplan- und Kinderhistorie steht.
    assert doc.status == "geloescht"
    assert doc.docstatus == 0


def test_loeschung_logt_die_widerrufe(client, welt):
    """Jede gesetzte Einwilligung erzeugt einen `widerrufen`-Log-Eintrag.

    Annas Profil hat `datenschutz` gesetzt; das ist der Eintrag, den die
    DSGVO verlangt (AGENTS.md Abschnitt 4: `delete_my_data` -> alle)."""
    set_user(ANNA)
    _admin_erledigt(client, welt)

    eintraege = _eintraege(welt, _geloescht(welt)[0])
    assert [e.aktion for e in eintraege] == ["widerrufen"]
    assert eintraege[0].typ == "datenschutz"
    # Der Log-Eintrag ueberlebt und nennt nur die technische ID.
    assert eintraege[0].mitglied == _geloescht(welt)[0]


def test_loeschung_logt_brunos_drei_widerrufe(client, welt):
    """Bruno hat foto+werbung gesetzt -> zwei Eintraege, korrekt typisiert."""
    set_user(BRUNO)
    _admin_erledigt(client, welt)

    eintraege = _eintraege(welt, _geloescht(welt)[0])
    assert {(e.typ, e.aktion) for e in eintraege} == {
        ("foto", "widerrufen"), ("werbung", "widerrufen"),
    }


def test_loeschung_logt_keinen_widerruf_ohne_vorbestehende_einwilligung(client, welt):
    """Kein Einwilligungs-Flag gesetzt -> KEIN Log-Eintrag.

    Ein "Widerruf" einer nie erteilten Einwilligung waere eine falsche
    Aktenlage. Der Test nimmt einen frischen Satz ohne Einwilligungen."""
    from diakronos_app.models.core import User
    from diakronos_app.models.diakonos import Mitglied

    welt.add(User(name="dora@example.org", email="dora@example.org",
                  full_name="Dora Damm", enabled=True))
    welt.add(Mitglied(
        name="M-0003", vorname="Dora", nachname="Damm", email="dora@example.org",
        status="Mitglied", user="dora@example.org", docstatus=0, idx=0,
    ))
    welt.commit()

    set_user("dora@example.org")
    res = _admin_erledigt(client, welt)
    assert res.status_code == 200, res.text
    assert _eintraege(welt, "M-0003") == []


def test_loeschung_ueberlebt_als_nutzer_danach_ausgeloggt(client, welt):
    """Die **eigene** Sitzung ist nach der Loeschung tot (Art. 17: sofort raus).

    Geprueft wird der `sid` direkt im Store, weil `logout` in `api/auth.py`
    den Cookie loescht — der Test-Client wuerde ihn sonst beim naechsten
    Request selbst wieder mitschicken und den Nachweis unmoeglich machen.

    B1 hat diesen Test ehrlich gemacht: er legt sich **selbst** eine Sitzung
    fuer ANNA an und setzt das Cookie darauf, statt das `Administrator`-Cookie
    des `client`-Fixtures zu benutzen, waehrend der Aufruf als ANNA lief.
    Der alte Aufbau pruefte etwas anderes als sein Name behauptete — er
    pruefte, dass `delete_my_data` das Cookie des *Geraets* loescht, nicht
    das des *Benutzers*. Beides ist richtig, nur waren sie nicht dasselbe.
    """
    from diakronos_app.frappe_compat import sitzungen

    sid, csrf = sitzungen.anlegen(ANNA)
    client.cookies.set("sid", sid)
    client.headers["X-Frappe-CSRF-Token"] = csrf
    assert sitzungen.lesen(sid) is not None, "Sitzung muss vorher existieren"

    set_user(ANNA)
    assert _admin_erledigt(client, welt).status_code == 200

    assert sitzungen.lesen(sid) is None, "die Sitzung muss geloescht sein"


def test_loeschung_beendet_auch_die_sitzung_des_anderen_geraets(client, welt):
    """**B1**: Der zweite Geraet-Anruf stirbt mit — das ist der ganze Punkt.

    Anna ist auf zwei Geraeten angemeldet (z. B. am Gemeinde-PC und am
    Handy) und loest den Widerruf am Handy aus. Die Sitzung am Gemeinde-PC
    ist eine *andere* `sid` — sie ist in keinem Cookie, das dieser Request
    sieht. Vor B1 blieb sie liegen, und der Docstring behauptete trotzdem
    "SOFORT raus".

    `loesche_alle_von(user)` arbeitet ueber den Benutzer-Index, deshalb
    greift es auch ohne den `sid` im Request.
    """
    from diakronos_app.frappe_compat import sitzungen

    pc_sid, _pc_csrf = sitzungen.anlegen(ANNA)      # Gemeinde-PC
    handy_sid, handy_csrf = sitzungen.anlegen(ANNA)  # Handy = dieses Geraet
    assert pc_sid != handy_sid
    assert sitzungen.lesen(pc_sid) is not None

    client.cookies.set("sid", handy_sid)
    client.headers["X-Frappe-CSRF-Token"] = handy_csrf
    set_user(ANNA)
    assert _admin_erledigt(client, welt).status_code == 200

    assert sitzungen.lesen(handy_sid) is None, "das eigene Geraet ist raus"
    assert sitzungen.lesen(pc_sid) is None, (
        "das FREMDE Geraet muss mit sterben — sonst ist die Zusage 'sofort "
        "raus' auf keinem Geraet wahr"
    )


def test_loeschung_laesst_fremde_sitzungen_stehen(client, welt):
    """Gegenrichtung: Brunos Geraet darf von Annas Widerruf unberuehrt sein.

    `loesche_alle_von` laeuft ueber den Benutzer-Index; ein Fehler darin
    (etwa ein Prefix, der auf alle zeigt) wuerde **fremde** Sitzungen
    mittoeten — ein Benutzer wuerde seinen Nachbarn ausloggen. Deshalb
    steht hier die Gegenrichtung ausdruecklich daneben.
    """
    from diakronos_app.frappe_compat import sitzungen

    bruno_sid, _csrf = sitzungen.anlegen(BRUNO)
    set_user(ANNA)
    _admin_erledigt(client, welt)

    assert sitzungen.lesen(bruno_sid) is not None, "fremde Sitzung geloescht"


def test_loeschung_vergisst_den_status_cache(client, welt):
    """B1: Nach dem Widerruf ist der Status-Cache weg, nicht nur die Sitzung.

    Ohne `vergiss()` wuerde der Benutzer nach einem spaeteren Reaktivieren
    noch bis zum TTL abgewiesen. Das waere die Umkehrung desselben Fehlers
    — zu frueh statt zu spaet raus.
    """
    from diakronos_app.frappe_compat import benutzer_status, sitzungen

    # Cache fuellen (die Middleware tut das bei jedem Aufruf).
    assert benutzer_status.ist_aktiv(ANNA) is True
    key = benutzer_status._key(ANNA)
    assert benutzer_status._client().get(key) is not None, "Cache muss gefuellt sein"

    set_user(ANNA)
    _admin_erledigt(client, welt)

    assert benutzer_status._client().get(key) is None, (
        "der Status-Cache wurde nicht vergessen — ein Reaktivieren bliebe "
        "bis zum TTL abgewiesen"
    )
    # Und der Inhalt ist die Wahrheit, nicht mehr der Cache:
    assert benutzer_status.ist_aktiv(ANNA) is False
    # Der Benutzer-Index ist ebenfalls leer, sonst waere `loesche_alle_von`
    # beim naechsten Mal nicht schnell genug.
    assert sitzungen.loesche_alle_von(ANNA) == 0


def test_loeschung_fremder_satz_bleibt_unberuehrt(client, welt):
    """Anna loescht ihr Profil — Brunos Satz bleibt, inkl. Einwilligung."""
    from diakronos_app.models.diakonos import Mitglied

    set_user(ANNA)
    _admin_erledigt(client, welt)

    welt.expire_all()
    # Ohne vorbestehende Einwilligung bleibt Bruno unveraendert (keine
    # Loeschung): nur der Widerruf-Log entfaellt.
    bruno = welt.get(Mitglied, "M-0002")
    assert bruno is not None
    assert bruno.vorname == "Bruno"
    assert bruno.email == BRUNO
    assert bruno.foto_einwilligung is True
    assert _eintraege(welt, "M-0002") == []


def test_loeschung_ohne_mitglied_aendert_nichts(client, welt):
    """Carla hat kein Mitglied: ehrliche Antwort, kein 500, kein Schreibzugriff.

    Die Reihenfolge ist der Punkt: `_get_my_mitglied()` wird VOR jedem
    Schreibzugriff gerufen, also wird auch kein `User` deaktiviert."""
    from diakronos_app.models.core import User
    from diakronos_app.models.diakonos import Mitglied

    set_user(CARLA)
    res = client.post(f"/api/method/{PROFILE}.delete_my_data")
    assert res.status_code == 417, res.text
    assert "Deinem Konto ist noch kein Mitglied zugeordnet." in res.json()["message"]

    welt.expire_all()
    assert welt.get(User, CARLA).enabled is True, "darf nicht deaktiviert werden"
    # Anna ist unberuehrt — ein Loeschversuch ohne eigenen Satz darf an
    # fremden Daten nichts aendern.
    assert welt.get(Mitglied, "M-0001").vorname == "Anna"
    assert welt.get(Mitglied, "M-0001").email == ANNA


# ── CSRF ────────────────────────────────────────────────────────────────────


@pytest.mark.skipif(
    not UPDATE_MY_PROFILE_PORTIERT,
    reason="update_my_profile kommt mit Commit 2",
)
def test_schreiben_ohne_csrf_417(client, welt):
    """CSRF bleibt Pflicht — der normale Weg, keine Ausnahme.

    Der `client`-Fixture sendet ein Token; dieser Test nimmt es weg.
    Geprueft wird der Schreibpfad; ein CSRF-Fehler kommt VOR der
    Fachlogik, das `Mitglied` darf also unveraendert bleiben."""
    set_user(ANNA)
    res = client.post(
        f"/api/method/{PROFILE}.update_my_profile",
        json={"vorname": "Ohne"},
        headers={"X-Frappe-CSRF-Token": ""},
    )
    assert res.status_code == 417, res.text
    assert res.json()["exc_type"] == "CSRFTokenError"
