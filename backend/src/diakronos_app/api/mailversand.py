"""MAIL-1: Oberflaeche fuer den Mailversand (nur System Manager).

Der Abschnitt „Mailversand“ liegt im Admin-Bereich (`#/einstellungen/mailversand`)
und ist **ausschliesslich fuer System Manager** („Hauptadmin“, S2):

* **lesen und aendern** — nur System Manager. Das Postfach entscheidet ueber
  ALLE ausgehenden Mails der Instanz (Löschbestätigungen, später mehr); wer es
  umstellt, kann Mails umleiten. Deshalb dieselbe Schranke wie bei der
  Datensicherung (`_angemeldeter_system_manager`).
* **Mitgliederadministratoren** sehen hoechstens „eingerichtet: ja/nein“ —
  dafuer gibt es `mailversand_status` (kein Host, kein Absender, kein
  Benutzername).

WAS DIESE ENDPUNKTE BEWUSST NICHT KOENNEN (S1)
---------------------------------------------
* **kein Passwort in der Antwort** — nur `passwort_gesetzt: true/false`. Es
  gibt keinen Endpunkt, der den Klartext liefert.
* **kein Passwort im Audit-Log** — protokolliert wird, DASS und von WEM
  geaendert wurde, nicht der Inhalt.
* **keine Rohdaten des Servers in einer Fehlermeldung** — `testmail` uebersetzt
  die Ursache in einen Satz (Anmeldung abgelehnt / nicht erreichbar /
  Zertifikat / Zeitüberschreitung) und filtert Passwort und Benutzername aus
  allem, was der Server zuruecksagt.

Endpunkt-Pfade (die SPA ruft die Frappe-Form):
``diakronos.diakonos.api.mailversand.<name>``.
"""

from __future__ import annotations

FRAPPE_MODULE = "diakronos.diakonos.api.mailversand"

import logging

from diakronos_app import db
from diakronos_app.api.audit import log as _audit_log
from diakronos_app.frappe_compat import whitelist
from diakronos_app.frappe_compat.exceptions import (
	FrappeCompatError,
	PermissionError as FrappePermissionError,
	ValidationError,
	throw,
)
from diakronos_app.frappe_compat.permissions import get_roles, is_admin
from diakronos_app.frappe_compat.session import session
from diakronos_app.models.smtp import STANDARD_TIMEOUT
from diakronos_app import smtp_einstellungen as einstellungen_modul

logger = logging.getLogger("diakronos_app.api.mailversand")

__all__ = [
	"mailversand_get",
	"mailversand_status",
	"mailversand_speichern",
	"mailversand_testmail",
]

#: Meldung, die ein Mitgliederadministrator hoechstens zu sehen bekommt.
_STATUS_OHNE_RECHTE = "Nur System Manager dürfen den Mailversand einstellen."


def _angemeldeter_system_manager() -> str:
	"""Nur System Manager — gleiche Pruefung wie ``api/sicherung.py``."""
	user = str(session.user or "").strip()
	if not user or user == "Guest":
		throw("Anmeldung verweigert.", FrappePermissionError)
	if "System Manager" not in get_roles():
		throw(_STATUS_OHNE_RECHTE, FrappePermissionError)
	return user


def _angemeldeter_admin() -> str:
	"""Irgendein Administrator — reicht fuer „eingerichtet: ja/nein“."""
	user = str(session.user or "").strip()
	if not user or user == "Guest":
		throw("Anmeldung verweigert.", FrappePermissionError)
	if not is_admin(user):
		throw("Anmeldung verweigert.", FrappePermissionError)
	return user


@whitelist(allow_guest=False)
def mailversand_get() -> dict:
	"""Einstellungen fuer die Oberflaeche (nur System Manager, ohne Passwort)."""
	_angemeldeter_system_manager()
	sess = db.SessionLocal()
	try:
		zeile = einstellungen_modul.holen(sess)
		return {
			"einstellungen": einstellungen_modul.als_dict(zeile),
			"standards": {
				"port": 587,
				"timeout": STANDARD_TIMEOUT,
			},
			"meine_adresse": str(getattr(session, "user", "") or ""),
		}
	finally:
		sess.close()


@whitelist(allow_guest=False)
def mailversand_status() -> dict:
	"""Nur „eingerichtet: ja/nein“ — fuer Mitgliederadministratoren (S2).

	Bewusst OHNE Server, Absender oder Benutzername: die Angaben zeigen, wohin
	die Post der Gemeinde geht, und gehen einen Mitgliederadministrator nichts
	an. Der Hinweis auf der Datenschutz-Seite braucht nur diese eine Auskunft.
	"""
	_angemeldeter_admin()
	from diakronos_app.mailversand import EinstellungenLaden, einstellungen_lesen

	system_manager = "System Manager" in get_roles()
	try:
		eingerichtet = einstellungen_lesen() is not None
		fehler = ""
	except EinstellungenLaden as ex:
		# Eine kaputte Zeile ist NICHT „eingerichtet“ — aber der Grund gehoert
		# dem, der es reparieren kann (System Manager), nicht hierher.
		# R-MAIL-1 (Kleinkram zu N5): die Meldung kann Spaltenwerte nennen
		# (etwa einen Klartext in `passwort_verschluesselt`) und bleibt deshalb
		# beim System Manager.
		eingerichtet = False
		fehler = str(ex) if system_manager else ""
	return {
		"eingerichtet": eingerichtet,
		"darf_aendern": system_manager,
		"hinweis": fehler,
	}


