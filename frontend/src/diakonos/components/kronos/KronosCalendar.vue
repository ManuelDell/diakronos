<script setup>
import { apiAntwortPruefen } from '../../composables/useApi.js'
// WEB-5b: Adressen unter dem Betriebs-Praefix (DIAKRONOS_BASE_PATH) bauen.
import { apiUrl } from '../../../shared/basis.js'
import { ref, onMounted, onBeforeUnmount, watch, nextTick, createApp, h } from 'vue'
import * as _EC from '@event-calendar/build'
import '@event-calendar/build/dist/event-calendar.min.css'
import { useEventsApi } from '../../composables/useEventsApi.js'
// ICAL-1: ganztägiges Ende für die Anzeige ausschließend machen (+1 Tag).
import { endeFuerKalender } from '../../composables/datumZeit.mjs'
import { useImpersonation } from '../../composables/useImpersonation.js'
import { showToast } from '../../composables/useToast.js'
import KronosSeriesDialog from './KronosSeriesDialog.vue'
import DkAktionen from '../ui/DkAktionen.vue'
import { MENUE_EINTRAEGE } from './terminAktionenMenue.mjs'
import { erstelleTerminDaten } from './terminAktionenDaten.mjs'
// UX2e5: „⋯" je Termin — der Knopf ist ein Geschwister der Bibliotheks-Zeile
// und wird per Kennung zugeordnet (siehe ./terminAktionen.mjs).
import { zuordnen } from './terminAktionen.mjs'
// P3-4b/Restpunkt 1: Schriftfarbe je Terminkachel nach Helligkeit (AA).
// UX3i3: die Termine in Woche/Liste nutzen jetzt dieselbe Chip-Logik wie der
// Monat (`chipStil` in `./chipText.mjs`) — die Kachel-Schrift der Bibliothek
// wird im Kalender nicht mehr gebraucht.
import { sichereFarbe } from '../../../shared/sichere-ausgabe.js'
// UX3i (Entwurf A4): Text, Kontrast und Zählung der Termin-Chips als reine
// Funktionen — ausführbar geprüft in `tests/ux3i-kalender-a4.test.mjs`.
import { chipText, chipTitel, chipStil, zeitBlockText } from './chipText.mjs'
// A4 (Review 07.11. Punkt 10): EINE Layout-Grenze des Kalenders (720 px).
import { istHandyBreite, istEngeBreite } from './breiten.mjs'

const EventCalendar = _EC.default?.create ? _EC.default : (_EC.create ? _EC : null)


const props = defineProps({
  selectedCalendars: { type: Array, default: () => [] },
  viewMode: { type: String, default: 'view' }
})

const emit = defineEmits([
  'eventClick',
  'dateClick',
  'select',
  'datesSet',
  'resourceViewChange',
  'viewChange',
  // UX2e5: Eintrag aus dem „⋯"-Menü eines Termins (siehe MENUE_EINTRAEGE).
  'terminAktion',
  // A10-N2: Das Raster steht (erster Aufbau) — die Seite zeigt bis dahin
  // ihren Ladezustand statt eines leeren, „kaputt“ wirkenden Kastens.
  'bereit',
])

const calendarEl = ref(null)
const seriesDialog = ref(null)
const calendar = ref(null)

/* ── UX2e5 · „⋯" je Termin in der Terminliste ──────────────────────────
 * Die Knöpfe stehen als GESCHWISTER direkt hinter ihrer Bibliotheks-Zeile
 * (siehe ./terminAktionen.mjs). Jeder Knopf ist ein eigener Vue-Knoten mit
 * seinem DkAktionen-Menü; der Halter wird im Abgleich gebaut und dort auch
 * wieder abgebaut (Rahmen + Knoten) — sonst bliebe je Neuladen ein Rahmen
 * samt offenem Menü im Speicher.
 */
const menueOffen = ref(false)
let abgleichGeplant = false
/** Kennung -> Halter-Element. NUR lebende Halter: was nicht mehr am Dokument
 *  hängt (Ansichtswechsel, Neubau der Bibliothek), wird sofort abgebaut. */
const KNOEPFE = new Map()

function istListenAnsicht() {
  const ansicht = calendar.value?.getOption('view') || ''
  return String(ansicht).startsWith('list')
}

/**
 * UX3i4 — Ist die laufende Ansicht ein ZEITRASTER (Woche/Tag)?
 *
 * Im Zeitraster ist die Höhe eines Termins seine DAUER (die Bibliothek setzt
 * `block-size` als Inline-Stil). Deshalb gilt dort die Block-Optik; Monat und
 * Liste tragen den Chip (Pille). Die Prüfung liegt an EINER Stelle, weil sie
 * an zwei Stellen gebraucht wird (`eventClassNames` UND `eventContent`) —
 * zwei getrennte Prüfungen könnten auseinanderlaufen (Prinzip S4).
 *
 * `resourceTimelineWeek` ist KEIN Zeitraster im hier gemeinten Sinn: die
 * Zeitleiste stapelt Termine je Ressource und ist ohne Dauer-Spalte; sie
 * bleibt beim Chip (wie im Monat).
 */
function istZeitrasterAnsicht() {
  const ansicht = String(calendar.value?.getOption('view') || '')
  return ansicht === 'timeGridWeek' || ansicht === 'timeGridDay'
}

/** Der Rahmen (Vue-App) eines Halters — er hängt am Inhalt darunter. */
function rahmenVon(el) {
  return el?.querySelector?.('.kronos-liste-aktionen-halter-inhalt')?.__kronosRahmen || null
}

/**
 * Ein Abgleich je Umlauf — `eventDidMount`/`eventWillUnmount` melden je Zeile;
 * abgeglichen wird danach EINMAL, nicht je Termin.
 */
function abgleichPlanen() {
  if (abgleichGeplant || !calendarEl.value) return
  abgleichGeplant = true
  nextTick(() => {
    abgleichGeplant = false
    if (!calendarEl.value || !istListenAnsicht()) {
      // Ansichtswechsel (oder Kalender schon weg): es bleibt KEIN Knopf und
      // kein Rahmen zurück — überall unter dem Kalender, nicht nur die
      // selbst gemerkten.
      alleKnoepfeAbbauen()
      return
    }
    // Halter, die nicht mehr am Dokument hängen (die Bibliothek hat sie beim
    // Neubau fortgeworfen), gehören keinem Termin mehr: erst abbauen, dann
    // neu zuordnen. Sonst bliebe für jede weggeworfene Zeile ein Rahmen.
    for (const [kennung, el] of Array.from(KNOEPFE)) {
      if (el?.isConnected) continue
      rahmenAbbauen(el)
      KNOEPFE.delete(kennung)
    }
    // UX3i4: Die Listenzeile bekommt ihre Kennzeichnung, BEVOR die „⋯“-Halter
    // gesetzt werden — die CSS-Regeln (Zeile und Halter nebeneinander) hängen
    // daran.
    zeilenHerrichten()
    // Der Abgleich hat die Zuordnung gerade festgelegt: alle übrigen
    // Halter im Kalender (doppelte/Waisen) werden abgebaut. Erst bauen, dann
    // weg — sonst stünde ein Knopf ohne Rahmen im Baum.
    const behalten = new Set(zuordnen(calendarEl.value, knopfSicherstellen, entfernenErlaubt, vergessen))
    for (const el of Array.from(calendarEl.value.querySelectorAll('.kronos-liste-aktionen-halter'))) {
      if (behalten.has(el)) continue
      rahmenAbbauen(el)
    }
    for (const [kennung, el] of Array.from(KNOEPFE)) {
      if (behalten.has(el)) continue
      rahmenAbbauen(el)
      KNOEPFE.delete(kennung)
    }
  })
}

