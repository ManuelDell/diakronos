<template>
  <DkDialog
    :model-value="modelValue"
    :title="ueberschrift"
    size="lg"
    @update:model-value="$emit('update:modelValue', $event)"
    @close="$emit('update:modelValue', false)"
  >
    <!-- Meldungen in Klartext -->
    <PrMeldungen v-if="meldungen.length" :meldungen="meldungen" />

    <!-- Grunddaten -->
    <div class="lgb-felder">
      <DkField label="Name der Gruppe" required :error="fehler.gruppenname">
        <input
          ref="ersteEingabe"
          v-model="form.gruppenname"
          class="dk-form-input"
          type="text"
          maxlength="140"
          placeholder="z. B. Chorlieder 2026, Gesangbuch, Musical Josef"
          :aria-invalid="!!fehler.gruppenname || undefined"
        />
      </DkField>

      <DkField label="Art" :help="typHilfe" :error="fehler.typ">
        <DkSelect
          :model-value="form.typ"
          :options="typOptionen"
          @update:model-value="(v) => (form.typ = v)"
        />
      </DkField>

      <DkField label="Status">
        <DkSelect
          :model-value="form.status"
          :options="statusOptionen"
          @update:model-value="(v) => (form.status = v)"
        />
      </DkField>

      <DkField label="Dauer (Minuten)" :error="fehler.dauer_minuten" help="Optional — Gesamtdauer der Gruppe.">
        <input v-model="form.dauer_minuten" class="dk-form-input" type="number" min="0" max="600" inputmode="numeric" />
      </DkField>

      <DkField label="Komponist/in" help="Optional.">
        <input v-model="form.komponist" class="dk-form-input" type="text" maxlength="140" />
      </DkField>

      <DkField label="Textdichter/in" help="Optional.">
        <input v-model="form.textautor" class="dk-form-input" type="text" maxlength="140" />
      </DkField>

      <DkField label="Verlag" help="Optional.">
        <input v-model="form.verlag" class="dk-form-input" type="text" maxlength="140" />
      </DkField>
    </div>

    <DkField label="Beschreibung" help="Optional — wofür ist diese Gruppe da?">
      <textarea v-model="form.beschreibung" class="dk-form-input lgb-textarea" rows="2"></textarea>
    </DkField>

    <!-- Lieder zuordnen -->
    <DkCard title="Lieder dieser Gruppe" :class="'lgb-lieder'">
      <p class="lgb-hinweis">
        Lieder hinzufügen, mit den Pfeilen in die richtige Reihenfolge bringen und bei Bedarf wieder entfernen.
      </p>

      <DkEmpty
        v-if="!form.lieder.length"
        title="Noch keine Lieder"
        text="Such ein Lied und füge es hinzu."
        icon="🎵"
      />

      <ol v-else class="lgb-liste">
        <li v-for="(z, i) in form.lieder" :key="z.lied" class="lgb-zeile">
          <span class="lgb-nr">{{ i + 1 }}</span>
          <span class="lgb-titel">{{ z.titel || z.lied }}</span>
          <span v-if="z.nummer" class="lgb-num">{{ z.nummer }}</span>
          <span class="lgb-aktionen">
            <DkButton variant="ghost" size="sm" :disabled="i === 0" @click="verschieben(i, -1)">Nach oben</DkButton>
            <DkButton variant="ghost" size="sm" :disabled="i === form.lieder.length - 1" @click="verschieben(i, 1)">Nach unten</DkButton>
            <DkButton variant="ghost" size="sm" @click="entfernen(i)">Entfernen</DkButton>
          </span>
        </li>
      </ol>

      <div class="lgb-suche">
        <div class="dk-toolbar-search lgb-suche-feld">
          <input
            v-model="suche"
            type="text"
            placeholder="Lied suchen (Titel, Nummer, Buch)…"
            @input="sucheStarten"
          />
        </div>
        <ul v-if="treffer.length" class="lgb-treffer">
          <li v-for="l in treffer" :key="l.name">
            <button type="button" class="dk-btn dk-btn-secondary dk-btn-sm" @click="hinzufuegen(l)">
              + {{ l.titel }}<span v-if="l.anzeige"> ({{ l.anzeige }})</span>
            </button>
          </li>
        </ul>
        <span v-else-if="suche && !sucheLaeuft" class="lgb-leer">Keine Lieder gefunden.</span>
      </div>
    </DkCard>

    <template #footer>
      <DkButton variant="ghost" @click="$emit('update:modelValue', false)">Abbrechen</DkButton>
      <DkButton variant="primary" :loading="beschaeftigt" @click="speichern">
        {{ istNeuanlage ? 'Gruppe anlegen' : 'Änderungen speichern' }}
      </DkButton>
    </template>
  </DkDialog>
</template>

<script setup>
/**
 * P1-10 / UXM-R9 — Liedgruppen anlegen und bearbeiten.
 *
 * Reine Logik (Prüfung, Zuordnungen, Nutzlast) steht in
 * `components/lieder/liedgruppe-bearbeiten.mjs` und ist dort node-getestet.
 * Der Server entscheidet über Rechte; die Komponente bietet nur an, was er
 * nicht ohnehin verweigert.
 */
import { ref, reactive, computed, watch, nextTick } from 'vue'
import { usePlanrahmen, fehlerMeldungen } from '../../composables/usePlanrahmen.js'
import { showToast } from '../../composables/useToast.js'
import DkDialog from '../ui/DkDialog.vue'
import DkCard from '../ui/DkCard.vue'
import DkField from '../ui/DkField.vue'
import DkSelect from '../ui/DkSelect.vue'
import DkButton from '../ui/DkButton.vue'
import DkEmpty from '../ui/DkEmpty.vue'
import PrMeldungen from '../planrahmen/PrMeldungen.vue'
import {
  LIEDGRUPPE_TYPEN, LIEDGRUPPE_STATUS, TYP_HILFEN,
  leereGruppe, gruppeAusDetail, istNeu, pruefen, nutzlast,
  liedHinzufuegen, liedEntfernen, liedVerschieben,
} from './liedgruppe-bearbeiten.mjs'

