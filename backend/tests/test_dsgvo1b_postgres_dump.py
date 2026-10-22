"""DSGVO-1b: die Löschung gegen eine KOPIE des Betriebs-Dumps.

WARUM GEGEN ECHTE DATEN
-----------------------
Die DSGVO-1-Suite lief auf einer leeren SQLite-Datenbank mit technischen
Kennungen („D1-anna“). Genau darum blieben die Befunde aus R-DSGVO-1
unentdeckt: im Betrieb ist `mitglied.name` der KLARNAME („Hans Beispiel“), die
FKs zeigen auf echte Zeilen, und es gibt JSON-Spalten mit Personenwerten
(`pr_eintrag.wert`, `pr_verlauf.*`, `pr_plan.veroeffentlichter_stand`).

Dieser Test läuft gegen eine Kopie des neuesten Betriebs-Dumps
(`data/sicherung-vor-*/db.sql.gz`) in einem Wegwerf-PostgreSQL:

    DSGVO1B_POSTGRES_URL=postgresql+psycopg://…/…_test \\
    DSGVO1B_DUMP=<pfad/zu/db.sql.gz> \\
    pytest tests/test_dsgvo1b_postgres_dump.py

Ohne die Variablen wird übersprungen. Der Test SCHREIBT nur in die
Wegwerf-Datenbank; der Dump wird ausschließlich gelesen.
"""
from __future__ import annotations

import os
import re

import pytest
from sqlalchemy import create_engine, text

pytestmark = pytest.mark.skipif(
    not os.environ.get("DSGVO1B_POSTGRES_URL"),
    reason="nur mit DSGVO1B_POSTGRES_URL (Wegwerf-PostgreSQL mit Dump-Kopie)",
)

def _url() -> str:
    url = str(os.environ["DSGVO1B_POSTGRES_URL"])
    assert "_test" in url, "DSGVO1B_POSTGRES_URL muss eine Wegwerf-Datenbank sein (*_test)"
    return url


def _person(url: str, ueberspringe: int = 0) -> dict:
    """Eine ECHTE Person aus der Kopie (Klarname als Kennung, wie im Betrieb).

    `ueberspringe` lässt bereits gelöschte Personen aus — die beiden Tests
    teilen sich eine Wegwerf-Datenbank, und der zweite darf nicht dieselbe
    Person noch einmal löschen wollen.
    """
    eng = create_engine(url, future=True)
    with eng.connect() as c:
        zeile = c.execute(text(
            "select name, vorname, nachname, email, telefonnummer, wohnort, "
            "postleitzahl, geburtstag, \"user\", foto, notiz "
            "from mitglied "
            "where vorname is not null and nachname is not null "
            "  and email is not null and email <> '' "
            "  and status <> 'geloescht' "
            "  and name = vorname || ' ' || nachname "  # Klarname ALS Kennung
            "order by name limit 1 offset :n"
        ), {"n": ueberspringe}).mappings().first()
    eng.dispose()
    assert zeile is not None, (
        "keine Person mit Klarname als Kennung in der Kopie — der Test würde "
        "die Betriebslage nicht abbilden"
    )
    return dict(zeile)


#: Präfixe, unter denen Testkennungen im Betrieb NICHT vorkommen: `geloescht-`
#: (unsere neutrale Kennung), `email:`/`name:` (eigene Wegwerf-Konten dieses
#: Tests) und die Vorsilbe `test`, die nur Seed-/Testzeilen tragen.
_TESTKENNUNG = re.compile(r"^(geloescht-|email:|name:|test)", re.IGNORECASE)


