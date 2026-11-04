"""UX1j — „Gestaltung“-Einstellungen: Rechte, Grenzen, Skala, CSS-Ausgabe.

Die Karte verlangt (J1–J3):

  * Tabelle `gestaltung_abweichung` + Migration (ein Head).
  * Erlaubte Tokens = feste Positivliste mit Bereich; NICHT einstellbar:
    Klickflächen, Farben, Schriften. Skala muss aufsteigend bleiben.
  * `gestaltung.lesen` (Admin), `gestaltung.speichern` POST,
    `gestaltung.zuruecksetzen` POST — nur System Manager, Audit, Inventar.
  * Öffentliche Route `{Präfix}/gestaltung.css`: NUR `:root{--token: wert;}`
    der Abweichungen (leer = leere Datei), Cache mit ETag/`?v=hash`, vor der
    Anmeldeschranke. `seitenrahmen.head_block()` und die SPA laden sie NACH
    tokens.css.

Was hier NICHT geprüft wird: die Oberfläche (das ist UX1k).
"""

from __future__ import annotations

import re

import pytest

from diakronos_app.gestaltung import speicher
from diakronos_app.gestaltung import tokens as T
from diakronos_app.models.gestaltung import GestaltungAbweichung

API = "diakronos.diakonos.api.gestaltung."
KURZ = "gestaltung."


@pytest.fixture()
def rollen(patched_db):
    """Konten + Rollen anlegen (Muster aus test_bk1_rechte.py)."""
    from diakronos_app.models.core import HasRole, User

    sess = patched_db()
    for name, rolle in (
        ("admin@example.org", None),
        ("mitgliederadmin@example.org", "Mitgliederadministrator"),
        ("chefin@example.org", "System Manager"),
    ):
        if sess.get(User, name) is None:
            sess.add(User(name=name, email=name, full_name=name, enabled=True))
        if rolle and sess.get(HasRole, f"hr-{name}") is None:
            sess.add(HasRole(name=f"hr-{name}", parent=name, parenttype="User",
                             parentfield="roles", role=rolle, docstatus=0, idx=1))
    sess.commit()
    sess.close()

    def _setze(name: str):
        from diakronos_app import frappe_compat

        frappe_compat.set_user(name)

    return _setze


def _lesen(client, prefix=API):
    return client.post(f"/api/method/{prefix}gestaltung_lesen", json={})


def _speichern(client, werte, prefix=API):
    return client.post(f"/api/method/{prefix}gestaltung_speichern", json={"werte": werte})


def _zurueck(client, token=None, prefix=API):
    return client.post(f"/api/method/{prefix}gestaltung_zuruecksetzen",
                       json={} if token is None else {"token": token})


# ── J1 · Positivliste ─────────────────────────────────────────────────────

def test_positivliste_nennt_die_karten_tokens():
    """Die Liste ist die der Karte — keine Farben, Schriften, Klickflächen."""
    erwartet = {
        "--sp-1", "--sp-2", "--sp-3", "--sp-4", "--sp-5", "--sp-6", "--sp-7", "--sp-8",
        "--pad", "--abstand-gruppe", "--abstand-innen", "--karte-innen",
        "--karte-rahmen", "--rahmen-breite", "--radius-sm", "--radius", "--radius-lg",
    }
    assert set(T.TOKEN_NAMEN) == erwartet


@pytest.mark.parametrize("verboten", [
    "--control-h", "--row-h", "--topbar-h",  # Klickflächen
    "--primary", "--bg", "--surface", "--text", "--err",  # Farben
    "--dk-navy-500", "--dk-gold-500",  # Rohfarben
    "--font-size", "--font-weight", "--schrift-groesse",  # Schriften
    "--radius-x", "--gap", "--grid-gap",  # nicht in der Liste
])
def test_verbotene_tokens_sind_nicht_einstellbar(verboten):
    assert T.token_oder_none(verboten) is None
    with pytest.raises(ValueError):
        T.pruefe_wert(verboten, 16)


