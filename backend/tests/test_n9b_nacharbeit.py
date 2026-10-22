"""N9b — Nacharbeit N9: Einwilligung angezeigt = gespeichert, Einstellungen
wirksam, R-N8-Reste.

Quelle: die vorausgehenden Reviews (H-1 hoch, M-1/M-2 mittel; R-N8-Punkte 1-4, R-N5 N-3).

Diese Datei ist der Reproduktions- und Absicherungstest:
  H-1  Der auf der oeffentlichen Seite ANGEZEIGTE Einwilligungstext muss genau
       dem GLEICHEN Text entsprechen, den `submit_*` als Beleg speichert.
  M-2  Nur die VEROEFFENTLICHTE Fassung gilt fuer neue Anmeldungen.
  M-1  Die Einstellungen wirken (Willkommenstext, Link-Vorgaben, oeffentliche
       Adresse als Linkbasis).
  R-N8 Rolle aus Mitgliedsstatus, abgelehnte Zuordnungen sichtbar, Modus
       „anlegen“ nur System Manager.
"""

from __future__ import annotations

import json
import re

import pytest

import diakronos_app.api  # noqa: F401 — registriert alle portierten Endpunkte

GEMEINDE = "/api/method/diakronos.diakonos.api.gemeinde."
LINK_API = "/api/method/diakronos.diakonos.api.registrierungslink_api."
ZUGANG = "/api/method/diakronos.diakonos.api.zugang."
SLUG = "n9bslug123"
LINK = "RL-N9B"
ADMIN = "n9b-admin@example.org"


# ── Fixtures ────────────────────────────────────────────────────────────────


def _oeffentlich_js(html: str) -> dict:
    """`window.__diakronos` aus dem HTML der oeffentlichen Seite lesen."""
    m = re.search(r"window\.__diakronos\s*=\s*(\{.*?\});", html, re.S)
    assert m, "window.__diakronos fehlt im HTML"
    return json.loads(m.group(1))


@pytest.fixture()
def admin_client(client, patched_db):
    """Angemeldeter Mitgliederadministrator (create_link verlangt die Rolle)."""
    from diakronos_app.frappe_compat.session import set_user
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


def _texte_speichern(patched_db, einwilligung, *, veroeffentlicht=True):
    """Schreibt die Datenschutz-Texte direkt (unabhaengig vom Admin-Client).

    N9b (M-2): Entwurf (``datenschutz_text``) und veroeffentlichte Fassung
    (``datenschutz_text_veroeffentlicht``) sind getrennte Zeilen. Mit
    ``veroeffentlicht=True`` wird zusaetzlich die veroeffentlichte Fassung
    gesetzt — genau wie ``datenschutz_speichern`` es tut.
    """
    from datetime import datetime

    from diakronos_app.models.gemeinde import (
        DATENSCHUTZ_TEXT_NAME,
        DATENSCHUTZ_VEROEFFENTLICHT_NAME,
        DatenschutzText,
        DatenschutzTextVeroeffentlicht,
    )

    sess = patched_db()
    zeile = sess.get(DatenschutzText, DATENSCHUTZ_TEXT_NAME)
    if zeile is None:
        zeile = DatenschutzText(name=DATENSCHUTZ_TEXT_NAME, version=1)
        sess.add(zeile)
    zeile.einwilligung = einwilligung
    zeile.datenschutzerklaerung = "Erklaerung zur Verarbeitung."
    zeile.aufbewahrung = "Aufbewahrung: bis zum Widerruf."
    zeile.veroeffentlicht = veroeffentlicht
    zeile.version = 1
    zeile.modified = datetime.now()

    if veroeffentlicht:
        pub = sess.get(DatenschutzTextVeroeffentlicht, DATENSCHUTZ_VEROEFFENTLICHT_NAME)
        if pub is None:
            pub = DatenschutzTextVeroeffentlicht(
                name=DATENSCHUTZ_VEROEFFENTLICHT_NAME, version=1
            )
            sess.add(pub)
        pub.einwilligung = einwilligung
        pub.datenschutzerklaerung = "Erklaerung zur Verarbeitung."
        pub.aufbewahrung = "Aufbewahrung: bis zum Widerruf."
        pub.version = int(pub.version or 1)
        pub.modified = datetime.now()

    sess.commit()
    sess.close()


