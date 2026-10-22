"""ID-1f (A1, G1): Löschung kennt die Zuordnungstabelle der Umschlüsselung.

WARUM
-----
ID-1 hat `mitglied.name` vom Klarnamen auf eine Zufallskennung umgeschlüsselt
und die alte Form in `id1_mitglied_kennung` (`alt` -> `neu`) protokolliert. Die
Löschung auf Antrag kannte diese Tabelle nicht: der Klarname der gelöschten
Person blieb in `alt` stehen — in einer Tabelle, die die Löschung überlebt.
Ebenso blieb ein Einwilligungs-Schlüssel aus der Zeit VOR ID-1
(`DSGVO-<frühere Kennung>-0002`) auf der alten Kennung sitzen.

WAS HIER GEPRÜFT WIRD
---------------------
A1 — `anonymisiere()`:
  * die Zeile(n) der Person in `id1_mitglied_kennung` sind weg (über die
    aktuelle und über die frühere Kennung erkannt),
  * `dsgvo_einwilligung.name` trägt danach die neutrale Kennung — auch für eine
    Zeile mit FRÜHERER Kennung, und die laufende Nummer bleibt,
  * der Vollscan (alle Textspalten) findet keinen Klarnamen und keine frühere
    Kennung mehr,
  * Fremdzeilen (andere Person) bleiben unangetastet,
  * die Löschung läuft auch, wenn `id1_mitglied_kennung` NICHT existiert
    (Downgrade, ältere DB).

G1 — `get_adressbuch`: für Ausgetretene sind `nachname` und `foto` `""`, nicht
`None` (das Frontend baut daraus `aria-label="Anrufen: Elvira null"`).
"""
from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import create_engine, inspect as sa_inspect, select, text

from test_dsgvo1_anonymisierung import (  # noqa: F401 — Fixtures
    ANNA, _alle_textwerte, _antrag_und_loeschen, _kennung, post, smtp, vollscan,
    welt,
)
from diakronos_app.frappe_compat.session import set_user
from diakronos_app.models.core import HasRole, User
from diakronos_app.models.diakonos import DSGVOEinwilligung, Mitglied
from diakronos_app.models.id1 import MitgliedKennung

#: Neutraler Anzeigename — das Ziel der Klarnamen-Ersetzung in FREMDEN Texten
#: (dieselbe Konstante wie im Modul; importiert statt abgeschrieben).
from diakronos_app.dsgvo_anonymisierung import ANZEIGENAME, FREITEXT_ERSETZUNG

#: Frühere Kennung der Person (im Betrieb: der Klarname) — so steht sie in
#: `id1_mitglied_kennung.alt` und in Nachweis-Schlüsseln aus der Zeit vor ID-1.
FRUEHER = "Annamaria Beispielhuber"
SCHLUESSEL_NEU = "3c4d5e6f-7"     # aktuelle Kennung, seit ID-1
SCHLUESSEL_ALT = "DSGVO-" + "Annamaria Beispielhuber" + "-0114"
SCHLUESSEL_FREMD = "DSGVO-Bert Berger-0002"


