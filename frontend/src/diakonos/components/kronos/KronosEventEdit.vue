<template>
  <Teleport to="body">
    <div v-if="show" class="diakronos-modal show" @click.self="onBackdropClick">
      <div
        ref="fenster"
        class="diakronos-modal-dialog"
        role="dialog"
        aria-modal="true"
        aria-label="Termin bearbeiten"
        tabindex="-1"
        @keydown="tastenFaenger"
      >
        <div class="diakronos-modal-content">
          <!-- Farbige Leiste -->
          <div class="diakronos-color-bar" :style="{ backgroundColor: selectedCalendarColor }"></div>

          <div class="diakronos-modal-header">
            <h3>Termin bearbeiten</h3>
            <button class="close-btn" aria-label="Schließen" @click="close">&times;</button>
          </div>

          <!-- Tabs -->
          <DkTabs
            class="diakronos-tabs"
            aria-label="Bereiche"
            :model-value="activeTab"
            :options="[{ value: 'basic', label: 'Grunddaten' }, { value: 'details', label: 'Details' }]"
            @update:model-value="activeTab = $event"
          />

          <div class="tab-content">
            <!-- Tab 1: Grunddaten -->
            <div v-show="activeTab === 'basic'">
              <DkField label="Titel" required>
                <input v-model="form.element_name" class="dk-mod-input" type="text" maxlength="140" placeholder="Termintitel" />
              </DkField>

              <!-- OP-UI-20: Datum und Uhrzeit über den gemeinsamen Baustein
                   (deutsche Anzeige, native Auswahl am Handy). Vorher stand
                   hier der ISO-Wert „2026-12-30 00:00“ im Feld. -->
              <DkDatumZeit
                v-model="form.element_start"
                v-model:ende-model-value="form.element_end"
                :ganztags="form.all_day"
                :mit-ende="true"
                required
                label-datum="Datum"
                label-zeit="Beginn"
                :fehler-datum="zeitFehler.datum"
                :fehler-zeit="zeitFehler.beginn"
                :fehler-ende="zeitFehler.ende"
                :fehler-enddatum="zeitFehler.enddatum"
              />

              <DkCheckbox v-model="form.all_day" label="Ganztägig" />

              <DkField label="Kalender" required>
                <DkSelect v-model="form.element_calendar" :options="calendarOptions" placeholder="Bitte wählen" empty-value="" />
              </DkField>

              <DkField label="Ort">
                <DkSelect v-model="form.ressource" :options="ortOptions.map(r => ({ value: r.id, label: r.title }))" placeholder="Bitte wählen" empty-value="" />
              </DkField>

              <!-- Weitere Ressourcen -->
              <div class="section-divider">Weitere Ressourcen</div>
              <div
                v-for="(row, idx) in form.zusaetzliche_ressourcen"
                :key="idx"
                class="zusatz-resource-row"
              >
                <select v-model="row.ressource" class="zusatz-select">
                  <option value="">Aus Katalog wählen</option>
                  <option
                    v-for="res in catalogOptions(row.ressource)"
                    :key="res.id"
                    :value="res.id"
                  >
                    {{ res.title }}
                  </option>
                </select>
                <input
                  v-model="row.freitext_ressource"
                  type="text"
                  class="zusatz-input"
                  placeholder="oder Freitext"
                />
                <DkBadge
                  class="status-chip"
                  :variant="row.status === 'Bestätigt' ? 'ok' : 'warn'"
                >
                  <!-- OP-EVENT-10: siehe KronosEventCreate — Status-Chip nur
                       fuer Ressourcenmoderatoren klickbar. -->
                  <button
                    v-if="istRessourcenmoderator"
                    type="button"
                    class="status-chip-btn"
                    @click="row.status = row.status === 'Bestätigt' ? 'Angefragt' : 'Bestätigt'"
                  >
                    {{ row.status }}
                  </button>
                  <span v-else class="status-chip-text">{{ row.status }}</span>
                </DkBadge>
                <button class="remove-row-btn" aria-label="Zeile entfernen" @click="form.zusaetzliche_ressourcen.splice(idx, 1)">&times;</button>
              </div>
              <button class="add-row-btn" @click="addAdditionalResource">+ Ressource hinzufügen</button>
            </div>

            <!-- Tab 2: Details -->
            <div v-show="activeTab === 'details'">
              <DkField label="Beschreibung">
                <textarea v-model="form.description" class="dk-mod-input" rows="3"></textarea>
              </DkField>

              <DkField label="Kategorie">
                <DkSelect v-model="form.element_category" :options="categories.map(c => ({ value: c.name, label: c.event_category_name }))" placeholder="Bitte wählen" empty-value="" />
              </DkField>

              <DkCheckbox v-model="form.ignore_conflict" label="Konflikte ignorieren" />
            </div>
          </div>

          <div class="diakronos-modal-footer">
            <DkButton v-if="!showDeleteConfirm" variant="danger" class="btn-delete" @click="showDeleteConfirm = true">
              Löschen
            </DkButton>
            <div v-if="showDeleteConfirm" class="delete-confirm-inline">
              <span>Wirklich löschen?</span>
              <DkButton variant="danger" @click="doDelete">Ja</DkButton>
              <DkButton variant="secondary" @click="showDeleteConfirm = false">Nein</DkButton>
            </div>
            <div class="footer-luecke"></div>
            <DkButton variant="secondary" @click="close">Abbrechen</DkButton>
            <DkButton variant="primary" @click="save">Speichern</DkButton>
          </div>
        </div>
      </div>
    </div>

    <!-- Konflikt-Dialog -->
    <KronosConflictDialog ref="conflictDialog" />
  </Teleport>
