<template>
  <div class="dk-screen dk-screen-wide dk-screen-enter">

    <!-- Header -->
    <!-- OP-UI-19: keine Zahl, solange nichts geladen ist. Vorher stand beim
         ersten Aufbau „0 Räume & Gegenstände verfügbar“ da — eine Aussage,
         die wie ein Ergebnis aussah. -->
    <DkPageHeader title="Ressourcen" :sub="kopfUntertitel">
      <template #actions>
        <DkButton
          :variant="showMyBookings ? 'primary' : 'secondary'"
          @click="toggleMyBookings"
        >
          <IconCalendarCheck class="dk-icon-sm" />
          Meine Buchungen
        </DkButton>
        <DkButton v-if="isAdmin" variant="primary" @click="openBookingModal()">
          <IconPlus class="dk-icon-sm" />
          Buchung anlegen
        </DkButton>
      </template>
    </DkPageHeader>

    <!-- Toolbar -->
    <div class="dk-toolbar">
      <div class="dk-toolbar-search">
        <svg class="dk-search-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
        <input v-model="searchQuery" type="text" placeholder="Ressource suchen…" @input="onSearchInput" />
      </div>

      <!-- DES-01: Filterzeile aus dem gemeinsamen Baustein (vorher drei von
           Hand gebaute Knöpfe, ohne Zustandsansage und ohne „Alle“). -->
      <DkFilterChips
        :chips="typChips"
        :model-value="typeFilter"
        aria-label="Ressourcen nach Art filtern"
        @waehlen="typeFilter = $event"
      />

      <span class="rs-toolbar-luecke" />

      <!-- DES-01/DES-06: Ansichtsumschalter bleibt ein eigener Knopf (Symbol
           ohne Text), sagt seinen Zustand jetzt aber an. -->
      <button
        class="dk-ui-chip"
        :class="{ 'is-active': viewMode === 'grid' }"
        :aria-pressed="viewMode === 'grid'"
        aria-label="Kachelansicht"
        title="Kachelansicht"
        @click="viewMode = 'grid'"
      >
        <IconLayoutGrid class="dk-icon-sm" />
      </button>
      <button
        class="dk-ui-chip"
        :class="{ 'is-active': viewMode === 'list' }"
        :aria-pressed="viewMode === 'list'"
        aria-label="Listenansicht"
        title="Listenansicht"
        @click="viewMode = 'list'"
      >
        <IconList class="dk-icon-sm" />
      </button>
    </div>

    <!-- Main Content Grid -->
    <div class="dk-two-col-wide rs-layout" :class="{ 'has-sidebar': showMyBookings || selectedResource }">

      <!-- Ressourcen-Grid / List -->
      <div class="rs-main">

        <!-- OP-UI-19: eine Ladeform für alle Seiten (DkSkelett). -->
        <DkSkelett v-if="loading" form="karten" :anzahl="6" text="Ressourcen werden geladen …" />

        <!-- Grid View -->
        <div v-else-if="viewMode === 'grid'" class="dk-card-grid">
          <!-- P3-4 (Restpunkt 2): Die Karte war ein <button> und enthielt den
               „Buchen“-Knopf — ein Knopf im Knopf (ungültiges HTML, unklares
               Tastatur-/Screenreader-Verhalten). Die Karte ist jetzt ein
               normales <div>; „Buchen“ bleibt ein eigener Knopf.
               P3-4b/W3: Die Kachel ist trotzdem als GANZES anwählbar — der
               Titelknopf wird per `::after` über die Kachel gedehnt
               (Stretched Link, dasselbe Muster wie in den Tabellen). So bleibt
               es bei EINEM bedienbaren Element für die Auswahl (Tab-Folge
               unverändert, kein Knopf im Knopf), und „Buchen“ liegt darüber. -->
          <div
            v-for="r in filteredResources"
            :key="r.id"
            class="dk-content-card rs-card"
            :class="{ 'is-selected': selectedResource?.id === r.id }"
          >
            <div class="rs-card-image" :class="`type-${r.type}`">
              <div class="rs-card-icon">
                <Icon v-if="r.type === 'room'" icon="building" />
                <Icon v-else-if="r.type === 'vehicle'" icon="truck" />
                <Icon v-else icon="box" />
              </div>
              <div class="rs-card-badge" :class="r.status">{{ statusLabel(r.status) }}</div>
            </div>
            <div class="rs-card-body">
              <button
                type="button"
                class="rs-card-title rs-card-title--knopf"
                :aria-pressed="selectedResource?.id === r.id ? 'true' : 'false'"
                @click="selectResource(r)"
              >{{ r.name }}</button>
              <div class="rs-card-meta">
                <span class="rs-card-type">{{ typeLabel(r.type) }}</span>
                <span v-if="r.capacity" class="rs-card-capacity"><IconUsers class="dk-icon-xs" /> {{ r.capacity }}</span>
              </div>
              <div class="rs-card-desc">{{ r.description }}</div>
              <div class="rs-card-tags">
                <span v-for="tag in r.tags" :key="tag" class="rs-tag">{{ tag }}</span>
              </div>
              <div class="rs-card-footer">
                <DkButton variant="secondary" size="sm" class="rs-btn-book" @click="openBookingModal(r)">
                  <IconCalendar class="dk-icon-xs" /> Buchen
                </DkButton>
              </div>
            </div>
          </div>
        </div>

        <!-- List View -->
        <div v-else-if="filteredResources.length" class="dk-card-list">
          <div class="dk-card-list-header">
            <span class="rs-spalte rs-spalte--name"><span class="truncate">Name</span></span>
            <span class="rs-spalte rs-spalte--typ">Typ</span>
            <span class="rs-spalte rs-spalte--status">Status</span>
            <span class="rs-spalte rs-spalte--aktionen">Aktionen</span>
          </div>
          <div
            v-for="r in filteredResources"
            :key="r.id"
            class="dk-card-list-row rs-list-row"
            :class="{ 'is-selected': selectedResource?.id === r.id }"
            @click="selectResource(r)"
          >
            <div class="rs-list-name">
              <div class="rs-list-icon" :class="`type-${r.type}`">
                <Icon v-if="r.type === 'room'" icon="building" />
                <Icon v-else-if="r.type === 'vehicle'" icon="truck" />
                <Icon v-else icon="box" />
              </div>
              <div>
                <div class="rs-list-title">{{ r.name }}</div>
                <div class="rs-list-sub">{{ r.description }}</div>
              </div>
            </div>
            <div class="rs-spalte rs-spalte--typ">
              <span class="rs-type-badge" :class="r.type">{{ typeLabel(r.type) }}</span>
            </div>
            <div class="rs-spalte rs-spalte--status">
              <span class="rs-status-dot" :class="r.status">{{ statusLabel(r.status) }}</span>
            </div>
            <div class="rs-spalte rs-spalte--aktionen">
              <DkButton variant="secondary" size="sm" class="rs-btn-book-sm" @click.stop="openBookingModal(r)">
                <IconCalendar class="dk-icon-xs" /> Buchen
              </DkButton>
            </div>
          </div>
        </div>

        <!-- OP-UI-19/S10: drei Leerfälle statt eines Satzes. -->
        <DkEmpty
          v-if="!loading && filteredResources.length === 0"
          :icon="filterAktiv ? '🔍' : '📦'"
          :title="filterAktiv ? 'Keine Ressource gefunden' : 'Noch keine Ressource angelegt'"
          :text="filterAktiv
            ? 'Passe den Filter an oder suche nach einem anderen Begriff.'
            : 'Sobald Räume, Fahrzeuge oder Gegenstände erfasst sind, erscheinen sie hier.'"
          class="rs-leer"
        >
          <DkButton v-if="filterAktiv" variant="ghost" size="sm" @click="filterZuruecksetzen">Filter zurücksetzen</DkButton>
        </DkEmpty>

        <!-- Offene Anfragen (Moderatoren) -->
        <div v-if="isModerator" class="rs-moderation-section">
          <div class="rs-moderation-header">
            <h2 class="rs-moderation-title">
              <IconClipboard class="dk-icon-md" />
              Offene Anfragen
              <span v-if="anfragen.length" class="rs-moderation-count">{{ anfragen.length }}</span>
            </h2>
            <button class="dk-btn dk-btn-sm dk-btn-ghost" @click="loadAnfragen" :disabled="loadingAnfragen"
              title="Offene Anfragen aktualisieren" aria-label="Offene Anfragen aktualisieren">
              <IconRefresh class="dk-icon-sm" :class="{ 'spin': loadingAnfragen }" />
            </button>
          </div>

          <div v-if="anfragen.length === 0" class="rs-moderation-empty">
            Keine offenen Anfragen.
          </div>

          <div v-for="a in anfragen" :key="a.id" class="rs-anfrage-card">
            <!-- Konflikt-Warnbanner (UXK-R8: eine Zeile je Eintrag, kein „[]“) -->
            <div v-if="konfliktHinweise(a).length" class="rs-anfrage-konflikt">
              <IconInfo class="dk-icon-xs dk-schrumpf-nicht" />
              <div>
                <div v-for="(k, i) in konfliktHinweise(a)" :key="i" class="rs-konflikt-zeile">
                  {{ konfliktText(k) }}
                </div>
              </div>
            </div>

            <div class="rs-anfrage-body">
              <div class="rs-anfrage-ressource">
                {{ a.ressource_name }}
                <!-- P1-4b/B1: der Moderator soll sehen, woher die Anfrage kommt:
                     eine Raumbuchung oder eine Ressourcen-Zuordnung am Termin. -->
                <span v-if="a.quelle === 'termin'" class="rs-anfrage-quelle">am Termin</span>
              </div>
              <div class="rs-anfrage-zweck">{{ a.zweck }}</div>
              <div class="rs-anfrage-meta">
                <span>{{ a.datum_von_fmt }} – {{ a.datum_bis_fmt }}</span>
                <span>von {{ a.gebucht_von_name }}</span>
              </div>
              <div v-if="a.notizen" class="rs-anfrage-notiz">{{ a.notizen }}</div>
            </div>

            <div class="rs-anfrage-actions">
              <!-- P1-4b/B1: gespiegelte Termin-Ressourcen (quelle="termin") sind
                   Kind-Zeilen eines Termins — sie werden am Termin entschieden,
                   nicht ueber `decide_buchung` (das laedt `Ressourcen Buchung`). -->
              <DkButton
                v-if="a.quelle === 'termin'"
                variant="primary"
                size="sm"
                @click="approveTerminRessource(a)"
              >
                <IconCheck class="dk-icon-xs" /> Freigeben
              </DkButton>
              <DkButton
                v-else
                variant="primary"
                size="sm"
                @click="approveBuchung(a.id)"
              >
                <IconCheck class="dk-icon-xs" /> Freigeben
              </DkButton>
              <DkButton variant="danger" size="sm" @click="openRejectModal(a)">
                <IconX class="dk-icon-xs" /> Ablehnen
              </DkButton>
            </div>
          </div>
        </div>
      </div>

      <!-- Right Sidebar: Detail OR My Bookings -->
      <div v-if="showMyBookings || selectedResource" ref="sidebarRef" class="rs-sidebar">

        <!-- Detail Panel -->
        <div v-if="selectedResource && !showMyBookings" class="rs-detail">
          <div class="rs-detail-header">
            <button class="rs-detail-close" aria-label="Detailansicht schliessen"
              title="Detailansicht schliessen" @click="selectedResource = null">
              <IconX class="dk-icon-md" />
            </button>
          </div>

          <div class="rs-detail-image" :class="`type-${selectedResource.type}`">
            <div class="rs-detail-icon">
              <Icon v-if="selectedResource.type === 'room'" icon="building" />
              <Icon v-else-if="selectedResource.type === 'vehicle'" icon="truck" />
              <Icon v-else icon="box" />
            </div>
          </div>

          <div class="rs-detail-body">
            <h2 class="rs-detail-title">{{ selectedResource.name }}</h2>
            <div class="rs-detail-meta">
              <span class="rs-type-badge" :class="selectedResource.type">{{ typeLabel(selectedResource.type) }}</span>
              <span v-if="selectedResource.capacity" class="rs-detail-capacity"><IconUsers class="dk-icon-xs" /> {{ selectedResource.capacity }} Plätze</span>
            </div>
            <p class="rs-detail-desc">{{ selectedResource.description }}</p>

            <div class="rs-detail-section">
              <h4>Ausstattung</h4>
              <div class="rs-detail-tags">
                <span v-for="tag in selectedResource.tags" :key="tag" class="rs-tag">{{ tag }}</span>
              </div>
            </div>

            <div class="rs-detail-section">
              <h4>Buchungen</h4>
              <div v-if="resourceBookings.length === 0" class="rs-empty">
                Keine bevorstehenden Buchungen.
              </div>
              <div v-for="b in resourceBookings" :key="b.id" class="rs-booking-item">
                <div class="rs-booking-date">
                  <div class="rs-booking-day">{{ b.day }}</div>
                  <div class="rs-booking-month">{{ b.month }}</div>
                </div>
                <div class="rs-booking-info">
                  <div class="rs-booking-title">{{ b.title }}</div>
                  <div class="rs-booking-time">{{ b.time }}</div>
                  <div class="rs-booking-user">{{ b.user }}</div>
                </div>
              </div>
            </div>

            <DkButton variant="primary" class="rs-detail-booken" @click="openBookingModal(selectedResource)">
              <IconCalendar class="dk-icon-sm" /> Jetzt buchen
            </DkButton>
          </div>
        </div>

        <!-- My Bookings Panel -->
        <div v-if="showMyBookings" class="rs-my-bookings">
          <div class="rs-detail-header">
            <h3 class="rs-panel-titel">Meine Buchungen</h3>
            <button class="rs-detail-close" aria-label="Meine Buchungen schliessen"
              title="Meine Buchungen schliessen" @click="showMyBookings = false">
              <IconX class="dk-icon-md" />
            </button>
          </div>

          <div v-if="myBookings.length === 0" class="dk-list-empty rs-panel-leer">
            <p class="rs-panel-leer-text">Du hast noch keine Buchungen.</p>
          </div>

          <div v-for="b in myBookings" :key="b.id" class="rs-my-booking">
            <div class="rs-my-booking-color" :class="`type-${b.resourceType}`"></div>
            <div class="rs-my-booking-body">
              <div class="rs-my-booking-title">{{ b.resourceName }}</div>
              <div class="rs-my-booking-date">{{ b.date }} · {{ b.time }}</div>
              <div class="rs-my-booking-purpose">{{ b.purpose }}</div>
              <span class="rs-status-badge" :class="statusClass(b.status)">{{ b.status }}</span>
              <div v-if="b.status === 'Abgelehnt' && b.ablehnungs_grund" class="rs-reject-reason">
                <IconInfo class="dk-icon-xs dk-schrumpf-nicht" />
                {{ b.ablehnungs_grund }}
              </div>
            </div>
            <div class="rs-my-booking-actions">
              <!-- OP-EVENT-14: „Verschieben“ — editBooking war nirgends
                   aufgerufen, eine Buchung liess sich nur stornieren und neu
                   anlegen (verlor dabei die Bestaetigung). -->
              <button v-if="b.status === 'Angefragt'" class="rs-my-btn" title="Verschieben" @click="editBooking(b)">
                <IconPencil class="dk-icon-sm" />
              </button>
              <button v-if="b.status === 'Angefragt' || b.status === 'Bestätigt'" class="rs-my-btn rs-my-btn--danger" title="Stornieren" @click="cancelBooking(b.id)">
                <IconTrash class="dk-icon-sm" />
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Booking Modal -->
    <DkModal v-model="bookingModalOpen" :before-close="buchungsSchutz.darfSchliessen" :title="editingBooking ? 'Buchung bearbeiten' : 'Ressource buchen'">
      <div class="rs-form">
        <DkField label="Ressource" required :error="bookingFehler['rs-ressource']">
          <select id="rs-ressource" :aria-invalid="!!bookingFehler['rs-ressource']" v-model="bookingForm.resourceId" class="rs-form-select" :disabled="editingBooking">
            <option v-for="r in resources" :key="r.id" :value="r.id">{{ r.name }}</option>
          </select>
        </DkField>

        <!-- DES-R14: Raster mit minmax(0,1fr); vorher ragte das Feld „bis“
             54 px aus dem 400-px-Dialog heraus. -->
        <div class="rs-form-row">
          <DkField label="Von (Datum)" required :error="bookingFehler['rs-von-datum']">
            <input id="rs-von-datum" :aria-invalid="!!bookingFehler['rs-von-datum']" v-model="bookingForm.date" type="date" class="rs-form-input" />
          </DkField>
          <DkField label="Von (Uhrzeit)" required :error="bookingFehler['rs-von-zeit']">
            <input id="rs-von-zeit" :aria-invalid="!!bookingFehler['rs-von-zeit']" v-model="bookingForm.startTime" type="time" class="rs-form-input" />
          </DkField>
        </div>
        <div class="rs-form-row">
          <DkField label="Bis (Datum)" required :error="bookingFehler['rs-bis-datum']">
            <input id="rs-bis-datum" :aria-invalid="!!bookingFehler['rs-bis-datum']" v-model="bookingForm.endDate" type="date" class="rs-form-input" />
          </DkField>
          <DkField label="Bis (Uhrzeit)" required :error="bookingFehler['rs-bis-zeit']">
            <input id="rs-bis-zeit" :aria-invalid="!!bookingFehler['rs-bis-zeit']" v-model="bookingForm.endTime" type="time" class="rs-form-input" />
          </DkField>
        </div>

        <DkField label="Zweck / Titel" required :error="bookingFehler['rs-zweck']">
          <input id="rs-zweck" :aria-invalid="!!bookingFehler['rs-zweck']" v-model="bookingForm.purpose" type="text" class="rs-form-input" placeholder="z. B. Jugendabend, Gottesdienst…" />
        </DkField>

        <DkField label="Notizen">
          <textarea v-model="bookingForm.notes" rows="2" class="rs-form-input" placeholder="Optionale Hinweise…" />
        </DkField>

        <!-- Availability Preview -->
        <div v-if="bookingForm.resourceId && bookingForm.date" class="rs-availability">
          <div class="rs-availability-title">
            <IconInfo class="dk-icon-sm" />
            Verfügbarkeit am {{ formatDateShort(bookingForm.date) }}
          </div>
          <div class="rs-availability-bar">
            <div
              v-for="slot in availabilitySlots"
              :key="slot.hour"
              class="rs-availability-slot"
              :class="{ 'is-booked': slot.booked, 'is-selected': slot.selected }"
              :title="slot.label"
            />
          </div>
          <div class="rs-availability-labels">
            <span>00:00</span>
            <span>06:00</span>
            <span>12:00</span>
            <span>18:00</span>
            <span>24:00</span>
          </div>
        </div>
      </div>

      <template #footer>
        <DkButton variant="secondary" @click="buchungSchliessen">Abbrechen</DkButton>
        <DkButton variant="primary" :disabled="submittingBooking" :loading="submittingBooking" @click="submitBooking">
          {{ editingBooking ? 'Speichern' : 'Buchen' }}
        </DkButton>
      </template>
    </DkModal>

    <!-- Ablehnungs-Modal -->
    <DkModal v-model="rejectModalOpen" title="Buchung ablehnen">
      <div class="rs-form-group">
        <label>Ablehnungsgrund <span class="rs-pflicht">*</span></label>
        <textarea
          v-model="rejectGrund"
          rows="3"
          placeholder="Grund für die Ablehnung eingeben…"
          class="rs-form-input rs-textarea"
        />
      </div>
      <template #footer>
        <DkButton variant="secondary" @click="rejectModalOpen = false">Abbrechen</DkButton>
        <DkButton variant="danger" :disabled="!rejectGrund.trim()" @click="submitReject">Ablehnen</DkButton>
      </template>
    </DkModal>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch, nextTick, h } from 'vue'
