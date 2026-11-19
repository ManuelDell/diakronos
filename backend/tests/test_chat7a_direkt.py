"""CHAT-7a: Direktnachrichten 1:1 (Backend) — Konzept S3, 2.4, 2.5, 3.3, 10.1/4.

Geprüft wird gegen die ECHTEN Endpunkte (``api/chat.py``), den ECHTEN
Rechte-Kern (``rechte/kern.py``) und die ECHTE Datenbank — keine Attrappe:

  * Anlegen/Fortsetzen: NIE ein zweites Gespräch je Personenpaar — auch nicht
    bei vertauschter Reihenfolge, bei erneutem Öffnen oder bei einem Rennen
    (IntegrityError im Savepoint abgefangen)
  * Dritte lesen NICHT (auch nicht HV/MV, auch nicht der Administrator):
    Verlauf, Senden, Reaktion, Lesestand, Stumm, Umfrage, Melden → 403 leer
  * Gegenüber ausgetreten/gesperrt → Verlauf LESBAR, Senden 403
  * an eine Person ohne Konto → 403, an sich selbst → 403, Gast → 403
  * Meldung aus einem Direktgespräch: NUR die Meldestelle (Administrator)
    bekommt die Glocke und sieht die Meldung in der Liste, HV sieht sie nicht
  * Personensuche liefert die Kennung eines vorhandenen Gesprächs
  * DSGVO: Konto gelöscht → Teilnahme fällt, Nachrichten bleiben zugeordnet,
    das Kontenpaar wird geleert
  * SEC-11: ``direkt_oeffnen`` ist schreibend (POST, Verbname)

Aufruf (Karte):
    docker run --rm --network none --entrypoint python -v <wt>:/repo:ro \\
      -w /repo/backend -e PYTHONPATH=/repo/backend/src:/repo/backend/tests:/repo/tools \\
      -e PYTHONDONTWRITEBYTECODE=1 <vorbau> -m pytest -q -p no:cacheprovider \\
      tests/test_chat7a_direkt.py
"""

from __future__ import annotations

import datetime as dt
import importlib
import json
from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory

from diakronos_app import db as dbmod
from diakronos_app.models.chat import (
    ART_DIREKT,
    ChatGespraech,
    ChatNachricht,
    ChatTeilnehmer,
)
from diakronos_app.models.core import HasRole, NotificationLog, User
from diakronos_app.models.diakonos import Mitglied

#: Die Test-Naht liegt im MODUL ``frappe_compat.session`` (wie ``test_chat2_api``).
_session_mod = importlib.import_module("diakronos_app.frappe_compat.session")

BACKEND = Path(__file__).resolve().parents[1]

ANNA = "anna@x.org"          # Gemeindemitglied mit Konto
BERT = "bert@x.org"          # Gemeindemitglied mit Konto
CLARA = "clara@x.org"        # Gemeindemitglied, tritt gleich aus
OHNE = "ohne@x.org"          # Mitglied OHNE Konto-Verknüpfung (kein Gegenüber)
HV = "hv@x.org"              # Gruppenleitung (darf in 1:1 NICHT mitlesen)
ADMIN = "admin@x.org"        # Administrator = Meldestelle (F7)


def _set_user(konto: str) -> None:
    _session_mod.set_user(konto)


@pytest.fixture()
def welt(patched_db):
    """Vier Mitglieder + Konten, ein Administrator mit ``System Manager``."""
    s = patched_db()
    # ``Administrator`` ist der Systembenutzer der Installation: die Meldestelle
    # (F7) IST dieses Konto — ohne die User-Zeile gäbe es sie nicht.
    s.add(User(name="Administrator", email="admin@example.invalid", enabled=1,
               full_name="Administrator"))
    for konto, kurz in [(ANNA, "Anna"), (BERT, "Bert"), (CLARA, "Clara"),
                        (OHNE, "Olaf"), (HV, "Hanna"), (ADMIN, "Admin")]:
        s.add(User(name=konto, email=konto, enabled=1, full_name=kurz))
    s.add_all([
        Mitglied(name="M-Anna", vorname="Anna", nachname="Beispiel",
                 email=ANNA, user=ANNA, status="Aktiv"),
        Mitglied(name="M-Bert", vorname="Bert", nachname="Brandner",
                 email=BERT, user=BERT, status="Aktiv"),
        Mitglied(name="M-Clara", vorname="Clara", nachname="Clausen",
                 email=CLARA, user=CLARA, status="Aktiv"),
        # Person OHNE Konto-Verknüpfung: auffindbar, aber nicht beschreibbar.
        Mitglied(name="M-Ohne", vorname="Olaf", nachname="Ohnberg",
                 email=OHNE, user=None, status="Aktiv"),
        Mitglied(name="M-Hv", vorname="Hanna", nachname="Hofmann",
                 email=HV, user=HV, status="Aktiv"),
    ])
    s.add(HasRole(name="hr-admin", parent=ADMIN, parenttype="User",
                  role="System Manager"))
    s.commit()
    yield s
    s.close()


# ── Aufruf-Hilfen ───────────────────────────────────────────────────────────


def _oeffnen(mitglied: str, konto: str = ANNA) -> dict:
    from diakronos_app.api import chat as C

    _set_user(konto)
    return C.direkt_oeffnen(mitglied)


def _senden(gespraech: str, text: str, konto: str) -> dict:
    from diakronos_app.api import chat as C

    _set_user(konto)
    return C.senden(gespraech, text)


def _verlauf(gespraech: str, konto: str, **kwargs) -> dict:
    from diakronos_app.api import chat as C

    _set_user(konto)
    return C.verlauf(gespraech, **kwargs)


def _meine(konto: str) -> dict:
    from diakronos_app.api import chat as C

    _set_user(konto)
    return C.meine_gespraeche()


def _kopf(gespraech: str) -> dict:
    return {e["name"]: e for e in _meine(ANNA)["gespraeche"]}[gespraech]


# ── 1) Anlegen und Fortsetzen ───────────────────────────────────────────────


