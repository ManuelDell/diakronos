# diakronos/diakronos/doctype/diakronos_einstellungen/demo_data.py
# Erstellt und löscht Demodaten für die Diakronos-App.

import frappe
from datetime import datetime, timedelta
from calendar import monthrange


# ── Statische Demo-Daten ─────────────────────────────────────────────────────

KATEGORIEN = [
    ("Gottesdienst",       "Wöchentliche Gottesdienste und Andachten der Gemeinde"),
    ("Gemeinschaftsabend", "Gesellige Abende für die gesamte Gemeindefamilie"),
    ("Jugend",             "Veranstaltungen für Jugendliche und Young Adults (13–30)"),
    ("Kleingruppe",        "Hauskreise, Bibelarbeiten und Gesprächsrunden"),
    ("Konzert & Musik",    "Chorproben, Konzerte und musikalische Abende"),
    ("Gemeindeausflug",    "Gemeinsame Ausflüge und Wochenendfreizeiten"),
    ("Kinder & Familie",   "Kindergottesdienst, Familiennachmittage und Bastelstunden"),
    ("Gebet & Andacht",    "Stille Gebetszeiten, Morgenandachten und Fürbittgruppen"),
]

KALENDER = [
    ("Gemeinde",    "#667eea", "Hauptkalender – allgemeine Termine und Gottesdienste"),
    ("Jugend",      "#f093fb", "Jugendgruppe und Young Adults"),
    ("Musik & Chor","#4facfe", "Chorproben, Konzerte und musikalische Veranstaltungen"),
    ("Intern",      "#43e97b", "Interne Termine für Leitungsteam und Mitarbeiter"),
]

MITGLIEDER = [
    ("Anna",    "Bergmann",  "anna.bergmann@example.de",   "1978-04-12", "70173", "Stuttgart", "Königstraße",       "15"),
    ("Hans",    "Müller",    "hans.mueller@example.de",    "1965-09-23", "70174", "Stuttgart", "Schillerstraße",    "8"),
    ("Maria",   "Schneider", "maria.schneider@example.de", "1990-02-14", "70175", "Stuttgart", "Friedrichstraße",   "22"),
    ("Klaus",   "Wagner",    "klaus.wagner@example.de",    "1955-11-30", "70176", "Stuttgart", "Hegelplatz",        "3"),
    ("Sabine",  "Fischer",   "sabine.fischer@example.de",  "1983-07-07", "70178", "Stuttgart", "Neckarstraße",      "47"),
    ("Thomas",  "Weber",     "thomas.weber@example.de",    "1971-03-19", "70173", "Stuttgart", "Marienstraße",      "11"),
    ("Petra",   "Meyer",     "petra.meyer@example.de",     "1988-12-05", "70174", "Stuttgart", "Augustenstraße",    "33"),
    ("Markus",  "Becker",    "markus.becker@example.de",   "1962-08-28", "70176", "Stuttgart", "Rotebühlstraße",    "19"),
    ("Julia",   "Hoffmann",  "julia.hoffmann@example.de",  "1995-05-17", "70175", "Stuttgart", "Tübinger Straße",   "6"),
    ("Werner",  "Schulz",    "werner.schulz@example.de",   "1948-01-09", "70178", "Stuttgart", "Vogelsangstraße",   "29"),
]

BESUCHER = [
    ("Lena",   "Zimmermann", "2025-09-15", 0),
    ("Felix",  "Hartmann",   "2025-11-01", 0),
    ("Monika", "Braun",      "2025-10-20", 1),
    ("Paul",   "Koch",       "2026-01-12", 0),
    ("Ingrid", "Richter",    "2025-08-03", 0),
]


# ── Hilfsfunktionen ───────────────────────────────────────────────────────────

