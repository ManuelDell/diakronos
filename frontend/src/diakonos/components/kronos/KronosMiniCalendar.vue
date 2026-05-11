<template>
  <div class="kronos-mini-calendar">
    <div class="mini-cal-header">
      <span class="mini-title">{{ monthTitle }}</span>
      <div class="mini-nav">
        <button class="mini-prev" @click="prevMonth">&lt;</button>
        <button class="mini-next" @click="nextMonth">&gt;</button>
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
          :class="['mini-cal-day', { 'other-month': day.otherMonth, 'today': day.isToday }]"
          @click="onDayClick(day)"
        >
          {{ day.dayNum }}
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
  }
});

const emit = defineEmits(['dateClick', 'monthChange']);

const dayHeaders = ['S', 'M', 'D', 'M', 'D', 'F', 'S'];

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
  const firstDay = firstOfMonth.getDay();
  const daysInMonth = new Date(y, m, 0).getDate();
  const numWeeks = Math.ceil((daysInMonth + firstDay) / 7);
  const today = new Date();
  const isCurrentMonth = today.getFullYear() === y && today.getMonth() === m - 1;

  const result = [];
  let dayCounter = 1 - firstDay;

  for (let week = 0; week < numWeeks; week++) {
    const weekStartDate = new Date(y, m - 1, 1 + dayCounter);
    const weekNum = getISOWeek(weekStartDate);
    const days = [];

    for (let d = 0; d < 7; d++) {
      let dayNum, otherMonth = false, isToday = false, dateStr = '';

      if (dayCounter <= 0) {
        dayNum = new Date(y, m - 1, 0).getDate() + dayCounter;
        otherMonth = true;
        const prevMonth = m === 1 ? 12 : m - 1;
        const prevYear = m === 1 ? y - 1 : y;
        dateStr = `${prevYear}-${String(prevMonth).padStart(2, '0')}-${String(dayNum).padStart(2, '0')}`;
      } else if (dayCounter > daysInMonth) {
        dayNum = dayCounter - daysInMonth;
        otherMonth = true;
        const nextMonth = m === 12 ? 1 : m + 1;
        const nextYear = m === 12 ? y + 1 : y;
        dateStr = `${nextYear}-${String(nextMonth).padStart(2, '0')}-${String(dayNum).padStart(2, '0')}`;
      } else {
        dayNum = dayCounter;
        if (isCurrentMonth && dayNum === today.getDate()) {
          isToday = true;
        }
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
  const newDate = m === 1 ? `${y - 1}-12` : `${y}-${String(m - 1).padStart(2, '0')}`;
  emit('monthChange', newDate);
}

function nextMonth() {
  const [y, m] = props.currentMonth.split('-').map(Number);
  const newDate = m === 12 ? `${y + 1}-01` : `${y}-${String(m + 1).padStart(2, '0')}`;
  emit('monthChange', newDate);
}

function onDayClick(day) {
  emit('dateClick', day.dateStr);
}
</script>

<style scoped>
.kronos-mini-calendar {
  padding: 12px;
  font-family: var(--font-family, sans-serif);
}
.mini-cal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}
.mini-title {
  font-weight: 600;
  font-size: 14px;
}
.mini-nav button {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 16px;
  padding: 2px 6px;
  color: var(--text-color, #333);
}
.mini-cal-grid {
  display: flex;
  flex-direction: column;
}
.mini-cal-header-row,
.mini-cal-week-row {
  display: grid;
  grid-template-columns: 24px repeat(7, 1fr);
}
.mini-cal-header-row {
  margin-bottom: 4px;
}
.mini-day-header,
.mini-cal-day {
  text-align: center;
  font-size: 12px;
  line-height: 24px;
}
.mini-day-header {
  font-weight: 600;
  color: var(--muted-color, #666);
}
.mini-week-number {
  font-size: 10px;
  color: var(--muted-color, #999);
  display: flex;
  align-items: center;
  justify-content: center;
}
.mini-cal-day {
  cursor: pointer;
  border-radius: 50%;
  width: 24px;
  height: 24px;
  margin: 0 auto;
}
.mini-cal-day:hover {
  background: var(--hover-bg, #eee);
}
.mini-cal-day.other-month {
  color: var(--muted-color, #bbb);
}
.mini-cal-day.today {
  background: var(--primary, #007bff);
  color: #fff;
}
</style>