const props = defineProps({
  modelValue: Boolean,
  /** Liedgruppen-Detail (get_liedgruppe_detail) zum Ändern; null = Neuanlage. */
  detail: { type: Object, default: null },
})
const emit = defineEmits(['update:modelValue', 'gespeichert'])

const { liedgruppeSpeichern, liederSuchen } = usePlanrahmen()

const form = reactive(props.detail ? gruppeAusDetail(props.detail) : leereGruppe())
const fehler = reactive({})
const meldungen = ref([])
const beschaeftigt = ref(false)
const ersteEingabe = ref(null)

const suche = ref('')
const treffer = ref([])
const sucheLaeuft = ref(false)
let sucheTimer = null

const istNeuanlage = computed(() => istNeu(form))
const ueberschrift = computed(() => (istNeuanlage.value ? 'Neue Liedgruppe' : 'Liedgruppe bearbeiten'))
const typOptionen = LIEDGRUPPE_TYPEN.map((t) => ({ value: t, label: t }))
const statusOptionen = LIEDGRUPPE_STATUS.map((s) => ({ value: s, label: s }))
const typHilfe = computed(() => TYP_HILFEN[form.typ] || '')

/* Beim Öffnen: Formular an das übergebene Detail angleichen. */
watch(() => [props.modelValue, props.detail], ([offen]) => {
  if (!offen) return
  const neu = props.detail ? gruppeAusDetail(props.detail) : leereGruppe()
  Object.assign(form, neu)
  meldungen.value = []
  Object.keys(fehler).forEach((k) => delete fehler[k])
  suche.value = ''
  treffer.value = []
  nextTick(() => ersteEingabe.value?.focus?.())
}, { deep: false })

function sucheStarten() {
  clearTimeout(sucheTimer)
  sucheLaeuft.value = true
  sucheTimer = setTimeout(async () => {
    try {
      const daten = await liederSuchen(suche.value, 30)
      treffer.value = Array.isArray(daten) ? daten : []
    } catch (e) {
      treffer.value = []
    } finally {
      sucheLaeuft.value = false
    }
  }, 250)
}

function hinzufuegen(l) {
  form.lieder = liedHinzufuegen(form.lieder, l)
}
function entfernen(i) {
  form.lieder = liedEntfernen(form.lieder, i)
}
function verschieben(i, richtung) {
  form.lieder = liedVerschieben(form.lieder, i, richtung)
}

async function speichern() {
  meldungen.value = []
  Object.keys(fehler).forEach((k) => delete fehler[k])
  const ergebnis = pruefen(form)
  Object.assign(fehler, ergebnis.fehler)
  if (!ergebnis.ok) {
    // OP-UI-4: Erstes fehlerhaftes Feld in den Blick holen (mobil wichtig).
    nextTick(() => {
      const el = document.querySelector('[aria-invalid="true"]')
      if (el) { el.focus(); el.scrollIntoView({ block: 'center' }) }
    })
    meldungen.value = [{ pfad: '', code: 'formular.unvollstaendig', stufe: 'fehler',
                         meldung: 'Bitte die markierten Felder prüfen.', hinweis: '' }]
    return
  }
  beschaeftigt.value = true
  try {
    const antwort = await liedgruppeSpeichern(nutzlast(form))
    showToast(istNeuanlage.value ? 'Liedgruppe angelegt.' : 'Liedgruppe gespeichert.')
    emit('gespeichert', antwort?.liedgruppe || form.name)
    emit('update:modelValue', false)
  } catch (e) {
    meldungen.value = fehlerMeldungen(e)
  } finally {
    beschaeftigt.value = false
  }
}
</script>

<style scoped>
.lgb-felder {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: var(--sp-3);
  margin-bottom: var(--sp-3);
}
.lgb-textarea { resize: vertical; font: inherit; padding: var(--sp-2); }
.lgb-lieder { margin-top: var(--sp-4); }
.lgb-hinweis { font-size: var(--fs-sm); color: var(--muted); margin: 0 0 var(--sp-2); }
.lgb-liste { list-style: none; margin: 0 0 var(--sp-3); padding: 0; display: flex; flex-direction: column; gap: var(--sp-1); }
.lgb-zeile { display: flex; align-items: center; gap: var(--sp-2); flex-wrap: wrap; border: 1px solid var(--line); border-radius: var(--radius); padding: var(--sp-2) var(--sp-3); }
.lgb-nr { width: 22px; height: 22px; flex: none; display: grid; place-items: center; border-radius: 50%; background: var(--surface-2); color: var(--muted); font-size: var(--fs-sm); font-weight: 600; }
.lgb-titel { font-size: var(--fs-sm); font-weight: 500; color: var(--text); }
.lgb-num { font-size: var(--fs-sm); color: var(--muted); }
.lgb-aktionen { margin-left: auto; display: inline-flex; gap: var(--sp-1); flex-wrap: wrap; }
.lgb-suche { margin-top: var(--sp-2); }
.lgb-suche-feld { max-width: 360px; }
.lgb-treffer { list-style: none; margin: var(--sp-2) 0 0; padding: 0; display: flex; flex-wrap: wrap; gap: var(--sp-2); }
.lgb-leer { font-size: var(--fs-sm); color: var(--muted); }
</style>
