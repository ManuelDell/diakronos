"""ON-6c — root-Schutz: die Luecken ueber die GENERISCHEN Wege (Befund-Triage).

Die Vorlage ist die Probe-Sammlung des Sicherheits-Reviews
(``on6-root-probes.py``, 36 Angriffe eines zweiten System Managers gegen
root). Sie war ein WEGWERF-Export: sie druckte nur und assertete nicht. Hier
ist jeder Angriff ein Test mit den drei Zusagen der Karte:

  1. Die Antwort ist 403/abgelehnt (kein 200, kein 202).
  2. Danach ist root unveraendert — aktiv, mit ALLEN Rollen, mit Kennrolle,
     mit Konto-Verknuepfung, nicht ausgeschlossen, nicht ausgetreten.
  3. Die Meldung nennt den Grund („geschützt“), nicht die Mechanik.

Ein Test, der nur den Statuscode prueft, wuerde eine halb ausgefuehrte
Aenderung nicht bemerken — deshalb der Zustandsvergleich gegen den Stand VOR
dem Angriff.

WAS DIESE KARTE SCHLIESST (Befunde 1, 2, 4, 5 der Triage)
--------------------------------------------------------
1. HOCH  ``PUT /api/resource/Mitglied/M-root {"ausgeschlossen": 1}`` -> 200
         (root verlor danach alle Rollen), ``DELETE Mitglied/M-root`` -> 202,
         ``{"user": ""}`` -> 200 (Entkopplung: danach ueber die E-Mail
         aussperrbar), ``update_mitglied`` mit ``status``/``email`` -> 200.
2. HOCH  ``PUT /api/resource/User/<root> {"email": "evil@…"}`` -> 200 — die
         OIDC-Erstanmeldung ordnet ueber die verifizierte E-Mail zu, das war
         eine Uebernahme von root. ``user_type`` ebenfalls schreibbar.
4. NIEDRIG ``DELETE /api/resource/Has Role/<root>-root`` -> 202 nahm root die
         Kennrolle.
5. NIEDRIG ``POST /api/resource/Has Role {"parent": <root>}`` ohne ``name``
         -> 200 haengte root eine Rolle an.

Datenbank: ausschliesslich ``patched_db`` (SQLite), kein Betrieb, kein Netz.
"""

from __future__ import annotations

import pytest

import diakronos_app.api  # noqa: F401 — registriert alle Endpunkte
from diakronos_app.frappe_compat.session import set_user

ROOT = "root@gemeinde.example"
SYSMGR = "sysmgr@gemeinde.example"
MITGLIED = "berta@gemeinde.example"
PASSWORT = "EinSicheresPasswort1"

M_ROOT = "M-root"
M_ADMIN = "M-admin"


# ── Hilfsmittel (dieselben wie in test_on6b_root_schutz.py) ────────────────


def _nutzer(sess, name: str, rollen: tuple[str, ...] = (), *, enabled: bool = True) -> None:
    from diakronos_app.models.core import HasRole, User

    if sess.get(User, name) is None:
        sess.add(User(name=name, email=name, full_name=name, enabled=enabled))
    for idx, rolle in enumerate(rollen, start=1):
        if not sess.query(HasRole).filter_by(parent=name, role=rolle).first():
            sess.add(HasRole(name=f"{name}-{rolle}", parent=name, parenttype="User",
                             parentfield="roles", idx=idx, role=rolle))


def _grundstand(patched_db) -> None:
    """root + ein ZWEITER System Manager, je mit Mitglied — der Angreifer ist SYSMGR.

    Idempotent: ein zweiter Aufruf legt nichts doppelt an (der partielle
    Unique-Index ``uq_mitglied_email_normalisiert`` laesst dasselbe Mitglied
    kein zweites Mal zu).
    """
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
    if sess.get(Mitglied, M_ROOT) is None:
        sess.add(Mitglied(name=M_ROOT, email=ROOT, vorname="Mara", nachname="Erste",
                          user=ROOT, status="Aktiv"))
    if sess.get(Mitglied, M_ADMIN) is None:
        sess.add(Mitglied(name=M_ADMIN, email=SYSMGR, vorname="Sven", nachname="Admin",
                          user=SYSMGR, status="Aktiv"))
    sess.commit()
    sess.close()