def test_oeffnen_legt_genau_ein_gespraech_je_personenpaar_an(welt):
    """Zweimal öffnen (auch aus der Gegenrichtung) → dieselbe Zeile."""
    from diakronos_app.api import chat as C

    erst = _oeffnen("M-Bert", ANNA)
    assert erst["art"] == ART_DIREKT
    assert erst["gruppe"] is None and erst["untergruppe"] is None
    # Titel = Anzeigename des Gegenübers aus der BESTEHENDEN Namensquelle
    # (``personen_anzeige.kuerze_name``: „Vorname N.“ — dieselbe Form, die
    # Suche und Adressbuch liefern; bei Gelöschten „Gelöschte Person“).
    assert erst["titel"] == "Bert B."
    assert erst["mitglied"] == "M-Bert"

    # Gegenrichtung: BERT öffnet ANNA → DASSELBE Gespräch.
    zurueck = _oeffnen("M-Anna", BERT)
    assert zurueck["name"] == erst["name"]
    # Und noch einmal von vorn.
    assert _oeffnen("M-Bert", ANNA)["name"] == erst["name"]

    with dbmod.SessionLocal() as s:
        zeilen = s.query(ChatGespraech).filter(ChatGespraech.art == ART_DIREKT).all()
        assert len(zeilen) == 1
        assert zeilen[0].paar_schluessel == f"anna@x.org{C.PAAR_TRENNER}bert@x.org"
        # BEIDE Teilnahmezeilen sind da — der Raum sind die Teilnehmenden.
        assert sorted(k for k, in s.query(ChatTeilnehmer.benutzer)
                      .filter(ChatTeilnehmer.gespraech == zeilen[0].name).all()) == \
            sorted([ANNA, BERT])


def test_paar_schluessel_sortiert_unabhaengig_von_der_reihenfolge(welt):
    from diakronos_app.api import chat as C

    assert C._paar_schluessel(BERT, ANNA) == C._paar_schluessel(ANNA, BERT)
    # Kein NUL-Byte: PostgreSQL-Textfelder verbieten es (PG-Lauf deckte das auf).
    assert "\x00" not in C._paar_schluessel(ANNA, BERT)
    # Getrennt mit \x1f: keine Verwechslung benachbarter Namen.
    assert C._paar_schluessel("ab", "c") != C._paar_schluessel("a", "bc")


def test_rennen_zweier_aufrufe_erzeugt_eine_zeile(welt, monkeypatch):
    """Zwei GLEICHZEITIGE Aufrufe: der Verlierer liest die Zeile des Gewinners.

    Nachgestellt wird das Rennen an der Naht, die der Endpunkt WIRKLICH
    benutzt (``_direkt_holen``): der Rivale legt VOR dem eigenen Savepoint
    dieselbe Paar-Zeile in einer eigenen Transaktion an. Danach greift der
    Unique-Index ``uq_chat_gespraech_paar``, der ``IntegrityError`` wird
    abgefangen und die vorhandene Zeile zurückgegeben — Ergebnis: EINE Zeile,
    keine 500.
    """
    from diakronos_app.api import chat as C
    from diakronos_app.models.chat import ChatGespraech as G

    echt = C._gespraech_mit_paar
    zustand = {"rivale": False}

    def _mit_rivalen(s, konto_a, konto_b):
        if not zustand["rivale"]:
            zustand["rivale"] = True
            with dbmod.SessionLocal.begin() as fremd:
                jetzt = dt.datetime(2026, 11, 19, 9, 0, 0)
                fremd.add(G(name="chat-gespraech-rivale", art=ART_DIREKT,
                            gruppe=None, untergruppe=None,
                            paar_schluessel=C._paar_schluessel(konto_a, konto_b),
                            angelegt_von=konto_a, angelegt_am=jetzt))
                fremd.flush()
                for konto in (konto_a, konto_b):
                    fremd.add(ChatTeilnehmer(gespraech="chat-gespraech-rivale",
                                             benutzer=konto, stumm=False,
                                             hinzugefuegt_am=jetzt))
        return echt(s, konto_a, konto_b)

    monkeypatch.setattr(C, "_gespraech_mit_paar", _mit_rivalen)
    antwort = _oeffnen("M-Bert", ANNA)
    assert antwort["name"] == "chat-gespraech-rivale"
    assert zustand["rivale"] is True
    with dbmod.SessionLocal() as s:
        assert s.query(ChatGespraech).filter(ChatGespraech.art == ART_DIREKT).count() == 1


def test_datenbank_erzwingt_ein_gespraech_je_paar(welt):
    """Die Regel steht in der DATENBANK, nicht nur im Endpunkt."""
    from sqlalchemy.exc import IntegrityError

    from diakronos_app.api import chat as C

    _oeffnen("M-Bert", ANNA)
    with pytest.raises(IntegrityError):
        with dbmod.SessionLocal.begin() as s:
            s.add(ChatGespraech(name="chat-gespraech-doppelt", art=ART_DIREKT,
                                gruppe=None, untergruppe=None,
                                paar_schluessel=C._paar_schluessel(ANNA, BERT),
                                angelegt_am=dt.datetime(2026, 11, 19, 10)))


# ── 2) Wer darf schreiben, wer nicht ────────────────────────────────────────

def _h_leer(fn, *args, **kwargs):
    from diakronos_app.frappe_compat.exceptions import PermissionError

    with pytest.raises(PermissionError) as fehler:
        try:
            fn(*args, **kwargs)
        except AssertionError:      # pragma: no cover — Diagnose
            print(f"DEBUG-ASSERT {fn.__name__}{args}")
            raise
        except PermissionError:
            raise
        except Exception as ausnahme:   # pragma: no cover — Diagnose
            print(f"DEBUG {fn.__name__}{args} -> {type(ausnahme).__name__}: {ausnahme}")
            raise
    # 403 OHNE Inhalt: der Grund bleibt im Server.
    assert not str(fehler.value or "")


def test_an_sich_selbst_und_an_person_ohne_konto_ist_verboten(welt):
    from diakronos_app.api import chat as C

    _set_user(ANNA)
    _h_leer(C.direkt_oeffnen, "M-Anna")            # an sich selbst
    _h_leer(C.direkt_oeffnen, "M-Ohne")            # Person ohne Konto
    _h_leer(C.direkt_oeffnen, "M-Gibtsnicht")
    with dbmod.SessionLocal() as s:
        assert s.query(ChatGespraech).filter(ChatGespraech.art == ART_DIREKT).count() == 0


