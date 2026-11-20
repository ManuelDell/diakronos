"""CHAT-8 — Chat-Aufbewahrung: Fristen, Loeschlauf, Einstellungen (F8).

Konzept ``docs/konzepte/CHAT-KONZEPT.md`` 4.2 (Tabelle Fristen), 4.3 und
Entscheidung **F8**: Fristen PRO GEMEINDE einstellbar (Standard 24 Monate
Gruppe / 12 Monate Direkt), Loeschung automatisch.

Geprueft wird gegen den ECHTEN Lauf (``chat_aufbewahrung.aufraeumen``), die
ECHTEN Endpunkte (``api.chat.fristen_*``) und den ECHTEN Rechte-Kern — keine
Attrappe:

  * Standardwerte 24/12 und die Grenzen 1…120
  * je Frist der GRENZFALL: knapp davor bleibt, knapp danach weg
    (Gespraeche nach letzter Nachricht UND nach Anlage, Nachrichtentext,
    Stimmenzeilen, Meldungen)
  * eine GEAENDERTE Einstellung wirkt (kuerzere Frist loescht frueher,
    laengere Frist schuetzt)
  * Nicht-Admin darf nicht speichern (403 ohne Inhalt), Admin schon
  * Idempotenz: der zweite Lauf aendert nichts
  * ein Gespraech mit Meldung + Umfrage + Reaktionen + Teilnehmern +
    Glocken-Merkern + Benachrichtigung wird VOLLSTAENDIG geloescht, ohne
    FK-Fehler und ohne toten Link
  * andere Gespraeche bleiben unberuehrt
  * das Gespraech einer bestehenden Gruppe entsteht beim naechsten Oeffnen
    neu (``gespraech_anlegen`` legt lazy an — geprueft, weil die Karte es
    verlangt)
  * Scheduler: der Job ist im Waechter-Job-Set registriert und schluckt
    Fehler, statt den Scheduler zu toeten

Die Migration ``chat8_fristen`` gehoert zu dieser Karte: die beiden Fristen
sind zwei NULLBARE Integer-Spalten der bestehenden Gemeinde-Single
(``models/gemeinde.py``) — angelegt hinter ``chat4a_glocke``, genau ein Kopf.
Ohne sie scheitert jeder Zugriff auf die Gemeinde-Einstellungen mit
``UndefinedColumn`` (Review R1). Das Inventar ``test_dsgvo1_inventar`` deckt
die Spalten mit ab (Integer, keine Textspalte); ``test_drift1_alembic_check``
prueft gegen PostgreSQL 17, dass Modell und migrierte Datenbank gleich sind.

Aufruf (Karte):
    docker run --rm --network none --entrypoint python -v <wt>:/repo:ro \\
      -w /repo/backend -e PYTHONPATH=/repo/backend/src:/repo/backend/tests:/repo/tools \\
      -e PYTHONDONTWRITEBYTECODE=1 <vorbau> -m pytest -q -p no:cacheprovider \\
      tests/test_chat8_fristen.py
"""

from __future__ import annotations

import datetime as dt
import importlib

import pytest

from diakronos_app import chat_aufbewahrung as A
from diakronos_app import db as dbmod

_session_mod = importlib.import_module("diakronos_app.frappe_compat.session")

from diakronos_app.models.chat import (  # noqa: E402
    ChatErwaehnung,
    ChatGespraech,
    ChatMeldung,
    ChatNachricht,
    ChatReaktion,
    ChatStimme,
    ChatTeilnehmer,
    ChatUmfrage,
    ChatUmfrageAbgabe,
    ChatUmfrageOption,
)
from diakronos_app.models.core import NotificationLog, User  # noqa: E402
from diakronos_app.models.diakonos import (  # noqa: E402
    Gruppe,
    Gruppenmitgliedschaft,
    Mitglied,
)
from diakronos_app.models.gemeinde import (  # noqa: E402
    GEMEINDE_EINSTELLUNGEN_NAME,
    GemeindeEinstellungen,
)
from diakronos_app.models.rechte import RechteModul  # noqa: E402

ADMIN = "admin@x.org"
SAENGER = "saenger@x.org"
FREMD = "fremd@x.org"

#: Bezugszeit des Laufs: feste Wandzeit, damit Grenzfaelle exakt sind.
JETZT = dt.datetime(2026, 11, 19, 12, 0, 0)


def _set_user(konto: str) -> None:
    _session_mod.set_user(konto)


@pytest.fixture()
def welt(patched_db):
    """Zwei Gruppen mit Chat-Modul, ein Admin — dieselbe Bauform wie CHAT-6."""
    s = patched_db()
    for konto, kurz in [(ADMIN, "Admin"), (SAENGER, "Sa"), (FREMD, "Fr")]:
        s.add(User(name=konto, email=konto, enabled=1, full_name=kurz))
        s.add(Mitglied(name=f"M-{kurz}", vorname=kurz, nachname="X",
                       email=konto, user=konto))
    from diakronos_app.models.core import HasRole

    s.add(HasRole(name="hr-admin", parent=ADMIN, parenttype="User",
                  role="System Manager"))
    for name in ("Chor", "Jugend"):
        s.add(Gruppe(name=name, gruppenname=name))
        s.add(RechteModul(gruppe=name, modul="chat"))
    s.add(Gruppenmitgliedschaft(name="gm1", parent="Chor",
                                parentfield="mitglieder", mitglied="M-Sa"))
    s.add(Gruppenmitgliedschaft(name="gm2", parent="Jugend",
                                parentfield="mitglieder", mitglied="M-Sa"))
    s.commit()
    yield s
    s.close()


