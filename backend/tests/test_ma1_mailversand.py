"""MAIL-1: SMTP-Einstellungen über die Oberfläche (S1–S4).

Zusagen dieser Karte und wo sie hier geprüft werden:

S1  Einstellungen in der DB, Passwort verschlüsselt, nie zurück an die
    Oberfläche, leeres Passwortfeld = unverändert.
    -> ``test_passwort_steht_verschluesselt_in_der_db``,
       ``test_passwort_kommt_nie_zurueck``,
       ``test_leeres_passwortfeld_aendert_nichts``
S2  Nur System Manager lesen/ändern; Mitgliederadministrator sieht höchstens
    „eingerichtet: ja/nein“; Änderungen im AuditLog ohne Passwort.
    -> ``test_mitgliederadministrator_darf_nicht_lesen``,
       ``test_mitgliederadministrator_sieht_nur_ja_nein``,
       ``test_aenderung_landet_im_auditlog_ohne_passwort``
S3  „Testmail senden“ an die Adresse des Angemeldeten mit verständlicher
    Fehlermeldung, ohne Rohdaten/Passwort.
    -> ``test_testmail_geht_an_den_angemeldeten_admin``,
       ``test_testmail_meldet_anmeldung_abgelehnt``,
       ``test_testmail_meldet_zeitueberschreitung``,
       ``test_testmail_passwort_nie_in_der_meldung``
S4  ``mailversand.py`` liest NUR die DB; ``SMTP_*`` aus der Umgebung gibt es
    nicht mehr; DSGVO-Bestätigung nutzt die DB-Einstellungen.
    -> ``test_keine_smtp_umgebungsvariablen_mehr``,
       ``test_versand_liest_die_db_nicht_die_umgebung``,
       ``test_loeschbestaetigung_nutzt_die_db_einstellungen``

Kein Test dieses Moduls baut eine Netzverbindung auf: der Transporter ist die
Testnaht ``mailversand.VERBINDUNG``.
"""
from __future__ import annotations

import logging
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
    """Minimaler SMTP-Client wie in `test_dsgvo1_mail.py`."""

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
    """Zwei Konten: System Manager (Administrator) und Mitgliederadministrator."""
    from diakronos_app.models.core import HasRole, User

    sess = patched_db()
    try:
        # Der Hauptadmin ist im Betrieb beides: System Manager UND
        # Mitgliederadministrator (`_require_admin` der Datenschutz-Seite
        # verlangt Letzteres, `mailversand_*` Ersteres).
        for name, rollen in (("Administrator", ("System Manager", "Mitgliederadministrator")),
                             ("verwalter@example.org", ("Mitgliederadministrator",))):
            if sess.get(User, name) is None:
                sess.add(User(name=name, email=name, full_name=name, enabled=True))
            for i, rolle in enumerate(rollen, start=1):
                sess.add(HasRole(name=f"hr-{rolle}-{name}", parent=name, parenttype="User",
                                 parentfield="roles", role=rolle, docstatus=0, idx=i))
        sess.commit()
    finally:
        sess.close()
    return patched_db


@pytest.fixture()
def konto_email(client, patched_db):
    """Das Konto des angemeldeten Administrators bekommt eine Adresse (S3)."""
    from diakronos_app.models.core import User

    sess = patched_db()
    try:
        sess.get(User, "Administrator").email = "hauptadmin@example.org"
        sess.commit()
    finally:
        sess.close()
    return "hauptadmin@example.org"


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


def _smtp_einrichten(patched_db):
    """MAIL-1: eine gültige SMTP-Zeile in der Test-Datenbank anlegen.

    Ersetzt das frühere `monkeypatch.setattr(get_settings(), "smtp_*", ...)`:
    seit MAIL-1 liest `mailversand.py` NUR die DB-Zeile (S4), eine gepatchte
    Einstellung wäre also wirkungslos. Die Werte sind dieselben wie zuvor
    (Host, Port 587, keine Anmeldung, Absender „verwaltung@example.org“).
    """
    from diakronos_app.models.smtp import SMTP_EINSTELLUNGEN_NAME, SmtpEinstellungen

    with patched_db() as s:
        zeile = s.get(SmtpEinstellungen, SMTP_EINSTELLUNGEN_NAME)
        if zeile is None:
            zeile = SmtpEinstellungen(name=SMTP_EINSTELLUNGEN_NAME, created_by="test")
            s.add(zeile)
        zeile.host = "mail.example.org"
        zeile.port = 587
        zeile.sicherheit = "starttls"
        zeile.benutzername = None
        zeile.passwort_verschluesselt = None
        zeile.absender = "verwaltung@example.org"
        zeile.absender_name = "Gemeinde Musterstadt"
        zeile.timeout = 5
        zeile.eingerichtet = True
        s.commit()
    return zeile


