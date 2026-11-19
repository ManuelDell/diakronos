"""CHAT-N1: Nacharbeiten aus den Reviews CHAT-7a/4b (Backend).

Eigene Datei, damit ``test_chat7a_direkt.py`` und die CHAT-4b-Datei lesbar
bleiben. Geprüft wird gegen die ECHTEN Endpunkte, den ECHTEN Rechte-Kern und
die ECHTE Datenbank — je Punkt der Karte genau das, was der Review verlangt
hat:

  1. ``_meldestellen_konten``: KEINE Rollennamen als Konten; ``Administrator``
     ohne eigene ``User``-Zeile bekommt die Meldungs-Glocke.
  2. ``_moderation_konten``/``meldungen_liste``: keine eigene Sitzung je
     Kandidat, MODERIEREN liest die Teilnehmenden nicht.
  3. Löschen/Umfrage schließen im 1:1: EINE Weiche (SCHREIBEN mit Besitzer),
     teilnehmender Admin 403.
  4. Bild eines ausgeschlossenen Gegenübers; kein Kennungs-Rückfall im Titel.
  5. Erinnerung: kurze Frist fällt in der SQL-Auswahl heraus.
  6. Teilweises Lesen: Glocke zählt fort, ``modified`` bleibt stehen.
"""

from __future__ import annotations

import datetime as dt
import importlib

import pytest

from diakronos_app import db as dbmod
from diakronos_app.models.chat import (
    ART_DIREKT,
    ChatGespraech,
    ChatMeldung,
    ChatNachricht,
    ChatTeilnehmer,
    ChatUmfrage,
)
from diakronos_app.models.core import HasRole, NotificationLog, User
from diakronos_app.models.diakonos import Mitglied

_session_mod = importlib.import_module("diakronos_app.frappe_compat.session")

ANNA = "anna@x.org"     # Gemeindemitglied mit Konto
BERT = "bert@x.org"     # Gemeindemitglied mit Konto
ADMIN = "admin@x.org"   # Konto MIT Rolle ``System Manager`` (Meldestelle)


def _set_user(konto: str) -> None:
    _session_mod.set_user(konto)


@pytest.fixture()
def welt(patched_db):
    """Zwei Mitglieder/Konten + ein Konto mit ``System Manager``.

    ``Administrator`` bekommt BEWUSST KEINE ``User``-Zeile: genau das ist der
    Fall aus Punkt 1 (der Kern bestätigt ihn trotzdem als Meldestelle).
    """
    s = patched_db()
    for konto, kurz in [(ANNA, "Anna"), (BERT, "Bert"), (ADMIN, "Admin")]:
        s.add(User(name=konto, email=konto, enabled=1, full_name=kurz))
    s.add_all([
        Mitglied(name="M-Anna", vorname="Anna", nachname="Beispiel",
                 email=ANNA, user=ANNA, status="Aktiv",
                 foto="/files/anna.jpg"),
        Mitglied(name="M-Bert", vorname="Bert", nachname="Brandner",
                 email=BERT, user=BERT, status="Aktiv",
                 foto="/files/bert.jpg"),
    ])
    s.add(HasRole(name="hr-admin", parent=ADMIN, parenttype="User",
                  role="System Manager"))
    s.commit()
    yield s
    s.close()


def _oeffnen(konto: str = ANNA) -> str:
    from diakronos_app.api import chat as C

    _set_user(konto)
    return C.direkt_oeffnen("M-Bert")["name"]


def _senden(gespraech: str, text: str, konto: str) -> dict:
    from diakronos_app.api import chat as C

    _set_user(konto)
    return C.senden(gespraech, text)


# ── 1) Meldestellen-Konten sind KONTEN, keine Rollen ────────────────────────