def _gespraech(name: str, *, art: str = "gruppe", gruppe: str = "Chor",
               angelegt_am: dt.datetime | None = None):
    """Ein Gespraech direkt anlegen (kein Endpunkt: die Zeit ist der Zweck).

    Der partielle Unique-Index laesst nur EIN Gespraech je (art, gruppe,
    untergruppe) zu. Deshalb haengt jedes Test-Gespraech an einer EIGENEN
    Einheit — entweder ``untergruppe`` = sein Name (eigener Raum, F4) oder
    eine eigens angelegte Hauptgruppe.
    """
    with dbmod.SessionLocal.begin() as s:
        if art in ("gruppe", "untergruppe"):
            vorhanden = s.query(Gruppe).filter(Gruppe.name == gruppe).one_or_none()
            if vorhanden is None:
                s.add(Gruppe(name=gruppe, gruppenname=gruppe))
                s.add(RechteModul(gruppe=gruppe, modul="chat"))
                s.flush()
            s.add(ChatGespraech(name=name, art=art, gruppe=gruppe,
                                untergruppe=name if art == "untergruppe" else None,
                                angelegt_am=angelegt_am or JETZT))
        else:
            s.add(ChatGespraech(name=name, art=art, gruppe=f"G-{name}",
                                angelegt_am=angelegt_am or JETZT))


def _nachricht(name: str, gespraech: str, *, text: str = "Hallo",
               erstellt_am: dt.datetime | None = None,
               geloescht_am: dt.datetime | None = None,
               autor_benutzer: str | None = SAENGER) -> None:
    with dbmod.SessionLocal.begin() as s:
        s.add(ChatNachricht(name=name, gespraech=gespraech, text=text,
                            erstellt_am=erstellt_am or JETZT,
                            geloescht_am=geloescht_am,
                            geloescht_von=SAENGER if geloescht_am else None,
                            autor_benutzer=autor_benutzer,
                            autor="M-Sa" if autor_benutzer else None))


def _teilnehmer(gespraech: str, konto: str = SAENGER) -> None:
    with dbmod.SessionLocal.begin() as s:
        s.add(ChatTeilnehmer(gespraech=gespraech, benutzer=konto, stumm=False,
                             hinzugefuegt_am=JETZT))


def _reaktion(nachricht: str, konto: str = SAENGER) -> None:
    with dbmod.SessionLocal.begin() as s:
        s.add(ChatReaktion(nachricht=nachricht, benutzer=konto,
                           reaktion="👍", erstellt_am=JETZT))


def _meldung(name: str, nachricht: str, *, stand: str = "offen",
             erstellt_am: dt.datetime | None = None,
             bearbeitet_am: dt.datetime | None = None,
             melder: str | None = FREMD) -> None:
    with dbmod.SessionLocal.begin() as s:
        s.add(ChatMeldung(name=name, nachricht=nachricht, grund="spam",
                          stand=stand, erstellt_am=erstellt_am or JETZT,
                          bearbeitet_am=bearbeitet_am,
                          bearbeitet_von=ADMIN if bearbeitet_am else None,
                          melder=melder))


def _entscheide(name: str, *, stand: str, bearbeitet_am: dt.datetime) -> None:
    """Eine bestehende Meldung entscheiden (Stand + Bearbeitungszeitpunkt)."""
    with dbmod.SessionLocal.begin() as s:
        zeile = s.get(ChatMeldung, name)
        zeile.stand = stand
        zeile.bearbeitet_am = bearbeitet_am
        zeile.bearbeitet_von = ADMIN


def _umfrage(name: str, gespraech: str, *, geschlossen_am=None,
             stimmen: int = 2) -> None:
    with dbmod.SessionLocal.begin() as s:
        s.add(ChatUmfrage(name=name, gespraech=gespraech, frage="Wer?",
                          mehrfach=False, anonym=False,
                          erstellt_am=JETZT, geschlossen_am=geschlossen_am))
        s.add(ChatUmfrageOption(umfrage=name, nummer=1, text="A",
                                stimmen=stimmen))
        s.add(ChatStimme(umfrage=name, option=1, benutzer=SAENGER,
                         erstellt_am=JETZT))
        s.add(ChatUmfrageAbgabe(umfrage=name, benutzer=FREMD,
                                erstellt_am=JETZT))


def _glocke_nachricht(ziel: str, doc_typ: str = "chat_nachricht",
                      konto: str = SAENGER, name: str = "NL-1") -> None:
    with dbmod.SessionLocal.begin() as s:
        s.add(NotificationLog(name=name, for_user=konto, subject="Neu",
                              type="Alert", document_type=doc_typ,
                              document_name=ziel, read=0, docstatus=0, idx=0))


def _existiert(cls, name: str) -> bool:
    with dbmod.SessionLocal() as s:
        return s.get(cls, name) is not None


