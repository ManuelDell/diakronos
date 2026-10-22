"""BF1 — Befunde aus Manuels Live-Test vom 15.10.2026.

Reproduktions-Tests zu den Funktionsfehlern aus dem Live-Test. Jeder Test
beschreibt zuerst den beobachteten Fehler (der Test war vorher rot) und
danach die belegte Ursache/Behebung.

Prioritaet 1:

A) KALENDER — „Termin anlegen speichert nicht“
   Beobachtung: Ein neuer Termin (Status „Vorschlag“) wurde angelegt, aber
   weder im Kalender (Lesemodus zeigt nur „Festgelegt“) noch in der
   Moderation sichtbar. Fuer den Moderator-Kalender muss der Vorschlag in
   der Moderation auftauchen und `create_event` muss den angelegten Termin
   benennen (id + status), damit die SPA eine ehrliche Erfolgsmeldung
   zeigen und auf die Moderation verweisen kann.

C) KALENDER Tagesansicht — „Keine Termine an diesem Tag“, obwohl der Tag
   Termine hat
   Beobachtung: Im Monatsraster stehen am 2.10. vier Termine, das
   Tages-Popup meldet „Keine Termine an diesem Tag.“
   Ursache: Das Tagesfenster war `element_start >= Tag 00:00 UND
   element_end <= Tag 23:59`. Jeder Termin, der den Tag nur *beruehrt*
   (mehrtägige Termine wie eine Freizeit, ganztägig oder ueber Mitternacht)
   fiel heraus, obwohl ihn das Monatsraster anzeigt.
   Ein Kalendertag enthaelt jeden Termin mit `element_start <= Tag 23:59`
   UND `element_end >= Tag 00:00`.

E) GRUPPEN — Mitglieder hinzufuegen
   Beobachtung: Die Auswahl war ein Freitextfeld (Mitglieds-ID musste
   bekannt sein), kein Dropdown.
   Ursache: Fuer die Auswahlliste braucht der Gruppenverantwortliche eine
   Mitgliederliste (Name, ggf. E-Mail, keine Adressdaten). Die
   Rechtepruefung liess bisher nur Admins und das eigene Profil zu.
"""
from __future__ import annotations

from datetime import datetime

import pytest

from diakronos_app.frappe_compat.session import set_user
from diakronos_app.models.kronos import Element

import diakronos_app.api  # noqa: E402,F401

# Fixtures/Seed der Kronos-Kern-Tests wiederverwenden (eine Kalenderwelt).
from test_p4b_kronos_kern import kalenderwelt  # noqa: E402,F401

# Der Plan-Rahmen bringt ein eigenes HTTP-Fixture mit (eigener engine-Aufbau
# optional auf Wegwerf-PostgreSQL). Wird hier mitgenutzt, statt ihn zu doppeln.
from test_planrahmen_api import engine  # noqa: E402,F401

PFAD = "/api/method/diakronos.kronos.api."


def aufruf(client, name, **daten):
    r = client.post(PFAD + name, json=daten)
    assert r.status_code == 200, r.text
    return r.json()["message"]


# ── A) Termin anlegen: Vorschlag landet in der Moderation ──────────────────


def test_a_neuer_termin_ist_in_der_moderation_und_wird_benannt(client, kalenderwelt):
    """A: Anlegen eines Termins — Erfolg muss ehrlich gemeldet und der
    Termin muss in der Moderation des Kalenders auffindbar sein."""
    set_user("admin-kal@example.org")

    antwort = aufruf(client, "event_crud.create_event",
                     element_name="Testtermin 27. Okt",
                     element_start="2026-10-27 18:00",
                     element_end="2026-10-27 19:00",
                     element_calendar="KAL-PUB",
                     all_day=0,
                     zusaetzliche_ressourcen="[]")

    # Der Endpunkt benennt den angelegten Termin (id) und seinen Status
    # (Vorschlag) — damit die SPA verlaesslich melden und verweisen kann.
    assert antwort["success"] is True
    assert antwort["id"]
    assert antwort["status"] == "Vorschlag"

    # Der neue Termin steht wirklich in der Datenbank.
    zeile = kalenderwelt.get(Element, antwort["id"])
    assert zeile is not None
    assert zeile.element_name == "Testtermin 27. Okt"
    assert zeile.element_calendar == "KAL-PUB"
    assert zeile.status == "Vorschlag"

    # Und er taucht in der Moderation dieses Kalenders auf (der Moderationsweg
    # ist der einzige Weg, auf dem ein Vorschlag sichtbar wird).
    brett = aufruf(client, "kanban_api.get_kanban_board_data")
    ids = {e["id"] for e in brett["vorschlaege"]}
    assert antwort["id"] in ids, "Neuer Vorschlag fehlt in der Terminmoderation."