def _dienstkonto(url: str) -> dict[str, str]:
    """Eine ECHTE Person, deren Adresse NUR noch als Wert in der DB steht.

    `mitglied.user` ist im Betrieb oft leer. Ist die `user`-Zeile zusätzlich
    von Hand gelöscht worden, steht die Adresse nur noch in Spalten ohne
    Fremdschlüssel (`has_role.parent`, `dienstbereich_verantwortlicher.user`).
    Genau dieser Fall blieb in der Kopie stehen.

    Die Kopie selbst hat keine Zeile in diesem Zustand (geprüft: jede
    Mitgliedsadresse mit Rollen hat eine `user`-Zeile), deshalb wird er aus
    einer echten Person HERGESTELLT — in der Wegwerf-DB, nicht im Betrieb.
    """
    eng = create_engine(url, future=True)
    with eng.connect() as c:
        for zeile in c.execute(text(
            "select m.name, m.email from mitglied m "
            "where m.email is not null and m.email <> '' and m.status <> 'geloescht' "
            "  and m.name = m.vorname || ' ' || m.nachname "
            "order by m.name"
        )).mappings():
            if _TESTKENNUNG.match(str(zeile["name"])):
                continue
            konto = str(zeile["email"])
            if _TESTKENNUNG.match(konto) or _TESTKENNUNG.match(konto.split("@")[0]):
                continue
            return {"name": str(zeile["name"]), "konto": konto}
    eng.dispose()
    pytest.skip("keine echte Person mit Klarname-Kennung in der Kopie")


#: Wert-Spalten, die auf `user.name` zeigen OHNE dass es eine FK ist (N-2).
#: Beide Helfer brauchen dieselbe Liste: vor dem Weg der Konto-Zeile müssen
#: sie frei sein, sonst blockiert die Fremdschluessel den Löschvorgang.
WERT_SPALTEN_KONTO = (
    ("dienstbereich_verantwortlicher", "user"),
    ("gruppe_verantwortlicher", "user"),
    ("untergruppe_verantwortlicher", "user"),
    ("kalender_moderator", "user"),
    ("nutzereinzelrechte", "nutzer"),
    ("user_notification_preference", "user"),
    ("dashboard_widget_user_config", "user"),
    ("kronos_kanban_zustand", "user"),
)


def _nur_als_wert(url: str, mitglied: str, konto: str) -> None:
    """Adresse nur noch als WERT in der DB: keine `user`-Zeile, `user`-Link weg.

    Legt vorher die beiden Wert-Spalten an, die es im Betrieb gibt: eine
    Rollenzeile und die Verantwortung für einen Dienstbereich.
    """
    eng = create_engine(url, future=True)
    with eng.begin() as c:
        c.execute(text('update mitglied set "user" = null where name = :m'),
                  {"m": mitglied})
        # Die FK-Spalten muessen frei sein, bevor die Konto-Zeile fallen kann —
        # das ist der Zustand "Konto von Hand geloescht".
        for t, s in WERT_SPALTEN_KONTO:
            c.execute(text(f'update "{t}" set "{s}" = null where "{s}" = :k'), {"k": konto})
        c.execute(text("delete from has_role where parent = :k"), {"k": konto})
        c.execute(text('delete from passwortzugang where "user" = :k'), {"k": konto})
        c.execute(text('delete from "user" where name = :k'), {"k": konto})
        c.execute(text("insert into has_role(name, parent, parenttype, parentfield, "
                       "role, docstatus, idx) values (:n, :k, 'User', 'roles', "
                       "'Mitglied', 0, 0)"), {"n": f"dsgvo1b-{konto}", "k": konto})
    eng.dispose()


def _pg_konto(eng, konto: str, anzeigename: str, antrag: bool,
              mitglied: str | None) -> None:
    """Konto (und Antrag) direkt anlegen — die Kopie bringt keine Sitzung mit."""
    with eng.begin() as c:
        if antrag and mitglied:
            c.execute(text("insert into loeschantrag(mitglied, beantragt_am, status) "
                           "values (:m, now(), 'offen')"), {"m": mitglied})
        c.execute(text('insert into "user"(name, email, full_name, enabled) '
                       "values (:k, :k, :n, true)"), {"k": konto, "n": anzeigename})
        if mitglied:
            c.execute(text('update mitglied set "user" = :k where name = :m'),
                      {"k": konto, "m": mitglied})


def _konten_wie_produktion(c, mitglied: str, konto: str) -> set[str]:
    """Kontenliste wie `api/datenschutz._konten` — nur gegen DIESE Datenbank.

    Produktiv ist `_kontozustand` an die Aufruf-Sitzung gebunden. Hier wird die
    Verbindung der Wegwerf-Kopie ausdrücklich übergeben, damit die Abfrage
    nicht (wie unter `conftest.patched_db` in der SQLite-Suite) auf die
    Test-Datenbank zeigt.
    """
    from diakronos_app.frappe_compat.benutzer_status import wirksame_konten

    konten = [dict(r) for r in c.execute(text(
        'select name, email, enabled from "user"')).mappings()]
    zeile = c.execute(text("select name, \"user\", email, ausgeschlossen "
                           "from mitglied where name = :m"),
                      {"m": mitglied}).mappings().one()
    return wirksame_konten(dict(zeile), _mitglieder=[dict(zeile)], _konten=konten)


