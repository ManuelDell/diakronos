"""CHAT-4a: gebündelte Chat-Glocke (Konzept 1/S1, 3.1, 4.5).

Geprüft wird gegen die ECHTEN Wege — ``api.chat`` (Senden, Lesestand, Stumm),
der ECHTE Scheduler-Eintrag und die ECHTE ``Notification Log``-Zeile:

  * Bündelung: 3 Nachrichten → EINE Glocke mit „3 neue Nachrichten“
  * 5-Minuten-Ruhe: vor Ablauf keine Glocke, danach genau eine (Zeit wird
    injiziert — kein ``sleep``)
  * kein Doppeln beim zweiten Joblauf
  * „aktualisieren statt zweiter Glocke“: neue Nachricht nach dem Glocken →
    dieselbe ``Notification Log``-Zeile wird fortgeschrieben
  * Verfasser/in, stumm geschaltete und wer schon gelesen hat bekommen nichts
    (der Zähler bleibt bei stumm)
  * Rechteentzug → nichts; Modul ``chat`` aus → nichts
  * die Glocke enthält weder Nachrichtentext noch Absender
  * Lesen markiert die Glocke als gelesen
  * Migration ``chat4a_glocke``: genau ein Kopf, hinter ``chat6_meldung``,
    upgrade/downgrade/upgrade, Spalten und Indizes

Aufruf (Karte):
    docker run --rm --network none --entrypoint python -v <wt>:/repo:ro \\
      -w /repo/backend -e PYTHONPATH=/repo/backend/src:/repo/backend/tests:/repo/tools \\
      -e PYTHONDONTWRITEBYTECODE=1 <vorbau> -m pytest -q -p no:cacheprovider \\
      tests/test_chat4a_glocke.py
"""

from __future__ import annotations

import importlib
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory

from diakronos_app import db as dbmod

#: Die Test-Naht liegt im MODUL ``frappe_compat.session`` (wie ``test_chat2_api``).
_session_mod = importlib.import_module("diakronos_app.frappe_compat.session")

from diakronos_app.models.chat import ChatGlocke, ChatNachricht, ChatTeilnehmer
from diakronos_app.models.core import HasRole, NotificationLog, User
from diakronos_app.models.diakonos import (
    Gruppe,
    Gruppenmitgliedschaft,
    Mitglied,
    Untergruppe,
    Untergruppenmitgliedschaft,
)
from diakronos_app.models.rechte import RechteGruppenrolle, RechteModul

BACKEND = Path(__file__).resolve().parents[1]

ADMIN = "admin@x.org"
HV = "hv@x.org"
MV = "mv@x.org"
GL = "gl@x.org"
SAENGER = "saenger@x.org"      # Mitglied Chor
SAENGER2 = "saenger2@x.org"    # zweites Mitglied Chor
NOTEN = "noten@x.org"          # Mitglied der Untergruppe Notenausschuss
FREMD = "fremd@x.org"          # Gemeindemitglied ohne Gruppe
JUGEND = "jugend@x.org"        # Mitglied einer Gruppe OHNE Chat-Modul


def _set_user(konto: str) -> None:
    _session_mod.set_user(konto)


@pytest.fixture()
def welt(patched_db):
    """Chor mit Untergruppe — dieselbe Welt wie ``test_chat2_api.py``."""
    s = patched_db()
    for konto, kurz in [(ADMIN, "Admin"), (HV, "Hv"), (MV, "Mv"), (GL, "Gl"),
                        (SAENGER, "Sa"), (SAENGER2, "Sb"), (NOTEN, "No"),
                        (FREMD, "Fr"), (JUGEND, "Ju")]:
        s.add(User(name=konto, email=konto, enabled=1, full_name=kurz))
        s.add(Mitglied(name=f"M-{kurz}", vorname=kurz, nachname="X", email=konto, user=konto))
    s.add(HasRole(name="hr-admin", parent=ADMIN, parenttype="User", role="System Manager"))
    s.add(Gruppe(name="Chor", gruppenname="Chor"))
    s.add(Gruppe(name="Jugend", gruppenname="Jugend"))
    s.add(Untergruppe(name="UG-Noten", untergruppenname="Notenausschuss", gruppe="Chor"))
    s.add(Gruppenmitgliedschaft(name="gm1", parent="Chor", parentfield="mitglieder",
                                mitglied="M-Sa"))
    s.add(Gruppenmitgliedschaft(name="gm2", parent="Chor", parentfield="mitglieder",
                                mitglied="M-Sb"))
    s.add(Gruppenmitgliedschaft(name="gm3", parent="Chor", parentfield="mitglieder",
                                mitglied="M-Mv"))
    s.add(Untergruppenmitgliedschaft(name="ugm1", parent="UG-Noten",
                                     parentfield="mitglieder", mitglied="M-No"))
    s.add(Gruppenmitgliedschaft(name="gm4", parent="Jugend",
                                parentfield="mitglieder", mitglied="M-Ju"))
    s.add_all([
        RechteGruppenrolle(gruppe="Chor", benutzer=HV, rolle="HV"),
        RechteGruppenrolle(gruppe="Chor", benutzer=MV, rolle="MV"),
        RechteGruppenrolle(gruppe="Chor", untergruppe="UG-Noten", benutzer=GL, rolle="GL"),
        RechteModul(gruppe="Chor", modul="chat"),
    ])
    s.commit()
    yield s
    s.close()


