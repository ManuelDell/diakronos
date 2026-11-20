<template>
  <!-- CHAT-6-UI: Reiter „Chat“ in „Zu prüfen“ — nichts sendet, alles über den
       Server. 403 zeigt der Reiter GAR NICHT (die Elternseite fragt
       `meldungen_liste` und zeigt ihn nur bei einer Antwort); hier steht nur,
       was die Antwort trägt. Keine Rechtelogik: was erscheint, entscheidet der
       Server über die Felder (melder, vorgeschichte, nachricht …). -->
  <section class="dk-mpanel" aria-label="Meldungen aus dem Chat">
    <p v-if="ladeFehler" class="dk-mpanel-fehler" role="alert">{{ ladeFehler }}</p>

    <DkSkelett v-if="laedt && !zeilen.length" form="zeilen" :anzahl="3" text="Meldungen werden geladen" />

    <template v-else>
      <!-- Zweiter Abschnitt: erledigte Meldungen, zugeklappt. -->
      <div class="dk-mpanel-wechsler">
        <DkFilterChips
          :chips="filterChips"
          :model-value="filter"
          aria-label="Stand der Meldungen"
          @waehlen="filterWaehlen"
        />
        <DkButton
          v-if="filter === 'offen'"
          variant="ghost"
          size="sm"
          :aria-expanded="erledigtOffen ? 'true' : 'false'"
          @click="erledigtUmschalten"
        >{{ erledigtOffen ? 'Erledigte ausblenden' : TEXTE.erledigtTitel }}</DkButton>
      </div>

      <DkEmpty
        v-if="!sichtbar.length"
        icon="⚑"
        :title="filter === 'offen' ? TEXTE.leerOffenTitel : 'Nichts hier'"
        :text="filter === 'offen' ? TEXTE.leerOffenText : 'In diesem Abschnitt steht gerade keine Meldung.'"
      />

      <ul v-else class="dk-mpanel-liste">
        <li v-for="m in sichtbar" :key="m.name" class="dk-mpanel-eintrag" :data-meldung="m.name">
          <!-- Kopf: Gesprächstitel (1:1 neutral „Direktnachricht“ — so liefert
               es der Server), Grund, Zeitpunkt (deutsche Zeit über die
               gemeinsame Zeit-Hilfe). Kein Name der meldenden Person, wenn
               der Server keinen liefert. -->
          <div class="dk-mpanel-kopf">
            <div class="dk-mpanel-kopftext">
              <p class="dk-mpanel-titel">{{ m.gespraechTitel }}</p>
              <p class="dk-mpanel-meta">
                <span class="dk-mpanel-grund">{{ m.grundText }}</span>
                <span v-if="m.erstelltAmText" class="dk-mpanel-zeit">· {{ m.erstelltAmText }}</span>
                <span v-if="!m.offen" class="dk-mpanel-stand">· {{ m.standText }}</span>
              </p>
              <p v-if="m.melderText" class="dk-mpanel-melder">Gemeldet von {{ m.melderText }}</p>
            </div>
            <DkButton
              variant="secondary"
              size="sm"
              :aria-expanded="offeneZeile === m.name ? 'true' : 'false'"
              :aria-controls="`meldung-${m.name}`"
              @click="umschalten(m.name)"
            >{{ offeneZeile === m.name ? 'Schließen' : 'Ansehen' }}</DkButton>
          </div>

          <p v-if="m.freitextText" class="dk-mpanel-freitext">„{{ m.freitextText }}“</p>

          <!-- Aufgeklappt: der Ausschnitt (die fünf davor, alt → neu, dann die
               gemeldete Nachricht HERVORGEHOBEN) und die Entscheidungen. Alles
               aus DIESER Antwort — keine eigene Abfrage. -->
          <div v-if="offeneZeile === m.name" :id="`meldung-${m.name}`" class="dk-mpanel-auszug">
            <ol class="dk-mpanel-verlauf">
              <li
                v-for="(z, i) in m.ausschnitt.davor"
                :key="z.name || `v${i}`"
                class="dk-mpanel-zeile"
              >
                <span class="dk-mpanel-zeile-kopf">
                  <span class="dk-mpanel-zeile-autor">{{ z.autor || 'Unbekannt' }}</span>
                  <span v-if="zeitVon(z.erstellt_am)" class="dk-mpanel-zeile-zeit">{{ zeitVon(z.erstellt_am) }}</span>
                </span>
                <span class="dk-mpanel-zeile-text">{{ z.geloescht ? 'Diese Nachricht wurde gelöscht.' : z.text }}</span>
              </li>
              <li class="dk-mpanel-zeile is-gemeldet">
                <span class="dk-mpanel-zeile-kopf">
                  <span class="dk-mpanel-zeile-autor">{{ m.nachrichtAutor || 'Unbekannt' }}</span>
                  <span v-if="zeitVon(m.nachricht?.erstellt_am)" class="dk-mpanel-zeile-zeit">{{ zeitVon(m.nachricht.erstellt_am) }}</span>
                  <span class="dk-mpanel-zeile-marke">gemeldet</span>
                </span>
                <span class="dk-mpanel-zeile-text">
                  {{ m.nachrichtText || 'Die Nachricht ist nicht mehr vorhanden.' }}
                </span>
              </li>
            </ol>

            <template v-if="m.offen">
              <div class="dk-mpanel-entscheidung">
                <fieldset class="dk-mpanel-wahl">
                  <legend class="dk-mpanel-label">Entscheidung</legend>
                  <label v-for="e in ENTSCHEIDUNGEN" :key="e.schluessel" class="dk-mpanel-wahlzeile">
                    <input
                      v-model="wahl[m.name]"
                      type="radio"
                      :name="`entscheidung-${m.name}`"
                      :value="e.schluessel"
                    />
                    <span>{{ e.label }}</span>
                  </label>
                </fieldset>
                <!-- Grund über DkField (Muster wie Datensicherung.vue): Label,
                     Pflichtzeichen und Fehler aus EINER Quelle. -->
                <DkField
                  v-slot="feld"
                  :label="grundPflicht(wahl[m.name]) ? 'Grund' : 'Grund (freiwillig)'"
                  :required="grundPflicht(wahl[m.name])"
                  :maxlength="FREITEXT_MAX"
                  :wert="grund[m.name]"
                  @update:wert="grund = { ...grund, [m.name]: $event }"
                >
                  <textarea v-bind="feld.feldProps" class="dk-mpanel-text" rows="2"></textarea>
                </DkField>
                <p class="dk-mpanel-hinweis">{{ HINWEIS_ENTSCHEIDUNG }}</p>
                <p v-if="zeilenFehler[m.name]" class="dk-mpanel-fehler" role="alert">{{ zeilenFehler[m.name] }}</p>
                <div class="dk-mpanel-aktionen">
                  <DkButton
                    variant="primary"
                    :loading="laeuft[m.name] === true"
                    :disabled="!wahl[m.name]"
                    @click="entscheiden(m)"
                  >{{ wahl[m.name] ? entscheidungLabel(wahl[m.name]) : 'Entscheidung wählen' }}</DkButton>
                </div>
              </div>
            </template>
            <p v-else class="dk-mpanel-hinweis">
              {{ m.standText }}
              <template v-if="m.bearbeitetText"> · entschieden am {{ m.bearbeitetText }}</template>
              <template v-if="m.entscheidung_grund"> · Grund: {{ m.entscheidung_grund }}</template>
            </p>
          </div>
        </li>
      </ul>
    </template>
  </section>
