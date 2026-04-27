<template>
  <div class="dk-screen dk-screen-enter">

    <!-- ==================== ADMIN HUB ==================== -->
    <template v-if="isAdmin">
      <div class="dk-screen-header">
        <div>
          <h1 class="dk-hub-greeting">
            Guten {{ greeting }},
            <span class="dk-muted">{{ firstName }}.</span>
          </h1>
          <p class="dk-hub-sub">{{ todayLabel }}</p>
        </div>
        <div class="dk-screen-actions">
          <button class="dk-btn dk-btn-secondary">
            <IconDownload /> Export
          </button>
          <button class="dk-btn dk-btn-primary" @click="navigate('#/anmeldungen')">
            <IconPlus /> Neues Mitglied
          </button>
        </div>
      </div>

      <div class="dk-stats-row">
        <div class="dk-card dk-stat-card" v-for="s in stats" :key="s.label">
          <div class="dk-stat-label">{{ s.label }}</div>
          <div class="dk-stat-value">
            <span v-if="loading">–</span>
            <span v-else>{{ s.value }}</span>
          </div>
          <div class="dk-stat-trend" :class="s.trend === 'down' ? 'down' : s.trend === 'flat' ? 'flat' : ''">
            <IconTrendUp v-if="!s.trend || s.trend === 'up'" />
            <IconTrendDown v-else-if="s.trend === 'down'" />
            {{ s.note }}
          </div>
        </div>
      </div>

      <div class="dk-quick-row">
        <button class="dk-quick-card" @click="navigate('#/anmeldungen')">
          <div class="dk-quick-icon"><IconUserPlus /></div>
          <div>
            <div class="dk-quick-title">Mitglied hinzufügen</div>
            <div class="dk-quick-desc">Neue Person anlegen und Gruppen zuordnen.</div>
          </div>
        </button>
        <button class="dk-quick-card" @click="navigate('#/mitglieder')">
          <div class="dk-quick-icon"><IconUsers /></div>
          <div>
            <div class="dk-quick-title">Mitgliederliste</div>
            <div class="dk-quick-desc">Alle Mitglieder suchen, filtern und verwalten.</div>
          </div>
        </button>
        <button class="dk-quick-card" @click="navigate('#/gruppen')">
          <div class="dk-quick-icon"><IconLayoutGrid /></div>
          <div>
            <div class="dk-quick-title">Gruppen & Dienste</div>
            <div class="dk-quick-desc">Mitarbeitende zu Bereichen zuordnen.</div>
          </div>
        </button>
      </div>

      <div class="dk-hub-grid">
        <div class="dk-card dk-panel">
          <div class="dk-panel-header">
            <h3 class="dk-panel-title">Neue Anmeldungen</h3>
            <a href="#/anmeldungen" class="dk-panel-link">
              Alle anzeigen
              <IconChevronRight style="width:12px;height:12px" />
            </a>
          </div>
          <div>
            <div v-if="anmeldungen.length === 0" class="dk-list-empty" style="padding:40px 22px">
              <p style="margin:0;font-size:13px">Keine offenen Anmeldungen.</p>
            </div>
            <div
              v-for="a in anmeldungen.slice(0, 5)"
              :key="a.name"
              class="dk-activity-item"
              style="cursor:pointer"
              @click="navigate('#/anmeldungen')"
            >
              <div class="dk-avatar dk-avatar-sm" :style="{ background: avatarColor(a.vorname), color: '#fff' }">
                {{ initials(a.vorname, a.nachname) }}
              </div>
              <div class="dk-activity-text">
                <div><strong>{{ a.vorname }} {{ a.nachname }}</strong> hat sich angemeldet.</div>
                <div class="dk-activity-time">{{ formatDate(a.anmeldedatum) }} · {{ a.anmeldungstyp === 'Mitglied-Registrierung' ? 'Mitglied' : 'Gast' }}</div>
              </div>
              <span class="dk-badge" :class="statusBadgeClass(a.status)">
                <span class="dk-badge-dot" />{{ a.status }}
              </span>
            </div>
          </div>
        </div>

        <div style="display:flex;flex-direction:column;gap:20px">
          <div class="dk-card dk-panel">
            <div class="dk-panel-header">
              <h3 class="dk-panel-title">DSGVO-Compliance</h3>
              <a href="#/dsgvo" class="dk-panel-link">
                Details <IconChevronRight style="width:12px;height:12px" />
              </a>
            </div>
            <div style="padding:16px 22px">
              <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px">
                <span style="font-size:13px;color:var(--dk-text-muted)">Einwilligung erteilt</span>
                <span style="font-size:22px;font-weight:600;color:var(--dk-success)">{{ dsgvoPct }}%</span>
              </div>
              <div style="height:6px;border-radius:3px;background:var(--dk-surface-2);overflow:hidden">
                <div :style="{ width: dsgvoPct + '%', height: '100%', borderRadius: '3px', background: dsgvoPct >= 90 ? 'var(--dk-success)' : 'var(--dk-warning)', transition: 'width 0.5s' }" />
              </div>
              <div style="display:flex;justify-content:space-between;margin-top:8px;font-size:12px;color:var(--dk-text-subtle)">
                <span>{{ dsgvo.ok }} erteilt</span>
                <span>{{ dsgvo.fehlt }} fehlt</span>
              </div>
            </div>
          </div>

          <div class="dk-card dk-panel">
            <div class="dk-panel-header">
              <h3 class="dk-panel-title">Mitglieder-Status</h3>
              <a href="#/statistik" class="dk-panel-link">
                Statistik <IconChevronRight style="width:12px;height:12px" />
              </a>
            </div>
            <div style="padding:12px 22px">
              <div
                v-for="row in statusRows"
                :key="row.label"
                class="dk-upcoming-item"
                style="padding:8px 0;border-top:none"
                :style="row !== statusRows[0] ? { borderTop: '1px solid var(--dk-divider)' } : {}"
              >
                <div style="display:flex;align-items:center;gap:8px;flex:1">
                  <span style="width:8px;height:8px;border-radius:50%;flex-shrink:0" :style="{ background: row.color }" />
                  <span style="font-size:13px">{{ row.label }}</span>
                </div>
                <span style="font-size:20px;font-weight:600;font-variant-numeric:tabular-nums">
                  {{ loading ? '–' : row.value }}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>

    <!-- ==================== MITGLIED DASHBOARD ==================== -->
    <template v-else>
      <!-- Header -->
      <div class="dk-screen-header">
        <div>
          <h1 class="dk-hub-greeting">
            Guten {{ greeting }},
            <span class="dk-muted">{{ firstName }}.</span>
          </h1>
          <p class="dk-hub-sub">{{ todayLabel }}</p>
        </div>
      </div>

      <!-- Quick Links -->
      <div class="md-quick-row">
        <button class="md-quick-card md-quick-card--highlight" @click="navigate('#/gruppen')">
          <div class="md-quick-icon"><IconLayoutGrid /></div>
          <div>
            <div class="md-quick-title">Gruppen & Dienste</div>
            <div class="md-quick-desc">Deine Bereiche und Dienstzuordnungen</div>
          </div>
        </button>
        <button class="md-quick-card" @click="navigate('#/mitglieder')">
          <div class="md-quick-icon"><IconUsers /></div>
          <div>
            <div class="md-quick-title">Mitglieder</div>
            <div class="md-quick-desc">Adressbuch und Kontakte</div>
          </div>
        </button>
        <button class="md-quick-card" @click="navigate('#/kalender')">
          <div class="md-quick-icon"><IconCalendar /></div>
          <div>
            <div class="md-quick-title">Kalender</div>
            <div class="md-quick-desc">Termine und Veranstaltungen</div>
          </div>
        </button>
      </div>

      <!-- Main Grid -->
      <div class="md-dashboard-grid">

        <!-- LEFT COLUMN -->
        <div class="md-col">

          <!-- Anstehende Dienste -->
          <div class="dk-card md-panel">
            <div class="dk-panel-header">
              <h3 class="dk-panel-title">
                <IconBriefcase style="width:14px;height:14px" />
                Anstehende Dienste
              </h3>
              <a href="#/dienstplan" class="dk-panel-link">
                Zum Dienstplan <IconChevronRight style="width:12px;height:12px" />
              </a>
            </div>
            <div class="md-dienst-list">
              <div v-if="upcomingDienste.length === 0" class="dk-list-empty" style="padding:32px 22px">
                <p style="margin:0;font-size:13px;color:var(--dk-text-muted)">Keine anstehenden Dienste.</p>
              </div>
              <div
                v-for="d in upcomingDienste"
                :key="d.id"
                class="md-dienst-item"
                @click="navigate('#/dienstplan')"
              >
                <div class="md-dienst-date">
                  <div class="md-dienst-day">{{ d.day }}</div>
                  <div class="md-dienst-month">{{ d.month }}</div>
                </div>
                <div class="md-dienst-body">
                  <div class="md-dienst-title">{{ d.title }}</div>
                  <div class="md-dienst-meta">
                    <span class="md-dienst-time"><IconClock style="width:12px;height:12px" /> {{ d.time }}</span>
                    <span class="md-dienst-group"><IconMapPin style="width:12px;height:12px" /> {{ d.group }}</span>
                  </div>
                </div>
                <div class="md-dienst-status" :class="`status-${d.status}`">
                  {{ d.statusLabel }}
                </div>
              </div>
            </div>
          </div>

          <!-- Dienstmöglichkeiten -->
          <div class="dk-card md-panel">
            <div class="dk-panel-header">
              <h3 class="dk-panel-title">
                <IconMail style="width:14px;height:14px" />
                Dienstmöglichkeiten
              </h3>
              <span class="dk-panel-link" style="cursor:default">
                {{ dienstAnfragen.filter(a => a.status === 'pending').length }} offen
              </span>
            </div>
            <div class="md-anfragen-list">
              <div v-if="dienstAnfragen.length === 0" class="dk-list-empty" style="padding:32px 22px">
                <p style="margin:0;font-size:13px;color:var(--dk-text-muted)">Keine offenen Anfragen.</p>
              </div>
              <div
                v-for="a in dienstAnfragen"
                :key="a.id"
                class="md-anfrage-item"
              >
                <div class="md-anfrage-info">
                  <div class="md-anfrage-title">{{ a.title }}</div>
                  <div class="md-anfrage-meta">
                    <span>{{ a.date }}</span>
                    <span>·</span>
                    <span>{{ a.group }}</span>
                  </div>
                </div>
                <div class="md-anfrage-actions">
                  <button class="md-btn-accept" @click="acceptAnfrage(a.id)">
                    <IconCheck style="width:12px;height:12px" /> Zusage
                  </button>
                  <button class="md-btn-decline" @click="declineAnfrage(a.id)">
                    <IconX style="width:12px;height:12px" /> Absage
                  </button>
                </div>
              </div>
            </div>
          </div>

        </div>

        <!-- RIGHT COLUMN -->
        <div class="md-col md-col--right">

          <!-- Mini Kalender -->
          <div class="dk-card md-panel">
            <div class="dk-panel-header">
              <h3 class="dk-panel-title">
                <IconCalendar style="width:14px;height:14px" />
                Kalender
              </h3>
              <a href="#/kalender" class="dk-panel-link">
                Öffnen <IconChevronRight style="width:12px;height:12px" />
              </a>
            </div>
            <div class="md-calendar">
              <div class="md-cal-header">
                <button class="md-cal-nav" @click="prevMonth"><IconChevronLeft style="width:14px;height:14px" /></button>
                <span class="md-cal-month">{{ currentMonthLabel }}</span>
                <button class="md-cal-nav" @click="nextMonth"><IconChevronRight style="width:14px;height:14px" /></button>
              </div>
              <div class="md-cal-weekdays">
                <span v-for="wd in ['Mo','Di','Mi','Do','Fr','Sa','So']" :key="wd">{{ wd }}</span>
              </div>
              <div class="md-cal-days">
                <span
                  v-for="day in calendarDays"
                  :key="day.key"
                  class="md-cal-day"
                  :class="{
                    'is-today': day.isToday,
                    'is-other': day.isOtherMonth,
                    'has-event': day.hasEvent
                  }"
                >
                  {{ day.day }}
                </span>
              </div>
              <div class="md-cal-legend">
                <span class="md-cal-dot" style="background:var(--dk-accent)"></span>
                <span style="font-size:11px;color:var(--dk-text-muted)">Dienst / Termin</span>
              </div>
            </div>
          </div>

          <!-- Kontaktliste -->
          <div class="dk-card md-panel">
            <div class="dk-panel-header">
              <h3 class="dk-panel-title">
                <IconAddressBook style="width:14px;height:14px" />
                Kontakte
              </h3>
              <a href="#/mitglieder" class="dk-panel-link">
                Alle <IconChevronRight style="width:12px;height:12px" />
              </a>
            </div>
            <div class="md-kontakt-search">
              <IconSearch style="width:14px;height:14px;color:var(--dk-text-subtle)" />
              <input
                v-model="kontaktSearch"
                type="text"
                placeholder="Kontakt suchen..."
              />
            </div>
            <div class="md-kontakt-list">
              <div
                v-for="k in filteredKontakte"
                :key="k.id"
                class="md-kontakt-item"
                @click="navigate(`#/mitglied/${k.id}`)"
              >
                <div class="dk-avatar dk-avatar-sm" :style="{ background: avatarColor(k.vorname), color: '#fff' }">
                  {{ initials(k.vorname, k.nachname) }}
                </div>
                <div class="md-kontakt-info">
                  <div class="md-kontakt-name">{{ k.vorname }} {{ k.nachname }}</div>
                  <div class="md-kontakt-role">{{ k.role }}</div>
                </div>
                <div class="md-kontakt-actions">
                  <a v-if="k.email" :href="`mailto:${k.email}`" class="md-kontakt-btn" title="E-Mail" @click.stop>
                    <IconMail style="width:14px;height:14px" />
                  </a>
                  <a v-if="k.phone" :href="`tel:${k.phone}`" class="md-kontakt-btn" title="Anrufen" @click.stop>
                    <IconPhone style="width:14px;height:14px" />
                  </a>
                </div>
              </div>
            </div>
          </div>

        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, h } from 'vue'
