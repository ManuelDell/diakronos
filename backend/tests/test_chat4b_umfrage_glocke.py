"""CHAT-4b: Umfrage-Glocken (Start + Erinnerung 24 h vor der Frist) und die
Restpunkte a/b aus dem CHAT-4a-Review.

Konzept ``docs/konzepte/CHAT-KONZEPT.md`` S2 (Zeile ~91): „eine Glocke beim
Start (‚Neue Umfrage im Chor'), eine Erinnerung 24 h vor Frist an die, die
noch nicht abgestimmt haben“. Geprüft wird gegen die ECHTEN Wege — die
Endpunkte ``umfrage_anlegen``/``umfrage_abstimmen``/``umfrage_schliessen``,
den ECHTEN Rechte-Kern, den ECHTEN Scheduler-Job und die echte
``Notification Log``-Zeile (nicht gegen Attrappen):

  * START-GLOCKE: an alle, die das Gespräch lesen dürfen — ohne die/den
    Anlegende/n, ohne stumm Geschaltete, ohne Personen ohne Teilnahmezeile;
    ohne Frage, ohne Optionen, ohne Namen; Modul aus ⇒ nichts
  * ERINNERUNG: genau einmal (``chat_umfrage.erinnert_am``), nur an
    Nicht-Abstimmte (offen UND anonym), nicht nach Schließen/Löschen,
    Grenzfall 24 h — und an die RICHTIGE Umfrage (Review R1/2: zwei offene
    Umfragen im selben Gespräch)
  * RESTPUNKT a: die fortgeschriebene Glocke steht oben in
    ``api.audit.get_my_notifications`` (siehe ``test_chat4a_glocke.py``)
  * RESTPUNKT b: nach teilweisem Lesen trägt die Bündel-Glocke die NEUE Zahl —
    und legt dabei NIE eine neue Glocke an (Review R1/4: weggeklickt, stumm,
    Ruhezeit)
  * Review R1: die Job-Naht ist KEIN HTTP-Endpunkt (MUSS 1), die Zeitstempel
    der Glocke sind UTC (MUSS 3), die Umfrage-Glocken eines gelöschten
    Gesprächs räumt CHAT-8 mit ab (MUSS 5), kurze Fristen werden nicht
    erinnert (SOLL), ``_glocken_titel`` liefert nie „None“ (SOLL)
  * Migration ``chat4b_umfrage_erinnerung``: genau ein Kopf, hinter
    ``chat7a_direkt`` (Sammelzweig mit CHAT-7a), upgrade/downgrade/upgrade
    — der Kopfname wird NIE fest verdrahtet (die Kette wächst weiter)

Aufruf (Karte):

    docker run --rm --network none --entrypoint python -v <wt>:/repo:ro \\
      -w /repo/backend -e PYTHONPATH=/repo/backend/src:/repo/backend/tests:/repo/tools \\
      -e PYTHONDONTWRITEBYTECODE=1 <vorbau> -m pytest -q -p no:cacheprovider \\
      --timeout=900 tests/test_chat4b_umfrage_glocke.py
"""

from __future__ import annotations

import importlib
import uuid
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine

from diakronos_app import db as dbmod
from diakronos_app.models.chat import ChatUmfrage
from diakronos_app.models.core import HasRole, NotificationLog, User
from diakronos_app.models.diakonos import (
    Gruppe,
    Gruppenmitgliedschaft,
    Mitglied,
    Untergruppe,
    Untergruppenmitgliedschaft,
)
from diakronos_app.models.rechte import RechteGruppenrolle, RechteModul

#: Die Test-Naht liegt im MODUL ``frappe_compat.session`` (wie ``test_chat2_api``).
_session_mod = importlib.import_module("diakronos_app.frappe_compat.session")

BACKEND = Path(__file__).resolve().parents[1]

ADMIN = "admin@x.org"
HV = "hv@x.org"
MV = "mv@x.org"
GL = "gl@x.org"
SAENGER = "saenger@x.org"      # Mitglied Chor (legt an)
SAENGER2 = "saenger2@x.org"    # zweites Mitglied Chor (bekommt die Glocke)
NOTEN = "noten@x.org"          # Mitglied der Untergruppe Notenausschuss
FREMD = "fremd@x.org"          # Gemeindemitglied ohne Gruppe
JUGEND = "jugend@x.org"        # Mitglied einer Gruppe OHNE Chat-Modul

GLOCKE_UMFRAGE = "chat_umfrage"
GLOCKE_GESPRAECH = "chat_gespraech"


def _set_user(konto: str | None) -> None:
    _session_mod.set_user(konto)


def _reset() -> None:
    _session_mod.reset_user()


@pytest.fixture()
def welt(patched_db):
    """Chor mit Untergruppe — dieselbe Welt wie ``test_chat4a_glocke.py``."""
    s = patched_db()
    for konto, kurz in [(ADMIN, "Admin"), (HV, "Hv"), (MV, "Mv"), (GL, "Gl"),
                        (SAENGER, "Sa"), (SAENGER2, "Sb"), (NOTEN, "No"),
                        (FREMD, "Fr"), (JUGEND, "Ju")]:
        s.add(User(name=konto, email=konto, enabled=1, full_name=kurz))
        s.add(Mitglied(name=f"M-{kurz}", vorname=kurz, nachname="X", email=konto,
                       user=konto))
    s.add(HasRole(name="hr-admin", parent=ADMIN, parenttype="User",
                  role="System Manager"))
    s.add(Gruppe(name="Chor", gruppenname="Chor"))
    s.add(Gruppe(name="Jugend", gruppenname="Jugend"))
    s.add(Untergruppe(name="UG-Noten", untergruppenname="Notenausschuss",
                      gruppe="Chor"))
    s.add(Gruppenmitgliedschaft(name="gm1", parent="Chor",
                                parentfield="mitglieder", mitglied="M-Sa"))
    s.add(Gruppenmitgliedschaft(name="gm2", parent="Chor",
                                parentfield="mitglieder", mitglied="M-Sb"))
    s.add(Gruppenmitgliedschaft(name="gm3", parent="Chor",
                                parentfield="mitglieder", mitglied="M-Mv"))
    s.add(Untergruppenmitgliedschaft(name="ugm1", parent="UG-Noten",
                                     parentfield="mitglieder", mitglied="M-No"))
    s.add(Gruppenmitgliedschaft(name="gm4", parent="Jugend",
                                parentfield="mitglieder", mitglied="M-Ju"))
    s.add_all([
        RechteGruppenrolle(gruppe="Chor", benutzer=HV, rolle="HV"),
        RechteGruppenrolle(gruppe="Chor", benutzer=MV, rolle="MV"),
        RechteGruppenrolle(gruppe="Chor", untergruppe="UG-Noten", benutzer=GL,
                           rolle="GL"),
        RechteModul(gruppe="Chor", modul="chat"),
    ])
    s.commit()
    yield s
    s.close()


