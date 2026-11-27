"""ABN-2/ABN-2b — Wiederherstellung: pruefen, einspielen, nachweisen (Tests).

Was hier festgehalten wird (die Zusagen der Karten ABN-2 und ABN-2b):

1. **Eine Sicherung wird VOR dem Anfassen geprueft** — fehlende
   ``FERTIG``-Markierung, abweichende Pruefsumme, fehlender Dump, unlesbarer
   Dump: in allen Faellen wird nichts eingespielt und nichts geloescht.
2. **Die Dateiablage kommt mit** — und zwar an den RICHTIGEN Ort: der
   Fehler in BETRIEBSANLEITUNG 14.4 (``tar -C data/files`` statt
   ``data/files/files``) darf nicht zurueckkommen. Das Archiv wird geprueft
   (Groesse UND SHA-256 je Eintrag), unsichere Pfade und Nicht-Dateien werden
   verworfen. Geschrieben wird IMMER lokal, auch bei
   ``SPEICHER_BACKEND=nextcloud`` (ABN-2b/M3).
3. **Kein halber Zustand** (ABN-2b/H2): eingespielt wird in eine NEUE
   Datenbank ``<ziel>_wiederherstellung``; erst nach Migration und Zaehlung
   wird getauscht, und die alte bleibt als ``<ziel>_vorher_<zeit>`` stehen.
   Scheitert ``pg_restore``, ist die Zieldatenbank unveruehrt.
4. **Der Bericht zaehlt nach**: Soll aus dem Dump-Index, Ist aus dem echten
   Schema; eine Abweichung ist ein Fehlschlag (Exit 1).
5. **Die Vorsicherung ist Pflicht** (ABN-2b/H3) und laeuft ueber den normalen
   Sicherungslauf (Sperre, Protokollzeile), nicht ueber ``dump.sichere``.
6. **Die Protokollzeile wird berichtigt** (ABN-2b/M1), ohne einen gerade
   laufenden Lauf als Fehlschlag zu markieren.

Echtes ``pg_restore``/``psql``/``alembic`` laeuft in der Suite nicht (SQLite,
kein PostgreSQL) — die Aufrufe werden an der Prozessgrenze ersetzt und dabei
auf Argumente und Umgebung geprueft. Der ECHTE Lauf gegen PostgreSQL steht im
Abnahmeprotokoll (docs/abnahmen/ABN-2-RESTORE-PROBE.md).
"""

from __future__ import annotations

import hashlib
import io
import os
import subprocess
import tarfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from diakronos_app.sicherung import dump, wiederherstellen as wdh

NAME = "2026-11-26_030000"


# ── Fixtures ───────────────────────────────────────────────────────────────

@pytest.fixture()
def heim(monkeypatch, tmp_path):
	"""Eigener Datenbaum: ``files``/``files/files``-Struktur wie im Betrieb.

	``settings.files_dir`` ist der BIND-MOUNT-Punkt (im Betrieb
	``/data/files``) — die Ablage schreibt ihre Dateien direkt hinein. Im
	Betriebsverzeichnis heisst dieser Ordner ``files``, liegt aber unter
	``data/``; hier ist er ``<tmp>/files``.
	"""
	import diakronos_app.settings as settings_modul

	wurzel = tmp_path / "data"
	files = wurzel / "files"
	files.mkdir(parents=True)
	heim = wurzel / "sicherungen"
	heim.mkdir(parents=True)
	for modul in (settings_modul.settings, dump.settings):
		monkeypatch.setattr(modul, "files_dir", str(files))
		monkeypatch.setattr(modul, "backup_dir", str(heim))
	# Die Ablage-Umsetzung merkt sich die Einstellung; nach einem Test, der
	# ``speicher_backend`` umstellt, darf hier nichts Altes weiterleben.
	from diakronos_app import speicher as speicher_modul
	orig = speicher_modul._speicher
	speicher_modul.vergiss_speicher()
	yield {"wurzel": wurzel, "files": files, "sicherungen": heim}
	speicher_modul._speicher = orig
	speicher_modul.vergiss_speicher()


def _dateiarchiv(ziel: Path, dateien: dict[str, bytes], *,
                 extra: list[tuple[str, bytes, str]] | None = None) -> None:
	"""Ein ``files.tar.gz`` wie ``dump.schreibe_dateiarchiv`` es schreibt."""
	with tarfile.open(ziel, "w:gz") as archiv:
		for name, inhalt in sorted(dateien.items()):
			info = tarfile.TarInfo(name)
			info.size = len(inhalt)
			archiv.addfile(info, io.BytesIO(inhalt))
		for name, inhalt, art in extra or []:
			info = tarfile.TarInfo(name)
			info.size = len(inhalt)
			if art == "symlink":
				info.type = tarfile.SYMTYPE
				info.linkname = "/etc/passwd"
				info.size = 0
				archiv.addfile(info)
			elif art == "dir":
				info.type = tarfile.DIRTYPE
				info.size = 0
				archiv.addfile(info)
			else:
				archiv.addfile(info, io.BytesIO(inhalt))


def _sicherung(heim, *, name: str = NAME, dateien: dict[str, bytes] | None = None,
               dump_inhalt: bytes = b"PGDMP-fake",
               extra: list[tuple[str, bytes, str]] | None = None) -> Path:
	"""Ein vollstaendiges Sicherungsverzeichnis mit gueltigen Pruefsummen."""
	ordner = heim["sicherungen"] / name
	ordner.mkdir(parents=True)
	(ordner / dump.DUMP_NAME).write_bytes(dump_inhalt)
	_dateiarchiv(ordner / dump.ARCHIV_NAME, dateien or {}, extra=extra)
	dump.schreibe_pruefsummen(ordner)
	(ordner / dump.FERTIG_NAME).write_bytes(b"")
	return ordner


DUMP_INDEX = """\
;
; Archive created at 2026-11-26 03:00:00
;
1; 3079 19015 TABLE DATA public mitglied diakronos 42
2; 3079 19019 TABLE DATA public gruppe diakronos 7
3; 3079 19023 TABLE DATA public file diakronos 3
5; 3079 19031 SEQUENCE SET public mitglied_id_seq diakronos
"""

#: So sieht der Index einer ECHTEN App-Sicherung aus (``pg_dump --no-owner``,
#: im Wegwerf-Stack ABN-2 aus ``db.dump`` gelesen): KEINE Datensatzmenge.
DUMP_INDEX_OHNE_ZAHL = """\
;
4783; 0 16390 TABLE DATA public ablaufplan diakronos
4836; 0 16805 TABLE DATA public ablaufplan_position diakronos
4890; 0 16404 TABLE DATA public anmeldeformular diakronos
5042; 0 16385 SEQUENCE SET public ablaufplan_id_seq diakronos
"""


@pytest.fixture()
def pg_ersatz(monkeypatch):
	"""``pg_restore``/``psql``/``alembic`` durch Aufzeichner ersetzen.

	Rueckgabe ist eine Liste aller Aufrufe als ``(programm, argumente, env)``.
	``psql`` antwortet je Abfrage sinnvoll: Tabellenliste, Zeilenzahlen,
	``alembic_version``, offene Sitzungen (0).
	"""
	aufrufe: list[tuple[str, list[str], dict]] = []
	zeilen = {"mitglied": 42, "gruppe": 7, "file": 3}

	def _run(kommando, *, env=None, capture_output=None, text=None, check=None,
	         timeout=None):  # noqa: ANN001 — Signatur von subprocess.run
		programm = os.path.basename(kommando[0])
		aufrufe.append((programm, list(kommando[1:]), dict(env or {})))
		# Im Image gibt es KEIN ``psql`` (so verhaelt sich der echte Lauf):
		# der Aufruf faellt auf den Treiberweg (``_sql``) zurueck.
		if programm == "psql":
			raise FileNotFoundError(kommando[0])
		stdout = ""
		if programm == "pg_restore" and "--list" in kommando:
			stdout = DUMP_INDEX
		return subprocess.CompletedProcess(kommando, 0, stdout=stdout, stderr="")

	monkeypatch.setattr(wdh.subprocess, "run", _run)
	monkeypatch.setattr(wdh, "_alembic_ini", lambda: Path("/app/alembic.ini"))

	def _sql(env, datenbank, anweisung, *, timeout, autocommit=True):  # noqa: ANN001
		# Ersatzweg ohne ``psql``: als psql-Aufruf aufzeichnen, damit die Tests
		# DDL und Abfragen an derselben Stelle pruefen koennen. Mehrere
		# Anweisungen (Transaktion, ABN-2c/H1) landen als EIN Aufruf.
		eintrag = {**dict(env or {}), "PGDATABASE": datenbank}
		if not autocommit:
			eintrag["AUTOCOMMIT"] = "aus"
		aufrufe.append(("psql",
		                ["-v", "ON_ERROR_STOP=1", "-t", "-A", "-c", anweisung],
		                eintrag))
		if "pg_stat_activity" in anweisung:
			return "0"
		if "FROM pg_database" in anweisung:
			return "diakronos\npostgres"
		if "SELECT datname" in anweisung:
			return "diakronos\npostgres"
		if "FROM alembic_version" in anweisung:
			return "abn2_head" if datenbank == "diakronos_wiederherstellung" else "alt_head"
		if "pg_catalog.pg_class" in anweisung:
			return "\n".join(zeilen or {})
		if "UNION ALL" in anweisung:
			return "\n".join(f"{k}|{v}" for k, v in zeilen.items())
		return ""

	monkeypatch.setattr(wdh, "_sql", _sql)
	# Der Dump-Index kommt aus dem ERSATZ: die echten Dateien in ``_sicherung``
	# sind Attrappen (kein gueltiges ``-Fc``-Archiv).
	monkeypatch.setattr(wdh, "pruefe_dump_inhalt",
	                    lambda *a, **k: {"mitglied": 42, "gruppe": 7, "file": 3})
	# Die Anzeige-Berichtigung braucht eine Datenbank — hier nicht Teil der
	# Zusage (dafuer gibt es eigene Tests in test_abn2b_*).
	monkeypatch.setattr(wdh, "_stelle_anzeige_wieder_her", lambda *a, **k: None)
	return aufrufe


