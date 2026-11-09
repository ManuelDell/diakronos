"""DEV-B3 — Mitglied-Detail-Kleinfixe (Befunde aus dem Dev-Modus, 29.10.).

Geprüft werden die SERVER-Seiten der Karte:

1. DMB-e2a7f41994d7 — Geschlecht nur „Männlich"/„Weiblich" (+ leer). Der
   Server nimmt nur diese Werte an (`update_my_profile`,
   `update_mitglied`, `update_mitglied_with_confirmation`); ein unverändert
   mitgesendetes Altdatum („divers") bleibt zulässig, damit das Speichern
   eines anderen Feldes nicht an Bestandsdaten scheitert.
2. DMB-d78583647c3a — `passwortzugang.link_erzeugen` baut den Link über
   `base_path.pfad`: unter dem Betriebs-Präfix `/diakronos` zeigt er auf
   `/diakronos/diakonos/passwort-setzen#token=…` und läuft dort NICHT in
   eine 404 (vorher fehlte das Präfix, Demo 404).

Die Oberflächenseite steht in `frontend/tests/dev-b3-mitglied-detail.test.mjs`.
"""
from __future__ import annotations

import pytest

ANNA = "anna@example.org"
PROFILE = "diakronos.diakonos.api.profile"


@pytest.fixture()
def welt(patched_db):
    """Anna mit Mitglied (über `user` verknüpft), Geschlecht „w".

    Eigene Fixture statt Import aus `test_p4n_profil`: Fixtures aus einem
    anderen Testmodul sieht pytest hier nicht.
    """
    from diakronos_app.frappe_compat.session import set_user
    from diakronos_app.models.core import User
    from diakronos_app.models.diakonos import Mitglied

    sess = patched_db()
    sess.add(User(name=ANNA, email=ANNA, full_name="Anna Beispiel", enabled=True))
    sess.add(Mitglied(name="M-0001", vorname="Anna", nachname="Beispiel", email=ANNA,
                      status="Mitglied", user=ANNA, docstatus=0, idx=0,
                      wohnort="Stuttgart", postleitzahl="70173",
                      **{"straße": "Hauptstr."}, nummer="7",
                      geschlecht="w", familienstand="verheiratet"))
    sess.commit()
    set_user(ANNA)
    yield sess
    sess.close()


# ── 1 · Eigenes Profil (Profile.vue -> update_my_profile) ───────────────────

@pytest.mark.parametrize("wert, gespeichert", [
    ("Männlich", "Männlich"),
    ("Weiblich", "Weiblich"),
    ("", ""),
    ("  Weiblich  ", "Weiblich"),   # Leerzeichen werden abgeschnitten
])
def test_update_my_profile_nimmt_maennlich_und_weiblich(client, welt, wert, gespeichert):  # noqa: F811
    from diakronos_app.frappe_compat.session import set_user

    set_user(ANNA)
    res = client.post(f"/api/method/{PROFILE}.update_my_profile", json={"geschlecht": wert})
    assert res.status_code == 200, res.text
    data = client.post(f"/api/method/{PROFILE}.get_my_profile").json()["message"]
    assert data["geschlecht"] == gespeichert


@pytest.mark.parametrize("wert", ["Divers", "divers", "d", "inter", "m", "männlich"])
def test_update_my_profile_weist_andere_angaben_ab(client, welt, wert):  # noqa: F811
    """Entscheidung Manuel 2026-10-29: nur männlich oder weiblich."""
    from diakronos_app.models.diakonos import Mitglied
    from diakronos_app.frappe_compat.session import set_user

    set_user(ANNA)
    res = client.post(f"/api/method/{PROFILE}.update_my_profile", json={"geschlecht": wert})
    assert res.status_code == 417, res.text
    assert "Männlich" in res.text and "Weiblich" in res.text, "Meldung nennt die beiden Werte"
    # Nichts geschrieben: der alte Wert steht noch da.
    welt.expire_all()
    assert welt.query(Mitglied).filter(Mitglied.name == "M-0001").one().geschlecht == "w"


def test_update_my_profile_alte_divers_angabe_bleibt_beim_speichern_gueltig(client, welt):  # noqa: F811
    """Ein Altdatum „divers" blockiert das Speichern anderer Felder nicht.

    Die SPA schickt das ganze Formular; ohne diese Ausnahme scheiterte jedes
    Speichern einer Person mit Altdatum — obwohl der Wert gar nicht geändert
    wurde. Die Datenbank wird dabei NICHT umgeschrieben (keine stille
    Datenänderung ohne Auftrag).
    """
    from diakronos_app.models.diakonos import Mitglied
    from diakronos_app.frappe_compat.session import set_user

    welt.get(Mitglied, "M-0001").geschlecht = "divers"
    welt.commit()

    set_user(ANNA)
    res = client.post(f"/api/method/{PROFILE}.update_my_profile",
                      json={"wohnort": "Freiburg", "geschlecht": "divers"})
    assert res.status_code == 200, res.text
    welt.expire_all()
    mitglied = welt.get(Mitglied, "M-0001")
    assert mitglied.wohnort == "Freiburg"
    assert mitglied.geschlecht == "divers", "Altdatum bleibt stehen (nicht umgeschrieben)"

    # Wird der Wert GEÄNDERT, gilt die neue Regel — z. B. auf leer.
    res = client.post(f"/api/method/{PROFILE}.update_my_profile", json={"geschlecht": ""})
    assert res.status_code == 200, res.text
    welt.expire_all()
    assert welt.get(Mitglied, "M-0001").geschlecht == ""


