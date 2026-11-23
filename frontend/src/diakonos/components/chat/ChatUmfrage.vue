<template>
  <!-- CHAT-5-UI: Umfrage als Karte im Verlauf (Konzept S2, „Oberfläche als
       Karte im Verlauf“). Sie steht an der Stelle der Umfrage-Nachricht —
       Frage, Optionen, eigener Stand, Ergebnis (Balken + Zahl), Frist, Zustand.
       Farben und Abstände nur aus `tokens.css`; keine eigene Farbe. -->
  <div
    class="dk-umfrage"
    :class="{ 'is-geschlossen': !offen }"
    role="group"
    :aria-label="`Umfrage: ${frage}`"
  >
    <div class="dk-umfrage-kopf">
      <span class="dk-umfrage-marke">{{ TEXTE.titel }}</span>
      <span class="dk-umfrage-art">{{ artText }}</span>
      <span v-if="!offen" class="dk-umfrage-zustand">{{ zustand }}</span>
    </div>

    <p class="dk-umfrage-frage">{{ frage }}</p>
    <p class="dk-umfrage-neben">
      <span v-if="mehrfach">{{ TEXTE.mehrfach }}</span>
      <span v-if="mehrfach" aria-hidden="true"> · </span>
      <span>{{ frist }}</span>
    </p>

    <!-- Die Optionen: Ergebnis (Balken + Zahl) steht IMMER darunter, gewählt
         wird über Radio bzw. Checkbox — beschriftet mit Antwort + Zahl. -->
    <ul v-if="zeilen.length" class="dk-umfrage-optionen">
      <li v-for="z in zeilen" :key="z.nummer" class="dk-umfrage-option">
        <label v-if="auswaehlbar" class="dk-umfrage-wahl">
          <input
            :type="mehrfach ? 'checkbox' : 'radio'"
            :name="`umfrage-${kennung}`"
            :value="z.nummer"
            :checked="auswahl.includes(z.nummer)"
            :aria-describedby="`umfrage-ergebnis-${kennung}-${z.nummer}`"
            @change="waehlen(z.nummer)"
          />
          <span class="dk-umfrage-option-text">{{ z.nummer }}. {{ z.text }}</span>
        </label>
        <p v-else class="dk-umfrage-option-text" :class="{ 'is-gewaehlt': auswahl.includes(z.nummer) }">
          <span v-if="auswahl.includes(z.nummer)" class="dk-umfrage-eigene-marke">✓</span>
          {{ z.nummer }}. {{ z.text }}
        </p>
        <div
          :id="`umfrage-ergebnis-${kennung}-${z.nummer}`"
          class="dk-umfrage-balken-zeile"
        >
          <span class="dk-umfrage-balken" aria-hidden="true">
            <span class="dk-umfrage-balken-fuellung" :style="{ width: z.anteil + '%' }"></span>
          </span>
          <span class="dk-umfrage-zahl">{{ z.stimmen }}</span>
          <span class="dk-umfrage-nur-vorlesen">
            {{ z.stimmen === 1 ? 'eine Stimme' : `${z.stimmen} Stimmen` }}
          </span>
        </div>
        <!-- Namen NUR bei offener Umfrage — der Server schickt sie dort.
             Anonym: die Liste ist immer leer (Regel in `ergebnisZeilen`). -->
        <p v-if="z.namen.length" class="dk-umfrage-namen">{{ z.namen.join(', ') }}</p>
      </li>
    </ul>
    <p v-else class="dk-umfrage-neben">{{ TEXTE.keine }}</p>

    <p class="dk-umfrage-summe">
      {{ gesamtText }}
      <span v-if="stimmenGesamt > abgegebenZahl(umfrage)" class="dk-umfrage-neben">
        · {{ stimmenGesamt }} {{ TEXTE.stimmen }}
      </span>
    </p>

    <!-- KEINE erklärenden Kästen (BEF-CHAT-HINWEIS, Manuel 23.11.: „keine
         Bemutterung der Teilnehmer“): der frühere graue Kasten „Ergebnis bei
         wenigen Teilnehmenden erratbar“ ist ERSATZLOS weg — er wurde nach einer
         erfolgreichen Abstimmung außerdem für eine Fehlermeldung gehalten.
         Was bleibt, ist Zustand, nicht Belehrung: der eigene Stand unten und
         echte Serverfehler (`.dk-umfrage-fehler`). -->
    <p v-if="stand" class="dk-umfrage-stand">{{ stand }}</p>

    <div v-if="knopfText || schliessenZeigen" class="dk-umfrage-aktionen">
      <DkButton
        v-if="knopfText"
        variant="primary"
        size="sm"
        :loading="laeuft"
        :disabled="!auswahl.length"
        @click="abstimmen"
      >{{ knopfText }}</DkButton>
      <DkButton
        v-if="schliessenZeigen"
        variant="ghost"
        size="sm"
        :loading="schliesst"
        @click="schliessen"
      >{{ TEXTE.schliessen }}</DkButton>
    </div>

    <p v-if="fehler" class="dk-umfrage-fehler" role="alert">{{ fehler }}</p>
  </div>
