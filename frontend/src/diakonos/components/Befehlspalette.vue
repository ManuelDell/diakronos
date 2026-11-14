<template>
  <!-- UX3f · Befehlspalette (Strg+K / ⌘+K) nach Entwurf A5.
       Aufbau: Abdunkelung, Fenster 640 px, Suchzeile, Abschnitte
       (Zuletzt verwendet · Seiten · Personen · Gruppen · Termine · Lieder ·
       Aktionen), Fußzeile mit Tastenhinweisen.
       Treffer zeigen ihren Ort rechts (Prinzip N7). Nur Tokens — keine festen
       Farben (Wächter-Test). -->
  <Teleport to="body">
    <div
      v-if="offen"
      class="dk-palette-huelle"
      @mousedown.self="schliessen"
    >
      <div
        ref="fensterEl"
        class="dk-palette"
        role="dialog"
        aria-modal="true"
        aria-label="Befehlspalette"
        @keydown="taste"
      >
        <div class="dk-palette-suchzeile">
          <DkSymbol name="suchen" :groesse="20" class="dk-palette-lupe" />
          <input
            ref="feldEl"
            v-model="begriff"
            class="dk-palette-feld"
            type="text"
            role="combobox"
            aria-expanded="true"
            aria-controls="dk-palette-liste"
            aria-autocomplete="list"
            :aria-activedescendant="aktiveId || undefined"
            placeholder="Suchen … Personen, Termine, Seiten"
            autocomplete="off"
            spellcheck="false"
            :aria-label="'Suchen in Diakronos'"
          />
          <span v-if="laedt" class="dk-palette-laden"><DkSpinner klein text="Treffer werden gesucht" /></span>
          <kbd v-else class="dk-palette-taste">{{ kuerzel.schliessen }}</kbd>
        </div>

        <div id="dk-palette-liste" class="dk-palette-liste" role="listbox" aria-label="Treffer">
          <!-- Fehlerzustand (Prinzip I5): echte Meldung + „Erneut versuchen“.
               Was schon dasteht, bleibt sichtbar — ein Fehler löscht keine
               Treffer. -->
          <div v-if="fehler" class="dk-palette-fehler" role="alert">
            <span>{{ fehler }}</span>
            <DkButton variant="ghost" size="sm" @click="erneutVersuchen">Erneut versuchen</DkButton>
          </div>

          <template v-for="gruppe in gruppen" :key="gruppe.id">
            <!-- role="group" + aria-labelledby statt role="presentation":
                 Screenreader nennen den Abschnittsnamen als Gruppentitel,
                 statt die Überschrift zu verschweigen. -->
            <div
              class="dk-palette-abschnitt"
              role="group"
              :aria-labelledby="abschnittId(gruppe.id)"
            >
              <span :id="abschnittId(gruppe.id)">{{ gruppe.label }}</span>
            </div>
            <button
              v-for="zeile in gruppe.zeilen"
              :id="idFuer(zeile)"
              :key="zeile.id"
              type="button"
              role="option"
              class="dk-palette-zeile"
              :class="{ 'is-aktiv': zeile.position === auswahl }"
              :aria-selected="zeile.position === auswahl ? 'true' : 'false'"
              @click="oeffne(zeile)"
              @mousemove="auswahl = zeile.position"
            >
              <DkSymbol :name="zeile.symbol" :groesse="18" class="dk-palette-zeilen-symbol" />
              <span class="dk-palette-titel">{{ zeile.titel }}</span>
              <span class="dk-palette-ort">{{ zeile.ort }}</span>
              <kbd v-if="zeile.position === auswahl" class="dk-palette-enter">{{ kuerzel.oeffnen_taste }}</kbd>
            </button>
          </template>

          <!-- Leerzustand: nur behaupten, wenn der Server für DIESEN Begriff
               geantwortet hat (istLeer in befehlspalette.mjs). -->
          <div v-if="leer" class="dk-palette-leer">
            <p class="dk-palette-leer-titel">Nichts gefunden für „{{ begriff.trim() }}“.</p>
            <p class="dk-palette-leer-text">Anders schreiben oder eine Seite direkt aufrufen — Strg+K öffnet diese Suche überall.</p>
          </div>
        </div>

        <div class="dk-palette-fuss">
          <span class="dk-palette-hinweis"><kbd>{{ kuerzel.hoch }}</kbd><kbd>{{ kuerzel.runter }}</kbd> wählen</span>
          <span class="dk-palette-hinweis"><kbd>{{ kuerzel.oeffnen_taste }}</kbd> öffnen</span>
          <span class="dk-palette-hinweis"><kbd>{{ kuerzel.schliessen }}</kbd> schließen</span>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