import { useSession } from '../composables/useSession.js'
import { apiCall } from '../composables/useApi.js'
import { navigate } from '../router.js'

const { user, isAdmin } = useSession()
const loading = ref(true)
const mitgliederData = ref({})
const dsgvo = ref({ ok: 0, fehlt: 0, widerrufen: 0 })
const anmeldungenStats = ref({ gesamt: 0, offen: 0, diesen_monat: 0 })
const anmeldungen = ref([])

// --- Greeting ---
const greeting = computed(() => {
  const h = new Date().getHours()
  if (h < 12) return 'Morgen'
  if (h < 18) return 'Tag'
  return 'Abend'
})
const firstName = computed(() => (user.value.fullname || '').split(' ')[0] || 'Nutzer')
const todayLabel = computed(() => {
  return new Date().toLocaleDateString('de-DE', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })
})

// --- Admin Stats ---
const m = computed(() => mitgliederData.value)
const stats = computed(() => [
  { label: 'Mitglieder gesamt', value: m.value.gesamt || 0,   note: 'Registriert' },
  { label: 'Aktive Mitglieder', value: m.value.mitglied || 0, note: 'Status Mitglied', trend: 'up' },
  { label: 'Gäste & Kinder',    value: (m.value.gast || 0) + (m.value.kind || 0), note: 'Gast + Kind', trend: 'flat' },
  { label: 'Anmeldeanfragen',   value: anmeldungenStats.value.offen || 0, note: 'Offen', trend: (anmeldungenStats.value.offen || 0) > 0 ? 'up' : 'flat' },
])

