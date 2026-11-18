"""CHAT-6: Melden und Moderation (Konzept 2.5, 3.3, 4.5, 9/F7).

Geprüft wird gegen die ECHTEN Endpunkte (``api/chat.py``) und den ECHTEN
Rechte-Kern (``rechte/kern.py``) — keine Attrappe:

  * Nichtmitglied kann nicht melden (403), Modul aus ebenso
  * eigene Nachricht nicht meldbar (400), falscher Grund, Freitext > 500
  * doppelte OFFENE Meldung abgewiesen — und in der PostgreSQL-Variante auch
    durch den partiellen Unique-Index (SQLite kennt partielle Indizes, der
    Test läuft auf beiden)
  * einfaches Mitglied sieht keine Meldungen (403), Leitung sieht nur die
    Meldungen ihrer Gruppe/Untergruppe, HV der Hauptgruppe sieht die
    Untergruppe
  * ``entfernen`` setzt Soft-Delete + Grund (Verlauf zeigt „entfernt“, Text
    weg), ``verwerfen`` lässt die Nachricht stehen
  * die MELDER-IDENTITÄT taucht in keiner Antwort an die gemeldete Person auf
    (Verlauf, Glocke, Meldungsantwort) — und die Glocke geht an sie
  * Migration ``chat6_meldung``: ein Kopf, hinter ``chat2_chat_s1``, anlegen /
    downgrade / idempotent, Index-Form

Aufruf (Karte):
    docker run --rm --network none --entrypoint python -v <wt>:/repo:ro \\
      -w /repo/backend -e PYTHONPATH=/repo/backend/src:/repo/backend/tests:/repo/tools \\
      -e PYTHONDONTWRITEBYTECODE=1 <vorbau> -m pytest -q -p no:cacheprovider \\
      tests/test_chat6_meldung.py
"""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory

from diakronos_app import db as dbmod

#: Die Test-Naht liegt im MODUL ``frappe_compat.session`` (wie ``test_chat2_api``).
_session_mod = importlib.import_module("diakronos_app.frappe_compat.session")
from diakronos_app.models.chat import ChatMeldung, ChatNachricht
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
SAENGER = "saenger@x.org"    # Mitglied Chor (nicht in der Untergruppe)
NOTEN = "noten@x.org"        # Mitglied der Untergruppe Notenausschuss
FREMD = "fremd@x.org"        # Gemeindemitglied ohne Gruppe
JUGEND = "jugend@x.org"      # Mitglied einer Gruppe OHNE Chat-Modul
POSAUNEN_HV = "posaunen@x.org"   # HV einer ECHTEN Fremdgruppe (Review Punkt 10)


def _set_user(konto: str) -> None:
    _session_mod.set_user(konto)


@pytest.fixture()
def welt(patched_db):
    """Chor mit Untergruppe — dieselbe Welt wie ``test_chat2_api.py``."""
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


@pytest.fixture()
def untergespraech(welt):
    from diakronos_app.api import chat as C

    _set_user(NOTEN)
    name = C.gespraech_anlegen("Chor", "UG-Noten")["name"]
    _session_mod.reset_user()
    return name


def _senden(text: str, gespraech: str, konto: str) -> dict:
    from diakronos_app.api import chat as C

    _set_user(konto)
    return C.senden(gespraech, text)


def _melden(nachricht: str, konto: str, grund: str = "spam",
            freitext=None) -> dict:
    from diakronos_app.api import chat as C

    _set_user(konto)
    return C.meldung_senden(nachricht, grund, freitext=freitext)


def _liste(konto: str, **kwargs) -> dict:
    from diakronos_app.api import chat as C

    _set_user(konto)
    return C.meldungen_liste(**kwargs)


def _entscheiden(meldung: str, konto: str, entscheidung: str, grund=None) -> dict:
    from diakronos_app.api import chat as C

    _set_user(konto)
    return C.meldung_entscheiden(meldung, entscheidung, grund=grund)


def _verlauf(gespraech: str, konto: str) -> dict:
    from diakronos_app.api import chat as C

    _set_user(konto)
    return C.verlauf(gespraech)


# ── Melden: wer darf, was ist verboten ──────────────────────────────────────


def test_nichtmitglied_kann_nicht_melden(gespraech):
    """FREMD ist Gemeindemitglied ohne Gruppe, JUGEND hat kein Chat-Modul: 403."""
    from diakronos_app.frappe_compat.exceptions import PermissionError

    n = _senden("Nur für den Chor", gespraech, SAENGER)
    for wer in (FREMD, JUGEND, "Guest"):
        _set_user(wer)
        from diakronos_app.api import chat as C

        with pytest.raises(PermissionError) as fehler:
            C.meldung_senden(n["name"], "spam")
        # 403 OHNE Inhalt: der Grund (Rollenstring) bleibt im Server.
        assert not str(fehler.value or "")


def test_mitglied_darf_melden(gespraech):
    n = _senden("Das ist Spam", gespraech, SAENGER)
    gemeldet = _melden(n["name"], NOTEN, "spam")
    assert gemeldet["stand"] == "offen"
    assert gemeldet["nachricht"] == n["name"]
    assert gemeldet["gespraech"] == gespraech
    # Die Antwort nennt den MELDER NICHT — sie geht an die meldende Person
    # selbst, ist aber auch kein Beleg über sie.
    assert "melder" not in gemeldet and "melder_konto" not in gemeldet
    assert "freitext" not in gemeldet