def _fmt(dt):
    """datetime → Frappe-Datetime-String."""
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _three_month_range():
    """Gibt (erster Tag Vormonat, letzter Tag Folgemonat) zurück."""
    today = datetime.now()

    # Vormonat erster Tag
    if today.month == 1:
        start = today.replace(year=today.year - 1, month=12, day=1, hour=0, minute=0, second=0, microsecond=0)
    else:
        start = today.replace(month=today.month - 1, day=1, hour=0, minute=0, second=0, microsecond=0)

    # Folgemonat letzter Tag
    if today.month == 12:
        next_month = today.replace(year=today.year + 1, month=1)
    else:
        next_month = today.replace(month=today.month + 1)
    last_day = monthrange(next_month.year, next_month.month)[1]
    end = next_month.replace(day=last_day, hour=23, minute=59, second=59, microsecond=0)

    return start, end


def _all_days(start, end):
    """Alle Tage zwischen start und end (inkl.)."""
    current = start.replace(hour=0, minute=0, second=0)
    while current <= end:
        yield current
        current += timedelta(days=1)


def _nth_weekday_of_month(year, month, weekday, n):
    """n-ter Wochentag (0=Mo … 6=So) im Monat. None wenn nicht vorhanden."""
    count = 0
    for day in range(1, monthrange(year, month)[1] + 1):
        d = datetime(year, month, day)
        if d.weekday() == weekday:
            count += 1
            if count == n:
                return d
    return None


# ── Prüfung ────────────────────────────────────────────────────────────────────

def has_existing_data():
    """True wenn bereits Daten in Diakronos vorhanden sind."""
    return (
        frappe.db.count("Kalender") > 0
        or frappe.db.count("Element") > 0
        or frappe.db.count("Mitglied") > 0
        or frappe.db.count("Besucher") > 0
        or frappe.db.count("Eventkategorie") > 0
    )


# ── Erstellen ──────────────────────────────────────────────────────────────────

def create_demo_data():
    if has_existing_data():
        frappe.throw(
            "Es sind bereits Daten vorhanden. Demodaten können nur in einer leeren App erstellt werden.",
            title="Daten vorhanden",
        )

    _create_kategorien()
    kal_namen = _create_kalender()
    _create_mitglieder()
    _create_besucher()
    _create_events(kal_namen)


def _create_kategorien():
    for name, detail in KATEGORIEN:
        if not frappe.db.exists("Eventkategorie", name):
            frappe.get_doc({
                "doctype": "Eventkategorie",
                "event_category_name": name,
                "event_category_detail": detail,
            }).insert(ignore_permissions=True, ignore_mandatory=True)


def _create_kalender():
    names = {}
    for cal_name, color, details in KALENDER:
        if frappe.db.exists("Kalender", cal_name):
            names[cal_name] = cal_name
            continue
        doc = frappe.get_doc({
            "doctype": "Kalender",
            "calendar_name": cal_name,
            "calendar_color": color,
            "calender_details": details,
        })
        # Leserechte: Mitglied, Schreibrechte: Kalenderadministrator
        doc.append("leserechte",   {"role": "Mitglied"})
        doc.append("schreibrechte", {"role": "Kalenderadministrator"})
        doc.insert(ignore_permissions=True, ignore_mandatory=True)
        names[cal_name] = doc.name
    return names


def _create_mitglieder():
    today = datetime.now()
    for vorname, nachname, email, geb, plz, ort, strasse, nr in MITGLIEDER:
        if frappe.db.exists("Mitglied", {"vorname": vorname, "nachname": nachname}):
            continue
        # Mitglied seit: zufällig 1–8 Jahre zurück (deterministisch über Namen)
        seed = sum(ord(c) for c in vorname + nachname)
        jahre = 1 + (seed % 8)
        seit = today.replace(year=today.year - jahre).strftime("%Y-%m-%d")
        doc = frappe.get_doc({
            "doctype":       "Mitglied",
            "vorname":       vorname,
            "nachname":      nachname,
            "email":         email,
            "geburtstag":    geb,
            "postleitzahl":  plz,
            "wohnort":       ort,
            "straße":        strasse,
            "nummer":        nr,
            "mitglied_seit": seit,
        })
        doc.insert(ignore_permissions=True, ignore_mandatory=True)


