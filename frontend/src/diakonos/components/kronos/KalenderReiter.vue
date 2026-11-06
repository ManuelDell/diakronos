<template>
  <!-- Kalender-Reiter (Entwurf A4, UX3d): EINE Leiste
       „Monat · Woche · Liste · Zu prüfen (n)“. Die drei Ansichten sind ein
       Umschalter innerhalb der Seite (Knöpfe, keine Adressen); „Zu prüfen“ ist
       eine eigene Seite und deshalb ein echter Link. Vorher lagen die
       Ansichten in einem Auswahlfeld und „Zu prüfen“ in einem zweiten Knopf
       rechts — jetzt steht beides an einem Ort. -->
  <nav
    v-if="options && options.length"
    class="kal-reiter"
    :aria-label="ariaLabel || 'Kalender-Ansichten'"
  >
    <template v-for="r in optionen" :key="r.id">
      <a
        v-if="!istAnsicht(r)"
        class="kal-reiter-punkt kal-reiter-punkt--link"
        :class="{ 'is-aktiv': istAktiv(r) }"
        :href="r.href"
        :aria-current="istAktiv(r) ? 'page' : undefined"
        :data-reiter="r.id"
      >
        <span class="kal-reiter-name">{{ r.label }}</span>
        <span v-if="zahl(r) !== null" class="kal-reiter-zahl">{{ zahl(r) }}</span>
      </a>
      <button
        v-else
        type="button"
        class="kal-reiter-punkt"
        :class="{ 'is-aktiv': istAktiv(r) }"
        :aria-pressed="istAktiv(r) ? 'true' : 'false'"
        :data-reiter="r.id"
        @click="$emit('waehlen', r)"
      >
        <span class="kal-reiter-name">{{ r.label }}</span>
        <span v-if="zahl(r) !== null" class="kal-reiter-zahl">{{ zahl(r) }}</span>
      </button>
    </template>
  </nav>
</template>

<script setup>
/**
 * KalenderReiter — die Reiterleiste des Kalenders (UX3d).
 *
 * Die ENTWÜRFE und die Sichtbarkeitsregel stehen in `menue.js`
 * (`kalenderReiter`): „Monat · Woche · Liste“ für alle, „Zu prüfen (n)“ nur
 * für Moderatoren. Diese Komponente zeichnet nur, was sie bekommt — sie
 * entscheidet kein Recht.
 *
 * Aufbau: Links (`<a href>`) für Seiten, Knöpfe für Ansichten derselben Seite.
 * Der aktive Eintrag ist über `is-aktiv` markiert und trägt
 * `aria-current="page"` (Link) bzw. `aria-pressed` (Knopf) — Farbe ist nie der
 * einzige Träger (Prinzip Ä4).
 *
 * Nur Tokens, keine festen Farben. Klickfläche: --control-h (Desktop) bzw.
 * 44 px bei pointer:coarse (K4).
 */
import { computed } from 'vue'

const props = defineProps({
  /** Gewählter Eintrag: `id` aus `menue.kalenderReiter`. */
  modelValue: { type: String, default: '' },
  options: { type: Array, default: () => [] },
  ariaLabel: { type: String, default: '' },
})
defineEmits(['waehlen'])

const optionen = computed(() => props.options || [])

/**
 * Umschalter derselben Seite (`ansicht: true`) oder eigene Seite? Das steht
 * ausdrücklich in der Liste aus `menue.js` — NICHT am `href` abgelesen: „Monat“
 * trägt die Adresse `#/kalender` (der Ort, an dem er gilt) und wäre sonst
 * versehentlich ein Seitenwechsel statt eines Umschalters.
 */
function istAnsicht(r) {
  return Boolean(r) && r.ansicht === true
}

function istAktiv(r) {
  return Boolean(props.modelValue) && String(r.id) === String(props.modelValue)
}

/** Kennzahl nur als echte Zahl — kein „0“ und kein leerer Punkt. */
function zahl(r) {
  const z = r ? r.zahl : null
  if (z === null || z === undefined || z === '') return null
  const n = Number(z)
  return Number.isFinite(n) ? n : null
}
</script>

<style scoped>
.kal-reiter {
  display: flex;
  align-items: stretch;
  /* Einträge stehen auf ihrer Textbreite: ein `<a>` mit auto-Breite füllte in
     der Zeile den Rest und wäre mit seiner Mitte unter Nachbarn — als Flex-
     Kind bleibt jeder Eintrag so breit wie seine Beschriftung. */
  justify-content: flex-start;
  gap: var(--sp-1);
  margin: 0 0 var(--sp-3);
  overflow-x: auto;
  scrollbar-width: none;
  border-bottom: var(--rahmen-breite) solid var(--line);
}
.kal-reiter::-webkit-scrollbar { display: none; }

.kal-reiter-punkt {
  /* `flex: 0 0 auto`: NICHT wachsen (sonst spannt der Link die ganze Zeile
     und sein Klickziel liegt teilweise unter dem Kopf), nicht schrumpfen
     (die Beschriftung soll ganz bleiben). */
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--sp-2);
  min-height: var(--control-h);
  padding: 0 var(--sp-3);
  border: 0;
  box-shadow: inset 0 calc(-1 * var(--rahmen-breite)) 0 transparent;
  border-radius: 0;
  background: none;
  color: var(--muted);
  font: inherit;
  font-weight: var(--fw-mittel);
  text-decoration: none;
  white-space: nowrap;
  cursor: pointer;
  transition: color var(--fast), border-color var(--fast);
}
.kal-reiter-punkt:hover { color: var(--text); }
/* Aktiver Eintrag: Akzentschrift statt --primary — im Dunkelmodus ist
   --primary WEISS und damit von den inaktiven nicht zu unterscheiden
   (DEV-4-Regel, wie DkTabs). */
.kal-reiter-punkt.is-aktiv {
  color: var(--accent);
  box-shadow: inset 0 calc(-2 * var(--rahmen-breite)) 0 var(--accent);
  font-weight: var(--fw-fett);
}
.kal-reiter-punkt:focus-visible { outline: 2px solid var(--focus-ring); outline-offset: -2px; }

.kal-reiter-name { min-width: 0; overflow: hidden; text-overflow: ellipsis; }

/* Zahl offener Prüfungen: Gold = Statusfarbe „zu prüfen“ (dieselben Tokens
   wie die Statusfläche am Termin). */
.kal-reiter-zahl {
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

/* K4: bei Fingerbedienung sind die Reiter 44 px hoch. */
@media (pointer: coarse) {
  .kal-reiter-punkt { min-height: 44px; }
}
</style>
