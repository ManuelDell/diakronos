<template>
  <div class="pr-te">
    <!-- Abgeleitete Reihe -->
    <template v-if="abgeleitet">
      <p class="pr-te-hinweis">
        Diese Termine leiten sich aus einer anderen Reihe ab — z. B. die Probe zwei Tage vor dem Gottesdienst.
        Ändert sich der Ursprungstermin, zieht diese Reihe automatisch nach.
      </p>
      <div class="pr-te-zeile">
        <label class="pr-te-label">Herkunft
          <select v-model="abgeleitet.von" class="dk-form-select">
            <option v-for="r in reihenIds" :key="r" :value="r">{{ r === 'standard' ? 'Hauptreihe' : r }}</option>
          </select>
        </label>
        <label class="pr-te-label">Versatz
          <span class="pr-te-versatz">
            <select v-model="versatzAngaben.signum" class="dk-form-select pr-te-klein" aria-label="Richtung" @change="versatzSchreiben">
              <option value="-">vorher</option>
              <option value="+">nachher</option>
            </select>
            <input type="number" min="0" class="dk-form-input pr-te-klein2" :value="versatzAngaben.zahl" aria-label="Anzahl" @change="versatzAngaben.zahl = $event.target.value; versatzSchreiben()" />
            <select v-model="versatzAngaben.einheit" class="dk-form-select pr-te-klein" aria-label="Einheit" @change="versatzSchreiben">
              <option value="T">Tage</option>
              <option value="W">Wochen</option>
              <option value="h">Stunden</option>
              <option value="min">Minuten</option>
            </select>
          </span>
        </label>
      </div>
      <p class="pr-te-vorschau">{{ versatzText(termine.abgeleitet?.versatz) }}</p>
      <PrKnotenEditor v-if="istKnoten(abgeleitet.nur_wenn)" :knoten="abgeleitet.nur_wenn" modus="bedingung" :kontext="kontext" />
      <div class="pr-te-zeile">
        <button v-if="!istKnoten(abgeleitet.nur_wenn)" type="button" class="dk-btn dk-btn-ghost dk-btn-sm" @click="abgeleitet.nur_wenn = { anlass: '' }">+ Nur unter Bedingung ableiten (z. B. nicht an Feiertagen)</button>
        <button v-else type="button" class="dk-btn dk-btn-ghost dk-btn-sm" @click="delete abgeleitet.nur_wenn">Bedingung entfernen</button>
      </div>
      <PrPfadMeldungen :meldungen="meldungen" :pfad="pfadZu('abgeleitet')" />
    </template>

    <!-- Eigenständige Zeitachse -->
    <template v-else>
      <div class="pr-te-zeile">
        <label class="pr-te-label">Wiederholung
          <span class="pr-te-wiederholung">
            <select v-model="frequenz" class="dk-form-select" aria-label="Wie oft?" @change="regelSchreiben">
              <option value="weekly">wöchentlich</option>
              <option value="daily">täglich</option>
              <option value="monthly">monatlich</option>
              <option value="yearly">jährlich</option>
            </select>
            <select v-if="frequenz === 'weekly'" v-model="tage" multiple size="4" class="dk-form-select" aria-label="Wochentage" @change="regelSchreiben">
              <option v-for="w in WOCHENTAGE" :key="w.kuerzel" :value="w.kuerzel">{{ w.name }}</option>
            </select>
          </span>
        </label>
        <label class="pr-te-label">Uhrzeit
          <input v-model="termine.uhrzeit" type="time" class="dk-form-input pr-te-zeit" aria-label="Uhrzeit" />
        </label>
      </div>
      <PrPfadMeldungen :meldungen="meldungen" :pfad="pfadZu('uhrzeit')" />
      <p class="pr-te-vorschau">Ergebnis: <strong>{{ wiederholungText(termine.regel) || 'keine Wiederholung — nur manuelle Termine' }}</strong></p>
      <details class="pr-te-details">
        <summary>Wiederholung als RRULE angeben (Fortgeschrittene)</summary>
        <input v-model="termine.regel" type="text" class="dk-form-input" placeholder="FREQ=WEEKLY;BYDAY=SU" aria-label="RRULE" />
      </details>
      <PrPfadMeldungen :meldungen="meldungen" :pfad="pfadZu('regel')" />

      <div class="pr-te-zeile">
        <label class="pr-te-label">Zeitraum von
          <span class="pr-te-ref">
            <select v-model="vonModus" class="dk-form-select pr-te-klein" aria-label="Art" @change="vonSchreiben">
              <option value="datum">Datum</option>
              <option value="parameter">Planparameter</option>
            </select>
            <input v-if="vonModus === 'datum'" v-model="vonDatum" type="date" class="dk-form-input" aria-label="Anfang" @change="vonSchreiben" />
            <select v-else v-model="vonParameter" class="dk-form-select" aria-label="Parameter" @change="vonSchreiben">
              <option value="">— Parameter —</option>
              <option v-for="p in kontext.parameter || []" :key="p.id" :value="p.id">{{ p.name || p.id }}</option>
            </select>
          </span>
        </label>
        <label class="pr-te-label">Zeitraum bis
          <span class="pr-te-ref">
            <select v-model="bisModus" class="dk-form-select pr-te-klein" aria-label="Art" @change="bisSchreiben">
              <option value="datum">Datum</option>
              <option value="parameter">Planparameter</option>
            </select>
            <input v-if="bisModus === 'datum'" v-model="bisDatum" type="date" class="dk-form-input" aria-label="Ende" @change="bisSchreiben" />
            <select v-else v-model="bisParameter" class="dk-form-select" aria-label="Parameter" @change="bisSchreiben">
              <option value="">— Parameter —</option>
              <option v-for="p in kontext.parameter || []" :key="p.id" :value="p.id">{{ p.name || p.id }}</option>
            </select>
          </span>
        </label>
      </div>

      <!-- Freizeit-artiger Zeitraum: jeder Tag zwischen zwei Daten -->
      <PrPfadMeldungen :meldungen="meldungen" :pfad="pfadZu('von')" />
      <PrPfadMeldungen :meldungen="meldungen" :pfad="pfadZu('bis')" />
      <details class="pr-te-details" :open="!!termine.zeitraum">
        <summary>Jeder Tag zwischen zwei Daten (Freizeit, Camp)</summary>
        <label class="pr-te-label">Welcher Plan-Parameter liefert den Zeitraum?
          <select class="dk-form-select" :value="zeitraumWert" @change="zeitRaumSetzen($event.target.value)">
            <option value="">— keiner, nur feste Termine —</option>
            <option v-for="p in zeitraumParameter" :key="p.id" :value="p.id">{{ p.name || p.id }}</option>
          </select>
        </label>
        <label class="pr-te-label">Nur diese Wochentage einschließen (ohne = jeder Tag)
          <span class="pr-te-tage">
            <label v-for="w in WOCHENTAGE" :key="w.kuerzel" class="pr-te-schalter">
              <input type="checkbox" :checked="wochentagEnthalten(w.kuerzel)" @change="wochentagToggle(w.kuerzel, $event.target.checked)" />
              {{ w.name }}
            </label>
          </span>
        </label>
        <PrPfadMeldungen :meldungen="meldungen" :pfad="pfadZu('wochentage')" />
      </details>

      <PrPfadMeldungen :meldungen="meldungen" :pfad="pfadZu('zeitraum')" />
      <!-- Kalender -->
      <details class="pr-te-details" :open="!!termine.kalender">
        <summary>Termine aus dem Gemeinde-Kalender übernehmen</summary>
        <div class="pr-te-zeile">
          <label class="pr-te-label">Kategorie
            <input v-model="kalenderKategorie" type="text" class="dk-form-input" placeholder="z. B. Gottesdienste" @change="kalenderSchreiben" />
          </label>
          <label class="pr-te-label">Gruppe
            <input v-model="kalenderGruppe" type="text" class="dk-form-input" placeholder="z. B. Proben" @change="kalenderSchreiben" />
          </label>
        </div>
      </details>

      <PrPfadMeldungen :meldungen="meldungen" :pfad="pfadZu('kalender')" />
      <PrPfadMeldungen :meldungen="meldungen" :pfad="pfadZu('feiertage')" />
      <!-- Feiertage -->
      <div class="pr-te-feiertage">
        <h5 class="pr-te-titel">Feiertage als Termine</h5>
        <p class="pr-te-hinweis">Jeder ausgewählte Feiertag wird Termin und setzt zugleich einen Anlass gleichen Namens.</p>
        <label v-for="f in feiertage" :key="f.schluessel" class="pr-te-schalter">
          <input type="checkbox" :checked="feiertagEnthalten(f.schluessel)" @change="feiertagToggle(f.schluessel, $event.target.checked)" />
          {{ f.name }}
        </label>
        <label class="pr-te-label pr-te-eigener">Eigener Feiertags-Schlüssel
          <input v-model="eigenerFeiertag" type="text" class="dk-form-input" placeholder="osterdienstag" @keydown.enter.prevent="eigenerFeiertagHinzufuegen" />
        </label>
        <button type="button" class="dk-btn dk-btn-ghost dk-btn-sm" :disabled="!eigenerFeiertag.trim()" @click="eigenerFeiertagHinzufuegen">Feiertag hinzufügen</button>
        <div v-for="k in eigeneFeiertage" :key="k" class="pr-te-zeile">
          <span>{{ k }}</span>
          <button type="button" class="dk-btn dk-btn-ghost dk-btn-sm" :aria-label="'Feiertag ' + k + ' entfernen'" @click="feiertagToggle(k, false)">Entfernen</button>
        </div>
      </div>

      <!-- Ausnahmen -->
      <div class="pr-te-ausnahmen">
        <h5 class="pr-te-titel">Ausnahmen — Termine, die entfallen</h5>
        <label class="pr-te-schalter pr-te-schalter--gross">
          <input type="checkbox" :checked="feiertagsAusnahme" @change="ausnahmeModus($event.target.checked ? 'feiertage' : 'keine')" />
          Die ganze Reihe fällt an Feiertagen aus (z. B. keine Probe am Heiligabend)
        </label>
        <div v-for="(a, ai) in ausnahmenListe" :key="ai" class="pr-te-zeile">
          <input v-model="a.datum" type="date" class="dk-form-input" aria-label="Entfallendes Datum" />
          <input v-model="a.grund" type="text" class="dk-form-input" placeholder="Grund (optional)" aria-label="Grund" />
          <button type="button" class="dk-btn dk-btn-ghost dk-btn-sm" aria-label="Ausnahme entfernen" @click="ausnahmenListe.splice(ai, 1)">✕</button>
          <PrPfadMeldungen :meldungen="meldungen" :pfad="pfadZu('ausnahmen/' + ai)" />
        </div>
        <button type="button" class="dk-btn dk-btn-ghost dk-btn-sm" @click="ausnahmeHinzufuegen">+ Einzelnen Termin entfallen lassen</button>
      </div>

      <!-- Manuelle Termine -->
      <div class="pr-te-manuell">
        <h5 class="pr-te-titel">Einzelne Termine von Hand</h5>
        <div v-for="(m, mi) in manuelleListe" :key="mi" class="pr-te-zeile">
          <input v-model="m.datum" type="date" class="dk-form-input" aria-label="Datum" />
          <input v-model="m.name" type="text" class="dk-form-input" placeholder="Name (optional)" aria-label="Name" />
          <input v-model="m.uhrzeit" type="time" class="dk-form-input pr-te-zeit" aria-label="Uhrzeit" />
          <select v-model="m.anlaesse" multiple size="3" class="dk-form-select" aria-label="Anlässe">
            <option v-for="a in kontext.anlaesse || []" :key="a.id" :value="a.id">{{ a.name || a.id }}</option>
          </select>
          <button type="button" class="dk-btn dk-btn-ghost dk-btn-sm" aria-label="Termin entfernen" @click="manuelleListe.splice(mi, 1)">✕</button>
          <PrPfadMeldungen :meldungen="meldungen" :pfad="pfadZu('manuell/' + mi)" />
        </div>
        <button type="button" class="dk-btn dk-btn-ghost dk-btn-sm" @click="manuellHinzufuegen">+ Termin hinzufügen</button>
      </div>
    </template>
  </div>
