<template>
  <div class="pr-ansicht" :class="{ 'pr-ansicht--druck': druckModus }">
    <!-- UXP-R7: Drucken-Knopf fuer JEDE Ansicht (der Chorplan deklariert keine
         eigene Druckansicht, muss aber als Aushang druckbar sein). -->
    <div v-if="druckKnopf" class="pr-druck-leiste">
      <span class="pr-ansicht-druckhinweis">
        Drucken zeigt nur den Plan — Seitenleiste, Knöpfe und Hinweise bleiben weg.
      </span>
      <button type="button" class="dk-btn dk-btn-secondary dk-btn-sm" data-test="pr-drucken" @click="drucken">Drucken</button>
    </div>

    <!-- Druck-Schaltfläche bei Druckansichten -->
    <div v-if="druckModus" class="pr-ansicht-druckleiste">
      <span class="pr-ansicht-druckhinweis">
        Druckansicht ({{ orientierung === 'quer' ? 'A4 quer' : 'A4 hoch' }}) — bitte im Drucker „Hintergrundgrafiken“ aktivieren.
      </span>
      <button class="dk-btn dk-btn-secondary dk-btn-sm" @click="drucken">Drucken</button>
    </div>

    <!-- Nur auf dem Papier: sprechende Ueberschrift, damit ein Aushang ohne
         die Bildschirm-Kopfzeile erkennbar bleibt. -->
    <div class="pr-druck-kopf">
      <span class="pr-druck-kopf-titel">{{ plan?.titel || 'Plan' }}</span>
      <span v-if="druckZeitraum" class="pr-druck-kopf-zeitraum">{{ druckZeitraum }}</span>
    </div>
    <PrTabelle
      v-if="art === 'tabelle' || art === 'druck'"
      :plan="plan" :termine="termine" :eintraege="eintraege"
      :definitionen="definitionen" :ansicht="tabelleAnsicht"
      :meldungen-zeigen="bearbeitbar"
      @bearbeiten="(t, p) => $emit('bearbeiten', t, p)"
    />
    <PrRaster
      v-else-if="art === 'raster'"
      :plan="plan" :termine="termine" :eintraege="eintraege"
      :definitionen="definitionen" :ansicht="ansicht || {}"
      :meldungen-zeigen="bearbeitbar"
      :bearbeitbar="bearbeitbar"
      @bearbeiten="(t, p) => $emit('bearbeiten', t, p)"
      @variante="(t, v) => $emit('variante', t, v)"
    />
    <PrKalender
      v-else-if="art === 'kalender'"
      :plan="plan" :termine="termine" :eintraege="eintraege"
      :definitionen="definitionen" :ansicht="ansicht || {}"
      :meldungen-zeigen="bearbeitbar"
      @bearbeiten="(t, p) => $emit('bearbeiten', t, p)"
    />
    <PrAblauf
      v-else-if="art === 'ablauf' || art === 'programm'"
      :plan="plan" :termin="termin" :eintraege="eintraege"
      :definitionen="definitionen" :ansicht="ansicht || {}"
      :bearbeitbar="bearbeitbar"
      :modus="art"
      @bearbeiten="(t, p) => $emit('bearbeiten', t, p)"
      @operationen="(ops) => $emit('operationen', ops)"
      @geaendert="$emit('geaendert')"
    />
    <div v-else-if="art === 'meine_dienste'" class="pr-ansicht-hinweis">
      Diese Ansicht zeigt deine persönlichen Dienste.
      <button class="dk-btn dk-btn-secondary dk-btn-sm" @click="$emit('navigation', '#/planrahmen/meine-dienste')">
        Zu meinen Diensten
      </button>
    </div>
    <div v-else-if="art === 'ical'" class="pr-ansicht-hinweis">
      Kalender-Export: alle Termine als Datei übernehmen.
      <button class="dk-btn dk-btn-secondary dk-btn-sm" @click="icsLaden">Kalenderdatei herunterladen</button>
    </div>
    <div v-else class="pr-ansicht-hinweis">
      Diese Ansichtsart ({{ art }}) wird noch nicht dargestellt.
    </div>
  </div>
