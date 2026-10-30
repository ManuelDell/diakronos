<template>
  <!-- Bereichsliste (UX-A2a): links neben dem Inhalt; am Handy eine
       waagerechte Reiterzeile. Es ist eine NAVIGATION, kein Umschalter —
       deshalb Links in einer Liste (Navigation-Muster nach WAI-ARIA), nicht
       role="tab"/"tablist": gewechselt wird mit Enter, die Pfeiltasten
       bewegen nur den Fokus. Der aktive Eintrag trägt aria-current="page". -->
  <nav class="dk-ui-bereichsliste" :aria-label="ariaLabel || undefined">
    <ul class="dk-ui-bz-liste">
      <li v-for="o in optionen" :key="wert(o)" class="dk-ui-bz-punkt" :class="klassen(o)">
        <a
          class="dk-ui-bz"
          :class="klassen(o)"
          :href="ziel(o)"
          :data-wert="wert(o)"
          :aria-current="istAktiv(o) ? 'page' : undefined"
          :tabindex="tabStopp(wert(o))"
          :ref="el => merkeEintrag(wert(o), el)"
          @keydown="pfeiltaste($event)"
        >
          <span class="dk-ui-bz-name">{{ label(o) }}</span>
          <span v-if="zahl(o) !== null" class="dk-ui-bz-zahl">{{ zahl(o) }}</span>
        </a>
        <!-- Unterbereiche: eingerückte Einträge DERSELBEN Liste (keine zweite
             Navigationsebene, keine verschachtelte Rolle). Der Oberpunkt
             beschreibt sie über aria-describedby; den Namen der Gruppe liefert
             ein eigener, unsichtbarer Text (ARIA erlaubt an aria-describedby
             nur IDs, keine wörtlichen Texte).
             UX-A2a2: Beide IDs sind DIESELBE (`unterId`), und der unsichtbare
             Text steht NUR beim Eintrag mit Unterpunkten — sonst hinge an
             jedem Punkt eine Beschreibung, die auf nichts zeigt. -->
        <span v-if="unterpunkte(o).length" :id="unterId(o)" class="dk-ui-bz-sr">Unterbereiche von {{ label(o) }}</span>
        <ul
          v-if="unterpunkte(o).length"
          class="dk-ui-bz-unter"
          :aria-describedby="unterId(o)"
        >
          <li v-for="u in unterpunkte(o)" :key="wert(u)">
            <a
              :class="['dk-ui-bz dk-ui-bz--unter', istAktiv(u) ? 'is-aktiv' : '']"
              :href="ziel(u)"
              :data-wert="wert(u)"
              :aria-current="istAktiv(u) ? 'page' : undefined"
              :tabindex="tabStopp(wert(u))"
              :ref="el => merkeEintrag(wert(u), el)"
              @keydown="pfeiltaste($event)"
            >
              <span class="dk-ui-bz-name">{{ label(u) }}</span>
              <span v-if="zahl(u) !== null" class="dk-ui-bz-zahl">{{ zahl(u) }}</span>
            </a>
          </li>
        </ul>
      </li>
    </ul>
  </nav>
</template>

<script setup>
/**
 * DkBereichsliste — feste Navigationsliste eines Bereichs (UX-A2a).
 *
 * Ersetzt den Reiterstreifen über dem Inhalt (DkTabs): die Einträge stehen
 * links neben dem Inhalt (Desktop) bzw. als waagerechte Reiterzeile darüber
 * (Mobil-Layout, ≤ 720 px — die eine Breitengrenze der App,
 * composables/eingabeart.mjs `MOBIL_GRENZE_PX`; die CSS-Regel steht unten). Unterbereiche eines Eintrags sind eigene, eingerückte
 * Einträge derselben Liste — es gibt keine zweite Reiterzeile mehr.
 *
 * Es ist eine NAVIGATION (Links), kein Umschalter (Operator-Review Punkt 1):
 *   <nav aria-label="…"> → Liste → Links, der aktive Link aria-current="page".
 *   KEIN role="tab"/"tablist"/"aria-controls"/"aria-orientation" — ein Satz
 *   Links ist keine Reiterliste, und `aria-orientation` gilt nur für
 *   Reiter-/Werkzeugleisten (bei einer Navigation ist es ungültig).
 *
 * Optionen wie bei DkTabs/DkSelect: Skalar oder
 *   { value, label, href?, zahl?, unterpunkte? }
 * `value` ist die gewählte Kennung (hier die Seite), `href` das Ziel.
 * `zahl` erscheint nur, wenn sie eine Zahl ist (null/'' = keine Kennzahl) —
 *          nie eine erfundene 0 (dieselbe Regel wie in der Seitenleiste).
 * Nur Tokens, keine festen Farben.
 */
import { computed, nextTick, onMounted, ref, watch } from 'vue'

const props = defineProps({
  modelValue: { default: '' },
  options: { type: Array, default: () => [] },
  ariaLabel: { type: String, default: '' },
})

