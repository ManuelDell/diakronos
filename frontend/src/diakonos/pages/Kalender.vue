<template>
  <!-- UX3i (Entwurf A4): EIN Seitenraster.
         Kopfzeile (Reiter links, Werkzeuge rechts) · darunter links das
         Raster in einer Karte mit Kartenkopf „November 2026 / KW 44–49“ und
         rechts — NUR für Moderatoren — die Spalte „Zu prüfen“.
         Die frühere dunkle Kalenderliste links ist entfallen (Auswahl jetzt
         als Popover am Knopf „Kalender“, Verwalten/Import/Hilfe im ⋯-Menü). -->
  <div class="kronos-page-content">
    <KronosTopbar
      :dateTitle="dateTitle"
      :currentView="currentView"
      :canWrite="hasWriteRight"
      :canModerate="darfPruefen"
      :offeneZahl="offeneZahl"
      :eingeblendet="eingeblendetZahl"
      :auswahlOffen="auswahlOffen"
      :istKalenderAdmin="istKalenderAdmin"
      :lesemodus="lesemodus"
      @prev="calendarRef?.prev()"
      @next="calendarRef?.next()"
      @today="calendarRef?.today()"
      @viewChange="onViewChange"
      @resourceToggle="onResourceToggle"
      @sidebarToggle="kronosSidebar.umschalten()"
      @kalenderAuswahlUmschalten="kalenderAuswahlUmschalten"
      @terminAnlegen="terminAnlegen"
      @hilfe="hilfeOeffnen"
      @lesemodusWechsel="onLesemodusWechsel"
      @abgelehnteTermine="abgelehnteListeOeffnen"
    />

    <div class="kronos-calendar-wrap">
      <!-- OP-UI-11: Die Kalenderliste ist am HANDY weiterhin ein einklappbares
           Feld (Overlay) — dort ist das Popover zu klein für CalDAV-Anleitung
           und Import. Am Desktop ist sie ausgeblendet; A10 (Mobil) ist eine
           eigene, spätere Karte. -->
      <KronosSidebar
        ref="sidebarRef"
        class="kronos-sidebar-inpage"
        :open="kronosSidebar.offen.value"
        @close="kronosSidebar.zu()"
        @ablehnungClick="zeigeAbgelehntenTermin"
        @calendarsChange="onCalendarsChange"
      />

      <!-- Die Kalenderfläche: Karte mit Kopf (Monat links, Kalenderwochen
           rechts) und darin das Raster. -->
      <div class="kal-flaeche">
        <div class="kal-karte">
          <div class="kal-karte-kopf">
            <h2 class="kal-karte-titel">{{ monat }}</h2>
            <span v-if="kwText" class="kal-karte-kw">{{ kwText }}</span>
          </div>
          <!-- Am Handy ist der Kartenkopf ausgeblendet (A10 gestaltet den
               Mobil-Kalender); der Monat muss dort trotzdem dastehen. -->
          <div v-if="monat" class="kal-monat-mobil">
            <h2 class="kal-monat-mobil-titel">{{ monat }}</h2>
            <span v-if="kwText" class="kal-monat-mobil-kw">{{ kwText }}</span>
          </div>
          <div class="kal-karte-raster">
            <KronosCalendar
              ref="calendarRef"
              :selectedCalendars="store.selectedCalendars.value"
              :viewMode="store.viewMode.value"
              @eventClick="onEventClick"
              @terminAktion="onTerminAktion"
              @dateClick="onDateClick"
              @select="onSelect"
              @datesSet="onDatesSet"
              @viewChange="onCalendarViewChange"
            />
          </div>
        </div>
        <!-- A4: rechte Spalte NUR für Moderatoren; sonst nimmt das Raster
             die Breite (die Fläche ist dann allein im Raster). -->
        <KalenderPruefPanel
          v-if="darfPruefen && !istSchmal"
          ref="pruefPanel"
          class="kal-pruef-panel"
          :zahl="panelZahl"
        />
      </div>
    </div>

    <!-- A4: Kalenderauswahl als Popover am Knopf „Kalender“. -->
    <KalenderAuswahl
      :open="auswahlOffen"
      :kalender="store.availableCalendars.value"
      :ausgewaehlt="store.selectedCalendars.value"
      :loading="store.loading.value"
      :anker="auswahlAnker"
      @schliessen="auswahlOffen = false"
      @update:ausgewaehlt="uebernehmeAuswahl"
    />

    <!-- Alle Modals -->
    <KronosEventCreate
      v-model:show="showCreate"
      :initialData="createInitialData"
      @created="onEventCreated"
    />
    <KronosEventEdit
      v-model:show="showEdit"
      :event="editEvent"
      @updated="onEventUpdated"
      @deleted="onEventDeleted"
    />
    <KronosEventView
      v-model:show="showView"
      :event="viewEvent"
    />
    <KronosDayEventsDialog
      v-model:show="showDayEvents"
      :dateStr="dayEventsDate"
      :calendarRef="calendarRef"
      :selectedCalendars="store.selectedCalendars.value"
      :viewMode="store.viewMode.value"
      @eventClick="onDayEventClick"
    />
    <KronosSeriesDialog ref="seriesDialogRef" />

    <!-- K-A (R-P1-8): Detailansicht des EIGENEN abgelehnten Termins aus der
         Kalenderliste. Vorher hing sie in App.vue an der dort gerenderten
         Kalender-Seitenleiste; seit OP-UI-11 liegt die Liste in dieser Seite,
         also auch ihre Detailansicht. -->
    <KronosEventView
      v-model:show="showAbgelehntView"
      :event="abgelehnterTermin"
    />

    <!-- Review 07.11. (R-P1-8/FIX-7): Liste der eigenen abgelehnten Termine —
         am Desktop war sie über die (dort ausgeblendete) Kalenderliste hinaus
         nicht erreichbar. Sie steht jetzt im ⋯-Menü der Kopfzeile; der Server
         liefert nur die eigenen (`get_meine_abgelehnten_termine`). -->
    <DkDialog
      v-if="showAbgelehntListe"
      :model-value="true"
      title="Abgelehnte Termine"
      size="sm"
      @schliessen="showAbgelehntListe = false"
    >
      <p v-if="!abgelehnteListe.length" class="kal-abgelehnt-leer">
        Keine abgelehnten Termine. Hier erscheint ein abgelehnter Vorschlag, bis er aus der Prüfliste verschwindet.
      </p>
      <ul v-else class="kal-abgelehnt-liste">
        <li v-for="t in abgelehnteListe" :key="t.id" class="kal-abgelehnt-zeile">
          <DkButton variant="ghost" class="kal-abgelehnt-knopf" @click="zeigeAbgelehntenTermin(t.id)">
            <span class="kal-abgelehnt-titel">{{ t.title || 'Termin ohne Titel' }}</span>
            <span class="kal-abgelehnt-datum">{{ kurzDatum(t.start) }}</span>
          </DkButton>
        </li>
      </ul>
    </DkDialog>

  </div>
