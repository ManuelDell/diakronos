<template>
    <div data-diakonos-app class="p-4 space-y-4">

        <!-- Loading -->
        <div v-if="resource.loading && !resource.data" class="flex items-center justify-center py-20 text-gray-400">
            <Spinner class="w-5 h-5 mr-2" />
            Daten werden geladen…
        </div>

        <!-- Error -->
        <div v-else-if="resource.error" class="bg-red-50 border border-red-200 text-red-700 rounded-lg p-4 text-sm">
            <strong>Fehler beim Laden der Statistik:</strong><br>
            <pre class="mt-2 text-xs whitespace-pre-wrap">{{ JSON.stringify(resource.error, null, 2) }}</pre>
        </div>

        <template v-else-if="resource.data">
            <!-- Aktualisieren -->
            <div class="flex">
                <Button @click="loadData()" :loading="resource.loading">Aktualisieren</Button>
            </div>

            <!-- KPI-Karten -->
            <div class="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
                <StatCard label="Mitglieder gesamt" :value="m.gesamt"             color="#6366f1" />
                <StatCard label="Aktive Mitglieder" :value="m.mitglied"           color="#10b981" sub="Status: Mitglied" />
                <StatCard label="Gäste"             :value="m.gast"               color="#f59e0b" sub="Status: Gast" />
                <StatCard label="Kinder"            :value="m.kind"               color="#3b82f6" sub="Status: Kind" />
                <StatCard label="Inaktiv / Archiv"  :value="(m.inaktiv||0)+(m.archiviert||0)" color="#9ca3af" />
            </div>

            <!-- Zwei Spalten: Mitglieder-Status + DSGVO -->
            <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">

                <div class="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
                    <h3 class="font-semibold text-gray-700 mb-4 pb-2 border-b border-gray-100">Mitglieder nach Status</h3>
                    <ProgressBar label="Mitglied"   :value="m.mitglied"       :total="m.gesamt" color="#10b981" />
                    <ProgressBar label="Gast"       :value="m.gast"           :total="m.gesamt" color="#f59e0b" />
                    <ProgressBar label="Kind"       :value="m.kind"           :total="m.gesamt" color="#3b82f6" />
                    <ProgressBar label="Inaktiv"    :value="m.inaktiv||0"     :total="m.gesamt" color="#9ca3af" />
                    <ProgressBar label="Archiviert" :value="m.archiviert||0"  :total="m.gesamt" color="#ef4444" />
                </div>

                <div class="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
                    <h3 class="font-semibold text-gray-700 mb-4 pb-2 border-b border-gray-100">DSGVO-Status</h3>
                    <ProgressBar label="Einwilligung erteilt" :value="dsgvo.ok"         :total="m.gesamt" color="#10b981" />
                    <ProgressBar label="Widerrufen"           :value="dsgvo.widerrufen"  :total="m.gesamt" color="#f59e0b" />
                    <ProgressBar label="Fehlt"                :value="dsgvo.fehlt"       :total="m.gesamt" color="#ef4444" />
                    <div class="mt-4 pt-3 border-t border-gray-100 flex justify-between items-center">
                        <span class="text-sm text-gray-500">Compliance-Rate</span>
                        <span class="font-bold text-sm" :style="{ color: complianceColor }">
                            {{ compliancePct }}%
                        </span>
                    </div>
                </div>
            </div>

            <!-- Zwei Spalten: Anmeldungen + Links -->
            <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">

                <div class="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
                    <h3 class="font-semibold text-gray-700 mb-4 pb-2 border-b border-gray-100">Anmeldungen</h3>
                    <div class="flex justify-around mb-4">
                        <MiniStat :value="anm.gesamt"      label="Gesamt"       color="#6366f1" />
                        <MiniStat :value="anm.diesen_monat" label="Diesen Monat" color="#10b981" />
                        <MiniStat :value="anm.offen"        label="Offen"        color="#f59e0b" />
                    </div>
                    <div
                        v-for="(count, status) in (anm.nach_status || {})"
                        :key="status"
                        class="flex justify-between items-center py-2 border-b border-gray-50 last:border-0"
                    >
                        <span class="text-sm text-gray-700">{{ status }}</span>
                        <span class="font-bold text-sm" :style="{ color: statusColor(status) }">{{ count }}</span>
                    </div>
                </div>

                <div class="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
                    <h3 class="font-semibold text-gray-700 mb-4 pb-2 border-b border-gray-100">Registrierungslinks</h3>
                    <div class="flex justify-around mb-4">
                        <MiniStat :value="links.aktiv"             label="Aktiv"      color="#10b981" />
                        <MiniStat :value="links.inaktiv"           label="Inaktiv"    color="#9ca3af" />
                        <MiniStat :value="links.gesamt_anmeldungen" label="Anmeldungen" color="#6366f1" />
                    </div>
                    <div
                        v-for="l in (links.top || [])"
                        :key="l.name"
                        class="flex justify-between items-center py-2 border-b border-gray-50 last:border-0"
                    >
                        <span class="text-sm text-gray-700 truncate mr-2">{{ l.bezeichnung || l.name }}</span>
                        <span class="font-semibold text-sm text-indigo-500 shrink-0">{{ l.anmeldungen_count }} Anm.</span>
                    </div>
                    <div v-if="!(links.top?.length)" class="text-sm text-gray-400">Keine Links</div>
                </div>
            </div>
        </template>
    </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { Button, Spinner } from 'frappe-ui'
import StatCard from './StatCard.vue'
import ProgressBar from './ProgressBar.vue'
import MiniStat from './MiniStat.vue'

const STATUS_COLORS = {
    'Anmeldeanfrage': '#f59e0b',
    'Ausstehend':     '#6366f1',
    'Bestätigt':      '#10b981',
    'Abgelehnt':      '#ef4444',
    'Warteliste':     '#3b82f6',
}

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
            method: 'diakronos.diakonos.api.admin_hub.get_statistik'
        })
        resource.value.data = result.message
    } catch (err) {
        resource.value.error = err
        console.error('API Error:', err)
    } finally {
        resource.value.loading = false
    }
}

const m     = computed(() => resource.value.data?.mitglieder || {})
const dsgvo = computed(() => resource.value.data?.dsgvo || {})
const anm   = computed(() => resource.value.data?.anmeldungen || {})
const links = computed(() => resource.value.data?.links || {})

const compliancePct = computed(() =>
    m.value.gesamt > 0 ? Math.round((dsgvo.value.ok / m.value.gesamt) * 100) : 0
)
const complianceColor = computed(() => compliancePct.value >= 90 ? '#10b981' : '#ef4444')

function statusColor(s) { return STATUS_COLORS[s] || '#6b7280' }

function refresh() { loadData() }

function onPageShow(e) {
    if (e.detail === 'statistik') loadData()
}

onMounted(() => {
    loadData()
    document.addEventListener('diakonos:page-show', onPageShow)
})
onUnmounted(() => document.removeEventListener('diakonos:page-show', onPageShow))

defineExpose({ refresh })
</script>
