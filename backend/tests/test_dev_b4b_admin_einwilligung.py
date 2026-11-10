"""DEV-B4b — Verwaltung setzt Einwilligungen („vom Admin gesetzt am … durch …“).

Befund DMB-623c6e586e03 (dev, 29.10., Wunsch Manuel): Admins muessen die
INTERNEN Einwilligungen eines Mitglieds setzen koennen (erste Datenpflege
oder persoenliche Bitte) — ohne Pflicht-Begruendung, aber ersichtlich.

Was hier festgehalten wird:

  1. `admin_einwilligung_setzen` setzt `datenschutz`/`foto` und legt JE
     Aenderung einen `DSGVO Einwilligung`-Eintrag mit `quelle="admin"` und
     Zeitstempel an.
  2. Die Anzeige-Herkunft („vom Admin gesetzt am … durch …“) kommt aus genau
     diesem Protokoll (`dsgvo.datenschutz_von_admin` / `.foto_von_admin`) und
     ist NUR fuer Berechtigte da.
  3. Die WEBSITE-Einwilligung (BS-3a) laesst sich ueber diesen Weg NICHT
     setzen: 417, Allowlist, nichts geschrieben — und die zentrale Schranke
     (`website/einwilligung.py`) bleibt unveraendert scharf.
  4. Rechte: ohne `can_edit` (Nicht-Admin auf fremdes Mitglied) 403; als
     Gast 403; falsche Methode 405.
  5. Ein Widerruf durch die Verwaltung setzt den Schalter auf Nein, loescht
     das Datum und hinterlaesst KEINE „vom Admin gesetzt“-Marke.

Netz (Kartenregel 11): `patched_db` (In-Memory-SQLite), `fake_redis`; kein
Test greift auf `settings.database_url` zu, keiner spricht nach aussen.
"""

from __future__ import annotations

import pytest

import diakronos_app.api  # noqa: F401 — registriert alle portierten Endpunkte
from diakronos_app.frappe_compat import sitzungen
from diakronos_app.frappe_compat.session import set_user
from diakronos_app.models.core import HasRole, User
from diakronos_app.models.diakonos import DSGVOEinwilligung, Mitglied

PFAD_SETZEN = "/api/method/mitglieder.admin_einwilligung_setzen"
PFAD_DETAIL = "/api/method/mitglieder.get_mitglied_detail"
PFAD_WIDERRUF = "/api/method/mitglieder.widerruf_einwilligung"

ADMIN_MAIL = "verwaltung@example.org"
PERSON_MAIL = "anna@example.org"


# ── Helfer ──────────────────────────────────────────────────────────────────


def _benutzer(sess, email: str, rollen=()) -> str:
    if sess.get(User, email) is None:
        sess.add(User(name=email, email=email, full_name=email, enabled=True))
        for idx, rolle in enumerate(rollen, start=1):
            sess.add(
                HasRole(
                    name=f"{email}-{rolle}",
                    parent=email,
                    parenttype="User",
                    parentfield="roles",
                    role=rolle,
                    docstatus=0,
                    idx=idx,
                )
            )
    return email


def _mitglied(sess, name: str, *, user: str | None = None, email: str | None = None,
              status: str = "Mitglied") -> Mitglied:
    zeile = Mitglied(
        name=name,
        vorname="Anna",
        nachname=f"Beispiel-{name}",
        email=email or f"{name}@example.org",
        user=user,
        status=status,
        ancestor_path=f"/{name}",
    )
    sess.add(zeile)
    return zeile


@pytest.fixture()
def welt(patched_db):
    """Bestand: eine Verwaltung, zwei Mitglieder (eines ohne eigenes Konto)."""
    sess = patched_db()
    _benutzer(sess, ADMIN_MAIL, ("Mitgliederadministrator",))
    _benutzer(sess, PERSON_MAIL, ("Mitglied",))
    _mitglied(sess, "M-0001", user=PERSON_MAIL)
    _mitglied(sess, "M-0002")
    sess.commit()
    yield sess
    sess.close()


