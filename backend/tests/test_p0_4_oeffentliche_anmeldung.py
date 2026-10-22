"""P0-4 — Oeffentliche Anmeldung/Registrierung lauffaehig.

Befunde aus der Nachtpruefung (GESAMTBERICHT.md, Paket P0-4):
  UXD-R1  kritisch  oeffentliche Anmeldung laesst sich nie absenden
                    (`window.__diakronos` wird von `spa.py` nie gesetzt)
  UXD-R2  hoch      neue Registrierungslinks bekommen keinen Token
                    (`slug`/`link_anzeige`/`anmeldungen_count` bleiben NULL)
  UXD-R3  hoch      kopierter Link ist ein relativer Pfad -> 404
  UXD-R27 niedrig   Registrierungsseite zeigt Serverfehler nie an
  BLD-R3  mittel    Registrierung verschluckt ungueltige Kind-/Antwortdaten
                    spurlos (HTTP 200, keine Logzeile)
  OP-ADMIN-9 mittel oeffentlicher Endpunkt gibt rohes SQL samt Schema,
                    Parametern und interner IP zurueck
  OP-ADMIN-R1 mittel IP der DSGVO-Einwilligung faelschbar per X-Forwarded-For
  OP-CHOR-4 mittel  geteilter Plan-Link geht bei der Anmeldung verloren
                    (Hash erreicht das redirect-to-Feld nie)
  UXM-R18 niedrig   Seite "Anmeldung": Rolle ist Freitext, halbfertige Zeilen
                    verschwinden still, zweistufiges Speichern

Diese Datei ist der Reproduktionstest: an der Basis sind die Faelle rot.
"""

from __future__ import annotations

import json
import logging
import re

import pytest

import diakronos_app.api  # noqa: F401 — registriert alle portierten Endpunkte
from diakronos_app.frappe_compat.session import set_user

MODUL = "diakronos.diakonos.api.registrierung"
MODUL_LINK = "diakronos.diakonos.api.registrierungslink_api"

SLUG = "abc123slug"
LINK = "RL-1"
ADMIN = "mitgliederadmin@example.org"
MITGLIED = "einfach@example.org"


# ── Fixtures ────────────────────────────────────────────────────────────────


def _link(**werte):
    from diakronos_app.models.diakonos import Registrierungslink

    daten = {
        "name": LINK,
        "bezeichnung": "Einladung",
        "typ": "Mitglied-Registrierung",
        "aktiv": True,
        "slug": SLUG,
        "max_anmeldungen": 0,
        "anmeldungen_count": 0,
        "docstatus": 0,
        "idx": 0,
    }
    daten.update(werte)
    return Registrierungslink(**daten)


@pytest.fixture()
def welt(patched_db):
    """Registrierungslink + Anmeldeformular (wie test_p4e_registrierung)."""
    from diakronos_app.models.diakonos import (
        Anmeldeformular,
        AnmeldeformularFeld,
    )

    sess = patched_db()
    # Der Link traegt das Formular: nur so liefert `validate_token` Felder und
    # `mit_kinder` (die Angaben des Formulars).
    sess.add(_link(anmeldeformular="AF-1"))
    sess.add(
        Anmeldeformular(
            name="AF-1",
            bezeichnung="Standard",
            mit_kinder=True,
            mit_gaesten=True,
            docstatus=0,
            idx=0,
        )
    )
    sess.add_all(
        [
            AnmeldeformularFeld(
                name="AFF-1",
                parent="AF-1",
                parentfield="felder",
                parenttype="Anmeldeformular",
                idx=1,
                label="Ernaehrung",
                feldtyp="Select",
                optionen="omnivor,vegan",
                pflichtfeld=True,
                fuer_gaeste=False,
                fuer_kinder=True,
                docstatus=0,
            ),
        ]
    )
    sess.commit()
    yield sess
    sess.close()