</template>

<script setup>
/**
 * Kalender-Seite — Entwurf A4 (UX3i).
 *
 * Was diese Karte geändert hat (Begründungen im Kartenkommentar):
 *  * EINE Kopfzeile; das Auswahlfeld „Monat“ und der Umschalter
 *    Ansehen/Bearbeiten sind entfallen (beides doppelte Wege zum selben
 *    Zustand, der Umschalter war ein zweiter gefüllter Knopf).
 *  * Das Raster steht in einer Karte (Fläche + Schatten), der Monatstitel und
 *    „KW a–b“ stehen im Kartenkopf — nicht mehr in der Kopfzeile, nicht mehr
 *    in den Zellen.
 *  * Die Kalenderauswahl ist ein Popover; „Verwalten/Import/Hilfe“ liegen im
 *    ⋯-Menü.
 *  * Rechts steht für Moderatoren die Spalte „Zu prüfen“.
 *
 * Ziehen/Ändern (ICAL-1b) bleibt erhalten: bei bestehendem Schreibrecht ist
 * der Kalender IMMER bearbeitbar (vorher schaltete das der Umschalter frei).
 * Die Moderationsregeln (P1-1b) und der Google-/iCal-Import hängen am
 * Schreibrecht bzw. an der Kalenderverwaltung und sind unverändert
 * erreichbar.
 */
import { ref, computed, onMounted, onBeforeUnmount, onUnmounted } from 'vue'
import { useKronosStore } from '../composables/useKronosStore.js'
import { useKronosSidebar } from '../composables/useKronosSidebar.js'
import { getMeinTermin } from '../composables/useEventsApi.js'
import { getModerationCount } from '../api/kanbanApi.js'
import { showToast } from '../composables/useToast.js'
// UX2e5 (Review 07.11.): „Löschen" im „⋯"-Menü geht direkt in den Papierkorb —
// Meldung und Zurückholen kommen aus dem gemeinsamen Baustein (wie in
// Beitraege.vue/Lieder.vue), nicht aus einer zweiten Löschlogik.
import { apiCall } from '../composables/useApi.js'
import { papierkorbMeldung, wiederherstellen } from '../composables/papierkorb.mjs'
import { useRueckgaengigAktion } from '../composables/useRueckgaengigAktion.js'
import { aktionsfehler } from '../../shared/fehlertexte.js'
import { vorschlagBeginn } from '../composables/datumZeit.mjs'
import { endeAusKalender } from '../composables/datumZeit.mjs'
import KronosTopbar from '../components/kronos/KronosTopbar.vue'
import KronosSidebar from '../components/kronos/KronosSidebar.vue'
import KronosCalendar from '../components/kronos/KronosCalendar.vue'
import KalenderAuswahl from '../components/kronos/KalenderAuswahl.vue'
import KalenderPruefPanel from '../components/kronos/KalenderPruefPanel.vue'
import KronosEventCreate from '../components/kronos/KronosEventCreate.vue'
import KronosEventEdit from '../components/kronos/KronosEventEdit.vue'
import KronosEventView from '../components/kronos/KronosEventView.vue'
import KronosDayEventsDialog from '../components/kronos/KronosDayEventsDialog.vue'
import KronosSeriesDialog from '../components/kronos/KronosSeriesDialog.vue'
import DkDialog from '../components/ui/DkDialog.vue'
import DkButton from '../components/ui/DkButton.vue'
// A4: „November 2026“ und „KW 44–49“ als reine Funktionen (geprüft in
// tests/ux3i-kalender-a4.test.mjs).
import {
  kwBereich, monatstitel, weitereText,
} from '../components/kronos/chipText.mjs'
import {
  istKalenderAdmin as kalenderAdmin,
  startLesemodus,
  lesemodusNachSchalter,
} from '../components/kronos/kalenderRechte.mjs'
import { eingeblendeteZahl } from '../components/kronos/kalenderKopf.mjs'
// Review 07.11. Punkt 10: EINE Layout-Grenze (720 px) — auch im Skript.
import { istHandyBreite } from '../components/kronos/breiten.mjs'

const store = useKronosStore()
const { mitRueckgaengig } = useRueckgaengigAktion()
const kronosSidebar = useKronosSidebar()