const optionen = computed(() => props.options || [])

function wert(o) { return (o !== null && typeof o === 'object') ? (o.value ?? o.href ?? '') : o }
function label(o) { return (o !== null && typeof o === 'object') ? (o.label ?? o.value) : o }
/** Ziel der Verknüpfung: `href`, sonst der Wert selbst. */
function ziel(o) { return (o !== null && typeof o === 'object') ? (o.href ?? o.value) : o }
function unterpunkte(o) {
  const u = (o !== null && typeof o === 'object' && Array.isArray(o.unterpunkte)) ? o.unterpunkte : []
  return u
}
/** Kennzahl nur als echte Zahl — kein „0“ und kein leerer Punkt. */
function zahl(o) {
  const z = (o !== null && typeof o === 'object') ? o.zahl : null
  if (z === null || z === undefined || z === '') return null
  const n = Number(z)
  return Number.isFinite(n) ? n : null
}
function istAktiv(o) { return String(wert(o)) === String(props.modelValue) }
/**
 * Kennung für aria-describedby des Unterpunkts-Blocks. Keine
 * Navigations-Semantik, nur ein Verweis, damit der Oberpunkt die Gruppe
 * benennt.
 */
function unterId(o) {
  return 'unter-' + String(wert(o)).replace(/[^a-zA-Z0-9]+/g, '-').replace(/^-+|-+$/g, '')
}
/**
 * Klassen des Punktes. Bewusst einfache STRINGS statt eines Objekts: im
 * laufenden Container kam `:class="{ 'is-aktiv': … }"` nicht am DOM an, obwohl
 * die Markierung stimmte (nachgestellt mit demselben DOM, kein aktiver
 * Eintrag sichtbar). Zwei feste Klassen lassen nichts zu raten.
 */
function klassen(o) {
  return [istAktiv(o) ? 'is-aktiv' : '', unterpunkte(o).length ? 'hat-unterpunkte' : '']
    .filter(Boolean).join(' ')
}

// ── Roving tabindex ────────────────────────────────────────────────────────
// ALLE Einträge liegen in EINER Liste, also gibt es genau EINEN Tabstopp. Er
// steht am gewählten Eintrag; nach den Pfeiltasten am zuletzt fokussierten
// (damit Tab/Shift+Tab dort weitergehen, wo man ist). Kennt die Liste den
// gewählten Wert nicht (z. B. Fremdadresse), liegt der Tabstopp auf dem
// ersten Eintrag — es gibt immer genau einen.
const fokusWert = ref(null)
const eintragEls = new Map()

function merkeEintrag(w, el) {
  if (!el) { eintragEls.delete(String(w)); return }
  eintragEls.set(String(w), el)
}

watch(() => props.modelValue, (neu) => {
  if (neu !== undefined) fokusWert.value = null
})

const alleWerte = computed(() => {
  const liste = []
  for (const o of optionen.value) {
    liste.push(wert(o))
    for (const u of unterpunkte(o)) liste.push(wert(u))
  }
  return liste
})

function tabStopp(kandidat) {
  const gewaehlt = fokusWert.value && alleWerte.value.includes(fokusWert.value)
    ? fokusWert.value
    : (alleWerte.value.includes(props.modelValue) ? props.modelValue : alleWerte.value[0])
  return String(kandidat) === String(gewaehlt) ? 0 : -1
}

/**
 * Pfeiltasten: ←/→ bzw. ↑/↓ durch die sichtbaren Einträge der GANZEN Liste
 * (Ober- und Unterpunkte in Anzeigereihenfolge). Home/End springen an die
 * Enden. Der Fokus wandert, gewechselt wird mit Enter (Link).
 */
function pfeiltaste(event) {
  const tasten = ['ArrowRight', 'ArrowLeft', 'ArrowDown', 'ArrowUp', 'Home', 'End']
  if (!tasten.includes(event.key)) return
  const nav = event.currentTarget.closest('.dk-ui-bereichsliste')
  if (!nav) return
  const eintraege = [...nav.querySelectorAll('a.dk-ui-bz')]
  const jetzt = eintraege.indexOf(event.currentTarget)
  if (jetzt < 0) return
  event.preventDefault()
  let neu = jetzt
  if (event.key === 'ArrowRight' || event.key === 'ArrowDown') neu = (jetzt + 1) % eintraege.length
  else if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') neu = (jetzt - 1 + eintraege.length) % eintraege.length
  else if (event.key === 'Home') neu = 0
  else if (event.key === 'End') neu = eintraege.length - 1
  // Der Tabstopp wandert über den Zustand (nicht per DOM-Schreibzugriff) —
  // Vue setzt `tabindex` beim nächsten Rendern nach.
  fokusWert.value = eintraege[neu].dataset.wert
  eintraege[neu].focus()
  eintraege[neu].scrollIntoView({ inline: 'nearest', block: 'nearest' })
}

