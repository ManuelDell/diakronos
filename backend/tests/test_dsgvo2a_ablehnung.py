"""DSGVO-2a: Die Verwaltung lehnt einen Löschantrag ab.

Zusagen der Karte (je Test eine Zusage):

* Rechte wie beim Bestätigen — nur Verwaltung; ein Mitglied mit Verwaltungskonto
  nur durch einen System Manager; der letzte Verwaltungszugang ist geschützt.
* Begründung ist PFLICHT (nicht leer, keine Steuerzeichen), wird am Antrag
  gespeichert und steht im Wortlaut in der Mail an die Person.
* Reihenfolge wie beim Bestätigen: Status + flush → Mail → Commit; bei
  Mailfehler bleibt der Antrag `offen` und es wird NICHTS geändert.
* Ohne eingerichteten Mailversand: klare Meldung, keine Ablehnung.
* AuditLog-Eintrag OHNE Begründungstext (kann Gesundheitsdaten enthalten).
* Das Mitglied sieht Status und Begründung; danach ist ein neuer Antrag möglich.
"""
from __future__ import annotations

import re
from datetime import date

import pytest

from test_ma1_mailversand import _smtp_einrichten
from sqlalchemy import select

from diakronos_app.frappe_compat.session import set_user
from diakronos_app.models.core import HasRole, NotificationLog, User
from diakronos_app.models.diakonos import AuditLog, Mitglied

PFAD = "/api/method/diakronos.diakonos.api.datenschutz."
ADMIN = "admin@example.org"
ANNA_MAIL = "annamaria.beispielhuber@example.org"
GRUND = "Es fehlt noch die Zustimmung des Vorstands; bitte im Januar erneut stellen."


def post(client, fn, **kw):
    return client.post(PFAD + fn, json=kw)


def _beantragen(client):
    """Die Person stellt fuer SICH einen Antrag (Setzen des Sitzungsnutzers)."""
    set_user(ANNA_MAIL)
    assert post(client, "loeschung_beantragen", bestaetigt=True).status_code == 200
    set_user(ADMIN)


@pytest.fixture()
def smtp(monkeypatch, patched_db):
    """Fake-SMTP an der Naht; `smtp.fehler` macht den Versand kaputt."""
    from diakronos_app import mailversand

    class Fake:
        def __init__(self):
            self.nachrichten = []
            self.fehler = None

        def ehlo(self):
            pass

        def has_extn(self, name):
            return True

        def starttls(self):
            pass

        def login(self, *_a):
            pass

        def send_message(self, nachricht):
            if self.fehler is not None:
                raise self.fehler
            self.nachrichten.append(nachricht)

        def quit(self):
            pass

    _smtp_einrichten(patched_db)
    fake = Fake()
    monkeypatch.setattr(mailversand, "VERBINDUNG", fake)
    return fake


@pytest.fixture()
def welt(patched_db):
    """Verwaltung, Person mit offenem Antrag und eine zweite Person ohne."""
    with patched_db.begin() as s:
        for konto, rolle in (
            (ADMIN, "System Manager"),
            ("admin2@example.org", "System Manager"),
            ("verwaltung@example.org", "Mitgliederadministrator"),
        ):
            s.add(User(name=konto, email=konto, full_name="Verwaltung " + konto, enabled=True))
            s.add(HasRole(name=f"role-{konto}", parent=konto, parenttype="User", role=rolle))
        s.add(User(name=ANNA_MAIL, email=ANNA_MAIL, full_name="Annamaria Beispielhuber",
                   enabled=True))
        s.add(HasRole(name="role-anna", parent=ANNA_MAIL, parenttype="User", role="Mitglied"))
        s.flush()
        s.add_all([
            Mitglied(name="D2a-anna", vorname="Annamaria", nachname="Beispielhuber",
                     email=ANNA_MAIL, telefonnummer="0170 4455667",
                     geburtstag=date(1990, 5, 4), status="Mitglied",
                     user=ANNA_MAIL, mitglied_seit=date(2020, 1, 1)),
            Mitglied(name="D2a-bert", vorname="Bert", nachname="Berger"),
        ])
    set_user(ADMIN)
    return patched_db


