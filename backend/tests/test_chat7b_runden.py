"""CHAT-7b: Runden (3–8) und Blockieren (Backend) — Konzept S3, 2.4, 4.2/4.3.

Geprüft wird gegen die ECHTEN Endpunkte (``api/chat.py``), den ECHTEN
Rechte-Kern (``rechte/kern.py``) und die ECHTE Datenbank — keine Attrappe:

  * Anlegen: Größe 3–8, alle erreichbar, eine Sperre verhindert es,
    Dritte/Admin/HV lesen die Runde nicht
  * Vorschlag → Zustimmung ALLER → Teilnahme; eine Ablehnung beendet ihn;
    ein Vorschlag durch Nicht-Teilnehmende ist 403
  * Verlassen: danach kein Lesen mehr — die anderen sehen KEINE „Gelöschte
    Person“, sondern weiter den Namen
  * Sperre: beide Richtungen kein neues 1:1 und kein Senden im bestehenden
    1:1; die Antwort der gesperrten Seite ist identisch mit „nicht
    erreichbar“; Entsperren hebt auf; ``meine_sperren`` nur eigene
  * DSGVO: Sperren und Vorschläge fallen mit dem Konto
  * Migration: EIN Kopf, dieser Schritt hängt dahinter, up/down/up
  * SEC-11: alle schreibenden Endpunkte sind POST mit Verbnamen

Aufruf (Karte):
    docker run --rm --network none --entrypoint python -v <wt>:/repo:ro \\
      -w /repo/backend -e PYTHONPATH=/repo/backend/src:/repo/backend/tests:/repo/tools \\
      -e PYTHONDONTWRITEBYTECODE=1 <vorbau> -m pytest -q -p no:cacheprovider \\
      tests/test_chat7b_runden.py
"""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory

from diakronos_app.frappe_compat.exceptions import PermissionError  # noqa: A004 — Projektklasse (403)
from diakronos_app.models.chat import (
    ART_DIREKT,
    ART_RUNDE,
    ChatGespraech,
    ChatNachricht,
    ChatRundeVorschlag,
    ChatTeilnehmer,
    VORSCHLAG_ABGELEHNT,
    VORSCHLAG_ANGENOMMEN,
    VORSCHLAG_BEENDET,
    VORSCHLAG_OFFEN,
)
from diakronos_app.models.core import HasRole, User
from diakronos_app.models.diakonos import Mitglied
from diakronos_app.models.rechte import RechteKontaktsperre

#: Die Test-Naht liegt im MODUL ``frappe_compat.session`` (wie ``test_chat2_api``).
_session_mod = importlib.import_module("diakronos_app.frappe_compat.session")

BACKEND = Path(__file__).resolve().parents[1]

ANNA = "anna@x.org"          # legt an
BERT = "bert@x.org"
CLARA = "clara@x.org"
DIETER = "dieter@x.org"
EMMA = "emma@x.org"
FRIDA = "frida@x.org"
GUSTAV = "gustav@x.org"
HUGO = "hugo@x.org"
IDA = "ida@x.org"
JONAS = "jonas@x.org"
HV = "hv@x.org"              # Gruppenleitung: darf NICHT mitlesen
ADMIN = "admin@x.org"        # Administrator = Meldestelle (F7)

ALLE = [ANNA, BERT, CLARA, DIETER, EMMA, FRIDA, GUSTAV, HUGO, IDA, JONAS]


def _set_user(konto: str) -> None:
    _session_mod.set_user(konto)


@pytest.fixture()
def welt(patched_db):
    """Zehn Gemeindemitglieder mit Konto plus Administrator und HV."""
    s = patched_db()
    s.add(User(name="Administrator", email="admin@example.invalid", enabled=1,
               full_name="Administrator"))
    for konto in ALLE + [HV, ADMIN]:
        s.add(User(name=konto, email=konto, enabled=1,
                   full_name=konto.split("@")[0].capitalize() + " Test"))
    namen = {ANNA: ("Anna", "Beispiel"), BERT: ("Bert", "Brandner"),
             CLARA: ("Clara", "Clausen"), DIETER: ("Dieter", "Dorn"),
             EMMA: ("Emma", "Eberle"), FRIDA: ("Frida", "Fink"),
             GUSTAV: ("Gustav", "Graf"), HUGO: ("Hugo", "Haas"),
             IDA: ("Ida", "Ilg"), JONAS: ("Jonas", "Jans"),
             HV: ("Hanna", "Hofmann")}
    for i, (konto, (vor, nach)) in enumerate(namen.items()):
        s.add(Mitglied(name=f"M-{i:02d}-{vor}", vorname=vor, nachname=nach,
                       email=konto, user=konto, status="Aktiv"))
    s.add(HasRole(name="hr-admin", parent=ADMIN, parenttype="User",
                  role="System Manager"))
    s.commit()
    yield s
    s.close()


MI = {  # Mitglied-Kennung je Konto
    ANNA: "M-00-Anna", BERT: "M-01-Bert", CLARA: "M-02-Clara",
    DIETER: "M-03-Dieter", EMMA: "M-04-Emma", FRIDA: "M-05-Frida",
    GUSTAV: "M-06-Gustav", HUGO: "M-07-Hugo", IDA: "M-08-Ida",
    JONAS: "M-09-Jonas", HV: "M-10-Hanna",
}


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


def _ablehnen(vorschlag: str, konto: str) -> dict:
    from diakronos_app.api import chat as C

    _set_user(konto)
    return C.runde_ablehnen(vorschlag)


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


def _sperren(mitglied: str, konto: str) -> dict:
    from diakronos_app.api import chat as C

    _set_user(konto)
    return C.kontakt_sperren(mitglied)


def _entsperren(mitglied: str, konto: str) -> dict:
    from diakronos_app.api import chat as C

    _set_user(konto)
    return C.kontakt_entsperren(mitglied)


def _gesperrte(konto: str) -> dict:
    from diakronos_app.api import chat as C

    _set_user(konto)
    return C.meine_sperren()


def _direkt_oeffnen(mitglied: str, konto: str) -> dict:
    from diakronos_app.api import chat as C

    _set_user(konto)
    return C.direkt_oeffnen(mitglied)


def _drei(patched_db) -> dict:
    """Die Standard-Runde Anna/Bert/Clara."""
    return _anlegen("Kigo-Vorbereitung", [MI[BERT], MI[CLARA]])


# ── 1) Anlegen: Größe, Erreichbarkeit, Sperre ───────────────────────────────


def test_anlegen_legt_eine_runde_mit_drei_beteiligten_an(welt):
    kopf = _drei(welt)
    assert kopf["art"] == ART_RUNDE
    assert kopf["titel"] == "Kigo-Vorbereitung"
    assert kopf["teilnehmer"] == 3
    # CHAT-7b-3: `mitglieder` sind Objekte [{mitglied, anzeigename}] der AKTIVEN
    # Beteiligten (dieselbe Form wie in `meine_gespraeche`).
    assert [m["mitglied"] for m in kopf["mitglieder"]] == [MI[ANNA], MI[BERT], MI[CLARA]]
    assert {m["mitglied"]: m["anzeigename"] for m in kopf["mitglieder"]}[MI[BERT]] == "Bert Brandner"
    assert kopf["ungelesen"] == 0

    # Alle drei sehen die Runde in ihrer Liste — mit Titel und Teilnehmerzahl.
    for konto in (ANNA, BERT, CLARA):
        eintrag = {e["name"]: e for e in _meine(konto)["gespraeche"]}[kopf["name"]]
        assert eintrag["art"] == ART_RUNDE
        assert eintrag["titel"] == "Kigo-Vorbereitung"
        assert eintrag["teilnehmer"] == 3
        assert eintrag["gruppe"] is None and eintrag["untergruppe"] is None


def test_anlegen_mit_zu_wenigen_oder_zu_vielen_ist_403(welt):
    from diakronos_app.api import chat as C

    # Zu klein: nur eine weitere Person (2 Beteiligte) — der Kern sagt nein.
    with pytest.raises(PermissionError):
        _anlegen("Zu klein", [MI[BERT]])
    # Zu gross: 8 weitere (9 Beteiligte).
    with pytest.raises(PermissionError):
        _anlegen("Zu gross", [MI[k] for k in
                              (BERT, CLARA, DIETER, EMMA, FRIDA, GUSTAV, HUGO, IDA)])
    # Doppelt zaehlt nicht als zwei.
    with pytest.raises(PermissionError):
        _anlegen("Doppelt", [MI[BERT], MI[BERT]])
    # Acht Beteiligte sind erlaubt (7 andere).
    kopf = _anlegen("Genau acht", [MI[k] for k in
                                   (BERT, CLARA, DIETER, EMMA, FRIDA, GUSTAV, HUGO)])
    assert kopf["teilnehmer"] == 8
    assert C.ART_RUNDE == ART_RUNDE


