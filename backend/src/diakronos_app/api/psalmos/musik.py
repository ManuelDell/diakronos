"""Psalmos Musikdatenbank — Lieder, Fassungen, Liedgruppen (P4i).

Original (READ-ONLY):
  referenz/diakronos-frappe/diakronos/psalmos/api/musik.py
Originalpfad der SPA: ``diakronos.psalmos.api.musik.*`` (hooks.py:150-157,
Aufrufliste des Frappe-Frontends). Der Originalpfad entsteht ueber die Konstante
`FRAPPE_MODULE`; ohne sie waeren alle Endpunkte fuer die SPA 404.

Endpunkte (8):
  get_lieder, get_lied_detail, get_fassungen, save_lied, save_fassung,
  get_lied_historie, get_liedgruppen, get_liedgruppe_detail

Berechtigungen (1:1 aus dem Original):
  - Lesen:  jedes eingeloggte Mitglied (kein Guest) — `allow_guest=False`
            plus `_require_login()`.
  - Schreiben: Verantwortlicher des Dienstbereichs "Musik und Worship"
            (oder einer seiner Gruppen) ODER Rolle Mitgliederadministrator /
            System Manager.
"""

from __future__ import annotations

FRAPPE_MODULE = "diakronos.psalmos.api.musik"

import json as _json
import unicodedata
from typing import Any

from diakronos_app.frappe_compat import api_helpers as _sh
from diakronos_app.frappe_compat import whitelist
from diakronos_app.frappe_compat.exceptions import DoesNotExistError, PermissionError, throw
from diakronos_app.frappe_compat.query import get_all, get_doc, get_value
from diakronos_app.frappe_compat.session import session

# ── Berechtigungen ──────────────────────────────────────────────────────────

ADMIN_ROLES = ["System Manager", "Mitgliederadministrator"]
MUSIK_DIENSTBEREICH = "Musik und Worship"


def _require_login() -> str:
	"""Wirft PermissionError, falls nicht angemeldet (Guest)."""
	user = session.user
	if user == "Guest":
		throw("Anmeldung erforderlich.", PermissionError)
	return user


def _is_admin(user: str) -> bool:
	from diakronos_app.frappe_compat.permissions import get_roles

	return any(r in ADMIN_ROLES for r in get_roles(user))


def _is_musikverantwortlicher(user: str) -> bool:
	"""Schreibrecht auf die Musikdatenbank.

	Eine globale User->Dienstrolle-Zuordnung gibt es in Diakronos nicht.
	Massgeblich ist deshalb die bestehende Hierarchie: wer Verantwortlicher
	des Dienstbereichs "Musik und Worship" oder einer seiner Gruppen ist,
	pflegt auch das Repertoire.

	Bewusst NICHT ueber "Dienstplan Mitwirkender": eine Mitwirkung in einem
	einzelnen Plan darf kein globales Schreibrecht auf alle Lieder ergeben.
	"""
	if _sh._count(
		"Dienstbereich Verantwortlicher",
		{"user": user, "parent": MUSIK_DIENSTBEREICH},
	):
		return True

	# Original: JOIN `tabGruppe` g ON g.name = gv.parent WHERE g.dienstbereich = %s.
	# Portierung: erst die Gruppen des Bereichs holen, dann die Verantwortlichen
	# dieser Gruppen pruefen — kein rohes SQL.
	gruppen = get_all(
		"Gruppe",
		filters={"dienstbereich": MUSIK_DIENSTBEREICH},
		fields=["name"],
		pluck="name",
	) or []
	if not gruppen:
		return False
	return bool(
		_sh._count(
			"Gruppe Verantwortlicher",
			{"user": user, "parent": ["in", list(gruppen)]},
		)
	)


def _require_write() -> None:
	"""Erzwingt Schreibrecht: Musikverantwortlicher oder Admin."""
	user = _require_login()
	if _is_admin(user):
		return
	if _is_musikverantwortlicher(user):
		return
	throw(
		"Keine Berechtigung zum Schreiben. Erforderlich: Verantwortlicher "
		"im Dienstbereich 'Musik und Worship' oder Rolle "
		"Mitgliederadministrator / System Manager.",
		PermissionError,
	)


# ── Helfer ──────────────────────────────────────────────────────────────────


def _lied_kopf(lied: Any) -> dict[str, Any]:
	"""Dict mit den Kernfeldern eines Liedes (fuer Listen/Zusammenfassungen)."""
	quelle = lied.get("quelle")
	buch = lied.get("buch")
	nummer = lied.gesangbuch_nummer
	seite = lied.get("seite")
	from diakronos_app.planrahmen.lieder_pflege import anzeige_text
	return {
		"name": lied.name,
		"titel": lied.titel,
		"alternativtitel": lied.alternativtitel,
		"gesangbuch_nummer": nummer,
		"buch": buch,
		"seite": seite,
		"quelle": quelle,
		# Fertige, menschenlesbare Kennung ('Kopie', 'JN 1297', 'WH S. 150').
		"anzeige": anzeige_text(quelle, buch, nummer, seite, lied.titel),
		"ccli_nummer": lied.ccli_nummer,
		"rechte_status": lied.rechte_status,
		"aktiv": bool(lied.get("aktiv")),
		"zuletzt_gesungen": lied.zuletzt_gesungen,
		"anzahl_gesungen": lied.anzahl_gesungen or 0,
	}


def _anzeige(l: Any) -> str:
	"""Menschenlesbare Kennung aus einem (dict- oder objektfoermigen) Lied.

	'Kopie' bei Quelle 'kopie', sonst 'BUCH NR' bzw. 'BUCH S. SEITE' — und
	leer, wenn es keine Angabe gibt. Nie ein 'Nr.' ohne Nummer.
	"""
	from diakronos_app.planrahmen.lieder_pflege import anzeige_text
	holen = (lambda key: l.get(key)) if isinstance(l, dict) else (lambda key: getattr(l, key, None))
	return anzeige_text(holen("quelle"), holen("buch"),
	                    holen("gesangbuch_nummer"), holen("seite"), holen("titel"))


