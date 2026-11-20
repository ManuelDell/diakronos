"""CHAT-7b-3 — Runden: die vier fehlenden Felder für die Oberfläche.

Geprüft wird gegen die ECHTEN Endpunkte (``api/chat.py``), den ECHTEN
Rechte-Kern und die ECHTE Datenbank. Der VERTRAG (verbindlich, die Oberfläche
CHAT-7b-UI-a wird parallel dagegen gebaut):

  1. ``system.vorschlag`` / ``system.eigene`` an der Verlaufszeile eines
     Vorschlags — ``eigene`` hängt an der LESENDEN Person.
  2. ``chat.verlauf`` trägt ``ab_eintritt`` (bool): Runde UND Eintritt nach
     dem Anlegen der Runde.
  3. ``chat.meine_gespraeche`` trägt für Runden ``mitglieder`` (aktiv, inkl.
     der lesenden Person) in stabiler Reihenfolge (Eintritt, dann Name) — für
     1:1/Gruppen FEHLT das Feld.
  4. Ausgetretene fehlen, gesperrte Aktive stehen trotzdem drin.

Aufruf (Karte):
    docker run --rm --network none --entrypoint python -v <wt>:/repo:ro \\
      -w /repo/backend -e PYTHONPATH=/repo/backend/src:/repo/backend/tests:/repo/tools \\
      -e PYTHONDONTWRITEBYTECODE=1 <vorbau> -m pytest -q -p no:cacheprovider \\
      tests/test_chat7b3_felder.py
"""

from __future__ import annotations

import importlib
from datetime import timedelta

import pytest

from diakronos_app.models.chat import (
    ART_DIREKT,
    ART_GRUPPE,
    ART_RUNDE,
    ChatGespraech,
    ChatNachricht,
    ChatTeilnehmer,
    VORSCHLAG_OFFEN,
)
from diakronos_app.models.core import HasRole, User
from diakronos_app.models.diakonos import Mitglied

#: Die Test-Naht liegt im MODUL ``frappe_compat.session`` (wie die chat7b-Tests).
_session_mod = importlib.import_module("diakronos_app.frappe_compat.session")

ANNA = "anna@x.org"
BERT = "bert@x.org"
CLARA = "clara@x.org"
DIETER = "dieter@x.org"
EMMA = "emma@x.org"
ADMIN = "admin@x.org"

ALLE = [ANNA, BERT, CLARA, DIETER, EMMA]

MI = {
    ANNA: "M-00-Anna", BERT: "M-01-Bert", CLARA: "M-02-Clara",
    DIETER: "M-03-Dieter", EMMA: "M-04-Emma",
}


def _set_user(konto: str) -> None:
    _session_mod.set_user(konto)


@pytest.fixture()
def welt(patched_db):
    """Fünf Gemeindemitglieder mit Konto plus Administrator (wie chat7b)."""
    s = patched_db()
    s.add(User(name="Administrator", email="admin@example.invalid", enabled=1,
               full_name="Administrator"))
    for konto in ALLE + [ADMIN]:
        s.add(User(name=konto, email=konto, enabled=1,
                   full_name=konto.split("@")[0].capitalize() + " Test"))
    namen = {ANNA: ("Anna", "Beispiel"), BERT: ("Bert", "Brandner"),
             CLARA: ("Clara", "Clausen"), DIETER: ("Dieter", "Dorn"),
             EMMA: ("Emma", "Eberle")}
    for i, (konto, (vor, nach)) in enumerate(namen.items()):
        s.add(Mitglied(name=f"M-{i:02d}-{vor}", vorname=vor, nachname=nach,
                       email=konto, user=konto, status="Aktiv"))
    s.add(HasRole(name="hr-admin", parent=ADMIN, parenttype="User",
                  role="System Manager"))
    s.commit()
    yield s
    s.close()


# ── Aufruf-Hilfen ───────────────────────────────────────────────────────────


def _anlegen(titel: str, mitglieder, konto: str = ANNA) -> dict:
    from diakronos_app.api import chat as C

    _set_user(konto)
    return C.runde_anlegen(titel, mitglieder)


