<template>
  <!-- CHAT-12b: die Anhänge, die auf das Senden warten — EINE Chip-Zeile über
       dem Eingabefeld (Karte Punkt 2). Je Datei: Name, Größe, Stand
       (lädt / bereit / ging nicht mit Begründung) und ein Entfernen-Knopf.

       Der Entfernen-Knopf nimmt den Eintrag NUR aus dieser Liste — der Server
       räumt nicht gesendete Anhänge selbst auf (`chat_anhaenge_aufraeumen`,
       24 h), ein eigener Löschaufruf wäre ein zweiter Weg.

       Am Handy stehen die Chips untereinander (`flex-wrap`), damit ein langer
       Dateiname nichts abschneidet; jedes Bedienelement ist 44 px hoch. -->
  <div v-if="liste.length" class="dk-chat-anhaenge" role="group" aria-label="Anhänge zu dieser Nachricht">
    <span class="dk-chat-nur-vorlesen" aria-live="polite">{{ ansage }}</span>
    <div
      v-for="c in liste"
      :key="c.schluessel"
      class="dk-chat-anhang-chip"
      :class="`is-${c.stand}`"
    >
      <span class="dk-chat-anhang-chip-symbol" aria-hidden="true">
        <DkSymbol :name="c.stand === 'laedt' ? 'uhr' : 'notiz'" :groesse="16" />
      </span>
      <span class="dk-chat-anhang-chip-text">
        <span class="dk-chat-anhang-chip-name" :title="c.dateiname">{{ c.dateiname }}</span>
        <span class="dk-chat-anhang-chip-meta">
          <span>{{ groesseText(c.groesse) }}</span>
          <span v-if="c.stand === 'laedt'" class="dk-chat-anhang-chip-stand">{{ TEXTE.laedt }}</span>
          <span v-else-if="c.stand === 'fertig'" class="dk-chat-anhang-chip-stand">{{ TEXTE.fertig }}</span>
          <span v-else class="dk-chat-anhang-chip-stand is-fehler">{{ TEXTE.fehler }}</span>
        </span>
        <!-- Der Fehlertext steht als SATZ da (Server-Meldung bzw. der feste
             ­Satz bei 429) — nicht als Symbol ohne Auskunft. -->
        <span v-if="c.stand === 'fehler' && c.fehler" class="dk-chat-anhang-chip-fehler">{{ c.fehler }}</span>
      </span>
      <DkButton
        variant="ghost"
        size="sm"
        class="dk-chat-anhang-chip-weg"
        :aria-label="`${TEXTE.entfernen}: ${c.dateiname}`"
        :title="TEXTE.entfernen"
        @click="$emit('entfernen', c)"
      ><template #icon><span aria-hidden="true">×</span></template></DkButton>
    </div>
  </div>
</template>

<script setup>
/**
 * ChatAnhangChips — die offenen Anhänge über der Eingabezeile (CHAT-12b).
 *
 * Der Baustein ZEICHNET nur. Was in der Liste steht und was ein Entfernen
 * bedeutet, entscheidet die Seite (`pages/Nachrichten.vue`) mit den Regeln aus
 * `anhaenge.mjs`.
 *
 * Barrierefreiheit (Karte Punkt 4): der Entfernen-Knopf trägt ein `aria-label`
 * mit dem Dateinamen („Anhang entfernen: probe.pdf“), damit am Handy ohne
 * Hover klar ist, welcher Chip gemeint ist; die Stand-Ansage läuft über eine
 * höfliche Live-Region (`aria-live="polite"`), nicht über einen Alarm.
 */
import { computed } from 'vue'
import DkButton from '../ui/DkButton.vue'
import DkSymbol from '../ui/DkSymbol.vue'
import { TEXTE, groesseText } from './anhaenge.mjs'

const props = defineProps({
  /** Die offenen Anhänge (Einträge aus `chipBauen`). */
  liste: { type: Array, default: () => [] },
})
defineEmits(['entfernen'])

/** Kurze Ansage für Vorleser: „2 Anhänge bereit, 1 wird geladen“. */
const ansage = computed(() => {
  const alle = props.liste || []
  const fertig = alle.filter((c) => c.stand === 'fertig').length
  const laedt = alle.filter((c) => c.stand === 'laedt').length
  const fehler = alle.filter((c) => c.stand === 'fehler').length
  const teile = []
  if (fertig) teile.push(`${fertig} ${fertig === 1 ? 'Anhang' : 'Anhänge'} bereit`)
  if (laedt) teile.push(`${laedt} wird geladen`)
  if (fehler) teile.push(`${fehler} nicht hochgeladen`)
  return teile.join(', ')
})
</script>

<style scoped>
.dk-chat-anhaenge {
  display: flex;
  flex-wrap: wrap;
  gap: var(--sp-2);
  margin-bottom: var(--sp-2);
}
.dk-chat-anhang-chip {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  min-height: var(--treffer-handy);
  max-width: 100%;
  padding: var(--sp-1) var(--sp-2);
  border: var(--rahmen-breite) solid var(--line);
  border-radius: var(--radius);
  background: var(--surface-2);
  color: var(--text);
}
/* Fehler: rot nur der Stand — der Rahmen bleibt ruhig (eine Auskunft, kein
   Alarm). */
.dk-chat-anhang-chip.is-fehler { border-color: var(--err); }
.dk-chat-anhang-chip-symbol { display: flex; color: var(--muted); flex: none; }
.dk-chat-anhang-chip-text {
  display: flex;
  flex-direction: column;
  min-width: 0;
  gap: var(--sp-1);
}
.dk-chat-anhang-chip-name {
  font-size: var(--fs-14);
  font-weight: var(--fw-mittel);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.dk-chat-anhang-chip-meta {
  display: flex;
  gap: var(--sp-2);
  font-size: var(--fs-12);
  color: var(--muted);
}
.dk-chat-anhang-chip-fehler { font-size: var(--fs-12); color: var(--err); }
.dk-chat-anhang-chip-weg { flex: none; }
.dk-chat-nur-vorlesen {
  position: absolute;
  width: var(--rahmen-breite);
  height: var(--rahmen-breite);
  margin: calc(var(--rahmen-breite) * -1);
  padding: 0;
  overflow: hidden;
  clip-path: inset(50%);
  white-space: nowrap;
  border: 0;
}
</style>