def _antrag(db, mitglied="D2a-anna"):
    from diakronos_app.models.datenschutz import Loeschantrag

    with db() as s:
        return s.get(Loeschantrag, mitglied)


def _ablehnen(client, **kw):
    werte = {"mitglied_id": "D2a-anna", "begruendung": GRUND, "bestaetigt": True}
    werte.update(kw)
    return post(client, "loeschantrag_ablehnen", **werte)


# ── Erfolgsweg ──────────────────────────────────────────────────────────────


def test_ablehnung_setzt_status_grund_zeitpunkt_und_admin(client, welt, smtp):
    _beantragen(client)
    r = _ablehnen(client)
    assert r.status_code == 200, r.text
    antwort = r.json()["message"]
    assert antwort["status"] == "abgelehnt"
    assert antwort["ablehnung_grund"] == GRUND
    assert antwort["ok"] is True
    a = _antrag(welt)
    assert a.status == "abgelehnt"
    assert a.abgelehnt_am is not None
    assert a.abgelehnt_von == ADMIN
    # Die Person ist NICHT gelöscht und behält alles.
    with welt() as s:
        m = s.get(Mitglied, "D2a-anna")
        assert m.vorname == "Annamaria" and m.email == ANNA_MAIL
        assert m.status == "Mitglied" and m.user == ANNA_MAIL


def test_mail_enthaelt_grund_erneuten_antrag_und_aufsichtsbehoerde(client, welt, smtp):
    _beantragen(client)
    assert _ablehnen(client).status_code == 200
    assert len(smtp.nachrichten) == 1
    mail = smtp.nachrichten[0]
    assert mail["To"] == ANNA_MAIL
    koerper = mail.get_content()
    assert GRUND in koerper
    assert "erneut stellen" in koerper
    assert "Aufsichtsbehörde" in koerper and "Art. 77" in koerper
    # Als Text gequotet, nicht als Kopfzeile gesprengt: kein CR im Betreff.
    assert "\n" not in mail["Subject"] and "\r" not in mail["Subject"]


def test_mitglied_sieht_status_und_begruendung(client, welt, smtp):
    _beantragen(client)
    assert _ablehnen(client).status_code == 200
    set_user(ANNA_MAIL)
    r = post(client, "mein_loeschantrag")
    assert r.status_code == 200
    stand = r.json()["message"]
    assert stand["status"] == "abgelehnt"
    assert stand["ablehnung_grund"] == GRUND
    assert stand["abgelehnt_am"] is not None
    # Wer abgelehnt hat, ist Sache der Verwaltung, nicht der Person.
    assert "abgelehnt_von" not in stand


def test_verwaltung_sieht_wer_abgelehnt_hat(client, welt, smtp):
    _beantragen(client)
    assert _ablehnen(client).status_code == 200
    set_user("verwaltung@example.org")
    liste = post(client, "get_loeschantraege", status="abgelehnt").json()["message"]
    assert len(liste) == 1
    assert liste[0]["status"] == "abgelehnt"
    assert liste[0]["abgelehnt_von"] == ADMIN
    # Ein abgelehnter Antrag steht nicht mehr auf der Arbeitsliste „offen“.
    offen = post(client, "get_loeschantraege").json()["message"]
    assert offen == []


def test_meldung_an_die_verwaltung_wird_abgeraeumt(client, welt, smtp):
    _beantragen(client)
    with welt() as s:
        assert s.scalars(select(NotificationLog).where(
            NotificationLog.document_name == "D2a-anna")).all()
    assert _ablehnen(client).status_code == 200
    with welt() as s:
        rest = s.scalars(select(NotificationLog).where(
            NotificationLog.document_type == "Mitglied",
            NotificationLog.document_name == "D2a-anna",
        )).all()
    assert rest == []


