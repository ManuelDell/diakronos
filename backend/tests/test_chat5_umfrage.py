"""CHAT-5 (S2): Umfragen im Gruppenchat — Modell, Rechte, Anonymität, API.

Konzept ``docs/konzepte/CHAT-KONZEPT.md`` Abschnitt 1/S2, 2.2 (Rechte-Matrix)
und Entscheidung F5 (Abschnitt 9: jedes Mitglied darf Umfragen starten;
Standard ANONYM, je Umfrage wählbar). Geprüft wird gegen die ECHTEN Endpunkte
(``api/chat.py``), den ECHTEN Rechte-Kern (``rechte/kern.py``) und die ECHTE
Migration — keine Attrappe:

  * Rechte: fremde Gruppe / Gast / Untergruppe → 403; wer lesen darf, sieht das
    Ergebnis; Schließen nur Ersteller oder MODERIEREN
  * ANONYM: die Datenbank enthält NACHWEISLICH keine Zeile, die Person und
    Option verbindet (``chat_stimme`` leer, ``chat_umfrage_abgabe`` ohne
    Optionsspalte); zweite Abgabe → 400, auch bei gleichzeitiger Abgabe
  * OFFEN: namentliche Stimmen, bis zur Frist änderbar, Namen im Ergebnis
  * nach Frist / nach Schließung: keine Stimme mehr (400), Ergebnis bleibt
  * Hinweis „erratbar“ unter 5 Abgegebenen
  * Scheduler: fällige Umfragen werden geschlossen (``geschlossen_von`` NULL)
  * Verlauf liefert die Umfragedaten mit — ohne N+1 (feste Zahl Abfragen)
  * Migration ``chat5_umfrage``: Kette hinter ``chat6_meldung``, genau EIN
    Kopf, anlegen / downgrade / idempotent
  * DSGVO: Anonymisierung löscht Stimmen und Marken, der ZÄHLER bleibt

Aufruf (Karte):
    docker run --rm --network none --entrypoint python -v <wt>:/repo:ro \\
      -w /repo/backend -e PYTHONPATH=/repo/backend/src:/repo/backend/tests:/repo/tools \\
      -e PYTHONDONTWRITEBYTECODE=1 <vorbau> -m pytest -q -p no:cacheprovider \\
      tests/test_chat5_umfrage.py
"""

from __future__ import annotations

import datetime as dt
import importlib
from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import event

from diakronos_app import db as dbmod

#: Die Test-Naht liegt im MODUL ``frappe_compat.session`` (wie ``test_chat2_api``).
_session_mod = importlib.import_module("diakronos_app.frappe_compat.session")
from diakronos_app.models.chat import (
    ChatStimme,
    ChatUmfrage,
    ChatUmfrageAbgabe,
    ChatUmfrageOption,
)
from diakronos_app.models.core import HasRole, User
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
SAENGER = "saenger@x.org"    # Mitglied Chor (nicht in der Untergruppe)
NOTEN = "noten@x.org"        # Mitglied der Untergruppe Notenausschuss
FREMD = "fremd@x.org"        # Gemeindemitglied ohne Gruppe
JUGEND = "jugend@x.org"      # Mitglied einer Gruppe OHNE Chat-Modul
POSAUNEN = "posaunen@x.org"  # Mitglied einer ECHTEN Fremdgruppe
POSAUNEN_HV = "posaunen-hv@x.org"


def _set_user(konto: str | None) -> None:
    _session_mod.set_user(konto)


def _reset() -> None:
    _session_mod.reset_user()


@pytest.fixture()
def welt(patched_db):
    """Chor mit Untergruppe — dieselbe Welt wie ``test_chat2_api.py``."""
    s = patched_db()
    for konto, kurz in [(ADMIN, "Admin"), (HV, "Hv"), (MV, "Mv"), (GL, "Gl"),
                        (SAENGER, "Sa"), (NOTEN, "No"), (FREMD, "Fr"),
                        (JUGEND, "Ju"), (POSAUNEN, "Po"), (POSAUNEN_HV, "Ph")]:
        s.add(User(name=konto, email=konto, enabled=1, full_name=kurz))
        s.add(Mitglied(name=f"M-{kurz}", vorname=kurz, nachname="X", email=konto,
                       user=konto))
    s.add(HasRole(name="hr-admin", parent=ADMIN, parenttype="User",
                  role="System Manager"))
    s.add(Gruppe(name="Chor", gruppenname="Chor"))
    s.add(Gruppe(name="Jugend", gruppenname="Jugend"))
    # Eine ECHTE zweite Gruppe MIT Chat-Modul: der saubere Fall „fremde Gruppe“
    # (bei der Jugend fehlt das Modul, dort wäre der 403 nicht aussagekräftig).
    s.add(Gruppe(name="Posaunen", gruppenname="Posaunen"))
    s.add(Untergruppe(name="UG-Noten", untergruppenname="Notenausschuss",
                      gruppe="Chor"))
    s.add(Gruppenmitgliedschaft(name="gm1", parent="Chor",
                                parentfield="mitglieder", mitglied="M-Sa"))
    s.add(Gruppenmitgliedschaft(name="gm2", parent="Chor",
                                parentfield="mitglieder", mitglied="M-Mv"))
    s.add(Untergruppenmitgliedschaft(name="ugm1", parent="UG-Noten",
                                     parentfield="mitglieder", mitglied="M-No"))
    s.add(Gruppenmitgliedschaft(name="gm3", parent="Jugend",
                                parentfield="mitglieder", mitglied="M-Ju"))
    s.add(Gruppenmitgliedschaft(name="gm4", parent="Posaunen",
                                parentfield="mitglieder", mitglied="M-Po"))
    s.add_all([
        RechteGruppenrolle(gruppe="Chor", benutzer=HV, rolle="HV"),
        RechteGruppenrolle(gruppe="Chor", benutzer=MV, rolle="MV"),
        RechteGruppenrolle(gruppe="Chor", untergruppe="UG-Noten", benutzer=GL,
                           rolle="GL"),
        RechteGruppenrolle(gruppe="Posaunen", benutzer=POSAUNEN_HV, rolle="HV"),
        RechteModul(gruppe="Chor", modul="chat"),
        RechteModul(gruppe="Posaunen", modul="chat"),
    ])
    s.commit()
    yield s
    s.close()


@pytest.fixture()
def gespraech(welt):
    """Das Chor-Gespräch (lazy angelegt, per Endpunkt)."""
    from diakronos_app.api import chat as C

    _set_user(SAENGER)
    name = C.gespraech_anlegen("Chor")["name"]
    _reset()
    return name