def _vorschlagen(gespraech: str, mitglied: str, konto: str) -> dict:
    from diakronos_app.api import chat as C

    _set_user(konto)
    return C.runde_vorschlagen(gespraech, mitglied)


def _zustimmen(vorschlag: str, konto: str) -> dict:
    from diakronos_app.api import chat as C

    _set_user(konto)
    return C.runde_zustimmen(vorschlag)


def _verlassen(gespraech: str, konto: str) -> dict:
    from diakronos_app.api import chat as C

    _set_user(konto)
    return C.runde_verlassen(gespraech)


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


def _kopf_aus_liste(konto: str, gespraech: str) -> dict:
    return {e["name"]: e for e in _meine(konto)["gespraeche"]}[gespraech]


def _sperren(mitglied: str, konto: str) -> dict:
    from diakronos_app.api import chat as C

    _set_user(konto)
    return C.kontakt_sperren(mitglied)


def _direkt_oeffnen(mitglied: str, konto: str) -> dict:
    from diakronos_app.api import chat as C

    _set_user(konto)
    return C.direkt_oeffnen(mitglied)


def _systemzeilen(verlauf: dict) -> list[dict]:
    return [z for z in verlauf["nachrichten"]
            if z.get("system", {}).get("art") == "runde_vorschlag"]


def _drei(titel: str = "Kigo-Vorbereitung") -> dict:
    """Die Standard-Runde Anna/Bert/Clara."""
    return _anlegen(titel, [MI[BERT], MI[CLARA]])


# ── 1) system.vorschlag / system.eigene ────────────────────────────────────


def test_system_vorschlag_ist_die_kennung_fuer_zustimmen(welt):
    """Ende-zu-Ende: die Kennung aus dem Verlauf trägt eine Zustimmung."""
    kopf = _drei()
    antwort = _vorschlagen(kopf["name"], MI[DIETER], ANNA)
    kennung = antwort["vorschlag"]["name"]
    # Die Zeile der Sende-Antwort trägt dieselbe Kennung wie die Vorschlagszeile.
    assert antwort["nachricht"]["system"]["vorschlag"] == kennung
    verlauf = _verlauf(kopf["name"], BERT)
    (zeile,) = _systemzeilen(verlauf)
    assert zeile["system"]["vorschlag"] == kennung
    # ... und mit GENAU dieser Kennung nimmt die Runde den Vorschlag an.
    _zustimmen(zeile["system"]["vorschlag"], BERT)
    letzte = _zustimmen(zeile["system"]["vorschlag"], CLARA)
    assert letzte["angenommen"] is True
    assert letzte["vorschlag"]["stand"] != VORSCHLAG_OFFEN


def test_system_eigene_haengt_an_der_lesenden_person(welt):
    kopf = _drei()
    v = _vorschlagen(kopf["name"], MI[DIETER], ANNA)["vorschlag"]
    # Die vorschlagende Person sieht „mein Vorschlag“ ...
    für_anna = _systemzeilen(_verlauf(kopf["name"], ANNA))[0]
    assert für_anna["system"]["eigene"] is True
    # ... die übrigen nicht. Kein Name, kein Textunterschied — nur das Flag.
    for konto in (BERT, CLARA):
        zeile = _systemzeilen(_verlauf(kopf["name"], konto))[0]
        assert zeile["system"]["eigene"] is False
        assert zeile["system"]["vorschlag"] == v["name"]
        assert zeile["text"] == "Anna möchte Dieter Dorn hinzufügen."
    # Das `eigene` der Zeile selbst bleibt davon unberührt: kein Besitz.
    assert für_anna["eigene"] is False and zeile["eigene"] is False
    # Nach der Annahme gilt dasselbe (Stand ändert nur den Satz).
    _zustimmen(v["name"], BERT)
    _zustimmen(v["name"], CLARA)
    assert _systemzeilen(_verlauf(kopf["name"], ANNA))[0]["system"]["eigene"] is True
    assert _systemzeilen(_verlauf(kopf["name"], BERT))[0]["system"]["eigene"] is False


