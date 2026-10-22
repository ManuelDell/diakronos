<template>
  <div class="lb">
    <!-- Kopf: Titel des Vorgangs + Kennung des Liedes -->
    <div class="lb-kopf">
      <div class="lb-kopf-text">
        <h2 class="lb-titel">{{ neuanlage ? 'Neues Lied' : 'Lied bearbeiten' }}</h2>
        <p class="lb-unter">{{ neuanlage
          ? 'Titel eintragen, Quelle wählen, fertig. Alles Weitere kannst du später ergänzen.'
          : 'Änderungen gelten sofort für alle Pläne.' }}</p>
      </div>
      <DkBadge v-if="anzeige" :variant="istKopie ? 'neutral' : 'akzent'">{{ anzeige }}</DkBadge>
    </div>

    <!-- Servermeldungen in Klartext (pfad/code/meldung/hinweis) -->
    <div v-if="fehlerListe.length" class="lb-meldungen">
      <PrMeldungen :meldungen="fehlerListe" />
    </div>

    <!-- ── Grunddaten ─────────────────────────────────────────────────── -->
    <DkCard title="Grunddaten">
      <div class="lb-felder">
        <DkField v-slot="feld" label="Titel" required :error="fehler.titel">
          <input
            :id="feld.id" :aria-describedby="feld.aria-describedby"
            v-model="form.titel" class="dk-form-input" type="text" maxlength="140"
            placeholder="Wie heißt das Lied?" :aria-invalid="!!fehler.titel || undefined"
          />
        </DkField>
        <DkField v-slot="feld" label="Zweiter Titel" help="Optional — z. B. englischer oder alternativer Titel.">
          <input :id="feld.id" :aria-describedby="feld.aria-describedby"
            v-model="form.alternativtitel" class="dk-form-input" type="text" maxlength="140" />
        </DkField>

        <DkField v-slot="feld" label="Hat das Lied eine Nummer?">
          <DkSelect
            :id="feld.id" :aria-describedby="feld.aria-describedby"
            :model-value="form.quelle" :options="quellenOptionen"
            @update:model-value="quelleSetzen"
          />
        </DkField>
        <p class="lb-quelle-hilfe">{{ quelleHilfe }}</p>

        <template v-if="nummernfelder">
          <DkField v-slot="feld" label="Liederbuch / Heft" help="Kürzel genügt, z. B. JN oder WH.">
            <input :id="feld.id" :aria-describedby="feld.aria-describedby"
              v-model="form.buch" class="dk-form-input" type="text" maxlength="140" placeholder="z. B. JN" />
          </DkField>
          <DkField v-slot="feld" label="Nummer">
            <input :id="feld.id" v-model="form.gesangbuch_nummer" class="dk-form-input" type="text" maxlength="140" />
          </DkField>
          <DkField v-slot="feld" label="Seite" help="Nur nötig, wenn das Lied keine Nummer hat.">
            <input :id="feld.id" :aria-describedby="feld.aria-describedby"
              v-model="form.seite" class="dk-form-input" type="text" maxlength="140" />
          </DkField>
        </template>

        <DkField v-slot="feld" label="CCLI-Nummer" help="Optional — Lizenznummer, falls vorhanden.">
          <input :id="feld.id" :aria-describedby="feld.aria-describedby"
            v-model="form.ccli_nummer" class="dk-form-input" type="text" maxlength="140" />
        </DkField>
      </div>

      <DkField v-slot="feld" label="Notiz" help="Optional. Nur für das Team sichtbar.">
        <textarea :id="feld.id" :aria-describedby="feld.aria-describedby"
          v-model="form.notiz" class="dk-form-input lb-textarea" rows="2"></textarea>
      </DkField>

      <label class="lb-schalter">
        <input v-model="form.aktiv" type="checkbox" />
        <span>Lied ist aktiv (kann in Plänen ausgewählt werden)</span>
      </label>
    </DkCard>

    <!-- ── Kategorien und Anlässe ─────────────────────────────────────── -->
    <DkCard title="Kategorien und Anlässe">
      <p class="lb-hinweis">
        Kategorien und Anlässe kommen aus dem gepflegten Verzeichnis. Schreib einen
        neuen Begriff, wenn keiner passt — er wird dann mit angelegt.
      </p>
      <DkField v-slot="feld" label="Kategorien / Themen" help="Mehrere mit Komma trennen, z. B. Lobpreis, Advent, Anbetung.">
        <input :id="feld.id" :aria-describedby="feld.aria-describedby"
          v-model="kategorienText" class="dk-form-input" type="text" :list="'lb-kat-' + uid" />
      </DkField>
      <datalist :id="'lb-kat-' + uid">
        <option v-for="k in kategorienVorschlaege" :key="k" :value="k" />
      </datalist>
      <div v-if="form.kategorien.length" class="lb-chips">
        <DkBadge v-for="(k, i) in form.kategorien" :key="k" variant="info">
          {{ k }}
          <!-- Befund 4: neue Begriffe (nicht im Verzeichnis) sichtbar kennzeichnen,
               damit ein Tippfehler nicht unbemerkt im Katalog landet. -->
          <span v-if="istNeuerBegriff(k, 'kategorie')" class="lb-neu" title="Wird neu ins Verzeichnis aufgenommen">neu</span>
          <button type="button" class="lb-chip-weg" :aria-label="'Kategorie ' + k + ' entfernen'" @click="kategorieEntfernen(i)">✕</button>
        </DkBadge>
      </div>

      <DkField v-slot="feld" label="Anlässe" help="Mehrere mit Komma trennen, z. B. Gottesdienst, Trauung, Taufe.">
        <input :id="feld.id" :aria-describedby="feld.aria-describedby"
          v-model="anlaesseText" class="dk-form-input" type="text" :list="'lb-anl-' + uid" />
      </DkField>
      <datalist :id="'lb-anl-' + uid">
        <option v-for="a in anlaesseVorschlaege" :key="a" :value="a" />
      </datalist>
      <div v-if="form.anlaesse.length" class="lb-chips">
        <DkBadge v-for="(a, i) in form.anlaesse" :key="a" variant="neutral">
          {{ a }}
          <span v-if="istNeuerBegriff(a, 'anlass')" class="lb-neu" title="Wird neu ins Verzeichnis aufgenommen">neu</span>
          <button type="button" class="lb-chip-weg" :aria-label="'Anlass ' + a + ' entfernen'" @click="anlassEntfernen(i)">✕</button>
        </DkBadge>
      </div>
    </DkCard>

    <!-- ── Strophen ───────────────────────────────────────────────────── -->
    <DkCard title="Strophen">
      <template #actions>
        <DkButton variant="secondary" size="sm" @click="hinzufuegen('Strophe')">Strophe hinzufügen</DkButton>
        <DkButton variant="ghost" size="sm" @click="hinzufuegen('Refrain')">Refrain</DkButton>
        <DkButton variant="ghost" size="sm" @click="hinzufuegen('Bridge')">Bridge</DkButton>
      </template>

      <DkEmpty
        v-if="!form.strophen.length"
        title="Noch keine Strophen"
        text="Strophen kannst du später ergänzen — sie sind keine Pflicht."
        icon="🎼"
      />

      <div v-for="(s, i) in form.strophen" :key="i" class="lb-strophe">
        <div class="lb-strophe-kopf">
          <span class="lb-strophe-nr">{{ i + 1 }}</span>
          <DkSelect
            class="lb-strophe-typ" :model-value="s.typ" :options="typOptionen" :aria-label="'Art der Strophe ' + (i + 1)"
            @update:model-value="(v) => (s.typ = v)"
          />
          <input v-model="s.sprache" class="dk-form-input lb-strophe-sprache" type="text" maxlength="140"
            :aria-label="'Sprache der Strophe ' + (i + 1)" placeholder="Sprache (optional)" />
          <label class="lb-schalter lb-schalter--klein">
            <input v-model="s.nur_chor" type="checkbox" />
            <span>nur Chor</span>
          </label>
          <span class="lb-strophe-aktionen">
            <DkButton variant="ghost" size="sm" :disabled="i === 0" @click="verschieben(i, -1)">Nach oben</DkButton>
            <DkButton variant="ghost" size="sm" :disabled="i === form.strophen.length - 1" @click="verschieben(i, 1)">Nach unten</DkButton>
            <DkButton variant="ghost" size="sm" @click="entfernen(i)">Entfernen</DkButton>
          </span>
        </div>
        <textarea
          v-model="s.text" class="dk-form-input lb-strophe-text" rows="3"
          :aria-label="'Text der Strophe ' + (i + 1)"
          :placeholder="'Text der ' + (i + 1) + '. Strophe'"
        ></textarea>
        <p v-if="fehler['strophe-' + i]" class="lb-strophe-fehler">{{ fehler['strophe-' + i] }}</p>
      </div>
    </DkCard>

    <!-- ── Merkmale aus dem Plan (nur wenn konfiguriert) ──────────────── -->
    <DkCard v-if="tagMerkmale.length || personMerkmale.length" title="Merkmale dieser Planvorlage">
      <p class="lb-hinweis">
        Diese Angaben gehören zur gewählten Planvorlage und helfen beim Planen.
        Sie werden sofort gespeichert.
      </p>

      <div v-for="m in personMerkmale" :key="m.id" class="lb-merkmal-reihe">
        <span class="lb-merkmal-label">{{ m.name || m.id }}</span>
        <MerkmalWert
          :merkmal="m" :kandidaten="kandidaten[m.id] ?? null"
          :kandidaten-hinweis="kandidatenHinweis[m.id] || ''"
          :model-value="merkmale[m.id] ?? null" :readonly="beschaeftigt"
          @update:model-value="(v) => merkmalSetzen(m, v)"
        />
      </div>

      <div v-for="m in tagMerkmale" :key="m.id" class="lb-merkmal-reihe">
        <span class="lb-merkmal-label">{{ m.name || m.id }}</span>
        <span class="lb-merkmal-werte">
          <label v-for="w in werteFuer(m.id)" :key="w" class="lb-tag-wahl">
            <input
              type="checkbox" :checked="alsListe(merkmale[m.id]).includes(w)"
              @change="tagToggle(m, w, $event.target.checked)"
            /><span>{{ w }}</span>
          </label>
          <span v-if="!werteFuer(m.id).length" class="lb-hinweis">Noch keine Werte hinterlegt.</span>
        </span>
      </div>
    </DkCard>

    <!-- ── Material ───────────────────────────────────────────────────── -->
    <DkCard title="Material">
      <p class="lb-hinweis">
        Noten als PDF, Hörproben als Audio (mp3/m4a/ogg/wav, höchstens {{ audioLimitText }})
        sowie MuseScore- oder MusicXML-Dateien zum Weiterbearbeiten.
        {{ neuanlage ? 'Material kannst du nach dem Speichern hinzufügen.' : '' }}
      </p>

      <DkEmpty
        v-if="!neuanlage && !material.length"
        title="Noch kein Material" text="Lade Noten, eine Hörprobe oder den Notensatz hoch." icon="📎"
      />

      <div v-for="g in materialGruppen" :key="g.art" class="lb-material-gruppe">
        <span class="lb-material-art">{{ materialLabel(g.art) }}</span>
        <ul class="lb-material-liste">
          <li v-for="m in g.eintraege" :key="m.material || m.anhang || m.dateiname" class="lb-material-eintrag">
            <span class="lb-material-name">{{ m.dateiname || m.anhang }}</span>
            <template v-if="m.datei?.datei_url">
              <audio v-if="g.art === 'audio'" controls preload="none" :src="m.datei.datei_url" class="lb-audio" />
              <a class="lb-link" :href="m.datei.datei_url" target="_blank" rel="noopener">Öffnen / Herunterladen</a>
            </template>
            <button type="button" class="lb-chip-weg" :aria-label="'Material entfernen'" @click="materialLoeschen(m)">Entfernen</button>
          </li>
        </ul>
      </div>

      <div v-if="!neuanlage" class="lb-upload">
        <DkSelect class="lb-upload-art" :model-value="upload.art" :options="materialOptionen" aria-label="Art des Materials"
                  @update:model-value="(v) => (upload.art = v)" />
        <input ref="dateiInput" type="file" class="lb-datei" :accept="akzeptierteEndungen" @change="dateiGewaehlt" />
        <input v-model="upload.stimme" class="dk-form-input lb-upload-klein" type="text" maxlength="140" placeholder="Stimme (optional)" />
        <input v-model="upload.beschreibung" class="dk-form-input lb-upload-klein" type="text" maxlength="140" placeholder="Beschreibung (optional)" />
        <DkButton variant="secondary" size="sm" :disabled="beschaeftigt || !upload.datei" @click="materialHochladen">
          Hochladen
        </DkButton>
      </div>
    </DkCard>

    <!-- ── Fuß: Speichern / Abbrechen ─────────────────────────────────── -->
    <div class="lb-fuss">
      <DkButton v-if="!neuanlage" variant="ghost" @click="anfragen('abbrechen')">Abbrechen</DkButton>
      <DkButton variant="primary" :loading="beschaeftigt" @click="speichern">
        {{ neuanlage ? 'Lied anlegen' : 'Änderungen speichern' }}
      </DkButton>
    </div>

    <!-- Ungespeicherte Änderungen: eingebaute Rückfrage, kein window.confirm -->
    <DkDialog v-model="dialogOffen" :title="dialogTitel" size="sm" @close="dialogOffen = false">
      <p class="lb-dialog-text">{{ dialogText }}</p>
      <template #footer>
        <DkButton variant="secondary" @click="dialogOffen = false">Weiter bearbeiten</DkButton>
        <DkButton variant="danger" @click="verwerfenBestaetigt">{{ dialogKnopf }}</DkButton>
      </template>
    </DkDialog>

    <!-- UXM-R17: Dublettenwarnung (gleiche Nummer bzw. gleicher Titel) -->
    <DkDialog v-model="dubletteDialog" title="Es gibt schon ein solches Lied" size="sm" @close="dubletteDialog = false">
      <p class="lb-dialog-text">
        Ein Lied mit diesem Titel oder dieser Nummer ist bereits vorhanden:
        <strong>{{ dublette }}</strong>. Trotzdem ein zweites anlegen?
      </p>
      <template #footer>
        <DkButton variant="secondary" @click="dubletteDialog = false">Abbrechen</DkButton>
        <DkButton variant="danger" :loading="beschaeftigt" @click="dubletteTrotzdem">Trotzdem anlegen</DkButton>
      </template>
    </DkDialog>
  </div>