@pytest.fixture()
def admin_client(client, patched_db):
    """Angemeldeter Mitgliederadministrator (create_link verlangt die Rolle)."""
    from diakronos_app.models.core import HasRole, User

    sess = patched_db()
    if sess.get(User, ADMIN) is None:
        sess.add(User(name=ADMIN, email=ADMIN, full_name="Admin", enabled=True))
    if not sess.query(HasRole).filter_by(parent=ADMIN, role="Mitgliederadministrator").first():
        sess.add(HasRole(name=f"{ADMIN}-MA", parent=ADMIN, parenttype="User",
                         parentfield="roles", idx=1, role="Mitgliederadministrator"))
    sess.commit()
    sess.close()

    set_user(ADMIN)
    try:
        yield client
    finally:
        set_user("Administrator")


# ════════════════════════════════════════════════════════════════════════════
# UXD-R1 — oeffentliche Seiten uebermitteln das Token nicht (window.__diakronos)
# ════════════════════════════════════════════════════════════════════════════

OEFFENTLICHE_SEITEN = [
    ("registrierung", 'src/registrierung/main.js'),
    ("gast", 'src/gast/main.js'),
]


@pytest.mark.parametrize("seite,_entry", OEFFENTLICHE_SEITEN)
def test_uxd_r1_seite_ist_ohne_sitzung_erreichbar(guest_client, seite, _entry):
    """Die Seite selbst liefert HTML (kein Login-Redirect)."""
    r = guest_client.get(f"/diakonos/{seite}", params={"token": SLUG})
    assert r.status_code == 200, r.text
    assert 'id="app"' in r.text


@pytest.mark.parametrize("seite,_entry", OEFFENTLICHE_SEITEN)
def test_uxd_r1_window_diakronos_mit_token(guest_client, welt, seite, _entry):
    """`window.__diakronos` muss Token und Linkzustand tragen.

    Ohne dieses Objekt liest `registrierung/App.vue:143` einen leeren Token,
    und der Absendeversuch laeuft in HTTP 403 "Kein Registrierungstoken".
    """
    r = guest_client.get(f"/diakonos/{seite}", params={"token": SLUG})
    assert r.status_code == 200, r.text
    m = re.search(r"window\.__diakronos\s*=\s*(\{.*?\});", r.text, re.S)
    assert m, "window.__diakronos fehlt im HTML der oeffentlichen Seite"
    daten = json.loads(m.group(1))
    assert daten["token"] == SLUG
    assert daten["linkFehler"] == ""
    assert isinstance(daten["felder"], list)
    assert isinstance(daten["dokumente"], list)
    assert daten["mitKinder"] == 1


def test_uxd_r1_ungueltiger_token_meldet_linkfehler(guest_client, welt):
    """Ungueltig/abgelaufen/voll -> `linkFehler` ist gesetzt ("Zugang nicht moeglich")."""
    r = guest_client.get("/diakonos/registrierung", params={"token": "gibt-es-nicht"})
    assert r.status_code == 200, r.text
    m = re.search(r"window\.__diakronos\s*=\s*(\{.*?\});", r.text, re.S)
    assert m
    daten = json.loads(m.group(1))
    assert daten["linkFehler"], "bei ungueltigem Token muss linkFehler gesetzt sein"
    assert daten["token"] == ""


def test_uxd_r1_fehlender_token_ist_kein_serverfehler(guest_client, welt):
    """Ohne `?token=` bleibt die Seite 200 und zeigt den Linkfehler."""
    r = guest_client.get("/diakonos/registrierung")
    assert r.status_code == 200, r.text
    assert "window.__diakronos" in r.text


def test_uxd_r1_bootobjekt_bleibt_am_platz(guest_client, welt):
    """Die Aenderung darf das regulaere Boot-Objekt nicht verdraengen."""
    r = guest_client.get("/diakonos/registrierung", params={"token": SLUG})
    assert "window.__DIakonosBOOT" in r.text


# ════════════════════════════════════════════════════════════════════════════
# UXD-R2 — neue Links haben keinen Token
# ════════════════════════════════════════════════════════════════════════════

