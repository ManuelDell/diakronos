"""ON-6b — root-Schutz vervollstaendigen (Sicherheits-Review ON-6).

Jeder Test hier ist eine Probe aus dem Sicherheits-Review zu ON-6, die VOR
dieser Karte erfolgreich war. Sie laufen als ECHTE HTTP-Aufrufe durch den
Router der App, damit genau der Weg geprueft ist, den ein Angreifer nimmt.

DIE PROBEN (Kartentext, Punkte 1 und 2)
---------------------------------------
Ein ZWEITER System Manager (``SYSMGR``) — also ein Konto, das die Wachen fuer
„Verwaltungskonto“ passiert — konnte root aussperren:

    PUT    /api/resource/User/<root>                  {"enabled": 0}   -> 200
    DELETE /api/resource/User/<root>                                   -> 200
    DELETE /api/resource/Has Role/<root>-System Manager                -> 202
    austritt.mitglied_austritt(<root-Mitglied>)                        -> enabled=False
    mitglieder.schliesse_mitglied_aus(<root-Mitglied>)                 -> 200

Fuer jeden Fall gilt hier: 403, und DANACH ist root unveraendert — aktiv, mit
Rollen, mit Sitzung. Ein Test, der nur den Statuscode prueft, wuerde eine
halb ausgefuehrte Aenderung nicht bemerken.

Punkt 2: Ein AUSGESCHLOSSENER root bestand weiter jede Pruefung, weil
``has_role``/``is_admin``/``spa.py``/``api/session.py`` ``ist_root`` direkt
riefen. ``get_roles`` liefert fuer Ausgeschlossene ``()`` — daran haengen die
Pruefungen jetzt.

Punkt 3: Migration (deterministische Reihenfolge, Zeile in
``gruppen_root_user``, keine verwaiste Rolle, deaktivierte SM uebersprungen).

Punkt 4: ``root_uebertragen`` in EINER gesperrten Transaktion.

Datenbank: ausschliesslich ``patched_db`` (SQLite) — kein Betrieb, kein Netz.
"""

from __future__ import annotations

import datetime
import re

import pytest

import diakronos_app.api  # noqa: F401 — registriert alle Endpunkte
from diakronos_app.frappe_compat.exceptions import PermissionError as FrappePermissionError
from diakronos_app.frappe_compat.session import set_user

ROOT = "root@gemeinde.example"
SYSMGR = "sysmgr@gemeinde.example"
MITGLIED = "berta@gemeinde.example"
PASSWORT = "EinSicheresPasswort1"

M_ROOT = "M-root"
M_ADMIN = "M-admin"


# ── Hilfsmittel ─────────────────────────────────────────────────────────────


def _nutzer(sess, name: str, rollen: tuple[str, ...] = (), *, enabled: bool = True) -> None:
    from diakronos_app.models.core import HasRole, User

    if sess.get(User, name) is None:
        sess.add(User(name=name, email=name, full_name=name, enabled=enabled))
    for idx, rolle in enumerate(rollen, start=1):
        if not sess.query(HasRole).filter_by(parent=name, role=rolle).first():
            sess.add(HasRole(name=f"{name}-{rolle}", parent=name, parenttype="User",
                             parentfield="roles", idx=idx, role=rolle))


def _grundstand(patched_db) -> None:
    """root + ein ZWEITER System Manager, je mit Mitglied — der Angreifer ist SYSMGR."""
    from diakronos_app import root_benutzer
    from diakronos_app.frappe_compat.passwoerter import neuer_hash
    from diakronos_app.models.core import User
    from diakronos_app.models.diakonos import Mitglied

    sess = patched_db()
    _nutzer(sess, ROOT, ("System Manager", "Mitgliederadministrator"))
    _nutzer(sess, SYSMGR, ("System Manager", "Mitgliederadministrator"))
    _nutzer(sess, MITGLIED)
    sess.commit()
    konto = sess.get(User, ROOT)
    konto.password_hash = neuer_hash(PASSWORT)
    root_benutzer.markiere(sess, ROOT)
    sess.add_all([
        Mitglied(name=M_ROOT, email=ROOT, vorname="Mara", nachname="Erste",
                 user=ROOT, status="Aktiv"),
        Mitglied(name=M_ADMIN, email=SYSMGR, vorname="Sven", nachname="Admin",
                 user=SYSMGR, status="Aktiv"),
    ])
    sess.commit()
    sess.close()


