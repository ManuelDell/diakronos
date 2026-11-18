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

Bei Nextcloud-Betrieb (SPEICHER-2) kommt die Liste aus dem Sicherungsordner
der Nextcloud und das Loeschen wirkt dort; genannt wird dann ``ort:
"nextcloud"`` — die ART des Ortes, nie eine Adresse oder ein Ordnerpfad.

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
from diakronos_app.models.sicherung import STATUS_FEHLGESCHLAGEN, Sicherungslauf
from diakronos_app.sicherung import aufbewahrung, cloud, dump, einstellungen as einstellungen_modul
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
		# SPEICHER-2: nur bei Nextcloud-Betrieb ist der Ort etwas anderes als
		# „lokal“. Im Lokal-Modus bleibt die Antwort exakt wie vorher.
		eintrag = {
			"name": zeile.name,
			"zeitpunkt": zeile.begonnen_am.isoformat() if zeile.begonnen_am else "",
			"groesse_bytes": int(zeile.groesse_bytes or 0),
			"status": zeile.status,
			"ausloeser": zeile.ausloeser,
			"meldung": zeile.meldung or "",
		}
		if cloud.ist_aktiv():
			eintrag["ort"] = "nextcloud"
		ergebnis.append(eintrag)
	return ergebnis


def _laeufe_aus_der_nextcloud(sess) -> list[dict]:
	"""Die Sicherungen so, wie sie in der Nextcloud liegen — PLUS die Fehlschlaege.

	Quelle ist der Ordner ``sicherungen`` — dort steht, was tatsaechlich
	vorhanden ist. Eine Zeile ohne Datei wuerde sonst als vorhandene Sicherung
	angezeigt, die es nicht gibt.

	**Fehlgeschlagene Laeufe kommen aus der Protokolltabelle dazu**
	(Review-Befund 4): ein Lauf, dessen Upload gescheitert ist, hat in der
	Nextcloud keinen (vollstaendigen) Ordner — er waere in der Liste sonst
	unsichtbar, obwohl in der Oberflaeche genau dort steht, warum die
	Sicherung nicht dort liegt. Gezeigt wird dann die Zeile mit Status und
	Meldung, ``ort`` bleibt ``nextcloud`` (die ART des Ablageorts, nie eine
	Adresse).

	Ist der Nextcloud-Ordner selbst nicht lesbar, wird der Fehler
	**hochgereicht** — die Oberflaeche meldet dann „nicht erreichbar“ statt
	„keine Sicherungen“.
	"""
	vorhanden = cloud.sicherungen_auflisten()
	namen = [eintrag[0] for eintrag in vorhanden]
	zeilen = {zeile.name: zeile for zeile in sess.scalars(
		select(Sicherungslauf).where(Sicherungslauf.name.in_(namen))
	)} if namen else {}
	ergebnis = []
	# SPEICHER-2b, Punkt 1: JEDER Name genau EINMAL. Frueher konnte ein
	# fehlgeschlagener Lauf mit Teilordner zweimal in der Liste stehen — die
	# Ordnerschleife zeigte ihn (aus der Nextcloud), die Fehlerzeilen-Schleife
	# uebersprang nur ``vollstaendig`` und haengte ihn noch einmal an.
	# Deshalb: was oben schon steht, wird nicht wiederholt; die Fehlerzeile
	# GEWINNT (sie kennt Status und Grund), der Ordner liefert nur Groesse und
	# die Tatsache, dass dort ein Rest liegt.
	gesehen: set[str] = set()
	for name, groesse, zeitpunkt, voll in vorhanden:
		gesehen.add(name)
		zeile = zeilen.get(name)
		ergebnis.append({
			"name": name,
			"zeitpunkt": zeitpunkt,
			"groesse_bytes": int(groesse or 0),
			"status": zeile.status if zeile is not None else "ok",
			"ausloeser": zeile.ausloeser if zeile is not None else "",
			"meldung": (zeile.meldung or "") if zeile is not None else "",
			"ort": "nextcloud",
			"vollstaendig": bool(voll),
		})
	# Fehlgeschlagene Laeufe, die es in der Nextcloud nicht (vollstaendig)
	# gibt: sie gehoeren in die Liste, sonst sieht niemand den Grund.
	fehlgeschlagen = sess.scalars(
		select(Sicherungslauf)
		.where(Sicherungslauf.status == STATUS_FEHLGESCHLAGEN)
		.order_by(Sicherungslauf.begonnen_am.desc())
		.limit(MAX_LAEUFE)
	)
	for zeile in fehlgeschlagen:
		if zeile.name in gesehen:
			# Entweder eine VOLLSTAENDIGE Sicherung (die Zeile steht schon
			# oben und traegt bereits Status und Meldung) — oder ein
			# Teilordner, dessen Zeile oben ohne Grund stand. Im letzteren
			# Fall gewinnt die Fehlerzeile: derselbe Name, aber mit Status,
			# Zeitpunkt und Meldung des Protokolls.
			_ersetze_zeile(ergebnis, zeile)
			continue
		gesehen.add(zeile.name)
		ergebnis.append({
			"name": zeile.name,
			"zeitpunkt": zeile.begonnen_am.isoformat() if zeile.begonnen_am else "",
			"groesse_bytes": int(zeile.groesse_bytes or 0),
			"status": zeile.status,
			"ausloeser": zeile.ausloeser,
			"meldung": zeile.meldung or "",
			"ort": "nextcloud",
			"vollstaendig": False,
		})
	ergebnis.sort(key=lambda eintrag: eintrag["zeitpunkt"], reverse=True)
	return ergebnis[:MAX_LAEUFE]


