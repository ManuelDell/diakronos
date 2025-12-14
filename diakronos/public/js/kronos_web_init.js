// diakronos/public/js/kronos_web_init.js
document.addEventListener('DOMContentLoaded', function () {
    const calendarEl = document.getElementById('calendar');
    
    if (!calendarEl) {
        console.error('Kalender-Container nicht gefunden');
        return;
    }
    
    const calendar = new tui.Calendar(calendarEl, {
        defaultView: 'week',
        useCreationPopup: true,
        useDetailPopup: true,
        taskView: true,
        scheduleView: true,
        timezone: 'Europe/Berlin',
        template: {
            allday: function(schedule) {
                return schedule.title + ' (ganztägig)';
            },
            time: function(schedule) {
                return schedule.title;
            }
        }
    });

    // View-Buttons
    document.getElementById('month-view').addEventListener('click', () => {
        calendar.changeView('month', true);
    });
    
    document.getElementById('week-view').addEventListener('click', () => {
        calendar.changeView('week', true);
    });
    
    document.getElementById('day-view').addEventListener('click', () => {
        calendar.changeView('day', true);
    });
    
    document.getElementById('task-view').addEventListener('click', () => {
        calendar.changeView('task', true);
    });

    // Beispieldaten laden (später: von Frappe-Backend)
    calendar.createSchedules([
        {
            id: '1',
            calendarId: '1',
            title: 'Testtermin',
            category: 'time',
            start: new Date(),
            end: new Date(Date.now() + 3600000)
        }
    ]);
});