# ── S1: Ablage und Verschlüsselung ─────────────────────────────────────────

def test_einstellungen_stehen_in_der_db(patched_db):
    """S1: gespeichert wird in `smtp_einstellungen`, nicht in der Umgebung."""
    _speichern(patched_db, passwort="streng-geheim")
    sess = patched_db()
    try:
        gelesen = sess.get(SmtpEinstellungen, SMTP_EINSTELLUNGEN_NAME)
        assert gelesen is not None
        assert gelesen.host == "mail.example.org"
        assert gelesen.port == 587
        assert gelesen.sicherheit == "starttls"
        assert gelesen.absender_name == "Gemeinde Musterstadt"
        assert gelesen.absender == "verwaltung@example.org"
    finally:
        sess.close()


def test_passwort_steht_verschluesselt_in_der_db(patched_db):
    """S1: das Passwort ist Fernet-Geheimtext mit eigenem Kontext."""
    _speichern(patched_db, passwort="streng-geheim")
    sess = patched_db()
    try:
        gelesen = sess.get(SmtpEinstellungen, SMTP_EINSTELLUNGEN_NAME)
        wert = gelesen.passwort_verschluesselt
        assert wert and "streng-geheim" not in wert
        assert wert.startswith(modul.PASSWORT_PRAEFIX)
        # Und der Geheimtext ist nur mit dem SMTP-Kontext lesbar.
        assert modul.entschluessle(wert) == "streng-geheim"
    finally:
        sess.close()


def test_passwort_kommt_nie_zurueck(client, konto):
    """S1: die Antwort enthält nur „gespeichert: ja/nein“."""
    r = client.post(f"/api/method/{API}mailversand_speichern",
                    json={**AENDERUNG, "passwort": "streng-geheim"})
    assert r.status_code == 200, r.text
    assert "streng-geheim" not in r.text
    assert r.json()["message"]["einstellungen"]["passwort_gesetzt"] is True

    r2 = client.post(f"/api/method/{API}mailversand_get", json={})
    assert r2.status_code == 200, r2.text
    assert "streng-geheim" not in r2.text
    assert r2.json()["message"]["einstellungen"]["passwort_gesetzt"] is True


def test_leeres_passwortfeld_aendert_nichts(client, konto, patched_db):
    """S1: leeres Feld = unverändert lassen (die UI schickt nie ein Passwort).

    MAIL-1b (N1): gilt für Änderungen OHNE Wechsel von Server/Benutzer. Bei
    geändertem Ziel wird das Passwort verworfen — dafür gibt es die eigenen
    Fälle in ``test_ma1b_mailversand_review.py``.
    """
    client.post(f"/api/method/{API}mailversand_speichern",
                json={**AENDERUNG, "passwort": "streng-geheim"})
    sess = patched_db()
    try:
        vorher = sess.get(SmtpEinstellungen, SMTP_EINSTELLUNGEN_NAME).passwort_verschluesselt
    finally:
        sess.close()

    r = client.post(f"/api/method/{API}mailversand_speichern",
                    json={**AENDERUNG, "absender_name": "Gemeinde Neu",
                          "passwort": ""})
    assert r.status_code == 200, r.text
    sess = patched_db()
    try:
        zeile = sess.get(SmtpEinstellungen, SMTP_EINSTELLUNGEN_NAME)
        assert zeile.absender_name == "Gemeinde Neu"
        assert zeile.passwort_verschluesselt == vorher
        assert modul.entschluessle(zeile.passwort_verschluesselt) == "streng-geheim"
    finally:
        sess.close()


