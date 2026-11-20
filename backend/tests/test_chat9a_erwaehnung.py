"""CHAT-9a: Erwähnungen (@Name) — Konzept S4, Kapitel 2 (Rechte über den Kern).

Geprüft wird gegen die ECHTEN Endpunkte (``api.chat``), den ECHTEN Rechte-Kern
(``rechte/kern.py``), die ECHTE ``Notification Log``-Zeile und die ECHTE
Datenbank — keine Attrappe:

  * gültige Erwähnung → Zeile in ``chat_erwaehnung`` + EIGENE Glocke
    (``document_type = 'chat_erwaehnung'``, NICHT gebündelt mit dem
    Gesprächs-Zähler)
  * STILL verworfen (kein Fehler, keine Glocke, keine Zeile): Nicht-Beteiligte,
    sich selbst, Runden-Teilnehmende vor ``sichtbar_ab``, ausgetretene Runde,
    Person ohne Konto
  * Kontaktsperre (beide Richtungen) → Erwähnung GESPEICHERT, Glocke NICHT
    (Entscheidung Operator R1/3: eine Sperre darf nie erkennbar sein)
  * Duplikate zusammengefasst; die Obergrenze (20) greift VOR der Prüfung
  * stumm geschaltetes Gespräch → Erwähnungs-Glocke klingelt trotzdem
  * Lesestand markiert die Erwähnungs-Glocke als gelesen (EIN UPDATE)
  * Verlauf liefert ``erwaehnt: [{mitglied, anzeigename}]``, gefiltert über
    ``rechte.darf_person_finden``; gelöschte Nachricht → leere Liste, Zeilen
    weg, Glocke gelesen
  * Moderations-Entfernung (``meldung_entscheiden``) räumt genauso auf
  * Bearbeiten erzeugt KEINE neue Glocke
  * Migration ``chat9a_erwaehnung``: genau ein Kopf, Kante hinter
    ``chat7b_runden``, up/down/up auf SQLite
  * SEC-11: ``senden`` bleibt POST-only, Inventar-Eintrag unverändert

Aufruf (Karte):
    docker run --rm --network none --entrypoint python -v <wt>:/repo:ro \\
      -w /repo/backend -e PYTHONPATH=/repo/backend/src:/repo/backend/tests:/repo/tools \\
      -e PYTHONDONTWRITEBYTECODE=1 <vorbau> -m pytest -q -p no:cacheprovider \\
      tests/test_chat9a_erwaehnung.py
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory

from diakronos_app.models.chat import (
    ART_RUNDE,
    ERWAEHNUNGEN_MAX,
    ChatErwaehnung,
    ChatNachricht,
    ChatTeilnehmer,
)
from diakronos_app.models.core import NotificationLog

#: Die Test-Naht liegt im MODUL ``frappe_compat.session`` (wie ``test_chat2_api``).
_session_mod = importlib.import_module("diakronos_app.frappe_compat.session")

#: Dieselbe Welt wie ``test_chat7b_runden`` (Chor, Untergruppe, Konten) —
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

BACKEND = Path(__file__).resolve().parents[1]

#: Der Chor-Chat aus ``test_chat4a_glocke`` passt hier nicht (andere Welt) —
#: die Erwähnungen werden in RUNDEN und im 1:1 geprüft; für Gruppe/Untergruppe
#: steht ein eigener kleiner Aufbau unten (``gruppe``-Fixture).


# ── Hilfen ──────────────────────────────────────────────────────────────────


def _senden(gespraech: str, text: str, konto: str, erwaehnt=None) -> dict:
    from diakronos_app.api import chat as C

    _set_user(konto)
    return C.senden(gespraech, text, erwaehnt=erwaehnt)


def _verlauf(gespraech: str, konto: str, **kwargs) -> dict:
    from diakronos_app.api import chat as C

    _set_user(konto)
    return C.verlauf(gespraech, **kwargs)


def _lesen(gespraech: str, konto: str, nachricht=None) -> dict:
    from diakronos_app.api import chat as C

    _set_user(konto)
    return C.lesestand_setzen(gespraech, nachricht)


def _loeschen(nachricht: str, konto: str) -> dict:
    from diakronos_app.api import chat as C

    _set_user(konto)
    return C.loeschen(nachricht)


def _aendern(nachricht: str, text: str, konto: str) -> dict:
    from diakronos_app.api import chat as C

    _set_user(konto)
    return C.aendern(nachricht, text)


def _stumm(gespraech: str, konto: str, an=True) -> dict:
    from diakronos_app.api import chat as C

    _set_user(konto)
    return C.stumm_setzen(gespraech, an)


@pytest.fixture()
def drei(welt):
    """Die Standard-Runde Anna/Bert/Clara (Anna legt an)."""
    return _runde_anlegen("Kigo-Vorbereitung", [MI[BERT], MI[CLARA]])


def _zeilen(nachricht: str | None = None) -> list[ChatErwaehnung]:
    from diakronos_app import db as dbmod

    with dbmod.SessionLocal() as s:
        abfrage = s.query(ChatErwaehnung)
        if nachricht:
            abfrage = abfrage.filter(ChatErwaehnung.nachricht == nachricht)
        return list(abfrage.all())


def _glocken(konto: str | None = None, nachricht: str | None = None,
             dtype: str = "chat_erwaehnung") -> list[NotificationLog]:
    from diakronos_app import db as dbmod

    with dbmod.SessionLocal() as s:
        abfrage = s.query(NotificationLog).filter(
            NotificationLog.document_type == dtype)
        if konto is not None:
            abfrage = abfrage.filter(NotificationLog.for_user == konto)
        if nachricht is not None:
            abfrage = abfrage.filter(NotificationLog.document_name == nachricht)
        return list(abfrage.all())


def _mitglieder(gespraech: str, text: str, konto: str, erwaehnt=None) -> dict:
    """Senden und die (gültigen) Erwähnungen der Antwort zurückgeben."""
    return _senden(gespraech, text, konto, erwaehnt=erwaehnt)


# ── 1) Gültige Erwähnung: Zeile + eigene Glocke ─────────────────────────────


def test_gueltige_erwaehnung_schreibt_zeile_und_eigene_glocke(welt, drei):
    antwort = _mitglieder(drei["name"], "Kannst du das übernehmen?", ANNA,
                          erwaehnt=[MI[BERT]])
    assert antwort["erwaehnt"] == [{"mitglied": MI[BERT],
                                    "anzeigename": "Bert Brandner"}]
    zeilen = _zeilen(antwort["name"])
    assert [(z.mitglied) for z in zeilen] == [MI[BERT]]

    glocken = _glocken(BERT, antwort["name"])
    assert len(glocken) == 1
    assert glocken[0].document_type == "chat_erwaehnung"
    assert glocken[0].read is False
    # Text im Stil der Chat-Glocken: KEIN Nachrichtentext, KEIN Absendername.
    assert "Kannst du das übernehmen" not in (glocken[0].subject or "")
    assert "Kannst du das übernehmen" not in (glocken[0].email_content or "")
    assert "Anna" not in (glocken[0].subject or "")
    assert "Anna" not in (glocken[0].email_content or "")
    assert "erwähnt" in (glocken[0].subject or "")

    # Die erwähnte Person bekommt KEINE der gebündelten Gesprächs-Glocken
    # (eigene Glocke, nicht gebündelt) …
    assert _glocken(BERT, antwort["name"], dtype="chat_gespraech") == []
    # … und niemand sonst (Clara ist nicht erwähnt).
    assert _glocken(CLARA) == []


def test_glocke_ist_eine_eigene_art_neben_dem_gespraechs_merker(welt, drei):
    """Die Erwähnungs-Glocke überschreibt NICHT die Bündel-Glocke."""
    from diakronos_app.api import chat as C
    from diakronos_app.models.chat import ChatGlocke
    from diakronos_app import db as dbmod

    antwort = _mitglieder(drei["name"], "Hallo @Bert", ANNA, erwaehnt=[MI[BERT]])
    assert C.CHAT_ERWAEHNUNG_GLOCKE_DOCTYPE != C.CHAT_GLOCKE_DOCTYPE
    assert _glocken(BERT, antwort["name"], dtype=C.CHAT_GLOCKE_DOCTYPE) == []
    with dbmod.SessionLocal() as s:
        # Der Merker der gebündelten Glocke wurde nicht angelegt/verändert.
        assert s.query(ChatGlocke).count() == 0


def test_mehrere_erwaehnungen_mehrere_glocken(welt, drei):
    antwort = _mitglieder(drei["name"], "Ihr zwei bitte", ANNA,
                          erwaehnt=[MI[BERT], MI[CLARA]])
    assert {e["mitglied"] for e in antwort["erwaehnt"]} == {MI[BERT], MI[CLARA]}
    assert len(_glocken(BERT, antwort["name"])) == 1
    assert len(_glocken(CLARA, antwort["name"])) == 1


# ── 2) Stilles Verwerfen ────────────────────────────────────────────────────


def test_nicht_beteiligte_person_wird_still_verworfen(welt, drei):
    """Dieter ist nicht in der Runde — kein Fehler, keine Zeile, keine Glocke."""
    antwort = _mitglieder(drei["name"], "Hallo", ANNA,
                          erwaehnt=[MI[DIETER], MI[BERT]])
    assert [e["mitglied"] for e in antwort["erwaehnt"]] == [MI[BERT]]
    assert [z.mitglied for z in _zeilen(antwort["name"])] == [MI[BERT]]
    assert _glocken(DIETER) == []


def test_sich_selbst_erwaehnen_wird_still_verworfen(welt, drei):
    antwort = _mitglieder(drei["name"], "Ich selbst", ANNA,
                          erwaehnt=[MI[ANNA], MI[BERT]])
    assert [e["mitglied"] for e in antwort["erwaehnt"]] == [MI[BERT]]
    assert _glocken(ANNA) == []


def test_kontaktsperre_verwirft_nicht_sondern_glockt_nicht(welt, drei):
    """ENTSCHEIDUNG Operator R1/3 (eine Sperre darf nie erkennbar sein).

    Eine Kontaktsperre verwirft die Erwähnung NICHT mehr still: die Zeile
    wird gespeichert und erscheint in ``erwaehnt`` wie jede andere — die
    Antwort an die sendende Person ist mit und ohne Sperre GLEICH (sonst
    verriete das Fehlen des Eintrags die Sperre). Nur die GLOCKE unterbleibt:
    die gesperrte Person merkt nichts.

    Zwei Läufe mit JE EINER Sperre — eine Sperre zwischen zwei
    Rundenteilnehmenden blockiert auch das Senden der anderen im Gespräch
    (vorhandene CHAT-7b-Regel, nicht die der Erwähnung): geprüft wird hier
    allein die Erwähnung.
    """
    # Richtung 1: Bert sperrt Anna. Anna erwähnt Bert → Zeile ja, Glocke nein.
    _sperren(MI[ANNA], BERT)
    antwort = _mitglieder(drei["name"], "Trotzdem", ANNA, erwaehnt=[MI[BERT]])
    assert [e["mitglied"] for e in antwort["erwaehnt"]] == [MI[BERT]]
    assert [z.mitglied for z in _zeilen(antwort["name"])] == [MI[BERT]]
    assert _glocken(BERT) == []
    # Clara (kein gesperrtes Paar mit Anna) wird erwähnt UND klingelt.
    antwort2 = _mitglieder(drei["name"], "Clara auch", ANNA, erwaehnt=[MI[CLARA]])
    assert [e["mitglied"] for e in antwort2["erwaehnt"]] == [MI[CLARA]]
    assert len(_glocken(CLARA, antwort2["name"])) == 1
    # DIE Antwort ist gleich der ohne Sperre — genau dieselben Felder.
    ohne = _mitglieder(drei["name"], "Ohne Sperre", ANNA, erwaehnt=[MI[CLARA]])
    assert set(ohne) == set(antwort2)


def test_gesperrte_person_wird_auch_gegen_die_richtung_geglockt_nicht(welt, drei, patched_db):
    """Die Sperre der ANDEREN Seite wirkt genauso (EINE Abfrage, beide Richtungen)."""
    from diakronos_app.models.rechte import RechteKontaktsperre

    # Zeile direkt setzen: Bert hat Anna gesperrt, Anna sendet. (Über den
    # Endpunkt ginge es nicht — ``kontakt_sperren`` prüft selbst.)
    s = patched_db()
    s.add(RechteKontaktsperre(benutzer=BERT, gesperrt=ANNA, angelegt_am=None))
    s.commit()
    from diakronos_app import rechte as R

    R.merker_leeren()
    # Umgekehrt sperrt ANNA nicht — der Schreibweg bleibt offen (keine
    # Sperre gegen CLARA), die Erwähnung von Bert steht, seine Glocke fehlt.
    antwort = _mitglieder(drei["name"], "Hallo Bert", ANNA, erwaehnt=[MI[BERT], MI[CLARA]])
    assert [e["mitglied"] for e in antwort["erwaehnt"]] == [MI[BERT], MI[CLARA]]
    assert _glocken(BERT) == []
    assert len(_glocken(CLARA, antwort["name"])) == 1


def test_runde_vor_sichtbar_ab_wird_verworfen(welt, drei, patched_db):
    """Wer erst NACH der Nachricht eintrat, sieht sie nicht — also keine Erwähnung.

    Nachgestellt über ``chat_teilnehmer.sichtbar_ab`` der Person (dieselbe
    Grenze, die ``verlauf``/``_vor_eintritt`` zieht): Bert tritt der Runde
    erst später bei.
    """
    from datetime import datetime

    s = patched_db()
    zeile = s.get(ChatTeilnehmer, (drei["name"], BERT))
    assert zeile is not None
    zeile.sichtbar_ab = datetime(2030, 1, 1, 12, 0)
    s.commit()
    from diakronos_app import rechte as R

    R.merker_leeren()

    antwort = _mitglieder(drei["name"], "Später Bert", ANNA, erwaehnt=[MI[BERT]])
    assert antwort["erwaehnt"] == []
    assert _zeilen(antwort["name"]) == []
    assert _glocken(BERT) == []


def test_ausgetretene_person_wird_verworfen(welt, drei):
    """``runde_verlassen`` → keine Teilnahme mehr → keine Erwähnung."""
    _verlassen(drei["name"], CLARA)
    antwort = _mitglieder(drei["name"], "Clara?", ANNA, erwaehnt=[MI[CLARA]])
    assert antwort["erwaehnt"] == []
    assert _glocken(CLARA) == []


def test_person_ohne_konto_wird_verworfen(welt, drei, patched_db):
    """Eine Kennung ohne Konto kann keine Glocke bekommen — also keine Zeile."""
    from diakronos_app.models.diakonos import Mitglied

    s = patched_db()
    s.add(Mitglied(name="M-ohne", vorname="Olaf", nachname="Ohnberg",
                   email="ohne@x.org", user=None, status="Aktiv"))
    s.commit()
    antwort = _mitglieder(drei["name"], "Olaf?", ANNA, erwaehnt=["M-ohne"])
    assert antwort["erwaehnt"] == []
    assert _zeilen(antwort["name"]) == []
    # Unbekannte Kennung ebenso still.
    antwort2 = _mitglieder(drei["name"], "Niemand?", ANNA,
                           erwaehnt=["M-gibt-es-nicht"])
    assert antwort2["erwaehnt"] == []


def test_ungueltiger_behaelter_ist_wie_keine_erwaehnung(welt, drei):
    """Kein Fehler bei kaputtem ``erwaehnt`` — kein Parsen, keine Auskunft."""
    for kaputt in ("kein json", "{", 42, {"mitglied": MI[BERT]}, None, ""):
        antwort = _mitglieder(drei["name"], f"Kaputt {kaputt!r}", ANNA,
                              erwaehnt=kaputt)
        assert antwort["erwaehnt"] == [], kaputt
    # Eine EINZELNE Kennung als Zeichenkette ist erlaubt (Formularweg).
    antwort = _mitglieder(drei["name"], "Einzeln", ANNA, erwaehnt=MI[BERT])
    assert [e["mitglied"] for e in antwort["erwaehnt"]] == [MI[BERT]]


def test_json_zeichenkette_und_dikt_formen(welt, drei):
    """Die Formen, die ein Formular/JSON-Client schickt — alles andere still."""
    antwort = _mitglieder(drei["name"], "JSON", ANNA,
                          erwaehnt=json.dumps([MI[BERT], {"mitglied": MI[CLARA]}]))
    assert {e["mitglied"] for e in antwort["erwaehnt"]} == {MI[BERT], MI[CLARA]}


def test_duplikate_werden_zusammengefasst(welt, drei):
    antwort = _mitglieder(drei["name"], "Doppelt", ANNA,
                          erwaehnt=[MI[BERT], MI[BERT], " " + MI[BERT] + " "])
    assert [e["mitglied"] for e in antwort["erwaehnt"]] == [MI[BERT]]
    assert len(_zeilen(antwort["name"])) == 1
    assert len(_glocken(BERT, antwort["name"])) == 1


def test_mehr_als_zwanzig_werden_gekappt(welt, patched_db):
    """Höchstens ``ERWAEHNUNGEN_MAX`` (20) je Nachricht; der Rest fällt weg."""
    from diakronos_app.api import chat as C
    from diakronos_app.models.core import User
    from diakronos_app.models.diakonos import (
        Gruppe,
        Gruppenmitgliedschaft,
        Mitglied,
    )
    from diakronos_app.models.rechte import RechteModul

    s = patched_db()
    # Eine EIGENE Gruppe mit Chat-Modul (die Welt der Runden-Tests hat keine).
    s.add(Gruppe(name="Kappung", gruppenname="Kappung"))
    s.add(RechteModul(gruppe="Kappung", modul="chat"))
    kennungen = []
    for i in range(ERWAEHNUNGEN_MAX + 5):
        konto = f"viel{i}@x.org"
        kennung = f"M-viel{i}"
        s.add(User(name=konto, email=konto, enabled=1, full_name=f"Viel {i}"))
        s.add(Mitglied(name=kennung, vorname=f"Viel{i}", nachname="Mehr",
                       email=konto, user=konto, status="Aktiv"))
        s.add(Gruppenmitgliedschaft(name=f"gm-viel{i}", parent="Kappung",
                                    parentfield="mitglieder", mitglied=kennung))
        kennungen.append(kennung)
    # Die sendende Person ist ebenfalls Mitglied (sonst kein LESEN/ANLEGEN).
    s.add(Gruppenmitgliedschaft(name="gm-sender", parent="Kappung",
                                parentfield="mitglieder", mitglied=MI[BERT]))
    s.commit()

    from diakronos_app import rechte as R

    _set_user(BERT)
    R.merker_leeren()
    gespraech = C.gespraech_anlegen("Kappung")["name"]
    # Der Sender steht selbst als Teilnehmer — er wird nie erwähnt.
    antwort = C.senden(gespraech, "Alle bitte", erwaehnt=kennungen)
    assert len(antwort["erwaehnt"]) == ERWAEHNUNGEN_MAX
    # GENAU die ersten 20 (in der Reihenfolge des Clients geprüft) — die
    # Antwort sortiert für die Anzeige nach Kennung, die AUSWAHL ist die des
    # Clients.
    assert {e["mitglied"] for e in antwort["erwaehnt"]} == set(kennungen[:ERWAEHNUNGEN_MAX])
    assert len(_zeilen(antwort["name"])) == ERWAEHNUNGEN_MAX
    assert {z.mitglied for z in _zeilen(antwort["name"])} == set(kennungen[:ERWAEHNUNGEN_MAX])


def test_obergrenze_vor_der_pruefung_zaehlt_nur_die_ersten_zwanzig(welt, drei):
    """25 Kennungen, die ersten 20 ungültig → keine Erwähnung, Bert fällt weg.

    (Ohne Kappung vor der Prüfung stünde Bert als 21. Eintrag in der Liste und
    würde gespeichert — die Obergrenze ist eine Grenze der PRÜFUNG, nicht des
    Ergebnisses.)
    """
    import time

    fremd = [f"M-gibt-es-nicht-{i}" for i in range(ERWAEHNUNGEN_MAX)]
    beginn = time.monotonic()
    antwort = _mitglieder(drei["name"], "Nur Unsinn zuerst", ANNA,
                          erwaehnt=fremd + [MI[BERT]])
    dauer = time.monotonic() - beginn
    assert antwort["erwaehnt"] == []
    assert _zeilen(antwort["name"]) == []
    assert _glocken(BERT) == []
    # Schnelle Antwort: 25 unbekannte Kennungen, davon 20 geprüft (statt 25).
    assert dauer < 5.0, dauer


# ── 3) Stumm und Lesen ──────────────────────────────────────────────────────


def test_stumm_glocke_klingelt_trotzdem(welt, drei):
    """Bewusste Entscheidung der Karte: Erwähnung klingelt auch bei stumm."""
    _stumm(drei["name"], BERT, True)
    antwort = _mitglieder(drei["name"], "Auch bei stumm", ANNA,
                          erwaehnt=[MI[BERT]])
    assert [e["mitglied"] for e in antwort["erwaehnt"]] == [MI[BERT]]
    assert len(_glocken(BERT, antwort["name"])) == 1
    # Die gebündelte Gesprächs-Glocke bleibt davon unberührt: der Job
    # überspringt stumm geschaltete Personen (CHAT-4a/F3) — die Erwähnung
    # kommt aus ``senden`` und hat mit dem Job nichts zu tun.
    from diakronos_app.api import chat as C

    C.chat_glocken_buendeln(ruhe=0)
    assert _glocken(BERT, dtype="chat_gespraech") == []


def test_lesen_markiert_die_erwaehnungs_glocke_als_gelesen(welt, drei):
    erste = _mitglieder(drei["name"], "Erste", ANNA, erwaehnt=[MI[BERT]])
    assert _glocken(BERT, erste["name"])[0].read is False
    _lesen(drei["name"], BERT, erste["name"])
    assert _glocken(BERT, erste["name"])[0].read is True


def test_lesen_bis_zur_erwaehnung_laesst_spaetere_offen(welt, drei):
    """Nur bis zur Nachricht — was DANACH erwähnt, bleibt ungelesen."""
    erste = _mitglieder(drei["name"], "Erste", ANNA, erwaehnt=[MI[BERT]])
    zweite = _mitglieder(drei["name"], "Zweite", ANNA, erwaehnt=[MI[BERT]])
    _lesen(drei["name"], BERT, erste["name"])
    assert _glocken(BERT, erste["name"])[0].read is True
    assert _glocken(BERT, zweite["name"])[0].read is False


def test_lesen_ohne_anker_markiert_alles_bis_zur_neuesten(welt, drei):
    erste = _mitglieder(drei["name"], "Erste", ANNA, erwaehnt=[MI[BERT]])
    zweite = _mitglieder(drei["name"], "Zweite", ANNA, erwaehnt=[MI[BERT]])
    _lesen(drei["name"], BERT)  # ohne Grenze = bis zur neuesten
    assert _glocken(BERT, erste["name"])[0].read is True
    assert _glocken(BERT, zweite["name"])[0].read is True


# ── 4) Verlauf liefert `erwaehnt` ───────────────────────────────────────────


def test_verlauf_liefert_erwaehnt_mit_anzeigename(welt, drei):
    antwort = _mitglieder(drei["name"], "Hallo", ANNA, erwaehnt=[MI[BERT]])
    seite = _verlauf(drei["name"], CLARA)
    zeile = [n for n in seite["nachrichten"] if n["name"] == antwort["name"]][0]
    assert zeile["erwaehnt"] == [{"mitglied": MI[BERT],
                                  "anzeigename": "Bert Brandner"}]


def test_verlauf_ohne_erwaehnung_hat_leere_liste(welt, drei):
    antwort = _mitglieder(drei["name"], "Niemand genannt", ANNA)
    seite = _verlauf(drei["name"], BERT)
    zeile = [n for n in seite["nachrichten"] if n["name"] == antwort["name"]][0]
    assert zeile["erwaehnt"] == []


def test_verlauf_laesst_nicht_auffindbare_personen_weg(welt, drei, patched_db):
    """Review R1/2: ``erwaehnt`` zeigt nur, wer für die LESENDE Person sichtbar ist.

    A (Anna) erwähnt B (Bert). Bert tritt aus (``status`` ausgetreten) — seine
    ERWÄHNUNG bleibt gespeichert (der Text nennt ihn ohnehin), aber die
    strukturierte Liste zeigt ihn C (Clara) nicht mehr. Dieselbe Kern-Frage
    wie überall: ``rechte.darf_person_finden`` (Kapitel 2.4).
    """
    from diakronos_app.models.diakonos import Mitglied
    from diakronos_app import rechte as R

    antwort = _mitglieder(drei["name"], "Hallo Bert", ANNA, erwaehnt=[MI[BERT]])
    seite = _verlauf(drei["name"], CLARA)
    zeile = [n for n in seite["nachrichten"] if n["name"] == antwort["name"]][0]
    assert [e["mitglied"] for e in zeile["erwaehnt"]] == [MI[BERT]]

    s = patched_db()
    s.get(Mitglied, MI[BERT]).status = "Ausgetreten"
    s.commit()
    R.merker_leeren()

    seite2 = _verlauf(drei["name"], CLARA)
    zeile2 = [n for n in seite2["nachrichten"] if n["name"] == antwort["name"]][0]
    assert zeile2["erwaehnt"] == []
    # Der Text bleibt stehen — der Filter betrifft nur die Liste.
    assert "Hallo Bert" in (zeile2["text"] or "")
    # Die Zeile ist weiter gespeichert (niemand wurde stillschweigend
    # enteignet); nur die ANZEIGE ist gefiltert.
    assert [z.mitglied for z in _zeilen(antwort["name"])] == [MI[BERT]]


def test_gruppe_mitglied_ohne_teilnahmezeile_ist_erwaehnbar(welt, patched_db):
    """Review R1/8: in einer GRUPPE braucht es keine Teilnahmezeile.

    Der Raum ist die Einheit: wer die Gruppe lesen darf, liest auch die
    Nachricht — eine Teilnahmezeile entsteht dort erst beim Öffnen des Chats
    und darf die Erwähnung nicht verhindern. Ein NICHT-Mitglied fällt still
    weg.
    """
    from diakronos_app.api import chat as C
    from diakronos_app.models.diakonos import (
        Gruppe,
        Gruppenmitgliedschaft,
        Mitglied,
    )
    from diakronos_app.models.rechte import RechteModul

    s = patched_db()
    s.add(Gruppe(name="Erwaehnbar", gruppenname="Erwaehnbar"))
    s.add(RechteModul(gruppe="Erwaehnbar", modul="chat"))
    s.add(Mitglied(name="M-nie-geoeffnet", vorname="Nina", nachname="Neu",
                   email="nina@x.org", user="nina@x.org", status="Aktiv"))
    from diakronos_app.models.core import User

    s.add(User(name="nina@x.org", email="nina@x.org", enabled=1,
               full_name="Nina Neu"))
    for kennung, gm in [(MI[ANNA], "gm-erw-a"), ("M-nie-geoeffnet", "gm-erw-n")]:
        s.add(Gruppenmitgliedschaft(name=gm, parent="Erwaehnbar",
                                    parentfield="mitglieder", mitglied=kennung))
    s.commit()
    from diakronos_app import rechte as R

    _set_user(ANNA)
    R.merker_leeren()
    gespraech = C.gespraech_anlegen("Erwaehnbar")["name"]
    # Nina hat den Chat nie geöffnet (keine chat_teilnehmer-Zeile) — sie ist
    # Mitglied der Gruppe und darum erwähnbar.
    antwort = C.senden(gespraech, "Nina, bitte", erwaehnt=["M-nie-geoeffnet", MI[DIETER]])
    assert [e["mitglied"] for e in antwort["erwaehnt"]] == ["M-nie-geoeffnet"]
    assert len(_glocken("nina@x.org", antwort["name"])) == 1
    # Dieter ist kein Mitglied dieser Gruppe → still verworfen.
    assert _zeilen(antwort["name"]) and [z.mitglied for z in _zeilen(antwort["name"])] == ["M-nie-geoeffnet"]
    assert _glocken(DIETER) == []


def test_untergruppe_nicht_mitglied_ist_nicht_erwaehnbar(welt, patched_db):
    """Untergruppe: nur wer die EINHEIT lesen darf (Kern), sonst still verworfen."""
    from diakronos_app.api import chat as C
    from diakronos_app.models.diakonos import (
        Gruppe,
        Gruppenmitgliedschaft,
        Mitglied,
        Untergruppe,
        Untergruppenmitgliedschaft,
    )
    from diakronos_app.models.rechte import RechteModul

    s = patched_db()
    s.add(Gruppe(name="UG-Haupt", gruppenname="UG-Haupt"))
    s.add(RechteModul(gruppe="UG-Haupt", modul="chat"))
    s.add(Untergruppe(name="UG-Kreis", untergruppenname="Kreis", gruppe="UG-Haupt"))
    for kennung in (MI[ANNA], MI[BERT]):
        s.add(Gruppenmitgliedschaft(name=f"gm-ug-{kennung}", parent="UG-Haupt",
                                    parentfield="mitglieder", mitglied=kennung))
        s.add(Untergruppenmitgliedschaft(name=f"um-ug-{kennung}", parent="UG-Kreis",
                                         parentfield="mitglieder", mitglied=kennung))
    s.add(Mitglied(name="M-aussen", vorname="Aussen", nachname="Vor",
                   email="aussen@x.org", user="aussen@x.org", status="Aktiv"))
    from diakronos_app.models.core import User

    s.add(User(name="aussen@x.org", email="aussen@x.org", enabled=1,
               full_name="Aussen Vor"))
    s.commit()
    from diakronos_app import rechte as R

    _set_user(ANNA)
    R.merker_leeren()
    gespraech = C.gespraech_anlegen("UG-Haupt", untergruppe="UG-Kreis")["name"]
    antwort = C.senden(gespraech, "Bert und Aussen", erwaehnt=[MI[BERT], "M-aussen"])
    assert [e["mitglied"] for e in antwort["erwaehnt"]] == [MI[BERT]]
    assert _glocken("aussen@x.org") == []


def test_erwaehnung_in_einem_zu_eins(welt):
    """1:1: das Gegenüber ist Beteiligte/r und wird erwähnt."""
    from diakronos_app.api import chat as C

    _set_user(ANNA)
    gespraech = C.direkt_oeffnen(MI[BERT])["name"]
    antwort = _senden(gespraech, "Nur an dich", ANNA, erwaehnt=[MI[BERT]])
    assert [e["mitglied"] for e in antwort["erwaehnt"]] == [MI[BERT]]
    assert len(_glocken(BERT, antwort["name"])) == 1
    # Ein Dritter (Clara) ist nicht Beteiligte → still verworfen.
    antwort2 = _senden(gespraech, "Auch Clara?", ANNA, erwaehnt=[MI[CLARA]])
    assert antwort2["erwaehnt"] == []
    assert _glocken(CLARA) == []


# ── 5) Löschen räumt auf ────────────────────────────────────────────────────


def test_loeschen_raeumt_erwaehnungen_und_glocke(welt, drei):
    antwort = _mitglieder(drei["name"], "Wird gelöscht", ANNA,
                          erwaehnt=[MI[BERT]])
    assert len(_zeilen(antwort["name"])) == 1
    assert _glocken(BERT, antwort["name"])[0].read is False

    _loeschen(antwort["name"], ANNA)
    assert _zeilen(antwort["name"]) == []
    # Die Glockenzeile bleibt als Nachweis stehen, ist aber GELESEN — sie
    # führt nicht mehr auf eine Lücke.
    glocken = _glocken(BERT, antwort["name"])
    assert len(glocken) == 1
    assert glocken[0].read is True

    # Der Verlauf zeigt an der Lücke keine Erwähnung.
    seite = _verlauf(drei["name"], BERT)
    zeile = [n for n in seite["nachrichten"] if n["name"] == antwort["name"]][0]
    assert zeile["geloescht"] is True
    assert zeile["erwaehnt"] == []


def test_zweites_loeschen_ist_idempotent(welt, drei):
    antwort = _mitglieder(drei["name"], "Zweimal", ANNA, erwaehnt=[MI[BERT]])
    _loeschen(antwort["name"], ANNA)
    _loeschen(antwort["name"], ANNA)  # kein Fehler
    assert _zeilen(antwort["name"]) == []


def test_moderations_entfernung_raeumt_erwaehnungen_und_glocke(welt, drei):
    """Review R1/8: ``meldung_entscheiden`` → ``entfernen`` räumt genauso auf.

    Dieselbe Stelle wie ``loeschen`` (``_nachricht_erwaehnungen_raeumen``):
    Zeilen weg, offene Erwähnungs-Glocke auf gelesen — sie führt sonst auf
    nichts. In einer RUNDE ist die Meldestelle der Administrator (F7,
    ``rechte.ist_meldestelle``) — kein stiller Mitleser, sondern der Meldeweg.
    """
    from diakronos_app.api import chat as C

    antwort = _mitglieder(drei["name"], "Boese Nachricht", ANNA,
                          erwaehnt=[MI[BERT]])
    assert len(_zeilen(antwort["name"])) == 1
    assert _glocken(BERT, antwort["name"])[0].read is False

    _set_user(BERT)
    gemeldet = C.meldung_senden(antwort["name"], "spam")
    _set_user("Administrator")
    C.meldung_entscheiden(gemeldet["name"], "entfernen", grund="Regelverstoss")

    assert _zeilen(antwort["name"]) == []
    glocken = _glocken(BERT, antwort["name"])
    assert len(glocken) == 1
    assert glocken[0].read is True


# ── 6) Bearbeiten: keine neue Glocke, keine neuen Erwähnungen ───────────────


def test_bearbeiten_erzeugt_keine_neue_glocke(welt, drei):
    antwort = _mitglieder(drei["name"], "Tippfehler", ANNA, erwaehnt=[MI[BERT]])
    vorher = _glocken(BERT, antwort["name"])
    assert len(vorher) == 1
    _aendern(antwort["name"], "Tippfehler behoben", ANNA)
    nachher = _glocken(BERT, antwort["name"])
    assert len(nachher) == 1
    assert nachher[0].name == vorher[0].name  # dieselbe Zeile, nicht doppelt
    # Erwähnungen bleiben wie beim Senden (``aendern`` hat kein ``erwaehnt``).
    assert [z.mitglied for z in _zeilen(antwort["name"])] == [MI[BERT]]


# ── 7) DSGVO ────────────────────────────────────────────────────────────────


def test_anonymisierung_entfernt_die_erwaehnungen_der_person(welt, drei, patched_db):
    from diakronos_app import dsgvo_anonymisierung as D

    antwort = _mitglieder(drei["name"], "Hallo Bert", ANNA, erwaehnt=[MI[BERT]])
    assert len(_zeilen(antwort["name"])) == 1
    s = patched_db()
    D.anonymisiere(s, MI[BERT], [BERT])
    s.commit()
    assert _zeilen(antwort["name"]) == []
    # Der Text der Nachricht bleibt (der Verlauf gehört den anderen).
    s = patched_db()
    assert s.get(ChatNachricht, antwort["name"]).text == "Hallo Bert"


# ── 8) SEC-11 / Inventar / Migration ────────────────────────────────────────


def test_senden_bleibt_post_und_ist_im_inventar_schreibend():
    from diakronos_app.api import chat as C
    from diakronos_app.frappe_compat import registry

    optionen = registry.options_for(C.senden)
    assert optionen.get("allow_guest") is False
    assert optionen.get("methods") == ("POST",)

    daten = json.loads((BACKEND / "src" / "diakronos_app" / "frappe_compat"
                        / "inventar" / "whitelist.json").read_text(encoding="utf-8"))
    eintrag = next(e for e in daten["eintraege"]
                   if e["funktion"] == "diakronos_app.api.chat.senden")
    assert eintrag["einstufung"] == "schreibend", eintrag
    assert eintrag["allow_guest"] is False


def test_inventar_hat_keine_neuen_offenen_widersprueche():
    """SEC-11: die Zahl der offenen Widersprüche darf NICHT steigen.

    Stand in ``main`` (Sammel 5): 2 (``chat.direkt_oeffnen``,
    ``kronos.google_import.get_oauth_url``). ``senden`` bleibt unverändert
    schreibend — dieser Schritt fügt KEINEN Endpunkt hinzu.
    """
    text = (BACKEND / "src" / "diakronos_app" / "frappe_compat" / "inventar"
            / "whitelist.md").read_text(encoding="utf-8")
    abschnitt = text.split("## Widersprueche", 1)[1].split("Entschieden ohne", 1)[0]
    zeilen = [z for z in abschnitt.splitlines()
              if z.startswith("| `") and "Funktion" not in z]
    assert len(zeilen) <= 2, zeilen
    assert not any("chat.senden" in z for z in zeilen), zeilen


def _skripte() -> ScriptDirectory:
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "alembic"))
    return ScriptDirectory.from_config(cfg)


def test_migration_haengt_hinter_chat7b_und_die_kette_hat_einen_kopf():
    skripte = _skripte()
    rev = skripte.get_revision("chat9a_erwaehnung")
    assert rev is not None
    assert rev.down_revision == "chat7b_runden", rev.down_revision
    assert "Revises: chat7b_runden" in Path(rev.path).read_text(encoding="utf-8")
    assert len(skripte.get_bases()) == 1
    heads = skripte.get_heads()
    # GENAU EIN Kopf — der NAME wächst weiter (CHAT-10a hängt hinter dieser
    # Revision, ``chat10a_push``). Der Test hält die STRUKTUR fest: eine Kette,
    # ein Kopf, und ``chat9a_erwaehnung`` hängt an ``chat7b_runden`` (oben).
    assert len(heads) == 1, heads
    # Keine Revision darf als Nachfolger fehlen: der Kopf muss von
    # ``chat9a_erwaehnung`` aus erreichbar sein (Kette abwärts ablaufen).
    # ``walk_revisions(base, head)`` läuft von der Wurzel zum Kopf — jede
    # Revision dazwischen steht in der Menge.
    erreichbar = {rev.revision for rev in skripte.walk_revisions()}
    assert "chat9a_erwaehnung" in erreichbar, heads
    # Und der Kopf liegt NACH dieser Revision (sonst wäre sie abgehängt).
    # Review CHAT-10a R1/9: NICHT ``down_revision is not None`` prüfen — das
    # gilt auch für eine Revision, die neben der Kette steht. Geprüft wird,
    # dass ``chat9a_erwaehnung`` in der Kette LIEGT, die beim Kopf beginnt:
    # ``iterate_revisions(head, 'base')`` läuft abwärts und muss sie treffen.
    kette = {r.revision for r in skripte.iterate_revisions(heads[0], "base")}
    assert "chat9a_erwaehnung" in kette, heads


@pytest.fixture()
def fresh_engine():
    """Leere SQLite-Engine nur mit dem Gerüst für die Fremdschlüssel."""
    from sqlalchemy import create_engine
    from sqlalchemy.pool import StaticPool

    from diakronos_app.models.base import Base

    eng = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(eng)
    with eng.begin() as verbindung:
        verbindung.exec_driver_sql('DROP TABLE IF EXISTS "chat_erwaehnung"')
    yield eng
    eng.dispose()


def test_migration_upgrade_downgrade_upgrade(fresh_engine):
    import importlib.util

    from sqlalchemy import inspect

    pfad = BACKEND / "alembic" / "versions" / "chat9a_erwaehnung.py"
    modul = importlib.util.module_from_spec(
        importlib.util.spec_from_file_location("chat9a_erwaehnung", pfad))
    modul.__spec__.loader.exec_module(modul)

    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    with fresh_engine.begin() as verbindung:
        with Operations.context(MigrationContext.configure(verbindung)):
            modul.upgrade()
        insp = inspect(verbindung)
        assert insp.has_table("chat_erwaehnung")
        spalten = {c["name"] for c in insp.get_columns("chat_erwaehnung")}
        assert {"nachricht", "mitglied", "angelegt_am"} <= spalten
        assert insp.get_pk_constraint("chat_erwaehnung")["constrained_columns"] == \
            ["nachricht", "mitglied"]
        namen = {i["name"] for i in insp.get_indexes("chat_erwaehnung")}
        assert "ix_chat_erwaehnung_nachricht" in namen
        assert "ix_chat_erwaehnung_mitglied" in namen
        ziele = {(fk["constrained_columns"][0], fk["referred_table"])
                 for fk in insp.get_foreign_keys("chat_erwaehnung")}
        assert ("nachricht", "chat_nachricht") in ziele
        nachricht_fk = next(fk for fk in insp.get_foreign_keys("chat_erwaehnung")
                            if fk["constrained_columns"] == ["nachricht"])
        assert nachricht_fk["options"].get("ondelete", "").upper() == "CASCADE"

    # downgrade → weg, zweiter upgrade → wieder da (kein Rest, der stört).
    with fresh_engine.begin() as verbindung:
        with Operations.context(MigrationContext.configure(verbindung)):
            modul.downgrade()
        assert not inspect(verbindung).has_table("chat_erwaehnung")
    with fresh_engine.begin() as verbindung:
        with Operations.context(MigrationContext.configure(verbindung)):
            modul.upgrade()
            modul.upgrade()  # idempotent
        assert inspect(verbindung).has_table("chat_erwaehnung")


def test_downgrade_ist_laut_wenn_erwaehnungen_existieren(fresh_engine):
    """Eine stille Datenvernichtung gibt es nicht."""
    import importlib.util

    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    pfad = BACKEND / "alembic" / "versions" / "chat9a_erwaehnung.py"
    modul = importlib.util.module_from_spec(
        importlib.util.spec_from_file_location("chat9a_erwaehnung", pfad))
    modul.__spec__.loader.exec_module(modul)
    with fresh_engine.begin() as verbindung:
        with Operations.context(MigrationContext.configure(verbindung)):
            modul.upgrade()
            verbindung.exec_driver_sql(
                "INSERT INTO chat_erwaehnung (nachricht, mitglied, angelegt_am) "
                "VALUES ('n1', 'm1', '2026-11-20 10:00:00')")
            with pytest.raises(RuntimeError):
                modul.downgrade()
            # Und die Tabelle steht noch (nichts halb abgebaut).
            from sqlalchemy import inspect

            assert inspect(verbindung).has_table("chat_erwaehnung")