import { useSession } from '../composables/useSession.js'
import { apiCall } from '../composables/useApi.js'
import { suchNormal } from '../composables/bf1Anzeige.js'
import {
  entscheidungsArgumente,
  entscheidungsEndpunkt,
  istTerminAnfrage,
} from '../composables/ressourcenEntscheidung.js'
import { showToast } from '../composables/useToast.js'
import { bestaetigen } from '../composables/useBestaetigen.js'
import { useFormularSchutz } from '../composables/useFormularSchutz.js'
import { buchungsFehler, erstesFehlerfeld } from '../composables/formularPruefung.mjs'
import DkModal from '../components/DkModal.vue'
import DkPageHeader from '../components/ui/DkPageHeader.vue'
import DkButton from '../components/ui/DkButton.vue'
import DkField from '../components/ui/DkField.vue'
import DkEmpty from '../components/ui/DkEmpty.vue'
import DkFilterChips from '../components/ui/DkFilterChips.vue'
import { chipsMitZahlen, istAlle } from '../composables/filterChips.mjs'

const { isAdmin } = useSession()
const sidebarRef = ref(null)

// ============================================================
// STATE
// ============================================================
const resources = ref([])
const allBookings = ref([])
const myBookings = ref([])
const loading = ref(true)

const viewMode = ref('grid')
const searchQuery = ref('')
const typeFilter = ref('')
const selectedResource = ref(null)
const showMyBookings = ref(false)
const bookingModalOpen = ref(false)
const editingBooking = ref(null)
const submittingBooking = ref(false)
const searchDebounce = ref(null)
// OP-HANDY-12: Kalendertermine, die die gewaehlte Ressource im gewaehlten
// Zeitraum belegen (aus `check_verfuegbarkeit`). Die Verfuegbarkeitsleiste
// zeigte vorher nur Buchungen — Termine (Gottesdienst im Saal) fehlten.
const terminBelegung = ref([])