def _anzahl(cls, **filter_) -> int:
    from sqlalchemy import func, select

    with dbmod.SessionLocal() as s:
        abfrage = select(func.count()).select_from(cls)
        for spalte, wert in filter_.items():
            abfrage = abfrage.where(getattr(cls, spalte) == wert)
        return int(s.execute(abfrage).scalar_one())


def _text(nachricht: str) -> str:
    with dbmod.SessionLocal() as s:
        return str(s.get(ChatNachricht, nachricht).text)


def _glocke(name: str = "NL-1") -> NotificationLog:
    with dbmod.SessionLocal() as s:
        return s.get(NotificationLog, name)


def _fristen_setzen(gruppe: int | None = None, direkt: int | None = None) -> None:
    with dbmod.SessionLocal.begin() as s:
        A.setze_einstellungen(s, gruppe_monate=gruppe, direkt_monate=direkt,
                              benutzer=ADMIN, jetzt=JETZT)


# ── Rechnung: Kalendermonate, kein 90-Tage-Ersatz ──────────────────────────


def test_monate_zurueck_rechnet_kalendermonate():
    assert A.monate_zurueck(dt.datetime(2026, 11, 19, 12), 24) == dt.datetime(2024, 11, 19, 12)
    # 31. Mai minus 3 Monate = 28. Februar (kein 3. Maerz aus einem Ueberlauf).
    assert A.monate_zurueck(dt.datetime(2026, 5, 31, 8), 3) == dt.datetime(2026, 2, 28, 8)
    # Schaltjahr: 31. Mai 2028 minus 3 = 29. Februar 2028.
    assert A.monate_zurueck(dt.datetime(2028, 5, 31, 8), 3) == dt.datetime(2028, 2, 29, 8)
    # Jahreswechsel.
    assert A.monate_zurueck(dt.datetime(2026, 1, 15, 0), 12) == dt.datetime(2025, 1, 15, 0)


# ── Standardwerte und Grenzen ──────────────────────────────────────────────


def test_standardwerte_sind_24_und_12(welt):
    with dbmod.SessionLocal() as s:
        werte = A.holen_einstellungen(s)
    assert werte == {"chat_frist_gruppe_monate": 24, "chat_frist_direkt_monate": 12}
    assert A.FRIST_STANDARD == {"gruppe": 24, "direkt": 12}


def test_grenzen_werden_geprueft(welt):
    for falsch in (0, -5, 121, 1000, "viele", None, ""):
        with pytest.raises(A.FristFehler):
            _fristen_setzen(gruppe=falsch, direkt=12)
    # Die Grenzen selbst sind zulaessig.
    _fristen_setzen(gruppe=1, direkt=120)
    with dbmod.SessionLocal() as s:
        assert A.holen_einstellungen(s) == {
            "chat_frist_gruppe_monate": 1, "chat_frist_direkt_monate": 120,
        }


def test_unbrauchbarer_wert_in_der_datenbank_faellt_auf_den_standard(welt):
    """Ein kaputter Wert darf den Job nicht toeten und nicht „unbegrenzt“ sein."""
    with dbmod.SessionLocal.begin() as s:
        zeile = s.get(GemeindeEinstellungen, GEMEINDE_EINSTELLUNGEN_NAME)
        if zeile is None:
            zeile = GemeindeEinstellungen(name=GEMEINDE_EINSTELLUNGEN_NAME)
            s.add(zeile)
        zeile.chat_frist_gruppe_monate = 0        # unmoeglich
        zeile.chat_frist_direkt_monate = 999999   # unmoeglich
    with dbmod.SessionLocal() as s:
        assert A.holen_einstellungen(s) == {
            "chat_frist_gruppe_monate": 24, "chat_frist_direkt_monate": 12,
        }


# ── a) Gespraeche: Grenzfall knapp davor / knapp danach ────────────────────


def test_gruppengespraech_knapp_davor_bleibt_knapp_danach_weg(welt):
    # Frist 24 Monate -> Cutoff 2024-11-19 12:00.
    _gespraech("Davor", art="untergruppe", angelegt_am=dt.datetime(2020, 1, 1))
    _nachricht("N-davor", "Davor", erstellt_am=dt.datetime(2024, 11, 19, 12, 0, 1))
    _gespraech("Danach", art="untergruppe", angelegt_am=dt.datetime(2020, 1, 1))
    _nachricht("N-danach", "Danach", erstellt_am=dt.datetime(2024, 11, 19, 11, 59, 59))

    ergebnis = A.aufraeumen(jetzt=JETZT)

    assert ergebnis["gespraeche"] == 1
    assert _existiert(ChatGespraech, "Davor") is True
    assert _existiert(ChatGespraech, "Danach") is False
    # Die Nachricht des alten Gespraechs ist mit ihm gegangen.
    assert _existiert(ChatNachricht, "N-danach") is False