@pytest.fixture()
def gespraech(welt):
    """Das Chor-Gespräch (lazy angelegt, per Endpunkt) — Teilnehmer: Saenger."""
    from diakronos_app.api import chat as C

    _set_user(SAENGER)
    name = C.gespraech_anlegen("Chor")["name"]
    _session_mod.reset_user()
    return name


def _senden(text: str, gespraech: str, konto: str) -> dict:
    from diakronos_app.api import chat as C

    _set_user(konto)
    return C.senden(gespraech, text)


def _teilnahme(gespraech: str, konto: str) -> None:
    """Teilnahmezeile anlegen (sonst hat die Person kein Konto im Gespräch)."""
    from diakronos_app.api import chat as C

    _set_user(konto)
    C.gespraech_anlegen("Chor")
    _session_mod.reset_user()


def _glocken(konto: str | None = None, gespraech: str | None = None) -> list[NotificationLog]:
    with dbmod.SessionLocal() as s:
        abfrage = s.query(NotificationLog).filter(
            NotificationLog.document_type == "chat_gespraech")
        if konto is not None:
            abfrage = abfrage.filter(NotificationLog.for_user == konto)
        if gespraech is not None:
            abfrage = abfrage.filter(NotificationLog.document_name == gespraech)
        return list(abfrage.all())


def _job(jetzt: datetime, ruhe: int = 5) -> int:
    from diakronos_app.api import chat as C

    return C.chat_glocken_buendeln(jetzt=jetzt, ruhe=ruhe)


def _neueste(gespraech: str) -> datetime:
    with dbmod.SessionLocal() as s:
        return s.query(ChatNachricht).filter_by(gespraech=gespraech).order_by(
            ChatNachricht.erstellt_am.desc()).first().erstellt_am


# ── Bündelung und Ruhe ──────────────────────────────────────────────────────


def test_drei_nachrichten_ergeben_eine_glocke_mit_drei(welt, gespraech):
    """Kartenkern: 3 Nachrichten → EINE Glocke „Chor: 3 neue Nachrichten“."""
    _teilnahme(gespraech, SAENGER2)
    for text in ("Erste", "Zweite", "Dritte"):
        _senden(text, gespraech, SAENGER)

    # Ruhe abgelaufen: 10 Minuten nach der letzten Nachricht.
    assert _job(_neueste(gespraech) + timedelta(minutes=10)) == 1

    glocken = _glocken(SAENGER2, gespraech)
    assert len(glocken) == 1
    assert glocken[0].subject == "Chor: 3 neue Nachrichten"
    assert glocken[0].read is False


def test_eine_nachricht_singular(welt, gespraech):
    _teilnahme(gespraech, SAENGER2)
    _senden("Nur eine", gespraech, SAENGER)

    assert _job(_neueste(gespraech) + timedelta(minutes=6)) == 1
    assert _glocken(SAENGER2, gespraech)[0].subject == "Chor: 1 neue Nachricht"


