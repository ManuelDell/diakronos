<template>
  <DkModal variant="planrahmen" v-model="offen" title="Wert bearbeiten" footer-sticky>
    <div class="pr-ed">
      <div v-if="fehlerListe.length" class="pr-ed-block">
        <PrMeldungen :meldungen="fehlerListe" />
      </div>

      <div v-if="slot" class="pr-ed-kopf">
        <span class="pr-ed-kopf-zeile">
          Termin: <strong>{{ datumText(termin?.datum) }}</strong><template v-if="termin?.titel"> — {{ termin.titel }}</template>
        </span>
        <span class="pr-ed-kopf-zeile">{{ frage }}</span>
        <span v-if="aktuellText" class="pr-ed-kopf-zeile">
          Aktuell: <strong>{{ aktuellText }}</strong>
          <span v-if="eintragZiel?.fixiert" class="pr-ed-pin" title="Von Hand festgelegt">📌 von Hand festgelegt</span>
        </span>
      </div>

      <!-- Unterfelder in Klartext: Reiter mit dem Namen des angeklickten Eintrags.
           Auf schmalen Geräten als Auswahlliste statt vieler Buttons (UX C1). -->
      <div v-if="unterZiele.length" class="pr-ed-feld">
        <label v-if="schmal" for="pr-ed-wahl" class="pr-ed-label" id="pr-ed-wahl-label">Was möchtest du ändern?</label>
        <select
          v-if="schmal"
          id="pr-ed-wahl" class="dk-form-select pr-ed-auswahl"
          :value="zielPfad" aria-labelledby="pr-ed-wahl-label"
          @change="zielPfad = $event.target.value"
        >
          <option v-for="u in unterZiele" :key="u.pfad" :value="u.pfad">{{ u.name }}</option>
        </select>
        <template v-else>
          <span id="pr-ed-wahl-label" class="pr-ed-label">Was möchtest du ändern?</span>
          <div class="pr-ed-reiter" role="tablist" aria-labelledby="pr-ed-wahl-label">
            <button
              v-for="u in unterZiele" :key="u.pfad" type="button" role="tab"
              class="dk-btn dk-btn-secondary dk-btn-sm"
              :class="{ 'is-active': zielPfad === u.pfad }"
              :aria-selected="zielPfad === u.pfad ? 'true' : 'false'"
              @click="zielPfad = u.pfad"
            >{{ u.name }}</button>
          </div>
        </template>
      </div>

      <div v-if="!slot && !unterZiele.length" class="pr-ed-leer">
        <template v-if="kannPlatzHinzufuegen">
          <p>Dieses Feld ist noch leer. Du kannst einen Platz anlegen und selbst besetzen.</p>
          <button
            type="button" class="dk-btn dk-btn-secondary dk-btn-sm"
            :disabled="platzLaedt" @click="platzAnlegen"
          >{{ platzLaedt ? 'Wird angelegt …' : platzLabel }}</button>
        </template>
        <template v-else>Dieses Feld kann hier nicht direkt bearbeitet werden.</template>
      </div>

      <template v-if="slot">
        <div v-if="KANDIDATEN_ARTEN.has(art)" class="pr-ed-feld">
          <label for="pr-ed-suche" class="pr-ed-label">Vorschläge durchsuchen</label>
          <input id="pr-ed-suche" v-model="suche" type="search" class="dk-form-input" placeholder="Name oder Titel …" />
        </div>

        <!-- ST2: Lied-Auswahl nach Tags filtern (nur Sammlung 'lieder').
             Die Tags kommen deklariert am Kandidaten mit; rein clientseitig. -->
        <div v-if="tagFilterMerkmale.length" class="pr-ed-feld pr-ed-tagfilter">
          <span class="pr-ed-label">Nach Tags filtern</span>
          <div class="pr-ed-tagfilter-reihe">
            <label
              v-for="m in tagFilterMerkmale" :key="m.id"
              class="pr-ed-tagfilter-feld"
            >
              <span class="pr-ed-tagfilter-name">{{ m.name || m.id }}</span>
              <select
                class="dk-form-select pr-ed-tagfilter-wahl"
                :value="tagFilter[m.id]?.[0] || ''"
                @change="tagFilterSetzen(m.id, $event.target.value)"
              >
                <option value="">Alle</option>
                <option v-for="w in tagFilterWerte[m.id] || []" :key="w" :value="w">{{ tagFilterAnzeige(m, w) }}</option>
              </select>
            </label>
            <button
              v-if="tagFilterAktiv" type="button"
              class="dk-btn dk-btn-ghost dk-btn-xs" @click="tagFilterLeeren"
            >Filter zurücksetzen</button>
          </div>
        </div>
        <div v-if="kandidatenLaedt" class="pr-ed-leer">Lade Vorschläge …</div>

        <div v-else-if="kandidatenFehler.length" class="pr-ed-block">
          <PrMeldungen :meldungen="kandidatenFehler" />
        </div>

        <!-- Einzelwahl aus Kandidaten (Person, Team, Sammlungseintrag, Auswahl) -->
        <fieldset v-else-if="istEinzelwahl" class="pr-ed-gruppe">
          <legend class="pr-ed-legend">Vorschläge ({{ kandidatenListe.length }}) — bitte wählen</legend>
          <label
            v-for="k in kandidatenListe"
            :key="kennung(k)"
            class="pr-ed-wahl"
            :class="{ 'pr-ed-wahl--gesetzt': wahl === kennung(k) }"
          >
            <input
              type="radio" class="pr-ed-input"
              :name="'pr-ed-' + pfadSchluessel"
              :value="kennung(k)"
              v-model="wahl"
            />
            <span class="pr-ed-wahl-text">
              <span class="pr-ed-wahl-name">{{ anzeige(k) }}</span>
              <span v-if="neben(k)" class="pr-ed-wahl-neben">{{ neben(k) }}</span>
            </span>
            <span v-if="bewertung(k)" class="dk-badge pr-ed-badge" :class="bewertung(k).klasse" :title="bewertung(k).text">{{ bewertung(k).text }}</span>
          </label>
          <div v-if="!kandidatenListe.length" class="pr-ed-leer">
            Keine Vorschläge vorhanden — bitte zuerst Stammdaten prüfen.
          </div>
        </fieldset>

        <!-- Mehrfachauswahl (Personen, mehrfache Auswahl) -->
        <fieldset v-else-if="istMehrfachwahl" class="pr-ed-gruppe">
          <legend class="pr-ed-legend">Vorschläge ({{ kandidatenListe.length }}) — mehrfach auswählbar</legend>
          <label
            v-for="k in kandidatenListe"
            :key="kennung(k)"
            class="pr-ed-wahl"
            :class="{ 'pr-ed-wahl--gesetzt': wahlListe.includes(kennung(k)) }"
          >
            <input type="checkbox" class="pr-ed-input" :value="kennung(k)" v-model="wahlListe" />
            <span class="pr-ed-wahl-text">
              <span class="pr-ed-wahl-name">{{ anzeige(k) }}</span>
              <span v-if="neben(k)" class="pr-ed-wahl-neben">{{ neben(k) }}</span>
            </span>
            <span v-if="bewertung(k)" class="dk-badge pr-ed-badge" :class="bewertung(k).klasse" :title="bewertung(k).text">{{ bewertung(k).text }}</span>
          </label>
          <div v-if="!kandidatenListe.length" class="pr-ed-leer">
            Keine Vorschläge vorhanden — bitte zuerst Stammdaten prüfen.
          </div>
        </fieldset>

        <!-- Freie Werte nach Feldart -->
        <div v-else-if="art === 'text'" class="pr-ed-feld">
          <label class="pr-ed-label" for="pr-ed-text">Text</label>
          <textarea id="pr-ed-text" class="dk-form-textarea" rows="3" :value="stringWert" @input="wahl = $event.target.value"></textarea>
        </div>

        <div v-else-if="art === 'zahl'" class="pr-ed-feld">
          <label class="pr-ed-label" for="pr-ed-zahl">Zahl</label>
          <input
            id="pr-ed-zahl" type="number" class="dk-form-input"
            :value="wahl === null || wahl === undefined ? '' : wahl"
            @input="zahlSetzen($event.target.value)"
          />
        </div>

        <div v-else-if="art === 'datum'" class="pr-ed-feld">
          <label class="pr-ed-label" for="pr-ed-datum">Datum</label>
          <input
            id="pr-ed-datum" type="date" class="dk-form-input"
            :value="stringWert" @change="wahl = $event.target.value || null"
          />
        </div>

        <div v-else-if="art === 'tag'" class="pr-ed-feld">
          <label class="pr-ed-label" for="pr-ed-tag">Angabe</label>
          <select id="pr-ed-tag" class="dk-form-select" :value="tagWahl" @change="tagWahl = $event.target.value">
            <option value="">— leer —</option>
            <option value="ja">Ja</option>
            <option value="nein">Nein</option>
          </select>
        </div>

        <div v-else class="pr-ed-feld">
          <label class="pr-ed-label" for="pr-ed-roh">Wert</label>
          <input
            id="pr-ed-roh" type="text" class="dk-form-input"
            :value="stringWert" @input="wahl = $event.target.value || null"
          />
        </div>

        <div v-if="auswahlWarnung" class="pr-ed-warnung">{{ auswahlWarnung }}</div>

        <PrMeldungen v-if="feldMeldungen.length" :meldungen="feldMeldungen" kompakt />
      </template>
    </div>

    <template #footer>
      <button type="button" class="dk-btn dk-btn-ghost" @click="schliessen">Abbrechen</button>
      <button
        v-if="eintragZiel?.fixiert"
        type="button" class="dk-btn dk-btn-secondary"
        :disabled="speichert || kandidatenLaedt"
        aria-label="Von Hand festgelegten Wert freigeben"
        @click="loesen"
      >Wieder vorschlagen lassen</button>
      <button
        type="button" class="dk-btn dk-btn-primary"
        :disabled="!slot || speichert || kandidatenLaedt || !gueltig"
        @click="uebernehmen"
      >{{ speichert ? 'Wird gespeichert …' : 'Übernehmen' }}</button>
    </template>
  </DkModal>
