"""ON-6 — der erste Administrator ist ``root``: alle Rechte, geschuetzt.

Jeder Test hier ist eine Zusage der Karte („ON-6“, Punkte 1–4) und laeuft als
ECHTER HTTP-Aufruf ueber den Router der App — nicht ueber die Funktionen
direkt. Damit ist geprueft, was die Oberflaeche auch tut.

* **Punkt 1** — der beim Ersteinrichtungs-Link angelegte Benutzer ist root
  (Feld an der Single-Zeile + Kennrolle); Migration auf Bestandsdaten.
* **Punkt 2** — root besteht jede Rollenpruefung: ohne
  ``Kalenderadministrator`` legt er im Onboarding Kalender an (Schritt 5) und
  darf Moderation/Website/Mitglieder. Ein anderer ``System Manager`` ist NICHT
  root und behaelt seine Grenzen.
* **Punkt 3** — Herabstufen/Sperren/Passwort/Loeschung von root durch andere
  ist 403; Uebertragung nur durch root selbst.

Datenbank: ausschliesslich ``patched_db`` (SQLite) — kein Betrieb, kein Netz.
"""

from __future__ import annotations

import pytest

import diakronos_app.api  # noqa: F401 — registriert alle Endpunkte
import diakronos_app.einrichtung as einrichtung
from diakronos_app.frappe_compat.session import set_user

ROOT = "root@gemeinde.example"
SYSMGR = "sysmgr@gemeinde.example"
MITGLIED = "berta@gemeinde.example"
PASSWORT = "EinSicheresPasswort1"


# ── Hilfsmittel ─────────────────────────────────────────────────────────────


def _nutzer(sess, name: str, rollen: tuple[str, ...] = (), *,
            enabled: bool = True) -> None:
    from diakronos_app.models.core import HasRole, User

    if sess.get(User, name) is None:
        sess.add(User(name=name, email=name, full_name=name, enabled=enabled))
    for idx, rolle in enumerate(rollen, start=1):
        if not sess.query(HasRole).filter_by(parent=name, role=rolle).first():
            sess.add(HasRole(name=f"{name}-{rolle}", parent=name, parenttype="User",
                             parentfield="roles", idx=idx, role=rolle))


def _als_root(sess) -> None:
    """Legt ROOT als ersten Administrator an — genau wie die Ersteinrichtung."""
    from diakronos_app import root_benutzer
    from diakronos_app.frappe_compat.passwoerter import neuer_hash

    _nutzer(sess, ROOT, ("System Manager", "Mitgliederadministrator"))
    from diakronos_app.models.core import User

    konto = sess.query(User).filter_by(name=ROOT).one()
    konto.password_hash = neuer_hash(PASSWORT)
    root_benutzer.markiere(sess, ROOT)
    sess.commit()


def _post(client, pfad: str, **daten):
    return client.post(f"/api/method/{pfad}", json=daten)


def _einrichtung_token() -> str:
    """Erzeugt einen Einrichtungs-Link wie beim Start (Einrichtungs-Token).

    Muss NACH der ``client``-Fixture laufen: nur dann zeigt ``SessionLocal``
    auf die Test-Datenbank (``patched_db``). ``erzeuge_token`` schreibt in
    einer eigenen Sitzung.
    """
    token, _bis = einrichtung.erzeuge_token()
    return token


def _formular(**abweichungen) -> dict:
    werte = {
        "vorname": "Mara",
        "nachname": "Erste",
        "email": ROOT,
        "passwort": PASSWORT,
        "wiederholung": PASSWORT,
    }
    werte.update(abweichungen)
    return werte


# ── Punkt 1: Ersteinrichtung macht den ersten Admin zum root ───────────────


