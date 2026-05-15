<template>
    <div class="dk-screen dk-screen-enter">
        <!-- Header -->
        <div class="dk-screen-header">
            <div class="flex items-center gap-4">
                <router-link to="#/mitglieder" class="text-[var(--dk-text-muted)] hover:text-[var(--dk-text)] transition">
                    <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                        <path stroke-linecap="round" stroke-linejoin="round" d="M15 19l-7-7 7-7" />
                    </svg>
                </router-link>
                <div class="flex items-center gap-4">
                    <div class="avatar">
                        <img v-if="mitglied?.image" :src="mitglied.image" :alt="fullName" class="avatar-img" />
                        <span v-else class="avatar-initials">{{ initials }}</span>
                    </div>
                    <div>
                        <h1 class="dk-screen-title">{{ fullName }}</h1>
                        <div class="flex items-center gap-2 mt-1">
                            <span
                                class="status-badge"
                                :class="{
                                    'dk-badge dk-badge-success': mitglied?.status === 'Aktiv',
                                    'dk-badge dk-badge-danger': mitglied?.status === 'Inaktiv',
                                    'dk-badge dk-badge-warning': mitglied?.status === 'Pausiert',
                                    'dk-badge': !mitglied?.status || mitglied?.status === 'Unbekannt'
                                }"
                            >
                                {{ mitglied?.status || 'Unbekannt' }}
                            </span>
                        </div>
                    </div>
                </div>
            </div>
            <div class="dk-screen-actions">
                <button v-if="canEdit && !isEditing" class="dk-btn dk-btn-secondary" @click="startEdit">
                    Bearbeiten
                </button>
                <template v-else-if="isEditing">
                    <button class="dk-btn dk-btn-secondary" @click="cancelEdit">
                        Abbrechen
                    </button>
                    <button class="dk-btn dk-btn-primary" :disabled="isSaving" @click="saveEdit">
                        <span v-if="isSaving" class="dk-spinner dk-spinner-sm" />
                        <template v-else>Speichern</template>
                    </button>
                </template>
            </div>
        </div>

        <!-- Tabs -->
        <div class="tabs-wrapper mb-6">
            <nav class="tabs-nav">
                <button
                    v-for="tab in tabs"
                    :key="tab.key"
                    @click="activeTab = tab.key"
                    :class="['tab-btn', { active: activeTab === tab.key }]"
                >
                    {{ tab.label }}
                </button>
            </nav>
        </div>

        <!-- Loading -->
        <div v-if="loading" class="dk-loading">
            <div class="dk-spinner"></div>
            <p class="dk-loading-text">Lade Mitglied...</p>
        </div>

        <!-- Error -->
        <div v-else-if="error" class="dk-empty">
            <p class="dk-empty-title">Fehler</p>
            <p class="dk-empty-desc">{{ error }}</p>
        </div>

        <!-- Tab: Details -->
        <div v-else-if="activeTab === 'details'" class="card">
            <h2 class="text-lg font-semibold text-[var(--dk-text)] mb-4">Persönliche Daten</h2>

            <!-- View mode -->
            <div v-if="!isEditing" class="space-y-3">
                <div class="data-row">
                    <span class="data-label">Vorname</span>
                    <span class="data-value">{{ mitglied?.vorname || '–' }}</span>
                </div>
                <div class="data-row">
                    <span class="data-label">Nachname</span>
                    <span class="data-value">{{ mitglied?.nachname || '–' }}</span>
                </div>
                <div class="data-row">
                    <span class="data-label">E-Mail</span>
                    <span class="data-value">{{ mitglied?.email || '–' }}</span>
                </div>
                <div class="data-row">
                    <span class="data-label">Telefon</span>
                    <span class="data-value">{{ mitglied?.telefonnummer || '–' }}</span>
                </div>
                <div class="data-row">
                    <span class="data-label">Geburtstag</span>
                    <span class="data-value">{{ formatDate(mitglied?.geburtstag) || '–' }}</span>
                </div>
                <div class="data-row">
                    <span class="data-label">Geschlecht</span>
                    <span class="data-value">{{ mitglied?.geschlecht || '–' }}</span>
                </div>
                <div class="data-row">
                    <span class="data-label">Familienstand</span>
                    <span class="data-value">{{ mitglied?.familienstand || '–' }}</span>
                </div>
                <div class="data-row">
                    <span class="data-label">Adresse</span>
                    <span class="data-value">
                        <template v-if="mitglied?.straße || mitglied?.nummer || mitglied?.postleitzahl || mitglied?.wohnort">
                            {{ [mitglied?.straße, mitglied?.nummer].filter(Boolean).join(' ') }}<br v-if="mitglied?.straße || mitglied?.nummer" />
                            {{ [mitglied?.postleitzahl, mitglied?.wohnort].filter(Boolean).join(' ') }}
                        </template>
                        <template v-else>–</template>
                    </span>
                </div>
                <div class="data-row">
                    <span class="data-label">Eintrittsdatum</span>
                    <span class="data-value">{{ formatDate(mitglied?.eintrittsdatum) || '–' }}</span>
                </div>
                <div class="data-row">
                    <span class="data-label">Letzte Anmeldung</span>
                    <span class="data-value">{{ formatDate(mitglied?.letzte_anmeldung) || '–' }}</span>
                </div>
            </div>

            <!-- Edit mode -->
            <div v-else class="edit-form">
                <div class="edit-grid">
                    <div class="edit-field">
                        <label class="edit-label">Vorname</label>
                        <input v-model="editForm.vorname" type="text" class="dk-form-input" />
                    </div>
                    <div class="edit-field">
                        <label class="edit-label">Nachname</label>
                        <input v-model="editForm.nachname" type="text" class="dk-form-input" />
                    </div>
                    <div class="edit-field">
                        <label class="edit-label">E-Mail</label>
                        <input v-model="editForm.email" type="email" class="dk-form-input" />
                    </div>
                    <div class="edit-field">
                        <label class="edit-label">Telefon</label>
                        <input v-model="editForm.telefon" type="tel" class="dk-form-input" />
                    </div>
                    <div class="edit-field">
                        <label class="edit-label">Geburtstag</label>
                        <input v-model="editForm.geburtstag" type="date" class="dk-form-input" />
                    </div>
                    <div class="edit-field">
                        <label class="edit-label">Geschlecht</label>
                        <select v-model="editForm.geschlecht" class="dk-form-input">
                            <option value="">– keine Angabe –</option>
                            <option>Männlich</option>
                            <option>Weiblich</option>
                            <option>Divers</option>
                        </select>
                    </div>
                    <div class="edit-field">
                        <label class="edit-label">Familienstand</label>
                        <select v-model="editForm.familienstand" class="dk-form-input">
                            <option value="">– keine Angabe –</option>
                            <option>Ledig</option>
                            <option>Verheiratet</option>
                            <option>Verwitwet</option>
                            <option>Geschieden</option>
                        </select>
                    </div>
                    <div class="edit-field edit-field-full">
                        <label class="edit-label">Straße &amp; Hausnummer</label>
                        <div class="flex gap-2">
                            <input v-model="editForm.strasse" type="text" class="dk-form-input" placeholder="Straße" style="flex:1" />
                            <input v-model="editForm.hausnummer" type="text" class="dk-form-input" placeholder="Nr." style="width:70px" />
                        </div>
                    </div>
                    <div class="edit-field">
                        <label class="edit-label">PLZ</label>
                        <input v-model="editForm.plz" type="text" class="dk-form-input" />
                    </div>
                    <div class="edit-field">
                        <label class="edit-label">Ort</label>
                        <input v-model="editForm.ort" type="text" class="dk-form-input" />
                    </div>
                </div>
            </div>
        </div>

        <!-- Tab: Dienste -->
        <div v-else-if="activeTab === 'dienste'" class="card">
            <h2 class="text-lg font-semibold text-[var(--dk-text)] mb-4">Dienste</h2>
            <p class="text-[var(--dk-text-muted)]">Dienst-Übersicht wird hier angezeigt</p>
        </div>

        <!-- Tab: Gruppen -->
        <div v-else-if="activeTab === 'gruppen'" class="card">
            <h2 class="text-lg font-semibold text-[var(--dk-text)] mb-4">Gruppen</h2>
            <p class="text-[var(--dk-text-muted)]">Gruppen-Zugehörigkeit wird hier angezeigt</p>
        </div>

        <!-- Tab: DSGVO -->
        <div v-else-if="activeTab === 'dsgvo'" class="card">
            <h2 class="text-lg font-semibold text-[var(--dk-text)] mb-4">DSGVO & Einwilligungen</h2>
            <div class="space-y-4">
                <div class="flex items-center justify-between p-3 bg-[var(--dk-surface-hover)] rounded">
                    <div>
                        <p class="font-medium text-[var(--dk-text)]">Datenschutzerklärung akzeptiert</p>
                        <p class="text-sm text-[var(--dk-text-muted)]">{{ dsgvo.datenschutz ? formatDate(dsgvo.datenschutz_datum) : 'Nicht akzeptiert' }}</p>
                    </div>
                    <span :class="dsgvo.datenschutz ? 'dk-badge dk-badge-success' : 'dk-badge dk-badge-danger'">
                        {{ dsgvo.datenschutz ? 'Ja' : 'Nein' }}
                    </span>
                </div>
                <div class="flex items-center justify-between p-3 bg-[var(--dk-surface-hover)] rounded">
                    <div>
                        <p class="font-medium text-[var(--dk-text)]">Foto-Einwilligung</p>
                        <p class="text-sm text-[var(--dk-text-muted)]">{{ dsgvo.foto ? formatDate(dsgvo.foto_datum) : 'Nicht erteilt' }}</p>
                    </div>
                    <span :class="dsgvo.foto ? 'dk-badge dk-badge-success' : 'dk-badge dk-badge-danger'">
                        {{ dsgvo.foto ? 'Ja' : 'Nein' }}
                    </span>
                </div>
                <div class="flex items-center justify-between p-3 bg-[var(--dk-surface-hover)] rounded">
                    <div>
                        <p class="font-medium text-[var(--dk-text)]">Werbeeinwilligung</p>
                        <p class="text-sm text-[var(--dk-text-muted)]">{{ dsgvo.werbung ? formatDate(dsgvo.werbung_datum) : 'Nicht erteilt' }}</p>
                    </div>
                    <span :class="dsgvo.werbung ? 'dk-badge dk-badge-success' : 'dk-badge dk-badge-danger'">
                        {{ dsgvo.werbung ? 'Ja' : 'Nein' }}
                    </span>
                </div>
                <button
                    v-if="dsgvo.datenschutz || dsgvo.foto || dsgvo.werbung"
                    class="dk-btn dk-btn-danger"
                    @click="widerrufEinwilligung"
                >
                    Einwilligungen widerrufen
                </button>
            </div>
        </div>

        <!-- Tab: Historie -->
        <div v-else-if="activeTab === 'historie'" class="card">
            <h2 class="text-lg font-semibold text-[var(--dk-text)] mb-4">Historie</h2>
            <p class="text-[var(--dk-text-muted)]">Audit-Log wird hier angezeigt</p>
        </div>
    </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useSession } from '../composables/useSession.js'
