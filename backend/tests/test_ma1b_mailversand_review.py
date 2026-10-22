"""MAIL-1b: Nacharbeit aus dem Review R-MAIL-1 (N1, N2, N5).

Je Zusage ein Test, der VOR dem Fix rot war:

N1  Ein gespeichertes Passwort geht nie an einen anderen Server oder ein
    anderes Konto: weichen ``host`` oder ``benutzername`` vom gespeicherten
    Stand ab, wird es WEDER für die Testmail noch beim Speichern
    weiterverwendet.
    -> ``test_testmail_mit_anderem_host_nutzt_das_passwort_nicht``,
       ``test_testmail_mit_anderem_benutzer_nutzt_das_passwort_nicht``,
       ``test_speichern_mit_anderem_host_verwirft_das_passwort``
N2  Steuerzeichen in Absendername, Absenderadresse, Server und Benutzer
    werden abgelehnt; ein Header-Fehler endet als Mailfehler (417), nie als
    500 — die Löschbestätigung rollt dann zurück.
    -> ``test_steuerzeichen_werden_abgelehnt``,
       ``test_header_fehler_endet_als_mailfehler``,
       ``test_kaputter_absendername_legt_loeschung_nicht_lahm``
N5  SMTP-Antwortfehler (550/535) sind eine eigene Kategorie „abgelehnt“;
    „nicht erreichbar“ gibt es nur bei Verbindungsfehlern.
    -> ``test_absender_abgelehnt_ist_eigene_kategorie``,
       ``test_anmeldung_abgelehnt_ist_eigene_kategorie`` (hier: Meldung),
       ``test_nicht_erreichbar_nur_bei_verbindungsfehlern``

Kein Test baut eine Netzverbindung auf: Transport ist ``mailversand.VERBINDUNG``.
"""
from __future__ import annotations

import smtplib

import pytest

from diakronos_app import mailversand
from diakronos_app import smtp_einstellungen as modul
from diakronos_app.models.smtp import SMTP_EINSTELLUNGEN_NAME, SmtpEinstellungen

API = "diakronos.diakronos.api.mailversand."

AENDERUNG = dict(
    host="mail.example.org",
    port=587,
    sicherheit="starttls",
    benutzername="verwaltung@example.org",
    absender="verwaltung@example.org",
    absender_name="Gemeinde Musterstadt",
    timeout=15,
)


class FakeSMTP:
    """Minimaler SMTP-Client wie in `test_ma1_mailversand.py`."""

    def __init__(self, *, starttls_verfuegbar: bool = True, fehler: Exception | None = None):
        self.starttls_verfuegbar = starttls_verfuegbar
        self.fehler = fehler
        self.ereignisse: list[str] = []
        self.nachrichten: list = []
        self.login_daten: tuple[str, str] | None = None

    def ehlo(self):
        self.ereignisse.append("ehlo")
        return 250, b"ok"

    def has_extn(self, name: str) -> bool:
        return name == "starttls" and self.starttls_verfuegbar

    def starttls(self):
        self.ereignisse.append("starttls")

    def login(self, user: str, passwort: str):
        self.ereignisse.append("login")
        self.login_daten = (user, passwort)

    def send_message(self, nachricht):
        if self.fehler is not None:
            raise self.fehler
        self.ereignisse.append("send")
        self.nachrichten.append(nachricht)

    def quit(self):
        self.ereignisse.append("quit")


@pytest.fixture()
def konto(patched_db):
    """System Manager (Administrator) mit E-Mail-Adresse."""
    from diakronos_app.models.core import HasRole, User

    sess = patched_db()
    try:
        if sess.get(User, "Administrator") is None:
            sess.add(User(name="Administrator", email="hauptadmin@example.org",
                          full_name="Administrator", enabled=True))
        else:
            sess.get(User, "Administrator").email = "hauptadmin@example.org"
        sess.add(HasRole(name="hr-sm-Administrator", parent="Administrator",
                         parenttype="User", parentfield="roles", role="System Manager",
                         docstatus=0, idx=1))
        sess.commit()
    finally:
        sess.close()
    return patched_db


@pytest.fixture()
def smtp(monkeypatch):
    fake = FakeSMTP()
    monkeypatch.setattr(mailversand, "VERBINDUNG", fake)
    return fake


