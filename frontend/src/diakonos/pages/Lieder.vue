<template>
  <div class="dk-screen dk-screen-wide dk-screen-enter">
    <!-- UX3a: „Lieder“ und „Liedgruppen“ sind zwei Reiter EINES Bereichs
         (Entwurf A1) — Liedgruppen war bis UX3a ein eigener Menüpunkt. -->
    <DiensteReiter :reiter="LIEDER_REITER" :seite="currentPageName" aria-label="Bereiche von Lieder" />
    <!-- Header -->
    <div class="dk-screen-header">
      <div>
        <h1 class="dk-screen-title">Lieder</h1>
        <p class="dk-screen-sub">{{ lieder.length }} {{ wortImNumerus(lieder.length, 'Lied', 'Lieder') }} geladen{{ hasMore ? '+' : '' }} – Klick auf eine Zeile für Details</p>
      </div>
      <DkButton
        v-if="darfSchreiben"
        class="ld-neu"
        variant="primary"
        @click="neuesLied"
      >
        <svg slot="icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
        Neues Lied
      </DkButton>
    </div>

    <!-- Toolbar -->
    <div class="dk-toolbar ld-toolbar">
      <div class="dk-toolbar-row">
        <div class="dk-toolbar-search ld-suche">
          <svg class="dk-search-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
          <input
            ref="suchFeld"
            v-model="searchQuery"
            type="text"
            aria-label="Lieder durchsuchen"
            placeholder="Titel, Nummer oder Strophentext suchen…"
            @input="onSearchInput"
          />
        </div>
        <!-- OP-HANDY-13: Am Handy liegen die Filter in einem Blatt, damit die
             Treffer nicht unter die Tastatur rutschen.
             FIX-3: Der Knopf war ein Alt-Baustein (.dk-btn-sm, ~27 px) neben dem
             Suchfeld (39 px). Jetzt DkButton „md“ — Höhe --control-h, also
             dieselbe wie das Suchfeld (--filter-h). -->
        <DkButton
          variant="secondary"
          class="ld-filter-knopf"
          :aria-expanded="String(filterBlatt)"
          @click="filterBlatt = !filterBlatt"
        >
          Filter<span v-if="aktiveFilterZahl" class="ld-filter-zahl">{{ aktiveFilterZahl }}</span>
        </DkButton>
      </div>

      <!-- DES-R21: Filter als EINE Zeile in fester Reihenfolge (Chips, dann
           drei Auswahlfelder mit Beschriftung davor). Vorher standen die drei
           Auswahlfelder über die volle Breite untereinander, die Beschriftung
           sass darüber und die Auswahltexte wurden abgeschnitten. -->
      <div
        class="dk-toolbar-row ld-filterzeile"
        :class="{ 'is-offen': filterBlatt }"
      >
        <!-- DES-01: Rechte-Status als gemeinsamer Chip-Baustein (abwählbar) -->
        <DkFilterChips
          :chips="rechteChipListe"
          :model-value="filters.rechte_status"
          :mit-zahl="false"
          aria-label="Lieder nach Rechte-Status filtern"
          @waehlen="rechteStatusWaehlen"
        />

        <div class="ld-filter-feld">
          <label class="ld-filter-label" for="ld-filter-gruppe">Gruppe</label>
          <select id="ld-filter-gruppe" v-model="filters.gruppe" class="dk-form-input ld-select" @change="filterGeaendert">
            <option value="">Alle</option>
            <option v-for="g in gruppeOptions" :key="g" :value="g">{{ g }}</option>
          </select>
        </div>
        <div class="ld-filter-feld">
          <label class="ld-filter-label" for="ld-filter-kategorie">Kategorie</label>
          <select id="ld-filter-kategorie" v-model="filters.kategorie" class="dk-form-input ld-select" @change="filterGeaendert">
            <option value="">Alle</option>
            <option v-for="k in kategorieOptions" :key="k" :value="k">{{ k }}</option>
          </select>
        </div>
        <div class="ld-filter-feld">
          <label class="ld-filter-label" for="ld-filter-anlass">Anlass</label>
          <select id="ld-filter-anlass" v-model="filters.anlass" class="dk-form-input ld-select" @change="filterGeaendert">
            <option value="">Alle</option>
            <option v-for="a in anlassOptions" :key="a" :value="a">{{ a }}</option>
          </select>
        </div>

        <DkButton v-if="hasAnyFilter" variant="ghost" size="md" class="ld-filter-reset" @click="resetFilters">
          Filter zurücksetzen
        </DkButton>
      </div>
    </div>

    <!-- OP-UI-19: eine Ladeform für alle Seiten — das Skelett aus dem
         Baustein. Vorher stand hier ein von Hand gebautes Gerüst neben fünf
         weiteren Ladeformen (Spinner, „Lade…“, leerer Bildschirm …). -->
    <!-- UX2d3b (Review UX2d3a/C): Der Platzhalter erscheint erst nach 300 ms
         (`useLadeSkelett`) und der Leerzustand darunter fordert ausdrücklich
         „fertig geladen" — in den ersten 300 ms ist der Bildschirm ruhig. -->
    <DkSkelett v-if="loadingSkelett && lieder.length === 0" form="tabelle" :anzahl="6" text="Lieder werden geladen" />

    <!-- Error -->
    <div v-else-if="error" class="ld-error">
      {{ error }}
      <DkButton
        variant="secondary"
        size="md"
        @click="reload"
      >Erneut versuchen</DkButton>
    </div>

    <!-- Table -->
    <template v-else>
      <!-- OP-HANDY-13: Am Handy Treffer als Karten (die 5-Spalten-Tabelle läuft
           sonst seitlich über). -->
      <ul v-if="lieder.length" class="ld-karten">
        <li v-for="l in lieder" :key="'k-' + l.name" class="ld-karte-li">
          <a class="ld-karte" :href="'#/lieder/' + encodeURIComponent(l.name)" @contextmenu.prevent="zeilenKontextmenue($event, l)">
            <div class="ld-karte-kopf">
              <span class="ld-karte-titel">{{ l.titel }}</span>
              <span v-if="l.anzeige" class="ld-karte-kennung" :class="{ 'ld-kopie': istKopie(l) }">{{ l.anzeige }}</span>
            </div>
            <div v-if="l.alternativtitel" class="ld-karte-alt">{{ l.alternativtitel }}</div>
            <div class="ld-karte-meta">
              <span class="dk-badge ld-badge-count">{{ fassungCount(l) }} {{ wortImNumerus(fassungCount(l), 'Fassung', 'Fassungen') }}</span>
              <span class="dk-badge" :class="rechtePill(l.rechte_status)">{{ l.rechte_status || 'Ungeklärt' }}</span>
            </div>
          </a>
          <!-- UX2e: dieselben Aktionen am Handy. Das „⋯" steht NEBEN dem Link
               (ein <button> in einem <a> wäre ungültiges HTML). -->
          <span class="ld-karte-aktionen">
            <DkAktionen
              :ref="el => setzeAktion(el, l)"
              :eintraege="aktionenFuer(l)"
              :label="`Aktionen für ${l.titel || 'dieses Lied'}`"
            />
          </span>
        </li>
      </ul>

      <div class="overflow-x-auto ld-tabelle">
        <table class="dk-table">
          <thead>
            <tr>
              <th>Titel</th>
              <th>Nummer</th>
              <th>Fassungen</th>
              <th>Rechte-Status</th>
              <th>Zuletzt gesungen</th>
              <th>Aktionen</th>
            </tr>
          </thead>
          <tbody>
            <!-- UX2d3b (Review UX2d3a/C): Der Leerzustand steht NUR in dieser
                 Zeile; sie darf erst erscheinen, wenn der Ladevorgang durch ist
                 (sonst las man „Keine Lieder gefunden", bevor die Antwort kam). -->
            <tr v-if="!loading && lieder.length === 0" data-leerzustand="lieder">
              <td colspan="6">
                <DkEmpty
                  title="Keine Lieder gefunden"
                  :text="darfSchreiben
                    ? 'Suche oder Filter anpassen — oder das erste Lied anlegen.'
                    : 'Suche oder Filter anpassen.'"
                  icon="🎼"
                >
                  <template v-if="darfSchreiben" #aktion>
                    <DkButton variant="primary" @click="neuesLied">Erstes Lied anlegen</DkButton>
                  </template>
                </DkEmpty>
              </td>
            </tr>
            <!-- UX2e (Entwurf B1, N6): alle Aktionen am Eintrag im „⋯"-Menü;
                 Rechtsklick auf die Zeile öffnet dasselbe Menü. Die Seite selbst
                 hat keinen Zeilenknopf — nur den einen Primärknopf oben. -->
            <tr
              v-for="l in lieder"
              :key="l.name"
              @contextmenu.prevent="zeilenKontextmenue($event, l)"
            >
              <td>
                <a class="dk-cell-name dk-zellen-link dk-zellen-link--dehnen" :href="'#/lieder/' + encodeURIComponent(l.name)">{{ l.titel }}</a>
                <div v-if="l.alternativtitel" class="dk-cell-email">{{ l.alternativtitel }}</div>
              </td>
              <td class="dk-cell-text">
                <span v-if="l.anzeige" :class="{ 'ld-kopie': istKopie(l) }">{{ l.anzeige }}</span>
                <span v-else class="dk-text-subtle">–</span>
              </td>
              <td>
                <span class="dk-badge ld-badge-count">{{ fassungCount(l) }}</span>
                <span v-if="l.besetzungen && l.besetzungen.length" class="ld-besetzungen">{{ l.besetzungen.join(', ') }}</span>
                <span v-else class="dk-text-subtle">–</span>
              </td>
              <td>
                <span class="dk-badge" :class="rechtePill(l.rechte_status)">
                  <span class="dk-badge-dot" />{{ l.rechte_status || 'Ungeklärt' }}
                </span>
              </td>
              <td class="dk-text-muted">{{ l.zuletzt_gesungen ? formatDate(l.zuletzt_gesungen) : '–' }}</td>
              <td class="dk-zeilen-aktion">
                <DkAktionen
                  :ref="el => setzeAktion(el, l)"
                  :eintraege="aktionenFuer(l)"
                  :label="`Aktionen für ${l.titel || 'dieses Lied'}`"
                />
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>

    <!-- Pagination -->
    <div class="dk-pagination">
      <div class="dk-text-muted">{{ lieder.length }} geladen</div>
      <div>
        <DkButton
          variant="secondary"
          size="md"
          v-if="hasMore"
          :disabled="loading"
          @click="loadMore"
        >Mehr laden</DkButton>
        <span v-else class="dk-text-subtle">Alle geladen</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import { apiCall } from '../composables/useApi.js'
import { useLadeSkelett } from '../composables/useLadeSkelett.js'
// UX2g: EINE Quelle fuer angezeigte Fehlertexte statt Floskeln wie
// "Fehler beim Laden" / "Fehler beim Speichern".
import { aktionsfehler } from '../../shared/fehlertexte.js'
import { serverDatum, GEMEINDE_ZONE } from '../../shared/zeit.mjs'
import { navigate, currentPageName } from '../router.js'
import { LIEDER_REITER } from '../menue.js'
import DiensteReiter from '../components/DiensteReiter.vue'
import { showToast } from '../composables/useToast.js'
// UX2e2: echter Papierkorb-Weg (Löschfrage, Meldung, Rückgängig).
import { papierkorbMeldung, wiederherstellen } from '../composables/papierkorb.mjs'
// UX2c (C2): Papierkorb-Löschen ohne Rückfrage, dafür „Rückgängig“ (Strg+Z).
import { useRueckgaengigAktion } from '../composables/useRueckgaengigAktion.js'
import { istKopie } from '../components/planrahmen/lied-anzeige.mjs'
import { listenArgs as liste_args, cacheArgs as liste_cache_args,
         cacheAktiv as liste_cache_aktiv, CACHE_NAME } from '../components/lieder/lieder-liste.mjs'
import { adresseSchreiben, zustandAusAdresse, pfadOhneAbfrage } from '../composables/listenzustand.mjs'
import { wortImNumerus } from '../components/ui/begriffe.mjs'
import DkButton from '../components/ui/DkButton.vue'
import DkFilterChips from '../components/ui/DkFilterChips.vue'
import DkSkelett from '../components/ui/DkSkelett.vue'
import { chipsMitZahlen, istAlle } from '../composables/filterChips.mjs'
import DkEmpty from '../components/ui/DkEmpty.vue'
// UX2e: EIN Aktionsmenü „⋯" für alle Listen (Entwurf B1).
import DkAktionen from '../components/ui/DkAktionen.vue'

const lieder = ref([])
// UX2c (C2): Rückgängig-Weg dieser Seite (Stapel-Eintrag + Meldung).
const { mitRueckgaengig } = useRueckgaengigAktion()
const loading = ref(false)
// UX2d2: Platzhalter erst nach 300 ms — schnelle Antworten flackern nicht.
const { skelettSichtbar: loadingSkelett } = useLadeSkelett(loading)
const loadingMore = ref(false)
const error = ref(null)
const hasMore = ref(false)
const start = ref(0)
const PAGE = 50
// PF2: Erstaufbau der Seite. Bei warmem Cache-Stand wird der sofort gezeigt
// (loading bleibt false), im Hintergrund still nachgeladen.
const erstaufbau = ref(true)

const searchQuery = ref('')
const filters = reactive({ gruppe: '', kategorie: '', anlass: '', rechte_status: '' })
// OP-HANDY-13: Das Filterblatt ist am Handy zunächst zu (Treffer bleiben sichtbar).
const filterBlatt = ref(false)
const suchFeld = ref(null)

const RECHTS_STATUS = ['Ungeklärt', 'Gemeinfrei', 'Lizenz vorhanden', 'Lizenz nötig']
// DES-01: Der Baustein erwartet { id, label, anzahl }; „Alle“ setzt er selbst
// davor (hier ohne Zahl — ein Rechte-Status lässt sich nicht zählen, ohne
// alle Lieder zu laden).
const rechteChipListe = chipsMitZahlen(
  RECHTS_STATUS.map(v => ({ id: v, label: v, anzahl: 0 })),
  'Alle', 'alle',
).map(c => ({ ...c }))

/** DES-01: Chip-Klick; der Baustein liefert bereits den nächsten Wert. */
function rechteStatusWaehlen(wert) {
  filters.rechte_status = istAlle(wert) ? '' : wert
  suchbegriffInAdresse()
  resetPaging()
  reload()
}

const hasAnyFilter = computed(() =>
  filters.gruppe || filters.kategorie || filters.anlass || filters.rechte_status
)

/** OP-HANDY-13: Zahl der aktiven Filter (Abzeichen am „Filter"-Knopf). */
const aktiveFilterZahl = computed(() =>
  [filters.gruppe, filters.kategorie, filters.anlass, filters.rechte_status]
    .filter(Boolean).length
)

// ── PF2: Filter-Optionen (Gruppe/Kategorie/Anlass) ─────────────────────────
// EIN Aufruf (get_lied_filteroptionen) statt vorher 1x Liedgruppen + 1x Liste
// + 30x Lied-Detail. Der Aufruf blockiert die Liste NICHT mehr: er laeuft
// parallel zum ersten Seitenaufruf (siehe onMounted).
const gruppeOptions = ref([])
const kategorieOptions = ref([])
const anlassOptions = ref([])

async function loadFilterOptions() {
  try {
    const opt = await apiCall('diakronos.psalmos.api.musik.get_lied_filteroptionen', {})
    gruppeOptions.value = opt?.gruppen || []
    kategorieOptions.value = opt?.kategorien || []
    anlassOptions.value = opt?.anlaesse || []
  } catch (e) {
    console.warn('Musik — Filter-Optionen nicht ladbar:', e)
  }
}

/** OP-UI-8: Auswahlliste geändert -> Adresse nachziehen und neu laden. */
function filterGeaendert() {
  suchbegriffInAdresse()
  resetPaging()
  reload()
}

function toggleFilter(key, value) {
  filters[key] = filters[key] === value ? '' : value
  // OP-UI-8: Filterzustand in die Adresse schreiben.
  suchbegriffInAdresse()
  resetPaging()
  reload()
}

function resetFilters() {
  filters.gruppe = ''
  filters.kategorie = ''
  filters.anlass = ''
  filters.rechte_status = ''
  searchQuery.value = ''
  suchbegriffInAdresse()
  resetPaging()
  reload()
}

function resetPaging() {
  start.value = 0
  hasMore.value = false
}

let searchTimer = null
function onSearchInput() {
  suchbegriffInAdresse()
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => { resetPaging(); reload() }, 300)
}

