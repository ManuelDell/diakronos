<template>
  <!-- UX2e · Objekt-Aktionen am Objekt (Entwurf B1, Prinzip N6/K4).
       Ein „⋯" als AUSLÖSER; das Menü selbst liegt in einem Teleport, damit
       es nicht von Tabellen-Überlauf oder Kartenhöhe abgeschnitten wird. -->
  <button
    v-if="!ohneAusloeser"
    ref="ausloeser"
    type="button"
    class="dk-ui-aktionen-ausloeser"
    :class="{ 'is-offen': offen }"
    :aria-label="ausloeserLabel"
    aria-haspopup="menu"
    :aria-expanded="offen ? 'true' : 'false'"
    :disabled="disabled || !eintraege.length"
    @click.stop="umschalten($event)"
    @keydown="amAusloeser"
    @contextmenu.stop.prevent="nichtDoppelt"
  >
    <span class="dk-ui-aktionen-punkte" aria-hidden="true">⋯</span>
  </button>

  <Teleport to="body">
    <div
      v-if="offen"
      ref="ebene"
      class="dk-ui-aktionen-ebene"
      :data-fuer="ebeneKennung"
    >
      <div
        ref="menue"
        class="dk-ui-aktionen-menue"
        :class="{ 'is-links': !rechts }"
        role="menu"
        :aria-label="menueLabel || ausloeserLabel"
        tabindex="-1"
        :style="lage"
        @keydown="imMenue"
        @contextmenu.prevent
      >
        <button
          v-for="(eintrag, i) in sichtbar"
          :key="eintrag.key || i"
          :ref="el => (eintragEls[i] = el)"
          type="button"
          role="menuitem"
          class="dk-ui-aktionen-eintrag"
          :class="{ 'is-gefahr': eintrag.gefahr, 'is-getrennt': eintrag.getrennt }"
          :tabindex="i === aktiv ? 0 : -1"
          :aria-disabled="eintrag.disabled ? 'true' : undefined"
          :disabled="eintrag.disabled === true"
          @click.stop="waehlen(i)"
          @mouseenter="aktiv = i"
        >
          <span class="dk-ui-aktionen-symbol" aria-hidden="true">
            <DkSymbol :name="eintrag.icon" />
          </span>
          <span class="dk-ui-aktionen-text">{{ eintrag.label }}</span>
        </button>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
/**
 * DkAktionen — das Aktionsmenü „⋯" an einem Eintrag (UX2e).
 *
 * Entwurf B1 (verbindlich): Knopf „⋯" mit aria-label, Menü mit 5–8
 * Einträgen, Symbole links auf der Textlinie, gefährliche Aktion abgesetzt
 * am Ende in Rot, Tastatur (Menü-Taste / Umschalt+F10, Pfeile, Pos1/Ende,
 * Buchstabensprung, ↵, Esc) und Rechtsklick auf die Zeile öffnet dasselbe
 * Menü.
 *
 * Der Auslöser steht IN der Zeile; weil die Zeile selbst ein Link oder Knopf
 * ist, fängt der Knopf seinen Klick ab (@click.stop). Die Zeile bekommt vom
 * Seiten-Test dieselbe Tastaturbedienung über `oeffnenFuerZeile` — zur Laufzeit
 * wird das Menü per Rechtsklick (Zeilen-@contextmenu) oder über den ⋯-Knopf
 * geöffnet; für Tastatur und Vorlesehilfe bleibt der ⋯-Knopf über den
 * Tab-Strom der Zeile erreichbar.
 *
 * eintraege: [{ key, label, icon, aktion?, gefahr?, disabled?, getrennt? }]
 *   icon     Name aus <DkSymbol> (siehe components/ui/DkSymbol.vue)
 *   gefahr   letzte Gruppe: getrennt, rot („Löschen", „Entfernen", …)
 *   aktion   Funktion; fehlt sie, wird das Ereignis `aktion` gemeldet
 *
 * Nur Tokens, keine festen Farben (Wächter-Test).
 */
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import DkSymbol from './DkSymbol.vue'
import {
  eintraegeNormalisieren, istKontextmenueTaste, springeZuBuchstabe, tasteImMenue,
} from './aktionen.mjs'

