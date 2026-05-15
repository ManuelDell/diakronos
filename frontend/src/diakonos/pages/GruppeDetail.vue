<template>
    <div class="dk-screen dk-screen-enter">
        <!-- Header -->
        <div class="dk-screen-header">
            <div class="flex items-center gap-4">
                <a href="#/gruppen" class="text-[var(--dk-text-muted)] hover:text-[var(--dk-text)] transition">
                    <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                        <path stroke-linecap="round" stroke-linejoin="round" d="M15 19l-7-7 7-7" />
                    </svg>
                </a>
                <div>
                    <div class="flex items-center gap-2 flex-wrap">
                        <h1 class="dk-screen-title">{{ displayName }}</h1>
                        <span
                            class="dk-badge"
                            :class="{
                                'dk-badge-success': currentStatus === 'Aktiv',
                                'dk-badge-danger': currentStatus === 'Inaktiv',
                                'dk-badge-warning': currentStatus === 'Pausiert'
                            }"
                        >{{ currentStatus || 'Unbekannt' }}</span>
                    </div>
                    <div class="text-sm text-[var(--dk-text-muted)] mt-1" v-if="breadcrumb">{{ breadcrumb }}</div>
                </div>
            </div>
            <!-- Avatar des ersten Verantwortlichen -->
            <div v-if="verantwortliche.length > 0" class="avatar" style="flex-shrink:0;">
                <img v-if="verantwortliche[0].foto" :src="verantwortliche[0].foto" :alt="verantwortliche[0].name" class="avatar-img" />
                <span v-else class="avatar-initials">{{ initials(verantwortliche[0].name) }}</span>
            </div>
        </div>

        <!-- Loading -->
        <div v-if="loading" class="dk-loading">
            <div class="dk-spinner"></div>
            <p class="dk-loading-text">Lade...</p>
        </div>

        <!-- Error -->
        <div v-else-if="error" class="dk-empty">
            <p class="dk-empty-title">Fehler</p>
            <p class="dk-empty-desc">{{ error }}</p>
        </div>

        <template v-else>
            <!-- Beschreibung -->
            <div class="card mb-4">
                <div class="flex items-center justify-between mb-3">
                    <h2 class="text-lg font-semibold text-[var(--dk-text)]">Details</h2>
                    <button v-if="canManage && !editingDesc" class="dk-btn dk-btn-ghost dk-btn-sm" @click="startEditDesc">
                        <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                            <path stroke-linecap="round" stroke-linejoin="round" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                        </svg>
                    </button>
                </div>
                <template v-if="!editingDesc">
                    <div class="dk-data-grid">
                        <div class="dk-data-row">
                            <span class="dk-data-label">Beschreibung</span>
                            <span class="dk-data-value">{{ currentDesc || '–' }}</span>
                        </div>
                        <div class="dk-data-row">
                            <span class="dk-data-label">Treffpunkt</span>
                            <span class="dk-data-value">{{ currentTreffpunkt || '–' }}</span>
                        </div>
                        <div class="dk-data-row">
                            <span class="dk-data-label">Treffzeit</span>
                            <span class="dk-data-value">{{ currentTreffzeit || '–' }}</span>
                        </div>
                        <div v-if="verantwortliche.length > 0" class="dk-data-row">
                            <span class="dk-data-label">Verantwortliche</span>
                            <span class="dk-data-value">{{ verantwortliche.map(v => v.name).join(', ') }}</span>
                        </div>
                    </div>
                </template>
                <template v-else>
                    <div class="flex flex-col gap-3">
                        <div>
                            <label class="text-sm font-medium text-[var(--dk-text-muted)] mb-1 block">Beschreibung</label>
                            <textarea v-model="editDesc" class="dk-form-input" rows="3" />
                        </div>
                        <div>
                            <label class="text-sm font-medium text-[var(--dk-text-muted)] mb-1 block">Treffpunkt</label>
                            <input v-model="editTreffpunkt" class="dk-form-input" type="text" />
                        </div>
                        <div>
                            <label class="text-sm font-medium text-[var(--dk-text-muted)] mb-1 block">Treffzeit</label>
                            <input v-model="editTreffzeit" class="dk-form-input" type="text" />
                        </div>
                        <div class="flex gap-2">
                            <button class="dk-btn dk-btn-primary dk-btn-sm" :disabled="savingDesc" @click="saveDesc">
                                {{ savingDesc ? 'Speichern...' : 'Speichern' }}
                            </button>
                            <button class="dk-btn dk-btn-ghost dk-btn-sm" @click="cancelEditDesc">Abbrechen</button>
                        </div>
                    </div>
                </template>
            </div>

            <!-- Aufgaben -->
            <div class="card mb-4">
                <div class="flex items-center justify-between mb-3">
                    <h2 class="text-lg font-semibold text-[var(--dk-text)]">Aufgaben</h2>
                    <button v-if="canManage" class="dk-btn dk-btn-ghost dk-btn-sm" @click="showAufgabeInput = !showAufgabeInput">+</button>
                </div>
                <!-- Neue Aufgabe Inline -->
                <div v-if="showAufgabeInput" class="flex gap-2 mb-3">
                    <input
                        v-model="neueAufgabe"
                        type="text"
                        placeholder="Neue Aufgabe..."
                        class="dk-form-input flex-1"
                        @keyup.enter="createAufgabe"
                    />
                    <button class="dk-btn dk-btn-primary dk-btn-sm" :disabled="!neueAufgabe.trim()" @click="createAufgabe">Hinzufügen</button>
                    <button class="dk-btn dk-btn-ghost dk-btn-sm" @click="showAufgabeInput = false; neueAufgabe = ''">✕</button>
                </div>
                <div v-if="aufgaben.length === 0" class="text-[var(--dk-text-muted)] text-sm">Keine Aufgaben vorhanden.</div>
                <ul v-else class="flex flex-col gap-1">
                    <li
                        v-for="a in aufgaben"
                        :key="a.name"
                        class="flex items-center gap-3 py-2 border-b border-[var(--dk-border)] last:border-0"
                    >
                        <input
                            type="checkbox"
                            :checked="a.erledigt"
                            class="accent-[var(--dk-brand-700)]"
                            @change="toggleAufgabe(a)"
                        />
                        <span :class="a.erledigt ? 'line-through text-[var(--dk-text-muted)]' : 'text-[var(--dk-text)]'" class="flex-1 text-sm">
                            {{ a.titel }}
                        </span>
                        <span v-if="a.faellig && !a.erledigt" class="text-xs text-[var(--dk-text-muted)]">{{ formatDate(a.faellig) }}</span>
                    </li>
                </ul>
            </div>

            <!-- Ankündigungen -->
            <div class="card mb-4">
                <div class="flex items-center justify-between mb-3">
                    <h2 class="text-lg font-semibold text-[var(--dk-text)]">Ankündigungen</h2>
                    <button v-if="canManage" class="dk-btn dk-btn-ghost dk-btn-sm" @click="showAnkuendigungForm = !showAnkuendigungForm">+</button>
                </div>
                <!-- Neue Ankündigung Form -->
                <div v-if="showAnkuendigungForm" class="flex flex-col gap-3 mb-4 p-3 rounded-lg bg-[var(--dk-surface-2)] border border-[var(--dk-border)]">
                    <input v-model="neueAnkuendigungTitel" type="text" placeholder="Titel" class="dk-form-input" />
                    <textarea v-model="neueAnkuendigungText" placeholder="Text (optional)" class="dk-form-input" rows="3" />
                    <div class="flex gap-2">
                        <button class="dk-btn dk-btn-primary dk-btn-sm" :disabled="!neueAnkuendigungTitel.trim()" @click="createAnkuendigung">Veröffentlichen</button>
                        <button class="dk-btn dk-btn-ghost dk-btn-sm" @click="showAnkuendigungForm = false; neueAnkuendigungTitel = ''; neueAnkuendigungText = ''">Abbrechen</button>
                    </div>
                </div>
                <div v-if="ankuendigungen.length === 0" class="text-[var(--dk-text-muted)] text-sm">Keine Ankündigungen vorhanden.</div>
                <ul v-else class="flex flex-col gap-2">
                    <li
                        v-for="a in ankuendigungen"
                        :key="a.name"
                        class="p-3 rounded-lg bg-[var(--dk-surface-2)] border border-[var(--dk-border)]"
                    >
                        <div class="flex items-center gap-2 mb-1">
                            <span v-if="a.pinned" class="dk-badge dk-badge-warning text-xs">Angepinnt</span>
                            <span class="font-medium text-[var(--dk-text)] text-sm">{{ a.titel }}</span>
                        </div>
                        <p v-if="a.text" class="text-xs text-[var(--dk-text-muted)]">{{ truncate(a.text, 100) }}</p>
                    </li>
                </ul>
            </div>

            <!-- Untergruppen (falls vorhanden) -->
            <div v-if="untergruppen.length > 0" class="card mb-4">
                <h2 class="text-lg font-semibold text-[var(--dk-text)] mb-3">Untergruppen</h2>
                <div class="flex flex-wrap gap-2">
                    <a
                        v-for="u in untergruppen"
                        :key="u.name"
                        :href="`#/gruppe/${u.name}`"
                        class="dk-badge hover:bg-[var(--dk-surface-hover)] transition cursor-pointer"
                        style="text-decoration:none;"
                    >
                        {{ u.untergruppenname || u.gruppenname || u.name }}
                    </a>
                </div>
            </div>

            <!-- Wiki Artikel -->
            <div v-if="wikiArtikel.length > 0" class="card mb-4">
                <h2 class="text-lg font-semibold text-[var(--dk-text)] mb-3">Wiki</h2>
                <ul class="flex flex-col gap-1">
                    <li v-for="w in wikiArtikel" :key="w.name">
                        <a :href="`#/wiki/${w.name}`" class="text-sm text-[var(--dk-brand-700)] hover:underline">{{ w.titel || w.name }}</a>
                    </li>
                </ul>
            </div>

            <!-- Mitglieder (für canManage) -->
            <div class="card mb-4">
                <div class="flex items-center justify-between mb-4">
                    <h2 class="text-lg font-semibold text-[var(--dk-text)]">Mitglieder</h2>
                    <span class="text-sm text-[var(--dk-text-muted)]">{{ mitglieder.length }} Mitglied(er)</span>
                </div>

                <!-- Mitglied hinzufügen (canManage) -->
                <div v-if="canManage" class="flex gap-2 mb-4">
                    <input
                        v-model="neuesMitglied"
                        type="text"
                        placeholder="Mitglieds-ID oder Name"
                        class="dk-form-input flex-1"
                        @keyup.enter="addMitglied"
                    />
                    <button class="dk-btn dk-btn-primary" :disabled="!neuesMitglied.trim()" @click="addMitglied">Hinzufügen</button>
                </div>

                <div v-if="mitglieder.length === 0" class="text-[var(--dk-text-muted)]">Keine Mitglieder vorhanden.</div>
                <div v-else class="overflow-x-auto">
                    <table class="dk-table">
                        <thead>
                            <tr>
                                <th>Name</th>
                                <th>Rolle</th>
                                <th>Status</th>
                                <th>Beitrittsdatum</th>
                                <th v-if="canManage" class="text-right">Aktionen</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr v-for="m in mitglieder" :key="m.name || m.mitglied">
                                <td class="text-[var(--dk-text)]">
                                    <a v-if="m.mitglied" :href="`#/mitglied/${m.mitglied}`" class="hover:text-[var(--dk-brand-800)] hover:underline">
                                        {{ m.vollstaendiger_name || m.name || m.mitglied }}
                                    </a>
                                    <span v-else>{{ m.vollstaendiger_name || m.name || '–' }}</span>
                                </td>
                                <td>
                                    <span v-if="!canManage" class="text-[var(--dk-text-muted)]">{{ m.rolle || '–' }}</span>
                                    <select
                                        v-else
                                        v-model="m.rolle"
                                        class="dk-form-input py-1 text-sm"
                                        @change="updateRolle(m)"
                                    >
                                        <option value="">–</option>
                                        <option value="Mitglied">Mitglied</option>
                                        <option value="Leiter">Leiter</option>
                                        <option value="Co-Leiter">Co-Leiter</option>
                                        <option value="Helfer">Helfer</option>
                                        <option value="Gast">Gast</option>
                                    </select>
                                </td>
                                <td>
                                    <span
                                        class="dk-badge"
                                        :class="{
                                            'dk-badge-success': m.status === 'Aktiv',
                                            'dk-badge-danger': m.status === 'Inaktiv',
                                            'dk-badge-warning': m.status === 'Pausiert'
                                        }"
                                    >{{ m.status || 'Unbekannt' }}</span>
                                </td>
                                <td class="text-[var(--dk-text-muted)]">{{ formatDate(m.beitrittsdatum) || '–' }}</td>
                                <td v-if="canManage" class="text-right">
                                    <button class="dk-btn dk-btn-ghost dk-btn-sm" style="color:var(--dk-danger);" @click="removeMitglied(m)">
                                        Entfernen
                                    </button>
                                </td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </template>
    </div>