</template>

<script setup>
/**
 * ChatMeldungen — der Reiter „Chat“ in „Zu prüfen“ (CHAT-6-UI).
 *
 * WAS HIER STEHT
 * Die Liste der Meldungen, die DIESE Person moderieren darf, kommt vom Server
 * (`meldungen_liste`), aufklappbar mit dem gemeldeten Ausschnitt (die
 * Nachricht + die fünf davor — beides aus DERSELBEN Antwort) und den
 * Entscheidungen (`meldung_entscheiden`). Erledigte Meldungen stehen im
 * zweiten Abschnitt.
 *
 * WAS HIER NICHT STEHT
 * Rechtelogik. 403 heißt „keine Moderationsrechte“ — dann zeigt die
 * Elternseite den Reiter nicht und diese Komponente wird gar nicht erst
 * eingebunden. Ein Name der meldenden Person erscheint nur, wenn der Server
 * ihn liefert (`melder`), nie geraten.
 *
 * Diese Komponente SENDET nichts selbst: sie meldet `entschieden` an die
 * Seite, die den Aufruf macht (und die Antwort zurückgibt). So bleibt die
 * Liste eine Anzeige der Server-Wahrheit.
 */
import { computed, ref } from 'vue'
import DkButton from '../ui/DkButton.vue'
import DkEmpty from '../ui/DkEmpty.vue'
import DkField from '../ui/DkField.vue'
import DkSkelett from '../ui/DkSkelett.vue'
import DkFilterChips from '../ui/DkFilterChips.vue'
import { serverZeitText } from '../../../shared/zeit.mjs'
import {
  ENTSCHEIDUNGEN, FREITEXT_MAX, TEXTE, ausschnitt, entscheidungLabel, entscheidungPruefen,
  grundPflicht,
} from './meldung.mjs'

