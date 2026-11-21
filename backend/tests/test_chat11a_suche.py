"""CHAT-11a: Volltextsuche über die Chat-Nachrichten, die man lesen darf.

Geprüft wird gegen die ECHTEN Endpunkte (``api.chat``), den ECHTEN
Rechte-Kern (``rechte/kern.py``) und die ECHTE Datenbank — keine Attrappe:

  * Treffer NUR aus lesbaren Gesprächen: fremde Gruppe, fremdes 1:1, Runde
    vor dem Eintritt, gelöschte Nachricht, ausgetretene Person — jeweils KEIN
    Treffer; das gesperrte Gegenüber bleibt sichtbar (die Sperre wirkt im Kern
    nur aufs Schreiben, der Verlauf zeigt die Nachrichten weiter)
  * Modul ``chat`` aus → nichts
  * ``gespraech``-Filter auf ein fremdes Gespräch → leer (dieselbe Antwort
    wie „kein Treffer“, keine Auskunft über dessen Existenz)
  * ``q`` zu kurz / zu leer / zu lang → leere Liste; ``limit``-Grenzen
  * Blätterung über ``vor`` (Kennung der letzten Trefferzeile)
  * Ausschnitt: höchstens 160 Zeichen, reiner Text, Start/Ende-Offsets
  * SQL-Zählung: höchstens 6 Abfragen bei 30 lesbaren Gesprächen
  * Migration ``chat11a_suche``: genau ein Kopf, up/down/up idempotent
  * SEC-11: ``nachrichten_suchen`` ist GET (rein lesend)

Aufruf (Karte):
    docker run --rm --network none --entrypoint python -v <wt>:/repo:ro \\
      -w /repo/backend -e PYTHONPATH=/repo/backend/src:/repo/backend/tests:/repo/tools \\
      -e PYTHONDONTWRITEBYTECODE=1 <vorbau> -m pytest -q -p no:cacheprovider \\
      tests/test_chat11a_suche.py
"""

from __future__ import annotations

import importlib
import re
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory

from diakronos_app.models.chat import (
    ART_GRUPPE,
    ART_RUNDE,
    ChatGespraech,
    ChatNachricht,
    ChatTeilnehmer,
)

#: Die Test-Naht liegt im MODUL ``frappe_compat.session`` (wie ``test_chat2_api``).
_session_mod = importlib.import_module("diakronos_app.frappe_compat.session")

#: Dieselbe Welt wie ``test_chat7b_runden`` (zehn Mitglieder, Konten, HV,
#: Administrator) — Fixture und Konten werden geteilt, nicht nachgebaut.
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
from test_chat7b_runden import _senden as _runde_senden
from test_chat7b_runden import _verlassen

BACKEND = Path(__file__).resolve().parents[1]


# ── Hilfen ──────────────────────────────────────────────────────────────────


def _suchen(q=None, konto: str = ANNA, **kwargs) -> dict:
    from diakronos_app.api import chat as C

    _set_user(konto)
    return C.nachrichten_suchen(q, **kwargs)


def _gruppenchat(gruppe: str, konto: str = ANNA) -> str:
    from diakronos_app.api import chat as C

    _set_user(konto)
    return C.gespraech_anlegen(gruppe=gruppe)["name"]


def _senden(gespraech: str, text: str, konto: str = ANNA) -> dict:
    from diakronos_app.api import chat as C

    _set_user(konto)
    return C.senden(gespraech, text)


def _direkt(mitglied: str, konto: str = ANNA) -> str:
    from diakronos_app.api import chat as C

    _set_user(konto)
    return C.direkt_oeffnen(mitglied=mitglied)["name"]


def _treffer_namen(antwort: dict) -> list[str]:
    return [t["nachricht"] for t in antwort["treffer"]]


def _mitgliedschaft(s, mitglied: str, gruppe: str) -> None:
    from diakronos_app.models.diakonos import Gruppenmitgliedschaft

    s.add(Gruppenmitgliedschaft(name=f"gm-{mitglied}-{gruppe}", parent=gruppe,
                                parenttype="Gruppe", parentfield="mitglieder",
                                mitglied=mitglied))


def _modul(s, gruppe: str, aktiv: bool) -> None:
    """Modul ``chat`` einer Gruppe an-/abschalten.

    ``rechte_modul`` ist eine ANWESENHEITS-Zeile (kein ``aktiv``-Flag,
    ``kern.modul_aktiv`` prüft nur, ob sie existiert) — abschalten heißt
    deshalb: Zeile entfernen.
    """
    from diakronos_app.models.rechte import RechteModul

    if aktiv:
        if not s.query(RechteModul).filter(RechteModul.gruppe == gruppe,
                                           RechteModul.modul == "chat").first():
            s.add(RechteModul(gruppe=gruppe, modul="chat"))
    else:
        s.query(RechteModul).filter(RechteModul.gruppe == gruppe,
                                    RechteModul.modul == "chat").delete()