/**
 * Am Handy ist die Liste eine waagerechte, scrollbare Reiterzeile. Damit der
 * aktive Eintrag nicht außerhalb des sichtbaren Streifens liegt (z. B. beim
 * Aufruf einer Adresse mit „Import“ ganz rechts), wird er beim Aufbau und bei
 * jedem Wechsel ins Bild gescrollt — `inline: 'nearest'` rührt die Seite
 * selbst nicht an. Am Desktop ist nichts zu scrollen; der Aufruf schadet dort
 * nicht (nächstgelegene Position ist die aktuelle).
 */
function aktivenEintragZeigen() {
  const w = String(props.modelValue ?? '')
  const el = eintragEls.get(w)
  if (!el || typeof el.scrollIntoView !== 'function') return
  el.scrollIntoView({ inline: 'nearest', block: 'nearest' })
}

onMounted(() => { nextTick(aktivenEintragZeigen) })
watch(() => props.modelValue, () => { nextTick(aktivenEintragZeigen) })
</script>

<style scoped>
.dk-ui-bereichsliste { min-width: 0; }
.dk-ui-bz-liste {
  display: flex;
  flex-direction: column;
  gap: 2px;
  margin: 0;
  padding: 0;
  list-style: none;
}
.dk-ui-bz-punkt { margin: 0; padding: 0; list-style: none; }
.dk-ui-bz {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--sp-2);
  padding: 8px 12px;
  border: 1px solid transparent;
  border-radius: var(--radius);
  color: var(--muted);
  font: inherit;
  font-weight: 550;
  text-decoration: none;
  transition: background var(--dk-fast), color var(--dk-fast), border-color var(--dk-fast);
}
.dk-ui-bz:hover { background: var(--surface-2); color: var(--text); }
/* Aktiver Eintrag: Fläche aus dem Theme, Schrift aus dem Akzent (DEV-4-Regel:
   im Dunkelmodus ist --primary WEISS und damit nicht unterscheidbar). */
.dk-ui-bz.is-aktiv {
  background: var(--surface-2);
  color: var(--text);
  font-weight: 650;
  border-color: var(--line);
  box-shadow: inset 3px 0 0 var(--accent);
}
.dk-ui-bz-name { min-width: 0; overflow: hidden; text-overflow: ellipsis; }
.dk-ui-bz-zahl {
  flex-shrink: 0;
  min-width: 20px;
  padding: 1px 6px;
  border-radius: var(--badge-r);
  background: var(--accent-soft);
  color: var(--badge-ink-warn);
  font-size: var(--fs-sm);
  font-weight: 600;
  text-align: center;
}
/* Unterbereiche: eigene, eingerückte Einträge derselben Liste. */
.dk-ui-bz-unter {
  margin: 2px 0 4px;
  padding: 0 0 0 var(--sp-4);
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 2px;
  border-left: 1px solid var(--line);
  margin-left: var(--sp-3);
}
.dk-ui-bz--unter { padding: 6px 10px; font-weight: 500; font-size: var(--fs-sm); }
.dk-ui-bz--unter.is-aktiv { box-shadow: inset 3px 0 0 var(--accent); }
.dk-ui-bz:focus-visible { outline: 2px solid var(--focus-ring); outline-offset: 1px; }
/* Nur für Vorlesehilfen — der Name der Unterpunkt-Gruppe. */
.dk-ui-bz-sr {
  position: absolute;
  width: 1px;
  height: 1px;
  margin: -1px;
  padding: 0;
  overflow: hidden;
  clip-path: inset(50%);
  white-space: nowrap;
  border: 0;
}

/* Handy und schmale Fenster: waagerechte Reiterzeile über dem Inhalt. Die
   Unterpunkte werden eigene Einträge derselben Zeile (ohne Einrückung) —
   eine zweite Reiterzeile gibt es nicht. */
@media (max-width: 720px) {
  .dk-ui-bz-liste {
    flex-direction: row;
    align-items: stretch;
    gap: var(--sp-1);
    overflow-x: auto;
    scroll-behavior: smooth;
    border-bottom: 1px solid var(--line);
    scrollbar-width: none;
  }
  .dk-ui-bz-liste::-webkit-scrollbar { display: none; }
  .dk-ui-bz-punkt { display: contents; }
  .dk-ui-bz-unter {
    display: contents;
    margin: 0;
    padding: 0;
    border: 0;
  }
  .dk-ui-bz {
    height: 100%;
    padding: 9px 12px;
    border: 0;
    border-bottom: 2px solid transparent;
    border-radius: 0;
    white-space: nowrap;
    box-shadow: none;
  }
  .dk-ui-bz.is-aktiv {
    background: none;
    border-bottom-color: var(--accent);
    box-shadow: none;
  }
  .dk-ui-bz--unter { font-size: inherit; font-weight: 550; }
}
</style>