def test_a_lesemodus_zeigt_vorschlag_nicht_aber_bearbeitungsmodus_schon(client, kalenderwelt):
    """A: Der Grund fuer „nichts gespeichert“ — der Lesemodus zeigt nur
    „Festgelegt“. Fuer den Kalendermoderator ist der Vorschlag im
    Bearbeitungsmodus da, also nicht verschluckt."""
    set_user("moderator@example.org")
    antwort = aufruf(client, "event_crud.create_event",
                     element_name="Testtermin 27. Okt",
                     element_start="2026-10-27 18:00",
                     element_end="2026-10-27 19:00",
                     element_calendar="KAL-PUB",
                     all_day=0, zusaetzliche_ressourcen="[]")

    lesen = aufruf(client, "calendar_get.get_calendar_events",
                   start_date="2026-10-01", end_date="2026-10-31",
                   calendar_filter='["KAL-PUB"]', view_mode="view")
    assert antwort["id"] not in {e["id"] for e in lesen}

    # Die SPA sendet die Modus-Woerter "view"/"edit" — "edit" muss
    # Bearbeitungsmodus heissen, sonst sieht der Moderator den Vorschlag nie.
    bearbeiten = aufruf(client, "calendar_get.get_calendar_events",
                        start_date="2026-10-01", end_date="2026-10-31",
                        calendar_filter='["KAL-PUB"]', view_mode="edit")
    assert antwort["id"] in {e["id"] for e in bearbeiten}


@pytest.mark.parametrize("wort, erwartet_view", [
    ("view", True), ("edit", False), ("false", False), ("true", True),
])
def test_a_view_mode_wort_wird_richtig_ausgelegt(kalenderwelt, wort, erwartet_view):
    """A: `view_mode` kommt als Wort aus der SPA. `edit` != `view`."""
    from diakronos_app.api.kronos.calendar_get import _as_bool

    assert _as_bool(wort) is erwartet_view


# ── C) Tagesansicht findet alle Termine des Tages ──────────────────────────


@pytest.fixture()
def tagwelt(kalenderwelt):
    """Termine rund um den 2.10.2026: mehrtägig, ganztägig, ueber Mitternacht."""
    sess = kalenderwelt
    sess.add_all([
        # Mehrtägige Freizeit: beginnt am 2.10., endet am 4.10.
        Element(name="EL-FREIZEIT", element_name="Freizeit", element_calendar="KAL-PUB",
                element_start=datetime(2026, 10, 2, 12, 0),
                element_end=datetime(2026, 10, 4, 10, 0),
                all_day=True, status="Festgelegt", docstatus=0, idx=0),
        # Ganztägig an genau dem Tag.
        Element(name="EL-GANZ", element_name="Feiertag", element_calendar="KAL-PUB",
                element_start=datetime(2026, 10, 2, 0, 0),
                element_end=datetime(2026, 10, 3, 0, 0),
                all_day=True, status="Festgelegt", docstatus=0, idx=0),
        # Serientermin (Einzelzeile einer Serie) an genau dem Tag.
        Element(name="EL-SERIE", element_name="Bibelstunde", element_calendar="KAL-PUB",
                element_start=datetime(2026, 10, 2, 18, 0),
                element_end=datetime(2026, 10, 2, 19, 0),
                all_day=False, status="Festgelegt", series_id="SER-9",
                repeat_this_event=True, docstatus=0, idx=0),
        # Normaler eintägiger Termin.
        Element(name="EL-EIN", element_name="Kinderstunde", element_calendar="KAL-PUB",
                element_start=datetime(2026, 10, 2, 15, 0),
                element_end=datetime(2026, 10, 2, 16, 0),
                all_day=False, status="Festgelegt", docstatus=0, idx=0),
        # Termin am Folgetag — darf NICHT im 2.10. erscheinen.
        Element(name="EL-FOLGE", element_name="Chorprobe", element_calendar="KAL-PUB",
                element_start=datetime(2026, 10, 3, 18, 0),
                element_end=datetime(2026, 10, 3, 19, 0),
                all_day=False, status="Festgelegt", docstatus=0, idx=0),
    ])
    sess.commit()
    return sess


