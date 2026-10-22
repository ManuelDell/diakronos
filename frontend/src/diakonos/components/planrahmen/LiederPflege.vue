<template>
  <section class="lp">
    <!-- Werkzeugleiste: Suche + Tag-Filter -->
    <div class="lp-toolbar">
      <input
        v-model="suche" type="search" class="dk-form-input lp-suche"
        placeholder="Lied suchen (Titel, Nummer) …" aria-label="Lieder suchen"
      />
      <div v-if="tagMerkmale.length" class="lp-tagfilter">
        <div v-for="m in tagMerkmale" :key="m.id" class="lp-tagfilter-gruppe">
          <span class="lp-tagfilter-label">{{ m.name || m.id }}</span>
          <select
            class="dk-form-select lp-tagfilter-wahl"
            :value="tagFilter[m.id]?.[0] || ''"
            @change="tagFilterSetzen(m.id, $event.target.value)"
          >
            <option value="">Alle</option>
            <option v-for="w in werteFuer(m.id)" :key="w" :value="w">{{ w }}</option>
          </select>
          <button
            v-if="darfEinstellungen"
            type="button" class="dk-btn dk-btn-ghost dk-btn-xs"
            :title="'Werte für ' + (m.name || m.id) + ' pflegen'"
            @click="einstellungenOeffnen(m)"
          >Einstellungen</button>
        </div>
      </div>
    </div>
    <p class="lp-hinweis">
      Lieder kommen aus Psalmos (eine Wahrheit). Titel, Nummer/Buch/Seite, Noten,
      Audio und Notensatz bearbeitest du hier direkt — dieselbe Ansicht wie unter
      <a href="#/lieder">Lieder</a>.
    </p>

    <!-- Material-Art-Hinweis aus dem Serverfehler -->
    <div v-if="fehler.length" class="lp-fehler">
      <PrMeldungen :meldungen="fehler" />
    </div>

    <p v-if="!gefiltert.length" class="lp-leer">Keine Lieder gefunden.</p>

    <!-- Liedliste -->
    <div v-for="l in gefiltert" :key="l.id" class="lp-lied">
      <div class="lp-lied-kopf">
        <div class="lp-lied-titel">
          <span class="lp-lied-name">{{ l.titel }}</span>
          <span v-if="badgeFuer(l)" class="lp-chip" :class="{ 'lp-chip--kopie': istKopie(l.daten) }">
            {{ badgeFuer(l) }}
          </span>
          <span v-for="tag in l.tags" :key="tag" class="lp-chip lp-chip--tag">{{ tag }}</span>
          <span v-for="p in personChips(l)" :key="p.id + p.name" class="lp-chip lp-chip--person">{{ p.label }}</span>
        </div>
        <div class="lp-lied-aktionen">
          <button type="button" class="dk-btn dk-btn-secondary dk-btn-sm" @click="bearbeitenToggle(l)">
            {{ bearbeiteId === l.id ? 'Schließen' : 'Bearbeiten' }}
          </button>
        </div>
      </div>

      <!-- LI1: dieselbe Bearbeiten-Komponente wie unter #/lieder (EINE Wahrheit) -->
      <div v-if="bearbeiteId === l.id" class="lp-bearbeiten">
        <LiedBearbeiten
          :lied="{ id: l.id, name: l.id, titel: l.titel, ...(l.daten || {}),
                    kategorien: kategorienFuer(l) }"
          :material="l.material || []"
          :plantyp="plantyp"
          :plan="plan"
          :definition="definition"
          :merkmale="l.merkmale || {}"
          :darf-globale-bearbeiten="darfGlobaleBearbeiten"
          @gespeichert="liedBearbeitet"
          @verlassen="bearbeiteId = ''"
          @reload="emit('reload')"
        />
      </div>
    </div>

    <!-- Einstellungen: Auswahl-/Tag-Werte pflegen -->
    <DkModal v-model="einstellungenOffen" :title="'Einstellungen: ' + (einstellungenMerkmal?.name || einstellungenMerkmal?.id || '')">
      <div class="lp-einst">
        <ul class="lp-einst-liste">
          <li v-for="w in (einstellungenMerkmal?.werte || [])" :key="w" class="lp-einst-eintrag">
            <span>{{ w }}</span>
            <span class="lp-einst-aktionen">
              <button type="button" class="dk-btn dk-btn-ghost dk-btn-xs" @click="wertUmbenennen(w)">Umbenennen</button>
              <button type="button" class="dk-btn dk-btn-ghost dk-btn-xs lp-loeschen" @click="wertEntfernen(w)">Entfernen</button>
            </span>
          </li>
        </ul>
        <div class="lp-einst-neu">
          <input v-model="neuerWert" class="dk-form-input" type="text" placeholder="Neuer Wert" @keyup.enter="wertHinzufuegen" />
          <button type="button" class="dk-btn dk-btn-primary dk-btn-sm" :disabled="beschaeftigt || !neuerWert.trim()" @click="wertHinzufuegen">Hinzufügen</button>
        </div>
        <p v-if="einstellungenHinweis" class="lp-einst-hinweis">{{ einstellungenHinweis }}</p>
      </div>
      <template #footer>
        <button type="button" class="dk-btn dk-btn-secondary dk-btn-sm" @click="einstellungenOffen = false">Fertig</button>
      </template>
    </DkModal>
    <DkModal v-model="umbenennenOffen" title="Wert umbenennen">
      <form id="lp-umbenennen" @submit.prevent="umbenennenSpeichern">
        <label class="dk-form-label" for="lp-neuer-name">Neuer Name</label>
        <input id="lp-neuer-name" v-model="umbenennenWert" class="dk-form-input" maxlength="140" required />
      </form>
      <template #footer>
        <button type="button" class="dk-btn dk-btn-secondary" @click="umbenennenOffen = false">Abbrechen</button>
        <button type="submit" form="lp-umbenennen" class="dk-btn dk-btn-primary">Umbenennen</button>
      </template>
    </DkModal>
  </section>