def _verwaltung_ersatz(aufrufe: list[str], *, scheitert_bei: str | None = None):
	"""``_sql`` ersetzen: Anweisung aufzeichnen (wie ``psql -c``), optional scheitern."""

	def _sql(env, datenbank, anweisung, *, timeout, autocommit=True):  # noqa: ANN001
		aufrufe.append(f"psql -d {datenbank} -c {anweisung}")
		if "pg_stat_activity" in anweisung:
			return "0"
		if "pg_database" in anweisung:
			return "diakronos\npostgres"
		if scheitert_bei and scheitert_bei in anweisung \
				and "wiederherstellung" in anweisung:
			raise wdh.WiederherstellungsFehler(
				"ALTER DATABASE scheiterte (database is being accessed)"
			)
		return ""

	return _sql


def _psql_aufrufe(aufrufe, *muster: str) -> list[tuple[str, list[str], dict]]:
	"""``psql``-Aufrufe, deren Argumente ALLE Muster enthalten."""
	return [
		eintrag for eintrag in aufrufe
		if eintrag[0] == "psql"
		and all(m in " ".join(eintrag[1]) for m in muster)
	]


# ── 1. Pruefungen vor dem Anfassen ─────────────────────────────────────────

def test_fehlen_der_fertig_markierung_bricht_ab(heim):
	ordner = _sicherung(heim)
	(ordner / dump.FERTIG_NAME).unlink()
	with pytest.raises(wdh.WiederherstellungsFehler, match="FERTIG"):
		wdh.pruefe_sicherung(ordner)


def test_abweichende_pruefsumme_bricht_ab(heim):
	ordner = _sicherung(heim)
	(ordner / dump.DUMP_NAME).write_bytes(b"nachher anders")
	with pytest.raises(wdh.WiederherstellungsFehler, match="beschaedigt"):
		wdh.pruefe_sicherung(ordner)


def test_fehlende_pruefsummendatei_bricht_ab(heim):
	ordner = _sicherung(heim)
	(ordner / dump.PRUEFSUMMEN_NAME).unlink()
	with pytest.raises(wdh.WiederherstellungsFehler, match="Pruefsummen"):
		wdh.pruefe_sicherung(ordner)


def test_dump_index_liefert_zeilenzahlen(heim, pg_ersatz):
	ordner = _sicherung(heim)
	zaehlung = wdh.pruefe_sicherung(ordner)
	# Die SEQUENCE-SET-Zeile zaehlt NICHT mit.
	assert zaehlung == {"mitglied": 42, "gruppe": 7, "file": 3}


def test_echter_index_ohne_anzahl_gilt_als_bekannt_aber_unbekannt(heim, monkeypatch):
	"""So sieht eine ECHTE App-Sicherung aus: Tabellen ja, Zahl nein.

	Frühere Fassung verlangte zwingend eine Zahl und haette damit JEDE echte
	Sicherung abgewiesen (im Wegwerf-Stack ABN-2 genau so passiert).
	"""
	ordner = _sicherung(heim)

	class _Index:
		returncode = 0
		stdout = DUMP_INDEX_OHNE_ZAHL
		stderr = ""

	monkeypatch.setattr(wdh.subprocess, "run", lambda *a, **k: _Index())
	zaehlung = wdh.pruefe_sicherung(ordner)
	assert set(zaehlung) == {"ablaufplan", "ablaufplan_position", "anmeldeformular"}
	assert all(wert == -1 for wert in zaehlung.values())


def test_unbekannte_anzahl_ist_keine_abweichung():
	bank = wdh.Datenbankbericht(
		soll={"ablaufplan": -1, "mitglied": 42},
		ist={"ablaufplan": 4, "mitglied": 42},
	)
	assert bank.abweichungen == {}


def test_unlesbarer_dump_bricht_ab(heim, monkeypatch):
	ordner = _sicherung(heim)

	class _Kaputt:
		returncode = 1
		stdout = ""
		stderr = "pg_restore: error: input file does not appear to be a valid archive"

	monkeypatch.setattr(wdh.subprocess, "run",
	                    lambda *a, **k: _Kaputt())
	with pytest.raises(wdh.WiederherstellungsFehler, match="nicht lesbar"):
		wdh.pruefe_dump_inhalt(ordner / dump.DUMP_NAME)


def test_dump_ohne_tabellendaten_bricht_ab(heim, monkeypatch):
	ordner = _sicherung(heim)

	class _Leer:
		returncode = 0
		stdout = "; 0 0 COMMENT - nothing here\n"
		stderr = ""

	monkeypatch.setattr(wdh.subprocess, "run", lambda *a, **k: _Leer())
	with pytest.raises(wdh.WiederherstellungsFehler, match="keine Tabellendaten"):
		wdh.pruefe_sicherung(ordner)


# ── 2. Dateiablage: Ort, Pruefung, Sicherheit ──────────────────────────────

def test_dateien_landen_in_der_ablage_wurzel(heim):
	"""DIE Stelle, an der die Betriebsanleitung falsch war (``files/files``)."""
	ordner = _sicherung(heim, dateien={
		"abc-foto.png": b"\x89PNG-inhalt",
		"unter/ordner/notiz.txt": b"text",
	})
	bericht = wdh.spiele_dateien_ein(ordner / dump.ARCHIV_NAME)
	assert bericht.dateien == 2
	assert bericht.bytes == len(b"\x89PNG-inhalt") + 4
	assert (heim["files"] / "abc-foto.png").read_bytes() == b"\x89PNG-inhalt"
	assert (heim["files"] / "unter/ordner/notiz.txt").read_bytes() == b"text"
	# NICHT in einem zweiten Unterordner — und kein Rest liegen geblieben.
	assert not (heim["files"] / "files").exists()
	assert not [p for p in heim["files"].rglob("*") if p.name.startswith(".abn2-")]
	# Der Bericht nennt die Wurzel, in die geschrieben wurde.
	assert bericht.ziel_wurzel == str(heim["files"])


def test_verweise_und_ordner_werden_verworfen(heim):
	ordner = _sicherung(heim, dateien={"echt.txt": b"x"},
	                    extra=[("link", b"", "symlink"), ("ordner/", b"", "dir")])
	bericht = wdh.spiele_dateien_ein(ordner / dump.ARCHIV_NAME)
	assert bericht.dateien == 1
	# Das Verzeichnis ist kein Verlust und steht deshalb NICHT im Bericht; der
	# Verweis wird verworfen (Sicherheit) und steht darin.
	assert len(bericht.verworfen) == 1
	assert bericht.verworfen[0].startswith("link")
	assert not (heim["files"] / "link").exists()


@pytest.mark.parametrize("boese", ["../aussen.txt", "/etc/passwd", "a/../../b.txt"])
def test_unsichere_pfade_brechen_ab(heim, boese):
	ordner = _sicherung(heim, dateien={"ok.txt": b"x"})
	_dateiarchiv(ordner / dump.ARCHIV_NAME, {"ok.txt": b"x", boese: b"boese"})
	dump.schreibe_pruefsummen(ordner)
	with pytest.raises(wdh.WiederherstellungsFehler, match="Unsicherer Pfad"):
		wdh.spiele_dateien_ein(ordner / dump.ARCHIV_NAME)
	assert not (heim["wurzel"].parent / "aussen.txt").exists()


def test_abgeschnittene_datei_wird_erkannt(heim):
	"""Eine Datei, die kuerzer ist als ihr tar-Kopf sagt, ist ein Abbruch.

	So sieht ein waehrend des Sicherns abgebrochener Lauf in einem Archiv aus,
	das von aussen gekommen ist (z. B. eine per ``cp`` halb kopierte
	``files.tar.gz``): die Pruefsumme der Sicherung fehlt in diesem Fall
	(sonst faellt es dort schon auf) — hier wird direkt eingespielt.
	"""
	ordner = _sicherung(heim, dateien={"gross.bin": b"x" * 100})
	with tarfile.open(ordner / dump.ARCHIV_NAME) as archiv:
		echt = archiv.getmember("gross.bin")

	class _KurzesTar:
		def __init__(self, members):  # noqa: ANN001
			self._members = members

		def __iter__(self):
			return iter(self._members)

		def extractfile(self, member):  # noqa: ANN001
			return io.BytesIO(b"x" * 10)  # 10 statt 100 Bytes

		def __enter__(self):
			return self

		def __exit__(self, *_exc):
			return False

	import diakronos_app.sicherung.wiederherstellen as modul

	echt_modul = modul.tarfile.open
	modul.tarfile.open = lambda *a, **k: _KurzesTar([echt])  # noqa: ARG005
	try:
		with pytest.raises(wdh.WiederherstellungsFehler, match="abgeschnitten"):
			wdh.spiele_dateien_ein(ordner / dump.ARCHIV_NAME)
	finally:
		modul.tarfile.open = echt_modul


def test_zweiter_lauf_ueberspringt_gleiche_dateien_und_wiederholen_schreibt(heim):
	ordner = _sicherung(heim, dateien={"a.txt": b"1", "b.txt": b"22"})
	erst = wdh.spiele_dateien_ein(ordner / dump.ARCHIV_NAME)
	assert erst.dateien == 2
	zweit = wdh.spiele_dateien_ein(ordner / dump.ARCHIV_NAME)
	assert (zweit.dateien, zweit.uebersprungen) == (0, 2)
	dritt = wdh.spiele_dateien_ein(ordner / dump.ARCHIV_NAME, wiederholen=True)
	assert (dritt.dateien, dritt.uebersprungen) == (2, 0)


