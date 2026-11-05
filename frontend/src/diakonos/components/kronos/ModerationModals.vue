<template>
  <!-- Edit Modal -->
  <!-- OP-UI-9: Frueher ein DkModal mit nur „Speichern“ — kein „Abbrechen“,
       kein ✕, Esc wirkungslos; einziger Ausweg war ein Klick ins Dunkle (der
       den Vorschlag ungewollt festlegte). DkDialog bringt ✕, Esc und
       Fokusfalle mit; „Abbrechen“ ist als Fussknopf ergaenzt. -->
  <DkDialog v-model="showEditModal" title="Termin bearbeiten" size="md">
    <form class="dk-mod-form" @submit.prevent="submitEdit">
      <div class="dk-mod-field">
        <label>Titel</label>
        <input v-model="editForm.title" type="text" class="dk-mod-input" required />
      </div>
      <!-- OP-UI-20: Datum und Uhrzeit wie überall über DkDatumZeit. Vorher
           war dies eine von vier Eingabearten (`datetime-local`), deren
           Anzeige je nach Browsersprache anders aussah. -->
      <DkDatumZeit
        v-model="editForm.start"
        v-model:ende-model-value="editForm.end"
        :ganztags="editForm.allDay"
        :mit-ende="true"
        label-datum="Datum"
        label-zeit="Beginn"
      />
      <div class="dk-mod-field dk-mod-field--checkbox">
        <label>
          <input v-model="editForm.allDay" type="checkbox" />
          Ganztägig
        </label>
      </div>
      <div class="dk-mod-field">
        <label>Raum</label>
        <select v-model="editForm.ressource" class="dk-mod-input">
          <option value="">— Kein Raum —</option>
          <option v-for="r in ressources" :key="r.id" :value="r.id">{{ r.title }}</option>
        </select>
      </div>
      <div class="dk-mod-field">
        <label>Beschreibung</label>
        <textarea v-model="editForm.description" rows="3" class="dk-mod-input"></textarea>
      </div>
    </form>
    <template #footer>
      <div class="dk-mod-footer">
        <DkButton variant="secondary" :disabled="submitting" @click="openAblehnen">
          Ablehnen…
        </DkButton>
        <div class="dk-mod-luecke"></div>
        <DkButton variant="secondary" :disabled="submitting" @click="showEditModal = false">
          Abbrechen
        </DkButton>
        <!-- DEV-7 (Befund DMB-eb5c6c69ea54): Ein Kalendermoderator muss den
             Vorschlag hier freigeben koennen — auch seinen EIGENEN. Vorher
             hatte dieser Dialog nur „Speichern“ (blieb Vorschlag) und
             „Ablehnen“; der einzige Freigabeweg war Drag&Drop ins Staging.
             Die Schranke ist serverseitig `_require_moderator`; wer nicht
             moderiert, kommt an diese Seite gar nicht heran. Der Knopf
             uebernimmt die Aenderungen aus dem Formular mit (`festlegen`). -->
        <DkButton
          variant="secondary"
          :disabled="submitting || !editForm.title.trim()"
          data-testid="dk-mod-freigeben"
          @click="submitFreigeben"
        >
          Freigeben
        </DkButton>
        <DkButton variant="primary" :loading="submitting" @click="submitEdit">
          {{ submitting ? '…' : 'Speichern' }}
        </DkButton>
      </div>
    </template>
  </DkDialog>

  <!-- OP-EVENT-12: Ablehnen mit Pflicht-Begruendung ------------------------- -->
  <DkDialog v-model="showAblehnenModal" title="Termin ablehnen" size="sm">
    <form class="dk-mod-form" @submit.prevent="submitAblehnen">
      <p class="dk-mod-hinweis">
        Der Terminvorschlag wird abgelehnt. Der Antragsteller erhält eine
        Nachricht mit deiner Begründung.
      </p>
      <div class="dk-mod-field">
        <label>Grund (Pflicht)</label>
        <textarea
          v-model="ablehnenGrund"
          rows="3"
          class="dk-mod-input"
          placeholder="Warum kann der Termin nicht freigegeben werden?"
          required
        ></textarea>
        <span v-if="ablehnenFehler" class="dk-mod-fehler">{{ ablehnenFehler }}</span>
      </div>
    </form>
    <template #footer>
      <div class="dk-mod-footer">
        <DkButton variant="secondary" :disabled="submitting" @click="showAblehnenModal = false">
          Abbrechen
        </DkButton>
        <div class="dk-mod-luecke"></div>
        <DkButton
          variant="danger"
          :loading="submitting"
          :disabled="!ablehnenGrund.trim()"
          @click="submitAblehnen"
        >
          {{ submitting ? '…' : 'Ablehnen' }}
        </DkButton>
      </div>
    </template>
  </DkDialog>

  <!-- Abgelehnt (Moderations-Historie, P1-5b W-1) -->
  <DkDialog v-model="showAbgelehntModal" title="Abgelehnter Termin" size="sm">
    <div class="dk-mod-form">
      <p class="dk-mod-hinweis">
        Dieser Terminvorschlag wurde abgelehnt. Er erscheint deshalb nicht mehr
        im Kalender.
      </p>
      <div class="dk-mod-field">
        <label>Titel</label>
        <div class="dk-mod-wert">{{ abgelehntEvent?.title }}</div>
      </div>
      <div class="dk-mod-field">
        <label>Beginn</label>
        <div class="dk-mod-wert">{{ abgelehntEvent?.start }}</div>
      </div>
      <div class="dk-mod-field">
        <label>Abgelehnt von</label>
        <div class="dk-mod-wert">{{ abgelehntEvent?.moderiert_von || '—' }}</div>
      </div>
      <div class="dk-mod-field">
        <label>Grund</label>
        <div class="dk-mod-wert">{{ abgelehntEvent?.ablehnungs_grund || '—' }}</div>
      </div>
    </div>
    <template #footer>
      <div class="dk-mod-footer">
        <div class="dk-mod-luecke"></div>
        <DkButton variant="secondary" @click="showAbgelehntModal = false">Schließen</DkButton>
      </div>
    </template>
  </DkDialog>

  <!-- Conflict Modal -->
  <DkModal v-model="showConflictModal" title="Konflikt auflösen" variant="planrahmen">
    <div v-if="conflictLoading" class="dk-mod-loading">Lade Konfliktdaten…</div>
    <template v-else>
      <form class="dk-mod-form" @submit.prevent>
        <div class="dk-mod-row">
          <div class="dk-mod-field dk-mod-field--wide">
            <label>Titel</label>
            <input v-model="conflictForm.title" type="text" class="dk-mod-input" required />
          </div>
        </div>
        <!-- OP-UI-20: gleicher Baustein auch im Konflikt-Fenster. -->
        <DkDatumZeit
          v-model="conflictForm.start"
          v-model:ende-model-value="conflictForm.end"
          :ganztags="conflictForm.allDay"
          :mit-ende="true"
          label-datum="Datum"
          label-zeit="Beginn"
        />
        <div class="dk-mod-field dk-mod-field--checkbox">
          <label>
            <input v-model="conflictForm.allDay" type="checkbox" />
            Ganztägig
          </label>
        </div>
        <div class="dk-mod-field">
          <label>Raum</label>
          <select v-model="conflictForm.ressource" class="dk-mod-input">
            <option value="">— Kein Raum —</option>
            <option v-for="r in ressources" :key="r.id" :value="r.id">{{ r.title }}</option>
          </select>
        </div>
        <div class="dk-mod-field">
          <label>Beschreibung</label>
          <textarea v-model="conflictForm.description" rows="3" class="dk-mod-input"></textarea>
        </div>
      </form>

      <!-- Conflict partner -->
      <div v-if="conflictPartner" class="dk-mod-partner">
        <div class="dk-mod-partner-header">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
          Überschneidung mit
        </div>
        <div class="dk-mod-partner-card">
          <div class="dk-mod-partner-title">{{ conflictPartner.title }}</div>
          <div class="dk-mod-partner-time">{{ fmtDate(conflictPartner.start, conflictPartner.all_day) }}</div>
          <div class="dk-mod-partner-cal">{{ conflictPartner.calendar }}</div>
          <div v-if="conflictPartner.ressource" class="dk-mod-partner-ressource">{{ conflictPartner.ressource }}</div>
          <p class="dk-mod-partner-hint">Passe Zeit oder Raum an um den Konflikt zu vermeiden, oder ignoriere ihn bewusst.</p>
        </div>
      </div>
      <div v-else class="dk-mod-partner dk-mod-partner--empty">
        <p>Kein konkreter Konfliktpartner gefunden. Möglicherweise wurde der überschneidende Termin bereits bearbeitet.</p>
      </div>
    </template>

    <template #footer>
      <div class="dk-mod-konflikt-fuss">
        <div class="dk-mod-conflict-footer">
          <DkButton variant="secondary" :disabled="submitting" @click="resolveAction('ignore')">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg>
            Konflikt ignorieren
          </DkButton>
          <div class="dk-mod-luecke"></div>
          <DkButton variant="secondary" :disabled="submitting" @click="showConflictModal = false">
            Abbrechen
          </DkButton>
          <!-- UX1e: kein „Warn-Knopf“ mehr. „Vorschlagen“ ist gefahrlos und
               deshalb secondary; die Warnung trägt das Symbol. -->
          <DkButton variant="secondary" :disabled="submitting" @click="resolveAction('vorschlag')">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
            Vorschlagen
          </DkButton>
          <DkButton
            variant="primary"
            :disabled="submitting"
            data-testid="dk-mod-freigeben-konflikt"
            :title="'Gibt den Termin trotz Überschneidung frei'"
            @click="resolveAction('festlegen')"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12l5 5l10-10"/></svg>
            Freigeben
          </DkButton>
        </div>
        <!-- DEV-7b: Der Hinweis nennt die Folge, die der Moderator mit dieser
             Entscheidung trifft: der Termin gilt trotz Ueberschneidung, und
             der Konflikt gilt als bewusst uebergangen (er kommt nicht
             wieder). Eigene Zeile unter der Knopfleiste — neben dem Knopf war
             er auf 390 px nur 94 px breit (Befund beim Nachher-Bild). -->
        <p v-if="!conflictLoading" class="dk-mod-konflikt-hinweis">
          „Freigeben“ gibt den Termin trotz Überschneidung frei — der Konflikt gilt damit als bewusst übergangen.
        </p>
      </div>
    </template>
  </DkModal>

  <!-- Series Modal -->
  <DkModal v-model="showSeriesModal" variant="planrahmen">
    <template #default>
      <div class="dk-mod-series-header">
        <h3>{{ seriesGroup?.title }}</h3>
        <span class="dk-mod-series-badge">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="17 1 21 5 17 9"/><path d="M3 11V9a4 4 0 0 1 4-4h14"/><polyline points="7 23 3 19 7 15"/><path d="M21 13v2a4 4 0 0 1-4 4H3"/></svg>
          {{ seriesGroup?.count }} Termine
        </span>
      </div>

      <!-- View mode -->
      <div v-if="seriesMode === 'view'" class="dk-mod-series-body">
        <div class="dk-mod-series-info">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>
          {{ seriesDateRange }}
        </div>
        <div class="dk-mod-series-info">
          <span class="dk-mcard-dot" :style="{ background: sichereFarbe(seriesGroup?.calendar_color) }"></span>
          {{ seriesGroup?.calendar_title }}
        </div>
      </div>

      <!-- Edit mode -->
      <div v-else-if="seriesMode === 'edit'" class="dk-mod-series-body">
        <div class="dk-mod-field">
          <label>Titel (alle {{ seriesGroup?.count }} Termine)</label>
          <input v-model="seriesEditTitle" type="text" class="dk-mod-input" required />
        </div>
      </div>

      <!-- Confirm delete mode -->
      <div v-else-if="seriesMode === 'confirm-delete'" class="dk-mod-series-body">
        <p>Sollen wirklich alle <strong>{{ seriesGroup?.count }} Termine</strong> der Serie <strong>{{ seriesGroup?.title }}</strong> unwiderruflich gelöscht werden?</p>
      </div>
    </template>

    <template #footer>
      <!-- View mode -->
      <div v-if="seriesMode === 'view'" class="dk-mod-series-footer">
        <!-- UX1e2: „Löschen“ stand hier als gefüllter Gefahrenknopf neben dem
             gefüllten Primärknopf „Bearbeiten“ — zwei gefüllte Knöpfe in einem
             Fuß, und der rote zog den Blick auf die Nebenaktion. Er öffnet nur
             die Bestätigung; deshalb secondary wie „Schließen“, die
             Gefahrenfarbe bleibt der Schrift vorbehalten (Klasse
             `dk-mod-loeschen-schrift`). -->
        <DkButton variant="secondary" class="dk-mod-loeschen-schrift" @click="seriesMode = 'confirm-delete'">Löschen</DkButton>
        <div class="dk-mod-luecke"></div>
        <DkButton variant="secondary" @click="showSeriesModal = false">Schließen</DkButton>
        <DkButton variant="primary" @click="seriesMode = 'edit'">Bearbeiten</DkButton>
      </div>
      <!-- Edit mode -->
      <div v-else-if="seriesMode === 'edit'" class="dk-mod-series-footer">
        <!-- UX1e2: siehe oben — Löschen ist hier die Nebenaktion zu
             „Speichern“ und bleibt secondary (Gefahrenfarbe als Schrift). -->
        <DkButton variant="secondary" class="dk-mod-loeschen-schrift" @click="seriesMode = 'confirm-delete'">Löschen</DkButton>
        <div class="dk-mod-luecke"></div>
        <DkButton variant="secondary" @click="seriesMode = 'view'">Abbrechen</DkButton>
        <DkButton variant="primary" :loading="submitting" @click="saveSeries">
          {{ submitting ? '…' : 'Speichern' }}
        </DkButton>
      </div>
      <!-- Confirm delete mode -->
      <div v-else class="dk-mod-series-footer">
        <DkButton variant="secondary" @click="seriesMode = 'view'">Abbrechen</DkButton>
        <div class="dk-mod-luecke"></div>
        <DkButton variant="danger" :loading="submitting" @click="deleteSeries">
          {{ submitting ? '…' : 'Alle löschen' }}
        </DkButton>
      </div>
    </template>
  </DkModal>

  <!-- Series Conflict Modal (list of conflicting dates) -->
  <DkModal v-model="showSeriesConflictModal" title="" variant="planrahmen">
    <template #default>
      <div class="dk-mod-series-header">
        <h3>{{ seriesConflictGroup?.title }}</h3>
        <span class="dk-mod-series-badge dk-mod-series-badge--konflikt">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
          {{ seriesConflictGroup?.konflikt_events?.length || 0 }} Konflikte
        </span>
      </div>
      <div class="dk-mod-series-conflict-intro">
        {{ seriesConflictGroup?.konflikt_events?.length }} von {{ seriesConflictGroup?.count }} Serienterminen haben eine Doppelbuchung.
        Löse jeden Konflikt einzeln auf.
      </div>
      <div class="dk-mod-series-conflict-list">
        <div
          v-for="ev in (seriesConflictGroup?.konflikt_events || [])"
          :key="ev.id"
          class="dk-mod-series-conflict-row"
        >
          <div class="dk-mod-series-conflict-date">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
            {{ fmtDate(ev.start, ev.all_day) }}
          </div>
          <DkButton variant="secondary" size="sm" @click="openSeriesConflictSingle(ev)">Auflösen</DkButton>
        </div>
      </div>
    </template>
    <template #footer>
      <DkButton variant="secondary" @click="showSeriesConflictModal = false">Schließen</DkButton>
    </template>
  </DkModal>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import DkModal from '../DkModal.vue'
