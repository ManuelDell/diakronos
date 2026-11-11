<template>
  <!-- UX3i (Entwurf A4): EIN Seitenraster.
         Kopfzeile (Reiter links, Werkzeuge rechts) · darunter links das
         Raster in einer Karte mit Kartenkopf „November 2026 / KW 44–49“ und
         rechts — NUR für Moderatoren — die Spalte „Zu prüfen“.
         Die frühere dunkle Kalenderliste links ist entfallen (Auswahl jetzt
         als Popover am Knopf „Kalender“, Verwalten/Import/Hilfe im ⋯-Menü). -->
  <div class="kronos-page-content">
    <!-- A10 (Entwurf „A10 Mobil Kalender"): Am Handy ist die Seite ein eigener
         Bau — Kopf mit Segmentsteuerung, goldene Prüf-Zeile (nur Moderatoren),
         Listen-Ansicht aus Mini-Monat + Tagesliste, schwebender Primärknopf.
         Die Kalender-Bibliothek bleibt für Monat/Woche. Desktop unverändert A4. -->
    <template v-if="istSchmal">
      <!-- A10-N2 (Review 09.11., Punkt 2): EIN Kopf. Segmente und Werkzeuge
           stehen in DERSELBEN Fläche (`KalenderKopfMobil`); die frühere eigene
           Werkzeugzeile „Kalender 3 · ‹ · › · ⋯" ist entfallen. ‹ › bewegen
           den Monat — sie stehen deshalb in der Kopfzeile des Mini-Monats
           (Liste) bzw. neben dem Monatstitel (Monat/Woche, s. u.). -->
      <KalenderKopfMobil
        :ansicht="mobilAnsichtId"
        :standard="standardAnsicht"
        :darf-pruefen="darfPruefen"
        :eingeblendet="eingeblendetZahl"
        :auswahl-offen="auswahlOffen"
        :hat-schreibrecht="hasWriteRight"
        :ist-kalender-admin="istKalenderAdmin"
        :lesemodus="lesemodus"
        @ansichtWechsel="aufMobilAnsicht"
        @kalenderauswahl="kalenderAuswahlUmschalten"
        @heute="aufHeute"
        @standardSetzen="alsStandardSetzen"
        @ressourcenplan="onResourceToggle"
        @bearbeitenUmschalten="onLesemodusWechsel(lesemodus)"
        @abgelehnteTermine="abgelehnteListeOeffnen"
        @hilfe="hilfeOeffnen"
      />

      <KalenderPruefZeile
        :darf-pruefen="darfPruefen"
        :zahl="offeneZahl"
        @oeffnen="zurPruefTafel"
      />

      <!-- Listen-Ansicht (A10): Mini-Monat + Tagesliste. -->
      <KalenderListeMobil
        v-if="mobilAnsichtId === 'liste'"
        :monat="mobilMonat"
        :gewaehlter-tag="gewaehlterTag"
        :termine="mobilTermine"
        :pruef-ids="pruefIds"
        :kalender-farbe="primaerFarbe"
        :lesemodus="lesemodus"
        @tagWechsel="tagWaehlen"
        @heute="aufHeute"
        @zurueck="calendarRef?.prev()"
        @vor="calendarRef?.next()"
        @terminOeffnen="terminOeffnenMobil"
        @terminAktion="onTerminAktion"
        @woche="aufMobilAnsicht('woche')"
        @spanne="spanneWechseln"
      />

      <!-- Monat/Woche: die vorhandene Kalender-Bibliothek, am Handy lesbar
           gemacht (Monat ohne abgeschnittene Chips, Tage mit Punkten).
           Die Monatszeile (Titel + ‹ ›) ist seit A10-N2 DIREKT im Kopf des
           Rasters: das Ereignis `datesSet` der Bibliothek meldet den Monat
           erst, wenn sie aufgebaut ist — ein Titel außerhalb des Rasters
           stünde für einen Moment (und bei einem Fehler dauerhaft) leer. -->
      <div v-else class="kal-mobil-raster">
        <!-- Der Rasterhalter steht IMMER im DOM (nur im Monat/Woche-Fall
             sichtbar): der Kalender-Baustein darf NICHT bei jeder Änderung
             neu aufgebaut werden — `offscreen` blendet ihn nur aus, statt ihn
             abzubauen (Vue hängt sonst die Bibliothek samt Zustand ab). -->
        <div class="kal-mobil-raster-halter" :class="{ offscreen: mobilAnsichtId === 'liste' }">
          <div class="kal-monat-mobil">
            <h2 class="kal-monat-mobil-titel">{{ monat }}<span v-if="!monat" class="ist-ladend" aria-hidden="true">···</span></h2>
            <span class="kal-monat-mobil-bewegung">
              <DkButton
                variant="ghost"
                class="kal-monat-mobil-pfeil"
                aria-label="Vorheriger Zeitraum"
                title="Zurück"
                @click="calendarRef?.prev()"
              >
                <template #icon><DkSymbol name="zurueck" :groesse="16" /></template>
              </DkButton>
              <DkButton
                variant="ghost"
                class="kal-monat-mobil-pfeil"
                aria-label="Nächster Zeitraum"
                title="Weiter"
                @click="calendarRef?.next()"
              >
                <template #icon><DkSymbol name="weiter" :groesse="16" /></template>
              </DkButton>
            </span>
          </div>
          <KronosCalendar
            ref="calendarRef"
            :selectedCalendars="store.selectedCalendars.value"
            :viewMode="store.viewMode.value"
            :monat-punkte="!istSchmal"
            @eventClick="onEventClickMobil"
            @terminAktion="onTerminAktion"
            @dateClick="onDateClick"
            @select="onSelect"
            @datesSet="onDatesSet"
            @viewChange="onCalendarViewChange"
            @bereit="rasterBereit = true"
          />
          <!-- A10-N2 (Punkt 2): Bis die Bibliothek steht, liegt ein ruhiger
               Zustand über der Fläche — sonst wirkte der Monat beim Umschalten
               wie eine leere, weiße Karte. KEIN Ladeprosatext (UX2d3a): drei
               ruhige Balken, für die Vorlesehilfe `role="status"` mit kurzem
               Wort. -->
          <div v-if="!rasterBereit" class="kal-mobil-ladend" role="status" aria-label="Kalender wird aufgebaut">
            <span aria-hidden="true"></span><span aria-hidden="true"></span><span aria-hidden="true"></span>
          </div>
        </div>
      </div>
    </template>

    <KronosTopbar
      v-if="!istSchmal"
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
           und Import. Am Desktop ist sie ausgeblendet.
           A10: Am Handy öffnet der Knopf „Kalender“ in der Werkzeugzeile
           dieses Feld; „Hilfe & Infos“ steht im „⋯“-Menü. -->
      <KronosSidebar
        ref="sidebarRef"
        class="kronos-sidebar-inpage"
        :class="{ open: kronosSidebar.offen.value }"
        :open="kronosSidebar.offen.value"
        @close="kronosSidebar.zu()"
        @ablehnungClick="zeigeAbgelehntenTermin"
        @calendarsChange="onCalendarsChange"
      />

      <!-- Die Kalenderfläche: Karte mit Kopf (Monat links, Kalenderwochen
           rechts) und darin das Raster. A10: nur am Desktop — am Handy steht
           das Raster in `.kal-mobil-raster` (siehe oben). -->
      <div v-if="!istSchmal" class="kal-flaeche">
        <div class="kal-karte">
          <div class="kal-karte-kopf">
            <h2 class="kal-karte-titel">{{ monat }}</h2>
            <span v-if="kwText" class="kal-karte-kw">{{ kwText }}</span>
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

    <!-- A10, Punkt 5: der schwebende Knopf „+ Termin anlegen“ (56 px) über der
         unteren Leiste — der EINE Primärknopf der Mobil-Ansicht, nur mit
         Schreibrecht. Am Desktop steht der Knopf in der Kopfzeile (A4). -->
    <button
      v-if="istSchmal && hasWriteRight"
      type="button"
      class="kal-fab"
      data-primaer="1"
      aria-label="Termin anlegen"
      @click="terminAnlegen"
    >
      <DkSymbol name="hinzufuegen" :groesse="20" />
      <span>Termin anlegen</span>
    </button>

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
      :laedt="ansichtLaedt"
      :handy-lage="istSchmal"
      :bearbeiten-erlaubt="darfOeffnenBearbeiten"
      @bearbeiten="ausBlattBearbeiten"
      @freigeben="ausBlattFreigeben"
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
      :handy-lage="istSchmal"
      :bearbeiten-erlaubt="false"
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
import { ref, computed, onMounted, onBeforeUnmount, onUnmounted, watch } from 'vue'
import { useKronosStore } from '../composables/useKronosStore.js'
import { useKronosSidebar } from '../composables/useKronosSidebar.js'
import { getMeinTermin } from '../composables/useEventsApi.js'
import { getModerationCount, getBoardData, resolveConflict } from '../api/kanbanApi.js'
// A10: „Zu prüfen“-Zeile und Termin-Blatt führen auf die vorhandene Tafel.
import { navigate } from '../router.js'
import { showToast } from '../composables/useToast.js'
// UX2e5 (Review 07.11.): „Löschen" im „⋯"-Menü geht direkt in den Papierkorb —
// Meldung und Zurückholen kommen aus dem gemeinsamen Baustein (wie in
// Beitraege.vue/Lieder.vue), nicht aus einer zweiten Löschlogik.
import { apiCall } from '../composables/useApi.js'
import { papierkorbMeldung, wiederherstellen } from '../composables/papierkorb.mjs'
import { useRueckgaengigAktion } from '../composables/useRueckgaengigAktion.js'
import { aktionsfehler } from '../../shared/fehlertexte.js'
import { wandZeit } from '../../shared/zeit.mjs'
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
// DEV-B6 (Review-Nacharbeit 10.11.): Das Handy-Gerüst der Seite hängt an der
// EINEN Handy-Lage der App (`composables/handyLage.mjs`). `istHandyBreite`
// (reine Breite) ist hier NICHT mehr im Spiel — ein Maus-Laptop bei 702 px
// bekam damit das Handy-Gerüst samt unterer Leiste (Befund DMB-3a7d335074cc).
import { useHandyLage, SEITENLEISTE_SCHMAL_ABFRAGE } from '../composables/handyLage.mjs'
// A10 (Mobil-Kalender): Ansicht/Standard/Tagesliste und das Termin-Blatt.
// Reine Funktionen — hier nur die Verbindung zur Seite.
import {
  MOBIL_ANSICHTEN,
  STANDARD_VORGABE,
  ansichtKennung,
  bibliothekAnsicht,
  heuteText,
  istAnsicht,
  monatsSchluessel,
  standardLesen,
  standardSetzen,
} from '../components/kronos/mobilAnsicht.mjs'
import KalenderKopfMobil from '../components/kronos/KalenderKopfMobil.vue'
import KalenderListeMobil from '../components/kronos/KalenderListeMobil.vue'
import KalenderPruefZeile from '../components/kronos/KalenderPruefZeile.vue'
// A10: das Rollen-Abzeichen der App-Kopfzeile (am Handy neben dem Titel).
import { setzeRollenMarke } from '../composables/useBereichskopf.js'
import DkSymbol from '../components/ui/DkSymbol.vue'
// A4/A10: Farbe aus den Kalenderdaten — geprüft, bevor sie in den Stil geht.
import { sichereFarbe } from '../../shared/sichere-ausgabe.js'

const store = useKronosStore()
const { mitRueckgaengig } = useRueckgaengigAktion()
const kronosSidebar = useKronosSidebar()

/**
 * UX3i/A10: Am Handy gibt es KEINE rechte Spalte und keine Karte um das
 * Raster — dort steht der Mobil-Bau (Kopf, Liste, FAB).
 *
 * DEV-B6 (Review-Nacharbeit 10.11.): Die Lage kommt aus der EINEN Quelle
 * (`composables/handyLage.mjs`, `useHandyLage()`) — dieselbe Abfrage wie das
 * CSS (Klasse `.dk-app--handy`, gesetzt in `App.vue`) und wie `App.vue`
 * selbst. Vorher las diese Seite ihre eigene Zeiger-Abfrage und war damit ein
 * zweiter Ort; ein Maus-Laptop bei 702 px bekam das Handy-Gerüst (Befund
 * DMB-3a7d335074cc). Reaktiv über `matchMedia`-`change` UND `resize`.
 */
const { istHandyLage } = useHandyLage()
const istSchmal = istHandyLage
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
// A10-N2: Meldet das Raster, dass es steht (`@bereit`)? Bis dahin zeigt der
// Mobil-Monat/die Mobil-Woche einen Ladezustand statt einer leeren Fläche.
const rasterBereit = ref(false)
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
  // A10 (Nacharbeit 09.11.): Die MOBILE Tagesliste lädt selbst und merkt vom
  // `refetchEvents` des Rasters nichts — ohne diesen Aufruf blieb sie nach dem
  // Umschalten auf dem alten Stand (im Wegwerf-Stack: nach „Bearbeiten
  // ausschalten“ standen Vorschläge weiter in der Liste, und ein Tag sah leer
  // aus, obwohl ein festgelegter Termin existierte). Ein Modus, EINE Wahrheit.
  if (istSchmal.value) mobilTermineLaden()
}
const lesemodus = computed(() => store.viewMode.value !== 'edit')

