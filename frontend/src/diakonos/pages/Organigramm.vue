<template>
    <div class="dk-screen dk-screen-wide dk-screen-enter">
        <div class="dk-screen-header">
            <div>
                <h1 class="dk-screen-title">Organigramm</h1>
                <p class="dk-screen-sub">Visuelle Übersicht der Gemeinde-Struktur.</p>
            </div>
            <div style="display:flex;gap:8px;align-items:center;">
                <button
                    v-if="hasEditableGroups || perms.can_create_dienstbereich"
                    class="dk-btn dk-btn-secondary"
                    @click="openManageModal"
                >
                    Gruppen verwalten
                </button>
            </div>
        </div>

        <div v-if="loading" style="padding:40px;text-align:center;color:var(--dk-text-muted);">
            Lade…
        </div>

        <div
            v-else-if="nodes.length <= 1"
            style="padding:40px;text-align:center;color:var(--dk-text-muted);"
        >
            Noch keine Gruppen vorhanden.
        </div>

        <div
            v-else
            id="dk-org-chart"
            style="width:100%;height:calc(100vh - 160px);overflow:hidden;"
        ></div>
    </div>

    <!-- MANAGE Modal (Schritt 1) -->
    <Teleport to="body">
        <div v-if="showManageModal" class="dk-modal-overlay" @click.self="closeManageModal">
            <div class="dk-modal">
                <h3>Gruppen verwalten</h3>
                <p style="margin-top:4px;color:var(--dk-text-muted);font-size:0.82rem;">Was möchtest du tun?</p>
                <div style="margin-top:16px;display:flex;flex-direction:column;gap:10px;">
                    <div class="manage-option" @click="goToEdit">
                        <span style="font-size:1.5rem">✏️</span>
                        <div>
                            <div style="font-weight:600;font-size:0.9rem;">Gruppe bearbeiten</div>
                            <div style="font-size:0.78rem;color:var(--dk-text-muted);">Name, Treffzeit, Beschreibung ändern</div>
                        </div>
                    </div>
                    <div class="manage-option" @click="goToCreate">
                        <span style="font-size:1.5rem">➕</span>
                        <div>
                            <div style="font-weight:600;font-size:0.9rem;">Neue Gruppe erstellen</div>
                            <div style="font-size:0.78rem;color:var(--dk-text-muted);">Gruppe, Untergruppe oder Dienstbereich anlegen</div>
                        </div>
                    </div>
                </div>
                <div class="dk-modal-actions" style="margin-top:16px;">
                    <button class="dk-btn dk-btn-secondary" @click="closeManageModal">Abbrechen</button>
                </div>
            </div>
        </div>
    </Teleport>

    <!-- EDIT-FLOW Modal (Schritt 2a) -->
    <Teleport to="body">
        <div v-if="showEditSelectModal" class="dk-modal-overlay" @click.self="closeEditSelectModal">
            <div class="dk-modal">
                <h3>Gruppe bearbeiten</h3>
                <div style="margin-top:16px;">
                    <div class="dk-form-group" style="margin-bottom:14px;">
                        <label>Gruppe auswählen</label>
                        <select v-model="editSelectId" class="dk-form-select" style="width:100%;">
                            <option value="">— Bitte wählen —</option>
                            <option v-for="n in editableNodes" :key="n.id" :value="n.id">{{ n.name }} ({{ n.type }})</option>
                        </select>
                    </div>
                </div>
                <div class="dk-modal-actions">
                    <button class="dk-btn dk-btn-secondary" @click="closeEditSelectModal">Zurück</button>
                    <button class="dk-btn dk-btn-primary" @click="proceedToEdit" :disabled="!editSelectId">Weiter</button>
                </div>
            </div>
        </div>
    </Teleport>

    <!-- EDIT Modal (Schritt 2a final) -->
    <Teleport to="body">
        <div v-if="showEditModal" class="dk-modal-overlay" @click.self="closeEditModal">
            <div class="dk-modal">
                <h3>Bearbeiten</h3>
                <div style="margin-top:16px;">
                    <div class="dk-form-group" style="margin-bottom:14px;">
                        <label>Name</label>
                        <input v-model="editForm.name" type="text" class="dk-form-input" />
                    </div>
                    <div class="dk-form-group" style="margin-bottom:14px;">
                        <label>Beschreibung</label>
                        <textarea v-model="editForm.beschreibung" class="dk-form-input" rows="3"></textarea>
                    </div>
                    <div class="dk-form-group" style="margin-bottom:14px;">
                        <label>Treffzeit</label>
                        <input v-model="editForm.treffzeit" type="text" class="dk-form-input" placeholder="z.B. Dienstag 19:30" />
                    </div>
                    <div class="dk-form-group" style="margin-bottom:14px;">
                        <label>Treffpunkt</label>
                        <input v-model="editForm.treffpunkt" type="text" class="dk-form-input" placeholder="z.B. Gemeindesaal" />
                    </div>
                </div>
                <div class="dk-modal-actions">
                    <button class="dk-btn dk-btn-secondary" @click="closeEditModal">Abbrechen</button>
                    <button class="dk-btn dk-btn-primary" @click="submitEdit">Speichern</button>
                </div>
            </div>
        </div>
    </Teleport>

    <!-- CREATE Modal (Schritt 2b) -->
    <Teleport to="body">
        <div v-if="showCreateModal" class="dk-modal-overlay" @click.self="closeCreateModal">
            <div class="dk-modal">
                <h3>Neue Gruppe / Untergruppe</h3>
                <div style="margin-top:16px;">
                    <div class="dk-form-group" style="margin-bottom:14px;">
                        <label>Typ</label>
                        <select v-model="createForm.typ" class="dk-form-select">
                            <option value="gruppe">Gruppe</option>
                            <option value="untergruppe">Untergruppe</option>
                            <option value="dienstbereich">Dienstbereich</option>
                        </select>
                    </div>
                    <div class="dk-form-group" style="margin-bottom:14px;">
                        <label>Name</label>
                        <input v-model="createForm.name" type="text" class="dk-form-input" placeholder="Name eingeben" />
                    </div>
                    <div v-if="createForm.typ === 'gruppe'" class="dk-form-group" style="margin-bottom:14px;">
                        <label>Dienstbereich</label>
                        <select v-model="createForm.parent" class="dk-form-select">
                            <option value="">Bitte wählen</option>
                            <option v-for="db in dienstbereiche" :key="db.id" :value="db.id">
                                {{ db.name }}
                            </option>
                        </select>
                    </div>
                    <div v-if="createForm.typ === 'untergruppe'" class="dk-form-group" style="margin-bottom:14px;">
                        <label>Gruppe</label>
                        <select v-model="createForm.parent" class="dk-form-select">
                            <option value="">Bitte wählen</option>
                            <option v-for="g in gruppenNodes" :key="g.id" :value="g.id">
                                {{ g.name }}
                            </option>
                        </select>
                    </div>
                    <div v-if="createForm.typ === 'dienstbereich'" class="dk-form-group" style="margin-bottom:14px;">
                        <label>Farbe (optional)</label>
                        <input v-model="createForm.farbe" type="text" class="dk-form-input" placeholder="#3b82f6" />
                    </div>
                </div>
                <div class="dk-modal-actions">
                    <button class="dk-btn dk-btn-secondary" @click="closeCreateModal">Abbrechen</button>
                    <button class="dk-btn dk-btn-primary" @click="submitCreate">Erstellen</button>
                </div>
            </div>
        </div>
    </Teleport>