</template>

<script setup>
/**
 * Ansichten-Verteiler: zeigt je nach deklarierter Ansichtart die passende
 * generische Darstellung. 'druck' nutzt dieselbe Tabelle im A4-Layout
 * (A4-quer/A4-hoch); Druckausgabe über window.print().
 */
import { computed, watch, onMounted, onUnmounted } from 'vue'
import PrTabelle from './PrTabelle.vue'
import PrRaster from './PrRaster.vue'
import PrKalender from './PrKalender.vue'
import PrAblauf from './PrAblauf.vue'
import { datumText } from '../../composables/usePlanrahmen.js'
// UXP-R22/K6: Anlässe auch im iCal-Export als Anzeigename, nie als rohe
// Kennung („1_weihnachtstag“); der Sammelanlass „feiertag“ bleibt draußen.
import { anlassName, sichtbareAnlaesse } from './anlaesse.mjs'

const props = defineProps({
  plan: { type: Object, default: null },
  termine: { type: Array, default: () => [] },
  eintraege: { type: Array, default: () => [] },
  definitionen: { type: [Object, Map], default: () => ({}) },
  ansicht: { type: Object, default: null },
  termin: { type: Object, default: null },
  bearbeitbar: { type: Boolean, default: false },
  // UXP-R7: „Drucken“ als Knopf der Plan-Kopfzeile. Der Chorplan deklariert
  // keine eigene Druckansicht; der Knopf setzt den Plan trotzdem sauber aufs
  // Papier (window.print() loest `beforeprint` aus, siehe unten).
  druckKnopf: { type: Boolean, default: false },
})
defineEmits(['bearbeiten', 'operationen', 'geaendert', 'navigation', 'variante'])

const art = computed(() => props.ansicht?.art || 'tabelle')

/**
 * UXP-R22/K6: Die `anlaesse`-Deklaration der Planvorlage, damit ein Anlass
 * seinen Anzeigenamen aus der Vorlage bekommt (sonst gilt der Katalog in
 * `anlaesse.mjs`, sonst ein lesbarer Ersatz — nie die rohe Kennung).
 */
const anlassKatalog = computed(() => {
    const liste = props.definitionen instanceof Map
        ? [...props.definitionen.values()]
        : Object.values(props.definitionen || {})
    for (const def of liste) {
        if (Array.isArray(def?.anlaesse) && def.anlaesse.length) return def.anlaesse
    }
    return []
})

/** Drucklayout: entweder eigene 'druck'-Ansicht oder druck-Eigenschaft. */
const druckModus = computed(() => art.value === 'druck' || !!props.ansicht?.druck)
const orientierung = computed(() => {
    const d = art.value === 'druck' ? (props.ansicht?.druck || 'A4-hoch') : props.ansicht?.druck
    return String(d || '').includes('quer') ? 'quer' : 'hoch'
})

/** Für 'druck' dieselbe Tabelle wie die tabelle Ansicht der Definition. */
const tabelleAnsicht = computed(() => {
    if (art.value !== 'druck') return props.ansicht || {}
    const tabelle = (props.plan?.ansichten || []).find((a) => a.art === 'tabelle') || {}
    return { ...tabelle, druck: props.ansicht?.druck }
})

/** Zeitraumzeile der Druckueberschrift (nur auf dem Papier sichtbar). */
const druckZeitraum = computed(() => {
    const von = props.plan?.zeitraum_von
    const bis = props.plan?.zeitraum_bis
    if (!von && !bis) return ''
    return `${datumText(von, false)} – ${datumText(bis, false)}`
})