def test_ohne_verschluesselung_nur_ohne_anmeldung(patched_db):
    """S1: „keine“ ist erlaubt — aber nicht mit Zugangsdaten (Klartext!)."""
    with pytest.raises(modul.EinstellungFehler) as fehler:
        _speichern(patched_db, sicherheit="keine", benutzername="verwaltung@example.org",
                   passwort="streng-geheim")
    assert "ohne Anmeldung" in str(fehler.value)


def test_anmeldung_ohne_passwort_wird_abgelehnt(patched_db):
    """S1: ein Benutzername ohne Passwort ist ein stiller Fehlschlag — vorher sagen."""
    with pytest.raises(modul.EinstellungFehler) as fehler:
        _speichern(patched_db, benutzername="verwaltung@example.org")
    assert "Passwort" in str(fehler.value)


def test_ohne_eintrag_gilt_nicht_eingerichtet(patched_db):
    """S1: keine Zeile = nicht eingerichtet (die Migration legt keine an)."""
    sess = patched_db()
    try:
        assert modul.holen(sess) is None
        assert modul.als_dict(None)["eingerichtet"] is False
    finally:
        sess.close()
    assert mailversand.ist_konfiguriert() is False


# ── S2: Rechte und Audit ───────────────────────────────────────────────────

def _als(name: str):
    """Identität für den Aufruf umstellen (Naht `session.set_user`)."""
    from diakronos_app import frappe_compat

    frappe_compat.set_user(name)


def test_mitgliederadministrator_darf_nicht_lesen(client, konto):
    """S2: lesen und ändern nur System Manager."""
    _als("verwalter@example.org")
    r = client.post(f"/api/method/{API}mailversand_get", json={})
    assert r.status_code == 403, r.text
    r = client.post(f"/api/method/{API}mailversand_speichern",
                    json={**AENDERUNG, "passwort": "x"})
    assert r.status_code == 403, r.text


def test_mitgliederadministrator_sieht_nur_ja_nein(client, konto):
    """S2: „eingerichtet: ja/nein“ — ohne Host, Absender, Benutzername."""
    client.post(f"/api/method/{API}mailversand_speichern",
                json={**AENDERUNG, "passwort": "streng-geheim"})
    _als("verwalter@example.org")
    r = client.post(f"/api/method/{API}mailversand_status", json={})
    assert r.status_code == 200, r.text
    daten = r.json()["message"]
    assert daten["eingerichtet"] is True
    assert daten["darf_aendern"] is False
    for feld in ("host", "absender", "benutzername", "passwort_gesetzt", "port"):
        assert feld not in daten
    assert "mail.example.org" not in r.text


def test_aenderung_landet_im_auditlog_ohne_passwort(client, konto, patched_db):
    """S2: Änderungen sind nachvollziehbar — aber ohne Zugangsdaten."""
    from diakronos_app.models.diakonos import AuditLog

    r = client.post(f"/api/method/{API}mailversand_speichern",
                    json={**AENDERUNG, "passwort": "streng-geheim"})
    assert r.status_code == 200, r.text
    sess = patched_db()
    try:
        zeilen = sess.query(AuditLog).all()
        assert len(zeilen) == 1
        text = " ".join(str(getattr(z, f) or "") for z in zeilen
                        for f in ("actor", "action_typ", "target_doctype",
                                  "target_name", "consequence", "begruendung")
                        if hasattr(z, f))
        assert "streng-geheim" not in text
        assert "verwaltung@example.org" not in text
        # Die Protokollzeile nennt die GEÄNDERTEN FELDER, nicht deren Werte
        # (der Host ist kein Geheimnis, gehört aber nicht in ein Protokoll,
        # das viele lesen dürfen).
        assert "host" in text and "absender" in text
        assert "Mailversand" in text
    finally:
        sess.close()


def test_passwort_steht_nie_im_protokoll(client, konto, caplog):
    """S1/S2: auch das Anwendungsprotokoll nennt kein Passwort."""
    with caplog.at_level(logging.DEBUG):
        client.post(f"/api/method/{API}mailversand_speichern",
                    json={**AENDERUNG, "passwort": "streng-geheim"})
    assert "streng-geheim" not in caplog.text


# ── S3: Testmail ───────────────────────────────────────────────────────────