@pytest.fixture()
def gespraech(welt):
    """Das Chor-Gespräch (lazy angelegt, per Endpunkt) — Teilnahme: Saenger."""
    from diakronos_app.api import chat as C

    _set_user(SAENGER)
    name = C.gespraech_anlegen("Chor")["name"]
    _reset()
    return name


def _teilnahme(gespraech: str, konto: str) -> None:
    """Teilnahmezeile anlegen (Gespräch öffnen — wie im Betrieb)."""
    from diakronos_app.api import chat as C

    _set_user(konto)
    C.gespraech_anlegen("Chor")
    _reset()


def _umfrage(gespraech: str, konto: str = SAENGER, frage: str = "Wann proben wir?",
             optionen=None, anonym: bool = True, frist=None) -> dict:
    from diakronos_app.api import chat as C

    _set_user(konto)
    antwort = C.umfrage_anlegen(
        gespraech, frage,
        optionen=optionen if optionen is not None else ["Samstag", "Sonntag"],
        anonym=anonym, frist=frist)
    _reset()
    return antwort


def _glocken(konto: str, doctype: str = GLOCKE_UMFRAGE) -> list[NotificationLog]:
    with dbmod.SessionLocal() as s:
        return list(s.query(NotificationLog)
                    .filter(NotificationLog.for_user == konto,
                            NotificationLog.document_type == doctype)
                    .order_by(NotificationLog.creation)
                    .all())


def _erinnerung(jetzt: datetime | None = None, vorlauf: int | None = None) -> int:
    from diakronos_app.api import chat as C

    return C.chat_umfrage_erinnerungen(jetzt=jetzt, vorlauf=vorlauf)


def _umfrage_zeile(name: str) -> ChatUmfrage:
    with dbmod.SessionLocal() as s:
        return s.get(ChatUmfrage, name)


# ── Start-Glocke ────────────────────────────────────────────────────────────


def test_start_glocke_geht_an_alle_lesenden_ausser_dem_anlegenden(welt, gespraech):
    """Kartenkern: „Neue Umfrage im Chor“ — nicht an die/den Anlegende/n."""
    _teilnahme(gespraech, SAENGER2)
    _teilnahme(gespraech, MV)
    _teilnahme(gespraech, GL)      # GL liest den Gruppenchat geerbt

    _umfrage(gespraech, SAENGER)

    for konto in (SAENGER2, MV, GL):
        glocken = _glocken(konto)
        assert len(glocken) == 1, f"{konto} hat keine Start-Glocke"
        assert glocken[0].subject == "Neue Umfrage im Chor"
        assert glocken[0].read is False
    assert _glocken(SAENGER) == [], "die anlegende Person bekommt keine Glocke"


def test_start_glocke_ohne_inhalt_und_ohne_namen(welt, gespraech):
    """Die Glocke nennt NUR den Gesprächstitel (Konzept 4.5)."""
    _teilnahme(gespraech, SAENGER2)
    _umfrage(gespraech, SAENGER, frage="Sollen wir Annas Plan nehmen?",
             optionen=["Annas Plan", "Mein Plan"])

    glocke = _glocken(SAENGER2)[0]
    zusammen = f"{glocke.subject}\n{glocke.email_content}"
    assert "Wann proben" not in zusammen
    assert "Annas Plan" not in zusammen
    assert "Sollen wir" not in zusammen
    # Kein Name der anlegenden Person (weder Konto noch Mitgliedskennung).
    assert SAENGER not in zusammen
    assert "Sa" not in zusammen.replace("Samstag", "")
    assert glocke.from_user in (None, "")


def test_stumme_bekommen_keine_start_glocke(welt, gespraech):
    """F3: stumm = keine Glocke — die Start-Glocke ist auch eine Glocke."""
    from diakronos_app.api import chat as C

    _teilnahme(gespraech, SAENGER2)
    _set_user(SAENGER2)
    C.stumm_setzen(gespraech, True)
    _reset()

    _umfrage(gespraech, SAENGER)

    assert _glocken(SAENGER2) == []


def test_ohne_teilnahmezeile_keine_glocke(welt, gespraech):
    """Wer das Gespräch nie geöffnet hat, bekommt nichts (Regel wie CHAT-4a)."""
    _teilnahme(gespraech, SAENGER2)
    _umfrage(gespraech, SAENGER)

    # Mitglied der Gruppe, aber ohne ``chat_teilnehmer``-Zeile.
    assert _glocken(NOTEN) == []
    assert _glocken(SAENGER2), "die Kontrollperson muss eine Glocke haben"
    # Fremdes Gemeindemitglied: kein Recht, also nichts.
    assert _glocken(FREMD) == []


def test_modul_aus_bekommt_keine_umfrage_glocke(welt):
    """Modul ``chat`` aus ⇒ der Kern gibt kein Lesen ⇒ keine Glocke.

    In der Gruppe „Jugend“ fehlt das Modul: das Gespräch lässt sich dort nicht
    einmal anlegen (der Rechte-Kern verweigert es), eine Umfrage schon gar
    nicht — und eine Glocke entsteht dabei nie.
    """
    from diakronos_app.api import chat as C
    from diakronos_app.frappe_compat.exceptions import PermissionError as KernAblehnung

    _set_user(JUGEND)
    with pytest.raises(KernAblehnung):
        C.gespraech_anlegen("Jugend")
    _reset()
    assert _glocken(JUGEND) == []