const bookingForm = ref({
  resourceId: '',
  date: '',
  startTime: '',
  endDate: '',
  endTime: '',
  purpose: '',
  notes: ''
})

const bookingFehler = ref({})
const buchungsSchutz = useFormularSchutz(() => bookingForm.value, () => submittingBooking.value)
async function buchungSchliessen() {
  if (await buchungsSchutz.darfSchliessen()) bookingModalOpen.value = false
}

// ── Moderation State ─────────────────────────────────────────
const isModerator = ref(false)
const anfragen = ref([])
const loadingAnfragen = ref(false)
const rejectModalOpen = ref(false)
const rejecting = ref(null)
const rejectGrund = ref('')

// ============================================================
// DATA LOADING
// ============================================================
async function loadResources() {
  loading.value = true
  try {
    resources.value = await apiCall('diakronos.diakonos.api.ressourcen.get_ressourcen_liste')
  } catch (err) {
    showToast('Ressourcen konnten nicht geladen werden', 'error')
  } finally {
    loading.value = false
  }
}

async function loadMyBookings() {
  try {
    myBookings.value = await apiCall('diakronos.diakonos.api.ressourcen.get_meine_buchungen')
  } catch (err) {
    console.error('Meine Buchungen:', err)
  }
}

async function loadResourceBookings(resourceId) {
  try {
    allBookings.value = await apiCall(
      'diakronos.diakonos.api.ressourcen.get_ressource_buchungen',
      { ressource_id: resourceId }
    )
  } catch (err) {
    console.error('Ressource-Buchungen:', err)
  }
}

onMounted(async () => {
  loadResources()
  loadMyBookings()
  await loadModeratorStatus()
})

// ── Moderation ───────────────────────────────────────────────────────────────
async function loadModeratorStatus() {
  try {
    const info = await apiCall('diakronos.kronos.api.permissions.get_session_info')
    const roles = info?.roles || []
    isModerator.value = roles.includes('Ressourcenmoderator')
      || roles.includes('Mitgliederadministrator')
      || roles.includes('System Manager')
  } catch {
    // Fallback: Admins sind immer Moderatoren
    isModerator.value = isAdmin.value
  }
  if (isModerator.value) {
    loadAnfragen()
  }
}

async function loadAnfragen() {
  loadingAnfragen.value = true
  try {
    const data = await apiCall('diakronos.diakonos.api.ressourcen.get_anfragen')
    anfragen.value = data?.anfragen || []
  } catch (err) {
    console.error('Anfragen laden:', err)
  } finally {
    loadingAnfragen.value = false
  }
}

