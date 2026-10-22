<template>
  <div class="dk-screen dk-screen-wide dk-screen-enter">

    <!-- Seitenkopf: der Mitglieder-Rahmen (Bereich.vue) bringt seinen
         eigenen Kopf mit; eingebettet entfaellt dieser hier. -->
    <DkPageHeader v-if="!embedded" title="Mitglieder" :sub="`${mitglieder.length} von ${gesamt} Personen`">
      <template #actions>
        <DkButton v-if="isAdmin" variant="secondary" :loading="exporting" @click="exportCsv">
          <IconDownload /> {{ exporting ? 'Exportiere…' : 'Export' }}
        </DkButton>
        <!-- Uebergangsloesung: Die neue Maske „Mitglied hinzufügen“ entsteht in
             Reiter N4 (Mitglieder -> Anfragen/Übersicht) auf Basis der in P1-9
             gehaerteten create_mitglied-Funktion. Bis dahin fuehrt der Knopf in
             die Anmeldungsverwaltung (dort bearbeitet der Admin Anmeldungen). -->
        <DkButton v-if="isAdmin" variant="primary" @click="navigate('#/mitglieder/anfragen')">
          <IconUserPlus /> Mitglied hinzufügen
        </DkButton>
      </template>
    </DkPageHeader>

    <!-- Werkzeugleiste -->
    <div class="dk-toolbar">
      <div class="dk-toolbar-search">
        <svg class="dk-search-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
        <input
          v-model="searchQuery"
          type="text"
          placeholder="Nach Name, E-Mail, Gruppe suchen…"
          @input="onSearchInput"
        />
      </div>

      <DkSegment :model-value="statusFilter" :options="filterOptionen" aria-label="Status-Filter"
                 @update:model-value="setStatusFilter" />

      <span class="mt-spacer" />

      <!-- Ansicht -->
      <DkSegment v-model="viewMode" :options="ansichtOptionen" aria-label="Ansicht" />

      <!-- BF1-F: Persoenliche Daten sind standardmaessig verborgen. Der
           Zustand wird bewusst nicht gespeichert (kein localStorage). -->
      <DkButton
        v-if="isAdmin"
        variant="secondary"
        size="sm"
        :aria-pressed="zeigePersoenlicheDaten ? 'true' : 'false'"
        @click="zeigePersoenlicheDaten = !zeigePersoenlicheDaten"
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <path d="M1 12s4-7 11-7 11 7 11 7-4 7-11 7-11-7-11-7z" /><circle cx="12" cy="12" r="3" />
        </svg>
        {{ zeigePersoenlicheDaten ? 'Persönliche Daten verbergen' : 'Persönliche Daten anzeigen' }}
      </DkButton>

      <DkButton variant="ghost" size="sm" @click="toggleSortOrder" :title="sortOrder === 'asc' ? 'A–Z' : 'Z–A'">
        <IconSort /> {{ sortOrder === 'asc' ? 'A–Z' : 'Z–A' }}
      </DkButton>
    </div>

    <!-- Ladeplatzhalter -->
    <div v-if="loading && mitglieder.length === 0" class="mt-skelett">
      <div v-for="n in 8" :key="n" class="mt-skelett-zeile" :class="{ 'is-first': n === 1 }">
        <div class="mt-puls mt-puls-avatar" />
        <div class="mt-skelett-text">
          <div class="mt-puls mt-puls-titel" />
          <div class="mt-puls mt-puls-sub" />
        </div>
      </div>
    </div>

    <!-- Fehler -->
    <DkHint v-else-if="error" variant="err">{{ error }}</DkHint>

    <!-- Kartenansicht -->
    <template v-else-if="viewMode === 'cards'">
      <DkEmpty
        v-if="mitglieder.length === 0"
        title="Keine Mitglieder gefunden"
        text="Suche oder Filter anpassen."
        icon="👤"
      />
      <div v-else class="dk-card-grid dk-card-grid-sm mt-cards">
        <!-- DSGVO-2d: Eine gelöschte Person (Status „geloescht“, Kennung
             `geloescht-…`) bleibt als Zeile sichtbar, hat aber kein Profil
             mehr — die Karte ist dann kein Link (`href` leer, `aria-disabled`).
             Der Name kommt aus der Server-Regel („Gelöschte Person“). -->
        <a
          v-for="m in mitglieder"
          :key="m.name"
          class="dk-member-card"
          :href="'#/mitglied/' + m.name"
          v-bind="ohneProfilZiel(m)"
          :tabindex="darfProfilLink(m) ? null : -1"
          :aria-disabled="darfProfilLink(m) ? null : 'true'"
          @click="profilOeffnen($event, m)"
          :class="{ 'dk-member-card--ohne-profil': !darfProfilLink(m) }"
        >
          <div class="dk-card-avatar">
            <div class="dk-avatar dk-avatar-md" :style="avatarStil(m.full_name)">
              {{ getInitials(m.full_name) }}
            </div>
          </div>
          <div class="mt-card-body">
            <div class="mt-card-name">{{ m.full_name }}</div>
            <!-- W7: Die E-Mail steht nur unter dem Namen, wenn persönliche
                 Daten bewusst angezeigt werden (sonst liefert sie der Server
                 ohnehin nicht). Statt einer leeren Zeile ein neutraler Platzhalter. -->
            <div class="mt-card-email">{{ zeigePersoenlicheDaten ? (m.email || '–') : 'E-Mail verborgen' }}</div>
            <div class="mt-card-groups">
              <DkBadge v-for="g in (m.gruppen || []).slice(0, 3)" :key="g" variant="neutral">{{ g }}</DkBadge>
            </div>
          </div>
          <div class="mt-card-footer">
            <DkBadge :variant="statusVariant(m.status)">{{ statusText(m.status) }}</DkBadge>
          </div>
        </a>
      </div>
    </template>

    <!-- Tabellenansicht -->
    <template v-else>
      <DkTable :spalten="spalten" :leer="mitglieder.length === 0"
               leer-titel="Keine Mitglieder gefunden" leer-text="Suche oder Filter anpassen.">
        <tr v-for="m in mitglieder" :key="m.name">
          <td>
            <a v-if="darfProfilLink(m)" class="dk-cell-person dk-zellen-link dk-zellen-link--dehnen" :href="'#/mitglied/' + m.name">
              <div class="dk-avatar mt-avatar-klein" :style="avatarStil(m.full_name)">
                {{ getInitials(m.full_name) }}
              </div>
              <div>
                <div class="dk-cell-name">{{ m.full_name }}</div>
                <!-- W7: E-Mail in der Unterzeile nur bei bewusstem Anzeigen. -->
                <div class="dk-cell-email">{{ zeigePersoenlicheDaten ? (m.email || '–') : 'E-Mail verborgen' }}</div>
              </div>
            </a>
            <!-- DSGVO-2d: gelöschte Person — Zeile ohne Profil-Link. -->
            <div v-else class="dk-cell-person">
              <div class="dk-avatar mt-avatar-klein" :style="avatarStil(m.full_name)">
                {{ getInitials(m.full_name) }}
              </div>
              <div>
                <div class="dk-cell-name">{{ m.full_name }}</div>
                <div class="dk-cell-email">Kein Profil mehr vorhanden</div>
              </div>
            </div>
          </td>
          <td>
            <DkBadge :variant="statusVariant(m.status)">{{ statusText(m.status) }}</DkBadge>
          </td>
          <td>
            <div class="dk-cell-groups">
              <DkBadge v-for="g in (m.gruppen || []).slice(0, 2)" :key="g" variant="neutral">{{ g }}</DkBadge>
              <DkBadge v-if="(m.gruppen || []).length > 2" variant="neutral">+{{ m.gruppen.length - 2 }}</DkBadge>
            </div>
          </td>
          <td v-if="isAdmin && zeigePersoenlicheDaten" class="dk-text-muted">{{ m.telefonnummer || '–' }}</td>
          <td v-if="isAdmin && zeigePersoenlicheDaten" class="dk-text-muted">{{ m.email || '–' }}</td>
          <td v-if="isAdmin && zeigePersoenlicheDaten" class="dk-text-muted">{{ formatAddress(m) }}</td>
          <td v-if="isAdmin && zeigePersoenlicheDaten" class="dk-text-muted">{{ m.geburtstag || '–' }}</td>
          <td class="dk-text-subtle">{{ m.creation ? new Date(m.creation).getFullYear() : '–' }}</td>
        </tr>
      </DkTable>
    </template>

    <!-- Blättern -->
    <div class="mt-pagination">
      <div class="dk-text-muted">{{ mitglieder.length }} von {{ gesamt }} geladen</div>
      <div>
        <DkButton
          v-if="hasMore"
          variant="secondary"
          size="sm"
          :loading="loading"
          @click="loadMore"
        >
          {{ loading ? 'Laden…' : 'Mehr laden' }}
        </DkButton>
        <span v-else class="dk-text-subtle">Alle geladen</span>
      </div>
    </div>

    <!-- R-P1-8/W1: wartende Konten (kein Mitglied) freischalten — nur Admins.
         Die Karte darf NICHT an `embedded` haengen: die Liste wird immer
         eingebettet vom Rahmen (pages/mitglieder/Bereich.vue) gerendert, sonst
         waeren wartende Gastkonten in der Oberflaeche nie freischaltbar. -->
    <WartendeKontenKarte v-if="isAdmin" class="mt-wartende" />

    <!-- Anlegen läuft künftig in Reiter N4 („Mitglied hinzufügen“); hier keine
         eigene Maske, bis N4 sie in der neuen Reiterstruktur liefert. -->
  </div>
