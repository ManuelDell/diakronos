"""SEC-2 — Sperre wirkt, und sie sperrt nicht dauerhaft (Pentest-Befund 3).

BEFUND (Pentest 2026-10-29, MITTEL): 27 Fehlversuche auf
`POST /api/method/login` ohne jede Bremse, konstante Antwortzeit.

WAS AM CODE FALSCH WAR — und was nicht
--------------------------------------
Die Bremse war **eingehaengt** (`api/auth.py::login` ruft
`loginversuche.pruefe_und_merke`). Sie war aber nach einer Handvoll
Versuche **nicht mehr zu beenden**:

1. `_setze_sperre()` rief `_erhoehe_stufe()` **und danach**
   `_sperr_dauer()` — die Stufe wurde also schon fuer die *erste* Sperre
   gelesen. Die erste Sperre war damit nicht `login_sperre_sekunden`
   (300 s), sondern 60 s.
2. `_verlaengere_sperre()` las die Stufe, setzte die Dauer und erhoehte sie
   danach. Jeder einzelne Versuch waehrend einer Sperre verdoppelte die
   naechste Dauer, solange bis sie den Deckel
   `login_sperre_sekunden * login_sperre_max_faktor` (16) erreichte.
   Danach blieb sie dort — auf **jeden** weiteren Versuch erneut gesetzt.

Ein Skript, das 30-mal durchprobiert (genau das, was ein Pentest tut),
hinterlaesst deshalb ein Konto, das 80 Minuten gesperrt ist, und ein
15-Minuten-Testfenster sieht nur 401er ohne jede sichtbare Bremse. Im
Betrieb ist das der schlimmere Fehler: **eine Sperre, die sich nicht mehr
abschaltet, ist ein Ausfall, kein Schutz** — und bei `angegriffenem` Konto
trifft er den Menschen, der sich vertippt hat, nicht den Angreifer.

Die Stufe ist jetzt **Backoff innerhalb einer Fehlserie**:

  * sie waechst erst, wenn die Sperre nach dem Fehlversuch *gesetzt* wird —
    nicht, wenn jemand waehrend einer laufenden Sperre klopft;
  * sie faellt auf 0, sobald die Sperre abgelaufen ist (statt beim
    naechsten Versuch wieder in die Verlaengerung zu laufen);
  * `_sperr_dauer` liest die Stufe **vor** ihrer Erhoehung.

DAMIT GILT: erster Fehlversuch ueber der Schwelle -> 300 s. Wer waehrend
der Sperre weiterklopft, verlaengert (das ist gewollt: ein laufender
Angriff soll nicht alle 5 Minuten neu zaehlen), aber die Verlaengerung
waechst nicht mit jedem Klopfen, sondern die Stufe einer Fehlserie ist
gedeckelt.

Die Tests hier sind am echten Login-Endpunkt (`guest_client`) und am
echten Zaehlerstore — nicht an einer nachgebauten Kopie der Logik. Sie
liefen VOR dem Fix rot: die Sperrzeit nach einer Serie lag bei 4800 s
statt bei 300 s bzw. die Serie setzte sich nach Ablauf nicht zurueck.
"""

from __future__ import annotations

import pytest

from diakronos_app.frappe_compat import loginversuche, passwoerter
from diakronos_app.models.core import User

GRUNDDAUER = 300
# Adresse des TestClients — oeffentlich, damit der IP-Zaehler ueberhaupt
# gezaehlt wird (`_ist_eigene_adresse` nimmt private Adressen aus).
TEST_IP = "203.0.113.90"
DECKEL = GRUNDDAUER * 16  # login_sperre_sekunden * login_sperre_max_faktor


# ── Hilfen ──────────────────────────────────────────────────────────────────


def _post(client, usr: str, pwd: str):
    # A1c12: echte IP statt Hostname "testclient" — sonst zaehlt der
    # IP-Zaehler auf einen Wert, den es im Betrieb nicht gibt.
    client._transport.client = (TEST_IP, 50000)
    return client.post("/api/method/login", json={"usr": usr, "pwd": pwd})