def test_uxd_r2_create_link_erzeugt_token_und_adresse(admin_client, patched_db):
    """`slug`, `link_anzeige` und `anmeldungen_count` werden gefuellt."""
    from diakronos_app.models.diakonos import Registrierungslink

    r = admin_client.post(
        f"/api/method/{MODUL_LINK}.create_link",
        json={"bezeichnung": "Sommerfreizeit", "typ": "Mitglied-Registrierung"},
    )
    assert r.status_code == 200, r.text
    link = r.json()["message"]["link"]
    assert link["slug"], "slug ist leer — der Link ist unbrauchbar"
    assert link["anmeldungen_count"] == 0

    sess = patched_db()
    try:
        roh = sess.get(Registrierungslink, link["name"])
        assert roh.slug, "slug wurde nicht gespeichert"
        assert roh.link_anzeige, "link_anzeige wurde nicht gespeichert"
        assert roh.anmeldungen_count == 0
    finally:
        sess.close()


def test_uxd_r2_neuer_link_ist_ueber_validate_token_gueltig(admin_client, welt):
    """Gegenprobe: der erzeugte Token wird von `validate_token` akzeptiert."""
    r = admin_client.post(
        f"/api/method/{MODUL_LINK}.create_link",
        json={"bezeichnung": "Sommerfreizeit", "typ": "Mitglied-Registrierung"},
    )
    slug = r.json()["message"]["link"]["slug"]

    r2 = admin_client.get(f"/api/method/{MODUL}.validate_token", params={"token": slug})
    assert r2.status_code == 200, r2.text
    assert r2.json()["message"]["typ"] == "Mitglied-Registrierung"


def test_uxd_r2_tokens_sind_verschieden(admin_client):
    """Zwei Links duerfen nicht denselben Token tragen."""
    slugs = set()
    for name in ("Freizeit A", "Freizeit B"):
        r = admin_client.post(
            f"/api/method/{MODUL_LINK}.create_link",
            json={"bezeichnung": name, "typ": "Mitglied-Registrierung"},
        )
        slugs.add(r.json()["message"]["link"]["slug"])
    assert len(slugs) == 2


def test_uxd_r2_link_anzeige_traegt_diakonos_pfad(admin_client):
    """UXD-R3: die Anzeige ist ein absoluter Pfad `/diakonos/...?token=`."""
    r = admin_client.post(
        f"/api/method/{MODUL_LINK}.create_link",
        json={"bezeichnung": "Sommerfreizeit", "typ": "Mitglied-Registrierung"},
    )
    link = r.json()["message"]["link"]
    assert link["link_anzeige"].startswith("/diakonos/registrierung?token="), link["link_anzeige"]
    assert link["slug"] in link["link_anzeige"]


def test_uxd_r3_gast_link_zeigt_auf_gast_seite(admin_client):
    r = admin_client.post(
        f"/api/method/{MODUL_LINK}.create_link",
        json={"bezeichnung": "Gastlink", "typ": "Gast-Anmeldung"},
    )
    link = r.json()["message"]["link"]
    assert link["link_anzeige"].startswith("/diakonos/gast?token="), link["link_anzeige"]


def test_uxd_r3_altpfad_registrierung_leitet_weiter(guest_client, welt):
    """Der Altpfad `/registrierung?token=…` darf kein 404 mehr sein."""
    r = guest_client.get("/registrierung", params={"token": SLUG}, follow_redirects=False)
    assert r.status_code in (200, 303, 307), r.text


# ════════════════════════════════════════════════════════════════════════════
# BLD-R3 — ungueltige Kind-/Antwortdaten verschwinden spurlos
# ════════════════════════════════════════════════════════════════════════════

def _anzahl(patched_db, modell):
    sess = patched_db()
    try:
        return sess.query(modell).count()
    finally:
        sess.close()


def test_bld_r3_ungueltige_kinder_werden_geloggt(client, welt, caplog):
    """Ein fehlerhafter Kind-Datensatz darf nicht ohne Logzeile verschwinden."""
    with caplog.at_level(logging.WARNING):
        r = client.post(
            f"/api/method/{MODUL}.submit_registrierung",
            data={
                "token": SLUG,
                "vorname": "Anna",
                "nachname": "Beispiel",
                "kinder": json.dumps([
                    {"vorname": "Kind", "nachname": "Beispiel", "geburtstag": "kein-datum"},
                ]),
                "dsgvo": "1",
            },
        )
    assert r.status_code == 200, r.text

    fehlerzeilen = [
        rec for rec in caplog.records
        if rec.levelno >= logging.WARNING and "Kind" in rec.getMessage()
    ]
    assert fehlerzeilen, "ungueltige Kinddaten wurden spurlos verschluckt (BLD-R3)"