def test_gast_und_fremdes_konto_oeffnen_nichts(welt):
    from diakronos_app.api import chat as C

    for wer in ("Guest", "", "niemand@x.org"):
        _set_user(wer)
        _h_leer(C.direkt_oeffnen, "M-Bert")
    with dbmod.SessionLocal() as s:
        assert s.query(ChatGespraech).filter(ChatGespraech.art == ART_DIREKT).count() == 0


def test_verlauf_senden_reaktion_lesestand_stumm_fuer_beide(welt):
    """Die BESTEHENDEN Endpunkte arbeiten für ``art = direkt`` über die Weiche."""
    from diakronos_app.api import chat as C

    g = _oeffnen("M-Bert", ANNA)["name"]
    n = _senden(g, "Hallo Bert", ANNA)
    assert n["text"] == "Hallo Bert" and n["eigene"] is True

    antwort = _senden(g, "Hallo Anna", BERT)
    assert antwort["text"] == "Hallo Anna"
    assert [p["text"] for p in _verlauf(g, ANNA)["nachrichten"]] == \
        ["Hallo Bert", "Hallo Anna"]

    # Reaktion, Lesestand, Stumm — alles LESEN bzw. eigenes.
    _set_user(BERT)
    assert C.reaktion_setzen(n["name"], "👍")["reaktionen"][0]["reaktion"] == "👍"
    assert C.lesestand_setzen(g)["ungelesen"] == 0
    assert C.stumm_setzen(g, True)["stumm"] is True
    # „Gelesen“ im 1:1 = Summe 1 (Konzept F2: die Summe, bei 1:1 ist sie 1).
    posten = {p["name"]: p for p in _verlauf(g, ANNA)["nachrichten"]}
    assert posten[n["name"]]["gelesen_von"] == 1


def test_eigene_nachricht_aendern_und_loeschen(welt):
    from diakronos_app.api import chat as C
    from diakronos_app.frappe_compat.exceptions import PermissionError

    g = _oeffnen("M-Bert", ANNA)["name"]
    n = _senden(g, "Tippfehler", ANNA)
    _set_user(ANNA)
    assert C.aendern(n["name"], "Tippfehler behoben")["bearbeitet"] is True

    _set_user(BERT)
    with pytest.raises(PermissionError):
        C.aendern(n["name"], "fremd umgeschrieben")
    _set_user(ANNA)
    assert C.loeschen(n["name"])["geloescht"] is True


# ── 3) Dritte lesen nicht ───────────────────────────────────────────────────

def test_dritte_lesen_nicht_auch_nicht_hv_und_admin(welt):
    """F7/S3: niemand sonst liest mit — auch die Leitung und der Admin nicht."""
    from diakronos_app.api import chat as C

    g = _oeffnen("M-Bert", ANNA)
    n = _senden(g["name"], "Nur für Bert", ANNA)

    for wer in (HV, ADMIN, CLARA, OHNE):
        _set_user(wer)
        # Kein einziger Zugriff auf das FREMDDE Gespräch — weder Inhalt noch
        # Reaktion, Lesestand oder Stumm.
        _h_leer(C.verlauf, g["name"])
        _h_leer(C.senden, g["name"], "Ich lese mit")
        _h_leer(C.reaktion_setzen, n["name"], "👍")
        _h_leer(C.lesestand_setzen, g["name"])
        _h_leer(C.stumm_setzen, g["name"], True)
        # Und es entsteht dabei KEINE Teilnahmezeile (sonst wäre der Verlauf
        # beim nächsten Versuch lesbar).
        with dbmod.SessionLocal() as s:
            assert s.get(ChatTeilnehmer, (g["name"], wer)) is None, wer

    # Der Administrator sieht das Gespräch AUCH NICHT in seiner Liste.
    assert [e for e in _meine(ADMIN)["gespraeche"] if e["art"] == ART_DIREKT] == []
    assert [e for e in _meine(HV)["gespraeche"] if e["art"] == ART_DIREKT] == []
    # Die Beteiligten sehen es.
    for wer in (ANNA, BERT):
        eintrag = [e for e in _meine(wer)["gespraeche"] if e["name"] == g["name"]]
        assert len(eintrag) == 1
        assert eintrag[0]["titel"] == ("Bert B." if wer == ANNA else "Anna B.")
        assert eintrag[0]["teilnehmer"] == 2
    # Ein fremdes PAAR bleibt fremd: nur die beiden 1:1 mit ihren Teilnehmern.
    with dbmod.SessionLocal() as s:
        assert s.query(ChatGespraech).filter(
            ChatGespraech.art == ART_DIREKT).count() == 1
        assert sorted(k for k, in s.query(ChatTeilnehmer.benutzer).filter(
            ChatTeilnehmer.gespraech == g["name"]).all()) == sorted([ANNA, BERT])


def test_verlauf_eines_fremden_gespraechs_ist_403_nicht_404(welt):
    """Bestehende Kennung, kein Recht → 403 leer (nichts über den Inhalt raten)."""
    from diakronos_app.api import chat as C

    g = _oeffnen("M-Bert", ANNA)["name"]
    _set_user(CLARA)
    _h_leer(C.verlauf, g)      # als Clara (nicht beteiligt)
    # Unbekannte Kennung bleibt 404 — wie bisher.
    from diakronos_app.frappe_compat.exceptions import DoesNotExistError

    _set_user(CLARA)
    with pytest.raises(DoesNotExistError):
        C.verlauf("chat-gespraech-gibtsnicht")


# ── 4) Ausgetreten / gesperrt: lesbar, aber stumm ───────────────────────────

def _mitglied_status(s, mitglied: str, **werte) -> None:
    from diakronos_app.models.diakonos import Mitglied as M

    s.query(M).filter_by(name=mitglied).update(werte)
    s.commit()


def test_ausgetretenes_gegenueber_verlauf_lesbar_senden_verboten(welt):
    from diakronos_app.api import chat as C
    from diakronos_app.frappe_compat.exceptions import PermissionError

    g = _oeffnen("M-Bert", ANNA)["name"]
    _senden(g, "Vor dem Austritt", BERT)
    _mitglied_status(welt, "M-Bert", status="Ausgetreten")

    # ANNA liest weiter (der Verlauf gehört ihr mit).
    assert [p["text"] for p in _verlauf(g, ANNA)["nachrichten"]] == ["Vor dem Austritt"]
    # Senden ist gesperrt: niemand ist mehr erreichbar (Kern: „niemand_erreichbar“).
    _set_user(ANNA)
    with pytest.raises(PermissionError):
        C.senden(g, "Bist du noch da?")
    # BERT kommt mit seinem (noch aktiven) Konto weiter an den gemeinsamen
    # Verlauf: es ist SEIN Gespräch, und der Kern lässt LESEN für Teilnehmende
    # mit gültigem Konto zu — gesperrt ist nur das SCHREIBEN (oben). Erst mit
    # dem Konto endet auch das Lesen (Test „gesperrtes Gegenüber“/DSGVO).
    assert [p["text"] for p in _verlauf(g, BERT)["nachrichten"]] == ["Vor dem Austritt"]