// P1-4b/B1: Termin-Ressourcen entscheidet ein eigener Endpunkt. `decide_buchung`
// laedt `Ressourcen Buchung` — die gespiegelte Zeile ist aber eine
// `Element Ressource`-Kind-Zeile und waere dort nicht auffindbar (der Moderator
// sah Knöpfe, die nur einen Fehler erzeugten). Die Zuordnung Anfrage->Endpunkt
// steht in `ressourcenEntscheidung.js` (verhaltensgetestet).
async function entscheideAnfrage(a, entscheidung, grund = '') {
  return apiCall(entscheidungsEndpunkt(a), entscheidungsArgumente(a, entscheidung, grund))
}

async function approveBuchung(id) {
  const anfrage = anfragen.value.find(a => a.id === id) || { id }
  try {
    await entscheideAnfrage(anfrage, 'bestaetigen')
    showToast('Buchung bestätigt', 'success')
    anfragen.value = anfragen.value.filter(a => a.id !== id)
    await loadMyBookings()
  } catch (err) {
    showToast(err?.message || 'Fehler bei Bestätigung', 'error')
  }
}

async function approveTerminRessource(a) {
  try {
    await entscheideAnfrage(a, 'bestaetigen')
    showToast('Zuordnung bestätigt', 'success')
    anfragen.value = anfragen.value.filter(x => x.id !== a.id)
    await loadAnfragen()
  } catch (err) {
    showToast(err?.message || 'Fehler bei Bestätigung', 'error')
  }
}

function openRejectModal(a) {
  // P1-4b/B1: es wird der ganze Eintrag gemerkt (nicht nur die id), damit beim
  // Ablehnen die Quelle bekannt ist und der richtige Endpunkt aufgerufen wird.
  rejecting.value = a
  rejectGrund.value = ''
  rejectModalOpen.value = true
}

async function submitReject() {
  if (!rejectGrund.value.trim()) return
  const eintrag = rejecting.value || {}
  const istTermin = istTerminAnfrage(eintrag)
  try {
    await entscheideAnfrage(eintrag, 'ablehnen', rejectGrund.value)
    showToast(istTermin ? 'Zuordnung abgelehnt' : 'Buchung abgelehnt', 'info')
    rejectModalOpen.value = false
    anfragen.value = anfragen.value.filter(x => x.id !== eintrag.id)
    await loadMyBookings()
  } catch (err) {
    showToast(err?.message || 'Fehler bei Ablehnung', 'error')
  }
}

// Wenn Ressource oder Datum im Buchungsformular wechselt → Buchungen UND
// Kalendertermine für die Verfügbarkeitsanzeige nachladen (OP-HANDY-12).
watch(
  () => [bookingForm.value.resourceId, bookingForm.value.date],
  async ([id, datum]) => {
    if (!id || !datum) {
      terminBelegung.value = []
      return
    }
    if (id !== selectedResource.value?.id) {
      await loadResourceBookings(id)
    }
    await ladeBelegung(id, datum)
  }
)

// OP-HANDY-12: Tagesfenster gegen `check_verfuegbarkeit` prüfen und die
// Kalendertermine (das Feld `kalender_konflikte`) für die Leiste merken.
// Die Terminliste kommt vom Server bereits ohne fremde Titel („Belegt“).
async function ladeBelegung(resourceId, datum) {
  try {
    const res = await apiCall('diakronos.diakonos.api.ressourcen.check_verfuegbarkeit', {
      ressource_id: resourceId,
      datum_von: `${datum} 00:00:00`,
      datum_bis: `${datum} 23:59:59`,
    })
    terminBelegung.value = (res?.kalender_konflikte || []).map(k => ({
      von: k?.von || k?.datum_von || null,
      bis: k?.bis || k?.datum_bis || null,
    }))
  } catch (err) {
    terminBelegung.value = []
  }
}

// Überlappt ein Belegungs-Eintrag (Buchung oder Termin) mit [von, bis)?
function ueberlappt(eintrag, von, bis) {
  const a = new Date(String(eintrag?.datum_von ?? eintrag?.von ?? '').replace(' ', 'T'))
  const b = new Date(String(eintrag?.datum_bis ?? eintrag?.bis ?? '').replace(' ', 'T'))
  if (Number.isNaN(a.getTime()) || Number.isNaN(b.getTime())) return false
  return a < bis && b > von
}

// ============================================================
// COMPUTED
// ============================================================
const filteredResources = computed(() => {
  let list = resources.value
  // DES-01: „Alle“ kommt jetzt als Wert 'alle' an (Baustein-Ruhezustand) und
  // darf nicht als Art missverstanden werden.
  if (!istAlle(typeFilter.value)) {
    list = list.filter(r => r.type === typeFilter.value)
  }
  if (searchQuery.value.trim()) {
    // BF1-J/W8: umlaut- und gross-klein-unabhaengig.
    const q = suchNormal(searchQuery.value)
    list = list.filter(r =>
      suchNormal(r.name).includes(q) ||
      suchNormal(r.description).includes(q) ||
      (r.tags || []).some(t => suchNormal(t).includes(q))
    )
  }
  return list
})

const filteredCount = computed(() => filteredResources.value.length)

/**
 * OP-UI-19: Kopfzeile ohne Zahl vor dem Laden. Beim Filtern bleibt die
 * Trefferzahl stehen (sie beschreibt dann die Auswahl, nicht den Bestand).
 */
/** Ist ein Filter gesetzt? (entscheidet zwischen „nichts gefunden“ und „nichts da“) */
const filterAktiv = computed(() => !istAlle(typeFilter.value) || !!String(searchQuery.value || '').trim())

/** OP-UI-19: Weg zurück aus einem leeren Suchergebnis. */
function filterZuruecksetzen() {
  typeFilter.value = 'alle'
  searchQuery.value = ''
}

const kopfUntertitel = computed(() => {
  if (loading.value) return 'Räume & Gegenstände werden geladen …'
  if (!filterAktiv.value) {
    return `${filteredCount.value} ${filteredCount.value === 1 ? 'Eintrag' : 'Einträge'} verfügbar`
  }
  return `${filteredCount.value} von ${resources.value.length} Einträgen`
})

// DES-01: „Alle“ gehört dazu (S9: ein Filter ist abwählbar, „Alle“ ist der
// Ruhezustand). Die alten drei Knöpfe liessen sich nur über den Knopf selbst
// abwählen, was der Nutzer nicht sehen konnte.
const ARTEN = [
  { id: 'room', label: 'Räume' },
  { id: 'vehicle', label: 'Fahrzeuge' },
  { id: 'item', label: 'Gegenstände' },
]
const typChips = computed(() => chipsMitZahlen(
  ARTEN.map(a => ({ ...a, anzahl: resources.value.filter(r => r.type === a.id).length })),
))

const resourceBookings = computed(() => allBookings.value.slice(0, 5))

const availabilitySlots = computed(() => {
  const slots = []
  for (let i = 0; i < 24; i++) {
    const label = `${String(i).padStart(2, '0')}:00`
    const slotStart = bookingForm.value.date
      ? new Date(`${bookingForm.value.date}T${label}:00`)
      : null
    const slotEnd = slotStart ? new Date(slotStart.getTime() + 3600 * 1000) : null
    // OP-HANDY-12: Belegung aus Buchungen UND Kalenderterminen. Der Endpunkt
    // liefert seit P1-4 ISO-Zeitstempel (`datum_von`/`datum_bis`);
    // `terminBelegung` kommt aus `check_verfuegbarkeit` (Kalendertermine).
    const booked =
      (slotStart && allBookings.value.some(b => ueberlappt(b, slotStart, slotEnd))) ||
      (slotStart && terminBelegung.value.some(t => ueberlappt(t, slotStart, slotEnd)))
    slots.push({ hour: i, booked, selected: false, label })
  }
  return slots
})

// ============================================================
// METHODS
// ============================================================
function onSearchInput() {
  clearTimeout(searchDebounce.value)
  searchDebounce.value = setTimeout(() => loadResources(), 300)
}

async function selectResource(r) {
  selectedResource.value = selectedResource.value?.id === r.id ? null : r
  showMyBookings.value = false
  if (selectedResource.value) {
    await loadResourceBookings(r.id)
    scrollZuPanel()
  } else {
    allBookings.value = []
  }
}

// OP-HANDY-20: Am Handy standen „Meine Buchungen“ und das Detail 1.500 px
// tiefer (Panel liegt nach dem Kartenraster), ohne dass etwas scrollte —
// der Knopf wechselte nur die Farbe. Jetzt springt die Ansicht weich hin.
async function scrollZuPanel() {
  await nextTick()
  sidebarRef.value?.scrollIntoView?.({ behavior: 'smooth', block: 'start' })
}