const statusRows = computed(() => [
  { label: 'Mitglied',   value: m.value.mitglied   || 0, color: '#16a34a' },
  { label: 'Gast',       value: m.value.gast       || 0, color: '#d97706' },
  { label: 'Kind',       value: m.value.kind       || 0, color: '#2563eb' },
  { label: 'Inaktiv',    value: m.value.inaktiv    || 0, color: '#9ca3af' },
  { label: 'Archiviert', value: m.value.archiviert || 0, color: '#dc2626' },
])

const dsgvoPct = computed(() => {
  const total = m.value.gesamt || 0
  return total > 0 ? Math.round((dsgvo.value.ok / total) * 100) : 0
})

// --- Admin API ---
async function loadData() {
  loading.value = true
  try {
    const data = await apiCall('diakronos.diakonos.api.admin_hub.get_statistik')
    mitgliederData.value = data.mitglieder || {}
    dsgvo.value = data.dsgvo || {}
    anmeldungenStats.value = data.anmeldungen || {}
  } catch (e) {
    console.warn('Statistik nicht verfügbar', e)
  } finally {
    loading.value = false
  }
}

async function loadAnmeldungen() {
  try {
    const data = await apiCall('diakronos.diakonos.api.admin_hub.get_anmeldungen_hub')
    anmeldungen.value = (data.anmeldungen || [])
      .filter(a => a.status === 'Anmeldeanfrage' || a.status === 'Ausstehend')
      .slice(0, 5)
  } catch (e) { /* noop */ }
}

