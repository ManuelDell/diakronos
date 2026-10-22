"""E-Mail-Versand (SMTP) — DSGVO-1 (D3), seit MAIL-1 mit DB-Einstellungen.

Benachrichtigungen lagen früher nur als `Notification Log` in der Datenbank.
Die Löschung auf Antrag braucht aber zwingend eine Mail an die betroffene
Person („deine Daten werden jetzt gelöscht“), und zwar NACHWEISLICH vor der
Anonymisierung.

DIE REGELN DIESES MODULS
------------------------
1. **Nicht eingerichtet heisst nicht senden.** Gibt es keine
   `smtp_einstellungen`-Zeile, ist der Versand nicht eingerichtet;
   `ist_konfiguriert()` sagt das, und `sende()` wirft `MailNichtEingerichtet`.
   Der Aufrufer entscheidet dann fachlich (im Löschablauf: „Bestätigen“ wird
   abgelehnt) — dieses Modul fällt niemals still auf „ok“ zurück.
2. **Die Einstellungen kommen NUR aus der Datenbank** (MAIL-1, S4): die
   Oberfläche `#/einstellungen/mailversand` schreibt sie, `smtp_einstellungen`
   liest und prüft sie. `SMTP_*` aus der Umgebung gibt es nicht mehr — ein
   zweiter halber Weg wäre eine zweite Wahrheit.
3. **Kein Passwort in Logs oder Meldungen.** Fehlertexte nennen den SMTP-Code
   und die Klartextmeldung des Servers, nie die Zugangsdaten. Exception-Texte
   von `smtplib` können den Server nennen, aber keine Credentials — sie werden
   dennoch zentral durch `_entschaerfe()` gefiltert.
4. **Kein Netz in Tests.** Der Transporter ist injizierbar
   (`sende(..., verbindung=<fake>)`); die Tests benutzen einen Fake-SMTP.
5. **Keine Zeitüberschreitung ohne Grenze.** Jede Verbindung hat das in der
   Oberfläche eingestellte Zeitlimit (Standard 15 s) — ein hängender Mailserver
   darf keinen Request minutenlang blockieren.
6. **Zertifikatsprüfung bleibt an** (`ssl.create_default_context()`).

Einstellungen (Tabelle `smtp_einstellungen`, gepflegt in der Oberfläche):

    host / port / sicherheit  (starttls | ssl | keine)
    benutzername / passwort   (Passwort Fernet-verschlüsselt, nie im Klartext)
    absender / absender_name
    timeout                   Zeitbudget je Verbindung in Sekunden
"""

from __future__ import annotations

import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formataddr, make_msgid

__all__ = [
    "MailNichtEingerichtet", "MailVersandFehler", "Mail", "Einstellungen",
    "EinstellungenLaden", "ist_konfiguriert", "einstellungen_lesen",
    "sende", "sende_loeschbestaetigung", "sende_ablehnung",
    "NICHT_EINGERICHTET", "VERBINDUNG",
]

#: Testnaht: ein Fake-SMTP-Client, den `sende()` benutzt, statt eine echte
#: Verbindung aufzubauen. Im Betrieb IMMER `None` — kein Schalter in den
#: Einstellungen, keine ENV, kein Pfad vom Netz dorthin.
VERBINDUNG = None

#: Meldung, wenn gar kein Versandweg eingerichtet ist. NEUTRAL formuliert
#: (N3, R-DSGVO-2a): derselbe Text gilt für JEDEN Versand — Bestätigen,
#: Ablehnen und alles Künftige. Eine Formulierung wie „die Löschung kann nicht
#: bestätigt werden“ war beim Ablehnen falsch, weil dort nichts bestätigt wird.
NICHT_EINGERICHTET = (
    "Mailversand ist nicht eingerichtet — ohne ihn kann der Löschantrag "
    "nicht bearbeitet werden."
)


class MailNichtEingerichtet(RuntimeError):
    """SMTP ist nicht konfiguriert — es wurde NICHTS versucht."""


