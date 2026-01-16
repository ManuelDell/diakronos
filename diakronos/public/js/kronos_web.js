/**
 * ═══════════════════════════════════════════════════════════════
 * KRONOS - MAIN CALENDAR APPLICATION
 * ═══════════════════════════════════════════════════════════════
 * 
 * Entry Point für die Kronos Web Kalender Anwendung
 * Orchestriert alle Module und Interaktionen
 * 
 * Requires:
 * - FullCalendar 6.1.x
 * - /assets/diakronos/js/modules/element_extract_id.js
 * - /assets/diakronos/js/modules/kronos_calendar.js
 * - /assets/diakronos/js/modules/kronos_web_sidebar.js
 * 
 * ⚠️ WICHTIG: kronos_modal.js wird vom Template geladen, NICHT hier!
 * 
 * Naming: calendar_init_diakronos
 * 
 * 🆕 FIX 1.0.69: Check ob Module bereits statisch geladen sind
 * 🆕 FIX: Verhindere doppeltes Laden von kronos_web_sidebar.js
 */
// ═════════════════════════════════════════════════════════════
// FRAPPE IM HINTERGRUND HALTEN - VOR ALLEM ANDEREN!
// ═════════════════════════════════════════════════════════════

(function() {
  'use strict';
  
  // Verstecke Frappe UI komplett
  setTimeout(() => {
    const frappeUI = document.querySelector('.frappe-control');
    const sidebar = document.querySelector('.sidebar-menu');
    const navbar = document.querySelector('.navbar');
    
    if (frappeUI) {
      frappeUI.style.display = 'none';
      frappeUI.style.visibility = 'hidden';
      frappeUI.style.pointerEvents = 'none';
    }
    if (sidebar) {
      sidebar.style.display = 'none';
      sidebar.style.visibility = 'hidden';
    }
    if (navbar) {
      navbar.style.display = 'none';
      navbar.style.visibility = 'hidden';
    }
    
    // Stelle sicher dass wrapper ALLES überlagert
    const wrapper = document.getElementById('wrapper');
    if (wrapper) {
      wrapper.style.position = 'fixed';
      wrapper.style.top = '0';
      wrapper.style.left = '0';
      wrapper.style.zIndex = '99999';
      wrapper.style.width = '100vw';
      wrapper.style.height = '100vh';
    }
    
    console.log('✅ Frappe UI versteckt, Kronos Vollbildmodus aktiv');
  }, 100);
})();


class KronosApp {
    
    constructor() {
        this.modules = {};
        this.ready = false;
        this.version = '1.0.69';  // ← BUMP: 1.0.69 (Static Module Check)
        
        console.log(`🚀 KronosApp v${this.version} - Initialisiere...`);
        this.init();
    }


    /**
     * Hauptinitialisierung
     * Prüft Abhängigkeiten und startet Kaskade
     */
    init() {
        try {
            this.registerLocale();
            this.waitForFullCalendar();
        } catch (e) {
            console.error('❌ KronosApp Init Error:', e);
            this._showError('Fehler beim Initialisieren der App');
        }
    }


    /**
     * ✅ FIX 1: Registriere deutsche Lokalisierung für FullCalendar
     */
    registerLocale() {
        try {
            if (!FullCalendar.globalLocales) {
                FullCalendar.globalLocales = [];
            }
            
            const deLocale = {
                code: 'de',
                buttonText: {
                    today: 'Heute',
                    month: 'Monat',
                    week: 'Woche',
                    day: 'Tag',
                    list: 'Agenda'
                },
                weekText: 'W',
                allDayText: 'Ganztägig',
                moreLinkText: function(n) {
                    return '+' + n + ' weitere';
                },
                noEventsText: 'Keine Termine',
                firstDay: 1
            };
            
            if (!FullCalendar.globalLocales.find(l => l.code === 'de')) {
                FullCalendar.globalLocales.push(deLocale);
                console.log('✅ Deutsch Locale registriert');
            }
        } catch (e) {
            console.error('❌ Fehler beim Registrieren der Locale:', e);
        }
    }