onMounted(() => {
  if (isAdmin.value) {
    loadData()
    loadAnmeldungen()
  } else {
    loading.value = false
    loadMemberDashboard()
  }
})

// ============================================================
// MEMBER DASHBOARD DATA
// ============================================================

// --- MOCK: Anstehende Dienste ---
// TODO_BACKEND: Endpoint `diakronos.diakonos.api.dienstplan.get_meine_dienste`
// Params: { user_email, limit: 5, status: ['confirmed','pending'] }
// Returns: [{ id, title, date, time, group, status }]
const upcomingDienste = ref([
  { id: 1, title: 'Gottesdienst – Lektoren', day: '28', month: 'Apr', time: '10:00 – 12:00', group: 'Lektoren', status: 'confirmed', statusLabel: 'Bestätigt' },
  { id: 2, title: 'Jugendabend – Betreuung', day: '02', month: 'Mai', time: '18:30 – 21:00', group: 'Jugend', status: 'confirmed', statusLabel: 'Bestätigt' },
  { id: 3, title: 'Taufvorbereitung', day: '15', month: 'Mai', time: '14:00 – 16:00', group: 'Taufpaten', status: 'pending', statusLabel: 'Ausstehend' },
])

// --- MOCK: Dienstmöglichkeiten ---
// TODO_BACKEND: Endpoint `diakronos.diakonos.api.dienstplan.get_dienstanfragen`
// Params: { user_email }
// Returns: [{ id, title, date, group, status }]
// Actions: POST `diakronos.diakonos.api.dienstplan.respond_anfrage` { id, response: 'accept'|'decline' }
const dienstAnfragen = ref([
  { id: 101, title: 'Gottesdienst – Technik', date: 'So, 05. Mai 2025', group: 'Technik', status: 'pending' },
  { id: 102, title: 'Kirchencafé – Aufbau', date: 'Sa, 10. Mai 2025', group: 'Hospitality', status: 'pending' },
])

function acceptAnfrage(id) {
  // TODO_BACKEND: Call API to accept
  const idx = dienstAnfragen.value.findIndex(a => a.id === id)
  if (idx > -1) dienstAnfragen.value.splice(idx, 1)
}

function declineAnfrage(id) {
  // TODO_BACKEND: Call API to decline
  const idx = dienstAnfragen.value.findIndex(a => a.id === id)
  if (idx > -1) dienstAnfragen.value.splice(idx, 1)
}

// --- Mini Kalender ---
// TODO_BACKEND: Endpoint `diakronos.diakonos.api.kalender.get_events`
// Params: { month, year, user_email }
// Returns: [{ date: '2025-04-28', title, type }]
const calCurrentDate = ref(new Date())
const currentMonthLabel = computed(() => {
  return calCurrentDate.value.toLocaleDateString('de-DE', { month: 'long', year: 'numeric' })
})

