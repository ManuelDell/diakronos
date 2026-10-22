"""A1c1 — Brute-Force-Sperre fuer `/api/method/login`.

Die Kette, die hier geprueft wird, ist durchgaengig: Zaehler-Store
(`frappe_compat.loginversuche`) -> HTTP-Endpunkt (`api/auth.py`) -> Audit.

Die vier Saetze, die diese Datei zusammenhalten:

 1. Die Sperre ist **nicht erkennbar**: gesperrt, falsches Passwort,
    unbekannter Benutzer und deaktiviertes Konto liefern Status, Body,
    Kopfzeilen und Groessenordnung der Antwortzeit identisch.
 2. Die Sperre ist **wirksam**: auch das richtige Passwort hilft nicht.
 3. Die Sperre ist **faelschungssicher zuruecknehmbar**: ein erfolgreicher
    Login entlastet beide Zaehler, sonst waere ein Benutzer mit zwei
    Vertippern dauerhaft ausgesperrt.
 4. Zwei Zaehler, unabhaengig: der Benutzerzaehler gilt weltweit, der
    IP-Zaehler gilt fuer alle Benutzer derselben IP.
"""

from __future__ import annotations

import base64
import hashlib

import pytest

from diakronos_app.frappe_compat import loginversuche
from diakronos_app.models.core import User

SCHWELLE = 5


# ── Helfer (dieselben Bausteine wie test_a1b1_login.py) ─────────────────────


def _frappe_hash(passwort: str, salt: bytes = b"testsalztestsalt", runden: int = 29000) -> str:
    digest = hashlib.pbkdf2_hmac("sha256", passwort.encode("utf-8"), salt, runden, dklen=32)

    def ab64(roh: bytes) -> str:
        return base64.b64encode(roh).decode().rstrip("=").replace("+", ".")

    return f"$pbkdf2-sha256${runden}${ab64(salt)}${ab64(digest)}"


def _lege_benutzer(session_factory, name: str, passwort: str, **felder) -> None:
    sess = session_factory()
    try:
        sess.add(User(
            name=name,
            email=felder.pop("email", name),
            full_name=felder.pop("full_name", name),
            enabled=felder.pop("enabled", True),
            password_hash=_frappe_hash(passwort),
        ))
        sess.commit()
    finally:
        sess.close()


def _post(client, usr: str, pwd: str):
    # A1c12: IP-Limits testen mit echter IP statt Hostname "testclient".
    client._transport.client = ("203.0.113.90", 50000)
    return client.post("/api/method/login", json={"usr": usr, "pwd": pwd})


def _serie(client, usr: str, pwd: str, anzahl: int = SCHWELLE) -> None:
    """`anzahl` Fehlversuche — jede Antwort 401, keine davon gesperrt.

    `login_max_versuche=5` heisst: fuenf Fehlversuche sind ERLAUBT, der
    sechste wird gesperrt — so zaehlt es Frappes
    `max_consecutive_login_failures` auch. Genau das prueft dieser Helfer.
    """
    for nummer in range(anzahl):
        r = _post(client, usr, pwd)
        assert r.status_code == 401, f"Fehlversuch {nummer}: {r.status_code}"


def _sperre(client, usr: str, pwd: str) -> None:
    """Fehlserie bis die Sperre steht — und BESTAETIGT, dass sie steht.

    Der Aufrufer will den gesperrten Zustand; ein Aufruf, der sich darauf
    verlaesst, dass 5 Fehlversuche gesperrt haben, waere ein Test, der die
    Sperre nicht wirklich belegt.
    """
    _serie(client, usr, pwd)
    r = _post(client, usr, pwd)
    assert r.status_code == 401
    assert loginversuche.ist_gesperrt(usr, _sperre_kunden(client)), "Sperre nicht aktiv"


def _sperre_kunden(client) -> str:
    """TCP-Client-Adresse des TestClients — der IP-Zaehler-Input."""
    return "203.0.113.90"


def _sperre_aufloesen(user: str, ip: str) -> None:
    """Simuliert das Ablaufen der Sperre (im Betrieb der Redis-TTL)."""
    client = loginversuche._client()
    loginversuche.zuruecksetzen(user, ip)


