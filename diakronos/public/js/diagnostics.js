/**
 * ═══════════════════════════════════════════════════════════════
 * DIAKRONOS DIAGNOSTICS SUITE (FullCalendar 6 optimiert)
 * ═══════════════════════════════════════════════════════════════
 * NUR MANUELL aufrufen: DiakronosDiagnostics.run()
 */

class DiakronosDiagnostics {
    static run() {
        console.clear();
        console.log('╔════════════════════════════════════════════╗');
        console.log('║  🔍 DIAKRONOS DIAGNOSTIC SUITE START       ║');
        console.log('╚════════════════════════════════════════════╝\n');
        
        this.checkAssets();
        this.checkFullCalendar();
        this.checkFullCalendarPlugins();
        this.checkKronosClasses();
        this.checkDOM();
        this.checkFrappe();
        this.checkCalendarInstance();
        
        console.log('\n═══════════════════════════════════════════════');
        console.log('✅ DIAGNOSTIC COMPLETE\n');
    }

    static checkAssets() {
        console.group('📦 Asset Loading Check');
        
        // CSS Check
        const cssLinks = Array.from(document.querySelectorAll('link[rel="stylesheet"]'));
        const kronoscss = cssLinks.find(l => l.href.includes('kronos.bundle'));
        const fcCss = cssLinks.find(l => l.href.includes('fullcalendar'));
        
        console.log(`CSS Bundle (kronos.bundle.*.css):`);
        if (kronoscss) {
            console.log(`✅ Geladen: ${kronoscss.href.split('/').pop()}`);
        } else {
            console.error(`❌ NICHT geladen! Suche verfügbar:`);
            cssLinks.forEach(l => {
                if (l.href.includes('diakronos')) {
                    console.log(`   - ${l.href}`);
                }
            });
        }
        
        console.log(`\nFullCalendar CSS (via Bundle):`);
        if (fcCss) {
            console.log(`✅ Zusätzlich geladen: ${fcCss.href.split('/').pop()}`);
        } else {
            console.log(`ℹ️ Nicht separat - sollte im kronos.bundle.css sein`);
        }
        
        // JS Check
        const scripts = Array.from(document.querySelectorAll('script[src]'));
        const kronosjs = scripts.find(s => s.src.includes('kronos.bundle'));
        
        console.log(`\nJS Bundle (kronos.bundle.*.js):`);
        if (kronosjs) {
            console.log(`✅ Geladen: ${kronosjs.src.split('/').pop()}`);
            console.log(`   Größe: ${kronosjs.getAttribute('data-size') || 'unknown'}`);
        } else {
            console.error(`❌ NICHT geladen! Verfügbar:`);
            scripts.forEach(s => {
                if (s.src.includes('diakronos')) {
                    console.log(`   - ${s.src.split('/').pop()}`);
                }
            });
        }
        
        console.groupEnd();
    }

    static checkFullCalendar() {
        console.group('🗓️ FullCalendar 6 Check');
        
        if (typeof window.FullCalendar === 'undefined') {
            console.error('❌ window.FullCalendar NOT FOUND!');
            console.log('Suche nach alternativen...');
            
            const calKeys = Object.keys(window).filter(k => 
                k.toLowerCase().includes('calendar') || 
                k.toLowerCase().includes('fullcalendar')
            );
            
            if (calKeys.length > 0) {
                console.log('⚠️ Gefundene Keys:');
                calKeys.forEach(k => console.log(`   - ${k}`));
            } else {
                console.error('❌ KEIN FullCalendar gefunden!');
            }
        } else {
            console.log('✅ window.FullCalendar vorhanden');
            
            // Check Constructor
            if (typeof window.FullCalendar.Calendar === 'function') {
                console.log('✅ Calendar-Konstruktor vorhanden');
            } else {
                console.error('❌ Calendar-Konstruktor NICHT vorhanden!');
            }
        }
        
        console.groupEnd();
    }