def test_zweite_umfrage_hat_eigene_glocke(welt, gespraech):
    """Zwei Umfragen im selben Gespräch: zwei Glocken (je Umfrage eine)."""
    _teilnahme(gespraech, SAENGER2)
    erste = _umfrage(gespraech, SAENGER, frage="Erste?")["umfrage"]["name"]
    zweite = _umfrage(gespraech, SAENGER, frage="Zweite?")["umfrage"]["name"]

    glocken = _glocken(SAENGER2)
    assert sorted(g.document_name for g in glocken) == sorted([erste, zweite])
    assert len({g.name for g in glocken}) == 2


# ── Erinnerung 24 h vor der Frist ───────────────────────────────────────────


def _mit_frist(gespraech: str, stunden: int = 30, konto: str = SAENGER,
               anonym: bool = True) -> tuple[str, datetime]:
    """Umfrage mit Frist ``stunden`` ab jetzt; liefert (Umfrage, Frist)."""
    from diakronos_app.api import chat as C

    jetzt = C._jetzt()
    frist = jetzt + timedelta(hours=stunden)
    # ``_frist_lesen`` nimmt Minuten — sekundengenau weitergerechnet wird mit
    # der ANGELEGTEN Frist (was der Endpunkt wirklich gespeichert hat).
    antwort = _umfrage(gespraech, konto, frage="Termin?", anonym=anonym,
                       frist=frist.strftime("%Y-%m-%d %H:%M"))
    name = antwort["umfrage"]["name"]
    return name, _umfrage_zeile(name).frist_am


def _erwartete_empfaenger() -> list[str]:
    """Wer nach der Öffnung des Gesprächs eine Erinnerung bekommt.

    Das Gespräch wird vom Anlegenden (``SAENGER``) und von der Kontrollperson
    (``SAENGER2``) geöffnet — beide sind Teilnehmende und dürfen lesen.
    """
    return [SAENGER, SAENGER2]


def _umfrage_glocken_texte(konto: str) -> list[str]:
    """Betreffs der Umfrage-Glocken einer Person, alt → neu."""
    return [str(g.subject or "") for g in _glocken(konto)]


def test_erinnerung_an_nicht_abgestimmte_offen(welt, gespraech):
    """OFFEN: wer schon gestimmt hat, bekommt KEINE Erinnerung."""
    from diakronos_app.api import chat as C

    _teilnahme(gespraech, SAENGER2)
    _teilnahme(gespraech, MV)
    name, frist = _mit_frist(gespraech, stunden=48, anonym=False)
    # Beide haben die Start-Glocke (ungelesen) — die Erinnerung schreibt sie fort.
    assert _glocken(SAENGER2) and _glocken(MV)

    _set_user(SAENGER2)
    C.umfrage_abstimmen(name, optionen=[1])
    _reset()

    # 25 h vor der Frist: noch zu früh.
    assert _erinnerung(jetzt=frist - timedelta(hours=25)) == 0
    assert "endet morgen" not in _umfrage_glocken_texte(SAENGER2)[0]

    # 24 h vor der Frist: fällig — nur an MV (SAENGER2 hat abgestimmt).
    assert _erinnerung(jetzt=frist - timedelta(hours=24)) >= 1
    assert _umfrage_glocken_texte(SAENGER2) == ["Neue Umfrage im Chor"]
    assert _umfrage_glocken_texte(MV) == ["Umfrage im Chor endet morgen"]


def test_erinnerung_an_nicht_abgestimmte_anonym(welt, gespraech):
    """ANONYM: die Abgabe-Marke zählt — ohne jeden Bezug zur Option."""
    from diakronos_app.api import chat as C

    _teilnahme(gespraech, SAENGER2)
    _teilnahme(gespraech, MV)
    name, frist = _mit_frist(gespraech, stunden=48, anonym=True)

    _set_user(SAENGER2)
    C.umfrage_abstimmen(name, optionen=[2])
    _reset()

    _erinnerung(jetzt=frist - timedelta(hours=23))
    assert _umfrage_glocken_texte(SAENGER2) == ["Neue Umfrage im Chor"]
    assert _umfrage_glocken_texte(MV) == ["Umfrage im Chor endet morgen"]


def test_erinnerung_genau_einmal(welt, gespraech):
    """Idempotenz über ``chat_umfrage.erinnert_am``."""
    _teilnahme(gespraech, SAENGER2)
    name, frist = _mit_frist(gespraech, stunden=48)

    assert _erinnerung(jetzt=frist - timedelta(hours=24)) == len(_erwartete_empfaenger())
    assert _umfrage_zeile(name).erinnert_am is not None
    # Zweiter Lauf (eine Minute später): nichts mehr zu tun, keine neue Zeile.
    assert _erinnerung(jetzt=frist - timedelta(hours=23, minutes=59)) == 0
    assert _umfrage_glocken_texte(SAENGER2) == ["Umfrage im Chor endet morgen"]


def test_erinnerung_grenzfall_24_stunden(welt, gespraech):
    """Die Frist in GENAU 24 h ist fällig; 24 h + 1 min noch nicht."""
    _teilnahme(gespraech, SAENGER2)
    name, frist = _mit_frist(gespraech, stunden=48)

    assert _erinnerung(jetzt=frist - timedelta(hours=24, minutes=1)) == 0
    assert _umfrage_zeile(name).erinnert_am is None
    assert _erinnerung(jetzt=frist - timedelta(hours=24)) == len(_erwartete_empfaenger())


def test_keine_erinnerung_nach_schliessen(welt, gespraech):
    from diakronos_app.api import chat as C

    _teilnahme(gespraech, SAENGER2)
    name, frist = _mit_frist(gespraech, stunden=48)
    _set_user(SAENGER)
    C.umfrage_schliessen(name)
    _reset()

    assert _erinnerung(jetzt=frist - timedelta(hours=23)) == 0
    assert _umfrage_glocken_texte(SAENGER2) == ["Neue Umfrage im Chor"]


