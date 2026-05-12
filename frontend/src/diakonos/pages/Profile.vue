<template>
  <div class="dk-screen dk-screen-enter">

    <!-- Header -->
    <div class="dk-screen-header" style="margin-bottom:0">
      <div>
        <h1>Mein Profil</h1>
        <p class="dk-text-muted">Persönliche Daten, Sichtbarkeit & Datenschutz</p>
      </div>
    </div>

    <div v-if="loading" class="prof-loading">
      <div class="dk-skeleton-line" style="width:60px;height:60px;border-radius:50%"></div>
      <div style="flex:1"><div class="dk-skeleton-line" style="width:40%"></div></div>
    </div>

    <div v-else-if="error" class="dk-widget-error" style="margin-top:24px">{{ error }}</div>

    <div v-else class="prof-layout">

      <!-- ── Avatar-Karte ── -->
      <div class="prof-card prof-avatar-card">
        <div class="prof-avatar-wrap" @click="openCropModal">
          <div class="prof-avatar" :style="avatarStyle">
            <img v-if="profile.foto" :src="profile.foto" alt="Foto" />
            <span v-else>{{ initials }}</span>
          </div>
          <div class="prof-avatar-overlay">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/><circle cx="12" cy="13" r="4"/></svg>
          </div>
        </div>
        <div class="prof-avatar-info">
          <div class="prof-avatar-name">{{ profile.vorname }} {{ profile.nachname }}</div>
          <div class="prof-avatar-email dk-text-muted">{{ profile.email }}</div>
        </div>
      </div>

      <!-- ── Persönliche Daten ── -->
      <div class="prof-card">
        <div class="prof-card-header">
          <h3>Persönliche Daten</h3>
          <button v-if="!editingData" class="dk-btn dk-btn-ghost dk-btn-sm" @click="startEdit">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
            Bearbeiten
          </button>
          <div v-else style="display:flex;gap:8px">
            <button class="dk-btn dk-btn-ghost dk-btn-sm" @click="cancelEdit">Abbrechen</button>
            <button class="dk-btn dk-btn-primary dk-btn-sm" :disabled="saving" @click="saveData">
              {{ saving ? 'Speichern…' : 'Speichern' }}
            </button>
          </div>
        </div>

        <div class="prof-fields" :class="{ 'is-editing': editingData }">
          <div class="prof-field-row">
            <div class="prof-field">
              <label>Vorname</label>
              <input v-if="editingData" v-model="form.vorname" class="dk-form-input" />
              <span v-else>{{ profile.vorname || '—' }}</span>
            </div>
            <div class="prof-field">
              <label>Nachname</label>
              <input v-if="editingData" v-model="form.nachname" class="dk-form-input" />
              <span v-else>{{ profile.nachname || '—' }}</span>
            </div>
          </div>
          <div class="prof-field-row">
            <div class="prof-field">
              <label>Geburtstag</label>
              <input v-if="editingData" v-model="form.geburtstag" type="date" class="dk-form-input" />
              <span v-else>{{ profile.geburtstag ? formatDate(profile.geburtstag) : '—' }}</span>
            </div>
            <div class="prof-field">
              <label>Geschlecht</label>
              <select v-if="editingData" v-model="form.geschlecht" class="dk-form-input">
                <option value="">—</option>
                <option>Männlich</option>
                <option>Weiblich</option>
                <option>Divers</option>
              </select>
              <span v-else>{{ profile.geschlecht || '—' }}</span>
            </div>
          </div>
          <div class="prof-field-row">
            <div class="prof-field">
              <label>Telefon</label>
              <input v-if="editingData" v-model="form.telefonnummer" type="tel" class="dk-form-input" />
              <span v-else>{{ profile.telefonnummer || '—' }}</span>
            </div>
            <div class="prof-field">
              <label>Familienstand</label>
              <select v-if="editingData" v-model="form.familienstand" class="dk-form-input">
                <option value="">—</option>
                <option>Ledig</option>
                <option>Verheiratet</option>
                <option>Verwitwet</option>
                <option>Geschieden</option>
              </select>
              <span v-else>{{ profile.familienstand || '—' }}</span>
            </div>
          </div>
          <div class="prof-field-row">
            <div class="prof-field prof-field-wide">
              <label>Straße & Nummer</label>
              <div v-if="editingData" style="display:flex;gap:8px">
                <input v-model="form.strasse" class="dk-form-input" placeholder="Straße" style="flex:1" />
                <input v-model="form.nummer" class="dk-form-input" placeholder="Nr." style="width:70px" />
              </div>
              <span v-else>{{ [profile.strasse, profile.nummer].filter(Boolean).join(' ') || '—' }}</span>
            </div>
          </div>
          <div class="prof-field-row">
            <div class="prof-field">
              <label>PLZ</label>
              <input v-if="editingData" v-model="form.postleitzahl" class="dk-form-input" />
              <span v-else>{{ profile.postleitzahl || '—' }}</span>
            </div>
            <div class="prof-field">
              <label>Wohnort</label>
              <input v-if="editingData" v-model="form.wohnort" class="dk-form-input" />
              <span v-else>{{ profile.wohnort || '—' }}</span>
            </div>
          </div>
          <!-- E-Mail ist nicht editierbar — läuft über Frappe Account -->
          <div class="prof-field-row">
            <div class="prof-field prof-field-wide">
              <label>E-Mail</label>
              <span class="dk-text-muted" style="font-size:13px">
                {{ profile.email }}
                <a href="/update-password" target="_blank" style="margin-left:8px;font-size:12px">Passwort ändern ↗</a>
              </span>
            </div>
          </div>
        </div>
      </div>

      <!-- ── Adressbuch-Sichtbarkeit ── -->
      <div class="prof-card">
        <div class="prof-card-header">
          <h3>Adressbuch-Sichtbarkeit</h3>
          <span class="dk-text-muted" style="font-size:12px">Was andere eingeloggte Mitglieder sehen dürfen</span>
        </div>
        <div class="prof-toggles">
          <div class="prof-toggle-row">
            <div class="prof-toggle-info">
              <span class="prof-toggle-label">E-Mail-Adresse</span>
              <span class="prof-toggle-desc dk-text-muted">{{ profile.email }}</span>
            </div>
            <label class="prof-switch">
              <input type="checkbox" v-model="sichtbarkeit.email" @change="saveSichtbarkeit" />
              <span class="prof-switch-track"></span>
            </label>
          </div>
          <div class="prof-toggle-row">
            <div class="prof-toggle-info">
              <span class="prof-toggle-label">Telefonnummer</span>
              <span class="prof-toggle-desc dk-text-muted">{{ profile.telefonnummer || 'Nicht angegeben' }}</span>
            </div>
            <label class="prof-switch">
              <input type="checkbox" v-model="sichtbarkeit.telefonnummer" @change="saveSichtbarkeit" />
              <span class="prof-switch-track"></span>
            </label>
          </div>
          <div class="prof-toggle-row">
            <div class="prof-toggle-info">
              <span class="prof-toggle-label">Adresse</span>
              <span class="prof-toggle-desc dk-text-muted">{{ fullAddress || 'Nicht angegeben' }}</span>
            </div>
            <label class="prof-switch">
              <input type="checkbox" v-model="sichtbarkeit.adresse" @change="saveSichtbarkeit" />
              <span class="prof-switch-track"></span>
            </label>
          </div>
          <div class="prof-toggle-row">
            <div class="prof-toggle-info">
              <span class="prof-toggle-label">Geburtstag</span>
              <span class="prof-toggle-desc dk-text-muted">{{ profile.geburtstag ? formatDate(profile.geburtstag) : 'Nicht angegeben' }}</span>
            </div>
            <label class="prof-switch">
              <input type="checkbox" v-model="sichtbarkeit.geburtstag" @change="saveSichtbarkeit" />
              <span class="prof-switch-track"></span>
            </label>
          </div>
        </div>
      </div>

      <!-- ── Datenschutz (DSGVO) ── -->
      <div class="prof-card prof-card-danger-zone">
        <div class="prof-card-header">
          <h3>Datenschutz</h3>
        </div>
        <div v-if="profile.datenschutz_einwilligung" class="prof-dsgvo-status prof-dsgvo-ok">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><polyline points="9 12 11 14 15 10"/></svg>
          <div>
            <div style="font-weight:600">Einwilligung erteilt</div>
            <div class="dk-text-muted" style="font-size:12px">{{ profile.datenschutz_datum ? `am ${formatDate(profile.datenschutz_datum)}` : '' }}</div>
          </div>
        </div>
        <div v-else class="prof-dsgvo-status prof-dsgvo-warn">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
          <div>
            <div style="font-weight:600">Keine Einwilligung</div>
            <div class="dk-text-muted" style="font-size:12px">Du hast noch keine DSGVO-Einwilligung erteilt.</div>
          </div>
        </div>

        <div class="prof-dsgvo-actions">
          <button class="dk-btn dk-btn-danger dk-btn-sm" @click="showDeleteConfirm = true">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/></svg>
            Einwilligung widerrufen & Daten löschen
          </button>
        </div>
      </div>

    </div>

    <!-- ── Crop-Modal ── -->
    <Teleport to="body">
      <div v-if="showCrop" class="prof-modal-overlay" @click.self="showCrop = false">
        <div class="prof-modal">
          <div class="prof-modal-header">
            <h3>Profilbild ändern</h3>
            <button class="dk-btn dk-btn-ghost dk-btn-sm" @click="showCrop = false">✕</button>
          </div>
          <div class="prof-crop-area">
            <Cropper
              v-if="cropSrc"
              ref="cropperRef"
              :src="cropSrc"
              :stencil-props="{ aspectRatio: 1 }"
              stencil-component="circle-stencil"
              class="prof-cropper"
            />
            <div v-else class="prof-crop-upload" @click="triggerFileInput" @dragover.prevent @drop.prevent="onFileDrop">
              <input ref="fileInput" type="file" accept="image/*" style="display:none" @change="onFileSelect" />
              <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
              <p>Bild hier ablegen oder klicken zum Auswählen</p>
            </div>
          </div>
          <div class="prof-modal-footer">
            <button v-if="cropSrc" class="dk-btn dk-btn-ghost dk-btn-sm" @click="cropSrc = null">Anderes Bild</button>
            <button class="dk-btn dk-btn-ghost dk-btn-sm" @click="showCrop = false">Abbrechen</button>
            <button v-if="cropSrc" class="dk-btn dk-btn-primary dk-btn-sm" :disabled="uploadingPhoto" @click="cropAndUpload">
              {{ uploadingPhoto ? 'Hochladen…' : 'Speichern' }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- ── Lösch-Bestätigung ── -->
    <Teleport to="body">
      <div v-if="showDeleteConfirm" class="prof-modal-overlay" @click.self="showDeleteConfirm = false">
        <div class="prof-modal prof-modal-danger">
          <div class="prof-modal-header">
            <h3>⚠️ Einwilligung widerrufen</h3>
          </div>
          <div style="padding:0 24px 16px">
            <p><strong>Diese Aktion ist unwiderruflich.</strong></p>
            <p style="margin-top:8px;color:var(--dk-text-muted);font-size:14px">
              Alle deine personenbezogenen Daten werden anonymisiert. Dein Account wird deaktiviert
              und du wirst sofort ausgeloggt. Du kannst dich danach nicht mehr einloggen.
            </p>
            <div class="prof-delete-confirm-input" style="margin-top:16px">
              <label style="font-size:13px;margin-bottom:4px;display:block">
                Tippe <strong>LÖSCHEN</strong> zur Bestätigung:
              </label>
              <input v-model="deleteConfirmText" class="dk-form-input" placeholder="LÖSCHEN" />
            </div>
          </div>
          <div class="prof-modal-footer">
            <button class="dk-btn dk-btn-ghost dk-btn-sm" @click="showDeleteConfirm = false">Abbrechen</button>
            <button
              class="dk-btn dk-btn-danger dk-btn-sm"
              :disabled="deleteConfirmText !== 'LÖSCHEN' || deleting"
              @click="executeDelete"
            >
              {{ deleting ? 'Löschen…' : 'Unwiderruflich löschen' }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>

  </div>
</template>

<script setup>
import { ref, computed, reactive, onMounted } from 'vue'
import { Cropper } from 'vue-advanced-cropper'
import 'vue-advanced-cropper/dist/style.css'

const API = '/api/method/diakronos.diakonos.api'

async function apiFetch(method, body = {}) {
  const csrf = document.querySelector('meta[name="csrf-token"]')?.content || ''
  const res = await fetch(`${API}.${method}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-Frappe-CSRF-Token': csrf },
    body: JSON.stringify(body),
  })
  const json = await res.json()
  if (!res.ok) throw new Error(json.message || 'API-Fehler')
  return json.message
}

// State
const loading = ref(true)
const error = ref(null)
const saving = ref(false)
const editingData = ref(false)
const uploadingPhoto = ref(false)
const deleting = ref(false)
const showCrop = ref(false)
const showDeleteConfirm = ref(false)
const deleteConfirmText = ref('')
const cropSrc = ref(null)
const cropperRef = ref(null)
const fileInput = ref(null)

const profile = ref({})
const form = reactive({})
const sichtbarkeit = reactive({ email: true, telefonnummer: true, adresse: false, geburtstag: false })

const COLORS = ['#3e4d78', '#1c2850', '#6e7ca6', '#d4a24c', '#8B5E3C']
const avatarStyle = computed(() => {
  if (profile.value.foto) return {}
  const idx = (profile.value.vorname || 'U').charCodeAt(0) % COLORS.length
  return { background: COLORS[idx], color: '#fff' }
})
const initials = computed(() => {
  const v = profile.value.vorname?.[0] || ''
  const n = profile.value.nachname?.[0] || ''
  return (v + n).toUpperCase() || 'U'
})
const fullAddress = computed(() => {
  const p = profile.value
  const street = [p.strasse, p.nummer].filter(Boolean).join(' ')
  const city = [p.postleitzahl, p.wohnort].filter(Boolean).join(' ')
  return [street, city].filter(Boolean).join(', ')
})

function formatDate(d) {
  if (!d) return ''
  const dt = new Date(d.replace(' ', 'T'))
  return dt.toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit', year: 'numeric' })
}

async function loadProfile() {
  loading.value = true
  error.value = null
  try {
    const data = await apiFetch('profile.get_my_profile')
    Object.assign(profile.value, data)
    Object.assign(sichtbarkeit, data.adressbuch_sichtbarkeit || {})
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

function startEdit() {
  Object.assign(form, {
    vorname: profile.value.vorname,
    nachname: profile.value.nachname,
    telefonnummer: profile.value.telefonnummer,
    postleitzahl: profile.value.postleitzahl,
    wohnort: profile.value.wohnort,
    strasse: profile.value.strasse,
    nummer: profile.value.nummer,
    geburtstag: profile.value.geburtstag,
    geschlecht: profile.value.geschlecht,
    familienstand: profile.value.familienstand,
  })
  editingData.value = true
}

function cancelEdit() {
  editingData.value = false
}

async function saveData() {
  saving.value = true
  try {
    await apiFetch('profile.update_my_profile', { ...form })
    Object.assign(profile.value, form)
    editingData.value = false
  } catch (e) {
    alert('Fehler beim Speichern: ' + e.message)
  } finally {
    saving.value = false
  }
}

async function saveSichtbarkeit() {
  try {
    await apiFetch('profile.update_adressbuch_sichtbarkeit', { settings: { ...sichtbarkeit } })
  } catch (e) {
    console.warn('Sichtbarkeit speichern fehlgeschlagen:', e)
  }
}

function openCropModal() {
  cropSrc.value = null
  showCrop.value = true
}
function triggerFileInput() { fileInput.value?.click() }
function onFileSelect(e) {
  const file = e.target.files[0]
  if (file) readFile(file)
}
function onFileDrop(e) {
  const file = e.dataTransfer.files[0]
  if (file) readFile(file)
}
function readFile(file) {
  const reader = new FileReader()
  reader.onload = (e) => { cropSrc.value = e.target.result }
  reader.readAsDataURL(file)
}

async function cropAndUpload() {
  if (!cropperRef.value) return
  const { canvas } = cropperRef.value.getResult()
  if (!canvas) return
  uploadingPhoto.value = true
  try {
    const blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/jpeg', 0.85))
    const fd = new FormData()
    fd.append('file', blob, 'profilbild.jpg')
    fd.append('is_private', '0')
    fd.append('folder', 'Home/Attachments')
    const csrf = document.querySelector('meta[name="csrf-token"]')?.content || ''
    const res = await fetch('/api/method/upload_file', {
      method: 'POST',
      headers: { 'X-Frappe-CSRF-Token': csrf },
      body: fd,
    })
    const json = await res.json()
    const url = json.message?.file_url
    if (!url) throw new Error('Upload fehlgeschlagen')
    await apiFetch('profile.update_profile_picture', { file_url: url })
    profile.value.foto = url
    showCrop.value = false
    cropSrc.value = null
  } catch (e) {
    alert('Fehler: ' + e.message)
  } finally {
    uploadingPhoto.value = false
  }
}

async function executeDelete() {
  if (deleteConfirmText.value !== 'LÖSCHEN') return
  deleting.value = true
  try {
    await apiFetch('profile.delete_my_data')
    window.location.href = '/login'
  } catch (e) {
    alert('Fehler: ' + e.message)
    deleting.value = false
  }
}

onMounted(loadProfile)
</script>

<style scoped>
.prof-loading { display: flex; align-items: center; gap: 16px; padding: 32px 0; }
.prof-layout { display: flex; flex-direction: column; gap: 16px; padding-bottom: 80px; }

/* Cards */
.prof-card {
  background: var(--dk-surface);
  border: 1px solid var(--dk-border);
  border-radius: 12px;
  overflow: hidden;
}
.prof-card-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid var(--dk-border);
  gap: 12px;
}
.prof-card-header h3 { margin: 0; font-size: 15px; font-weight: 600; }

/* Avatar card */
.prof-avatar-card { display: flex; align-items: center; gap: 20px; padding: 20px; }
.prof-avatar-wrap {
  position: relative; width: 72px; height: 72px;
  border-radius: 50%; cursor: pointer; flex-shrink: 0;
  overflow: hidden;
}
.prof-avatar {
  width: 100%; height: 100%; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: 24px; font-weight: 700;
}
.prof-avatar img { width: 100%; height: 100%; object-fit: cover; }
.prof-avatar-overlay {
  position: absolute; inset: 0; background: rgba(0,0,0,0.45);
  display: flex; align-items: center; justify-content: center;
  opacity: 0; transition: opacity 0.15s; color: #fff; border-radius: 50%;
}
.prof-avatar-wrap:hover .prof-avatar-overlay { opacity: 1; }
.prof-avatar-name { font-weight: 600; font-size: 17px; }

/* Fields */
.prof-fields { padding: 16px 20px; display: flex; flex-direction: column; gap: 12px; }
.prof-field-row { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.prof-field-wide { grid-column: 1 / -1; }
.prof-field { display: flex; flex-direction: column; gap: 4px; }
.prof-field label { font-size: 11px; font-weight: 600; color: var(--dk-text-muted); text-transform: uppercase; letter-spacing: 0.5px; }
.prof-field span { font-size: 14px; padding: 6px 0; }
.prof-fields.is-editing .dk-form-input { font-size: 14px; }

/* Toggles */
.prof-toggles { padding: 8px 0; }
.prof-toggle-row {
  display: flex; align-items: center; justify-content: space-between;
  padding: 12px 20px;
  border-bottom: 1px solid var(--dk-border);
}
.prof-toggle-row:last-child { border-bottom: none; }
.prof-toggle-info { display: flex; flex-direction: column; gap: 2px; }
.prof-toggle-label { font-size: 14px; font-weight: 500; }
.prof-toggle-desc { font-size: 12px; }

/* Toggle switch */
.prof-switch { position: relative; display: inline-block; width: 44px; height: 24px; flex-shrink: 0; }
.prof-switch input { opacity: 0; width: 0; height: 0; }
.prof-switch-track {
  position: absolute; inset: 0; border-radius: 12px;
  background: var(--dk-border); cursor: pointer; transition: background 0.2s;
}
.prof-switch-track::after {
  content: ''; position: absolute; top: 3px; left: 3px;
  width: 18px; height: 18px; border-radius: 50%;
  background: #fff; transition: transform 0.2s;
  box-shadow: 0 1px 3px rgba(0,0,0,0.2);
}
.prof-switch input:checked + .prof-switch-track { background: var(--dk-brand-500, #1c2850); }
.prof-switch input:checked + .prof-switch-track::after { transform: translateX(20px); }

/* DSGVO */
.prof-dsgvo-status {
  display: flex; align-items: flex-start; gap: 12px;
  padding: 16px 20px;
  border-radius: 8px; margin: 16px 20px 0;
}
.prof-dsgvo-ok { background: rgba(46,204,113,0.1); color: #27ae60; }
.prof-dsgvo-warn { background: rgba(231,76,60,0.1); color: var(--dk-danger, #e74c3c); }
.prof-dsgvo-actions { padding: 16px 20px; }
.prof-card-danger-zone { border-color: rgba(231,76,60,0.3); }
.dk-btn-danger {
  background: var(--dk-danger, #e74c3c); color: #fff; border: none;
  padding: 6px 14px; border-radius: 7px; font-size: 13px; cursor: pointer;
  display: inline-flex; align-items: center; gap: 6px;
  opacity: 1; transition: opacity 0.15s;
}
.dk-btn-danger:hover { opacity: 0.85; }
.dk-btn-danger:disabled { opacity: 0.5; cursor: not-allowed; }

/* Modal */
.prof-modal-overlay {
  position: fixed; inset: 0; background: rgba(0,0,0,0.5);
  display: flex; align-items: center; justify-content: center;
  z-index: 9999; padding: 16px;
}
.prof-modal {
  background: var(--dk-surface); border-radius: 12px;
  width: 100%; max-width: 480px;
  box-shadow: 0 20px 60px rgba(0,0,0,0.3);
  overflow: hidden;
}
.prof-modal-danger { border: 1px solid rgba(231,76,60,0.4); }
.prof-modal-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 16px 20px; border-bottom: 1px solid var(--dk-border);
}
.prof-modal-header h3 { margin: 0; font-size: 16px; font-weight: 600; }
.prof-modal-footer {
  display: flex; justify-content: flex-end; gap: 8px;
  padding: 16px 20px; border-top: 1px solid var(--dk-border);
}

/* Crop */
.prof-crop-area { padding: 20px; min-height: 300px; display: flex; align-items: center; justify-content: center; }
.prof-cropper { width: 100%; max-height: 340px; }
.prof-crop-upload {
  border: 2px dashed var(--dk-border); border-radius: 8px;
  padding: 40px; text-align: center; cursor: pointer; width: 100%;
  color: var(--dk-text-muted); transition: border-color 0.15s;
  display: flex; flex-direction: column; align-items: center; gap: 12px;
}
.prof-crop-upload:hover { border-color: var(--dk-brand-500, #1c2850); }
.prof-crop-upload p { margin: 0; font-size: 14px; }

@media (max-width: 600px) {
  .prof-field-row { grid-template-columns: 1fr; }
  .prof-avatar-card { flex-direction: column; text-align: center; }
}
</style>