</template>

<script setup>
/**
 * Generischer Bearbeitungs-Dialog für einen Plan-Rahmen-Slot.
 *
 * Öffnet auf einen geklickten Zellenpfad. Ist der Pfad kein eigener
 * Einzelplatz (Gruppe, wiederholte Instanz, Ablauf-Unterfeld), zeigt
 * der Dialog die benachbarten Einzelplätze als Auswahl. Kandidaten,
 * Feldart und Bedarfsmeldungen kommen ausschließlich vom Server
 * (feld_kandidaten), Werte werden über eintrag_setzen/eintrag_loesen
 * geschrieben — keine Freitext-Zuordnungen, keine erfundenen Pfade.
 */
import { ref, computed, watch, inject, onMounted, onUnmounted } from 'vue'
import DkModal from '../DkModal.vue'
import PrMeldungen from './PrMeldungen.vue'
import { usePlanrahmen, datumText, wertText, fehlerMeldungen, feldGehoertZu, anzahlBereich } from '../../composables/usePlanrahmen.js'
import { feldInfo, meldungsKurz, kandidatenHinweise } from './klartext.mjs'
import { wertAnzeige } from './auswahlwerte.mjs'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  plan: { type: String, default: '' },
  termin: { type: Object, default: null },
  feldPfad: { type: String, default: '' },
  // Einzelplätze des Termins aus termin_struktur (Server-Slots).
  slots: { type: Array, default: () => [] },
  // Aktive Versionsdefinition des Termins (für Klartext-Beschriftungen).
  definition: { type: Object, default: () => ({}) },
  eintraege: { type: Array, default: () => [] },
})
const emit = defineEmits(['update:modelValue', 'gespeichert', 'geloest', 'platz-hinzugefuegt'])