def test_gleich_gross_aber_anders_wird_neu_geschrieben(heim):
	"""ABN-2b/M2: nicht die Groesse entscheidet, sondern der Inhalt.

	Gleiche Groesse, anderer Inhalt war vorher ein stiller „unveraendert“ —
	genau der Fall, in dem eine beschaedigte Datei in der Ablage stehen bleibt.
	"""
	(heim["files"] / "a.txt").write_bytes(b"A")
	ordner = _sicherung(heim, dateien={"a.txt": b"B"})
	bericht = wdh.spiele_dateien_ein(ordner / dump.ARCHIV_NAME)
	assert (bericht.dateien, bericht.uebersprungen) == (1, 0)
	assert (heim["files"] / "a.txt").read_bytes() == b"B"


def test_aufaddierend_nichts_wird_geloescht(heim):
	"""Eine vorhandene Datei, die nicht im Archiv steht, bleibt."""
	(heim["files"] / "bleibt.txt").write_bytes(b"da")
	ordner = _sicherung(heim, dateien={"neu.txt": b"x"})
	wdh.spiele_dateien_ein(ordner / dump.ARCHIV_NAME)
	assert (heim["files"] / "bleibt.txt").read_bytes() == b"da"
	assert (heim["files"] / "neu.txt").is_file()


def test_fehlt_das_archiv_ist_das_ein_fehler(heim):
	ordner = _sicherung(heim)
	(ordner / dump.ARCHIV_NAME).unlink()
	with pytest.raises(wdh.WiederherstellungsFehler, match="Dateiarchiv fehlt"):
		wdh.spiele_dateien_ein(ordner / dump.ARCHIV_NAME)


def test_dateibestand_zaehlt_dateien_und_bytes(heim):
	ordner = _sicherung(heim, dateien={"a.txt": b"12345", "b.txt": b"67"})
	wdh.spiele_dateien_ein(ordner / dump.ARCHIV_NAME)
	assert wdh.dateibestand() == (2, 7)


def test_dateibestand_ignoriert_temp_reste(heim):
	"""ABN-2b/L4: ein Rest des Entpackens zaehlt nicht als Ablage-Datei."""
	(heim["files"] / "echt.txt").write_bytes(b"abc")
	rest = heim["files"] / ".abn2-abc123" / "datei-00000001"
	rest.parent.mkdir()
	rest.write_bytes(b"xxxxxx")
	assert wdh.dateibestand() == (1, 3)


def test_temp_reste_im_archiv_werden_verworfen(heim):
	"""ABN-2b/L4: ein ``.abn2-*``-Pfad im Archiv ist ein Sicherungsrest."""
	ordner = _sicherung(heim, dateien={"echt.txt": b"x"})
	_dateiarchiv(ordner / dump.ARCHIV_NAME,
	             {"echt.txt": b"x", ".abn2-xyz/datei-00000001": b"rest"})
	dump.schreibe_pruefsummen(ordner)
	bericht = wdh.spiele_dateien_ein(ordner / dump.ARCHIV_NAME)
	assert bericht.dateien == 1
	assert any("Sicherungsrest" in eintrag for eintrag in bericht.verworfen)
	assert not (heim["files"] / ".abn2-xyz").exists()


def test_nextcloud_modus_schreibt_lokal(heim, monkeypatch):
	"""ABN-2b/M3: bei ``SPEICHER_BACKEND=nextcloud`` nur LOKAL einspielen.

	``files.tar.gz`` enthaelt nur die lokale Ablage. Wuerde ``spiele_dateien_ein``
	ueber ``hole_speicher()`` in die Nextcloud schreiben, laegen die Dateien
	dort, wo die App (Modus ``lokal``) sie nicht sucht — und der fremde
	Nextcloud-Bestand wuerde ueberschrieben. Die Attrappe belegt: die
	Nextcloud wird NICHT benutzt, der lokale Dateibaum bekommt die Datei.
	"""
	import diakronos_app.settings as settings_modul
	from diakronos_app import speicher as speicher_modul
	from diakronos_app.speicher.basis import Basis

	benutzt: list[str] = []

	class _Attrappe(Basis):  # type: ignore[misc]
		name = "nextcloud"

		def _unbenutzt(self, *_a, **_k):  # noqa: ANN002, ANN003
			benutzt.append("nextcloud")
			raise AssertionError("Die Nextcloud darf nicht angefasst werden")

		schreiben = _unbenutzt
		lesen = _unbenutzt
		groesse = _unbenutzt
		auflisten = _unbenutzt
		oeffnen = _unbenutzt
		loeschen = _unbenutzt
		existiert = _unbenutzt
		gesundheit = _unbenutzt

	speicher_modul.setze_speicher(_Attrappe())
	monkeypatch.setattr(settings_modul.settings, "speicher_backend", "nextcloud", raising=False)
	ordner = _sicherung(heim, dateien={"protokoll.pdf": b"%PDF-1.4"})
	bericht = wdh.spiele_dateien_ein(ordner / dump.ARCHIV_NAME)
	assert benutzt == []
	assert bericht.dateien == 1
	assert bericht.ziel_wurzel == str(heim["files"])
	assert (heim["files"] / "protokoll.pdf").read_bytes() == b"%PDF-1.4"
	assert wdh.dateibestand() == (1, 8)


def test_ziel_wurzel_ausdruecklich_lokal(heim, tmp_path):
	"""``ziel_wurzel`` gewinnt — der Weg bleibt auch dann lokal."""
	ziel = tmp_path / "anderswo"
	ziel.mkdir()
	ordner = _sicherung(heim, dateien={"a.txt": b"abc"})
	bericht = wdh.spiele_dateien_ein(ordner / dump.ARCHIV_NAME, ziel_wurzel=ziel)
	assert bericht.dateien == 1
	assert (ziel / "a.txt").read_bytes() == b"abc"
	assert not (heim["files"] / "a.txt").exists()


# ── 3. Datenbank einspielen: kein halber Zustand ───────────────────────────

def test_eingespielt_wird_in_neue_datenbank_und_erst_dann_getauscht(heim, pg_ersatz):
	"""ABN-2b/H2: DROP der Zieldatenbank kommt VOR dem Tausch nicht vor."""
	ordner = _sicherung(heim)
	neu = wdh.spiele_datenbank_ein(ordner / dump.DUMP_NAME)
	assert neu == "diakronos_wiederherstellung"

	# Kein DROP/CREATE an der ZIELDATENBANK: nur die NEUE wird angelegt.
	# (Ihr DROP raeumt einen Rest eines frueheren Versuchs weg — nie Betriebsdaten.)
	assert _psql_aufrufe(pg_ersatz, 'DROP DATABASE IF EXISTS "diakronos"') == []
	assert len(_psql_aufrufe(pg_ersatz, 'CREATE DATABASE "diakronos_wiederherstellung"')) == 1
	assert _psql_aufrufe(pg_ersatz, 'CREATE DATABASE "diakronos"') == []
	assert _psql_aufrufe(pg_ersatz, 'DROP DATABASE IF EXISTS "diakronos"') == []

	restore = [aufruf for aufruf in pg_ersatz if aufruf[0] == "pg_restore"]
	assert len(restore) == 1
	argumente = restore[0][1]
	# Die Datei steht ALS ARGUMENT am Ende — nicht ``< db.dump`` (stdin).
	assert argumente[-1] == str(ordner / dump.DUMP_NAME)
	assert "--dbname" in argumente
	assert argumente[argumente.index("--dbname") + 1] == "diakronos_wiederherstellung"
	assert "--exit-on-error" in argumente
	assert "--single-transaction" in argumente
	assert "--no-owner" in argumente
	# KEIN ``--role``: der Dump ist ``--no-owner``; ein ``--role`` verlangte eine
	# vorhandene Rolle (im Wegwerf-Stack ABN-2b daran abgebrochen).
	assert "--role" not in argumente
	# Verbindungsdaten nur in der Umgebung, nie auf der Zeile.
	assert all("@" not in teil for teil in argumente)


def test_abbruch_von_pg_restore_laesst_die_alte_datenbank_stehen(heim, monkeypatch):
	"""ABN-2b/H2: scheitert ``pg_restore``, bleibt die Zieldatenbank unangetastet."""
	ordner = _sicherung(heim)
	aufrufe: list[str] = []

	def _run(kommando, *, env=None, capture_output=None, text=None, check=None,
	         timeout=None):  # noqa: ANN001
		text_kommando = " ".join(kommando)
		programm = os.path.basename(kommando[0])
		aufrufe.append(text_kommando)
		if programm == "pg_restore" and "--list" not in kommando:
			return subprocess.CompletedProcess(
				kommando, 1, stdout="",
				stderr="pg_restore: error: could not execute query: relation exists\n")
		if programm == "pg_restore":
			return subprocess.CompletedProcess(kommando, 0, stdout=DUMP_INDEX, stderr="")
		stdout = "0\n" if "pg_stat_activity" in text_kommando else ""
		if "FROM pg_database" in text_kommando:
			stdout = "diakronos\npostgres\n"
		return subprocess.CompletedProcess(kommando, 0, stdout=stdout, stderr="")

	monkeypatch.setattr(wdh.subprocess, "run", _run)
	monkeypatch.setattr(wdh, "_sql", _verwaltung_ersatz(aufrufe))
	monkeypatch.setattr(wdh, "pruefe_dump_inhalt",
	                    lambda *a, **k: {"mitglied": 42, "gruppe": 7, "file": 3})
	with pytest.raises(wdh.WiederherstellungsFehler, match="pg_restore.*relation exists"):
		wdh.spiele_datenbank_ein(ordner / dump.DUMP_NAME)
	# Nie ein DROP/ALTER an der ZIELDATENBANK; die halb gefuellte NEUE wird
	# wieder verworfen (dort liegen keine Betriebsdaten).
	assert not [auftrag for auftrag in aufrufe if '"diakronos"' in auftrag and
	            ("DROP" in auftrag or "ALTER" in auftrag)]
	assert any('DROP DATABASE IF EXISTS "diakronos_wiederherstellung"' in auftrag
	           for auftrag in aufrufe)


