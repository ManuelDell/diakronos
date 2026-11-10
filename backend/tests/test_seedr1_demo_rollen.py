"""SEED-R1: Demo-Konten fuer die BESTEHENDEN Leitungen, Admin nirgends verantwortlich.

BEFUND (Manuel 09.11.): „Du hast meinen Testaccount ueberall als verantwortlich
gesetzt. Es muss verschiedene Verantwortliche geben und der Admin muss dennoch
alles machen koennen."

URSACHEN im Seed (alle hier abgesichert):

* ``gruppen_anlegen`` suchte das Mitglied mit dem ANZEIGENAMEN
  (``a.s.get(Mitglied, "Rebekka Fink")``) — die Kennung ist aber die
  Server-Kennung, ``None`` war die Folge, und die Verantwortungszeile fiel auf
  ``ADMIN_EMAIL`` zurueck. Jede Gruppe hatte damit das Verwaltungskonto als
  Verantwortlichen.
* Nur zwei Konten: wer etwas verantwortete oder moderierte, konnte nur der
  Admin sein.

SOLL (Manuel 09.11., 2. Fassung): „Nutze die bestehenden Rollenverteilungen,
die bereits konfiguriert sind. Kreiere fuer den Test keine neuen." — es gibt
KEINE neuen Personen und KEINE neuen Verantwortlichkeiten; die vier Personen,
die im Bestand schon leiten (Chor, Jugendkreis, Technikteam, Kinderdienst),
bekommen ein Konto mit der Rolle „Mitglied". Zusammen mit ``anna.beispiel``
sind das 5 Testkonten.

WICHTIG: Diese Tests laufen auf einer frischen In-Memory-SQLite — NICHT gegen
die Betriebs-Datenbank ``devecg``.
"""

from __future__ import annotations

import importlib
from datetime import date

import pytest
from sqlalchemy import select, text

STICHTAG = date(2026, 11, 2)


@pytest.fixture()
def demo(patched_db):
    return importlib.import_module("musterhausen")


def _personen_mit_konto(demo) -> dict[str, str]:
    """``person -> konto`` aller Testkonten (die vier Leitungs-Konten)."""
    return demo.testkonten()


# ── Konten ──────────────────────────────────────────────────────────────────


def test_seedr1_fuenf_testkonten_mit_bestehenden_personen(engine, session_factory, demo):
    """Fuenf Testkonten: Anna + die vier BESTEHENDEN Leitungs-Personen.

    Keine neuen Personen: die Konten gehoeren Personen, die im Bestand schon
    eine Gruppe leiten (``musterhausen_daten.GRUPPEN[..]["leitung"]``).
    """
    aus_daten = {eintrag["person"] for eintrag in demo.daten.TESTKONTEN_LEITUNG}
    assert aus_daten == {"Rebekka Fink", "Samuel Fink", "Susanne Gerlach", "Niklas Jäger"}
    leitungen = {gruppe["leitung"] for gruppe in demo.daten.GRUPPEN}
    assert aus_daten <= leitungen, "Testkonto ohne bestehende Leitung"

    demo.anlegen(stichtag=STICHTAG)
    with session_factory() as s:
        emails = {email for (email,) in s.execute(text('SELECT name FROM "user"')).all()}
    erwartet = {demo.daten.ADMIN_EMAIL, demo.daten.MITGLIED_EMAIL}
    erwartet |= {demo.konto_email(person) for person in aus_daten}
    assert emails == erwartet, f"unerwartete/missing Konten: {emails ^ erwartet}"