const { feldKandidaten, eintragSetzen, eintragLoesen, platzHinzufuegen } = usePlanrahmen()

const offen = computed({
  get: () => !!props.modelValue,
  set: (v) => emit('update:modelValue', v),
})

// ── Schmale Geräte (≤480px): Auswahlliste statt Buttonwand (UX C1) ──────────
const schmal = ref(false)
let mq = null
function mqAktualisieren(e) { schmal.value = e.matches }
onMounted(() => {
  if (typeof window !== 'undefined' && window.matchMedia) {
    mq = window.matchMedia('(max-width: 480px)')
    schmal.value = mq.matches
    mq.addEventListener('change', mqAktualisieren)
  }
})
onUnmounted(() => { if (mq) mq.removeEventListener('change', mqAktualisieren) })

const zielPfad = ref('')
const suche = ref('')
const wahl = ref(null)
const kandidatenDaten = ref(null)
const kandidatenAnzeige = ref({})
const planAnzeige = inject('planrahmenAnzeige', null)
const kandidatenAngaben = computed(() => props.definition?.merkmale?.[slot.value?.sammlung || feldDeklaration.value?.sammlung] || [])
const kandidatenLaedt = ref(false)
const kandidatenFehler = ref([])
const fehlerListe = ref([])
const speichert = ref(false)