</template>

<script setup>
/**
 * ST2/LI1 — Lieder pflegen (eingebaute Sammlung 'lieder' in der Stammdaten-Ansicht).
 *
 * Alles laeuft ueber Psalmos + die planrahmen-Endpunkte (usePlanrahmen):
 *  - Bearbeiten (Titel/Nummer/Buch/Seite, Strophen, Tags, Material) macht die
 *    GEMEINSAME Komponente `components/lieder/LiedBearbeiten.vue` — dieselbe
 *    Ansicht wie unter #/lieder. Hier gibt es bewusst keine zweite Formular-Kopie.
 *  - Tags des Plantyps werden weiterhin in der Liste gefiltert;
 *    `sammlungsmerkmalWertePflegen` pflegt deren Auswahl-Werte.
 *  - Personen-Auswahl fuer person-Merkmale kommt rollengefiltert vom Server
 *    (`merkmalKandidaten`) — nur passende Personen (z. B. nur 'dirigiert').
 */
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { usePlanrahmen, fehlerMeldungen } from '../../composables/usePlanrahmen.js'
import { showToast } from '../../composables/useToast.js'
import { bestaetigen } from '../../composables/useBestaetigen.js'
import DkModal from '../DkModal.vue'
import LiedBearbeiten from '../lieder/LiedBearbeiten.vue'
import PrMeldungen from './PrMeldungen.vue'
import {
  pflegbareWertMerkmale, personMerkmale, liederFiltern, asListe, tagWerte,
} from './lieder-pflege.mjs'
import { liedAnzeige, istKopie } from './lied-anzeige.mjs'

const props = defineProps({
  plantyp: { type: String, default: '' },
  plan: { type: String, default: '' },
  darfBearbeiten: { type: Boolean, default: false },
  darfGlobaleBearbeiten: { type: Boolean, default: false },
  definition: { type: Object, default: null },
  lieder: { type: Array, default: () => [] },
  audioLimitBytes: { type: Number, default: 50 * 1024 * 1024 },
})
const emit = defineEmits(['reload'])

const { sammlungsmerkmalWertePflegen, merkmalKandidaten } = usePlanrahmen()

const beschaeftigt = ref(false)
const fehler = ref([])
const suche = ref('')
const tagFilter = reactive({})

const tagMerkmale = computed(() => pflegbareWertMerkmale(props.definition, 'lieder'))
const personMerkmaleListe = computed(() => personMerkmale(props.definition, 'lieder'))
const darfEinstellungen = computed(() => props.darfGlobaleBearbeiten)

// ── Personen-Merkmale: rollengefilterte Kandidaten vom Server ───────────────
// Nur Personen, die die Rolle der Merkmals-Definition erfuellen (z. B. nur
// 'dirigiert'-markierte Personen als Standard-Dirigent). Nie umgekehrt: die
// UI zeigt ausschliesslich, was der Server liefert.
const kandidaten = reactive({})        // merkmalId -> [{kennung, anzeige, kuerzel}]
const kandidatenHinweis = reactive({}) // merkmalId -> Hinweistext bei leerer Liste
const kandidatenGeladen = ref(false)

async function kandidatenLaden() {
  if (!props.plantyp || !personMerkmaleListe.value.length) return
  kandidatenGeladen.value = false
  try {
    for (const m of personMerkmaleListe.value) {
      try {
        const erg = await merkmalKandidaten(props.plantyp, m.id, props.plan || null)
        kandidaten[m.id] = Array.isArray(erg?.kandidaten) ? erg.kandidaten : []
        kandidatenHinweis[m.id] = erg?.hinweis || ''
      } catch (err) {
        kandidaten[m.id] = []
        const meldungen = fehlerMeldungen(err)
        kandidatenHinweis[m.id] = meldungen?.[0]?.meldung || 'Auswahl konnte nicht geladen werden.'
      }
    }
  } finally {
    kandidatenGeladen.value = true
  }
}

