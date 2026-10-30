"""SEC-3 — Registrierungstoken stark erzeugen + Rate-Limit auf Token-Endpunkte.

Befunde aus dem Pentest von dev.ecg-hn.de (MITTEL):

  (a) `POST /api/resource/Registrierungslink` nahm einen frei gewaehlten,
      kurzen `slug` an ("pt-mitglied"). Der Token eines NEUEN Links muss
      serverseitig mit hoher Entropie entstehen (`secrets.token_urlsafe(32)`);
      bestehende Links bleiben unveraendert gueltig.
  (b) `validate_token` und `submit_registrierung` waren gegenueber dem
      Pentest NICHT gebremst — `registrierung_max_validierung` griff nicht,
      Token-Enumeration lief ungebremst. Ein ueberschrittenes Limit muss als
      HTTP 429 ankommen; die erste, legitime Validierung bleibt erlaubt.

Die Datei ist der Reproduktionstest: an der Basis (vor der Aenderung) sind
S1/S2 rot. Zahlen sind an `settings` gepatcht, nie an echten Grenzen — und
alle Aufrufe laufen ueber `patched_db`/`fake_redis` (nie gegen die
Betriebs-DB oder das Betriebs-Redis).
"""

from __future__ import annotations

import string

import pytest

import diakronos_app.api  # noqa: F401 — registriert alle portierten Endpunkte
from diakronos_app.frappe_compat.session import set_user

MODUL = "diakronos.diakonos.api.registrierung"
MODUL_LINK = "diakronos.diakonos.api.registrierungslink_api"

SLUG = "abc123slug"
LINK = "RL-1"
ADMIN = "mitgliederadmin@example.org"
KUNDEN_IP = "203.0.113.7"


# ── Fixtures ───────────────────────────────────────────────────────────────


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
    from diakronos_app.models.diakonos import Anmeldeformular, AnmeldeformularFeld

    sess = patched_db()
    sess.add(_link(anmeldeformular="AF-1"))
    sess.add(
        Anmeldeformular(
            name="AF-1", bezeichnung="Standard", mit_kinder=True, mit_gaesten=True,
            docstatus=0, idx=0,
        )
    )
    sess.add(
        AnmeldeformularFeld(
            name="AFF-1", parent="AF-1", parentfield="felder", parenttype="Anmeldeformular",
            idx=1, label="Ernaehrung", feldtyp="Select", optionen="omnivor,vegan",
            pflichtfeld=True, fuer_gaeste=False, fuer_kinder=True, docstatus=0,
        )
    )
    sess.commit()
    yield sess
    sess.close()


@pytest.fixture()
def admin_client(client, patched_db):
    """Angemeldeter Mitgliederadministrator (`create_link` verlangt die Rolle)."""
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


def _mit_ip(monkeypatch, ip=KUNDEN_IP):
    """Setzt die Client-IP des laufenden Requests auf eine zaehlbare Adresse.

    Der TestClient hat als Host `testclient` (kein gueltiges IP-Literal); der
    IP-Zaehler wuerde ihn — wie jede eigene/ungueltige Adresse — ueberspringen.
    Dieselbe Naht, die `BEHIND_PROXY` im Betrieb nutzt.
    """
    from diakronos_app import request_context

    monkeypatch.setattr(request_context, "zaehler_client_ip", lambda: ip)


def _post_anmeldung(client, **extra):
    """Minimal gueltiger Registrierungs-POST (inkl. Einwilligung)."""
    daten = {"token": SLUG, "vorname": "Anna", "nachname": "Beispiel", "dsgvo": True}
    daten.update(extra)
    return client.post(f"/api/method/{MODUL}.submit_registrierung", data=daten)


def _validiere(client, token=SLUG):
    return client.get(f"/api/method/{MODUL}.validate_token", params={"token": token})


def _slug_der_zeile(patched_db, name):
    from diakronos_app.models.diakonos import Registrierungslink

    sess = patched_db()
    try:
        zeile = sess.get(Registrierungslink, name)
        return zeile.slug if zeile else None
    finally:
        sess.close()


# Zeichen, die `secrets.token_urlsafe` (base64url ohne Padding) erzeugt.
URLSAFE_ZEICHEN = set(string.ascii_letters + string.digits + "-_")


# ════════════════════════════════════════════════════════════════════════════
# S1 — es gibt keinen Weg, einen schwachen Slug in einen neuen Link zu bekommen
# ════════════════════════════════════════════════════════════════════════════


def test_s1_create_link_ignoriert_gewuenschten_kurzen_slug(admin_client, patched_db):
    """Ein mitgeschickter Wunsch-Slug ("pt-mitglied") wird NICHT uebernommen."""
    r = admin_client.post(
        f"/api/method/{MODUL_LINK}.create_link",
        json={
            "bezeichnung": "Pentest",
            "typ": "Mitglied-Registrierung",
            "slug": "pt-mitglied",
        },
    )
    assert r.status_code == 200, r.text
    link = r.json()["message"]["link"]

    assert link["slug"] != "pt-mitglied", "der Wunsch-Slug wurde uebernommen"
    assert len(link["slug"]) >= 43, link["slug"]
    assert set(link["slug"]) <= URLSAFE_ZEICHEN, link["slug"]
    assert "pt-mitglied" not in link["link_anzeige"], link["link_anzeige"]

    gespeichert = _slug_der_zeile(patched_db, link["name"])
    assert gespeichert == link["slug"], "die Antwort nennt einen anderen Slug als die Datenbank"