// ── Druck (UXP-R7 / OP-EVENT-5) ────────────────────────────────────────────
//
// Befund der Nachtpruefung: Druckausgaben enthielten Seitenleiste, Kopfzeile
// und Knöpfe, der Plan stand in einer 256 px breiten Spalte, und alles nach
// der ersten Seite fehlte. Ursache sind drei Regeln in `index.css`:
//   .dk-app            { display:grid; grid-template-columns:256px 1fr; height:100vh }
//   html,body,#app     { height:100%; overflow:hidden }
//   .dk-main-wrap/.dk-content { overflow:hidden } bzw. intern scrollend
// Ein blosses `.dk-app{display:block}` reicht daher NICHT (gemessen in R-UXP):
// ohne `height:auto`/`overflow:visible` verschwindet ab Zeile 6 wieder alles.
// Darum stellt `DRUCK_CSS` Hoehen und Overflow frei, macht aus dem Raster einen
// Block und blendet die Nicht-Plan-Bereiche aus.
//
// Die Regeln gelten fuer JEDE Ansicht (auch die Chorplan-`tabelle`, die gar
// keinen `druck` deklariert): `druckModus` setzt sie dauerhaft fuer
// deklarierte Druckansichten, `beforeprint` zusaetzlich fuer den normalen
// Druck (Strg+P, Menue „Drucken“) und `afterprint` raeumt wieder auf.

const DRUCK_AUSBLENDEN = [
    '.dk-sidebar', '.dk-topbar', '.dk-bottom-nav', '.diakonos-toast-container',
    '.dk-screen-actions', '.dk-crumbs', '.dk-crumb', '.dk-crumb-sep',
    '.pr-druck-leiste', '.pr-ansicht-druckleiste', '.pr-plan-leiste',
    '.pr-plan-meldungen', '.pr-erststart', '.pr-legende',
    '.dk-devmodus-rahmen', '.dk-dev-start', '.impersonation-banner',
]
const DRUCK_BESCHNITT = [
    '.pr-tabelle tr', '.pr-raster-tabelle tr', '.pr-ablauf-element', '.pr-tabelle-karte',
]
const DRUCK_UEBERLAUF = ['.pr-tabelle-wrap', '.pr-raster', '.pr-kalender-wrap']

/**
 * Druck-Stylesheet als Text. `ausrichtung` ist 'quer' | 'hoch'.
 * `.pr-druck-aktiv` sitzt am `<body>`; `html,body,#app` werden bewusst OHNE
 * diese Klasse angesprochen, weil die Hoehen-/Overflow-Sperre auf Ebene des
 * Wurzelelements sitzt (index.css:15).
 */
