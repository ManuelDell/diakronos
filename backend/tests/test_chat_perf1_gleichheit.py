"""CHAT-PERF-1, Review R1: der Sammelweg muss dem ALTEN Code gleichen.

Drei Befunde der Review (Opus) sind hier als Test festgenagelt — die Antwort
darf auch bei Daten gleich bleiben, die der App-Code heute nicht erzeugt:

  1. ZWEI Mitglieder an EINEM Login (geteilter Haushalts-Login). ``Mitglied.user``
     ist nicht eindeutig; ``_runde_mitglieder`` verbindet darueber und zeigt
     BEIDE. Der Sammellauf darf keines der beiden verschlucken.
  2. ``sichtbar_ab`` gilt NUR in Runden und NUR fuer die Vorschau
     (``_letzte_nachricht``); ``_ungelesen_zaehlen`` kennt die Grenze gar nicht.
     Eine Grenze auf Gruppe/1:1 oder im Zaehler waere eine stille Verhaltens-
     Aenderung.
  3. Die Teilnehmerzahl einer GRUPPE/1:1 zaehlt ALLE Teilnahmezeilen
     (``_teilnahme_konten`` kennt keinen ``verlassen_am``-Filter), die einer
     RUNDE nur die aktiven.

Der vierte Punkt ist die Gleichheitsprobe: der EINZELWEG (``_gespraech_kopf``
ohne ``daten`` — dieselben Bausteine wie vor dem Umbau) gegen den SAMMELWEG
(``_kopfdaten_sammeln``) ueber viele zufaellige Welten mit festem Seed,
inklusive der inkonsistenten Daten aus 1–3.

Aufruf (Karte):
    docker run --rm --network none --entrypoint python -v <wt>:/repo:ro \\
      -w /repo/backend -e PYTHONPATH=/repo/backend/src:/repo/backend/tests:/repo/tools \\
      -e PYTHONDONTWRITEBYTECODE=1 <vorbau> -m pytest -q -p no:cacheprovider \\
      tests/test_chat_perf1_gleichheit.py
"""

from __future__ import annotations

import json
import random
from datetime import datetime, timedelta

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

#: Dieselbe Personenwelt wie ``test_chat7b_runden``/``test_chat_perf1_liste``.
from test_chat7b_runden import (  # noqa: E402,F401
    ANNA,
    BERT,
    CLARA,
    DIETER,
    EMMA,
    FRIDA,
    HV,
    MI,
    _set_user,
    welt,
)

T0 = datetime(2026, 11, 20, 12, 0, 0)


# ── Hilfen ──────────────────────────────────────────────────────────────────


def _gruppe(s, name: str, *, mitglieder=(), modul: bool = True) -> None:
    s.add(Gruppe(name=name))
    for konto in mitglieder:
        s.add(Gruppenmitgliedschaft(
            name=f"gm-{name}-{MI[konto]}", parent=name, parenttype="Gruppe",
            parentfield="mitglieder", mitglied=MI[konto]))
    if modul:
        s.add(RechteModul(gruppe=name, modul="chat"))


def _kopfpaare() -> tuple[dict[str, dict], dict[str, dict]]:
    """``({gespraech: einzelkopf}, {gespraech: sammelkopf})`` ueber ALLE Arten.

    Der Einzelweg ist der alte Rechenweg: ``_gespraech_kopf`` ohne ``daten``
    liest jede Frage einzeln ueber ``_ungelesen_zaehlen``, ``_letzte_nachricht``,
    ``_teilnehmer_aktuelle`` und ``_runde_mitglieder``. Der Sammelweg ist der
    neue: ``_kopfdaten_sammeln`` + derselbe Kopf. Beide werden aus DEMSELBEN
    Bestand gebaut — verglichen wird also nur der Rechenweg.

    ``_set_user(ANNA)`` ist PFLICHT: ``_lesbare_gespraeche`` holt die
    Gruppen/Untergruppen ueber ``_meine_kennung()`` aus der SITZUNG — ohne
    angemeldete Person kaeme keine einzige Gruppe vor und der Vergleich waere
    blind fuer genau die Arten, deren Grenzen er pruefen soll (Review R1).
    """
    from diakronos_app import rechte as R
    from diakronos_app.api import chat as C
    import diakronos_app.db as dbmod

    _set_user(ANNA)
    with dbmod.SessionLocal() as s:
        alle = (C._lesbare_gespraeche(s, ANNA)
                + C._direkt_gespraeche(s, ANNA)
                + C._runde_gespraeche(s, ANNA))
        # Je Zeile EINMAL ``darf`` fragen — ob die Antwort cacht, ist Sache
        # des Kerns (``rollen_vorladen``), hier zaehlt nur das Ergebnis.
        gespraeche = [g for g in alle
                      if g.name is None or C._darf_lesen(s, ANNA, g.name)]
        einzeln = []
        for g in gespraeche:
            R.merker_leeren()
            with R.merkungsrahmen():
                einzeln.append((g.name or f"nie:{g.gruppe}:{g.untergruppe}",
                                C._gespraech_kopf(s, g, ANNA)))
        daten = C._kopfdaten_sammeln(s, gespraeche, ANNA)
        gesammelt = []
        for g in gespraeche:
            gesammelt.append((g.name or f"nie:{g.gruppe}:{g.untergruppe}",
                              C._gespraech_kopf(s, g, ANNA, daten=daten)))
    return dict(einzeln), dict(gesammelt)