def test_anlegen_braucht_ein_erreichbares_ziel(welt, patched_db):
    """Ohne Konto ist niemand erreichbar → dieselbe 403 ohne Inhalt."""
    s = patched_db()
    s.add(Mitglied(name="M-ohne", vorname="Olaf", nachname="Ohnberg",
                   email="ohne@x.org", user=None, status="Aktiv"))
    s.commit()
    with pytest.raises(PermissionError):
        _anlegen("Mit Konto-losem", [MI[BERT], "M-ohne"])
    # Unbekannte Kennung ebenso.
    with pytest.raises(PermissionError):
        _anlegen("Mit Unbekanntem", [MI[BERT], "M-gibt-es-nicht"])


def test_anlegen_traegt_die_art_runde_ohne_gruppe_und_ohne_paarschluessel(welt, patched_db):
    kopf = _drei(welt)
    s = patched_db()
    g = s.get(ChatGespraech, kopf["name"])
    assert g.art == ART_RUNDE
    assert g.gruppe is None and g.untergruppe is None
    assert g.paar_schluessel is None
    assert g.titel == "Kigo-Vorbereitung"


# ── 2) Lesen: nur Teilnehmende ──────────────────────────────────────────────


def test_dritte_admin_und_hv_lesen_die_runde_nicht(welt):
    kopf = _drei(welt)
    _senden(kopf["name"], "Hallo Runde", ANNA)
    for fremd in (DIETER, HV, ADMIN):
        with pytest.raises(PermissionError):
            _verlauf(kopf["name"], fremd)
        with pytest.raises(PermissionError):
            _senden(kopf["name"], "Ich auch", fremd)
        # Und die Runde steht nicht in ihrer Liste.
        namen = [e["name"] for e in _meine(fremd)["gespraeche"]]
        assert kopf["name"] not in namen


def test_verlauf_und_ungelesen_zaehler_arbeiten_wie_im_1zu1(welt):
    kopf = _drei(welt)
    _senden(kopf["name"], "Erste Nachricht", ANNA)
    verlauf = _verlauf(kopf["name"], BERT)
    assert [n["text"] for n in verlauf["nachrichten"]] == ["Erste Nachricht"]
    assert verlauf["nachrichten"][0]["autor"] == "Anna Beispiel"
    bert = {e["name"]: e for e in _meine(BERT)["gespraeche"]}[kopf["name"]]
    assert bert["ungelesen"] == 1
    # Der Zaehler der Schreibenden bleibt 0 (eigene Nachricht zaehlt nicht).
    anna = {e["name"]: e for e in _meine(ANNA)["gespraeche"]}[kopf["name"]]
    assert anna["ungelesen"] == 0


# ── 3) Vorschlag → Zustimmung → Teilnahme ───────────────────────────────────


def test_vorschlag_erscheint_als_systemnachricht_ohne_weitere_daten(welt):
    kopf = _drei(welt)
    antwort = _vorschlagen(kopf["name"], MI[DIETER], ANNA)
    v = antwort["vorschlag"]
    assert v["stand"] == VORSCHLAG_OFFEN
    assert v["mitglied"] == MI[DIETER]
    assert v["zustimmungen"] == 0
    # Benoetigt: alle bisherigen ausser der vorschlagenden Person = Bert+Clara.
    assert v["benoetigt"] == 2
    # Die Systemzeile nennt Vornamen und Zielperson — sonst nichts. Sie ist
    # ein SYSTEMHINWEIS (SOLL 8): eigener Art, kein Besitz, kein Text im
    # Datensatz (der Satz entsteht beim Lesen aus der Vorschlagszeile).
    assert antwort["nachricht"]["text"] == "Anna möchte Dieter Dorn hinzufügen."
    # CHAT-7b-3: `system` trägt zusätzlich die Kennung (für runde_zustimmen/
    # runde_ablehnen) und `eigene` aus Sicht der LESENDEN Person — hier Anna,
    # die den Vorschlag gemacht hat.
    assert antwort["nachricht"]["system"] == {"art": "runde_vorschlag",
                                              "stand": VORSCHLAG_OFFEN,
                                              "vorschlag": v["name"],
                                              "eigene": True}
    assert antwort["nachricht"]["eigene"] is False
    assert antwort["nachricht"]["autor"] is None
    s_db = welt
    zeile = s_db.get(ChatNachricht, antwort["nachricht"]["name"])
    assert zeile.vorschlag == v["name"]
    assert zeile.text == ""
    assert zeile.autor_benutzer is None and zeile.autor is None
    # Dieter ist noch NICHT dabei.
    assert {e["name"]: e for e in _meine(DIETER)["gespraeche"]}.get(kopf["name"]) is None


def test_zustimmung_aller_macht_die_person_zur_teilnehmerin(welt):
    kopf = _drei(welt)
    v = _vorschlagen(kopf["name"], MI[DIETER], ANNA)["vorschlag"]
    erst = _zustimmen(v["name"], BERT)
    assert erst["angenommen"] is False
    assert erst["vorschlag"]["zustimmungen"] == 1
    assert erst["teilnehmer"] == 3  # noch nicht dabei
    letzte = _zustimmen(v["name"], CLARA)
    assert letzte["angenommen"] is True
    assert letzte["vorschlag"]["stand"] == VORSCHLAG_ANGENOMMEN
    assert letzte["teilnehmer"] == 4
    # Dieter liest und schreibt jetzt.
    _senden(kopf["name"], "Willkommen", CLARA)
    assert _verlauf(kopf["name"], DIETER)["nachrichten"]
    _senden(kopf["name"], "Danke", DIETER)
    # Und er steht in aller Liste.
    assert kopf["name"] in [e["name"] for e in _meine(DIETER)["gespraeche"]]


def test_eine_person_kann_den_vorschlag_nicht_allein_durchbringen(welt):
    """Jede Person zaehlt GENAU einmal — sonst waere „alle“ nicht geprueft."""
    kopf = _drei(welt)
    v = _vorschlagen(kopf["name"], MI[DIETER], ANNA)["vorschlag"]
    erst = _zustimmen(v["name"], BERT)
    assert erst["angenommen"] is False and erst["vorschlag"]["zustimmungen"] == 1
    # Zweite Zustimmung derselben Person: idempotent, KEIN Fortschritt.
    zweit = _zustimmen(v["name"], BERT)
    assert zweit["angenommen"] is False
    assert zweit["vorschlag"]["zustimmungen"] == 1
    assert zweit["vorschlag"]["stand"] == VORSCHLAG_OFFEN
    # Erst die zweite Person bringt ihn durch.
    dritt = _zustimmen(v["name"], CLARA)
    assert dritt["angenommen"] is True
    assert dritt["vorschlag"]["stand"] == VORSCHLAG_ANGENOMMEN


def test_ablehnung_beendet_den_vorschlag(welt):
    kopf = _drei(welt)
    v = _vorschlagen(kopf["name"], MI[DIETER], ANNA)["vorschlag"]
    _zustimmen(v["name"], BERT)     # eine Zustimmung liegt vor
    ab = _ablehnen(v["name"], CLARA)  # EINE Gegenstimme beendet ihn
    assert ab["angenommen"] is False
    assert ab["vorschlag"]["stand"] == VORSCHLAG_ABGELEHNT
    # Weitere Zustimmungen sind nicht mehr moeglich, die Person bleibt draussen.
    with pytest.raises(Exception):
        _zustimmen(v["name"], CLARA)
    assert DIETER not in [e["name"] for e in _meine(DIETER)["gespraeche"]]
    with pytest.raises(PermissionError):
        _verlauf(kopf["name"], DIETER)


def test_vorschlag_durch_nicht_teilnehmende_ist_403(welt):
    kopf = _drei(welt)
    with pytest.raises(PermissionError):
        _vorschlagen(kopf["name"], MI[DIETER], DIETER)
    with pytest.raises(PermissionError):
        _vorschlagen(kopf["name"], MI[DIETER], HV)
    with pytest.raises(PermissionError):
        _vorschlagen(kopf["name"], MI[DIETER], ADMIN)


def test_der_vorschlagende_stimmt_nicht_mit_und_doppelte_vorschlaege_prallen(welt):
    kopf = _drei(welt)
    v = _vorschlagen(kopf["name"], MI[DIETER], ANNA)["vorschlag"]
    with pytest.raises(Exception):
        _zustimmen(v["name"], ANNA)
    with pytest.raises(Exception):
        _ablehnen(v["name"], ANNA)
    with pytest.raises(Exception):
        _vorschlagen(kopf["name"], MI[DIETER], BERT)  # schon offen


def test_bis_acht_beteiligte_und_dann_kein_weiterer_vorschlag(welt):
    achte = _anlegen("Acht", [MI[k] for k in
                              (BERT, CLARA, DIETER, EMMA, FRIDA, GUSTAV, HUGO)])
    assert achte["teilnehmer"] == 8
    with pytest.raises(PermissionError):
        _vorschlagen(achte["name"], MI[IDA], ANNA)