</template>

<script setup>
/**
 * LI1 — EIN Ort zum Anlegen und Bearbeiten eines Liedes.
 *
 * Diese Komponente ist die einzige Bearbeiten-Oberfläche: „Neues Lied“ in
 * der Lieder-Liste und „Bearbeiten“ im Lied-Detail benutzen sie, und die
 * Lieder-Pflege im Plan verlinkt hierher, statt eigene Felder zu duplizieren.
 *
 * Reine Logik (Quelle, Strophen, Prüfung, Nutzlast) steht in
 * `components/lieder/lied-bearbeiten.mjs` und ist dort node-getestet.
 *
 * Rechte: Der Server entscheidet. `darfSchreiben` kommt aus
 * `diakronos.planrahmen.api.lied_rechte` — dieselbe Regel, die
 * `lied_speichern` prüft.
 *
 * Material (PDF/Audio/Notensatz) läuft weiter über die Planrahmen-Endpunkte.
 * Der Plantyp ist optional: mit Planvorlage gilt das Planer-Recht, ohne (Aufruf
 * aus dem Lied-Detail) die Psalmos-Regel — darum funktioniert der Material-
 * bereich auch ohne `plantyp`-Prop (UXM-R7).
 */
import { ref, reactive, computed, onMounted, onBeforeUnmount, watch, nextTick, useId } from 'vue'
import { apiCall } from '../../composables/useApi.js'
import { showToast } from '../../composables/useToast.js'
import { fehlerMeldungen } from '../../composables/usePlanrahmen.js'
import { usePlanrahmen } from '../../composables/usePlanrahmen.js'
import { useSession } from '../../composables/useSession.js'
import { navigate, onBeforeEach } from '../../router.js'
import DkCard from '../ui/DkCard.vue'
import DkField from '../ui/DkField.vue'
import DkSelect from '../ui/DkSelect.vue'
import DkButton from '../ui/DkButton.vue'
import DkBadge from '../ui/DkBadge.vue'
import DkEmpty from '../ui/DkEmpty.vue'
import DkDialog from '../ui/DkDialog.vue'
import PrMeldungen from '../planrahmen/PrMeldungen.vue'
import MerkmalWert from '../planrahmen/MerkmalWert.vue'
import {
  QUELLEN, STROPHEN_TYPEN, quellenfelderSichtbar, quelleLabel,
  stropheHinzufuegen, stropheEntfernen, stropheVerschieben,
  leeresFormular, formularAusLied, quelleGewechselt,
  formularAnzeige, formularIstKopie, pruefen, nutzlast, istNeuanlage,
} from './lied-bearbeiten.mjs'
import { MATERIAL_ARTEN, artFuerDateiname, materialNachArt } from '../planrahmen/lieder-pflege.mjs'