def test_getauschte_datenbank_bleibt_als_vorher_stehen(heim, pg_ersatz, monkeypatch):
	"""Der Tausch ist ein RENAME; die alte Datenbank wird NICHT geloescht.

	ABN-2c/H1: BEIDE RENAMEs muessen in EINER Transaktion laufen
	(``autocommit`` aus) — sonst gibt es zwischen ihnen einen Moment ohne
	Zieldatenbank.
	"""
	alt = wdh.tausche_datenbank("diakronos_wiederherstellung", ziel="diakronos")
	assert alt.startswith("diakronos_vorher_")
	tausch = [eintrag for eintrag in _psql_aufrufe(pg_ersatz, "ALTER DATABASE", "RENAME TO")
	          if "RENAME TO" in " ".join(eintrag[1])]
	# Genau EIN Aufruf mit BEIDEN Umbenennungen — und ohne Autocommit.
	assert len(tausch) == 1, tausch
	anweisung = tausch[0][1][-1]
	assert f'ALTER DATABASE "diakronos" RENAME TO "{alt}"' in anweisung
	assert f'ALTER DATABASE "diakronos_wiederherstellung" RENAME TO "diakronos"' in anweisung
	assert tausch[0][2].get("AUTOCOMMIT") == "aus", "Tausch ohne Transaktion"
	# Kein DROP auf die alte oder die neue Datenbank.
	assert not [eintrag for eintrag in pg_ersatz
	            if eintrag[0] == "psql" and "DROP DATABASE" in " ".join(eintrag[1])
	            and ("vorher" in " ".join(eintrag[1]))]


def test_gescheiterter_tausch_laesst_die_alte_datenbank_aktiv(heim, monkeypatch):
	"""ABN-2c/H1: bricht der Tausch ab, gilt KEINE der beiden Umbenennungen.

	Der alte Code fuehrte zwei getrennte ``ALTER DATABASE`` aus und versuchte,
	den ersten von Hand zurueckzunehmen — ein Kill/OOM dazwischen hinterliess
	einen Zustand OHNE Zieldatenbank. Jetzt laufen beide in EINER Transaktion;
	ein Fehler (hier: der zweite RENAME scheitert) rollt alles zurueck. Der
	Ersatz zeichnet auf, dass genau EIN transaktionaler Aufruf abgesetzt wurde
	und KEIN Ruecknahme-ALTER hinterhergeschickt wird.
	"""
	aufrufe: list[tuple[str, bool]] = []

	def _run(kommando, *, env=None, capture_output=None, text=None, check=None,
	         timeout=None):  # noqa: ANN001
		if os.path.basename(kommando[0]) == "psql":
			raise FileNotFoundError(kommando[0])
		return subprocess.CompletedProcess(kommando, 0, stdout="", stderr="")

	def _sql(env, datenbank, anweisung, *, timeout, autocommit=True):  # noqa: ANN001
		aufrufe.append((anweisung, autocommit))
		if "SELECT datname FROM pg_database" in anweisung:
			return "diakronos\npostgres\n"
		if "pg_stat_activity" in anweisung:
			return "0"
		if "RENAME TO" in anweisung:
			# Der zweite RENAME scheitert — die Transaktion rollt zurueck.
			raise wdh.WiederherstellungsFehler(
				"Die Anweisung an die Datenbank ist fehlgeschlagen "
				"(UniqueViolation: database is being accessed by other users)."
			)
		return ""

	monkeypatch.setattr(wdh.subprocess, "run", _run)
	monkeypatch.setattr(wdh, "_sql", _sql)
	with pytest.raises(wdh.WiederherstellungsFehler):
		wdh.tausche_datenbank("diakronos_wiederherstellung", ziel="diakronos")
	tausch = [eintrag for eintrag in aufrufe if "RENAME TO" in eintrag[0]]
	assert len(tausch) == 1, "mehrere RENAMEs = kein atomarer Tausch"
	anweisung, autocommit = tausch[0]
	assert autocommit is False, "Tausch lief ausserhalb einer Transaktion"
	assert anweisung.count("ALTER DATABASE") == 2
	# KEINE Ruecknahme danach: die Transaktion hat sie ueberfluessig gemacht.
	assert not [eintrag for eintrag in aufrufe
	            if "ALTER DATABASE" in eintrag[0] and "RENAME TO" not in eintrag[0]]


def test_fehlende_zieldatenbank_nennt_den_rueckweg(heim, monkeypatch):
	"""H1: fehlt ``<ziel>``, liegt aber ``<ziel>_vorher_*`` da — Meldung mit Rueckweg."""
	def _sql(env, datenbank, anweisung, *, timeout, autocommit=True):  # noqa: ANN001
		if "pg_stat_activity" in anweisung:
			return "0"
		if "SELECT datname" in anweisung:
			# Ein frueherer Tausch blieb nach dem ERSTEN RENAME stehen.
			return "diakronos_vorher_20261126_120000\npostgres"
		raise AssertionError(f"darf nicht ausgefuehrt werden: {anweisung}")

	monkeypatch.setattr(wdh, "_sql", _sql)
	with pytest.raises(wdh.WiederherstellungsFehler) as fehler:
		wdh.tausche_datenbank("diakronos_wiederherstellung", ziel="diakronos")
	text = str(fehler.value)
	assert "diakronos fehlt" in text
	assert "diakronos_vorher_20261126_120000" in text
	assert 'ALTER DATABASE "diakronos_vorher_20261126_120000" RENAME TO "diakronos"' in text


def test_finde_umleitung_erkennt_die_ausgelagerte_datenbank(monkeypatch):
	zustand = {"da": {"diakronos_vorher_20261126_120000", "postgres"}}

	def _sql(env, datenbank, anweisung, *, timeout, autocommit=True):  # noqa: ANN001
		if "SELECT datname" in anweisung:
			return "\n".join(sorted(zustand["da"]))
		return "0"

	monkeypatch.setattr(wdh, "_sql", _sql)
	assert wdh.finde_umleitung("diakronos") == "diakronos_vorher_20261126_120000"
	zustand["da"] = {"diakronos", "postgres"}
	assert wdh.finde_umleitung("diakronos") is None


def test_offene_verbindung_wird_gemeldet_statt_die_datenbank_zu_zerstoeren(heim,
                                                                          monkeypatch):
	"""Steht die App noch, wird NICHT getauscht."""
	aufrufe: list[str] = []
	vorhanden = ["diakronos", "postgres"]

	def _run(kommando, *, env=None, capture_output=None, text=None, check=None,
	         timeout=None):  # noqa: ANN001
		text_kommando = " ".join(kommando)
		aufrufe.append(os.path.basename(kommando[0]))
		if os.path.basename(kommando[0]) == "psql":
			# Kein ``psql`` im Image: die Abfrage geht ueber den Treiber —
			# hier der Ersatz ``_sql`` (zählt ebenfalls als „psql“-Aufruf).
			raise FileNotFoundError(kommando[0])
		if "pg_stat_activity" in text_kommando:
			return subprocess.CompletedProcess(kommando, 0, stdout="7\n", stderr="")
		if "SELECT datname" in text_kommando:
			# Die Zieldatenbank ist da — der Abbruch kommt aus der Zaehlung.
			return subprocess.CompletedProcess(kommando, 0, stdout="\n".join(vorhanden) + "\n",
			                                  stderr="")
		return subprocess.CompletedProcess(kommando, 0, stdout="", stderr="")

	def _sql(env, datenbank, anweisung, *, timeout, autocommit=True):  # noqa: ANN001
		aufrufe.append("psql")
		if "pg_stat_activity" in anweisung:
			return "7"
		if "SELECT datname" in anweisung:
			return "\n".join(vorhanden)
		return ""

	monkeypatch.setattr(wdh.subprocess, "run", _run)
	monkeypatch.setattr(wdh, "_sql", _sql)
	with pytest.raises(wdh.WiederherstellungsFehler, match="7 Verbindungen"):
		wdh.tausche_datenbank("diakronos_wiederherstellung", ziel="diakronos")
	# Ausser der Zaehlung wurde nichts aufgerufen: kein ALTER. Die Zaehlung
	# wiederholt sich kurz (abklingende Verbindungen), aber es bleibt bei psql.
	assert set(aufrufe) == {"psql"}


def test_unlesbare_sitzungszahl_wird_gemeldet_nicht_geschluckt(monkeypatch):
	"""ABN-2b/L2: eine Pruefung, die nicht stattfindet, wird gesagt."""

	def _run(kommando, *, env=None, capture_output=None, text=None, check=None,
	         timeout=None):  # noqa: ANN001
		return subprocess.CompletedProcess(kommando, 1, stdout="",
		                                   stderr="ERROR: permission denied")

	monkeypatch.setattr(wdh.subprocess, "run", _run)
	with pytest.raises(wdh.WiederherstellungsFehler, match="zaehlen"):
		wdh._pruefe_keine_sitzung({"PGHOST": "db"}, "diakronos", timeout=None)


def test_ohne_psql_geht_der_verwaltungsweg_ueber_den_treiber(heim, monkeypatch):
	"""ABN-2b: das Image hat kein ``psql`` — der Weg darf daran NICHT enden.

	``DROP``/``CREATE``/``ALTER DATABASE`` laufen dann ueber den
	Datenbanktreiber, der fuer die App ohnehin im Image ist. Vorher brach hier
	alles mit „psql ist im Programm nicht vorhanden“ ab — und die Probe im
	Wegwerf-Stack zeigte, dass ``--einspielen`` im Image so gar nicht ging.
	"""
	ordner = _sicherung(heim)
	befehle: list[tuple[str, str]] = []
	todesfaelle: list[str] = []

	def _run(kommando, *, env=None, capture_output=None, text=None, check=None,
	         timeout=None):  # noqa: ANN001 — Signatur von subprocess.run
		if os.path.basename(kommando[0]) == "psql":
			raise FileNotFoundError(kommando[0])
		if os.path.basename(kommando[0]) == "pg_restore" and "--list" in kommando:
			return subprocess.CompletedProcess(kommando, 0, stdout=DUMP_INDEX, stderr="")
		todesfaelle.append("pg_restore")
		return subprocess.CompletedProcess(kommando, 0, stdout="", stderr="")

	def _sql(env, datenbank, anweisung, *, timeout, autocommit=True):  # noqa: ANN001
		befehle.append((datenbank, anweisung))
		if "SELECT datname" in anweisung:
			return "diakronos\npostgres"
		if "pg_stat_activity" in anweisung:
			return "0"
		return ""

	monkeypatch.setattr(wdh.subprocess, "run", _run)
	monkeypatch.setattr(wdh, "pruefe_dump_inhalt",
	                    lambda *a, **k: {"mitglied": 42, "gruppe": 7, "file": 3})
	echt_sql = wdh._sql
	monkeypatch.setattr(wdh, "_sql", _sql)
	neu = wdh.spiele_datenbank_ein(ordner / dump.DUMP_NAME)
	assert neu == "diakronos_wiederherstellung"
	assert ("postgres", 'CREATE DATABASE "diakronos_wiederherstellung"') in befehle
	# Kein DROP an der ZIELDATENBANK — nur die neue wird angelegt.
	assert not [eintrag for eintrag in befehle
	            if "diakronos\"" in eintrag[1] and "DROP" in eintrag[1].upper()]
	assert todesfaelle == ["pg_restore"]


