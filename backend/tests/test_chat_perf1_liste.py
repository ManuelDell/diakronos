"""CHAT-PERF-1: Gesprächsliste ohne Abfragen je Gespräch (Backend).

Geprüft wird gegen die ECHTEN Endpunkte (``api.chat``), den ECHTEN
Rechte-Kern (``rechte/kern.py``) und die ECHTE Datenbank — keine Attrappe:

  * FESTGEHALTENE ANTWORT: eine gemischte Welt (Gruppen, Untergruppen, 1:1,
    Runden, stumm, gelöscht, Vorschlagszeilen, Runde mit ``sichtbar_ab``,
    ungelesen 0/1/viele, ein noch nie geöffnetes Gespräch) wird VOR dem
    Umbau als Wortlaut abgelegt. Nach dem Umbau muss dieselbe Antwort
    herauskommen — Feld für Feld, Reihenfolge für Reihenfolge.
  * Dieselbe Antwort für JEDEN der drei Aufrufwege: ``meine_gespraeche``,
    ``direkt_oeffnen`` und ``runde_anlegen`` (alle drei bauen ihren Kopf in
    ``_gespraech_kopf``).
  * SQL-Zählung: die Zahl der Abfragen hängt NICHT an der Zahl der Gespräche.
    30 Gespräche ≤ 25 Abfragen, 60 Gespräche ebenso viele wie 30.

Aufruf (Karte):
    docker run --rm --network none --entrypoint python -v <wt>:/repo:ro \\
      -w /repo/backend -e PYTHONPATH=/repo/backend/src:/repo/backend/tests:/repo/tools \\
      -e PYTHONDONTWRITEBYTECODE=1 <vorbau> -m pytest -q -p no:cacheprovider \\
      tests/test_chat_perf1_liste.py
"""

from __future__ import annotations

import importlib
import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from diakronos_app.models.chat import (
    ART_DIREKT,
    ART_GRUPPE,
    ART_RUNDE,
    ART_UNTERGRUPPE,
    ChatGespraech,
    ChatNachricht,
    ChatRundeVorschlag,
    ChatTeilnehmer,
    VORSCHLAG_BEENDET,
    VORSCHLAG_OFFEN,
)
from diakronos_app.models.diakonos import (
    Gruppe,
    Gruppenmitgliedschaft,
    Mitglied,
    Untergruppe,
    Untergruppenmitgliedschaft,
)
from diakronos_app.models.rechte import RechteModul

#: Die Test-Naht liegt im MODUL ``frappe_compat.session`` (wie ``test_chat2_api``).
_session_mod = importlib.import_module("diakronos_app.frappe_compat.session")

BACKEND = Path(__file__).resolve().parents[1]