</template>

<script setup>
import { apiAntwortPruefen } from '../../composables/useApi.js'
import { ref, reactive, watch, computed, onMounted, nextTick } from 'vue'
import { useFormularSchutz } from '../../composables/useFormularSchutz.js'
import { pruefeSitzungsAntwort } from '../../composables/useApi.js'
import KronosConflictDialog from './KronosConflictDialog.vue'
import DkField from '../ui/DkField.vue'
import DkDatumZeit from '../ui/DkDatumZeit.vue'
import DkSelect from '../ui/DkSelect.vue'
import DkCheckbox from '../ui/DkCheckbox.vue'
import DkTabs from '../ui/DkTabs.vue'
import DkBadge from '../ui/DkBadge.vue'
import DkButton from '../ui/DkButton.vue'
import { showToast } from '../../composables/useToast.js'
import { useDialogFokus } from '../../composables/useDialogFokus.js'
import {
  zerlegeDatumZeit, istDatum, pruefeZeitraumMitDatum, datumNach,
} from '../../composables/datumZeit.mjs'

const props = defineProps({
  show: { type: Boolean, default: false },
  event: { type: Object, default: () => ({}) }
})

const emit = defineEmits(['update:show', 'updated', 'deleted'])

const activeTab = ref('basic')
const conflictDialog = ref(null)
const showDeleteConfirm = ref(false)

const calendars = ref([])
const categories = ref([])
const ressources = ref([])
const kronosSettings = ref({})
// OP-EVENT-10: Ressourcenmoderator? Nur er darf den Status-Chip umschalten.
const istRessourcenmoderator = ref(false)


const form = reactive({
  name: '',
  element_name: '',
  element_start: '',
  element_end: '',
  all_day: false,
  element_calendar: '',
  ressource: '',
  description: '',
  element_category: '',
  ignore_conflict: false,
  status: '',
  zusaetzliche_ressourcen: []
})

const selectedCalendarColor = computed(() => {
  const cal = calendars.value.find(c => c.name === form.element_calendar)
  return cal?.color || 'var(--primary)'
})

const calendarOptions = computed(() => calendars.value.map(c => ({ value: c.name, label: c.calendar_name })))

// Ort-Dropdown: nur Räume, aber aktuellen Wert immer anbieten (Legacy)
const ortOptions = computed(() => {
  const allResources = ressources.value?.resources || []
  const raumList = allResources.filter(r => r.typ === 'Raum')
  if (form.ressource && !raumList.find(r => r.id === form.ressource)) {
    const currentRes = allResources.find(r => r.id === form.ressource)
    if (currentRes) return [currentRes, ...raumList]
  }
  return raumList
})

function catalogOptions(currentValue) {
  const allResources = ressources.value?.resources || []
  // Keine Raeume/Orte in den weiteren Ressourcen - Ort sitzt am Haupt-Event
  const list = allResources.filter(r => r.typ !== 'Raum')
  // Aktuell gewaehlten Wert (z.B. Legacy-Eintrag) immer anbieten, damit er nicht verloren geht
  if (currentValue && !list.find(r => r.id === currentValue)) {
    const currentRes = allResources.find(r => r.id === currentValue)
    if (currentRes) return [currentRes, ...list]
  }
  return list
}