const props = defineProps({
  eintraege: { type: Array, default: () => [] },
  /** Beschriftung des Auslösers, z. B. „Aktionen für Hanna Voss". */
  label: { type: String, default: 'Aktionen' },
  /** Name des Menüs für Vorlesehilfen (fällt auf `label` zurück). */
  menueLabel: { type: String, default: '' },
  disabled: Boolean,
  /**
   * UX2e2: KEIN eigenes „⋯" — das Menü wird von außen an einen Anker
   * geöffnet (Terminliste: die Zeile selbst trägt den Knopf). Ohne dieses
   * Merkmal stünde ein zweites, freistehendes „⋯" ohne Bezug in der Seite.
   */
  ohneAusloeser: Boolean,
  /**
   * UX2e2: Kennung der Menü-Ebene (`data-fuer="…"` im Teleport). Mehrere
   * Menüs können gleichzeitig im DOM stehen — die Kalender-Terminliste hat
   * eins, das am Zeilenknopf hängt; ohne Kennung ließe sich im Browser und
   * in Tests nicht sagen, WELCHES Menü offen ist.
   */
  kennung: { type: String, default: 'aktionen' },
})

const emit = defineEmits(['aktion', 'offenGeaendert'])

const ausloeser = ref(null)
const ebene = ref(null)
const menue = ref(null)
const eintragEls = ref([])
const offen = ref(false)
const aktiv = ref(0)
const lage = ref({})
const rechts = ref(false)
/** Element, das den Fokus beim Schließen zurückbekommt (Zeile oder ⋯). */
let fokusZurueck = null
/** Gemessenes Ankerrechteck des laufenden Menüs (Zeile, ⋯ oder extern). */
let anker = null

const ausloeserLabel = computed(() => (props.label || 'Aktionen'))
const ebeneKennung = computed(() => props.kennung || 'aktionen')
const sichtbar = computed(() => {
  const liste = eintraegeNormalisieren(props.eintraege)
  // Die TRENNLINIE (B1: „Der Abstand trennt, keine zweite Linie") wird an
  // der ersten gefährlichen Aktion gesetzt, nicht am Eintrag selbst — so
  // bleibt es bei EINER Markierung, egal wie viele gefährliche folgen.
  let gefahrGesehen = false
  return liste.map((e) => {
    let getrennt = !!e.getrennt
    if (e.gefahr && !gefahrGesehen) { getrennt = true; gefahrGesehen = true }
    return { ...e, getrennt }
  })
})

/** Position des Menüs an einem Ankerrechteck festmachen. */
function oeffnenBei(rechteck, zurueckZiel, startIndex = 0) {
  fokusZurueck = zurueckZiel || document.activeElement
  // UX2e2: Den Anker für die Lagemessung MERKEN. Beim Nachmessen (Schrift
  // nachgeladen, Menü noch ohne Höhe) und bei der Größenänderung wurde
  // vorher `ankerRechteck()` am (hier gar nicht vorhandenen oder falschen)
  // Auslöser gemessen — das Menü sprang dann an die falsche Stelle.
  anker = rechteck || null
  aktiv.value = startIndex
  offen.value = true
  emit('offenGeaendert', true)
  lageWaehlen(rechteck)
  nextTick(() => {
    focusAktiv()
  })
}

/**
 * Lage: unter dem Auslöser, rechtsbündig, so weit wie nötig im Fenster
 * gehalten (Handy 390 px: das Menü darf nie seitlich hinauslaufen). Gemessen
 * wird erst NACH dem Einbau (das Menü kennt seine Höhe dann selbst).
 */
function lageWaehlen(rechteck) {
  if (!rechteck) return
  const breite = menue.value?.offsetWidth || 248
  const hoehe = menue.value?.offsetHeight || 0
  const rand = 8
  const platzUnten = window.innerHeight - rechteck.bottom
  const nachOben = platzUnten < hoehe + rand && rechteck.top > platzUnten
  const links = Math.min(
    Math.max(rand, rechteck.right - breite),
    Math.max(rand, window.innerWidth - breite - rand),
  )
  const oben = nachOben
    ? Math.max(rand, rechteck.top - hoehe - 4)
    : Math.min(rechteck.bottom + 4, Math.max(rand, window.innerHeight - hoehe - rand))
  rechts.value = rechteck.right - breite >= rand
  lage.value = { left: `${Math.round(links)}px`, top: `${Math.round(oben)}px` }
}