// ── Slot und Unterfelder ───────────────────────────────────────────────────

const slot = computed(() => props.slots.find((s) => s.feld_pfad === zielPfad.value) || null)
const art = computed(() => slot.value?.art || '')
const feldDeklaration = computed(() => slot.value?.feld || {})

const KANDIDATEN_ARTEN = new Set(['person', 'personen', 'team', 'eintrag', 'auswahl'])
const istMehrfach = computed(() => art.value === 'personen' || !!feldDeklaration.value.mehrfach)
const istEinzelwahl = computed(() => KANDIDATEN_ARTEN.has(art.value) && !istMehrfach.value)
const istMehrfachwahl = computed(() => KANDIDATEN_ARTEN.has(art.value) && istMehrfach.value)

/** Nachbar-Einzelplätze, wenn der geklickte Pfad selbst keiner ist. */
const unterZiele = computed(() => {
    if (props.slots.some((s) => s.feld_pfad === props.feldPfad)) return []
    const p = props.feldPfad
    return props.slots
        .filter((s) => feldGehoertZu(s.feld_pfad, p))
        .map((s) => ({ pfad: s.feld_pfad, name: unterName(s) }))
})

function unterName(s) {
    // Instanzkontext bleibt auch bei Zeilenumbruch im Reiter eindeutig.
    return feldInfo(s.feld_pfad, props.definition, props.termin).name
}

/** Klare Frage in Klartext statt interner Feldnamen. */
const frage = computed(() => {
    const eintrag = props.slots.find((s) => s.feld_pfad === zielPfad.value)
    const info = feldInfo(eintrag?.feld_pfad || props.feldPfad, props.definition, props.termin)
    const bezeichnung = info.name.split(' · ').slice(0, -1).join(' · ')
    const ziel = bezeichnung || info.name
    if (zielPfad.value && eintrag) return `Was möchtest du für ${ziel} ändern?`
    if (!unterZiele.value.length) return `Was möchtest du für ${info.name} eintragen?`
    return `Was möchtest du an ${info.name} ändern?`
})

const eintragZiel = computed(() =>
    props.eintraege.find((e) => e.termin === props.termin?.id && e.feld_pfad === zielPfad.value) || null)

// ── Optionalen Platz anlegen (UX FACH 2 / B) ───────────────────────────────
// Nur ein optionales Mehrfachfeld (anzahl 'min..max', z. B. einueben '0..2')
// kennt zusaetzliche Plaetze. Der Server validiert Obergrenze und Rechte.
const feldDeklarationFeld = computed(() =>
    feldInfo(props.feldPfad, props.definition, props.termin).feld || null)

