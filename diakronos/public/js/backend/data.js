// diakronos/public/js/backend/data.js

export async function fetch_accessible_calendars() {
    try {
        // Direkter REST-API Aufruf an Frappe
        const response = await fetch('/api/method/diakronos.kronos.api.calendar_get.get_accessible_calendars', {
            method: 'GET',
            headers: {
                'Accept': 'application/json',
                'Content-Type': 'application/json'
            }
        });

        if (!response.ok) {
            throw new Error(`HTTP Fehler! Status: ${response.status}`);
        }

        const data = await response.json();
        
        // Frappe verpackt die Antwort immer in einem "message" Objekt
        const calendars = data.message;

        if (calendars && Array.isArray(calendars)) {
            if (window.kronosState) {
                window.kronosState.setAvailableCalendars(calendars);
                const initialSelected = calendars.map(cal => cal.name);
                window.kronosState.setSelectedCalendars(initialSelected);
            }
            return true;
        } else {
            console.warn('⚠️ Data-Fetch: Keine Kalender in der Antwort gefunden');
            return false;
        }
    } catch (err) {
        console.error('❌ Data-Fetch Fehler:', err);
        return false;
    }
}

// true = View-Modus (Standard, nur Lesen), false = Bearbeitungs-Modus
let viewMode = true;

export const setViewMode = (val) => { viewMode = !!val; };
export const getViewMode = () => viewMode;


// --- CALENDAR FILTER STATE ---
// Array mit den Namen der ausgewählten Kalender. Leer = Alle anzeigen.
let selectedCalendars = [];

export const setSelectedCalendars = (calendarsArray) => { selectedCalendars = calendarsArray || []; };
export const getSelectedCalendars = () => selectedCalendars;

// TEMPORÄR FÜR DIE KONSOLE ZUM TESTEN:
//window.test_fetch_calendars = fetch_accessible_calendars;