import DkDialog from '../ui/DkDialog.vue'
import DkButton from '../ui/DkButton.vue'
import DkDatumZeit from '../ui/DkDatumZeit.vue'
import {
  getConflictPartner,
  resolveConflict,
  updateSeriesBatchFast,
  deleteSeriesBatchFast,
} from '../../api/kanbanApi.js'
import { showToast } from '../../composables/useToast.js'
// UX2g: EINE Quelle fuer angezeigte Fehlertexte statt Floskeln wie
// "Fehler beim Speichern" / "Unbekannter Fehler".
import { aktionsfehler } from '../../../shared/fehlertexte.js'
// UXD-R28: Kalenderfarbe nur als gueltiger Hex-Wert in den style-String.
import { sichereFarbe } from '../../../shared/sichere-ausgabe.js'
import { serienMeldung } from '../../composables/serienMeldung.mjs'

const props = defineProps({
  ressources: { type: Array, default: () => [] },
})

const emit = defineEmits(['resolved', 'series-updated', 'series-deleted'])

const submitting = ref(false)

// ── Helpers ──────────────────────────────────────────────────────────────────
function fmtDate(str, allDay) {
  if (!str) return ''
  const d = new Date(str)
  if (isNaN(d)) return str
  const opts = { weekday: 'short', day: '2-digit', month: '2-digit' }
  if (allDay) return d.toLocaleDateString('de-DE', opts)
  return d.toLocaleDateString('de-DE', opts) + ' · ' +
         d.toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' })
}