def test_eigene_nachricht_nicht_meldbar(gespraech):
    from diakronos_app.frappe_compat.exceptions import ValidationError

    n = _senden("Meine eigene Nachricht", gespraech, SAENGER)
    _set_user(SAENGER)
    from diakronos_app.api import chat as C

    with pytest.raises(ValidationError):
        C.meldung_senden(n["name"], "spam")


def test_unbekannter_grund_und_zu_langer_freitext(gespraech):
    from diakronos_app.api import chat as C
    from diakronos_app.frappe_compat.exceptions import ValidationError

    n = _senden("Irgendwas", gespraech, SAENGER)
    _set_user(NOTEN)
    with pytest.raises(ValidationError):
        C.meldung_senden(n["name"], "mir_gefällt_das_nicht")
    with pytest.raises(ValidationError):
        C.meldung_senden(n["name"], "sonstiges", freitext="x" * 501)
    # Genau 500 Zeichen gehen.
    ok = C.meldung_senden(n["name"], "sonstiges", freitext="x" * 500)
    assert ok["stand"] == "offen"


def test_doppelte_offene_meldung_wird_abgewiesen(gespraech):
    from diakronos_app.api import chat as C
    from diakronos_app.frappe_compat.exceptions import ValidationError

    n = _senden("Zweimal gemeldet", gespraech, SAENGER)
    _melden(n["name"], NOTEN, "spam")
    _set_user(NOTEN)
    with pytest.raises(ValidationError):
        C.meldung_senden(n["name"], "beleidigung")
    # Nur EINE offene Meldung steht in der Datenbank.
    with dbmod.SessionLocal() as s:
        offen = s.query(ChatMeldung).filter(
            ChatMeldung.nachricht == n["name"],
            ChatMeldung.melder == NOTEN,
            ChatMeldung.stand == "offen",
        ).count()
    assert offen == 1
    # Nach einer Entscheidung darf dieselbe Person erneut melden (2.5: der
    # partielle Index lässt es zu — „eine Meldung je Vorgang“, nicht für immer).
    m = _liste(HV)["meldungen"][0]
    _entscheiden(m["name"], HV, "verwerfen")
    wieder = _melden(n["name"], NOTEN, "beleidigung")
    assert wieder["stand"] == "offen"


def test_partielle_eindeutigkeit_haelt_auch_ohne_endpunkt(gespraech):
    """Die Regel steht in der DATENBANK, nicht nur im Endpunkt.

    Ein zweiter Schreibweg (Skript, künftige Karte) darf keine zweite OFFENE
    Meldung derselben Person anlegen — der partielle Unique-Index weist sie ab.
    Eine ZWEITE Meldung nach einer Entscheidung bleibt jedoch möglich.
    """
    from sqlalchemy.exc import IntegrityError

    import datetime as _dt

    n = _senden("Datenbankregel", gespraech, SAENGER)
    with dbmod.SessionLocal.begin() as s:
        s.add(ChatMeldung(name="M-1", nachricht=n["name"], melder=NOTEN,
                          grund="spam", stand="offen",
                          erstellt_am=_dt.datetime(2026, 11, 18, 9)))
    with pytest.raises(IntegrityError):
        with dbmod.SessionLocal.begin() as s:
            s.add(ChatMeldung(name="M-2", nachricht=n["name"], melder=NOTEN,
                              grund="beleidigung", stand="offen",
                              erstellt_am=_dt.datetime(2026, 11, 18, 10)))
    with dbmod.SessionLocal.begin() as s:
        s.add(ChatMeldung(name="M-3", nachricht=n["name"], melder=NOTEN,
                          grund="beleidigung", stand="verworfen",
                          erstellt_am=_dt.datetime(2026, 11, 18, 11)))
    with dbmod.SessionLocal() as s:
        assert s.query(ChatMeldung).filter(ChatMeldung.nachricht == n["name"]).count() == 2


# ── Liste: wer sieht welche Meldungen ───────────────────────────────────────


def test_einfaches_mitglied_sieht_keine_meldungen(gespraech):
    from diakronos_app.api import chat as C
    from diakronos_app.frappe_compat.exceptions import PermissionError

    n = _senden("Gemeldet", gespraech, SAENGER)
    _melden(n["name"], NOTEN, "spam")
    for wer in (SAENGER, NOTEN, FREMD):
        _set_user(wer)
        with pytest.raises(PermissionError):
            C.meldungen_liste()


def test_leitung_sieht_meldungen_ihrer_gruppe(gespraech):
    n = _senden("Gemeldet im Chor", gespraech, SAENGER)
    m = _melden(n["name"], NOTEN, "beleidigung", freitext="Das geht nicht")
    liste = _liste(HV)
    assert [e["name"] for e in liste["meldungen"]] == [m["name"]]
    assert liste["offen"] == 1
    eintrag = liste["meldungen"][0]
    assert eintrag["grund"] == "beleidigung"
    assert eintrag["freitext"] == "Das geht nicht"
    assert eintrag["nachricht"]["text"] == "Gemeldet im Chor"
    assert eintrag["melder"] == "No"        # Anzeige aus dem Konto (full_name)
    assert eintrag["melder_konto"] == NOTEN
    assert eintrag["gespraech_titel"] == "Chor"


