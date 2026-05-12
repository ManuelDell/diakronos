<template>
  <BaseWidgetCard label="Mini-Kalender" gridSize="small" :loading="false" :error="null" :isEmpty="false" :isEditing @refresh="refresh" @hide="$emit('hide')" @collapse-change="$emit('collapse-change', $event)">
    <div class="mini-calendar">
      <div class="cal-header">
        <span v-for="d in ['Mo','Di','Mi','Do','Fr','Sa','So']" :key="d">{{ d }}</span>
      </div>
      <div class="cal-days">
        <span v-for="day in calendarDays" :key="day.key" :class="{ 'out-of-month': !day.current, 'today': day.today }" @click="navigate('#/kalender')">
          {{ day.label }}
        </span>
      </div>
    </div>
  </BaseWidgetCard>
</template>
<script setup>
import BaseWidgetCard from './BaseWidgetCard.vue'
import { computed } from 'vue'
const props = defineProps({ isEditing: Boolean, refreshInterval: { type: Number, default: 60 } })
const emit = defineEmits(['hide', 'collapse-change'])
const refresh = () => {}
const navigate = (href) => { window.location.hash = href }
const calendarDays = computed(() => {
  const now = new Date()
  const year = now.getFullYear()
  const month = now.getMonth()
  const firstDay = new Date(year, month, 1)
  const lastDay = new Date(year, month + 1, 0)
  const startDay = (firstDay.getDay() + 6) % 7
  const daysInMonth = lastDay.getDate()
  const days = []
  const prevMonthLast = new Date(year, month, 0).getDate()
  for (let i = startDay - 1; i >= 0; i--) {
    days.push({ key: 'p' + i, label: prevMonthLast - i, current: false, today: false })
  }
  const today = now.getDate()
  for (let i = 1; i <= daysInMonth; i++) {
    days.push({ key: 'c' + i, label: i, current: true, today: i === today })
  }
  const remaining = (7 - (days.length % 7)) % 7
  for (let i = 1; i <= remaining; i++) {
    days.push({ key: 'n' + i, label: i, current: false, today: false })
  }
  return days
})
</script>