def _speichern(session_factory, **abweichungen):
    werte = {**AENDERUNG, **abweichungen}
    sess = session_factory()
    try:
        return modul.speichern(sess, benutzer="Administrator", **werte)
    finally:
        sess.close()


def _gespeichertes_passwort(session_factory) -> str | None:
    sess = session_factory()
    try:
        zeile = sess.get(SmtpEinstellungen, SMTP_EINSTELLUNGEN_NAME)
        return zeile.passwort_verschluesselt if zeile is not None else None
    finally:
        sess.close()


# ── N1: Passwort nie an einen fremden Server ───────────────────────────────

def test_testmail_mit_anderem_host_nutzt_das_passwort_nicht(client, konto, smtp):
    """N1: anderer Server + leeres Passwortfeld -> Fehler, KEIN login."""
    _speichern(konto, passwort="streng-geheim")
    r = client.post(f"/api/method/{API}mailversand_testmail",
                    json={**AENDERUNG, "host": "angreifer.example.net", "passwort": ""})
    assert r.status_code == 417, r.text
    assert "neu eingeben" in r.text
    assert "streng-geheim" not in r.text
    assert smtp.login_daten is None, "das gespeicherte Passwort darf nicht rausgehen"
    assert "login" not in smtp.ereignisse
    assert smtp.nachrichten == []


def test_testmail_mit_anderem_host_und_neuem_passwort_geht(client, konto, smtp):
    """N1: mit neu eingetipptem Passwort ist der andere Server erlaubt."""
    _speichern(konto, passwort="streng-geheim")
    r = client.post(f"/api/method/{API}mailversand_testmail",
                    json={**AENDERUNG, "host": "probe.example.org",
                          "passwort": "neues-geheim"})
    assert r.status_code == 200, r.text
    assert smtp.login_daten == ("verwaltung@example.org", "neues-geheim")


def test_testmail_mit_anderem_benutzer_nutzt_das_passwort_nicht(client, konto, smtp):
    """N1: anderer Benutzer ist derselbe Hebel wie ein anderer Server."""
    _speichern(konto, passwort="streng-geheim")
    r = client.post(f"/api/method/{API}mailversand_testmail",
                    json={**AENDERUNG, "benutzername": "fremd@example.org",
                          "passwort": ""})
    assert r.status_code == 417, r.text
    assert "neu eingeben" in r.text
    assert smtp.login_daten is None


def test_speichern_mit_anderem_host_verwirft_das_passwort(client, konto):
    """N1: nach dem Serverwechsel ist das alte Passwort nicht mehr hinterlegt."""
    r = client.post(f"/api/method/{API}mailversand_speichern",
                    json={**AENDERUNG, "passwort": "streng-geheim"})
    assert r.status_code == 200, r.text

    # Anderer Server, Passwortfeld leer: das Passwort wird VERWORFEN (der
    # Speichervorgang selbst geht durch — ohne Passwort ist das eine gueltige
    # Einstellung „Server ohne Anmeldung“).
    r2 = client.post(f"/api/method/{API}mailversand_speichern",
                     json={**AENDERUNG, "host": "mail2.example.org",
                           "benutzername": "", "passwort": ""})
    assert r2.status_code == 200, r2.text
    assert r2.json()["message"]["einstellungen"]["passwort_gesetzt"] is False
    assert _gespeichertes_passwort(konto) is None
    assert "streng-geheim" not in r2.text

    # Und ohne hinterlegtes Passwort gibt es auch keine Anmeldung mehr.
    assert mailversand.einstellungen_lesen().passwort == ""


def test_speichern_neuer_host_mit_altem_passwort_feld(client, konto):
    """N1: prallt ein geleertes Feld auf eine noetige Anmeldung -> Fehler."""
    _speichern(konto, passwort="streng-geheim")
    r = client.post(f"/api/method/{API}mailversand_speichern",
                    json={**AENDERUNG, "host": "mail2.example.org", "passwort": ""})
    assert r.status_code == 417, r.text
    assert "Passwort" in r.text
    assert _gespeichertes_passwort(konto) is not None
    assert modul.entschluessle(_gespeichertes_passwort(konto)) == "streng-geheim"