/**
 * OP-HANDY-13 / OP-UI-8: Suchbegriff UND Filter in die Adresse schreiben
 * (?q=…&kategorie=…), damit Suche und Filter beim Zurückkehren erhalten
 * bleiben und teilbar sind. Kein Reload — `history.replaceState` ändert nur
 * die Zeile. Die Auswertung liegt in composables/listenzustand.mjs (getestet).
 */
function suchbegriffInAdresse() {
  if (typeof window === 'undefined') return
  const pfad = pfadOhneAbfrage(window.location.href)
  const ziel = adresseSchreiben(pfad, {
    q: String(searchQuery.value || '').trim(),
    gruppenname: filters.gruppe,
    kategorie: filters.kategorie,
    anlass: filters.anlass,
    rechte_status: filters.rechte_status,
  })
  window.history.replaceState(null, '', ziel)
}

/** Suchbegriff beim Öffnen aus `?q=` übernehmen. */
function suchbegriffAusAdresse() {
  if (typeof window === 'undefined') return ''
  return zustandAusAdresse(window.location.hash).q
}

/** OP-UI-8: Filter beim Öffnen aus der Adresse übernehmen. */
function filterAusAdresse() {
  if (typeof window === 'undefined') return {}
  const z = zustandAusAdresse(window.location.hash)
  return {
    gruppe: z.gruppenname, kategorie: z.kategorie,
    anlass: z.anlass, rechte_status: z.rechte_status,
  }
}

