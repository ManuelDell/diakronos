"""N3 — Registrierungslinks: Zustand, Plaetze und Verlaengern (Backend).

Prueft, was die Karte N3 fuer die Karten im Unterbereich „Links & QR-Codes“
braucht (Konzept Abschnitt 5):
  - die Liste nennt je Link den Zustand (`zustand`, `abgelaufen`, `voll`),
    die Anzahl Plaetze (`plaetze_belegt`, `plaetze_gesamt`) und die offenen
    Anfragen (`anfragen_offen`) sowie den Hinweis, ob ein Serverfilter auf
    `aktiv` (1) den Link ausblenden wuerde (`wuerde_ausgeblendet`),
  - `verlaengern_link` verlaesst den Zustand „Abgelaufen“/„Voll“ wieder.

An der Basis (vor der Behebung) sind diese Faelle rot: die Linkliste kam ohne
`zustand`/`plaetze_*`/`anfragen_offen` und `verlaengern_link` fehlte ganz.
"""
from __future__ import annotations

import datetime

import pytest

import diakronos_app.api  # noqa: F401 — registriert alle portierten Endpunkte
from diakronos_app.frappe_compat.session import set_user

MODUL = "diakronos.diakonos.api.admin_hub"
ADMIN = "mitgliederadmin@example.org"


def _link(**werte):
    from diakronos_app.models.diakonos import Registrierungslink

    daten = {
        "name": "RL-1",
        "bezeichnung": "Gemeindefest 2026",
        "typ": "Mitglied-Registrierung",
        "aktiv": True,
        "slug": "abc123slug",
        "max_anmeldungen": 0,
        "anmeldungen_count": 0,
        "docstatus": 0,
        "idx": 0,
    }
    daten.update(werte)
    return Registrierungslink(**daten)


@pytest.fixture()
def admin_client(client, patched_db):
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


def _hub(client):
    r = client.get(f"/api/method/{MODUL}.get_anmeldungen_hub")
    assert r.status_code == 200, r.text
    return {l["name"]: l for l in r.json()["message"]["links"]}


def test_zustand_aktiv_mit_plaetzen(admin_client, patched_db):
    """Aktiv, Plaetze frei -> zustand 'aktiv', Balkenwerte da."""
    sess = patched_db()
    sess.add(_link(max_anmeldungen=50, anmeldungen_count=12))
    sess.commit()
    sess.close()

    l = _hub(admin_client)["RL-1"]
    assert l["zustand"] == "aktiv", l
    assert l["plaetze_belegt"] == 12, l
    assert l["plaetze_gesamt"] == 50, l
    assert l["abgelaufen"] is False, l
    assert l["voll"] is False, l
    assert l["anfragen_offen"] == 0, l


def test_zustand_abgelaufen(admin_client, patched_db):
    """Gueltig bis gestern -> 'abgelaufen' (und trotz aktiver Spalte gelistet)."""
    gestern = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
    sess = patched_db()
    sess.add(_link(gueltig_bis=datetime.date.fromisoformat(gestern), max_anmeldungen=10))
    sess.commit()
    sess.close()

    l = _hub(admin_client)["RL-1"]
    assert l["zustand"] == "abgelaufen", l
    assert l["abgelaufen"] is True, l


def test_zustand_voll(admin_client, patched_db):
    """Kontingent aufgebraucht -> 'voll'."""
    sess = patched_db()
    sess.add(_link(max_anmeldungen=5, anmeldungen_count=5))
    sess.commit()
    sess.close()

    l = _hub(admin_client)["RL-1"]
    assert l["zustand"] == "voll", l
    assert l["voll"] is True, l


def test_zustand_inaktiv(admin_client, patched_db):
    """Ausgeschaltet -> 'inaktiv' und waere ohne Zustandsliste ausgeblendet."""
    sess = patched_db()
    sess.add(_link(aktiv=False))
    sess.commit()
    sess.close()

    l = _hub(admin_client)["RL-1"]
    assert l["zustand"] == "inaktiv", l
    assert l["wuerde_ausgeblendet"] is True, l


def test_offene_anfragen_gezaehlt(admin_client, patched_db):
    """Offene Anfragen werden je Link gezaehlt (Konzept Abschnitt 5)."""
    from diakronos_app.models.diakonos import Anmeldung

    sess = patched_db()
    sess.add(_link(max_anmeldungen=0))
    for i, status in enumerate(["Anmeldeanfrage", "Anmeldeanfrage", "Bestätigt"]):
        sess.add(Anmeldung(name=f"ANM-{i}", vorname="Anna", nachname=f"Muster{i}",
                           status=status, anmeldedatum=datetime.date.today(),
                           registrierungslink="RL-1", docstatus=0, idx=0))
    sess.commit()
    sess.close()

    l = _hub(admin_client)["RL-1"]
    assert l["anfragen_offen"] == 2, l