def test_seedr1_testkonto_traegt_nur_mitglied_und_ist_mitglied_verknuepft(
        engine, session_factory, demo):
    """Jedes Testkonto: Rolle nur „Mitglied", verknuepft mit SEINEM Mitglied."""
    from diakronos_app.models.core import HasRole, User
    from diakronos_app.models.diakonos import Mitglied

    demo.anlegen(stichtag=STICHTAG)
    with session_factory() as s:
        for person, konto in _personen_mit_konto(demo).items():
            email = konto
            user = s.get(User, email)
            assert user is not None, f"Konto fehlt: {konto}"
            assert user.enabled and user.full_name == person, user.full_name

            rollen = {r.role for r in s.scalars(
                select(HasRole).where(HasRole.parent == email)).all()}
            assert rollen == {"Mitglied"}, f"{person}: Rollen {rollen}"

            mitglied = s.scalar(select(Mitglied).where(Mitglied.user == email))
            assert mitglied is not None, f"{person}: kein Mitglied am Konto"
            assert f"{mitglied.vorname} {mitglied.nachname}" == person
            assert mitglied.email == email, "Sitzung ordnet ueber die E-Mail zu"


def test_seedr1_passwort_hash_kommt_vom_admin(engine, session_factory, demo):
    """Alle Testkonten haben denselben Passwort-Hash wie ``admin@example.org``."""
    from diakronos_app.models.core import User

    demo.anlegen(stichtag=STICHTAG)
    with session_factory() as s:
        admin = s.get(User, demo.daten.ADMIN_EMAIL)
        assert admin.password_hash
        for konto in _personen_mit_konto(demo).values():
            user = s.get(User, konto)
            assert user.password_hash == admin.password_hash, konto


def test_seedr1_zweiter_lauf_ueberschreibt_kein_passwort(engine, session_factory, demo):
    """Ein zweiter Lauf laesst bestehende Passwoerter stehen — auch das des Admins.

    Manuel kann sein Passwort geaendert haben; ein Seed, der es zuruecksetzt,
    waere ein Datenverlust.
    """
    from diakronos_app.models.core import User

    demo.anlegen(stichtag=STICHTAG)
    neu = "hash-von-hand-geaendert"
    with session_factory() as s:
        s.get(User, demo.daten.ADMIN_EMAIL).password_hash = neu
        for konto in _personen_mit_konto(demo).values():
            s.get(User, konto).password_hash = neu
        s.commit()

    # Zweiter Lauf auf einer BESTEHENDEN Demo (Nachziehen, siehe `nachziehen`).
    demo.nachziehen(stichtag=STICHTAG)
    with session_factory() as s:
        assert s.get(User, demo.daten.ADMIN_EMAIL).password_hash == neu
        for konto in _personen_mit_konto(demo).values():
            assert s.get(User, konto).password_hash == neu, konto


# ── Verantwortung: Admin nirgends ───────────────────────────────────────────


def test_seedr1_admin_ist_nirgends_verantwortlich(engine, session_factory, demo):
    """Kein Verantwortungs- oder Leitungsfeld zeigt auf den Admin.

    Kalender-Moderation bleibt beim Admin (Manuel 09.11.: „Kalender-Moderatoren
    NICHT neu verteilen“) — eigener Test unten.
    """
    from diakronos_app.models.diakonos import (
        DienstbereichVerantwortlicher,
        Dienstplan,
        Gruppe,
        GruppeVerantwortlicher,
        Mitglied,
    )

    admin = demo.daten.ADMIN_EMAIL
    demo.anlegen(stichtag=STICHTAG)
    with session_factory() as s:
        for modell in (GruppeVerantwortlicher, DienstbereichVerantwortlicher):
            treffer = s.scalars(select(modell).where(modell.user == admin)).all()
            assert not treffer, f"{modell.__tablename__} nennt den Admin: " \
                                f"{[t.name for t in treffer]}"
        admin_kennung = s.scalar(select(Mitglied.name).where(Mitglied.user == admin))
        assert admin_kennung
        assert not s.scalars(select(Gruppe).where(Gruppe.leiter == admin_kennung)).all()
        assert not s.scalars(select(Gruppe).where(Gruppe.leiter == admin)).all()
        assert not s.scalars(select(Dienstplan).where(
            Dienstplan.leitung == admin_kennung)).all()


