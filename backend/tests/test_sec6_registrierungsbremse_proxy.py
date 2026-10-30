"""SEC-6 — Registrierungs-Rate-Limit wirkt auch hinter Proxy/NAT (N2).

Befund aus dem Pentest von dev.ecg-hn.de (Runde 2, MITTEL):

    Der IP-Zaehler der Registrierungsbremse ist fuer private/loopback-Adressen
    BEFREIT (`registrierungsbremse._zaehle_ip` -> `_ist_eigene_adresse`).
    Hinter einem Reverse-Proxy/NAT sieht das Backend immer die Adresse des
    Proxies — also immer eine private. Damit feuerte der IP-Zaehler nie.

    Im Pentest feuerte aber auch der LINK-Zaehler (`registrierung_max_link`,
    Default 20) nicht: 25x `submit_registrierung` und 65x `validate_token`
    liefen ohne 429 durch. Der Validierungs-Zaehler haing an derselben
    Adressbefreiung wie der IP-Zaehler, und der Link-Zaehler wird von
    `_pruefe_bremse` erst NACH der Adresspruefung gezaehlt — wich die
    Adresspruefung vorher aus, wurde gar nicht weitergezaehlt.

VORGABE (Manuel, verbindlich): Hinter einem Proxy ist IP-basiert sinnlos.
Der TOKEN-/LINK-Zaehler ist der eigentliche Schutz und MUSS unabhaengig von
der (privaten) Adresse greifen.

    (S1) LINK-Zaehler und VALIDIERUNGS-Zaehler haengen NICHT mehr an der
         Privat-IP-Befreiung. Nur der reine IP-Zaehler darf sie behalten.
    (S2) Die Bremse laeuft auf BEIDEN Wegen (`validate_token` UND
         `submit_registrierung`), liefert ab der Schwelle HTTP 429
         (`RateLimitError`) und die Defaults sind 20/60/10 — nicht 0.

Die Datei ist der Reproduktionstest: an der Basis sind die hier geprueften
Faelle rot, weil jede Adresse im Test privat ist (so wie hinter dem Proxy)
und die Zaehler deshalb schweigen. Alle Aufrufe laufen ueber
`patched_db`/`fake_redis` — nie gegen die Betriebs-DB oder das Betriebs-Redis.
"""

from __future__ import annotations

import pytest

import diakronos_app.api  # noqa: F401 — registriert alle portierten Endpunkte

MODUL = "diakronos.diakronos.api.registrierung"

SLUG = "abc123slug"
LINK = "RL-1"
# DIE Adresse des Befunds: hinter Reverse-Proxy/NAT ist sie IMMER privat.
# `10.0.0.5` steht fuer den Proxy im eigenen Netz (RFC 1918).
PROXY_IP = "10.0.0.5"
# Dieselbe Adresse in einer anderen Schreibweise — derselbe Absender darf
# nicht durch Wechsel der Notation ein neues Kontingent bekommen.
PROXY_IP_ANDERS = "10.0.000.5"


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


def _mit_proxy_ip(monkeypatch, ip=PROXY_IP):
    """Client-IP des laufenden Requests auf eine PRIVATE Adresse setzen.

    Genau der Betriebsfall: der TestClient hat als Host `testclient`, das
    Backend sieht hinter dem Proxy die private Adresse. Dieselbe Naht, die
    `BEHIND_PROXY` im Betrieb nutzt (`request_context.zaehler_client_ip`).
    """
    from diakronos_app import request_context

    monkeypatch.setattr(request_context, "zaehler_client_ip", lambda: ip)


def _post_anmeldung(client, token=SLUG, **extra):
    """Minimal gueltiger Registrierungs-POST (inkl. Einwilligung)."""
    daten = {"token": token, "vorname": "Anna", "nachname": "Beispiel", "dsgvo": True}
    daten.update(extra)
    return client.post(f"/api/method/{MODUL}.submit_registrierung", data=daten)