def test_gesperrtes_gegenueber_konto_verlauf_lesbar_senden_verboten(welt):
    """Konto deaktiviert = „kein Konto“: lesbar, aber stumm (Kern-Regel)."""
    from diakronos_app.api import chat as C
    from diakronos_app.frappe_compat.exceptions import PermissionError

    g = _oeffnen("M-Bert", ANNA)["name"]
    _senden(g, "Hallo", BERT)
    welt.query(User).filter(User.name == BERT).update({"enabled": 0})
    welt.commit()

    assert len(_verlauf(g, ANNA)["nachrichten"]) == 1
    _set_user(ANNA)
    with pytest.raises(PermissionError):
        C.senden(g, "noch da?")
    # Das Gegenüber selbst kommt gar nicht mehr an seinen Verlauf.
    _set_user(BERT)
    _h_leer(C.verlauf, g)


# ── 5) Meldung aus dem Direktgespräch → nur die Meldestelle ─────────────────

def _glocken(meldung: str) -> dict[str, NotificationLog]:
    with dbmod.SessionLocal() as s:
        return {z.for_user: z for z in s.query(NotificationLog).filter(
            NotificationLog.document_type == "chat_meldung",
            NotificationLog.document_name == meldung).all()}


def test_meldung_geht_nur_an_die_meldestelle(welt):
    from diakronos_app.api import chat as C

    g = _oeffnen("M-Bert", ANNA)["name"]
    n = _senden(g, "Das ist nicht in Ordnung", BERT)
    _set_user(ANNA)
    gemeldet = C.meldung_senden(n["name"], "beleidigung", freitext="so nicht")
    assert gemeldet["stand"] == "offen"

    # Glocke: NUR die Meldestelle, nicht HV, nicht der Melder. Die Meldestelle
    # ist ``rechte.ist_meldestelle`` — hier das Systemkonto ``Administrator``
    # und das Konto der Person mit der Rolle ``System Manager``.
    assert set(_glocken(gemeldet["name"])) == {ADMIN, "Administrator"}
    inhalt = str(_glocken(gemeldet["name"])[ADMIN].email_content or "")
    # Ohne Nachrichtentext und ohne Absender (Konzept 2.5).
    assert "nicht in Ordnung" not in inhalt
    assert BERT not in inhalt

    # Der Administrator SIEHT die Meldung in der Liste — mit dem Ausschnitt.
    _set_user(ADMIN)
    liste = C.meldungen_liste()
    eintrag = [e for e in liste["meldungen"] if e["name"] == gemeldet["name"]]
    assert len(eintrag) == 1
    assert eintrag[0]["nachricht"]["text"] == "Das ist nicht in Ordnung"
    assert eintrag[0]["gespraech"] == g
    assert eintrag[0]["melder_konto"] == ANNA

    # HV sieht sie NICHT (kein Recht an einem Direktgespräch) — und auch
    # keine leere Liste mit Glocke: 403 ohne Inhalt.
    from diakronos_app.frappe_compat.exceptions import PermissionError

    _set_user(HV)
    with pytest.raises(PermissionError):
        C.meldungen_liste()

    # Die Meldestelle entscheidet: entfernen setzt Soft-Delete + Grund.
    _set_user(ADMIN)
    entschieden = C.meldung_entscheiden(gemeldet["name"], "entfernen",
                                        grund="Regelverstoß")
    assert entschieden["stand"] == "erledigt"
    posten = {p["name"]: p for p in _verlauf(g, ANNA)["nachrichten"]}
    assert posten[n["name"]]["geloescht"] is True
    assert posten[n["name"]]["text"] is None
    # Die verfassende Person wird geglockt — ohne den Namen des Melders.
    with dbmod.SessionLocal() as s:
        entfernt = s.query(NotificationLog).filter(
            NotificationLog.for_user == BERT,
            NotificationLog.document_type == "chat_nachricht",
            NotificationLog.document_name == n["name"]).all()
    assert len(entfernt) == 1
    assert ANNA not in str(entfernt[0].email_content or "")


def test_meldestelle_ohne_gruppe_bekommt_keine_403_auf_die_liste(welt):
    """Der Administrator hat keine Gruppenrolle: die Liste bleibt leer, kein 403.

    Die Meldestelle ist für DIREKTGESPRÄCHE zuständig (F7); sie bekommt also
    eine (leere) Liste statt 403 — Gruppenmeldungen sieht sie wie bisher nicht.
    """
    from diakronos_app.api import chat as C

    _set_user(ADMIN)
    assert C.meldungen_liste() == {"meldungen": [], "offen": 0}
    assert C.meldungen_liste(stand="erledigt") == {"meldungen": [], "offen": 0}


def _altern(gespraech: str) -> None:
    """Nachrichten UND Beitritte auf den 19.11.2026 09:00 zurückdatieren.

    Die Ruhezeit (5 Minuten) wird gegen ``erstellt_am`` gemessen, der
    Ungelesen-Zähler gegen ``hinzugefuegt_am`` der Teilnahme — beide müssen
    altern, sonst gilt die Nachricht als „vor dem Beitritt“ und zählt nicht.
    Ein fester Zeitpunkt, kein ``sleep``.
    """
    from diakronos_app.api import chat as C

    zeit = dt.datetime(2026, 11, 19, 9, 0, 0)
    with dbmod.SessionLocal.begin() as s:
        s.execute(C.update(ChatNachricht)
                  .where(ChatNachricht.gespraech == gespraech)
                  .values(erstellt_am=zeit))
        s.execute(C.update(ChatTeilnehmer)
                  .where(ChatTeilnehmer.gespraech == gespraech)
                  .values(hinzugefuegt_am=zeit))