def _loesche(url: str, mitglied: str, konten: set[str]) -> str:
    """`anonymisiere` gegen die Wegwerf-Kopie; gibt die neue Kennung zurück."""
    import diakronos_app.db as dbmod
    import diakronos_app.models  # noqa: F401
    from sqlalchemy.orm import sessionmaker

    from diakronos_app.dsgvo_anonymisierung import anonymisiere

    eng = create_engine(url, future=True)
    factory = sessionmaker(bind=eng, autoflush=False, autocommit=False, future=True)
    alt_engine, alt_factory = dbmod.engine, dbmod.SessionLocal
    dbmod.engine, dbmod.SessionLocal = eng, factory
    try:
        with factory.begin() as s:
            ergebnis = anonymisiere(s, mitglied, konten, dateien=[])
    finally:
        dbmod.engine, dbmod.SessionLocal = alt_engine, alt_factory
        eng.dispose()
    kennung = ergebnis["kennung"]
    assert re.fullmatch(r"geloescht-[0-9a-f]{32}", kennung), kennung
    return kennung


def _nadeln(p: dict) -> list[str]:
    """Nur Werte, die die Person EINDEUTIG identifizieren.

    Bewusste Fachentscheidung (K2): einzelne Vornamen, Wohnort und PLZ werden
    in fremden Texten NICHT angetastet — „Anna“ steckt in „Hanna“ und
    „Hosianna“, „Stuttgart“ bei neun anderen Mitgliedern. Ein Scan auf diese
    Wörter würde fremde Daten als Rest melden und die richtige Löschung als
    Fehler erscheinen lassen.
    """
    werte = [p["name"], p["email"], str(p["email"]).split("@")[0]]
    # Telefon und der Foto-Pfad sind eindeutig; Wohnort/PLZ/Notiz NICHT —
    # sie stehen auch bei anderen Mitgliedern (`mitglied.wohnort = 'Stuttgart'`
    # bei neun Personen der Kopie).
    for feld in ("telefonnummer", "foto"):
        if p.get(feld):
            werte.append(str(p[feld]))
    if p.get("telefonnummer"):
        ziffern = "".join(z for z in str(p["telefonnummer"]) if z.isdigit())
        if len(ziffern) >= 6:
            werte.append(ziffern)
    return sorted({w for w in werte if len(str(w)) >= 3}, key=len, reverse=True)


def _scan(eng) -> list[tuple[str, str, str, str]]:
    """Ganze DB (auch JSON) nach jedem Textwert durchsuchen.

    Läuft über `information_schema`: die Betriebs-Kopie kann Spalten tragen,
    die im Modell fehlen (Overlay-Spalten) — der Vollscan muss die Datenbank
    prüfen, nicht das Modell.
    """
    treffer = []
    with eng.connect() as c:
        tabellen = [r[0] for r in c.execute(text(
            "select table_name from information_schema.tables "
            "where table_schema='public' and table_type='BASE TABLE' "
            "and table_name <> 'alembic_version' order by 1"))]
        for t in tabellen:
            spalten = [r[0] for r in c.execute(text(
                "select column_name from information_schema.columns "
                "where table_schema='public' and table_name = :t "
                "order by ordinal_position"), {"t": t})]
            # Eine Abfrage je Tabelle, alle Spalten als Text.
            ausdruck = ", ".join(f'"{s}"::text' for s in spalten)
            for zeile in c.execute(text(f'select {ausdruck} from public."{t}"')):
                for spalte, wert in zip(spalten, zeile):
                    if wert is None:
                        continue
                    treffer.append((t, spalte, str(wert)))
    return treffer


def _rest(treffer, nadeln) -> list[tuple[str, str, str, str]]:
    reste = []
    for tabelle, spalte, wert in treffer:
        klein = wert.lower()
        for nadel in nadeln:
            if str(nadel).lower() in klein:
                reste.append((tabelle, spalte, str(nadel), wert[:90]))
                break
    return reste


