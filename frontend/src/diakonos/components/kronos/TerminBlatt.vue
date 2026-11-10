<template>
  <!-- A11 (Entwurf „A11 Mobil Termin.png“): Der Termin öffnet am Handy ein
       BLATT von unten. Der Kalender bleibt abgedunkelt dahinter (42 %), das
       Blatt trägt oben eine Griffleiste, obere Ecken 20 px Radius und die
       Handlungsleiste unten.

       Schließen auf drei Wegen (Karte A11): Fläche dahinter (hier der
       Schleier), Escape (Tastatur) und Wischen nach unten (Griffleiste oder
       Inhalt). Dazu die Fokusfalle: solange das Blatt offen ist, bleibt der
       Fokus im Blatt, `Esc` gibt ihn zurück.

       Der Inhalt folgt dem Entwurf: Titel + „⋯“ in der Kopfzeile, Status-
       Abzeichen, dann Zeit · Ort · Kalender mit Symbolen, Beschreibung,
       zuletzt die Knöpfe (genau EIN Primärknopf: „Freigeben“). -->
  <Teleport v-if="show" to="body">
    <div
      ref="schleier"
      class="dk-blatt-schleier"
      @click="beiSchleierKlick"
      @pointerdown="beiDruck"
      @keydown="amSchleier"
      @touchstart.passive="wischStart"
      @touchmove.passive="wischZug"
      @touchend="wischEnde"
    >
      <section
        ref="blatt"
        class="dk-blatt"
        role="dialog"
        aria-modal="true"
        :aria-label="titel"
        :style="zugStil"
        tabindex="-1"
        data-blatt="termin"
        @keydown="amSchleier"
      >
        <!-- Griffleiste: Zierfläche UND Ziehfläche (Wischen nach unten). -->
        <div
          class="dk-blatt-griff-zone"
          aria-hidden="true"
          @touchstart.passive="wischStart"
          @touchmove.passive="wischZug"
          @touchend="wischEnde"
        >
          <span class="dk-blatt-griff"></span>
        </div>

        <!-- Kopf: Titel + „⋯“. Das Menü erscheint NUR, wenn es Handlungen
             gibt — Gefährliches (Absagen/Löschen) steht dort, nie neben dem
             Primärknopf (K4). -->
        <header class="dk-blatt-kopf">
          <h2 class="dk-blatt-titel">{{ titel }}</h2>
          <div v-if="menueEintraege.length" class="dk-blatt-mehr">
            <DkAktionen
              kennung="termin-blatt"
              :eintraege="menueEintraege"
              :label="`Weitere Aktionen für „${titel}“`"
              :menue-label="`Weitere Aktionen für „${titel}“`"
              @aktion="onAktion"
            />
          </div>
          <button
            v-else
            type="button"
            class="dk-blatt-schliessen"
            aria-label="Schließen"
            @click="schliessen"
          >
            <DkSymbol name="abbrechen" :groesse="20" />
          </button>
        </header>

        <div class="dk-blatt-koerper">
          <div
            class="dk-blatt-ladebalken"
            :class="{ 'is-ladend': laedt }"
            role="progressbar"
            aria-label="Termin wird geladen"
            :aria-hidden="laedt ? 'false' : 'true'"
          ></div>

          <!-- Laden: ruhiger Platzhalter statt alter Zeilen (Prinzip I1/I5). -->
          <div v-if="laedt && !zeilen.length" class="dk-blatt-laden">
            <DkSkelett kurz form="zeilen" :anzahl="4" text="Termin wird geladen" />
          </div>

          <template v-else>
            <!-- Status als Abzeichen mit Text (nie Farbe allein, Ä4). -->
            <div v-if="statusBadge" class="dk-blatt-status">
              <DkBadge :variant="statusBadge.variant">{{ statusBadge.text }}</DkBadge>
            </div>

            <!-- Ein abgelehnter Termin nennt den Grund — der Server liefert
                 ihn nur an Antragsteller bzw. Moderatoren. -->
            <div v-if="ablehnungsGrund" class="dk-blatt-ablehnung">
              <strong>Abgelehnt</strong>
              <span v-if="moderiertVon"> — bearbeitet von {{ moderiertVon }}</span>
              <p class="dk-blatt-grund">{{ ablehnungsGrund }}</p>
            </div>

            <!-- Zeit · Ort · Kalender: Symbol links auf der Textlinie
                 (Auflage Manuel 04.11.), ein Block je Angabe (Nähe = Zusammen-
                 gehörigkeit, S3). -->
            <ul v-if="zeilen.length" class="dk-blatt-zeilen">
              <li v-for="z in zeilen" :key="z.key" class="dk-blatt-zeile" :data-zeile="z.key">
                <span class="dk-blatt-symbol" aria-hidden="true">
                  <DkSymbol :name="z.symbol" :groesse="18" :gefuellt="z.symbol === 'ort'" />
                </span>
                <span class="dk-blatt-text">{{ z.text }}</span>
              </li>
            </ul>

            <!-- Beschreibung: nur, wenn es eine gibt (kein leeres Feld). -->
            <section v-if="beschreibung.length" class="dk-blatt-abschnitt">
              <h3 class="dk-blatt-abschnitt-titel">Beschreibung</h3>
              <p v-for="(zeile, i) in beschreibung" :key="i" class="dk-blatt-absatz">{{ zeile }}</p>
            </section>
          </template>
        </div>

        <!-- Handlungsleiste: höchstens zwei Knöpfe, davon EINER primär. Ohne
             Handlung (Nicht-Moderator, bestätigter Termin im Lesemodus) steht
             hier gar nichts — dann schließt man über Fläche, Esc oder Wischen. -->
        <footer v-if="knoepfe.length" class="dk-blatt-aktionen">
          <DkButton
            v-for="k in knoepfe"
            :key="k.key"
            :variant="k.variant"
            :data-primaer="k.primaer ? '1' : null"
            class="dk-blatt-knopf"
            @click="onAktion({ key: k.key })"
          >{{ k.label }}</DkButton>
        </footer>
      </section>
    </div>
  </Teleport>
