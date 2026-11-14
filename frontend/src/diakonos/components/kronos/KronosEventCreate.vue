<template>
  <Teleport to="body">
    <div v-if="show" class="diakronos-modal show" @click.self="onBackdropClick">
      <div
        ref="fenster"
        class="diakronos-modal-dialog"
        role="dialog"
        aria-modal="true"
        aria-label="Neuer Termin"
        tabindex="-1"
        @keydown="tastenFaenger"
      >
        <div class="diakronos-modal-content">
          <!-- Farbige Leiste -->
          <div class="diakronos-color-bar" :style="{ backgroundColor: selectedCalendarColor }"></div>

          <div class="diakronos-modal-header">
            <h3>Neuer Termin</h3>
            <button class="close-btn" aria-label="Schließen" @click="close">&times;</button>
          </div>

          <!-- Tabs -->
          <DkTabs
            class="diakronos-tabs"
            aria-label="Bereiche"
            :model-value="activeTab"
            :options="[{ value: 'basic', label: 'Grunddaten' }, { value: 'details', label: 'Details' }]"
            @update:model-value="activeTab = $event"
          />

          <div class="tab-content">
            <!-- UXK-R10: Kalenderauswahl ist leer, wenn der Nutzer nirgends
                 schreiben darf. Statt einer falschen Pflichtfeld-Meldung wird
                 der Grund verstaendlich benannt. DEV-B1: Konnten die Kalender
                 gar nicht geladen werden, steht hier der LADE-Fehler — nicht
                 die Behauptung „kein Schreibrecht“. -->
            <DkHint v-if="kalenderFehler" variant="warn" data-dev-b1="kalender-fehler">
              Die Kalenderliste konnte nicht geladen werden, deshalb ist offen,
              ob du Termine anlegen darfst. Bitte schließe den Dialog und
              versuche es erneut.
            </DkHint>
            <DkHint v-else-if="!calendars.length" variant="warn" data-dev-b1="kein-schreibrecht">
              Du kannst derzeit keine Termine anlegen: Für dich ist kein
              Kalender mit Schreibrecht freigegeben. Bitte wende dich an die
              Gemeindeleitung.
            </DkHint>

            <!-- Tab 1: Grunddaten -->
            <div v-show="activeTab === 'basic'">
              <!-- UX2f: Feld mit Prüfung — der Titel ist Pflicht, die Meldung steht
              direkt am Feld; aria-invalid/aria-describedby kommen aus DkField. -->
              <DkField
                label="Titel"
                required
                :error="titelFehler"
                :regel="regelTitel"
                :wert="form.element_name"
                pflicht-name="einen Titel"
                maxlength="140"
                @update:wert="form.element_name = $event"
                v-slot="feld"
              >
                <input v-bind="feld.feldProps" type="text" placeholder="Termintitel" />
              </DkField>

              <!-- OP-UI-20: Datum und Uhrzeit über den gemeinsamen Baustein.
                   Vorher zeigte das Feld den ISO-Wert („2026-12-30 00:00“),
                   ein neuer Termin begann um 00:00 und die Uhrzeit war ein
                   freies Textfeld. Jetzt: deutsche Auswahl, Vorschlag
                   19:00–20:00, „ganztägig“ blendet die Uhrzeit aus. -->
              <DkDatumZeit
                v-model="form.element_start"
                v-model:ende-model-value="form.element_end"
                :ganztags="form.all_day"
                :mit-ende="true"
                required
                label-datum="Datum"
                label-zeit="Beginn"
                :fehler-datum="zeitFehler.datum"
                :fehler-zeit="zeitFehler.beginn"
                :fehler-ende="zeitFehler.ende"
                :fehler-enddatum="zeitFehler.enddatum"
              />

              <DkCheckbox v-model="form.all_day" label="Ganztägig" />

              <!-- UI-R5b (Punkt 2): „N Kalender … bitte wählen“ stand auf der
                   Gruppenseite HINTER dem Dialog (der Teleport hängt ihn ans
                   <body>-Ende) und war dort nicht zu sehen. Der Satz steht
                   jetzt dort, wo er gilt: im Formular ÜBER der Kalenderwahl. -->
              <DkHint v-if="kalenderWahlHinweis" variant="info" data-ui-r5b="kalender-wahl">
                {{ kalenderWahlHinweis }}
              </DkHint>

              <DkField label="Kalender" required>
                <DkSelect v-model="form.element_calendar" :options="calendarOptions" placeholder="Bitte wählen" empty-value="" />
              </DkField>

              <DkField label="Ort">
                <DkSelect v-model="form.ressource" :options="ortOptions.map(r => ({ value: r.id, label: r.title }))" placeholder="Bitte wählen" empty-value="" />
              </DkField>

              <!-- Weitere Ressourcen -->
              <div class="section-divider">Weitere Ressourcen</div>
              <div
                v-for="(row, idx) in form.zusaetzliche_ressourcen"
                :key="idx"
                class="zusatz-resource-row"
              >
                <select v-model="row.ressource" class="zusatz-select">
                  <option value="">Aus Katalog wählen</option>
                  <option
                    v-for="res in catalogOptions(row.ressource)"
                    :key="res.id"
                    :value="res.id"
                  >
                    {{ res.title }}
                  </option>
                </select>
                <input
                  v-model="row.freitext_ressource"
                  type="text"
                  class="zusatz-input"
                  placeholder="oder Freitext"
                />
                <DkBadge
                  class="status-chip"
                  :variant="row.status === 'Bestätigt' ? 'ok' : 'warn'"
                >
                  <!-- OP-EVENT-10: Der Status-Chip war frei klickbar — jeder mit
                       Schreibrecht bestätigte seine eigene Ressource und umging
                       die Ressourcen-Moderation. Nur Ressourcenmoderatoren
                       duerfen umschalten; der Server erzwingt es ohnehin. -->
                  <button
                    v-if="istRessourcenmoderator"
                    type="button"
                    class="status-chip-btn"
                    @click="row.status = row.status === 'Bestätigt' ? 'Angefragt' : 'Bestätigt'"
                  >
                    {{ row.status }}
                  </button>
                  <span v-else class="status-chip-text">{{ row.status }}</span>
                </DkBadge>
                <!-- UX1e: EIN Knopf-System. „Zeile entfernen“ ist ein
                     Ghost-Knopf (nur Symbol, Beschriftung für Vorleser), die
                     Zeile ergänzen ein Ghost-Knopf über die volle Breite —
                     vorher zwei Eigenklassen mit eigener Optik. -->
                <DkButton
                  class="row-entfernen"
                  variant="ghost"
                  size="md"
                  aria-label="Ressourcenzeile entfernen"
                  title="Ressourcenzeile entfernen"
                  @click="form.zusaetzliche_ressourcen.splice(idx, 1)"
                >&times;</DkButton>
              </div>
              <DkButton class="row-hinzufuegen" variant="ghost" size="md" block @click="addAdditionalResource">
                + Ressource anlegen
              </DkButton>
            </div>

            <!-- Tab 2: Details -->
            <div v-show="activeTab === 'details'">
              <DkCheckbox v-model="form.is_series" label="Serientermin" />

              <!-- OP-ADMIN-1: `v-show` statt `v-if`. Mit `v-if` existierte das
                   Feld beim Oeffnen des Dialogs noch nicht, der Kalender band
                   es nie — das Serienende wurde still verworfen und es
                   entstanden immer 100 Termine. (Seit OP-UI-20 bindet
                   DkDatumZeit selbst; `v-show` bleibt trotzdem richtig, weil
                   ein ausgeblendetes Feld seinen Wert behalten soll.) -->
              <DkField v-show="form.is_series" label="Wiederholung" required>
                <DkSelect v-model="form.repeat_type" :options="[{ value: 'daily', label: 'Täglich' }, { value: 'weekly', label: 'Wöchentlich' }, { value: 'monthly', label: 'Monatlich' }]" placeholder="Bitte wählen" empty-value="" />
              </DkField>

              <!-- OP-ADMIN-1/OP-UI-20: Serienende als Datumsfeld mit
                   deutschem Kalender statt eines nackten Textfelds. -->
              <DkDatumZeit
                v-show="form.is_series"
                v-model="form.series_end"
                :mit-zeit="false"
                required
                label-datum="Serienende"
              />
              <p v-show="form.is_series" class="series-hinweis">
                Ohne Serienende werden höchstens 100 Termine angelegt.
              </p>

              <DkField label="Beschreibung">
                <textarea v-model="form.description" class="dk-mod-input" rows="3"></textarea>
              </DkField>

              <DkField label="Kategorie">
                <DkSelect v-model="form.element_category" :options="categories.map(c => ({ value: c.name, label: c.event_category_name }))" placeholder="Bitte wählen" empty-value="" />
              </DkField>

              <DkCheckbox v-model="form.ignore_conflict" label="Konflikte ignorieren" />
            </div>
          </div>

          <!-- UI-R5: Der Prüfhinweis steht VOR dem Speichern — die Person soll
               wissen, dass der Termin geprüft wird, nicht erst danach. Er
               hängt am gewählten Kalender (`direkt === false` des Servers).
               Bleibt ein Kind des Formulars: der Dialogfuß ist eine
               Knopfreihe, der Hinweis bekommt eine eigene Zeile darüber.
               Der Abstand liegt am WRAPPER: `.dk-pruefhinweis` hat vorher die
               Polsterung und den Hintergrund von DkHint überschrieben (Text
               klebte oben, Box bis an den Rand, Info-Farbe weg). -->
          <div v-if="wirdGeprueft" class="dk-pruefhinweis">
            <DkHint variant="info" data-ui-r5="pruefhinweis">{{ pruefHinweis }}</DkHint>
          </div>
          <div class="diakronos-modal-footer">
            <DkButton variant="secondary" @click="close">Abbrechen</DkButton>
            <DkButton variant="primary" :loading="saving" :disabled="saving" @click="save">Speichern</DkButton>
          </div>
        </div>
      </div>
    </div>

    <!-- Konflikt-Dialog -->
    <KronosConflictDialog ref="conflictDialog" />
  </Teleport>
