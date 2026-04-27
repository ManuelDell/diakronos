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
                    <h1 class="dk-screen-title">{{ gruppe?.gruppenname || 'Gruppe' }}</h1>
                    <div class="flex items-center gap-2 mt-1">
                        <span
                            class="dk-badge"
                            :class="{
                                'dk-badge-success': gruppe?.status === 'Aktiv',
                                'dk-badge-danger': gruppe?.status === 'Inaktiv',
                                'dk-badge-warning': gruppe?.status === 'Pausiert'
                            }"
                        >
                            {{ gruppe?.status || 'Unbekannt' }}
                        </span>
                        <span v-if="gruppe?.dienstbereich" class="dk-badge">
                            {{ gruppe.dienstbereich }}
                        </span>
                        <span v-if="isAdminMode" class="dk-badge dk-badge-brand">
                            Admin-Mode
                        </span>
                    </div>
                </div>
            </div>
        </div>

        <!-- Details -->
        <div class="dk-card p-5 mb-6">
            <h2 class="text-lg font-semibold text-[var(--dk-text)] mb-4">Details</h2>
            <div class="dk-data-grid">
                <div class="dk-data-row">
                    <span class="dk-data-label">Beschreibung</span>
                    <span class="dk-data-value">{{ gruppe?.beschreibung || '\u2013' }}</span>
                </div>
                <div class="dk-data-row">
                    <span class="dk-data-label">Treffpunkt</span>
                    <span class="dk-data-value">{{ gruppe?.treffpunkt || '\u2013' }}</span>
                </div>
                <div class="dk-data-row">
                    <span class="dk-data-label">Treffzeit</span>
                    <span class="dk-data-value">{{ gruppe?.treffzeit || '\u2013' }}</span>
                </div>
            </div>
        </div>

        <!-- Verantwortliche -->
        <div class="dk-card p-5 mb-6">
            <h2 class="text-lg font-semibold text-[var(--dk-text)] mb-4">Verantwortliche</h2>
            <div v-if="verantwortliche.length === 0" class="text-[var(--dk-text-muted)]">Keine Verantwortlichen zugewiesen.</div>
            <div v-else class="dk-list">
                <div v-for="v in verantwortliche" :key="v.name || v.verantwortlicher" class="dk-list-item">
                    <div class="font-medium text-[var(--dk-text)]">{{ v.vollstaendiger_name || v.name || v.verantwortlicher }}</div>
                    <div v-if="v.rolle" class="text-sm text-[var(--dk-text-muted)]">{{ v.rolle }}</div>
                </div>
            </div>
        </div>

        <!-- Untergruppen -->
        <div class="dk-card p-5 mb-6">
            <h2 class="text-lg font-semibold text-[var(--dk-text)] mb-4">Untergruppen</h2>
            <div v-if="untergruppen.length === 0" class="text-[var(--dk-text-muted)]">Keine Untergruppen vorhanden.</div>
            <div v-else class="dk-list">
                <a
                    v-for="u in untergruppen"
                    :key="u.name"
                    :href="`#/gruppe/${u.name}`"
                    class="dk-list-item hover:bg-[var(--dk-surface-hover)] transition cursor-pointer"
                >
                    <div class="flex-1">
                        <div class="font-medium text-[var(--dk-text)]">{{ u.gruppenname || u.name }}</div>
                        <div v-if="u.beschreibung" class="text-sm text-[var(--dk-text-muted)]">{{ u.beschreibung }}</div>
                    </div>
                    <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 text-[var(--dk-text-subtle)]" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                        <path stroke-linecap="round" stroke-linejoin="round" d="M9 5l7 7-7 7" />
                    </svg>
                </a>
            </div>
        </div>

        <!-- Mitglieder -->
        <div class="dk-card p-5 mb-6">
            <div class="flex items-center justify-between mb-4">
                <h2 class="text-lg font-semibold text-[var(--dk-text)]">Mitglieder</h2>
                <span class="text-sm text-[var(--dk-text-muted)]">{{ mitglieder.length }} Mitglied(er)</span>
            </div>

            <!-- Mitglied hinzuf\u00fcgen (nur Admin-Mode) -->
            <div v-if="isAdminMode" class="flex gap-2 mb-4">
                <input
                    v-model="neuesMitglied"
                    type="text"
                    placeholder="Mitglieds-ID oder Name"
                    class="dk-form-input flex-1"
                    @keyup.enter="addMitglied"
                />
                <button class="dk-btn dk-btn-primary" :disabled="!neuesMitglied.trim()" @click="addMitglied">
                    Hinzuf\u00fcgen
                </button>
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
                            <th v-if="isAdminMode" class="text-right">Aktionen</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr v-for="m in mitglieder" :key="m.name || m.mitglied">
                            <td class="text-[var(--dk-text)]">
                                <a v-if="m.mitglied" :href="`#/mitglied/${m.mitglied}`" class="hover:text-[var(--dk-brand-800)] hover:underline">
                                    {{ m.vollstaendiger_name || m.mitglied }}
                                </a>
                                <span v-else>{{ m.vollstaendiger_name || m.name || '\u2013' }}</span>
                            </td>
                            <td>
                                <span v-if="!isAdminMode" class="text-[var(--dk-text-muted)]">{{ m.rolle || '\u2013' }}</span>
                                <select
                                    v-else
                                    v-model="m.rolle"
                                    class="dk-form-input py-1 text-sm"
                                    @change="updateRolle(m)"
                                >
                                    <option value="">\u2013</option>
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
                                >
                                    {{ m.status || 'Unbekannt' }}
                                </span>
                            </td>
                            <td class="text-[var(--dk-text-muted)]">{{ formatDate(m.beitrittsdatum) || '\u2013' }}</td>
                            <td v-if="isAdminMode" class="text-right">
                                <button class="text-[var(--dk-danger)] hover:opacity-80 text-sm font-medium" @click="removeMitglied(m)">
                                    Entfernen
                                </button>
                            </td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </div>
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
        const { isAdminMode } = useSession()

        const gruppe = ref(null)
        const mitglieder = ref([])
        const verantwortliche = ref([])
        const untergruppen = ref([])
        const loading = ref(false)
        const error = ref(null)
        const neuesMitglied = ref('')

        const gruppeId = computed(() => getRouteParam('id') || window.location.hash.split('/')[2] || '')

        function formatDate(val) {
            if (!val) return ''
            const d = new Date(val)
            if (isNaN(d.getTime())) return val
            return d.toLocaleDateString('de-DE')
        }

        async function fetchGruppe() {
            const id = gruppeId.value
            if (!id) return
            loading.value = true
            try {
                const data = await apiCall('diakronos.diakonos.api.gruppen.get_gruppe_detail', { gruppe_id: id })
                gruppe.value = data?.gruppe || data
                mitglieder.value = data?.mitglieder || []
                verantwortliche.value = data?.verantwortliche || []
                untergruppen.value = data?.untergruppen || []
            } catch (err) {
                error.value = err?.message || 'Fehler beim Laden'
            } finally {
                loading.value = false
            }
        }

        async function addMitglied() {
            if (!isAdminMode.value) return
            const id = gruppeId.value
            const mitglied = neuesMitglied.value.trim()
            if (!id || !mitglied) return
            try {
                const res = await apiCall('diakronos.diakonos.api.gruppen.add_mitglied_to_gruppe', {
                    gruppe_id: id,
                    mitglied_id: mitglied,
                })
                if (res?.success) {
                    neuesMitglied.value = ''
                    showToast('Mitglied hinzugef\u00fcgt', 'success')
                    fetchGruppe()
                } else {
                    showToast(res?.message || 'Fehler beim Hinzuf\u00fcgen', 'error')
                }
            } catch (err) {
                showToast('Fehler beim Hinzuf\u00fcgen', 'error')
            }
        }

        async function removeMitglied(m) {
            if (!isAdminMode.value) return
            const id = gruppeId.value
            const mitglied_id = m.mitglied || m.name
            if (!id || !mitglied_id) return
            if (!confirm('Mitglied wirklich aus der Gruppe entfernen?')) return
            try {
                const res = await apiCall('diakronos.diakonos.api.gruppen.remove_mitglied_from_gruppe', {
                    gruppe_id: id,
                    mitglied_id: mitglied_id,
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
            if (!isAdminMode.value) return
            const id = gruppeId.value
            const mitglied_id = m.mitglied || m.name
            if (!id || !mitglied_id) return
            try {
                const res = await apiCall('diakronos.diakonos.api.gruppen.update_mitglied_rolle', {
                    gruppe_id: id,
                    mitglied_id: mitglied_id,
                    rolle: m.rolle || '',
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
            mitglieder,
            verantwortliche,
            untergruppen,
            loading,
            error,
            isAdminMode,
            neuesMitglied,
            formatDate,
            addMitglied,
            removeMitglied,
            updateRolle,
        }
    },
}
</script>
