"""DSGVO-1 (D3): Mailversand — ohne Netz, mit Fake-SMTP.

Der Test benutzt `mailversand.VERBINDUNG` (die Testnaht des Moduls) und einen
Fake-Client, der die winzige `smtplib.SMTP`-Schnittstelle nachbildet. Kein
Test dieses Moduls baut eine Netzverbindung auf.
"""
from __future__ import annotations

import pytest

from diakronos_app import mailversand
from diakronos_app.mailversand import (
    Mail, MailNichtEingerichtet, MailVersandFehler, ist_konfiguriert, sende,
)


class FakeSMTP:
    """Minimaler SMTP-Client. Zeichnet auf, was das Modul mit ihm macht."""

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


@pytest.fixture
def smtp(monkeypatch, patched_db):
    """Konfiguriert SMTP (in der DB-Zeile, MAIL-1) und haengt einen Fake-Client an."""
    from diakronos_app import smtp_einstellungen as smtp_mod

    sess = patched_db()
    try:
        smtp_mod.speichern(
            sess, benutzer="test", host="mail.example.org", port=587,
            sicherheit="starttls", benutzername="absender@example.org",
            passwort="streng-geheim", absender="absender@example.org",
            absender_name="Gemeinde Musterstadt", timeout=5,
        )
    finally:
        sess.close()
    fake = FakeSMTP()
    monkeypatch.setattr(mailversand, "VERBINDUNG", fake)
    return fake


def test_nicht_eingerichtet_wird_gemeldet_und_sendet_nichts(patched_db, monkeypatch):
    # MAIL-1: „nicht eingerichtet“ = keine Zeile in `smtp_einstellungen`.
    fake = FakeSMTP()
    monkeypatch.setattr(mailversand, "VERBINDUNG", fake)
    assert ist_konfiguriert() is False
    with pytest.raises(MailNichtEingerichtet) as fehler:
        sende(Mail(an="person@example.org", betreff="x", text="y"))
    assert "nicht eingerichtet" in str(fehler.value)
    assert fake.ereignisse == []  # nichts versucht


def test_konfiguriert_ist_wahr_mit_host_und_absender(smtp):
    assert ist_konfiguriert() is True


def test_starttls_dann_login_dann_senden(smtp):
    sende(Mail(an="person@example.org", betreff="Testbetreff", text="Zeile eins"))
    assert smtp.ereignisse == ["ehlo", "starttls", "login", "send"]
    assert smtp.login_daten == ("absender@example.org", "streng-geheim")
    nachricht = smtp.nachrichten[0]
    assert nachricht["To"] == "person@example.org"
    assert nachricht["Subject"] == "Testbetreff"
    assert "Zeile eins" in nachricht.get_content()
    assert "Gemeinde Musterstadt" in nachricht["From"]


def test_server_ohne_starttls_wird_abgelehnt(monkeypatch, smtp):
    smtp.starttls_verfuegbar = False
    with pytest.raises(MailVersandFehler) as fehler:
        sende(Mail(an="person@example.org", betreff="x", text="y"))
    assert "STARTTLS" in str(fehler.value)
    assert "login" not in smtp.ereignisse and "send" not in smtp.ereignisse


def test_passwort_steht_nie_in_der_fehlermeldung(smtp):
    smtp.fehler = RuntimeError("535 auth failed for streng-geheim / absender@example.org")
    with pytest.raises(MailVersandFehler) as fehler:
        sende(Mail(an="person@example.org", betreff="x", text="y"))
    text = str(fehler.value)
    assert "streng-geheim" not in text
    assert "absender@example.org" not in text
    assert "***" in text


def test_ungueltige_adresse_wird_abgelehnt_ohne_versand(smtp):
    with pytest.raises(MailVersandFehler):
        sende(Mail(an="", betreff="x", text="y"))
    assert smtp.ereignisse == []


def test_loeschbestaetigung_nennt_gemeinde_und_ist_endgueltig(smtp, patched_db):
    """Der Text aus D4 — kurz, deutsch, ohne Rückfrage-Link."""
    from diakronos_app.models.diakronos import DiakronosEinstellungen

    with patched_db.begin() as s:
        s.add(DiakronosEinstellungen(name="Einstellungen", organisationsname="Gemeinde Musterstadt"))

    mailversand.sende_loeschbestaetigung("person@example.org")
    assert len(smtp.nachrichten) == 1
    nachricht = smtp.nachrichten[0]
    text = nachricht.get_content()
    assert nachricht["To"] == "person@example.org"
    assert "Gemeinde Musterstadt" in text
    assert "werden jetzt gelöscht" in text
    assert "nicht rückgängig" in text
    # Kein Bestätigungslink, keine Rückfrage: die Löschung läuft ohne Zutun.
    assert "http" not in text
