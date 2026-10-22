<template>
  <div class="bereich dk-screen dk-screen-wide dk-screen-enter">
    <!-- Ein Seitenkopf fuer den ganzen Bereich; oben rechts die Aktionen.
         Der Export gehoert zur Liste: der Server exportiert die GESAMTE
         gefilterte Liste (kein clientseitiger Notbehelf). Sichtbar ist er
         nur im Reiter „Liste“; „Mitglied hinzufuegen“ fuehrt wie bisher in
         die Anmeldungsverwaltung, ein Import-Knopf kommt erst mit N11. -->
    <DkPageHeader title="Mitglieder" :sub="unterzeile">
      <template #actions>
        <!-- Bedingung aus Skripten: in der Vorlage werden Refs in Ausdruecken
             nicht ausgepackt, deshalb hier nur Namen (kein `a && b.id`). -->
        <template v-if="zeigeExportKnopf">
          <DkButton variant="secondary" :loading="exportLaeuft" @click="exportieren">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
            {{ exportLaeuft ? 'Exportiere…' : 'Export' }}
          </DkButton>
        </template>
        <!-- N11: dasselbe im Reiter „Import“ — dort gibt es keine eingebettete
             Liste, deren Export gerufen werden koennte, und der Reiter heisst
             „Import + Export“. Der Server exportiert die Gesamtliste. -->
        <template v-if="zeigeImportExportKnopf">
          <DkButton variant="secondary" :loading="exportLaeuft" @click="exportierenDirekt">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
            {{ exportLaeuft ? 'Exportiere…' : 'Export' }}
          </DkButton>
        </template>
        <template v-if="istAdmin">
          <DkButton variant="primary" @click="mitgliedHinzufuegen">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="8.5" cy="7" r="4"/><line x1="20" y1="8" x2="20" y2="14"/><line x1="23" y1="11" x2="17" y2="11"/></svg>
            Mitglied hinzufügen
          </DkButton>
        </template>
      </template>
    </DkPageHeader>

    <!-- Reiterleiste nur für Mitgliederadministratoren (Konzept Abschnitt 3);
         für alle anderen ist die Liste die einzige Ansicht. -->
    <DkTabs
      v-if="reiter.length > 1"
      class="mb-reiter"
      :model-value="aktiverReiter.id"
      :options="reiter.map(r => ({ value: r.id, label: r.label }))"
      aria-label="Bereiche von Mitglieder"
      @update:model-value="reiterWechseln"
    />

    <!-- Inhalt des aktiven Reiters. Die Körper stammen aus den vorhandenen
         Seiten; ihr eigener Kopf ist dort ausgeblendet (embedded). -->
    <component :is="inhalt" ref="liste" embedded />

    <!-- Dialog „Mitglied hinzufügen“ (Neuordnung N4). Ersetzt den früheren
         Sprung in die Anmeldungen: hier entsteht die Person direkt (Zugang
         „kein Zugang“); die Passwort-Wege folgen mit N5. -->
    <MitgliedHinzufuegenDialog
      v-model="hinzufuegenOffen"
      :gruppen="gruppenAuswahl"
      @angelegt="nachAnlegen"
    />
  </div>
</template>

<script setup>
/**
 * Mitglieder — Rahmen mit Reitern (Neuordnung N1).
 * Kopf und Reiterleiste kommen aus der zentralen Definition (menue.js);
 * jeder Reiter hat eine eigene Adresse. Die Inhalte sind eigene bzw. die
 * vorhandenen Seiten, eingebettet über ihr Merkmal `embedded`.
 *
 * Export (P1-9b + N1b): Der Rahmen zeigt den Knopf NUR im Reiter „Liste“ und
 * ruft die echte Server-Export-Funktion der Liste über ihre Template-Ref auf
 * (defineExpose). Der fruehere zweite, clientseitige Export ist entfallen —
 * er widersprach dem serverseitigen Export (CSV-Entschaerfung, alle Zeilen).
 * „Mitglied hinzufügen“ öffnet seit N4 den eigenen Dialog (Zugang „kein
 * Zugang“) statt in die Anmeldungen zu springen; einen „Importieren“-Knopf
 * gibt es erst mit dem Import-Reiter (N11), statt eines Knopfes mit falscher
 * Beschriftung (Befund R-N1-code N1-4).
 */