</template>

<script setup>
/**
 * Mitglieder — Liste im Design-System „A · Ruhig & Klar“.
 *
 * P1-9-Reparaturen (minimal, Neuordnung N4/N11 baut darauf auf):
 *   UXD-R13  toter „Importieren“-/„⋯“-Knopf entfernt; „Export“ liefert eine
 *            echte CSV-Datei (nur für Admins sichtbar).
 *   UXD-R14  Statusfilter aus den ECHTEN Status (inkl. „Alle“), Zähler aus der
 *            Server-Gesamtzahl; erneuter Klick wählt ab (DkSegment).
 *   UXD-R8   maxlength=140 an Namens-/Adressfeldern.
 *
 * Nicht hier: „Mitglied hinzufügen“ – die neue Maske entsteht im Paket N4 auf
 * Basis der inzwischen gehaerteten `create_mitglied`.
 */
import { ref, computed, onMounted, onBeforeUnmount, watch, h } from 'vue'
import { useMitglieder, persoenlicheDatenZuruecksetzen } from '../composables/useMitglieder.js'
import { useSession } from '../composables/useSession.js'
import { apiCall } from '../composables/useApi.js'
import { showToast } from '../composables/useToast.js'
import { navigate } from '../router.js'
import { darfProfilLink, istGeloescht } from '../composables/geloeschte-person.mjs'
import DkPageHeader from '../components/ui/DkPageHeader.vue'
import DkButton from '../components/ui/DkButton.vue'
import DkBadge from '../components/ui/DkBadge.vue'
import DkSegment from '../components/ui/DkSegment.vue'
import DkTable from '../components/ui/DkTable.vue'
import DkEmpty from '../components/ui/DkEmpty.vue'
import DkHint from '../components/ui/DkHint.vue'
import WartendeKontenKarte from '../components/WartendeKontenKarte.vue'