def _post(client, pfad: str, **daten):
    return client.post(f"/api/method/{pfad}", json=daten)


def _root_zustand(patched_db) -> dict:
    """ALLES, was nach einem Angriff unveraendert sein MUSS."""
    from diakronos_app import root_benutzer
    from diakronos_app.frappe_compat.permissions import get_roles
    from diakronos_app.models.core import HasRole, User
    from diakronos_app.models.diakonos import Mitglied
    from diakronos_app.models.root_benutzer import RootUser

    sess = patched_db()
    try:
        konto = sess.get(User, ROOT)
        mitglied = sess.get(Mitglied, M_ROOT)
        return {
            "konto_da": konto is not None,
            "aktiv": bool(konto.enabled) if konto is not None else False,
            "email": str(konto.email) if konto is not None else None,
            "user_type": str(konto.user_type) if konto is not None else None,
            "passwort": str(konto.password_hash or "")[:20] if konto is not None else None,
            "rollen": set(get_roles(ROOT)),
            "hasrole_zeilen": sorted(r.role for r in sess.query(HasRole).filter_by(parent=ROOT)),
            "root_name": root_benutzer.root_name(),
            "marker": {str(k) for (k,) in sess.query(RootUser.konto)},
            "mitglied_da": mitglied is not None,
            "mitglied_user": str(mitglied.user or "") if mitglied else None,
            "mitglied_email": str(mitglied.email or "") if mitglied else None,
            "mitglied_ausgeschlossen": bool(mitglied.ausgeschlossen) if mitglied else None,
            "mitglied_status": str(mitglied.status) if mitglied else None,
        }
    finally:
        sess.close()


def _unveraendert(vorher: dict, nachher: dict) -> None:
    """Nichts am Zustand von root darf sich geaendert haben."""
    for feld in ("konto_da", "aktiv", "email", "user_type", "passwort", "rollen",
                 "hasrole_zeilen", "root_name", "marker", "mitglied_da",
                 "mitglied_user", "mitglied_email", "mitglied_ausgeschlossen",
                 "mitglied_status"):
        assert nachher[feld] == vorher[feld], (
            f"root wurde veraendert: {feld} war {vorher[feld]!r}, ist {nachher[feld]!r}"
        )
    # Und die Zusagen, die gelten muessen (nicht nur „gleich geblieben“).
    assert nachher["konto_da"] is True, "root-Konto ist weg"
    assert nachher["aktiv"] is True, "root-Konto ist gesperrt"
    assert "root" in nachher["rollen"], f"root verlor die Kennrolle: {nachher['rollen']}"
    assert "System Manager" in nachher["rollen"], f"root verlor System Manager: {nachher['rollen']}"
    assert nachher["marker"] == {ROOT}, f"Marker veraendert: {nachher['marker']}"
    assert nachher["mitglied_user"] == ROOT, "root-Mitglied wurde vom Konto getrennt"
    assert nachher["mitglied_ausgeschlossen"] is False, "root-Mitglied wurde ausgeschlossen"


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


def _probe(client, patched_db, methode: str, pfad: str, body=None, *, als: str = SYSMGR):
    """Fuehrt einen Angriff aus und liefert (Antwort, Zustand_vorher, Zustand_nachher)."""
    _grundstand(patched_db)
    vorher = _root_zustand(patched_db)
    with _als(als):
        aufruf = getattr(client, methode)
        antwort = aufruf(pfad, json=body) if body is not None else aufruf(pfad)
    return antwort, vorher, _root_zustand(patched_db)


def _abgelehnt(antwort, *, code: int = 403) -> None:
    assert antwort.status_code == code, f"{antwort.status_code} statt {code}: {antwort.text[:200]}"


# ── Befund 1 (HOCH): Aussperren ueber das MITGLIED von root ────────────────


def test_mitglied_ausschliessen_ist_403(client, patched_db, fake_redis) -> None:
    """``PUT /api/resource/Mitglied/M-root {"ausgeschlossen": 1}`` war 200.

    Danach lieferte ``get_roles(root)`` die leere Menge — root war ein
    gewoehnliches, ausgeschlossenes Konto.
    """
    antwort, vorher, nachher = _probe(
        client, patched_db, "put", f"/api/resource/Mitglied/{M_ROOT}", {"ausgeschlossen": 1})
    _abgelehnt(antwort)
    _unveraendert(vorher, nachher)