/* Grundsatz, der bei jeder Entscheidung steht (Konzept 2.5). */
const HINWEIS_ENTSCHEIDUNG =
  'Entfernst du die Nachricht, nimmt sie aus dem Verlauf und die verfassende Person bekommt einen Hinweis. '
  + 'Weist du die Meldung zurück, bleibt die Nachricht stehen.'

const props = defineProps({
  /** Zeilen aus `meldungZeilen(meldungen_liste)` — der Server ist die Quelle. */
  zeilen: { type: Array, default: () => [] },
  /** Läuft gerade ein Abruf? */
  laedt: { type: Boolean, default: false },
  /** Fehler des Abrufs in Klartext ('' = keiner). */
  ladeFehler: { type: String, default: '' },
  /**
   * Wurden die erledigten Meldungen schon geholt? Der Server filtert HART auf
   * `stand` — die erledigten sind ein EIGENER Abruf. Die Seite hält den
   * Zustand; hier wird nur gemeldet, wann sie gebraucht werden.
   */
  erledigtGeladen: { type: Boolean, default: false },
})

const emit = defineEmits(['entschieden', 'erledigte-anfordern'])

/** Gewählter Stand: offen (Arbeitsliste) oder erledigt. */
const filter = ref('offen')
/** Ist der Abschnitt „Erledigte“ unter der offenen Liste aufgeklappt? */
const erledigtOffen = ref(false)
/** Welche Meldung ist aufgeklappt (genau eine — eine Arbeitsliste bleibt ruhig). */
const offeneZeile = ref('')
/** Entscheidung je Meldung (`name` → 'entfernen' | 'verwerfen'). */
const wahl = ref({})
/** Grund je Meldung (`name` → Text). */
const grund = ref({})
/** Fehler je Meldung (Prüfung des Formulars ODER Text des Servers). */
const zeilenFehler = ref({})
/** Läuft gerade eine Entscheidung für diese Meldung? */
const laeuft = ref({})

const mitZeit = (m) => ({
  ...m,
  erstelltAmText: serverZeitText(m.erstellt_am),
  bearbeitetText: serverZeitText(m.bearbeitet_am),
  melderText: String(m.melder || '').trim(),
  ausschnitt: ausschnitt(m),
})

const alle = computed(() => (props.zeilen || []).map(mitZeit))
const offene = computed(() => alle.value.filter((m) => m.offen))

/** Welche Zeilen stehen da? Offene Arbeitsliste; erledigte auf Wunsch darunter. */
const sichtbar = computed(() => {
  if (filter.value === 'erledigt') return alle.value.filter((m) => !m.offen)
  const liste = [...offene.value]
  if (erledigtOffen.value) liste.push(...alle.value.filter((m) => !m.offen))
  return liste
})