def test_speichern_ohne_passwort_bei_neuem_benutzer_fragt_nach(client, konto):
    """N1: neuer Benutzer ohne Passwort -> klare Meldung statt fremder Anmeldung."""
    _speichern(konto, passwort="streng-geheim")
    r = client.post(f"/api/method/{API}mailversand_speichern",
                    json={**AENDERUNG, "benutzername": "neu@example.org",
                          "passwort": ""})
    assert r.status_code == 417, r.text
    assert "Passwort" in r.text
    assert modul.entschluessle(_gespeichertes_passwort(konto)) == "streng-geheim"


def test_speichern_gleicher_stand_behaelt_das_passwort(client, konto):
    """N1: unveraenderter Server/Benutzer + leeres Feld = Passwort bleibt."""
    _speichern(konto, passwort="streng-geheim")
    vorher = _gespeichertes_passwort(konto)
    r = client.post(f"/api/method/{API}mailversand_speichern",
                    json={**AENDERUNG, "absender_name": "Gemeinde Neu",
                          "passwort": ""})
    assert r.status_code == 200, r.text
    assert r.json()["message"]["einstellungen"]["passwort_gesetzt"] is True
    assert _gespeichertes_passwort(konto) == vorher


# ── N2: Steuerzeichen ──────────────────────────────────────────────────────

@pytest.mark.parametrize("feld,wert", [
    ("absender_name", "Gemeinde\r\nBcc: x@y"),
    ("absender_name", "Gemeinde\nBcc: x@y"),
    ("absender_name", "Gemeinde\x00"),
    ("absender", "verwaltung@example.org\r\nBcc: x@y"),
    ("benutzername", "verwaltung@example.org\nX: y"),
    ("host", "mail.example.org\r\nX: y"),
])
def test_steuerzeichen_werden_abgelehnt(feld, wert):
    """N2: CR/LF und andere Steuerzeichen sind in keinem Kopffeld erlaubt."""
    werte = {**AENDERUNG, feld: wert}
    with pytest.raises(modul.EinstellungFehler) as fehler:
        modul.pruefen(passwort_gesetzt=True, **{k: werte[k] for k in (
            "host", "port", "sicherheit", "benutzername", "absender",
            "absender_name", "timeout")})
    assert "Steuerzeichen" in str(fehler.value)


def test_steuerzeichen_bei_der_testmail_werden_abgelehnt(client, konto, smtp):
    """N2: derselbe Schutz im Endpunkt (nicht nur beim Speichern)."""
    r = client.post(f"/api/method/{API}mailversand_testmail",
                    json={**AENDERUNG, "absender_name": "X\r\nBcc: y@z",
                          "passwort": "streng-geheim"})
    assert r.status_code == 417, r.text
    assert smtp.login_daten is None and smtp.nachrichten == []


def test_header_fehler_endet_als_mailfehler(patched_db):
    """N2: ein Wert, der durch die Pruefung rutscht, wird zum Mailfehler."""
    _speichern(patched_db, passwort="streng-geheim")
    fake = FakeSMTP()
    mail = mailversand.Mail(an="a@example.org", betreff="x", text="y")
    # Der Betreff kommt nicht aus der Oberflaeche, kann aber Zeilenumbrueche
    # enthalten (etwa aus einem importierten Text).
    mail = mailversand.Mail(an="a@example.org", betreff="x\r\nBcc: y@z", text="y")
    with pytest.raises(mailversand.MailVersandFehler) as fehler:
        mailversand.sende(mail, verbindung=fake)
    assert fake.nachrichten == []
    assert "fehlgeschlagen" in str(fehler.value)