class MailVersandFehler(RuntimeError):
    """Der Versand ist versucht worden und fehlgeschlagen.

    ``art`` ist eine von ``anmeldung`` / ``abgelehnt`` / ``server`` /
    ``zertifikat`` / ``zeit`` / ``sonstiges`` — die Oberfläche formuliert daraus
    einen Satz für Ehrenamtliche, statt die Rohdaten des Servers zu zeigen (S3).
    ``abgelehnt`` heisst: der Server ist erreichbar und hat die Mail abgelehnt
    (etwa 550 „Absender nicht erlaubt“) — das ist NICHT „nicht erreichbar“
    (MAIL-1b, N5).
    """

    def __init__(self, meldung: str, art: str = "sonstiges") -> None:
        super().__init__(meldung)
        self.art = art


@dataclass(frozen=True)
class Einstellungen:
    """Die wirksamen Versand-Einstellungen. `passwort` NIE ausgeben."""

    host: str
    port: int
    sicherheit: str
    benutzername: str = ""
    passwort: str = ""
    absender: str = ""
    absender_name: str = "Diakronos"
    timeout: float = 15.0


@dataclass(frozen=True)
class Mail:
    """Eine fertige Nachricht. `an` ist genau eine Adresse (kein Verteiler)."""

    an: str
    betreff: str
    text: str

    def als_nachricht(self, absender: str, absender_name: str = "Diakronos") -> EmailMessage:
        msg = EmailMessage()
        msg["From"] = formataddr((absender_name or "Diakronos", absender))
        msg["To"] = self.an
        msg["Subject"] = self.betreff
        msg["Message-ID"] = make_msgid(domain=(absender.split("@")[-1] or None))
        msg.set_content(self.text)
        return msg


class EinstellungenLaden(RuntimeError):
    """Die gespeicherten Einstellungen liessen sich nicht lesen/entschluesseln.

    Getrennt von `MailNichtEingerichtet`: eine vorhandene, aber unbrauchbare
    Zeile (etwa ein Passwort, das der geänderte SECRET_KEY nicht mehr öffnet)
    ist ein Fehler, kein „nicht eingerichtet“ — der Administrator muss es
    erfahren, statt eine stille Ablehnung zu sehen.
    """


def einstellungen_lesen() -> Einstellungen | None:
    """Die Einstellungen aus der Datenbank; ``None`` = nicht eingerichtet.

    MAIL-1, K3-Lehre: die Sitzung wird GELIEHEN (`lesesitzung`), nicht
    geöffnet. Mitten im Löschablauf hält der Aufrufer eine Transaktion mit
    einem SAVEPOINT; `close()` auf einer zweiten Sitzung rollt auf einer
    Datenbank mit EINER Verbindung je Engine die offene Transaktion mit
    („no such savepoint“ — genau der Fehler, den SEC-c fuer `_gemeindename()`
    schon einmal behoben hat). Eine geliehene Sitzung wird nie geschlossen und
    nie geleert. Der Klartext des Passworts lebt nur in diesem Aufruf und wird
    nie geloggt.
    """
    from sqlalchemy import select

    from diakronos_app.db import lesesitzung
    from diakronos_app.frappe_compat.exceptions import ValidationError
    from diakronos_app.models.smtp import SmtpEinstellungen
    from diakronos_app.smtp_einstellungen import als_dict, entschluessle

    try:
        with lesesitzung() as s:
            zeile = s.scalars(select(SmtpEinstellungen).limit(1)).first()
            if zeile is None:
                return None
            daten = als_dict(zeile)
            passwort = entschluessle(zeile.passwort_verschluesselt)
    except ValidationError as ex:
        raise EinstellungenLaden(str(ex)) from None
    except Exception as ex:  # noqa: BLE001 — jede Ursache wird zur klaren Meldung
        # Kein `str(ex)` in der Meldung: die Ursache kann Spaltenwerte nennen.
        raise EinstellungenLaden(
            "Die gespeicherten Einstellungen für den Mailversand lassen sich "
            "nicht lesen. Bitte in den Einstellungen neu speichern."
        ) from None
    if not daten.get("host") or not daten.get("absender"):
        return None
    return Einstellungen(
        host=str(daten["host"]).strip(),
        port=int(daten["port"]),
        sicherheit=str(daten["sicherheit"]),
        benutzername=str(daten.get("benutzername") or ""),
        passwort=str(passwort or ""),
        absender=str(daten["absender"]).strip(),
        absender_name=str(daten.get("absender_name") or "Diakronos"),
        timeout=float(daten.get("timeout") or 15.0),
    )