def test_meldestellen_konten_enthalten_keine_rollennamen(welt):
    """``"System Manager"``/``ROOT_ROLLE`` sind ``role``, keine ``parent``."""
    from diakronos_app.api import chat as C
    from diakronos_app.frappe_compat.permissions import ROOT_ROLLE

    konten = C._meldestellen_konten()
    assert "System Manager" not in konten
    assert ROOT_ROLLE not in konten
    # Konto MIT der Rolle: ja. Konten ohne Rolle: nein.
    assert ADMIN in konten
    assert ANNA not in konten and BERT not in konten


def test_administrator_ohne_user_zeile_bekommt_die_meldungsglocke(welt):
    """``Administrator`` ist Meldestelle, auch OHNE eigene ``User``-Zeile.

    Die Glocke einer gemeldeten Nachricht aus einem 1:1 geht an die
    Meldestelle — hier an ``Administrator`` (kein ``user``-Eintrag!) und an
    das Konto mit ``System Manager``. Kein Rollenname taucht als Empfänger
    auf.
    """
    from diakronos_app.api import chat as C

    with dbmod.SessionLocal() as s:
        assert s.get(User, "Administrator") is None      # Fall aus dem Review

    g = _oeffnen(ANNA)
    n = _senden(g, "Bert schreibt", BERT)
    _set_user(ANNA)
    gemeldet = C.meldung_senden(n["name"], "beleidigung")

    with dbmod.SessionLocal() as s:
        empfaenger = {str(z.for_user) for z in s.query(NotificationLog).filter(
            NotificationLog.document_type == "chat_meldung",
            NotificationLog.document_name == gemeldet["name"]).all()}
    assert empfaenger == {ADMIN, "Administrator"}, empfaenger


# ── 2) Keine eigene Sitzung je Kandidat ─────────────────────────────────────

def test_moderation_konten_und_liste_oeffnen_keine_eigene_sitzung(welt, monkeypatch):
    """Meldungsweg und Liste arbeiten in der Sitzung des AUFRUFERS.

    ``SessionLocal`` wird hier zur Falle: jedes Öffnen einer eigenen Sitzung
    zählt mit. Danach ist die Zahl der Aufrufe 0 — weder je Kandidat noch für
    die ART-Abfrage.
    """
    from diakronos_app.api import chat as C

    g = _oeffnen(ANNA)
    n = _senden(g, "Bert schreibt", BERT)
    _set_user(ANNA)
    gemeldet = C.meldung_senden(n["name"], "beleidigung")

    aufrufe = {"n": 0}
    echt = dbmod.SessionLocal

    class _Zaehlend:
        """Attrappe der Sitzungs-Factory, die jeden Aufruf mitzählt."""

        def __call__(self, *args, **kwargs):
            aufrufe["n"] += 1
            return echt(*args, **kwargs)

        def begin(self):
            aufrufe["n"] += 1
            return echt.begin()

    monkeypatch.setattr(C.dbmod, "SessionLocal", _Zaehlend())

    _set_user(ADMIN)
    # Direkt die Hilfsfunktion (mit Sitzung des Aufrufers) …
    with echt.begin() as s:
        konten = C._moderation_konten(s.get(ChatGespraech, g), sitzung=s)
    assert "Administrator" in konten
    # … und der ganze Endpunkt: nur die EINE Sitzung der Liste (oben, außerhalb
    # der Zählung) plus die des Endpunkts selbst. Kein Aufruf je Kandidat.
    vorher = aufrufe["n"]
    _set_user(ADMIN)
    liste = C.meldungen_liste()
    assert any(e["name"] == gemeldet["name"] for e in liste["meldungen"])
    # Der Endpunkt öffnet genau EINE Sitzung; ``SessionLocal`` wird in der
    # Liste nirgends mehr gebraucht (``als_aktuelle_sitzung`` greift, der Kern
    # liest über ``lesesitzung``).
    assert aufrufe["n"] - vorher == 1, aufrufe


