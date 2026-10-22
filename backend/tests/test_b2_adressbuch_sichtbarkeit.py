"""B2 — Adressbuch-Sichtbarkeit wird serverseitig durchgesetzt.

BEFUND (vorher, live am Stack reproduziert): `get_mitglieder_liste` und
`get_mitglied_detail` lieferten Telefon, Geburtstag, Anschrift, `notiz` und
alle Einwilligungsfelder an jeden Nutzer mit `can_view` — die pro Mitglied
gesetzte `adressbuch_sichtbarkeit` wurde an beiden Stellen ignoriert (das
Frappe-Original tut dasselbe, siehe `frappe_compat/mitglied_sichtbarkeit.py`).

Die Tests decken die Abnahme der Karte ab:
  1. B schaltet alles ab -> A sieht in Liste und Detail nichts davon.
  2. B gibt genau `email` frei -> A sieht genau `email`.
  3. B sieht seine eigenen Daten vollstaendig.
  4. Admin sieht alles.
  5. A sieht `notiz` und Einwilligungen von B nicht.
  6. Suche/Filter vertrennt versteckte Felder nicht (Seitenkanal).
  7. `get_adressbuch` verhaelt sich unveraendert (es kannte die Regel schon).

Ohne den Fix sind 1, 2, 5 und 6 rot: die Felder kommen dann vollstaendig
durch, `notiz`/`datenschutz_einwilligung` stehen in der Detail-Antwort, und
`suche` nach einer versteckten E-Mail liefert die Zeile.
"""

from __future__ import annotations

import json

import pytest

from tests.test_permissions import hierarchie  # noqa: F401 — Fixture


# Beide Nutzer liegen in G-A1/DB-A und sehen einander ueber `ancestor_path`
# (`mitglied_permissions` -> `_paths_overlap`). `M-gruppe-a1` IST das eigene
# Mitglied von mitglied-a, `M-verantw-a` ist ein sichtbares fremdes Mitglied.
SICHTBAR = "M-verantw-a"


@pytest.fixture()
def sess(patched_db):
    """Session der Test-DB — die `hierarchie`-Fixture legt ihre Zeilen hier ab."""
    s = patched_db()
    yield s
    s.close()


def _set_user(user: str) -> None:
    from diakronos_app.frappe_compat.session import set_user

    set_user(user)


def _sichtbarkeit_setzen(sess, mitglied: str, **schalter) -> None:
    """Schreibt den Sichtbarkeits-Blob direkt — der Umweg ueber die API
    braucht eine eigene Sitzung und wuerde den Test von derDB entkoppeln."""
    blob = {
        "email": schalter.get("email", True),
        "telefonnummer": schalter.get("telefonnummer", True),
        "adresse": schalter.get("adresse", False),
        "geburtstag": schalter.get("geburtstag", False),
    }
    m = sess.get(_mitglied_model(), mitglied)
    m.adressbuch_sichtbarkeit = json.dumps(blob)
    sess.commit()


def _mitglied_model():
    from diakronos_app.models.diakonos import Mitglied

    return Mitglied


def _pfd_daten(sess) -> None:
    """Füllt die PII-Felder des sichtbaren fremden Mitglieds."""
    m = sess.get(_mitglied_model(), SICHTBAR)
    m.telefonnummer = "0170-2220002"
    m.geburtstag = _datum("1985-05-05")
    m.postleitzahl = "73728"
    m.wohnort = "Esslingen"
    # `straße` ist im Modell ein regulaerer Attributname (Python erlaubt
    # Umlaute in Bezeichnern). `__dict__[...]` waere still ein Fehler: der
    # Wert landet dann in keinem Mapper und wird nie geschrieben.
    m.straße = "Nebenweg"
    m.nummer = "2"
    m.notiz = "VERTRAULICHE-NOTIZ"
    m.datenschutz_einwilligung = True
    m.foto_einwilligung = True
    sess.commit()


def _datum(iso: str):
    from datetime import date

    return date.fromisoformat(iso)


def _liste(client, **params):
    r = client.get("/api/method/mitglieder.get_mitglieder_liste", params=params or {"limit": 50})
    assert r.status_code == 200, r.text
    return r.json()["message"]["data"]