</template>

<script setup>
/**
 * ChatUmfrage — eine Umfrage als Karte im Verlauf (CHAT-5-UI).
 *
 * Die Karte zeichnet und meldet; sie entscheidet nichts (Regeln:
 * `umfrage.mjs`, Server: `api/chat.py`). Über 44 px Tippflächen, native
 * Radio-/Checkbox-Elemente (Tastatur und Vorlesehilfen kostenlos korrekt) und
 * `role="group"` mit Namen „Umfrage: <Frage>“.
 *
 * ANONYM: keine Namen, kein eigener Stand als Option (`eigene_stimme` ist beim
 * Server `null`), nur Summen — plus der Zustand „Du hast abgestimmt. / Nicht
 * mehr änderbar.“. Erklärende Hinweiskästen gibt es NICHT (BEF-CHAT-HINWEIS).
 * OFFEN: Namen stehen an der Option, wenn der Server sie liefert (er tut es
 * nur bei offenen Umfragen) — hier wird NICHTS nachgeladen.
 */
import { computed, ref, watch } from 'vue'
import DkButton from '../ui/DkButton.vue'
import {
  TEXTE, abstimmKnopfText, abgegebenZahl, darfSchliessenZeigen, eigeneWahl,
  eigenerStandText, ergebnisZeilen, fristText, zustandText, wahlUmschalten,
} from './umfrage.mjs'

const props = defineProps({
  /** Die Umfragedaten aus der Nachricht (`nachricht.umfrage`). */
  umfrage: { type: Object, required: true },
  /** Läuft gerade eine Abgabe? (Elternteil hält den Zustand) */
  laeuft: { type: Boolean, default: false },
  /** Läuft gerade das Schließen DIESER Umfrage? (Elternteil hält den Zustand:
   *  `umfrageSchliessenLaeuft === umfrage.name`) */
  schliesst: { type: Boolean, default: false },
  /** Meldung des Servers zur letzten Aktion (403, 400 …) — ruhig, kein Alarm. */
  fehler: { type: String, default: '' },
})

const emit = defineEmits(['abstimmen', 'schliessen'])

const auswahl = ref([])

const kennung = computed(() => String(props.umfrage?.name || 'neu').replace(/[^\w-]/g, ''))
const frage = computed(() => String(props.umfrage?.frage || ''))
const mehrfach = computed(() => props.umfrage?.mehrfach === true)
const offen = computed(() => {
  const u = props.umfrage || {}
  if (u.geschlossen_am) return false
  return u.offen !== false
})
const artText = computed(() => (props.umfrage?.anonym === true ? TEXTE.anonym : TEXTE.offen))
const anonym = computed(() => props.umfrage?.anonym === true)
const zustand = computed(() => zustandText(props.umfrage))
const frist = computed(() => fristText(props.umfrage))
const zeilen = computed(() => ergebnisZeilen(props.umfrage))
const stand = computed(() => eigenerStandText(props.umfrage))
const knopfText = computed(() => abstimmKnopfText(props.umfrage))
const schliessenZeigen = computed(() => darfSchliessenZeigen(props.umfrage))
const stimmenGesamt = computed(() => Number(props.umfrage?.stimmen_gesamt) || 0)
const auswaehlbar = computed(() => Boolean(knopfText.value))

const gesamtText = computed(() => {
  const n = abgegebenZahl(props.umfrage)
  if (n === 1) return '1 Person hat abgestimmt'
  return `${n} Personen haben abgestimmt`
})

/**
 * Die Auswahl mit dem Stand des Servers abgleichen (nach jeder Antwort).
 *
 * Beobachtet wird NUR die eigene Wahl (`eigene_stimme`), nicht das ganze
 * Objekt: der Verlauf wird alle paar Sekunden neu geholt, und eine
 * angefangene, noch nicht abgegebene Auswahl darf dabei nicht verloren gehen.
 */