const kannPlatzHinzufuegen = computed(() => {
    // Nur wenn der geklickte Feldpfad selbst noch keinen Platz hat — andere
    // Slots desselben Termins (z. B. Lied, Einsingen) duerfen die Aktion nicht
    // verdecken. Der Server validiert Obergrenze und Rechte erneut.
    if (slot.value || unterZiele.value.length) return false
    const d = feldDeklarationFeld.value
    if (!d) return false
    const bereich = anzahlBereich(d.anzahl)
    return ['eintrag', 'personen', 'team', 'text', 'zahl'].includes(d.art)
        && typeof d.anzahl === 'string' && d.anzahl.includes('..') && bereich.max !== null
})

const platzLabel = computed(() => {
    const d = feldDeklarationFeld.value
    const name = (d?.name || feldInfo(props.feldPfad, props.definition, props.termin).name || 'Eintrag').toString()
    return '+ ' + name + ' hinzufügen'
})

const platzLaedt = ref(false)

async function platzAnlegen() {
    if (!props.plan || !props.termin?.id) return
    platzLaedt.value = true
    fehlerListe.value = []
    try {
        const erg = await platzHinzufuegen(props.plan, props.termin.id, props.feldPfad)
        emit('platz-hinzugefuegt', { feld_pfad: erg?.feld_pfad || props.feldPfad })
    } catch (err) {
        fehlerListe.value = fehlerMeldungen(err)
    } finally {
        platzLaedt.value = false
    }
}

const feldName = computed(() => {
    const d = feldDeklaration.value
    return d?.name || d?.id || (zielPfad.value ? zielPfad.value.split(/[.:/]/).pop() : '')
})
const pfadSchluessel = computed(() => zielPfad.value.replace(/[^a-zA-Z0-9_-]/g, ''))
const aktuellText = computed(() => {
    const w = eintragZiel.value?.wert
    if (w === null || w === undefined || w === '') return ''
    return wertText(w)
})

// ── Start und Zielwechsel ──────────────────────────────────────────────────

let kandidatenAufruf = 0

watch([zielPfad, () => props.slots, () => props.plan, () => props.termin?.id], () => {
    if (!props.modelValue) return
    wahlZuruecksetzen()
    tagFilter.value = {}
    ladeKandidaten()
})

watch(() => props.modelValue, (an) => {
    if (an) starten()
    else {
        kandidatenAufruf++
        kandidatenDaten.value = null
        kandidatenFehler.value = []
        kandidatenLaedt.value = false
    }
})

function starten() {
    fehlerListe.value = []
    suche.value = ''
    tagFilter.value = {}
    kandidatenDaten.value = null
    kandidatenFehler.value = []
    zielPfad.value = props.feldPfad
    // Erster Einzelplatz als Vorauswahl, wenn der Klick auf einem
    // Gruppen-/Instanzenpfad landete.
    if (unterZiele.value.length && !props.slots.some((s) => s.feld_pfad === props.feldPfad)) {
        zielPfad.value = unterZiele.value[0].pfad
    }
    wahlZuruecksetzen()
    ladeKandidaten()
}

function wahlZuruecksetzen() {
    const wert = eintragZiel.value?.wert ?? null
    if (istMehrfach.value) {
        wahl.value = Array.isArray(wert) ? wert.slice() : (wert === null || wert === '' ? [] : [wert])
    } else {
        wahl.value = wert
    }
}