def test_keine_glocke_vor_ablauf_der_ruhe(welt, gespraech):
    """5-Minuten-Ruhe: 1 Minute nach der Nachricht passiert NICHTS (kein sleep)."""
    _teilnahme(gespraech, SAENGER2)
    _senden("Frisch", gespraech, SAENGER)

    assert _job(_neueste(gespraech) + timedelta(minutes=1)) == 0
    assert _glocken(SAENGER2, gespraech) == []
    # Grenzfall: exakt 5 Minuten — die Bedingung ist „älter oder gleich“.
    assert _job(_neueste(gespraech) + timedelta(minutes=5)) == 1
    assert len(_glocken(SAENGER2, gespraech)) == 1


def test_zweiter_joblauf_glockt_nicht_doppelt(welt, gespraech):
    _teilnahme(gespraech, SAENGER2)
    _senden("Einmal", gespraech, SAENGER)
    zeit = _neueste(gespraech) + timedelta(minutes=10)

    assert _job(zeit) == 1
    assert _job(zeit + timedelta(minutes=1)) == 0
    assert _job(zeit + timedelta(minutes=2)) == 0
    assert len(_glocken(SAENGER2, gespraech)) == 1


def test_neue_nachricht_aktualisiert_die_glocke_statt_einer_zweiten(welt, gespraech):
    """Ungelesene Glocke desselben Gesprächs wird fortgeschrieben.

    Review R1 (MUSS 1, Fall b): die ZAHL ist der Ungelesen-Zähler (Lesestand),
    nicht „neu seit der letzten Glocke“. Nach der ersten Glocke (1 Nachricht
    ungelesen) kommen zwei dazu → in derselben Glocke stehen **3**.
    """
    _teilnahme(gespraech, SAENGER2)
    _senden("Erste", gespraech, SAENGER)
    assert _job(_neueste(gespraech) + timedelta(minutes=10)) == 1
    erste = _glocken(SAENGER2, gespraech)
    assert len(erste) == 1
    assert erste[0].subject == "Chor: 1 neue Nachricht"

    # Zwei weitere Nachrichten, danach wieder Ruhe.
    _senden("Zweite", gespraech, SAENGER)
    _senden("Dritte", gespraech, SAENGER)
    assert _job(_neueste(gespraech) + timedelta(minutes=10)) == 1

    glocken = _glocken(SAENGER2, gespraech)
    assert len(glocken) == 1, "zweite Glocke statt Aktualisierung"
    assert glocken[0].name == erste[0].name
    assert glocken[0].subject == "Chor: 3 neue Nachrichten"
    assert glocken[0].read is False


def test_zahl_zaehlt_ab_lesestand_nicht_ab_glockenstand(welt, gespraech):
    """Review R1 (MUSS 1, Fall a): Vorher Gelesenes zählt nie mit.

    Vier Nachrichten, gelesen, dann eine neue → die Glocke sagt „1“, nicht
    „5“.
    """
    from diakronos_app.api import chat as C

    _teilnahme(gespraech, SAENGER2)
    for text in ("a", "b", "c", "d"):
        _senden(text, gespraech, SAENGER)
    _set_user(SAENGER2)
    C.lesestand_setzen(gespraech)
    _session_mod.reset_user()
    _senden("e", gespraech, SAENGER)

    assert _job(_neueste(gespraech) + timedelta(minutes=10)) == 1
    assert _glocken(SAENGER2, gespraech)[0].subject == "Chor: 1 neue Nachricht"


def test_zahl_ignoriert_nachrichten_vor_dem_beirat(welt, gespraech):
    """Wer später dazukommt, bekommt nicht die halbe Geschichte als Zahl."""
    _senden("Vorher 1", gespraech, SAENGER)
    _senden("Vorher 2", gespraech, SAENGER)
    _teilnahme(gespraech, SAENGER2)  # Beitritt jetzt
    _senden("Nachher", gespraech, SAENGER)

    assert _job(_neueste(gespraech) + timedelta(minutes=10)) == 1
    assert _glocken(SAENGER2, gespraech)[0].subject == "Chor: 1 neue Nachricht"