def test_s1_create_link_slug_traegt_viele_zufaellige_zeichen(admin_client, patched_db):
    """Zwei neue Links: verschiedene Slugs, beide lang und zufaellig gemischt.

    `secrets.token_urlsafe(32)` ergibt 43 Zeichen aus Buchstaben, Ziffern,
    `-` und `_`. Eine Ableitung aus der Bezeichnung („sommerfest“) hat weder
    diese Laenge noch Ziffern/Grossbuchstaben in dieser Mischung.
    """
    slugs = []
    for name in ("Sommerfest A", "Sommerfest B"):
        r = admin_client.post(
            f"/api/method/{MODUL_LINK}.create_link",
            json={"bezeichnung": name, "typ": "Mitglied-Registrierung", "slug": "kurz"},
        )
        assert r.status_code == 200, r.text
        slugs.append(r.json()["message"]["link"]["slug"])

    assert len(set(slugs)) == 2
    for slug in slugs:
        assert len(slug) >= 43, slug
        assert set(slug) <= URLSAFE_ZEICHEN, slug
        assert any(z.isdigit() for z in slug), f"kein Zufall erkennbar: {slug}"


def test_s1_generischer_ressourcenweg_vergibt_ebenfalls_einen_starken_slug(
    admin_client, patched_db
):
    """Auch `POST /api/resource/Registrierungslink` (Pentest-Weg) kann keinen
    schwachen Slug setzen — die Regel haengt am Server, nicht am einen Endpunkt."""
    r = admin_client.post(
        "/api/resource/Registrierungslink",
        json={
            "bezeichnung": "Ressource-Weg",
            "typ": "Mitglied-Registrierung",
            "slug": "pt-mitglied",
            "aktiv": 1,
        },
    )
    assert r.status_code == 200, r.text
    slug = r.json()["data"]["slug"]
    assert slug != "pt-mitglied", "der Wunsch-Slug wurde uebernommen"
    assert len(slug) >= 43, slug


def test_s1_bestehender_link_bleibt_mit_altem_slug_gueltig(admin_client, welt):
    """Nur NEUANLAGEN sind betroffen: ein vorhandener kurzer Slug bleibt nutzbar."""
    r = _validiere(admin_client, SLUG)
    assert r.status_code == 200, r.text
    assert r.json()["message"]["typ"] == "Mitglied-Registrierung"


# ════════════════════════════════════════════════════════════════════════════
# S2 — Rate-Limit auf validate_token und submit_registrierung
# ════════════════════════════════════════════════════════════════════════════


def test_s2_erste_validierung_ist_erlaubt(client, welt, fake_redis, monkeypatch):
    """Gegenprobe: die legitime Erst-Validierung wird nicht gebremst."""
    from diakronos_app.settings import settings

    _mit_ip(monkeypatch)
    monkeypatch.setattr(settings, "registrierung_max_validierung", 3)

    r = _validiere(client)
    assert r.status_code == 200, r.text


def test_s2_validate_token_ueber_dem_limit_antwortet_429(
    client, welt, fake_redis, monkeypatch
):
    """Nach `registrierung_max_validierung` Pruefungen je Adresse kommt 429.

    Der Pentest fand 12 ungebremste Aufrufe mit ungueltigem Token. Hier ist
    die Grenze 3: die vierte Pruefung MUSS als HTTP 429 ankommen.
    """
    from diakronos_app.settings import settings

    _mit_ip(monkeypatch)
    monkeypatch.setattr(settings, "registrierung_max_validierung", 3)

    codes = [_validiere(client).status_code for _ in range(3)]
    assert codes == [200, 200, 200], codes

    gebremst = _validiere(client)
    assert gebremst.status_code == 429, gebremst.text
    assert "zu viele" in gebremst.text.lower(), gebremst.text


def test_s2_validate_token_bremse_gilt_auch_fuer_erfundene_tokens(
    client, welt, fake_redis, monkeypatch
):
    """Token-Enumeration: auch ungueltige Tokens verbrauchen das Adresskontingent."""
    from diakronos_app.settings import settings

    _mit_ip(monkeypatch)
    monkeypatch.setattr(settings, "registrierung_max_validierung", 4)

    codes = [_validiere(client, f"geraten{i}").status_code for i in range(4)]
    assert all(c in (403, 417) for c in codes), codes

    assert _validiere(client, "geraten99").status_code == 429


def test_s2_submit_registrierung_ueber_dem_limit_antwortet_429(
    client, welt, fake_redis, monkeypatch
):
    """Nach `registrierung_max_ip` Absendeversuchen je Adresse kommt 429."""
    from diakronos_app.settings import settings

    _mit_ip(monkeypatch)
    monkeypatch.setattr(settings, "registrierung_max_ip", 2)
    monkeypatch.setattr(settings, "registrierung_max_link", 100)

    assert _post_anmeldung(client, nachname="Erste").status_code == 200
    assert _post_anmeldung(client, nachname="Zweite").status_code == 200

    gebremst = _post_anmeldung(client, nachname="Dritte")
    assert gebremst.status_code == 429, gebremst.text
    assert "zu viele" in gebremst.text.lower(), gebremst.text


def test_s2_limit_null_schaltet_die_bremse_aus(client, welt, fake_redis, monkeypatch):
    """`0` heisst ausdruecklich unbegrenzt (bestehende Zusage der Einstellungen)."""
    from diakronos_app.settings import settings

    _mit_ip(monkeypatch)
    monkeypatch.setattr(settings, "registrierung_max_validierung", 0)

    codes = [_validiere(client).status_code for _ in range(8)]
    assert codes == [200] * 8, codes