/**
 * OP-EVENT-12: Bei Serien im Folgejahr fehlte die Jahreszahl („Mo., 26.07.“).
 * Das Jahr wird angehaengt, wenn es nicht das laufende Jahr ist.
 */
function fmtDateMitJahr(str, allDay) {
  const basis = fmtDate(str, allDay)
  const d = new Date(str)
  if (isNaN(d)) return basis
  if (d.getFullYear() === new Date().getFullYear()) return basis
  return `${basis} ${d.getFullYear()}`
}

function getEditFormData(form) {
  return {
    title: form.title || '',
    // OP-UI-20: DkDatumZeit liefert bereits „YYYY-MM-DD HH:MM“ — das ist das
    // Serverformat; die frühere Umrechnung von/nach `datetime-local` entfällt.
    element_start: form.allDay ? null : (form.start || null),
    element_end: form.allDay ? null : (form.end || null),
    all_day: form.allDay ? 1 : 0,
    ressource: form.ressource || '',
    description: form.description || '',
  }
}

// ── Edit Modal ───────────────────────────────────────────────────────────────
const showEditModal = ref(false)
const editEvent = ref(null)
const editForm = ref({ title: '', start: '', end: '', allDay: false, ressource: '', description: '' })

function openEditModal(event) {
  editEvent.value = event
  editForm.value = {
    title: event.title || '',
    start: event.start || '',
    end: event.end || '',
    allDay: !!event.all_day,
    ressource: event.ressource || '',
    description: event.description || '',
  }
  showEditModal.value = true
}