def _zeile(client, name: str, **params) -> dict:
    for z in _liste(client, limit=50, **params):
        if z.get("name") == name:
            return z
    raise AssertionError(f"Zeile {name!r} nicht in der Liste")


def _detail(client, mitglied_id: str) -> dict:
    r = client.get(
        "/api/method/mitglieder.get_mitglied_detail",
        params={"mitglied_id": mitglied_id},
    )
    assert r.status_code == 200, r.text
    return r.json()["message"]["data"]


# ════════════════════════════════════════════════════════════════════════════
# 1) Alles abgeschaltet -> nichts sichtbar (Liste UND Detail)
# ════════════════════════════════════════════════════════════════════════════


def test_liste_ohne_freigabe_zeigt_keine_pii(client, hierarchie, sess):  # noqa: F811
    """Alle vier Schalter auf false: die Zeile bleibt, die Felder sind `None`."""
    _pfd_daten(sess)
    _sichtbarkeit_setzen(
        sess, SICHTBAR, email=False, telefonnummer=False, adresse=False, geburtstag=False
    )
    _set_user("mitglied-a@example.org")

    z = _zeile(client, SICHTBAR)
    assert z["email"] is None, "E-Mail ist nicht freigegeben, kommt aber an"
    assert z["telefonnummer"] is None
    assert z["geburtstag"] is None
    assert z["postleitzahl"] is None
    assert z["wohnort"] is None
    assert z.get("straße") is None, "die Strasse gehoert zur Adresse"
    assert z.get("nummer") is None, "die Hausnummer gehoert zur Adresse"


def test_detail_ohne_freigabe_zeigt_keine_pii(client, hierarchie, sess):  # noqa: F811
    """Dieselbe Lage im Detail-Endpunkt — das Original ignorierte es dort."""
    _pfd_daten(sess)
    _sichtbarkeit_setzen(
        sess, SICHTBAR, email=False, telefonnummer=False, adresse=False, geburtstag=False
    )
    _set_user("mitglied-a@example.org")

    d = _detail(client, SICHTBAR)
    for feld in ("email", "telefonnummer", "geburtstag", "postleitzahl",
                 "wohnort", "straße", "nummer"):
        assert d.get(feld) is None, f"{feld} ist nicht freigegeben, kommt aber an"


def test_antwortstruktur_bleibt_erhalten(client, hierarchie, sess):  # noqa: F811
    """`None` statt Feld entfernen — die SPA darf nicht an fehlenden Keys
    scheitern (`Mitglieder.vue:114` ist `m.email || '–'`)."""
    _sichtbarkeit_setzen(
        sess, SICHTBAR, email=False, telefonnummer=False, adresse=False, geburtstag=False
    )
    _set_user("mitglied-a@example.org")

    z = _zeile(client, SICHTBAR)
    for feld in ("email", "telefonnummer", "geburtstag", "postleitzahl", "wohnort"):
        assert feld in z, f"Feld {feld!r} fehlt in der Zeile (Struktur gebrochen)"

    d = _detail(client, SICHTBAR)
    for feld in ("email", "telefonnummer", "geburtstag", "postleitzahl", "wohnort"):
        assert feld in d, f"Feld {feld!r} fehlt im Detail (Struktur gebrochen)"
    # `dsgvo` bleibt ein Dict — `MitgliedDetail.vue:389` haengt daran.
    assert isinstance(d.get("dsgvo"), dict)


# ════════════════════════════════════════════════════════════════════════════
# 2) Genau eine Freigabe -> genau ein Feld
# ════════════════════════════════════════════════════════════════════════════


def test_nur_email_freigegeben(client, hierarchie, sess):  # noqa: F811
    """Der Schalter wirkt einzeln, nicht als Pauschal-Freigabe."""
    _pfd_daten(sess)
    _sichtbarkeit_setzen(
        sess, SICHTBAR, email=True, telefonnummer=False, adresse=False, geburtstag=False
    )
    _set_user("mitglied-a@example.org")

    z = _zeile(client, SICHTBAR)
    assert z["email"] == "verantw-a@example.org", "freigegebenes Feld fehlt"
    assert z["telefonnummer"] is None
    assert z["geburtstag"] is None
    assert z["wohnort"] is None

    d = _detail(client, SICHTBAR)
    assert d["email"] == "verantw-a@example.org"
    assert d["telefonnummer"] is None
    assert d["wohnort"] is None


