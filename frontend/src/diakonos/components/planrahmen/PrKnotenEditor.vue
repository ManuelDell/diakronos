<template>
  <div class="pr-kn" :class="{ 'pr-kn--tief': tiefe > 0 }">
    <div class="pr-kn-kopf">
      <select class="dk-form-select pr-kn-wahl" :value="schluessel" aria-label="Art des Kriteriums" @change="wechseln($event.target.value)">
        <option v-for="o in optionen" :key="o.wert" :value="o.wert">{{ o.name }}</option>
      </select>
      <span v-if="anzeigeText && !istVerbinder && schluessel !== 'nicht'" class="pr-kn-text">{{ anzeigeText }}</span>
      <button v-if="entfernbar" type="button" class="dk-btn dk-btn-ghost dk-btn-sm" aria-label="Kriterium entfernen" @click="$emit('entfernen')">✕</button>
    </div>

    <!-- Verbinder: UND / ODER mit kindlichen Kriterien -->
    <div v-if="istVerbinder" class="pr-kn-kinder">
      <PrKnotenEditor
        v-for="(k, i) in kinder" :key="i"
        :modus="modus" :knoten="k" :kontext="kontext" :tiefe="tiefe + 1" :entfernbar="true"
        @update="kinder[i] = $event" @entfernen="kinder.splice(i, 1)"
      />
      <button type="button" class="dk-btn dk-btn-ghost dk-btn-sm" @click="kinder.push(leerenKnoten(modus))">+ Kriterium anlegen</button>
    </div>

    <!-- Negation mit genau einem Kriterium -->
    <div v-else-if="schluessel === 'nicht'" class="pr-kn-kinder">
      <PrKnotenEditor
        :modus="modus" :knoten="kind" :kontext="kontext" :tiefe="tiefe + 1" :entfernbar="false"
        @update="knoten.nicht = $event"
      />
    </div>

    <!-- Blätter -->
    <template v-else>
      <select
        v-if="typ === 'wochentage'" multiple size="4"
        class="dk-form-select" :value="knoten.wochentag || []"
        aria-label="Wochentage wählen" @change="wochentageSetzen($event.target)"
      >
        <option v-for="w in WOCHENTAGE" :key="w.kuerzel" :value="w.kuerzel">{{ w.name }}</option>
      </select>
      <div v-else-if="typ === 'parameter'" class="pr-kn-zeile">
        <PrAuswahl
          :model-value="parameterId" :optionen="parameterAuswahl" platzhalter="— Parameter wählen —"
          aria-label="Parameter" anderer-wert @update:model-value="parameterSetzen('id', $event)"
        />
        <!-- UX-C3b: Bei einem Auswahl-Parameter ist der Vergleichswert einer
             seiner Werte — Auswahl statt Freitext. -->
        <PrAuswahl
          v-if="parameterWerte.length" :model-value="gleichWert" :optionen="wertAuswahl"
          platzhalter="— Wert wählen —" aria-label="Gewünschter Wert"
          :unbekannt-name="'unbekannter Auswahlwert'" anderer-wert
          @update:model-value="parameterSetzen('gleich', $event)"
        />
        <input
          v-else
          class="dk-form-input" type="text" placeholder="gleicher Wert"
          :value="gleichWert" aria-label="Gewünschter Wert"
          @input="parameterSetzen('gleich', $event.target.value)"
        />
      </div>
      <label v-else-if="typ === 'termin_nr'" class="pr-kn-zeile pr-kn-satz">
        Jeder <input type="number" min="2" class="dk-form-input pr-kn-zahl" :value="jede" @change="terminNrSetzen($event.target.value)" /> -te Termin
      </label>
      <input
        v-else-if="typ === 'zahl'" type="number" class="dk-form-input"
        :value="knoten[schluessel]" aria-label="Zahl"
        @input="wertSetzen($event.target.value === '' ? null : Number($event.target.value))"
      />
      <input
        v-else-if="typ === 'datum'" type="date" class="dk-form-input"
        :value="knoten[schluessel]" aria-label="Datum"
        @change="wertSetzen($event.target.value)"
      />
      <!-- UX-C3b: Werte, die exakt passen müssen, sind Auswahllisten; ein
           gespeicherter Altwert bleibt als „unbekannter Wert“ sichtbar.
           „Anderer Wert …“ lässt neue Kennungen zu (Review Punkt 2). -->
      <PrAuswahl
        v-else-if="auswahlQuelle" :model-value="knoten[schluessel]" :optionen="auswahlQuelle.optionen"
        :platzhalter="auswahlQuelle.platzhalter" :unbekannt-name="auswahlQuelle.unbekanntName"
        :warnung="auswahlQuelle.warnung" :aria-label="wertName" :info="auswahlQuelle.info"
        anderer-wert
        @update:model-value="wertSetzen($event)"
      />
      <input
        v-else type="text" class="dk-form-input"
        :value="knoten[schluessel]" :placeholder="platzhalter"
        @input="wertSetzen($event.target.value)"
      />
    </template>
  </div>
