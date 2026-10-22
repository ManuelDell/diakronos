"""A1c6 (3/3) — der Notweg: die CLI im Container, ohne HTTP und ohne Sitzung.

Die Karte verlangt fuer diesen Weg ausdruecklich: **echte Redis-Verbindung im
Test, nicht nur ein Mock**. Das ist berechtigt — der ganze Notfall existiert
doch nur, weil diese Zeilen im Betrieb gegen den echten Store laufen. Ein Test
gegen eine Attrappe wuerde genau das pruefen, was nicht kaputtgehen kann
(argparse, Exitcodes), und das nicht, was es zu pruefen gibt: die Schluessel,
die `pruefe_und_merke` schreibt, und die `entsperre_konto_und_ip` wieder loescht.

Deshalb laeuft hier der **komplette Pfad des Containers**:

    1. `pruefe_und_merke` sperrt ein Konto und eine IP (echter Redis),
    2. `python -m diakronos_app.loginversuche --entsperren …` als **Unterprozess**,
       mit derselben `PYTHONPATH`-Belegung wie der laufende `app`-Container,
    3. danach wird ueber `pruefe_und_merke` **im Prozess** nachgemessen, ob die
       Sperre wirklich weg ist — nicht ueber den Rueckgabewert der CLI.

Der Unterprozess ist der Punkt: nur so ist belegt, dass der dokumentierte
Befehl wirklich funktioniert und nicht nur die aufgerufene Python-Funktion.
Ein Test, der `cli_entsperren.main([...])` direkt im eigenen Prozess aufruft,
wuerde einen `__main__`-Block, ein falsch gesetztes `sys.path` oder ein
falsches Arbeitsverzeichnis genau nicht erwischen.

Geprueft wird ausserdem die Abnahme der Karte:
  1. **Der Notfall loest den Notfall.** Konto UND IP gesperrt, Notweg laeuft
     — danach ist die Anmeldung wirklich moeglich. Genau der Messfall, an dem
     A1c2s `zuruecksetzen_alles` gescheitert ist (der Gegenprobe-Orchestrator
     hat ihn gemessen: Konto frei, IP gesperrt, weiter 401).
  2. **Ohne HTTP, ohne Rolle, ohne Sitzung** — der Unterprozess hat keine.
  3. **`--ip` ist nicht still.** Ohne `--bestaetigen` passiert nichts, der
     Exitcode sagt es, und die Ausgabe nennt die Gefahr fuer alle Konten
     hinter der Adresse.
  4. **Unbekannter Benutzer → Exitcode != 0**, damit ein Skript nicht
     weiterlaeuft und denkt, es haette freigegeben.
  5. **Idempotent**: zweimal aufrufen ist unschadlich.
  6. **Kein Klartext in der Ausgabe** — weder E-Mail noch IP.
  7. **Kein Passwort im Befehl**: es gibt kein `--passwort`, und es wird auch
     keins angenommen (ein unbekanntes Argument bricht ab, statt es zu
     uebergehen).

WARUM DER UNTERPROZESS SEINE EIGENE DATENBRAUCHT
------------------------------------------------
Der Test-Prozess laeuft auf einer In-Memory-SQLite (siehe `conftest.py`), und
`fake_redis` patcht den Store auf einen Stub. Beides sieht ein Unterprozess
nicht. Deshalb bekommen die Aufrufe hier eine eigene Umgebung: eine
**Datei**-SQLite und das **echte** Redis des Stacks, per `DATABASE_URL` /
`REDIS_URL` gesetzt — dieselben Schalter, ueber die auch der laufende
Container konfiguriert ist.

Das ist keine Bequemlichkeit, sondern der Punkt der Karte: der Notfallweg
existiert, weil diese Zeilen im Betrieb gegen den echten Store laufen. Ein
Test gegen eine Attrappe prueft, was nicht kaputtgehen kann (argparse,
Exitcodes) — und nicht das, was es zu pruefen gibt.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from diakronos_app.frappe_compat import loginversuche as lv

SCHWELLE = 5
# A1c10: die Adressschwelle ist eine eigene Zahl (Default 25). Die CLI-Tests
# brauchen sie an drei Stellen — deshalb wird sie hier einmal aus dem Store
# gelesen und nicht an vier Stellen ausgeschrieben. Sonst waere das die
# Kopie, die A1c3 bei `ADMIN_ROLES` teuer gekommen ist.
ADRESSSCHWELLE = lv._max_versuche("ip")

ZIEL = "anna@example.org"
UNBEKANNT = "gibtsnicht@example.org"
IP = "203.0.113.77"
GEHEIM = "Geheim-1"

# A1c11: jeder pytest-Prozess bekommt einen eigenen Redis-Server.
# Kein gemeinsamer DB-Index und keine Reservierung im Betriebsstore.


# ── Helfer ──────────────────────────────────────────────────────────────────


def _sperre_konto(user: str, anzahl: int = SCHWELLE + 1) -> None:
    for bereich in lv.BEREICHE:
        for _ in range(anzahl):
            lv.pruefe_und_merke(user, None, bereich=bereich)


def _sperre_ip(ip: str, anzahl: int = ADRESSSCHWELLE + 1) -> None:
    """Setzt die IP-Sperre — so, wie es ein Angreifer von aussen tut.

    Die Konten dabei absichtlich **anders** als das Zielkonto: es geht um die
    Sperre der *Adresse*, nicht um ein Konto.

    **A1c10:** `anzahl` ist die **Adressschwelle** + 1, nicht mehr die
    Kontoschwelle + 1. Gesperrt wird bei `zaehler > schwelle` — mit
    Schwelle 5 waren das 6 Versuche, mit Schwelle 25 sind es 26. Mit den
    alten 6 Versuergen erreicht der Adresszaehler nur 6 und die Adresse wird
    nie gesperrt; die Assertion unten faellt dann genau so auf wie oben.
    """
    assert anzahl >= ADRESSSCHWELLE + 1, (
        f"{anzahl} Versuche reichen nicht fuer die Adressschwelle "
        f"{ADRESSSCHWELLE} (geprueft wird bei zaehler > schwelle)"
    )
    for bereich in lv.BEREICHE:
        for nummer in range(anzahl):
            lv.pruefe_und_merke(f"opfer{nummer}@example.org", ip, bereich=bereich)


def _konto_gesperrt(user: str) -> bool:
    client = lv._client()
    return any(
        client.exists(sperr)
        for bereich in lv.BEREICHE
        for _art, _zaehler, sperr in lv._kennungen(user, None, bereich)
    )


def _ip_gesperrt(ip: str) -> bool:
    client = lv._client()
    return any(
        client.exists(sperr)
        for bereich in lv.BEREICHE
        for _art, _zaehler, sperr in lv._kennungen(None, ip, bereich)
    )


def _aufraeumen(user: str | None = None, ip: str | None = None) -> None:
    """Alles wieder aus dem Weg, was ein Test zuruecklaesst."""
    client = lv._client()
    for bereich in lv.BEREICHE:
        for _art, zaehler, sperr in lv._kennungen(user, ip, bereich):
            client.delete(zaehler, sperr, f"{sperr}:stufe")


@pytest.fixture()
def echt_stores(tmp_path, monkeypatch, privater_redis_url):
    """Datei-SQLite + privates echtes Redis fuer Test und CLI-Unterprozess.

    Der sessionweite Server wird vor und nach jedem Test geleert. Sein
    Unix-Socket ist nur diesem pytest-Prozess bekannt; REDIS_URL des
    laufenden Stacks wird weder verwendet noch umgeschrieben.
    """
    import redis as redis_lib

    monkeypatch.setenv("REDIS_URL", privater_redis_url)

    datei = tmp_path / "a1c6-cli.db"
    datenbank_url = f"sqlite+pysqlite:///{datei}"
    monkeypatch.setenv("DATABASE_URL", datenbank_url)

    # Schema anlegen: die Modelle braucht der Testprozess, und der
    # Unterprozess soll nur lesen, nicht migrieren.
    import diakronos_app.models  # noqa: F401
    import diakronos_app.db as dbmod
    from diakronos_app.models.base import Base

    motor = create_engine(datenbank_url, future=True)
    Base.metadata.create_all(motor)
    # `diakronos_app.db.SessionLocal` ist beim Import gegen die **Postgres**
    # des Stacks gebunden worden — ENV aus `monkeypatch.setenv` kommt dann
    # zu spaet. Deshalb hier ausdruecklich auf die Datei-DB umhaengen, sonst
    # schreibt der Test in die Betriebsdatenbank (das ist ein echter Neben-
    # effekt, kein Testproblem: die beiden Prozesse muessen dieselbe Datei
    # sehen, sonst ist der ganze Test sinnlos).
    motor.dispose()
    datei_motor = create_engine(datenbank_url, future=True)
    monkeypatch.setattr(dbmod, "engine", datei_motor)
    monkeypatch.setattr(dbmod, "SessionLocal", sessionmaker(bind=datei_motor, future=True))

    verbindung = redis_lib.Redis.from_url(privater_redis_url)
    try:
        verbindung.flushdb()
        monkeypatch.setattr(lv, "_client", lambda: verbindung)
        yield verbindung
    finally:
        try:
            verbindung.flushdb()
        finally:
            verbindung.close()
            datei_motor.dispose()


@pytest.fixture()
def notfall(echt_stores):
    """Ein gesperrtes Konto **und** eine gesperrte IP, beide im echten Redis.

    Genau der Zustand aus der Gegenprobe: der einzige Administrator ist
    gesperrt, und ueber dieselbe Adresse laeuft ein Angriff. Nach einem reinen
    Konto-Aufraehr waere die IP weiter gesperrt und jede Anmeldung bliebe 401.
    """
    yield from _notfall_mit(echt_stores, sperre_auf_ip=True)


@pytest.fixture()
def nur_konto(echt_stores):
    """Dieselbe Lage, aber **ohne** IP-Sperre.

    Fuer die Faelle, die sich nur mit dem Konto beschaeftigen. Der
    Unterschied ist nicht kosmetisch: steht eine IP-Sperre im Store, meldet
    der Notweg am Ende ehrlich "es steht noch eine Sperre auf einer
    Client-IP" und endet mit Exitcode 2 — das ist gewollt, macht aber
    einen Test, der nur das Konto sehen will, sonst unlesbar.
    """
    yield from _notfall_mit(echt_stores, sperre_auf_ip=False)


# ── A1c8: der Alltagsfall einer Gemeinde ────────────────────────────────────
#
# Fuenf erlaubte Fehlversuche eines EINZIGEN Benutzers von der gemeinsamen
# Adresse: der Benutzerzaehler sperrt, der IP-Zaehler bleibt **auf der
# Schwelle** stehen. Steht die Sperre danach auf dem Konto, ist das der
# wahrscheinlichste Fall ueberhaupt — und `zaehle_gesperrte_ips()` sah ihn
# nicht, weil sie Sperren zaehlt und im Store keine steht.


def _zaehler_auf_der_schwelle(user: str, ip: str, anzahl: int = SCHWELLE + 1) -> None:
    """Der Benutzer sperrt, die Adresse bleibt genau auf der Schwelle.

    Das ist der Zustand aus dem Befund dieser Karte, und er entsteht von
    selbst, wenn man denselben Benutzer sechsmal anmeldet: `pruefe_und_merke`
    zaehlt **erst den Benutzer, dann die Adresse** und bricht sofort ab, sobald
    eine Schwelle ausloest.

    **Warum `SCHWELLE + 1` Versuche noetig sind** (live gemessen, echter
    Redis, DB 14, `login_max_versuche=5`):

        Versuch 1..5  -> erlaubt, Konto frei, IP-Zaehler 1..5
        Versuch 6     -> Konto gesperrt, IP-Zaehler **5**

    Gesperrt wird bei `zaehler > schwelle`, nicht bei `>=`. Nach fuenf
    Versuchen steht der Benutzerzaehler also auf 5 und das Konto ist noch
    frei — der sechste Versuch sperrt es und laesst den IP-Zaehler bei 5
    stehen.

    Mit `SCHWELLE` Versuchen bricht die Schleife vorher ab, das Konto
    bleibt frei, und der Test prueft den Fall aus A1c6 statt den aus
    A1c8. Die Assertion in der Fixture deckt das ab.

    **A1c10 — die Schleife laeuft weiter als bis zum Konto.** Die Adress-
    schwelle ist von 5 auf 25 gewandert (`LOGIN_MAX_VERSUCHE_IP`), und die
    Schleife bricht erst ab, wenn das **Konto** gesperrt ist. Damit ist der
    Zustand nach dem sechsten Versuch nicht mehr "Adresse auf 5", sondern
    "Adresse auf 6, Konto gesperrt" — und das ist genau richtig: die Adresse
    ist ja **nicht** auf ihrer Schwelle, sondern sechs Fehlversuche unter
    ihrer eigenen. Die Fixture unten stellt deshalb den Adresszaehler
    ausdruecklich auf die **Adressschwelle** (25), sonst prueft der Test
    nicht mehr den Fall aus A1c8, sondern den uninteressanten Fall
    "Adresse weit unter der Schwelle".
    """
    for _ in range(anzahl):
        lv.pruefe_und_merke(user, ip, bereich=lv.BEREICH_LOGIN)
        if _konto_gesperrt(user):
            break


def _adresse_auf_die_schwelle(ip: str, bereich: str = lv.BEREICH_LOGIN) -> None:
    """Bringt den Adresszaehler exakt auf die **Adressschwelle** (A1c10).

    Ueber **andere** Konten, sonst sperrt zuerst der Benutzerzaehler und
    der Adresszaehler kommt nie in die Naehe der Schwelle. Jeder Versuch
    zaehlt die Adresse mit; abgebrochen wird, sobald die Adressschwelle
    erreicht ist — also **ohne** zu sperren (`pruefe_und_merke` sperrt erst
    bei `zaehler > schwelle`).
    """
    schwelle = lv._max_versuche("ip")
    for nummer in range(schwelle + 1):
        erlaubt, grund = lv.pruefe_und_merke(
            f"opfer{nummer}@example.org", ip, bereich=bereich
        )
        assert grund != "ip" and not (not erlaubt and grund == "ip"), (
            "die Adresse wurde gesperrt, bevor der Zaehler auf der Schwelle stand"
        )
        if _ip_zaehler(ip, bereich) >= schwelle:
            break


def _ip_zaehler(ip: str, bereich: str = lv.BEREICH_LOGIN) -> int:
    client = lv._client()
    for _art, zaehler, _sperr in lv._kennungen(None, ip, bereich):
        roh = client.get(zaehler)
        if roh is not None:
            return int(roh)
    return 0


@pytest.fixture()
def schwelle_steht(echt_stores):
    """Konto gesperrt, Adresse **auf der Adressschwelle** — der Messfall.

    Genau der Befund aus dem Review von A1c7: EIN Benutzer, Fehlversuche vom
    gemeinsamen Internetanschluss. Der alte Notweg meldete hier "alles
    erledigt" (exit 0) und die naechste Anmeldung gab 401.

    **A1c10:** die "Schwelle" ist seitdem die **Adressschwelle** (25), nicht
    mehr die Kontoschwelle (5). Nach sechs Fehlversuchen eines Benutzers
    steht der Adresszaehler bei 6 — das ist weit unter 25 und damit
    zu Recht *nicht* "im Weg". Deshalb wird der Zaehler hier ausdruecklich
    auf die Adressschwelle gebracht, sonst prueft dieser Test nicht mehr den
    Fall aus A1c8.

    Der Aufbau laeuft bewusst ueber **andere** Konten, bis der Zaehler auf
    der Adressschwelle steht, und der letzte Versuch kommt dann vom
    gesperrten Zielkonto — so, wie es im Betrieb passiert.
    """
    from diakronos_app.db import SessionLocal
    from diakronos_app.frappe_compat.passwoerter import neuer_hash
    from diakronos_app.models.core import User

    sess = SessionLocal()
    try:
        sess.add(User(
            name=ZIEL, email=ZIEL, full_name=ZIEL, enabled=True,
            password_hash=neuer_hash(GEHEIM),
        ))
        sess.commit()
    finally:
        sess.close()

    # Reihenfolge (A1c10): erst den Adresszaehler auf **seine** Schwelle
    # bringen, dann das Konto sperren. Umgekehrt waere der Adresszaehler
    # bei 6 — der Messfall waere dann nicht mehr "Adresse auf der Schwelle",
    # sondern "Adresse weit darunter", und der Test pruefte etwas anderes.
    _adresse_auf_die_schwelle(IP)
    _sperre_konto(ZIEL)

    # Die Ausgangslage wird **abgeprueft** statt angenommen: steht die Adresse
    # doch gesperrt, prueft der Test den Fall aus A1c6 und nicht den aus A1c8.
    assert _konto_gesperrt(ZIEL), "Ausgangslage fehlt: Konto nicht gesperrt"
    assert not _ip_gesperrt(IP), (
        "Ausgangslage ist nicht der Messfall: es steht eine IP-Sperre im Store"
    )
    assert _ip_zaehler(IP) == ADRESSSCHWELLE, (
        f"der IP-Zaehler steht auf {_ip_zaehler(IP)}, nicht auf der "
        f"Adressschwelle {ADRESSSCHWELLE}"
    )
    yield


def _notfall_mit(echt_stores, sperre_auf_ip: bool):
    from diakronos_app.db import SessionLocal
    from diakronos_app.frappe_compat.passwoerter import neuer_hash
    from diakronos_app.models.core import User

    sess = SessionLocal()
    try:
        sess.add(User(
            name=ZIEL, email=ZIEL, full_name=ZIEL, enabled=True,
            password_hash=neuer_hash(GEHEIM),
        ))
        sess.commit()
    finally:
        sess.close()

    _sperre_konto(ZIEL)
    if sperre_auf_ip:
        _sperre_ip(IP)
    assert _konto_gesperrt(ZIEL), "Ausgangslage fehlt: Konto nicht gesperrt"
    assert _ip_gesperrt(IP) is sperre_auf_ip, "Ausgangslage der IP stimmt nicht"
    yield


def _cli(*args: str) -> subprocess.CompletedProcess:
    """Ruft die CLI so auf, wie der Betreiber es im Notfall tut.

    Als **Unterprozess** — nicht `main()` im eigenen Prozess. Nur so wird der
    dokumentierte Befehl `python -m diakronos_app.loginversuche` selbst
    getestet, und nicht nur die Python-Funktion dahinter.

    `PYTHONPATH=/app/src` entspricht der Belegung im `app`-Container
    (siehe Dockerfile); `capture_output` haelt die Ausgabe aus dem Log heraus.

    `DATABASE_URL`, `REDIS_URL` und `SECRET_KEY` werden **durchgereicht**
    (gesetzt vom Fixture `echt_stores` bzw. von der Container-ENV). Alle drei
    gehoeren zusammen: die Schluessel im Redis sind mit `secret_key` gesalzen,
    ein Unterprozess mit dem Development-Default als Salz wuerde also
    voellig andere Schluessel schreiben als der Testprozess — die Freigabe
    liefe ins Leere und der Test wuerde die falsche Sache messen.
    """
    return subprocess.run(
        [sys.executable, "-m", "diakronos_app.loginversuche", *args],
        capture_output=True,
        text=True,
        timeout=60,
        env=_unterprozess_umgebung(),
    )


def _out(prozess: subprocess.CompletedProcess) -> str:
    return prozess.stdout + prozess.stderr


# ── 1. Der Notfall loest den Notfall ────────────────────────────────────────


def test_nur_das_konto_zu_loesen_waere_die_sackgasse(notfall):
    """Gegenprobe zuerst: der reine Konto-Weg laesst die IP gesperrt.

    Ohne diesen Test koennte ein spaeterer Umbau die IP-Freigabe zum
    Nebenbehalt machen und der Notfall waere ungetestet wieder die Sackgasse,
    gegen die diese Karte gebaut wurde.
    """
    lv.zuruecksetzen_alles(ZIEL)

    assert not _konto_gesperrt(ZIEL), "das Konto sollte frei sein"
    assert _ip_gesperrt(IP), (
        "die IP-Sperre besteht weiter — genau das ist der Grund fuer --ip"
    )


def test_der_notweg_befaehigt_konto_und_ip_wieder(notfall):
    """**Der Abnahmepunkt der Karte.** Beide Sperren sind weg.

    Danach muss `pruefe_und_merke` den richtigen Zugang wieder durchlassen.
    Der Test prueft nicht nur "die Schluessel sind geloescht", sondern den
    Aufruf, der am Ende einer echten Anmeldung steht.
    """
    assert _konto_gesperrt(ZIEL), "Ausgangslage: Konto ist gesperrt"
    assert _ip_gesperrt(IP), "Ausgangslage: IP ist gesperrt"

    prozess = _cli("--entsperren", ZIEL, "--ip", IP, "--bestaetigen")

    assert prozess.returncode == 0, _out(prozess)
    assert not _konto_gesperrt(ZIEL), "Konto ist immer noch gesperrt"
    assert not _ip_gesperrt(IP), "IP ist immer noch gesperrt"

    # Der Zugang, um den es hier geht: kein 401 mehr.
    assert lv.ist_gesperrt(ZIEL, IP) is False


# ── 1b. Der Notweg darf nicht "erfolgreich" melden, was scheitert ───────────


def test_bleibt_die_ip_gesperrt_sagt_der_notweg_es_laut(notfall):
    """Konto frei, IP gesperrt — der Notweg darf das **nicht** verschweigen.

    Das ist der Messfall aus der Gegenprobe des Orchestrators, live
    gemessen: nach `zuruecksetzen_alles` war das Konto frei, die Anmeldung
    blieb 401, weil die IP noch gesperrt war. Ein Notweg, der "aufgehoben"
    meldet und dann nicht weiterkommt, ist schlimmer als keiner — man
    glaubt, es sei erledigt, und steht genau da, wo man vorher stand.
    """
    prozess = _cli("--entsperren", ZIEL)  # NUR das Konto
    ausgabe = _out(prozess)

    assert not _konto_gesperrt(ZIEL), "das Konto sollte frei sein"
    assert _ip_gesperrt(IP), "die IP-Sperre besteht weiter"

    # Der Exitcode sagt: der Notfall ist NICHT geloest.
    assert prozess.returncode == 2, (
        "es meldet Erfolg, obwohl es 401 gibt "
        f"(Exitcode war {prozess.returncode})"
    )
    # Und die Ausgabe sagt, woran es liegt — und bietet den naechsten Weg.
    assert "ADRESSE" in ausgabe or "Adresse" in ausgabe
    assert "--ip" in ausgabe, "der zweite Weg wird nicht genannt"
    assert IP not in ausgabe, "die IP wird geraten oder im Klartext genannt"


def test_bleibt_die_ip_gesperrt_ist_die_anmeldung_trotzdem_gesperrt(notfall):
    """Der Exitcode 2 ist nicht nur eine Zahl — er beschreibt die Wirklichkeit.

    Die Karte A1c7 sagt: Exit 2, *"kein 200, keine Anmeldung moeglich"*.
    Geprueft wird deshalb nicht der Exitcode allein, sondern der Zustand, den
    ein Skript nach `0` annaehme: `pruefe_und_merke` muss den Versuch weiter
    abweisen. Ein Exitcode, der die Wirklichkeit nicht beschreibt, waere
    genau die Luege, die diese Karte abstreift — nur an anderer Stelle.
    """
    prozess = _cli("--entsperren", ZIEL)
    assert prozess.returncode == 2, _out(prozess)

    assert not _konto_gesperrt(ZIEL), "das Konto sollte frei sein"
    assert lv.ist_gesperrt(ZIEL, IP) is True, (
        "Exitcode 2 behauptet 'es sperrt noch' — die Anmeldung geht aber durch"
    )


def test_ohne_ip_sperre_bleibt_der_notweg_still(nur_konto):
    """Der Normalfall darf nicht leiden: keine IP-Sperre -> Exitcode 0.

    Sonst waere Exit 2 wertlos — er muesste ja immer kommen. Das ist die
    Angst, die man hat, wenn man einen Exitcode repariert: dass er jetzt
    uebertrieben muendlich ist und der haeufigste Fall (ein Mitglied hat sich
    dreimal vertippt) aus einem Skript heraus bricht.
    """
    prozess = _cli("--entsperren", ZIEL)

    assert prozess.returncode == 0, _out(prozess)
    assert "ADRESSE" not in _out(prozess), "die Warnung kommt ohne Anlass"


def test_ein_store_ohne_antwort_darf_nicht_erfolg_melden(notfall, monkeypatch):
    """Kein Redis, kein Erfolg — dieselbe Fehlerklasse, eine Ebene tiefer.

    Das ist der Restfall, der am alten Stand wirklich noch falsch war (und
    die Karte A1c7 hat, an der falschen Stelle, genau diese Klasse
    beschrieben): `_ip_hinweis()` fing einen Store-Ausfall und gab Exitcode
    **0** zurueck. Ein Skript haette danach geglaubt, der Notfall sei
    geloest, und der naechste Anmeldeversuch gibt wieder 401.

    "Ich habe nicht nachgesehen" ist nicht "es ist nichts im Weg". An jeder
    anderen Stelle derselben Datei ist genau das so behandelt
    (`cli_entsperren.py::_status`, siehe `_entsperren`) — mit derselben
    Begruendung im Wortlaut. Diese eine Stelle war ein Fail-open.

    Der Fehlerfall wird **im Unterprozess** erzeugt: der ganze Sinn dieser
    Karte ist der dokumentierte Befehl, nicht die Python-Funktion dahinter.
    Einen unerreichbaren Redis zu bauen ist unmoeglich, ohne den Container
    zu stoeren — deshalb wird hier `zaehle_gesperrte_ips` im Kindprozess
    kaputt gemacht, ueber ein kleines Rueckgabemodul in `PYTHONPATH`.
    """
    prozess = _cli_fehlerfall("--entsperren", ZIEL)

    assert prozess.returncode == 1, (
        "ohne Antwort aus dem Store wird Erfolg gemeldet — das ist die Luege, "
        f"die diese Karte abstreift (Exitcode war {prozess.returncode})"
    )
    ausgabe = _out(prozess)
    # Und es sagt, dass es den Rest **nicht weiss** — statt zu schweigen.
    assert "nicht erreichbar" in ausgabe, ausgabe
    # Die Konto-Freigabe darf und soll gemeldet werden: sie **ist**
    # passiert. Was der Befehl nicht weiss, ist, ob noch etwas im Weg
    # steht — genau das muss er sagen, statt mit Exitcode 0 zu behaupten,
    # es gebe nichts mehr.
    assert "laesst sich nicht sagen" in ausgabe, ausgabe
    # Und es behauptet nirgends, der Notfall sei geloest.
    assert "nicht gelöst" not in ausgabe and "geloest" not in ausgabe, ausgabe


def _cli_fehlerfall(*args: str) -> subprocess.CompletedProcess:
    """Die CLI im Unterprozess — mit kaputtem `zaehle_adressen_im_weg`.

    Der Store-Ausfall ist der einzige Fall, den man nicht durch Einrichten
    des Zustands herstellen kann, sondern nur durch **Abstellen** des
    Store-Zugriffs. Damit der trotzdem durch den echten `python -m
    diakronos_app.loginversuche`-Weg läuft (nicht durch einen Aufruf von
    `main()` im Testprozess), bekommt der Kindprozess ein zusaetzliches
    Verzeichnis im `PYTHONPATH` vorangestellt, das `diakronos_app`
    vortaeuscht: dort liegt ein `sitecustomize.py`, das genau diese eine
    Funktion durch eine kaputte ersetzt.

    **A1c8: die kaputte Funktion ist `zaehle_adressen_im_weg`, nicht mehr
    `zaehle_gesperrte_ips`.** `_ip_hinweis` fragt inzwischen danach, ob
    eine Adresse **im Weg** steht (Sperre *oder* Zaehler auf der Schwelle).
    Wuerde hier weiter die alte Funktion kaputtgemacht, wuerde der Test
    einen Store-Ausfall simulieren, den der Befehl gar nicht mehr erlebt —
    und "es wurde kein Erfolg gemeldet" waere wieder eine Behauptung ohne
    Beleg. Genau die Sorte Fehler, die diese Kartenreihe abstreift.

    Der Rest des Moduls bleibt unangetastet — es geht um den Store-Zugriff,
    nicht um den Aufruf.
    """
    quatsch = Path(tempfile.mkdtemp(prefix="a1c7-kaputt-"))
    (quatsch / "sitecustomize.py").write_text(
        "import diakronos_app.frappe_compat.loginversuche as lv\n"
        "def _kaputt(*_a, **_kw):\n"
        "    raise RuntimeError('Redis nicht erreichbar')\n"
        "lv.zaehle_adressen_im_weg = _kaputt\n",
        encoding="utf-8",
    )
    umgebung = _unterprozess_umgebung(extra_pythonpath=quatsch)
    try:
        return subprocess.run(
            [sys.executable, "-m", "diakronos_app.loginversuche", *args],
            capture_output=True, text=True, timeout=60, env=umgebung,
        )
    finally:
        shutil.rmtree(quatsch, ignore_errors=True)


def _worktree_quellpfad() -> str | None:
    """`/app/src` genau dann, wenn dieser Lauf den Worktree-Code sieht.

    `backend/src` ist dabei read-only nach `/app/src` gebunden. Das ist
    im Container **derselbe Pfad** wie im Image — die Frage "laeuft der
    Unterprozess gegen den Worktree oder gegen das Image?" ist von innen also
    **nicht** am Pfad zu erkennen, sondern nur am Inhalt.

    Deshalb wird gemessen statt geraten: nur wenn `/app/src` das Modul **und**
    die Funktion dieser Karte traegt (`zaehle_adressen_im_weg`), ist es der
    Worktree-Stand. Sonst bleibt es beim `None` des Aufrufers und der
    Unterprozess laeuft — wie im Betrieb — gegen das Image. Ein Fehlschlag
    beim Lesen ist kein Fehler, sondern ein "weiss nicht".
    """
    if not Path("/app/src/diakronos_app/frappe_compat/loginversuche.py").is_file():
        return None
    try:
        text = Path("/app/src/diakronos_app/frappe_compat/loginversuche.py").read_text(
            encoding="utf-8"
        )
    except OSError:
        return None
    return "/app/src" if "def zaehle_adressen_im_weg" in text else None


def _unterprozess_umgebung(extra_pythonpath: Path | None = None) -> dict[str, str]:
    """Die ENV des Unterprozesses — dieselbe wie in `_cli`.

    `extra_pythonpath` kommt **vorangestellt**, nicht ersetzt: der Kindprozess
    braucht beides, das eigene Verzeichnis fuer den `sitecustomize` und den
    echten Quellpfad fuer `diakronos_app`.

    **A1C8: der Quellpfad kommt aus `A1C8_SRC`, falls gesetzt.** Der
    Unterprozess ist das, was diese Datei eigentlich testet — laeuft er
    gegen den Code aus dem Image statt gegen den der Arbeitskopie, prueft
    die ganze Datei eine alte Fassung und meldet dabei "gruen". Genau das
    ist beim ersten Lauf dieser Karte passiert: die drei A1c8-Tests waren rot
    mit der Behauptung, der Notweg melde "aufgehoben", waehrend er im
    Worktree-Code `zaehle_adressen_im_weg` aufrief.

    Ohne die Variable bleibt `/app/src` stehen — im Betrieb ist das der
    gemountete Quellpfad des Containers, und daran wird nichts geaendert.

    **A1C8 (Nachtrag): `A1C8_SRC` wird automatisch belegt, wenn der Quellbaum
    read-only gemountet ist.** Ohne das laeuft der Unterprozess gegen
    `/app/src` aus dem **Image**, waehrend die uebrigen Tests gegen den
    Worktree-Code laufen. Genau das hat diese Karte zuerst gemessen: die
    A1c8-Tests waren rot mit "der Notweg meldete 'aufgehoben'", obwohl der
    Worktree-Code die richtige Funktion aufrief — der Unterprozess lief
    gegen den alten Stand. Die ausdrueckliche `A1C8_SRC`-Setzung gewinnt,
    damit die Variable in anderen Umgebungen (CI, anderer Mount) weiter
    gesetzt werden kann.
    """
    pfad = os.environ.get("A1C8_SRC") or _worktree_quellpfad() or "/app/src"
    if extra_pythonpath is not None:
        pfad = f"{extra_pythonpath}:{pfad}"

    umgebung = {
        "PYTHONPATH": pfad,
        "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
        "HOME": os.environ.get("HOME", "/root"),
    }
    for schluessel in ("DATABASE_URL", "REDIS_URL", "SECRET_KEY"):
        if schluessel in os.environ:
            umgebung[schluessel] = os.environ[schluessel]
    return umgebung


def test_ohne_ip_sperre_meldet_der_notweg_erfolg(nur_konto):
    """Der Gegenfall: ist keine IP gesperrt, bleibt der Exitcode 0.

    Sonst waere die Warnung wertlos — sie muesste ja immer kommen. Der
    gleiche Aufruf wie im Notfall, nur ohne die IP-Sperre im Store.
    """
    assert not _ip_gesperrt(IP), "Ausgangslage: es ist doch eine IP gesperrt"

    prozess = _cli("--entsperren", ZIEL)

    assert prozess.returncode == 0, _out(prozess)
    assert "ADRESSE" not in _out(prozess)
    assert not _konto_gesperrt(ZIEL)


def test_zaehle_gesperrte_ips_zaehlt_nicht_doppelt(echt_stores):
    """Eine IP-Sperre liegt genau einmal im Keyspace, nicht je Bereich.

    Die Sperre ist bereichsuebergreifend (A1c2). Wer hier ueber `BEREICHE`
    zaehlt, trifft dieselbe Sperre zweimal und meldet dem Betreiber zwei
    Adressen, wo eine steht — die Zahl soll etwas ueber den Zustand
    sagen, nicht ueber die eigene Schleife.
    """
    assert lv.zaehle_gesperrte_ips() == 0, "Ausgangslage ist nicht sauber"

    _sperre_ip(IP)
    assert lv.zaehle_gesperrte_ips() == 1, (
        "eine gesperrte Adresse muss genau einmal gezaehlt werden"
    )

    _aufraeumen(None, IP)
    assert lv.zaehle_gesperrte_ips() == 0


def test_die_zaehlung_zaehlt_die_backoff_stufe_nicht_mit(echt_stores):
    """`:stufe` ist die Stufe derselben Sperre, kein zweiter Eintrag.

    Der Schluessel-Vergleich dekodiert hier bewusst mit — sonst wuerde die
    Vorbedingung des Tests selbst an `bytes` scheitern und der Test waere
    gruen, ohne die Zaehlschleife je geprueft zu haben.
    """
    _sperre_ip(IP)

    client = lv._client()
    stufen = [
        k.decode() if isinstance(k, bytes) else str(k)
        for k in client.scan_iter(match=f"{lv.SPERRE_PRAEFIX}ip:*")
    ]
    assert any(k.endswith(":stufe") for k in stufen), (
        "Ausgangslage: es gibt keine Backoff-Stufe, der Test prueft nichts"
    )

    assert lv.zaehle_gesperrte_ips() == 1, "die Stufe wurde mitgezaehlt"
    _aufraeumen(None, IP)


def test_beide_bereiche_sind_frei_nicht_nur_der_login(notfall):
    """CalDAV haengt an denselben Store (A1c2) — beide muessen durch sein.

    Ein Aufraehrweg, der nur den Login-zaehler leert, laesst den CalDAV-Zaehler
    stehen; der naechste Fehlversuch dort sperrt sofort wieder. Deshalb wird
    je Bereich einzeln nachgemessen.
    """
    _cli("--entsperren", ZIEL, "--ip", IP, "--bestaetigen")

    client = lv._client()
    for bereich in lv.BEREICHE:
        for _art, zaehler, sperr in lv._kennungen(ZIEL, None, bereich):
            fehlt = f" steht noch ({bereich})"
            assert not client.exists(zaehler), "Zaehler" + fehlt
            assert not client.exists(sperr), "Sperre" + fehlt
            assert not client.exists(f"{sperr}:stufe"), "Backoff-Stufe" + fehlt


def test_die_ausgabe_bestaetigt_und_nennt_die_folgen_in_der_klartextform(notfall):
    """Die Konsole muss sagen, was passiert ist — und vor der IP die Warnung."""
    prozess = _cli("--entsperren", ZIEL, "--ip", IP, "--bestaetigen")
    ausgabe = _out(prozess)

    assert "Login" in ausgabe and "CalDAV" in ausgabe
    assert "aufgehoben" in ausgabe
    # Die Folge fuer die anderen Konten hinter derselben Adresse wird
    # genannt — wer eine IP freigibt, entsperrt damit das halbe Buero.
    assert "alle anderen Konten" in ausgabe


def test_ohne_klartext_weder_e_mail_noch_ip(notfall):
    """Die Konsole ist fuer Support-Faelle da, nicht als Adressliste."""
    ausgabe = _out(_cli("--entsperren", ZIEL, "--ip", IP, "--bestaetigen"))

    assert ZIEL not in ausgabe, "E-Mail im Klartext in der Ausgabe"
    assert IP not in ausgabe, "IP im Klartext in der Ausgabe"
    assert GEHEIM not in ausgabe


# ── 2. Ohne HTTP, ohne Rolle, ohne Sitzung ──────────────────────────────────


def test_der_befehl_laeuft_ohne_sitzung_und_ohne_rolle(nur_konto):
    """Der ganze Zweck: nichts von dem braucht der Aufruf.

    Kein `sid` in der Umgebung, keine Rolle, kein Cookie — der Unterprozess
    startet mit einer nackten Python-Umgebung. Waere `require_admin()`
    unterwegs, wuerde der Lauf hier mit 403 abbrechen.
    """
    prozess = _cli("--entsperren", ZIEL)

    assert prozess.returncode == 0, _out(prozess)
    assert not _konto_gesperrt(ZIEL)


def test_der_pfad_laesst_die_ip_in_ruehe_wenn_kein_ip_genannt_ist(notfall):
    """Ohne `--ip` wird **nur** das Konto geloest — der Web-Weg-Sinn.

    Bleibt die IP gesperrt, meldet der Notweg das am Ende (Exitcode 2, siehe
    `test_bleibt_die_ip_gesperrt_sagt_der_notweg_es_laut`). Hier geht es nur
    darum, dass der reine Konto-Aufruf die Adresse nicht mitnimmt.
    """
    assert _ip_gesperrt(IP), "Ausgangslage: es ist keine IP gesperrt"

    prozess = _cli("--entsperren", ZIEL)

    assert not _konto_gesperrt(ZIEL)
    assert _ip_gesperrt(IP), "ohne --ip darf die IP nicht mitgeloest werden"
    assert prozess.returncode != 0, (
        "mit offener IP-Sperre darf kein Erfolg gemeldet werden"
    )


# ── 3. --ip ist nicht still ─────────────────────────────────────────────────


def test_ohne_bestaetigung_wird_nichts_geloescht(notfall):
    """`--ip` ohne `--bestaetigen`: Exitcode != 0, **beide** Sperren bleiben."""
    prozess = _cli("--entsperren", ZIEL, "--ip", IP)

    assert prozess.returncode != 0
    assert _konto_gesperrt(ZIEL), "es wurde doch geloescht"
    assert _ip_gesperrt(IP), "es wurde doch geloescht"


def test_die_frage_warnt_ausdruecklich_vor_den_anderen_konten(notfall):
    """Die Warnung steht in der Ausgabe, bevor irgendetwas passiert."""
    ausgabe = _out(_cli("--entsperren", ZIEL, "--ip", IP))

    assert IP in ausgabe, "die Adresse wird nicht genannt, um die es geht"
    assert "ALLE Konten" in ausgabe or "allen Konten" in ausgabe
    assert "--bestaetigen" in ausgabe, "der zweite Schritt wird nicht erklaert"


def test_bestaetigen_ohne_ip_ist_ein_fehler(notfall):
    """Widerspruechliche Schalter brechen ab, statt stillzuschweigen."""
    prozess = _cli("--entsperren", ZIEL, "--bestaetigen")

    assert prozess.returncode != 0
    assert _konto_gesperrt(ZIEL)


# ── 4. Unbekannter Benutzer: Exitcode != 0 ──────────────────────────────────


def test_unbekannter_benutzer_bricht_mit_exitcode_ab(echt_stores):
    """Ein Skript darf nicht weiterlaufen und denken, es haette freigegeben."""
    prozess = _cli("--entsperren", UNBEKANNT)

    assert prozess.returncode != 0
    assert "FEHLER" in _out(prozess)


def test_die_fehlermeldung_nennt_die_adresse_nicht_im_klartext(echt_stores):
    ausgabe = _out(_cli("--entsperren", UNBEKANNT))

    assert UNBEKANNT not in ausgabe
    # Aber sie sagt, WAS fehlt — ein Support-Fall, der nur sagt
    # "FEHLER", ist keine Hilfe.
    assert "Konto" in ausgabe


def test_leerer_benutzername_bricht_ab(echt_stores):
    assert _cli("--entsperren", "").returncode != 0
    assert _cli().returncode != 0, "ohne --entsperren gibt es nichts zu tun"


# ── 5. Idempotent ───────────────────────────────────────────────────────────


def test_zweimal_aufrufen_ist_unschaedlich(nur_konto):
    """Zweimal ist kein Fehler — auch dann nicht, wenn nichts mehr zu tun ist."""
    erstens = _cli("--entsperren", ZIEL)
    zweitens = _cli("--entsperren", ZIEL)

    assert erstens.returncode == 0, _out(erstens)
    assert zweitens.returncode == 0, _out(zweitens)
    assert "War nicht gesperrt" in _out(zweitens)
    assert not _konto_gesperrt(ZIEL)


# ── 6. Nur ansehen ──────────────────────────────────────────────────────────


def test_status_aendert_nichts(nur_konto):
    gesperrt = _cli("--entsperren", ZIEL, "--status")
    assert gesperrt.returncode == 0, _out(gesperrt)
    assert "Gesperrt" in _out(gesperrt)
    assert _konto_gesperrt(ZIEL), "--status hat etwas geloescht"

    _cli("--entsperren", ZIEL)
    frei = _cli("--entsperren", ZIEL, "--status")
    assert frei.returncode == 0, _out(frei)
    assert "Nicht gesperrt" in _out(frei)


# ── 7. Kein Passwort im Befehl ──────────────────────────────────────────────


def test_es_gibt_kein_passwort_argument(nur_konto):
    """Es gibt kein `--passwort`; ein unbekanntes bricht ab.

    Wichtig fuer die Betriebsregel der Karte: der Befehl **entsperrt**, er
    setzt kein Passwort. Ein spaeterer Umbau, der ein Passwort-Argument
    einbaut, wuerde hier auffallen — und haette es an dieser Stelle zu tun.
    """
    prozess = _cli("--entsperren", ZIEL, "--passwort", "irgendwas")

    assert prozess.returncode != 0, "ein unbekanntes Argument wurde geschluckt"
    assert "unrecognized" in _out(prozess) or "unbekannt" in _out(prozess)
    assert _konto_gesperrt(ZIEL), "es wurde trotzdem etwas getan"


def test_der_befehl_setzt_kein_passwort(nur_konto):
    """Nach der Freigabe ist das gespeicherte Passwort unveraendert.

    Die Karte sagt das ausdruecklich: "Der Befehl entsperrt, er setzt kein
    Passwort. Wenn doch ein neues Passwort noetig wird, ist das eine andere
    Karte." Ein Hash-Vergleich ist die ehrliche Pruefung — die Ausgabe zu
    lesen wuerde nur beweisen, was der Aufrufer selbst gedruckt hat.
    """
    from diakronos_app.db import SessionLocal
    from diakronos_app.frappe_compat.passwoerter import pruefe
    from diakronos_app.models.core import User

    def _hash_lesen() -> str:
        sess = SessionLocal()
        try:
            return sess.query(User).filter(User.name == ZIEL).one().password_hash
        finally:
            sess.close()

    hash_vorher = _hash_lesen()
    assert pruefe(GEHEIM, hash_vorher), "Ausgangslage: Passwort stimmt nicht"

    prozess = _cli("--entsperren", ZIEL)
    assert prozess.returncode == 0, _out(prozess)

    hash_nachher = _hash_lesen()
    assert hash_nachher == hash_vorher, "das Passwort wurde veraendert"
    assert pruefe(GEHEIM, hash_nachher), "das Passwort passt nicht mehr"


# ── 8. Der dokumentierte Befehl ist der, den die Karte nennt ─────────────────


def test_der_einstieg_ist_diakronos_app_loginversuche():
    """`python -m diakronos_app.loginversuche` — genau der aus der Karte.

    Der Store liegt tiefer (`frappe_compat.loginversuche`). Beide Pfade
    dauerhaft anzubieten waere zwei Wege fuer denselben Notfall, die
    auseinanderlaufen koennen; wovor man in einer Fuelle steht, ist der
    kuerzere Pfad. Der Test haelt ihn fest, damit ihn niemand umbenennt und
    die README damit falsch wird.
    """
    from diakronos_app import loginversuche as einstieg

    from diakronos_app.cli_entsperren import main

    assert einstieg.main is main


def test_der_einstieg_importiert_die_logik_nicht_beim_laden_des_stores():
    """`import loginversuche` darf nicht ungefragt die CLI nachziehen.

    Der Store wird bei jedem Anmeldeversuch geladen. Zuege der CLI (argparse,
    models) an diese Stelle gehoeren nicht dorthin — sie machen einen
    haeufigen Pfad abhaengig von einem Werkzeug, das nur im Notfall laeuft.
    """
    import subprocess

    prozess = subprocess.run(
        [sys.executable, "-c",
         "import diakronos_app.frappe_compat.loginversuche as m, sys; "
         "print('cli_entsperren' in sys.modules)"],
        capture_output=True, text=True, timeout=60,
        env={"PYTHONPATH": "/app/src", "PATH": "/usr/local/bin:/usr/bin:/bin"},
    )

    assert prozess.returncode == 0, prozess.stdout + prozess.stderr
    assert prozess.stdout.strip() == "False", (
        "der Store zieht die CLI beim Import nach"
    )


# ── 9. A1c8: der Zaehlerstand, nicht die Sperre ─────────────────────────────
#
# Der Fall, der am Stand von `main` durchging: EIN Benutzer, fuenf erlaubte
# Fehlversuche vom gemeinsamen Internetanschluss. Der Benutzerzaehler sperrt,
# die Adresse steht danach **auf der Schwelle** — der naechste Versuch dieser
# Adresse sperrt sie. Im Store steht keine IP-Sperre, also zaehlte
# `zaehle_gesperrte_ips()` eine Null, der Notweg meldete "aufgehoben" mit
# exit 0 — und die Anmeldung danach gab 401.
#
# Gegenprobe am alten Stand: `git stash` des Quellcodes, dieselben Tests.


def test_der_notweg_meldet_nicht_erledigt_wenn_die_adresse_auf_der_schwelle_steht(
    schwelle_steht,
):
    """**Die Abnahme dieser Karte.** Fall 2: kein "alles erledigt".

    Erwartet wird derselbe Exitcode 2 wie in Fall 1 — nicht weil die Adresse
    gesperrt waere, sondern weil sie beim naechsten Versuch sperrt. Die
    Sperre selbst ist fuer den Aufrufer nicht sichtbar; die *Wirkung* schon.
    """
    prozess = _cli("--entsperren", ZIEL)
    ausgabe = _out(prozess)

    assert not _konto_gesperrt(ZIEL), "das Konto sollte frei sein"
    assert not _ip_gesperrt(IP), "es stand ja keine IP-Sperre im Store"

    # Der IP-Zaehler bleibt **stehen** — das ist der ganze Messfall. Er
    # gehoert dem Konto nicht: `zuruecksetzen_alles` loescht in allen
    # Bereichen die Konto-Schluessel, die Adress-Schluessel bleiben unberuehrt
    # (sonst wuerde der Notweg das halbe Buero mitsperren, siehe Modulkopf
    # `cli_entsperren.py`). Live gemessen, DB 14, **A1c10** mit
    # `login_max_versuche=5` / `login_max_versuche_ip=25`:
    #
    #   VOR  der Freigabe:  ip_zaehler=25  konto_gesperrt=True   im_weg=1
    #   NACH der Freigabe:  ip_zaehler=25  konto_gesperrt=False  im_weg=1
    #   naechster Versuch:  erlaubt=False, Grund 'ip'   <- die 401 der Karte
    #
    # Vor A1c10 stand hier `5` — dieselbe Zahl fuer Konto und Adresse. Die
    # Zahl ist gewandert, die Aussage nicht: der Zaehler gehoert nicht dem
    # Konto, und genau deshalb sperrt der naechste Versuch dieser Adresse.
    #
    # Behauptete dieser Test vorher das Gegenteil ("die Konto-Freigabe hat den
    # IP-Zaehler geleert"), pruefte er den Zustand nach dem Aufraehrweg — und
    # damit genau den nicht.
    assert _ip_zaehler(IP) == ADRESSSCHWELLE, (
        "der IP-Zaehler muss auf der Schwelle stehen bleiben — er ist nicht "
        "der Konto-Zaehler, und genau deshalb sperrt der naechste Versuch"
    )

    assert prozess.returncode == 2, (
        "die Adresse steht auf der Schwelle und sperrt beim naechsten Versuch — "
        f"'alles erledigt' waere eine Luege (Exitcode war {prozess.returncode})"
    )
    # Und er sagt, woran es liegt, ohne die Adresse zu errauten.
    assert "ADRESSE" in ausgabe or "Adresse" in ausgabe, ausgabe
    assert "--ip" in ausgabe, "der zweite Weg wird nicht genannt"
    assert IP not in ausgabe, "die IP wird im Klartext genannt"


def test_der_exitcode_2_beschreibt_auch_hier_die_wirklichkeit(schwelle_steht):
    """Auch hier gilt: nicht nur der Exitcode, sondern der Zustand danach.

    Der alte Notweg meldete in diesem Zustand `0`, waehrend die naechste
    Anmeldung 401 gab. Der Exitcode 2 sagt: **es kann noch scheitern**. Ob es
    das wirklich tut, sagt nur ein Anmeldeversuch — und inzwischen geht er
    durch, weil `--status`/die Konto-Freigabe den ausloesenden Zaehler
    mitgenommen hat.

    A1c8: die Aussage des Exitcodes ist die **Warnung**, nicht die Garantie
    (siehe Docstring `_ip_hinweis`: "der naechste Versuch *kann* 401 geben").
    Diese Vorgaenger-Fassung erwartete noch "es steht noch etwas im Weg und
    deshalb wird der naechste Versuch abgewiesen" — eine Behauptung, die der
    Notweg gar nicht aufstellen kann: welche Adresse im Weg steht, weiss er
    nicht (`pruefe_und_merke` merkt sich die Herkunft nicht, die Schluessel
    sind gesalzen gehasht).
    """
    prozess = _cli("--entsperren", ZIEL)
    assert prozess.returncode == 2, _out(prozess)

    # Und die Gegenprobe, die die ganze Karte traegt: der Zustand **danach**.
    #
    # A1c8: `zuruecksetzen_alles` loescht nur die Konto-Schluessel (`ip=None`
    # ist Absicht, Docstring: "freigegeben wird, wen der Administrator benannt
    # hat"). Der IP-Zaehler bleibt deshalb stehen — genau das ist der Befund.
    # Der naechste Anmeldeversuch dieser Adresse wird damit abgewiesen, obwohl
    # das Konto frei ist. Deshalb exit 2 und nicht 0.
    assert _ip_zaehler(IP) == ADRESSSCHWELLE, (
        "der Zaehler gehoert dem Konto nicht — die Konto-Freigabe laesst ihn stehen"
    )

    # Und der Unterschied ist sichtbar: `--status` sieht nur das **Konto** und
    # meldet 'nicht gesperrt', waehrend die Anmeldung scheitert. Genau diese
    # Verwechslung ist die Luege, gegen die die Karte gebaut ist.
    status = _cli("--entsperren", ZIEL, "--status")
    assert status.returncode == 0, _out(status)
    assert "Nicht gesperrt" in _out(status), _out(status)

    # Erst danach der Anmeldeversuch — er veraendert den Zustand (und sperrt
    # das Konto erneut, weil die Adresse auf der Schwelle steht). Deshalb
    # steht er hier zuletzt und die Aussage ist genau die der Karte: **es
    # steht etwas im Weg**, obwohl das Konto frei war.
    erlaubt, grund = lv.pruefe_und_merke(ZIEL, IP, bereich=lv.BEREICH_LOGIN)
    assert erlaubt is False, (
        "der Notweg meldet 'es steht noch etwas im Weg', der Anmeldeversuch "
        f"ging aber durch (grund={grund!r}) — beides kann nicht stimmen"
    )
    assert grund == "ip", (
        f"abgewiesen wird nicht die Adresse, sondern {grund!r} — "
        "dann prueft dieser Test den Fall der Karte nicht"
    )


def test_der_zaehlerstand_wird_in_der_ausgabe_unterschieden(schwelle_steht):
    """'gesperrt' und 'auf der Schwelle' sind zwei Sachen — der Text auch.

    A1c8: Der Hinweis nennt **beide** Zustaende ausdruecklich, weil der Befehl
    nicht sagen kann, welcher vorliegt. Welche Adresse gesperrt ist und ob
    ueberhaupt eine, steht nicht im Store (gesalzen gehashte Schluessel) —
    deshalb nennt die Ausgabe die Schwelle als eigenen Grund und behauptet
    nicht, es sei eine Sperre.
    """
    ausgabe = _out(_cli("--entsperren", ZIEL))

    assert "schwelle" in ausgabe.lower(), (
        f"der zweite Grund (Zaehler auf der Schwelle) fehlt im Hinweis: {ausgabe}"
    )
    assert "gesperrt" in ausgabe.lower(), (
        f"der erste Grund (Sperre) fehlt im Hinweis: {ausgabe}"
    )
    # Kein geratener Zustand der eigenen Adresse: die Meldung sagt "kann
    # scheitern", nicht "wird scheitern".
    assert "kann noch scheitern" in ausgabe, (
        f"der Hinweis behauptet mehr, als der Store hergibt: {ausgabe}"
    )


def test_drei_vertippten_loesen_keinen_alarm_aus(echt_stores):
    """Der Alltagsfall bleibt still: `nur_konto` ist der Normalfall.

    Wird der Exitcode hier uebertrieben muendlich, bricht jedes Skript im
    Alltag aus — und der Exitcode 2 waere dann wertlos, weil er immer kaeme.
    """
    from diakronos_app.db import SessionLocal
    from diakronos_app.frappe_compat.passwoerter import neuer_hash
    from diakronos_app.models.core import User

    sess = SessionLocal()
    try:
        sess.add(User(
            name=ZIEL, email=ZIEL, full_name=ZIEL, enabled=True,
            password_hash=neuer_hash(GEHEIM),
        ))
        sess.commit()
    finally:
        sess.close()

    # Drei Fehlversuche: der uebliche Fall, niemand ist gesperrt.
    for _ in range(3):
        lv.pruefe_und_merke(ZIEL, IP, bereich=lv.BEREICH_LOGIN)

    assert not _konto_gesperrt(ZIEL), "drei Versuche sperren nicht"
    assert not _ip_gesperrt(IP)
    assert _ip_zaehler(IP) == 3

    prozess = _cli("--entsperren", ZIEL)

    assert prozess.returncode == 0, _out(prozess)
    assert "ADRESSE" not in _out(prozess), "die Warnung kommt ohne Anlass"