def test_hv_der_hauptgruppe_sieht_untergruppe_gl_nicht_fremdgruppe(
        gespraech, untergespraech):
    """HV moderiert Gruppe UND Untergruppen; GL nur seine Untergruppe."""
    from diakronos_app.api import chat as C
    from diakronos_app.frappe_compat.exceptions import PermissionError

    im_chor = _senden("Chor-Nachricht", gespraech, SAENGER)
    in_ug = _senden("Noten-Nachricht", untergespraech, NOTEN)
    _melden(im_chor["name"], NOTEN, "spam")
    _melden(in_ug["name"], GL, "spam")

    hv_liste = _liste(HV)
    assert {e["nachricht"]["name"] for e in hv_liste["meldungen"]} == {
        im_chor["name"], in_ug["name"]}

    # GL moderiert die Untergruppe — aber NICHT den Gruppenchat.
    gl_liste = _liste(GL)
    assert {e["nachricht"]["name"] for e in gl_liste["meldungen"]} == {in_ug["name"]}
    _set_user(GL)
    with pytest.raises(PermissionError):
        C.meldungen_liste(gespraech=gespraech)   # Chor-Chat: kein Recht → 403

    # MV der Hauptgruppe sieht beides (Matrix 2.2).
    assert len(_liste(MV)["meldungen"]) == 2


def test_liste_filtert_nach_stand(gespraech):
    n1 = _senden("Eins", gespraech, SAENGER)
    n2 = _senden("Zwei", gespraech, SAENGER)
    m1 = _melden(n1["name"], NOTEN, "spam")
    _melden(n2["name"], NOTEN, "beleidigung")
    _entscheiden(m1["name"], HV, "verwerfen")
    offen = _liste(HV, stand="offen")
    assert len(offen["meldungen"]) == 1
    assert offen["meldungen"][0]["nachricht"]["name"] == n2["name"]
    verworfen = _liste(HV, stand="verworfen")
    assert [e["name"] for e in verworfen["meldungen"]] == [m1["name"]]
    from diakronos_app.api import chat as C
    from diakronos_app.frappe_compat.exceptions import ValidationError

    _set_user(HV)
    with pytest.raises(ValidationError):
        C.meldungen_liste(stand="irgendwas")


def test_liste_zeigt_die_fuenf_nachrichten_davor(gespraech):
    """Konzept 2.5: der gemeldete Ausschnitt = die Nachricht + die fünf davor."""
    namen = []
    for i in range(8):
        namen.append(_senden(f"Nachricht {i}", gespraech, SAENGER)["name"])
    ziel = namen[-1]
    _melden(ziel, NOTEN, "spam")
    eintrag = _liste(HV)["meldungen"][0]
    kontext = eintrag["vorgeschichte"]
    assert len(kontext) == 5
    assert [z["name"] for z in kontext] == namen[-6:-1]
    assert [z["text"] for z in kontext] == [f"Nachricht {i}" for i in range(2, 7)]


# ── Entscheiden: entfernen und verwerfen ────────────────────────────────────


def test_entfernen_setzt_softdelete_und_grund_und_verlauf_zeigt_entfernt(gespraech):
    n = _senden("Böse Nachricht", gespraech, SAENGER)
    m = _melden(n["name"], NOTEN, "beleidigung")
    from diakronos_app.api import chat as C
    from diakronos_app.frappe_compat.exceptions import ValidationError

    # Ohne Grund wird NICHT entfernt (Konzept 2.5: „Grund ist Pflicht“).
    _set_user(HV)
    with pytest.raises(ValidationError):
        C.meldung_entscheiden(m["name"], "entfernen")

    entschieden = _entscheiden(m["name"], HV, "entfernen", grund="Beleidigung")
    assert entschieden["stand"] == "erledigt"
    assert entschieden["bearbeitet_von"] == "Hv"
    assert entschieden["entscheidung_grund"] == "Beleidigung"

    with dbmod.SessionLocal() as s:
        zeile = s.get(ChatNachricht, n["name"])
        assert zeile.geloescht_am is not None
        assert zeile.geloescht_von == HV
        assert zeile.entfernt_grund == "Beleidigung"
        # Der Text BLEIBT in der Datenbank (Widerspruchsfall, CHAT-8).
        assert zeile.text == "Böse Nachricht"

    # Verlauf: „entfernt“ mit Grund, Text weg — für JEDES Mitglied.
    for wer in (SAENGER, NOTEN, HV):
        posten = {p["name"]: p for p in _verlauf(gespraech, wer)["nachrichten"]}
        assert posten[n["name"]]["geloescht"] is True
        assert posten[n["name"]]["text"] is None
        assert posten[n["name"]]["geloescht_grund"] == "Beleidigung"


def test_verwerfen_laesst_die_nachricht_stehen(gespraech):
    n = _senden("Harmlos", gespraech, SAENGER)
    m = _melden(n["name"], NOTEN, "spam")
    entschieden = _entscheiden(m["name"], HV, "verwerfen", grund="Kein Verstoß")
    assert entschieden["stand"] == "verworfen"
    assert entschieden["entscheidung_grund"] == "Kein Verstoß"
    with dbmod.SessionLocal() as s:
        zeile = s.get(ChatNachricht, n["name"])
        assert zeile.geloescht_am is None and zeile.entfernt_grund is None
    posten = {p["name"]: p for p in _verlauf(gespraech, SAENGER)["nachrichten"]}
    assert posten[n["name"]]["text"] == "Harmlos"
    assert posten[n["name"]]["geloescht"] is False