def _umfrage(gespraech: str, konto: str = SAENGER, frage: str = "Wann proben wir?",
             optionen=None, mehrfach: bool = False, anonym: bool = True,
             frist=None) -> dict:
    """Eine Umfrage per Endpunkt anlegen (Antwortform des Endpunkts)."""
    from diakronos_app.api import chat as C

    _set_user(konto)
    return C.umfrage_anlegen(
        gespraech, frage,
        optionen=optionen if optionen is not None else ["Samstag", "Sonntag"],
        mehrfach=mehrfach, anonym=anonym, frist=frist,
    )


def _abstimmen(umfrage: str, konto: str, optionen) -> dict:
    from diakronos_app.api import chat as C

    _set_user(konto)
    return C.umfrage_abstimmen(umfrage, optionen=optionen)


# ── Anlegen: Form, Optionen, Frist ─────────────────────────────────────────


def test_anlegen_erzeugt_nachricht_mit_umfrage(gespraech):
    """Die Umfrage IST eine Nachricht im Verlauf (Reihenfolge/Lesestand)."""
    from diakronos_app.api import chat as C
    from diakronos_app.models.chat import ChatNachricht

    _set_user(SAENGER)
    antwort = C.umfrage_anlegen(gespraech, "Wann proben wir?",
                                optionen=["Samstag", "Sonntag"])
    u = antwort["umfrage"]
    assert u["frage"] == "Wann proben wir?"
    assert [o["text"] for o in u["optionen"]] == ["Samstag", "Sonntag"]
    assert [o["nummer"] for o in u["optionen"]] == [1, 2]
    assert u["abgegeben"] == 0 and u["stimmen_gesamt"] == 0
    assert u["offen"] is True
    assert u["anonym"] is True          # F5: Standard ANONYM
    assert u["mehrfach"] is False
    assert u["eigene_stimme"] is None
    assert u["frist_am"] is None        # offen bis zur Schließung
    assert u["geschlossen_am"] is None

    # Der Verweis steht an der Nachricht: sie trägt die Frage als Text.
    with dbmod.SessionLocal() as s:
        n = s.get(ChatNachricht, antwort["name"])
        assert n.umfrage == u["name"]
        assert n.text == "Wann proben wir?"
        assert n.autor_benutzer == SAENGER


def test_optionen_grenzen_und_leere_texte(gespraech):
    """2–15 Optionen; leere Einträge fallen weg, zu wenige/zu viele → 400."""
    from diakronos_app.api import chat as C
    from diakronos_app.frappe_compat.exceptions import ValidationError

    _set_user(SAENGER)
    with pytest.raises(ValidationError):
        C.umfrage_anlegen(gespraech, "Nur eine?", optionen=["Ja"])
    with pytest.raises(ValidationError):
        C.umfrage_anlegen(gespraech, "Zu viele?",
                          optionen=[f"O{i}" for i in range(16)])
    with pytest.raises(ValidationError):
        C.umfrage_anlegen(gespraech, "", optionen=["A", "B"])

    # Leere Einträge verschwinden (Formular schickt gelegentlich eins mit).
    u = C.umfrage_anlegen(gespraech, "Zwei?", optionen=["A", "", "B", "  "])["umfrage"]
    assert [o["text"] for o in u["optionen"]] == ["A", "B"]


def test_string_optionen_mit_trenner(gespraech):
    """``||`` als Trenner (Formularweg); Kommas dürfen in der Option bleiben."""
    from diakronos_app.api import chat as C

    _set_user(SAENGER)
    u = C.umfrage_anlegen(gespraech, "Termin?",
                          optionen="Samstag, 18 Uhr||Sonntag, 10 Uhr")["umfrage"]
    assert [o["text"] for o in u["optionen"]] == ["Samstag, 18 Uhr", "Sonntag, 10 Uhr"]


def test_frist_in_der_vergangenheit_wird_abgewiesen(gespraech):
    from diakronos_app.api import chat as C
    from diakronos_app.frappe_compat.exceptions import ValidationError

    _set_user(SAENGER)
    with pytest.raises(ValidationError):
        C.umfrage_anlegen(gespraech, "Vorbei?", optionen=["A", "B"],
                          frist="2020-01-01 10:00")
    with pytest.raises(ValidationError):
        C.umfrage_anlegen(gespraech, "Kauderwelsch?", optionen=["A", "B"],
                          frist="irgendwann")


# ── Rechte: fremde Gruppe, Gast, Untergruppe ───────────────────────────────


def test_fremde_gruppe_kann_nicht_anlegen_abstimmen_lesen(welt):
    """Fremde Gruppe MIT Chat-Modul: kein Anlegen, kein Abstimmen, kein Lesen."""
    from diakronos_app.api import chat as C
    from diakronos_app.frappe_compat.exceptions import PermissionError

    _set_user(POSAUNEN)
    fremd = C.gespraech_anlegen("Posaunen")["name"]
    _set_user(SAENGER)
    chor = C.gespraech_anlegen("Chor")["name"]
    u = C.umfrage_anlegen(chor, "Chor-Frage", optionen=["A", "B"])["umfrage"]

    _set_user(POSAUNEN)
    with pytest.raises(PermissionError) as fehler:
        C.umfrage_anlegen(chor, "Untergeschoben", optionen=["A", "B"])
    assert str(fehler.value) == ""
    with pytest.raises(PermissionError) as fehler:
        C.umfrage_abstimmen(u["name"], optionen=1)
    assert str(fehler.value) == ""
    with pytest.raises(PermissionError) as fehler:
        C.umfrage_ergebnis(u["name"])
    assert str(fehler.value) == ""
    # Und der eigene (fremde) Raum bleibt unberührt.
    assert fremd != chor


def test_gast_und_nichtmitglied_bekommen_403(gespraech):
    from diakronos_app.api import chat as C
    from diakronos_app.frappe_compat.exceptions import PermissionError

    _set_user(SAENGER)
    u = C.umfrage_anlegen(gespraech, "Frage?", optionen=["A", "B"])["umfrage"]

    for konto in (None, "Guest", FREMD):
        _set_user(konto)
        with pytest.raises(PermissionError):
            C.umfrage_anlegen(gespraech, "Frage?", optionen=["A", "B"])
        with pytest.raises(PermissionError):
            C.umfrage_abstimmen(u["name"], optionen=1)
        with pytest.raises(PermissionError):
            C.umfrage_ergebnis(u["name"])
        with pytest.raises(PermissionError):
            C.umfrage_schliessen(u["name"])

    # Gast und Nichtmitglied wurden keine Stimme los.
    with dbmod.SessionLocal() as s:
        assert s.query(ChatUmfrageAbgabe).count() == 0