const filterChips = computed(() => [
  { id: 'offen', label: 'Offen', anzahl: offene.value.length },
  { id: 'erledigt', label: TEXTE.erledigtTitel, anzahl: alle.value.filter((m) => !m.offen).length },
])

/**
 * Der zweite Abschnitt („Erledigte Meldungen“) wurde geöffnet oder der Filter
 * auf „erledigt“ gewechselt: die Seite holt dann die Stände `erledigt` und
 * `verworfen` — einmal, nicht bei jedem Klick.
 */
function filterWaehlen(wert) {
  filter.value = String(wert || 'offen')
  if (filter.value !== 'offen' && !props.erledigtGeladen) emit('erledigte-anfordern')
}

function erledigtUmschalten() {
  erledigtOffen.value = !erledigtOffen.value
  if (erledigtOffen.value && !props.erledigtGeladen) emit('erledigte-anfordern')
}

function umschalten(name) {
  offeneZeile.value = offeneZeile.value === name ? '' : String(name)
  // KEINE Vorauswahl (Review CHAT-6 R1): die Entscheidung fällt die Person
  // bewusst — der Knopf ist erst nach einer Wahl aktiv. Eine vorbelegte
  // „Entfernen“-Wahl würde beim Aufklappen schon eine Entscheidung nahelegen.
}

function zeitVon(wert) {
  return serverZeitText(wert)
}

/** Fehler einer Zeile setzen (null = löschen). */
function fehlerSetzen(name, text) {
  const kennung = String(name)
  zeilenFehler.value = { ...zeilenFehler.value, [kennung]: text || '' }
}

/**
 * Entscheiden — prüft nur die BEDIENUNG (Entscheidung gewählt, Grund beim
 * Entfernen), dann meldet sie den Auftrag an die Seite.
 */
function entscheiden(zeile) {
  if (!zeile || laeuft.value[zeile.name] === true) return
  const geprueft = entscheidungPruefen({
    entscheidung: wahl.value[zeile.name] || '',
    grund: grund.value[zeile.name] || '',
  })
  if (!geprueft.ok) {
    fehlerSetzen(zeile.name, geprueft.fehler)
    return
  }
  fehlerSetzen(zeile.name, null)
  laeuft.value = { ...laeuft.value, [zeile.name]: true }
  emit('entschieden', {
    meldung: zeile.name,
    entscheidung: geprueft.entscheidung,
    grund: geprueft.grund,
  })
}

/**
 * Die Seite meldet zurück, dass der Auftrag beantwortet ist (Erfolg oder
 * Fehler) — der Ladezustand der Zeile endet IMMER.
 */
function auftragBeendet(name, fehlerText = '') {
  const kennung = String(name)
  laeuft.value = { ...laeuft.value, [kennung]: false }
  fehlerSetzen(kennung, fehlerText)
}

/** Stand für den Node-Test (kein Betriebsweg). */
defineExpose({
  filter, erledigtOffen, offeneZeile, wahl, grund, laeuft, zeilenFehler,
  umschalten, entscheiden, auftragBeendet, sichtbar, offene,
  filterWaehlen, erledigtUmschalten,
})
</script>

