<template>
  <div class="pr-fb">
    <div v-for="(f, i) in felder" :key="i" class="pr-fb-feld" :class="{ 'pr-fb-feld--tief': tiefe > 0 }">
      <div class="pr-fb-kopf">
        <button
          type="button" class="pr-fb-auf" :aria-expanded="auf === i ? 'true' : 'false'"
          :aria-label="'Feld ' + (f.id || i + 1) + (auf === i ? ' zuklappen' : ' aufklappen')"
          @click="auf = auf === i ? null : i"
        >{{ auf === i ? '▾' : '▸' }}</button>
        <input v-model="f.id" type="text" class="dk-form-input pr-fb-id" placeholder="kennung" aria-label="Feld-Kennung" />
        <input v-model="f.name" type="text" class="dk-form-input pr-fb-name" placeholder="Anzeigename" aria-label="Anzeigename" />
        <select v-model="f.art" class="dk-form-select pr-fb-art" aria-label="Feldart" @change="artGewechselt(f)">
          <option v-for="a in FELD_ARTEN" :key="a.wert" :value="a.wert">{{ a.name }}</option>
        </select>
        <span v-if="stufenFuer(i)" class="dk-badge" :class="stufenFuer(i) === 'fehler' ? 'dk-badge-danger' : stufenFuer(i) === 'warnung' ? 'dk-badge-warning' : 'dk-badge'">
          {{ stufenFuer(i) === 'fehler' ? 'Fehler' : stufenFuer(i) === 'warnung' ? 'Warnung' : 'Hinweis' }}
        </span>
        <span class="pr-fb-aktionen">
          <button type="button" class="dk-btn dk-btn-ghost dk-btn-sm" aria-label="Nach oben" :disabled="i === 0" @click="verschieben(i, -1)">↑</button>
          <button type="button" class="dk-btn dk-btn-ghost dk-btn-sm" aria-label="Nach unten" :disabled="i === felder.length - 1" @click="verschieben(i, 1)">↓</button>
          <button
            v-if="i > 0 && ['gruppe', 'eintrag'].includes(felder[i - 1]?.art)"
            type="button" class="dk-btn dk-btn-ghost dk-btn-sm" title="In das vorherige Feld einrücken"
            @click="einruecken(i)"
          >→ einrücken</button>
          <button
            v-if="gruppenModus" type="button" class="dk-btn dk-btn-ghost dk-btn-sm" title="Eine Ebene heraus"
            @click="$emit('ausruecken', { index: i, feld: f })"
          >← ausrücken</button>
          <button type="button" class="dk-btn dk-btn-ghost dk-btn-sm" aria-label="Feld entfernen" @click="felder.splice(i, 1)">✕</button>
        </span>
      </div>
      <PrMeldungen :meldungen="meldungenFuer(i)" kompakt />

      <div v-if="auf === i" class="pr-fb-koerper">
        <div class="pr-fb-zeile">
          <label class="pr-fb-label">Anzahl je Termin
            <span class="pr-fb-hilfe">feste Zahl oder Bereich</span>
            <span class="pr-fb-anzahl">
              <input type="number" min="0" class="dk-form-input pr-fb-zahl" :value="anzahlVon(i)" aria-label="Mindestanzahl" @change="anzahlSetzen(f, { min: $event.target.value }, 'min')" />
              <span class="pr-fb-bis">bis</span>
              <input type="number" min="0" class="dk-form-input pr-fb-zahl" :value="anzahlBis(i)" :disabled="anzahlOffen(i)" aria-label="Höchstanzahl" @change="anzahlSetzen(f, { max: $event.target.value }, 'max')" />
              <label class="pr-fb-schalter"><input type="checkbox" :checked="anzahlOffen(i)" @change="anzahlSetzen(f, { offen: $event.target.checked }, 'offen')" /> offen</label>
            </span>
          </label>
          <label class="pr-fb-schalter pr-fb-schalter--gross"><input v-model="f.pflicht" type="checkbox" /> Pflichtfeld</label>
          <label class="pr-fb-label">Zeitfenster
            <input v-model="f.zeit" type="text" class="dk-form-input pr-fb-zeit" placeholder="10:30-12:00" aria-label="Zeitfenster" />
          </label>
        </div>

        <!-- Art-spezifisch -->
        <div v-if="f.art === 'person' || f.art === 'personen'" class="pr-fb-zeile">
          <label class="pr-fb-label">Wer kommt in Frage?
            <select :value="rollenModus(i)" class="dk-form-select" @change="rollenModusSetzen(f, $event.target.value)">
              <option value="inline">Eigener Filter</option>
              <option v-for="r in kontext.rollen || []" :key="r.id" :value="'@' + r.id">Benannte Rolle: {{ r.name || r.id }}</option>
            </select>
          </label>
        </div>
        <template v-if="(f.art === 'person' || f.art === 'personen') && rollenModus(i) === 'inline'">
          <PrKnotenEditor v-if="istKnoten(f.rolle)" :knoten="f.rolle" modus="rolle" :kontext="kontext" />
          <div v-else class="pr-fb-zeile">
            <button type="button" class="dk-btn dk-btn-ghost dk-btn-sm" @click="f.rolle = { merkmal: '' }">+ Personenauswahl einschränken (Rollenfilter)</button>
          </div>
        </template>

        <div v-if="f.art === 'eintrag'" class="pr-fb-zeile">
          <label class="pr-fb-label">Liste, aus der gewählt wird
            <input v-model="f.sammlung" type="text" class="dk-form-input" list="pr-fb-sammlungen" placeholder="lieder" aria-label="Liste" />
            <datalist id="pr-fb-sammlungen">
              <option value="lieder" />
              <option v-for="s in kontext.sammlungen || []" :key="s.id" :value="s.id" />
            </datalist>
            <span class="pr-fb-hilfe">Eingebaute Liste „lieder“, eigene Kennung oder {parameter.x}</span>
          </label>
        </div>

        <div v-if="f.art === 'auswahl'" class="pr-fb-zeile">
          <label class="pr-fb-label">Werte (mit Komma getrennt)
            <input type="text" class="dk-form-input" :value="(f.werte || []).join(', ')" placeholder="Chor, Solo" @change="listeSetzen(f, 'werte', $event.target.value)" />
          </label>
          <label class="pr-fb-schalter pr-fb-schalter--gross"><input v-model="f.mehrfach" type="checkbox" /> mehrere Werte gleichzeitig</label>
        </div>

        <div v-if="f.art === 'team'" class="pr-fb-zeile">
          <label class="pr-fb-label">Welche Teams?
            <select :value="teamsModus(i)" class="dk-form-select" @change="teamsModusSetzen(f, $event.target.value)">
              <option value="gruppe_unter">Alle Gruppen unter einer Obergruppe</option>
              <option value="liste">Bestimmte Teams auflisten</option>
            </select>
          </label>
          <label v-if="teamsModus(i) === 'gruppe_unter'" class="pr-fb-label">Obergruppe
            <input type="text" class="dk-form-input" :value="f.teams?.gruppe_unter || ''" placeholder="Musikteams" @input="teamsSetzen(f, { gruppe_unter: $event.target.value })" />
          </label>
          <label v-else class="pr-fb-label">Teams (mit Komma getrennt)
            <input type="text" class="dk-form-input" :value="Array.isArray(f.teams) ? f.teams.join(', ') : ''" @change="listeSetzen(f, 'teams', $event.target.value)" />
          </label>
        </div>
        <template v-if="f.art === 'team'">
          <p class="pr-fb-hilfe">Optional: nur eine Teilmenge der Teammitglieder auswählen — z. B. nur die Sänger.</p>
          <PrKnotenEditor v-if="istKnoten(f.mitglieder)" :knoten="f.mitglieder" modus="rolle" :kontext="kontext" />
          <div class="pr-fb-zeile">
            <button v-if="!istKnoten(f.mitglieder)" type="button" class="dk-btn dk-btn-ghost dk-btn-sm" @click="f.mitglieder = { merkmal: '' }">+ Nur bestimmte Mitglieder auswählen</button>
            <button v-else type="button" class="dk-btn dk-btn-ghost dk-btn-sm" @click="delete f.mitglieder">Alle Teammitglieder (Filter entfernen)</button>
          </div>
        </template>

        <!-- Füllstrategie -->
        <div class="pr-fb-zeile">
          <label class="pr-fb-label">Wie wird das Feld gefüllt?
            <select v-model="f.fuellen" class="dk-form-select">
              <option v-for="s in FUELLSTRATEGIEN" :key="s.wert" :value="s.wert">{{ s.name }}</option>
            </select>
          </label>
          <label v-if="f.fuellen === 'vorbelegen'" class="pr-fb-label">Wert kommt aus
            <input v-model="f.aus" type="text" class="dk-form-input" placeholder="eintrag.dirigent oder anderes Feld" aria-label="Bezugsfeld" />
            <span class="pr-fb-hilfe">Eigenschaft des Listeneintrags (eintrag.x), Feldpfad oder bezug.team</span>
          </label>
        </div>

        <!-- Bedingung: nur vorhandene Knoten rendern, Anlegen/Löschen per Knopf -->
        <PrKnotenEditor v-if="istKnoten(f.bedingung)" :knoten="f.bedingung" modus="bedingung" :kontext="kontext" />
        <div class="pr-fb-zeile">
          <button v-if="!istKnoten(f.bedingung)" type="button" class="dk-btn dk-btn-ghost dk-btn-sm" @click="f.bedingung = { anlass: '' }">+ Nur unter Bedingung erscheinen</button>
          <button v-else type="button" class="dk-btn dk-btn-ghost dk-btn-sm" @click="delete f.bedingung">Bedingung entfernen (immer erscheinen)</button>
        </div>

        <!-- Unterfelder: Gruppe und Eintrag -->
        <div v-if="f.art === 'gruppe' || f.art === 'eintrag'" class="pr-fb-unter">
          <h5 class="pr-fb-unter-titel">Unterfelder</h5>
          <PrFelderEditor
            v-if="Array.isArray(f.inhalt)"
            :felder="f.inhalt" :kontext="kontext" :tiefe="tiefe + 1" :gruppen-modus="true"
            :meldungen="meldungen" :basis-pfad="feldPfad(i) + '/inhalt'"
            @ausruecken="ausrueckenAus(f, $event)"
          />
          <div class="pr-fb-zeile">
            <button v-if="!Array.isArray(f.inhalt)" type="button" class="dk-btn dk-btn-ghost dk-btn-sm" @click="f.inhalt = []">+ Unterfelder hinzufügen</button>
            <button v-else type="button" class="dk-btn dk-btn-ghost dk-btn-sm" @click="delete f.inhalt">Unterfelder entfernen</button>
          </div>
        </div>

        <!-- Varianten und Teile: nur Gruppe -->
        <div v-if="f.art === 'gruppe'" class="pr-fb-unter">
          <h5 class="pr-fb-unter-titel">Varianten — es gilt je Termin EINE</h5>
          <div v-for="(v, vi) in (f.varianten || [])" :key="'v' + vi" class="pr-fb-zweig">
            <div class="pr-fb-zeile">
              <input v-model="v.id" type="text" class="dk-form-input pr-fb-id" placeholder="kennung" aria-label="Variante" />
              <input v-model="v.name" type="text" class="dk-form-input pr-fb-name" placeholder="Anzeigename" aria-label="Anzeigename" />
              <label class="pr-fb-schalter"><input type="checkbox" :checked="Array.isArray(v.inhalt)" @change="zweigInhaltToggle(v, $event.target.checked)" /> eigene Felder</label>
              <button type="button" class="dk-btn dk-btn-ghost dk-btn-sm" aria-label="Variante entfernen" @click="f.varianten.splice(vi, 1)">✕</button>
            </div>
            <PrKnotenEditor v-if="istKnoten(v.bedingung)" :knoten="v.bedingung" modus="bedingung" :kontext="kontext" />
            <div class="pr-fb-zeile">
              <button v-if="!istKnoten(v.bedingung)" type="button" class="dk-btn dk-btn-ghost dk-btn-sm" @click="v.bedingung = { anlass: '' }">+ Bedingung</button>
              <button v-else type="button" class="dk-btn dk-btn-ghost dk-btn-sm" @click="delete v.bedingung">Bedingung entfernen</button>
            </div>
            <PrFelderEditor
              v-if="Array.isArray(v.inhalt)"
              :felder="v.inhalt" :kontext="kontext" :tiefe="tiefe + 1" :gruppen-modus="true"
              :meldungen="meldungen" :basis-pfad="feldPfad(i) + '/varianten/' + vi + '/inhalt'"
              @ausruecken="zweigAusruecken(v, $event)"
            />
          </div>
          <button v-if="!Array.isArray(f.varianten)" type="button" class="dk-btn dk-btn-ghost dk-btn-sm" @click="f.varianten = []">+ Varianten hinzufügen (z. B. Sonne/Regen)</button>
          <button v-else type="button" class="dk-btn dk-btn-ghost dk-btn-sm" @click="f.varianten.push({ id: '' })">+ Variante hinzufügen</button>

          <h5 class="pr-fb-unter-titel">Teile — laufen nacheinander ab</h5>
          <div v-for="(t, ti) in (f.teile || [])" :key="'t' + ti" class="pr-fb-zweig">
            <div class="pr-fb-zeile">
              <input v-model="t.id" type="text" class="dk-form-input pr-fb-id" placeholder="kennung" aria-label="Teil" />
              <input v-model="t.name" type="text" class="dk-form-input pr-fb-name" placeholder="Anzeigename" aria-label="Anzeigename" />
              <label class="pr-fb-schalter"><input type="checkbox" :checked="Array.isArray(t.inhalt)" @change="zweigInhaltToggle(t, $event.target.checked)" /> eigene Felder</label>
              <button type="button" class="dk-btn dk-btn-ghost dk-btn-sm" aria-label="Teil entfernen" @click="f.teile.splice(ti, 1)">✕</button>
            </div>
            <PrFelderEditor
              v-if="Array.isArray(t.inhalt)"
              :felder="t.inhalt" :kontext="kontext" :tiefe="tiefe + 1" :gruppen-modus="true"
              :meldungen="meldungen" :basis-pfad="feldPfad(i) + '/teile/' + ti + '/inhalt'"
              @ausruecken="zweigAusruecken(t, $event)"
            />
          </div>
          <button v-if="!Array.isArray(f.teile)" type="button" class="dk-btn dk-btn-ghost dk-btn-sm" @click="f.teile = []">+ Teile hinzufügen (nacheinander)</button>
          <button v-else type="button" class="dk-btn dk-btn-ghost dk-btn-sm" @click="f.teile.push({ id: '' })">+ Teil hinzufügen</button>
        </div>

        <!-- Elementtypen: nur Ablauf -->
        <div v-if="f.art === 'ablauf'" class="pr-fb-unter">
          <h5 class="pr-fb-unter-titel">Elementtypen des Ablaufs (in Reihenfolge)</h5>
          <div v-for="(e, ei) in (f.elemente || [])" :key="'e' + ei" class="pr-fb-zweig">
            <div class="pr-fb-zeile">
              <input v-model="e.typ" type="text" class="dk-form-input pr-fb-id" placeholder="lied" aria-label="Elementtyp" />
              <input v-model="e.name" type="text" class="dk-form-input pr-fb-name" placeholder="Anzeigename" aria-label="Anzeigename" />
              <label class="pr-fb-schalter"><input v-model="e.nummeriert" type="checkbox" /> laufende Nummer</label>
              <button type="button" class="dk-btn dk-btn-ghost dk-btn-sm" aria-label="Elementtyp entfernen" @click="f.elemente.splice(ei, 1)">✕</button>
            </div>
            <PrFelderEditor
              v-if="Array.isArray(e.inhalt)"
              :felder="e.inhalt" :kontext="kontext" :tiefe="tiefe + 1" :gruppen-modus="true"
              :meldungen="meldungen" :basis-pfad="feldPfad(i) + '/elemente/' + ei + '/inhalt'"
              @ausruecken="zweigAusruecken(e, $event)"
            />
            <div class="pr-fb-zeile">
              <button v-if="!Array.isArray(e.inhalt)" type="button" class="dk-btn dk-btn-ghost dk-btn-sm" @click="e.inhalt = []">+ Felder des Elements hinzufügen</button>
              <button v-else type="button" class="dk-btn dk-btn-ghost dk-btn-sm" @click="delete e.inhalt">Felder entfernen</button>
            </div>
          </div>
          <button type="button" class="dk-btn dk-btn-ghost dk-btn-sm" @click="f.elemente.push({ typ: '', inhalt: [] })">+ Elementtyp hinzufügen</button>
        </div>
      </div>
    </div>

    <div class="pr-fb-neu">
      <select v-model="neueArt" class="dk-form-select pr-fb-neu-wahl" aria-label="Art des neuen Felds">
        <option v-for="a in FELD_ARTEN" :key="a.wert" :value="a.wert">{{ a.name }}</option>
      </select>
      <button type="button" class="dk-btn dk-btn-secondary dk-btn-sm" @click="feldHinzufuegen">+ Feld hinzufügen</button>
    </div>
  </div>
