# Copyright (c) 2026, Dells Dienste and Contributors
# See license.txt
#
# Kronos Primärfunktionen – Regressionstests für Kalender
# Schützt: CRUD, Pflichtfelder, Permissions, Event-Filterung

import frappe
import datetime
from frappe.tests import UnitTestCase
from frappe.utils import now_datetime


_TEST_CAL_A = "_Test Kalender A"
_TEST_CAL_B = "_Test Kalender B"


def _get_or_make_kalender(name, color="#3b82f6", leserechte=None, schreibrechte=None):
    if frappe.db.exists("Kalender", name):
        return frappe.get_doc("Kalender", name)
    return frappe.get_doc({
        "doctype": "Kalender",
        "calendar_name": name,
        "calendar_color": color,
        "calender_details": f"Testkalender: {name}",
        "leserechte": leserechte or [{"role": "System Manager"}],
        "schreibrechte": schreibrechte or [],
    }).insert(ignore_permissions=True)


def _make_element(name, kalender, status="Festgelegt"):
    base = now_datetime()
    return frappe.get_doc({
        "doctype": "Element",
        "element_name": name,
        "element_calendar": kalender,
        "element_start": base,
        "element_end": frappe.utils.add_to_date(base, hours=1),
        "status": status,
    }).insert(ignore_permissions=True)