async function submitEdit() {
  if (!editEvent.value) return
  submitting.value = true
  try {
    await resolveConflict(editEvent.value.id, 'vorschlag', getEditFormData(editForm.value))
    showEditModal.value = false
    emit('resolved')
  } catch (e) {
    showToast(aktionsfehler('speichern', e), 'error')
  } finally {
    submitting.value = false
  }
}

/**
 * DEV-7 (Befund DMB-eb5c6c69ea54): Vorschlag aus dem Dialog freigeben.
 *
 * Nimmt die (ggf. korrigierten) Formularwerte mit und setzt den Termin auf
 * „Festgelegt“ — fuer eigene und fremde Vorschlaege gleich. Vorher blieb der
 * Termin nach „Speichern“ ein Vorschlag, und der Dialog bot gar keine Freigabe
 * an; der einzige Weg war das Staging. Wer hier klickt, ist bereits als
 * Moderator am Kalender angemeldet (die Seite ist Moderatoren vorbehalten,
 * `_require_moderator` prueft es serverseitig erneut).
 */
async function submitFreigeben() {
  if (!editEvent.value) return
  submitting.value = true
  try {
    await resolveConflict(editEvent.value.id, 'festlegen', getEditFormData(editForm.value))
    showEditModal.value = false
    showToast('Termin freigegeben', 'success')
    emit('resolved')
  } catch (e) {
    showToast(e.message || 'Fehler beim Freigeben', 'error')
  } finally {
    submitting.value = false
  }
}

