<template>
  <details v-if="kompakt && meldungen.length" class="pr-meldungen-termin">
    <summary
      :class="{ 'pr-meldung--fehler': gruppiert.anzahl.fehler }"
      :aria-label="kompaktName"
    >{{ gruppiert.anzahl.fehler ? '⛔' : '⚠️' }} {{ meldungen.length }}<span class="pr-meldungen-sr"> {{ kompaktName }}</span></summary>
    <PrMeldungen :meldungen="meldungen" />
  </details>
  <details v-else-if="zusammenfassung && meldungen.length" class="pr-meldungen-uebersicht">
    <summary class="pr-meldungen-kopf">
      <span class="pr-meldungen-pfeil" aria-hidden="true">▸</span>
      <span class="pr-meldungen-titel">{{ titel }}: {{ gruppiert.anzahl.fehler }} Fehler · {{ gruppiert.anzahl.warnung }} {{ gruppiert.anzahl.warnung === 1 ? 'Warnung' : 'Warnungen' }} · {{ gruppiert.anzahl.hinweis }} {{ gruppiert.anzahl.hinweis === 1 ? 'Hinweis' : 'Hinweise' }}</span>
      <span class="dk-btn dk-btn-secondary dk-btn-sm pr-meldungen-anzeigen">Anzeigen</span>
    </summary>
    <details v-for="g in gruppiert.gruppen" :key="g.key" class="pr-meldungen-gruppe">
      <summary><span class="pr-meldungen-pfeil" aria-hidden="true">▸</span>{{ regelTitel(g.regel, g.meldungen.length, ersteDefinition) }} · Anzeigen</summary>
      <PrMeldungen :meldungen="g.meldungen" />
    </details>
  </details>
  <div v-else-if="meldungen.length" class="pr-meldungen" :class="'pr-meldungen--' + (kompakt ? 'kompakt' : 'normal')">
    <div
      v-for="(m, i) in meldungen"
      :key="i"
      class="pr-meldung"
      :class="'pr-meldung--' + ({ muss: 'fehler', sollte: 'warnung' }[m.stufe] || m.stufe || 'fehler')"
    >
      <span class="pr-meldung-piktogramm" aria-hidden="true">{{ piktogramm(m.stufe) }}</span>
      <span class="pr-meldung-text">
        <span class="pr-meldung-meldung">{{ klartext(m) }}</span>
        <span v-if="m.hinweis" class="pr-meldung-hinweis"> {{ klartext({ ...m, meldung: m.hinweis, code: '' }) }}</span>
        <!-- UXP-R24: Der Pfad-Kontext („· /zeitraum“) erscheint nur, wenn er sich
             in einen lesbaren Feldnamen auflöst. Rohe Pfade sind Fachjargon. -->
        <span v-if="kontext(m) && kontext(m) !== pfadRoh(m)" class="pr-meldung-pfad"> · {{ kontext(m) }}</span>
      </span>
    </div>
  </div>
</template>

<script setup>
import { computed, inject } from 'vue'
import { feldBeschriftung, regelTitel, meldungsKurz } from './klartext.mjs'
import { meldungsGruppen } from './meldungen.mjs'
import { stufeSprache } from '../ui/statussprache.mjs'
/**
 * Strukturierte Plan-Rahmen-Meldungen (fehler/warnung/hinweis) in Freundesmund.
 * Quelle: meldungen der Prüf-Endpunkte (HTTP 417 oder plantyp_pruefen).
 */
const props = defineProps({
  /* DES-R20: Im Plan standen 40 gleichlautende „⚠️ N Meldungen anzeigen“ —
     fuer Tastatur und Vorleser nicht unterscheidbar. Die aufrufende Stelle
     nennt deshalb das Datum bzw. den betroffenen Termin. */
  bezeichnung: { type: String, default: '' },
  meldungen: { type: Array, default: () => [] },
  kompakt: { type: Boolean, default: false },
  titel: { type: String, default: 'Regelprüfung' },
  zusammenfassung: { type: Boolean, default: false },
})
const anzeige = inject('planrahmenAnzeige', null)
const ersteDefinition = computed(() => anzeige?.value?.definitionen?.values().next().value || {})