def test_c_tagesabfrage_findet_alle_termine_des_tages(client, tagwelt):
    """C: Der Tagesaufruf (start=end=2.10.) liefert jeden Termin, den das
    Monatsraster an diesem Tag zeigt — auch mehrtägige/ganztägige/Serien."""
    set_user("admin-kal@example.org")
    tag = aufruf(client, "calendar_get.get_calendar_events",
                 start_date="2026-10-02", end_date="2026-10-02",
                 calendar_filter='["KAL-PUB"]')
    ids = {e["id"] for e in tag}
    assert {"EL-FREIZEIT", "EL-GANZ", "EL-SERIE", "EL-EIN"} <= ids, \
        f"Termine des Tages fehlen im Tagesaufruf: {sorted(ids)}"
    assert "EL-FOLGE" not in ids, "Termin des Folgetags gehoert nicht in den 2.10."


def test_c_tagesabfrage_akzeptiert_vollen_iso_zeitstempel(client, tagwelt):
    """C: Der Tagesdialog schickt `dateStr` aus dem Kalender — ein voller
    ISO-Zeitstempel (`2026-10-02T00:00:00`). Frueher scheiterte der Aufruf
    daran (417) und der Dialog meldete „Keine Termine an diesem Tag“. Die
    Zeitspanne muss denselben Bestand liefern wie das reine Datum."""
    set_user("admin-kal@example.org")
    mit_zeit = aufruf(client, "calendar_get.get_calendar_events",
                      start_date="2026-10-02T00:00:00",
                      end_date="2026-10-02T00:00:00",
                      calendar_filter='["KAL-PUB"]')
    ids = {e["id"] for e in mit_zeit}
    assert {"EL-FREIZEIT", "EL-GANZ", "EL-SERIE", "EL-EIN"} <= ids, \
        f"Voller Zeitstempel liefert die Termine des Tages nicht: {sorted(ids)}"


def test_c_tagesabfrage_stimmt_mit_dem_monatsraster_ueberein(client, tagwelt):
    """C: Widerspruch aus dem Live-Test — was das Raster am Tag zeigt, zeigt
    das Tages-Popup ebenso (eine Wahrheit)."""
    set_user("admin-kal@example.org")
    raster = aufruf(client, "calendar_get.get_calendar_events",
                    start_date="2026-09-28", end_date="2026-11-08",
                    calendar_filter='["KAL-PUB"]')
    im_raster = {
        e["id"] for e in raster
        if str(e["start"])[:10] <= "2026-10-02" <= str(e["end"] or e["start"])[:10]
    }
    tag = aufruf(client, "calendar_get.get_calendar_events",
                 start_date="2026-10-02", end_date="2026-10-02",
                 calendar_filter='["KAL-PUB"]')
    assert im_raster == {e["id"] for e in tag}


def test_c_mehrtagiger_termin_am_letzten_tag(client, tagwelt):
    """C: Auch der letzte Tag eines mehrtägigen Termins (4.10.) findet ihn."""
    set_user("admin-kal@example.org")
    tag = aufruf(client, "calendar_get.get_calendar_events",
                 start_date="2026-10-04", end_date="2026-10-04",
                 calendar_filter='["KAL-PUB"]')
    assert "EL-FREIZEIT" in {e["id"] for e in tag}


# ── E) Gruppenverantwortliche duerfen die Mitgliederliste sehen ────────────
#
# Eigene Welt: eine Gruppe mit Verantwortlichem, mehrere Mitglieder.
# Der Verantwortliche ist NICHT Admin und NICHT das jeweilige Mitglied.