def test_direktgespraech_hat_die_kuerzere_frist(welt):
    """12 Monate Direkt: was fuer die Gruppe bleibt, faellt hier schon."""
    grenze = dt.datetime(2025, 11, 19, 12, 0, 0)
    _gespraech("Gruppenraum", art="gruppe", angelegt_am=dt.datetime(2020, 1, 1))
    _nachricht("N-gruppe", "Gruppenraum", erstellt_am=grenze - dt.timedelta(minutes=1))
    _gespraech("Direktraum", art="direkt", angelegt_am=dt.datetime(2020, 1, 1))
    _nachricht("N-direkt", "Direktraum", erstellt_am=grenze - dt.timedelta(minutes=1))

    ergebnis = A.aufraeumen(jetzt=JETZT)

    assert ergebnis["gespraeche"] == 1
    assert _existiert(ChatGespraech, "Gruppenraum") is True
    assert _existiert(ChatGespraech, "Direktraum") is False


def test_gespraech_ohne_nachrichten_zaehlt_ab_anlage(welt):
    _gespraech("LeerDavor", art="untergruppe", angelegt_am=dt.datetime(2024, 11, 19, 12, 0, 1))
    _gespraech("LeerDanach", art="untergruppe", angelegt_am=dt.datetime(2024, 11, 19, 11, 59, 59))

    ergebnis = A.aufraeumen(jetzt=JETZT)

    assert ergebnis["gespraeche"] == 1
    assert _existiert(ChatGespraech, "LeerDavor") is True
    assert _existiert(ChatGespraech, "LeerDanach") is False


def test_eine_junge_nachricht_haelt_ein_alten_gespraech_am_leben(welt):
    """Massgeblich ist die LETZTE Nachricht, nicht die Anlage."""
    _gespraech("Altraum", art="untergruppe", angelegt_am=dt.datetime(2015, 1, 1))
    _nachricht("N-alt", "Altraum", erstellt_am=dt.datetime(2016, 1, 1))
    _nachricht("N-neu", "Altraum", erstellt_am=JETZT - dt.timedelta(days=1))

    assert A.aufraeumen(jetzt=JETZT)["gespraeche"] == 0
    assert _existiert(ChatGespraech, "Altraum") is True


# ── Einstellung geaendert wirkt ────────────────────────────────────────────


def test_kuerzere_einstellung_loescht_frueher(welt):
    _gespraech("RaumX", art="untergruppe", angelegt_am=dt.datetime(2020, 1, 1))
    _nachricht("N-x", "RaumX", erstellt_am=JETZT - dt.timedelta(days=200))

    # Standard 24 Monate: bleibt.
    assert A.aufraeumen(jetzt=JETZT)["gespraeche"] == 0
    # 6 Monate eingestellt: faellt.
    _fristen_setzen(gruppe=6, direkt=12)
    assert A.aufraeumen(jetzt=JETZT)["gespraeche"] == 1
    assert _existiert(ChatGespraech, "RaumX") is False


def test_laengere_einstellung_schuetzt(welt):
    _gespraech("RaumY", art="untergruppe", angelegt_am=dt.datetime(2020, 1, 1))
    _nachricht("N-y", "RaumY", erstellt_am=JETZT - dt.timedelta(days=800))  # ~26 Monate

    _fristen_setzen(gruppe=60, direkt=12)
    assert A.aufraeumen(jetzt=JETZT)["gespraeche"] == 0
    assert _existiert(ChatGespraech, "RaumY") is True


# ── b) Nachrichtentexte geloeschter/entfernter Nachrichten ─────────────────


def test_geloeschter_text_nach_6_monaten_geleert(welt):
    _gespraech("RaumN", art="untergruppe")
    grenze = dt.datetime(2026, 5, 19, 12, 0, 0)   # JETZT minus 6 Monate
    _nachricht("N-davor", "RaumN", text="Geheim",
               erstellt_am=JETZT, geloescht_am=grenze + dt.timedelta(seconds=1))
    _nachricht("N-danach", "RaumN", text="Geheim",
               erstellt_am=JETZT, geloescht_am=grenze - dt.timedelta(seconds=1))
    # Eine geloeschte Nachricht muss das Gespraech nicht selbst altern lassen.
    _nachricht("N-frisch", "RaumN", text="Noch da", erstellt_am=JETZT)

    ergebnis = A.aufraeumen(jetzt=JETZT)

    assert ergebnis["nachrichten"] == 1
    assert _text("N-davor") == "Geheim"   # knapp davor: bleibt (Meldestelle)
    assert _text("N-danach") == ""        # knapp danach: endgueltig leer


def test_offene_nachricht_wird_nie_geleert(welt):
    """Die Frist trifft NUR geloeschte Zeilen — nicht jede alte Nachricht."""
    _gespraech("RaumO", art="untergruppe")
    _nachricht("N-offen", "RaumO", text="Bleibt", erstellt_am=dt.datetime(2015, 1, 1))

    ergebnis = A.aufraeumen(jetzt=JETZT)

    # Das Gespraech selbst ist mit seiner einzigen (alten) Nachricht faellig —
    # die Nachricht ging MIT ihm. Die Textleerung betrifft sie daher nicht.
    assert ergebnis["gespraeche"] == 1
    assert ergebnis["nachrichten"] == 0


def test_offene_nachricht_in_jungem_gespraech_bleibt_lesbar(welt):
    _gespraech("RaumO2", art="untergruppe")
    _nachricht("N-offen2", "RaumO2", text="Bleibt",
               erstellt_am=JETZT - dt.timedelta(days=30))

    ergebnis = A.aufraeumen(jetzt=JETZT)

    assert ergebnis["gespraeche"] == 0
    assert ergebnis["nachrichten"] == 0
    assert _text("N-offen2") == "Bleibt"