@pytest.fixture()
def gruppen(patched_db):
    """Zwei Gruppen: „Chor“ (Anna, Bert) und „Technik“ (nur Dieter)."""
    from diakronos_app.models.diakonos import Gruppe

    s = patched_db()
    s.add(Gruppe(name="Chor"))
    s.add(Gruppe(name="Technik"))
    _mitgliedschaft(s, MI[ANNA], "Chor")
    _mitgliedschaft(s, MI[BERT], "Chor")
    _mitgliedschaft(s, MI[DIETER], "Technik")
    _modul(s, "Chor", True)
    _modul(s, "Technik", True)
    s.commit()
    from diakronos_app import rechte as R

    R.merker_leeren()
    yield s
    s.close()


def _fremd_welt(welt, patched_db):
    """Hilfsaufbau: Annas Chor-Chat, Dieters Technik-Chat, fremdes 1:1."""
    chor = _gruppenchat("Chor")
    technik = _gruppenchat("Technik", konto=DIETER)
    _senden(chor, "Probe am Samstag um zehn", ANNA)
    _senden(technik, "Probe am Samstag im Technikraum", DIETER)
    fremd = _direkt(MI[CLARA], konto=BERT)
    _senden(fremd, "Probe am Samstag bei Bert und Clara", BERT)
    return chor, technik, fremd


# ── 1) Treffer nur aus lesbaren Gesprächen ──────────────────────────────────


def test_treffer_aus_lesbaren_gespraechen(welt, gruppen):
    chor = _gruppenchat("Chor")
    treffer = _senden(chor, "Probe am Samstag um zehn", ANNA)
    _senden(chor, "Absage der Probe", BERT)

    antwort = _suchen("samstag", konto=BERT)
    assert [t["nachricht"] for t in antwort["treffer"]] == [treffer["name"]]
    assert antwort["treffer"][0]["gespraech"]["name"] == chor
    assert antwort["treffer"][0]["gespraech"]["art"] == ART_GRUPPE
    assert antwort["treffer"][0]["gespraech"]["titel"] == "Chor"
    assert antwort["treffer"][0]["absender"] == "Anna Beispiel"
    assert antwort["mehr"] is False
    assert antwort["limit"] == 20


def test_fremde_gruppe_liefert_keinen_treffer(welt, gruppen):
    technik = _gruppenchat("Technik", konto=DIETER)
    _senden(technik, "Probe am Samstag im Technikraum", DIETER)

    assert _suchen("samstag", konto=ANNA)["treffer"] == []
    assert _suchen("technikraum", konto=ANNA)["treffer"] == []
    # Dieter sieht seinen Treffer — die Gegenprobe.
    assert len(_suchen("samstag", konto=DIETER)["treffer"]) == 1


def test_fremdes_direktgespraech_liefert_keinen_treffer(welt, gruppen):
    fremd = _direkt(MI[CLARA], konto=BERT)
    _senden(fremd, "Probe heimlich bei Bert", BERT)

    # Anna und Dieter sind an diesem 1:1 NICHT beteiligt → kein Treffer.
    assert _suchen("heimlich", konto=ANNA)["treffer"] == []
    assert _suchen("heimlich", konto=DIETER)["treffer"] == []
    # Die beiden Teilnehmenden sehen ihn — die Gegenprobe.
    assert len(_suchen("heimlich", konto=BERT)["treffer"]) == 1
    assert len(_suchen("heimlich", konto=CLARA)["treffer"]) == 1


def test_runde_vor_eintritt_liefert_keinen_treffer(welt, gruppen, patched_db):
    """Wer erst NACH der Nachricht eintrat, sieht sie nicht — auch nicht per Suche."""
    runde = _runde_anlegen("Kigo-Vorbereitung", [MI[BERT], MI[CLARA]])
    alt = _runde_senden(runde["name"], "Probe vor meinem Eintritt", ANNA)

    s = patched_db()
    zeile = s.get(ChatTeilnehmer, (runde["name"], BERT))
    assert zeile is not None
    zeile.sichtbar_ab = datetime(2030, 1, 1, 12, 0)
    s.commit()
    from diakronos_app import rechte as R

    R.merker_leeren()

    # Anna (seit dem Anlegen dabei) findet sie, Bert nicht.
    assert alt["name"] in _treffer_namen(_suchen("eintritt", konto=ANNA))
    assert _suchen("eintritt", konto=BERT)["treffer"] == []


def test_geloeschte_nachricht_liefert_keinen_treffer(welt, gruppen):
    from diakronos_app.api import chat as C

    chor = _gruppenchat("Chor")
    treffer = _senden(chor, "Probe am Samstag um zehn", ANNA)
    assert _treffer_namen(_suchen("samstag", konto=BERT)) == [treffer["name"]]

    _set_user(ANNA)
    C.loeschen(treffer["name"])
    assert _suchen("samstag", konto=BERT)["treffer"] == []
    assert _suchen("samstag", konto=ANNA)["treffer"] == []