/** DES-R20: unterscheidbarer Name der kompakten Zeile. */
const kompaktName = computed(() =>
  props.bezeichnung ? `Meldungen zu ${props.bezeichnung} anzeigen` : 'Meldungen anzeigen',
)
function klartext(m) {
  const t = anzeige?.value?.termine?.find(t => t.id === (m.termin || m.bewertung?.termin))
  const def = anzeige?.value?.definitionen?.get(t?.plantyp_version) || ersteDefinition.value
  return meldungsKurz(m, def, t, anzeige?.value?.anzeige)
}
function kontext(m) {
  const t = anzeige?.value?.termine?.find(t => t.id === (m.termin || m.bewertung?.termin))
  const pfad = m.feld_pfad || m.bewertung?.feld_pfad || m.pfad
  // UXP-R24 (d): ohne Plan-Kontext (z. B. „Neuer Plan“) gibt es keine
  // Feldbeschriftung — dann KEINEN rohen Pfad („· /zeitraum“) anhängen, der
  // Maschinenjargon wäre. Die Meldung selbst nennt das Feld bereits.
  if (!anzeige?.value || !pfad) return ''
  return feldBeschriftung(pfad, anzeige.value.definitionen.get(t?.plantyp_version), t)
}
/** Der rohe Pfad — nur zum Vergleich, damit er nie als Kontext erscheint. */
function pfadRoh(m) {
  return m.feld_pfad || m.bewertung?.feld_pfad || m.pfad
}
const gruppiert = computed(() => meldungsGruppen(props.meldungen))

function piktogramm(stufe) {
  return stufeSprache(stufe).piktogramm
}
</script>

<style scoped>
.pr-meldungen-termin { font-size: .76rem; margin-top: 4px; }
.pr-meldungen-termin > summary { cursor: pointer; color: var(--dk-text-muted); width: fit-content; }
.pr-meldungen-sr { position: absolute; width: 1px; height: 1px; overflow: hidden; clip-path: inset(50%); }
.pr-meldungen-uebersicht { border: 1px solid var(--dk-border); border-radius: 8px; padding: 8px 10px; font-size: .82rem; background: var(--dk-surface-2); }
.pr-meldungen-uebersicht summary { cursor: pointer; }
.pr-meldungen-kopf { display: flex; align-items: center; gap: 8px; }
.pr-meldungen-kopf .pr-meldungen-titel { flex: 1; min-width: 0; }
.pr-meldungen-anzeigen { flex-shrink: 0; }
.pr-meldungen-pfeil { display: inline-block; transition: transform 120ms ease; }
details[open] > summary .pr-meldungen-pfeil { transform: rotate(90deg); }
.pr-meldungen-gruppe { margin-top: 8px; }
.pr-meldungen-gruppe > summary { margin-bottom: 6px; display: flex; align-items: center; gap: 6px; }
.pr-meldungen { display: flex; flex-direction: column; gap: 6px; }
.pr-meldung {
  display: flex; align-items: flex-start; gap: 8px;
  padding: 8px 10px; border-radius: 8px;
  border: 1px solid var(--dk-border); background: var(--dk-surface-2);
  font-size: 0.82rem; line-height: 1.4;
}
.pr-meldung--fehler {
  border-color: color-mix(in oklch, var(--dk-danger) 30%, var(--dk-surface));
  background: color-mix(in oklch, var(--dk-danger) 6%, var(--dk-surface));
  color: var(--dk-danger);
}
.pr-meldung--warnung {
  border-color: color-mix(in oklch, var(--dk-warning) 35%, var(--dk-surface));
  background: color-mix(in oklch, var(--dk-warning) 8%, var(--dk-surface));
  color: var(--dk-warning);
}
.pr-meldung--hinweis { color: var(--dk-text-muted); }
.pr-meldung-piktogramm { flex-shrink: 0; }
.pr-meldung-text { flex: 1; min-width: 0; color: var(--dk-text); }
.pr-meldung--fehler .pr-meldung-meldung { color: var(--dk-danger); font-weight: 600; }
.pr-meldung--warnung .pr-meldung-meldung { color: var(--dk-warning); font-weight: 600; }
.pr-meldung-hinweis { color: var(--dk-text-muted); }
.pr-meldung-pfad { color: var(--dk-text-subtle); font-size: 0.74rem; font-family: monospace; }
.pr-meldungen--kompakt .pr-meldung { padding: 5px 8px; font-size: 0.76rem; }
</style>
