/**
 * ═══════════════════════════════════════════════════════════════
 * KRONOS CALENDAR - MAIN APPLICATION
 * ═══════════════════════════════════════════════════════════════
 * Entry point für die Kronos Calendar App
 * Lädt alle Module und orchestriert die App
 */

class KronosApp {
    constructor() {
        this.modules = {};
        this.ready = false;
        
        console.log('🚀 KronosApp - Initialisiere...');
        this.init();
    }

    init() {
        this.registerLocale();
        this.waitForFullCalendar();
    }

    registerLocale() {
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
        }
        console.log('✅ Deutsch Locale registriert');
    }

    waitForFullCalendar() {
        if (typeof FullCalendar === 'undefined' || !FullCalendar.Calendar) {
            console.log('⏳ Warte auf FullCalendar...');
            setTimeout(() => this.waitForFullCalendar(), 500);
            return;
        }
        
        console.log('✅ FullCalendar bereit!');
        this.loadModules();
    }

    loadModules() {
        console.log('📦 Lade Module...');
        
        this.loadScript('/assets/diakronos/js/modules/kronos_events.js', () => {
            console.log('✅ Events Modul geladen');
            
            this.loadScript('/assets/diakronos/js/modules/kronos_calendar.js', () => {
                console.log('✅ Calendar Modul geladen');
                this.start();
            });
        });
    }


    loadScript(src, callback) {
        const script = document.createElement('script');
        script.src = src + '?v=' + Math.random();
        script.async = true;
        script.onload = callback;
        script.onerror = () => {
            console.error('❌ Fehler beim Laden von:', src);
        };
        document.head.appendChild(script);
    }

    start() {
        console.log('🎯 Starte App...');
        
        window.kronosCalendar.init();
        this.setupControls();
        this.setGreeting();
        this.updateMonth();
        
        this.ready = true;
        console.log('✨ KronosApp bereit!');
    }

    setupControls() {
        const self = this;
        
        document.getElementById('prev-month')?.addEventListener('click', () => {
            window.kronosCalendar.prev();
            self.updateMonth();
        });

        document.getElementById('next-month')?.addEventListener('click', () => {
            window.kronosCalendar.next();
            self.updateMonth();
        });

        document.getElementById('today-button')?.addEventListener('click', () => {
            window.kronosCalendar.today();
            self.updateMonth();
        });

        document.getElementById('month-view')?.addEventListener('click', () => {
            window.kronosCalendar.changeView('dayGridMonth');
            document.getElementById('month-view').classList.add('active');
            document.getElementById('week-view').classList.remove('active');
        });

        document.getElementById('week-view')?.addEventListener('click', () => {
            window.kronosCalendar.changeView('timeGridWeek');
            document.getElementById('week-view').classList.add('active');
            document.getElementById('month-view').classList.remove('active');
        });

        document.getElementById('back-button')?.addEventListener('click', () => {
            window.location.href = '/app/home';
        });

        console.log('✅ Controls setup fertig');
    }

    updateMonth() {
        const date = window.kronosCalendar.getDate();
        const monthStr = new Intl.DateTimeFormat('de-DE', { 
            month: 'long', 
            year: 'numeric' 
        }).format(date);
        
        const month = monthStr.charAt(0).toUpperCase() + monthStr.slice(1);
        document.getElementById('current-month-header').textContent = month;
    }

    setGreeting() {
        const hour = new Date().getHours();
        const greeting = hour < 12 ? '🌅 Guten Morgen' : 
                         hour < 18 ? '☀️ Guten Mittag' : 
                         '🌙 Guten Abend';
        
        const name = frappe.session?.user_fullname?.split(' ')[0] || '';
        const text = name ? `${greeting}, ${name}` : greeting;
        
        document.getElementById('greeting-title').textContent = text;
    }
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        window.kronosApp = new KronosApp();
    });
} else {
    window.kronosApp = new KronosApp();
}