/**
 * Befehlspalette (UX3f, Entwurf A5).
 *
 * ÖFFNEN: Strg+K / ⌘+K überall (ausser in einem Eingabefeld — dort gehört das
 * Kürzel dem Feld) und Klick auf das Suchfeld der Kopfzeile (`oeffnen()` über
 * `defineExpose`). Schliessen: Esc, Klick daneben.
 *
 * Die Palette zeichnet NUR. Was sie zeigt (Abschnitte, Seiten aus der
 * Menüdefinition, Aktionen je Recht, Zuletzt-verwendet-Verlauf) und wie sie
 * auf Tasten reagiert, steht in `composables/befehlspalette.mjs` und ist dort
 * ohne Browser geprüft.
 *
 * Treffer kommen ausschliesslich vom Server (`suche.global`, UX3g); welche
 * Treffer jemand sehen darf, entscheidet der Server. Die Palette filtert NICHT
 * nachrechte-halber und lädt nicht nach.
 */
import { computed, nextTick, ref, watch, onMounted, onUnmounted } from 'vue'
import DkSymbol from './ui/DkSymbol.vue'
import DkSpinner from './ui/DkSpinner.vue'
import DkButton from './ui/DkButton.vue'
// Review UX3f: Fokusfalle + Fokus-Rückgabe wie bei DkDialog (DES-R6) — Tab
// bleibt im Fenster, Esc schliesst, beim Schliessen geht der Fokus zurück auf
// das Element, das die Palette geöffnet hat.
import { useDialogFokus } from '../composables/useDialogFokus.js'
import { apiGet } from '../composables/useApi.js'
import { fehlertext } from '../../shared/fehlertexte.js'
import { navigate } from '../router.js'
import { useSession } from '../composables/useSession.js'
import { useKronosStore } from '../composables/useKronosStore.js'
import { MENUE, FUSS_EINTRAEGE, sichtbareEintraege } from '../menue.js'
import {
  KUERZEL as kuerzel, MIN_ZEICHEN, istLeer, istOeffnenTaste, richtungstaste, naechsteAuswahl,
  paletteZeilen, trefferEinsortieren, seitenEintraege, aktionsEintraege,
  verlaufLesen, verlaufSchreiben, verlaufNachWahl, gesuchteArten,
} from '../composables/befehlspalette.mjs'

const { isAdmin, istMitgliederverwaltung, istGast, istTester, rollen, user } = useSession()

/**
 * Nutzerkennung für den Verlauf „Zuletzt verwendet“ (DSGVO, Review UX3f):
 * derselbe Ausdruck wie in main.js für den Planrahmen-Cache — die E-Mail,
 * sonst der Anzeigename. Der Verlaufsschlüssel hängt daran.
 */
const nutzerKennung = computed(() => String(user.value?.email || user.value?.fullname || ''))

const offen = ref(false)
const begriff = ref('')
const auswahl = ref(-1)
const fensterEl = ref(null)
const feldEl = ref(null)