</template>

<script setup>
/**
 * Termine einer Reihe: verständliche Wiederholung („jeden Sonntag“),
 * Uhrzeit, Zeitraum von/bis (Datum oder Planparameter), Freizeit-Zeitraum,
 * Kalenderbezug, Feiertage aus dem Katalog, Ausnahmen und manuelle Termine —
 * sowie abgeleitete Reihen (Versatz + Bedingung). Alles in place.
 */
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import PrKnotenEditor from './PrKnotenEditor.vue'
import PrPfadMeldungen from './PrPfadMeldungen.vue'
import { WOCHENTAGE, FEIERTAGE, rruleAus, rruleLesen, wiederholungText, versatzLesen, versatzAus, versatzText, wertOderRefLesen, wertOderRefAus, feldPruefPfad, alsListe } from './editor.mjs'
import { beiFeiertagskatalog } from './anlaesse.mjs'

const props = defineProps({
  termine: { type: Object, required: true },
  reihenIds: { type: Array, default: () => [] },
  kontext: { type: Object, default: () => ({}) },
  meldungen: { type: Array, default: () => [] },   // Prüfmeldungen (Inline am Pfad)
  basisPfad: { type: String, default: 'termine' }, // JSON-Pointer-Basis dieser Reihe
})

/** Pfad eines Terminbestandteils, z. B. 'regel' → 'terminreihen/1/termine/regel'. */
function pfadZu(teil) { return feldPruefPfad(props.basisPfad, teil) }