// UX3d: Reiter „Zu prüfen“ nur für Moderatoren — das Recht steht im
// Boot-Objekt (`can_moderate`), dieselbe Quelle wie `get_session_info` im
// Server. Fehlt der Schlüssel (alte Seite, Test), gilt `false`: kein Reiter
// und keine rechte Spalte, die der Server ohnehin verweigern würde.
const darfPruefen = computed(() => window.__DIakonosBOOT?.can_moderate === true)
// A10 (Review 09.11., Punkt 4): Das Abzeichen „Moderator" steht am Handy
// neben dem Titel in der APP-Kopfzeile (Entwurf A10: Menü · Kalender
// [Moderator] · Suche). Die Seite meldet es dort — dieselbe Quelle wie
// Panel, Prüf-Zeile und Blatt (`can_moderate`), nur EINMAL ausgewertet.
// Ohne Recht meldet sie nichts: dann gibt es kein Abzeichen und keinen Platz.
watch(darfPruefen, (darf) => setzeRollenMarke(darf ? 'Moderator' : ''), { immediate: true })
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
onMounted(() => { if (!istHandyLage.value) kronosSidebar.zu() })

function onDatesSet(info) {
  dateTitle.value = info.title || info.view?.title || ''
  bereich.value = { start: info.start || null, end: info.end || null }
  // A10: Der Raster-Feed der Bibliothek ist die AUTORITÄT über den geladenen
  // Zeitraum. Vorher holte die Mobil-Liste denselben Aufruf ein zweites Mal
  // und mit ihrem eigenen Fenster (Monat + Puffer) — im Wegwerf-Stack
  // gemessen: nach „Heute“ blieben zwei Aufrufe mit verschiedenen Fenstern
  // nebeneinander stehen, und der gewählte Tag war mal leer. Jetzt übernimmt
  // die Liste GENAU die Termine, die das Raster geladen hat (ein Aufruf,
  // eine Wahrheit).
  if (info?.eventSource && typeof info.eventSource.getEvents === 'function') {
    rasterTermine.value = info.eventSource.getEvents() || []
    if (istSchmal.value) uebernehmeRasterTermine()
  }
  const start = info.start
  if (start) {
    store.setCurrentMonth(start)
  }
  // A10: Die Bibliothek ist die Wahrheit über die Ansicht (auch wenn sie
  // selbst wechselt, z.B. nach einem Klick im Monatsraster). Die Kennung
  // der Segmentsteuerung zieht nach; der Mini-Monat folgt dem Monat.
  if (istSchmal.value) {
    const kennung = ansichtKennung(info.view?.type)
    if (kennung !== mobilAnsichtId.value) mobilAnsichtId.value = kennung
    if (kennung === 'monat' || kennung === 'woche') {
      const neuerMonat = monatsSchluessel(info.start || new Date())
      if (neuerMonat !== mobilMonat.value) {
        mobilMonat.value = neuerMonat
        mobilTermineLaden()
      }
    }
  }
}