</template>

<script setup>
import { apiAntwortPruefen } from '../../composables/useApi.js'
// WEB-5b: Adressen unter dem Betriebs-Praefix (DIAKRONOS_BASE_PATH) bauen.
import { apiUrl, ressourceUrl } from '../../../shared/basis.js'
import { ref, reactive, watch, computed, onMounted, nextTick } from 'vue'
import { useFormularSchutz } from '../../composables/useFormularSchutz.js'
import { pruefeSitzungsAntwort } from '../../composables/useApi.js'
import KronosConflictDialog from './KronosConflictDialog.vue'
import DkField from '../ui/DkField.vue'
// UX2f: Prüfregel des Titels aus EINER Quelle (Feld und Sammelprüfung).
import { pflicht, laenge as laengeRegel } from '../../composables/feldPruefung.mjs'
import DkDatumZeit from '../ui/DkDatumZeit.vue'
import DkSelect from '../ui/DkSelect.vue'
import DkCheckbox from '../ui/DkCheckbox.vue'
import DkTabs from '../ui/DkTabs.vue'
import DkBadge from '../ui/DkBadge.vue'
import DkButton from '../ui/DkButton.vue'
import DkHint from '../ui/DkHint.vue'
import { showToast } from '../../composables/useToast.js'
import { useDialogFokus } from '../../composables/useDialogFokus.js'
// UI-R5b: „N Kalender stehen zur Auswahl“ (Punkt 2) — kein Klammerplural.
import { zahlWort } from '../ui/begriffe.mjs'
// UI-R5: Auswahlliste, Prüfhinweis und Erfolgsmeldung der Gruppenseite — eine
// Quelle für Wortlaut („Der Termin wird vor der Veröffentlichung geprüft.“),
// für die Prüfregel und für „wartet auf <Stufe>“.
import {
  PRUEFHINWEIS, kalenderOptionen, meldungNachSpeichern,
  wirdGeprueft as wirdGeprueftRegel, statusFuerKalender,
} from '../gruppen/gruppenTermin.mjs'
import {
  zerlegeDatumZeit, baueDatumZeit, vorschlagZeitraum, istDatum,
  pruefeZeitraumMitDatum, datumNach,
} from '../../composables/datumZeit.mjs'

