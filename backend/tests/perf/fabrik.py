"""PERF-K3 — Testdaten-Fabrik in realistischer Groesse (Postgres, Wegwerf-Stack).

Vorgabe der Karte PERF-K3: 26 Gruppen, 14 Kalender, 134 Mitglieder,
2000 Termine. Die Zuordnung ist bewusst verteilt und nicht „alle in einer
Gruppe“: sonst misst man einen Rechte-Pfad, den es im Betrieb nicht gibt.

Aufbau:

  * 26 Gruppen, davon 8 Untergruppen (Kind einer Hauptgruppe).
  * 14 Kalender: 6 Gemeinde-Kalender (keine Gruppe), 6 einer Hauptgruppe,
    2 einer Untergruppe.
  * 134 Mitglieder (je ein Konto + Mitglied + Gruppenmitgliedschaft).
  * Rollen: je Hauptgruppe genau EIN HV, dazu MV; je Untergruppe ein GL.
  * 2000 Termine im Messfenster + Serien; ein Teil als ``Vorschlag``
    (Moderationslast) und ``Konflikt``.

Die Funktionen sind idempotent-frei: sie nehmen eine LEERE Datenbank an
(`alembic upgrade head` ist gelaufen).
"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy.orm import Session

# Zielgroessen (Karte PERF-K3).
GRUPPEN = 26
UNTERGRUPPEN = 8
KALENDER = 14
MITGLIEDER = 134
TERMINE = 2000

# Konten, die das Messskript anspricht.
ADMIN = "perfk3-admin@example.org"
HV = "perfk3-hv@example.org"          # HV der Gruppe GR-01 (moderiert deren Kalender)
MV = "perfk3-mv@example.org"          # MV derselben Gruppe (nur Vorschläge)
MITGLIED = "perfk3-mitglied@example.org"   # einfaches Mitglied von GR-01
FREMD = "perfk3-fremd@example.org"         # Mitglied einer ANDEREN Gruppe (GR-02)
OHNE = "perfk3-ohne@example.org"           # Konto ohne Mitgliedschaft


def _mitglied_name(i: int) -> str:
	return f"MIT-K3-{i:03d}"


def _gruppe_name(i: int) -> str:
	return f"GR-{i:02d}"


def aufbauen(sess: Session) -> dict:
	"""Legt die Welt an und gibt die Kennzahlen zurueck."""
	from diakronos_app.models.core import HasRole, User
	from diakronos_app.models.diakonos import (
		Gruppe,
		Gruppenmitgliedschaft,
		Mitglied,
	)
	from diakronos_app.models.kronos import Element, Eventkategorie, Kalender, Ressource
	from diakronos_app.models.rechte import (
		RechteFreigabe,
		RechteGruppenrolle,
		RechteModul,
		RechteObjekt,
	)

	# ── Gruppen ────────────────────────────────────────────────────────────
	hauptgruppen = [_gruppe_name(i) for i in range(1, GRUPPEN - UNTERGRUPPEN + 1)]
	untergruppen = [f"UG-{i:02d}" for i in range(1, UNTERGRUPPEN + 1)]
	gruppen = []
	for i, name in enumerate(hauptgruppen):
		gruppen.append(Gruppe(name=name, gruppenname=f"Gruppe {name}", docstatus=0,
		                      idx=i, status="Aktiv", sichtbarkeit="intern"))
	for i, name in enumerate(untergruppen):
		# Jede Untergruppe haengt an einer der ersten Hauptgruppen.
		ober = hauptgruppen[i % len(hauptgruppen)]
		gruppen.append(Gruppe(name=name, gruppenname=f"Untergruppe {name}", docstatus=0,
		                      idx=100 + i, status="Aktiv", sichtbarkeit="intern",
		                      obergruppe=ober, ancestor_path=ober))
	sess.add_all(gruppen)
	sess.flush()

	# ── Konten + Mitglieder + Mitgliedschaften ─────────────────────────────
	sonder = [ADMIN, HV, MV, MITGLIED, FREMD, OHNE]
	namen = list(sonder)
	while len(namen) < MITGLIEDER + 1:  # +1 wegen Admin ohne Mitglied
		namen.append(f"perfk3-person{len(namen):03d}@example.org")

	nutzer = []
	for i, mail in enumerate(namen):
		nutzer.append(User(name=mail, email=mail, full_name=f"Person {i:03d}",
		                   enabled=True, user_type="System User"))
	sess.add_all(nutzer)
	sess.flush()
	sess.add(HasRole(name="HR-K3-ADMIN", parent=ADMIN, parenttype="User",
	                 parentfield="roles", role="System Manager", docstatus=0, idx=1))
	sess.add(HasRole(name="HR-K3-ALLE", parent=ADMIN, parenttype="User",
	                 parentfield="roles", role="Mitglied", docstatus=0, idx=2))
	sess.flush()

	# Jedes Nicht-Admin-Konto wird Mitglied — verteilt ueber alle Gruppen.
	mitglieder = []
	konto_je_mitglied: dict[str, str] = {}
	verteilung = [g for g in (hauptgruppen + untergruppen)]
	for i, mail in enumerate(namen):
		if mail == ADMIN:
			continue
		mname = _mitglied_name(i)
		mitglieder.append(Mitglied(
			name=mname, vorname="Person", nachname=f"{i:03d}", email=mail,
			user=mail, status="Aktiv", ausgeschlossen=0, docstatus=0, idx=i))
		konto_je_mitglied[mail] = mname
	sess.add_all(mitglieder)
	sess.flush()

	gm = []
	for i, mail in enumerate(namen):
		if mail == OHNE:
			continue  # Konto ohne Mitgliedschaft („Gast“ im Sinne der Rechte)
		if mail == ADMIN:
			continue
		ziel = verteilung[i % len(verteilung)]
		gm.append(Gruppenmitgliedschaft(
			name=f"GM-K3-{i:03d}", parent=ziel, parenttype="Gruppe",
			parentfield="mitglieder", mitglied=_mitglied_name(i), status="Aktiv",
			docstatus=0, idx=i))
	# Der Mess-HV, -MV und das Messmitglied gehoeren nach GR-01.
	for mail, idx in ((HV, 1), (MV, 2), (MITGLIED, 3)):
		gm.append(Gruppenmitgliedschaft(
			name=f"GM-K3-FIX-{idx}", parent=hauptgruppen[0], parenttype="Gruppe",
			parentfield="mitglieder", mitglied=konto_je_mitglied[mail], status="Aktiv",
			docstatus=0, idx=900 + idx))
	sess.add_all(gm)
	sess.flush()

	# ── Rollen ─────────────────────────────────────────────────────────────
	rollen = [RechteGruppenrolle(gruppe=hauptgruppen[0], benutzer=HV, rolle="HV"),
	          RechteGruppenrolle(gruppe=hauptgruppen[0], benutzer=MV, rolle="MV")]
	for i, g in enumerate(hauptgruppen[1:], start=1):
		# Jede weitere Hauptgruppe bekommt einen eigenen HV (echte Verteilung).
		rollen.append(RechteGruppenrolle(gruppe=g, benutzer=namen[10 + i], rolle="HV"))
	for i, ug in enumerate(untergruppen):
		rollen.append(RechteGruppenrolle(gruppe=hauptgruppen[i % len(hauptgruppen)],
		                                 untergruppe=ug, benutzer=namen[40 + i],
		                                 rolle="GL"))
	sess.add_all(rollen)

	# Modul „kalender“ fuer JEDE Gruppe aktiv — sonst antwortet der Kern
	# „modul_aus“ und die Messung liefe ins Leere (PERF-K1-Befund).
	sess.add_all([RechteModul(gruppe=g, modul="kalender")
	              for g in hauptgruppen + untergruppen])
	sess.flush()

	# ── Kalender ───────────────────────────────────────────────────────────
	kalender = []
	for i in range(KALENDER):
		kalender.append(Kalender(
			name=f"KAL-K3-{i:02d}", calendar_name=f"Kalender {i:02d}",
			calendar_color=f"#33{66 + i:02d}00", selbstverwaltet=(i % 4 == 0),
			docstatus=0, idx=i))
	sess.add_all(kalender)
	sess.flush()

	# 0..5 Gemeinde (keine Gruppe), 6..11 Hauptgruppe GR-01, 12..13 Untergruppe.
	objekte = []
	for i, k in enumerate(kalender):
		if i < 6:
			objekte.append(RechteObjekt(typ="kalender", objekt=k.name, gruppe=None,
			                            untergruppe=None, gemeinde_status="aktiv",
			                            gruppe_status="aus"))
		elif i < 12:
			objekte.append(RechteObjekt(typ="kalender", objekt=k.name, gruppe=hauptgruppen[0],
			                            untergruppe=None, gemeinde_status="aktiv",
			                            gruppe_status="aus"))
		else:
			objekte.append(RechteObjekt(typ="kalender", objekt=k.name, gruppe=hauptgruppen[0],
			                            untergruppe=untergruppen[i - 12],
			                            gemeinde_status="aktiv", gruppe_status="aktiv"))
	sess.add_all(objekte)
	sess.flush()

	# Freigaben: die Gruppen-Kalender an die Gruppe (schreiben), die
	# Untergruppen-Kalender zusaetzlich an die Hauptgruppe (nur lesen).
	freigaben = []
	for i, k in enumerate(kalender):
		if 6 <= i < 12:
			freigaben.append(RechteFreigabe(typ="kalender", objekt=k.name,
			                                gruppe=hauptgruppen[0], lesen=True,
			                                schreiben=True, moderieren=True))
		elif i >= 12:
			freigaben.append(RechteFreigabe(typ="kalender", objekt=k.name,
			                                gruppe=untergruppen[i - 12], lesen=True,
			                                schreiben=True, moderieren=False))
	sess.add_all(freigaben)

	# ── Stammdaten-Termine und Ressourcen ──────────────────────────────────
	sess.add_all([Eventkategorie(name=f"KAT-K3-{i}", event_category_name=f"Kategorie {i}",
	                             farbe="#3366ff", docstatus=0, idx=i) for i in range(6)])
	sess.add_all([Ressource(name=f"RES-K3-{i}", ressource_name=f"Raum {i}", docstatus=0,
	                        idx=i) for i in range(11)])
	sess.flush()

	# 2000 Termine: das Messfenster ist Nov/Dez 2026 (Monatsansicht).
	# Verteilung: ~70 % Festgelegt, ~22 % Vorschlag, ~8 % Konflikt.
	elemente = []
	start = datetime(2026, 10, 20, 8, 0)
	for i in range(TERMINE):
		s = start + timedelta(minutes=(i * 37) % (75 * 24 * 60))
		rest = i % 100
		if rest < 70:
			status = "Festgelegt"
		elif rest < 92:
			status = "Vorschlag"
		else:
			status = "Konflikt"
		kal = f"KAL-K3-{i % KALENDER:02d}"
		elemente.append(Element(
			name=f"EL-K3-{i:04d}", element_name=f"Termin {i}",
			element_calendar=kal, element_start=s,
			element_end=s + timedelta(hours=1 + (i % 3)), all_day=(i % 11 == 0),
			status=status, element_category=f"KAT-K3-{i % 6}",
			ressource=(f"RES-K3-{i % 11}" if i % 5 == 0 else None),
			owner=namen[i % len(namen)], repeat_this_event=0, docstatus=0, idx=i))
	# Serien: 30 Serien mit je 8 Folgeterminen (im Fenster sichtbar).
	for k in range(30):
		s0 = datetime(2026, 10, 26, 18, 0) + timedelta(days=k % 7)
		for j in range(8):
			s = s0 + timedelta(days=7 * j)
			elemente.append(Element(
				name=f"EL-K3-S{k:02d}-{j}", element_name=f"Serie {k} Folge {j}",
				element_calendar=f"KAL-K3-{k % KALENDER:02d}", element_start=s,
				element_end=s + timedelta(hours=2), all_day=False,
				status=("Vorschlag" if k % 9 == 0 else "Festgelegt"),
				series_id=f"SER-K3-{k:02d}", owner=namen[k % len(namen)],
				repeat_this_event=0, docstatus=0, idx=5000 + k * 10 + j))
	sess.add_all(elemente)
	sess.commit()

	return {
		"gruppen": len(hauptgruppen) + len(untergruppen),
		"hauptgruppen": len(hauptgruppen),
		"untergruppen": len(untergruppen),
		"kalender": len(kalender),
		"mitglieder": len(mitglieder),
		"konten": len(namen),
		"termine": len(elemente),
		"vorschlaege": sum(1 for e in elemente if e.status == "Vorschlag"),
		"konflikte": sum(1 for e in elemente if e.status == "Konflikt"),
	}


__all__ = [
	"aufbauen", "GRUPPEN", "UNTERGRUPPEN", "KALENDER", "MITGLIEDER", "TERMINE",
	"ADMIN", "HV", "MV", "MITGLIED", "FREMD", "OHNE",
]