import { computed, defineAsyncComponent, onMounted, ref } from 'vue'
import { currentPageName, navigate } from '../../router.js'
import { apiCall } from '../../composables/useApi.js'
import { useSession } from '../../composables/useSession.js'
import { MITGLIEDER_REITER, sichtbareMitgliederReiter } from '../../menue.js'
import { showToast } from '../../composables/useToast.js'
import DkPageHeader from '../../components/ui/DkPageHeader.vue'
import DkButton from '../../components/ui/DkButton.vue'
import DkTabs from '../../components/ui/DkTabs.vue'
import MitgliedHinzufuegenDialog from '../../components/mitglieder/MitgliedHinzufuegenDialog.vue'

const { isAdmin } = useSession()
const seite = currentPageName
// ACHTUNG: In der VORLAGE werden Verweise aus `script setup` NICHT
// automatisch ausgepackt, wenn sie in einem Ausdruck stehen (v-if="a && b").
// Deshalb hier fertige Wahrheitswerte bereitstellen; `aktiverReiter` bleibt
// eine Ref (nur `.id`/`.value` in Skripten).
const istAdmin = computed(() => isAdmin.value === true)

// Inhalte der Reiter. Die Übersicht ist die eigene, neue Seite (N1); die
// Liste bleibt die vorhandene Seite.
const UEBERSICHT   = defineAsyncComponent(() => import('./Uebersicht.vue'))
const LISTE        = defineAsyncComponent(() => import('../Mitglieder.vue'))
const ANFRAGEN     = defineAsyncComponent(() => import('../Registrierung.vue'))
const DATENSCHUTZ  = defineAsyncComponent(() => import('./Datenschutz.vue'))
// DSGVO-2c: eigene Arbeitsliste der Verwaltung (Freigeben/Ablehnen).
const LOESCHANTRAEGE = defineAsyncComponent(() => import('./Loeschantraege.vue'))
const IMPORT       = defineAsyncComponent(() => import('./Import.vue'))

const reiter = computed(() => sichtbareMitgliederReiter({ istAdmin: isAdmin.value }))

const aktiverReiter = computed(() =>
  reiter.value.find(r => r.seite === seite.value)
  || reiter.value.find(r => r.id === 'liste')
  || reiter.value[0]
  || MITGLIEDER_REITER[1],
)

const inhalt = computed(() => {
  switch (aktiverReiter.value.id) {
    case 'uebersicht':  return UEBERSICHT
    case 'anfragen':    return ANFRAGEN
    case 'datenschutz': return DATENSCHUTZ
    case 'loeschantraege': return LOESCHANTRAEGE
    case 'import':      return IMPORT
    default:            return LISTE
  }
})

const unterzeile = computed(() => {
  if (aktiverReiter.value.id === 'liste') return 'Alle Personen der Gemeinde'
  if (aktiverReiter.value.id === 'import') return 'Personen aus einer CSV-Datei einlesen'
  return ''
})

/** Export nur im Reiter „Liste“ und nur fuer Mitgliederadministratoren.
 *  Bewusst ein fertiger Wahrheitswert: `v-if="istAdmin && aktiverReiter.id…"`
 *  waere in der Vorlage falsch (kein Auspacken in Ausdruecken). */
const zeigeExportKnopf = computed(
  () => istAdmin.value === true && aktiverReiter.value.id === 'liste',
)

/** N11: Der Reiter „Import“ hat keine eingebettete Liste, deren Export
 *  gerufen werden koennte — hier holt der Server den Export direkt. Nur fuer
 *  Mitgliederadministratoren (der Server verweigert sonst ohnehin). */