def test_vorschlag_einer_gesperrten_person_ist_403(welt):
    """Die Sperre wirkt beim Vorschlagen — als „nicht erreichbar“.

    R1-Review des Operators: niemand wird mit einer Person zusammengebracht,
    die ihn gesperrt hat oder die er gesperrt hat — AUCH NICHT DURCH DRITTE.
    Der Kern prüft das Ziel gegen ALLE Teilnehmenden
    (``darf_runde_erweitern``); deshalb ist auch Berts Vorschlag 403, weil
    Dieter und Anna im selben Raum sitzen.
    """
    kopf = _drei(welt)
    _sperren(MI[DIETER], ANNA)  # Anna sperrt Dieter
    # Anna kann ihn deshalb nicht selbst vorschlagen.
    with pytest.raises(PermissionError):
        _vorschlagen(kopf["name"], MI[DIETER], ANNA)
    # Bert auch nicht: Anna (gesperrt mit Dieter) ist in der Runde — „auch
    # nicht durch Dritte“. Nach aussen „nicht erreichbar“, kein Unterschied.
    with pytest.raises(PermissionError):
        _vorschlagen(kopf["name"], MI[DIETER], BERT)
    # Der Kern prüft das Ziel gegen ALLE Teilnehmenden — deshalb genügt EIN
    # gesperrtes Paar in der Runde, um jeden Vorschlag dieser Person zu
    # verhindern (auch wenn die Sperre nicht die eigene ist, hier oben: Anna).
    # Ausserhalb dieser Runde bleibt alles offen: hier zeigt es die
    # Gegenprobe — OHNE Sperre ist derselbe Vorschlag ein regulärer Vorschlag.
    _entsperren(MI[DIETER], ANNA)
    assert (_vorschlagen(kopf["name"], MI[DIETER], BERT)["vorschlag"]["stand"]
            == VORSCHLAG_OFFEN)
    _sperren(MI[DIETER], ANNA)  # Sperre wieder setzen
    # Und in der Gegenrichtung: Dieter sperrt Anna.
    _entsperren(MI[DIETER], ANNA)
    _sperren(MI[ANNA], DIETER)
    with pytest.raises(PermissionError):
        _vorschlagen(kopf["name"], MI[DIETER], ANNA)


# ── 4) Verlassen ────────────────────────────────────────────────────────────


def test_verlassen_beendet_die_teilnahme_ohne_geloeschte_person(welt, patched_db):
    kopf = _drei(welt)
    _senden(kopf["name"], "Bevor ich gehe", BERT)
    antwort = _verlassen(kopf["name"], BERT)
    assert antwort["verlassen"] is True
    assert antwort["teilnehmer"] == 2

    # Kein Lesen, kein Senden mehr fuer Bert.
    with pytest.raises(PermissionError):
        _verlauf(kopf["name"], BERT)
    with pytest.raises(PermissionError):
        _senden(kopf["name"], "Noch da?", BERT)
    # Aus seiner Liste verschwunden.
    assert kopf["name"] not in [e["name"] for e in _meine(BERT)["gespraeche"]]

    # Die anderen sehen weiter SEINEN Namen, keine „Gelöschte Person“.
    verlauf = _verlauf(kopf["name"], ANNA)
    assert verlauf["nachrichten"][0]["autor"] == "Bert Brandner"
    assert "Gelöschte Person" not in str(verlauf)
    anna = {e["name"]: e for e in _meine(ANNA)["gespraeche"]}[kopf["name"]]
    assert anna["teilnehmer"] == 2

    # Die Teilnahmezeile steht noch — mit `verlassen_am`, nicht geloescht.
    s = patched_db()
    zeile = s.get(ChatTeilnehmer, (kopf["name"], BERT))
    assert zeile is not None and zeile.verlassen_am is not None


def test_verlassen_und_wieder_aufnehmen_ueber_einen_neuen_vorschlag(welt, patched_db):
    kopf = _drei(welt)
    _verlassen(kopf["name"], BERT)
    v = _vorschlagen(kopf["name"], MI[BERT], ANNA)["vorschlag"]
    # Nach Berts Austritt sind nur Anna und Clara dabei; noetig ist damit EINE
    # Zustimmung (alle ausser der vorschlagenden Anna).
    erg = _zustimmen(v["name"], CLARA)
    assert erg["angenommen"] is True
    assert erg["vorschlag"]["stand"] == VORSCHLAG_ANGENOMMEN
    assert erg["teilnehmer"] == 3
    # Bert sieht den Verlauf ab seinem NEUEN Eintritt (SOLL 7) — und der
    # liegt NACH der Vorschlags-Systemzeile. Von vorher sieht er nichts.
    texte = [n["text"] for n in _verlauf(kopf["name"], BERT)["nachrichten"]]
    assert texte == []
    # Anna (durchgehend dabei) sieht die Systemzeile weiterhin.
    anna_texte = [n["text"] for n in _verlauf(kopf["name"], ANNA)["nachrichten"]]
    assert anna_texte == ["Anna möchte Bert Brandner hinzufügen."]
    # Genau EINE Teilnahmezeile (wiederbelebt, nicht doppelt).
    s = patched_db()
    zeilen = [z for z in s.query(ChatTeilnehmer).all()
              if z.gespraech == kopf["name"] and z.benutzer == BERT]
    assert len(zeilen) == 1 and zeilen[0].verlassen_am is None


# ── 5) Blockieren ───────────────────────────────────────────────────────────


def test_sperre_verhindert_neues_1zu1_in_beide_richtungen(welt):
    _sperren(MI[BERT], ANNA)  # Anna sperrt Bert
    with pytest.raises(PermissionError):
        _direkt_oeffnen(MI[BERT], ANNA)
    # Und in der Gegenrichtung — Bert erfaehrt NICHTS vom Grund.
    with pytest.raises(PermissionError):
        _direkt_oeffnen(MI[ANNA], BERT)


def test_sperre_verhindert_senden_im_bestehenden_1zu1(welt):
    gespraech = _direkt_oeffnen(MI[BERT], ANNA)["name"]
    _senden(gespraech, "Hallo Bert", ANNA)
    _sperren(MI[BERT], ANNA)
    with pytest.raises(PermissionError):
        _senden(gespraech, "Noch was", ANNA)
    with pytest.raises(PermissionError):
        _senden(gespraech, "Antwort", BERT)
    # Der Verlauf bleibt lesbar (nur das Schreiben ist zu).
    assert len(_verlauf(gespraech, ANNA)["nachrichten"]) == 1


def test_antwort_der_gesperrten_seite_ist_identisch_mit_nicht_erreichbar(welt, patched_db):
    """Gleicher Fehlertext, gleicher Status — kein Unterschied erkennbar."""
    from diakronos_app.api import chat as C

    _sperren(MI[BERT], ANNA)
    # Gesperrt (Anna -> Bert).
    _set_user(ANNA)
    gesperrt = None
    try:
        C.direkt_oeffnen(MI[BERT])
    except PermissionError as fehler:
        gesperrt = (type(fehler), str(fehler), fehler.args)
    # Nicht erreichbar aus einem ANDEREN Grund: Ida hat kein Konto in der
    # Runde — hier ein Mitglied ohne Konto.
    s = patched_db()
    s.add(Mitglied(name="M-ohne", vorname="Olaf", nachname="Ohnberg",
                   email="ohne@x.de", user=None, status="Aktiv"))
    s.commit()
    _set_user(CLARA)
    unerreichbar = None
    try:
        C.direkt_oeffnen("M-ohne")
    except PermissionError as fehler:
        unerreichbar = (type(fehler), str(fehler), fehler.args)
    assert gesperrt is not None and unerreichbar is not None
    assert gesperrt[0] is unerreichbar[0]
    assert gesperrt[1] == unerreichbar[1] == ""
    assert gesperrt[2] == unerreichbar[2]


def test_personensuche_zeigt_bei_sperre_nur_darf_schreiben_false(welt):
    from diakronos_app.api import chat as C

    _sperren(MI[BERT], ANNA)
    _set_user(ANNA)
    treffer = {t["mitglied"]: t for t in C.personen_suchen("Bert")["treffer"]}
    assert MI[BERT] in treffer
    assert treffer[MI[BERT]]["darf_schreiben"] is False
    # Vor der Sperre war es true.
    _entsperren(MI[BERT], ANNA)
    treffer = {t["mitglied"]: t for t in C.personen_suchen("Bert")["treffer"]}
    assert treffer[MI[BERT]]["darf_schreiben"] is True


