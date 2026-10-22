"""BACKUP-1b (N5): der Entrypoint weist eine unsichere Sicherungsablage ab.

Der Entrypoint ist das letzte Netz vor dem ersten Schreibzugriff: Docker legt
den Bind-Mount an, und der Dienst bekommt BACKUP_DIR als Ziel. Steht dort
``/`` oder ``/data``, legt der Dump Personendaten in den Wurzelbaum bzw. in
die halbe Datenablage; ist BACKUP_DIR gleich FILES_DIR, raeumt die
Aufbewahrung spaeter die Anhaenge mit weg. Beides ist eine stille
Fehlkonfiguration — hier wird sie laut und frueh abgelehnt.

Geprueft wird das Skript selbst (``sh``), nicht ein Nachbau: die Testzeile ist
genau die Bedingung, die im Container greift. Laeuft nur dort, wo ``sh`` und
``gosu``/``id`` vorhanden sind — im Image also immer.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

ENTRYPOINT = Path(__file__).resolve().parents[1] / "docker-entrypoint.sh"
#: Im Image installiert das Dockerfile das Skript als `/usr/local/bin/
#: diakronos-entrypoint`; `/app/docker-entrypoint.sh` ist dort nicht vorhanden.
#: Geprueft wird also das INSTALLIERTE Skript, wenn das Repo-Skript fehlt.
ENTRYPOINT_INSTALLIERT = Path("/usr/local/bin/diakronos-entrypoint")


def _skript() -> Path:
	return ENTRYPOINT if ENTRYPOINT.is_file() else ENTRYPOINT_INSTALLIERT


def _starte(**umgebung):
	"""[1] Rennt der Entrypoint mit dieser Umgebung los?"""
	basis = {
		"PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
		"HOME": "/tmp",
		# Ohne Migrationen/Startdienst: es geht nur um die Pruefungen.
		"SKIP_MIGRATIONS": "1",
	}
	basis.update(umgebung)
	return subprocess.run(
		["sh", str(_skript()), "true"],
		env=basis, capture_output=True, text=True, timeout=60,
	)


@pytest.mark.parametrize("ziel", ["/", "/data", "/app", "relativ/pfad"])
def test_unsichere_ablage_wird_abgewiesen(ziel):
	ergebnis = _starte(BACKUP_DIR=ziel)
	assert ergebnis.returncode == 1, ergebnis.stdout + ergebnis.stderr
	assert "BACKUP_DIR" in ergebnis.stderr


def test_ablage_gleich_dateiablage_wird_abgewiesen():
	ergebnis = _starte(BACKUP_DIR="/tmp/bk1b-gleich/files", FILES_DIR="/tmp/bk1b-gleich/files/")
	assert ergebnis.returncode == 1
	assert "must not be FILES_DIR" in ergebnis.stderr


# ── N8 (BACKUP-1c): Ablage UNTERHALB der Dateiablage (und umgekehrt) ────────
#
# ``BACKUP_DIR=/data/files/sub`` ist nicht ``/data/files`` — der Guard oben
# greift also nicht. Folge: das Dateiarchiv zieht die frueheren Sicherungen mit
# hinein (jede Sicherung enthaelt alle vorherigen), und die Aufbewahrung
# loescht im schlimmsten Fall Anhaenge. Beides ist eine Fehlkonfiguration.
#
# ``_starte_zur_pruefung`` faehrt nur die Ablage-Pruefungen des Entrypoints:
# sie brechen mit dem Guard-Text ab, brauchen aber kein ``root``, ``appuser``
# oder ``gosu`` (auf dem Entwicklungs-LXC gibt es die nicht; im Image schon).
# Damit prueft der Test die Bedingung selbst, nicht das Vorhandensein eines
# Benutzers. Der Text wird aus dem Skript geschnitten, nicht nachgebaut.

def _pruefblock(pfad: Path) -> str:
	skript = pfad.read_text(encoding="utf-8")
	nach_n8 = skript.split("    # N8 (BACKUP-1c)", 1)[1]
	block = '    # N8 (BACKUP-1c)' + nach_n8.split('    mkdir -p "$files_dir"', 1)[0]
	files_dir = skript.split('    files_dir="', 1)[1].split("\n", 1)[0]
	backup_dir = skript.split('    backup_dir="', 1)[1].split("\n", 1)[0]
	return (
		'set -e\n'
		f'files_dir="{files_dir}\n'
		f'backup_dir="{backup_dir}\n'
		f"{block}"
		'echo VORBEREITUNG_OK\n'
	)


def _starte_zur_pruefung(**umgebung):
	basis = {"PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"), "HOME": "/tmp"}
	basis.update(umgebung)
	return subprocess.run(
		["sh", "-c", _pruefblock(_skript())],
		env=basis, capture_output=True, text=True, timeout=60,
	)


def test_ablage_unterhalb_der_dateiablage_wird_abgewiesen():
	ergebnis = _starte_zur_pruefung(BACKUP_DIR="/data/files/sub", FILES_DIR="/data/files")
	assert ergebnis.returncode == 1, ergebnis.stdout + ergebnis.stderr
	assert "must not be inside FILES_DIR" in ergebnis.stderr


def test_dateiablage_unterhalb_der_ablage_wird_abgewiesen():
	ergebnis = _starte_zur_pruefung(BACKUP_DIR="/data/sicherungen", FILES_DIR="/data/sicherungen/files")
	assert ergebnis.returncode == 1, ergebnis.stdout + ergebnis.stderr
	assert "must not be inside BACKUP_DIR" in ergebnis.stderr


def test_geschwisterordner_laufen_durch():
	"""``/data/sicherungen`` und ``/data/files`` liegen NEBENeinander — Betrieb."""
	ergebnis = _starte_zur_pruefung(BACKUP_DIR="/data/sicherungen/", FILES_DIR="/data/files")
	assert ergebnis.returncode == 0, ergebnis.stderr
	assert "VORBEREITUNG_OK" in ergebnis.stdout


def test_aehnlicher_name_ist_kein_unterordner():
	"""``/data/files2`` liegt NICHT unterhalb von ``/data/files``."""
	ergebnis = _starte_zur_pruefung(BACKUP_DIR="/data/files2", FILES_DIR="/data/files")
	assert ergebnis.returncode == 0, ergebnis.stderr
	assert "VORBEREITUNG_OK" in ergebnis.stdout


def test_betriebswerte_laufen_durch():
	"""/data/sicherungen + /data/files ist die Betriebskonfiguration (Karte)."""
	ergebnis = _starte_zur_pruefung(BACKUP_DIR="/data/sicherungen", FILES_DIR="/data/files")
	assert ergebnis.returncode == 0, ergebnis.stderr
	assert "VORBEREITUNG_OK" in ergebnis.stdout


def test_gleichheit_trotz_schraegstrich_wird_abgewiesen():
	"""``/x/sicherungen/`` und ``/x/sicherungen`` sind dasselbe Verzeichnis."""
	ergebnis = _starte_zur_pruefung(BACKUP_DIR="/data/sicherungen/", FILES_DIR="/data/sicherungen")
	assert ergebnis.returncode == 1
	assert "must not be FILES_DIR" in ergebnis.stderr


def test_eigene_ablage_unter_dem_datenbaum_ist_erlaubt(tmp_path):
	"""``/data/sicherungen`` neben ``/data/files`` ist der Betriebsfall."""
	import shutil

	if shutil.which("gosu") is None or not Path("/usr/local/bin/diakronos-entrypoint").is_file():
		# Auf dem Entwicklungs-LXC fehlen ``appuser`` und ``gosu`` — die volle
		# Stufe laeuft nur im Image (dort ist sie die eigentliche Abnahme).
		pytest.skip("voller Entrypoint (chown/gosu) nur im Image")
	ergebnis = _starte(BACKUP_DIR=str(tmp_path / "sicherungen"),
	                   FILES_DIR=str(tmp_path / "files"))
	assert (tmp_path / "sicherungen").is_dir(), ergebnis.stdout + ergebnis.stderr