def test_system_eigene_fehlt_nicht_bei_fremden_systemzeilen_aber_andere_zeilen_tragen_kein_system(welt):
    """Nur Vorschlagszeilen haben ``system`` — normale Beiträge nicht."""
    kopf = _drei()
    _senden(kopf["name"], "Hallo zusammen", BERT)
    _vorschlagen(kopf["name"], MI[DIETER], ANNA)
    zeilen = _verlauf(kopf["name"], BERT)["nachrichten"]
    ohne = [z for z in zeilen if z.get("system") is None]
    assert len(ohne) == 1 and ohne[0]["text"] == "Hallo zusammen"
    assert "vorschlag" not in ohne[0] and "eigene" in ohne[0]
    mit = [z for z in zeilen if z.get("system")]
    assert len(mit) == 1
    assert set(mit[0]["system"]) == {"art", "stand", "vorschlag", "eigene"}


# ── 2) ab_eintritt ─────────────────────────────────────────────────────────


def test_ab_eintritt_false_fuer_gruendungsmitglieder(welt):
    kopf = _drei()
    for konto in (ANNA, BERT, CLARA):
        assert _verlauf(kopf["name"], konto)["ab_eintritt"] is False


def test_ab_eintritt_false_fuer_nicht_runden(welt):
    """1:1 und Gruppe: Feld ist da (bool), aber immer false."""
    direkt = _direkt_oeffnen(MI[BERT], ANNA)
    assert _verlauf(direkt["name"], ANNA)["ab_eintritt"] is False
    assert _verlauf(direkt["name"], BERT)["ab_eintritt"] is False


def test_ab_eintritt_true_fuer_nachtraeglich_hinzugefuegte(welt, patched_db):
    kopf = _drei()
    v = _vorschlagen(kopf["name"], MI[DIETER], ANNA)["vorschlag"]
    _zustimmen(v["name"], BERT)
    _zustimmen(v["name"], CLARA)
    # Dieter ist jetzt dabei — aber erst NACH dem Anlegen der Runde.
    assert _verlauf(kopf["name"], DIETER)["ab_eintritt"] is True
    # Die Gründungsmitglieder bleiben false, auch nachdem jemand dazukam.
    for konto in (ANNA, BERT, CLARA):
        assert _verlauf(kopf["name"], konto)["ab_eintritt"] is False
    # Es ist ein bool, keine Zahl und keine Auskunft über alte Nachrichten.
    antwort = _verlauf(kopf["name"], DIETER)
    assert isinstance(antwort["ab_eintritt"], bool)
    assert set(antwort) == {"gespraech", "richtung", "nachrichten",
                            "ab_eintritt", "vor", "seit"}


def test_ab_eintritt_gilt_auch_fuer_wiedereintritt(welt, patched_db):
    """Wer wieder eintritt, hat einen NEUEN Eintritt nach dem Anlegen."""
    kopf = _drei()
    _verlassen(kopf["name"], CLARA)
    v = _vorschlagen(kopf["name"], MI[CLARA], ANNA)["vorschlag"]
    _zustimmen(v["name"], BERT)   # nötig: Anna + Bert sind die Aktiven
    assert _verlauf(kopf["name"], CLARA)["ab_eintritt"] is True


def test_ab_eintritt_false_ohne_eintrittszeitpunkt(welt, patched_db):
    """Bestandszeile ohne ``sichtbar_ab`` → nichts zu vergleichen → false."""
    kopf = _drei()
    s = patched_db()
    zeile = s.get(ChatTeilnehmer, (kopf["name"], BERT))
    zeile.sichtbar_ab = None
    s.commit()
    assert _verlauf(kopf["name"], BERT)["ab_eintritt"] is False


# ── 3) mitglieder in meine_gespraeche ──────────────────────────────────────


def test_mitglieder_nur_bei_runden(welt, patched_db):
    kopf = _drei()
    direkt = _direkt_oeffnen(MI[BERT], ANNA)
    eintrag = _kopf_aus_liste(ANNA, kopf["name"])
    assert eintrag["art"] == ART_RUNDE
    assert [m["mitglied"] for m in eintrag["mitglieder"]] == [MI[ANNA], MI[BERT], MI[CLARA]]
    # 1:1: das Feld FEHLT (nicht `None`).
    assert "mitglieder" not in _kopf_aus_liste(ANNA, direkt["name"])
    assert direkt["art"] == ART_DIREKT