/** Aufruf-Parameter der aktuellen Liste (Seite + Suche + Filter). */
function listenArgs(abStart) {
  return liste_args({ seite: abStart, suche: searchQuery.value, filter: filters })
}

// PF2: Nutzerbezogener Browser-Cache (stale-while-revalidate) auch fuer die
// Lieder-Liste. Der erste Seitenaufruf ohne Suche/Filter wird
// zwischengespeichert; beim Wiederbesuch zeigt die Seite den letzten Stand
// sofort und tauscht ihn still gegen den Serverstand (nur bei Unterschied).
// Rechte bleiben allein beim Server (apiCall verwirft den Stand bei 401/419;
// Nutzerwechsel leert den Cache in main.js). Die Entscheidungen liegen in
// components/lieder/lieder-liste.mjs und sind dort getestet.

function cacheArgs() {
  return liste_cache_args({ filter: filters, suche: searchQuery.value })
}

function cacheAktiv() {
  return liste_cache_aktiv({ filter: filters, suche: searchQuery.value })
}

async function reload() {
  const args = listenArgs(0)
  const frisch_laden = async () => {
    const data = await apiCall('diakronos.psalmos.api.musik.get_lieder', args)
    return data || []
  }

  // Cache-Stand sofort zeigen, dann still nachladen.
  let gecacht = null
  if (cacheAktiv()) {
    try {
      const { standLesen } = await import('../composables/usePlanrahmenCache.js')
      gecacht = standLesen(CACHE_NAME, cacheArgs())
    } catch { /* Speicher nicht verfuegbar -> normales Laden */ }
  }

  if (gecacht && gecacht.length) {
    lieder.value = gecacht
    start.value = gecacht.length
    hasMore.value = gecacht.length >= PAGE
    loading.value = false
    erstaufbau.value = false
  } else if (!cacheAktiv()) {
    // Filter/Suche: immer die Ladeanzeige zeigen, nie alte Zeilen stehen lassen.
    loading.value = true
    error.value = null
  } else {
    // Erstaufbau ohne Cache-Stand: Skeleton nur beim allerersten Aufbau.
    loading.value = erstaufbau.value
    error.value = null
  }

  try {
    const data = await frisch_laden()
    const geaendert = !gecacht || JSON.stringify(gecacht) !== JSON.stringify(data)
    if (geaendert) {
      lieder.value = data
      start.value = data.length
      hasMore.value = data.length >= PAGE
    }
    if (cacheAktiv()) {
      try {
        const { standSchreiben } = await import('../composables/usePlanrahmenCache.js')
        standSchreiben(CACHE_NAME, cacheArgs(), data)
      } catch { /* egal */ }
    }
  } catch (err) {
    // Bei warmem Cache-Stand die Anzeige NICHT kippen (stale ist besser als leer).
    if (!gecacht) {
      error.value = aktionsfehler('laden', err)
    }
    console.error('Lieder — Fehler:', err)
  } finally {
    loading.value = false
    erstaufbau.value = false
  }
}

