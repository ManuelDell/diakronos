"""P0-4b — Nacharbeit der oeffentlichen Registrierung (Befunde 1-11, N1, N2).

Reproduktionstests aus dem Code-Review P0-4
(Reproduktionsschritte im Code-Review zur Karte P0-4) und der
Operator-Nachtrag N1/N2:

   1  wichtig  Ratenbegrenzung der anonymen Registrierungs-Endpunkte
   2  wichtig  atomarer Anmeldezaehler (max_anmeldungen nie ueberschritten)
   3  wichtig  Logs ohne personenbezogene SQL-Parameter und ohne Token
   4  wichtig  OP-CHOR-4 Deep-Link auch bei aktivem OIDC
   5  wichtig  Rollenliste kommt vom Server (nicht fest in Anmeldung.vue)
   6  klein    dsgvo-Zustimmung serverseitig verlangt
   7  klein    Link-Ableitung an EINER Stelle (keine 3 Kopien)
   8  klein    fehlende Negativfaelle/OIDC-Tests
  10  klein    Hinweis zur globalen Neutralisierung (bekannte Grenze)
  11  klein    Referrer-Policy: no-referrer auf den oeffentlichen Seiten
   N1         BYSETPOS wieder erlauben, BYHOUR bleibt verboten
   N2         doppelter Pfad in aus_terminlimit

Die Datei ist der Reproduktionstest: an der Basis (vor den Aenderungen) sind
die Faelle rot.
"""

from __future__ import annotations

import json
import logging
import re

import pytest

import diakronos_app.api  # noqa: F401 — registriert alle portierten Endpunkte
from diakronos_app.frappe_compat.session import set_user

MODUL = "diakronos.diakonos.api.registrierung"
MODUL_LINK = "diakronos.diakonos.api.registrierungslink_api"

SLUG = "abc123slug"
LINK = "RL-1"
ADMIN = "mitgliederadmin@example.org"


# ── Fixtures (wie test_p0_4_oeffentliche_anmeldung) ─────────────────────────


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
    from diakronos_app.models.diakonos import (
        Anmeldeformular,
        AnmeldeformularFeld,
    )

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


def _post_anmeldung(client, **extra):
    """Minimal gueltiger Registrierungs-POST (inkl. Einwilligung)."""
    daten = {"token": SLUG, "vorname": "Anna", "nachname": "Beispiel", "dsgvo": True}
    daten.update(extra)
    return client.post(f"/api/method/{MODUL}.submit_registrierung", data=daten)


# ════════════════════════════════════════════════════════════════════════════
# Befund 1 — Ratenbegrenzung
# ════════════════════════════════════════════════════════════════════════════


def _mit_ip(monkeypatch, ip="203.0.113.7"):
    """Setzt die Client-IP des laufenden Requests auf eine zaehlbare Adresse.

    Der TestClient hat als Host `testclient` (kein gueltiges IP-Literal); der
    IP-Zaehler wuerde ihn deshalb — wie jede eigene/ungueltige Adresse —
    ueberspringen. Fuer die IP-Grenze wird daher eine echte oeffentliche IP
    vorgegeben (dieselbe Naht, die `BEHIND_PROXY` im Betrieb nutzt).
    """
    from diakronos_app import request_context

    monkeypatch.setattr(request_context, "zaehler_client_ip", lambda: ip)


def test_befund1_ip_bremse_blockt_nach_schwelle(client, welt, fake_redis, monkeypatch):
    """Nach `REGISTRIERUNG_MAX_IP` Absendeversuchen wird gebremst."""
    from diakronos_app.settings import settings

    _mit_ip(monkeypatch)
    monkeypatch.setattr(settings, "registrierung_max_ip", 3)
    monkeypatch.setattr(settings, "registrierung_max_link", 100)

    for i in range(3):
        r = _post_anmeldung(client, nachname=f"Beispiel{i}")
        assert r.status_code == 200, (i, r.text)

    r = _post_anmeldung(client, nachname="Zuviel")
    assert r.status_code >= 400, "die Adressgrenze muss greifen"
    assert "zu viele" in r.text.lower(), r.text