function addAdditionalResource() {
  form.zusaetzliche_ressourcen.push({
    ressource: '',
    freitext_ressource: '',
    status: 'Angefragt',
    notiz: ''
  })
}

function populateForm() {
  const ev = props.event || {}
  form.name = ev.name || ''
  form.element_name = ev.element_name || ''
  form.element_start = ev.element_start || ''
  form.element_end = ev.element_end || ''
  form.all_day = !!ev.all_day
  form.element_calendar = ev.element_calendar || ''
  form.ressource = ev.ressource || ''
  form.description = ev.description || ''
  form.element_category = ev.element_category || ''
  form.ignore_conflict = !!ev.ignore_conflict
  form.status = ev.status || ''

  // Load zusaetzliche_ressourcen from event extendedProps
  const additional = ev.zusaetzliche_ressourcen || []
  form.zusaetzliche_ressourcen = additional.map(row => ({
    ressource: row.ressource || '',
    freitext_ressource: row.freitext_ressource || '',
    status: row.status || 'Angefragt',
    notiz: row.notiz || ''
  }))

  activeTab.value = 'basic'
  showDeleteConfirm.value = false
}

// OP-UI-20: flatpickr entfällt — DkDatumZeit bringt deutsche Anzeige und
// die native Auswahl des Geräts mit. Damit ist auch der sichtbare ISO-Wert
// („2026-12-30 00:00“) weg, der Anlass dieses Befunds war.
const zeitFehler = ref({ datum: '', beginn: '', ende: '', enddatum: '' })

const formularSchutz = useFormularSchutz(() => form, () => saving.value)
async function close() {
  if (await formularSchutz.darfSchliessen()) emit('update:show', false)
}

// DES-R6: Fokus hinein, Tab bleibt im Fenster, Esc schliesst (der Dialog
// hatte weder role noch Fokusfuehrung; der Fokus stand auf <body>).
const fenster = ref(null)
const { tastenFaenger } = useDialogFokus(computed(() => props.show), fenster, close)

// UXK-002: kurzer Schutz gegen den Doppelklick-Fehlschlag (Backdrop).
let geoeffnet_am = 0

function onBackdropClick() {
  if (Date.now() - geoeffnet_am < 400) return
  // Auch nach dem Doppelklickschutz darf ein Tipp daneben nichts verwerfen.
}

async function loadData() {
  try {
    const csrf = document.querySelector('meta[name="csrf-token"]')?.content || ''
    const [calRes, catRes, resRes, settingsRes, sessRes] = await Promise.all([
      fetch("/api/method/diakronos.kronos.api.permissions.get_writable_calendars", { credentials: 'same-origin' }).then(apiAntwortPruefen),
      fetch("/api/resource/Eventkategorie?fields=[\"name\",\"event_category_name\"]&limit_page_length=500", { credentials: 'same-origin' }).then(apiAntwortPruefen),
      fetch("/api/method/diakronos.kronos.api.ressource_api.get_ressources", {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json', 'X-Frappe-CSRF-Token': csrf },
        body: JSON.stringify({})
      }).then(apiAntwortPruefen),
      fetch("/api/method/diakronos.kronos.api.ressource_api.get_kronos_settings", {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json', 'X-Frappe-CSRF-Token': csrf },
        body: JSON.stringify({})
      }).then(apiAntwortPruefen),
      fetch("/api/method/diakronos.kronos.api.permissions.get_session_info", { credentials: 'same-origin' }).then(apiAntwortPruefen).catch(() => ({}))
    ])

    calendars.value = calRes.message || []
    categories.value = catRes.data || []
    ressources.value = resRes.message || {}
    kronosSettings.value = settingsRes.message || {}
    // OP-EVENT-10: siehe KronosEventCreate.
    const rollen = sessRes?.message?.roles || []
    istRessourcenmoderator.value = rollen.includes('Ressourcenmoderator')
      || rollen.includes('Mitgliederadministrator')
      || rollen.includes('System Manager')
  } catch (err) {
    console.error('Fehler beim Laden der Daten:', err)
  }
}