/**
 * DSGVO-2d: Klick auf eine Mitglieder-Karte. Für eine gelöschte Person gibt es
 * kein Profil — der Sprung wird abgefangen (die Karte bleibt sichtbar, ist
 * aber kein Link mehr: `aria-disabled`, kein Tabstopp, kein Zeiger).
 */
function profilOeffnen(ereignis, m) {
  if (darfProfilLink(m)) return
  ereignis.preventDefault()
  ereignis.stopPropagation()
}

/**
 * Ziel der Mitglieder-Karte. Ohne Profil (gelöschte Person) gibt es KEIN
 * Ziel: das nachgestellte `v-bind` überschreibt `href` mit dem reinen Anker.
 * Ein stehengebliebenes `#/mitglied/geloescht-…` wäre ein toter Link — auch
 * wenn der Klick abgefangen wird (Vorlesehilfen und „Link kopieren“ lesen
 * `href`, nicht den Klick-Handler).
 */
function ohneProfilZiel(m) {
  return darfProfilLink(m) ? {} : { href: '#' }
}

const { isAdmin } = useSession()

/** Im Mitglieder-Rahmen (Bereich.vue) eingebettet: dessen Kopf uebernimmt
 *  Unterzeile und Deckknoepfe, dieser eigene Kopf entfaellt dann. */