// MOCK: Event dates for highlighting
const eventDates = ref(['2025-04-28', '2025-05-02', '2025-05-05', '2025-05-10', '2025-05-15'])

const calendarDays = computed(() => {
  const year = calCurrentDate.value.getFullYear()
  const month = calCurrentDate.value.getMonth()
  const firstDayOfMonth = new Date(year, month, 1)
  const lastDayOfMonth = new Date(year, month + 1, 0)
  const daysInMonth = lastDayOfMonth.getDate()

  // Adjust so Monday = 0
  let startWeekday = firstDayOfMonth.getDay() - 1
  if (startWeekday < 0) startWeekday = 6

  const today = new Date()
  const days = []

  // Previous month padding
  const prevMonthLastDay = new Date(year, month, 0).getDate()
  for (let i = startWeekday - 1; i >= 0; i--) {
    const d = prevMonthLastDay - i
    days.push({ key: `p${d}`, day: d, isOtherMonth: true, isToday: false, hasEvent: false })
  }

  // Current month
  for (let d = 1; d <= daysInMonth; d++) {
    const dateStr = `${year}-${String(month + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`
    const isToday = today.getFullYear() === year && today.getMonth() === month && today.getDate() === d
    days.push({
      key: `c${d}`,
      day: d,
      isOtherMonth: false,
      isToday,
      hasEvent: eventDates.value.includes(dateStr)
    })
  }

  // Next month padding to fill 6 rows
  const remaining = 42 - days.length
  for (let d = 1; d <= remaining; d++) {
    days.push({ key: `n${d}`, day: d, isOtherMonth: true, isToday: false, hasEvent: false })
  }

  return days
})

function prevMonth() {
  calCurrentDate.value = new Date(calCurrentDate.value.getFullYear(), calCurrentDate.value.getMonth() - 1, 1)
}

function nextMonth() {
  calCurrentDate.value = new Date(calCurrentDate.value.getFullYear(), calCurrentDate.value.getMonth() + 1, 1)
}

// --- Kontaktliste ---
// TODO_BACKEND: Endpoint `diakronos.diakonos.api.mitglieder.get_kontaktliste`
// Params: { user_email, search? }
// Returns: [{ id, vorname, nachname, role, email?, phone? }]
const kontaktSearch = ref('')
const kontakte = ref([
  { id: 'MIT-001', vorname: 'Anna', nachname: 'Bergmann', role: 'Lektor · Chor', email: 'anna.bergmann@example.de', phone: '' },
  { id: 'MIT-002', vorname: 'Hans', nachname: 'Müller', role: 'Technik · Verwaltung', email: 'hans.mueller@example.de', phone: '+49 171 1234567' },
  { id: 'MIT-003', vorname: 'Julia', nachname: 'Hoffmann', role: 'Jugend · Taufpaten', email: 'julia.hoffmann@example.de', phone: '' },
  { id: 'MIT-004', vorname: 'Klaus', nachname: 'Wagner', role: 'Hospitality', email: 'klaus.wagner@example.de', phone: '+49 172 9876543' },
  { id: 'MIT-005', vorname: 'Maria', nachname: 'Schneider', role: 'Chor · Kinder', email: 'maria.schneider@example.de', phone: '' },
  { id: 'MIT-006', vorname: 'Markus', nachname: 'Becker', role: 'Pastoral', email: 'markus.becker@example.de', phone: '+49 173 5555555' },
])

const filteredKontakte = computed(() => {
  const q = kontaktSearch.value.toLowerCase().trim()
  if (!q) return kontakte.value.slice(0, 6)
  return kontakte.value.filter(k =>
    `${k.vorname} ${k.nachname}`.toLowerCase().includes(q) ||
    (k.role || '').toLowerCase().includes(q)
  ).slice(0, 10)
})

async function loadMemberDashboard() {
  // TODO_BACKEND: Load real data from endpoints:
  // - get_meine_dienste
  // - get_dienstanfragen
  // - get_events (for calendar)
  // - get_kontaktliste
}

// --- Utils ---
function initials(v, n) {
  return ((v || '').charAt(0) + (n || '').charAt(0)).toUpperCase()
}
const COLORS = ['#3e4d78', '#1c2850', '#6e7ca6', '#d4a24c', '#8B5E3C', '#2563eb']
function avatarColor(name) {
  return COLORS[(name || 'A').charCodeAt(0) % COLORS.length]
}
function formatDate(d) {
  if (!d) return '–'
  return new Date(String(d).split(' ')[0]).toLocaleDateString('de-DE')
}
function statusBadgeClass(s) {
  if (s === 'Bestätigt') return 'dk-badge-success'
  if (s === 'Abgelehnt') return 'dk-badge-danger'
  if (s === 'Warteliste') return 'dk-badge-info'
  return 'dk-badge-warning'
}

