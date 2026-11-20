"""CHAT-9c: zwei Lese-Endpunkte für die Erwähnungs-Oberfläche.

Geprüft wird gegen die ECHTEN Endpunkte (``api.chat``), den ECHTEN Rechte-Kern
(``rechte/kern.py``) und die ECHTE Datenbank — keine Attrappe.

``chat.gespraech_mitglieder`` (GET, CHAT-9c-2: Suche statt Vollliste)
  * Vertrag ``(gespraech, q="", limit=20)`` → ``{art, mitglieder, mehr}``
  * Gruppe: alle Mitglieder OHNE die lesende Person, voller Name, nach Name
    sortiert
  * Untergruppe: NUR ihre Mitglieder (das Außenmitglied fehlt)
  * Runde: nur AKTIVE Teilnehmende (wer gegangen ist, fehlt); die Grenze ist
    dieselbe wie beim Senden (``_erwaehnung_grenze``)
  * 1:1: genau die andere Person, mit vollem Namen
  * ``q`` filtert nach Namensanfang: Vorname, Nachname, „Vor Nach“, Umlaut-
    und Groß-/Kleinschreibung egal; ``q=""`` = alle
  * Obergrenze ``limit`` (Vorgabe 20, größer wird gekappt) + ``mehr``
  * geprüft werden höchstens ``3*limit`` Kandidaten (Gruppe mit 300 Personen)
  * ausgetretene Person fehlt, gesperrte Person ist DRIN (Sperre darf nicht
    erkennbar sein)
  * ohne Leserecht: neutrale Ablehnung wie bei den übrigen Chat-Endpunkten
  * nur Kennung + Anzeigename (keine Kontaktdaten)
  * ABFRAGEZAHL begrenzt (``before_cursor_execute``): 300-Personen-Gruppe
    bleibt unter 1500 SQL-Anweisungen — kein N+1 über alle Mitglieder

``chat.nachricht_kontext`` (GET)
  * erlaubte Nachricht → ``{gespraech, art, titel}`` (Titel wie in
    ``meine_gespraeche``, auch bei 1:1 der Anzeigename des Gegenübers)
  * Runde: Nachricht VOR ``sichtbar_ab`` → dieselbe neutrale Antwort
  * gelöschte Nachricht, fremde Nachricht, unbekannte Kennung → dieselbe
    neutrale Antwort (kein Unterschied, keine Auskunft)

Beide nur GET: POST → 405 (SEC-11).

Aufruf (Karte):
    docker run --rm --network none --entrypoint python -v <wt>:/repo:ro \\
      -w /repo/backend -e PYTHONPATH=/repo/backend/src:/repo/backend/tests:/repo/tools \\
      -e PYTHONDONTWRITEBYTECODE=1 <vorbau> -m pytest -q -p no:cacheprovider \\
      tests/test_chat9c_lesen.py
"""

from __future__ import annotations

import importlib

import pytest

from diakronos_app.frappe_compat.exceptions import (  # noqa: A004 — Projektklasse (403)
    DoesNotExistError,
    PermissionError,
)

#: Dieselbe Welt wie ``test_chat9a_erwaehnung``/``test_chat7b_runden`` —
#: Fixture und Konten werden geteilt, nicht nachgebaut.
from test_chat7b_runden import (  # noqa: E402,F401 — Fixture teilen
    ANNA,
    BERT,
    CLARA,
    DIETER,
    FRIDA,
    HV,
    MI,
    _set_user,
    welt,
)
from test_chat7b_runden import _anlegen as _runde_anlegen
from test_chat7b_runden import _sperren, _verlassen

_session_mod = importlib.import_module("diakronos_app.frappe_compat.session")


# ── Hilfen ──────────────────────────────────────────────────────────────────


def _mitglieder(gespraech: str, konto: str, q=None, limit=None) -> dict:
    from diakronos_app.api import chat as C

    _set_user(konto)
    if q is None and limit is None:
        # Der Normalfall bleibt der eine Parameter der Oberfläche.
        return C.gespraech_mitglieder(gespraech)
    werte: dict = {}
    if q is not None:
        werte["q"] = q
    if limit is not None:
        werte["limit"] = limit
    return C.gespraech_mitglieder(gespraech, **werte)


def _kontext(nachricht: str, konto: str) -> dict:
    from diakronos_app.api import chat as C

    _set_user(konto)
    return C.nachricht_kontext(nachricht)


def _senden(gespraech: str, text: str, konto: str, erwaehnt=None) -> dict:
    from diakronos_app.api import chat as C

    _set_user(konto)
    return C.senden(gespraech, text, erwaehnt=erwaehnt)


def _direkt(mitglied: str, konto: str) -> dict:
    from diakronos_app.api import chat as C

    _set_user(konto)
    return C.direkt_oeffnen(mitglied)


def _meine(konto: str) -> dict:
    from diakronos_app.api import chat as C

    _set_user(konto)
    return C.meine_gespraeche()