def ist_konfiguriert() -> bool:
    """Sind Server und Absender gesetzt? Nur dann darf „Bestätigen“ senden."""
    try:
        return einstellungen_lesen() is not None
    except EinstellungenLaden as ex:
        # Nicht eingerichtet ist die sichere Antwort: es wird nichts versucht.
        # Der Grund steht im Protokoll — die Meldung an den Aufrufer bleibt
        # „nicht eingerichtet“ (fail closed).
        import logging

        logging.getLogger("diakronos_app.mailversand").warning(
            "Mailversand: %s", ex)
        return False


def _verbindung_oeffnen(host: str, port: int, timeout: float, ssl_: bool, starttls: bool):
    """Baut die SMTP-Verbindung auf — MIT Zertifikatsprüfung (M2, R-DSGVO-1).

    Ohne `context=` benutzt `smtplib` intern `ssl._create_stdlib_context()`,
    also `CERT_NONE` und `check_hostname=False`: Zugangsdaten und Mailinhalt
    wären per MITM abgreifbar. `ssl.create_default_context()` prüft Kette und
    Hostnamen und ist damit der einzige vertretbare Standard für einen Kanal,
    über den Personendaten gehen.
    """
    context = ssl.create_default_context()
    if ssl_:
        return smtplib.SMTP_SSL(host, port, timeout=timeout, context=context)
    client = smtplib.SMTP(host, port, timeout=timeout)
    if starttls:
        client.ehlo()
        if not client.has_extn("starttls"):
            raise MailVersandFehler(
                "Der Mailserver unterstützt kein STARTTLS — Versand abgebrochen "
                "(unverschlüsselt werden keine Personendaten verschickt).",
                art="sonstiges",
            )
        client.starttls(context=context)
        client.ehlo()
    return client


def _entschaerfe(text: str, *geheim: str) -> str:
    """Passwort/Benutzer aus einer Fehlermeldung entfernen (Defensive)."""
    ergebnis = str(text or "")
    for wert in geheim:
        if wert:
            ergebnis = ergebnis.replace(wert, "***")
    return ergebnis[:400]


def _art(ex: Exception) -> str:
    """Fehlerursache in eine der Kategorien aus S3 übersetzen.

    Reihenfolge ist wichtig (MAIL-1b, N5): `SMTPException` IST eine Unterklasse
    von `OSError`. Wer zuerst `OSError` prüft, macht aus „550 Absender
    abgelehnt“ ein irreführendes „Server nicht erreichbar“. Deshalb kommen die
    Antwort-Fehler des Servers (``abgelehnt``) VOR den Verbindungsfehlern.
    """
    if isinstance(ex, smtplib.SMTPAuthenticationError):
        return "anmeldung"
    if isinstance(ex, ssl.SSLCertVerificationError):
        return "zertifikat"
    if isinstance(ex, smtplib.SMTPConnectError):
        return "server"
    # 4xx/5xx-Antwort des Servers: er ist erreichbar und hat geantwortet.
    # `SMTPRecipientsRefused` ist KEINE Antwortklasse (kein 4xx/5xx-Träger),
    # fachlich aber dasselbe: der Server hat den Empfänger abgelehnt.
    if isinstance(ex, (smtplib.SMTPResponseException, smtplib.SMTPRecipientsRefused)):
        return "abgelehnt"
    if isinstance(ex, (TimeoutError, smtplib.SMTPServerDisconnected)):
        return "zeit"
    if isinstance(ex, OSError):
        return "server"
    return "sonstiges"


