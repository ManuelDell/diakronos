"""BUG-T1 — „Nächste Termine“ einer Gruppe war leer, obwohl der Kalender sie zeigt.

Befund (Manuel, 17.11., Dev-Modus devecg): Untergruppe „Gemeinschaftsteam“
(Untergruppe von „Jugendkreis“) -> Seite „#/gruppe/<id>“ -> Karte „Nächste
Termine“ zeigt „Keine bevorstehenden Termine“. Dieselben Termine stehen im
Kalender.

Ursache: `get_gruppe_termine` (api/gruppen.py) siebte `Element` mit
``filters={"gruppe": gruppe_id}``. `Element.gruppe` ist ein Feld, das KEIN
Schreibweg dieser App setzt — `create_event`, `create_series`, `save_event`,
`update_event` nehmen es nicht an, die Oberfläche (`KronosEventCreate.vue`)
schickt es nicht. Auf jedem regulär angelegten Termin ist es leer, also war die
Liste IMMER leer (`dienstplan.py` dokumentiert dasselbe Feld als „auf
Bestandsterminen leer“).

Der Test legt seine Welt über die ECHTEN Endpunkte an (`create_event`) — kein
direkt geschriebenes `Element.gruppe`, sonst prüfte er genau den Fehler nicht,
den der Befund beschreibt. Geprüft wird über HTTP:

  1. Untergruppe: der Termin im Kalender der UNTERGRUPPE erscheint in ihrer
     Terminliste (vor dem Fix rot: `gruppe` ist NULL).
  2. Untergruppe: der Termin im Kalender der HAUPTGRUPPE erscheint ebenfalls —
     dieselbe Zuordnung wie „+ Termin“ (`kalenderDerGruppe`).
  3. Gruppe (Hauptgruppe): der Termin in ihrem Kalender erscheint in ihrer
     Terminliste.
  4. Kein Durchsickern: der Kalender einer FREMDEN Gruppe (nicht sichtbar)
     und ein gelöschter Termin (Papierkorb) kommen nicht vor.
  5. Serientermine: `create_series` legt je Vorkommen ein Element an
     (UXK-R7) — die Vorkommen im Fenster erscheinen einzeln.
  6. `Element.gruppe` zählt weiterhin: ein Termin mit gesetztem Feld in einem
     Kalender OHNE Seitenzuordnung erscheint (Alternative bleibt gültig).

     TERMIN-GRUPPE (17.11.): `Element.gruppe` wird inzwischen beim Schreiben aus
     dem Kalender gesetzt und trägt bei Untergruppen-Kalendern die HAUPTgruppe.
     Deshalb gilt diese Alternative nur noch für Seiten OHNE eigenen Kalender —
     sonst stünde der Termin des Untergruppen-Kalenders auch auf der
     Hauptgruppen-Seite (Test `test_gruppe_zeigt_keinen_termine_der_untergruppe`).
     Fall 7 („F1“) prüft das bereits so; hier bleibt alles unverändert.

Alle Testdaten liegen über dem MCK-Endpunkt an, damit der Test nicht von
internem Schreibverhalten abhängt, das sich ändern darf.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from diakronos_app.frappe_compat.session import set_user

GRUPPEN = "diakronos.diakonos.api.gruppen"
EVENT_CRUD = "diakronos.kronos.api.event_crud"

GL = "bugt1-gl@example.org"
HV = "bugt1-hv@example.org"
FREMD = "bugt1-fremd@example.org"


def _in_tagen(tage: int, stunde: int = 18) -> datetime:
    """Termin in der Zukunft — am Kalendertag der Gemeinde gedacht."""
    from diakronos_app.zeit import heute_gemeinde

    return datetime.combine(heute_gemeinde() + timedelta(days=tage), datetime.min.time()).replace(
        hour=stunde
    )


@pytest.fixture()
def welt(patched_db, fake_redis):
    """Jugendkreis (Hauptgruppe) + Gemeinschaftsteam (Untergruppe) + Fremd.

    Rechte im EINEN Rechtesystem: HV des Jugendkreises, GL des
    Gemeinschaftsteams (zugleich Mitglied der Hauptgruppe, wie im Befund),
    dazu eine unberührte Fremdgruppe. Kalender: je einer für Haupt- und
    Untergruppe, einer für die Fremdgruppe.
    """
    from diakronos_app.models.core import User
    from diakronos_app.models.diakonos import (
        Gruppe,
        Gruppenmitgliedschaft,
        Mitglied,
        Untergruppe,
        Untergruppenmitgliedschaft,
    )
    from diakronos_app.models.kronos import Kalender
    from diakronos_app.models.rechte import (
        RechteFreigabe,
        RechteGruppenrolle,
        RechteModul,
        RechteObjekt,
    )

    sess = patched_db()
    sess.add_all([
        User(name=GL, email=GL, full_name="Gela Leitung", enabled=1),
        User(name=HV, email=HV, full_name="Hanno Verantwortlich", enabled=1),
        User(name=FREMD, email=FREMD, full_name="Frieda Fremd", enabled=1),
        Mitglied(name="MIT-GL", vorname="Gela", nachname="Leitung", email=GL, user=GL,
                 status="Mitglied"),
    ])
    sess.add_all([
        Gruppe(name="GRU-JK", gruppenname="Jugendkreis", status="Aktiv", docstatus=0, idx=0),
        Gruppe(name="GRU-XX", gruppenname="Fremdgruppe", status="Aktiv", docstatus=0, idx=0),
        Untergruppe(name="UG-GT", untergruppenname="Gemeinschaftsteam", gruppe="GRU-JK",
                    status="Aktiv", docstatus=0, idx=0),
    ])
    # Befund: die GL ist Mitglied der HAUPTgruppe (und der Untergruppe).
    sess.add_all([
        Gruppenmitgliedschaft(name="GM-GL", parent="GRU-JK", parenttype="Gruppe",
                              parentfield="mitglieder", mitglied="MIT-GL", rolle="Mitglied",
                              status="Aktiv", docstatus=0, idx=0),
        Untergruppenmitgliedschaft(name="UM-GL", parent="UG-GT", parenttype="Untergruppe",
                                   parentfield="mitglieder", mitglied="MIT-GL",
                                   rolle="Mitglied", status="Aktiv", docstatus=0, idx=0),
        # HV der Hauptgruppe, GL der Untergruppe — wer darf, sieht beides.
        RechteGruppenrolle(gruppe="GRU-JK", benutzer=HV, rolle="HV"),
        RechteGruppenrolle(gruppe="GRU-JK", benutzer=GL, rolle="MV"),
        RechteGruppenrolle(gruppe="GRU-JK", untergruppe="UG-GT", benutzer=GL, rolle="GL"),
        RechteModul(gruppe="GRU-JK", modul="kalender"),
        # Der HV darf im fremden Kalender LESEN und SCHREIBEN (Einzelfreigabe) —
        # nur so kann der Test beweisen, dass dessen Termine trotzdem NICHT in
        # der Liste der Hauptgruppe stehen (Zuordnung, nicht Sichtbarkeit).
        RechteFreigabe(typ="kalender", objekt="KAL-XX", benutzer=HV, lesen=True,
                       schreiben=True),
    ])
    sess.add_all([
        Kalender(name="KAL-JK", calendar_name="Jugendkreis", selbstverwaltet=0,
                 docstatus=0, idx=0),
        Kalender(name="KAL-GT", calendar_name="Gemeinschaftsteam", selbstverwaltet=0,
                 docstatus=0, idx=0),
        Kalender(name="KAL-XX", calendar_name="Fremdgruppe", selbstverwaltet=0,
                 docstatus=0, idx=0),
        # TERMIN-GRUPPE (Review 18.11.): Kalender OHNE Gruppenzuordnung — die
        # Heimat echter Alt-/Importdaten. Nur hier greift die Ersatzregel
        # `Element.gruppe` noch (bei gruppengebundenen Kalendern entscheidet
        # die Kalenderzuordnung).
        Kalender(name="KAL-ALT", calendar_name="Altbestand", selbstverwaltet=0,
                 docstatus=0, idx=0),
        # Zuordnung wie „+ Termin“ sie liest (`RechteObjekt`).
        RechteObjekt(typ="kalender", objekt="KAL-JK", gruppe="GRU-JK"),
        RechteObjekt(typ="kalender", objekt="KAL-GT", gruppe="GRU-JK", untergruppe="UG-GT"),
        RechteObjekt(typ="kalender", objekt="KAL-XX", gruppe="GRU-XX"),
        RechteObjekt(typ="kalender", objekt="KAL-ALT"),
        RechteModul(gruppe="GRU-XX", modul="kalender"),
    ])
    sess.commit()
    yield sess
    sess.close()


@pytest.fixture()
def als_gl(welt):
    set_user(GL)
    yield GL
    set_user("Administrator")


@pytest.fixture()
def als_hv(welt):
    set_user(HV)
    yield HV
    set_user("Administrator")


def _termin(client, kalender: str, titel: str, tage: int, dauer_h: int = 2) -> str:
    """Termin über den echten Endpunkt anlegen (kein `Element.gruppe` im Spiel)."""
    start = _in_tagen(tage)
    antwort = client.post(
        f"/api/method/{EVENT_CRUD}.create_event",
        json={
            "element_name": titel,
            "element_start": start.strftime("%Y-%m-%d %H:%M:%S"),
            "element_end": (start + timedelta(hours=dauer_h)).strftime("%Y-%m-%d %H:%M:%S"),
            "all_day": 0,
            "element_calendar": kalender,
            "ressource": None,
            "description": None,
            "element_category": None,
            "ignore_conflict": 0,
            "zusaetzliche_ressourcen": "[]",
        },
    )
    assert antwort.status_code == 200, antwort.text
    kennung = antwort.json()["message"]["id"]
    assert kennung
    return kennung


def _termine(client, gruppe_id: str) -> list[dict]:
    antwort = client.get(f"/api/method/{GRUPPEN}.get_gruppe_termine",
                         params={"gruppe_id": gruppe_id})
    assert antwort.status_code == 200, antwort.text
    return antwort.json()["message"]["termine"]


def _kennungen(termine: list[dict]) -> list[str]:
    return [t["name"] for t in termine]


# ── 1 · Untergruppen-Kalender ───────────────────────────────────────────────


def test_untergruppe_zeigt_termin_aus_ihrem_kalender(client, als_gl, welt):
    """Der Kern des Befunds: Termin im Kalender der Untergruppe fehlte."""
    kennung = _termin(client, "KAL-GT", "Teamabend", 3)
    treffer = _kennungen(_termine(client, "UG-GT"))
    assert kennung in treffer, (
        "Termin aus dem Kalender der Untergruppe steht nicht in „Nächste Termine“ "
        f"({treffer}) — genau der Befund"
    )


# ── 2 · Kalender der Hauptgruppe zählt für die Untergruppe ──────────────────


def test_untergruppe_zeigt_termine_der_hauptgruppe(client, als_gl, welt):
    """Dieselbe Zuordnung wie „+ Termin“ (`kalenderDerGruppe`)."""
    kennung = _termin(client, "KAL-JK", "Jugendtreff", 4)
    treffer = _kennungen(_termine(client, "UG-GT"))
    assert kennung in treffer, (
        f"Termin aus dem Kalender der Hauptgruppe fehlt bei der Untergruppe ({treffer})"
    )


# ── 3 · Hauptgruppe ─────────────────────────────────────────────────────────


def test_gruppe_zeigt_termin_aus_ihrem_kalender(client, als_hv, welt):
    kennung = _termin(client, "KAL-JK", "Jugendtreff", 5)
    treffer = _kennungen(_termine(client, "GRU-JK"))
    assert kennung in treffer, (
        f"Termin aus dem Kalender der Gruppe fehlt in ihrer Terminliste ({treffer})"
    )


def test_gruppe_zeigt_keinen_termine_der_untergruppe(client, als_hv, welt):
    """Der Untergruppen-Termin ist kein Termin der Hauptgruppe."""
    kennung = _termin(client, "KAL-GT", "Teamabend", 6)
    treffer = _kennungen(_termine(client, "GRU-JK"))
    assert kennung not in treffer, (
        "Termin des Untergruppen-Kalenders steht in der Liste der Hauptgruppe — "
        "die Zuordnung ist zu weit"
    )


# ── 4 · Kein Durchsickern ───────────────────────────────────────────────────


def test_fremder_kalender_und_papierkorb_bleiben_draussen(client, als_hv, welt):
    fremd = _termin(client, "KAL-XX", "Fremdtermin", 7)
    weg = _termin(client, "KAL-JK", "Wird geloescht", 8)

    from diakronos_app import papierkorb

    papierkorb.loeschen("Element", weg, von="Administrator")

    treffer = _kennungen(_termine(client, "GRU-JK"))
    assert fremd not in treffer, "Termin eines fremden Kalenders ist durchgesickert"
    assert weg not in treffer, "gelöschter Termin steht noch in der Terminliste"


# ── 5 · Serien: Vorkommen statt nur Stammtermin ─────────────────────────────


def test_serie_erscheint_mit_ihren_vorkommen(client, als_hv, welt):
    """`create_series` legt je Vorkommen ein Element an (UXK-R7)."""
    start = _in_tagen(2)
    antwort = client.post(
        f"/api/method/{EVENT_CRUD}.create_series",
        json={
            "element_name": "Wöchentlicher Treff",
            "element_start": start.strftime("%Y-%m-%d %H:%M:%S"),
            "element_end": (start + timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S"),
            "element_calendar": "KAL-JK",
            "repeat_type": "weekly",
            "series_end": (start + timedelta(days=20)).strftime("%Y-%m-%d"),
            "all_day": 0,
            "zusaetzliche_ressourcen": "[]",
        },
    )
    assert antwort.status_code == 200, antwort.text
    angelegt = antwort.json()["message"]["created_ids"]
    assert len(angelegt) >= 3, angelegt

    treffer = _kennungen(_termine(client, "GRU-JK"))
    # Die ersten beiden Vorkommen liegen im 60-Tage-Fenster und kommen einzeln.
    assert set(angelegt[:2]) <= set(treffer), (
        f"Serienvorkommen fehlen einzeln in der Terminliste ({treffer})"
    )


# ── 6 · `Element.gruppe` bleibt gültig ──────────────────────────────────────


def test_termin_mit_gruppenfeld_zaehlt_ohne_seitenkalender(client, welt):
    """`Element.gruppe` bleibt gültig, wenn der KALENDER keine Gruppe hat.

    Alt-/Importdaten tragen das Feld. Eine Gruppe OHNE zugeordneten Kalender
    (hier eine frisch angelegte) findet ihren Termin dann über das Feld — der
    Termin liegt dafür in einem Kalender OHNE Gruppenzuordnung (`KAL-ALT`),
    genau die Lage, für die die Ersatzregel gedacht ist (Review 18.11.).
    """
    from diakronos_app.frappe_compat.session import set_user
    from diakronos_app.models.diakonos import Gruppe
    from diakronos_app.models.kronos import Element

    set_user("Administrator")  # legt im fremden Kalender an und sieht die Gruppe

    sess = welt
    sess.add(Gruppe(name="GRU-OHNE", gruppenname="Ohne Kalender", status="Aktiv",
                    docstatus=0, idx=0))
    sess.commit()

    kennung = _termin(client, "KAL-ALT", "Importierter Gruppentermin", 9)
    # `KAL-ALT` hat KEINE Gruppenzuordnung; erst das Feld macht den Termin zum
    # Termin der Gruppe ohne Kalender (so wie ein Alt-/Importdatensatz aussieht).
    zeile = sess.get(Element, kennung)
    assert zeile is not None
    zeile.gruppe = "GRU-OHNE"
    sess.commit()

    treffer = _kennungen(_termine(client, "GRU-OHNE"))
    assert kennung in treffer, (
        "Termin mit ausdrücklichem `Element.gruppe` fehlt — die Alternative ist verloren"
    )


# ── 7 · Review F1 ───────────────────────────────────────────────────────────


def test_gruppenfeld_zieht_keinen_fremdtermin_mit(client, welt):
    """Review F1: `Element.gruppe` ist eine Alternative — kein Kalender-Griff.

    Kalender OHNE Gruppenzuordnung, in dem ein Termin mit `gruppe=<Seite>` und
    ein FREMDER Termin ohne Feld liegen. Nur der markierte darf erscheinen; der
    fremde Termin desselben Kalenders nicht. (Termine in einem Kalender MIT
    Gruppenzuordnung entscheidet ohnehin die Kalenderzuordnung — Review 18.11.)
    """
    from diakronos_app.frappe_compat.session import set_user
    from diakronos_app.models.diakonos import Gruppe
    from diakronos_app.models.kronos import Element

    set_user("Administrator")

    sess = welt
    sess.add(Gruppe(name="GRU-OHNE", gruppenname="Ohne Kalender", status="Aktiv",
                    docstatus=0, idx=0))
    sess.commit()

    markiert = _termin(client, "KAL-ALT", "Importierter Gruppentermin", 9)
    fremd = _termin(client, "KAL-ALT", "Fremder Termin im selben Kalender", 10)
    zeile = sess.get(Element, markiert)
    assert zeile is not None
    zeile.gruppe = "GRU-OHNE"
    sess.commit()

    treffer = _kennungen(_termine(client, "GRU-OHNE"))
    assert markiert in treffer, f"markierter Termin fehlt ({treffer})"
    assert fremd not in treffer, (
        "Review F1: ein Termin ohne `Element.gruppe` aus demselben Kalender ist "
        "mitgekommen — die Alternative greift auf den ganzen Kalender zu"
    )


# ── 8 · Review F2: Gesamtsortierung ─────────────────────────────────────────


def test_termine_sind_nach_start_sortiert(client, als_gl, welt):
    """Review F2: die Liste ist EINE sortierte Liste, nicht zwei Blöcke.

    Gemischte Kalender (`KAL-GT` der Untergruppe, `KAL-JK` der Hauptgruppe),
    absichtlich in umgekehrter Reihenfolge angelegt (spät zuerst). Der Endpunkt
    holt zwei Blöcke (`_hole(mod_kalender)` dann `_hole(regulaer)`) und darf
    sie nicht einfach aneinanderhängen: die Oberfläche nimmt die ersten vier
    (`GruppeDetail.vue:1063`), ein später Termin dürfte einen frühen nicht
    verdrängen.

    Hinweis zur Grenze des Tests: für EINEN Benutzer sind auf einer Seite beide
    Kalender gleich moderiert (Rollen-Moderation greift für Gruppe und
    Untergruppe gemeinsam, `pruefstufen` im Rechte-Kern), die Blöcke laufen hier
    also nicht auseinander. Der Test sichert die geforderte Eigenschaft trotzdem
    ab — er bricht, sobald die Rücksortierung fehlt und die Blöcke ungeordnet
    aneinandergehängt werden (z. B. bei künftig unterschiedlicher Moderation).
    """
    spaet = _termin(client, "KAL-GT", "Spaeter Termin", 30)
    frueh = _termin(client, "KAL-JK", "Frueher Termin", 1)

    liste = _termine(client, "UG-GT")
    kennungen = _kennungen(liste)
    assert frueh in kennungen and spaet in kennungen, (
        f"Beide Termine müssen in der Liste stehen ({kennungen})"
    )
    daten = [x["start"] for x in liste if x["start"]]
    assert daten == sorted(daten), f"Terminliste ist nicht nach Start sortiert: {daten}"
    assert kennungen.index(frueh) < kennungen.index(spaet), (
        "Review F2: der spätere Termin steht vor dem früheren (Blöcke ungeordnet)"
    )


# ── 9 · Review F3: Untergruppe ohne ermittelte Hauptgruppe ──────────────────


def test_untergruppe_ohne_hauptgruppe_behaelt_ihren_kalender(welt):
    """Review F3: `hauptgruppe == ""` darf die Seite nicht zum Gruppenzweig machen.

    Die Seite einer Untergruppe, deren Hauptgruppe nicht ermittelt werden kann
    (Altbestand, verwaister Verweis), verlor ihren EIGENEN Untergruppen-Kalender:
    die Prüfung hing an ``if hauptgruppe`` statt an der Art der Seite.

    Der Fall wird am Helfer ``_kalender_der_seite`` selbst geprüft — über HTTP
    ist er nicht herstellbar, weil das Rechte-Gate (`_rechte.darf`) dieselbe
    Untergruppen-Zeile liest und ohne Hauptgruppe mit 403 abweist (fail closed,
    unverändert und richtig).
    """
    from diakronos_app.api.gruppen import _kalender_der_seite

    kalender_info = [
        {"name": "KAL-GT", "gruppe": "GRU-JK", "untergruppe": "UG-GT"},
        {"name": "KAL-JK", "gruppe": "GRU-JK", "untergruppe": None},
        {"name": "KAL-XX", "gruppe": "GRU-XX", "untergruppe": None},
    ]
    seite = _kalender_der_seite(
        "UG-GT", "", kalender_info=kalender_info, ist_untergruppe=True
    )
    assert "KAL-GT" in seite, (
        "Review F3: der eigene Untergruppen-Kalender geht verloren, wenn die "
        f"Hauptgruppe nicht ermittelt werden kann ({sorted(seite)})"
    )
    assert "KAL-XX" not in seite, "fremder Kalender ist auf die Seite gekommen"


def test_untergruppe_ohne_hauptgruppe_zieht_keine_gemeindekalender() -> None:
    """Review Runde 2: unbekannte Hauptgruppe darf nicht auf Gemeinde-Kalender (gruppe leer) passen."""
    from diakronos_app.api.gruppen import _kalender_der_seite

    info = [
        {"name": "KAL-GEMEINDE", "gruppe": None, "untergruppe": None},
        {"name": "KAL-UG", "gruppe": "GRU-X", "untergruppe": "UG-1"},
    ]
    namen = _kalender_der_seite("UG-1", hauptgruppe="", ist_untergruppe=True, kalender_info=info)
    assert namen == {"KAL-UG"}