    /**
     * ✅ FIX 2: Warte bis FullCalendar vollständig geladen ist
     */
    waitForFullCalendar() {
        if (typeof FullCalendar === 'undefined' || !FullCalendar.Calendar) {
            console.log('⏳ Warte auf FullCalendar...');
            setTimeout(() => this.waitForFullCalendar(), 500);
            return;
        }
        
        console.log('✅ FullCalendar bereit!');
        this.loadModules();
    }


    /**
     * 🆕 FIX 1.0.69: Prüfe ob Module bereits statisch geladen sind
     * ═════════════════════════════════════════════════════════════
     * 
     * Problem: Wenn Module sowohl statisch im Template UND dynamisch 
     * via loadScript() geladen werden → redeclaration error
     * 
     * Lösung: Check ob Module bereits da sind, skip dynamisches Laden
     */
    loadModules() {
        console.log('📦 Prüfe ob Module bereits geladen sind...');
        
        // ✅ Check 1: Sind die kritischen Module bereits da?
        const staticModulesReady = (
            typeof ElementExtractId !== 'undefined' &&
            typeof window.KronosSidebar !== 'undefined' &&
            typeof window.kronosCalendar !== 'undefined'
        );
        
        if (staticModulesReady) {
            console.log('✅ Alle Module bereits statisch vom Template geladen!');
            console.log('✅ ElementExtractId:', typeof ElementExtractId);
            console.log('✅ KronosSidebar:', typeof window.KronosSidebar);
            console.log('✅ kronosCalendar:', window.kronosCalendar?.constructor?.name);
            
            // Warte direkt auf KronosModal (wird auch statisch vom Template geladen)
            this.waitForKronosModal();
            return;
        }
        
        // Falls nicht alle Modules vorhanden sind: Lade dynamisch (Fallback)
        console.log('📦 Einige Module fehlen, lade dynamisch als Fallback...');
        
        const baseUrl = '/assets/diakronos/js/modules/';
        
        // SCHRITT 1: Lade ElementExtractId
        this.loadScript(baseUrl + 'element_extract_id.js', () => {
            if (typeof ElementExtractId === 'undefined') {
                console.error('❌ ElementExtractId nicht geladen!');
                this._showError('Fehler beim Laden der erforderlichen Module');
                return;
            }
            console.log('✅ ElementExtractId Modul geladen');
            
            // SCHRITT 2: Lade Sidebar Module
            this.loadScript(baseUrl + 'kronos_web_sidebar.js', () => {
                if (typeof window.KronosSidebar === 'undefined') {
                    console.error('❌ KronosSidebar nicht geladen!');
                    this._showError('Fehler beim Laden der Sidebar');
                    return;
                }
                console.log('✅ KronosSidebar Modul geladen');
                
                // SCHRITT 3: Lade KronosCalendar
                this.loadScript(baseUrl + 'kronos_calendar.js', () => {
                    if (typeof window.kronosCalendar === 'undefined') {
                        console.error('❌ KronosCalendar nicht geladen!');
                        this._showError('Fehler beim Laden des Kalenders');
                        return;
                    }
                    console.log('✅ KronosCalendar Modul geladen');
                    
                    // Warte bis KronosModal verfügbar ist
                    this.waitForKronosModal();
                });
            });
        });
    }


    /**
     * 🆕 WAIT FOR KRONOS MODAL
     * Warte bis das Modal-Modul vom Template geladen wurde
     */
    waitForKronosModal() {
        if (typeof window.KronosModal === 'undefined') {
            console.log('⏳ Warte auf KronosModal vom Template...');
            setTimeout(() => this.waitForKronosModal(), 100);
            return;
        }
        
        console.log('✅ KronosModal Modul vom Template geladen');
        this.start();
    }