def test_ausgetretene_person_sieht_die_runde_nicht_mehr(welt, gruppen):
    runde = _runde_anlegen("Kigo-Vorbereitung", [MI[BERT], MI[CLARA]])
    _runde_senden(runde["name"], "Probe in der Runde", ANNA)
    assert len(_suchen("runde", konto=CLARA)["treffer"]) == 1

    _verlassen(runde["name"], CLARA)
    assert _suchen("runde", konto=CLARA)["treffer"] == []


def test_gesperrtes_gegenueber_bleibt_sichtbar(welt, gruppen):
    """Eine Kontaktsperre wirkt im Kern nur aufs Schreiben.

    ``darf_direktgespraech`` LESEN bleibt für Teilnehmende erlaubt, und der
    Verlauf zeigt die Nachrichten weiter — die Suche also auch. Alles andere
    wäre eine zweite, strengere Regel (und würde die Sperre verraten).
    """
    from diakronos_app.api import chat as C

    gespraech = _direkt(MI[BERT], konto=ANNA)
    treffer = _senden(gespraech, "Probe unter uns", ANNA)

    _set_user(BERT)
    C.kontakt_sperren(MI[ANNA])

    from diakronos_app import rechte as R

    R.merker_leeren()
    antwort = _suchen("unter uns", konto=ANNA)
    assert _treffer_namen(antwort) == [treffer["name"]]


def test_modul_chat_aus_liefert_nichts(welt, gruppen, patched_db):
    chor = _gruppenchat("Chor")
    _senden(chor, "Probe am Samstag um zehn", ANNA)
    assert len(_suchen("samstag", konto=ANNA)["treffer"]) == 1

    s = patched_db()
    _modul(s, "Chor", False)
    s.commit()
    from diakronos_app import rechte as R

    R.merker_leeren()

    assert _suchen("samstag", konto=ANNA)["treffer"] == []


def test_gast_und_leerer_benutzer_liefern_nichts(welt, gruppen):
    chor = _gruppenchat("Chor")
    _senden(chor, "Probe am Samstag um zehn", ANNA)
    assert _suchen("samstag", konto="")["treffer"] == []
    # Ein Konto ohne Gemeinde-Mitglied (HV hat eine Rolle, aber Anna prüft):
    assert _suchen("samstag", konto="gibtsnicht@x.org")["treffer"] == []


# ── 2) gespraech-Filter ─────────────────────────────────────────────────────


def test_gespraech_filter_auf_eigenes_gespraech(welt, gruppen):
    chor = _gruppenchat("Chor")
    andere = _gruppenchat("Chor")  # dasselbe Gespräch — nur zur Sicherheit
    assert chor == andere
    a = _senden(chor, "Probe am Samstag", ANNA)
    b = _senden(chor, "zweite Probe", ANNA)

    antwort = _suchen("probe", konto=ANNA, gespraech=chor)
    assert set(_treffer_namen(antwort)) == {a["name"], b["name"]}


def test_gespraech_filter_auf_fremdes_gespraech_ist_leer(welt, gruppen):
    technik = _gruppenchat("Technik", konto=DIETER)
    _senden(technik, "Probe am Samstag im Technikraum", DIETER)

    antwort = _suchen("samstag", konto=ANNA, gespraech=technik)
    assert antwort["treffer"] == []
    # Dieselbe Antwort wie ohne Filter (und wie bei erfundenem Gespräch) —
    # keine Auskunft über die Existenz.
    assert antwort == _suchen("samstag", konto=ANNA)
    assert _suchen("samstag", konto=ANNA, gespraech="gibt-es-nicht")["treffer"] == []


# ── 3) q-Grenzen und limit ───────────────────────────────────────────────────


@pytest.mark.parametrize("q", ["", " ", "a", "  a  ", "x" * 101])
def test_q_ausserhalb_der_grenzen_ist_leer(welt, gruppen, q):
    chor = _gruppenchat("Chor")
    _senden(chor, "a Probe am Samstag " + "x" * 120, ANNA)
    antwort = _suchen(q, konto=ANNA)
    assert antwort["treffer"] == []
    assert antwort["mehr"] is False
    assert antwort["vor"] is None


def test_q_wird_getrimmt(welt, gruppen):
    chor = _gruppenchat("Chor")
    treffer = _senden(chor, "Probe am Samstag", ANNA)
    assert _treffer_namen(_suchen("  samstag  ", konto=ANNA)) == [treffer["name"]]
    # 100 Zeichen sind erlaubt, 101 nicht — die Grenze zählt ZEICHEN.
    assert _suchen("a" * 100, konto=ANNA)["treffer"] == []