def test_moderieren_im_direktgespraech_liest_die_teilnehmer_nicht(welt, monkeypatch):
    """MODERIEREN wertet die Teilnehmenden im Kern nicht aus — hier auch nicht."""
    from diakronos_app.api import chat as C

    g = _oeffnen(ANNA)
    gelesen = {"n": 0}

    def _verboten(gespraech, *, sitzung=None):
        gelesen["n"] += 1
        raise AssertionError("Teilnehmende wurden für MODERIEREN gelesen")

    monkeypatch.setattr(C, "_wechselart_lesen", _verboten)
    monkeypatch.setattr(C, "_teilnahme_konten_aus_db", _verboten)
    monkeypatch.setattr(C, "_teilnahme_konten", _verboten)

    from diakronos_app import rechte as R

    with dbmod.SessionLocal.begin() as s, dbmod.als_aktuelle_sitzung(s):
        zeile = s.get(ChatGespraech, g)
        assert C._weiche_ja(ADMIN, R.MODERIEREN, g=zeile, sitzung=s) is True
        assert C._weiche_ja(ANNA, R.MODERIEREN, g=zeile, sitzung=s) is False
    assert gelesen["n"] == 0, gelesen


# ── 3) Abgelehnt wird trotzdem: EINE Weiche statt Sonderregel ───────────────

def test_teilnehmender_admin_schliesst_fremde_umfrage_nicht(welt):
    """Im 1:1 gibt es KEINEN Moderationsweg neben dem Meldeweg (Punkt 3)."""
    from diakronos_app.api import chat as C
    from diakronos_app.frappe_compat.exceptions import PermissionError

    # ANNA wird Meldestelle und ist gleichzeitig Teilnehmerin des 1:1.
    welt.add(HasRole(name="hr-anna", parent=ANNA, parenttype="User",
                     role="System Manager"))
    welt.commit()
    g = _oeffnen(ANNA)
    _set_user(BERT)
    umfrage = C.umfrage_anlegen(g, "Kaffee oder Tee?", ["Kaffee", "Tee"])

    _set_user(ANNA)
    with pytest.raises(PermissionError):
        C.umfrage_schliessen(umfrage["umfrage"]["name"])
    # Und die Nachricht des Gegenübers ebenfalls nicht.
    n = _senden(g, "Bert schreibt", BERT)
    _set_user(ANNA)
    with pytest.raises(PermissionError):
        C.loeschen(n["name"])


# ── 3b) MUSS 2: nach der Anonymisierung bleibt die fremde Nachricht fremd ───

def test_nach_anonymisierung_bleibt_die_nachricht_der_geloeschten_fremd(welt):
    """Review CHAT-N1, MUSS 2: ``autor_benutzer`` NULL ist NICHT „eigene“.

    Der Kern liest ``besitzer is None`` als „eigene Nachricht“ (JA). Nach der
    Anonymisierung trägt die Nachricht der gelöschten Person aber kein Konto
    mehr — ohne die Umwandlung in ``""`` dürfte die verbliebene Person sie
    löschen (vorher 403). Dasselbe gilt für die Umfrage der gelöschten Person.
    """
    from diakronos_app import dsgvo_anonymisierung as D
    from diakronos_app.api import chat as C
    from diakronos_app.frappe_compat.exceptions import PermissionError

    g = _oeffnen(ANNA)
    n = _senden(g, "Bert schreibt", BERT)
    _set_user(BERT)
    umfrage = C.umfrage_anlegen(g, "Kaffee oder Tee?", ["Kaffee", "Tee"])

    with dbmod.SessionLocal.begin() as s:
        D.anonymisiere(s, "M-Bert", [BERT])

    with dbmod.SessionLocal() as s:
        # Vorbedingung: genau der Fall aus dem Review — kein Konto am Autor.
        assert s.get(ChatNachricht, n["name"]).autor_benutzer is None
        huelle = s.query(ChatNachricht).filter(
            ChatNachricht.umfrage == umfrage["umfrage"]["name"]).one()
        assert huelle.autor_benutzer is None

    _set_user(ANNA)
    with pytest.raises(PermissionError):
        C.loeschen(n["name"])
    with pytest.raises(PermissionError):
        C.umfrage_schliessen(umfrage["umfrage"]["name"])


