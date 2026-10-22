<template>
  <section v-if="hinweise.length" class="pr-erststart dk-card" aria-label="In drei Schritten zum Plan">
    <h2>In drei Schritten zum Plan</h2>
    <p>Es fehlen noch Angaben. Du kannst sie jetzt ergänzen oder später von Hand planen.</p>
    <ol class="pr-erststart-liste">
      <li :class="{ 'is-erledigt': schritt1Erledigt }">
        <span class="pr-erststart-marke" aria-hidden="true">{{ schritt1Erledigt ? '✔' : '1' }}</span>
        <div class="pr-erststart-inhalt">
          <strong>Wer kann was?<span v-if="schritt1Erledigt" class="pr-erststart-status"> — erledigt</span></strong>
          <ul v-if="hinweise.length"><li v-for="h in hinweise" :key="h">{{ h }}</li></ul>
          <!--
            ST1: 'Stammdaten öffnen' navigiert NICHT mehr weg (sonst ist der
            angefangene Plan verloren). Ist `panel` gesetzt, meldet der Klick
            stattdessen nach oben, damit dort das Seitenpanel über dem
            Dialog/der Seite aufgeht. Ohne `panel` bleibt der Link erhalten
            (Rückwärtskompatibilität, z. B. Plan.vue in älteren Aufrufen).
          -->
          <button
            v-if="panel" type="button" class="dk-btn dk-btn-secondary dk-btn-sm"
            data-test="pr-erststart-stammdaten-panel" @click="oeffnen"
          >Stammdaten öffnen</button>
          <a v-else class="dk-btn dk-btn-secondary dk-btn-sm" :href="stammdaten">Stammdaten öffnen</a>
        </div>
      </li>
      <li :class="{ 'is-erledigt': angelegt }">
        <span class="pr-erststart-marke" aria-hidden="true">{{ angelegt ? '✔' : '2' }}</span>
        <div class="pr-erststart-inhalt">
          <strong>{{ angelegt ? 'Plan erstellt' : 'Plan erstellen' }}<span v-if="angelegt" class="pr-erststart-status"> — erledigt</span></strong>
          <span> — Titel und Zeitraum angeben.</span>
        </div>
      </li>
      <li :class="{ 'is-erledigt': veroeffentlicht }">
        <span class="pr-erststart-marke" aria-hidden="true">{{ veroeffentlicht ? '✔' : '3' }}</span>
        <div class="pr-erststart-inhalt">
          <strong>Automatisch einteilen &amp; prüfen<span v-if="veroeffentlicht" class="pr-erststart-status"> — veröffentlicht</span></strong>
          <span> — Einteilung ansehen, bei Bedarf ändern und veröffentlichen.</span>
        </div>
      </li>
    </ol>
  </section>
</template>
<script setup>
import { computed } from 'vue'
import { bedarfHinweise, erststartSchritte } from './erststart.mjs'
const props = defineProps({ bedarf: { type: Array, default: () => [] }, definition: { type: Object, default: () => ({}) }, stammdaten: { type: String, default: '' }, angelegt: Boolean, veroeffentlicht: Boolean, panel: Boolean })
const emit = defineEmits(['stammdaten-oeffnen'])
const hinweise = computed(() => bedarfHinweise(props.bedarf, props.definition))
const schritte = computed(() => erststartSchritte({ hinweise: hinweise.value, angelegt: props.angelegt, veroeffentlicht: props.veroeffentlicht }))
const schritt1Erledigt = computed(() => schritte.value[0].erledigt)
function oeffnen() { emit('stammdaten-oeffnen') }
</script>
<style scoped>
.pr-erststart { padding: 16px; margin-bottom: 16px; font-size: .86rem; }
.pr-erststart h2 { font-size: 1rem; margin: 0 0 8px; }
.pr-erststart p { color: var(--dk-text-muted); }
.pr-erststart-liste { list-style: none; padding-left: 0; margin: 0; }
.pr-erststart-liste > li { display: flex; align-items: flex-start; gap: 10px; margin: 8px 0; }
.pr-erststart-marke {
  flex-shrink: 0; width: 24px; height: 24px; border-radius: 50%;
  display: inline-flex; align-items: center; justify-content: center;
  font-weight: 600; font-size: .8rem;
  background: color-mix(in oklch, var(--dk-brand-400) 14%, var(--dk-surface));
  color: var(--dk-brand-600, var(--dk-text)); border: 1px solid var(--dk-border);
}
.pr-erststart-liste > li.is-erledigt .pr-erststart-marke {
  background: color-mix(in oklch, var(--ok) 18%, var(--surface));
  color: var(--ok);
  border-color: color-mix(in oklch, var(--ok) 40%, var(--line));
}
.pr-erststart-inhalt { min-width: 0; }
.pr-erststart-status { color: var(--ok); font-weight: 500; }
.pr-erststart ul { padding-left: 18px; }
</style>