async function loadMore() {
  if (loading.value || loadingMore.value || !hasMore.value) return
  loadingMore.value = true
  try {
    const data = await apiCall('diakronos.psalmos.api.musik.get_lieder', listenArgs(start.value))
    lieder.value = lieder.value.concat(data || [])
    start.value = lieder.value.length
    hasMore.value = (data || []).length >= PAGE
  } catch (err) {
    console.error('Lieder — Mehr laden Fehler:', err)
  } finally {
    loadingMore.value = false
  }
}

function fassungCount(l) {
  // Echte Fassungszahl aus dem Backend; besetzungen.length nur als
  // Rueckfallebene, falls ein aelterer Endpoint sie nicht liefert.
  const n = typeof l.anzahl_fassungen === 'number'
    ? l.anzahl_fassungen
    : (l.besetzungen ? l.besetzungen.length : 0)
  return n
}

function rechtePill(s) {
  if (s === 'Gemeinfrei') return 'dk-badge-success'
  if (s === 'Lizenz vorhanden') return 'dk-badge-info'
  if (s === 'Lizenz nötig') return 'dk-badge-warning'
  return 'dk-badge-danger'
}

/** ZEIT-2: `zuletzt_gesungen` ist ein DATUM (kein Zeitpunkt) — bleibt der Tag. */
function formatDate(val) {
  if (!val) return ''
  const d = serverDatum(val)
  if (!d) return String(val)
  return new Intl.DateTimeFormat('de-DE', {
    day: '2-digit', month: 'short', year: 'numeric', timeZone: GEMEINDE_ZONE,
  }).format(d)
}

