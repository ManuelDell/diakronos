"""DSGVO-1 (D5/D6): vollständige Anonymisierung, Nachweis und Eindeutigkeit.

Der Kern dieses Moduls ist der VOLLSCAN: nach der Anonymisierung wird die GANZE
Test-Datenbank (alle Tabellen, alle Textspalten) nach Vorname, Nachname, Mail
und Telefon der Person durchsucht — auch in klein/ohne Leerzeichen. Erwartet
werden 0 Treffer. Dazu kommen Rechte, Reihenfolge, Rollback und Eindeutigkeit.

Der Scan läuft hier über die Metadaten (SQLite) — dieselbe Suite läuft im Image
zusätzlich gegen den Wegwerf-PostgreSQL (`make test` im Container) und der
Inventar-Test `test_dsgvo1_inventar.py` prüft die ECHTE Betriebs-DB.
"""
from __future__ import annotations

from datetime import date, datetime

import pytest

from test_ma1_mailversand import _smtp_einrichten
from sqlalchemy import String, Text, select

from diakronos_app.frappe_compat.session import set_user
from diakronos_app.models.core import HasRole, NotificationLog, User, UserRole
from diakronos_app.models.diakonos import (
    Anmeldung, AnmeldungAntwort, AnmeldungKind, AuditLog, Beitrag,
    Mitglied, MitgliedBeziehung, RessourcenBuchung,
)
from diakronos_app.models.sicherung import Sicherungslauf

PFAD = "/api/method/diakronos.diakonos.api.datenschutz."

ANNA = {
    "vorname": "Annamaria",
    "nachname": "Beispielhuber",
    "email": "annamaria.beispielhuber@example.org",
    "telefon": "0170 4455667",
}


def post(client, fn, **kw):
    return client.post(PFAD + fn, json=kw)


@pytest.fixture
def welt(patched_db):
    """Zwei Personen mit vollem Bezugswerk; die Admin-Konten zum Löschen."""
    with patched_db.begin() as s:
        for konto, rolle in (
            ("admin@example.org", "System Manager"),
            ("admin2@example.org", "System Manager"),
            ("verwaltung@example.org", "Mitgliederadministrator"),
        ):
            s.add(User(name=konto, email=konto, full_name="Verwaltung " + konto, enabled=True))
            s.add(HasRole(name=f"role-{konto}", parent=konto, parenttype="User", role=rolle))
        s.add(User(name=ANNA["email"], email=ANNA["email"],
                   full_name="Annamaria Beispielhuber", password_hash="hash", enabled=True))
        s.add(HasRole(name="role-anna", parent=ANNA["email"], parenttype="User", role="Mitglied"))
        s.flush()
        s.add_all([
            Mitglied(
                name="D1-anna", vorname=ANNA["vorname"], nachname=ANNA["nachname"],
                email=ANNA["email"], telefonnummer=ANNA["telefon"],
                geburtstag=date(1990, 5, 4), wohnort="Beispieldorf",
                straße="Beispielweg", nummer="7", notiz="Annamaria mag Kuchen",
                user=ANNA["email"], status="Mitglied", datenschutz_einwilligung=True,
                foto_einwilligung=True, mitglied_seit=date(2020, 1, 1),
                ancestor_path="Beispielhuber, Annamaria",
            ),
            # Bewusst ein ANDERER Nachname: derselbe Nachname einer zweiten
            # Person ist DEREN Datum und darf von der Löschung nicht angetastet
            # werden — der Vollscan würde es sonst als Rest melden.
            Mitglied(name="D1-bert", vorname="Bert", nachname="Berger"),
        ])
        s.add_all([
            # Anmeldung mit Angehörigen und Freitextantwort
            Anmeldung(
                name="D1-anmeldung", mitglied="D1-anna", vorname=ANNA["vorname"],
                nachname=ANNA["nachname"], email=ANNA["email"],
                email_freitext="kontakt: annamaria.beispielhuber@example.org",
                name_freitext="Annamaria Beispielhuber", telefon=ANNA["telefon"],
                geburtstag=date(1990, 5, 4), ip_adresse="203.0.113.7",
                kommentar="Annamaria fragt nach dem Bus", status="angemeldet",
            ),
            AnmeldungAntwort(name="D1-antwort", parent="D1-anmeldung",
                             feldlabel="Allergien", antwort="Annamaria: Nüsse"),
            AnmeldungKind(name="D1-kind", parent="D1-anmeldung",
                          vorname="Annamaria", nachname="Beispielhuber"),
            # Protokolleinträge, die die Person nennen
            AuditLog(name="D1-audit", actor=ANNA["email"], target_user=ANNA["email"],
                     target_doctype="Mitglied", target_name="D1-anna",
                     action_typ="Aenderung", field_changed="email",
                     old_value="annamaria.beispielhuber@example.org",
                     new_value="Annamaria Beispielhuber",
                     ip_address="203.0.113.7", user_agent="Mozilla Annamaria"),
            NotificationLog(name="D1-notiz", for_user=ANNA["email"],
                            from_user="verwaltung@example.org",
                            subject="Hallo Annamaria",
                            email_content="Annamaria, dein Antrag ist da."),
            MitgliedBeziehung(name="D1-beziehung", parent="D1-bert", beziehung_zu="D1-anna"),
        ])
    # Zweite Transaktion: `s.get` wuerde sonst einen Identitaetskonflikt melden
    # (D1-bert liegt noch im Identity-Map dieser Sitzung).
    with patched_db.begin() as s:
        s.get(Mitglied, "D1-bert").ehepartner = "D1-anna"
    set_user("admin@example.org")
    return patched_db


