"""CHAT-2 (S1): Gruppenchat — Datenmodell, Rechte, API.

Konzept ``docs/konzepte/CHAT-KONZEPT.md`` (Abschnitt 1/S1, 2, 3.3, 4.5, 9) und
Karte CHAT-2. Geprüft wird gegen die ECHTEN Endpunkte (``api/chat.py``) und den
ECHTEN Rechte-Kern (``rechte/kern.py``) — keine Attrappe:

  * Nichtmitglied → 403, Modul aus → 403, fremde Nachricht bearbeiten → 403
  * Leitung darf löschen, Mitglied nicht
  * Untergruppen-Chat ist getrennt (F4)
  * 15-Minuten-Grenze beim Bearbeiten, Kennzeichen „bearbeitet“
  * Reaktion einmalig je Person und Nachricht (PK)
  * Lesestand nur als SUMME („gelesen von N“), nie als Namensliste (F2)
  * Lazy-Anlegen: ein Gespräch je Einheit, kein Massen-Insert
  * Verlauf seitenweise: „vor X“ (älter) und „seit X“ (neuer, Polling)
  * Textgrenze 4 000 Zeichen, Zeilenumbrüche bleiben
  * Soft-Delete: Lücke bleibt, Inhalt geht nicht nach außen

Aufruf (Karte):
    docker run --rm --network none --entrypoint python -v <wt>:/repo:ro \
      -w /repo/backend -e PYTHONPATH=/repo/backend/src:/repo/backend/tests:/repo/tools \
      --entrypoint python <vorbau> -m pytest -q -p no:cacheprovider tests/test_chat2_api.py
"""

from __future__ import annotations

import datetime as dt

import pytest
from fastapi.testclient import TestClient

import importlib

#: Die Sitzungs-Factory IMMER ueber das Modul `db` holen: ein gebundener Name
#: (`from diakronos_app.db import SessionLocal`) friert die Betriebs-Engine beim
#: Import ein, und `patched_db` biegt dann nur noch `db.SessionLocal` um —
#: der Test liefe gegen `db:5432`.
from diakronos_app import db as dbmod

#: Die Test-Naht liegt im MODUL ``frappe_compat.session`` — ``from
#: diakronos_app.frappe_compat import session`` liefert dagegen das
#: Sitzungs-OBJEKT (das Paket bindet den Namen um, s. ``conftest.py``).
_session_mod = importlib.import_module("diakronos_app.frappe_compat.session")
from diakronos_app.models.chat import ChatNachricht, ChatTeilnehmer
from diakronos_app.models.core import HasRole, User
from diakronos_app.models.diakonos import (
    Gruppe,
    Gruppenmitgliedschaft,
    Mitglied,
    Untergruppe,
    Untergruppenmitgliedschaft,
)
from diakronos_app.models.rechte import RechteGruppenrolle, RechteModul

ADMIN = "admin@x.org"
HV = "hv@x.org"
MV = "mv@x.org"
GL = "gl@x.org"
SAENGER = "saenger@x.org"    # Mitglied Chor (nicht in der Untergruppe)
NOTEN = "noten@x.org"        # Mitglied der Untergruppe Notenausschuss
FREMD = "fremd@x.org"        # Gemeindemitglied ohne Gruppe
JUGEND = "jugend@x.org"      # Mitglied einer Gruppe OHNE Chat-Modul


def _set_user(konto: str) -> None:
    """Identität für den Direktaufruf (Test-Naht aus conftest)."""
    _session_mod.set_user(konto)