def _lied_kurzinfo(lied: str | None) -> dict[str, Any]:
	"""Titel / Alternativtitel / Kennung eines Liedes (UXM-R10).

	Robust gegen geloeschte oder fehlende Kennungen: dann kommt ein leeres
	dict zurueck, statt einen Fehler zu werfen.
	"""
	if not lied:
		return {}
	try:
		doc = get_doc("Lied", lied)
	except Exception:
		return {}
	titel = doc.get("titel")
	return {
		"titel": titel,
		"alternativtitel": doc.get("alternativtitel"),
		"buch": doc.get("buch"),
		"gesangbuch_nummer": doc.get("gesangbuch_nummer"),
		"anzeige": _anzeige(doc),
	}


def _fassung_brief(fassung: Any) -> dict[str, Any]:
	"""Kompakte Fassungs-Daten (ohne Material-/Notiz-Rauschen)."""
	return {
		"name": fassung.name,
		"fassungsname": fassung.fassungsname,
		"gruppe": fassung.gruppe,
		"besetzung": fassung.besetzung,
		"ist_standard": bool(fassung.get("ist_standard")),
	}


def _fassung_voll(fassung: Any) -> dict[str, Any]:
	"""Vollstaendige Fassung inkl. Tonart/Tempo/Material."""
	data = _fassung_brief(fassung)
	data.update({
		"stimmen": fassung.stimmen,
		"tonart": fassung.tonart,
		"taktart": fassung.taktart,
		"tempo_bpm": fassung.tempo_bpm,
		"dauer_minuten": fassung.dauer_minuten,
		"schwierigkeit": fassung.schwierigkeit,
		"arrangeur": fassung.arrangeur,
		"externe_links": fassung.externe_links,
		"notiz": fassung.notiz,
	})
	material = []
	for row in _sh._child_rows("Lied Material", fassung.name, "material",
	                           ["name", "art", "stimme", "anhang", "beschreibung"]):
		eintrag = {
			"art": row.get("art"),
			"stimme": row.get("stimme"),
			"anhang": row.get("anhang"),
			# UXM-R8: Kennung der Kind-Zeile fuer „Entfernen".
			"material": row.get("name"),
			"beschreibung": row.get("beschreibung"),
		}
		# ST2: Anhang-Verweis zu Datei-URL/Name/Typ aufloesen, damit die UI
		# Material anzeigen, abspielen und herunterladen kann.
		if row.get("anhang"):
			eintrag["datei"] = _anhang_info(row.get("anhang"))
		material.append(eintrag)
	data["material"] = material
	return data


def _anhang_info(name: str) -> dict[str, Any]:
	"""Sicherer Anhang → {datei_url, dateiname, dateityp} (ohne Fehler bei Luecke).

	Robust gegen Altbestand, in dem ``anhang`` direkt eine Datei-URL traegt
	(kein ``Sicherer Anhang``-Datensatz): dann wird die Zeichenkette als
	``datei_url`` durchgereicht statt einen Fehler zu werfen.
	"""
	try:
		doc = get_doc("Sicherer Anhang", name)
	except Exception:
		doc = None
	if doc is None:
		url = name if str(name).startswith(("/files/", "/private/files/")) else ""
		return {"datei_url": url, "dateiname": "", "dateityp": ""}
	return {"datei_url": doc.datei or "", "dateiname": doc.dateiname or "",
	        "dateityp": doc.dateityp or ""}


def _lied_besetzungen(lied_name: str) -> list[str]:
	"""Besetzungen aller Fassungen eines Liedes (fuer get_lied_detail).

    Fuer die LISTE wird das NICHT benutzt — dort sammelt
    :func:`_besetzungen_je_lied` alle Besetzungen in EINER Abfrage
    (PF2: die fruehere Schleife kostete eine Abfrage je Lied).
    """
	fassungen = get_all(
		"Liedfassung",
		filters={"lied": lied_name},
		fields=["besetzung"],
	) or []
	seen: list[str] = []
	for f in fassungen:
		bes = f.get("besetzung") if isinstance(f, dict) else getattr(f, "besetzung", None)
		if bes and bes not in seen:
			seen.append(bes)
	return seen


def _besetzungen_je_lied(lied_namen: list[str]) -> dict[str, list[str]]:
	"""Besetzungen aller Fassungen fuer VIELE Lieder in EINER Abfrage.

    PF2: vorher rief die Listen-Schleife ``_lied_besetzungen`` je Lied auf —
    bei 50 Liedern also 50 Abfragen (bei 134 Liedern 134). Hier wird genau
    eine Abfrage gestellt und im Speicher gruppiert. Ergebnis identisch:
    Reihenfolge je Lied = Reihenfolge der Fassungen (idx), Duplikate raus.
    """
	if not lied_namen:
		return {}
	fassungen = get_all(
		"Liedfassung",
		filters={"lied": ["in", list(lied_namen)]},
		fields=["lied", "besetzung"],
		order_by="idx asc",
	) or []
	ergebnis: dict[str, list[str]] = {}
	for f in fassungen:
		lied = f.get("lied") if isinstance(f, dict) else getattr(f, "lied", None)
		bes = f.get("besetzung") if isinstance(f, dict) else getattr(f, "besetzung", None)
		if not lied or not bes:
			continue
		vorhanden = ergebnis.setdefault(lied, [])
		if bes not in vorhanden:
			vorhanden.append(bes)
	return ergebnis


# ── Suche ────────────────────────────────────────────────────────────────────

#: LIKE-Steuerzeichen. Werden maskiert, damit ein Suchbegriff wie '%' oder '_'
#: nicht als Platzhalter wirkt (UXM-R11: '%' lieferte vorher ALLE Lieder).
_LIKE_MASK = {"\\": "\\\\", "%": "\\%", "_": "\\_"}
#: LIKE-Steuerzeichen der vier Lied-Felder, die durchsucht werden.
_SUCH_FELDER = ("titel", "alternativtitel", "gesangbuch_nummer", "buch", "ccli_nummer")


def _like_maskieren(text: str) -> str:
	"""Suchbegriff fuer LIKE entschaerfen (\\, % und _woertlich nehmen)."""
	return "".join(_LIKE_MASK.get(z, z) for z in str(text))