/**
 * UX3i: Am Handy gibt es KEINE rechte Spalte und keine Karte um das Raster —
 * A10 (Mobil-Kalender) ist eine eigene, spätere Karte, und UX3i darf Mobil
 * nicht verschlechtern. Die Grenze ist dieselbe wie im CSS (720 px, reine
 * BREITE — FIX-6); hier wird sie reaktiv gelesen, damit ein Drehen/Fenster-
 * ziehen die Spalte sofort nimmt (ein `matchMedia` beim Aufbau griffe nicht).
 */
const istSchmal = ref(typeof window !== 'undefined' && istHandyBreite(window.innerWidth))
function breitePruefen() {
  if (typeof window !== 'undefined') istSchmal.value = istHandyBreite(window.innerWidth)
}
onMounted(() => {
  window.addEventListener('resize', breitePruefen)
})
onBeforeUnmount(() => {
  window.removeEventListener('resize', breitePruefen)
})
const calendarRef = ref(null)
const seriesDialogRef = ref(null)
const sidebarRef = ref(null)
const pruefPanel = ref(null)

// State
const dateTitle = ref('')
const currentView = ref('dayGridMonth')
const bereich = ref({ start: null, end: null })

// A4: Kalenderauswahl (Popover)
const auswahlOffen = ref(false)
const auswahlAnker = ref(null)
const eingeblendetZahl = computed(() =>
  eingeblendeteZahl(store.availableCalendars.value, store.selectedCalendars.value))

// A4: Kartenkopf. Der Monatstitel kommt aus der Ansicht (`datesSet`), die
// Kalenderwochen aus dem gezeigten Bereich.
const monat = computed(() => monatstitel(dateTitle.value))
const kwText = computed(() => kwBereich(bereich.value.start, bereich.value.end))

// Modal states
const showCreate = ref(false)
const createInitialData = ref({})
const showEdit = ref(false)
const editEvent = ref(null)
const showView = ref(false)
const viewEvent = ref(null)
const showDayEvents = ref(false)
const dayEventsDate = ref('')

// UXK-R10: „Termin anlegen“ und Ziehen/Ändern setzen voraus, dass der Nutzer
// auf MINDESTENS einen Kalender schreiben darf (Rechte vom Server:
// `get_accessible_calendars` -> `write`).
const hasWriteRight = computed(() =>
  (store.availableCalendars.value || []).some(c => c.write)
)

/* ── Lesemodus (Review 07.11., Variante b der Karte) ────────────────────────
 * Nacharbeit 07.11. Punkt 8: Der Modus lebt wie VOR UX3i nur im
 * Arbeitsspeicher. `localStorage` ist hier bewusst NICHT im Spiel — ein
 * gemerkter „Bearbeiten“-Zustand überlebte sonst jeden Neustart, obwohl der
 * Lesemodus der Standard ist. `view` ist der Standard; ohne Schreibrecht
 * bleibt es immer beim Lesen (UXK-R10) — der Server verweigert sonst ohnehin.
 */

/**
 * Schalter im „⋯“-Menü: Zustand setzen und die Termine neu holen.
 *
 * Nacharbeit 07.11. Punkt 5: Der Modus entscheidet, welche Einträge das
 * „⋯“-Menü je Termin anbietet („Ansehen“ vs. „Bearbeiten/Löschen“). Das alte
 * Menü kennt den neuen Modus nicht — es wird deshalb neu gebaut
 * (`neuZuordnen`), wie in `onViewModeChange`.
 */
function onLesemodusWechsel(bearbeiten) {
  store.setViewMode(lesemodusNachSchalter(bearbeiten === true, hasWriteRight.value))
  calendarRef.value?.refetchEvents()  // view_mode affects which statuses are shown
  calendarRef.value?.neuZuordnen?.()
  pruefPanel.value?.laden?.()
}
const lesemodus = computed(() => store.viewMode.value !== 'edit')

// UX3d: Reiter „Zu prüfen“ nur für Moderatoren — das Recht steht im
// Boot-Objekt (`can_moderate`), dieselbe Quelle wie `get_session_info` im
// Server. Fehlt der Schlüssel (alte Seite, Test), gilt `false`: kein Reiter
// und keine rechte Spalte, die der Server ohnehin verweigern würde.
const darfPruefen = computed(() => window.__DIakonosBOOT?.can_moderate === true)
// OP-ADMIN-10 / Review 07.11.: „Kalender verwalten“ / „Kalender importieren“
// im ⋯-Menü. Die Rolle wird EINMAL hier gelesen (dieselbe Prüfung wie bisher
// in der Kalenderliste: Administrator ODER Kalenderadministrator) und an die
// Kopfzeile gegeben. `is_admin` aus dem Boot-Objekt reichte nicht: damit
// verlor die Rolle „Kalenderadministrator“ ihre Einträge, und Mitgliederadmins
// sahen Einträge, die der Server ablehnt.
const benutzerKontext = ref(null)
const istKalenderAdmin = computed(() => kalenderAdmin(benutzerKontext.value))
async function benutzerKontextLaden() {
  try {
    benutzerKontext.value = await apiCall('diakronos.diakonos.api.session.get_current_user_context')
  } catch (_) {
    // Ohne Kontext keine Verwaltungs-Einträge (fail closed) — der Kalender
    // selbst bleibt benutzbar.
    benutzerKontext.value = null
  }
}
// Zahl offener Prüfungen für Reiter und Spalte. `null` heißt unbekannt —
// dann steht keine Zahl (nie eine erfundene 0). Ein Fehler bleibt still:
// eine Kennzahl darf den Kalender nicht stören.
const offeneZahl = ref(null)
const panelZahl = computed(() => (offeneZahl.value === null ? null : offeneZahl.value))