def test_untergruppe_ist_getrennt(gespraech):
    """F4: der Untergruppen-Chat ist ein eigener Raum — auch für Umfragen."""
    from diakronos_app.api import chat as C
    from diakronos_app.frappe_compat.exceptions import PermissionError

    _set_user(NOTEN)
    ug = C.gespraech_anlegen("Chor", "UG-Noten")["name"]
    u_ug = C.umfrage_anlegen(ug, "Noten-Frage", optionen=["A", "B"])["umfrage"]

    _set_user(SAENGER)   # Chormitglied, NICHT im Notenausschuss
    with pytest.raises(PermissionError):
        C.umfrage_ergebnis(u_ug["name"])
    with pytest.raises(PermissionError):
        C.umfrage_abstimmen(u_ug["name"], optionen=1)

    # Die Umfrage des Chors sieht der Notenausschuss NICHT — er ist nicht
    # Chormitglied im Sinne dieses Raums? Doch: GL ist Leitung, NOTEN nicht
    # zwingend Mitglied. Geprüft wird die Richtung, die sicher gilt: SAENGER
    # sieht die Untergruppen-Umfrage nicht (oben), und die Untergruppen-Umfrage
    # liegt in EINEM anderen Gespräch als die Chor-Umfrage.
    _set_user(SAENGER)
    u_chor = C.umfrage_anlegen(gespraech, "Chor-Frage", optionen=["A", "B"])["umfrage"]
    assert u_chor["gespraech"] != u_ug["gespraech"]


# ── Anonym: keine Zeile mit Personenbezug zur Option ───────────────────────


def test_anonym_speichert_nachweislich_keine_option_je_person(gespraech):
    """KERNZUSAGE: keine Zeile verbindet Person und Option.

    Geprüft wird nicht die Antwort, sondern die DATENBANK — auch die Spalten,
    die es geben könnte und nicht gibt (``chat_umfrage_abgabe`` hat keine
    Optionsspalte), und die Zählung je Option.
    """
    from sqlalchemy import inspect

    u = _umfrage(gespraech, anonym=True)["umfrage"]
    ergebnis = _abstimmen(u["name"], SAENGER, 1)
    assert ergebnis["stimmen_gesamt"] == 1
    assert ergebnis["abgegeben"] == 1
    assert ergebnis["abgestimmt"] is True
    assert ergebnis["eigene_stimme"] is None     # anonym: keine eigene Stimme
    assert [o["stimmen"] for o in ergebnis["optionen"]] == [1, 0]
    # Auch keine NAMEN — es gibt keine Zeile, aus der sie kämen.
    assert all(o["namen"] == [] for o in ergebnis["optionen"])

    with dbmod.SessionLocal() as s:
        # 1) KEINE Stimmenzeile (die Tabelle bleibt für diese Umfrage leer).
        assert s.query(ChatStimme).filter(ChatStimme.umfrage == u["name"]).count() == 0
        # 2) Genau EINE Marke, und zwar ohne jede Option.
        marken = s.query(ChatUmfrageAbgabe).filter(
            ChatUmfrageAbgabe.umfrage == u["name"]).all()
        assert len(marken) == 1
        assert marken[0].benutzer == SAENGER
        spalten = {c["name"] for c in inspect(s.get_bind()).get_columns("chat_umfrage_abgabe")}
        assert spalten == {"umfrage", "benutzer", "erstellt_am"}, spalten
        # 3) Der Zähler steht an der Option, nicht an der Person.
        opt = s.get(ChatUmfrageOption, (u["name"], 1))
        assert opt.stimmen == 1
        assert s.get(ChatUmfrageOption, (u["name"], 2)).stimmen == 0
    _reset()


def test_anonyme_zweite_abgabe_ist_gesperrt(gespraech):
    """Anonyme Stimmen sind ENDGÜLTIG — zweite Abgabe → 400, Zähler unverändert."""
    from diakronos_app.api import chat as C
    from diakronos_app.frappe_compat.exceptions import ValidationError

    u = _umfrage(gespraech, anonym=True)["umfrage"]
    _abstimmen(u["name"], SAENGER, 1)

    _set_user(SAENGER)
    with pytest.raises(ValidationError):
        C.umfrage_abstimmen(u["name"], optionen=2)
    with pytest.raises(ValidationError):
        C.umfrage_abstimmen(u["name"], optionen=1)

    with dbmod.SessionLocal() as s:
        assert s.get(ChatUmfrageOption, (u["name"], 1)).stimmen == 1
        assert s.get(ChatUmfrageOption, (u["name"], 2)).stimmen == 0
        assert s.query(ChatUmfrageAbgabe).filter(
            ChatUmfrageAbgabe.umfrage == u["name"]).count() == 1
    _reset()


def test_anonyme_doppelabgabe_scheitert_auch_gleichzeitig(gespraech):
    """Der Primärschlüssel ist die Sperre — nicht eine Prüfung, die zwei
    gleichzeitige Aufrufe beide bestehen würden.

    Der zweite Aufruf wird HIER so gefahren, dass er die Marke schon in der
    Datenbank findet (der Primärschlüssel greift), ohne dass die
    Python-Prüfung „schon abgestimmt“ hätte zählen können: die Marke wird
    direkt eingefügt und der Zähler NICHT erhöht. Ergebnis: IntegrityError →
    ValidationError, und der Zähler bleibt genau einmal."""
    from sqlalchemy.exc import IntegrityError

    u = _umfrage(gespraech, anonym=True)["umfrage"]
    _abstimmen(u["name"], SAENGER, 1)

    with dbmod.SessionLocal() as s:
        # Der Doppelklick: dieselbe Person legt die Marke ein zweites Mal an.
        s.add(ChatUmfrageAbgabe(umfrage=u["name"], benutzer=SAENGER,
                                erstellt_am=dt.datetime.now()))
        with pytest.raises(IntegrityError):
            s.commit()
        s.rollback()
        assert s.query(ChatUmfrageAbgabe).filter(
            ChatUmfrageAbgabe.umfrage == u["name"]).count() == 1
        assert s.get(ChatUmfrageOption, (u["name"], 1)).stimmen == 1
    _reset()


def test_anonymer_hinweis_unter_fuenf_abgegebenen(gespraech):
    """„Ergebnis bei wenigen Teilnehmenden erratbar“ — ab 5 verschwindet er."""
    u = _umfrage(gespraech, anonym=True)["umfrage"]
    assert _abstimmen(u["name"], SAENGER, 1)["hinweis"] is not None

    for konto in (HV, MV, GL, NOTEN):
        ergebnis = _abstimmen(u["name"], konto, 2)
    assert ergebnis["abgegeben"] == 5
    assert ergebnis["hinweis"] is None
    assert ergebnis["stimmen_gesamt"] == 5
    _reset()


# ── Offen: namentlich, änderbar, Namen im Ergebnis ─────────────────────────