def _suche_liednamen(suche: str) -> list[str]:
	"""Lied-Namen, die zum Suchbegriff passen.

	Durchsucht Titel, Alternativtitel, Liednummer, Buch/Heft, CCLI-Nummer und
	Strophentext (tabLiedstrophe.text). Gross-/Kleinschreibung spielt keine
	Rolle (UXM-R11 / BF1-J), LIKE-Steuerzeichen sind maskiert.

	Ein Eintrag wie 'JN 1297' wird als Buch + Nummer verstanden: zuerst wird
	der ganze Begriff gesucht; findet sich damit genau nichts, wird zusaetzlich
	in zwei Feldern gesucht ("JN" in `buch`, "1297" in `gesangbuch_nummer`).
	"""
	begriff = str(suche or "").strip()
	if not begriff:
		return []
	like = f"%{_like_maskieren(begriff)}%"
	names: set[str] = set()
	for feld in _SUCH_FELDER:
		for t in get_all("Lied", filters=[[feld, "like", like]], fields=["name"]) or []:
			names.add(t["name"])
	# Strophentext durchsuchen (Child-Table tabLiedstrophe)
	for s in get_all("Liedstrophe", filters=[["text", "like", like]],
                 fields=["parent"]) or []:
		names.add(s["parent"])
	if names:
		return list(names)

	# Zusatzweg 'BUCH NUMMER' (z. B. 'JN 1297'): beide Teile getrennt suchen.
	teile = begriff.split()
	if len(teile) < 2:
		return []
	treffer: set[str] | None = None
	for teil in teile:
		teil_like = f"%{_like_maskieren(teil)}%"
		teilnamen: set[str] = set()
		for feld in _SUCH_FELDER:
			for t in get_all("Lied", filters=[[feld, "like", teil_like]], fields=["name"]) or []:
				teilnamen.add(t["name"])
		treffer = teilnamen if treffer is None else (treffer & teilnamen)
		if not treffer:
			return []
	return list(treffer or set())


# ── Lieder ───────────────────────────────────────────────────────────────────


@whitelist(allow_guest=False)
def get_lieder(gruppe: str | None = None, kategorie: str | None = None,
               anlass: str | None = None, rechte_status: str | None = None,
               suche: str | None = None, limit: int = 50, start: int = 0) -> list[dict[str, Any]]:
	"""Liste von Liedern mit Titel, Nummer, Besetzungen, rechte_status,
	zuletzt_gesungen.

	suche durchsucht Titel, Alternativtitel, Nummer, Buch/Heft, CCLI-Nummer UND
	Strophentext (tabLiedstrophe.text) — siehe :func:`_suche_liednamen`.
	"""
	_require_login()
	limit = min(int(limit) or 50, 200)
	start = max(int(start) or 0, 0)

	# Suche -> Lied-Namen ermitteln
	lied_names: list[str] | None = None
	if suche and str(suche).strip():
		lied_names = _suche_liednamen(suche)
		if not lied_names:
			return []

	filters: list[list[Any]] = []
	if lied_names is not None:
		filters.append(["name", "in", lied_names])
	if rechte_status:
		filters.append(["rechte_status", "=", rechte_status])
	if gruppe:
		# Lied-Zuordnung ueber Child `Lied Gruppenzuordnung` (feld `gruppe`)
		in_group = get_all("Lied Gruppenzuordnung", filters={"gruppe": gruppe},
		                   fields=["parent"], pluck="parent") or []
		if not in_group:
			return []
		filters.append(["name", "in", list(in_group)])
	if kategorie:
		in_cat = get_all("Lied Kategorie", filters={"kategorie": kategorie},
		                 fields=["parent"], pluck="parent") or []
		if not in_cat:
			return []
		filters.append(["name", "in", list(in_cat)])
	if anlass:
		in_anlass = get_all("Lied Anlass", filters={"anlass": anlass},
		                    fields=["parent"], pluck="parent") or []
		if not in_anlass:
			return []
		filters.append(["name", "in", list(in_anlass)])

	lieder = get_all(
		"Lied",
		filters=filters,
		fields=["name", "titel", "alternativtitel", "gesangbuch_nummer",
		        "buch", "seite", "quelle",
		        "ccli_nummer", "rechte_status", "aktiv", "zuletzt_gesungen",
		        "anzahl_gesungen"],
		order_by="titel asc",
		limit_page_length=limit,
		limit_start=start,
	) or []

	# Fassungen je Lied in EINER Abfrage zaehlen. Die Zahl der Besetzungen
	# taugt nicht als Ersatz: drei Chorsaetze desselben Liedes haetten sonst
	# alle die Besetzung "Chor" und wuerden als eine einzige Fassung angezeigt.
	fassungszahl: dict[str, int] = {}
	if lieder:
		namen = [l["name"] for l in lieder]
		for row in get_all("Liedfassung", filters={"lied": ["in", namen]},
		                   fields=["lied"]):
			fassungszahl[row["lied"]] = fassungszahl.get(row["lied"], 0) + 1

	# PF2: Besetzungen ALLER Zeilen in EINER Abfrage statt einer je Lied.
	besetzungen_je_lied = _besetzungen_je_lied([l["name"] for l in lieder])

	result = []
	for l in lieder:
		item = {
			"name": l["name"],
			"titel": l["titel"],
			"alternativtitel": l["alternativtitel"],
			"gesangbuch_nummer": l["gesangbuch_nummer"],
			"buch": l.get("buch"),
			"seite": l.get("seite"),
			"quelle": l.get("quelle"),
			"anzeige": _anzeige(l),
			"ccli_nummer": l["ccli_nummer"],
			"rechte_status": l["rechte_status"],
			"aktiv": bool(l["aktiv"]),
			"zuletzt_gesungen": l["zuletzt_gesungen"],
			"anzahl_gesungen": l["anzahl_gesungen"] or 0,
			"besetzungen": besetzungen_je_lied.get(l["name"], []),
			"anzahl_fassungen": fassungszahl.get(l["name"], 0),
		}
		result.append(item)
	return result