async function ladeKandidaten() {
    const aufruf = ++kandidatenAufruf
    const plan = props.plan
    const termin = props.termin?.id
    const pfad = zielPfad.value
    const aktuell = () => aufruf === kandidatenAufruf && props.modelValue
        && props.plan === plan && props.termin?.id === termin && zielPfad.value === pfad
    kandidatenDaten.value = null
    kandidatenFehler.value = []
    kandidatenLaedt.value = false
    if (!props.modelValue || !slot.value || !KANDIDATEN_ARTEN.has(art.value)) return
    kandidatenLaedt.value = true
    try {
        const daten = await feldKandidaten(plan, termin, pfad)
        if (!aktuell()) return
        const namen = { ...(planAnzeige?.value?.anzeige || {}) }
        for (const m of kandidatenAngaben.value.filter(m => m.art === 'person')) {
            const ziel = props.slots.find(s => s.art === 'person' && s.feld?.id === m.id)
            if (!ziel) continue
            const weitere = await feldKandidaten(plan, termin, ziel.feld_pfad)
            if (!aktuell()) return
            for (const k of weitere?.kandidaten || []) if (k.kennung) namen[k.kennung] = k
        }
        if (aktuell()) {
            kandidatenAnzeige.value = namen
            kandidatenDaten.value = daten
        }
    } catch (err) {
        if (aktuell()) kandidatenFehler.value = fehlerMeldungen(err)
    } finally {
        if (aktuell()) kandidatenLaedt.value = false
    }
}

// ── Kandidatendarstellung ──────────────────────────────────────────────────

// ST2: Tags der Sammlung 'lieder' zum Filtern der Lied-Auswahl. Die Merkmale
// kommen deklariert aus der Definition, die Werte aus den geladenen
// Kandidaten (deklarierte Werte am Kandidaten). Rein clientseitig.
const tagFilter = ref({})

const tagFilterMerkmale = computed(() => {
    if (art.value !== 'eintrag' || (slot.value?.sammlung || '') !== 'lieder') return []
    const merkmale = (props.definition?.merkmale?.lieder) || []
    return merkmale.filter(m => m && m.art !== 'person' && Array.isArray(m.werte) && m.werte.length)
})

const tagFilterWerte = computed(() => {
    const ergebnis = {}
    const liste = Array.isArray(kandidatenDaten.value?.kandidaten) ? kandidatenDaten.value.kandidaten : []
    for (const m of tagFilterMerkmale.value) {
        const werte = new Set(m.werte || [])
        for (const k of liste) for (const w of alsListe(k?.merkmale?.[m.id])) werte.add(w)
        ergebnis[m.id] = [...werte].sort((a, b) => String(a).localeCompare(String(b), 'de'))
    }
    return ergebnis
})

const tagFilterAktiv = computed(() => Object.values(tagFilter.value).some(v => (v || []).length))

function alsListe(w) {
    if (w === null || w === undefined || w === '') return []
    return Array.isArray(w) ? w : [w]
}

function tagFilterSetzen(id, wert) {
    tagFilter.value = { ...tagFilter.value, [id]: wert ? [wert] : [] }
}

function tagFilterLeeren() { tagFilter.value = {} }

/** P3-1c (A): Auswahlwerte im Filter als Anzeigename zeigen („Männerchor“). */
function tagFilterAnzeige(merkmal, wert) {
    return wertAnzeige(merkmal, wert)
}

const kandidatenListe = computed(() => {
    const liste = Array.isArray(kandidatenDaten.value?.kandidaten) ? kandidatenDaten.value.kandidaten : []
    const query = suche.value.trim().toLocaleLowerCase('de-DE')
    const aktiv = Object.entries(tagFilter.value).filter(([, werte]) => (werte || []).length)
    return liste.filter((k) => {
        if (query && !anzeige(k).toLocaleLowerCase('de-DE').includes(query)) return false
        for (const [mid, werte] of aktiv) {
            const hat = alsListe(k?.merkmale?.[mid])
            if (!werte.every((w) => hat.includes(w))) return false
        }
        return true
    })
        .slice().sort((a, b) => Number(a?.bewertung?.zulaessig === false) - Number(b?.bewertung?.zulaessig === false)
            || (a?.bewertung?.strafe || 0) - (b?.bewertung?.strafe || 0)
            || anzeige(a).localeCompare(anzeige(b), 'de'))
})

function kennung(k) { return typeof k === 'string' ? k : (k?.kennung ?? '') }