def test_seedr1_gruppenverantwortung_gehoert_der_leitung(engine, session_factory, demo):
    """Jede Gruppe mit Konto-Leitung: Verantwortungszeile = DIESES Konto.

    Gruppen, deren Leitung kein Konto hat, bekommen KEINE Zeile (kein
    Admin-Rueckfall).
    """
    from diakronos_app.models.diakonos import GruppeVerantwortlicher

    demo.anlegen(stichtag=STICHTAG)
    with session_factory() as s:
        for gruppe in demo.daten.GRUPPEN:
            zeile = s.get(GruppeVerantwortlicher, f"{gruppe['name']}-verantwortlich")
            konto = demo.konto_von_person(gruppe["leitung"])
            if konto is None:
                assert zeile is None, f"{gruppe['name']}: Zeile ohne Konto-Leitung"
                continue
            assert zeile is not None, f"{gruppe['name']}: Verantwortung fehlt"
            assert zeile.user == konto, f"{gruppe['name']}: {zeile.user} statt {konto}"


def test_seedr1_gruppe_leiter_bleibt_freitext(engine, session_factory, demo):
    """``gruppe.leiter`` ist ein Freitext-Name (kein Fremdschluessel) — unveraendert."""
    from diakronos_app.models.diakonos import Gruppe

    demo.anlegen(stichtag=STICHTAG)
    with session_factory() as s:
        for gruppe in demo.daten.GRUPPEN:
            zeile = s.get(Gruppe, gruppe["name"])
            assert zeile is not None
            assert zeile.leiter == gruppe["leitung"]


def test_seedr1_kalender_moderatoren_bleiben_wie_konfiguriert(engine, session_factory, demo):
    """Kalender-Moderatoren werden NICHT neu verteilt (Manuel 09.11.)."""
    from diakronos_app.models.kronos import Kalender, KalenderModerator

    demo.anlegen(stichtag=STICHTAG)
    with session_factory() as s:
        zeilen = s.scalars(select(KalenderModerator)).all()
        assert {z.user for z in zeilen} == {demo.daten.ADMIN_EMAIL}
        assert {z.parent for z in zeilen} == set(s.scalars(select(Kalender.name)).all())


def test_seedr1_anna_bekommt_keine_neue_verantwortung(engine, session_factory, demo):
    """Anna: BESTEHENDE Verantwortung bleibt (Bereich Musik, Dienstplan
    Gottesdienst), NEU hinzu kommt nichts (keine Gruppe, kein Kalender)."""
    from diakronos_app.models.diakonos import (
        DienstbereichVerantwortlicher,
        Dienstplan,
        GruppeVerantwortlicher,
        Mitglied,
    )
    from diakronos_app.models.kronos import KalenderModerator

    demo.anlegen(stichtag=STICHTAG)
    konto = demo.daten.MITGLIED_EMAIL
    with session_factory() as s:
        for modell in (GruppeVerantwortlicher, KalenderModerator):
            assert not s.scalars(select(modell).where(modell.user == konto)).all(), \
                f"{modell.__tablename__}"
        bereiche = {z.parent for z in s.scalars(
            select(DienstbereichVerantwortlicher).where(
                DienstbereichVerantwortlicher.user == konto)).all()}
        assert bereiche <= {"musik"}, bereiche
        anna = s.scalar(select(Mitglied.name).where(Mitglied.user == konto))
        plaene = {p.name for p in s.scalars(
            select(Dienstplan).where(Dienstplan.leitung == anna)).all()}
        assert plaene == {"Dienstplan Gottesdienst"}, plaene


def test_seedr1_bestehende_leitungen_bleiben_wie_konfiguriert(engine, session_factory, demo):
    """Keine erfundene Neuverteilung: die Leitungen sind die der Daten.

    Dienstplaene: Gottesdienst -> Anna Beispiel, Kinderdienst -> Susanne
    Gerlach (wie im Bestand).
    """
    from diakronos_app.models.diakonos import Dienstplan, Mitglied

    assert demo.daten.DIENSTPLAN_LEITUNGEN == {
        "Dienstplan Gottesdienst": "Anna Beispiel",
        "Dienstplan Kinderdienst": "Susanne Gerlach",
    }
    demo.anlegen(stichtag=STICHTAG)
    with session_factory() as s:
        for name, person in demo.daten.DIENSTPLAN_LEITUNGEN.items():
            zeile = s.get(Dienstplan, name)
            assert zeile is not None
            vorname, _, nachname = person.partition(" ")
            erwartet = s.scalar(select(Mitglied.name).where(
                Mitglied.vorname == vorname, Mitglied.nachname == nachname))
            assert zeile.leitung == erwartet, f"{name}: {zeile.leitung!r}"