def _ersetze_zeile(ergebnis: list[dict], zeile) -> None:
	"""Die Zeile zum selben Namen durch die PROTOKOLLZEILE ersetzen.

	Nur wenn oben ein unvollstaendiger Rest stand (``vollstaendig: False``):
	ein vollstaendiger Ordner bleibt, wie er ist — Status und Meldung stehen
	dort schon aus derselben Protokollzeile, und „vollstaendig“ waere sonst
	falsch. ``groesse_bytes``/``zeitpunkt`` kommen aus dem Ordner, weil dort
	steht, was WIRKLICH liegt.
	"""
	for eintrag in ergebnis:
		if eintrag["name"] != zeile.name:
			continue
		if eintrag["vollstaendig"]:
			return
		eintrag["status"] = zeile.status
		eintrag["ausloeser"] = zeile.ausloeser
		eintrag["meldung"] = zeile.meldung or ""
		if zeile.begonnen_am is not None and not eintrag["zeitpunkt"]:
			eintrag["zeitpunkt"] = zeile.begonnen_am.isoformat()
		if not eintrag["groesse_bytes"]:
			eintrag["groesse_bytes"] = int(zeile.groesse_bytes or 0)
		return


@whitelist(allow_guest=False)
def sicherung_get() -> dict:
	"""Einstellungen, Liste der Sicherungen und Zustand des Ablageorts."""
	_angemeldeter_system_manager()
	sess = db.SessionLocal()
	try:
		zeile = einstellungen_modul.holen_oder_anlegen(sess)
		# SPEICHER-2: liegt die Sicherung in der Nextcloud, kommt die Liste von
		# DORT (Name, Groesse, Zeitpunkt) — im Lokal-Modus unveraendert aus der
		# Protokolltabelle.
		aktiv = cloud.ist_aktiv()
		fehler = ""
		if aktiv:
			try:
				sicherungen = _laeufe_aus_der_nextcloud(sess)
			except Exception as problem:  # noqa: BLE001 — Anzeige, kein Absturz
				# Review-Befund 4: nicht erreichbar ist NICHT „keine
				# Sicherungen“. Die Liste bleibt leer, aber der Hinweis sagt,
				# was los ist — und die Protokollzeilen sind trotzdem da.
				logger.warning("Sicherungen in der Nextcloud nicht lesbar: %s", problem)
				sicherungen = _laeufe(sess)
				fehler = (
					"Die Sicherungen in der Nextcloud konnten nicht gelesen "
					"werden — die Nextcloud ist nicht erreichbar. Gezeigt "
					"werden die protokollierten Läufe."
				)
		else:
			sicherungen = _laeufe(sess)
		ablage = lauf_modul.status_fuer_oberflaeche(sess)
		if fehler:
			ablage = {**ablage, "benutzbar": False, "hinweis_ort": fehler}
		return {
			"einstellungen": einstellungen_modul.als_dict(zeile),
			"sicherungen": sicherungen,
			"ablage": ablage,
			"maximum_aufbewahrung_tage": 3650,
		}
	finally:
		sess.close()


@whitelist(methods=["POST"], allow_guest=False)
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


@whitelist(methods=["POST"], allow_guest=False)
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


