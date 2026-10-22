<template>
  <div class="pr-diff">
    <p class="pr-diff-zusammenfassung" role="status">
      {{ zusammenfassung }}<span v-if="vorschlag">; 0 von Hand festgelegte Werte werden überschrieben</span>.
    </p>
    <div v-if="!gruppen.length" class="pr-diff-leer">Keine Wertänderungen.</div>
    <details v-for="g in gruppen" :key="g.id" class="pr-diff-gruppe">
      <summary>
        {{ datumText(g.datum) }}<template v-if="g.titel"> · {{ g.titel }}</template> · {{ zahlWort(g.zeilen.length, 'Änderung', 'Änderungen') }}
      </summary>
      <ul class="pr-diff-liste">
        <li v-for="(z, i) in g.zeilen" :key="i" class="pr-diff-zeile">
          <span class="pr-diff-feld">{{ z.feld }}:</span>
          <span class="pr-diff-werte">
            <span class="pr-diff-alt" :class="{ 'pr-diff-leerwert': z.vorher === '(leer)' }" :title="z.vorher === '(leer)' ? 'Noch kein Wert eingetragen' : ''">{{ z.vorher }}</span>
            <span class="pr-diff-pfeil" aria-hidden="true">→</span>
            <span class="pr-diff-neu" :class="{ 'pr-diff-leerwert': z.nachher === '(leer)' }" :title="z.nachher === '(leer)' ? 'Noch kein Wert eingetragen' : ''">{{ z.nachher }}</span>
          </span>
        </li>
      </ul>
    </details>
  </div>
</template>

<script setup>
/**
 * Wert-Diff (Generator-Vorschau, Veröffentlichung) mit freundlicher Anzeige:
 * Termin, Feldname und Werte vorher → nachher.
 */
import { computed } from 'vue'
import { datumText } from '../../composables/usePlanrahmen.js'
import { diffGruppen } from './klartext.mjs'
import { zahlWort } from './format.mjs'

const props = defineProps({
  diff: { type: Array, default: () => [] },
  termine: { type: Array, default: () => [] },   // Plan-Termine (id, datum)
  definitionen: { type: [Object, Map], default: () => ({}) },
  anzeige: { type: Object, default: () => ({}) },
  vorschlag: { type: Boolean, default: false },
})

const gruppen = computed(() => diffGruppen(props.diff, props.termine, props.definitionen, props.anzeige))

/** OP-CHOR-12: „1 Änderung für 1 Termin“ statt „1 Änderungen für 1 Termine“. */
const zusammenfassung = computed(() => {
    const aenderungen = zahlWort(
        props.diff.length,
        props.vorschlag ? 'Vorschlag' : 'Änderung',
        props.vorschlag ? 'Vorschläge' : 'Änderungen',
    )
    return `${aenderungen} für ${zahlWort(gruppen.value.length, 'Termin', 'Termine')}`
})

// Regelmeldungen kommen separat aus den Prüfantworten, nicht aus Wert-Diffs.
</script>

<style scoped>
.pr-diff-zusammenfassung { font-size: .86rem; line-height: 1.5; }
.pr-diff-gruppe { padding: 10px 0; border-bottom: 1px solid var(--dk-border); }
.pr-diff-gruppe summary { cursor: pointer; font-weight: 600; font-size: .84rem; }
.pr-diff-liste { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; }
.pr-diff-zeile {
  display: flex; align-items: baseline; gap: 10px; flex-wrap: wrap;
  padding: 7px 0; border-bottom: 1px solid var(--dk-divider);
  font-size: 0.82rem;
}
.pr-diff-zeile:last-child { border-bottom: none; }
.pr-diff-datum { flex-shrink: 0; min-width: 96px; color: var(--dk-text-muted); font-size: 0.76rem; }
.pr-diff-feld { flex-shrink: 0; min-width: 110px; font-weight: 600; color: var(--dk-text); }
.pr-diff-werte { display: inline-flex; align-items: baseline; gap: 6px; flex-wrap: wrap; min-width: 0; }
.pr-diff-alt { color: var(--dk-text-muted); text-decoration: line-through; text-decoration-color: color-mix(in oklch, var(--dk-danger) 50%, transparent); }
.pr-diff-neu { color: var(--dk-success); font-weight: 500; }
.pr-diff-pfeil { color: var(--dk-text-subtle); }
.pr-diff-leerwert { font-style: italic; }
.pr-diff-leer { font-size: 0.82rem; color: var(--dk-text-muted); }
.pr-diff-mehr { margin-top: 8px; font-size: 0.76rem; color: var(--dk-text-subtle); }
</style>