function focusAktiv() {
  const el = eintragEls.value[aktiv.value]
  if (el && typeof el.focus === 'function') el.focus()
  else menue.value?.focus?.()
}

function umschalten(ereignis) {
  if (offen.value) { schliessen(); return }
  const el = ereignis?.currentTarget || ausloeser.value
  oeffnenBei(el?.getBoundingClientRect(), el)
}

function nichtDoppelt(ereignis) {
  // Der Rechtsklick auf den ⋯ gehört der Zeile (die das Menü ohnehin
  // öffnet) — hier nur unterbinden, dass das Browser-Menü erscheint.
  ereignis?.preventDefault?.()
}

/** Tastatur am Auslöser: Menü-Taste / Umschalt+F10 öffnet, ↓ öffnet am Anfang. */
function amAusloeser(ereignis) {
  const oeffnend = istKontextmenueTaste(ereignis)
    || ereignis.key === 'ArrowDown' || ereignis.key === 'Enter' || ereignis.key === ' '
  if (!oeffnend) return
  // UX2e2 (Punkt 3): Der Knopf ist ein echter <button> — ohne preventDefault
  // löste Enter/Space zusätzlich den Klick aus und das Menü öffnete doppelt
  // (bzw. schloss sofort wieder). Für ALLE öffnenden Tasten unterbinden.
  ereignis.preventDefault()
  const el = ausloeser.value
  oeffnenBei(el?.getBoundingClientRect(), el)
}

/**
 * Rechtsklick oder Menü-Taste auf der ZEILE öffnet dasselbe Menü.
 * Die Seite bindet dazu @contextmenu.prevent an die Zeile und reicht
 * das Ereignis hierher; `ankerEl` ist das Ankerelement (Zeile oder der
 * „⋯"-Knopf einer Terminzeile).
 *
 * UX2e2: Das gemessene Rechteck wird an `oeffnenBei` WEITERGEGEBEN und dort
 * gemerkt — vorher wurde der Anker nur zum Öffnen benutzt und die zweite
 * Messung (nach dem Einbau, wenn die Höhe bekannt ist) lief am ⋯-Knopf des
 * Bauteils statt an der Zeile: das Menü stand dann nicht an der Zeile.
 */
function oeffnenFuerZeile(ereignis, ankerEl, startIndex = 0) {
  if (props.disabled || !sichtbar.value.length) return
  const ziel = ankerEl || ereignis?.currentTarget || ereignis?.target || null
  const rechteck = ziel && typeof ziel.getBoundingClientRect === 'function'
    ? ziel.getBoundingClientRect()
    : null
  oeffnenBei(rechteck, ziel, startIndex)
}

function imMenue(ereignis) {
  const folge = tasteImMenue(ereignis, { index: aktiv.value, anzahl: sichtbar.value.length })
  if (!folge) {
    // Buchstabensprung (K3: Wiedererkennen statt Suchen).
    if (ereignis.key?.length === 1 && !ereignis.ctrlKey && !ereignis.metaKey && !ereignis.altKey) {
      const neu = springeZuBuchstabe(sichtbar.value, aktiv.value, ereignis.key)
      if (neu !== aktiv.value) {
        ereignis.preventDefault()
        aktiv.value = neu
        focusAktiv()
      }
    }
    return
  }
  ereignis.preventDefault()
  ereignis.stopPropagation()
  if (folge.aktion === 'schliessen') schliessen()
  else if (folge.aktion === 'fokus') { aktiv.value = folge.index; focusAktiv() }
  else if (folge.aktion === 'waehlen') waehlen(folge.index)
}

function waehlen(index) {
  const eintrag = sichtbar.value[index]
  if (!eintrag || eintrag.disabled) return
  schliessen()
  if (typeof eintrag.aktion === 'function') eintrag.aktion(eintrag)
  else emit('aktion', { eintrag, index })
}