# ── c) Stimmenzeilen offener Umfragen ──────────────────────────────────────


def test_stimmen_nach_6_monaten_weg_zaehler_bleibt(welt):
    _gespraech("RaumU", art="untergruppe")
    _nachricht("N-u", "RaumU", erstellt_am=JETZT)
    grenze = dt.datetime(2026, 5, 19, 12, 0, 0)
    _umfrage("U-davor", "RaumU", geschlossen_am=grenze + dt.timedelta(seconds=1))
    _umfrage("U-danach", "RaumU", geschlossen_am=grenze - dt.timedelta(seconds=1))
    # Eine Umfrage ohne Schliessung behaelt ihre Stimmen.
    _umfrage("U-offen", "RaumU", geschlossen_am=None)

    ergebnis = A.aufraeumen(jetzt=JETZT)

    assert ergebnis["stimmen"] == 1   # nur die eine Zeile von U-danach
    assert _anzahl(ChatStimme, umfrage="U-davor") == 1
    assert _anzahl(ChatStimme, umfrage="U-danach") == 0
    assert _anzahl(ChatStimme, umfrage="U-offen") == 1
    # Der ZAEHLER bleibt stehen (Konzept 4.2: „anonym: nur der Zaehler bleibt“).
    with dbmod.SessionLocal() as s:
        option = s.get(ChatUmfrageOption, ("U-danach", 1))
        assert option.stimmen == 2
    # Die „hat abgestimmt“-Marke ist kein Stimmgeheimnis zur Option und bleibt.
    assert _anzahl(ChatUmfrageAbgabe, umfrage="U-danach") == 1


# ── d) Meldungen 12 Monate nach Abschluss ──────────────────────────────────


def test_meldungen_nach_12_monaten_ab_abschluss_weg(welt):
    _gespraech("RaumM", art="untergruppe")
    _nachricht("N-m", "RaumM", erstellt_am=JETZT)
    grenze = dt.datetime(2025, 11, 19, 12, 0, 0)
    _meldung("M-davor", "N-m", stand="erledigt",
             bearbeitet_am=grenze + dt.timedelta(seconds=1))
    _meldung("M-danach", "N-m", stand="verworfen",
             bearbeitet_am=grenze - dt.timedelta(seconds=1))
    _meldung("M-offen", "N-m", stand="offen", bearbeitet_am=None)

    ergebnis = A.aufraeumen(jetzt=JETZT)

    assert ergebnis["meldungen"] == 1
    assert _existiert(ChatMeldung, "M-davor") is True
    assert _existiert(ChatMeldung, "M-danach") is False
    # Eine offene Meldung wartet auf eine Entscheidung — sie bleibt.
    assert _existiert(ChatMeldung, "M-offen") is True


def test_abgeschlossene_meldung_ohne_zeitpunkt_bleibt(welt):
    """Ohne Datum gibt es keine Frist (Altzeile, kein Grund fuer eine Loeschung)."""
    _gespraech("RaumM2", art="untergruppe")
    _nachricht("N-m2", "RaumM2", erstellt_am=JETZT)
    _meldung("M-ohne-zeit", "N-m2", stand="erledigt", bearbeitet_am=None)

    assert A.aufraeumen(jetzt=JETZT)["meldungen"] == 0
    assert _existiert(ChatMeldung, "M-ohne-zeit") is True


# ── Vollstaendige Loeschung ohne FK-Fehler und ohne toten Link ─────────────


def test_gespraech_mit_allem_wird_vollstaendig_geloescht(welt):
    alt = dt.datetime(2020, 1, 1)
    _gespraech("RaumVoll", art="untergruppe", angelegt_am=alt)
    _nachricht("N-1", "RaumVoll", erstellt_am=alt, autor_benutzer=SAENGER)
    _nachricht("N-2", "RaumVoll", erstellt_am=alt, autor_benutzer=FREMD,
               text="Antwort")
    with dbmod.SessionLocal.begin() as s:
        s.get(ChatNachricht, "N-2").antwort_auf = "N-1"
    _teilnehmer("RaumVoll", SAENGER)
    _teilnehmer("RaumVoll", FREMD)
    _reaktion("N-1")
    _reaktion("N-2", FREMD)
    _umfrage("U-voll", "RaumVoll", geschlossen_am=None)
    with dbmod.SessionLocal.begin() as s:
        s.get(ChatNachricht, "N-1").umfrage = "U-voll"
    # Eine ENTSCHEIDENE Meldung — eine offene wuerde das Gespraech aussetzen
    # (Entscheidung Operator R1/4, eigener Test unten).
    _meldung("M-voll", "N-2", stand="erledigt", bearbeitet_am=alt)
    _glocke_nachricht("RaumVoll", doc_typ="chat_gespraech", name="NL-G")
    _glocke_nachricht("N-1", doc_typ="chat_nachricht", name="NL-N")

    ergebnis = A.aufraeumen(jetzt=JETZT)

    assert ergebnis["gespraeche"] == 1
    for cls, name in [(ChatGespraech, "RaumVoll"), (ChatNachricht, "N-1"),
                      (ChatNachricht, "N-2"), (ChatMeldung, "M-voll"),
                      (ChatUmfrage, "U-voll")]:
        assert _existiert(cls, name) is False, f"{cls.__tablename__}.{name} lebt noch"
    assert _anzahl(ChatStimme, umfrage="U-voll") == 0
    # Reaktionen haengen am zusammengesetzten Schluessel (nachricht, benutzer).
    for nachricht in ("N-1", "N-2"):
        assert _anzahl(ChatReaktion, nachricht=nachricht) == 0
    assert _anzahl(ChatUmfrageOption, umfrage="U-voll") == 0
    assert _anzahl(ChatUmfrageAbgabe, umfrage="U-voll") == 0
    assert _anzahl(ChatTeilnehmer, gespraech="RaumVoll") == 0
    # Kein toter Link: Chat-Benachrichtigungen auf das geloeschte Ziel werden
    # GELOESCHT, nicht entkoppelt (Entscheidung Operator R1/3).
    assert ergebnis["glocken"] == 2
    for name in ("NL-G", "NL-N"):
        assert _glocke(name) is None, f"{name} lebt noch (toter Link)"


