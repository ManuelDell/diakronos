// kronos_mini_calendar.js
// Leichter Mini-Monatskalender mit Moment.js (angepasst an Diakronos/Frappe)
// Fallback: Sprache aus <html lang="..."> lesen
// === Mini-Kalender: Sprache explizit auf Deutsch fixieren ===
    if (window.moment) {
        // 1. Locale laden und aktivieren (de ist in moment enthalten)
        moment.locale('de');

        // 2. Sicherstellen, dass es wirklich 'de' bleibt (aggressiv)
        moment.updateLocale('de', {
            months: 'Januar_Februar_März_April_Mai_Juni_Juli_August_September_Oktober_November_Dezember'.split('_'),
            monthsShort: 'Jan_Feb_Mär_Apr_Mai_Jun_Jul_Aug_Sep_Okt_Nov_Dez'.split('_'),
            weekdays: 'Sonntag_Montag_Dienstag_Mittwoch_Donnerstag_Freitag_Samstag'.split('_'),
            weekdaysShort: 'So_Mo_Di_Mi_Do_Fr_Sa'.split('_'),
            weekdaysMin: 'So_Mo_Di_Mi_Do_Fr_Sa'.split('_')
        });

//        console.log('Mini-Kalender: moment-Locale explizit auf Deutsch gesetzt');
//        console.log('Aktuelle Locale:', moment().locale());           // sollte 'de' sein
//        console.log('Test-Monat:', moment().format('MMMM YYYY'));     // sollte 'Februar 2026' sein
//    } else {
//        console.error('Moment.js nicht verfügbar – Mini-Kalender kann keine deutsche Locale setzen');
    }

class KronosMiniCalendar {
    constructor(selector = '#mini-kalender') {
        this.el = document.querySelector(selector);
        if (!this.el) {
            console.warn('Mini-Kalender Container nicht gefunden');
            return;
        }
        this.m = moment(); // aktueller Monat
        this.today = moment();
        this.init();
    }

    init() {
        this.render();
        this.bind();
    }

    render() {
        const y = this.m.year();
        const m = this.m.month();
        const title = this.m.format('MMMM YYYY');

        const firstDay = this.m.clone().startOf('month').day(); // 0=So, 1=Mo, ...
        const daysInMonth = this.m.daysInMonth();

        // Anzahl Wochen (aufgerundet)
        const weeks = Math.ceil((daysInMonth + firstDay) / 7);

        let html = `
            <!-- Header: Monat + Jahr links, Pfeile rechts -->
            <div class="mini-cal-header">
                <span class="mini-title">${title}</span>
                <div class="mini-nav">
                    <button class="mini-prev">&lt;</button>
                    <button class="mini-next">&gt;</button>
                </div>
            </div>

            <!-- Ein einziges Grid: KW + 7 Tage -->
            <div class="mini-cal-grid">
                <!-- Header-Zeile: leer (für KW) + Wochentage nur Anfangsbuchstabe -->
                <div class="mini-cal-header-row">
                    <div class="mini-week-header"></div> <!-- leer -->
                    <div class="mini-day-header">S</div>
                    <div class="mini-day-header">M</div>
                    <div class="mini-day-header">D</div>
                    <div class="mini-day-header">M</div>
                    <div class="mini-day-header">D</div>
                    <div class="mini-day-header">F</div>
                    <div class="mini-day-header">S</div>
                </div>
        `;

        let dayCounter = 1 - firstDay;

        for (let week = 0; week < weeks; week++) {
            // KW-Nummer (ISO-Woche)
            const weekStart = this.m.clone().startOf('month').add(week * 7 - firstDay + 1, 'days');
            const weekNum = weekStart.isoWeek();

            html += `
                <div class="mini-cal-week-row">
                    <div class="mini-week-number">${weekNum}</div>
            `;

            for (let d = 0; d < 7; d++) {
                let dayNum, className = 'mini-cal-day';

                if (dayCounter <= 0) {
                    dayNum = this.m.clone().subtract(1, 'month').daysInMonth() + dayCounter;
                    className += ' other-month';
                } else if (dayCounter > daysInMonth) {
                    dayNum = dayCounter - daysInMonth;
                    className += ' other-month';
                } else {
                    dayNum = dayCounter;
                    if (dayNum === this.today.date() && m === this.today.month() && y === this.today.year()) {
                        className += ' today';
                    }
                }

                html += `<div class="${className}">${dayNum}</div>`;
                dayCounter++;
            }

            html += `</div>`;
        }

        html += `</div>`;

        this.el.innerHTML = html;
    }
    bind() {
        this.el.addEventListener('click', e => {
            if (e.target.classList.contains('mini-prev')) {
                this.m.subtract(1, 'month');
                this.render();
            }
            if (e.target.classList.contains('mini-next')) {
                this.m.add(1, 'month');
                this.render();
            }
        });
    }

    syncWithMain() {
        if (!window.kronosCalendar?.calendar) {
            console.warn('Haupt-Kalender nicht verfügbar – Sync deaktiviert');
            return;
        }

        const mainCalendar = window.kronosCalendar.calendar;

        // Einmalig: Aktuellen Monat vom Haupt-Kalender übernehmen
        this.m = moment(mainCalendar.getDate()).startOf('month');
        this.render();

        // Nur bei Änderung im Haupt-Kalender nachziehen (datesSet = Monatswechsel, View-Wechsel usw.)
        mainCalendar.on('datesSet', () => {
            const newDate = mainCalendar.getDate();
            const newMonth = moment(newDate).startOf('month');

            // Nur wenn Monat wirklich anders → updaten
            if (!this.m.isSame(newMonth, 'month')) {
                this.m = newMonth;
                this.render();
//                console.log('Mini-Kalender synchronisiert mit Haupt-Kalender:', this.m.format('MMMM YYYY'));
            }
        });
    }
}

window.KronosMiniCalendar = KronosMiniCalendar;
//.log('✅ KronosMiniCalendar Klasse geladen');

// Auto-Init: Starte Mini-Kalender automatisch, wenn Container da ist
document.addEventListener('DOMContentLoaded', () => {
    const container = document.querySelector('#mini-kalender');
    if (container) {
        // ── HIER die entscheidende Zeile hinzufügen ──
        window.kronosMiniCalendar = new KronosMiniCalendar('#mini-kalender'); // Instanziiert die Klasse
//    console.log('✅ Mini-Kalender auto-initialisiert');
} else {
    console.warn('⚠️ Mini-Kalender-Container nicht gefunden');
  }
});