</template>

<script setup>
/**
 * Rekursiver Felderbaum des Plantyp-Editor: hinzufügen, sortieren (↑/↓),
 * einrücken/ausrücken, alle Feldarten mit ihren bausteinspezifischen
 * Einstellungen (Rolle, Sammlung, Teams, Füllstrategie, Bedingung,
 * Unterfelder, Varianten, Teile, Elementtypen). Der Baum wird IN PLACE
 * verwaltet — die Referenz zur Definition bleibt erhalten.
 */
import { ref } from 'vue'
import PrKnotenEditor from './PrKnotenEditor.vue'
import PrMeldungen from './PrMeldungen.vue'
import { FELD_ARTEN, FUELLSTRATEGIEN, leeresFeld, anzahlLesen, anzahlAus, feldVerschieben, feldEinruecken, feldPruefPfad, meldungenAmFeld } from './editor.mjs'

const props = defineProps({
  felder: { type: Array, required: true },
  kontext: { type: Object, default: () => ({}) },
  tiefe: { type: Number, default: 0 },
  gruppenModus: { type: Boolean, default: false },
  meldungen: { type: Array, default: () => [] },   // Prüfmeldungen (für Abzeichen)
  basisPfad: { type: String, default: '' },        // JSON-Pointer-Basis für Abzeichen
})
defineEmits(['ausruecken'])

