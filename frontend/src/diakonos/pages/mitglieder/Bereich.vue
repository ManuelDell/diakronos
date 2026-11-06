<template>
  <div class="bereich dk-screen dk-screen-wide dk-screen-enter">
    <!-- Ein Seitenkopf fuer den ganzen Bereich; oben rechts die Aktionen.
         Der Export gehoert zur Liste: der Server exportiert die GESAMTE
         gefilterte Liste (kein clientseitiger Notbehelf). Sichtbar ist er
         nur im Reiter „Liste“; „Mitglied hinzufuegen“ fuehrt wie bisher in
         die Anmeldungsverwaltung, ein Import-Knopf kommt erst mit N11. -->
    <DkPageHeader title="Personen" :sub="unterzeile">
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
            Person anlegen
          </DkButton>
        </template>
      </template>
    </DkPageHeader>

    <!-- UX-A2a: Bereichsliste links neben dem Inhalt (am Handy eine
         waagerechte Reiterzeile). Sie ersetzt den Reiterstreifen; die
         Unterbereiche von „Anfragen“ sind eigene, eingerückte Einträge
         („Anfragen“ selbst ist der Hauptpunkt mit der Zahl).
         Nur für Mitgliederadministratoren mehr als ein Eintrag (Konzept
         Abschnitt 3); für alle anderen ist die Liste die einzige Ansicht. -->
    <div class="mb-raster" :class="{ 'ohne-liste': !zeigtBereichsliste }">
      <DkBereichsliste
        v-if="zeigtBereichsliste"
        class="mb-liste"
        :model-value="aktiverEintragValue"
        :options="bereichsEintraege"
        aria-label="Bereiche von Personen"
      />

      <!-- Inhalt des aktiven Eintrags. Die Körper stammen aus den vorhandenen
           Seiten; ihr eigener Kopf ist dort ausgeblendet (embedded).
           UX-A2a: KEIN role="tabpanel" — die Einträge sind Links einer
           Navigation (kein Reiter-Muster). Der Bereich trägt einen Namen für
           Vorlesehilfen und ist per Tastatur erreichbar. -->
      <div class="mb-inhalt" :aria-label="inhaltName" role="region" tabindex="0">
        <component
          :is="inhalt"
          ref="liste"
          embedded
          :unterbereich="unterbereich"
          @leer-anlegen="mitgliedHinzufuegen"
        />
      </div>
    </div>

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
 * Personen — Rahmen mit Bereichsliste (Neuordnung N1, UX-A2a; UX3a heißt der
 * Bereich „Personen“, vorher „Mitglieder“).
 * Kopf und Einträge kommen aus der zentralen Definition (menue.js); jeder
 * Eintrag hat eine eigene Adresse.
 *
 * UX-A2a (Entwurf A2, Manuel 23.10.): Der Reiterstreifen ist durch EINE feste
 * Liste links neben dem Inhalt ersetzt (am Handy: waagerechte Reiterzeile).
 * Die Unterbereiche von „Anfragen“ (Links & QR-Codes · Formulare) sind eigene,
 * eingerückte Einträge dieser Liste — „Anfragen“ selbst ist der Hauptpunkt mit
 * der Zahl; die bisherige zweite Reiterzeile in der Anfragen-Seite entfällt.
 * Neben „Anfragen“ steht die Zahl offener Anfragen aus demselben Stand wie an
 * „Mitglieder“ in der Seitenleiste (eine Abfrage für beide Anzeigen).
 *
 * Export (P1-9b + N1b): Der Rahmen zeigt den Knopf NUR beim Eintrag „Liste“
 * und ruft die echte Server-Export-Funktion der Liste über ihre Template-Ref
 * auf (defineExpose). Der fruehere zweite, clientseitige Export ist entfallen —
 * er widersprach dem serverseitigen Export (CSV-Entschaerfung, alle Zeilen).
 * „Mitglied hinzufügen“ öffnet seit N4 den eigenen Dialog (Zugang „kein
 * Zugang“) statt in die Anmeldungen zu springen; einen „Importieren“-Knopf
 * gibt es erst mit dem Import-Reiter (N11), statt eines Knopfes mit falscher
 * Beschriftung (Befund R-N1-code N1-4).
 */