def test_erwaehnungen_und_ihre_glocken_sterben_mit_dem_gespraech(welt):
    """CHAT-9a (Review R1/1): die Frist loescht Erwaehnungen UND ihre Glocken.

    Die Erwaehnungs-Glocke haengt an der NACHRICHT
    (``document_type='chat_erwaehnung'``, ``document_name`` = Nachricht), nicht
    am Gespraech — ohne den Eintrag in ``GLOCKE_DOKUMENTTYPEN`` bliebe sie als
    toter Link stehen. Die Zeilen selbst fallen in ``_gespraech_entfernen``
    (Kinder zuerst: SQLite hat ohne FK-Pragma keine wirksame Kaskade).
    """
    alt = dt.datetime(2020, 1, 1)
    _gespraech("RaumErw", art="untergruppe", angelegt_am=alt)
    _nachricht("N-erw", "RaumErw", erstellt_am=alt)
    _teilnehmer("RaumErw")
    with dbmod.SessionLocal.begin() as s:
        s.add(ChatErwaehnung(nachricht="N-erw", mitglied="M-Fr", angelegt_am=alt))
    assert "chat_erwaehnung" in A.GLOCKE_DOKUMENTTYPEN
    _glocke_nachricht("N-erw", doc_typ="chat_erwaehnung", konto=FREMD, name="NL-ERW")

    ergebnis = A.aufraeumen(jetzt=JETZT)

    assert ergebnis["gespraeche"] == 1
    assert _existiert(ChatGespraech, "RaumErw") is False
    assert _existiert(ChatNachricht, "N-erw") is False
    assert _anzahl(ChatErwaehnung, nachricht="N-erw") == 0
    assert _glocke("NL-ERW") is None, "Erwaehnungs-Glocke lebt noch (toter Link)"
    assert ergebnis["glocken"] == 1


def test_andere_gespraeche_bleiben_unberuehrt(welt):
    _gespraech("Altraum", art="untergruppe", angelegt_am=dt.datetime(2020, 1, 1))
    _nachricht("N-alt", "Altraum", erstellt_am=dt.datetime(2020, 1, 2))
    _gespraech("RaumJung", art="untergruppe", angelegt_am=dt.datetime(2020, 1, 1))
    _nachricht("N-jung", "RaumJung", erstellt_am=JETZT - dt.timedelta(days=3))
    _teilnehmer("RaumJung")
    # Auch die junge Nachricht traegt eine Umfrage — sie darf nicht mitfallen.
    _umfrage("U-jung", "RaumJung", geschlossen_am=None)
    with dbmod.SessionLocal.begin() as s:
        s.get(ChatNachricht, "N-jung").umfrage = "U-jung"

    A.aufraeumen(jetzt=JETZT)

    assert _existiert(ChatGespraech, "Altraum") is False
    assert _existiert(ChatGespraech, "RaumJung") is True
    assert _existiert(ChatNachricht, "N-jung") is True
    assert _existiert(ChatUmfrage, "U-jung") is True
    assert _anzahl(ChatStimme, umfrage="U-jung") == 1
    assert _anzahl(ChatTeilnehmer, gespraech="RaumJung") == 1


def test_offene_meldung_setzt_die_frist_aus(welt):
    """Entscheidung Operator R1/4: offene Meldung = Gespraech bleibt stehen.

    Solange ein Fall nicht entschieden ist, braucht die Meldestelle den
    Ausschnitt — auch wenn das Gespraech laengst ueber der Frist liegt. Nach
    der Entscheidung greift die Frist beim NAECHSTEN Lauf.
    """
    alt = dt.datetime(2020, 1, 1)
    _gespraech("RaumOffen", art="untergruppe", angelegt_am=alt)
    _nachricht("N-offen", "RaumOffen", erstellt_am=alt)
    _meldung("M-offen-frist", "N-offen", stand="offen")

    erster = A.aufraeumen(jetzt=JETZT)

    assert erster["gespraeche"] == 0
    assert erster["gespraeche_offen"] == 1
    assert _existiert(ChatGespraech, "RaumOffen") is True
    assert _existiert(ChatNachricht, "N-offen") is True
    assert _existiert(ChatMeldung, "M-offen-frist") is True

    # Meldung entschieden -> beim naechsten Lauf greift die Frist.
    _entscheide("M-offen-frist", bearbeitet_am=JETZT - dt.timedelta(days=1),
                stand="erledigt")

    zweiter = A.aufraeumen(jetzt=JETZT)

    assert zweiter["gespraeche"] == 1
    assert zweiter["gespraeche_offen"] == 0
    assert _existiert(ChatGespraech, "RaumOffen") is False
    assert _existiert(ChatNachricht, "N-offen") is False
    assert _existiert(ChatMeldung, "M-offen-frist") is False