onMounted(kandidatenLaden)
watch(
  () => [props.plantyp, props.plan, personMerkmaleListe.value.length].join('|'),
  () => kandidatenLaden(),
)

/** Lieder mit aufgeloesten Tag-Chips fuer die Anzeige. */
const liederMitTags = computed(() => (props.lieder || []).map((l) => ({
  ...l,
  tags: tagMerkmale.value.flatMap((m) => asListe(l.merkmale?.[m.id])),
})))

const gefiltert = computed(() => liederFiltern(liederMitTags.value, { suche: suche.value, tagFilter }))

function werteFuer(merkmalId) {
  return tagWerte(props.definition, 'lieder', props.lieder)[merkmalId] || []
}

/** Anzeige-Chips der gesetzten Personen-Angaben (z. B. „Dirigent: Anna Alt“). */
function personChips(l) {
  const ergebnis = []
  for (const m of personMerkmaleListe.value) {
    const kennung = l.merkmale?.[m.id]
    if (!kennung) continue
    const treffer = (kandidaten[m.id] || []).find((k) => (k.kennung ?? k.id) === kennung)
    const name = treffer?.name || treffer?.anzeige || kennung
    ergebnis.push({ id: m.id, name: kennung, label: `${m.name || m.id}: ${name}` })
  }
  return ergebnis
}

function tagFilterSetzen(merkmalId, wert) {
  if (!wert) delete tagFilter[merkmalId]
  else tagFilter[merkmalId] = [wert]
}

// ── Bearbeiten ─────────────────────────────────────────────────────────────

const bearbeiteId = ref('')

/** Badge-Label eines Liedes (nie "Nr." ohne Nummer). */
function badgeFuer(l) {
  return liedAnzeige({ quelle: l.daten?.quelle, buch: l.daten?.buch,
                       gesangbuch_nummer: l.daten?.gesangbuch_nummer, seite: l.daten?.seite })
}

function bearbeitenToggle(l) {
  if (bearbeiteId.value === l.id) { bearbeiteId.value = ''; return }
  bearbeiteId.value = l.id
}

/** Nach dem Speichern in der gemeinsamen Bearbeiten-Komponente. */
function liedBearbeitet() {
  bearbeiteId.value = ''
  emit('reload')
}

/** Kategorien eines Liedes aus den Deklarationen (quelle psalmos.kategorie). */
function kategorienFuer(l) {
  const liste = []
  for (const m of (props.definition?.merkmale?.lieder || [])) {
    if (m?.quelle !== 'psalmos.kategorie') continue
    const wert = l?.merkmale?.[m.id]
    if (wert === null || wert === undefined || wert === '') continue
    liste.push(...(Array.isArray(wert) ? wert : [wert]))
  }
  return liste.map(String)
}

// ── Einstellungen (Auswahl-/Tag-Werte) ──────────────────────────────────────
const einstellungenOffen = ref(false)
const einstellungenMerkmal = ref(null)
const neuerWert = ref('')
const einstellungenHinweis = ref('')

function einstellungenOeffnen(m) {
  einstellungenMerkmal.value = m
  neuerWert.value = ''
  einstellungenHinweis.value = ''
  einstellungenOffen.value = true
}

async function wertAktion(aktion, wert, neu = null) {
  fehler.value = []
  beschaeftigt.value = true
  try {
    const erg = await sammlungsmerkmalWertePflegen(
      props.plantyp, einstellungenMerkmal.value.id, aktion, wert, neu, props.plan || null)
    einstellungenHinweis.value = erg?.hinweis || ''
    showToast('Werte gespeichert.')
    emit('reload')
    // Definition im Dialog aktualisieren, damit die Liste stimmt.
    einstellungenMerkmal.value = { ...einstellungenMerkmal.value, werte: erg?.werte || [] }
  } catch (err) {
    fehler.value = fehlerMeldungen(err)
  } finally {
    beschaeftigt.value = false
  }
}

function wertHinzufuegen() {
  const w = neuerWert.value.trim()
  if (!w) return
  neuerWert.value = ''
  return wertAktion('hinzufuegen', w)
}
const umbenennenOffen = ref(false)
const umbenennenAlt = ref('')
const umbenennenWert = ref('')
function wertUmbenennen(w) {
  umbenennenAlt.value = w
  umbenennenWert.value = w
  umbenennenOffen.value = true
}
async function umbenennenSpeichern() {
  const neu = umbenennenWert.value.trim()
  if (!neu || beschaeftigt.value) return
  if (neu !== umbenennenAlt.value) await wertAktion('umbenennen', umbenennenAlt.value, neu)
  if (!fehler.value.length) umbenennenOffen.value = false
}
async function wertEntfernen(w) {
  if (!await bestaetigen({ titel: 'Wert entfernen?', text: `Wert „${w}“ aus der Auswahl entfernen?`, aktion: 'Entfernen' })) return
  return wertAktion('entfernen', w)
}
</script>