onMounted(() => {
  // PF2: Liste und Filter-Optionen laufen PARALLEL — die Liste wartet nicht
  // mehr auf die Optionen (vorher 1x Liedgruppen + 80er-Stichprobe + 30
  // Detail-Aufrufe davor).
  // OP-HANDY-13: Suchbegriff aus der Adresse übernehmen (teilbare/erhaltene Suche).
  searchQuery.value = suchbegriffAusAdresse()
  // OP-UI-8: Filter ebenfalls aus der Adresse übernehmen — sonst gingen sie
  // beim Zurückkehren aus einem Lied verloren.
  Object.assign(filters, filterAusAdresse())
  if (searchQuery.value || hasAnyFilter.value) filterBlatt.value = true
  reload()
  loadFilterOptions()
  rechteLaden()
})
onUnmounted(() => clearTimeout(searchTimer))

/* ── LI1: „Neues Lied“ nur für Schreibberechtigte ────────────────────────── */
// Das Recht kommt vom Server (diakronos.planrahmen.api.lied_rechte) — dieselbe
// Regel, die save_lied prüft. Ohne Auskunft wird nichts angeboten.
const darfSchreiben = ref(false)

async function rechteLaden() {
  try {
    const erg = await apiCall('diakronos.planrahmen.api.lied_rechte', {})
    darfSchreiben.value = !!erg?.darf_schreiben
  } catch (e) {
    darfSchreiben.value = false
  }
}