def test_ersteinrichtungslink_macht_den_ersten_admin_zum_root(
    patched_db, fake_redis
) -> None:
    """Der ueber den Einrichtungs-Link angelegte Benutzer ist root."""
    from diakronos_app.models.gemeinde import (
        GEMEINDE_EINSTELLUNGEN_NAME,
        GemeindeEinstellungen,
    )

    token = _einrichtung_token()
    # EIGENER Client: die `client`-Fixture legt das Konto `Administrator` an,
    # und `einrichtung` verweigert dann mit „bereits eingerichtet“ (die
    # Ersteinrichtung ist der Fall „noch kein Benutzer“).
    from fastapi.testclient import TestClient

    from diakronos_app.main import app

    client = TestClient(app)
    # Die Seite ist mit einem Einmal-Token ausgestattet (SEC-1): der
    # Formular-POST braucht ihn — der GET liefert ihn im HTML.
    seite = client.get(f"/einrichtung/{token}")
    assert seite.status_code == 200, seite.text
    import re as _re

    csrf = _re.search(r'name="_csrf" value="([^"]*)"', seite.text)
    assert csrf is not None, seite.text
    antwort = client.post(f"/einrichtung/{token}",
                          data={**_formular(), "_csrf": csrf.group(1)},
                          follow_redirects=False)
    assert antwort.status_code == 303, antwort.text

    sess = patched_db()
    try:
        zeile = sess.get(GemeindeEinstellungen, GEMEINDE_EINSTELLUNGEN_NAME)
        assert zeile is not None and zeile.root_benutzer == ROOT
    finally:
        sess.close()

    # Und die Rechtepruefung sieht es genauso (EINE Wahrheit).
    from diakronos_app.frappe_compat.permissions import get_roles, has_role, ist_root

    assert ist_root(ROOT) is True
    assert "Kalenderadministrator" in get_roles(ROOT)
    from diakronos_app.frappe_compat.session import set_user

    set_user(ROOT)
    try:
        assert has_role("Eine Rolle, die es noch nicht gibt") is True
    finally:
        set_user("Administrator")


# ── Punkt 2: root besteht jede Rechtepruefung ──────────────────────────────


def test_root_ohne_kalenderrolle_legt_kalender_im_onboarding_an(client, patched_db, fake_redis) -> None:
    """DER Anlass der Karte: Onboarding-Schritt 5 ist fuer root gruen.

    root traegt hier ausdruecklich NUR ``System Manager`` — nicht
    ``Kalenderadministrator``. Vor ON-6 scheiterte der Vorschlag an
    ``create_kalender`` mit „Nur Kalenderadministratoren duerfen Kalender
    verwalten.“
    """
    from diakronos_app.models.kronos import Kalender

    sess = patched_db()
    _nutzer(sess, ROOT, ("System Manager",))
    from diakronos_app import root_benutzer

    root_benutzer.markiere(sess, ROOT)
    sess.commit()
    sess.close()

    set_user(ROOT)
    try:
        r = _post(client, "einrichtung.kalender_vorschlag_anlegen",
                  namen=["Gottesdienste", "Gemeindekalender"])
    finally:
        set_user("Administrator")
    assert r.status_code == 200, r.text
    assert sorted(r.json()["message"]["angelegt"]) == ["Gemeindekalender", "Gottesdienste"]

    sess = patched_db()
    try:
        namen = {n for (n,) in sess.query(Kalender.name)}
    finally:
        sess.close()
    assert {"Gottesdienste", "Gemeindekalender"} <= namen


def test_root_darf_moderation_website_und_mitglieder(client, patched_db, fake_redis) -> None:
    """root besteht die Pruefungen der anderen Bereiche ohne deren Rollen."""
    from diakronos_app.frappe_compat.permissions import get_roles

    sess = patched_db()
    _nutzer(sess, ROOT, ("System Manager",))
    _nutzer(sess, MITGLIED)
    from diakronos_app import root_benutzer

    root_benutzer.markiere(sess, ROOT)
    sess.commit()
    sess.close()

    rollen = set(get_roles(ROOT))
    for rolle in ("Kalenderadministrator", "Ressourcenmoderator",
                  "Website-Moderator", "Mitgliederadministrator", "Mitglied"):
        assert rolle in rollen, rolle

    set_user(ROOT)
    try:
        # Mitgliederliste (Mitgliederverwaltung) und Moderations-Uebersicht.
        assert _post(client, "mitglieder.get_mitglieder_liste").status_code == 200
        assert _post(client, "einrichtung.status").status_code == 200
        # Die Rollenuebersicht ist dem System Manager vorbehalten — root ohnehin.
        assert _post(client, "zugang.get_rollen_uebersicht").status_code == 200
    finally:
        set_user("Administrator")


