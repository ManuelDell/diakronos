<template>
    <div class="dk-screen dk-screen-wide dk-screen-enter">
        <div class="dk-screen-header">
            <div>
                <h1 class="dk-screen-title">Kalender</h1>
            </div>
            <div class="dk-screen-actions">
                <button
                    class="dk-btn dk-btn-secondary dk-btn-sm"
                    @click="prevMonth"
                >
                    ‹ Zurück
                </button>
                <span class="text-lg font-semibold min-w-[140px] text-center">
                    {{ monthLabel }}
                </span>
                <button
                    class="dk-btn dk-btn-secondary dk-btn-sm"
                    @click="nextMonth"
                >
                    Weiter ›
                </button>
            </div>
        </div>

        <!-- Wochentage + Tage -->
        <div class="dk-calendar">
            <div
                v-for="day in weekDays"
                :key="day"
                class="dk-calendar-header"
            >
                {{ day }}
            </div>
            <div
                v-for="(cell, idx) in calendarCells"
                :key="idx"
                class="dk-calendar-cell"
                :class="{
                    'is-today': cell.isToday,
                    'is-other-month': !cell.isCurrentMonth,
                }"
            >
                <div class="dk-calendar-day">{{ cell.day }}</div>
                <div class="flex flex-col gap-1">
                    <span
                        v-for="evt in cell.events"
                        :key="evt.title"
                        class="dk-calendar-event"
                    >
                        {{ evt.title }}
                    </span>
                </div>
            </div>
        </div>
    </div>
</template>

<script>
import { ref, computed, watch } from 'vue'
import { apiCall } from '../composables/useApi.js'

export default {
    name: 'Kalender',
    setup() {
        const today = new Date()
        const currentYear = ref(today.getFullYear())
        const currentMonth = ref(today.getMonth())
        const events = ref([])

        const monthLabel = computed(() => {
            return new Date(currentYear.value, currentMonth.value).toLocaleString('de-DE', {
                month: 'long',
                year: 'numeric',
            })
        })

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
                const day = daysInPrevMonth - i
                cells.push({ day, isCurrentMonth: false, isToday: false, events: [] })
            }

            const todayDate = new Date()
            for (let d = 1; d <= daysInMonth; d++) {
                const isToday =
                    d === todayDate.getDate() &&
                    month === todayDate.getMonth() &&
                    year === todayDate.getFullYear()
                const dateStr = `${year}-${String(month + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`
                const dayEvents = events.value.filter((e) => e.start === dateStr)
                cells.push({ day: d, isCurrentMonth: true, isToday, events: dayEvents })
            }

            const remaining = (7 - (cells.length % 7)) % 7
            for (let d = 1; d <= remaining; d++) {
                cells.push({ day: d, isCurrentMonth: false, isToday: false, events: [] })
            }
            return cells
        })

        function prevMonth() {
            if (currentMonth.value === 0) {
                currentMonth.value = 11
                currentYear.value--
            } else {
                currentMonth.value--
            }
        }

        function nextMonth() {
            if (currentMonth.value === 11) {
                currentMonth.value = 0
                currentYear.value++
            } else {
                currentMonth.value++
            }
        }

        async function loadEvents() {
            const start = `${currentYear.value}-${String(currentMonth.value + 1).padStart(2, '0')}-01`
            const end = `${currentYear.value}-${String(currentMonth.value + 1).padStart(2, '0')}-${getDaysInMonth(currentYear.value, currentMonth.value)}`
            try {
                events.value = await apiCall('diakronos.diakonos.api.kalender.get_events', {
                    start_date: start,
                    end_date: end,
                }) || []
            } catch (err) {
                console.error('Kalender loadEvents error:', err)
                events.value = []
            }
        }

        watch([currentYear, currentMonth], loadEvents, { immediate: true })

        return { monthLabel, weekDays, calendarCells, prevMonth, nextMonth }
    },
}
</script>