def _kennungen(antwort: dict) -> list[str]:
    return [e["mitglied"] for e in antwort["mitglieder"]]


def _frische_sicht() -> None:
    """Rechte-Merker leeren — nach Schreibzugriffen auf Mitglieder/Gruppen."""
    from diakronos_app import rechte as R

    R.merker_leeren()


@pytest.fixture()
def gruppe(welt, patched_db):
    """Gruppe „Lesekreis“ mit Chat-Modul: Anna, Bert, Clara sind Mitglieder."""
    from diakronos_app.models.diakonos import Gruppe, Gruppenmitgliedschaft
    from diakronos_app.models.rechte import RechteModul

    s = patched_db()
    s.add(Gruppe(name="Lesekreis", gruppenname="Lesekreis"))
    s.add(RechteModul(gruppe="Lesekreis", modul="chat"))
    for i, kennung in enumerate((MI[ANNA], MI[BERT], MI[CLARA])):
        s.add(Gruppenmitgliedschaft(name=f"gm-lesekreis-{i}", parent="Lesekreis",
                                    parentfield="mitglieder", mitglied=kennung))
    s.commit()
    _frische_sicht()
    from diakronos_app.api import chat as C

    _set_user(ANNA)
    return C.gespraech_anlegen("Lesekreis")


# ── 1) gespraech_mitglieder ─────────────────────────────────────────────────


def test_gruppe_liefert_mitglieder_ohne_mich_sortiert(welt, gruppe):
    """Gruppe: die anderen Mitglieder mit vollem Namen, ohne die lesende Person."""
    antwort = _mitglieder(gruppe["name"], ANNA)
    assert antwort["art"] == "gruppe"
    # Bert Brandner vor Clara Clausen — nach Name, ohne Anna.
    assert antwort["mitglieder"] == [
        {"mitglied": MI[BERT], "anzeigename": "Bert Brandner"},
        {"mitglied": MI[CLARA], "anzeigename": "Clara Clausen"},
    ]
    assert antwort["art"] == gruppe["art"]
    # Der Vertrag trägt ``mehr`` immer; unter 20 Einträgen ist es falsch.
    assert antwort["mehr"] is False
    for eintrag in antwort["mitglieder"]:
        assert set(eintrag) == {"mitglied", "anzeigename"}

    # Aus Sicht von Bert steht Anna drin (die eigene Person fehlt jeweils).
    assert _kennungen(_mitglieder(gruppe["name"], BERT)) == [MI[ANNA], MI[CLARA]]


def test_gruppe_nennt_mitglied_ohne_teilnahmezeile(welt, patched_db):
    """Wer die Gruppe nie geöffnet hat, ist trotzdem erwähnbar (wie CHAT-9a)."""
    from diakronos_app.models.core import User
    from diakronos_app.models.diakonos import Gruppe, Gruppenmitgliedschaft, Mitglied
    from diakronos_app.models.rechte import RechteModul

    s = patched_db()
    s.add(Gruppe(name="Nielokal", gruppenname="Nielokal"))
    s.add(RechteModul(gruppe="Nielokal", modul="chat"))
    s.add(Mitglied(name="M-nie", vorname="Nina", nachname="Neu",
                   email="nina@x.org", user="nina@x.org", status="Aktiv"))
    s.add(User(name="nina@x.org", email="nina@x.org", enabled=1,
               full_name="Nina Neu"))
    for kennung, gm in ((MI[ANNA], "gm-nl-a"), ("M-nie", "gm-nl-n")):
        s.add(Gruppenmitgliedschaft(name=gm, parent="Nielokal",
                                    parentfield="mitglieder", mitglied=kennung))
    s.commit()
    _frische_sicht()
    from diakronos_app.api import chat as C

    _set_user(ANNA)
    gespraech = C.gespraech_anlegen("Nielokal")["name"]
    assert _kennungen(_mitglieder(gespraech, ANNA)) == ["M-nie"]


def test_untergruppe_liefert_nur_ihre_mitglieder(welt, patched_db):
    """Untergruppe: nur ihre Mitglieder — das Außenmitglied der Hauptgruppe fehlt."""
    from diakronos_app.models.diakonos import (
        Gruppe,
        Gruppenmitgliedschaft,
        Mitglied,
        Untergruppe,
        Untergruppenmitgliedschaft,
    )
    from diakronos_app.models.rechte import RechteModul

    s = patched_db()
    s.add(Gruppe(name="UGH", gruppenname="UGH"))
    s.add(RechteModul(gruppe="UGH", modul="chat"))
    s.add(Untergruppe(name="UGK", untergruppenname="Kreis", gruppe="UGH"))
    for kennung in (MI[ANNA], MI[BERT], MI[CLARA]):
        s.add(Gruppenmitgliedschaft(name=f"gm-ugh-{kennung}", parent="UGH",
                                    parentfield="mitglieder", mitglied=kennung))
    for kennung in (MI[ANNA], MI[BERT]):
        s.add(Untergruppenmitgliedschaft(name=f"um-ugk-{kennung}", parent="UGK",
                                         parentfield="mitglieder", mitglied=kennung))
    s.commit()
    _frische_sicht()
    from diakronos_app.api import chat as C

    _set_user(ANNA)
    gespraech = C.gespraech_anlegen("UGH", untergruppe="UGK")["name"]
    antwort = _mitglieder(gespraech, ANNA)
    assert antwort["art"] == "untergruppe"
    # Clara ist nur in der Hauptgruppe — in der Untergruppe nicht zu erwähnen.
    assert _kennungen(antwort) == [MI[BERT]]
    assert antwort["mitglieder"][0]["anzeigename"] == "Bert Brandner"