@pytest.fixture()
def link(patched_db):
    """Ein gueltiger Registrierungs-Link (ohne Formular -> keine Felder)."""
    from diakronos_app.models.diakonos import Registrierungslink

    sess = patched_db()
    sess.add(
        Registrierungslink(
            name=LINK,
            bezeichnung="Einladung",
            typ="Mitglied-Registrierung",
            aktiv=True,
            slug=SLUG,
            max_anmeldungen=0,
            anmeldungen_count=0,
            docstatus=0,
            idx=0,
        )
    )
    sess.commit()
    sess.close()


@pytest.fixture()
def gast_link(patched_db):
    """Ein gueltiger Gast-Anmeldungs-Link."""
    from diakronos_app.models.diakonos import Registrierungslink

    sess = patched_db()
    sess.add(
        Registrierungslink(
            name="RL-N9B-GAST",
            bezeichnung="Gast-Einladung",
            typ="Gast-Anmeldung",
            aktiv=True,
            slug="n9bgastslug",
            max_anmeldungen=0,
            anmeldungen_count=0,
            docstatus=0,
            idx=0,
        )
    )
    sess.commit()
    sess.close()


def _veroeffentliche(client, einwilligung, *, veroeffentlicht=True, extra=""):
    """Pflegt die Datenschutz-Texte (Veroeffentlichung wahlweise)."""
    r = client.post(GEMEINDE + "datenschutz_speichern", json={
        "einwilligung": einwilligung,
        "datenschutzerklaerung": "Erklaerung " + extra,
        "aufbewahrung": "Aufbewahrung " + extra,
        "veroeffentlicht": veroeffentlicht,
    })
    assert r.status_code == 200, r.text
    return r


# ════════════════════════════════════════════════════════════════════════════
# H-1 — Angezeigt = gespeichert (Art. 7 DSGVO)
# ════════════════════════════════════════════════════════════════════════════


def test_h1_veroeffentlichter_text_wird_angezeigt_und_belegt(guest_client, link, patched_db):
    """Der gepflegte, veroeffentlichte Text erscheint UND wird als Beleg gespeichert.

    Genau der Wortlaut, den die Seite zeigt (window.__diakronos.texte), muss in
    `dsgvo_text_snapshot` der Anmeldung landen — sonst belegt die Anmeldung
    einen Text, den die Person nie gesehen hat.
    """
    from diakronos_app.models.diakonos import Anmeldung

    EIGEN = "Eigener Einwilligungstext der Gemeinde N9b (Fassung 1)."
    _texte_speichern(patched_db, EIGEN)

    # 1. Angezeigt: die oeffentliche Seite traegt genau diesen Text.
    r = guest_client.get("/diakonos/registrierung", params={"token": SLUG})
    assert r.status_code == 200, r.text
    daten = _oeffentlich_js(r.text)
    assert daten["texte"]["einwilligung"] == EIGEN

    # 2. Gespeichert: der Snapshot ist GENAU der angezeigte Text.
    r = guest_client.post(
        "/api/method/diakronos.diakonos.api.registrierung.submit_registrierung",
        json={"token": SLUG, "vorname": "Lena", "nachname": "Beleg",
              "email": "", "telefon": "", "geburtstag": "",
              "kommentar": "", "antworten": "[]", "kinder": "[]", "dsgvo": True},
    )
    assert r.status_code == 200, r.text
    name = r.json()["message"]["anmeldung"]

    from diakronos_app.db import SessionLocal
    with SessionLocal() as s:
        zeile = s.get(Anmeldung, name)
        assert zeile is not None
        # N-1 (R-N10): der Beleg traegt den Fassungskopf vor dem angezeigten
        # Wortlaut — der Wortlaut selbst steht unveraendert darin.
        assert zeile.dsgvo_text_snapshot.startswith("Fassung ")
        assert EIGEN in zeile.dsgvo_text_snapshot
        assert daten["texte"]["einwilligung"] == EIGEN


def test_h1_gastseite_zeigt_denselben_text(guest_client, gast_link, patched_db):
    """Auch die Gast-Anmeldung zeigt den veroeffentlichten Text."""
    from diakronos_app.models.diakonos import Registrierungslink

    EIGEN = "Gast-Einwilligungstext N9b."
    _texte_speichern(patched_db, EIGEN)

    r = guest_client.get("/diakonos/gast", params={"token": "n9bgastslug"})
    assert r.status_code == 200, r.text
    daten = _oeffentlich_js(r.text)
    assert daten["texte"]["einwilligung"] == EIGEN