# ── 5b) Gebündelte Glocke (CHAT-4a) für Direktgespräche ────────────────────

def test_buendelglocke_erreicht_das_direktgespraech(welt):
    """Die Glocke aus CHAT-4a ist art-unabhängig — und glockt NUR Teilnehmende.

    Geprüft wird der ECHTE Job (``chat_glocken_buendeln``): ANNA schreibt,
    BERT bekommt nach der Ruhezeit EINE Glocke, die dritte Person keine — der
    Rechte-Recheck läuft über ``_darf_lesen`` → ``darf_direktgespraech``.
    """
    from diakronos_app.api import chat as C

    g = _oeffnen("M-Bert", ANNA)["name"]
    _senden(g, "Hallo Bert", ANNA)
    _altern(g)
    assert C.chat_glocken_buendeln(jetzt=dt.datetime(2026, 11, 19, 10, 0, 0)) == 1
    with dbmod.SessionLocal() as s:
        glocken = s.query(NotificationLog).filter(
            NotificationLog.document_type == "chat_gespraech",
            NotificationLog.document_name == g).all()
    assert [z.for_user for z in glocken] == [BERT]


# ── 6) Personensuche und Gesprächskennung ──────────────────────────────────

def test_suche_liefert_die_gespraechskennung(welt):
    from diakronos_app.api import chat as C

    _set_user(ANNA)
    ohne = C.personen_suchen(q="bert")["treffer"][0]
    assert ohne["darf_schreiben"] is True
    assert ohne["gespraech"] is None            # noch kein Gespräch

    g = _oeffnen("M-Bert", ANNA)["name"]
    mit = C.personen_suchen(q="bert")["treffer"][0]
    assert mit["gespraech"] == g
    # Die Suche legt NICHTS an: ein Treffer auf eine dritte Person bleibt None.
    assert C.personen_suchen(q="clara")["treffer"][0]["gespraech"] is None


def test_suche_zeigt_keine_gespraechskennung_ohne_teilnahme(welt):
    """Ein Gespräch zwischen anderen taucht bei der Suche nicht als Kennung auf."""
    from diakronos_app.api import chat as C

    # BERT ↔ CLARA — ANNA ist daran NICHT beteiligt.
    _oeffnen("M-Clara", BERT)
    _set_user(ANNA)
    assert C.personen_suchen(q="clara")["treffer"][0]["gespraech"] is None


# ── 7) DSGVO: Konto gelöscht ───────────────────────────────────────────────

def test_anonymisierung_ueber_das_echte_anonymiere(welt):
    """Konto weg → Teilnahme fällt, Nachrichten bleiben, Titel „Gelöschte Person“.

    Gefahren wird das ECHTE ``anonymisiere()`` — nicht Teilschritte von Hand.
    Damit hängt der Test an der Reihenfolge im Modul (Schritt 4 nimmt die
    Teilnahmezeile mit dem Konto mit, Schritt 6a leert das Kontenpaar).
    """
    from diakronos_app import dsgvo_anonymisierung as D

    g = _oeffnen("M-Bert", ANNA)["name"]
    _senden(g, "Bis bald", BERT)
    _senden(g, "Tschüss", ANNA)

    with dbmod.SessionLocal.begin() as s:
        ergebnis = D.anonymisiere(s, "M-Bert", [BERT])
    assert ergebnis["zaehler"].get("chat_gespraech.paar_schluessel") == 1

    with dbmod.SessionLocal() as s:
        zeile = s.get(ChatGespraech, g)
        assert zeile.paar_schluessel is None             # kein Personenbezug mehr
        assert zeile.art == ART_DIREKT                   # das Gespräch bleibt
        # Teilnahme der Person ist gefallen (Konto-Spalte), ANNA bleibt.
        assert sorted(k for k, in s.query(ChatTeilnehmer.benutzer).filter(
            ChatTeilnehmer.gespraech == g).all()) == [ANNA]
        # Nachrichten bleiben erhalten; die des Kontos tragen kein Konto mehr
        # (die Konto-Spalte ist `user_null`), der Verlauf selbst bleibt lesbar.
        assert s.query(ChatNachricht).filter(
            ChatNachricht.gespraech == g).count() == 2
        # Das Kontenpaar ist geleert (CHAT-7a-Schritt 6a) — der Titel kommt
        # deshalb aus der fehlenden Teilnahme, nicht aus dem Schlüssel.
        bleibt_paar = zeile.paar_schluessel is not None

    eintrag = {e["name"]: e for e in _meine(ANNA)["gespraeche"]}[g]
    # „teilnehmer“ zählt AKTUELLE Angehörige über den Kern: 1.
    assert eintrag["teilnehmer"] == 1
    # Titel: der neutrale Text „Gelöschte Person“ — NIE die Kennung, NIE der
    # Name, NIE die Adresse.
    assert eintrag["titel"] == "Gelöschte Person", eintrag["titel"]
    for verboten in ("Bert", "Brandner", "@", "geloescht-"):
        assert verboten not in eintrag["titel"], eintrag["titel"]
    assert eintrag["bild"] in ("", None)


def test_anonymisierung_ohne_paar_schluessel_bleibt_leer(welt):
    """Ist auch ``paar_schluessel`` schon weg, bleibt der Titel LEER (nie E-Mail)."""
    from diakronos_app import dsgvo_anonymisierung as D

    g = _oeffnen("M-Bert", ANNA)["name"]
    with dbmod.SessionLocal.begin() as s:
        D.anonymisiere(s, "M-Bert", [BERT])
    eintrag = {e["name"]: e for e in _meine(ANNA)["gespraeche"]}[g]
    # Es gibt keinen zweiten Namensweg: weder Adresse noch Konto-Name. Der
    # eine zulässige Text ist „Gelöschte Person“ (auch hier, weil die
    # Teilnahme fehlt — unabhängig davon, ob das Paar noch steht).
    assert eintrag["titel"] == "Gelöschte Person", eintrag["titel"]
    assert BERT not in eintrag["titel"]
    assert "@" not in eintrag["titel"]


def test_nach_der_loeschung_kein_neues_gespraech_mit_der_person(welt):
    """Das Konto ist weg → ``darf_direktnachricht`` sagt Nein (403)."""
    from diakronos_app.api import chat as C

    _oeffnen("M-Bert", ANNA)
    welt.query(User).filter(User.name == BERT).delete()
    welt.commit()
    _set_user(ANNA)
    _h_leer(C.direkt_oeffnen, "M-Bert")