defineProps({ embedded: { type: Boolean, default: false } })

const {
  mitglieder,
  gesamt,
  gesamtAlle,
  statusZaehler,
  loading,
  error,
  hasMore,
  searchQuery,
  statusFilter,
  sortBy,
  sortOrder,
  persoenlicheDaten,
  loadMore,
  reload,
} = useMitglieder()

/** Kopf-Aktionen (Export) und Neuladen fuer den einbettenden Rahmen.
 *  `reload` braucht der Dialog „Mitglied hinzufügen“ (N4): nach dem Anlegen
 *  soll die neue Person sofort in der Liste stehen, ohne Neuladen der Seite.
 *  WICHTIG: erst NACH dem Auspacken oben — vorher läge `reload` in der
 *  temporalen Totzone (ReferenceError beim Aufbau der Seite). */
defineExpose({ exportCsv, reload })

const viewMode = ref('cards')
/** P1-9b: Der CSV-Export holt jetzt den Server — waehrenddessen Knopf sperren. */
const exporting = ref(false)

/** BF1-F/W7: Persönliche Daten erst nach bewusstem Anzeigen — und zwar
 *  SERVERSEITIG: der Schalter geht an `get_mitglieder_liste`
 *  (`persoenliche_daten`), sonst stehen Telefon/Adresse/Geburtstag/E-Mail
 *  gar nicht erst in der Antwort. Nur für die Dauer der Seite, nicht
 *  gespeichert. */
const zeigePersoenlicheDaten = persoenlicheDaten
onBeforeUnmount(persoenlicheDatenZuruecksetzen)

/** UXD-R14: Die echten Status der Daten (keine „Kind“/„Inaktiv“, die es nie
 *  gibt) plus „Alle“. Die Zahl je Status kommt aus der Server-Gesamtzahl nur
 *  für „Alle“; die Einzelzahlen zählen die geladenen Zeilen (ehrlich als
 *  Anzeige-Zahl der aktuell geladenen Seite).
 *
 *  AUSTRITT A5: „Ausgetreten“ ist seit dem Austritt ein echter Status und
 *  gehoert deshalb in dieselbe Liste — er ist der einzige Weg, Ausgetretene
 *  zu sehen; einen zweiten Schalter fuer denselben Filter gibt es bewusst
 *  nicht (zwei Wege waeren zwei halbe Wege). */
/* DSGVO-2d: Der Endstatus der Löschung auf Antrag („geloescht“) ist ein
 * echter Status der Daten — er gehört deshalb in dieselbe Liste wie die
 * gepflegten (vorher fiel `?status=geloescht` still auf „Alle“ zurück). Sein
 * Wort in der Oberfläche ist „Gelöschte Person“, nicht der Speicherwert. */
const MT_GELOESCHT = 'geloescht'
const MT_STATUS = ['Mitglied', 'Gast', 'Passives Mitglied', 'Passiver Gast', 'Ausgetreten']
// DSGVO-2d: Der Endstatus der Löschung steht in DERSELBEN Liste — er ist ein
// echter Status der Daten, und ohne ihn fiel `?status=geloescht` still auf
// „Alle“ zurück. Der Chip erscheint nur, wenn es solche Zeilen gibt.
MT_STATUS.push(MT_GELOESCHT)
/** Anzeigewort je Status, wo es vom Speicherwert abweicht (DSGVO-2d). */
const MT_STATUS_WORT = { [MT_GELOESCHT]: 'Gelöschte Person' }



/** N1b (H2): Kacheln der Uebersicht verlinken mit gesetztem Filter
 *  (#/mitglieder/liste?status=Mitglied). Der Wert wird als Startfilter
 *  uebernommen und bei Filterwechsel im aktuellen Verlaufseintrag ersetzt.
 *  So bleibt er beim Zurueckkehren aus dem Mitglied-Detail erhalten.
 *
 *  H1 (R-N2-code): Die Kachel „Personen“ verlinkt OHNE `status` und meint
 *  „alle“. Der Filter kommt deshalb IMMER aus der Adresse — fehlt der
 *  Parameter, gilt „Alle“. Sonst zeigte die Kachel weiter den zuletzt im
 *  Modulzustand gesetzten Status (z.B. „Mitglied“). */