def test_h1_standardtext_ohne_veroeffentlichung(guest_client, link, patched_db):
    """Ohne veroeffentlichten Text greift der Standardtext (Anzeige UND Beleg)."""
    from diakronos_app.api import gemeinde, registrierung

    r = guest_client.get("/diakonos/registrierung", params={"token": SLUG})
    daten = _oeffentlich_js(r.text)
    assert daten["texte"]["einwilligung"] == gemeinde.STANDARD_EINWILLIGUNG
    assert registrierung._dsgvo_text_aktuell() == daten["texte"]["einwilligung"]


# ════════════════════════════════════════════════════════════════════════════
# M-2 — veroeffentlicht wirksam
# ════════════════════════════════════════════════════════════════════════════


def test_m2_entwurf_gilt_nicht_fuer_neue_anmeldungen(guest_client, link, patched_db):
    """Ein NICHT veroeffentlichter Text aendert weder Anzeige noch Beleg."""
    from diakronos_app.api import gemeinde, registrierung

    ENTWURF = "Noch nicht freigegebener Entwurf."
    _texte_speichern(patched_db, ENTWURF, veroeffentlicht=False)

    # Anzeige: Standardtext, nicht der Entwurf.
    r = guest_client.get("/diakonos/registrierung", params={"token": SLUG})
    daten = _oeffentlich_js(r.text)
    assert daten["texte"]["einwilligung"] == gemeinde.STANDARD_EINWILLIGUNG
    assert daten["texte"]["einwilligung"] != ENTWURF
    # Beleg-Snapshot: ebenfalls Standardtext.
    assert registrierung._dsgvo_text_aktuell() == gemeinde.STANDARD_EINWILLIGUNG


def test_m2_nach_veroeffentlichung_gilt_neue_fassung(patched_db):
    """Veroeffentlichen schaltet die gepflegte Fassung frei."""
    from diakronos_app.api import registrierung

    _texte_speichern(patched_db, "Fassung A", veroeffentlicht=False)
    assert registrierung._dsgvo_text_aktuell() != "Fassung A"
    _texte_speichern(patched_db, "Fassung A", veroeffentlicht=True)
    assert registrierung._dsgvo_text_aktuell() == "Fassung A"


def test_m2_entwurf_loescht_die_veroeffentlichte_fassung_nicht(
    guest_client, admin_client, link, patched_db
):
    """REGRESSION (M-2): ein Speichern OHNE Haken darf die geltende Fassung
    nicht veraendern oder gar vernichten.

    Vorher lag Entwurf und geltende Fassung in DERSELBEN Zeile: ein
    unveroeffentlichter Entwurf ueberschrieb den Inhalt und die oeffentliche
    Seite fiel auf den Standardtext zurueck — obwohl die Oberflaeche
    verspricht, dass der bisherige Text stehen bleibt.
    """
    from diakronos_app.api import gemeinde, registrierung

    GELTEND = "Veroeffentlichte Fassung A der Gemeinde."
    ENTWURF = "Bearbeiteter Entwurf B (noch nicht freigegeben)."

    # 1. Fassung A veroeffentlichen (ueber die echte Admin-API).
    r = admin_client.post(GEMEINDE + "datenschutz_speichern", json={
        "einwilligung": GELTEND,
        "datenschutzerklaerung": "Erklaerung A",
        "aufbewahrung": "Aufbewahrung A",
        "veroeffentlicht": True,
    })
    assert r.status_code == 200, r.text
    assert gemeinde.wirksame_texte()["einwilligung"] == GELTEND

    # 2. Entwurf B speichern — OHNE Haken.
    r = admin_client.post(GEMEINDE + "datenschutz_speichern", json={
        "einwilligung": ENTWURF,
        "datenschutzerklaerung": "Erklaerung B",
        "aufbewahrung": "Aufbewahrung B",
        "veroeffentlicht": False,
    })
    assert r.status_code == 200, r.text

    # 3. Die geltende Fassung ist UNVERAENDERT A (nicht B, nicht Standard).
    assert gemeinde.wirksame_texte()["einwilligung"] == GELTEND
    assert registrierung._dsgvo_text_aktuell() == GELTEND
    seite = guest_client.get("/diakonos/registrierung", params={"token": SLUG})
    assert _oeffentlich_js(seite.text)["texte"]["einwilligung"] == GELTEND

    # 4. Der Entwurf ist gespeichert und wieder lesbar (nichts verloren).
    d = admin_client.post(GEMEINDE + "datenschutz_get_texte").json()["message"]
    assert d["einwilligung"] == ENTWURF
    assert d["veroeffentlicht"] is False
    # Die wirksame Fassung ist ebenfalls Teil der Antwort (UI-Anzeige).
    assert d["wirksam"]["einwilligung"] == GELTEND