def _raeume_auf(eng, mitglied: str, konto: str) -> None:
    """Macht den Test wiederholbar: liegt die Testperson noch da, neu beginnen.

    Der Test arbeitet in einer WEGWERF-Kopie; ein zweiter Lauf (etwa nach einem
    Fehlschlag) darf nicht an einem Rest aus dem ersten scheitern.
    """
    with eng.begin() as c:
        # Nachweise und Verweise der alten Test-Kennungen zuerst entfernen
        # (sonst blockiert die FK), dann die Zeile selbst.
        for name in list(c.execute(text(
                "select name from mitglied where name like 'geloescht-%'")).scalars()):
            c.execute(text("delete from loeschantrag where mitglied = :n"), {"n": name})
            c.execute(text("update dsgvo_einwilligung set mitglied = null "
                           "where mitglied = :n"), {"n": name})
            for spalte in c.execute(text(
                    "select conrelid::regclass::text as t, a.attname as s "
                    "from pg_constraint co "
                    "join pg_attribute a on a.attrelid = co.conrelid "
                    "and a.attnum = any(co.conkey) "
                    "join pg_class cf on cf.oid = co.confrelid "
                    "where co.contype = 'f' and cf.relname = 'mitglied' "
                    "and a.attnotnull = false")).mappings():
                if (spalte["t"], spalte["s"]) in (("dsgvo_einwilligung", "mitglied"),
                                                  ("loeschantrag", "mitglied")):
                    continue
                c.execute(text(f'update "{spalte["t"]}" set "{spalte["s"]}" = null '
                               f'where "{spalte["s"]}" = :n'), {"n": name})
            c.execute(text("delete from mitglied where name = :n"), {"n": name})
        c.execute(text("delete from has_role where name like :p"),
                  {"p": "dsgvo1b-%"})
        c.execute(text("delete from loeschantrag where mitglied = :m"), {"m": mitglied})
        c.execute(text('update mitglied set "user" = null where name = :m'), {"m": mitglied})
        # Gegen die FRISCHE Kopie: der Dump bringt das Konto schon als Wert mit
        # (`dienstbereich_verantwortlicher.user`) — ohne Freigabe blockiert die
        # Fremdschluessel das Wegwerfen der Konto-Zeile.
        for t, s in WERT_SPALTEN_KONTO:
            c.execute(text(f'update "{t}" set "{s}" = null where "{s}" = :k'),
                      {"k": konto})
        c.execute(text('delete from "user" where name like :k'), {"k": konto[:20] + "%"})


def _pg(session_engine, anweisung, **kw):
    with session_engine.begin() as c:
        return c.execute(text(anweisung), kw)


def _fremdzeilen(eng) -> dict:
    """Prüfsumme aller Zeilen ANDERER Mitglieder (vor/nach)."""
    import hashlib

    summen = {}
    with eng.connect() as c:
        for name, wert in c.execute(text(
            "select to_jsonb(m)::text, m.name from mitglied m"
        )):
            summen[wert] = hashlib.sha256(str(name).encode()).hexdigest()
    return summen