/** Server-Treffer des aktuellen Begriffs. */
const treffer = ref([])
/** Arten, für die der Server geantwortet hat (`quellen` aus `suche.global`). */
const gesucht = ref(null)
/** Begriff, für den der Server GEANTWORTET hat (nicht: gerade läuft). */
const beantwortet = ref('')
const laedt = ref(false)
const fehler = ref('')

// ── Rechtslage und Quellen ───────────────────────────────────────────────────

const rechte = computed(() => ({
  istAdmin: isAdmin.value === true,
  // UI-R10: zweite Verwaltungsstufe — „Einstellungen“ und der Personenbereich.
  istMitgliederverwaltung: istMitgliederverwaltung.value === true,
  istTester: istTester.value === true,
  istGast: istGast.value === true,
  rollen: Array.isArray(rollen.value) ? rollen.value : [],
}))

const seiten = computed(() => seitenEintraege({
  menue: MENUE, fuss: FUSS_EINTRAEGE, sichtbareEintraege, rechte: rechte.value,
}))

/**
 * Die zwei Anlege-Wege des Entwurfs — nur, wenn das Ziel sie wirklich anbietet.
 * „Termin anlegen“: der Kalender bietet es bei Schreibrecht auf mindestens
 * einen Kalender (`get_accessible_calendars` -> `write`, dieselbe Regel wie die
 * Schaltfläche im Kalender). „Person anlegen“: Mitgliederverwaltung.
 */
const darfTerminAnlegen = ref(false)
const aktionen = computed(() => aktionsEintraege({
  darfTermin: darfTerminAnlegen.value,
  // UI-R10: „Person anlegen“ ist Personenbereich — Mitgliederverwaltung oder
  // Administrator (der Server verweigert es anderen ohnehin).
  darfPerson: rechte.value.istMitgliederverwaltung && !rechte.value.istGast,
}))

const verlauf = ref([])

/** Die Arten aus der Server-Antwort (`quellen`) — steuert, welche Abschnitte es gibt. */
const gesuchteArtenVon = computed(() => (gesucht.value ? Object.fromEntries([...gesucht.value].map(a => [a, true])) : null))

const trefferZeilen = computed(() => trefferEinsortieren(
  treffer.value,
  { gefragt: beantwortet.value === begriff.value.trim(), quellen: gesuchteArtenVon.value },
))

const gebaut = computed(() => paletteZeilen({
  begriff: begriff.value,
  verlauf: verlauf.value,
  seiten: seiten.value,
  aktionen: aktionen.value,
  treffer: trefferZeilen.value,
}))

const gruppen = computed(() => gebaut.value.gruppen)
const zeilen = computed(() => gebaut.value.zeilen)
const leer = computed(() => istLeer({
  begriff: begriff.value,
  zeilen: zeilen.value,
  trefferGefragt: beantwortet.value === begriff.value.trim() && !laedt.value,
}))

const aktiveId = computed(() => {
  const z = zeilen.value[auswahl.value]
  return z ? idFuer(z) : ''
})

function idFuer(zeile) {
  return 'dk-palette-' + String(zeile.id).replace(/[^A-Za-z0-9_-]+/g, '-')
}

function abschnittId(id) {
  return 'dk-palette-abschnitt-' + String(id)
}

// ── Server-Abfrage (entprellt) ───────────────────────────────────────────────

let suchTimer = 0
let laufendeAnfrage = 0

function planeSuche() {
  clearTimeout(suchTimer)
  const wert = begriff.value.trim()
  if (wert.length < MIN_ZEICHEN) {
    // Unter der Mindestlänge antwortet der Server ohnehin leer; kein Aufruf.
    treffer.value = []
    gesucht.value = null
    beantwortet.value = wert
    laedt.value = false
    fehler.value = ''
    return
  }
  laedt.value = true
  suchTimer = setTimeout(() => suche(wert), 180)
}