def test_kaputter_absendername_legt_loeschung_nicht_lahm(client, konto, patched_db,
                                                         monkeypatch):
    """N2: gespeicherter Header-Fehler -> 417 mit Rollback, nie 500."""
    from datetime import datetime

    from diakronos_app.models.datenschutz import Loeschantrag
    from diakronos_app.models.diakonos import Mitglied

    # Der Wert steht so in der DB (etwa von Hand eingetragen) — die Pruefung
    # beim Speichern umgehen wir hier bewusst.
    _speichern(patched_db, passwort="streng-geheim")
    sess = patched_db()
    try:
        sess.get(SmtpEinstellungen, SMTP_EINSTELLUNGEN_NAME).absender_name = "Gemeinde\r\nBcc: x@y"
        sess.add(Mitglied(name="M1", vorname="Anna", nachname="Beispiel",
                          email="anna@example.org", status="Aktiv"))
        sess.add(Loeschantrag(mitglied="M1", status="offen",
                              beantragt_am=datetime(2026, 10, 20)))
        sess.commit()
    finally:
        sess.close()

    fake = FakeSMTP()
    monkeypatch.setattr(mailversand, "VERBINDUNG", fake)
    r = client.post("/api/method/diakronos.diakronos.api.datenschutz.loeschung_bestaetigen",
                    json={"mitglied_id": "M1", "bestaetigt": True})
    assert r.status_code == 417, r.text
    assert "NICHTS gelöscht" in r.text
    assert fake.nachrichten == []

    # Nichts geloescht, Antrag weiter offen.
    from diakronos_app.models.diakonos import Mitglied as M

    sess = patched_db()
    try:
        person = sess.get(M, "M1")
        assert person is not None and person.nachname == "Beispiel"
        antrag = sess.get(Loeschantrag, "M1")
        assert antrag is not None and antrag.status == "offen"
    finally:
        sess.close()


# ── N5: Fehlerkategorien ───────────────────────────────────────────────────

def test_absender_abgelehnt_ist_eigene_kategorie():
    """N5: 550 „Absender abgelehnt“ ist keine Verbindungsstoerung."""
    fehler = smtplib.SMTPSenderRefused(550, b"5.7.1 Sender address rejected", "a@b")
    assert mailversand._art(fehler) == "abgelehnt"


def test_datenfehler_ist_eigene_kategorie():
    """N5: ein Datenfehler des Servers (550) ist „abgelehnt“."""
    assert mailversand._art(smtplib.SMTPDataError(550, b"5.7.1 rejected")) == "abgelehnt"


def test_empfaenger_abgelehnt_ist_eigene_kategorie():
    """N5: 550 für den Empfänger ist ebenfalls „abgelehnt“."""
    assert mailversand._art(
        smtplib.SMTPRecipientsRefused({"a@b": (550, b"no such user")})) == "abgelehnt"


def test_nicht_erreichbar_nur_bei_verbindungsfehlern():
    """N5: „server“ bleibt Verbindungsfehlern vorbehalten."""
    assert mailversand._art(ConnectionRefusedError(111, "refused")) == "server"
    assert mailversand._art(smtplib.SMTPConnectError(421, b"nope")) == "server"


def test_testmail_meldet_absender_abgelehnt(client, konto, smtp, monkeypatch):
    """N5: 550 -> eigener Satz, NICHT „nicht erreichbar“."""
    monkeypatch.setattr(
        mailversand, "VERBINDUNG",
        FakeSMTP(fehler=smtplib.SMTPSenderRefused(550, b"5.7.1 rejected", "x@y")))
    r = client.post(f"/api/method/{API}mailversand_testmail",
                    json={**AENDERUNG, "passwort": "streng-geheim"})
    assert r.status_code == 417, r.text
    assert "abgelehnt" in r.text
    assert "nicht erreichbar" not in r.text


def test_testmail_meldet_datenfehler_abgelehnt(client, konto, monkeypatch):
    """N5: SMTPDataError (550) heisst „abgelehnt“, nicht „nicht erreichbar“."""
    monkeypatch.setattr(
        mailversand, "VERBINDUNG",
        FakeSMTP(fehler=smtplib.SMTPDataError(550, b"5.7.1 rejected")))
    r = client.post(f"/api/method/{API}mailversand_testmail",
                    json={**AENDERUNG, "passwort": "streng-geheim"})
    assert r.status_code == 417, r.text
    assert "abgelehnt" in r.text
    assert "nicht erreichbar" not in r.text