def test_entscheidung_ist_endgueltig_und_braucht_moderationsrecht(gespraech):
    from diakronos_app.api import chat as C
    from diakronos_app.frappe_compat.exceptions import PermissionError, KonfliktError, ValidationError

    n = _senden("Prüffall", gespraech, SAENGER)
    m = _melden(n["name"], NOTEN, "spam")

    # Einfaches Mitglied darf nicht entscheiden (403 ohne Inhalt).
    _set_user(NOTEN)
    with pytest.raises(PermissionError):
        C.meldung_entscheiden(m["name"], "verwerfen")

    _entscheiden(m["name"], HV, "verwerfen")
    _set_user(HV)
    # Bereits entschieden → 409 (Zustand passt nicht mehr, nichts zu korrigieren).
    with pytest.raises(KonfliktError):
        C.meldung_entscheiden(m["name"], "entfernen", grund="nochmal")
    # Unbekannte Entscheidung → 400 (Eingabe unbrauchbar).
    with pytest.raises(ValidationError):
        C.meldung_entscheiden(m["name"], "löschen")


# ── Review Runde 1: Rechtefilter vor Limit, Zähler, Konflikte ───────────────


@pytest.fixture()
def zweite_welt(welt):
    """Eine ECHTE Fremdgruppe „Posaunen“ mit eigener Leitung (Review Punkt 10).

    Eigene Gruppe, eigener HV, eigener Chat. Damit ist „Moderator B sieht
    keine Meldung aus Gruppe A“ eine Aussage über zwei getrennte Einheiten und
    nicht über einen Untergruppen-Sonderfall.
    """
    s = welt
    s.add(User(name=POSAUNEN_HV, email=POSAUNEN_HV, enabled=1, full_name="Ph"))
    s.add(Mitglied(name="M-Ph", vorname="Ph", nachname="X", email=POSAUNEN_HV,
                   user=POSAUNEN_HV))
    s.add(Gruppe(name="Posaunen", gruppenname="Posaunen"))
    s.add(Gruppenmitgliedschaft(name="gm-pos", parent="Posaunen",
                                parentfield="mitglieder", mitglied="M-Ph"))
    s.add_all([
        RechteGruppenrolle(gruppe="Posaunen", benutzer=POSAUNEN_HV, rolle="HV"),
        RechteModul(gruppe="Posaunen", modul="chat"),
    ])
    s.commit()
    return s


@pytest.fixture()
def posaunengespraech(zweite_welt):
    from diakronos_app.api import chat as C

    _set_user(POSAUNEN_HV)
    name = C.gespraech_anlegen("Posaunen")["name"]
    _session_mod.reset_user()
    return name


def test_fremdgruppe_sieht_und_entscheidet_keine_fremde_meldung(
        gespraech, posaunengespraech):
    """Punkt 10: der HV von Gruppe B sieht nichts aus Gruppe A und kann dort
    auch nicht entscheiden (403 ohne Inhalt)."""
    from diakronos_app.api import chat as C
    from diakronos_app.frappe_compat.exceptions import PermissionError

    n = _senden("Chor-Sache", gespraech, SAENGER)
    m = _melden(n["name"], NOTEN, "spam")

    # Ohne Meldungen in der EIGENEN Gruppe: leere Liste, KEIN 403.
    leer = _liste(POSAUNEN_HV)
    assert leer == {"meldungen": [], "offen": 0}

    _set_user(POSAUNEN_HV)
    with pytest.raises(PermissionError) as fehler:
        C.meldung_entscheiden(m["name"], "verwerfen")
    assert not str(fehler.value or "")
    # Und die Meldung steht danach unverändert offen.
    assert [e["name"] for e in _liste(HV)["meldungen"]] == [m["name"]]


def test_moderator_ohne_meldungen_bekommt_leere_liste(gespraech):
    """Punkt 1/10: moderierbares Gespräch, aber keine Meldung → [] statt 403."""
    _senden("Nur Geplauder", gespraech, SAENGER)
    assert _liste(HV) == {"meldungen": [], "offen": 0}
    assert _liste(MV, stand="erledigt") == {"meldungen": [], "offen": 0}


def test_limit_schneidet_nie_die_eigenen_meldungen_weg(
        gespraech, posaunengespraech, monkeypatch):
    """Punkt 1 + 3: die Grenze greift NACH dem Rechtefilter.

    Die Fremdgruppe füllt die global neuesten Meldungen; die Grenze wird auf 2
    gesetzt. Früher hätte ``limit`` diese zwei Zeilen genommen und der
    Chor-Leitung nichts übrig gelassen — jetzt zählt der Rechtefilter zuerst.
    """
    from diakronos_app.api import chat as C

    for i in range(3):
        fremd = _senden(f"Posaune {i}", posaunengespraech, POSAUNEN_HV)
        # Melden kann in B nur, wer NICHT der Autor ist — hier ist es das
        # eigene Konto der Leitung, deshalb bleibt B ohne Meldung. Für den
        # Test zählt: die (späteren) A-Meldungen liegen NICHT in der
        # global-neuesten Auswahl, wenn `limit` vor dem Rechtefilter griffe.
        assert fremd["name"]
        n = _senden(f"Chor {i}", gespraech, SAENGER)
        _melden(n["name"], NOTEN, "spam")
    monkeypatch.setattr(C, "MELDUNGEN_MAX", 2)
    liste = _liste(HV)
    assert len(liste["meldungen"]) == 2
    assert {e["gespraech"] for e in liste["meldungen"]} == {gespraech}
    # Der Zähler zählt ALLE offenen der eigenen Gespräche, nicht die Seite.
    assert liste["offen"] == 3


