<template>
  <!-- CHAT-7b-UI — Personensuche für RUNDEN (ein Baustein, zwei Einsatzorte:
       „Neue Runde“ und „Person vorschlagen“). Dieselbe Suche wie überall in
       „Nachrichten“ (`chat.personen_suchen`, entprellt, veraltete Antworten
       verworfen); wählbar nur, was der Server als beschreibbar meldet. -->
  <div class="dk-runde-auswahl">
    <label class="dk-runde-label" :for="feldId">{{ feldLabel }}</label>
    <input
      :id="feldId"
      v-model="begriff"
      class="dk-runde-feld"
      type="search"
      autocomplete="off"
      :placeholder="SUCH_PLATZHALTER"
      @keydown.escape.prevent="begriff = ''"
      @keydown.enter.prevent="ersterTreffer"
    />
    <p v-if="zaehler" class="dk-runde-zaehler" role="status">{{ zaehler }}</p>

    <p v-if="zuKurz" class="dk-runde-hinweis">
      Bitte mindestens {{ SUCHE_MIN_ZEICHEN }} Zeichen eingeben.
    </p>
    <DkSkelett v-else-if="laedt" form="zeilen" :anzahl="2" text="Personen werden gesucht …" />
    <p v-else-if="suchFehler" class="dk-runde-fehler" role="alert">{{ suchFehler }}</p>
    <ul v-else-if="kandidaten.length" class="dk-runde-treffer">
      <li v-for="person in kandidaten" :key="person.mitglied">
        <!-- Mehrfachauswahl (Neue Runde): ein Kästchen je Person. -->
        <label
          v-if="mehrfach"
          class="dk-runde-treffer-zeile"
          :class="{ 'is-gesperrt': !waehlbar(person), 'is-gewaehlt': istGewaehlt(props.auswahl, person.mitglied) }"
        >
          <input
            type="checkbox"
            class="dk-runde-kasten"
            :checked="istGewaehlt(props.auswahl, person.mitglied)"
            :disabled="!waehlbar(person)"
            @change="umschalten(person)"
          />
          <span v-if="person.bild" class="dk-runde-av dk-runde-av--bild">
            <img :src="person.bild" alt="" />
          </span>
          <span v-else class="dk-runde-av" aria-hidden="true">{{ initialen(person.name) }}</span>
          <span class="dk-runde-name">{{ person.name }}</span>
          <span v-if="person.hinweis" class="dk-runde-grund">{{ person.hinweis }}</span>
        </label>
        <!-- Einzelauswahl (Vorschlagen): die Zeile ist ein DkButton (Knopf-
             System, UX1g2) — Inhalt links, „vorschlagen“ rechts. -->
        <DkButton
          v-else
          variant="ghost"
          class="dk-runde-treffer-zeile"
          :class="{ 'is-gesperrt': !waehlbar(person) }"
          :disabled="!waehlbar(person) || laeuft"
          @click="$emit('waehlen', person)"
        >
          <span v-if="person.bild" class="dk-runde-av dk-runde-av--bild">
            <img :src="person.bild" alt="" />
          </span>
          <span v-else class="dk-runde-av" aria-hidden="true">{{ initialen(person.name) }}</span>
          <span class="dk-runde-name">{{ person.name }}</span>
          <span v-if="person.hinweis" class="dk-runde-grund">{{ person.hinweis }}</span>
          <span v-else class="dk-runde-grund">vorschlagen</span>
        </DkButton>
      </li>
    </ul>
    <p v-else-if="begriff.trim()" class="dk-runde-hinweis">Niemand gefunden.</p>
  </div>
</template>

<script setup>
/**
 * RundePersonenAuswahl — die Personensuche für Runden (CHAT-7b-UI-a, Punkt 1/3).
 *
 * EIN Baustein für beide Orte: „Neue Runde“ (Mehrfachauswahl, 2–7) und
 * „Person vorschlagen“ (eine Person, Klick schlägt vor). Die Suche ist die
 * vorhandene (`chat.personen_suchen`, Entpreller aus `nachrichtenSuche.mjs`),
 * damit es keine zweite Personensuche gibt.
 *
 * Wählbar ist NUR, was der Server beschreibbar meldet (`darf_schreiben ===
 * true`, `rundenKandidat`) — sonst steht die Zeile ausgegraut da, ohne dass
 * die Oberfläche einen Grund erfindet.
 */