const auf = ref(null)
const neueArt = ref('text')

function verschieben(i, delta) { feldVerschieben(props.felder, i, delta) }
function einruecken(i) { feldEinruecken(props.felder, i) }
function feldHinzufuegen() {
  props.felder.push(leeresFeld(neueArt.value))
  auf.value = props.felder.length - 1
}

/** 'ausruecken'-Event aus einem Unterbaum: Feld eine Ebene nach oben. */
function ausrueckenAus(besitzer, ereignis) {
  const liste = Array.isArray(besitzer.inhalt) ? besitzer.inhalt : []
  if (ereignis.index < 0 || ereignis.index >= liste.length) return
  const [feld] = liste.splice(ereignis.index, 1)
  const pos = props.felder.indexOf(besitzer)
  props.felder.splice(pos + 1, 0, feld)
}

function zweigAusruecken(zweig, ereignis) {
  const liste = Array.isArray(zweig.inhalt) ? zweig.inhalt : []
  if (ereignis.index < 0 || ereignis.index >= liste.length) return
  const [feld] = liste.splice(ereignis.index, 1)
  // Zwei Ebenen heraus: aus der Variante/Teil-Liste in die aktuelle Feldliste.
  props.felder.push(feld)
}

function zweigInhaltToggle(zweig, an) {
  if (an) { if (!Array.isArray(zweig.inhalt)) zweig.inhalt = [] }
  else delete zweig.inhalt
}