function _statusAusAdresse() {
  const hash = window.location.hash || ''
  const frage = hash.indexOf('?')
  if (frage === -1) return ''
  const wert = new URLSearchParams(hash.slice(frage + 1)).get('status') || ''
  // `MT_STATUS` führt seit DSGVO-2d auch den Endstatus „geloescht“ — vorher
  // fiel `?status=geloescht` still auf „Alle“ zurück.
  return MT_STATUS.includes(wert) ? wert : ''
}
// Immer aus der Adresse setzen (auch auf '' = Alle) — nicht nur bei Treffer.
statusFilter.value = _statusAusAdresse()
// Filter ist Teil des aktuellen Verlaufseintrags: Zurück aus dem Detail
// stellt genau die zuvor angezeigte Liste wieder her (kein neuer Eintrag).
watch(statusFilter, (wert) => {
  const [pfad, suche = ''] = window.location.hash.split('?')
  const parameter = new URLSearchParams(suche)
  parameter.set('status', wert)
  window.history.replaceState(null, '', `${pfad}?${parameter}`)
})

const filterOptionen = computed(() => {
  // DSGVO-2d: Der Endstatus „geloescht“ erscheint nur, wenn es solche Zeilen
  // gibt, und trägt sein Anzeigewort („Gelöschte Person“) statt des
  // Speicherwerts. Ein leerer Chip „geloescht 0“ wäre nur Rauschen.
  const optionen = MT_STATUS
    .filter(s => s !== MT_GELOESCHT || (statusZaehler.value[s] ?? 0) > 0)
    .map(s => ({
      value: s,
      label: `${MT_STATUS_WORT[s] || s} ${statusZaehler.value[s] ?? 0}`,
    }))
  return [{ value: '', label: `Alle ${gesamtAlle.value}` }, ...optionen]
})
const ansichtOptionen = [
  { value: 'cards', label: 'Karten' },
  { value: 'table', label: 'Tabelle' },
]

const spalten = computed(() => {
  const liste = [
    { key: 'name', label: 'Name' },
    { key: 'status', label: 'Status' },
    { key: 'gruppen', label: 'Gruppen' },
  ]
  if (isAdmin.value && zeigePersoenlicheDaten.value) {
    liste.push(
      { key: 'telefon', label: 'Telefon' },
      { key: 'email', label: 'E-Mail' },
      { key: 'adresse', label: 'Adresse' },
      { key: 'geburtstag', label: 'Geburtstag' },
    )
  }
  liste.push({ key: 'dabei', label: 'Dabei seit' })
  return liste
})

function formatAddress(m) {
  const parts = []
  if (m.straße) parts.push(m.straße + (m.nummer ? ' ' + m.nummer : ''))
  if (m.postleitzahl || m.wohnort) parts.push([m.postleitzahl, m.wohnort].filter(Boolean).join(' '))
  return parts.join(', ') || '–'
}

let searchTimer = null
function onSearchInput() {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(reload, 300)
}

/** UXD-R14: Erneutes Anklicken des aktiven Status wählt ihn ab (→ „Alle“). */
function setStatusFilter(wert) {
  statusFilter.value = (wert === statusFilter.value) ? '' : wert
}

/** Befund 1 (P1-9b): Der Knopf A–Z/Z–A rief eine Funktion auf, die beim
 *  Zurückbauen der Maske aus dem Skript verschwunden war — toter Knopf bzw.
 *  Laufzeitfehler beim Klick. Stellt die Umschaltung wieder her; `sortOrder`
 *  ist die Quelle (der Watcher in useMitglieder laedt neu). */
function toggleSortOrder() {
  sortOrder.value = sortOrder.value === 'asc' ? 'desc' : 'asc'
}