async function toggleMyBookings() {
  showMyBookings.value = !showMyBookings.value
  if (showMyBookings.value) {
    selectedResource.value = null
    scrollZuPanel()
  }
}

function konfliktHinweise(a) {
  // UXK-R8: Der Server liefert eine Liste (auch leer). Ein blosses
  // `v-if="a.konflikt_hinweis"` ist bei [] bereits wahr -> jedes Banner „[]“.
  const liste = a?.konflikt_hinweis
  return Array.isArray(liste) ? liste : []
}

function konfliktText(k) {
  // UXK-R8: Eintraege sind Objekte — „[object Object]“ in der Oberflaeche.
  if (typeof k === 'string') return k
  const titel = k?.titel || k?.name || k?.zweck || 'Belegung'
  const zeitraum = k?.zeitraum ? ` (${k.zeitraum})` : ''
  return `Überschneidung mit „${titel}“${zeitraum}`
}

function konfliktSatz(liste) {
  return liste.map(konfliktText).join('; ')
}

function typeLabel(type) {
  const map = { room: 'Raum', vehicle: 'Fahrzeug', item: 'Gegenstand' }
  return map[type] || type
}

function statusLabel(status) {
  const map = { available: 'Verfügbar', booked: 'Belegt', maintenance: 'Wartung' }
  return map[status] || status
}

function statusClass(status) {
  const map = {
    'Angefragt': 'rs-status-badge--pending',
    'Bestätigt': 'rs-status-badge--confirmed',
    'Abgelehnt': 'rs-status-badge--rejected',
    'Storniert': 'rs-status-badge--cancelled',
  }
  return map[status] || ''
}

function heuteLokal() {
  // OP-UI-21: `toISOString()` liefert das UTC-Datum. Zwischen 0 und 2 Uhr
  // (Winter 0–1 Uhr) schlug der Dialog damit das Datum von GESTERN vor.
  // `sv-SE` formatiert als YYYY-MM-DD in der lokalen Zeitzone.
  return new Date().toLocaleDateString('sv-SE')
}

function openBookingModal(resource = null) {
  editingBooking.value = null
  bookingForm.value = {
    resourceId: resource?.id || '',
    date: heuteLokal(),
    startTime: '09:00',
    endDate: heuteLokal(),
    endTime: '11:00',
    purpose: '',
    notes: ''
  }
  bookingFehler.value = {}
  buchungsSchutz.merken()
  bookingModalOpen.value = true
}

function editBooking(booking) {
  editingBooking.value = booking
  const [start, ende] = (booking.time || '08:00 – 18:00').split(' – ')
  bookingForm.value = {
    resourceId: booking.resourceId,
    date: booking.date || heuteLokal(),
    startTime: start || '08:00',
    // OP-EVENT-14: Von/bis mit Datum+Zeit — eine Buchung darf ueber mehrere
    // Tage gehen (Gemeindebus 26.–30.07.).
    endDate: booking.endDate || booking.date || heuteLokal(),
    endTime: ende || '18:00',
    purpose: booking.purpose || '',
    notes: ''
  }
  bookingFehler.value = {}
  buchungsSchutz.merken()
  bookingModalOpen.value = true
}

async function submitBooking() {
  if (submittingBooking.value) return
  bookingFehler.value = buchungsFehler(bookingForm.value)
  if (Object.keys(bookingFehler.value).length) {
    erstesFehlerfeld(bookingFehler.value)
    return
  }
  submittingBooking.value = true
  const f = bookingForm.value
  const datum_von = `${f.date} ${f.startTime}:00`
  const datum_bis = `${f.endDate} ${f.endTime}:00`
  try {
    if (editingBooking.value) {
      // OP-EVENT-14: Verschieben — Zeitraum wird mitgeschickt; der Server
      // prüft den neuen Zeitraum auf harte Konflikte.
      await apiCall('diakronos.diakonos.api.ressourcen.update_buchung', {
        buchung_id: editingBooking.value.id,
        datum_von, datum_bis,
        zweck: f.purpose,
        notizen: f.notes,
      })
      showToast('Buchung aktualisiert')
    } else {
      const res = await apiCall('diakronos.diakonos.api.ressourcen.create_buchung', {
        ressource_id: f.resourceId,
        datum_von, datum_bis,
        zweck: f.purpose,
        notizen: f.notes,
      })
      showToast('Anfrage gestellt, wartet auf Bestätigung')
      if (res?.konflikt_hinweis?.length) {
        showToast(konfliktSatz(res.konflikt_hinweis), 'warning')
      }
    }
    bookingModalOpen.value = false
    await loadResources()
    await loadMyBookings()
    if (selectedResource.value) await loadResourceBookings(selectedResource.value.id)
  } catch (err) {
    showToast(err?.message || 'Fehler beim Speichern', 'error')
  } finally {
    submittingBooking.value = false
  }
}

async function cancelBooking(id) {
  if (!await bestaetigen({ titel: 'Buchung stornieren?', text: 'Eine Buchung wird storniert und die Ressource wieder freigegeben.', aktion: 'Stornieren', gefahr: true })) return
  try {
    await apiCall('diakronos.diakonos.api.ressourcen.delete_buchung', { buchung_id: id })
    showToast('Buchung storniert')
    myBookings.value = myBookings.value.filter(b => b.id !== id)
    await loadResources()
  } catch (err) {
    showToast(err?.message || 'Fehler', 'error')
  }
}

function formatDateShort(d) {
  if (!d) return ''
  const [y, m, day] = d.split('-')
  return `${day}.${m}.${y}`
}

// ============================================================
// ICONS
// ============================================================
const Icon = {
  props: ['icon'],
  setup(props) {
    const paths = {
      building: 'M3 21h18M5 21V7l8-4 8 4v14M8 21v-9a2 2 0 0 1 4 0v9',
      truck: 'M10 17h4V5H2v12h3m15 0h2a2 2 0 0 0 2-2v-4h-6v6zm-10 0h4M7 17h2m8 0h2',
      box: 'M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z M3.27 6.96L12 12.01l8.73-5.05 M12 22.08V12',
    }
    return () => h('svg', {
      width: 24, height: 24, viewBox: '0 0 24 24',
      fill: 'none', stroke: 'currentColor', 'stroke-width': 1.5,
      'stroke-linecap': 'round', 'stroke-linejoin': 'round'
    }, [h('path', { d: paths[props.icon] || '' })])
  }
}