def _json(wert) -> str:
    return json.dumps(wert, ensure_ascii=False, indent=1, sort_keys=False)


# ── 1) Zwei Mitglieder an einem Login ───────────────────────────────────────


@pytest.fixture()
def doppelkonto(welt, patched_db, engine):
    """Runde mit Anna, Bert — und ZWEI Mitgliedern am Konto ``BERT``.

    ``Mitglied.user`` ist nicht eindeutig (geteilter Haushalts-Login).
    ``_runde_mitglieder`` verbindet ueber genau diese Spalte und zeigt beide.
    Das zweite Mitglied entsteht ueber das Modell und bekommt das Konto
    anschliessend per ``UPDATE`` (das Modell kennt keine Sperre auf ``user``;
    die Doppelbelegung ist ein Altbestand, den die Leser trotzdem richtig
    behandeln muessen).
    """
    s = patched_db()
    s.add(Mitglied(name="M-99-Doppel", vorname="Doppel", nachname="Dorn",
                   email=None, user=BERT, status="Aktiv", idx=99))
    s.flush()
    s.execute(__import__("sqlalchemy").text(
        "UPDATE mitglied SET user = :konto WHERE name = 'M-99-Doppel'"),
        {"konto": BERT})
    r = ChatGespraech(name="chat-r-doppel", art=ART_RUNDE, titel="Doppelt",
                      angelegt_am=T0)
    s.add(r)
    for konto in (ANNA, BERT):
        s.add(ChatTeilnehmer(gespraech=r.name, benutzer=konto, stumm=False,
                             hinzugefuegt_am=T0, sichtbar_ab=T0))
    s.commit()
    yield s
    s.rollback()


def test_doppeltes_konto_zeigt_beide_mitglieder(doppelkonto):
    """``mitglieder`` nennt BEIDE Mitglieder des Kontos — wie ``_runde_mitglieder``."""
    from diakronos_app.api import chat as C
    import diakronos_app.db as dbmod

    with dbmod.SessionLocal() as s:
        r = s.get(ChatGespraech, "chat-r-doppel")
        gespraeche = [g for g in C._runde_gespraeche(s, ANNA)
                      if g.name == r.name]
        daten = C._kopfdaten_sammeln(s, gespraeche, ANNA)
        kopf = C._gespraech_kopf(s, r, ANNA, daten=daten)
        einzeln = C._gespraech_kopf(s, r, ANNA)

    # BEIDE Mitglieder des Kontos BERT stehen drin — keines faellt weg.
    # (Anna traegt eine eigene Teilnahmezeile, sie steht mit drin.)
    kennungen = [m["mitglied"] for m in kopf["mitglieder"]]
    assert kennungen == [MI[ANNA], MI[BERT], "M-99-Doppel"], kennungen
    # Der Einzelweg sagt dasselbe (Bit-Gleichheit, nicht "fast").
    assert _json(kopf["mitglieder"]) == _json(einzeln["mitglieder"]), (
        kopf["mitglieder"], einzeln["mitglieder"])
    assert kopf["teilnehmer"] == 2
    # Und die alte Funktion selbst zeigt dieselben Kennungen (auch wenn ihre
    # REIHENFOLGE bei zwei Mitgliedern an einem Login unbestimmt ist: dort
    # entscheidet nur der Name, und der ist hier verschieden).
    assert {m["mitglied"] for m in kopf["mitglieder"]} == {
        m["mitglied"] for m in C._runde_mitglieder(s, r.name)}


# ── 2) sichtbar_ab: nur Runden, nur Vorschau ────────────────────────────────