def _lege_benutzer(session_factory, name: str, passwort: str) -> None:
    """Konto wie im Betrieb: mit Passwort-Hash und aktiviertem Status."""
    sess = session_factory()
    try:
        sess.add(
            User(
                name=name,
                email=name,
                full_name=name,
                password_hash=passwoerter.neuer_hash(passwort),
                enabled=True,
                user_type="System User",
            )
        )
        sess.commit()
    finally:
        sess.close()


def _sperr_keys(client) -> list[str]:
    """Alle Sperr-Schluessel OHNE die Backoff-Stufe (`:stufe`)."""
    return [
        k
        for k in client._values
        if k.startswith(loginversuche.SPERRE_PRAEFIX) and not k.endswith(":stufe")
    ]


def _einzige_sperre(client) -> str:
    keys = _sperr_keys(client)
    assert len(keys) == 1, f"genau eine Sperre erwartet, gefunden: {keys}"
    return keys[0]


def _serie(client, usr: str, anzahl: int) -> list[int]:
    """`anzahl` Fehlversuche; gibt die Statuscodes zurueck."""
    return [_post(client, usr, f"falsch-{i}").status_code for i in range(anzahl)]


def _loese_sperre_ab(client, sperr_key: str) -> None:
    """Simuliert das Ablaufen der Sperre samt Stufe (das macht sonst die TTL).

    Ohne die Stufe mitzuentfernen waere das kein Ablaufen, sondern ein
    halber Zustand — Redis raeumt beide Keys ueber ihre TTL ab, und die
    TTL der Stufe ist an die Sperre gekoppelt (`_erhoehe_stufe`).
    """
    client._values.pop(sperr_key, None)
    client._ttl.pop(sperr_key, None)
    stufe_key = f"{sperr_key}:stufe"
    client._values.pop(stufe_key, None)
    client._ttl.pop(stufe_key, None)


# ── (S1) Die Sperre greift ueberhaupt ──────────────────────────────────────


def test_mehr_als_die_schwelle_sperrt_das_konto(guest_client, patched_db, fake_redis):
    """N+1 Fehlversuche -> Sperrantwort, und danach bleibt es dabei.

    `test_a1c1_*` belegt das schon fuer die Antwortform. Hier steht der
    BELEG DES BEFUNDS: nach der Serie ist das Konto wirklich gesperrt und
    auch das richtige Passwort kommt nicht mehr durch.
    """
    _lege_benutzer(patched_db, "sec2@example.org", "richtig-123")
    schwelle = loginversuche._max_versuche("u")

    codes = _serie(guest_client, "sec2@example.org", schwelle + 1)

    assert codes[:schwelle] == [401] * schwelle
    assert codes[schwelle] == 401, "der Versuch ueber der Schwelle muss abgewiesen werden"
    assert loginversuche.ist_gesperrt("sec2@example.org", TEST_IP)

    # Und das KORREKTE Passwort wird bei gesperrtem Konto abgewiesen.
    assert _post(guest_client, "sec2@example.org", "richtig-123").status_code == 401


def test_korrektes_passwort_bei_gesperrtem_konto_wird_abgewiesen(
    guest_client, patched_db, fake_redis
):
    """Sperre gilt vor der Passwortpruefung — nicht danach."""
    _lege_benutzer(patched_db, "sec2b@example.org", "richtig-123")
    _serie(guest_client, "sec2b@example.org", loginversuche._max_versuche("u") + 1)

    antwort = _post(guest_client, "sec2b@example.org", "richtig-123")
    assert antwort.status_code == 401
    assert "sid" not in antwort.cookies, "gesperrter Login darf keine Sitzung anlegen"


# ── (S1) Nach dem Fenster wieder moeglich ──────────────────────────────────