const IconPlus         = () => h('svg', { width:14, height:14, viewBox:'0 0 24 24', fill:'none', stroke:'currentColor', 'stroke-width':2, 'stroke-linecap':'round', 'stroke-linejoin':'round' }, [h('line',{x1:12,y1:5,x2:12,y2:19}), h('line',{x1:5,y1:12,x2:19,y2:12})])
const IconCalendar     = () => h('svg', { width:14, height:14, viewBox:'0 0 24 24', fill:'none', stroke:'currentColor', 'stroke-width':2, 'stroke-linecap':'round', 'stroke-linejoin':'round' }, [h('rect',{x:3,y:4,width:18,height:18,rx:2}), h('line',{x1:16,y1:2,x2:16,y2:6}), h('line',{x1:8,y1:2,x2:8,y2:6}), h('line',{x1:3,y1:10,x2:21,y2:10})])
const IconCalendarCheck= () => h('svg', { width:14, height:14, viewBox:'0 0 24 24', fill:'none', stroke:'currentColor', 'stroke-width':2, 'stroke-linecap':'round', 'stroke-linejoin':'round' }, [h('rect',{x:3,y:4,width:18,height:18,rx:2}), h('line',{x1:16,y1:2,x2:16,y2:6}), h('line',{x1:8,y1:2,x2:8,y2:6}), h('line',{x1:3,y1:10,x2:21,y2:10}), h('polyline',{points:'9 15 12 17 16 11'})])
const IconUsers        = () => h('svg', { width:14, height:14, viewBox:'0 0 24 24', fill:'none', stroke:'currentColor', 'stroke-width':2, 'stroke-linecap':'round', 'stroke-linejoin':'round' }, [h('path',{d:'M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2'}), h('circle',{cx:9,cy:7,r:4}), h('path',{d:'M23 21v-2a4 4 0 0 0-3-3.87'}), h('path',{d:'M16 3.13a4 4 0 0 1 0 7.75'})])
const IconLayoutGrid   = () => h('svg', { width:14, height:14, viewBox:'0 0 24 24', fill:'none', stroke:'currentColor', 'stroke-width':2, 'stroke-linecap':'round', 'stroke-linejoin':'round' }, [h('rect',{x:3,y:3,width:7,height:7}), h('rect',{x:14,y:3,width:7,height:7}), h('rect',{x:14,y:14,width:7,height:7}), h('rect',{x:3,y:14,width:7,height:7})])
const IconList         = () => h('svg', { width:14, height:14, viewBox:'0 0 24 24', fill:'none', stroke:'currentColor', 'stroke-width':2, 'stroke-linecap':'round', 'stroke-linejoin':'round' }, [h('line',{x1:8,y1:6,x2:21,y2:6}), h('line',{x1:8,y1:12,x2:21,y2:12}), h('line',{x1:8,y1:18,x2:21,y2:18}), h('line',{x1:3,y1:6,x2:3.01,y2:6}), h('line',{x1:3,y1:12,x2:3.01,y2:12}), h('line',{x1:3,y1:18,x2:3.01,y2:18})])
const IconX            = () => h('svg', { width:14, height:14, viewBox:'0 0 24 24', fill:'none', stroke:'currentColor', 'stroke-width':2, 'stroke-linecap':'round', 'stroke-linejoin':'round' }, [h('line',{x1:18,y1:6,x2:6,y2:18}), h('line',{x1:6,y1:6,x2:18,y2:18})])
const IconPencil       = () => h('svg', { width:14, height:14, viewBox:'0 0 24 24', fill:'none', stroke:'currentColor', 'stroke-width':2, 'stroke-linecap':'round', 'stroke-linejoin':'round' }, [h('path',{d:'M17 3a2.828 2.828 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z'})])
const IconTrash        = () => h('svg', { width:14, height:14, viewBox:'0 0 24 24', fill:'none', stroke:'currentColor', 'stroke-width':2, 'stroke-linecap':'round', 'stroke-linejoin':'round' }, [h('polyline',{points:'3 6 5 6 21 6'}), h('path',{d:'M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2'}), h('line',{x1:10,y1:11,x2:10,y2:17}), h('line',{x1:14,y1:11,x2:14,y2:17})])
const IconInfo         = () => h('svg', { width:14, height:14, viewBox:'0 0 24 24', fill:'none', stroke:'currentColor', 'stroke-width':2, 'stroke-linecap':'round', 'stroke-linejoin':'round' }, [h('circle',{cx:12,cy:12,r:10}), h('line',{x1:12,y1:16,x2:12,y2:12}), h('line',{x1:12,y1:8,x2:12.01,y2:8})])
const IconClipboard    = () => h('svg', { width:14, height:14, viewBox:'0 0 24 24', fill:'none', stroke:'currentColor', 'stroke-width':2, 'stroke-linecap':'round', 'stroke-linejoin':'round' }, [h('path',{d:'M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2'}), h('rect',{x:8,y:2,width:8,height:4,rx:1})])
const IconCheck        = () => h('svg', { width:14, height:14, viewBox:'0 0 24 24', fill:'none', stroke:'currentColor', 'stroke-width':2, 'stroke-linecap':'round', 'stroke-linejoin':'round' }, [h('polyline',{points:'20 6 9 17 4 12'})])
const IconRefresh      = () => h('svg', { width:14, height:14, viewBox:'0 0 24 24', fill:'none', stroke:'currentColor', 'stroke-width':2, 'stroke-linecap':'round', 'stroke-linejoin':'round' }, [h('polyline',{points:'23 4 23 10 17 10'}), h('path',{d:'M20.49 15a9 9 0 1 1-2.12-9.36L23 10'})])
</script>

<style scoped>
/* ================================================================
   LAYOUT
   ================================================================ */
.rs-layout.has-sidebar {
  grid-template-columns: 1fr 360px;
}

.rs-main {
  min-width: 0;
}

/* DES-02: die frühere Inline-Angabe `flex:1` als Klasse — die Lücke schiebt den
   Ansichtsumschalter an das rechte Ende der Werkzeugleiste. */
.rs-toolbar-luecke { flex: 1; }

/* DES-02: Spaltenbreiten der Listenansicht (vorher je Zelle als style-Attribut
   gesetzt — vier Stellen im Kopf, drei in jeder Zeile). */
.rs-spalte { flex-shrink: 0; }
.rs-spalte--name { flex: 1; min-width: 0; }
.rs-spalte--typ { width: 90px; }
.rs-spalte--status { width: 80px; }
.rs-spalte--aktionen { width: 100px; }

.rs-panel-titel { margin: 0; font-size: var(--fs-h3); }
.rs-panel-leer { padding: var(--sp-8) var(--sp-4); }
.rs-panel-leer-text { margin: 0; font-size: var(--fs); color: var(--muted); }
.rs-pflicht { color: var(--err); }
.rs-textarea { resize: vertical; }

.rs-sidebar {
  background: var(--dk-surface);
  border: 1px solid var(--dk-border);
  border-radius: 12px;
  overflow: hidden;
  box-shadow: var(--dk-shadow-xs);
  max-height: calc(100vh - 220px);
  overflow-y: auto;
}

/* ================================================================
   GRID VIEW
   ================================================================ */
.rs-card {
  background: var(--dk-surface);
  border: 1px solid var(--dk-border);
  border-radius: 12px;
  overflow: hidden;
  /* P3-4b/W3: Bezugsrahmen für die gedehnte Titel-Linkfläche. */
  position: relative;
  cursor: pointer;
  transition: all var(--dk-med);
  box-shadow: var(--dk-shadow-xs);
}
.rs-card:hover {
  border-color: var(--dk-border-strong);
  box-shadow: var(--dk-shadow-sm);
  transform: translateY(-2px);
}
.rs-card.is-selected {
  border-color: var(--dk-accent);
  box-shadow: 0 0 0 3px color-mix(in oklch, var(--accent) 15%, transparent);
}

.rs-card-image {
  height: 120px;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  background: var(--dk-surface-2);
}
.rs-card-image.type-room    { background: linear-gradient(135deg, color-mix(in oklch, var(--dk-brand-500) 10%, var(--dk-surface-2)) 0%, color-mix(in oklch, var(--dk-brand-500) 20%, var(--dk-surface-2)) 100%); }
.rs-card-image.type-vehicle { background: linear-gradient(135deg, color-mix(in oklch, var(--dk-res-vehicle) 10%, var(--dk-surface-2)) 0%, color-mix(in oklch, var(--dk-res-vehicle) 20%, var(--dk-surface-2)) 100%); }
.rs-card-image.type-item    { background: linear-gradient(135deg, color-mix(in oklch, var(--dk-res-item) 10%, var(--dk-surface-2)) 0%, color-mix(in oklch, var(--dk-res-item) 20%, var(--dk-surface-2)) 100%); }

.rs-card-icon {
  color: var(--dk-brand-400);
  opacity: 0.5;
}
.rs-card-image.type-room .rs-card-icon { color: var(--dk-brand-500); }
.rs-card-image.type-vehicle .rs-card-icon { color: var(--dk-res-vehicle); }
.rs-card-image.type-item .rs-card-icon    { color: var(--dk-res-item); }

.rs-card-badge {
  position: absolute;
  top: 10px;
  right: 10px;
  font-size: 10px;
  font-weight: 600;
  padding: 3px 8px;
  border-radius: 999px;
  text-transform: uppercase;
  letter-spacing: 0.03em;
}
.rs-card-badge.available   { background: color-mix(in oklch, var(--dk-success) 12%, var(--dk-surface)); color: var(--dk-success); }
.rs-card-badge.booked      { background: color-mix(in oklch, var(--dk-danger)  10%, var(--dk-surface)); color: var(--dk-danger); }
.rs-card-badge.maintenance { background: color-mix(in oklch, var(--dk-warning) 12%, var(--dk-surface)); color: var(--dk-warning); }