def test_testmail_geht_an_den_angemeldeten_admin(client, konto, konto_email, smtp):
    """S3: Empfänger ist die Adresse des angemeldeten System Managers."""
    client.post(f"/api/method/{API}mailversand_speichern",
                json={**AENDERUNG, "passwort": "streng-geheim"})
    r = client.post(f"/api/method/{API}mailversand_testmail", json={})
    assert r.status_code == 200, r.text
    assert r.json()["message"]["gesendet"] is True
    assert r.json()["message"]["an"] == konto_email
    assert len(smtp.nachrichten) == 1
    assert smtp.nachrichten[0]["To"] == konto_email
    assert smtp.login_daten == ("verwaltung@example.org", "streng-geheim")


def test_testmail_nimmt_ungespeicherte_eingaben(client, konto, konto_email, smtp):
    """S3: proben VOR dem Speichern — die eingegebenen Werte gelten."""
    r = client.post(f"/api/method/{API}mailversand_testmail",
                    json={**AENDERUNG, "host": "probe.example.org",
                          "benutzername": "", "passwort": ""})
    assert r.status_code == 200, r.text
    assert smtp.nachrichten[0]["To"] == konto_email


def test_testmail_meldet_anmeldung_abgelehnt(client, konto, konto_email, monkeypatch):
    """S3: Anmeldung abgelehnt -> verständlicher Satz, keine Rohdaten."""
    def _login(self, user, passwort):
        raise smtplib.SMTPAuthenticationError(535, b"5.7.8 Authentication failed")

    monkeypatch.setattr(FakeSMTP, "login", _login)
    monkeypatch.setattr(mailversand, "VERBINDUNG", FakeSMTP())
    r = client.post(f"/api/method/{API}mailversand_testmail",
                    json={**AENDERUNG, "passwort": "streng-geheim"})
    assert r.status_code == 417, r.text
    assert "Anmeldung abgelehnt" in r.text
    assert "535" not in r.text
    assert "streng-geheim" not in r.text


def test_testmail_meldet_server_nicht_erreichbar(client, konto, konto_email, monkeypatch):
    """S3: Server nicht erreichbar -> „nicht erreichbar“, ohne Rohdaten."""
    monkeypatch.setattr(mailversand, "VERBINDUNG",
                        FakeSMTP(fehler=ConnectionRefusedError(111, "Connection refused")))
    r = client.post(f"/api/method/{API}mailversand_testmail",
                    json={**AENDERUNG, "passwort": "streng-geheim"})
    assert r.status_code == 417, r.text
    assert "nicht erreichbar" in r.text


def test_testmail_meldet_zertifikat(client, konto, konto_email, monkeypatch):
    """S3: Zertifikat ungültig -> eigener Satz (kein ungeprüfter Versand)."""
    import ssl

    fehler = ssl.SSLCertVerificationError(1, "certificate verify failed")
    monkeypatch.setattr(mailversand, "VERBINDUNG", FakeSMTP(fehler=fehler))
    r = client.post(f"/api/method/{API}mailversand_testmail",
                    json={**AENDERUNG, "passwort": "streng-geheim"})
    assert r.status_code == 417, r.text
    assert "Zertifikat" in r.text


def test_testmail_meldet_zeitueberschreitung(client, konto, konto_email, monkeypatch):
    """S3: Zeitüberschreitung -> eigener Satz."""
    monkeypatch.setattr(mailversand, "VERBINDUNG", FakeSMTP(fehler=TimeoutError("timed out")))
    r = client.post(f"/api/method/{API}mailversand_testmail",
                    json={**AENDERUNG, "passwort": "streng-geheim"})
    assert r.status_code == 417, r.text
    assert "Zeitüberschreitung" in r.text


def test_testmail_passwort_nie_in_der_meldung(client, konto, konto_email, monkeypatch):
    """S3: selbst wenn der Server das Passwort zurückgibt — es wird entschärft."""
    monkeypatch.setattr(
        mailversand, "VERBINDUNG",
        FakeSMTP(fehler=smtplib.SMTPDataError(554, b"rejected streng-geheim / verwalter")))
    r = client.post(f"/api/method/{API}mailversand_testmail",
                    json={**AENDERUNG, "passwort": "streng-geheim"})
    assert r.status_code == 417, r.text
    assert "streng-geheim" not in r.text