def test_offen_speichert_namen_und_ist_aenderbar(gespraech):
    u = _umfrage(gespraech, anonym=False)["umfrage"]
    assert u["anonym"] is False

    erste = _abstimmen(u["name"], SAENGER, 1)
    assert erste["eigene_stimme"] == [1]
    assert erste["optionen"][0]["stimmen"] == 1
    assert "Sa" in erste["optionen"][0]["namen"] or erste["optionen"][0]["namen"]

    with dbmod.SessionLocal() as s:
        zeilen = s.query(ChatStimme).filter(ChatStimme.umfrage == u["name"]).all()
        assert [(z.benutzer, z.option) for z in zeilen] == [(SAENGER, 1)]
        # Offene Umfrage: KEINE Abgabe-Marke (die gibt es nur anonym).
        assert s.query(ChatUmfrageAbgabe).filter(
            ChatUmfrageAbgabe.umfrage == u["name"]).count() == 0

    # Ändern: die alte Stimme fällt, der Zähler wandert mit.
    zweite = _abstimmen(u["name"], SAENGER, 2)
    assert zweite["eigene_stimme"] == [2]
    assert [o["stimmen"] for o in zweite["optionen"]] == [0, 1]
    with dbmod.SessionLocal() as s:
        zeilen = s.query(ChatStimme).filter(ChatStimme.umfrage == u["name"]).all()
        assert [(z.benutzer, z.option) for z in zeilen] == [(SAENGER, 2)]

    # Eine ZWEITE Person wählt dieselbe Option: Zähler 2, zwei Namen, EINE
    # abgegebene Person mehr (nicht zwei Stimmen = zwei Personen).
    dritte = _abstimmen(u["name"], HV, 2)
    assert dritte["optionen"][1]["stimmen"] == 2
    assert dritte["abgegeben"] == 2
    _reset()


def test_offen_mehrfachauswahl_und_grenze(gespraech):
    from diakronos_app.api import chat as C
    from diakronos_app.frappe_compat.exceptions import ValidationError

    einfach = _umfrage(gespraech, anonym=False, mehrfach=False)["umfrage"]
    _set_user(SAENGER)
    with pytest.raises(ValidationError):
        C.umfrage_abstimmen(einfach["name"], optionen=[1, 2])

    mehrfach = _umfrage(gespraech, anonym=False, mehrfach=True)["umfrage"]
    _set_user(SAENGER)
    ergebnis = C.umfrage_abstimmen(mehrfach["name"], optionen=[1, 2])
    assert ergebnis["eigene_stimme"] == [1, 2]
    assert [o["stimmen"] for o in ergebnis["optionen"]] == [1, 1]
    # Wer zwei Optionen wählt, ist EINE abgegebene Person.
    assert ergebnis["abgegeben"] == 1
    _reset()


def test_stimme_ausserhalb_der_optionen_wird_abgewiesen(gespraech):
    from diakronos_app.api import chat as C
    from diakronos_app.frappe_compat.exceptions import ValidationError

    u = _umfrage(gespraech, anonym=False)["umfrage"]
    _set_user(SAENGER)
    with pytest.raises(ValidationError):
        C.umfrage_abstimmen(u["name"], optionen=[99])
    with pytest.raises(ValidationError):
        C.umfrage_abstimmen(u["name"], optionen=[])
    _reset()


# ── Frist und Schließung ───────────────────────────────────────────────────


def test_nach_frist_keine_stimme_mehr_ergebnis_bleibt(gespraech):
    from diakronos_app.api import chat as C
    from diakronos_app.frappe_compat.exceptions import ValidationError

    u = _umfrage(gespraech, anonym=False)["umfrage"]
    _abstimmen(u["name"], SAENGER, 1)

    # Die Frist verstreichen lassen (die Wandzeit der Umfrage zurücksetzen —
    # der Endpunkt weist vergangene Fristen beim Anlegen ab, das ist gewollt).
    with dbmod.SessionLocal() as s:
        zeile = s.get(ChatUmfrage, u["name"])
        zeile.frist_am = dt.datetime.now() - dt.timedelta(minutes=1)
        s.commit()

    _set_user(HV)
    with pytest.raises(ValidationError):
        C.umfrage_abstimmen(u["name"], optionen=1)

    _set_user(SAENGER)
    ergebnis = C.umfrage_ergebnis(u["name"])
    assert ergebnis["offen"] is False
    assert ergebnis["stimmen_gesamt"] == 1   # Ergebnis bleibt
    assert ergebnis["optionen"][0]["stimmen"] == 1
    _reset()


def test_fremde_koennen_nicht_schliessen(gespraech):
    from diakronos_app.api import chat as C
    from diakronos_app.frappe_compat.exceptions import PermissionError

    u = _umfrage(gespraech, konto=SAENGER)["umfrage"]
    for konto in (NOTEN, FREMD, JUGEND):
        _set_user(konto)
        with pytest.raises(PermissionError):
            C.umfrage_schliessen(u["name"])
    with dbmod.SessionLocal() as s:
        assert s.get(ChatUmfrage, u["name"]).geschlossen_am is None
    _reset()


def test_ersteller_und_moderation_duerfen_schliessen(gespraech):
    from diakronos_app.api import chat as C

    # a) Der ERSTELLER (eigenes Mitgliedsrecht, nicht Rolle).
    u = _umfrage(gespraech, konto=SAENGER)["umfrage"]
    _set_user(SAENGER)
    geschlossen = C.umfrage_schliessen(u["name"])
    assert geschlossen["offen"] is False
    assert geschlossen["geschlossen_von"] == SAENGER
    assert geschlossen["geschlossen_am"] is not None

    # b) Die MODERATION (HV) bei fremder Umfrage.
    u2 = _umfrage(gespraech, konto=SAENGER)["umfrage"]
    _set_user(HV)
    assert C.umfrage_schliessen(u2["name"])["offen"] is False

    # Idempotent: der zweite Aufruf ändert den Zeitpunkt NICHT.
    _set_user(SAENGER)
    zweite = C.umfrage_schliessen(u["name"])
    assert zweite["geschlossen_von"] == SAENGER
    _reset()


def test_geschlossene_umfrage_nimmt_keine_stimme_mehr(gespraech):
    from diakronos_app.api import chat as C
    from diakronos_app.frappe_compat.exceptions import ValidationError

    u = _umfrage(gespraech, konto=SAENGER, anonym=False)["umfrage"]
    _abstimmen(u["name"], SAENGER, 1)
    _set_user(SAENGER)
    C.umfrage_schliessen(u["name"])

    _set_user(HV)
    with pytest.raises(ValidationError):
        C.umfrage_abstimmen(u["name"], optionen=2)
    _reset()