    /**
     * ✅ FIX 4: Script-Loading mit Error-Handling
     * Verwende Versionsnummer statt Math.random() für Cache-Busting
     */
    loadScript(src, callback) {
        try {
            const script = document.createElement('script');
            // ✅ Besseres Cache-Busting: Versionsnummer verwenden
            const version = window.DIAKRONOS_VERSION || this.version;
            script.src = src + '?v=' + version;
            script.async = true;
            script.onerror = () => {
                console.error('❌ Fehler beim Laden von:', src);
                this._showError(`Fehler beim Laden: ${src}`);
            };
            script.onload = () => {
                console.log(`✅ Geladen: ${src}`);
                callback();
            };
            document.head.appendChild(script);
        } catch (e) {
            console.error('❌ Script Load Error:', e);
            this._showError('Fehler beim Laden der Module');
        }
    }


    /**
     * ✅ FIX 5: Starte App wenn alle Module bereit sind
     */
    start() {
        try {
            console.log('🎯 Starte App...');
            
            // ✅ Validiere dass Kalender existiert
            if (!window.kronosCalendar || typeof window.kronosCalendar.init !== 'function') {
                throw new Error('KronosCalendar nicht initialisierbar');
            }
            
            // ✅ Validiere dass Modal existiert
            if (typeof window.KronosModal === 'undefined') {
                console.warn('⚠️ KronosModal immer noch nicht verfügbar!');
                console.warn('⚠️ Modal-Funktionen könnten fehlschlagen');
            }
            
            // 🆕 Initialisiere Sidebar Module (wenn nicht bereits gemacht)
            if (typeof window.KronosSidebar !== 'undefined' && !window.kronosSidebar) {
                try {
                    window.kronosSidebar = new window.KronosSidebar();
                    window.kronosSidebar.init();
                    console.log('✅ KronosSidebar initialisiert');
                } catch (e) {
                    console.warn('⚠️ Fehler beim Initialisieren von KronosSidebar:', e);
                }
            }
            
            window.kronosCalendar.init();
            this.setupWeekNumbers();
            this.setupDarkModeToggle(); 
            this.setupSmoothResize();
            this.setupControls();
            // ❌ NICHT: this.setupSidebarToggle();
            this.setupWindowResize();
            this.setGreeting();
            this.updateMonth();
            
            this.ready = true;
            console.log('✨ KronosApp bereit!');
        } catch (e) {
            console.error('❌ Fehler beim Starten der App:', e);
            this._showError('Fehler beim Starten der App');
        }
    }



    /**
     * 🆕 SETUP WEEK NUMBERS
     * ═════════════════════════════════════════════════════════════
     * 
     * Aktiviert Wochennummern mit Custom Format (nur Nummern, keine W)
     * Wird direkt nach Calendar-Initialisierung aufgerufen
     */
    setupWeekNumbers() {
        try {
            console.log('📅 Aktiviere Wochennummern...');
            
            // Warte kurz bis Calendar vollständig initialisiert ist
            setTimeout(() => {
                if (!window.kronosCalendar || !window.kronosCalendar.calendar) {
                    console.warn('⚠️ FullCalendar nicht verfügbar für Week Numbers');
                    return;
                }
                
                // ✅ Aktiviere Wochennummern
                window.kronosCalendar.calendar.setOption('weekNumbers', true);
                
                // ✅ ISO 8601 Standard (Woche beginnt Montag)
                window.kronosCalendar.calendar.setOption('weekNumberCalculation', 'ISO');
                
                // ✅ Custom Format: nur Nummer (1, 2, 3...) ohne "W"
                window.kronosCalendar.calendar.setOption('weekNumberFormat', {
                    week: 'numeric'
                });
                
                console.log('✅ Wochennummern aktiviert! (ISO 8601, ohne W-Prefix)');
            }, 100);
        } catch (e) {
            console.error('❌ setupWeekNumbers Error:', e);
        }
    }