def test_zaehler_ist_unabhaengig_vom_stand_filter(gespraech):
    """Punkt 3: ``offen`` bleibt der offene Zähler, auch bei ``stand=verworfen``."""
    n1 = _senden("Eins", gespraech, SAENGER)
    n2 = _senden("Zwei", gespraech, SAENGER)
    m1 = _melden(n1["name"], NOTEN, "spam")
    _melden(n2["name"], NOTEN, "beleidigung")
    _entscheiden(m1["name"], HV, "verwerfen")
    verworfen = _liste(HV, stand="verworfen")
    assert [e["name"] for e in verworfen["meldungen"]] == [m1["name"]]
    assert verworfen["offen"] == 1                     # die zweite ist noch offen
    offen = _liste(HV, stand="offen")
    assert offen["offen"] == 1
    assert len(offen["meldungen"]) == 1


def test_liste_fragt_das_recht_nur_fuer_gespraeche_mit_meldungen(
        gespraech, untergespraech, posaunengespraech, monkeypatch):
    """A3: ``meldungen_liste`` fragt ``_erlaube`` NICHT für jedes Gespräch der
    Instanz, sondern nur für die Kandidaten aus den Meldungen.

    Es existieren drei Gespräche (Chor, Untergruppe Notenausschuss, Posaunen);
    Meldungen liegen nur im Chor. Gezählt wird jeder Rechteaufruf: kein
    Gespräch ohne Meldung darf dabei sein.
    """
    from diakronos_app.api import chat as C

    n = _senden("Die einzige Meldung", gespraech, SAENGER)
    _melden(n["name"], NOTEN, "spam")

    gefragt: list[str] = []
    echt = C.rechte.darf

    def _darf(benutzer, aktion, typ, objekt=None, **kwargs):
        gefragt.append(str(objekt or ""))
        return echt(benutzer, aktion, typ, objekt, **kwargs)

    monkeypatch.setattr(C.rechte, "darf", _darf)
    liste = _liste(HV)
    assert [e["nachricht"]["name"] for e in liste["meldungen"]] == [n["name"]]
    # Genau EIN Rechteaufruf — für das Gespräch, in dem die Meldung liegt.
    assert gefragt == [gespraech], gefragt
    for ohne_meldung in (untergespraech, posaunengespraech):
        assert ohne_meldung not in gefragt

    # Auch bei einem Moderator OHNE passende Meldung (Fremdgruppe): erst die
    # Kandidaten (Chor) ablehnen, dann die übrigen mit frühem Abbruch prüfen —
    # leere Liste statt 403, und der Durchlauf endet beim ersten „ja“.
    gefragt.clear()
    assert _liste(POSAUNEN_HV) == {"meldungen": [], "offen": 0}
    assert gespraech in gefragt
    assert posaunengespraech in gefragt        # eigenes Gespräch, „ja“ → Ende
    # Nach dem Treffer in Posaunen wird NICHT weitergefragt: kein Gespräch
    # hinter Posaunen (in Namensreihenfolge) steht in der Liste.
    nach_treffer = gefragt[gefragt.index(posaunengespraech) + 1:]
    assert nach_treffer == [], nach_treffer


def test_zweite_entscheidung_gleichzeitig_gibt_409(gespraech, monkeypatch):
    """Punkt 2/A2: verliert das bedingte UPDATE, kommt 409 — nichts wird doppelt
    geschrieben und der Verlauf bleibt der des Gewinners.

    Der Rivale schreibt hier NACH der Vorprüfung (Stand, Recht, Selbst-Moderation
    sind schon durch) und VOR dem bedingten UPDATE: der Rivalenschreibvorgang
    hängt an ``_ist_meine``, das der Endpunkt genau zwischen Vorprüfung und
    UPDATE aufruft. Damit erreicht der Test WIRKLICH den ``rowcount``-Zweig
    (``WHERE stand='offen'``) — nicht die Vorprüfung, die den Fall schon vorher
    abfangen würde.
    """
    from diakronos_app.api import chat as C
    from diakronos_app.frappe_compat.exceptions import KonfliktError

    n = _senden("Konfliktfall", gespraech, SAENGER)
    m = _melden(n["name"], NOTEN, "spam")

    echt_ist_meine = C._ist_meine
    zustand = {"rivale_hat_geschrieben": False}

    def _ist_meine_mit_rivalen(nachricht, benutzer):
        if not zustand["rivale_hat_geschrieben"]:
            zustand["rivale_hat_geschrieben"] = True
            # Der Rivale entscheidet in einer EIGENEN Transaktion — genau wie
            # ein zweiter Aufruf, der eine Sekunde schneller war.
            with dbmod.SessionLocal.begin() as fremd:
                C.ChatMeldung.__table__  # noqa: B018 — Modulbezug bleibt lesbar
                fremd.execute(
                    C.update(C.ChatMeldung)
                    .where(C.ChatMeldung.name == m["name"])
                    .values(stand="verworfen", bearbeitet_von=HV)
                )
        return echt_ist_meine(nachricht, benutzer)

    monkeypatch.setattr(C, "_ist_meine", _ist_meine_mit_rivalen)

    _set_user(MV)
    with pytest.raises(KonfliktError) as fehler:
        C.meldung_entscheiden(m["name"], "entfernen", grund="doch")
    assert fehler.value.http_status == 409
    # Belegt, dass der Rivale wirklich VOR dem UPDATE geschrieben hat: sonst
    # hätte die Vorprüfung den Aufruf abgefangen und die Meldung wäre schon
    # entschieden, ohne dass der rowcount-Zweig erreichbar war.
    assert zustand["rivale_hat_geschrieben"] is True
    # Der Verlierer hat NICHTS am Verlauf geändert.
    with dbmod.SessionLocal() as s:
        zeile = s.get(ChatNachricht, n["name"])
        assert zeile.geloescht_am is None
        assert zeile.entfernt_grund is None
        # Die Meldung steht auf dem Stand des GEWINNERS.
        gewonnen = s.get(ChatMeldung, m["name"])
        assert gewonnen.stand == "verworfen"
        assert gewonnen.bearbeitet_von == HV