def test_zweiter_lauf_ohne_neue_nachricht_bleibt_billig(welt, gespraech, engine):
    """Review R1 (MUSS 2): Aufwand hängt an den faelligen Paaren, nicht an der Zahl der Gespraeche.

    Aufbau: 12 Gespräche mit Nachrichten und Teilnehmern, alle laengst ausser
    Ruhe und alle schon geglockt. Ein weiterer Lauf darf sie nicht mehr
    „durchzaehlen“ (kein Verlauf, keine Rechte-Frage je Zeile): die Zahl der
    SQL-Abfragen bleibt fest und ist unabhaengig von der Zahl der Gespraeche.
    """
    from sqlalchemy import event

    from diakronos_app.models.chat import ChatGespraech, ChatTeilnehmer

    _teilnahme(gespraech, SAENGER2)
    _senden("Basis", gespraech, SAENGER)
    with dbmod.SessionLocal() as s:
        from diakronos_app.models.diakonos import Gruppe

        for i in range(12):
            name = f"G-last-{i}"
            letzte = datetime(2026, 1, 2, 9, 0)
            # Ein Gespraech je GRUPPE (Unique-Index art+gruppe): echte Einheiten.
            s.add(Gruppe(name=f"Grp-{i}", gruppenname=f"Gruppe {i}"))
            s.add(ChatGespraech(name=name, art="gruppe", gruppe=f"Grp-{i}"))
            s.add(ChatTeilnehmer(gespraech=name, benutzer=SAENGER2, stumm=False,
                                 hinzugefuegt_am=datetime(2026, 1, 1),
                                 letzter_lesestand=letzte,
                                 letzter_lesestand_nachricht=f"N-last-{i}"))
            s.add(ChatNachricht(name=f"N-last-{i}", gespraech=name,
                                autor_benutzer=SAENGER, text="alt",
                                erstellt_am=letzte))
            # Alle 12 sind laengst geglockt (und gelesen) — ein weiterer Lauf
            # hat dort nichts zu tun.
            s.add(ChatGlocke(gespraech=name, benutzer=SAENGER2, merker_am=letzte,
                             geglockt_am=letzte))
        s.commit()

    _senden("Neu", gespraech, SAENGER)
    _senden("Noch neu", gespraech, SAENGER)
    zeit = _neueste(gespraech) + timedelta(minutes=10)
    assert _job(zeit) == 1  # nur das echte Gespräch ist offen

    abfragen: list[int] = [0]

    def _zaehle(*_a, **_k):
        abfragen[0] += 1

    event.listen(engine, "before_cursor_execute", _zaehle)
    try:
        assert _job(zeit + timedelta(minutes=1)) == 0
    finally:
        event.remove(engine, "before_cursor_execute", _zaehle)

    # Feste, kleine Obergrenze: Sitzungssperre, Kandidaten-Abfrage, Abschluss.
    # Mit dem alten N+1-Lauf waeren es > 12 * (Rechte + 3 Abfragen).
    assert abfragen[0] <= 8, f"{abfragen[0]} Abfragen bei 13 Gespraechen"


def test_gelesene_glocke_wird_nicht_fortgeschrieben_sondern_ersetzt(welt, gespraech):
    """Nach dem Lesen ist die nächste Glocke eine NEUE Zeile (Nachweis bleibt)."""
    _teilnahme(gespraech, SAENGER2)
    _senden("Erste", gespraech, SAENGER)
    assert _job(_neueste(gespraech) + timedelta(minutes=10)) == 1
    alte = _glocken(SAENGER2, gespraech)[0]

    from diakronos_app.api import chat as C

    _set_user(SAENGER2)
    C.lesestand_setzen(gespraech)
    _session_mod.reset_user()
    assert _glocken(SAENGER2, gespraech)[0].read is True

    _senden("Neue", gespraech, SAENGER)
    assert _job(_neueste(gespraech) + timedelta(minutes=10)) == 1
    glocken = _glocken(SAENGER2, gespraech)
    assert len(glocken) == 2
    assert {g.read for g in glocken} == {True, False}
    assert any(g.name == alte.name and g.read is True for g in glocken)


# ── Wer bekommt nichts ──────────────────────────────────────────────────────


def test_verfasser_bekommt_keine_glocke(welt, gespraech):
    """Eigene Nachrichten glocken nie — auch nicht, wenn parallel geantwortet wird.

    Achtung Testaufbau: hier schreiben BEIDE (Saenger und Saenger2) etwas, also
    liegt für jede Person genau EINE fremde Nachricht vor. Wer nur die eigene
    Nachricht geschrieben hat, ist der Fall in
    ``test_nur_der_verfasser_schreibt``.
    """
    _teilnahme(gespraech, SAENGER2)
    _senden("Von mir", gespraech, SAENGER)
    _senden("Antwort", gespraech, SAENGER2)

    _job(_neueste(gespraech) + timedelta(minutes=10))

    for konto, erwartet in ((SAENGER, "Chor: 1 neue Nachricht"),
                            (SAENGER2, "Chor: 1 neue Nachricht")):
        glocken = _glocken(konto, gespraech)
        assert len(glocken) == 1
        assert glocken[0].subject == erwartet