def test_nur_adresse_freigegeben(client, hierarchie, sess):  # noqa: F811
    """`adresse` ist ein Sammelschalter: er schaltet ALLE Adressfelder."""
    _pfd_daten(sess)
    _sichtbarkeit_setzen(
        sess, SICHTBAR, email=False, telefonnummer=False, adresse=True, geburtstag=False
    )
    _set_user("mitglied-a@example.org")

    z = _zeile(client, SICHTBAR)
    assert z["postleitzahl"] == "73728"
    assert z["wohnort"] == "Esslingen"
    assert z.get("straße") == "Nebenweg"
    assert z.get("nummer") == "2"
    assert z["email"] is None, "E-Mail ist nicht Teil des Adress-Schalters"


# ════════════════════════════════════════════════════════════════════════════
# 3) Eigene Daten vollstaendig
# ════════════════════════════════════════════════════════════════════════════


def test_own_daten_vollstaendig_im_detail(client, hierarchie, sess):  # noqa: F811
    """Wer seinen eigenen Schalter auf false stellt, sieht seine Daten trotzdem.

    Sonst waere die Profilseite nach dem Speichern leer — und die
    Einstellung waere nicht mehr umkehrbar.
    """
    eigenes = "M-gruppe-a1"
    m = sess.get(_mitglied_model(), eigenes)
    m.telefonnummer = "0170-1111111"
    m.notiz = "EIGENE-NOTIZ"
    m.adressbuch_sichtbarkeit = json.dumps(
        {"email": False, "telefonnummer": False, "adresse": False, "geburtstag": False}
    )
    sess.commit()

    _set_user("mitglied-a@example.org")
    d = _detail(client, eigenes)
    assert d["telefonnummer"] == "0170-1111111", "eigene Daten muessen vollstaendig sein"
    assert d["email"] == "mitglied-a@example.org"
    assert d.get("notiz") == "EIGENE-NOTIZ", "die eigene Notiz ist keine fremde"


def test_own_daten_vollstaendig_in_der_liste(client, hierarchie, sess):  # noqa: F811
    eigenes = "M-gruppe-a1"
    m = sess.get(_mitglied_model(), eigenes)
    m.telefonnummer = "0170-1111111"
    m.adressbuch_sichtbarkeit = json.dumps(
        {"email": False, "telefonnummer": False, "adresse": False, "geburtstag": False}
    )
    sess.commit()

    _set_user("mitglied-a@example.org")
    z = _zeile(client, eigenes)
    assert z["telefonnummer"] == "0170-1111111", "die eigene Zeile wird sonst maskiert"


# ════════════════════════════════════════════════════════════════════════════
# 4) Admin sieht alles
# ════════════════════════════════════════════════════════════════════════════


def test_admin_sieht_alles_auch_bei_vollstaendiger_abschaltung(client, hierarchie, sess):  # noqa: F811
    """Ein Admin muss Einwilligungen widerrufen koennen — dafuer braucht er
    den Beleg, auch wenn das Mitglied alles abgeschaltet hat."""
    _pfd_daten(sess)
    _sichtbarkeit_setzen(
        sess, SICHTBAR, email=False, telefonnummer=False, adresse=False, geburtstag=False
    )
    _set_user("mitglied-a@example.org")

    # `mitglied-a` bekommt temporaer die Adminrolle; das ist der Rollenweg,
    # den `_has_admin_role` auch im Betrieb nimmt.
    from diakronos_app.models.core import HasRole

    sess.add(HasRole(
        name="HR-b2-admin", parent="mitglied-a@example.org", parenttype="User",
        parentfield="roles", role="System Manager", docstatus=0, idx=0,
    ))
    sess.commit()

    # W7: Persönliche Werte liefert die Liste nur auf ausdrückliche Anforderung
    # (`persoenliche_daten=1`) — die Fähigkeit des Admins bleibt, sie wird nur
    # bewusst abgerufen (Knopf »Persönliche Daten anzeigen«).
    z = _zeile(client, SICHTBAR, persoenliche_daten=1)
    assert z["telefonnummer"] == "0170-2220002"
    assert z["wohnort"] == "Esslingen"

    d = _detail(client, SICHTBAR)
    assert d["telefonnummer"] == "0170-2220002"
    assert d.get("notiz") == "VERTRAULICHE-NOTIZ"
    assert d["dsgvo"]["datenschutz"] is True