def test_personensuche_verraet_die_sperre_nicht(welt):
    """Review R1 (SOLL 6): ein gesperrtes Paar sieht aus wie „hat kein Konto“.

    ``hat_konto`` UND ``darf_schreiben`` sind beide false — genau die Form
    einer Person ohne aktives Konto. Vor der Sperre ist ``hat_konto`` true.
    """
    from diakronos_app.api import chat as C

    _set_user(ANNA)
    vorher = {t["mitglied"]: t for t in C.personen_suchen("Bert")["treffer"]}[MI[BERT]]
    assert vorher["hat_konto"] is True
    _sperren(MI[BERT], ANNA)  # Anna sperrt Bert
    _set_user(ANNA)
    gesperrt = {t["mitglied"]: t for t in C.personen_suchen("Bert")["treffer"]}[MI[BERT]]
    # Vorher OFFENBARKEIT: die Person ist noch da (keine Auskunft), aber
    # „hat_konto“ und „darf_schreiben“ sind beide false.
    assert gesperrt["hat_konto"] is False
    assert gesperrt["darf_schreiben"] is False
    assert gesperrt["mitglied"] == MI[BERT]
    # Die GESPERRTE Seite sieht es genauso (beide Richtungen).
    _set_user(BERT)
    andere = {t["mitglied"]: t for t in C.personen_suchen("Anna")["treffer"]}[MI[ANNA]]
    assert andere["hat_konto"] is False and andere["darf_schreiben"] is False
    # Aus einem DRITTEN Blickwinkel ist Bert unverändert: hat Konto, schreibbar.
    _set_user(CLARA)
    dritte = {t["mitglied"]: t for t in C.personen_suchen("Bert")["treffer"]}[MI[BERT]]
    assert dritte["hat_konto"] is True and dritte["darf_schreiben"] is True


def test_suche_der_eigenen_person_bleibt_unveraendert(welt):
    """Die eigene Person: auffindbar MIT Konto — nur nicht beschreibbar.

    Der Grund des Kerns ist dort ``selbst``, NICHT ``gesperrt`` — die Suche
    darf daraus keine „Sperre“ machen (Regression aus dem R1-Review).
    """
    from diakronos_app.api import chat as C

    _set_user(ANNA)
    treffer = {t["mitglied"]: t for t in C.personen_suchen("Anna")["treffer"]}
    assert treffer[MI[ANNA]]["hat_konto"] is True
    assert treffer[MI[ANNA]]["darf_schreiben"] is False


def test_entsperren_hebt_auf(welt):
    _sperren(MI[BERT], ANNA)
    with pytest.raises(PermissionError):
        _direkt_oeffnen(MI[BERT], ANNA)
    antwort = _entsperren(MI[BERT], ANNA)
    assert antwort == {"mitglied": MI[BERT], "gesperrt": False}
    assert _direkt_oeffnen(MI[BERT], ANNA)["name"]
    assert _direkt_oeffnen(MI[ANNA], BERT)["name"]


def test_entsperren_loescht_nur_die_eigene_richtung(welt, patched_db):
    _sperren(MI[BERT], ANNA)   # Anna -> Bert
    _sperren(MI[ANNA], BERT)   # Bert -> Anna
    _entsperren(MI[BERT], ANNA)
    s = patched_db()
    zeilen = s.query(RechteKontaktsperre).all()
    assert len(zeilen) == 1
    assert (zeilen[0].benutzer, zeilen[0].gesperrt) == (BERT, ANNA)
    # Die Sperre des anderen wirkt weiter.
    with pytest.raises(PermissionError):
        _direkt_oeffnen(MI[ANNA], BERT)


def test_sperren_sich_selbst_ist_nicht_moeglich(welt):
    with pytest.raises(PermissionError):
        _sperren(MI[ANNA], ANNA)


def test_meine_sperren_zeigt_nur_eigene_ohne_konto_feld(welt):
    _sperren(MI[BERT], ANNA)    # Anna sperrt Bert
    _sperren(MI[BERT], CLARA)   # Clara sperrt Bert
    eigene = _gesperrte(ANNA)["sperren"]
    assert [e["mitglied"] for e in eigene] == [MI[BERT]]
    assert eigene[0]["anzeigename"]
    fremde = _gesperrte(CLARA)["sperren"]
    assert [e["mitglied"] for e in fremde] == [MI[BERT]]
    assert _gesperrte(DIETER)["sperren"] == []


def test_sperren_ist_idempotent(welt, patched_db):
    _sperren(MI[BERT], ANNA)
    _sperren(MI[BERT], ANNA)
    s = patched_db()
    assert s.query(RechteKontaktsperre).count() == 1


# ── 6) DSGVO ────────────────────────────────────────────────────────────────


def test_anonymisierung_entfernt_sperren_beider_richtungen(welt, patched_db):
    from diakronos_app import dsgvo_anonymisierung as D

    _sperren(MI[BERT], ANNA)   # Anna -> Bert
    _sperren(MI[ANNA], BERT)   # Bert -> Anna
    _sperren(MI[BERT], CLARA)  # Clara -> Bert (bleibt: Clara ist nicht betroffen)
    s = patched_db()
    D.anonymisiere(s, MI[BERT], [BERT])
    s.commit()
    s = patched_db()
    # Die Sperren des gelöschten Kontos fallen in BEIDE Richtungen — auch die,
    # in der die Person GESPERRT war (eine Sperre gegen ein Konto, das es nicht
    # mehr gibt, waere wirkungslos und bliebe als Zeile stehen).
    assert s.query(RechteKontaktsperre).all() == []


def test_anonymisierung_nullen_des_vorschlagenden(welt, patched_db):
    """Review R1 (MUSS 4): `vorgeschlagen_von` wird GENULLT, nicht gelöscht.

    Die Zeile bleibt: die anderen sehen ihre Systemzeile im Verlauf weiter
    (SOLL 8). Nur das Konto der gelöschten Person verschwindet.
    """
    from diakronos_app import dsgvo_anonymisierung as D

    kopf = _drei(welt)
    v = _vorschlagen(kopf["name"], MI[DIETER], ANNA)["vorschlag"]
    s = patched_db()
    assert s.query(ChatRundeVorschlag).count() == 1
    D.anonymisiere(s, MI[ANNA], [ANNA])
    s.commit()
    s = patched_db()
    zeilen = s.query(ChatRundeVorschlag).all()
    assert len(zeilen) == 1
    assert zeilen[0].name == v["name"]
    assert zeilen[0].vorgeschlagen_von is None
    assert zeilen[0].entschieden_von is None
    # Der Vorgang bleibt lesbar — und nennt niemanden mehr beim Namen.
    texte = [n["text"] for n in _verlauf(kopf["name"], BERT)["nachrichten"]]
    assert all("Anna" not in (t or "") for t in texte)


def test_anonymisierung_entfernt_zustimmende_und_haengt_die_vorgeschlagene_um(
        welt, patched_db):
    """Review R1 (MUSS 4): Zustimmenden-Liste bereinigt, `mitglied` umgehängt.

    Art.-17-Löschung läuft durch — und es bleibt KEIN Konto in `zustimmende`.
    """
    from diakronos_app import dsgvo_anonymisierung as D

    kopf = _drei(welt)
    v = _vorschlagen(kopf["name"], MI[DIETER], ANNA)["vorschlag"]
    _zustimmen(v["name"], BERT)  # Bert steht damit in `zustimmende`
    s = patched_db()
    zeile = s.get(ChatRundeVorschlag, v["name"])
    assert BERT in zeile.zustimmungen
    D.anonymisiere(s, MI[BERT], [BERT])
    s.commit()
    s = patched_db()
    zeile = s.get(ChatRundeVorschlag, v["name"])
    assert zeile is not None                      # Vorgang bleibt
    assert BERT not in zeile.zustimmungen         # Konto ist weg
    assert zeile.zustimmende in ("", None)
    # Der Vorschlag selbst steht noch auf `offen` — jetzt fehlt eine Stimme.
    assert zeile.stand == VORSCHLAG_OFFEN


def test_anonymisierung_der_vorgeschlagenen_person_haengt_den_verweis_um(
        welt, patched_db):
    """`mitglied` ist eine Mitglied-Kennung ohne FK: sie wird umgehängt."""
    from diakronos_app import dsgvo_anonymisierung as D

    kopf = _drei(welt)
    v = _vorschlagen(kopf["name"], MI[DIETER], ANNA)["vorschlag"]
    s = patched_db()
    D.anonymisiere(s, MI[DIETER], [DIETER])
    s.commit()
    s = patched_db()
    zeile = s.get(ChatRundeVorschlag, v["name"])
    assert zeile is not None
    assert zeile.mitglied != MI[DIETER]
    assert str(zeile.mitglied).startswith("geloescht-")


def test_anonymisierung_schliesst_die_runde_nicht(welt, patched_db):
    """Der Verlauf der Runde bleibt lesbar, der Name wird zur neutralen Kennung."""
    from diakronos_app import dsgvo_anonymisierung as D

    kopf = _drei(welt)
    _senden(kopf["name"], "Von Bert", BERT)
    s = patched_db()
    D.anonymisiere(s, MI[BERT], [BERT])
    s.commit()
    verlauf = _verlauf(kopf["name"], ANNA)
    assert [n["text"] for n in verlauf["nachrichten"]] == ["Von Bert"]
    assert "Bert" not in str(verlauf["nachrichten"][0]["autor"] or "")
    anna = {e["name"]: e for e in _meine(ANNA)["gespraeche"]}[kopf["name"]]
    assert anna["teilnehmer"] == 2