# ════════════════════════════════════════════════════════════════════════════
# M-1 — Einstellungen wirksam
# ════════════════════════════════════════════════════════════════════════════


def test_m1_willkommenstext_erscheint_auf_der_oeffentlichen_seite(guest_client, link, client):
    r = client.post(GEMEINDE + "gemeinde_speichern", json={
        "gemeindename": "Versöhnungskirche",
        "willkommenstext": "Schön, dass du da bist.",
    })
    assert r.status_code == 200, r.text
    seite = guest_client.get("/diakonos/registrierung", params={"token": SLUG})
    daten = _oeffentlich_js(seite.text)
    assert daten["willkommenstext"] == "Schön, dass du da bist."


def test_m1_oeffentliche_adresse_ist_die_linkbasis(client):
    """M-1: gepflegte Adresse -> geteilte Links zeigen dorthin."""
    from diakronos_app.anmeldung.registrierungslink import link_anzeige

    r = client.post(GEMEINDE + "gemeinde_speichern", json={
        "gemeindename": "Versöhnungskirche",
        "oeffentliche_adresse": "https://gemeinde.example.org/",
    })
    assert r.status_code == 200, r.text
    assert link_anzeige("Mitglied-Registrierung", "abc") == \
        "https://gemeinde.example.org/diakonos/registrierung?token=abc"


def test_m1_ohne_adresse_bleibt_der_link_relativ(client):
    from diakronos_app.anmeldung.registrierungslink import link_anzeige

    assert link_anzeige("Mitglied-Registrierung", "abc") == \
        "/diakonos/registrierung?token=abc"


def test_m1_linkvorgaben_werden_beim_anlegen_angewendet(admin_client):
    """M-1: leere Felder -> die gepflegten Vorgaben (Laufzeit, Hoechstzahl)."""
    from diakronos_app.db import SessionLocal
    from diakronos_app.models.diakonos import Registrierungslink

    r = admin_client.post(GEMEINDE + "gemeinde_setze_linkvorgaben",
                          json={"link_laufzeit_tage": 7, "link_max_anmeldungen": 42})
    assert r.status_code == 200, r.text

    r = admin_client.post("/api/method/diakronos.diakonos.api.registrierungslink_api.create_link",
                          json={"bezeichnung": "Test", "typ": "Mitglied-Registrierung"})
    assert r.status_code == 200, r.text
    name = r.json()["message"]["link"]["name"]
    with SessionLocal() as s:
        zeile = s.get(Registrierungslink, name)
        assert int(zeile.max_anmeldungen) == 42
        assert zeile.gueltig_bis is not None  # 7 Tage ab heute


def test_m1_ausdruecklicher_wert_schlaegt_die_vorgabe(admin_client):
    """M-1: die Verwaltung kann am einzelnen Link abweichen."""
    from diakronos_app.db import SessionLocal
    from diakronos_app.models.diakonos import Registrierungslink

    admin_client.post(GEMEINDE + "gemeinde_setze_linkvorgaben",
                      json={"link_laufzeit_tage": 7, "link_max_anmeldungen": 42})
    r = admin_client.post("/api/method/diakronos.diakonos.api.registrierungslink_api.create_link",
                          json={"bezeichnung": "Test", "typ": "Mitglied-Registrierung",
                                "max_anmeldungen": 5, "gueltig_bis": "2030-01-01"})
    assert r.status_code == 200, r.text
    name = r.json()["message"]["link"]["name"]
    with SessionLocal() as s:
        zeile = s.get(Registrierungslink, name)
        assert int(zeile.max_anmeldungen) == 5
        assert str(zeile.gueltig_bis)[:10] == "2030-01-01"