function neuesLied() {
  navigate('#/lieder/neu')
}

/* ── UX2e · Aktionsmenü „⋯" an jedem Lied (Entwurf B1, N6/K4) ──────────────
   Einträge dieses Lieds:
     · Lied öffnen                (immer)
     · Bearbeiten                 (nur mit Schreibrecht — dieselbe Auskunft
                                   wie der „Neues Lied"-Knopf, `darfSchreiben`)
     · In den Papierkorb legen    (gefährlich, abgesetzt am Ende)
   Der Papierkorb ist `save_lied` mit `aktiv = false`: das Lied verschwindet
   aus der Auswahl der Pläne, bleibt aber mit allen Fassungen erhalten. Ein
   echtes Löschen gibt es in der Lieder-Ablage nicht — der Eintrag verspricht
   deshalb auch nicht mehr (S4: ein Begriff, ein Verhalten). */
const aktionRefs = new Map()
function setzeAktion(el, l) {
  if (!l?.name) return
  if (el) aktionRefs.set(l.name, el)
  else aktionRefs.delete(l.name)
}

async function bearbeiten(l) {
  navigate('#/lieder/' + encodeURIComponent(l.name))
}

/**
 * Punkt 1 (UX2e2) · „In den Papierkorb legen“ läuft über den ECHTEN
 * Papierkorb-Weg: musik.delete_lied → papierkorbMeldung mit „Rückgängig“
 * (= musik.wiederherstellen_lied).
 * UX2c (C2): KEINE Rückfrage mehr — der Papierkorb ist umkehrbar (Prinzip
 * I2), also sofort ausführen und „Rückgängig“ anbieten (10 s = `ANZEIGE_MS`, Strg+Z).
 * Vorher lief hier `save_lied {aktiv: false}` — das nahm das Lied nur aus der
 * Auswahl, ohne Papierkorb und ohne Rückgängig.
 */