def _create_besucher():
    for vorname, nachname, seit, ehemals in BESUCHER:
        if frappe.get_all("Besucher", filters={"name1": vorname, "nachname": nachname}, limit=1):
            continue
        frappe.get_doc({
            "doctype": "Besucher",
            "name1":                        vorname,
            "nachname":                     nachname,
            "besucher_seit":                seit,
            "ehemaliges_gemeindemitglied":  ehemals,
        }).insert(ignore_permissions=True, ignore_mandatory=True,
                  set_name=f"{vorname} {nachname}")


def _create_events(kal_namen):
    start, end = _three_month_range()

    gemeinde = kal_namen.get("Gemeinde",    "Gemeinde")
    jugend   = kal_namen.get("Jugend",      "Jugend")
    musik    = kal_namen.get("Musik & Chor","Musik & Chor")
    intern   = kal_namen.get("Intern",      "Intern")

    events = []

    # ── Wiederkehrende Wochentermine ─────────────────────────────────────────
    for day in _all_days(start, end):
        wd = day.weekday()  # 0=Mo … 6=So

        # Sonntag: Gottesdienst 10:00–12:00
        if wd == 6:
            events.append({
                "element_name":     "Gottesdienst",
                "element_start":    _fmt(day.replace(hour=10, minute=0)),
                "element_end":      _fmt(day.replace(hour=12, minute=0)),
                "element_calendar": gemeinde,
                "element_category": "Gottesdienst",
                "status":           "Festgelegt",
                "description":      "Wöchentlicher Gemeinschaftsgottesdienst mit Predigt, Lobpreis und Abendmahl.",
            })
            # Sonntag Nachmittag alle 2 Wochen: Kindergottesdienst
            if day.day % 14 < 7:
                events.append({
                    "element_name":     "Kindergottesdienst",
                    "element_start":    _fmt(day.replace(hour=14, minute=0)),
                    "element_end":      _fmt(day.replace(hour=15, minute=30)),
                    "element_calendar": gemeinde,
                    "element_category": "Kinder & Familie",
                    "status":           "Festgelegt",
                    "description":      "Kinderprogramm parallel zum Gottesdienst – Basteln, Lieder und Bibelgeschichten.",
                })

        # Mittwoch: Gebetskreis 19:00–20:30
        if wd == 2:
            events.append({
                "element_name":     "Gebetskreis",
                "element_start":    _fmt(day.replace(hour=19, minute=0)),
                "element_end":      _fmt(day.replace(hour=20, minute=30)),
                "element_calendar": gemeinde,
                "element_category": "Gebet & Andacht",
                "status":           "Festgelegt",
                "description":      "Offener Gebetsabend – Fürbitten, stille Anbetung und gemeinsames Gebet.",
            })

        # Donnerstag: Chorprobe 19:30–21:00
        if wd == 3:
            events.append({
                "element_name":     "Chorprobe",
                "element_start":    _fmt(day.replace(hour=19, minute=30)),
                "element_end":      _fmt(day.replace(hour=21, minute=0)),
                "element_calendar": musik,
                "element_category": "Konzert & Musik",
                "status":           "Festgelegt",
                "description":      "Wöchentliche Probe des Gemeindechors.",
            })

    # ── Monatliche Termine (dynamisch pro Monat im Zeitraum) ─────────────────
    months_to_cover = []
    cur = start.replace(day=1)
    while cur <= end:
        months_to_cover.append((cur.year, cur.month))
        if cur.month == 12:
            cur = cur.replace(year=cur.year + 1, month=1)
        else:
            cur = cur.replace(month=cur.month + 1)

    for year, month in months_to_cover:
        # 2. Freitag: Jugendabend 18:00–21:30
        fri2 = _nth_weekday_of_month(year, month, 4, 2)
        if fri2 and start <= fri2 <= end:
            events.append({
                "element_name":     "Jugendabend",
                "element_start":    _fmt(fri2.replace(hour=18, minute=0)),
                "element_end":      _fmt(fri2.replace(hour=21, minute=30)),
                "element_calendar": jugend,
                "element_category": "Jugend",
                "status":           "Festgelegt",
                "description":      "Monatlicher Jugendabend – gemeinsames Kochen, Spiele, Austausch und kurze Andacht.",
            })

        # 3. Freitag: Jugend Bibelarbeit 19:00–21:00
        fri3 = _nth_weekday_of_month(year, month, 4, 3)
        if fri3 and start <= fri3 <= end:
            events.append({
                "element_name":     "Jugend – Bibelarbeit",
                "element_start":    _fmt(fri3.replace(hour=19, minute=0)),
                "element_end":      _fmt(fri3.replace(hour=21, minute=0)),
                "element_calendar": jugend,
                "element_category": "Jugend",
                "status":           "Festgelegt",
                "description":      "Gemeinsame Bibelarbeit mit Diskussionsrunde.",
            })

        # 2. Dienstag: Kleingruppe Mitte 19:30–21:30
        tue2 = _nth_weekday_of_month(year, month, 1, 2)
        if tue2 and start <= tue2 <= end:
            events.append({
                "element_name":     "Kleingruppe Stadtmitte",
                "element_start":    _fmt(tue2.replace(hour=19, minute=30)),
                "element_end":      _fmt(tue2.replace(hour=21, minute=30)),
                "element_calendar": gemeinde,
                "element_category": "Kleingruppe",
                "status":           "Festgelegt",
                "description":      "Hauskreis im Stadtzentrum – Bibeltext, Gebet und Austausch in kleiner Runde.",
            })

        # 4. Dienstag: Kleingruppe Nord 19:30–21:30
        tue4 = _nth_weekday_of_month(year, month, 1, 4)
        if tue4 and start <= tue4 <= end:
            events.append({
                "element_name":     "Kleingruppe Nord",
                "element_start":    _fmt(tue4.replace(hour=19, minute=30)),
                "element_end":      _fmt(tue4.replace(hour=21, minute=30)),
                "element_calendar": gemeinde,
                "element_category": "Kleingruppe",
                "status":           "Festgelegt",
                "description":      "Hauskreis im Norden der Stadt.",
            })

        # 1. Samstag: Gemeinschaftsabend 18:00–22:00
        sat1 = _nth_weekday_of_month(year, month, 5, 1)
        if sat1 and start <= sat1 <= end:
            events.append({
                "element_name":     "Gemeinschaftsabend",
                "element_start":    _fmt(sat1.replace(hour=18, minute=0)),
                "element_end":      _fmt(sat1.replace(hour=22, minute=0)),
                "element_calendar": gemeinde,
                "element_category": "Gemeinschaftsabend",
                "status":           "Festgelegt",
                "description":      "Monatlicher Gemeinschaftsabend mit Buffet, Liedern und gemeinsamer Zeit.",
            })

        # Letzter Samstag: Konzert / musikalischer Abend
        sat_last = _nth_weekday_of_month(year, month, 5, 4) or _nth_weekday_of_month(year, month, 5, 5)
        if sat_last and start <= sat_last <= end and sat_last != sat1:
            events.append({
                "element_name":     "Lobpreis & Worship-Abend",
                "element_start":    _fmt(sat_last.replace(hour=19, minute=0)),
                "element_end":      _fmt(sat_last.replace(hour=21, minute=30)),
                "element_calendar": musik,
                "element_category": "Konzert & Musik",
                "status":           "Festgelegt",
                "description":      "Abend der Stille und des Lobpreises – Chor, Band und offene Bühne.",
            })

        # Montagmittag: Leitungstreffen (monatlich)
        mon1 = _nth_weekday_of_month(year, month, 0, 1)
        if mon1 and start <= mon1 <= end:
            events.append({
                "element_name":     "Leitungsteam-Treffen",
                "element_start":    _fmt(mon1.replace(hour=18, minute=30)),
                "element_end":      _fmt(mon1.replace(hour=20, minute=30)),
                "element_calendar": intern,
                "element_category": "Kleingruppe",
                "status":           "Festgelegt",
                "description":      "Monatliches Planungsgespräch des Leitungsteams.",
            })

    # ── Besondere Einzel-Events (relativ zu heute) ────────────────────────────
    today = datetime.now()
    specials = [
        # Vergangener Monat
        (today - timedelta(days=45), gemeinde,  "Gemeindeausflug Schwarzwald",
         "Kinder & Familie", 8 * 3600, 0,
         "Ganztagesausflug in den Schwarzwald – Wandern, Picknick und gemeinsame Zeit."),
        (today - timedelta(days=28), musik,     "Frühjahrskonzert des Chors",
         "Konzert & Musik", 2 * 3600, 19 * 3600,
         "Jährliches Frühjahrskonzert mit geistlichen Liedern aus fünf Jahrhunderten."),
        (today - timedelta(days=18), jugend,    "Jugendfreizeit Burg Wildenstein",
         "Jugend", 48 * 3600, 0,
         "Dreitägige Jugendfreizeit – Bibelstudium, Sport und Lagerfeuer."),

        # Dieser Monat
        (today + timedelta(days=4),  gemeinde,  "Taufe & Aufnahmefeier",
         "Gottesdienst", 3 * 3600, 10 * 3600,
         "Taufgottesdienst mit anschließendem Empfang für neue Gemeindemitglieder."),
        (today + timedelta(days=10), intern,    "Gemeindeversammlung",
         "Gemeinschaftsabend", 2 * 3600, 19 * 3600,
         "Jährliche Mitgliederversammlung – Berichte, Abstimmungen und Ausblick."),
        (today + timedelta(days=17), jugend,    "Kino-Abend mit Diskussion",
         "Jugend", 3 * 3600, 18 * 3600,
         "Filmabend mit anschließender Gesprächsrunde zu christlichen Themen."),

        # Nächster Monat
        (today + timedelta(days=38), gemeinde,  "Pfingstgottesdienst",
         "Gottesdienst", 3 * 3600, 10 * 3600,
         "Festlicher Gottesdienst mit besonderem Programm und Live-Musik."),
        (today + timedelta(days=44), musik,     "Sommerkonzert im Freien",
         "Konzert & Musik", 3 * 3600, 16 * 3600,
         "Offenes Konzert im Gemeindegarten – Eintritt frei, Spende willkommen."),
        (today + timedelta(days=52), gemeinde,  "Gemeindefest",
         "Gemeinschaftsabend", 6 * 3600, 14 * 3600,
         "Jährliches Gemeindefest mit Barbecue, Kinderprogramm und Live-Musik."),
    ]

    for base_dt, kalender, name, kategorie, dauer, start_offset, desc in specials:
        ev_start = base_dt.replace(
            hour=int(start_offset // 3600),
            minute=int((start_offset % 3600) // 60),
            second=0, microsecond=0
        )
        ev_end = ev_start + timedelta(seconds=dauer)
        events.append({
            "element_name":     name,
            "element_start":    _fmt(ev_start),
            "element_end":      _fmt(ev_end),
            "element_calendar": kalender,
            "element_category": kategorie,
            "status":           "Festgelegt",
            "description":      desc,
        })

    for ev in events:
        frappe.get_doc({"doctype": "Element", **ev}).insert(ignore_permissions=True, ignore_mandatory=True)


# ── Löschen ────────────────────────────────────────────────────────────────────

def delete_demo_data():
    for doctype in ["Element", "Kalender", "Eventkategorie", "Mitglied", "Besucher"]:
        records = frappe.get_all(doctype, fields=["name"])
        for r in records:
            try:
                frappe.delete_doc(doctype, r.name, ignore_permissions=True, force=True)
            except Exception:
                pass