def _post(client, pfad: str, **daten):
    return client.post(f"/api/method/{pfad}", json=daten)


def _root_zustand(patched_db) -> dict:
    """Alles, was nach einem Angriff unveraendert sein MUSS."""
    from diakronos_app import root_benutzer
    from diakronos_app.frappe_compat.permissions import get_roles
    from diakronos_app.models.core import User
    from diakronos_app.models.diakonos import Mitglied
    from diakronos_app.models.root_benutzer import RootUser

    sess = patched_db()
    try:
        konto = sess.get(User, ROOT)
        mitglied = sess.get(Mitglied, M_ROOT)
        marker = {str(k) for (k,) in sess.query(RootUser.konto)}
        return {
            "konto_da": konto is not None,
            "aktiv": bool(konto.enabled) if konto is not None else False,
            "rollen": set(get_roles(ROOT)),
            "root_name": root_benutzer.root_name(),
            "marker": marker,
            "mitglied_ausgeschlossen": bool(mitglied.ausgeschlossen) if mitglied else None,
            "mitglied_status": str(mitglied.status) if mitglied else None,
        }
    finally:
        sess.close()


def _unveraendertes_root(patched_db) -> None:
    """root ist aktiv, traegt seine Rollen, ist eingetragen und nicht gesperrt."""
    z = _root_zustand(patched_db)
    assert z["konto_da"] is True, "root-Konto wurde geloescht"
    assert z["aktiv"] is True, "root-Konto wurde gesperrt"
    assert "System Manager" in z["rollen"], f"root verlor System Manager: {z['rollen']}"
    assert "root" in z["rollen"], f"root verlor die Kennrolle: {z['rollen']}"
    assert z["root_name"] == ROOT, "der root-Eintrag wurde veraendert"
    assert z["marker"] == {ROOT}, f"Marker veraendert: {z['marker']}"
    assert z["mitglied_ausgeschlossen"] in (False, None), "root-Mitglied wurde gesperrt"
    assert z["mitglied_status"] != "Passiver Gast", "root-Mitglied wurde ausgeschlossen"


def _als(user: str):
    """Kontext-Manager: handelt als ``user``, danach zurueck auf Administrator."""
    class _Als:
        def __enter__(self):
            set_user(user)
            return self

        def __exit__(self, *exc):
            set_user("Administrator")
            return False

    return _Als()


# ── Punkt 1: die fuenf Proben aus dem Review ───────────────────────────────


def test_probe_user_sperren_ist_403(client, patched_db, fake_redis) -> None:
    """``PUT /api/resource/User/<root> {"enabled": 0}`` war 200 — jetzt 403."""
    _grundstand(patched_db)

    with _als(SYSMGR):
        antwort = client.put(f"/api/resource/User/{ROOT}", json={"enabled": 0})
    assert antwort.status_code == 403, antwort.text
    assert "geschützt" in antwort.text

    _unveraendertes_root(patched_db)


def test_probe_user_loeschen_ist_403(client, patched_db, fake_redis) -> None:
    """``DELETE /api/resource/User/<root>`` war 200 — jetzt 403."""
    _grundstand(patched_db)

    with _als(SYSMGR):
        antwort = client.delete(f"/api/resource/User/{ROOT}")
    assert antwort.status_code == 403, antwort.text

    _unveraendertes_root(patched_db)