const props = defineProps({
  show: { type: Boolean, default: false },
  initialData: { type: Object, default: () => ({}) },
  // UI-R5 („+ Termin“ auf der Gruppenseite): WELCHE Kalender dieses Formular
  // anbietet — `[{name, title}]`, fertig gefiltert vom Aufrufer (die
  // Rechtefrage beantwortet der Server). `null` = wie bisher alle
  // beschreibbaren Kalender laden (Aufruf aus dem Kalender).
  kalenderVorgabe: { type: Array, default: null },
})

const emit = defineEmits(['update:show', 'created'])

const activeTab = ref('basic')
const saving = ref(false)
const conflictDialog = ref(null)

const calendars = ref([])
// DEV-B1: Kalender konnten nicht geladen werden (Schreibrecht also UNBEKANNT
// — nicht „kein Schreibrecht“). Text erscheint als Hinweis im Dialog.
const kalenderFehler = ref('')
const categories = ref([])
const ressources = ref([]) // {types: [...], resources: [{id, title, typ, ...}]}
const kronosSettings = ref({})
// OP-EVENT-10: Ressourcenmoderator? Nur er darf den Status-Chip der
// Termin-Ressourcen umschalten.
const istRessourcenmoderator = ref(false)
// UI-R5 (Review 3): Titel der Prüfstufen („Untergruppe“, „Gruppe“, „Alle
// Mitglieder der Gemeinde“) — EINE Quelle ist der Server
// (`get_rollen_erklaerung().stufen_titel`), damit die Oberfläche keine zweite
// Wortliste pflegt. Fehlt die Antwort, bleibt die Stufe selbst lesbar.
const stufenTitel = ref({})


const form = reactive({
  element_name: '',
  element_start: '',
  element_end: '',
  all_day: false,
  element_calendar: '',
  ressource: '',
  is_series: false,
  repeat_type: '',
  series_end: '',
  description: '',
  element_category: '',
  ignore_conflict: false,
  status: '',
  zusaetzliche_ressourcen: []
})

const selectedCalendarColor = computed(() => {
  const cal = calendars.value.find(c => c.name === form.element_calendar)
  return cal?.color || 'var(--primary)'
})

const calendarOptions = computed(() => {
  // UI-R5/UI-R5b: Aufruf von einer Gruppen-/Untergruppenseite — die Kalender
  // DIESER Seite, fertig gefiltert (beschreibbar) und in Serverreihenfolge.
  // Ein zweites Argument gibt es nicht mehr; es war wirkungslos (Punkt 3).
  if (hatVorgabe.value) return kalenderOptionen(props.kalenderVorgabe)
  return calendars.value.map(c => ({ value: c.name, label: c.calendar_name }))
})

/**
 * UI-R5: Ist die Kalenderauswahl dieser Seite VORGEGEBEN?
 *
 * `null` = keine Vorgabe (Aufruf aus dem Kalender). Eine LEERE Liste ist
 * ebenfalls keine brauchbare Vorgabe: sie entsteht, wenn die Seite ihre
 * Kalenderliste noch nicht hat — dann lädt das Formular selbst, statt alle
 * Kalender zu verschweigen.
 */
const hatVorgabe = computed(() => Array.isArray(props.kalenderVorgabe)
  && props.kalenderVorgabe.length > 0)

/**
 * UI-R5: Wird der Termin des GEWÄHLTEN Kalenders vor der Veröffentlichung
 * geprüft? Die Regel steht an EINER Stelle (`wirdGeprueft` in
 * gruppenTermin.mjs, dort getestet) — hier wird sie nur gelesen.
 *
 * Review UI-R5 (HOCH) und (6): Vorher stand die Bedingung zweimal im Baum
 * (`cal.direkt !== true`) und zeigte auf der Kalenderseite JEDER Person den
 * Prüfhinweis, auch HV und Admin, weil `get_writable_calendars` dort kein
 * `direkt` lieferte. Seit R-12e liefert der Server es; maßgeblich ist
 * `direkt === false`.
 */
const gewaehlterKalender = computed(() => calendars.value.find(c => c.name === form.element_calendar) || null)
const wirdGeprueft = computed(() => wirdGeprueftRegel(gewaehlterKalender.value))
// Derselbe Satz steht im Modul (eine Quelle für Wortlaut und Regel).
const pruefHinweis = PRUEFHINWEIS