def test_runde_liefert_nur_aktive_teilnehmende(welt):
    """Runde: die aktiven Teilnehmenden ohne mich; wer gegangen ist, fehlt."""
    runde = _runde_anlegen("Lesekreis-Runde", [MI[BERT], MI[CLARA]])
    antwort = _mitglieder(runde["name"], ANNA)
    assert antwort["art"] == "runde"
    assert _kennungen(antwort) == [MI[BERT], MI[CLARA]]

    _verlassen(runde["name"], CLARA)
    assert _kennungen(_mitglieder(runde["name"], ANNA)) == [MI[BERT]]
    # Wer gegangen ist, darf die Runde auch nicht mehr abfragen.
    with pytest.raises(PermissionError):
        _mitglieder(runde["name"], CLARA)


def test_direkt_liefert_genau_die_andere_person(welt):
    """1:1: die andere Person, mit demselben vollen Namen (Karten-Nachtrag)."""
    gespraech = _direkt(MI[BERT], ANNA)["name"]
    antwort = _mitglieder(gespraech, ANNA)
    assert antwort["art"] == "direkt"
    assert antwort["mitglieder"] == [
        {"mitglied": MI[BERT], "anzeigename": "Bert Brandner"}]

    assert _mitglieder(gespraech, BERT)["mitglieder"] == [
        {"mitglied": MI[ANNA], "anzeigename": "Anna Beispiel"}]

    # Ein Dritter ist nicht beteiligt — neutrale Ablehnung, nicht „leer“.
    with pytest.raises(PermissionError):
        _mitglieder(gespraech, CLARA)


def test_ausgetretene_person_fehlt_gesperrte_ist_drin(welt, patched_db):
    """Ausgetretene fehlen (nicht auffindbar), gesperrte stehen DRIN."""
    from diakronos_app.models.diakonos import Mitglied

    # Die Runde besteht SCHON (mit Clara) — danach sperrt Anna sie. Die Sperre
    # verhindert neue Gespräche, nicht die Erwähnbarkeit im bestehenden.
    runde = _runde_anlegen("Sperr-Runde", [MI[BERT], MI[CLARA]])
    _sperren(MI[CLARA], ANNA)  # Anna sperrt Clara
    _frische_sicht()
    # Die Sperre filtert NICHT — sie darf nicht erkennbar sein.
    assert _kennungen(_mitglieder(runde["name"], ANNA)) == [MI[BERT], MI[CLARA]]

    # Bert tritt aus: er ist danach nicht mehr auffindbar und fehlt.
    s = patched_db()
    s.get(Mitglied, MI[BERT]).status = "Ausgetreten"
    s.commit()
    _frische_sicht()
    assert _kennungen(_mitglieder(runde["name"], ANNA)) == [MI[CLARA]]


def test_ohne_leserecht_neutrale_antwort(welt, gruppe):
    """Ohne LESEN in der Einheit (hier: nicht mehr im Chat-Modul) → 403 ohne Inhalt."""
    from diakronos_app.models.rechte import RechteModul

    from diakronos_app import db as dbmod

    with dbmod.SessionLocal.begin() as s:
        s.query(RechteModul).filter(RechteModul.gruppe == "Lesekreis").delete()
    _frische_sicht()
    for konto in (ANNA, BERT):
        with pytest.raises(PermissionError) as fehler:
            _mitglieder(gruppe["name"], konto)
        # Dieselbe neutrale Ablehnung wie bei den übrigen Chat-Endpunkten:
        # 403 OHNE Inhalt (der Grund bleibt im Server).
        assert not str(fehler.value)

    # Ein unbekanntes Gespräch ist 404 — auch das ohne Auskunft.
    with pytest.raises(DoesNotExistError):
        _mitglieder("gibt-es-nicht", ANNA)