    static checkFullCalendarPlugins() {
        console.group('🔌 FullCalendar Plugins Check');
        
        if (typeof window.FullCalendar === 'undefined') {
            console.error('❌ FullCalendar nicht geladen - überspringe Plugin-Check');
            console.groupEnd();
            return;
        }
        
        const requiredPlugins = [
            'dayGridPlugin',
            'timeGridPlugin',
            'listPlugin'
        ];
        
        const availablePlugins = Object.keys(window.FullCalendar);
        console.log(`Available in window.FullCalendar: ${availablePlugins.length} Keys`);
        console.log(`Keys: ${availablePlugins.join(', ')}`);
        
        console.log(`\nRequired Plugins:`);
        requiredPlugins.forEach(plugin => {
            if (window.FullCalendar[plugin]) {
                console.log(`✅ ${plugin}: vorhanden`);
                console.log(`   Type: ${typeof window.FullCalendar[plugin]}`);
            } else {
                console.error(`❌ ${plugin}: FEHLT!`);
            }
        });
        
        console.groupEnd();
    }

    static checkKronosClasses() {
        console.group('⚙️ Kronos Classes Check');
        
        const classes = [
            { name: 'KronosCalendar', var: 'KronosCalendar' },
            { name: 'KronosCreateDialog', var: 'KronosCreateDialog' },
            { name: 'KronosEventClickHandler', var: 'KronosEventClickHandler' },
            { name: 'KronosEvents', var: 'KronosEvents' }
        ];
        
        classes.forEach(({ name, var: varName }) => {
            if (typeof window[varName] !== 'undefined') {
                console.log(`✅ ${name} (window.${varName}) geladen`);
                if (typeof window[varName] === 'function') {
                    console.log(`   ℹ️ Ist eine Klasse (Constructor)`);
                } else if (typeof window[varName] === 'object') {
                    console.log(`   ℹ️ Ist ein Objekt (Methods: ${Object.keys(window[varName]).length})`);
                }
            } else {
                console.warn(`⚠️ ${name} nicht geladen`);
            }
        });
        
        // Check window.kronosCalendar (Instanz)
        if (typeof window.kronosCalendar !== 'undefined') {
            console.log(`\n✅ window.kronosCalendar (Instanz) vorhanden`);
            if (window.kronosCalendar.calendar) {
                console.log(`   ✅ .calendar Eigenschaft vorhanden`);
                console.log(`   ℹ️ Typ: ${typeof window.kronosCalendar.calendar}`);
            }
        } else {
            console.warn(`⚠️ window.kronosCalendar nicht instantiiert`);
        }
        
        console.groupEnd();
    }

    static checkDOM() {
        console.group('📄 DOM Structure Check');
        
        const elements = {
            'body': document.body,
            '.kronos-app-container': document.querySelector('.kronos-app-container'),
            '.kronos-main-content': document.querySelector('.kronos-main-content'),
            '.kronos-sidebar': document.querySelector('.kronos-sidebar'),
            '.kronos-calendar-container': document.querySelector('.kronos-calendar-container'),
            '#calendar': document.getElementById('calendar'),
            '.fullcalendar-wrapper': document.querySelector('.fullcalendar-wrapper')
        };
        
        for (const [name, el] of Object.entries(elements)) {
            if (el) {
                const hidden = el.offsetHeight === 0 && el.offsetWidth === 0;
                const size = el.offsetWidth > 0 ? `${el.offsetWidth}x${el.offsetHeight}px` : '0x0px (hidden)';
                
                if (hidden && name !== 'body') {
                    console.warn(`⚠️ ${name}: vorhanden aber ${size}`);
                } else {
                    console.log(`✅ ${name}: ${size}`);
                }
            } else {
                console.error(`❌ ${name}: NICHT GEFUNDEN`);
            }
        }
        
        console.log(`\n📐 Viewport: ${window.innerWidth}x${window.innerHeight}px`);
        
        console.groupEnd();
    }