async function inPapierkorb(l) {
  try {
    const antwort = await apiCall('diakronos.psalmos.api.musik.delete_lied', { lied: l.name })
    await reload()
    await mitRueckgaengig({
      beschreibung: papierkorbMeldung(l.titel, antwort?.wiederherstellbar_bis),
      zurueck: () => wiederherstellen('lied', l.name),
      danach: reload,
      erfolg: `„${l.titel}“ wiederhergestellt.`,
    })
  } catch (e) {
    showToast(aktionsfehler('löschen', e), 'error')
  }
}

function aktionenFuer(l) {
  const eintraege = [
    {
      key: 'oeffnen', label: 'Lied öffnen', icon: 'ansehen',
      aktion: () => navigate('#/lieder/' + encodeURIComponent(l.name)),
    },
  ]
  if (darfSchreiben.value) {
    eintraege.push({
      key: 'bearbeiten', label: 'Bearbeiten', icon: 'bearbeiten',
      aktion: () => bearbeiten(l),
    })
    eintraege.push({
      key: 'papierkorb', label: 'In den Papierkorb legen', icon: 'entfernen',
      gefahr: true,
      aktion: () => inPapierkorb(l),
    })
  }
  return eintraege
}

/** Rechtsklick auf die Zeile/Karte öffnet dasselbe Menü. */
function zeilenKontextmenue(ereignis, l) {
  aktionRefs.get(l?.name)?.oeffnenFuerZeile(ereignis, ereignis?.currentTarget)
}
</script>

<style scoped>
@keyframes dk-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}
.dk-cell-text { font-size: var(--fs-14); color: var(--dk-text); }
.dk-cell-email { font-size: var(--fs-12); color: var(--dk-text-subtle); }
.dk-cell-name { font-size: var(--fs-14); font-weight: var(--fw-mittel); color: var(--dk-text); }
.ld-badge-count {
  background: var(--dk-surface-2);
  border: 1px solid var(--dk-border);
  color: var(--dk-text-muted);
  margin-right: 6px;
}
.ld-besetzungen { font-size: var(--fs-12); color: var(--dk-text-muted); }
.ld-kopie { font-style: italic; color: var(--dk-text-muted); }
/* DES-02: Die Inline-Angaben der Werkzeugleiste sind hier zu Klassen geworden. */
.ld-toolbar { display: flex; flex-direction: column; gap: var(--sp-3); align-items: stretch; }
.dk-toolbar-row { display: flex; gap: var(--sp-2); align-items: center; flex-wrap: wrap; }

/* DES-R21: Eine Filterzeile. Chip-Gruppe links, dann drei beschriftete
   Auswahlfelder, die ihre Breite teilen statt über die ganze Seite zu laufen. */