async function offeneZahlLaden() {
  if (!darfPruefen.value) return
  try {
    const anzahl = await getModerationCount()
    const n = Number(anzahl?.count)
    offeneZahl.value = Number.isFinite(n) ? n : null
  } catch (_) {
    offeneZahl.value = null
  }
}

// FIX-7: Die Kalenderliste (Meine Kalender, Abgelehnte Termine, Hilfe) ist ab
// 721 px Breite ausgeblendet, weil nur der Handy-Umschalter (`display: none`
// am Desktop) sie oeffnet. Ohne diesen Aufruf waren ihre Eintraege auf dem
// Desktop unerreichbar (im Browser gemessen 2026-11-05: sichtbare Breite 0).
// Nur am Handy (≤ 720 px) ist `.open` ein Overlay über dem Kalender.
// UX3i: Am Desktop gehört die Auswahl jetzt in das Popover; die Leiste bleibt
// für den Handy-Betrieb und für „Hilfe & Infos“ erreichbar.
onMounted(() => { if (window.matchMedia('(min-width: 721px)').matches) kronosSidebar.zu() })

function onDatesSet(info) {
  dateTitle.value = info.title || info.view?.title || ''
  bereich.value = { start: info.start || null, end: info.end || null }
  const start = info.start
  if (start) {
    store.setCurrentMonth(start)
  }
}

/* ── A4: Kalenderauswahl ─────────────────────────────────────────────────── */
function kalenderAuswahlUmschalten() {
  if (auswahlOffen.value) {
    auswahlOffen.value = false
    return
  }
  // Lage am Auslöser messen, bevor das Popover erscheint (sonst springt es).
  const ausloeser = document.querySelector('[data-kalender-ausloeser="1"]')
  auswahlAnker.value = ausloeser ? ausloeser.getBoundingClientRect() : null
  auswahlOffen.value = true
}

/** Auswahl aus dem Popover: EINE Wahrheit (Store, wie bisher gespeichert). */
function uebernehmeAuswahl(namen) {
  store.setSelectedCalendars([...(namen || [])])
}

/** „+ Termin anlegen“: derselbe Dialog, vorbelegt mit dem Vorschlag (DEV-5). */
function terminAnlegen() {
  const jetzt = new Date()
  const tag = `${jetzt.getFullYear()}-${String(jetzt.getMonth() + 1).padStart(2, '0')}-${String(jetzt.getDate()).padStart(2, '0')}`
  const beginn = vorschlagBeginn()
  const ende = defaultEndZeit(beginn)
  createInitialData.value = {
    element_start: `${tag}T${beginn}`,
    element_end: `${endeTagAusZeit(tag, beginn, ende)}T${ende}`,
  }
  showCreate.value = true
}

/** „Hilfe & Infos“ aus dem ⋯-Menü: die vorhandene Erklärung der Leiste. */
function hilfeOeffnen() {
  sidebarRef.value?.hilfeOeffnen?.()
}

/* ── Termine ─────────────────────────────────────────────────────────────── */
function onEventClick(event) {
  const props = event.extendedProps || {}
  if (store.isViewMode.value) {
    viewEvent.value = props
    showView.value = true
  } else {
    if (props.series_id) {
      seriesDialogRef.value?.showEditOptions(props).then(action => {
        if (action === 'edit') {
          editEvent.value = { ...props, series_id: '' }
          showEdit.value = true
        } else if (action === 'deleted') {
          // UXK-R3: Nach dem Serien-Loeschen blieben die geloeschten Termine
          // sichtbar, bis die Seite neu geladen wurde. Nacharbeit 07.11.
          // Punkt 6: derselbe Weg wie jede andere Änderung (`nachAenderung`) —
          // der zieht Raster, die Kennzahl und die Spalte „Zu prüfen“ nach,
          // statt nur die Termine neu zu holen.
          nachAenderung()
        }
      })
    } else {
      editEvent.value = props
      showEdit.value = true
    }
  }
}

/**
 * UX2e5 — Eintrag aus dem „⋯"-Menü eines Termins in der Terminliste.
 * Das Widget kennt weder Adressen noch Rechte; hier wird entschieden, was
 * passiert. Gelöscht wird über DENSELBEN Weg wie in der Einzelansicht
 * (Papierkorb + Rückgängig, `papierkorbMeldung` / `wiederherstellen`) — keine
 * zweite, ungefragte Löschlogik (I2: Rückfrage nur für Unumkehrbares).
 *
 * REVIEW UX2e5/3: Im ANSEHEN-Modus ist „Ansehen" die einzige Handlung — wie
 * beim Klick auf die Zeile (`onEventClick`).
 * REVIEW UX2e5/4: „Löschen" bei einem EINZELTERMIN geht direkt in den
 * Papierkorb (mit Rückgängig-Meldung), es öffnet NICHT den Bearbeiten-Dialog.
 * Serientermine behalten die Rückfrage nach dem Umfang (`showEditOptions`).
 */
