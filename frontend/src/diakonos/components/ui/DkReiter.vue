<template>
  <!-- UX3j (Entwurf A3, Muster A4/UX3i): EINE Reiterzeile oben — unterstrichen,
       mit Kennzahl am Eintrag. Einträge mit `href` sind LINKS (eigene
       Adresse, Lesezeichen, Zurück-Taste); ein Eintrag OHNE `href` ist ein
       Umschalter derselben Seite und wird als Link mit `role="button"`
       gezeichnet (gleiche Zeile, gleiche Klickfläche, EIN Aussehen). Der
       aktive Eintrag trägt IMMER die Akzentfarbe UND den Unterstrich —
       Farbe ist nie der einzige Träger (Ä4). -->
  <nav
    v-if="optionen.length"
    class="dk-ui-reiter"
    :class="{ 'is-klein': klein, 'is-segment': segment }"
    :aria-label="ariaLabel || undefined"
  >
    <template v-for="o in optionen" :key="wert(o)">
      <a
        v-if="href(o)"
        class="dk-ui-reiter-punkt"
        :class="{ 'is-active': wert(o) === modelValue }"
        :href="href(o)"
        :aria-current="wert(o) === modelValue ? 'page' : undefined"
        :data-reiter="wert(o)"
      >
        <span class="dk-ui-reiter-name">{{ label(o) }}</span>
        <span v-if="zahl(o) !== null" class="dk-ui-reiter-zahl">{{ zahl(o) }}</span>
      </a>
      <a
        v-else
        class="dk-ui-reiter-punkt"
        :class="{ 'is-active': wert(o) === modelValue }"
        role="button"
        tabindex="0"
        :aria-pressed="wert(o) === modelValue ? 'true' : 'false'"
        :data-reiter="wert(o)"
        @click.prevent="$emit('update:modelValue', wert(o))"
        @keydown.enter.prevent="$emit('update:modelValue', wert(o))"
        @keydown.space.prevent="$emit('update:modelValue', wert(o))"
      >
        <span class="dk-ui-reiter-name">{{ label(o) }}</span>
        <span v-if="zahl(o) !== null" class="dk-ui-reiter-zahl">{{ zahl(o) }}</span>
      </a>
    </template>
  </nav>
</template>

<script setup>
/**
 * DkReiter — die EINE Reiterzeile (Stil A4, UX3j).
 *
 * Warum eine eigene Komponente: Unter „Personen“ stand die Reiterzeile im
 * Reiter „Liste“ als Segmentschalter oben, in „Anfragen“, „Datenschutz“ und
 * „Import“ dagegen als seitliche Liste links (Befund Manuel 08.11.). Mit
 * diesem Baustein zeichnet JEDER Reiter dieselbe Leiste — gleiche Optik,
 * gleiche Höhe, gleiche Position, gleiche Kennzahl.
 *
 * Optionen: `{ value, label, href?, zahl? }` (oder ein Skalar).
 *  • `href` gesetzt → der Eintrag ist ein Link (`aria-current="page"`).
 *  • ohne `href`   → Umschalter derselben Seite (Knopf, `aria-pressed`),
 *                    Wechsel über `update:modelValue`.
 * `zahl` erscheint nur als ECHTE Zahl (kein „0“, kein leerer Punkt).
 * `klein` = zweite Ebene (Unterbereiche) — gleiche Optik, kleinere Schrift.
 *
 * Nur Tokens, keine festen Farben; Klickfläche --control-h (44 px bei
 * Fingerbedienung, K4).
 */
import { computed } from 'vue'

const props = defineProps({
  modelValue: { type: String, default: '' },
  options: { type: Array, default: () => [] },
  ariaLabel: { type: String, default: '' },
  /** Zweite, kleinere Ebene (z. B. Unterbereiche von „Anfragen“). */
  klein: { type: Boolean, default: false },
  /** Optik der Segmentleiste (DkSegment) statt der Unterstrich-Zeile — für
   *  die zweite Ebene, die wie ein Umschalter aussehen soll (Punkt 3 der
   *  Nacharbeit). Die Einträge bleiben LINKS mit eigener Adresse. */
  segment: { type: Boolean, default: false },
})
defineEmits(['update:modelValue'])

const optionen = computed(() => props.options || [])

function wert(o) { return (o !== null && typeof o === 'object') ? o.value : o }
function label(o) { return (o !== null && typeof o === 'object') ? (o.label ?? o.value) : o }
function href(o) { return (o !== null && typeof o === 'object' && o.href) ? o.href : '' }
function zahl(o) {
  if (o === null || typeof o !== 'object') return null
  const z = o.zahl
  if (z === null || z === undefined || z === '') return null
  const n = Number(z)
  // UX3j-Nacharbeit (Punkt 5): „0“ wird NICHT gezeichnet — kein Warnfleck
  // „Anfragen 0“ an einer Stelle, an der nichts zu tun ist.
  return Number.isFinite(n) && n > 0 ? n : null
}
</script>

