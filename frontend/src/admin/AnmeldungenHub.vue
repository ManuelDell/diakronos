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

        <template v-else>
            <!-- Aktionsleiste -->
            <div class="flex gap-2">
                <Button @click="loadData()" :loading="resource.loading">
                    Aktualisieren
                </Button>
                <Button variant="solid" @click="openNewLinkDialog">
                    + Neuer Anmeldelink
                </Button>
            </div>

            <!-- Anmeldungen -->
            <div class="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
                <h3 class="font-semibold text-gray-700 mb-3">
                    Eingegangene Anmeldungen ({{ anmeldungen.length }})
                </h3>

                <!-- Filter-Tabs -->
                <div class="flex flex-wrap gap-2 mb-4">
                    <button
                        v-for="tab in ALL_TABS"
                        :key="tab"
                        @click="activeFilter = tab"
                        :class="['px-3 py-1 rounded-full text-sm font-medium transition-colors',
                                 activeFilter === tab
                                   ? 'bg-indigo-500 text-white'
                                   : 'bg-gray-100 text-gray-700 hover:bg-gray-200']"
                    >
                        {{ tab }}
                        <span class="ml-1 text-xs opacity-70">{{ tabCount(tab) }}</span>
                    </button>
                </div>

                <div class="overflow-x-auto">
                    <table class="w-full text-sm">
                        <thead>
                            <tr class="text-left text-gray-500 border-b border-gray-100">
                                <th class="pb-2 font-medium">Name</th>
                                <th class="pb-2 font-medium">Status</th>
                                <th class="pb-2 font-medium">Typ</th>
                                <th class="pb-2 font-medium">Datum</th>
                                <th class="pb-2 font-medium">E-Mail</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr v-if="!filteredAnmeldungen.length">
                                <td colspan="5" class="py-10 text-center text-gray-400">
                                    Keine Anmeldungen vorhanden.
                                </td>
                            </tr>
                            <tr
                                v-for="a in filteredAnmeldungen"
                                :key="a.name"
                                @click="openForm('Anmeldung', a.name)"
                                class="border-b border-gray-50 hover:bg-gray-50 cursor-pointer"
                            >
                                <td class="py-3">{{ a.vorname }} {{ a.nachname }}</td>
                                <td class="py-3">
                                    <Badge :color="statusColor(a.status)" size="sm">{{ a.status }}</Badge>
                                </td>
                                <td class="py-3 text-gray-600">
                                    {{ a.anmeldungstyp === 'Mitglied-Registrierung' ? 'Mitglied' : 'Gast' }}
                                </td>
                                <td class="py-3 text-gray-600">{{ formatDate(a.anmeldedatum) }}</td>
                                <td class="py-3 text-gray-500">{{ a.email || '–' }}</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>

            <!-- Registrierungslinks -->
            <div class="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
                <h3 class="font-semibold text-gray-700 mb-3">
                    Registrierungslinks ({{ links.length }})
                </h3>
                <div class="overflow-x-auto">
                    <table class="w-full text-sm">
                        <thead>
                            <tr class="text-left text-gray-500 border-b border-gray-100">
                                <th class="pb-2 font-medium">Bezeichnung</th>
                                <th class="pb-2 font-medium">Typ</th>
                                <th class="pb-2 font-medium">Status</th>
                                <th class="pb-2 font-medium">Anmeldungen</th>
                                <th class="pb-2 font-medium">Gültig bis</th>
                                <th class="pb-2 font-medium">Aktionen</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr v-if="!links.length">
                                <td colspan="6" class="py-10 text-center text-gray-400">
                                    Keine Registrierungslinks erstellt.
                                </td>
                            </tr>
                            <tr
                                v-for="l in links"
                                :key="l.name"
                                class="border-b border-gray-50"
                            >
                                <td class="py-3 font-medium">{{ l.bezeichnung || l.name }}</td>
                                <td class="py-3 text-gray-600">
                                    {{ l.typ === 'Mitglied-Registrierung' ? 'Mitglied' : 'Gast' }}
                                </td>
                                <td class="py-3">
                                    <Badge :color="l.aktiv ? 'green' : 'gray'" size="sm">
                                        {{ l.aktiv ? 'Aktiv' : 'Inaktiv' }}
                                    </Badge>
                                </td>
                                <td class="py-3 text-gray-600">
                                    {{ l.anmeldungen_count || 0 }} / {{ l.max_anmeldungen > 0 ? l.max_anmeldungen : '∞' }}
                                </td>
                                <td class="py-3 text-gray-600">{{ l.gueltig_bis ? formatDate(l.gueltig_bis) : '–' }}</td>
                                <td class="py-3">
                                    <div class="flex gap-2">
                                        <Button size="sm" @click="copyLink(l)">Kopieren</Button>
                                        <Button size="sm" @click="openForm('Registrierungslink', l.name)">Öffnen</Button>
                                    </div>
                                </td>
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

