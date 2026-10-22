<template>
  <div class="pr-dek">
    <!-- Planparameter -->
    <section class="pr-dek-abschnitt">
      <h4 class="pr-dek-titel">Planparameter</h4>
      <p class="pr-dek-hinweis">
        Parameter sind Platzhalter, die erst der konkrete Plan mit Werten füllt
        (Zeitraum, Thema, Themenreihe …). In der Planvorlage werden sie über
        <code>{parameter.&lt;id&gt;}</code> referenziert.
      </p>
      <p v-if="!parameter.length" class="pr-dek-leer">Keine Parameter — der Wert ist in der Planvorlage fest.</p>
      <div v-for="(p, i) in parameter" :key="i" class="pr-dek-karte">
        <div class="pr-dek-zeile">
          <label class="pr-dek-label">Kennung
            <input v-model="p.id" type="text" class="dk-form-input pr-dek-kurz" placeholder="zeitraum" />
          </label>
          <label class="pr-dek-label">Name
            <input v-model="p.name" type="text" class="dk-form-input" placeholder="Zeitraum" />
          </label>
          <label class="pr-dek-label">Art
            <select v-model="p.art" class="dk-form-select">
              <option v-for="a in PARAMETER_ARTEN" :key="a.wert" :value="a.wert">{{ a.name }}</option>
            </select>
          </label>
          <label v-if="p.art === 'auswahl'" class="pr-dek-label">Werte (Komma)
            <input type="text" class="dk-form-input" :value="(p.werte || []).join(', ')" @change="listeSetzen(p, 'werte', $event.target.value)" />
          </label>
          <label v-if="p.art === 'auswahl'" class="pr-dek-schalter"><input v-model="p.mehrfach" type="checkbox" /> mehrfach</label>
          <button type="button" class="dk-btn dk-btn-ghost dk-btn-sm" aria-label="Parameter entfernen" @click="parameter.splice(i, 1)">✕</button>
        </div>
        <PrPfadMeldungen :meldungen="meldungen" :pfad="'parameter/' + i" />
      </div>
      <button type="button" class="dk-btn dk-btn-secondary dk-btn-sm" @click="parameterHinzufuegen">+ Parameter hinzufügen</button>
    </section>

    <!-- Angaben -->
    <section class="pr-dek-abschnitt">
      <h4 class="pr-dek-titel">Angaben</h4>
      <p class="pr-dek-hinweis">
        Angaben beschreiben Personen („spielt Klavier“) oder Listeneinträge
        (Standard-Dirigent eines Liedes). Eingebaute Attribute wie
        <code>kuerzel</code> oder <code>titel</code> brauchen keine Deklaration.
      </p>
      <div v-for="ziel in ziele" :key="ziel.wert" class="pr-dek-ziel">
        <h5 class="pr-dek-ziel-titel">{{ ziel.name }}</h5>
        <p v-if="!merkmaleListe(ziel.wert).length" class="pr-dek-leer">Noch keine Angaben deklariert.</p>
        <div v-for="(m, i) in merkmaleListe(ziel.wert)" :key="i" class="pr-dek-karte">
          <div class="pr-dek-zeile">
            <label class="pr-dek-label">Kennung
              <input v-model="m.id" type="text" class="dk-form-input pr-dek-kurz" placeholder="klavier" />
            </label>
            <label class="pr-dek-label">Name
              <input v-model="m.name" type="text" class="dk-form-input" placeholder="spielt Klavier" />
            </label>
            <label class="pr-dek-label">Art
              <select v-model="m.art" class="dk-form-select">
                <option v-for="a in MERKMALS_ARTEN" :key="a.wert" :value="a.wert">{{ a.name }}</option>
              </select>
            </label>
            <label v-if="m.art === 'auswahl'" class="pr-dek-label">Werte (Komma)
              <input type="text" class="dk-form-input" :value="(m.werte || []).join(', ')" @change="listeSetzen(m, 'werte', $event.target.value)" />
            </label>
            <label v-if="m.art === 'auswahl'" class="pr-dek-schalter"><input v-model="m.mehrfach" type="checkbox" /> mehrfach</label>
            <button type="button" class="dk-btn dk-btn-ghost dk-btn-sm" aria-label="Eigenschaft entfernen" @click="merkmaleVon(ziel.wert)?.splice(i, 1)">✕</button>
          </div>
          <PrPfadMeldungen :meldungen="meldungen" :pfad="'merkmale/' + ziel.wert + '/' + i" />
          <template v-if="m.art === 'person'">
            <div v-if="typeof m.rolle === 'string'" class="pr-dek-zeile">
              <label class="pr-dek-label">Welche Personen als Wert?
                <select class="dk-form-select" :value="m.rolle" @change="merkmalsRolleSetzen(m, $event.target.value)">
                  <option v-for="r in kontext.rollen || []" :key="r.id" :value="'@' + r.id">{{ r.name || r.id }}</option>
                </select>
              </label>
              <button type="button" class="dk-btn dk-btn-ghost dk-btn-sm" @click="delete m.rolle">Rollenreferenz lösen</button>
            </div>
            <PrKnotenEditor v-else-if="istKnoten(m.rolle)" :knoten="m.rolle" modus="rolle" :kontext="kontext" />
            <div v-else class="pr-dek-zeile">
              <button type="button" class="dk-btn dk-btn-ghost dk-btn-sm" @click="m.rolle = { merkmal: '' }">+ Welche Personen als Wert? (Rollenfilter)</button>
            </div>
          </template>
        </div>
        <button type="button" class="dk-btn dk-btn-secondary dk-btn-sm" @click="merkmalHinzufuegen(ziel.wert)">+ Eigenschaft hinzufügen</button>
      </div>
    </section>

    <!-- Listen -->
    <section class="pr-dek-abschnitt">
      <h4 class="pr-dek-titel">Eigene Listen</h4>
      <p class="pr-dek-hinweis">
        Benannte Listen, aus denen Felder der Art „Eintrag“ wählen (Bibelarbeiten,
        Spiele, Predigtreihen …). Die Liedliste <code>lieder</code> ist
        eingebaut und wird hier nicht angelegt. Umfang „Plan“ gehört zu einem
        einzelnen Plan und wird beim Vorbereiten befüllt.
      </p>
      <p v-if="!sammlungen.length" class="pr-dek-leer">Keine eigenen Listen — „lieder“ ist eingebaut.</p>
      <div v-for="(s, i) in sammlungen" :key="i" class="pr-dek-karte">
        <div class="pr-dek-zeile">
          <label class="pr-dek-label">Kennung
            <input v-model="s.id" type="text" class="dk-form-input pr-dek-kurz" placeholder="bibelarbeiten" />
          </label>
          <label class="pr-dek-label">Name
            <input v-model="s.name" type="text" class="dk-form-input" placeholder="Bibelarbeiten" />
          </label>
          <label class="pr-dek-label">Umfang
            <select v-model="s.umfang" class="dk-form-select">
              <option value="gemeinde">gemeinde — dauerhafte Liste</option>
              <option value="plan">plan — gehört zum einzelnen Plan</option>
            </select>
          </label>
          <button type="button" class="dk-btn dk-btn-ghost dk-btn-sm" aria-label="Liste entfernen" @click="sammlungen.splice(i, 1)">✕</button>
        </div>
        <PrPfadMeldungen :meldungen="meldungen" :pfad="'sammlungen/' + i" />
        <label class="pr-dek-label">Beschreibung
          <input v-model="s.beschreibung" type="text" class="dk-form-input" placeholder="Was diese Liste enthält" />
        </label>
      </div>
      <button type="button" class="dk-btn dk-btn-secondary dk-btn-sm" @click="sammlungHinzufuegen">+ Liste hinzufügen</button>
    </section>

    <!-- Benannte Rollen -->
    <section class="pr-dek-abschnitt">
      <h4 class="pr-dek-titel">Benannte Rollen</h4>
      <p class="pr-dek-hinweis">
        Rollen legen fest, WER für Felder in Frage kommt, und werden mehrfach
        wiederverwendet (Felder wählen sie per <code>@kennung</code>).
      </p>
      <p v-if="!rollen.length" class="pr-dek-leer">Keine benannten Rollen — Felder legen ihren Filter direkt an.</p>
      <div v-for="(r, i) in rollen" :key="i" class="pr-dek-karte">
        <div class="pr-dek-zeile">
          <label class="pr-dek-label">Kennung
            <input v-model="r.id" type="text" class="dk-form-input pr-dek-kurz" placeholder="mitarbeiter" />
          </label>
          <label class="pr-dek-label">Name
            <input v-model="r.name" type="text" class="dk-form-input" placeholder="Mitarbeiter" />
          </label>
          <button type="button" class="dk-btn dk-btn-ghost dk-btn-sm" aria-label="Rolle entfernen" @click="rollen.splice(i, 1)">✕</button>
        </div>
        <PrPfadMeldungen :meldungen="meldungen" :pfad="'rollen/' + i" />
        <PrKnotenEditor v-if="istKnoten(r.filter)" :knoten="r.filter" modus="rolle" :kontext="kontext" />
        <div v-else class="pr-dek-zeile">
          <button type="button" class="dk-btn dk-btn-ghost dk-btn-sm" @click="r.filter = { merkmal: '' }">+ Filter hinzufügen</button>
        </div>
      </div>
      <button type="button" class="dk-btn dk-btn-secondary dk-btn-sm" @click="rollenHinzufuegen">+ Rolle hinzufügen</button>
    </section>
  </div>