import { getRouteParam } from '../router.js'
import { apiCall, AuditConfirmationRequired } from '../composables/useApi.js'
import { useAuditConfirm } from '../composables/useAuditConfirm.js'
import { showToast } from '../composables/useToast.js'

const { isAdmin } = useSession()
const { openConfirm, isSubmitting } = useAuditConfirm()

const mitglied = ref(null)
const loading = ref(true)
const error = ref(null)
const isSaving = ref(false)
const canEdit = computed(() => !error.value && mitglied.value && isAdmin.value)
const isEditing = ref(false)
const activeTab = ref('details')

const tabs = [
    { key: 'details', label: 'Details' },
    { key: 'dienste', label: 'Dienste' },
    { key: 'gruppen', label: 'Gruppen' },
    { key: 'dsgvo', label: 'DSGVO' },
    { key: 'historie', label: 'Historie' },
]

const editForm = reactive({
    vorname: '',
    nachname: '',
    email: '',
    telefon: '',
    geburtstag: '',
    strasse: '',
    hausnummer: '',
    plz: '',
    ort: '',
    geschlecht: '',
    familienstand: '',
})

const dsgvo = reactive({
    datenschutz: false,
    datenschutz_datum: null,
    foto: false,
    foto_datum: null,
    werbung: false,
    werbung_datum: null,
})