# ── 2 · Mitgliederverwaltung (MitgliedDetail.vue -> update_mitglied) ────────

@pytest.fixture()
def verwaltung(patched_db, set_user, monkeypatch):
    """Mitglied + Bearbeitungsrecht für `update_mitglied`.

    Das Recht wird an EINER Stelle gesetzt (`permissions.mitglied_permissions`
    im Mitglieder-Modul, Muster wie `test_austritt_c._detail`) — es geht hier
    nicht um die Rechteprüfung (die prüft P4l), sondern um die
    Geschlechts-Regel des Schreibwegs.
    """
    from diakronos_app.api import mitglieder as m
    from diakronos_app.models.core import User
    from diakronos_app.models.diakonos import Mitglied

    with patched_db() as sess:
        sess.add(User(name="dev-b3-admin", email="dev-b3-admin@example.org", enabled=True))
        sess.add(Mitglied(name="DB3-0001", vorname="Erika", nachname="Beispiel",
                          status="Mitglied", docstatus=0, idx=0))
        sess.commit()
    set_user("dev-b3-admin")
    monkeypatch.setattr(
        m.permissions, "mitglied_permissions",
        lambda *a, **k: {"can_view": True, "can_edit": True, "can_delete": False,
                         "can_view_sensitive": True, "reason": "test"},
    )
    return "DB3-0001"


def _geschlecht_im_bestand(patched_db, name: str):
    from diakronos_app.models.diakonos import Mitglied

    with patched_db() as sess:
        return sess.get(Mitglied, name).geschlecht


@pytest.mark.parametrize("pfad", [
    "diakronos.diakonos.api.mitglieder.update_mitglied",
    "diakronos.diakonos.api.mitglieder.update_mitglied_with_confirmation",
])
def test_update_mitglied_nimmt_nur_maennlich_und_weiblich(verwaltung, patched_db, client, pfad):
    """BEIDE Schreibwege der Mitgliederverwaltung prüfen dasselbe.

    Vorher nahm keiner von beiden das Feld überhaupt an — jetzt gilt für
    beide dieselbe Regel (kein Weg, der sie umgeht).
    """
    argumente = {"mitglied_id": verwaltung, "data": {"geschlecht": "Männlich"}}
    if pfad.endswith("with_confirmation"):
        argumente["audit_confirmation"] = {}
    res = client.post(f"/api/method/{pfad}", json=argumente)
    assert res.status_code == 200, res.text
    assert _geschlecht_im_bestand(patched_db, verwaltung) == "Männlich"

    argumente["data"] = {"geschlecht": "Divers"}
    res = client.post(f"/api/method/{pfad}", json=argumente)
    assert res.status_code == 417, res.text
    assert "Männlich" in res.text and "Weiblich" in res.text
    assert _geschlecht_im_bestand(patched_db, verwaltung) == "Männlich", "nichts geschrieben"


def test_update_mitglied_alte_divers_angabe_bleibt_gueltig(verwaltung, patched_db, client):
    """Altdatum „divers" blockiert das Speichern unverwandter Felder nicht."""
    from diakronos_app.models.diakonos import Mitglied

    with patched_db() as sess:
        sess.get(Mitglied, verwaltung).geschlecht = "divers"
        sess.commit()

    res = client.post("/api/method/diakronos.diakonos.api.mitglieder.update_mitglied",
                      json={"mitglied_id": verwaltung,
                            "data": {"telefonnummer": "0711 1", "geschlecht": "divers"}})
    assert res.status_code == 200, res.text
    assert _geschlecht_im_bestand(patched_db, verwaltung) == "divers"


# ── 3 · Passwort-Link mit Pfad-Präfix ───────────────────────────────────────

@pytest.fixture()
def konto(patched_db):
    from diakronos_app.models.core import User
    from diakronos_app.frappe_compat.passwoerter import neuer_hash

    with patched_db() as sess:
        sess.add(User(name="dev-b3-neu@example.org", email="dev-b3-neu@example.org",
                      enabled=True, password_hash=neuer_hash("Startpasswort-123")))
        sess.commit()
    return "dev-b3-neu@example.org"


def test_passwortlink_ohne_praefix_unveraendert(konto):
    """Ohne Betriebs-Präfix bleibt der Link wie bisher (Bestandsschutz)."""
    from diakronos_app import base_path
    from diakronos_app.anmeldung.passwortzugang import link_erzeugen

    base_path.setze_praefix("")
    link = link_erzeugen(konto)["link"]
    anfang, _, kennung = link.partition("#token=")
    assert anfang == "/diakonos/passwort-setzen"
    assert len(kennung) == 43, "256-Bit-Kennung wie bisher"


def test_passwortlink_traegt_den_betriebspraefix(konto):
    """DMB-d78583647c3a: unter `/diakronos` liegt die Seite eine Ebene tiefer.

    Vorher baute `link_erzeugen` den Pfad OHNE Präfix — der Link zeigte im
    Betrieb auf `/diakonos/passwort-setzen` und lief in eine 404.
    """
    from diakronos_app import base_path
    from diakronos_app.anmeldung.passwortzugang import link_erzeugen

    base_path.setze_praefix("/diakronos")
    try:
        link = link_erzeugen(konto, erstwechsel=True)["link"]
        assert link.startswith("/diakronos/diakonos/passwort-setzen#token="), link
        assert base_path.pfad(link.split("#")[0]) == link.split("#")[0], "nicht doppelt präfigiert"
    finally:
        base_path.setze_praefix("")