def test_mitglieder_fehlt_auch_im_gruppengespraech(welt, patched_db):
    """Ein echtes Gruppen-Gespräch (Chor) trägt das Feld ebenfalls nicht."""
    from diakronos_app.api import chat as C
    from diakronos_app.models.diakonos import Gruppe, Gruppenmitgliedschaft
    from diakronos_app.models.rechte import RechteModul

    s = patched_db()
    s.add(Gruppe(name="Chor", gruppenname="Chor"))
    for konto in (ANNA, BERT):
        s.add(Gruppenmitgliedschaft(name=f"gm-{konto}", parent="Chor",
                                    parentfield="mitglieder", mitglied=MI[konto]))
    s.add(RechteModul(gruppe="Chor", modul="chat"))
    s.commit()
    _set_user(ANNA)
    name = C.gespraech_anlegen("Chor")["name"]
    _senden(name, "Hallo Chor", ANNA)
    eintrag = _kopf_aus_liste(ANNA, name)
    assert eintrag["art"] == ART_GRUPPE
    assert "mitglieder" not in eintrag
    # Der Verlauf trägt `ab_eintritt` (bool) — bei einer Gruppe immer false.
    assert _verlauf(name, ANNA)["ab_eintritt"] is False


def test_mitglieder_gleiche_form_wie_runde_anlegen(welt):
    """Beide Wege liefern dieselbe FORM und dieselbe Reihenfolge (eine Quelle)."""
    kopf = _drei()
    aus_liste = _kopf_aus_liste(ANNA, kopf["name"])["mitglieder"]
    assert aus_liste == kopf["mitglieder"]
    # Vertrag 3: je Eintrag GENAU {mitglied, anzeigename} — kein zweites Feld.
    for eintrag in aus_liste:
        assert set(eintrag) == {"mitglied", "anzeigename"}
    for konto in (ANNA, BERT, CLARA):
        assert _kopf_aus_liste(konto, kopf["name"])["mitglieder"] == kopf["mitglieder"]
    # Nur Personen der Runde — nichts über Dritte.
    assert {m["mitglied"] for m in aus_liste} == {MI[ANNA], MI[BERT], MI[CLARA]}
    # Anzeigenamen kommen aus `_personen` („Vorname Nachname“), nicht aus dem Konto.
    namen = {m["mitglied"]: m["anzeigename"] for m in aus_liste}
    assert namen == {MI[ANNA]: "Anna Beispiel", MI[BERT]: "Bert Brandner",
                     MI[CLARA]: "Clara Clausen"}


def test_mitglieder_reihenfolge_eintritt_dann_name(welt, patched_db):
    """Stabil: erst nach Eintritt, dann nach Anzeigename — nicht nach Kennung."""
    # Clara ist die erste andere Person, Bert die zweite, Anna legt an.
    kopf = _anlegen("Reihenfolge", [MI[CLARA], MI[BERT]])
    s = patched_db()
    basis = s.get(ChatGespraech, kopf["name"]).angelegt_am
    # Eintritte künstlich auseinanderziehen: Anna > Bert > Clara.
    s.get(ChatTeilnehmer, (kopf["name"], ANNA)).hinzugefuegt_am = basis + timedelta(minutes=3)
    s.get(ChatTeilnehmer, (kopf["name"], BERT)).hinzugefuegt_am = basis + timedelta(minutes=2)
    s.get(ChatTeilnehmer, (kopf["name"], CLARA)).hinzugefuegt_am = basis + timedelta(minutes=1)
    s.commit()
    assert ([m["mitglied"] for m in _kopf_aus_liste(ANNA, kopf["name"])["mitglieder"]]
            == [MI[CLARA], MI[BERT], MI[ANNA]])
    # Gleicher Eintritt (Anlegen) → entscheidet der Anzeigename.
    for konto in (ANNA, BERT, CLARA):
        s.get(ChatTeilnehmer, (kopf["name"], konto)).hinzugefuegt_am = basis
    s.commit()
    assert ([m["mitglied"] for m in _kopf_aus_liste(ANNA, kopf["name"])["mitglieder"]]
            == [MI[ANNA], MI[BERT], MI[CLARA]])
    # Zweimal gefragt: dieselbe Reihenfolge (stabil).
    assert (_kopf_aus_liste(BERT, kopf["name"])["mitglieder"]
            == _kopf_aus_liste(BERT, kopf["name"])["mitglieder"])