const fullName = computed(() => {
    const m = mitglied.value
    if (!m) return 'Unbekannt'
    const v = (m.vorname ?? '').toString().trim()
    const n = (m.nachname ?? '').toString().trim()
    if (v || n) return `${v} ${n}`.trim()
    if (m.full_name) return m.full_name
    if (m.name) return m.name
    if (m.email) return m.email
    return 'Unbekannt'
})

const initials = computed(() => {
    const m = mitglied.value
    if (!m) return '?'
    const v = (m.vorname ?? '').toString().trim()[0] || ''
    const n = (m.nachname ?? '').toString().trim()[0] || ''
    return (v + n).toUpperCase() || '?'
})

function formatDate(date) {
    if (!date) return null
    try {
        return new Date(date).toLocaleDateString('de-DE')
    } catch {
        return date
    }
}

function _fillEditForm(payload) {
    Object.assign(editForm, {
        vorname: payload.vorname || '',
        nachname: payload.nachname || '',
        email: payload.email || '',
        telefon: payload.telefonnummer || '',
        geburtstag: payload.geburtstag || '',
        strasse: payload.straße || '',
        hausnummer: payload.nummer || '',
        plz: payload.postleitzahl || '',
        ort: payload.wohnort || '',
        geschlecht: payload.geschlecht || '',
        familienstand: payload.familienstand || '',
    })
}