</template>

<script setup>
/**
 * Baukasten für strukturierte Knoten — gleiche Grammatik für Rollenfilter
 * (modus 'rolle': merkmal/gruppe/anmeldung/person) und Feld-Bedingungen
 * (modus 'bedingung': anlass/wochentag/variante/…). Verknüpft wird mit
 * 'alle' (UND), 'eine' (ODER) und 'nicht' — es gibt nie einen freien
 * Ausdrucks-String. Die Knoten werden IN PLACE verändert (Referenz bleibt),
 * damit tiefe Bäume im Plantyp-Editor reaktiv同步 bleiben.
 */
import { computed } from 'vue'
import PrAuswahl from './PrAuswahl.vue'
import { WOCHENTAGE, ROLLEN_KNOTEN, BEDINGUNGS_KNOTEN, leerenKnoten, knotenSchluessel, feldPfadListe } from './editor.mjs'
import {
  anlassOptionen, feldPfadOptionen, gruppenOptionen, option,
  personenMerkmalOptionen, sammlungOptionen, varianteOptionen,
} from './auswahl.mjs'

const props = defineProps({
  knoten: { type: Object, required: true },
  modus: { type: String, default: 'rolle' },   // 'rolle' | 'bedingung'
  kontext: { type: Object, default: () => ({}) }, // {anlaesse, parameter, feldPfade, varianteIds}
  tiefe: { type: Number, default: 0 },
  entfernbar: { type: Boolean, default: false },
})
defineEmits(['update', 'entfernen'])

const VERBINDER = [
  { wert: 'alle', name: 'UND — alle Kriterien müssen zutreffen' },
  { wert: 'eine', name: 'ODER — mindestens eines muss zutreffen' },
  { wert: 'nicht', name: 'NICHT — Negation' },
]

const optionen = computed(() => {
  const blaetter = props.modus === 'bedingung' ? BEDINGUNGS_KNOTEN : ROLLEN_KNOTEN
  return [...VERBINDER, ...blaetter]
})

const schluessel = computed(() => knotenSchluessel(props.knoten) || (props.modus === 'bedingung' ? 'anlass' : 'merkmal'))
const istVerbinder = computed(() => ['alle', 'eine'].includes(schluessel.value))
const typ = computed(() => {
  const treffer = optionen.value.find((o) => o.wert === schluessel.value)
  return treffer?.typ || 'text'
})
const platzhalter = computed(() => {
  const treffer = optionen.value.find((o) => o.wert === schluessel.value)
  return treffer ? treffer.name : ''
})
const wertName = computed(() => {
  const treffer = optionen.value.find((o) => o.wert === schluessel.value)
  return treffer ? treffer.name : 'Wert'
})
const anzeigeText = computed(() => {
  const key = schluessel.value
  if (!['alle', 'eine', 'nicht'].includes(key)) return ''
  return { alle: 'alles zusammen', eine: 'eines davon', nicht: 'gilt nicht' }[key]
})

const kinder = computed(() => {
  const key = schluessel.value
  if (!Array.isArray(props.knoten[key])) props.knoten[key] = []
  return props.knoten[key]
})

// ── UX-C3b: Auswahllisten für Kennungs-Werte ──────────────────────────────

const definition = computed(() => props.kontext?.definition || {})
const parameterAuswahl = computed(() => (props.kontext?.parameter || [])
  .filter((p) => p && p.id)
  .map((p) => option(p.id, p.name ? `${p.name} (${p.id})` : p.id)))

/** Werte eines Auswahl-Parameters (Vergleichswert der Bedingung). */
const parameterWerte = computed(() => {
  const treffer = (props.kontext?.parameter || []).find((p) => p?.id === parameterId.value)
  return Array.isArray(treffer?.werte) ? treffer.werte : []
})
const wertAuswahl = computed(() => parameterWerte.value.map((w) => option(w, w)))

/**
 * Quellen der Blattwerte, die eine Kennung referenzieren. Für alle anderen
 * (freier Text, Zahl, Datum) bleibt es beim Eingabefeld — dort ist der Text
 * wirklich frei (Vorname, Thema …).
 */
