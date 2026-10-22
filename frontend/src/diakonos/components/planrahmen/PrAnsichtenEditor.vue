<template>
  <div class="pr-an">
    <p class="pr-an-hinweis">
      Ansichten sind Ausgaben des Plans (Aushang, Chorleiter, Programmheft …).
      In den Formatvorlagen stehen Platzhalter in geschweiften Klammern, z. B.
      <code>{eintrag.titel}</code> oder <code>{dirigent.kuerzel}</code>. Ein
      Platzhalter darf eine Bedingung tragen: <code>{gaeste: + {gaeste.vorname}}</code>
      zeigt den Text nur, wenn <code>gaeste</code> gefüllt ist.
    </p>

    <p v-if="!ansichten.length" class="pr-an-leer">Keine Ansicht — der Plan wird als Tabelle angezeigt.</p>

    <div v-for="(a, i) in ansichten" :key="i" class="pr-an-karte">
      <div class="pr-an-zeile">
        <label class="pr-an-label">Art
          <select v-model="a.art" class="dk-form-select">
            <option v-for="art in ANSICHTS_ARTEN" :key="art.wert" :value="art.wert">{{ art.name }}</option>
          </select>
        </label>
        <PrPfadMeldungen :meldungen="meldungen" :pfad="'ansichten/' + i + '/art'" />
        <label class="pr-an-label">Name (optional)
          <input v-model="a.name" type="text" class="dk-form-input" placeholder="Aushang" />
        </label>
        <PrPfadMeldungen :meldungen="meldungen" :pfad="'ansichten/' + i + '/name'" />
        <button type="button" class="dk-btn dk-btn-ghost dk-btn-sm" aria-label="Ansicht entfernen" @click="ansichten.splice(i, 1)">✕</button>
      </div>
      <PrPfadMeldungen :meldungen="meldungen" :pfad="'ansichten/' + i" exakt />

      <!-- Spalten -->
      <div v-if="a.art === 'tabelle' || a.art === 'druck' || a.art === 'kalender'" class="pr-an-block">
        <template v-if="a.art === 'kalender'">
          <label class="pr-an-schalter"><input type="checkbox" :checked="a.spalten === 'monat'" @change="kalenderSpalten(a, $event.target.checked)" /> Monatsspalte statt Feldspalten</label>
        </template>
        <div v-if="a.spalten !== 'monat'" class="pr-an-chips">
          <label v-for="f in feldPfade" :key="f.pfad" class="pr-an-chip">
            <input type="checkbox" :checked="(spaltenVon(a) || []).includes(f.pfad)" @change="spaltenToggle(a, f.pfad, $event.target.checked)" />
            {{ f.name || f.pfad }}
          </label>
        </div>
        <PrPfadMeldungen :meldungen="meldungen" :pfad="'ansichten/' + i + '/spalten'" />
        <template v-if="a.art === 'kalender'">
          <label class="pr-an-schalter"><input v-model="a.alle_tage" type="checkbox" /> Auch Tage ohne Termin zeigen</label>
          <label class="pr-an-schalter"><input v-model="a.kw" type="checkbox" /> Kalenderwochen-Spalte</label>
          <label class="pr-an-label">Papierformat
            <select v-model="a.druck" class="dk-form-select">
              <option v-for="d in DRUCK_FORMATE" :key="d.wert" :value="d.wert">{{ d.name }}</option>
            </select>
          </label>
        </template>
      </div>

      <div v-if="a.art === 'raster'" class="pr-an-block">
        <label class="pr-an-label">Was bildet eine Zeile?
          <input v-model="a.zeilen" type="text" class="dk-form-input" placeholder="termin" />
        </label>
        <PrPfadMeldungen :meldungen="meldungen" :pfad="'ansichten/' + i + '/zeilen'" />
      </div>

      <div v-if="a.art === 'druck'" class="pr-an-block">
        <label class="pr-an-label">Papierformat
          <select v-model="a.druck" class="dk-form-select">
            <option v-for="d in DRUCK_FORMATE" :key="d.wert" :value="d.wert">{{ d.name }}</option>
          </select>
        </label>
        <PrPfadMeldungen :meldungen="meldungen" :pfad="'ansichten/' + i + '/druck'" />
      </div>

      <div v-if="a.art === 'programm'" class="pr-an-block">
        <label class="pr-an-label">Überschrift (Kopf)
          <input v-model="a.kopf" type="text" class="dk-form-input" placeholder="{plan.titel} {termin.datum}" />
        </label>
        <PrPfadMeldungen :meldungen="meldungen" :pfad="'ansichten/' + i + '/kopf'" />
        <label class="pr-an-label">Fußzeile
          <input v-model="a.fuss" type="text" class="dk-form-input" placeholder="{parameter.schlusswort}" />
        </label>
        <PrPfadMeldungen :meldungen="meldungen" :pfad="'ansichten/' + i + '/fuss'" />
        <label class="pr-an-label">Papierformat
          <select v-model="a.druck" class="dk-form-select">
            <option v-for="d in DRUCK_FORMATE" :key="d.wert" :value="d.wert">{{ d.name }}</option>
          </select>
        </label>
      </div>

      <!-- Formatvorlagen mit Live-Vorschau -->
      <div class="pr-an-block">
        <h5 class="pr-an-titel">Formatvorlagen der Zellen</h5>
        <PrPfadMeldungen :meldungen="meldungen" :pfad="'ansichten/' + i + '/format'" exakt />
        <div v-for="(vorlage, schluessel) in formatVon(a)" :key="schluessel" class="pr-an-format">
          <input
            :value="schluessel" type="text" class="dk-form-input pr-an-schluessel"
            list="pr-an-feldpfade" aria-label="Feld"
            @change="formatSchluesselWechseln(a, schluessel, $event.target.value)"
          />
          <input v-model="a.format[schluessel]" type="text" class="dk-form-input" placeholder="{eintrag.buch} {eintrag.titel}" aria-label="Formatvorlage" />
          <button type="button" class="dk-btn dk-btn-ghost dk-btn-sm" aria-label="Formatvorlage entfernen" @click="delete a.format[schluessel]">✕</button>
          <p class="pr-an-vorschau">Vorschau: {{ formatVorschau(a.format[schluessel]) }}</p>
          <div class="pr-an-formatfehler"><PrPfadMeldungen :meldungen="meldungen" :pfad="'ansichten/' + i + '/format/' + schluessel" /></div>
        </div>
        <datalist id="pr-an-feldpfade">
          <option v-for="f in feldPfade" :key="f.pfad" :value="f.pfad" />
        </datalist>
        <button type="button" class="dk-btn dk-btn-ghost dk-btn-sm" @click="formatHinzufuegen(a)">+ Formatvorlage hinzufügen</button>
      </div>
    </div>

    <button type="button" class="dk-btn dk-btn-secondary dk-btn-sm" @click="ansichten.push({ art: 'tabelle', name: '' })">+ Ansicht hinzufügen</button>
  </div>