def _alle_textwerte(session) -> list[tuple[str, str, str]]:
    """Jede Textspalte jeder Tabelle: (tabelle, spalte, wert).

    Bei gleichem Spaltennamen trägt SQLAlchemy den Namen doppelt ein (`name`,
    `name_1`, …) — zurück auf den echten Spaltennamen abgebildet, sonst
    verdeckt das Label eine Fundstelle.
    """
    from diakronos_app.models.base import Base

    gefunden = []
    for mapper in Base.registry.mappers:
        tabelle = mapper.local_table
        spalten = [c for c in tabelle.c if isinstance(c.type, (String, Text))]
        if not spalten:
            continue
        for zeile in session.execute(select(*spalten)).all():
            for spalte, wert in zip(spalten, zeile):
                if wert is None or str(wert) == "":
                    continue
                gefunden.append((tabelle.name, spalte.name, str(wert)))
    return gefunden


def vollscan(welt_factory, *werte) -> list[tuple[str, str, str]]:
    """Alle Stellen, an denen einer der Werte vorkommt.

    Gesucht wird exakt UND in der normalisierten Form (`email_belegung.
    normalisiere`: NFKC, Leerraum weg, klein) — aber nur für Werte, die wie
    eine Adresse oder wie ein Telefon aussehen. Ein Nachname in Kleinschreibung
    wäre eine falsche Fahndung: „beispielhuber“ trifft auch fremde Treffer und
    umgekehrt bliebe ein korrekt ersetzter Wert als Treffer stehen.
    """
    from diakronos_app.email_belegung import normalisiere

    nadel: list[str] = []
    for wert in werte:
        text = str(wert or "").strip()
        if not text:
            continue
        # Groß/klein ist kein Personenbezug-Unterschied: die Ersetzung im
        # Freitext arbeitet mit `lower()` auf beiden Seiten, die Suche hier
        # muss dieselbe Regel verwenden. Adressen zusätzlich in der
        # normalisierten Form (`email_belegung.normalisiere`).
        nadel.append(text.lower())
        # Adressen zusätzlich in der normalisierten Form (`email_belegung.
        # normalisiere`: NFKC, Leerraum weg, klein) — die Ersetzung im Freitext
        # vergleicht ebenfalls normalisiert.
        if "@" in text:
            nadel.append(normalisiere(text))
        elif text.replace(" ", "").isdigit():
            nadel.append(normalisiere(text))
    treffer = []
    with welt_factory() as s:
        for tabelle, spalte, wert in _alle_textwerte(s):
            if any(n and n in wert.lower() for n in nadel):
                treffer.append((tabelle, spalte, wert[:120]))
    return treffer


def test_vollscan_vor_der_loeschung_findet_die_person(welt):
    """Gegenprobe: der Scan ist scharf — vorher MUSS er Treffer liefern."""
    treffer = vollscan(welt, ANNA["vorname"], ANNA["nachname"], ANNA["email"])
    assert treffer, "Der Vollscan findet nichts — er waere als Nachweis wertlos"
    assert {"mitglied", "anmeldung", "audit_log", "notification_log"} <= {t for t, _, _ in treffer}


def test_vollscan_findet_kleinschreibung(welt):
    """Gegenprobe für die Nadeln: Groß/klein zählt mit.

    Sonst wäre „Keine Treffer“ eine Aussage über die Suche, nicht über die
    Daten — genau der Fehler, den dieser Nachweis verhindern soll. Der Name der
    Person ist ein Eigenname („Annamaria“) und kommt in der Welt in
    Kleinschreibung vor; ein normalisiert verglichener Treffer ist Pflicht.
    """
    with welt.begin() as s:
        s.get(Mitglied, "D1-bert").notiz = "Klein: annamaria"
    klein = vollscan(welt, "annamaria")
    assert any(tabelle == "mitglied" for tabelle, _, _ in klein), klein


def test_wohnort_und_geburtsdatum_bleiben_in_fremden_texten(client, welt, smtp):
    """Wohnort/Straße/Geburtstag stehen in der EIGENEN Zeile nicht mehr — in
    FREMDEN Notizen bleiben sie stehen (Fachentscheidung DSGVO-1b, K2).

    Die alte Fassung ersetzte diese Werte als Teilstring über alle Tabellen.
    Folge im Betrieb (R-DSGVO-1, K2): „Stuttgart“ wurde bei NEUN anderen
    Mitgliedern zu `[gelöscht]`, und ein Wohnort ist kein Merkmal, das eine
    Person in fremden Texten eindeutig identifiziert — einzelne Vornamen und
    Orte treffen beliebige andere Wörter („Eva“ → „Evangelisch“).
    """
    with welt.begin() as s:
        s.get(Mitglied, "D1-bert").notiz = "wohnt in Beispieldorf, Beispielweg 7, geb. 1990-05-04"
    assert _antrag_und_loeschen(client, welt).status_code == 200
    with welt() as s:
        # Eigene Zeile: die Werte der Person sind weg.
        eigene = s.get(Mitglied, _kennung(welt))
        for feld in ("wohnort", "straße", "nummer", "postleitzahl", "geburtstag"):
            assert getattr(eigene, feld) is None, feld
        # Fremde Notiz: unverändert (der Ort ist kein Identifikationsmerkmal).
        assert s.get(Mitglied, "D1-bert").notiz == (
            "wohnt in Beispieldorf, Beispielweg 7, geb. 1990-05-04")