<style scoped>
.dk-mpanel {
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
}
.dk-mpanel-wechsler {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  flex-wrap: wrap;
}
.dk-mpanel-liste {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
}
.dk-mpanel-eintrag {
  border: var(--rahmen-breite) solid var(--rahmen-farbe);
  border-radius: var(--radius);
  background: var(--surface);
  padding: var(--sp-3);
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
}
.dk-mpanel-kopf {
  display: flex;
  align-items: flex-start;
  gap: var(--sp-3);
  justify-content: space-between;
  flex-wrap: wrap;
}
.dk-mpanel-kopftext { min-width: 0; display: flex; flex-direction: column; gap: var(--sp-1); }
.dk-mpanel-titel {
  margin: 0;
  font-size: var(--fs-14);
  font-weight: var(--fw-fett);
  color: var(--text);
}
.dk-mpanel-meta,
.dk-mpanel-melder,
.dk-mpanel-freitext,
.dk-mpanel-hinweis {
  margin: 0;
  font-size: var(--fs-12);
  color: var(--dk-text-muted);
  line-height: var(--lh-text);
}
.dk-mpanel-grund { color: var(--text); font-weight: var(--fw-mittel); }
.dk-mpanel-zeit { font-variant-numeric: var(--fs-tabular); }
.dk-mpanel-freitext {
  font-size: var(--fs-14);
  color: var(--text);
  border-left: var(--rahmen-breite) solid var(--line-strong);
  padding-left: var(--sp-2);
}
.dk-mpanel-auszug {
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
  border-top: var(--rahmen-breite) solid var(--rahmen-farbe);
  padding-top: var(--sp-3);
}
.dk-mpanel-verlauf {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--sp-1);
}
.dk-mpanel-zeile {
  display: flex;
  flex-direction: column;
  gap: calc(var(--sp-1) / 2);
  padding: var(--sp-1) var(--sp-2);
  border-radius: var(--radius-sm);
  font-size: var(--fs-12);
  color: var(--dk-text-muted);
}
/* Die GEMELDETE Nachricht ist hervorgehoben — sie ist der Anlass. */
.dk-mpanel-zeile.is-gemeldet {
  background: var(--accent-soft);
  border-left: var(--rahmen-breite) solid var(--accent);
  color: var(--text);
  font-size: var(--fs-14);
}
.dk-mpanel-zeile-kopf {
  display: flex;
  gap: var(--sp-2);
  align-items: baseline;
  flex-wrap: wrap;
}
.dk-mpanel-zeile-autor { font-weight: var(--fw-mittel); }
.dk-mpanel-zeile-zeit,
.dk-mpanel-zeile-marke { font-size: var(--fs-12); font-variant-numeric: var(--fs-tabular); }
.dk-mpanel-zeile-marke { color: var(--accent); font-weight: var(--fw-fett); }
.dk-mpanel-zeile-text { white-space: pre-line; overflow-wrap: anywhere; }
.dk-mpanel-entscheidung {
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
}
.dk-mpanel-wahl {
  margin: 0;
  padding: 0;
  border: none;
  display: flex;
  flex-direction: column;
  gap: var(--sp-1);
}
.dk-mpanel-label {
  display: block;
  margin: 0 0 var(--sp-1);
  padding: 0;
  font-size: var(--fs-14);
  font-weight: var(--fw-mittel);
  color: var(--text);
}
/* K4: Wahlen sind am Finger mindestens 44 px hoch — `--control-h` ist am
   groben Zeiger 44 px (tokens.css), also kein eigener fester Wert. */
.dk-mpanel-wahlzeile {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  min-height: var(--control-h);
  padding: 0 var(--sp-2);
  border-radius: var(--radius-sm);
  font-size: var(--fs-14);
  color: var(--text);
  cursor: pointer;
}
.dk-mpanel-wahlzeile:hover { background: var(--surface-hover); }
.dk-mpanel-wahlzeile:focus-within { outline: var(--rahmen-breite) solid var(--focus-ring); outline-offset: var(--rahmen-breite); }
.dk-mpanel-text {
  width: 100%;
  box-sizing: border-box;
  padding: var(--sp-2) var(--sp-3);
  border: var(--rahmen-breite) solid var(--rahmen-farbe);
  border-radius: var(--radius);
  background: var(--surface);
  color: var(--text);
  font: inherit;
  font-size: var(--fs-14);
  line-height: var(--lh-text);
  resize: vertical;
}
.dk-mpanel-text:focus-visible { outline: var(--rahmen-breite) solid var(--focus-ring); outline-offset: var(--rahmen-breite); }
.dk-mpanel-aktionen { display: flex; gap: var(--sp-2); flex-wrap: wrap; }
.dk-mpanel-fehler { margin: 0; font-size: var(--fs-14); color: var(--err); }
</style>
