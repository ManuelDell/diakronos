<template>
  <div class="dk-screen dk-screen-enter">
    <div class="dk-screen-header">
      <div>
        <h1 class="dk-screen-title">Registrierung</h1>
        <p class="dk-screen-sub">Anmeldungen, Links & Formulare verwalten</p>
      </div>
    </div>

    <!-- Stats -->
    <div class="dk-stats-row" style="margin-bottom:24px">
      <div class="dk-card dk-stat-card">
        <div class="dk-stat-label">Anmeldungen</div>
        <div class="dk-stat-value">{{ stats.anmeldungen }}</div>
      </div>
      <div class="dk-card dk-stat-card">
        <div class="dk-stat-label">Links</div>
        <div class="dk-stat-value">{{ stats.links }}</div>
      </div>
      <div class="dk-card dk-stat-card">
        <div class="dk-stat-label">Formulare</div>
        <div class="dk-stat-value">{{ stats.formulare }}</div>
      </div>
    </div>

    <!-- Tabs -->
    <div class="dk-tabs" style="margin-bottom:20px">
      <button
        v-for="t in tabs"
        :key="t.id"
        class="dk-tab"
        :class="{ 'is-active': activeTab === t.id }"
        @click="activeTab = t.id"
      >
        {{ t.label }}
      </button>
    </div>

    <!-- TAB 1: Anmeldungen -->
    <div v-if="activeTab === 'anmeldungen'">
      <div class="dk-filter-bar" style="margin-bottom:16px">
        <button
          v-for="f in anmeldungFilters"
          :key="f.value"
          class="dk-filter-chip"
          :class="{ 'is-active': filterStatus === f.value }"
          @click="filterStatus = f.value"
        >
          {{ f.label }}
        </button>
      </div>

      <div v-if="loading" class="dk-skeleton-loader">
        <div class="dk-skeleton-row" v-for="n in 5" :key="n"><div class="dk-skeleton-cell" style="width:100%"></div></div>
      </div>

      <div v-else-if="filteredAnmeldungen.length === 0" class="dk-list-empty">
        <p>Keine Anmeldungen gefunden.</p>
      </div>

      <div v-else class="dk-card" style="padding:0;overflow:hidden">
        <table class="dk-table">
          <thead>
            <tr>
              <th>Datum</th>
              <th>Name</th>
              <th>Typ</th>
              <th>Status</th>
              <th style="width:160px">Aktionen</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="a in filteredAnmeldungen" :key="a.name">
              <td class="whitespace-nowrap">{{ formatDate(a.anmeldedatum) }}</td>
              <td>{{ a.vorname }} {{ a.nachname }}</td>
              <td>{{ a.anmeldungstyp }}</td>
              <td><span :class="statusBadgeClass(a.status)">{{ a.status }}</span></td>
              <td>
                <div class="dk-row-actions">
                  <button v-if="a.status === 'Anmeldeanfrage' || a.status === 'Ausstehend'"
                    class="dk-btn dk-btn-sm dk-btn-success" @click="genehmigen(a.name)"
                    :disabled="processing[a.name]">
                    <IconCheck style="width:12px;height:12px" /> Genehmigen
                  </button>
                  <button v-if="a.status === 'Anmeldeanfrage' || a.status === 'Ausstehend'"
                    class="dk-btn dk-btn-sm dk-btn-danger" @click="ablehnen(a.name)"
                    :disabled="processing[a.name]">
                    <IconX style="width:12px;height:12px" /> Ablehnen
                  </button>
                  <button class="dk-btn dk-btn-sm dk-btn-secondary" @click="showDetail(a)">Details</button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- TAB 2: Links -->
    <div v-if="activeTab === 'links'">
      <div class="dk-screen-actions" style="margin-bottom:20px">
        <button class="dk-btn dk-btn-primary" @click="showCreateLink = true">
          <IconPlus style="width:14px;height:14px" /> Neuer Link
        </button>
      </div>

      <div v-if="loadingLinks" class="dk-skeleton-loader">
        <div class="dk-skeleton-row" v-for="n in 3" :key="n"><div class="dk-skeleton-cell" style="width:100%"></div></div>
      </div>

      <div v-else-if="links.length === 0" class="dk-list-empty">
        <p>Keine Registrierungslinks vorhanden.</p>
      </div>

      <div v-else class="dk-grid-3">
        <div class="dk-card dk-link-card" v-for="l in links" :key="l.name">
          <div class="dk-link-header">
            <h4 class="dk-link-title">{{ l.bezeichnung }}</h4>
            <span class="dk-badge" :class="l.aktiv ? 'dk-badge-success' : 'dk-badge-muted'">
              {{ l.aktiv ? 'aktiv' : 'inaktiv' }}
            </span>
          </div>
          <div class="dk-link-meta">
            <span class="dk-link-type">{{ l.typ }}</span>
            <span class="dk-link-count">{{ l.anmeldungen_count }} Anm.</span>
          </div>
          <div v-if="l.gueltig_bis" class="dk-link-expiry">Gültig bis: {{ formatDate(l.gueltig_bis) }}</div>
          <div class="dk-link-url" @click="copyLink(l.link_anzeige)">
            <IconLink style="width:12px;height:12px" />
            <span class="dk-link-url-text">{{ l.link_anzeige }}</span>
          </div>
          <div class="dk-link-actions">
            <button class="dk-btn dk-btn-sm dk-btn-secondary" @click="copyLink(l.link_anzeige)">Kopieren</button>
            <button class="dk-btn dk-btn-sm dk-btn-secondary" @click="toggleLink(l)">
              {{ l.aktiv ? 'Deaktivieren' : 'Aktivieren' }}
            </button>
            <button class="dk-btn dk-btn-sm dk-btn-danger" @click="deleteLink(l.name)">Löschen</button>
          </div>
        </div>
      </div>
    </div>

    <!-- TAB 3: Formulare -->
    <div v-if="activeTab === 'formulare'">
      <div class="dk-screen-actions" style="margin-bottom:20px">
        <button class="dk-btn dk-btn-primary" @click="showCreateFormular = true">
          <IconPlus style="width:14px;height:14px" /> Neues Formular
        </button>
      </div>

      <div v-if="loadingFormulare" class="dk-skeleton-loader">
        <div class="dk-skeleton-row" v-for="n in 3" :key="n"><div class="dk-skeleton-cell" style="width:100%"></div></div>
      </div>

      <div v-else-if="formulare.length === 0" class="dk-list-empty">
        <p>Keine Anmeldeformulare vorhanden.</p>
      </div>

      <div v-else class="dk-card" style="padding:0;overflow:hidden">
        <table class="dk-table">
          <thead>
            <tr>
              <th>Bezeichnung</th>
              <th>Gäste</th>
              <th>Kinder</th>
              <th>Felder</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="f in formulare" :key="f.name">
              <td>{{ f.bezeichnung }}</td>
              <td>{{ f.mit_gaesten ? 'Ja' : 'Nein' }}</td>
              <td>{{ f.mit_kinder ? 'Ja' : 'Nein' }}</td>
              <td>–</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- MODAL: Link erstellen -->
    <Teleport to="body">
      <div v-if="showCreateLink" class="dk-modal-overlay" @click.self="showCreateLink = false">
        <div class="dk-modal" style="max-width:480px">
          <h3>Neuen Registrierungslink erstellen</h3>
          <div class="dk-form-group">
            <label>Bezeichnung *</label>
            <input v-model="newLink.bezeichnung" class="dk-input" placeholder="z. B. Gemeindefest 2026" />
          </div>
          <div class="dk-form-group">
            <label>Typ *</label>
            <select v-model="newLink.typ" class="dk-input">
              <option value="Mitglied-Registrierung">Mitglied-Registrierung</option>
              <option value="Gast-Anmeldung">Gast-Anmeldung</option>
              <option value="Veranstaltung">Veranstaltung</option>
            </select>
          </div>
          <div class="dk-form-group">
            <label>Gültig bis</label>
            <input v-model="newLink.gueltig_bis" type="date" class="dk-input" />
          </div>
          <div class="dk-form-group">
            <label>Max. Anmeldungen (0 = unbegrenzt)</label>
            <input v-model.number="newLink.max_anmeldungen" type="number" class="dk-input" min="0" />
          </div>
          <div class="dk-form-group">
            <label>Anmeldeformular</label>
            <select v-model="newLink.anmeldeformular_id" class="dk-input">
              <option value="">– Keines –</option>
              <option v-for="f in formulare" :key="f.name" :value="f.name">{{ f.bezeichnung }}</option>
            </select>
          </div>
          <div class="dk-modal-actions">
            <button class="dk-btn dk-btn-secondary" @click="showCreateLink = false">Abbrechen</button>
            <button class="dk-btn dk-btn-primary" @click="createLink" :disabled="!newLink.bezeichnung || !newLink.typ">Erstellen</button>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- MODAL: Formular erstellen -->
    <Teleport to="body">
      <div v-if="showCreateFormular" class="dk-modal-overlay" @click.self="showCreateFormular = false">
        <div class="dk-modal" style="max-width:480px">
          <h3>Neues Anmeldeformular</h3>
          <div class="dk-form-group">
            <label>Bezeichnung *</label>
            <input v-model="newFormular.bezeichnung" class="dk-input" placeholder="z. B. Standard-Anmeldung" />
          </div>
          <div class="dk-form-group" style="display:flex;gap:16px">
            <label style="display:flex;align-items:center;gap:6px;cursor:pointer">
              <input v-model="newFormular.mit_gaesten" type="checkbox" /> Mit Gästen
            </label>
            <label style="display:flex;align-items:center;gap:6px;cursor:pointer">
              <input v-model="newFormular.mit_kinder" type="checkbox" /> Mit Kinder-Option
            </label>
          </div>

          <!-- Felder-Builder -->
          <div class="cm-felder-section" style="margin-top:12px">
            <div class="cm-felder-header" style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">
              <span style="font-size:13px;font-weight:600;color:var(--dk-text)">Felder</span>
              <button type="button" class="dk-btn dk-btn-sm dk-btn-secondary" @click="addFeld">+ Feld</button>
            </div>
            <div v-for="(f, i) in formularFelder" :key="i" class="cm-feld-row" style="display:grid;grid-template-columns:1fr 120px 60px 28px;gap:8px;align-items:center;margin-bottom:8px">
              <input v-model="f.label" placeholder="Bezeichnung *" class="dk-input" style="font-size:13px" />
              <select v-model="f.feldtyp" class="dk-input" style="font-size:13px">
                <option v-for="t in feldTypen" :value="t">{{ t }}</option>
              </select>
              <label style="display:flex;align-items:center;gap:4px;font-size:12px;cursor:pointer;color:var(--dk-text-muted)">
                <input type="checkbox" v-model="f.pflichtfeld" /> Pflicht
              </label>
              <button type="button" class="dk-btn dk-btn-sm dk-btn-danger" @click="formularFelder.splice(i,1)" style="padding:2px 6px">×</button>
            </div>
          </div>

          <div class="dk-modal-actions">
            <button class="dk-btn dk-btn-secondary" @click="showCreateFormular = false">Abbrechen</button>
            <button class="dk-btn dk-btn-primary" @click="createFormular" :disabled="!newFormular.bezeichnung">Erstellen</button>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- MODAL: Anmeldung Detail -->
    <Teleport to="body">
      <div v-if="detailAnmeldung" class="dk-modal-overlay" @click.self="detailAnmeldung = null">
        <div class="dk-modal" style="max-width:560px">
          <h3>Anmeldung {{ detailAnmeldung.name }}</h3>
          <div class="dk-detail-grid">
            <div><strong>Name:</strong> {{ detailAnmeldung.vorname }} {{ detailAnmeldung.nachname }}</div>
            <div><strong>E-Mail:</strong> {{ detailAnmeldung.email || '–' }}</div>
            <div><strong>Telefon:</strong> {{ detailAnmeldung.telefon || '–' }}</div>
            <div><strong>Typ:</strong> {{ detailAnmeldung.anmeldungstyp }}</div>
            <div><strong>Status:</strong> <span :class="statusBadgeClass(detailAnmeldung.status)">{{ detailAnmeldung.status }}</span></div>
            <div><strong>Datum:</strong> {{ formatDate(detailAnmeldung.anmeldedatum) }}</div>
            <div v-if="detailAnmeldung.kommentar"><strong>Kommentar:</strong> {{ detailAnmeldung.kommentar }}</div>
          </div>

          <!-- Antworten (Custom-Felder) -->
          <div v-if="detailAnmeldung.antworten?.length" class="detail-section" style="margin:16px 0">
            <h4 style="font-size:14px;font-weight:600;margin-bottom:8px;color:var(--dk-text)">Formular-Antworten</h4>
            <dl style="display:grid;grid-template-columns:auto 1fr;gap:6px 16px;font-size:13px">
              <template v-for="a in detailAnmeldung.antworten" :key="a.label">
                <dt style="color:var(--dk-text-muted)">{{ a.label }}</dt>
                <dd style="color:var(--dk-text);margin:0">{{ a.wert || '–' }}</dd>
              </template>
            </dl>
          </div>

          <!-- Kinder -->
          <div v-if="detailAnmeldung.kinder?.length" class="detail-section" style="margin:16px 0">
            <h4 style="font-size:14px;font-weight:600;margin-bottom:8px;color:var(--dk-text)">Angemeldete Kinder</h4>
            <ul style="list-style:none;padding:0;margin:0;font-size:13px">
              <li v-for="k in detailAnmeldung.kinder" :key="k.vorname" style="padding:4px 0;border-bottom:1px solid var(--dk-border)">
                {{ k.vorname }} {{ k.nachname }}<span v-if="k.geburtstag" style="color:var(--dk-text-muted)"> ({{ k.geburtstag }})</span>
              </li>
            </ul>
          </div>

          <div class="dk-modal-actions">
            <button class="dk-btn dk-btn-secondary" @click="detailAnmeldung = null">Schließen</button>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- Toast -->
    <div v-if="toast" class="dk-toast" :class="toast.type">{{ toast.message }}</div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, h } from 'vue'
