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
        <!-- UX-C3b: Baustein und Stufe sind Kennungen — Auswahl, kein Freitext.
             Ein gespeicherter Baustein, den die Registry nicht kennt (alte
             Version, Tippfehler), bleibt als „unbekannter Wert“ sichtbar. -->
        <label class="pr-rg-label">Baustein
          <PrAuswahl
            class="pr-rg-baustein" :model-value="r.baustein" :optionen="bausteinOptionen"
            platzhalter="— bitte wählen —" aria-label="Baustein" info="baustein"
            :warnung="bausteinWarnung(r)" anderer-wert
            @update:model-value="bausteinSetzen(r, $event)"
          />
        </label>
        <label class="pr-rg-label">Stufe
          <PrAuswahl
            class="pr-rg-stufe" :model-value="r.stufe" :optionen="stufenOptionen" aria-label="Stufe"
            anderer-wert @update:model-value="r.stufe = $event"
          />
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

        <!-- Planuebergreifender Verweis: Planvorlage und Feld sind Kennungen,
             die es wirklich geben muss — Auswahl statt Freitext (UX-C3b).
             Ist die Liste leer (keine fremde Vorlage, fremde Felder unbekannt),
             steht dort ein Textfeld: nie eine leere, unbedienbare Auswahl. -->
        <span v-else-if="feld.typ === 'fremd_feld'" class="pr-rg-zeile">
          <PrAuswahl
            :model-value="r[feld.name]?.plantyp || ''" :optionen="plantypAuswahl"
            platzhalter="— Planvorlage —" aria-label="Planvorlage" info="fremde_vorlage"
            :unbekannt-name="'nicht in deinen Vorlagen'" anderer-wert
            @update:model-value="fremdSetzen(r, feld.name, 'plantyp', $event)"
          />
          <PrAuswahl
            :model-value="r[feld.name]?.feld || ''" :optionen="fremdFeldOptionen(r[feld.name]?.plantyp)"
            platzhalter="— Feld dort —" :aria-label="paramName(feld) + ' – Feld dort'"
            :unbekannt-name="'nicht in dieser Vorlage'" anderer-wert
            @update:model-value="fremdSetzen(r, feld.name, 'feld', $event)"
          />
        </span>

        <!-- Auswahl: Werte aus dem Baustein-Schema. Freie Werte gehen über
             „Anderer Wert …“ (Operator-Entscheidung), nie über eine leere
             Liste. Das aria-label nennt den Parameter. -->
        <PrAuswahl
          v-else-if="feld.typ === 'auswahl'" :model-value="r[feld.name]"
          :optionen="feldOptionen(feld)" :aria-label="paramName(feld)" anderer-wert
          @update:model-value="r[feld.name] = $event"
        />

        <!-- Zahl -->
        <input v-else-if="feld.typ === 'zahl'" v-model.number="r[feld.name]" type="number" class="dk-form-input pr-rg-zahl" :placeholder="beispielText(feld)" />

        <!-- Einzelne Kennung (Feld, Übungsfeld, Merkmal, Sammlung, fremde
             Planvorlage): der Server verlangt einen exakten Verweis — Auswahl
             aus der Definition statt Freitext (UX-C3b, Review Punkt 1). Eine
             Liste, die den gespeicherten Wert nicht kennt, öffnet das Feld
             mit „Anderer Wert …“; ist sie leer, steht ein Textfeld da. -->
        <PrAuswahl
          v-else-if="kennungOptionen(feld).length || istKennung(feld)"
          :model-value="r[feld.name]" :optionen="kennungOptionen(feld)"
          :aria-label="paramName(feld)" anderer-wert
          @update:model-value="kennungSetzen(r, feld.name, $event)"
        />

        <!-- Schalter -->
        <label v-else-if="feld.typ === 'schalter'" class="pr-rg-schalter"><input v-model="r[feld.name]" type="checkbox" /> ja</label>

        <!-- Liste von Kennungen: bekannte Werte zum Anhaken, der gespeicherte
             Altwert bleibt als „unbekannter Wert“ sichtbar (UX-C3b). Ist der
             Katalog leer, steht das Textfeld für freie Werte da. -->
        <template v-else-if="feld.typ === 'liste'">
          <div v-if="listenOptionen(feld).length" class="pr-rg-chips">
            <label v-for="o in listenOptionen(feld)" :key="o.wert" class="pr-rg-chip">
              <input
                type="checkbox" :checked="alsListe(r[feld.name]).includes(o.wert)"
                @change="listeToggle(r, feld.name, o.wert, $event.target.checked)"
              />
              {{ o.text }}
            </label>
          </div>
          <p v-for="u in unbekannteListenWerte(r, feld)" :key="u" class="pr-rg-altwert">
            „{{ u }}“ ({{ istAusFremderVorlage(feld) ? 'nicht in dieser Vorlage' : 'unbekannter Wert' }}) —
            <button type="button" class="pr-rg-link" @click="listeToggle(r, feld.name, u, false)">entfernen</button>
          </p>
          <input
            v-if="!listenOptionen(feld).length || freieListe(feld)" type="text" class="dk-form-input"
            :value="alsListe(r[feld.name]).join(', ')" :placeholder="beispielText(feld)"
            :aria-label="paramName(feld) + ' – Werte mit Komma'" @change="listeSetzen(r, feld.name, $event.target.value)"
          />
        </template>

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
import { computed } from 'vue'
import PrKnotenEditor from './PrKnotenEditor.vue'
import PrAuswahl from './PrAuswahl.vue'
import PrPfadMeldungen from './PrPfadMeldungen.vue'
import { STUFEN, regelParameterForm, feldPruefPfad, feldPfadListe, alsListe } from './editor.mjs'
import {
  feldOptionen as feldOptionenAus, feldPfadOptionen,
  option, personenMerkmalOptionen, plantypOptionen, sammlungOptionen,
} from './auswahl.mjs'