async function checkConflict() {
  if (form.ignore_conflict) return false
  const hasOrt = !!form.ressource
  const additionalIds = (form.zusaetzliche_ressourcen || [])
    .filter(r => r.ressource)
    .map(r => r.ressource)

  if (!hasOrt && additionalIds.length === 0) return false

  try {
    const csrf = document.querySelector('meta[name="csrf-token"]')?.content || ''
    const res = await fetch("/api/method/diakronos.kronos.api.ressource_api.check_resource_conflict", {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', 'X-Frappe-CSRF-Token': csrf },
      body: JSON.stringify({
        ressource: form.ressource || '',
        element_start: form.element_start,
        element_end: form.element_end,
        exclude_id: form.name,
        zusaetzliche_ressourcen: additionalIds.map(id => ({ ressource: id }))
      })
    })
    const data = await apiAntwortPruefen(res)
    return data.message?.has_conflict ? data.message : null
  } catch (err) {
    console.error('Konfliktprüfung fehlgeschlagen:', err)
    throw err
  }
}

const saving = ref(false)
async function save() {
  if (saving.value) return
  saving.value = true
  try { await speichern() } finally { saving.value = false }
}

async function speichern() {
  if (!form.element_name || !form.element_calendar || !form.element_start) {
    showToast('Bitte Titel, Beginn und Kalender ausfüllen.', 'error')
    return
  }

  let conflictMsg
  try {
    conflictMsg = await checkConflict()
  } catch (err) {
    showToast(err?.message || 'Die Verfügbarkeit konnte nicht geprüft werden. Bitte erneut versuchen.', 'error')
    return
  }
  if (conflictMsg) {
    const result = await conflictDialog.value?.show({
      element_name: form.element_name,
      element_start: form.element_start,
      element_end: form.element_end,
      ressource: form.ressource,
      conflicts: (conflictMsg.conflicts || []).map(c => {
        const res = (ressources.value?.resources || []).find(r => r.id === c.ressource)
        return { ...c, ressource_title: res ? res.title : c.ressource }
      })
    })
    if (!result) return
    if (result === 'ignore') form.ignore_conflict = true
    // UXK-R6: „Als Konflikt markieren“ setzt den Status (Moderationsspalte).
    if (result === 'conflict') form.status = 'Konflikt'
  }

  await doSave()
}

/**
 * OP-UI-20: Datum/Uhrzeit prüfen und die Meldung am Feld zeigen.
 * Ein Ende vor dem Beginn fiel bisher erst dem Server auf.
 */
function pruefeTerminZeit() {
  const start = zerlegeDatumZeit(form.element_start)
  const ende = zerlegeDatumZeit(form.element_end)
  const fehler = { datum: '', beginn: '', ende: '', enddatum: '' }
  if (!istDatum(start.datum)) {
    fehler.datum = 'Bitte ein gültiges Datum wählen.'
  } else if (!form.all_day && !start.zeit) {
    fehler.beginn = 'Bitte eine Beginnzeit angeben.'
  }
  // B2: Enddatum vor dem Beginndatum ist ein Fehler — mehrtägige Termine
  // (auch mit früherer Endzeit) sind es nicht.
  if (!fehler.datum && ende.datum && !datumNach(ende.datum, start.datum)
      && ende.datum !== start.datum) {
    fehler.enddatum = 'Das Ende liegt vor dem Beginn.'
  }
  if (!fehler.datum && !fehler.beginn && !fehler.enddatum) {
    fehler.ende = pruefeZeitraumMitDatum(
      start.datum, start.zeit, ende.datum, ende.zeit, form.all_day,
    )
  }
  zeitFehler.value = fehler
  if (fehler.datum || fehler.beginn || fehler.ende || fehler.enddatum) {
    showToast(fehler.datum || fehler.beginn || fehler.enddatum || fehler.ende, 'error')
    return false
  }
  return true
}