@pytest.fixture()
def gruppenwelt(patched_db, seed_mitglieder):
    from diakronos_app.models.core import HasRole, User
    from diakronos_app.models.diakonos import Gruppe, GruppeVerantwortlicher, Gruppenmitgliedschaft

    sess = patched_db()
    sess.add_all([
        User(name="leiter@example.org", email="leiter@example.org",
             full_name="Leiter", enabled=True),
        HasRole(name="HR-L", parent="leiter@example.org", parenttype="User",
                parentfield="roles", role="Mitglied", docstatus=0, idx=1),
    ])
    sess.add(Gruppe(name="GRP-CHOR", gruppenname="Chor", ancestor_path="/GRP-CHOR"))
    sess.flush()
    sess.add_all([
        Gruppenmitgliedschaft(name="GM-1", parent="GRP-CHOR", parenttype="Gruppe",
                              parentfield="mitglieder", mitglied="M-0001",
                              status="Aktiv", docstatus=0, idx=1),
        GruppeVerantwortlicher(name="GV-1", parent="GRP-CHOR", parenttype="Gruppe",
                               parentfield="verantwortliche", user="leiter@example.org",
                               docstatus=0, idx=1),
    ])
    sess.commit()
    return sess


GRUPPEN_PFAD = "/api/method/diakronos.diakonos.api.gruppen."


def gruppen_aufruf(client, name, **daten):
    r = client.post(GRUPPEN_PFAD + name, json=daten)
    assert r.status_code == 200, r.text
    return r.json()["message"]


def test_e_gruppenleiter_sieht_mitgliederliste(client, gruppenwelt):
    """E/B-1: Ein Gruppenverantwortlicher darf die Auswahlliste sehen — aber
    NUR Name und interne ID, KEINE E-Mail, KEIN Status, keine Adressdaten.

    Die E-Mail ist ein Adressbuch-Feld (`adressbuch_sichtbarkeit`, Regel B2);
    die Verwalterrolle ist keine Freigabe. Vorher lieferte der Endpunkt sie
    ungemaskt an jeden Gruppenleiter (Befund B-1)."""
    set_user("leiter@example.org")
    liste = gruppen_aufruf(client, "get_gruppe_mitglieder_auswahl", gruppe_id="GRP-CHOR")

    assert isinstance(liste, list) and liste, "Auswahlliste ist leer."
    eintrag = next(e for e in liste if e["mitglied"] == "M-0001")
    assert eintrag["name"] == "Anna Beispiel"
    # B-1: E-Mail und Status duerfen NICHT geliefert werden.
    assert "email" not in eintrag, f"E-Mail leckt in die Auswahlliste: {eintrag!r}"
    assert "status" not in eintrag, f"Status leckt in die Auswahlliste: {eintrag!r}"
    for verboten in ("straße", "strasse", "postleitzahl", "wohnort", "geburtstag",
                     "telefonnummer", "adressbuch_sichtbarkeit", "email", "status"):
        assert verboten not in eintrag, f"Feld {verboten!r} in der Auswahlliste."


def test_e_auswahlliste_felder_genau_mitglied_name_in_gruppe(client, gruppenwelt):
    """B-1: Die Auswahlliste hat GENAU die drei Felder `mitglied`, `name`,
    `in_gruppe` — kein viertes Feld kann unbemerkt dazukommen."""
    set_user("leiter@example.org")
    liste = gruppen_aufruf(client, "get_gruppe_mitglieder_auswahl", gruppe_id="GRP-CHOR")
    assert liste, "Auswahlliste ist leer."
    for eintrag in liste:
        assert set(eintrag) == {"mitglied", "name", "in_gruppe"}, \
            f"Unerwartete Felder in der Auswahl: {sorted(eintrag)}"


def test_e_suche_trifft_nicht_die_email(client, gruppenwelt):
    """B-1: Die E-Mail ist KEIN Suchfeld dieser Auswahl. Eine Suche nach dem
    E-Mail-Anfang darf die Person nicht ueber ihr Adressbuchfeld auffinden —
    sonst waere die Suche ein Seitenkanal genau auf das Feld, das
    `get_mitglieder_liste` abschneidet."""
    set_user("leiter@example.org")
    liste = gruppen_aufruf(client, "get_gruppe_mitglieder_auswahl",
                           gruppe_id="GRP-CHOR", suche="anna@example.org")
    assert all(e["mitglied"] != "M-0001" for e in liste), \
        "E-Mail-Suche findet die Person — Seitenkanal auf ein Adressbuchfeld."