    setupDarkModeToggle() {
        try {
            const checkbox = document.getElementById('darkmode-checkbox');
            if (!checkbox) {
                console.warn('⚠️ #darkmode-checkbox nicht gefunden');
                return;
            }

            // ✅ Lade gespeicherte Preference
            const saved = localStorage.getItem('kronos-darkmode');
            const prefersLight = !window.matchMedia('(prefers-color-scheme: dark)').matches;
            const isDark = saved ? saved === 'true' : !prefersLight;
            
            if (isDark) {
                checkbox.checked = true;
                this._enableDarkMode();
            } else {
                checkbox.checked = false;
                this._disableDarkMode();
            }

            // ✅ Change Handler
            checkbox.addEventListener('change', (e) => {
                if (e.target.checked) {
                    this._enableDarkMode();
                } else {
                    this._disableDarkMode();
                }
            });

            console.log('✅ Dark Mode Toggle setup fertig');
        } catch (e) {
            console.error('❌ setupDarkModeToggle Error:', e);
        }
    }


    _enableDarkMode() {
        document.documentElement.setAttribute('data-color-scheme', 'dark');
        localStorage.setItem('kronos-darkmode', 'true');
        console.log('🌙 Dark Mode aktiviert');
    }


    _disableDarkMode() {
        document.documentElement.setAttribute('data-color-scheme', 'light');
        localStorage.setItem('kronos-darkmode', 'false');
        console.log('☀️ Light Mode aktiviert');
    }


    /**
     * 🆕 SETUP SMOOTH RESIZE ANIMATIONS
     * ═════════════════════════════════════════════════════════════
     * 
     * Integriert CSS Transitions + ResizeObserver für smooth Calendar Resizing
     * Dies ist die HAUPTLÖSUNG für das Smooth Resize Problem!
     */
    setupSmoothResize() {
        try {
            console.log('🎯 Aktiviere Smooth Resize Animations...');
            
            const calendarWrapper = document.querySelector('.calendar-wrapper');
            const kronosApp = document.getElementById('kronos-app');
            const fcElement = document.querySelector('.fc');
            
            // ✅ 1. CSS Transitions auf dem Wrapper Container
            if (calendarWrapper) {
                calendarWrapper.style.transition = 'all 400ms cubic-bezier(0.16, 1, 0.3, 1)';
                calendarWrapper.style.willChange = 'height, width';
            }
            
            // ✅ 2. CSS Transitions auf FullCalendar selbst
            if (fcElement) {
                fcElement.style.transition = 'height 400ms cubic-bezier(0.16, 1, 0.3, 1), width 400ms cubic-bezier(0.16, 1, 0.3, 1)';
            }
            
            // ✅ 3. ResizeObserver für Größenänderungen
            let resizeDebounce;
            const resizeObserver = new ResizeObserver(() => {
                clearTimeout(resizeDebounce);
                resizeDebounce = setTimeout(() => {
                    if (window.kronosCalendar && window.kronosCalendar.calendar) {
                        window.kronosCalendar.calendar.updateSize();
                        console.log('🔄 ResizeObserver: updateSize() aufgerufen');
                    }
                }, 100);
            });
            
            // Beobachte nur wenn kronosApp existiert
            if (kronosApp) {
                resizeObserver.observe(kronosApp);
                this.resizeObserver = resizeObserver; // Für Cleanup
            }
            
            // ✅ 4. Hook für View-Änderungen
            if (window.kronosCalendar && window.kronosCalendar.calendar) {
                window.kronosCalendar.calendar.on('datesSet', () => {
                    setTimeout(() => {
                        if (window.kronosCalendar && window.kronosCalendar.calendar) {
                            window.kronosCalendar.calendar.updateSize();
                            console.log('🔄 datesSet Hook: updateSize() aufgerufen');
                        }
                    }, 50);
                });
            }
            
            console.log('✅ Smooth Resize Animations aktiviert!');
        } catch (e) {
            console.error('❌ setupSmoothResize Error:', e);
        }
    }