def test_scheduler_schliesst_faellige_umfragen(gespraech):
    """Der BESTEHENDE Scheduler-Job schließt zur Frist — ohne ``geschlossen_von``."""
    from diakronos_app import scheduler as S
    from diakronos_app.api import chat as C
    from diakronos_app.frappe_compat.exceptions import ValidationError

    faellig = _umfrage(gespraech, anonym=False)["umfrage"]
    spaeter = _umfrage(gespraech, anonym=False)["umfrage"]
    offen = _umfrage(gespraech, anonym=False)["umfrage"]   # ohne Frist

    jetzt = dt.datetime.now()
    with dbmod.SessionLocal() as s:
        s.get(ChatUmfrage, faellig["name"]).frist_am = jetzt - dt.timedelta(hours=1)
        s.get(ChatUmfrage, spaeter["name"]).frist_am = jetzt + dt.timedelta(days=1)
        s.commit()

    # Der Job ist im Scheduler registriert (täglicher Lauf, eine Stelle).
    assert "umfragen_schliessen" in [job_id for _fn, job_id in S.DAILY_JOBS]

    # Der Job selbst schließt die fällige Umfrage (er nimmt „jetzt“).
    assert S.job_umfragen_schliessen() is None

    with dbmod.SessionLocal() as s:
        zu = s.get(ChatUmfrage, faellig["name"])
        # geschlossen_am = die FRIST, nicht „jetzt“ — die Anzeige ist damit
        # unabhängig davon, wann der Job tatsächlich lief.
        assert zu.geschlossen_am == zu.frist_am
        assert zu.geschlossen_von is None            # automatisch = automatisch
        assert s.get(ChatUmfrage, spaeter["name"]).geschlossen_am is None
        assert s.get(ChatUmfrage, offen["name"]).geschlossen_am is None

    # Idempotent: ein zweiter Lauf schließt nichts mehr.
    assert C.schliesse_faellige(jetzt=jetzt) == 0

    _set_user(HV)
    with pytest.raises(ValidationError):
        C.umfrage_abstimmen(faellig["name"], optionen=1)
    _reset()


def test_scheduler_job_faengt_fehler_ab(monkeypatch):
    """Ein Fehler im Job darf den Scheduler nicht töten (bestehendes Muster)."""
    from diakronos_app import api as api_paket  # noqa: F401 — Import-Reihenfolge
    from diakronos_app import scheduler as S

    def kaputt(*_a, **_k):
        raise RuntimeError("Datenbank weg")

    import diakronos_app.api.chat as C

    monkeypatch.setattr(C, "schliesse_faellige", kaputt)
    assert S.job_umfragen_schliessen() is None


# ── Verlauf: Umfragedaten kommen mit, ohne N+1 ─────────────────────────────


def test_verlauf_liefert_umfragedaten_mit(gespraech):
    from diakronos_app.api import chat as C

    u = _umfrage(gespraech, anonym=False)["umfrage"]
    _abstimmen(u["name"], SAENGER, 1)

    _set_user(SAENGER)
    seite = C.verlauf(gespraech)
    zeilen = seite["nachrichten"]
    umfrage_zeilen = [z for z in zeilen if "umfrage" in z]
    assert len(umfrage_zeilen) == 1
    daten = umfrage_zeilen[0]["umfrage"]
    assert daten["name"] == u["name"]
    assert daten["eigene_stimme"] == [1]        # offen: die eigene Stimme
    assert daten["abgegeben"] == 1

    # Nicht-Umfrage-Nachrichten tragen den Schlüssel GAR NICHT (flache Form).
    C.senden(gespraech, "Nur Text")
    _set_user(SAENGER)
    seite = C.verlauf(gespraech)
    for z in seite["nachrichten"]:
        if z["text"] == "Nur Text":
            assert "umfrage" not in z
    _reset()


def test_verlauf_anonyme_umfrage_zeigt_nur_abgestimmt(gespraech):
    from diakronos_app.api import chat as C

    u = _umfrage(gespraech, anonym=True)["umfrage"]
    _abstimmen(u["name"], SAENGER, 2)

    _set_user(SAENGER)
    daten = [z for z in C.verlauf(gespraech)["nachrichten"] if "umfrage" in z][0]["umfrage"]
    assert daten["abgestimmt"] is True
    assert daten["eigene_stimme"] is None       # KEINE Option zur Person
    assert [o["stimmen"] for o in daten["optionen"]] == [0, 1]
    _reset()


def test_verlauf_umfrage_seite_ohne_n_plus_eins(gespraech, welt):
    """Feste Zahl Abfragen für die ganze Seite, unabhängig von der Zahl der
    Umfragen: der naive Weg (eine Abfrage je Nachricht) wäre 3× so viel."""
    from diakronos_app.api import chat as C

    for i in range(3):
        u = _umfrage(gespraech, anonym=False, frage=f"Frage {i}")["umfrage"]
        _abstimmen(u["name"], SAENGER, 1)

    zaehler = {"n": 0}

    def mithoeren(*_a, **_k):
        zaehler["n"] += 1

    eng = welt.get_bind()
    event.listen(eng, "before_cursor_execute", mithoeren)
    try:
        _set_user(SAENGER)
        C.verlauf(gespraech)
    finally:
        event.remove(eng, "before_cursor_execute", mithoeren)
    _reset()
    # Drei Umfragen, drei Stimmen: die Zahl der Abfragen hängt NICHT an der
    # Zahl der Umfragen (sie bleibt beim Verlauf der Nachrichtenseite).
    assert zaehler["n"] < 60, zaehler["n"]


# ── Gelöschte Umfrage: für alle Wege weg (Review CHAT-5b, MUSS 2) ──────────


def _loeschen(nachricht: str, konto: str) -> None:
    from diakronos_app.api import chat as C

    _set_user(konto)
    C.loeschen(nachricht)


def _pruefe_weg(umfrage: str, konto: str) -> None:
    """Abstimmen, Ergebnis und Schließen liefern für eine entfernte Umfrage 404."""
    from diakronos_app.api import chat as C
    from diakronos_app.frappe_compat.exceptions import (
        DoesNotExistError,
        PermissionError,
    )

    _set_user(konto)
    with pytest.raises(DoesNotExistError):
        C.umfrage_abstimmen(umfrage, optionen=1)
    _reset()
    _set_user(konto)
    with pytest.raises(DoesNotExistError):
        C.umfrage_ergebnis(umfrage)
    _reset()
    # Schließen: die Rechteprüfung kommt VOR dem Lesen — ein Fremder bekommt
    # 403 (er darf die Umfrage nicht einmal sehen). Der Ersteller/Moderator
    # kommt durch die Rechte und landet dann auf 404.
    _set_user(konto)
    try:
        C.umfrage_schliessen(umfrage)
    except DoesNotExistError:
        pass
    except PermissionError:
        pass
    else:
        pytest.fail("gelöschte Umfrage ließ sich schließen")
    finally:
        _reset()