def test_e_gruppenleiter_sieht_auch_nicht_gruppenmitglieder(client, gruppenwelt):
    """E: Die Liste umfasst ALLE waehlbaren Mitglieder (nicht nur die der
    Gruppe), damit ein neues Mitglied auswählbar ist.

    B-1: Ausgetretene (hier M-0003, `status='Ausgetreten'`) sind KEINE
    sinnvolle Auswahl zum Aufnehmen — sie fehlen bewusst."""
    set_user("leiter@example.org")
    liste = gruppen_aufruf(client, "get_gruppe_mitglieder_auswahl", gruppe_id="GRP-CHOR")
    ids = {e["mitglied"] for e in liste}
    assert {"M-0001", "M-0002"} <= ids, f"Liste unvollstaendig: {sorted(ids)}"
    assert "M-0003" not in ids, "Ausgetretenes Mitglied wird zum Aufnehmen angeboten."


def test_e_liste_schneidet_nicht_bei_50_ab(client, patched_db):
    """B-2: Eine Gemeinde mit mehr als 50 Mitgliedern muss jede Person
    auswaehlen koennen. Vorher brach die Liste bei 50 ab (Default `limit`),
    und die SPA filterte nur lokal in diesen 50 — „Zacharias“ war nie
    auswaehlbar. Jetzt liefert der Aufruf ohne `limit` ALLE."""
    from diakronos_app.models.core import HasRole, User
    from diakronos_app.models.diakonos import Gruppe, GruppeVerantwortlicher, Mitglied

    sess = patched_db()
    sess.add(User(name="leiter50@example.org", email="leiter50@example.org",
                  full_name="Leiter 50", enabled=True))
    sess.add(HasRole(name="HR-L50", parent="leiter50@example.org", parenttype="User",
                     parentfield="roles", role="Mitglied", docstatus=0, idx=1))
    sess.add(Gruppe(name="GRP-50", gruppenname="Gross", ancestor_path="/GRP-50"))
    sess.flush()
    sess.add(GruppeVerantwortlicher(name="GV-50", parent="GRP-50", parenttype="Gruppe",
                                    parentfield="verantwortliche", user="leiter50@example.org",
                                    docstatus=0, idx=1))
    sess.add_all([
        Mitglied(name=f"M-{i:04d}", vorname=f"Person{i:02d}", nachname=f"Nachname{i:02d}",
                 email=f"p{i}@example.org", status="Mitglied", docstatus=0, idx=i)
        for i in range(1, 74)
    ])
    sess.commit()

    set_user("leiter50@example.org")
    liste = gruppen_aufruf(client, "get_gruppe_mitglieder_auswahl", gruppe_id="GRP-50")
    assert len(liste) == 73, f"Nicht alle Mitglieder geliefert: {len(liste)}"
    ids = {e["mitglied"] for e in liste}
    assert "M-0073" in ids, "Das 73. Mitglied fehlt — Liste ist abgeschnitten."