    static checkFrappe() {
        console.group('🍌 Frappe Integration Check');
        
        if (typeof frappe === 'undefined') {
            console.error('❌ Frappe nicht verfügbar');
            console.groupEnd();
            return;
        }
        
        console.log('✅ Frappe vorhanden');
        
        // Check wichtige Funktionen
        const functions = [
            'call',
            'msgprint',
            'throw_permission_error',
            'get_route'
        ];
        
        functions.forEach(fn => {
            if (typeof frappe[fn] === 'function') {
                console.log(`✅ frappe.${fn}() vorhanden`);
            } else {
                console.warn(`⚠️ frappe.${fn}() fehlt`);
            }
        });
        
        // Check Socket
        if (frappe.socketio) {
            const connected = frappe.socketio.connected || false;
            console.log(`\n${connected ? '✅' : '⚠️'} WebSocket: ${connected ? 'verbunden' : 'nicht verbunden'}`);
        } else {
            console.log(`\nℹ️ frappe.socketio nicht verfügbar`);
        }
        
        console.groupEnd();
    }

    static checkCalendarInstance() {
        console.group('📅 Calendar Instance Check');
        
        if (!window.kronosCalendar || !window.kronosCalendar.calendar) {
            console.warn('⚠️ Kalender-Instanz nicht initialisiert');
            console.log('   Das ist OK wenn die Seite gerade lädt');
            console.groupEnd();
            return;
        }
        
        const cal = window.kronosCalendar.calendar;
        
        console.log('✅ Calendar-Instanz vorhanden');
        console.log(`   initialView: ${cal.getOption('initialView')}`);
        console.log(`   locale: ${cal.getOption('locale')}`);
        
        // Check Plugins
        const plugins = cal.getOption('plugins') || [];
        console.log(`   Plugins registriert: ${plugins.length}`);
        
        if (plugins.length === 0) {
            console.error('❌ KEINE Plugins registriert! → Das ist der Fehler!');
            console.log('   Fix: plugins: [dayGridPlugin, timeGridPlugin, listPlugin]');
        } else {
            plugins.forEach((p, i) => {
                console.log(`      ${i + 1}. ${p.name || p.constructor.name || 'Unknown'}`);
            });
        }
        
        // Check View
        try {
            const view = cal.view;
            console.log(`\n   Aktuelle View: ${view.type}`);
            console.log(`   Title: ${view.title}`);
        } catch (e) {
            console.warn(`⚠️ View nicht verfügbar: ${e.message}`);
        }
        
        // Check Events
        try {
            const events = cal.getEvents();
            console.log(`\n   Geladen Events: ${events.length}`);
        } catch (e) {
            console.warn(`⚠️ Events nicht geladen: ${e.message}`);
        }
        
        console.groupEnd();
    }

    // Hilfsmethode für weitere Diagnosen
    static exportDiagnostics() {
        return {
            timestamp: new Date().toISOString(),
            userAgent: navigator.userAgent,
            url: window.location.href,
            fullcalendarLoaded: typeof window.FullCalendar !== 'undefined',
            fullcalendarPlugins: Object.keys(window.FullCalendar || {}),
            kronosLoaded: typeof window.KronosCalendar !== 'undefined',
            kronosInstantiated: typeof window.kronosCalendar !== 'undefined' && window.kronosCalendar.calendar !== null,
            frappeLoaded: typeof frappe !== 'undefined',
            domReady: document.readyState === 'complete'
        };
    }
}

// ═══════════════════════════════════════════════════════════════
// Nur Klasse registrieren, NICHT automatisch laufen
// ═══════════════════════════════════════════════════════════════

// Verfügbar in Console
window.DiakronosDiagnostics = DiakronosDiagnostics;
console.log('💡 DiakronosDiagnostics verfügbar. Zum Starten aufrufen:');
console.log('   DiakronosDiagnostics.run()');
