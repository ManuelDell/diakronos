"""UX1j2 — Skalen-Regel: `--pad` (und die übrigen Abstände) sind KEINE Kettenglieder.

Befund (UX1k-Worker, LIVE): Die Prüfung der Gruppe ``skala`` behandelte JEDES
Token ohne eigene Gruppe als Glied der aufsteigenden Kette — also auch
``--pad``, ``--abstand-gruppe``, ``--abstand-innen`` und ``--karte-innen``.
Weil ``--pad`` mit 16 px (Bestand: 14) unter ``--sp-8`` (64 px) liegt, lehnte
der Server JEDE Änderung einer Skalenstufe über 14 px ab — die Abstände ließen
sich über die API praktisch nicht einstellen.

Richtige Regel (Karte UX1j2):
  * ``--sp-1 < --sp-2 < … < --sp-8`` — streng aufsteigend, als GANZES auch
    beim Zurücksetzen eines einzelnen Feldes.
  * Alle übrigen Maße (``--pad`` u. ä.) sind KEINE Kettenglieder; sie werden
    einzeln gegen ihre eigenen Min/Max-Grenzen geprüft.
  * Der Server sagt der Oberfläche, WELCHE Maße die Kette bilden
    (Feld ``skala_ordnung`` in der Antwort von ``lesen``/``speichern``/
    ``zuruecksetzen``) — EINE Quelle für Backend und Oberfläche (UX1k).
  * Eine Altzeile in der Datenbank, die die Kette bricht, landet nicht im CSS.

Geprüft wird über HTTP (nur System Manager) und über den Speicher.
"""

from __future__ import annotations

import pytest

from diakronos_app.gestaltung import speicher
from diakronos_app.gestaltung import tokens as T
from diakronos_app.models.gestaltung import GestaltungAbweichung

API = "diakronos.diakonos.api.gestaltung."


@pytest.fixture()
def admin(patched_db):
    """Ein System Manager (Muster aus test_ux1j_gestaltung.py `rollen`)."""
    from diakronos_app.frappe_compat import set_user
    from diakronos_app.models.core import HasRole, User

    name = "chefin@example.org"
    sess = patched_db()
    if sess.get(User, name) is None:
        sess.add(User(name=name, email=name, full_name=name, enabled=True))
    if sess.get(HasRole, f"hr-{name}") is None:
        sess.add(HasRole(name=f"hr-{name}", parent=name, parenttype="User",
                         parentfield="roles", role="System Manager",
                         docstatus=0, idx=1))
    sess.commit()
    sess.close()
    set_user(name)
    return name


def _speichern(client, werte):
    return client.post(f"/api/method/{API}gestaltung_speichern", json={"werte": werte})


def _zurueck(client, token=None):
    return client.post(
        f"/api/method/{API}gestaltung_zuruecksetzen",
        json={} if token is None else {"token": token},
    )


def _lesen(client):
    return client.post(f"/api/method/{API}gestaltung_lesen", json={})


# ── 1. Die Kette besteht NUR aus --sp-1 … --sp-8 ─────────────────────────

def test_kette_ist_genau_die_skala_token():
    """`--pad` und die übrigen Abstände sind KEINE Kettenglieder."""
    assert set(T.SKALA_TOKEN) == {f"--sp-{i}" for i in range(1, 9)}
    for name in ("--pad", "--abstand-gruppe", "--abstand-innen", "--karte-innen"):
        assert name in T.TOKEN_NAMEN, f"{name} fehlt in der Positivliste"
        assert name not in T.SKALA_TOKEN, f"{name} darf kein Kettenglied sein"


def test_pad_verletzt_die_kette_nicht():
    """--pad (16) liegt unter --sp-8 (64) — das ist erlaubt."""
    T.pruefe_skala({"--pad": 20})
    T.pruefe_skala({"--pad": 12})
    T.pruefe_skala({"--karte-innen": 40, "--abstand-gruppe": 10})


def test_die_kette_gilt_weiter_fuer_die_skala():
    with pytest.raises(ValueError):
        T.pruefe_skala({"--sp-3": 20})  # 20 > --sp-4 (16)
    T.pruefe_skala({"--sp-5": 28})


# ── 2. HTTP: Änderungen, die vorher fälschlich abgelehnt wurden ──────────

def test_skalenstufe_ueber_14px_wird_angenommen(client, admin):
    antwort = _speichern(client, {"--sp-5": 28})
    assert antwort.status_code == 200, antwort.text
    assert antwort.json()["message"]["abweichungen"] == {"--sp-5": 28}


def test_pad_ueber_14px_wird_angenommen(client, admin):
    antwort = _speichern(client, {"--pad": 20})
    assert antwort.status_code == 200, antwort.text
    assert antwort.json()["message"]["abweichungen"] == {"--pad": 20}