# ── 7) Aufbewahrung (CHAT-8) ────────────────────────────────────────────────


def test_aufbewahrung_loescht_runde_mit_ihren_vorschlaegen(welt, patched_db):
    from diakronos_app import chat_aufbewahrung as A

    kopf = _drei(welt)
    vorschlag = _vorschlagen(kopf["name"], MI[DIETER], ANNA)["vorschlag"]
    assert vorschlag["stand"] == VORSCHLAG_OFFEN
    s = patched_db()
    assert s.query(ChatRundeVorschlag).count() == 1
    # Runden laufen unter `chat_frist_direkt_monate` (Standard 12 Monate): der
    # Test altert Anlage UND Nachrichten zwei Jahre — die Frist misst ab der
    # letzten Nachricht (der Systemnachricht des Vorschlags).
    import datetime as dt
    alt = A.monate_zurueck(dt.datetime(2026, 11, 19), 24)
    s.get(ChatGespraech, kopf["name"]).angelegt_am = alt
    for zeile in s.query(ChatNachricht).filter(
            ChatNachricht.gespraech == kopf["name"]).all():
        zeile.erstellt_am = alt
    s.commit()
    ergebnis = A.aufraeumen(dt.datetime(2026, 11, 19))
    assert ergebnis["gespraeche"] >= 1
    s = patched_db()
    assert s.get(ChatGespraech, kopf["name"]) is None
    assert s.query(ChatRundeVorschlag).count() == 0


# ── 8) Migration ────────────────────────────────────────────────────────────


def _skripte() -> ScriptDirectory:
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "alembic"))
    return ScriptDirectory.from_config(cfg)


def test_genau_ein_kopf_und_unser_schritt_haengt_dahinter():
    skripte = _skripte()
    assert len(skripte.get_bases()) == 1
    assert len(skripte.get_heads()) == 1, skripte.get_heads()
    rev = skripte.get_revision("chat7b_runden")
    assert rev is not None
    # Der Kopfname wird NICHT festgeschrieben: jede weitere Fachmigration haengt
    # sich hinten an. Geprueft wird die KANTE (der Vorgaenger ist der Kopf, der
    # beim Bauen galt) und dass es genau einen Kopf gibt.
    assert rev.down_revision == "chat4b_umfrage_erinnerung", rev.down_revision
    assert "Revises: chat4b_umfrage_erinnerung" in Path(rev.path).read_text(encoding="utf-8")


def test_migration_upgrade_downgrade_upgrade():
    """up/down/up gegen eine frische Datenbank — ueber das Skript selbst."""
    import importlib.util

    from sqlalchemy import create_engine, inspect, text as sql_text
    from sqlalchemy.pool import StaticPool

    from diakronos_app.models.base import Base

    pfad = BACKEND / "alembic" / "versions" / "chat7b_runden.py"
    spec = importlib.util.spec_from_file_location("chat7b_runden", pfad)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)

    eng = create_engine("sqlite+pysqlite:///:memory:",
                        connect_args={"check_same_thread": False},
                        poolclass=StaticPool, future=True)
    Base.metadata.create_all(eng)
    # Zuruecksetzen auf den Stand VOR chat7b: die drei Dinge wieder weg.
    with eng.begin() as v:
        v.exec_driver_sql('DROP TABLE IF EXISTS "chat_nachricht"')
        v.exec_driver_sql('DROP INDEX IF EXISTS "uq_chat_runde_vorschlag_offen"')
        v.exec_driver_sql('DROP INDEX IF EXISTS "ix_chat_runde_vorschlag_gespraech"')
        v.exec_driver_sql('DROP TABLE IF EXISTS "chat_runde_vorschlag"')
        v.exec_driver_sql('DROP INDEX IF EXISTS "uq_rechte_kontaktsperre"')
        v.exec_driver_sql('DROP INDEX IF EXISTS "ix_rechte_kontaktsperre_gesperrt"')
        v.exec_driver_sql('DROP TABLE IF EXISTS "rechte_kontaktsperre"')
        # `chat_nachricht` wurde oben ganz entfernt (SQLite kann eine Spalte
        # mit FK nicht einfach loswerden); die steht danach OHNE `vorschlag`.
        v.exec_driver_sql('ALTER TABLE "chat_teilnehmer" DROP COLUMN "verlassen_am"')
        v.exec_driver_sql('ALTER TABLE "chat_teilnehmer" DROP COLUMN "sichtbar_ab"')
        # Neu aufbauen — ohne `vorschlag` und ohne die FK darauf.
        v.exec_driver_sql(
            'CREATE TABLE "chat_nachricht" ('
            '"name" VARCHAR(140) NOT NULL PRIMARY KEY, '
            '"gespraech" VARCHAR(140) NOT NULL REFERENCES "chat_gespraech" ("name"), '
            '"autor_benutzer" VARCHAR(140) REFERENCES "user" ("name"), '
            '"autor" VARCHAR(140) REFERENCES "mitglied" ("name"), '
            '"text" TEXT NOT NULL, '
            '"antwort_auf" VARCHAR(140) REFERENCES "chat_nachricht" ("name"), '
            '"erstellt_am" DATETIME NOT NULL, "bearbeitet_am" DATETIME, '
            '"geloescht_am" DATETIME, "geloescht_von" VARCHAR(140) REFERENCES "user" ("name"), '
            '"entfernt_grund" TEXT, "umfrage" VARCHAR(140) REFERENCES "chat_umfrage" ("name"))')

    def _stand():
        insp = inspect(eng)
        sperre = insp.has_table("rechte_kontaktsperre")
        vorschlag = insp.has_table("chat_runde_vorschlag")
        spalten = {c["name"] for c in insp.get_columns("chat_teilnehmer")}
        nachricht = {c["name"] for c in insp.get_columns("chat_nachricht")}
        return (sperre, vorschlag, "verlassen_am" in spalten,
                "sichtbar_ab" in spalten, "vorschlag" in nachricht)

    def _laufen(funktion):
        from alembic.migration import MigrationContext
        from alembic.operations import Operations

        with eng.begin() as verbindung:
            with Operations.context(MigrationContext.configure(verbindung)):
                funktion()

    assert _stand() == (False, False, False, False, False)
    _laufen(modul.upgrade)
    sperre, vorschlag, verlassen, sichtbar, nachricht_vorschlag = _stand()
    assert sperre and vorschlag and verlassen and sichtbar and nachricht_vorschlag
    # Die Indizes der neuen Tabellen liegen an (Unique auf (benutzer, gesperrt)).
    insp = inspect(eng)
    namen = {i["name"] for i in insp.get_indexes("rechte_kontaktsperre")}
    assert {"uq_rechte_kontaktsperre", "ix_rechte_kontaktsperre_gesperrt"} <= namen
    namen = {i["name"] for i in insp.get_indexes("chat_runde_vorschlag")}
    assert {"uq_chat_runde_vorschlag_offen", "ix_chat_runde_vorschlag_gespraech"} <= namen
    # Zweiter Lauf ist idempotent.
    _laufen(modul.upgrade)
    assert _stand() == (True, True, True, True, True)
    # Ruecknahme stellt den alten Stand wieder her (es gibt keine Daten).
    _laufen(modul.downgrade)
    assert _stand() == (False, False, False, False, False)
    # Und wieder hoch — der Rundlauf bricht nicht.
    _laufen(modul.upgrade)
    assert _stand() == (True, True, True, True, True)
    eng.dispose()


def test_ruecknahme_ist_laut_wenn_sperren_existieren():
    """Keine stille Datenvernichtung: mit Sperren verweigert downgrade."""
    import importlib.util

    from sqlalchemy import create_engine
    from sqlalchemy.pool import StaticPool

    from diakronos_app.models.base import Base

    pfad = BACKEND / "alembic" / "versions" / "chat7b_runden.py"
    spec = importlib.util.spec_from_file_location("chat7b_runden_b", pfad)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)

    eng = create_engine("sqlite+pysqlite:///:memory:",
                        connect_args={"check_same_thread": False},
                        poolclass=StaticPool, future=True)
    Base.metadata.create_all(eng)
    with eng.begin() as v:
        v.exec_driver_sql("INSERT INTO rechte_kontaktsperre (benutzer, gesperrt) "
                          "VALUES ('a@x.org', 'b@x.org')")

    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    with eng.begin() as verbindung:
        with Operations.context(MigrationContext.configure(verbindung)):
            with pytest.raises(RuntimeError):
                modul.downgrade()
    eng.dispose()


# ── 9) SEC-11: POST mit Verbnamen ───────────────────────────────────────────