# ── 4) Ausgeschlossenes Gegenüber: kein Bild, kein Kennungs-Titel ───────────
def test_ausgeschlossenes_gegenueber_liefert_kein_bild(welt):
    """Punkt 4: kein Profilbild einer ausgeschlossenen Person im 1:1."""
    from diakronos_app.api import chat as C

    g = _oeffnen(ANNA)
    _set_user(ANNA)
    vorher = {e["name"]: e for e in C.meine_gespraeche()["gespraeche"]}[g]
    assert vorher["bild"], "Vorbedingung: das Bild kommt ohne Ausschluss"

    # Ausschluss setzt am MITGLIED, nicht am Konto (P1-8).
    welt.query(Mitglied).filter_by(name="M-Bert").update({"ausgeschlossen": True})
    welt.commit()

    _set_user(ANNA)
    after = {e["name"]: e for e in C.meine_gespraeche()["gespraeche"]}[g]
    assert after["bild"] in ("", None), after["bild"]
    # Der Titel bleibt der gekürzte Name — kein Rückfall auf die Kennung.
    assert "Bert" in str(after["titel"] or ""), after["titel"]
    assert BERT not in str(after["titel"] or "")


def test_titel_faellt_nicht_auf_die_kennung_zurueck(welt, monkeypatch):
    """Liefert die Namensquelle nichts, bleibt der Titel LEER (nie Kennung)."""
    from diakronos_app.api import chat as C
    from diakronos_app.frappe_compat import personen_anzeige

    g = _oeffnen(ANNA)
    monkeypatch.setattr(personen_anzeige, "kuerze_name",
                        lambda *a, **k: "", raising=True)
    _set_user(ANNA)
    eintrag = {e["name"]: e for e in C.meine_gespraeche()["gespraeche"]}[g]
    # Ohne Namensquelle: leer ODER „Gelöschte Person“ — NIE die Kennung.
    titel = str(eintrag["titel"] or "")
    assert titel in ("", "Gelöschte Person"), titel
    assert "M-Bert" not in titel and BERT not in titel


# ── 5) Erinnerung: kurze Frist schon in der SQL-Auswahl raus ────────────────

def _umfrage_zeile(welt, gespraech: str, *, name: str, erstellt_am, frist_am,
                   erinnert_am=None) -> None:
    welt.add(ChatUmfrage(
        name=name, gespraech=gespraech, frage="Frage?", anonym=False,
        erstellt_am=erstellt_am, frist_am=frist_am, erinnert_am=erinnert_am,
        geschlossen_am=None,
    ))
    welt.add(ChatNachricht(name=f"chat-nachricht-{name}", gespraech=gespraech,
                           autor=None, autor_benutzer=ANNA, text="Umfrage",
                           erstellt_am=erstellt_am, umfrage=name))
    welt.commit()


def test_kurze_frist_faellt_aus_der_erinnerungs_auswahl(welt):
    """Punkt 5: ``frist_am - erstellt_am <= vorlauf`` wird gar nicht erst geholt.

    Grenze STRIKT (Review CHAT-N1, MUSS 1): genau ``vorlauf`` Abstand ist
    „kurz“ und damit KEIN Kandidat — dieselbe Grenze wie in der
    Python-Nachprüfung.
    """
    from diakronos_app.api import chat as C

    g = _oeffnen(ANNA)
    basis = dt.datetime(2026, 11, 19, 9, 0, 0)
    # Kurz (12 h Frist) → KEIN Kandidat.
    _umfrage_zeile(welt, g, name="um-kurz", erstellt_am=basis,
                   frist_am=basis + dt.timedelta(hours=12))
    # Genau 24 h → Grenze strikt, ebenfalls KEIN Kandidat.
    _umfrage_zeile(welt, g, name="um-grenze", erstellt_am=basis,
                   frist_am=basis + dt.timedelta(hours=24))
    # Lange Frist (3 Tage), Frist naht → Kandidat.
    _umfrage_zeile(welt, g, name="um-lang", erstellt_am=basis,
                   frist_am=basis + dt.timedelta(hours=72))

    zeit = basis + dt.timedelta(hours=48)
    with dbmod.SessionLocal() as s:
        gefunden = C._offene_umfragen_mit_frist(s, zeit, 24)
    assert "um-kurz" not in gefunden, gefunden
    assert "um-grenze" not in gefunden, gefunden
    assert gefunden == ["um-lang"], gefunden