// --- Inline Icons ---
const IconDownload     = () => h('svg', { width:14, height:14, viewBox:'0 0 24 24', fill:'none', stroke:'currentColor', 'stroke-width':2, 'stroke-linecap':'round', 'stroke-linejoin':'round' }, [h('path',{d:'M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4'}), h('polyline',{points:'7 10 12 15 17 10'}), h('line',{x1:12,y1:15,x2:12,y2:3})])
const IconPlus         = () => h('svg', { width:14, height:14, viewBox:'0 0 24 24', fill:'none', stroke:'currentColor', 'stroke-width':2, 'stroke-linecap':'round', 'stroke-linejoin':'round' }, [h('line',{x1:12,y1:5,x2:12,y2:19}), h('line',{x1:5,y1:12,x2:19,y2:12})])
const IconUserPlus     = () => h('svg', { width:18, height:18, viewBox:'0 0 24 24', fill:'none', stroke:'currentColor', 'stroke-width':2, 'stroke-linecap':'round', 'stroke-linejoin':'round' }, [h('path',{d:'M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2'}), h('circle',{cx:8.5,cy:7,r:4}), h('line',{x1:20,y1:8,x2:20,y2:14}), h('line',{x1:23,y1:11,x2:17,y2:11})])
const IconUsers        = () => h('svg', { width:18, height:18, viewBox:'0 0 24 24', fill:'none', stroke:'currentColor', 'stroke-width':2, 'stroke-linecap':'round', 'stroke-linejoin':'round' }, [h('path',{d:'M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2'}), h('circle',{cx:9,cy:7,r:4}), h('path',{d:'M23 21v-2a4 4 0 0 0-3-3.87'}), h('path',{d:'M16 3.13a4 4 0 0 1 0 7.75'})])
const IconLayoutGrid   = () => h('svg', { width:18, height:18, viewBox:'0 0 24 24', fill:'none', stroke:'currentColor', 'stroke-width':2, 'stroke-linecap':'round', 'stroke-linejoin':'round' }, [h('rect',{x:3,y:3,width:7,height:7}), h('rect',{x:14,y:3,width:7,height:7}), h('rect',{x:14,y:14,width:7,height:7}), h('rect',{x:3,y:14,width:7,height:7})])
const IconCalendar     = () => h('svg', { width:18, height:18, viewBox:'0 0 24 24', fill:'none', stroke:'currentColor', 'stroke-width':2, 'stroke-linecap':'round', 'stroke-linejoin':'round' }, [h('rect',{x:3,y:4,width:18,height:18,rx:2}), h('line',{x1:16,y1:2,x2:16,y2:6}), h('line',{x1:8,y1:2,x2:8,y2:6}), h('line',{x1:3,y1:10,x2:21,y2:10})])
const IconBriefcase    = () => h('svg', { width:18, height:18, viewBox:'0 0 24 24', fill:'none', stroke:'currentColor', 'stroke-width':2, 'stroke-linecap':'round', 'stroke-linejoin':'round' }, [h('rect',{x:2,y:7,width:20,height:14,rx:2}), h('path',{d:'M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16'})])
const IconMail         = () => h('svg', { width:18, height:18, viewBox:'0 0 24 24', fill:'none', stroke:'currentColor', 'stroke-width':2, 'stroke-linecap':'round', 'stroke-linejoin':'round' }, [h('path',{d:'M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z'}), h('polyline',{points:'22,6 12,13 2,6'})])
const IconPhone        = () => h('svg', { width:18, height:18, viewBox:'0 0 24 24', fill:'none', stroke:'currentColor', 'stroke-width':2, 'stroke-linecap':'round', 'stroke-linejoin':'round' }, [h('path',{d:'M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72c.127.96.361 1.903.7 2.81a2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45c.907.339 1.85.573 2.81.7A2 2 0 0 1 22 16.92z'})])
const IconClock        = () => h('svg', { width:18, height:18, viewBox:'0 0 24 24', fill:'none', stroke:'currentColor', 'stroke-width':2, 'stroke-linecap':'round', 'stroke-linejoin':'round' }, [h('circle',{cx:12,cy:12,r:10}), h('polyline',{points:'12 6 12 12 16 14'})])
const IconMapPin       = () => h('svg', { width:18, height:18, viewBox:'0 0 24 24', fill:'none', stroke:'currentColor', 'stroke-width':2, 'stroke-linecap':'round', 'stroke-linejoin':'round' }, [h('path',{d:'M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z'}), h('circle',{cx:12,cy:10,r:3})])
const IconCheck        = () => h('svg', { width:18, height:18, viewBox:'0 0 24 24', fill:'none', stroke:'currentColor', 'stroke-width':2, 'stroke-linecap':'round', 'stroke-linejoin':'round' }, [h('polyline',{points:'20 6 9 17 4 12'})])
const IconX            = () => h('svg', { width:18, height:18, viewBox:'0 0 24 24', fill:'none', stroke:'currentColor', 'stroke-width':2, 'stroke-linecap':'round', 'stroke-linejoin':'round' }, [h('line',{x1:18,y1:6,x2:6,y2:18}), h('line',{x1:6,y1:6,x2:18,y2:18})])
const IconSearch       = () => h('svg', { width:18, height:18, viewBox:'0 0 24 24', fill:'none', stroke:'currentColor', 'stroke-width':2, 'stroke-linecap':'round', 'stroke-linejoin':'round' }, [h('circle',{cx:11,cy:11,r:8}), h('line',{x1:21,y1:21,x2:16.65,y2:16.65})])
const IconAddressBook  = () => h('svg', { width:18, height:18, viewBox:'0 0 24 24', fill:'none', stroke:'currentColor', 'stroke-width':2, 'stroke-linecap':'round', 'stroke-linejoin':'round' }, [h('path',{d:'M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2'}), h('circle',{cx:12,cy:7,r:4})])
const IconChevronRight = () => h('svg', { width:14, height:14, viewBox:'0 0 24 24', fill:'none', stroke:'currentColor', 'stroke-width':2, 'stroke-linecap':'round', 'stroke-linejoin':'round' }, [h('polyline',{points:'9 18 15 12 9 6'})])
const IconChevronLeft  = () => h('svg', { width:14, height:14, viewBox:'0 0 24 24', fill:'none', stroke:'currentColor', 'stroke-width':2, 'stroke-linecap':'round', 'stroke-linejoin':'round' }, [h('polyline',{points:'15 18 9 12 15 6'})])
const IconTrendUp      = () => h('svg', { width:12, height:12, viewBox:'0 0 24 24', fill:'none', stroke:'currentColor', 'stroke-width':2, 'stroke-linecap':'round', 'stroke-linejoin':'round' }, [h('polyline',{points:'23 6 13.5 15.5 8.5 10.5 1 18'}), h('polyline',{points:'17 6 23 6 23 12'})])
const IconTrendDown    = () => h('svg', { width:12, height:12, viewBox:'0 0 24 24', fill:'none', stroke:'currentColor', 'stroke-width':2, 'stroke-linecap':'round', 'stroke-linejoin':'round' }, [h('polyline',{points:'23 18 13.5 8.5 8.5 13.5 1 6'}), h('polyline',{points:'17 18 23 18 23 12'})])
</script>