<style scoped>
.dk-ui-reiter {
  display: flex;
  align-items: stretch;
  gap: var(--sp-1);
  margin: 0 0 var(--sp-3);
  border-bottom: var(--rahmen-breite) solid var(--line);
  /* Am Handy (390) scrollt die Zeile waagerecht statt umzubrechen oder in
     eine Seitenliste zu kippen (A9/A10-Muster, Punkt 5 der Karte). */
  overflow-x: auto;
  scrollbar-width: none;
}
.dk-ui-reiter::-webkit-scrollbar { display: none; }

.dk-ui-reiter-punkt {
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--sp-2);
  min-height: var(--control-h);
  padding: 0 var(--sp-3);
  border: 0;
  border-radius: 0;
  box-shadow: inset 0 calc(-1 * var(--rahmen-breite)) 0 transparent;
  background: none;
  color: var(--muted);
  font: inherit;
  font-size: var(--fs);
  font-weight: var(--fw-mittel);
  text-decoration: none;
  white-space: nowrap;
  cursor: pointer;
  transition: color var(--fast), box-shadow var(--fast);
}
.dk-ui-reiter-punkt:hover { color: var(--text); }
/* Akzentschrift statt --primary: im Dunkelmodus ist --primary WEISS und
   damit von den inaktiven Einträgen nicht zu unterscheiden (DEV-4-Regel,
   gleiche Lösung wie DkTabs und KalenderReiter). */
.dk-ui-reiter-punkt.is-active {
  color: var(--accent);
  box-shadow: inset 0 calc(-2 * var(--rahmen-breite)) 0 var(--accent);
  font-weight: var(--fw-fett);
}
.dk-ui-reiter-punkt:focus-visible { outline: 2px solid var(--focus-ring); outline-offset: -2px; }

.dk-ui-reiter-name { min-width: 0; overflow: hidden; text-overflow: ellipsis; }

/* Kennzahl offener Anfragen: Statusfarbe „zu prüfen“ (dieselben Tokens wie am
   Termin und in der Kalender-Reiterzeile). */
.dk-ui-reiter-zahl {
  flex: 0 0 auto;
  min-width: var(--sp-4);
  padding: 0 var(--sp-1);
  border-radius: var(--badge-r);
  background: var(--warn-soft);
  color: var(--warn);
  font-size: var(--fs-sm);
  font-weight: var(--fw-fett);
  line-height: var(--sp-4);
  text-align: center;
}

/* Zweite Ebene (Unterbereiche): gleiche Optik, kleinere Schrift, weniger
   Höhe als die Hauptzeile — die Hierarchie trägt der Abstand, nicht ein
   zweites Muster (N2: höchstens drei Ebenen). */
.dk-ui-reiter.is-klein { margin-bottom: var(--sp-4); }
.dk-ui-reiter.is-klein .dk-ui-reiter-punkt {
  min-height: var(--control-h);
  font-size: var(--fs-sm);
}

/* Punkt 3 der Nacharbeit: Die zweite Ebene sieht aus wie ein SEGMENTSCHALTER
   (DkSegment) — getönte Fläche, aktiver Eintrag als erhabene Fläche —, bleibt
   aber eine Zeile aus LINKS mit eigener Adresse. */
.dk-ui-reiter.is-segment {
  display: inline-flex;
  gap: var(--sp-1);
  padding: var(--sp-1);
  border-bottom: 0;
  border-radius: var(--radius);
  background: var(--surface-2);
  overflow-x: auto;
}
.dk-ui-reiter.is-segment .dk-ui-reiter-punkt {
  min-height: calc(var(--control-h) - 2 * var(--sp-1));
  padding: 0 var(--sp-3);
  border-radius: var(--radius-sm);
  box-shadow: none;
  font-size: var(--fs-sm);
  font-weight: var(--fw-mittel);
}
.dk-ui-reiter.is-segment .dk-ui-reiter-punkt.is-active {
  background: var(--surface);
  color: var(--text);
  box-shadow: var(--shadow);
  font-weight: var(--fw-fett);
}
.dk-ui-reiter.is-segment .dk-ui-reiter-punkt:focus-visible { outline-offset: 0; }

/* K4: bei Fingerbedienung sind die Einträge 44 px hoch. */
@media (pointer: coarse) {
  .dk-ui-reiter-punkt { min-height: 44px; }
  .dk-ui-reiter.is-segment .dk-ui-reiter-punkt { min-height: 44px; }
}
</style>