/**
 * Schließen und Fokus zurückgeben. `zurueck` ist standardmäßig der Auslöser
 * bzw. die Zeile, von der geöffnet wurde — Prinzip S5: Esc schließt, und man
 * steht danach wieder dort, wo man war.
 */
function schliessen({ fokus = true } = {}) {
  if (!offen.value) return
  offen.value = false
  // UX2e2: Den Eigentümer (Seite mit eigenem Zeilenknopf) SOFORT und
  // ausdrücklich benachrichtigen. Ein Watch auf `offen` in der Seite blieb in
  // der Terminliste wirkungslos (im Browser gemessen: „true" blieb nach Esc
  // stehen) — das Ereignis ist eindeutig und unabhängig von der Reihenfolge
  // der Watches. `false` = geschlossen, `true` = offen.
  emit('offenGeaendert', false)
  const ziel = fokusZurueck
  fokusZurueck = null
  if (fokus && ziel && typeof ziel.focus === 'function' && ziel.isConnected !== false) {
    ziel.focus()
  }
}

/** Klick daneben, Größenänderung, Scrollen: Menü zu (ohne Fokus umzulenken). */
function ausserhalb(ereignis) {
  if (!offen.value) return
  if (menue.value?.contains(ereignis.target) || ausloeser.value?.contains(ereignis.target)) return
  if (ebene.value?.contains(ereignis.target)) return
  schliessen({ fokus: false })
}

function onScroll() {
  if (offen.value) schliessen({ fokus: false })
}

const RESIZE_OPTIONEN = { passive: true }
const SCROLL_OPTIONEN = { passive: true, capture: true }

watch(offen, (ist) => {
  if (typeof document === 'undefined') return
  if (ist) {
    document.addEventListener('mousedown', ausserhalb, true)
    document.addEventListener('keydown', escGlobal, true)
    window.addEventListener('resize', onScroll, RESIZE_OPTIONEN)
    window.addEventListener('scroll', onScroll, SCROLL_OPTIONEN)
    // Zweite Messung, wenn das Menü seine Höhe kennt (Lage bleibt am Anker).
    nextTick(() => lageWaehlen(anker))
  } else {
    document.removeEventListener('mousedown', ausserhalb, true)
    document.removeEventListener('keydown', escGlobal, true)
    // UX2e2 (Punkt 4): identische Optionen wie beim Anmelden — `capture`
    // entscheidet über den Listener-Schlüssel, sonst bleibt der Eintrag
    // stehen (Leck über Öffnen/Schließen hinweg).
    window.removeEventListener('resize', onScroll, RESIZE_OPTIONEN)
    window.removeEventListener('scroll', onScroll, SCROLL_OPTIONEN)
  }
})

/**
 * Esc schließt das Menü AUCH dann, wenn der Fokus gerade nicht im Menü steht
 * (z. B. nach einem Klick in die Seite). Das Menü ist keine modale Ebene —
 * es legt keinen Hintergrund über die Seite —, deshalb genügt Esc.
 */
function escGlobal(ereignis) {
  if (ereignis.key !== 'Escape') return
  ereignis.stopPropagation()
  schliessen()
}

onBeforeUnmount(() => {
  if (typeof document === 'undefined') return
  document.removeEventListener('mousedown', ausserhalb, true)
  document.removeEventListener('keydown', escGlobal, true)
  window.removeEventListener('resize', onScroll, RESIZE_OPTIONEN)
  window.removeEventListener('scroll', onScroll, SCROLL_OPTIONEN)
})

defineExpose({
  ausloeser,
  /** Rechtsklick/Menü-Taste auf der ZEILE öffnet dasselbe Menü. */
  oeffnenFuerZeile,
  /** Öffnen an einem frei gelieferten Element (Terminzeile: der ⋯-Knopf). */
  oeffnenAn: (el, startIndex = 0) => oeffnenFuerZeile(null, el, startIndex),
  schliessen,
  offen,
})
</script>