const props = defineProps({
  /** Vorhandenes Lied (Ändern). Ohne `lied` ist es eine Neuanlage. */
  lied: { type: Object, default: null },
  strophen: { type: Array, default: () => [] },
  material: { type: Array, default: () => [] },
  /** Plantyp-Kontext für Merkmale (je Plantyp) und Material. */
  plantyp: { type: String, default: '' },
  plan: { type: String, default: null },
  /** Merkmals-Definition des Plantyps (nur Anzeige, Werte kommen vom Server). */
  definition: { type: Object, default: null },
  /** Vorgegebene Sammlungs-Merkmale des Liedes (schlüssel → Wert). */
  merkmale: { type: Object, default: () => ({}) },
  darfGlobaleBearbeiten: { type: Boolean, default: false },
  audioLimitBytes: { type: Number, default: 50 * 1024 * 1024 },
})
const emit = defineEmits(['gespeichert', 'reload'])

const uid = useId()
const { user, isAdmin } = useSession()
const {
  liedMaterialHinzufuegen, liedMaterialLoeschen, uploadDatei,
  merkmalePflegen, merkmalKandidaten,
} = usePlanrahmen()

/* ── Zustand ─────────────────────────────────────────────────────────────── */

const form = reactive(props.lied
  ? formularAusLied(props.lied, props.strophen)
  : leeresFormular())