function artGewechselt(f) {
  if (f.art === 'gruppe' && !Array.isArray(f.inhalt)) f.inhalt = []
  if (f.art === 'ablauf' && !Array.isArray(f.elemente)) f.elemente = []
  if (f.art !== 'ablauf') delete f.elemente
}

// ── kleine Helfer für in-place-strukturierte Werte ────────────────────────

/** Ein vorhandener, nicht-leerer Knoten? Rendern nur bei wahr — nie anlegen. */
function istKnoten(wert) {
  return !!wert && typeof wert === 'object' && !Array.isArray(wert)
}

function listeSetzen(obj, schluessel, roh) {
  const werte = String(roh || '').split(',').map((s) => s.trim()).filter(Boolean)
  if (werte.length) obj[schluessel] = werte
  else delete obj[schluessel]
}

function rollenModus(i) {
  const r = props.felder[i].rolle
  return typeof r === 'string' && r.startsWith('@') ? r : 'inline'
}
function rollenModusSetzen(f, modus) {
  if (modus === 'inline') {
    // Bestehender Inline-Filter bleibt erhalten; nur Fremdwerte werden ersetzt.
    if (typeof f.rolle !== 'object' || f.rolle === null || Array.isArray(f.rolle)) f.rolle = { merkmal: '' }
  } else {
    f.rolle = modus   // '@kennung' — bleibt eine String-Referenz
  }
}