/**
 * UI-R5b (Punkt 2): Hinweis ÜBER der Kalenderwahl, wenn es MEHRERE Kalender
 * zur Auswahl gibt und noch keiner gewählt ist („Diakronos fragt, für
 * welchen“). Nur mit `kalenderVorgabe` (Gruppen-/Untergruppenseite): im
 * Kalender ist „Bitte wählen“ selbst erklärend, dort bleibt es ruhig.
 */
const kalenderWahlHinweis = computed(() => {
  if (!hatVorgabe.value || form.element_calendar) return ''
  const anzahl = calendarOptions.value.length
  if (anzahl < 2) return ''
  return `${zahlWort(anzahl, 'Kalender', 'Kalender')} stehen zur Auswahl — bitte den Kalender für diesen Termin wählen.`
})

// Ort-Dropdown: nur Räume, aber aktuellen Wert immer anbieten (Legacy)
const ortOptions = computed(() => {
  const allResources = ressources.value?.resources || []
  const raumList = allResources.filter(r => r.typ === 'Raum')
  // If current ressource is not a Raum, add it to options so it's not lost
  if (form.ressource && !raumList.find(r => r.id === form.ressource)) {
    const currentRes = allResources.find(r => r.id === form.ressource)
    if (currentRes) return [currentRes, ...raumList]
  }
  return raumList
})

// Catalog options fuer weitere Ressourcen: keine Raeume/Orte (Ort sitzt am Haupt-Event)
function catalogOptions(currentValue) {
  const allResources = ressources.value?.resources || []
  // Keine Raeume/Orte in den weiteren Ressourcen - Ort sitzt am Haupt-Event
  const list = allResources.filter(r => r.typ !== 'Raum')
  // Aktuell gewaehlten Wert (z.B. Legacy-Eintrag) immer anbieten, damit er nicht verloren geht
  if (currentValue && !list.find(r => r.id === currentValue)) {
    const currentRes = allResources.find(r => r.id === currentValue)
    if (currentRes) return [currentRes, ...list]
  }
  return list
}

function addAdditionalResource() {
  form.zusaetzliche_ressourcen.push({
    ressource: '',
    freitext_ressource: '',
    status: 'Angefragt',
    notiz: ''
  })
}

function resetForm() {
  form.element_name = ''
  form.element_start = ''
  form.element_end = ''
  form.all_day = false
  form.element_calendar = ''
  form.ressource = ''
  form.is_series = false
  form.repeat_type = ''
  form.series_end = ''
  form.description = ''
  form.element_category = ''
  form.ignore_conflict = false
  form.status = ''
  form.zusaetzliche_ressourcen = []

  zeitFehler.value = { datum: '', beginn: '', ende: '', enddatum: '' }

  if (props.initialData) {
    if (props.initialData.element_start) form.element_start = props.initialData.element_start
    if (props.initialData.element_end) form.element_end = props.initialData.element_end
    if (props.initialData.element_calendar) form.element_calendar = props.initialData.element_calendar
  }
  // DEV-5: Ohne Klickzeit beginnt ein neuer Termin mit der NÄCHSTEN vollen
  // Stunde (Browserzeit) und endet eine Stunde später; der Tag des Klicks
  // bleibt. Ein angeklickter Slot liefert bereits eine Uhrzeit und wird
  // dadurch nicht angefasst.
  const beginn = zerlegeDatumZeit(form.element_start)
  if (beginn.datum && !beginn.zeit) {
    const v = vorschlagZeitraum(new Date(), beginn.datum)
    form.element_start = baueDatumZeit(v.datum, v.beginn)
    form.element_end = baueDatumZeit(v.endeDatum, v.ende)
  }
  // Auch ohne Datum gibt es sinnvolle Felder: heute, nächste volle Stunde.
  if (!form.element_start) {
    const v = vorschlagZeitraum()
    if (v.datum) {
      form.element_start = baueDatumZeit(v.datum, v.beginn)
      form.element_end = baueDatumZeit(v.endeDatum, v.ende)
    }
  }

  activeTab.value = 'basic'
}

// OP-UI-20: flatpickr entfällt. Datum und Uhrzeit kommen aus DkDatumZeit
// (deutsche Anzeige, native Auswahl am Handy, Vorschlag 19:00–20:00). Damit
// verschwinden auch die beiden Fehler, die an flatpickr hingen: der sichtbare
// ISO-Wert und das nicht gebundene Serienende bei `v-show`.
const zeitFehler = ref({ datum: '', beginn: '', ende: '', enddatum: '' })

// UX2f: Der Termin-Titel ist Pflicht und höchstens 140 Zeichen lang. Dieselbe
// Regel prüft das Feld beim Verlassen/Tippen UND die Sammelprüfung beim
// Speichern — eine Quelle, ein Text.
const regelTitel = (wert) => pflicht('einen Titel')(wert) || laengeRegel({ max: 140, name: 'Der Titel' })(wert)
const titelFehler = ref('')

const formularSchutz = useFormularSchutz(() => form, () => saving.value)
async function close() {
  if (await formularSchutz.darfSchliessen()) emit('update:show', false)
}

// DES-R6: Fokus hinein, Tab bleibt im Fenster, Esc schliesst (der Dialog
// hatte weder role noch Fokusfuehrung; der Fokus stand auf <body>).
const fenster = ref(null)
const { tastenFaenger } = useDialogFokus(computed(() => props.show), fenster, close)