const fehler = reactive({})
const fehlerListe = ref([])
const beschaeftigt = ref(false)
const gespeichert = ref(false)
const dialogOffen = ref(false)
const dialogAbsicht = ref('abbrechen')
// UXM-R17: Dublettenwarnung beim Anlegen.
const dubletteDialog = ref(false)
const dublette = ref('')
const dubletteBestaetigt = ref(false)
const upload = reactive({ art: 'noten_pdf', datei: null, stimme: '', beschreibung: '' })
const dateiInput = ref(null)
const materialStand = ref([...(props.material || [])])
const merkmale = reactive({ ...(props.merkmale || {}) })

const neuanlage = computed(() => istNeuanlage(form))
const anzeige = computed(() => formularAnzeige(form))
const istKopie = computed(() => formularIstKopie(form))
const nummernfelder = computed(() => quellenfelderSichtbar(form.quelle))
const quellenOptionen = QUELLEN.map((q) => ({ value: q.wert, label: q.label }))
const typOptionen = STROPHEN_TYPEN.map((t) => ({ value: t, label: t }))
const quelleHilfe = computed(() => (QUELLEN.find((q) => q.wert === form.quelle) || QUELLEN[2]).hilfe)

/* Freitextfelder für Kategorien/Anlässe (Komma-Listen) mit Chips darunter. */
const kategorienText = ref((props.lied?.kategorien || []).join(', '))
const anlaesseText = ref((props.lied?.anlaesse || []).join(', '))

function kommaListe(text) {
  return String(text || '').split(',').map((t) => t.trim()).filter(Boolean)
}
watch(kategorienText, (t) => { form.kategorien = kommaListe(t) })
watch(anlaesseText, (t) => { form.anlaesse = kommaListe(t) })

const kategorienVorschlaege = ref([])
const anlaesseVorschlaege = ref([])

/**
 * Befund 4: Ein Begriff gilt als „neu", wenn er nicht im Verzeichnis steht.
 * Beim Speichern legt der Server ihn an — der Chip macht das sichtbar, damit
 * ein Tippfehler nicht unbemerkt im Katalog landet.
 */
function istNeuerBegriff(begriff, art) {
  const liste = art === 'anlass' ? anlaesseVorschlaege.value : kategorienVorschlaege.value
  const klein = String(begriff || '').trim().toLowerCase()
  if (!klein) return false
  return !liste.some((v) => String(v || '').trim().toLowerCase() === klein)
}
const materialOptionen = Object.entries(MATERIAL_ARTEN).map(([wert, def]) => ({ value: wert, label: def.label }))
const akzeptierteEndungen = Object.values(MATERIAL_ARTEN).flatMap((a) => a.endungen).join(',')
const audioLimitText = computed(() => `${Math.round(props.audioLimitBytes / (1024 * 1024))} MB`)
const materialGruppen = computed(() => materialNachArt(materialStand.value))