def test_loeschung_einer_echten_person_laesst_nichts_stehen():
    """Der Kern: echte Person, echte FKs, echte JSON-Werte — 0 Treffer danach."""
    url = _url()
    person = _person(url)
    nadeln = _nadeln(person)
    eng = create_engine(url, future=True)

    # Ausgangslage: der Scan MUSS die Person vorher finden (Gegenprobe).
    vorher = _rest(_scan(eng), nadeln)
    assert vorher, "Vollscan findet die Person VOR der Löschung nicht — wertlos"
    tabelle_vorher = {t for t, _s, _n, _w in vorher}

    # Konto und Antrag anlegen (die Kopie bringt keine Sitzung mit).
    konto = f"dsgvo1b-{person['name'][:20].replace(' ', '-').lower()}@test.example"
    _raeume_auf(eng, person["name"], konto)
    _pg(eng, 'insert into "user"(name, email, full_name, enabled) '
             "values (:k, :k, :n, true)", k=konto, n=person["name"])
    _pg(eng, "update mitglied set \"user\" = :k where name = :m",
        k=konto, m=person["name"])
    _pg(eng, "insert into loeschantrag(mitglied, beantragt_am, status) "
             "values (:m, now(), 'offen')", m=person["name"])

    import diakronos_app.db as dbmod
    import diakronos_app.models  # noqa: F401
    from sqlalchemy.orm import sessionmaker

    from diakronos_app.dsgvo_anonymisierung import anonymisiere

    factory = sessionmaker(bind=eng, autoflush=False, autocommit=False, future=True)
    alt_engine, alt_factory = dbmod.engine, dbmod.SessionLocal
    dbmod.engine, dbmod.SessionLocal = eng, factory
    try:
        with factory.begin() as s:
            ergebnis = anonymisiere(s, person["name"], {konto}, dateien=[])
    finally:
        dbmod.engine, dbmod.SessionLocal = alt_engine, alt_factory

    kennung = ergebnis["kennung"]
    assert re.fullmatch(r"geloescht-[0-9a-f]{32}", kennung), kennung

    reste = _rest(_scan(eng), nadeln)
    assert reste == [], (
        f"Personendaten stehen noch in {len(reste)} Stellen "
        f"(vorher {len(vorher)}):\n  "
        + "\n  ".join(f"{t}.{s} ({n}): {w}" for t, s, n, w in reste[:20])
    )

    with eng.connect() as c:
        assert c.execute(text("select count(*) from mitglied where name = :m"),
                         {"m": person["name"]}).scalar() == 0
        neu = c.execute(text("select vorname, nachname, status from mitglied "
                             "where name = :k"), {"k": kennung}).one()
        assert tuple(neu) == ("Gelöschte", "Person", "geloescht")
        assert c.execute(text('select count(*) from "user" where name = :k'),
                         {"k": konto}).scalar() == 0
        # Der Nachweis hängt an der NEUEN Kennung.
        assert c.execute(text("select count(*) from loeschantrag where mitglied = :k"),
                         {"k": kennung}).scalar() == 1
    eng.dispose()


def test_fremde_mitglieder_bleiben_unveraendert():
    """Fremde Mitglieder-Zeilen vor/nach: nur die gelöschte Person ändert sich.

    Die Prüfsumme läuft über `to_jsonb(m)` — ALLE Spalten, nicht nur die, die
    das Inventar kennt. Der frühere Freitext-Replace hat hier neun fremde
    Wohnorte zerstört (R-DSGVO-1, K2).
    """
    url = _url()
    person = _person(url, ueberspringe=1)
    eng = create_engine(url, future=True)

    with eng.connect() as c:
        vorher = {n: h for h, n in c.execute(text(
            "select to_jsonb(m)::text as j, m.name from mitglied m"))}
    assert len(vorher) >= 2, vorher

    konto = f"dsgvo1b2-{person['name'][:20].replace(' ', '-').lower()}@test.example"
    _raeume_auf(eng, person["name"], konto)
    _pg(eng, 'insert into "user"(name, email, full_name, enabled) '
             "values (:k, :k, :n, true)", k=konto, n=person["name"])
    _pg(eng, "update mitglied set \"user\" = :k where name = :m",
        k=konto, m=person["name"])
    import diakronos_app.db as dbmod
    import diakronos_app.models  # noqa: F401
    from sqlalchemy.orm import sessionmaker

    from diakronos_app.dsgvo_anonymisierung import anonymisiere

    factory = sessionmaker(bind=eng, autoflush=False, autocommit=False, future=True)
    alt_engine, alt_factory = dbmod.engine, dbmod.SessionLocal
    dbmod.engine, dbmod.SessionLocal = eng, factory
    try:
        with factory.begin() as s:
            ergebnis = anonymisiere(s, person["name"], {konto}, dateien=[])
    finally:
        dbmod.engine, dbmod.SessionLocal = alt_engine, alt_factory

    with eng.connect() as c:
        nachher = {n: h for h, n in c.execute(text(
            "select to_jsonb(m)::text as j, m.name from mitglied m"))}
    eng.dispose()

    assert person["name"] not in nachher, "alte Kennung steht noch in mitglied"
    assert ergebnis["kennung"] in nachher
    # Jede ANDERE Zeile ist bitgleich (ihr `user`-Link wurde nicht angefasst —
    # die Testperson hatte keinen).
    # Bereits geloeschte Personen (aus dem ersten Test derselben Wegwerf-DB)
    # sind kein "fremdes Mitglied" mehr und bleiben hier aussen vor.
    geaendert = [n for n in vorher
                 if n != person["name"]
                 and not re.fullmatch(r"geloescht-[0-9a-f]{32}", str(n))
                 and vorher[n] != nachher.get(n)]
    assert geaendert == [], f"fremde Mitglieder verändert: {geaendert}"