def test_jedes_token_hat_einen_sinnvollen_bereich():
    for token in T.TOKENS:
        assert 0 <= token.minimum <= token.standard <= token.maximum, token.name
        assert token.einheit == "px"
        assert token.gruppe


def test_skala_token_sind_vollstaendig_und_aufsteigend():
    assert set(T.SKALA_TOKEN) == {f"--sp-{i}" for i in range(1, 9)}
    standard = {t.name: t.standard for t in T.TOKENS}
    werte = [standard[n] for n in T.SKALA_TOKEN]
    assert werte == sorted(werte) and len(set(werte)) == len(werte)


# ── J1 · Werteprüfung ─────────────────────────────────────────────────────

@pytest.mark.parametrize("wert,erwartet", [
    (8, 8), ("8", 8), ("8px", 8), (8.0, 8), (" 12 ", 12),
])
def test_zahlen_werden_angenommen(wert, erwartet):
    assert T.zahl_aus(wert) == erwartet
    assert T.pruefe_wert("--sp-2", wert) == erwartet


@pytest.mark.parametrize("wert", [
    "calc(100% - 8px)", "var(--sp-1)", "8em", "8.5", -8, "0x10",
    "8px; } body { display:none", "url(x)", "", None, True, "abc",
])
def test_ungueltige_werte_werden_abgelehnt(wert):
    with pytest.raises(ValueError):
        T.pruefe_wert("--sp-2", wert)


@pytest.mark.parametrize("name,wert", [
    ("--sp-6", 1),      # unter min
    ("--sp-6", 9999),   # über max
    ("--radius-sm", 999),
])
def test_bereich_wird_eingehalten(name, wert):
    with pytest.raises(ValueError):
        T.pruefe_wert(name, wert)


def test_skala_pruefung_meldet_die_gebrochene_stelle():
    with pytest.raises(ValueError) as fehler:
        T.pruefe_skala({"--sp-2": 40})  # 40 > --sp-3 (12)
    assert "--sp-2" in str(fehler.value)
    assert "aufsteigend" in str(fehler.value)


def test_skala_pruefung_verlangt_strenge_ordnung():
    with pytest.raises(ValueError):
        T.pruefe_skala({"--sp-2": 12})  # gleich --sp-3 -> keine Ordnung
    T.pruefe_skala({"--sp-2": 11})  # knapp darunter ist in Ordnung


# ── J1 · Speicher ─────────────────────────────────────────────────────────

def test_speichern_und_zuruecksetzen_einzel(patched_db):
    nach = speicher.speichern({"--pad": 24}, benutzer="chefin@example.org")
    assert nach == {"--pad": 24}
    assert speicher.zuruecksetzen("--pad") == {}


def test_speichern_des_standardwerts_loescht_die_abweichung(patched_db):
    speicher.speichern({"--pad": 24}, benutzer="chefin@example.org")
    assert speicher.speichern({"--pad": 16}, benutzer="chefin@example.org") == {}
    sess = patched_db()
    assert list(sess.query(GestaltungAbweichung)) == []
    sess.close()


def test_zuruecksetzen_ohne_token_raeumt_alles(patched_db):
    speicher.speichern({"--pad": 24, "--radius": 12}, benutzer="chefin@example.org")
    assert speicher.zuruecksetzen() == {}


def test_gebrochene_skala_schreibt_nichts(patched_db):
    with pytest.raises(ValueError):
        speicher.speichern({"--sp-2": 40, "--pad": 20}, benutzer="chefin@example.org")
    assert speicher.abweichungen() == {}


def test_speichern_lehnt_unbekanntes_token_ab(patched_db):
    with pytest.raises(ValueError):
        speicher.speichern({"--control-h": 44}, benutzer="chefin@example.org")
    assert speicher.abweichungen() == {}


