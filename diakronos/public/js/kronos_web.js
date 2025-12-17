class KronosApp {
    constructor() {
        this.calendar = null;
        this.userName = null;
        this.cachedYears = new Set();
        this.allEvents = [];
        this.currentMonthDate = new Date();
        this.currentView = 'month';
        this.resizeTimeout = null;
        this.init();
    }

    async init() {
        const calendarEl = document.getElementById('calendar');
        if (!calendarEl) {
            console.error('❌ Kalender-Container nicht gefunden');
            return;
        }

        try {
            console.log('🔍 Prüfe Prerequisites...');
            if (typeof frappe === 'undefined' || typeof tui === 'undefined') {
                throw new Error('Frappe oder TUI nicht verfügbar!');
            }

            console.log('📦 TUI Calendar Objekt:', typeof tui.Calendar);

            await this.loadUserData();
            this.setGreeting();
            this.setupBackButton();

            calendarEl.style.width = '100%';
            calendarEl.style.height = '100%';
            calendarEl.classList.remove('loading');

            this.calendar = new tui.Calendar(calendarEl, {
                defaultView: 'month',
                useCreationPopup: true,
                useDetailPopup: true,
                timezone: {
                    zones: ['Europe/Berlin'],
                },
                isReadOnly: false,
                usageStatistics: false,

                week: {
                    hourStart: 6,
                    hourEnd: 23,
                    dayNames: ['Sonntag', 'Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag'],
                    startDayOfWeek: 1,
                    narrowWeekend: false,
                },
                month: {
                    dayNames: ['So', 'Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa'],
                    startDayOfWeek: 1,
                    narrowWeekend: false,
                },

                template: {
                    alldayTitle: function () {
                        return '<span style="font-weight:bold; font-size:11px;">Ganztägig</span>';
                    },
                    monthGridFooterExceed: function (hiddenEvents) {
                        return '<span style="color: grey;">+' + hiddenEvents + ' weitere</span>';
                    },
                    popupDetailDate: function (isAllDay, start, end) {
                        var isSameDate = moment(start).isSame(end);
                        var endFormat = (isSameDate ? '' : 'DD.MM.YYYY ') + 'HH:mm';

                        if (isAllDay) {
                            return moment(start).format('DD.MM.YYYY') + (isSameDate ? '' : ' - ' + moment(end).format('DD.MM.YYYY'));
                        }
                        return (moment(start).format('DD.MM.YYYY HH:mm') + ' - ' + moment(end).format(endFormat));
                    },
                }
            });

            this.calendar.render();
            console.log('✅ Kronos Kalender (TUI v2) initialisiert');

            this.setupCRUDEvents();
            this.setupViewButtons();
            this.setupMonthNavigation();

            console.log('🚀 Lade Events für 2 Jahre...');
            await this.loadEventsCached();

            this.calendar.on('afterRenderDate', () => {
                this.updateHeaderDisplay();
                this.handleMonthChange();
            });

            this.calendar.on('afterRender', () => {
                setTimeout(() => {
                    this.optimize_layout_view();
                }, 100);
            });

            window.addEventListener('resize', () => {
                clearTimeout(this.resizeTimeout);
                this.resizeTimeout = setTimeout(() => {
                    this.optimize_layout_view();
                }, 300);
            });

            setTimeout(() => {
                this.optimize_layout_view();
            }, 300);

        } catch (error) {
            console.error('❌ Init-Fehler:', error);
            if (calendarEl) {
                calendarEl.innerHTML = `<div style="padding: 20px; color: red;">❌ ${error.message}</div>`;
            }
        }
    }

    optimize_layout_view() {
        if (this.currentView !== 'week') {
            return;
        }

        document.querySelectorAll('.toastui-calendar-milestone, .toastui-calendar-task').forEach(el => {
            el.remove();
        });
        document.querySelectorAll('.toastui-calendar-panel-resizer').forEach(el => {
            el.remove();
        });

        const layout = document.querySelector('.toastui-calendar-layout');
        if (layout) {
            const timePanel = document.querySelector('.toastui-calendar-time');
            const allDayPanel = document.querySelector('.toastui-calendar-allday');

            if (timePanel && allDayPanel) {
                const parentHeight = layout.offsetHeight;
                allDayPanel.style.height = 'auto';
                allDayPanel.style.flexGrow = '0';

                const allDayHeight = allDayPanel.offsetHeight;
                timePanel.style.height = (parentHeight - allDayHeight) + 'px';
            }
        }

        console.log('✅ Allday minimiert, Time maximiert (Week View)');
    }

    setupCRUDEvents() {
        this.calendar.on('beforeCreateEvent', (eventData) => {
            console.log('✅ beforeCreateEvent:', eventData);
            const { title, start, end, isAllday, calendarId } = eventData;
            const startDate = this.ensureDate(start);
            const endDate = this.ensureDate(end);

            if (!startDate || !endDate) {
                console.error('❌ Ungültige Datum-Konversion');
                return;
            }

            frappe.call({
                method: 'diakronos.kronos.api.tui_management.event_create_from_tui',
                args: {
                    title: title,
                    start: startDate.toISOString(),
                    end: endDate.toISOString(),
                    calendar_id: calendarId || 'Standard',
                    is_all_day: isAllday || false,
                },
                callback: (r) => {
                    if (r.message && r.message.name) {
                        this.calendar.createEvents([{
                            id: r.message.name,
                            calendarId: calendarId || 'Standard',
                            title,
                            start: startDate,
                            end: endDate,
                            isAllday: isAllday || false,
                            category: isAllday ? 'allday' : 'time',
                        }]);
                        frappe.msgprint(__('✅ Termin angelegt'));
                    }
                },
                error: () => frappe.msgprint(__('❌ Fehler beim Anlegen')),
            });
        });

        this.calendar.on('beforeUpdateEvent', (eventData) => {
            const eventObj = eventData.event;
            const changes = eventData.changes || {};
            if (!eventObj) return;

            const startDate = this.ensureDate(changes.start || eventObj.start);
            const endDate = this.ensureDate(changes.end || eventObj.end);

            frappe.call({
                method: 'diakronos.kronos.api.tui_management.event_update_from_tui',
                args: {
                    name: eventObj.id,
                    title: changes.title || eventObj.title,
                    start: startDate.toISOString(),
                    end: endDate.toISOString(),
                    calendar_id: eventObj.calendarId || 'Standard',
                    is_all_day: typeof changes.isAllday === 'boolean' ? changes.isAllday : eventObj.isAllday,
                },
                callback: () => {
                    this.calendar.updateEvent(eventObj.id, eventObj.calendarId, { ...changes });
                    frappe.msgprint(__('✅ Termin aktualisiert'));
                },
            });
        });

        this.calendar.on('beforeDeleteEvent', (eventData) => {
            const eventObj = eventData;
            if (!eventObj || !eventObj.id) return;

            frappe.call({
                method: 'diakronos.kronos.api.tui_management.event_delete_from_tui',
                args: { name: eventObj.id },
                callback: () => {
                    this.calendar.deleteEvent(eventObj.id, eventObj.calendarId);
                    frappe.msgprint(__('✅ Termin gelöscht'));
                },
            });
        });
    }

    async loadUserData() {
        try {
            if (frappe.session && frappe.session.user_fullname) {
                this.userName = frappe.session.user_fullname;
            } else if (frappe.session && frappe.session.user) {
                this.userName = frappe.session.user;
            }
        } catch (e) {
            console.warn('⚠️ Kein Benutzername verfügbar');
        }
    }

    setGreeting() {
        const hour = new Date().getHours();
        let greeting = '📅 Kronos';

        if (hour >= 5 && hour < 12) {
            greeting = '🌅 Guten Morgen';
        } else if (hour >= 12 && hour < 18) {
            greeting = '☀️ Guten Mittag';
        } else {
            greeting = '🌙 Guten Abend';
        }

        if (this.userName) {
            greeting += `, ${this.userName.split(' ')[0]}`;
        }

        const greetingEl = document.getElementById('greeting-title');
        if (greetingEl) {
            greetingEl.textContent = greeting;
        }
    }

    setupBackButton() {
        const backBtn = document.getElementById('back-button');
        if (backBtn) {
            backBtn.addEventListener('click', () => {
                window.location.href = '/apps';
            });
        }
    }

    setupViewButtons() {
        document.getElementById('month-view')?.addEventListener('click', () => {
            this.calendar.changeView('month');
            this.currentView = 'month';
            document.getElementById('month-view').classList.add('active');
            document.getElementById('week-view').classList.remove('active');
            this.updateHeaderDisplay();
        });

        document.getElementById('week-view')?.addEventListener('click', () => {
            this.calendar.changeView('week');
            this.currentView = 'week';
            document.getElementById('week-view').classList.add('active');
            document.getElementById('month-view').classList.remove('active');
            this.updateHeaderDisplay();

            setTimeout(() => {
                this.optimize_layout_view();
            }, 100);
        });
    }

    setupMonthNavigation() {
        const prevBtn = document.getElementById('prev-month');
        const nextBtn = document.getElementById('next-month');
        const todayBtn = document.getElementById('today-button');

        prevBtn?.addEventListener('click', () => {
            this.calendar.prev();
            if (this.currentView === 'month') {
                this.currentMonthDate.setMonth(this.currentMonthDate.getMonth() - 1);
            }
            this.updateHeaderDisplay();
            this.handleMonthChange();
        });

        nextBtn?.addEventListener('click', () => {
            this.calendar.next();
            if (this.currentView === 'month') {
                this.currentMonthDate.setMonth(this.currentMonthDate.getMonth() + 1);
            }
            this.updateHeaderDisplay();
            this.handleMonthChange();
        });

        todayBtn?.addEventListener('click', () => {
            this.calendar.today();
            this.currentMonthDate = new Date();
            this.updateHeaderDisplay();
            this.handleMonthChange();
        });

        this.updateHeaderDisplay();
    }

    toNativeDate(tzDate) {
        try {
            if (tzDate && typeof tzDate.getTime === 'function') {
                return new Date(tzDate.getTime());
            }
            if (tzDate instanceof Date) {
                return tzDate;
            }
            if (typeof tzDate === 'string') {
                return new Date(tzDate);
            }
        } catch (e) {
            console.warn('⚠️ Konnte TZDate nicht konvertieren:', e);
        }
        return new Date();
    }

    getWeekNumber(date) {
        const d = new Date(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()));
        const dayNum = d.getUTCDay() || 7;
        d.setUTCDate(d.getUTCDate() + 4 - dayNum);
        const yearStart = new Date(Date.UTC(d.getUTCFullYear(), 0, 1));
        return Math.ceil((((d - yearStart) / 86400000) + 1) / 7);
    }

    getMonthString(date) {
        const monthStr = date.toLocaleDateString('de-DE', {
            month: 'long',
            year: 'numeric'
        });
        return monthStr.charAt(0).toUpperCase() + monthStr.slice(1);
    }

    updateHeaderDisplay() {
        try {
            const el = document.getElementById('current-month-header');
            if (!el) return;

            if (this.currentView === 'week') {
                const date = this.calendar.getDate();

                const d = new Date(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()));
                const dayNum = d.getUTCDay() || 7;
                d.setUTCDate(d.getUTCDate() + 4 - dayNum);

                const yearStart = new Date(Date.UTC(d.getUTCFullYear(), 0, 1));
                const weekNum = Math.ceil((((d - yearStart) / 86400000) + 1) / 7);

                const monthStr = d.toLocaleDateString('de-DE', { month: 'short' });
                el.textContent = `KW ${weekNum}, ${monthStr}`;
            } else {
                el.textContent = this.getMonthString(this.currentMonthDate);
            }
        } catch (e) {
            console.error('❌ updateHeaderDisplay Fehler:', e);
        }
    }

    async handleMonthChange() {
        try {
            const year = this.currentMonthDate.getFullYear();

            if (!this.cachedYears.has(year)) {
                console.log(`💾 Lade Cache für ${year}-${year + 1}`);
                await this.loadEventsCached();
            }
        } catch (e) {
            console.error('❌ handleMonthChange Fehler:', e);
        }
    }

    async loadEventsCached() {
        try {
            const year = this.currentMonthDate.getFullYear();

            const cacheStart = new Date(year, 0, 1);
            const cacheEnd = new Date(year + 2, 11, 31);

            const startStr = this.formatDate(cacheStart);
            const endStr = this.formatDate(cacheEnd);

            console.log(`📅 Lade Events ${startStr} bis ${endStr}`);

            return new Promise((resolve, reject) => {
                frappe.call({
                    method: 'diakronos.kronos.api.events.get_calendar_events',
                    args: {
                        start_date: startStr,
                        end_date: endStr,
                        calendar_filter: '[]',
                    },
                    callback: (response) => {
                        try {
                            if (response.message && Array.isArray(response.message)) {
                                console.log(`✅ ${response.message.length} Events geladen`);

                                const existingIds = new Set(this.allEvents.map(e => e.id));
                                const newEvents = response.message.filter(e => !existingIds.has(e.id));

                                this.allEvents = this.allEvents.concat(newEvents);

                                if (newEvents.length > 0) {
                                    const tuiEvents = newEvents.map(e => ({
                                        id: e.id,
                                        calendarId: e.calendar || 'Standard',
                                        title: e.title,
                                        start: new Date(e.start),
                                        end: new Date(e.end),
                                        isAllday: e.isAllday,
                                        backgroundColor: e.backgroundColor,
                                        borderColor: e.borderColor,
                                        category: e.isAllday ? 'allday' : 'time',
                                    }));
                                    this.calendar.createEvents(tuiEvents);
                                }

                                this.cachedYears.add(year);
                                this.cachedYears.add(year + 1);
                            }
                            resolve();
                        } catch (err) {
                            console.error('❌ Parse-Fehler:', err);
                            reject(err);
                        }
                    },
                    error: (err) => {
                        console.error('❌ API-Fehler:', err);
                        reject(err);
                    },
                });
            });
        } catch (e) {
            console.error('❌ loadEventsCached Fehler:', e);
        }
    }

    ensureDate(value) {
        if (!value) return null;
        if (value instanceof Date) {
            return isNaN(value.getTime()) ? null : value;
        }
        try {
            const d = new Date(value);
            return isNaN(d.getTime()) ? null : d;
        } catch {
            return null;
        }
    }

    formatDate(date) {
        const year = date.getFullYear();
        const month = String(date.getMonth() + 1).padStart(2, '0');
        const day = String(date.getDate()).padStart(2, '0');
        return `${year}-${month}-${day}`;
    }
}

document.addEventListener('DOMContentLoaded', () => {
    console.log('🎯 Starte Kronos App (TUI v2.1.3)');
    window.kronosApp = new KronosApp();
});