def sende(mail: Mail, *, verbindung=None, einstellungen: Einstellungen | None = None) -> None:
    """Verschickt `mail`. Wirft `MailNichtEingerichtet` / `MailVersandFehler`.

    `verbindung` ist die Testnaht: ein Objekt mit derselben kleinen
    Schnittstelle wie `smtplib.SMTP` (`ehlo`, `starttls`, `login`, `send_message`,
    `quit`, `has_extn`). Ohne Argument gilt `VERBINDUNG`; im Betrieb ist beides
    `None` und es wird eine echte SMTP-Verbindung aufgebaut (und wieder
    geschlossen).

    `einstellungen` erlaubt es, geprüfte Werte durchzureichen (die Testmail in
    der Oberfläche prüft VOR dem Speichern die eingegebenen Werte) — ohne
    Argument gilt die Datenbank.
    """
    if verbindung is None:
        verbindung = VERBINDUNG
    if einstellungen is None:
        try:
            einstellungen = einstellungen_lesen()
        except EinstellungenLaden as ex:
            raise MailNichtEingerichtet(str(ex)) from None
    if einstellungen is None:
        raise MailNichtEingerichtet(NICHT_EINGERICHTET)
    s = einstellungen
    if not s.host or not s.absender:
        raise MailNichtEingerichtet(NICHT_EINGERICHTET)
    if not mail.an or "@" not in mail.an:
        raise MailVersandFehler("Für diese Person ist keine gültige E-Mail-Adresse hinterlegt.")

    eigen = verbindung is None
    client = None
    try:
        # MAIL-1b (N2): der Aufbau der Nachricht gehoert IN den try — ein
        # Steuerzeichen in einem Kopffeld warf vorher einen `ValueError`, der
        # als 500 beim Aufrufer ankam und den Löschablauf lahmlegte.
        nachricht = mail.als_nachricht(s.absender, s.absender_name)
        if eigen:
            client = _verbindung_oeffnen(
                s.host, int(s.port), float(s.timeout),
                ssl_=s.sicherheit == "ssl", starttls=s.sicherheit == "starttls",
            )
        else:
            # Die Testnaht bildet denselben Ablauf ab: ein Server ohne STARTTLS
            # bekommt keine Personendaten im Klartext.
            client = verbindung
            if s.sicherheit == "starttls":
                client.ehlo()
                if not client.has_extn("starttls"):
                    raise MailVersandFehler(
                        "Der Mailserver unterstützt kein STARTTLS — Versand abgebrochen "
                        "(unverschlüsselt werden keine Personendaten verschickt)."
                    )
                client.starttls()
        if s.benutzername:
            # Erst nach TLS anmelden: Zugangsdaten nie im Klartext.
            client.login(str(s.benutzername), str(s.passwort or ""))
        client.send_message(nachricht)
    except (MailVersandFehler, MailNichtEingerichtet):
        raise
    except Exception as ex:  # noqa: BLE001 — jede Ursache wird zur fachlichen Meldung
        raise MailVersandFehler(
            "Der Versand der E-Mail ist fehlgeschlagen: "
            + _entschaerfe(str(ex), str(s.passwort or ""), str(s.benutzername or "")),
            art=_art(ex),
        ) from None
    finally:
        if eigen and client is not None:
            try:
                client.quit()
            except Exception:  # noqa: BLE001 — Aufraeumen darf den Fehler nicht ersetzen
                pass


def _gemeindename() -> str:
    """Gemeindename aus den Einstellungen; ohne Eintrag neutral „Diakronos“."""
    try:
        from sqlalchemy import select

        from diakronos_app.db import SessionLocal
        from diakronos_app.models.diakronos import DiakronosEinstellungen

        with SessionLocal() as s:
            zeile = s.scalars(select(DiakronosEinstellungen).limit(1)).first()
            name = str(getattr(zeile, "organisationsname", "") or "").strip()
            return name or "Diakronos"
    except Exception:  # noqa: BLE001 — die Mail darf nicht an der Anrede scheitern
        return "Diakronos"