function druckCss(ausrichtung) {
    return `@media print {
      @page { size: A4 ${ausrichtung === 'quer' ? 'landscape' : 'portrait'}; margin: 12mm; }
      html, body, #app { height: auto !important; overflow: visible !important; }
      /* Papier bleibt weiss, unabhaengig vom Bildschirm-Theme (Dunkelmodus
         darf den Ausdruck nicht schwaerzen): --dk-warm-0 ist der feste
         Papier-Ton des Design-Systems und wechselt nicht mit dem Theme. */
      body.pr-druck-aktiv { background: var(--dk-warm-0) !important; }
      /* DES-R1/Nachtrag R-P1-12: Das Theme sitzt seit DES-R1 auch am <html>.
         Die hellen Papierwerte liegen deshalb als Token-Paare in tokens.css
         (--druck-*) und werden hier nur zugeordnet — sonst behaelt .dk-app im
         Dunkelmodus var(--bg)/var(--text) und druckt hellen Text auf weisses
         Papier. */
      html[data-theme="dark"],
      [data-theme="dark"] .dk-app,
      [data-theme="dark"] #dk-inhalt {
        --bg: var(--druck-bg);
        --bg-subtle: var(--druck-bg);
        --surface: var(--druck-bg);
        --surface-2: var(--druck-bg);
        --surface-hover: var(--druck-bg);
        --text: var(--druck-text);
        --muted: var(--druck-muted);
        --subtle: var(--druck-subtle);
        --line: var(--druck-line);
        --line-strong: var(--druck-line-strong);
        --divider: var(--druck-line);
        --primary: var(--druck-primary);
        --primary-ink: var(--druck-bg);
        --accent: var(--druck-accent);
        --event-ink: var(--druck-text);
      }
      body.pr-druck-aktiv .dk-app,
      body.pr-druck-aktiv .dk-app * {
        background-image: none !important;
      }
      /* Zellen- und Zeilen-Hintergruende bleiben transparent, damit nichts auf
         dem Papier grau erscheint. */
      body.pr-druck-aktiv .pr-tabelle td,
      body.pr-druck-aktiv .pr-tabelle th,
      body.pr-druck-aktiv .pr-raster-tabelle td,
      body.pr-druck-aktiv .pr-raster-tabelle th,
      body.pr-druck-aktiv .pr-raster-zelle {
        background: transparent !important;
        box-shadow: none !important;
      }
      body.pr-druck-aktiv .dk-app { display: block !important; height: auto !important; }
      body.pr-druck-aktiv .dk-main-wrap, body.pr-druck-aktiv .dk-content {
        display: block !important; height: auto !important; overflow: visible !important; }
      body.pr-druck-aktiv ${DRUCK_AUSBLENDEN.join(', body.pr-druck-aktiv ')} { display: none !important; }
      body.pr-druck-aktiv .dk-main-wrap { padding: 0 !important; margin: 0 !important; }
      body.pr-druck-aktiv .dk-content, body.pr-druck-aktiv .dk-screen {
        padding: 0 !important; margin: 0 !important; max-width: none !important; width: auto !important; }
      body.pr-druck-aktiv .pr-ansicht--druck { border: none !important; padding: 0 !important; }
      /* Lange Reihen nicht mitten in einer Zeile zerreissen; klebende
         Tabellenkoepfe und Scroll-Rahmen im Druck aufloesen. */
      body.pr-druck-aktiv ${DRUCK_BESCHNITT.join(', body.pr-druck-aktiv ')} { break-inside: avoid; }
      body.pr-druck-aktiv .pr-tabelle thead th,
      body.pr-druck-aktiv .pr-raster-tabelle thead th { position: static !important; }
      body.pr-druck-aktiv ${DRUCK_UEBERLAUF.join(', body.pr-druck-aktiv ')} { overflow: visible !important; }
    }`
}

let styleEl = null
let aussenAktiv = false      // Druckmodus war schon vor dem Druckvorgang aktiv

function stylesheetSichern() {
    if (!styleEl) {
        styleEl = document.createElement('style')
        styleEl.setAttribute('data-pr-druck', '')
        document.head.appendChild(styleEl)
    }
    return styleEl
}

// Deklarierte Druckansichten: Regeln dauerhaft setzen, solange sie sichtbar ist.
watch([druckModus, orientierung], ([aktiv]) => {
    if (!aktiv) {
        document.body.classList.remove('pr-druck-aktiv')
        aussenAktiv = false
        if (styleEl) { styleEl.remove(); styleEl = null }
        return
    }
    stylesheetSichern().textContent = druckCss(orientierung.value)
    document.body.classList.add('pr-druck-aktiv')
    aussenAktiv = true
}, { immediate: true })

/** Kurz vor dem Druck (Strg+P, window.print()): Druckregeln scharfschalten. */
function druckVorbereiten() {
    if (aussenAktiv) return
    stylesheetSichern().textContent = druckCss(orientierung.value)
    document.body.classList.add('pr-druck-aktiv')
}

/** Nach dem Druck: nur aufraeumen, was dieser Vorgang gesetzt hat. */
function druckAufraeumen() {
    if (aussenAktiv) return
    document.body.classList.remove('pr-druck-aktiv')
    if (styleEl) { styleEl.remove(); styleEl = null }
}

onMounted(() => {
    // Manche Browser feuern `beforeprint` nicht zuverlaessig; zusaetzlich
    // greift der Knopf „Drucken“, der direkt `window.print()` aufruft.
    window.addEventListener('beforeprint', druckVorbereiten)
    window.addEventListener('afterprint', druckAufraeumen)
})