def test_probe_system_manager_rolle_loeschen_ist_403(client, patched_db, fake_redis) -> None:
    """``DELETE /api/resource/Has Role/<root>-System Manager`` war 202 — jetzt 403.

    Der Fall ist besonders: der Zweit-Admin loescht eine FREMDE Rollenzeile
    (``parent`` = root), also nicht sein eigenes Konto — der Aussperrschutz
    fuer den LETZTEN System Manager greift hier gar nicht.
    """
    _grundstand(patched_db)

    with _als(SYSMGR):
        antwort = client.delete(f"/api/resource/Has Role/{ROOT}-System Manager")
    assert antwort.status_code == 403, antwort.text

    _unveraendertes_root(patched_db)


def test_probe_rolle_auf_root_umbiegen_ist_403(client, patched_db, fake_redis) -> None:
    """``PUT /api/resource/Has Role/<fremde Zeile> {"parent": <root>}`` — 403.

    Der Weg in die andere Richtung: eine fremde Rollenzeile wird auf root
    umgehaengt. Das nimmt dem alte Traeger die Rolle und kann root weitere
    Rollen geben — beides ohne Uebertragung.
    """
    from diakronos_app.models.core import HasRole

    _grundstand(patched_db)
    sess = patched_db()
    sess.add(HasRole(name="HR-berta-Mitglied", parent=MITGLIED, parenttype="User",
                     parentfield="roles", idx=1, role="Mitglied"))
    sess.commit()
    sess.close()

    with _als(SYSMGR):
        antwort = client.put("/api/resource/Has Role/HR-berta-Mitglied",
                             json={"parent": ROOT})
    assert antwort.status_code == 403, antwort.text

    sess = patched_db()
    try:
        zeile = sess.get(HasRole, "HR-berta-Mitglied")
        assert zeile is not None and zeile.parent == MITGLIED
    finally:
        sess.close()


def test_probe_rolle_root_vergeben_ist_403(client, patched_db, fake_redis) -> None:
    """Eine ``root``-Rolle fuer ein fremdes Konto geht nur ueber die Uebertragung."""
    _grundstand(patched_db)

    with _als(SYSMGR):
        antwort = client.post("/api/resource/Has Role", json={
            "name": f"{SYSMGR}-root", "parent": SYSMGR, "parenttype": "User",
            "parentfield": "roles", "role": "root", "idx": 9,
        })
    assert antwort.status_code == 403, antwort.text

    from diakronos_app.frappe_compat.permissions import ist_root

    assert ist_root(SYSMGR) is False
    assert ist_root(ROOT) is True


def test_probe_austritt_ist_403(client, patched_db, fake_redis) -> None:
    """``austritt.mitglied_austritt(<root-Mitglied>)`` setzte ``enabled=False``."""
    _grundstand(patched_db)

    with _als(SYSMGR):
        antwort = _post(client, "austritt.mitglied_austritt", mitglied_id=M_ROOT)
    assert antwort.status_code == 403, antwort.text

    _unveraendertes_root(patched_db)


def test_probe_ausschluss_ist_403(client, patched_db, fake_redis) -> None:
    """``mitglieder.schliesse_mitglied_aus(<root-Mitglied>)`` war 200 + Sitzungen weg."""
    _grundstand(patched_db)

    with _als(SYSMGR):
        antwort = _post(client, "mitglieder.schliesse_mitglied_aus",
                        mitglied_id=M_ROOT, begruendung="Probe")
    assert antwort.status_code == 403, antwort.text

    _unveraendertes_root(patched_db)


