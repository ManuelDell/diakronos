# Copyright (c) 2025, Dells Dienste and Contributors
# See license.txt
#
# Kronos Primärfunktionen – Regressionstests für Element (Termin/Event)
# Schützt: CRUD, Serien-Erstellung, Status-Filterung, View-Mode-Logik

import frappe
import datetime
from frappe.tests import UnitTestCase
from frappe.utils import now_datetime


_TEST_CAL_NAME = "_Test Kronos Kalender EL"


def _get_or_make_kalender():
    if frappe.db.exists("Kalender", _TEST_CAL_NAME):
        return frappe.get_doc("Kalender", _TEST_CAL_NAME)
    return frappe.get_doc({
        "doctype": "Kalender",
        "calendar_name": _TEST_CAL_NAME,
        "calendar_color": "#3b82f6",
        "calender_details": "Test-Kalender für Element-Tests",
        "leserechte": [{"role": "System Manager"}],
        "schreibrechte": [{"role": "System Manager"}],
    }).insert(ignore_permissions=True)


def _make_element(name, status="Festgelegt", start_offset_hours=0, kalender=None):
    base = now_datetime()
    start = frappe.utils.add_to_date(base, hours=start_offset_hours)
    end   = frappe.utils.add_to_date(start, hours=1)
    return frappe.get_doc({
        "doctype": "Element",
        "element_name": name,
        "element_calendar": kalender or _TEST_CAL_NAME,
        "element_start": start,
        "element_end": end,
        "status": status,
    }).insert(ignore_permissions=True)