onUnmounted(() => {
    window.removeEventListener('beforeprint', druckVorbereiten)
    window.removeEventListener('afterprint', druckAufraeumen)
    document.body.classList.remove('pr-druck-aktiv')
    if (styleEl) { styleEl.remove(); styleEl = null }
})

function drucken() { window.print() }

/** iCal-Export der Terminreihe (ohne Server, aus den Plan-Terminen). */
function icsLaden() {
    const zeilen = [
        'BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//Diakronos//Plan-Rahmen//DE',
    ]
    for (const t of props.termine) {
        if (t.entfaellt) continue
        const datum = String(t.datum).slice(0, 10).replace(/-/g, '')
        const zeit = t.uhrzeit ? String(t.uhrzeit).slice(0, 5).replace(':', '') + '00' : ''
        const anlaesse = sichtbareAnlaesse(t.anlaesse)
            .map((a) => anlassName(a, anlassKatalog.value))
        const zusammenfassung = [props.plan?.titel, t.titel, anlaesse.join(', ')]
            .filter(Boolean).join(' — ').replace(/[,;]/g, ' ')
        zeilen.push('BEGIN:VEVENT')
        zeilen.push(`UID:${t.id}@diakronos`)
        zeilen.push(zeit ? `DTSTART:${datum}T${zeit}` : `DTSTART;VALUE=DATE:${datum}`)
        zeilen.push(`SUMMARY:${zusammenfassung}`)
        zeilen.push('END:VEVENT')
    }
    zeilen.push('END:VCALENDAR')
    const blob = new Blob([zeilen.join('\r\n')], { type: 'text/calendar;charset=utf-8' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = (props.plan?.titel || 'Plan') + '.ics'
    a.click()
    URL.revokeObjectURL(a.href)
}
</script>

<style scoped>
.pr-ansicht-druckleiste,
.pr-druck-leiste {
  display: flex; align-items: center; justify-content: space-between; gap: 12px;
  margin-bottom: 12px; padding: 8px 12px; border-radius: 10px;
  background: color-mix(in oklch, var(--dk-info) 8%, var(--dk-surface));
  border: 1px solid color-mix(in oklch, var(--dk-info) 25%, var(--dk-surface));
}
.pr-ansicht-druckhinweis { font-size: 0.8rem; color: var(--dk-text-muted); }
.pr-ansicht-hinweis { display: flex; align-items: center; gap: 12px; font-size: 0.86rem; color: var(--dk-text-muted); padding: 10px 0; }
.pr-ansicht--druck { background: var(--dk-surface); }
/* UXP-R7: Die Druckueberschrift erscheint nur auf dem Papier — am Bildschirm
   traegt die Plan-Kopfzeile bereits Titel und Zeitraum. */
.pr-druck-kopf { display: none; }
@media print {
  .pr-ansicht-druckleiste, .pr-druck-leiste { display: none; }
  /* Nachtrag R-P1-12: Auch im gescopten Block der Ansicht die hellen
     Papierwerte erzwingen — gescopte Regeln schlagen globale. */
  :global([data-theme="dark"]) .pr-ansicht--druck {
    background: var(--druck-bg) !important;
    color: var(--druck-text) !important;
  }
  .pr-druck-kopf {
    display: block; margin-bottom: 10mm; padding-bottom: 3mm;
    border-bottom: 1px solid var(--dk-border-strong);
  }
  .pr-druck-kopf-titel { display: block; font-size: 15pt; font-weight: 700; color: var(--dk-text); }
  .pr-druck-kopf-zeitraum { display: block; font-size: 10pt; color: var(--dk-text-muted); margin-top: 1mm; }
  .pr-tabelle, .pr-raster-tabelle, .pr-kalender { font-size: 9pt; }
  .pr-tabelle th, .pr-tabelle td,
  .pr-raster-tabelle th, .pr-raster-tabelle td { padding: 4px 6px; }
}
</style>