</template>

<script setup>
/**
 * Deklarationen des Plantyps: Planparameter, Merkmale (Person + Sammlungen),
 * eigene Sammlungen und benannte Rollen — alles in place auf der Definition.
 */
import { computed } from 'vue'
import PrKnotenEditor from './PrKnotenEditor.vue'
import PrPfadMeldungen from './PrPfadMeldungen.vue'
import { PARAMETER_ARTEN, MERKMALS_ARTEN, merkmalsZiele } from './editor.mjs'

const props = defineProps({
  definition: { type: Object, required: true },
  kontext: { type: Object, default: () => ({}) },
  meldungen: { type: Array, default: () => [] }, // Prüfmeldungen (Inline am Pfad)
})

/** Nur vorhandene Listen rendern — Anlegen per Knopf, nie im Render. */
function vorhandeneListe(schluessel) {
  return Array.isArray(props.definition[schluessel]) ? props.definition[schluessel] : []
}
function sicherListe(schluessel) {
  if (!Array.isArray(props.definition[schluessel])) props.definition[schluessel] = []
  return props.definition[schluessel]
}

const parameter = computed(() => vorhandeneListe('parameter'))
const sammlungen = computed(() => vorhandeneListe('sammlungen'))
const rollen = computed(() => vorhandeneListe('rollen'))
const ziele = computed(() => merkmalsZiele(props.definition))