def test_mitglied_loeschen_ist_403(client, patched_db, fake_redis) -> None:
    """``DELETE /api/resource/Mitglied/M-root`` war 202."""
    antwort, vorher, nachher = _probe(
        client, patched_db, "delete", f"/api/resource/Mitglied/{M_ROOT}")
    _abgelehnt(antwort)
    _unveraendert(vorher, nachher)
    assert nachher["mitglied_da"] is True, "das root-Mitglied wurde geloescht"


def test_mitglied_entkoppeln_ist_403(client, patched_db, fake_redis) -> None:
    """``PUT ... {"user": ""}`` war 200 — danach greift der Ausschluss ueber die E-Mail."""
    antwort, vorher, nachher = _probe(
        client, patched_db, "put", f"/api/resource/Mitglied/{M_ROOT}", {"user": ""})
    _abgelehnt(antwort)
    _unveraendert(vorher, nachher)


def test_mitglied_status_ausgetreten_ist_403(client, patched_db, fake_redis) -> None:
    """``PUT ... {"status": "Ausgetreten"}`` war 200 (Austritt ohne Austrittsweg)."""
    antwort, vorher, nachher = _probe(
        client, patched_db, "put", f"/api/resource/Mitglied/{M_ROOT}", {"status": "Ausgetreten"})
    _abgelehnt(antwort)
    _unveraendert(vorher, nachher)


def test_mitglied_email_aendern_ist_403(client, patched_db, fake_redis) -> None:
    """``PUT ... {"email": "evil@…"}`` war 200 (Adresse des root-Mitglieds)."""
    antwort, vorher, nachher = _probe(
        client, patched_db, "put", f"/api/resource/Mitglied/{M_ROOT}", {"email": "evil@x.example"})
    _abgelehnt(antwort)
    _unveraendert(vorher, nachher)


@pytest.mark.parametrize("daten", [
    {"email": "evil@x.example"},
    {"status": "Ausgetreten"},
    {"status": "Passiver Gast"},
], ids=["email", "status-ausgetreten", "status-passiver-gast"])
def test_update_mitglied_ist_403(client, patched_db, fake_redis, daten) -> None:
    """``mitglieder.update_mitglied(M-root, …)`` war 200 (Fachweg am PUT vorbei)."""
    _grundstand(patched_db)
    vorher = _root_zustand(patched_db)
    with _als(SYSMGR):
        antwort = _post(client, "mitglieder.update_mitglied", mitglied_id=M_ROOT, data=daten)
    _abgelehnt(antwort)
    _unveraendert(vorher, _root_zustand(patched_db))


def test_fremdes_mitglied_wird_weiter_ausgeschlossen(client, patched_db, fake_redis) -> None:
    """Kein Ueberschutz: ein normales Mitglied sperrt der Admin weiter (200)."""
    from diakronos_app.models.diakonos import Mitglied

    _grundstand(patched_db)
    sess = patched_db()
    sess.add(Mitglied(name="M-berta", email=MITGLIED, vorname="Berta", nachname="Test",
                      user=MITGLIED, status="Aktiv"))
    sess.commit()
    sess.close()

    with _als(SYSMGR):
        antwort = client.put("/api/resource/Mitglied/M-berta", json={"ausgeschlossen": 1})
    assert antwort.status_code == 200, antwort.text

    sess = patched_db()
    try:
        assert sess.get(Mitglied, "M-berta").ausgeschlossen is True
    finally:
        sess.close()


# ── Befund 2 (HOCH): Uebernahme ueber Felder des User-Kontos ───────────────