# ════════════════════════════════════════════════════════════════════════════
# 5) `notiz` und Einwilligungen nur fuer Berechtigte
# ════════════════════════════════════════════════════════════════════════════


def test_notiz_und_einwilligungen_fuer_fremde_weg(client, hierarchie, sess):  # noqa: F811
    """Verwaltungsdaten sind keine Adressbuch-Daten: `can_view_sensitive`
    ist in `frappe_compat/permissions.py` ausdruecklich "Admin-only".

    Weglassen statt `False`: `False` waere die erfundene Aussage "hat nicht
    eingewilligt" — ein Fehler, der in einer DSGVO-Auskunft teuer wird.
    """
    _pfd_daten(sess)
    _sichtbarkeit_setzen(sess, SICHTBAR, email=True, telefonnummer=True,
                          adresse=True, geburtstag=True)
    _set_user("mitglied-a@example.org")

    d = _detail(client, SICHTBAR)
    # Alles freigegeben -> die PII ist da, die Verwaltungsdaten trotzdem nicht.
    assert d["email"] == "verantw-a@example.org"
    assert d["telefonnummer"] == "0170-2220002"
    assert "notiz" not in d, "die Notiz ist fuer Fremde nicht freigegeben"
    for feld in ("datenschutz_einwilligung", "foto_einwilligung",
                 "werbeeinwilligung", "datenschutz_datum", "foto_datum",
                 "werbung_datum"):
        assert feld not in d, f"{feld} gehoert nicht an einen normalen Leser"


def test_dsgvo_block_ist_fuer_fremde_neutral(client, hierarchie, sess):  # noqa: F811
    """Der `dsgvo`-Block traegt dieselben Daten wie die Einzelfelder.

    Ohne diese Massnahme waere die Maskierung oben halb wirksam: dieselben
    Einwilligungen kaemen ueber den zweiten Weg doch heraus. Die Struktur
    bleibt, damit `MitgliedDetail.vue:389` (`if (payload.dsgvo)`) nicht
    crasht.
    """
    _pfd_daten(sess)  # setzt datenschutz_einwilligung = True
    _sichtbarkeit_setzen(sess, SICHTBAR, email=True, telefonnummer=True,
                          adresse=True, geburtstag=True)
    _set_user("mitglied-a@example.org")

    d = _detail(client, SICHTBAR)
    block = d["dsgvo"]
    assert block["datenschutz"] is None, "die Einwilligung ist fuer Fremde nicht sichtbar"
    assert block["foto"] is None
    assert block["datenschutz_datum"] is None


def test_adressbuch_sichtbarkeit_wird_nicht_ausgeliefert(client, hierarchie, sess):  # noqa: F811
    """Der Blob selbst geht nicht nach aussen — er verrate, welche Felder
    der Nutzer ueberhaupt freigegeben hat, und war nie Teil der Antwort."""
    _sichtbarkeit_setzen(sess, SICHTBAR, email=True)
    _set_user("mitglied-a@example.org")

    assert "adressbuch_sichtbarkeit" not in _detail(client, SICHTBAR)
    assert "adressbuch_sichtbarkeit" not in _zeile(client, SICHTBAR)


# ════════════════════════════════════════════════════════════════════════════
# 6) Seitenkanal: Suche/Filter vertrennt versteckte Felder nicht
# ════════════════════════════════════════════════════════════════════════════


