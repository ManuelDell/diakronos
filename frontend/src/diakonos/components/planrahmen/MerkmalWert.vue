<template>
  <!-- Tag: Ja/Nein-Schalter (leer = nicht gesetzt) -->
  <label v-if="merkmal?.art === 'tag'" class="mk-tag" :class="{ 'mk-tag--kompakt': kompakt }" :title="titel">
    <input
      type="checkbox"
      :checked="modelValue === true"
      :disabled="readonly"
      @change="tagSetzen($event.target.checked)"
    />
  </label>

  <!-- Auswahl mehrfach: Checkboxen als Chips -->
  <div v-else-if="merkmal?.art === 'auswahl' && merkmal.mehrfach" class="mk-mehrfach" :class="{ 'mk-mehrfach--kompakt': kompakt }">
    <label v-for="o in auswahlOptionen(merkmal)" :key="o.wert" class="mk-mehrfach-wahl">
      <input
        type="checkbox"
        :checked="liste.includes(o.wert)"
        :disabled="readonly"
        @change="mehrfachToggle(o.wert, $event.target.checked)"
      />
      <span>{{ o.text }}</span>
    </label>
  </div>

  <!-- Auswahl: Dropdown -->
  <select
    v-else-if="merkmal?.art === 'auswahl'"
    class="mk-eingabe"
    :class="{ 'mk-eingabe--kompakt': kompakt }"
    :value="modelValue ?? ''"
    :disabled="readonly"
    :aria-label="merkmal?.name || merkmal?.id"
    @change="auswahlSetzen($event.target.value)"
  >
    <option value="">— leer —</option>
    <option v-for="o in auswahlOptionen(merkmal)" :key="o.wert" :value="o.wert">{{ o.text }}</option>
  </select>

  <!-- Person: Dropdown über alle geladenen Personen; sind Kandidaten (Rolle)
       bekannt, ausschließlich diese (ST2, nur passende Personen). -->
  <span v-else-if="merkmal?.art === 'person'" class="mk-person">
    <select
      class="mk-eingabe"
      :class="{ 'mk-eingabe--kompakt': kompakt }"
      :value="modelValue ?? ''"
      :disabled="readonly"
      :aria-label="merkmal?.name || merkmal?.id"
      @change="personSetzen($event.target.value)"
    >
      <option value="">— leer —</option>
      <option v-for="p in sortiertePersonen" :key="p.id" :value="p.id">
        {{ p.name || p.id }}<template v-if="p.kuerzel"> ({{ p.kuerzel }})</template>
      </option>
    </select>
    <small v-if="kandidatenHinweis" class="mk-hinweis">{{ kandidatenHinweis }}</small>
  </span>

  <!-- Zahl -->
  <input
    v-else-if="merkmal?.art === 'zahl'"
    type="number"
    class="mk-eingabe"
    :class="{ 'mk-eingabe--kompakt': kompakt }"
    :value="modelValue === null || modelValue === undefined ? '' : modelValue"
    :disabled="readonly"
    :aria-label="merkmal?.name || merkmal?.id"
    @change="zahlSetzen($event.target.value)"
  />

  <!-- Datum -->
  <input
    v-else-if="merkmal?.art === 'datum'"
    type="date"
    class="mk-eingabe"
    :class="{ 'mk-eingabe--kompakt': kompakt }"
    :value="stringWert"
    :disabled="readonly"
    :aria-label="merkmal?.name || merkmal?.id"
    @change="datumSetzen($event.target.value)"
  />

  <!-- Text (Vorgabe) -->
  <input
    v-else
    type="text"
    class="mk-eingabe"
    :class="{ 'mk-eingabe--kompakt': kompakt }"
    :value="stringWert"
    :disabled="readonly"
    :aria-label="merkmal?.name || merkmal?.id"
    @change="textSetzen($event.target.value)"
  />
</template>

<script setup>
/**
 * Generische Merkmalswert-Eingabe für die Stammdaten-Pflege.
 *
 * Die Art kommt ausschließlich aus der Plantyp-Deklaration
 * (tag/auswahl/text/zahl/datum/person, meherfach) — kein Plantyp-Spezialfall.
 * Ausgeliefert werden rohe JSON-Werte: true/false (tag), String, Zahl,
 * ISO-Datum, Person-Kennung bzw. Liste davon; leer wird zu null.
 */