// UXK-002: Ein Doppelklick auf eine Tageszelle oeffnete den Dialog und der
// zweite Klick traf sofort den Hintergrund -> Dialog schloss wieder. Ein
// kurzer Schutz (400 ms) nach dem Oeffnen ignoriert solche Fehlklicks.
let geoeffnet_am = 0

function onBackdropClick() {
  if (Date.now() - geoeffnet_am < 400) return
  // Auch nach dem Doppelklickschutz darf ein Tipp daneben nichts verwerfen.
}

async function loadData() {
  try {
    const csrf = document.querySelector('meta[name="csrf-token"]')?.content || ''
    // DEV-B1: `Promise.allSettled` statt `Promise.all` — EIN gescheiterter
    // Nebenzweig (Kategorien, Ressourcen, Einstellungen) hat bisher die
    // Kalenderliste mitgerissen, und der Dialog behauptete dann faelschlich
    // „kein Schreibrecht“. Jetzt entscheidet allein `get_writable_calendars`
    // ueber das Schreibrecht; ein Fehler dort wird als Lade-Fehler benannt.
    const [calRes, catRes, resRes, settingsRes, sessRes, erklaerungRes] = await Promise.allSettled([
      // UI-R5: Von einer Gruppen-/Untergruppenseite kommt die Anfrage mit
      // `kalenderVorgabe`. Dann liefert `get_accessible_calendars` die Felder
      // `write`/`direkt`/`pruefstufen` je Kalender — nur so ist der Satz
      // „wird vor der Veröffentlichung geprüft“ belegbar. Ohne Vorgabe bleibt
      // der bisherige Weg (`get_writable_calendars`).
      fetch(apiUrl(hatVorgabe.value
        ? 'diakronos.kronos.api.permissions.get_accessible_calendars'
        : 'diakronos.kronos.api.permissions.get_writable_calendars'), { credentials: 'same-origin' }).then(apiAntwortPruefen),
      fetch(ressourceUrl('Eventkategorie?fields=' + encodeURIComponent('["name","event_category_name"]') + '&limit_page_length=500'), { credentials: 'same-origin' }).then(apiAntwortPruefen),
      fetch(apiUrl('diakronos.kronos.api.ressource_api.get_ressources'), {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json', 'X-Frappe-CSRF-Token': csrf },
        body: JSON.stringify({})
      }).then(apiAntwortPruefen),
      fetch(apiUrl('diakronos.kronos.api.ressource_api.get_kronos_settings'), {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json', 'X-Frappe-CSRF-Token': csrf },
        body: JSON.stringify({})
      }).then(apiAntwortPruefen),
      fetch(apiUrl('diakronos.kronos.api.permissions.get_session_info'), { credentials: 'same-origin' }).then(apiAntwortPruefen),
      // UI-R5 (Review 3): Titel der Prüfstufen aus der EINEN Quelle des Servers.
      fetch(apiUrl('diakronos.diakonos.api.rechte.get_rollen_erklaerung'), { credentials: 'same-origin' }).then(apiAntwortPruefen)
    ])

    if (calRes.status === 'fulfilled') {
      const kalenderRoh = calRes.value?.message || []
      const liste = Array.isArray(kalenderRoh) ? kalenderRoh : []
      // UI-R5: Auf einer Gruppenseite bietet das Formular nur Kalender dieser
      // Seite an (die Vorgabe kam fertig gefiltert vom Aufrufer). Die
      // Rechtefelder (`direkt`, `pruefstufen`) bleiben am Eintrag — daraus
      // kommt der Prüfhinweis. Ein Kalender, den der Server inzwischen NICHT
      // mehr als beschreibbar führt, faellt hier heraus.
      // Der Test-Aufbau alter Karten liefert hier `{message: {ok: true}}` —
      // kein Array. Das bleibt ein Lade-Ergebnis ohne Kalender, keine Ausnahme.
      calendars.value = hatVorgabe.value
        ? liste.filter(c => c && c.write === true
          && props.kalenderVorgabe.some(v => v && v.name === c.name))
        : liste
      // Eine Auswahl, die es in der neuen Liste nicht mehr gibt, wird
      // verworfen (sonst zeigt das Pflichtfeld einen Wert, den der Server
      // nicht kennt).
      if (form.element_calendar
          && !calendars.value.some(c => c.name === form.element_calendar)) {
        form.element_calendar = ''
      }
      kalenderFehler.value = ''
    } else {
      // Schreibrecht UNBEKANNT ist nicht dasselbe wie „kein Schreibrecht“.
      calendars.value = []
      kalenderFehler.value = fehlerText(calRes.reason, 'Die Kalender konnten nicht geladen werden.')
      console.error('Kalender konnten nicht geladen werden:', calRes.reason)
    }
    categories.value = catRes.status === 'fulfilled' ? (catRes.value?.data || []) : []
    ressources.value = resRes.status === 'fulfilled' ? (resRes.value?.message || {}) : {}
    kronosSettings.value = settingsRes.status === 'fulfilled' ? (settingsRes.value?.message || {}) : {}
    // OP-EVENT-10: Nur Ressourcenmoderatoren duerfen den Status-Chip klicken.
    const rollen = (sessRes.status === 'fulfilled' ? sessRes.value?.message?.roles : null) || []
    istRessourcenmoderator.value = rollen.includes('Ressourcenmoderator')
      || rollen.includes('Mitgliederadministrator')
      || rollen.includes('System Manager')
    // UI-R5 (Review 3): Stufen-Titel für „wartet auf <Stufe>“.
    const erklaerung = erklaerungRes.status === 'fulfilled' ? (erklaerungRes.value?.message || {}) : {}
    stufenTitel.value = (erklaerung && typeof erklaerung.stufen_titel === 'object' && erklaerung.stufen_titel) || {}
    // Jeder aufgegebene Zweig wird benannt (kein stiller Ausfall).
    for (const [name, r] of [['Kategorien', catRes], ['Ressourcen', resRes], ['Einstellungen', settingsRes], ['Rollen-Erklärung', erklaerungRes]]) {
      if (r.status === 'rejected') console.warn(`${name} konnten nicht geladen werden:`, r.reason)
    }
  } catch (err) {
    console.error('Fehler beim Laden der Daten:', err)
  }
}