const abgeleitet = computed(() => (props.termine.abgeleitet && typeof props.termine.abgeleitet === 'object' ? props.termine.abgeleitet : null))

// ── Wiederholung ──────────────────────────────────────────────────────────

const gelesen = computed(() => rruleLesen(props.termine.regel) || { frequenz: 'weekly', tage: [], intervall: 1 })
const frequenz = ref(gelesen.value.frequenz)
const tage = ref(gelesen.value.tage.slice())
// JSON-Reiter oderVersionswechsel können die Regel ändern — Eingaben nachziehen.
watch(() => props.termine.regel, (neu) => {
  const g = rruleLesen(neu)
  if (g) { frequenz.value = g.frequenz; tage.value = g.tage.slice() }
})
function regelSchreiben() {
  props.termine.regel = rruleAus({ frequenz: frequenz.value, tage: tage.value })
}

// ── Versatz ───────────────────────────────────────────────────────────────

const versatzAngaben = ref(versatzLesen(props.termine.abgeleitet?.versatz) || { signum: '-', zahl: 2, einheit: 'T' })
watch(() => props.termine.abgeleitet?.versatz, (neu) => {
  const g = versatzLesen(neu)
  if (g) versatzAngaben.value = g
})
function versatzSchreiben() {
  if (abgeleitet.value) abgeleitet.value.versatz = versatzAus(versatzAngaben.value)
}