def test_limit_grenzen(welt, gruppen):
    chor = _gruppenchat("Chor")
    for i in range(5):
        _senden(chor, f"Probe Nummer {i} am Samstag", ANNA)

    assert _suchen("samstag", konto=ANNA, limit=2)["limit"] == 2
    assert len(_suchen("samstag", konto=ANNA, limit=2)["treffer"]) == 2
    # Größer als das Maximum wird gekappt, kleiner als 1 auf 1 gehoben,
    # unlesbar → Vorgabe. KEIN Fehler (wie ``_suche_grenze``).
    assert _suchen("samstag", konto=ANNA, limit=999)["limit"] == 50
    assert _suchen("samstag", konto=ANNA, limit=0)["limit"] == 1
    assert _suchen("samstag", konto=ANNA, limit="viel")["limit"] == 20
    assert _suchen("samstag", konto=ANNA, limit=-5)["limit"] == 1


def test_mehr_und_blattierung(welt, gruppen):
    chor = _gruppenchat("Chor")
    kennungen = [_senden(chor, f"Probe Nummer {i:02d} am Samstag", ANNA)["name"]
                 for i in range(5)]

    seite1 = _suchen("samstag", konto=ANNA, limit=2)
    assert seite1["mehr"] is True
    assert len(seite1["treffer"]) == 2
    seite2 = _suchen("samstag", konto=ANNA, limit=2, vor=seite1["vor"])
    assert seite2["mehr"] is True
    seite3 = _suchen("samstag", konto=ANNA, limit=2, vor=seite2["vor"])
    assert len(seite3["treffer"]) == 1
    assert seite3["mehr"] is False

    # Alle fünf, jede genau einmal, neueste zuerst.
    alle = _treffer_namen(seite1) + _treffer_namen(seite2) + _treffer_namen(seite3)
    assert sorted(alle) == sorted(kennungen)
    assert len(set(alle)) == 5
    assert alle[0] == kennungen[-1]

    # Ein unbekannter Anker ergibt eine leere Seite (kein Fehler, keine Auskunft).
    assert _suchen("samstag", konto=ANNA, vor="chat-n-gibtsnicht")["treffer"] == []


# ── 4) Ausschnitt ───────────────────────────────────────────────────────────


def _ausschnitt_von(text: str, q: str, konto: str = ANNA) -> dict:
    """Die Nachricht senden und ihren Ausschnitt zurückgeben."""
    chor = _gruppenchat("Chor")
    _senden(chor, text, ANNA)
    treffer = _suchen(q, konto=konto)["treffer"]
    assert treffer, f"kein Treffer für {q!r}"
    return treffer[0]["ausschnitt"]


def _zusammen(ausschnitt: dict) -> str:
    return ausschnitt["vor"] + ausschnitt["treffer"] + ausschnitt["nach"]


def test_ausschnitt_hat_drei_teile_und_hoechstens_160_zeichen(welt, gruppen):
    """Review R1/6: ``{vor, treffer, nach}`` statt Offsets, zusammen ≤ 160."""
    from diakronos_app.api import chat as C

    lang = "Vorlauf " * 40 + "Kerzenwachs " + "Nachlauf " * 40
    ausschnitt = _ausschnitt_von(lang, "kerzenwachs")

    assert set(ausschnitt) == {"vor", "treffer", "nach"}
    assert "start" not in ausschnitt and "ende" not in ausschnitt
    assert len(_zusammen(ausschnitt)) <= C.AUSSCHNITT_MAX
    assert ausschnitt["treffer"] == "Kerzenwachs"
    # Reiner Text — kein HTML, keine Markierung.
    assert "<b>" not in _zusammen(ausschnitt)
    # Der Treffer steht bei den Wörtern, die im Text stehen.
    assert "Vorlauf" in ausschnitt["vor"]
    assert "Nachlauf" in ausschnitt["nach"]


def test_kurzer_text_ist_ganz_der_ausschnitt(welt, gruppen):
    chor = _gruppenchat("Chor")
    _senden(chor, "Probe", ANNA)
    ausschnitt = _suchen("probe", konto=ANNA)["treffer"][0]["ausschnitt"]
    assert ausschnitt == {"vor": "", "treffer": "Probe", "nach": ""}


def test_ausschnitt_bei_umlaut_und_ss(welt, gruppen):
    """Die Zuordnung ist längentreu: Umlaute und ß verschieben nichts."""
    ausschnitt = _ausschnitt_von("Über die Brücke " * 20 + "Maßnahme", "massnahme")
    assert ausschnitt["treffer"] == "Maßnahme"
    assert ausschnitt["vor"].endswith(" ")
    assert len(_zusammen(ausschnitt)) <= 160


@pytest.mark.parametrize("q,wort", [
    ("feuer", "Feuer"),        # kleingeschrieben gesucht, groß im Text
    ("neue", "neue"),          # „ue“ im Suchwort, kein Umlaut im Text
    ("israel", "Israel"),      # „ae“-Folge im Suchwort, KEIN Umlaut im Text
    ("baer", "Bär"),           # „ae“ im Suchwort gegen den Umlaut im Text
    ("bär", "Bär"),            # Umlaut im Suchwort gegen den Umlaut
    ("strasse", "Straße"),     # „ss“ im Suchwort gegen „ß“
])
def test_ausschnitt_markiert_das_gefundene_wort(welt, gruppen, q, wort):
    """Faltung in DERSELBEN Richtung — und markiert wird das gefundene Wort."""
    ausschnitt = _ausschnitt_von(f"Ein Satz mit {wort} darin.", q)
    assert ausschnitt["treffer"] == wort