def test_m1_ohne_ablauf_uebersteuert_die_vorgabe(admin_client):
    """M-1 (R-N9b): „ohne Ablauf" ist NICHT dasselbe wie ein leeres Feld.

    Eine Gemeinde-Vorgabe von 7 Tagen gilt fuer leere Felder. Waehlt die
    Verwaltung am einzelnen Link ausdruecklich „ohne Ablauf", bekommt der Link
    kein Ablaufdatum — sonst haette sie keine Moeglichkeit, einen unbefristeten
    Link zu erzeugen (das war der Befund aus R-N9b).
    """
    from diakronos_app.db import SessionLocal
    from diakronos_app.models.diakonos import Registrierungslink

    admin_client.post(GEMEINDE + "gemeinde_setze_linkvorgaben",
                      json={"link_laufzeit_tage": 7, "link_max_anmeldungen": 42})
    r = admin_client.post("/api/method/diakronos.diakonos.api.registrierungslink_api.create_link",
                          json={"bezeichnung": "Test", "typ": "Mitglied-Registrierung",
                                "ohne_ablauf": True})
    assert r.status_code == 200, r.text
    name = r.json()["message"]["link"]["name"]
    with SessionLocal() as s:
        zeile = s.get(Registrierungslink, name)
        assert zeile.gueltig_bis is None  # unbefristet, trotz Vorgabe
        assert int(zeile.max_anmeldungen) == 42  # Platzzahl: weiter die Vorgabe


def test_m1_unbegrenzt_uebersteuert_die_vorgabe(admin_client):
    """M-1 (R-N9b): „unbegrenzt" ist NICHT dasselbe wie ein leeres Feld.

    Trotz Gemeinde-Vorgabe (Hoechstzahl 42) bleibt die Platzzahl am einzelnen
    Link 0 = unbegrenzt, wenn die Verwaltung das ausdruecklich waehlt.
    """
    from diakronos_app.db import SessionLocal
    from diakronos_app.models.diakonos import Registrierungslink

    admin_client.post(GEMEINDE + "gemeinde_setze_linkvorgaben",
                      json={"link_laufzeit_tage": 7, "link_max_anmeldungen": 42})
    r = admin_client.post("/api/method/diakronos.diakonos.api.registrierungslink_api.create_link",
                          json={"bezeichnung": "Test", "typ": "Mitglied-Registrierung",
                                "unbegrenzt": True})
    assert r.status_code == 200, r.text
    name = r.json()["message"]["link"]["name"]
    with SessionLocal() as s:
        zeile = s.get(Registrierungslink, name)
        assert int(zeile.max_anmeldungen) == 0  # unbegrenzt, trotz Vorgabe
        assert zeile.gueltig_bis is not None  # Laufzeit: weiter die Vorgabe


def test_m1_ohne_flags_bleibt_es_bei_der_vorgabe(admin_client):
    """M-1: ohne ausdrueckliche Wahl gilt weiter „leer = Vorgabe" (Bestandsschutz)."""
    from diakronos_app.db import SessionLocal
    from diakronos_app.models.diakonos import Registrierungslink

    admin_client.post(GEMEINDE + "gemeinde_setze_linkvorgaben",
                      json={"link_laufzeit_tage": 7, "link_max_anmeldungen": 42})
    r = admin_client.post("/api/method/diakronos.diakonos.api.registrierungslink_api.create_link",
                          json={"bezeichnung": "Test", "typ": "Mitglied-Registrierung"})
    assert r.status_code == 200, r.text
    name = r.json()["message"]["link"]["name"]
    with SessionLocal() as s:
        zeile = s.get(Registrierungslink, name)
        assert int(zeile.max_anmeldungen) == 42
        assert zeile.gueltig_bis is not None


# ════════════════════════════════════════════════════════════════════════════
# R-N8 — Reste
# ════════════════════════════════════════════════════════════════════════════


def _konto(email, *, verified=True, sub="sub-1", name="Person"):
    from diakronos_app.anmeldung.zuordnung import ExternesKonto

    return ExternesKonto(issuer="https://idp.example", sub=sub, email=email,
                         email_verified=verified, name=name)


def test_rn8_rolle_kommt_aus_dem_mitgliedsstatus(patched_db):
    """R-N8-1 / N10-M-2: ein Gast wird weder „Mitglied" noch „Gast".

    Statt der erfundenen Rolle „Gast" (die niemand kennt und die nichts
    bewirkt) traegt ein Nicht-Mitglied gar keine Diakronos-Rolle. Die Rechte
    laufen ueber `Mitglied.status` — die Rolle waere eine zweite, ungenutzte
    Quelle der Wahrheit.
    """
    from diakronos_app.anmeldung.zuordnung import loese_konto_auf
    from diakronos_app.models.core import HasRole
    from diakronos_app.models.diakonos import Mitglied

    sess = patched_db()
    # Kein lokales Konto -> der Zuordnungsweg legt es an und vergibt die Rolle.
    sess.add(Mitglied(name="M-GAST", vorname="Greta", nachname="Gast",
                      email="gast@example.org", status="Gast", docstatus=0, idx=0))
    sess.commit()

    ergebnis = loese_konto_auf(sess, _konto("gast@example.org"))
    sess.commit()
    assert ergebnis.erlaubt is True
    rollen = {r.role for r in sess.query(HasRole).filter(
        HasRole.parent == ergebnis.user).all()}
    assert "Mitglied" not in rollen
    assert "Gast" not in rollen
    assert rollen == set()  # gar keine Diakronos-Rolle