// ── OP-EVENT-12: Ablehnen mit Pflicht-Begruendung ─────────────────────────────
const showAblehnenModal = ref(false)
const ablehnenGrund = ref('')
const ablehnenFehler = ref('')
const ablehnenEvent = ref(null)

function openAblehnen() {
  ablehnenEvent.value = editEvent.value
  ablehnenGrund.value = ''
  ablehnenFehler.value = ''
  showEditModal.value = false
  showAblehnenModal.value = true
}

async function submitAblehnen() {
  if (!ablehnenEvent.value) return
  const grund = ablehnenGrund.value.trim()
  if (!grund) {
    // Der Server prueft ebenfalls — hier die schnelle, verstaendliche Meldung.
    ablehnenFehler.value = 'Bitte einen Grund angeben.'
    return
  }
  ablehnenFehler.value = ''
  submitting.value = true
  try {
    await resolveConflict(ablehnenEvent.value.id, 'ablehnen', { grund })
    showAblehnenModal.value = false
    showToast('Termin abgelehnt', 'success')
    emit('resolved')
  } catch (e) {
    showToast(e.message || 'Fehler beim Ablehnen', 'error')
  } finally {
    submitting.value = false
  }
}

// ── Abgelehnt: Moderations-Historie (P1-5b W-1) ──────────────────────────────
const showAbgelehntModal = ref(false)
const abgelehntEvent = ref(null)

function openAbgelehntModal(event) {
  abgelehntEvent.value = event
  showAbgelehntModal.value = true
}

// ── Conflict Modal ───────────────────────────────────────────────────────────
const showConflictModal = ref(false)
const conflictEvent = ref(null)
const conflictPartner = ref(null)
const conflictLoading = ref(false)
const conflictForm = ref({ title: '', start: '', end: '', allDay: false, ressource: '', description: '' })

async function openConflictModal(event) {
  conflictEvent.value = event
  conflictPartner.value = null
  conflictLoading.value = true
  conflictForm.value = {
    title: event.title || '',
    start: event.start || '',
    end: event.end || '',
    allDay: !!event.all_day,
    ressource: event.ressource || '',
    description: event.description || '',
  }
  showConflictModal.value = true

  try {
    conflictPartner.value = await getConflictPartner(event.id)
  } catch {
    // no partner
  } finally {
    conflictLoading.value = false
  }
}