@whitelist(allow_guest=False)
def mailversand_speichern(host=None, port=None, sicherheit=None, benutzername="",
                          passwort="", passwort_entfernen=False, absender=None,
                          absender_name="", timeout=None) -> dict:
	"""Einstellungen pruefen und speichern (EINE Transaktion, S1).

	Ein leeres `passwort` laesst das hinterlegte Passwort unveraendert — die
	Oberflaeche bekommt es nie zurueck und kann es deshalb auch nicht erneut
	mitschicken.
	"""
	benutzer = _angemeldeter_system_manager()
	sess = db.SessionLocal()
	try:
		vorher = einstellungen_modul.als_dict(einstellungen_modul.holen(sess))
		try:
			zeile = einstellungen_modul.speichern(
				sess, benutzer=benutzer, host=host, port=port,
				sicherheit=sicherheit, benutzername=benutzername,
				passwort=passwort, passwort_entfernen=bool(passwort_entfernen),
				absender=absender, absender_name=absender_name,
				timeout=STANDARD_TIMEOUT if timeout is None else timeout,
			)
		except einstellungen_modul.EinstellungFehler as fehler:
			raise ValidationError(str(fehler)) from None
		neu = einstellungen_modul.als_dict(zeile)
	finally:
		sess.close()

	# S2: Aenderung ins Audit-Log — OHNE Passwort, ohne Benutzername des
	# Mailkontos. NUR die Felder, die sich fachlich geaendert haben.
	geaendert = [
		feld for feld in ("host", "port", "sicherheit", "absender",
		                  "absender_name", "timeout")
		if vorher.get(feld) != neu.get(feld)
	]
	if vorher.get("passwort_gesetzt") != neu.get("passwort_gesetzt"):
		geaendert.append("passwort_gesetzt")
	_audit_log(
		action_typ="Berechtigungsänderung",
		target_doctype="Einstellungen",
		target_name="Mailversand",
		begruendung=(
			"Mailversand-Einstellungen geändert: "
			+ (", ".join(geaendert) if geaendert else "ohne inhaltliche Änderung")
		),
	)
	return {"gespeichert": True, "einstellungen": neu}