@pytest.fixture()
def grenzen(welt, patched_db):
    """Inkonsistente Daten, die der App-Code heute nicht erzeugt.

    * ``sichtbar_ab`` auf einer GRUPPE (darf nichts filtern),
    * ``sichtbar_ab`` auf einem 1:1 (darf nichts filtern),
    * ``sichtbar_ab`` > ``hinzugefuegt_am`` in einer RUNDE (Vorschau leer,
      Zaehler unberuehrt — der Zaehler kennt die Grenze nicht),
    * ``verlassen_am`` auf einer Nicht-Runden-Zeile (zaehlt weiter mit).
    """
    s = patched_db()
    spaeter = T0 + timedelta(hours=3)

    # Gruppe mit sichtbar_ab: Nachricht VOR der Grenze bleibt sichtbar/zaehlbar.
    _gruppe(s, "Grenze-Gruppe", mitglieder=[ANNA, BERT])
    g = ChatGespraech(name="chat-g-grenze", art=ART_GRUPPE,
                      gruppe="Grenze-Gruppe", angelegt_am=T0)
    s.add(g)
    s.add(ChatTeilnehmer(gespraech=g.name, benutzer=ANNA, stumm=False,
                         hinzugefuegt_am=T0, sichtbar_ab=spaeter))
    s.add(ChatNachricht(name="n-gg-1", gespraech=g.name, autor=MI[BERT],
                        autor_benutzer=BERT, text="vor der Grenze",
                        erstellt_am=T0 + timedelta(minutes=5)))

    # 1:1 mit sichtbar_ab: dieselbe Antwort.
    d = ChatGespraech(name="chat-d-grenze", art=ART_DIREKT,
                      paar_schluessel="\x1f".join(sorted([ANNA, BERT])),
                      angelegt_am=T0)
    s.add(d)
    s.add_all([
        ChatTeilnehmer(gespraech=d.name, benutzer=ANNA, stumm=False,
                       hinzugefuegt_am=T0, sichtbar_ab=spaeter),
        ChatTeilnehmer(gespraech=d.name, benutzer=BERT, stumm=False,
                       hinzugefuegt_am=T0),
    ])
    s.add(ChatNachricht(name="n-dg-1", gespraech=d.name, autor=MI[BERT],
                        autor_benutzer=BERT, text="vor der Grenze 1:1",
                        erstellt_am=T0 + timedelta(minutes=6)))

    # Runde: sichtbar_ab NACH dem Eintritt → Vorschau leer, Zaehler bleibt.
    r = ChatGespraech(name="chat-r-grenze", art=ART_RUNDE, titel="Spaet",
                      angelegt_am=T0)
    s.add(r)
    s.add_all([
        ChatTeilnehmer(gespraech=r.name, benutzer=ANNA, stumm=False,
                       hinzugefuegt_am=T0, sichtbar_ab=spaeter),
        ChatTeilnehmer(gespraech=r.name, benutzer=BERT, stumm=False,
                       hinzugefuegt_am=T0, sichtbar_ab=T0),
    ])
    s.add(ChatNachricht(name="n-rg-1", gespraech=r.name, autor=MI[BERT],
                        autor_benutzer=BERT, text="vor der Grenze Runde",
                        erstellt_am=T0 + timedelta(minutes=7)))

    # Gruppe mit verlassen_am: die Zahl zaehlt weiter (alter Code ohne Filter).
    _gruppe(s, "Grenze-Exit", mitglieder=[ANNA, BERT])
    ge = ChatGespraech(name="chat-g-exit", art=ART_GRUPPE,
                       gruppe="Grenze-Exit", angelegt_am=T0)
    s.add(ge)
    s.add(ChatTeilnehmer(gespraech=ge.name, benutzer=ANNA, stumm=False,
                         hinzugefuegt_am=T0))
    s.add(ChatTeilnehmer(gespraech=ge.name, benutzer=BERT, stumm=False,
                         hinzugefuegt_am=T0,
                         verlassen_am=T0 + timedelta(hours=1)))
    s.commit()
    yield s
    s.rollback()