def test_glocken_merker_des_geloeschten_gespraechs_fallen_mit(welt):
    """CHAT-4a: ``chat_glocke`` haelt das Gespraech als PK — die FK verlangt
    die Loeschung VOR dem Gespraech. Der Merker anderer Gespraeche bleibt."""
    from diakronos_app.models.chat import ChatGlocke
    from sqlalchemy import func, select

    alt = dt.datetime(2020, 1, 1)
    _gespraech("RaumGlocke", art="untergruppe", angelegt_am=alt)
    _nachricht("N-glocke", "RaumGlocke", erstellt_am=alt)
    _gespraech("RaumBleibt", art="untergruppe", angelegt_am=alt)
    _nachricht("N-bleibt", "RaumBleibt", erstellt_am=JETZT - dt.timedelta(days=1))
    with dbmod.SessionLocal.begin() as s:
        s.add(ChatGlocke(gespraech="RaumGlocke", benutzer=SAENGER,
                         stand="N-glocke", stand_am=alt))
        s.add(ChatGlocke(gespraech="RaumGlocke", benutzer=FREMD,
                         stand=None, stand_am=alt))
        s.add(ChatGlocke(gespraech="RaumBleibt", benutzer=SAENGER,
                         stand="N-bleibt", stand_am=JETZT))

    assert A.aufraeumen(jetzt=JETZT)["gespraeche"] == 1

    with dbmod.SessionLocal() as s:
        assert s.execute(
            select(func.count()).select_from(ChatGlocke)
            .where(ChatGlocke.gespraech == "RaumGlocke")
        ).scalar_one() == 0
        assert s.execute(
            select(func.count()).select_from(ChatGlocke)
            .where(ChatGlocke.gespraech == "RaumBleibt")
        ).scalar_one() == 1


def test_benachrichtigung_auf_geloeschte_meldung_wird_entfernt(welt):
    """12-Monats-Frist (d): die Glocke auf die Meldung zeigt sonst ins Leere."""
    _gespraech("RaumMeld", art="untergruppe")
    _nachricht("N-meld", "RaumMeld", erstellt_am=JETZT)
    _meldung("M-alt", "N-meld", stand="erledigt", bearbeitet_am=dt.datetime(2020, 1, 1))
    _glocke_nachricht("M-alt", doc_typ="chat_meldung", name="NL-M")
    # Ein FREMDER Typ bleibt unberuehrt (keine Chat-Benachrichtigung).
    _glocke_nachricht("irgendwas", doc_typ="mitglied", name="NL-fremd")

    ergebnis = A.aufraeumen(jetzt=JETZT)

    assert ergebnis["meldungen"] == 1
    assert ergebnis["glocken"] == 1
    assert _glocke("NL-M") is None
    assert _glocke("NL-fremd") is not None


def test_verwaiste_glocke_aus_frueherem_lauf_wird_entfernt(welt):
    """Zweiter Netz: eine Glocke, deren Ziel es schon vorher nicht mehr gab."""
    _gespraech("RaumX", art="untergruppe")
    _nachricht("N-x", "RaumX", erstellt_am=JETZT)
    _glocke_nachricht("chat-gespraech-weg", doc_typ="chat_gespraech", name="NL-weg")
    _glocke_nachricht("N-x", doc_typ="chat_nachricht", name="NL-ok")

    ergebnis = A.aufraeumen(jetzt=JETZT)

    assert ergebnis["glocken"] == 1
    assert _glocke("NL-weg") is None
    assert _glocke("NL-ok") is not None


def test_zweiter_lauf_aendert_nichts(welt):
    """Idempotenz: was weg ist, ist weg — der zweite Lauf findet nichts."""
    _gespraech("RaumA", art="untergruppe", angelegt_am=dt.datetime(2020, 1, 1))
    _nachricht("N-a", "RaumA", erstellt_am=dt.datetime(2020, 1, 2),
               geloescht_am=dt.datetime(2020, 1, 3))
    _gespraech("RaumB", art="untergruppe")
    _umfrage("U-b", "RaumB", geschlossen_am=dt.datetime(2020, 1, 1))
    _nachricht("N-b", "RaumB", erstellt_am=JETZT)
    _meldung("M-b", "N-b", stand="erledigt", bearbeitet_am=dt.datetime(2020, 1, 1))

    erster = A.aufraeumen(jetzt=JETZT)
    zweiter = A.aufraeumen(jetzt=JETZT)

    assert erster["gespraeche"] == 1
    assert erster["stimmen"] == 1
    assert erster["meldungen"] == 1
    assert zweiter == {schluessel: 0 for schluessel in A.ERGEBNIS_KEYS}