def test_probe_reaktivierung_und_dsgvo_loeschung_ist_403(
    client, patched_db, fake_redis
) -> None:
    """Die beiden Gegenrichtungen: Reaktivieren und DSGVO-Loeschung von root."""
    from diakronos_app.models.diakonos import Mitglied

    _grundstand(patched_db)
    # Ein FRUEHERER Austritt (Altbestand) — „Reaktivieren“ waere der Weg zurueck
    # in ein aktives root-Konto … und damit eine Rechteaenderung an root.
    sess = patched_db()
    sess.get(Mitglied, M_ROOT).status = "Ausgetreten"
    sess.commit()
    sess.close()

    with _als(SYSMGR):
        zurueck = _post(client, "austritt.mitglied_reaktivieren", mitglied_id=M_ROOT)

    sess = patched_db()
    try:
        assert sess.get(Mitglied, M_ROOT).status == "Ausgetreten"
    finally:
        sess.close()
    assert zurueck.status_code == 403, zurueck.text

    # DSGVO: root laesst sich nicht anonymisieren.
    with _als(SYSMGR):
        from diakronos_app.api.datenschutz import _pruefe_loeschberechtigung

        with pytest.raises(FrappePermissionError):
            _pruefe_loeschberechtigung({ROOT})

    _unveraendertes_root(patched_db)


def test_root_selbst_bleibt_handlungsfaehig(client, patched_db, fake_redis) -> None:
    """Die Sperre gilt nur fuer ANDERE: root darf sein Konto weiter pflegen."""
    _grundstand(patched_db)

    with _als(ROOT):
        antwort = client.put(f"/api/resource/User/{ROOT}",
                             json={"full_name": "Mara Erste (Root)"})
    assert antwort.status_code == 200, antwort.text

    _unveraendertes_root(patched_db)


def test_fremdes_mitglied_ohne_root_wird_weiter_bearbeitet(
    client, patched_db, fake_redis
) -> None:
    """Kein Ueberschutz: ein normales Mitglied sperrt der Admin weiter."""
    _grundstand(patched_db)

    with _als(SYSMGR):
        antwort = client.put(f"/api/resource/User/{MITGLIED}", json={"enabled": 0})
    assert antwort.status_code == 200, antwort.text


# ── Punkt 2: ausgeschlossener root besteht keine Pruefung ──────────────────


def _root_ausschliessen(patched_db) -> None:
    """Markiert das Mitglied von root als ausgeschlossen (Zustand direkt gesetzt).

    Der Weg ueber die Endpunkte ist seit dieser Karte gesperrt; geprueft wird
    hier der ZUSTAND — so, wie ihn ein Altdatensatz oder ein kuenftiger Weg
    herstellen koennte.
    """
    from diakronos_app.frappe_compat.benutzer_status import vergiss
    from diakronos_app.models.diakonos import Mitglied

    sess = patched_db()
    sess.get(Mitglied, M_ROOT).ausgeschlossen = True
    sess.commit()
    sess.close()
    vergiss(ROOT)


def test_ausgeschlossener_root_hat_keine_rollen_und_ist_kein_admin(
    patched_db, fake_redis
) -> None:
    """``is_admin``/``has_role``/``get_roles`` — alle drei ueber ``get_roles``."""
    from diakronos_app.frappe_compat.permissions import get_roles, has_role, is_admin

    _grundstand(patched_db)
    assert is_admin(ROOT) is True

    set_user(ROOT)
    try:
        assert has_role("System Manager") is True
        assert has_role("Eine Rolle, die es nicht gibt") is True
    finally:
        set_user("Administrator")

    _root_ausschliessen(patched_db)

    assert get_roles(ROOT) == (), f"ausgeschlossener root hat Rollen: {get_roles(ROOT)}"
    assert is_admin(ROOT) is False, "ausgeschlossener root gilt weiter als Admin"

    set_user(ROOT)
    try:
        assert has_role("System Manager") is False
        assert has_role("Eine Rolle, die es nicht gibt") is False
    finally:
        set_user("Administrator")


def test_ausgeschlossener_root_meldet_sich_nicht_als_root(client, patched_db, fake_redis) -> None:
    """Boot-Objekt und User-Context: ``is_root``/``is_admin`` kommen aus den Rollen."""
    from diakronos_app.spa import boot_fuer_request

    _grundstand(patched_db)
    _root_ausschliessen(patched_db)

    set_user(ROOT)
    try:
        boot = boot_fuer_request()
        kontext = client.get("/api/method/session.get_current_user_context")
    finally:
        set_user("Administrator")

    assert boot["is_root"] is False
    assert boot["is_admin"] is False
    assert kontext.status_code == 200, kontext.text
    daten = kontext.json()["message"]
    assert daten["is_root"] is False
    assert daten["is_admin"] is False