def test_sichtbar_ab_nur_runde_nur_vorschau(grenzen):
    """``sichtbar_ab`` filtert NUR die Vorschau einer RUNDE (alter Code)."""
    from diakronos_app import rechte as R
    from diakronos_app.api import chat as C
    import diakronos_app.db as dbmod

    _set_user(ANNA)
    with dbmod.SessionLocal() as s:
        R.merker_leeren()
        with R.merkungsrahmen():
            gespraeche = (C._lesbare_gespraeche(s, ANNA)
                          + C._direkt_gespraeche(s, ANNA)
                          + C._runde_gespraeche(s, ANNA))
        daten = C._kopfdaten_sammeln(s, gespraeche, ANNA)
        gesammelt = {}
        einzeln = {}
        for g in gespraeche:
            schluessel = g.name or f"nie:{g.gruppe}:{g.untergruppe}"
            gesammelt[schluessel] = C._gespraech_kopf(s, g, ANNA, daten=daten)
            einzeln[schluessel] = C._gespraech_kopf(s, g, ANNA)
    assert sorted(gesammelt) == sorted(einzeln), sorted(gesammelt)

    # Gruppe: Grenze zaehlt nicht → Nachricht ist Vorschau und ungelesen.
    assert gesammelt["chat-g-grenze"]["letzte_nachricht"] == "vor der Grenze"
    assert gesammelt["chat-g-grenze"]["ungelesen"] == 1
    # 1:1: dasselbe.
    assert gesammelt["chat-d-grenze"]["letzte_nachricht"] == "vor der Grenze 1:1"
    assert gesammelt["chat-d-grenze"]["ungelesen"] == 1
    # Runde: Vorschau leer (hinter der Grenze), Zaehler unberuehrt.
    assert gesammelt["chat-r-grenze"]["letzte_nachricht"] is None
    assert gesammelt["chat-r-grenze"]["letzte_am"] is None
    assert gesammelt["chat-r-grenze"]["ungelesen"] == 1

    # Und beides gleich dem Einzelweg (dem alten Rechenweg).
    for schluessel in ("chat-g-grenze", "chat-d-grenze", "chat-r-grenze"):
        assert _json(gesammelt[schluessel]) == _json(einzeln[schluessel]), schluessel

    # Gegenprobe am Einzelweg selbst: der Zaehler kennt die Grenze nicht.
    with dbmod.SessionLocal() as s:
        g = s.get(ChatGespraech, "chat-r-grenze")
        assert C._ungelesen_zaehlen(
            s, g.name, ANNA, s.get(ChatTeilnehmer, (g.name, ANNA))) == 1


def test_verlassen_am_zaehlt_in_gruppe_weiter(grenzen):
    """Gruppe/1:1 zaehlen ALLE Teilnahmezeilen — Austritt aendert die Zahl nicht."""
    from diakronos_app import rechte as R
    from diakronos_app.api import chat as C
    import diakronos_app.db as dbmod

    _set_user(ANNA)
    with dbmod.SessionLocal() as s:
        R.merker_leeren()
        with R.merkungsrahmen():
            gespraeche = [g for g in C._lesbare_gespraeche(s, ANNA)
                          if g.gruppe == "Grenze-Exit"] \
                + [g for g in C._direkt_gespraeche(s, ANNA)] \
                + [g for g in C._runde_gespraeche(s, ANNA)]
        daten = C._kopfdaten_sammeln(s, gespraeche, ANNA)
        sammel = {g.name: C._gespraech_kopf(s, g, ANNA, daten=daten)
                  for g in gespraeche if g.name}
        einzeln = {g.name: C._gespraech_kopf(s, g, ANNA)
                   for g in gespraeche if g.name}
    assert sammel["chat-g-exit"]["teilnehmer"] == 2
    for schluessel in sorted(sammel):
        assert _json(sammel[schluessel]) == _json(einzeln[schluessel]), schluessel


# ── 4) Gleichheitsprobe: Sammelweg gegen Einzelweg, viele Welten ────────────


#: Welten fuer die Zufallsprobe. Fester Seed, damit ein Fehlschlag wiederholbar
#: ist: die BESTANDSZAHLEN waechst nicht mit, jeder Lauf baut dieselben 50.
WELTEN = 50

#: Praefix der Nachricht, die als Lesestand-Anker dient (``lesestand_echt``):
#: ein FESTER Anfang, damit die Teilnahmezeile ihn nennen kann, bevor die
#: Nachrichten gewuerfelt sind — gefolgt von der Gespraechskennung (Namen sind
#: primaer). In jeder Welt mit ``lesestand_echt`` traegt jedes Gespraech genau
#: diese Nachricht; sie liegt zeitlich genau auf dem Lesestand, sodass die
#: Kennung entscheidet (``>`` gegen ``>=``).
LESESTAND_ECHT = "zz-anker"


def _anker(gespraech: str) -> str:
    return f"{LESESTAND_ECHT}:{gespraech}"