<style scoped>
/* Auslöser „⋯": quadratische Trefferfläche in Zeilenhöhe, ohne Rahmen. */
.dk-ui-aktionen-ausloeser {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: var(--control-h);
  height: var(--control-h);
  padding: 0;
  border: 0;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--subtle);
  font: inherit;
  cursor: pointer;
}
.dk-ui-aktionen-ausloeser:hover:not(:disabled),
.dk-ui-aktionen-ausloeser.is-offen {
  background: var(--surface-hover);
  color: var(--text);
}
.dk-ui-aktionen-ausloeser:focus-visible {
  outline: 2px solid var(--focus-ring);
  outline-offset: -2px;
}
.dk-ui-aktionen-ausloeser:disabled { cursor: default; opacity: .5; }
.dk-ui-aktionen-punkte {
  font-size: var(--fs-h3);
  font-weight: var(--fw-mittel);
  line-height: 1;
  letter-spacing: .08em;
  /* Optische Mitte: die drei Punkte stehen im Zeichen nicht mittig, deshalb
     gleicht ein kleiner Versatz nach oben aus (Auflage: Symbole auf der
     Textlinie). */
  transform: translateY(-3px);
}

/* Der Menü-Sockel ist nur ein Positionsanker; er fängt keine Klicks ab. */
.dk-ui-aktionen-ebene {
  position: fixed;
  inset: 0;
  z-index: var(--z-popover, 1200);
  pointer-events: none;
}

/* 5–8 Einträge, Karte ohne Rahmen, sanfter Schatten (Ä2). */
.dk-ui-aktionen-menue {
  position: absolute;
  min-width: 232px;
  max-width: min(320px, calc(100vw - 16px));
  padding: var(--sp-2) 0;
  margin: 0;
  background: var(--surface);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-lg);
  pointer-events: auto;
  overflow-y: auto;
  max-height: min(70vh, 480px);
}

.dk-ui-aktionen-eintrag {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  width: 100%;
  min-height: var(--control-h);
  padding: 0 var(--sp-4);
  border: 0;
  background: transparent;
  color: var(--text);
  font: inherit;
  font-size: var(--fs-h4);
  line-height: 1.4;
  text-align: left;
  cursor: pointer;
}
.dk-ui-aktionen-eintrag:hover:not(:disabled),
.dk-ui-aktionen-eintrag:focus-visible {
  background: var(--surface-hover);
  outline: none;
}
.dk-ui-aktionen-eintrag:focus-visible {
  outline: 2px solid var(--focus-ring);
  outline-offset: -2px;
}
.dk-ui-aktionen-eintrag:disabled {
  color: var(--subtle);
  cursor: default;
}

/* Symbol links, feste Größe je Schriftstufe, optisch auf der Textlinie
   (Auflage Manuel 2026-11-04: „Symbole stehen exakt auf der Textlinie"). */
.dk-ui-aktionen-symbol {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: none;
  width: var(--fs-h3);
  height: var(--fs-h3);
  color: var(--muted);
}
.dk-ui-aktionen-text {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* Gefährliches: abgesetzt am Ende, in Rot (B1). Getrennt wird durch Abstand
   UND eine dünne Linie in Zeilenfarbe — das ist die eine Markierung, die
   B1 ausdrücklich vorsieht („Löschen steht allein am Ende"). */
.dk-ui-aktionen-eintrag.is-gefahr { color: var(--err); }
.dk-ui-aktionen-eintrag.is-gefahr .dk-ui-aktionen-symbol { color: var(--err); }
.dk-ui-aktionen-eintrag.is-getrennt {
  margin-top: var(--sp-2);
  padding-top: var(--sp-2);
  border-top: var(--rahmen-breite) solid var(--line);
  min-height: calc(var(--control-h) + var(--sp-2));
}
.dk-ui-aktionen-eintrag.is-gefahr:hover:not(:disabled),
.dk-ui-aktionen-eintrag.is-gefahr:focus-visible {
  background: var(--err-soft);
}

/* Grober Zeiger (Handy/iPad): Trefferfläche ≥ 44 px (K4). */
@media (pointer: coarse) {
  .dk-ui-aktionen-ausloeser {
    width: 44px;
    height: 44px;
  }
  .dk-ui-aktionen-eintrag { min-height: 44px; }
  .dk-ui-aktionen-eintrag.is-getrennt { min-height: 52px; }
}
</style>