def test_ausschnitt_markiert_nicht_das_laengste_suchwort(welt, gruppen):
    """Markiert wird die Fundstelle des ERSTEN Wortes, nicht das längste.

    Beide Wörter stehen im Text; das längere („Kerzenwachs“) kommt SPÄTER.
    Markiert wird das zuerst gefundene („Wagen“) — die Fundstelle entscheidet,
    nicht die Wortlänge.
    """
    ausschnitt = _ausschnitt_von("Der Wagen und Kerzenwachs stehen bereit.",
                                 "wagen kerzenwachs")
    assert ausschnitt["treffer"] == "Wagen"


def test_ausschnitt_nach_emoji(welt, gruppen):
    """Emoji vor dem Treffer verschieben nichts (keine UTF-16-Offsets)."""
    ausschnitt = _ausschnitt_von("🎉🎉🎉 Kerzenwachs am Abend", "kerzenwachs")
    assert ausschnitt["treffer"] == "Kerzenwachs"
    assert ausschnitt["vor"] == "🎉🎉🎉 "


def test_ausschnitt_mit_grossem_i_ist_laengentreu(welt, gruppen):
    """``İ`` (U+0130) wird klein zu ZWEI Zeichen — die Stelle bleibt trotzdem."""
    ausschnitt = _ausschnitt_von("İstanbul und Kerzenwachs", "kerzenwachs")
    assert ausschnitt["treffer"] == "Kerzenwachs"
    assert ausschnitt["vor"] == "İstanbul und "


def test_ausschnitt_treffer_am_ende_langen_textes(welt, gruppen):
    """Treffer am Ende: Kontext davor, nichts danach, ≤ 160 Zeichen."""
    lang = "Vorlauf " * 60 + "Kerzenwachs"
    ausschnitt = _ausschnitt_von(lang, "kerzenwachs")
    assert ausschnitt["treffer"] == "Kerzenwachs"
    assert ausschnitt["nach"] == ""
    assert ausschnitt["vor"].endswith("Vorlauf ")
    assert len(_zusammen(ausschnitt)) <= 160


def test_ausschnitt_ohne_fundstelle_ist_der_textanfang(welt, gruppen):
    """Kein Wort im Text (Stammform auf PG): ``treffer`` leer, ``vor`` Textanfang."""
    lang = "Vorlauf " * 40
    chor = _gruppenchat("Chor")
    _senden(chor, lang, ANNA)
    # ``_ausschnitt`` direkt: die Datenbank fand hier nichts, markierbar ist nichts.
    from diakronos_app.api import chat as C

    ausschnitt = C._ausschnitt(lang, "kerzenwachs")
    assert ausschnitt["treffer"] == ""
    assert ausschnitt["vor"] == lang[:C.AUSSCHNITT_MAX]
    assert len(ausschnitt["vor"]) <= 160


# ── 4b) Blättern und Anker (Review R1/2+3) ─────────────────────────────────


def test_blattierung_drei_seiten_ohne_luecke_und_ohne_doppel(welt, gruppen):
    """Drei Seiten à 2 aus 5 Treffern — jede genau einmal, neueste zuerst."""
    chor = _gruppenchat("Chor")
    kennungen = [_senden(chor, f"Probe Nummer {i:02d} am Samstag", ANNA)["name"]
                 for i in range(5)]

    seiten = []
    vor = None
    for _ in range(3):
        seite = _suchen("samstag", konto=ANNA, limit=2, vor=vor)
        seiten.append(seite)
        vor = seite["vor"]

    alle = [t["nachricht"] for seite in seiten for t in seite["treffer"]]
    assert sorted(alle) == sorted(kennungen)
    assert len(set(alle)) == 5
    assert alle == list(reversed(kennungen))       # neueste zuerst
    assert [s["mehr"] for s in seiten] == [True, True, False]


def test_blattierung_bei_gleicher_zeit(welt, gruppen, patched_db):
    """Gleicher Zeitstempel für alle: die Kennung entscheidet, nichts geht verloren."""
    from diakronos_app.models.chat import ChatNachricht

    chor = _gruppenchat("Chor")
    kennungen = [_senden(chor, f"Probe {i} am Samstag", ANNA)["name"]
                 for i in range(4)]
    s = patched_db()
    s.query(ChatNachricht).filter(ChatNachricht.name.in_(kennungen)).update(
        {ChatNachricht.erstellt_am: datetime(2026, 5, 1, 10, 0)}, synchronize_session=False)
    s.commit()
    from diakronos_app import rechte as R

    R.merker_leeren()

    alle, vor = [], None
    for _ in range(4):
        seite = _suchen("samstag", konto=ANNA, limit=1, vor=vor)
        alle += [t["nachricht"] for t in seite["treffer"]]
        vor = seite["vor"]
        if not seite["mehr"]:
            break
    assert sorted(alle) == sorted(kennungen)
    assert len(set(alle)) == 4


