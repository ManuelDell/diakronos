<template>
  <BaseWidgetCard
    label="Meine Dienste"
    gridSize="medium"
    :loading
    :error
    :isEmpty
    emptyMessage="Keine Dienste eingetragen."
    :isEditing
    @refresh="refresh"
    @hide="$emit('hide')"
    @collapse-change="$emit('collapse-change', $event)"
  >
    <ul class="msv-list">
      <li v-for="(d, i) in nextServices" :key="d.schluessel || i" class="msv-row">
        <div class="msv-main">
          <div class="msv-title">{{ d.titel }}</div>
          <div class="msv-meta">{{ d.zeit }}</div>
        </div>
        <div class="msv-side">
          <span v-if="d.rolle" class="msv-rolle">{{ d.rolle }}</span>
          <span class="dk-badge" :class="d.art === 'Vorbereitung' ? 'dk-badge-warning' : 'dk-badge-info'">
            {{ d.art }}
          </span>
        </div>
      </li>
    </ul>
    <a class="msv-link" href="#/planrahmen/meine-dienste">Alle Dienste ansehen</a>
  </BaseWidgetCard>
</template>
<script setup>
import BaseWidgetCard from './BaseWidgetCard.vue'
import { useWidgetData } from '../../composables/useWidgetData'
import { apiCall } from '../../composables/useApi.js'
import { feldName, kachelEintraege } from '../planrahmen/meine-dienste.mjs'
import { computed, onMounted, ref } from 'vue'

const props = defineProps({ isEditing: Boolean, refreshInterval: { type: Number, default: 60 } })
const emit = defineEmits(['hide', 'collapse-change'])
const { data, loading: alteLaden, error: alterFehler, refresh: alteNeu } = useWidgetData('my-services', props.refreshInterval)

/**
 * OP-HANDY-5: Kachel aus BEIDEN Quellen speisen.
 *
 * Der Dashboard-Widget-Endpunkt (`get_meine_dienste`) liest nur das alte
 * Kronos-Modell (Element Mitarbeiter). Der Plan-Rahmen fuehrt die Dienste der
 * veroeffentlichten Plaene — dort stehen die meisten Einsaetze. Beides wird
 * zusammengefuehrt, damit die Kachel nicht „Keine Dienste eingetragen." sagt,
 * waehrend unter „Meine Dienste" 6–15 Einsaetze stehen.
 */
const planDienste = ref([])
const planLaedt = ref(false)
let planFehler = ref(null)

async function planNeu() {
  planLaedt.value = true
  planFehler.value = null
  try {
    const liste = await apiCall('diakronos.planrahmen.api.meine_dienste', {})
    planDienste.value = Array.isArray(liste) ? liste : []
  } catch (e) {
    planFehler.value = e?.message || 'Fehler'
    planDienste.value = []
  } finally {
    planLaedt.value = false
  }
}

function refresh() { alteNeu(); planNeu() }
onMounted(planNeu)

const loading = computed(() => alteLaden.value || planLaedt.value)
const error = computed(() => (planDienste.value.length || data.value ? null : (alterFehler.value || planFehler.value)))

// Alte Kronos-Quelle: { vorbereitung: [...], einsatz: [...] }
function alteEintraege() {
  const d = data.value || {}
  const vor = Array.isArray(d.vorbereitung) ? d.vorbereitung : []
  const ein = Array.isArray(d.einsatz) ? d.einsatz : []
  return [
    ...vor.map((x) => ({
      schluessel: 'alt-v-' + x.element + (x.mitglied || ''),
      titel: x.element_name || '–',
      zeit: formatDateTime(x.element_start),
      rolle: x.dienstrolle_name || '',
      art: 'Vorbereitung',
      sort: x.element_start || '',
    })),
    ...ein.map((x) => ({
      schluessel: 'alt-e-' + x.element + (x.mitglied || ''),
      titel: x.element_name || '–',
      zeit: formatDateTime(x.element_start),
      rolle: x.dienstrolle_name || '',
      art: 'Einsatz',
      sort: x.element_start || '',
    })),
  ]
}

// Plan-Rahmen-Quelle: veroeffentlichte Plaene, ein Eintrag je Zuordnung.
function planEintraege() {
  return planDienste.value.map((d, i) => {
    const rolle = d.lied_titel ? `${d.lied_titel} · ${feldName(d.feld_pfad)}` : feldName(d.feld_pfad)
    return {
      schluessel: 'plan-' + (d.plan || '') + '-' + (d.termin_id || d.termin || '') + '-' + (d.feld_pfad || '') + '-' + i,
      titel: d.plan_titel || d.titel || 'Plan',
      zeit: [datumZeit(d.termin, d.uhrzeit), d.abwesend ? '⚠️ Abwesenheit gemeldet' : ''].filter(Boolean).join(' · '),
      rolle,
      art: 'Einsatz',
      sort: d.termin || '',
    }
  })
}

// P1-11b (Befund 4): beide Quellen zusammenfuehren und Dubletten entfernen —
// derselbe Einsatz stand sonst doppelt in der Kachel, wenn er in beiden
// Modellen lag.
const alleEintraege = computed(() => kachelEintraege(planEintraege(), alteEintraege()))
const nextServices = computed(() => alleEintraege.value.slice(0, 3))
const isEmpty = computed(() => !loading.value && alleEintraege.value.length === 0)

function datumZeit(datum, uhrzeit) {
  if (!datum) return ''
  const d = new Date(String(datum).slice(0, 10) + 'T12:00:00')
  const tag = isNaN(d) ? String(datum)
    : d.toLocaleDateString('de-DE', { weekday: 'short', day: '2-digit', month: 'short' })
  return uhrzeit ? tag + ', ' + String(uhrzeit).slice(0, 5) + ' Uhr' : tag
}

function formatDateTime(s) {
  if (!s) return ''
  const d = new Date(String(s).replace(' ', 'T'))
  if (isNaN(d)) return s
  return (
    d.toLocaleDateString('de-DE', { weekday: 'short', day: '2-digit', month: 'short' }) +
    ', ' + d.toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' })
  )
}
</script>

<style scoped>
.msv-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 2px; }
.msv-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 8px 4px;
  border-bottom: 1px solid var(--dk-border);
}
.msv-row:last-child { border-bottom: none; }
.msv-main { flex: 1; min-width: 0; }
.msv-title {
  font-size: 0.875rem;
  font-weight: 500;
  color: var(--dk-text);
  line-height: 1.3;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.msv-meta { font-size: 0.75rem; color: var(--dk-text-muted); margin-top: 2px; }
.msv-side { display: inline-flex; align-items: center; gap: 8px; flex-shrink: 0; }
.msv-rolle { font-size: 0.72rem; color: var(--dk-text-muted); max-width: 120px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.msv-link { display: inline-block; margin-top: 10px; font-size: 0.8rem; color: var(--dk-brand-700, var(--dk-info)); text-decoration: none; }
.msv-link:hover { text-decoration: underline; }
</style>