def test_nur_der_verfasser_selbst_bekommt_nichts(welt, gespraech):
    """Schreibt nur eine Person, bekommt der VERFASSER nichts — die andere schon.

    Korrigiert im Lauf (Review-Hinweis an mich selbst): hier gibt es für
    Saenger2 genau EINE fremde Nachricht, also MUSS sie eine Glocke bekommen.
    Die Zusage der Karte betrifft ausschließlich den Verfasser.
    """
    _teilnahme(gespraech, SAENGER2)
    _senden("Von mir", gespraech, SAENGER)

    assert _job(_neueste(gespraech) + timedelta(minutes=10)) == 1
    assert _glocken(SAENGER, gespraech) == []                       # Verfasser
    assert len(_glocken(SAENGER2, gespraech)) == 1                  # Teilnehmerin
    assert _glocken(SAENGER2, gespraech)[0].subject == "Chor: 1 neue Nachricht"


def test_stumm_bekommt_keine_glocke_zaehler_bleibt(welt, gespraech):
    """F3/S1: stumm = keine Glocke; der Ungelesen-Zähler bleibt."""
    from diakronos_app.api import chat as C

    _teilnahme(gespraech, SAENGER2)
    _set_user(SAENGER2)
    assert C.stumm_setzen(gespraech, True)["stumm"] is True
    _session_mod.reset_user()

    _senden("Laut", gespraech, SAENGER)
    _job(_neueste(gespraech) + timedelta(minutes=10))

    assert _glocken(SAENGER2, gespraech) == []
    from diakronos_app.api import chat as C2

    _set_user(SAENGER2)
    liste = C2.meine_gespraeche()["gespraeche"]
    _session_mod.reset_user()
    eintrag = next(e for e in liste if e["name"] == gespraech)
    assert eintrag["ungelesen"] == 1
    assert eintrag["stumm"] is True


def test_wer_gelesen_hat_bekommt_keine_glocke(welt, gespraech):
    from diakronos_app.api import chat as C

    _teilnahme(gespraech, SAENGER2)
    _senden("Gelesen", gespraech, SAENGER)

    _set_user(SAENGER2)
    C.lesestand_setzen(gespraech)
    _session_mod.reset_user()

    assert _job(_neueste(gespraech) + timedelta(minutes=10)) == 0
    assert _glocken(SAENGER2, gespraech) == []


def test_rechteentzug_bekommt_keine_glocke(welt, gespraech):
    """Ohne Gruppenmitgliedschaft keine Glocke — entschieden vom Rechte-Kern."""
    _teilnahme(gespraech, SAENGER2)
    _senden("Bleibt", gespraech, SAENGER)

    from diakronos_app.models.diakonos import Gruppenmitgliedschaft

    with dbmod.SessionLocal() as s:
        s.query(Gruppenmitgliedschaft).filter_by(name="gm2").delete()
        s.commit()

    assert _job(_neueste(gespraech) + timedelta(minutes=10)) == 0
    assert _glocken(SAENGER2, gespraech) == []


def test_modul_aus_bekommt_keine_glocke(welt, gespraech):
    _teilnahme(gespraech, SAENGER2)
    _senden("Modul", gespraech, SAENGER)

    with dbmod.SessionLocal() as s:
        s.query(RechteModul).filter_by(gruppe="Chor", modul="chat").delete()
        s.commit()

    assert _job(_neueste(gespraech) + timedelta(minutes=10)) == 0
    assert _glocken(SAENGER2, gespraech) == []


def test_jugend_ohne_modul_bekommt_nichts(welt, gespraech):
    """Gruppe mit Chat-Modul glockt nicht in die Gruppe OHNE Modul."""
    _senden("Chor", gespraech, SAENGER)
    _job(_neueste(gespraech) + timedelta(minutes=10))
    assert _glocken() == []  # niemand sonst ist Teilnehmer des Chor-Gesprächs


# ── Datenschutz und Lesen ───────────────────────────────────────────────────