@pytest.fixture
def id1_welt(welt, smtp):
    """Die DSGVO-Welt plus Zuordnungstabelle und Nachweise aus der Zeit vor ID-1.

    `welt` legt die Person unter der ALTEN Kennung `D1-anna` an — genau der
    Zustand, den ID-1 im Betrieb hinterlässt: die Person ist umgeschlüsselt,
    die alte Form steht nur noch in `id1_mitglied_kennung`.

    `mitglied` bekommt dabei wieder einen Status: `welt` setzt den der Person
    selbst nicht, und `api/datenschutz` verweigert den Antrag fuer ein schon
    ausgeschlossenes Mitglied.

    `smtp` gehört HIERHER, nicht in die Tests: die Löschung sendet erst die
    Mail und anonymisiert dann, und `_smtp_einrichten` legt die Einstellungen
    an. Steht der Fixture nur am Test, laufen beide in beliebiger Reihenfolge —
    dann fehlt die Zeile (417 „Mailversand ist nicht eingerichtet“), und
    `patched_db` setzt die Sitzung zurück, bevor der Test sie geschrieben hat.
    """
    with welt.begin() as s:
        s.get(Mitglied, "D1-anna").status = "Mitglied"
    with welt.begin() as s:
        s.add(MitgliedKennung(alt=FRUEHER, neu="D1-anna"))
        s.add(MitgliedKennung(alt="Bert Berger", neu="D1-bert"))
        s.add(DSGVOEinwilligung(
            name=SCHLUESSEL_ALT, mitglied="D1-anna", typ="datenschutz",
            aktion="erteilt"))
        # Zeile, deren Schlüssel BEREITS die Kennung trägt (nach ID-1), und eine
        # FREMDZEILE: beide dürfen sich nicht verändern.
        s.add(DSGVOEinwilligung(
            name=f"DSGVO-{SCHLUESSEL_NEU}-0115", mitglied=SCHLUESSEL_NEU,
            typ="foto", aktion="erteilt"))
        s.add(DSGVOEinwilligung(
            name=SCHLUESSEL_FREMD, mitglied="D1-bert", typ="datenschutz",
            aktion="erteilt"))
    return welt


def _abbildung(welt) -> list[tuple[str, str]]:
    with welt() as s:
        return [tuple(z) for z in s.execute(
            select(MitgliedKennung.alt, MitgliedKennung.neu)).all()]


def _schluessel(welt) -> dict[str, str]:
    with welt() as s:
        return dict(s.execute(
            select(DSGVOEinwilligung.name, DSGVOEinwilligung.mitglied)).all())


# ── A1: Zuordnungstabelle ───────────────────────────────────────────────────

def _belegt(welt) -> dict:
    """Alle Zeilen der Abbildung als ``{alt: neu}``."""
    with welt() as s:
        return dict(s.execute(
            select(MitgliedKennung.alt, MitgliedKennung.neu)).all())


def test_zuordnung_der_person_ist_geloescht(client, id1_welt):
    """Die Zeile(n) der Person fallen — die fremde bleibt zeichengleich."""
    assert _antrag_und_loeschen(client, id1_welt).status_code == 200
    zeilen = _belegt(id1_welt)
    assert zeilen == {"Bert Berger": "D1-bert"}, zeilen


def test_zuordnung_ueber_die_neue_kennung_erkannt(engine):
    """NUR die Spalte `neu` nennt die Person — die Zeile fällt trotzdem.

    Erkannt wird über `alt IN (…) OR neu IN (…)`. Ein Test über die Oberfläche
    prüft das nicht: dort steht die Person schon durch ihre Fixture-Zeile in
    `alt`, ein Fehler im `neu`-Zweig fiele nicht auf. Deshalb wird
    `_zeilen_loeschen` HIER direkt aufgerufen — mit festgelegten Kennungen, in
    einer Welt, in der die Person ausschließlich in `neu` steht:

    * `fremd-1` -> `person-1`  (Person NUR in `neu`)  → fällt
    * `fremd-2` -> `fremd-3`   (andere Person)        → bleibt zeichengleich
    """
    from sqlalchemy.orm import sessionmaker

    from diakronos_app.dsgvo_anonymisierung import Bestand, _zeilen_loeschen

    fabrik = sessionmaker(bind=engine, autoflush=False, autocommit=False,
                          future=True)
    with fabrik.begin() as s:
        s.add(MitgliedKennung(alt="fremd-1", neu="person-1"))
        s.add(MitgliedKennung(alt="fremd-2", neu="fremd-3"))
    b = Bestand(mitglied="person-1")
    with fabrik.begin() as s:
        _zeilen_loeschen(s, b, "person-1")
    with fabrik() as s:
        zeilen = dict(s.execute(
            select(MitgliedKennung.alt, MitgliedKennung.neu)).all())
    assert zeilen == {"fremd-2": "fremd-3"}, zeilen