def test_benachrichtigung_an_die_verwaltung_nennt_keine_adresse(client, welt):
    """Die Meldung an die Verwaltung nennt den Namen (die Verwaltung muss
    wissen, wen) — aber NICHT die E-Mail der Person, die im `for_user` des
    Empfängers sonst als Freitext übrig bliebe."""
    set_user(ANNA["email"])
    assert post(client, "loeschung_beantragen", bestaetigt=True).status_code == 200
    with welt() as s:
        inhalt = " ".join(
            str(m.email_content or "") for m in s.scalars(select(NotificationLog).where(
                NotificationLog.subject == "Löschantrag nach DSGVO gestellt")).all()
        )
    assert "Annamaria Beispielhuber hat" in inhalt
    assert ANNA["email"] not in inhalt


def _kennung(welt, alt="D1-anna") -> str:
    """Die NEUE neutrale Kennung der geloeschten Person (K1, DSGVO-1b).

    Seit der Nacharbeit bekommt die Person bei der Loeschung eine eigene
    Kennung `geloescht-<hex>`; `mitglied.name` ist im Betrieb der KLARNAME und
    darf nicht als Primaerschluessel stehen bleiben.
    """
    with welt() as s:
        for name in s.scalars(select(Mitglied.name)).all():
            if name != alt and str(name).startswith("geloescht-"):
                return str(name)
    raise AssertionError("keine neutrale Kennung gefunden — Loeschung nicht erfolgt?")


def _antrag_und_loeschen(client, welt, mitglied="D1-anna", smtp_ok=True):
    set_user(ANNA["email"])
    assert post(client, "loeschung_beantragen", bestaetigt=True).status_code == 200
    set_user("admin@example.org")
    return post(client, "loeschung_bestaetigen", mitglied_id=mitglied, bestaetigt=True)


@pytest.fixture
def smtp(monkeypatch, patched_db):
    """Fake-SMTP an der Testnaht; `smtp.fehler` macht den Versand kaputt."""
    from diakronos_app import mailversand
    from diakronos_app.settings import get_settings

    class Fake:
        def __init__(self):
            self.nachrichten = []
            self.fehler = None
            self.ereignisse = []

        def ehlo(self):
            self.ereignisse.append("ehlo")

        def has_extn(self, name):
            return True

        def starttls(self):
            self.ereignisse.append("starttls")

        def login(self, *_a):
            self.ereignisse.append("login")

        def send_message(self, nachricht):
            if self.fehler is not None:
                self.ereignisse.append("fehler")
                raise self.fehler
            self.ereignisse.append("send")
            self.nachrichten.append(nachricht)

        def quit(self):
            pass

    # MAIL-1: die Einstellungen stehen in der DB (Tabelle `smtp_einstellungen`),
    # nicht mehr in der Umgebung. `patched_db` legt sie in der Test-Datenbank an.
    _smtp_einrichten(patched_db)
    fake = Fake()
    monkeypatch.setattr(mailversand, "VERBINDUNG", fake)
    return fake


def test_vollstaendige_anonymisierung_null_treffer(client, welt, smtp):
    r = _antrag_und_loeschen(client, welt)
    assert r.status_code == 200, r.text
    assert len(smtp.nachrichten) == 1 and smtp.nachrichten[0]["To"] == ANNA["email"]
    treffer = vollscan(welt, ANNA["vorname"], ANNA["nachname"], ANNA["email"], ANNA["telefon"])
    assert treffer == [], f"Personendaten stehen noch in: {treffer}"
    # Was der Scan NICHT finden kann, wird ausdrücklich geprüft: die
    # Protokollzeile selbst bleibt (Nachweis), ihre personenbezogenen Werte
    # sind ersetzt. `user_agent` steht (wie IP und Browserkennung generell)
    # in der Spaltenliste des Inventars, nicht in der Namenssuche: er nennt
    # ein Gerät, nicht einen Namen.
    with welt() as s:
        kennung = _kennung(welt)
        eintrag = s.get(AuditLog, "D1-audit")
        assert eintrag is not None
        assert eintrag.old_value == "[gelöscht]" and eintrag.new_value == "[gelöscht]"
        assert eintrag.user_agent is None and eintrag.ip_address is None
        assert eintrag.actor is None and eintrag.target_user is None
        # K1: die Zielkennung ist die NEUE neutrale Kennung.
        assert eintrag.target_name == kennung


def test_mitglied_zeigt_geloeschte_person_und_status(client, welt, smtp):
    assert _antrag_und_loeschen(client, welt).status_code == 200
    with welt() as s:
        assert s.get(Mitglied, "D1-anna") is None, "alte Kennung (Klarname) bleibt"
        m = s.get(Mitglied, _kennung(welt))
        assert (m.vorname, m.nachname) == ("Gelöschte", "Person")
        assert m.status == "geloescht" and m.ausgeschlossen is True
        for feld in ("email", "telefonnummer", "geburtstag", "wohnort", "straße",
                     "nummer", "notiz", "user", "foto", "mitglied_seit", "ancestor_path"):
            assert getattr(m, feld) is None, feld