# ── 8) SEC-11 / Migration ──────────────────────────────────────────────────

def test_direkt_oeffnen_ist_schreibend_und_im_inventar(welt):
    from diakronos_app.api import chat as C
    from diakronos_app.frappe_compat import registry

    assert registry.lookup("chat.direkt_oeffnen") is C.direkt_oeffnen
    optionen = registry.options_for(C.direkt_oeffnen)
    assert optionen.get("allow_guest") is False
    assert optionen.get("methods") == ("POST",)

    inventar = (BACKEND / "src" / "diakronos_app" / "frappe_compat" / "inventar"
                / "whitelist.json")
    daten = json.loads(inventar.read_text(encoding="utf-8"))
    eintrag = next(e for e in daten["eintraege"]
                   if e["funktion"] == "diakronos_app.api.chat.direkt_oeffnen")
    assert eintrag["einstufung"] == "schreibend", eintrag
    assert eintrag["allow_guest"] is False


def _skripte() -> ScriptDirectory:
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "alembic"))
    return ScriptDirectory.from_config(cfg)


def test_migration_haengt_hinter_chat8_und_die_kette_hat_einen_kopf():
    skripte = _skripte()
    rev = skripte.get_revision("chat7a_direkt")
    assert rev is not None
    # Nach dem zweiten Nachziehen von ``main``: der vorherige Kopf ist
    # ``chat8_fristen`` (CHAT-8). Der KOPFNAME wird bewusst nicht
    # festgeschrieben (jede weitere Fachmigration haengt sich hinten an) —
    # geprüft wird: diese Kante, EIN Kopf, EIN Zweig.
    assert rev.down_revision == "chat8_fristen", rev.down_revision
    assert "Revises: chat8_fristen" in Path(rev.path).read_text(encoding="utf-8")
    assert len(skripte.get_bases()) == 1
    # Genau EIN Kopf — und es ist diese Revision (bzw. ein späterer Nachfolger).
    heads = skripte.get_heads()
    assert len(heads) == 1, heads


@pytest.fixture()
def fresh_engine():
    """Leere SQLite-Engine mit Gerüst; ``chat_gespraech`` im ALTEN Stand."""
    from sqlalchemy import create_engine, text as sql_text
    from sqlalchemy.pool import StaticPool

    from diakronos_app.models.base import Base

    eng = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(eng)
    # Zurücksetzen auf den Stand VOR chat7a: Spalte weg, `gruppe` NOT NULL,
    # Einheits-Index ohne Paar-Ausnahme (wie die Migration ihn erwartet).
    with eng.begin() as v:
        v.exec_driver_sql('DROP INDEX IF EXISTS "uq_chat_gespraech_paar"')
        v.exec_driver_sql('DROP INDEX IF EXISTS "uq_chat_gespraech_einheit"')
        v.exec_driver_sql('ALTER TABLE "chat_gespraech" DROP COLUMN "paar_schluessel"')
        v.exec_driver_sql('INSERT INTO "chat_gespraech" (name, art, gruppe) '
                          "VALUES ('G-ALT', 'gruppe', 'Chor')")
    yield eng
    eng.dispose()


def test_migration_upgrade_downgrade_upgrade(fresh_engine):
    import importlib.util

    from sqlalchemy import inspect

    pfad = BACKEND / "alembic" / "versions" / "chat7a_direkt.py"
    spec = importlib.util.spec_from_file_location("chat7a_direkt", pfad)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)

    def _zustand():
        insp = inspect(fresh_engine)
        spalten = {c["name"]: c for c in insp.get_columns("chat_gespraech")}
        indizes = {i["name"]: i for i in insp.get_indexes("chat_gespraech")}
        return spalten, indizes

    with fresh_engine.begin() as verbindung:
        from alembic.migration import MigrationContext
        from alembic.operations import Operations

        with Operations.context(MigrationContext.configure(verbindung)):
            modul.upgrade()
    spalten, indizes = _zustand()
    assert spalten["gruppe"]["nullable"] is True
    assert "paar_schluessel" in spalten and spalten["paar_schluessel"]["nullable"] is True
    assert bool(indizes["uq_chat_gespraech_paar"]["unique"]) is True
    assert indizes["uq_chat_gespraech_paar"]["column_names"] == ["paar_schluessel"]
    # Der Bestand ist unangetastet (Gruppen-Gespräch behält seinen Namen).
    with fresh_engine.begin() as v:
        assert v.exec_driver_sql(
            "SELECT gruppe FROM chat_gespraech WHERE name = 'G-ALT'").scalar_one() == "Chor"

    # Zweiter Lauf ist idempotent.
    with fresh_engine.begin() as verbindung:
        from alembic.migration import MigrationContext
        from alembic.operations import Operations

        with Operations.context(MigrationContext.configure(verbindung)):
            modul.upgrade()
    assert "paar_schluessel" in _zustand()[0]

    # Downgrade stellt den ALten Stand wieder her (es gibt kein Direktgespräch).
    with fresh_engine.begin() as verbindung:
        from alembic.migration import MigrationContext
        from alembic.operations import Operations

        with Operations.context(MigrationContext.configure(verbindung)):
            modul.downgrade()
    spalten, indizes = _zustand()
    assert "paar_schluessel" not in spalten
    assert spalten["gruppe"]["nullable"] is False
    assert "uq_chat_gespraech_paar" not in indizes

    # Und wieder hoch — der Rundlauf bricht nicht.
    with fresh_engine.begin() as verbindung:
        from alembic.migration import MigrationContext
        from alembic.operations import Operations

        with Operations.context(MigrationContext.configure(verbindung)):
            modul.upgrade()
    assert "paar_schluessel" in _zustand()[0]


# ── 9) Review R1: Glocken-Betreff, Titel/Maskierung, Moderation, Dritte ────