import { computed, onUnmounted, ref, watch } from 'vue'
import { apiGet } from '../../composables/useApi.js'
import { fehlertext } from '../../../shared/fehlertexte.js'
import { initialen as initialenAus } from '../../composables/anzeigename.mjs'
import { SUCHE_MIN_ZEICHEN, SUCH_PLATZHALTER, darfPersonenFragen, entpreller } from '../../composables/nachrichtenSuche.mjs'
import {
  ANDERE_MAX, auswahlUmschalten, istGewaehlt, kandidatenAusAntwort, zaehlerText,
} from '../../composables/nachrichtenRunden.mjs'
import DkButton from '../ui/DkButton.vue'
import DkSkelett from '../ui/DkSkelett.vue'

const props = defineProps({
  /** Mehrfachauswahl (Neue Runde) oder Einzelauswahl (Vorschlagen)? */
  mehrfach: { type: Boolean, default: true },
  /** Die gewählten MITGLIED-Kennungen (Mehrfachauswahl). */
  auswahl: { type: Array, default: () => [] },
  /** Steht ein Aufruf? (sperrt die Einzelauswahl-Knöpfe) */
  laeuft: { type: Boolean, default: false },
  /** Ausgeschlossene Kennungen (schon dabei / schon vorgeschlagen). */
  ohne: { type: Array, default: () => [] },
  feldLabel: { type: String, default: 'Personen' },
  feldId: { type: String, default: 'runde-personensuche' },
  /** Timer/Netz hineinreichen: der Test gibt Attrappen, der Betrieb nichts. */
  timer: { type: Function, default: null },
  timerAus: { type: Function, default: null },
  holen: { type: Function, default: null },
})
const emit = defineEmits(['update:auswahl', 'waehlen'])

const begriff = ref('')
const kandidaten = ref([])
const laedt = ref(false)
const suchFehler = ref('')
let anfrageNr = 0
let aktiv = true

const holen = props.holen || ((parameter) => apiGet('chat.personen_suchen', parameter))

/** Enter wählt den ersten wählbaren Treffer — Tastaturweg ohne Maus. */
function ersterTreffer() {
  const person = kandidaten.value.find((k) => waehlbar(k))
  if (!person || props.laeuft) return
  if (props.mehrfach) umschalten(person)
  else emit('waehlen', person)
}

const zuKurz = computed(() => begriff.value.trim() !== '' && !darfPersonenFragen(begriff.value))
const zaehler = computed(() => (props.mehrfach ? zaehlerText({ anzahl: props.auswahl.length }) : ''))
const initialen = (name) => initialenAus(null, String(name || ''))
const ohneMenge = computed(() => new Set(props.ohne.map(String).filter(Boolean)))
/**
 * Wählbar: der Server sagt „beschreibbar“ UND die Person ist nicht schon dabei
 * UND (Mehrfachauswahl) die Grenze ist noch nicht erreicht.
 */
function waehlbar(person) {
  if (person.waehlbar !== true) return false
  if (ohneMenge.value.has(person.mitglied)) return false
  if (!props.mehrfach) return true
  return istGewaehlt(props.auswahl, person.mitglied) || props.auswahl.length < ANDERE_MAX
}

const entprellt = entpreller({
  ...(props.timer ? { timer: props.timer } : {}),
  ...(props.timerAus ? { timerAus: props.timerAus } : {}),
  beiFaelligkeit: (gefragt) => personenHolen(gefragt),
})
onUnmounted(() => {
  aktiv = false
  entprellt.beenden()
})

