<template>
  <!-- ON-4 (H3, Entwurf 12): freundlicher Leerzustand der Mitgliederliste.
       Zwei VORHANDENE Wege: „CSV importieren“ (Import-Reiter) und „Mitglied
       anlegen“ (der Dialog „Mitglied hinzufügen“ der Liste — diese Komponente
       öffnet ihn nur per Ereignis, sie baut keine zweite Maske). -->
  <div class="dk-ui-empty dk-ui-empty--freundlich">
    <div class="dk-ui-empty-icon" aria-hidden="true">{{ symbols }}</div>
    <p class="dk-ui-empty-title">{{ titel }}</p>
    <p v-if="text" class="dk-ui-empty-text">{{ text }}</p>
    <div v-if="zeigeImport || zeigeAnlegen" class="dk-ui-empty-aktion">
      <a v-if="zeigeImport" :href="IMPORT_ROUTE" class="dk-ui-empty-knopf dk-ui-empty-knopf--sekundaer">
        {{ texte.csvImportieren }}
      </a>
      <button
        v-if="zeigeAnlegen"
        type="button"
        class="dk-ui-empty-knopf dk-ui-empty-knopf--primar"
        @click="$emit('anlegen')"
      >
        {{ texte.mitgliederAnlegen }}
      </button>
    </div>
    <p v-if="fuss" class="dk-ui-empty-fuss">{{ fuss }}</p>
  </div>
</template>

<script setup>
/**
 * MitgliederLeerzustand — Leerzustand der Mitgliederliste (ON-4/H3).
 *
 * Die Komponente entscheidet NICHTS: `zustand` kommt aus
 * `mitgliederLeerzustand(...)` (`composables/einrichtungsHinweise.mjs`) und
 * unterscheidet „wirklich niemand da“ (Frame 12) von „Suche/Filter greift“.
 * Nur so kann die Suche nie fälschlich „Noch keine Mitglieder“ behaupten.
 *
 * Nur Tokens (`var(--…)`) — keine Farb-, Schrift- oder Radius-Zahlen.
 */
import { computed } from 'vue'

import { IMPORT_ROUTE, TEXTE } from '../../composables/einrichtungsHinweise.mjs'

const props = defineProps({
  zustand: { type: Object, required: true },
  symbol: { type: String, default: '👤' },
})

defineEmits(['anlegen'])

const texte = TEXTE
const titel = computed(() => props.zustand?.titel || '')
const text = computed(() => props.zustand?.text || '')
const fuss = computed(() => props.zustand?.fuss || '')
const zeigeImport = computed(() => props.zustand?.zeigeImport === true)
const zeigeAnlegen = computed(() => props.zustand?.zeigeAnlegen === true)
const symbols = computed(() => props.symbol)
</script>

<style scoped>
.dk-ui-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  gap: var(--sp-2);
  padding: var(--sp-8) var(--sp-6);
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
}
.dk-ui-empty-icon {
  width: calc(var(--sp-8) + var(--sp-8) + var(--sp-2));
  height: calc(var(--sp-8) + var(--sp-8) + var(--sp-2));
  display: grid;
  place-items: center;
  border-radius: 50%;
  background: var(--surface-2);
  color: var(--subtle);
  font-size: var(--fs-h3);
}
.dk-ui-empty-title { margin: var(--sp-2) 0 0; font-size: var(--fs-h3); font-weight: var(--fw-h); color: var(--text); }
.dk-ui-empty-text { margin: 0; max-width: 46ch; font-size: var(--fs); color: var(--muted); line-height: 1.55; }
.dk-ui-empty-aktion {
  display: flex;
  flex-wrap: wrap;
  gap: var(--sp-2);
  justify-content: center;
  margin-top: var(--sp-3);
}
.dk-ui-empty-knopf {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  height: var(--control-h);
  padding: 0 var(--sp-4);
  border-radius: var(--radius);
  border: 1px solid transparent;
  font: inherit;
  font-size: var(--fs);
  font-weight: 550;
  text-decoration: none;
  cursor: pointer;
}
.dk-ui-empty-knopf--primar { background: var(--primary); color: var(--primary-ink); border-color: var(--primary); }
.dk-ui-empty-knopf--sekundaer { background: var(--surface); color: var(--text); border-color: var(--line-strong); }
.dk-ui-empty-knopf--sekundaer:hover { background: var(--surface-2); }
.dk-ui-empty-knopf:focus-visible { outline: 2px solid var(--focus-ring); outline-offset: 2px; }
.dk-ui-empty-fuss { margin: var(--sp-3) 0 0; font-size: var(--fs-xs); color: var(--subtle); }
</style>