@pytest.mark.parametrize("boese", ["diakronos; DROP TABLE x", 'dia"kronos', "a b"])
def test_brauchbare_bezeichner_nur(boese):
	"""ABN-2b/L1: Namen aus der Konfiguration stehen in SQL — geprueft."""
	with pytest.raises(wdh.WiederherstellungsFehler, match="unbrauchbar"):
		wdh._bezeichner(boese)


def test_bezeichner_pruefung_laesst_normale_namen_durch():
	assert wdh._bezeichner("diakronos_restore_2") == "diakronos_restore_2"


# ── 4. Migration und Umgebung (M4) ─────────────────────────────────────────

def test_migration_meint_dieselbe_datenbank(heim, pg_ersatz, monkeypatch):
	"""ABN-2b/M4: ``alembic`` laeuft gegen die NEUE Datenbank, nicht die alte."""
	version = wdh.migriere_nach(datenbank="diakronos_wiederherstellung")
	assert version == "abn2_head"
	alembic = [aufruf for aufruf in pg_ersatz if "alembic" in " ".join(aufruf[1])]
	assert alembic, "alembic upgrade head wurde nicht aufgerufen"
	assert alembic[0][1][-2:] == ["upgrade", "head"]
	assert alembic[0][2]["DATABASE_URL"].endswith("/diakronos_wiederherstellung")
	# Dieselben Verbindungsdaten wie bei ``pg_restore`` (eine Umgebung).
	pg = [aufruf for aufruf in pg_ersatz if aufruf[0] == "pg_restore"]
	if pg:
		assert alembic[0][2]["PGHOST"] == pg[-1][2]["PGHOST"]
		assert alembic[0][2]["PGUSER"] == pg[-1][2]["PGUSER"]


def test_widerspruch_zwischen_backup_db_name_und_database_url_bricht_ab(
        heim, monkeypatch):
	"""ABN-2b/M4: zwei Quellen, zwei Datenbanken — Abbruch statt Blindflug."""
	import diakronos_app.settings as settings_modul

	monkeypatch.setattr(settings_modul.settings, "backup_db_name", "andere", raising=False)
	monkeypatch.setattr(settings_modul.settings, "database_url",
	                    "postgresql+psycopg://diakronos:geheim@db:5432/diakronos",
	                    raising=False)
	for aufruf in ("spiele_datenbank_ein", "migriere_nach", "tabellenstaende",
	               "alembic_version"):
		with pytest.raises(wdh.WiederherstellungsFehler, match="verschiedene Datenbanken"):
			if aufruf == "spiele_datenbank_ein":
				wdh.spiele_datenbank_ein(Path("/nicht/da.dump"))
			elif aufruf == "migriere_nach":
				wdh.migriere_nach()
			else:
				getattr(wdh, aufruf)()


def test_env_und_url_ergeben_dieselbe_datenbank(heim, monkeypatch):
	"""(M4) Ohne Widerspruch: Name und Rolle aus derselben Quelle."""
	import diakronos_app.settings as settings_modul

	monkeypatch.setattr(settings_modul.settings, "backup_db_name", "", raising=False)
	monkeypatch.setattr(settings_modul.settings, "backup_db_user", "", raising=False)
	monkeypatch.setattr(settings_modul.settings, "database_url",
	                    "postgresql+psycopg://diakronos:geheim@db:5432/diakronos",
	                    raising=False)
	env, name, rolle = wdh._pg_umgebung()
	assert name == "diakronos"
	assert rolle == "diakronos"
	assert env["PGUSER"] == "diakronos"
	assert env["PGPASSWORD"] == "geheim"
	url = wdh._url_fuer(settings_modul.settings.database_url, "diakronos_wiederherstellung")
	assert url == "postgresql+psycopg://diakronos:geheim@db:5432/diakronos_wiederherstellung"


# ── 5. Der ganze Vorgang ───────────────────────────────────────────────────

def test_ohne_einspielen_wird_nichts_geschrieben(heim, pg_ersatz, monkeypatch):
	"""Der bisherige Aufruf bleibt vertraeglich: pruefen, nicht anfassen."""
	ordner = _sicherung(heim)
	monkeypatch.setattr(wdh, "spiele_datenbank_ein",
	                    lambda *a, **k: pytest.fail("darf nicht einspielen"))
	monkeypatch.setattr(wdh, "spiele_dateien_ein",
	                    lambda *a, **k: pytest.fail("darf keine Dateien schreiben"))
	bericht = wdh.stelle_wieder_her(NAME)
	assert bericht.datenbank.soll["mitglied"] == 42
	assert bericht.datenbank.ist == {}
	assert (ordner / dump.DUMP_NAME).is_file()


def _vorsicherung_ersatz(monkeypatch, heim, *, kaputt: bool = False) -> list[dict]:
	"""``lauf.fuehre_aus`` ersetzen: der normale Sicherungslauf, aufgezeichnet."""
	from diakronos_app.sicherung import lauf as laufmodul

	gerufen: list[dict] = []

	def _fuehre_aus(**kwargs):  # noqa: ANN003
		gerufen.append(dict(kwargs))
		if kaputt:
			raise RuntimeError("Sperre nicht erreichbar")
		name = "2026-11-27_030000"
		ziel = heim["sicherungen"] / name
		ziel.mkdir()
		(ziel / dump.FERTIG_NAME).write_bytes(b"")
		return laufmodul.Sicherungsergebnis(
			name=name, status="ok", meldung="", zeitpunkt=datetime.now(),
		)

	monkeypatch.setattr(laufmodul, "fuehre_aus", _fuehre_aus)
	return gerufen


def test_vorsicherung_geht_ueber_den_normalen_sicherungslauf(heim, pg_ersatz, monkeypatch):
	"""ABN-2b/H3: Sperre + Protokollzeile — nicht ``dump.sichere`` am Lauf vorbei."""
	_sicherung(heim)
	gerufen = _vorsicherung_ersatz(monkeypatch, heim)
	monkeypatch.setattr(dump, "sichere",
	                    lambda **k: pytest.fail("Vorsicherung am Lauf vorbei"))
	bericht = wdh.stelle_wieder_her(NAME, einspielen=True)
	assert len(gerufen) == 1
	assert gerufen[0]["ausloeser"] == "manuell"
	assert bericht.datenbank.vorsicherung == "2026-11-27_030000"
	assert bericht.datenbank.vorsicherung_verzeichnis == str(
		heim["sicherungen"] / "2026-11-27_030000"
	)


def test_ohne_vorsicherung_wird_bewusst_nicht_gesichert(heim, pg_ersatz, monkeypatch):
	_sicherung(heim)
	gerufen = _vorsicherung_ersatz(monkeypatch, heim)
	bericht = wdh.stelle_wieder_her(NAME, einspielen=True, vorsicherung=False)
	assert gerufen == []
	assert bericht.datenbank.vorsicherung == ""


def test_gescheiterte_vorsicherung_spielt_nichts_ein(heim, pg_ersatz, monkeypatch):
	"""ABN-2c/L11: der Test prueft den Pfad, den ``stelle_wieder_her`` WIRKLICH ruft.

	Vorher stand hier ``spiele_datenbank_ein`` — ``stelle_wieder_her`` ruft
	aber ``_spiele_in_neue_datenbank``. Die „darf nicht einspielen“-Sicherung
	war damit wirkungslos: ohne die Schutzpruefung in ``stelle_wieder_her``
	waere der Test trotzdem gruen geblieben. Deshalb steht der Waechter jetzt
	an ``_spiele_in_neue_datenbank`` (Mutationsprobe: Schutz entfernen → rot).
	"""
	_sicherung(heim)

	def _nie(*a, **k):  # noqa: ANN002, ANN003
		pytest.fail("darf nicht einspielen")

	monkeypatch.setattr(wdh, "_spiele_in_neue_datenbank", _nie)
	monkeypatch.setattr(wdh, "spiele_datenbank_ein", _nie)
	_vorsicherung_ersatz(monkeypatch, heim, kaputt=True)
	with pytest.raises(wdh.WiederherstellungsFehler, match="Vorsicherung"):
		wdh.stelle_wieder_her(NAME, einspielen=True)


def test_ohne_vorsicherung_warnt_deutlich(heim, pg_ersatz, monkeypatch, capsys):
	"""ABN-2c/M4: ``--ohne-vorsicherung`` steht als WARNUNG in Meldung und Bericht."""
	_sicherung(heim, dateien={"a.txt": b"abc"})
	bericht = wdh.stelle_wieder_her(NAME, einspielen=True, vorsicherung=False)
	assert bericht.datenbank.ohne_vorsicherung is True
	assert any("WARNUNG" in meldung and "Ohne Vorsicherung" in meldung
	           for meldung in bericht.meldungen)
	wdh._drucke_bericht(bericht)
	ausgabe = capsys.readouterr().out
	assert "WARNUNG: OHNE VORSICHERUNG" in ausgabe