function teamsModus(i) {
  const t = props.felder[i].teams
  return Array.isArray(t) ? 'liste' : 'gruppe_unter'
}
function teamsModusSetzen(f, modus) {
  if (modus === 'liste') f.teams = []
  else f.teams = { gruppe_unter: '' }
}
function teamsSetzen(f, neu) { f.teams = neu }

// ── Anzahl ────────────────────────────────────────────────────────────────

function anzahlVon(i) { return anzahlLesen(props.felder[i].anzahl).min }
function anzahlBis(i) {
  const g = anzahlLesen(props.felder[i].anzahl)
  return g.offen ? '' : g.max
}
function anzahlOffen(i) { return anzahlLesen(props.felder[i].anzahl).offen }
function anzahlSetzen(f, ergaenzen, teil) {
  const g = { ...anzahlLesen(f.anzahl), ...ergaenzen }
  if (teil === 'min') g.min = Math.max(0, Math.floor(Number(ergaenzen.min) || 0))
  if (teil === 'max') g.max = Math.max(g.min, Math.floor(Number(ergaenzen.max) || g.min))
  if (teil === 'offen' && !ergaenzen.offen) g.max = g.max ?? g.min
  f.anzahl = anzahlAus(g)
}

// ── Meldungs-Abzeichen ────────────────────────────────────────────────────