def test_ausgeschlossener_root_ist_kein_plan_admin(patched_db, fake_redis) -> None:
    """``planrahmen.rechte.Rechte.admin`` fragte ``ist_root`` direkt."""
    from diakronos_app.db import SessionLocal
    from diakronos_app.planrahmen.rechte import Rechte

    _grundstand(patched_db)

    sess = SessionLocal()
    try:
        assert Rechte(sess, ROOT).admin() is True
    finally:
        sess.close()

    _root_ausschliessen(patched_db)

    sess = SessionLocal()
    try:
        with pytest.raises(FrappePermissionError):
            Rechte(sess, ROOT).admin()
    finally:
        sess.close()


# ── Punkt 3: Migration ─────────────────────────────────────────────────────


class _OpMitEngine:
    """Minimaler ``alembic.op``-Ersatz: echte Engine als Bindung."""

    def __init__(self, engine):
        self._engine = engine
        self._verbindung = engine.connect()

    def get_bind(self):
        return self._verbindung

    def add_column(self, *args, **kwargs):
        pass

    def create_table(self, *args, **kwargs):
        pass

    def drop_column(self, *args, **kwargs):
        pass

    def drop_table(self, *args, **kwargs):
        pass

    def commit(self) -> None:
        self._verbindung.commit()

    def _schliessen(self) -> None:
        self._verbindung.close()


def _migration():
    import importlib.util
    from pathlib import Path

    pfad = (Path(__file__).resolve().parents[1] / "alembic" / "versions"
            / "on6_root_benutzer.py")
    spec = importlib.util.spec_from_file_location("on6_root_benutzer", pfad)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _migration_lauf(engine, monkeypatch, mod) -> None:
    betrieb = _OpMitEngine(engine)
    monkeypatch.setattr(mod, "op", betrieb)
    try:
        mod.upgrade()
    finally:
        betrieb.commit()
        betrieb._schliessen()


def _bewerber_stand(engine, *, mit_gemeinde_zeile: bool = True) -> None:
    """Drei SM-Kandidaten: ohne creation, alt+aktiv, alt+DEAKTIVIERT."""
    from sqlalchemy.orm import sessionmaker

    from diakronos_app.models.core import HasRole, User
    from diakronos_app.models.gemeinde import (
        GEMEINDE_EINSTELLUNGEN_NAME,
        GemeindeEinstellungen,
    )

    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    sess = factory()
    sess.add_all([
        User(name="a-alt@x.org", email="a-alt@x.org", full_name="Alt", enabled=True),
        User(name="b-gesperrt@x.org", email="b-gesperrt@x.org",
             full_name="Gesperrt", enabled=False),
        User(name="c-ohne-creation@x.org", email="c-ohne-creation@x.org",
             full_name="Ohne", enabled=True),
        # ZUERST zum System Manager gemacht, aber deaktiviert -> ueberspringen.
        HasRole(name="b1", parent="b-gesperrt@x.org", parenttype="User",
                role="System Manager", idx=0,
                creation=datetime.datetime(2025, 6, 1, 8, 0)),
        HasRole(name="a1", parent="a-alt@x.org", parenttype="User",
                role="System Manager", idx=0,
                creation=datetime.datetime(2026, 1, 2, 9, 0)),
        # Ohne creation: PostgreSQL sortiert NULL zuletzt, SQLite zuerst —
        # deshalb muss die Reihenfolge explizit sein.
        HasRole(name="c1", parent="c-ohne-creation@x.org", parenttype="User",
                role="System Manager", idx=0, creation=None),
        HasRole(name="a2", parent="a-alt@x.org", parenttype="User",
                role="Mitgliederadministrator", idx=1,
                creation=datetime.datetime(2026, 1, 2, 9, 0)),
    ])
    if mit_gemeinde_zeile:
        sess.add(GemeindeEinstellungen(name=GEMEINDE_EINSTELLUNGEN_NAME))
    sess.commit()
    sess.close()