def _viele(patched_db, anzahl: int, *, vornamen=None) -> str:
    """Gruppe „Viele“ mit ``anzahl`` Personen (Konto + Mitglied + Mitgliedschaft)."""
    from diakronos_app.api import chat as C
    from diakronos_app.models.core import User
    from diakronos_app.models.diakonos import (
        Gruppe,
        Gruppenmitgliedschaft,
        Mitglied,
    )
    from diakronos_app.models.rechte import RechteModul

    s = patched_db()
    s.add(Gruppe(name="Viele", gruppenname="Viele"))
    s.add(RechteModul(gruppe="Viele", modul="chat"))
    for i in range(anzahl):
        konto = f"viel{i:03d}@x.org"
        vor, nach = (vornamen[i] if vornamen else ("Viel", f"{i:03d}"))
        s.add(User(name=konto, email=konto, enabled=1,
                   full_name=f"{vor} {nach}"))
        s.add(Mitglied(name=f"M-viel{i:03d}", vorname=vor, nachname=nach,
                       email=konto, user=konto, status="Aktiv"))
        s.add(Gruppenmitgliedschaft(name=f"gm-viel{i:03d}", parent="Viele",
                                    parentfield="mitglieder",
                                    mitglied=f"M-viel{i:03d}"))
    s.add(Gruppenmitgliedschaft(name="gm-viele-a", parent="Viele",
                                parentfield="mitglieder", mitglied=MI[ANNA]))
    s.commit()
    _frische_sicht()

    _set_user(ANNA)
    return C.gespraech_anlegen("Viele")["name"]


def test_q_ein_zeichen_filtert_schon(welt, gruppe):
    """Ein einzelnes Zeichen filtert (Review R1/1).

    ``_suche_begriff`` verlangt sonst zwei Zeichen (Personensuche) und liefert
    darunter ``""`` — hier wäre das ein Muster ``%``, also die Vollliste. Nach
    dem „@“ ist ein Zeichen aber der Normalfall.
    """
    name = gruppe["name"]
    # „b“ trifft nur Bert (Bert Brandner, Nachname Brandner).
    assert _kennungen(_mitglieder(name, ANNA, q="b")) == [MI[BERT]]
    # Groß-/Kleinschreibung egal.
    assert _kennungen(_mitglieder(name, ANNA, q="B")) == [MI[BERT]]
    # „c“ trifft nur Clara — nicht „alle“.
    assert _kennungen(_mitglieder(name, ANNA, q="c")) == [MI[CLARA]]
    # Die Mindestlänge der Personensuche bleibt unverändert (keine zweite Regel).
    from diakronos_app.api import chat as C

    assert C._suche_begriff("b") == ""
    assert C._suche_begriff("b", min_zeichen=1) == "b"


def test_mehr_zaehlt_mich_nicht_als_weiteren_kandidaten(welt, patched_db):
    """Ich selbst macht ``mehr`` nicht true (Review R1/2).

    20 andere Kandidaten, ich stehe als 21. nach Name: alle 20 Treffer sind
    da, dahinter liegt nur noch ICH — also keine weiteren Kandidaten,
    ``mehr: false``. Vorher zählte ich als geprüfter Kandidat und ``mehr``
    war true.
    """
    # Anna steht mit „Aaa“ ganz vorn? Nein — sie soll HINTER den 20 stehen.
    vornamen = [("Mia", f"M{i:02d}") for i in range(20)]
    gespraech = _viele(patched_db, 20, vornamen=vornamen)
    antwort = _mitglieder(gespraech, ANNA)
    assert len(antwort["mitglieder"]) == 20
    assert antwort["mehr"] is False
    # Gegenprobe: kommt noch jemand DAZU, ist wieder etwas dahinter.
    from diakronos_app.api import chat as C
    from diakronos_app.models.core import User
    from diakronos_app.models.diakonos import Gruppenmitgliedschaft, Mitglied

    s = patched_db()
    s.add(User(name="zuletzt@x.org", email="zuletzt@x.org", enabled=1,
               full_name="Zoe Zorn"))
    s.add(Mitglied(name="M-zuletzt", vorname="Zoe", nachname="Zorn",
                   email="zuletzt@x.org", user="zuletzt@x.org", status="Aktiv"))
    s.add(Gruppenmitgliedschaft(name="gm-zuletzt", parent="Viele",
                                parentfield="mitglieder", mitglied="M-zuletzt"))
    s.commit()
    _frische_sicht()
    assert C.gespraech_mitglieder  # Import bleibt benutzt
    assert _mitglieder(gespraech, ANNA)["mehr"] is True