const props = defineProps({
  regeln: { type: Array, required: true },
  bausteine: { type: Object, default: () => ({}) },   // x-regel-bausteine
  kontext: { type: Object, default: () => ({}) },
  meldungen: { type: Array, default: () => [] },      // Prüfmeldungen (Inline am Pfad)
  basisPfad: { type: String, default: 'regeln' },     // JSON-Pointer-Basis der Regeln
})

/**
 * UX-C3b: Wahlwerte für die Parameter der Regeln. Alles, was eine Kennung
 * referenziert (Feld, Sammlung, Merkmal, Planvorlage), kommt aus der
 * Definition bzw. dem Serverstand — kein Freitext mehr. Die Kennungen
 * mehrerer Terminreihen tragen `<reihe>:` (servergeprüft).
 */
const kontext = computed(() => props.kontext || {})
/** Felder der Definition (Top-Level, mit Reihenpräfix). */
const feldAuswahl = computed(() => feldOptionenAus(kontext.value.definition || {}))
/** Alle Feldpfade (auch Unterfelder) für „nicht gleichzeitig“ / „Feld dort“. */
const pfadAuswahl = computed(() => feldPfadOptionen(kontext.value.definition || {}, feldPfadListe))
/** Planvorlagen aus `plantypen_liste` — ohne die eigene. */
const plantypAuswahl = computed(() => plantypOptionen(kontext.value.plantypen, kontext.value.eigenerPlantyp))
/** Sammlungen der Definition (+ eingebaute Liedliste). */
const sammlungAuswahl = computed(() => sammlungOptionen(kontext.value.definition || {}))
/** Merkmale der Personen (für „Angabe des Eintrags“, das ist meist person-bezogen). */
const merkmalAuswahl = computed(() => personenMerkmalOptionen(kontext.value.definition || {}))

const bausteinOptionen = computed(() => Object.keys(props.bausteine || {}).map((name) => option(name, name)))
const stufenOptionen = computed(() => STUFEN.map((s) => option(s.wert, s.name)))

/** Warum ein gespeicherter Baustein nicht in der Registry steht. */
function bausteinWarnung(regel) {
  if (!regel?.baustein || props.bausteine[regel.baustein]) return ''
  return `„${regel.baustein}“ kennt diese Registry nicht — der Wert bleibt erhalten, `
    + 'die Prüfung meldet ihn als unbekannten Baustein.'
}

// ── Auswahl der Feldreferenzen ─────────────────────────────────────────────

const FELD_PARAMETER = new Set(['feld', 'uebungsfeld'])
const SAMMLUNG_PARAMETER = new Set(['sammlung'])
const MERKMAL_PARAMETER = new Set(['merkmal'])

function feldOptionen(feld) { return (feld?.werte || []).map((w) => option(w, w)) }

/**
 * Einzelne Kennungs-Referenz als Auswahl (Review Punkt 1): `feld` und
 * `uebungsfeld` zeigen auf Felder der eigenen Definition, `merkmal` auf die
 * Merkmale der Personen. Der Server verlangt dort einen exakten Verweis,
 * deshalb Auswahl statt Freitext — auch als String-Parameter.
 */
function istKennung(feld) {
  return feld?.typ === 'text' && (FELD_PARAMETER.has(feld.name) || MERKMAL_PARAMETER.has(feld.name))
}

function kennungOptionen(feld) {
  if (FELD_PARAMETER.has(feld.name)) return feldAuswahl.value
  if (MERKMAL_PARAMETER.has(feld.name)) return merkmalAuswahl.value
  return []
}

/**
 * Einzelne Kennung setzen. `wert` kommt aus der Auswahl bzw. aus dem Feld
 * „Anderer Wert …“ — ein gespeicherter Altwert bleibt unverändert, solange er
 * nicht ersetzt wird.
 */
function kennungSetzen(regel, name, wert) {
  const text = String(wert ?? '').trim()
  if (!text) { delete regel[name]; return }
  regel[name] = text
}

/**
 * Optionen einer Liste-Referenz je Parameter:
 *   feld/uebungsfeld → Felder der Definition, auch_in → fremde Planvorlagen,
 *   felder → Feldpfade (nicht gleichzeitig), sammlung → Sammlungen,
 *   merkmal → Personen-Merkmale. Leer = keine bekannten Werte.
 */
