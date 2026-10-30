import { computed } from 'vue'
const OFFENE_ANMELDESTATI = ['Anmeldeanfrage', 'Ausstehend']

const STATUS_LEITER = [
  { wert: 'alle',      label: 'Alle',         leer: 'Keine Anfragen vorhanden' },
  { wert: 'offen',     label: 'Offen',        leer: 'Keine offenen Anfragen' },
  { wert: 'genehmigt', label: 'Aufgenommen',  leer: 'Keine aufgenommenen Anfragen' },
  { wert: 'abgelehnt', label: 'Abgelehnt',    leer: 'Keine abgelehnten Anfragen' },
]

function istOffen(a) {
  return OFFENE_ANMELDESTATI.includes(a.status)
}

const filteredAnmeldungen = computed(() => {
  if (statusFilter.value === 'offen') return anmeldungen.value.filter(istOffen)
  if (statusFilter.value === 'genehmigt') return anmeldungen.value.filter(a => a.status === 'Bestätigt')
  if (statusFilter.value === 'abgelehnt') return anmeldungen.value.filter(a => a.status === 'Abgelehnt')
  return anmeldungen.value
})
export { STATUS_LEITER, filteredAnmeldungen, istOffen }