function anzeige(k) {
    if (typeof k === 'string') return k
    const teile = []
    teile.push(k.titel || k.anzeige || k.name || k.kennung || '')
    if (k.buch || k.nr) teile.push([k.buch, k.nr ? 'Nr. ' + k.nr : ''].filter(Boolean).join(' '))
    if (k.seite) teile.push('S. ' + k.seite)
    return teile.filter(Boolean).join(' · ')
}

function neben(k) {
    return typeof k === 'string' ? '' : kandidatenHinweise(k, kandidatenAngaben.value, kandidatenAnzeige.value)
}

function bewertung(k) {
    const b = typeof k === 'string' ? null : k?.bewertung
    if (!b) return null
    if (!b.zulaessig) return { klasse: 'dk-badge-danger', text: 'nicht zulässig' }
    if (b.strafe > 0) {
        // Klartext der wichtigsten Regelmeldung statt Rohscore (z.B. „zuletzt vor 3 Wochen gesungen“).
        const kurz = meldungsKurz((b.meldungen || [])[0], props.definition, props.termin, kandidatenAnzeige.value)
        return { klasse: 'dk-badge-warning', text: kurz || 'Regelhinweis' }
    }
    return null
}

// ── Werteingabe ────────────────────────────────────────────────────────────

const wahlListe = computed({
    get: () => (Array.isArray(wahl.value) ? wahl.value : []),
    set: (v) => { wahl.value = v },
})

const tagWahl = computed({
    get: () => (wahl.value === true ? 'ja' : wahl.value === false ? 'nein' : ''),
    set: (v) => { wahl.value = v === 'ja' ? true : v === 'nein' ? false : null },
})

const stringWert = computed(() =>
    (wahl.value === null || wahl.value === undefined) ? '' : String(wahl.value))

function zahlSetzen(roh) {
    wahl.value = roh === '' ? null : Number(roh)
}

const gueltig = computed(() => {
    if (istMehrfach.value) return Array.isArray(wahl.value) && wahl.value.length > 0
    if (art.value === 'zahl') return typeof wahl.value === 'number' && !Number.isNaN(wahl.value)
    return wahl.value !== null && wahl.value !== undefined && wahl.value !== ''
})

const auswahlWarnung = computed(() => {
    const liste = Array.isArray(wahl.value) ? wahl.value : [wahl.value]
    const treffer = kandidatenListe.value.find((k) => liste.includes(kennung(k)) && bewertung(k))
    if (!treffer) return ''
    return `Hinweis zu „${anzeige(treffer)}“: ${bewertung(treffer).text}. Der Wert wird trotzdem von Hand festgelegt.`
})

const feldMeldungen = computed(() => nachrichten(kandidatenDaten.value?.meldungen))

// ── Speichern und Lösen ────────────────────────────────────────────────────

async function uebernehmen() {
    if (!gueltig.value || !slot.value) return
    speichert.value = true
    fehlerListe.value = []
    try {
        const erg = await eintragSetzen(props.plan, props.termin?.id, zielPfad.value, wahl.value)
        emit('gespeichert', { feld_pfad: zielPfad.value, meldungen: nachrichten(erg?.meldungen) })
        offen.value = false
    } catch (err) {
        fehlerListe.value = fehlerMeldungen(err)
    } finally {
        speichert.value = false
    }
}

async function loesen() {
    speichert.value = true
    fehlerListe.value = []
    try {
        await eintragLoesen(props.plan, props.termin?.id, zielPfad.value)
        emit('geloest', { feld_pfad: zielPfad.value })
        offen.value = false
    } catch (err) {
        fehlerListe.value = fehlerMeldungen(err)
    } finally {
        speichert.value = false
    }
}

function schliessen() { offen.value = false }

/** Engine-Meldungen in freundliche deutsche Anzeigestufen übersetzen. */
function nachrichten(liste) {
    return (liste || []).map((m) => {
        const roh = typeof m === 'string' ? { meldung: m } : (m || {})
        return {
            pfad: roh.pfad || roh.feld_pfad || '',
            code: roh.code || roh.baustein || '',
            feld_pfad: roh.feld_pfad || zielPfad.value,
            termin: props.termin?.id,
            meldung: roh.meldung || 'Unbekannte Meldung.',
            hinweis: roh.hinweis || '',
            stufe: roh.stufe === 'muss' ? 'fehler' : roh.stufe === 'sollte' ? 'warnung' : 'hinweis',
        }
    })
}
</script>

