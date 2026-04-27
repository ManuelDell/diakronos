<template>
  <div class="dk-screen dk-screen-wide dk-screen-enter">

    <!-- Header -->
    <div class="dk-screen-header">
      <div>
        <h1 class="dk-screen-title">Ressourcen</h1>
        <p class="dk-screen-sub">{{ filteredCount }} Räume & Gegenstände verfügbar</p>
      </div>
      <div class="dk-screen-actions">
        <button class="dk-btn dk-btn-secondary" :class="{ 'is-active': showMyBookings }" @click="showMyBookings = !showMyBookings">
          <IconCalendarCheck style="width:14px;height:14px" />
          Meine Buchungen
        </button>
        <button v-if="isAdmin" class="dk-btn dk-btn-primary" @click="openBookingModal()">
          <IconPlus style="width:14px;height:14px" />
          Buchung anlegen
        </button>
      </div>
    </div>

    <!-- Toolbar -->
    <div class="dk-toolbar">
      <div class="dk-toolbar-search">
        <svg class="dk-search-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
        <input v-model="searchQuery" type="text" placeholder="Ressource suchen…" @input="onSearchInput" />
      </div>

      <button
        v-for="f in typeFilters"
        :key="f.id"
        class="dk-filter-chip"
        :class="{ 'is-active': typeFilter === f.id }"
        @click="typeFilter = f.id === typeFilter ? '' : f.id"
      >
        {{ f.label }}
        <span class="dk-chip-count">{{ f.count }}</span>
      </button>

      <span style="flex:1" />

      <button class="dk-filter-chip" :class="{ 'is-active': viewMode === 'grid' }" @click="viewMode = 'grid'" title="Kachelansicht">
        <IconLayoutGrid style="width:14px;height:14px" />
      </button>
      <button class="dk-filter-chip" :class="{ 'is-active': viewMode === 'list' }" @click="viewMode = 'list'" title="Listenansicht">
        <IconList style="width:14px;height:14px" />
      </button>
    </div>

    <!-- Main Content Grid -->
    <div class="rs-layout" :class="{ 'has-sidebar': showMyBookings || selectedResource }">

      <!-- Ressourcen-Grid / List -->
      <div class="rs-main">

        <!-- Grid View -->
        <div v-if="viewMode === 'grid'" class="rs-grid">
          <div
            v-for="r in filteredResources"
            :key="r.id"
            class="rs-card"
            :class="{ 'is-selected': selectedResource?.id === r.id }"
            @click="selectResource(r)"
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
              <div class="rs-card-title">{{ r.name }}</div>
              <div class="rs-card-meta">
                <span class="rs-card-type">{{ typeLabel(r.type) }}</span>
                <span v-if="r.capacity" class="rs-card-capacity"><IconUsers style="width:12px;height:12px" /> {{ r.capacity }}</span>
              </div>
              <div class="rs-card-desc">{{ r.description }}</div>
              <div class="rs-card-tags">
                <span v-for="tag in r.tags" :key="tag" class="rs-tag">{{ tag }}</span>
              </div>
              <div class="rs-card-footer">
                <button class="rs-btn-book" @click.stop="openBookingModal(r)">
                  <IconCalendar style="width:12px;height:12px" /> Buchen
                </button>
              </div>
            </div>
          </div>
        </div>

        <!-- List View -->
        <div v-else class="rs-list">
          <div class="rs-list-header">
            <span style="flex:1">Name</span>
            <span style="width:120px">Typ</span>
            <span style="width:100px">Status</span>
            <span style="width:140px">Aktionen</span>
          </div>
          <div
            v-for="r in filteredResources"
            :key="r.id"
            class="rs-list-row"
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
            <div style="width:120px">
              <span class="rs-type-badge" :class="r.type">{{ typeLabel(r.type) }}</span>
            </div>
            <div style="width:100px">
              <span class="rs-status-dot" :class="r.status">{{ statusLabel(r.status) }}</span>
            </div>
            <div style="width:140px">
              <button class="rs-btn-book-sm" @click.stop="openBookingModal(r)">
                <IconCalendar style="width:12px;height:12px" /> Buchen
              </button>
            </div>
          </div>
        </div>

        <div v-if="filteredResources.length === 0" class="dk-list-empty" style="padding:60px 22px">
          <p style="margin:0 0 8px;font-size:15px;font-weight:500">Keine Ressourcen gefunden</p>
          <p style="margin:0;font-size:13px;color:var(--dk-text-muted)">Passe die Filter an oder suche nach einem anderen Begriff.</p>
        </div>
      </div>

      <!-- Right Sidebar: Detail OR My Bookings -->
      <div v-if="showMyBookings || selectedResource" class="rs-sidebar">

        <!-- Detail Panel -->
        <div v-if="selectedResource && !showMyBookings" class="rs-detail">
          <div class="rs-detail-header">
            <button class="rs-detail-close" @click="selectedResource = null">
              <IconX style="width:16px;height:16px" />
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
              <span v-if="selectedResource.capacity" class="rs-detail-capacity"><IconUsers style="width:12px;height:12px" /> {{ selectedResource.capacity }} Plätze</span>
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

            <button class="dk-btn dk-btn-primary" style="width:100%;margin-top:16px" @click="openBookingModal(selectedResource)">
              <IconCalendar style="width:14px;height:14px" /> Jetzt buchen
            </button>
          </div>
        </div>

        <!-- My Bookings Panel -->
        <div v-if="showMyBookings" class="rs-my-bookings">
          <div class="rs-detail-header">
            <h3 style="margin:0;font-size:15px">Meine Buchungen</h3>
            <button class="rs-detail-close" @click="showMyBookings = false">
              <IconX style="width:16px;height:16px" />
            </button>
          </div>

          <div v-if="myBookings.length === 0" class="dk-list-empty" style="padding:32px 16px">
            <p style="margin:0;font-size:13px;color:var(--dk-text-muted)">Du hast noch keine Buchungen.</p>
          </div>

          <div v-for="b in myBookings" :key="b.id" class="rs-my-booking">
            <div class="rs-my-booking-color" :class="`type-${b.resourceType}`"></div>
            <div class="rs-my-booking-body">
              <div class="rs-my-booking-title">{{ b.resourceName }}</div>
              <div class="rs-my-booking-date">{{ b.date }} · {{ b.time }}</div>
              <div class="rs-my-booking-purpose">{{ b.purpose }}</div>
            </div>
            <div class="rs-my-booking-actions">
              <button class="rs-my-btn" title="Bearbeiten" @click="editBooking(b)">
                <IconPencil style="width:14px;height:14px" />
              </button>
              <button class="rs-my-btn rs-my-btn--danger" title="Stornieren" @click="cancelBooking(b.id)">
                <IconTrash style="width:14px;height:14px" />
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Booking Modal -->
    <Teleport to="body">
      <div v-if="bookingModalOpen" class="dk-modal-overlay" @click.self="bookingModalOpen = false">
        <div class="dk-modal" style="max-width:480px">
          <h3>{{ editingBooking ? 'Buchung bearbeiten' : 'Ressource buchen' }}</h3>

          <div class="rs-form-group">
            <label>Ressource</label>
            <select v-model="bookingForm.resourceId" class="rs-form-select" :disabled="editingBooking">
              <option v-for="r in resources" :key="r.id" :value="r.id">{{ r.name }}</option>
            </select>
          </div>

          <div class="rs-form-row">
            <div class="rs-form-group">
              <label>Datum</label>
              <input v-model="bookingForm.date" type="date" class="rs-form-input" />
            </div>
            <div class="rs-form-group">
              <label>Zeitraum</label>
              <div class="rs-form-time">
                <input v-model="bookingForm.startTime" type="time" class="rs-form-input" />
                <span style="color:var(--dk-text-muted)">bis</span>
                <input v-model="bookingForm.endTime" type="time" class="rs-form-input" />
              </div>
            </div>
          </div>

          <div class="rs-form-group">
            <label>Zweck / Titel</label>
            <input v-model="bookingForm.purpose" type="text" class="rs-form-input" placeholder="z. B. Jugendabend, Gottesdienst…" />
          </div>

          <div class="rs-form-group">
            <label>Notizen</label>
            <textarea v-model="bookingForm.notes" rows="2" class="rs-form-input" placeholder="Optionale Hinweise…" />
          </div>

          <!-- Availability Preview -->
          <div v-if="bookingForm.resourceId && bookingForm.date" class="rs-availability">
            <div class="rs-availability-title">
              <IconInfo style="width:14px;height:14px" />
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

          <div class="dk-modal-actions">
            <button class="dk-btn dk-btn-secondary" @click="bookingModalOpen = false">Abbrechen</button>
            <button class="dk-btn dk-btn-primary" :disabled="!canSubmitBooking" @click="submitBooking">
              {{ editingBooking ? 'Speichern' : 'Buchen' }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, h } from 'vue'