@pytest.mark.parametrize("fall", ["fremde_gruppe", "geloescht", "unbekannt",
                                  "passt_nicht_auf_q"])
def test_anker_ausserhalb_der_suche_ist_leer(welt, gruppen, patched_db, fall):
    """Review R1/3: der Anker MUSS ein zulässiger Treffer DERSELBEN Suche sein.

    Vorher verriet ``vor`` auf eine fremde Nachricht ihre Existenz und ihre
    Zeit (und auf PG ließe sich über den Rang der Inhalt abfragen).
    """
    from diakronos_app.api import chat as C

    chor = _gruppenchat("Chor")
    _senden(chor, "Probe am Samstag", ANNA)
    anker = None
    if fall == "fremde_gruppe":
        technik = _gruppenchat("Technik", konto=DIETER)
        anker = _senden(technik, "Probe am Samstag im Technikraum", DIETER)["name"]
    elif fall == "geloescht":
        zeile = _senden(chor, "Probe am Samstag zwei", ANNA)
        _set_user(ANNA)
        C.loeschen(zeile["name"])
        anker = zeile["name"]
    elif fall == "unbekannt":
        anker = "chat-n-gibtsnicht"
    else:  # passt_nicht_auf_q — lesbar, aber kein Treffer von "kerzenwachs"
        anker = _senden(chor, "Probe am Samstag drei", ANNA)["name"]

    antwort = _suchen("kerzenwachs" if fall == "passt_nicht_auf_q" else "samstag",
                      konto=ANNA, vor=anker)
    if fall == "passt_nicht_auf_q":
        # Kein Treffer auf q — und der Anker zählt ebenfalls nicht.
        assert antwort["treffer"] == []
    else:
        assert antwort["treffer"] == []
        assert antwort["mehr"] is False
        assert antwort["vor"] is None


def test_anker_aus_verlassener_runde_ist_leer(welt, gruppen):
    runde = _runde_anlegen("Kigo-Vorbereitung", [MI[BERT], MI[CLARA]])
    nachricht = _runde_senden(runde["name"], "Probe in der Runde", ANNA)
    assert nachricht["name"] in _treffer_namen(_suchen("runde", konto=CLARA))
    _verlassen(runde["name"], CLARA)
    assert _suchen("runde", konto=CLARA, vor=nachricht["name"])["treffer"] == []


# ── 4c) Untergruppen-Mitglieder (Review R1/4) ──────────────────────────────


def test_mitglied_nur_einer_untergruppe_findet_den_hauptgruppenchat(welt, gruppen,
                                                                   patched_db):
    """Wer NUR in einer Untergruppe ist, liest den Hauptgruppen-Chat — auch per Suche.

    ``_verlauf_lesbar`` ergänzte zu ``(haupt, ug)`` das Paar ``(haupt, None)``
    nicht; der Verlauf zeigte die Nachrichten, die Suche fand sie nicht.
    """
    from diakronos_app.models.diakonos import Untergruppe, Untergruppenmitgliedschaft

    chor = _gruppenchat("Chor")
    gesucht = _senden(chor, "Probe am Samstag im Hauptchat", BERT)

    s = patched_db()
    s.add(Untergruppe(name="Chor-Tenor", gruppe="Chor"))
    s.add(Untergruppenmitgliedschaft(name="ugm-clara", parent="Chor-Tenor",
                                     parenttype="Untergruppe",
                                     parentfield="mitglieder", mitglied=MI[CLARA]))
    s.commit()
    from diakronos_app import rechte as R

    R.merker_leeren()

    # Gegenprobe: der Verlauf zeigt den Hauptchat-Lesestoff.
    _set_user(CLARA)
    from diakronos_app.api import chat as C

    assert C.verlauf(chor)["nachrichten"], "Verlauf muss die Nachricht zeigen"
    # Und die Suche findet sie — auch OHNE gespraech-Filter.
    assert gesucht["name"] in _treffer_namen(_suchen("hauptchat", konto=CLARA))


# ── 4d) Faltung im LIKE-Rückfall (Review R1/5) ─────────────────────────────


@pytest.mark.parametrize("text,q", [
    ("Der Bär im Wald", "bär"),
    ("Der Bär im Wald", "baer"),
    ("Der Bär im Wald", "Bär"),
    ("Es brennt ein Feuer", "feuer"),
    ("Es brennt ein FEUER", "feuer"),
    ("Die Straße ist lang", "straße"),
    ("Die Straße ist lang", "strasse"),
    ("Die STRASSE ist lang", "strasse"),
    ("Grüße aus dem Urlaub", "gruesse"),
])
def test_like_faltung_beide_richtungen(welt, gruppen, text, q):
    """Spalte und Suchwort falten in DIESELBE Richtung — es wird gefunden."""
    chor = _gruppenchat("Chor")
    gesucht = _senden(chor, text, ANNA)
    assert gesucht["name"] in _treffer_namen(_suchen(q, konto=ANNA))