def test_kette_von_kennungen_wird_vollstaendig_verfolgt(client, id1_welt):
    """A -> B -> C: auch die Zeile mit A faellt (transitive Huelle, Punkt 3).

    Ein zweiter Umschluesselungs-Lauf haengt an die Kennung der Person eine
    weitere Stufe. Eine Suche in EINER Stufe faende nur B — A bliebe mit dem
    Klarnamen stehen. Deshalb wird gelesen, bis keine neue Kennung dazukommt.
    """
    A, B = FRUEHER, "D1-anna"
    with id1_welt.begin() as s:
        # Die Fixture-Zeile (A -> B) und eine zweite Stufe (B -> C) bilden die
        # Kette A -> B -> C; C ist die Kennung, unter der die Person steht.
        s.add(MitgliedKennung(alt=B, neu=SCHLUESSEL_NEU))
    assert _antrag_und_loeschen(client, id1_welt).status_code == 200
    zeilen = _belegt(id1_welt)
    # Beide Zeilen der Kette sind weg — die fremde bleibt.
    assert all(A not in alt and B not in alt for alt in zeilen), zeilen
    assert all(A not in neu and B not in neu for neu in zeilen.values()), zeilen
    assert zeilen == {"Bert Berger": "D1-bert"}, zeilen


# ── A1: Einwilligungs-Schlüssel ─────────────────────────────────────────────

def test_fruehere_kennungen_ueber_die_ganze_kette(engine):
    """`_fruehere_kennungen` folgt A -> B -> C, nicht nur einer Stufe (Punkt 3).

    Mit EINER Stufe findet der Aufruf die Zeile (A -> B) nicht, wenn die Person
    unter C steht — A (der Klarname) bleibt dann in der Loeschung unbekannt.
    Geprueft wird die Funktion selbst: der Weg ueber die Oberflaeche findet
    beide Zeilen schon durch das ODER der einen Stufe.
    """
    from sqlalchemy.orm import sessionmaker

    from diakronos_app.dsgvo_anonymisierung import Bestand, _fruehere_kennungen

    fabrik = sessionmaker(bind=engine, autoflush=False, autocommit=False,
                          future=True)
    A = "Annamaria Beispielhuber"   # im Betrieb der Klarname
    with fabrik.begin() as s:
        s.add(MitgliedKennung(alt=A, neu="kennung-b"))
        s.add(MitgliedKennung(alt="kennung-b", neu="kennung-c"))

    b = Bestand(mitglied="kennung-c")
    with fabrik.begin() as s:
        _fruehere_kennungen(s, b)
    assert {A, "kennung-b", "kennung-c"} <= b.kennungen, sorted(b.kennungen)


def test_einwilligungsschluessel_aus_frueherer_kennung_wird_neutral(
        client, id1_welt, smtp):
    """`DSGVO-<frühere Kennung>-0114` -> `DSGVO-<geloescht-…>-0114`."""
    assert _antrag_und_loeschen(client, id1_welt).status_code == 200
    schluessel = _schluessel(id1_welt)
    kennung = _kennung(id1_welt)
    assert SCHLUESSEL_ALT not in schluessel, sorted(schluessel)
    # Die laufende Nummer bleibt, der Namensanteil ist die neutrale Kennung.
    assert f"DSGVO-{kennung}-0114" in schluessel, sorted(schluessel)
    assert schluessel[f"DSGVO-{kennung}-0114"] == kennung


def test_fremde_und_schon_neutrale_nachweise_bleiben(client, id1_welt, smtp):
    """Gegenprobe: fremde Zeile und Zeile mit Kennung bleiben zeichengleich."""
    assert _antrag_und_loeschen(client, id1_welt).status_code == 200
    schluessel = _schluessel(id1_welt)
    assert SCHLUESSEL_FREMD in schluessel, sorted(schluessel)
    assert schluessel[SCHLUESSEL_FREMD] == "D1-bert"
    assert f"DSGVO-{SCHLUESSEL_NEU}-0115" in schluessel, sorted(schluessel)