def test_keine_erinnerung_fuer_geloeschte_umfrage(welt, gespraech):
    from diakronos_app.api import chat as C

    _teilnahme(gespraech, SAENGER2)
    antwort = _mit_frist(gespraech, stunden=48)
    name, frist = antwort

    # Die Hülle-Nachricht löschen (Selbstlöschung der verfassenden Person).
    with dbmod.SessionLocal() as s:
        from diakronos_app.models.chat import ChatNachricht

        n = s.query(ChatNachricht).filter_by(umfrage=name).one()
        n.geloescht_am = C._jetzt()
        s.commit()

    assert _erinnerung(jetzt=frist - timedelta(hours=23)) == 0
    assert _umfrage_glocken_texte(SAENGER2) == ["Neue Umfrage im Chor"]


def test_keine_erinnerung_ohne_frist(welt, gespraech):
    """Ohne Frist gibt es kein „endet morgen“."""
    _teilnahme(gespraech, SAENGER2)
    _umfrage(gespraech, SAENGER, frage="Offen bis Schluss")

    assert _erinnerung() == 0
    assert _umfrage_glocken_texte(SAENGER2) == ["Neue Umfrage im Chor"]


def test_erinnerung_nach_verstrichener_frist_schliesst_zuerst(welt, gespraech):
    """Der Job schließt fällige Umfragen SELBST — eine abgelaufene wird nicht
    mehr erinnert (sonst käme „endet morgen“ nach dem Ende)."""
    _teilnahme(gespraech, SAENGER2)
    name, frist = _mit_frist(gespraech, stunden=2)

    assert _erinnerung(jetzt=frist + timedelta(minutes=5)) == 0
    assert _umfrage_zeile(name).geschlossen_am == frist
    assert _umfrage_glocken_texte(SAENGER2) == ["Neue Umfrage im Chor"]


def test_erinnerung_an_stumme_nicht(welt, gespraech):
    from diakronos_app.api import chat as C

    _teilnahme(gespraech, SAENGER2)
    _teilnahme(gespraech, MV)
    name, frist = _mit_frist(gespraech, stunden=48)

    _set_user(SAENGER2)
    C.stumm_setzen(gespraech, True)
    _reset()

    _erinnerung(jetzt=frist - timedelta(hours=23))
    # Stumm schaltet die Glocke, nicht die Vergangenheit: die START-Glocke
    # stand schon vor dem Stummschalten — sie bleibt, wird aber NICHT zur
    # Erinnerung fortgeschrieben (stumm_setzen fasst bestehende Glocken nicht an).
    assert _umfrage_glocken_texte(SAENGER2) == ["Neue Umfrage im Chor"]
    assert _umfrage_glocken_texte(MV) == ["Umfrage im Chor endet morgen"]


def test_erinnerung_verraet_keine_liste_an_dritte(welt, gespraech):
    """Die Glocke sagt der Person nur, dass SIE noch nicht abgestimmt hat."""
    from diakronos_app.api import chat as C

    _teilnahme(gespraech, SAENGER2)
    _teilnahme(gespraech, MV)
    name, frist = _mit_frist(gespraech, stunden=48, anonym=False)

    _set_user(SAENGER2)
    C.umfrage_abstimmen(name, optionen=[1])
    _reset()
    _erinnerung(jetzt=frist - timedelta(hours=23))

    glocke = _glocken(MV)[-1]
    zusammen = f"{glocke.subject}\n{glocke.email_content}"
    # Kein Name, keine Anzahl, wer/wie viele nicht abgestimmt haben.
    assert SAENGER2 not in zusammen
    assert "Sa" not in zusammen
    assert "1" not in zusammen.replace("24", "")


def test_erinnerung_trifft_die_richtige_umfrage(welt, gespraech):
    """Review R1/2: zwei offene Umfragen — die Erinnerung zu A filtert nach A.

    Die frühere Fassung nahm „die neueste Umfrage des Gesprächs“; hier wird
    SAENGER2s Stimme bei A abgegeben und B bleibt offen. Die Erinnerung zu A
    darf SAENGER2 deshalb NICHT schreiben, die zu B schon — und jede Glocke
    hängt an ihrer eigenen Umfrage.
    """
    from diakronos_app.api import chat as C

    _teilnahme(gespraech, SAENGER2)
    a_name, a_frist = _mit_frist(gespraech, stunden=48, anonym=False)
    b_name, _b_frist = _mit_frist(gespraech, stunden=72, anonym=False)
    assert a_name != b_name

    _set_user(SAENGER2)
    C.umfrage_abstimmen(a_name, optionen=[1])
    _reset()

    # Nur A ist fällig (Erinnerungsfenster 24 h), B nicht.
    assert _erinnerung(jetzt=a_frist - timedelta(hours=23)) >= 1
    nach_a = {g.document_name: g.subject for g in _glocken(SAENGER2)}
    assert nach_a[a_name] == "Neue Umfrage im Chor", (
        "A wurde erinnert, obwohl SAENGER2 bei A abgestimmt hat")
    assert nach_a[b_name] == "Neue Umfrage im Chor"
    # SAENGER (hat nicht abgestimmt) bekommt die Erinnerung zu A.
    assert _glocken(SAENGER)[0].document_name == a_name
    assert _glocken(SAENGER)[0].subject == "Umfrage im Chor endet morgen"


def test_keine_erinnerung_bei_kurzer_frist(welt, gespraech):
    """Review R1, SOLL: < 24 h zwischen Anlage und Frist ⇒ Start-Glocke genügt."""
    _teilnahme(gespraech, SAENGER2)
    # Frist in 10 h — die Umfrage wurde GERADE angelegt (10 h < 24 h).
    name, frist = _mit_frist(gespraech, stunden=10)

    assert _erinnerung(jetzt=frist - timedelta(hours=9)) == 0
    assert _umfrage_zeile(name).erinnert_am is None
    assert _umfrage_glocken_texte(SAENGER2) == ["Neue Umfrage im Chor"]