def _wuerfle_welt(s, rnd: random.Random, nummer: int) -> None:
    """Eine zufaellige, absichtlich INKONSISTENTE Welt (R1 1–3 inklusive).

    Je Gespraech hoechstens ZWEI Teilnahmezeilen — und hoechstens EINE davon
    fuer Anna. ``ChatTeilnehmer`` ist (gespraech, benutzer) — zwei Zeilen
    desselben Kontos im selben Gespraech gibt es nicht; zwei Zeilen fuer ANNA
    gaebe es in der App also nie.

    ``sichtbar_ab`` steht AUCH dort, wo sie nichts zu suchen hat (Gruppe,
    1:1), oft hinter dem Eintritt (``sichtbar_ab > hinzugefuegt_am``), und
    ``verlassen_am`` auch auf einer Nicht-Runden-Zeile.

    JEDE Welt traegt mindestens eine RUNDE: die zweite Runde wird ohne Wurf
    angehaengt, wenn der Wurf keine ergab. Ohne Runde prueft die Gleichheits-
    probe die Runden-Regeln (``sichtbar_ab``, ``verlassen_am``) nicht — das
    war der Befund der Review R1. Der Zusatz steht am ENDE, damit die
    gewuerfelten Gespraeche der uebrigen Welten unveraendert bleiben.
    """
    _wuerfle_gespraeche(s, rnd, nummer)
    if not any(isinstance(o, ChatGespraech) and o.art == ART_RUNDE
               for o in s.new):
        # Kein Wurf-Ergebnis: eine Runde mehr, mit denselben Zutaten.
        _wuerfle_gespraech(s, rnd, nummer, len(s.new), ART_RUNDE, {},
                           erzwungene_runde=True)
    # DOPPELTES KONTO (R1 1): in etwa der HAELFTE der Welten traegt BERTs Login
    # ein ZWEITES Mitglied. ``mitglied.user`` ist NICHT eindeutig — es gibt nur
    # ``uq_mitglied_email_normalisiert``, und dieses Mitglied bleibt ohne
    # Adresse (``email=None``), also kollidiert der Index nicht. Die Runde
    # zeigt deshalb BEIDE Namen; wer nur "das erste Mitglied je Konto" nimmt,
    # faellt hier auf.
    #
    # Damit die Probe das auch SIEHT, bekommt eine Runde dieser Welt eine
    # Teilnahmezeile fuer BERT: das doppelte Konto wirkt nur, wo es eine Zeile
    # gibt (``_mitglieder_je_konto`` fragt ueber die Konten der Zeilen).
    if nummer % 2:
        s.add(Mitglied(name=f"M-99-Doppel-{nummer}", vorname="Doppel",
                       nachname=f"Dorn {nummer}", email=None, user=BERT,
                       status="Aktiv", idx=99))
        runden = [o for o in s.new
                  if isinstance(o, ChatGespraech) and o.art == ART_RUNDE]
        if runden:
            ziel = runden[0].name
            if not any(isinstance(o, ChatTeilnehmer)
                       and o.gespraech == ziel and o.benutzer == BERT
                       for o in s.new):
                s.add(ChatTeilnehmer(
                    gespraech=ziel, benutzer=BERT, stumm=False,
                    hinzugefuegt_am=T0 + timedelta(minutes=5)))


def _wuerfle_gespraeche(s, rnd: random.Random, nummer: int) -> None:
    """Die 2–5 gewuerfelten Gespraeche einer Welt."""
    paare: dict[str, str] = {}
    for i in range(rnd.randint(2, 5)):
        # ``None`` = der Wurf waehlt die Art; die ERZWUNGENE Runde gibt sie vor.
        _wuerfle_gespraech(s, rnd, nummer, i, None, paare)