/**
 * UX3i4 — Das „⋯“ auf DIESELBE Zeile wie sein Chip bringen (nur Liste).
 *
 * Der Halter ist ein Geschwister der Bibliothekszeile im `.ec-day`-Container;
 * zwei Blöcke untereinander ergaben je Termin eine zusätzliche 40-px-Zeile
 * (Befund 2). Hier wird er auf `inline-flex` gestellt und die Zeile selbst
 * auf Inhaltsbreite begrenzt — beide stehen dann nebeneinander. Die
 * CSS-Regeln dazu hängen an `data-aktionen-zeile` (scoped CSS kann das DOM der
 * Bibliothek nicht anders erreichen).
 *
 * Idempotent und ohne Maße: die Kennzeichnung wird NUR gesetzt, wenn sie
 * fehlt (kein Schreibzugriff bei jedem Abgleich), und wieder entfernt, sobald
 * die Ansicht keine Liste mehr ist.
 */
function zeilenHerrichten() {
  if (!calendarEl.value) return
  const liste = istListenAnsicht()
  for (const zeile of Array.from(calendarEl.value.querySelectorAll('article.ec-event[data-aktionen-zeile]'))) {
    if (!liste || !zeile.closest('.ec-list')) zeile.removeAttribute('data-aktionen-zeile')
  }
  if (!liste) return
  for (const zeile of Array.from(calendarEl.value.querySelectorAll('.ec-list article.ec-event'))) {
    if (!zeile.hasAttribute('data-aktionen-zeile')) zeile.setAttribute('data-aktionen-zeile', '')
  }
}

/** Meldung des Abgleichs: dieser Halter wird nicht behalten — Rahmen weg. */
function vergessen(el) {
  rahmenAbbauen(el)
  for (const [kennung, bekannt] of Array.from(KNOEPFE)) {
    if (bekannt === el) KNOEPFE.delete(kennung)
  }
}

/** Baut ALLE „⋯" samt Rahmen ab (Ansichtswechsel, Verlassen der Seite). */
function alleKnoepfeAbbauen() {
  const gesehen = new Set()
  for (const el of Array.from(calendarEl.value?.querySelectorAll?.('.kronos-liste-aktionen-halter') || [])) {
    gesehen.add(el)
    rahmenAbbauen(el)
  }
  for (const [kennung, el] of Array.from(KNOEPFE)) {
    if (!gesehen.has(el)) rahmenAbbauen(el)
    KNOEPFE.delete(kennung)
  }
  menueOffen.value = false
}

/**
 * Darf der Abgleich DIESEN Knoten entfernen? Nur Knöpfe, die diese Ansicht
 * gebaut hat — ein fremder Kalender ausserhalb dieser Wurzel bleibt unberührt
 * (Karten über React/Vue mit mehreren Kalendern).
 */
function entfernenErlaubt(el) {
  if (!el) return false
  for (const knoten of KNOEPFE.values()) if (knoten === el) return true
  return false
}

/** Baut den Vue-Rahmen eines „⋯"-Halters ab. */
function rahmenAbbauen(el) {
  const rahmen = rahmenVon(el)
  if (rahmen) {
    try { rahmen.unmount() } catch { /* schon abgebaut */ }
    const inhalt = el?.querySelector?.('.kronos-liste-aktionen-halter-inhalt')
    if (inhalt) inhalt.__kronosRahmen = null
  }
  // Der Halter selbst wird IMMER aus dem Baum genommen (die Bibliothek hat ihn
  // nach einem Neubau schon herausgenommen — dann ist das folgenlos).
  if (el?.remove) el.remove()
}

/**
 * WARUM HIER GESTOPPT WIRD (Befund der Browser-Abnahme 07.11.):
 * Der Halter steht als GESCHWISTER der Terminzeile im `.ec-day`-Container.
 * Dieser Container ist in der Liste das Datumsfeld der Bibliothek — ein Klick
 * darin zählt als Klick auf den Tag bzw. als Auswahl (Ziehen), und die
 * Bibliothek meldet dafür `dateClick`/`select`. Folge: „Neuer Termin" ging auf,
 * sobald man das „⋯" (oder die Halter-Fläche) anklickte.
 * Ein Bedienelement IN der Zeile hätte dasselbe Problem gehabt — deshalb
 * beendet sich hier jeder Zeiger-Klick am Halter: er gehört dem Menü, nicht
 * dem Tag. (Die Zeile selbst bleibt unberührt; ihr Klick ist ein eigenes
 * Element mit eigenem `article`-Verhalten.)
 */
function zeigerAmHalterBleibt(halter) {
  for (const art of ['pointerdown', 'pointerup', 'mousedown', 'mouseup', 'click', 'dblclick']) {
    halter.addEventListener(art, (ereignis) => {
      ereignis.stopPropagation()
      // Tastaturbedienung des Auslösers bleibt unberührt (kein preventDefault).
    })
  }
}

/** Baut den „⋯" samt Menü und merkt ihn sich zur Kennung. */
function knopfAnlegen(kennung, zeile) {
  const halter = document.createElement('span')
  halter.className = 'kronos-liste-aktionen-halter'
  halter.setAttribute('data-termin', kennung)
  const unterbau = document.createElement('span')
  unterbau.className = 'kronos-liste-aktionen-halter-inhalt'
  halter.appendChild(unterbau)
  const rahmen = knopfRahmenFuer(kennung, unterbau)
  unterbau.__kronosRahmen = rahmen
  zeigerAmHalterBleibt(halter)
  KNOEPFE.set(kennung, halter)
  return halter
}

/** Der Termin (Bibliotheks-Objekt) zu einem „⋯"-Knopf. */
function terminZumKnopf(kennung, el) {
  let zeile = el?.previousElementSibling?.matches?.('article.ec-event')
    ? el.previousElementSibling
    : null
  // Der Knopf hängt evtl. schon nicht mehr an seiner Zeile (Neuordnung in
  // Arbeit): dann die Zeile über ihre Kennung suchen.
  if (!zeile && calendarEl.value) {
    zeile = calendarEl.value.querySelector(`article.ec-event[data-event-id="${kennung}"]`)
  }
  const daten = erstelleTerminDaten(zeile)
  if (daten) {
    daten.id = kennung
    return daten
  }
  return { id: kennung, title: '', extendedProps: {} }
}

/**
 * Vue-App für EINEN „⋯"-Knopf samt seinem Menü.
 *
 * Der eigene Rahmen ist nötig, weil der Knopf kein Kind einer Seite, sondern
 * ein Anhängsel der Bibliothek ist. Sein `render` liefert den Knopf als
 * BAUTEIL-Knoten (nicht als gezeichnetes Element): `render: () => h(...)`.
 * Damit gehören `eintraege`, `label` und die Zuhörer zur Komponente
 * DkAktionen — so kommen `aktion` (Menüeintrag) und `offenGeaendert` an.
 *
 * REVIEW UX2e5/3: Im ANSEHEN-Modus bietet das Menü nur „Ansehen" an (das ist
 * dort die einzige erlaubte Handlung — wie beim Klick auf die Zeile,
 * `onEventClick` in Kalender.vue). Die Entscheidung fällt beim Öffnen des
 * Rahmens: `viewMode` steht beim Bauen fest (Kalender wird beim Wechsel des
 * Modus neu geholt).
 */