@whitelist(allow_guest=False)
def get_lied_detail(lied: str) -> dict[str, Any]:
	"""Kopf + Strophen + Fassungen (je mit Material) + zugehoerige Liedgruppen."""
	_require_login()
	doc = get_doc("Lied", lied)

	strophen = []
	for s in _sh._child_rows("Liedstrophe", lied, "strophen",
	                         ["nummer", "typ", "text", "sprache", "nur_chor"]):
		strophen.append({
			"nummer": s.get("nummer"),
			"typ": s.get("typ"),
			"text": s.get("text"),
			"sprache": s.get("sprache"),
			"nur_chor": bool(s.get("nur_chor")),
		})

	fassungen = [
		_fassung_voll(get_doc("Liedfassung", f["name"]))
		for f in get_all(
			"Liedfassung",
			filters={"lied": lied},
			fields=["name"],
			order_by="ist_standard desc, fassungsname asc",
		) or []
	]

	# Liedgruppen, in denen dieses Lied steckt (via Child `Liedgruppe Lied`)
	liedgruppen = get_all(
		"Liedgruppe Lied",
		filters={"lied": lied},
		fields=["parent", "fassung", "reihenfolge", "nummer"],
	) or []
	gruppen = []
	for lg in liedgruppen:
		gruppen.append({
			"liedgruppe": lg["parent"],
			"fassung": lg["fassung"],
			"reihenfolge": lg["reihenfolge"],
			"nummer": lg["nummer"],
		})

	# Kategorien + Anlaesse
	kategorien = list(get_all("Lied Kategorie", filters={"parent": lied},
	                          fields=["kategorie"], pluck="kategorie") or [])
	anlaesse = list(get_all("Lied Anlass", filters={"parent": lied},
	                        fields=["anlass"], pluck="anlass") or [])

	kopf = _lied_kopf(doc)
	kopf.update({
		"notiz": doc.notiz,
		"streaming_erlaubt": bool(doc.get("streaming_erlaubt")),
		"rechtehinweis": doc.rechtehinweis,
		"kategorien": kategorien,
		"anlaesse": anlaesse,
	})

	return {
		"lied": kopf,
		"strophen": strophen,
		"fassungen": fassungen,
		"liedgruppen": gruppen,
	}


@whitelist(allow_guest=False)
def get_fassungen(lied: str, gruppe: str | None = None) -> list[dict[str, Any]]:
	"""Alle Fassungen eines Liedes, optional auf eine Gruppe gefiltert."""
	_require_login()
	filters: dict[str, Any] = {"lied": lied}
	if gruppe:
		filters["gruppe"] = gruppe
	fassungen = get_all(
		"Liedfassung",
		filters=filters,
		fields=["name"],
		order_by="ist_standard desc, fassungsname asc",
	) or []
	result = []
	for f in fassungen:
		fdoc = get_doc("Liedfassung", f["name"])
		result.append(_fassung_voll(fdoc))
	return result


@whitelist(allow_guest=False)
def save_lied(daten: Any) -> dict[str, Any]:
	"""Lied anlegen oder aendern. `daten` enthaelt `name` fuer Update, sonst Insert.

	UXM-R1: Der ganze Vorgang laeuft in EINER Transaktion — entweder Lied UND
	alle Kind-Tabellen (Strophen/Gruppen/Kategorien/Anlaesse) werden
	geschrieben, oder nichts. Frueher committete jeder Kind-Schritt einzeln;
	ein Fehler in einem spaeteren Schritt liess Lied und Strophen bereits
	gespeichert zurueck (Teilspeicherung + Dubletten beim zweiten Klick).

	Kategorien und Anlaesse werden gegen den Katalog geprueft; unbekannte
	Namen legen — wie die Stammdaten-Pflege — einen Katalogeintrag an, statt
	an einem Fremdschluessel zu scheitern und rohen SQL-Text auszuliefern.
	"""
	_require_write()
	daten = daten or {}
	if isinstance(daten, str):
		daten = _json.loads(daten)

	from diakronos_app.db import SessionLocal, als_aktuelle_sitzung

	with SessionLocal.begin() as sitzung:
		with als_aktuelle_sitzung(sitzung):
			# Katalog-Zuordnungen VOR dem Schreiben pruefen/anlegen: schlaegt
			# das fehl, sind weder Lied noch Kinder entstanden (eine Transaktion).
			kategorien_ids = _katalog_zuordnungen(
				"Liedkategorie", "kategoriename", daten.get("kategorien")) \
				if _liste_uebergeben(daten, "kategorien") else None
			anlaesse_ids = _katalog_zuordnungen(
				"Liedanlass", "anlassname", daten.get("anlaesse")) \
				if _liste_uebergeben(daten, "anlaesse") else None

			name = daten.get("name")
			if name:
				_sh._update_doc("Lied", name, _lied_schreibfelder(daten))
			else:
				# P1-10b Befund 7: Dublettenschutz auch serverseitig. Die
				# Warnung im Frontend ist umgehbar (zweiter Aufruf/alter Stand);
				# hier entscheidet der Server. Gleicher Titel (ohne
				# Groß-/Kleinschreibung) oder gleiche Buch+Nummer gelten als
				# Dublette. Mit `dublette_bestaetigt` bleibt das bewusste
				# Doppel möglich.
				if not daten.get("dublette_bestaetigt"):
					_dublette_pruefen(daten)
				name = _sh._create("Lied", _lied_schreibfelder(daten))

			# Child-Tabellen nur bei expliziter Angabe schreiben (Original: doc.update()).
			if "strophen" in daten and isinstance(daten["strophen"], list):
				_replace_children("Liedstrophe", name, "strophen", "Lied",
				                  _strophen_rows(daten["strophen"]))
			if "gruppen" in daten and isinstance(daten["gruppen"], list):
				_replace_children("Lied Gruppenzuordnung", name, "gruppen", "Lied",
				                  [{"gruppe": _feld(r, "gruppe")} for r in daten["gruppen"]])
			if kategorien_ids is not None:
				_replace_children("Lied Kategorie", name, "kategorien", "Lied",
				                  [{"kategorie": kid} for kid in kategorien_ids])
			if anlaesse_ids is not None:
				_replace_children("Lied Anlass", name, "anlaesse", "Lied",
				                  [{"anlass": aid} for aid in anlaesse_ids])

			doc = get_doc("Lied", name)
			return {"success": True, "lied": name, "titel": doc.titel}


