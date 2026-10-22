"""BACKUP-1: Oberflaeche der Datensicherung (nur System Manager).

Der Bereich „Datensicherung“ liegt im Admin-Bereich und ist **ausschliesslich
fuer System Manager**: die Einstellungen entscheiden ueber die Lebensdauer der
Personendaten des ganzen Bestands, und die Liste nennt Zeitpunkte und
Groessen der Kopien. Ein Mitgliederadministrator hat dort nichts zu suchen —
``_require_system_manager`` (dieselbe Pruefung wie in ``api/zugang.py``) weist
ihn mit 403 ab; die Oberflaeche blendet den Abschnitt zusaetzlich aus, aber
das ist nur Komfort.

WAS DIESE ENDPUNKTE BEWUSST NICHT KOENNEN (Karte B3/B4)
-------------------------------------------------------
* **kein Herunterladen** — es gibt keinen Endpunkt, der Dump oder Archiv
  liefert. Die Dateien liegen mit Rechten 0600 in einem Verzeichnis 0700
  ausserhalb des HTTP-Wurzelbaums; die Wiederherstellung ist ein
  Kommandozeilen-Vorgang (BETRIEBSANLEITUNG).
* **kein Wiederherstellen** — kein Endpunkt ruft ``pg_restore`` auf.
* **kein Pfad in der Antwort** — die Liste nennt Zeitpunkt, Groesse und
  Status, nie ``settings.backup_dir``. Ein Pfad im Browser ist der erste
  Schritt zu einem Download, und er verraet die Verzeichnisstruktur.
* **keine Zugangsdaten** — siehe ``sicherung/dump.py`` (Modulkopf).

Endpunkt-Pfade (die SPA ruft die Frappe-Form):
``diakronos.diakonos.api.sicherung.<name>``.
"""

from __future__ import annotations

FRAPPE_MODULE = "diakronos.diakonos.api.sicherung"

import logging
from datetime import datetime

from sqlalchemy import select

from diakronos_app import db
from diakronos_app.frappe_compat import whitelist
from diakronos_app.frappe_compat.exceptions import (
	DoesNotExistError,
	FrappeCompatError,
	PermissionError as FrappePermissionError,
	ValidationError,
	throw,
)
from diakronos_app.frappe_compat.session import session
from diakronos_app.models.sicherung import Sicherungslauf
from diakronos_app.sicherung import aufbewahrung, dump, einstellungen as einstellungen_modul
from diakronos_app.sicherung import lauf as lauf_modul
from diakronos_app.sicherung.sperre import SperreBesteht, SperreNichtVerfuegbar

logger = logging.getLogger("diakronos_app.api.sicherung")

__all__ = [
	"sicherung_get",
	"sicherung_einstellungen_speichern",
	"sicherung_jetzt",
	"sicherung_loeschen",
]

#: So viele Laeufe zeigt die Liste hoechstens (die Aufbewahrung begrenzt die
#: Zahl ohnehin; das hier ist eine Obergrenze fuer die Antwort).
MAX_LAEUFE = 100


def _angemeldeter_system_manager() -> str:
	"""Nur System Manager — gleiche Pruefung wie ``api/zugang.py``."""
	user = str(session.user or "").strip()
	if not user or user == "Guest":
		throw("Anmeldung verweigert.", FrappePermissionError)
	from diakronos_app.frappe_compat.permissions import get_roles

	if "System Manager" not in get_roles():
		throw(
			"Nur System Manager dürfen die Datensicherung einstellen.",
			FrappePermissionError,
		)
	return user


def _sicherungsname(wert: object) -> str:
	"""Name einer Sicherung pruefen — nur das Zeitstempel-Muster ist erlaubt.

	Ohne diese Schranke waere ``name`` ein Pfadbestandteil aus dem Browser
	(``../../etc``). ``ist_sicherungsname`` laesst ausschliesslich
	``JJJJ-MM-TT_HHMMSS`` durch.
	"""
	name = str(wert or "").strip()
	if not aufbewahrung.ist_sicherungsname(name):
		throw("Diese Sicherung gibt es nicht.", DoesNotExistError)
	return name


def _laeufe(sess) -> list[dict]:
	zeilen = list(sess.scalars(
		select(Sicherungslauf)
		.order_by(Sicherungslauf.begonnen_am.desc())
		.limit(MAX_LAEUFE)
	))
	ergebnis = []
	for zeile in zeilen:
		ergebnis.append({
			"name": zeile.name,
			"zeitpunkt": zeile.begonnen_am.isoformat() if zeile.begonnen_am else "",
			"groesse_bytes": int(zeile.groesse_bytes or 0),
			"status": zeile.status,
			"ausloeser": zeile.ausloeser,
			"meldung": zeile.meldung or "",
		})
	return ergebnis


