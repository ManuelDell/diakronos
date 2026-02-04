// kronos.bundle.js – optimierte Ladereihenfolge für www-Seiten

// 1. Kern-Klassen & Utilities (müssen zuerst da sein)
import './kronos_calendar.js';                // definiert window.kronosCalendar
import './kronos_events.js';                 // Events
import './element_extract_id.js';            // Hilfsfunktionen
import './diagnostics.js';                   // Debugging (optional, aber früh)

// 2. Modale & Helfer (brauchen Kalender + Events)
import './kronos_modal.js';
import './modal/modal_base.js';
import './modal/modal_create_dialog.js';
import './modal/modal_event_click.js';
import './modal/modal_helpers.js';
import './modal/modal_series_handler.js';
import './modal/modal_smart_edit.js';
import './kronos_mini_calendar.js';          // Mini-Kalender nutzt FullCalendar

// 3. Builder-Module (bauen UI auf Basis der Klassen)
import './builder/header_build_elements.js'; // braucht Kalender für Navigation
import './builder/sidebar_build_elements.js'; // braucht Kalender für Mini-Kalender
import './builder/calendar_build_init.js';   // letzter Schritt: fügt alles zusammen

console.log('✅ Kronos Bundle geladen – bereit');