const zeigeImportExportKnopf = computed(
  () => istAdmin.value === true && aktiverReiter.value.id === 'import',
)

// Die eingebettete Liste meldet ihren Umfang selbst (eigener Kopf im
// Standalone-Betrieb) und stellt ihren Export über diese Referenz bereit.
const liste = ref(null)
const exportLaeuft = ref(false)

async function exportieren() {
  // `liste` ist eine Template-Ref auf <component>. Dort greift die
  // Zurueckweisung (ref < component): in Vue 3 gibt es kein `.value`, der
  // Verweis ist das Bauteil selbst — beides wird bedient, damit weder
  // Buildart noch Vue-Fassung still brechen.
  const ziel = liste.value ?? liste
  const exportFn = ziel && (typeof ziel.exportCsv === 'function' ? ziel.exportCsv : null)
  if (!exportFn) {
    showToast('Es sind keine Personen zum Export geladen.', 'info')
    return
  }
  exportLaeuft.value = true
  try {
    await exportFn.call(ziel)
  } finally {
    exportLaeuft.value = false
  }
}

function reiterWechseln(id) {
  const ziel = reiter.value.find(r => r.id === id)
  if (ziel) navigate(ziel.href)
}

/** Export direkt vom Server (Reiter „Import“, N11). Der Server entschaerft die
 *  Zellen und quotet die Datei; hier wird nur gespeichert. Die frueheren
 *  Client-Basteleien (naives Teilen an „;“ und eigene Entschaerfung) sind
 *  entfallen, weil sie gequotete Zellen falsch behandelten. */
async function exportierenDirekt() {
  if (exportLaeuft.value) return
  exportLaeuft.value = true
  try {
    const antwort = await apiCall('diakronos.diakonos.api.mitglieder.exportiere_mitglieder_csv', {})
    const blob = new Blob(['\ufeff' + (antwort?.csv || '')], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = antwort?.dateiname || 'mitglieder.csv'
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
    showToast(`${antwort?.anzahl ?? 0} Mitglied(er) exportiert`, 'success')
  } catch (err) {
    showToast(err?.message || 'Export fehlgeschlagen', 'error')
  } finally {
    exportLaeuft.value = false
  }
}

// ── „Mitglied hinzufügen“ (N4) ─────────────────────────────────────────────

const hinzufuegenOffen = ref(false)
// Gruppenauswahl ist reiner Komfort (dieselbe Quelle wie überall); der Server
// prüft die Zuweisung ohnehin. Fehler hier dürfen den Dialog nicht sperren.
const gruppenAuswahl = ref([])

async function gruppenLaden() {
  if (istAdmin.value !== true) return
  try {
    const res = await apiCall('diakronos.diakonos.api.gruppen.get_gruppen_page_data')
    gruppenAuswahl.value = res?.gruppen_auswahl || []
  } catch (err) {
    gruppenAuswahl.value = []
    console.error('Gruppenauswahl nicht geladen:', err)
  }
}

onMounted(gruppenLaden)

async function mitgliedHinzufuegen() {
  await gruppenLaden()
  hinzufuegenOffen.value = true
}

function nachAnlegen() {
  // Die neue Person soll sofort in der eingebetteten Liste stehen.
  const ziel = liste.value ?? liste
  const reloadFn = ziel && (typeof ziel.reload === 'function' ? ziel.reload : null)
  if (reloadFn) reloadFn.call(ziel)
}
</script>

<style scoped>
.mb-reiter { margin-bottom: var(--sp-3); }
/* Die eingebetteten Seiten bringen ihren eigenen .dk-screen mit; hier liegt
   der Rahmen schon in einem, deshalb innen Abstand und Breite aufheben. */
.bereich :deep(.dk-screen) { max-width: none; padding: 0; margin: 0; }
</style>