def test_gespraech_einer_gruppe_entsteht_beim_naechsten_oeffnen_neu(welt):
    """Die Karte verlangt ausdruecklich: nach der Loeschung wieder lazy anlegbar."""
    from diakronos_app.api import chat as C

    _set_user(SAENGER)
    erst = C.gespraech_anlegen("Chor")["name"]
    _session_mod.reset_user()
    with dbmod.SessionLocal.begin() as s:
        s.get(ChatGespraech, erst).angelegt_am = dt.datetime(2020, 1, 1)
    _nachricht("N-alt", erst, erstellt_am=dt.datetime(2020, 1, 2))

    assert A.aufraeumen(jetzt=JETZT)["gespraeche"] == 1
    assert _existiert(ChatGespraech, erst) is False

    _set_user(SAENGER)
    neu = C.gespraech_anlegen("Chor")["name"]
    _session_mod.reset_user()
    assert neu != erst
    assert _existiert(ChatGespraech, neu) is True


# ── Endpunkte: Lesen fuer alle, Schreiben nur fuer den Administrator ───────


def test_fristen_lesen_ist_fuer_mitglieder_erlaubt(welt):
    from diakronos_app.api import chat as C

    _set_user(SAENGER)
    daten = C.fristen_lesen()
    _session_mod.reset_user()
    assert daten["chat_frist_gruppe_monate"] == 24
    assert daten["chat_frist_direkt_monate"] == 12
    assert daten["standard"] == {"gruppe": 24, "direkt": 12}
    assert (daten["minimum"], daten["maximum"]) == (1, 120)
    assert daten["meldung_monate"] == 12


def test_nicht_admin_darf_nicht_speichern(welt):
    from diakronos_app.api import chat as C
    from diakronos_app.frappe_compat.exceptions import PermissionError

    for wer in (SAENGER, FREMD, "Guest"):
        _set_user(wer)
        with pytest.raises(PermissionError) as fehler:
            C.fristen_speichern(chat_frist_gruppe_monate=6,
                                chat_frist_direkt_monate=3)
        # 403 OHNE Inhalt — der Grund bleibt im Server.
        assert not str(fehler.value or "")
    _session_mod.reset_user()

    # Und nichts wurde geschrieben.
    with dbmod.SessionLocal() as s:
        assert A.holen_einstellungen(s)["chat_frist_gruppe_monate"] == 24


def test_admin_darf_speichern_und_der_lauf_nimmt_es(welt):
    from diakronos_app.api import chat as C

    _set_user(ADMIN)
    antwort = C.fristen_speichern(chat_frist_gruppe_monate=6,
                                  chat_frist_direkt_monate=3)
    _session_mod.reset_user()
    assert antwort["gespeichert"] is True
    assert antwort["chat_frist_gruppe_monate"] == 6
    assert antwort["chat_frist_direkt_monate"] == 3

    with dbmod.SessionLocal() as s:
        assert A.holen_einstellungen(s) == {
            "chat_frist_gruppe_monate": 6, "chat_frist_direkt_monate": 3,
        }


def test_admin_bekommt_bei_unmoeglichem_wert_eine_meldung(welt):
    from diakronos_app.api import chat as C
    from diakronos_app.frappe_compat.exceptions import ValidationError

    _set_user(ADMIN)
    try:
        with pytest.raises(ValidationError) as fehler:
            C.fristen_speichern(chat_frist_gruppe_monate=0,
                                chat_frist_direkt_monate=12)
        assert "zwischen 1 und 120" in str(fehler.value)
    finally:
        _session_mod.reset_user()


# ── Scheduler ──────────────────────────────────────────────────────────────


def test_scheduler_job_ist_registriert_und_laeuft_nicht_sofort():
    from diakronos_app.scheduler import DAILY_JOBS, build_scheduler

    assert ("chat_aufbewahrung" in {job_id for _, job_id in DAILY_JOBS})
    scheduler = build_scheduler()
    try:
        job = {j.id: j for j in scheduler.get_jobs()}["chat_aufbewahrung"]
        assert job.trigger.__class__.__name__ == "CronTrigger"
    finally:
        scheduler.shutdown(wait=False) if scheduler.running else None


def test_scheduler_job_schluckt_fehler(welt, monkeypatch):
    """Ein Fehler im Lauf darf den Scheduler nicht toeten."""
    from diakronos_app import scheduler as S

    def platzt(jetzt=None):
        raise RuntimeError("Datenbank weg")

    monkeypatch.setattr(A, "aufraeumen", platzt)
    S.job_chat_aufbewahrung()  # darf NICHT werfen


def test_scheduler_job_ruft_den_lauf(welt, monkeypatch):
    from diakronos_app import scheduler as S

    gesehen = {}

    def merkt(jetzt=None):
        gesehen["gelaufen"] = True
        return {"gespraeche": 0}

    monkeypatch.setattr(A, "aufraeumen", merkt)
    S.job_chat_aufbewahrung()
    assert gesehen.get("gelaufen") is True
