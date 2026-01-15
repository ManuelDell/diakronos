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
 * 
 * ⚠️ WICHTIG: kronos_modal.js wird vom Template geladen, NICHT hier!
 * 
 * Naming: calendar_init_diakronos
 */



class KronosApp {
    
    constructor() {
        this.modules = {};
        this.ready = false;
        this.version = '1.0.25';  // ← BUMP: 1.0.25 (Modal Timing-Fix)
        
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
     * ✅ FIX 3: Lade alle abhängigen Module in korrekter Reihenfolge
     * ✅ FIX 7: Prüfe ob Module existieren vor Nutzung
     * 
     * 🔧 GEFIXT: Lade Module in DIESER REIHENFOLGE:
     * 1. element_extract_id.js    (Dependency für andere)
     * 2. kronos_calendar.js       (Nutzt KronosModal vom Template)
     * 
     * ⚠️ kronos_modal.js wird vom Template geladen, NICHT hier!
     */
    loadModules() {
        console.log('📦 Lade Module in korrekter Reihenfolge...');
        
        const baseUrl = '/assets/diakronos/js/modules/';
        
        // SCHRITT 1: Lade ElementExtractId
        this.loadScript(baseUrl + 'element_extract_id.js', () => {
            if (typeof ElementExtractId === 'undefined') {
                console.error('❌ ElementExtractId nicht geladen!');
                this._showError('Fehler beim Laden der erforderlichen Module');
                return;
            }
            console.log('✅ ElementExtractId Modul geladen');
            
            // SCHRITT 2: Lade KronosCalendar
            // KronosModal wird vom Template geladen (asynchron)
            this.loadScript(baseUrl + 'kronos_calendar.js', () => {
                if (typeof window.kronosCalendar === 'undefined') {
                    console.error('❌ KronosCalendar nicht geladen!');
                    this._showError('Fehler beim Laden des Kalenders');
                    return;
                }
                console.log('✅ KronosCalendar Modul geladen');
                
                // Warte bis KronosModal verfügbar ist (vom Template)
                this.waitForKronosModal();
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
            
            window.kronosCalendar.init();
            this.setupControls();
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
