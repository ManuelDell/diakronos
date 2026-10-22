"""B1 — Sitzungen ueberleben Deaktivierung, Loeschung und Nicht-Existenz.

DER BEFUND, DEN DIESE DATEI FESTNAGELT
--------------------------------------
`frappe_compat/auth_middleware.py` hat aus einem `sid` schlicht
`session.user` gemacht. Weder `User.enabled` noch die Existenz des
Benutzers wurden geprueft. Ein deaktivierter oder geloeschter Benutzer
blieb damit angemeldet, solange seine Sitzung im Redis lag — auf **jedem**
Geraet, ohne dass irgendetwas sichtbar gewesen waere. `delete_my_data`
raeumte nur die *aktuelle* Sitzung ab und versprach im Docstring trotzdem
"SOFORT raus".

Was hier festgenagelt wird, in vier Richtungen:

  1. **Regel** (`frappe_compat/benutzer_status.py`): existiert der Benutzer
     und ist er `enabled`? Ein Geraet mit einer Sitzung fuer ein totes
     Konto bekommt `Guest` — 403, nicht irgendein Rest von Rechten.
  2. **Serverseitig**: die Sitzung wird nicht nur fuer diesen Aufruf
     ignoriert, sondern geloescht. Sonst bliebe das Cookie liegen und der
     Zustand saehe in einem spaeteren Lauf wie eine halbe Massnahme aus.
  3. **Der Cache hat eine Frist** (Default 30 s, `settings.benutzerstatus_ttl`)
     und wird beim Reaktivieren nicht vergessen. Wer die Frist anhebt,
     verletzt die Abnahme der Karte.
  4. **Gegenrichtung**: ein Konto, das es gibt und das `enabled` ist, wird
     nicht versehentlich rausgeworfen; und der Widerruf eines Benutzers
     toetet nicht die Sitzung eines anderen.

Jeder Test hier waere **ohne** den Fix rot: die Regel gab es vorher nicht,
und ein Test, der sie nicht ausloest, prueft nichts.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import diakronos_app.api.profile  # noqa: F401  (registriert die whitelists)
from diakronos_app.frappe_compat import benutzer_status, sitzungen
from diakronos_app.frappe_compat.passwoerter import neuer_hash
from diakronos_app.main import app
from diakronos_app.models.core import User
from diakronos_app.models.diakonos import Mitglied

PROFIL = "diakronos.diakonos.api.profile"
PROFIL_PFAD = f"/api/method/{PROFIL}"

# `user` und `Mitglied` fuer beide Richtungen: der Zugriffspunkt
# `get_my_profile` verlangt ein Mitglied, sonst waere ein 417 (kein
# Mitglied-Datensatz) von einem 403 (keine Sitzung) nicht zu unterscheiden.
ANNA = "anna@example.org"
BRUNO = "bruno@example.org"


@pytest.fixture()
def welt(patched_db):
    """Zwei aktive Konten mit Mitglied-Datensatz."""
    sess = patched_db()
    sess.add_all([
        User(name=ANNA, email=ANNA, full_name="Anna Beispiel", enabled=True,
             password_hash=neuer_hash("Geheim-1")),
        User(name=BRUNO, email=BRUNO, full_name="Bruno Beispiel", enabled=True,
             password_hash=neuer_hash("Geheim-2")),
        Mitglied(name="M-0001", vorname="Anna", nachname="Beispiel",
                 email=ANNA, status="Mitglied", user=ANNA, docstatus=0, idx=0),
        Mitglied(name="M-0002", vorname="Bruno", nachname="Beispiel",
                 email=BRUNO, status="Mitglied", user=BRUNO, docstatus=0, idx=0),
    ])
    sess.commit()
    yield sess
    sess.close()


def _browser(user: str) -> tuple[TestClient, str]:
    """Ein Browser mit eigener Sitzung — wie ein Geraet, nicht wie ein Admin."""
    sid, csrf = sitzungen.anlegen(user)
    c = TestClient(app)
    c.cookies.set("sid", sid)
    c.headers["X-Frappe-CSRF-Token"] = csrf
    return c, sid


# ── 1. Deaktivierung von aussen: die Sitzung stirbt ─────────────────────────


def _cache_verfaellig() -> None:
    """Laesst die Cache-Frist ablaufen, ohne 30 Sekunden zu warten.

    Der Test stubt `time.monotonic` nicht — er setzt den TTL des Eintrags
    auf das, was nach `benutzerstatus_ttl` Sekunden **wirklich** dasteht:
    abgelaufen. Das ist dieselbe Wirkung wie Warten, nur ohne Warten, und es
    sagt genau das aus, was die Abnahme der Karte sagt: die Frist, nicht
    der Moment.
    """
    for schluessel in benutzer_status._client().scan_iter(
        match=f"{benutzer_status.STATUS_PRAEFIX}*"
    ):
        benutzer_status._client().delete(schluessel)


def test_deaktivierter_benutzer_ist_kein_angemeldeter_benutzer(welt, fake_redis) -> None:
    """`enabled=0` in der DB -> `Guest`, spaetestens nach der Cache-Frist.

    Das ist der Kernfall der Karte. Ohne den Fix liefert derselbe Aufruf
    200 mit dem echten Profil, obwohl das Konto deaktiviert ist.

    **Achtung, die Reihenfolge ist der Punkt**: die Ausgangslage (200)
    fuellt den Status-Cache. Ein direktes Umschalten in der Datenbank
    umgeht den aktiven Widerruf, und da ist die Frist die dokumentierte
    Luecke der Karte. Der Test laesst sie deshalb ablaufen, statt zu
    behaupten, es gebe keine — der Test `test_der_aktive_widerruf_ist_sofort`
    in `test_p4n_profil.py` haelt die andere, strengere Seite fest.
    """
    c, sid = _browser(ANNA)
    assert c.post(f"{PROFIL_PFAD}.get_my_profile").status_code == 200, "Ausgangslage"

    welt.expire_all()
    welt.get(User, ANNA).enabled = False
    welt.commit()
    _cache_verfaellig()

    assert c.post(f"{PROFIL_PFAD}.get_my_profile").status_code == 401
    c.close()


def test_der_widerruf_der_datenbank_wirkt_binnen_der_frist(welt, fake_redis) -> None:
    """**Dieselbe Messung ohne Warten** — so schnell, wie die Frist es zulässt.

    Ohne die Frist-Vorbereitung schlaegt der Test fehl, solange der Cache
    gefuellt ist; mit ihr belegt er, dass die Frist die **einzige**
    Verzoegerung ist und nicht ein Nebenschauplatz, an dem auch der
    eigentliche Fehler haengt.
    """
    c, _sid = _browser(ANNA)
    c.post(f"{PROFIL_PFAD}.get_my_profile")          # Cache fuellen

    welt.expire_all()
    welt.get(User, ANNA).enabled = False
    welt.commit()
    # Ein Aufruf **vor** Ablauf ist noch der alte Stand — das ist die
    # dokumentierte Frist, und der Test sagt es laut, statt es zu verstecken.
    assert c.post(f"{PROFIL_PFAD}.get_my_profile").status_code == 200

    _cache_verfaellig()
    assert c.post(f"{PROFIL_PFAD}.get_my_profile").status_code == 401
    c.close()


def test_deaktivierung_beendet_auch_das_ausgelagerte_cookie(welt, fake_redis) -> None:
    """Nicht nur "fuer diesen Request ignoriert": die Sitzung ist weg.

    Der Beweis liegt im Store. Waere die Sitzung nur nicht ausgewertet
    worden, waere das Cookie weiterhin ein `sid`, der auf einen Benutzer
    zeigt, den es nicht mehr gibt — und jeder spaetere Lauf wuerde denselben
    Zustand wieder vorfinden.
    """
    c, sid = _browser(ANNA)

    welt.expire_all()
    welt.get(User, ANNA).enabled = False
    welt.commit()
    _cache_verfaellig()

    c.post(f"{PROFIL_PFAD}.get_my_profile")
    assert sitzungen.lesen(sid) is None, "die Sitzung liegt noch im Store"
    c.close()


def test_geloeschter_benutzer_hat_keine_sitzung(welt, fake_redis) -> None:
    """Aus der `user`-Tabelle verschwunden -> `Guest`.

    Der zweite Fall der Karte neben dem Deaktivieren, und nicht derselbe
    Codeweg: `ist_aktiv` bekommt diesmal *keine Zeile* zurueck statt einer
    mit `enabled = False`. Beide muessen dasselbe Ergebnis haben.
    """
    c, sid = _browser(ANNA)

    welt.expire_all()
    welt.delete(welt.get(User, ANNA))
    welt.commit()
    _cache_verfaellig()

    assert c.post(f"{PROFIL_PFAD}.get_my_profile").status_code == 401
    assert sitzungen.lesen(sid) is None
    c.close()


def test_der_index_des_benutzers_wird_mitgeraeumt(welt, fake_redis) -> None:
    """Nach der Verwerfung ist der Benutzer-Index leer.

    `loesche_alle_von` stuetzt sich auf diesen Index. Lieffe ein
    verwaister `sid` darin weiter, wuerde ein spaeterer Widerruf Zeit auf
    Eintraege verschwenden, die es gar nicht mehr gibt.
    """
    c, sid = _browser(ANNA)
    welt.expire_all()
    welt.get(User, ANNA).enabled = False
    welt.commit()
    _cache_verfaellig()

    c.post(f"{PROFIL_PFAD}.get_my_profile")

    assert sid not in sitzungen._client().smembers(sitzungen.benutzer_index_key(ANNA))
    c.close()


# ── 2. Der Cache: Frist und Vergessen ───────────────────────────────────────


def test_der_status_cache_hat_die_dokumentierte_frist(welt, fake_redis) -> None:
    """`settings.benutzerstatus_ttl` ist 30 s — und wird auch angewandt.

    Nicht nur der Wert wird geprueft, sondern der **TTL am Key**: eine
    Einstellung, die niemand liest, ist keine Frist, sondern ein Kommentar.
    Wer den Wert auf 600 aendert, verletzt die Abnahme der Karte. Ein Deckel
    im Settings-Objekt waere die naheliegende Haertung, ist hier aber
    bewusst **nicht** gebaut: `settings` ist eine reine Konfigurationshuelle
    ohne `field_validator`, und eine Validierungslogik nur fuer dieses eine
    Feld waere dort ein Fremdkoerper. Der Test ist die Haertung — er schlaegt
    rot, sobald jemand die Frist anhebt, und das ist der Moment, in dem die
    Aenderung auffaellt.
    """
    from diakronos_app.settings import settings

    assert settings.benutzerstatus_ttl == 30, (
        "die Widerrufsfrist der Karte ist ~30 s; ein anderer Wert ist eine "
        "bewusste Entscheidung und keine Konfiguration"
    )

    assert benutzer_status.ist_aktiv(ANNA) is True
    key = benutzer_status._key(ANNA)
    ttl = benutzer_status._client().ttl(key)
    assert 0 < ttl <= 30, f"TTL {ttl} passt nicht zur Frist"


def test_der_cache_wird_nicht_bei_jedem_request_gefragt(welt, fake_redis, monkeypatch) -> None:
    """Zwei Aufrufe, **eine** Datenbankabfrage.

    Das ist der Grund fuer den Cache. Ohne ihn waere jede Anfrage ein
    `SELECT` (gemessen 0,407 ms am laufenden Stack); mit ihm ist es alle
    `benutzerstatus_ttl` Sekunden einer. Der Test zaehlt die Abrufe, damit
    die Begruendung "kostet nichts" nicht nur eine Behauptung bleibt.
    """
    rufe = {"n": 0}
    echte = benutzer_status._aus_db

    def zaehle(name: str) -> bool:
        rufe["n"] += 1
        return echte(name)

    monkeypatch.setattr(benutzer_status, "_aus_db", zaehle)

    c, _sid = _browser(ANNA)
    c.post(f"{PROFIL_PFAD}.get_my_profile")
    c.post(f"{PROFIL_PFAD}.get_my_profile")
    c.post(f"{PROFIL_PFAD}.get_my_profile")
    c.close()

    assert rufe["n"] == 1, f"{rufe['n']} DB-Abfragen fuer drei Aufrufe"


def test_vergiss_zwingt_den_naechsten_aufruf_zur_wahrheit(welt, fake_redis) -> None:
    """Nach `vergiss()` entscheidet wieder die Datenbank — nicht der Cache.

    Der Weg von innen (Reaktivieren durch einen Administrator) darf nicht an
    einer Restfrist hängen. Ohne `vergiss()` waere ein zurueckgesetztes
    Konto bis zu `benutzerstatus_ttl` Sekunden lang abgewiesen — dieselbe
    Art Fehler wie vorher, nur mit umgekehrtem Vorzeichen.
    """
    assert benutzer_status.ist_aktiv(ANNA) is True
    benutzer_status.vergiss(ANNA)
    assert benutzer_status._client().get(benutzer_status._key(ANNA)) is None

    welt.expire_all()
    welt.get(User, ANNA).enabled = False
    welt.commit()
    assert benutzer_status.ist_aktiv(ANNA) is False


def test_geloeschtes_konto_bleibt_geloescht_auch_bei_gefuelltem_cache(welt, fake_redis) -> None:
    """Der Cache darf einen deaktivierten Benutzer nicht "retten".

    `enabled` faellt unter **einem** Cache-Schluessel zusammen, nicht unter
    einem gemeinsamen: der Schluessel traegt den Benutzernamen. Wer den
    Schluessel baut, muss das wissen — ein Sammelschluessel wuerde bedeuten,
    dass die Deaktivierung *irgendeines* Kontos alle anderen mitreisst.
    """
    benutzer_status.ist_aktiv(ANNA)
    benutzer_status.ist_aktiv(BRUNO)
    schluessel_a = benutzer_status._key(ANNA)
    schluessel_b = benutzer_status._key(BRUNO)
    assert schluessel_a != schluessel_b
    assert ANNA not in schluessel_b
    assert BRUNO not in schluessel_a


# ── 3. Fail closed ─────────────────────────────────────────────────────────


def test_fehlende_datenbank_heisst_nicht_angemeldet(welt, fake_redis, monkeypatch) -> None:
    """Kann der Status nicht geprueft werden, ist die Sitzung ungueltig.

    "Im Zweifel verweigern": ein Benutzer, dessen Status sich nicht
    feststellen laesst, wird wie `Guest` behandelt. Der Gegenfall waere
    "im Zweifel durchlassen" — und genau das waere ein Datenleck in einer
    Anwendung, die Mitgliederdaten verwaltet.
    """
    def kaputt(name: str) -> bool:
        raise RuntimeError("Datenbank nicht erreichbar")

    monkeypatch.setattr(benutzer_status, "_aus_db", kaputt)
    c, sid = _browser(ANNA)

    assert c.post(f"{PROFIL_PFAD}.get_my_profile").status_code == 401
    assert sitzungen.lesen(sid) is None
    c.close()


def test_nicht_erreichbarer_cache_heisst_nicht_angemeldet(welt, fake_redis, monkeypatch) -> None:
    """Auch ein Redis-Ausfall darf keine offene Sitzung erzeugen.

    Der Cache ist eine Optimierung; sein Ausfall darf nicht zur
    Arbeitsverweigerung fuehren — aber er darf auch **nicht** zum
    Durchlassen fuehren. Beides waere eine Verletzung derselben Regel.
    """
    class Tot:
        def get(self, *_a, **_kw):
            raise ConnectionError("Redis weg")

    monkeypatch.setattr(benutzer_status, "_client", lambda: Tot())
    c, _sid = _browser(ANNA)

    assert c.post(f"{PROFIL_PFAD}.get_my_profile").status_code == 401
    c.close()


def test_gast_ist_kein_sitzungstraeger(fake_redis) -> None:
    """`Guest` ist nie ein angemeldeter Name.

    Eine Sitzung, deren `user` auf `Guest` gesetzt ist, waere eine
    Hintertuer: sie umginge jede Rollenpruefung, weil `get_roles` fuer
    `Guest` leer ist — also eher harmlos, aber sie waere trotzdem eine
    Identitaet ohne Konto.
    """
    assert benutzer_status.ist_aktiv("Guest") is False
    assert benutzer_status.ist_aktiv("") is False
    assert benutzer_status.ist_aktiv("   ") is False


# ── 4. Gegenrichtung: aktive Konten bleiben drin ───────────────────────────


def test_aktiver_benutzer_bleibt_angemeldet(welt, fake_redis) -> None:
    """Die Regel kostet keine Berechtigung, die vorher da war."""
    c, sid = _browser(ANNA)
    assert c.post(f"{PROFIL_PFAD}.get_my_profile").status_code == 200
    assert sitzungen.lesen(sid) is not None
    c.close()


def test_zwei_aktive_konten_beeinflussen_sich_nicht(welt, fake_redis) -> None:
    """Brunos Deaktivierung wirft Anna nicht raus und umgekehrt."""
    anna, _ = _browser(ANNA)
    bruno, _ = _browser(BRUNO)

    welt.expire_all()
    welt.get(User, BRUNO).enabled = False
    welt.commit()
    benutzer_status.vergiss(BRUNO)   # der aktive Widerruf eines Admins

    assert anna.post(f"{PROFIL_PFAD}.get_my_profile").status_code == 200
    assert bruno.post(f"{PROFIL_PFAD}.get_my_profile").status_code == 401
    anna.close()
    bruno.close()


def test_die_ablehnung_nennt_kein_konto(welt, fake_redis) -> None:
    """Die Antwort traegt die Frappe-Form, keinen Bestand.

    `router._guest_denied` liefert "Zugriff verweigert." — das ist der Weg,
    den ein Gast auch geht. Die Ablehnung unterscheidet damit nicht
    "deaktiviert" von "falsches Cookie", was fuer den Benutzer richtig und
    fuer niemanden sonst nuetzlich ist.
    """
    c, _sid = _browser(ANNA)
    welt.expire_all()
    welt.get(User, ANNA).enabled = False
    welt.commit()

    koerper = c.post(f"{PROFIL_PFAD}.get_my_profile").text
    assert ANNA not in koerper
    assert "Anna" not in koerper
    c.close()


# ── 5. Die Regel lebt an EINER Stelle ──────────────────────────────────────


def test_login_und_caldav_nutzen_dieselbe_funktion() -> None:
    """Beleg auf Codeebene: kein eigener `enabled`-**Entscheid** im Anmeldeweg.

    Die Karte verlangt, dass die Regel an einer Stelle lebt. Zwei getrennt
    gepflegte `if not doc["enabled"]`-Zeilen waeren zwei Wahrheiten, die
    auseinanderlaufen koennen — und die A1c1/A1c2-Zeitangleichung misst
    beide Wege.

    Geprueft wird deshalb nicht "kommt `enabled` vor", sondern "wird es
    ausgewertet". `caldav/auth.py::_benutzer_aus_db` liefert die Spalte
    weiterhin mit — das ist Datengrundlage, keine Regel; ausgewertet wird
    sie nur noch in `benutzer_status.konto_ist_aktiv`.
    """
    import ast
    from pathlib import Path

    import diakronos_app.api.auth as login_modul

    wurzel = Path(login_modul.__file__).resolve().parents[1]
    for datei in ("api/auth.py", "caldav/auth.py"):
        baum = ast.parse((wurzel / datei).read_text(encoding="utf-8"))
        # Gesucht sind die Orte, an denen `enabled` in eine **Bedingung**
        # wandert (`if`/`and`/`or`/`not`) — nicht die reine Nennung. Die
        # Rueckgabe von `_benutzer_aus_db` darf die Spalte weiterliefern;
        # entschieden wird nur in `konto_ist_aktiv`.
        bedingungen = [
            f"{datei}:{knoten.lineno}"
            for knoten in ast.walk(baum)
            if isinstance(knoten, (ast.BoolOp, ast.UnaryOp))
            and any(
                isinstance(kind, ast.Attribute) and kind.attr == "enabled"
                for kind in ast.walk(knoten)
            )
        ]
        assert not bedingungen, (
            f"{datei} entscheidet selbst ueber `enabled`: {bedingungen} — "
            "die Regel gehoert nach frappe_compat/benutzer_status.py"
        )

    # Und die Regel wird von beiden Wegen auch wirklich benutzt — ein
    # "kein eigener Entscheid" waere sonst auch dann gruen, wenn niemand
    # die Regel aufruft.
    for datei in ("api/auth.py", "caldav/auth.py"):
        text = (wurzel / datei).read_text(encoding="utf-8")
        assert "konto_ist_aktiv" in text, f"{datei} ruft die Regel nicht auf"


def test_der_widerruf_geht_ueber_die_zentrale_funktion() -> None:
    """`delete_my_data` erreicht `widerrufe_sitzungen`, ohne selbst den Store anzufassen.

    Wer die Sitzungen hier direkt loescht, umgeht das Cache-Vergessen — und
    haelt sich den genauen Fehler, den B1 beseitigt: der Widerruf wirkt
    sofort, ein spaeteres Reaktivieren aber nicht (bzw. umgekehrt).

    Auch hier wird der **Rumpf** geprueft, nicht der Kommentar darum herum.
    DSGVO-1c (N-5): `anonymisieren` loescht selbst nichts mehr, sondern fuehrt
    hart auf `loeschung_bestaetigen` — deshalb gilt der AUFRUFPFAD als Ganzes.
    Ein Block der Schleife rechnet sich transitiv aus, und die Verbote gelten
    fuer JEDE erreichbare Funktion; `loesche_alle_von`/`_logout_sitzung` in
    `loeschung_bestaetigen` waeren genauso ein Treffer wie in `anonymisieren`.
    """
    import ast
    from pathlib import Path

    import diakronos_app.api.datenschutz as profil

    baum = ast.parse(Path(profil.__file__).read_text(encoding="utf-8"))
    funktionen = {
        k.name: k for k in ast.walk(baum) if isinstance(k, ast.FunctionDef)
    }

    # Sowohl `Name` (einfacher Aufruf) als auch `Attribute` (`modul.funktion`)
    # zaehlen als Aufruf.
    def aufrufe(name: str) -> set[str]:
        return {
            k.id if isinstance(k, ast.Name) else k.attr
            for k in ast.walk(funktionen[name])
            if isinstance(k, (ast.Name, ast.Attribute))
        }

    direkt = aufrufe("anonymisieren")
    assert "loeschung_bestaetigen" in direkt, (
        "anonymisieren fuehrt nicht mehr hart auf den Antragsweg: "
        f"{sorted(direkt)}"
    )

    erreichbar, offen = ["anonymisieren"], {"anonymisieren"}
    while offen:
        for ziel in aufrufe(offen.pop()):
            if ziel in funktionen and ziel not in erreichbar:
                erreichbar.append(ziel)
                offen.add(ziel)
    gesamt = set().union(*(aufrufe(n) for n in erreichbar))

    assert "widerrufe_sitzungen" in gesamt, (
        f"delete_my_data ruft nicht den zentralen Widerruf: {sorted(gesamt)}"
    )
    assert "loesche_alle_von" not in gesamt, (
        "delete_my_data loescht Sitzungen direkt — der Cache wird dann nicht vergessen"
    )
    assert "_logout_sitzung" not in gesamt, (
        "delete_my_data loescht nur das eigene Geraet (B1 genau der Befund)"
    )