async function loadMitglied() {
    loading.value = true
    error.value = null
    try {
        const id = getRouteParam('id')
        if (!id) throw new Error('Keine Mitglied-ID angegeben')

        const response = await apiCall('diakronos.diakonos.api.mitglieder.get_mitglied_detail', { mitglied_id: id })
        const payload = response?.data ?? response

        if (!payload || typeof payload !== 'object') {
            throw new Error('Ungültige Daten vom Server')
        }

        mitglied.value = payload
        _fillEditForm(payload)

        if (payload.dsgvo) {
            Object.assign(dsgvo, payload.dsgvo)
        }
    } catch (e) {
        console.error('[MitgliedDetail] load error:', e)
        error.value = e.message || 'Mitglied konnte nicht geladen werden'
    } finally {
        loading.value = false
    }
}

function startEdit() {
    _fillEditForm(mitglied.value || {})
    isEditing.value = true
}

function cancelEdit() {
    isEditing.value = false
}

async function saveEdit() {
    if (isSaving.value) return
    isSaving.value = true
    const idempotencyKey = generateIdempotencyKey()
    try {
        const id = getRouteParam('id')
        await apiCall('diakronos.diakonos.api.mitglieder.update_mitglied', {
            mitglied_id: id,
            data: JSON.stringify({ ...editForm }),
        })
        showToast('Mitglied gespeichert', 'success')
        isEditing.value = false
        await loadMitglied()
    } catch (err) {
        if (err instanceof AuditConfirmationRequired) {
            const reason = await openConfirm(err.policy)
            if (!reason) {
                showToast('Abgebrochen', 'info')
                return
            }
            const id = getRouteParam('id')
            isSubmitting.value = true
            try {
                await apiCall('diakronos.diakonos.api.mitglieder.update_mitglied', {
                    mitglied_id: id,
                    data: JSON.stringify({ ...editForm }),
                    __audit_confirmation: JSON.stringify({
                        policy_name: err.policy.policy_name,
                        reason: reason,
                        idempotency_key: idempotencyKey,
                    }),
                })
                showToast('Mitglied gespeichert', 'success')
                isEditing.value = false
                await loadMitglied()
            } finally {
                isSubmitting.value = false
            }
        } else {
            console.error('[MitgliedDetail] save error:', err)
            showToast(err.message || 'Speichern fehlgeschlagen', 'error')
        }
    } finally {
        isSaving.value = false
    }
}