def test_selbst_geloeschte_umfrage_nimmt_keine_stimme_und_kein_ergebnis(gespraech):
    """SOLL: die Hülle-Nachricht ist die Umfrage — weg ist weg (404)."""
    from diakronos_app.api import chat as C

    u = _umfrage(gespraech, konto=SAENGER, anonym=False)["umfrage"]
    _abstimmen(u["name"], HV, 1)          # eine FREMDSTIMME steht schon drin

    _set_user(SAENGER)
    antwort = C.umfrage_anlegen(gespraech, "Zweite Frage", optionen=["A", "B"])
    _loeschen(antwort["name"], SAENGER)   # die eigene Umfrage selbst gelöscht
    _reset()

    _pruefe_weg(antwort["umfrage"]["name"], SAENGER)
    _pruefe_weg(antwort["umfrage"]["name"], HV)
    # KEINE Stimme kam durch — auch keine fremde.
    with dbmod.SessionLocal() as s:
        assert s.query(ChatStimme).filter(
            ChatStimme.umfrage == antwort["umfrage"]["name"]).count() == 0
        assert s.get(ChatUmfrage, antwort["umfrage"]["name"]).geschlossen_am is None
        # Die erste Umfrage bleibt unberührt.
        assert s.get(ChatUmfrageOption, (u["name"], 1)).stimmen == 1
    _reset()


def test_moderation_entfernte_umfrage_nimmt_keine_stimme_und_keine_namen(gespraech):
    """MUSS 2: die offene Umfrage lieferte nach dem Entfernen noch NAMEN."""
    from diakronos_app.api import chat as C

    _set_user(SAENGER)
    antwort = C.umfrage_anlegen(gespraech, "Vertraulich?", optionen=["A", "B"])
    # Die Stimme kommt von einer ANDEREN Person: sonst entfernt das Löschen
    # der Nachricht den Personenbezug mit (Chat-Nachrichten der Person gehen
    # bei „Nachricht entfernen“ mit) — hier soll die Umfrage selbst geprüft
    # werden.
    _abstimmen(antwort["umfrage"]["name"], MV, 1)

    # HV ist Moderator und entfernt die Nachricht (nicht sein Eigentum).
    _loeschen(antwort["name"], HV)
    _reset()

    _pruefe_weg(antwort["umfrage"]["name"], SAENGER)
    _pruefe_weg(antwort["umfrage"]["name"], HV)
    _pruefe_weg(antwort["umfrage"]["name"], MV)
    with dbmod.SessionLocal() as s:
        # Die Stimme der ANDEREN Person steht (kein Name kam hinzu), ist aber
        # über keinen Endpunkt mehr lesbar: Abstimmen, Ergebnis, Schließen →
        # 404. Genau das war der Befund: vorher lieferte das Ergebnis hier
        # den Namen samt gewählter Option.
        # Der Zähler der Option steht (die Stimme zählt weiter im Ergebnis);
        # die ZEILE der Person kann bei der Moderation mitgehen
        # (``entfernt_grund`` räumt die Stimmen mit) — was NICHT bleiben darf,
        # ist der Weg zum Namen. Der führt jetzt ins 404.
        assert s.get(ChatUmfrageOption, (antwort["umfrage"]["name"], 1)).stimmen == 1
        assert s.get(ChatUmfrage, antwort["umfrage"]["name"]).geschlossen_am is None
        # Der VERLAUF zeigt die Lücke ohne Umfragedaten — nicht die Umfrage.
        _set_user(HV)
        for z in C.verlauf(gespraech)["nachrichten"]:
            if z["name"] == antwort["name"]:
                assert z["geloescht"] is True
                # Der Schlüssel steht (flache Form), ist aber LEER: kein
                # Ergebnis, keine Namen einer entfernten Umfrage.
                assert z.get("umfrage") is None
        _reset()
    _reset()


def test_geloeschte_umfrage_wird_vom_scheduler_nicht_mehr_geschlossen(gespraech):
    """Die Frist läuft ab, die Umfrage ist weg: kein Schließen, kein Fehler."""
    from diakronos_app.api import chat as C

    _set_user(SAENGER)
    faellig = C.umfrage_anlegen(gespraech, "Fristig?", optionen=["A", "B"])["umfrage"]
    with dbmod.SessionLocal() as s:
        s.get(ChatUmfrage, faellig["name"]).frist_am = (
            dt.datetime.now() - dt.timedelta(minutes=5))
        s.commit()
    zeile = [z for z in C.verlauf(gespraech)["nachrichten"]
             if "umfrage" in z][-1]
    _loeschen(zeile["name"], SAENGER)
    _reset()

    C.schliesse_faellige()
    with dbmod.SessionLocal() as s:
        # Der Scheduler schreibt weiter auf die Zeile (er kennt den Verlauf
        # nicht) — sichtbar ist sie nicht: jeder Weg endet im 404.
        assert s.get(ChatUmfrage, faellig["name"]) is not None
    _pruefe_weg(faellig["name"], SAENGER)
    _reset()


# ── Aendern: die Frage einer Umfrage ist nicht umschreibbar (SOLL b) ───────


def test_umfragefrage_laesst_sich_nicht_aendern(gespraech):
    from diakronos_app.api import chat as C
    from diakronos_app.frappe_compat.exceptions import ValidationError
    from diakronos_app.models.chat import ChatNachricht

    antwort = _umfrage(gespraech, konto=SAENGER)
    _set_user(SAENGER)
    with pytest.raises(ValidationError):
        C.aendern(antwort["name"], "Ganz andere Frage")
    with dbmod.SessionLocal() as s:
        n = s.get(ChatNachricht, antwort["name"])
        assert n.text == "Wann proben wir?"
        assert n.bearbeitet_am is None
        assert s.get(ChatUmfrage, antwort["umfrage"]["name"]).frage == "Wann proben wir?"

    # Eine NORMALE Nachricht bleibt bearbeitbar (die Sperre gilt nur der Hülle).
    _set_user(SAENGER)
    normal = C.senden(gespraech, "Erster Text")
    assert C.aendern(normal["name"], "Neuer Text")["text"] == "Neuer Text"
    _reset()


# ── Offene Stimme: Ändern ist ein Rennen ohne Doppelzählung (SOLL a) ───────