<style scoped>
/* ================================================================
   MEMBER DASHBOARD STYLES
   ================================================================ */

.md-quick-row {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
  margin-bottom: 24px;
}

.md-quick-card {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 18px 20px;
  background: var(--dk-surface);
  border: 1px solid var(--dk-border);
  border-radius: 12px;
  text-align: left;
  cursor: pointer;
  transition: all var(--dk-med);
  box-shadow: var(--dk-shadow-xs);
}
.md-quick-card:hover {
  border-color: var(--dk-border-strong);
  box-shadow: var(--dk-shadow-sm);
  transform: translateY(-1px);
}
.md-quick-card--highlight {
  border-color: var(--dk-accent);
  background: linear-gradient(135deg, rgba(212,162,76,.06) 0%, var(--dk-surface) 100%);
}
.md-quick-card--highlight:hover {
  border-color: var(--dk-accent-d);
  box-shadow: 0 4px 12px rgba(212,162,76,.15);
}

.md-quick-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  border-radius: 10px;
  background: var(--dk-brand-50);
  color: var(--dk-brand-500);
  flex-shrink: 0;
}
.md-quick-card--highlight .md-quick-icon {
  background: rgba(212,162,76,.15);
  color: var(--dk-accent-d);
}

.md-quick-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--dk-text);
}
.md-quick-desc {
  font-size: 12px;
  color: var(--dk-text-muted);
  margin-top: 2px;
}

/* Dashboard Grid */
.md-dashboard-grid {
  display: grid;
  grid-template-columns: 1fr 380px;
  gap: 24px;
  align-items: start;
}

.md-col {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.md-panel {
  overflow: hidden;
}

/* Anstehende Dienste */
.md-dienst-list {
  padding: 4px 0;
}
.md-dienst-item {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 14px 20px;
  cursor: pointer;
  transition: background var(--dk-fast);
  border-bottom: 1px solid var(--dk-divider);
}
.md-dienst-item:last-child {
  border-bottom: none;
}
.md-dienst-item:hover {
  background: var(--dk-surface-hover);
}

.md-dienst-date {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  width: 48px;
  height: 48px;
  border-radius: 10px;
  background: var(--dk-brand-50);
  color: var(--dk-brand-500);
  flex-shrink: 0;
}
.md-dienst-day {
  font-size: 18px;
  font-weight: 700;
  line-height: 1;
}
.md-dienst-month {
  font-size: 10px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-top: 2px;
}

.md-dienst-body {
  flex: 1;
  min-width: 0;
}
.md-dienst-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--dk-text);
}
.md-dienst-meta {
  display: flex;
  gap: 12px;
  margin-top: 4px;
  font-size: 12px;
  color: var(--dk-text-muted);
}
.md-dienst-meta span {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.md-dienst-status {
  font-size: 11px;
  font-weight: 600;
  padding: 4px 10px;
  border-radius: 999px;
  flex-shrink: 0;
}
.status-confirmed {
  background: rgba(22, 163, 74, .10);
  color: var(--dk-success);
}
.status-pending {
  background: rgba(217, 119, 6, .10);
  color: var(--dk-warning);
}

/* Dienstmöglichkeiten */
.md-anfragen-list {
  padding: 4px 0;
}
.md-anfrage-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 14px 20px;
  border-bottom: 1px solid var(--dk-divider);
}
.md-anfrage-item:last-child {
  border-bottom: none;
}