@pytest.fixture()
def als(welt, patched_db, fake_redis):
    """Factory: HTTP-Client mit echter Sitzung und CSRF-Token."""
    from fastapi.testclient import TestClient

    from diakronos_app.main import app

    erzeugt: list[TestClient] = []

    def _bauen(benutzer: str) -> TestClient:
        set_user(benutzer)
        sid, csrf = sitzungen.anlegen(benutzer)
        c = TestClient(app)
        c.__enter__()
        c.cookies.set("sid", sid)
        c.headers["X-Frappe-CSRF-Token"] = csrf
        erzeugt.append(c)
        return c

    yield _bauen
    for c in erzeugt:
        c.__exit__(None, None, None)


def _dsgvo_zeilen(sess, mitglied: str) -> list[DSGVOEinwilligung]:
    sess.expire_all()
    return (
        sess.query(DSGVOEinwilligung)
        .filter(DSGVOEinwilligung.mitglied == mitglied)
        .order_by(DSGVOEinwilligung.creation)
        .all()
    )


def _lesen(sess, mitglied: str) -> Mitglied:
    sess.expire_all()
    return sess.get(Mitglied, mitglied)


# ── Setzen: Wert, Datum, Protokoll ──────────────────────────────────────────


def test_admin_setzt_datenschutz_mit_protokoll(als, welt):
    c = als(ADMIN_MAIL)
    r = c.post(PFAD_SETZEN, json={"mitglied_id": "M-0001", "typ": "datenschutz",
                                  "erteilt": True})
    assert r.status_code == 200, r.text
    antwort = r.json()["message"]
    assert antwort["success"] is True
    assert antwort["erteilt"] is True
    assert antwort["von_admin"] is True
    assert antwort["datum"], "das Datum der Erteilung muss gesetzt sein"

    zeile = _lesen(welt, "M-0001")
    assert bool(zeile.datenschutz_einwilligung) is True
    assert zeile.datenschutz_datum is not None

    eintraege = _dsgvo_zeilen(welt, "M-0001")
    assert len(eintraege) == 1, [e.aktion for e in eintraege]
    assert eintraege[0].typ == "datenschutz"
    assert eintraege[0].aktion == "erteilt"
    assert eintraege[0].quelle == "admin"
    assert eintraege[0].zeitstempel is not None


def test_admin_setzt_foto_und_protokoll_nennt_admin(als, welt):
    c = als(ADMIN_MAIL)
    r = c.post(PFAD_SETZEN, json={"mitglied_id": "M-0002", "typ": "foto", "erteilt": True})
    assert r.status_code == 200, r.text

    zeile = _lesen(welt, "M-0002")
    assert bool(zeile.foto_einwilligung) is True
    assert zeile.foto_datum is not None

    eintraege = _dsgvo_zeilen(welt, "M-0002")
    assert [(e.typ, e.aktion, e.quelle) for e in eintraege] == [
        ("foto", "erteilt", "admin")
    ]
    assert eintraege[0].owner == ADMIN_MAIL, "Admin-Kennung fehlt im Protokoll"


def test_mehrfaches_setzen_loggt_jede_aenderung(als, welt):
    """Kein stilles Überschreiben: zwei Aufrufe = zwei Protokollzeilen."""
    c = als(ADMIN_MAIL)
    for _ in range(2):
        r = c.post(PFAD_SETZEN, json={"mitglied_id": "M-0001", "typ": "datenschutz",
                                      "erteilt": True})
        assert r.status_code == 200, r.text
    assert len(_dsgvo_zeilen(welt, "M-0001")) == 2


def test_datum_falsch_ist_ein_fehler_und_schreibt_nichts(als, welt):
    c = als(ADMIN_MAIL)
    r = c.post(PFAD_SETZEN, json={"mitglied_id": "M-0001", "typ": "datenschutz",
                                  "erteilt": "vielleicht"})
    assert r.status_code == 417, r.text
    assert bool(_lesen(welt, "M-0001").datenschutz_einwilligung) is False
    assert _dsgvo_zeilen(welt, "M-0001") == []


# ── Anzeige „vom Admin gesetzt am … durch …“ ───────────────────────────────


