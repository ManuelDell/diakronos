"""SPEICHER-2: Sicherungen liegen bei Nextcloud-Betrieb in der Nextcloud.

DIE ENTSCHEIDUNG (Manuel, 17.11.: „Ja das backup soll dann auch auf der
nextcloud liegen“)
--------------------------------------------------------------------------
Ist die Datei-Ablage auf ``nextcloud`` gestellt, gehoert die fertige Sicherung
dorthin — nicht (nur) auf das Volume des Containers. Sonst waere die
Datensicherung genau dann weg, wenn das Volume weg ist: dieselbe Maschine,
dieselbe Platte, derselbe Fehler.

DER WEG EINER SICHERUNG
-----------------------
1. ``dump.sichere`` schreibt das Verzeichnis ``JJJJ-MM-TT_HHMMSS`` **lokal**
   (``pg_dump`` braucht ein Dateisystem, und das Sperr-/Aufraeumverhalten von
   BACKUP-1 bleibt unveraendert).
2. :func:`hochladen` schiebt jede Datei ueber die EINE Ablage-Schnittstelle
   (``speicher/basis.py``) in den Ordner ``sicherungen/<name>`` der
   Gemeinde-Nextcloud — **blockweise** (``BLOCKGROESSE``), nie ganz in den
   Speicher. Danach wird die Groesse im Ziel gelesen und mit der Quelle
   verglichen; erst dann gilt die Sicherung als „auch in der Nextcloud“.
3. Nur die JUENGSTE Sicherung bleibt lokal liegen (schnelle Wiederherstellung).
   Aeltere lokale Kopien werden geloescht, sobald die Aufbewahrung durch ist.
4. Die Aufbewahrung (``aufbewahrung.py``) gilt fuer die **Nextcloud-Seite**:
   ``\u00fcberfristige`` Namen werden dort nach Alter entfernt.

WAS HIER BEWUSST NICHT PASSIERT
-------------------------------
* **Kein Loeschen des lokalen Laufs nach einem gescheiterten Upload.** Ein
  fehlgeschlagener Upload hinterlaesst die lokale Kopie — sonst waere die
  Sicherung genau dann weg, wenn sie gebraucht wird.
* **Keine zweite Ablage.** Es wird ausschliesslich ``hole_speicher()``
  benutzt; eine eigene WebDAV-Verbindung gibt es hier nicht (Kartenvorgabe:
  „ueber die EINE Ablage-Schnittstelle“).
* **Kein Pfad und keine Adresse nach aussen.** Die Oberflaeche nennt Namen,
  Groesse, Zeitpunkt — nie den Ort (Kartenvorgabe 4, wie BACKUP-1).
* **Kein Fehler nach oben durchgereicht.** ``lauf.fuehre_aus`` bekommt ein
  Ergebnis (:class:`Uploadergebnis`), damit der Scheduler nicht an einem
  Netzfehler stirbt und der Knopf in der Oberflaeche eine Meldung zeigt.

LOKAL-MODUS
-----------
Ist die Ablage ``lokal``, ist dieses Modul still: ``ist_aktiv()`` False,
``hochladen`` meldet „nicht aktiv, nichts zu tun“, ``sicherungen_auflisten``
und ``loeschen`` werden von ``api/sicherung.py`` gar nicht erst gefragt. Am
Verhalten von BACKUP-1 aendert sich damit nichts: die Sicherungen liegen
weiter unter ``<BACKUP_DIR>/JJJJ-MM-TT_HHMMSS`` — genau wie vorher.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from diakronos_app.sicherung import aufbewahrung, dump

logger = logging.getLogger("diakronos_app.sicherung.cloud")

__all__ = [
	"Uploadergebnis",
	"Ziel",
	"ist_aktiv",
	"hochladen",
	"sicherungen_auflisten",
	"ist_vollstaendig",
	"schluessel",
	"lokale_basis",
	"nur_neueste_lokal_behalten",
	"loeschen",
	"aufraeumen",
	"zeitpunkt_von_ziel",
]

#: Ordner im Bereich der Ablage (unter ``NEXTCLOUD_ORDNER``), in dem die
#: Sicherungen liegen. Eigener Ordner, damit die Aufbewahrung der Sicherungen
#: nie eine Nutzerdatei erwischt und umgekehrt.
ORDNER = "sicherungen"


# ── Zustand ────────────────────────────────────────────────────────────────

def _ablage():
	"""Die aktive Ablage (EINE Schnittstelle — hier wird keine zweite gebaut)."""
	from diakronos_app.speicher import hole_speicher

	return hole_speicher()


def ist_aktiv() -> bool:
	"""Liegen die Sicherungen in der Nextcloud (statt nur lokal)?"""
	try:
		return _ablage().name == "nextcloud"
	except Exception as fehler:  # noqa: BLE001 — eine kaputte Einstellung ist kein Backup
		# Eine unbrauchbare Einstellung darf den Lauf nicht verhindern: es wird
		# lokal gesichert wie bisher, und der Grund steht im Log. Besser eine
		# Sicherung am falschen Ort als keine.
		logger.warning("Ablage nicht bestimmbar — Sicherung bleibt lokal: %s", fehler)
		return False


def lokale_basis() -> Path:
	"""Das lokale Sicherungsverzeichnis — immer ``BACKUP_DIR``, in BEIDEN Modi.

	Review-Befund SPEICHER-2: hier stand im Lokal-Modus ein Unterordner
	``<BACKUP_DIR>/sicherungen``. Damit verschwanden alle bestehenden
	Sicherungen aus Aufbewahrung, Liste und Loeschen — eine stille
	Verhaltensaenderung an BACKUP-1, die niemand bestellt hat. Jetzt gilt:
	die lokale Ablage ist ``BACKUP_DIR``, unveraendert. Im Nextcloud-Betrieb
	ist derselbe Ort die Zwischenablage (``dump.sichere`` schreibt dorthin,
	hochgeladen und danach aufgeraeumt wird von hier) und der Ort, den
	``wiederherstellen`` fuellt.
	"""
	from diakronos_app.settings import settings

	return Path(settings.backup_dir)


def schluessel(name: str) -> str:
	"""Schluessel einer Sicherung in der Ablage: ``sicherungen/<name>``."""
	return f"{ORDNER}/{name}"


# ── Hochladen ──────────────────────────────────────────────────────────────

@dataclass
class Uploadergebnis:
	"""Was der Upload getan hat — genug fuer Statuszeile und Oberflaeche."""

	aktiv: bool = False
	"""False: die Ablage ist lokal, es gab nichts hochzuladen."""
	ok: bool = False
	dateien: int = 0
	bytes: int = 0
	meldung: str = ""
	fehler: list[str] = field(default_factory=list)

	@property
	def fehlgeschlagen(self) -> bool:
		return self.aktiv and not self.ok


def _dateien(verzeichnis: Path) -> list[Path]:
	"""Alle Dateien einer Sicherung, in stabiler Reihenfolge (``FERTIG`` zuletzt).

	Die Reihenfolge ist Absicht: die ``FERTIG``-Markierung wird als LETZTES
	hochgeladen. Bricht der Upload ab, liegt in der Nextcloud ein
	Sicherungsordner ohne ``FERTIG`` — und ``aufbewahrung.ist_vollstaendig``
	erkennt ihn dort als unvollstaendig (raus nach Frist, nie „neueste
	erfolgreiche“).
	"""
	if not verzeichnis.is_dir():
		return []
	dateien = sorted(datei for datei in verzeichnis.iterdir() if datei.is_file())
	dateien.sort(key=lambda datei: datei.name == dump.FERTIG_NAME)
	return dateien


def _laenge(pruefsummen: str) -> str:
	"""Erste Spalte der ``sha256sum``-Zeile (leer, wenn nicht lesbar)."""
	return pruefsummen.split()[0] if pruefsummen else ""


def _erwartete_summe(verzeichnis: Path, datei: Path) -> str:
	"""SHA-256 aus ``SHA256SUMS`` — sonst leer (dann wird frisch gerechnet)."""
	return dump.lese_pruefsummen(verzeichnis).get(datei.name, "")


def _fehlertext(datei: Path, problem: Exception) -> str:
	"""Kurzer Grund fuer die Oberflaeche — ohne Adresse, ohne Zugangsdaten.

	``AblageFehler`` traegt bereits einen Satz fuer Menschen („Die Nextcloud
	meldet keinen freien Speicher“). Andere Ausnahmen nennen nur ihren Typ:
	ein Stapelauszug oder eine WebDAV-Adresse gehoert nicht in die
	Sicherungsliste.
	"""
	from diakronos_app.speicher.basis import AblageFehler

	text = str(problem).strip() if isinstance(problem, AblageFehler) else ""
	return f"{datei.name}: {text or type(problem).__name__}"


def _hochladen_je_datei(ablage, verzeichnis: Path) -> list[str]:
	"""Alle Dateien der Sicherung hochladen. Rueckgabe: Fehlertexte.

	Je Datei:
	1. Groesse vergleichen (ist der Upload vollstaendig?) — die Zusage der
	   Karte: „Erfolg erst, wenn der Upload vollstaendig ist“.
	2. Pruefsumme im ZIEL nachrechnen und mit ``SHA256SUMS`` vergleichen. Ein
	   abgeschnittener oder unterwegs verfaelschter Dump ist damit erkannt;
	   die Groessenpruefung allein faengt genau diesen Fall nicht.

	**Beim ERSTEN Fehler ist Schluss** (Review-Befund 3): der frueherer
	``continue`` lud munter weiter — und am Ende auch noch die
	``FERTIG``-Markierung. Damit stand in der Nextcloud eine „vollstaendige“
	Sicherung, in der eine Datei fehlte. Jetzt bleibt die Markierung weg, und
	der Ordner dort ist erkennbar unvollstaendig (``aufbewahrung`` raeumt ihn
	nach der Frist, schuetzt ihn aber nie als „neueste“).
	"""
	fehler: list[str] = []
	for datei in _dateien(verzeichnis):
		ziel = schluessel(f"{verzeichnis.name}/{datei.name}")
		soll_groesse = datei.stat().st_size
		try:
			with open(datei, "rb") as quelle:
				ablage.schreiben(ziel, quelle)
		except Exception as problem:  # noqa: BLE001 — jeder Fehler ist ein Ergebnis
			logger.warning("Upload von %s fehlgeschlagen: %s", ziel, problem)
			fehler.append(_fehlertext(datei, problem))
			break
		try:
			ist_groesse = ablage.groesse(ziel)
		except Exception as problem:  # noqa: BLE001
			logger.warning("Groesse von %s nicht lesbar: %s", ziel, problem)
			fehler.append(f"{datei.name}: Groesse im Ziel nicht pruefbar")
			break
		if ist_groesse != soll_groesse:
			fehler.append(
				f"{datei.name}: unvollstaendig "
				f"({ist_groesse} von {soll_groesse} Bytes)"
			)
			break
		erwartet = _erwartete_summe(verzeichnis, datei)
		if erwartet:
			ist_summe = _summe_in_der_ablage(ablage, ziel)
			# Review-Befund 7: ein Lesefehler bei der Pruefsumme ist ein
			# FEHLSCHLAG, keine „keine Abweichung“ — sonst gaelte eine
			# unlesbare Datei als geprueft.
			if not ist_summe:
				fehler.append(f"{datei.name}: Pruefsumme nicht pruefbar")
				break
			if ist_summe != erwartet:
				fehler.append(f"{datei.name}: Pruefsumme weicht ab")
				break
	return fehler


def _summe_in_der_ablage(ablage, ziel: str) -> str:
	"""SHA-256 einer Datei in der Ablage — blockweise gelesen (nie ganz im RAM)."""
	summe = hashlib.sha256()
	try:
		with ablage.oeffnen(ziel) as quelle:
			for block in quelle.strom():
				summe.update(block)
	except Exception as fehler:  # noqa: BLE001 — Unlesbarkeit ist der Befund
		logger.warning("Pruefsumme von %s nicht lesbar: %s", ziel, fehler)
		return ""
	return summe.hexdigest()


def hochladen(verzeichnis: Path, *, ablage=None) -> Uploadergebnis:
	"""Eine fertige Sicherung in die Nextcloud legen (siehe Modulkopf).

	``ablage`` ist nur fuer Tests da; im Betrieb ist es ``hole_speicher()``.
	Die lokale Kopie bleibt in JEDEM Fall liegen — was damit passiert,
	entscheidet :func:`nur_neueste_lokal_behalten` erst nach diesem Erfolg.
	"""
	if ablage is None:
		if not ist_aktiv():
			return Uploadergebnis(
				aktiv=False,
				meldung="Die Ablage ist lokal — es wird nichts hochgeladen.",
			)
		ablage = _ablage()
	verzeichnis = Path(verzeichnis)
	if not verzeichnis.is_dir():
		return Uploadergebnis(
			aktiv=True, meldung="Die Sicherung ist lokal nicht vorhanden.",
			fehler=["Verzeichnis fehlt"],
		)
	fehler = _hochladen_je_datei(ablage, verzeichnis)
	anzahl = len(_dateien(verzeichnis))
	groesse = dump.verzeichnisgroesse(verzeichnis)
	if fehler:
		return Uploadergebnis(
			aktiv=True, ok=False, dateien=anzahl, bytes=groesse,
			meldung=(
				"Die Sicherung liegt nur lokal — die Uebertragung in die "
				"Nextcloud ist nicht vollstaendig."
			),
			fehler=fehler,
		)
	logger.info(
		"Sicherung %s in die Nextcloud uebertragen (%s Dateien, %s Bytes).",
		verzeichnis.name, anzahl, groesse,
	)
	return Uploadergebnis(
		aktiv=True, ok=True, dateien=anzahl, bytes=groesse,
		meldung="Sicherung auch in der Nextcloud abgelegt.",
	)


# ── Aufbewahrung auf der Nextcloud-Seite ───────────────────────────────────

def _eintraege_in_der_ablage(ablage) -> list[str]:
	"""Alle Schluessel unter ``sicherungen`` — Fehler werden HOCHGEREICHT.

	Review-Befund 4: frueher schluckte diese Funktion jeden Fehler und gab
	``[]`` zurueck. Die Oberflaeche meldete dann „keine Sicherungen
	vorhanden“, obwohl in Wahrheit die Nextcloud nicht erreichbar war — der
	schlimmste denkbare Fall: der Betrieb glaubt, es gebe keine Sicherung.
	Jetzt entscheidet der Aufrufer: ``status_fuer_oberflaeche`` macht daraus
	„Nextcloud nicht erreichbar“, der Lauf bricht die Aufbewahrung ab.
	"""
	return list(ablage.auflisten(ORDNER))


def _namen_in_der_ablage(ablage) -> list[str]:
	"""Alle Sicherungsnamen im Ordner ``sicherungen`` (aelteste zuerst)."""
	namen = {
		eintrag[len(ORDNER) + 1:].split("/")[0]
		for eintrag in _eintraege_in_der_ablage(ablage)
		if eintrag.startswith(ORDNER + "/")
	}
	return sorted(
		(name for name in namen if aufbewahrung.ist_sicherungsname(name)),
		key=lambda name: zeitpunkt_von_name(name) or datetime.min,
	)


def ist_vollstaendig(ablage, name: str) -> bool:
	"""Liegt in der Ablage eine VOLLSTAENDIGE Sicherung ``name``?

	Dieselbe Regel wie lokal (``aufbewahrung.ist_vollstaendig``): nur mit
	``SHA256SUMS`` UND ``FERTIG``. Ein abgebrochener Upload hinterlaesst einen
	Ordner ohne ``FERTIG`` — der darf nie als „die neueste Sicherung“
	gelten und damit eine echte Kopie vor dem Loeschen schuetzen.
	"""
	try:
		eintraege = set(ablage.auflisten(schluessel(name)))
	except Exception as fehler:  # noqa: BLE001 — nicht lesbar heisst: nicht vollstaendig
		logger.warning("Sicherung %s nicht lesbar: %s", name, fehler)
		return False
	return (
		schluessel(f"{name}/{aufbewahrung.PRUEFSUMMEN_DATEI}") in eintraege
		and schluessel(f"{name}/{aufbewahrung.FERTIG_DATEI}") in eintraege
	)


def zeitpunkt_von_name(name: str) -> datetime | None:
	"""``JJJJ-MM-TT_HHMMSS`` -> ``datetime`` (Delegation an ``aufbewahrung``)."""
	return aufbewahrung.zeitpunkt_aus_name(name)


def sicherungen_auflisten(ablage=None) -> list[tuple[str, int, str, bool]]:
	"""Sicherungen in der Nextcloud: ``(name, groesse_bytes, zeitpunkt, voll)``.

	``zeitpunkt`` ist ISO-Text aus dem Namen (dieselbe Form wie die
	Protokollzeile in der Oberflaeche) — keine Uhrzeit des Servers, keine
	Zeitzone, kein Pfad. Einzelne unlesbare Groessen ergeben ``0`` statt eines
	Abbruchs der ganzen Liste: ein Ordner mit einer kaputten Datei soll die
	uebrigen nicht verstecken. ``voll`` sagt, ob ``SHA256SUMS`` und ``FERTIG``
	dort liegen (Review-Befund 5).

	Ist der Ordner selbst nicht lesbar, wird der Fehler **hochgereicht**
	(``SpeicherNichtErreichbar``/``AblageFehler``) — siehe
	:func:`_eintraege_in_der_ablage`.
	"""
	ablage = ablage if ablage is not None else (_ablage() if ist_aktiv() else None)
	if ablage is None:
		return []
	ergebnis: list[tuple[str, int, str, bool]] = []
	for name, vorhandene in _sicherungen_mit_dateien(ablage):
		zeitpunkt = zeitpunkt_von_name(name)
		ergebnis.append((
			name,
			_groesse_aus_schluesseln(ablage, vorhandene),
			zeitpunkt.isoformat() if zeitpunkt else "",
			_vollstaendig_aus_schluesseln(name, vorhandene),
		))
	return ergebnis


def _sicherungen_mit_dateien(ablage) -> list[tuple[str, set[str]]]:
	"""``{name: {schluessel, …}}`` fuer alle Sicherungen — EIN Auflisten.

	Ein rundes ``ablage.auflisten(ORDNER)`` reicht fuer Name, Groesse und
	Vollstaendigkeit; das frueherer Abfragen je Ordner kostete bei vielen
	Sicherungen ein PROPFIND pro Ordner und je Datei.
	"""
	je_name: dict[str, set[str]] = {}
	for eintrag in _eintraege_in_der_ablage(ablage):
		if not eintrag.startswith(ORDNER + "/"):
			continue
		rest = eintrag[len(ORDNER) + 1:]
		name, _, datei = rest.partition("/")
		if name and datei and aufbewahrung.ist_sicherungsname(name):
			je_name.setdefault(name, set()).add(eintrag)
	return sorted(
		je_name.items(),
		key=lambda paar: zeitpunkt_von_name(paar[0]) or datetime.min,
	)


def _vollstaendig_aus_schluesseln(name: str, vorhandene: set[str]) -> bool:
	return (
		schluessel(f"{name}/{aufbewahrung.PRUEFSUMMEN_DATEI}") in vorhandene
		and schluessel(f"{name}/{aufbewahrung.FERTIG_DATEI}") in vorhandene
	)


def _groesse_aus_schluesseln(ablage, vorhandene: set[str]) -> int:
	"""Summe der Dateigroessen; eine unlesbare Groesse zaehlt als 0."""
	summe = 0
	for eintrag in sorted(vorhandene):
		try:
			summe += int(ablage.groesse(eintrag) or 0)
		except Exception:  # noqa: BLE001 — Anzeige, kein Betriebszustand
			continue
	return summe


def zu_alt(
	namen: list[str], *, jetzt: datetime, aufbewahrung_tage: int,
	ablage=None,
) -> list[str]:
	"""Welche Namen in der Nextcloud sind nach der Frist zu loeschen?

	Dieselbe Regel wie ``aufbewahrung.zu_loeschen``: alles, was aelter als die
	Frist ist — ausser der NEUESTEN erfolgreichen Sicherung (die bleibt, auch
	wenn sie selbst aelter ist; sonst waere nach einem Ausfall die letzte
	Kopie weg).

	**Geschuetzt ist nur eine VOLLSTAENDIGE Sicherung** (Review-Befund 5):
	ein Ordner aus einem abgebrochenen Upload (ohne ``FERTIG``) zaehlt nicht
	als „neueste“ — sonst rettete ein Rest die letzte echte Kopie nicht.
	Ohne ``ablage`` wird die Vollstaendigkeit nicht geprueft (dann gilt die
	Regel rein nach Namen, wie in den Aufrufen ohne Ablage).
	"""
	if aufbewahrung_tage < 1:
		logger.warning(
			"Ungueltige Aufbewahrung (%s Tage) — in der Nextcloud wird nichts geloescht.",
			aufbewahrung_tage,
		)
		return []
	grenze = jetzt - timedelta(days=aufbewahrung_tage)
	mit_zeit: list[tuple[datetime, str]] = [
		(zeitpunkt, name)
		for name in namen
		for zeitpunkt in (zeitpunkt_von_name(name),)
		if zeitpunkt is not None
	]
	mit_zeit.sort()
	if not mit_zeit:
		return []
	neueste = None
	for zeitpunkt, name in reversed(mit_zeit):
		if ablage is None or ist_vollstaendig(ablage, name):
			neueste = name
			break
	return [name for zeitpunkt, name in mit_zeit
			if zeitpunkt < grenze and name != neueste]


def loeschen(name: str, ablage=None) -> bool:
	"""Eine Sicherung samt ihrem Ordner aus der Nextcloud entfernen.

	WebDAV loescht einen ORDNER rekursiv (RFC 4918, 9.6.1) — deshalb wird
	zuerst die Ordner-Adresse geloescht (``ordner_loeschen``). Das ist der
	einzige Weg, der einen Rest aus einem halben Loeschvorgang mitnimmt:
	``auflisten`` nennt nur DATEIEN, ein „leerer Ordner“ war damit nie zu
	finden (SPEICHER-2b, Punkt 5) und ueberlebte jede Aufbewahrung.

	Kann die Ablage keine Ordner loeschen (``False``) oder scheitert sie,
	werden die Dateien einzeln entfernt — dann bleibt wenigstens nichts
	Personenbezogenes liegen. Der Ordner selbst wird danach noch einmal
	versucht; ein einzelner Fehler bricht nicht ab, macht das Ergebnis aber
	``False``: „geloescht“ ist nur, wenn wirklich alles weg ist.

	Ein Name, der in der Nextcloud gar nicht vorkommt (nur eine Zeile in der
	Protokolltabelle), ist **kein Fehler** (Review-Befund 7): es gibt nichts
	zu loeschen, die Zeile des Aufrufers faellt trotzdem. ``True`` heisst
	hier „in der Ablage ist nichts (mehr) vorhanden“.
	"""
	ablage = ablage if ablage is not None else _ablage()
	ordner = schluessel(name)
	vollstaendig = True
	ordner_weg = False
	try:
		ordner_weg = ablage.ordner_loeschen(ordner)
	except Exception as fehler:  # noqa: BLE001 — Einzelloeschen als Rueckfall
		logger.warning("Ordner %s nicht geloescht: %s", ordner, fehler)
		vollstaendig = False
	try:
		eintraege = ablage.auflisten(ordner)
	except Exception as fehler:  # noqa: BLE001
		logger.warning("Sicherung %s nicht lesbar: %s", name, fehler)
		return False
	if not eintraege and (ordner_weg or vollstaendig):
		if vollstaendig:
			logger.info("Sicherung %s aus der Nextcloud entfernt.", name)
		return vollstaendig
	for eintrag in eintraege:
		try:
			if not ablage.loeschen(eintrag):
				vollstaendig = False
		except Exception as fehler:  # noqa: BLE001
			logger.warning("Datei %s nicht geloescht: %s", eintrag, fehler)
			vollstaendig = False
	if vollstaendig:
		# Die Dateien sind weg, der Ordner blieb (Rueckfall-Pfad) — jetzt
		# noch einmal, sonst steht dort eine leere Sicherung.
		try:
			ablage.ordner_loeschen(ordner)
		except Exception as fehler:  # noqa: BLE001 — Aufraeumen ist Beiwerk
			logger.warning("Leerer Ordner %s blieb stehen: %s", ordner, fehler)
		logger.info("Sicherung %s aus der Nextcloud entfernt.", name)
	return vollstaendig



def aufraeumen(*, jetzt: datetime, aufbewahrung_tage: int, ablage=None) -> list[str]:
	"""Aufbewahrung auf der Nextcloud-Seite anwenden. Rueckgabe: entfernte Namen."""
	ablage = ablage if ablage is not None else _ablage()
	namen = _namen_in_der_ablage(ablage)
	entfernt: list[str] = []
	for name in zu_alt(
		namen, jetzt=jetzt, aufbewahrung_tage=aufbewahrung_tage, ablage=ablage,
	):
		if loeschen(name, ablage=ablage):
			entfernt.append(name)
	# Review-Befund 7: leere Ordner (nur noch ein Rest nach einem halben
	# Loeschvorgang) blieben stehen und tauchten in manchen WebDAV-Clients als
	# „Sicherung ohne Inhalt“ auf.
	_leere_ordner_entfernen(ablage)
	if entfernt:
		logger.info("Aufbewahrung (Nextcloud): %s Sicherung(en) entfernt.", len(entfernt))
	return entfernt


def _leere_ordner_entfernen(ablage) -> None:
	"""Sicherungsordner ohne Inhalt entfernen — ueber die ORDNER-Adresse.

	SPEICHER-2b, Punkt 5: hier stand vorher ``ablage.loeschen(name)`` auf
	einem ORDNER-Namen. ``loeschen`` heisst in der Ablage-Schnittstelle aber
	„DATEI entfernen“ — der Aufruf lief entweder ins Leere oder, bei
	``Lokal``, gegen eine Datei gleichen Namens. ``auflisten`` nennt
	grundsaetzlich nur Dateien, „leere Ordner suchen“ war damit wirkungslos.

	Jetzt wird jeder Sicherungsordner, in dem keine Datei mehr liegt, per
	``ordner_loeschen`` entfernt (WebDAV-DELETE auf die Ordner-Adresse,
	rekursiv — RFC 4918, 9.6.1). Das ist der Rueckfall fuer Reste; der
	Normalfall laeuft schon in :func:`loeschen`.

	Ein Ordner, den ``auflisten`` gar nicht kennt (der Server listet leere
	Sammlungen nicht), wird mitgezaehlt: ein Sicherungs-ORDNER hat immer
	Dateien, ein „Name ohne Dateien“ ist genau der Rest, den ein halber
	Loeschvorgang hinterlaesst.
	"""
	ordner: set[str] = set()
	for eintrag in _eintraege_in_der_ablage(ablage):
		if not eintrag.startswith(ORDNER + "/"):
			continue
		rest = eintrag[len(ORDNER) + 1:]
		name = rest.split("/")[0]
		if not name or not aufbewahrung.ist_sicherungsname(name):
			continue
		if "/" in rest:
			# Datei in diesem Ordner -> kein leerer Ordner.
			continue
		ordner.add(name)
	for name in sorted(ordner):
		try:
			if ablage.ordner_loeschen(schluessel(name)):
				logger.info("Leerer Sicherungsordner %s entfernt.", name)
		except Exception as fehler:  # noqa: BLE001 — Aufraeumen ist Beiwerk
			logger.warning("Leerer Ordner %s blieb stehen: %s", name, fehler)


def nur_neueste_lokal_behalten(
	verzeichnis: Path, *, behalten: str
) -> list[str]:
	"""Alle lokalen Sicherungen AUSSER ``behalten`` entfernen.

	Wird nach einem vollstaendigen Upload aufgerufen: lokal bleibt genau die
	juengste Kopie (schnelle Wiederherstellung, ohne erst 2 GB aus der
	Nextcloud zu holen). Absichtlich OHNE Alterspruefung — die Aufbewahrung
	gilt fuer die Nextcloud-Seite; lokal gibt es nur diese eine Kopie.

	**Was NICHT geloescht wird:**
	* ``behalten`` selbst — der Aufrufer ruft das nur nach verifiziertem
	  Upload (Review-Befund 6).
	* **Sicherungen, deren Upload nicht verifiziert ist** (``verifiziert``):
	  Ein frueherer Lauf, dessen Upload gescheitert ist, hat keinen Eintrag
	  in der Nextcloud — seine lokale Kopie ist die EINZIGE. Sie wird
	  deshalb nur entfernt, wenn der Name dort vollstaendig liegt.
	* ``.tmp-``-Reste (die raeumt ``aufbewahrung.verwaiste_temp_entfernen``
	  nach seiner Frist) und fremde Eintraege (nur ``JJJJ-MM-TT_HHMMSS``
	  kommt in Frage).
	"""
	entfernt: list[str] = []
	if not verzeichnis.is_dir():
		return entfernt
	ablage = None
	try:
		ablage = _ablage()
	except Exception as fehler:  # noqa: BLE001 — dann bleibt eben alles liegen
		logger.warning("Ablage fuer die lokale Aufraeumung nicht bestimmbar: %s", fehler)
		return entfernt
	for zeitpunkt, pfad in aufbewahrung.sicherungen_im_verzeichnis(verzeichnis):
		if pfad.name == behalten:
			continue
		if not ist_vollstaendig(ablage, pfad.name):
			logger.info(
				"Lokale Kopie %s bleibt: in der Nextcloud nicht (vollstaendig) "
				"vorhanden — sie ist die einzige Kopie.", pfad.name,
			)
			continue
		if aufbewahrung.entferne(pfad):
			entfernt.append(pfad.name)
	if entfernt:
		logger.info(
			"Lokale Kopien entfernt (nur %s bleibt): %s",
			behalten, ", ".join(entfernt),
		)
	return entfernt