<style scoped>
.pr-ed { display: flex; flex-direction: column; gap: 14px; min-width: 0; }
.pr-ed-block + .pr-ed-block { margin-top: 8px; }
.pr-ed-kopf { display: flex; flex-direction: column; gap: 3px; font-size: 0.84rem; color: var(--dk-text-muted); }
.pr-ed-kopf strong { color: var(--dk-text); }
.pr-ed-pin { margin-left: 6px; font-size: 0.76rem; }
.pr-ed-feld { display: flex; flex-direction: column; gap: 5px; }
/* ST2: Tag-Filter der Lied-Auswahl */
.pr-ed-tagfilter-reihe { display: flex; flex-wrap: wrap; gap: 8px 14px; align-items: center; }
.pr-ed-tagfilter-feld { display: inline-flex; gap: 6px; align-items: center; font-size: 12px; color: var(--dk-text-muted); }
.pr-ed-tagfilter-wahl { font-size: 12px; padding: 4px 8px; }
.pr-ed-label { font-size: 0.8rem; font-weight: 600; color: var(--dk-text-muted); }
.pr-ed-gruppe { border: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 6px; }
.pr-ed-legend { font-size: 0.8rem; font-weight: 600; color: var(--dk-text-muted); padding: 0 0 4px; }
.pr-ed-wahl {
  display: flex; align-items: baseline; gap: 9px; padding: 8px 10px;
  border: 1px solid var(--dk-border); border-radius: 10px; background: var(--dk-surface);
  cursor: pointer; transition: background var(--dk-fast, 120ms);
}
.pr-ed-wahl:hover { background: var(--dk-surface-hover); }
.pr-ed-wahl--gesetzt {
  border-color: color-mix(in oklch, var(--primary) 45%, var(--line));
  background: color-mix(in oklch, var(--primary) 7%, var(--surface));
}
.pr-ed-input { flex-shrink: 0; margin: 0; align-self: center; }
.pr-ed-wahl-text { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 1px; }
.pr-ed-wahl-name { font-size: 0.88rem; color: var(--dk-text); font-weight: 500; }
.pr-ed-wahl-neben { font-size: 0.74rem; color: var(--dk-text-muted); }
.pr-ed-reiter { display: flex; flex-wrap: wrap; gap: 6px; }
.pr-ed-auswahl { width: 100%; }
.pr-ed-reiter .is-active {
  border-color: color-mix(in oklch, var(--primary) 45%, var(--line));
  background: color-mix(in oklch, var(--accent) 14%, var(--surface));
  font-weight: 600;
}
.pr-ed-warnung {
  padding: 8px 10px; border-radius: 8px; font-size: 0.8rem;
  border: 1px solid color-mix(in oklch, var(--dk-warning) 35%, var(--dk-surface));
  background: color-mix(in oklch, var(--dk-warning) 8%, var(--dk-surface));
  color: var(--dk-warning);
}
.pr-ed-leer { font-size: 0.84rem; color: var(--dk-text-muted); padding: 4px 0; }
/* OP-CHOR-10: Mobil wurde die Auswahlliste unbedienbar — die Regelabzeichen
   liefen Wort fuer Wort ueber mehrere Zeilen (Karten bis 764 px hoch, rund
   154 Karten). Auf schmalen Geraeten bleiben sie kurz und einzeilig; der
   volle Text steht im title-Attribut. */
.pr-ed-badge {
  max-width: 9.5rem; overflow: hidden; text-overflow: ellipsis;
  white-space: nowrap; flex-shrink: 0;
}
@media (max-width: 640px) {
  .pr-ed-wahl { flex-wrap: wrap; }
  .pr-ed-badge { max-width: 100%; }
  .pr-ed-gruppe { max-height: none; }
}
</style>
