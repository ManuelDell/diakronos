// shared/state.js – Zustandsverwaltung für Diakronos

// Zustand initialisieren
const state = {
    userRoles: [],
    viewMode: 'view', // 'view' oder 'edit'
    currentCalendar: null,
    filters: {},
    lastUpdated: null
};

// Zustand setzen
function setState(key, value) {
    // Wenn viewMode geändert wird, speichern und evtl spezifisches Event auslösen
    const oldValue = state[key];
    if (key === 'viewMode') {
        state[key] = (value === 'edit') ? 'edit' : 'view';
        // Wenn sich der Wert geändert hat, löse spezifisches Event aus
        if (oldValue !== state[key]) {
            document.dispatchEvent(new CustomEvent('viewModeChanged', { 
                detail: { 
                    newValue: state[key], 
                    oldValue: oldValue 
                } 
            }));
        }
    } else {
        state[key] = value;
    }
    // Allgemeines Event für andere Module 
    document.dispatchEvent(new CustomEvent('stateChanged', { detail: { key, value: state[key] } }));
}

// Zustand abrufen
function getState(key) {
    if (key === undefined) {
        return state;
    }
    return state[key];
}

// Zustand löschen
function clearState(key) {
    if (key) {
        delete state[key];
    } else {
        Object.keys(state).forEach(k => delete state[k]);
    }
    document.dispatchEvent(new CustomEvent('stateCleared', { detail: { key } }));
}

// Nutzenrolle-Helfer
function getUserRoles() {
    return getState('userRoles');
}

// Initialisierungsfunktion
function initStateFromDOM() {
    const userRoles = JSON.parse(document.body.dataset.userRoles || '[]');
    setState('userRoles', userRoles);
    // Initialisiere viewMode aus dem DOM, falls vorhanden, sonst 'view'
    const initialViewMode = document.body.dataset.viewMode || 'view';
    setState('viewMode', initialViewMode);
    setState('lastUpdated', new Date().toISOString());
}

// Hilfsfunktion zum Abrufen des aktuellen View-Modus
function getCurrentViewMode() {
    return getState('viewMode');
}

// Öffentliche API exportieren
export { setState, getState, clearState, getUserRoles, initStateFromDOM, getCurrentViewMode };