@pytest.mark.parametrize("body,felder", [
    ({"email": "evil@x.example"}, ("email",)),
    ({"user_type": "Website User"}, ("user_type",)),
    ({"full_name": "Gekapert"}, ("full_name",)),
    ({"user_image": "/files/evil.png"}, ("user_image",)),
    ({"enabled": 0, "email": "evil@x.example"}, ("enabled", "email")),
], ids=["email", "user_type", "full_name", "user_image", "enabled-plus-email"])
def test_user_felder_schreiben_ist_403(client, patched_db, fake_redis, body, felder) -> None:
    """JEDES geaenderte Feld am root-Konto ist eine Wirkung (vorher 200).

    Die E-Mail ist der gefaehrlichste Fall: die OIDC-Erstanmeldung ordnet
    ueber die VERIFIZIERTE Adresse zu — wer die Adresse von root auf seine
    eigene umbiegt, wird bei der naechsten Anmeldung als root angemeldet.
    """
    antwort, vorher, nachher = _probe(
        client, patched_db, "put", f"/api/resource/User/{ROOT}", body)
    _abgelehnt(antwort)
    assert "geschützt" in antwort.text, antwort.text
    _unveraendert(vorher, nachher)


def test_passwort_hash_direkt_ist_fest(client, patched_db, fake_redis) -> None:
    """``password_hash`` ueber den generischen Weg: 400 (abgelehnt) und unveraendert.

    Der Weg endet schon VOR der Pruefung: das Konto wird beim Speichern des
    Rohfelds abgelehnt (400, „bitte die Eingaben prüfen“) — ein Passwort wird
    nie ueber ``/api/resource`` gesetzt. Geprueft wird deshalb, was zaehlt:
    abgelehnt, und der Hash ist danach derselbe. ``_pruefe_root_schreibzugriff``
    zaehlt dieses Feld ebenfalls als Wirkung (403), damit auch ein spaeterer
    Weg nicht stillschweigend durchrutscht.
    """
    from diakronos_app.frappe_compat.api_helpers import _pruefe_root_schreibzugriff
    from diakronos_app.frappe_compat.exceptions import PermissionError
    from diakronos_app.frappe_compat.session import set_user as _set_user

    antwort, vorher, nachher = _probe(
        client, patched_db, "put", f"/api/resource/User/{ROOT}",
        {"password_hash": "$argon2id$v=19$m=65536,t=3,p=4$evil"})
    _abgelehnt(antwort, code=400)
    _unveraendert(vorher, nachher)

    # Die Schranke selbst kennt das Feld: 403 fuer einen fremden Aufrufer.
    _grundstand(patched_db)
    _set_user(SYSMGR)
    try:
        with pytest.raises(PermissionError):
            _pruefe_root_schreibzugriff("User", ROOT, {"password_hash": "$argon2id$evil"})
    finally:
        _set_user("Administrator")


def test_user_unveraendert_speichern_bleibt_erlaubt(client, patched_db, fake_redis) -> None:
    """Kein Ueberschutz: root darf sein Konto weiter pflegen, auch mit allen Feldern.

    Die SPA schickt das ganze Formular zurueck — unveraenderte Felder sind
    keine Wirkung und duerfen nicht 403 werden.
    """
    _grundstand(patched_db)
    with _als(ROOT):
        antwort = client.put(f"/api/resource/User/{ROOT}", json={
            "email": ROOT, "full_name": ROOT, "enabled": 1,
        })
    assert antwort.status_code == 200, antwort.text


def test_fremdes_konto_email_aendern_bleibt_erlaubt(client, patched_db, fake_redis) -> None:
    """Kein Ueberschutz: die E-Mail eines NICHT-root-Kontos bleibt aenderbar."""
    from diakronos_app.models.core import User

    _grundstand(patched_db)
    with _als(SYSMGR):
        antwort = client.put(f"/api/resource/User/{MITGLIED}", json={"full_name": "Berta Neu"})
    assert antwort.status_code == 200, antwort.text

    sess = patched_db()
    try:
        assert sess.get(User, MITGLIED).full_name == "Berta Neu"
    finally:
        sess.close()


# ── Befund 4 (NIEDRIG): Kennrolle per DELETE entfernen ─────────────────────


def test_kennrolle_loeschen_ist_403(client, patched_db, fake_redis) -> None:
    """``DELETE /api/resource/Has Role/<root>-root`` war 202 (root verlor die Kennung)."""
    from diakronos_app.models.core import HasRole

    _grundstand(patched_db)
    sess = patched_db()
    zeilen = [r.name for r in sess.query(HasRole).filter_by(parent=ROOT, role="root")]
    sess.close()
    assert zeilen == [f"{ROOT}-root"], zeilen

    antwort, vorher, nachher = _probe(
        client, patched_db, "delete", f"/api/resource/Has Role/{ROOT}-root")
    _abgelehnt(antwort)
    _unveraendert(vorher, nachher)