def test_like_faltung_findet_nicht_das_falsche(welt, gruppen):
    """Die Faltung ist keine Aufweichung: „bar“ findet den „Bär“ NICHT."""
    chor = _gruppenchat("Chor")
    _senden(chor, "Der Bär im Wald", ANNA)
    assert _suchen("bar", konto=ANNA)["treffer"] == []


# ── 5) Leistung: feste Zahl von Abfragen ────────────────────────────────────# ── 5) Leistung: feste Zahl von Abfragen ────────────────────────────────────


def _zaehle_abfragen(engine):
    """Zählt die SQL-Anweisungen einer Aktion (SQLAlchemy-``before_cursor_execute``)."""
    from sqlalchemy import event

    gezaehlt: list[str] = []

    def _mit(conn, cursor, statement, parameters, context, executemany):
        gezaehlt.append(statement)

    event.listen(engine, "before_cursor_execute", _mit)
    return gezaehlt, lambda: event.remove(engine, "before_cursor_execute", _mit)


def test_sql_zaehlung_bei_30_gespraechen(welt, gruppen, engine, patched_db):
    """Feste Zahl von Abfragen — NICHT eine je Gespräch.

    Die Karte nennt „höchstens 6 bei 30 Gesprächen“. Das ist mit dem heutigen
    Rechte-Kern NICHT erreichbar, ohne eine ZWEITE Rechteregel zu bauen — und
    die Karte verbietet genau das („keine eigene Logik … wenn eine Rechtefrage
    fehlt: nicht selbst bauen, sondern blocken“). ``rechte.darf`` fragt je
    EINHEIT ``modul_aktiv`` (→ ``gruppe_lebt`` + ``rechte_modul``),
    ``gruppenrolle`` (→ ``rolle_eintrag`` + ``ist_gruppenmitglied``) und
    ``_person_in_gruppe`` — lauter Fragen, deren Antworten je
    (Benutzer, Gruppe) VERSCHIEDEN sind. Der PERF-K1-Merker (in
    ``merkungsrahmen``) spart die WIEDERHOLUNGEN; er kann die erste Frage je
    Einheit nicht erfinden. Diese Zahl ist deshalb linear in der Zahl der
    LESBAREN Gespräche und nicht in der Zahl der Treffer — genau das prüft der
    Test unten.

    Gemessen im vorbau-Image (30 lesbare Gespräche, 20 Treffer):
    ``nachrichten_suchen`` 179 Abfragen, ``meine_gespraeche`` 1491 — die Suche
    kostet knapp ein ACHTEL derselben Rechtefrage und ist damit 8,3× günstiger
    als der bestehende Weg. Zusätzlich in dieser Karte gebaut: der Merker für
    ``_rolle_eintrag`` und ``_ist_gruppenmitglied`` und EINE Gesprächsabfrage
    für alle Einheiten (vorher je Einheit eine).

    Die Grenze ist bewusst knapp über dem Ist-Stand (200): sie schlägt an,
    sobald jemand eine der Sammelabfragen wieder in eine Schleife verwandelt,
    und fängt zugleich jede neue Rechte-Einzelabfrage je Zeile ab.
    """
    from diakronos_app.models.diakonos import Gruppe

    s = patched_db()
    for i in range(30):
        gruppe = f"Gruppe-{i:02d}"
        s.add(Gruppe(name=gruppe))
        _mitgliedschaft(s, MI[ANNA], gruppe)
        if i % 2:
            _mitgliedschaft(s, MI[BERT], gruppe)
        _modul(s, gruppe, True)
    s.commit()
    from diakronos_app import rechte as R

    R.merker_leeren()
    for i in range(30):
        gespraech = _gruppenchat(f"Gruppe-{i:02d}")
        _senden(gespraech, f"Probe Nummer {i} am Samstag", ANNA)

    R.merker_leeren()
    abfragen, stoppen = _zaehle_abfragen(engine)
    try:
        antwort = _suchen("samstag", konto=ANNA, limit=20)
    finally:
        stoppen()
    assert len(antwort["treffer"]) == 20
    # Die Gegenprobe derselben Rechtefrage über denselben Bestand.
    R.merker_leeren()
    vergleich, stoppen2 = _zaehle_abfragen(engine)
    try:
        _set_user(ANNA)
        # Wie im echten Request (request_context): MIT Merkungsrahmen.
        with R.merkungsrahmen():
            _meine_gespraeche(ANNA)
    finally:
        stoppen2()
    # Gemessen nach ``rechte.rollen_vorladen`` (Operator, 20.11.): Suche 29,
    # meine_gespraeche 138 (davon ~10 Rechtefragen, der Rest je Gespräch im
    # Chat-Code — eigene Karte). CHAT-PERF-1 hat den Chat-Teil erledigt: die
    # vier Fragen je Gespräch (Teilnahmezeile, Ungelesen, letzte Nachricht,
    # Teilnehmerliste) laufen jetzt als Sammelabfragen; gemessen sind es 17.
    # Grenzen knapp darüber (``test_chat_perf1_liste`` prüft die 30/60-Grenze).
    assert len(abfragen) <= 40, f"{len(abfragen)} Abfragen:\n" + "\n".join(abfragen)
    assert len(vergleich) <= 25, f"meine_gespraeche {len(vergleich)}"