def test_glocke_enthaelt_weder_text_noch_absender(welt, gespraech):
    _teilnahme(gespraech, SAENGER2)
    _senden("Geheimer Inhalt 4711", gespraech, SAENGER)
    _job(_neueste(gespraech) + timedelta(minutes=10))

    glocke = _glocken(SAENGER2, gespraech)[0]
    zusammen = f"{glocke.subject or ''} {glocke.email_content or ''}"
    assert "4711" not in zusammen
    assert "Geheimer" not in zusammen
    assert SAENGER not in zusammen
    assert "Sa" not in (glocke.subject or "").replace("Nachrichten", "")
    assert glocke.from_user in (None, "")


def test_lesen_markiert_die_glocke_als_gelesen(welt, gespraech):
    from diakronos_app.api import chat as C

    _teilnahme(gespraech, SAENGER2)
    _senden("Ungelesen", gespraech, SAENGER)
    _job(_neueste(gespraech) + timedelta(minutes=10))
    assert _glocken(SAENGER2, gespraech)[0].read is False

    _set_user(SAENGER2)
    C.lesestand_setzen(gespraech)
    _session_mod.reset_user()

    assert _glocken(SAENGER2, gespraech)[0].read is True
    with dbmod.SessionLocal() as s:
        merker = s.get(ChatGlocke, (gespraech, SAENGER2))
        assert merker is not None and merker.gelesen_am is not None


def test_merker_haelt_den_stand_fest(welt, gespraech):
    """Der Merker traegt den Anker (Lesestand beim Glocken) und die neueste Nachricht."""
    _teilnahme(gespraech, SAENGER2)
    _senden("A", gespraech, SAENGER)
    _senden("B", gespraech, SAENGER)
    _job(_neueste(gespraech) + timedelta(minutes=10))

    with dbmod.SessionLocal() as s:
        merker = s.get(ChatGlocke, (gespraech, SAENGER2))
        neueste = s.query(ChatNachricht).filter_by(gespraech=gespraech).order_by(
            ChatNachricht.erstellt_am.desc(), ChatNachricht.name.desc()).first()
        teilnahme = s.get(ChatTeilnehmer, (gespraech, SAENGER2))
        assert merker is not None
        # ``merker_am`` = die neueste Nachricht beim Glocken (kein zweiter
        # Glockenschlag fuer sie), ``stand_am`` = der Anker (Beitritt, weil nie
        # gelesen) — NICHT die Nachricht, bis zu der geglockt wurde.
        assert merker.merker_am == neueste.erstellt_am
        assert merker.stand_am == teilnahme.hinzugefuegt_am
        assert merker.geglockt_am is not None


def test_lesestand_auf_aelterer_nachricht_laesst_die_glocke_offen(welt, gespraech):
    """Review R1 (SOLL d): Lesen BIS ZU EINER aelteren Nachricht schliesst nicht alles.

    Bleibt danach etwas ungelesen, ist die Glocke noch nicht erledigt — sonst
    behauptete sie „gelesen“, obwohl die Oberflaeche weiter ungelesene
    Nachrichten zeigt.
    """
    from diakronos_app.api import chat as C

    _teilnahme(gespraech, SAENGER2)
    erste = _senden("Erste", gespraech, SAENGER)["name"]
    _senden("Zweite", gespraech, SAENGER)
    _senden("Dritte", gespraech, SAENGER)
    _job(_neueste(gespraech) + timedelta(minutes=10))
    assert _glocken(SAENGER2, gespraech)[0].read is False

    _set_user(SAENGER2)
    antwort = C.lesestand_setzen(gespraech, erste)
    _session_mod.reset_user()
    assert antwort["ungelesen"] == 2
    assert _glocken(SAENGER2, gespraech)[0].read is False, "Glocke vorzeitig erledigt"

    # Bis zur neuesten gelesen → jetzt ist sie erledigt.
    _set_user(SAENGER2)
    C.lesestand_setzen(gespraech)
    _session_mod.reset_user()
    assert _glocken(SAENGER2, gespraech)[0].read is True