@whitelist(methods=["POST"], allow_guest=False)
def sicherung_loeschen(name: str | None = None) -> dict:
	"""Eine einzelne Sicherung loeschen (mit Bestaetigungsdialog in der UI).

	Die NEUESTE erfolgreiche Sicherung ist auch hier geschuetzt — derselbe
	Grund wie bei der Aufbewahrung: ein Fehlgriff im Dialog darf nicht die
	letzte Kopie kosten. Wer sie wirklich weghaben will, sichert vorher neu.

	SPEICHER-2: liegt die Sicherung in der Nextcloud, wird DORT geloescht (und
	die lokale Kopie mit, falls es noch eine gibt — sie ist sonst ein Rest, den
	niemand mehr sieht).
	"""
	_angemeldeter_system_manager()
	geprueft = _sicherungsname(name)
	sess = db.SessionLocal()
	try:
		zeile = sess.get(Sicherungslauf, geprueft)
		if cloud.ist_aktiv():
			return _loeschen_in_der_nextcloud(sess, zeile, geprueft)
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


def _loeschen_in_der_nextcloud(sess, zeile, name: str) -> dict:
	"""Loeschen bei Nextcloud-Betrieb: dort, und (falls vorhanden) lokal.

	Die Schranke „die neueste Sicherung nicht“ gilt hier genauso, nur mit der
	Nextcloud als Massstab — und **nur ueber VOLLSTAENDIGE Sicherungen**
	(Review-Befund 5): ein Ordner aus einem abgebrochenen Upload ist keine
	Sicherung, er darf weder die letzte echte Kopie schuetzen noch als
	„neueste“ gelten. Geloescht wird in der Nextcloud zuerst: lokal ist die
	juengste Kopie ohnehin da, ein halber Loeschvorgang ist also
	wiederholbar.

	**SPEICHER-2b, Punkt 4 — die lokale Kopie wird API-seitig geschuetzt:**
	liegt in der Nextcloud KEINE vollstaendige Sicherung, ist die lokale Kopie
	die einzige, die es gibt. Dann wird abgelehnt (nicht nur in der
	Oberflaeche ausgegraut): ein Aufruf mit ``name`` direkt am Endpunkt duerfte
	die letzte Sicherung nicht kosten. Die Meldung nennt den Weg heraus —
	erst neu sichern, dann loeschen.
	"""
	vorhanden = cloud.sicherungen_auflisten()
	namen = [eintrag[0] for eintrag in vorhanden]
	vollstaendig = [eintrag[0] for eintrag in vorhanden if eintrag[3]]
	lokal = dump.ziel_basis() / name
	lokal_da = lokal.is_dir()
	if not vollstaendig and lokal_da:
		throw(
			"Die einzige Kopie dieser Sicherung liegt auf diesem Server — "
			"in der Nextcloud ist keine vollständige Sicherung vorhanden. "
			"Bitte zuerst eine neue Sicherung in der Nextcloud ablegen.",
			ValidationError,
		)
	if not namen and zeile is None and not lokal_da:
		throw("Diese Sicherung gibt es nicht.", DoesNotExistError)
	# Die einzige (bzw. neueste) VOLLSTAENDIGE Kopie bleibt — auch dann, wenn
	# daneben nur unvollstaendige Reste liegen.
	if name in vollstaendig and name == vollstaendig[-1]:
		throw(
			"Die neueste Sicherung lässt sich nicht löschen. Bitte zuerst "
			"eine neue Sicherung anlegen.",
			ValidationError,
		)
	if name in namen and not cloud.loeschen(name):
		throw("Die Sicherung konnte nicht gelöscht werden.", FrappeCompatError)
	# Die lokale Kopie ist danach ein Rest ohne Bedeutung (die Liste kommt aus
	# der Nextcloud) — deshalb mit entfernen. Sie ist hier NICHT die einzige:
	# liegt in der Nextcloud keine vollstaendige Sicherung, wurde oben
	# abgelehnt; liegt dort eine, ist die lokale Kopie ersetzbar.
	if lokal_da and vollstaendig and not aufbewahrung.entferne(lokal):
		logger.warning("Lokale Kopie von %s blieb liegen.", name)
	if zeile is not None:
		sess.delete(zeile)
		sess.commit()
	return {"geloescht": True, "name": name}


def _jetzt() -> datetime:  # pragma: no cover — nur fuer Lesbarkeit der Tests
	"""Jetzt in Ortszeit (ZEIT-3) — ``sicherung/dump.py:jetzt_ortszeit``."""
	return dump.jetzt_ortszeit()