def test_sp5_und_pad_gemeinsam_werden_angenommen(client, admin):
    antwort = _speichern(client, {"--sp-5": 28, "--pad": 20})
    assert antwort.status_code == 200, antwort.text
    assert antwort.json()["message"]["abweichungen"] == {"--sp-5": 28, "--pad": 20}


def test_alle_skalenstufen_lassen_sich_anheben(client, admin):
    """Der eigentliche LIVE-Fehler: jede Stufe über 14 px war gesperrt."""
    antwort = _speichern(client, {"--sp-3": 22, "--sp-4": 30, "--sp-5": 38, "--sp-6": 46})
    assert antwort.status_code == 200, antwort.text


# ── 3. HTTP: die Kette gilt weiter ───────────────────────────────────────

def test_gebrochene_kette_wird_abgelehnt_mit_klarer_meldung(client, admin):
    antwort = _speichern(client, {"--sp-3": 20})  # 20 > --sp-4 (16)
    assert antwort.status_code == 417, antwort.text
    text = antwort.text
    assert "--sp-3" in text and "--sp-4" in text
    assert "aufsteigend" in text
    assert _lesen(client).json()["message"]["abweichungen"] == {}


def test_gleichstand_wird_abgelehnt(client, admin):
    antwort = _speichern(client, {"--sp-4": 12})  # gleich --sp-3
    assert antwort.status_code == 417, antwort.text


# ── 4. Zurücksetzen wirkt ────────────────────────────────────────────────

def test_zuruecksetzen_der_skalenstufe_wirkt(client, admin):
    assert _speichern(client, {"--sp-5": 28}).status_code == 200
    assert _speichern(client, {"--pad": 20}).status_code == 200

    antwort = _zurueck(client, "--sp-5")
    assert antwort.status_code == 200, antwort.text
    assert antwort.json()["message"]["abweichungen"] == {"--pad": 20}

    # Auch danach bleibt --pad (kein Kettenglied) unangetastet stehen.
    gelesen = _lesen(client).json()["message"]
    felder = {f["token"]: f for f in gelesen["felder"]}
    assert felder["--sp-5"]["wert"] == T.standard_zu("--sp-5")
    assert felder["--sp-5"]["abweichend"] is False
    assert felder["--pad"]["wert"] == 20


def test_zuruecksetzen_aller_werte_wirkt(client, admin):
    _speichern(client, {"--sp-5": 28, "--pad": 20})
    antwort = _zurueck(client)
    assert antwort.status_code == 200, antwort.text
    assert antwort.json()["message"]["abweichungen"] == {}


# ── 5. EINE Quelle: der Server sagt, was die Kette ist ───────────────────

@pytest.mark.parametrize("endpunkt", ["lesen", "speichern", "zuruecksetzen"])
def test_antwort_nennt_die_kette(client, admin, endpunkt):
    """Die Oberfläche (UX1k) darf keine eigene Kette raten müssen."""
    if endpunkt == "lesen":
        antwort = _lesen(client)
    elif endpunkt == "speichern":
        antwort = _speichern(client, {"--pad": 20})
    else:
        antwort = _zurueck(client)
    assert antwort.status_code == 200, antwort.text
    ordnung = antwort.json()["message"]["skala_ordnung"]
    assert ordnung == list(T.SKALA_TOKEN)
    assert "--pad" not in ordnung


def test_felder_tragen_die_gruppe_skala_nur_fuer_die_kette(client, admin):
    """`gruppe` bleibt bei allen Abständen `skala`; die Kette steht separat da."""
    gelesen = _lesen(client).json()["message"]
    felder = {f["token"]: f for f in gelesen["felder"]}
    assert felder["--pad"]["gruppe"] == T.SKALA_GRUPPE
    assert "skala_ordnung" in gelesen


# ── 6. Altzeile, die die Kette bricht, kommt nicht ins CSS ───────────────

def test_gebrochene_altzeile_landet_nicht_im_css(patched_db):
    sess = patched_db()
    sess.add(GestaltungAbweichung(token="--sp-3", wert=30, geaendert_von="x"))
    sess.add(GestaltungAbweichung(token="--pad", wert=20, geaendert_von="x"))
    sess.commit()
    sess.close()

    css = speicher.als_css()
    assert "--sp-3" not in css, "gebrochene Kette darf nicht ausgeliefert werden"
    assert "--pad: 20px;" in css, "einzeln geprüfte Maße bleiben gültig"


def test_gebrochene_altzeile_wird_beim_speichern_mitrepariert(patched_db):
    """Ein Speichervorgang, der die Kette wieder herstellt, ist erlaubt."""
    sess = patched_db()
    sess.add(GestaltungAbweichung(token="--sp-3", wert=30, geaendert_von="x"))
    sess.commit()
    sess.close()

    nach = speicher.speichern({"--sp-3": 12}, benutzer="chefin@example.org")
    assert nach == {}