function knopfRahmenFuer(kennung, el) {
  const nurAnsehen = props.viewMode === 'view'
  const rahmen = createApp({
    render: () => h(DkAktionen, {
      label: 'Aktionen für diesen Termin',
      menueLabel: 'Aktionen für diesen Termin',
      kennung: `termin-${kennung}`,
      // Gemeldet wird von der EIGENEN Uhr-Komponente, nicht vom Unterbau:
      // `emit` von DkAktionen erreicht in einer eigenen App keinen Zuhörer
      // — der Eintrag kommt dort mit `aktion` an, es gibt aber keinen
      // Empfänger (im Browser und in jsdom gemessen).
      eintraege: MENUE_EINTRAEGE
        .filter((eintrag) => !nurAnsehen || eintrag.key === 'ansehen')
        .map((eintrag) => ({
          ...eintrag,
          aktion: () => emit('terminAktion', {
            key: eintrag.key,
            terminId: kennung,
            // Der Termin wird JETZT gelesen, nicht beim Bauen: nach einem
            // Neubau der Bibliothek ist der Inhalt (mit seinen Daten) ein
            // anderer Knoten.
            termin: terminZumKnopf(kennung, el),
          }),
        })),
      onOffenGeaendert: (offen) => { menueOffen.value = offen },
    }),
  })
  rahmen.mount(el)
  return rahmen
}

/** Baut (falls nötig) den „⋯" an einer Zeile und liefert ihn. */
function knopfSicherstellen(zeile, kennung) {
  const bekannt = KNOEPFE.get(kennung)
  if (bekannt && bekannt.isConnected) return bekannt
  // Ein Halter zu dieser Kennung, der nicht mehr am Dokument hängt, ist
  // Müll: erst seinen Rahmen abbauen, dann einen frischen bauen. Sonst
  // sammelt jedes Neuladen einen Vue-Rahmen samt Menü-Zuhörern an.
  if (bekannt) {
    rahmenAbbauen(bekannt)
    KNOEPFE.delete(kennung)
  }
  return knopfAnlegen(kennung, zeile)
}

const _resourcesLoaded = ref(false)
const _highlightEventId = ref(null)
const sessionAutoConvertSeries = ref(false)
let _suppressClick = false  // true nach Swipe/Drag -> unterdrueckt eventClick/dateClick (Tap vs Swipe)
let _dayPushed = false   // History-Eintrag fuer Tagesansicht aktiv
let _popHandling = false
function _onPopState() {
  if (!_dayPushed) return
  _popHandling = true
  _dayPushed = false
  if (calendar.value && calendar.value.getOption('view') === 'timeGridDay') {
    calendar.value.setOption('view', 'dayGridMonth')   // Edge-/Browser-Back -> Monatsansicht
  }
  _popHandling = false
}

const eventsApi = useEventsApi()
const _imp = useImpersonation()

/**
 * A4: Die Rest-Zeile „+n weitere“ im Monatsraster.
 *
 * Die Bibliothek legt dafür einen `<a role="button" tabindex="0">` in den
 * Tag-Fuß (`.ec-day-foot`) — ohne Beschriftung, denn die Zahl kennt sie nur
 * im Tages-Popup (`moreLinkContent` mit `num`). Hier wird die Zeile deshalb
 * nach dem Einbau einer Kachel:
 *
 *   * mit „+n weitere“ beschriftet (Zahl aus den Kacheln des Tages),
 *   * mit `aria-label` versehen (der Tag gehört dazu),
 *   * an den Tageswechsel gehängt (`mehrOeffnen`) — die Bibliothek würde das
 *     Popup öffnen, A4 will die Tagesansicht.
 *
 * Nacharbeit 07.11. Punkt 3: Die Option `moreLinkClick` gibt es in
 * @event-calendar 5.4 NICHT — der Hook war wirkungslos. Der Klick-Zuhörer
 * sitzt deshalb hier: `stopPropagation` nimmt den Klick VOR dem Zuhörer der
 * Bibliothek weg (er hängt am Container, hier wird am Link selbst gefangen),
 * damit kein leeres Popup aufgeht; Tastatur (Enter/Leertaste) läuft über den
 * `keydown`-Zweig, weil `<a role="button">` von sich aus nicht auslöst.
 */
function mehrZeilenHerrichten(info) {
  const el = info?.el
  if (!el) return
  // Die Rest-Zeile kann am Tag-Fuß des Termins hängen — oder (Tage ohne
  // Kacheln, z. B. am Handy) an einem Tag, den dieser Hook nie sieht. Deshalb
  // wird hier über den UMSCHLIESSENDEN Tag gesucht und zusätzlich nach jedem
  // Aufbau `mehrZeilenNachtragen` über den ganzen Kalender gefahren.
  const fuss = el.closest?.('.ec-day-foot') || el.closest?.('.ec-day')?.querySelector?.('.ec-day-foot')
  const link = fuss?.querySelector?.('a[role="button"]')
  if (!link || link.dataset.dkMehr === '1') return
  const tag = el.closest('.ec-day')
  // Die ZAHL steht in der Zeile selbst („+2 weitere“ aus `moreLinkContent`) —
  // sie ist die Wahrheit der Bibliothek. Zählen der sichtbaren Kacheln ergab
  // „1“, weil im Monatsraster nur die GEZEIGTEN Termine als `article` im DOM
  // stehen (die versteckten sind gar nicht gebaut).
  const ausText = Number((/\+(\d+)/.exec(link.textContent || '') || [])[1])
  const zahl = Number.isFinite(ausText) && ausText > 0
    ? ausText
    : Math.max(1, tag ? tag.querySelectorAll('article.ec-event').length : 0)
  link.dataset.dkMehr = '1'
  if (!link.textContent?.trim()) link.textContent = `+${zahl} weitere`
  link.classList.add('ec-mehr-weitere')
  // Der volle Titel für Vorlesehilfen: welcher Tag, wie viele Termine.
  const zeit = fuss.querySelector('time')?.getAttribute('datetime')
    || tag?.querySelector('.ec-day-head time')?.getAttribute('datetime') || ''
  const wann = zeit ? ` am ${new Date(`${zeit}T12:00:00`).toLocaleDateString('de-DE', { weekday: 'long', day: 'numeric', month: 'long' })}` : ''
  link.setAttribute('aria-label', `${zahl} weitere ${zahl === 1 ? 'Termin' : 'Termine'}${wann}`)
  // Der gezeigte Tag steht am Tag-Container (`data-date`) oder an der Uhrzeit.
  const datum = tag?.getAttribute('data-date') || zeit
  if (link.__dkOeffnen) return
  const oeffnen = (e) => {
    e.preventDefault()
    e.stopPropagation()
    mehrOeffnen(datum)
  }
  link.__dkOeffnen = oeffnen
  link.addEventListener('click', oeffnen)
  link.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' || e.key === ' ') oeffnen(e)
  })
}

/**
 * Nacharbeit 07.11. Punkt 3 (Nachtrag): Die Rest-Zeile entsteht NICHT über
 * `eventDidMount` — die Bibliothek zeichnet sie selbst (kein Ereignis-Hook).
 * Deshalb wird sie nach jedem Aufbau des Rasters einmal über den ganzen
 * Kalender hergerichtet (idempotent über `data-dk-mehr`).
 */
function mehrZeilenNachtragen() {
  const kal = calendarEl.value
  if (!kal) return
  for (const link of kal.querySelectorAll('.ec-day-foot a[role="button"]')) {
    if (link.dataset.dkMehr === '1') continue
    const tag = link.closest('.ec-day')
    mehrZeilenHerrichten({ el: tag || link })
  }
}

/**
 * Die Bibliothek zeichnet Termine und Rest-Zeilen in mehreren Runden — ein
 * Lauf im Microtask war ZU FRÜH: gemessen im Wegwerf-Stack fand er 0 Kandidaten,
 * obwohl das Raster Sekundenbruchteile später vier „+n weitere“-Zeilen trug.
 * Deshalb ein Lauf im NÄCHSTEN Bild (rAF) plus ein zweiter kurzer Nachlauf
 * (die Bibliothek zeichnet die Rest-Zeilen nach den Kacheln). Beides
 * idempotent über `data-dk-mehr`, also mehrfach aufrufbar.
 */
