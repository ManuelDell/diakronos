<template>
  <!-- UX-C3b: ⓘ am Feld. Der Text kommt AUS DEM GLOSSAR (abschnitte.mjs) —
       dieselbe Quelle wie die Erklärspalte, keine zweite Wahrheit. Erscheint
       beim Überfahren UND bei Tastaturfokus (aria-describedby), damit der
       Hinweis nicht nur mit der Maus erreichbar ist. -->
  <span class="pr-info">
    <button
      type="button"
      class="pr-info-knopf"
      :aria-label="'Erklärung: ' + (begriff || id)"
      :aria-describedby="hilfeId"
      :aria-expanded="offen ? 'true' : 'false'"
      @click="umschalten"
      @keydown.escape="offen = false"
    >i</button>
    <span
      :id="hilfeId"
      class="pr-info-text"
      :class="{ 'is-offen': offen }"
      role="tooltip"
    >
      <strong v-if="begriff">{{ begriff }}:</strong> {{ text }}
      <span v-if="quelle" class="pr-info-quelle">{{ quelle }}</span>
    </span>
  </span>
</template>

<script setup>
/**
 * Info-Knopf zum Drüberfahren (Befund DMB-674355ec0e2b: „die
 * Einstellmöglichkeiten sollen einen info button zum drüberhovern haben,
 * welcher die funktion erklärt“).
 *
 * Der Text steht im Glossar (`ERKLAERUNGEN` in abschnitte.mjs); fehlt der
 * Eintrag, wird das ehrlich gesagt statt eine Erklärung zu erfinden.
 */
import { computed, ref } from 'vue'
import { erklaerung, PLATZHALTER } from './abschnitte.mjs'

const props = defineProps({
  /** Kennung im Glossar, z. B. 'sammlung'. */
  id: { type: String, required: true },
})
/** Einmalig geöffnet (Klick/Tastatur) — Hover erledigt das CSS. */
const offen = ref(false)
let zaehler = 0
const hilfeId = computed(() => `pr-info-${props.id}-${(zaehler += 1)}`)

const eintrag = computed(() => erklaerung(props.id))
const begriff = computed(() => eintrag.value?.begriff || '')
const text = computed(() => eintrag.value?.text || PLATZHALTER)
const quelle = computed(() => eintrag.value?.quelle || '')

function umschalten() { offen.value = !offen.value }
</script>

<style scoped>
.pr-info { position: relative; display: inline-flex; align-items: center; }
.pr-info-knopf {
  width: 16px; height: 16px; padding: 0; line-height: 1;
  display: inline-flex; align-items: center; justify-content: center;
  font-size: 0.68rem; font-weight: 700; font-style: italic;
  color: var(--dk-text-muted); background: var(--dk-surface-2);
  border: 1px solid var(--dk-border); border-radius: 50%; cursor: help;
}
.pr-info-knopf:hover, .pr-info-knopf:focus-visible { color: var(--dk-text); border-color: var(--dk-text-muted); }
.pr-info-text {
  position: absolute; left: 0; top: calc(100% + 4px); z-index: 20;
  width: max-content; max-width: 280px;
  padding: 8px 10px; border-radius: 8px;
  background: var(--dk-surface); color: var(--dk-text);
  border: 1px solid var(--dk-border);
  box-shadow: var(--shadow-lg);
  font-size: 0.78rem; font-weight: 400; line-height: 1.45;
  display: none;
}
/* Hover UND Tastaturfokus zeigen den Text; der Klick hält ihn offen. */
.pr-info:hover .pr-info-text,
.pr-info:focus-within .pr-info-text,
.pr-info-text.is-offen { display: block; }
.pr-info-quelle { display: block; margin-top: 4px; color: var(--dk-text-subtle); font-size: 0.7rem; }
/* Inhaltsumbruch, kein Layout: der Info-Text schwebt am schmalen Gerät nicht
   mehr, sondern steht unter dem Feld (280 px passten sonst nicht in die
   Dialogbreite). */
@media (max-width: 640px) {
  /* Am Handy kein Schweben: der Text steht unter dem Feld, volle Breite. */
  .pr-info-text { position: static; display: none; width: 100%; max-width: none; box-shadow: none; }
  .pr-info-text.is-offen { display: block; }
}
</style>