def test_e_suche_filtert_serverseitig_und_umlautunabhaengig(client, patched_db):
    """B-2/J: Das Tippen filtert ueber den Server; die Suche beachtet Umlaute
    und Gross-/Kleinschreibung nicht. Damit findet die 73. Person, ohne dass
    die SPA alle Eintraege lokal halten muss."""
    from diakronos_app.models.core import HasRole, User
    from diakronos_app.models.diakonos import Gruppe, GruppeVerantwortlicher, Mitglied

    sess = patched_db()
    sess.add(User(name="ls@example.org", email="ls@example.org",
                  full_name="LS", enabled=True))
    sess.add(HasRole(name="HR-LS", parent="ls@example.org", parenttype="User",
                     parentfield="roles", role="Mitglied", docstatus=0, idx=1))
    sess.add(Gruppe(name="GRP-S", gruppenname="Suchgruppe", ancestor_path="/GRP-S"))
    sess.flush()
    sess.add(GruppeVerantwortlicher(name="GV-S", parent="GRP-S", parenttype="Gruppe",
                                    parentfield="verantwortliche", user="ls@example.org",
                                    docstatus=0, idx=1))
    sess.add_all([
        Mitglied(name="M-ZAC", vorname="Zacharias", nachname="Müller",
                 email="zacharias@example.org", status="Mitglied", docstatus=0, idx=1),
        Mitglied(name="M-AND", vorname="Andrea", nachname="Schmidt",
                 email="andrea@example.org", status="Mitglied", docstatus=0, idx=2),
    ])
    sess.commit()

    set_user("ls@example.org")
    for begriff in ("zacharias", "ZACHARIAS", "mueller", "MÜLLER", "müller"):
        treffer = gruppen_aufruf(client, "get_gruppe_mitglieder_auswahl",
                                 gruppe_id="GRP-S", suche=begriff)
        assert {e["mitglied"] for e in treffer} == {"M-ZAC"}, \
            f"Suche {begriff!r} fand Zacharias Müller nicht: {treffer}"


def test_e_fremder_sieht_keine_mitgliederliste(client, gruppenwelt):
    """E: Wer die Gruppe nicht verantwortet, bekommt keine Liste (fail closed)."""
    set_user("mitglied-a@example.org")
    r = client.post(GRUPPEN_PFAD + "get_gruppe_mitglieder_auswahl",
                    json={"gruppe_id": "GRP-CHOR"})
    assert r.status_code == 403, r.text


# ── B) Plan veroeffentlichen ────────────────────────────────────────────────
#
# Der Plan-Rahmen hat ein eigenes HTTP-Fixture (`test_planrahmen_api`), das
# denselben `client` benutzt. Hier der vollstaendige Weg ueber einen
# Kochbuch-Plantyp bis zum veroeffentlichten Stand — genau der Weg, der im
# Live-Test „funktioniert nicht“ gemeldet wurde.

PLAN_PFAD = "/api/method/diakronos.planrahmen.api."


def plan_aufruf(client, name, **daten):
    r = client.post(PLAN_PFAD + name, json=daten)
    assert r.status_code == 200, r.text
    return r.json()["message"]


@pytest.mark.parametrize("plantyp", ["chorplan", "freizeit", "musikteams", "programm"])
def test_b_kochbuch_plantyp_laesst_sich_veroeffentlichen(client, patched_db, plantyp):
    """B: Veröffentlichen eines Plans mit einem Kochbuch-Plantyp.

    Der Weg ist: Plantyp speichern -> Plan anlegen -> generieren ->
    veroeffentlichen. Der veroeffentlichte Stand muss danach da sein, der
    Status „veroeffentlicht“ lauten und ein Diff liefern (nicht stumm
    scheitern)."""
    from diakronos_app.planrahmen.ressourcen import kochbuch_laden

    # Der Kochbuch-Plantyp traegt einen Bereich (Chor/Freizeit/Musik) — der
    # muss in den Stammdaten existieren.
    from diakronos_app.models.diakonos import Dienstbereich

    definition = kochbuch_laden(plantyp)
    bereich = definition.get("bereich")
    with patched_db.begin() as s:
        if bereich and s.get(Dienstbereich, bereich) is None:
            s.add(Dienstbereich(name=bereich))
    plan_aufruf(client, "plantyp_speichern", definition=definition, gueltig_ab="2026-01-01")

    parameter = {}
    if plantyp == "freizeit":
        parameter = {"zeitraum": ["2026-10-01", "2026-10-03"], "thema": "Freude"}
    p = plan_aufruf(client, "plan_anlegen", plantyp=plantyp, titel="BF1-Test",
                    von="2026-01-01", bis="2026-12-31", parameter=parameter)
    plan_aufruf(client, "plan_generieren", plan=p["id"])

    erg = plan_aufruf(client, "veroeffentlichen", plan=p["id"])
    assert "diff" in erg, f"veroeffentlichen lieferte kein Diff: {erg!r}"

    # BF1-B: Beim ERSTEN Veroeffentlichen ist nichts vorher da — der Diff muss
    # die BELEGTEN Werte trotzdem melden (vorher `vorher: null`). Sonst meldet
    # die SPA „0 Änderungen öffentlich“ und der Planer sieht „nichts passiert“,
    # obwohl der Stand geschrieben wurde.
    # K1: Leere Plaetze (`nachher: null`) sind KEINE Änderung; sie tauchen im
    # Diff nicht mehr auf. Geprueft wird daher gegen die belegten Eintrage.
    eintraege = plan_aufruf(client, "plan_holen", plan=p["id"])["eintraege"]
    belegt = [e for e in eintraege if e.get("wert")]
    assert len(erg["diff"]) == len(belegt), \
        f"Erstveroeffentlichung meldet {len(erg['diff'])} statt {len(belegt)} Änderungen."
    assert erg["erstveroeffentlichung"] is True
    assert all(d["neu"] for d in erg["diff"])
    assert all(d["nachher"] is not None for d in erg["diff"]), \
        "Leerer Platz darf nicht als Änderung gemeldet werden (K1)."

    stand = plan_aufruf(client, "plan_holen", plan=p["id"])
    assert stand["plan"]["status"] == "veroeffentlicht"

    # Der veroeffentlichte Stand ist im Speicher wirklich angelegt.
    from diakronos_app.models.planrahmen import Plan

    with patched_db.begin() as s:
        zeile = s.get(Plan, p["id"])
        assert zeile.veroeffentlichter_stand is not None, "Kein veroeffentlichter Stand gespeichert."
        assert zeile.veroeffentlichter_stand["plan"]["status"] == "veroeffentlicht"