async function onTerminAktion({ key, termin } = {}) {
  if (!key || !termin) return
  const daten = termin.extendedProps ? { ...termin, ...termin.extendedProps } : { ...termin }
  if (store.isViewMode.value) {
    viewEvent.value = daten
    showView.value = true
    return
  }
  if (key === 'ansehen') {
    viewEvent.value = daten
    showView.value = true
    return
  }
  if (key === 'bearbeiten') {
    if (daten.series_id) {
      seriesDialogRef.value?.showEditOptions(daten).then(action => {
        if (action === 'edit') {
          editEvent.value = { ...daten, series_id: '' }
          showEdit.value = true
        } else if (action === 'deleted') {
          // Auflage Orchestrator (UX2e5): nach dem Löschen auch die Spalte
          // „Zu prüfen“ nachziehen — sonst zeigt sie den alten Stand.
          nachAenderung()
        }
      })
    } else {
      editEvent.value = daten
      showEdit.value = true
    }
    return
  }
  if (key === 'loeschen') {
    if (daten.series_id) {
      // Umfang der Serie (nur dieser / diese und folgende / alle): der Dialog
      // fragt und löscht; `deleted` löst das Neuladen aus.
      seriesDialogRef.value?.showEditOptions(daten).then(action => {
        if (action === 'deleted') nachAenderung()
      })
      return
    }
    await terminInPapierkorb(daten)
  }
}

/**
 * Löscht einen EINZELTERMIN direkt in den Papierkorb (7 Tage wiederherstellbar)
 * und bietet „Rückgängig" an — derselbe Weg wie im Bearbeiten-Dialog
 * (KronosEventEdit.vue: `delete_event` → `papierkorbMeldung`), nur ohne dessen
 * Fenster. Der Kalender holt danach neu (`refetchEvents`), damit die Zeile
 * samt ihrem „⋯" verschwindet.
 */
async function terminInPapierkorb(daten) {
  const name = daten.name || daten.extendedProps?.name || ''
  if (!name) {
    showToast('Dieser Termin lässt sich nicht löschen: seine Kennung fehlt. Bitte die Seite neu laden.', 'error')
    return
  }
  const titel = daten.element_name || daten.title || 'Termin'
  try {
    const antwort = await apiCall('diakronos.kronos.api.event_crud.delete_event', { name })
    nachAenderung()
    // UX2c-Mechanik (Review 07.11.): Meldung + Rückgängig-Stapel (Strg+Z) an EINER Stelle.
    await mitRueckgaengig({
      beschreibung: papierkorbMeldung(titel, antwort?.wiederherstellbar_bis),
      zurueck: () => wiederherstellen('termin', name),
      danach: () => nachAenderung(),
      erfolg: `„${titel}“ wiederhergestellt.`,
    })
  } catch (err) {
    showToast(aktionsfehler('löschen', err), 'error')
  }
}

function onDateClick(info) {
  if (store.isViewMode.value) {
    dayEventsDate.value = info.dateStr
    showDayEvents.value = true
  } else {
    // UXK-R1: `info.dateStr` der Kalender-Bibliothek enthaelt BEREITS die
    // Uhrzeit (Monat: `YYYY-MM-DDT00:00:00`, Woche/Tag: die geklickte Zeit).
    // Frueher wurde daran noch einmal `T{HH}:{MM}` gehaengt — daraus wurde
    // `2026-10-21T00:00:00T19:00`, der Server antwortete 417 „Ungueltiges
    // Datum“, und weil der Dialog trotzdem schloss, sah es nach Erfolg aus.
    // Jetzt: nur das reine Datum nehmen und die Uhrzeit sinnvoll vorbelegen.
    const tag = String(info.dateStr || '').slice(0, 10)
    const beginn = defaultStartZeit(info)
    const ende = defaultEndZeit(beginn)
    createInitialData.value = {
      element_start: `${tag}T${beginn}`,
      // DEV-5: 23:00 + 1 h ist der Folgetag, nicht 00:00 desselben Tages.
      element_end: `${endeTagAusZeit(tag, beginn, ende)}T${ende}`
    }
    showCreate.value = true
  }
}

/**
 * Standard-Beginnzeit fuer einen Klick (DEV-5): Woche/Tag uebernehmen die
 * angeklickte Slot-Zeit unveraendert. Das Monatsraster liefert nur 00:00 —
 * dort (und bei einem reinen Tagesklick) gilt die NAECHSTE volle Stunde der
 * Browserzeit; vorher war es fest 19:00.
 */
function defaultStartZeit(info) {
  const str = String(info.dateStr || '')
  const treffer = str.match(/T(\d{2}):(\d{2})/)
  if (treffer) {
    const h = treffer[1]
    const m = treffer[2]
    // Klick um 00:00 (Tagesbeginn) kommt aus dem Monatsraster -> Vorschlag.
    if (h === '00' && m === '00' && info.view?.type?.startsWith('dayGrid')) {
      return vorschlagBeginn()
    }
    return `${h}:${m}`
  }
  return vorschlagBeginn()
}

/** Standard-Endzeit: eine Stunde nach dem Beginn (UXK-R1). */
function defaultEndZeit(beginn) {
  const [h, m] = String(beginn).split(':').map(Number)
  const endH = String((h + 1) % 24).padStart(2, '0')
  return `${endH}:${String(m).padStart(2, '0')}`
}

/** Endtag zu einer Endzeit: ab Mitternacht ist es der Folgetag (DEV-5). */
function endeTagAusZeit(startTag, startZeit, endeZeit) {
  const s = String(startZeit || '').match(/^(\d{1,2}):/)?.[1]
  const e = String(endeZeit || '').match(/^(\d{1,2}):/)?.[1]
  if (s === undefined || e === undefined) return startTag
  return Number(e) < Number(s) ? naechsterTag(startTag) : startTag
}