def test_detail_zeigt_herkunft_nur_fuer_berechtigte(als, welt):
    c = als(ADMIN_MAIL)
    r = c.post(PFAD_SETZEN, json={"mitglied_id": "M-0001", "typ": "datenschutz",
                                  "erteilt": True})
    assert r.status_code == 200, r.text

    detail = c.post(PFAD_DETAIL, json={"mitglied_id": "M-0001"})
    assert detail.status_code == 200, detail.text
    dsgvo = detail.json()["message"]["data"]["dsgvo"]
    assert dsgvo["datenschutz"] is True
    herkunft = dsgvo.get("datenschutz_von_admin")
    assert herkunft, f"keine Herkunftsangabe: {dsgvo}"
    assert herkunft["durch"] == ADMIN_MAIL
    assert herkunft["am"], "Zeitpunkt der Verwaltungs-Änderung fehlt"
    # Die nicht gesetzte Einwilligung traegt keine Marke.
    assert "foto_von_admin" not in dsgvo or dsgvo["foto_von_admin"] is None

    # Die Person selbst sieht ihre Werte (eigenes Mitglied = vollstaendig);
    # die Herkunfts-Marke bleibt der VERWALTUNG vorbehalten — sie nennt den
    # handelnden Administrator und gehoert nicht in die Selbstauskunft.
    person = als(PERSON_MAIL)
    eigen = person.post(PFAD_DETAIL, json={"mitglied_id": "M-0001"})
    assert eigen.status_code == 200, eigen.text
    eigen_dsgvo = eigen.json()["message"]["data"]["dsgvo"]
    assert eigen_dsgvo["datenschutz"] is True
    assert not eigen_dsgvo.get("datenschutz_von_admin"), eigen_dsgvo


def test_nonadmin_sieht_fremde_einwilligung_nicht(als, welt):
    """Ohne can_view_sensitive bleibt der DSGVO-Block leer (B2, unveraendert)."""
    c = als(ADMIN_MAIL)
    assert c.post(PFAD_SETZEN, json={"mitglied_id": "M-0002", "typ": "datenschutz",
                                     "erteilt": True}).status_code == 200

    fremd = als(PERSON_MAIL)
    r = fremd.post(PFAD_DETAIL, json={"mitglied_id": "M-0002"})
    # Kein Sichtrecht (kein ancestor_path-Overlap) -> 403, sonst maskiert.
    if r.status_code == 200:
        dsgvo = r.json()["message"]["data"]["dsgvo"]
        assert dsgvo["datenschutz"] is None
        assert not dsgvo.get("datenschutz_von_admin")
    else:
        assert r.status_code in (403, 417), r.text


# ── Website-Einwilligung bleibt ausschliesslich bei der Person ─────────────


@pytest.mark.parametrize("typ", ["website", "website_foto", "website_einwilligung"])
def test_admin_setzt_nie_die_website_einwilligung(als, welt, typ):
    c = als(ADMIN_MAIL)
    r = c.post(PFAD_SETZEN, json={"mitglied_id": "M-0001", "typ": typ, "erteilt": True})
    assert r.status_code == 417, r.text
    assert "nur die Person selbst" in r.text

    zeile = _lesen(welt, "M-0001")
    assert bool(zeile.website_einwilligung) is False
    assert bool(zeile.website_einwilligung_foto) is False
    assert zeile.website_einwilligung_am is None
    assert _dsgvo_zeilen(welt, "M-0001") == []


def test_allowlist_kennt_nur_datenschutz_und_foto():
    from diakronos_app.api.mitglieder import ADMIN_EINWILLIGUNGEN

    assert set(ADMIN_EINWILLIGUNGEN) == {"datenschutz", "foto"}
    from diakronos_app.website.einwilligung import FELDER_EINWILLIGUNG

    for schalter, datum in ADMIN_EINWILLIGUNGEN.values():
        assert schalter not in FELDER_EINWILLIGUNG
        assert datum not in FELDER_EINWILLIGUNG


# ── Rechte / Methoden ──────────────────────────────────────────────────────