/* ── A4: Kalenderauswahl ─────────────────────────────────────────────────── */
function kalenderAuswahlUmschalten() {
  // DEV-B6b (Review 10.11., Punkt 3 — Entscheidung Operator): EIN Weg zur
  // Kalenderliste. Wo die Liste ein OVERLAY ist (Maus-Fenster ≤ 1100 px,
  // kronos.css `@media (max-width: 1100px)`, dieselbe Abfrage wie die
  // eingeklappte Seitenleiste: `SEITENLEISTE_SCHMAL_ABFRAGE`), öffnet der Knopf
  // „Kalender“ dieses Overlay. In der HANDY-LAGE bleibt es beim Popover (A10),
  // ebenso am breiten Desktop (A4).
  const listeAlsOverlay = !istHandyLage.value && typeof window !== 'undefined'
    && typeof window.matchMedia === 'function'
    && window.matchMedia(SEITENLEISTE_SCHMAL_ABFRAGE).matches
  if (listeAlsOverlay) {
    if (kronosSidebar.offen.value) kronosSidebar.zu()
    else kronosSidebar.auf()
    return
  }
  if (auswahlOffen.value) {
    auswahlOffen.value = false
    return
  }
  // Lage am Auslöser messen, bevor das Popover erscheint (sonst springt es).
  // A10: Am Handy hat der Auslöser einen eigenen Wert (`mobil`), am Desktop
  // bleibt `1` — gesucht wird der SICHTBARE Knopf (im DOM steht immer nur
  // einer von beiden, weil die Seite den Weg je Lage wählt).
  const ausloeser = document.querySelector('[data-kalender-ausloeser][data-kalender-sichtbar="1"]')
    || document.querySelector('[data-kalender-ausloeser]')
  auswahlAnker.value = ausloeser ? ausloeser.getBoundingClientRect() : null
  auswahlOffen.value = true
}

/** Auswahl aus dem Popover: EINE Wahrheit (Store, wie bisher gespeichert). */
function uebernehmeAuswahl(namen) {
  store.setSelectedCalendars([...(namen || [])])
}

/** „+ Termin anlegen“: derselbe Dialog, vorbelegt mit dem Vorschlag (DEV-5).
 *  A10: Der geladene Zeitraum der Mobil-Liste folgt dem Tag des Dialogs —
 *  sonst stand der neue Termin da, aber die Liste zeigte weiter den alten
 *  Monat und der Termin wirkte „verschwunden“ (im Wegwerf-Stack gemessen:
 *  nur der 8.11. war geladen). */