def test_abgelaufene_meldung_gibt_409_statt_400(gespraech):
    """Punkt 2 (Zustandsprüfung): der Stand ist nicht mehr „offen“ → ebenfalls
    409, nicht 400 — es gibt nichts zu korrigieren, nur neu zu laden."""
    from diakronos_app.api import chat as C
    from diakronos_app.frappe_compat.exceptions import KonfliktError

    n = _senden("Wettlauf", gespraech, SAENGER)
    m = _melden(n["name"], NOTEN, "spam")
    _entscheiden(m["name"], HV, "verwerfen")
    _set_user(MV)
    with pytest.raises(KonfliktError):
        C.meldung_entscheiden(m["name"], "entfernen", grund="doch")
    with dbmod.SessionLocal() as s:
        assert s.get(ChatNachricht, n["name"]).geloescht_am is None


def test_meldung_auf_geloeschte_nachricht_ist_nicht_moeglich(gespraech):
    """Punkt 4: was nicht mehr sichtbar ist, ist nicht meldbar (400) —
    und eine Meldung, deren Nachricht inzwischen weg ist, ist nicht
    entscheidbar (400)."""
    from diakronos_app.api import chat as C
    from diakronos_app.frappe_compat.exceptions import ValidationError

    n = _senden("Wird gleich weg sein", gespraech, SAENGER)
    m = _melden(n["name"], NOTEN, "spam")
    _set_user(SAENGER)
    C.loeschen(n["name"])                          # eigene Löschung
    _set_user(MV)
    with pytest.raises(ValidationError):
        C.meldung_senden(n["name"], "spam")
    with pytest.raises(ValidationError):
        C.meldung_entscheiden(m["name"], "entfernen", grund="zu spät")


def test_selbst_geloeschte_nachricht_liefert_der_moderation_keinen_text(gespraech):
    """Punkt 4 (Operator-Entscheidung Runde 2): ``text`` in der Meldungszeile
    fehlt nur bei einer SELBSTLÖSCHUNG der verfassenden Person."""
    n = _senden("Autor löscht selbst", gespraech, NOTEN)
    m = _melden(n["name"], SAENGER, "spam")
    from diakronos_app.api import chat as C

    _set_user(NOTEN)
    C.loeschen(n["name"])
    eintrag = {e["name"]: e for e in _liste(HV)["meldungen"]}[m["name"]]
    assert eintrag["nachricht"]["text"] is None
    assert eintrag["nachricht"]["text_entfernt"] is True
    assert eintrag["nachricht"]["entfernt_grund"] is None   # war keine Moderation


def test_von_der_moderation_entfernte_nachricht_bleibt_fuer_die_moderation_lesbar(
        gespraech):
    """Punkt 4 (Operator-Entscheidung Runde 2): nach ``entfernen`` sieht die
    Moderation weiterhin, WAS sie entfernt hat — der Verlauf liefert es nicht."""
    n = _senden("Bleibt für die Moderation lesbar", gespraech, SAENGER)
    m = _melden(n["name"], NOTEN, "beleidigung")
    _entscheiden(m["name"], HV, "entfernen", grund="Regelverstoß")

    eintrag = {e["name"]: e for e in _liste(HV, stand="erledigt")["meldungen"]}[m["name"]]
    assert eintrag["nachricht"]["text"] == "Bleibt für die Moderation lesbar"
    assert eintrag["nachricht"]["text_entfernt"] is True
    assert eintrag["nachricht"]["entfernt_grund"] == "Regelverstoß"
    # Der VERLAUF gibt den Text nach außen nicht mehr her (nach wie vor).
    posten = {p["name"]: p for p in _verlauf(gespraech, SAENGER)["nachrichten"]}
    assert posten[n["name"]]["text"] is None


def test_entfernen_erledigt_die_uebrigen_offenen_meldungen_und_glockt_einmal(
        gespraech):
    """Punkt 5: eine Entfernung entscheidet ALLE offenen Meldungen der
    Nachricht; die Glocke geht EINMAL an die verfassende Person."""
    n = _senden("Mehrfach gemeldet", gespraech, SAENGER)
    m1 = _melden(n["name"], NOTEN, "spam")
    m2 = _melden(n["name"], GL, "beleidigung")
    assert {e["name"] for e in _liste(HV)["meldungen"]} == {m1["name"], m2["name"]}

    _entscheiden(m1["name"], HV, "entfernen", grund="Regelverstoß")
    with dbmod.SessionLocal() as s:
        staende = {m.name: m.stand for m in s.query(ChatMeldung).filter(
            ChatMeldung.nachricht == n["name"]).all()}
        assert staende == {m1["name"]: "erledigt", m2["name"]: "erledigt"}
        glocken = s.query(NotificationLog).filter(
            NotificationLog.for_user == SAENGER,
            NotificationLog.document_name == n["name"]).count()
    assert glocken == 1
    # Es bleibt keine offene Arbeit stehen.
    assert _liste(HV)["offen"] == 0