import { computed, defineAsyncComponent, onMounted, ref } from 'vue'
import { currentHash, currentPageName } from '../../router.js'
import { apiCall } from '../../composables/useApi.js'
import { useSession } from '../../composables/useSession.js'
import { bereichsEintragAusHash, bereichsWert, mitgliederBereichEintraege, unterbereichsWert } from '../../menue.js'
import { anfragenZaehler, anfragenZahlAuffrischen } from '../../composables/useVerwaltung.js'
import { showToast } from '../../composables/useToast.js'
import DkPageHeader from '../../components/ui/DkPageHeader.vue'
import DkButton from '../../components/ui/DkButton.vue'
import DkBereichsliste from '../../components/ui/DkBereichsliste.vue'
import MitgliedHinzufuegenDialog from '../../components/mitglieder/MitgliedHinzufuegenDialog.vue'

const { isAdmin } = useSession()
const seite = currentPageName
// ACHTUNG: In der VORLAGE werden Verweise aus `script setup` NICHT
// automatisch ausgepackt, wenn sie in einem Ausdruck stehen (v-if="a && b").
// Deshalb hier fertige Wahrheitswerte bereitstellen.
const istAdmin = computed(() => isAdmin.value === true)

// Inhalte der Einträge. Die Übersicht ist die eigene, neue Seite (N1); die
// Liste bleibt die vorhandene Seite.
const UEBERSICHT   = defineAsyncComponent(() => import('./Uebersicht.vue'))
const LISTE        = defineAsyncComponent(() => import('../Mitglieder.vue'))
const ANFRAGEN     = defineAsyncComponent(() => import('../Registrierung.vue'))
const DATENSCHUTZ  = defineAsyncComponent(() => import('./Datenschutz.vue'))
// DSGVO-2c: eigene Arbeitsliste der Verwaltung (Freigeben/Ablehnen).
const LOESCHANTRAEGE = defineAsyncComponent(() => import('./Loeschantraege.vue'))
const IMPORT       = defineAsyncComponent(() => import('./Import.vue'))
// UX3a: Das Adressbuch ist ein Reiter von „Personen“ (vorher eigener Menüpunkt).
// UX3b2: KEINE eigene Adressbuch-Seite mehr — die Adressen leiten auf „Personen →
// Liste“ (dort zeigt die Liste die Freigabe-Sicht). Eine zweite Liste ohne
// Blättern und Statusfilter wären zwei halbe Wege.


// ── Einträge und Auswahl ───────────────────────────────────────────────────

// Kennzahl offener Anfragen: DERSELBE Stand wie an „Mitglieder“ in der
// Seitenleiste (useVerwaltung.js, eine Abfrage für beide Anzeigen). Der
// Bereich LIEST nur — kein eigenes Intervall (UX-A2a2 Punkt 3): den Takt hält
// die Seitenleiste über `anfragenZaehlerBeobachten`, hier steht kein
// `setInterval`. Auch beim Wechsel des Eintrags wird nicht nachgefragt; die
// Zahl ändert sich im Minutentakt bzw. nach einer Handlung (Aufnehmen/
// Ablehnen ruft die Anfragen-Seite `anfragenZahlAuffrischen`).
const anfragenZahl = anfragenZaehler

const bereichsEintraege = computed(() => mitgliederBereichEintraege({
  istAdmin: isAdmin.value === true,
  anfragenZahl: anfragenZahl.value,
}))

/** Nur Mitgliederadministratoren sehen mehr als einen Eintrag. */
const zeigtBereichsliste = computed(() => bereichsEintraege.value.length > 1)

const aktiveAuswahl = computed(() => bereichsEintragAusHash(currentHash.value, {
  istAdmin: isAdmin.value === true,
  anfragenZahl: anfragenZahl.value,
}))

const aktiverEintrag = computed(() => aktiveAuswahl.value?.eintrag || null)
const unterbereich = computed(() => aktiveAuswahl.value?.unterbereich?.bereich || null)

/** Gewählter Wert für die Liste: Seite bzw. Seite + Unterbereich (menue.js,
 *  damit Ober- und Unterpunkte NICHT gleichzeitig als gewählt gelten).
 *  Der Anfragen-Hauptpunkt ohne Abfrageteil bleibt der Hauptpunkt selbst. */