async function resolveAction(action) {
  if (!conflictEvent.value) return
  submitting.value = true
  try {
    // DEV-7b: Dieser Dialog loest eine UEBERSCHNEIDUNG auf. „Freigeben“ gibt
    // den Termin bewusst TROTZ Konflikt frei (Operator-Entscheidung) — dann
    // muss der Konflikt als bewusst uebergangen gelten, sonst taucht der
    // Termin erneut als Konflikt auf. `ueberschneidung: 1` setzt serverseitig
    // zusaetzlich `ignore_conflict=1` (kanban_api.resolve_conflict).
    const werte = getEditFormData(conflictForm.value)
    if (action === 'festlegen') werte.ueberschneidung = 1
    await resolveConflict(conflictEvent.value.id, action, werte)
    showConflictModal.value = false
    emit('resolved')
  } catch (e) {
    showToast(e.message || 'Fehler bei der Konfliktlösung', 'error')
  } finally {
    submitting.value = false
  }
}

// ── Series Modal ─────────────────────────────────────────────────────────────
const showSeriesModal = ref(false)
const seriesGroup = ref(null)
const seriesMode = ref('view')
const seriesEditTitle = ref('')

const seriesDateRange = computed(() => {
  if (!seriesGroup.value) return ''
  const sameDay = seriesGroup.value.first_start === seriesGroup.value.last_start
  if (sameDay) return fmtDateMitJahr(seriesGroup.value.first_start, seriesGroup.value.all_day)
  return `${fmtDateMitJahr(seriesGroup.value.first_start, seriesGroup.value.all_day)} – ${fmtDateMitJahr(seriesGroup.value.last_start, seriesGroup.value.all_day)}`
})

function openSeriesModal(group) {
  seriesGroup.value = group
  seriesMode.value = 'view'
  seriesEditTitle.value = group.title
  showSeriesModal.value = true
}

async function saveSeries() {
  if (!seriesGroup.value || !seriesEditTitle.value.trim()) return
  submitting.value = true
  try {
    // P1-5c (9): Der Server verwirft bei einem Nicht-Moderator z. B. den
    // Serien-Status und meldet das in `verworfen`/`meldung`. Diese Antwort
    // wurde vorher nicht ausgewertet — der Nutzer glaubte an eine wirksame
    // Änderung. Jetzt wird sie als Hinweis gezeigt.
    const antwort = await updateSeriesBatchFast(
      seriesGroup.value.series_id, seriesEditTitle.value.trim(),
    )
    showSeriesMeldung(antwort)
    showSeriesModal.value = false
    emit('series-updated')
  } catch (e) {
    showToast(e.message || 'Fehler beim Aktualisieren der Serie', 'error')
  } finally {
    submitting.value = false
  }
}

/**
 * Antwort des Serien-Updates auswerten (P1-5c, Punkt 9).
 *
 * Der Server verwirft bei einem Nicht-Moderator z. B. den Status und meldet
 * das in `verworfen`/`meldung`. Ohne diese Anzeige glaubte der Nutzer an eine
 * wirksame Änderung. Die Entscheidung, WAS gezeigt wird, liegt in
 * `serienMeldung()` (rein und testbar).
 */
function showSeriesMeldung(antwort) {
  const meldung = serienMeldung(antwort)
  if (!meldung) return
  showToast(meldung.text, meldung.type)
}

async function deleteSeries() {
  if (!seriesGroup.value) return
  submitting.value = true
  try {
    await deleteSeriesBatchFast(seriesGroup.value.series_id)
    showSeriesModal.value = false
    emit('series-deleted')
  } catch (e) {
    showToast(aktionsfehler('loeschen', e), 'error')
  } finally {
    submitting.value = false
  }
}

// ── Series Conflict Modal ────────────────────────────────────────────────────
const showSeriesConflictModal = ref(false)
const seriesConflictGroup = ref(null)

function openSeriesKonfliktModal(group) {
  seriesConflictGroup.value = group
  showSeriesConflictModal.value = true
}

function openSeriesConflictSingle(ev) {
  showSeriesConflictModal.value = false
  openConflictModal(ev)
}

// ── Expose for parent ────────────────────────────────────────────────────────
defineExpose({
  openEditModal,
  openConflictModal,
  openSeriesModal,
  openSeriesKonfliktModal,
  openAbgelehntModal,
})
</script>