.rs-card-body {
  padding: 14px 16px 16px;
}
.rs-card-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--dk-text);
  margin-bottom: 4px;
}
/* P3-4 (Restpunkt 2): Der Titel ist der Knopf, der die Kachel auswählt — er
   muss wie Text aussehen, nicht wie ein Knopf. */
.rs-card-title--knopf {
  display: block;
  width: 100%;
  padding: 0;
  border: 0;
  background: none;
  font: inherit;
  text-align: left;
  cursor: pointer;
}
.rs-card-title--knopf:hover { color: var(--dk-brand-800); text-decoration: underline; }
/* P3-4b/W3: Die ganze Kachel wählt aus — der Titelknopf wird über die Kachel
   gedehnt. Der ::after braucht die Kachel als Bezugsrahmen; „Buchen“ und die
   Kartenmarke liegen darüber und bleiben einzeln treffbar. */
.rs-card-title--knopf::after {
  content: "";
  position: absolute;
  inset: 0;
  z-index: 0;
}
/* R-P3-4b W2: das Abzeichen bleibt absolut positioniert, nur ueber die Kartenflaeche. */
.rs-card-badge { z-index: 1; }
.rs-btn-book,
.rs-card .dk-btn { position: relative; z-index: 1; }
.rs-card:has(.rs-card-title--knopf:focus-visible) {
  outline: 2px solid var(--dk-accent);
  outline-offset: 2px;
}
.rs-card-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 12px;
  color: var(--dk-text-muted);
  margin-bottom: 8px;
}
.rs-card-type {
  font-weight: 500;
}
.rs-card-capacity {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.rs-card-desc {
  font-size: 12px;
  color: var(--dk-text-muted);
  line-height: 1.45;
  margin-bottom: 10px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.rs-card-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-bottom: 12px;
}
.rs-tag {
  font-size: 10px;
  font-weight: 500;
  padding: 2px 8px;
  border-radius: 4px;
  background: var(--dk-surface-2);
  color: var(--dk-text-muted);
}
.rs-card-footer {
  padding-top: 10px;
  border-top: 1px solid var(--dk-divider);
}
.rs-btn-book {
  font-weight: 600;
}

/* ================================================================
   LIST VIEW
   ================================================================ */
.rs-list-row:last-child { border-bottom: none; }
.rs-list-row:hover { background: var(--dk-surface-hover); }
.rs-list-row.is-selected { background: color-mix(in oklch, var(--accent) 6%, var(--surface)); }

.rs-list-name {
  display: flex;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid var(--dk-divider);
  cursor: pointer;
  transition: background var(--dk-fast);
}
.rs-list-row:last-child { border-bottom: none; }
.rs-list-row:hover { background: var(--dk-surface-hover); }
.rs-list-row.is-selected { background: color-mix(in oklch, var(--accent) 6%, var(--surface)); }

.rs-list-name {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}
.rs-list-icon {
  width: 40px;
  height: 40px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  background: var(--dk-surface-2);
  color: var(--dk-brand-500);
}
.rs-list-icon.type-vehicle { color: var(--dk-res-vehicle); background: color-mix(in oklch, var(--dk-res-vehicle) 12%, var(--dk-surface-2)); }
.rs-list-icon.type-item    { color: var(--dk-res-item);    background: color-mix(in oklch, var(--dk-res-item)    12%, var(--dk-surface-2)); }
.rs-list-title {
  font-size: 14px;
  font-weight: 500;
  color: var(--dk-text);
}
.rs-list-sub {
  font-size: 12px;
  color: var(--dk-text-muted);
  margin-top: 1px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.rs-type-badge {
  display: inline-block;
  font-size: 11px;
  font-weight: 500;
  padding: 2px 8px;
  border-radius: 4px;
  background: var(--dk-surface-2);
  color: var(--dk-text-muted);
}
.rs-type-badge.room    { background: color-mix(in oklch, var(--dk-brand-500) 10%, var(--dk-surface-2)); color: var(--dk-brand-500); }
.rs-type-badge.vehicle { background: color-mix(in oklch, var(--dk-res-vehicle) 12%, var(--dk-surface-2)); color: var(--dk-res-vehicle); }
.rs-type-badge.item    { background: color-mix(in oklch, var(--dk-res-item)    12%, var(--dk-surface-2)); color: var(--dk-res-item); }

.rs-status-dot {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 12px;
  font-weight: 500;
}
.rs-status-dot::before {
  content: '';
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--dk-text-subtle);
}
.rs-status-dot.available::before { background: var(--dk-success); }
.rs-status-dot.booked::before { background: var(--dk-danger); }
.rs-status-dot.maintenance::before { background: var(--dk-warning); }

.rs-btn-book-sm {
  font-weight: 600;
}

/* ================================================================
   DETAIL PANEL
   ================================================================ */
.rs-detail-header {
  display: flex;
  justify-content: flex-end;
  padding: 10px 14px;
  border-bottom: 1px solid var(--dk-divider);
}
.rs-detail-close {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 6px;
  border: none;
  background: transparent;
  color: var(--dk-text-muted);
  cursor: pointer;
  transition: all var(--dk-fast);
}
.rs-detail-close:hover {
  background: var(--dk-surface-hover);
  color: var(--dk-text);
}

.rs-detail-image {
  height: 140px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.rs-detail-image.type-room    { background: linear-gradient(135deg, color-mix(in oklch, var(--dk-brand-500) 10%, var(--dk-surface-2)) 0%, color-mix(in oklch, var(--dk-brand-500) 20%, var(--dk-surface-2)) 100%); }
.rs-detail-image.type-vehicle { background: linear-gradient(135deg, color-mix(in oklch, var(--dk-res-vehicle) 10%, var(--dk-surface-2)) 0%, color-mix(in oklch, var(--dk-res-vehicle) 20%, var(--dk-surface-2)) 100%); }
.rs-detail-image.type-item    { background: linear-gradient(135deg, color-mix(in oklch, var(--dk-res-item) 10%, var(--dk-surface-2)) 0%, color-mix(in oklch, var(--dk-res-item) 20%, var(--dk-surface-2)) 100%); }
.rs-detail-icon {
  color: var(--dk-brand-400);
  opacity: 0.6;
}

.rs-detail-body {
  padding: 16px;
}
.rs-detail-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--dk-text);
  margin: 0 0 6px;
}
.rs-detail-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 10px;
}
.rs-detail-capacity {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--dk-text-muted);
}
.rs-detail-desc {
  font-size: 13px;
  color: var(--dk-text-muted);
  line-height: 1.5;
  margin: 0 0 16px;
}

.rs-detail-section {
  margin-bottom: 16px;
}
.rs-detail-section h4 {
  font-size: 11px;
  font-weight: 600;
  color: var(--dk-text-subtle);
  text-transform: uppercase;
  letter-spacing: 0.06em;
  margin: 0 0 8px;
}
.rs-detail-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
}

.rs-booking-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 0;
  border-bottom: 1px solid var(--dk-divider);
}
.rs-booking-item:last-child { border-bottom: none; }
.rs-booking-date {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  border-radius: 8px;
  background: var(--dk-surface-2);
  flex-shrink: 0;
}
.rs-booking-day {
  font-size: 14px;
  font-weight: 700;
  line-height: 1;
  color: var(--dk-text);
}
.rs-booking-month {
  font-size: 9px;
  font-weight: 600;
  text-transform: uppercase;
  color: var(--dk-text-muted);
  margin-top: 2px;
}
.rs-booking-info {
  flex: 1;
  min-width: 0;
}
.rs-booking-title {
  font-size: 12px;
  font-weight: 500;
  color: var(--dk-text);
}
.rs-booking-time {
  font-size: 11px;
  color: var(--dk-text-muted);
  margin-top: 1px;
}
.rs-booking-user {
  font-size: 11px;
  color: var(--dk-text-subtle);
  margin-top: 1px;
}
.rs-empty {
  font-size: 12px;
  color: var(--dk-text-muted);
  padding: 8px 0;
}

/* ================================================================
   MY BOOKINGS PANEL
   ================================================================ */