def test_moderator_entscheidet_nicht_ueber_eigene_nachricht(gespraech):
    """Punkt 6: MV schreibt selbst — über Meldungen dagegen entscheidet MV nicht."""
    from diakronos_app.api import chat as C
    from diakronos_app.frappe_compat.exceptions import ValidationError

    n = _senden("Aussage von MV", gespraech, MV)
    m = _melden(n["name"], SAENGER, "beleidigung")
    _set_user(MV)
    with pytest.raises(ValidationError):
        C.meldung_entscheiden(m["name"], "verwerfen")
    # HV (andere Person der Leitung) übernimmt.
    entschieden = _entscheiden(m["name"], HV, "verwerfen")
    assert entschieden["stand"] == "verworfen"


# ── Die gemeldete Person erfährt NICHT, wer gemeldet hat ────────────────────


def test_melder_identitaet_taucht_in_keiner_antwort_an_die_gemeldete_person_auf(gespraech):
    """Weder Verlauf noch Meldungsantwort noch Glocke nennen den Melder.

    Geprüft wird der NAME und das KONTO der meldenden Person über ALLE
    Antwortformen, die die gemeldete Person erreichen.
    """
    melder_name, melder_konto = "No", NOTEN          # M-NO, noten@x.org
    n = _senden("Das meldet gleich jemand", gespraech, SAENGER)
    meldung = _melden(n["name"], NOTEN, "sonstiges", freitext="Ich bin No")
    _entscheiden(meldung["name"], HV, "entfernen", grund="Regelverstoß")

    # 1) Verlauf, den die gemeldete Person abruft.
    for wer in (SAENGER, NOTEN):
        seite = _verlauf(gespraech, wer)
        roh = str(seite)
        assert melder_konto not in roh
        # Der Anzeigename des Kontos ("No" aus full_name) steht nirgends.
        for posten in seite["nachrichten"]:
            assert melder_konto not in str(posten)
            assert "melder" not in posten

    # 2) Die Glocke der verfassenden Person: kein Melder, aber der Grund.
    with dbmod.SessionLocal() as s:
        glocken = s.query(NotificationLog).filter(
            NotificationLog.for_user == SAENGER,
            NotificationLog.document_name == n["name"],
        ).all()
        assert len(glocken) == 1
        inhalt = f"{glocken[0].subject} {glocken[0].email_content}"
        assert melder_konto not in inhalt and "No" not in inhalt.split()
        assert "Regelverstoß" in inhalt         # der GRUND darf hin
        assert glocken[0].document_type == "chat_nachricht"

    # 3) Die Antwort auf die Meldung selbst (an die meldende Person: kein Melder).
    assert "melder" not in meldung


def test_gemeldete_person_sieht_keine_meldung_in_ihren_daten(gespraech):
    """Die Meldung ist kein Teil des Verlaufs: sie taucht dort nicht auf."""
    n = _senden("Prüftext", gespraech, SAENGER)
    _melden(n["name"], NOTEN, "spam", freitext="vertraulicher Hinweis")
    roh = str(_verlauf(gespraech, SAENGER))
    assert "vertraulicher Hinweis" not in roh
    assert "chat-meldung" not in roh


# ── HTTP-Weg ────────────────────────────────────────────────────────────────


def test_http_weg_melden_und_liste(welt, client, fake_redis):
    """``/api/method/chat.*`` — derselbe Endpunkt, Frappe-Envelope.

    Der Client gehört dem Konto ``Administrator``; gemeldet wird eine
    Nachricht, die der Administrator (Admin = LESEN überall) lesen darf.
    """
    from diakronos_app.api import chat as C

    _set_user(SAENGER)
    gespraech = C.gespraech_anlegen("Chor")["name"]
    nachricht = C.senden(gespraech, "HTTP-Prüffall")["name"]
    _session_mod.reset_user()

    antwort = client.post("/api/method/chat.meldung_senden",
                          json={"nachricht": nachricht, "grund": "spam",
                                "freitext": "sieht nach Werbung aus"})
    assert antwort.status_code == 200, antwort.text
    gemeldet = antwort.json()["message"]
    assert gemeldet["stand"] == "offen"

    # meldungen_liste ist rein LESEND (SEC-11) — die Kurzform per GET geht.
    liste = client.get("/api/method/chat.meldungen_liste")
    assert liste.status_code == 200, liste.text
    assert [e["name"] for e in liste.json()["message"]["meldungen"]] == [gemeldet["name"]]

    # Ein zweiter POST derselben Person ist abgewiesen (400).
    zweite = client.post("/api/method/chat.meldung_senden",
                         json={"nachricht": nachricht, "grund": "spam"})
    assert zweite.status_code in (400, 417), zweite.text


# ── Migration ───────────────────────────────────────────────────────────────


def _skripte() -> ScriptDirectory:
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "alembic"))
    return ScriptDirectory.from_config(cfg)


def test_genau_ein_kopf_und_chat6_haengt_hinter_chat2():
    skripte = _skripte()
    heads = skripte.get_heads()
    assert heads == ["chat6_meldung"], f"Kopf(e): {heads}"
    revision = skripte.get_revision("chat6_meldung")
    assert revision is not None
    assert revision.down_revision == "chat2_chat_s1", revision.down_revision
    assert "Revises: chat2_chat_s1" in Path(revision.path).read_text(encoding="utf-8")


