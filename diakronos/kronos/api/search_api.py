"""
Kronos Terminsuche – Wasserfall: Titel → Kalender/Raum → Beschreibung
"""
import frappe
from diakronos.kronos.api.permissions import get_accessible_calendars


@frappe.whitelist(allow_guest=False)
def search_events(query, limit=15):
    """
    Sucht Termine in zugänglichen Kalendern.
    Wasserfallstrategie: erst Titel, dann +Kalender/Raum, dann +Beschreibung.
    Serientermine werden gruppiert (frühste Instanz, count).
    """
    if not query or len(query.strip()) < 2:
        return []

    q = f"%{query.strip()}%"
    limit = min(int(limit), 50)

    allowed = [c["name"] for c in get_accessible_calendars()]
    if not allowed:
        return []

    in_ph = ", ".join(["%s"] * len(allowed))

    def run(extra_cond="", extra_vals=None):
        sql = f"""
            SELECT
                e.name          AS id,
                e.element_name  AS title,
                e.element_start AS start,
                e.all_day,
                e.series_id,
                e.element_calendar,
                c.calendar_name AS calendar_title,
                c.calendar_color AS calendar_color
            FROM `tabElement` e
            LEFT JOIN `tabKalender` c ON c.name = e.element_calendar
            WHERE e.element_calendar IN ({in_ph})
              AND (e.element_name LIKE %s{extra_cond})
            ORDER BY e.element_start ASC
            LIMIT {limit}
        """
        params = allowed + [q] + (extra_vals or [])
        return frappe.db.sql(sql, params, as_dict=True)

    rows = run()
    if not rows:
        rows = run(
            " OR c.calendar_name LIKE %s OR e.ressource LIKE %s",
            [q, q]
        )
    if not rows:
        rows = run(
            " OR c.calendar_name LIKE %s OR e.ressource LIKE %s OR e.description LIKE %s",
            [q, q, q]
        )

    # Serien gruppieren: frühste Instanz bleibt, count hochzählen
    seen, result = {}, []
    for r in rows:
        key = r.series_id or r.id
        if key in seen:
            seen[key]["series_count"] += 1
        else:
            r["is_series"] = bool(r.series_id)
            r["series_count"] = 1
            seen[key] = r
            result.append(r)

    return result