</template>

<script setup>
import { ref, computed, onMounted, nextTick } from 'vue'
import { OrgChart } from 'd3-org-chart'
import { apiCall } from '../composables/useApi.js'

const loading = ref(true)
const nodes = ref([])
const perms = ref({ can_create_dienstbereich: false, can_create_any: false, can_edit_ids: [] })
let chart = null

const hasEditableGroups = computed(() => perms.value.can_edit_ids?.length > 0)

const dienstbereiche = computed(() => nodes.value.filter(n => n.type === 'dienstbereich'))
const gruppenNodes = computed(() => nodes.value.filter(n => n.type === 'gruppe'))
const editableNodes = computed(() => nodes.value.filter(n => perms.value.can_edit_ids?.includes(n.id)))

/* ---------- Modals ---------- */
const showManageModal = ref(false)
const showEditSelectModal = ref(false)
const showEditModal = ref(false)
const showCreateModal = ref(false)

const editSelectId = ref('')
const createForm = ref({ typ: 'gruppe', name: '', parent: '', farbe: '' })

const editTarget = ref(null)
const editForm = ref({ name: '', beschreibung: '', treffzeit: '', treffpunkt: '' })

function openManageModal() {
    showManageModal.value = true
}
function closeManageModal() {
    showManageModal.value = false
}