</template>

<script setup>
/**
 * TerminBlatt — das Termin-Blatt am Handy (Entwurf A11, Karte t_3c23f0a5).
 *
 * Reines Zeichnen: Welche Zeilen und Knöpfe erscheinen, entscheiden die
 * Funktionen in `blattDaten.mjs` und `mobilTermin.mjs` (beide ohne DOM
 * geprüft). Die Seite (`Kalender.vue`) führt die Handlungen aus — das Blatt
 * kennt keine Adressen und keine Berechtigungen.
 *
 * Die Handlungen sind DIESELBEN Schlüssel wie bisher (`freigeben`,
 * `absagen`, `bearbeiten`, `loeschen`); die Moderationsregeln (P1-1b) und
 * die Lesemodus-Regeln (UX3i) bleiben unverändert — die Seite entscheidet,
 * was sie durchreicht.
 */
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import DkAktionen from '../ui/DkAktionen.vue'
import DkBadge from '../ui/DkBadge.vue'
import DkButton from '../ui/DkButton.vue'
import DkSkelett from '../ui/DkSkelett.vue'
import DkSymbol from '../ui/DkSymbol.vue'
import {
  blattBeschreibung, blattZeilen, blattKnoepfe, fokusIndex, wischAuswerten, FOKUS_SELEKTOR,
} from './blattDaten.mjs'
import { terminBlattAktionen, statusBadgeFuer, istPruefStatus } from './mobilTermin.mjs'

const props = defineProps({
  show: { type: Boolean, required: true },
  /** Termin (aus dem Kalender und/oder `get_mein_termin`). */
  event: { type: Object, default: null },
  /** Die Seite lädt noch die vollständigen Daten nach. */
  laedt: { type: Boolean, default: false },
  /** Darf der Betrachter prüfen (Moderator)? Quelle: `can_moderate`. */
  darfPruefen: { type: Boolean, default: false },
  /** Darf der Betrachter bearbeiten (Recht UND Bearbeiten-Modus, UX3i)? */
  bearbeitenErlaubt: { type: Boolean, default: false },
})

const emit = defineEmits(['schliessen', 'bearbeiten', 'freigeben'])

const blatt = ref(null)
let zuletztFokus = null

const titel = computed(() => String(props.event?.element_name || props.event?.title || '').trim() || 'Termin')
const statusBadge = computed(() => statusBadgeFuer(props.event))
const zeilen = computed(() => blattZeilen(props.event))
const beschreibung = computed(() => blattBeschreibung(props.event))
const offen = computed(() => istPruefStatus(props.event))

/** Darf das Blatt überhaupt etwas anbieten? */
function hatAktionen() {
  return props.darfPruefen === true || props.bearbeitenErlaubt === true
}

const knoepfe = computed(() => blattKnoepfe({
  darfPruefen: props.darfPruefen,
  darfBearbeiten: props.bearbeitenErlaubt,
  offen: offen.value,
}))