def test_rn8_mitglied_bleibt_mitglied(patched_db):
    from diakronos_app.anmeldung.zuordnung import loese_konto_auf
    from diakronos_app.models.core import HasRole
    from diakronos_app.models.diakonos import Mitglied

    sess = patched_db()
    sess.add(Mitglied(name="M-VOLL", vorname="Vera", nachname="Voll",
                      email="voll@example.org", status="Mitglied", docstatus=0, idx=0))
    sess.commit()

    ergebnis = loese_konto_auf(sess, _konto("voll@example.org"))
    sess.commit()
    assert ergebnis.erlaubt is True
    rollen = {r.role for r in sess.query(HasRole).filter(
        HasRole.parent == ergebnis.user).all()}
    assert "Mitglied" in rollen


def test_rn8_abgelehnte_zuordnung_wird_vermerkt_und_gezeigt(
    patched_db, admin_client, altbestand_dublette,
):
    """R-N8-2: eine abgelehnte E-Mail-Zuordnung erscheint unter wartende Konten.

    Der Fall „zwei Personen, eine Adresse“ ist seit der Fachentscheidung
    (Manuel 2026-10-19) nur noch als Altbestand denkbar — die Fixture
    `altbestand_dublette` stellt ihn her. Bleibt er im Bestand, muss die
    Zuordnung weiterhin fail closed ablehnen.
    """
    from diakronos_app.anmeldung.zuordnung import (
        loese_konto_auf,
        merke_ablehnung_separat,
    )
    from diakronos_app.models.diakonos import Mitglied

    sess = patched_db()
    # Zwei Personen mit derselben E-Mail -> nicht eindeutig -> Ablehnung.
    sess.add(Mitglied(name="M-A", vorname="A", nachname="Doppel",
                      email="doppelt@example.org", status="Mitglied", docstatus=0, idx=0))
    sess.add(Mitglied(name="M-B", vorname="B", nachname="Doppel",
                      email="doppelt@example.org", status="Mitglied", docstatus=0, idx=0))
    sess.commit()

    konto = _konto("doppelt@example.org")
    ergebnis = loese_konto_auf(sess, konto)
    assert ergebnis.erlaubt is False
    assert ergebnis.grund == "mitglied_zuordnung"
    sess.rollback()
    sess.close()

    merke_ablehnung_separat(konto, ergebnis)

    d = admin_client.post("/api/method/diakronos.diakonos.api.zugang.get_wartende_konten").json()["message"]
    assert d["abgelehnt"], "die abgelehnte Zuordnung muss sichtbar sein"
    eintrag = d["abgelehnt"][0]
    assert eintrag["email"] == "doppelt@example.org"
    assert eintrag["grund"] == "mitglied_zuordnung"
    assert eintrag["versuche"] == 1


def test_rn8_modus_anlegen_nur_system_manager(patched_db, set_user):
    """R-N8-3: „unbekannte Nutzer anlegen“ ist System-Manager-pflichtig."""
    from diakronos_app.anmeldung import einstellungen_api
    from diakronos_app.frappe_compat.exceptions import PermissionError
    from diakronos_app.models.core import HasRole, User

    sess = patched_db()
    sess.add(User(name="ma@example.org", email="ma@example.org",
                  full_name="MA", enabled=True))
    sess.add(HasRole(name="ma-role", parent="ma@example.org", parenttype="User",
                     parentfield="roles", idx=1, role="Mitgliederadministrator"))
    sess.commit()
    sess.close()

    set_user("ma@example.org")
    with pytest.raises(PermissionError):
        einstellungen_api.anmeldung_setze_unbekannte_nutzer("anlegen_mit_rollen")
    # „abweisen“ bleibt erlaubt.
    assert einstellungen_api.anmeldung_setze_unbekannte_nutzer("abweisen")["unbekannte_nutzer"] == "abweisen"