function goToEdit() {
    closeManageModal()
    editSelectId.value = ''
    showEditSelectModal.value = true
}
function goToCreate() {
    closeManageModal()
    createForm.value = { typ: 'gruppe', name: '', parent: '', farbe: '' }
    showCreateModal.value = true
}

function closeEditSelectModal() {
    showEditSelectModal.value = false
    editSelectId.value = ''
}

function proceedToEdit() {
    if (!editSelectId.value) return
    const node = nodes.value.find(n => n.id === editSelectId.value)
    if (!node) return
    editTarget.value = node
    editForm.value = {
        name: node.name || '',
        beschreibung: node.beschreibung || '',
        treffzeit: node.treffzeit || '',
        treffpunkt: node.treffpunkt || ''
    }
    showEditSelectModal.value = false
    showEditModal.value = true
}

function openCreateModal() {
    createForm.value = { typ: 'gruppe', name: '', parent: '', farbe: '' }
    showCreateModal.value = true
}
function closeCreateModal() {
    showCreateModal.value = false
}

function closeEditModal() {
    showEditModal.value = false
    editTarget.value = null
}

async function submitCreate() {
    const f = createForm.value
    try {
        if (f.typ === 'dienstbereich') {
            await apiCall('diakronos.diakonos.api.gruppen.create_dienstbereich', {
                name: f.name,
                farbe: f.farbe || undefined
            })
        } else if (f.typ === 'gruppe') {
            await apiCall('diakronos.diakonos.api.gruppen.create_gruppe', {
                name: f.name,
                parent: f.parent
            })
        } else if (f.typ === 'untergruppe') {
            await apiCall('diakronos.diakonos.api.gruppen.create_untergruppe', {
                name: f.name,
                parent: f.parent
            })
        }
        closeCreateModal()
        await loadData()
    } catch (err) {
        console.error('Fehler beim Erstellen:', err)
        alert('Fehler beim Erstellen: ' + (err.message || 'Unbekannter Fehler'))
    }
}

async function submitEdit() {
    if (!editTarget.value) return
    try {
        const payload = {
            name: editTarget.value.id,
            gruppenname: editForm.value.name,
            beschreibung: editForm.value.beschreibung,
            treffzeit: editForm.value.treffzeit,
            treffpunkt: editForm.value.treffpunkt
        }
        if (editTarget.value.type === 'gruppe') {
            await apiCall('diakronos.diakonos.api.gruppen.update_gruppe', payload)
        } else if (editTarget.value.type === 'untergruppe') {
            await apiCall('diakronos.diakonos.api.gruppen.update_untergruppe', payload)
        } else if (editTarget.value.type === 'dienstbereich') {
            await apiCall('diakronos.diakonos.api.gruppen.update_dienstbereich', payload)
        }
        closeEditModal()
        await loadData()
    } catch (err) {
        console.error('Fehler beim Speichern:', err)
        alert('Fehler beim Speichern: ' + (err.message || 'Unbekannter Fehler'))
    }
}