def test_buendelglocke_hat_neutralen_betreff_ohne_namen(welt):
    """CHAT-4a „kein Absendername“ gilt auch fürs 1:1: Betreff „Direktnachricht“.

    Vorher stand dort „None: 1 neue Nachricht“ (Titel, Untergruppe und Gruppe
    sind bei einem Direktgespräch alle NULL). Der Gesprächstitel eines 1:1 IST
    der Name des Absenders — der darf nicht in der Glocke stehen.
    """
    from diakronos_app.api import chat as C

    g = _oeffnen("M-Bert", ANNA)["name"]
    _senden(g, "Hallo Bert", ANNA)
    _altern(g)
    assert C.chat_glocken_buendeln(jetzt=dt.datetime(2026, 11, 19, 10, 0, 0)) == 1

    with dbmod.SessionLocal() as s:
        glocke = s.query(NotificationLog).filter(
            NotificationLog.document_type == "chat_gespraech",
            NotificationLog.document_name == g,
            NotificationLog.for_user == BERT).one()
    betreff = str(glocke.subject or "")
    assert betreff == "Direktnachricht: 1 neue Nachricht", betreff
    # Weder Name noch Adresse noch der Platzhalter einer fehlenden Gruppe.
    for verboten in ("Anna", "Beispiel", "@", "None", "Hallo Bert"):
        assert verboten not in betreff, betreff
    assert verboten not in str(glocke.email_content or "")


def _titel(konto: str, gespraech: str) -> str:
    return {e["name"]: e for e in _meine(konto)["gespraeche"]}[gespraech]["titel"]


def test_titel_maskiert_auch_bei_gesperrtem_und_ausgeschlossenem_gegenueber(welt):
    """Titel = ``kuerze_name`` — NIE der volle Name und NIE die E-Mail.

    Vorher löste ``_person_je_konto`` über ``rechte.eigenes_mitglied`` auf; für
    ein gesperrtes/ausgeschlossenes Mitglied kam ``None`` zurück, und der Titel
    fiel auf Konto bzw. Adresse zurück — der VOLLE Name.
    """
    g = _oeffnen("M-Bert", ANNA)["name"]
    assert _titel(ANNA, g) == "Bert B."

    # Gesperrtes KONTO (kein aktives Konto) → weiterhin gekürzt.
    welt.query(User).filter(User.name == BERT).update({"enabled": 0})
    welt.commit()
    assert _titel(ANNA, g) == "Bert B."

    welt.query(User).filter(User.name == BERT).update({"enabled": 1})
    welt.commit()
    # AUSGESCHLOSSENES Mitglied (Konto aktiv) → ebenfalls gekürzt.
    _mitglied_status(welt, "M-Bert", ausgeschlossen=1)
    titel = _titel(ANNA, g)
    assert titel == "Bert B.", titel
    assert BERT not in titel and "Brandner" not in titel

    # Ausgetreten → ebenfalls gekürzt (nicht der volle Name).
    _mitglied_status(welt, "M-Bert", ausgeschlossen=0, status="Ausgetreten")
    assert _titel(ANNA, g) == "Bert B."


def test_titel_faellt_nie_auf_konto_oder_mail_zurueck(welt):
    """Ohne Mitgliedsdatensatz bleibt der Titel LEER — nicht ``full_name``/Adresse."""
    g = _oeffnen("M-Bert", ANNA)["name"]
    # Mitgliedszeile weg, Konto bleibt: kein Anzeigename mehr vorhanden.
    welt.query(Mitglied).filter(Mitglied.name == "M-Bert").delete()
    welt.commit()
    titel = _titel(ANNA, g)
    assert titel == "", titel
    assert "@" not in titel and "Bert" not in titel


def test_dritte_kommen_auch_nicht_an_aendern_loeschen_und_umfragen(welt):
    """Dritte/HV/Admin: kein Ändern, kein Löschen, keine Umfrage-Wege."""
    from diakronos_app.api import chat as C

    g = _oeffnen("M-Bert", ANNA)["name"]
    n = _senden(g, "Nur für Bert", ANNA)
    _set_user(ANNA)
    # ``umfrage_anlegen`` liefert ``{name: <Nachricht>, umfrage: {...}}``.
    umfrage = C.umfrage_anlegen(g, "Wann treffen wir uns?", ["Montag", "Dienstag"])["umfrage"]

    for wer in (HV, ADMIN, CLARA, OHNE):
        _set_user(wer)
        _h_leer(C.aendern, n["name"], "fremd umgeschrieben")
        _h_leer(C.loeschen, n["name"])
        _h_leer(C.umfrage_anlegen, g, "Frage?", ["a", "b"])
        _h_leer(C.umfrage_abstimmen, umfrage["name"], [0])
        _h_leer(C.umfrage_ergebnis, umfrage["name"])
        _h_leer(C.umfrage_schliessen, umfrage["name"])
        _h_leer(C.meldung_senden, n["name"], "beleidigung")

    # Die Nachricht lebt weiter, die Umfrage steht offen.
    posten = {p["name"]: p for p in _verlauf(g, ANNA)["nachrichten"]}
    assert posten[n["name"]]["text"] == "Nur für Bert"
    assert posten[n["name"]]["geloescht"] is False
    _set_user(ANNA)
    assert C.umfrage_ergebnis(umfrage["name"])["offen"] is True


def test_umfrage_im_direktgespraech_durch_teilnehmende(welt):
    """Umfrage im 1:1: Anlegen/Abstimmen/Ergebnis/Schließen gehen für beide."""
    from diakronos_app.api import chat as C

    g = _oeffnen("M-Bert", ANNA)["name"]
    _set_user(ANNA)
    # ``umfrage_anlegen`` liefert ``{name: <Nachricht>, umfrage: {...}}``.
    umfrage = C.umfrage_anlegen(g, "Wann treffen wir uns?", ["Montag", "Dienstag"])["umfrage"]
    _set_user(BERT)
    assert C.umfrage_abstimmen(umfrage["name"], [1]) is not None
    ergebnis = C.umfrage_ergebnis(umfrage["name"])
    assert ergebnis["offen"] is True
    # Nur die ANLEGENDE Person schließt (SCHREIBEN mit besitzer).
    _h_leer(C.umfrage_schliessen, umfrage["name"])
    _set_user(ANNA)
    assert C.umfrage_schliessen(umfrage["name"])["offen"] is False