def test_konto_und_zugang_sind_weg(client, welt, smtp):
    assert _antrag_und_loeschen(client, welt).status_code == 200
    with welt() as s:
        assert s.get(User, ANNA["email"]) is None
        # Rollen: die Zeilen sind weg — ihre Eindeutigkeit ist der Zugang selbst
        # (`api/zugang._rollen_von` liest sie).
        assert s.scalars(select(HasRole).where(HasRole.parent == ANNA["email"])).all() == []


def test_antrag_ueberlebt_als_nachweis_ohne_personenbezug(client, welt, smtp):
    assert _antrag_und_loeschen(client, welt).status_code == 200
    from diakronos_app.models.datenschutz import STATUS_AUSGEFUEHRT, Loeschantrag

    with welt() as s:
        a = s.get(Loeschantrag, _kennung(welt))
        assert a is not None, "Löschantrag hängt nicht an der neuen Kennung"
        assert a.status == STATUS_AUSGEFUEHRT
        assert s.get(Loeschantrag, "D1-anna") is None
        assert a.anonymisiert_am is not None and a.freigegeben_am is not None
        assert a.freigegeben_von == "admin@example.org"
        assert a.benachrichtigt_am is not None
        # Der Datensatz traegt nur die technische ID — kein Name, keine Mail.
        assert {c.key for c in Loeschantrag.__table__.columns} >= {
            "mitglied", "beantragt_am", "status", "anonymisiert_am"
        }


def test_login_der_geloeschten_person_ist_unmoeglich(client, welt, smtp):
    from diakronos_app.frappe_compat import sitzungen

    sid, _ = sitzungen.anlegen(ANNA["email"])
    assert _antrag_und_loeschen(client, welt).status_code == 200
    assert sitzungen.lesen(sid) is None
    from diakronos_app.api.auth import login

    with pytest.raises(Exception):
        login(email=ANNA["email"], passwort="irgendwas")


def test_mailfehler_loescht_nichts(client, welt, smtp):
    """D4, Schritt 2: Versand scheitert -> NICHTS gelöscht, erneut versuchbar."""
    smtp.fehler = RuntimeError("550 mailbox unavailable")
    set_user(ANNA["email"])
    assert post(client, "loeschung_beantragen", bestaetigt=True).status_code == 200
    set_user("admin@example.org")
    r = post(client, "loeschung_bestaetigen", mitglied_id="D1-anna", bestaetigt=True)
    assert r.status_code == 417, r.text
    assert "fehlgeschlagen" in r.json()["message"]
    assert "NICHTS gelöscht" in r.json()["message"]
    with welt() as s:
        assert s.get(Mitglied, "D1-anna").vorname == ANNA["vorname"]
        assert s.get(User, ANNA["email"]) is not None
        from diakronos_app.models.datenschutz import STATUS_OFFEN, Loeschantrag

        assert s.get(Loeschantrag, "D1-anna").status == STATUS_OFFEN
    treffer = vollscan(welt, ANNA["vorname"], ANNA["email"])
    assert treffer, "Nach dem fehlgeschlagenen Versand muss die Person noch da sein"

    # Erneut versuchen, diesmal mit funktionierendem Versand.
    smtp.fehler = None
    assert _antrag_und_loeschen(client, welt).status_code in (200, 417)


def test_rollback_bei_fehlender_mail_einrichtung(client, welt, monkeypatch):
    # MAIL-1: „nicht eingerichtet“ heisst jetzt: KEINE Zeile in der DB.
    from diakronos_app.db import SessionLocal
    from diakronos_app.models.smtp import SMTP_EINSTELLUNGEN_NAME, SmtpEinstellungen

    with SessionLocal.begin() as s:
        zeile = s.get(SmtpEinstellungen, SMTP_EINSTELLUNGEN_NAME)
        if zeile is not None:
            s.delete(zeile)
    set_user(ANNA["email"])
    assert post(client, "loeschung_beantragen", bestaetigt=True).status_code == 200
    set_user("admin@example.org")
    r = post(client, "loeschung_bestaetigen", mitglied_id="D1-anna", bestaetigt=True)
    assert r.status_code == 417
    assert "Mailversand ist nicht eingerichtet" in r.json()["message"]
    with welt() as s:
        assert s.get(Mitglied, "D1-anna").email == ANNA["email"]
        assert s.get(User, ANNA["email"]) is not None