@whitelist(allow_guest=False)
def sicherung_get() -> dict:
	"""Einstellungen, Liste der Sicherungen und Zustand des Ablageorts."""
	_angemeldeter_system_manager()
	sess = db.SessionLocal()
	try:
		zeile = einstellungen_modul.holen_oder_anlegen(sess)
		return {
			"einstellungen": einstellungen_modul.als_dict(zeile),
			"sicherungen": _laeufe(sess),
			"ablage": lauf_modul.status_fuer_oberflaeche(sess),
			"maximum_aufbewahrung_tage": 3650,
		}
	finally:
		sess.close()


@whitelist(allow_guest=False)
def sicherung_einstellungen_speichern(automatisch=None, uhrzeit=None,
                                     aufbewahrung_tage=None) -> dict:
	"""Einstellungen pruefen und speichern (EINE Transaktion)."""
	benutzer = _angemeldeter_system_manager()
	sess = db.SessionLocal()
	try:
		try:
			zeile = einstellungen_modul.speichern(
				sess, automatisch=automatisch, uhrzeit=uhrzeit,
				aufbewahrung_tage=aufbewahrung_tage, benutzer=benutzer,
			)
		except einstellungen_modul.EinstellungFehler as fehler:
			raise ValidationError(str(fehler)) from None
		return {"gespeichert": True, "einstellungen": einstellungen_modul.als_dict(zeile)}
	finally:
		sess.close()


@whitelist(allow_guest=False)
def sicherung_jetzt() -> dict:
	"""„Jetzt sichern“ — ein Lauf von Hand, synchron.

	Synchron ist hier richtig: der Administrator drueckt den Knopf und will
	wissen, ob es geklappt hat. Ist die Sicherung groesser als die Geduld
	(oder der Proxy-Zeitablauf), nennt die Antwort trotzdem das Ergebnis —
	der Lauf selbst wird nicht abgebrochen, weil der Client auflegt.
	"""
	_angemeldeter_system_manager()
	sess = db.SessionLocal()
	try:
		try:
			ergebnis = lauf_modul.fuehre_aus(
				ausloeser=lauf_modul.AUSLOESER_MANUELL, sitzung=sess,
			)
		except SperreBesteht as fehler:
			raise ValidationError(str(fehler)) from None
		except SperreNichtVerfuegbar as fehler:
			raise FrappeCompatError(str(fehler)) from None
		return {
			"ok": ergebnis.ok,
			"name": ergebnis.name,
			"status": ergebnis.status,
			"meldung": ergebnis.meldung,
			"groesse_bytes": ergebnis.groesse_bytes,
			"entfernt": ergebnis.entfernt,
		}
	finally:
		sess.close()


@whitelist(allow_guest=False)
def sicherung_loeschen(name: str | None = None) -> dict:
	"""Eine einzelne Sicherung loeschen (mit Bestaetigungsdialog in der UI).

	Die NEUESTE erfolgreiche Sicherung ist auch hier geschuetzt — derselbe
	Grund wie bei der Aufbewahrung: ein Fehlgriff im Dialog darf nicht die
	letzte Kopie kosten. Wer sie wirklich weghaben will, sichert vorher neu.
	"""
	_angemeldeter_system_manager()
	geprueft = _sicherungsname(name)
	sess = db.SessionLocal()
	try:
		zeile = sess.get(Sicherungslauf, geprueft)
		basis = dump.ziel_basis()
		verzeichnis = basis / geprueft
		vorhanden = list(aufbewahrung.sicherungen_im_verzeichnis(basis))
		erfolgreich = [pfad for zeitpunkt, pfad in vorhanden
		               if aufbewahrung.ist_vollstaendig(pfad)]
		neueste = erfolgreich[-1].name if erfolgreich else None
		if geprueft == neueste:
			throw(
				"Die neueste Sicherung lässt sich nicht löschen. Bitte zuerst "
				"eine neue Sicherung anlegen.",
				ValidationError,
			)
		if zeile is None and not verzeichnis.exists():
			throw("Diese Sicherung gibt es nicht.", DoesNotExistError)
		if verzeichnis.exists():
			if not aufbewahrung.entferne(verzeichnis):
				throw("Die Sicherung konnte nicht gelöscht werden.", FrappeCompatError)
		if zeile is not None:
			sess.delete(zeile)
			sess.commit()
		return {"geloescht": True, "name": geprueft}
	finally:
		sess.close()


def _jetzt() -> datetime:  # pragma: no cover — nur fuer Lesbarkeit der Tests
	return datetime.now()