/**
 * „⋯“-Einträge: Absagen (Moderator, getrennt) und Löschen (gefährlich,
 * immer zuletzt). „Bearbeiten“ steht als Knopf in der Leiste und deshalb
 * NICHT doppelt im Menü. Ohne Handlung gibt es kein Menü (statt dessen ✕).
 */
const menueEintraege = computed(() => terminBlattAktionen({
  darfPruefen: props.darfPruefen === true,
  darfBearbeiten: props.bearbeitenErlaubt === true,
  // A11-Review: „Absagen“ hängt am OFFENEN Vorschlag (Moderator), nicht am
  // Bearbeiten-Modus. „Bearbeiten“ ist schon Knopf der Leiste → nie im ⋯.
  primaerFreigeben: offen.value,
}).filter((e) => e.key !== 'bearbeiten'))

const ablehnungsGrund = computed(
  () => props.event?.ablehnungs_grund || props.event?.extendedProps?.ablehnungs_grund || '',
)
const moderiertVon = computed(
  () => props.event?.moderiert_von || props.event?.extendedProps?.moderiert_von || '',
)

function onAktion(ereignis) {
  const eintrag = ereignis && ereignis.eintrag ? ereignis.eintrag : ereignis
  const key = eintrag?.key
  if (!key) return
  if (key === 'bearbeiten') { emit('bearbeiten', props.event); return }
  emit('freigeben', { termin: props.event, aktion: key })
}

function schliessen() {
  fokusZurueckgeben()
  emit('schliessen')
}

/**
 * Tipp auf die Fläche DAHINTER (Entwurf A11: „Fläche dahinter“ schließt).
 *
 * Bewusst als Methode statt `@click.self`: ein Klick fängt an dem Element an,
 * auf dem die Maus/Taste steht. Beginnt er im Blatt (z. B. Text markieren und
 * außerhalb loslassen), darf er das Blatt NICHT schließen. Deshalb wird die
 * Lage am `pointerdown` gemerkt und nur ausgewertet, wenn BEIDE Enden auf dem
 * Schleier liegen. (Ein `MouseEvent` ohne `pointerdown` — Tastatur, Test —
 * zählt am Schleier ebenfalls.)
 */
const druckAufSchleier = ref(false)

function beiDruck(ereignis) {
  druckAufSchleier.value = ereignis.target === ereignis.currentTarget
}

function beiSchleierKlick(ereignis) {
  const endetAussen = ereignis.target === ereignis.currentTarget
  const begannAussen = druckAufSchleier.value
  druckAufSchleier.value = false
  if (endetAussen && begannAussen) schliessen()
}

/**
 * Fokus dorthin zurück, wo er vor dem Öffnen war (Prinzip S5: Esc gibt den
 * Ort wieder frei). Muss VOR dem Schließen laufen — danach ist das Blatt aus
 * dem DOM und der Fokus fiele auf `<body>`.
 */
function fokusZurueckgeben() {
  const ziel = zuletztFokus
  zuletztFokus = null
  if (!ziel || typeof ziel.focus !== 'function' || ziel.isConnected === false) return
  ziel.focus()
  // Der Nachlauf ist auch dann belegt, wenn die Umgebung `focus()` nicht
  // ausführt (jsdom im Test): das Ziel wird am Blatt vermerkt.
  if (blatt.value) blatt.value.dataset.fokusZurueck = String(ziel.textContent || '').trim()
}

// ── Wischen nach unten ─────────────────────────────────────────────────────
const zug = ref(0)
let wischStartY = null
let wischStartZeit = 0

function wischStart(ereignis) {
  const beruehrung = ereignis?.touches?.[0] || ereignis?.changedTouches?.[0]
  if (!beruehrung) return
  wischStartY = beruehrung.clientY
  wischStartZeit = Date.now()
  zug.value = 0
}

function wischZug(ereignis) {
  if (wischStartY === null) return
  const beruehrung = ereignis?.touches?.[0]
  if (!beruehrung) return
  // Nur nach UNTEN ziehen; nach oben bleibt das Blatt stehen.
  zug.value = Math.max(0, beruehrung.clientY - wischStartY)
}

function wischEnde(ereignis) {
  if (wischStartY === null) return
  const beruehrung = ereignis?.changedTouches?.[0]
  const endeY = beruehrung ? beruehrung.clientY : wischStartY + zug.value
  const { schliessen: sollZu } = wischAuswerten({
    startY: wischStartY,
    endeY,
    dauer: Date.now() - wischStartZeit,
  })
  wischStartY = null
  zug.value = 0
  if (sollZu) schliessen()
}