/** „YYYY-MM-DD“ + 1 Tag (Monats-/Jahreswechsel inklusive). */
function naechsterTag(datum) {
  const m = String(datum || '').match(/^(\d{4})-(\d{2})-(\d{2})$/)
  if (!m) return datum
  const d = new Date(Date.UTC(Number(m[1]), Number(m[2]) - 1, Number(m[3]) + 1, 12))
  const zwei = (n) => String(n).padStart(2, '0')
  return `${d.getUTCFullYear()}-${zwei(d.getUTCMonth() + 1)}-${zwei(d.getUTCDate())}`
}

function onSelect(info) {
  // UXK-R1: Auch die Auswahl (Ziehen) liefert je nach Ansicht ein reines Datum
  // (`2026-10-21`) oder einen vollen Zeitstempel. Vereinheitlichen: Tag + Zeit,
  // damit der Dialog immer ein vollstaendiges, gueltiges Datum bekommt.
  const startTag = String(info.startStr || '').slice(0, 10)
  const startZeit = zeitAusStr(info.startStr) || '09:00'
  const endeStr = String(info.endStr || '')
  // ICAL-1b: eine ganztägige Auswahl liefert ein AUSSCHLIESSLICHES Ende;
  // gespeichert wird einschliesslich (21.–22. -> Ende 22., nicht 23.).
  const endeTag = info.allDay
    ? String(endeAusKalender(endeStr.slice(0, 10), true, startTag) || '').slice(0, 10)
    : endeStr.slice(0, 10)
  const endeZeit = zeitAusStr(endeStr) || defaultEndZeit(startZeit)
  const endeEffektivTag = (endeTag && endeTag !== startTag) ? endeTag : startTag
  const endeEffektivZeit = (endeTag && endeTag !== startTag) ? endeZeit : defaultEndZeit(startZeit)
  createInitialData.value = {
    element_start: `${startTag}T${startZeit}`,
    element_end: `${endeEffektivTag}T${endeEffektivZeit}`
  }
  showCreate.value = true
}

/** Uhrzeit aus einem ISO-/DateStr ziehen (`2026-10-21T19:00:00` -> `19:00`). */
function zeitAusStr(wert) {
  const treffer = String(wert || '').match(/T(\d{2}:\d{2})/)
  return treffer ? treffer[1] : ''
}

function onCalendarsChange(calendars) {
  store.setSelectedCalendars(calendars)
}

/* K-A (R-P1-8): eigener abgelehnter Termin aus der Kalenderliste. */
const showAbgelehntView = ref(false)
const abgelehnterTermin = ref(null)

/* Review 07.11. (R-P1-8/FIX-7): Liste der eigenen abgelehnten Termine über
 * das ⋯-Menü. Datenquelle ist derselbe Aufruf wie in der Kalenderliste
 * (`get_meine_abgelehnten_termine`); der Server liefert nur die eigenen. */
const showAbgelehntListe = ref(false)
const abgelehnteListe = ref([])

async function abgelehnteListeOeffnen() {
  showAbgelehntListe.value = true
  try {
    const antwort = await apiCall('diakronos.kronos.api.calendar_get.get_meine_abgelehnten_termine')
    abgelehnteListe.value = Array.isArray(antwort) ? antwort : (antwort?.message || [])
  } catch (_) {
    // Still leer: eine leere Liste ist ehrlicher als eine Fehlermeldung über
    // einen Bereich, den man nur gelegentlich öffnet.
    abgelehnteListe.value = []
  }
}

/** Kurzes Datum („6. Nov.“) einer Terminangabe; leer, wenn unbrauchbar. */
function kurzDatum(wert) {
  if (!wert) return ''
  const d = new Date(String(wert).replace(' ', 'T'))
  if (Number.isNaN(d.getTime())) return ''
  return d.toLocaleDateString('de-DE', { day: 'numeric', month: 'short' })
}

async function zeigeAbgelehntenTermin(elementId) {
  showAbgelehntListe.value = false
  const daten = await getMeinTermin(elementId)
  if (!daten) {
    showToast('Termin konnte nicht geladen werden.', 'error')
    return
  }
  abgelehnterTermin.value = daten
  showAbgelehntView.value = true
}

function onViewChange(viewName) {
  currentView.value = viewName
  calendarRef.value?.changeView(viewName)
}

/** BF1-D: Das Kalender-Widget hat die Ansicht selbst gewechselt (z.B.
 *  Mobil-Klick im Monat -> Tagesansicht). `currentView` nachziehen, damit die
 *  Reiter dieselbe Ansicht anzeigen (eine Wahrheit). */
function onCalendarViewChange(viewType) {
  if (viewType && viewType !== currentView.value && !RESOURCE_VIEWS.has(viewType)) {
    currentView.value = viewType
  }
}

/** Resource-Timeline-Ansichten sind eine Untermenge der normalen Ansichten;
 *  die Reiter führen die Normalansicht. Bei Ressourcenansicht bleibt die
 *  zuletzt gewaehlte Normalansicht aktiv — das erledigt `onCalendarViewChange`
 *  bereits, indem es Ressourcenansichten nicht uebernimmt. */
const RESOURCE_VIEWS = new Set([
  'resourceTimelineMonth', 'resourceTimelineWeek', 'resourceTimelineDay',
])

function onResourceToggle() {
  const RESOURCE_VIEW_MAP = {
    'dayGridMonth': 'resourceTimelineMonth',
    'timeGridWeek': 'resourceTimelineWeek',
    'timeGridDay':  'resourceTimelineDay',
    'listMonth':    'resourceTimelineWeek',
  }
  const cur = currentView.value
  if (RESOURCE_VIEWS.has(cur)) {
    calendarRef.value?.changeView('dayGridMonth')
  } else {
    calendarRef.value?.changeView(RESOURCE_VIEW_MAP[cur] || 'resourceTimelineWeek')
  }
}

