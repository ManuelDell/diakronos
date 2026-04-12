// diakronos/public/js/backend/data.js

// Importiere setState und getState aus dem gemeinsamen Zustandsmodul
import { setState, getState } from '../shared/state.js';

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

// Funktion zum Setzen des View-Modus
export const setViewMode = (val) => {
    // 'true' bedeutet View-Modus, 'false' Bearbeitungsmodus
    const mode = val ? 'view' : 'edit';
    setState('viewMode', mode);
};

// Funktion zum Abrufen des View-Modus
export const getViewMode = () => {
    const mode = getState('viewMode');
    // Rückgabe als boolean für Abwärtskompatibilität
    return mode !== 'edit';
};


// --- CALENDAR FILTER STATE ---
export const setSelectedCalendars = (calendarsArray) => {
    setState('selectedCalendars', calendarsArray || []);
};

export const getSelectedCalendars = () => {
    const val = getState('selectedCalendars');
    return val !== undefined ? val : [];
};