</template>

<script setup>
/**
 * Ansichten-Editor: Art, Spalten, Druck, Kalender-/Programm-Einstellungen
 * und Formatvorlagen mit lebender Beispielvorschau (formatTemplate mit
 * Beispielwerten aus der eigenen Definition — keine erfundenen Inhalte).
 */
import { computed } from 'vue'
import PrPfadMeldungen from './PrPfadMeldungen.vue'
import { ANSICHTS_ARTEN, DRUCK_FORMATE, feldPfadListe } from './editor.mjs'
import { formatTemplate } from './format.mjs'

const props = defineProps({
  ansichten: { type: Array, required: true },
  definition: { type: Object, required: true },
  meldungen: { type: Array, default: () => [] }, // Prüfmeldungen (Inline am Pfad)
})

/** Alle Feldpfade der Definition (Kurzform und Terminreihen). */
const feldPfade = computed(() => {
  const liste = []
  if (Array.isArray(props.definition.felder)) liste.push(...feldPfadListe(props.definition.felder))
  for (const reihe of props.definition.terminreihen || []) {
    for (const f of feldPfadListe(reihe.felder || [])) {
      liste.push({ ...f, pfad: f.pfad }) // Reihenpräfix: Kalenderformate nutzen 'reihe:feld'
    }
  }
  return liste
})

/** Beispielkontext für die Formatvorschau — nur Struktur aus der Definition. */
const beispiel = computed(() => {
  const ctx = { plan: { titel: props.definition.name || 'Plan' }, termin: { datum: 'TT.MM.JJJJ', uhrzeit: '', titel: '', anlass: '' }, parameter: {} }
  for (const p of props.definition.parameter || []) {
    ctx.parameter[p.id] = p.art === 'auswahl' ? (p.werte || ['…'])[0] : p.art === 'zahl' ? 0 : p.art === 'datum' ? 'TT.MM.JJJJ' : '…'
  }
  const setzen = (felder) => {
    for (const f of felder || []) {
      if (!f?.id) continue
      ctx[f.id] = wertFuer(f)
      if (Array.isArray(f.inhalt)) {
        const unter = {}
        for (const u of f.inhalt) if (u?.id) unter[u.id] = wertFuer(u)
        if (Object.keys(unter).length) ctx[f.id] = { ...(typeof ctx[f.id] === 'object' ? ctx[f.id] : {}), ...unter }
      }
    }
  }
  setzen(props.definition.felder)
  for (const reihe of props.definition.terminreihen || []) setzen(reihe.felder)
  return ctx
})