let _mehrGeplant = false
// A10-N2: „bereit" wird EINMAL gemeldet (erster Aufbau).
let _bereitGemeldet = false
function _mehrZeilenPlanen() {
  if (_mehrGeplant) return
  _mehrGeplant = true
  const lauf = () => {
    _mehrGeplant = false
    mehrZeilenNachtragen()
  }
  if (typeof requestAnimationFrame === 'function') {
    requestAnimationFrame(() => {
      lauf()
      // Nachlauf: die Rest-Zeilen der zweiten Zeichenrunde.
      setTimeout(() => mehrZeilenNachtragen(), 120)
    })
  } else {
    Promise.resolve().then(lauf)
  }
}

/**
 * A10-N2 (Review 09.11., Punkt 1) — Punkte je Tag im MONATSRASTER am Handy.
 *
 * Am Handy blendet die Seite die Termin-Chips im Raster aus (siehe
 * `pages/Kalender.vue`: `.ec-event` unter 720 px). Ein Tag mit drei Terminen
 * sähe dann aus wie ein leerer, und der Tipp-Ziel („Tipp auf Tag →
 * Tagesliste“) wäre nicht erkennbar. Die Bibliothek zeichnet keine Punkte —
 * sie kennt nur ihre eigenen (ausgeblendeten) Kacheln.
 *
 * Deshalb markiert dieser Lauf jeden Tag, der einen sichtbaren Termin hat:
 *   * `data-dk-termin="n"`   Kennzahl für das Styling und für Prüfungen,
 *   * `aria-label` am Tageskopf ergänzt um „, n Termine“ (Farbe ist nie
 *     alleiniger Träger — die Vorlesehilfe sagt die Zahl).
 * Der Punkt selbst ist reine Gestaltung (CSS in `pages/Kalender.vue`).
 *
 * Gezählt wird über die Termin-Artikel der Sicht (`article.ec-event`, in
 * @event-calendar 5.18 die echte Struktur — geprüft im Browser). ACHTUNG: im
 * MONATSRASTER liegen die Artikel NICHT in `.ec-day`, sondern in einer
 * eigenen, absolut gesetzten Ebene daneben:
 *
 *   .ec-month-view > .ec-main > .ec-body > .ec-day (Kopf + Fuß)
 *                                        > .ec-events > article.ec-event
 *
 * Die Artikel tragen `grid-area: <Zeile> / <Spalte> / …` (gesetzt von der
 * Bibliothek) und sind am Handy per CSS ausgeblendet (`display: none` in
 * `pages/Kalender.vue`) — ihre Rechtecke sind deshalb Null und NICHT
 * messbar. Gelesen wird die Zuordnung deshalb aus dem Stil. Im Browser
 * gemessen (390 px, November 2026): `termin-2026-11-06-00` hat `2 / 5` —
 * der 6.11.2026 ist ein FREITAG, also Spalte 5, Zeile 2. Die Rasterzahlen
 * sind also 1-basiert und OHNE Randleisten-Spalte; `tage[0]` (2026-10-26,
 * Montag) ist Zeile 0 / Spalte 0. Einfacher und ohne diese Annahme:
 * die Tageszellen in Dokumentreihenfolge (7 je Zeile) und die Terminzelle
 * als `(zeile-1) * 7 + (spalte-1)`.
 *
 * Der Lauf ist idempotent über `data-dk-termin` und mehrfach aufrufbar.
 */
function tagesPunkteNachtragen() {
  const kal = calendarEl.value
  if (!kal) return
  // Nur das Monatsraster; Zeitraster und Liste haben eigene Wege.
  const raster = kal.querySelector('.ec-month-view')
  if (!raster) return
  const tage = [...raster.querySelectorAll('.ec-day')]
  if (!tage.length) return
  // Zeile/Spalte eines Termins aus dem Inline-Stil („grid-area: 2 / 5 / …“).
  const gitter = (el) => {
    const stil = el.getAttribute('style') || ''
    const treffer = /grid-area:\s*(\d+)\s*\/\s*(\d+)/.exec(stil)
    if (!treffer) return null
    return { zeile: Number(treffer[1]) - 1, spalte: Number(treffer[2]) - 1 }
  }
  const termine = [...raster.querySelectorAll('article.ec-event')]
    .map((el) => gitter(el))
    .filter(Boolean)
  const jeZeile = 7
  const zaehler = new Map(tage.map((tag) => [tag, 0]))
  for (const { zeile, spalte } of termine) {
    if (zeile < 0 || spalte < 0 || spalte >= jeZeile) continue
    const tag = tage[zeile * jeZeile + spalte]
    if (tag) zaehler.set(tag, (zaehler.get(tag) || 0) + 1)
  }
  for (const tag of tage) {
    const anzahl = zaehler.get(tag) || 0
    const kopf = tag.querySelector('.ec-day-head')
    if (!kopf) continue
    const alt = kopf.dataset.dkTerminAlt || kopf.getAttribute('aria-label') || kopf.textContent.trim()
    if (anzahl > 0) {
      tag.dataset.dkTermin = String(anzahl)
      kopf.dataset.dkTerminAlt = alt
      kopf.setAttribute('aria-label', `${alt}, ${anzahl} ${anzahl === 1 ? 'Termin' : 'Termine'}`)
    } else {
      delete tag.dataset.dkTermin
      if (kopf.dataset.dkTerminAlt) kopf.setAttribute('aria-label', kopf.dataset.dkTerminAlt)
    }
  }
}

/**
 * A10-N2 — Punkte je Tag in der WOCHENANSICHT am Handy.
 *
 * Die Wochenansicht ist ein Zeitraster mit sieben schmalen Tagesspalten; die
 * Terminblöcke sind dort per CSS ausgeblendet (siehe `pages/Kalender.vue`),
 * weil in ~50 px nur „G… 1…“ stand. Ein Tag mit drei Terminen sähe dann aus
 * wie ein leerer Tag. Deshalb bekommt der TAGESKOPF („Mo 9.11.“) einen Punkt
 * mit der Zahl — dieselbe Sprache wie im Monat, nur an der Kopfzeile.
 *
 * Gezählt wird über die KOPF-`<time datetime>`: jede Tagesspalte trägt ihren
 * Tag selbst; die Termine werden über ihren `data-event-id`-Tag zugeordnet
 * (die Kennung beginnt bei den Diakronos-Terminen mit dem Datum, z. B.
 * „termin-2026-11-08-04“ / „gottesdienst-2026-11-08“). Fehlt das Datum in
 * der Kennung, bleibt der Tag unmarkiert — es wird NICHTS geraten.
 */