def test_auditlog_ohne_begruendungstext(client, welt, smtp):
    _beantragen(client)
    assert _ablehnen(client).status_code == 200
    with welt() as s:
        zeilen = s.scalars(select(AuditLog).where(
            AuditLog.action_typ == "Loeschantrag abgelehnt")).all()
        assert len(zeilen) == 1
        zeile = zeilen[0]
        assert zeile.actor == ADMIN
        assert zeile.target_name == "D2a-anna"
        # Weder Begründung noch Teile davon im Protokoll — auch nicht in den
        # Freitextfeldern, die das Audit-Log sonst mitschreibt.
        werte = " ".join(str(getattr(zeile, c.key) or "") for c in zeile.__table__.columns)
        assert "Zustimmung des Vorstands" not in werte
        assert GRUND not in werte


def test_erneuter_antrag_nach_ablehnung(client, welt, smtp):
    _beantragen(client)
    assert _ablehnen(client).status_code == 200
    set_user(ANNA_MAIL)
    r = post(client, "loeschung_beantragen", bestaetigt=True)
    assert r.status_code == 200, r.text
    assert r.json()["message"]["status"] == "offen"
    a = _antrag(welt)
    assert a.status == "offen"
    # Der neue Vorgang beginnt bei der Verwaltung ohne alte Begründung.
    assert a.ablehnung_grund is None and a.abgelehnt_am is None and a.abgelehnt_von is None
    # Und er ist erneut prüfbar: die Verwaltung kann ihn wieder ablehnen.
    set_user(ADMIN)
    assert _ablehnen(client, begruendung="Zweite Prüfung.").status_code == 200


# ── Rechte ─────────────────────────────────────────────────────────────────


def test_nur_verwaltung_darf_ablehnen(client, welt, smtp):
    _beantragen(client)
    set_user(ANNA_MAIL)
    assert _ablehnen(client).status_code == 403
    set_user("bert@example.org")
    assert _ablehnen(client).status_code == 403
    a = _antrag(welt)
    assert a.status == "offen" and smtp.nachrichten == []


def test_mitglied_mit_verwaltungskonto_nur_system_manager(client, welt, smtp):
    """P1-8c gilt auch hier: ein Mitgliederadministrator lehnt kein
    Verwaltungskonto ab."""
    with welt.begin() as s:
        s.add(User(name="chefin@example.org", email="chefin@example.org", enabled=True))
        s.add(HasRole(name="role-chefin", parent="chefin@example.org",
                      parenttype="User", role="System Manager"))
        s.flush()
        s.add(Mitglied(name="D2a-chefin", vorname="Chefin", nachname="Muster",
                       email="chefin@example.org", user="chefin@example.org",
                       status="Mitglied"))
    set_user("chefin@example.org")
    assert post(client, "loeschung_beantragen", bestaetigt=True).status_code == 200
    set_user("verwaltung@example.org")
    r = _ablehnen(client, mitglied_id="D2a-chefin")
    assert r.status_code == 403
    assert "System Manager" in r.json()["message"]
    assert _antrag(welt, "D2a-chefin").status == "offen"
    assert smtp.nachrichten == []


def test_letzter_system_manager_schuetzt_sich_selbst(client, patched_db, smtp):
    with patched_db.begin() as s:
        s.add(User(name="sm@example.org", email="sm@example.org", enabled=True))
        s.add(HasRole(name="role-sm", parent="sm@example.org",
                      parenttype="User", role="System Manager"))
        s.flush()
        s.add(Mitglied(name="D2a-sm", vorname="Solo", nachname="Manager",
                       email="sm@example.org", user="sm@example.org"))
    set_user("sm@example.org")
    assert post(client, "loeschung_beantragen", bestaetigt=True).status_code == 200
    r = _ablehnen(client, mitglied_id="D2a-sm")
    assert r.status_code == 403
    assert "letzte aktive" in r.json()["message"]