function wertFuer(f) {
  if (['person', 'personen', 'team'].includes(f.art)) return { name: 'Name', kuerzel: 'KA' }
  if (f.art === 'eintrag') return { titel: 'Titel', buch: 'GB', nummer: '1' }
  if (f.art === 'zahl') return 0
  if (f.art === 'datum') return 'TT.MM.JJJJ'
  if (f.art === 'auswahl') return (f.werte || ['…'])[0]
  return '…'
}

function formatVon(ansicht) {
  if (!ansicht.format || typeof ansicht.format !== 'object') return {}
  return ansicht.format
}
function formatVorschau(vorlage) {
  if (!vorlage) return '—'
  try { return formatTemplate(vorlage, beispiel.value) || '—' } catch { return '—' }
}
function formatHinzufuegen(ansicht) {
  if (!ansicht.format || typeof ansicht.format !== 'object') ansicht.format = {}
  const feld = feldPfade.value[0]?.pfad || ''
  ansicht.format[feld] = ''
}
function formatSchluesselWechseln(ansicht, alt, neu) {
  if (alt === neu || !neu) return
  if (!ansicht.format || typeof ansicht.format !== 'object') ansicht.format = {}
  ansicht.format[neu] = ansicht.format[alt]
  delete ansicht.format[alt]
}

function spaltenVon(ansicht) {
  return Array.isArray(ansicht.spalten) ? ansicht.spalten : []
}
function spaltenToggle(ansicht, pfad, an) {
  const liste = spaltenVon(ansicht).slice()
  const i = liste.indexOf(pfad)
  if (an && i === -1) liste.push(pfad)
  if (!an && i !== -1) liste.splice(i, 1)
  if (liste.length) ansicht.spalten = liste
  else delete ansicht.spalten
}
function kalenderSpalten(ansicht, monat) {
  if (monat) ansicht.spalten = 'monat'
  else delete ansicht.spalten
}
</script>

<style scoped>
.pr-an { display: flex; flex-direction: column; gap: 12px; }
.pr-an-hinweis { font-size: 0.82rem; color: var(--dk-text-muted); margin: 0; line-height: 1.5; }
.pr-an-hinweis code { font-size: 0.78rem; background: var(--dk-surface-2); padding: 1px 4px; border-radius: 4px; }
.pr-an-leer { font-size: 0.8rem; color: var(--dk-text-muted); margin: 0; }
.pr-an-karte { border: 1px solid var(--dk-border); border-radius: 10px; background: var(--dk-surface); padding: 10px 12px; display: flex; flex-direction: column; gap: 10px; }
.pr-an-zeile { display: flex; align-items: flex-end; gap: 10px; flex-wrap: wrap; }
.pr-an-label { display: flex; flex-direction: column; gap: 4px; font-size: 0.8rem; font-weight: 600; color: var(--dk-text-muted); }
.pr-an-block { display: flex; flex-direction: column; gap: 8px; border-top: 1px solid var(--dk-divider); padding-top: 8px; }
.pr-an-titel { font-size: 0.74rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: var(--dk-text-muted); margin: 0; }
.pr-an-chips { display: flex; flex-wrap: wrap; gap: 6px 12px; }
.pr-an-chip { display: inline-flex; align-items: center; gap: 5px; font-size: 0.82rem; color: var(--dk-text); cursor: pointer; }
.pr-an-schalter { display: inline-flex; align-items: center; gap: 6px; font-size: 0.82rem; color: var(--dk-text); cursor: pointer; }
.pr-an-format { display: grid; grid-template-columns: minmax(120px, 200px) 1fr auto; gap: 6px; align-items: center; }
.pr-an-formatfehler { grid-column: 1 / -1; }
.pr-an-schluessel { font-family: ui-monospace, monospace; font-size: 0.82rem; }
.pr-an-vorschau { grid-column: 1 / -1; font-size: 0.78rem; color: var(--dk-text-muted); margin: 0; font-style: italic; }
@media (max-width: 640px) { .pr-an-format { grid-template-columns: 1fr; } }
</style>