def test_suche_nach_versteckter_email_trennt_nicht(client, hierarchie, sess):  # noqa: F811
    """Wer B nach Bs E-Mail sucht, darf nicht daran erkennen, ob B sie
    freigegeben hat. Das Original sucht in `email` (mitglieder.py:92-96),
    ohne die Sichtbarkeit zu kennen — das waere genau der Seitenkanal, den
    die Karte verbietet."""
    _sichtbarkeit_setzen(sess, SICHTBAR, email=False, telefonnummer=False,
                          adresse=False, geburtstag=False)
    _set_user("mitglied-a@example.org")

    ohne = _liste(client, limit=50, suche="verantw-a@example.org")
    assert all(z.get("name") != SICHTBAR for z in ohne), (
        "die Suche nach einer nicht freigegebenen E-Mail liefert die Zeile — "
        "damit ist die Maskierung umgehbar"
    )

    # Gegenprobe: die Suche nach dem **Namen** findet dieselbe Zeile weiterhin
    # (Namen sind kein Adressbuch-Feld). Sonst waere der Nutzer eingeschraenkt
    # und die Zeile gar nicht mehr auffindbar.
    mit_name = _liste(client, limit=50, suche="verantw-a@example.org".replace(
        "verantw-a@example.org", "Vera"))
    assert any(z.get("name") == SICHTBAR for z in mit_name), (
        "die Namenssuche muss weiterhin greifen"
    )


def test_suche_nach_verstecktem_telefon_trennt_nicht(client, hierarchie, sess):  # noqa: F811
    """Gleiche Lage fuer das Telefonfeld: es wird nirgends durchsucht, und die
    Antwort darf es auch nicht preisgeben (der Fall steckt in Test 1)."""
    _pfd_daten(sess)
    _sichtbarkeit_setzen(sess, SICHTBAR, email=True, telefonnummer=False,
                          adresse=False, geburtstag=False)
    _set_user("mitglied-a@example.org")

    z = _zeile(client, SICHTBAR)
    assert "0170-2220002" not in json.dumps(z), "die Nummer taucht irgendwo auf"


def test_admin_darf_weiterhin_volltextsuchen(client, hierarchie, sess):  # noqa: F811
    """Gegenprobe, damit die Abschraenkung nicht ueberzogen ist: fuer einen
    Admin bleibt die Suche unveraendert (inkl. E-Mail)."""
    from diakronos_app.models.core import HasRole

    sess.add(HasRole(
        name="HR-b2-admin-2", parent="mitglied-a@example.org", parenttype="User",
        parentfield="roles", role="System Manager", docstatus=0, idx=0,
    ))
    _sichtbarkeit_setzen(sess, SICHTBAR, email=False)
    sess.commit()

    _set_user("mitglied-a@example.org")
    treffer = _liste(client, limit=50, suche="verantw-a@example.org")
    assert any(z.get("name") == SICHTBAR for z in treffer), (
        "der Admin muss unveraendert auch nach E-Mail suchen koennen"
    )


# ════════════════════════════════════════════════════════════════════════════
# 7) `get_adressbuch` — kannte die Regel schon, verhaelt sich unveraendert
# ════════════════════════════════════════════════════════════════════════════


def test_adressbuch_unveraendert(client, hierarchie, sess):  # noqa: F811
    """Der Adressbuch-Pfad war die einzige Stelle mit korrekter Regelung.
    Die Karte verlangt, ihn zu pruefen, nicht ihn umzubauen — dieser Test
    nagelt das fest, damit die Umstellung auf den gemeinsamen Helfer nichts
    verschiebt."""
    _pfd_daten(sess)
    _sichtbarkeit_setzen(sess, SICHTBAR, email=False, telefonnummer=False,
                          adresse=False, geburtstag=False)
    _set_user("mitglied-a@example.org")

    r = client.get("/api/method/mitglieder.get_adressbuch")
    assert r.status_code == 200, r.text
    zeilen = r.json()["message"]["data"]
    b = next(z for z in zeilen if z["name"] == SICHTBAR)

    assert b["email"] is None
    assert b["telefonnummer"] is None
    assert b["wohnort"] is None
    assert b["postleitzahl"] is None
    assert b["geburtstag"] is None
    # Der Altcode liefert `vorname`/`nachname` leer-sicher und ohne `straße`.
    assert b["vorname"] == "Vera"
    assert "straße" not in b, "der Altcode gab die Strasse nie aus"