def test_nach_ablauf_der_sperre_ist_der_login_wieder_moeglich(
    guest_client, patched_db, fake_redis
):
    """Fenster beachten: Sperre abgelaufen -> richtiges Passwort geht wieder."""
    _lege_benutzer(patched_db, "sec2c@example.org", "richtig-123")
    _serie(guest_client, "sec2c@example.org", loginversuche._max_versuche("u") + 1)

    client = loginversuche._client()
    assert loginversuche.ist_gesperrt("sec2c@example.org", TEST_IP)

    _loese_sperre_ab(client, _einzige_sperre(client))

    assert not loginversuche.ist_gesperrt("sec2c@example.org", TEST_IP)
    assert _post(guest_client, "sec2c@example.org", "richtig-123").status_code == 200


# ── (S1/S2) Die Sperre laesst sich NICHT auf den Deckel treiben ───────────


def test_erste_sperre_dauert_die_grunddauer(guest_client, patched_db, fake_redis):
    """Die Sperre nach der Schwelle dauert `LOGIN_SPERRE_SEKUNDEN`.

    Rot vor dem Fix: die Stufe wurde schon fuer die erste Sperre gezaehlt,
    die Dauer war 60 s statt 300 s (`_setze_sperre` las die erhoehte Stufe).
    """
    _lege_benutzer(patched_db, "sec2d@example.org", "richtig-123")
    _serie(guest_client, "sec2d@example.org", loginversuche._max_versuche("u") + 1)

    client = loginversuche._client()
    assert int(client.get(_einzige_sperre(client))) == GRUNDDAUER


def test_klopfen_waehrend_der_sperre_laesst_sie_nicht_auf_den_deckel_laufen(
    guest_client, patched_db, fake_redis
):
    """DER BEFUND: 27 Versuche duerfen keine 80-Minuten-Sperre hinterlassen.

    Ein Pentest (oder ein Angreifer) probiert in wenigen Sekunden
    durch. Vor dem Fix stand danach `DECKEL` im Store und die Sperre wurde
    bei JEDEM weiteren Versuch erneut auf den Deckel gesetzt — das Konto kam
    ohne Handeingriff 80 Minuten nicht mehr herein. Bei einem Konto, das
    jemand versehentlich attackiert, ist das ein Ausfall.

    Erwartet: die Sperre waechst mit dem Klopfen (das ist gewollt), aber
    eine Fehlserie ist in ihrer Stufe gedeckelt — und nach dem Ablauf beginnt
    die naechste Serie wieder bei der Grunddauer.
    """
    _lege_benutzer(patched_db, "sec2e@example.org", "richtig-123")
    _serie(guest_client, "sec2e@example.org", loginversuche._max_versuche("u") + 1)

    client = loginversuche._client()
    sperr_key = _einzige_sperre(client)

    # 27 Versuche insgesamt — genau die Zahl aus dem Pentest-Befund.
    rest = 27 - (loginversuche._max_versuche("u") + 1)
    assert _serie(guest_client, "sec2e@example.org", rest) == [401] * rest

    dauer = int(client.get(sperr_key))
    assert dauer <= DECKEL
    # Die Kernforderung: nach dieser Serie steht die Sperre NICHT auf dem
    # Deckel. Sie darf wachsen, aber nicht bis zum Maximum — sonst ist sie
    # faktisch ein Lockout ohne Zeitfenster (der Kartentext verlangt
    # ausdruecklich "Zeitfenster beachten").
    assert dauer < DECKEL, (
        f"Sperre steht nach 27 Versuchen auf dem Deckel ({dauer} s) — "
        "das ist ein Lockout ohne wirksames Zeitfenster"
    )