def test_q_ueberspringt_personen_ohne_konto(welt, patched_db):
    """Personen ohne Konto verdrängen die Erwähnbaren NICHT (Review R1/3).

    30 Personen ohne Konto (kein ``mitglied.user``) stehen VORN im Alphabet,
    dahinter 2 Erwähnbare. Ohne den SQL-Vorfilter (``user IS NOT NULL``)
    füllten die 30 die 3*limit-Prüfstrecke und die beiden erschienen nie.
    """
    from diakronos_app.models.core import User
    from diakronos_app.models.diakonos import Gruppenmitgliedschaft, Mitglied

    gespraech = _viele(patched_db, 0)   # nur die Gruppe samt Anna
    s = patched_db()
    for i in range(30):
        s.add(Mitglied(name=f"M-ohne{i:02d}", vorname="Aaa", nachname=f"Ohne{i:02d}",
                       email=f"ohne{i:02d}@x.org", user=None, status="Aktiv"))
        s.add(Gruppenmitgliedschaft(name=f"gm-ohne{i:02d}", parent="Viele",
                                    parentfield="mitglieder",
                                    mitglied=f"M-ohne{i:02d}"))
    for kennung, konto, vor, nach in (("M-zz-1", "zz1@x.org", "Zoe", "Zeta"),
                                      ("M-zz-2", "zz2@x.org", "Zora", "Zorn")):
        s.add(User(name=konto, email=konto, enabled=1, full_name=f"{vor} {nach}"))
        s.add(Mitglied(name=kennung, vorname=vor, nachname=nach,
                       email=konto, user=konto, status="Aktiv"))
        s.add(Gruppenmitgliedschaft(name=f"gm-{kennung}", parent="Viele",
                                    parentfield="mitglieder", mitglied=kennung))
    s.commit()
    _frische_sicht()
    # mit Vorgabe-limit 20 (3*limit = 60 Prüfungen) liegen die beiden
    # Erwähnbaren hinter 30 Kontolosen und 28 Erwähnbaren — ohne Vorfilter
    # wären sie nicht erreichbar.
    assert _kennungen(_mitglieder(gespraech, ANNA)) == ["M-zz-1", "M-zz-2"]


def test_sortierung_haelt_bei_fehlendem_namensteil(welt, patched_db):
    """Ein fehlender Namensteil kippt die Reihenfolge nicht (R1/4)."""
    from diakronos_app.models.core import User
    from diakronos_app.models.diakonos import Gruppenmitgliedschaft, Mitglied

    gespraech = _viele(patched_db, 0)
    s = patched_db()
    for kennung, konto, vor, nach in (
            ("M-n1", "n1@x.org", "Benno", None),
            ("M-n2", "n2@x.org", None, "Abel"),
            ("M-n3", "n3@x.org", "Bea", "Zorn")):
        s.add(User(name=konto, email=konto, enabled=1, full_name=f"{vor} {nach}"))
        s.add(Mitglied(name=kennung, vorname=vor, nachname=nach,
                       email=konto, user=konto, status="Aktiv"))
        s.add(Gruppenmitgliedschaft(name=f"gm-{kennung}", parent="Viele",
                                    parentfield="mitglieder", mitglied=kennung))
    s.commit()
    _frische_sicht()
    # Anzeigenamen: „abel“ (nur Nachname), „bea zorn“, „benno“ (nur Vorname).
    # Ohne COALESCE rutschte die Zeile ohne Vorname in PostgreSQL ans Ende.
    antwort = _mitglieder(gespraech, ANNA)
    assert _kennungen(antwort) == ["M-n2", "M-n3", "M-n1"]
    assert antwort["mehr"] is False


def test_runde_entdoppelt_je_konto(welt, patched_db):
    """1:1/Runde: ein Konto erscheint einmal, auch mit mehreren Zeilen (R1/5).

    Die Teilnahme ist je (Gespräch, Konto) eindeutig — doppelt angefragte
    Konten dürfen trotzdem keinen zweiten Eintrag erzeugen.
    """
    from diakronos_app.api import chat as C
    from diakronos_app import db as dbmod

    runde = _runde_anlegen("Doppel-Runde", [MI[BERT], MI[CLARA]])
    _set_user(ANNA)
    # Dieselbe Konto-Liste doppelt übergeben — der Entdoppler der Sammelstelle
    # (dict) hält die Kandidatenzahl bei 2.
    with dbmod.SessionLocal.begin() as s:
        kandidaten = C._mitglieder_kandidaten(
            s, "", konten=[BERT, BERT, CLARA, CLARA])
    assert [z.mitglied for z in kandidaten] == [MI[BERT], MI[CLARA]]
    assert _kennungen(_mitglieder(runde["name"], ANNA)) == [MI[BERT], MI[CLARA]]


def test_obergrenze_20_und_mehr(welt, patched_db):
    """Vorgabe 20: die ersten 20 nach Anzeigename plus ``mehr: true``."""
    gespraech = _viele(patched_db, 30)
    antwort = _mitglieder(gespraech, ANNA)
    assert len(antwort["mitglieder"]) == 20
    assert antwort["mehr"] is True
    # Die ersten 20 nach Anzeigename: „Viel 000“ … „Viel 019“.
    assert antwort["mitglieder"][0]["anzeigename"] == "Viel 000"
    assert antwort["mitglieder"][-1]["anzeigename"] == "Viel 019"
    assert MI[ANNA] not in _kennungen(antwort)
    # Jeder Eintrag trägt nur Kennung + Name (keine Kontaktdaten).
    for eintrag in antwort["mitglieder"]:
        assert set(eintrag) == {"mitglied", "anzeigename"}


