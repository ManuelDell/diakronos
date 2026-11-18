"""BACKUP-1: EIN Sicherungslauf, von Anfang bis Ende.

DER ABLAUF
----------
1. Sperre setzen (Redis; zwei gleichzeitige Laeufe sind der Fehler, den die
   Karte ausschliesst). Geht nicht → ``SperreBesteht`` / ``SperreNichtVerfuegbar``.
2. Zeile in ``sicherungslauf`` mit Status ``laeuft`` — ab jetzt ist der Lauf
   auch nach einem Neustart sichtbar. Was noch ``laeuft`` ist, gehoert zu einem
   toten Prozess und wird zuerst als ``fehlgeschlagen`` gemeldet.
3. Dump + Dateiarchiv + Pruefsummen schreiben (``sicherung/dump.py``).
4. Ergebnis in die Zeile (Status, Groesse, Meldung).
5. Aufbewahrung anwenden: aeltere Sicherungen loeschen, die neueste
   erfolgreiche nie.
6. Bei Fehlschlag: In-App-Benachrichtigung an alle System Manager.

WARUM DER FEHLSCHLAG NICHT DURCHGEWORFEN WIRD
---------------------------------------------
Der Scheduler darf an einer fehlgeschlagenen Sicherung nicht sterben, und der
Knopf in der Oberflaeche soll eine Meldung zeigen statt eines Serverfehlers.
``fuehre_aus`` liefert deshalb das Ergebnis (``Sicherungsergebnis``) zurueck —
wer den Fehler als Ausnahme braucht, fragt ``fehler`` ab.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

from diakronos_app import benachrichtigungen
from diakronos_app.models.core import HasRole, User
from diakronos_app.models.sicherung import (
	STATUS_FEHLGESCHLAGEN,
	STATUS_LAEUFT,
	STATUS_OK,
	Sicherungslauf,
)
from diakronos_app.settings import settings
from diakronos_app.sicherung import aufbewahrung, cloud, dump
from diakronos_app.sicherung.einstellungen import holen_oder_anlegen, jetzt_ortszeit
from diakronos_app.sicherung.sperre import (
	Sicherungssperre,
	SperreBesteht,
	SperreNichtVerfuegbar,
	raeume_abgebrochene_auf,
)

logger = logging.getLogger("diakronos_app.sicherung.lauf")

#: Traegt den Ergebnistyp von ``_mit_herzschlag`` (Upload-Ergebnis).
_T = TypeVar("_T")

#: Wie ein Lauf gestartet wurde.
AUSLOESER_AUTOMATISCH = "automatisch"
AUSLOESER_MANUELL = "manuell"


# ── N6 (BACKUP-1c): hoechstens EINE Meldung je Tag und Ursache ──────────────
#
# Der Minuten-Job versucht es bei jedem Tick erneut (N3, Absicht — der Tag
# bleibt offen, bis wirklich gesichert ist). Die MELDUNG darf dabei nicht
# mitwachsen: bei belegter Sperre oder Redis-Ausfall standen so bis zu 30
# Meldungen je System Manager im Postfach.
#
# Der Merker liegt deshalb NICHT in Redis (der Ausfall, den er drosselt, kann
# genau Redis treffen) und NICHT im Prozess (ein Neustart des Schedulers
# wuerde die Flut wieder freigeben), sondern als Datei im Sicherungsordner —
# derselbe Bind-Mount wie die Sicherungen, also ueber Neustarts hinweg da.
# Vorbild ist die ``FERTIG``-Markierung in ``dump.py``.
#
# Die Datei traegt nur Datum und Ursache, keine Personendaten. Sie wird beim
# Aufraeumen nicht erfasst (die Aufbewahrung nimmt nur ``JJJJ-MM-TT_HHMMSS``).
MELDUNG_PRAEFIX = "MELDUNG_gesendet"

#: Die beiden Ursachen aus dem Kartenpunkt N6.
URSACHE_SPERRE = "sperre"
URSACHE_REDIS = "redis"


def _meldung_verzeichnis() -> Path:
	"""Wo der Drossel-Merker liegt: das Sicherungsverzeichnis."""
	return Path(settings.backup_dir)


def _meldung_marker(ursache: str, zeit: datetime) -> Path:
	return _meldung_verzeichnis() / f"{MELDUNG_PRAEFIX}_{ursache}_{zeit:%Y-%m-%d}"


def heute_schon_gemeldet(ursache: str, zeit: datetime) -> bool:
	"""Wurde fuer ``ursache`` heute (Ortszeit-Datum) schon gemeldet?"""
	try:
		return _meldung_marker(ursache, zeit).is_file()
	except OSError as fehler:  # noqa: BLE001 — Drossel ist Beiwerk
		logger.warning("Drossel-Merker nicht lesbar: %s", fehler)
		return False


def _merke_meldung(ursache: str, zeit: datetime) -> None:
	"""Merker setzen. Scheitert das Schreiben, wird NICHT doppelt gemeldet."""
	marker = _meldung_marker(ursache, zeit)
	try:
		marker.parent.mkdir(parents=True, exist_ok=True)
		marker.write_text("", encoding="utf-8")
	except OSError as fehler:  # noqa: BLE001
		logger.warning("Drossel-Merker nicht setzbar: %s", fehler)


def melde_einmal_je_tag(ursache: str, *, zeit: datetime, subject: str,
                        inhalt: str) -> bool:
	"""Meldet ``ursache`` heute zum ersten Mal — sonst still.

	Der Merker wird VOR dem Versand gesetzt: schlaegt die Zustellung fehl, ist
	die Meldung fuer heute verloren, aber es entsteht keine Flut. Das ist die
	richtige Reihenfolge — die Wiederholung bringt keine neue Information,
	der Ausfall steht ohnehin im Log und in der Oberflaeche.
	"""
	if heute_schon_gemeldet(ursache, zeit):
		logger.info(
			"Meldung „%s“ heute schon gesendet — keine Wiederholung.", subject,
		)
		return False
	_merke_meldung(ursache, zeit)
	benachrichtige_system_manager(subject, inhalt)
	return True


@dataclass
class Sicherungsergebnis:
	"""Ergebnis eines Laufs — genug fuer Oberflaeche, Scheduler und Log."""

	name: str = ""
	status: str = STATUS_LAEUFT
	meldung: str = ""
	groesse_bytes: int = 0
	entfernt: list[str] = field(default_factory=list)
	zeitpunkt: datetime | None = None

	@property
	def ok(self) -> bool:
		return self.status == STATUS_OK

	@property
	def fehler(self) -> str:
		return "" if self.ok else (self.meldung or "Die Sicherung ist fehlgeschlagen.")


def system_manager(sitzung: Session | None = None) -> list[str]:
	"""Alle aktiven Konten mit der Rolle System Manager (fail safe leer).

	``sitzung`` ist die Sitzung des Aufrufers (Tests, Request); fehlt sie,
	wird eine eigene geoeffnet und wieder geschlossen.
	"""
	eigene = sitzung is None
	if sitzung is None:
		from diakronos_app.db import SessionLocal

		sitzung = SessionLocal()
	try:
		return list(sitzung.scalars(
			select(HasRole.parent)
			.join(User, User.name == HasRole.parent)
			.where(HasRole.role == "System Manager", User.enabled.is_(True))
			.distinct()
		))
	finally:
		if eigene:
			sitzung.close()


def benachrichtige_system_manager(subject: str, inhalt: str,
                                  sitzung: Session | None = None) -> list[str]:
	"""In-App-Benachrichtigung an alle System Manager. Rueckgabe: Empfaenger."""
	empfaenger = system_manager(sitzung)
	zugestellt: list[str] = []
	for konto in empfaenger:
		if benachrichtigungen.schreibe_meldung(
			for_user=konto, subject=subject, inhalt=inhalt,
			document_type="Sicherungslauf", typ="Alert",
		):
			zugestellt.append(konto)
	if not zugestellt:
		logger.warning("Kein System Manager fuer die Meldung %r erreichbar.", subject)
	return zugestellt


def _setze_status(session: Session, name: str, *, status: str, meldung: str,
                  groesse: int | None, beendet: datetime,
                  benachrichtigt: str | None = None) -> None:
	zeile = session.get(Sicherungslauf, name)
	if zeile is None:
		return
	zeile.status = status
	zeile.meldung = meldung or None
	zeile.groesse_bytes = groesse
	zeile.beendet_am = beendet
	if benachrichtigt is not None:
		zeile.benachrichtigt = benachrichtigt
	session.commit()


def _sperr_dauer(settings, *, verzeichnis: Path | None = None) -> int:
	"""Wie lange die Sperre gilt: Dump/Archiv PLUS Uebertragung.

	Review-Befund 6: ``backup_timeout + 300`` deckte nur den lokalen Teil ab.
	Ein Lauf, der nach dem Dump noch 2 GB in die Nextcloud schiebt (Upload,
	Groessen-/Pruefsummen-Gegenprobe, Aufbewahrung dort), lief laenger als die
	Sperre — sie fiel waehrend des Laufs ab, und ein zweiter Lauf haette
	parallel einen Dump geschrieben.

	Rechnung: der lokale Teil darf ``backup_timeout`` dauern. Die Uebertragung
	braucht bei realistischen Leitungen (10 Mbit/s aufwaerts) fuer die
	Groesse der letzten Sicherung ``groesse_und_bereich`` Zeit. Beides plus
	ein Aufschlag von 5 Minuten fuer Gegenprobe und Aufbewahrung; mindestens
	das alte Verhalten (Timeout + 300).
	"""
	lokal = int(getattr(settings, "backup_timeout_sekunden", None) or 1800)
	#: Untergrenze der Uebertragungszeit: 10 Mbit/s aufwaerts.
	ANNAHME_BYTES_PRO_SEKUNDE = 1_250_000
	#: Reine Rechenzeit fuer Upload-Aufrufe, Gegenprobe, Aufraeumen.
	ZUSCHLAG_SEKUNDEN = 300
	uebertragung = 0.0
	try:
		basis = Path(verzeichnis) if verzeichnis is not None else dump.ziel_basis()
		letzte = aufbewahrung.sicherungen_im_verzeichnis(basis)
		if letzte:
			# Die Groesse ist der beste Schaetzwert fuer den naechsten Upload.
			groesse = dump.verzeichnisgroesse(letzte[-1][1])
			uebertragung = groesse / ANNAHME_BYTES_PRO_SEKUNDE
	except Exception as fehler:  # noqa: BLE001 — Schaetzung darf nie den Lauf stoppen
		logger.warning("Groesse der letzten Sicherung nicht ermittelbar: %s", fehler)
	return max(lokal + ZUSCHLAG_SEKUNDEN, lokal + int(uebertragung) + ZUSCHLAG_SEKUNDEN)


#: Wie oft die Sperre waehrend Upload und Gegenprobe verlaengert wird. Die TTL
#: aus ``_sperr_dauer`` ist eine Schaetzung; dieser Herzschlag macht sie
#: unempfindlich gegen eine langsamere Leitung oder eine groessere Sicherung
#: als die letzte (SPEICHER-2b, Punkt 3).
HERZSCHLAG_SEKUNDEN = 60.0


def _mit_herzschlag(sperre, arbeit: Callable[[], _T],
                    *, takt: float | None = None) -> _T:
	"""``arbeit()`` ausfuehren und dabei die Sperre regelmaessig verlaengern.

	Der Upload und die Gegenprobe (Groesse, Pruefsumme) koennen beliebig lange
	dauern — die Sperre deckt beide nur mit einer Schaetzung ab. Statt die
	Verlaengerung in jede Blockgrenze zu haengen (die liegt in ``speicher/``,
	wo es keine Sperre gibt), laeuft hier ein eigener Faeden, der die Sperre
	jede ``takt`` Sekunde nachfasst und danach still aufhoert.

	Der Faeden ist ein ``daemon``: er haelt den Prozess nie am Leben, und er
	wird im ``finally`` gestoppt — auch wenn ``arbeit`` wirft. Scheitert das
	Verlaengern (Redis weg), wird das geloggt und es geht weiter: die Sicherung
	ist dann nicht mehr vor einem zweiten Lauf geschuetzt, aber ein
	abgebrochener Dump waere schlimmer.
	"""
	import threading

	dauer = max(0.01, float(takt if takt is not None else HERZSCHLAG_SEKUNDEN))
	fertig = threading.Event()

	def _klopfen() -> None:
		# Warten zuerst: die Sperre ist gerade gesetzt, ein sofortiges
		# Verlaengern waere nur ein zweiter Aufruf ohne Nutzen.
		while not fertig.wait(dauer):
			if sperre is None or not hasattr(sperre, "verlaengern"):
				return
			try:
				if not sperre.verlaengern():
					logger.warning(
						"Die Sperre der Datensicherung ist waehrend des Laufs "
						"abgelaufen oder wurde fremd gesetzt."
					)
					return
			except Exception as fehler:  # noqa: BLE001 — Sperre ist Beiwerk
				logger.warning("Sicherungssperre nicht verlaengert: %s", fehler)
				return

	faeden = None
	if sperre is not None and hasattr(sperre, "verlaengern"):
		faeden = threading.Thread(target=_klopfen, name="sicherung-herzschlag",
		                          daemon=True)
		faeden.start()
	try:
		return arbeit()
	finally:
		fertig.set()
		if faeden is not None:
			faeden.join(timeout=1.0)


def _freie_kennung(session: Session, zeit: datetime) -> str:
	"""Kennung, die es weder als Zeile noch als Verzeichnis gibt (N4).

	Zwei Laeufe in derselben Sekunde sind durch die Sperre ausgeschlossen —
	aber ein Verzeichnis aus einem frueheren Lauf kann stehenbleiben, waehrend
	seine Protokollzeile weg ist (oder umgekehrt). Dann kollidiert der Name
	entweder im Primaerschluessel (IntegrityError → 500 bei „Jetzt sichern“)
	oder im Dateisystem. Der Name bekommt deshalb keinen Zusatz — er muss im
	Muster ``JJJJ-MM-TT_HHMMSS`` bleiben, sonst erfasst die Aufbewahrung ihn
	nicht mehr. Stattdessen rueckt die Uhr um so viele Sekunden vor, bis
	Zeilen- und Ordnerplatz frei sind.
	"""
	basis = dump.ziel_basis()
	for versatz in range(0, 120):
		kennung = dump.neue_kennung(zeit + timedelta(seconds=versatz))
		besetzt = session.get(Sicherungslauf, kennung) is not None
		if not besetzt and not (basis / kennung).exists():
			if versatz:
				logger.info(
					"Kennung %s war belegt — Lauf heisst %s.",
					dump.neue_kennung(zeit), kennung,
				)
			return kennung
	raise dump.SicherungFehler(
		"Fuer diese Sekunde gibt es keine freie Kennung fuer die Sicherung."
	)


def fuehre_aus(
	*,
	ausloeser: str = AUSLOESER_MANUELL,
	jetzt: datetime | None = None,
	sitzung: Session | None = None,
	timeout: int | None = None,
	aufraeumen: bool = True,
	sperre_gesetzt: Callable[[], None] | None = None,
) -> Sicherungsergebnis:
	"""Einen Sicherungslauf durchfuehren (siehe Modulkopf).

	``sitzung`` ist die Sitzung des Aufrufers (Request). Fehlt sie, oeffnet
	der Lauf eine eigene — der Scheduler hat keine.

	``sperre_gesetzt`` wird aufgerufen, sobald die Sperre steht und bevor der
	erste Dump-Bytes geschrieben wird. Der Scheduler setzt dort seinen
	Tagesmerker (N3): scheitert der Lauf vorher an Sperre oder Redis, bleibt
	der Tag offen und der naechste Tick versucht es erneut.
	"""
	from diakronos_app.db import SessionLocal

	zeit = jetzt or jetzt_ortszeit()
	eigene = sitzung is None
	session = sitzung if sitzung is not None else SessionLocal()
	try:
		einstellungen = holen_oder_anlegen(session, jetzt=zeit)
		tage = int(einstellungen.aufbewahrung_tage)

		ttl = _sperr_dauer(settings, verzeichnis=None)
		try:
			sperre = Sicherungssperre(ttl_sekunden=ttl)
			sperre.setzen()
		except SperreBesteht as belegt:
			# N3: bei einem AUTOMATISCHEN Lauf ist das ein Ausfall, den
			# niemand von Hand mitbekommt — die System Manager erfahren es.
			# N6: hoechstens einmal je Tag (sonst 30 Meldungen am Tag).
			if ausloeser == AUSLOESER_AUTOMATISCH:
				melde_einmal_je_tag(
					URSACHE_SPERRE, zeit=zeit,
					subject="Datensicherung nicht gelaufen",
					inhalt=(
						"Die automatische Datensicherung konnte nicht starten: "
						f"{belegt}\n\nEs wurde nichts gesichert. Der naechste Versuch "
						"laeuft, sobald keine Sicherung mehr laeuft."
					),
				)
			return Sicherungsergebnis(
				status=STATUS_FEHLGESCHLAGEN,
				meldung=str(belegt),
				zeitpunkt=zeit,
			)
		except SperreNichtVerfuegbar as fehler:
			# Fail closed: ohne Sperre wird nicht gesichert.
			if ausloeser == AUSLOESER_AUTOMATISCH:
				melde_einmal_je_tag(
					URSACHE_REDIS, zeit=zeit,
					subject="Datensicherung nicht gelaufen",
					inhalt=(
						"Die automatische Datensicherung konnte nicht starten: "
						f"{fehler}\n\nEs wurde nichts gesichert. Der naechste Versuch "
						"laeuft bei der naechsten Pruefung."
					),
				)
			return Sicherungsergebnis(
				status=STATUS_FEHLGESCHLAGEN, meldung=str(fehler), zeitpunkt=zeit,
			)

		try:
			if sperre_gesetzt is not None:
				sperre_gesetzt()
			# Abgebrochene Vorgaenger melden, BEVOR der neue Lauf beginnt.
			abgebrochen = raeume_abgebrochene_auf(session, jetzt=zeit)

			name = _freie_kennung(session, zeit)
			session.add(Sicherungslauf(
				name=name, begonnen_am=zeit, status=STATUS_LAEUFT,
				ausloeser=ausloeser,
			))
			session.commit()

			try:
				verzeichnis = dump.sichere(
					jetzt=zeit, name=name,
					timeout=timeout or settings.backup_timeout_sekunden or None,
				)
			except Exception as fehler:  # noqa: BLE001 — jeder Fehler ist ein Ergebnis
				logger.exception("Sicherung %s fehlgeschlagen", name)
				meldung = str(fehler) or f"Die Sicherung ist fehlgeschlagen ({type(fehler).__name__})."
				_setze_status(session, name, status=STATUS_FEHLGESCHLAGEN,
				              meldung=meldung, groesse=None, beendet=jetzt_ortszeit())
				zugestellt = benachrichtige_system_manager(
					"Datensicherung fehlgeschlagen",
					"Die automatische Datensicherung vom "
					f"{zeit.strftime('%d.%m.%Y %H:%M')} ist fehlgeschlagen:\n\n{meldung}\n\n"
					"Bitte in „Einstellungen → Datensicherung“ nachsehen und die "
					"Sicherung von Hand anstossen.",
				)
				if zugestellt:
					zeile = session.get(Sicherungslauf, name)
					if zeile is not None:
						zeile.benachrichtigt = ", ".join(zugestellt)
						session.commit()
				return Sicherungsergebnis(
					name=name, status=STATUS_FEHLGESCHLAGEN, meldung=meldung,
					zeitpunkt=zeit,
				)

			groesse = dump.verzeichnisgroesse(verzeichnis)
			# SPEICHER-2b, Punkt 3: Upload UND Gegenprobe (Groesse,
			# Pruefsumme je Datei) koennen die geschaetzte TTL ueberschreiten.
			# Hier wird die Sperre deshalb regelmaessig nachgefasst; der
			# Aufraeumteil darunter laeuft ebenfalls unter der Sperre, ist aber
			# kurz (nur WebDAV-DELETEs).
			hochgeladen = _mit_herzschlag(sperre, lambda: cloud.hochladen(verzeichnis))
			if hochgeladen.fehlgeschlagen:
				# SPEICHER-2: die Sicherung liegt nur lokal. Das ist ein
				# TEILERFOLG, kein Erfolg — die Oberflaeche muss es zeigen
				# (BACKUP-1-Status) und die System Manager erfahren es. Die
				# lokale Kopie bleibt ausdruecklich stehen (Review-Befund 7:
				# hier wird NICHTS lokal geloescht, auch keine aeltere Kopie —
				# sie koennte die letzte in der Nextcloud fehlende sein, und
				# ``nur_neueste_lokal_behalten`` prueft das selbst).
				teil_meldung = hochgeladen.meldung + (
					" " + "; ".join(hochgeladen.fehler[:3])
					if hochgeladen.fehler else ""
				)
				logger.warning("Sicherung %s nur lokal: %s", name, teil_meldung)
				_setze_status(session, name, status=STATUS_FEHLGESCHLAGEN,
				              meldung=teil_meldung, groesse=groesse,
				              beendet=jetzt_ortszeit())
				zugestellt = benachrichtige_system_manager(
					"Datensicherung nicht in der Nextcloud",
					"Die Datensicherung vom "
					f"{zeit.strftime('%d.%m.%Y %H:%M')} wurde erstellt, konnte "
					f"aber nicht vollstaendig in die Nextcloud uebertragen "
					f"werden:\n\n{teil_meldung}\n\nDie Kopie liegt weiterhin "
					"lokal. Bitte in „Einstellungen → Datensicherung“ nachsehen "
					"und die Uebertragung mit einem neuen Lauf wiederholen.",
				)
				if zugestellt:
					zeile = session.get(Sicherungslauf, name)
					if zeile is not None:
						zeile.benachrichtigt = ", ".join(zugestellt)
						session.commit()
				return Sicherungsergebnis(
					name=name, status=STATUS_FEHLGESCHLAGEN,
					meldung=teil_meldung, groesse_bytes=groesse,
					zeitpunkt=zeit,
				)

			meldung = "Sicherung vollstaendig."
			if hochgeladen.aktiv:
				meldung = "Sicherung vollstaendig (in der Nextcloud abgelegt)."
			_setze_status(session, name, status=STATUS_OK,
			              meldung=meldung, groesse=groesse,
			              beendet=jetzt_ortszeit())

			entfernt: list[str] = []
			if hochgeladen.aktiv:
				# Aufbewahrung gilt jetzt fuer die NEXTCLOUD-Seite; lokal bleibt
				# nur die juengste Kopie (schnelle Wiederherstellung).
				try:
					# SPEICHER-2: die lokalen Reste (``.tmp-*`` abgestuerzter Laeufe)
					# raeumt AUCH der Nextcloud-Betrieb auf — sonst blieben Teil-Dumps
					# mit Personendaten im lokalen Verzeichnis liegen, weil die
					# Sicherung selbst ja in der Nextcloud liegt.
					aufbewahrung.verwaiste_temp_entfernen(
						verzeichnis.parent, jetzt=zeit,
						timeout_sekunden=int(settings.backup_timeout_sekunden or 1800),
					)
					entfernt = cloud.aufraeumen(
						jetzt=zeit, aufbewahrung_tage=tage,
					)
				except Exception as fehler:  # noqa: BLE001 — Aufraeumen ist Beiwerk
					logger.warning("Aufbewahrung in der Nextcloud fehlgeschlagen: %s",
					               fehler)
				cloud.nur_neueste_lokal_behalten(verzeichnis.parent, behalten=name)
				for alt in entfernt:
					zeile = session.get(Sicherungslauf, alt)
					if zeile is not None:
						session.delete(zeile)
				if entfernt:
					session.commit()
			elif aufraeumen:
				erfolgreich = set(session.scalars(
					select(Sicherungslauf.name).where(Sicherungslauf.status == STATUS_OK)
				))
				entfernt = aufbewahrung.aufraeumen(
					verzeichnis.parent, jetzt=zeit, aufbewahrung_tage=tage,
					erfolgreich=erfolgreich,
					timeout_sekunden=int(settings.backup_timeout_sekunden or 1800),
				)
				for alt in entfernt:
					zeile = session.get(Sicherungslauf, alt)
					if zeile is not None:
						session.delete(zeile)
				# N1 (BACKUP-1b): ein FEHLGESCHLAGENER Lauf hat kein Verzeichnis,
				# wird von der Aufbewahrung oben also nie erfasst — seine Zeile
				# blieb fuer immer in der Liste stehen. Sie faellt nach derselben
				# Frist heraus; den Grund nennt das Log (die Zeile ist dann weg).
				grenze = zeit - timedelta(days=tage)
				alte_fehler = list(session.scalars(
					select(Sicherungslauf).where(
						Sicherungslauf.status != STATUS_OK,
						Sicherungslauf.begonnen_am < grenze,
					)
				))
				for zeile in alte_fehler:
					logger.info(
						"Alter fehlgeschlagener Lauf faellt aus der Liste: %s (%s)",
						zeile.name, zeile.meldung or zeile.status,
					)
					session.delete(zeile)
				if entfernt or alte_fehler:
					session.commit()
			# Abgebrochene Vorgaenger interessieren nur im Log: sie sind als
			# fehlgeschlagen sichtbar und wurden bereits gemeldet.
			if abgebrochen:
				logger.warning("Abgebrochene Sicherungslaeufe gemeldet: %s", abgebrochen)

			logger.info("Sicherung %s fertig (%s Bytes, %s alte entfernt).",
			            name, groesse, len(entfernt))
			return Sicherungsergebnis(
				name=name, status=STATUS_OK, meldung=meldung,
				groesse_bytes=groesse, entfernt=entfernt, zeitpunkt=zeit,
			)
		finally:
			sperre.freigeben()
	finally:
		if eigene:
			session.close()


def status_fuer_oberflaeche(session: Session, verzeichnis: Path | None = None) -> dict:
	"""Was die Oberflaeche ueber den Ablageort sagen darf (B4: kein Pfad).

	Nennt nur, OB ein Ablageort benutzbar ist und ob dort etwas liegt — nie
	den Pfad. Ein Pfad im Browser waere der erste Schritt zu einem
	Herunterladen, und genau das schliesst die Karte aus.
	"""
	basis = Path(verzeichnis or dump.ziel_basis())
	try:
		dump.pruefe_ziel(basis)
		benutzbar = True
		hinweis = ""
	except dump.SicherungFehler as fehler:
		benutzbar = False
		hinweis = str(fehler)
	anzahl = len(aufbewahrung.sicherungen_im_verzeichnis(basis)) if basis.is_dir() else 0
	# SPEICHER-2: liegt die Sicherung in der Nextcloud, nennt die Oberflaeche
	# den Ort (nur die ART, nie eine Adresse) und die dort vorhandene Anzahl.
	# Gezaehlt wird dort, wo die Liste herkommt — sonst widerspraechen sich
	# Liste und „vorhanden“.
	ort = "lokal"
	hinweis_cloud = ""
	if cloud.ist_aktiv():
		ort = "nextcloud"
		try:
			anzahl = len(cloud.sicherungen_auflisten())
		except Exception as fehler:  # noqa: BLE001 — Anzeige, kein Betriebszustand
			# Review-Befund 4: „nicht erreichbar“ ist NICHT „keine
			# Sicherungen“. Der Unterschied entscheidet, ob der Betrieb
			# ruhig schlaeft.
			logger.warning("Sicherungen in der Nextcloud nicht lesbar: %s", fehler)
			anzahl = 0
			if benutzbar:
				benutzbar = False
			# SPEICHER-2b, Punkt 6: ``benutzbar=False`` mit LEEREM ``hinweis``
			# ergab in der Oberflaeche einen leeren roten Kasten. Steht dort
			# schon ein Satz (Ziel unbrauchbar), bleibt er — es ist die
			# dringendere Meldung.
			if not hinweis:
				hinweis = (
					"Die Nextcloud ist gerade nicht erreichbar — Sicherungen "
					"werden lokal behalten. Die Liste zeigt die protokollierten "
					"Läufe, nicht was in der Nextcloud liegt."
				)
			hinweis_cloud = (
				"Die Sicherungen in der Nextcloud konnten nicht gelesen werden "
				"— die Nextcloud ist nicht erreichbar. Es ist NICHT gesagt, "
				"dass es keine Sicherung gibt."
			)
	return {
		"benutzbar": benutzbar,
		"hinweis": hinweis,
		"vorhanden": anzahl,
		"ort": ort,
		"hinweis_ort": hinweis_cloud,
	}