def test_fehler_bei_einem_paar_kippt_den_lauf_nicht(welt, gespraech, monkeypatch):
    """Review R1 (SOLL b): ein Fehler je (Gespraech, Person) bleibt lokal."""
    from diakronos_app.api import chat as C

    _teilnahme(gespraech, SAENGER2)
    _senden("Einmal", gespraech, SAENGER)

    echt = C._glocke_setzen
    aufrufe: list[str] = []

    def _kaputt(*a, **k):
        aufrufe.append(k.get("konto", ""))
        raise RuntimeError("kaputt")

    monkeypatch.setattr(C, "_glocke_setzen", _kaputt)
    assert C.chat_glocken_buendeln(jetzt=_neueste(gespraech) + timedelta(minutes=10)) == 0
    assert aufrufe == [SAENGER2]           # versucht …
    assert _glocken(SAENGER2, gespraech) == []  # … und sauber zurueckgenommen
    with dbmod.SessionLocal() as s:
        assert s.get(ChatGlocke, (gespraech, SAENGER2)) is None

    # Ohne den Fehler glockt derselbe Aufbau normal.
    monkeypatch.setattr(C, "_glocke_setzen", echt)
    assert C.chat_glocken_buendeln(jetzt=_neueste(gespraech) + timedelta(minutes=10)) == 1


def test_stand_wird_nur_bei_erfolgreicher_glocke_gesetzt(welt, gespraech, monkeypatch):
    """Review R1 (SOLL a): scheitert das Schreiben, bleibt der Merker leer.

    Sonst saehe der naechste Lauf die Nachricht als „schon geglockt“ an — sie
    ginge still verloren.
    """
    from diakronos_app import benachrichtigungen as B
    from diakronos_app.api import chat as C

    _teilnahme(gespraech, SAENGER2)
    _senden("Geht schief", gespraech, SAENGER)

    # Eigener, enger ``monkeypatch``: ``undo()`` auf DEMSELBEN Objekt wuerde
    # auch die Datenbank-Patchung der Fixture zuruecknehmen (der Lauf traefe
    # dann die echte Betriebsdatenbank).
    with pytest.MonkeyPatch.context() as m:
        m.setattr(B, "glocke_setzen", lambda **k: "")
        assert C.chat_glocken_buendeln(
            jetzt=_neueste(gespraech) + timedelta(minutes=10)) == 0
        with dbmod.SessionLocal() as s:
            assert s.get(ChatGlocke, (gespraech, SAENGER2)) is None

    assert C.chat_glocken_buendeln(jetzt=_neueste(gespraech) + timedelta(minutes=11)) == 1
    assert len(_glocken(SAENGER2, gespraech)) == 1


def test_aktualisierte_glocke_rueckt_nach_oben(welt, gespraech):
    """Review R1 (SOLL c): die fortgeschriebene Glocke bekommt ein neues ``modified``."""
    _teilnahme(gespraech, SAENGER2)
    _senden("Erste", gespraech, SAENGER)
    _job(_neueste(gespraech) + timedelta(minutes=10))
    vorher = _glocken(SAENGER2, gespraech)[0].modified

    _senden("Zweite", gespraech, SAENGER)
    _job(_neueste(gespraech) + timedelta(minutes=10))
    glocke = _glocken(SAENGER2, gespraech)
    assert len(glocke) == 1
    assert glocke[0].modified is not None
    if vorher is not None:
        assert glocke[0].modified >= vorher
    # Sortierfeld der Glockenliste: ``creation`` bleibt die Anlage (Nachweis),
    # ``modified`` ist der letzte Anlass.
    assert glocke[0].creation is not None


# ── Scheduler ───────────────────────────────────────────────────────────────


def test_scheduler_registriert_die_glocke_als_minutenjob():
    from diakronos_app import scheduler

    ids = {job_id for _, _, job_id in scheduler.MINUTEN_JOBS}
    assert "chat_glocken_buendeln" in ids
    jobs = {job.id: job for job in scheduler.build_scheduler().get_jobs()}
    assert "chat_glocken_buendeln" in jobs
    assert jobs["chat_glocken_buendeln"].trigger.__class__.__name__ == "IntervalTrigger"


def test_job_wrapper_ruft_die_fachfunktion(welt, monkeypatch):
    from diakronos_app import scheduler
    from diakronos_app.api import chat as C

    aufgerufen: list[int] = []
    monkeypatch.setattr(C, "chat_glocken_buendeln",
                        lambda *a, **k: aufgerufen.append(1) or 0)
    scheduler.job_chat_glocken_buendeln()
    assert aufgerufen == [1]