async function suche(wert) {
  const meine = ++laufendeAnfrage
  try {
    // GET: der Endpunkt deklariert `methods=["GET"]` (SEC-11) — ein POST
    // wird dort mit 405 abgewiesen. `apiGet` schickt die Parameter im
    // Abfrageteil und trägt Token/Sitzungsbehandlung genauso.
    const antwort = await apiGet('diakronos.diakonos.api.suche.global', { q: wert })
    if (meine !== laufendeAnfrage) return
    treffer.value = Array.isArray(antwort?.treffer) ? antwort.treffer : []
    // Welche Arten hat der Server gesucht? Ein Abschnitt ohne diese Angabe
    // ist für die Sitzung nicht vorhanden und erscheint gar nicht erst.
    gesucht.value = gesuchteArten(antwort)
    beantwortet.value = wert
    fehler.value = ''
  } catch (err) {
    if (meine !== laufendeAnfrage) return
    // Prinzip I4/I5: Katalogtext statt roher Servermeldung. `fehlertext`
    // nimmt eine brauchbare deutsche Fachmeldung des Servers, ersetzt aber
    // Floskeln, technische Kennungen und Stapel durch den Katalogtext.
    fehler.value = fehlertext(err || {}, {
      angefragt: true,
      text: 'Die Suche hat gerade nicht geklappt. Versuche es noch einmal.',
    })
  } finally {
    if (meine === laufendeAnfrage) laedt.value = false
  }
}

function erneutVersuchen() {
  fehler.value = ''
  const wert = begriff.value.trim()
  if (wert.length < MIN_ZEICHEN) return
  laedt.value = true
  suche(wert)
}

// Auswahl: nach jeder neuen Liste auf die erste Zeile, damit ↵ sofort wirkt.
watch(zeilen, () => {
  auswahl.value = zeilen.value.length ? 0 : -1
}, { flush: 'sync' })

/**
 * Review UX3f: Die aktive Zeile muss IM BILD bleiben. Ohne das wanderte ↑↓
 * bei langen Listen (26 Termine im Seed) unsichtbar unter den Rand — die
 * Auswahl stand im Nirgendwo, ↵ traf eine Zeile, die niemand sah.
 * `block: 'nearest'` scrollt nur, wenn es nötig ist; `smooth` bleibt aus, weil
 * eine Tastenwiederholung sonst hinterherläuft.
 */
function aktiveZeileSichtbar() {
  const el = document.getElementById(aktiveId.value)
  if (el && typeof el.scrollIntoView === 'function') {
    el.scrollIntoView({ block: 'nearest', inline: 'nearest' })
  }
}

watch(auswahl, () => {
  nextTick(aktiveZeileSichtbar)
})

watch(begriff, () => {
  auswahl.value = -1
  planeSuche()
})

// ── Termin-Schreibrecht (für „Termin anlegen“) ───────────────────────────────
//
// Die Palette fragt das Recht EINMAL beim Öffnen ab (nicht bei jedem Tastendruck).
// Ein Fehler bleibt still: dann fehlt der Eintrag — ein Eintrag, der den
// Kalender nur lesend öffnet, wäre ein toter Knopf.
//
// Gelesen wird über den gemeinsamen Kalender-Speicher (`useKronosStore`), der
// die Liste ohnehin für den Kalender lädt — kein zweiter Weg zum selben
// Endpunkt, keine zweite Rechteauslegung.

const kronos = useKronosStore()

async function kalenderRechtPruefen() {
  try {
    // Bereits geladene Liste nutzen (der Kalender lädt sie beim Öffnen) —
    // sonst EINMAL nachladen. So kostet die Palette im Regelfall keinen Aufruf.
    let liste = kronos.availableCalendars?.value
    if (!Array.isArray(liste) || !liste.length) {
      liste = await kronos.fetchAccessibleCalendars()
    }
    darfTerminAnlegen.value = (Array.isArray(liste) ? liste : [])
      .some(k => k && k.write === true)
  } catch (_) {
    darfTerminAnlegen.value = false
  }
}

// ── Öffnen / Schliessen ──────────────────────────────────────────────────────