def test_andere_rolle_loeschen_am_root_ist_403(client, patched_db, fake_redis) -> None:
    """Auch die System-Manager-Zeile von root bleibt (kein Weg drumherum)."""
    antwort, vorher, nachher = _probe(
        client, patched_db, "delete", f"/api/resource/Has Role/{ROOT}-Mitgliederadministrator")
    _abgelehnt(antwort)
    _unveraendert(vorher, nachher)


# ── Befund 5 (NIEDRIG): neue Rollenzeile fuer root ─────────────────────────


def test_rolle_an_root_anhaengen_ist_403(client, patched_db, fake_redis) -> None:
    """``POST /api/resource/Has Role {"parent": <root>}`` ohne ``name`` war 200."""
    antwort, vorher, nachher = _probe(
        client, patched_db, "post", "/api/resource/Has Role", {
            "parent": ROOT, "parenttype": "User", "parentfield": "roles",
            "role": "Tester", "idx": 9,
        })
    _abgelehnt(antwort)
    _unveraendert(vorher, nachher)


def test_rolle_fuer_fremdes_konto_bleibt_erlaubt(client, patched_db, fake_redis) -> None:
    """Kein Ueberschutz: einem NICHT-root-Konto eine Rolle geben bleibt erlaubt."""
    _grundstand(patched_db)
    with _als(SYSMGR):
        antwort = client.post("/api/resource/Has Role", json={
            "name": f"{MITGLIED}-Tester", "parent": MITGLIED, "parenttype": "User",
            "parentfield": "roles", "role": "Tester", "idx": 3,
        })
    assert antwort.status_code in (200, 201), antwort.text


# ── Die restlichen Proben der Vorlage (schon durch ON-6/6b geschlossen) ────


@pytest.mark.parametrize("tag,methode,pfad,body", [
    ("user-sperren", "put", f"/api/resource/User/{ROOT}", {"enabled": 0}),
    ("user-sperren-als-string", "put", f"/api/resource/User/{ROOT}", {"enabled": "0"}),
    ("user-loeschen", "delete", f"/api/resource/User/{ROOT}", None),
    ("user-umbenennen", "put", f"/api/resource/User/{ROOT}", {"name": "neu@x.example"}),
    ("system-manager-zeile-loeschen", "delete",
     f"/api/resource/Has Role/{ROOT}-System Manager", None),
    ("rolle-umbiegen", "put", f"/api/resource/Has Role/{ROOT}-System Manager",
     {"role": "Mitglied"}),
    ("zeile-auf-root-umbiegen", "put", f"/api/resource/Has Role/{ROOT}-System Manager",
     {"parent": SYSMGR}),
    ("kennrolle-vergeben", "post", "/api/resource/Has Role",
     {"name": f"{SYSMGR}-root", "parent": SYSMGR, "parenttype": "User",
      "parentfield": "roles", "role": "root", "idx": 5}),
    ("rollen-entziehen", "delete", f"/api/resource/Has Role/{ROOT}-Mitgliederadministrator", None),
], ids=lambda v: v if isinstance(v, str) else "")
def test_weitere_generische_proben_sind_403(client, patched_db, fake_redis,
                                            tag, methode, pfad, body) -> None:
    """Die uebrigen Angriffe der Vorlage — alle 403, root unveraendert."""
    antwort, vorher, nachher = _probe(client, patched_db, methode, pfad, body)
    _abgelehnt(antwort)
    _unveraendert(vorher, nachher)


@pytest.mark.parametrize("pfad,daten", [
    ("zugang.setze_passwort", dict(mitglied_id=M_ROOT, passwort="NeuesPasswort12345!")),
    ("zugang.einladungslink", dict(mitglied_id=M_ROOT)),
    ("zugang.konto_sperren", dict(mitglied_id=M_ROOT, gesperrt=True)),
    ("zugang.setze_rollen", dict(mitglied_id=M_ROOT, rollen=["Mitglied"])),
    ("zugang.konto_freischalten", dict(user=ROOT, freischalten=False)),
    ("austritt.mitglied_austritt", dict(mitglied_id=M_ROOT)),
    ("mitglieder.schliesse_mitglied_aus", dict(mitglied_id=M_ROOT, begruendung="Probe")),
    ("root.root_uebertragen", dict(konto=SYSMGR, passwort=PASSWORT, bestaetigt=True)),
], ids=lambda v: v if isinstance(v, str) else "")
def test_benannte_wege_sind_403(client, patched_db, fake_redis, pfad, daten) -> None:
    """Alle benannten Endpunkte auf das root-Konto: 403, nichts veraendert."""
    _grundstand(patched_db)
    vorher = _root_zustand(patched_db)
    with _als(SYSMGR):
        antwort = _post(client, pfad, **daten)
    _abgelehnt(antwort)
    _unveraendert(vorher, _root_zustand(patched_db))


