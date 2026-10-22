<template>
  <div class="pr-re">
    <!-- Kurzform: eine Zeitachse, Felder ohne Präfix -->
    <template v-if="!reihen.length">
      <PrTermineEditor :termine="sicherTermine()" :reihen-ids="['standard']" :kontext="kontext" :meldungen="meldungen" basis-pfad="termine" />
      <h4 class="pr-re-titel">Felder pro Termin</h4>
      <PrFelderEditor :felder="sicherFelder()" :kontext="kontext" :meldungen="meldungen" basis-pfad="felder/" />
      <button type="button" class="dk-btn dk-btn-secondary dk-btn-sm" @click="zuReihenWechseln">+ Zweite Terminreihe (z. B. Probe am Freitag)</button>
    </template>

    <!-- Mehrere Reihen: jede mit eigener Zeitachse und eigenen Feldern -->
    <template v-else>
      <div v-for="(reihe, ri) in reihen" :key="ri" class="pr-re-reihe">
        <div class="pr-re-kopf">
          <input v-model="reihe.id" type="text" class="dk-form-input pr-re-id" placeholder="gottesdienst" aria-label="Kennung der Reihe" />
          <input v-model="reihe.name" type="text" class="dk-form-input" placeholder="Anzeigename (optional)" aria-label="Anzeigename" />
          <span v-if="reihe.termine?.abgeleitet" class="dk-badge dk-badge-brand">abgeleitet</span>
          <PrPfadMeldungen :meldungen="meldungen" :pfad="'terminreihen/' + ri + '/id'" />
          <PrPfadMeldungen :meldungen="meldungen" :pfad="'terminreihen/' + ri + '/name'" />
          <button
            v-if="reihen.length > 1" type="button" class="dk-btn dk-btn-ghost dk-btn-sm"
            aria-label="Terminreihe entfernen" @click="reiheLoeschen(ri)"
          >✕</button>
        </div>
        <PrTermineEditor :termine="sicherReihenTermine(reihe)" :reihen-ids="reihenIds" :kontext="kontext" :meldungen="meldungen" :basis-pfad="'terminreihen/' + ri + '/termine'" />
        <h5 class="pr-re-unter-titel">Felder dieser Reihe<span v-if="reihe.id"> — Pfade beginnen mit „{{ reihe.id }}:“</span></h5>
        <PrFelderEditor
          :felder="sicherReihenFelder(reihe)" :kontext="kontext"
          :meldungen="meldungen" :basis-pfad="'terminreihen/' + ri + '/felder/'"
        />
      </div>
      <div class="pr-re-knopfzeile">
        <button type="button" class="dk-btn dk-btn-secondary dk-btn-sm" @click="reiheHinzufuegen(false)">+ Eigene Terminreihe</button>
        <button type="button" class="dk-btn dk-btn-secondary dk-btn-sm" @click="reiheHinzufuegen(true)">+ Abgeleitete Terminreihe (z. B. Probe vor dem Gottesdienst)</button>
        <button type="button" class="dk-btn dk-btn-ghost dk-btn-sm" @click="zurKurzform">Zur einfachen Form zurück (nur eine Reihe)</button>
      </div>
    </template>
  </div>
</template>

<script setup>
/**
 * Termine + Felder einer Plantyp-Definition: Kurzform (termine/felder auf
 * oberster Ebene) oder mehrere Terminreihen mit eigener Zeitachse, inklusive
 * abgeleiteter Reihen. Die Umstellung ist verlustfrei — bestehende Werte
 * wandern in die erste Reihe.
 */
import { computed } from 'vue'
import PrTermineEditor from './PrTermineEditor.vue'
import PrFelderEditor from './PrFelderEditor.vue'
import PrPfadMeldungen from './PrPfadMeldungen.vue'

const props = defineProps({
  definition: { type: Object, required: true },
  kontext: { type: Object, default: () => ({}) },
  meldungen: { type: Array, default: () => [] },
})

const reihen = computed(() => (Array.isArray(props.definition.terminreihen) ? props.definition.terminreihen : []))
const reihenIds = computed(() => ['standard', ...reihen.value.map((r) => r.id).filter(Boolean)])

function sicherTermine() {
  if (!props.definition.termine || typeof props.definition.termine !== 'object') props.definition.termine = {}
  return props.definition.termine
}
function sicherFelder() {
  if (!Array.isArray(props.definition.felder)) props.definition.felder = []
  return props.definition.felder
}
function sicherReihenTermine(reihe) {
  if (!reihe.termine || typeof reihe.termine !== 'object') reihe.termine = {}
  return reihe.termine
}
function sicherReihenFelder(reihe) {
  if (!Array.isArray(reihe.felder)) reihe.felder = []
  return reihe.felder
}

function zuReihenWechseln() {
  const quelle = { termine: sicherTermine(), felder: sicherFelder() }
  props.definition.terminreihen = [{ id: 'standard', name: 'Hauptreihe', ...quelle }]
  delete props.definition.termine
  delete props.definition.felder
}

function reiheHinzufuegen(abgeleitet) {
  if (!Array.isArray(props.definition.terminreihen)) props.definition.terminreihen = []
  const neu = { id: '', name: '', termine: {}, felder: [] }
  if (abgeleitet) {
    const ziel = reihenIds.value.find((id) => id) || 'standard'
    neu.termine = { abgeleitet: { von: ziel, versatz: '-2T' } }
    neu.name = 'Probe'
  }
  props.definition.terminreihen.push(neu)
}

function reiheLoeschen(ri) { reihen.value.splice(ri, 1) }

function zurKurzform() {
  if (reihen.value.length !== 1) return
  const r = reihen.value[0]
  props.definition.termine = r.termine || {}
  props.definition.felder = r.felder || []
  delete props.definition.terminreihen
}
</script>

<style scoped>
.pr-re { display: flex; flex-direction: column; gap: 14px; }
.pr-re-titel { font-size: 0.76rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: var(--dk-text-muted); margin: 6px 0 0; }
.pr-re-reihe { border: 1px solid var(--dk-border); border-radius: 12px; background: var(--dk-surface); padding: 12px; display: flex; flex-direction: column; gap: 10px; }
.pr-re-kopf { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.pr-re-id { max-width: 180px; font-family: ui-monospace, monospace; }
.pr-re-unter-titel { font-size: 0.74rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: var(--dk-text-muted); margin: 4px 0 0; }
.pr-re-knopfzeile { display: flex; gap: 8px; flex-wrap: wrap; }
</style>
