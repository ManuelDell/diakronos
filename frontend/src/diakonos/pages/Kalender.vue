<template>
    <div class="dk-screen dk-screen-wide dk-screen-enter">
        <div class="dk-screen-header">
            <div>
                <h1 class="dk-screen-title">Kalender</h1>
            </div>
            <div class="dk-screen-actions">
                <button class="dk-btn dk-btn-secondary dk-btn-sm" @click="prevMonth">‹ Zurück</button>
                <span class="text-lg font-semibold min-w-[140px] text-center">{{ monthLabel }}</span>
                <button class="dk-btn dk-btn-secondary dk-btn-sm" @click="nextMonth">Weiter ›</button>
            </div>
        </div>

        <!-- Wochentage + Tage -->
        <div class="dk-calendar">
            <div v-for="day in weekDays" :key="day" class="dk-calendar-header">{{ day }}</div>
            <div
                v-for="(cell, idx) in calendarCells"
                :key="idx"
                class="dk-calendar-cell"
                :class="{ 'is-today': cell.isToday, 'is-other-month': !cell.isCurrentMonth }"
            >
                <div class="dk-calendar-day">{{ cell.day }}</div>
                <div class="flex flex-col gap-1">
                    <span
                        v-for="evt in cell.events"
                        :key="evt.id"
                        class="dk-calendar-event"
                        :class="{ 'has-anmeldung': evt.anmeldungAktiv }"
                        @click.stop="openEventDetail(evt)"
                    >
                        {{ evt.title }}
                    </span>
                </div>
            </div>
        </div>

        <!-- Event-Detail-Modal -->
        <div v-if="showDetail && selectedEvent" class="dk-modal-overlay" @click.self="closeDetail">
            <div class="dk-modal" style="max-width:440px">
                <div class="dk-modal-header">
                    <h3>{{ selectedEvent.title }}</h3>
                    <button class="dk-btn dk-btn-ghost dk-btn-sm" @click="closeDetail">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
                    </button>
                </div>
                <div class="dk-modal-body">
                    <div class="kl-event-meta">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>
                        <span>{{ formatEventDate(selectedEvent) }}</span>
                    </div>

                    <!-- Anmeldung -->
                    <div v-if="selectedEvent.anmeldungAktiv" class="kl-anmeldung-box">
                        <p v-if="!anmeldungErfolg" class="kl-anmeldung-hint">
                            Für diese Veranstaltung kannst du dich direkt anmelden.
                        </p>
                        <div v-if="anmeldungErfolg" class="kl-anmeldung-success">
                            ✅ Du bist angemeldet!
                        </div>
                        <div v-else-if="anmeldungFehler" class="kl-anmeldung-error">
                            {{ anmeldungFehler }}
                        </div>
                    </div>
                </div>
                <div v-if="selectedEvent.anmeldungAktiv && !anmeldungErfolg" class="dk-modal-actions">
                    <button class="dk-btn dk-btn-secondary" @click="closeDetail">Schließen</button>
                    <button
                        class="dk-btn dk-btn-primary"
                        :disabled="anmeldungLaden"
                        @click="jetzt_anmelden"
                    >
                        {{ anmeldungLaden ? 'Wird angemeldet…' : 'Jetzt anmelden' }}
                    </button>
                </div>
                <div v-else class="dk-modal-actions">
                    <button class="dk-btn dk-btn-secondary" @click="closeDetail">Schließen</button>
                </div>
            </div>
        </div>
    </div>
</template>

<script>
import { ref, computed, watch } from 'vue'
import { apiCall } from '../composables/useApi.js'
import { showToast } from '../composables/useToast.js'