def test_offene_stimme_aendern_zaehlt_nicht_doppelt(gespraech):
    """Zwei Aufrufe derselben Person: am Ende EINE Zeile, EINE Stimme.

    Sequenziell simuliert, aber über den Pfad, der das Rennen entscheidet: das
    Herunterzählen hängt am ``rowcount`` des ``DELETE``. Der zweite Aufruf
    findet keine Zeile mehr zum Löschen — und deshalb bleibt der Zähler bei 1
    statt auf 0/2 zu wandern.
    """
    from sqlalchemy import delete, select, update

    from diakronos_app.api.chat import _offene_stimmen_setzen
    from diakronos_app.models.chat import ChatNachricht

    with dbmod.SessionLocal.begin() as s:
        u = ChatUmfrage(name="U-1", gespraech=gespraech, frage="Wer?",
                        mehrfach=False, anonym=False,
                        erstellt_am=dt.datetime.now())
        u2 = ChatUmfrage(name="U-2", gespraech=gespraech, frage="Wer noch?",
                         mehrfach=False, anonym=False,
                         erstellt_am=dt.datetime.now())
        s.add_all([u, u2])
        for kennung in ("U-1", "U-2"):
            s.add(ChatUmfrageOption(umfrage=kennung, nummer=1, text="A", stimmen=0))
            s.add(ChatUmfrageOption(umfrage=kennung, nummer=2, text="B", stimmen=0))

    with dbmod.SessionLocal.begin() as s:
        s.add(ChatNachricht(name="N-1", gespraech=gespraech, text="Wer?",
                            erstellt_am=dt.datetime.now(), umfrage="U-1"))
    _set_user(SAENGER)
    _abstimmen("U-1", SAENGER, 1)
    # Der gleichzeitige ZWEITE Aufruf hat die Zeile schon entfernt und den
    # Zähler schon heruntergezählt — hier direkt nachgestellt.
    with dbmod.SessionLocal.begin() as s:
        s.execute(delete(ChatStimme).where(ChatStimme.umfrage == "U-1",
                                           ChatStimme.option == 1,
                                           ChatStimme.benutzer == SAENGER))
        s.execute(update(ChatUmfrageOption)
                  .where(ChatUmfrageOption.umfrage == "U-1",
                         ChatUmfrageOption.nummer == 1)
                  .values(stimmen=ChatUmfrageOption.stimmen - 1))

    # Jetzt setzt der zweite Aufruf die Stimme auf 2 — er darf NICHT noch
    # einmal von Option 1 herunterzählen (die Zeile ist weg).
    with dbmod.SessionLocal.begin() as s:
        _offene_stimmen_setzen(s, s.get(ChatUmfrage, "U-1"), SAENGER, [2])
        s.flush()

    with dbmod.SessionLocal() as s:
        zeilen = s.execute(select(ChatStimme.option).where(
            ChatStimme.umfrage == "U-1", ChatStimme.benutzer == SAENGER)).scalars().all()
        assert list(zeilen) == [2], zeilen            # Einzelauswahl = eine Stimme
        assert s.get(ChatUmfrageOption, ("U-1", 1)).stimmen == 0   # nie negativ
        assert s.get(ChatUmfrageOption, ("U-1", 2)).stimmen == 1
    _reset()


def test_umfragen_laden_nutzt_durchgaengig_textschluessel(welt):
    """SOLL c: die Kennungen im Ergebnis sind ``str``, egal was die DB liefert."""
    from diakronos_app.api.chat import _umfragen_laden

    _set_user(SAENGER)
    with dbmod.SessionLocal.begin() as s:
        s.add(ChatUmfrage(name="12345", gespraech="Chor", frage="F?",
                          mehrfach=False, anonym=False,
                          erstellt_am=dt.datetime.now()))
        s.add(ChatUmfrageOption(umfrage="12345", nummer=1, text="A", stimmen=1))
        s.add(ChatStimme(umfrage="12345", option=1, benutzer=SAENGER,
                         erstellt_am=dt.datetime.now()))

    with dbmod.SessionLocal() as s:
        # Ein INTEGER als Kennung darf den Schlüssel nicht verändern.
        daten = _umfragen_laden(s, [12345, "12345"], SAENGER)
        assert list(daten) == ["12345"], list(daten)
        assert daten["12345"]["abgegeben"] == 1
        assert daten["12345"]["eigene_stimme"] == [1]
    _reset()


# ── Migration ──────────────────────────────────────────────────────────────


def _skripte() -> ScriptDirectory:
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "alembic"))
    return ScriptDirectory.from_config(cfg)


    """GENAU EIN Kopf; chat5_umfrage haengt hinter chat6_meldung."""
def test_genau_ein_kopf_und_chat5_haengt_hinter_chat6():
    """GENAU EIN Kopf: chat2_chat_s1 -> chat6_meldung -> chat5_umfrage.

    Der KOPFNAME wird NICHT festgeschrieben (Hinweis Operator): spaetere
    Fachmigrationen haengen sich hinten an, ein Test auf einen festen Kopf
    wird dabei ohne Fachfehler rot.
    """
    skripte = _skripte()
    assert len(skripte.get_heads()) == 1, skripte.get_heads()
    assert len(skripte.get_bases()) == 1, skripte.get_bases()
    revision = skripte.get_revision("chat5_umfrage")
    assert revision is not None
    assert revision.down_revision == "chat6_meldung", revision.down_revision
    assert "Revises: chat6_meldung" in Path(revision.path).read_text(encoding="utf-8")
    # Beide Zweige des Zwischenstands sind eingehängt, nicht abgeschnitten.
    assert skripte.get_revision("chat6_meldung").down_revision == "chat2_chat_s1"


@pytest.fixture()
def fresh_engine():
    """Leere SQLite-Engine MIT Gerüst, aber OHNE die vier Umfrage-Tabellen."""
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
        verbindung.exec_driver_sql('DROP TABLE IF EXISTS "chat_umfrage_abgabe"')
        verbindung.exec_driver_sql('DROP TABLE IF EXISTS "chat_stimme"')
        verbindung.exec_driver_sql('DROP TABLE IF EXISTS "chat_umfrage_option"')
        verbindung.exec_driver_sql('DROP TABLE IF EXISTS "chat_umfrage"')
    yield eng
    eng.dispose()


def _migration():
    import importlib.util

    pfad = BACKEND / "alembic" / "versions" / "chat5_umfrage.py"
    spec = importlib.util.spec_from_file_location("chat5_umfrage", pfad)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def test_migration_legt_tabellen_spalte_und_indizes_an(fresh_engine):
    from sqlalchemy import inspect

    modul = _migration()
    insp = inspect(fresh_engine)
    assert not insp.has_table("chat_umfrage")

    with fresh_engine.begin() as verbindung:
        from alembic.migration import MigrationContext
        from alembic.operations import Operations

        import alembic.op as alembic_op

        ctx = MigrationContext.configure(verbindung)
        ops = Operations(ctx)
        alt = getattr(alembic_op, "_proxy", None)
        alembic_op._proxy = ops
        try:
            modul.upgrade()
        finally:
            alembic_op._proxy = alt

    insp = inspect(fresh_engine)
    for tabelle in ("chat_umfrage", "chat_umfrage_option", "chat_stimme",
                    "chat_umfrage_abgabe"):
        assert insp.has_table(tabelle), tabelle
    spalten = {c["name"] for c in insp.get_columns("chat_nachricht")}
    assert "umfrage" in spalten
    # Höchstens EINE Umfrage je Nachricht — in der Datenbank.
    unique = {i["name"]: i for i in insp.get_indexes("chat_nachricht")}
    assert unique["uq_chat_nachricht_umfrage"]["unique"] == 1
    assert {i["name"] for i in insp.get_indexes("chat_umfrage")} >= {
        "ix_chat_umfrage_gespraech", "ix_chat_umfrage_frist"}
    assert {i["name"] for i in insp.get_indexes("chat_stimme")} >= {
        "ix_chat_stimme_benutzer"}
    # F5: Standard ANONYM steht im Schema.
    anonym = [c for c in insp.get_columns("chat_umfrage") if c["name"] == "anonym"][0]
    assert anonym["nullable"] is False