def _validiere(client, token=SLUG):
    return client.get(f"/api/method/{MODUL}.validate_token", params={"token": token})


# ════════════════════════════════════════════════════════════════════════════
# S2 — die Defaults sind Grenzen, nicht das Nichts
# ════════════════════════════════════════════════════════════════════════════


def test_s2_defaults_begrenzen_link_validierung_und_ip():
    """Ohne Eingriff in die Umgebung sind alle drei Schwellen > 0.

    Ein Default `0` hiesse „unbegrenzt“ — genau der Zustand aus dem Pentest.
    """
    from diakronos_app.settings import settings

    assert settings.registrierung_max_link == 20
    assert settings.registrierung_max_validierung == 60
    assert settings.registrierung_max_ip == 10
    assert settings.registrierung_fenster_sekunden > 0


# ════════════════════════════════════════════════════════════════════════════
# S1 — validate_token: der VALIDIERUNGS-Zaehler greift auch bei privater IP
# ════════════════════════════════════════════════════════════════════════════


def test_s1_validate_token_zaehlt_trotz_privater_adresse(
    client, welt, fake_redis, monkeypatch
):
    """Ab der Schwelle kommt 429 — obwohl die Adresse privat (dem Proxy) ist.

    Der Pentest lief 65 Pruefungen ohne Bremse; hier ist die Grenze 4 und die
    fuenfte Pruefung MUSS als HTTP 429 (`RateLimitError`) ankommen.
    """
    from diakronos_app.settings import settings

    _mit_proxy_ip(monkeypatch)
    monkeypatch.setattr(settings, "registrierung_max_validierung", 4)

    codes = [_validiere(client).status_code for _ in range(4)]
    assert codes == [200, 200, 200, 200], codes

    gebremst = _validiere(client)
    assert gebremst.status_code == 429, gebremst.text
    # SEC-8/S2: Klassenname generisch — die Grenze steht an der Statuszeile (429).
    assert gebremst.json()["exc_type"] == "Error", gebremst.text
    assert "zu viele" in gebremst.text.lower(), gebremst.text


def test_s1_validate_token_bremse_auch_fuer_erfundene_tokens(
    client, welt, fake_redis, monkeypatch
):
    """Token-Enumeration: geratene Tokens verbrauchen das Kontingent ebenfalls."""
    from diakronos_app.settings import settings

    _mit_proxy_ip(monkeypatch)
    monkeypatch.setattr(settings, "registrierung_max_validierung", 3)

    codes = [_validiere(client, f"geraten{i}").status_code for i in range(3)]
    assert codes == [403, 403, 403], codes

    assert _validiere(client, "geraten99").status_code == 429


def test_s1_validate_token_schreibweise_aendert_nichts(
    client, welt, fake_redis, monkeypatch
):
    """`10.0.0.5` und `10.0.000.5` sind derselbe Absender (ein Kontingent)."""
    from diakronos_app.settings import settings

    monkeypatch.setattr(settings, "registrierung_max_validierung", 2)

    _mit_proxy_ip(monkeypatch)
    assert _validiere(client).status_code == 200
    assert _validiere(client).status_code == 200

    _mit_proxy_ip(monkeypatch, PROXY_IP_ANDERS)
    assert _validiere(client).status_code == 429


# ════════════════════════════════════════════════════════════════════════════
# S1/S2 — submit_registrierung: der LINK-Zaehler greift bei privater IP
# ════════════════════════════════════════════════════════════════════════════