import { computed } from 'vue'
// UXP-R23/P3-1b W3: gespeicherte Kennung („Maennerchor“) bleibt, angezeigt
// wird der Anzeigename aus `anzeigenamen` („Männerchor“).
import { auswahlOptionen } from './auswahlwerte.mjs'

const props = defineProps({
  merkmal: { type: Object, default: null },
  modelValue: { default: null },
  // Personen für merkmal.art 'person' ([{id, name, kuerzel}]).
  personen: { type: Array, default: () => [] },
  // Rollengefilterte Kandidaten (ST2): [{kennung, anzeige, kuerzel}]. Ist die
  // Liste gesetzt (nicht null), wird ausschließlich sie angeboten.
  kandidaten: { type: Array, default: null },
  kandidatenHinweis: { type: String, default: '' },
  kompakt: { type: Boolean, default: false },
  readonly: { type: Boolean, default: false },
})
const emit = defineEmits(['update:modelValue'])

const titel = computed(() => props.merkmal?.name || props.merkmal?.id || '')

const sortiertePersonen = computed(() => {
    const quelle = props.kandidaten != null
        ? props.kandidaten.map(k => ({ id: k.kennung ?? k.id, name: k.name || k.anzeige, kuerzel: k.kuerzel }))
        : (props.personen || [])
    return quelle.slice().sort((a, b) =>
        String(a?.name || a?.id || '').localeCompare(String(b?.name || b?.id || ''), 'de'))
})

const liste = computed(() => (Array.isArray(props.modelValue) ? props.modelValue : []))
const stringWert = computed(() =>
    (props.modelValue === null || props.modelValue === undefined) ? '' : String(props.modelValue))

function setze(wert) { emit('update:modelValue', wert) }

function tagSetzen(an) { setze(an ? true : false) }
function auswahlSetzen(roh) { setze(roh === '' ? null : roh) }
function personSetzen(roh) { setze(roh === '' ? null : roh) }
function textSetzen(roh) { setze(roh.trim() === '' ? null : roh) }
function datumSetzen(roh) { setze(roh === '' ? null : roh) }
function zahlSetzen(roh) { setze(roh === '' ? null : Number(roh)) }
function mehrfachToggle(wert, an) {
    const alt = liste.value.slice()
    const i = alt.indexOf(wert)
    if (an && i === -1) alt.push(wert)
    if (!an && i !== -1) alt.splice(i, 1)
    setze(alt)
}

defineExpose({ tagSetzen, auswahlSetzen, personSetzen, textSetzen, datumSetzen, zahlSetzen, mehrfachToggle })
</script>

<style scoped>
.mk-eingabe {
  width: 100%; padding: 8px 10px; border-radius: 8px;
  border: 1px solid var(--dk-border); background: var(--dk-surface);
  color: var(--dk-text); font-size: 0.86rem; font-family: inherit;
}
.mk-eingabe--kompakt { padding: 4px 6px; font-size: 0.8rem; }
.mk-eingabe:focus {
  outline: 2px solid color-mix(in oklch, var(--dk-brand-400) 50%, transparent);
  outline-offset: 0; border-color: var(--dk-brand-400);
}
.mk-tag { display: inline-flex; align-items: center; justify-content: center; cursor: pointer; min-height: 28px; }
.mk-tag input { margin: 0; cursor: pointer; }
.mk-tag--kompakt { min-height: 20px; }
.mk-mehrfach { display: flex; flex-wrap: wrap; gap: 4px 10px; }
.mk-mehrfach-wahl {
  display: inline-flex; align-items: center; gap: 4px;
  font-size: 0.78rem; color: var(--dk-text); cursor: pointer; white-space: nowrap;
}
.mk-mehrfach-wahl input { margin: 0; cursor: pointer; }
.mk-person { display: inline-flex; flex-direction: column; gap: 2px; width: 100%; }
.mk-hinweis { font-size: 0.72rem; color: var(--dk-text-subtle); }
</style>