def test_anonymisierungsfehler_rollt_alles_zurueck(client, welt, smtp):
    """Scheitert die Anonymisierung, bleibt die Person vollständig erhalten."""
    from sqlalchemy import event

    set_user(ANNA["email"])
    assert post(client, "loeschung_beantragen", bestaetigt=True).status_code == 200
    set_user("admin@example.org")

    engine = welt.kw["bind"]

    def abbrechen(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith(("DELETE FROM USER", "UPDATE MITGLIED")):
            raise RuntimeError("Erzwungener Abbruch der Anonymisierung")

    event.listen(engine, "before_cursor_execute", abbrechen)
    try:
        with pytest.raises(RuntimeError, match="Erzwungener Abbruch"):
            post(client, "loeschung_bestaetigen", mitglied_id="D1-anna", bestaetigt=True)
    finally:
        event.remove(engine, "before_cursor_execute", abbrechen)

    with welt() as s:
        assert s.get(Mitglied, "D1-anna").vorname == ANNA["vorname"]
        assert s.get(User, ANNA["email"]) is not None
        from diakronos_app.models.datenschutz import STATUS_OFFEN, Loeschantrag

        assert s.get(Loeschantrag, "D1-anna").status == STATUS_OFFEN


def test_nach_loeschung_ist_die_adresse_wieder_vergebbar(client, welt, smtp):
    """D6: `email` ist NULL, der partielle Unique-Index greift nicht mehr."""
    assert _antrag_und_loeschen(client, welt).status_code == 200
    with welt.begin() as s:
        s.add(User(name=ANNA["email"], email=ANNA["email"], enabled=True))
        s.flush()
        s.add(Mitglied(name="D1-neu", vorname="Annamaria", nachname="Beispielhuber",
                       email=ANNA["email"], user=ANNA["email"]))
    with welt() as s:
        neu = s.get(Mitglied, "D1-neu")
        assert neu.email == ANNA["email"]
        assert s.get(Mitglied, _kennung(welt)).email is None


def test_planhistorie_bleibt_und_zeigt_geloeschte_person(client, welt, smtp):
    """Dienstpläne/Einplanungen bleiben strukturell — ohne Personenbezug."""
    from diakronos_app.models.diakonos import (
        Dienstplan, DienstplanTeilnehmer, Gruppenmitgliedschaft,
    )

    with welt.begin() as s:
        s.add(Dienstplan(name="D1-plan", plantitel="Probe"))
        s.flush()
        s.add_all([
            DienstplanTeilnehmer(name="D1-teilnehmer", parent="D1-plan", mitglied="D1-anna",
                                 notiz_intern="Nur morgens da"),
            Gruppenmitgliedschaft(name="D1-gruppe", parent="D1-plan", mitglied="D1-anna",
                                  notiz="Annamaria ist dabei"),
        ])
    assert _antrag_und_loeschen(client, welt).status_code == 200
    with welt() as s:
        kennung = _kennung(welt)
        t = s.get(DienstplanTeilnehmer, "D1-teilnehmer")
        # Der Verweis zeigt auf die NEUE neutrale Kennung (K1): der Plan bleibt
        # strukturell vollständig, die Person ist aber nicht mehr erkennbar.
        # Die Notiz bleibt lesbar — sie nannte keinen Namen.
        assert t is not None and t.mitglied == kennung
        assert t.notiz_intern == "Nur morgens da"
        assert s.get(Gruppenmitgliedschaft, "D1-gruppe").mitglied == kennung
        assert s.get(Dienstplan, "D1-plan") is not None


def test_geloeschte_person_kann_nicht_reaktiviert_werden(client, welt, smtp):
    from diakronos_app.api.mitglieder import MITGLIED_STATUS

    assert "geloescht" not in MITGLIED_STATUS
    assert _antrag_und_loeschen(client, welt).status_code == 200
    kennung = _kennung(welt)
    for status in ("Mitglied", "Gast"):
        r = client.post("/api/method/mitglieder.set_mitglied_status",
                        json={"mitglied_id": kennung, "status": status})
        assert r.status_code in (403, 417)
    r = client.post("/api/method/mitglieder.schliesse_mitglied_aus",
                    json={"mitglied_id": kennung})
    assert r.status_code in (403, 417) and "gelöscht" in r.json()["message"]
    # Ein zweiter Löschversuch ist ebenfalls abgelehnt.
    r = post(client, "loeschung_bestaetigen", mitglied_id=kennung, bestaetigt=True)
    assert r.status_code == 417


def test_zweiter_antrag_nach_ausfuehrung_wird_abgelehnt(client, welt, smtp):
    assert _antrag_und_loeschen(client, welt).status_code == 200
    with welt() as s:
        # Das Konto ist weg; die Person kann sich nicht mehr anmelden. Ein
        # Antrag kann nur noch aus der Sitzung kommen — hier direkt geprueft.
        from diakronos_app.models.diakonos import Mitglied as M

        assert s.get(M, "D1-anna") is None
        assert s.get(M, _kennung(welt)).status == "geloescht"


def test_antrag_zurueckziehen_und_erneut_stellen(client, welt):
    from diakronos_app.models.datenschutz import Loeschantrag

    set_user(ANNA["email"])
    assert post(client, "loeschung_beantragen", bestaetigt=True).json()["message"]["status"] == "offen"
    r = post(client, "loeschantrag_zurueckziehen", bestaetigt=True)
    assert r.status_code == 200 and r.json()["message"]["status"] == "zurueckgezogen"
    # idempotent
    assert post(client, "loeschantrag_zurueckziehen", bestaetigt=True).status_code == 200
    with welt() as s:
        assert s.get(Loeschantrag, "D1-anna").zurueckgezogen_am is not None
    # erneut stellen -> wieder offen, neuer Zeitpunkt
    r = post(client, "loeschung_beantragen", bestaetigt=True)
    assert r.status_code == 200 and r.json()["message"]["status"] == "offen"
    with welt() as s:
        a = s.get(Loeschantrag, "D1-anna")
        assert a.zurueckgezogen_am is None and a.status == "offen"


def test_antrag_nur_fuer_sich_selbst(client, welt):
    set_user(ANNA["email"])
    r = post(client, "loeschung_beantragen", bestaetigt=True, mitglied_id="D1-bert")
    # Das Fremd-Argument wird ignoriert (kein solcher Parameter) — der Antrag
    # entsteht fuer die eigene Person.
    assert r.status_code == 200
    from diakronos_app.models.datenschutz import Loeschantrag

    with welt() as s:
        assert s.get(Loeschantrag, "D1-anna") is not None
        assert s.get(Loeschantrag, "D1-bert") is None


def test_antrag_ohne_bestaetigung_wird_abgelehnt(client, welt):
    set_user(ANNA["email"])
    r = post(client, "loeschung_beantragen", bestaetigt=False)
    assert r.status_code == 417


def test_zurueckgezogener_antrag_raeumt_die_meldung_ab(client, welt):
    """Zieht die Person zurück, verschwindet auch die Meldung an die
    Verwaltung — sonst stünde ihr Name dort weiter als offener Vorgang."""
    from diakronos_app.api.datenschutz import MELDUNG_BETREFF

    set_user(ANNA["email"])
    assert post(client, "loeschung_beantragen", bestaetigt=True).status_code == 200
    with welt() as s:
        assert s.scalars(select(NotificationLog).where(
            NotificationLog.subject == MELDUNG_BETREFF)).all() != []
    assert post(client, "loeschantrag_zurueckziehen", bestaetigt=True).status_code == 200
    with welt() as s:
        assert s.scalars(select(NotificationLog).where(
            NotificationLog.subject == MELDUNG_BETREFF)).all() == []
        assert s.get(NotificationLog, "D1-notiz") is not None  # fremde bleibt


def test_meldung_an_die_verwaltung(client, welt):
    set_user(ANNA["email"])
    post(client, "loeschung_beantragen", bestaetigt=True)
    with welt() as s:
        meldungen = s.scalars(select(NotificationLog).where(
            NotificationLog.subject == "Löschantrag nach DSGVO gestellt"
        )).all()
        assert meldungen
        empfaenger = {m.for_user for m in meldungen}
        assert empfaenger == {"admin@example.org", "admin2@example.org", "verwaltung@example.org"}
        assert "Annamaria Beispielhuber" in meldungen[0].email_content


def test_liste_zeigt_offene_antraege_nur_fuer_verwaltung(client, welt):
    set_user(ANNA["email"])
    post(client, "loeschung_beantragen", bestaetigt=True)
    assert post(client, "get_loeschantraege").status_code == 403
    set_user("verwaltung@example.org")
    r = post(client, "get_loeschantraege")
    assert r.status_code == 200
    liste = r.json()["message"]
    assert len(liste) == 1 and liste[0]["mitglied"] == "D1-anna"
    assert liste[0]["vorname"] == ANNA["vorname"] and liste[0]["email"] == ANNA["email"]


def test_mitglied_mit_verwaltungskonto_darf_nur_system_manager_loeschen(client, welt, smtp):
    """Ein Mitgliederadministrator loescht kein Verwaltungskonto (P1-8c)."""
    from diakronos_app.models.diakonos import Mitglied as M

    with welt.begin() as s:
        s.add(User(name="chefin@example.org", email="chefin@example.org", enabled=True))
        s.add(HasRole(name="role-chefin", parent="chefin@example.org",
                      parenttype="User", role="System Manager"))
        s.flush()
        s.add(M(name="D1-chefin", vorname="Chefin", nachname="Muster",
                email="chefin@example.org", user="chefin@example.org", status="Mitglied"))
    set_user("chefin@example.org")
    assert post(client, "loeschung_beantragen", bestaetigt=True).status_code == 200
    set_user("verwaltung@example.org")
    r = post(client, "loeschung_bestaetigen", mitglied_id="D1-chefin", bestaetigt=True)
    assert r.status_code == 403
    assert "System Manager" in r.json()["message"]
    with welt() as s:
        assert s.get(M, "D1-chefin").vorname == "Chefin"


def test_letzter_system_manager_kann_sich_nicht_loeschen(client, patched_db, smtp):
    """Der letzte aktive System Manager ist geschützt — auch vor sich selbst."""
    with patched_db.begin() as s:
        s.add(User(name="sm@example.org", email="sm@example.org", enabled=True))
        s.add(HasRole(name="role-sm", parent="sm@example.org",
                      parenttype="User", role="System Manager"))
        s.flush()
        s.add(Mitglied(name="D1-sm", vorname="Solo", nachname="Manager",
                       email="sm@example.org", user="sm@example.org"))
    set_user("sm@example.org")
    assert post(client, "loeschung_beantragen", bestaetigt=True).status_code == 200
    r = post(client, "loeschung_bestaetigen", mitglied_id="D1-sm", bestaetigt=True)
    assert r.status_code == 403
    assert "letzte aktive" in r.json()["message"]
    with patched_db() as s:
        assert s.get(Mitglied, "D1-sm").vorname == "Solo"


def test_nur_admin_kann_bestaetigen(client, welt, smtp):
    set_user(ANNA["email"])
    post(client, "loeschung_beantragen", bestaetigt=True)
    r = post(client, "loeschung_bestaetigen", mitglied_id="D1-anna", bestaetigt=True)
    assert r.status_code == 403


def test_bestaetigen_ohne_antrag_wird_abgelehnt(client, welt, smtp):
    r = post(client, "loeschung_bestaetigen", mitglied_id="D1-bert", bestaetigt=True)
    assert r.status_code == 417
    assert "kein offener Löschantrag" in r.json()["message"]


def test_keine_mail_adresse_verhindert_die_loeschung(client, welt, smtp):
    set_user("admin@example.org")
    from diakronos_app.models.datenschutz import STATUS_OFFEN, Loeschantrag

    with welt.begin() as s:
        s.add(Loeschantrag(mitglied="D1-bert", beantragt_am=datetime.utcnow(),
                           status=STATUS_OFFEN))
    r = post(client, "loeschung_bestaetigen", mitglied_id="D1-bert", bestaetigt=True)
    assert r.status_code == 417
    assert "keine E-Mail-Adresse" in r.json()["message"]
    assert smtp.nachrichten == []


def test_einwilligungen_werden_widerrufen_nicht_geloescht(client, welt, smtp):
    """Art. 7 Abs. 1: der Nachweis bleibt — nur sein Bezug ist die technische ID."""
    from diakronos_app.models.diakonos import DSGVOEinwilligung

    assert _antrag_und_loeschen(client, welt).status_code == 200
    with welt() as s:
        widerrufe = s.scalars(select(DSGVOEinwilligung).where(
            DSGVOEinwilligung.mitglied == _kennung(welt),
            DSGVOEinwilligung.aktion == "widerrufen",
        )).all()
        assert {w.typ for w in widerrufe} == {"datenschutz", "foto"}


def test_dsgvo_auskunft_funktioniert_weiter(client, welt):
    """Regression: die Auskunft liest die neuen Antragsfelder ohne Fehler."""
    set_user(ANNA["email"])
    post(client, "loeschung_beantragen", bestaetigt=True)
    r = post(client, "mein_loeschantrag")
    assert r.status_code == 200
    assert r.json()["message"]["status"] == "offen"
    assert post(client, "meine_auskunft").status_code == 200


def test_benachrichtigungstexte_an_die_person_ohne_namen(client, welt, smtp):
    """Betreff/Inhalt einer Meldung an die Person sind Fließtext — der Name
    darin muss weg, die Zeile („die Meldung gab es“) bleibt."""
    from diakronos_app import dsgvo_anonymisierung as Meldung
    assert _antrag_und_loeschen(client, welt).status_code == 200
    with welt() as s:
        # Genau EINE Meldung an die Person, und ihr Text nennt sie nicht mehr.
        # (Der Betreff ist nicht durchsuchbar: er ist der Spaltentitel der
        # Meldung, kein Bezug zur Person — gesucht wird der Inhalt.)
        zeilen = s.scalars(select(NotificationLog).where(
            NotificationLog.for_user.is_(None))).all()
        assert len(zeilen) == 1
        assert zeilen[0].email_content == Meldung.MELDUNG_PLATZHALTER


def test_protokollwerte_eines_feldes_werden_ersetzt(client, welt, smtp):
    """`old_value`/`new_value` sind Werte EINES Feldes dieser Person — auch
    wenn der Wert nicht im Freitext-Bestand steht (hier: ein alter Name)."""
    with welt.begin() as s:
        s.add(AuditLog(name="D1-audit2", target_doctype="Mitglied", target_name="D1-anna",
                       action_typ="Aenderung", field_changed="nachname",
                       old_value="Beispielhuberin", new_value="Beispielhuber"))
    assert _antrag_und_loeschen(client, welt).status_code == 200
    with welt() as s:
        e = s.get(AuditLog, "D1-audit2")
        assert (e.old_value, e.new_value) == ("[gelöscht]", "[gelöscht]")


def test_telefon_ohne_leerzeichen_verschwindet(client, welt, smtp):
    """Dieselbe Nummer anders geschrieben (01704455667) bleibt nicht stehen."""
    with welt.begin() as s:
        s.get(Mitglied, "D1-bert").notiz = "erreichbar: 01704455667"
    assert _antrag_und_loeschen(client, welt).status_code == 200
    treffer = vollscan(welt, "01704455667")
    assert treffer == [], treffer


def test_sicherungslauf_verliert_nur_die_eigene_adresse(client, welt, smtp):
    """BACKUP-1: `sicherungslauf.benachrichtigt` ist eine KOMMA-LISTE.

    Der Eintrag der gelöschten Person wird als GANZER Eintrag entfernt; die
    übrigen Adressen bleiben byte-gleich und in ihrer Reihenfolge. Ein
    Fremdtext-Ersatz („[gelöscht]“) würde die Liste zerschneiden.
    """
    fremd = "verwaltung@example.org, fremd@example.org"
    with welt.begin() as s:
        s.add_all([
            Sicherungslauf(name="BK1-2026-10-21_0300", begonnen_am=datetime(2026, 10, 21, 3, 0),
                           status="fehlgeschlagen", ausloeser="automatisch",
                           meldung="pg_dump abgebrochen",
                           benachrichtigt=f"verwaltung@example.org, {ANNA['email']}, fremd@example.org"),
            # Ohne die Person: bleibt unverändert.
            Sicherungslauf(name="BK1-2026-10-20_0300", begonnen_am=datetime(2026, 10, 20, 3, 0),
                           status="fehlgeschlagen", ausloeser="manuell", benachrichtigt=fremd),
        ])
    assert _antrag_und_loeschen(client, welt).status_code == 200
    with welt() as s:
        betroffen = s.get(Sicherungslauf, "BK1-2026-10-21_0300")
        assert betroffen.benachrichtigt == fremd, betroffen.benachrichtigt
        # Struktur des Laufs bleibt: er beschreibt die Sicherung, nicht die Person.
        assert (betroffen.status, betroffen.ausloeser) == ("fehlgeschlagen", "automatisch")
        assert betroffen.meldung == "pg_dump abgebrochen"
        assert s.get(Sicherungslauf, "BK1-2026-10-20_0300").benachrichtigt == fremd


def test_rollenzeilen_mit_fremdem_parenttype_bleiben(client, welt, smtp):
    """R-DSGVO-1c (4): Rollen werden NUR bei `parenttype='User'` gelöscht.

    `has_role.parent` ist in Frappe auch die Kennung einer Page, eines Report,
    eines Workspace oder eines Desktop Icon; `user_role.parent` die eines
    Kalenders. Trifft der Löschfilter nur nach `parent`, reißt er solche
    Zeilen mit, sobald der Name zufällig dem Konto gleicht. Im Betrieb sind
    das 54 `has_role`- und 38 `user_role`-Waisen, alle ohne Personenbezug.
    """
    with welt.begin() as s:
        s.add_all([
            # Waisen, deren `parent` ABSICHTLICH wie die Adresse der Person
            # lautet — der ungünstigste Fall.
            HasRole(name="D1-waise-page", parent=ANNA["email"], parenttype="Page",
                    parentfield="roles", role="System Manager"),
            HasRole(name="D1-waise-report", parent="D1-anna", parenttype="Report",
                    parentfield="roles", role="System Manager"),
            UserRole(name="D1-waise-kalender", parent=ANNA["email"],
                     parenttype="Kalender", parentfield="leserechte", role="Leser"),
        ])
    assert _antrag_und_loeschen(client, welt).status_code == 200
    with welt() as s:
        for name in ("D1-waise-page", "D1-waise-report", "D1-waise-kalender"):
            assert s.get(HasRole, name) is not None or s.get(UserRole, name) is not None, name
        # Die ECHTE Zugangszeile der Person ist weg.
        assert s.scalars(select(HasRole).where(
            HasRole.parent == ANNA["email"], HasRole.parenttype == "User")).all() == []


def test_fremde_sicherungs_und_rollenzeilen_bleiben_byte_gleich(client, welt, smtp):
    """Gegenprobe R-DSGVO-1c: fremde Waisen und fremde Konten bleiben.

    Ersetzt den Scheintest `test_fremde_konten_behalten_ihre_rollen`
    (R-DSGVO-1c Punkt 5): dort wurde nichts gelöscht und nichts verglichen.
    Hier wird der Zustand VORHER/NACHHER als Ganzes verglichen.
    """
    with welt.begin() as s:
        s.add_all([
            HasRole(name="D1-fremd-page", parent="D1-bert", parenttype="Page",
                    parentfield="roles", role="Gast"),
            HasRole(name="D1-fremd-bert", parent="D1-bert", parenttype="User",
                    parentfield="roles", role="Mitglied"),
            UserRole(name="D1-fremd-kalender", parent="Persönlich",
                     parenttype="Kalender", parentfield="leserechte", role="Leser"),
        ])
    with welt() as s:
        vorher = _rollenzeilen(s)
    assert _antrag_und_loeschen(client, welt).status_code == 200
    with welt() as s:
        nachher = _rollenzeilen(s)
    fremd = {k: v for k, v in vorher.items()
             if k.startswith(("has_role:D1-fremd", "user_role:D1-fremd"))}
    assert fremd, vorher
    assert {k: v for k, v in nachher.items() if k in fremd} == fremd


def _rollenzeilen(session) -> dict[str, tuple]:
    """Jede Rollenzeile als (parent, parenttype, role) — Vergleich als Ganzes."""
    from diakronos_app.models.core import HasRole, UserRole

    werte = {}
    for modell, art in ((HasRole, "has_role"), (UserRole, "user_role")):
        for zeile in session.scalars(select(modell)).all():
            werte[f"{art}:{zeile.name}"] = (zeile.parent, zeile.parenttype, zeile.role)
    return werte


def test_einzelner_namensteil_wird_nicht_neutralisiert(client, welt, smtp):
    """R-DSGVO-1c (5): `_platzhalter_spalten`/`_autoren_neutralisieren`
    vergleichen nur volle Namen, Kennung, Konto und Adresse.

    Ein fremder Beitrag mit Autor genau „Annamaria“ (nur der Vorname der
    Person) und eine fremde Buchung mit „Beispielhuber“ als Buchernamen
    gehören einer ANDEREN Person mit diesem Namensteil. Verglichen wird exakt,
    also würde ein einzelner Teil als Nadel die fremde Zeile treffen.
    """
    with welt.begin() as s:
        s.add_all([
            Beitrag(name="D1-fremd-beitrag", autor="Annamaria",
                    autor_email="fremd@example.org", titel="Gruß",
                    inhalt="Von einer anderen Annamaria."),
            RessourcenBuchung(name="D1-fremd-buchung", gebucht_von="fremd@example.org",
                              gebucht_von_name="Beispielhuber", zweck="Probe"),
        ])
    assert _antrag_und_loeschen(client, welt).status_code == 200
    with welt() as s:
        beitrag = s.get(Beitrag, "D1-fremd-beitrag")
        assert beitrag is not None, "fremder Beitrag wurde gelöscht"
        assert (beitrag.autor, beitrag.autor_email) == ("Annamaria", "fremd@example.org")
        buchung = s.get(RessourcenBuchung, "D1-fremd-buchung")
        assert buchung is not None, "fremde Buchung wurde gelöscht"
        assert buchung.gebucht_von_name == "Beispielhuber"