def test_limit_wird_gekappt_und_kleiner_angenommen(welt, patched_db):
    """``limit`` wirkt (5 → 5 Treffer), größer als 20 wird auf 20 gekappt.

    Kleiner als 5 wird auf 5 gehoben (Review R1/6): ``limit=1`` wäre ein
    Seitenkanal — über ``mehr`` ließe sich die Gemeinde Zeichen für Zeichen
    abfragen.
    """
    gespraech = _viele(patched_db, 30)
    assert len(_mitglieder(gespraech, ANNA, limit=5)["mitglieder"]) == 5
    assert len(_mitglieder(gespraech, ANNA, limit=999)["mitglieder"]) == 20
    # Unlesbar/leer → Vorgabe (kein Fehler); 0/1/4 → Untergrenze 5.
    assert len(_mitglieder(gespraech, ANNA, limit="kaputt")["mitglieder"]) == 20
    assert len(_mitglieder(gespraech, ANNA, limit=0)["mitglieder"]) == 5
    assert len(_mitglieder(gespraech, ANNA, limit=1)["mitglieder"]) == 5
    assert len(_mitglieder(gespraech, ANNA, limit=4)["mitglieder"]) == 5


def test_q_filtert_nach_namensanfang(welt, gruppe):
    """``q`` trifft Vorname, Nachname und „Vor Nach“ — Umlaut/Größe egal."""
    name = gruppe["name"]
    # Vorname-Anfang, klein geschrieben: Bert Brandner.
    assert _kennungen(_mitglieder(name, ANNA, q="ber")) == [MI[BERT]]
    # Nachname-Anfang: Brandner → Bert.
    assert _kennungen(_mitglieder(name, ANNA, q="Brand")) == [MI[BERT]]
    # Phrase „Vor Nach“.
    assert _kennungen(_mitglieder(name, ANNA, q="clara c")) == [MI[CLARA]]
    # Kein Treffer → leere Liste, kein „mehr“.
    leer = _mitglieder(name, ANNA, q="zzz")
    assert leer["mitglieder"] == [] and leer["mehr"] is False
    # Leeres/whitespace q = alle Kandidaten (wie ohne q).
    assert _kennungen(_mitglieder(name, ANNA, q="   ")) == [MI[BERT], MI[CLARA]]


def test_q_umlaut_und_grossschreibung(welt, patched_db):
    """„müller“ findet „Müller“ und „Mueller“ (Faltung wie personen_suchen)."""
    from diakronos_app.api import chat as C
    from diakronos_app.models.core import User
    from diakronos_app.models.diakonos import (
        Gruppe,
        Gruppenmitgliedschaft,
        Mitglied,
    )
    from diakronos_app.models.rechte import RechteModul

    s = patched_db()
    s.add(Gruppe(name="Umlaut", gruppenname="Umlaut"))
    s.add(RechteModul(gruppe="Umlaut", modul="chat"))
    for kennung, konto, vor, nach in (
            ("M-ue", "ue@x.org", "Jörg", "Müller"),
            ("M-oe", "oe@x.org", "Özlem", "Özdemir")):
        s.add(User(name=konto, email=konto, enabled=1, full_name=f"{vor} {nach}"))
        s.add(Mitglied(name=kennung, vorname=vor, nachname=nach,
                       email=konto, user=konto, status="Aktiv"))
        s.add(Gruppenmitgliedschaft(name=f"gm-{kennung}", parent="Umlaut",
                                    parentfield="mitglieder", mitglied=kennung))
    s.add(Gruppenmitgliedschaft(name="gm-umlaut-a", parent="Umlaut",
                                parentfield="mitglieder", mitglied=MI[ANNA]))
    s.commit()
    _frische_sicht()

    _set_user(ANNA)
    gespraech = C.gespraech_anlegen("Umlaut")["name"]
    # Getippt ohne Umlaut, klein: findet Müller.
    assert _kennungen(_mitglieder(gespraech, ANNA, q="mueller")) == ["M-ue"]
    assert _kennungen(_mitglieder(gespraech, ANNA, q="MÜLLER")) == ["M-ue"]
    # Umlaut am Wortanfang: Özdemir über „oez“.
    assert _kennungen(_mitglieder(gespraech, ANNA, q="oez")) == ["M-oe"]
    assert _kennungen(_mitglieder(gespraech, ANNA, q="Jörg")) == ["M-ue"]