/** UXD-R13: echter CSV-Export der GESAMTEN gefilterten Liste (kein Platzhalter).
 *  P1-9b: Der Export lag vorher im Browser und enthielt nur die geladenen
 *  Zeilen (Seitengroesse 30) — die Datei hiess aber „mitglieder.csv“ und sah
 *  nach der Gesamtliste aus. Jetzt holt der Server dieselbe Filterung ohne
 *  Seitengrenze und entschaerft die Zellen (CSV-/Formel-Einschleusung).
 */
async function exportCsv() {
  if (exporting.value) return
  exporting.value = true
  try {
    const antwort = await apiCall('diakronos.diakonos.api.mitglieder.exportiere_mitglieder_csv', {
      suche: searchQuery.value || undefined,
      status: statusFilter.value || undefined,
      persoenliche_daten: zeigePersoenlicheDaten.value === true,
    })
    const csv = antwort?.csv || ''
    const blob = new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8;' })
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
    exporting.value = false
  }
}

/** P1-9b (Befund 2, Nacharbeit N11): Die clientseitige Doppelsicherung ist
 *  ENTFALLEN. Sie teilte die Serverdatei naiv an „;“ — bei gequoteten Zellen
 *  (Wert mit Semikolon, Anfuehrungszeichen oder Zeilenumbruch) verschob das
 *  die Spalten und zerlegte eine Zelle in zwei. Der Server entschaerft und
 *  quotet (siehe `_csv_zelle`/`csv.writer` in api/mitglieder.py); hier wird
 *  die Datei unveraendert gespeichert. */

function getInitials(name) {
  if (!name) return '?'
  // DSGVO-2d: „Gelöschte Person“ darf keine Initialen „GP“ ergeben — der
  // Avatar zeigt ein neutrales Zeichen (kein aus einem Restnamen abgeleitetes
  // Kürzel).
  if (istGeloescht(String(name))) return 'U'
  return name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2)
}
/* DES-08: Die Initialen trugen die Schriftfarbe --primary-ink — auf Gold
   2,68:1, im Dunkelmodus bis 1,41:1. Jedes Paar aus Flaeche UND Schrift
   kommt aus tokens.css; die Verteilung nutzt zwei Zeichen des Namens, damit
   benachbarte Namen nicht immer dieselbe Farbe bekommen. */
const AVATAR_PAARE = [
  { bg: 'var(--dk-avatar-1-bg)', ink: 'var(--dk-avatar-1-ink)' },
  { bg: 'var(--dk-avatar-2-bg)', ink: 'var(--dk-avatar-2-ink)' },
  { bg: 'var(--dk-avatar-3-bg)', ink: 'var(--dk-avatar-3-ink)' },
  { bg: 'var(--dk-avatar-4-bg)', ink: 'var(--dk-avatar-4-ink)' },
  { bg: 'var(--dk-avatar-5-bg)', ink: 'var(--dk-avatar-5-ink)' },
  { bg: 'var(--dk-avatar-6-bg)', ink: 'var(--dk-avatar-6-ink)' },
]
function avatarStil(name) {
  const n = String(name || 'A').trim()
  // zwei Zeichen streuen breiter als das erste allein (DES-08).
  const summe = (n.charCodeAt(0) || 65) + (n.length > 1 ? n.charCodeAt(n.length - 1) : 0)
  const paar = AVATAR_PAARE[summe % AVATAR_PAARE.length]
  return { background: paar.bg, color: paar.ink }
}
/** Mitgliedsstatus → Kennzeichen-Variante der Statussprache. */
function statusVariant(s) {
  // DSGVO-2d: Endstatus der Löschung — gedämpft, kein „Fehler“.
  if (s === MT_GELOESCHT) return 'neutral'
  if (s === 'Ausgetreten') return 'err'
  if (s === 'Mitglied') return 'ok'
  if (s === 'Passives Mitglied') return 'info'
  if (s === 'Gast') return 'warn'
  if (s === 'Passiver Gast') return 'warn'
  return 'neutral'
}

/** Statuswort fürs Kennzeichen — der Endstatus steht technisch in der DB,
 *  angezeigt wird er als „Gelöschte Person“ (DSGVO-2d). */
function statusText(s) {
  if (!s) return 'Unbekannt'
  return MT_STATUS_WORT[s] || s
}

onMounted(reload)