def test_migration_nimmt_aktiven_sm_und_schreibt_kennrolle(engine, monkeypatch) -> None:
    """Deaktivierte SM ueberspringen, deterministisch sortieren, Marker schreiben."""
    from sqlalchemy.orm import sessionmaker

    from diakronos_app.models.gemeinde import (
        GEMEINDE_EINSTELLUNGEN_NAME,
        GemeindeEinstellungen,
    )
    from diakronos_app.models.root_benutzer import RootUser

    _bewerber_stand(engine)
    mod = _migration()
    _migration_lauf(engine, monkeypatch, mod)

    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    sess = factory()
    try:
        zeile = sess.get(GemeindeEinstellungen, GEMEINDE_EINSTELLUNGEN_NAME)
        # a-alt ist der aelteste AKTIVE; der gesperrte b-gesperrt wird
        # uebersprungen, obwohl er die aelteste Zeile hat. c-ohne-creation
        # (NULL) kommt in beiden Dialekten ZULETZT.
        assert zeile.root_benutzer == "a-alt@x.org", zeile.root_benutzer
        assert [str(k) for (k,) in sess.query(RootUser.konto)] == ["a-alt@x.org"]
    finally:
        sess.close()

    # Idempotent: ein zweiter Lauf aendert nichts.
    _migration_lauf(engine, monkeypatch, mod)
    sess = factory()
    try:
        assert sess.get(GemeindeEinstellungen,
                        GEMEINDE_EINSTELLUNGEN_NAME).root_benutzer == "a-alt@x.org"
        assert sess.query(RootUser).count() == 1
    finally:
        sess.close()


def test_migration_legt_fehlende_gemeinde_zeile_an(engine, monkeypatch) -> None:
    """Fehlt die Single-Zeile, entsteht KEINE verwaiste Has-Role-``root``-Zeile."""
    from sqlalchemy import text
    from sqlalchemy.orm import sessionmaker

    from diakronos_app.models.gemeinde import (
        GEMEINDE_EINSTELLUNGEN_NAME,
        GemeindeEinstellungen,
    )

    _bewerber_stand(engine, mit_gemeinde_zeile=False)
    mod = _migration()
    _migration_lauf(engine, monkeypatch, mod)

    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    sess = factory()
    try:
        zeile = sess.get(GemeindeEinstellungen, GEMEINDE_EINSTELLUNGEN_NAME)
        assert zeile is not None, "die Single-Zeile wurde nicht angelegt"
        assert zeile.root_benutzer == "a-alt@x.org"
        rollen = {r for (r,) in sess.execute(text(
            "SELECT parent FROM has_role WHERE role = 'root'"))}
        # Entweder BEIDES (Eintrag + Kennrolle) oder NICHTS — nie eine Rolle
        # ohne Eintrag.
        assert rollen == {"a-alt@x.org"}, rollen
    finally:
        sess.close()


def test_migration_erfindet_keinen_root_ohne_aktiven_system_manager(
    engine, monkeypatch
) -> None:
    """Nur ein DEAKTIVIERTER SM -> kein root (und keine Kennrolle)."""
    from sqlalchemy import text
    from sqlalchemy.orm import sessionmaker

    from diakronos_app.models.core import HasRole, User
    from diakronos_app.models.gemeinde import (
        GEMEINDE_EINSTELLUNGEN_NAME,
        GemeindeEinstellungen,
    )

    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    sess = factory()
    sess.add_all([
        User(name="aus@x.org", email="aus@x.org", full_name="Aus", enabled=False),
        HasRole(name="x1", parent="aus@x.org", parenttype="User",
                role="System Manager", idx=0,
                creation=datetime.datetime(2025, 1, 1, 8, 0)),
        GemeindeEinstellungen(name=GEMEINDE_EINSTELLUNGEN_NAME),
    ])
    sess.commit()
    sess.close()

    mod = _migration()
    _migration_lauf(engine, monkeypatch, mod)

    sess = factory()
    try:
        assert sess.get(GemeindeEinstellungen,
                        GEMEINDE_EINSTELLUNGEN_NAME).root_benutzer is None
        assert sess.execute(text(
            "SELECT COUNT(*) FROM has_role WHERE role = 'root'")).scalar() == 0
    finally:
        sess.close()