# ── A1: Klarname im Schlüssel AUSSERHALB der Bauform (Punkt 1) ──────────────
#
# Die Kennungsregel (`_schluessel_neu`) erkennt nur die exakte Bauform
# `<Präfix><Kennung>-<Ziffern>`. Sie hat die frühere Klarnamen-Suche ERSETZT —
# damit blieben drei Fälle stehen, die die Bauform nicht trifft. Die Suche läuft
# deshalb als ZWEITER Schritt zusätzlich (dieselbe Regel wie vor ID-1).

def _eigene_schluessel(welt) -> list[str]:
    """Alle Nachweis-Schlüssel der geloeschten Person (nach ihrer Kennung)."""
    from diakronos_app.models.diakonos import DSGVOEinwilligung as Zeile

    kennung = _kennung(welt)
    with welt() as s:
        return [str(n) for n in s.scalars(
            select(Zeile.name).where(Zeile.mitglied == kennung)).all()]


def test_kollisionszusatz_traegt_keinen_klarnamen(client, id1_welt):
    """`DSGVO-<Name>-0114-1` (Zusatz wegen Schlüsselkollision) wird neutral.

    Der Kollisionszweig hängt eine Laufnummer an: `0114-1` ist keine Bauform
    mehr (`0114-1` besteht nicht aus Ziffern). Die Klarnamen-Suche trifft die
    Stelle trotzdem.
    """
    from diakronos_app.models.diakonos import DSGVOEinwilligung as Zeile

    with id1_welt.begin() as s:
        # Belegt den Bauform-Schlüssel der Person, damit der obige Nachweis
        # einen Zusatz bekommt.
        s.add(Zeile(name=SCHLUESSEL_ALT + "-1", mitglied="D1-anna",
                    typ="werbung", aktion="erteilt"))
    assert _antrag_und_loeschen(client, id1_welt).status_code == 200
    schluessel = _eigene_schluessel(id1_welt)
    assert all(FRUEHER not in s for s in schluessel), schluessel
    # Der Namensanteil wird der Platzhalter für Freitext (dieselbe Ersetzung
    # wie in fremden Texten), die laufende Nummer (`0114`, `0114-1`) bleibt
    # stehen. Welche der beiden Regeln den Kollisionsschlüssel zuerst sieht,
    # ist offen — der NAME darf in keinem Fall stehen bleiben.
    # (Der Löschpfad legt zusätzlich Widerrufs-Belege `uuid4().hex` an — ohne
    # Namen, deshalb nur die `DSGVO-`-Schlüssel.)
    gebaut = sorted(s for s in schluessel if s.startswith("DSGVO-"))
    assert len(gebaut) == 2, schluessel
    assert all(s.endswith(("-0114", "-0114-1")) for s in gebaut), schluessel
    assert all(s.startswith(("DSGVO-[gelöscht]-", "DSGVO-geloescht-"))
               for s in gebaut), schluessel


def test_klarname_bei_abweichender_kennung_wird_neutral(client, id1_welt):
    """Namensanteil ist der Klarname, die Zeile gilt einer ANDEREN Person.

    Grenzfall aus dem Re-Review (Punkt 1): die Zeile trägt den Namen der
    gelöschten Person, gehört aber über `mitglied` einer fremden Kennung. Sie
    ist damit der Nachweis eines DRITTEN (Art. 7) und bleibt unverändert —
    „Namensvetter“ ist entweder eine andere Person oder eine Verwechslung, in
    keinem Fall dürfen wir ihren Nachweis zerstören.

    Ersetzt wird die eigene Zeile desselben Falls — die mit dem Klarnamen im
    Schlüssel und einer Kennung der Person; sie steht in
    `test_altzeilen_ohne_zuordnung_verlieren_den_klarnamen` (ohne Abbildung)
    und in `test_einwilligungsschluessel_aus_frueherer_kennung_wird_neutral`.
    """
    from diakronos_app.models.diakonos import DSGVOEinwilligung as Zeile

    FREMD = "fremd-kennung-8"
    with id1_welt.begin() as s:
        s.add(Zeile(name=f"DSGVO-{FRUEHER}-0200", mitglied=FREMD,
                    typ="foto", aktion="erteilt"))
    assert _antrag_und_loeschen(client, id1_welt).status_code == 200
    with id1_welt() as s:
        zeilen = dict(s.execute(
            select(Zeile.name, Zeile.mitglied)).all())
    assert zeilen.get(f"DSGVO-{FRUEHER}-0200") == FREMD, sorted(zeilen)