def test_hv_kommt_nicht_an_die_meldungsliste_eines_direktgespraechs(welt):
    """HV: ``meldungen_liste(gespraech=<direkt>)`` und Entscheiden → 403 leer."""
    from diakronos_app.api import chat as C

    g = _oeffnen("M-Bert", ANNA)["name"]
    n = _senden(g, "Grenzwertig", BERT)
    _set_user(ANNA)
    gemeldet = C.meldung_senden(n["name"], "beleidigung")

    _set_user(HV)
    _h_leer(C.meldungen_liste, gespraech=g)
    _h_leer(C.meldung_entscheiden, gemeldet["name"], "verwerfen")
    # Und der Admin sieht in der Liste KEINE Gruppenmeldung dieses 1:1 fuer HV.
    _set_user(ADMIN)
    liste = C.meldungen_liste(gespraech=g)
    assert [e["name"] for e in liste["meldungen"]] == [gemeldet["name"]]
    assert liste["meldungen"][0]["gespraech_titel"] == "Direktnachricht"


def test_admin_als_teilnehmer_loescht_fremde_nachricht_nicht(welt):
    """MODERIEREN im 1:1 gibt es NUR auf dem Meldeweg (Kern-Docstring).

    Ein teilnehmender Admin darf die Nachricht des Gegenübers nicht über
    ``loeschen`` entfernen (SCHREIBEN mit besitzer → 403) — über
    ``meldung_entscheiden`` geht es.
    """
    from diakronos_app.api import chat as C

    # Anna bekommt ebenfalls die Admin-Rolle und ist damit Meldestelle UND
    # Teilnehmerin eines 1:1 mit Bert.
    welt.add(HasRole(name="hr-anna", parent=ANNA, parenttype="User",
                     role="System Manager"))
    welt.commit()
    g = _oeffnen("M-Bert", ANNA)["name"]
    n = _senden(g, "Bert schreibt", BERT)

    _set_user(ANNA)
    _h_leer(C.loeschen, n["name"])
    # Gemeldet wird von der PERSON, die nicht die Verfasserin ist: ANNA meldet
    # BERTs Nachricht — und genau das darf sie hier (sie ist Teilnehmerin).
    gemeldet = C.meldung_senden(n["name"], "beleidigung")
    entschieden = C.meldung_entscheiden(gemeldet["name"], "entfernen",
                                        grund="Regelverstoß")
    assert entschieden["stand"] == "erledigt"
    posten = {p["name"]: p for p in _verlauf(g, ANNA)["nachrichten"]}
    assert posten[n["name"]]["geloescht"] is True


def test_ausgetretene_person_selbst_liest_sendet_aber_nicht(welt):
    """Die ausgetretene Person selbst: LESEN ja (aktives Konto), SENDEN 403."""
    from diakronos_app.api import chat as C

    g = _oeffnen("M-Bert", ANNA)["name"]
    _senden(g, "Vor dem Austritt", ANNA)
    _mitglied_status(welt, "M-Bert", status="Ausgetreten")

    _set_user(BERT)
    assert [p["text"] for p in C.verlauf(g)["nachrichten"]] == ["Vor dem Austritt"]
    _h_leer(C.senden, g, "Ich schreibe trotzdem")
    # Reaktion ist LESEN (der Kern lässt sie zu) — gesperrt ist nur das
    # SCHREIBEN neuer Nachrichten/Umfragen.
    _set_user(ANNA)
    _h_leer(C.senden, g, "Ich schreibe auch nicht mehr")


def test_kern_verlangt_ein_auffindbares_eigenes_mitglied(welt):
    """Neuer Kern (d732717a): Konto ohne Mitglied (Admin) beginnt kein 1:1."""
    from diakronos_app.api import chat as C

    # ADMIN ist ``ist_gemeindemitglied`` (System Manager), hat aber kein
    # auffindbares Mitglied → „selbst_nicht_aktiv“, 403 ohne Inhalt.
    _set_user(ADMIN)
    _h_leer(C.direkt_oeffnen, "M-Bert")


def test_dsgvo_loescht_nur_das_eigene_kontenpaar(welt):
    """``_``/``%`` in Adressen sind KEINE LIKE-Platzhalter.

    ``max_mueller@`` träfe sonst auch ``max.mueller@``: ein FREMDES Paar
    verlöre seinen Schlüssel, und ein zweites Gespräch desselben Paares wäre
    wieder möglich. Geprüft mit genau diesem Paar.
    """
    from diakronos_app import dsgvo_anonymisierung as D

    unterstrich = "max_mueller@x.org"
    punkt = "max.mueller@x.org"
    fremd = "zoe@x.org"
    welt.add(User(name=unterstrich, email=unterstrich, enabled=1, full_name="Max U"))
    welt.add(User(name=punkt, email=punkt, enabled=1, full_name="Max P"))
    welt.add(User(name=fremd, email=fremd, enabled=1, full_name="Zoe"))
    welt.add_all([
        Mitglied(name="M-MaxU", vorname="Max", nachname="Unter", email=unterstrich,
                 user=unterstrich, status="Aktiv"),
        Mitglied(name="M-MaxP", vorname="Max", nachname="Punkt", email=punkt,
                 user=punkt, status="Aktiv"),
        Mitglied(name="M-Zoe", vorname="Zoe", nachname="Zett", email=fremd,
                 user=fremd, status="Aktiv"),
    ])
    welt.commit()

    _oeffnen("M-Zoe", unterstrich)      # Paar 1: max_mueller ↔ zoe
    _oeffnen("M-Zoe", punkt)            # Paar 2: max.mueller ↔ zoe
    from diakronos_app.api.chat import _paar_schluessel

    eigen = _paar_schluessel(unterstrich, fremd)
    fremdes = _paar_schluessel(punkt, fremd)
    with dbmod.SessionLocal() as s:
        paare = [str(z[0]) for z in s.query(ChatGespraech.paar_schluessel)
                 .filter(ChatGespraech.art == ART_DIREKT).all() if z[0]]
    assert sorted(paare) == sorted([eigen, fremdes]), paare

    with dbmod.SessionLocal.begin() as s:
        D.anonymisiere(s, "M-MaxU", [unterstrich])

    with dbmod.SessionLocal() as s:
        nachher = [str(z[0]) for z in s.query(ChatGespraech.paar_schluessel)
                   .filter(ChatGespraech.art == ART_DIREKT).all() if z[0]]
    # Genau EIN Schlüssel bleibt: das FREMDDE Paar (max.mueller ↔ zoe). Mit
    # LIKE wären beide gefallen (``_`` = ein beliebiges Zeichen).
    assert nachher == [fremdes], nachher