function terminAnlegen() {
  const jetzt = new Date()
  const tag = `${jetzt.getFullYear()}-${String(jetzt.getMonth() + 1).padStart(2, '0')}-${String(jetzt.getDate()).padStart(2, '0')}`
  if (istSchmal.value) {
    // Die Liste folgt dem Raster (`onDatesSet`); der Monat des Mini-Monats
    // wird mitgezogen, damit Punkte und Tagesliste denselben Ausschnitt zeigen.
    gewaehlterTag.value = tag
    const neuerMonat = tag.slice(0, 7)
    if (neuerMonat !== mobilMonat.value) {
      mobilMonat.value = neuerMonat
      mobilTermineLaden()
    }
  }
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
  // A10-N2 (Review 09.11., Punkt 1): Am HANDY führt der Tipp auf einen Tag in
  // die A10-Liste dieses Tages („Tipp auf Tag → Tagesliste"), nicht in das
  // alte Tagesblatt der Bibliothek. Vorher öffnete `showDayEvents` ein Modal
  // über dem Raster — die Tagesliste der Karte war so gar nicht zu erreichen.
  if (istSchmal.value) {
    const tag = String(info.dateStr || '').slice(0, 10)
    if (tag) {
      gewaehlterTag.value = tag
      mobilMonat.value = tag.slice(0, 7)
      mobilTermineLaden()
      aufMobilAnsicht('liste')
      return
    }
  }
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
  const d = wandZeit(String(wert))
  if (!d) return ''
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

/* ── A10 (Mobil-Kalender) ───────────────────────────────────────────────────
 * Die Regeln stehen in `components/kronos/mobilAnsicht.mjs` und
 * `mobilTermin.mjs` (reine Funktionen, geprüft in tests/a10-*); hier wird nur
 * verbunden: Ansicht, Standard je Benutzer, Tagesliste, Blatt-Handlungen.
 */

/** Kennung der Nutzersitzung — Schlüssel für den Browserspeicher. */
const mobilNutzer = computed(() => window.__DIakonosBOOT?.user_email
  || window.__DIakonosBOOT?.user_fullname || '')
/** Persönlicher Standard (ohne eigene Wahl: „Liste“, Entwurf A10). */
const standardAnsicht = ref(STANDARD_VORGABE)
/** Gewählte Ansicht der Segmentsteuerung. */
const mobilAnsichtId = ref(STANDARD_VORGABE)
/** Gewählter Tag der Listen-Ansicht (`JJJJ-MM-TT`). */
const gewaehlterTag = ref(heuteText())
/** Monat des Mini-Monats (`JJJJ-MM`). */
const mobilMonat = ref(monatsSchluessel())
/** Termine für Mini-Monat und Tagesliste (aus `get_calendar_events`). */
const mobilTermine = ref([])
/** Kennungen der zu prüfenden Termine (goldene Punkte, goldene Badges). */
const pruefIds = ref([])

/** Farbe des gewählten Tages: die des ersten eingeblendeten Kalenders. */
const primaerFarbe = computed(() => {
  const gewaehlt = new Set(store.selectedCalendars.value || [])
  const treffer = (store.availableCalendars.value || [])
    .find((k) => k && (gewaehlt.size === 0 || gewaehlt.has(k.name)))
  return sichereFarbe(treffer?.color) || ''
})

/** Standard aus dem Browserspeicher lesen (je Benutzer) und anwenden. */
function standardLaden() {
  standardAnsicht.value = standardLesen(window.localStorage, mobilNutzer.value)
  mobilAnsichtId.value = standardAnsicht.value
}

/**
 * Termine des Mobil-Bereichs holen: der gezeigte Monat plus ein Puffer, damit
 * mehrtägige Termine am Rand mit ihren Punkten erscheinen. EINE Quelle
 * (`get_calendar_events`) — dieselbe, die das Raster und die Prüf-Spalte
 * benutzen; kein neuer Endpunkt.
 */
async function mobilTermineLaden() {
  // Zeitraum: die sechs Wochen des Mini-Monats (er meldet sie über `spanne`);
  // ohne Meldung die Wochen des gezeigten Monats.
  let vonTag
  let bisTag
  if (listenSpanne.value) {
    [vonTag, bisTag] = String(listenSpanne.value).split('|')
  } else {
    const [jahr, monatNr] = mobilMonat.value.split('-').map(Number)
    const von = new Date(jahr, monatNr - 1, 1, 12)
    von.setDate(von.getDate() - 7)
    const bis = new Date(jahr, monatNr, 0, 12)   // letzter Tag des Monats
    bis.setDate(bis.getDate() + 14)
    const tag = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
    vonTag = tag(von)
    bisTag = tag(bis)
  }
  try {
    const antwort = await apiCall('diakronos.kronos.api.calendar_get.get_calendar_events', {
      start_date: vonTag,
      end_date: bisTag,
      calendar_filter: JSON.stringify(store.selectedCalendars.value || []),
      view_mode: store.isViewMode.value,
    })
    const liste = Array.isArray(antwort) ? antwort : (antwort?.message || [])
    mobilTermine.value = liste.map((t) => ({ ...t, ...(t.extendedProps || {}) }))
  } catch (_) {
    // Still leer: der Mini-Monat ohne Punkte ist ehrlicher als eine Meldung
    // über einem Bereich, der sich durch Antippen von „Heute“ neu holt.
    mobilTermine.value = []
  }
  await pruefIdsLaden()
}

/** Zu prüfende Termine (goldene Punkte) — dieselbe Quelle wie das Panel. */
async function pruefIdsLaden() {
  if (!darfPruefen.value) { pruefIds.value = []; return }
  try {
    const daten = await getBoardData()
    const liste = [
      ...(Array.isArray(daten?.vorschlaege) ? daten.vorschlaege : []),
      ...(Array.isArray(daten?.konflikte) ? daten.konflikte : []),
    ]
    pruefIds.value = liste.map((e) => String(e?.id || e?.name || '')).filter(Boolean)
  } catch (_) {
    pruefIds.value = []
  }
}

/** Segmentsteuerung: Ansicht wechseln (Bibliothek und Mobil-Liste gleichzeitig). */
function aufMobilAnsicht(id) {
  if (!istAnsicht(id)) return
  mobilAnsichtId.value = id
  calendarRef.value?.changeView(bibliothekAnsicht(id))
  if (id !== 'liste') {
    // Monat/Woche rechnet die Bibliothek; ihr `datesSet` zieht `mobilMonat`.
  } else {
    mobilMonat.value = String(gewaehlterTag.value).slice(0, 7)
    mobilTermineLaden()
  }
}

/** Mini-Monat meldet seine sechs Wochen: Termine GENAU dafür holen. */
function spanneWechseln(spanne) {
  if (!Array.isArray(spanne) || spanne.length !== 2) return
  const wert = String(spanne[0]) + '|' + String(spanne[1])
  if (listenSpanne.value === wert) return
  listenSpanne.value = wert
  mobilTermineLaden()
}

/** Tag im Mini-Monat gewählt: Tagesliste füllt sich, Monat bleibt. */
function tagWaehlen(tag) {
  if (!tag) return
  gewaehlterTag.value = String(tag).slice(0, 10)
  mobilMonat.value = gewaehlterTag.value.slice(0, 7)
  // Ein Tag aus einem anderen Monat (graue Zelle) holt dessen Termine.
  mobilTermineLaden()
}

/** „Heute“: Bibliothek und Mobil-Ansicht springen gemeinsam (eine Wahrheit). */
function aufHeute() {
  calendarRef.value?.today()
  gewaehlterTag.value = heuteText()
  mobilMonat.value = gewaehlterTag.value.slice(0, 7)
  mobilTermineLaden()
}

/**
 * „Als Standard verwenden“ aus dem „⋯“-Menü: die AKTUELL gewählte Ansicht
 * wird der persönliche Standard (je Benutzer im Browserspeicher). Kein
 * eigener Einstellungs-Dialog (Entscheidung Manuel 08.11.).
 */
function alsStandardSetzen() {
  if (standardSetzen(window.localStorage, mobilNutzer.value, mobilAnsichtId.value)) {
    standardAnsicht.value = mobilAnsichtId.value
    const name = MOBIL_ANSICHTEN.find((a) => a.id === mobilAnsichtId.value)?.label || ''
    showToast(`„${name}“ ist jetzt dein Standard auf dem Handy.`, 'ok')
  } else {
    showToast('Der Standard ließ sich nicht speichern — der Browserspeicher ist gesperrt.', 'error')
  }
}

/** Tafel „Zu prüfen“ (UX3d) — dieselbe Seite wie am Desktop. */
function zurPruefTafel() {
  navigate('#/kalender/pruefen')
}

/**
 * A10: Der geladene Zeitraum der Tagesliste — vom Mini-Monat gemeldet (die
 * sechs Wochen, die er zeigt). Nur dieser Bereich wird geholt: der Zeitraum
 * des Rasters deckt bei der Wochenansicht keine sechs Wochen ab, und der
 * Mini-Monat braucht Punkte auch für die Randtage.
 */
const listenSpanne = ref(null)

/** A10: Das Blatt lädt die vollständigen Daten des Termins nach. */
const ansichtLaedt = ref(false)
/**
 * Die Termine, die das Raster (Kalender-Bibliothek) geladen hat — EINE
 * Quelle für Mini-Monat und Tagesliste (siehe `onDatesSet`). Jeder Eintrag
 * wird auf dieselbe flache Form gebracht, die die reinen Funktionen lesen.
 */
const rasterTermine = ref([])
function uebernehmeRasterTermine() {
  const liste = Array.isArray(rasterTermine.value) ? rasterTermine.value : []
  mobilTermine.value = liste
    .filter((t) => t && !t.extendedProps?.geloescht_am)
    .map((t) => ({
      ...t.extendedProps,
      id: t.id || t.extendedProps?.name || '',
      title: t.title || t.extendedProps?.element_name || '',
      start: t.startStr || t.start,
      end: t.endStr || t.end,
      allDay: t.allDay === true || t.extendedProps?.all_day === true,
    }))
}

/** A11: Darf das Blatt „Bearbeiten“ anbieten? Nur im Bearbeiten-Modus. */
const darfOeffnenBearbeiten = computed(() => !store.isViewMode.value && hasWriteRight.value)

/**
 * Tipp auf eine Zeile der Tagesliste: dasselbe Blatt wie beim Raster-Klick.
 *
 * Die Kalenderdaten sind unvollständig (kein `event_category_name`, kein
 * `ressource_name` — im Wegwerf-Stack fehlten Kategorie und Ort im Blatt).
 * Deshalb werden die VOLLSTÄNDIGEN Daten nachgeladen (`get_mein_termin`,
 * derselbe Aufruf wie bei den eigenen abgelehnten Terminen); bis dahin läuft
 * der Ladebalken, und alte Zeilen erscheinen nicht.
 */
async function terminOeffnenMobil(termin) {
  const daten = termin?.extendedProps ? { ...termin, ...termin.extendedProps } : { ...termin }
  // A11 (Karte t_3c23f0a5): Ein Tipp auf einen Termin öffnet zuerst das BLATT
  // (Entwurf A11: „Tipp auf Termin am Handy öffnet ein Blatt von unten“) —
  // auch im Bearbeiten-Modus. Ins Formular geht es von dort über den Knopf
  // „Bearbeiten“ (`ausBlattBearbeiten`), der nur mit Recht erscheint. Vorher
  // sprang die Zeile im Bearbeiten-Modus direkt ins Formular; das Blatt war
  // damit für Schreibberechtigte am Handy gar nicht erreichbar.
  const kennung = daten.id || daten.name || daten.extendedProps?.name || ''
  viewEvent.value = daten
  showView.value = true
  if (!kennung) return
  ansichtLaedt.value = true
  try {
    const vollstaendig = await getMeinTermin(kennung)
    if (vollstaendig && showView.value) {
      viewEvent.value = { ...daten, ...vollstaendig }
    }
  } catch (_) {
    // Das Blatt behält dann die Kalenderdaten — besser als eine leere Karte.
  } finally {
    ansichtLaedt.value = false
  }
}

/**
 * Klick auf einen Termin im Mobile-Raster (Monat/Woche): derselbe Weg.
 *
 * A11-N2 (Punkt 4): IMMER zuerst das Blatt — auch im Bearbeiten-Modus. Vorher
 * sprang ein Tipp im Raster für Schreibberechtigte direkt ins Formular,
 * während eine Listenzeile das Blatt öffnete: zwei Verhalten für dieselbe
 * Geste. Ins Formular geht es aus dem Blatt über „Bearbeiten“.
 */
function onEventClickMobil(event) {
  const props = event?.extendedProps || {}
  const daten = { ...props, id: event?.id || props.name, title: event?.title || props.element_name }
  terminOeffnenMobil(daten)
}

/** „Bearbeiten“ im Termin-Blatt. */
function ausBlattBearbeiten(termin) {
  const daten = termin?.extendedProps ? { ...termin, ...termin.extendedProps } : { ...termin }
  showView.value = false
  if (daten.series_id) {
    seriesDialogRef.value?.showEditOptions(daten).then((action) => {
      if (action === 'edit') {
        editEvent.value = { ...daten, series_id: '' }
        showEdit.value = true
      } else if (action === 'deleted') {
        nachAenderung()
      }
    })
    return
  }
  editEvent.value = daten
  showEdit.value = true
}

/**
 * „Freigeben“ / „Absagen“ im Termin-Blatt — die vorhandene Moderation
 * (`resolve_conflict`), kein zweiter Weg. „Absagen“ verlangt einen Grund
 * (Server-Regel OP-EVENT-12): ohne Grund fragt das Blatt ihn nicht ab, es
 * sagt ehrlich, wo es weitergeht.
 */
async function ausBlattFreigeben({ termin, aktion } = {}) {
  const name = termin?.id || termin?.name || termin?.extendedProps?.name || ''
  if (!name) {
    showToast('Dieser Termin lässt sich nicht ändern: seine Kennung fehlt. Bitte die Seite neu laden.', 'error')
    return
  }
  if (aktion === 'absagen') {
    showView.value = false
    showToast('Zum Absagen bitte den Grund auf der Tafel „Zu prüfen“ eintragen.', 'info')
    navigate('#/kalender/pruefen')
    return
  }
  if (aktion === 'loeschen') {
    // A11-Review: „Löschen“ aus dem ⋯ des Blattes ist der vorhandene
    // Löschweg (Papierkorb + Rückgängig, Serie mit Rückfrage) — NIE Freigeben.
    showView.value = false
    await onTerminAktion({ key: 'loeschen', termin: { ...termin, name } })
    return
  }
  // Nur „freigeben“ legt fest; jeder andere/unbekannte Schlüssel tut nichts.
  if (aktion !== 'freigeben') return
  try {
    await resolveConflict(name, 'festlegen', {})
    showView.value = false
    showToast('Termin freigegeben.', 'ok')
    nachAenderung()
    mobilTermineLaden()
  } catch (err) {
    showToast(aktionsfehler('freigeben', err), 'error')
  }
}

onMounted(async () => {
  await store.fetchAccessibleCalendars()
  offeneZahlLaden()
  benutzerKontextLaden()
  // A10: persönliche Standard-Ansicht (je Benutzer) lesen und anwenden —
  // am Handy beginnt die Seite damit (ohne eigene Wahl: „Liste“).
  standardLaden()
  // DEV-B2: Ein Reiter der Prüf-Tafel bringt die gewünschte Ansicht in der
  // Adresse mit (`#/kalender?ansicht=woche`). Sie gilt VOR dem persönlichen
  // Standard — wer sie anklickt, will genau diese Ansicht sehen.
  const wunsch = ansichtsWunschAusAdresse()
  if (wunsch && istSchmal.value) mobilAnsichtId.value = wunsch
  if (istSchmal.value) {
    if (mobilAnsichtId.value !== 'liste') {
      // Die Bibliothek steht (noch) auf Monat; der Standard ist Woche/Monat.
      calendarRef.value?.changeView(bibliothekAnsicht(mobilAnsichtId.value))
    }
    mobilTermineLaden()
  } else if (wunsch) {
    currentView.value = bibliothekAnsicht(wunsch)
    calendarRef.value?.changeView(currentView.value)
  }
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
  // A10: das Abzeichen gehört zu DIESER Seite — beim Verlassen abräumen,
  // sonst stünde „Moderator“ auch auf der Übersicht (Entwurf A10 zeigt es
  // nur im Kalender).
  setzeRollenMarke('')
})

/**
 * DEV-B2 (Befund DMB-8e166c0aacff): Die Reiter der Prüf-Tafel führen als
 * LINKS zurück in den Kalender (`#/kalender?ansicht=woche`). Der Wunsch wird
 * EINMAL beim Öffnen gelesen und sofort aus der Adresse entfernt
 * (`history.replaceState`, dasselbe Muster wie `anlegeWunschAusAdresse`) —
 * sonst setzte jedes Neuladen und jedes Zurück die Ansicht erneut, und ein
 * späterer Wechsel per Reiter wäre nach einem Neuladen wieder überschrieben.
 *
 * Am Handy gilt dieselbe Wahl für die Segmentsteuerung (dort ist sie die
 * Ansicht); am Desktop für das Raster. Eine unbekannte Angabe wird
 * stillschweigend ignoriert (kein Fehler, keine geratene Ansicht).
 */
function ansichtsWunschAusAdresse() {
  let werte
  try {
    werte = new URLSearchParams(String(location.hash || '').split('?')[1] || '')
  } catch (_) {
    return null
  }
  const gewuenscht = werte.get('ansicht')
  if (!gewuenscht) return null
  if (gewuenscht !== 'neu') {
    // `neu` gehört `anlegeWunschAusAdresse` (unten) — es bleibt in der Adresse.
    const rest = String(location.hash || '').split('?')[0] || '#/kalender'
    try {
      history.replaceState(null, '', rest)
    } catch (_) {
      // Ohne history-Zugriff bleibt der Abfrageteil stehen; die Ansicht ist
      // bereits gesetzt — kein Grund, die Seite zu verlassen.
    }
  }
  return istAnsicht(gewuenscht) ? gewuenscht : null
}

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
defineExpose({
  onTerminAktion, onViewModeChange, terminOeffnenMobil, ausBlattBearbeiten, ausBlattFreigeben,
})

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
   bleibt der Rahmen wie bisher (A10 ist eine eigene Karte).
   DEV-B6 (Review-Nacharbeit 10.11.): Die Desktop-Lage wird über die KLASSE
   negiert (`:not(.dk-app--handy)`) statt über `min-width: 721px` — sonst bekam
   ein Laptop mit 702 px (Maus, Desktop-Bau!) den Handy-Rahmen ohne Rand,
   obwohl er die Desktop-Karte zeigt. */
.dk-app:not(.dk-app--handy) .kronos-page-content {
  padding: var(--sp-4) var(--sp-5) var(--sp-5);
  gap: var(--sp-4);
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
   regelt kronos.css.
   DEV-B6 (Review-Nacharbeit 10.11., Punkt 5): Am Laptop (Maus, < 720 px) war
   die Liste im FLUSS geöffnet und quetschte das Raster auf ~70 px (Belege
   `laptop-702x894-fine-hell-kalender.png`, `fenster-400x800-fine-hell-*.png`).
   Deshalb ist sie in der Handy-Lage ein OVERLAY und dort STANDARDMÄSSIG ZU
   (`useKronosSidebar`, Start false); der Weg dorthin ist der Kalender-Knopf
   der Kopfzeile (`kalenderAuswahlUmschalten` → `kronosSidebar.auf()`, siehe
   `kalenderAuswahlUmschalten` im Skript). Ein zweites Navigationselement
   braucht es daneben nicht — die App-Kopfzeile trägt den Menü-Knopf. */

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
/* DEV-B6b (Review 10.11., Punkt 4): Bei 400 px passen Raster und Prüf-Spalte
   nicht mehr nebeneinander — die Spalte rutscht UNTER das Raster (Inhalts-
   Umbruch, also BREITE, nicht Zeiger). Vorher quetschte die Spalte das Raster
   auf einen schmalen Streifen und lief selbst rechts aus dem Bild (Beleg
   `fenster-400x800-fine-hell-kalender.png`). */
@media (max-width: 720px) {
  .kal-flaeche {
    flex-direction: column;
  }
  .kal-flaeche > .kal-pruef-panel {
    flex: none;
    width: 100%;
    max-width: none;
  }
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
   vor sich hat. Hier steht er als ruhige Zeile über dem Raster (A10 zeigt ihn
   über Monats- und Wochenansicht). */
.kal-monat-mobil {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--sp-2);
  min-height: var(--treffer-handy);
  padding: var(--sp-1) 0 0;
}
.kal-monat-mobil-titel {
  margin: 0;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: var(--fs);
  font-weight: var(--fw-fett);
  color: var(--text);
}
.kal-monat-mobil-titel .ist-ladend { color: var(--muted); font-weight: var(--fw-normal); }
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
/* FIX-6: Der Fußabstand für die untere Leiste gilt in der Handy-Lage —
   Gerüst, nicht Inhalt. DEV-B6 (Manuel 09.11., Review-Nacharbeit 10.11.):
   Handy-Lage = Klasse `.dk-app--handy` (Quelle `composables/handyLage.mjs`,
   gesetzt in `App.vue`). Am Maus-Laptop mit 702 px wird KEIN Platz für die
   Leiste reserviert. Bewusst keine zweite Media-Regel — sonst entschieden
   wieder zwei Orte.
   A10-N2 (Review 09.11., Punkt 5): Die INHALTS-Regeln des Mobil-Baus hängen
   an den Mobil-Klassen (`dk-mobilkopf`, `kal-mobil-raster`,
   `kal-a10-liste`, `kal-fab`), die allein `istSchmal` im Skript setzt — und
   `istSchmal` IST seit DEV-B6 die Handy-Lage. So entscheidet genau EINE
   Stelle, wer das Handy-Layout bekommt.
   Die Wähler IN die Bibliothek hinein brauchen `:deep()`: die Elemente
   `article.ec-event`, `.ec-day`, `.ec-col-head` gehören @event-calendar und
   tragen die Scoped-Kennung der Seite NICHT (im Browser geprüft: der
   `.ec`-Container hat kein `data-v-…`, der `article` also auch nicht) — ein
   `:deep()` von der Mobil-Klasse aus durchdringt den Teleport-Ziel-Container.
   Die Lage entscheidet trotzdem allein die Klasse: `:deep()` vererbt keinen
   Scope, der Wähler beginnt bei `.kal-mobil-raster[data-v-…]`. */
.dk-app--handy .kronos-page-content {
  padding-bottom: 80px;
}
/* A10-N2 (Re-Review 09.11.): Die frühere Rücksetzung von `.kal-karte`
   (padding/radius/schatten 0) entfällt — `.kal-karte` steht NUR im
   Desktop-Zweig (`v-if="!istSchmal"`); ohne Media-Regel traf sie den
   DESKTOP und machte die A4-Karte flach. */
/* A10 (Review-Nacharbeit 10.11., Ergänzung a): Kartenkopf und Monatstitel
   verschwinden NUR am Handy. Vorher stand hier `max-width: 720px` — am
   Laptop mit 702 px (Maus) fehlten damit Monat und KW, obwohl dort der
   Desktop-Bau läuft. Die Karte selbst steht im Desktop-Zweig und wird am
   Handy ohnehin nicht gerendert. */
.dk-app--handy .kal-karte-kopf { display: none; }
.dk-app--handy .kal-karte-titel { display: none; }
.dk-app--handy .kronos-calendar-wrap { padding: var(--sp-2); }
/* A10, Punkt 4: KEINE abgeschnittenen Termin-Chips im Monatsraster. Am
   Handy zeigt jede Zelle nur die Tageszahl und einen Punkt (Kalenderfarbe
   bzw. gold für „zu prüfen“); ein Tipp auf den Tag öffnet die Tagesliste.
   Die Chip-Regeln selbst bleiben unangetastet (Desktop = A4).

   A10-N2 (Review 09.11., Punkt 1): Der Wähler war `[data-ec-event]` — ein
   Attribut, das @event-calendar 5.18 NICHT setzt (im Browser geprüft:
   `dataEcEvent: 0`). Die Regel lief damit ins Leere, und der Monat zeigte
   weiter 47×16-px-Chips mit „Ch…“. Das Element heißt `article.ec-event`
   (Klassen `ec-event ec-chip-event ec-draggable`, `data-event-id`).
   A10-N3 (Punkt 6, im Browser gemessen): Der Wähler gilt jetzt NUR für das
   MONATSRASTER. Vorher traf `.ec-event` auch die Wochenblöcke — die Woche war
   deshalb leer, obwohl Termine da sind (und der automatische Scroll lief ins
   Nichts).

   `!important` ist nötig und begründet: `kronos.css` gibt
   `.ec-event.ec-chip-event` (0-2-0) eine `display`-Regel für die Chips des
   DESKTOPS (A4); diese Regel steht global und gewinnt sonst gegen den
   `:deep`-Wähler der Seite. Der Monat bleibt unberührt, weil sein Punkt-/
   Tages-Modell (A10) die Chips in den Zellen nicht braucht. */
.kal-mobil-raster :deep(.ec-month-view .ec-event) { display: none !important; }
/* A10 (Review 09.11., Punkt 4, Wochenansicht): Am Handy sind sieben
   Tagesspalten à ~50 px. A10-N3 (Punkt 6, 10.11.): Die Terminblöcke waren
   dort komplett AUSGEBLENDET (`display: none`) — die Woche zeigte nur ein
   leeres Raster, und der Befund „Termine liegen abends, man sieht nichts“
   war in Wahrheit gar nicht scrollbar. Sie sind jetzt wieder sichtbar,
   aber auf das Nötigste eingedampft: der Block trägt nur die ANFANGSZEIT
   (`KronosCalendar` rendert für das Zeitraster Titel + Zeit; in der engen
   Lage fällt der Titel weg, s. `.ec-block-titel` unten). Der VOLLE Titel
   steht im `title`/`aria-label` und in der Tagesliste unter dem Mini-Monat.
   Desktop (Woche = A4) ist unberührt. */
.kal-mobil-raster :deep(.ec-time-grid .ec-block-titel) { display: none; }
/* In der engen Lage sitzt die Uhrzeit allein im Block, oben ausgerichtet —
   der Block bleibt so hoch wie die DAUER (die Bibliothek setzt die Höhe).
   A10-N3 (im Browser gemessen, 10.11.): In einer ~50-px-Spalte wurden aus
   „19:30–21:30“ nur „19:…“ — die Zeit wird deshalb beim Aufbau des Rasters
   gekürzt (siehe `wochenStart.engeZeit`: nur die Anfangszeit „19:30“).
   Sie steht linksbündig in einer Zeile, ohne Ellipse. */
.kal-mobil-raster :deep(.ec-time-grid .ec-block) {
  padding: 0 var(--sp-1);
  justify-content: flex-start;
  font-size: var(--fs-sm);
  line-height: 1.2;
}
.kal-mobil-raster :deep(.ec-time-grid .ec-block-zeit) {
  font-size: var(--fs-sm);
  text-overflow: clip;
}
/* Die Termine bleiben aber als PUNKTE je Tag sichtbar: sonst sähe ein Tag
   mit drei Terminen aus wie ein leerer. Die Punkte zeichnet die Bibliothek
   NICHT — `KronosCalendar.tagesPunkteNachtragen()` markiert jeden Tag mit
   Termin als `.ec-day[data-dk-termin]` und ergänzt das `aria-label` des
   Tageskopfes um „, n Termine“. Der Punkt hier ist reine Gestaltung
   (Farbe ist nie alleiniger Träger — die Zahl steht in der Vorlesehilfe). */
.kal-mobil-raster :deep(.ec-day[data-dk-termin] .ec-day-head)::after {
  content: '';
  display: block;
  width: var(--sp-1);
  height: var(--sp-1);
  margin: var(--sp-1) auto 0;
  border-radius: var(--badge-r);
  /* A10-N2 (Review 09.11., Punkt 3): `--marke-flaeche` ist in BEIDEN Themes
     Navy — auf dem dunklen Raster war der Punkt damit unsichtbar (Navy auf
     Navy). `--primary` wie der Punkt im Mini-Monat: hell navy (14,3:1),
     dunkel weiß (18,0:1). Farbe ist nie alleiniger Träger (die Zahl steht
     im `aria-label` des Tageskopfes). */
  background: var(--primary);
}
/* A10-N2: dasselbe in der WOCHENANSICHT. Dort ist der Tageskopf
   `div.ec-col-head` (im Browser gemessen; `ec-day-head` ist der Monat) —
   der Punkt sitzt unter Wochentag + Datum. */
.kal-mobil-raster :deep(.ec-week-view .ec-col-head[data-dk-termin])::after {
  content: '';
  display: block;
  width: var(--sp-1);
  height: var(--sp-1);
  margin: var(--sp-1) auto 0;
  border-radius: var(--badge-r);
  background: var(--primary);
}
/* A10-N3 (Punkt 4): Die HEUTIGE Zelle im Monatsraster ist auch im Dunkeln
   deutlich zu sehen. Vorher kam die Fläche aus `--ec-today-bg-color` =
   `--heute-flaeche` — seit A10-N2 im Dunkeln Weiß 5 % auf #0a0e22 (1,15:1),
   praktisch schwarz; hell dagegen ein warmes Beige. Die Zelle nimmt deshalb
   das Themeneigene TOKEN `--heute-zelle` (hell: Gold-Beige, dunkel: ruhiges
   Navy-Grau, an derselben Stelle gepflegt) — gleiche Logik in beiden Themes:
   Fläche ruhig sichtbar, kein Rahmen, kein Muster. Nur die Monatszelle:
   die Wochenspalte behält `--ec-today-bg-color` (`--heute-flaeche`). */
.kal-mobil-raster :deep(.ec-month-view .ec-day.ec-today) {
  --ec-day-bg-color: var(--heute-zelle);
}
/* Dazu trägt die ZAHL den Tag mit: fett (Farbe ist nie alleiniger Träger,
   Prinzip Ä4). Gilt in beiden Themes.
   A10-N3 (Review-Nacharbeit, Punkt 7): Der Kommentar sagte „fett +
   unterstrichen“ — unterstrichen war nie umgesetzt. Es bleibt bei Fett
   (die Zusage stimmt jetzt mit dem Code überein). */
.kal-mobil-raster :deep(.ec-month-view .ec-day.ec-today .ec-day-head) {
  font-weight: var(--fw-fett);
}

/* OP-HANDY-9: Im Querformat darf der Inhalt scrollen, damit das Monatsraster
   seine Mindesthoehe behaelt und Termine sichtbar bleiben. */
/* DEV-B6b (Review 10.11., Punkt 4): Im Handy-Querformat darf der Inhalt
   scrollen (OP-HANDY-9), damit das Monatsraster seine Mindesthöhe behält und
   Termine sichtbar bleiben. Das ist Gerüst-Mechanik der Handy-Lage — ein
   Desktop-Fenster (auch flach, 1280×450) behält `overflow: hidden` aus der
   Grundregel oben. Vorher galt `overflow-y: auto` ÜBERALL und der
   Desktop-Kalender bekam einen Scrollbalken, den er nicht braucht. */
@media (orientation: landscape) and (max-height: 480px) {
  .dk-app--handy .kronos-page-content {
    overflow-y: auto;
    /* DEV-B6b-Kleinfix (Punkt 6): Den Fußabstand für die Leiste trägt schon
       `.dk-app--handy .dk-content` (index.css) — doppelt (88 + 80 px) blieben
       im Querformat ~80 px für Mini-Monat und Tagesliste. */
    padding-bottom: 0;
  }
}
/* ── A10: Mobil-Ansicht ─────────────────────────────────────────────────────
   Die Liste (Mini-Monat + Tagesliste) und das Raster (Monat/Woche) scrollen
   unter dem Kopf; der schwebende Knopf liegt über der unteren Leiste. */
/* Kopf (Segmente, Werkzeuge — alles in EINEM Kopf seit A10-N2), Monatszeile
   des Rasters und die goldene Prüf-Zeile bleiben stehen; nur der Inhalt
   darunter rollt. Ohne das schrumpfte der Inhalt auf die Höhe des Kopfes und
   die TERMINE der Tagesliste lagen unter dem schwebenden Knopf bzw. wurde
   gar nicht gescrollt (im Wegwerf-Stack gemessen: Listenfläche 666 px hoch,
   Fenster 708 px).
   Die Höhe der Mobil-Fläche ist deshalb ausdrücklich das Fenster minus
   obere Leiste minus untere Leiste (A10: 844 − 56 − 64 = 724 px). */
.kronos-page-content > .dk-mobilkopf,
.kronos-page-content > .dk-pruefzeile,
.kronos-page-content > .kal-mobil-raster > .kal-monat-mobil { flex: none; }
.kal-a10-liste {
  flex: 1 1 auto;
  min-height: 0;
  height: calc(100vh - var(--topbar-h) - var(--sp-8) - env(safe-area-inset-bottom));
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
  /* Platz unter der letzten Zeile: FAB (56 px) + Rand (der Knopf liegt über
     der unteren Leiste, nicht über dem Inhalt). */
  padding-bottom: calc(var(--sp-8) + var(--sp-4));
}
/* DEV-B6 (Review 10.11., Punkt 4): Die A10-Fläche existiert NUR im Mobil-Bau
   (Handy-Lage) — dort gelten die Querformat-Abstände.
   DEV-B6b (Review 10.11., Punkt 6): Im Querformat (844×390) ist die untere
   Leiste da (Handy-Lage) — die Höhe muss sie ABZIEHEN, sonst reicht die Liste
   unter die Leiste (die letzten 64 px sind verdeckt). Gerundet wird sie
   ausdrücklich NICHT: eine Liste darf scrollen, und `padding-bottom` mit
   FAB-Platz (56 px) bleibt. */
@media (max-height: 480px) and (orientation: landscape) {
  /* DEV-B6b-Kleinfix: im Querformat rollt EINE Fläche (die Seite, s. o.) —
     die Liste schrumpft nicht auf den Rest unter dem Kopf. */
  .dk-app--handy .kal-a10-liste {
    flex: none;
    height: auto;
    overflow: visible;
    padding-bottom: calc(var(--sp-8) + var(--sp-4));
  }
}
.kal-mobil-raster {
  flex: 1 1 auto;
  min-height: 0;
  display: flex;
  flex-direction: column;
  height: calc(100vh - var(--topbar-h) - var(--sp-8) - env(safe-area-inset-bottom));
  overflow: auto;
  padding: 0 var(--sp-2) var(--sp-8);
}
/* Der Halter des Rasters (Monat/Woche) — volle Höhe, damit
   „Kalender wird geladen …“ mittig sitzt und das Raster darunter Platz hat. */
.kal-mobil-raster-halter {
  display: flex;
  flex-direction: column;
  flex: 1 1 auto;
  min-height: 100%;
  position: relative;
}
/* Die Listen-Ansicht steht an seiner Stelle: der Rasterhalter bleibt im DOM
   (die Bibliothek sonst ab- und wieder aufbauen würde), ist aber ganz weg —
   auch für Vorlesehilfe und Tastatur. */
.kal-mobil-raster-halter.offscreen {
  display: none;
}
/* Ladezustand: ruhiger Text unter der Monatszeile, keine leere Fläche. */
/* Ruhiger Aufbau-Zustand (drei Balken, kein Text — UX2d3a): sieht aus wie ein
   Platzhalter, nicht wie ein Fehler. */
.kal-mobil-ladend {
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
  margin: var(--sp-4) 0 0;
}
.kal-mobil-ladend span {
  display: block;
  height: var(--sp-6);
  border-radius: var(--radius-sm);
  background: var(--surface-2);
}
/* Monatszeile des Rasters (Monat/Woche): Titel links, ‹ › rechts — dieselbe
   Sprache wie die Kopfzeile des Mini-Monats (Liste). Beide Pfeile sind
   44-px-Ziele (K4). */
.kal-monat-mobil-bewegung {
  display: inline-flex;
  align-items: center;
  gap: var(--sp-1);
  flex: none;
}
.kal-monat-mobil-pfeil {
  flex: none;
  min-width: var(--treffer-handy);
  min-height: var(--treffer-handy);
  padding: 0;
}
.kal-monat-mobil-pfeil:deep(.dk-ui-btn) { min-height: var(--treffer-handy); }
/* Das Raster selbst füllt den Rest der Mobil-Fläche. */
.kal-mobil-raster-halter > .kronos-calendar-wrap,
.kal-mobil-raster-halter > .kronos-calendar-shell { flex: 1 1 auto; min-height: 0; }
.kal-mobil-raster .kronos-calendar-wrap { padding: 0; }
/* Der EINE Primärknopf der Mobil-Ansicht: 56 px hoch, Pillenform, über der
   unteren Leiste (72 px + Sicherheitsabstand). Rechts 16 px vom Rand. */
.kal-fab {
  position: fixed;
  right: var(--pad);
  bottom: calc(var(--sp-8) + env(safe-area-inset-bottom));
  z-index: var(--z-sticky);
  display: inline-flex;
  align-items: center;
  gap: var(--sp-2);
  min-height: 56px;
  padding: 0 var(--sp-5);
  border: none;
  border-radius: var(--badge-r);
  /* A10 (Review 09.11., Punkt 1): die FLÄCHE ist das Marken-Navy aus dem
     Token — NICHT `--primary`: das ist im Dunkelmodus Weiß, und mit der
     weißen Schrift ergäbe das eine leere weiße Pille.
     A10-N3 (Punkt 3): Im Dunkelmodus lag um die Pille ein 2-px-Hellblau-Ring
     (aus A10-N2), weil Navy auf der dunklen Fläche nur 1,16:1 hatte — der
     Ring wirkte wie ein fremdes Bedienelement. Jetzt trägt sich die FLÄCHE
     selbst: `--fab-flaeche` ist im Dunkeln ein aufgehelltes Navy
     (#2b3a6b, 2,6:1 gegen die Karte / ≥ 3:1 gegen die Seitenfläche), hell
     bleibt sie das Marken-Navy. KEIN Dauer-Ring mehr; Kontrast für die
     Tastatur gibt es nur bei `:focus-visible` (Regel darunter). */
  background: var(--fab-flaeche);
  /* A10: dunkles Navy mit heller Schrift. Die Schriftfarbe steht als Token
     (`--fab-ink`: hell weiß, dunkel das helle Navy-100 — Weiß auf dem
     aufgehellten Navy ergäbe 6,0:1, Navy-100 8,1:1). */
  color: var(--fab-ink);
  font: inherit;
  font-size: var(--fs);
  font-weight: var(--fw-fett);
  box-shadow: var(--shadow-md);
  cursor: pointer;
}
.kal-fab:hover { background: var(--fab-flaeche-hover); }
/* A10-N3 (Punkt 3): Fokusring NUR bei Tastaturbedienung — im Ruhezustand
   trägt die Fläche (kein „fremder“ Ring mehr). */
.kal-fab:focus-visible { outline: var(--ring-breite) solid var(--focus-ring); outline-offset: var(--sp-1); }
/* DEV-B6: Der FAB steht nur im Mobil-Bau (Handy-Lage).
   DEV-B6b (Review 10.11., Punkt 6): Im Querformat lag er mit `bottom: 16px`
   HINTER der unteren Leiste (64 px) — er ist jetzt genauso hoch gestellt wie
   in der Hochkant-Lage: über der Leiste plus Sicherheitsabstand. */
@media (max-height: 480px) and (orientation: landscape) {
  .dk-app--handy .kal-fab {
    bottom: calc(var(--bottom-nav-h) + env(safe-area-inset-bottom) + var(--sp-3));
  }
}
</style>