# ── Idempotenz / Nachziehen ─────────────────────────────────────────────────


def test_seedr1_nachziehen_ist_idempotent(engine, session_factory, demo):
    """Ein zweiter Lauf auf einer fertigen Demo legt nichts Neues an."""
    demo.anlegen(stichtag=STICHTAG)
    with session_factory() as s:
        vorher = {
            tabelle: s.execute(text(f'SELECT count(*) FROM "{tabelle}"')).scalar_one()
            for tabelle in ("user", "has_role", "gruppe_verantwortlicher",
                            "kalender_moderator", "dienstplan")
        }
    bericht = demo.nachziehen(stichtag=STICHTAG)
    assert "neu" not in bericht.replace("bereits vorhanden", ""), bericht
    with session_factory() as s:
        for tabelle, anzahl in vorher.items():
            assert s.execute(text(f'SELECT count(*) FROM "{tabelle}"')).scalar_one() == anzahl, tabelle


def test_seedr1_nachziehen_korrigiert_den_alten_admin_stand(engine, session_factory, demo):
    """Nachziehen raeumt die Gruppen-Verantwortung des Admins (alter Seed) weg —
    und NUR die: von Hand gesetzte Verantwortliche, Leiter-Freitext,
    Dienstplan-Leitungen und Kalender-Moderatoren bleiben unberuehrt.
    Idempotent (noch ein Lauf aendert nichts).
    """
    from diakronos_app.models.diakonos import (
        Dienstplan,
        Gruppe,
        GruppeVerantwortlicher,
    )
    from diakronos_app.models.kronos import KalenderModerator

    demo.anlegen(stichtag=STICHTAG)
    admin = demo.daten.ADMIN_EMAIL
    hand = demo.konto_email("Samuel Fink")
    # Eine Gruppe, deren Zeile von Hand auf ein ANDERES Konto gesetzt wurde.
    hand_gruppe = next(g["name"] for g in demo.daten.GRUPPEN
                       if demo.konto_von_person(g["leitung"]) is None)
    with session_factory() as s:
        for gruppe in demo.daten.GRUPPEN:
            zeile = s.get(GruppeVerantwortlicher, f"{gruppe['name']}-verantwortlich")
            ziel = hand if gruppe["name"] == hand_gruppe else admin
            if zeile is None:
                s.add(GruppeVerantwortlicher(
                    name=f"{gruppe['name']}-verantwortlich", parent=gruppe["name"],
                    parenttype="Gruppe", parentfield="verantwortliche", user=ziel,
                    docstatus=0, idx=1))
            else:
                zeile.user = ziel
        s.get(Gruppe, hand_gruppe).leiter = "von Hand"
        s.get(Dienstplan, "Dienstplan Kinderdienst").leitung = s.get(
            Dienstplan, "Dienstplan Gottesdienst").leitung
        s.commit()
        moderatoren_vorher = {(z.name, z.user) for z in s.scalars(select(KalenderModerator)).all()}

    demo.nachziehen(stichtag=STICHTAG)

    with session_factory() as s:
        assert not s.scalars(select(GruppeVerantwortlicher).where(
            GruppeVerantwortlicher.user == admin)).all()
        for gruppe in demo.daten.GRUPPEN:
            zeile = s.get(GruppeVerantwortlicher, f"{gruppe['name']}-verantwortlich")
            if gruppe["name"] == hand_gruppe:
                assert zeile is not None and zeile.user == hand
                continue
            konto = demo.konto_von_person(gruppe["leitung"])
            assert (zeile.user if zeile is not None else None) == konto
        assert s.get(Gruppe, hand_gruppe).leiter == "von Hand"
        assert (s.get(Dienstplan, "Dienstplan Kinderdienst").leitung
                == s.get(Dienstplan, "Dienstplan Gottesdienst").leitung)
        assert {(z.name, z.user) for z in s.scalars(
            select(KalenderModerator)).all()} == moderatoren_vorher

    # Und noch einmal: nichts mehr zu tun, nichts mehr zu aendern.
    with session_factory() as s:
        vorher = {
            tabelle: s.execute(text(f'SELECT count(*) FROM "{tabelle}"')).scalar_one()
            for tabelle in ("user", "has_role", "gruppe_verantwortlicher",
                            "kalender_moderator", "dienstplan")
        }
    demo.nachziehen(stichtag=STICHTAG)
    with session_factory() as s:
        for tabelle, anzahl in vorher.items():
            assert s.execute(text(f'SELECT count(*) FROM "{tabelle}"')).scalar_one() == anzahl