async function personenHolen(gefragt) {
  if (!aktiv || !darfPersonenFragen(gefragt)) {
    kandidaten.value = []
    return
  }
  const nummer = ++anfrageNr
  laedt.value = true
  suchFehler.value = ''
  try {
    const antwort = await holen({ q: gefragt })
    if (!aktiv || nummer !== anfrageNr) return
    kandidaten.value = kandidatenAusAntwort(antwort)
  } catch (fehler) {
    if (!aktiv || nummer !== anfrageNr) return
    kandidaten.value = []
    suchFehler.value = fehlertext(fehler, { text: 'Die Personen konnten nicht gesucht werden. Versuche es noch einmal.' })
  } finally {
    if (aktiv && nummer === anfrageNr) laedt.value = false
  }
}

watch(begriff, (neu) => {
  suchFehler.value = ''
  if (!darfPersonenFragen(neu)) {
    anfrageNr += 1
    kandidaten.value = []
    laedt.value = false
    entprellt.abbrechen()
    return
  }
  entprellt.tippen(neu)
})

function umschalten(person) {
  if (!waehlbar(person)) return
  emit('update:auswahl', auswahlUmschalten(props.auswahl, person.mitglied))
}
</script>

<style scoped>
.dk-runde-auswahl { display: flex; flex-direction: column; gap: var(--sp-2); }
.dk-runde-feld {
  width: 100%;
  min-height: var(--control-h);
  padding: var(--sp-2) var(--sp-3);
  border: var(--rahmen-breite) solid var(--rahmen-farbe);
  border-radius: var(--radius);
  background: var(--surface);
  color: var(--text);
  font-family: inherit;
  font-size: var(--fs-14);
  line-height: var(--lh-text);
}
.dk-runde-feld:focus-visible { outline: var(--rahmen-breite) solid var(--focus-ring); outline-offset: var(--rahmen-breite); }
.dk-runde-label { font-size: var(--fs-sm); font-weight: var(--fw-mittel); color: var(--text); }
.dk-runde-zaehler { margin: 0; font-size: var(--fs-12); color: var(--muted); }
.dk-runde-hinweis { margin: 0; font-size: var(--fs-12); color: var(--subtle); }
.dk-runde-fehler {
  margin: 0;
  padding: var(--sp-2) var(--sp-3);
  border-radius: var(--radius);
  background: var(--err-soft);
  color: var(--err);
  font-size: var(--fs-12);
}
.dk-runde-treffer { list-style: none; margin: 0; padding: 0; max-height: calc(var(--sp-8) * 4); overflow-y: auto; }
.dk-runde-treffer-zeile {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  width: 100%;
  min-height: var(--control-h);
  padding: var(--sp-1) var(--sp-2);
  border: none;
  border-radius: var(--radius);
  background: none;
  font-family: inherit;
  font-size: inherit;
  color: var(--text);
  text-align: start;
  cursor: pointer;
}
.dk-runde-treffer-zeile:hover { background: var(--surface-hover); }
.dk-runde-treffer-zeile.is-gewaehlt { background: var(--surface-2); }
/* Ausgegraut, aber LESBAR: „nicht auswählbar“ ist eine Auskunft, keine Strafe. */
.dk-runde-treffer-zeile.is-gesperrt,
.dk-runde-treffer-zeile:disabled { color: var(--subtle); cursor: default; }
.dk-runde-treffer-zeile:focus-visible { outline: var(--rahmen-breite) solid var(--focus-ring); outline-offset: calc(var(--rahmen-breite) * -2); }
.dk-runde-kasten { flex: none; }
.dk-runde-av {
  width: var(--sp-6);
  height: var(--sp-6);
  border-radius: 50%;
  display: grid;
  place-items: center;
  flex: none;
  background: var(--surface-2);
  color: var(--muted);
  font-size: var(--fs-12);
  font-weight: var(--fw-fett);
  overflow: hidden;
}
.dk-runde-av--bild img { width: 100%; height: 100%; object-fit: cover; }
.dk-runde-name { font-size: var(--fs-14); min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.dk-runde-grund { margin-left: auto; font-size: var(--fs-12); color: var(--subtle); }
</style>