</template>

<script>
import { ref, computed, onMounted } from 'vue'
import { useSession } from '../composables/useSession.js'
import { getRouteParam } from '../router.js'
import { apiCall } from '../composables/useApi.js'
import { showToast } from '../composables/useToast.js'

export default {
    name: 'GruppeDetail',
    setup() {
        const { isAdmin, user } = useSession()

        const gruppe = ref(null)
        const untergruppe = ref(null)
        const mitglieder = ref([])
        const verantwortliche = ref([])
        const untergruppen = ref([])
        const aufgaben = ref([])
        const ankuendigungen = ref([])
        const wikiArtikel = ref([])
        const loading = ref(false)
        const error = ref(null)
        const neuesMitglied = ref('')

        // Beschreibung Edit
        const editingDesc = ref(false)
        const editDesc = ref('')
        const editTreffpunkt = ref('')
        const editTreffzeit = ref('')
        const savingDesc = ref(false)

        // Aufgaben
        const showAufgabeInput = ref(false)
        const neueAufgabe = ref('')

        // Ankündigungen
        const showAnkuendigungForm = ref(false)
        const neueAnkuendigungTitel = ref('')
        const neueAnkuendigungText = ref('')

        const gruppeId = computed(() => getRouteParam('id') || window.location.hash.split('/')[2] || '')

        // Prüfe ob es eine Untergruppe ist (Untergruppe DocType hat kein gruppenname, sondern untergruppenname)
        const isUntergruppe = computed(() => !!untergruppe.value)

        const displayName = computed(() => {
            if (untergruppe.value) return untergruppe.value.untergruppenname || untergruppe.value.name || 'Gruppe'
            return gruppe.value?.gruppenname || gruppe.value?.name || 'Gruppe'
        })

        const currentStatus = computed(() => {
            if (untergruppe.value) return untergruppe.value.status
            return gruppe.value?.status
        })

        const currentDesc = computed(() => {
            if (untergruppe.value) return untergruppe.value.beschreibung
            return gruppe.value?.beschreibung
        })

        const currentTreffpunkt = computed(() => {
            if (untergruppe.value) return untergruppe.value.treffpunkt
            return gruppe.value?.treffpunkt
        })

        const currentTreffzeit = computed(() => {
            if (untergruppe.value) return untergruppe.value.treffzeit
            return gruppe.value?.treffzeit
        })

        const breadcrumb = computed(() => {
            if (untergruppe.value && untergruppe.value.gruppe) {
                return `${untergruppe.value.gruppe} > ${displayName.value}`
            }
            if (gruppe.value?.dienstbereich) {
                return `${gruppe.value.dienstbereich} > ${displayName.value}`
            }
            return null
        })

        const canManage = computed(() => {
            if (isAdmin.value) return true
            const email = user.value?.email
            if (!email) return false
            if (verantwortliche.value.some(v => v.email === email)) return true
            return false
        })

        function initials(name) {
            if (!name) return '?'
            return name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2)
        }

        function formatDate(val) {
            if (!val) return ''
            const d = new Date(val)
            if (isNaN(d.getTime())) return val
            return d.toLocaleDateString('de-DE')
        }

        function truncate(str, n) {
            if (!str) return ''
            // Strip HTML tags
            const plain = str.replace(/<[^>]+>/g, '')
            return plain.length > n ? plain.slice(0, n) + '...' : plain
        }

        async function fetchGruppe() {
            const id = gruppeId.value
            if (!id) return
            loading.value = true
            error.value = null
            try {
                // Versuche erst als Gruppe, dann als Untergruppe
                let data
                try {
                    data = await apiCall('diakronos.diakonos.api.gruppen.get_gruppe_detail', { gruppe_id: id })
                    gruppe.value = data?.gruppe || null
                    untergruppe.value = null
                } catch (e) {
                    // Evtl. Untergruppe
                    data = await apiCall('diakronos.diakonos.api.gruppen.get_untergruppe_detail', { untergruppe_id: id })
                    untergruppe.value = data?.untergruppe || null
                    gruppe.value = null
                }
                mitglieder.value = data?.mitglieder || []
                verantwortliche.value = data?.verantwortliche || []
                untergruppen.value = data?.untergruppen || []
                aufgaben.value = data?.aufgaben || []
                ankuendigungen.value = data?.ankuendigungen || []
                wikiArtikel.value = data?.wiki_artikel || []
            } catch (err) {
                error.value = err?.message || 'Fehler beim Laden'
            } finally {
                loading.value = false
            }
        }

        // --- Beschreibung Edit ---
        function startEditDesc() {
            editDesc.value = currentDesc.value || ''
            editTreffpunkt.value = currentTreffpunkt.value || ''
            editTreffzeit.value = currentTreffzeit.value || ''
            editingDesc.value = true
        }

        function cancelEditDesc() {
            editingDesc.value = false
        }

        async function saveDesc() {
            const id = gruppeId.value
            savingDesc.value = true
            try {
                const method = isUntergruppe.value
                    ? 'diakronos.diakonos.api.gruppen.update_untergruppe'
                    : 'diakronos.diakonos.api.gruppen.update_gruppe'
                const params = isUntergruppe.value
                    ? { name: id, beschreibung: editDesc.value, treffpunkt: editTreffpunkt.value, treffzeit: editTreffzeit.value }
                    : { name: id, beschreibung: editDesc.value, treffpunkt: editTreffpunkt.value, treffzeit: editTreffzeit.value }
                const res = await apiCall(method, params)
                if (res?.success) {
                    showToast('Gespeichert', 'success')
                    editingDesc.value = false
                    fetchGruppe()
                } else {
                    showToast('Fehler beim Speichern', 'error')
                }
            } catch (e) {
                showToast('Fehler beim Speichern', 'error')
            } finally {
                savingDesc.value = false
            }
        }

        // --- Aufgaben ---
        async function createAufgabe() {
            const titel = neueAufgabe.value.trim()
            if (!titel) return
            const id = gruppeId.value
            try {
                const params = isUntergruppe.value
                    ? { titel, untergruppe_id: id }
                    : { titel, gruppe_id: id }
                const res = await apiCall('diakronos.diakonos.api.gruppen.create_aufgabe', params)
                if (res?.success) {
                    neueAufgabe.value = ''
                    showAufgabeInput.value = false
                    showToast('Aufgabe erstellt', 'success')
                    fetchGruppe()
                } else {
                    showToast('Fehler beim Erstellen', 'error')
                }
            } catch (e) {
                showToast('Fehler beim Erstellen', 'error')
            }
        }

        async function toggleAufgabe(a) {
            try {
                const res = await apiCall('diakronos.diakonos.api.gruppen.toggle_aufgabe', { aufgabe_id: a.name })
                if (res?.success) {
                    a.erledigt = res.erledigt
                }
            } catch (e) {
                showToast('Fehler', 'error')
            }
        }

        // --- Ankündigungen ---
        async function createAnkuendigung() {
            const titel = neueAnkuendigungTitel.value.trim()
            if (!titel) return
            const id = gruppeId.value
            try {
                const params = isUntergruppe.value
                    ? { titel, text: neueAnkuendigungText.value, untergruppe_id: id }
                    : { titel, text: neueAnkuendigungText.value, gruppe_id: id }
                const res = await apiCall('diakronos.diakonos.api.gruppen.create_ankuendigung', params)
                if (res?.success) {
                    neueAnkuendigungTitel.value = ''
                    neueAnkuendigungText.value = ''
                    showAnkuendigungForm.value = false
                    showToast('Ankündigung veröffentlicht', 'success')
                    fetchGruppe()
                } else {
                    showToast('Fehler beim Erstellen', 'error')
                }
            } catch (e) {
                showToast('Fehler beim Erstellen', 'error')
            }
        }

        // --- Mitglieder ---
        async function addMitglied() {
            const id = gruppeId.value
            const mitglied = neuesMitglied.value.trim()
            if (!id || !mitglied) return
            try {
                const res = await apiCall('diakronos.diakonos.api.gruppen.add_mitglied_to_gruppe', {
                    gruppe_id: id,
                    mitglied_id: mitglied,
                    is_untergruppe: isUntergruppe.value,
                })
                if (res?.success) {
                    neuesMitglied.value = ''
                    showToast('Mitglied hinzugefügt', 'success')
                    fetchGruppe()
                } else {
                    showToast(res?.message || 'Fehler beim Hinzufügen', 'error')
                }
            } catch (err) {
                showToast('Fehler beim Hinzufügen', 'error')
            }
        }

        async function removeMitglied(m) {
            const id = gruppeId.value
            const mitglied_id = m.mitglied || m.name
            if (!id || !mitglied_id) return
            if (!confirm('Mitglied wirklich aus der Gruppe entfernen?')) return
            try {
                const res = await apiCall('diakronos.diakonos.api.gruppen.remove_mitglied_from_gruppe', {
                    gruppe_id: id,
                    mitglied_id: mitglied_id,
                    is_untergruppe: isUntergruppe.value,
                })
                if (res?.success) {
                    showToast('Mitglied entfernt', 'success')
                    fetchGruppe()
                } else {
                    showToast(res?.message || 'Fehler beim Entfernen', 'error')
                }
            } catch (err) {
                showToast('Fehler beim Entfernen', 'error')
            }
        }

        async function updateRolle(m) {
            const id = gruppeId.value
            const mitglied_id = m.mitglied || m.name
            if (!id || !mitglied_id) return
            try {
                const res = await apiCall('diakronos.diakonos.api.gruppen.update_mitglied_rolle', {
                    gruppe_id: id,
                    mitglied_id: mitglied_id,
                    rolle: m.rolle || '',
                    is_untergruppe: isUntergruppe.value,
                })
                if (res?.success) {
                    showToast('Rolle aktualisiert', 'success')
                } else {
                    showToast(res?.message || 'Fehler beim Aktualisieren', 'error')
                }
            } catch (err) {
                showToast('Fehler beim Aktualisieren', 'error')
            }
        }

        onMounted(() => {
            fetchGruppe()
        })

        return {
            gruppe,
            untergruppe,
            mitglieder,
            verantwortliche,
            untergruppen,
            aufgaben,
            ankuendigungen,
            wikiArtikel,
            loading,
            error,
            isAdmin,
            canManage,
            neuesMitglied,
            displayName,
            currentStatus,
            currentDesc,
            currentTreffpunkt,
            currentTreffzeit,
            breadcrumb,
            editingDesc,
            editDesc,
            editTreffpunkt,
            editTreffzeit,
            savingDesc,
            showAufgabeInput,
            neueAufgabe,
            showAnkuendigungForm,
            neueAnkuendigungTitel,
            neueAnkuendigungText,
            initials,
            formatDate,
            truncate,
            startEditDesc,
            cancelEditDesc,
            saveDesc,
            createAufgabe,
            toggleAufgabe,
            createAnkuendigung,
            addMitglied,
            removeMitglied,
            updateRolle,
        }
    },
}
</script>
