<template>
  <div class="dk-ui-schalterzeile" :class="{ 'is-disabled': disabled }">
    <DkCheckbox
      v-model="an"
      :disabled="disabled"
      :aria-label="ariaLabel"
      :aria-describedby="zeilenBeschreibung || ''"
    >
      <slot>{{ label }}</slot>
    </DkCheckbox>
    <p v-if="meldung" :id="meldungId" class="dk-ui-schalterzeile-fehler" role="alert">{{ meldung }}</p>
    <p v-else-if="zeilenHilfe" :id="hilfeId" class="dk-ui-schalterzeile-hilfe">{{ help }}</p>
  </div>
</template>

<script setup>
/**
 * DkSchalterZeile — EINE Schalterzeile der gemeinsamen Formular-Sprache.
 *
 * Warum dieser Baustein (BEFUND Manuel 23.11., #/website):
 * Die Schalter einer Karte standen dort als nacktes Kästchen zwischen Absätzen,
 * ohne eigenen Bereich: mal klebte der Schalter am Text darüber, mal nicht, und
 * die Hilfetexte sprangen zwischen „direkt darunter“ und „mit Lücke“. Hier ist
 * die Zeile EIN Baustein mit EINEM festen Aufbau:
 *
 *   Schalter + Beschriftung        (linksbündig, in EINER Zeile)
 *     Hilfetext                    (eingerückt auf den Text der Beschriftung)
 *
 * Abstände kommen ausschließlich aus Tokens (`--sp-1`, `--sp-2`, `--gap`),
 * damit alle Schalterzeilen einer Seite gleich aussehen — egal in welcher
 * Karte sie stehen.
 *
 * `v-model` ist der Schalterstand (Boolean). Anzeige und Modell sind sofort
 * gleich: der Aufrufer entscheidet, was er mit dem neuen Wert tut (die
 * Freigabe-Rückfrage der Website liegt NICHT hier, damit der Schalter nicht
 * umspringt, während die Rückfrage offen ist).
 *
 * `aria-describedby` zeigt auf den Hilfetext bzw. die Fehlermeldung — der
 * Schalter bekommt damit denselben Satz vorgelesen, der darunter steht.
 */
import { computed, useId } from 'vue'
import DkCheckbox from './DkCheckbox.vue'
import {
  beschriebenDurch,
  fehlerKennung,
  hatHilfe,
  hilfeKennung,
  zeilenKennung,
} from './formularZeile.mjs'

const props = defineProps({
  /** Schalterstand (Boolean). */
  modelValue: Boolean,
  /** Beschriftung neben dem Kästchen (alternativ der Standard-Slot). */
  label: { type: String, default: '' },
  /** Hilfetext unter der Beschriftung (eingerückt). Leer = kein Hilfetext. */
  help: { type: String, default: '' },
  /** Meldung unter der Zeile (Server-Ablehnung). Hat Vorrang vor der Hilfe. */
  error: { type: String, default: '' },
  /**
   * Zugänglicher Name des KÄSTCHENS (nicht der Zeile) — gehört aufs `<input>`,
   * ein `aria-label` am umgebenden Label erreicht es nicht (siehe DkCheckbox).
   */
  ariaLabel: { type: String, default: '' },
  disabled: Boolean,
})

const emit = defineEmits(['update:modelValue'])

const kennung = zeilenKennung(typeof useId === 'function' ? useId : undefined)
const hilfeId = hilfeKennung(kennung)
const meldungId = fehlerKennung(kennung)

const an = computed({
  get: () => props.modelValue === true,
  set: (wert) => emit('update:modelValue', wert === true),
})

/** Leere Angaben erzeugen weder Absatz noch Beschreibung. */
const zeilenHilfe = computed(() => hatHilfe(props.help))
const meldung = computed(() => String(props.error ?? '').trim())

const zeilenBeschreibung = computed(() => beschriebenDurch({
  fehler: props.error,
  hilfe: props.help,
  kennung,
}))
</script>

<style scoped>
/* EINE Zeile = EINE Gruppe: Schalter, darunter Hilfe (Faktor 1) und Fehler.
   Der Abstand ZWISCHEN zwei Zeilen setzt der Aufrufer (`--gap`). */
.dk-ui-schalterzeile {
  display: flex;
  flex-direction: column;
  gap: var(--sp-1);
  min-width: 0;
}
.dk-ui-schalterzeile.is-disabled { opacity: .6; }
/* Der Hilfetext steht auf dem Text der Beschriftung — nicht darunter am
   Kästchen: die Einrückung ist Breite des Kästchens + Abstand aus dem
   Baustein (`--sp-2`), technisch als calc über die Tokens.
   ANNAHME (R1/Nachtrag 8): Das Kästchen selbst ist 16 px breit und steht im
   Markup von `DkCheckbox` (dort fest, aus der Anforderung „Kästchen nicht
   skalieren“) — es gibt dafür kein Token. `--sp-4` ist damit die
   Token-Entsprechung dieser Breite; ändert `DkCheckbox` sein Kästchen, gehört
   diese Zeile mit angefasst (der Render-Test R4 hält die Rechnung fest). */
.dk-ui-schalterzeile-hilfe,
.dk-ui-schalterzeile-fehler {
  margin: 0;
  padding-left: calc(var(--sp-4) + var(--sp-2));
  font-size: var(--fs-sm);
  color: var(--muted);
  overflow-wrap: anywhere;
}
.dk-ui-schalterzeile-fehler { color: var(--err); font-weight: var(--fw-mittel); }
</style>