def test_befund1_link_bremse_blockt_nach_schwelle(client, welt, fake_redis, monkeypatch):
    """Nach `REGISTRIERUNG_MAX_LINK` Absendeversuchen je Link wird gebremst."""
    from diakronos_app.settings import settings

    monkeypatch.setattr(settings, "registrierung_max_ip", 100)
    monkeypatch.setattr(settings, "registrierung_max_link", 2)

    for i in range(2):
        assert _post_anmeldung(client, nachname=f"B{i}").status_code == 200

    r = _post_anmeldung(client, nachname="Zuviel")
    assert r.status_code >= 400
    assert "zu viele" in r.text.lower(), r.text


def test_befund1_gueltige_anmeldung_zaehlt_nicht_als_fehler(client, welt, fake_redis, monkeypatch):
    """Ein Seitenaufruf verbraucht NICHT das Absende-Kontingent."""
    from diakronos_app.settings import settings

    monkeypatch.setattr(settings, "registrierung_max_ip", 100)
    monkeypatch.setattr(settings, "registrierung_max_link", 2)
    monkeypatch.setattr(settings, "registrierung_max_validierung", 100)

    # Zwei Seitenaufrufe (Tokenpruefungen) …
    for _ in range(2):
        assert client.get(
            f"/api/method/{MODUL}.validate_token", params={"token": SLUG}
        ).status_code == 200

    # … und danach sind trotzdem noch beide Absendeplaetze frei.
    assert _post_anmeldung(client, nachname="A").status_code == 200
    assert _post_anmeldung(client, nachname="B").status_code == 200
    # Der dritte Absendeversuch geht ueber die Linkgrenze -> gebremst.
    assert _post_anmeldung(client, nachname="C").status_code >= 400


def test_befund1_validierung_hat_eigene_grenze(client, welt, fake_redis, monkeypatch):
    """Viele Seitenaufrufe werden ab `REGISTRIERUNG_MAX_VALIDIERUNG` gebremst."""
    from diakronos_app.settings import settings
    from diakronos_app.anmeldung import registrierungsbremse

    monkeypatch.setattr(settings, "registrierung_max_validierung", 2)

    erlaubt = registrierungsbremse.zaehle_validierung("203.0.113.5", fake_redis)
    assert erlaubt is True
    assert registrierungsbremse.zaehle_validierung("203.0.113.5", fake_redis) is True
    assert registrierungsbremse.zaehle_validierung("203.0.113.5", fake_redis) is False


def test_befund1_eigene_adresse_wird_nicht_gezaehlt(fake_redis, monkeypatch):
    """Hinter einem Proxy (private Adresse) darf der IP-Zaehler nicht greifen."""
    from diakronos_app.settings import settings
    from diakronos_app.anmeldung import registrierungsbremse

    monkeypatch.setattr(settings, "registrierung_max_ip", 1)
    for _ in range(10):
        assert registrierungsbremse.pruefe("127.192_168_001_050.127", "tok", fake_redis)[0] is True


# ════════════════════════════════════════════════════════════════════════════
# Befund 2 — atomarer Anmeldezaehler
# ════════════════════════════════════════════════════════════════════════════


def test_befund2_zaehler_lehnt_bei_voller_spalte_ab(patched_db):
    """Ist das Kontingent aufgebraucht, liefert der atomare Zaehler False."""
    from diakronos_app.api.registrierung import _inkrementiere_zaehler
    from diakronos_app.models.diakonos import Registrierungslink

    sess = patched_db()
    sess.add(_link(name="RL-VOLL", slug="voll", max_anmeldungen=2, anmeldungen_count=2))
    sess.commit()
    sess.close()

    assert _inkrementiere_zaehler("RL-VOLL", 2) is False

    sess = patched_db()
    satz = sess.get(Registrierungslink, "RL-VOLL")
    assert satz.anmeldungen_count == 2, "der Zaehler darf nicht ueber das Maximum steigen"
    sess.close()