<style scoped>
.lp { display: flex; flex-direction: column; gap: 12px; }
.lp-toolbar { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; }
.lp-suche { max-width: 320px; }
.lp-tagfilter { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; }
.lp-tagfilter-gruppe { display: inline-flex; gap: 6px; align-items: center; }
.lp-tagfilter-label { font-size: 12px; color: var(--dk-text-muted); }
.lp-tagfilter-wahl { font-size: 12px; padding: 4px 8px; }
.lp-hinweis { font-size: 12px; color: var(--dk-text-subtle); margin: 0; }
.lp-hinweis a { color: var(--dk-brand-500); }
.lp-fehler { margin: 4px 0; }
.lp-leer { color: var(--dk-text-subtle); font-size: 13px; }
.lp-lied { border: 1px solid var(--dk-border); border-radius: 10px; background: var(--dk-surface); overflow: hidden; }
.lp-lied-kopf { display: flex; justify-content: space-between; align-items: center; gap: 10px; padding: 10px 12px; }
.lp-lied-titel { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
.lp-lied-name { font-weight: 500; color: var(--dk-text); }
.lp-chip { font-size: 11px; padding: 2px 8px; border-radius: 999px; background: var(--dk-surface-2); color: var(--dk-text-muted); border: 1px solid var(--dk-border); }
.lp-chip--tag { background: color-mix(in oklch, var(--dk-brand-400) 16%, var(--dk-surface)); color: var(--dk-text); }
.lp-chip--kopie { background: color-mix(in oklch, var(--dk-text-subtle) 14%, var(--dk-surface)); color: var(--dk-text-muted); font-style: italic; }
.lp-chip--person { background: color-mix(in oklch, var(--dk-success-400, var(--dk-brand-400)) 18%, var(--dk-surface)); color: var(--dk-text); }
.lp-personen { display: flex; flex-direction: column; gap: 6px; }
.lp-person-reihe { display: flex; gap: 8px; align-items: flex-start; flex-wrap: wrap; }
.lp-person-reihe .mk-person { max-width: 280px; }
.lp-bearbeiten { border-top: 1px solid var(--dk-divider); padding: 12px; display: flex; flex-direction: column; gap: 12px; background: var(--dk-surface-2); }
.lp-felder { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 8px; }
.lp-feld { display: flex; flex-direction: column; gap: 3px; font-size: 12px; color: var(--dk-text-muted); }
.lp-feld-hinweis { font-size: 12px; color: var(--dk-text-subtle); margin: 0; align-self: end; }
.lp-tags { display: flex; flex-direction: column; gap: 6px; }
.lp-tag-reihe { display: flex; flex-wrap: wrap; gap: 4px 12px; align-items: center; }
.lp-tag-label { font-size: 12px; color: var(--dk-text-muted); min-width: 90px; }
.lp-tag-wahl { display: inline-flex; gap: 4px; align-items: center; font-size: 12px; cursor: pointer; }
.lp-aktionen { display: flex; gap: 8px; }
.lp-material { border-top: 1px dashed var(--dk-border); padding-top: 10px; display: flex; flex-direction: column; gap: 8px; }
.lp-material-titel { font-size: 13px; margin: 0; color: var(--dk-text); }
.lp-material-gruppe { display: flex; flex-direction: column; gap: 4px; }
.lp-material-art { font-size: 12px; font-weight: 500; color: var(--dk-text-muted); }
.lp-material-liste { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 6px; }
.lp-material-eintrag { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
.lp-material-name { font-size: 12px; color: var(--dk-text); }
.lp-audio { height: 32px; }
.lp-material-leer { font-size: 12px; color: var(--dk-text-subtle); }
.lp-loeschen { color: var(--dk-danger); }
.lp-upload { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
.lp-datei { font-size: 12px; }
.lp-stimme, .lp-beschreibung { max-width: 160px; }
.lp-upload-hinweis { font-size: 11px; color: var(--dk-text-subtle); margin: 0; }
.lp-einst { display: flex; flex-direction: column; gap: 10px; }
.lp-einst-liste { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 4px; }
.lp-einst-eintrag { display: flex; justify-content: space-between; align-items: center; gap: 8px; font-size: 13px; }
.lp-einst-aktionen { display: inline-flex; gap: 4px; }
.lp-einst-neu { display: flex; gap: 8px; }
.lp-einst-hinweis { font-size: 12px; color: var(--dk-text-muted); margin: 0; }
</style>