# ── 6) Teilweises Lesen schiebt die Glocke NICHT nach oben ──────────────────

def test_teilweises_lesen_zaehlt_fort_ohne_modified(welt):
    """Punkt 6: Zahl folgt dem Lesestand, ``modified`` bleibt stehen."""
    from diakronos_app.api import chat as C

    g = _oeffnen(ANNA)
    for text in ("eins", "zwei", "drei"):
        _senden(g, text, ANNA)
    zeit = dt.datetime(2026, 11, 19, 9, 0, 0)
    with dbmod.SessionLocal.begin() as s:
        s.execute(C.update(ChatNachricht).where(ChatNachricht.gespraech == g)
                  .values(erstellt_am=zeit))
        s.execute(C.update(ChatTeilnehmer).where(ChatTeilnehmer.gespraech == g)
                  .values(hinzugefuegt_am=zeit))

    C.chat_glocken_buendeln(jetzt=zeit + dt.timedelta(minutes=30))
    with dbmod.SessionLocal() as s:
        glocke = s.query(NotificationLog).filter(
            NotificationLog.for_user == BERT,
            NotificationLog.document_type == C.CHAT_GLOCKE_DOCTYPE,
            NotificationLog.document_name == g).one()
        assert "3 neue Nachrichten" in str(glocke.subject)
        vorher = glocke.modified
        assert vorher is not None

    # TEILWEISE lesen: nur die erste der drei.
    erste = _verlauf_erste(g, BERT)
    _set_user(BERT)
    C.lesestand_setzen(g, erste)

    with dbmod.SessionLocal() as s:
        glocke = s.query(NotificationLog).filter(
            NotificationLog.for_user == BERT,
            NotificationLog.document_type == C.CHAT_GLOCKE_DOCTYPE,
            NotificationLog.document_name == g).one()
        # Die ZAHL folgt (2 statt 3) …
        assert "2 neue Nachrichten" in str(glocke.subject), glocke.subject
        # … der Anlass der Zeile NICHT.
        assert glocke.modified == vorher, (glocke.modified, vorher)
        assert glocke.read is False


def _verlauf_erste(gespraech: str, konto: str) -> str:
    from diakronos_app.api import chat as C

    _set_user(konto)
    return C.verlauf(gespraech)["nachrichten"][0]["name"]


# ── 6b) SOLL: eine Sitzung, kein eigener Lesepfad ───────────────────────────

def test_wechselart_lesen_nutzt_die_uebergebene_sitzung(welt):
    """Review CHAT-N1 (SOLL): die ART wird in der Sitzung des Aufrufers gelesen.

    Eine zweite Sitzung sähe geflushte, noch nicht festgeschriebene Zeilen
    nicht — und eine eigene je Aufruf wäre der alte Fehler.
    """
    from diakronos_app.api import chat as C

    g = _oeffnen(ANNA)
    aufrufe = {"n": 0}
    echt = dbmod.SessionLocal

    class _Zaehlend:
        def __call__(self, *args, **kwargs):
            aufrufe["n"] += 1
            return echt(*args, **kwargs)

        def begin(self):
            aufrufe["n"] += 1
            return echt.begin()

    with echt.begin() as s:
        vorher = aufrufe["n"]
        assert C._wechselart_lesen(g, sitzung=s) == ART_DIREKT
        assert aufrufe["n"] == vorher, aufrufe     # keine eigene Sitzung
        # Und die Teilnehmenden ebenso: dieselbe Sitzung, kein eigener Zugriff.
        assert sorted(C._teilnahme_konten_aus_db(g, sitzung=s)) == sorted([ANNA, BERT])
        assert aufrufe["n"] == vorher, aufrufe