def test_nach_ablauf_beginnt_die_naechste_serie_bei_der_grunddauer(
    guest_client, patched_db, fake_redis
):
    """Backoff ist eine Fehlserie, kein Dauerzustand.

    Rot vor dem Fix: die Stufe ueberlebte den Ablauf der Sperre, und die
    naechste Serie startete direkt beim Deckel — wer sich einmal vertippt
    hatte, war dauerhaft auf 80-Minuten-Sperren festgelegt.
    """
    _lege_benutzer(patched_db, "sec2f@example.org", "richtig-123")
    client = loginversuche._client()

    _serie(guest_client, "sec2f@example.org", loginversuche._max_versuche("u") + 1)
    _serie(guest_client, "sec2f@example.org", 10)  # waehrend der Sperre klopfen
    alter_key = _einzige_sperre(client)
    _loese_sperre_ab(client, alter_key)

    # Zweite Fehlserie nach dem Ablauf.
    _serie(guest_client, "sec2f@example.org", loginversuche._max_versuche("u") + 1)

    neu = _einzige_sperre(client)
    assert int(client.get(neu)) == GRUNDDAUER, (
        "die zweite Fehlserie muss wieder bei der Grunddauer beginnen"
    )


# ── Zeitfenster: der Zaehler allein laeuft ab ──────────────────────────────


def test_zaehler_unter_der_schwelle_laeuft_ab_ohne_zu_sperren(
    guest_client, patched_db, fake_redis
):
    """Ein paar Vertipper sperren nicht, wenn das Fenster dazwischen ablaeuft."""
    _lege_benutzer(patched_db, "sec2g@example.org", "richtig-123")
    client = loginversuche._client()
    schwelle = loginversuche._max_versuche("u")

    _serie(guest_client, "sec2g@example.org", schwelle - 1)
    assert not loginversuche.ist_gesperrt("sec2g@example.org", TEST_IP)

    # Fenster abgelaufen: der Zaehler verschwindet (so macht es Redis per TTL).
    for key in list(client._values):
        if key.startswith(loginversuche.SCHLUESSEL_PRAEFIX):
            client._values.pop(key, None)
            client._ttl.pop(key, None)

    assert _post(guest_client, "sec2g@example.org", "richtig-123").status_code == 200


# ── (S2) Defaults ──────────────────────────────────────────────────────────


def test_schwellen_defaults_sind_sinnvoll():
    """Konto 5, Adresse 25 — die Zahlen aus der Karte und der Betriebsanleitung."""
    from diakronos_app.settings import Settings

    felder = Settings.model_fields
    assert felder["login_max_versuche"].default == 5
    assert felder["login_max_versuche_ip"].default == 25


# ── (S2) Keine Benutzer-Enumeration ───────────────────────────────────────


def test_sperrantwort_ist_von_falschem_passwort_nicht_unterscheidbar(
    guest_client, patched_db, fake_redis
):
    """Ein gesperrtes KONTO darf sich nicht verraten.

    Wichtig fuer den Kartentext: keine 429, kein zusaetzliches Feld, keine
    eigene Meldung. Nur so bleibt die Sperre fuer einen Angreifer unsichtbar
    und fuer den Menschen, der sich vertippt hat, erklaerbar durch Warten.
    """
    _lege_benutzer(patched_db, "sec2h@example.org", "richtig-123")

    falsch = _post(guest_client, "sec2h@example.org", "falsch")
    _serie(guest_client, "sec2h@example.org", loginversuche._max_versuche("u") + 1)
    gesperrt = _post(guest_client, "sec2h@example.org", "falsch")

    assert falsch.status_code == gesperrt.status_code == 401
    assert falsch.json() == gesperrt.json()
    assert falsch.headers.get("retry-after") is None
    assert gesperrt.headers.get("retry-after") is None


def test_unbekannter_und_bekannter_benutzer_antworten_gleich(guest_client, patched_db, fake_redis):
    """Keine Enumeration ueber den Antworttext — auch nicht am Limit."""
    _lege_benutzer(patched_db, "sec2i@example.org", "richtig-123")

    bekannt = _post(guest_client, "sec2i@example.org", "falsch")
    unbekannt = _post(guest_client, "gibtesnicht@example.org", "falsch")

    assert bekannt.status_code == unbekannt.status_code == 401
    assert bekannt.json() == unbekannt.json()