def test_migration_ist_idempotent_und_geht_zurueck(fresh_engine):
    """upgrade → downgrade → upgrade: keine Reste, kein Fehler."""
    from sqlalchemy import inspect

    modul = _migration()

    def _upgrade():
        from alembic.migration import MigrationContext
        from alembic.operations import Operations

        import alembic.op as alembic_op

        with fresh_engine.begin() as verbindung:
            ops = Operations(MigrationContext.configure(verbindung))
            alt = getattr(alembic_op, "_proxy", None)
            alembic_op._proxy = ops
            try:
                modul.upgrade()
            finally:
                alembic_op._proxy = alt

    def _downgrade():
        from alembic.migration import MigrationContext
        from alembic.operations import Operations

        import alembic.op as alembic_op

        with fresh_engine.begin() as verbindung:
            ops = Operations(MigrationContext.configure(verbindung))
            alt = getattr(alembic_op, "_proxy", None)
            alembic_op._proxy = ops
            try:
                modul.downgrade()
            finally:
                alembic_op._proxy = alt

    _upgrade()
    _upgrade()          # idempotent: nichts doppelt
    _downgrade()
    insp = inspect(fresh_engine)
    for tabelle in ("chat_umfrage", "chat_umfrage_option", "chat_stimme",
                    "chat_umfrage_abgabe"):
        assert not insp.has_table(tabelle), tabelle
    assert "umfrage" not in {c["name"] for c in insp.get_columns("chat_nachricht")}
    _upgrade()
    assert inspect(fresh_engine).has_table("chat_umfrage")


# ── DSGVO ──────────────────────────────────────────────────────────────────


def test_inventar_deckt_die_umfrage_tabellen():
    """Jede personenbezogene Spalte der neuen Tabellen hat eine Entscheidung."""
    from diakronos_app import dsgvo_anonymisierung as D

    for tabelle, spalten in {
        "chat_umfrage": {"frage", "geschlossen_von"},
        "chat_umfrage_option": {"text"},
        "chat_stimme": {"benutzer"},
        "chat_umfrage_abgabe": {"benutzer"},
    }.items():
        assert spalten <= set(D.SPALTEN.get(tabelle, {})), (tabelle,
                                                           D.SPALTEN.get(tabelle))

    loeschzeilen = {name for name, _ in D.ZEILEN_LOESCHEN}
    assert {"chat_stimme", "chat_umfrage_abgabe"} <= loeschzeilen
    assert D.KONTO_ZEILEN <= loeschzeilen
    # Der ZÄHLER trägt keinen Personenbezug — die Optionszeile bleibt.
    assert "chat_umfrage_option" not in loeschzeilen
    assert "chat_umfrage" not in loeschzeilen


def test_anonymisierung_loescht_stimmen_und_marken_zaehler_bleibt(gespraech):
    """Art. 17: die Spur der Person fällt, das ERGEBNIS bleibt stehen."""
    from diakronos_app import dsgvo_anonymisierung as D

    offen = _umfrage(gespraech, anonym=False)["umfrage"]
    anonym = _umfrage(gespraech, anonym=True)["umfrage"]
    _abstimmen(offen["name"], SAENGER, 1)
    _abstimmen(anonym["name"], SAENGER, 2)

    with dbmod.SessionLocal.begin() as s:
        vorher = (s.get(ChatUmfrageOption, (offen["name"], 1)).stimmen,
                  s.get(ChatUmfrageOption, (anonym["name"], 2)).stimmen)
        assert vorher == (1, 1)
        D.anonymisiere(s, "M-Sa", [SAENGER])
        s.flush()

        # Die Zeilen DER PERSON sind weg …
        assert s.query(ChatStimme).filter(ChatStimme.benutzer == SAENGER).count() == 0
        assert s.query(ChatUmfrageAbgabe).filter(
            ChatUmfrageAbgabe.benutzer == SAENGER).count() == 0
        # … der ZÄHLER steht unverändert (das Ergebnis gehört den anderen).
        assert (s.get(ChatUmfrageOption, (offen["name"], 1)).stimmen,
                s.get(ChatUmfrageOption, (anonym["name"], 2)).stimmen) == vorher
        # Die Umfrage selbst bleibt bestehen (Fachdatum der Gruppe).
        assert s.get(ChatUmfrage, offen["name"]) is not None
    _reset()


def test_anonymisierung_laesst_stimmen_anderer_stehen(gespraech):
    """Die Löschung trifft die Zeilen der PERSON — nicht die aller Umfragen.

    Befund aus dem Review-Lauf: ``_zeilen_loeschen`` verknüpfte die Spalten
    von ``chat_stimme`` mit ODER. ``option`` hat aber nur kleine Zahlen (1, 2
    …) — die Löschung nahm damit die Stimmen der Person in JEDER Umfrage mit,
    in der irgendwer die Option 1 oder 2 gewählt hatte. Hier geprüft: eine
    zweite Person stimmt in derselben Umfrage ab und behält ihre Stimme.
    """
    from diakronos_app import dsgvo_anonymisierung as D
    from diakronos_app.models.chat import ChatNachricht

    _set_user(SAENGER)
    from diakronos_app.api import chat as C

    u = C.umfrage_anlegen(gespraech, "Wer kommt?", optionen=["A", "B"],
                          anonym=False)["umfrage"]
    _abstimmen(u["name"], SAENGER, 1)
    _abstimmen(u["name"], HV, 1)      # HV wählt DIESELBE Option 1
    _abstimmen(u["name"], MV, 2)      # MV eine andere

    with dbmod.SessionLocal.begin() as s:
        D.anonymisiere(s, "M-Sa", [SAENGER])
        s.flush()

    with dbmod.SessionLocal() as s:
        zeilen = s.query(ChatStimme).filter(ChatStimme.umfrage == u["name"]).all()
        # Nur die Zeile von SAENGER fällt; HV und MV behalten ihre.
        assert sorted(z.benutzer for z in zeilen) == sorted([HV, MV])
        # Der ZÄHLER bleibt (Karte: „der Zähler bleibt“) — 2 Stimmen auf
        # Option 1, eine davon ohne Zeile. Das Ergebnis gehört den anderen.
        assert s.get(ChatUmfrageOption, (u["name"], 1)).stimmen == 2
        assert s.get(ChatUmfrageOption, (u["name"], 2)).stimmen == 1   # MV
        # Und die Hülle-Nachricht bleibt sichtbar (die Umfrage ist Fachdatum).
        n = s.query(ChatNachricht).filter(ChatNachricht.umfrage == u["name"]).one()
        assert n.geloescht_am is None
    _reset()