def test_loeschbestaetigung_meldet_abgelehnt_verstaendlich(client, konto, patched_db,
                                                           monkeypatch):
    """N5: auch der Löschablauf bekommt den richtigen Satz und rollt zurück."""
    from datetime import datetime

    from diakronos_app.models.datenschutz import Loeschantrag
    from diakronos_app.models.diakonos import Mitglied

    _speichern(patched_db, passwort="streng-geheim")
    sess = patched_db()
    try:
        sess.add(Mitglied(name="M2", vorname="Bea", nachname="Beispiel",
                          email="bea@example.org", status="Aktiv"))
        sess.add(Loeschantrag(mitglied="M2", status="offen",
                              beantragt_am=datetime(2026, 10, 21)))
        sess.commit()
    finally:
        sess.close()
    fake = FakeSMTP(fehler=smtplib.SMTPSenderRefused(550, b"5.7.1 rejected", "x@y"))
    monkeypatch.setattr(mailversand, "VERBINDUNG", fake)
    r = client.post("/api/method/diakronos.diakronos.api.datenschutz.loeschung_bestaetigen",
                    json={"mitglied_id": "M2", "bestaetigt": True})
    assert r.status_code == 417, r.text
    assert "NICHTS gelöscht" in r.text
    sess = patched_db()
    try:
        assert sess.get(Mitglied, "M2").nachname == "Beispiel"
        assert sess.get(Loeschantrag, "M2").status == "offen"
    finally:
        sess.close()


# ── Kleinkram zu N5: `hinweis` nur fuer System Manager ─────────────────────

def test_status_hinweis_nur_fuer_system_manager(client, konto, monkeypatch):
    """R-MAIL-1 (Kleinkram): der Grund einer kaputten Zeile geht nur den
    System Manager an — ein Mitgliederadministrator bekommt nur „nein“."""
    from diakronos_app.mailversand import EinstellungenLaden
    from diakronos_app.models.core import HasRole, User

    sess = konto()
    try:
        if sess.get(User, "verwalter@example.org") is None:
            sess.add(User(name="verwalter@example.org", email="verwalter@example.org",
                          full_name="Verwalter", enabled=True))
        sess.add(HasRole(name="hr-ma-verwalter", parent="verwalter@example.org",
                         parenttype="User", parentfield="roles",
                         role="Mitgliederadministrator", docstatus=0, idx=1))
        sess.commit()
    finally:
        sess.close()

    def _kaputt():
        raise EinstellungenLaden("Passwort laesst sich nicht entschluesseln")

    monkeypatch.setattr("diakronos_app.mailversand.einstellungen_lesen", _kaputt)

    from diakronos_app import frappe_compat

    r = client.post(f"/api/method/{API}mailversand_status", json={})
    assert r.status_code == 200, r.text
    assert r.json()["message"]["hinweis"], "der System Manager sieht den Grund"

    frappe_compat.set_user("verwalter@example.org")
    r2 = client.post(f"/api/method/{API}mailversand_status", json={})
    assert r2.status_code == 200, r2.text
    assert r2.json()["message"]["eingerichtet"] is False
    assert r2.json()["message"]["hinweis"] == "", (
        "der Mitgliederadministrator bekommt keinen Grund")


# ── N4: „Gespeichertes Passwort entfernen“ muss moeglich sein ──────────────

OHNE_ANMELDUNG = dict(AENDERUNG, benutzername="")


def test_passwort_entfernen_ohne_anmeldung_geht_durch(client, konto, patched_db):
    """N4: das ausdrueckliche Entfernen ist ausfuehrbar (Server ohne Anmeldung).

    VOR dem Fix kam hier „Für die Anmeldung fehlt das Passwort“ — die
    Oberflaeche konnte den Loeschwunsch deshalb gar nicht ausfuehren.
    """
    _speichern(patched_db, passwort="streng-geheim")
    r = client.post(f"/api/method/{API}mailversand_speichern",
                    json={**OHNE_ANMELDUNG, "passwort": "", "passwort_entfernen": True})
    assert r.status_code == 200, r.text
    assert r.json()["message"]["einstellungen"]["passwort_gesetzt"] is False
    assert _gespeichertes_passwort(patched_db) is None


def test_passwort_entfernen_mit_benutzername_erklaert_den_widerspruch(client, konto,
                                                                     patched_db):
    """N4: mit Benutzername bleibt es verboten — aber mit klarer Ansage."""
    _speichern(patched_db, passwort="streng-geheim")
    r = client.post(f"/api/method/{API}mailversand_speichern",
                    json={**AENDERUNG, "passwort": "", "passwort_entfernen": True})
    assert r.status_code == 417, r.text
    assert "Benutzernamen leeren" in r.text
    assert _gespeichertes_passwort(patched_db) is not None, "nichts still geloescht"