function generateIdempotencyKey() {
    if (typeof crypto !== 'undefined' && crypto.randomUUID) {
        return crypto.randomUUID()
    }
    return Date.now().toString(36) + '-' + Math.random().toString(36).slice(2)
}

async function widerrufEinwilligung() {
    if (!confirm('Möchten Sie alle Einwilligungen widerrufen?')) return
    const idempotencyKey = generateIdempotencyKey()
    try {
        const id = getRouteParam('id')
        await apiCall('diakronos.diakonos.api.mitglieder.widerruf_einwilligung', { mitglied_id: id })
        showToast('Einwilligungen widerrufen', 'success')
        await loadMitglied()
    } catch (err) {
        if (err instanceof AuditConfirmationRequired) {
            const reason = await openConfirm(err.policy)
            if (!reason) {
                showToast('Abgebrochen', 'info')
                return
            }
            const id = getRouteParam('id')
            isSubmitting.value = true
            try {
                await apiCall('diakronos.diakonos.api.mitglieder.widerruf_einwilligung', {
                    mitglied_id: id,
                    __audit_confirmation: JSON.stringify({
                        policy_name: err.policy.policy_name,
                        reason: reason,
                        idempotency_key: idempotencyKey,
                    }),
                })
                showToast('Einwilligungen widerrufen', 'success')
                await loadMitglied()
            } finally {
                isSubmitting.value = false
            }
        } else {
            console.error('[MitgliedDetail] widerruf error:', err)
            showToast(err.message || 'Widerruf fehlgeschlagen', 'error')
        }
    }
}

onMounted(loadMitglied)
</script>

<style scoped>
.avatar {
    width: 56px;
    height: 56px;
    border-radius: 50%;
    background: #e5e7eb;
    display: flex;
    align-items: center;
    justify-content: center;
    overflow: hidden;
    flex-shrink: 0;
}

.avatar-img {
    width: 100%;
    height: 100%;
    object-fit: cover;
}

.avatar-initials {
    font-size: 20px;
    font-weight: 600;
    color: #374151;
}

.data-row {
    display: flex;
    justify-content: space-between;
    padding: 0.75rem 0;
    border-bottom: 1px solid var(--dk-border);
}

.data-row:last-child {
    border-bottom: none;
}

.data-label {
    font-weight: 500;
    color: var(--dk-text-muted);
}

.data-value {
    color: var(--dk-text);
    text-align: right;
}

.tabs-wrapper {
    border-bottom: 1px solid var(--dk-border);
}

.tabs-nav {
    display: flex;
    gap: 1rem;
}

.tab-btn {
    padding: 0.5rem 0;
    background: none;
    border: none;
    color: var(--dk-text-muted);
    font-weight: 500;
    cursor: pointer;
    border-bottom: 2px solid transparent;
    transition: all 0.2s;
}

.tab-btn:hover {
    color: var(--dk-text);
}

.tab-btn.active {
    color: var(--dk-primary);
    border-bottom-color: var(--dk-primary);
}

.status-badge {
    font-size: 0.75rem;
    padding: 0.25rem 0.5rem;
    border-radius: 9999px;
}

.card {
    background: var(--dk-surface);
    border: 1px solid var(--dk-border);
    border-radius: 0.75rem;
    padding: 1.5rem;
}

.edit-form {
    padding-top: 0.25rem;
}

.edit-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1rem;
}

@media (max-width: 600px) {
    .edit-grid {
        grid-template-columns: 1fr;
    }
}

.edit-field {
    display: flex;
    flex-direction: column;
    gap: 0.375rem;
}

.edit-field-full {
    grid-column: 1 / -1;
}

.edit-label {
    font-size: 0.8125rem;
    font-weight: 500;
    color: var(--dk-text-muted);
}
</style>