    /**
     * ✅ FIX 5: Setup mit delegierten Event Listenern
     * Speichere Referenzen um später cleanup zu ermöglichen
     */
    setupControls() {
        try {
            const self = this;
            
            // Sammle Event Listener für Cleanup
            this.eventListeners = [];
            
            const setupButton = (id, callback) => {
                const el = document.getElementById(id);
                if (!el) {
                    console.warn(`⚠️ Element #${id} nicht gefunden`);
                    return;
                }
                
                el.addEventListener('click', callback);
                this.eventListeners.push({ el, callback });
            };
            
            // Navigation
            setupButton('prev-month', () => {
                if (window.kronosCalendar?.prev) {
                    window.kronosCalendar.prev();
                    self.updateMonth();
                }
            });
            
            setupButton('next-month', () => {
                if (window.kronosCalendar?.next) {
                    window.kronosCalendar.next();
                    self.updateMonth();
                }
            });
            
            setupButton('today-button', () => {
                if (window.kronosCalendar?.today) {
                    window.kronosCalendar.today();
                    self.updateMonth();
                }
            });
            
            // View Switcher
            setupButton('month-view', () => {
                if (window.kronosCalendar?.changeView) {
                    window.kronosCalendar.changeView('dayGridMonth');
                    self._updateViewButtons('month');
                }
            });
            
            setupButton('week-view', () => {
                if (window.kronosCalendar?.changeView) {
                    window.kronosCalendar.changeView('timeGridWeek');
                    self._updateViewButtons('week');
                }
            });
            
            // Back Button - Navigiere zur Übersichtsseite
            setupButton('back-button', () => {
                window.location.href = '/app/übersichtsseite';
            });

            console.log('✅ Controls setup fertig');
        } catch (e) {
            console.error('❌ Setup Controls Error:', e);
        }
    }


    /**
     * 🆕 SIDEBAR TOGGLE MIT FULLCALENDAR RESIZE
     * ═════════════════════════════════════════
     * 
     * Das ist die KRITISCHE FUNKTION für die Sidebar!
     * 
     * Problem: Wenn die Grid-Spalten wechseln (0 1fr ↔ 250px 1fr),
     * merkt FullCalendar davon NICHTS und bleibt bei der alten Breite.
     * 
     * Lösung: Nach der CSS-Transition updateSize() aufrufen!
     * 
     * Transition dauert 0.4s → wir warten 420ms und rufen updateSize() auf
     */


    /**
     * 🆕 WINDOW RESIZE LISTENER
     * ═════════════════════════
     * 
     * Falls sich die Browser-Breite ändert (z.B. bei Responsive),
     * auch dann updateSize() aufrufen
     */
    setupWindowResize() {
        try {
            const self = this;

            window.addEventListener('resize', () => {
                // Mit Debounce: nur alle 250ms aufrufen
                if (this.resizeTimeout) {
                    clearTimeout(this.resizeTimeout);
                }

                this.resizeTimeout = setTimeout(() => {
                    console.log('📏 Window Resize erkannt, Update Calendar Size');
                    self._updateCalendarSize();
                }, 250);
            });

            console.log('✅ Window Resize Listener setup fertig');
        } catch (e) {
            console.error('❌ Window Resize Setup Error:', e);
        }
    }


    /**
     * 🆕 UPDATE CALENDAR SIZE
     * ═══════════════════════
     * 
     * ZENTRALE HILFSFUNKTION: Ruft calendar.updateSize() auf
     * wenn FullCalendar verfügbar ist
     */
    _updateCalendarSize() {
        try {
            if (!window.kronosCalendar || !window.kronosCalendar.calendar) {
                console.warn('⚠️ FullCalendar nicht verfügbar für updateSize()');
                return;
            }

            console.log('🔄 FullCalendar updateSize() wird aufgerufen...');
            window.kronosCalendar.calendar.updateSize();
            console.log('✅ Calendar Size updated!');
        } catch (e) {
            console.error('❌ updateCalendarSize Error:', e);
        }
    }


