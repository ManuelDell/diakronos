// ✅ KRONOS CALENDAR SMOOTH RESIZE - FullCalendar v6.1.16
// Datei: kronos_calendar_smooth.js
// Kopiere das in deine kronos_web.js NACH der Calendar-Initialisierung

(function() {
    'use strict';

    // Finde den Calendar vom Window (wird von kronos_web.js gesetzt)
    let calendar = window.kronosCalendar || null;

    if (!calendar) {
        console.error('❌ kronosCalendar nicht gefunden');
        return;
    }

    // ✅ 1. CSS Transitions auf dem Container
    const calendarWrapper = document.querySelector('.calendar-wrapper');
    const kronosApp = document.getElementById('kronos-app');
    
    if (calendarWrapper) {
        calendarWrapper.style.transition = 'all 400ms cubic-bezier(0.16, 1, 0.3, 1)';
        calendarWrapper.style.willChange = 'height, width';
    }

    // ✅ 2. FullCalendar selbst mit Transition
    const fcElement = document.querySelector('.fc');
    if (fcElement) {
        fcElement.style.transition = 'height 400ms cubic-bezier(0.16, 1, 0.3, 1), width 400ms cubic-bezier(0.16, 1, 0.3, 1)';
    }

    // ✅ 3. ResizeObserver - beobachte Größenänderungen
    let resizeTimeout;
    const resizeObserver = new ResizeObserver(() => {
        clearTimeout(resizeTimeout);
        resizeTimeout = setTimeout(() => {
            if (calendar && calendar.updateSize) {
                calendar.updateSize();
            }
        }, 100); // Debounce: nur 1x pro 100ms rechnen
    });

    // Beobachte den Kronos App Container
    if (kronosApp) {
        resizeObserver.observe(kronosApp);
    }

    // ✅ 4. Bei View-Wechsel smooth animieren
    // Hook für datesSet (wenn sich die Ansicht ändert)
    calendar.on('datesSet', function() {
        // View hat sich geändert → trigger smooth resize
        setTimeout(() => {
            if (calendar && calendar.updateSize) {
                calendar.updateSize();
            }
        }, 50);
    });

    // ✅ 5. Auch bei Window Resize smooth animieren
    let windowResizeTimeout;
    window.addEventListener('resize', () => {
        clearTimeout(windowResizeTimeout);
        windowResizeTimeout = setTimeout(() => {
            if (calendar && calendar.updateSize) {
                calendar.updateSize();
            }
        }, 200);
    }, { passive: true });

    // ✅ 6. Sidebar Toggle - auch smooth animieren
    const menuToggle = document.getElementById('menu-toggle');
    if (menuToggle) {
        menuToggle.addEventListener('click', () => {
            setTimeout(() => {
                if (calendar && calendar.updateSize) {
                    calendar.updateSize();
                }
            }, 420); // Nach der Transition-Animation (400ms)
        });
    }

    console.log('✅ Kronos Smooth Resize aktiviert');
})();