import { useSession } from '../composables/useSession.js'
import { navigate } from '../router.js'

const { isAdmin } = useSession()

// ============================================================
// MOCK DATA - TODO_BACKEND: Replace with API calls
// ============================================================

// TODO_BACKEND: GET diakronos.diakonos.api.ressourcen.get_ressourcen_liste
// Params: { search?, type?, status? }
// Returns: [{ id, name, type, description, capacity?, status, tags[], image? }]
const resources = ref([
  { id: 'R-001', name: 'Gemeindesaal', type: 'room', description: 'Großer Saal mit Bühne, Beamer und Tonanlage. Für bis zu 120 Personen.', capacity: 120, status: 'available', tags: ['Beamer', 'Tonanlage', 'Küche', 'Rollstuhlgerecht'] },
  { id: 'R-002', name: 'Besprechungsraum', type: 'room', description: 'Kleiner Raum mit Tisch für 8 Personen. Ideal für Teamsitzungen.', capacity: 8, status: 'available', tags: ['Whiteboard', 'TV'] },
  { id: 'R-003', name: 'Kirchencafé', type: 'room', description: 'Gemütlicher Raum mit Küche und Sitzgruppen.', capacity: 30, status: 'booked', tags: ['Küche', 'Kaffeemaschine'] },
  { id: 'V-001', name: 'Gemeindebus', type: 'vehicle', description: '9-Sitzer Kleinbus, Führerschein Klasse B.', capacity: 9, status: 'available', tags: ['Klima', 'Anhängerkupplung'] },
  { id: 'V-002', name: 'Pkw (Gemeinde)', type: 'vehicle', description: 'VW Passat Kombi, Führerschein Klasse B.', capacity: 5, status: 'maintenance', tags: ['Dachträger'] },
  { id: 'I-001', name: 'Beamer Full-HD', type: 'item', description: 'Epson Beamer, 4000 Lumen, Full HD.', capacity: null, status: 'available', tags: ['Full HD', 'HDMI', '4000 Lumen'] },
  { id: 'I-002', name: 'Tonmischpult', type: 'item', description: 'Yamaha 16-Kanal Digitalmischpult.', capacity: null, status: 'available', tags: ['16 Kanäle', 'Digital', 'USB'] },
  { id: 'I-003', name: 'Fotostativ', type: 'item', description: 'Robustes Aluminium-Stativ bis 2m Höhe.', capacity: null, status: 'booked', tags: ['Aluminium', '2m'] },
])