def test_vorsicherung_gesetzt_warnt_nicht(heim, pg_ersatz, monkeypatch):
	_sicherung(heim)
	_vorsicherung_ersatz(monkeypatch, heim)
	bericht = wdh.stelle_wieder_her(NAME, einspielen=True)
	assert bericht.datenbank.ohne_vorsicherung is False
	assert not any("Ohne Vorsicherung" in meldung for meldung in bericht.meldungen)


def test_vorhandene_vorher_datenbanken_werden_gemeldet(heim, monkeypatch):
	"""ABN-2c/M6: alte Staende werden aufgelistet und im Bericht genannt."""
	_sicherung(heim, dateien={"a.txt": b"abc"})
	_vorsicherung_ersatz(monkeypatch, heim)
	alte = ["diakronos_vorher_20261001_030000", "diakronos_vorher_20261101_030000"]
	monkeypatch.setattr(wdh, "pruefe_dump_inhalt",
	                    lambda *a, **k: {"mitglied": 42, "gruppe": 7, "file": 3})

	def _sql(env, datenbank, anweisung, *, timeout, autocommit=True):  # noqa: ANN001
		if "SELECT datname FROM pg_database" in anweisung:
			return "\n".join(["diakronos", "postgres", *alte])
		if "pg_stat_activity" in anweisung:
			return "0"
		if "FROM alembic_version" in anweisung:
			return "abn2_head"
		if "pg_catalog.pg_class" in anweisung:
			return "mitglied\ngruppe\nfile"
		if "UNION ALL" in anweisung:
			return "mitglied|42\ngruppe|7\nfile|3"
		return ""

	def _run(kommando, *, env=None, capture_output=None, text=None, check=None,
	         timeout=None):  # noqa: ANN001
		if os.path.basename(kommando[0]) == "psql":
			raise FileNotFoundError(kommando[0])
		if os.path.basename(kommando[0]) == "pg_restore":
			return subprocess.CompletedProcess(kommando, 0, stdout=DUMP_INDEX, stderr="")
		return subprocess.CompletedProcess(kommando, 0, stdout="", stderr="")

	monkeypatch.setattr(wdh, "_sql", _sql)
	monkeypatch.setattr(wdh.subprocess, "run", _run)
	bericht = wdh.stelle_wieder_her(NAME, einspielen=True, dateien=False)
	assert bericht.datenbank.vorher_datenbanken == alte
	assert any(meldung.startswith("2 fruehere Datenbank(en)") and "DROP DATABASE" in meldung
	           for meldung in bericht.meldungen), "der Bericht nennt, wie man sie loescht"


def test_vorher_datenbanken_werden_nur_gelesen(monkeypatch):
	"""M6: das Auflisten loescht nichts — es fragt nur ``pg_database``."""
	aufrufe: list[str] = []

	def _sql(env, datenbank, anweisung, *, timeout, autocommit=True):  # noqa: ANN001
		aufrufe.append(anweisung)
		return "diakronos\ndiakronos_vorher_20261001_030000"

	monkeypatch.setattr(wdh, "_sql", _sql)
	assert wdh._vorher_datenbanken("diakronos") == ["diakronos_vorher_20261001_030000"]
	assert not [a for a in aufrufe if "DROP" in a.upper()]


# ── 5b. Namenslaenge (L9) ──────────────────────────────────────────────────

def test_zu_langer_bezeichner_bricht_ab():
	"""ABN-2c/L9: PostgreSQL kuerzt still — alles ueber 63 Bytes bricht ab."""
	with pytest.raises(wdh.WiederherstellungsFehler, match="zu lang"):
		wdh._bezeichner("a" * 64)


def test_abgeleitete_namen_ueber_63_bytes_brechen_ab(heim, pg_ersatz):
	"""Der gefaehrliche Fall: ``<ziel>_wiederherstellung`` wird gekuerzt.

	Bei einem langen Ziel waere der gekuerzte neue Name GLEICH dem Ziel —
	und ein ``DROP``/``ALTER`` traefe die AKTIVE Datenbank.
	"""
	import diakronos_app.settings as settings_modul

	lang = "d" * 50            # 50 + len("_wiederherstellung") = 69 > 63
	monkeypatch_target = settings_modul.settings
	with pytest.MonkeyPatch.context() as mp:
		mp.setattr(monkeypatch_target, "backup_db_name", lang, raising=False)
		with pytest.raises(wdh.WiederherstellungsFehler, match="zu lang"):
			wdh._neuer_name(lang)
		with pytest.raises(wdh.WiederherstellungsFehler, match="zu lang"):
			wdh._alter_name(lang, "20261126_120000")
	# Vor dem Einspielen bricht es ebenfalls ab (nichts wird angelegt) — der
	# Name inkl. Endung wird geprueft, BEVOR die Datenbank angelegt wird.
	with pytest.raises(wdh.WiederherstellungsFehler, match="zu lang"):
		wdh.spiele_datenbank_ein(Path("/nicht/da.dump"), datenbank=lang)


def test_grenzlaenge_63_geht_noch_durch():
	"""63 Bytes sind erlaubt — genau die Grenze, keine stille Kuerzung."""
	assert wdh._bezeichner("a" * 63) == "a" * 63
	# 41 + len("_vorher_") + len("20261126_120000") = 41 + 8 + 15 = 64 → zu lang
	with pytest.raises(wdh.WiederherstellungsFehler, match="zu lang"):
		wdh._alter_name("d" * 41, "20261126_120000")
	# 40 Zeichen sind genau die Grenze (40 + 8 + 15 = 63).
	wdh._alter_name("d" * 40, "20261126_120000")


def test_voller_lauf_berichtet_soll_und_ist(heim, pg_ersatz, monkeypatch):
	_sicherung(heim, dateien={"foto.png": b"abc"})
	_vorsicherung_ersatz(monkeypatch, heim)
	bericht = wdh.stelle_wieder_her(
		NAME, einspielen=True, vorsicherung=False, wiederholen=True,
	)
	assert bericht.datenbank.soll == {"mitglied": 42, "gruppe": 7, "file": 3}
	assert bericht.datenbank.ist == {"mitglied": 42, "gruppe": 7, "file": 3}
	assert bericht.datenbank.abweichungen == {}
	assert bericht.dateien.dateien == 1
	assert bericht.datenbank.alembic_nachher == "abn2_head"
	assert bericht.datenbank.getauscht is True
	assert bericht.datenbank.eingespielt_in == "diakronos_wiederherstellung"
	assert bericht.datenbank.alte_datenbank.startswith("diakronos_vorher_")


def test_abweichung_bricht_vor_dem_tausch_ab(heim, pg_ersatz, monkeypatch):
	"""ABN-2c/M3: weicht eine Zeilenzahl ab, wird NICHT getauscht.

	Vorher lief ``--einspielen`` durch und meldete die Abweichung erst DANACH
	(mit Exit 1) — die abweichende Datenbank war da schon aktiv. Jetzt bricht
	der Vorgang VOR dem Tausch ab; die alte Datenbank bleibt aktiv.
	"""
	_sicherung(heim)
	monkeypatch.setattr(wdh, "tabellenstaende",
	                    lambda **k: {"mitglied": 41, "gruppe": 7, "file": 3})
	with pytest.raises(wdh.WiederherstellungsFehler, match="ABBRUCH VOR DEM TAUSCH"):
		wdh.stelle_wieder_her(NAME, einspielen=True, vorsicherung=False)
	# Kein ALTER DATABASE — der Tausch hat nie stattgefunden.
	assert not [eintrag for eintrag in pg_ersatz
	            if "ALTER DATABASE" in " ".join(eintrag[1])]


def test_leeres_alembic_nachher_bricht_vor_dem_tausch_ab(heim, pg_ersatz, monkeypatch):
	"""ABN-2c/M3: keine belegte Schemaversion → kein Tausch."""
	_sicherung(heim)
	monkeypatch.setattr(wdh, "alembic_version", lambda **k: "")
	with pytest.raises(wdh.WiederherstellungsFehler, match="alembic_version"):
		wdh.stelle_wieder_her(NAME, einspielen=True, vorsicherung=False)
	assert not [eintrag for eintrag in pg_ersatz
	            if "ALTER DATABASE" in " ".join(eintrag[1])]


def test_cli_meldet_abbruch_vor_dem_tausch_mit_exit_1(heim, pg_ersatz, monkeypatch, capsys):
	_sicherung(heim)
	monkeypatch.setattr(wdh, "tabellenstaende",
	                    lambda **k: {"mitglied": 41, "gruppe": 7, "file": 3})
	code = wdh.main([NAME, "--einspielen", "--ohne-vorsicherung"])
	assert code == 1
	fehler = capsys.readouterr().err
	assert "ABBRUCH VOR DEM TAUSCH" in fehler and "mitglied" in fehler
	# Der Bericht nennt klar, dass die abweichende Datenbank NICHT aktiv wurde.
	assert "wurde NICHT aktiviert" in fehler


def test_cli_pruefen_allein_spielt_nichts_ein(heim, pg_ersatz, monkeypatch, capsys):
	_sicherung(heim)
	monkeypatch.setattr(wdh, "spiele_datenbank_ein",
	                    lambda *a, **k: pytest.fail("darf nicht einspielen"))
	assert wdh.main([NAME]) == 0
	assert wdh.main([NAME, "--pruefen"]) == 0
	assert "NICHT eingespielt" in capsys.readouterr().out


def test_cli_unbekannte_sicherung_exit_1(heim, pg_ersatz, capsys):
	assert wdh.main(["2026-01-01_000000", "--einspielen"]) == 1
	assert "liegt nicht im Sicherungsverzeichnis" in capsys.readouterr().err


def test_cli_ungueltiger_name_exit_1(heim, pg_ersatz, capsys):
	assert wdh.main(["../etc", "--einspielen"]) == 1
	assert "JJJJ-MM-TT_HHMMSS" in capsys.readouterr().err