def test_b_veroeffentlichen_ohne_plan_meldet_verstaendlich(client, patched_db):
    """B: Ein unbekannter Plan darf nicht stumm bleiben — der Aufruf endet
    mit einer Fehlerantwort (403/404/417), die die SPA anzeigen kann."""
    r = client.post(PLAN_PFAD + "veroeffentlichen", json={"plan": "gibt-es-nicht"})
    assert r.status_code in (403, 404, 417), r.text
    assert r.json().get("message")


def test_b_zweite_veroeffentlichung_meldet_wert_aenderung(client, patched_db):
    """B: Nach dem ersten Veroeffentlichen meldet die naechste
    Veroeffentlichung GENAU die geaenderte Zeile (nicht 0)."""
    from diakronos_app.models.diakonos import Dienstbereich
    from diakronos_app.planrahmen.ressourcen import kochbuch_laden

    with patched_db.begin() as s:
        s.add(Dienstbereich(name="Chor"))
    # Personenpool der Vorlage: Gruppe "Chor" mit einem aktiven Mitglied.
    from diakronos_app.models.core import User
    from diakronos_app.models.diakonos import Gruppe, Gruppenmitgliedschaft, Mitglied

    with patched_db.begin() as s:
        s.add(User(name="bf1u", email="bf1u@example.org", full_name="BF1 U", enabled=True))
        s.add(Gruppe(name="Chor", gruppenname="Chor"))
        s.flush()
        s.add(Mitglied(name="BF1P", user="bf1u", email="bf1u@example.org",
                       vorname="BF1", nachname="Person"))
        s.add(Gruppenmitgliedschaft(name="BF1GM", parent="Chor", parenttype="Gruppe",
                                    parentfield="mitglieder", mitglied="BF1P",
                                    status="Aktiv"))
    definition = kochbuch_laden("chorplan")
    definition["gruppen"] = ["Chor"]
    plan_aufruf(client, "plantyp_speichern", definition=definition, gueltig_ab="2026-01-01")
    p = plan_aufruf(client, "plan_anlegen", plantyp="chorplan", titel="B2",
                    von="2026-01-01", bis="2026-12-31")
    plan_aufruf(client, "plan_generieren", plan=p["id"])
    plan_aufruf(client, "veroeffentlichen", plan=p["id"])

    stand = plan_aufruf(client, "plan_holen", plan=p["id"])
    ziel = next(e for e in stand["eintraege"] if e["feld_pfad"] == "einsingen")
    plan_aufruf(client, "merkmale_pflegen", plantyp="chorplan",
                werte=[{"ziel": "person", "schluessel": "einsingen",
                        "ziel_id": "BF1P", "wert": True}])

    plan_aufruf(client, "eintrag_setzen", plan=p["id"], termin=ziel["termin"],
                feld_pfad="einsingen", wert="BF1P")

    erg = plan_aufruf(client, "veroeffentlichen", plan=p["id"])
    assert erg["erstveroeffentlichung"] is False
    aenderungen = [d for d in erg["diff"] if d["feld_pfad"] == "einsingen"
                   and d["termin"] == ziel["termin"]]
    assert len(aenderungen) == 1, f"Wertaenderung fehlt im Diff: {erg['diff'][:3]}"
    assert aenderungen[0]["nachher"] == "BF1P"