def test_anderer_system_manager_ist_nicht_root_und_behaelt_grenzen(
    client, patched_db, fake_redis
) -> None:
    """Ein zweiter System Manager wird von ON-6 NICHT aufgewertet."""
    from diakronos_app.frappe_compat.permissions import get_roles, ist_root

    sess = patched_db()
    _al_root = _nutzer
    _al_root(sess, ROOT, ("System Manager", "Mitgliederadministrator"))
    _al_root(sess, SYSMGR, ("System Manager",))
    from diakronos_app import root_benutzer

    root_benutzer.markiere(sess, ROOT)
    sess.commit()
    sess.close()

    assert ist_root(ROOT) is True
    assert ist_root(SYSMGR) is False
    assert "Kalenderadministrator" not in get_roles(SYSMGR)

    set_user(SYSMGR)
    try:
        r = _post(client, "einrichtung.kalender_vorschlag_anlegen", namen=["NurSo"])
    finally:
        set_user("Administrator")
    # Genau die Grenze von vorher: ohne Kalenderrolle verweigert.
    assert r.status_code == 403, r.text


# ── Punkt 3: Schutz ────────────────────────────────────────────────────────


def _root_und_admin(patched_db, fake_redis) -> None:
    """Test-Konten aus einer EIGENEN Sitzung — danach Existenz frisch lesen.

    ``patched_db`` gibt je Aufruf eine NEUE Sitzung; deren Identity-Map kennt
    die Zeilen einer anderen Sitzung nicht. Ohne ``populate_existing`` (bzw.
    eine frische Abfrage) liefert ``sess.get`` hier ``None``.
    """
    sess = patched_db()
    _nutzer(sess, ROOT, ("System Manager", "Mitgliederadministrator"))
    _nutzer(sess, SYSMGR, ("System Manager", "Mitgliederadministrator"))
    from diakronos_app import root_benutzer
    from diakronos_app.frappe_compat.passwoerter import neuer_hash
    from diakronos_app.models.core import User
    from diakronos_app.models.diakonos import Mitglied

    from sqlalchemy import select

    sess.commit()
    konto = sess.execute(
        select(User).where(User.name == ROOT).execution_options(populate_existing=True)
    ).scalar_one()
    konto.password_hash = neuer_hash(PASSWORT)
    root_benutzer.markiere(sess, ROOT)
    sess.add(Mitglied(name="M-root", email=ROOT, vorname="Mara", nachname="Erste",
                      user=ROOT, status="Aktiv"))
    sess.add(Mitglied(name="M-admin", email=SYSMGR, vorname="Sven", nachname="Admin",
                      user=SYSMGR, status="Aktiv"))
    sess.commit()
    sess.close()


def test_herabstufen_von_root_durch_anderen_admin_ist_403(client, patched_db, fake_redis) -> None:
    """Kein anderer Administrator nimmt dem root die Verwaltungsrolle."""
    _root_und_admin(patched_db, fake_redis)

    set_user(SYSMGR)
    try:
        r = _post(client, "zugang.setze_rollen", mitglied_id="M-root",
                  rollen=["Mitglied"])
    finally:
        set_user("Administrator")
    assert r.status_code == 403, r.text
    assert "geschützt" in r.text

    from diakronos_app.frappe_compat.permissions import ist_root

    assert ist_root(ROOT) is True


def test_root_kann_nicht_gesperrt_werden(client, patched_db, fake_redis) -> None:
    _root_und_admin(patched_db, fake_redis)

    set_user(SYSMGR)
    try:
        r = _post(client, "zugang.konto_sperren", mitglied_id="M-root", gesperrt=True)
    finally:
        set_user("Administrator")
    assert r.status_code == 403, r.text

    from diakronos_app.models.core import User

    sess = patched_db()
    try:
        assert sess.get(User, ROOT).enabled is True
    finally:
        sess.close()


def test_root_kann_keinen_loeschantrag_stellen(client, patched_db, fake_redis) -> None:
    """DSGVO-Loeschung des root-Kontos: klare Meldung statt Anonymisierung."""
    _root_und_admin(patched_db, fake_redis)

    set_user(ROOT)
    try:
        r = _post(client, "datenschutz.loeschung_beantragen", bestaetigt=True)
    finally:
        set_user("Administrator")
    assert r.status_code in (417, 400), r.text
    # ON-6f: Wortwahl wie in ON-6d — „Konto der Hauptverwaltung (root)“ statt
    # „Root-Benutzer“ (Du-Form).
    assert "Hauptverwaltung (root)" in r.text, r.text
    assert "geschützt" in r.text, r.text
    assert "Root-Benutzer" not in r.text, r.text

    from diakronos_app.models.datenschutz import Loeschantrag

    sess = patched_db()
    try:
        assert sess.get(Loeschantrag, "M-root") is None
    finally:
        sess.close()