    /**
     * ✅ FIX 6: Aktualisiere View-Buttons mit korrekter Logik
     */
    _updateViewButtons(activeView) {
        try {
            const monthBtn = document.getElementById('month-view');
            const weekBtn = document.getElementById('week-view');
            
            if (monthBtn) {
                monthBtn.classList.toggle('active', activeView === 'month');
            }
            if (weekBtn) {
                weekBtn.classList.toggle('active', activeView === 'week');
            }
        } catch (e) {
            console.error('❌ Update View Buttons Error:', e);
        }
    }


    /**
     * ✅ FIX 2: Aktualisiere Monatszahl sicher
     */
    updateMonth() {
        try {
            if (!window.kronosCalendar || typeof window.kronosCalendar.getDate !== 'function') {
                return;
            }
            
            const date = window.kronosCalendar.getDate();
            if (!date) return;
            
            const monthStr = new Intl.DateTimeFormat('de-DE', { 
                month: 'long', 
                year: 'numeric' 
            }).format(date);
            
            const month = monthStr.charAt(0).toUpperCase() + monthStr.slice(1);
            const headerEl = document.getElementById('current-month-header');
            if (headerEl) {
                headerEl.textContent = month;
            }
        } catch (e) {
            console.error('❌ Update Month Error:', e);
        }
    }


    /**
     * ✅ FIX 2: Setze Begrüßung mit korrekten Frappe Properties
     */
    setGreeting() {
        try {
            const hour = new Date().getHours();
            const greeting = hour < 12 ? '🌅 Guten Morgen' : 
                             hour < 18 ? '☀️ Guten Mittag' : 
                             '🌙 Guten Abend';
            
            // ✅ Korrekte Frappe Session Properties
            let name = '';
            if (frappe.session && frappe.session.user_fullname) {
                name = frappe.session.user_fullname.split(' ')[0] || '';
            }
            
            const text = name ? `${greeting}, ${name}` : greeting;
            const greetingEl = document.getElementById('greeting-title');
            if (greetingEl) {
                greetingEl.textContent = text;
            }
        } catch (e) {
            console.error('❌ Set Greeting Error:', e);
        }
    }


    /**
     * ✅ FIX 2: Zeige Fehler mit frappe.show_alert() statt alert()
     */
    _showError(message) {
        try {
            frappe.show_alert({
                message: message,
                indicator: 'red'
            });
        } catch (e) {
            console.error('❌ Show Error:', message, e);
            // Fallback wenn Frappe nicht verfügbar
            console.error('ERROR:', message);
        }
    }


    /**
     * ✅ FIX 5: Cleanup-Methode zum Entfernen von Event Listenern
     */
    cleanup() {
        try {
            if (this.eventListeners) {
                this.eventListeners.forEach(({ el, callback }) => {
                    el.removeEventListener('click', callback);
                });
            }
            
            // Cleanup Window Resize
            if (this.resizeTimeout) {
                clearTimeout(this.resizeTimeout);
            }
            
            // Cleanup ResizeObserver
            if (this.resizeObserver) {
                this.resizeObserver.disconnect();
            }

            // Cleanup Sidebar Module
            if (window.kronosSidebar && typeof window.kronosSidebar.cleanup === 'function') {
                window.kronosSidebar.cleanup();
            }

            console.log('✅ Cleanup fertig');
        } catch (e) {
            console.error('❌ Cleanup Error:', e);
        }
    }
}


/**
 * ✅ Initialisiere App wenn DOM bereit ist
 */
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        try {
            window.kronosApp = new KronosApp();
        } catch (e) {
            console.error('❌ KronosApp Creation Error:', e);
        }
    });
} else {
    try {
        window.kronosApp = new KronosApp();
    } catch (e) {
        console.error('❌ KronosApp Creation Error:', e);
    }
}