# ── Pflichtfelder und Fehlerfolgen ─────────────────────────────────────────


def test_ablehnung_ohne_begruendung_wird_abgelehnt(client, welt, smtp):
    _beantragen(client)
    for grund in ("", "   ", "\n\t "):
        r = _ablehnen(client, begruendung=grund)
        assert r.status_code == 417, r.text
        assert "Begründung" in r.json()["message"]
    r = post(client, "loeschantrag_ablehnen",
             mitglied_id="D2a-anna", bestaetigt=True)
    assert r.status_code == 417
    assert _antrag(welt).status == "offen" and smtp.nachrichten == []


def test_steuerzeichen_in_der_begruendung_werden_abgelehnt(client, welt, smtp):
    _beantragen(client)
    for grund in ("Erledigt\x00bitte später", "Zeile\x0bumbruch", "Glos\x1fe"):
        r = _ablehnen(client, begruendung=grund)
        assert r.status_code == 417, (grund, r.text)
        assert "Steuerzeichen" in r.json()["message"]
    assert smtp.nachrichten == []


def test_absaetze_und_umlaute_sind_erlaubt(client, welt, smtp):
    """TAB und Zeilenumbrüche gehören zu normalen Absätzen; Ränder fallen weg."""
    text = ("Erster Absatz mit Umlauten (äöü).\n\n"
            "Zweiter Absatz\tmit Tabulator.")
    _beantragen(client)
    r = _ablehnen(client, begruendung="\n  " + text + "  \n")
    assert r.status_code == 200, r.text
    assert _antrag(welt).ablehnung_grund == text


def test_zu_lange_begruendung(client, welt, smtp):
    from diakronos_app.models.datenschutz import GRUND_MAX

    _beantragen(client)
    r = _ablehnen(client, begruendung="x" * (GRUND_MAX + 1))
    assert r.status_code == 417
    assert "zu lang" in r.json()["message"]


def test_ablehnung_ohne_antrag(client, welt, smtp):
    r = _ablehnen(client, mitglied_id="D2a-bert")
    assert r.status_code == 417
    assert "kein offener Löschantrag" in r.json()["message"]


def test_ablehnung_ohne_bestaetigung(client, welt, smtp):
    _beantragen(client)
    r = _ablehnen(client, bestaetigt=False)
    assert r.status_code == 417
    assert "bestätigen" in r.json()["message"]
    assert _antrag(welt).status == "offen"


def test_mailfehler_laesst_den_antrag_offen(client, welt, smtp):
    """Reihenfolge: Status + flush → Mail → Commit. Mailfehler → Rollback."""
    _beantragen(client)
    smtp.fehler = OSError("Verbindung weg")
    r = _ablehnen(client)
    assert r.status_code == 417
    assert "nichts abgelehnt" in r.json()["message"]
    a = _antrag(welt)
    assert a.status == "offen"
    assert a.abgelehnt_am is None and a.ablehnung_grund is None and a.abgelehnt_von is None
    with welt() as s:
        assert s.scalars(select(AuditLog).where(
            AuditLog.action_typ == "Loeschantrag abgelehnt")).all() == []
    # Nach dem Fehler ist die Ablehnung erneut versuchbar.
    smtp.fehler = None
    assert _ablehnen(client).status_code == 200
    assert len(smtp.nachrichten) == 1


def test_ohne_mailversand_keine_ablehnung(client, welt, monkeypatch):
    """Ohne eingerichteten Mailversand wird NICHTS abgelehnt (fail closed).

    Die Testnaht ist `mailversand.ist_konfiguriert` — der echte Weg über eine
    unvollständige DB-Zeile ist in `test_ma1_mailversand.py` belegt; hier geht
    es um die Folge für den Antrag.
    """
    from diakronos_app import mailversand

    _beantragen(client)
    monkeypatch.setattr(mailversand, "ist_konfiguriert", lambda: False)
    r = _ablehnen(client)
    assert r.status_code == 417
    # N3: derselbe neutrale Text wie beim Bestätigen.
    assert "Mailversand ist nicht eingerichtet" in r.json()["message"]
    assert "Löschantrag" in r.json()["message"]
    assert _antrag(welt).status == "offen"