def test_erinnerung_setzt_merker_nicht_wenn_keine_glocke_geschrieben_wurde(
        welt, gespraech):
    """Review R1, SOLL: bei einem Schreibfehler holt der nächste Lauf es nach."""
    from diakronos_app.api import chat as C

    _teilnahme(gespraech, SAENGER2)
    name, frist = _mit_frist(gespraech, stunden=48)

    echt = C._umfrage_glocke_setzen
    # KEIN ``monkeypatch``: dessen ``undo()`` nimmt auch die DB-Naht der
    # Fixture zurück (``patched_db``) — der zweite Lauf ginge dann in die
    # echte Datenbank. Die Panne wird deshalb von Hand gesetzt und behoben.
    C._umfrage_glocke_setzen = lambda *a, **k: False
    try:
        assert _erinnerung(jetzt=frist - timedelta(hours=23)) == 0
    finally:
        C._umfrage_glocke_setzen = echt
    assert _umfrage_zeile(name).erinnert_am is None, (
        "der Merker wurde trotz gescheitertem Schreiben gesetzt")

    # Ohne die Panne läuft die Erinnerung beim nächsten Takt.
    assert _erinnerung(jetzt=frist - timedelta(hours=23, minutes=1)) >= 1
    assert _umfrage_zeile(name).erinnert_am is not None


def test_merker_wird_ohne_empfaenger_gesetzt(welt, gespraech):
    """Review R1, SOLL: niemand offen ⇒ nichts zu erinnern, Merker trotzdem."""
    from diakronos_app.api import chat as C

    # Nur der Anlegende ist Teilnehmer — und der bekommt keine Erinnerung.
    name, frist = _mit_frist(gespraech, stunden=48)
    _set_user(SAENGER)
    C.umfrage_abstimmen(name, optionen=[1])
    _reset()

    assert _erinnerung(jetzt=frist - timedelta(hours=23)) == 0
    assert _umfrage_zeile(name).erinnert_am is not None, (
        "ohne Empfänger muss der Merker gesetzt werden (sonst jeder Takt neu)")


def test_glocken_titel_nie_none(welt):
    """Review R1, SOLL: ohne Titel/Einheit (CHAT-7a „direkt“) steht ein Wort da."""
    from diakronos_app.api import chat as C
    from diakronos_app.models.chat import ChatGespraech

    g = ChatGespraech(name="chat-g-direkt", gruppe=None, untergruppe=None,
                      titel=None)
    assert C._glocken_titel(g) == "Direktnachricht"
    g2 = ChatGespraech(name="chat-g-untergruppe", gruppe="Chor",
                       untergruppe="Notenausschuss", titel="")
    assert C._glocken_titel(g2) == "Notenausschuss"


def _direktgespraech() -> str:
    """1:1 zwischen SAENGER und SAENGER2 (CHAT-7a), über den Endpunkt geöffnet."""
    from diakronos_app.api import chat as C
    from diakronos_app.models.diakonos import Mitglied as _M

    with dbmod.SessionLocal.begin() as s:
        for kennung in ("M-Sa", "M-Sb"):
            s.get(_M, kennung).status = "Aktiv"
    _set_user(SAENGER)
    name = C.direkt_oeffnen("M-Sb")["name"]
    _reset()
    return name


def test_umfrage_im_direktgespraech_betreff_ohne_namen(welt):
    """Im 1:1: eigener Betreff „… in einer Direktnachricht“ — nie ein Name.

    Beide Teilnehmenden außer der/dem Anlegenden bekommen die Start-Glocke;
    die Erinnerung trägt ebenfalls den eigenen 1:1-Betreff.
    """
    name_g = _direktgespraech()
    name, frist = _mit_frist(name_g, stunden=48, konto=SAENGER)

    assert _glocken(SAENGER) == [], "die anlegende Person bekommt keine Glocke"
    glocken = _glocken(SAENGER2)
    assert len(glocken) == 1
    assert glocken[0].subject == "Neue Umfrage in einer Direktnachricht"
    zusammen = f"{glocken[0].subject}\n{glocken[0].email_content}"
    for verboten in (SAENGER, "Sa X", "Sb X", " Sa", " Sb", "im Direktnachricht"):
        assert verboten not in zusammen, verboten

    assert _erinnerung(jetzt=frist - timedelta(hours=24)) >= 1
    assert _umfrage_glocken_texte(SAENGER2) == [
        "Umfrage in einer Direktnachricht endet morgen"]
    assert _umfrage_glocken_texte(SAENGER) == [
        "Umfrage in einer Direktnachricht endet morgen"]


def test_umfrage_anlegen_endet_nie_mit_500_wenn_die_glocke_scheitert(
        welt, gespraech, monkeypatch):
    """Die Umfrage ist gespeichert — ein Glockenfehler bleibt im Log."""
    from diakronos_app.api import chat as C

    def kaputt(*_a, **_k):
        raise RuntimeError("Glocke kaputt")

    monkeypatch.setattr(C, "_glocke_neue_umfrage", kaputt)
    antwort = _umfrage(gespraech, SAENGER)
    assert antwort["umfrage"]["name"]
    assert _umfrage_zeile(antwort["umfrage"]["name"]) is not None


# ── Start-Glocke und Zeitstempel ─────────────────────────────────────────────


def test_umfrage_glocke_hat_utc_zeitstempel(welt, gespraech):
    """Review R1/3: ``creation``/``modified`` in UTC (wie ``_create``)."""
    from datetime import timezone

    _teilnahme(gespraech, SAENGER2)
    _umfrage(gespraech, SAENGER)

    glocke = _glocken(SAENGER2)[0]
    utc_jetzt = datetime.now(timezone.utc).replace(tzinfo=None)
    for feld in ("creation", "modified"):
        wert = getattr(glocke, feld)
        assert wert is not None
        abweichung = abs((utc_jetzt - wert).total_seconds())
        assert abweichung < 120, (
            f"{feld} ist nicht UTC (Abweichung {abweichung:.0f} s) — Wandzeit?")


def test_umfrage_glocke_setzt_owner_und_modified_by(welt, gespraech):
    """Review R1, SOLL: ``owner``/``modified_by`` wie ``_create``."""
    _teilnahme(gespraech, SAENGER2)
    _umfrage(gespraech, SAENGER)

    glocke = _glocken(SAENGER2)[0]
    assert glocke.owner == SAENGER
    assert glocke.modified_by == SAENGER


# ── CHAT-8: Glocken gelöschter Gespräche ────────────────────────────────────