def test_schreibende_endpunkte_sind_post_mit_verbnamen():
    from diakronos_app.api import chat as C
    from diakronos_app.frappe_compat.registry import methoden_fuer

    for name in ("runde_anlegen", "runde_vorschlagen", "runde_zustimmen",
                 "runde_ablehnen", "runde_verlassen", "kontakt_sperren",
                 "kontakt_entsperren"):
        assert methoden_fuer(getattr(C, name)) == ("POST",), name
    # Lesend (nur eigene Sperren): ausdruecklich GET — der SEC-11-Waechter
    # liest „sperren“ als schreibend, die Menge sagt „nur lesen“.
    assert methoden_fuer(C.meine_sperren) == ("GET",)


def test_endpunkte_sind_im_register_erreichbar():
    from diakronos_app.frappe_compat.registry import lookup

    for name in ("runde_anlegen", "runde_vorschlagen", "runde_zustimmen",
                 "runde_ablehnen", "runde_verlassen", "kontakt_sperren",
                 "kontakt_entsperren", "meine_sperren"):
        assert lookup(f"diakronos_app.api.chat.{name}") is not None, name


# ── 10) Review R1: Meldeweg in Runden (MUSS 1/2/10) ─────────────────────────


def _glocken_texte(s, konto: str) -> list[str]:
    """Die Glocken-Betreffe eines Kontos — in der Sitzung des Tests gelesen."""
    from diakronos_app.models.core import NotificationLog

    return [str(z.subject or "") for z in s.query(NotificationLog)
            .filter(NotificationLog.for_user == konto).all()]


def test_meldung_in_einer_runde_geht_nur_an_die_meldestelle(welt, patched_db):
    """MUSS 2: eine Meldung aus einer Runde erreicht die Meldestelle.

    Glocke nur beim Administrator (Betreff „Runde <Titel>“, kein
    Absendername), Liste für den Admin sichtbar, HV 403.
    """
    from diakronos_app.api import chat as C

    kopf = _drei(welt)
    nachricht = _senden(kopf["name"], "Unschön", BERT)
    _set_user(ANNA)
    C.meldung_senden(nachricht["name"], "beleidigung")
    s = patched_db()
    admin_glocken = _glocken_texte(s, ADMIN)
    # Der BESTEHENDE Meldeweg (``_glocke_neue_meldung``) — unverändert seit
    # CHAT-6, bewusst ohne Absender und ohne Gesprächsangabe (Konzept 2.5).
    assert admin_glocken == ["Neue Meldung im Chat"], admin_glocken
    assert _glocken_texte(s, HV) == []
    _set_user(ADMIN)
    liste = C.meldungen_liste()
    # Der Admin sieht die Meldung aus der RUNDE (Titel aus dem Gespräch).
    assert [m["nachricht"]["name"] for m in liste["meldungen"]] == [nachricht["name"]]
    assert liste["meldungen"][0]["gespraech_titel"] == "Runde Kigo-Vorbereitung"
    assert liste["offen"] == 1
    _set_user(HV)
    with pytest.raises(PermissionError):
        C.meldungen_liste()


def test_admin_ohne_meldung_in_einer_runde_bekommt_leere_liste(welt):
    """MUSS 10: kein 403 für den Admin, nur weil eine Runde existiert."""
    from diakronos_app.api import chat as C

    kopf = _drei(welt)
    _senden(kopf["name"], "Hallo", ANNA)
    _set_user(ADMIN)
    assert C.meldungen_liste() == {"meldungen": [], "offen": 0}


def test_admin_als_teilnehmer_loescht_fremde_runde_nachricht_nicht(welt, patched_db):
    """MUSS 1: MODERIEREN in der Runde gibt es NUR auf dem Meldeweg."""
    from diakronos_app.api import chat as C

    # Der Administrator hat hier einen eigenen Mitgliedsdatensatz — er ist
    # Teilnehmer wie jeder andere.
    s = patched_db()
    s.add(Mitglied(name="M-99-Admin", vorname="Ad", nachname="Min",
                   email=ADMIN, user=ADMIN, status="Aktiv"))
    s.commit()
    _set_user(ADMIN)
    kopf = C.runde_anlegen("Mit Admin", [MI[BERT], MI[CLARA]])
    zeile = _senden(kopf["name"], "Von Bert", BERT)
    _set_user(ADMIN)
    with pytest.raises(PermissionError):
        C.loeschen(zeile["name"])


# ── 11) Review R1: Zustimmung (MUSS 5) ──────────────────────────────────────


def test_zustimmender_verlaesst_vor_der_letzten_zustimmung(welt):
    """MUSS 5a: wer gegangen ist, zählt weder als Zustimmender noch als nötig.

    Vier Beteiligte (Anna, Bert, Clara, Emma): Anna schlägt Dieter vor, nötig
    sind DREI Stimmen. Bert und Emma stimmen zu, dann geht CLAUDE — der
    Vorschlag steht weiter offen, die Grenze sinkt auf ZWEI (Bert + Emma
    sind beide schon da, also ist er mit ihren Stimmen erfüllt).

    Zusätzlich (Kartenvorgabe MUSS 5e): jedes Verlassen beendet die offenen
    Vorschläge der Runde — der Kreis hat sich geändert, es wird neu
    verhandelt. Deshalb wird hier NACH dem Austritt ein NEUER Vorschlag
    gestellt, um die Zählregel zu zeigen.
    """
    vier = _anlegen("Vier", [MI[BERT], MI[CLARA], MI[EMMA]])
    assert vier["teilnehmer"] == 4
    v = _vorschlagen(vier["name"], MI[DIETER], ANNA)["vorschlag"]
    assert v["benoetigt"] == 3          # Bert, Clara, Emma
    assert _zustimmen(v["name"], BERT)["angenommen"] is False
    assert _zustimmen(v["name"], EMMA)["angenommen"] is False
    # Clara geht: der Kreis ändert sich → der offene Vorschlag endet.
    _verlassen(vier["name"], CLARA)
    from diakronos_app.models.chat import ChatRundeVorschlag as _V
    # SOLL 4 (CHAT-7b-2): mit dem Austritt ist der Vorschlag hinfällig —
    # Stand `beendet`, nicht `abgelehnt` (niemand hat dagegen gestimmt).
    assert welt.get(_V, v["name"]).stand == VORSCHLAG_BEENDET
    # Neuer Vorschlag: nötig sind jetzt nur noch ZWEI (Bert + Emma).
    v2 = _vorschlagen(vier["name"], MI[DIETER], ANNA)["vorschlag"]
    assert v2["benoetigt"] == 2
    assert _zustimmen(v2["name"], BERT)["angenommen"] is False
    erg = _zustimmen(v2["name"], EMMA)
    assert erg["angenommen"] is True
    assert erg["vorschlag"]["stand"] == VORSCHLAG_ANGENOMMEN
    assert erg["teilnehmer"] == 4       # Anna, Bert, Emma, Dieter


def test_vorschlagender_verlaesst_beendet_seine_offenen_vorschlaege(welt, patched_db):
    """MUSS 5e/5f: mit dem Austritt enden seine Vorschläge."""
    kopf = _drei(welt)
    v = _vorschlagen(kopf["name"], MI[DIETER], ANNA)["vorschlag"]
    _verlassen(kopf["name"], ANNA)
    s = patched_db()
    # SOLL 4: `beendet` (hinfällig), nicht `abgelehnt`.
    assert s.get(ChatRundeVorschlag, v["name"]).stand == VORSCHLAG_BEENDET


def test_bei_sieben_beteiligten_macht_der_erste_vorschlag_die_runde_voll(welt):
    """MUSS 5b: bei 7 Beteiligten ist EIN Platz frei — danach keiner mehr."""
    sieben = _anlegen("Sieben", [MI[k] for k in
                                (BERT, CLARA, DIETER, EMMA, FRIDA, GUSTAV)])
    assert sieben["teilnehmer"] == 7
    v1 = _vorschlagen(sieben["name"], MI[HUGO], ANNA)["vorschlag"]
    erg = None
    for konto in (BERT, CLARA, DIETER, EMMA, FRIDA, GUSTAV):
        erg = _zustimmen(v1["name"], konto)
    assert erg["angenommen"] is True
    assert erg["teilnehmer"] == 8
    # Kein weiterer Vorschlag mehr (8 ist die Grenze).
    with pytest.raises(PermissionError):
        _vorschlagen(sieben["name"], MI[IDA], ANNA)


# ── 12) Review R1: Sichtbarkeit neuer Teilnehmender (SOLL 7) ────────────────


def test_neue_teilnehmende_sehen_den_verlauf_erst_ab_ihrem_eintritt(welt):
    kopf = _drei(welt)
    _senden(kopf["name"], "Vor Dieters Eintritt", ANNA)
    v = _vorschlagen(kopf["name"], MI[DIETER], ANNA)["vorschlag"]
    _zustimmen(v["name"], BERT)
    _zustimmen(v["name"], CLARA)
    _senden(kopf["name"], "Nach Dieters Eintritt", ANNA)
    texte = [n["text"] for n in _verlauf(kopf["name"], DIETER)["nachrichten"]]
    assert "Vor Dieters Eintritt" not in texte
    assert "Nach Dieters Eintritt" in texte