function parameterHinzufuegen() { sicherListe('parameter').push({ id: '', art: 'text', name: '' }) }
function sammlungHinzufuegen() { sicherListe('sammlungen').push({ id: '', name: '', umfang: 'gemeinde' }) }
function rollenHinzufuegen() { sicherListe('rollen').push({ id: '', name: '' }) }

function merkmaleListe(ziel) {
  const m = props.definition.merkmale
  return m && typeof m === 'object' && Array.isArray(m[ziel]) ? m[ziel] : []
}
function merkmaleVon(ziel) {
  if (!props.definition.merkmale || typeof props.definition.merkmale !== 'object') props.definition.merkmale = {}
  if (!Array.isArray(props.definition.merkmale[ziel])) props.definition.merkmale[ziel] = []
  return props.definition.merkmale[ziel]
}
function merkmalHinzufuegen(ziel) { merkmaleVon(ziel).push({ id: '', art: 'tag', name: '' }) }

function istKnoten(wert) {
  return !!wert && typeof wert === 'object' && !Array.isArray(wert)
}

/** Rollenreferenz eines Personen-Merkmalwerts setzen ('@x' bleibt String). */
function merkmalsRolleSetzen(m, wert) {
  if (wert) m.rolle = wert
  else delete m.rolle
}

function listeSetzen(obj, schluessel, roh) {
  const werte = String(roh || '').split(',').map((s) => s.trim()).filter(Boolean)
  if (werte.length) obj[schluessel] = werte
  else delete obj[schluessel]
}

</script>

<style scoped>
.pr-dek { display: flex; flex-direction: column; gap: 20px; }
.pr-dek-titel { font-size: 0.76rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: var(--dk-text-muted); margin: 0 0 4px; }
.pr-dek-hinweis { font-size: 0.82rem; color: var(--dk-text-muted); margin: 0 0 10px; line-height: 1.5; }
.pr-dek-hinweis code { font-size: 0.78rem; background: var(--dk-surface-2); padding: 1px 4px; border-radius: 4px; }
.pr-dek-ziel + .pr-dek-ziel { margin-top: 14px; }
.pr-dek-ziel-titel { font-size: 0.8rem; font-weight: 600; color: var(--dk-text); margin: 0 0 8px; }
.pr-dek-karte { border: 1px solid var(--dk-border); border-radius: 10px; background: var(--dk-surface); padding: 8px 10px; display: flex; flex-direction: column; gap: 8px; }
.pr-dek-karte + .pr-dek-karte { margin-top: 8px; }
.pr-dek-leer { font-size: 0.8rem; color: var(--dk-text-muted); margin: 0 0 8px; }
.pr-dek-zeile { display: flex; align-items: flex-end; gap: 10px; flex-wrap: wrap; }
.pr-dek-label { display: flex; flex-direction: column; gap: 4px; font-size: 0.8rem; font-weight: 600; color: var(--dk-text-muted); }
.pr-dek-kurz { max-width: 180px; font-family: ui-monospace, monospace; }
.pr-dek-schalter { display: inline-flex; align-items: center; gap: 6px; font-size: 0.82rem; color: var(--dk-text); cursor: pointer; padding-bottom: 8px; }
.pr-dek-details summary { cursor: pointer; font-size: 0.8rem; color: var(--dk-text-muted); }
@media (max-width: 640px) { .pr-dek-kurz { max-width: none; width: 100%; } }
</style>