def test_adressbuch_mit_vollstaendiger_freigabe(client, hierarchie, sess):  # noqa: F811
    _pfd_daten(sess)
    _sichtbarkeit_setzen(sess, SICHTBAR, email=True, telefonnummer=True,
                          adresse=True, geburtstag=True)
    _set_user("mitglied-a@example.org")

    r = client.get("/api/method/mitglieder.get_adressbuch")
    b = next(z for z in r.json()["message"]["data"] if z["name"] == SICHTBAR)
    assert b["email"] == "verantw-a@example.org"
    assert b["telefonnummer"] == "0170-2220002"
    assert b["wohnort"] == "Esslingen"
    assert b["geburtstag"] == "1985-05-05", "der Altcast str() bleibt erhalten"


# ════════════════════════════════════════════════════════════════════════════
# 8) Die zentrale Regel selbst (Fail-closed auf kaputte Werte)
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("raw", [None, "kein json", "{}", "[]", "null", "true"])
def test_sichtbarkeit_lesen_fail_closed(raw):
    from diakronos_app.frappe_compat.mitglied_sichtbarkeit import sichtbarkeit_lesen

    assert sichtbarkeit_lesen(raw) == {
        "email": False, "telefonnummer": False, "adresse": False, "geburtstag": False,
    }


@pytest.mark.parametrize("wert", ["false", "true", 0, 1, [], {}, None])
def test_nur_bool_true_ist_eine_freigabe(wert):
    from diakronos_app.frappe_compat.mitglied_sichtbarkeit import sichtbarkeit_lesen

    assert sichtbarkeit_lesen({"email": wert})["email"] is False


def test_sichtbarkeit_liest_teilweise_angaben_als_default():
    """Wer nur `email` speichert, meint das nicht als "Adresse auch frei"."""
    from diakronos_app.frappe_compat.mitglied_sichtbarkeit import sichtbarkeit_lesen

    s = sichtbarkeit_lesen('{"email": false}')
    assert s["email"] is False
    assert s["telefonnummer"] is False, "unbestimmt -> fail closed"
    assert s["adresse"] is False


def test_maskiere_datensatz_aendert_die_quelle_nicht():
    """Die Maskierung liefert ein neues Dict — `doc.as_dict()` darf nicht
    still veraendert werden, der Aufrufer koennte es weiterverwenden."""
    from diakronos_app.frappe_compat.mitglied_sichtbarkeit import maskiere_datensatz

    quelle = {
        "name": "M-x", "email": "a@b.de", "telefonnummer": "0170", "notiz": "geheim",
        "adressbuch_sichtbarkeit": json.dumps(
            {"email": False, "telefonnummer": False, "adresse": False, "geburtstag": False}
        ),
    }
    ergebnis = maskiere_datensatz(quelle, mitglied_id="M-x", vollstaendig=False) or {}

    assert ergebnis["email"] is None
    assert "notiz" not in ergebnis
    assert quelle["email"] == "a@b.de", "die Quelle wurde veraendert"
    assert quelle["notiz"] == "geheim", "die Quelle wurde veraendert"


# ════════════════════════════════════════════════════════════════════════════
# 9) Der Gruppenweg (Befund aus der Abnahme-Runde: `email` ungeprueft)
# ════════════════════════════════════════════════════════════════════════════
#
# Beim Nachpruefen aller Auslieferungswege nach dem Auftrag der Karte
# ("pruefe per Grep alle Stellen, die Mitgliedsfelder ausliefern") kam ein
# zweiter Weg heraus, den die erste Fassung dieser Karte nicht angefasst hatte:
# `api/gruppen.py::_mitglieder_der_gruppe` las `email` ungeprueft, obwohl das
# ein Adressbuch-Feld ist. Dasselbe galt fuer die Verantwortlichen-Liste in
# `get_gruppe_detail`. Das Frappe-Original hat denselben Mangel.


def _mitglied_in_gruppe(sess, mitglied: str, gruppe: str) -> None:
    """Hängt ein Mitglied als Kindzeile an eine Gruppe (Child-Tabelle)."""
    from diakronos_app.models.diakonos import Gruppenmitgliedschaft

    sess.add(Gruppenmitgliedschaft(
        name=f"GM-b2-{mitglied}", parent=gruppe, parenttype="Gruppe",
        parentfield="mitglieder", mitglied=mitglied, status="Aktiv",
        docstatus=0, idx=1,
    ))
    sess.commit()