def test_dreifache_limit_grenze_gepruefter_kandidaten(welt, patched_db):
    """Höchstens ``3*limit`` Kandidaten werden geprüft, dann ``mehr: true``.

    20 Ausgetretene stehen (nach Name) VOR den Erwähnbaren: mit ``limit=5``
    werden nur 15 Kandidaten geprüft — die Erwähnbaren liegen dahinter, die
    Antwort ist leer mit ``mehr: true`` (statt alle 22 durchzuprüfen).
    """
    from diakronos_app import db as dbmod
    from sqlalchemy import update

    from diakronos_app.models.diakonos import Mitglied

    vornamen = [("Aaa", f"{i:02d}") for i in range(20)] + \
               [("Zoe", "Zeta"), ("Zora", "Zorn")]
    gespraech = _viele(patched_db, 22, vornamen=vornamen)
    # Direktes UPDATE (kein Autoflush, kein Konflikt mit den geschriebenen
    # Zeilen) — die Suche selbst löst keinen Autoflush aus.
    with dbmod.SessionLocal.begin() as s:
        geaendert = s.execute(
            update(Mitglied)
            .where(Mitglied.name.in_([f"M-viel{i:03d}" for i in range(20)]))
            .values(status="Ausgetreten")
        ).rowcount
        assert geaendert == 20, geaendert
    _frische_sicht()

    antwort = _mitglieder(gespraech, ANNA, limit=5)
    assert antwort["mitglieder"] == []
    assert antwort["mehr"] is True
    # Ohne 3*limit-Grenze kämen die beiden Erwähnbaren (die Prüfung aller 22
    # wäre der alte Weg) — mit größerem limit tauchen sie auf.
    assert _kennungen(_mitglieder(gespraech, ANNA, limit=20)) == \
        ["M-viel020", "M-viel021"]


def test_abfragezahl_gruppe_300_bleibt_begrenzt(welt, patched_db, engine):
    """300-Personen-Gruppe: < 400 SQL-Anweisungen, höchstens 60 geprüft.

    Vorher (CHAT-9c) kostete DIESELBE Gruppe ~7500 Anweisungen: je Person die
    Einzelprüfung über die Rechte-Regel. Jetzt wird nach Name vorgefiltert und
    nur ``3*limit`` Kandidaten werden geprüft — der Zähler hängt an
    ``before_cursor_execute`` der echten Engine.

    Verglichen wird ``q=""`` mit einem ``q`` MIT Treffern (Review R1/7): ein
    ``q`` ohne Treffer wäre schon durch den SQL-Vorfilter billig und bewiese
    nichts über den Vorfilter-Abbruch. Gewählt ist ``q="Viel 29"`` — es hat
    Treffer (10 Stück), ist aber eng genug, dass der Vorfilter weniger
    Kandidaten durch die Einzelprüfung schickt.
    """
    from sqlalchemy import event

    from diakronos_app import rechte as R

    # 300 Personen — die ersten 20 heißen „Bea …“, der Rest „Viel …“.
    vornamen = [("Bea", f"Be{i:03d}") for i in range(20)] + \
               [("Viel", f"{i:03d}") for i in range(20, 300)]
    gespraech = _viele(patched_db, 300, vornamen=vornamen)
    R.merker_leeren()

    abfragen = [0]

    def _zaehle(*_a, **_k):
        abfragen[0] += 1

    event.listen(engine, "before_cursor_execute", _zaehle)
    try:
        R.merker_leeren()
        antwort = _mitglieder(gespraech, ANNA)
        alle = abfragen[0]
        abfragen[0] = 0
        R.merker_leeren()
        eng = _mitglieder(gespraech, ANNA, q="Viel 29")
        eng_abfragen = abfragen[0]
    finally:
        event.remove(engine, "before_cursor_execute", _zaehle)

    assert len(antwort["mitglieder"]) == 20
    assert antwort["mehr"] is True
    assert alle < 400, f"{alle} SQL-Anweisungen bei 300 Mitgliedern"
    # Enges q MIT Treffern: nur diese Kandidaten werden geprüft.
    assert len(eng["mitglieder"]) == 10
    assert eng["mehr"] is False
    assert eng_abfragen < alle, (eng_abfragen, alle)



# ── 2) nachricht_kontext ────────────────────────────────────────────────────


def test_kontext_erlaubte_nachricht_gruppe_und_direkt(welt, gruppe):
    """Erlaubte Nachricht → Gespräch, Art und der Titel aus `meine_gespraeche`."""
    antwort = _senden(gruppe["name"], "Hallo Kreis", ANNA)
    kontext = _kontext(antwort["name"], BERT)
    assert kontext == {"gespraech": gruppe["name"], "art": "gruppe",
                       "titel": "Lesekreis"}
    # Derselbe Titel wie in der Gesprächsliste (keine zweite Titelregel).
    titel_liste = {g["name"]: g["titel"] for g in _meine(BERT)["gespraeche"]}
    assert titel_liste[gruppe["name"]] == kontext["titel"]

    # 1:1: der Titel ist der Anzeigename des Gegenübers — genau der aus der
    # Gesprächsliste (`_direkt_titel`, mit der Maskierung aus
    # `personen_anzeige`; keine zweite Titelregel hier).
    direkt = _direkt(MI[BERT], ANNA)["name"]
    nachricht = _senden(direkt, "Nur an dich", ANNA)
    kontext = _kontext(nachricht["name"], BERT)
    assert kontext["art"] == "direkt"
    assert kontext["gespraech"] == direkt
    titel_liste = {g["name"]: g["titel"] for g in _meine(BERT)["gespraeche"]}
    assert kontext["titel"] == titel_liste[direkt]
    assert kontext["titel"].startswith("Anna")

    # Runde: der Rundenname.
    runde = _runde_anlegen("Kontext-Runde", [MI[BERT], MI[CLARA]])
    rn = _senden(runde["name"], "In der Runde", ANNA)
    kontext = _kontext(rn["name"], BERT)
    assert kontext["art"] == "runde"
    assert kontext["titel"] == "Kontext-Runde"


