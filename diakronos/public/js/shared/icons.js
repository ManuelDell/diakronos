// ═══════════════════════════════════════════════════════════════════════════
// icons.js – Zentrales Icon-Modul für Diakronos
// Quelle: @tabler/icons (MIT-Lizenz) · https://tabler.io/icons
// Paket: node_modules/@tabler/icons  (npm install @tabler/icons)
//
// PFLICHTDATEI – wird app-weit importiert. Nicht löschen!
// Neue Icons: Pfad aus node_modules/@tabler/icons/icons/outline/<name>.svg kopieren
// ═══════════════════════════════════════════════════════════════════════════

// SVG-Wrapper: stroke-width über CSS-Variable steuerbar (für Active-State-Toggle)
function _svg(paths, size, sw) {
    return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="${size}" height="${size}" fill="none" stroke="currentColor" stroke-width="var(--icon-stroke,${sw})" stroke-linecap="round" stroke-linejoin="round">${paths}</svg>`;
}

// Pfad-Daten aus @tabler/icons/icons/outline/*.svg (verifiziert v3.41.1)
// Bounding-Box-Pfad `<path stroke="none" d="M0 0h24v24H0z"/>` ist bewusst enthalten.
const P = {
    search:          `<path stroke="none" d="M0 0h24v24H0z"/><path d="M3 10a7 7 0 1 0 14 0a7 7 0 1 0-14 0"/><path d="M21 21l-6-6"/>`,
    x:               `<path stroke="none" d="M0 0h24v24H0z"/><path d="M18 6l-12 12"/><path d="M6 6l12 12"/>`,
    calendar:        `<path stroke="none" d="M0 0h24v24H0z"/><path d="M4 7a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-12a2 2 0 0 1-2-2l0-12"/><path d="M16 3l0 4"/><path d="M8 3l0 4"/><path d="M4 11l16 0"/><path d="M11 15h1"/><path d="M12 15v3"/>`,
    repeat:          `<path stroke="none" d="M0 0h24v24H0z"/><path d="M4 12v-3a3 3 0 0 1 3-3h13m-3-3l3 3l-3 3"/><path d="M20 12v3a3 3 0 0 1-3 3h-13m3 3l-3-3l3-3"/>`,
    alertTriangle:   `<path stroke="none" d="M0 0h24v24H0z"/><path d="M12 9v4"/><path d="M10.363 3.591l-8.106 13.534a1.914 1.914 0 0 0 1.636 2.871h16.214a1.914 1.914 0 0 0 1.636-2.87l-8.106-13.536a1.914 1.914 0 0 0-3.274 0"/><path d="M12 16h.01"/>`,
    infoCircle:      `<path stroke="none" d="M0 0h24v24H0z"/><path d="M3 12a9 9 0 1 0 18 0a9 9 0 0 0-18 0"/><path d="M12 9h.01"/><path d="M11 12h1v4h1"/>`,
    building:        `<path stroke="none" d="M0 0h24v24H0z"/><path d="M3 21l18 0"/><path d="M9 8l1 0"/><path d="M9 12l1 0"/><path d="M9 16l1 0"/><path d="M14 8l1 0"/><path d="M14 12l1 0"/><path d="M14 16l1 0"/><path d="M5 21v-16a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v16"/>`,
    chevronDown:     `<path stroke="none" d="M0 0h24v24H0z"/><path d="M6 9l6 6l6-6"/>`,
    chevronLeft:     `<path stroke="none" d="M0 0h24v24H0z"/><path d="M15 6l-6 6l6 6"/>`,
    chevronRight:    `<path stroke="none" d="M0 0h24v24H0z"/><path d="M9 6l6 6l-6 6"/>`,
    eye:             `<path stroke="none" d="M0 0h24v24H0z"/><path d="M10 12a2 2 0 1 0 4 0a2 2 0 0 0-4 0"/><path d="M21 12c-2.4 4-5.4 6-9 6c-3.6 0-6.6-2-9-6c2.4-4 5.4-6 9-6c3.6 0 6.6 2 9 6"/>`,
    eyeOff:          `<path stroke="none" d="M0 0h24v24H0z"/><path d="M10.585 10.587a2 2 0 0 0 2.829 2.828"/><path d="M16.681 16.673a8.717 8.717 0 0 1-4.681 1.327c-3.6 0-6.6-2-9-6c1.272-2.12 2.712-3.678 4.32-4.674m2.86-1.146a9.055 9.055 0 0 1 1.82-.18c3.6 0 6.6 2 9 6c-.666 1.11-1.379 2.067-2.138 2.87"/><path d="M3 3l18 18"/>`,
    pencil:          `<path stroke="none" d="M0 0h24v24H0z"/><path d="M4 20h4l10.5-10.5a2.828 2.828 0 1 0-4-4l-10.5 10.5v4"/><path d="M13.5 6.5l4 4"/>`,
    clock:           `<path stroke="none" d="M0 0h24v24H0z"/><path d="M3 12a9 9 0 1 0 18 0a9 9 0 0 0-18 0"/><path d="M12 7v5l3 3"/>`,
    check:           `<path stroke="none" d="M0 0h24v24H0z"/><path d="M5 12l5 5l10-10"/>`,
    deviceFloppy:    `<path stroke="none" d="M0 0h24v24H0z"/><path d="M6 4h10l4 4v10a2 2 0 0 1-2 2h-12a2 2 0 0 1-2-2v-12a2 2 0 0 1 2-2"/><path d="M10 14a2 2 0 1 0 4 0a2 2 0 1 0-4 0"/><path d="M14 4l0 4l-6 0l0-4"/>`,
    logout:          `<path stroke="none" d="M0 0h24v24H0z"/><path d="M14 8v-2a2 2 0 0 0-2-2h-7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h7a2 2 0 0 0 2-2v-2"/><path d="M9 12h12l-3-3"/><path d="M18 15l3-3"/>`,
    home:            `<path stroke="none" d="M0 0h24v24H0z"/><path d="M5 12l-2 0l9-9l9 9l-2 0"/><path d="M5 12v7a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-7"/><path d="M9 21v-6a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v6"/>`,
    layoutDashboard: `<path stroke="none" d="M0 0h24v24H0z"/><path d="M5 4h4a1 1 0 0 1 1 1v6a1 1 0 0 1-1 1h-4a1 1 0 0 1-1-1v-6a1 1 0 0 1 1-1"/><path d="M5 16h4a1 1 0 0 1 1 1v2a1 1 0 0 1-1 1h-4a1 1 0 0 1-1-1v-2a1 1 0 0 1 1-1"/><path d="M15 12h4a1 1 0 0 1 1 1v6a1 1 0 0 1-1 1h-4a1 1 0 0 1-1-1v-6a1 1 0 0 1 1-1"/><path d="M15 4h4a1 1 0 0 1 1 1v2a1 1 0 0 1-1 1h-4a1 1 0 0 1-1-1v-2a1 1 0 0 1 1-1"/>`,
    layoutColumns:   `<path stroke="none" d="M0 0h24v24H0z"/><path d="M4 6a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-12a2 2 0 0 1-2-2l0-12"/><path d="M12 4l0 16"/>`,
    layoutGridAdd:   `<path stroke="none" d="M0 0h24v24H0z"/><path d="M4 5a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v4a1 1 0 0 1-1 1h-4a1 1 0 0 1-1-1l0-4"/><path d="M14 5a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v4a1 1 0 0 1-1 1h-4a1 1 0 0 1-1-1l0-4"/><path d="M4 15a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v4a1 1 0 0 1-1 1h-4a1 1 0 0 1-1-1l0-4"/><path d="M14 17h6m-3-3v6"/>`,
    calendarEvent:   `<path stroke="none" d="M0 0h24v24H0z"/><path d="M4 7a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-12a2 2 0 0 1-2-2l0-12"/><path d="M16 3l0 4"/><path d="M8 3l0 4"/><path d="M4 11l16 0"/><path d="M8 15h2v2h-2l0-2"/>`,
    arrowDown:       `<path stroke="none" d="M0 0h24v24H0z"/><path d="M12 5l0 14"/><path d="M18 13l-6 6"/><path d="M6 13l6 6"/>`,
    music:           `<path stroke="none" d="M0 0h24v24H0z"/><path d="M3 17a3 3 0 1 0 6 0a3 3 0 0 0-6 0"/><path d="M13 17a3 3 0 1 0 6 0a3 3 0 0 0-6 0"/><path d="M9 17v-13h10v13"/><path d="M9 8h10"/>`,
};

// Generische Icon-Funktion für custom Größen (z.B. in neuen Komponenten)
export function icon(name, size = 24, strokeWidth = 2) {
    return _svg(P[name] ?? '', size, strokeWidth);
}

// ── Benannte Exports (Standardgrößen passend zum jeweiligen Verwendungskontext) ──

// Suche & Navigation
export const ICON_SEARCH         = _svg(P.search,          18, 2);
export const ICON_SEARCH_SM      = _svg(P.search,          16, 2);
export const ICON_CLOSE          = _svg(P.x,               16, 2);
export const ICON_CHEVRON_DOWN   = _svg(P.chevronDown,     12, 2);
export const ICON_CHEVRON_LEFT   = _svg(P.chevronLeft,     23, 2);
export const ICON_CHEVRON_RIGHT  = _svg(P.chevronRight,    23, 2);
export const ICON_ARROW_DOWN     = _svg(P.arrowDown,       28, 1.5);

// Kalender & Zeit
export const ICON_CALENDAR       = _svg(P.calendar,        14, 2);
export const ICON_CALENDAR_LG    = _svg(P.calendar,        16, 2);
export const ICON_CALENDAR_TODAY = _svg(P.calendarEvent,   22, 2);
export const ICON_CLOCK          = _svg(P.clock,           13, 2);
export const ICON_CLOCK_LG       = _svg(P.clock,           16, 2);

// Status & Feedback
export const ICON_CHECK          = _svg(P.check,           14, 2);
export const ICON_CHECK_LG       = _svg(P.check,           16, 2);
export const ICON_CHECK_XL       = _svg(P.check,           15, 2);
export const ICON_WARN           = _svg(P.alertTriangle,   10, 2.5);
export const ICON_WARN_LG        = _svg(P.alertTriangle,   16, 2);
export const ICON_INFO           = _svg(P.infoCircle,      11, 2);
export const ICON_FLOPPY         = _svg(P.deviceFloppy,    16, 2);

// Serien & Wiederholung
export const ICON_REPEAT         = _svg(P.repeat,          12, 2);
export const ICON_REPEAT_SM      = _svg(P.repeat,          11, 2);

// Raum & Ressource
export const ICON_BUILDING       = _svg(P.building,        11, 2);
export const ICON_BUILDING_MD    = _svg(P.building,        13, 2);

// Ansichten & Layouts
// stroke-width über CSS-Variable (--icon-stroke) steuerbar → Active-State via CSS
export const ICON_EYE            = _svg(P.eye,             20, 1.5);
export const ICON_EYE_OFF        = _svg(P.eyeOff,          14, 2);
export const ICON_PENCIL         = _svg(P.pencil,          20, 1.5);
export const ICON_ROOM_VIEW      = _svg(P.layoutColumns,   16, 2);
export const ICON_MODERATION     = _svg(P.layoutGridAdd,   16, 2);
export const ICON_MODERATION_LG  = _svg(P.layoutGridAdd,   18, 2);

// Navigation & User-Menü
export const ICON_LOGOUT         = _svg(P.logout,          16, 2);
export const ICON_HOME           = _svg(P.home,            16, 2);
export const ICON_HOME_SM        = _svg(P.home,            14, 2);
export const ICON_DASHBOARD      = _svg(P.layoutDashboard, 16, 2);
export const ICON_DASHBOARD_SM   = _svg(P.layoutDashboard, 14, 2);

// App-Icons
export const ICON_MUSIC          = _svg(P.music,           20, 2);