def test_uebertragung_nur_durch_root_selbst(client, patched_db, fake_redis) -> None:
    """Ein System Manager kann root NICHT an sich ziehen (403)."""
    _root_und_admin(patched_db, fake_redis)

    set_user(SYSMGR)
    try:
        r = _post(client, "root.root_uebertragen", konto=SYSMGR,
                  passwort=PASSWORT, bestaetigt=True)
    finally:
        set_user("Administrator")
    assert r.status_code == 403, r.text

    from diakronos_app.frappe_compat.permissions import ist_root

    assert ist_root(ROOT) is True
    assert ist_root(SYSMGR) is False


def test_root_uebertraegt_an_aktiven_system_manager(client, patched_db, fake_redis) -> None:
    """Der eigene Endpunkt: root gibt die Rechte — mit Passwort + Bestaetigung."""
    _root_und_admin(patched_db, fake_redis)

    # ohne Bestaetigung: abgelehnt
    set_user(ROOT)
    try:
        ohne = _post(client, "root.root_uebertragen", konto=SYSMGR, passwort=PASSWORT)
        falsch = _post(client, "root.root_uebertragen", konto=SYSMGR,
                       passwort="FalschFalsch1", bestaetigt=True)
        ok = _post(client, "root.root_uebertragen", konto=SYSMGR,
                   passwort=PASSWORT, bestaetigt=True)
    finally:
        set_user("Administrator")
    assert ohne.status_code in (417, 400), ohne.text
    assert falsch.status_code == 403, falsch.text
    assert ok.status_code == 200, ok.text
    assert ok.json()["message"]["root"] == SYSMGR

    from diakronos_app.frappe_compat.permissions import get_roles, ist_root

    assert ist_root(SYSMGR) is True
    assert ist_root(ROOT) is False
    # Der alte root ist wieder ein gewoehnlicher System Manager — ohne
    # Kalenderadministrator.
    assert "Kalenderadministrator" not in get_roles(ROOT)


def test_root_status_verraet_den_namen_nur_administration(client, patched_db, fake_redis) -> None:
    """Der Name des root ist Verwaltungswissen."""
    _root_und_admin(patched_db, fake_redis)
    sess = patched_db()
    _nutzer(sess, MITGLIED)
    sess.commit()
    sess.close()

    set_user(MITGLIED)
    try:
        fremd = _post(client, "root.status")
    finally:
        set_user(ROOT)
    try:
        eigen = _post(client, "root.status")
    finally:
        set_user("Administrator")

    assert fremd.status_code == 200, fremd.text
    assert fremd.json()["message"] == {"root": None, "ist_root": False}
    assert eigen.json()["message"] == {"root": ROOT, "ist_root": True}


def test_boot_liefert_is_root(client, patched_db, fake_redis) -> None:
    """Die Oberflaeche erfaehrt von root (Boot-Objekt + User-Context)."""
    _root_und_admin(patched_db, fake_redis)

    set_user(ROOT)
    try:
        kontext = client.get("/api/method/session.get_current_user_context")
    finally:
        set_user("Administrator")
    assert kontext.status_code == 200, kontext.text
    daten = kontext.json()["message"]
    assert daten["is_root"] is True
    assert daten["is_admin"] is True
    assert "Kalenderadministrator" in daten["roles"]

    from diakronos_app.spa import boot_fuer_request
    from diakronos_app.frappe_compat.session import set_user as _set

    _set(ROOT)
    try:
        boot = boot_fuer_request()
    finally:
        _set("Administrator")
    assert boot["is_root"] is True


# ── Punkt 1 (Bestand): Migration ───────────────────────────────────────────


class _OpMitEngine:
    """Minimaler ``alembic.op``-Ersatz: echte Engine als Bindung.

    Beide Zugriffe der Migration muessen funktionieren:
      * ``op.get_bind().execute(...)`` (Bestandsdaten) -> Connection,
      * ``sa.inspect(op.get_bind())``                    -> Engine/Connection.
    Eine Connection, die die Test-Engine offen haelt, erfuellt beides.
    Nach dem Lauf wird sie geschlossen (``_schliessen``).
    """

    def __init__(self, engine):
        self._engine = engine
        self._verbindung = engine.connect()

    def get_bind(self):
        return self._verbindung

    def add_column(self, *args, **kwargs):  # Spalten existieren (Modelle)
        pass

    def create_table(self, *args, **kwargs):
        pass

    def commit(self) -> None:
        """Wie Alembic: die Migration laeuft in EINER Transaktion, die am Ende
        committet wird. Ohne commit sieht eine zweite Sitzung nichts."""
        self._verbindung.commit()

    def _schliessen(self) -> None:
        self._verbindung.close()