def test_ohne_adresse_keine_ablehnung(client, welt, smtp):
    """Ohne hinterlegte Adresse kann die Begründung nicht zugestellt werden."""
    _beantragen(client)
    with welt.begin() as s:
        s.get(Mitglied, "D2a-anna").email = ""
    r = _ablehnen(client)
    assert r.status_code == 417
    assert "keine E-Mail-Adresse" in r.json()["message"]
    assert smtp.nachrichten == []
    assert _antrag(welt).status == "offen"


def test_zurueckziehen_nach_ablehnung_ist_kein_weg(client, welt, smtp):
    _beantragen(client)
    assert _ablehnen(client).status_code == 200
    set_user(ANNA_MAIL)
    r = post(client, "loeschantrag_zurueckziehen", bestaetigt=True)
    assert r.status_code == 417
    assert "abgelehnt" in r.json()["message"]
    assert _antrag(welt).status == "abgelehnt"


#: Die In-App-Meldung aus `admin_hub` („Mitglied angelegt: …“). Sie hat
#: DENSELBEN Dokumentbezug wie der Löschantrag (Mitglied), gehört aber einem
#: anderen Vorgang — sie darf beim Aufräumen der Antragsmeldung nicht
#: mitgerissen werden (N1, R-DSGVO-2a).
FREMDE_MELDUNG = "Mitglied angelegt: Annamaria Beispielhuber"


def _fremde_meldung(db) -> None:
    """Eine Meldung eines ANDEREN Vorgangs zum selben Mitglied anlegen."""
    from diakronos_app.benachrichtigungen import schreibe_meldung

    with db.begin() as s:
        assert schreibe_meldung(
            for_user="verwaltung@example.org", subject=FREMDE_MELDUNG,
            inhalt="Anmeldung <b>D2a-anna</b> bestätigt.<br>Mitglied: <b>D2a-anna</b>",
            document_type="Mitglied", document_name="D2a-anna",
        )
        s.flush()


def _meldungen(db, *betreffe) -> list[str]:
    with db() as s:
        return sorted(
            str(z.subject) for z in s.scalars(select(NotificationLog).where(
                NotificationLog.document_type == "Mitglied",
                NotificationLog.document_name == "D2a-anna",
                NotificationLog.subject.in_(betreffe),
            )).all()
        )


def test_ablehnen_laesst_fremde_meldungen_stehen(client, welt, smtp):
    """N1: Aufgeräumt wird NUR die Antragsmeldung — fremde bleiben.

    Der Filter stand auf „jede Meldung mit Betreff“ und löschte damit auch
    „Mitglied angelegt: …“ aus dem Postfach der Verwaltung.
    """
    _beantragen(client)
    _fremde_meldung(welt)
    assert _ablehnen(client).status_code == 200
    assert _meldungen(welt, FREMDE_MELDUNG) == [FREMDE_MELDUNG]
    with welt() as s:
        antrag = s.scalars(select(NotificationLog).where(
            NotificationLog.document_type == "Mitglied",
            NotificationLog.document_name == "D2a-anna",
        )).all()
    assert [str(z.subject) for z in antrag] == [FREMDE_MELDUNG]