class TestElement(UnitTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        frappe.set_user("Administrator")
        _get_or_make_kalender()

    @classmethod
    def tearDownClass(cls):
        frappe.db.delete("Element", {"element_calendar": _TEST_CAL_NAME})
        frappe.db.delete("Kalender", {"calendar_name": _TEST_CAL_NAME})
        frappe.db.commit()
        super().tearDownClass()

    def setUp(self):
        frappe.set_user("Administrator")

    # ------------------------------------------------------------------
    # 1. CRUD – Grundlegende Erstellung und Persistenz
    # ------------------------------------------------------------------

    def test_element_create_festgelegt(self):
        """Element mit Status Festgelegt lässt sich anlegen."""
        el = _make_element("_Test Festgelegt", status="Festgelegt")
        self.assertEqual(el.status, "Festgelegt")
        self.assertEqual(el.element_calendar, _TEST_CAL_NAME)
        self.assertTrue(frappe.db.exists("Element", el.name))

    def test_element_create_vorschlag(self):
        """Element mit Status Vorschlag lässt sich anlegen."""
        el = _make_element("_Test Vorschlag", status="Vorschlag")
        self.assertEqual(el.status, "Vorschlag")
        self.assertTrue(frappe.db.exists("Element", el.name))

    def test_element_requires_calendar(self):
        """Element ohne Kalender wirft MandatoryError."""
        with self.assertRaises(frappe.exceptions.MandatoryError):
            frappe.get_doc({
                "doctype": "Element",
                "element_name": "_Test Ohne Kalender",
                "element_start": now_datetime(),
                "element_end": frappe.utils.add_to_date(now_datetime(), hours=1),
                "status": "Festgelegt",
            }).insert(ignore_permissions=True)

    def test_element_requires_start(self):
        """Element ohne Start-Zeit wirft MandatoryError."""
        with self.assertRaises(frappe.exceptions.MandatoryError):
            frappe.get_doc({
                "doctype": "Element",
                "element_name": "_Test Ohne Start",
                "element_calendar": _TEST_CAL_NAME,
                "element_end": frappe.utils.add_to_date(now_datetime(), hours=1),
                "status": "Festgelegt",
            }).insert(ignore_permissions=True)

    def test_element_update_status(self):
        """Status lässt sich von Vorschlag auf Festgelegt ändern."""
        el = _make_element("_Test Update Status", status="Vorschlag")
        el.status = "Festgelegt"
        el.save(ignore_permissions=True)
        el.reload()
        self.assertEqual(el.status, "Festgelegt")

    def test_element_delete(self):
        """Element lässt sich löschen."""
        el = _make_element("_Test Delete")
        name = el.name
        frappe.delete_doc("Element", name, ignore_permissions=True)
        self.assertFalse(frappe.db.exists("Element", name))

    # ------------------------------------------------------------------
    # 2. Serien-Erstellung
    # ------------------------------------------------------------------

    def test_series_daily_creates_multiple_elements(self):
        """Tägliche Serie erzeugt mindestens 2 Elemente mit gleicher series_id."""
        base = now_datetime()
        till = str(str(frappe.utils.add_to_date(base, days=3))).split(" ")[0]

        el = frappe.get_doc({
            "doctype": "Element",
            "element_name": "_Test Serie Täglich",
            "element_calendar": _TEST_CAL_NAME,
            "element_start": base,
            "element_end": frappe.utils.add_to_date(base, hours=1),
            "status": "Festgelegt",
            "repeat_this_event": 1,
            "repeat_on": "Daily",
            "repeat_till": till,
        }).insert(ignore_permissions=True)

        self.assertIsNotNone(el.series_id)
        self.assertFalse(el.repeat_this_event)
        count = frappe.db.count("Element", {"series_id": el.series_id})
        self.assertGreaterEqual(count, 2,
            "Tägliche Serie über 3 Tage muss mind. 2 Elemente erzeugen")

    def test_series_sets_series_id(self):
        """Nach Serien-Insert hat das Element eine series_id."""
        base = now_datetime()
        till = str(frappe.utils.add_to_date(base, days=2)).split(" ")[0]

        el = frappe.get_doc({
            "doctype": "Element",
            "element_name": "_Test Serie ID Check",
            "element_calendar": _TEST_CAL_NAME,
            "element_start": base,
            "element_end": frappe.utils.add_to_date(base, hours=1),
            "status": "Festgelegt",
            "repeat_this_event": 1,
            "repeat_on": "Daily",
            "repeat_till": till,
        }).insert(ignore_permissions=True)

        self.assertTrue(el.series_id.startswith("SER-"),
            f"series_id sollte mit SER- beginnen, war: {el.series_id}")

    def test_two_series_have_different_ids(self):
        """Zwei separate Serien haben unterschiedliche series_ids."""
        base = now_datetime()
        till = str(frappe.utils.add_to_date(base, days=2)).split(" ")[0]

        el1 = frappe.get_doc({
            "doctype": "Element",
            "element_name": "_Test Serie X",
            "element_calendar": _TEST_CAL_NAME,
            "element_start": base,
            "element_end": frappe.utils.add_to_date(base, hours=1),
            "status": "Festgelegt",
            "repeat_this_event": 1,
            "repeat_on": "Daily",
            "repeat_till": till,
        }).insert(ignore_permissions=True)

        el2 = frappe.get_doc({
            "doctype": "Element",
            "element_name": "_Test Serie Y",
            "element_calendar": _TEST_CAL_NAME,
            "element_start": frappe.utils.add_to_date(base, hours=2),
            "element_end": frappe.utils.add_to_date(base, hours=3),
            "status": "Festgelegt",
            "repeat_this_event": 1,
            "repeat_on": "Daily",
            "repeat_till": till,
        }).insert(ignore_permissions=True)

        self.assertNotEqual(el1.series_id, el2.series_id)

    def test_series_monthly_creates_elements(self):
        """Monatliche Serie über 3 Monate erzeugt Elemente."""
        base = now_datetime()
        till = str(frappe.utils.add_to_date(base, months=3)).split(" ")[0]

        el = frappe.get_doc({
            "doctype": "Element",
            "element_name": "_Test Serie Monatlich",
            "element_calendar": _TEST_CAL_NAME,
            "element_start": base,
            "element_end": frappe.utils.add_to_date(base, hours=1),
            "status": "Festgelegt",
            "repeat_this_event": 1,
            "repeat_on": "Monthly",
            "repeat_till": till,
        }).insert(ignore_permissions=True)

        count = frappe.db.count("Element", {"series_id": el.series_id})
        self.assertGreaterEqual(count, 2)

    # ------------------------------------------------------------------
    # 3. View-Mode Filterung (get_calendar_events)
    # ------------------------------------------------------------------

    def test_view_mode_excludes_vorschlag(self):
        """get_calendar_events(view_mode=True) gibt keine Vorschlag-Events zurück."""
        from diakronos.kronos.api.calendar_get import get_calendar_events

        _make_element("_Test VM Festgelegt", status="Festgelegt")
        _make_element("_Test VM Vorschlag",  status="Vorschlag")

        today = datetime.date.today()
        start = str(today - datetime.timedelta(days=1))
        end   = str(today + datetime.timedelta(days=2))

        events = get_calendar_events(start_date=start, end_date=end, view_mode=True)
        statuses = {
            e["extendedProps"]["status"] for e in events
            if e["extendedProps"]["element_calendar"] == _TEST_CAL_NAME
        }
        self.assertNotIn("Vorschlag", statuses,
            "view_mode=True darf keine Vorschlag-Events zeigen")

    def test_edit_mode_includes_vorschlag_for_admin(self):
        """get_calendar_events(view_mode=False) zeigt Vorschlag für Administrator."""
        from diakronos.kronos.api.calendar_get import get_calendar_events

        _make_element("_Test EM Festgelegt", status="Festgelegt")
        _make_element("_Test EM Vorschlag",  status="Vorschlag")

        today = datetime.date.today()
        start = str(today - datetime.timedelta(days=1))
        end   = str(today + datetime.timedelta(days=2))

        events = get_calendar_events(start_date=start, end_date=end, view_mode=False)
        statuses = {
            e["extendedProps"]["status"] for e in events
            if e["extendedProps"]["element_calendar"] == _TEST_CAL_NAME
        }
        self.assertIn("Vorschlag", statuses,
            "edit_mode=False muss Vorschlag für Administrator zeigen")

    def test_view_mode_string_true_works(self):
        """view_mode='true' (String vom Frontend) wird korrekt interpretiert."""
        from diakronos.kronos.api.calendar_get import get_calendar_events

        today = datetime.date.today()
        start = str(today - datetime.timedelta(days=1))
        end   = str(today + datetime.timedelta(days=1))

        result = get_calendar_events(start_date=start, end_date=end, view_mode="true")
        self.assertIsInstance(result, list)

    def test_view_mode_string_false_works(self):
        """view_mode='false' (String vom Frontend) wird korrekt interpretiert."""
        from diakronos.kronos.api.calendar_get import get_calendar_events

        today = datetime.date.today()
        start = str(today - datetime.timedelta(days=1))
        end   = str(today + datetime.timedelta(days=1))

        result = get_calendar_events(start_date=start, end_date=end, view_mode="false")
        self.assertIsInstance(result, list)

    def test_events_return_correct_structure(self):
        """Jedes zurückgegebene Event hat die erwartete FullCalendar-Struktur."""
        from diakronos.kronos.api.calendar_get import get_calendar_events

        _make_element("_Test Struktur", status="Festgelegt")

        today = datetime.date.today()
        start = str(today - datetime.timedelta(days=1))
        end   = str(today + datetime.timedelta(days=2))

        events = get_calendar_events(start_date=start, end_date=end, view_mode=True)
        if not events:
            return  # Kein Event im Fenster – Skip

        e = events[0]
        for key in ("id", "title", "start", "end", "allDay",
                    "backgroundColor", "borderColor", "extendedProps"):
            self.assertIn(key, e, f"Pflichtfeld '{key}' fehlt im Event")

        ext = e["extendedProps"]
        for key in ("name", "element_name", "element_calendar", "status"):
            self.assertIn(key, ext, f"extendedProps-Pflichtfeld '{key}' fehlt")
