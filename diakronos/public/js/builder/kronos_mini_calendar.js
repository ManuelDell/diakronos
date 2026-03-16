// builder/kronos_mini_calendar.js – Mini-Monatskalender mit Moment.js

// Moment.js Locale auf Deutsch setzen (moment ist als globales Script geladen)
if (typeof moment !== 'undefined') {
    moment.locale('de');
    moment.updateLocale('de', {
        months: 'Januar_Februar_März_April_Mai_Juni_Juli_August_September_Oktober_November_Dezember'.split('_'),
        monthsShort: 'Jan_Feb_Mär_Apr_Mai_Jun_Jul_Aug_Sep_Okt_Nov_Dez'.split('_'),
        weekdays: 'Sonntag_Montag_Dienstag_Mittwoch_Donnerstag_Freitag_Samstag'.split('_'),
        weekdaysShort: 'So_Mo_Di_Mi_Do_Fr_Sa'.split('_'),
        weekdaysMin: 'So_Mo_Di_Mi_Do_Fr_Sa'.split('_')
    });
}

class KronosMiniCalendar {
    constructor(selector = '#mini-kalender') {
        this.el = document.querySelector(selector);
        if (!this.el) {
            console.warn('Mini-Kalender Container nicht gefunden');
            return;
        }
        this.m = moment();
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

        const firstDay = this.m.clone().startOf('month').day();
        const daysInMonth = this.m.daysInMonth();
        const weeks = Math.ceil((daysInMonth + firstDay) / 7);

        let html = `
            <div class="mini-cal-header">
                <span class="mini-title">${title}</span>
                <div class="mini-nav">
                    <button class="mini-prev">&lt;</button>
                    <button class="mini-next">&gt;</button>
                </div>
            </div>
            <div class="mini-cal-grid">
                <div class="mini-cal-header-row">
                    <div class="mini-week-header"></div>
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
            const weekStart = this.m.clone().startOf('month').add(week * 7 - firstDay + 1, 'days');
            const weekNum = weekStart.isoWeek();

            html += `<div class="mini-cal-week-row"><div class="mini-week-number">${weekNum}</div>`;

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
        // EventCalendar hat kein .on() – stattdessen ec:datesSet DOM-Event
        document.addEventListener('ec:datesSet', (e) => {
            const newMonth = moment(e.detail.start).startOf('month');
            if (!this.m.isSame(newMonth, 'month')) {
                this.m = newMonth;
                this.render();
            }
        });
    }
}

export { KronosMiniCalendar };

export let kronosMiniCalendar = null;

export function initMiniCalendar() {
    if (!kronosMiniCalendar) {
        kronosMiniCalendar = new KronosMiniCalendar('#mini-kalender');
    }
    return kronosMiniCalendar;
}
