"""IPv6-Infrastruktur, ungueltiges XFF und gemeinsame Login/CalDAV-Regel."""

import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request

from diakronos_app import request_context as rc
from diakronos_app.frappe_compat import loginversuche as lv

EIGENE = [
    "::1", "fd77:9999::1", "fc77:9999::1", "fe80:9999::cafe", "febf:ffff::1", "::",
    "127.0.0.1", "10.1.2.3", "192.168.0.11", "169.254.1.1", "0.0.0.0",
    *[f"172.{n}.0.1" for n in range(16, 32)], "172.31.255.255",
    "::ffff:192.168.0.11", "fe80:9999::cafe%eth0",
]
FREMDE = [
    "2001:db8::1", "203.0.113.44", "198.51.100.7", "8.8.8.8",
    "172.15.255.255", "172.32.0.0", "fec0::1", "fbff::1", "0.1.2.3",
]
MUELL = ["kein-ip", ":", "999.999.999.999", "10.kein-ip", "unix:/tmp/app.sock"]


@pytest.mark.parametrize("ip", EIGENE)
def test_infrastruktur_wird_in_beiden_bereichen_nicht_gezaehlt(ip, fake_redis):
    assert lv._ist_eigene_adresse(ip)
    for bereich in lv.BEREICHE:
        for n in range(30):
            lv.pruefe_und_merke(f"ipv6-{bereich}-{n}@example.invalid", ip, bereich=bereich)
        assert lv._kennungen(None, ip, bereich) == []
        assert not lv.ist_gesperrt(None, ip)
    assert lv.zaehle_adressen_im_weg() == 0


@pytest.mark.parametrize("ip", FREMDE)
def test_fremde_adressen_bleiben_sperrbar(ip, fake_redis):
    assert not lv._ist_eigene_adresse(ip)
    for n in range(26):
        lv.pruefe_und_merke(f"ipv6-{n}@example.invalid", ip)
    assert lv.ist_gesperrt(None, ip)
    assert lv.ist_gesperrt(None, ip, bereich="caldav")


@pytest.mark.parametrize("ip", MUELL + [None, "", "   "])
def test_muell_ist_nicht_eigen_aber_bekommt_keinen_ip_key(ip, fake_redis):
    assert not lv._ist_eigene_adresse(ip)
    for n in range(30):
        lv.pruefe_und_merke(f"muell-{n}@example.invalid", ip)
    assert lv._kennungen(None, ip) == []
    assert not lv.ist_gesperrt(None, ip)


def test_ipv6_schreibweisen_teilen_eine_sperre(fake_redis):
    for n in range(26):
        lv.pruefe_und_merke(f"form-{n}@example.invalid", "2001:0db8:0:0:0:0:0:7")
    assert lv.ist_gesperrt(None, "2001:db8::7")
    assert lv._kennungen(None, "::ffff:8.8.8.8") == lv._kennungen(None, "8.8.8.8")
    assert lv.ist_gesperrt(None, "2001:db8::7%eth0")


@pytest.mark.parametrize("proxy", [False, True])
@pytest.mark.parametrize("xff", ["kein-ip, 8.8.4.4", ":", "999.999.999.999"])
def test_header_keine_zweite_chance_und_konto_bleibt_geschuetzt(proxy, xff, fake_redis, monkeypatch):
    monkeypatch.setattr(lv.settings, "behind_proxy", proxy)
    rc.set_request(Request({"type": "http", "client": ("fd77:9999::1", 1234),
                            "headers": [(b"x-forwarded-for", xff.encode())]}))
    try:
        assert rc.zaehler_client_ip() == "fd77:9999::1"
        for _ in range(6):
            lv.pruefe_und_merke("fallback-konto@example.invalid", rc.zaehler_client_ip())
        assert lv.ist_gesperrt("fallback-konto@example.invalid", None)
        assert not lv.ist_gesperrt(None, "fd77:9999::1")
    finally:
        rc.clear_request()


@pytest.mark.parametrize("proxy", [False, True])
def test_gueltiges_xff_nur_mit_proxy(proxy, monkeypatch):
    monkeypatch.setattr(lv.settings, "behind_proxy", proxy)
    rc.set_request(Request({"type": "http", "client": ("8.8.8.8", 1234),
                            "headers": [(b"x-forwarded-for", b"2001:0DB8::7, fd77:9999::1")]}))
    try:
        assert rc.zaehler_client_ip() == ("2001:db8::7" if proxy else "8.8.8.8")
    finally:
        rc.clear_request()


