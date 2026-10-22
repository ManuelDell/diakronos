<template>
  <div class="pr-kalender-wrap">
    <table class="pr-kalender">
      <thead><tr><th v-for="m in monate" :key="m.id" :colspan="mitKw ? 3 : 2">{{ m.name }}</th></tr>
        <tr><template v-for="m in monate" :key="m.id"><th v-if="mitKw">KW</th><th>Tag</th><th>Einteilung</th></template></tr>
      </thead>
      <tbody><tr v-for="tag in 31" :key="tag">
        <template v-for="m in monate" :key="m.id">
          <td v-if="mitKw">{{ m.days[tag - 1]?.kw || '' }}</td>
          <td>{{ m.days[tag - 1] ? `${tag}. ${weekdayLabel(m.days[tag - 1].weekday)}` : '' }}</td>
          <td :class="{ 'pr-kalender-inaktiv': !m.days[tag - 1]?.inside }">
            <template v-if="m.days[tag - 1]">
              <div v-for="t in termineJe(m.days[tag - 1].date)" :key="t.id" class="pr-kalender-eintrag">
                <button class="pr-kalender-termin" @click="$emit('bearbeiten', t, ersterPfad(t))">
                  {{ calendarTime(t, definitionen.get(t.plantyp_version)) }} {{ terminText(t) }}
                  <span v-if="eintraegeJe(t).some(e => e.fixiert)" title="Von Hand festgelegt">📌</span>
                </button>
                <PrMeldungen v-if="meldungenZeigen" :meldungen="eintraegeJe(t).flatMap(e => e.meldungen || [])" kompakt :bezeichnung="kalenderBezeichnung(t)" />
              </div>
              <span v-if="!termineJe(m.days[tag - 1].date).length && ansicht.alle_tage !== false">–</span>
            </template>
          </td>
        </template>
      </tr></tbody>
    </table>
    <p v-if="!monate.length">Für diesen Zeitraum gibt es noch keine Termine.</p>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { calendarMonths, weekdayLabel, calendarTime } from './calendar.mjs'
import { planKontext, formatVorlage, anzeigeZu, reihenFelder, reihePraefix, wertText } from '../../composables/usePlanrahmen.js'
import PrMeldungen from './PrMeldungen.vue'
const props = defineProps({
  plan: { type: Object, default: null }, termine: { type: Array, default: () => [] },
  eintraege: { type: Array, default: () => [] }, definitionen: { type: [Object, Map], default: () => ({}) },
  ansicht: { type: Object, default: () => ({}) },
  // UXP-R19: Regelmeldungen nur fuer Planer sichtbar.
  meldungenZeigen: { type: Boolean, default: false },
})
defineEmits(['bearbeiten'])
const monate = computed(() => calendarMonths(props.plan?.zeitraum_von, props.plan?.zeitraum_bis))
const mitKw = computed(() => props.ansicht.kw !== false)
const definitionen = computed(() => props.definitionen instanceof Map ? props.definitionen : new Map(Object.entries(props.definitionen)))
const termineMap = computed(() => {
  const map = new Map()
  for (const t of props.termine) { const key = t.datum.slice(0, 10); if (!map.has(key)) map.set(key, []); map.get(key).push(t) }
  return map
})

/** DES-R20: Name der Meldungszeile eines Kalendertags. */
function kalenderBezeichnung(t) {
  const d = typeof t === 'string' ? t : (t?.datum || t?.tag)
  if (!d) return ''
  const alsDatum = new Date(String(d).slice(0, 10) + 'T00:00:00')
  if (Number.isNaN(alsDatum.getTime())) return String(d)
  return alsDatum.toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit', year: 'numeric' })
}
function termineJe(datum) { return termineMap.value.get(datum) || [] }
function eintraegeJe(t) { return props.eintraege.filter(e => e.termin === t.id) }

function felderJe(t) { return reihenFelder(definitionen.value.get(t.plantyp_version)).find(r => r.id === t.reihe)?.felder || [] }
function ersterPfad(t) { return reihePraefix(t.reihe) || felderJe(t)[0]?.id || '' }
function terminText(t) {
  const ctx = planKontext(props.plan, t)
  const felder = new Map(felderJe(t).map(f => [f.id, f]))
  for (const e of eintraegeJe(t)) {
    const id = e.feld_pfad.replace(reihePraefix(t.reihe), '')
    const art = felder.get(id)?.art
    ctx[id] = ['person', 'personen', 'team', 'eintrag'].includes(art)
      ? (Array.isArray(e.wert) ? e.wert.map(anzeigeZu) : anzeigeZu(e.wert)) : e.wert
  }
  const format = props.ansicht.format?.[t.reihe]
  return format ? formatVorlage(format, ctx) : eintraegeJe(t).map(e => wertText(e.wert)).join(' · ')
}
</script>

<style scoped>
.pr-kalender-wrap { overflow-x: auto; border: 1px solid var(--dk-border); border-radius: 12px; }
.pr-kalender { width: 100%; border-collapse: collapse; font-size: .78rem; background: var(--dk-surface); }
.pr-kalender td, .pr-kalender th { border: 1px solid var(--dk-border); padding: 6px; vertical-align: top; }
.pr-kalender th { background: var(--dk-surface-2); }
.pr-kalender-termin { border: 0; background: transparent; color: var(--dk-text); text-align: left; cursor: pointer; min-width: 150px; font: inherit; }
.pr-kalender-inaktiv { background: var(--dk-surface-2); opacity: .7; }
@media print { .pr-kalender-wrap { overflow: visible; } .pr-kalender-termin { min-width: 0; } }
</style>