def test_juengste_sicherung_wird_gewaehlt(heim, pg_ersatz, capsys):
	_sicherung(heim, name="2026-11-20_030000")
	_sicherung(heim, name="2026-11-26_030000")
	# Eine unvollstaendige juengere Sicherung zaehlt NICHT.
	unvoll = _sicherung(heim, name="2026-11-27_030000")
	(unvoll / dump.FERTIG_NAME).unlink()
	assert wdh.main([]) == 0
	ausgabe = capsys.readouterr().out
	assert "Juengste Sicherung: 2026-11-26_030000" in ausgabe


def test_cli_dateien_einspielen_laesst_die_datenbank_in_ruhe(heim, pg_ersatz, monkeypatch,
                                                            capsys):
	"""Der belegte Betriebsweg: Datenbank im db-Dienst, Dateien hier."""
	_sicherung(heim, dateien={"protokoll.pdf": b"%PDF-1.4-test"})
	monkeypatch.setattr(wdh, "spiele_datenbank_ein",
	                    lambda *a, **k: pytest.fail("darf die Datenbank nicht anfassen"))
	assert wdh.main([NAME, "--dateien-einspielen"]) == 0
	assert (heim["files"] / "protokoll.pdf").read_bytes() == b"%PDF-1.4-test"
	assert "Die Datenbank ist unberuehrt" in capsys.readouterr().out


def test_cli_meldet_beide_schalter_als_aufruffehler(heim, capsys):
	assert wdh.main([NAME, "--einspielen", "--dateien-einspielen"]) == 2
	assert "schliessen sich aus" in capsys.readouterr().err


def test_cli_zeitplan_zeigt_den_handweg_auf_wunsch(heim, monkeypatch, capsys):
	"""Der Handweg im db-Dienst ist Nachweis, nicht Bedingung (ABN-2b)."""
	assert wdh.main([NAME, "--zeitplan"]) == 0
	ausgabe = capsys.readouterr().out
	assert "im db-Dienst des Stacks" in ausgabe
	assert "pg_restore" in ausgabe and "--single-transaction" in ausgabe
	# ABN-2b/M5: die Zeilenfortsetzung ist EIN Backslash, nicht zwei.
	assert "\\\\" not in ausgabe
	assert " \\\n" in ausgabe
	# Der Handweg spielt ebenfalls in eine NEUE Datenbank und tauscht danach.
	assert "diakronos_wiederherstellung" in ausgabe
	assert "--tausch" in ausgabe


def test_zeitplan_nennt_konfigurierte_namen(heim, monkeypatch, capsys):
	"""ABN-2b/M5: Datenbank und Benutzer aus der Konfiguration, nicht fest."""
	import diakronos_app.settings as settings_modul

	monkeypatch.setattr(settings_modul.settings, "backup_db_name", "gemeinde_db",
	                    raising=False)
	monkeypatch.setattr(settings_modul.settings, "backup_db_user", "dienst",
	                    raising=False)
	wdh._drucke_zeitplan(wdh.Wiederherstellungsbericht(sicherung=NAME))
	ausgabe = capsys.readouterr().out
	assert "-U dienst" in ausgabe
	assert "gemeinde_db_wiederherstellung" in ausgabe
	assert "-U diakronos" not in ausgabe


def test_liste_zeigt_lokale_sicherungen(heim, capsys):
	_sicherung(heim, name="2026-11-20_030000")
	assert wdh.main(["--liste"]) == 0
	assert "2026-11-20_030000" in capsys.readouterr().out


# ── 6. Protokollzeile (M1) und Zeitzone (ABN-2c/H2) ────────────────────────

def test_stichtag_ist_naive_ortszeit(monkeypatch):
	"""ABN-2c/H2: der Stichtag ist NAIV und kommt aus ``jetzt_ortszeit``.

	``begonnen_am`` der Sicherungslaeufe ist naive Ortszeit
	(``einstellungen.jetzt_ortszeit``, ``calendar_timezone``). Ein
	tz-behafteter Stichtag warf beim Vergleich einen TypeError.
	"""
	from diakronos_app.sicherung import einstellungen as sicherung_einstellungen

	ortszeit = datetime(2026, 11, 26, 22, 30, 15)
	monkeypatch.setattr(sicherung_einstellungen, "jetzt_ortszeit", lambda: ortszeit)
	stichtag = wdh._jetzt_ortszeit_naiv()
	assert stichtag.tzinfo is None, "Stichtag mit Zone — Vergleich wirft TypeError"
	assert stichtag == ortszeit


def test_stichtag_ohne_naht_ist_trotzdem_naiv(monkeypatch):
	"""Faellt ``jetzt_ortszeit`` aus, bleibt der Wert trotzdem naiv."""
	from diakronos_app.sicherung import einstellungen as sicherung_einstellungen

	def _kaputt():
		raise RuntimeError("kein Einstellungsdienst")

	monkeypatch.setattr(sicherung_einstellungen, "jetzt_ortszeit", _kaputt)
	stichtag = wdh._jetzt_ortszeit_naiv()
	assert stichtag.tzinfo is None


def test_stichtag_aus_dem_bericht_bleibt_naiv():
	"""``_stichtag`` liefert auch fuer einen tz-behafteten Zeitpunkt naiv."""
	naiv = wdh._stichtag(wdh.Wiederherstellungsbericht(zeitpunkt="2026-11-26T22:30:15"))
	assert naiv is not None and naiv.tzinfo is None
	assert naiv == datetime(2026, 11, 26, 22, 30, 15)
	mit_zone = wdh._stichtag(
		wdh.Wiederherstellungsbericht(zeitpunkt="2026-11-26T22:30:15+01:00"))
	assert mit_zone is not None and mit_zone.tzinfo is None
	assert mit_zone == datetime(2026, 11, 26, 22, 30, 15)


def test_frueherer_tz_stichtag_warf_typeerror(patched_db, heim, monkeypatch):
	"""Der FRUEHERE Pfad (vor H2) — und dass er jetzt nicht mehr greift.

	Mit einem tz-behafteten Stichtag warf der Vergleich
	``begonnen_am >= nicht_ab_vor`` (naiv gegen tz-behaftet) einen TypeError.
	Der wurde in ``_stelle_anzeige_wieder_her`` geschluckt (`except Exception`)
	— und mit ihm das ``commit``: auch der ``ok``-Eintrag der eingespielten
	Sicherung ging verloren. Hier wird beides gezeigt: der alte Wert scheitert
	weiss, der neue kommt durch und der ``ok``-Eintrag steht in der Datenbank.
	"""
	from diakronos_app.models.sicherung import STATUS_LAEUFT, STATUS_OK, Sicherungslauf
	from diakronos_app.sicherung import sperre

	jetzt_naiv = datetime(2026, 11, 26, 22, 30, 15)
	mit_zone = jetzt_naiv.replace(tzinfo=datetime.now().astimezone().tzinfo)
	sitzung = patched_db()
	try:
		sitzung.add(Sicherungslauf(name=NAME, begonnen_am=jetzt_naiv - timedelta(hours=2),
		                           status=STATUS_LAEUFT))
		sitzung.add(Sicherungslauf(name="2026-11-26_223001", begonnen_am=jetzt_naiv,
		                           status=STATUS_LAEUFT))
		sitzung.commit()
		# (a) Der ALTE Weg: tz-behaftet gegen naiv — genau der TypeError.
		with pytest.raises(TypeError):
			sperre.raeume_abgebrochene_auf(sitzung, nicht_ab_vor=mit_zone,
			                               abschliessen=(NAME,))
		# (b) Der neue Weg: naiv gegen naiv — und das ``ok`` landet wirklich.
		betroffen = sperre.raeume_abgebrochene_auf(sitzung, nicht_ab_vor=jetzt_naiv,
		                                           abschliessen=(NAME,))
		assert betroffen == [NAME]
		assert sitzung.get(Sicherungslauf, NAME).status == STATUS_OK
		assert sitzung.get(Sicherungslauf, "2026-11-26_223001").status == STATUS_LAEUFT
	finally:
		sitzung.close()


def test_abgebrochene_laeufe_markiert_nichts_junges(patched_db, heim):
	"""ABN-2b/M1: ein Lauf NACH dem Stichtag bleibt ``laeuft``."""
	from diakronos_app.models.sicherung import STATUS_LAEUFT, STATUS_FEHLGESCHLAGEN, \
		STATUS_OK, Sicherungslauf
	from diakronos_app.sicherung import sperre

	jetzt = datetime(2026, 11, 26, 15, 0, 0)
	sitzung = patched_db()
	try:
		sitzung.add(Sicherungslauf(name="2026-11-26_030000", begonnen_am=jetzt - timedelta(days=1),
		                           status=STATUS_LAEUFT))
		# Die Vorsicherung, die DIESER Vorgang gerade gestartet hat.
		sitzung.add(Sicherungslauf(name="2026-11-26_150001", begonnen_am=jetzt,
		                           status=STATUS_LAEUFT))
		sitzung.commit()
		betroffen = sperre.raeume_abgebrochene_auf(sitzung, jetzt=jetzt,
		                                           nicht_ab_vor=jetzt)
		assert betroffen == ["2026-11-26_030000"]
		laufend = sitzung.get(Sicherungslauf, "2026-11-26_150001")
		assert laufend.status == STATUS_LAEUFT
		assert laufend.beendet_am is None
		alt = sitzung.get(Sicherungslauf, "2026-11-26_030000")
		assert alt.status == STATUS_FEHLGESCHLAGEN
	finally:
		sitzung.close()


def test_eingespielte_sicherung_gilt_als_erledigt(patched_db, heim):
	"""Die Sicherung aus dem Dump traegt ihre Zeile im Zustand ``laeuft``."""
	from diakronos_app.models.sicherung import STATUS_LAEUFT, STATUS_OK, Sicherungslauf
	from diakronos_app.sicherung import sperre

	jetzt = datetime(2026, 11, 26, 15, 0, 0)
	sitzung = patched_db()
	try:
		sitzung.add(Sicherungslauf(name=NAME, begonnen_am=jetzt - timedelta(hours=2),
		                           status=STATUS_LAEUFT))
		sitzung.commit()
		sperre.raeume_abgebrochene_auf(sitzung, jetzt=jetzt, abschliessen=(NAME,))
		zeile = sitzung.get(Sicherungslauf, NAME)
		assert zeile.status == STATUS_OK
		assert "eingespielt" in zeile.meldung
	finally:
		sitzung.close()