def _liste_uebergeben(daten: dict[str, Any], schluessel: str) -> bool:
	"""True, wenn der Schluessel als Liste uebergeben wurde (ersetzen)."""
	return schluessel in daten and isinstance(daten.get(schluessel), list)


def _katalog_zuordnungen(doctype: str, namensfeld: str,
                         werte: Any) -> list[str]:
	"""Namen in Zuordnungen des Katalogs uebersetzen; fehlende anlegen.

	Liefert die `name`-Kennungen der Katalogzeilen (nicht die Klartextnamen) —
	so entsteht bei `Lied Kategorie`/`Lied Anlass` kein Fremdschluessel-Fehler
	mehr (UXM-R1). Doppelte und leere Namen werden entfernt.
	"""
	namen: list[str] = []
	for w in (werte or []):
		text = _feld(w, "kategorie") if doctype == "Liedkategorie" else _feld(w, "anlass")
		if text is None:
			text = w if isinstance(w, str) else None
		text = str(text).strip() if text is not None else ""
		if text and text not in namen:
			namen.append(text)
	if not namen:
		return []

	katalog: dict[str, str] = {}
	for r in get_all(doctype, fields=["name", namensfeld]) or []:
		katalog[(r.get(namensfeld) or r["name"])] = r["name"]

	ids: list[str] = []
	for text in namen:
		kid = katalog.get(text)
		if kid is None:
			# Tippfehler-/Laengenschutz (Review P1-10, Befund 4): ein zu langer
			# oder leerer Name wuerde sonst erst als roher DB-Fehler auffallen.
			if len(text) > 140:
				throw(f"{doctype}: Name darf höchstens 140 Zeichen haben "
				      f"(erhalten: {len(text)}).")
			# Den Klartext SELBST als Katalog-Kennung nehmen: die Kind-Zeile
			# (`Lied Kategorie`) verweist auf `liedkategorie.name`; so bleibt die
			# Zuordnung lesbar und die bestehende Konvention (Name = Klartext)
			# erhalten — kein UUID-Umweg.
			kid = _sh._create(doctype,
			                  {"name": text, namensfeld: text})
			katalog[text] = kid
		ids.append(kid)
	return ids


def _replace_children(child_doctype: str, parent: str, parentfield: str,
                      parenttype: str, rows: list[dict[str, Any]]) -> None:
	"""Kind-Tabelle ersetzen (Original: `doc.set(feld, [])` + append).

	Wie `frappe_compat/api_helpers._child_replace`, aber mit EXPLIZITEM `parenttype`:
	Frappe speichert in Kind-Zeilen den DocType des ELTERN-Dokuments
	(`parenttype="Lied"`), waehrend `_child_replace` den Kind-DocType selbst
	nimmt — das waere ein Datenfehler.
	"""
	_sh._child_delete(child_doctype, parent, parentfield)
	for row in rows:
		_sh._child_insert(child_doctype, parent, parentfield, row,
		                  parenttype=parenttype)


def _strophen_rows(rows: list[Any]) -> list[dict[str, Any]]:
	"""Strophen-Zeilen auf die Schreibfelder reduzieren."""
	allowed = ["nummer", "typ", "text", "sprache", "nur_chor"]
	out = []
	for r in rows:
		if not isinstance(r, dict):
			continue
		out.append({k: r[k] for k in allowed if k in r})
	return out


def _feld(row: Any, key: str) -> Any:
	"""Ein Wert aus einer Kind-Zeile: dict mit `key` oder die Zeile selbst."""
	if isinstance(row, dict):
		return row.get(key)
	return row


def _lied_schreibfelder(daten: dict[str, Any]) -> dict[str, Any]:
	"""Erlaubte Schreibfelder eines Liedes."""
	allowed = [
		"titel", "alternativtitel", "gesangbuch_nummer", "buch", "seite",
		"quelle", "ccli_nummer", "aktiv", "rechte_status", "streaming_erlaubt",
		"rechtehinweis", "notiz",
	]
	return {k: daten[k] for k in allowed if k in daten}


def _dublette_pruefen(daten: dict[str, Any]) -> None:
	"""P1-10b Befund 7: gleiche Titel oder gleiche Buch+Nummer serverseitig abweisen.

	Dieselbe Regel wie die Warnung im Frontend (`LiedBearbeiten.vue`): ein Lied
	mit identischem Titel (ohne Groß-/Kleinschreibung) oder identischer
	Buch+Nummer gilt als Dublette. Die Prüfung sitzt am Server, damit ein
	zweiter Aufruf oder ein alter SPA-Stand sie nicht umgehen kann. Bewusste
	Doppel bleiben über `dublette_bestaetigt` möglich.
	"""
	titel = str(daten.get("titel") or "").strip()
	buch = str(daten.get("buch") or "").strip()
	nummer = str(daten.get("gesangbuch_nummer") or "").strip()
	if not titel and not (buch and nummer):
		return
	# `like_exakt` vergleicht ohne Ruecksicht auf Gross-/Kleinschreibung und
	# Umlautform, behandelt `%`/`_` aber als Zeichen (K-2) — sonst faende ein
	# Titel wie „100 %" beliebige Lieder.
	kandidaten = get_all("Lied", filters={"titel": ["like_exakt", titel]},
	                     fields=["name", "titel", "buch", "gesangbuch_nummer"]) if titel else []
	gesehen: set[str] = set()
	for r in (kandidaten or []):
		if not isinstance(r, dict):
			continue
		gesehen.add(str(r.get("name") or ""))
		if str(r.get("titel") or "").strip().casefold() == titel.casefold():
			throw(
				f"Es gibt schon ein Lied mit dem Titel „{r.get('titel')}“. "
				"Bitte prüfe deine Eingabe oder bestätige, dass du trotzdem "
				"ein zweites anlegen möchtest."
			)
	if buch and nummer:
		for r in get_all("Lied", filters={"buch": buch, "gesangbuch_nummer": nummer},
		                     fields=["name", "titel", "buch", "gesangbuch_nummer"]) or []:
			if not isinstance(r, dict) or r.get("name") in gesehen:
				continue
			throw(
				f"Es gibt schon ein Lied mit {buch} Nr. {nummer}: „{r.get('titel')}“. "
				"Bitte prüfe deine Eingabe oder bestätige, dass du trotzdem "
				"ein zweites anlegen möchtest."
			)


