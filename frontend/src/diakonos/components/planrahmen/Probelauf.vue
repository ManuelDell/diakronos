<template>
  <section class="pr-probe">
    <h2>Probelauf ohne Speichern</h2>
    <p>Prüfe acht Wochen mit den vorhandenen Stammdaten. Es werden keine Pläne oder Einträge gespeichert.</p>
    <label class="dk-form-group">Beginn<input v-model="ab" type="date" class="dk-form-input" /></label>
    <PrParameterForm v-if="definition.parameter?.length" :parameter="definition.parameter" v-model="parameter" />
    <button type="button" class="dk-btn dk-btn-secondary" :disabled="busy || !ab" @click="ausfuehren">{{ busy ? 'Wird geprüft …' : 'Probelauf 8 Wochen' }}</button>
    <PrMeldungen v-if="fehler.length" :meldungen="fehler" />
    <template v-if="ergebnis">
      <p v-if="veraltet" role="status" class="pr-probe-hinweis">Der Entwurf wurde geändert. Bitte den Probelauf wiederholen.</p>
      <PrMeldungen :meldungen="meldungen" zusammenfassung />
      <h3>Datenbedarf</h3>
      <ul><li v-for="(b,i) in ergebnis.bedarf || []" :key="i">{{ b.abdeckung }} <span v-if="b.detail">— {{ b.detail }}</span></li></ul>
      <label v-if="ansichten.length > 1" class="dk-form-group">Ansicht<select v-model.number="ansichtIndex" class="dk-form-select"><option v-for="(a,i) in ansichten" :value="i" :key="i">{{ a.name || a.art }}</option></select></label>
      <label v-if="['programm','ablauf'].includes(ansicht.art)" class="dk-form-group">Termin<select v-model="terminId" class="dk-form-select"><option v-for="t in ergebnis.termine || []" :value="t.id" :key="t.id">{{ datumText(t.datum) }}</option></select></label>
      <PrAnsicht :plan="plan" :termine="ergebnis.termine || []" :eintraege="ergebnis.eintraege || []" :definitionen="definitionen" :ansicht="ansicht" :termin="termin" :bearbeitbar="false" />
      <p v-if="!ergebnis.termine?.length">In diesem Zeitraum entstehen keine Termine. Prüfe Beginn und Planparameter.</p>
    </template>
  </section>
</template>
<script setup>
import { ref, computed, watch, onUnmounted } from 'vue'
import { usePlanrahmen, fehlerMeldungen, datumText, anzeigeUebernehmen } from '../../composables/usePlanrahmen.js'
import PrParameterForm from './PrParameterForm.vue'
import PrMeldungen from './PrMeldungen.vue'
import PrAnsicht from './PrAnsicht.vue'
const props = defineProps({ definition: { type: Object, required: true } })
const { trockenlauf } = usePlanrahmen()
const ab = ref(((d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`)(new Date()))
const parameter = ref({})
const busy = ref(false)
const fehler = ref([])
const ergebnis = ref(null)
const pruefDefinition = ref(null)
const pruefParameter = ref({})
const signatur = ref('')
const ansichtIndex = ref(0)
const terminId = ref('')
let nummer = 0
const veraltet = computed(() => signatur.value !== JSON.stringify([props.definition, parameter.value, ab.value]))
const ansichten = computed(() => pruefDefinition.value?.ansichten?.length ? pruefDefinition.value.ansichten : [{art:'tabelle'}])
const ansicht = computed(() => ansichten.value[ansichtIndex.value] || ansichten.value[0])
const definitionen = computed(() => new Map([['probelauf', pruefDefinition.value]]))
const plan = computed(() => ({ titel: pruefDefinition.value?.name || 'Probelauf', parameter: pruefParameter.value, ansichten: ansichten.value }))
const termin = computed(() => ergebnis.value?.termine?.find(t => t.id === terminId.value) || ergebnis.value?.termine?.[0] || null)
const meldungen = computed(() => [...(ergebnis.value?.meldungen || []), ...(ergebnis.value?.verstoesse || [])].map(m => typeof m === 'string' ? {meldung:m,stufe:'hinweis'} : {...m,pfad:m.pfad || m.feld_pfad,stufe:({muss:'fehler',sollte:'warnung'}[m.stufe] || m.stufe || 'hinweis')}))
async function ausfuehren() {
  const n = ++nummer
  busy.value = true
  fehler.value = []
  const def = JSON.parse(JSON.stringify(props.definition))
  const args = JSON.parse(JSON.stringify(parameter.value))
  const sig = JSON.stringify([def,args,ab.value])
  try {
    const res = await trockenlauf(def,args,ab.value,8)
    if (n !== nummer) return
    ergebnis.value = res
    pruefDefinition.value = def
    pruefParameter.value = args
    signatur.value = sig
    anzeigeUebernehmen(res.anzeige || {})
    ansichtIndex.value = 0
    terminId.value = res.termine?.[0]?.id || ''
  } catch (e) { if (n === nummer) fehler.value = fehlerMeldungen(e) }
  finally { if (n === nummer) busy.value = false }
}
watch(() => props.definition.id, () => { nummer++; busy.value = false; ergebnis.value = null; parameter.value = {} })
onUnmounted(() => { nummer++ })
</script>
<style scoped>
.pr-probe { display: grid; gap: 14px; min-width: 0; }
.pr-probe h2,.pr-probe h3,.pr-probe p { margin: 0; }
.pr-probe p { color: var(--dk-text-muted); }
.pr-probe-hinweis { color: var(--dk-warning) !important; }
.pr-probe > .dk-form-group { max-width: 460px; }
</style>