.rs-my-bookings { padding-bottom: 8px; }
.rs-my-booking {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  border-bottom: 1px solid var(--dk-divider);
  transition: background var(--dk-fast);
}
.rs-my-booking:hover { background: var(--dk-surface-hover); }
.rs-my-booking-color {
  width: 3px;
  height: 36px;
  border-radius: 2px;
  flex-shrink: 0;
  background: var(--dk-brand-400);
}
.rs-my-booking-color.type-room { background: var(--dk-brand-400); }
.rs-my-booking-color.type-vehicle { background: var(--dk-res-vehicle); }
.rs-my-booking-color.type-item    { background: var(--dk-res-item); }
.rs-my-booking-body { flex: 1; min-width: 0; }
.rs-my-booking-title {
  font-size: 13px;
  font-weight: 500;
  color: var(--dk-text);
}
.rs-my-booking-date {
  font-size: 11px;
  color: var(--dk-text-muted);
  margin-top: 2px;
}
.rs-my-booking-purpose {
  font-size: 11px;
  color: var(--dk-text-subtle);
  margin-top: 1px;
}
.rs-my-booking-actions {
  display: flex;
  gap: 2px;
  opacity: 0;
  transition: opacity var(--dk-fast);
}
.rs-my-booking:hover .rs-my-booking-actions { opacity: 1; }
.rs-my-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 6px;
  border: none;
  background: transparent;
  color: var(--dk-text-muted);
  cursor: pointer;
  transition: all var(--dk-fast);
}
.rs-my-btn:hover { background: var(--dk-surface-2); color: var(--dk-brand-500); }
.rs-my-btn--danger:hover { background: color-mix(in oklch, var(--err) 10%, transparent); color: var(--err); }

.rs-form { display: flex; flex-direction: column; gap: var(--sp-3); }
.rs-form-bis { color: var(--muted); }
.rs-leer { padding: var(--sp-8) var(--sp-6); }
.rs-detail-booken { width: 100%; margin-top: var(--sp-4); }

/* ================================================================
   BOOKING MODAL FORM
   ================================================================ */
.rs-form-group {
  margin-bottom: 14px;
}
.rs-form-group label {
  display: block;
  font-size: 12px;
  font-weight: 500;
  color: var(--dk-text-muted);
  margin-bottom: 5px;
}
.rs-form-input, .rs-form-select {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid var(--dk-border);
  border-radius: 8px;
  background: var(--dk-surface);
  color: var(--dk-text);
  font-size: 13px;
  transition: border-color var(--dk-fast);
  font-family: inherit;
}
.rs-form-input:focus, .rs-form-select:focus {
  outline: none;
  border-color: var(--dk-accent);
}
.rs-form-input::placeholder {
  color: var(--dk-text-subtle);
}

.rs-form-row {
  display: grid;
  /* DES-R14: minmax(0,1fr) statt 1fr — ohne die 0-Untergrenze konnte ein
     breites Zeitfeld („11:00“) aus dem 400-px-Dialog herausragen. */
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 12px;
}
.rs-form-row > * { min-width: 0; }
.rs-form-time {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}
.rs-form-time input {
  flex: 1;
  min-width: 0;
}

/* Availability Bar */
.rs-availability {
  background: var(--dk-surface-2);
  border-radius: 8px;
  padding: 12px;
  margin-bottom: 16px;
}
.rs-availability-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 500;
  color: var(--dk-text-muted);
  margin-bottom: 8px;
}
.rs-availability-bar {
  display: flex;
  gap: 1px;
  height: 24px;
  border-radius: 4px;
  overflow: hidden;
}
.rs-availability-slot {
  flex: 1;
  background: var(--dk-success);
  opacity: 0.3;
  transition: opacity var(--dk-fast);
}
.rs-availability-slot.is-booked {
  background: var(--dk-danger);
  opacity: 0.6;
}
.rs-availability-slot.is-selected {
  background: var(--dk-accent);
  opacity: 0.8;
}
.rs-availability-labels {
  display: flex;
  justify-content: space-between;
  margin-top: 4px;
  font-size: 9px;
  color: var(--dk-text-subtle);
}

/* ================================================================
   STATUS BADGES (Moderation)
   ================================================================ */
.rs-status-badge {
  display: inline-block;
  font-size: 10px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 999px;
  text-transform: uppercase;
  letter-spacing: 0.03em;
  margin-top: 4px;
}
.rs-status-badge--pending  { background: color-mix(in oklch, var(--dk-warning) 15%, var(--dk-surface)); color: var(--dk-warning); }
.rs-status-badge--confirmed { background: color-mix(in oklch, var(--dk-success) 12%, var(--dk-surface)); color: var(--dk-success); }
.rs-status-badge--rejected { background: color-mix(in oklch, var(--dk-danger) 12%, var(--dk-surface)); color: var(--dk-danger); }
.rs-status-badge--cancelled { background: var(--dk-surface-2); color: var(--dk-text-muted); }

.rs-reject-reason {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  margin-top: 6px;
  padding: 6px 8px;
  border-radius: 6px;
  font-size: 11px;
  color: var(--dk-danger);
  background: color-mix(in oklch, var(--dk-danger) 6%, var(--dk-surface));
  line-height: 1.4;
}

/* ================================================================
   MODERATION SECTION
   ================================================================ */
.rs-moderation-section {
  margin-top: 24px;
  padding-top: 24px;
  border-top: 2px solid var(--dk-border);
}
.rs-moderation-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}
.rs-moderation-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  font-weight: 600;
  color: var(--dk-text);
  margin: 0;
}
.rs-moderation-count {
  font-size: 11px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 999px;
  background: var(--dk-accent);
  color: var(--dk-brand-800);
}
.rs-moderation-empty {
  font-size: 13px;
  color: var(--dk-text-muted);
  padding: 20px 0;
  text-align: center;
}

.rs-anfrage-card {
  background: var(--dk-surface);
  border: 1px solid var(--dk-border);
  border-radius: 10px;
  overflow: hidden;
  margin-bottom: 10px;
  transition: border-color var(--dk-fast);
}
.rs-anfrage-card:hover {
  border-color: var(--dk-border-strong);
}

.rs-anfrage-konflikt {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  padding: 8px 14px;
  font-size: 11px;
  font-weight: 500;
  color: var(--dk-warning);
  background: color-mix(in oklch, var(--dk-warning) 8%, var(--dk-surface));
  border-bottom: 1px solid color-mix(in oklch, var(--dk-warning) 15%, var(--dk-border));
  line-height: 1.4;
}
.rs-konflikt-zeile + .rs-konflikt-zeile { margin-top: 2px; }

.rs-anfrage-body {
  padding: 12px 14px;
}
.rs-anfrage-ressource {
  font-size: 13px;
  font-weight: 600;
  color: var(--dk-text);
  margin-bottom: 2px;
}
/* P1-4b/B1: Herkunft der Anfrage (Buchung vs. Zuordnung am Termin). */
.rs-anfrage-quelle {
  margin-left: 6px;
  padding: 1px 6px;
  font-size: 10px;
  font-weight: 500;
  text-transform: none;
  color: var(--dk-text-muted);
  background: var(--dk-surface-2);
  border: 1px solid var(--dk-divider);
  border-radius: 999px;
  vertical-align: middle;
}
.rs-anfrage-zweck {
  font-size: 13px;
  color: var(--dk-text);
  margin-bottom: 6px;
}
.rs-anfrage-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  font-size: 11px;
  color: var(--dk-text-muted);
}
.rs-anfrage-notiz {
  margin-top: 8px;
  padding: 6px 8px;
  font-size: 11px;
  color: var(--dk-text-muted);
  background: var(--dk-surface-2);
  border-radius: 6px;
  line-height: 1.4;
}

.rs-anfrage-actions {
  display: flex;
  gap: 8px;
  padding: 10px 14px;
  border-top: 1px solid var(--dk-divider);
  background: var(--dk-surface-2);
}

.dk-btn-danger {
  background: var(--dk-danger);
  color: var(--primary-ink);
  border-color: var(--dk-danger);
}
.dk-btn-danger:hover {
  background: color-mix(in oklch, var(--err) 85%, black);
}
.dk-btn-danger:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.spin {
  animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* Responsive */
@media (max-width: 1100px) {
  .rs-layout.has-sidebar {
    grid-template-columns: 1fr;
  }
  .rs-sidebar {
    max-height: none;
  }
}
@media (max-width: 640px) {
  .rs-form-row {
    grid-template-columns: 1fr;
  }
  .rs-my-booking-actions { opacity: 1; }
  .rs-anfrage-actions { flex-direction: column; }
}
</style>