@whitelist(allow_guest=False)
def save_fassung(daten: Any) -> dict[str, Any]:
	"""Fassung anlegen oder aendern. `daten` enthaelt `name` fuer Update."""
	_require_write()
	daten = daten or {}
	if isinstance(daten, str):
		daten = _json.loads(daten)

	if not daten.get("lied"):
		throw("Fassung benoetigt ein Lied ('lied').")

	allowed = [
		"lied", "fassungsname", "gruppe", "ist_standard", "besetzung",
		"stimmen", "tonart", "taktart", "tempo_bpm", "dauer_minuten",
		"schwierigkeit", "arrangeur", "externe_links", "notiz",
	]
	werte = {k: daten[k] for k in allowed if k in daten}

	name = daten.get("name")
	if name:
		_sh._update_doc("Liedfassung", name, werte)
	else:
		name = _sh._create("Liedfassung", werte)

	if "material" in daten and isinstance(daten["material"], list):
		_replace_children("Lied Material", name, "material", "Liedfassung",
		                  [r for r in daten["material"] if isinstance(r, dict)])

	doc = get_doc("Liedfassung", name)
	return {"success": True, "fassung": name, "fassungsname": doc.fassungsname}


# ── Historie ─────────────────────────────────────────────────────────────────

# Spalten der echten DB (Spaltenabzug der Betriebs-DB): `Ablaufplan Position`
# hat referenz_doctype + referenz_name; `Ablaufplan` hat sie NICHT.
_ABLAUFPLAN_POSITION_COLS = {
	"name", "creation", "modified", "modified_by", "owner", "docstatus", "idx",
	"reihenfolge", "bezeichnung", "dauer_minuten", "verantwortlicher", "notiz",
	"parent", "parentfield", "parenttype", "referenz_doctype", "referenz_name",
	"funktion", "gruppe", "detail",
}
_ABLAUFPLAN_COLS = {
	"name", "creation", "modified", "modified_by", "owner", "docstatus", "idx",
	"titel", "element", "datum", "notizen", "_user_tags", "_comments", "_assign",
	"_liked_by",
}


@whitelist(allow_guest=False)
def get_lied_historie(lied: str) -> list[dict[str, Any]]:
	"""Wann/wo ein Lied zuletzt gesungen wurde.

	Quelle: Ablaufplan-Positionen mit referenz_doctype="Lied" und
	referenz_name=lied, gejoint ueber den Ablaufplan (titel, datum, element).
	Defensiv: falls die Felder referenz_doctype/referenz_name an den Positionen
	noch fehlen (Karte 1a-1), leere Liste statt Crash zurueckgeben.
	"""
	_require_login()

	# Original prueft `frappe.db.get_table_columns`; hier gegen die echte
	# Schema-Inventur (Spaltenabzug der Betriebs-DB). `Ablaufplan` hat KEIN
	# referenz_doctype -> Original liefert in der Live-DB deshalb immer [].
	if ("referenz_doctype" not in _ABLAUFPLAN_POSITION_COLS
			or "referenz_name" not in _ABLAUFPLAN_POSITION_COLS
			or "referenz_doctype" not in _ABLAUFPLAN_COLS):
		return []

	positions = get_all(
		"Ablaufplan Position",
		filters={"referenz_doctype": "Lied", "referenz_name": lied},
		fields=["parent", "funktion", "gruppe", "detail"],
		order_by="creation desc",
	) or []
	if not positions:
		return []

	result = []
	for p in positions:
		ablaufplan = get_value(
			"Ablaufplan", p["parent"],
			["titel", "datum", "element"],
			as_dict=True,
		)
		if not ablaufplan:
			continue
		element_name = None
		element_start = None
		if ablaufplan.get("element"):
			ev = get_value(
				"Element", ablaufplan["element"],
				["element_name", "element_start"],
				as_dict=True,
			)
			if ev:
				element_name = ev.get("element_name")
				element_start = ev.get("element_start")
		result.append({
			"ablaufplan": p["parent"],
			"titel": ablaufplan.get("titel"),
			"datum": ablaufplan.get("datum"),
			"element": ablaufplan.get("element"),
			"element_name": element_name,
			"element_start": element_start,
			"funktion": p["funktion"],
			"gruppe": p["gruppe"],
			"detail": p["detail"],
		})
	return result


# ── Liedgruppen ──────────────────────────────────────────────────────────────


@whitelist(allow_guest=False)
def get_liedgruppen(typ: str | None = None, gruppe: str | None = None) -> list[dict[str, Any]]:
	"""Liste aller Liedgruppen, optional nach typ / gruppe gefiltert."""
	_require_login()
	filters: dict[str, Any] = {}
	if typ:
		filters["typ"] = typ
	if gruppe:
		filters["gruppe"] = gruppe
	gruppen = get_all(
		"Liedgruppe",
		filters=filters,
		fields=["name", "gruppenname", "typ", "status", "gruppe",
		        "komponist", "textautor", "verlag", "dauer_minuten"],
		order_by="gruppenname asc",
	) or []
	result = []
	for g in gruppen:
		result.append({
			"name": g["name"],
			"gruppenname": g["gruppenname"],
			"typ": g["typ"],
			"status": g["status"],
			"gruppe": g["gruppe"],
			"komponist": g["komponist"],
			"textautor": g["textautor"],
			"verlag": g["verlag"],
			"dauer_minuten": g["dauer_minuten"],
		})
	return result