const auswahlQuelle = computed(() => {
  const key = schluessel.value
  const def = definition.value
  const bauen = (optionen, platzhalter, unbekanntName, info) => {
    if (!optionen.length) return null
    return { optionen, platzhalter, unbekanntName, warnung: '', info: info || '' }
  }
  if (key === 'anlass') return bauen(anlassOptionen(def), '— Anlass wählen —', 'unbekannter Anlass', 'anlasswert')
  if (key === 'variante') return bauen(varianteOptionen(def), '— Variante wählen —', 'unbekannte Variante', 'variante')
  if (key === 'feld_gesetzt') {
    return bauen(feldPfadOptionen(def, feldPfadListe), '— Feld wählen —', 'unbekannter Feldpfad')
  }
  if (props.modus !== 'bedingung') {
    // Rollenfilter: merkmal/gruppe/anmeldung/person
    if (key === 'merkmal') {
      const optionen = [...personenMerkmalOptionen(def), ...sammlungMerkmale(def)]
      return bauen(optionen, '— Angabe wählen —', 'unbekannte Angabe')
    }
    if (key === 'gruppe') return bauen(gruppenOptionen(props.kontext?.gruppen), '— Gruppe wählen —', 'unbekannte Gruppe')
    if (key === 'anmeldung') {
      const optionen = sammlungOptionen(def).map((o) => option(o.wert, o.text))
      return bauen(optionen, '— Liste wählen —', 'unbekannte Liste', 'eingebaute_liste')
    }
    if (key === 'person') return null // Personen sind kein Katalog des Editors
  }
  return null
})

/** Merkmale eigener Sammlungen — für Sammlungs-Filter („lieder: thema“). */
function sammlungMerkmale(def) {
  const liste = []
  const merkmale = def?.merkmale && typeof def.merkmale === 'object' ? def.merkmale : {}
  for (const [ziel, gruppe] of Object.entries(merkmale)) {
    if (ziel === 'person' || !Array.isArray(gruppe)) continue
    for (const m of gruppe) {
      if (!m?.id) continue
      liste.push(option(`${ziel}:${m.id}`, m.name ? `${ziel}:${m.id} — ${m.name}` : `${ziel}:${m.id}`))
    }
  }
  return liste
}

const kind = computed(() => {
  if (!props.knoten.nicht || typeof props.knoten.nicht !== 'object') props.knoten.nicht = leerenKnoten(props.modus)
  return props.knoten.nicht
})

const parameterId = computed(() => props.knoten.parameter?.id || '')
const gleichWert = computed(() => props.knoten.parameter?.gleich ?? '')
const jede = computed(() => props.knoten.termin_nr?.jede ?? 2)

/** Inhalt eines Knotens leeren und neu setzen (Referenz bleibt erhalten). */
function knotenInhaltSetzen(neu) {
  for (const k of Object.keys(props.knoten)) delete props.knoten[k]
  Object.assign(props.knoten, neu)
}

function wechseln(neu) { knotenInhaltSetzen(leerenKnoten(props.modus, neu)) }
function wertSetzen(wert) { props.knoten[schluessel.value] = wert }

function wochentageSetzen(el) {
  const gewaehlt = Array.from(el.selectedOptions).map((o) => o.value)
  props.knoten.wochentag = gewaehlt.length ? gewaehlt : ['so']
}

function parameterSetzen(feld, wert) {
  if (!props.knoten.parameter || typeof props.knoten.parameter !== 'object') props.knoten.parameter = { id: '', gleich: '' }
  // UX-C3b: Ein Wert, den die Liste nicht kennt, wird als „unbekannter Wert“
  // angezeigt. Bei einem gewechselten Parameter ist der alte Vergleichswert
  // ohnehin erledigt — er darf nicht als Leiche mitgeschleppt werden.
  if (feld === 'id' && wert !== props.knoten.parameter.id) props.knoten.parameter.gleich = ''
  props.knoten.parameter[feld] = wert
}

function terminNrSetzen(wert) {
  const zahl = Math.max(2, Math.floor(Number(wert) || 2))
  props.knoten.termin_nr = { jede: zahl }
}
</script>

<style scoped>
.pr-kn { display: flex; flex-direction: column; gap: 6px; padding: 8px 10px; border: 1px solid var(--dk-border); border-radius: 10px; background: var(--dk-surface); min-width: 0; }
.pr-kn--tief { background: var(--dk-surface-2); }
.pr-kn-kopf { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.pr-kn-wahl { max-width: 320px; }
.pr-kn-text { font-size: var(--fs-12); color: var(--dk-text-muted); font-style: italic; }
.pr-kn-kinder { display: flex; flex-direction: column; gap: 6px; padding-left: 12px; border-left: 2px solid var(--dk-border); }
.pr-kn-zeile { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.pr-kn-satz { font-size: var(--fs-14); color: var(--dk-text); }
.pr-kn-zahl { max-width: 90px; }
</style>