/** Kurzer, lesbarer Text aus einem abgelehnten Lade-Versuch. */
function fehlerText(grund, ersatz) {
  const text = String(grund?.message || grund?.fehler || '').trim()
  return text && text.length <= 160 ? text : ersatz
}

async function checkConflict() {
  if (form.ignore_conflict) return false
  const hasOrt = !!form.ressource
  const additionalIds = (form.zusaetzliche_ressourcen || [])
    .filter(r => r.ressource)
    .map(r => r.ressource)

  if (!hasOrt && additionalIds.length === 0) return false

  try {
    const csrf = document.querySelector('meta[name="csrf-token"]')?.content || ''
    const res = await fetch(apiUrl('diakronos.kronos.api.ressource_api.check_resource_conflict'), {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', 'X-Frappe-CSRF-Token': csrf },
      body: JSON.stringify({
        ressource: form.ressource || '',
        element_start: form.element_start,
        element_end: form.element_end,
        zusaetzliche_ressourcen: additionalIds.map(id => ({ ressource: id }))
      })
    })
    const data = await apiAntwortPruefen(res)
    return data.message?.has_conflict ? data.message : null
  } catch (err) {
    console.error('Konfliktprüfung fehlgeschlagen:', err)
    throw err
  }
}

/**
 * OP-UI-20: Datum und Uhrzeit prüfen. Meldung am Feld (DkDatumZeit zeigt sie
 * über `fehler-*`), damit der Nutzer nicht suchen muss, welches Feld gemeint
 * ist. Gibt `true` zurück, wenn alles passt.
 */
function pruefeTerminZeit() {
  const start = zerlegeDatumZeit(form.element_start)
  const ende = zerlegeDatumZeit(form.element_end)
  const fehler = { datum: '', beginn: '', ende: '', enddatum: '' }
  if (!istDatum(start.datum)) {
    fehler.datum = 'Bitte ein gültiges Datum wählen.'
  } else if (!form.all_day && !start.zeit) {
    fehler.beginn = 'Bitte eine Beginnzeit angeben.'
  }
  // B2: Das Enddatum darf nicht vor dem Beginn liegen (mehrtägige Termine
  // sind in Ordnung, auch wenn die Endzeit vor der Beginnzeit liegt).
  if (!fehler.datum && ende.datum && datumNach(ende.datum, start.datum) === false
      && ende.datum !== start.datum) {
    fehler.enddatum = 'Das Ende liegt vor dem Beginn.'
  }
  if (!fehler.datum && !fehler.beginn && !fehler.enddatum) {
    fehler.ende = pruefeZeitraumMitDatum(
      start.datum, start.zeit, ende.datum, ende.zeit, form.all_day,
    )
  }
  zeitFehler.value = fehler
  if (fehler.datum || fehler.beginn || fehler.ende || fehler.enddatum) {
    showToast(fehler.datum || fehler.beginn || fehler.enddatum || fehler.ende, 'error')
    return false
  }
  return true
}

async function save() {
  // DEV-B1: „unbekannt“ ist kein „kein Schreibrecht“ — der Lade-Fehler bekommt
  // seinen eigenen Satz, statt die Rechte-Lage zu behaupten.
  if (kalenderFehler.value) {
    showToast('Die Kalenderliste konnte nicht geladen werden. Bitte schließe den Dialog und versuche es erneut.', 'error')
    return
  }
  if (!calendars.value.length) {
    showToast('Du hast auf keinen Kalender Schreibrecht. Termine kann die Gemeindeleitung für dich anlegen.', 'error')
    return
  }
  // UX2f: der Titel wird AM FELD beanstandet (Meldung + aria-invalid),
  // nicht nur im Toast; Beginn und Kalender bleiben beim bisherigen Weg.
  titelFehler.value = regelTitel(form.element_name)
  if (titelFehler.value) {
    activeTab.value = 'basic'
    requestAnimationFrame(() => document.querySelector('[aria-invalid="true"]')?.focus())
    return
  }
  if (!form.element_calendar || !form.element_start) {
    showToast('Bitte Beginn und Kalender ausfüllen.', 'error')
    return
  }
  // OP-UI-20: Meldung direkt am Feld statt nur im Toast; ein Ende vor dem
  // Beginn wurde bisher erst vom Server abgelehnt.
  if (!pruefeTerminZeit()) return
  // OP-ADMIN-R2: Ein Häkchen „Serientermin“ ohne Wiederholung legte still nur
  // einen Einzeltermin an. Die Wiederholung ist bei gesetztem Häkchen Pflicht.
  if (form.is_series && !form.repeat_type) {
    activeTab.value = 'details'
    showToast('Bitte eine Wiederholung wählen oder „Serientermin“ abwählen.', 'error')
    return
  }
  if (form.is_series && !form.series_end) {
    activeTab.value = 'details'
    showToast('Bitte ein Serienende angeben (sonst entstehen bis zu 100 Termine).', 'error')
    return
  }

  let conflictMsg
  try {
    conflictMsg = await checkConflict()
  } catch (err) {
    showToast(err?.message || 'Die Verfügbarkeit konnte nicht geprüft werden. Bitte erneut versuchen.', 'error')
    return
  }
  if (conflictMsg) {
    const result = await conflictDialog.value?.show({
      element_name: form.element_name,
      element_start: form.element_start,
      element_end: form.element_end,
      ressource: form.ressource,
      conflicts: (conflictMsg.conflicts || []).map(c => {
        const res = (ressources.value?.resources || []).find(r => r.id === c.ressource)
        return { ...c, ressource_title: res ? res.title : c.ressource }
      })
    })
    if (!result) return
    if (result === 'ignore') form.ignore_conflict = true
    // UXK-R6: „Als Konflikt markieren“ muss den Status „Konflikt“ setzen,
    // sonst bleibt die Moderationsspalte „Konflikte“ immer leer.
    if (result === 'conflict') form.status = 'Konflikt'
  }

  await doSave()
}