def test_altzeile_ausserhalb_der_liste_wird_ignoriert(patched_db):
    """Eine Zeile mit fremdem Token/Wert darf nie ins CSS kommen."""
    sess = patched_db()
    sess.add(GestaltungAbweichung(token="--boese", wert=1, geaendert_von="x"))
    sess.add(GestaltungAbweichung(token="--pad", wert=9999, geaendert_von="x"))
    sess.add(GestaltungAbweichung(token="--radius", wert=10, geaendert_von="x"))
    sess.commit()
    sess.close()

    assert speicher.abweichungen() == {"--radius": 10}
    css = speicher.als_css()
    assert "--boese" not in css
    assert "9999" not in css


# ── J3 · CSS-Ausgabe ──────────────────────────────────────────────────────

def test_css_ist_ohne_abweichung_leer(patched_db):
    assert speicher.als_css() == ""


def test_css_enthaelt_nur_root_mit_den_abweichungen(patched_db):
    speicher.speichern({"--pad": 20, "--radius": 10}, benutzer="chefin@example.org")
    css = speicher.als_css()
    assert ":root {" in css
    assert "--pad: 20px;" in css
    assert "--radius: 10px;" in css
    # NUR die Abweichungen — nicht alle Token.
    assert "--sp-1" not in css
    # Kein Selektor ausser :root, keine Eigenschaft ausser den Token.
    rumpf = css[css.index(":root {"):]
    for zeile in rumpf.splitlines()[1:]:
        zeile = zeile.strip()
        if not zeile or zeile == "}":
            continue
        assert re.fullmatch(r"--[a-z0-9-]+: \d+px;", zeile), zeile


def test_css_kann_kein_fremdes_css_enthalten(patched_db):
    """Selbst eine manipulierte Zeile landet nicht im CSS (nur Zahlen + px)."""
    sess = patched_db()
    sess.add(GestaltungAbweichung(
        token="--radius", wert=8, geaendert_von="x; } body { display:none",
    ))
    sess.commit()
    sess.close()
    css = speicher.als_css()
    assert "display:none" not in css
    assert "body" not in css


def test_css_hash_aendert_sich_mit_dem_wert(patched_db):
    leer = speicher.css_hash()
    speicher.speichern({"--pad": 20}, benutzer="chefin@example.org")
    geaendert = speicher.css_hash()
    assert geaendert != leer
    assert geaendert == speicher.css_hash()  # stabil bei gleichem Inhalt


# ── J2 · Endpunkte: Rollen ────────────────────────────────────────────────

def test_system_manager_darf_lesen(client, rollen):
    rollen("chefin@example.org")
    antwort = _lesen(client)
    assert antwort.status_code == 200, antwort.text
    daten = antwort.json()["message"]
    assert daten["abweichungen"] == {}
    assert daten["standard"]["--pad"] == 16
    tokens = {f["token"]: f for f in daten["felder"]}
    assert set(tokens) == set(T.TOKEN_NAMEN)
    assert tokens["--sp-1"]["min"] == 1
    assert tokens["--sp-1"]["einheit"] == "px"
    assert tokens["--sp-1"]["abweichend"] is False


@pytest.mark.parametrize("endpunkt", ["lesen", "speichern", "zuruecksetzen"])
def test_mitgliederadministrator_wird_abgewiesen(client, rollen, endpunkt):
    rollen("mitgliederadmin@example.org")
    if endpunkt == "lesen":
        antwort = _lesen(client)
    elif endpunkt == "speichern":
        antwort = _speichern(client, {"--pad": 20})
    else:
        antwort = _zurueck(client)
    assert antwort.status_code == 403, antwort.text


@pytest.mark.parametrize("endpunkt", ["lesen", "speichern", "zuruecksetzen"])
def test_gast_wird_abgewiesen(guest_client, patched_db, endpunkt):
    if endpunkt == "lesen":
        antwort = _lesen(guest_client)
    elif endpunkt == "speichern":
        antwort = _speichern(guest_client, {"--pad": 20})
    else:
        antwort = _zurueck(guest_client)
    assert antwort.status_code in (401, 403), antwort.text