@whitelist(allow_guest=False)
def get_liedgruppe_detail(liedgruppe: str) -> dict[str, Any]:
	"""Detail einer Liedgruppe inkl. Lieder und Rollen."""
	_require_login()
	doc = get_doc("Liedgruppe", liedgruppe)

	lieder = []
	for row in _sh._child_rows("Liedgruppe Lied", liedgruppe, "lieder",
	                           ["lied", "fassung", "reihenfolge", "nummer",
	                            "szene", "notiz"]):
		# UXM-R10: Klartext statt interner Kennung. Ohne `titel`/`anzeige`
		# zeigte die Spalte „Lied" die rohe ID (q9jpcjb7o5).
		lied_info = _lied_kurzinfo(row.get("lied"))
		lieder.append({
			"lied": row.get("lied"),
			"titel": lied_info.get("titel"),
			"alternativtitel": lied_info.get("alternativtitel"),
			"anzeige": lied_info.get("anzeige"),
			"buch": lied_info.get("buch"),
			"gesangbuch_nummer": lied_info.get("gesangbuch_nummer"),
			"fassung": row.get("fassung"),
			"reihenfolge": row.get("reihenfolge"),
			"nummer": row.get("nummer"),
			"szene": row.get("szene"),
			"notiz": row.get("notiz"),
		})

	rollen = []
	for row in _sh._child_rows("Liedgruppe Rolle", liedgruppe, "rollen",
	                           ["rollenname", "rollentyp", "stimmlage", "umfang",
	                            "min_alter", "max_alter", "anzahl_besetzungen",
	                            "beschreibung"]):
		rollen.append({
			"rollenname": row.get("rollenname"),
			"rollentyp": row.get("rollentyp"),
			"stimmlage": row.get("stimmlage"),
			"umfang": row.get("umfang"),
			"min_alter": row.get("min_alter"),
			"max_alter": row.get("max_alter"),
			"anzahl_besetzungen": row.get("anzahl_besetzungen"),
			"beschreibung": row.get("beschreibung"),
		})

	return {
		"liedgruppe": {
			"name": doc.name,
			"gruppenname": doc.gruppenname,
			"typ": doc.typ,
			"status": doc.status,
			"gruppe": doc.gruppe,
			"dauer_minuten": doc.dauer_minuten,
			"komponist": doc.komponist,
			"textautor": doc.textautor,
			"verlag": doc.verlag,
			"lizenzhinweis": doc.lizenzhinweis,
			"beschreibung": doc.beschreibung,
		},
		"lieder": lieder,
		"rollen": rollen,
	}


#: Erlaubte Liedgruppen-Typen (UXM-R9 / Manuels Wunsch „Buch/Projekt/Sammlung/frei").
LIEDGRUPPE_TYPEN = ["Werk", "Musical", "Kantate", "Sammlung", "Gesangbuch",
                    "Projekt", "Reihe", "Mappe", "Buch", "Sonstiges"]
LIEDGRUPPE_STATUS = ["Aktiv", "Archiviert"]


@whitelist(allow_guest=False)
def save_liedgruppe(daten: Any) -> dict[str, Any]:
	"""Liedgruppe anlegen oder aendern (UXM-R9).

	`daten` enthaelt `name` fuer Update, sonst Insert. `lieder` (Liste) wird —
	falls uebergeben — als Kind-Tabelle ersetzt; jedes Element ist
	``{lied, fassung?, reihenfolge?, nummer?, szene?, notiz?}``. Alles laeuft in
	EINER Transaktion.
	"""
	_require_write()
	daten = daten or {}
	if isinstance(daten, str):
		daten = _json.loads(daten)

	from diakronos_app.db import SessionLocal, als_aktuelle_sitzung

	with SessionLocal.begin() as sitzung:
		with als_aktuelle_sitzung(sitzung):
			werte = _liedgruppe_schreibfelder(daten)
			name = daten.get("name")
			if name:
				if get_doc("Liedgruppe", name) is None:
					throw("Liedgruppe nicht gefunden.", DoesNotExistError)
				_sh._update_doc("Liedgruppe", name, werte)
			else:
				if not str(daten.get("gruppenname") or "").strip():
					throw("Bitte einen Namen für die Liedgruppe eintragen.")
				name = _sh._create("Liedgruppe", werte)

			if "lieder" in daten and isinstance(daten["lieder"], list):
				_replace_children("Liedgruppe Lied", name, "lieder", "Liedgruppe",
				                  _liedgruppe_lieder_rows(daten["lieder"]))

			doc = get_doc("Liedgruppe", name)
			return {"success": True, "liedgruppe": name,
			        "gruppenname": doc.gruppenname}


@whitelist(allow_guest=False)
def delete_liedgruppe(liedgruppe: str) -> dict[str, Any]:
	"""Liedgruppe mit ihren Zuordnungen loeschen (UXM-R9).

	Eine Liedgruppe ist selbststaendig (kein Fremdschluessel auf `Lied`); die
	Kind-Zeilen (Lieder/Rollen) werden mit entfernt. Die Lieder selbst bleiben
	natuerlich erhalten.

	Review P1-10 (Befund M2): Wird die Liedgruppe noch als Inhalt eines
	Plan-Rahmen-Slots (`dienstplan_vorlage_slot.inhalt_sammlung`) verwendet,
	wird sie NICHT geloescht — sonst kaeme ein roher Fremdschluessel-Fehler.
	Stattdessen eine verstaendliche Meldung mit der Anzahl der Verwendungen.
	"""
	_require_write()
	if not liedgruppe:
		throw("Keine Liedgruppe angegeben.")

	from diakronos_app.db import SessionLocal, als_aktuelle_sitzung
	from diakronos_app.models.diakonos import DienstplanVorlageSlot

	with SessionLocal.begin() as sitzung:
		with als_aktuelle_sitzung(sitzung):
			if get_doc("Liedgruppe", liedgruppe) is None:
				throw("Liedgruppe nicht gefunden.", DoesNotExistError)
			verwendungen = _sh._count("Dienstplan Vorlage Slot",
			                         {"inhalt_sammlung": liedgruppe})
			if verwendungen:
				throw("Diese Liedgruppe wird in "
				      f"{verwendungen} Plan-Vorlage(n) verwendet. "
				      "Bitte sie dort zuerst entfernen — oder die Gruppe "
				      "stattdessen auf den Status „Archiviert“ setzen.")
			for child, feld in (("Liedgruppe Lied", "lieder"),
			                    ("Liedgruppe Rolle", "rollen")):
				_sh._child_delete(child, liedgruppe, feld)
			_sh._delete_doc("Liedgruppe", liedgruppe)
			return {"success": True, "liedgruppe": liedgruppe}