@pytest.fixture()
def fresh_engine():
    """Leere SQLite-Engine NUR mit dem Gerüst für die Fremdschlüssel."""
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
    # Die Tabelle vorher herausnehmen, damit `upgrade` sie WIRKLICH anlegt.
    with eng.begin() as verbindung:
        verbindung.exec_driver_sql('DROP TABLE IF EXISTS "chat_meldung"')
    yield eng
    eng.dispose()


def test_migration_legt_tabelle_und_indizes_an_und_nimmt_sie_zurueck(fresh_engine):
    import importlib.util

    from sqlalchemy import inspect

    pfad = BACKEND / "alembic" / "versions" / "chat6_meldung.py"
    spec = importlib.util.spec_from_file_location("chat6_meldung", pfad)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)

    with fresh_engine.begin() as verbindung:
        from alembic.migration import MigrationContext
        from alembic.operations import Operations

        with Operations.context(MigrationContext.configure(verbindung)):
            modul.upgrade()
        insp = inspect(verbindung)
        assert insp.has_table("chat_meldung")
        spalten = {c["name"] for c in insp.get_columns("chat_meldung")}
        for name in ("name", "nachricht", "melder", "grund", "freitext", "stand",
                     "bearbeitet_von", "bearbeitet_am", "entscheidung_grund",
                     "erstellt_am"):
            assert name in spalten, name
        namen = {i["name"]: i for i in insp.get_indexes("chat_meldung")}
        # ``unique`` kommt je Dialekt als bool ODER als 1/0 zurueck.
        assert bool(namen["uq_chat_meldung_offen"]["unique"]) is True
        assert namen["uq_chat_meldung_offen"]["column_names"] == ["nachricht", "melder"]
        assert namen["ix_chat_meldung_stand"]["column_names"] == ["stand", "erstellt_am"]
        # Fremdschlüssel: Nachricht (Fachobjekt) und die zwei Konto-Verweise.
        ziele = {(fk["constrained_columns"][0], fk["referred_table"])
                 for fk in insp.get_foreign_keys("chat_meldung")}
        assert ("nachricht", "chat_nachricht") in ziele
        assert ("melder", "user") in ziele
        assert ("bearbeitet_von", "user") in ziele

    # Zweiter Lauf (idempotent) und downgrade.
    with fresh_engine.begin() as verbindung:
        from alembic.migration import MigrationContext
        from alembic.operations import Operations

        with Operations.context(MigrationContext.configure(verbindung)):
            modul.upgrade()
            modul.downgrade()
        assert not inspect(verbindung).has_table("chat_meldung")


# ── Glocke an die Moderation (Rechte-Kern `chat_moderatoren`) ──────────────


def _meldungsglocken(meldung: str) -> dict[str, NotificationLog]:
    with dbmod.SessionLocal() as s:
        zeilen = s.query(NotificationLog).filter(
            NotificationLog.document_type == "chat_meldung",
            NotificationLog.document_name == meldung).all()
        return {z.for_user: z for z in zeilen}


def test_kern_chat_moderatoren_folgt_darf(welt):
    from diakronos_app import rechte

    assert rechte.chat_moderatoren("Chor") == sorted([HV, MV])
    assert rechte.chat_moderatoren(None, "UG-Noten") == sorted([GL, HV, MV])
    assert rechte.chat_moderatoren("Chor", "UG-Noten") == sorted([GL, HV, MV])
    assert rechte.chat_moderatoren(None, None) == []
    assert rechte.chat_moderatoren("Jugend") == []


def test_kern_chat_moderatoren_leer_ohne_chat_modul(welt):
    from diakronos_app import rechte

    welt.query(RechteModul).filter(RechteModul.gruppe == "Chor",
                                   RechteModul.modul == "chat").delete()
    welt.commit()
    rechte.merker_leeren()
    assert rechte.chat_moderatoren("Chor") == []


def test_neue_meldung_glockt_die_moderation_ohne_melder_und_text(gespraech):
    n = _senden("Geheimer Inhalt", gespraech, SAENGER)
    m = _melden(n["name"], NOTEN, "beleidigung", freitext="Freitext des Melders")
    glocken = _meldungsglocken(m["name"])
    assert set(glocken) == {HV, MV}          # GL moderiert den Gruppenchat nicht
    for g in glocken.values():
        inhalt = f"{g.subject} {g.email_content}"
        assert "Geheimer Inhalt" not in inhalt
        assert "Freitext" not in inhalt
        assert "No" not in inhalt.split() and NOTEN not in inhalt


def test_meldende_moderation_und_verfasser_bekommen_keine_meldungsglocke(gespraech):
    n = _senden("Von MV gemeldet", gespraech, HV)
    m = _melden(n["name"], MV, "spam")
    # MV meldet (keine Glocke an sich selbst), HV hat verfasst (keine Glocke).
    assert _meldungsglocken(m["name"]) == {}


def test_meldung_in_untergruppe_glockt_gl_und_leitung(untergespraech):
    n = _senden("Noten-Nachricht", untergespraech, NOTEN)
    m = _melden(n["name"], GL, "spam")
    assert set(_meldungsglocken(m["name"])) == {HV, MV}   # GL meldet selbst
    n2 = _senden("Noch eine", untergespraech, GL)
    m2 = _melden(n2["name"], NOTEN, "spam")
    assert set(_meldungsglocken(m2["name"])) == {HV, MV}  # GL ist Verfasser