def test_bld_r3_ungueltige_antworten_werden_geloggt(client, welt, caplog, monkeypatch):
    """Dasselbe fuer die Antwortzeilen.

    SQLite erzwingt keine Spaltenlaengen, ein langer Text loest also keinen
    Fehler aus. Geprueft wird deshalb der Vertrag selbst: schlaegt das
    Schreiben einer Kindzeile fehl, darf der Vorgang NICHT scheitern (wie im
    Original) — aber der Fehler darf nicht spurlos verschwinden (BLD-R3).
    """
    from diakronos_app.api import registrierung as reg

    def platzt(*_args, **_kwargs):
        raise RuntimeError("Kindzeile konnte nicht geschrieben werden")

    monkeypatch.setattr(reg, "_child_insert", platzt)

    with caplog.at_level(logging.WARNING):
        r = client.post(
            f"/api/method/{MODUL}.submit_registrierung",
            data={
                "token": SLUG,
                "vorname": "Anna",
                "nachname": "Beispiel",
                "antworten": json.dumps([{"label": "Ernaehrung", "wert": "vegan"}]),
                "dsgvo": "1",
            },
        )
    assert r.status_code == 200, r.text
    assert r.json()["message"]["success"] is True
    fehlerzeilen = [
        rec for rec in caplog.records
        if rec.levelno >= logging.WARNING and "Antwort" in rec.getMessage()
    ]
    assert fehlerzeilen, "ungueltige Antwortdaten wurden spurlos verschluckt (BLD-R3)"


def test_bld_r3_gueltige_kinder_landen_in_der_db(client, welt, patched_db):
    """Gegenprobe: der Normalfall bleibt unveraendert erfolgreich."""
    from diakronos_app.models.diakonos import AnmeldungKind

    r = client.post(
        f"/api/method/{MODUL}.submit_registrierung",
        data={
            "token": SLUG,
            "vorname": "Anna",
            "nachname": "Beispiel",
            "kinder": json.dumps([
                {"vorname": "Kind", "nachname": "Beispiel", "geburtstag": "2015-05-01"},
            ]),
            "dsgvo": "1",
        },
    )
    assert r.status_code == 200, r.text
    assert _anzahl(patched_db, AnmeldungKind) == 1


# ════════════════════════════════════════════════════════════════════════════
# OP-ADMIN-9 / OP-ADMIN-R1 — rohes SQL und faelschbare IP am oeffentlichen Ende
# ════════════════════════════════════════════════════════════════════════════

def test_op_admin_9_kein_sql_im_fehlertext(client, welt):
    """Ungueltiges Geburtsdatum: verstaendliche Meldung, kein SQL/Schema."""
    r = client.post(
        f"/api/method/{MODUL}.submit_registrierung",
        data={
            "token": SLUG,
            "vorname": "Anna",
            "nachname": "Beispiel",
            "geburtstag": "1990-02-31",
            "dsgvo": "1",
        },
    )
    assert r.status_code >= 400, "ungueltiges Datum muss abgewiesen werden"
    text = r.text
    for verboten in ("psycopg", "INSERT INTO", "parameters", "[SQL:", "sqlalche.me",
                     "ip_adresse", "dsgvo_text_snapshot"):
        assert verboten not in text, f"SQL-Detail '{verboten}' im Clientfehler: {text[:400]}"


def test_op_admin_9_datum_vorpruefung_liefert_klartext(client, welt):
    r = client.post(
        f"/api/method/{MODUL}.submit_registrierung",
        data={
            "token": SLUG,
            "vorname": "Anna",
            "nachname": "Beispiel",
            "geburtstag": "1990-02-31",
            "dsgvo": "1",
        },
    )
    assert "Geburtsdatum" in r.text, r.text[:400]


