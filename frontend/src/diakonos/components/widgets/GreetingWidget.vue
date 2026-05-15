<template>
  <div class="dk-widget-card dk-widget-full dk-widget-greeting">
    <div class="dk-widget-greeting-inner">
      <div>
        <h1 class="dk-hub-greeting">
          Guten {{ greeting }},
          <span class="dk-muted">{{ firstName }}.</span>
        </h1>
        <p class="dk-hub-sub">{{ todayLabel }}</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useSession } from '../../composables/useSession'

const { user } = useSession()

const firstName = computed(() => {
  if (!user.value?.fullname) return ''
  return user.value.fullname.split(' ')[0]
})

const greeting = computed(() => {
  const h = new Date().getHours()
  if (h < 12) return 'Morgen'
  if (h < 18) return 'Tag'
  return 'Abend'
})

const todayLabel = computed(() => {
  return new Date().toLocaleDateString('de-DE', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })
})
</script>