import { apiCall } from '../composables/useApi.js'

const tabs = [
  { id: 'anmeldungen', label: 'Anmeldungen' },
  { id: 'links',       label: 'Links' },
  { id: 'formulare',   label: 'Formulare' },
]
const activeTab = ref('anmeldungen')

const loading = ref(true)
const loadingLinks = ref(true)
const loadingFormulare = ref(true)
const anmeldungen = ref([])
const links = ref([])
const formulare = ref([])
const filterStatus = ref('alle')
const processing = ref({})
const toast = ref(null)

const anmeldungFilters = [
  { value: 'alle',       label: 'Alle' },
  { value: 'Anmeldeanfrage', label: 'Offen' },
  { value: 'Bestätigt',  label: 'Bestätigt' },
  { value: 'Abgelehnt',  label: 'Abgelehnt' },
]

const stats = computed(() => ({
  anmeldungen: anmeldungen.value.length,
  links: links.value.length,
  formulare: formulare.value.length,
}))

const filteredAnmeldungen = computed(() => {
  if (filterStatus.value === 'alle') return anmeldungen.value
  if (filterStatus.value === 'Offen') return anmeldungen.value.filter(a => a.status === 'Anmeldeanfrage' || a.status === 'Ausstehend')
  return anmeldungen.value.filter(a => a.status === filterStatus.value)
})