def test_meldestellen_konten_oeffnen_keine_eigene_sitzung(welt, monkeypatch):
    """Review CHAT-N1 (SOLL): ``dbmod.lesesitzung`` statt eigener ``SessionLocal``.

    Der Aufrufer läuft hier AUSDRÜCKLICH in einer eigenen Sitzung (so wie
    jedes Gegenstück in ``chat.py`` hinter ``als_aktuelle_sitzung``). Ohne
    diesen Rahmen darf ``lesesitzung`` eine eigene öffnen — das ist gewollt
    (kein Aufrufkontext, keine geliehene Sitzung).
    """
    from diakronos_app.api import chat as C

    aufrufe = {"n": 0}
    echt = dbmod.SessionLocal

    class _Zaehlend:
        def __call__(self, *args, **kwargs):
            aufrufe["n"] += 1
            return echt(*args, **kwargs)

        def begin(self):
            aufrufe["n"] += 1
            return echt.begin()

    monkeypatch.setattr(C.dbmod, "SessionLocal", _Zaehlend())
    with echt.begin() as s, dbmod.als_aktuelle_sitzung(s):
        vorher = aufrufe["n"]
        konten = C._meldestellen_konten()
    assert ADMIN in konten, konten
    assert aufrufe["n"] == vorher, aufrufe


def test_ausgeschlossenes_mitglied_ist_kein_meldestellen_kandidat(welt):
    """Review CHAT-N1 (SOLL): ein ausgeschlossenes Konto fällt schon hier raus.

    Der Kern gäbe ihm keine Rolle (``get_roles`` → ``()``); die Kandidatenliste
    soll dieselbe Grenze ziehen, statt es erst in ``_weiche_ja`` zu verlieren.
    """
    from diakronos_app.api import chat as C

    welt.add(Mitglied(name="M-Admin", vorname="Ada", nachname="Min",
                      email=ADMIN, user=ADMIN, status="Aktiv",
                      ausgeschlossen=True))
    welt.commit()
    konten = C._meldestellen_konten()
    assert ADMIN not in konten, konten
    assert "Administrator" in konten, konten


# ── 7) Die Meldungsliste läuft über EINE Sitzung (Nachweis oben) ────────────

def test_meldungen_liste_zaehlt_mit_einer_sitzung_je_kandidat_null(welt, monkeypatch):
    """Punkt 2 am Endpunkt: 3 Meldungen, 1 Sitzung (nicht 1 + 3)."""
    from diakronos_app.api import chat as C

    kennungen = []
    for _ in range(3):
        g = _oeffnen(ANNA)
        n = _senden(g, "Text", BERT)
        _set_user(ANNA)
        kennungen.append(C.meldung_senden(n["name"], "spam")["name"])
    assert len(set(kennungen)) == 3

    aufrufe = {"n": 0}
    echt = dbmod.SessionLocal

    class _Zaehlend:
        """Attrappe der Sitzungs-Factory, die jeden Aufruf mitzählt."""

        def __call__(self, *args, **kwargs):
            aufrufe["n"] += 1
            return echt(*args, **kwargs)

        def begin(self):
            aufrufe["n"] += 1
            return echt.begin()

    monkeypatch.setattr(C.dbmod, "SessionLocal", _Zaehlend())
    _set_user(ADMIN)
    liste = C.meldungen_liste()
    assert len(liste["meldungen"]) == 3
    # EINE Sitzung für die ganze Liste (der Endpunkt selbst), keine je Meldung.
    assert aufrufe["n"] == 1, aufrufe
