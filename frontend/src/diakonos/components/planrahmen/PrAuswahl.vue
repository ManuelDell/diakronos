<template>
  <!-- UX-C3b: Auswahlfeld des Plantyp-Editors. Eine gespeicherte Kennung, die
       die Liste nicht (mehr) kennt, bleibt als eigene Zeile stehen und wird
       als „unbekannter Wert“ benannt — sie geht beim Bearbeiten nicht
       verloren. `warnung` erklärt darunter, warum der Wert nicht passt.

       Mit `anderer-wert` steht „Anderer Wert …“ in der Liste: ein Wert, den
       die Auswahl nicht kennt, wird eingetippt (Operator-Entscheidung aus dem
       Review). Ist die Liste leer, steht NUR das Textfeld da — nie eine leere,
       unbedienbare Auswahl. -->
  <span class="pr-auswahl">
    <span class="pr-auswahl-kopf">
      <!-- Liste leer (oder kein Katalog vorhanden): direkt das Textfeld — nie
           eine leere, unbedienbare Auswahl. Ein gespeicherter Altwert steht
           darin und geht nicht verloren. -->
      <input
        v-if="textModus"
        class="dk-form-input pr-auswahl-feld"
        :value="gespeichert"
        :aria-label="ariaLabel || undefined"
        :placeholder="platzhalter"
        :aria-invalid="unbekannt ? 'true' : undefined"
        :disabled="disabled"
        @change="$emit('update:modelValue', $event.target.value)"
      />
      <select
        v-else
        class="dk-form-select pr-auswahl-feld"
        :class="{ 'pr-auswahl--unbekannt': unbekannt }"
        :value="waehlbar"
        :aria-label="ariaLabel || undefined"
        :aria-invalid="unbekannt ? 'true' : undefined"
        :disabled="disabled"
        @change="gewaehlt($event.target.value)"
      >
        <option v-if="platzhalter" value="">{{ platzhalter }}</option>
        <option v-for="o in optionenMitEigenem" :key="o.wert" :value="o.wert">{{ o.text }}</option>
        <!-- KEINE eigene Altwert-Zeile: ein unbekannter Wert erscheint als
             „Anderer Wert …“ und steht im Textfeld darunter. -->
      </select>
      <!-- UX-C3b: ⓘ erklärt das Feld; der Text steht im Glossar (abschnitte.mjs). -->
      <PrInfo v-if="info" :id="info" />
    </span>
    <!-- Eigener Wert: bei einem gespeicherten Altwert (Anderer Wert …) oder
         nach der Wahl von „Anderer Wert …“ tippbar. -->
    <input
      v-if="andererEingabe"
      class="dk-form-input pr-auswahl-feld pr-auswahl-eigener"
      :value="gespeichert"
      placeholder="eigener Wert"
      :aria-label="andererFeldName"
      :disabled="disabled"
      @change="$emit('update:modelValue', $event.target.value)"
    />
    <span v-if="unbekannt" class="pr-auswahl-hinweis" role="status">{{ warnung || standardWarnung }}</span>
  </span>
</template>

<script setup>
/**
 * Auswahlfeld für Werte, die EXAKT passen müssen (Feld, Sammlung, Baustein,
 * Stufe, Anlass, Variante, Planvorlage …). Bewusst schmal: die Regeln
 * „Altwert nicht verlieren“ (`auswahlMitAltwert`, `istUnbekannt`) und
 * „Anderer Wert …“ (`wertAuswahl`) stehen in `auswahl.mjs` und sind dort
 * ohne DOM geprüft.
 *
 * Mit `platzhalter` ist der leere Wert immer wählbar — eine optionale Angabe
 * lässt sich damit auch wieder entfernen.
 */
import { computed, ref, watch } from 'vue'
import PrInfo from './PrInfo.vue'
import { ANDERER_WERT, UNBEKANNT, istUnbekannt, mitAnderemWert } from './auswahl.mjs'