def _wuerfle_gespraech(s, rnd: random.Random, nummer: int, i: int,
                       art: str | None, paare: dict[str, str],
                       erzwungene_runde: bool = False) -> None:
    """EIN Gespraech samt Teilnahmezeilen, Nachrichten und Vorschlaegen.

    ``paare`` ist der gemeinsame Stand der WELT: je Personenpaar gibt es genau
    EIN 1:1-Gespraech (``uq_chat_gespraech_paar``) — der Wurf muss das ueber
    alle Gespraeche einer Welt hinweg wissen.
    """
    andere = [BERT, CLARA, DIETER, EMMA, FRIDA]
    zaehler = {"g": 0, "d": 0, "r": 0, "n": 0, "v": 0}

    def kennung(art: str) -> str:
        zaehler[art] += 1
        # Der Zaehler laeuft PRO GESPRAECH — die Kennung braucht deshalb auch
        # den Lauf ``i``, sonst kollidiert sie mit dem ersten Gespraech.
        return f"w{nummer}-{i}-{art}-{zaehler[art]:03d}"

    def zeit() -> datetime:
        return T0 + timedelta(minutes=rnd.randint(0, 600))

    if art is None:
        art = rnd.choice([ART_GRUPPE, ART_UNTERGRUPPE, ART_DIREKT, ART_RUNDE])
    weitere = rnd.sample(andere, rnd.randint(0, 1))
    if art == ART_DIREKT:
        a, b = ANNA, weitere[0] if weitere else rnd.choice(andere)
        schluessel = "\x1f".join(sorted([a, b]))
        if schluessel in paare:
            # Dieses Paar hat sein 1:1 schon — die Runde ist der Ersatz.
            art = ART_RUNDE
        else:
            paare[schluessel] = kennung("d")
            g = ChatGespraech(name=paare[schluessel], art=ART_DIREKT,
                              paar_schluessel=schluessel, angelegt_am=T0)
    if art == ART_RUNDE:
        # Die ERZWUNGENE Runde (Welt ohne gewuerfelte Runde) braucht eine
        # zweite Person: allein traegt sie keinen Namen in der Liste, und dann
        # waere die Runden-Regel der Probe wiederum ungeprueft.
        weitere = weitere or [rnd.choice(andere)]
        g = ChatGespraech(name=kennung("r"), art=ART_RUNDE,
                          titel=f"Runde {nummer}-{i}", angelegt_am=T0)
    elif art != ART_DIREKT:
        name = f"W{nummer}-{i}"
        s.add(Untergruppe(name=name + "-u", gruppe=name,
                          untergruppenname=name + " U"))
        _gruppe(s, name, mitglieder=[ANNA] + (weitere or []))
        if art == ART_UNTERGRUPPE:
            s.add(Untergruppenmitgliedschaft(
                name=f"ugm-{name}", parent=name + "-u", parenttype="Untergruppe",
                parentfield="mitglieder", mitglied=MI[ANNA]))
            g = ChatGespraech(name=kennung("g"), art=ART_UNTERGRUPPE,
                              gruppe=name, untergruppe=name + "-u",
                              angelegt_am=T0)
        else:
            g = ChatGespraech(name=kennung("g"), art=ART_GRUPPE,
                              gruppe=name, angelegt_am=T0)
        if rnd.random() < 0.2:
            g.geloescht_am = T0 + timedelta(days=1)
    s.add(g)

    # Teilnahmezeilen — mit JEDEM Zustand, den der Zaehler/die Grenzen
    # unterscheiden: Lesestand (+Kennung), Beitritt, Austritt,
    # sichtbar_ab (auch dort, wo sie nichts zu suchen hat: Gruppe/1:1).
    # Die Kennung des Lesestands IST in einem Teil der Welten eine ECHTE
    # Nachricht dieses Gespraechs (``lesestand_echt``) — nur dann
    # entscheidet ``letzter_lesestand_nachricht`` wirklich ueber ``>``
    # gegen ``>=``; eine erfundene Kennung traefe nie eine Zeile und die
    # Stelle bliebe ungeprueft.
    lesestand = None
    # In jeder Welt mit ``lesestand_echt`` nennt der Lesestand eine ECHTE
    # Nachricht dieses Gespraechs. Die Wahl ist bewusst NICHT gewuerfelt: eine
    # Stelle, die nur in 1 von 50 Welten entscheidet, bewacht den ``>`` gegen
    # ``>=``-Vergleich praktisch nicht (Review R1, Punkt 4).
    lesestand_echt = rnd.random() < 0.5
    # Die ERZWUNGENE Runde ist der einzige Rundenkopf dieser Welt: ihre
    # Teilnahmezeilen bleiben darum AKTIV (``_runde_gespraeche`` zeigt nur
    # aktive Zeilen) — sonst faellt der einzige Rundenkopf aus der Liste und
    # die Probe prueft die Runden-Regeln dieser Welt wieder nicht.
    erzwungen = erzwungene_runde and g.art == ART_RUNDE
    # In einer RUNDE ist ANNAs Zeile immer AKTIV: ``_teilnehmer_konten``
    # reicht dem Rechte-Kern nur Zeilen ohne ``verlassen_am``, eine
    # ausgetretene Anna koennte die Runde also gar nicht lesen — und sie
    # stuende nicht in der Liste. Die uebrigen Zeilen duerfen ausgetreten sein.
    #
    # In jeder ERZWUNGENEN Runde tritt die zweite Person aus (falls die
    # gewuerfelten Zeilen das nicht schon tun): ohne Austritt in einer Runde,
    # die Anna SIEHT, waere die Regel "Runde zaehlt nur aktive Zeilen" in
    # dieser Welt ungeprueft (Review R1, Punkt 3d).
    _staende: dict[str, datetime] = {}
    for konto in [ANNA] + weitere:
        hat_stand = rnd.random() < 0.5
        stand = zeit() if hat_stand else None
        beitritt = zeit()
        verlassen = None if (erzwungen or (g.art == ART_RUNDE
                                           and konto == ANNA)) else (
            zeit() if rnd.random() < 0.2 else None)
        if erzwungen and konto != ANNA:
            verlassen = T0 + timedelta(hours=2)
        s.add(ChatTeilnehmer(
            gespraech=g.name, benutzer=konto,
            stumm=rnd.random() < 0.3, hinzugefuegt_am=beitritt,
            sichtbar_ab=(zeit() if rnd.random() < 0.5 else None),
            verlassen_am=verlassen,
            letzter_lesestand=stand,
            letzter_lesestand_nachricht=(
                _anker(g.name) if hat_stand and lesestand_echt
                else (kennung("n")
                      if hat_stand and rnd.random() < 0.2
                      else None))))
        if stand is not None:
            _staende[konto] = stand
        if konto == ANNA:
            lesestand = stand

    # Nachrichten: eigene, fremde, anonymisierte, geloeschte, doppelte
    # Zeitstempel — und Vorschlagszeilen (offen/beendet, eigen/fremd).
    # Je (Gespraech, Mitglied) gibt es hoechstens EINEN Vorschlag
    # (``UniqueConstraint``); die Systemzeilen schliessen daran an.
    vorgeschlagen: set[str] = set()
    # Der Lesestand-Anker (``lesestand_echt``): eine ECHTE Nachricht dieses
    # Gespraechs, genau auf dem Lesestand der Person — Konto ANNA, damit
    # sie fuer Anna nicht schon durch ``_nicht_von`` herausfaellt und die
    # Kennung wirklich entscheidet.
    if lesestand_echt and lesestand is not None:
        s.add(ChatNachricht(
            name=_anker(g.name), gespraech=g.name,
            autor=MI[ANNA], autor_benutzer=ANNA, text="Anker",
            erstellt_am=lesestand))
    # Zeitstempel, die GENAU auf einem Lesestand liegen: nur dort entscheidet
    # die Kennung (``letzter_lesestand_nachricht``) — und damit der Vergleich
    # ``>=`` gegen ``>``. Ohne diesen Vorrat trifft der ``>``-Zweig fast nie
    # eine Zeile und die Stelle bleibt ungeprueft (Review R1, Punkt 4).
    auf_stand = sorted({stand for stand in _staende.values()})
    for _ in range(rnd.randint(1, 5)):
        von = rnd.choice([ANNA, BERT, CLARA, None])
        s.add(ChatNachricht(
            name=kennung("n"), gespraech=g.name,
            autor=MI[von] if von else None, autor_benutzer=von,
            text=f"Zeile {nummer}",
            erstellt_am=(rnd.choice(auf_stand) if auf_stand and rnd.random() < 0.6
                         else (lesestand + timedelta(seconds=rnd.randint(0, 40))
                               if lesestand is not None and rnd.random() < 0.2
                               else zeit())),
            geloescht_am=(zeit() if rnd.random() < 0.15 else None)))
        ziel = rnd.choice(andere)
        # In einer RUNDE hoert jede Vorschlags-Systemzeile auf einen
        # Zaehler (``UniqueConstraint``) — ausserhalb gibt es keine
        # Vorschlaege.
        if (g.art == ART_RUNDE and rnd.random() < 0.3
                and ziel not in vorgeschlagen):
            vorgeschlagen.add(ziel)
            v = ChatRundeVorschlag(
                name=kennung("v"), gespraech=g.name,
                mitglied=MI[ziel],
                vorgeschlagen_von=von,
                angelegt_am=zeit(),
                stand=rnd.choice([VORSCHLAG_OFFEN, VORSCHLAG_BEENDET]),
                entschieden_am=(zeit() if rnd.random() < 0.5 else None))
            s.add(v)
            # Ihre Systemzeile traegt die Kennung des Vorschlags; ob sie als
            # ``vorschlag`` verknuepft ist, schwankt (wie in Altdaten).
            s.add(ChatNachricht(
                name=kennung("n"), gespraech=g.name, autor=None,
                autor_benutzer=None,
                vorschlag=(v.name if rnd.random() < 0.6 else None),
                text="",
                erstellt_am=zeit()))