def test_gruppenliste_verbirgt_nicht_freigegebene_email(hierarchie, sess):  # noqa: F811
    """Ohne den Fix kommt die E-Mail hier an, obwohl das Mitglied sie
    abgeschaltet hat — der Test waere also genau dann rot."""
    from diakronos_app.api.gruppen import _mitglieder_der_gruppe

    _sichtbarkeit_setzen(sess, SICHTBAR, email=False)
    _mitglied_in_gruppe(sess, SICHTBAR, "G-A1")
    _set_user("mitglied-a@example.org")

    zeilen = _mitglieder_der_gruppe("Gruppe", "G-A1")
    ziel = next(z for z in zeilen if z["mitglied"] == SICHTBAR)
    assert ziel["email"] is None, (
        "die Gruppenliste liefert eine nicht freigegebene E-Mail"
    )
    # Der Name bleibt — die Sichtbarkeit kennt kein Namensfeld.
    assert ziel["name"], "der Name muss stehen bleiben"


def test_gruppenliste_zeigt_freigegebene_email(hierarchie, sess):  # noqa: F811
    """Gegenprobe: wer die E-Mail freigibt, sieht sie auch in der Liste."""
    from diakronos_app.api.gruppen import _mitglieder_der_gruppe

    _sichtbarkeit_setzen(sess, SICHTBAR, email=True)
    _mitglied_in_gruppe(sess, SICHTBAR, "G-A1")
    _set_user("mitglied-a@example.org")

    zeilen = _mitglieder_der_gruppe("Gruppe", "G-A1")
    ziel = next(z for z in zeilen if z["mitglied"] == SICHTBAR)
    assert ziel["email"] == "verantw-a@example.org"


def test_gruppenliste_zeigt_die_eigene_email_immer(hierarchie, sess):  # noqa: F811
    """Das eigene Mitglied sieht seine E-Mail in der Gruppenliste, auch wenn
    der Schalter steht — sonst waere die eigene Profilseite blind."""
    from diakronos_app.api.gruppen import _mitglieder_der_gruppe

    eigenes = "M-gruppe-a1"
    _sichtbarkeit_setzen(sess, eigenes, email=False)
    _mitglied_in_gruppe(sess, eigenes, "G-A1")
    _set_user("mitglied-a@example.org")

    zeilen = _mitglieder_der_gruppe("Gruppe", "G-A1")
    ziel = next(z for z in zeilen if z["mitglied"] == eigenes)
    assert ziel["email"], "das eigene Mitglied muss seine E-Mail sehen"


def test_gruppenliste_zeigt_fuer_admin_alles(hierarchie, sess):  # noqa: F811
    """Admin sieht auch in der Gruppenliste alles (`can_view_sensitive`)."""
    from diakronos_app.api.gruppen import _mitglieder_der_gruppe
    from diakronos_app.models.core import HasRole

    sess.add(HasRole(
        name="HR-b2-grp", parent="mitglied-a@example.org", parenttype="User",
        parentfield="roles", role="System Manager", docstatus=0, idx=0,
    ))
    _sichtbarkeit_setzen(sess, SICHTBAR, email=False)
    _mitglied_in_gruppe(sess, SICHTBAR, "G-A1")
    sess.commit()
    _set_user("mitglied-a@example.org")

    zeilen = _mitglieder_der_gruppe("Gruppe", "G-A1")
    ziel = next(z for z in zeilen if z["mitglied"] == SICHTBAR)
    assert ziel["email"] == "verantw-a@example.org", "der Admin sieht alles"