#: Dieselbe Personenwelt wie ``test_chat7b_runden`` (Konten, Mitglieder, HV,
#: Administrator) — Fixture und Kennungen werden geteilt, nicht nachgebaut.
from test_chat7b_runden import (  # noqa: E402,F401
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


# ── Hilfen ──────────────────────────────────────────────────────────────────


def _jetzt() -> datetime:
    return datetime(2026, 11, 20, 12, 0, 0)


def _kennung(priefix: str, i: int) -> str:
    return f"{priefix}-{i:03d}"


def _gruppe(s, name: str, *, mitglieder=()) -> None:
    s.add(Gruppe(name=name))
    for konto in mitglieder:
        s.add(Gruppenmitgliedschaft(
            name=f"gm-{name}-{MI[konto]}", parent=name, parenttype="Gruppe",
            parentfield="mitglieder", mitglied=MI[konto]))
    s.add(RechteModul(gruppe=name, modul="chat"))


def _liste(konto: str = ANNA) -> dict:
    from diakronos_app.api import chat as C

    _set_user(konto)
    return C.meine_gespraeche()


def _json(wert) -> str:
    """Antwort als Text — Reihenfolge und Felder bleiben, ``None`` bleibt ``None``."""
    return json.dumps(wert, ensure_ascii=False, indent=1, sort_keys=False)


def _zaehle_abfragen(engine):
    """Zählt die SQL-Anweisungen einer Aktion (SQLAlchemy-``before_cursor_execute``)."""
    from sqlalchemy import event

    gezaehlt: list[str] = []

    def _mit(conn, cursor, statement, parameters, context, executemany):
        gezaehlt.append(statement)

    event.listen(engine, "before_cursor_execute", _mit)
    return gezaehlt, lambda: event.remove(engine, "before_cursor_execute", _mit)


# ── Die gemischte Welt ──────────────────────────────────────────────────────


@pytest.fixture()
def gemischt(welt, patched_db):
    """Die Welt, deren LISTE unten als Wortlaut festgehalten ist.

    Alles wird DIREKT in die Datenbank geschrieben (kein Endpunkt, keine
    Uhr): die Zeiten sind fest, damit die Antwort reproduzierbar ist.
    """
    s = patched_db()
    t0 = _jetzt()

    # 1) Gruppe „Chor“ (Anna, Bert) mit Gespräch, zwei Nachrichten von Bert,
    #    Anna hat keine gelesen → ungelesen 2.
    _gruppe(s, "Chor", mitglieder=[ANNA, BERT])
    g1 = ChatGespraech(name=_kennung("chat-g", 1), art=ART_GRUPPE, gruppe="Chor",
                       angelegt_am=t0)
    s.add(g1)
    for i, (konto, text) in enumerate([(BERT, "Erste Zeile"), (BERT, "Zweite Zeile")]):
        s.add(ChatNachricht(
            name=_kennung("chat-n", i + 1), gespraech=g1.name, autor=MI[konto],
            autor_benutzer=konto, text=text,
            erstellt_am=t0 + timedelta(minutes=10 + i)))
    s.add(ChatTeilnehmer(gespraech=g1.name, benutzer=ANNA, stumm=False,
                         hinzugefuegt_am=t0))
    s.add(ChatTeilnehmer(gespraech=g1.name, benutzer=BERT, stumm=False,
                         hinzugefuegt_am=t0,
                         letzter_lesestand=t0 + timedelta(minutes=11),
                         letzter_lesestand_nachricht=_kennung("chat-n", 2)))

    # 2) Gruppe „Technik“ NUR mit Anna, Gespräch noch NICHT angelegt →
    #    `geoeffnet: false`, `name: null`, ungelesen 0.
    _gruppe(s, "Technik", mitglieder=[ANNA])

    # 3) Gruppe „Musik“ (Anna, Clara) mit Untergruppe „Musik/Bläser“ (Anna):
    #    Anna ist Mitglied der Untergruppe → liest BEIDE (Untergruppe erbt die
    #    Hauptgruppe), ungelesen in der Untergruppe 1, alles stumm geschaltet.
    _gruppe(s, "Musik", mitglieder=[ANNA, CLARA])
    s.add(Untergruppe(name="Musik-Blaeser", gruppe="Musik",
                      untergruppenname="Bläser"))
    s.add(Untergruppenmitgliedschaft(
        name="ugm-1", parent="Musik-Blaeser", parenttype="Untergruppe",
        parentfield="mitglieder", mitglied=MI[ANNA]))
    g3 = ChatGespraech(name=_kennung("chat-g", 3), art=ART_GRUPPE, gruppe="Musik",
                       angelegt_am=t0)
    g3u = ChatGespraech(name=_kennung("chat-g", 4), art=ART_UNTERGRUPPE,
                        gruppe="Musik", untergruppe="Musik-Blaeser",
                        angelegt_am=t0)
    s.add_all([g3, g3u])
    s.add(ChatTeilnehmer(gespraech=g3.name, benutzer=ANNA, stumm=True,
                         hinzugefuegt_am=t0))
    s.add(ChatTeilnehmer(gespraech=g3u.name, benutzer=ANNA, stumm=False,
                         hinzugefuegt_am=t0))
    s.add(ChatNachricht(
        name=_kennung("chat-n", 10), gespraech=g3u.name, autor=MI[CLARA],
        autor_benutzer=CLARA, text="Bläser: Probe am Freitag",
        erstellt_am=t0 + timedelta(minutes=30)))

    # 3b) Gruppe „Lesestand“ (Anna, Clara): drei fremde Nachrichten, Anna hat
    #     die ersten ZWEI gelesen (`letzter_lesestand` + Kennung) → ungelesen
    #     1. Die Kennung entscheidet bei gleichem Zeitstempel — die dritte
    #     Nachricht traegt exakt den Zeitstempel des Lesestands.
    _gruppe(s, "Lesestand", mitglieder=[ANNA, CLARA])
    g3b = ChatGespraech(name=_kennung("chat-g", 6), art=ART_GRUPPE,
                        gruppe="Lesestand", angelegt_am=t0)
    s.add(g3b)
    for i, text in enumerate(["eins", "zwei", "drei"]):
        s.add(ChatNachricht(
            name=f"ls-n-{i}", gespraech=g3b.name, autor=MI[CLARA],
            autor_benutzer=CLARA, text=text,
            erstellt_am=t0 + timedelta(minutes=20)))
    s.add(ChatTeilnehmer(gespraech=g3b.name, benutzer=ANNA, stumm=False,
                         hinzugefuegt_am=t0,
                         letzter_lesestand=t0 + timedelta(minutes=20),
                         letzter_lesestand_nachricht="ls-n-1"))
    # 3c) Gruppe „Beitritt“ (Anna, Clara): Anna ist erst spaeter beigetreten,
    #     hat nie gelesen → nur die Nachricht NACH dem Beitritt zaehlt.
    _gruppe(s, "Beitritt", mitglieder=[ANNA, CLARA])
    g3c = ChatGespraech(name=_kennung("chat-g", 7), art=ART_GRUPPE,
                        gruppe="Beitritt", angelegt_am=t0)
    s.add(g3c)
    s.add(ChatNachricht(
        name=_kennung("chat-n", 70), gespraech=g3c.name, autor=MI[CLARA],
        autor_benutzer=CLARA, text="vor dem Beitritt",
        erstellt_am=t0 + timedelta(minutes=5)))
    s.add(ChatNachricht(
        name=_kennung("chat-n", 71), gespraech=g3c.name, autor=MI[CLARA],
        autor_benutzer=CLARA, text="nach dem Beitritt",
        erstellt_am=t0 + timedelta(minutes=25)))
    s.add(ChatTeilnehmer(gespraech=g3c.name, benutzer=ANNA, stumm=False,
                         hinzugefuegt_am=t0 + timedelta(minutes=10)))

    # 4) Gruppe „Archiv“ (nur Anna) mit GELÖSCHTEM Gespräch: die EINHEIT ist
    #    lesbar, das Gespräch ist stillgelegt — sie steht deshalb MIT in der
    #    Liste, aber ohne Kennung (``geoeffnet: false``). Das ist der heutige
    #    Stand; der Test hält ihn fest.
    _gruppe(s, "Archiv", mitglieder=[ANNA])
    s.add(ChatGespraech(name=_kennung("chat-g", 5), art=ART_GRUPPE,
                        gruppe="Archiv", angelegt_am=t0,
                        geloescht_am=t0 + timedelta(days=1)))

    # 5) Gruppe „OhneModul“ (nur Anna), Modul `chat` NICHT an → kein Eintrag.
    s.add(Gruppe(name="OhneModul"))
    s.add(Gruppenmitgliedschaft(name="gm-om", parent="OhneModul",
                                parenttype="Gruppe", parentfield="mitglieder",
                                mitglied=MI[ANNA]))

    # 6) 1:1 Anna ↔ Bert: Bert schreibt, Anna liest nichts → ungelesen 1.
    direkt = ChatGespraech(name=_kennung("chat-d", 1), art=ART_DIREKT,
                           paar_schluessel="\x1f".join(sorted([ANNA, BERT])),
                           angelegt_am=t0)
    s.add(direkt)
    s.add_all([
        ChatTeilnehmer(gespraech=direkt.name, benutzer=ANNA, stumm=False,
                       hinzugefuegt_am=t0),
        ChatTeilnehmer(gespraech=direkt.name, benutzer=BERT, stumm=False,
                       hinzugefuegt_am=t0),
    ])
    s.add(ChatNachricht(
        name=_kennung("chat-n", 20), gespraech=direkt.name, autor=MI[BERT],
        autor_benutzer=BERT, text="Hallo Anna, hast du kurz Zeit?",
        erstellt_am=t0 + timedelta(minutes=40)))

    # 7) 1:1 Anna ↔ Clara mit GELÖSCHTER letzter Nachricht: die Vorschau ist
    #    der Text der gelöschten Nachricht NICHT (``_zitat`` → None), der
    #    Zeitstempel bleibt.
    d2 = ChatGespraech(name=_kennung("chat-d", 2), art=ART_DIREKT,
                       paar_schluessel="\x1f".join(sorted([ANNA, CLARA])),
                       angelegt_am=t0)
    s.add(d2)
    s.add_all([
        ChatTeilnehmer(gespraech=d2.name, benutzer=ANNA, stumm=False,
                       hinzugefuegt_am=t0),
        ChatTeilnehmer(gespraech=d2.name, benutzer=CLARA, stumm=False,
                       hinzugefuegt_am=t0),
    ])
    s.add(ChatNachricht(
        name=_kennung("chat-n", 30), gespraech=d2.name, autor=MI[CLARA],
        autor_benutzer=CLARA, text="Das war ein Fehler",
        erstellt_am=t0 + timedelta(minutes=50),
        geloescht_am=t0 + timedelta(minutes=55)))

    # 8) Runde „Wanderung“ (Anna, Bert, Dieter) mit einem OFFENEN Vorschlag
    #    für Frida: die Vorschlags-Systemzeile ist für Anna ungelesen (sie hat
    #    nicht vorgeschlagen); Fritzens Vorschlag wird ausserdem als
    #    LETZTE Nachricht verdrängt — die Vorschlagszeile ist NIE die Vorschau.
    r1 = ChatGespraech(name=_kennung("chat-r", 1), art=ART_RUNDE, titel="Wanderung",
                       angelegt_am=t0)
    s.add(r1)
    for konto in (ANNA, BERT, DIETER):
        s.add(ChatTeilnehmer(gespraech=r1.name, benutzer=konto, stumm=False,
                             hinzugefuegt_am=t0, sichtbar_ab=t0))
    s.add(ChatRundeVorschlag(
        name=_kennung("chat-v", 1), gespraech=r1.name, mitglied=MI[FRIDA],
        vorgeschlagen_von=BERT, angelegt_am=t0 + timedelta(minutes=60),
        stand=VORSCHLAG_OFFEN, zustimmende=json.dumps([ANNA])))
    s.add(ChatNachricht(
        name=_kennung("chat-n", 40), gespraech=r1.name, autor=MI[DIETER],
        autor_benutzer=DIETER, text="Treffpunkt ist der Bahnhof",
        erstellt_am=t0 + timedelta(minutes=70)))
    s.add(ChatNachricht(
        name=_kennung("chat-n", 41), gespraech=r1.name, autor=None,
        autor_benutzer=None, vorschlag=_kennung("chat-v", 1), text="",
        erstellt_am=t0 + timedelta(minutes=80)))

    # 9) Runde „Neu“ mit SICHTBAR_AB in der Zukunft: die Nachricht von vor dem
    #    Eintritt ist weder Vorschau noch ungelesen (0) — und der Vorschlag
    #    „beendet“ steht als Systemzeile, aber nicht als Vorschau.
    r2 = ChatGespraech(name=_kennung("chat-r", 2), art=ART_RUNDE, titel="Neu",
                       angelegt_am=t0)
    s.add(r2)
    s.add_all([
        ChatTeilnehmer(gespraech=r2.name, benutzer=BERT, stumm=False,
                       hinzugefuegt_am=t0, sichtbar_ab=t0),
        ChatTeilnehmer(gespraech=r2.name, benutzer=ANNA, stumm=False,
                       hinzugefuegt_am=t0 + timedelta(hours=5),
                       sichtbar_ab=t0 + timedelta(hours=5)),
    ])
    s.add(ChatRundeVorschlag(
        name=_kennung("chat-v", 2), gespraech=r2.name, mitglied=MI[CLARA],
        vorgeschlagen_von=BERT, angelegt_am=t0 + timedelta(minutes=90),
        stand=VORSCHLAG_BEENDET, entschieden_am=t0 + timedelta(minutes=95)))
    s.add(ChatNachricht(
        name=_kennung("chat-n", 50), gespraech=r2.name, autor=MI[BERT],
        autor_benutzer=BERT, text="Vor deinem Eintritt",
        erstellt_am=t0 + timedelta(minutes=100)))
    s.add(ChatNachricht(
        name=_kennung("chat-n", 51), gespraech=r2.name, autor=None,
        autor_benutzer=None, vorschlag=_kennung("chat-v", 2), text="",
        erstellt_am=t0 + timedelta(minutes=110)))

    # 10) Runde „Ausgetreten“: Anna ist gegangen → nicht in der Liste.
    r3 = ChatGespraech(name=_kennung("chat-r", 3), art=ART_RUNDE, titel="Ausgetreten",
                       angelegt_am=t0)
    s.add(r3)
    s.add_all([
        ChatTeilnehmer(gespraech=r3.name, benutzer=ANNA, stumm=False,
                       hinzugefuegt_am=t0, sichtbar_ab=t0,
                       verlassen_am=t0 + timedelta(hours=1)),
        ChatTeilnehmer(gespraech=r3.name, benutzer=BERT, stumm=False,
                       hinzugefuegt_am=t0, sichtbar_ab=t0),
    ])

    # 11) Fremdes 1:1 (Bert ↔ Clara) und fremde Gruppe („Fremd“, nur Bert):
    #     tauchen bei Anna NICHT auf.
    _gruppe(s, "Fremd", mitglieder=[BERT])
    g11 = ChatGespraech(name=_kennung("chat-g", 11), art=ART_GRUPPE,
                        gruppe="Fremd", angelegt_am=t0)
    fremd_d = ChatGespraech(name=_kennung("chat-d", 11), art=ART_DIREKT,
                            paar_schluessel="\x1f".join(sorted([BERT, CLARA])),
                            angelegt_am=t0)
    s.add_all([g11, fremd_d])
    s.add_all([
        ChatTeilnehmer(gespraech=fremd_d.name, benutzer=BERT, stumm=False,
                       hinzugefuegt_am=t0),
        ChatTeilnehmer(gespraech=fremd_d.name, benutzer=CLARA, stumm=False,
                       hinzugefuegt_am=t0),
    ])
    s.add(ChatNachricht(
        name=_kennung("chat-n", 60), gespraech=fremd_d.name, autor=MI[BERT],
        autor_benutzer=BERT, text="Nur für Clara",
        erstellt_am=t0 + timedelta(minutes=120)))

    s.commit()
    yield s
    s.rollback()


# ── 1) Die Antwort steht fest ───────────────────────────────────────────────


def test_antwort_ist_festgehalten(gemischt, welt):
    """Die Liste der gemischten Welt — Feld für Feld, in IHRER Reihenfolge.

    Der Wortlaut unten ist der Stand VOR dem Umbau (CHAT-PERF-1). Er ist der
    Maßstab: was danach anders aussieht, ist ein Fehler und kein Fortschritt.
    Geprüft wird bewusst der GANZE Text (nicht einzelne Felder): eine
    zusätzliche oder fehlende Zeile, ein ``null`` statt ``""`` oder eine
    andere Sortierung fällt damit auf.
    """
    from diakronos_app import rechte as R

    R.merker_leeren()
    with R.merkungsrahmen():
        antwort = _liste(ANNA)

    titel = [e["titel"] for e in antwort["gespraeche"]]
    # Sortierung: ``letzte_am`` absteigend, dann Titel. „Neu“ steht HINTEN:
    # seine letzte sichtbare Nachricht liegt hinter ``sichtbar_ab``, also gibt
    # es keine Vorschau und es zählt der leere Zeitstempel.
    assert titel == ["Wanderung", "Clara C.", "Bert B.", "Musik-Blaeser",
                     "Beitritt", "Lesestand", "Chor", "Technik", "Neu",
                     "Musik", "Archiv"], titel

    # Die Zahlen: 0 / 1 / viele — je Gesprächsart.
    nach_titel = {e["titel"]: e for e in antwort["gespraeche"]}
    assert nach_titel["Chor"]["ungelesen"] == 2          # viele
    assert nach_titel["Musik-Blaeser"]["ungelesen"] == 1  # eine
    assert nach_titel["Musik"]["ungelesen"] == 0
    assert nach_titel["Bert B."]["ungelesen"] == 1       # 1:1
    assert nach_titel["Clara C."]["ungelesen"] == 0      # letzte gelöscht
    assert nach_titel["Technik"]["ungelesen"] == 0       # nie geöffnet
    assert nach_titel["Technik"]["geoeffnet"] is False
    assert nach_titel["Technik"]["name"] is None
    assert nach_titel["Chor"]["stumm"] is False
    assert nach_titel["Musik"]["stumm"] is True
    assert nach_titel["Musik"]["darf_senden"] is True
    assert nach_titel["Musik-Blaeser"]["art"] == ART_UNTERGRUPPE
    assert nach_titel["Bert B."]["art"] == ART_DIREKT
    assert nach_titel["Bert B."]["mitglied"] == MI[BERT]
    # Lesestand: die ersten zwei sind gelesen, die dritte traegt denselben
    # Zeitstempel und entscheidet ueber die Kennung → genau 1 ungelesen.
    assert nach_titel["Lesestand"]["ungelesen"] == 1
    assert nach_titel["Lesestand"]["letzte_nachricht"] == "drei"
    # Beitritt: nur die Nachricht NACH dem Beitritt zaehlt.
    assert nach_titel["Beitritt"]["ungelesen"] == 1
    assert nach_titel["Beitritt"]["letzte_nachricht"] == "nach dem Beitritt"
    assert nach_titel["Neu"]["art"] == ART_RUNDE
    # Zwei aktive Beteiligte: Bert (Eintritt zuerst) und Anna (sieht ihre
    # eigene Runde, die Nachricht von Bert liegt hinter ihrem Eintritt).
    assert nach_titel["Neu"]["mitglieder"] == [
        {"mitglied": MI[BERT], "anzeigename": "Bert Brandner"},
        {"mitglied": MI[ANNA], "anzeigename": "Anna Beispiel"}]
    # Die Vorschlagszeile ist NIE die Vorschau: in der Runde ist die letzte
    # Nachricht die Systemzeile, gezeigt wird der echte Beitrag davor.
    assert nach_titel["Wanderung"]["letzte_nachricht"] == "Treffpunkt ist der Bahnhof"
    assert nach_titel["Wanderung"]["ungelesen"] == 2  # Beitrag + Systemzeile
    assert nach_titel["Neu"]["letzte_nachricht"] is None
    assert nach_titel["Neu"]["ungelesen"] == 0
    # Gelöschte letzte Nachricht: Vorschau None, Zeitstempel da.
    assert nach_titel["Clara C."]["letzte_nachricht"] is None
    assert nach_titel["Clara C."]["letzte_am"] is not None
    # Gelöschtes Gespräch, ausgetretene Runde, fremde Gespräche: NICHT dabei.
    # „Archiv“ steht dagegen MIT in der Liste — so ist das heutige Verhalten
    # (die Einheit ist lesbar, nur das Gespräch ist stillgelegt:
    # ``geoeffnet: false``, Namen ``null``). Der Test hält es FEST, er ändert
    # es nicht — CHAT-PERF-1 darf die Antwort nicht umbauen.
    for fern in ("Ausgetreten", "Fremd"):
        assert fern not in nach_titel, sorted(nach_titel)
    assert nach_titel["Archiv"]["geoeffnet"] is False
    assert nach_titel["Archiv"]["name"] is None
    assert len(antwort["gespraeche"]) == 11, titel

    # Und jetzt der Wortlaut selbst: EIN Vergleich über die ganze Antwort.
    assert _json(antwort) == _FESTGEHALTEN


#: Der Wortlaut der Antwort (Stand VOR dem Umbau CHAT-PERF-1, gemessen im
#: vorbau-Image). Bewusst als Text: nur so fallen neue Felder, ``null`` statt
#: ``""`` und vertauschte Zeilen auf.
_FESTGEHALTEN = """\
{
 "gespraeche": [
  {
   "name": "chat-r-001",
   "art": "runde",
   "gruppe": null,
   "untergruppe": null,
   "titel": "Wanderung",
   "mitglied": null,
   "bild": "",
   "teilnehmer": 3,
   "stumm": false,
   "geoeffnet": true,
   "ungelesen": 2,
   "letzte_nachricht": "Treffpunkt ist der Bahnhof",
   "letzte_am": "2026-11-20T13:10:00",
   "darf_senden": true,
   "mitglieder": [
    {
     "mitglied": "M-00-Anna",
     "anzeigename": "Anna Beispiel"
    },
    {
     "mitglied": "M-01-Bert",
     "anzeigename": "Bert Brandner"
    },
    {
     "mitglied": "M-03-Dieter",
     "anzeigename": "Dieter Dorn"
    }
   ]
  },
  {
   "name": "chat-d-002",
   "art": "direkt",
   "gruppe": null,
   "untergruppe": null,
   "titel": "Clara C.",
   "mitglied": "M-02-Clara",
   "bild": "",
   "teilnehmer": 2,
   "stumm": false,
   "geoeffnet": true,
   "ungelesen": 0,
   "letzte_nachricht": null,
   "letzte_am": "2026-11-20T12:50:00",
   "darf_senden": true
  },
  {
   "name": "chat-d-001",
   "art": "direkt",
   "gruppe": null,
   "untergruppe": null,
   "titel": "Bert B.",
   "mitglied": "M-01-Bert",
   "bild": "",
   "teilnehmer": 2,
   "stumm": false,
   "geoeffnet": true,
   "ungelesen": 1,
   "letzte_nachricht": "Hallo Anna, hast du kurz Zeit?",
   "letzte_am": "2026-11-20T12:40:00",
   "darf_senden": true
  },
  {
   "name": "chat-g-004",
   "art": "untergruppe",
   "gruppe": "Musik",
   "untergruppe": "Musik-Blaeser",
   "titel": "Musik-Blaeser",
   "mitglied": null,
   "bild": "",
   "teilnehmer": 1,
   "stumm": false,
   "geoeffnet": true,
   "ungelesen": 1,
   "letzte_nachricht": "Bläser: Probe am Freitag",
   "letzte_am": "2026-11-20T12:30:00",
   "darf_senden": true
  },
  {
   "name": "chat-g-007",
   "art": "gruppe",
   "gruppe": "Beitritt",
   "untergruppe": null,
   "titel": "Beitritt",
   "mitglied": null,
   "bild": "",
   "teilnehmer": 1,
   "stumm": false,
   "geoeffnet": true,
   "ungelesen": 1,
   "letzte_nachricht": "nach dem Beitritt",
   "letzte_am": "2026-11-20T12:25:00",
   "darf_senden": true
  },
  {
   "name": "chat-g-006",
   "art": "gruppe",
   "gruppe": "Lesestand",
   "untergruppe": null,
   "titel": "Lesestand",
   "mitglied": null,
   "bild": "",
   "teilnehmer": 1,
   "stumm": false,
   "geoeffnet": true,
   "ungelesen": 1,
   "letzte_nachricht": "drei",
   "letzte_am": "2026-11-20T12:20:00",
   "darf_senden": true
  },
  {
   "name": "chat-g-001",
   "art": "gruppe",
   "gruppe": "Chor",
   "untergruppe": null,
   "titel": "Chor",
   "mitglied": null,
   "bild": "",
   "teilnehmer": 2,
   "stumm": false,
   "geoeffnet": true,
   "ungelesen": 2,
   "letzte_nachricht": "Zweite Zeile",
   "letzte_am": "2026-11-20T12:11:00",
   "darf_senden": true
  },
  {
   "name": null,
   "art": "gruppe",
   "gruppe": "Technik",
   "untergruppe": null,
   "titel": "Technik",
   "mitglied": null,
   "bild": "",
   "teilnehmer": 0,
   "stumm": false,
   "geoeffnet": false,
   "ungelesen": 0,
   "letzte_nachricht": null,
   "letzte_am": null,
   "darf_senden": true
  },
  {
   "name": "chat-r-002",
   "art": "runde",
   "gruppe": null,
   "untergruppe": null,
   "titel": "Neu",
   "mitglied": null,
   "bild": "",
   "teilnehmer": 2,
   "stumm": false,
   "geoeffnet": true,
   "ungelesen": 0,
   "letzte_nachricht": null,
   "letzte_am": null,
   "darf_senden": true,
   "mitglieder": [
    {
     "mitglied": "M-01-Bert",
     "anzeigename": "Bert Brandner"
    },
    {
     "mitglied": "M-00-Anna",
     "anzeigename": "Anna Beispiel"
    }
   ]
  },
  {
   "name": "chat-g-003",
   "art": "gruppe",
   "gruppe": "Musik",
   "untergruppe": null,
   "titel": "Musik",
   "mitglied": null,
   "bild": "",
   "teilnehmer": 1,
   "stumm": true,
   "geoeffnet": true,
   "ungelesen": 0,
   "letzte_nachricht": null,
   "letzte_am": null,
   "darf_senden": true
  },
  {
   "name": null,
   "art": "gruppe",
   "gruppe": "Archiv",
   "untergruppe": null,
   "titel": "Archiv",
   "mitglied": null,
   "bild": "",
   "teilnehmer": 0,
   "stumm": false,
   "geoeffnet": false,
   "ungelesen": 0,
   "letzte_nachricht": null,
   "letzte_am": null,
   "darf_senden": true
  }
 ]
}"""


def test_alle_drei_wege_liefern_denselben_kopf(gemischt, welt):
    """``meine_gespraeche``, ``direkt_oeffnen`` und ``runde_anlegen``: EINE Form.

    Alle drei bauen ihren Kopf in ``_gespraech_kopf`` — nach dem Umbau müssen
    sie dieselben Felder mit denselben Werten liefern. Geprüft wird der
    Vergleich der Schlüssel und der gemeinsamen Werte (die Liste sortiert, der
    Einzelaufruf nicht).
    """
    from diakronos_app import rechte as R
    from diakronos_app.api import chat as C

    R.merker_leeren()
    with R.merkungsrahmen():
        liste = {e["name"]: e for e in _liste(ANNA)["gespraeche"]}

    R.merker_leeren()
    _set_user(ANNA)
    with R.merkungsrahmen():
        direkt = C.direkt_oeffnen(mitglied=MI[BERT])
    assert direkt["name"] == _kennung("chat-d", 1)
    assert set(direkt) == set(liste[direkt["name"]]), sorted(direkt)
    for feld in ("art", "titel", "ungelesen", "stumm", "mitglied", "bild",
                 "teilnehmer", "letzte_nachricht", "letzte_am", "darf_senden"):
        assert direkt[feld] == liste[direkt["name"]][feld], feld

    R.merker_leeren()
    _set_user(ANNA)
    with R.merkungsrahmen():
        neu = C.runde_anlegen("Probe", [MI[CLARA], MI[DIETER]])
    # ``runde_anlegen`` antwortet mit ``_runde_kopf`` (eine ANDERE, schlankere
    # Form: ``erstellt_am`` statt ``letzte_am``/``bild``/…). Sie muss aber
    # inhaltlich dasselbe sagen wie der Eintrag in der Liste.
    assert neu["art"] == ART_RUNDE
    assert neu["titel"] == "Probe"
    mitglieder = {m["mitglied"] for m in neu["mitglieder"]}
    assert mitglieder == {MI[ANNA], MI[CLARA], MI[DIETER]}

    R.merker_leeren()
    with R.merkungsrahmen():
        nachher = {e["name"]: e for e in _liste(ANNA)["gespraeche"]}
    assert neu["name"] in nachher
    eintrag = nachher[neu["name"]]
    for feld in ("name", "art", "titel", "teilnehmer", "stumm", "ungelesen",
                 "mitglieder"):
        assert eintrag[feld] == neu[feld], feld


# ── 2) Die Zahl der Abfragen wächst nicht ───────────────────────────────────


def _viele_gruppen(s, praefix: str, anzahl: int) -> None:
    """``anzahl`` Gruppen mit Anna als Mitglied, Modul an — und ein Gespräch mit
    einer fremden Nachricht: je Gruppe eine Zeile in der Liste, ungelesen 1."""
    t0 = _jetzt()
    for i in range(anzahl):
        gruppe = f"{praefix}-{i:03d}"
        _gruppe(s, gruppe, mitglieder=[ANNA])
        g = ChatGespraech(name=_kennung(f"chat-w{i}", 0), art=ART_GRUPPE,
                          gruppe=gruppe, angelegt_am=t0)
        s.add(g)
        s.add(ChatTeilnehmer(gespraech=g.name, benutzer=ANNA, stumm=False,
                             hinzugefuegt_am=t0))
        s.add(ChatNachricht(
            name=_kennung(f"chat-x{i}", 0), gespraech=g.name, autor=MI[BERT],
            autor_benutzer=BERT, text=f"Zeile {i}",
            erstellt_am=t0 + timedelta(minutes=i + 1)))
    s.commit()


def _messen(engine) -> tuple[int, int]:
    """(Abfragen für die Liste, Zeilen in der Antwort) — mit Merkungsrahmen."""
    from diakronos_app import rechte as R

    R.merker_leeren()
    abfragen, stoppen = _zaehle_abfragen(engine)
    try:
        _set_user(ANNA)
        with R.merkungsrahmen():
            antwort = _liste(ANNA)
    finally:
        stoppen()
    return len(abfragen), len(antwort["gespraeche"])


def test_sql_zaehlung_bei_30_gespraechen(welt, engine, patched_db):
    """Höchstens 25 Abfragen bei 30 Gesprächen — gemessen wie im echten Request.

    Gezählt wird mit ``before_cursor_execute`` und MIT ``merkungsrahmen``
    (derselbe Rahmen wie ``test_chat11a_suche.py::test_sql_zaehlung_bei_30_gespraechen``):
    ohne Rahmen würde der Merker des Rechte-Kerns jede Messung verfälschen.
    Die vier Fragen je Gespräch (Teilnahmezeile, Ungelesen-Zähler, letzte
    Nachricht, Teilnehmerliste) sind in Sammelabfragen übergegangen — die
    Grenze liegt knapp über dem Ist-Stand (11) und schlägt an, sobald jemand
    eine davon wieder in eine Schleife verwandelt.
    """
    _viele_gruppen(patched_db(), "Welt30", 30)
    anzahl, zeilen = _messen(engine)
    assert zeilen == 30
    assert anzahl <= 25, f"{anzahl} Abfragen bei 30 Gesprächen"


def test_zahl_waechst_nicht_mit_60_gespraechen(welt, engine, patched_db):
    """60 Gespräche kosten nicht mehr als 30 — die Zahl hängt nicht an der Liste."""
    _viele_gruppen(patched_db(), "Welt60", 60)
    sechzig, zeilen_sechzig = _messen(engine)
    assert zeilen_sechzig == 60
    assert sechzig <= 25, f"{sechzig} Abfragen bei 60 Gesprächen"

    # Gegenprobe im selben Bestand: die 60 Zeilen der Liste wieder weg, dann
    # 30 — die Zahl der Abfragen darf sich NICHT ändern.
    from diakronos_app.models.chat import ChatGespraech as G
    from diakronos_app.models.chat import ChatNachricht as N
    from diakronos_app.models.chat import ChatTeilnehmer as T
    from diakronos_app.models.diakonos import Gruppenmitgliedschaft as GM
    from diakronos_app.models.rechte import RechteModul as RM

    s = patched_db()
    for modell in (N, T, G):
        s.query(modell).delete()
    s.query(GM).delete()
    s.query(RM).delete()
    s.query(Gruppe).delete()
    s.commit()
    _viele_gruppen(s, "Welt30b", 30)
    dreissig, zeilen_dreissig = _messen(engine)
    assert zeilen_dreissig == 30
    assert sechzig == dreissig, (sechzig, dreissig)