def test_verlaengern_hebt_ablauf_auf(admin_client, patched_db):
    """`verlaengern_link` setzt neues Datum und gibt die Zustandsliste zurueck."""
    gestern = datetime.date.today() - datetime.timedelta(days=1)
    in_zwei_wochen = datetime.date.today() + datetime.timedelta(days=14)
    sess = patched_db()
    sess.add(_link(gueltig_bis=gestern, max_anmeldungen=2, anmeldungen_count=2))
    sess.commit()
    sess.close()

    r = admin_client.post(
        "/api/method/diakronos.diakonos.api.registrierungslink_api.verlaengern_link",
        data={"link_id": "RL-1", "gueltig_bis": in_zwei_wochen.isoformat(),
              "max_anmeldungen": 30},
    )
    assert r.status_code == 200, r.text
    antwort = r.json()["message"]
    assert antwort["success"] is True, antwort
    assert antwort["link"]["zustand"] == "aktiv", antwort
    assert antwort["link"]["gueltig_bis"] == in_zwei_wochen.isoformat(), antwort
    assert antwort["link"]["plaetze_gesamt"] == 30, antwort


def test_verlaengern_nur_admin(client, patched_db, guest_client):
    """Ohne Administratorrolle kein Verlaengern (Rechte bleiben serverseitig)."""
    sess = patched_db()
    sess.add(_link())
    sess.commit()
    sess.close()

    r = guest_client.post(
        "/api/method/diakronos.diakonos.api.registrierungslink_api.verlaengern_link",
        data={"link_id": "RL-1", "gueltig_bis": ""},
    )
    assert r.status_code >= 400, r.text


# ── Nacharbeit R-N3-main-commits: Eingabepruefung und Rollen ───────────────


def _einfacher_client(client, patched_db):
    """Angemeldeter Benutzer OHNE Mitgliederadministrator-Rolle."""
    from diakronos_app.models.core import HasRole, User
    from diakronos_app.frappe_compat.session import set_user

    sess = patched_db()
    name = "einfach@example.org"
    if sess.get(User, name) is None:
        sess.add(User(name=name, email=name, full_name="Einfach", enabled=True))
    if not sess.query(HasRole).filter_by(parent=name, role="Mitglied").first():
        sess.add(HasRole(name=f"{name}-M", parent=name, parenttype="User",
                         parentfield="roles", idx=1, role="Mitglied"))
    sess.commit()
    sess.close()
    set_user(name)
    try:
        yield client
    finally:
        set_user("Administrator")


def test_verlaengern_nur_admin_rolle(client, patched_db):
    """Ein angemeldeter Benutzer ohne Adminrolle darf nicht verlaengern."""
    sess = patched_db()
    sess.add(_link())
    sess.commit()
    sess.close()

    for c in _einfacher_client(client, patched_db):
        r = c.post(
            "/api/method/diakronos.diakonos.api.registrierungslink_api.verlaengern_link",
            data={"link_id": "RL-1", "gueltig_bis": ""},
        )
        assert r.status_code >= 400, r.text


def test_verlaengern_ungueltiges_datum_ist_kein_500(admin_client, patched_db):
    """Ein ungueltiges Datum ergibt eine saubere Meldung, keinen 500er."""
    sess = patched_db()
    sess.add(_link())
    sess.commit()
    sess.close()

    r = admin_client.post(
        "/api/method/diakronos.diakonos.api.registrierungslink_api.verlaengern_link",
        data={"link_id": "RL-1", "gueltig_bis": "31.02.2026", "max_anmeldungen": 5},
    )
    assert r.status_code < 500, r.text
    assert "JJJJ-MM-TT" in r.text, r.text


def test_verlaengern_ungueltige_platzzahl_ist_kein_500(admin_client, patched_db):
    """Nicht-Zahl und negative Zahl werden abgewiesen, nicht gespeichert."""
    sess = patched_db()
    sess.add(_link())
    sess.commit()
    sess.close()

    for wert in ("drei", -3):
        r = admin_client.post(
            "/api/method/diakronos.diakonos.api.registrierungslink_api.verlaengern_link",
            data={"link_id": "RL-1", "gueltig_bis": "", "max_anmeldungen": wert},
        )
        assert r.status_code < 500, f"{wert}: {r.text}"
        assert "Platzzahl" in r.text, f"{wert}: {r.text}"

    # Der Link bleibt unveraendert (keine negative Platzzahl gespeichert).
    l = _hub(admin_client)["RL-1"]
    assert l["plaetze_gesamt"] >= 0, l


def test_verlaengern_platzzahl_null_erlaubt(admin_client, patched_db):
    """0 = unbegrenzt ist gueltig."""
    sess = patched_db()
    sess.add(_link(max_anmeldungen=3, anmeldungen_count=3))
    sess.commit()
    sess.close()

    r = admin_client.post(
        "/api/method/diakronos.diakonos.api.registrierungslink_api.verlaengern_link",
        data={"link_id": "RL-1", "gueltig_bis": "", "max_anmeldungen": 0},
    )
    assert r.status_code == 200, r.text
    assert r.json()["message"]["link"]["plaetze_gesamt"] == 0, r.text


def test_alle_links_im_hub_auch_inaktive(admin_client, patched_db):
    """Die Linkliste ist eine Zustandsliste: inaktive Links fehlen nicht."""
    sess = patched_db()
    sess.add(_link(name="RL-A", slug="a", aktiv=True))
    sess.add(_link(name="RL-B", slug="b", aktiv=False))
    sess.commit()
    sess.close()

    namen = set(_hub(admin_client))
    assert {"RL-A", "RL-B"} <= namen, namen