# ── J2 · Endpunkte: Verhalten ─────────────────────────────────────────────

def test_speichern_und_lesen_ueber_die_api(client, rollen):
    rollen("chefin@example.org")
    antwort = _speichern(client, {"--pad": 24, "--radius": 10})
    assert antwort.status_code == 200, antwort.text
    assert antwort.json()["message"]["abweichungen"] == {"--pad": 24, "--radius": 10}

    gelesen = _lesen(client).json()["message"]
    felder = {f["token"]: f for f in gelesen["felder"]}
    assert felder["--pad"]["wert"] == 24
    assert felder["--pad"]["abweichend"] is True


def test_speichern_prueft_bereich(client, rollen):
    rollen("chefin@example.org")
    antwort = _speichern(client, {"--sp-1": 900})
    assert antwort.status_code == 417, antwort.text
    assert "Bereich" in antwort.text or "außerhalb" in antwort.text
    assert _lesen(client).json()["message"]["abweichungen"] == {}


def test_speichern_prueft_skala(client, rollen):
    rollen("chefin@example.org")
    antwort = _speichern(client, {"--sp-2": 40})
    assert antwort.status_code == 417, antwort.text
    assert "aufsteigend" in antwort.text


def test_speichern_lehnt_unbekanntes_token_ueber_die_api_ab(client, rollen):
    rollen("chefin@example.org")
    antwort = _speichern(client, {"--control-h": 44})
    assert antwort.status_code == 417, antwort.text


def test_speichern_ohne_werte(client, rollen):
    rollen("chefin@example.org")
    antwort = _speichern(client, None)
    assert antwort.status_code == 417, antwort.text


def test_zuruecksetzen_einzeln_und_alles(client, rollen):
    rollen("chefin@example.org")
    _speichern(client, {"--pad": 24, "--radius": 10})
    einzeln = _zurueck(client, "--pad")
    assert einzeln.status_code == 200, einzeln.text
    assert einzeln.json()["message"]["abweichungen"] == {"--radius": 10}

    alles = _zurueck(client)
    assert alles.status_code == 200, alles.text
    assert alles.json()["message"]["abweichungen"] == {}


def test_zuruecksetzen_lehnt_unbekanntes_token_ab(client, rollen):
    rollen("chefin@example.org")
    antwort = _zurueck(client, "--control-h")
    assert antwort.status_code == 417, antwort.text


def test_schreibende_endpunkte_lehnen_get_ab(client, rollen):
    """SEC-11: `methods=["POST"]` ist eine echte Grenze."""
    rollen("chefin@example.org")
    for endpunkt in ("gestaltung_speichern", "gestaltung_zuruecksetzen"):
        antwort = client.get(f"/api/method/{API}{endpunkt}")
        assert antwort.status_code in (405, 303), (endpunkt, antwort.status_code)


def test_kurzpfad_funktioniert_ebenfalls(client, rollen):
    """(J2) Die Karte nennt `gestaltung.<name>` — beide Wege loesen auf."""
    rollen("chefin@example.org")
    antwort = client.post(f"/api/method/{KURZ}lesen", json={})
    assert antwort.status_code == 200, antwort.text


# ── J2 · Audit ────────────────────────────────────────────────────────────

def test_aenderung_landet_im_audit_log(client, rollen, patched_db):
    from diakronos_app.models.diakonos import AuditLog

    rollen("chefin@example.org")
    _speichern(client, {"--pad": 24})

    sess = patched_db()
    eintraege = list(sess.query(AuditLog))
    sess.close()
    assert len(eintraege) == 1
    eintrag = eintraege[0]
    assert eintrag.target_doctype == "Gestaltung"
    assert eintrag.target_name == "--pad"
    assert eintrag.actor == "chefin@example.org"
    assert "24" in (eintrag.begruendung or "")