def test_zurueckziehen_laesst_fremde_meldungen_stehen(client, welt, smtp):
    """N1: dasselbe beim Zurückziehen (beide Aufrufer des Aufräumens)."""
    _beantragen(client)
    _fremde_meldung(welt)
    set_user(ANNA_MAIL)
    r = post(client, "loeschantrag_zurueckziehen", bestaetigt=True)
    assert r.status_code == 200, r.text
    with welt() as s:
        zeilen = s.scalars(select(NotificationLog).where(
            NotificationLog.document_type == "Mitglied",
            NotificationLog.document_name == "D2a-anna",
        )).all()
    # Die Antragsmeldung ist weg, die fremde steht noch.
    assert [str(z.subject) for z in zeilen] == [FREMDE_MELDUNG]


def test_bestaetigen_entfernt_den_namen_auch_aus_fremden_meldungen(client, welt, smtp):
    """Beim BESTÄTIGEN geht der Name der Person aus ALLEN Meldungen zum Mitglied.

    Abgrenzung zu N1: Beim Aufräumen/Entpersonalisieren der Antragsmeldung
    bleiben fremde Meldungen unangetastet (`test_ablehnen_...`,
    `test_zurueckziehen_...`). Die Anonymisierung selbst greift dagegen weiter:
    „Mitglied angelegt: Annamaria Beispielhuber“ trägt den Namen der Person,
    und nach der Löschung darf er nirgends mehr stehen — Betreff und Text
    werden durch den Platzhalter ersetzt (`_benachrichtigungen_neutralisieren`).
    """
    from diakronos_app.dsgvo_anonymisierung import MELDUNG_PLATZHALTER

    _beantragen(client)
    _fremde_meldung(welt)
    r = post(client, "loeschung_bestaetigen", mitglied_id="D2a-anna", bestaetigt=True)
    assert r.status_code == 200, r.text
    with welt() as s:
        zeilen = s.scalars(select(NotificationLog).where(
            NotificationLog.document_type == "Mitglied",
            NotificationLog.document_name == r.json()["message"]["mitglied"],
        )).all()
    assert zeilen, "Die Meldung wurde nicht umgehängt"
    for zeile in zeilen:
        assert str(zeile.subject) == MELDUNG_PLATZHALTER
        assert str(zeile.email_content) == MELDUNG_PLATZHALTER


def test_bestaetigen_nach_ablehnung_loescht_nichts(client, welt, smtp):
    """Eine Ablehnung ist kein offener Antrag — die Löschung bleibt aus."""
    from diakronos_app.models.diakonos import Mitglied as M

    _beantragen(client)
    assert _ablehnen(client).status_code == 200
    r = post(client, "loeschung_bestaetigen", mitglied_id="D2a-anna", bestaetigt=True)
    assert r.status_code == 417
    with welt() as s:
        assert s.get(M, "D2a-anna").vorname == "Annamaria"


# ── N2 (R-DSGVO-2a, Nacharbeit): kein Personenbezug im Bestätigungsweg ─────


def test_loeschung_nach_ablehnung_entfernt_die_alte_begruendung(client, welt, smtp):
    """N2: ablehnen mit Grund → neuer Antrag → bestätigen → Grund ist überall weg.

    Die Begründung der Ablehnung ist für die Verwaltung formuliert und kann
    alles enthalten („Frau Beispielhuber ist erkrankt“). Nach der
    Anonymisierung darf sie in KEINER Textspalte mehr stehen — der Vollscan
    der Löschung sucht genau danach.

    Der Suchwert enthält KEINEN Namen und keine Adresse: nur so belegt der
    Test, dass die Spalte selbst geleert wird. Sonst könnte die
    Fremdtext-Ersetzung den Treffer zufällig beseitigen und die falsche
    Inventar-Entscheidung (`keep`) bliebe unentdeckt.
    """
    from test_dsgvo1_anonymisierung import vollscan

    grund = "Nachweis der Erkrankung liegt vor; zum Schutz der Person keine Löschung"
    _beantragen(client)
    assert _ablehnen(client, begruendung=grund).status_code == 200
    # Der Scan ist scharf: vor der Löschung MUSS er den Grund finden.
    assert vollscan(welt, grund), "Der Vollscan findet den Grund nicht — Nachweis wertlos"
    set_user(ANNA_MAIL)
    assert post(client, "loeschung_beantragen", bestaetigt=True).status_code == 200
    set_user(ADMIN)
    r = post(client, "loeschung_bestaetigen", mitglied_id="D2a-anna", bestaetigt=True)
    assert r.status_code == 200, r.text
    assert vollscan(welt, grund) == []
    kennung = r.json()["message"]["mitglied"]
    from diakronos_app.models.datenschutz import Loeschantrag

    with welt() as s:
        a = s.get(Loeschantrag, kennung)
        assert a is not None
        assert a.ablehnung_grund is None and a.abgelehnt_am is None
        # Zeitpunkt/Administrator der Entscheidung bleiben als Nachweis.
        assert a.freigegeben_von == ADMIN and a.anonymisiert_am is not None