def test_umfrage_glocke_eines_geloeschten_gespraechs_wird_entfernt(welt, gespraech):
    """Review R1/5: ``chat_umfrage`` gehört zu den Glockenzielen des Aufräumlaufs.

    Ohne den Eintrag bliebe „Neue Umfrage im Chor“ stehen, nachdem das
    Gespräch samt Umfrage gelöscht wurde — eine Glocke, die in nichts führt.
    """
    from diakronos_app import chat_aufbewahrung as AB
    from diakronos_app.models.chat import ChatNachricht

    assert "chat_umfrage" in AB.GLOCKE_DOKUMENTTYPEN
    _teilnahme(gespraech, SAENGER2)
    _umfrage(gespraech, SAENGER)
    assert len(_glocken(SAENGER2)) == 1

    # Das Gespräch samt Inhalt entfernen (wie der Aufbewahrungslauf es tut).
    with dbmod.SessionLocal() as s:
        AB._gespraech_entfernen(s, gespraech)
        s.commit()

    with dbmod.SessionLocal() as s:
        assert AB._glocken_verwaist_loeschen(s) >= 1
        s.commit()
    assert _glocken(SAENGER2) == [], "die Umfrage-Glocke blieb verwaist stehen"
    # Und die Nachrichtenzeilen sind wirklich weg (Kontrolle der Vorbereitung).
    with dbmod.SessionLocal() as s:
        assert s.query(ChatNachricht).filter_by(gespraech=gespraech).count() == 0


def test_buendel_glocke_traegt_nach_teilweisem_lesen_die_neue_zahl(welt, gespraech):
    """CHAT-4b (b): „3 neue“ → nach dem Lesen bis zur ersten „2 neue“ SOFORT."""
    from diakronos_app.api import chat as C

    _teilnahme(gespraech, SAENGER2)
    erste = None
    for text in ("Eins", "Zwei", "Drei"):
        _set_user(SAENGER)
        antwort = C.senden(gespraech, text)
        _reset()
        if erste is None:
            erste = antwort["name"]
    from diakronos_app.models.chat import ChatNachricht

    with dbmod.SessionLocal() as s:
        neueste_am = (s.query(ChatNachricht).filter_by(gespraech=gespraech)
                      .order_by(ChatNachricht.erstellt_am.desc()).first().erstellt_am)

    assert C.chat_glocken_buendeln(jetzt=neueste_am + timedelta(minutes=10),
                                   ruhe=5) == 1
    glocke = _glocken(SAENGER2, GLOCKE_GESPRAECH)[0]
    assert glocke.subject == "Chor: 3 neue Nachrichten"

    # Bis zur ERSTEN Nachricht lesen → 2 bleiben ungelesen. Die Ruhezeit ist
    # abgelaufen (``_glocke_ruhe_vorbei`` misst an der echten Wandzeit, der Job
    # oben rechnete mit ``neueste_am + 10 min``) — dafür werden die Nachrichten
    # auf die Wandzeit zurückdatiert, sonst stünde die Zahl bis zum nächsten
    # echten Joblauf.
    _altere_nachrichten(gespraech, minutes=30)
    _set_user(SAENGER2)
    antwort = C.lesestand_setzen(gespraech, erste)
    _reset()
    assert antwort["ungelesen"] == 2

    glocke = _glocken(SAENGER2, GLOCKE_GESPRAECH)[0]
    assert glocke.read is False
    assert glocke.subject == "Chor: 2 neue Nachrichten", (
        "die Zahl der Bündel-Glocke folgt nicht dem Lesestand")

    # Und der nächste Joblauf ändert nichts mehr an der Zahl (kein Rückfall).
    C.chat_glocken_buendeln(jetzt=neueste_am + timedelta(minutes=20), ruhe=5)
    assert _glocken(SAENGER2, GLOCKE_GESPRAECH)[0].subject == "Chor: 2 neue Nachrichten"


def _frisches_gespraech() -> str:
    """Das Chor-Gespräch auf einen leeren Verlauf zurücksetzen.

    Die Test-Datenbank ist EINE SQLite-Datei für die ganze Testdatei, und je
    (Art, Einheit) gibt es GENAU EIN Gespräch (Unique-Index) — ein „neues“
    Gespräch derselben Gruppe lässt sich also nicht anlegen. Stattdessen wird
    der Verlauf dieses Gesprächs geleert: Nachrichten, Lesestände, Merker und
    Glocken weg, Teilnahme-Zeilen bleiben (sie tragen den Beitritt).
    """
    from diakronos_app.models.chat import (
        ChatGespraech,
        ChatGlocke,
        ChatNachricht,
        ChatTeilnehmer,
    )
    from diakronos_app.models.core import NotificationLog

    with dbmod.SessionLocal() as s:
        g = s.query(ChatGespraech).filter_by(gruppe="Chor").first()
        kennung = g.name
        s.query(NotificationLog).filter(
            NotificationLog.document_name == kennung).delete()
        s.query(ChatNachricht).filter_by(gespraech=kennung).delete()
        s.query(ChatGlocke).filter_by(gespraech=kennung).delete()
        for t in s.query(ChatTeilnehmer).filter_by(gespraech=kennung).all():
            t.letzter_lesestand = None
            t.letzter_lesestand_nachricht = None
            t.stumm = False
        s.commit()
    return kennung


def _beitritt_zurueckdatieren(gespraech: str, minutes: int = 60) -> None:
    """``hinzugefuegt_am`` aller Teilnahme-Zeilen nach hinten schieben.

    Nach ``_frisches_gespraech`` ist der Beitritt „jetzt“; zurückdatierte
    Nachrichten lägen dann VOR dem Beitritt und zählten als nicht neu. Eine
    Stunde reicht: die Tests legen ihre Nachrichten danach mit ``minutes=30``
    weiter zurück (``_altere_nachrichten``).
    """
    from diakronos_app.api import chat as C
    from diakronos_app.models.chat import ChatTeilnehmer

    frueher = C._jetzt() - timedelta(minutes=minutes)
    with dbmod.SessionLocal() as s:
        for t in s.query(ChatTeilnehmer).filter_by(gespraech=gespraech).all():
            t.hinzugefuegt_am = frueher
        s.commit()


