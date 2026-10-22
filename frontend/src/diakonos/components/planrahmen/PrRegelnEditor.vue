<template>
  <div class="pr-rg">
    <p class="pr-rg-hinweis">
      Regeln sind Bausteine mit Stufe: <strong>muss</strong> wird nie verletzt,
      <strong>sollte</strong> wird möglichst erfüllt (Verstoß wird sichtbar),
      <strong>Hinweis</strong> wird nur angezeigt. Welche Parameter ein Baustein
      akzeptiert, sagt die Registry — das Formular baut sich daraus.
    </p>

    <p v-if="!regeln.length" class="pr-rg-leer">Keine Regeln — der Generator füllt nach Vorgabe (Pflichtfelder zuerst).</p>
    <div v-for="(r, i) in regeln" :key="i" class="pr-rg-karte">
      <div class="pr-rg-zeile">
        <label class="pr-rg-label">Baustein
          <select v-model="r.baustein" class="dk-form-select pr-rg-baustein" @change="bausteinGewechselt(r)">
            <option value="">— bitte wählen —</option>
            <option v-for="(def, name) in bausteine" :key="name" :value="name">{{ name }}</option>
          </select>
        </label>
        <label class="pr-rg-label">Stufe
          <select v-model="r.stufe" class="dk-form-select pr-rg-stufe">
            <option v-for="s in STUFEN" :key="s.wert" :value="s.wert">{{ s.name }}</option>
          </select>
        </label>
        <label class="pr-rg-label">Gewicht
          <input v-model.number="r.gewicht" type="number" step="0.5" min="0" class="dk-form-input pr-rg-zahl" placeholder="optional" />
        </label>
        <button type="button" class="dk-btn dk-btn-ghost dk-btn-sm" aria-label="Regel entfernen" @click="regeln.splice(i, 1)">✕</button>
      </div>
      <PrPfadMeldungen :meldungen="meldungen" :pfad="regelPfad(i) + '/baustein'" />
      <PrPfadMeldungen :meldungen="meldungen" :pfad="regelPfad(i) + '/stufe'" />
      <PrPfadMeldungen :meldungen="meldungen" :pfad="regelPfad(i) + '/gewicht'" />
      <PrPfadMeldungen :meldungen="meldungen" :pfad="regelPfad(i)" exakt />

      <p v-if="beschreibung(r)" class="pr-rg-beschreibung">{{ beschreibung(r) }}</p>

      <div v-for="feld in paramForm(r)" :key="feld.name" class="pr-rg-param">
        <label class="pr-rg-label">
          {{ paramName(feld) }}<span v-if="feld.pflicht" class="pr-rg-pflicht"> (Pflicht)</span>
          <span v-if="feld.beschreibung" class="pr-rg-beschreibung-klein">{{ feld.beschreibung }}</span>
        </label>

        <!-- Filter: nur vorhandenen Knoten rendern, Anlegen/Löschen per Knopf -->
        <template v-if="feld.typ === 'filter'">
          <PrKnotenEditor v-if="istKnoten(r[feld.name])" :knoten="r[feld.name]" modus="rolle" :kontext="kontext" />
          <div class="pr-rg-zeile">
            <button v-if="!istKnoten(r[feld.name])" type="button" class="dk-btn dk-btn-ghost dk-btn-sm" @click="r[feld.name] = { merkmal: '' }">+ Personen-Filter hinzufügen</button>
            <button v-else type="button" class="dk-btn dk-btn-ghost dk-btn-sm" @click="delete r[feld.name]">Filter entfernen</button>
          </div>
        </template>

        <!-- Planuebergreifender Verweis -->
        <span v-else-if="feld.typ === 'fremd_feld'" class="pr-rg-zeile">
          <input type="text" class="dk-form-input" :value="r[feld.name]?.plantyp || ''" placeholder="Planvorlage (z. B. chorplan)" @change="fremdSetzen(r, feld.name, 'plantyp', $event.target.value)" />
          <input type="text" class="dk-form-input" :value="r[feld.name]?.feld || ''" placeholder="Feld dort (z. B. einueben)" @change="fremdSetzen(r, feld.name, 'feld', $event.target.value)" />
        </span>

        <!-- Auswahl -->
        <select v-else-if="feld.typ === 'auswahl'" v-model="r[feld.name]" class="dk-form-select">
          <option v-for="w in feld.werte" :key="w" :value="w">{{ w }}</option>
        </select>

        <!-- Zahl -->
        <input v-else-if="feld.typ === 'zahl'" v-model.number="r[feld.name]" type="number" class="dk-form-input pr-rg-zahl" :placeholder="beispielText(feld)" />

        <!-- Schalter -->
        <label v-else-if="feld.typ === 'schalter'" class="pr-rg-schalter"><input v-model="r[feld.name]" type="checkbox" /> ja</label>

        <!-- Liste (Komma) -->
        <input
          v-else-if="feld.typ === 'liste'" type="text" class="dk-form-input"
          :value="Array.isArray(r[feld.name]) ? r[feld.name].join(', ') : ''"
          :placeholder="beispielText(feld)"
          @change="listeSetzen(r, feld.name, $event.target.value)"
        />

        <!-- Muster: String ODER Objekt -->
        <input
          v-else-if="feld.typ === 'text_oder_json'" type="text" class="dk-form-input"
          :value="musterText(r[feld.name])" :placeholder="beispielText(feld)"
          @change="musterSetzen(r, feld.name, $event.target.value)"
        />

        <!-- Freier Text -->
        <input
          v-else type="text" class="dk-form-input"
          :value="typeof r[feld.name] === 'object' ? JSON.stringify(r[feld.name]) : (r[feld.name] ?? '')"
          :placeholder="beispielText(feld)"
          @change="textSetzen(r, feld.name, $event.target.value)"
        />
        <PrPfadMeldungen :meldungen="meldungen" :pfad="regelPfad(i) + '/' + feld.name" />
      </div>
    </div>

    <button type="button" class="dk-btn dk-btn-secondary dk-btn-sm" @click="regelnHinzufuegen">+ Regel hinzufügen</button>
  </div>