def test_befund2_zaehler_erhoeht_bis_zur_grenze(patched_db):
    """Bis zum Maximum zaehlt der atomare Zaehler hoch, danach nicht mehr."""
    from diakronos_app.api.registrierung import _inkrementiere_zaehler
    from diakronos_app.models.diakonos import Registrierungslink

    sess = patched_db()
    sess.add(_link(name="RL-PLATZ", slug="platz", max_anmeldungen=2, anmeldungen_count=0))
    sess.commit()
    sess.close()

    assert _inkrementiere_zaehler("RL-PLATZ", 2) is True
    assert _inkrementiere_zaehler("RL-PLATZ", 2) is True
    assert _inkrementiere_zaehler("RL-PLATZ", 2) is False

    sess = patched_db()
    assert sess.get(Registrierungslink, "RL-PLATZ").anmeldungen_count == 2
    sess.close()


def test_befund2_ohne_grenze_zaehlt_immer(patched_db):
    """`max_anmeldungen=0` heisst unbegrenzt — der Zaehler laeuft weiter."""
    from diakronos_app.api.registrierung import _inkrementiere_zaehler
    from diakronos_app.models.diakonos import Registrierungslink

    sess = patched_db()
    sess.add(_link(name="RL-FREI", slug="frei", max_anmeldungen=0, anmeldungen_count=5))
    sess.commit()
    sess.close()

    assert _inkrementiere_zaehler("RL-FREI", 0) is True
    sess = patched_db()
    assert sess.get(Registrierungslink, "RL-FREI").anmeldungen_count == 6
    sess.close()


