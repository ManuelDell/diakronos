"""Tests fuer die Demo-Daten „Musterhausen“ (PUB-2).

Die Tests laufen auf einer FRISCHEN In-Memory-SQLite (``Base.metadata.create_all``,
also der volle Modellstand) und pruefen:

* das Skript laeuft auf einer leeren Datenbank durch und legt die erwarteten
  Datensaetze an,
* ein zweiter Lauf ist idempotent (nichts neu, nichts doppelt),
* das Skript verweigert eine Datenbank, die schon Mitglieder enthaelt,
* die Demo-Daten verraten nichts: keine echten Namen, keine internen
  Adressen, keine Zugangsdaten ausser den beiden Demo-Konten,
* der Plan-Rahmen bekommt echte Plantypen und Plaene aus dem Kochbuch.

Bewusst OHNE ``TestClient``: das Skript schreibt ueber dieselben Funktionen wie
die Endpunkte, braucht aber keine HTTP-Sitzung. Die Datenbank-Patches
(``SessionLocal``/``engine``) kommen aus ``patched_db`` (siehe ``conftest``).
"""

from __future__ import annotations

import importlib
import re
from datetime import date

import pytest
from sqlalchemy import select, text

#: Fester Referenztag — die Tests duerfen nicht vom Kalender abhaengen.
STICHTAG = date(2026, 11, 2)

#: Form der von der App vergebenen Mitglied-Kennung (ID-1d).
KENNUNG = re.compile(r"^[0-9a-f]{8}-[0-9a-f]$")


@pytest.fixture()
def demo(patched_db):
    """Laedt das Demo-Modul gegen die Testdatenbank (ohne Redis/HTTP)."""
    modul = importlib.import_module("musterhausen")
    # Der Anleger oeffnet die Sitzung selbst ueber `diakronos_app.db.SessionLocal`;
    # `patched_db` zeigt sie auf die Test-Engine.
    yield modul
def _anzahl(session, tabelle: str) -> int:
    return session.execute(text(f'SELECT count(*) FROM "{tabelle}"')).scalar_one()


def test_demo_legt_gemeinde_an(engine, session_factory, demo):
    """Ein Lauf auf leerer Datenbank legt die erwarteten Datensaetze an."""
    bericht = demo.anlegen(stichtag=STICHTAG)
    assert "neu" in bericht

    from diakronos_app.models.diakonos import Dienstbereich, Gruppe, Mitglied
    from diakronos_app.models.kronos import Kalender, Ressource
    from diakronos_app.models.psalmos import Lied
    from diakronos_app.models.planrahmen import Plan, Plantyp

    with session_factory() as s:
        # ID-1d: Die Kennung vergibt der Server — gesucht wird ueber den Namen.
        assert s.scalar(select(Mitglied.name).where(
            Mitglied.vorname == "Anna", Mitglied.nachname == "Beispiel"))
        assert _anzahl(s, "mitglied") >= 40
        assert _anzahl(s, "gruppe") >= 6
        assert _anzahl(s, "kalender") == 3
        assert _anzahl(s, "lied") >= 20
        assert _anzahl(s, "element") >= 10          # Gottesdienste + Feste
        assert _anzahl(s, "ressource") >= 5
        assert s.scalar(select(Dienstbereich.name).where(Dienstbereich.name == "musik"))
        assert s.scalar(select(Plan.id).limit(1)) is not None
        assert s.scalar(select(Plantyp.schluessel).where(
            Plantyp.schluessel == "gottesdienstablauf"))
        # Die Gemeinde steht in den Einstellungen.
        assert s.execute(text(
            'SELECT organisationsname FROM diakronos_einstellungen'
        )).scalar_one() == "Evangelische Gemeinde Musterhausen"