async function oeffnen() {
  if (offen.value) {
    feldEl.value?.focus()
    return
  }
  begriff.value = ''
  treffer.value = []
  gesucht.value = null
  beantwortet.value = ''
  fehler.value = ''
  laedt.value = false
  auswahl.value = -1
  offen.value = true
  verlauf.value = verlaufLesen(speicher(), nutzerKennung.value)
  kalenderRechtPruefen()
  await nextTick()
  feldEl.value?.focus()
}

function schliessen() {
  offen.value = false
  clearTimeout(suchTimer)
  // Eine laufende Anfrage darf keine Zeilen mehr in die nächste Öffnung legen.
  ++laufendeAnfrage
  laedt.value = false
}

defineExpose({ oeffnen, schliessen })

// Fokus (Review UX3f, DES-R6): Tab bleibt im Fenster, Esc schliesst, beim
// Schliessen geht der Fokus auf das Element zurück, das die Palette geöffnet
// hat (Suchfeld der Kopfzeile bzw. der Auslöser der Tastenkombination).
// `esc = false`: Esc behandelt `taste` am Fenster bereits selbst — zwei
// Handler würden doppelt schliessen.
useDialogFokus(offen, fensterEl, schliessen, { esc: false })

function speicher() {
  try {
    return typeof window !== 'undefined' ? window.localStorage : null
  } catch (_) {
    return null
  }
}

// ── Tastatur ─────────────────────────────────────────────────────────────────

function taste(event) {
  if (event.key === 'Escape') {
    event.preventDefault()
    event.stopPropagation()
    schliessen()
    return
  }
  const richtung = richtungstaste(event)
  if (richtung) {
    event.preventDefault()
    auswahl.value = naechsteAuswahl(auswahl.value, zeilen.value.length, richtung)
    return
  }
  if (event.key === 'Home') {
    event.preventDefault()
    auswahl.value = zeilen.value.length ? 0 : -1
    return
  }
  if (event.key === 'End') {
    event.preventDefault()
    auswahl.value = zeilen.value.length ? zeilen.value.length - 1 : -1
    return
  }
  if (event.key === 'Enter') {
    event.preventDefault()
    const ziel = zeilen.value[auswahl.value]
    if (ziel) oeffne(ziel)
  }
}

function beiKuerzel(event) {
  if (!istOeffnenTaste(event)) return
  const ziel = event.target
  // Nicht kapern: in Feldern (dort gehört das Kürzel dem Feld) und in offenen
  // Dialogen, die selbst eine Tastaturbehandlung haben.
  if (!offen.value && !darfFeldAusnehmen(ziel)) return
  event.preventDefault()
  if (offen.value) schliessen()
  else oeffnen()
}

/**
 * Darf Strg+K hier greifen? In Eingabefeldern NICHT — ausser die Palette ist
 * schon offen (dann schliesst das Kürzel wieder).
 */
function darfFeldAusnehmen(ziel) {
  const tag = String(ziel?.tagName || '').toUpperCase()
  return !['INPUT', 'TEXTAREA', 'SELECT'].includes(tag) && ziel?.isContentEditable !== true
}

// ── Ausführen ────────────────────────────────────────────────────────────────

/**
 * Zeile wählen: Verlauf fortschreiben, schliessen, navigieren.
 *
 * Der Verlauf speichert NUR die Zeile (Titel, Ort, Ziel) — nie den getippten
 * Text. Ein Fehler beim Speichern (privater Modus) bleibt still.
 */
function oeffne(zeile) {
  if (!zeile) return
  verlauf.value = verlaufNachWahl(verlauf.value, zeile)
  verlaufSchreiben(speicher(), verlauf.value, nutzerKennung.value)
  schliessen()
  // Seiten-Adressen laufen über den Router; alles andere (falls je ein
  // Nicht-Seitenziel dazukommt) über dieselbe Adresse.
  navigate(zeile.ziel)
}