def test_op_admin_9_ungueltiges_kinddatum_wird_gemeldet(client, welt):
    r = client.post(
        f"/api/method/{MODUL}.submit_registrierung",
        data={
            "token": SLUG,
            "vorname": "Anna",
            "nachname": "Beispiel",
            "kinder": json.dumps([{"vorname": "K", "nachname": "B", "geburtstag": "kein-datum"}]),
            "dsgvo": "1",
        },
    )
    assert r.status_code == 200
    assert "02-31" not in r.text


def test_op_admin_r1_xff_wird_nicht_ungeprueft_uebernommen(client, welt, patched_db, monkeypatch):
    """Ohne `BEHIND_PROXY` darf X-Forwarded-For die gespeicherte IP nicht setzen."""
    from diakronos_app.models.diakonos import Anmeldung

    r = client.post(
        f"/api/method/{MODUL}.submit_registrierung",
        data={"token": SLUG, "vorname": "Anna", "nachname": "Beispiel", "dsgvo": "1"},
        headers={"X-Forwarded-For": "203.0.113.9"},
    )
    assert r.status_code == 200, r.text

    sess = patched_db()
    try:
        anm = sess.query(Anmeldung).first()
        assert anm is not None
        assert anm.ip_adresse != "203.0.113.9", (
            "X-Forwarded-For wurde ungeprueft als Einwilligungsnachweis gespeichert"
        )
    finally:
        sess.close()


def test_op_admin_r1_hinter_proxy_wird_xff_genutzt(client, welt, patched_db, monkeypatch):
    """Mit `BEHIND_PROXY=1` gilt die erste XFF-Adresse (gewolltes Verhalten)."""
    from diakronos_app import request_context
    from diakronos_app.models.diakonos import Anmeldung

    monkeypatch.setattr(request_context, "_proxy_vorausgesetzt", lambda: True)

    r = client.post(
        f"/api/method/{MODUL}.submit_registrierung",
        data={"token": SLUG, "vorname": "Anna", "nachname": "Beispiel", "dsgvo": "1"},
        headers={"X-Forwarded-For": "203.0.113.9, 198.51.100.1"},
    )
    assert r.status_code == 200, r.text

    sess = patched_db()
    try:
        anm = sess.query(Anmeldung).first()
        assert anm.ip_adresse == "203.0.113.9"
    finally:
        sess.close()


# ════════════════════════════════════════════════════════════════════════════
# OP-CHOR-4 — geteilter Plan-Link geht bei der Anmeldung verloren
# ════════════════════════════════════════════════════════════════════════════

def test_op_chor_4_anmeldemaske_pflegt_den_hash_nach(guest_client, welt):
    """Die Maske muss `location.hash` in das Feld `redirect-to` nachtragen.

    Der Hash erreicht den Server nie (Browser senden ihn nicht mit). Ohne das
    Skript landet ein geteilter Deeplink `#/planrahmen/plan/…` nach der
    Anmeldung auf dem Dashboard.
    """
    r = guest_client.get("/diakonos")
    assert r.status_code == 200, r.text
    assert 'name="redirect-to"' in r.text
    assert "location.hash" in r.text, "die Anmeldemaske traegt den Hash nicht nach"


def test_op_chor_4_altpfad_maske_pflegt_den_hash_nach(guest_client, welt):
    """Dasselbe fuer die Maske, die ein Altpfad ausliefert."""
    from diakronos_app.spa import render_login

    html = render_login("/diakonos/planrahmen")
    assert "location.hash" in html


def test_op_chor_4_zentrale_maske_pflegt_den_hash_nach():
    """Auch die SEC1-Anmeldeseite (/login) traegt den Hash nach."""
    from diakronos_app.anmeldung.routen import erstelle_anmeldeseite

    html = erstelle_anmeldeseite("/diakonos")
    assert 'name="redirect-to"' in html
    assert "location.hash" in html


def test_op_chor_4_ziel_mit_hash_wird_akzeptiert():
    """Der Server laesst ein Fragment im Ziel durch (Voraussetzung)."""
    from diakronos_app.api.auth import _redirect_ziel

    ziel = _redirect_ziel("/diakonos#/planrahmen/plan/P-1")
    assert ziel == "/diakonos#/planrahmen/plan/P-1"
    # Offene Weiterleitung bleibt verboten.
    assert _redirect_ziel("https://evil.de") != "https://evil.de"