</template>

<script setup>
/**
 * Regeln-Editor: das Parameterformular baut sich schema-getrieben aus der
 * Baustein-Registry (schemaHolen liefert x-regel-bausteine:
 * {name: {beschreibung, parameter_schema}}). Ist die Registry noch nicht
 * geladen, bleibt ein Hinweis — die Regeln selbst bleiben lesbar und änderbar.
 */
import PrKnotenEditor from './PrKnotenEditor.vue'
import PrPfadMeldungen from './PrPfadMeldungen.vue'
import { STUFEN, regelParameterForm, feldPruefPfad } from './editor.mjs'

const props = defineProps({
  regeln: { type: Array, required: true },
  bausteine: { type: Object, default: () => ({}) },   // x-regel-bausteine
  kontext: { type: Object, default: () => ({}) },
  meldungen: { type: Array, default: () => [] },      // Prüfmeldungen (Inline am Pfad)
  basisPfad: { type: String, default: 'regeln' },     // JSON-Pointer-Basis der Regeln
})

/** Pfad einer Regel, z. B. 0 → 'regeln/0'; Parameter hängen darunter. */
function regelPfad(i) { return feldPruefPfad(props.basisPfad, i) }

function regelnHinzufuegen() {
  if (!Array.isArray(props.regeln)) return
  props.regeln.push({ baustein: '', stufe: 'sollte' })
}

const PARAM_NAMEN = {
  feld: 'Feld', wochen: 'Mindestabstand in Wochen', fuer: 'Gilt je (eintrag oder person)',
  anzahl: 'Anzahl', zeitraum: 'Bezugszeitraum', rolle: 'Rolle / Personenfilter',
  person: 'Person', felder: 'Felder (Komma)', personen: 'Personen (Komma)',
  uebungsfeld: 'Übungsfeld (eigene Planvorlage)', uebung: 'Übung (andere Planvorlage)',
  auch_in: 'Zählt auch in (Komma)', mindestens: 'Mindestens so oft geübt',
  vorlauf_wochen: 'Vorlauf in Wochen', merkmal: 'Angabe des Eintrags',
  muster: 'Verfügbarkeitsmuster', team: 'Team', vorbelegte_mitzaehlen: 'Vorbelegte zählen mit',
}