async function doSave() {
  // Filter empty additional resource rows
  const validAdditional = (form.zusaetzliche_ressourcen || []).filter(r => r.ressource || r.freitext_ressource)

  const payload = {
    element_name: form.element_name,
    element_start: form.element_start,
    element_end: form.element_end,
    all_day: form.all_day ? 1 : 0,
    element_calendar: form.element_calendar,
    ressource: form.ressource || null,
    description: form.description || null,
    element_category: form.element_category || null,
    ignore_conflict: form.ignore_conflict ? 1 : 0,
    zusaetzliche_ressourcen: JSON.stringify(validAdditional)
  }
  // UXK-R6: Ein ausdruecklicher Konflikt-Status muss mit (leer = Server-Default).
  // UI-R5b: Bei einem DIREKTSCHREIBER-Kalender (`direkt === true`) bittet das
  // Formular um "Festgelegt" — der Server legt ohne `status` immer nur einen
  // Vorschlag an (BF1-A) und verweigert Nicht-Direktschreibern "Festgelegt".
  // Ein ausdruecklicher Konflikt-Status (UXK-R6) geht vor; sonst bleibt
  // `status` weg. Die Regel steht in gruppenTermin.mjs (getestet), sie gilt
  // fuer create_event UND create_series (derselbe Payload).
  if (form.status) payload.status = form.status
  else {
    const direktStatus = statusFuerKalender(gewaehlterKalender.value)
    if (direktStatus) payload.status = direktStatus
  }

  saving.value = true
  try {
    const csrf = document.querySelector('meta[name="csrf-token"]')?.content || ''
    let res
    if (form.is_series && form.repeat_type) {
      payload.repeat_type = form.repeat_type
      payload.series_end = form.series_end || null
      res = await fetch(apiUrl('diakronos.kronos.api.event_crud.create_series'), {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json', 'X-Frappe-CSRF-Token': csrf },
        body: JSON.stringify(payload)
      })
    } else {
      res = await fetch(apiUrl('diakronos.kronos.api.event_crud.create_event'), {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json', 'X-Frappe-CSRF-Token': csrf },
        body: JSON.stringify(payload)
      })
    }

    // BF1-A: Der Fehler darf NIE still verschluckt werden. Zuerst den
    // HTTP-Status pruefen — eine Fehlermeldung des Servers ist kein Erfolg,
    // auch wenn der Body wie JSON aussieht.
    let data = null
    try { data = await apiAntwortPruefen(res, { fehlerWerfen: false }) } catch { data = null }
    pruefeSitzungsAntwort(res, data)

    const fehler = !res.ok || !data || !data.message || data.message?.success !== true
    if (fehler) {
      const meldung = extrahiereFehler(data, res)
      showToast(meldung, 'error')
      return
    }

    // Echter Erfolg: Termin benennen und ehrlich sagen, wo er landet.
    // UI-R5 (Review 3): Bei einem Vorschlag nennt die Meldung die OFFENE STUFE
    // aus `naechste_stufe` (R-12e) mit ihrem Titel aus `get_rollen_erklaerung()`
    // — nicht nur „(Vorschlag)“. Für Serien gilt der `status` aus der Antwort
    // (dieselbe Quelle), kein pauschaler Vorschlag.
    const angelegt = data.message
    const meldung = meldungNachSpeichern(angelegt, stufenTitel.value)
    showToast(meldung.text, meldung.variante)
    emit('created', angelegt)
    emit('update:show', false)
    resetForm()
    formularSchutz.merken()
  } catch (err) {
    console.error('Speichern fehlgeschlagen:', err)
    showToast('Termin konnte nicht gespeichert werden. Bitte erneut versuchen.', 'error')
  } finally {
    saving.value = false
  }
}

/** Holt die verstaendlichste Fehlermeldung aus einer API-Antwort (BF1-A). */
function extrahiereFehler(data, res) {
  if (data) {
    // Die API liefert {exc, exception, _server_messages} oder „message“ als Text.
    const kandidaten = [
      data.message, data.exception, data.exc, data.detail, data.error,
      Array.isArray(data._server_messages) ? data._server_messages.join(' ') : data._server_messages,
    ]
    for (const k of kandidaten) {
      if (typeof k === 'string' && k.trim()) return aufraeumen(k)
    }
  }
  if (res.status === 403) return 'Keine Berechtigung: Termine in diesem Kalender anlegen.'
  if (res.status === 417 || res.status === 400) return 'Die Angaben sind unvollständig oder ungültig.'
  if (res.status >= 500) return 'Der Server konnte den Termin nicht speichern. Bitte später erneut versuchen.'
  return 'Termin konnte nicht gespeichert werden.'
}