# ── 13) Review R1: Systemhinweis ist kein normaler Beitrag (SOLL 8) ────────


def test_vorschlags_systemhinweis_ist_nicht_bearbeitbar_loeschbar_meldbar(welt, patched_db):
    from diakronos_app.api import chat as C

    kopf = _drei(welt)
    antwort = _vorschlagen(kopf["name"], MI[DIETER], ANNA)
    nachricht = antwort["nachricht"]["name"]
    _set_user(ANNA)
    with pytest.raises(Exception):
        C.aendern(nachricht, "neu")
    with pytest.raises(Exception):
        C.loeschen(nachricht)
    _set_user(BERT)
    with pytest.raises(Exception):
        C.meldung_senden(nachricht, "beleidigung")
    # Der Datenbank-Text ist LEER — keine Namen-Kopie, die eine Anonymisierung
    # stehen ließe.
    assert patched_db().get(ChatNachricht, nachricht).text == ""


# ── 14) Review R1: Umfrage-Glocke in Runden (SOLL 9) ───────────────────────


def test_umfrage_glocke_in_einer_runde_nennt_die_runde_einmal(welt, patched_db):
    from diakronos_app.api import chat as C

    kopf = _drei(welt)
    _set_user(ANNA)
    C.umfrage_anlegen(kopf["name"], "Wann treffen wir uns?", ["Sa", "So"])
    glocken = _glocken_texte(patched_db(), BERT)
    assert any(t == "Neue Umfrage in der Runde Kigo-Vorbereitung" for t in glocken), glocken


# ── 15) CHAT-7b-2: Sichtbarkeit ab Eintritt lückenlos (MUSS 1) ──────────────

def _dieter_spaeter_eintreten(kopf: dict) -> None:
    """Dieter über einen Vorschlag in die Runde holen (Anna legt an)."""
    v = _vorschlagen(kopf["name"], MI[DIETER], ANNA)["vorschlag"]
    _zustimmen(v["name"], BERT)
    assert _zustimmen(v["name"], CLARA)["angenommen"] is True


def test_muss1a_letzte_nachricht_der_liste_ist_fuer_neue_leer(welt):
    """MUSS 1a: ``meine_gespraeche`` verrät den Text von VOR dem Eintritt nicht.

    Bert tritt nach einer Nachricht ein → ``letzte_nachricht`` ist ``None``
    (nicht der Text von vorher), ``ungelesen`` bleibt 0.
    """
    kopf = _drei(welt)
    _senden(kopf["name"], "Geheimnis von vorher", ANNA)
    _dieter_spaeter_eintreten(kopf)
    eintrag = {e["name"]: e for e in _meine(DIETER)["gespraeche"]}[kopf["name"]]
    assert eintrag["letzte_nachricht"] is None, eintrag["letzte_nachricht"]
    assert eintrag["letzte_am"] is None
    assert eintrag["ungelesen"] == 0
    # Nach einer Nachricht NACH dem Eintritt steht sie wieder da.
    _senden(kopf["name"], "Willkommen Dieter", ANNA)
    eintrag = {e["name"]: e for e in _meine(DIETER)["gespraeche"]}[kopf["name"]]
    assert eintrag["letzte_nachricht"] == "Willkommen Dieter"


def test_muss1a_liste_zeigt_alteren_teilnehmenden_weiter_ihren_verlauf(welt):
    """Die Grenze gilt NUR für den Neuen — Clara sieht die Vorschau wie bisher."""
    kopf = _drei(welt)
    _senden(kopf["name"], "Geheimnis von vorher", ANNA)
    _dieter_spaeter_eintreten(kopf)
    eintrag = {e["name"]: e for e in _meine(CLARA)["gespraeche"]}[kopf["name"]]
    assert eintrag["letzte_nachricht"] is not None
    # Auch der Vorschlagende selbst sieht SEINE eigene Systemzeile nicht als
    # letzten Beitrag (SOLL 5) — der Text von vorher bleibt aber sichtbar.
    eintrag_anna = {e["name"]: e for e in _meine(ANNA)["gespraeche"]}[kopf["name"]]
    assert eintrag_anna["letzte_nachricht"] == "Geheimnis von vorher"


def test_muss1b_umfrage_von_vor_dem_eintritt_ist_404(welt):
    """MUSS 1b: Ergebnis und Abstimmen einer Umfrage von VOR dem Eintritt = 404."""
    from diakronos_app.api import chat as C
    from diakronos_app.frappe_compat.exceptions import DoesNotExistError

    kopf = _drei(welt)
    _set_user(ANNA)
    u = C.umfrage_anlegen(kopf["name"], "Wann treffen wir uns?", ["Sa", "So"])["umfrage"]
    _dieter_spaeter_eintreten(kopf)
    _set_user(DIETER)
    with pytest.raises(DoesNotExistError):
        C.umfrage_ergebnis(u["name"])
    with pytest.raises(DoesNotExistError):
        C.umfrage_abstimmen(u["name"], optionen=1)
    # Die anderen sehen und nutzen sie unverändert.
    _set_user(BERT)
    assert C.umfrage_ergebnis(u["name"])["name"] == u["name"]


def test_muss1b_keine_glocke_fuer_die_umfrage_von_vor_dem_eintritt(welt, patched_db):
    """MUSS 1b: Start-Glocke und Erinnerung gehen nur an Lesende der Umfrage."""
    from datetime import timedelta

    from diakronos_app.api import chat as C
    from diakronos_app.models.chat import ChatUmfrage

    kopf = _drei(welt)
    _set_user(ANNA)
    u = C.umfrage_anlegen(kopf["name"], "Wann treffen wir uns?", ["Sa", "So"])["umfrage"]
    _dieter_spaeter_eintreten(kopf)
    glocken = _glocken_texte(patched_db(), DIETER)
    assert glocken == [], glocken

    # Erinnerung: Frist in 24 h, Dieter ist NIE erinnert worden.
    s = patched_db()
    zeile = s.get(ChatUmfrage, u["name"])
    zeile.frist_am = zeile.erstellt_am + timedelta(hours=48)
    zeile.erinnert_am = None
    s.commit()
    _set_user(ANNA)
    C.chat_umfrage_erinnerungen(jetzt=zeile.erstellt_am + timedelta(hours=30))
    assert _glocken_texte(patched_db(), DIETER) == [], "Dieter wurde erinnert"
    # Bert (von Anfang an dabei) wird erinnert — die Filterung ist keine
    # stille Abschaltung der Erinnerung.
    from diakronos_app.api.chat import _umfrage_betreff_ende

    glocke_bert = _glocken_texte(patched_db(), BERT)
    assert any(t == _umfrage_betreff_ende(
        patched_db().get(ChatGespraech, kopf["name"]), "Runde Kigo-Vorbereitung")
        for t in glocke_bert), glocke_bert


def test_muss1b_umfrage_aus_der_gruppe_ist_fuer_alle_wie_bisher(welt, patched_db):
    """Gegenprobe: in einer GRUPPE gibt es keine Eintrittsgrenze (NULL).

    ``sichtbar_ab`` ist ein Feld der RUNDE — die Prüfung darf dort nicht
    greifen. Aufgebaut wird die kleinste Gruppe mit Chat-Modul, damit die
    Umfrage überhaupt angelegt werden darf.
    """
    from diakronos_app.api import chat as C
    from diakronos_app.models.diakonos import (
        Gruppe,
        Gruppenmitgliedschaft,
    )
    from diakronos_app.models.rechte import RechteGruppenrolle, RechteModul

    s = patched_db()
    s.add(Gruppe(name="G-Test", gruppenname="Testgruppe"))
    s.add(Gruppenmitgliedschaft(name="gm-a", parent="G-Test",
                                parentfield="mitglieder", mitglied=MI[ANNA]))
    s.add(Gruppenmitgliedschaft(name="gm-b", parent="G-Test",
                                parentfield="mitglieder", mitglied=MI[BERT]))
    s.add_all([
        RechteGruppenrolle(gruppe="G-Test", benutzer=ANNA, rolle="HV"),
        RechteModul(gruppe="G-Test", modul="chat"),
    ])
    s.commit()
    _set_user(ANNA)
    g = C.gespraech_anlegen("G-Test")["name"]
    u = C.umfrage_anlegen(g, "Gruppenfrage", ["A", "B"])["umfrage"]
    _set_user(BERT)
    assert C.umfrage_ergebnis(u["name"])["name"] == u["name"]


# ── 16) CHAT-7b-2: alte Nachrichten über Zitat/Reaktion/Meldung (SOLL 2) ───

def _reagieren(nachricht: str, konto: str, zeichen: str = "👍") -> dict:
    from diakronos_app.api import chat as C

    _set_user(konto)
    return C.reaktion_setzen(nachricht, zeichen)