def test_altzeilen_ohne_zuordnung_verlieren_den_klarnamen(client, id1_welt):
    """Altzeile ohne Abbildungs-Eintrag (nach einem Downgrade): Klarname weg.

    Fehlt `id1_mitglied_kennung`, gibt es keine frühere Kennung zu erkennen —
    der Klarname steht aber wortgleich im Schlüssel. Er wird ersetzt.

    Die Zeile gehört der Person: sie steht auf deren aktueller Kennung (`D1-anna`),
    die Abbildung fehlt nur.
    """
    from diakronos_app.models.diakonos import DSGVOEinwilligung as Zeile
    from diakronos_app.models.id1 import MitgliedKennung

    with id1_welt.begin() as s:
        s.execute(MitgliedKennung.__table__.delete())
        s.add(Zeile(name=f"DSGVO-{FRUEHER}-0300", mitglied="D1-anna",
                    typ="foto", aktion="widerrufen"))
    assert _antrag_und_loeschen(client, id1_welt).status_code == 200
    schluessel = _eigene_schluessel(id1_welt)
    assert f"DSGVO-{FRUEHER}-0300" not in schluessel, schluessel
    assert all(FRUEHER not in s for s in schluessel), schluessel


def test_kennungslose_altzeile_verliert_den_klarnamen(client, id1_welt):
    """Altzeile OHNE `mitglied` (vor ID-1 angelegt): Klarname wird ersetzt.

    Die Migration hängt nur um, was eine Kennung trägt; eine Zeile ohne
    `mitglied` bleibt kennungslos. Sie ist trotzdem der Nachweis der Person —
    ihr Schlüssel führt den Klarnamen, und der muss weg. Ein solcher Schlüssel
    ist keine fremde Zeile: „ohne Kennung“ heißt nicht „gehört jemand anderem“.
    """
    from diakronos_app.models.diakonos import DSGVOEinwilligung as Zeile

    NACHWEIS = f"DSGVO-{FRUEHER}-0500"
    with id1_welt.begin() as s:
        s.add(Zeile(name=NACHWEIS, mitglied=None, typ="foto", aktion="erteilt"))
    assert _antrag_und_loeschen(client, id1_welt).status_code == 200
    schluessel = _eigene_schluessel(id1_welt)
    assert NACHWEIS not in schluessel, schluessel
    assert all(FRUEHER not in s for s in schluessel), schluessel
    with id1_welt() as s:
        bleibt = s.execute(select(Zeile.name).where(
            Zeile.mitglied.is_(None))).scalars().all()
    assert f"DSGVO-{FREITEXT_ERSETZUNG}-0500" in list(bleibt), bleibt


