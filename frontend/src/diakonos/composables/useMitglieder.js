import { ref, computed, watch } from 'vue'
import { apiCall } from './useApi.js'

const mitglieder = ref([])
const loading = ref(false)
const error = ref(null)
const hasMore = ref(true)
/** UXD-R14: Gesamtzahl aus der Server-Antwort (`total`), nicht aus den
 *  geladenen Zeilen. `mitglieder.length` bleibt die Anzeige-Zahl. */
const gesamt = ref(0)
/** N11b/K1: Gesamtzahl OHNE Statusfilter — fuer die Beschriftung „Alle n“.
 *  `gesamt` ist das `total` der gefilterten Abfrage und stand bei aktivem
 *  Statusfilter faelschlich auch an „Alle“. */
const gesamtAlle = ref(0)

const searchQuery = ref('')
const statusFilter = ref('')
const sortBy = ref('full_name')
const sortOrder = ref('asc')
/** N11/Befund 10: Statuszahlen kommen vom SERVER ueber alle sichtbaren
 *  Mitglieder (nicht mehr aus den geladenen Zeilen — bei Seitengroesse 30
 *  waren sie schlicht falsch). */
const statusZaehler = ref({})
/** W7: Erst wenn der Admin bewusst anzeigt, fordert die Liste persönliche
 *  Daten beim Server an. Vorgabe aus — der Server liefert sie sonst gar nicht. */
const persoenlicheDaten = ref(false)

const privateFelder = ['email', 'telefonnummer', 'telefon', 'geburtstag', 'postleitzahl', 'wohnort', 'strasse', 'straße', 'nummer']
function ohnePersoenlicheDaten(zeile) {
    const kopie = { ...zeile }
    for (const feld of privateFelder) kopie[feld] = null
    return kopie
}

export function persoenlicheDatenZuruecksetzen() {
    persoenlicheDaten.value = false
    mitglieder.value = mitglieder.value.map(ohnePersoenlicheDaten)
}

const limit = 30
let currentStart = 0

async function loadMitglieder({ start = 0, append = false } = {}) {
    if (loading.value) return

    loading.value = true
    error.value = null

    try {
        const data = await apiCall('diakronos.diakonos.api.mitglieder.get_mitglieder_liste', {
            start,
            limit,
            suche: searchQuery.value || undefined,
            status: statusFilter.value || undefined,
            sort_by: sortBy.value,
            sort_order: sortOrder.value,
            persoenliche_daten: persoenlicheDaten.value === true,
        })

        const payload = data || {}
        const rows = (payload.data || []).map(row => persoenlicheDaten.value ? row : ohnePersoenlicheDaten(row))

        if (append) {
            mitglieder.value.push(...rows)
        } else {
            mitglieder.value = rows
        }

        // UXD-R14: Gesamtzahl serverseitig (dieselbe Filterung wie die Liste).
        if (typeof payload.total === 'number') {
            gesamt.value = payload.total
        } else {
            gesamt.value = mitglieder.value.length
        }

        // N11/Befund 10: Statuszahlen je Status aus der Server-Antwort.
        if (payload.status_zaehler && typeof payload.status_zaehler === 'object') {
            statusZaehler.value = { ...payload.status_zaehler }
        }
        // N11b/K1: Gesamtzahl ohne Statusfilter (Beschriftung „Alle n“).
        if (typeof payload.gesamt_alle === 'number') {
            gesamtAlle.value = payload.gesamt_alle
        }

        currentStart = start + rows.length
        hasMore.value = rows.length === limit && currentStart < gesamt.value
    } catch (err) {
        error.value = err?.message || 'Fehler beim Laden der Mitglieder'
        console.error('loadMitglieder error:', err)
    } finally {
        loading.value = false
    }
}

function reload() {
    currentStart = 0
    hasMore.value = true
    return loadMitglieder({ start: 0, append: false })
}

function loadMore() {
    if (!hasMore.value || loading.value) return
    return loadMitglieder({ start: currentStart, append: true })
}

// Auto-reload when filters or sorting change
watch([searchQuery, statusFilter, sortBy, sortOrder, persoenlicheDaten], () => {
    reload()
}, { flush: 'post' })

export function useMitglieder() {
    return {
        mitglieder: computed(() => mitglieder.value),
        gesamt: computed(() => gesamt.value),
        gesamtAlle: computed(() => gesamtAlle.value),
        statusZaehler: computed(() => statusZaehler.value),
        loading: computed(() => loading.value),
        error: computed(() => error.value),
        hasMore: computed(() => hasMore.value),
        searchQuery,
        statusFilter,
        sortBy,
        sortOrder,
        persoenlicheDaten,
        reload,
        loadMore,
    }
}