function showToast(message, type = 'success') {
  toast.value = { message, type }
  setTimeout(() => toast.value = null, 3000)
}

async function fetchData() {
  loading.value = true
  loadingLinks.value = true
  loadingFormulare.value = true
  try {
    const res = await apiCall('diakronos.diakonos.api.admin_hub.get_anmeldungen_hub')
    anmeldungen.value = res.anmeldungen || []
    links.value = res.links || []
  } catch (err) {
    console.error(err)
    showToast('Fehler beim Laden', 'error')
  } finally {
    loading.value = false
    loadingLinks.value = false
  }

  try {
    const fRes = await apiCall('diakronos.diakonos.api.admin_hub.get_anmeldeformulare')
    formulare.value = fRes.formulare || []
  } catch (err) {
    console.error(err)
  } finally {
    loadingFormulare.value = false
  }
}

async function genehmigen(id) {
  processing.value[id] = true
  try {
    const res = await apiCall('diakronos.diakonos.api.admin_hub.genehmige_anmeldung', { anmeldung_id: id })
    if (res.success) {
      showToast('Anmeldung genehmigt')
      await fetchData()
    }
  } catch (err) {
    showToast(err?.message || 'Fehler', 'error')
  } finally {
    processing.value[id] = false
  }
}

async function ablehnen(id) {
  const grund = prompt('Grund für die Ablehnung (optional):')
  if (grund === null) return
  processing.value[id] = true
  try {
    const res = await apiCall('diakronos.diakonos.api.admin_hub.lehne_anmeldung_ab', { anmeldung_id: id, grund })
    if (res.success) {
      showToast('Anmeldung abgelehnt')
      await fetchData()
    }
  } catch (err) {
    showToast(err?.message || 'Fehler', 'error')
  } finally {
    processing.value[id] = false
  }
}