# ── 4) Sichtbarkeit: Ausgetretene, Gesperrte ───────────────────────────────


def test_mitglieder_ohne_ausgetretene(welt, patched_db):
    kopf = _drei()
    _verlassen(kopf["name"], CLARA)
    for konto in (ANNA, BERT):
        eintrag = _kopf_aus_liste(konto, kopf["name"])
        assert [m["mitglied"] for m in eintrag["mitglieder"]] == [MI[ANNA], MI[BERT]]
        assert MI[CLARA] not in {m["mitglied"] for m in eintrag["mitglieder"]}
        assert eintrag["teilnehmer"] == 2
    # Die Teilnahmezeile bleibt stehen (keine Löschung) — nur nicht mehr aktiv.
    s = patched_db()
    assert s.get(ChatTeilnehmer, (kopf["name"], CLARA)).verlassen_am is not None


def test_mitglieder_zeigen_gesperrte_aktive_trotzdem(welt):
    """Die Runde entscheidet die Sperre nicht: wer aktiv ist, steht drin."""
    kopf = _drei()
    _sperren(MI[BERT], ANNA)
    eintrag = _kopf_aus_liste(ANNA, kopf["name"])
    namen = {m["mitglied"]: m["anzeigename"] for m in eintrag["mitglieder"]}
    assert MI[BERT] in namen
    # Nur der Anzeigename der betroffenen Person, keine weiteren Felder: der
    # gesperrte Eintrag ist formgleich mit allen anderen.
    assert namen[MI[BERT]] == "Bert Brandner"
    assert all(set(m) == {"mitglied", "anzeigename"} for m in eintrag["mitglieder"])
    # Auch aus Berts Sicht bleibt die Runde vollständig (die Sperre verbietet
    # nur NEUE 1:1-Gespräche, nicht die Mitgliederliste).
    assert MI[BERT] in {m["mitglied"] for m in _kopf_aus_liste(BERT, kopf["name"])["mitglieder"]}


def test_mitglieder_ohne_sperre_wirkung_auf_vorschlagssicht(welt):
    """Sperre bleibt beim Vorschlagen wirksam — `mitglieder` hebelt sie nicht aus."""
    from diakronos_app.frappe_compat.exceptions import PermissionError as ProjectPermissionError

    kopf = _drei()
    _sperren(MI[DIETER], BERT)
    with pytest.raises(ProjectPermissionError):
        _vorschlagen(kopf["name"], MI[DIETER], BERT)


# ── Angrenzend: der Vorschlag bleibt im Verlauf auffindbar ─────────────────


def test_verlaufszeile_traegt_stand_und_eigene_auch_nach_ablehnung(welt, patched_db):
    from diakronos_app.api import chat as C

    kopf = _drei()
    v = _vorschlagen(kopf["name"], MI[DIETER], ANNA)["vorschlag"]
    _set_user(CLARA)
    C.runde_ablehnen(v["name"])
    (zeile,) = _systemzeilen(_verlauf(kopf["name"], ANNA))
    assert zeile["system"]["stand"] == "abgelehnt"
    assert zeile["system"]["vorschlag"] == v["name"]
    assert zeile["system"]["eigene"] is True
    (fremd,) = _systemzeilen(_verlauf(kopf["name"], BERT))
    assert fremd["system"]["eigene"] is False
    # Die Datenbank bleibt ohne Namen-Kopie: kein Text, kein Autor.
    s = patched_db()
    db_zeile = s.get(ChatNachricht, zeile["name"])
    assert db_zeile.text == "" and db_zeile.autor is None