// TODO_BACKEND: GET diakronos.diakonos.api.ressourcen.get_ressource_buchungen
// Params: { resource_id, date_from?, date_to? }
// Returns: [{ id, title, date, time, user }]
const allBookings = ref([
  { id: 'B-001', resourceId: 'R-001', resourceName: 'Gemeindesaal', resourceType: 'room', title: 'Gottesdienst', day: '27', month: 'Apr', date: '2026-04-27', time: '10:00 – 12:00', user: 'Pfarrer Schmidt', purpose: 'Sonntagsgottesdienst' },
  { id: 'B-002', resourceId: 'R-001', resourceName: 'Gemeindesaal', resourceType: 'room', title: 'Jugendabend', day: '30', month: 'Apr', date: '2026-04-30', time: '18:30 – 21:00', user: 'Julia Hoffmann', purpose: 'Jugendtreffen' },
  { id: 'B-003', resourceId: 'R-003', resourceName: 'Kirchencafé', resourceType: 'room', title: 'Frühstück', day: '28', month: 'Apr', date: '2026-04-28', time: '09:00 – 11:00', user: 'Seniorenkreis', purpose: 'Seniorenfrühstück' },
  { id: 'B-004', resourceId: 'V-001', resourceName: 'Gemeindebus', resourceType: 'vehicle', title: 'Fahrt Jugendcamp', day: '02', month: 'Mai', date: '2026-05-02', time: '08:00 – 18:00', user: 'Markus Becker', purpose: 'Jugendcamp Transport' },
  { id: 'B-005', resourceId: 'I-003', resourceName: 'Fotostativ', resourceType: 'item', title: 'Konfirmation', day: '15', month: 'Mai', date: '2026-05-15', time: '14:00 – 16:00', user: 'Technik-Team', purpose: 'Fotos Konfirmation' },
])

// TODO_BACKEND: GET diakronos.diakonos.api.ressourcen.get_meine_buchungen
// Params: { user_email }
// Returns: [{ id, resourceId, resourceName, resourceType, date, time, purpose }]
const myBookings = ref([
  { id: 'B-004', resourceId: 'V-001', resourceName: 'Gemeindebus', resourceType: 'vehicle', date: 'Sa, 02. Mai 2026', time: '08:00 – 18:00', purpose: 'Jugendcamp Transport' },
  { id: 'B-006', resourceId: 'R-002', resourceName: 'Besprechungsraum', resourceType: 'room', date: 'Mi, 29. Apr 2026', time: '19:00 – 20:30', purpose: 'Teamleitungssitzung' },
])

