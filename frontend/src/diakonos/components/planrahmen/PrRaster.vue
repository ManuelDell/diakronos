<template>
  <div class="pr-raster">
    <!-- OP-EVENT-18: Die geltende Variante (Sonne/Regen) wird je Tag gewählt —
         nicht global im Browser. Der aktive Knopf ist deutlich hervorgehoben. -->
    <p v-if="varianten.length" class="pr-raster-varianten-hinweis">Wetter je Tag</p>
    <table class="pr-raster-tabelle">
      <thead>
        <tr>
          <th class="pr-raster-termin">Tag</th>
          <th v-for="s in spalten" :key="s.id">{{ s.name }}</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="t in termine" :key="t.id" :class="{ 'pr-raster-entfaellt': t.entfaellt }">
          <td class="pr-raster-termin">
            <span class="pr-raster-datum">{{ datumText(t.datum) }}</span>
            <PrMeldungen v-if="meldungenZeigen" :meldungen="terminMeldungen(eintraege, t.id)" kompakt :bezeichnung="datumText(t.datum)" />
            <span v-if="t.uhrzeit" class="pr-raster-uhrzeit">{{ uhrzeitText(t.uhrzeit) }}</span>
            <span v-if="t.titel" class="pr-raster-titel">{{ t.titel }}</span>
            <span v-for="a in anlaesse(t)" :key="a" class="dk-badge dk-badge-brand">{{ anlassText(a) }}</span>
            <!-- OP-EVENT-18: Variantenschalter je Termin (nur Planer). -->
            <div v-if="varianten.length && bearbeitbar" class="pr-raster-varianten" role="group"
                 :aria-label="'Geltende Variante am ' + datumText(t.datum)">
              <button
                v-for="v in varianten" :key="v.id" type="button"
                class="dk-btn dk-btn-sm"
                :class="geltendeVariante(t) === v.id ? 'dk-btn-primary' : 'dk-btn-secondary'"
                :aria-pressed="geltendeVariante(t) === v.id ? 'true' : 'false'"
                @click="$emit('variante', t, v.id)"
              >{{ v.name || v.id }}</button>
            </div>
            <span v-else-if="varianten.length" class="pr-raster-variante-aktiv">
              {{ variantenName(geltendeVariante(t)) }}
            </span>
          </td>
          <td
            v-for="s in spalten"
            :key="s.id"
            class="pr-raster-zelle"
            @click="s.anlass ? null : $emit('bearbeiten', t, s.pfad)"
          >
            <template v-if="s.anlass">
              <span v-for="a in anlaesse(t)" :key="a" class="dk-badge dk-badge-brand">{{ anlassText(a) }}</span>
              <span v-if="!anlaesse(t).length" class="pr-raster-leer">–</span>
            </template>
            <template v-else>
              <div v-for="(z, zi) in zeilen(t, s)" :key="zi" class="pr-raster-zeile">
                <span v-if="s.feld?.art === 'gruppe'" class="pr-raster-name">{{ z.name }}</span>
                <span class="pr-raster-wert">
                  {{ z.text }}<span v-if="z.fixiert" class="pr-raster-pin" title="Von Hand festgelegt">📌</span>
                </span>
              </div>
              <span v-if="!zeilen(t, s).length" class="pr-raster-leer">–</span>
            </template>
          </td>
        </tr>
        <tr v-if="!termine.length">
          <td class="pr-raster-leer" :colspan="spalten.length + 1">
            Für diesen Zeitraum gibt es noch keine Termine.
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script setup>
/**
 * Generische Rasteransicht (Ansicht art 'raster'): Tag × Block mit Karten-
 * charakter. Zeilen sind Termine, Spalten die obersten Felder (Gruppen als
 * Block mit Unterfeldzeilen). Zellen öffnen die Bearbeitung.
 */
import { computed, ref } from 'vue'
import { datumText, uhrzeitText, reihenFelder, reihePraefix } from '../../composables/usePlanrahmen.js'
import { zellenInhalt } from './zellen.js'
import PrMeldungen from './PrMeldungen.vue'
import { terminMeldungen } from './meldungen.mjs'
import { anlassName, sichtbareAnlaesse } from './anlaesse.mjs'

const props = defineProps({
  plan: { type: Object, default: null },
  termine: { type: Array, default: () => [] },
  eintraege: { type: Array, default: () => [] },
  definitionen: { type: [Object, Map], default: () => ({}) },
  ansicht: { type: Object, default: () => ({}) },
  // UXP-R19: Regelmeldungen nur fuer Planer sichtbar.
  meldungenZeigen: { type: Boolean, default: false },
  // OP-EVENT-18: nur Planer dürfen die geltende Variante umschalten.
  bearbeitbar: { type: Boolean, default: false },
})
defineEmits(['bearbeiten', 'variante'])

const definitionen = computed(() =>
    props.definitionen instanceof Map ? props.definitionen : new Map(Object.entries(props.definitionen || {})))
const erstdefinition = computed(() => {
    for (const d of definitionen.value.values()) if (d) return d
    return null
})
const varianten = computed(() => {
    const map = new Map()
    function sammle(felder) {
        for (const f of felder || []) {
            for (const v of f.varianten || []) {
                const obj = typeof v === 'string' ? { id: v } : v
                map.set(obj.id, obj)
                sammle(obj.inhalt)
            }
            sammle(f.inhalt)
            for (const teil of f.teile || []) sammle(teil.inhalt)
        }
    }
    for (const d of definitionen.value.values()) for (const r of reihenFelder(d)) sammle(r.felder)
    return [...map.values()]
})