def _verantwortlichen_zeile(sess, user: str) -> str:
    """Hängt `user` als Verantwortlichen an G-A1.

    Der Code loest den Verantwortlichen ueber `get_value("Mitglied",
    {"user": ...})` auf. In der Test-Fixture hat **kein** Mitglied ein
    `user`-Feld (siehe Kommentarzeilen 39/128 dort: `gruppenverantw` ist
    bewusst "OHNE Mitglied-Datensatz"). Deshalb wird hier ein eigenes
    Mitglied angelegt, das genau diesen `user` traegt — sonst wuerde der Weg
    gar nicht erst erreicht und der Test waeite gruen, ohne etwas zu pruefen.
    """
    from diakronos_app.models.diakonos import (
        GruppeVerantwortlicher,
        Mitglied,
    )

    mitglied_id = f"M-b2-vrw-{user.split('@')[0]}"
    sess.add(Mitglied(
        name=mitglied_id, vorname="Vera", nachname="Verantwortlich",
        email=f"{user}", status="Mitglied", user=user,
        ancestor_path="/G-A1/|/DB-A/", docstatus=0, idx=0,
    ))
    sess.add(GruppeVerantwortlicher(
        name=f"GRV-b2-{user.split('@')[0]}", parent="G-A1", parenttype="Gruppe",
        parentfield="verantwortliche", user=user, docstatus=0, idx=2,
    ))
    sess.commit()
    return mitglied_id


def test_verantwortliche_verbirgt_nicht_freigegebene_email(hierarchie, sess):  # noqa: F811
    """Derselbe Weg fuer die Verantwortlichen-Liste in `get_gruppe_detail`.

    Der Verantwortliche ist ein anderes Mitglied als der Aufrufer und hat
    seine E-Mail abgeschaltet — die Liste darf sie trotzdem nicht liefern.
    Ohne den Fix kommt `email` hier an.
    """
    from diakronos_app.api.gruppen import get_gruppe_detail

    user = "b2-vrw@example.org"
    mitglied_id = _verantwortlichen_zeile(sess, user)
    _sichtbarkeit_setzen(sess, mitglied_id, email=False)
    _set_user("mitglied-a@example.org")

    res = get_gruppe_detail("G-A1")
    treffer = [v for v in res["verantwortliche"] if v["name"] == "Vera Verantwortlich"]
    assert treffer, "der Verantwortliche fehlt in der Liste"
    assert treffer[0]["verantwortlicher"] is None
    assert treffer[0]["email"] is None, (
        "die Verantwortlichen-Liste liefert eine nicht freigegebene E-Mail"
    )


def test_verantwortliche_zeigt_fuer_admin_alles(hierarchie, sess):  # noqa: F811
    """Gegenprobe fuer denselben Weg: der Admin sieht die E-Mail."""
    from diakronos_app.api.gruppen import get_gruppe_detail
    from diakronos_app.models.core import HasRole

    user = "b2-vrw@example.org"
    mitglied_id = _verantwortlichen_zeile(sess, user)
    _sichtbarkeit_setzen(sess, mitglied_id, email=False)
    sess.add(HasRole(
        name="HR-b2-vrw", parent="mitglied-a@example.org", parenttype="User",
        parentfield="roles", role="System Manager", docstatus=0, idx=0,
    ))
    sess.commit()
    _set_user("mitglied-a@example.org")

    res = get_gruppe_detail("G-A1")
    treffer = [v for v in res["verantwortliche"] if v["verantwortlicher"] == user]
    assert treffer
    assert treffer[0]["email"], "der Admin sieht die E-Mail auch hier"


def test_verantwortliche_ohne_freigabe_bei_fremdem(hierarchie, sess):  # noqa: F811
    """Ein fremdes Mitglied ohne Freigabe verliert seine E-Mail in der Liste.

    `M-gruppe-b1` steht in der Fixture als fremdes Mitglied, das mitglied-a
    ueber die Gruppenverknuepfung sieht. Damit ist der Weg
    "Mitgliederliste einer Gruppe, die A lesen darf" abgedeckt.
    """
    from diakronos_app.api.gruppen import _mitglieder_der_gruppe

    fremd = "M-gruppe-b1"
    _sichtbarkeit_setzen(sess, fremd, email=False)
    _mitglied_in_gruppe(sess, fremd, "G-A1")
    _set_user("mitglied-a@example.org")

    zeilen = _mitglieder_der_gruppe("Gruppe", "G-A1")
    treffer = [z for z in zeilen if z["mitglied"] == fremd]
    assert treffer, "das fremde Mitglied steht nicht in der Gruppenliste"
    assert treffer[0]["email"] is None, (
        "fremdes Mitglied ohne Freigabe: die Gruppenliste darf die E-Mail "
        "nicht liefern"
    )