def test_demo_ist_idempotent(engine, session_factory, demo):
    """Zweiter Lauf legt nichts doppelt an.

    „Idempotent“ heisst Nachziehen, nicht Neuaufsetzen: das Skript fuellt nur
    eine LEERE Datenbank (Betriebsschutz). Es muss also, wenn es nicht darf,
    sauber und begruendet abbrechen, und die vorhandenen Daten duerfen sich
    dabei nicht veraendern.
    """
    demo.anlegen(stichtag=STICHTAG)
    with session_factory() as s:
        vorher = {
            tabelle: _anzahl(s, tabelle)
            for tabelle in ("mitglied", "gruppe", "kalender", "lied", "element",
                            "pr_plan", "pr_plantyp", "gruppenmitgliedschaft",
                            "element_mitarbeiter", "dienstplan", "beitrag",
                            "wiki_artikel", "dashboard_widget")
        }

    with pytest.raises(demo.DemoFehler):
        demo.anlegen(stichtag=STICHTAG)

    with session_factory() as s:
        for tabelle, anzahl in vorher.items():
            assert _anzahl(s, tabelle) == anzahl, f"{tabelle} hat sich geaendert"


def _mit_verwaltungskonto(demo) -> None:
    """Das Verwaltungskonto anlegen — Vorbedingung, nicht Teil des Prueflaufs.

    ``--pruefen`` rollt am Ende alles zurueck. Die App-Funktionen pruefen aber
    VORHER die Identitaet (``planrahmen/rechte.py``: angemeldet und aktiv), und
    die entsteht in einem echten Stack beim Start (Entrypoint). Fuer den
    Prueflauf wird dieses Vorbild genauso hergestellt und festgeschrieben.
    """
    from diakronos_app.db import SessionLocal

    session = SessionLocal()
    try:
        a = demo.Anleger(session)
        demo.konten_anlegen(a)
        demo.einstellungen_anlegen(a)
        a.abschluss()
    finally:
        a.schliessen()
        session.close()


def test_demo_pruefen_ist_wiederholbar(engine, session_factory, demo):
    """``--pruefen`` hinterlaesst keine Spur — auch zweimal hintereinander nicht.

    Der Lauf rollt alles zurueck; ein zweiter Prueflauf muss wieder „leer“
    sehen (sonst haelt der Betriebsschutz die Datenbank fuer belegt).
    """
    _mit_verwaltungskonto(demo)
    demo.anlegen(nur_pruefen=True, stichtag=STICHTAG)
    demo.anlegen(nur_pruefen=True, stichtag=STICHTAG)
    with session_factory() as s:
        assert _anzahl(s, "mitglied") == 0


def test_demo_verweigert_volle_datenbank(engine, session_factory, demo):
    """Eine Datenbank mit Mitgliedern wird NICHT befuellt (Betriebsschutz)."""
    from diakronos_app.models.diakonos import Mitglied

    with session_factory() as s:
        s.add(Mitglied(name="Fremde Person", vorname="Fremde", nachname="Person"))
        s.commit()

    with pytest.raises(demo.DemoFehler):
        demo.anlegen(stichtag=STICHTAG)


def test_demo_pruefen_schreibt_nichts(engine, session_factory, demo):
    """``--pruefen`` rollt alles zurueck."""
    _mit_verwaltungskonto(demo)
    demo.anlegen(nur_pruefen=True, stichtag=STICHTAG)
    with session_factory() as s:
        assert _anzahl(s, "mitglied") == 0


def test_demo_entfernen_raeumt_auf(engine, session_factory, demo):
    """``--entfernen`` laesst eine leere Datenbank zurueck."""
    demo.anlegen(stichtag=STICHTAG)
    demo.entfernen()
    with session_factory() as s:
        for tabelle in ("mitglied", "gruppe", "kalender", "lied", "element",
                        "pr_plan", "pr_plantyp", "dienstplan", "user"):
            assert _anzahl(s, tabelle) == 0, f"{tabelle} ist nicht leer"