async function doSave() {
  if (!pruefeTerminZeit()) return
  const validAdditional = (form.zusaetzliche_ressourcen || []).filter(r => r.ressource || r.freitext_ressource)

  const payload = {
    name: form.name,
    element_name: form.element_name,
    element_start: form.element_start,
    element_end: form.element_end,
    all_day: form.all_day ? 1 : 0,
    element_calendar: form.element_calendar,
    ressource: form.ressource || null,
    description: form.description || null,
    element_category: form.element_category || null,
    ignore_conflict: form.ignore_conflict ? 1 : 0,
    status: form.status || null,
    zusaetzliche_ressourcen: JSON.stringify(validAdditional)
  }

  try {
    const csrf = document.querySelector('meta[name="csrf-token"]')?.content || ''
    const res = await fetch("/api/method/diakronos.kronos.api.event_crud.save_event", {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', 'X-Frappe-CSRF-Token': csrf },
      body: JSON.stringify(payload)
    })

    // UXK-R2: Zuerst den HTTP-Status pruefen. Frueher entschied
    // `if (data.message)` — jede Fehlerantwort der Compat-Schicht traegt aber
    // ein `message`-Feld, also galt auch 403 als Erfolg und der Dialog schloss.
    let data = null
    try { data = await apiAntwortPruefen(res, { fehlerWerfen: false }) } catch { data = null }
    pruefeSitzungsAntwort(res, data)
    if (!res.ok || !data || data.exc || data.message?.success !== true) {
      showToast(extrahiereFehler(data, res), 'error')
      return
    }
    const antwort = data.message || {}
    if (antwort.aenderung_wartet) {
      // Operator-Regel: an einem festgelegten Termin wartet diese Aenderung
      // auf die Freigabe durch die Terminmoderation.
      showToast('Änderung wartet auf Freigabe (Terminmoderation).', 'success')
    } else {
      showToast('Termin gespeichert.', 'success')
    }
    emit('updated')
    emit('update:show', false)
  } catch (err) {
    console.error('Speichern fehlgeschlagen:', err)
    showToast('Termin konnte nicht gespeichert werden. Bitte erneut versuchen.', 'error')
  }
}

async function doDelete() {
  if (!form.name) return
  try {
    const csrf = document.querySelector('meta[name="csrf-token"]')?.content || ''
    const res = await fetch("/api/method/diakronos.kronos.api.event_crud.delete_event", {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', 'X-Frappe-CSRF-Token': csrf },
      body: JSON.stringify({ name: form.name })
    })

    // UXK-R2: Fehlerantworten (403/404/500) duerfen nicht als Erfolg gelten.
    let data = null
    try { data = await apiAntwortPruefen(res, { fehlerWerfen: false }) } catch { data = null }
    pruefeSitzungsAntwort(res, data)
    if (!res.ok || !data || data.exc || data.message?.success !== true) {
      showToast(extrahiereFehler(data, res), 'error')
      return
    }
    showToast('Termin gelöscht.', 'success')
    emit('deleted')
    emit('update:show', false)
    showDeleteConfirm.value = false
  } catch (err) {
    console.error('Löschen fehlgeschlagen:', err)
    showToast('Termin konnte nicht gelöscht werden. Bitte erneut versuchen.', 'error')
  }
}

/** Verstaendlichste Fehlermeldung aus einer API-Antwort (wie im Create-Dialog). */
function extrahiereFehler(data, res) {
  if (data) {
    const kandidaten = [
      data.message, data.exception, data.exc, data.detail, data.error,
      Array.isArray(data._server_messages) ? data._server_messages.join(' ') : data._server_messages,
    ]
    for (const k of kandidaten) {
      if (typeof k === 'string' && k.trim()) return aufraeumen(k)
    }
  }
  if (res.status === 403) return 'Keine Berechtigung: Du darfst diesen Termin nicht ändern.'
  if (res.status === 417 || res.status === 400) return 'Die Angaben sind unvollständig oder ungültig.'
  if (res.status >= 500) return 'Der Server konnte den Termin nicht speichern. Bitte später erneut versuchen.'
  return 'Termin konnte nicht gespeichert werden.'
}

function aufraeumen(text) {
  let t = String(text).trim()
  try {
    const parsed = JSON.parse(t)
    if (typeof parsed === 'string') t = parsed
    else if (Array.isArray(parsed) && typeof parsed[0] === 'string') t = parsed[0]
    else if (parsed && typeof parsed.message === 'string') t = parsed.message
  } catch { /* kein JSON — Text belassen */ }
  return t.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim() || 'Termin konnte nicht gespeichert werden.'
}

watch(() => props.show, async (val) => {
  if (val) {
    geoeffnet_am = Date.now()
    zeitFehler.value = { datum: '', beginn: '', ende: '', enddatum: '' }
    populateForm()
    formularSchutz.merken()
  } else {
    showDeleteConfirm.value = false
  }
})

watch(() => props.event, (val) => {
  if (props.show && val) {
    populateForm()
    formularSchutz.merken()
  }
}, { deep: true })

onMounted(() => {
  loadData()
  if (props.show) {
    populateForm()
    formularSchutz.merken()
  }
})
</script>

<style scoped>
.diakronos-modal {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: color-mix(in oklch, var(--dk-navy-900) 55%, transparent);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: var(--z-modal);
  opacity: 0;
  visibility: hidden;
  transition: opacity var(--med) var(--ease), visibility var(--med) var(--ease);
}
.diakronos-modal.show {
  opacity: 1;
  visibility: visible;
}
.diakronos-modal-dialog {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-lg);
  max-width: 560px;
  width: 90%;
  max-height: 90vh;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}