// ── von/bis (Datum oder Parameter) ────────────────────────────────────────

const von = ref(wertOderRefLesen(props.termine.von))
const bis = ref(wertOderRefLesen(props.termine.bis))
const vonModus = ref(von.value.modus), vonDatum = ref(von.value.datum), vonParameter = ref(von.value.wert)
const bisModus = ref(bis.value.modus), bisDatum = ref(bis.value.datum), bisParameter = ref(bis.value.wert)
function vonSchreiben() {
  const wert = wertOderRefAus({ modus: vonModus.value, datum: vonDatum.value, wert: vonParameter.value })
  if (wert) props.termine.von = wert; else delete props.termine.von
}
function bisSchreiben() {
  const wert = wertOderRefAus({ modus: bisModus.value, datum: bisDatum.value, wert: bisParameter.value })
  if (wert) props.termine.bis = wert; else delete props.termine.bis
}

// ── Zeitraum (jeder Tag) ──────────────────────────────────────────────────

const zeitraumParameter = computed(() => alsListe(props.kontext.parameter).filter((p) => p.art === 'zeitraum'))
const zeitraumWert = computed(() => {
  const m = String(props.termine.zeitraum || '').match(/^\{parameter\.([a-z0-9][a-z0-9_-]*)\}$/i)
  return m ? m[1] : ''
})
function zeitRaumSetzen(id) {
  if (id) props.termine.zeitraum = `{parameter.${id}}`
  else delete props.termine.zeitraum
}
function wochentagEnthalten(k) { return alsListe(props.termine.wochentage).includes(k) }
function wochentagToggle(k, an) {
  if (!Array.isArray(props.termine.wochentage)) props.termine.wochentage = []
  const i = props.termine.wochentage.indexOf(k)
  if (an && i === -1) props.termine.wochentage.push(k)
  if (!an && i !== -1) props.termine.wochentage.splice(i, 1)
  if (!props.termine.wochentage.length) delete props.termine.wochentage
}

// ── Kalender ──────────────────────────────────────────────────────────────

const kalenderKategorie = ref(props.termine.kalender?.kategorie || '')
const kalenderGruppe = ref(props.termine.kalender?.gruppe || '')
function kalenderSchreiben() {
  if (kalenderKategorie.value || kalenderGruppe.value) {
    props.termine.kalender = {}
    if (kalenderKategorie.value) props.termine.kalender.kategorie = kalenderKategorie.value
    if (kalenderGruppe.value) props.termine.kalender.gruppe = kalenderGruppe.value
  } else delete props.termine.kalender
}

// ── Feiertage ─────────────────────────────────────────────────────────────

