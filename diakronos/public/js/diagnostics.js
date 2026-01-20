/**
 * ═══════════════════════════════════════════════════════════════
 * KRONOS DIAGNOSTICS
 * ═══════════════════════════════════════════════════════════════
 */

class KronosDiagnostics {
    static run() {
        console.clear();
        console.log('╔════════════════════════════════════════════╗');
        console.log('║  🔍 KRONOS DIAGNOSTIC SUITE START         ║');
        console.log('╚════════════════════════════════════════════╝');
        
        this.checkEnvironment();
        this.checkDOM();
        this.checkScripts();
        this.checkFullCalendar();
        this.checkFrappe();
        
        console.log('═══════════════════════════════════════════════');
    }

    static checkEnvironment() {
        console.group('🌍 Environment Check');
        
        console.log('Browser:', navigator.userAgent.split('(')[1].split(')')[0]);
        console.log('URL:', window.location.href);
        console.log('Protocol:', window.location.protocol);
        console.log('Host:', window.location.host);
        console.log('Path:', window.location.pathname);
        
        // SSL Check
        const isSecure = window.location.protocol === 'https:';
        console.log(`🔒 HTTPS/SSL: ${isSecure ? '✅ YES' : '❌ NO'}`);
        
        console.groupEnd();
    }

    static checkDOM() {
        console.group('📄 DOM Check');
        
        const elements = {
            'body': document.body,
            '.kronos-wrapper': document.querySelector('.kronos-wrapper'),
            '#sidebar': document.getElementById('sidebar'),
            '#calendar-container': document.getElementById('calendar-container'),
            '.calendar-container': document.querySelector('.calendar-container')
        };

        for (const [name, el] of Object.entries(elements)) {
            if (el) {
                console.log(`✅ ${name} found`);
                if (el.offsetHeight === 0 && el.offsetWidth === 0) {
                    console.warn(`⚠️ ${name} is hidden (0x0)`);
                }
            } else {
                console.error(`❌ ${name} NOT FOUND`);
            }
        }
        
        console.log(`📐 Viewport: ${window.innerWidth}x${window.innerHeight}`);
        
        console.groupEnd();
    }

    static checkScripts() {
        console.group('📦 Script Loading Check');
        
        const scripts = [
            { name: 'FullCalendar', var: 'FullCalendar' },
            { name: 'Frappe', var: 'frappe' },
            { name: 'KronosApp', var: 'kronosApp' }
        ];

        scripts.forEach(({ name, var: varName }) => {
            if (typeof window[varName] !== 'undefined') {
                console.log(`✅ ${name} loaded (window.${varName})`);
                if (varName === 'FullCalendar') {
                    console.log('   Version info:', typeof window[varName].Calendar);
                }
            } else {
                console.error(`❌ ${name} NOT loaded (window.${varName})`);
            }
        });
        
        console.groupEnd();
    }

    static checkFullCalendar() {
        console.group('🗓️ FullCalendar Check');
        
        if (typeof window.FullCalendar === 'undefined') {
            console.error('❌ FullCalendar not in window');
            console.log('Checking global objects...');
            console.log('window keys containing "calendar":', 
                Object.keys(window).filter(k => k.toLowerCase().includes('calendar')));
        } else {
            console.log('✅ FullCalendar is available');
            console.log('   Calendar constructor:', typeof window.FullCalendar.Calendar);
            
            // Check if CSS is loaded
            const fcCss = Array.from(document.styleSheets).find(sheet => 
                sheet.href && sheet.href.includes('fullcalendar')
            );
            console.log(`📄 FullCalendar CSS: ${fcCss ? '✅ loaded' : '❌ NOT loaded'}`);
        }
        
        console.groupEnd();
    }

    static checkFrappe() {
        console.group('🍌 Frappe Check');
        
        if (typeof frappe === 'undefined') {
            console.error('❌ Frappe not available - using dummy data mode');
        } else {
            console.log('✅ Frappe is available');
            console.log('   frappe.call available:', typeof frappe.call === 'function');
            console.log('   frappe.get_route available:', typeof frappe.get_route === 'function');
            
            // Check socketio
            if (frappe.socketio) {
                console.log('   frappe.socketio:', frappe.socketio.connected ? '✅ Connected' : '❌ Disconnected');
            } else {
                console.warn('   frappe.socketio not available (this is OK for web mode)');
            }
        }
        
        console.groupEnd();
    }
}

// Run diagnostics immediately
KronosDiagnostics.run();

// Also run on window load
window.addEventListener('load', () => {
    console.log('\n🔄 Re-running diagnostics after page load...\n');
    KronosDiagnostics.run();
});