const props = defineProps({
  modelValue: { default: '' },
  /** Anzuzeigende Optionen: `{wert, text}` — der Altwert wird hier ergänzt. */
  optionen: { type: Array, default: () => [] },
  /** Erste, leere Zeile („— bitte wählen —“). Leer = keine leere Zeile. */
  platzhalter: { type: String, default: '' },
  /** Text der Altwert-Zeile, Standard „unbekannter Wert“. */
  unbekanntName: { type: String, default: UNBEKANNT },
  /** Erklärung unter dem Feld, wenn der gespeicherte Wert unbekannt ist. */
  warnung: { type: String, default: '' },
  ariaLabel: { type: String, default: '' },
  /** Glossar-Kennung für das ⓘ (z. B. 'sammlung'); leer = kein Knopf. */
  info: { type: String, default: '' },
  /** Eintrag „Anderer Wert …“ anbieten (Werte, die frei wählbar sind). */
  andererWert: Boolean,
  disabled: Boolean,
})
const emit = defineEmits(['update:modelValue'])

const gespeichert = computed(() => (props.modelValue === undefined || props.modelValue === null
  ? '' : String(props.modelValue)))

const unbekannt = computed(() => istUnbekannt(props.optionen, gespeichert.value))

/** Der Eintrag „Anderer Wert …“ steht zur Wahl (nur mit `andererWert`). */
const mitEigenem = computed(() => props.andererWert === true)

/** Optionsliste der `<select>`-Zeile — MIT „Anderer Wert …“ (Review Punkt 2). */
const optionenMitEigenem = computed(() => (mitEigenem.value
  ? mitAnderemWert(props.optionen) : props.optionen))

/** Liste ist leer: nur das Textfeld (ein gespeicherter Altwert steht darin). */
const textModus = computed(() => props.andererWert === true && props.optionen.length === 0)

/** „Anderer Wert …“ ist gewählt: ein unbekannter Wert steht schon da, oder
     der Eintrag wurde gerade gewählt (das Feld ist dann leer). */
const andererOffen = ref(false)
const andererEingabe = computed(() => mitEigenem.value
  && (andererOffen.value || unbekannt.value))

/** Wert, den die `<select>`-Zeile darstellt. */
const waehlbar = computed(() => (andererEingabe.value ? ANDERER_WERT : gespeichert.value))

watch(() => props.modelValue, () => { andererOffen.value = false })

function gewaehlt(wert) {
  if (wert === ANDERER_WERT) {
    if (!andererEingabe.value) andererOffen.value = true
    return
  }
  andererOffen.value = false
  emit('update:modelValue', wert)
}

const andererFeldName = computed(() => `${props.ariaLabel || 'Wert'} – eigener Wert`)

const standardWarnung = computed(() => `„${gespeichert.value}“ steht nicht in der Liste. `
  + 'Der Wert bleibt erhalten, bis du ihn ersetzt — die Prüfung meldet ihn als unbekannt.')
</script>

<style scoped>
.pr-auswahl { display: flex; flex-direction: column; gap: 4px; min-width: 0; }
.pr-auswahl-kopf { display: inline-flex; align-items: center; gap: 6px; }
.pr-auswahl-feld { max-width: 340px; }
.pr-auswahl--unbekannt {
  border-color: color-mix(in oklch, var(--dk-warning) 55%, var(--dk-border));
}
.pr-auswahl-altwert { font-style: italic; }
.pr-auswahl-eigener { font-family: inherit; }
.pr-auswahl-hinweis { font-size: 0.76rem; font-weight: 400; color: var(--dk-warning); line-height: 1.4; max-width: 340px; }
/* Inhaltsumbruch, kein Layout: Feld und Warnhinweis nehmen die volle Breite
   (die 340-px-Grenze des Hinweises fällt weg). */
@media (max-width: 640px) {
  .pr-auswahl-feld, .pr-auswahl-hinweis { max-width: none; width: 100%; }
}
</style>
