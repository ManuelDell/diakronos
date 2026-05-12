<template>
  <div class="kronos-mini-calendar">
    <div class="mini-cal-header">
      <span class="mini-title">{{ monthTitle }}</span>
      <div class="mini-nav">
        <button class="mini-prev" @click="prevMonth">‹</button>
        <button class="mini-next" @click="nextMonth">›</button>
      </div>
    </div>
    <div class="mini-cal-grid">
      <div class="mini-cal-header-row">
        <div class="mini-week-header"></div>
        <div v-for="d in dayHeaders" :key="d" class="mini-day-header">{{ d }}</div>
      </div>
      <div v-for="(week, wi) in weeks" :key="wi" class="mini-cal-week-row">
        <div class="mini-week-number">{{ week.weekNum }}</div>
        <div
          v-for="day in week.days"
          :key="day.dateStr"
          :class="['mini-cal-day', { 'other-month': day.otherMonth, 'today': day.isToday, 'has-event': eventDays.includes(day.dateStr) }]"
          @click="onDayClick(day)"
        >
          {{ day.dayNum }}
          <span v-if="!day.otherMonth && eventDays.includes(day.dateStr)" class="event-dot"></span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue';

const props = defineProps({
  currentMonth: {
    type: String,
    default: () => {
      const now = new Date();
      return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;
    }
  },
  eventDays: { type: Array, default: () => [] },
});

const emit = defineEmits(['dateClick', 'monthChange']);

const dayHeaders = ['Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So'];

const months = [
  'Januar', 'Februar', 'März', 'April', 'Mai', 'Juni',
  'Juli', 'August', 'September', 'Oktober', 'November', 'Dezember'
];

const monthTitle = computed(() => {
  const [y, m] = props.currentMonth.split('-').map(Number);
  return `${months[m - 1]} ${y}`;
});

function getISOWeek(date) {
  const tmp = new Date(date.valueOf());
  const day = (tmp.getDay() + 6) % 7;
  tmp.setDate(tmp.getDate() - day + 3);
  const firstThursday = new Date(tmp.getFullYear(), 0, 4);
  const firstDay = (firstThursday.getDay() + 6) % 7;
  firstThursday.setDate(firstThursday.getDate() - firstDay);
  return 1 + Math.ceil((tmp - firstThursday) / 604800000);
}

const weeks = computed(() => {
  const [y, m] = props.currentMonth.split('-').map(Number);
  const firstOfMonth = new Date(y, m - 1, 1);
  const firstDay = (firstOfMonth.getDay() + 6) % 7; // Mon=0
  const daysInMonth = new Date(y, m, 0).getDate();
  const today = new Date();
  const result = [];
  let dayCounter = 1 - firstDay;

  while (dayCounter <= daysInMonth) {
    const weekStartDate = new Date(y, m - 1, dayCounter < 1 ? 1 : dayCounter);
    const weekNum = getISOWeek(weekStartDate);
    const days = [];
    for (let d = 0; d < 7; d++) {
      let dayNum, otherMonth = false, isToday = false, dateStr = '';
      if (dayCounter <= 0) {
        dayNum = new Date(y, m - 1, 0).getDate() + dayCounter;
        otherMonth = true;
        const pm = m === 1 ? 12 : m - 1, py = m === 1 ? y - 1 : y;
        dateStr = `${py}-${String(pm).padStart(2, '0')}-${String(dayNum).padStart(2, '0')}`;
      } else if (dayCounter > daysInMonth) {
        dayNum = dayCounter - daysInMonth;
        otherMonth = true;
        const nm = m === 12 ? 1 : m + 1, ny = m === 12 ? y + 1 : y;
        dateStr = `${ny}-${String(nm).padStart(2, '0')}-${String(dayNum).padStart(2, '0')}`;
      } else {
        dayNum = dayCounter;
        isToday = today.getFullYear() === y && today.getMonth() === m - 1 && today.getDate() === dayNum;
        dateStr = `${y}-${String(m).padStart(2, '0')}-${String(dayNum).padStart(2, '0')}`;
      }
      days.push({ dayNum, otherMonth, isToday, dateStr });
      dayCounter++;
    }
    result.push({ weekNum, days });
  }
  return result;
});

function prevMonth() {
  const [y, m] = props.currentMonth.split('-').map(Number);
  emit('monthChange', m === 1 ? `${y - 1}-12` : `${y}-${String(m - 1).padStart(2, '0')}`);
}
function nextMonth() {
  const [y, m] = props.currentMonth.split('-').map(Number);
  emit('monthChange', m === 12 ? `${y + 1}-01` : `${y}-${String(m + 1).padStart(2, '0')}`);
}
function onDayClick(day) {
  emit('dateClick', day.dateStr);
}
</script>

<style scoped>
.kronos-mini-calendar { font-family: var(--font-family, sans-serif); }
.mini-cal-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.mini-title { font-weight: 600; font-size: 13px; }
.mini-nav { display: flex; gap: 2px; }
.mini-nav button { background: none; border: none; cursor: pointer; font-size: 18px; padding: 0 4px; line-height: 1; color: var(--dk-text-muted, #666); }
.mini-nav button:hover { color: var(--dk-text, #15182a); }
.mini-cal-grid { display: block; width: 100%; }
.mini-cal-header-row, .mini-cal-week-row { display: grid; grid-template-columns: 18px repeat(7, 1fr); gap: 0 1px; min-width: 0; }
.mini-cal-header-row { margin-bottom: 4px; }
.mini-day-header { text-align: center; font-size: 10px; font-weight: 600; color: var(--dk-text-muted, #666); padding-bottom: 4px; min-width: 0; overflow: hidden; }
.mini-week-header { }
.mini-week-number { font-size: 9px; color: var(--dk-text-subtle, #999); display: flex; align-items: center; justify-content: center; min-width: 0; }
.mini-cal-week-row { margin-bottom: 2px; align-items: center; }
.mini-cal-day {
  position: relative;
  font-size: 11px;
  cursor: pointer;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  min-width: 0;
  width: 100%;
  aspect-ratio: 1;
  max-width: 26px;
  margin: 0 auto;
}
.mini-cal-day:hover { background: var(--dk-bg-subtle, #f3f3ef); }
.mini-cal-day.other-month { color: var(--dk-text-subtle, #bbb); }
.mini-cal-day.today { background: var(--dk-brand-500, #1c2850); color: #fff; font-weight: 700; }
.mini-cal-day.has-event:not(.today) { font-weight: 600; }
.event-dot {
  position: absolute;
  bottom: 1px;
  left: 50%;
  transform: translateX(-50%);
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: var(--dk-accent, #d4a24c);
}
.mini-cal-day.today .event-dot { background: rgba(255,255,255,0.8); }
</style>