def test_soll2_zitat_von_vor_dem_eintritt_bleibt_leer(welt):
    """SOLL 2: die Zitat-HÜLLE bleibt, der TEXT von vorher wird nicht gezeigt.

    Dieter kommt nach der alten Nachricht dazu. Die Antwort auf sie entsteht
    NACH seinem Eintritt (er sieht sie also), zitiert aber den Text von
    vorher — der bleibt für ihn leer, für die anderen nicht.
    """
    from diakronos_app.api import chat as C

    kopf = _drei(welt)
    alt = _senden(kopf["name"], "Alter Text vor Dieters Eintritt", ANNA)
    _dieter_spaeter_eintreten(kopf)
    _set_user(BERT)
    C.senden(kopf["name"], "Antwort nach dem Eintritt", alt["name"])

    zeilen = _verlauf(kopf["name"], DIETER)["nachrichten"]
    zitiert = [z for z in zeilen if z["antwort_auf"] == alt["name"]]
    assert zitiert, [z["name"] for z in zeilen]
    # Hülle bleibt (die Kennung), Text ist nicht sichtbar.
    assert zitiert[0]["antwort_auf_text"] is None
    # Bert (von Anfang an dabei) sieht das Zitat.
    zeilen = _verlauf(kopf["name"], BERT)["nachrichten"]
    zitiert = [z for z in zeilen if z["antwort_auf"] == alt["name"]]
    assert zitiert[0]["antwort_auf_text"] == "Alter Text vor Dieters Eintritt"


def test_soll2_reaktion_meldung_und_lesestand_auf_alte_nachricht_sind_404(welt):
    from diakronos_app.api import chat as C
    from diakronos_app.frappe_compat.exceptions import DoesNotExistError

    kopf = _drei(welt)
    alt = _senden(kopf["name"], "Alter Text vor Dieters Eintritt", ANNA)
    _dieter_spaeter_eintreten(kopf)
    _set_user(DIETER)
    with pytest.raises(DoesNotExistError):
        C.reaktion_setzen(alt["name"], "👍")
    with pytest.raises(DoesNotExistError):
        C.meldung_senden(alt["name"], "beleidigung")
    with pytest.raises(DoesNotExistError):
        C.lesestand_setzen(kopf["name"], alt["name"])
    # Ohne Anker setzt der Lesestand nur bis zur SICHTBAREN Nachricht.
    _senden(kopf["name"], "Nach dem Eintritt", ANNA)
    _set_user(DIETER)
    stand = C.lesestand_setzen(kopf["name"])
    assert stand["bis"] != alt["name"]
    assert C.reaktion_setzen(stand["bis"], "👍")["reaktionen"]
    # Bert darf auf die alte Nachricht reagieren (keine Grenze für ihn).
    _set_user(BERT)
    assert C.reaktion_setzen(alt["name"], "👍")["reaktionen"]


# ── 17) CHAT-7b-2: Austritt beendet Vorschläge als `beendet` (SOLL 3/4) ────

def test_soll4_austritt_beendet_vorschlaege_als_beendet_nicht_abgelehnt(welt, patched_db):
    from diakronos_app.api.chat import _vorschlag_satz

    kopf = _drei(welt)
    v = _vorschlagen(kopf["name"], MI[DIETER], ANNA)["vorschlag"]
    _zustimmen(v["name"], BERT)
    _verlassen(kopf["name"], CLARA)
    s = patched_db()
    zeile = s.get(ChatRundeVorschlag, v["name"])
    assert zeile.stand == VORSCHLAG_BEENDET
    assert zeile.stand in ("offen", "angenommen", "abgelehnt", "beendet")
    # Der Systemhinweis sagt „beendet“ und nennt niemanden sonst.
    assert "beendet" in _vorschlag_satz("Anna", "Dieter", VORSCHLAG_BEENDET)
    assert "Runde geändert" in _vorschlag_satz("Anna", "Dieter", VORSCHLAG_BEENDET)
    # Im Verlauf steht die Zeile mit dem neuen Stand.
    zeilen = _verlauf(kopf["name"], ANNA)["nachrichten"]
    system = [z for z in zeilen if z.get("system", {}).get("art") == "runde_vorschlag"]
    assert system and system[0]["system"]["stand"] == VORSCHLAG_BEENDET, system


def test_soll4_nach_einem_austritt_ist_ein_neuer_vorschlag_wieder_moeglich(welt):
    """`beendet` blockiert den partiellen Unique-Index NICHT (kein CHECK)."""
    kopf = _drei(welt)
    v = _vorschlagen(kopf["name"], MI[DIETER], ANNA)["vorschlag"]
    _verlassen(kopf["name"], CLARA)
    v2 = _vorschlagen(kopf["name"], MI[DIETER], ANNA)["vorschlag"]
    assert v2["stand"] == VORSCHLAG_OFFEN
    assert v2["name"] != v["name"]


# ── 18) CHAT-7b-2: eigener Vorschlag zählt nicht als ungelesen (SOLL 5) ────

def test_soll5_eigener_vorschlag_zaehlt_nicht_als_ungelesen_bei_den_anderen_schon(welt):
    kopf = _drei(welt)
    # Ein echter Beitrag, damit es eine Vorschau gibt (die Vorschlagszeile
    # selbst trägt keinen Text — s. u.).
    _senden(kopf["name"], "Geheimnis von vorher", ANNA)
    vorher = {e["name"]: e["ungelesen"] for e in _meine(ANNA)["gespraeche"]}[kopf["name"]]
    _vorschlagen(kopf["name"], MI[DIETER], ANNA)
    danach = {e["name"]: e for e in _meine(ANNA)["gespraeche"]}[kopf["name"]]
    assert danach["ungelesen"] == vorher, (vorher, danach["ungelesen"])
    # Die übrigen SOLLEN es sehen — sie stimmen ab.
    for konto in (BERT, CLARA):
        eintrag = {e["name"]: e for e in _meine(konto)["gespraeche"]}[kopf["name"]]
        # 2 = der echte Beitrag von Anna + der Vorschlag (beides fremd).
        assert eintrag["ungelesen"] == 2, (konto, eintrag["ungelesen"])
        # Die Vorschau zeigt weiter den letzten ECHTEN Beitrag — die
        # Vorschlagszeile trägt keinen Text in der Datenbank (er entsteht
        # beim Lesen und steht im Verlauf).
        assert eintrag["letzte_nachricht"] == "Geheimnis von vorher"


def test_soll5_eigener_vorschlag_loest_keine_glocke_aus(welt, patched_db):
    from diakronos_app.api import chat as C

    kopf = _drei(welt)
    _set_user(ANNA)
    C.lesestand_setzen(kopf["name"])
    vorher = len(_glocken_texte(patched_db(), ANNA))
    _vorschlagen(kopf["name"], MI[DIETER], ANNA)
    # Glocken entstehen im Minuten-Job; hier zählt der Merker/die Bedingung:
    # für Anna ist nichts offen, für Bert/Clara schon.
    from diakronos_app.api.chat import _glocke_faellig

    s = patched_db()
    g = s.get(ChatGespraech, kopf["name"])
    assert _glocke_faellig(s, g, ANNA) is False
    assert _glocke_faellig(s, g, BERT) is True
    assert len(_glocken_texte(patched_db(), ANNA)) == vorher


# ── 19) CHAT-7b-2 R1: Senden MIT antwort_auf prüft die Sichtbarkeit ─────────

def test_r1_senden_mit_antwort_auf_eine_alte_nachricht_ist_404(welt):
    """MUSS 1 (R1): der Zitat-Text kommt aus der SENDE-Antwort — also 404.

    Vorher prüfte nur das Lesen (``_zitate``) die Grenze; ``senden`` mit
    ``antwort_auf`` gab den Text einer Nachricht von vor dem Eintritt in der
    eigenen Antwort heraus. Es wird NICHTS angelegt.
    """
    from diakronos_app.api import chat as C
    from diakronos_app.frappe_compat.exceptions import DoesNotExistError

    kopf = _drei(welt)
    alt = _senden(kopf["name"], "Geheimnis von vorher", ANNA)
    _dieter_spaeter_eintreten(kopf)
    _set_user(DIETER)
    with pytest.raises(DoesNotExistError):
        C.senden(kopf["name"], "Antwort auf etwas Unsichtbares", alt["name"])
    # Es wurde NICHTS angelegt — auch für Anna nicht, die alles sieht.
    _set_user(ANNA)
    texte = [n.get("text") for n in _verlauf(kopf["name"], ANNA)["nachrichten"]]
    assert "Antwort auf etwas Unsichtbares" not in texte, texte
    # Ohne ``antwort_auf`` darf Dieter normal senden.
    _set_user(DIETER)
    neu = C.senden(kopf["name"], "Hallo in die Runde")
    # Und eine Antwort auf eine SICHTBARE Nachricht geht mit Zitattext.
    _set_user(ANNA)
    antwort = C.senden(kopf["name"], "Willkommen", neu["name"])
    _set_user(DIETER)
    assert C.senden(kopf["name"], "Danke", antwort["name"])["antwort_auf_text"] == "Willkommen"