def test_s1_submit_registrierung_linkgrenze_greift_trotz_privater_adresse(
    client, welt, fake_redis, monkeypatch
):
    """Nach `registrierung_max_link` Absendeversuchen je Link kommt 429.

    Der Pentest schickte 25 Anmeldungen ueber denselben Link (Default 20) —
    alle ohne Bremse. Hier ist die Grenze 3, der vierte Versuch MUSS 429
    liefern, obwohl die Adresse privat ist.
    """
    from diakronos_app.settings import settings

    _mit_proxy_ip(monkeypatch)
    monkeypatch.setattr(settings, "registrierung_max_link", 3)
    monkeypatch.setattr(settings, "registrierung_max_ip", 100)

    for i in range(3):
        r = _post_anmeldung(client, nachname=f"Beispiel{i}")
        assert r.status_code == 200, (i, r.text)

    gebremst = _post_anmeldung(client, nachname="Vier")
    assert gebremst.status_code == 429, gebremst.text
    # SEC-8/S2: Klassenname generisch — die Grenze steht an der Statuszeile (429).
    assert gebremst.json()["exc_type"] == "Error", gebremst.text
    assert "zu viele" in gebremst.text.lower(), gebremst.text


def test_s2_legitime_erstvalidierung_bleibt_erlaubt(
    client, welt, fake_redis, monkeypatch
):
    """Gegenprobe: die erste, legitime Validierung und Anmeldung gehen durch."""
    from diakronos_app.settings import settings

    _mit_proxy_ip(monkeypatch)
    monkeypatch.setattr(settings, "registrierung_max_validierung", 60)
    monkeypatch.setattr(settings, "registrierung_max_link", 20)

    assert _validiere(client).status_code == 200
    r = _post_anmeldung(client)
    assert r.status_code == 200, r.text


def test_s2_ip_zaehler_bleibt_fuer_eigene_adressen_befreit(
    fake_redis, monkeypatch
):
    """Der REINE IP-Zaehler behaelt die Befreiung (Vorgabe: nur sekundaer).

    Hinter dem Proxy waere er ohnehin wirkungslos; die Zaehler fuer Link und
    Validierung duerfen davon aber NICHT mehr abhaengen (S1, oben).
    """
    from diakronos_app.anmeldung import registrierungsbremse
    from diakronos_app.settings import settings

    monkeypatch.setattr(settings, "registrierung_max_ip", 1)
    monkeypatch.setattr(settings, "registrierung_max_link", 0)

    for _ in range(10):
        assert registrierungsbremse.pruefe(PROXY_IP, None, fake_redis)[0] is True


def test_s1_link_zaehler_laeuft_auch_ohne_bekannte_adresse(fake_redis, monkeypatch):
    """Ohne Adresse (None) traegt der Link-Zaehler die Bremse allein."""
    from diakronos_app.anmeldung import registrierungsbremse
    from diakronos_app.settings import settings

    monkeypatch.setattr(settings, "registrierung_max_ip", 100)
    monkeypatch.setattr(settings, "registrierung_max_link", 2)

    assert registrierungsbremse.pruefe(None, "tok", fake_redis) == (True, "")
    assert registrierungsbremse.pruefe(None, "tok", fake_redis) == (True, "")
    erlaubt, grund = registrierungsbremse.pruefe(None, "tok", fake_redis)
    assert (erlaubt, grund) == (False, "link")


def test_s1_stand_zeigt_link_und_validierung_trotz_privater_adresse(
    fake_redis, monkeypatch
):
    """Die Diagnose (`zaehler_stand`) verschweigt private Adressen nicht mehr."""
    from diakronos_app.anmeldung import registrierungsbremse
    from diakronos_app.settings import settings

    monkeypatch.setattr(settings, "registrierung_max_ip", 10)
    monkeypatch.setattr(settings, "registrierung_max_link", 10)
    monkeypatch.setattr(settings, "registrierung_max_validierung", 10)

    registrierungsbremse.pruefe(PROXY_IP, "tok", fake_redis)
    registrierungsbremse.zaehle_validierung(PROXY_IP, fake_redis)

    stand = registrierungsbremse.zaehler_stand(PROXY_IP, "tok", fake_redis)
    assert stand["link"] == 1, stand
    assert stand["validierung"] == 1, stand
    # Der reine IP-Zaehler bleibt bei eigener Adresse bewusst auf 0.
    assert stand["ip"] == 0, stand
