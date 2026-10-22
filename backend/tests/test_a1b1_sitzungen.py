"""A1b1 — Sitzungs-Store (`frappe_compat/sitzungen.py`) gegen den Redis-Stub.

Deckt die vom Kartentext geforderten fuenf Operationen ab:
anlegen, lesen, verlaengern, loeschen, loesche_alle_von.
"""

from __future__ import annotations

import time

from diakronos_app.frappe_compat import sitzungen


def test_sid_und_csrf_sind_56_hex(fake_redis):
    """`secrets.token_hex(28)` -> 56 Hex-Zeichen, wie `frappe.generate_hash()`."""
    sid, csrf = sitzungen.anlegen("anna@example.org")

    assert len(sid) == 56
    assert len(csrf) == 56
    assert all(c in "0123456789abcdef" for c in sid)
    # Zwei getrennte Zufallswerte — niemals derselbe Token.
    assert sid != csrf


def test_anlegen_und_lesen(fake_redis):
    sid, csrf = sitzungen.anlegen("anna@example.org")

    daten = sitzungen.lesen(sid)

    assert daten is not None
    assert daten["user"] == "anna@example.org"
    assert daten["csrf_token"] == csrf
    # Genau der erwartete Schluesselraum (eigener Praefix).
    assert fake_redis.get(f"{sitzungen.SCHLUESSEL_PRAEFIX}{sid}") is not None


def test_lesen_unbekannt_ist_none(fake_redis):
    assert sitzungen.lesen("a" * 56) is None
    assert sitzungen.lesen("") is None


def test_sitzungen_sind_eindeutig(fake_redis):
    s1, _ = sitzungen.anlegen("anna@example.org")
    s2, _ = sitzungen.anlegen("anna@example.org")

    assert s1 != s2
    assert sitzungen.lesen(s1)["user"] == "anna@example.org"
    assert sitzungen.lesen(s2)["user"] == "anna@example.org"


def test_verlaengern_ueberlebt_die_urspruengliche_ttl(fake_redis, monkeypatch):
    """Verlaengern setzt die TTL neu — mit stark verkuerzter Probe-TTL messbar."""
    from diakronos_app import settings as settings_mod

    monkeypatch.setattr(settings_mod.settings, "session_ttl_seconds", 1)

    sid, _ = sitzungen.anlegen("anna@example.org")
    # Kurz warten, dann verlaengern: der Eintrag muss danach wieder ~1s leben.
    time.sleep(0.6)
    assert sitzungen.verlaengern(sid) is True
    time.sleep(0.6)
    # Ohne das Verlaengern waere er jetzt weg (1.2s > 1s).
    assert sitzungen.lesen(sid) is not None


def test_verlaengern_unbekannt_ist_false(fake_redis):
    assert sitzungen.verlaengern("b" * 56) is False


def test_loeschen_macht_sid_ungueltig(fake_redis):
    sid, _ = sitzungen.anlegen("anna@example.org")
    assert sitzungen.lesen(sid) is not None

    assert sitzungen.loeschen(sid) is True
    assert sitzungen.lesen(sid) is None
    # Zweites Loeschen ist kein Treffer mehr.
    assert sitzungen.loeschen(sid) is False


def test_loeschen_raeumt_den_benutzerindex(fake_redis):
    sid, _ = sitzungen.anlegen("anna@example.org")

    sitzungen.loeschen(sid)

    assert sid not in fake_redis.smembers(sitzungen.benutzer_index_key("anna@example.org"))


def test_loesche_alle_von_trifft_nur_diesen_benutzer(fake_redis):
    a1, _ = sitzungen.anlegen("anna@example.org")
    a2, _ = sitzungen.anlegen("anna@example.org")
    b1, _ = sitzungen.anlegen("bruno@example.org")

    geloescht = sitzungen.loesche_alle_von("anna@example.org")

    assert geloescht == 2
    assert sitzungen.lesen(a1) is None
    assert sitzungen.lesen(a2) is None
    # Bruno bleibt angemeldet.
    assert sitzungen.lesen(b1) is not None


def test_loesche_alle_von_ohne_sitzungen(fake_redis):
    assert sitzungen.loesche_alle_von("niemand@example.org") == 0