/**
 * UX3i: Nach jeder Änderung an einem Termin werden Raster, Kennzahl und die
 * Zeilen der Spalte „Zu prüfen“ nachgezogen — sonst zeigte die Spalte den
 * alten Stand (ein Vorschlag bleibt stehen, obwohl er geprüft wurde).
 */
function nachAenderung() {
  calendarRef.value?.refetchEvents()
  offeneZahlLaden()
  pruefPanel.value?.laden?.()
  // UX2e5: Die „⋯"-Menüs neu bauen — nach einer Änderung ist der Inhalt der
  // Zeilen ein anderer Knoten.
  calendarRef.value?.neuZuordnen?.()
}

/**
 * REVIEW UX2e5/3 (Randfall): Das Menü je Knopf wird beim Zuordnen gebaut und
 * kennt den Modus von da. Der Kalender wird beim Umschalten neu geholt (die
 * Bibliothek setzt ihre Zeilen neu und `refetchEvents` stößt den Abgleich an),
 * damit „Ansehen" im Bearbeitungsmodus wieder alle Einträge hat.
 */
function onViewModeChange(mode) {
  // UXK-R10: Ohne Schreibrecht gibt es keinen Bearbeitungsmodus.
  if (mode === 'edit' && !hasWriteRight.value) return
  store.setViewMode(mode === 'view')
  calendarRef.value?.refetchEvents()  // view_mode affects which statuses are shown
  calendarRef.value?.neuZuordnen()
}

function onEventCreated() {
  showCreate.value = false
  nachAenderung()
}

function onEventUpdated() {
  showEdit.value = false
  nachAenderung()
}

function onEventDeleted() {
  showEdit.value = false
  nachAenderung()
}

function onDayEventClick(eventData) {
  showDayEvents.value = false
  viewEvent.value = eventData
  showView.value = true
}

onMounted(async () => {
  await store.fetchAccessibleCalendars()
  offeneZahlLaden()
  benutzerKontextLaden()
  // Review 07.11.: Der LESEMODUS ist der Standard (wie vor UX3i). Der Zustand
  // lebt nur im Arbeitsspeicher (Nacharbeit Punkt 8: kein `localStorage` mehr —
  // ein gemerkter „Bearbeiten“-Zustand hätte jeden Neustart überlebt).
  // Bearbeiten schaltet der dezente Eintrag im ⋯-Menü ein
  // (`onLesemodusWechsel`); ohne Schreibrecht bleibt es beim Lesen.
  store.setViewMode(startLesemodus(null))
  // UX3f: „Termin anlegen“ aus der Befehlspalette (`#/kalender?neu=1`).
  anlegeWunschAusAdresse()
  // UX3f (Review): „Termin anlegen“ wirkt auch, wenn der Kalender SCHON offen
  // ist. Dann ändert die Palette nur den Abfrageteil des Hashes
  // (`#/kalender` -> `#/kalender?neu=1`), der Router baut die Seite nicht neu,
  // und `onMounted` liefe nie wieder. Ein `hashchange`-Zuhörer holt den Wunsch
  // nach — dasselbe Muster wie `adresseGeaendert` in Personen.vue.
  window.addEventListener('hashchange', anlegeWunschAusAdresse)
})

onUnmounted(() => {
  window.removeEventListener('hashchange', anlegeWunschAusAdresse)
})

/**
 * UX3f: Die Befehlspalette bietet „Termin anlegen“ als `#/kalender?neu=1`.
 * Der Schalter wird EINMAL beim Öffnen gelesen und sofort aus der Adresse
 * entfernt (`history.replaceState`) — sonst öffnete jedes Neuladen und jedes
 * Zurück den Dialog erneut. Ohne Schreibrecht bleibt es beim reinen
 * Seitenwechsel (der Knopf erscheint dann gar nicht erst).
 */
function anlegeWunschAusAdresse() {
  let werte
  try {
    werte = new URLSearchParams(String(location.hash || '').split('?')[1] || '')
  } catch (_) {
    return
  }
  if (werte.get('neu') !== '1') return
  const rest = String(location.hash || '').split('?')[0] || '#/kalender'
  try {
    history.replaceState(null, '', rest)
  } catch (_) {
    // Ohne history-Zugriff bleibt der Schalter stehen; der Dialog öffnet
    // trotzdem einmal — kein Grund, die Seite zu verlassen.
  }
  // Rechte kommen asynchron (`fetchAccessibleCalendars`) — kurz warten, damit
  // „Termin anlegen“ nicht an einem noch leeren Kalender-Speicher scheitert.
  const start = Date.now()
  const versuch = () => {
    if (hasWriteRight.value) {
      // UX3i: derselbe vorbelegte Dialog wie der Primärknopf „Termin
      // anlegen“ — zwei Türen, ein Ziel (Begriff/Vorbelegung identisch).
      terminAnlegen()
      return
    }
    if (Date.now() - start < 4000) setTimeout(versuch, 100)
  }
  versuch()
}

/**
 * UX2e5: Der Eintrag aus dem „⋯"-Menü eines Termins ist eine Handlung der
 * SEITE (das Widget kennt keine Adressen und keine Rechte). Öffentlich, damit
 * der Node-Test genau diesen Weg prüfen kann (Löschen → Papierkorb, Serien →
 * Rückfrage, Ansehen-Modus) — ohne eine zweite Fassung der Logik im Test.
 * `onViewModeChange` steht daneben, weil der Test den Modus auf demselben Weg
 * umstellt wie die Kopfzeile.
 */