.ld-filterzeile { gap: var(--sp-3); }
.ld-filter-feld {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  min-width: 0;
}
.ld-filter-label { font-size: var(--fs-sm); color: var(--muted); white-space: nowrap; }
.ld-select {
  min-width: 130px;
  max-width: 210px;
  font-size: var(--fs-sm);
  padding: 5px 10px;
  text-overflow: ellipsis;
}
.ld-filter-reset { margin-left: auto; }
.ld-error {
  padding: 20px;
  background: color-mix(in oklch, var(--dk-danger) 8%, var(--dk-surface));
  border: 1px solid color-mix(in oklch, var(--dk-danger) 25%, var(--dk-surface));
  border-radius: 12px;
  color: var(--dk-danger);
  font-size: var(--fs-14);
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.ld-empty { text-align: center; padding: 32px 0; }
/* LI1: „Neues Lied“ steht in der Kopfzeile und bleibt mobil gut erreichbar. */
.ld-neu { flex: none; }

/* ── OP-HANDY-13: Mobilfreundliche Liste ─────────────────────────────────── */
/* Der „Filter"-Knopf und die Karten sind nur am Handy nötig; am Desktop
   bleiben die gewohnte Tabelle und die offene Filterzeile. */
.ld-filter-knopf { display: none; }
/* FIX-3: Der Knopf steht am Handy neben dem Suchfeld und ist ein DkButton
   (Höhe --control-h = --filter-h); das Feld daneben kommt seit FIX-3 ebenfalls
   auf --filter-h. Kein eigenes Maß mehr an dieser Stelle. */
.ld-filter-zahl {
  display: inline-grid; place-items: center; min-width: 16px; height: 16px;
  margin-left: 5px; padding: 0 4px; border-radius: 8px;
  background: var(--primary); color: var(--primary-ink); font-size: var(--fs-12);
}
.ld-karten { list-style: none; margin: 0; padding: 0; display: none; flex-direction: column; gap: var(--sp-2); }
.ld-karte {
  background: var(--dk-surface); border: 1px solid var(--dk-border);
  border-radius: 12px; padding: var(--sp-3); cursor: pointer;
  display: flex; flex-direction: column; gap: 6px;
}
.ld-karte-kopf { display: flex; align-items: baseline; justify-content: space-between; gap: var(--sp-2); }
.ld-karte-titel { font-size: var(--fs-14); font-weight: var(--fw-fett); color: var(--dk-text); }
.ld-karte-kennung { font-size: var(--fs-12); color: var(--dk-text-muted); flex: none; }
.ld-karte-alt { font-size: var(--fs-12); color: var(--dk-text-subtle); }
.ld-karte-meta { display: flex; flex-wrap: wrap; gap: 6px; }
/* UX2e: Platz für das „⋯" rechts oben — der Titel bekommt den Knopf nicht ins
   Gehege. */
.ld-karte-kopf { padding-right: var(--control-h); }
/* UX2e: Das „⋯" der Liedkarte (Handy-Liste) sitzt oben rechts; die Karte
   bleibt ganz Link, der Knopf steht daneben im Listenpunkt. */
.ld-karte-li { position: relative; }
.ld-karte-aktionen {
  position: absolute;
  top: var(--sp-1);
  right: var(--sp-1);
}

@media (max-width: 700px) {
  .ld-neu { width: 100%; justify-content: center; }
  /* Filter nur auf Wunsch (Blatt), Treffer als Karten statt breiter Tabelle.
     FIX-3: Feld und Knopf teilen sich die Zeile. Vorher fraß das Feld
     (flex: 1 1 auto, aber mit min-width 220px) die ganze Breite und der Knopf
     rutschte darunter — der Befund „unterschiedlich groß“ war auch ein
     Zeilenproblem. Jetzt: Feld nimmt den Rest, Knopf behält seine Breite. */
  .ld-suche { flex: 1 1 0; min-width: 0; }
  .ld-filter-knopf { display: inline-flex; flex: none; }
  .ld-filterzeile { display: none !important; }
  .ld-filterzeile.is-offen { display: flex !important; }
  .ld-karten { display: flex; }
  .ld-tabelle { display: none; }
  .ld-filter-feld { flex: 1 1 140px; }
  .ld-select { min-width: 110px; max-width: none; flex: 1 1 110px; }
  .ld-filter-reset { margin-left: 0; }
}
</style>