@pytest.fixture()
def welt(patched_db):
    """Chor mit Untergruppe — dieselbe Welt wie ``test_chat1_rechte.py``."""
    s = patched_db()
    for konto, kurz in [(ADMIN, "Admin"), (HV, "Hv"), (MV, "Mv"), (GL, "Gl"),
                        (SAENGER, "Sa"), (NOTEN, "No"), (FREMD, "Fr"), (JUGEND, "Ju")]:
        s.add(User(name=konto, email=konto, enabled=1, full_name=kurz))
        s.add(Mitglied(name=f"M-{kurz}", vorname=kurz, nachname="X", email=konto, user=konto))
    s.add(HasRole(name="hr-admin", parent=ADMIN, parenttype="User", role="System Manager"))
    s.add(Gruppe(name="Chor", gruppenname="Chor"))
    s.add(Gruppe(name="Jugend", gruppenname="Jugend"))
    s.add(Untergruppe(name="UG-Noten", untergruppenname="Notenausschuss", gruppe="Chor"))
    s.add(Gruppenmitgliedschaft(name="gm1", parent="Chor", parentfield="mitglieder",
                                mitglied="M-Sa"))
    # MV ist ebenfalls Mitglied der Gruppe (Rolle allein zaehlt im Kern als
    # Mitglied, aber eine echte Mitgliedschaft macht die Welt realistisch).
    s.add(Gruppenmitgliedschaft(name="gm2", parent="Chor", parentfield="mitglieder",
                                mitglied="M-Mv"))
    s.add(Untergruppenmitgliedschaft(name="ugm1", parent="UG-Noten",
                                     parentfield="mitglieder", mitglied="M-No"))
    s.add(Gruppenmitgliedschaft(name="gm3", parent="Jugend",
                                parentfield="mitglieder", mitglied="M-Ju"))
    s.add_all([
        RechteGruppenrolle(gruppe="Chor", benutzer=HV, rolle="HV"),
        RechteGruppenrolle(gruppe="Chor", benutzer=MV, rolle="MV"),
        RechteGruppenrolle(gruppe="Chor", untergruppe="UG-Noten", benutzer=GL, rolle="GL"),
        # Chat ist im Chor AN; die Jugend hat das Modul NICHT (Modul aus = Chat aus).
        RechteModul(gruppe="Chor", modul="chat"),
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
    _session_mod.reset_user()
    return name


def _senden(text: str, gespraech: str, konto: str, antwort_auf: str | None = None) -> dict:
    from diakronos_app.api import chat as C

    _set_user(konto)
    return C.senden(gespraech, text, antwort_auf=antwort_auf)


# ── Modell & Lazy-Anlegen ───────────────────────────────────────────────────


def test_lazy_anlegen_ist_ein_gespraech_je_einheit(gespraech):
    """Kein Massen-Insert: das Gespräch entsteht beim ERSTEN Zugriff — und nur einmal."""
    from diakronos_app.api import chat as C
    from diakronos_app.models.chat import ChatGespraech

    _set_user(SAENGER)
    zweite = C.gespraech_anlegen("Chor")["name"]
    assert zweite == gespraech
    with dbmod.SessionLocal() as s:
        assert s.query(ChatGespraech).count() == 1
        zeile = s.get(ChatGespraech, gespraech)
        assert (zeile.art, zeile.gruppe, zeile.untergruppe) == ("gruppe", "Chor", None)


def test_untergruppe_hat_eigenes_gespraech(gespraech):
    """F4: der Untergruppen-Chat ist ein EIGENER Verlauf, kein Reiter im Chor."""
    from diakronos_app.api import chat as C

    _set_user(NOTEN)
    ug = C.gespraech_anlegen("Chor", "UG-Noten")
    assert ug["name"] != gespraech
    assert (ug["art"], ug["untergruppe"]) == ("untergruppe", "UG-Noten")


def test_untergruppe_nur_unter_ihrer_hauptgruppe(gespraech):
    """Review Punkt 1: `gespraech(gruppe=<falsch>, untergruppe=U)` → 403.

    Die Hauptgruppe einer Untergruppe ist IMMER ``untergruppe.gruppe``. Mit
    einer fremden Gruppe liesse sich sonst der Modulschalter der echten
    Hauptgruppe umgehen und ein Streu-Gespraech unter falscher Gruppe anlegen.
    """
    from diakronos_app.api import chat as C
    from diakronos_app.frappe_compat.exceptions import PermissionError

    _set_user(GL)
    # Ohne `gruppe` ist erlaubt: die Hauptgruppe kommt aus der Untergruppe.
    ug = C.gespraech_anlegen(untergruppe="UG-Noten")
    assert (ug["gruppe"], ug["art"]) == ("Chor", "untergruppe")
    assert C.gespraech_anlegen("Chor", "UG-Noten")["name"] == ug["name"]

    # Mit der FALSCHEN Hauptgruppe: 403 ohne Inhalt — auch fuer die Leitung.
    for konto in (GL, HV):
        _set_user(konto)
        with pytest.raises(PermissionError) as fehler:
            C.gespraech_anlegen("Jugend", "UG-Noten")
        assert str(fehler.value) == ""
    with dbmod.SessionLocal() as s:
        from diakronos_app.models.chat import ChatGespraech

        assert s.query(ChatGespraech).filter_by(gruppe="Jugend").count() == 0


def test_teilnahme_entsteht_beim_lesen(gespraech):
    """Wer den Verlauf oeffnet, ist Teilnehmer (Lesestand braucht die Zeile)."""
    from diakronos_app.api import chat as C

    _set_user(SAENGER)
    C.gespraech_anlegen("Chor")
    with dbmod.SessionLocal() as s:
        zeile = s.get(ChatTeilnehmer, (gespraech, SAENGER))
        assert zeile is not None and zeile.stumm is False


# ── Rechte ──────────────────────────────────────────────────────────────────


def test_nichtmitglied_bekommt_403(gespraech):
    """Fremdes Gemeindemitglied (ohne Gruppe) sieht den Chor-Chat nicht."""
    from diakronos_app.api import chat as C
    from diakronos_app.frappe_compat.exceptions import PermissionError

    _set_user(FREMD)
    with pytest.raises(PermissionError) as fehler:
        C.verlauf(gespraech)
    assert str(fehler.value) == ""  # 403 OHNE Inhalt (Karte)
    with pytest.raises(PermissionError) as fehler:
        C.senden(gespraech, "Hallo")
    assert str(fehler.value) == ""


def test_modul_aus_heisst_chat_aus(welt):
    """Ohne Zeile in ``rechte_modul`` gibt es kein Gespräch — auch für Mitglieder."""
    from diakronos_app.api import chat as C
    from diakronos_app.frappe_compat.exceptions import PermissionError

    _set_user(JUGEND)
    with pytest.raises(PermissionError):
        C.gespraech_anlegen("Jugend")


def test_fremde_nachricht_bearbeiten_ist_verboten(gespraech):
    """Autor schreibt — ein anderes MITGLIED darf die Nachricht nicht umschreiben."""
    from diakronos_app.api import chat as C
    from diakronos_app.frappe_compat.exceptions import PermissionError

    n = _senden("Original", gespraech, SAENGER)
    _set_user(MV)
    with pytest.raises(PermissionError):
        C.aendern(n["name"], "Umgeschrieben")
    with pytest.raises(PermissionError):
        C.aendern(n["name"], "Auch die Leitung schreibt nicht um")


def test_leitung_darf_fremde_nachricht_loeschen_mitglied_nicht(gespraech):
    """Fremde Nachricht: HV/MV duerfen entfernen (MODERIEREN), Mitglieder nicht."""
    from diakronos_app.api import chat as C
    from diakronos_app.frappe_compat.exceptions import PermissionError

    n = _senden("Bleibt bitte stehen", gespraech, SAENGER)
    _set_user(NOTEN)  # Untergruppen-Mitglied, im Chor nur Mitglied
    with pytest.raises(PermissionError):
        C.loeschen(n["name"])

    _set_user(HV)
    weg = C.loeschen(n["name"])
    assert weg["geloescht"] is True and weg["text"] is None
    # Der Text bleibt in der Datenbank (Widerspruchsfall), geht aber nicht raus.
    with dbmod.SessionLocal() as s:
        assert s.get(ChatNachricht, n["name"]).text == "Bleibt bitte stehen"
        assert s.get(ChatNachricht, n["name"]).geloescht_von == HV


def test_eigene_nachricht_darf_jeder_loeschen(gespraech):
    """Eigene Nachricht: jederzeit loeschbar (Soft-Delete, Luecke bleibt)."""
    from diakronos_app.api import chat as C

    n = _senden("Meine Nachricht", gespraech, SAENGER)
    _set_user(SAENGER)
    weg = C.loeschen(n["name"])
    assert weg["geloescht"] is True


def test_untergruppe_ist_getrennt(gespraech):
    """F4: Saenger (Hauptgruppe) sieht den Untergruppen-Verlauf NICHT; Noten nicht den Chor-Chat."""
    from diakronos_app.api import chat as C
    from diakronos_app.frappe_compat.exceptions import PermissionError

    _set_user(NOTEN)
    ug = C.gespraech_anlegen("Chor", "UG-Noten")["name"]
    C.senden(ug, "Nur fuer den Ausschuss")

    _set_user(SAENGER)
    with pytest.raises(PermissionError):
        C.verlauf(ug)
    assert [g["name"] for g in C.meine_gespraeche()["gespraeche"]] == [gespraech]

    # Umgekehrt gilt der Rechte-Kern: wer in einer Untergruppe ist, gehoert zur
    # Hauptgruppe (`_person_in_gruppe`) und liest deren Chat — die Liste zeigt
    # ihn deshalb auch (Review 18.11., Liste = genau das Lesbare).
    _set_user(NOTEN)
    liste = [g["name"] for g in C.meine_gespraeche()["gespraeche"]]
    assert sorted(liste) == sorted([ug, gespraech])


def test_gast_sieht_nichts_ueber_http(guest_client, gespraech):
    """Ueber HTTP: ohne Anmeldung gibt es 401/403 — nie einen Verlauf."""
    antwort = guest_client.post(f"/api/method/chat.verlauf?gespraech={gespraech}")
    assert antwort.status_code in (401, 403)
    assert "nachrichten" not in antwort.text


# ── Senden / Bearbeiten ─────────────────────────────────────────────────────


def test_textgrenze_und_zeilenumbrueche(gespraech):
    """≤ 4 000 Zeichen; Absaetze und Einrueckungen bleiben unveraendert."""
    from diakronos_app.api import chat as C
    from diakronos_app.frappe_compat.exceptions import ValidationError

    text = "Erste Zeile\n\n  eingerueckt\nDritte"
    n = _senden(text, gespraech, SAENGER)
    assert n["text"] == text
    assert n["antwort_auf"] is None and n["geloescht"] is False

    zu_lang = "x" * 4001
    with pytest.raises(ValidationError):
        C.senden(gespraech, zu_lang)
    assert _senden("x" * 4000, gespraech, SAENGER)["text"] == "x" * 4000
    with pytest.raises(ValidationError):
        C.senden(gespraech, "   \n  ")


def test_antwort_auf_genau_eine_nachricht(gespraech):
    """``antwort_auf`` zeigt auf eine Nachricht DESSELBEN Gespraechs."""
    from diakronos_app.api import chat as C
    from diakronos_app.frappe_compat.exceptions import DoesNotExistError

    a = _senden("Frage?", gespraech, SAENGER)
    b = _senden("Antwort.", gespraech, HV, antwort_auf=a["name"])
    assert b["antwort_auf"] == a["name"]
    assert b["antwort_auf_text"] == "Frage?"

    _set_user(NOTEN)
    ug = C.gespraech_anlegen("Chor", "UG-Noten")["name"]
    fremd = C.senden(ug, "Aus dem Ausschuss")
    _set_user(SAENGER)
    with pytest.raises(DoesNotExistError):
        C.senden(gespraech, "Zitat aus fremdem Gespraech", antwort_auf=fremd["name"])


def test_bearbeiten_nur_15_minuten(gespraech):
    """Innerhalb 15 Min. mit Kennzeichen; danach ValidationError."""
    from diakronos_app.api import chat as C
    from diakronos_app.frappe_compat.exceptions import ValidationError

    n = _senden("Tippfehler", gespraech, SAENGER)
    _set_user(SAENGER)
    neu = C.aendern(n["name"], "Tippfehler behoben")
    assert neu["text"] == "Tippfehler behoben" and neu["bearbeitet"] is True
    assert neu["bearbeitet_am"] is not None

    # Zeitstempel 16 Minuten zurueckdrehen — wie ein echter alter Beitrag.
    with dbmod.SessionLocal.begin() as s:
        zeile = s.get(ChatNachricht, n["name"])
        zeile.erstellt_am = zeile.erstellt_am - dt.timedelta(minutes=16)
    with pytest.raises(ValidationError) as fehler:
        C.aendern(n["name"], "Zu spaet")
    assert "15 Minuten" in str(fehler.value)


def test_geloeschte_nachricht_nicht_bearbeitbar(gespraech):
    from diakronos_app.api import chat as C
    from diakronos_app.frappe_compat.exceptions import ValidationError

    n = _senden("Weg damit", gespraech, SAENGER)
    _set_user(SAENGER)
    C.loeschen(n["name"])
    with pytest.raises(ValidationError):
        C.aendern(n["name"], "Doch nicht")


# ── Verlauf, Polling ────────────────────────────────────────────────────────


def test_verlauf_vor_und_seit(gespraech):
    """``vor`` liefert Aeltere, ``seit`` Neuere — beide ueber denselben Index."""
    from diakronos_app.api import chat as C

    ids = [_senden(f"Nachricht {i}", gespraech, SAENGER if i % 2 else HV)["name"]
           for i in range(6)]
    _set_user(SAENGER)

    neueste = C.verlauf(gespraech)
    assert [p["name"] for p in neueste["nachrichten"]] == ids  # alt -> neu
    assert neueste["richtung"] == "neueste"

    vor = C.verlauf(gespraech, vor=ids[3])
    assert [p["name"] for p in vor["nachrichten"]] == ids[:3]
    assert vor["richtung"] == "vor"

    seit = C.verlauf(gespraech, seit=ids[2])
    assert [p["name"] for p in seit["nachrichten"]] == ids[3:]
    assert seit["richtung"] == "seit" and seit["seit"] == ids[-1]

    leer = C.verlauf(gespraech, seit=ids[-1])
    assert leer["nachrichten"] == [] and leer["seit"] is None


# ── Reaktion ────────────────────────────────────────────────────────────────


def test_reaktion_einmal_je_person(gespraech):
    """EINE Reaktion je Person und Nachricht: wechseln ersetzt, leer entfernt."""
    from diakronos_app.frappe_compat.exceptions import ValidationError
    from diakronos_app.models.chat import ChatReaktion
    from diakronos_app.api import chat as C

    n = _senden("Stimmung?", gespraech, SAENGER)
    _set_user(HV)
    erste = C.reaktion_setzen(n["name"], "👍")
    assert erste["reaktionen"] == [{"reaktion": "👍", "anzahl": 1, "von_mir": True}]
    # Zweites Zeichen DERSELBEN Person: ersetzt, keine zweite Zeile.
    zweite = C.reaktion_setzen(n["name"], "❤")
    assert [r["reaktion"] for r in zweite["reaktionen"]] == ["❤"]
    with dbmod.SessionLocal() as s:
        assert s.query(ChatReaktion).filter_by(nachricht=n["name"]).count() == 1

    _set_user(MV)
    C.reaktion_setzen(n["name"], "❤")
    _set_user(SAENGER)
    C.reaktion_setzen(n["name"], "✅")
    _set_user(HV)
    stand = C.reaktion_setzen(n["name"], "❤")["reaktionen"]
    assert stand == [{"reaktion": "❤", "anzahl": 2, "von_mir": True},
                     {"reaktion": "✅", "anzahl": 1, "von_mir": False}]

    entfernt = C.reaktion_setzen(n["name"], "")["reaktionen"]
    assert entfernt == [{"reaktion": "❤", "anzahl": 1, "von_mir": False},
                        {"reaktion": "✅", "anzahl": 1, "von_mir": False}]

    with pytest.raises(ValidationError):
        C.reaktion_setzen(n["name"], "🙈")


# ── Lesestand ───────────────────────────────────────────────────────────────


def test_lesestand_nur_als_summe(gespraech):
    """F2: „gelesen von N“ an EIGENEN Nachrichten — keine Namensliste."""
    from diakronos_app.api import chat as C

    n = _senden("Wer liest mit?", gespraech, SAENGER)
    _set_user(HV)
    C.lesestand_setzen(gespraech, n["name"])
    _set_user(MV)
    C.lesestand_setzen(gespraech, n["name"])
    _set_user(SAENGER)
    seite = C.verlauf(gespraech)
    eigene = [p for p in seite["nachrichten"] if p["name"] == n["name"]][0]
    assert eigene["gelesen_von"] == 2
    # Die Antwort enthaelt NUR die Summe — kein Feld mit Namen.
    assert set(eigene) == {"name", "gespraech", "autor", "autor_mitglied", "eigene", "text",
                          "geloescht", "bearbeitet", "bearbeitet_am", "erstellt_am",
                          "antwort_auf", "antwort_auf_text", "reaktionen", "gelesen_von"}
    # `gelesen_von` ist eine ZAHL — in der Antwort steht keine Personenliste.
    assert isinstance(eigene["gelesen_von"], int)


def test_lesestand_ist_kumulativ(gespraech):
    """Wer die neueste Nachricht gelesen hat, hat alles davor gelesen."""
    from diakronos_app.api import chat as C

    a = _senden("eins", gespraech, SAENGER)
    b = _senden("zwei", gespraech, SAENGER)
    _set_user(HV)
    C.lesestand_setzen(gespraech, b["name"])  # nur bis zur zweiten — die erste gilt mit
    _set_user(SAENGER)
    seite = {p["name"]: p for p in C.verlauf(gespraech)["nachrichten"]}
    assert seite[a["name"]]["gelesen_von"] == 1
    assert seite[b["name"]]["gelesen_von"] == 1


def test_ungelesen_zaehler_und_lesen_ohne_ziel(gespraech):
    """Ungelesen zaehlt fremde, nicht geloeschte Nachrichten; ``lesen`` ohne Ziel
    setzt auf die neueste — danach ist der Zaehler 0."""
    from diakronos_app.api import chat as C

    _senden("eins", gespraech, SAENGER)
    _senden("zwei", gespraech, SAENGER)
    _set_user(HV)
    C.lesestand_setzen(gespraech)  # Ausgangsstand
    _senden("drei", gespraech, SAENGER)
    # Der Zeitstempel reist in Sekunden: ohne diese Verschiebung lägen "zwei"
    # (Lesestand) und "drei" in derselben Sekunde, und `erstellt_am > stand`
    # wäre für die neue Nachricht falsch — dieselbe Sekunde gilt als gelesen.
    with dbmod.SessionLocal.begin() as s:
        drei = s.query(ChatNachricht).filter_by(text="drei").one()
        drei.erstellt_am = drei.erstellt_am + dt.timedelta(seconds=1)
    _set_user(HV)
    gespraeche = {g["name"]: g for g in C.meine_gespraeche()["gespraeche"]}
    assert gespraeche[gespraech]["ungelesen"] == 1
    assert gespraeche[gespraech]["titel"] == "Chor"
    assert gespraeche[gespraech]["stumm"] is False
    assert gespraeche[gespraech]["letzte_nachricht"] == "drei"

    assert C.lesestand_setzen(gespraech)["ungelesen"] == 0
    _set_user(SAENGER)
    assert C.meine_gespraeche()["gespraeche"][0]["ungelesen"] == 0  # eigene zaehlen nicht


def test_stumm_schalten_ist_persoenlich(gespraech):
    from diakronos_app.api import chat as C

    _set_user(HV)
    assert C.stumm_setzen(gespraech, True) == {"gespraech": gespraech, "stumm": True}
    _set_user(SAENGER)
    eigene = [g for g in C.meine_gespraeche()["gespraeche"] if g["name"] == gespraech][0]
    assert eigene["stumm"] is False


# ── Review-Nachbesserungen (Punkte 2–5) ─────────────────────────────────────


def test_doppelanlage_wird_abgefangen(gespraech):
    """Review Punkt 2: ein zweiter Anlage-Versuch faellt auf das vorhandene Gespraech.

    Nachgestellt wird das Rennen zweier Erst-Aufrufe: der zweite Anlage-Versuch
    laeuft auf demselben Gespraech in einen ``IntegrityError`` (der partielle
    Unique-Index haelt) — er darf weder 500en noch eine zweite Zeile anlegen.
    """
    from sqlalchemy.exc import IntegrityError

    from diakronos_app.api import chat as C
    from diakronos_app.models.chat import ChatGespraech

    _set_user(SAENGER)
    with dbmod.SessionLocal.begin() as s:
        vorhanden = C._gespraech_holen(s, "Chor")
        assert vorhanden.name == gespraech
        # Der partielle Unique-Index greift auch fuer `untergruppe IS NULL`:
        # eine zweite Zeile derselben Gruppe ist in der Datenbank unmoeglich.
        s.add(ChatGespraech(name="chat-doppel", art="gruppe", gruppe="Chor"))
        with pytest.raises(IntegrityError):
            s.flush()
        s.rollback()

    # Und der Weg im Code: der Savepoint faengt den Fehler, die Sitzung lebt.
    with dbmod.SessionLocal.begin() as s:
        original = C._gespraech_suchen
        aufrufe = {"n": 0}

        def erst_leer_dann_echt(ses, art, gruppe, untergruppe):
            aufrufe["n"] += 1
            return None if aufrufe["n"] == 1 else original(ses, art, gruppe, untergruppe)

        C._gespraech_suchen = erst_leer_dann_echt
        try:
            zweite = C._gespraech_holen(s, "Chor")
        finally:
            C._gespraech_suchen = original
        assert zweite.name == gespraech
    with dbmod.SessionLocal() as s:
        assert s.query(ChatGespraech).filter_by(gruppe="Chor").count() == 1


def test_gelesen_von_nur_an_eigenen_nachrichten(gespraech):
    """Review Punkt 3: an fremden Nachrichten steht ``None``, nicht die Summe."""
    from diakronos_app.api import chat as C

    fremd = _senden("Von Saenger", gespraech, SAENGER)
    eigen = _senden("Von HV", gespraech, HV)
    # HV liest die SAENGER-Nachricht; SAENGER liest die HV-Nachricht.
    _set_user(HV)
    C.lesestand_setzen(gespraech, fremd["name"])
    _set_user(SAENGER)
    C.lesestand_setzen(gespraech, eigen["name"])

    # Sicht des HV: die EIGENE Nachricht traegt die Summe der anderen (1),
    # die fremde steht auf ``None``.
    _set_user(HV)
    seite = {p["name"]: p for p in C.verlauf(gespraech)["nachrichten"]}
    assert seite[eigen["name"]]["eigene"] is True
    assert seite[eigen["name"]]["gelesen_von"] == 1
    assert seite[fremd["name"]]["eigene"] is False
    assert seite[fremd["name"]]["gelesen_von"] is None

    # Und umgekehrt: SAENGER sieht die Summe an SEINER Nachricht, ``None`` an
    # der fremden (HV) — nie die Zahl der anderen.
    _set_user(SAENGER)
    seite = {p["name"]: p for p in C.verlauf(gespraech)["nachrichten"]}
    assert seite[fremd["name"]]["gelesen_von"] == 1
    assert seite[eigen["name"]]["gelesen_von"] is None


def test_ausgetretenes_mitglied_zaehlt_nicht_als_leser(gespraech):
    """Review Punkt 3: eine stehengebliebene Teilnahmezeile zaehlt nicht mehr."""
    from diakronos_app.api import chat as C
    from diakronos_app.models.diakonos import Gruppenmitgliedschaft

    n = _senden("Wer ist noch da?", gespraech, SAENGER)
    _set_user(HV)
    C.lesestand_setzen(gespraech, n["name"])
    _set_user(SAENGER)
    assert C.verlauf(gespraech)["nachrichten"][0]["gelesen_von"] == 1

    # HV verliert die Mitgliedschaft (Rolle und Mitgliedschaft weg) — die
    # Teilnahmezeile mit Lesestand BLEIBT stehen (der Kern raeumt sie nicht ab).
    with dbmod.SessionLocal.begin() as s:
        from diakronos_app.models.rechte import RechteGruppenrolle

        s.query(Gruppenmitgliedschaft).filter_by(parent="Chor", mitglied="M-Mv").delete()
        s.query(RechteGruppenrolle).filter_by(gruppe="Chor", benutzer=HV).delete()
        assert s.get(ChatTeilnehmer, (gespraech, HV)) is not None

    _set_user(SAENGER)
    kopf = [p for p in C.verlauf(gespraech)["nachrichten"] if p["name"] == n["name"]][0]
    assert kopf["gelesen_von"] == 0          # kein aktuelles Mitglied mehr
    liste = [g for g in C.meine_gespraeche()["gespraeche"] if g["name"] == gespraech][0]
    assert liste["teilnehmer"] == 1          # nur Saenger ist noch dabei


def test_verfasser_ohne_mitgliedsdatensatz(welt):
    """Review Punkt 4: Administrator/HV ohne Mitglied duerfen senden (autor NULL)."""
    from diakronos_app.api import chat as C
    from diakronos_app.models.core import User
    from diakronos_app.models.diakonos import Mitglied

    with dbmod.SessionLocal.begin() as s:
        # Konto OHNE Mitgliedsdatensatz, mit Rolle in der Gruppe (MV — HV gibt
        # es je Gruppe nur einmal, und das ist `hv@x.org`).
        s.add(User(name="mv2@x.org", email="mv2@x.org", enabled=1, full_name="Martin Verwaltung"))
        from diakronos_app.models.rechte import RechteGruppenrolle

        s.add(RechteGruppenrolle(gruppe="Chor", benutzer="mv2@x.org", rolle="MV"))

    _set_user("mv2@x.org")
    g = C.gespraech_anlegen("Chor")["name"]
    n = C.senden(g, "Ich habe kein Mitglied")
    assert n["text"] == "Ich habe kein Mitglied"
    assert n["autor_mitglied"] is None
    assert n["autor"] == "Martin Verwaltung"   # Anzeige aus dem Konto
    assert n["eigene"] is True

    # Bearbeiten geht ueber den BESITZ (Konto), nicht ueber ein Mitglied.
    neu = C.aendern(n["name"], "Ich habe kein Mitglied (bearbeitet)")
    assert neu["bearbeitet"] is True

    # Eigene Nachrichten zaehlen nicht als ungelesen — auch ohne Mitgliedsdatensatz.
    # (Geprueft am Ungelesen-Zaehler des Gespraechs, nicht an der Liste: die
    # Liste verlangt `ist_gemeindemitglied`, ein reines Rollenkonto ist das nicht.)
    with dbmod.SessionLocal.begin() as s:
        assert C._ungelesen(s, g, "mv2@x.org") == 0
    with dbmod.SessionLocal() as s:
        from diakronos_app.models.chat import ChatNachricht

        assert s.get(ChatNachricht, n["name"]).autor_benutzer == "mv2@x.org"
        assert s.get(ChatNachricht, n["name"]).autor is None
        assert s.get(Mitglied, "M-Mv2") is None  # es wurde KEIN Mitglied angelegt

        # Und eine fremde Nachricht zaehlt fuer ihn sehr wohl.
    _set_user(SAENGER)
    fremd = C.senden(g, "Vom Saenger")
    with dbmod.SessionLocal.begin() as s:
        assert C._ungelesen(s, g, "mv2@x.org") == 1
    assert fremd["name"]


def test_ungeoeffneter_gruppenchat_steht_in_der_liste(gespraech):
    """Review Punkt 5: lesbaren Chat ohne Oeffnen zeigen — ohne Zeilen anzulegen."""
    from diakronos_app.api import chat as C
    from diakronos_app.models.chat import ChatGespraech

    # Die Jugend bekommt das Chat-Modul; das Gespraech existiert noch NICHT.
    with dbmod.SessionLocal.begin() as s:
        from diakronos_app.models.rechte import RechteModul

        s.add(RechteModul(gruppe="Jugend", modul="chat"))
    with dbmod.SessionLocal() as s:
        assert s.query(ChatGespraech).filter_by(gruppe="Jugend").count() == 0

    _set_user(JUGEND)
    liste = C.meine_gespraeche()["gespraeche"]
    jugend = [g for g in liste if g["gruppe"] == "Jugend" and g["untergruppe"] is None][0]
    assert jugend["name"] is None            # kein Gespraech angelegt
    assert jugend["geoeffnet"] is False
    assert jugend["ungelesen"] == 0
    assert jugend["titel"] == "Jugend"
    assert jugend["teilnehmer"] == 0

    # Auch nach diesem Aufruf gibt es KEINE Zeile (die Liste legt nichts an).
    with dbmod.SessionLocal() as s:
        assert s.query(ChatGespraech).filter_by(gruppe="Jugend").count() == 0
        assert s.query(ChatTeilnehmer).filter_by(benutzer=JUGEND).count() == 0

    # Ein Tipp auf die Gruppe legt sie an — ab dann mit Kennung.
    _set_user(JUGEND)
    name = C.gespraech_anlegen("Jugend")["name"]
    jugend = [g for g in C.meine_gespraeche()["gespraeche"] if g["name"] == name][0]
    assert jugend["geoeffnet"] is True


def test_ungelesen_bei_ungeoeffnetem_gespraech_zaehlt_ab_beiritt(gespraech):
    """Review Punkt 5: ohne Oeffnen zaehlt alles seit dem Beitritt."""
    from diakronos_app.api import chat as C

    # MV schreibt zwei Nachrichten in den Chor-Chat.
    _senden("eins", gespraech, MV)
    _senden("zwei", gespraech, MV)

    # Neu dabei: Saenger2 ist seit einer Stunde Mitglied, hat nie geoeffnet.
    with dbmod.SessionLocal.begin() as s:
        from diakronos_app.models.core import User
        from diakronos_app.models.diakonos import Gruppenmitgliedschaft, Mitglied

        s.add(User(name="sa2@x.org", email="sa2@x.org", enabled=1, full_name="Sa Zwei"))
        s.add(Mitglied(name="M-Sa2", vorname="Sa", nachname="Zwei", email="sa2@x.org",
                       user="sa2@x.org"))
        s.add(Gruppenmitgliedschaft(name="gm-sa2", parent="Chor", parentfield="mitglieder",
                                    mitglied="M-Sa2", beitrittsdatum=dt.date(2020, 1, 1)))

    _set_user("sa2@x.org")
    eintrag = [g for g in C.meine_gespraeche()["gespraeche"] if g["name"] == gespraech][0]
    assert eintrag["geoeffnet"] is True      # das Gespraech gibt es schon (von Saenger)
    assert eintrag["ungelesen"] == 2         # beide fremden Nachrichten
    assert eintrag["teilnehmer"] == 2        # Saenger (geoeffnet) + MV (geschrieben)

    # Lesestand setzen → 0.
    assert C.lesestand_setzen(gespraech)["ungelesen"] == 0


# ── HTTP-Weg (Registry) ─────────────────────────────────────────────────────


def test_http_weg_senden_und_verlauf(welt, client, fake_redis):
    """Ueber ``/api/method/chat.*`` — derselbe Endpunkt, Frappe-Envelope."""
    from diakronos_app.api import chat as C

    _set_user(SAENGER)
    name = C.gespraech_anlegen("Chor")["name"]
    _session_mod.reset_user()

    antwort = client.post("/api/method/chat.senden",
                          json={"gespraech": name, "text": "Hallo aus dem Chor"})
    assert antwort.status_code == 200, antwort.text
    gesendet = antwort.json()["message"]
    # `autor` ist der ANZEIGENAME (die Spalte traegt die Mitglied-Kennung);
    # `autor_mitglied` sagt der Oberflaeche, ob es die eigene Nachricht ist.
    # Der Client gehoert dem KONTO `Administrator`. `rechte.eigenes_mitglied`
    # liefert dafuer "" (der Kern behandelt ihn als Admin, nicht als Mitglied;
    # dieselbe Aufloesung wie in ``_meine_kennung``). Hier zaehlt der WEG:
    # der Aufruf geht durch die Registry, die Identitaet kommt aus der Sitzung,
    # und die Antwort hat die Form der Direktaufrufe.
    assert gesendet["text"] == "Hallo aus dem Chor"
    # Besitz = das KONTO; `autor` (Anzeige) ist leer, weil der Administrator
    # keinen Mitgliedsdatensatz hat — und `eigene` sagt der Oberflaeche, dass
    # es die eigene Nachricht ist (Review Punkt 4).
    assert gesendet["autor_mitglied"] is None
    assert gesendet["autor"] == "Administrator"   # Anzeige aus dem Konto
    assert gesendet["eigene"] is True
    assert "autor" in gesendet and gesendet["gespraech"] == name

    seite = client.post("/api/method/chat.verlauf", json={"gespraech": name})
    assert seite.status_code == 200, seite.text
    assert [p["name"] for p in seite.json()["message"]["nachrichten"]] == [gesendet["name"]]

    # verlauf ist rein lesend (SEC-11) — die Kurzform per GET geht.
    kurz = client.get(f"/api/method/chat.verlauf?gespraech={name}")
    assert kurz.status_code == 200, kurz.text


def test_liste_ergaenzt_hauptgruppe_und_geerbte_untergruppen(gespraech):
    """Review 18.11.: Untergruppenmitglied sieht den Gruppenchat, HV die
    Untergruppen-Chats — ein einfaches Mitglied NICHT den Untergruppen-Chat."""
    from diakronos_app.api import chat as C

    def einheiten(konto):
        _set_user(konto)
        return {(g["gruppe"], g["untergruppe"]) for g in C.meine_gespraeche()["gespraeche"]}

    assert ("Chor", None) in einheiten(NOTEN)
    assert ("Chor", "UG-Noten") in einheiten(NOTEN)
    assert ("Chor", "UG-Noten") in einheiten(HV)
    assert ("Chor", "UG-Noten") not in einheiten(SAENGER)
    assert ("Chor", None) in einheiten(SAENGER)