const ALL_TABS = ['Alle', 'Anmeldeanfrage', 'Ausstehend', 'Bestätigt', 'Abgelehnt', 'Warteliste']

const STATUS_COLORS = {
    'Anmeldeanfrage': 'orange',
    'Ausstehend':     'blue',
    'Bestätigt':      'green',
    'Abgelehnt':      'red',
    'Warteliste':     'blue',
}

const activeFilter = ref('Alle')

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
            method: 'diakronos.diakonos.api.admin_hub.get_anmeldungen_hub'
        })
        resource.value.data = result.message
    } catch (err) {
        resource.value.error = err
        console.error('API Error:', err)
    } finally {
        resource.value.loading = false
    }
}

function openNewLinkDialog() {
    const d = new frappe.ui.Dialog({
        title: 'Neuen Anmeldelink erstellen',
        fields: [
            {
                fieldname: 'bezeichnung',
                label: 'Bezeichnung',
                fieldtype: 'Data',
                reqd: 1,
                placeholder: 'z.B. Herbst-Aufnahme 2026',
            },
            {
                fieldname: 'typ',
                label: 'Typ',
                fieldtype: 'Select',
                options: ['Mitglied-Registrierung', 'Gast-Anmeldung'],
                default: 'Mitglied-Registrierung',
            },
            {
                fieldname: 'gueltig_bis',
                label: 'Gültig bis (optional)',
                fieldtype: 'Date',
            },
            {
                fieldname: 'max_anmeldungen',
                label: 'Max. Anmeldungen (0 = unbegrenzt)',
                fieldtype: 'Int',
                default: 0,
            },
        ],
        primary_action_label: 'Link erstellen',
        async primary_action(values) {
            if (!values.bezeichnung?.trim()) {
                frappe.show_alert('Bezeichnung ist ein Pflichtfeld.', 3)
                return
            }
            d.set_primary_action('Wird erstellt…', () => {})
            try {
                const doc = await frappe.call({
                    method: 'frappe.client.insert',
                    args: {
                        doc: {
                            doctype: 'Registrierungslink',
                            bezeichnung: values.bezeichnung,
                            typ: values.typ,
                            aktiv: 1,
                            gueltig_bis: values.gueltig_bis || null,
                            max_anmeldungen: values.max_anmeldungen || 0,
                        },
                    },
                })
                d.hide()
                loadData()
                const url = window.location.origin + (doc.message.link_anzeige || '')
                frappe.msgprint({
                    title: `Link "${doc.message.bezeichnung}" erstellt`,
                    message: `<p>Teile diesen Link mit den Personen:</p>
                        <div style="display:flex;gap:8px;margin-top:10px;align-items:center">
                            <input id="nlu" class="form-control" value="${url}" readonly style="flex:1">
                            <button class="btn btn-sm btn-primary"
                                onclick="navigator.clipboard.writeText(document.getElementById('nlu').value);frappe.show_alert('Kopiert!',2)">
                                Kopieren
                            </button>
                        </div>`,
                    indicator: 'green',
                })
            } catch (err) {
                frappe.show_alert(err?.message || 'Fehler beim Erstellen des Links.', 4)
            } finally {
                d.set_primary_action('Link erstellen', d.primary_action)
            }
        },
    })
    d.show()
}

const anmeldungen = computed(() => resource.value.data?.anmeldungen || [])
const links       = computed(() => resource.value.data?.links || [])

const filteredAnmeldungen = computed(() =>
    activeFilter.value === 'Alle'
        ? anmeldungen.value
        : anmeldungen.value.filter(a => a.status === activeFilter.value)
)

function tabCount(tab) {
    return tab === 'Alle'
        ? anmeldungen.value.length
        : anmeldungen.value.filter(a => a.status === tab).length
}

function statusColor(s) { return STATUS_COLORS[s] || 'gray' }

function formatDate(d) {
    if (!d) return '–'
    return new Date(String(d).split(' ')[0]).toLocaleDateString('de-DE')
}

function openForm(doctype, name) {
    frappe.set_route('Form', doctype, name)
}

function copyLink(l) {
    const url = window.location.origin + (l.link_anzeige || '')
    navigator.clipboard.writeText(url).then(() => frappe.show_alert('Link kopiert!', 3))
}



function refresh() { loadData() }

function onPageShow(e) {
    if (e.detail === 'anmeldungen') loadData()
}

onMounted(() => {
    loadData()
    document.addEventListener('diakonos:page-show', onPageShow)
})
onUnmounted(() => document.removeEventListener('diakonos:page-show', onPageShow))

defineExpose({ refresh })
</script>