def test_planrahmen_regression_keine_zweite_sitzung(client, patched_db, fake_redis) -> None:
    """Befund 3: der Planrahmen darf NICHT ueber ``get_roles`` root pruefen.

    ``get_roles`` liest den Ausschluss in einer EIGENEN Sitzung; deren
    ``close()`` reisst auf einer DB mit EINER Verbindung je Engine die offene
    Transaktion des Aufrufers mit. Folge (auf ON-6/6b): ``plan_anlegen``
    antwortete 200, der Plan war weg — 6 Fehler in
    ``test_plan_w1_warnungen_nur_planer.py``, auf main gruen.

    Geprueft wird die ANWEISUNG an der Quelle: ``Rechte.admin`` fragt
    ``root_benutzer.ist_root_in(self.session, …)`` und oeffnet keine zweite
    Sitzung. Der Zustandsbeweis steht in jener Testdatei (gruen) und im Test
    darunter (Ausschluss wirkt in derselben Transaktion).
    """
    import inspect

    from diakronos_app.planrahmen import rechte

    quelle = inspect.getsource(rechte.Rechte.admin)
    # Nur CODE pruefen, nicht die Kommentare (die nennen den alten Weg).
    code = "\n".join(zeile.split("#", 1)[0].strip()
                     for zeile in quelle.splitlines())
    assert "ist_root_in" in code, "Rechte.admin prueft root nicht in der Aufrufer-Sitzung"
    assert "get_roles" not in code, "Rechte.admin ruft weiter get_roles (eigene Sitzung)"
    assert "ist_root(" not in code.replace("ist_root_in", ""), (
        "Rechte.admin prueft mit ist_root (eigene Sitzung) statt ist_root_in"
    )


def test_rechte_admin_liest_root_in_der_aufrufer_transaktion(client, patched_db, fake_redis) -> None:
    """Der Beweis am Verhalten: root ist Plan-Admin, der Ausschluss entzieht es ihm.

    Und der Ausschluss wirkt in DERSELBEN Transaktion (nicht erst nach einem
    Commit in einer zweiten Sitzung).
    """
    from diakronos_app.db import SessionLocal
    from diakronos_app.frappe_compat.exceptions import PermissionError
    from diakronos_app.models.diakonos import Mitglied
    from diakronos_app.planrahmen.rechte import Rechte

    _grundstand(patched_db)
    sess = SessionLocal()
    try:
        assert Rechte(sess, ROOT).admin() is True
        # Ausschluss in DIESER Transaktion setzen — noch nicht committet.
        sess.get(Mitglied, M_ROOT).ausgeschlossen = True
        sess.flush()
        with pytest.raises(PermissionError):
            Rechte(sess, ROOT).admin()
        sess.rollback()
    finally:
        sess.close()


def test_klartext_datei_ist_kein_test(client, patched_db, fake_redis) -> None:
    """Waechter: das Gebiet bleibt beim Namen — kein 200 als „abgelehnt“ durchgewinkt.

    Die Probe-Vorlage (``on6-root-probes.py``) war ein Wegwerf-Export ohne
    Zusagen. Diese Datei ist die bleibende Fassung; jede Probe MUSS einen
    Fehlercode liefern. Der Test haelt fest, dass die Vorlage selbst nie als
    Testdatei im Repo landet (sie druckt nur und wuerde gruen durchlaufen).
    """
    from pathlib import Path

    ordner = Path(__file__).resolve().parent
    assert not (ordner / "on6-root-probes.py").exists()
    assert not (ordner / "test_on6c_root_proben_vorlage.py").exists()
