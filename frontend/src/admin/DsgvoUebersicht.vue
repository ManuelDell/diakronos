<template>
    <div data-diakonos-app class="p-4 space-y-4">

        <!-- Loading -->
        <div v-if="resource.loading && !resource.data" class="flex items-center justify-center py-20 text-gray-400">
            <Spinner class="w-5 h-5 mr-2" />
            Daten werden geladen…
        </div>

        <!-- Error -->
        <div v-else-if="resource.error" class="bg-red-50 border border-red-200 text-red-700 rounded-lg p-4 text-sm">
            <strong>Fehler beim Laden der Daten:</strong><br>
            <pre class="mt-2 text-xs whitespace-pre-wrap">{{ JSON.stringify(resource.error, null, 2) }}</pre>
        </div>

        <template v-else-if="resource.data">
            <!-- Aktualisieren -->
            <div class="flex">
                <Button @click="loadData()" :loading="resource.loading">Aktualisieren</Button>
            </div>

            <!-- Stat-Karten -->
            <div class="grid grid-cols-2 gap-4 sm:grid-cols-4">
                <StatCard label="Gesamt Mitglieder" :value="stats.gesamt" color="#6366f1" />
                <StatCard label="Einwilligung erteilt" :value="stats.ok"        color="#10b981" />
                <StatCard label="Ohne Einwilligung"   :value="stats.fehlt"     color="#f59e0b" />
                <StatCard label="Widerrufen"           :value="stats.widerrufen" color="#ef4444" />
            </div>

            <!-- Mitglieder-Tabelle -->
            <div class="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
                <h3 class="font-semibold text-gray-700 mb-3">Datenschutz-Status aller Mitglieder</h3>
                <div class="overflow-x-auto">
                    <table class="w-full text-sm">
                        <thead>
                            <tr class="text-left text-gray-500 border-b border-gray-100">
                                <th class="pb-2 font-medium">Name</th>
                                <th class="pb-2 font-medium">Status</th>
                                <th class="pb-2 font-medium">DSGVO</th>
                                <th class="pb-2 font-medium">Einwilligung am</th>
                                <th class="pb-2 font-medium">E-Mail</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr v-if="!mitglieder.length">
                                <td colspan="5" class="py-10 text-center text-gray-400">Keine Mitglieder gefunden.</td>
                            </tr>
                            <tr
                                v-for="m in mitglieder"
                                :key="m.name"
                                @click="openMitglied(m.name)"
                                :class="['border-b border-gray-50 cursor-pointer',
                                         m.dsgvo_status === 'fehlt' ? 'bg-red-50 hover:bg-red-100' :
                                         m.dsgvo_status === 'widerrufen' ? 'bg-amber-50 hover:bg-amber-100' :
                                         'hover:bg-gray-50']"
                            >
                                <td class="py-3 font-medium">{{ m.vorname }} {{ m.nachname }}</td>
                                <td class="py-3 text-gray-600">{{ m.status || '–' }}</td>
                                <td class="py-3">
                                    <Badge :color="dsgvoBadgeColor(m.dsgvo_status)" size="sm">
                                        {{ dsgvoBadgeLabel(m.dsgvo_status) }}
                                    </Badge>
                                </td>
                                <td class="py-3 text-gray-600">{{ m.dsgvo_datum ? formatDate(m.dsgvo_datum) : '–' }}</td>
                                <td class="py-3 text-gray-500">{{ m.email || '–' }}</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </template>
    </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { Button, Badge, Spinner } from 'frappe-ui'
import StatCard from './StatCard.vue'

const resource = ref({
    loading: true,
    data: null,
    error: null,
})

async function loadData() {
    resource.value.loading = true
    resource.value.error = null
    try {
        const result = await frappe.call({
            method: 'diakronos.diakonos.api.admin_hub.get_dsgvo_uebersicht'
        })
        resource.value.data = result.message
    } catch (err) {
        resource.value.error = err
        console.error('API Error:', err)
    } finally {
        resource.value.loading = false
    }
}

const stats     = computed(() => resource.value.data?.stats || { gesamt: 0, ok: 0, fehlt: 0, widerrufen: 0 })
const mitglieder = computed(() => resource.value.data?.mitglieder || [])

function dsgvoBadgeColor(s) {
    if (s === 'ok')         return 'green'
    if (s === 'widerrufen') return 'orange'
    return 'red'
}

function dsgvoBadgeLabel(s) {
    if (s === 'ok')         return 'Erteilt'
    if (s === 'widerrufen') return 'Widerrufen'
    return 'Fehlt'
}

function formatDate(d) {
    return new Date(String(d).split(' ')[0]).toLocaleDateString('de-DE')
}

function openMitglied(name) {
    frappe.set_route('Form', 'Mitglied', name)
}

function refresh() { loadData() }

function onPageShow(e) {
    if (e.detail === 'dsgvo') loadData()
}

onMounted(() => {
    loadData()
    document.addEventListener('diakonos:page-show', onPageShow)
})
onUnmounted(() => document.removeEventListener('diakonos:page-show', onPageShow))

defineExpose({ refresh })
</script>