function paramName(feld) { return PARAM_NAMEN[feld.name] || feld.name }
function beispielText(feld) { return feld.beispiel === undefined ? '' : String(feld.beispiel) }
function paramForm(regel) {
  if (!regel?.baustein || !props.bausteine[regel.baustein]) return []
  return regelParameterForm(props.bausteine[regel.baustein])
}
function beschreibung(regel) { return props.bausteine[regel?.baustein]?.beschreibung || '' }

/** Regel-Baustein gewechselt: Parameter-Keys entfernen, die der neue nicht kennt. */
function bausteinGewechselt(regel) {
  const erlaubt = new Set(paramForm(regel).map((f) => f.name))
  for (const key of Object.keys(regel)) {
    if (!['baustein', 'stufe', 'gewicht'].includes(key) && !erlaubt.has(key)) delete regel[key]
  }
}

function istKnoten(wert) {
  return !!wert && typeof wert === 'object' && !Array.isArray(wert)
}
function fremdSetzen(regel, name, teil, wert) {
  if (!regel[name] || typeof regel[name] !== 'object') regel[name] = {}
  regel[name][teil] = wert
  if (!regel[name].plantyp && !regel[name].feld) delete regel[name]
}
function listeSetzen(regel, name, roh) {
  const werte = String(roh || '').split(',').map((s) => s.trim()).filter(Boolean)
  if (werte.length) regel[name] = werte
  else delete regel[name]
}
function musterText(wert) {
  if (wert === undefined || wert === null || wert === '') return ''
  return typeof wert === 'object' ? JSON.stringify(wert) : String(wert)
}
function musterSetzen(regel, name, roh) {
  const text = String(roh || '').trim()
  if (!text) { delete regel[name]; return }
  if (text.startsWith('{')) {
    try { regel[name] = JSON.parse(text); return } catch { /* als Text behandeln */ }
  }
  regel[name] = text
}
function textSetzen(regel, name, roh) {
  const text = String(roh || '').trim()
  if (!text) { delete regel[name]; return }
  if (text.startsWith('{') || text.startsWith('[')) {
    try { regel[name] = JSON.parse(text); return } catch { /* als Text behandeln */ }
  }
  regel[name] = text
}
</script>

<style scoped>
.pr-rg { display: flex; flex-direction: column; gap: 12px; }
.pr-rg-hinweis { font-size: 0.82rem; color: var(--dk-text-muted); margin: 0; line-height: 1.5; }
.pr-rg-leer { font-size: 0.8rem; color: var(--dk-text-muted); margin: 0; }
.pr-rg-karte { border: 1px solid var(--dk-border); border-radius: 10px; background: var(--dk-surface); padding: 10px 12px; display: flex; flex-direction: column; gap: 10px; }
.pr-rg-zeile { display: flex; align-items: flex-end; gap: 10px; flex-wrap: wrap; }
.pr-rg-label { display: flex; flex-direction: column; gap: 4px; font-size: 0.8rem; font-weight: 600; color: var(--dk-text-muted); min-width: 0; }
.pr-rg-baustein { max-width: 260px; }
.pr-rg-stufe { max-width: 240px; }
.pr-rg-zahl { max-width: 110px; }
.pr-rg-pflicht { color: var(--dk-danger); }
.pr-rg-beschreibung { font-size: 0.82rem; color: var(--dk-text); margin: 0; line-height: 1.5; }
.pr-rg-beschreibung-klein { font-weight: 400; font-size: 0.74rem; color: var(--dk-text-subtle); }
.pr-rg-param { display: flex; flex-direction: column; gap: 6px; border-top: 1px solid var(--dk-divider); padding-top: 8px; }
.pr-rg-schalter { display: inline-flex; align-items: center; gap: 6px; font-size: 0.84rem; color: var(--dk-text); cursor: pointer; }
</style>