<style scoped>
.dk-mod-form { display: flex; flex-direction: column; gap: var(--sp-3); }
/* UXK-R12: `min-width:0` erlaubt es den Feldern in der Zeile zu schrumpfen;
   ohne das ragte das Feld „Ende“ aus dem Dialog. */
.dk-mod-field { display: flex; flex-direction: column; gap: var(--sp-1); min-width: 0; }
.dk-mod-field label { font-size: var(--fs-sm); font-weight: var(--fw-mittel); color: var(--muted); }
/* UXK-R12: Die Checkbox „Ganztägig“ war nur 2 px breit (vom globalen
   `input { width: 100% }` zusammengedrueckt). Feste Groesse, nicht schrumpfen. */
.dk-mod-field--checkbox label { display: flex; align-items: center; gap: var(--sp-2); cursor: pointer; font-size: var(--fs-14); }
.dk-mod-field--checkbox input[type="checkbox"] {
  flex: none;
  width: 16px;
  height: 16px;
  margin: 0;
}
.dk-mod-field--wide { flex: 1; min-width: 0; }
.dk-mod-row { display: flex; gap: var(--sp-3); min-width: 0; }
.dk-mod-row .dk-mod-field { flex: 1; min-width: 0; }
/* K1 (DES-REST-b): Das breite Moderationsfenster (DkModal variant="planrahmen",
   760 px) spannt die Datumsfelder über die ganze Zeile — „Datum“ und „Ende am“
   wurden dabei unnötig lang. Die Felder bekommen hier eine gemeinsame,
   lesbare Breite und brechen am Handy untereinander um. */
.dk-mod-form :deep(.dk-ui-datumzeit-felder) {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: var(--sp-3);
  align-items: flex-start;
}
.dk-mod-form :deep(.dk-ui-datumzeit-felder > *) { min-width: 0; }
@media (max-width: 420px) {
  .dk-mod-form :deep(.dk-ui-datumzeit-felder) { grid-template-columns: 1fr; }
}
.dk-mod-input {
  width: 100%;
  min-width: 0;
  box-sizing: border-box;
  padding: 8px 10px;
  background: var(--surface-2);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  font-size: var(--fs-14);
  font-family: inherit;
  color: var(--text);
  outline: none;
  transition: border-color var(--fast);
}
.dk-mod-input:focus { border-color: var(--dk-navy-400); }
/* DES-02: `style="flex:1"` als Klasse — schiebt die Hauptaktion nach rechts. */
.dk-mod-luecke { flex: 1; }
.dk-mod-loading { padding: var(--sp-5); text-align: center; color: var(--muted); font-size: var(--fs-14); }
/* OP-EVENT-12: Hinweis- und Fehlertexte im Ablehnen-Dialog */
.dk-mod-hinweis { margin: 0; font-size: var(--fs-sm); color: var(--muted); line-height: 1.5; }
/* P1-5b (W-1): Nur-Lese-Wert im Dialog „Abgelehnter Termin“. */
.dk-mod-wert { font-size: var(--fs-sm); color: var(--text); overflow-wrap: anywhere; }
.dk-mod-fehler { font-size: var(--fs-sm); color: var(--err); }

/* Partner */
.dk-mod-partner { margin-top: var(--sp-4); }
.dk-mod-partner-header { display: flex; align-items: center; gap: var(--sp-2); font-size: var(--fs-14); font-weight: var(--fw-fett); color: var(--warn); margin-bottom: var(--sp-2); }
.dk-mod-partner-card { background: var(--surface-2); border: 1px solid var(--line); border-radius: var(--radius); padding: var(--sp-3); font-size: var(--fs-14); }
.dk-mod-partner-title { font-weight: var(--fw-fett); margin-bottom: 4px; }
.dk-mod-partner-time, .dk-mod-partner-cal, .dk-mod-partner-ressource { color: var(--muted); font-size: var(--fs-sm); margin-bottom: 2px; }
.dk-mod-partner-hint { margin: var(--sp-2) 0 0; font-size: var(--fs-sm); color: var(--subtle); }
.dk-mod-partner--empty { padding: var(--sp-3); background: var(--surface-2); border-radius: var(--radius); }
.dk-mod-partner--empty p { margin: 0; font-size: var(--fs-14); color: var(--muted); }