def test_demo_daten_sind_erfunden(demo):
    """Die Beispielwerte verraten keine echten Personen und keine Infrastruktur.

    Geprueft wird der QUELLTEXT der Daten (die Werte, die in die Datenbank
    gehen) — nicht das Skript selbst, das Adressformen in Kommentaren nennt.
    """
    daten = demo.daten
    text_alle = "\n".join([
        daten.GEMEINDE,
        daten.ADMIN_EMAIL,
        daten.MITGLIED_EMAIL,
        daten.ORT,
        *[f"{p['vorname']} {p['nachname']}" for p in daten.MITGLIEDER],
        *[l["titel"] for l in daten.LIEDER],
        *[r["name"] for r in daten.RESSOURCEN],
        *[t["titel"] for t in daten.TERMINE_FEST],
        *daten.PREDIGTREIHE,
    ])

    # Keine IP-Adressen irgendwo in den Beispieldaten (privater Adressraum
    # waere ein Hinweis auf die Aufnahme-Umgebung).
    assert not re.search(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", text_alle)
    # Keine internen Hostnamen, Pfade oder Produktnamen von Werkzeugen, die
    # nur im Aufnahme-Rechner existieren.
    for verboten in ("localhost", "internal", ".local", ".lan", "intranet",
                     "infra", "://"):
        assert verboten not in text_alle.lower(), verboten

    # Nur Beispiel-Domains.
    for adresse in re.findall(r"[\w.+-]+@[\w.-]+", text_alle):
        assert adresse.endswith("@example.org") or adresse.endswith("@example.com"), adresse

    # Mitglieder-Mails zeigen auf example.org, Telefonnummern auf 0123.
    for p in daten.MITGLIEDER:
        email = daten.email_von(p["vorname"], p["nachname"])
        assert email.endswith("@example.org")


def test_demo_adressen_und_konten(demo):
    """Adressen, Telefon und Konten folgen dem Muster der Karte."""
    for i, p in enumerate(demo.daten.MITGLIEDER):
        strasse, nummer = demo.daten.strasse_fuer(i)
        assert strasse and nummer.isdigit()
        assert demo.daten.telefon_fuer(i).startswith("0123 456789-")
    assert demo.KONTEN == {
        "admin@example.org": demo.daten.ADMIN_PASSWORT,
        "anna.beispiel@example.org": demo.daten.MITGLIED_PASSWORT,
    }


def test_demo_gottesdienste_ueber_zwei_monate(engine, session_factory, demo):
    """Die Gottesdienste decken den Zeitraum von zwei Monaten ab."""
    from diakronos_app.models.kronos import Element

    demo.anlegen(stichtag=STICHTAG)
    with session_factory() as s:
        starts = [e.element_start for e in s.scalars(
            select(Element).where(Element.element_calendar == "gottesdienste")).all()]
    assert len(starts) >= 8
    assert min(starts).date() >= STICHTAG
    assert max(starts).date() >= STICHTAG.replace(month=STICHTAG.month + 1) if STICHTAG.month < 12 \
        else max(starts).date() >= date(2027, 1, 1)


def test_demo_plantypen_aus_dem_kochbuch(engine, session_factory, demo):
    """Die eingerichteten Plantypen stammen aus dem Kochbuch des Pakets."""
    from diakronos_app.models.planrahmen import Plan, Plantyp, PlantypVersion

    demo.anlegen(stichtag=STICHTAG)
    with session_factory() as s:
        schluessel = set(s.scalars(select(Plantyp.schluessel)).all())
        assert set(demo.daten.PLANTYPEN) <= schluessel
        # Jeder Plantyp hat eine unveraenderliche Version und einen Plan.
        for typ in s.scalars(select(Plantyp)).all():
            assert s.scalar(select(PlantypVersion.id).where(
                PlantypVersion.plantyp == typ.id).limit(1))
            assert s.scalar(select(Plan.id).where(Plan.plantyp == typ.id).limit(1))


def test_demo_kalender_termine_sind_sichtbar_konfiguriert(engine, session_factory, demo):
    """Termine stehen auf „Festgelegt“ und in einem Kalender mit Moderator."""
    from diakronos_app.models.kronos import Element, Kalender, KalenderModerator

    demo.anlegen(stichtag=STICHTAG)
    with session_factory() as s:
        elemente = s.scalars(select(Element)).all()
        assert elemente
        for element in elemente:
            assert element.status == "Festgelegt"
            assert element.element_calendar
        moderatoren = s.scalars(select(KalenderModerator)).all()
        assert {m.parent for m in moderatoren} == {
            k.name for k in s.scalars(select(Kalender)).all()}


# ── Sichtpruefung PUB-2b (B1–B5) ────────────────────────────────────────────
#
# Jeder Test haengt an EINEM Befund der Sichtpruefung. Er war vor der
# Nachbesserung rot und ist die Absicherung dagegen, dass die Demo-Daten
# erneut stumm leer aussehen (Statusfilter 0, Uebersicht leer, Plaene als
# Entwurf).


def _alle_personen(daten) -> list[dict]:
    return list(daten.MITGLIEDER) + list(daten.MITGLIEDER_AUSGETRETEN)


def test_b1_status_nur_aus_der_app(engine, session_factory, demo):
    """B1: Jeder Status ist einer der vier der App — oder durch Austritt entstanden.

    „Aktiv“ gab es nicht: die Mitgliederliste filtert auf die vier Werte aus
    ``api/mitglieder.MITGLIED_STATUS``, alles andere faellt durch und der
    Filter zeigt 0.
    """
    from diakronos_app.api.mitglieder import MITGLIED_STATUS
    from diakronos_app.models.diakonos import Mitglied

    demo.anlegen(stichtag=STICHTAG)
    with session_factory() as s:
        zaehler: dict[str, int] = {}
        for (status,) in s.execute(select(Mitglied.status)).all():
            zaehler[status] = zaehler.get(status, 0) + 1

    erlaubt = set(MITGLIED_STATUS) | {"Ausgetreten"}
    assert set(zaehler) <= erlaubt, f"unbekannte Status: {set(zaehler) - erlaubt}"
    # Realistische Verteilung: ueberwiegend „Mitglied“, aber jeder Filter hat
    # etwas zu zeigen.
    for status in MITGLIED_STATUS:
        assert zaehler.get(status, 0) >= 1, f"Status {status!r} kommt nicht vor"
    assert zaehler["Mitglied"] > sum(n for k, n in zaehler.items() if k != "Mitglied")
    assert zaehler.get("Ausgetreten", 0) >= 1


def test_b1_austritt_geht_ueber_den_echten_weg(engine, session_factory, demo):
    """B1: „Ausgetreten“ traegt die Merkmale des Austritts (Datum, Grund, Vorstatus)."""
    from diakronos_app.models.diakonos import Mitglied

    demo.anlegen(stichtag=STICHTAG)
    with session_factory() as s:
        zeilen = s.scalars(select(Mitglied).where(
            Mitglied.status == "Ausgetreten")).all()
        assert zeilen
        for zeile in zeilen:
            assert zeile.austritt_datum is not None
            assert zeile.austritt_grund
            assert zeile.vor_austritt_status in ("Mitglied", "Gast",
                                                "Passives Mitglied", "Passiver Gast")


def test_b2_verwaltungskonto_hat_ein_mitglied_in_gruppen_und_plaenen(
        engine, session_factory, demo):
    """B2: Das Admin-Konto haengt an einem Mitglied, das mitarbeitet.

    Ohne Zuordnung sagt die Uebersicht „Kein Mitglied“, und Dienstplan/„Meine
    Dienste“ bleiben leer.
    """
    from diakronos_app.models.diakonos import Gruppenmitgliedschaft, Mitglied

    from diakronos_app.models.diakonos import Mitglied

    demo.anlegen(stichtag=STICHTAG)
    with session_factory() as s:
        admin = s.scalar(select(Mitglied).where(Mitglied.user == demo.daten.ADMIN_EMAIL))
        assert admin is not None, "Admin-Konto ist keinem Mitglied zugeordnet"
        # ID-1d: Die Kennung ist die Server-Kennung; der Anzeigename steht in
        # Vor-/Nachname.
        assert KENNUNG.match(admin.name), admin.name
        assert f"{admin.vorname} {admin.nachname}".strip() == demo.daten.ADMIN_PERSON
        assert admin.status == "Mitglied"
        # in mindestens einer Gruppe
        assert s.scalar(select(Gruppenmitgliedschaft.name).where(
            Gruppenmitgliedschaft.mitglied == admin.name).limit(1))
        # in den Plaenen eingeplant (Chorplan: Dirigent oder Einsingen)
        eintraege = s.execute(text(
            "SELECT count(*) FROM pr_eintrag WHERE wert = :p"
        ), {"p": f'"{admin.name}"'}).scalar_one()
        assert eintraege >= 1, "Gemeindeleitung steht in keinem Plan"


def test_b3_uebersicht_hat_kacheln_und_daten(engine, session_factory, demo):
    """B3: Die Uebersicht hat Kacheln, und die Kacheln haben Daten.

    Ohne Zeilen in ``dashboard_widget`` zeigt die Startseite nichts an.
    """
    from diakronos_app.models.diakonos import Beitrag, DashboardWidget, WikiArtikel

    demo.anlegen(stichtag=STICHTAG)
    with session_factory() as s:
        ids = {w.widget_id for w in s.scalars(select(DashboardWidget)).all()}
        sichtbar = [w.widget_id for w in s.scalars(select(DashboardWidget)).all()
                    if w.default_visible]
        assert {"upcoming-events", "my-services", "announcements", "mini-calendar"} <= ids
        assert len(sichtbar) >= 4
        assert s.scalar(select(Beitrag.name).where(Beitrag.veroeffentlicht == 1).limit(1))
        assert s.scalar(select(WikiArtikel.name).limit(1)) is not None


def test_b3_widget_endpunkte_sind_auffindbar(engine, session_factory, demo):
    """B3: Kein Kachel-Zeiger laeuft ins Leere (sonst „Fehler beim Laden“)."""
    from diakronos_app.api.dashboard import FRAPPE_MODULE
    from diakronos_app.frappe_compat.registry import lookup
    from diakronos_app.models.diakonos import DashboardWidget

    demo.anlegen(stichtag=STICHTAG)
    with session_factory() as s:
        zeiger = [w.api_method for w in s.scalars(select(DashboardWidget)).all()
                  if w.api_method]
    assert zeiger
    for pfad in zeiger:
        voll = pfad if "." in pfad else f"{FRAPPE_MODULE}.{pfad}"
        assert lookup(voll) is not None, f"api_method nicht auffindbar: {pfad}"


def test_b4_zwei_plaene_veroeffentlicht_und_besetzt(engine, session_factory, demo):
    """B4: Chorplan und Gottesdienst-Ablauf stehen veroeffentlicht und besetzt da."""
    from diakronos_app.models.planrahmen import Eintrag, Plan, Termin

    demo.anlegen(stichtag=STICHTAG)
    with session_factory() as s:
        plaene = {p.titel.split(" ")[0]: p for p in s.scalars(select(Plan)).all()}
        veroeffentlicht = [p for p in plaene.values() if p.status == "veroeffentlicht"]
        assert len(veroeffentlicht) == len(demo.daten.VEROEFFENTLICHTE_PLAENE)
        assert any(p.status == "entwurf" for p in plaene.values()), "kein Entwurf mehr da"

        for plan in veroeffentlicht:
            assert plan.veroeffentlichter_stand, "veroeffentlicht ohne Stand"
            termine = s.scalars(select(Termin).where(Termin.plan == plan.id)).all()
            assert termine
            mit_wert = s.execute(text(
                "SELECT count(*) FROM pr_eintrag e JOIN pr_termin t ON t.id = e.termin"
                " WHERE t.plan = :plan AND CAST(e.wert AS TEXT) <> 'null'"
            ), {"plan": plan.id}).scalar_one()
            assert mit_wert >= len(termine), (
                f"Plan {plan.titel!r} ist nicht besetzt ({mit_wert} Werte)")


def test_b4_ablaufplan_hat_lieder(engine, session_factory, demo):
    """B4: Der Gottesdienst-Ablauf steht mit Liedern im Plan."""
    from diakronos_app.models.planrahmen import Plan

    demo.anlegen(stichtag=STICHTAG)
    with session_factory() as s:
        ablauf = s.scalar(select(Plan).where(Plan.titel.like("Gottesdienste%")))
        assert ablauf is not None
        lieder = s.execute(text(
            "SELECT count(DISTINCT e.wert) FROM pr_eintrag e"
            " JOIN pr_termin t ON t.id = e.termin"
            " WHERE t.plan = :plan AND e.feld_pfad LIKE 'ablauf%lied'"
            "   AND CAST(e.wert AS TEXT) <> 'null'"
        ), {"plan": ablauf.id}).scalar_one()
        assert lieder >= 3, f"nur {lieder} verschiedene Lieder im Ablauf"


def test_b4_jeder_plan_hat_werte(engine, session_factory, demo):
    """B4: KEIN Plan der Demo steht voellig leer da (auch die Entwuerfe nicht).

    Die Befunde der Sichtpruefung waren nicht auf zwei Plaene begrenzt: ein Plan
    ohne Werte zeigt in der Oberflaeche nur leere Felder. Hinter jedem leeren
    Plan stand eine fehlende Voraussetzung — Merkmale ohne Traeger
    (Kindergottesdienst), eine Gruppe mit anderem Namen als im Kochbuch
    (Putzplan: `Hauskreis`), fehlende Untergruppen (Musikteams) bzw. eine leere
    Sammlung (Kindergottesdienst: `programme`). Dieser Test haelt fest, dass die
    Demo alle Voraussetzungen selbst mitbringt.
    """
    from diakronos_app.models.diakonos import Mitglied
    from diakronos_app.models.planrahmen import Plan

    demo.anlegen(stichtag=STICHTAG)
    with session_factory() as s:
        plaene = s.scalars(select(Plan)).all()
        assert len(plaene) == len(demo.daten.PLANTYPEN)
        # ID-1d: Personenzeiger im Plan-Rahmen tragen die SERVER-Kennung der
        # Person, nicht den Anzeigenamen (der Rahmen prueft „Mitglied nicht
        # gefunden“). Der Test prueft deshalb gegen die Kennung.
        _admin_kennung = s.scalar(select(Mitglied.name).where(
            Mitglied.user == demo.daten.ADMIN_EMAIL))
        assert _admin_kennung is not None
        leer = []
        for plan in plaene:
            mit_wert = s.execute(text(
                "SELECT count(*) FROM pr_eintrag e JOIN pr_termin t ON t.id = e.termin"
                " WHERE t.plan = :plan AND CAST(e.wert AS TEXT) <> 'null'"
            ), {"plan": plan.id}).scalar_one()
            termine = s.execute(text(
                "SELECT count(*) FROM pr_termin WHERE plan = :plan"), {"plan": plan.id}).scalar_one()
            if termine == 0 or mit_wert == 0:
                leer.append(f"{plan.titel} (Termine {termine}, Werte {mit_wert})")
        assert not leer, "Plaene ohne Inhalt: " + ", ".join(leer)


def test_b4_veroeffentlichte_plaene_sind_vollstaendig_besetzt(engine, session_factory, demo):
    """B4: In den zwei veroeffentlichten Plaenen traegt fast JEDER Termin Werte.

    Nicht *jeder*: der Gottesdienst-Ablauf hat Termine ohne die passenden
    Elemente (das Abendmahl erscheint nur bei Anlass „abendmahl“), und ein
    Gottesdienst ohne Lied-Element hat folgerichtig nichts zu besetzen. Ein
    einzelner leerer Termin ist also kein Fehler — ein Plan, in dem die
    Mehrheit leer ist, waere einer.
    """
    from diakronos_app.models.planrahmen import Plan

    demo.anlegen(stichtag=STICHTAG)
    with session_factory() as s:
        for plan in s.scalars(select(Plan)).all():
            if plan.status != "veroeffentlicht":
                continue
            gesamt = s.execute(text(
                "SELECT count(*) FROM pr_termin WHERE plan = :plan"),
                {"plan": plan.id}).scalar_one()
            besetzt = s.execute(text(
                "SELECT count(*) FROM pr_termin t WHERE t.plan = :plan AND EXISTS ("
                "  SELECT 1 FROM pr_eintrag e WHERE e.termin = t.id"
                "    AND CAST(e.wert AS TEXT) <> 'null')"
            ), {"plan": plan.id}).scalar_one()
            assert besetzt >= gesamt - 1, (
                f"{plan.titel}: nur {besetzt} von {gesamt} Terminen besetzt")


def test_b2_konto_traegt_den_personennamen(engine, session_factory, demo):
    """B2: `user.full_name` ist die Person — nicht „Administrator“.

    Die Seitenleiste und „Meine Dienste“ zeigen den ANZEIGENAMEN des Kontos.
    Hiess es „Administrator Musterhausen“, sah die verknuepfte Gemeindeleitung
    wie ein Konto ohne Mitglied aus (Sichtpruefung: „Kein Mitglied“).
    """
    from diakronos_app.models.core import User

    demo.anlegen(stichtag=STICHTAG)
    with session_factory() as s:
        admin = s.get(User, demo.daten.ADMIN_EMAIL)
        assert admin is not None
        assert admin.full_name == demo.daten.ADMIN_PERSON
        assert admin.enabled
        mitglied = s.get(User, demo.daten.MITGLIED_EMAIL)
        assert mitglied.full_name == demo.daten.MITGLIED_PERSON


def test_b2_mitglied_wird_ueber_die_konto_email_gefunden(engine, session_factory, demo):
    """B2: Die E-MAIL des Mitglieds ist die des Kontos.

    `api/session.py` ordnet ein Konto ueber `Mitglied.email == User.email` zu
    (nicht ueber `mitglied.user`). Stand dort die private Adresse, lieferte die
    Sitzung `mitglied: null` — Seitenleiste „Kein Mitglied“, „Meine Dienste“
    leer, obwohl die Verknuepfung gesetzt war.
    """
    from diakronos_app.models.diakonos import Mitglied

    demo.anlegen(stichtag=STICHTAG)
    with session_factory() as s:
        for email, person in ((demo.daten.ADMIN_EMAIL, demo.daten.ADMIN_PERSON),
                              (demo.daten.MITGLIED_EMAIL, demo.daten.MITGLIED_PERSON)):
            # ID-1d: die Kennung vergibt der Server — gesucht wird ueber die
            # E-Mail des Kontos (genau die Zuordnung, die die Sitzung nutzt).
            zeile = s.scalar(select(Mitglied).where(Mitglied.email == email))
            assert zeile is not None, f"{person}: kein Mitglied mit {email!r}"
            assert zeile.vorname in person, f"{person}: Vorname {zeile.vorname!r}"
            assert zeile.user == email


def test_b2_gemeindeleitung_hat_mehrere_anstehende_dienste(engine, session_factory, demo):
    """B2: Das Admin-Mitglied hat mehrere Einsätze, nicht nur einen.

    „Meine Dienste“ und die Dienstplan-Kachel der Startseite sind fuer ein
    Konto mit einem einzigen Einsatz praktisch leer — eine Gemeindeleitung
    moderiert und leitet das Einsingen regelmaessig.
    """
    from diakronos_app.models.diakonos import Mitglied

    demo.anlegen(stichtag=STICHTAG)
    with session_factory() as s:
        admin = s.scalar(select(Mitglied).where(Mitglied.user == demo.daten.ADMIN_EMAIL))
        assert admin is not None, "Admin-Konto ist keinem Mitglied zugeordnet"
        einsaetze = s.execute(text(
            "SELECT count(*) FROM pr_eintrag WHERE wert = :p"
        ), {"p": f'"{admin.name}"'}).scalar_one()
        assert einsaetze >= 3, f"nur {einsaetze} Einsaetze fuer die Gemeindeleitung"


def test_b4_ablauf_hat_verschiedene_lieder(engine, session_factory, demo):
    """B4: Die Lieder im Ablauf sind je Termin unterschiedlich.

    Vorher stand in beiden Lied-Elementen desselben Gottesdienstes dasselbe
    Lied (der Zaehler war an die abgelehnten Felder gekoppelt).
    """
    from diakronos_app.models.planrahmen import Plan

    demo.anlegen(stichtag=STICHTAG)
    with session_factory() as s:
        ablauf = s.scalar(select(Plan).where(Plan.titel.like("Gottesdienste%")))
        for (termin,) in s.execute(text(
                "SELECT DISTINCT e.termin FROM pr_eintrag e JOIN pr_termin t"
                " ON t.id = e.termin WHERE t.plan = :plan AND e.feld_pfad LIKE '%lied'"),
                {"plan": ablauf.id}).all():
            titel = [w for (w,) in s.execute(text(
                "SELECT CAST(e.wert AS TEXT) FROM pr_eintrag e"
                " WHERE e.termin = :t AND e.feld_pfad LIKE '%lied'"
                "   AND CAST(e.wert AS TEXT) <> 'null'"), {"t": termin}).all()]
            assert len(titel) == len(set(titel)), f"Lied doppelt am {termin}: {titel}"


def test_b5_beitraege_und_wiki(engine, session_factory, demo):
    """B5: Beitraege und Wiki haben erfundene Eintraege mit Autor und Datum."""
    from diakronos_app.models.diakonos import Beitrag, WikiArtikel

    demo.anlegen(stichtag=STICHTAG)
    with session_factory() as s:
        beitraege = s.scalars(select(Beitrag)).all()
        assert len(beitraege) >= 3
        for beitrag in beitraege:
            assert beitrag.veroeffentlicht == 1
            assert beitrag.autor and beitrag.datum and beitrag.auszug and beitrag.inhalt
            assert beitrag.datum <= STICHTAG
        artikel = s.scalars(select(WikiArtikel)).all()
        assert len(artikel) >= 3
        for a in artikel:
            assert a.titel and a.inhalt and a.kategorie


# ── Rechte-Status der Lieder (PUB-4g, Befund Opus B2) ───────────────────────
# Vorher setzte der Seed ALLE 24 Lieder auf „Gemeinfrei“. Das ist eine falsche
# Rechtsauskunft in einem OEFFENTLICHEN Beispielbestand: gemeinfrei ist nur,
# wessen Text UND Melodie frei sind (Urheber seit ueber 70 Jahren tot).


def test_pub4g_rechte_status_nur_aus_der_app(engine, session_factory, demo):
    """Jeder Rechte-Status ist einer der vier Werte, die die App kennt."""
    from diakronos_app.models.psalmos import Lied

    demo.anlegen(stichtag=STICHTAG)
    with session_factory() as s:
        werte = {l.rechte_status for l in s.scalars(select(Lied)).all()}
    erlaubt = set(demo.daten.RECHTS_STATUS)
    assert werte <= erlaubt, f"unbekannte Rechte-Status: {werte - erlaubt}"


def test_pub4g_nicht_alle_lieder_gemeinfrei(engine, session_factory, demo):
    """Der Bestand ist gemischt — die Status-Spalte zeigt nicht viermal dasselbe.

    Ein Bestand, in dem jedes Lied „Gemeinfrei“ ist, ist fuer eine Gemeinde
    unglaubwuerdig und im Screenshot wertlos (Befund B2).
    """
    from diakronos_app.models.psalmos import Lied

    demo.anlegen(stichtag=STICHTAG)
    with session_factory() as s:
        zeilen = s.scalars(select(Lied)).all()
        je_status: dict[str, int] = {}
        for lied in zeilen:
            je_status[lied.rechte_status] = je_status.get(lied.rechte_status, 0) + 1

    assert len(zeilen) == len(demo.daten.LIEDER)
    assert set(je_status) >= {"Gemeinfrei", "Lizenz vorhanden", "Ungeklärt"}
    # Klare Minderheit: gemeinfrei ist die Ausnahme, nicht die Regel.
    assert je_status["Gemeinfrei"] < len(zeilen), "wieder alle Lieder gemeinfrei"
    assert je_status["Gemeinfrei"] <= len(zeilen) // 2


def test_pub4g_genannte_lieder_nicht_gemeinfrei(engine, session_factory, demo):
    """Die im Befund genannten neueren Lieder stehen NICHT auf „Gemeinfrei“.

    Betroffen waren die Zeilen 438, 454, 460, 464, 466, 470, 476 und 480 der
    Datendatei (Stand der Befundmeldung) — das sind die Lieder
    „Der Morgen strahlt in hellem Licht“, „Lobe den Herrn, meine Seele“,
    „Wo Menschen sich vergessen“, „Auf, auf, mein Herz, mit Freuden“,
    „Macht hoch die Tür“, „Ich will dich lieben, meine Stärke“,
    „Gott hat mir längst einen Engel gesandt“ und „In dir ist Freude“.
    Abgesichert wird ueber den Liedtitel, damit ein Verschieben der Zeilen
    den Test nicht stillschweigend entwertet.
    """
    from diakronos_app.models.psalmos import Lied

    neuere = [
        "Der Morgen strahlt in hellem Licht",
        "Lobe den Herrn, meine Seele",
        "Wo Menschen sich vergessen",
        "Auf, auf, mein Herz, mit Freuden",
        "Macht hoch die Tür",
        "Ich will dich lieben, meine Stärke",
        "Gott hat mir längst einen Engel gesandt",
        "In dir ist Freude",
    ]
    demo.anlegen(stichtag=STICHTAG)
    with session_factory() as s:
        for titel in neuere:
            lied = s.scalar(select(Lied).where(Lied.name == titel))
            assert lied is not None, f"Lied fehlt: {titel}"
            assert lied.rechte_status != "Gemeinfrei", (
                f"{titel!r} steht auf „Gemeinfrei“ — das ist nicht belegt")