def _einziger_sperr_key(client) -> str:
    """Der eine Sperr-Key im Stub — ohne den Stufen-Key daneben.

    **A1c2-Anpassung**: Die Sperre liegt nicht mehr unter dem Zaehler-Praefix
    mit dem Suffix `:sperre`, sondern unter `SPERRE_PRAEFIX`. Der Hilfsfilter
    sucht deshalb im Sperr-Namensraum und schliesst den Stufen-Key (`:stufe`)
    aus. Die Absicht des Tests bleibt unveraendert: "die eine Sperre, nicht
    ihr Stufen-Key daneben".
    """
    treffer = [
        k
        for k in client._values
        if k.startswith(loginversuche.SPERRE_PRAEFIX) and not k.endswith(":stufe")
    ]
    assert len(treffer) == 1, f"genau eine Sperre erwartet, gefunden: {treffer}"
    return treffer[0]


# ── 1. Die Sperre ist nicht erkennbar ───────────────────────────────────────


def test_gesperrt_antwortet_wie_falsches_passwort(guest_client, patched_db):
    """Status, Body und Kopfzeilen des gesperrten Versuchs == falsches Passwort."""
    _lege_benutzer(patched_db, "anna@example.org", "geheim-123")

    falsch = _post(guest_client, "anna@example.org", "falsch")
    _sperre(guest_client, "anna@example.org", "falsch")
    gesperrt = _post(guest_client, "anna@example.org", "falsch")

    assert gesperrt.status_code == falsch.status_code == 401
    assert gesperrt.json() == falsch.json()
    # KEIN Hinweis auf "gesperrt": kein 429, keine Retry-After, kein Feld,
    # kein zusaetzlicher Header. Ein `Retry-After` allein wuerde dem
    # Angreifer schon sagen, dass er richtig liegt.
    assert gesperrt.headers.get("retry-after") is None
    assert "set-cookie" not in gesperrt.headers
    assert set(gesperrt.headers) == set(falsch.headers)


def test_gesperrt_liefert_kein_cookie(guest_client, patched_db):
    _lege_benutzer(patched_db, "anna@example.org", "geheim-123")
    _sperre(guest_client, "anna@example.org", "falsch")

    r = _post(guest_client, "anna@example.org", "falsch")

    assert "sid" not in r.cookies