def test_namensgleiche_fremde_person_behaelt_ihren_nachweis(client, id1_welt):
    """Der Namensvetter einer anderen Person bleibt zeichengleich (Punkt 1).

    Die Klarnamen-Suche (Schritt 2) darf nur EIGENE Zeilen der Person treffen:
    die mit `mitglied` auf eine ihrer Kennungen und die kennungslosen Altzeilen
    (kein Eintrag in der Abbildung). Die Nachweiszeile einer ANDEREN Person, die
    denselben Namen trägt, ist deren Personendatum — sie wird nicht angefasst,
    sonst zerstörte die Löschung den Nachweis eines Dritten (Art. 7).
    """
    from diakronos_app.models.diakonos import DSGVOEinwilligung as Zeile

    FREMD = "fremd-kennung-8"
    NACHWEIS = f"DSGVO-{FRUEHER}-0400"
    with id1_welt.begin() as s:
        s.add(Zeile(name=NACHWEIS, mitglied=FREMD, typ="foto", aktion="erteilt"))
    assert _antrag_und_loeschen(client, id1_welt).status_code == 200
    with id1_welt() as s:
        fremd = s.execute(select(Zeile.mitglied).where(
            Zeile.name == NACHWEIS)).scalar_one_or_none()
    assert fremd == FREMD, f"Nachweis der fremden Person umgeschrieben: {fremd!r}"


def test_vollscan_null_nach_umschluesselung_und_loeschung(client, id1_welt, smtp):
    """Kernnachweis: kein Klarname, keine frühere Kennung — nirgends."""
    assert _antrag_und_loeschen(client, id1_welt).status_code == 200
    treffer = vollscan(id1_welt, FRUEHER, ANNA["vorname"], ANNA["nachname"],
                       ANNA["email"], ANNA["telefon"])
    assert treffer == [], f"Personendaten stehen noch in: {treffer}"


# ── A1: ohne die Tabelle (Downgrade) ────────────────────────────────────────

def test_fremdtexte_ohne_katalog_werden_nicht_still_uebersprungen(
        engine, monkeypatch):
    """Unbekannter Katalog (`None`) schaltet den Filter NICHT ab (Punkt 2).

    `_vorhandene_tabellen` liefert ``None``, wenn keine Katalogabfrage
    gelingt. Mit `set()` als Ersatz übersprang `_fremdtexte_ersetzen` JEDE
    Tabelle — die Personen-Nennung im fremden Freitext bliebe stehen, und
    niemand merkte es (fail open). Erwartet: der Filter greift dann gar nicht,
    die Ersetzung läuft über alle Tabellen.

    EIGENE Datenbank, weil ein `DROP`/`ALTER` in der geteilten Test-Engine den
    SAVEPOINT von `patched_db` beendet (s. `test_loeschung_ohne_zuordnungstabelle`).
    """
    from sqlalchemy.orm import sessionmaker

    from diakronos_app import dsgvo_anonymisierung as modul
    from diakronos_app.models.diakonos import Mitglied as Person

    fabrik = sessionmaker(bind=engine, autoflush=False, autocommit=False,
                          future=True)
    with fabrik.begin() as s:
        s.add(Person(name="D1-anna", vorname="Annamaria",
                     nachname="Beispielhuber", status="Mitglied"))
        s.add(Person(name="D1-bert", vorname="Bert", nachname="Berger",
                     notiz="Annamaria Beispielhuber kommt mit"))

    monkeypatch.setattr(modul, "_vorhandene_tabellen", lambda s: None)
    with fabrik.begin() as s:
        b = modul.bestand_erheben(s, "D1-anna", set())
        zaehler = modul._fremdtexte_ersetzen(s, b)
    assert zaehler.get("mitglied.notiz") == 1, zaehler
    with fabrik() as s:
        # Der ganze Name ist ersetzt, der übrige Text bleibt stehen.
        assert s.get(Person, "D1-bert").notiz == (
            f"{modul.FREITEXT_ERSETZUNG} kommt mit")
        assert s.get(Person, "D1-anna").vorname == "Annamaria"