# ── Punkt 4: root_uebertragen in EINER gesperrten Transaktion ──────────────


def test_uebertragung_sperrt_die_gemeinde_zeile(client, patched_db, fake_redis) -> None:
    """``with_for_update`` auf ``gemeinde_einstellungen`` — der Doppelmarker faellt weg.

    Geprueft wird die ANWEISUNG, nicht das Timing: die Sperre muss auf der
    Zeile liegen, die die Wahrheit traegt. Ein Nebenlaeufigkeitstest waere auf
    der SQLite-Test-DB nicht aussagekraeftig (kein ``FOR UPDATE``).
    """
    gesehen: list[str] = []

    from diakronos_app.db import SessionLocal as _SessionLocal

    class _SitzungMitMitschrift:
        """SessionLocal-Ersatz: reicht die Sitzung durch und schreibt mit.

        ``SessionLocal()`` liefert in dieser App eine SQLAlchemy-Session, die
        als Kontext-Manager benutzt wird (``with SessionLocal() as sess``).
        Der Ersatz bleibt deshalb eine SESSION und haengt sich nur an
        ``execute`` — kein zweiter Kontext-Manager.
        """

        def __init__(self):
            self._sess = _SessionLocal()
            echte_execute = self._sess.execute

            def execute(anweisung, *a, **kw):
                gesehen.append(str(anweisung))
                return echte_execute(anweisung, *a, **kw)

            self._sess.execute = execute

        def __enter__(self):
            self._sess.__enter__()
            return self._sess

        def __exit__(self, *exc):
            return self._sess.__exit__(*exc)

        def __getattr__(self, name):
            # `SessionLocal()` wird an mehreren Stellen auch OHNE `with`
            # benutzt (`sess = SessionLocal(); … sess.close()`); alles ausser
            # `execute` reicht der Ersatz unveraendert an die echte Sitzung.
            return getattr(self._sess, name)

    _grundstand(patched_db)

    # `SessionLocal` wird IN der Funktion importiert (nicht auf Modulebene) —
    # gepatcht wird deshalb die quelle, gegen die sie importiert: `db`.
    import diakronos_app.db as _db

    with _als(ROOT):
        import unittest.mock as _mock

        with _mock.patch.object(_db, "SessionLocal", _SitzungMitMitschrift):
            antwort = _post(client, "root.root_uebertragen", konto=SYSMGR,
                            passwort=PASSWORT, bestaetigt=True)
    assert antwort.status_code == 200, antwort.text

    gesperrt = [s for s in gesehen if "FOR UPDATE" in s.upper()]
    assert gesperrt, "keine Zeilensperre in der Uebertragungs-Transaktion"
    assert any("gemeinde_einstellungen" in s for s in gesperrt), gesperrt

    # Genau EIN Marker — kein doppelter.
    from diakronos_app.models.root_benutzer import RootUser

    sess = patched_db()
    try:
        marker = sorted(str(k) for (k,) in sess.query(RootUser.konto))
    finally:
        sess.close()
    assert marker == [SYSMGR], marker


def test_uebertragung_holt_die_pruefung_in_die_transaktion(client, patched_db, fake_redis) -> None:
    """Ein Nicht-root wird IN der gesperrten Transaktion verweigert (403, kein Schreibvorgang)."""
    _grundstand(patched_db)

    with _als(SYSMGR):
        antwort = _post(client, "root.root_uebertragen", konto=SYSMGR,
                        passwort=PASSWORT, bestaetigt=True)
    assert antwort.status_code == 403, antwort.text

    _unveraendertes_root(patched_db)