/* ---------- d3-org-chart ---------- */
function buildNodeContent(d) {
    if (d.data.type === 'root') {
        return '<div style="width:1px;height:1px;overflow:hidden;opacity:0;"></div>'
    }
    const t = d.data.type
    const isDB = t === 'dienstbereich'
    const isUG = t === 'untergruppe'

    let nodeWidth = 220
    let nodeHeight = 80
    if (isDB) { nodeWidth = 200; nodeHeight = 60 }
    else if (t === 'gruppe') { nodeWidth = 190; nodeHeight = 72 }
    else if (isUG) { nodeWidth = 170; nodeHeight = 64 }

    const borderLeft = d.data.farbe ? `border-left:3px solid ${d.data.farbe};` : ''
    const bg = isDB ? 'background:var(--dk-surface-2);' : 'background:var(--dk-surface);'
    const boxShadow = isDB ? 'box-shadow:0 1px 4px rgba(0,0,0,0.08);' : ''
    const borderRadius = 'border-radius:10px;'
    const cursor = isDB ? '' : 'cursor:pointer;'
    const fontWeight = isDB ? '700' : '600'
    const fontSize = isUG ? '0.78rem' : (isDB ? '0.88rem' : '0.82rem')
    const padding = isDB ? '8px 14px' : '10px 12px'

    const editBtn = perms.value.can_edit_ids?.includes(d.data.id)
        ? `<button onclick="window.__orgEditNode('${d.data.id}')" style="position:absolute;top:6px;right:6px;background:none;border:none;cursor:pointer;font-size:0.75rem;color:var(--dk-text-muted);">✏️</button>`
        : ''
    const memberLine = (!isDB && d.data.mitglieder_count !== undefined)
        ? `<div style="font-size:0.72rem;color:var(--dk-text-muted);margin-top:4px;">👤 ${d.data.mitglieder_count}</div>`
        : ''
    const timeLine = d.data.treffzeit
        ? `<div style="font-size:0.7rem;color:var(--dk-text-subtle);margin-top:2px;">🕐 ${d.data.treffzeit}</div>`
        : ''
    return `<div style="width:${d.width}px;height:${d.height}px;padding:${padding};box-sizing:border-box;border:1px solid var(--dk-border);${bg}${borderLeft}${boxShadow}${borderRadius}${cursor}position:relative;overflow:hidden;"
        onclick="window.__orgNavigateNode('${d.data.id}', '${d.data.type}')">
        ${editBtn}
        <div style="font-weight:${fontWeight};font-size:${fontSize};color:var(--dk-text);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${d.data.name || d.data.id}</div>
        ${memberLine}
        ${timeLine}
    </div>`
}

async function renderChart() {
    await nextTick()
    const container = document.getElementById('dk-org-chart')
    if (!container) return
    if (chart) {
        chart.clear()
        chart = null
    }
    chart = new OrgChart()
    chart
        .container('#dk-org-chart')
        .data(nodes.value)
        .nodeWidth(d => {
            if (d.data.type === 'root') return 1
            if (d.data.type === 'dienstbereich') return 200
            if (d.data.type === 'gruppe') return 190
            if (d.data.type === 'untergruppe') return 170
            return 220
        })
        .nodeHeight(d => {
            if (d.data.type === 'root') return 1
            if (d.data.type === 'dienstbereich') return 60
            if (d.data.type === 'gruppe') return 72
            if (d.data.type === 'untergruppe') return 64
            return 80
        })
        .childrenMargin(() => 40)
        .compactMarginBetween(() => 15)
        .compactMarginPair(() => 40)
        .nodeContent(buildNodeContent)
        .render()
}

async function loadData() {
    loading.value = true
    try {
        const [chartData, permsData] = await Promise.all([
            apiCall('diakronos.diakonos.api.gruppen.get_gruppen_for_orgchart'),
            apiCall('diakronos.diakonos.api.gruppen.get_user_create_permissions')
        ])
        nodes.value = chartData?.nodes || []
        perms.value = permsData || {}
        loading.value = false
        if (nodes.value.length > 1) {
            await renderChart()
        }
    } catch (err) {
        console.error('Fehler beim Laden:', err)
        loading.value = false
    }
}

onMounted(loadData)

/* ---------- Globale Handler fuer inline HTML ---------- */
window.__orgEditNode = (id) => {
    const node = nodes.value.find(n => n.id === id)
    if (!node) return
    editTarget.value = node
    editForm.value = {
        name: node.name || '',
        beschreibung: node.beschreibung || '',
        treffzeit: node.treffzeit || '',
        treffpunkt: node.treffpunkt || ''
    }
    showEditModal.value = true
}

window.__orgNavigateNode = (id, type) => {
    if (type === 'root' || type === 'dienstbereich') return
    window.location.hash = '#/gruppe/' + encodeURIComponent(id)
}
</script>

<style scoped>
#dk-org-chart :deep(svg) {
    background: transparent !important;
}
#dk-org-chart :deep(.node) {
    cursor: default;
}
.manage-option {
    display: flex;
    align-items: center;
    gap: 14px;
    padding: 14px 16px;
    border-radius: 10px;
    border: 1px solid var(--dk-border);
    cursor: pointer;
    transition: background 0.12s;
}
.manage-option:hover {
    background: var(--dk-surface-2);
}
</style>