def test_konto_ohne_user_zeile_verschwindet_aus_den_rollen():
    """Konto, das NUR als Wert existiert — Kontenliste wie im Betrieb.

    R-DSGVO-1c, offene Frage (Operator-Entscheidung): `wirksame_konten` wird
    NICHT erweitert. Im Betrieb gibt es 0 Waisen, deren `parent` eine
    Mitglieds-, Konto- oder Anmeldungsadresse ist; die 54 `has_role`- und
    38 `user_role`-Waisen haengen alle an Frappe-Konfiguration
    (Page/Report/Workspace/Desktop Icon) bzw. an Kalendern.

    Die „Kontenliste wie im Betrieb“ darf deshalb LEER sein: geloescht wird
    ueber die eigenen bekannten Kennungen der Person — hier `mitglied.user`
    und `mitglied.email` (`anonymisiere` -> `_konto_werte`).

    Geprueft wird beides:
    * die Rollen-/Verantwortungs-Zeilen des Kontos sind weg, und der Vollscan
      nach der Adresse findet 0 Treffer;
    * die WAISEN (fremde `parenttype`s) sind vorher/nachher BYTE-GLEICH — das
      ersetzt den Scheintest `test_fremde_konten_behalten_ihre_rollen`.
    """
    url = _url()
    person = _dienstkonto(url)
    mitglied, konto = person["name"], person["konto"]
    eng = create_engine(url, future=True)
    _raeume_auf(eng, mitglied, konto)
    _nur_als_wert(url, mitglied, konto)

    with eng.connect() as c:
        assert c.execute(text("select count(*) from has_role where parent = :k"),
                         {"k": konto}).scalar() > 0
        assert c.execute(text('select count(*) from "user" where name = :k'),
                         {"k": konto}).scalar() == 0
        konten = _konten_wie_produktion(c, mitglied, konto)
        # Waisen ohne Personenbezug: alles ausser parenttype='User'.
        waisen = _waisen(c)
    assert konto not in konten, konten
    assert waisen, "die Kopie hat keine Waisen — die Gegenprobe waere leer"

    kennung = _loesche(url, mitglied, konten)

    with eng.connect() as c:
        assert c.execute(text("select count(*) from has_role "
                              "where parent = :k and parenttype = 'User'"),
                         {"k": konto}).scalar() == 0
        assert c.execute(text('select count(*) from dienstbereich_verantwortlicher '
                              'where "user" = :k'), {"k": konto}).scalar() == 0
        assert c.execute(text("select count(*) from mitglied where name = :m"),
                         {"m": mitglied}).scalar() == 0
        assert c.execute(text("select count(*) from mitglied where name = :k"),
                         {"k": kennung}).scalar() == 1
        # Vollscan nach der Adresse: 0 Treffer.
        reste = _rest(_scan(eng), [konto])
        assert reste == [], reste
        # Gegenprobe: die Waisen sind unangetastet.
        nachher = _waisen(c)
    assert nachher == waisen, (
        f"{len(set(waisen.items()) - set(nachher.items()))} Waisen-Zeilen veraendert"
    )
    eng.dispose()


def _waisen(c) -> dict:
    """Alle Rollenzeilen mit `parenttype <> 'User'` (Frappe-Konfiguration und
    Kalender) als Pruefsumme je Tabelle."""
    zaehler = {}
    for tabelle in ("has_role", "user_role"):
        for zeile in c.execute(text(
            f'select "parent", "parenttype", "role", count(*) from "{tabelle}" '
            'where "parenttype" is distinct from \'User\' '
            'group by 1, 2, 3 order by 1, 2, 3'
        )):
            zaehler[f"{tabelle}|{zeile[0]}|{zeile[1]}|{zeile[2]}"] = int(zeile[3])
    return zaehler