function feldPfad(i) { return feldPruefPfad(props.basisPfad, i) }
function meldungenFuer(i) { return meldungenAmFeld(props.meldungen, feldPfad(i)) }

/** Prüfmeldungen, deren JSON-Pointer auf dieses Feld zeigen. */
function stufenFuer(i) {
  const treffer = meldungenFuer(i)
  if (treffer.some((m) => m.stufe === 'fehler')) return 'fehler'
  if (treffer.some((m) => m.stufe === 'warnung')) return 'warnung'
  return treffer.length ? 'hinweis' : ''
}
</script>

<style scoped>
.pr-fb { display: flex; flex-direction: column; gap: 10px; min-width: 0; }
.pr-fb-feld { border: 1px solid var(--dk-border); border-radius: 10px; background: var(--dk-surface); padding: 8px 10px; }
.pr-fb-feld--tief { background: var(--dk-surface-2); }
.pr-fb-kopf { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.pr-fb-auf { background: none; border: none; cursor: pointer; font-size: 0.9rem; color: var(--dk-text-muted); padding: 2px 6px; }
.pr-fb-id { max-width: 170px; font-family: ui-monospace, monospace; font-size: 0.82rem; }
.pr-fb-name { max-width: 240px; }
.pr-fb-art { max-width: 250px; }
.pr-fb-aktionen { display: inline-flex; gap: 2px; margin-left: auto; }
.pr-fb-koerper { display: flex; flex-direction: column; gap: 10px; margin-top: 10px; }
.pr-fb-zeile { display: flex; align-items: flex-end; gap: 12px; flex-wrap: wrap; }
.pr-fb-label { display: flex; flex-direction: column; gap: 4px; font-size: 0.8rem; font-weight: 600; color: var(--dk-text-muted); }
.pr-fb-hilfe { font-weight: 400; font-size: 0.74rem; color: var(--dk-text-subtle); }
.pr-fb-anzahl { display: inline-flex; align-items: center; gap: 6px; }
.pr-fb-zahl { max-width: 80px; }
.pr-fb-bis { font-size: 0.76rem; color: var(--dk-text-subtle); }
.pr-fb-zeit { max-width: 150px; }
.pr-fb-schalter { display: inline-flex; align-items: center; gap: 6px; font-size: 0.82rem; color: var(--dk-text); cursor: pointer; }
.pr-fb-schalter--gross { padding-bottom: 8px; }
.pr-fb-details { font-size: 0.84rem; }
.pr-fb-details summary { cursor: pointer; color: var(--dk-text-muted); font-size: 0.8rem; font-weight: 600; }
.pr-fb-unter { padding-left: 10px; border-left: 3px solid color-mix(in oklch, var(--dk-brand-400) 35%, var(--dk-border)); display: flex; flex-direction: column; gap: 8px; }
.pr-fb-unter-titel { font-size: 0.74rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: var(--dk-text-muted); margin: 4px 0 0; }
.pr-fb-zweig { border: 1px dashed var(--dk-border); border-radius: 8px; padding: 8px; display: flex; flex-direction: column; gap: 6px; }
.pr-fb-neu { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.pr-fb-neu-wahl { max-width: 260px; }
@media (max-width: 640px) {
  .pr-fb-id, .pr-fb-name, .pr-fb-art { max-width: none; width: 100%; }
  .pr-fb-aktionen { margin-left: 0; }
}
</style>