function wochenPunkteNachtragen() {
  const kal = calendarEl.value
  if (!kal) return
  const raster = kal.querySelector('.ec-week-view')
  if (!raster) return
  // Im Browser gemessen (Zeitraster 5.18): je Tagesspalte steht
  //   <header class="ec-header"><div class="ec-grid">
  //     <div class="ec-col-head ec-mon|ec-tue|…"><time datetime="2026-11-09">…
  // `ec-day-head` gibt es dort NICHT — das ist der Monatsname.
  const spalten = [...raster.querySelectorAll('.ec-col-head')]
    .map((kopf) => ({ kopf, tag: (kopf.querySelector('time[datetime]')?.getAttribute('datetime') || '').slice(0, 10) }))
    .filter((s) => s.tag)
  if (!spalten.length) return
  const jeTag = new Map(spalten.map((s) => [s.tag, 0]))
  for (const el of raster.querySelectorAll('.ec-event')) {
    const kennung = el.getAttribute('data-event-id') || el.dataset.eventId || ''
    const treffer = /(\d{4}-\d{2}-\d{2})/.exec(kennung)
    if (!treffer) continue
    if (jeTag.has(treffer[1])) jeTag.set(treffer[1], jeTag.get(treffer[1]) + 1)
  }
  for (const { kopf, tag } of spalten) {
    const anzahl = jeTag.get(tag) || 0
    const alt = kopf.dataset.dkTerminAlt || kopf.getAttribute('aria-label') || kopf.textContent.trim()
    if (anzahl > 0) {
      kopf.dataset.dkTermin = String(anzahl)
      kopf.dataset.dkTerminAlt = alt
      kopf.setAttribute('aria-label', `${alt}, ${anzahl} ${anzahl === 1 ? 'Termin' : 'Termine'}`)
    } else {
      delete kopf.dataset.dkTermin
      if (kopf.dataset.dkTerminAlt) kopf.setAttribute('aria-label', kopf.dataset.dkTerminAlt)
    }
  }
}

/** Nach jedem Aufbau einplanen (rAF + kurzer Nachlauf, wie die „+n“-Zeilen). */
let _punkteGeplant = false
function _tagesPunktePlanen() {
  if (_punkteGeplant) return
  _punkteGeplant = true
  const lauf = () => {
    _punkteGeplant = false
    tagesPunkteNachtragen()
    wochenPunkteNachtragen()
  }
  if (typeof requestAnimationFrame === 'function') {
    requestAnimationFrame(() => {
      lauf()
      setTimeout(() => { tagesPunkteNachtragen(); wochenPunkteNachtragen() }, 120)
    })
  } else {
    Promise.resolve().then(lauf)
  }
}

/** „+n weitere“: in die Tagesansicht des betroffenen Tages wechseln. */
function mehrOeffnen(datum) {
  // `datum` ist ein ISO-TAG aus dem Raster („2026-11-08“) oder ein Date.
  // Achtung: `new Date('2026-11-08')` ist UTC-Mitternacht — lokale Zeitzone
  // kann den Tag verschieben. Deshalb wird ein ISO-Tag als LOKALER Tag gebaut.
  let d
  if (typeof datum === 'string' && /^\d{4}-\d{2}-\d{2}/.test(datum)) {
    const [j, m, t] = datum.slice(0, 10).split('-').map(Number)
    d = new Date(j, m - 1, t)
  } else {
    d = datum instanceof Date && !Number.isNaN(datum.getTime()) ? datum : new Date()
  }
  calendar.value?.setOption('view', 'timeGridDay')
  // KEIN Tagesversatz: der Tag aus dem Raster ist bereits der Zieltag.
  calendar.value?.setOption('date', d)
}

/**
 * P1-1b: Verschieben/Groessenaenderung an einem FESTGELEGTEN Termin wirkt fuer
 * Nicht-Moderatoren nicht sofort — die Aenderung wartet als offener Vorschlag.
 * Ohne diese Meldung sah es so aus, als sei der Termin "zurueckgesprungen".
 */
function meldeWartendeAenderung(ergebnis) {
  if (ergebnis?.wartet) {
    showToast(ergebnis.meldung || 'Änderung wartet auf Freigabe (Zu prüfen).', 'success')
  }
}