def _altere_nachrichten(gespraech: str, minutes: int = 30) -> None:
    """Nachrichten (und Teilnahme-Zeilen) auf ``jetzt - minutes`` zurückdatieren.

    Die Ruhezeit der Bündel-Glocke (``GLOCKE_RUHE_MINUTEN``) wird an der echten
    Wandzeit gemessen; Tests, die den Zustand „Gespräch ist ruhig“ brauchen,
    ohne eine halbe Stunde zu warten, stellen ihn so her. ``hinzugefuegt_am``
    der Teilnahme geht mit zurück — sonst läge der Beitritt NACH den
    Nachrichten und der Anker (``_glocke_anker``) ließe sie „nicht neu“ sein.
    """
    from diakronos_app.api import chat as C
    from diakronos_app.models.chat import ChatNachricht, ChatTeilnehmer

    frueher = C._jetzt() - timedelta(minutes=minutes)
    with dbmod.SessionLocal() as s:
        # Jede Nachricht eine Sekunde weiter — gleiche Zeitstempel würden die
        # „nach dem Lesestand“-Vergleiche (``>``) unbrauchbar machen. Sortiert
        # wird nach der BISHERIGEN Zeit (die Namensordnung ist nicht die
        # Reihenfolge), damit die Verlaufsfolge erhalten bleibt.
        zeilen = sorted(
            s.query(ChatNachricht).filter_by(gespraech=gespraech).all(),
            key=lambda x: (x.erstellt_am, x.name))
        for i, n in enumerate(zeilen):
            n.erstellt_am = frueher + timedelta(seconds=i)
        for t in s.query(ChatTeilnehmer).filter_by(gespraech=gespraech).all():
            if t.hinzugefuegt_am is not None:
                # Eine Sekunde VOR den Nachrichten: ``_ungelesen_zaehlen``
                # vergleicht ``erstellt_am > stand``.
                t.hinzugefuegt_am = frueher - timedelta(seconds=1)
        s.commit()


def test_nachziehen_legt_keine_neue_glocke_an_wenn_weggeklickt(welt, gespraech):
    """Review R1/4: die Zahl wird nur an einer BESTEHENDEN ungelesenen Zeile geführt.

    Wurde die Glocke gelesen (weggeklickt) und danach ein älterer Lesestand
    gesetzt, entsteht KEINE neue Glocke — nur der Job darf wieder glocken.
    """
    from diakronos_app.api import chat as C

    # Leerer Verlauf: die Test-Datenbank ist EINE SQLite-Datei für die ganze
    # Datei — Nachrichten früherer Tests würden die Zählung verfälschen.
    gespraech = _frisches_gespraech()
    _teilnahme(gespraech, SAENGER2)
    erste = None
    for text in ("Eins", "Zwei", "Drei"):
        _set_user(SAENGER)
        antwort = C.senden(gespraech, text)
        _reset()
        if erste is None:
            erste = antwort["name"]
    _altere_nachrichten(gespraech)
    C.chat_glocken_buendeln(jetzt=C._jetzt(), ruhe=5)
    assert len(_glocken(SAENGER2, GLOCKE_GESPRAECH)) == 1

    # Wegklicken: alles gelesen ⇒ die Glocke ist ``read``.
    _set_user(SAENGER2)
    C.lesestand_setzen(gespraech)
    _reset()
    assert _glocken(SAENGER2, GLOCKE_GESPRAECH)[0].read is True

    # Jetzt einen ÄLTEREN Lesestand setzen: es bleibt etwas ungelesen, aber
    # die Glocke ist weggeklickt — es darf KEINE neue entstehen.
    _set_user(SAENGER2)
    antwort = C.lesestand_setzen(gespraech, erste)
    _reset()
    assert antwort["ungelesen"] == 2
    glocken = _glocken(SAENGER2, GLOCKE_GESPRAECH)
    assert len(glocken) == 1, "Restpunkt b hat eine neue Glocke angelegt"
    assert glocken[0].read is True
    assert glocken[0].subject == "Chor: 3 neue Nachrichten"


def test_nachziehen_bei_stumm_aendert_nichts(welt, gespraech):
    """Review R1/4: stumm = keine Glocke — auch das Nachziehen nicht."""
    from diakronos_app.api import chat as C

    gespraech = _frisches_gespraech()
    _teilnahme(gespraech, SAENGER2)
    erste = None
    for text in ("Eins", "Zwei", "Drei"):
        _set_user(SAENGER)
        antwort = C.senden(gespraech, text)
        _reset()
        if erste is None:
            erste = antwort["name"]
    _altere_nachrichten(gespraech)
    C.chat_glocken_buendeln(jetzt=C._jetzt(), ruhe=5)
    vorher = _glocken(SAENGER2, GLOCKE_GESPRAECH)[0].subject
    assert vorher == "Chor: 3 neue Nachrichten"

    _set_user(SAENGER2)
    C.stumm_setzen(gespraech, True)
    antwort = C.lesestand_setzen(gespraech, erste)
    _reset()
    assert antwort["ungelesen"] == 2
    assert _glocken(SAENGER2, GLOCKE_GESPRAECH)[0].subject == vorher, (
        "stumm: die Bündel-Glocke wurde trotzdem fortgeschrieben")


def test_nachziehen_innerhalb_der_ruhezeit_aendert_nichts(welt, gespraech):
    """Review R1/4: die Ruhezeit wird nicht umgangen (der Job glockt dann auch nicht)."""
    from diakronos_app.api import chat as C

    gespraech = _frisches_gespraech()
    _teilnahme(gespraech, SAENGER2)
    erste = None
    for text in ("Eins", "Zwei"):
        _set_user(SAENGER)
        antwort = C.senden(gespraech, text)
        _reset()
        if erste is None:
            erste = antwort["name"]
    _altere_nachrichten(gespraech)
    C.chat_glocken_buendeln(jetzt=C._jetzt(), ruhe=5)
    assert _glocken(SAENGER2, GLOCKE_GESPRAECH)[0].subject == "Chor: 2 neue Nachrichten"

    # Neue Nachricht ⇒ Gespräch ist NICHT mehr ruhig; Lesestand auf die erste
    # ⇒ „Zwei“ und „Drei“ bleiben ungelesen, aber die Glocke folgt erst beim
    # nächsten Joblauf.
    _set_user(SAENGER)
    C.senden(gespraech, "Drei")
    _reset()
    _set_user(SAENGER2)
    antwort = C.lesestand_setzen(gespraech, erste)
    _reset()
    assert antwort["ungelesen"] == 2
    assert _glocken(SAENGER2, GLOCKE_GESPRAECH)[0].subject == "Chor: 2 neue Nachrichten", (
        "die Ruhezeit wurde beim Nachziehen umgangen")