def sende_loeschbestaetigung(an: str, *, verbindung=None, gemeinde: str | None = None) -> None:
    """Die Meldung aus D4: „Deine Daten in Diakronos werden jetzt gelöscht …“.

    Knapp, deutsch, ohne Anrede mit Klarnamen (die Anonymisierung folgt
    unmittelbar) und ohne Rückfrage-Link — die Löschung ist nicht rückgängig
    zu machen (Fachentscheidung Manuel).

    `gemeinde` erlaubt dem Aufrufer, den Namen VORHER zu lesen: `_gemeindename()`
    öffnet eine eigene Sitzung, und mitten in der Löschtransaktion würde deren
    `close()` auf einer Datenbank mit EINER Verbindung je Engine die offene
    Transaktion mitreissen (R-DSGVO-1, K3 — Realisierung: SAVEPOINT).
    """
    if gemeinde is None:
        gemeinde = _gemeindename()
    text = (
        f"Guten Tag\n\n"
        f"deine Daten in {gemeinde} werden jetzt gelöscht.\n\n"
        "Deine Löschung wurde von der Gemeindeverwaltung bestätigt. Wir entfernen "
        "jetzt deinen Namen, deine Kontaktdaten, dein Benutzerkonto und deine "
        "Anmeldedaten. In Plänen und Dienstplänen bleibt nur ein neutraler Eintrag "
        "„Gelöschte Person“, damit die Einteilung nachvollziehbar bleibt.\n\n"
        "Diese Löschung ist endgültig und kann nicht rückgängig gemacht werden.\n"
        "Wenn du später wieder mitmachen möchtest, kannst du dich mit derselben "
        "E-Mail-Adresse neu anmelden.\n\n"
        f"Viele Grüße\n{gemeinde}\n\n"
        "— Diese Nachricht wurde automatisch verschickt.\n"
    )
    sende(Mail(an=an, betreff=f"Deine Daten in {gemeinde} werden gelöscht", text=text),
          verbindung=verbindung)


def sende_ablehnung(an: str, begruendung: str, *, verbindung=None,
                    gemeinde: str | None = None) -> None:
    """Die Meldung an die Person, wenn die Verwaltung den Antrag ABLEHNT.

    Anders als `sende_loeschbestaetigung` geht diese Mail VOR jeglicher
    Löschung raus (DSGVO-2a): Die Person behält alle Daten und muss erfahren,
    warum — und was sie danach tun kann. Beides steht deshalb im Text:
    erneuter Antrag und Beschwerde bei der Aufsichtsbehörde (Art. 77 DSGVO).

    Kein Rückfrage-Link: die Entscheidung trifft die Verwaltung; die Person
    wendet sich an sie oder an die Aufsichtsbehörde.

    `gemeinde` erlaubt dem Aufrufer, den Namen VORHER zu lesen — gleiche
    Begründung wie bei `sende_loeschbestaetigung` (eigene Sitzung in
    `_gemeindename()` würde eine laufende Transaktion mitreißen).
    """
    if gemeinde is None:
        gemeinde = _gemeindename()
    grund = str(begruendung or "").strip()
    text = (
        "Guten Tag\n\n"
        f"dein Antrag auf Löschung deiner Daten in {gemeinde} wurde geprüft und "
        "abgelehnt.\n\n"
        f"Begründung der Gemeindeverwaltung:\n{grund}\n\n"
        "Deine Daten bleiben damit gespeichert; gelöscht wurde nichts.\n\n"
        "Du kannst den Antrag erneut stellen, wenn die Gründe für die Ablehnung "
        "weggefallen sind oder du eine andere Entscheidung erwirken möchtest — "
        "stelle ihn dazu einfach wieder in deinem Profil.\n\n"
        "Wenn du mit dieser Entscheidung nicht einverstanden bist, kannst du dich "
        "bei einer Datenschutz-Aufsichtsbehörde beschweren (Art. 77 DSGVO). "
        "Zuständig ist meist die Behörde deines Wohnorts.\n\n"
        f"Viele Grüße\n{gemeinde}\n\n"
        "— Diese Nachricht wurde automatisch verschickt.\n"
    )
    # Betreff und Adresse stehen fest, die Begründung steht im Textkörper. Sie
    # wird nicht still umgeschrieben: die API lehnt Steuerzeichen ab (DSGVO-2a).
    sende(Mail(an=an, betreff=f"Löschantrag bei {gemeinde} abgelehnt", text=text),
          verbindung=verbindung)