def test_begruendung_gilt_als_personenbezug_im_inventar():
    """N2: `loeschantrag.ablehnung_grund` wird beim Löschen GELEERT.

    Sie darf nicht als `keep` stehen bleiben: der Freitext ist für die
    Verwaltung geschrieben („Frau X ist erkrankt“) und nennt Personen. Der
    Nachweis der Entscheidung sind Zeitpunkt, Konto und Status — nicht der
    Wortlaut. Der BESTÄTIGENDE liest die Zeile in derselben Transaktion und
    leert sie selbst (`loeschung_bestaetigen`); dieser Eintrag ist die
    Entscheidung, die bei jeder künftigen Löschung gilt.
    """
    from diakronos_app import dsgvo_anonymisierung as modul

    art = modul.SPALTEN["loeschantrag"]["ablehnung_grund"][0]
    assert art != "keep", "Die Ablehnungsbegründung ist ein Freitext — sie wird geleert"
    assert art in ("protokoll", "mitglied_platzhalter"), art


def test_inventar_leert_die_begruendung_auch_ohne_den_bestaetigenden(client, welt, smtp):
    """N2: der Inventar-Eintrag wirkt selbst — nicht nur die Zeile im Endpunkt.

    Ohne diesen Nachweis wäre `protokoll` an `loeschantrag` ein toter
    Buchstabe: der Bestätigende leert das Feld ohnehin, ein Fehler im
    Inventar bliebe unbemerkt.
    """
    from diakronos_app import dsgvo_anonymisierung as modul
    from diakronos_app.models.datenschutz import Loeschantrag

    _beantragen(client)
    assert _ablehnen(client, begruendung="Nachweis der Erkrankung liegt vor").status_code == 200
    with welt.begin() as s:
        a = s.get(Loeschantrag, "D2a-anna")
        assert a.ablehnung_grund == "Nachweis der Erkrankung liegt vor"
        bestand = modul.bestand_erheben(s, "D2a-anna", {ANNA_MAIL})
        zaehler = modul._eigene_protokolle(s, bestand, bestand.mitglied)
        assert zaehler.get("loeschantrag.ablehnung_grund") == 1, zaehler
        s.flush()
        # Die UPDATE-Anweisung lief ohne ORM-Objekt: den Stand neu von der
        # Datenbank lesen, statt dem zwischengespeicherten Objekt zu glauben.
        s.expire_all()
        assert s.get(Loeschantrag, "D2a-anna").ablehnung_grund is None


def test_abgelehnt_am_und_grund_bleiben_nach_der_abgelehnten_entscheidung(client, welt, smtp):
    """Gegenprobe: solange nicht gelöscht wurde, bleibt die Begründung lesbar.

    Sonst wäre die Löschung ein Betriebsunfall der Anzeige (Art. 15).
    """
    _beantragen(client)
    assert _ablehnen(client).status_code == 200
    set_user(ANNA_MAIL)
    stand = post(client, "mein_loeschantrag").json()["message"]
    assert stand["ablehnung_grund"] == GRUND