onMounted(() => {
  if (!calendarEl.value) {
    console.error('Calendar Element nicht gefunden')
    return
  }

  try {
    const isEditMode = props.viewMode === 'edit'

    calendar.value = EventCalendar.create(calendarEl.value, {
      view: 'dayGridMonth',
      locale: 'de',
      // UX3i5 (Befund 2, live 08.11.): Der Tageskopf der LISTE besteht aus
      // ZWEI Stücken im SELBEN `h4`:
      //   <time>Freitag</time> <time class="ec-day-side">6. November 2026</time>
      // Im Browser stand „Freitag6. November 2026“ — die Bibliothek setzt
      // keinen Trenner zwischen die beiden Stücke; die Lücke in der Vorlage
      // ist ein Zeilenumbruch, der zu EINEM Leerzeichen zusammengefasst wird.
      // Beide Formate werden deshalb ausdrücklich gesetzt (vorher waren die
      // Vorgaben der Bibliothek in Gebrauch); der Trenner „, “ kommt aus dem
      // CSS (`::after` am Wochentag) — dort bleibt er an EINER Stelle und
      // folgt der Schrift des Kopfes.
      listDayFormat: { weekday: 'long' },
      listDaySideFormat: { day: 'numeric', month: 'long', year: 'numeric' },
      eventTimeFormat: { hour: '2-digit', minute: '2-digit', hour12: false },
      headerToolbar: false,
      // OP-ADMIN-17: Die Kalenderwoche beginnt am Montag (wie der Mini-Kalender
      // und wie in Deutschland ueblich). Vorher fing das Raster am Sonntag an.
      firstDay: 1,
      // UX3i (Entwurf A4): KEINE Kalenderwoche in den Zellen mehr. Sie stand
      // in der Montagszelle und drängte die Termine nach unten; die Woche
      // steht jetzt EINMAL im Kartenkopf („KW 44–49“, siehe `kwBereich` in
      // `chipText.mjs` und `cardTitle` der Seite).
      weekNumbers: false,
      // UX3i: so viele Chips je Tag, wie in A4 stehen. `true` heißt „so viele,
      // wie Platz haben“ (die Zahl hatte die Bibliothek über den Rand laufen
      // lassen); der Rest wird zu „+n weitere“ und öffnet die Tagesansicht.
      dayMaxEvents: true,
      // UXK-R13: englische Texte der Bibliothek übersetzen („all-day“, „+2 more“).
      allDayContent: { text: 'ganztägig' },
      moreLinkContent: (info) => `+${info.num} weitere`,
      // A4: „+n weitere“ führt in die TAGESANSICHT (dort stehen alle Termine
      // des Tages) — dafür hängt `mehrZeilenHerrichten` einen eigenen
      // Klick-Zuhörer an die Rest-Zeile. Die Option `moreLinkClick` gibt es in
      // @event-calendar 5.4 NICHT (geprüft im Bundle 5.4.2: unbekannte
      // Optionen werden still verworfen, der Klick landete auf einem leeren
      // Popup) und ist deshalb entfernt.
      height: '100%',
      resourceAreaWidth: 200,
      editable: isEditMode,
      selectable: isEditMode,

      resources: [],
      resourceLabelContent: (info) => {
        if (info.resource.extendedProps?.isGroupHeader) {
          return { html: '<span class="ec-res-group-label">' + info.resource.title + '</span>' }
        }
        return { html: '<span class="ec-res-normal-label">' + info.resource.title + '</span>' }
      },
      resourceLabelDidMount: (info) => {
        if (info.resource.extendedProps?.isGroupHeader) {
          info.el.style.marginLeft = '6px'
        }
      },
      events: [],
      eventSources: [
        {
          events: function(fetchInfo, successCallback, failureCallback) {
            const startDate = fetchInfo.startStr ? fetchInfo.startStr.split('T')[0] : ''
            const endDate   = fetchInfo.endStr   ? fetchInfo.endStr.split('T')[0]   : ''
            const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || ''
            const activeCalendars = props.selectedCalendars

            fetch(apiUrl('diakronos.kronos.api.calendar_get.get_calendar_events'), {
              method: 'POST',
              headers: {
                'Accept': 'application/json',
                'Content-Type': 'application/json',
                'X-Frappe-CSRF-Token': csrfToken
              },
              body: JSON.stringify({
                start_date: startDate,
                end_date: endDate,
                calendar_filter: JSON.stringify(activeCalendars),
                view_mode: props.viewMode,
                ...(_imp.isActive.value ? { __impersonated_as: _imp.mitglied.value } : {})
              })
            })
            .then(apiAntwortPruefen)
            .then(result => {
              const events = result.message || []
              const processedEvents = events.map(ev => {
                if (ev.start && typeof ev.start === 'string' && ev.start.includes('T')) {
                  ev.allDay = false
                }
                if (ev.end && typeof ev.end === 'string' && ev.end.includes('T')) {
                  ev.allDay = false
                }
                // ICAL-1: Die Bibliothek zählt das Ende ganztägiger Termine
                // AUSSCHLIESSEND (RFC 5545), Diakronos speichert es
                // EINSCHLIESSEND. Ohne diesen Tag fehlte der zweite Tag eines
                // mehrtägigen Ganztags-Termins im Monatsraster.
                const endePlus = endeFuerKalender(ev.end, ev.allDay)
                if (endePlus) ev.end = endePlus
                return ev
              })
              successCallback(processedEvents)
            })
            .catch(err => {
              console.error('Events Fetch Fehler:', err)
              failureCallback(err)
            })
          }
        }
      ],

      dateClick: (info) => {
        if (_suppressClick) return
        emit('dateClick', info)
      },

      eventClick: (info) => {
        if (_suppressClick) return
        const isMobile = istHandyBreite(window.innerWidth)
        const currentView = info.view.type

        // OP-HANDY-8: Am Handy fuehrte ein Tipp auf einen Monatstermin in die
        // Tagesansicht — und die war scheinbar leer, weil der Termin (z. B.
        // 21:00) hunderte Pixel unter dem sichtbaren Bereich lag. Jetzt oeffnet
        // der Tipp direkt das Termindetail (Titel, Zeit, Ort, Beschreibung);
        // wer die Tagesübersicht will, waehlt sie oben im Ansichtsfeld.
        if (isMobile && currentView === 'dayGridMonth') {
          emit('eventClick', info.event)
          info.jsEvent.preventDefault()
          return
        }

        emit('eventClick', info.event)
        info.jsEvent.preventDefault()
      },

      eventDrop: async (info) => {
        const _dropRes = (info.event.getResources?.() || [])[0]
        if (_dropRes?.id?.startsWith('__grp_') || _dropRes?.extendedProps?.isGroupHeader) { info.revert(); return }
        const props_ev = info.event.extendedProps || {}
        let ergebnis
        if (props_ev.series_id) {
          if (!sessionAutoConvertSeries.value) {
            const result = await seriesDialog.value?.showDragConfirmation(info.event)
            if (!result?.confirmed) { info.revert(); return }
            if (result.rememberSession) sessionAutoConvertSeries.value = true
          }
          ergebnis = await eventsApi.updateEvent(info.event, () => refetchEvents(), true)
        } else {
          ergebnis = await eventsApi.updateEvent(info.event, () => refetchEvents(), false)
        }
        meldeWartendeAenderung(ergebnis)
      },

      eventResize: async (info) => {
        const props_ev = info.event.extendedProps || {}
        let ergebnis
        if (props_ev.series_id) {
          if (!sessionAutoConvertSeries.value) {
            const result = await seriesDialog.value?.showDragConfirmation(info.event)
            if (!result?.confirmed) { info.revert(); return }
            if (result.rememberSession) sessionAutoConvertSeries.value = true
          }
          ergebnis = await eventsApi.updateEvent(info.event, () => refetchEvents(), true)
        } else {
          ergebnis = await eventsApi.updateEvent(info.event, () => refetchEvents(), false)
        }
        meldeWartendeAenderung(ergebnis)
      },

      select: (info) => {
        if (info.resource?.id?.startsWith('__grp_') || info.resource?.extendedProps?.isGroupHeader) return
        emit('select', info)
      },

      // A4 („+n weitere“) UND UX2e5 (Termin-Datensatz für das ⋯-Menü) — EIN
      // Schlüssel. Vorher stand `eventDidMount` zweimal im Optionsobjekt (aus
      // dem Merge von UX2e5); beim doppelten Schlüssel gewinnt der letzte,
      // `mehrZeilenHerrichten` lief nie („+n weitere“ ohne Text/Ziel).
      // Nacharbeit 07.11. Punkt 2: erst die Rest-Zeile herrichten, dann die
      // Kennung der Kachel setzen und den Knopf-Abgleich anstoßen.
      eventDidMount: (info) => {
        mehrZeilenHerrichten(info)
        const el = info?.el
        if (!el || el.tagName !== 'ARTICLE') return
        const kennung = String(info?.event?.id ?? '')
        if (kennung) el.setAttribute('data-event-id', kennung)
        abgleichPlanen()
        // A4: Die Rest-Zeile des Tages kann erst jetzt (nach den Kacheln)
        // entstanden sein.
        _mehrZeilenPlanen()
        // A10-N2: Punkte je Tag im Monatsraster (Handy) nachziehen.
        _tagesPunktePlanen()
      },
      eventWillUnmount: () => { abgleichPlanen() },

      datesSet: (info) => {
        // A4: Nach jedem Aufbau des Rasters (Monatswechsel, Ansichtswechsel,
        // neu geholte Termine) die Rest-Zeile „+n weitere“ herrichten.
        _mehrZeilenPlanen()
        // A10-N2: ebenso die Punkte je Tag (Handy-Monat).
        _tagesPunktePlanen()
        // UX3i (A4): Der Kartenkopf braucht den Titel OHNE Beschneidung
        // („November 2026“) — `info.view.title` ist die eine Wahrheit.
        emit('datesSet', { ...info, title: info.view?.title || '' })
        const vt = info.view.type
        // BF1-D: Die tatsaechliche Ansicht melden. Das Kalender-Widget wechselt
        // die Ansicht auch selbst (z.B. Mobil-Klick im Monat -> Tagesansicht);
        // nur so spiegelt das Ansichts-Dropdown die eine Wahrheit.
        emit('viewChange', vt)
        const isResourceView = vt === 'resourceTimelineDay'
          || vt === 'resourceTimelineWeek'
          || vt === 'resourceTimelineMonth'

        emit('resourceViewChange', isResourceView)
        // A10-N2: erste Meldung, dass das Raster steht (Ladezustand der Seite).
        if (!_bereitGemeldet) {
          _bereitGemeldet = true
          emit('bereit')
        }

        if (isResourceView && !_resourcesLoaded.value) {
          _loadResources()
        }

        if (vt === 'timeGridDay' && !_dayPushed) {
          history.pushState({ kronosDay: 1 }, '')   // Back-Geste faengt Tag->Monat ab statt Seite verlassen
          _dayPushed = true
        } else if (vt === 'dayGridMonth' && _dayPushed && !_popHandling) {
          _dayPushed = false
          history.back()                              // In-App-Rueckkehr -> History-Eintrag konsumieren
        }
      },

      eventClassNames: (info) => {
        const isMonthView = calendar.value?.getOption('view') === 'dayGridMonth'
        const isMobile   = istEngeBreite(window.innerWidth)
        const isMultiDay = !info.event.allDay && info.event.end &&
          new Date(info.event.start).toDateString() !== new Date(info.event.end).toDateString()
        const useDot = !info.event.allDay && isMonthView && !isMobile && !isMultiDay
        // UX3i4 (Befund 08.11.): Die Chip-Klasse hängt an der ANSICHT, nicht am
        // Termin. Im ZEITRASTER (Woche/Tag) ist der Termin ein Block über seine
        // DAUER — die Bibliothek setzt Höhe und Lage dort als Inline-Stil; die
        // Chip-Optik (`ec-chip-event`, Pille) darf die Fläche nicht aufheben,
        // sonst schrumpft der Termin auf eine Pille an der Startzeit.
        // UX3i3 hatte die Klasse „überall“ vergeben — das war die Ursache des
        // Live-Befunds. Chip-Optik gilt jetzt in Monat und Liste (Tag = Zeitraster).
        const istZeitraster = istZeitrasterAnsicht()
        const classes = []
        if (!istZeitraster) classes.push('ec-chip-event')
        if (useDot) classes.push('ec-event-dot-style')
        if (_highlightEventId.value && info.event.id === _highlightEventId.value)
          classes.push('kronos-event-highlight')
        return classes
      },

      eventContent: (info) => {
        const event = info.event
        const safe = s => (s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
          .replace(/"/g, '&quot;')
        // UX2e5: Der Termin-Datensatz für das „⋯"-Menü der LISTE. Die
        // Bibliothek liefert keine Rückreferenz zum Datensatz, deshalb reist
        // er als JSON an der Zeile mit (ausgelesen in ./terminAktionenDaten.mjs).
        const daten = {
          id: String(event.id ?? ''),
          title: event.title || '',
          start: event.start ? new Date(event.start).toISOString() : null,
          end: event.end ? new Date(event.end).toISOString() : null,
          allDay: !!event.allDay,
          backgroundColor: event.backgroundColor || '',
          extendedProps: event.extendedProps || {},
        }
        // Einfache Anführungszeichen: der Inhalt ist JSON mit doppelten —
        // mit doppelten umschlossen endete das Merkmal mitten im JSON.
        const datenAttr = " data-termin-daten='" + safe(JSON.stringify(daten)) + "'"

        // UX3i3 (Befunde 1/2/3/4): EINE Chip-Logik für Monat, Woche und Liste.
        // Vorher hatten die drei Ansichten drei verschiedene Termin-Optiken:
        //   Monat  — getönter Chip (A4), Woche — satte Kachel mit schwarzer
        //   Schrift, Liste — voller Farbbalken mit heller Uhrzeit. Jetzt gilt
        //   überall derselbe Chip (getönte Kalenderfarbe + `light-dark()`-
        //   Schrift aus `chipStil`), der Text ist überall „Titel 19:00“.
        // Der VOLLE Titel (mit Datum und Zeit) steht in `title`/`aria-label`;
        // gekürzt wird nur optisch (Textellipse).
        // Auch die enge Lage (Handy, 390 px) baut DIESEN Chip — kein eigener
        // Handy-Sonderweg mehr (Befund 3). Wie breit der Chip dort ist und wie
        // viel Text passt, regelt das Layout der Zelle; die Mobile-Gestaltung
        // des Kalenders ist die eigene Karte A10.
        const tag = event.start
          ? `${event.start.getFullYear()}-${String(event.start.getMonth() + 1).padStart(2, '0')}-${String(event.start.getDate()).padStart(2, '0')}`
          : ''
        const chipDaten = { title: event.title, start: event.start, end: event.end, allDay: event.allDay }
        const titel = chipTitel(chipDaten)
        const dunkel = typeof document !== 'undefined'
          && document.documentElement.getAttribute('data-theme') === 'dark'
        // Fläche UND Schrift (beide Variablen), gerechnet gegen die echte
        // Fläche — siehe `chipFarben`.
        const stil = chipStil(sichereFarbe(event.backgroundColor), { theme: dunkel ? 'dunkel' : 'hell' })

        // UX3i4 (Befund 1, 08.11.): Im ZEITRASTER (Woche/Tag) ist der Termin
        // ein BLOCK über seine Dauer. Seit UX3i3 lag dort derselbe Chip wie im
        // Monat — der Termin schrumpfte auf eine ~16 px hohe Pille an der
        // Startzeit, weil die Chip-Regel den Innenabstand auf 0 nahm und der
        // Inhalt nur eine Zeile war. Hier steht deshalb ein eigener Block:
        // Titel ZEILE 1, Uhrzeit ZEILE 2, oben ausgerichtet; Fläche und Schrift
        // kommen aus derselben Rechnung wie der Chip (`chipStil`).
        // Die Höhe gibt die Bibliothek als Inline-Stil vor (`block-size` aus
        // der Dauer) — der Block FÜLLT sie (`height: 100%`), er setzt sie nicht.
        if (istZeitrasterAnsicht()) {
          const zeilen = zeitBlockText(chipDaten, { tag })
          return { html:
            '<div class="ec-block" role="button" tabindex="0" title="' + safe(titel) +
            '" aria-label="' + safe(titel) + '"' + datenAttr + ' style="' + stil + '">' +
            '<span class="ec-block-titel">' + safe(zeilen.titel) + '</span>' +
            (zeilen.zeit ? '<span class="ec-block-zeit">' + safe(zeilen.zeit) + '</span>' : '') +
            '</div>'
          }
        }

        const text = chipText(chipDaten, { tag })
        // Der Datensatz reist am Chip mit (UX2e5: Klick und „⋯“-Menü finden
        // den Termin in jeder Ansicht).
        return { html:
          '<div class="ec-chip" role="button" tabindex="0" title="' + safe(titel) +
          '" aria-label="' + safe(titel) + '"' + datenAttr + ' style="' + stil + '">' +
          '<span class="ec-chip-text">' + safe(text) + '</span>' +
          '</div>'
        }
      },

      // UX2e5: Ein-/Ausbau und jeder Neubau der Bibliothek stoßen den
      // Knopf-Abgleich an (idempotent, ein Lauf je Umlauf). KEIN gemessenes
      // Nachführen je Knopf (kein ResizeObserver) — die Zuordnung hängt an
      // der Kennung, nicht an Maßen.
      // Die Kennung setzt KEIN Teil der Bibliothek ans `article` (sie führt
      // sie nur intern); sie kommt oben im gemeinsamen `eventDidMount` an die
      // Zeile, damit der Abgleich Knopf und Termin ohne Raten zusammenbringt.
    })

    // Mobile: Swipe-Navigation
    let _swipeStartX = 0
    let _swipeStartY = 0
    calendarEl.value.addEventListener('touchstart', (e) => {
      _swipeStartX = e.touches[0].clientX
      _swipeStartY = e.touches[0].clientY
      _suppressClick = false
    }, { passive: true })
    calendarEl.value.addEventListener('touchmove', (e) => {
      if (Math.abs(e.touches[0].clientX - _swipeStartX) > 10 || Math.abs(e.touches[0].clientY - _swipeStartY) > 10) _suppressClick = true
    }, { passive: true })
    // Capture-Phase: blockt den lib-eigenen click NACH Drag/Swipe, bevor eventClick feuert
    calendarEl.value.addEventListener('click', (e) => {
      if (_suppressClick) { e.stopImmediatePropagation(); e.preventDefault(); _suppressClick = false }
    }, true)
    calendarEl.value.addEventListener('touchend', (e) => {
      const delta = e.changedTouches[0].clientX - _swipeStartX
      const viewType = calendar.value.getOption('view')
      if (viewType === 'timeGridDay') {
        if (delta > 80) calendar.value.setOption('view', 'dayGridMonth')
      } else if (viewType === 'dayGridMonth') {
        if (delta < -80) calendar.value.next()
        else if (delta > 80) calendar.value.prev()
      }
    }, { passive: true })

    window.addEventListener('popstate', _onPopState)

  } catch (error) {
    console.error('Fehler beim Initialisieren:', error)
    console.error(' Stack:', error.stack)
  }
})

onBeforeUnmount(() => {
  window.removeEventListener('popstate', _onPopState)
  // UX2e5: Alle „⋯"- Rahmen der Liste abbauen (kein hängender Knoten, kein
  // offenes Menü nach dem Verlassen der Seite).
  alleKnoepfeAbbauen()
  menueOffen.value = false
  if (calendar.value && typeof calendar.value.destroy === 'function') {
    calendar.value.destroy()
  }
})

watch(() => props.selectedCalendars, () => {
  refetchEvents()
}, { deep: true })

watch(() => props.viewMode, (newVal) => {
  const isEditMode = newVal === 'edit'
  if (calendar.value) {
    calendar.value.setOption('editable', isEditMode)
    calendar.value.setOption('selectable', isEditMode)
  }
  refetchEvents()
})

async function _loadResources() {
  _resourcesLoaded.value = true
  const csrf = document.querySelector('meta[name="csrf-token"]')?.content || ''
  try {
    const res = await fetch(apiUrl('diakronos.kronos.api.ressource_api.get_ressources'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Frappe-CSRF-Token': csrf },
      body: JSON.stringify({})
    })
    const data = await apiAntwortPruefen(res)
    const msg = data.message
    const resList = Array.isArray(msg) ? msg : (msg?.resources || [])
    const typeOrder = Array.isArray(msg) ? [] : (msg?.types || [])
    const rawList = resList.map(r => ({
      id: r.id,
      title: r.title,
      extendedProps: { typ: r.typ || 'Sonstiges' }
    }))

    const grouped = {}
    for (const r of rawList) {
      const t = r.extendedProps.typ
      if (!grouped[t]) grouped[t] = []
      grouped[t].push(r)
    }

    const allTypes = [
      ...typeOrder,
      ...Object.keys(grouped).filter(t => !typeOrder.includes(t) && t !== 'Sonstiges')
    ]
    if (grouped['Sonstiges']) allTypes.push('Sonstiges')

    const resources = []
    for (const typ of allTypes) {
      if (grouped[typ]?.length) {
        resources.push({
          id: '__grp_' + typ,
          title: typ,
          extendedProps: { isGroupHeader: true },
          children: grouped[typ]
        })
      }
    }
    resources.push({ id: '__unassigned__', title: 'Nicht zugeordnet' })

    if (calendar.value) {
      calendar.value.setOption('resources', resources)
      calendar.value.refetchResources()
    }

  } catch (e) {
    _resourcesLoaded.value = false
    console.warn('Ressourcen konnten nicht geladen werden:', e)
  }
}

function changeView(viewName, date) {
  if (!calendar.value) return
  calendar.value.setOption('view', viewName)
  if (date) calendar.value.setOption('date', date instanceof Date ? date : new Date(date))
}

function gotoDate(date) {
  if (!calendar.value) return
  calendar.value.setOption('date', date instanceof Date ? date : new Date(date))
}

function today() {
  if (!calendar.value) return
  calendar.value.setOption('date', new Date())
}

function next() {
  if (calendar.value) calendar.value.next()
}

function prev() {
  if (calendar.value) calendar.value.prev()
}

function refetchEvents() {
  if (calendar.value) calendar.value.refetchEvents()
  // UX2e5: Nach jedem Neuladen neu zuordnen — auch wenn die Bibliothek die
  // Zeilen in derselben Lage weiterbenutzt (Rückgängig, Serien-Fragen).
  abgleichPlanen()
}

defineExpose({
  changeView, gotoDate, today, next, prev, refetchEvents,
  // REVIEW UX2e5/3: die „⋯"-Menüs neu bauen (nach einem Moduswechsel kennt
  // das alte Menü den neuen Modus nicht).
  neuZuordnen,
  // UX2e5 (Review 07.11.): Anzahl der „⋯"-Rahmen im Kalender. Der Test hält
  // damit fest, dass nach vielen Neuladen/Ansichtswechseln KEIN Rahmen übrig
  // bleibt (jedem sichtbaren Termin genau einer).
  anzahlRahmen,
})

/** Zahl der lebenden „⋯"-Rahmen — nur für Belege (Test), ohne Nebenwirkung. */
function anzahlRahmen() {
  return Array.from(calendarEl.value?.querySelectorAll?.('.kronos-liste-aktionen-halter-inhalt') || [])
    .filter((inhalt) => !!inhalt.__kronosRahmen).length
}

/**
 * REVIEW UX2e5/3: Alle „⋯" samt Menü verwerfen und frisch zuordnen.
 *
 * Das Menü eines Knopfes entsteht beim Zuordnen und kennt den ANSEHEN- bzw.
 * BEARBEITEN-Modus von da. Nach einem Moduswechsel (oder wenn ein Test den
 * Modus umstellt) wird deshalb neu gebaut — kein zweiter Menüpfad, keine
 * Prüfung im Klickpfad.
 */
function neuZuordnen() {
  for (const [kennung, el] of Array.from(KNOEPFE)) {
    rahmenAbbauen(el)
    KNOEPFE.delete(kennung)
  }
  abgleichGeplant = false
  abgleichPlanen()
}

</script>

<template>
  <div ref=calendarEl style=height:100%></div>
  <KronosSeriesDialog ref=seriesDialog />
</template>

<style scoped>
/* UX2e5 — „⋯" je Termin in der Terminliste.
   Die Zeilen der Bibliothek sind Geschwister im Tages-Container (keine
   gemeinsame Hülle); der Halter ist das nächste Geschwister SEINER Zeile,
   also in Zeilenhöhe unter seinem Termin.

   TREFFERFLÄCHE (Befund aus der Browser-Abnahme 07.11.): Der Halter nimmt die
   ganze Zeilenbreite ein — der AUSLÖSER darin aber nur eine quadratische
   Fläche von --control-h (44 px bei pointer: coarse) am rechten Rand, oben
   bündig zur Zeile. Vorher füllte der Auslöser die ganze Breite und lag über
   dem Termin: ein Klick auf den Termin traf das „⋯" statt der Zeile (die
   Bibliothek öffnete stattdessen „Neuer Termin"). Die Leerfläche LINKS bleibt
   klickdurchlässig (Halter und Inhalt ohne Hintergrund). */
:deep(.kronos-liste-aktionen-halter) {
  display: block;
  margin: 0 0 var(--sp-1) 0;
  padding: 0;
}
:deep(.kronos-liste-aktionen-halter-inhalt) {
  display: block;
}
/* UX3i4 (Befund 2, 08.11.): Das „⋯“ stand in der LISTE als eigener Knoten
   UNTER dem Chip (der Halter ist ein Geschwister der Bibliothekszeile) — je
   Termin eine zusätzliche 40-px-Zeile. Jetzt liegt es auf DERSELBEN Zeile
   rechts neben dem Chip: die Zeile (article) und ihr Halter teilen sich einen
   Flex-Container (`.ec-day`). Die Kennzeichnung `data-aktionen-zeile` setzt
   `zeilenHerrichten()` (Skript) — nur so bleibt die Regel auf die Listenzeilen
   beschränkt; das Monatsraster behält seine Punkte-Zeilen. */
:deep(.ec-list .ec-day > article.ec-event[data-aktionen-zeile]) {
  display: inline-flex;
  inline-size: fit-content;
  max-inline-size: calc(100% - var(--control-h));
}
/* Nur in der Liste: das Monatsraster behält seine Punkte-Zeilen. */
:deep(.ec-list .kronos-liste-aktionen-halter) {
  display: inline-flex;
  vertical-align: top;
  margin: 0;
  padding: 0;
}
:deep(.ec-list .kronos-liste-aktionen-halter .dk-ui-aktionen-ausloeser) {
  display: flex;
  width: var(--control-h);
  height: var(--control-h);
  margin-left: auto;
  justify-content: center;
}
@media (pointer: coarse) {
  :deep(.ec-list .kronos-liste-aktionen-halter .dk-ui-aktionen-ausloeser) {
    width: 44px;
    height: 44px;
  }
}
</style>