function ausServer() {
  auswahl.value = eigeneWahl(props.umfrage)
}
ausServer()
watch(() => eigeneWahl(props.umfrage).join(','), ausServer)

function waehlen(nummer) {
  if (!auswaehlbar.value) return
  auswahl.value = wahlUmschalten(auswahl.value, nummer, mehrfach.value)
}

function abstimmen() {
  if (!auswahl.value.length || props.laeuft) return
  emit('abstimmen', { umfrage: props.umfrage, optionen: [...auswahl.value] })
}

function schliessen() {
  if (props.schliesst) return
  emit('schliessen', { umfrage: props.umfrage })
}

/** Stand der Karte — nur für den Node-Test nachlesbar (kein Betriebsweg). */
defineExpose({ auswahl, waehlen, abstimmen, schliessen })
</script>

<style scoped>
.dk-umfrage {
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
  padding: var(--sp-3);
  border: var(--rahmen-breite) solid var(--divider);
  border-left: calc(3 * var(--rahmen-breite)) solid var(--accent);
  border-radius: var(--radius);
  background: var(--surface);
  min-width: 0;
}
.dk-umfrage.is-geschlossen { background: var(--surface-2); border-left-color: var(--subtle); }
.dk-umfrage-kopf {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--sp-2);
  font-size: var(--fs-12);
  color: var(--muted);
}
.dk-umfrage-marke {
  font-weight: var(--fw-fett);
  color: var(--text);
  text-transform: uppercase;
  letter-spacing: .04em;
}
.dk-umfrage-zustand {
  margin-left: auto;
  padding: 0 var(--sp-2);
  border-radius: var(--radius);
  background: var(--surface-2);
  color: var(--muted);
}
.dk-umfrage-frage {
  margin: 0;
  font-weight: var(--fw-mittel);
  color: var(--text);
  font-size: var(--fs-14);
  line-height: var(--lh-text);
  overflow-wrap: anywhere;
}
.dk-umfrage-neben {
  margin: 0;
  font-size: var(--fs-12);
  color: var(--subtle);
}
.dk-umfrage-optionen {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
}
.dk-umfrage-option { min-width: 0; }
.dk-umfrage-wahl {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  min-height: var(--control-h);
  padding: 0 var(--sp-1);
  border-radius: var(--radius);
  cursor: pointer;
}
.dk-umfrage-wahl:hover { background: var(--surface-hover); }
.dk-umfrage-wahl input {
  flex: none;
  width: 20px;
  height: 20px;
  accent-color: var(--accent);
}
.dk-umfrage-wahl input:focus-visible { outline: var(--rahmen-breite) solid var(--focus-ring); outline-offset: 2px; }
.dk-umfrage-option-text {
  margin: 0;
  font-size: var(--fs-14);
  color: var(--text);
  overflow-wrap: anywhere;
}
.dk-umfrage-option-text.is-gewaehlt { font-weight: var(--fw-mittel); }
.dk-umfrage-eigene-marke { color: var(--accent); margin-right: var(--sp-1); }
.dk-umfrage-balken-zeile {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  margin-top: var(--sp-1);
}
.dk-umfrage-balken {
  flex: 1;
  height: 8px;
  border-radius: var(--radius);
  background: var(--surface-2);
  overflow: hidden;
}
.dk-umfrage-balken-fuellung {
  display: block;
  height: 100%;
  background: var(--accent);
  transition: width var(--fast);
}
.dk-umfrage-zahl {
  flex: none;
  min-width: 2ch;
  text-align: right;
  font-size: var(--fs-12);
  font-variant-numeric: var(--fs-tabular);
  color: var(--text);
}
.dk-umfrage-namen {
  margin: 0;
  padding-left: var(--sp-4);
  font-size: var(--fs-12);
  color: var(--muted);
  overflow-wrap: anywhere;
}
.dk-umfrage-summe {
  margin: 0;
  font-size: var(--fs-12);
  color: var(--muted);
}
.dk-umfrage-stand { margin: 0; font-size: var(--fs-12); color: var(--subtle); }
.dk-umfrage-aktionen {
  display: flex;
  flex-wrap: wrap;
  gap: var(--sp-2);
  margin-top: var(--sp-1);
}
.dk-umfrage-fehler {
  margin: 0;
  padding: var(--sp-2);
  border-radius: var(--radius);
  background: var(--err-soft);
  color: var(--err);
  font-size: var(--fs-12);
}
.dk-umfrage-nur-vorlesen {
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