function materialLabel(art) {
  return MATERIAL_ARTEN[art]?.label || art
}

/* ── Schreibrecht (Serverwahrheit) ──────────────────────────────────────── */

const darfSchreiben = ref(false)
const rechteHinweis = ref('')

async function rechteLaden() {
  try {
    const erg = await apiCall('diakronos.planrahmen.api.lied_rechte', {
      plantyp: props.plantyp || null, plan: props.plan || null,
    })
    darfSchreiben.value = !!erg?.darf_schreiben
    rechteHinweis.value = erg?.hinweis || ''
  } catch (e) {
    // Ohne Auskunft wird nichts angeboten — nie umgekehrt verlassen.
    darfSchreiben.value = !!isAdmin.value
    rechteHinweis.value = 'Ob du Lieder bearbeiten darfst, konnte nicht geprüft werden.'
  }
}

/* ── Merkmale je Plantyp (nur wenn konfiguriert) ────────────────────────── */

const merkmaleDef = computed(() => props.definition?.merkmale || {})
const tagMerkmale = computed(() =>
  (merkmaleDef.value.lieder || []).filter((m) => m?.art === 'tag' || m?.art === 'auswahl'))
const personMerkmale = computed(() =>
  (merkmaleDef.value.lieder || []).filter((m) => m?.art === 'person'))

const kandidaten = reactive({})
const kandidatenHinweis = reactive({})

function alsListe(wert) {
  if (wert === null || wert === undefined || wert === '') return []
  return Array.isArray(wert) ? wert : [wert]
}

function werteFuer(merkmalId) {
  const m = (merkmaleDef.value.lieder || []).find((x) => x.id === merkmalId)
  return (m?.werte || []).map(String)
}

async function kandidatenLaden() {
  if (!props.plantyp || !personMerkmale.value.length) return
  for (const m of personMerkmale.value) {
    if (kandidaten[m.id]) continue
    try {
      const erg = await merkmalKandidaten(props.plantyp, m.id, props.plan || null)
      kandidaten[m.id] = Array.isArray(erg?.kandidaten) ? erg.kandidaten : []
      kandidatenHinweis[m.id] = erg?.hinweis || ''
    } catch (e) {
      kandidaten[m.id] = []
      kandidatenHinweis[m.id] = fehlerMeldungen(e)?.[0]?.meldung || 'Auswahl konnte nicht geladen werden.'
    }
  }
}

async function merkmalSetzen(merkmal, wert) {
  merkmale[merkmal.id] = wert || null
  await merkmaleSenden([{ ziel: 'sammlung:lieder', schluessel: merkmal.id, ziel_id: form.name, wert: wert || null }])
}

async function tagToggle(merkmal, wert, an) {
  const neu = alsListe(merkmale[merkmal.id]).slice()
  const i = neu.indexOf(wert)
  if (an && i === -1) neu.push(wert)
  if (!an && i !== -1) neu.splice(i, 1)
  merkmale[merkmal.id] = neu.length ? (merkmal.mehrfach ? neu : neu[0]) : null
  await merkmaleSenden([{ ziel: 'sammlung:lieder', schluessel: merkmal.id, ziel_id: form.name,
                          wert: merkmale[merkmal.id] }])
}

async function merkmaleSenden(werte) {
  if (!props.plantyp || !darfSchreiben.value) return
  beschaeftigt.value = true
  try {
    await merkmalePflegen(props.plantyp, werte, props.plan || null)
    emit('reload')
  } catch (e) {
    fehlerListe.value = fehlerMeldungen(e)
  } finally {
    beschaeftigt.value = false
  }
}

/* ── Formular-Handlungen ────────────────────────────────────────────────── */

function quelleSetzen(wert) {
  const neu = quelleGewechselt({ ...form }, wert)
  Object.assign(form, neu)
}

let kategorienVorher = [...(props.lied?.kategorien || [])]
let anlaesseVorher = [...(props.lied?.anlaesse || [])]

function kategorieEntfernen(index) {
  kategorienVorher = form.kategorien.filter((_, i) => i !== index)
  kategorienText.value = kategorienVorher.join(', ')
}

function anlassEntfernen(index) {
  anlaesseVorher = form.anlaesse.filter((_, i) => i !== index)
  anlaesseText.value = anlaesseVorher.join(', ')
}

function hinzufuegen(typ) {
  form.strophen = stropheHinzufuegen(form.strophen, typ)
}
function entfernen(index) {
  form.strophen = stropheEntfernen(form.strophen, index)
}
function verschieben(index, richtung) {
  form.strophen = stropheVerschieben(form.strophen, index, richtung)
}

/* ── Speichern ──────────────────────────────────────────────────────────── */