.md-anfrage-info {
  flex: 1;
  min-width: 0;
}
.md-anfrage-title {
  font-size: 14px;
  font-weight: 500;
  color: var(--dk-text);
}
.md-anfrage-meta {
  display: flex;
  gap: 8px;
  margin-top: 4px;
  font-size: 12px;
  color: var(--dk-text-muted);
}

.md-anfrage-actions {
  display: flex;
  gap: 6px;
  flex-shrink: 0;
}
.md-btn-accept, .md-btn-decline {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 6px 12px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  transition: all var(--dk-fast);
  border: none;
}
.md-btn-accept {
  background: rgba(22, 163, 74, .10);
  color: var(--dk-success);
}
.md-btn-accept:hover {
  background: var(--dk-success);
  color: #fff;
}
.md-btn-decline {
  background: transparent;
  color: var(--dk-text-subtle);
  border: 1px solid var(--dk-border);
}
.md-btn-decline:hover {
  background: var(--dk-surface-hover);
  color: var(--dk-danger);
  border-color: var(--dk-danger);
}

/* Mini Kalender */
.md-calendar {
  padding: 16px 20px 20px;
}
.md-cal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}
.md-cal-month {
  font-size: 14px;
  font-weight: 600;
  color: var(--dk-text);
}
.md-cal-nav {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 6px;
  border: none;
  background: var(--dk-surface-2);
  color: var(--dk-text-muted);
  cursor: pointer;
  transition: all var(--dk-fast);
}
.md-cal-nav:hover {
  background: var(--dk-surface-hover);
  color: var(--dk-text);
}

.md-cal-weekdays {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 2px;
  margin-bottom: 4px;
}
.md-cal-weekdays span {
  text-align: center;
  font-size: 10px;
  font-weight: 600;
  color: var(--dk-text-subtle);
  text-transform: uppercase;
  padding: 4px 0;
}

.md-cal-days {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 2px;
}
.md-cal-day {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border-radius: 8px;
  font-size: 12px;
  font-weight: 500;
  color: var(--dk-text);
  cursor: pointer;
  transition: all var(--dk-fast);
  position: relative;
}
.md-cal-day:hover {
  background: var(--dk-surface-hover);
}
.md-cal-day.is-other {
  color: var(--dk-text-subtle);
}
.md-cal-day.is-today {
  background: var(--dk-brand-500);
  color: #fff;
  font-weight: 600;
}
.md-cal-day.has-event::after {
  content: '';
  position: absolute;
  bottom: 4px;
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: var(--dk-accent);
}
.md-cal-day.is-today.has-event::after {
  background: #fff;
}

.md-cal-legend {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--dk-divider);
}
.md-cal-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
}

/* Kontaktliste */
.md-kontakt-search {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 14px;
  margin: 8px 16px 4px;
  background: var(--dk-surface-2);
  border: 1px solid var(--dk-border);
  border-radius: 8px;
  transition: border-color var(--dk-fast);
}
.md-kontakt-search:focus-within {
  border-color: var(--dk-border-strong);
}
.md-kontakt-search input {
  flex: 1;
  border: none;
  background: transparent;
  font-size: 13px;
  color: var(--dk-text);
  outline: none;
}
.md-kontakt-search input::placeholder {
  color: var(--dk-text-subtle);
}

.md-kontakt-list {
  padding: 4px 0;
}
.md-kontakt-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 16px;
  cursor: pointer;
  transition: background var(--dk-fast);
}
.md-kontakt-item:hover {
  background: var(--dk-surface-hover);
}

.md-kontakt-info {
  flex: 1;
  min-width: 0;
}
.md-kontakt-name {
  font-size: 13px;
  font-weight: 500;
  color: var(--dk-text);
}
.md-kontakt-role {
  font-size: 11px;
  color: var(--dk-text-muted);
  margin-top: 1px;
}

.md-kontakt-actions {
  display: flex;
  gap: 2px;
  opacity: 0;
  transition: opacity var(--dk-fast);
}
.md-kontakt-item:hover .md-kontakt-actions {
  opacity: 1;
}
.md-kontakt-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 6px;
  color: var(--dk-text-muted);
  text-decoration: none;
  transition: all var(--dk-fast);
}
.md-kontakt-btn:hover {
  background: var(--dk-surface-2);
  color: var(--dk-brand-500);
}

/* Responsive */
@media (max-width: 1100px) {
  .md-dashboard-grid {
    grid-template-columns: 1fr;
  }
  .md-col--right {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 24px;
  }
}
@media (max-width: 768px) {
  .md-quick-row {
    grid-template-columns: 1fr;
  }
  .md-col--right {
    grid-template-columns: 1fr;
  }
  .md-anfrage-item {
    flex-direction: column;
    align-items: flex-start;
    gap: 10px;
  }
  .md-kontakt-actions {
    opacity: 1;
  }
}
</style>