def test_fertig_markierung_gilt_weiterhin_als_ok(patched_db, heim):
	"""Das alte Verhalten bleibt: ``FERTIG`` im Ordner → ``ok`` (kein Testverlust)."""
	from diakronos_app.models.sicherung import STATUS_LAEUFT, STATUS_OK, Sicherungslauf
	from diakronos_app.sicherung import sperre

	ordner = heim["sicherungen"] / NAME
	ordner.mkdir(parents=True)
	(ordner / dump.FERTIG_NAME).write_bytes(b"")
	jetzt = datetime(2026, 11, 26, 15, 0, 0)
	sitzung = patched_db()
	try:
		sitzung.add(Sicherungslauf(name=NAME, begonnen_am=jetzt - timedelta(days=1),
		                           status=STATUS_LAEUFT))
		sitzung.commit()
		sperre.raeume_abgebrochene_auf(sitzung, jetzt=jetzt, nicht_ab_vor=jetzt)
		assert sitzung.get(Sicherungslauf, NAME).status == STATUS_OK
	finally:
		sitzung.close()


# ── 7. Hilfsfunktionen ─────────────────────────────────────────────────────

def test_signatur_pruefsumme_bleibt_kompatibel(heim):
	"""Die Pruefsummendatei ist dieselbe wie beim Sichern (sha256sum-Format)."""
	ordner = _sicherung(heim)
	text = (ordner / dump.PRUEFSUMMEN_NAME).read_text(encoding="utf-8")
	for name in (dump.DUMP_NAME, dump.ARCHIV_NAME):
		summe = hashlib.sha256((ordner / name).read_bytes()).hexdigest()
		assert f"{summe}  {name}" in text


def test_menschengroesse():
	assert wdh._menschengroesse(512) == "512 Bytes"
	assert wdh._menschengroesse(2048) == "2.0 KiB"


def test_treiberweg_liefert_die_erste_spalte(monkeypatch):
	"""ABN-2b (im Stack gefunden): ``_sql`` gab fuer JEDES SELECT ``""`` zurueck.

	Dann meldete ``_pruefe_keine_sitzung`` „nicht zaehlbar“ und der Tausch
	gelang nie — obwohl die Datenbank offen war. Ein ``psycopg``-Ersatz belegt:
	die erste Spalte jeder Zeile kommt an, Anweisungen ohne Ergebnismenge
	liefern ``""``.
	"""
	import sys
	import types


	class _Cursor:
		def __init__(self):
			self.description = None
			self._zeilen: list[tuple] = []

		def __enter__(self):
			return self

		def __exit__(self, *_exc):
			return False

		def execute(self, anweisung):  # noqa: ANN001
			if anweisung.strip().upper().startswith("SELECT"):
				self.description = [("x",)]
				self._zeilen = [("0",), ("7",)]
			else:
				self.description = None
				self._zeilen = []

		def fetchall(self):
			return list(self._zeilen)


	class _Verbindung:
		def __enter__(self):
			return self

		def __exit__(self, *_exc):
			return False

		def cursor(self):
			return _Cursor()


	class _Psycopg(types.SimpleNamespace):
		Error = Exception

		def __init__(self):
			super().__init__()
			self.aufrufe: list[dict] = []

		def connect(self, **kwargs):  # noqa: ANN003 — M5: nur Schluesselwort-Argumente
			self.aufrufe.append(kwargs)
			return _Verbindung()


	ersatz = _Psycopg()
	monkeypatch.setitem(sys.modules, "psycopg", ersatz)
	env = {"PGHOST": "db", "PGPORT": "5432", "PGUSER": "diakronos",
	       # Passwort mit Leerzeichen UND Anfuehrungszeichen: als DSN waere das
	       # zerlegt worden (ABN-2c/M5).
	       "PGPASSWORD": 'ge heim"wort'}
	# ``psql -t -A``: je Zeile die erste Spalte, eine Zeile je Zeile.
	assert wdh._sql(env, "postgres", "SELECT x", timeout=None) == "0\n7"
	# Ohne Ergebnismenge (DROP/CREATE/ALTER): leer, kein Fehler.
	assert wdh._sql(env, "postgres", 'CREATE DATABASE "x"', timeout=None) == ""
	# M5: die Verbindungsdaten gehen als Schluesselwort-Argumente raus, das
	# Passwort kommt UNVERAENDERT an, der Port ist eine Zahl.
	assert ersatz.aufrufe[0]["host"] == "db"
	assert ersatz.aufrufe[0]["port"] == 5432
	assert isinstance(ersatz.aufrufe[0]["port"], int)
	assert ersatz.aufrufe[0]["user"] == "diakronos"
	assert ersatz.aufrufe[0]["dbname"] == "postgres"
	assert ersatz.aufrufe[0]["password"] == 'ge heim"wort'
	assert ersatz.aufrufe[0]["autocommit"] is True
	# Ohne ``timeout`` keine Zeitgrenze gesetzt; mit ``timeout`` gilt sie fuer die
	# ANWEISUNG (statement_timeout, in Millisekunden) — nicht nur fuer den Aufbau.
	assert "options" not in ersatz.aufrufe[0]
	wdh._sql(env, "postgres", "SELECT x", timeout=30)
	assert ersatz.aufrufe[-1]["options"] == "-c statement_timeout=30000"
	# ``autocommit=False`` (H1) kommt ebenfalls durch.
	wdh._sql(env, "postgres", "SELECT x", timeout=None, autocommit=False)
	assert ersatz.aufrufe[-1]["autocommit"] is False


def test_treiberweg_meldet_unbrauchbaren_port(monkeypatch):
	"""M5: ein Port, der keine Zahl ist, wird gemeldet statt geraten."""
	import sys
	import types

	monkeypatch.setitem(sys.modules, "psycopg",
	                    types.SimpleNamespace(Error=Exception,
	                                          connect=lambda **k: None))  # noqa: ARG005
	with pytest.raises(wdh.WiederherstellungsFehler, match="Port"):
		wdh._sql({"PGHOST": "db", "PGPORT": "abc"}, "postgres", "SELECT 1", timeout=None)

# ── 8. Doku 14.4 und Code im Einklang (ABN-2c/M7) ───────────────────────────

def _betriebsanleitung() -> str | None:
	"""``docs/BETRIEBSANLEITUNG.md`` — im Image nicht vorhanden (dann Skip)."""
	from pathlib import Path as _Pd

	# backend/tests/ -> zwei Ebenen hoch ist die Repo-Wurzel.
	pfad = _Pd(__file__).resolve().parents[2] / "docs" / "BETRIEBSANLEITUNG.md"
	return pfad.read_text(encoding="utf-8") if pfad.is_file() else None


def test_doku_14_4_nennt_einspielen_als_normalweg():
	"""ABN-2c/M7: ``--einspielen`` ist der Normalfall — ``psql`` nicht noetig.

	Der alte Text erklaerte den Handweg im db-Dienst fuer „den belegten Weg“,
	weil ``psql`` im Image fehle. Das ist mit dem Treiberweg falsch.
	"""
	inhalt = _betriebsanleitung()
	if inhalt is None:
		pytest.skip("docs/ liegt nicht im Image (Frontend-Bau prueft es)")
	abschnitt = inhalt.split("### 14.4", 1)[1].split("\n## 15.", 1)[0]
	assert "--einspielen" in abschnitt
	assert "5a" in abschnitt and "Normalfall" in abschnitt
	# Die alte Falschaussage darf nicht zurueckkommen.
	assert "psql` muss im Image vorhanden sein" not in abschnitt
	assert "psql ist im Programm nicht vorhanden" not in abschnitt
	# Der Ablauf nennt Vorsicherung VOR dem Anhalten (Schritt 2 vor Schritt 3).
	assert "Vor Schritt 3" in abschnitt
	# ``--dateien-einspielen`` migriert nicht — muss so dastehen.
	assert "migriert nicht" in abschnitt


def test_doku_14_4_hat_eine_pruefstufe_vor_dem_tausch():
	"""Handweg: erst zaehlen/pruefen, dann tauschen (M7)."""
	inhalt = _betriebsanleitung()
	if inhalt is None:
		pytest.skip("docs/ liegt nicht im Image (Frontend-Bau prueft es)")
	abschnitt = inhalt.split("### 14.4", 1)[1].split("\n## 15.", 1)[0]
	assert "zaehlen und prüfen" in abschnitt or "zählen und prüfen" in abschnitt
	assert "einer** Transaktion" in abschnitt


def test_zeitplan_druckt_den_stempel_mit_doppelten_anfuehrungszeichen(capsys):
	"""ABN-2c/L8: ``$(date …)`` in einfachen Anfuehrungszeichen wird nicht expandiert."""
	wdh._drucke_zeitplan(wdh.Wiederherstellungsbericht(sicherung=NAME))
	ausgabe = capsys.readouterr().out
	notausgang = [z for z in ausgabe.splitlines() if "vorher_$(date" in z]
	assert notausgang, "der Notausgang fehlt"
	for zeile in notausgang:
		assert "-c '" not in zeile, "einfache Anfuehrungszeichen: $(date) bleibt Literal"
		assert '\"-c \"' in zeile or '-c "' in zeile
	# Die Zaehlstufe steht vor dem Tausch.
	assert ausgabe.index("SELECT count(*) FROM mitglied") < ausgabe.index("--tausch")


def test_zeitplan_nennt_nicht_mehr_migrationen_bei_den_dateien(capsys):
	"""M7: ``--dateien-einspielen`` migriert nicht — der Zeitplan sagt das."""
	wdh._drucke_zeitplan(wdh.Wiederherstellungsbericht(sicherung=NAME))
	ausgabe = capsys.readouterr().out
	assert "--dateien-einspielen" not in ausgabe or "migriert nicht" in ausgabe
