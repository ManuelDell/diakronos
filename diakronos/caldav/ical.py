# diakronos/caldav/ical.py – Frappe Element → iCalendar (.ics)


def _escape(text):
    """iCal-Sonderzeichen escapen (RFC 5545)."""
    if not text:
        return ''
    return (str(text)
            .replace('\\', '\\\\')
            .replace('\n', '\\n')
            .replace(',', '\\,')
            .replace(';', '\\;'))


def _fmt_dt(dt, all_day=False):
    """Datetime → iCal-Datumsstring."""
    if not dt:
        return ''
    if all_day:
        return dt.strftime('%Y%m%d')
    return dt.strftime('%Y%m%dT%H%M%S')


def element_to_ical(el):
    """
    Wandelt ein Frappe-Element-Dokument in einen iCalendar-String um.
    Gibt einen vollständigen VCALENDAR-Block zurück.
    """
    all_day = bool(el.all_day)

    if all_day:
        dtstart = f'DTSTART;VALUE=DATE:{_fmt_dt(el.element_start, True)}'
        dtend   = f'DTEND;VALUE=DATE:{_fmt_dt(el.element_end,   True)}'
    else:
        dtstart = f'DTSTART:{_fmt_dt(el.element_start)}'
        dtend   = f'DTEND:{_fmt_dt(el.element_end)}'

    lines = [
        'BEGIN:VCALENDAR',
        'VERSION:2.0',
        'PRODID:-//Diakronos//Kronos CalDAV//DE',
        'CALSCALE:GREGORIAN',
        'BEGIN:VEVENT',
        f'UID:{el.name}@diakronos',
        f'SUMMARY:{_escape(el.element_name)}',
        dtstart,
        dtend,
    ]

    if el.description:
        lines.append(f'DESCRIPTION:{_escape(el.description)}')

    if el.series_id:
        lines.append(f'RELATED-TO;RELTYPE=SIBLING:{el.series_id}')

    # Letzte Änderung für ETags / Sync
    if el.modified:
        lines.append(f'LAST-MODIFIED:{el.modified.strftime("%Y%m%dT%H%M%SZ")}')

    lines += ['END:VEVENT', 'END:VCALENDAR']
    return '\r\n'.join(lines)