// ============================================================
// STATE
// ============================================================
const viewMode = ref('grid')
const searchQuery = ref('')
const typeFilter = ref('')
const selectedResource = ref(null)
const showMyBookings = ref(false)
const bookingModalOpen = ref(false)
const editingBooking = ref(null)
const searchDebounce = ref(null)

const bookingForm = ref({
  resourceId: '',
  date: '',
  startTime: '',
  endTime: '',
  purpose: '',
  notes: ''
})

// ============================================================
// COMPUTED
// ============================================================
const filteredResources = computed(() => {
  let list = resources.value
  if (typeFilter.value) {
    list = list.filter(r => r.type === typeFilter.value)
  }
  if (searchQuery.value.trim()) {
    const q = searchQuery.value.toLowerCase()
    list = list.filter(r =>
      r.name.toLowerCase().includes(q) ||
      r.description.toLowerCase().includes(q) ||
      r.tags.some(t => t.toLowerCase().includes(q))
    )
  }
  return list
})

const filteredCount = computed(() => filteredResources.value.length)

const typeFilters = computed(() => {
  const counts = { room: 0, vehicle: 0, item: 0 }
  resources.value.forEach(r => { if (counts[r.type] !== undefined) counts[r.type]++ })
  return [
    { id: 'room', label: 'Räume', count: counts.room },
    { id: 'vehicle', label: 'Fahrzeuge', count: counts.vehicle },
    { id: 'item', label: 'Gegenstände', count: counts.item },
  ]
})

const resourceBookings = computed(() => {
  if (!selectedResource.value) return []
  return allBookings.value
    .filter(b => b.resourceId === selectedResource.value.id)
    .slice(0, 5)
})

const canSubmitBooking = computed(() => {
  return bookingForm.value.resourceId &&
    bookingForm.value.date &&
    bookingForm.value.startTime &&
    bookingForm.value.endTime &&
    bookingForm.value.purpose.trim()
})

// Mock availability slots (24h)
const availabilitySlots = computed(() => {
  const slots = []
  for (let i = 0; i < 24; i++) {
    slots.push({
      hour: i,
      booked: [8, 9, 10, 14, 15].includes(i), // Mock booked hours
      selected: false,
      label: `${String(i).padStart(2, '0')}:00`
    })
  }
  return slots
})

// ============================================================
// METHODS
// ============================================================
function onSearchInput() {
  clearTimeout(searchDebounce.value)
  searchDebounce.value = setTimeout(() => {
    // TODO_BACKEND: Trigger search API
  }, 300)
}

function selectResource(r) {
  selectedResource.value = selectedResource.value?.id === r.id ? null : r
  showMyBookings.value = false
}

function typeLabel(type) {
  const map = { room: 'Raum', vehicle: 'Fahrzeug', item: 'Gegenstand' }
  return map[type] || type
}

function statusLabel(status) {
  const map = { available: 'Verfügbar', booked: 'Belegt', maintenance: 'Wartung' }
  return map[status] || status
}

function openBookingModal(resource = null) {
  editingBooking.value = null
  bookingForm.value = {
    resourceId: resource?.id || '',
    date: new Date().toISOString().split('T')[0],
    startTime: '09:00',
    endTime: '11:00',
    purpose: '',
    notes: ''
  }
  bookingModalOpen.value = true
}

function editBooking(booking) {
  editingBooking.value = booking
  bookingForm.value = {
    resourceId: booking.resourceId,
    date: '2026-04-27', // Parse from booking.date
    startTime: '08:00',
    endTime: '18:00',
    purpose: booking.purpose,
    notes: ''
  }
  bookingModalOpen.value = true
}

function submitBooking() {
  // TODO_BACKEND: POST diakronos.diakonos.api.ressourcen.create_buchung
  // Params: { resource_id, date, start_time, end_time, purpose, notes, user_email }
  console.log('Booking submitted:', bookingForm.value)
  bookingModalOpen.value = false
}

function cancelBooking(id) {
  // TODO_BACKEND: DELETE diakronos.diakonos.api.ressourcen.delete_buchung
  // Params: { id, user_email }
  if (!confirm('Buchung wirklich stornieren?')) return
  myBookings.value = myBookings.value.filter(b => b.id !== id)
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
</script>

<style scoped>
/* ================================================================
   LAYOUT
   ================================================================ */
.rs-layout {
  display: grid;
  grid-template-columns: 1fr;
  gap: 24px;
  align-items: start;
}
.rs-layout.has-sidebar {
  grid-template-columns: 1fr 360px;
}

.rs-main {
  min-width: 0;
}

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
.rs-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
}