async function speichern() {
  fehlerListe.value = []
  Object.keys(fehler).forEach((k) => delete fehler[k])
  const ergebnis = pruefen(form)
  Object.assign(fehler, ergebnis.fehler)
  if (!ergebnis.ok) {
    fehlerListe.value = [{ pfad: '', code: 'formular.unvollstaendig', stufe: 'fehler',
                           meldung: 'Bitte die markierten Felder prüfen.', hinweis: '' }]
    // OP-UI-4: Das erste fehlerhafte Feld in den Blick holen und fokussieren —
    // sonst steht die Meldung oben außerhalb des Sichtbereichs (v. a. mobil).
    feldFokussieren()
    return
  }
  if (!darfSchreiben.value) {
    fehlerListe.value = [{ pfad: '', code: 'rechte.lied', stufe: 'fehler',
      meldung: rechteHinweis.value || 'Dafür fehlt dir die Berechtigung.', hinweis: '' }]
    return
  }
  // UXM-R17: Vor dem Anlegen warnen, wenn Buch+Nummer oder Titel schon existieren.
  if (neuanlage.value && !dubletteBestaetigt.value) {
    const treffer = await dublettePruefen()
    if (treffer) {
      dublette.value = treffer
      dubletteDialog.value = true
      return
    }
  }
  beschaeftigt.value = true
  try {
    const werte = nutzlast(form)
    // P1-10b Befund 7: Der Server prüft Dubletten ebenfalls. Erst nach der
    // Warnung im Fenster (dubletteBestaetigt) wird das bewusste Doppel erlaubt.
    if (neuanlage.value && dubletteBestaetigt.value) werte.dublette_bestaetigt = 1
    const antwort = await apiCall('diakronos.psalmos.api.musik.save_lied', { daten: werte })
    const name = antwort?.lied || form.name
    form.name = name
    gespeichert.value = true
    dialogOffen.value = false
    dubletteDialog.value = false
    showToast(neuanlage.value ? 'Lied angelegt.' : 'Lied gespeichert.')
    emit('gespeichert', name)
    emit('reload')
    if (props.plantyp) {
      // Merkmale gelten nur mit einem Lied-Namen und einem Plantyp.
      const offen = Object.entries(merkmale)
        .filter(([, wert]) => wert !== null && wert !== undefined && wert !== '')
        .map(([schluessel, wert]) => ({ ziel: 'sammlung:lieder', schluessel, ziel_id: name, wert }))
      if (offen.length) await merkmalePflegen(props.plantyp, offen, props.plan || null)
    }
    nachDemSpeichern(name)
  } catch (e) {
    fehlerListe.value = fehlerMeldungen(e)
  } finally {
    beschaeftigt.value = false
  }
}

/** Erstes als fehlerhaft markiertes Feld fokussieren und ins Bild holen. */
function feldFokussieren() {
  nextTick(() => {
    const el = document.querySelector('[aria-invalid="true"]')
    if (el) {
      el.focus()
      el.scrollIntoView({ block: 'center' })
    }
  })
}

/**
 * UXM-R17: Gibt es bereits ein Lied mit derselben Buch-/Nummernkennung oder
 * demselben Titel? Liefert eine Beschreibung oder null.
 */
async function dublettePruefen() {
  const titel = String(form.titel || '').trim()
  if (!titel) return null
  try {
    const treffer = await apiCall('diakronos.psalmos.api.musik.get_lieder',
      { suche: titel, limit: 20 })
    const gleich = (treffer || []).filter((l) =>
      String(l.titel || '').trim().toLowerCase() === titel.toLowerCase()
      || (form.buch && form.gesangbuch_nummer
          && String(l.buch || '') === String(form.buch)
          && String(l.gesangbuch_nummer || '') === String(form.gesangbuch_nummer)))
    if (!gleich.length) return null
    const erst = gleich[0]
    return `${erst.titel}${erst.anzeige ? ' (' + erst.anzeige + ')' : ''}${gleich.length > 1 ? ` und ${gleich.length - 1} weitere` : ''}`
  } catch (e) {
    return null   // Prüfung ist ein Zusatz; ohne Auskunft wird nicht blockiert.
  }
}

function dubletteTrotzdem() {
  dubletteBestaetigt.value = true
  dubletteDialog.value = false
  speichern()
}

function nachDemSpeichern(name) {
  const ziel = props.plantyp
    ? null   // Aufrufer (Plan-Stammdaten) lädt selbst neu
    : '#/lieder/' + encodeURIComponent(name)
  if (ziel) navigate(ziel)
}

/* ── Material ───────────────────────────────────────────────────────────── */

function dateiGewaehlt(ereignis) {
  upload.datei = ereignis.target.files?.[0] || null
  const art = artFuerDateiname(upload.datei?.name)
  if (art) upload.art = art
}

async function materialHochladen() {
  // UXM-R7: Kein stummer Abbruch mehr. Fehlt die Datei oder der Lied-Name,
  // gibt es eine Meldung; der Plantyp ist NICHT mehr Bedingung (der Server
  // prüft ohne Plantyp die Psalmos-Regel).
  if (!upload.datei) return
  if (!form.name) {
    fehlerListe.value = [{ pfad: '', code: 'lied.unsaved', stufe: 'fehler',
      meldung: 'Bitte das Lied zuerst speichern, danach Material hochladen.', hinweis: '' }]
    return
  }
  fehlerListe.value = []
  beschaeftigt.value = true
  try {
    const hoch = await uploadDatei(upload.datei)
    const antwort = await liedMaterialHinzufuegen(props.plantyp || null, form.name,
      upload.art, upload.datei.name, hoch.file_url, upload.stimme, upload.beschreibung,
      props.plan || null)
    showToast('Material hinzugefügt.')
    amortisiereMaterial({ material: antwort?.material, art: upload.art, stimme: upload.stimme,
      beschreibung: upload.beschreibung, dateiname: upload.datei.name,
      datei: { datei_url: hoch.file_url, dateiname: upload.datei.name } })
    upload.datei = null
    if (dateiInput.value) dateiInput.value.value = ''
  } catch (e) {
    fehlerListe.value = fehlerMeldungen(e)
  } finally {
    beschaeftigt.value = false
  }
}