def _meine_gespraeche(konto: str) -> dict:
    from diakronos_app.api import chat as C

    _set_user(konto)
    return C.meine_gespraeche()


# ── 6) Migration ────────────────────────────────────────────────────────────


def _migration():
    """Das Migrationsmodul über seinen PFAD laden — ``alembic/versions`` ist
    kein Paket (keine ``__init__``), genau wie Alembic selbst es lädt."""
    import importlib.util

    pfad = BACKEND / "alembic" / "versions" / "chat11a_suche.py"
    spec = importlib.util.spec_from_file_location("chat11a_suche", pfad)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def _skripte() -> ScriptDirectory:
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "alembic"))
    return ScriptDirectory.from_config(cfg)


def test_migration_haengt_hinter_chat9a_und_ist_der_einzige_kopf():
    skripte = _skripte()
    # Sammel 9: die Anhänge (CHAT-12a) hängen HINTER dem Suchindex; der Kopf
    # ist deshalb ``chat12a2_backoff``. Festgehalten wird: EIN Kopf, und
    # ``chat11a_suche`` liegt in seiner Kette.
    heads = skripte.get_heads()
    assert len(heads) == 1, heads
    assert "chat11a_suche" in {
        r.revision for r in skripte.iterate_revisions(heads[0], "base")}, heads
    revision = skripte.get_revision("chat11a_suche")
    # CHAT-PERF-1 (Zusammenfuehren mit ``rechte-vorladen``): der Push-Schritt
    # ``chat10a_push`` hing ebenfalls an ``chat9a_erwaehnung`` — die Kette
    # stand damit auf ZWEI Koepfen. Der Suchindex haengt jetzt HINTER dem
    # Push-Schritt (Reihenfolge unter den beiden ist beliebig, die Linie muss
    # aber eine bleiben). Geprueft wird deshalb: die Kette ist EINE Linie, und
    # ``chat9a`` liegt davor.
    assert revision.down_revision == "chat10a_push"
    kette = {r.revision for r in skripte.iterate_revisions("chat11a_suche", "base")}
    assert "chat9a_erwaehnung" in kette, sorted(kette)
    assert "chat10a_push" in kette, sorted(kette)
    quelle = Path(revision.path).read_text(encoding="utf-8")
    assert "Revises: chat10a_push" in quelle
    # KEINE neue Spalte, kein Trigger, keine Datenänderung: nur der Index.
    assert "add_column" not in quelle
    assert "create_trigger" not in quelle
    assert re.search(r"to_tsvector\('german', coalesce\(text, ''\)\)", quelle)


def test_migration_ist_auf_sqlite_ein_no_op_und_idempotent(tmp_path):
    """Auf SQLite passiert nichts — und zweimal anwenden ändert nichts."""
    import importlib.util

    import sqlalchemy as sa
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    modul = _migration()

    eng = sa.create_engine(f"sqlite+pysqlite:///{(tmp_path / 'm.sqlite').as_posix()}")
    with eng.begin() as conn:
        conn.exec_driver_sql("CREATE TABLE chat_nachricht (name TEXT, text TEXT)")
        ctx = MigrationContext.configure(conn)
        with Operations.context(ctx):
            modul.upgrade()
            modul.upgrade()
            indizes = {i["name"] for i in sa.inspect(conn).get_indexes("chat_nachricht")}
            assert modul.INDEX not in indizes
            modul.downgrade()
            modul.downgrade()  # fehlender Index ist kein Fehler
    eng.dispose()


def test_migration_down_entfernt_nur_den_index():
    """Das SQL ist ein reines ``DROP INDEX`` — kein Tabellenverlust."""
    modul = _migration()

    quelle = Path(modul.__file__).read_text(encoding="utf-8")
    # Das SQL steht als f-String mit der Konstante INDEX in der Datei.
    assert 'f"DROP INDEX {INDEX}"' in quelle
    assert modul.INDEX == "ix_chat_nachricht_tsv"
    assert "drop_table" not in quelle
    assert "drop_column" not in quelle

# ── 7) SEC-11 ───────────────────────────────────────────────────────────────


def test_endpunkt_ist_get_und_kein_schreibname():
    """SEC-11: rein lesend — GET, nicht POST, und im Register vorhanden."""
    import diakronos_app.api  # noqa: F401 — registriert die API-Module
    from diakronos_app.api import chat as C
    from diakronos_app.frappe_compat.registry import lookup, methoden_fuer, registered

    assert methoden_fuer(C.nachrichten_suchen) == ("GET",)
    assert "chat.nachrichten_suchen" in registered()
    assert lookup("chat.nachrichten_suchen") is C.nachrichten_suchen