class TestKalender(UnitTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        frappe.set_user("Administrator")
        _get_or_make_kalender(_TEST_CAL_A, "#3b82f6")
        _get_or_make_kalender(_TEST_CAL_B, "#10b981")

    @classmethod
    def tearDownClass(cls):
        frappe.db.delete("Element", {"element_calendar": ["in", [_TEST_CAL_A, _TEST_CAL_B]]})
        frappe.db.delete("Kalender", {"calendar_name": ["in", [_TEST_CAL_A, _TEST_CAL_B]]})
        frappe.db.commit()
        super().tearDownClass()

    def setUp(self):
        frappe.set_user("Administrator")

    # ------------------------------------------------------------------
    # 1. Kalender CRUD
    # ------------------------------------------------------------------

    def test_kalender_exists_after_create(self):
        """Kalender ist nach Erstellung in der DB vorhanden."""
        self.assertTrue(frappe.db.exists("Kalender", _TEST_CAL_A))
        self.assertTrue(frappe.db.exists("Kalender", _TEST_CAL_B))

    def test_kalender_fields_stored_correctly(self):
        """Kalenderfelder werden korrekt gespeichert."""
        kal = frappe.get_doc("Kalender", _TEST_CAL_A)
        self.assertEqual(kal.calendar_name, _TEST_CAL_A)
        self.assertEqual(kal.calendar_color, "#3b82f6")
        self.assertIsNotNone(kal.calender_details)

    def test_kalender_requires_name(self):
        """Kalender ohne calendar_name wirft einen Fehler (ValidationError, da autoname=field)."""
        # calendar_name ist autoname-Feld → Frappe wirft ValidationError (nicht MandatoryError)
        with self.assertRaises((frappe.exceptions.ValidationError, frappe.exceptions.MandatoryError)):
            frappe.get_doc({
                "doctype": "Kalender",
                "calendar_color": "#000000",
                "calender_details": "Ohne Name",
                "leserechte": [{"role": "System Manager"}],
            }).insert(ignore_permissions=True)

    def test_kalender_requires_color(self):
        """Kalender ohne Farbe wirft MandatoryError."""
        with self.assertRaises(frappe.exceptions.MandatoryError):
            frappe.get_doc({
                "doctype": "Kalender",
                "calendar_name": "_Test Ohne Farbe XYZ_unique",
                "calender_details": "Ohne Farbe",
                "leserechte": [{"role": "System Manager"}],
            }).insert(ignore_permissions=True)

    def test_kalender_requires_details(self):
        """Kalender ohne calender_details wirft MandatoryError."""
        with self.assertRaises(frappe.exceptions.MandatoryError):
            frappe.get_doc({
                "doctype": "Kalender",
                "calendar_name": "_Test Ohne Details XYZ_unique",
                "calendar_color": "#000000",
                "leserechte": [{"role": "System Manager"}],
            }).insert(ignore_permissions=True)

    def test_kalender_name_is_unique(self):
        """Doppelter Kalender-Name wirft DuplicateEntryError."""
        with self.assertRaises(frappe.exceptions.DuplicateEntryError):
            frappe.get_doc({
                "doctype": "Kalender",
                "calendar_name": _TEST_CAL_A,
                "calendar_color": "#ff0000",
                "calender_details": "Duplikat-Test",
                "leserechte": [{"role": "System Manager"}],
            }).insert(ignore_permissions=True)

    def test_kalender_update_color(self):
        """Kalenderfarbe lässt sich aktualisieren."""
        kal = frappe.get_doc("Kalender", _TEST_CAL_B)
        original = kal.calendar_color
        kal.calendar_color = "#ff00ff"
        kal.save(ignore_permissions=True)
        kal.reload()
        self.assertEqual(kal.calendar_color, "#ff00ff")
        kal.calendar_color = original
        kal.save(ignore_permissions=True)

    def test_selbstverwaltet_default_false(self):
        """selbstverwaltet ist standardmäßig False."""
        kal = frappe.get_doc("Kalender", _TEST_CAL_A)
        self.assertFalse(bool(kal.selbstverwaltet))

    def test_selbstverwaltet_can_be_set_true(self):
        """selbstverwaltet=1 lässt sich setzen und lesen."""
        tmp_name = "_Test Selbstverwaltet TMP"
        if frappe.db.exists("Kalender", tmp_name):
            frappe.delete_doc("Kalender", tmp_name, ignore_permissions=True)

        kal = frappe.get_doc({
            "doctype": "Kalender",
            "calendar_name": tmp_name,
            "calendar_color": "#ff9900",
            "calender_details": "Selbstverwalteter Test-Kalender",
            "selbstverwaltet": 1,
            "leserechte": [{"role": "System Manager"}],
        }).insert(ignore_permissions=True)

        kal.reload()
        self.assertTrue(bool(kal.selbstverwaltet))
        frappe.delete_doc("Kalender", tmp_name, ignore_permissions=True)

    # ------------------------------------------------------------------
    # 2. Kalender × Element Verknüpfung
    # ------------------------------------------------------------------

    def test_element_linked_to_calendar(self):
        """Ein erstelltes Element ist korrekt mit dem Kalender verknüpft."""
        el = _make_element("_Test Kal Link", _TEST_CAL_A)
        self.assertEqual(el.element_calendar, _TEST_CAL_A)

    def test_deleting_element_does_not_affect_calendar(self):
        """Löschen eines Elements lässt den Kalender unberührt."""
        el = _make_element("_Test Kal Del Check", _TEST_CAL_A)
        frappe.delete_doc("Element", el.name, ignore_permissions=True)
        self.assertTrue(frappe.db.exists("Kalender", _TEST_CAL_A),
            "Kalender darf nach Element-Löschung nicht verschwinden")

    # ------------------------------------------------------------------
    # 3. Permissions API (get_accessible_calendars)
    # ------------------------------------------------------------------

    def test_admin_sees_all_calendars(self):
        """Administrator sieht beide Test-Kalender."""
        from diakronos.kronos.api.permissions import get_accessible_calendars

        frappe.set_user("Administrator")
        calendars = get_accessible_calendars()
        names = {c["name"] for c in calendars}
        self.assertIn(_TEST_CAL_A, names)
        self.assertIn(_TEST_CAL_B, names)

    def test_accessible_calendars_have_required_fields(self):
        """Jeder Kalender in get_accessible_calendars hat Pflichtfelder."""
        from diakronos.kronos.api.permissions import get_accessible_calendars

        frappe.set_user("Administrator")
        calendars = get_accessible_calendars()
        self.assertGreater(len(calendars), 0)
        for cal in calendars:
            for field in ("name", "title", "color", "write", "is_moderator"):
                self.assertIn(field, cal,
                    f"Pflichtfeld '{field}' fehlt in Kalender '{cal.get('name')}'")

    def test_admin_has_write_on_all_calendars(self):
        """Administrator hat write=True auf alle Kalender."""
        from diakronos.kronos.api.permissions import get_accessible_calendars

        frappe.set_user("Administrator")
        for cal in get_accessible_calendars():
            self.assertTrue(cal["write"],
                f"Administrator muss Schreibzugriff auf '{cal['name']}' haben")

    def test_writable_is_subset_of_accessible(self):
        """get_writable_calendars ist Teilmenge von get_accessible_calendars."""
        from diakronos.kronos.api.permissions import (
            get_accessible_calendars, get_writable_calendars
        )

        frappe.set_user("Administrator")
        accessible = {c["name"] for c in get_accessible_calendars()}
        writable   = {c["name"] for c in get_writable_calendars()}
        self.assertTrue(writable.issubset(accessible),
            "Schreibbare Kalender müssen Teilmenge der lesbaren Kalender sein")

    def test_calendar_color_non_empty(self):
        """Kalenderfarbe in get_accessible_calendars ist nicht leer."""
        from diakronos.kronos.api.permissions import get_accessible_calendars

        frappe.set_user("Administrator")
        calendars = get_accessible_calendars()
        cal_a = next((c for c in calendars if c["name"] == _TEST_CAL_A), None)
        if cal_a:
            self.assertTrue(len(cal_a["color"]) > 0)

    # ------------------------------------------------------------------
    # 4. get_calendar_events – kalenderübergreifend
    # ------------------------------------------------------------------

    def test_calendar_filter_restricts_events(self):
        """calendar_filter beschränkt Events auf ausgewählte Kalender."""
        import json
        from diakronos.kronos.api.calendar_get import get_calendar_events

        _make_element("_Test Filter A", _TEST_CAL_A, status="Festgelegt")
        _make_element("_Test Filter B", _TEST_CAL_B, status="Festgelegt")

        today = datetime.date.today()
        start = str(today - datetime.timedelta(days=1))
        end   = str(today + datetime.timedelta(days=2))

        events_only_a = get_calendar_events(
            start_date=start, end_date=end,
            calendar_filter=json.dumps([_TEST_CAL_A]),
            view_mode=True
        )
        calendars_in_result = {e["extendedProps"]["element_calendar"] for e in events_only_a}
        if calendars_in_result:
            self.assertNotIn(_TEST_CAL_B, calendars_in_result,
                "calendar_filter=[A] darf keine Events aus Kalender B enthalten")

    def test_no_events_for_empty_calendar_filter(self):
        """calendar_filter=[] gibt leere Liste zurück."""
        import json
        from diakronos.kronos.api.calendar_get import get_calendar_events

        today = datetime.date.today()
        start = str(today - datetime.timedelta(days=1))
        end   = str(today + datetime.timedelta(days=2))

        events = get_calendar_events(
            start_date=start, end_date=end,
            calendar_filter=json.dumps([]),
            view_mode=True
        )
        self.assertEqual(events, [])