export default {
    name: 'Kalender',
    setup() {
        const today = new Date()
        const currentYear = ref(today.getFullYear())
        const currentMonth = ref(today.getMonth())
        const events = ref([])

        const showDetail = ref(false)
        const selectedEvent = ref(null)
        const anmeldungLaden = ref(false)
        const anmeldungErfolg = ref(false)
        const anmeldungFehler = ref('')

        const monthLabel = computed(() =>
            new Date(currentYear.value, currentMonth.value).toLocaleString('de-DE', {
                month: 'long', year: 'numeric',
            })
        )

        const weekDays = ['Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So']

        function getDaysInMonth(year, month) {
            return new Date(year, month + 1, 0).getDate()
        }
        function getFirstDayOfMonth(year, month) {
            const d = new Date(year, month, 1).getDay()
            return d === 0 ? 6 : d - 1
        }

        const calendarCells = computed(() => {
            const year = currentYear.value
            const month = currentMonth.value
            const daysInMonth = getDaysInMonth(year, month)
            const firstDay = getFirstDayOfMonth(year, month)
            const daysInPrevMonth = getDaysInMonth(year, month - 1)
            const cells = []

            for (let i = firstDay - 1; i >= 0; i--) {
                cells.push({ day: daysInPrevMonth - i, isCurrentMonth: false, isToday: false, events: [] })
            }

            const todayDate = new Date()
            for (let d = 1; d <= daysInMonth; d++) {
                const isToday = d === todayDate.getDate() && month === todayDate.getMonth() && year === todayDate.getFullYear()
                const dateStr = `${year}-${String(month + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`
                const dayEvents = events.value.filter(e => e.start === dateStr)
                cells.push({ day: d, isCurrentMonth: true, isToday, events: dayEvents })
            }

            const remaining = (7 - (cells.length % 7)) % 7
            for (let d = 1; d <= remaining; d++) {
                cells.push({ day: d, isCurrentMonth: false, isToday: false, events: [] })
            }
            return cells
        })

        function prevMonth() {
            if (currentMonth.value === 0) { currentMonth.value = 11; currentYear.value-- }
            else currentMonth.value--
        }
        function nextMonth() {
            if (currentMonth.value === 11) { currentMonth.value = 0; currentYear.value++ }
            else currentMonth.value++
        }

        async function loadEvents() {
            const start = `${currentYear.value}-${String(currentMonth.value + 1).padStart(2, '0')}-01`
            const end = `${currentYear.value}-${String(currentMonth.value + 1).padStart(2, '0')}-${getDaysInMonth(currentYear.value, currentMonth.value)}`
            try {
                events.value = await apiCall('diakronos.diakonos.api.kalender.get_events', {
                    start_date: start, end_date: end,
                }) || []
            } catch (err) {
                console.error('Kalender loadEvents error:', err)
                events.value = []
            }
        }

        function openEventDetail(evt) {
            selectedEvent.value = evt
            showDetail.value = true
            anmeldungErfolg.value = false
            anmeldungFehler.value = ''
        }
        function closeDetail() {
            showDetail.value = false
            selectedEvent.value = null
        }

        function formatEventDate(evt) {
            if (!evt.startDatetime) return evt.start || ''
            const d = new Date(evt.startDatetime)
            return d.toLocaleDateString('de-DE', { weekday: 'long', day: '2-digit', month: 'long', year: 'numeric' })
                + (evt.allDay ? '' : ' ' + d.toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' }) + ' Uhr')
        }

        async function jetzt_anmelden() {
            if (!selectedEvent.value?.registrierungslinkId) return
            anmeldungLaden.value = true
            anmeldungFehler.value = ''
            try {
                const res = await apiCall(
                    'diakronos.diakonos.api.veranstaltungsanmeldung.register_mitglied',
                    { registrierungslink_id: selectedEvent.value.registrierungslinkId }
                )
                if (res?.success) {
                    anmeldungErfolg.value = true
                    showToast('Anmeldung erfolgreich!', 'success')
                }
            } catch (err) {
                anmeldungFehler.value = err?.message || 'Anmeldung fehlgeschlagen.'
            } finally {
                anmeldungLaden.value = false
            }
        }

        watch([currentYear, currentMonth], loadEvents, { immediate: true })

        return {
            monthLabel, weekDays, calendarCells, prevMonth, nextMonth,
            showDetail, selectedEvent, openEventDetail, closeDetail,
            anmeldungLaden, anmeldungErfolg, anmeldungFehler,
            jetzt_anmelden, formatEventDate,
        }
    },
}
</script>

<style scoped>
.dk-calendar-event {
    cursor: default;
}
.dk-calendar-event.has-anmeldung {
    cursor: pointer;
    background: var(--dk-brand-500);
    color: #fff;
    border-radius: 4px;
    padding: 1px 6px;
    font-size: 11px;
}
.dk-calendar-event.has-anmeldung:hover {
    background: var(--dk-brand-600, #5a6fd6);
}
.kl-event-meta {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 13px;
    color: var(--dk-text-muted);
    margin-bottom: 16px;
}
.kl-anmeldung-box {
    background: var(--dk-surface-2);
    border-radius: 8px;
    padding: 12px;
    font-size: 13px;
}
.kl-anmeldung-hint { color: var(--dk-text-muted); margin: 0; }
.kl-anmeldung-success {
    color: var(--dk-success);
    font-weight: 600;
}
.kl-anmeldung-error {
    color: var(--dk-danger);
    font-size: 13px;
}
</style>
