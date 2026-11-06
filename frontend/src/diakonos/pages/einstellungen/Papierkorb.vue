<template>
  <div class="pk-abschnitt">
    <h2>Papierkorb</h2>
    <p class="pk-hilfe">
      Gelöschte Einträge bleiben {{ aufbewahrung }} Tage hier und lassen sich in
      dieser Zeit zurückholen. Danach entfernt der Server sie endgültig — samt
      Anhängen und Kind-Einträgen.
    </p>

    <DkSkelett v-if="laedt" form="tabelle" :anzahl="5" text="Papierkorb wird geladen …" />
    <DkHint v-if="fehler" variant="err" role="alert">{{ fehler }}</DkHint>
    <DkButton v-if="!geladen && !laedt" variant="secondary" @click="laden">Erneut versuchen</DkButton>

    <DkTable
      v-if="geladen"
      :spalten="spalten"
      :leer="eintraege.length === 0"
      leer-titel="Der Papierkorb ist leer."
      leer-text="Gelöschte Beiträge, Termine, Gruppen, Wiki-Seiten und Lieder erscheinen hier."
    >
      <tr v-for="e in zeilen" :key="e.doctype + ':' + e.name">
        <td class="pk-bereich">{{ e.bereich }}</td>
        <td><strong>{{ e.titel || e.name }}</strong></td>
        <td class="pk-datum">{{ e.geloescht_amText }}</td>
        <td class="dk-text-muted">{{ e.geloescht_von || '—' }}</td>
        <td class="pk-datum">{{ e.laeuft_ab_amText || '—' }}</td>
        <td class="pk-aktion">
          <DkButton
            variant="secondary"
            :loading="zurueckLaeuft === e.name"
            @click="zurueckholen(e)"
          >Wiederherstellen</DkButton>
        </td>
      </tr>
    </DkTable>
  </div>
</template>

<script setup>
/**
 * UX2b — Papierkorb (nur Administration).
 *
 * Zeigt, was in den letzten 7 Tagen gelöscht wurde, wer es gelöscht hat und
 * wann es endgültig verschwindet. „Wiederherstellen“ ruft den
 * bereichsrichtigen Endpunkt (`<bereich>.wiederherstellen_*`) — dieselbe
 * Wahrheit wie beim Rückgängig-Knopf der Meldung (`composables/papierkorb.mjs`).
 */
import { computed, onMounted, ref } from 'vue'
import { apiCall } from '../../composables/useApi.js'
import { showToast } from '../../composables/useToast.js'
import { wiederherstellen } from '../../composables/papierkorb.mjs'
import DkButton from '../../components/ui/DkButton.vue'
import DkHint from '../../components/ui/DkHint.vue'
import DkTable from '../../components/ui/DkTable.vue'
import DkSkelett from '../../components/ui/DkSkelett.vue'

//: Bereich der Server-Liste -> Schlüssel von `WIEDERHERSTELLEN`.
const BEREICH_ZU_SCHLUESSEL = {
  Beitrag: 'beitrag',
  Termin: 'termin',
  Gruppe: 'gruppe',
  'Wiki-Seite': 'artikel',
  Lied: 'lied',
}

const spalten = [
  { key: 'bereich', label: 'Bereich' },
  { key: 'titel', label: 'Eintrag' },
  // Datumsspalten breit genug, dass „04.11.2026, 15:24“ in EINER Zeile steht.
  { key: 'geloescht_am', label: 'Gelöscht am', width: '170px' },
  { key: 'geloescht_von', label: 'Von' },
  { key: 'laeuft_ab_am', label: 'Verschwindet am', width: '170px' },
  { key: 'aktion', label: '', aktion: true },
]

const laedt = ref(true)
const geladen = ref(false)
const fehler = ref('')
const aufbewahrung = ref(7)
const eintraege = ref([])
const zurueckLaeuft = ref('')

const zeilen = computed(() =>
  eintraege.value.map((e) => ({
    ...e,
    geloescht_amText: datumZeit(e.geloescht_am),
    laeuft_ab_amText: datumZeit(e.laeuft_ab_am),
  }))
)

/** Serverseitiges „JJJJ-MM-TT HH:MM:SS“ als deutsches Datum mit Uhrzeit. */
function datumZeit(wert) {
  const roh = String(wert || '').trim()
  if (!roh) return ''
  const m = /^(\d{4})-(\d{2})-(\d{2})(?:[ T](\d{2}):(\d{2}))?/.exec(roh)
  if (!m) return roh
  const [, jahr, monat, tag, stunde, minute] = m
  const datum = `${tag}.${monat}.${jahr}`
  return stunde ? `${datum}, ${stunde}:${minute}` : datum
}

async function laden() {
  laedt.value = true
  fehler.value = ''
  try {
    const antwort = await apiCall('diakronos_app.api.papierkorb.liste', {})
    aufbewahrung.value = antwort?.aufbewahrung_tage ?? 7
    eintraege.value = Array.isArray(antwort?.eintraege) ? antwort.eintraege : []
    geladen.value = true
  } catch (err) {
    fehler.value = err?.message || 'Der Papierkorb konnte nicht geladen werden.'
  } finally {
    laedt.value = false
  }
}

async function zurueckholen(zeile) {
  const schluessel = BEREICH_ZU_SCHLUESSEL[zeile.bereich]
  if (!schluessel) return
  zurueckLaeuft.value = zeile.name
  const ergebnis = await wiederherstellen(schluessel, zeile.name)
  zurueckLaeuft.value = ''
  if (!ergebnis.ok) {
    showToast(ergebnis.fehler, 'error')
    return
  }
  showToast(`„${zeile.titel || zeile.name}“ wiederhergestellt.`)
  await laden()
}

onMounted(laden)
</script>

<style scoped>
.pk-abschnitt { display: grid; gap: var(--gap); }
.pk-hilfe { color: var(--text-muted); }
.pk-bereich { color: var(--text-muted); font-size: var(--fs-sm); }
.pk-aktion { text-align: right; white-space: nowrap; }
.pk-datum { white-space: nowrap; }
</style>