const aktiverEintragValue = computed(() => {
  const unter = aktiveAuswahl.value?.unterbereich
  return unter ? unterbereichsWert(unter.seite, unter.bereich)
    : bereichsWert(aktiveAuswahl.value?.eintrag?.seite || seite.value)
})

/** Name des Inhaltsbereichs für Vorlesehilfen (role="region"). */
const inhaltName = computed(() => aktiverEintrag.value?.label || 'Personen')

const inhalt = computed(() => {
  switch (aktiverEintrag.value?.id) {
    case 'uebersicht':  return UEBERSICHT
    case 'anfragen':    return ANFRAGEN
    case 'datenschutz': return DATENSCHUTZ
    case 'loeschantraege': return LOESCHANTRAEGE
    case 'import':      return IMPORT
    default:            return LISTE
  }
})

const unterzeile = computed(() => {
  if (aktiverEintrag.value?.id === 'liste') return 'Alle Personen der Gemeinde'
  if (aktiverEintrag.value?.id === 'import') return 'Personen aus einer CSV-Datei einlesen'
  return ''
})

/** Export nur beim Eintrag „Liste“ und nur fuer Mitgliederadministratoren.
 *  Bewusst ein fertiger Wahrheitswert: `v-if="istAdmin && …"` waere in der
 *  Vorlage falsch (kein Auspacken in Ausdruecken). */
const zeigeExportKnopf = computed(
  () => istAdmin.value === true && aktiverEintrag.value?.id === 'liste',
)

/** N11: Der Eintrag „Import“ hat keine eingebettete Liste, deren Export
 *  gerufen werden koennte — hier holt der Server den Export direkt. Nur fuer
 *  Mitgliederadministratoren (der Server verweigert sonst ohnehin). */
const zeigeImportExportKnopf = computed(
  () => istAdmin.value === true && aktiverEintrag.value?.id === 'import',
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

/** Wechsel des Unterbereichs INNERHALB der Anfragen-Seite. Der Rahmen hat
 *  dafür keinen Umschalter (die Bereichsliste links ist die Navigation); die
 *  Seite allein — ohne `embedded` — schaltet lokal und schreibt die Adresse
 *  selbst. Das frühere Ereignis `unterbereich-wechsel` samt Empfänger ist
 *  entfallen (UX-A2a2): es wurde von keiner Seite mehr ausgelöst. */

/** Export direkt vom Server (Eintrag „Import“, N11). Der Server entschaerft die
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

onMounted(() => {
  gruppenLaden()
})

// ── Aufnehmen/Ablehnen: die Kennzahl sofort nachziehen ─────────────────────

/**
 * Weiterreichen an die eingebettete Anfragen-Seite (UX-A2a2): nach einer
 * Handlung, die die Zahl offener Anfragen ändert (aufnehmen/ablehnen), holt
 * der Bereich den gemeinsamen Stand EINMAL neu. NICHT bei jedem Wechsel des
 * Eintrags — das war die zusätzliche Abfrage aus dem Review.
 */
function anfragenStandAuffrischen() {
  anfragenZahlAuffrischen()
}

defineExpose({ anfragenStandAuffrischen })

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
/* UX-A2a: Bereichsliste links, Inhalt rechts. Auf schmalen Anzeigen stellt
   die Komponente selbst auf eine waagerechte Reiterzeile um (≤ 720 px);
   hier wird dann nur das Raster einspaltig. */
.mb-raster {
  display: grid;
  grid-template-columns: 216px minmax(0, 1fr);
  gap: var(--sp-5);
  align-items: start;
}
.mb-raster.ohne-liste { grid-template-columns: minmax(0, 1fr); }
@media (max-width: 1100px) {
  .mb-raster { grid-template-columns: 184px minmax(0, 1fr); gap: var(--sp-4); }
}
@media (max-width: 720px) {
  .mb-raster { grid-template-columns: minmax(0, 1fr); gap: var(--sp-3); }
}
/* Die eingebetteten Seiten bringen ihren eigenen .dk-screen mit; hier liegt
   der Rahmen schon in einem, deshalb innen Abstand und Breite aufheben. */
.mb-inhalt { min-width: 0; }
.mb-inhalt:focus-visible { outline: 2px solid var(--focus-ring); outline-offset: 4px; border-radius: var(--radius); }
.bereich :deep(.dk-screen) { max-width: none; padding: 0; margin: 0; }
</style>