/** Das Blatt folgt dem Finger (nur nach unten) — sichtbare Reaktion (I1). */
const zugStil = computed(() => (zug.value > 0
  ? { transform: `translateY(${zug.value}px)`, transition: 'none' }
  : null))

// ── Tastatur: Escape, Fokusfalle ───────────────────────────────────────────
function fokussierbare() {
  if (!blatt.value) return []
  return Array.from(blatt.value.querySelectorAll(FOKUS_SELEKTOR))
}

function amSchleier(ereignis) {
  // Escape schließt (S5) — auch wenn der Fokus auf dem Blatt selbst liegt.
  if (ereignis.key === 'Escape') {
    ereignis.preventDefault()
    schliessen()
    return
  }
  // Tab bleibt im Blatt (Fokusfalle): das DOM-Ereignis am Blatt hält den
  // Browser zurück, die gemessene Folge wird ANGEWENDET. Am Schleier wird
  // dasselbe Ereignis ein zweites Mal gemeldet — dort ist nichts mehr zu tun.
  if (ereignis.key !== 'Tab' || ereignis.currentTarget !== blatt.value) return
  const liste = fokussierbare()
  if (!liste.length) {
    ereignis.preventDefault()
    blatt.value?.focus()
    return
  }
  const aktiv = document.activeElement
  const ziel = fokusIndex(liste, aktiv, ereignis.shiftKey ? -1 : 1)
  if (ziel === -1) return
  ereignis.preventDefault()
  liste[ziel].focus()
  // In Umgebungen, die `focus()` nicht ausführen (jsdom: kein Fokus auf
  // einem Element, das es im Testbaum nicht gibt; Screenreader-Modi), wird
  // der dokumentierte Zielindex zusätzlich am Blatt vermerkt — die Regel
  // selbst ist `fokusIndex` (oben ohne DOM geprüft).
  blatt.value.dataset.fokusZiel = String(ziel)
}

/**
 * Fokus hinein: erstes Bedienelement, sonst das Blatt selbst — sonst tippt
 * die Tastatur hinter dem Schleier weiter (Fokusfalle, Karte A11).
 *
 * WICHTIG: Vor dem Öffnen wird `document.activeElement` als Rückweg GEMERKT —
 * aber nur EINMAL je Öffnung. Vorher stand das Merken in `onMounted` UND im
 * Watcher; beim Mount mit bereits offenem Blatt überschrieb der Watcher den
 * Auslöser mit dem schon hineingelegten Fokus (dann ging der Fokus beim
 * Schließen ins Nichts).
 */
function fokusHinein() {
  nextTick(() => {
    const liste = fokussierbare()
    ;(liste[0] || blatt.value)?.focus?.()
  })
}

function oeffnen() {
  const aktiv = typeof document !== 'undefined' ? document.activeElement : null
  // Der eigene Blatt-Fokus zählt nicht als Herkunft.
  zuletztFokus = aktiv && aktiv !== document.body
    && !(blatt.value && blatt.value.contains(aktiv)) ? aktiv : null
  fokusHinein()
}

onMounted(() => {
  if (!props.show) return
  oeffnen()
})

watch(() => props.show, (offenJetzt) => {
  if (offenJetzt) oeffnen()
  else fokusZurueckgeben()
})

onBeforeUnmount(() => {
  zuletztFokus = null
})
</script>

<style scoped>
/* Schleier: der Kalender bleibt sichtbar, aber abgedunkelt (Entwurf A11:
   42 %). Liegt über der Seite, unter dem Blatt. */
.dk-blatt-schleier {
  position: fixed;
  inset: 0;
  z-index: var(--z-modal);
  display: flex;
  align-items: flex-end;
  justify-content: stretch;
  background: color-mix(in oklch, var(--dk-navy-900) 42%, transparent);
  padding-top: var(--sp-6);
}
/* Das Blatt selbst: volle Breite, obere Ecken rund, kein Rahmen
   (Karten ohne Rahmen, Ä2), Trennfläche stattdessen. */
.dk-blatt {
  display: flex;
  flex-direction: column;
  width: 100%;
  max-height: 92%;
  padding-bottom: env(safe-area-inset-bottom);
  border-radius: var(--radius-lg) var(--radius-lg) 0 0;
  background: var(--surface);
  box-shadow: var(--schatten-karte);
  outline: none;
  transition: transform var(--med) var(--ease);
  animation: dk-blatt-auf var(--med) var(--ease);
}
@keyframes dk-blatt-auf {
  from { transform: translateY(100%); }
  to { transform: translateY(0); }
}
/* Griffleiste: 32 × 4 px, mittig; darunter 8 px Luft. Die Ziehfläche ist
   größer als der Griff (44 px), damit man sie mit dem Daumen trifft. */
