// kronos_mini_calendar.js
// Leichter Mini-Monatskalender mit Moment.js (angepasst an Diakronos/Frappe)

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

        let html = `
            <div class="mini-cal-header">
                <button class="mini-prev">&lsaquo;</button>
                <span class="mini-title">${title}</span>
                <button class="mini-next">&rsaquo;</button>
            </div>
            <div class="mini-cal-weekdays">
                <span>So</span><span>Mo</span><span>Di</span><span>Mi</span>
                <span>Do</span><span>Fr</span><span>Sa</span>
            </div>
            <div class="mini-cal-days">
        `;

        const first = moment([y, m, 1]);
        let start = first.day(); // 0 = Sonntag

        for (let i = 0; i < start; i++) {
            html += '<div class="mini-day empty"></div>';
        }

        const days = this.m.daysInMonth();
        for (let d = 1; d <= days; d++) {
            const date = moment([y, m, d]);
            let cls = 'mini-day';
            if (date.isSame(this.today, 'day')) cls += ' today';
            if (date.isSame(this.m, 'day')) cls += ' selected';

            html += `<div class="${cls}">${d}</div>`;
        }

        html += '</div>';
        this.el.innerHTML = html;

        // Klick → Haupt-Kalender springen
        this.el.querySelectorAll('.mini-day:not(.empty)').forEach(day => {
            day.addEventListener('click', () => {
                const num = parseInt(day.textContent, 10);
                const clicked = moment([y, m, num]).format('YYYY-MM-DD');
                if (window.kronosCalendar?.calendar) {
                    window.kronosCalendar.calendar.gotoDate(clicked);
                    console.log('Mini-Kalender → Haupt: ' + clicked);
                }
            });
        });
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
            if (window.kronosCalendar?.calendar) {
                const mainDate = window.kronosCalendar.calendar.getDate();
                    this.m = moment(mainDate).startOf('month');
                    this.render();
                    window.kronosCalendar.calendar.on('datesSet', () => {
                        this.m = moment(window.kronosCalendar.calendar.getDate()).startOf('month');
                        this.render();
                    });
                }
            }
}

window.KronosMiniCalendar = KronosMiniCalendar;
console.log('✅ KronosMiniCalendar Klasse geladen');