function aufraeumen(text) {
  let t = String(text).trim()
  // Frappe verpackt Fehler teils als JSON-Liste mit HTML.
  try {
    const parsed = JSON.parse(t)
    if (typeof parsed === 'string') t = parsed
    else if (Array.isArray(parsed) && typeof parsed[0] === 'string') t = parsed[0]
    else if (parsed && typeof parsed.message === 'string') t = parsed.message
  } catch { /* kein JSON — Text belassen */ }
  return t.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim() || 'Termin konnte nicht gespeichert werden.'
}

watch(() => props.show, (val) => {
  if (val) {
    geoeffnet_am = Date.now()
    resetForm()
    formularSchutz.merken()
    // UI-R5: Die Kalenderliste wird beim Öffnen NACHGELADEN — die Montage
    // (App-Start) kann sie verfehlt haben (dann behauptete der Dialog
    // faelschlich „kein Schreibrecht“, obwohl Kalender wählbar sind).
    if (!calendars.value.length) loadData()
  }
})

onMounted(() => {
  loadData()
  if (props.show) {
    resetForm()
    formularSchutz.merken()
  }
})

// UI-R5: Die Kalenderlage dieser Seite kommt nach dem Seitenaufbau. Ohne
// diesen Nachlauf bliebe ein früh geöffnetes Formular bei der Liste vom
// Montagezeitpunkt stehen (im Messlauf: der Untergruppen-Kalender fehlte).
watch(hatVorgabe, (jetzt) => {
  if (jetzt) loadData()
})
</script>

<style scoped>
.diakronos-modal {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: color-mix(in oklch, var(--dk-navy-900) 55%, transparent);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: var(--z-modal);
  opacity: 0;
  visibility: hidden;
  transition: opacity var(--med) var(--ease), visibility var(--med) var(--ease);
}
.diakronos-modal.show {
  opacity: 1;
  visibility: visible;
}
.diakronos-modal-dialog {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-lg);
  max-width: 560px;
  width: 90%;
  max-height: 90vh;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}
.diakronos-modal-content {
  display: flex;
  flex-direction: column;
  max-height: 90vh;
}
.diakronos-color-bar {
  height: 6px;
  width: 100%;
  transition: background-color var(--med) var(--ease);
}
.diakronos-modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--sp-4) var(--sp-alt-20);
  border-bottom: 1px solid var(--line);
}
.diakronos-modal-header h3 {
  margin: 0;
  font-size: var(--fs-h2);
  font-weight: var(--fw-h);
  color: var(--text);
}
.close-btn {
  background: none;
  border: none;
  font-size: var(--fs-26);
  cursor: pointer;
  color: var(--muted);
  line-height: 1;
}
.close-btn:hover { color: var(--text); }
.diakronos-tabs { margin: 0; }
.tab-content {
  padding: var(--sp-4) var(--sp-alt-20);
  overflow-y: auto;
  max-height: calc(90vh - 200px);
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
}
.form-row {
  display: flex;
  gap: var(--sp-3);
}
.form-row > * {
  flex: 1;
}
.dk-mod-input {
  width: 100%;
  padding: 8px 10px;
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  font-size: var(--fs);
  font-family: inherit;
  color: var(--text);
  box-sizing: border-box;
  outline: none;
  transition: border-color var(--fast);
}
.dk-mod-input:focus { border-color: var(--dk-navy-400); }

/* Weitere Ressourcen section */
.section-divider {
  font-weight: var(--fw-fett);
  font-size: var(--fs);
  color: var(--text);
  margin: var(--sp-2) 0 0;
  padding-top: var(--sp-3);
  border-top: 1px solid var(--line);
}
.zusatz-resource-row {
  display: flex;
  gap: var(--sp-2);
  align-items: center;
}
.zusatz-select,
.zusatz-input {
  flex: 1;
  padding: 6px 8px;
  border: 1px solid var(--line);
  border-radius: var(--radius-sm);
  font-size: var(--fs-sm);
  font-family: inherit;
  background: var(--surface);
  color: var(--text);
  box-sizing: border-box;
  min-width: 0;
}
.status-chip { flex-shrink: 0; }
.status-chip-btn {
  background: none;
  border: none;
  color: inherit;
  font: inherit;
  cursor: pointer;
  padding: 0;
}
/* UX1e: `.remove-row-btn` und `.add-row-btn` sind weg — beide sind jetzt
   DkButton (ghost, sm). Nur die Lage in der Zeile bleibt eigen. */
.row-entfernen { flex-shrink: 0; font-size: var(--fs-16); }
.row-hinzufuegen { justify-content: flex-start; }

.diakronos-modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: var(--sp-2);
  padding: var(--sp-3) var(--sp-alt-20);
  border-top: 1px solid var(--line);
  background: var(--surface-2);
}
/* UI-R5: Der Prüfhinweis bekommt eine eigene Zeile über der Knopfreihe. Der
   Abstand liegt am WRAPPER — DkHint selbst behält seine Polsterung und seine
   Info-Farbe (vorher überschrieb diese Regel beides: Text klebte oben, die Box
   lief bis an den Rand). Der Abstand kommt aus der 4er-Leiter; kein
   Handy-Zweig: die Regel hängt an keiner Breite, der Hinweis bricht selbst um.
   Senkrecht dieselben 16px wie `--pad` (Innenabstand von DkHint), waagerecht
   `--sp-4` — NICHT `--sp-alt-20`, dessen Bestand je Datei eingefroren ist und
   nur schrumpfen darf (UX1a2/F4). */
.dk-pruefhinweis {
  padding: var(--sp-4);
  background: var(--surface-2);
}
</style>