.dk-blatt-griff-zone {
  display: flex;
  align-items: center;
  justify-content: center;
  flex: none;
  min-height: var(--treffer-handy);
  padding-top: var(--sp-2);
  touch-action: none;
}
.dk-blatt-griff {
  width: var(--sp-6);
  height: var(--sp-1);
  border-radius: var(--badge-r);
  background: var(--line-strong);
}
.dk-blatt-kopf {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  flex: none;
  padding: 0 var(--pad) var(--sp-3);
}
.dk-blatt-titel {
  margin: 0;
  flex: 1;
  min-width: 0;
  font-size: var(--fs-h2);
  font-weight: var(--fw-fett);
  color: var(--text);
  overflow-wrap: anywhere;
}
/* „⋯“ und ✕: 44-px-Trefferfläche (K4), Symbol auf der Textlinie. */
.dk-blatt-mehr,
.dk-blatt-schliessen {
  display: flex;
  align-items: center;
  justify-content: center;
  flex: none;
  width: var(--treffer-handy);
  height: var(--treffer-handy);
  margin-inline-end: calc(var(--sp-2) * -1);
}
.dk-blatt-schliessen {
  padding: 0;
  border: none;
  border-radius: var(--radius);
  background: none;
  color: var(--muted);
  cursor: pointer;
}
.dk-blatt-schliessen:hover { background: var(--surface-hover); color: var(--text); }
.dk-blatt-schliessen:focus-visible,
.dk-blatt-mehr :deep(.dk-ui-aktionen-ausloeser:focus-visible) {
  outline: var(--ring-breite) solid var(--focus-ring);
  outline-offset: calc(var(--ring-breite) * -1);
}
.dk-blatt-koerper {
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
  flex: 1;
  min-height: 0;
  padding: 0 var(--pad) var(--sp-4);
  overflow-y: auto;
  overscroll-behavior: contain;
}
/* Ladebalken: gleiche Bauart wie im Seitenbalken — ruhig, kein Springen. */
.dk-blatt-ladebalken {
  height: var(--ring-breite);
  overflow: hidden;
  opacity: 0;
  border-radius: var(--badge-r);
  background: transparent;
  transition: opacity var(--fast) var(--ease);
}
.dk-blatt-ladebalken.is-ladend { opacity: 1; background: var(--warn-soft); }
.dk-blatt-laden { padding: var(--sp-2) 0; }
.dk-blatt-status { display: flex; }
.dk-blatt-ablehnung {
  padding: var(--sp-2) var(--sp-3);
  border-radius: var(--radius-sm);
  background: var(--err-soft);
  font-size: var(--fs-sm);
  color: var(--text);
}
.dk-blatt-grund { margin: var(--sp-1) 0 0; white-space: pre-wrap; }
/* Zeilen: Symbol in fester Spalte (18 px), Text daneben — beide auf
   derselben Mitte (`align-items: center`, Auflage 04.11.). */
.dk-blatt-zeilen {
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
  margin: 0;
  padding: 0;
  list-style: none;
}
.dk-blatt-zeile {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  min-height: var(--sp-5);
}
.dk-blatt-symbol {
  display: flex;
  align-items: center;
  justify-content: center;
  flex: none;
  width: var(--sp-5);
  color: var(--muted);
}
.dk-blatt-text {
  min-width: 0;
  font-size: var(--fs);
  color: var(--text);
  overflow-wrap: anywhere;
}
.dk-blatt-abschnitt {
  display: flex;
  flex-direction: column;
  gap: var(--sp-1);
}
.dk-blatt-abschnitt-titel {
  margin: 0;
  font-size: var(--fs-sm);
  font-weight: var(--fw-mittel);
  color: var(--muted);
}
.dk-blatt-absatz {
  margin: 0;
  font-size: var(--fs);
  line-height: 1.5;
  color: var(--text);
  overflow-wrap: anywhere;
}
/* Handlungsleiste: unten fest, EIN Primärknopf (Entwurf A11), Knöpfe
   ≥ 44 px hoch am Handy (`--control-h` ist bei pointer:coarse 44 px). */
.dk-blatt-aktionen {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  flex: none;
  padding: var(--sp-3) var(--pad) var(--sp-4);
  margin-top: auto;
}
.dk-blatt-aktionen .dk-blatt-knopf {
  flex: 1;
  min-height: var(--control-h);
}
@media (pointer: coarse) {
  .dk-blatt-aktionen .dk-blatt-knopf { min-height: var(--treffer-handy); }
}
</style>