def test_loeschung_ohne_zuordnungstabelle(engine):
    """`id1_mitglied_kennung` fehlt (Downgrade): die Löschung läuft durch.

    Der Wächter `has_table` im Löschpfad statt einer Annahme: die Migration ist
    rückbaubar, und eine Sicherung von vor ID-1 kennt die Tabelle nicht. Die
    Tabelle wird dafür in einer EIGENEN Datenbank GELÖSCHT — nicht in der
    geteilten Test-Engine, deren Transaktion `patched_db` gerade hält (ein DDL
    darin beendet den Savepoint und bricht alle folgenden Tests).

    ``engine`` ohne ``patched_db``: die Löschung läuft auf genau der Sitzung,
    die ihr übergeben wird (`anonymisiere(s, ...)`), nicht über `SessionLocal`.
    """
    from sqlalchemy import text as _text
    from sqlalchemy.orm import sessionmaker

    from diakronos_app import dsgvo_anonymisierung as modul
    from diakronos_app.models.core import User as Konto
    from diakronos_app.models.diakonos import Mitglied as Person

    with engine.begin() as c:
        c.execute(_text("DROP TABLE " + modul.KENNUNG_ABBILDUNG))
    assert not sa_inspect(engine).has_table(modul.KENNUNG_ABBILDUNG)

    fabrik = sessionmaker(bind=engine, autoflush=False, autocommit=False,
                          future=True)
    with fabrik.begin() as s:
        s.add(Person(name="D1-anna", vorname="Annamaria", nachname="Beispielhuber",
                     email="annamaria.beispielhuber@example.org", status="Mitglied"))
        s.add(Konto(name="annamaria.beispielhuber@example.org",
                    email="annamaria.beispielhuber@example.org", enabled=True))

    with fabrik.begin() as s:
        ergebnis = modul.anonymisiere(
            s, "D1-anna", {"annamaria.beispielhuber@example.org"})
        s.flush()
        assert ergebnis["kennung"].startswith(modul.GELOESCHT_PRAEFIX)
        assert s.get(Person, "D1-anna") is None
        assert s.get(Person, ergebnis["kennung"]) is not None
        assert s.get(Konto, "annamaria.beispielhuber@example.org") is None


# ── G1: Adressbuch ──────────────────────────────────────────────────────────

def test_adressbuch_gibt_ausgetretenen_leeren_nachnamen(client, id1_welt):
    """Nicht `null` in der Antwort: `nachname`/`foto` sind `""` (G1).

    Der Weg ist derselbe wie in `test_id1_leak`: ein Nicht-Administrator liest
    das Adressbuch, die Person ist ausgetreten, `personen_anzeige.kuerze` setzt
    `nachname`/`foto` auf `None` — das Frontend baute daraus „Elvira null“.
    """
    from diakronos_app.api import mitglieder as api_mitglieder

    with id1_welt.begin() as s:
        s.add(User(name="leser@x.org", email="leser@x.org", full_name="Leser Leser",
                   enabled=True))
        s.add(HasRole(name="role-leser", parent="leser@x.org", parenttype="User",
                      role="Mitglied"))
        # Der Leser braucht eine EIGENE Mitgliedszeile: ohne `ancestor_path`
        # filtert `get_adressbuch` fail-closed auf die eigene Adresse.
        s.add(Mitglied(name="L-leser", vorname="Lena", nachname="Leser",
                       email="leser@x.org", status="Mitglied",
                       ancestor_path="/gemeinde/|/chor/"))
        mitglied = s.get(Mitglied, "D1-bert")
        mitglied.status = "Ausgetreten"
        mitglied.austritt_datum = date(2026, 10, 1)
        mitglied.nachname = "Berger"
        mitglied.foto = None
        # Gemeinsamer Bereich: sonst sieht der Leser die Zeile nicht.
        mitglied.ancestor_path = "/gemeinde/|/chor/"
        leser = s.get(Mitglied, "D1-anna")
        leser.ancestor_path = "/gemeinde/|/chor/"

    set_user("leser@x.org")
    antwort = api_mitglieder.get_adressbuch("")
    zeilen = {z["name"]: z for z in antwort["data"]}
    assert "D1-bert" in zeilen, sorted(zeilen)
    zeile = zeilen["D1-bert"]
    assert zeile["nachname"] == "", zeile
    assert zeile["foto"] == "", zeile
    assert zeile["vorname"] == "Bert B.", zeile