def _liedgruppe_schreibfelder(daten: dict[str, Any]) -> dict[str, Any]:
	"""Erlaubte Schreibfelder einer Liedgruppe.

	Review P1-10:
	- Befund 5: Ein unbekannter Wert in `gruppe` (Fremdschluessel
	  `liedgruppe.name`) wird vorab mit Klartextmeldung abgelehnt.
	- Befund 6: `typ` wird nur geprueft, wenn er sich tatsaechlich aendert.
	  Bestandsdaten mit einem Altwert (ausserhalb der Liste) bleiben so beim
	  Bearbeiten speicherbar, solange der Wert unveraendert mitgesendet wird.
	"""
	allowed = ["gruppenname", "typ", "status", "gruppe", "dauer_minuten",
	           "komponist", "textautor", "verlag", "lizenzhinweis", "beschreibung"]
	werte = {k: daten[k] for k in allowed if k in daten}
	if "typ" in werte and werte["typ"] and werte["typ"] not in LIEDGRUPPE_TYPEN:
		name = daten.get("name")
		alt = get_value("Liedgruppe", name, "typ") if name else None
		if werte["typ"] != alt:
			throw("Unbekannter Typ. Erlaubt: " + ", ".join(LIEDGRUPPE_TYPEN) + ".")
	if "gruppenname" in werte and not str(werte["gruppenname"] or "").strip():
		throw("Bitte einen Namen für die Liedgruppe eintragen.")
	if werte.get("gruppe") and not _dokument_existiert("Gruppe", str(werte["gruppe"])):
		throw("Die zugeordnete Gruppe wurde nicht gefunden. Bitte die Gruppenauswahl aktualisieren.")
	return werte


def _liedgruppe_lieder_rows(rows: list[Any]) -> list[dict[str, Any]]:
	"""Zeilen der Kind-Tabelle `Liedgruppe Lied` aufbereiten.

	Nicht existierende Lieder werden mit Klartextmeldung abgelehnt (Review
	P1-10, Befund 5: `get_doc` wirft `DoesNotExistError` statt `None` zurueck,
	die frueherere `is None`-Pruefung war toter Code und der Abbruch kam als
	roher Fehler). Die Reihenfolge ergibt sich aus der Listenposition, sofern
	sie nicht gesetzt ist.
	"""
	allowed = ["lied", "fassung", "reihenfolge", "nummer", "szene", "notiz"]
	out: list[dict[str, Any]] = []
	for pos, r in enumerate(rows):
		if not isinstance(r, dict):
			continue
		lied = r.get("lied")
		if not lied:
			continue
		if not _dokument_existiert("Lied", lied):
			throw(f"Lied {lied!r} wurde nicht gefunden — bitte die Liste "
			      "aktualisieren und erneut speichern.")
		zeile = {k: r[k] for k in allowed if k in r and r[k] is not None}
		zeile["lied"] = lied
		if "reihenfolge" not in zeile:
			zeile["reihenfolge"] = pos + 1
		out.append(zeile)
	return out


def _dokument_existiert(doctype: str, name: str) -> bool:
	"""True, wenn das Dokument existiert — ohne Ausnahme (Review P1-10, Befund 5)."""
	return bool(get_value(doctype, name, "name"))


def _katalog_sortierschluessel(wert: Any) -> tuple[str, str]:
	"""Deutsche Wörterbuchfolge, unabhängig von installierten Host-Locales.

	Umlaute zählen wie der Grundbuchstabe, ß wie ss. Ein zweiter, NFC-
	normalisierter Schlüssel hält gleichwertige Einträge deterministisch,
	auch wenn die Datenbank oder das Set eine andere Reihenfolge liefert.
	"""
	text = unicodedata.normalize("NFC", str(wert)).casefold()
	grund = "".join(c for c in unicodedata.normalize("NFD", text)
	                if not unicodedata.combining(c))
	return grund, unicodedata.normalize("NFC", str(wert))


@whitelist(allow_guest=False)
def get_lied_filteroptionen() -> dict[str, list[str]]:
	"""Alle Filter-Optionen der Lieder-Liste in EINEM Aufruf.

    PF2: Die SPA holte sich Kategorien und Anlaesse bisher, indem sie
    nacheinander 30 Lied-Details abrief (N+1 im Frontend) — das war der
    Hauptteil der ~1,3 s Ladezeit. Hier werden dieselben Optionslisten direkt
    und gebuendelt gelesen, unabhaengig von der Listen-Seite. Sortierung wie in
    der SPA (deutsch, alphabetisch).

    BF1b (Operator-Vorgabe): Die Filter zeigen ALLE Katalogwerte
    (Liedkategorie/Liedanlass/Liedgruppe) — nicht nur die an Liedern bereits
    zugeordneten. So kann man auch nach einer Kategorie filtern, die es als
    Stammdatum gibt, an der aber noch kein Lied haengt (sonst waere die Liste
    unvollstaendig und der Filter praktisch blind). Vorher wurde ueber die
    Zuordnungs-Childs eingesammelt — leere Kategorien fehlten dadurch.

    Rueckgabe: {"gruppen": [...], "kategorien": [...], "anlaesse": [...]}
    """
	_require_login()

	# Liedgruppen: Klartextname (gruppenname) aus dem Katalog, Fallback `name`.
	gruppen = get_all("Liedgruppe", fields=["name", "gruppenname"]) or []
	gruppen_namen = sorted(
		{(g.get("gruppenname") or g.get("name")) for g in gruppen if (g.get("gruppenname") or g.get("name"))},
		key=_katalog_sortierschluessel,
	)

	def _katalog(stamm_doctype: str, stamm_feld: str) -> list[str]:
		"""Klartextnamen ALLER Katalogzeilen (Stammdaten) eines Typs."""
		rows = get_all(stamm_doctype, fields=[stamm_feld, "name"]) or []
		namen = {(r.get(stamm_feld) or r.get("name")) for r in rows}
		return sorted((n for n in namen if n), key=_katalog_sortierschluessel)

	kategorien = _katalog("Liedkategorie", "kategoriename")
	anlaesse = _katalog("Liedanlass", "anlassname")

	return {
		"gruppen": gruppen_namen,
		"kategorien": kategorien,
		"anlaesse": anlaesse,
	}
