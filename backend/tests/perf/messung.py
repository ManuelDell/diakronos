"""PERF-K3 — Kalender-Startaufrufe LIVE messen (Postgres, Wegwerf-Stack).

Zaehlt je Endpunkt, den `frontend/src/diakonos/pages/Kalender.vue` beim
Seitenaufbau ausloest, die SQL-Abfragen (`before_cursor_execute`) und die
Antwortzeit (Median aus 5 Laeufen) — je Rolle.

Gemessene Reihenfolge (aus Kalender.vue `onMounted` + KronosCalendar):

  1. get_accessible_calendars   (store.fetchAccessibleCalendars)
  2. get_kalender_verwaltung    (kalenderVerwaltungLaden, parallel)
  3. get_current_user_context   (benutzerKontextLaden)
  4. get_moderation_count       (offeneZahlLaden, nur wenn darfPruefen)
  5. get_kanban_board_data      (pruefIdsLaden, Prüf-Spalte)
  6. get_calendar_events        (Raster-Feed, KronosCalendar eventSources)

Rollen: Admin (System Manager), HV einer Gruppe, MV, normales Mitglied,
Mitglied einer FREMDEN Gruppe, Konto ohne Mitgliedschaft.

Je Messung wird EIN `merkungsrahmen` geoeffnet (das tut im Betrieb
`RequestContextMiddleware` je Request) — sonst waere die Zahl geschoent.

Aufruf im Container:

    python /app/tests/perf/messung.py [--json PFAD] [--laeufe N]

Das Skript ist KEIN pytest-Test (kein `test_`-Praefix); der Marker `perf`
in `test_perf_k3_waechter.py` haelt es aus der normalen Suite heraus.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import sys
import time
import traceback

os.environ.setdefault("DIAKRONOS_TEST_MODUS", "1")

# ── SQL-Zaehler ────────────────────────────────────────────────────────────
_AKTIV = {"an": False}
_ZEILEN: list[dict] = []


def _zaehle(conn, cursor, statement, parameters, context, executemany):
	if not _AKTIV["an"]:
		return
	_ZEILEN.append({
		"sql": " ".join(statement.split()),
		"params": str(parameters)[:200],
		# Herkunft wird HIER bestimmt: nur während der Ausführung steht der
		# Stack der aufrufenden Stelle (Modell/Helper/Endpunkt) zur Verfügung.
		"herkunft": _herkunft(),
	})


def _normalisiere(sql: str) -> str:
	"""Abfrage-Vorlage ohne Werte (Gruppierung der Wiederholer)."""
	t = re.sub(r"'[^']*'", "?", sql)
	t = re.sub(r"\b\d+(\.\d+)?\b", "?", t)
	# IN-Listen zu EINEM Platzhalter zusammenfassen: sonst zerfaellt
	# `IN (?, ?, ?)` je nach Kalenderzahl in eigene Vorlagen.
	t = re.sub(r"\?(\s*,\s*\?)+", "?", t)
	return " ".join(t.split())[:220]


def _herkunft() -> str:
	"""Stack-Auszug bis in `diakronos_app` (ohne Framework-Rauschen)."""
	frames = []
	for fr in traceback.extract_stack()[:-2]:
		pfad = fr.filename or ""
		if "diakronos_app" not in pfad:
			continue
		frames.append(f"{os.path.basename(pfad)}:{fr.lineno}:{fr.name}")
		if len(frames) >= 4:
			break
	return " <- ".join(frames)


def _top(zeilen: list[dict], n: int = 10) -> list[dict]:
	zaehlung: dict[str, int] = {}
	beispiel: dict[str, str] = {}
	herkunft: dict[str, dict[str, int]] = {}
	for z in zeilen:
		k = _normalisiere(z["sql"])
		zaehlung[k] = zaehlung.get(k, 0) + 1
		beispiel.setdefault(k, z["sql"][:300])
		h = z.get("herkunft") or "?"
		herkunft.setdefault(k, {})
		herkunft[k][h] = herkunft[k].get(h, 0) + 1
	raus = []
	for k, v in sorted(zaehlung.items(), key=lambda kv: -kv[1])[:n]:
		top_h = sorted(herkunft[k].items(), key=lambda kv: -kv[1])[:2]
		raus.append({
			"anzahl": v,
			"vorlage": k,
			"beispiel": beispiel[k],
			"herkunft": [[h, c] for h, c in top_h],
		})
	return raus


# ── Messung eines Endpunkts ────────────────────────────────────────────────
def _messe(fn, *args, **kwargs) -> dict:
	"""Ein Aufruf = EIN Request: eigener Merkungsrahmen, Zaehler an."""
	from diakronos_app.rechte.kern import _MERKER, merkungsrahmen

	_ZEILEN.clear()
	fehler = None
	ergebnis = None
	t0 = time.perf_counter()
	with merkungsrahmen():
		_AKTIV["an"] = True
		try:
			ergebnis = fn(*args, **kwargs)
		except Exception as exc:  # noqa: BLE001 — Fehlerweg wird GEMESSEN
			fehler = f"{type(exc).__name__}: {exc}"
		finally:
			_AKTIV["an"] = False
	dauer = (time.perf_counter() - t0) * 1000.0
	merker = len(_MERKER.get() or {})

	return {
		"ms": dauer,
		"sql": len(_ZEILEN),
		"zeilen": list(_ZEILEN),
		"merker": merker,
		"fehler": fehler,
		"ergebnis": ergebnis,
	}


def _messe_n(fn, *args, laeufe: int = 5, **kwargs) -> dict:
	laeufe_roh = [_messe(fn, *args, **kwargs) for _ in range(laeufe)]
	zeiten = [r["ms"] for r in laeufe_roh]
	letzter = laeufe_roh[-1]
	anfang = laeufe_roh[0]
	return {
		"ms_median": round(statistics.median(zeiten), 1),
		"ms_min": round(min(zeiten), 1),
		"ms_max": round(max(zeiten), 1),
		# Der ERSTE Lauf ist der kalte (Verbindungsaufbau, Plan-Cache);
		# der Median beschreibt den warmen Fall.
		"ms_kalt": round(anfang["ms"], 1),
		"sql": letzter["sql"],
		"sql_kalt": anfang["sql"],
		"merker": letzter["merker"],
		"fehler": letzter["fehler"],
		"vorlagen": _top(letzter["zeilen"]),
		"anzahl_ergebnis": _anzahl(letzter["ergebnis"]),
	}


def _anzahl(erg) -> object:
	if isinstance(erg, list):
		return len(erg)
	if isinstance(erg, dict):
		raus = {}
		for k, v in erg.items():
			if isinstance(v, (list, dict)):
				raus[k] = len(v)
			elif isinstance(v, (int, float, str, bool)) or v is None:
				raus[k] = v
		return raus
	return None


# ── Rollen und Aufrufplan ──────────────────────────────────────────────────
def _endpunkte():
	from diakronos_app.api.kronos.calendar_get import get_calendar_events
	from diakronos_app.api.kronos.kalender_verwaltung import get_kalender_verwaltung
	from diakronos_app.api.kronos.kanban_api import get_kanban_board_data, get_moderation_count
	from diakronos_app.api.kronos.permissions import get_accessible_calendars
	from diakronos_app.api.session import get_current_user_context

	return {
		"get_accessible_calendars": (get_accessible_calendars, (), {}),
		"get_kalender_verwaltung": (get_kalender_verwaltung, (), {}),
		"get_current_user_context": (get_current_user_context, (), {}),
		"get_moderation_count": (get_moderation_count, (), {}),
		"get_kanban_board_data": (get_kanban_board_data, (), {}),
		# Raster-Feed: FullCalendar-Monatsfenster um November 2026.
		"get_calendar_events:view": (get_calendar_events,
		                            ("2026-10-26", "2026-12-06", None, "view"), {}),
	}


def messen(laeufe: int = 5) -> dict:
	from diakronos_app.frappe_compat.session import set_user, testnaht

	from fabrik import ADMIN, FREMD, HV, MITGLIED, MV, OHNE

	rollen = {
		"Admin": ADMIN,
		"HV (Gruppe GR-01)": HV,
		"MV (Gruppe GR-01)": MV,
		"Mitglied (GR-01)": MITGLIED,
		"Mitglied fremde Gruppe (GR-02)": FREMD,
		"Konto ohne Gruppe": OHNE,
	}
	endpunkte = _endpunkte()
	ausgabe = {}
	naht = testnaht()
	naht.__enter__()
	try:
		for rolle, konto in rollen.items():
			set_user(konto)
			je_rolle = {}
			# Die Kalenderliste wird EINMAL je Rolle geholt: der Raster-Feed
			# filtert auf genau diese Namen (wie `selectedCalendars` im Store).
			kalender_liste: list[str] = []
			for name, (fn, args, kwargs) in endpunkte.items():
				a = list(args)
				if name.startswith("get_calendar_events"):
					if not kalender_liste:
						je_rolle[name] = {"uebersprungen": "kein Kalender sichtbar"}
						continue
					a[2] = json.dumps(kalender_liste)
				teil = _messe_n(fn, *a, laeufe=laeufe, **kwargs)
				if name == "get_accessible_calendars":
					# Namen EINMAL direkt holen — `_messe_n` reicht die Rohantwort
					# nicht weiter (sie waere gross), und der Raster-Feed
					# braucht genau diese Namen wie `selectedCalendars`.
					sichtbar = fn()
					if isinstance(sichtbar, list):
						kalender_liste = [str(k.get("name")) for k in sichtbar if k.get("name")]
						teil["anzahl_sichtbar"] = len(kalender_liste)
						teil["namensliste"] = kalender_liste
				je_rolle[name] = teil
			ausgabe[rolle] = {"konto": konto, "endpunkte": je_rolle}
	finally:
		naht.__exit__(None, None, None)
	return ausgabe


def main(argv=None) -> int:
	parser = argparse.ArgumentParser()
	parser.add_argument("--json", default=None)
	parser.add_argument("--laeufe", type=int, default=5)
	args = parser.parse_args(argv)

	from sqlalchemy import event

	import diakronos_app.db as dbmod
	import fabrik

	from sqlalchemy import func, select

	from diakronos_app.models.kronos import Element

	with dbmod.SessionLocal() as sess:
		# Wiederholter Lauf: die Welt steht schon, dann NICHT doppelt anlegen
		# (der Primärschlüssel wurde beim zweiten Lauf sonst zur Kollision).
		vorhanden = sess.scalar(select(func.count()).select_from(Element)) or 0
		if vorhanden >= fabrik.TERMINE:
			kennzahlen = {"vorhanden": True, "termine": vorhanden}
		else:
			kennzahlen = fabrik.aufbauen(sess) | {"vorhanden": False}

	# Abfragen der Fabrik NICHT mitzaehlen: Zaehler erst danach scharf.
	event.listen(dbmod.engine, "before_cursor_execute", _zaehle)

	try:
		from diakronos_app.rechte.kern import _MERKER, merkungsrahmen
	except ImportError:
		raise SystemExit("PERF-K3 braucht den Rechte-Merker (PERF-K1).") from None

	# Rechte-Vorrat NICHT vorwaermen: jede Messung startet mit leerem Merker.
	with merkungsrahmen():
		_MERKER.get().clear()

	daten = {"daten": kennzahlen, "db": dbmod.engine.url.render_as_string(hide_password=True),
	         "laeufe": args.laeufe, "rollen": messen(laeufe=args.laeufe)}

	text = json.dumps(daten, indent=2, ensure_ascii=False)
	if args.json:
		with open(args.json, "w", encoding="utf-8") as fh:
			fh.write(text)
	print(text)
	return 0


if __name__ == "__main__":
	sys.exit(main())