def _neutrale_antwort(nachricht: str, konto: str) -> tuple[str, str]:
    with pytest.raises(DoesNotExistError) as fehler:
        _kontext(nachricht, konto)
    return (type(fehler.value).__name__, str(fehler.value))


def test_kontext_vor_sichtbar_ab_geloescht_fremd_und_unbekannt_gleich(welt, patched_db):
    """Alle Fehlfälle antworten GLEICH — keine Auskunft über die Nachricht."""
    from datetime import timedelta

    from diakronos_app import db as dbmod
    from diakronos_app.models.chat import ChatNachricht, ChatTeilnehmer

    # (a) Runde, Nachricht VOR dem Eintritt von Bert.
    runde = _runde_anlegen("Sichtbarkeits-Runde", [MI[BERT], MI[CLARA]])
    alt = _senden(runde["name"], "Von vorher", ANNA)
    with dbmod.SessionLocal.begin() as s:
        zeile = s.get(ChatTeilnehmer, (runde["name"], BERT))
        zeile.sichtbar_ab = s.get(ChatNachricht, alt["name"]).erstellt_am + timedelta(minutes=1)
    _frische_sicht()
    # Für Anna (Eintritt früher) ist dieselbe Nachricht erlaubt — der Beweis,
    # dass die Grenze an der LESENDEN Person hängt und nicht an der Nachricht.
    assert _kontext(alt["name"], ANNA)["gespraech"] == runde["name"]

    # (b) gelöschte Nachricht in einer RUNDE (Clara und Dieter sind beteiligt;
    #     Bert ist es nicht und muss die neutrale 404 bekommen).
    runde_weg = _runde_anlegen("Kontext-Löschung", [MI[BERT], MI[DIETER]])
    weg = _senden(runde_weg["name"], "Wird gelöscht", ANNA)
    from diakronos_app.api import chat as C

    _set_user(ANNA)
    C.loeschen(weg["name"])

    # (c) fremde Nachricht: Clara ist an Annas/Berts 1:1 nicht beteiligt.
    direkt = _direkt(MI[BERT], ANNA)["name"]
    fremd = _senden(direkt, "Geheim", ANNA)

    # (d) unbekannte Kennung.
    neutrale = [
        _neutrale_antwort(alt["name"], BERT),
        _neutrale_antwort(weg["name"], BERT),
        _neutrale_antwort(fremd["name"], CLARA),
        _neutrale_antwort("chat-n-gibtesnicht", BERT),
    ]
    assert len(set(neutrale)) == 1, neutrale
    assert neutrale[0][0] == "DoesNotExistError"


def test_kontext_ohne_leserecht_gleiche_neutrale_antwort(welt, gruppe):
    """Auch das fehlende Leserecht ist dieselbe neutrale Antwort (kein 403)."""
    antwort = _senden(gruppe["name"], "Nur für den Kreis", ANNA)
    vorher = _neutrale_antwort("chat-n-gibtesnicht", DIETER)
    # Dieter ist nicht in der Gruppe → weder lesen noch unterscheiden können.
    assert _neutrale_antwort(antwort["name"], DIETER) == vorher


# ── 3) SEC-11: beide nur GET ────────────────────────────────────────────────


def test_beide_endpunkte_sind_get_only(client):
    """POST → 405 mit ``Allow: GET`` (kein Schreibweg über die Leser)."""
    for name in ("gespraech_mitglieder", "nachricht_kontext"):
        antwort = client.post(
            f"/api/method/diakronos.diakonos.api.chat.{name}",
            params={"gespraech": "egal", "nachricht": "egal"})
        assert antwort.status_code == 405, (name, antwort.text)
        assert antwort.headers["allow"] == "GET"


def test_beide_endpunkte_sind_im_register_als_get():
    from diakronos_app.api import chat as C
    from diakronos_app.frappe_compat.registry import lookup, methoden_fuer

    for name in ("gespraech_mitglieder", "nachricht_kontext"):
        fn = getattr(C, name)
        assert methoden_fuer(fn) == ("GET",), name
        assert lookup(f"diakronos_app.api.chat.{name}") is fn, name