async function materialLoeschen(m) {
  // UXM-R8: Der Server erwartet die Kennung der Material-Zeile (m.material),
  // nicht die Anhang-UUID. Altbestand ohne `material` wird nicht gesendet.
  if (!form.name) return
  const zeile = m.material || null
  if (!zeile) {
    fehlerListe.value = [{ pfad: '', code: 'material.zeile', stufe: 'fehler',
      meldung: 'Dieser Materialeintrag kann nicht entfernt werden.', hinweis: '' }]
    return
  }
  fehlerListe.value = []
  beschaeftigt.value = true
  try {
    await liedMaterialLoeschen(props.plantyp || null, form.name, zeile, props.plan || null)
    showToast('Material entfernt.')
    materialStand.value = materialStand.value.filter((x) => (x.material || x.anhang || x.dateiname) !== (zeile || m.anhang || m.dateiname))
    emit('reload')
  } catch (e) {
    fehlerListe.value = fehlerMeldungen(e)
  } finally {
    beschaeftigt.value = false
  }
}

/** Neu hochgeladenes Material sofort anzeigen (kein Nachladen nötig). */
function amortisiereMaterial(eintrag) {
  materialStand.value = [...materialStand.value, eintrag]
  emit('reload')
}

/* ── Ungespeicherte Änderungen ──────────────────────────────────────────── */

const dialogTitel = computed(() =>
  dialogAbsicht.value === 'verlassen' ? 'Änderungen verwerfen?' : 'Änderungen verwerfen?')
const dialogText = computed(() => (dialogAbsicht.value === 'verlassen'
  ? 'Du hast Änderungen an diesem Lied, die noch nicht gespeichert sind. Wenn du gehst, gehen sie verloren.'
  : 'Du hast Änderungen an diesem Lied, die noch nicht gespeichert sind. Wenn du abbrichst, gehen sie verloren.'))
const dialogKnopf = computed(() => (dialogAbsicht.value === 'verlassen' ? 'Verwerfen und gehen' : 'Verwerfen'))

/** Gibt es etwas zu verlieren? (Vergleich der Nutzlast mit dem Ausgangsstand) */
function ungespeichert() {
  if (gespeichert.value) return false
  const start = props.lied
    ? JSON.stringify(nutzlast(formularAusLied(props.lied, props.strophen)))
    : JSON.stringify(nutzlast(leeresFormular()))
  return JSON.stringify(nutzlast(form)) !== start
}

function anfragen(art = 'abbrechen') {
  dialogAbsicht.value = art
  if (!ungespeichert()) {
    verwerfenBestaetigt()
    return
  }
  dialogOffen.value = true
}

function verwerfenBestaetigt() {
  dialogOffen.value = false
  gespeichert.value = true  // es gibt nichts mehr zu warnen
  emit('verlassen', dialogAbsicht.value)
  if (dialogAbsicht.value === 'verlassen') {
    // Der vom Nutzer angestrebte Routenwechsel wurde vom Wächter abgefangen;
    // jetzt (ohne offene Änderungen) dorthin navigieren, sonst auf die Liste.
    const ziel = zielNachVerwerfen
    zielNachVerwerfen = null
    navigate(ziel || '#/lieder')
  }
}

/* ── Verlassen der Seite (Hash-Router) ──────────────────────────────────── */

// Vor jedem Routenwechsel: offene Änderungen abfangen.
// Der Router fragt diesen Wächter VOR dem Seitenwechsel; `false` lässt den
// Nutzer stehen und öffnet die eingebaute Rückfrage. (Ein `hashchange`-Listener
// wäre zu spät — das Ereignis ist nicht abbrechbar.)
let abloesungGuard = null   // Abmelde-Funktion des Routen-Wächters
let zielNachVerwerfen = null  // angestrebte Route, wenn der Nutzer verwirft

function vorRoutenwechsel({ to }) {
  if (!ungespeichert()) return true
  zielNachVerwerfen = to
  dialogAbsicht.value = 'verlassen'
  dialogOffen.value = true
  return false
}

onMounted(() => {
  rechteLaden()
  kandidatenLaden()
  optionenLaden()
  abloesungGuard = onBeforeEach(vorRoutenwechsel)
  // UXM-R16: Auch das Neuladen/Schließen des Tabs verwirft Eingaben — dann
  // soll der Browser warnen (der Router-Wächter greift hier nicht).
  window.addEventListener('beforeunload', vorSeitenverlassen)
})
onBeforeUnmount(() => {
  if (abloesungGuard) abloesungGuard()
  window.removeEventListener('beforeunload', vorSeitenverlassen)
})

/** UXM-R16: Standard-Browserwarnung bei ungespeicherten Änderungen. */
function vorSeitenverlassen(ereignis) {
  if (!ungespeichert()) return
  ereignis.preventDefault()
  ereignis.returnValue = ''
  return ''
}