@pytest.mark.parametrize("nummer", range(WELTEN))
def test_sammelweg_gleich_einzelweg(welt, patched_db, tmp_path, nummer):
    """Zufallswelt ``nummer``: Sammelweg und Einzelweg liefern DENSELBEN Kopf.

    Der Einzelweg ist der ALTE Rechenweg (``_gespraech_kopf`` ohne ``daten``:
    ``_ungelesen_zaehlen``, ``_letzte_nachricht``, ``_teilnehmer_aktuelle``,
    ``_runde_mitglieder`` je Gespraech). Der Sammelweg ist der neue. Verglichen
    wird der ganze Kopf als Text — je Feld, in IHRER Reihenfolge.
    """
    s = patched_db()
    _wuerfle_welt(s, random.Random(nummer), nummer)
    s.commit()
    try:
        einzeln, gesammelt = _kopfpaare()
        # Die Probe darf nicht wieder BLIND werden: kommen in einer Welt keine
        # Runden vor, prueft sie die Runden-Regeln nicht. Deshalb muss jede
        # Welt mindestens einen Rundenkopf tragen (der Wurf wuerfelt je Welt
        # 2–5 Gespraeche und macht die Runde zum Ersatz fuer ein doppeltes
        # Paar; ohne Runde waere die Welt fuer die Mutationsprobe wertlos).
        assert any(k["art"] == ART_RUNDE for k in einzeln.values()), (
            f"Welt {nummer}: kein Rundenkopf — die Probe waere blind")
        # Die Gegenprobe schreibt ihre Abweichung als Datei: pytest kuerzt
        # Assertion-Texte, ein Diff ueber 11 Felder soll vollstaendig lesbar
        # sein (``tmp_path``, damit nichts in /tmp liegen bleibt).
        abweichungen = [
            (schluessel, gesammelt[schluessel], einzeln[schluessel])
            for schluessel in sorted(einzeln)
            if _json(gesammelt[schluessel]) != _json(einzeln[schluessel])]
        if abweichungen:
            text = _diff_datei(tmp_path, abweichungen, s)
            (tmp_path / "perf1-abweichung.txt").write_text(text, encoding="utf-8")
            assert False, text
    finally:
        s.rollback()