@whitelist(allow_guest=False)
def mailversand_testmail(host=None, port=None, sicherheit=None, benutzername="",
                         passwort="", absender=None, absender_name="",
                         timeout=None) -> dict:
	"""„Testmail senden“ an die Adresse des angemeldeten System Managers (S3).

	Mit uebergebenen Feldern werden DIESE benutzt (der Administrator probt,
	bevor er speichert — das ist der Sinn des Knopfes).

	MAIL-1b (N1): Ein leeres `passwort` heisst NUR dann „das gespeicherte
	verwenden“, wenn Server und Benutzer unveraendert sind. Weicht eines von
	beiden ab, wird das gespeicherte Passwort NICHT benutzt — sonst ginge es
	an einen fremden Server (wer eine System-Manager-Sitzung hat, koennte es
	mit einem eigenen Host abholen). Dann gibt es eine Fehlermeldung.

	Die Antwort nennt nur Erfolg und Empfaenger; die Fehlermeldung ist ein Satz
	fuer Ehrenamtliche, nie die Rohantwort des Servers.
	"""
	benutzer = _angemeldeter_system_manager()
	from diakronos_app import mailversand
	from diakronos_app.models.core import User

	sess = db.SessionLocal()
	try:
		konto = sess.get(User, benutzer)
		adresse = str(getattr(konto, "email", "") or "").strip()
		gespeichert = einstellungen_modul.holen(sess)
		gespeicherte_werte = einstellungen_modul.als_dict(gespeichert)
		passwort_klartext = ""
		verworfen = False
		if passwort:
			passwort_klartext = str(passwort)
		elif gespeichert is not None and gespeichert.passwort_verschluesselt:
			# N1: nur weiterreichen, wenn das Ziel dasselbe ist.
			if einstellungen_modul.gleicher_stand(
					gespeicherte_werte,
					{"host": host if host is not None else gespeicherte_werte.get("host"),
					 "benutzername": (benutzername if benutzername
					                  else gespeicherte_werte.get("benutzername"))}):
				passwort_klartext = einstellungen_modul.entschluessle(
					gespeichert.passwort_verschluesselt)
			else:
				verworfen = True
	finally:
		sess.close()

	if not adresse or "@" not in adresse:
		raise ValidationError(
			"Für dein Konto ist keine E-Mail-Adresse hinterlegt — die Testmail "
			"kann nicht zugestellt werden."
		)
	if verworfen:
		raise ValidationError(einstellungen_modul.passwort_verworfen_meldung())

	# Ohne uebergebene Werte gilt der gespeicherte Stand („nur mal testen“).
	if host is None:
		host = gespeicherte_werte.get("host") or ""
	if port is None:
		port = gespeicherte_werte.get("port") or 587
	if sicherheit is None:
		sicherheit = gespeicherte_werte.get("sicherheit") or "starttls"
	if not benutzername:
		benutzername = gespeicherte_werte.get("benutzername") or ""
	if absender is None:
		absender = gespeicherte_werte.get("absender") or ""
	if not absender_name:
		absender_name = gespeicherte_werte.get("absender_name") or ""
	if timeout is None:
		timeout = gespeicherte_werte.get("timeout") or STANDARD_TIMEOUT

	if not str(host or "").strip() or not str(absender or "").strip():
		raise ValidationError(
			"Bitte zuerst Server und Absenderadresse eintragen — ohne sie kann "
			"keine Mail rausgehen."
		)

	# Dieselbe Pruefung wie beim Speichern: ein Tippfehler soll hier auffallen
	# und nicht erst beim ersten Loeschantrag.
	try:
		einstellungen_modul.pruefen(
			host=host, port=port, sicherheit=sicherheit, benutzername=benutzername,
			absender=absender, absender_name=absender_name, timeout=timeout,
			passwort_gesetzt=bool(passwort_klartext),
		)
	except einstellungen_modul.EinstellungFehler as fehler:
		raise ValidationError(str(fehler)) from None

	werte = mailversand.Einstellungen(
		host=str(host).strip(), port=int(port), sicherheit=str(sicherheit),
		benutzername=str(benutzername or ""), passwort=passwort_klartext,
		absender=str(absender).strip(),
		absender_name=str(absender_name or "").strip() or "Diakronos",
		timeout=float(timeout),
	)
	mail = mailversand.Mail(
		an=adresse,
		betreff="Testmail aus Diakronos",
		text=(
			"Guten Tag\n\n"
			"diese Testmail zeigt, dass der Mailversand aus Diakronos "
			"funktioniert. Du musst nichts weiter tun.\n\n"
			"Wenn du diese Nachricht liest, kommen auch die Meldungen zur "
			"Löschung auf Antrag bei den Mitgliedern an.\n\n"
			"Viele Grüße\nDiakronos\n\n"
			"— Diese Nachricht wurde automatisch verschickt.\n"
		),
	)
	try:
		mailversand.sende(mail, einstellungen=werte)
	except mailversand.MailNichtEingerichtet as ex:
		raise ValidationError(str(ex)) from None
	except mailversand.MailVersandFehler as ex:
		# S3: verstaendlicher Satz, KEINE Rohdaten. `str(ex)` ist bereits durch
		# `_entschaerfe` gefiltert (Passwort/Benutzer ersetzt) und wird nur fuer
		# die Kategorie `sonstiges` angehaengt.
		raise ValidationError(_testmail_meldung(ex)) from None

	_audit_log(
		action_typ="Sonstiges",
		target_doctype="Einstellungen",
		target_name="Mailversand",
		begruendung=f"Testmail an {adresse} verschickt",
	)
	return {"gesendet": True, "an": adresse}


def _testmail_meldung(fehler: "Exception") -> str:
	"""S3: Ursache -> Satz fuer Ehrenamtliche."""
	art = getattr(fehler, "art", "sonstiges")
	if art == "anmeldung":
		return (
			"Der Mailserver hat die Anmeldung abgelehnt. Bitte Benutzername und "
			"Passwort prüfen — manche Anbieter brauchen ein eigenes "
			"„App-Passwort“."
		)
	if art == "zertifikat":
		return (
			"Das Zertifikat des Mailservers ist ungültig oder passt nicht zum "
			"Servernamen. Bitte den Servernamen prüfen. Aus Sicherheitsgründen "
			"werden E-Mails mit Personendaten nicht ungeprüft verschickt."
		)
	if art == "zeit":
		return (
			"Der Mailserver hat nicht rechtzeitig geantwortet "
			"(Zeitüberschreitung). Bitte Port und Verschlüsselung prüfen und es "
			"erneut versuchen."
		)
	if art == "server":
		return (
			"Der Mailserver ist nicht erreichbar. Bitte den Servernamen und den "
			"Port prüfen."
		)
	if art == "abgelehnt":
		# N5: der Server IST erreichbar und hat die Mail abgelehnt (4xx/5xx).
		# Häufigste Ursachen: Absenderadresse nicht erlaubt, Empfänger
		# unbekannt, Nachricht als Spam eingestuft.
		return (
			"Der Mailserver hat die Nachricht abgelehnt. Meist liegt es an der "
			"Absenderadresse: manche Anbieter erlauben nur die eigene Adresse "
			"des Postfachs. Bitte Absenderadresse und Empfänger prüfen."
		)
	return f"Der Versand der Testmail ist fehlgeschlagen: {fehler}"
