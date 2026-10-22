<template>
  <div class="pr-parameter">
    <div v-for="p in parameter" :key="p.id" class="pr-parameter-feld">
      <label class="pr-parameter-label" :for="'pr-p-' + p.id">
        {{ p.name || p.id }}
        <span v-if="p.art === 'zeitraum'" class="pr-parameter-hinweis">(von bis)</span>
      </label>

      <!-- Zeitraum: zwei Daten -->
      <div v-if="p.art === 'zeitraum'" class="pr-parameter-zeitraum">
        <input
          :id="'pr-p-' + p.id" type="date" class="pr-input"
          :value="zeitraumVon(p.id)"
          @change="setzeZeitraum(p.id, 'von', $event.target.value)"
        />
        <span class="pr-parameter-bis">bis</span>
        <input
          type="date" class="pr-input"
          :value="zeitraumBis(p.id)"
          @change="setzeZeitraum(p.id, 'bis', $event.target.value)"
        />
      </div>

      <!-- Auswahl mehrfach -->
      <div v-else-if="p.art === 'auswahl' && p.mehrfach" class="pr-parameter-wahlliste">
        <label v-for="o in auswahlOptionen(p)" :key="o.wert" class="pr-parameter-wahl">
          <input type="checkbox" :checked="mehrfachEnthalten(p.id, o.wert)" @change="toggleMehrfach(p.id, o.wert, $event.target.checked)" />
          {{ o.text }}
        </label>
      </div>

      <!-- Auswahl -->
      <select v-else-if="p.art === 'auswahl'" :id="'pr-p-' + p.id" class="pr-input" :value="wert(p.id)" @change="setze(p.id, $event.target.value || null)">
        <option value="">— bitte wählen —</option>
        <option v-for="o in auswahlOptionen(p)" :key="o.wert" :value="o.wert">{{ o.text }}</option>
      </select>

      <!-- Zahl -->
      <input v-else-if="p.art === 'zahl'" :id="'pr-p-' + p.id" type="number" class="pr-input" :value="wert(p.id)" @change="setze(p.id, $event.target.value === '' ? null : Number($event.target.value))" />

      <!-- Datum -->
      <input v-else-if="p.art === 'datum'" :id="'pr-p-' + p.id" type="date" class="pr-input" :value="wert(p.id)" @change="setze(p.id, $event.target.value || null)" />

      <!-- Text (Vorgabe) -->
      <input v-else :id="'pr-p-' + p.id" type="text" class="pr-input" :value="wert(p.id)" :placeholder="p.platzhalter || ''" @change="setze(p.id, $event.target.value)" />
    </div>
    <div v-if="!parameter.length" class="pr-parameter-leer">
      Diese Planvorlage braucht keine Angaben — der Plan kann direkt angelegt werden.
    </div>
  </div>
</template>

<script setup>
/**
 * Generisches Parameterformular aus der Plantyp-Deklaration
 * (art: text/zahl/datum/zeitraum/auswahl, meherfach). Keine feste Feldliste.
 */
// UXP-R23/P3-1b W3: Auswahlwerte zeigen ihren Anzeigenamen.
import { auswahlOptionen } from './auswahlwerte.mjs'

const props = defineProps({
  parameter: { type: Array, default: () => [] },
  modelValue: { type: Object, default: () => ({}) },
})
const emit = defineEmits(['update:modelValue'])

function wert(id) {
    const v = props.modelValue?.[id]
    return Array.isArray(v) ? '' : (v ?? '')
}

function setze(id, wertNeu) {
    const neu = { ...(props.modelValue || {}) }
    if (wertNeu === null || wertNeu === '') delete neu[id]
    else neu[id] = wertNeu
    emit('update:modelValue', neu)
}

function zeitraumWert(id) {
    const v = props.modelValue?.[id]
    return Array.isArray(v) ? v : ['', '']
}
function zeitraumVon(id) { return zeitraumWert(id)[0] || '' }
function zeitraumBis(id) { return zeitraumWert(id)[1] || '' }
function setzeZeitraum(id, teil, datum) {
    const alt = zeitraumWert(id).slice()
    alt[teil === 'von' ? 0 : 1] = datum
    // Teilweise Angaben bleiben erhalten (erst beide Daten sind ein Planraum).
    const neu = { ...(props.modelValue || {}) }
    if (alt[0] || alt[1]) neu[id] = alt
    else delete neu[id]
    emit('update:modelValue', neu)
}

function mehrfachEnthalten(id, wertNeu) {
    return Array.isArray(props.modelValue?.[id]) && props.modelValue[id].includes(wertNeu)
}
function toggleMehrfach(id, wertNeu, an) {
    const alt = Array.isArray(props.modelValue?.[id]) ? props.modelValue[id].slice() : []
    const i = alt.indexOf(wertNeu)
    if (an && i === -1) alt.push(wertNeu)
    if (!an && i !== -1) alt.splice(i, 1)
    setze(id, alt.length ? alt : null)
}
</script>

<style scoped>
.pr-parameter { display: flex; flex-direction: column; gap: 12px; }
.pr-parameter-feld { display: flex; flex-direction: column; gap: 5px; }
.pr-parameter-label { font-size: 0.8rem; font-weight: 600; color: var(--dk-text-muted); }
.pr-parameter-hinweis { font-weight: 400; color: var(--dk-text-subtle); }
.pr-input {
  width: 100%; padding: 8px 10px; border-radius: 8px;
  border: 1px solid var(--dk-border); background: var(--dk-surface);
  color: var(--dk-text); font-size: 0.88rem; font-family: inherit;
}
.pr-input:focus { outline: 2px solid color-mix(in oklch, var(--dk-brand-400) 50%, transparent); outline-offset: 0; border-color: var(--dk-brand-400); }
.pr-parameter-zeitraum { display: flex; align-items: center; gap: 8px; }
.pr-parameter-zeitraum .pr-input { width: auto; flex: 1; }
.pr-parameter-bis { font-size: 0.78rem; color: var(--dk-text-subtle); }
.pr-parameter-wahlliste { display: flex; flex-wrap: wrap; gap: 8px 14px; }
.pr-parameter-wahl { display: inline-flex; align-items: center; gap: 6px; font-size: 0.85rem; color: var(--dk-text); cursor: pointer; }
.pr-parameter-leer { font-size: 0.84rem; color: var(--dk-text-muted); padding: 4px 0; }
</style>
