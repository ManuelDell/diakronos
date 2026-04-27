<template>
    <div class="dk-screen dk-screen-enter">
        <h1 class="text-2xl font-bold mb-4">Adressbuch</h1>

        <!-- Suchfeld -->
        <div class="mb-4">
            <input
                v-model="search"
                type="text"
                placeholder="Suchen nach Name, E-Mail oder Ort..."
                class="dk-form-input max-w-md"
            />
        </div>

        <!-- Tabelle -->
        <div class="overflow-x-auto dk-card">
            <table class="dk-table">
                <thead>
                    <tr>
                        <th>Name</th>
                        <th>E-Mail</th>
                        <th>Telefon</th>
                        <th>PLZ</th>
                        <th>Ort</th>
                    </tr>
                </thead>
                <tbody>
                    <tr v-if="loading">
                        <td colspan="5">
                            <div class="dk-list-empty" style="padding:40px 32px">Laden...</div>
                        </td>
                    </tr>
                    <tr v-else-if="error">
                        <td colspan="5">
                            <div class="dk-list-empty" style="padding:40px 32px;color:var(--dk-danger)">{{ error }}</div>
                        </td>
                    </tr>
                    <tr v-else-if="filteredMitglieder.length === 0">
                        <td colspan="5">
                            <div class="dk-list-empty" style="padding:40px 32px">Keine Einträge gefunden.</div>
                        </td>
                    </tr>
                    <tr
                        v-for="m in filteredMitglieder"
                        :key="m.name"
                    >
                        <td class="font-medium text-[var(--dk-text)]">
                            {{ m.vorname }} {{ m.nachname }}
                        </td>
                        <td class="text-[var(--dk-text-muted)]">{{ m.email || '-' }}</td>
                        <td class="text-[var(--dk-text-muted)]">{{ m.telefonnummer || '-' }}</td>
                        <td class="text-[var(--dk-text-muted)]">{{ m.postleitzahl || '-' }}</td>
                        <td class="text-[var(--dk-text-muted)]">{{ m.wohnort || '-' }}</td>
                    </tr>
                </tbody>
            </table>
        </div>
    </div>
</template>

<script>
import { ref, computed, watch, onMounted } from 'vue'
import { apiCall } from '../composables/useApi.js'

export default {
    name: 'Adressbuch',
    setup() {
        const mitglieder = ref([])
        const loading = ref(false)
        const error = ref(null)
        const search = ref('')

        async function loadMitglieder() {
            loading.value = true
            error.value = null
            try {
                const payload = await apiCall('diakronos.diakonos.api.mitglieder.get_mitglieder_liste', {
                    start: 0,
                    limit: 100,
                    suche: search.value || undefined,
                })
                mitglieder.value = payload?.data || []
            } catch (err) {
                error.value = err?.message || 'Fehler beim Laden der Mitglieder'
                console.error('Adressbuch loadMitglieder error:', err)
            } finally {
                loading.value = false
            }
        }

        const filteredMitglieder = computed(() => {
            const q = search.value.toLowerCase().trim()
            if (!q) return mitglieder.value
            return mitglieder.value.filter((m) => {
                const name = `${m.vorname || ''} ${m.nachname || ''}`.toLowerCase()
                const email = (m.email || '').toLowerCase()
                const ort = (m.wohnort || '').toLowerCase()
                return name.includes(q) || email.includes(q) || ort.includes(q)
            })
        })

        // Debounce-Suche (300 ms)
        let debounceTimer = null
        watch(search, () => {
            clearTimeout(debounceTimer)
            debounceTimer = setTimeout(() => {
                loadMitglieder()
            }, 300)
        })

        onMounted(() => {
            loadMitglieder()
        })

        return {
            search,
            loading,
            error,
            filteredMitglieder,
        }
    },
}
</script>