const showCreateLink = ref(false)
const newLink = ref({ bezeichnung: '', typ: 'Mitglied-Registrierung', gueltig_bis: '', max_anmeldungen: 0, anmeldeformular_id: '' })

async function createLink() {
  try {
    const res = await apiCall('diakronos.diakonos.api.registrierungslink_api.create_link', newLink.value)
    if (res.success) {
      showToast('Link erstellt')
      showCreateLink.value = false
      newLink.value = { bezeichnung: '', typ: 'Mitglied-Registrierung', gueltig_bis: '', max_anmeldungen: 0, anmeldeformular_id: '' }
      await fetchData()
    }
  } catch (err) {
    showToast(err?.message || 'Fehler', 'error')
  }
}

async function toggleLink(l) {
  try {
    const res = await apiCall('diakronos.diakonos.api.registrierungslink_api.toggle_link', { link_id: l.name })
    if (res.success) {
      l.aktiv = res.aktiv ? 1 : 0
      showToast(l.aktiv ? 'Link aktiviert' : 'Link deaktiviert')
    }
  } catch (err) {
    showToast(err?.message || 'Fehler', 'error')
  }
}

async function deleteLink(id) {
  if (!confirm('Link wirklich löschen? Alle ausstehenden Anmeldungen werden ebenfalls gelöscht.')) return
  try {
    const res = await apiCall('diakronos.diakonos.api.registrierungslink_api.delete_link', { link_id: id })
    if (res.success) {
      showToast('Link gelöscht')
      await fetchData()
    }
  } catch (err) {
    showToast(err?.message || 'Fehler', 'error')
  }
}