def test_gast_wird_abgewiesen(guest_client):
    r = guest_client.post(PFAD_SETZEN, json={"mitglied_id": "M-0001",
                                             "typ": "datenschutz", "erteilt": True})
    assert r.status_code in (401, 403, 417), r.text


def test_nicht_admin_auf_fremdes_mitglied_403(als, welt):
    c = als(PERSON_MAIL)
    r = c.post(PFAD_SETZEN, json={"mitglied_id": "M-0002", "typ": "datenschutz",
                                  "erteilt": True})
    assert r.status_code == 403, r.text
    assert bool(_lesen(welt, "M-0002").datenschutz_einwilligung) is False
    assert _dsgvo_zeilen(welt, "M-0002") == []


def test_nur_post(als):
    c = als(ADMIN_MAIL)
    r = c.get(PFAD_SETZEN, params={"mitglied_id": "M-0001", "typ": "datenschutz",
                                   "erteilt": "true"})
    assert r.status_code in (405, 417), r.text


# ── Widerruf durch die Verwaltung ──────────────────────────────────────────


def test_widerruf_durch_admin_entfernt_datum_und_marke(als, welt):
    c = als(ADMIN_MAIL)
    assert c.post(PFAD_SETZEN, json={"mitglied_id": "M-0001", "typ": "foto",
                                     "erteilt": True}).status_code == 200

    r = c.post(PFAD_SETZEN, json={"mitglied_id": "M-0001", "typ": "foto", "erteilt": False})
    assert r.status_code == 200, r.text
    zeile = _lesen(welt, "M-0001")
    assert bool(zeile.foto_einwilligung) is False
    assert zeile.foto_datum is None, "ein Datum ohne Einwilligung wäre ein falscher Nachweis"

    eintraege = _dsgvo_zeilen(welt, "M-0001")
    assert [(e.aktion, e.quelle) for e in eintraege] == [
        ("erteilt", "admin"), ("widerrufen", "admin"),
    ]

    detail = c.post(PFAD_DETAIL, json={"mitglied_id": "M-0001"})
    dsgvo = detail.json()["message"]["data"]["dsgvo"]
    assert dsgvo["foto"] is False
    assert not dsgvo.get("foto_von_admin"), "Widerruf trägt keine „gesetzt“-Marke"


def test_person_widerruf_hebt_die_admin_marke_auf(als, welt):
    """Nach einem Widerruf (welche Quelle auch immer) gilt der letzte Eintrag."""
    c = als(ADMIN_MAIL)
    assert c.post(PFAD_SETZEN, json={"mitglied_id": "M-0001", "typ": "datenschutz",
                                     "erteilt": True}).status_code == 200
    assert c.post(PFAD_WIDERRUF, json={"mitglied_id": "M-0001"}).status_code == 200

    detail = c.post(PFAD_DETAIL, json={"mitglied_id": "M-0001"})
    dsgvo = detail.json()["message"]["data"]["dsgvo"]
    assert dsgvo["datenschutz"] is False
    assert not dsgvo.get("datenschutz_von_admin")


PFAD_PROFIL = "/api/method/profile.update_einwilligung"


def test_person_ersetzt_admin_marke_selbst(als, welt):
    """Admin setzt Foto → Person widerruft selbst → Person erteilt selbst:
    die Marke „vom Admin gesetzt“ darf danach NICHT mehr erscheinen."""
    a = als(ADMIN_MAIL)
    assert a.post(PFAD_SETZEN, json={"mitglied_id": "M-0001", "typ": "foto",
                                     "erteilt": True}).status_code == 200
    p = als(PERSON_MAIL)
    assert p.post(PFAD_PROFIL, json={"typ": "foto", "erteilt": 0}).status_code == 200, "w"
    assert p.post(PFAD_PROFIL, json={"typ": "foto", "erteilt": 1}).status_code == 200, "e"
    a = als(ADMIN_MAIL)
    dsgvo = a.post(PFAD_DETAIL, json={"mitglied_id": "M-0001"}).json()["message"]["data"]["dsgvo"]
    assert dsgvo["foto"] is True
    assert not dsgvo.get("foto_von_admin"), dsgvo.get("foto_von_admin")