def _migration():
    import importlib.util
    from pathlib import Path

    pfad = Path(__file__).resolve().parents[1] / "alembic" / "versions" / \
        "on6_root_benutzer.py"
    spec = importlib.util.spec_from_file_location("on6_root_benutzer", pfad)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_migration_setzt_root_auf_ersten_system_manager(engine, monkeypatch) -> None:
    """Bestandsdaten: der ZUERST zum System Manager gemachte Benutzer wird root."""
    import datetime

    from sqlalchemy import text

    from diakronos_app.models.core import HasRole, User
    from diakronos_app.models.gemeinde import (
        GEMEINDE_EINSTELLUNGEN_NAME,
        GemeindeEinstellungen,
    )
    from sqlalchemy.orm import sessionmaker

    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    sess = factory()
    sess.add_all([
        User(name="spaeter@x.org", email="spaeter@x.org", full_name="Spät", enabled=True),
        User(name="frueh@x.org", email="frueh@x.org", full_name="Früh", enabled=True),
        User(name="admin@x.org", email="admin@x.org", full_name="Adm", enabled=True),
        HasRole(name="a1", parent="spaeter@x.org", parenttype="User",
                role="System Manager", idx=1,
                creation=datetime.datetime(2026, 3, 1, 10, 0)),
        HasRole(name="a2", parent="frueh@x.org", parenttype="User",
                role="System Manager", idx=0,
                creation=datetime.datetime(2026, 1, 2, 9, 0)),
        # Der Administrator-Platzhalter ist KEIN Kandidat (kein System Manager).
        HasRole(name="a3", parent="admin@x.org", parenttype="User",
                role="Mitgliederadministrator", idx=0,
                creation=datetime.datetime(2025, 1, 1, 8, 0)),
        GemeindeEinstellungen(name=GEMEINDE_EINSTELLUNGEN_NAME),
    ])
    sess.commit()
    sess.close()

    # Die Migration laeuft ohne Alembic-Kontext: `op` gegen die Test-Engine.
    # Die Migration laeuft wie bei Alembic in EINER Transaktion, die am Ende
    # committet wird (sonst sieht eine zweite Sitzung nichts).
    betrieb = _OpMitEngine(engine)
    mod = _migration()
    monkeypatch.setattr(mod, "op", betrieb)
    try:
        mod.upgrade()
    finally:
        betrieb.commit()
        betrieb._schliessen()

    sess = factory()
    try:
        zeile = sess.get(GemeindeEinstellungen, GEMEINDE_EINSTELLUNGEN_NAME)
        assert zeile.root_benutzer == "frueh@x.org"
        rollen = {r for (r,) in sess.execute(text(
            "SELECT role FROM has_role WHERE parent = 'frueh@x.org'"))}
        assert "root" in rollen
    finally:
        sess.close()

    # Idempotent: ein zweiter Lauf aendert nichts (frische Verbindung).
    betrieb = _OpMitEngine(engine)
    monkeypatch.setattr(mod, "op", betrieb)
    try:
        mod.upgrade()
    finally:
        betrieb._schliessen()
    sess = factory()
    try:
        assert sess.get(GemeindeEinstellungen,
                        GEMEINDE_EINSTELLUNGEN_NAME).root_benutzer == "frueh@x.org"
    finally:
        sess.close()


def test_migration_erfindet_keinen_root_ohne_system_manager(engine, monkeypatch) -> None:
    from sqlalchemy.orm import sessionmaker

    from diakronos_app.models.core import User
    from diakronos_app.models.gemeinde import (
        GEMEINDE_EINSTELLUNGEN_NAME,
        GemeindeEinstellungen,
    )

    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    sess = factory()
    sess.add_all([
        User(name="nur@x.org", email="nur@x.org", full_name="Nur", enabled=True),
        GemeindeEinstellungen(name=GEMEINDE_EINSTELLUNGEN_NAME),
    ])
    sess.commit()
    sess.close()

    mod = _migration()

    betrieb = _OpMitEngine(engine)
    monkeypatch.setattr(mod, "op", betrieb)
    try:
        mod.upgrade()
    finally:
        betrieb.commit()
        betrieb._schliessen()

    sess = factory()
    try:
        assert sess.get(GemeindeEinstellungen,
                        GEMEINDE_EINSTELLUNGEN_NAME).root_benutzer is None
    finally:
        sess.close()