// --- Inline-Symbole (dekorativ) ---
const IconDownload = () => h('svg', { width:14, height:14, viewBox:'0 0 24 24', fill:'none', stroke:'currentColor', 'stroke-width':2, 'stroke-linecap':'round', 'stroke-linejoin':'round' }, [h('path',{d:'M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4'}), h('polyline',{points:'7 10 12 15 17 10'}), h('line',{x1:12,y1:15,x2:12,y2:3})])
const IconUserPlus = () => h('svg', { width:14, height:14, viewBox:'0 0 24 24', fill:'none', stroke:'currentColor', 'stroke-width':2, 'stroke-linecap':'round', 'stroke-linejoin':'round' }, [h('path',{d:'M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2'}), h('circle',{cx:8.5,cy:7,r:4}), h('line',{x1:20,y1:8,x2:20,y2:14}), h('line',{x1:23,y1:11,x2:17,y2:11})])
const IconSort     = () => h('svg', { width:13, height:13, viewBox:'0 0 24 24', fill:'none', stroke:'currentColor', 'stroke-width':2, 'stroke-linecap':'round', 'stroke-linejoin':'round' }, [h('line',{x1:8,y1:6,x2:21,y2:6}), h('line',{x1:8,y1:12,x2:21,y2:12}), h('line',{x1:8,y1:18,x2:21,y2:18}), h('line',{x1:3,y1:6,x2:3.01,y2:6}), h('line',{x1:3,y1:12,x2:3.01,y2:12}), h('line',{x1:3,y1:18,x2:3.01,y2:18})])
</script>

<style scoped>
@keyframes dk-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

.mt-spacer { flex: 1; }

/* Ladeplatzhalter */
.mt-skelett {
  display: flex;
  flex-direction: column;
  gap: 0;
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
  overflow: hidden;
}
.mt-skelett-zeile {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  padding: var(--sp-3) var(--sp-4);
  border-top: 1px solid var(--divider);
}
.mt-skelett-zeile.is-first { border-top: none; }
.mt-skelett-text { flex: 1; display: flex; flex-direction: column; gap: 6px; }
.mt-puls { background: var(--surface-2); animation: dk-pulse 1.5s infinite; }
.mt-puls-avatar { width: 28px; height: 28px; border-radius: 50%; }
.mt-puls-titel { height: 12px; width: 140px; border-radius: var(--radius-sm); }
.mt-puls-sub { height: 10px; width: 100px; border-radius: var(--radius-sm); }

/* Karten */
.mt-cards { margin-top: 0; }

.dk-member-card {
  display: flex;
  flex-direction: column;
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
  padding: var(--pad);
  cursor: pointer;
  transition: box-shadow var(--fast) var(--ease), border-color var(--fast) var(--ease);
}
.dk-member-card:hover {
  border-color: var(--primary);
  box-shadow: var(--shadow-md);
}
/* DSGVO-2d: Karte einer gelöschten Person — sie führt auf kein Profil mehr,
   deshalb kein Zeiger und kein Hover-Versprechen. */
.dk-member-card--ohne-profil { cursor: default; }
.dk-member-card--ohne-profil:hover {
  border-color: var(--line);
  box-shadow: none;
}

.dk-card-avatar { display: flex; justify-content: center; margin-bottom: var(--sp-3); }
.mt-card-body { flex: 1; text-align: center; }
.mt-card-name {
  font-size: var(--fs-h3);
  font-weight: var(--fw-h);
  color: var(--text);
  margin-bottom: var(--sp-1);
}
.mt-card-email {
  font-size: var(--fs-sm);
  color: var(--muted);
  margin-bottom: var(--sp-2);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.mt-card-groups {
  display: flex;
  flex-wrap: wrap;
  gap: var(--sp-1);
  justify-content: center;
  min-height: 20px;
}
.mt-card-footer {
  display: flex;
  justify-content: center;
  margin-top: var(--sp-3);
  padding-top: var(--sp-3);
  border-top: 1px solid var(--line);
}

.mt-avatar-klein { width: 28px; height: 28px; font-size: var(--fs-xs); }

.mt-pagination {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--pad) var(--sp-1);
  font-size: var(--fs-sm);
  color: var(--muted);
}
.mt-wartende { margin-top: var(--sp-4); }
</style>