/** OP-EVENT-18: die je Termin geltende Variante (leer = erste deklarierte). */
function geltendeVariante(t) {
    return t?.variante || varianten.value[0]?.id || ''
}
/** Anzeigename einer Variante (Definition, sonst Kennung). */
function variantenName(id) {
    return varianten.value.find((v) => v.id === id)?.name || id || ''
}

const alleFelder = computed(() => {
    const result = []
    for (const r of reihenFelder(erstdefinition.value)) {
        const präfix = reihePraefix(r.id)
        for (const f of r.felder) result.push({ ...f, pfad: präfix + f.id })
    }
    return result
})

const spalten = computed(() => {
    const deklariert = Array.isArray(props.ansicht?.spalten) ? props.ansicht.spalten : []
    const liste = deklariert.length
        ? deklariert.map((id) => ({ id, pfad: id }))
        : alleFelder.value.map((f) => ({ id: f.pfad, pfad: f.pfad }))
    return liste.map((s) => {
        const feld = alleFelder.value.find((f) => f.pfad === s.pfad) || null
        return {
            ...s,
            anlass: !feld && s.id === 'anlass',
            name: feld?.name || (s.id === 'anlass' ? 'Anlass' : s.pfad.split(':').pop()),
            feld,
            format: props.ansicht?.format?.[s.id] || props.ansicht?.format?.[s.pfad] || '',
        }
    })
})

/** UXP-R22: ohne Sammelanlass „feiertag“ und ohne Doppelungen. */
function anlaesse(t) { return sichtbareAnlaesse(t.anlaesse) }
/** UXP-R22: Katalognamen statt interner Kennungen (Auflösung in anlaesse.mjs). */
function anlassText(a) { return anlassName(a, erstdefinition.value?.anlaesse) }

function zeilen(t, s) {
    if (s.anlass || !s.feld) return []
    // OP-EVENT-18: es gilt die am Termin festgelegte Variante (leer = erste).
    const aktiv = geltendeVariante(t)
    const eintraege = props.eintraege.filter(e => {
        const variante = e.feld_pfad.match(/@([^#.\[/]+)/)?.[1]
        return !variante || variante === aktiv
    })
    const feld = reihenFelder(definitionen.value.get(t.plantyp_version))
        .flatMap(r => r.felder.map(f => ({ ...f, pfad: reihePraefix(r.id) + f.id })))
        .find(f => f.pfad === s.pfad)
    return feld ? zellenInhalt({ eintraege, plan: props.plan, termin: t, feld, format: s.format }) : []
}
</script>

<style scoped>
.pr-raster { overflow-x: auto; border: 1px solid var(--dk-border); border-radius: 12px; background: var(--dk-surface); }
.pr-raster-varianten { display: flex; gap: 6px; flex-wrap: wrap; margin-top: 6px; }
.pr-raster-varianten-hinweis { margin: 8px 10px 0; font-size: 0.74rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em; color: var(--dk-text-muted); }
.pr-raster-variante-aktiv { display: inline-block; margin-top: 4px; font-size: 0.76rem; color: var(--dk-text-muted); }
@media print { .pr-raster-varianten { display: none; } .pr-raster-varianten-hinweis { display: none; } }
.pr-raster-tabelle { width: 100%; border-collapse: separate; border-spacing: 0; font-size: 0.84rem; }
.pr-raster-tabelle th, .pr-raster-tabelle td { padding: 10px 14px; text-align: left; vertical-align: top; }
.pr-raster-tabelle thead th {
  background: var(--dk-surface-2); color: var(--dk-text-muted);
  font-size: 0.72rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em;
  border-bottom: 1px solid var(--dk-border); white-space: nowrap;
}
.pr-raster-tabelle tbody tr > * { border-top: 1px solid var(--dk-divider); }
.pr-raster-tabelle tbody tr:hover { background: var(--dk-surface-hover); }
.pr-raster-termin { min-width: 160px; position: sticky; left: 0; background: var(--dk-surface); z-index: 1; }
.pr-raster-tabelle tbody tr:hover .pr-raster-termin { background: var(--dk-surface-hover); }
.pr-raster-datum { display: block; font-weight: 600; color: var(--dk-text); }
.pr-raster-uhrzeit { display: block; font-size: 0.74rem; color: var(--dk-text-muted); }
.pr-raster-titel { display: block; font-size: 0.76rem; color: var(--dk-text-muted); }
.pr-raster-termin .dk-badge { margin-top: 4px; margin-right: 4px; }
.pr-raster-zelle { cursor: pointer; min-width: 170px; border-left: 1px solid var(--dk-divider); }
.pr-raster-zelle:hover { background: color-mix(in oklch, var(--dk-brand-400) 6%, var(--dk-surface)); }
.pr-raster-zeile { display: flex; gap: 6px; align-items: baseline; }
.pr-raster-zeile + .pr-raster-zeile { margin-top: 4px; }
.pr-raster-name { flex-shrink: 0; font-size: 0.72rem; color: var(--dk-text-subtle); min-width: 68px; }
.pr-raster-wert { color: var(--dk-text); }
.pr-raster-pin { margin-left: 4px; font-size: 0.72rem; }
.pr-raster-meldung { font-size: 0.72rem; cursor: help; }
.pr-raster-leer { color: var(--dk-text-subtle); }
.pr-raster-entfaellt { opacity: 0.55; }
.pr-raster-entfaellt .pr-raster-datum { text-decoration: line-through; }
</style>