// ── Lebenszyklus ─────────────────────────────────────────────────────────────

onMounted(() => {
  window.addEventListener('keydown', beiKuerzel)
  // Schon geöffnete Palette an ein neues Recht anpassen (Konto wechselt).
  auswahl.value = -1
})

onUnmounted(() => {
  window.removeEventListener('keydown', beiKuerzel)
  clearTimeout(suchTimer)
  ++laufendeAnfrage
})

// Bei leerer Eingabe steht der Startzustand; ein alter Fehler darf dort nicht
// stehenbleiben.
watch(begriff, (wert) => {
  if (!String(wert || '').trim()) fehler.value = ''
})
</script>

<style scoped>
/* Abdunkelung wie bei den Dialogen (dieselbe Quelle: --overlay). */
.dk-palette-huelle {
  position: fixed;
  inset: 0;
  /* Eigener Stapelkontext: die Palette ist damit EINE Ebene über der Seite.
     Ohne `isolation` mischten sich ihre Zeilen mit den Ebenen der App (im
     Wegwerf-Stack lag die Fußzeile optisch über den Termin-Zeilen). */
  isolation: isolate;
  /* Eigene Z-Ebene ÜBER den Dialogen (--z-modal = 400): „Strg+K öffnet
     überall“ muss auch stimmen, wenn gerade ein Fenster offen ist. */
  z-index: var(--z-palette);
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding: var(--sp-7) var(--sp-4) var(--sp-6);
  background: var(--overlay);
}

.dk-palette {
  display: flex;
  flex-direction: column;
  width: var(--palette-w);
  max-width: 100%;
  /* Entwurf A5: 640 × 624 px (--palette-w/-h in tokens.css). FESTE Höhe
     (nicht nur max-height): im Wegwerf-Stack gemessen wuchs der Scrollbereich
     in einem Flex-Container ohne definite Höhe über den Rahmen hinaus
     (959 px Inhalt in 508 px Fläche) und schob die Fußzeile aus dem Bild. */
  height: min(var(--palette-h), calc(100vh - var(--sp-7) * 2.5));
  background: var(--surface);
  color: var(--text);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-lg);
  overflow: hidden;
}

.dk-palette-suchzeile {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  padding: 0 var(--sp-5);
  min-height: var(--palette-suchzeile-h);
  border-bottom: var(--rahmen-breite) solid var(--line);
}

.dk-palette-lupe {
  color: var(--primary);
  flex: none;
}

.dk-palette-feld {
  flex: 1;
  min-width: 0;
  border: 0;
  outline: none;
  background: transparent;
  color: var(--text);
  font-family: inherit;
  font-size: var(--fs-16);
  font-weight: var(--fw-mittel);
  line-height: 1.5;
  padding: var(--sp-2) 0;
}

.dk-palette-feld::placeholder {
  color: var(--subtle);
  font-weight: var(--fw-normal);
}

.dk-palette-laden {
  display: inline-flex;
  align-items: center;
  color: var(--muted);
}

.dk-palette-taste,
.dk-palette-enter {
  font-family: inherit;
  font-size: var(--fs-12);
  color: var(--muted);
  background: var(--surface-2);
  border: var(--rahmen-breite) solid var(--line);
  border-radius: var(--radius-sm);
  padding: var(--sp-1);
  line-height: 1.4;
  flex: none;
}

.dk-palette-liste {
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;
  overscroll-behavior: contain;
  padding: var(--sp-2) var(--sp-3) var(--sp-3);
}