defineExpose({ onTerminAktion, onViewModeChange })

</script>

<style scoped>
.kronos-page-content {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}
/* UX3i (A4): Die Seite bekommt denselben Rahmen wie alle anderen Seiten
   (.dk-screen: Rand und Luft) — vorher klebte das Raster am Fensterrand und
   die Kalenderliste ragte über die Kante. NUR die DESKTOP-Lage: am Handy
   bleibt der Rahmen wie bisher (A10 ist eine eigene Karte). */
@media (min-width: 721px) {
  .kronos-page-content {
    padding: var(--sp-4) var(--sp-5) var(--sp-5);
    gap: var(--sp-4);
  }
}
.kronos-calendar-wrap {
  flex: 1;
  min-height: 0;
  overflow: hidden;
  display: flex;
  align-items: stretch;
  gap: var(--sp-3);
}
/* WP8/OP-UI-11: Am Schreibtisch ist die Kalenderliste einklappbar — sie nimmt
   nur Platz ein, wenn sie gebraucht wird (Handy-Overlay, Hilfe). Die Breite
   regelt kronos.css. */

/* Die Fläche links: Karte (Raster) plus — für Moderatoren — die Spalte
   „Zu prüfen“. */
.kal-flaeche {
  display: flex;
  align-items: stretch;
  gap: var(--sp-4);
  flex: 1;
  min-width: 0;
  min-height: 0;
}
.kal-karte {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-width: 0;
  min-height: 0;
  padding: var(--karte-innen, var(--sp-4));
  border-radius: var(--radius-lg);
  background: var(--surface);
  box-shadow: var(--schatten-karte);
  border: var(--karte-rand) solid var(--rahmen-farbe);
}
.kal-karte-kopf {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--sp-3);
  padding: 0 0 var(--sp-3);
}
/* Kartenkopf links: der Monat, normal gewichtet (A4: 16/600). */
.kal-karte-titel {
  margin: 0;
  font-size: var(--fs);
  font-weight: var(--fw-fett);
  color: var(--text);
}
/* Kartenkopf rechts: „KW 44–49“ dezent — sie ist eine Orientierung, keine
   Aktion (Prinzip S2: Hierarchie über Helligkeit). */
.kal-karte-kw {
  font-size: var(--fs-sm);
  color: var(--muted);
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}
.kal-karte-raster {
  flex: 1;
  min-height: 0;
  overflow: hidden;
}
/* Review 07.11. (R-P1-8/FIX-7): Liste der eigenen abgelehnten Termine im
   Dialog — je Zeile Titel und Datum, die ganze Zeile ist der Knopf (K4). */
.kal-abgelehnt-liste {
  display: flex;
  flex-direction: column;
  gap: var(--sp-1);
  margin: 0;
  padding: 0;
  list-style: none;
}
.kal-abgelehnt-knopf {
  display: flex;
  width: 100%;
  min-height: var(--control-h);
  justify-content: space-between;
  gap: var(--sp-2);
  text-align: left;
}
.kal-abgelehnt-titel { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.kal-abgelehnt-datum { color: var(--muted); flex: none; }
.kal-abgelehnt-leer { margin: 0; color: var(--muted); }

/* Mobile Leiste (Review 07.11.): Der Monatstitel fehlte am Handy, weil der
   Kartenkopf dort ausgeblendet ist — die Person sah nicht, welchen Monat sie
   vor sich hat. Hier steht er als ruhige Zeile über dem Raster (A10 gestaltet
   den Kalender später ganz; UX3i darf Mobil nicht verschlechtern). */
.kal-monat-mobil {
  display: none;
}
.kal-monat-mobil-titel {
  margin: 0;
  font-size: var(--fs);
  font-weight: var(--fw-fett);
  color: var(--text);
}
.kal-monat-mobil-kw {
  font-size: var(--fs-sm);
  color: var(--muted);
}

/* Rechte Spalte: feste Breite, sonst nähme sie dem Raster den Platz. Der Wert
   kommt aus der Skala (--sp-8 = 64 px) — Review 07.11. hatte die festen
   320 px beanstandet. */
.kal-pruef-panel {
  width: calc(var(--sp-8) * 5);
  flex: 0 0 calc(var(--sp-8) * 5);
  overflow: auto;
}
/* FIX-6: Der Fußabstand für die untere Leiste gilt in der Mobil-Lage —
   LAYOUT, also nur die Breite (index.css «FIX-6 · Layout nur nach Breite»). */
@media (max-width: 720px) {
  .kronos-page-content {
    padding-bottom: 80px;
  }
  /* Mobil bleibt die bisherige Lage: KEINE Karte um das Raster, keine rechte
     Spalte — A10 (Mobil-Kalender) ist eine eigene Karte, und UX3i darf Mobil
     nicht verschlechtern. */
  .kal-karte {
    padding: 0;
    border-radius: 0;
    box-shadow: none;
  }
  .kal-karte-kopf { display: none; }
  .kal-karte-titel { display: none; }
  /* Der Monat steht am Handy in der eigenen Zeile (siehe `.kal-monat-mobil`). */
  .kal-monat-mobil {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: var(--sp-2);
    padding: var(--sp-2) var(--sp-2) 0;
  }
  .kronos-calendar-wrap { padding: var(--sp-2); }
}
/* OP-HANDY-9: Im Querformat darf der Inhalt scrollen, damit das Monatsraster
   seine Mindesthoehe behaelt und Termine sichtbar bleiben. */
@media (orientation: landscape) and (max-height: 480px) {
  .kronos-page-content {
    overflow-y: auto;
  }
}
</style>