def test_testmail_braucht_system_manager(client, konto):
    """S3: der Knopf steht nur dem System Manager zur Verfügung."""
    _als("verwalter@example.org")
    r = client.post(f"/api/method/{API}mailversand_testmail", json={**AENDERUNG})
    assert r.status_code == 403, r.text


# ── S4: nur die DB, kein zweiter Weg ───────────────────────────────────────

def test_keine_smtp_umgebungsvariablen_mehr():
    """S4: die SMTP_*-Felder sind aus `settings.py` entfernt (kein zweiter Weg)."""
    from diakronos_app.settings import Settings, get_settings

    felder = set(Settings.model_fields)
    assert not {f for f in felder if f.startswith("smtp_")}, sorted(
        f for f in felder if f.startswith("smtp_"))
    assert not {f for f in dir(get_settings()) if f.startswith("smtp_")}


def test_versand_liest_die_db_nicht_die_umgebung(patched_db, smtp, monkeypatch):
    """S4: nur die DB-Zeile entscheidet — eine ENV gibt es nicht mehr."""
    # Nichts eingerichtet: es wird nichts versucht.
    with pytest.raises(mailversand.MailNichtEingerichtet):
        mailversand.sende(mailversand.Mail(an="a@example.org", betreff="x", text="y"))
    assert smtp.nachrichten == []

    _speichern(patched_db, passwort="streng-geheim")
    assert mailversand.ist_konfiguriert() is True
    mailversand.sende(mailversand.Mail(an="a@example.org", betreff="x", text="y"))
    assert len(smtp.nachrichten) == 1
    assert smtp.login_daten == ("verwaltung@example.org", "streng-geheim")


def test_versand_nutzt_ssl_und_keine_verschluesselung(patched_db):
    """S1/S4: „SSL/TLS“ und „keine“ werden beim Verbindungsaufbau beachtet."""
    gesehen = {}

    class _Client:
        def __init__(self):
            self.nachrichten = []

        def ehlo(self):
            gesehen.setdefault("ehlo", 0)
            gesehen["ehlo"] += 1

        def has_extn(self, name):
            return name == "starttls" and False

        def login(self, u, p):
            gesehen["login"] = (u, p)

        def send_message(self, n):
            self.nachrichten.append(n)

        def quit(self):
            pass

    def _oeffnen(host, port, timeout, ssl_, starttls):
        gesehen.update(host=host, port=port, timeout=timeout, ssl=ssl_, starttls=starttls)
        return _Client()

    import diakronos_app.mailversand as mv

    original = mv._verbindung_oeffnen
    mv._verbindung_oeffnen = _oeffnen
    try:
        _speichern(patched_db, sicherheit="ssl", port=465, benutzername="",
                   passwort="")
        mv.sende(mailversand.Mail(an="a@example.org", betreff="x", text="y"))
        assert gesehen["ssl"] is True and gesehen["starttls"] is False
        assert gesehen["port"] == 465 and gesehen["host"] == "mail.example.org"
        assert gesehen["timeout"] == 15.0
        assert "login" not in gesehen  # ohne Benutzername keine Anmeldung
    finally:
        mv._verbindung_oeffnen = original


def test_unlesbares_passwort_wird_gemeldet(patched_db, monkeypatch):
    """S1: geänderter SECRET_KEY -> klare Meldung statt stiller Ablehnung."""
    _speichern(patched_db, passwort="streng-geheim")
    sess = patched_db()
    try:
        sess.get(SmtpEinstellungen, SMTP_EINSTELLUNGEN_NAME).passwort_verschluesselt = \
            "fernet:v1:kaputt"
        sess.commit()
    finally:
        sess.close()
    with pytest.raises(mailversand.EinstellungenLaden) as fehler:
        mailversand.einstellungen_lesen()
    assert "nicht entschlüsseln" in str(fehler.value)
    # „nicht eingerichtet“ ist die sichere Antwort für den Löschablauf.
    assert mailversand.ist_konfiguriert() is False