const showCreateFormular = ref(false)
const newFormular = ref({ bezeichnung: '', mit_gaesten: false, mit_kinder: false })
const formularFelder = ref([])
const feldTypen = ['Text', 'Zahl', 'Datum', 'Ja-Nein', 'Auswahl']

function addFeld() {
    formularFelder.value.push({ label: '', feldtyp: 'Text', pflichtfeld: false, fuer_gaeste: false, fuer_kinder: false })
}

async function createFormular() {
  try {
    const res = await apiCall('diakronos.diakonos.api.admin_hub.create_anmeldeformular', {
      bezeichnung: newFormular.value.bezeichnung,
      mit_gaesten: newFormular.value.mit_gaesten ? 1 : 0,
      mit_kinder: newFormular.value.mit_kinder ? 1 : 0,
    })
    if (res.success) {
      // Felder speichern wenn vorhanden
      if (formularFelder.value.length > 0) {
        const cleanFelder = formularFelder.value.map(f => ({
          label: f.label,
          feldtyp: f.feldtyp,
          optionen: f.optionen || '',
          pflichtfeld: f.pflichtfeld ? 1 : 0,
          fuer_gaeste: f.fuer_gaeste ? 1 : 0,
          fuer_kinder: f.fuer_kinder ? 1 : 0,
        }))
        await apiCall('diakronos.diakonos.api.admin_hub.update_anmeldeformular_felder', {
          formular_id: res.id,
          felder_json: JSON.stringify(cleanFelder),
        })
      }
      showToast('Formular erstellt')
      showCreateFormular.value = false
      newFormular.value = { bezeichnung: '', mit_gaesten: false, mit_kinder: false }
      formularFelder.value = []
      await fetchData()
    }
  } catch (err) {
    showToast(err?.message || 'Fehler', 'error')
  }
}

const detailAnmeldung = ref(null)
function showDetail(a) { detailAnmeldung.value = a }

function copyLink(url) {
  navigator.clipboard.writeText(url).then(() => showToast('Link kopiert'))
}

function formatDate(dateStr) {
  if (!dateStr) return '–'
  const d = new Date(dateStr)
  if (isNaN(d)) return dateStr
  return d.toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit', year: 'numeric' })
}