@pytest.mark.parametrize("ip", ["::1", "fd77:9999::1", "fe80:9999::cafe", "::"])
def test_escape_hatch_und_kontosperre(ip, fake_redis, monkeypatch):
    for _ in range(6):
        lv.pruefe_und_merke("konto@example.invalid", ip)
    assert lv.ist_gesperrt("konto@example.invalid", None)
    assert not lv.ist_gesperrt(None, ip)
    monkeypatch.setattr(lv.settings, "login_ip_sperre_auch_privat", True)
    assert not lv._ist_eigene_adresse(ip)
    for n in range(26):
        lv.pruefe_und_merke(f"escape-{n}@example.invalid", ip)
    assert lv.ist_gesperrt(None, ip)


@pytest.mark.parametrize("xff", MUELL)
def test_muell_xff_nutzt_echte_adresse_nicht_neue_kennung(xff, fake_redis, monkeypatch):
    monkeypatch.setattr(lv.settings, "behind_proxy", True)
    request = Request({"type": "http", "client": ("8.8.8.8", 1234),
                       "headers": [(b"x-forwarded-for", xff.encode())]})
    rc.set_request(request)
    try:
        assert rc.zaehler_client_ip() == "8.8.8.8"
        for n in range(26):
            lv.pruefe_und_merke(f"fallback-{n}@example.invalid", rc.zaehler_client_ip())
        assert lv.ist_gesperrt(None, "8.8.8.8")
        assert lv._kennungen(None, xff) == []
    finally:
        rc.clear_request()


@pytest.mark.parametrize("bereich", ["login", "caldav"])
@pytest.mark.parametrize("xff", ["fd77:9999::1", "2001:db8::7", *MUELL[:3]])
def test_http_beide_zugaenge(xff, bereich, patched_db, fake_redis, monkeypatch):
    from diakronos_app.main import app

    monkeypatch.setattr(lv.settings, "behind_proxy", True)
    with TestClient(app, client=("fd77:9999::2", 50000)) as client:
        for n in range(30):
            user = f"http-{bereich}-{n}@example.invalid"
            if bereich == "login":
                response = client.post("/api/method/login", json={"usr": user, "pwd": "falsch"},
                                       headers={"X-Forwarded-For": xff})
            else:
                response = client.request("PROPFIND", "/dav/", auth=(user, "falsch"),
                                          headers={"X-Forwarded-For": xff})
            assert response.status_code == 401
    assert lv.ist_gesperrt(None, xff) == (xff == "2001:db8::7")
    if xff != "2001:db8::7":
        assert lv._kennungen(None, xff) == []
        assert not fake_redis.exists(f"{lv.SPERRE_PRAEFIX}ip:{lv._hash(xff)}")
        assert not fake_redis.exists(f"{lv._zaehler_praefix(bereich)}ip:{lv._hash(xff)}")


@pytest.mark.parametrize("bereich", ["login", "caldav"])
@pytest.mark.parametrize("xff", MUELL[:3])
def test_http_muell_header_umgeht_peer_sperre_nicht(xff, bereich, patched_db, fake_redis, monkeypatch):
    from diakronos_app.main import app

    peer = "203.0.113.90"
    monkeypatch.setattr(lv.settings, "behind_proxy", True)
    with TestClient(app, client=(peer, 50000)) as client:
        for n in range(30):
            user = f"fallback-http-{bereich}-{n}@example.invalid"
            if bereich == "login":
                response = client.post("/api/method/login", json={"usr": user, "pwd": "falsch"},
                                       headers={"X-Forwarded-For": xff})
            else:
                response = client.request("PROPFIND", "/dav/", auth=(user, "falsch"),
                                          headers={"X-Forwarded-For": xff})
            assert response.status_code == 401
    assert lv.ist_gesperrt(None, peer)
    assert lv.ist_gesperrt(None, peer, bereich="caldav" if bereich == "login" else "login")
    assert not fake_redis.exists(f"{lv.SPERRE_PRAEFIX}ip:{lv._hash(xff)}")
    assert not fake_redis.exists(f"{lv._zaehler_praefix(bereich)}ip:{lv._hash(xff)}")