.diakronos-modal-content {
  display: flex;
  flex-direction: column;
  max-height: 90vh;
}
.diakronos-color-bar {
  height: 6px;
  width: 100%;
  transition: background-color var(--med) var(--ease);
}
.diakronos-modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--sp-4) var(--sp-5);
  border-bottom: 1px solid var(--line);
}
.diakronos-modal-header h3 {
  margin: 0;
  font-size: var(--fs-h2);
  font-weight: var(--fw-h);
  color: var(--text);
}
.close-btn {
  background: none;
  border: none;
  font-size: 1.5rem;
  cursor: pointer;
  color: var(--muted);
  line-height: 1;
}
.close-btn:hover { color: var(--text); }
.diakronos-tabs { margin: 0; }
.tab-content {
  padding: var(--sp-4) var(--sp-5);
  overflow-y: auto;
  max-height: calc(90vh - 200px);
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
}
.form-row {
  display: flex;
  gap: var(--sp-3);
}
.form-row > * {
  flex: 1;
}
.dk-mod-input {
  width: 100%;
  padding: 8px 10px;
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  font-size: var(--fs);
  font-family: inherit;
  color: var(--text);
  box-sizing: border-box;
  outline: none;
  transition: border-color var(--fast);
}
.dk-mod-input:focus { border-color: var(--dk-navy-400); }

/* Weitere Ressourcen section */
.section-divider {
  font-weight: 600;
  font-size: var(--fs);
  color: var(--text);
  margin: var(--sp-2) 0 0;
  padding-top: var(--sp-3);
  border-top: 1px solid var(--line);
}
.zusatz-resource-row {
  display: flex;
  gap: var(--sp-2);
  align-items: center;
}
.zusatz-select,
.zusatz-input {
  flex: 1;
  padding: 6px 8px;
  border: 1px solid var(--line);
  border-radius: var(--radius-sm);
  font-size: var(--fs-sm);
  font-family: inherit;
  background: var(--surface);
  color: var(--text);
  box-sizing: border-box;
  min-width: 0;
}
.status-chip { flex-shrink: 0; }
.status-chip-btn {
  background: none;
  border: none;
  color: inherit;
  font: inherit;
  cursor: pointer;
  padding: 0;
}
.remove-row-btn {
  background: none;
  border: none;
  color: var(--subtle);
  font-size: 1.1rem;
  cursor: pointer;
  padding: 0 2px;
  flex-shrink: 0;
}
.remove-row-btn:hover {
  color: var(--err);
}
.add-row-btn {
  background: none;
  border: 1px dashed var(--line-strong);
  border-radius: var(--radius-sm);
  padding: 6px 12px;
  font-size: var(--fs-sm);
  color: var(--muted);
  font-family: inherit;
  cursor: pointer;
  width: 100%;
}
.add-row-btn:hover {
  border-color: var(--accent);
  color: var(--accent);
}

/* K1 (DES-REST-b): Auf schmalen Anzeigen passen Löschen + Abbrechen +
   Speichern nicht in eine Zeile. Vorher lief der Löschen-Knopf links aus dem
   Fenster (bei 390 px abgeschnitten). Jetzt bricht die Zeile um und die
   Knöpfe bleiben vollständig sichtbar. */
.diakronos-modal-footer {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  flex-wrap: wrap;
  gap: var(--sp-2);
  padding: var(--sp-3) var(--sp-5);
  border-top: 1px solid var(--line);
  background: var(--surface-2);
}
.btn-delete {
  margin-right: auto;
}
.footer-luecke { flex: 1 1 0; }
@media (max-width: 480px) {
  .diakronos-modal-footer {
    padding: var(--sp-3) var(--sp-4);
  }
  .diakronos-modal-footer > .btn-delete { margin-right: 0; }
  /* K1: Der Platzhalter zwang die Knöpfe bei 390 px in eine Zeile. Am Handy
     fällt er weg, die Zeile bricht um. */
  .diakronos-modal-footer > .footer-luecke { display: none; }
  .diakronos-modal-footer .delete-confirm-inline { margin-right: 0; flex-basis: 100%; }
}
.delete-confirm-inline {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  margin-right: auto;
}
.delete-confirm-inline span {
  font-size: var(--fs);
  color: var(--err);
  font-weight: 500;
}
</style>