function statusBadgeClass(status) {
  const map = {
    'Bestätigt': 'dk-badge dk-badge-success',
    'Ausstehend': 'dk-badge dk-badge-warning',
    'Anmeldeanfrage': 'dk-badge dk-badge-warning',
    'Abgelehnt': 'dk-badge dk-badge-danger',
    'Warteliste': 'dk-badge dk-badge-info',
  }
  return map[status] || 'dk-badge'
}

// Icons
const IconPlus  = () => h('svg', { width:14, height:14, viewBox:'0 0 24 24', fill:'none', stroke:'currentColor', 'stroke-width':2, 'stroke-linecap':'round', 'stroke-linejoin':'round' }, [h('line',{x1:12,y1:5,x2:12,y2:19}), h('line',{x1:5,y1:12,x2:19,y2:12})])
const IconCheck = () => h('svg', { width:14, height:14, viewBox:'0 0 24 24', fill:'none', stroke:'currentColor', 'stroke-width':2, 'stroke-linecap':'round', 'stroke-linejoin':'round' }, [h('polyline',{points:'20 6 9 17 4 12'})])
const IconX     = () => h('svg', { width:14, height:14, viewBox:'0 0 24 24', fill:'none', stroke:'currentColor', 'stroke-width':2, 'stroke-linecap':'round', 'stroke-linejoin':'round' }, [h('line',{x1:18,y1:6,x2:6,y2:18}), h('line',{x1:6,y1:6,x2:18,y2:18})])
const IconLink  = () => h('svg', { width:14, height:14, viewBox:'0 0 24 24', fill:'none', stroke:'currentColor', 'stroke-width':2, 'stroke-linecap':'round', 'stroke-linejoin':'round' }, [h('path',{d:'M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71'}), h('path',{d:'M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71'})])

onMounted(fetchData)
</script>

<style scoped>
.dk-tabs { display:flex; gap:4px; border-bottom:1px solid var(--dk-border); }
.dk-tab { padding:10px 18px; border:none; background:transparent; color:var(--dk-text-muted); cursor:pointer; font-size:14px; border-bottom:2px solid transparent; transition:all .15s; }
.dk-tab:hover { color:var(--dk-text); }
.dk-tab.is-active { color:var(--dk-primary); border-bottom-color:var(--dk-primary); font-weight:600; }

.dk-filter-bar { display:flex; gap:8px; flex-wrap:wrap; }
.dk-filter-chip { padding:6px 14px; border-radius:99px; border:1px solid var(--dk-border); background:var(--dk-surface); color:var(--dk-text-muted); font-size:13px; cursor:pointer; transition:all .15s; }
.dk-filter-chip:hover { border-color:var(--dk-primary); color:var(--dk-primary); }
.dk-filter-chip.is-active { background:var(--dk-primary); color:#fff; border-color:var(--dk-primary); }

.dk-grid-3 { display:grid; grid-template-columns:repeat(auto-fill,minmax(300px,1fr)); gap:16px; }
.dk-link-card { padding:20px; }
.dk-link-header { display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:8px; }
.dk-link-title { font-size:16px; font-weight:600; margin:0; color:var(--dk-text); }
.dk-link-meta { display:flex; gap:12px; font-size:12px; color:var(--dk-text-muted); margin-bottom:8px; }
.dk-link-expiry { font-size:12px; color:var(--dk-danger); margin-bottom:8px; }
.dk-link-url { display:flex; align-items:center; gap:6px; padding:8px 10px; background:var(--dk-bg); border-radius:6px; cursor:pointer; margin-bottom:12px; font-size:12px; }
.dk-link-url-text { color:var(--dk-primary); overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.dk-link-actions { display:flex; gap:8px; flex-wrap:wrap; }

.dk-detail-grid { display:grid; gap:10px; font-size:14px; margin:16px 0; }
.dk-detail-grid div { color:var(--dk-text); }

.dk-row-actions { display:flex; gap:6px; flex-wrap:wrap; }

.dk-toast { position:fixed; bottom:24px; right:24px; padding:12px 20px; border-radius:8px; color:#fff; font-size:14px; z-index:9999; animation:slideIn .3s ease; }
.dk-toast.success { background:var(--dk-success); }
.dk-toast.error { background:var(--dk-danger); }
@keyframes slideIn { from { transform:translateY(20px); opacity:0; } to { transform:translateY(0); opacity:1; } }
</style>