def test_job_wrapper_schluckt_fehler(monkeypatch):
    from diakronos_app import scheduler
    from diakronos_app.api import chat as C

    def kaputt(*a, **k):
        raise RuntimeError("boom")

    monkeypatch.setattr(C, "chat_glocken_buendeln", kaputt)
    scheduler.job_chat_glocken_buendeln()  # darf nicht werfen


def test_job_ist_kein_http_endpunkt():
    from diakronos_app.frappe_compat.registry import lookup

    assert lookup("diakronos.diakonos.api.chat.chat_glocken_buendeln") is None


# ── Migration ───────────────────────────────────────────────────────────────


def _skripte() -> ScriptDirectory:
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "alembic"))
    return ScriptDirectory.from_config(cfg)


def test_genau_ein_kopf_und_chat4a_haengt_hinter_chat6():
    skripte = _skripte()
    heads = skripte.get_heads()
    assert len(heads) == 1, f"Kopf(e): {heads}"
    revision = skripte.get_revision("chat4a_glocke")
    assert revision is not None
    assert revision.down_revision == "chat5_umfrage", revision.down_revision
    assert "Revises: chat5_umfrage" in Path(revision.path).read_text(encoding="utf-8")


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
        verbindung.exec_driver_sql('DROP TABLE IF EXISTS "chat_glocke"')
    yield eng
    eng.dispose()


def test_migration_upgrade_downgrade_upgrade(fresh_engine):
    import importlib.util

    from sqlalchemy import inspect

    pfad = BACKEND / "alembic" / "versions" / "chat4a_glocke.py"
    spec = importlib.util.spec_from_file_location("chat4a_glocke", pfad)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)

    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    with fresh_engine.begin() as verbindung:
        with Operations.context(MigrationContext.configure(verbindung)):
            modul.upgrade()
        insp = inspect(verbindung)
        assert insp.has_table("chat_glocke")
        spalten = {c["name"] for c in insp.get_columns("chat_glocke")}
        for name in ("gespraech", "benutzer", "stand", "stand_am", "stand_nachricht",
                     "merker_am", "geglockt_am", "gelesen_am"):
            assert name in spalten, name
        assert insp.get_pk_constraint("chat_glocke")["constrained_columns"] == \
            ["gespraech", "benutzer"]
        namen = {i["name"]: i for i in insp.get_indexes("chat_glocke")}
        assert namen["ix_chat_glocke_gespraech"]["column_names"] == ["gespraech"]
        assert namen["ix_chat_glocke_benutzer"]["column_names"] == ["benutzer"]
        ziele = {(fk["constrained_columns"][0], fk["referred_table"])
                 for fk in insp.get_foreign_keys("chat_glocke")}
        assert ("gespraech", "chat_gespraech") in ziele
        assert ("benutzer", "user") in ziele
        assert ("stand", "chat_nachricht") in ziele
        # CHAT-8 loescht Nachrichten: der Merker darf dabei NICHT mitgerissen
        # werden (Review R1/f) — ``stand`` wird genullt, ``stand_am`` bleibt.
        stand_fk = next(fk for fk in insp.get_foreign_keys("chat_glocke")
                        if fk["constrained_columns"] == ["stand"])
        assert stand_fk["options"].get("ondelete", "").upper() == "SET NULL", stand_fk

    # downgrade → weg, zweiter upgrade → wieder da (kein Rest, der stört).
    with fresh_engine.begin() as verbindung:
        with Operations.context(MigrationContext.configure(verbindung)):
            modul.downgrade()
        assert not inspect(verbindung).has_table("chat_glocke")
    with fresh_engine.begin() as verbindung:
        with Operations.context(MigrationContext.configure(verbindung)):
            modul.upgrade()
            modul.upgrade()  # idempotent
        assert inspect(verbindung).has_table("chat_glocke")


def test_inventar_deckt_die_glockentabelle():
    from diakronos_app import dsgvo_anonymisierung as D

    assert {"benutzer", "gespraech", "stand", "stand_nachricht"} <= set(
        D.SPALTEN["chat_glocke"])
    assert D.SPALTEN["chat_glocke"]["benutzer"][0] == "zeile_loeschen"
    loeschzeilen = {name for name, _ in D.ZEILEN_LOESCHEN}
    assert "chat_glocke" in loeschzeilen
    assert "chat_glocke" in D.KONTO_ZEILEN