def test_seedr1_nachziehen_mit_geaendertem_admin_passwort(engine, session_factory, demo):
    """Admin-Passwort von Hand geaendert, Testkonten fehlen noch (Demo von vor
    SEED-R1): Nachziehen legt die Konten mit dem AKTUELLEN Admin-Hash an und
    bricht nicht an der Klartext-Pruefung ab."""
    from diakronos_app.frappe_compat.passwoerter import neuer_hash
    from diakronos_app.models.core import HasRole, User
    from diakronos_app.models.diakonos import GruppeVerantwortlicher, Mitglied

    demo.anlegen(stichtag=STICHTAG)
    neu = neuer_hash("anderes-passwort-von-hand")
    with session_factory() as s:
        s.get(User, demo.daten.ADMIN_EMAIL).password_hash = neu
        for konto in _personen_mit_konto(demo).values():
            for m in s.scalars(select(Mitglied).where(Mitglied.user == konto)).all():
                m.user = None
            for r in s.scalars(select(HasRole).where(HasRole.parent == konto)).all():
                s.delete(r)
            # Alter Stand: die Verantwortung lag beim Admin (Admin-Rueckfall).
            for z in s.scalars(select(GruppeVerantwortlicher).where(
                    GruppeVerantwortlicher.user == konto)).all():
                z.user = demo.daten.ADMIN_EMAIL
            s.flush()
            s.delete(s.get(User, konto))
        s.commit()

    demo.nachziehen(stichtag=STICHTAG)
    with session_factory() as s:
        assert s.get(User, demo.daten.ADMIN_EMAIL).password_hash == neu
        for konto in _personen_mit_konto(demo).values():
            assert s.get(User, konto).password_hash == neu, konto


def test_seedr1_nachziehen_legt_keine_neuen_zuweisungen_an(engine, session_factory, demo):
    """Demo ohne Website-/Bereichs-Verantwortung (Stand devecg): Nachziehen
    legt dort nichts davon nach — nur Konten + Korrektur des Admin-Rueckfalls."""
    from diakronos_app.models.diakonos import DienstbereichVerantwortlicher
    from diakronos_app.models.website_ansprechpartner import WebsiteAnsprechpartner

    demo.anlegen(stichtag=STICHTAG)
    with session_factory() as s:
        for modell in (DienstbereichVerantwortlicher, WebsiteAnsprechpartner):
            for z in s.scalars(select(modell)).all():
                s.delete(z)
        s.commit()

    demo.nachziehen(stichtag=STICHTAG)
    with session_factory() as s:
        assert not s.scalars(select(DienstbereichVerantwortlicher)).all()
        assert not s.scalars(select(WebsiteAnsprechpartner)).all()


def test_seedr1_nachziehen_verweigert_fremde_datenbank(engine, session_factory, demo):
    """Ohne Musterhausen-Marker bricht Nachziehen ab (Betriebsschutz)."""
    with pytest.raises(demo.DemoFehler):
        demo.nachziehen(stichtag=STICHTAG)