.rs-card {
  background: var(--dk-surface);
  border: 1px solid var(--dk-border);
  border-radius: 12px;
  overflow: hidden;
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
  box-shadow: 0 0 0 3px rgba(212,162,76,.15);
}

.rs-card-image {
  height: 120px;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  background: var(--dk-surface-2);
}
.rs-card-image.type-room { background: linear-gradient(135deg, #eef1f8 0%, #d6dcea 100%); }
.rs-card-image.type-vehicle { background: linear-gradient(135deg, #fef3e2 0%, #fde8c4 100%); }
.rs-card-image.type-item { background: linear-gradient(135deg, #f0f4ff 0%, #e0e8ff 100%); }

.rs-card-icon {
  color: var(--dk-brand-400);
  opacity: 0.5;
}
.rs-card-image.type-room .rs-card-icon { color: var(--dk-brand-500); }
.rs-card-image.type-vehicle .rs-card-icon { color: #d97706; }
.rs-card-image.type-item .rs-card-icon { color: #2563eb; }

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
.rs-card-badge.available { background: rgba(22,163,74,.12); color: var(--dk-success); }
.rs-card-badge.booked { background: rgba(220,38,38,.10); color: var(--dk-danger); }
.rs-card-badge.maintenance { background: rgba(217,119,6,.10); color: var(--dk-warning); }

.rs-card-body {
  padding: 14px 16px 16px;
}
.rs-card-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--dk-text);
  margin-bottom: 4px;
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
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 7px 14px;
  border-radius: 8px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: all var(--dk-fast);
  border: none;
  background: var(--dk-brand-50);
  color: var(--dk-brand-500);
}
.rs-btn-book:hover {
  background: var(--dk-brand-500);
  color: #fff;
}

/* ================================================================
   LIST VIEW
   ================================================================ */
.rs-list {
  background: var(--dk-surface);
  border: 1px solid var(--dk-border);
  border-radius: 12px;
  overflow: hidden;
}
.rs-list-header {
  display: flex;
  align-items: center;
  padding: 10px 16px;
  font-size: 11px;
  font-weight: 600;
  color: var(--dk-text-subtle);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  border-bottom: 1px solid var(--dk-divider);
  background: var(--dk-surface-2);
}
.rs-list-row {
  display: flex;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid var(--dk-divider);
  cursor: pointer;
  transition: background var(--dk-fast);
}
.rs-list-row:last-child { border-bottom: none; }
.rs-list-row:hover { background: var(--dk-surface-hover); }
.rs-list-row.is-selected { background: rgba(212,162,76,.06); }

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
.rs-list-icon.type-vehicle { color: #d97706; background: #fef3e2; }
.rs-list-icon.type-item { color: #2563eb; background: #f0f4ff; }
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
.rs-type-badge.room { background: #eef1f8; color: var(--dk-brand-500); }
.rs-type-badge.vehicle { background: #fef3e2; color: #b45309; }
.rs-type-badge.item { background: #f0f4ff; color: #1d4ed8; }

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
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 5px 10px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 600;
  cursor: pointer;
  transition: all var(--dk-fast);
  border: none;
  background: var(--dk-surface-2);
  color: var(--dk-text-muted);
}
.rs-btn-book-sm:hover {
  background: var(--dk-brand-500);
  color: #fff;
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
.rs-detail-image.type-room { background: linear-gradient(135deg, #eef1f8 0%, #d6dcea 100%); }
.rs-detail-image.type-vehicle { background: linear-gradient(135deg, #fef3e2 0%, #fde8c4 100%); }
.rs-detail-image.type-item { background: linear-gradient(135deg, #f0f4ff 0%, #e0e8ff 100%); }
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
.rs-my-booking-color.type-vehicle { background: #d97706; }
.rs-my-booking-color.type-item { background: #2563eb; }
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
.rs-my-btn--danger:hover { background: rgba(220,38,38,.10); color: var(--dk-danger); }

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
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}
.rs-form-time {
  display: flex;
  align-items: center;
  gap: 8px;
}
.rs-form-time input {
  flex: 1;
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
  .rs-grid {
    grid-template-columns: 1fr;
  }
  .rs-list-header { display: none; }
  .rs-list-row {
    flex-direction: column;
    align-items: flex-start;
    gap: 8px;
  }
  .rs-form-row {
    grid-template-columns: 1fr;
  }
  .rs-my-booking-actions { opacity: 1; }
}
</style>