def test_loeschbestaetigung_nutzt_die_db_einstellungen(client, konto, patched_db,
                                                     monkeypatch):
    """S4: die DSGVO-Bestätigung liest die Einstellungen aus der DB-Zeile."""
    from datetime import datetime

    from diakronos_app.api import datenschutz as ds
    from diakronos_app.models.datenschutz import Loeschantrag
    from diakronos_app.models.diakonos import Mitglied

    sess = patched_db()
    try:
        sess.add(Mitglied(name="M1", vorname="Anna", nachname="Beispiel",
                          email="anna@example.org", status="Aktiv"))
        sess.add(Loeschantrag(mitglied="M1", status="offen",
                              beantragt_am=datetime(2026, 10, 20)))
        sess.commit()
    finally:
        sess.close()

    # Ohne Einstellungen lehnt die Bestätigung ab, OHNE zu löschen (D4).
    r = client.post("/api/method/diakronos.diakronos.api.datenschutz.loeschung_bestaetigen",
                    json={"mitglied_id": "M1", "bestaetigt": True})
    assert r.status_code == 417, r.text
    assert "nicht eingerichtet" in r.text

    _speichern(patched_db, passwort="streng-geheim")
    fake = FakeSMTP()
    monkeypatch.setattr(mailversand, "VERBINDUNG", fake)
    # Die Anonymisierung selbst ist nicht Gegenstand dieser Karte (DSGVO-1);
    # hier zaehlt NUR, dass die Mail aus der DB-Zeile verschickt wird.
    from diakronos_app import dsgvo_anonymisierung as dsgvo

    echte_anonymisierung = dsgvo.anonymisiere
    aufrufe = []

    def _merken(*a, **k):
        # Beim ERSTEN Aufruf (ohne Einstellungen) kommt es gar nicht so weit;
        # beim zweiten liefert die echte Funktion das Ergebnis, und die Mail
        # geht danach aus der DB-Zeile raus.
        aufrufe.append(1)
        return echte_anonymisierung(*a, **k)

    monkeypatch.setattr(dsgvo, "anonymisiere", _merken)
    monkeypatch.setattr(dsgvo, "dateien_entfernen", lambda dateien: 0)
    r = client.post("/api/method/diakronos.diakronos.api.datenschutz.loeschung_bestaetigen",
                    json={"mitglied_id": "M1", "bestaetigt": True})
    assert fake.nachrichten, r.text
    assert fake.nachrichten[0]["To"] == "anna@example.org"
    assert fake.login_daten == ("verwaltung@example.org", "streng-geheim")


# ── N3 (R-DSGVO-2a): neutrale Meldung, wenn der Versand fehlt ──────────────


def test_meldung_ohne_einrichtung_nennt_keinen_einzelfall(patched_db, smtp):
    """N3: `MailNichtEingerichtet` gilt für JEDEN Versandweg.

    Der Text sprach nur von der „Löschung … bestätigt“ — beim Ablehnen und in
    jedem anderen Zusammenhang war das falsch. Er nennt jetzt den Zustand und
    die Folge für den Löschantrag, ohne eine bestimmte Aktion zu behaupten.
    """
    text = None
    with pytest.raises(mailversand.MailNichtEingerichtet) as fehler:
        mailversand.sende(mailversand.Mail(an="a@example.org", betreff="x", text="y"))
    text = str(fehler.value)
    assert text.startswith("Mailversand ist nicht eingerichtet")
    # Die Folge wird benannt — für Bestätigen UND Ablehnen gültig.
    assert "Löschantrag" in text
    # Keine Behauptung über EINE Aktion (die alte Formulierung).
    assert "nicht bestätigt werden" not in text
    assert "abgelehnt werden" not in text
    assert smtp.nachrichten == []


def test_halb_eingerichtete_zeile_meldet_denselben_neutralen_text(patched_db):
    """N3: auch der zweite Weg (Zeile ohne Host/Absender) ist neutral."""
    from diakronos_app.models.smtp import SMTP_EINSTELLUNGEN_NAME, SmtpEinstellungen

    _smtp_einrichten(patched_db)
    with patched_db.begin() as s:
        zeile = s.get(SmtpEinstellungen, SMTP_EINSTELLUNGEN_NAME)
        # Leer, nicht NULL: die Spalten sind NOT NULL.
        zeile.host = ""
        zeile.absender = ""
    with pytest.raises(mailversand.MailNichtEingerichtet) as fehler:
        mailversand.sende(mailversand.Mail(an="a@example.org", betreff="x", text="y"))
    text = str(fehler.value)
    assert text == mailversand.NICHT_EINGERICHTET
    assert "nicht bestätigt werden" not in text and "abgelehnt werden" not in text