/**
 * UXM-R1: Kategorien und Anlässe als Auswahl laden (dieselben Optionslisten,
 * die auch die Filter der Lieder-Liste nutzen). Schlägt der Aufruf fehl,
 * bleibt die Freitexteingabe möglich — der Server legt neue Begriffe an.
 */
async function optionenLaden() {
  try {
    const opt = await apiCall('diakronos.psalmos.api.musik.get_lied_filteroptionen', {})
    kategorienVorschlaege.value = opt?.kategorien || []
    anlaesseVorschlaege.value = opt?.anlaesse || []
  } catch (e) {
    // Zusatzangabe; ohne Auskunft bleibt der Freitext.
  }
}

defineExpose({ anfragen, ungespeichert, speichern })
</script>

<style scoped>
.lb { display: flex; flex-direction: column; gap: var(--sp-4); }
.lb-kopf { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--sp-3); flex-wrap: wrap; }
.lb-titel { font-size: var(--fs-h3); font-weight: var(--fw-h); margin: 0; color: var(--text); }
.lb-unter { margin: var(--sp-1) 0 0; font-size: var(--fs); color: var(--muted); }
.lb-meldungen { margin: 0; }
.lb-felder { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: var(--sp-3); margin-bottom: var(--sp-3); }
.lb-quelle-hilfe { grid-column: 1 / -1; font-size: var(--fs-sm); color: var(--muted); margin: 0; }
.lb-textarea { resize: vertical; font: inherit; padding: var(--sp-2); }
.lb-schalter { display: inline-flex; align-items: center; gap: var(--sp-2); font-size: var(--fs-sm); color: var(--text); cursor: pointer; margin-top: var(--sp-2); }
.lb-schalter--klein { margin: 0; font-size: var(--fs-sm); color: var(--muted); }
.lb-chips { display: flex; flex-wrap: wrap; gap: 6px; margin: var(--sp-2) 0; }
.lb-chip-weg { background: none; border: none; color: inherit; cursor: pointer; font: inherit; padding: 0 0 0 4px; }
/* Befund 4: Kennzeichnung neuer Katalogbegriffe im Chip. */
.lb-neu {
  margin-left: 6px; padding: 0 5px; border-radius: 999px;
  background: var(--dk-warning); color: var(--dk-text);
  font-size: 0.7em; font-weight: 600; text-transform: uppercase; letter-spacing: .03em;
}
.lb-strophe { border: 1px solid var(--line); border-radius: var(--radius); padding: var(--sp-3); margin-bottom: var(--sp-3); display: flex; flex-direction: column; gap: var(--sp-2); }
.lb-strophe-kopf { display: flex; align-items: center; gap: var(--sp-2); flex-wrap: wrap; }
.lb-strophe-nr { width: 22px; height: 22px; flex: none; display: grid; place-items: center; border-radius: 50%; background: var(--surface-2); color: var(--muted); font-size: var(--fs-sm); font-weight: 600; }
.lb-strophe-typ { min-width: 130px; }
.lb-strophe-sprache { max-width: 180px; }
.lb-strophe-aktionen { display: inline-flex; gap: var(--sp-1); margin-left: auto; flex-wrap: wrap; }
.lb-strophe-text { resize: vertical; font: inherit; padding: var(--sp-2); line-height: 1.6; }
.lb-strophe-fehler { margin: 0; font-size: var(--fs-sm); color: var(--err); font-weight: 500; }
.lb-hinweis { font-size: var(--fs-sm); color: var(--muted); margin: 0 0 var(--sp-2); }
.lb-merkmal-reihe { display: flex; align-items: flex-start; gap: var(--sp-3); padding: var(--sp-2) 0; border-top: 1px solid var(--divider); flex-wrap: wrap; }
.lb-merkmal-reihe:first-of-type { border-top: none; }
.lb-merkmal-label { font-size: var(--fs-sm); color: var(--muted); min-width: 110px; }
.lb-merkmal-werte { display: flex; flex-wrap: wrap; gap: var(--sp-3); }
.lb-tag-wahl { display: inline-flex; align-items: center; gap: var(--sp-1); font-size: var(--fs-sm); cursor: pointer; }
.lb-material-gruppe { margin-bottom: var(--sp-3); }
.lb-material-art { font-size: var(--fs-sm); font-weight: 600; color: var(--muted); }
.lb-material-liste { list-style: none; margin: var(--sp-1) 0 0; padding: 0; display: flex; flex-direction: column; gap: var(--sp-1); }
.lb-material-eintrag { display: flex; align-items: center; gap: var(--sp-2); flex-wrap: wrap; font-size: var(--fs-sm); }
.lb-material-name { color: var(--text); }
.lb-audio { height: 32px; }
.lb-link { color: var(--primary); text-decoration: none; }
.lb-link:hover { text-decoration: underline; }
.lb-upload { display: flex; flex-wrap: wrap; gap: var(--sp-2); align-items: center; }
.lb-upload-art { min-width: 200px; }
.lb-upload-klein { max-width: 170px; }
.lb-datei { font-size: var(--fs-sm); }
.lb-fuss { display: flex; justify-content: flex-end; gap: var(--sp-2); padding-top: var(--sp-2); }
.lb-dialog-text { margin: 0; font-size: var(--fs); color: var(--text); line-height: 1.55; }
</style>