def test_befund2_parallele_anfragen_ueberschreiten_das_maximum_nie(tmp_path, monkeypatch):
    """Nebenlaeufigkeit: viele gleichzeitige Reservierungen, nie mehr als max.

    Ohne die atomare Bedingung (Read-Modify-Write) verlieren parallele Aufrufe
    Schritte bzw. ueberschreiten das Maximum. Der Test startet 20 Threads
    gleichzeitig gegen ein Kontingent von 5.

    Eigene, DATEIBASIERTE SQLite-Engine mit `NullPool`: die Test-Engine der
    uebrigen Fixtures teilt EINE Verbindung (StaticPool), und SQLite kann
    darauf keine parallelen Schreiber ausfuehren. Fuer einen echten
    Nebenlaeufigkeitstest braucht jeder Thread seine eigene Verbindung — genau
    wie im Betrieb (PostgreSQL). Die Atomaritaet selbst ist datenbankseitig
    (das UPDATE ... WHERE), nicht SQLite-spezifisch.
    """
    import threading

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import NullPool

    import diakronos_app.models  # noqa: F401 — Modelle registrieren
    from diakronos_app.models.base import Base

    pfad = tmp_path / "race.sqlite"
    eng = create_engine(
        f"sqlite+pysqlite:///{pfad}",
        connect_args={"check_same_thread": False, "timeout": 30},
        poolclass=NullPool,
        future=True,
    )
    Base.metadata.create_all(eng)
    fabrik = sessionmaker(bind=eng, autoflush=False, autocommit=False, future=True)

    import diakronos_app.db as dbmod
    from diakronos_app.api import registrierung as reg

    monkeypatch.setattr(dbmod, "SessionLocal", fabrik)
    # Der Helfer holt `SessionLocal` per `from ... import` — die Modulbindung
    # wird im Aufruf aufgeloest, deshalb genuegt das Patchen von `db`; zur
    # Sicherheit wird die im Modul genutzte Referenz mitgesetzt.
    monkeypatch.setattr(reg, "SessionLocal", fabrik, raising=False)

    sess = fabrik()
    sess.add(_link(name="RL-RACE", slug="race", max_anmeldungen=5, anmeldungen_count=0))
    sess.commit()
    sess.close()

    erfolge: list[bool] = []
    sperre = threading.Lock()
    start = threading.Barrier(20)

    def _lauf():
        start.wait()
        ok = reg._inkrementiere_zaehler("RL-RACE", 5)
        with sperre:
            erfolge.append(ok)

    threads = [threading.Thread(target=_lauf) for _ in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert sum(1 for e in erfolge if e) == 5, f"erwartet 5 Zusagen, waren {sum(erfolge)}"
    from diakronos_app.models.diakonos import Registrierungslink

    sess = fabrik()
    assert sess.get(Registrierungslink, "RL-RACE").anmeldungen_count == 5
    sess.close()
    eng.dispose()


def test_befund2_platzfreigabe_gibt_reservierung_zurueck(patched_db):
    """Scheitert das Anlegen, wird der reservierte Platz wieder frei."""
    from diakronos_app.api.registrierung import _gib_platz_frei
    from diakronos_app.models.diakonos import Registrierungslink

    sess = patched_db()
    sess.add(_link(name="RL-ZURUECK", slug="zurueck", max_anmeldungen=5, anmeldungen_count=3))
    sess.commit()
    sess.close()

    _gib_platz_frei("RL-ZURUECK")
    sess = patched_db()
    assert sess.get(Registrierungslink, "RL-ZURUECK").anmeldungen_count == 2
    sess.close()


# ════════════════════════════════════════════════════════════════════════════
# Befund 3 — Logs ohne PII / Token
# ════════════════════════════════════════════════════════════════════════════


def test_befund3_kinddaten_log_ohne_personenbezug(client, welt, caplog):
    """Ein fehlerhaftes Kinddatum darf nicht den Rohwert ins Log schreiben."""
    with caplog.at_level(logging.WARNING):
        _post_anmeldung(client, kinder=json.dumps([
            {"vorname": "Kind", "nachname": "Beispiel", "geburtstag": "kein-datum"},
        ]))
    block = "\n".join(rec.getMessage() for rec in caplog.records)
    assert "kein-datum" not in block, "das Rohdatum taucht im Log auf"
    assert "18.05.1990" not in block


def test_befund3_spa_loggt_keinen_token(client, welt, caplog, monkeypatch):
    """Ein Programmfehler beim Linkpruefen darf den Token nicht protokollieren."""
    from diakronos_app.api import registrierung as reg

    def platzt(*_a, **_k):
        raise RuntimeError("kaputte Abfrage")

    monkeypatch.setattr(reg, "validate_token", platzt)

    with caplog.at_level(logging.WARNING):
        client.get("/diakonos/registrierung", params={"token": SLUG})

    block = "\n".join(rec.getMessage() for rec in caplog.records)
    assert SLUG not in block, "der Token steht im Log"


# ════════════════════════════════════════════════════════════════════════════
# Befund 4 — OP-CHOR-4 Deep-Link bei OIDC
# ════════════════════════════════════════════════════════════════════════════


def test_befund4_transaktion_speichert_ziel(fake_redis):
    """Das Ziel wird mit der OIDC-Transaktion gespeichert und wiedergefunden."""
    from diakronos_app.anmeldung import transaktionen

    transaktionen.ablegen("state-1", "nonce-1", "verifier-1", "/diakonos#/planrahmen/plan/P-1")
    daten = transaktionen.entnehmen("state-1")
    assert daten is not None
    assert daten["ziel"] == "/diakonos#/planrahmen/plan/P-1"


def test_befund4_transaktion_ohne_ziel_bleibt_leer(fake_redis):
    """Ohne Ziel bleibt das Feld leer (kein Altverhalten bricht)."""
    from diakronos_app.anmeldung import transaktionen

    transaktionen.ablegen("state-2", "nonce-2", "verifier-2")
    daten = transaktionen.entnehmen("state-2")
    assert daten is not None
    assert daten.get("ziel") == ""


def test_befund4_hash_bruecke_merkt_den_hash():
    """Die Zwischenseite legt `location.hash` in `sessionStorage` ab."""
    from diakronos_app.anmeldung.routen import _hash_bruecke_seite

    html = _hash_bruecke_seite("/diakonos")
    assert "location.hash" in html
    assert "sessionStorage.setItem('dk-login-hash'" in html
    assert "/login?sso=1&redirect-to=" in html


def test_befund4_hash_wiederherstellen_setzt_hash_an():
    """Die Rueckkehrseite haengt den gemerkten Hash wieder an das Ziel."""
    from diakronos_app.anmeldung.routen import _hash_wiederherstellen_seite

    html = _hash_wiederherstellen_seite("/diakonos#/planrahmen/plan/P-1")
    assert "sessionStorage.getItem('dk-login-hash')" in html
    assert "ziel + hash" in html


def test_befund4_bruecke_escapet_script_ende():
    """`</script>` im Ziel darf das Tag nicht schliessen (XSS-Schutz)."""
    from diakronos_app.anmeldung.routen import _hash_bruecke_seite

    html = _hash_bruecke_seite("/diakonos</script><script>alert(1)</script>")
    assert "</script><script>alert(1)" not in html
    assert "\\u003c" in html


def test_befund4_login_leitet_bei_oidc_ueber_die_bruecke(monkeypatch):
    """Bei aktivem OIDC liefert `/login` zuerst die Brueckenseite."""
    from diakronos_app.anmeldung import konfiguration as konf

    monkeypatch.setattr(konf, "oidc_aktiv", lambda: True)

    from diakronos_app.main import app
    from fastapi.testclient import TestClient

    with TestClient(app) as c:
        r = c.get("/login", params={"redirect-to": "/diakonos#/planrahmen/plan/P-1"},
                  follow_redirects=False)
    assert r.status_code == 200, r.text
    assert "sessionStorage" in r.text, "die Bruecke muss den Hash merken"


def test_befund4_relatives_ziel_pruefung_bleibt_streng():
    """Die Zwischenseiten bauen keinen offenen Redirect."""
    from diakronos_app.anmeldung.routen import _relatives_ziel

    assert _relatives_ziel("https://evil.de") != "https://evil.de"
    assert _relatives_ziel("//evil.de") == "/diakonos"
    assert _relatives_ziel("/diakonos#/planrahmen") == "/diakonos#/planrahmen"


# ════════════════════════════════════════════════════════════════════════════
# Befund 5 — Rollenliste vom Server
# ════════════════════════════════════════════════════════════════════════════


def test_befund5_rollen_kommen_vom_server(admin_client, patched_db):
    """`anmeldung_get_einstellungen` liefert die waehlbaren Rollen mit."""
    r = admin_client.get(
        "/api/method/diakronos.anmeldung.anmeldung_get_einstellungen", params={}
    )
    assert r.status_code == 200, r.text
    rollen = r.json()["message"]["rollen"]
    assert "System Manager" in rollen
    assert "Kalenderadministrator" in rollen


def test_befund5_eigener_endpunkt(admin_client):
    """Der eigene Rollen-Endpunkt liefert dieselbe Liste."""
    r = admin_client.get("/api/method/diakronos.anmeldung.anmeldung_get_rollen", params={})
    assert r.status_code == 200, r.text
    assert "System Manager" in r.json()["message"]["rollen"]


def test_befund5_rollen_endpunkt_nur_admin(guest_client):
    """Ohne Administratorrolle kein Zugriff."""
    r = guest_client.get("/api/method/diakronos.anmeldung.anmeldung_get_rollen", params={})
    assert r.status_code >= 400


def test_befund5_db_rollen_haben_vorrang(admin_client, patched_db):
    """Fuehrt die Installation echte Rollen, stehen sie in der Liste."""
    from diakronos_app.models.core import Role

    sess = patched_db()
    sess.add(Role(name="Eigene Rolle"))
    sess.commit()
    sess.close()

    r = admin_client.get("/api/method/diakronos.anmeldung.anmeldung_get_rollen", params={})
    assert "Eigene Rolle" in r.json()["message"]["rollen"]


# ════════════════════════════════════════════════════════════════════════════
# Befund 6 — dsgvo-Zustimmung serverseitig verlangt
# ════════════════════════════════════════════════════════════════════════════


def test_befund6_ohne_zustimmung_abgelehnt(client, welt):
    """Ein direkter API-Aufruf ohne Einwilligung legt keine Anmeldung an."""
    r = client.post(
        f"/api/method/{MODUL}.submit_registrierung",
        data={"token": SLUG, "vorname": "Anna", "nachname": "Beispiel"},
    )
    assert r.status_code >= 400, r.text
    assert "stimme der verarbeitung" in r.text.lower(), r.text


def test_befund6_mit_zustimmung_erlaubt(client, welt):
    """Mit Zustimmung laeuft die Registrierung wie zuvor."""
    r = _post_anmeldung(client)
    assert r.status_code == 200, r.text
    assert r.json()["message"]["success"] is True


def test_befund6_gast_ohne_zustimmung_abgelehnt(client, welt):
    """Dasselbe fuer die Gast-Anmeldung."""
    from diakronos_app.models.diakonos import Registrierungslink

    sess = welt
    sess.add(_link(name="RL-GAST", slug="gastslug", typ="Gast-Anmeldung"))
    sess.commit()

    r = client.post(
        f"/api/method/{MODUL}.submit_gast",
        data={"token": "gastslug", "vorname": "Gast", "nachname": "Beispiel"},
    )
    assert r.status_code >= 400, r.text


# ════════════════════════════════════════════════════════════════════════════
# Befund 7 — Link-Ableitung an EINER Stelle
# ════════════════════════════════════════════════════════════════════════════


def test_befund7_gemeinsame_ableitung():
    """Die zentrale Funktion bildet die Adresse korrekt."""
    from diakronos_app.anmeldung.registrierungslink import (
        link_anzeige,
        link_seite,
        neuer_token,
        normalisiere_link,
    )

    assert link_seite("Gast-Anmeldung") == "gast"
    assert link_seite("Mitglied-Registrierung") == "registrierung"
    assert link_anzeige("Mitglied-Registrierung", "abc") == "/diakonos/registrierung?token=abc"
    assert link_anzeige("Gast-Anmeldung", "xyz") == "/diakonos/gast?token=xyz"
    assert link_anzeige("Mitglied-Registrierung", "") == ""
    assert len(neuer_token()) >= 10
    assert normalisiere_link({"typ": "Gast-Anmeldung", "slug": "s"})["link_anzeige"] == \
        "/diakonos/gast?token=s"


def test_befund7_keine_dritten_kopien():
    """Die drei Aufrufer nutzen die gemeinsame Funktion (kein eigener f-String)."""
    from diakronos_app.api import admin_hub, registrierungslink_api

    assert registrierungslink_api._link_anzeige("Gast-Anmeldung", "s") == "/diakonos/gast?token=s"
    assert admin_hub._normalisiere_link({"typ": "Mitglied-Registrierung", "slug": "s"})[
        "link_anzeige"
    ] == "/diakonos/registrierung?token=s"


# ════════════════════════════════════════════════════════════════════════════
# Befund 11 — Referrer-Policy
# ════════════════════════════════════════════════════════════════════════════


def test_befund11_oeffentliche_seite_ohne_referrer(guest_client, welt):
    """Die oeffentliche Seite traegt `Referrer-Policy: no-referrer`."""
    r = guest_client.get("/diakonos/registrierung", params={"token": SLUG})
    assert r.headers.get("referrer-policy") == "no-referrer", r.headers


# ════════════════════════════════════════════════════════════════════════════
# N1 — BYSETPOS wieder erlauben
# ════════════════════════════════════════════════════════════════════════════


def test_n1_bysetpos_erlaubt():
    """'letzter Sonntag im Monat' muss wieder als Regel durchgehen."""
    from diakronos_app.planrahmen.rrule import rrule_problem

    assert rrule_problem("FREQ=MONTHLY;BYDAY=SU;BYSETPOS=-1") is None


def test_n1_byhour_bleibt_verboten():
    """BYHOUR vervielfacht weiterhin und bleibt abgelehnt."""
    from diakronos_app.planrahmen.rrule import rrule_problem

    problem = rrule_problem("FREQ=DAILY;BYHOUR=9")
    assert problem is not None
    assert problem[0] == "rrule_expansion_zu_fein"


def test_n1_bysetpos_in_engine_laeuft():
    """Die Engine erzeugt fuer BYSETPOS genau einen Termin je Monat."""
    from datetime import date

    from diakronos_app.planrahmen.engine.termine import erzeuge_termine

    plantyp = {
        "termine": {"regel": "FREQ=MONTHLY;BYDAY=SU;BYSETPOS=-1", "von": "2026-01-01"},
    }
    ergebnis = erzeuge_termine(plantyp, {}, None, von=date(2026, 1, 1), bis=date(2026, 3, 31))
    termine = ergebnis.get("standard") or []
    assert len(termine) == 3, f"erwartet 3 Monatstermine, waren {len(termine)}"
    # Jeweils der letzte Sonntag: 25.01., 22.02., 29.03.2026
    assert [t.datum for t in termine] == [
        date(2026, 1, 25), date(2026, 2, 22), date(2026, 3, 29),
    ]


# ════════════════════════════════════════════════════════════════════════════
# N2 — kein doppelter Pfad in aus_terminlimit
# ════════════════════════════════════════════════════════════════════════════


def test_n2_pfad_nicht_verdoppelt():
    """Ein gesetzter Reihenpfad wird unveraendert uebernommen."""
    from diakronos_app.planrahmen.dienste import DienstFehler
    from diakronos_app.planrahmen.engine.termine import TerminLimitUeberschritten

    exc = TerminLimitUeberschritten("zu viele Termine", "/terminreihen/0/termine/regel")
    fehler = DienstFehler.aus_terminlimit(exc)
    pfad = fehler.meldungen[0]["pfad"] if hasattr(fehler, "meldungen") else fehler.args[0][0]["pfad"]
    assert pfad == "/terminreihen/0/termine/regel", pfad
    assert "terminreihen//terminreihen" not in pfad
    assert pfad.count("/termine/regel") == 1


def test_n2_kurzform_pfad_bleibt():
    """Die Kurzform (`/termine/regel`) bleibt unveraendert."""
    from diakronos_app.planrahmen.dienste import DienstFehler
    from diakronos_app.planrahmen.engine.termine import TerminLimitUeberschritten

    exc = TerminLimitUeberschritten("zu viele Termine", "/termine/regel")
    fehler = DienstFehler.aus_terminlimit(exc)
    pfad = fehler.meldungen[0]["pfad"] if hasattr(fehler, "meldungen") else fehler.args[0][0]["pfad"]
    assert pfad == "/termine/regel"


def test_n2_ohne_reihe_faellt_auf_regel_zurueck():
    """Ohne Reihenangabe (Gesamtgrenze) gilt der allgemeine Regelpfad."""
    from diakronos_app.planrahmen.dienste import DienstFehler
    from diakronos_app.planrahmen.engine.termine import TerminLimitUeberschritten

    exc = TerminLimitUeberschritten("zu viele Termine")
    fehler = DienstFehler.aus_terminlimit(exc)
    pfad = fehler.meldungen[0]["pfad"] if hasattr(fehler, "meldungen") else fehler.args[0][0]["pfad"]
    assert pfad == "/termine/regel"