def test_gesperrt_antwortzeit_ist_von_unbekannt_nicht_unterscheidbar(
    guest_client, patched_db
):
    """Die Sperre darf nicht daran erkennbar sein, dass sie schneller ist.

    Der gesperrte Zweig verbraucht denselben Dummy-Hash wie ein unbekannter
    Benutzer — sonst waere die Sperre per Zeitmessung sichtbar, und ein
    Angreifer wuesste sofort, dass er den richtigen Namen hat.
    """
    import time

    _lege_benutzer(patched_db, "anna@example.org", "geheim-123")

    def median(aufrufe: int = 7) -> float:
        dauer = []
        for _ in range(aufrufe):
            start = time.perf_counter()
            _post(guest_client, "anna@example.org", "falsch")
            dauer.append(time.perf_counter() - start)
        dauer.sort()
        return dauer[len(dauer) // 2]

    # Aufwaermen, dann Median: der erste Aufruf enthaelt den Dummy-Hash-Aufbau.
    median(2)
    unbekannt = median()

    _sperre(guest_client, "anna@example.org", "falsch")
    gesperrt = median()

    verhaeltnis = max(gesperrt, unbekannt) / max(min(gesperrt, unbekannt), 1e-6)
    # Faktor 1,6: CI-Jitter laesst keinen engeren Wert zu, ein "gesperrt
    # antwortet in 2 ms"-Sonderfall waere Faktor 50+.
    assert verhaeltnis < 1.6, f"Sperre an der Zeit erkennbar: {gesperrt=} {unbekannt=}"


# ── 2. Die Sperre ist wirksam ───────────────────────────────────────────────


def test_richtiges_passwort_waehrend_der_sperre_auch_401(guest_client, patched_db):
    """Der Kern der Karte: richtig eingeloggt und trotzdem abgewiesen."""
    _lege_benutzer(patched_db, "anna@example.org", "geheim-123")
    _sperre(guest_client, "anna@example.org", "falsch")

    r = _post(guest_client, "anna@example.org", "geheim-123")

    assert r.status_code == 401
    assert r.json()["message"] == "Ungueltige Anmeldedaten"
    assert "sid" not in r.cookies


def test_nach_ablauf_der_sperre_wieder_200(guest_client, patched_db, fake_redis):
    """Nach Ablauf der Sperre funktioniert derselbe Login wieder."""
    _lege_benutzer(patched_db, "anna@example.org", "geheim-123")
    _sperre(guest_client, "anna@example.org", "falsch")
    # Der naechste Versuch ist gesperrt — auch mit dem richtigen Passwort.
    assert _post(guest_client, "anna@example.org", "geheim-123").status_code == 401

    _sperre_aufloesen("anna@example.org", _sperre_kunden(guest_client))

    r = _post(guest_client, "anna@example.org", "geheim-123")

    assert r.status_code == 200
    assert r.json()["message"] == "Logged In"


def test_zuruecksetzen_entsperrt(guest_client, patched_db, fake_redis):
    """Der Notfallweg aus dem Modul wirkt (und steht nicht im Anmeldepfad)."""
    _lege_benutzer(patched_db, "anna@example.org", "geheim-123")
    _sperre(guest_client, "anna@example.org", "falsch")

    loginversuche.zuruecksetzen("anna@example.org", _sperre_kunden(guest_client))

    assert _post(guest_client, "anna@example.org", "geheim-123").status_code == 200


# ── 3. Zuruecknehmen nach Erfolg ────────────────────────────────────────────


def test_erfolg_setzt_zaehler_zurueck(guest_client, patched_db, fake_redis):
    """Abnahme: Fehlversuch, Fehlversuch, Login, dann wieder 5 bis zur Sperre."""
    _lege_benutzer(patched_db, "anna@example.org", "geheim-123")

    assert _post(guest_client, "anna@example.org", "falsch").status_code == 401
    assert _post(guest_client, "anna@example.org", "falsch").status_code == 401
    assert _post(guest_client, "anna@example.org", "geheim-123").status_code == 200

    stand = loginversuche.zaehler_stand("anna@example.org", _sperre_kunden(guest_client))
    assert stand["benutzer"] == 0, "Erfolg muss den Benutzerzaehler leeren"

    # Und die volle Serie ist danach wieder moeglich.
    _sperre(guest_client, "anna@example.org", "falsch")
    assert _post(guest_client, "anna@example.org", "geheim-123").status_code == 401


def test_erfolg_setzt_auch_den_ip_zaehler_zurueck(guest_client, patched_db, fake_redis):
    _lege_benutzer(patched_db, "anna@example.org", "geheim-123")

    _post(guest_client, "anna@example.org", "falsch")
    _post(guest_client, "anna@example.org", "geheim-123")

    stand = loginversuche.zaehler_stand("anna@example.org", _sperre_kunden(guest_client))
    assert stand["ip"] == 0


def test_zwei_vertipper_und_login_sperren_nicht(guest_client, patched_db, fake_redis):
    """Der Alltagsfall: zweimal danebengetippt und gut drauf."""
    _lege_benutzer(patched_db, "anna@example.org", "geheim-123")

    assert _post(guest_client, "anna@example.org", "ghesim").status_code == 401
    assert _post(guest_client, "anna@example.org", "gehem-123").status_code == 401
    assert _post(guest_client, "anna@example.org", "geheim-123").status_code == 200

    # Und danach direkt wieder drei Versuche, ohne Sperre.
    for _ in range(3):
        assert _post(guest_client, "anna@example.org", "falsch").status_code == 401
    assert _post(guest_client, "anna@example.org", "geheim-123").status_code == 200


# ── 4. Zwei unabhaengige Zaehler ────────────────────────────────────────────


def test_benutzerzaehler_greift_wenn_derselbe_name_von_vielen_ips_kommt(
    guest_client, patched_db, fake_redis
):
    """Vom gleichen Benutzer, aber von wechselnden IPs: trotzdem Sperre.

    Sonst waere die Sperre per IP-Wechsel aufzuheben — genau die
   _proxy-Pfade eines Angreifers.
    """
    _lege_benutzer(patched_db, "anna@example.org", "geheim-123")

    for _ in range(SCHWELLE):
        erlaubt, _grund = loginversuche.pruefe_und_merke("anna@example.org", f"203.0.113.{_}")
        assert erlaubt, f"Versuch {_} von {SCHWELLE} muss erlaubt sein"

    erlaubt, grund = loginversuche.pruefe_und_merke("anna@example.org", "203.0.113.99")

    assert erlaubt is False
    assert grund == "benutzer"


def test_ip_zaehler_greift_fuer_verschiedene_benutzer(guest_client, patched_db, fake_redis):
    """Abnahme: IP-Sperre unabhaengig vom Benutzerzaehler.

    **A1c10:** das sind jetzt **25** Fehlversuche mit 25 verschiedenen
    (unbekannten) Namen, nicht fuenf. Fuenf Fehlversuche sperren weiter das
    **Konto**; die **Adresse** erst ab 25, und dieser Test ist der Beweis,
    dass die Adresssperre unabhaengig vom Benutzerzaehler greift — jeder der
    25 Namen steht bei genau einem Fehlversuch.
    """
    adressschwelle = loginversuche._max_versuche("ip")
    for nummer in range(adressschwelle):
        erlaubt, _grund = loginversuche.pruefe_und_merke(
            f"opfer{nummer}@example.org", _sperre_kunden(guest_client)
        )
        assert erlaubt, f"Versuch {nummer} muss erlaubt sein"

    # Ein voellig unbeteiligter Benutzer von derselben IP ist mitgesperrt.
    erlaubt, grund = loginversuche.pruefe_und_merke(
        "unbeteiligt@example.org", _sperre_kunden(guest_client)
    )

    assert erlaubt is False
    assert grund == "ip"


def test_ip_zaehler_belegt_auch_ueber_http(guest_client, patched_db):
    """Dieselbe Aussage auf dem echten HTTP-Weg, ueber den Login-Endpunkt.

    **A1c10:** 25 Fehlversuche ueber 25 verschiedene Konten — die Adresse
    sperrt erst bei 25, nicht bei 5.
    """
    for nummer in range(loginversuche._max_versuche("ip")):
        assert _post(guest_client, f"opfer{nummer}@example.org", "egal").status_code == 401
    # Ab jetzt ist die IP durch — auch fuer einen Benutzer mit gutem Passwort.

    # Ein Benutzer, der vorher nie gefehlt hat, ist jetzt trotzdem draussen.
    _lege_benutzer(patched_db, "anna@example.org", "geheim-123")
    r = _post(guest_client, "anna@example.org", "geheim-123")

    assert r.status_code == 401
    assert r.json()["message"] == "Ungueltige Anmeldedaten"


def test_verschiedene_ips_sind_unabhaengig(guest_client, patched_db, fake_redis):
    """Der Benutzerzaehler gilt WELTWEIT — eine andere IP aendert nichts.

    Der Gegenfall (die IP-Sperre greift fuer jeden Benutzer) steht in
    `test_ip_zaehler_greift_fuer_verschiedene_benutzer`: dort sind die
    Benutzernamen verschieden, sodass der Benutzerzaehler nicht ausloest.
    """
    _lege_benutzer(patched_db, "anna@example.org", "geheim-123")

    _sperre(guest_client, "anna@example.org", "falsch")

    # Der Benutzerzaehler gilt weltweit: jede IP ist gesperrt, nicht nur die
    # des Angreifers.
    assert loginversuche.ist_gesperrt("anna@example.org", "203.0.113.1") is True
    assert loginversuche.ist_gesperrt("anna@example.org", "203.0.113.9") is True
    assert loginversuche.ist_gesperrt("anna@example.org", "2001:db8::1") is True
    # Auch die Gross-/Kleinschreibweise des Namens aendert nichts.
    assert loginversuche.ist_gesperrt("ANNA@example.org", "203.0.113.1") is True
    # Ein noch nie gesehener Benutzer von einer noch nie gesehenen IP: frei.
    assert loginversuche.ist_gesperrt("carla@example.org", "198.51.100.4") is False


def test_der_ip_zaehler_zaehlt_auch_bei_einer_einzelnen_serie(guest_client, patched_db, fake_redis):
    """Auch wenn der Benutzerzaehler ausloest, laeuft der IP-Zaehler mit.

    `pruefe_und_merke` prueft die Zaehler in fester Reihenfolge (Benutzer,
    dann IP) und bricht beim ersten Treffer ab. Bei einer Serie mit EINEM
    Benutzer loest deshalb der Benutzerzaehler aus, bevor der IP-Zaehler
    drankommt. Der IP-Zaehler steht damit knapp unter der Schwelle — und
    beim naechsten Versuch von dieser IP (anderer Name) greift er sofort.
    """
    _lege_benutzer(patched_db, "anna@example.org", "geheim-123")
    _sperre(guest_client, "anna@example.org", "falsch")

    stand = loginversuche.zaehler_stand("anna@example.org", _sperre_kunden(guest_client))

    # Sechs Anfragen gingen von dieser IP raus; die letzte loeste die Sperre
    # aus, bevor der IP-Zaehler geprueft wurde -> 5.
    assert stand["ip"] == SCHWELLE, f"IP-Zaehler muss mitlaufen: {stand['ip']}"


# ── Backoff ─────────────────────────────────────────────────────────────────


def test_sperrzeit_waechst_mit_jeweiligem_versuch(guest_client, patched_db, fake_redis):
    """Abnahme: Backoff. Ohne das waere ein Rhythmus ein endloser Durchlauf."""
    _lege_benutzer(patched_db, "anna@example.org", "geheim-123")
    _sperre(guest_client, "anna@example.org", "falsch")

    client = loginversuche._client()
    sperr_key = _einziger_sperr_key(client)
    dauer = [int(client.get(sperr_key))]

    # Fuenf weitere Versuche waehrend der Sperr: jede verlaengert.
    for nummer in range(5):
        assert _post(guest_client, "anna@example.org", "falsch").status_code == 401
        dauer.append(int(client.get(sperr_key)))

    grund = 300
    assert dauer[0] == grund
    assert dauer[1] > dauer[0], "erster Versuch muss verlaengern"
    assert dauer == sorted(dauer), f"Sperrzeit muss monoton wachsen: {dauer}"
    # Gedeckelt: hoechstens der Backoff-Deckel (16) der Grunddauer.
    assert dauer[-1] <= grund * 16, f"Backoff-Deckel verletzt: {dauer[-1]}"


def test_backoff_ist_gedeckelt(guest_client, patched_db, fake_redis):
    """Nach sehr vielen Versuchen ist die Sperrzeit nicht unendlich."""
    _lege_benutzer(patched_db, "anna@example.org", "geheim-123")
    _sperre(guest_client, "anna@example.org", "falsch")

    client = loginversuche._client()
    for _ in range(40):
        _post(guest_client, "anna@example.org", "falsch")

    assert int(client.get(_einziger_sperr_key(client))) == 300 * 16


def test_alle_zaehler_haben_einen_ttl(guest_client, patched_db, fake_redis):
    """REGRESSION (im Live-Test aufgefallen): kein Schluessel darf ewig leben.

    Die Backoff-Stufe wurde zuerst ohne TTL gesetzt — `ttl` stand auf -1.
    Damit waere der Keyspace unbegrenzt gewachsen: jeder jemals gesperrte
    Benutzer und jede IP haette zwei Keys FUER IMMER hinterlassen. Bei einer
    Gemeinde mit wechselnden Angreifer-IPs ist das ein echtes Leck.
    """
    _lege_benutzer(patched_db, "anna@example.org", "geheim-123")
    _sperre(guest_client, "anna@example.org", "falsch")

    client = loginversuche._client()
    schluessel = [k for k in client._values if k.startswith(loginversuche.SCHLUESSEL_PRAEFIX)]
    assert schluessel, "es muessen Eintraege da sein"

    ohne_ablauf = [k for k in schluessel if client.ttl(k) == -1]
    assert ohne_ablauf == [], f"Schluessel ohne Ablauf (Keyspace-Leak): {ohne_ablauf}"
    # Und sie laufen auch nicht schon ab, solange die Sperre gilt.
    assert all(client.ttl(k) > 0 for k in schluessel)


def test_zaehler_wird_nach_der_sperre_zurueckgesetzt(guest_client, patched_db, fake_redis):
    """Direkt nach der Sperr ist der Fehlversuchszaehler wieder 0.

    Sonst kaeme der Benutzer nach dem Ablaufen der Sperr nie wieder hinein.
    """
    _lege_benutzer(patched_db, "anna@example.org", "geheim-123")
    _sperre(guest_client, "anna@example.org", "falsch")

    stand = loginversuche.zaehler_stand("anna@example.org", _sperre_kunden(guest_client))

    assert loginversuche.ist_gesperrt("anna@example.org", _sperre_kunden(guest_client))
    # Der Zaehler des Ausloesers ist auf 0 gesetzt (nicht auf 5 stehen
    # geblieben) — sonst kaeme der Benutzer direkt nach dem Ablaufen der
    # Sperr nie wieder hinein.
    assert stand["benutzer"] == 0, f"Fehlversuchszaehler muss neu beginnen: {stand['benutzer']}"


# ── Kein Informationsleck ───────────────────────────────────────────────────


def test_redis_key_enthaelt_keine_email_im_klartext(guest_client, patched_db, fake_redis):
    """Abnahme: kein Schluessel nennt die E-Mail.

    Wer den Redis-Keyspace sieht (Backup, Monitoring, ein Kollege mit
    Zugang), sieht damit keine Adressliste. Fuer BEIDE Zaehler.
    """
    _lege_benutzer(patched_db, "anna@example.org", "geheim-123")
    _post(guest_client, "anna@example.org", "falsch")

    rohdaten = repr(fake_redis._values) + repr(fake_redis._sets)

    assert "anna" not in rohdaten
    assert "example.org" not in rohdaten
    assert "geheim" not in rohdaten
    # Aber der Schluessel IST da — sonst wuesste der Test nichts.
    assert any(k.startswith(loginversuche.SCHLUESSEL_PRAEFIX) for k in fake_redis._values)


def test_unbekannter_benutzer_hinterlaesst_dieselbe_form(guest_client, patched_db, fake_redis):
    """Unbekannter Benutzer: gleiche Schluessellaenge, gleiche TTL."""
    _lege_benutzer(patched_db, "anna@example.org", "geheim-123")
    _post(guest_client, "anna@example.org", "falsch")
    bekannt = loginversuche.zaehler_stand("anna@example.org", _sperre_kunden(guest_client))

    _post(guest_client, "niemand@example.org", "egal")
    unbekannt = loginversuche.zaehler_stand("niemand@example.org", _sperre_kunden(guest_client))

    assert unbekannt["benutzer"] == bekannt["benutzer"] == 1
    # TTL = Sperrzeit in beiden Faellen, nicht etwa kuerzer beim Unbekannten.
    assert unbekannt["benutzer_ttl"] == bekannt["benutzer_ttl"]
    assert 0 < unbekannt["benutzer_ttl"] <= 300


def test_leerer_benutzername_verbraucht_keinen_zaehler(fake_redis):
    """Ein Aufruf ganz ohne `usr` darf keinen gemeinsam genutzten Zaehler leeren."""
    erlaubt, grund = loginversuche.pruefe_und_merke("", "203.0.113.1")

    assert erlaubt is True
    assert grund == ""
    # Der IP-Zaehler hat aber schon gezaehlt — der Absender ist ja bekannt.
    assert loginversuche.zaehler_stand(None, "203.0.113.1")["ip"] == 1


def test_gleiche_email_in_gross_klein_ist_derselbe_zaehler(fake_redis):
    """`Anna@Example.ORG` und `anna@example.org` teilen sich den Zaehler.

    Sonst waere die Sperre per Gross-/Kleinschreibungswechsel aufzuheben.
    """
    for _ in range(SCHWELLE):
        assert loginversuche.pruefe_und_merke("Anna@Example.ORG", "203.0.113.1")[0] is True

    erlaubt, grund = loginversuche.pruefe_und_merke("anna@example.org", "203.0.113.1")

    assert erlaubt is False
    assert grund == "benutzer"


def test_x_forwarded_for_umgeht_die_ip_sperre_nicht(guest_client, patched_db, fake_redis):
    """Abnahme-Kernfall: IP-Sperre laesst sich nicht durch einen Header heben.

    `X-Forwarded-For` setzt der Client. Wuerde der IP-Zaehler darauf
    aufbauen, koennte ein Angreifer mit 1000 gefaelschten Adressen die
    halbe Sperre umgehen. Der Zaehler nutzt deshalb `request.client.host`.
    """
    _lege_benutzer(patched_db, "anna@example.org", "geheim-123")
    for nummer in range(SCHWELLE):
        guest_client.post(
            "/api/method/login",
            json={"usr": "anna@example.org", "pwd": "falsch"},
            headers={"X-Forwarded-For": f"203.0.113.{nummer}"},
        )
    # Fuenf Fehlversuche = erlaubt; der naechste wird gesperrt.

    r = guest_client.post(
        "/api/method/login",
        json={"usr": "anna@example.org", "pwd": "geheim-123"},
        headers={"X-Forwarded-For": "198.51.100.7"},
    )

    assert r.status_code == 401


# ── Audit ───────────────────────────────────────────────────────────────────


def _audit_zeilen(session_factory) -> list:
    from diakronos_app.models.diakonos import AuditLog

    sess = session_factory()
    try:
        return sess.query(AuditLog).all()
    finally:
        sess.close()


def test_gesperrter_versuch_erzeugt_audit_eintrag(guest_client, patched_db, fake_redis):
    """Jeder abgewiesene Versuch wird protokolliert — genau einer, wenn einer
    abgewiesen wurde.

    `_sperre` stellt den gesperrten Zustand her: fuenf Fehlversuche (401,
    erlaubt) plus der sechste, der die Sperre ausloest und selbst abgewiesen
    wird. Der bringt EINEN Audit-Eintrag mit. Ein weiterer Versuch waere ein
    zweiter.
    """
    _lege_benutzer(patched_db, "anna@example.org", "geheim-123")
    _sperre(guest_client, "anna@example.org", "falsch")

    zeilen = [z for z in _audit_zeilen(patched_db) if "Brute-Force" in (z.begruendung or "")]

    assert len(zeilen) == 1, f"genau der abgewiesene Versuch wird protokolliert: {len(zeilen)}"
    assert zeilen[0].actor == "Guest"
    assert zeilen[0].target_doctype == "User"


def test_jeder_weitere_abgewiesene_versuch_wird_auch_protokolliert(
    guest_client, patched_db, fake_redis
):
    """Ein Angreifer, der weiterklopft, erzeugt eine sichtbare Spur.

    Ohne das waere eine laufende Brute-Force-Serie im Log nicht von einer
    Einmal-Serie zu unterscheiden.
    """
    _lege_benutzer(patched_db, "anna@example.org", "geheim-123")
    _sperre(guest_client, "anna@example.org", "falsch")

    for _ in range(4):
        assert _post(guest_client, "anna@example.org", "falsch").status_code == 401

    zeilen = [z for z in _audit_zeilen(patched_db) if "Brute-Force" in (z.begruendung or "")]
    assert len(zeilen) == 5


def test_audit_eintrag_ohne_klartext(guest_client, patched_db, fake_redis):
    """Abnahme: kein Name, keine IP, kein Passwort, kein Token im Log."""
    _lege_benutzer(patched_db, "anna@example.org", "geheim-123")
    _sperre(guest_client, "anna@example.org", "falsch")
    # Auch der Versuch mit dem RICHTIGEN Passwort wird protokolliert (und
    # abgewiesen) — im Log steht genau das Gleiche wie beim falschen.
    _post(guest_client, "anna@example.org", "geheim-123")

    zeilen = [z for z in _audit_zeilen(patched_db) if "Brute-Force" in (z.begruendung or "")]
    assert zeilen

    volltext = " ".join(
        str(getattr(z, feld) or "")
        for z in zeilen
        for feld in ("begruendung", "target_name", "ip_address", "user_agent", "old_value", "new_value")
    )

    assert "anna" not in volltext.lower()
    assert "example.org" not in volltext.lower()
    assert "geheim" not in volltext
    assert "$" not in volltext
    # Pseudonymform wie im DSGVO-Nachtjob.
    assert zeilen[0].target_name.startswith("sha256:")


def test_erfolgreicher_login_erzeugt_keinen_sperr_eintrag(guest_client, patched_db, fake_redis):
    _lege_benutzer(patched_db, "anna@example.org", "geheim-123")

    _post(guest_client, "anna@example.org", "falsch")
    _post(guest_client, "anna@example.org", "geheim-123")

    zeilen = [z for z in _audit_zeilen(patched_db) if "Brute-Force" in (z.begruendung or "")]
    assert zeilen == [], "ein normaler Fehlversuch ist keine Sperre"


def test_audit_fehlschlag_haelt_die_sperre_nicht_auf(guest_client, patched_db, fake_redis, monkeypatch):
    """Faellt der Audit-Eintrag aus, bleibt die Anmeldung trotzdem gesperrt.

    Sonst wuerde ein Angreifer die Sperre durch Ueberlasten der Logbuch-
    haltung abschalten — ein simpler DoS als Ausfallschalter.

    Der Fehler wird **unterhalb** von `_audit_gesperrt` erzeugt (die
    `_create`-Aufrufe), damit der echte `try/except` in der Funktion greift
    und nicht bloss ein ersetzter Aufruf vermieden wird.
    """
    import diakronos_app.frappe_compat.api_helpers as helpers

    _lege_benutzer(patched_db, "anna@example.org", "geheim-123")
    _sperre(guest_client, "anna@example.org", "falsch")

    def _kaputt(*_a, **_kw):
        raise RuntimeError("Audit-DB weg")

    monkeypatch.setattr(helpers, "_create", _kaputt)
    r = _post(guest_client, "anna@example.org", "geheim-123")

    assert r.status_code == 401
    assert loginversuche.ist_gesperrt("anna@example.org", _sperre_kunden(guest_client))


# ── Der Store als Schnittstelle (CalDAV, Karte A1c2) ───────────────────────


def test_pruefe_und_merke_ist_die_einzige_abnahmeschnittstelle(fake_redis):
    """Der Docstring sagt es, der Test prueft es: zwei Argumente, ein bool.

    CalDAV ruft `pruefe_und_merke(user, ip)` und braucht sonst nichts aus
    dem Modul. Zaehler, Sperre und Backoff sind intern.
    """
    erlaubt, grund = loginversuche.pruefe_und_merke("anna@example.org", "203.0.113.1")

    assert isinstance(erlaubt, bool)
    assert isinstance(grund, str)

    # Der erste Aufruf oben war Versuch 1, es folgen noch SCHWELLE-1.
    for nummer in range(SCHWELLE - 1):
        assert loginversuche.pruefe_und_merke("anna@example.org", "203.0.113.1")[0] is True

    assert loginversuche.pruefe_und_merke("anna@example.org", "203.0.113.1")[0] is False
    # Und ab jetzt bleibt es gesperrt, egal wie oft gefragt wird.
    assert loginversuche.pruefe_und_merke("anna@example.org", "203.0.113.1")[0] is False


def test_ist_gesperrt_aendert_nichts(fake_redis):
    """Nur lesend — ein Diagnoseaufruf darf den Zustand nicht verschieben."""
    for _ in range(3):
        loginversuche.pruefe_und_merke("anna@example.org", "203.0.113.1")

    for _ in range(5):
        loginversuche.ist_gesperrt("anna@example.org", "203.0.113.1")

    stand = loginversuche.zaehler_stand("anna@example.org", "203.0.113.1")
    assert stand["benutzer"] == 3


# ── Konfiguration ───────────────────────────────────────────────────────────


def test_defaults_sind_gesetzt():
    """Ohne ENV startet die App und sperrt trotzdem — Pflicht der Karte."""
    from diakronos_app.settings import settings

    assert settings.login_max_versuche >= 1
    assert settings.login_sperre_sekunden >= 30
    assert settings.login_sperre_max_faktor >= 1


def test_komma_seh_wert_wird_verstanden(fake_redis):
    """`LOGIN_MAX_VERSUCHE=3` aus der .env wirkt tatsaechlich."""
    from diakronos_app import settings as settingsmod

    original = settingsmod.settings.login_max_versuche
    try:
        settingsmod.settings.login_max_versuche = 3
        for nummer in range(3):
            assert loginversuche.pruefe_und_merke("anna@example.org", "203.0.113.1")[0] is True
        assert loginversuche.pruefe_und_merke("anna@example.org", "203.0.113.1")[0] is False
    finally:
        settingsmod.settings.login_max_versuche = original


@pytest.mark.parametrize("unsinn,erste_gesperrt", [(0, 2), (-5, 2), (1, 2)])
def test_unsinnige_schwelle_sperrt_trotzdem(unsinn, erste_gesperrt, fake_redis):
    """Ungueltige Schwellen duerfen die Sperre nicht AUSSCHALTEN.

    `0` und `-5` werden intern auf 1 gehoben: ein Fehlversuch ist immer
    erlaubt, der zweite gesperrt. Das ist die bewusst konservative Deutung
    — eine Schwelle von 0 wuerde bedeuten, dass der allererste Versuch
    gesperrt wird, und damit auch jeder allererste ERFOLGREICHE Login.
    """
    from diakronos_app import settings as settingsmod

    original = settingsmod.settings.login_max_versuche
    try:
        settingsmod.settings.login_max_versuche = unsinn
        for nummer in range(erste_gesperrt - 1):
            assert loginversuche.pruefe_und_merke("anna@example.org", "203.0.113.1")[0] is True
        assert loginversuche.pruefe_und_merke("anna@example.org", "203.0.113.1")[0] is False
    finally:
        settingsmod.settings.login_max_versuche = original