/* Conflict footer */
/* DEV-7b (Befund Opus-Review, Befund 1): Die Basisregel wurde beim Umbau der
   Knopfleiste geloescht (Commit 6033c69) — nur der @media-Block blieb. Ohne
   sie steht die Fussleiste auf dem Desktop nicht als Zeile rechtsbuendig
   ausgerichtet: „Ablehnen…“ verlässt die Knopfreihe und rutscht in eine
   eigene Zeile (alle drei Dialoge, ModerationModals.vue Z. 43/93/135).
   `dk-modal-actions` (DkModal) brachte die Zeile nebenbei ins Lot, DkDialog
   (`.dk-ui-dialog-fuss`) nicht — deshalb fehlte es dort sichtbar. */
.dk-mod-footer {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: var(--sp-2);
  padding-top: var(--sp-2);
}
.dk-mod-conflict-footer { display: flex; align-items: center; gap: var(--sp-2); width: 100%; }
/* DEV-7: Die Knopfleiste des Vorschlagsdialogs hat jetzt vier Knoepfe
   (Ablehnen / Abbrechen / Freigeben / Speichern) — vorher waren es drei.
   Am Handy (390 px) ist nebeneinander kein Platz; sie bricht deshalb um,
   „Ablehnen…“ steht dann allein in der ersten Zeile. Bis 480 px bekommt
   jeder Knopf seine natuerliche Breite (`DkButton` schrumpft sonst und
   schneidet das Label ab). */
@media (max-width: 480px) {
  .dk-mod-footer { flex-wrap: wrap; row-gap: var(--sp-2); }
  .dk-mod-footer > * { flex: 0 0 auto; }
  .dk-mod-footer .dk-mod-luecke { flex: 1 0 100%; height: 0; }
}

/* Series modal */
.dk-mod-series-header { display: flex; align-items: center; gap: var(--sp-2); margin-bottom: var(--sp-3); }
.dk-mod-series-header h3 { margin: 0; font-size: var(--fs-h3); font-weight: var(--fw-fett); }
.dk-mod-series-badge, .dk-mod-series-badge--konflikt {
  display: inline-flex; align-items: center; gap: 4px;
  font-size: var(--fs-sm); font-weight: var(--fw-mittel); padding: 2px 8px; border-radius: var(--badge-r);
  background: var(--surface-2); color: var(--muted);
}
.dk-mod-series-badge--konflikt { background: var(--err-soft); color: var(--err); }
.dk-mod-series-body { font-size: var(--fs-14); }
.dk-mod-series-info { display: flex; align-items: center; gap: var(--sp-2); color: var(--muted); margin-bottom: var(--sp-2); }
.dk-mod-series-footer { display: flex; align-items: center; gap: var(--sp-2); width: 100%; }
.dk-mod-series-conflict-intro { font-size: var(--fs-14); color: var(--muted); margin-bottom: var(--sp-3); }
.dk-mod-series-conflict-list { display: flex; flex-direction: column; gap: var(--sp-2); }
.dk-mod-series-conflict-row { display: flex; align-items: center; justify-content: space-between; gap: var(--sp-2); padding: 8px 10px; background: var(--surface-2); border-radius: var(--radius-sm); }
.dk-mod-series-conflict-date { display: flex; align-items: center; gap: var(--sp-2); font-size: var(--fs-14); color: var(--muted); }

/* UX1e: `.dk-mod-btn-inline`, `.dk-mod-btn-warn`, `.dk-mod-btn-ok` und
   `.dk-mod-btn-danger-outline` sind weg — die vier Eigenknöpfe sind jetzt
   DkButton (secondary/danger, sm) und bekommen ihre Optik vom Knopf-System.
   Vorher standen zwei verschiedene „Löschen“-Knöpfe nebeneinander: der eine
   gefüllt rot, der andere rot nur in der Schrift. */
/* DEV-7b: Hinweis unter der Konflikt-Knopfleiste (Folge der bewussten Freigabe). */
.dk-mod-konflikt-fuss { display: flex; flex-direction: column; width: 100%; }
.dk-mod-konflikt-hinweis {
  margin: var(--sp-2) 0 0;
  font-size: var(--fs-sm);
  color: var(--muted);
  line-height: 1.5;
}
/* UX1e2: Nebenaktion „Löschen“ im Serienfuß. Der Knopf bleibt secondary (die
   Fläche gehört dem einen Primärknopf), die Gefahr zeigt die Schrift — dieselbe
   Farbe wie der Gefahrenknopf (--err), nur nicht gefüllt. Im Dunkelmodus zieht
   --err automatisch mit (tokens.css). */
.dk-mod-loeschen-schrift { color: var(--err); }
.dk-mod-loeschen-schrift:hover:not(:disabled) { color: var(--err); }
</style>