.dk-palette-abschnitt {
  padding: var(--sp-3) var(--sp-3) var(--sp-1);
  font-size: var(--fs-12);
  font-weight: var(--fw-fett);
  color: var(--muted);
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.dk-palette-zeile {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  width: 100%;
  /* Klickfläche: Prinzip K4 — ganze Zeile, mindestens --control-h. */
  min-height: var(--control-h);
  padding: var(--sp-2) var(--sp-3);
  border: 0;
  border-radius: var(--radius);
  background: none;
  color: var(--text);
  font-family: inherit;
  font-size: var(--fs-14);
  font-weight: var(--fw-normal);
  text-align: left;
  cursor: pointer;
}

.dk-palette-zeile.is-aktiv {
  background: var(--surface-hover);
}

.dk-palette-zeile:focus-visible {
  outline: var(--rahmen-breite) solid var(--focus-ring);
  outline-offset: calc(var(--rahmen-breite) * -1);
}

.dk-palette-zeilen-symbol {
  color: var(--muted);
  flex: none;
}

.dk-palette-zeile.is-aktiv .dk-palette-zeilen-symbol {
  color: var(--primary);
}

.dk-palette-titel {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-weight: var(--fw-mittel);
}

.dk-palette-ort {
  flex: none;
  font-size: var(--fs-12);
  color: var(--muted);
  max-width: 40%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.dk-palette-fehler {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  flex-wrap: wrap;
  margin: var(--sp-2) var(--sp-3);
  padding: var(--sp-3);
  border-radius: var(--radius);
  background: var(--err-soft);
  color: var(--err);
  font-size: var(--fs-14);
}

.dk-palette-leer {
  padding: var(--sp-6) var(--sp-5);
  text-align: center;
}

.dk-palette-leer-titel {
  margin: 0 0 var(--sp-2);
  font-size: var(--fs-14);
  font-weight: var(--fw-fett);
  color: var(--text);
}

.dk-palette-leer-text {
  margin: 0;
  font-size: var(--fs-12);
  color: var(--muted);
  line-height: 1.5;
}

.dk-palette-fuss {
  display: flex;
  align-items: center;
  gap: var(--sp-4);
  padding: var(--sp-3) var(--sp-5);
  border-top: var(--rahmen-breite) solid var(--line);
  background: var(--surface-2);
}

.dk-palette-hinweis {
  display: inline-flex;
  align-items: center;
  gap: var(--sp-1);
  font-size: var(--fs-12);
  color: var(--muted);
}

.dk-palette-hinweis kbd {
  font-family: inherit;
  font-size: var(--fs-12);
  color: var(--muted);
  background: var(--surface);
  border: var(--rahmen-breite) solid var(--line);
  border-radius: var(--radius-sm);
  padding: var(--sp-1);
  line-height: 1.4;
}

/* Mobil (390 px): die Palette liegt oben, das Feld bleibt 16 px (iOS zoomt
   sonst beim Fokussieren). Zeilen bleiben ≥ 44 px hoch.
   DEV-B6 (Review-Nacharbeit 10.11.): „mobil“ ist die Handy-Lage als KLASSE
   `.dk-app--handy` (Quelle `composables/handyLage.mjs`) — eine ganzseitige
   Overlay-Palette ist Touch-Bedienung, kein Inhaltsumbruch; ein Maus-Laptop
   bei 702 px behält die schwebende Palette. */
  .dk-app--handy .dk-palette-huelle {
    padding: var(--sp-4);
  }
  .dk-app--handy .dk-palette {
    width: 100%;
    height: calc(100vh - var(--sp-7));
    border-radius: var(--radius);
  }
  .dk-app--handy .dk-palette-suchzeile {
    padding: 0 var(--sp-4);
    min-height: var(--control-h);
  }
  .dk-app--handy .dk-palette-zeile {
    min-height: var(--control-h);
  }
  .dk-app--handy .dk-palette-ort {
    max-width: 45%;
  }
  .dk-app--handy .dk-palette-fuss {
    padding: var(--sp-2) var(--sp-4);
    gap: var(--sp-3);
  }


/* Der grobe Zeiger bekommt die 44 px NICHT hier, sondern über den
   blockweiten `--control-h: 44px` in index.css (@media pointer: coarse) —
   `--control-h` steuert die Zeilenhöhe bereits. */
</style>