# ── J) Mitglieder-/Adressbuch-Suche ignoriert Gross-/Kleinschreibung ────────
#
# Beobachtung aus dem Live-Test: „Suche beachtet Gross-/Kleinschreibung“.
# Ursache: Die Liste benutzte `LIKE`, das in PostgreSQL case-sensitiv ist
# (SQLite waere zufaellig tolerant). Jetzt `LOWER(...) LIKE LOWER(...)`.
# Der Test laeuft auf SQLite und prueft die Normalisierung, die der Server
# seit BF1-J anwendet — vorher lieferte die Abfrage mit anderer Schreibweise
# keine Treffer.


@pytest.fixture()
def suchwelt(patched_db):
    """Admin (System Manager) + Mitglieder mit Grossbuchstaben und Umlauten."""
    from diakronos_app.models.core import HasRole, User
    from diakronos_app.models.diakonos import Mitglied

    sess = patched_db()
    sess.add(User(name="bf1-admin@example.org", email="bf1-admin@example.org",
                  full_name="BF1 Admin", enabled=True))
    sess.add(HasRole(name="HR-bf1-admin", parent="bf1-admin@example.org",
                     parenttype="User", parentfield="roles", role="System Manager",
                     docstatus=0, idx=0))
    sess.add_all([
        Mitglied(name="M-J1", vorname="Anna", nachname="MÜLLER",
                 email="Anna.Mueller@example.org", status="Mitglied",
                 ancestor_path="/M-J1", docstatus=0, idx=0),
        Mitglied(name="M-J2", vorname="Jörg", nachname="Weiß",
                 email="joerg@example.org", status="Mitglied",
                 ancestor_path="/M-J2", docstatus=0, idx=0),
    ])
    sess.commit()
    return sess


def _liste_suche(client, suche):
    r = client.get("/api/method/mitglieder.get_mitglieder_liste",
                   params={"limit": 50, "suche": suche})
    assert r.status_code == 200, r.text
    return r.json()["message"]["data"]


@pytest.mark.parametrize("suche", ["müller", "MÜLLER", "Mueller", "mueller", "ANNA"])
def test_j_mitgliedersuche_ignoriert_schreibweise(client, suchwelt, suche):
    """J: dieselbe Person wird unabhaengig von der getippten Schreibweise
    und Umlautform gefunden."""
    set_user("bf1-admin@example.org")
    treffer = _liste_suche(client, suche)
    assert any(z["name"] == "M-J1" for z in treffer), \
        f"Suche {suche!r} fand Anna Müller nicht: {[z['name'] for z in treffer]}"


def test_j_suche_findet_umlaut_gegen_ersatzschreibweise(client, suchwelt):
    """J: „weiss“ findet „Weiß“ und umgekehrt."""
    set_user("bf1-admin@example.org")
    assert any(z["name"] == "M-J2" for z in _liste_suche(client, "weiss"))
    assert any(z["name"] == "M-J2" for z in _liste_suche(client, "WEISS"))


def test_j_suche_ueber_email_unabhaengig_von_schreibweise(client, suchwelt):
    """J: auch die E-Mail-Suche (Admin) beachtet die Schreibweise nicht."""
    set_user("bf1-admin@example.org")
    assert any(z["name"] == "M-J1" for z in _liste_suche(client, "anna.mueller@"))
    assert any(z["name"] == "M-J1" for z in _liste_suche(client, "ANNA.MUELLER@"))