function listenOptionen(feld) {
  if (FELD_PARAMETER.has(feld.name)) return feldAuswahl.value
  if (feld.name === 'auch_in') return plantypAuswahl.value
  if (feld.name === 'felder') return pfadAuswahl.value
  if (SAMMLUNG_PARAMETER.has(feld.name)) return sammlungAuswahl.value
  return []
}

/**
 * Freie Restliste: Parameter ohne Kennungsbezug (Personen, freie Werte) —
 * und eine Kennungsliste, für die es (noch) KEINEN Katalog gibt. Dann steht
 * dort das Textfeld: eine leere Auswahl wäre nicht bedienbar.
 */
function freieListe(feld) {
  return listenOptionen(feld).length === 0
}

/** Verweist der Parameter auf eine ANDERE Planvorlage? */
function istAusFremderVorlage(feld) { return feld?.name === 'auch_in' }

function fremdFeldOptionen(plantyp) {
  // Felder eines fremden Plantyps kennt der Editor nicht. Die Auswahl zeigt
  // dann ein Textfeld („Anderer Wert …“) — der gespeicherte Wert bleibt als
  // Altwert sichtbar, neue Werte sind frei wählbar.
  const eigen = kontext.value.definition?.id
  if (!plantyp || plantyp === eigen) return feldAuswahl.value
  return []
}

/** Gespeicherte Listenwerte, die keine Option (mehr) haben. */
function unbekannteListenWerte(regel, feld) {
  const liste = alsListe(regel?.[feld.name])
  const bekannt = new Set(listenOptionen(feld).map((o) => o.wert))
  return liste.filter((w) => !bekannt.has(String(w)))
}

function listeToggle(regel, name, wert, an) {
  const liste = alsListe(regel[name]).filter((w) => w !== wert)
  if (an) liste.push(wert)
  if (liste.length) regel[name] = liste
  else delete regel[name]
}

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

/**
 * FIX-7: Baustein einer Regel wechseln.
 *
 * Das Template bindet `@update:model-value="bausteinSetzen(r, $event)"`; die
 * Funktion fehlte im Skript (Vue brach die Auswahl mit „Property
 * "bausteinSetzen" was accessed during render but is not defined" ab, der
 * Baustein liess sich im Plantyp-Editor nicht umstellen). Eingetragen wird
 * der neue Name und aufgeraeumt, was der neue Baustein nicht mehr kennt —
 * dafuer gibt es bereits `bausteinGewechselt`, das hier gefaellt war.
 */
function bausteinSetzen(regel, wert) {
  if (!regel) return
  regel.baustein = typeof wert === 'string' ? wert : (wert && wert.wert) || ''
  bausteinGewechselt(regel)
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
.pr-rg-hinweis { font-size: var(--fs-14); color: var(--dk-text-muted); margin: 0; line-height: 1.5; }
.pr-rg-leer { font-size: var(--fs-12); color: var(--dk-text-muted); margin: 0; }
.pr-rg-karte { border: 1px solid var(--dk-border); border-radius: 10px; background: var(--dk-surface); padding: 10px 12px; display: flex; flex-direction: column; gap: 10px; }
.pr-rg-zeile { display: flex; align-items: flex-end; gap: 10px; flex-wrap: wrap; }
.pr-rg-label { display: flex; flex-direction: column; gap: 4px; font-size: var(--fs-12); font-weight: var(--fw-fett); color: var(--dk-text-muted); min-width: 0; }
.pr-rg-baustein { max-width: 260px; }
.pr-rg-stufe { max-width: 240px; }
.pr-rg-zahl { max-width: 110px; }
.pr-rg-pflicht { color: var(--dk-danger); }
.pr-rg-beschreibung { font-size: var(--fs-14); color: var(--dk-text); margin: 0; line-height: 1.5; }
.pr-rg-beschreibung-klein { font-weight: var(--fw-normal); font-size: var(--fs-12); color: var(--dk-text-subtle); }
.pr-rg-param { display: flex; flex-direction: column; gap: 6px; border-top: 1px solid var(--dk-divider); padding-top: 8px; }
.pr-rg-schalter { display: inline-flex; align-items: center; gap: 6px; font-size: var(--fs-14); color: var(--dk-text); cursor: pointer; }
/* UX-C3b: Listen-Referenzen als Chips statt Komma-Freitext. */
.pr-rg-chips { display: flex; flex-wrap: wrap; gap: 6px 12px; }
.pr-rg-chip { display: inline-flex; align-items: center; gap: 5px; font-size: var(--fs-14); color: var(--dk-text); cursor: pointer; }
.pr-rg-altwert { font-size: var(--fs-12); color: var(--dk-warning); margin: 0; display: flex; gap: 6px; align-items: baseline; flex-wrap: wrap; }
.pr-rg-link { background: none; border: none; padding: 0; font: inherit; color: var(--dk-brand-800); text-decoration: underline; cursor: pointer; }
</style>