// REST-1: Der Katalog kommt vom Server (`feiertage_holen`, in `usePlanrahmen`
// beim Betreten des Plan-Bereichs). `FEIERTAGE` ist ein einfaches Array und
// damit nicht reaktiv — ein bereits offener Editor blieb auf dem Stand vom
// Öffnen. Diese Kopie wird bei einem neuen Katalog nachgezogen.
const feiertage = ref(FEIERTAGE.map((f) => ({ ...f })))
let katalogAbmelden = null
onMounted(() => {
  katalogAbmelden = beiFeiertagskatalog(() => {
    feiertage.value = FEIERTAGE.map((f) => ({ ...f }))
  })
})
onBeforeUnmount(() => { if (katalogAbmelden) katalogAbmelden() })

const eigenerFeiertag = ref('')
const eigeneFeiertage = computed(() => alsListe(props.termine.feiertage).filter(k => !feiertage.value.some(f => f.schluessel === k)))
function eigenerFeiertagHinzufuegen() {
  const k = eigenerFeiertag.value.trim()
  if (!k) return
  feiertagToggle(k, true)
  eigenerFeiertag.value = ''
}
function feiertagEnthalten(k) { return alsListe(props.termine.feiertage).includes(k) }
function feiertagToggle(k, an) {
  if (!k) return
  if (!Array.isArray(props.termine.feiertage)) props.termine.feiertage = []
  const i = props.termine.feiertage.indexOf(k)
  if (an && i === -1) props.termine.feiertage.push(k)
  if (!an && i !== -1) props.termine.feiertage.splice(i, 1)
  if (!props.termine.feiertage.length) delete props.termine.feiertage
}

// ── Ausnahmen ─────────────────────────────────────────────────────────────

const feiertagsAusnahme = computed(() => !!props.termine.ausnahmen?.feiertage)
const ausnahmenListe = computed(() => (Array.isArray(props.termine.ausnahmen) ? props.termine.ausnahmen : []))
function ausnahmeModus(modus) {
  if (modus === 'feiertage') props.termine.ausnahmen = { feiertage: true }
  else if (modus === 'liste') props.termine.ausnahmen = []
  else delete props.termine.ausnahmen
}
function ausnahmeHinzufuegen() {
  if (!Array.isArray(props.termine.ausnahmen)) props.termine.ausnahmen = []
  props.termine.ausnahmen.push({ datum: '' })
}

// ── Manuelle Termine ──────────────────────────────────────────────────────

const manuelleListe = computed(() => (Array.isArray(props.termine.manuell) ? props.termine.manuell : []))
function manuellHinzufuegen() {
  if (!Array.isArray(props.termine.manuell)) props.termine.manuell = []
  props.termine.manuell.push({ datum: '', anlaesse: [] })
}

/** Ein vorhandener Knoten? Rendern nur bei wahr — nie anlegen. */
function istKnoten(wert) {
  return !!wert && typeof wert === 'object' && !Array.isArray(wert)
}
</script>

<style scoped>
.pr-te { display: flex; flex-direction: column; gap: 12px; min-width: 0; }
.pr-te-zeile { display: flex; gap: 12px; flex-wrap: wrap; align-items: flex-end; }
.pr-te-label { display: flex; flex-direction: column; gap: 4px; font-size: 0.8rem; font-weight: 600; color: var(--dk-text-muted); min-width: 0; }
.pr-te-wiederholung, .pr-te-ref, .pr-te-versatz { display: inline-flex; gap: 6px; align-items: center; }
.pr-te-klein { max-width: 130px; }
.pr-te-klein2 { max-width: 70px; }
.pr-te-zeit { max-width: 130px; }
.pr-te-vorschau { font-size: 0.86rem; color: var(--dk-text); margin: 0; }
.pr-te-vorschau strong { color: var(--dk-brand-800); }
.pr-te-details { font-size: 0.84rem; }
.pr-te-details summary { cursor: pointer; color: var(--dk-text-muted); font-size: 0.8rem; font-weight: 600; }
.pr-te-titel { font-size: 0.74rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: var(--dk-text-muted); margin: 0; }
.pr-te-hinweis { font-size: 0.8rem; color: var(--dk-text-muted); margin: 0; }
.pr-te-feiertage, .pr-te-ausnahmen, .pr-te-manuell { display: flex; flex-direction: column; gap: 8px; border-top: 1px solid var(--dk-divider); padding-top: 10px; }
.pr-te-schalter { display: inline-flex; align-items: center; gap: 5px; font-size: 0.82rem; color: var(--dk-text); cursor: pointer; }
.pr-te-schalter--gross { font-size: 0.86rem; }
.pr-te-tage { display: flex; flex-wrap: wrap; gap: 8px 12px; }
.pr-te-eigener { max-width: 260px; }
</style>
