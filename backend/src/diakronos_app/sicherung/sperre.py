"""BACKUP-1: Sperre gegen zwei gleichzeitige Sicherungslaeufe.

WARUM EINE SPERRE IN REDIS UND EINE IN DER DATENBANK
----------------------------------------------------
Zwei Laeufe gleichzeitig schreiben in dasselbe Verzeichnis und loeschen sich
gegenseitig Dateien weg. Zwei Wege koennen das ausloesen: der Scheduler (03:00)
trifft auf einen Menschen, der gerade "Jetzt sichern" drueckt, oder zwei
App-Arbeiten (``WEB_CONCURRENCY``) bekommen gleichzeitig einen Aufruf.

* **Redis** (``SET NX PX``) ist die schnelle, atomare Sperre. Sie traegt den
  ganzen Betrieb und laeuft nach ``ttl`` von selbst ab, damit ein abgestuerzter
  Prozess sie nicht dauerhaft haelt.
* **Die Datenbank** ist die ehrliche Spur: die Zeile ``sicherungslauf`` mit
  Status ``laeuft`` ueberlebt einen Neustart und wird beim naechsten Start als
  ``fehlgeschlagen`` gemeldet (``raeume_abgebrochene_auf``). Ohne sie waere ein
  abgebrochener Lauf in der Oberflaeche unsichtbar — und genau der ist die
  interessante Information.

Fällt Redis aus, wird NICHT gesichert (fail closed): ein Lauf ohne Sperre
kann eine laufende Sicherung zerstoeren, und ein Dump ist wiederholbar. Die
Meldung an die System Manager sagt das im Klartext.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from diakronos_app.models.sicherung import (
	STATUS_FEHLGESCHLAGEN,
	STATUS_LAEUFT,
	STATUS_OK,
	Sicherungslauf,
)
from diakronos_app.settings import settings

logger = logging.getLogger("diakronos_app.sicherung.sperre")

#: Schluessel der Redis-Sperre. Eigener Namensraum, damit sie nicht mit
#: Sitzungen/Anmeldebremse kollidiert.
SPERRE_SCHLUESSEL = "diakronos:sicherung:sperre"


class SperreBesteht(RuntimeError):
	"""Es laeuft bereits eine Sicherung."""

	def __init__(self, seit: datetime | None = None):
		self.seit = seit
		wann = seit.strftime("%d.%m.%Y %H:%M") if seit else "gerade eben"
		super().__init__(f"Es laeuft bereits eine Sicherung (seit {wann}).")


class SperreNichtVerfuegbar(RuntimeError):
	"""Die Sperre konnte nicht gesetzt werden (Redis weg). Fail closed."""


def _client():
	"""Redis-Client der Sperre — eigene Funktion, damit Tests sie ersetzen."""
	from diakronos_app.settings import settings
	from redis import Redis

	return Redis.from_url(settings.redis_url)


class Sicherungssperre:
	"""Kontext-Manager: setzt die Redis-Sperre und gibt sie wieder frei."""

	def __init__(self, ttl_sekunden: int = 3600):
		self.ttl = max(60, int(ttl_sekunden))
		self._token: str | None = None
		self._schluessel = SPERRE_SCHLUESSEL

	def setzen(self) -> None:
		import uuid

		kennung = uuid.uuid4().hex
		try:
			gesetzt = _client().set(self._schluessel, kennung, nx=True, px=self.ttl * 1000)
		except Exception as fehler:  # noqa: BLE001 — Redis weg
			raise SperreNichtVerfuegbar(
				"Die Sperre der Datensicherung ist nicht erreichbar (Redis). "
				"Es wurde nichts gesichert."
			) from fehler
		if not gesetzt:
			raise SperreBesteht()
		self._token = kennung

	def freigeben(self) -> None:
		# Nur die EIGENE Sperre loeschen: laeuft die TTL ab, waehrend der Lauf
		# noch arbeitet, hat inzwischen vielleicht ein anderer die Sperre.
		#
		# Vergleich als TEXT: ein echter Redis-Client liefert `bytes`
		# zurueck (decode_responses ist nicht gesetzt), der Test-Stub `str`.
		# Vorher stand hier `== self._token.encode()` — gegen den Stub war das
		# immer falsch, die Sperre wurde NIE freigegeben und ein einziger
		# abgebrochener Lauf blockierte jede weitere Sicherung bis zum Ablauf
		# der TTL. Der Test hat das gefunden, nicht der Betrieb.
		if not self._token:
			return
		try:
			client = _client()
			gespeichert = client.get(self._schluessel)
			if isinstance(gespeichert, bytes):
				gespeichert = gespeichert.decode()
			if gespeichert == self._token:
				client.delete(self._schluessel)
		except Exception as fehler:  # noqa: BLE001
			logger.warning("Sicherungssperre nicht freigegeben: %s", fehler)
		finally:
			self._token = None

	def __enter__(self) -> Sicherungssperre:
		self.setzen()
		return self

	def __exit__(self, *_exc) -> None:
		self.freigeben()


def laufende_sicherung(session: Session) -> Sicherungslauf | None:
	"""Die aelteste Zeile mit Status ``laeuft`` (falls vorhanden)."""
	return session.scalars(
		select(Sicherungslauf)
		.where(Sicherungslauf.status == STATUS_LAEUFT)
		.order_by(Sicherungslauf.begonnen_am)
	).first()


def raeume_abgebrochene_auf(session: Session, *, jetzt: datetime | None = None,
                            grund: str = "Der Lauf wurde abgebrochen (Neustart).") -> list[str]:
	"""Zeilen mit Status ``laeuft`` klaeren.

	Wird beim START eines Laufs aufgerufen: was jetzt noch ``laeuft`` ist,
	gehoert zu einem Prozess, den es nicht mehr gibt. AUSNAHME: steht im
	Sicherungsverzeichnis die ``FERTIG``-Markierung, war der Lauf doch
	vollstaendig — typisch nach dem Einspielen einer Sicherung, deren eigener
	Dump die Protokollzeile noch im Zustand ``laeuft`` enthaelt. Dann wird er
	als ``ok`` gefuehrt, statt einen falschen Fehlschlag zu melden.
	Rueckgabe: die Namen der betroffenen Laeufe.
	"""
	from diakronos_app.sicherung import dump
	from diakronos_app.sicherung.einstellungen import jetzt_ortszeit

	zeit = jetzt or jetzt_ortszeit()
	basis = Path(settings.backup_dir)
	offen = list(session.scalars(
		select(Sicherungslauf).where(Sicherungslauf.status == STATUS_LAEUFT)
	))
	for zeile in offen:
		verzeichnis = basis / zeile.name
		if (verzeichnis / dump.FERTIG_NAME).is_file():
			zeile.status = STATUS_OK
			zeile.meldung = "Sicherung vollstaendig (Fertig-Markierung)."
			if not zeile.groesse_bytes:
				zeile.groesse_bytes = dump.verzeichnisgroesse(verzeichnis)
		else:
			zeile.status = STATUS_FEHLGESCHLAGEN
			zeile.meldung = grund
		zeile.beendet_am = zeile.beendet_am or zeit
	session.commit()
	return [zeile.name for zeile in offen]