def test_zuruecksetzen_alles_landet_im_audit_log(client, rollen, patched_db):
    from diakronos_app.models.diakonos import AuditLog

    rollen("chefin@example.org")
    _speichern(client, {"--pad": 24})
    _zurueck(client)
    sess = patched_db()
    ziele = [e.target_name for e in sess.query(AuditLog)]
    sess.close()
    assert "--pad" in ziele
    assert "alle" in ziele


def test_unveraenderte_werte_erzeugen_keinen_audit_eintrag(client, rollen, patched_db):
    from diakronos_app.models.diakonos import AuditLog

    rollen("chefin@example.org")
    _speichern(client, {"--pad": 24})
    _speichern(client, {"--pad": 24})
    sess = patched_db()
    assert sess.query(AuditLog).count() == 1
    sess.close()


# ── J3 · Öffentliche Route ────────────────────────────────────────────────

def test_route_liefert_leere_datei_ohne_abweichung(guest_client, patched_db):
    antwort = guest_client.get("/gestaltung.css")
    assert antwort.status_code == 200, antwort.text
    assert antwort.text == ""
    assert antwort.headers["content-type"].startswith("text/css")
    assert antwort.headers["etag"]
    assert antwort.headers["cache-control"] == "no-cache"


def test_route_ist_ohne_anmeldung_erreichbar(guest_client, patched_db):
    speicher.speichern({"--pad": 20}, benutzer="chefin@example.org")
    antwort = guest_client.get("/gestaltung.css")
    assert antwort.status_code == 200
    assert "--pad: 20px;" in antwort.text


def test_route_liefert_nur_die_abweichungen(guest_client, patched_db):
    speicher.speichern({"--pad": 20}, benutzer="chefin@example.org")
    text = guest_client.get("/gestaltung.css").text
    assert ":root" in text
    assert "--pad: 20px;" in text
    assert "--sp-1" not in text


def test_route_beantwortet_if_none_match_mit_304(guest_client, patched_db):
    speicher.speichern({"--pad": 20}, benutzer="chefin@example.org")
    erste = guest_client.get("/gestaltung.css")
    etag = erste.headers["etag"]
    zweite = guest_client.get("/gestaltung.css", headers={"If-None-Match": etag})
    assert zweite.status_code == 304
    assert zweite.text == ""


def test_route_ist_nicht_schreibbar(guest_client, patched_db):
    antwort = guest_client.post("/gestaltung.css")
    assert antwort.status_code in (405, 403)


def test_head_block_laedt_gestaltung_nach_tokens(patched_db):
    from diakronos_app.anmeldung import seitenrahmen

    block = seitenrahmen.head_block()
    stelle_tokens = block.find("diakronos-tokens.css")
    stelle_gestaltung = block.find("/gestaltung.css")
    stelle_seiten = block.find("diakronos-seiten.css")
    assert -1 < stelle_tokens < stelle_gestaltung < stelle_seiten


def test_head_block_haengt_hash_nur_bei_abweichungen_an(patched_db):
    from diakronos_app.anmeldung import seitenrahmen

    assert "gestaltung.css?v=" not in seitenrahmen.head_block()
    speicher.speichern({"--pad": 20}, benutzer="chefin@example.org")
    block = seitenrahmen.head_block()
    assert f"gestaltung.css?v={speicher.css_hash()}" in block


def test_route_ist_praefixbewusst(patched_db, monkeypatch):
    """WEB-5a: unter `DIAKRONOS_BASE_PATH` steht der Präfix davor."""
    from diakronos_app import base_path
    from diakronos_app.gestaltung import route

    monkeypatch.setattr(base_path, "_AKTIV", "/gemeinde")
    assert route.css_url() == "/gemeinde/gestaltung.css"