# ── Scheduler ───────────────────────────────────────────────────────────────


def test_scheduler_registriert_die_erinnerung_als_minutenjob():
    from diakronos_app import scheduler

    ids = {job_id for _, _, job_id in scheduler.MINUTEN_JOBS}
    assert "chat_umfrage_erinnerungen" in ids
    jobs = {job.id: job for job in scheduler.build_scheduler().get_jobs()}
    assert "chat_umfrage_erinnerungen" in jobs
    assert jobs["chat_umfrage_erinnerungen"].trigger.__class__.__name__ == "IntervalTrigger"


def test_job_wrapper_ruft_die_fachfunktion(welt, monkeypatch):
    from diakronos_app import scheduler
    from diakronos_app.api import chat as C

    aufgerufen: list[int] = []
    monkeypatch.setattr(C, "chat_umfrage_erinnerungen",
                        lambda *a, **k: aufgerufen.append(1) or 0)
    scheduler.job_chat_umfrage_erinnerungen()
    assert aufgerufen == [1]


def test_job_wrapper_schluckt_fehler(monkeypatch):
    from diakronos_app import scheduler
    from diakronos_app.api import chat as C

    def kaputt(*a, **k):
        raise RuntimeError("boom")

    monkeypatch.setattr(C, "chat_umfrage_erinnerungen", kaputt)
    scheduler.job_chat_umfrage_erinnerungen()  # darf nicht werfen


def test_job_naht_ist_nicht_per_http_erreichbar():
    """Review R1/1: die Job-Naht ist KEIN Endpunkt (wie ``chat_glocken_buendeln``).

    Der Rumpf nimmt ``jetzt``/``vorlauf`` an und SCHLIESST fällige Umfragen —
    über HTTP könnte jeder Angemeldete ``jetzt=2099-01-01`` schicken und alle
    befristeten Umfragen schließen. Deshalb steht sie nicht im Register.
    """
    from diakronos_app.frappe_compat.registry import lookup

    assert lookup("diakronos.diakronos.api.chat.chat_umfrage_erinnerungen") is None
    assert lookup("diakronos.diakonos.api.chat.chat_umfrage_erinnerungen") is None
    # Und der Ausnahme-Eintrag im SEC-11-Inventar ist gestrichen.
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "whitelist_inventar", str(BACKEND.parent / "tools" / "whitelist_inventar.py"))
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    assert "diakronos_app.api.chat.chat_umfrage_erinnerungen" not in modul.AUSNAHMEN
    assert "diakronos_app.api.chat.chat_umfrage_erinnerungen" not in modul.AUSNAHME_ART


# ── Migration ───────────────────────────────────────────────────────────────


def _skripte() -> ScriptDirectory:
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "alembic"))
    return ScriptDirectory.from_config(cfg)


def test_genau_ein_kopf_und_chat4b_haengt_hinter_chat7a():
    """Die Kette hat EINEN Kopf; unser Schritt sitzt dahinter — ohne festen Namen."""
    skripte = _skripte()
    koepfe = skripte.get_heads()
    assert len(koepfe) == 1, f"mehrere Köpfe: {koepfe}"
    revision = skripte.get_revision("chat4b_umfrage_erinnerung")
    assert revision is not None
    assert revision.down_revision == "chat7a_direkt"
    # Der Schritt ist vom Kopf aus erreichbar (er ist der Kopf oder davor).
    assert "chat4b_umfrage_erinnerung" in {
        r.revision for r in skripte.walk_revisions()}


def test_migration_upgrade_downgrade_upgrade(tmp_path):
    """Spalte anlegen, entfernen, wieder anlegen — gegen eine frische SQLite-Datei.

    Eine DATEI statt ``:memory:``: Alembic prüft den Stand in einer eigenen
    Verbindung; ein In-Memory-Schema wäre für ``upgrade`` nicht da (und die URL
    mit ``%``-Zeichen verträgt die Alembic-Config nicht).
    """
    import sqlalchemy as sa
    from alembic import command
    from alembic.runtime.migration import MigrationContext

    datei = tmp_path / "chat4b_test.db"
    eng = create_engine(f"sqlite+pysqlite:///{datei}", future=True)
    # ``alembic/env.py`` liest die URL aus ``settings`` (DATABASE_URL), NICHT aus
    # der Config — hier wird die Einstellung auf die Wegwerf-DATEI gesetzt
    # (sonst liefe der Lauf gegen die in der Umgebung eingestellte URL).
    from diakronos_app import settings as settings_mod

    vorher = settings_mod.settings.database_url
    settings_mod.settings.database_url = f"sqlite+pysqlite:///{datei}"
    try:
        with eng.begin() as conn:
            conn.execute(sa.text("CREATE TABLE chat_umfrage (name VARCHAR(140) "
                                 "PRIMARY KEY, gespraech VARCHAR(140) NOT NULL, "
                                 "frage TEXT NOT NULL)"))
        cfg = Config(str(BACKEND / "alembic.ini"))
        cfg.set_main_option("script_location", str(BACKEND / "alembic"))
        cfg.set_main_option("sqlalchemy.url", f"sqlite+pysqlite:///{datei}")
        with eng.begin() as conn:
            MigrationContext.configure(conn).stamp(_skripte(), "chat7a_direkt")

        command.upgrade(cfg, "chat4b_umfrage_erinnerung")
        with eng.connect() as conn:
            spalten = {c["name"] for c in sa.inspect(conn).get_columns("chat_umfrage")}
        assert "erinnert_am" in spalten

        command.downgrade(cfg, "chat7a_direkt")
        with eng.connect() as conn:
            spalten = {c["name"] for c in sa.inspect(conn).get_columns("chat_umfrage")}
        assert "erinnert_am" not in spalten

        command.upgrade(cfg, "chat4b_umfrage_erinnerung")
        with eng.connect() as conn:
            spalten = {c["name"] for c in sa.inspect(conn).get_columns("chat_umfrage")}
        assert "erinnert_am" in spalten
    finally:
        settings_mod.settings.database_url = vorher
        eng.dispose()