def _diff_datei(tmp_path, abweichungen, s) -> str:
    """Die Abweichungen als Text — ``Sammelweg`` gegen ``Einzelweg``, je Feld.

    Dazu die Datenlage des Gespraechs (Teilnahme, Nachrichten, Vorschlaege) —
    ohne sie ist ein Unterschied zwischen zwei Rechenwegen nicht zu deuten.
    """
    from sqlalchemy import select

    zeilen = [f"{len(abweichungen)} Gespraech(e) verschieden"]
    for schluessel, neu, alt in abweichungen:
        zeilen.append(f"\n=== {schluessel} ===")
        for feld in alt if isinstance(alt, dict) else ():
            if _json(neu.get(feld)) != _json(alt.get(feld)):
                zeilen.append(f"  {feld}:\n    sammel: {_json(neu.get(feld))}"
                              f"\n    einzeln: {_json(alt.get(feld))}")
        g = s.get(ChatGespraech, schluessel)
        if g is None:
            continue
        zeilen.append(f"  art={g.art} geloescht={g.geloescht_am}")
        for t in s.execute(select(ChatTeilnehmer).where(
                ChatTeilnehmer.gespraech == schluessel)).scalars():
            zeilen.append(f"  teilnehmer {t.benutzer}: beitritt={t.hinzugefuegt_am} "
                          f"sichtbar_ab={t.sichtbar_ab} "
                          f"verlassen={t.verlassen_am} "
                          f"lesestand={t.letzter_lesestand}/"
                          f"{t.letzter_lesestand_nachricht}")
        for n in s.execute(select(ChatNachricht).where(
                ChatNachricht.gespraech == schluessel).order_by(
                ChatNachricht.erstellt_am)).scalars():
            zeilen.append(f"  nachricht {n.name}: {n.erstellt_am} "
                          f"von={n.autor_benutzer} vorschlag={n.vorschlag} "
                          f"geloescht={n.geloescht_am}")
        for v in s.execute(select(ChatRundeVorschlag).where(
                ChatRundeVorschlag.gespraech == schluessel)).scalars():
            zeilen.append(f"  vorschlag {v.name}: von={v.vorgeschlagen_von} "
                          f"mitglied={v.mitglied} stand={v.stand}")
    return "\n".join(zeilen)
