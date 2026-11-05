<template>
  <!-- ON-3: EIN Symbolvorrat für den Einrichtungs-Assistenten. Die Pfade
       stehen gebündelt hier statt in jeder Vorlage; FARBE und GRÖSSE kommen
       immer von außen (`currentColor`, `size`) — kein `stroke="#…"`, damit
       `tokens.css` die einzige Farbquelle bleibt. `aria-hidden`, weil jedes
       Symbol neben einer Beschriftung steht (dekorativ). -->
  <svg
    :width="1"
    :height="1"
    :style="{ width: size, height: size }"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    :stroke-width="strich"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
    focusable="false"
  >
    <template v-if="name === 'haken'">
      <path d="M20 6 9 17l-5-5" />
    </template>
    <template v-else-if="name === 'zurueck'">
      <path d="M15 18l-6-6 6-6" />
    </template>
    <template v-else-if="name === 'bild'">
      <rect x="3" y="3" width="18" height="18" rx="2" />
      <circle cx="8.5" cy="8.5" r="1.5" />
      <path d="m21 15-5-5L5 21" />
    </template>
    <template v-else-if="name === 'hochladen'">
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
      <polyline points="17 8 12 3 7 8" />
      <line x1="12" y1="3" x2="12" y2="15" />
    </template>
    <template v-else-if="name === 'entfernen'">
      <path d="M18 6 6 18" />
      <path d="m6 6 12 12" />
    </template>
    <template v-else-if="name === 'warnung'">
      <path d="M12 3 2 20h20L12 3z" />
      <line x1="12" y1="9" x2="12" y2="14" />
      <line x1="12" y1="17" x2="12" y2="17.01" />
    </template>
    <template v-else-if="name === 'brief'">
      <rect x="2" y="4" width="20" height="16" rx="2" />
      <path d="m2 7 10 7 10-7" />
    </template>
    <template v-else-if="name === 'senden'">
      <path d="M22 2 11 13" />
      <path d="M22 2 15 22l-4-9-9-4 20-7z" />
    </template>
    <template v-else-if="name === 'kreis-haken'">
      <circle cx="12" cy="12" r="10" />
      <path d="m8 12 3 3 5-6" />
    </template>
  </svg>
</template>

<script setup>
/**
 * AssistentSymbol — Symbolvorrat des Einrichtungs-Assistenten (ON-3).
 *
 * `name`: haken | zurueck | bild | hochladen | entfernen | warnung | brief |
 *         senden | kreis-haken
 * `size`: Kantenlänge; eine Zahl = px, eine CSS-Länge/Tokens wie
 *         `var(--icon-sm)` (Default `--icon-md`, also 16 px).
 * `strich`: Strichstärke; 2 ist der Standard, 1.6–1.9 passen zu größeren
 *           Symbolen (Entwurf zeichnet z. B. die 29-px-Haken mit ~1.8).
 *
 * WARUM DIE ATTRIBUTE `1` TRAGEN UND DIE GRÖSSE AUS TOKENS KOMMT (ON-E2E)
 * ---------------------------------------------------------------------
 * `width`/`height` sind SVG-**Attribute** und nehmen nur echte Längen
 * (`16`, `16px`) — `var(--icon-md)` ist dort keine Länge. Der Browser meldete
 * das je Symbol mit „<svg> attribute width: Expected length, \"var(…)\"\" in
 * der Konsole, und die übrigen Regeln des Hauses („keine Größen-Zahlen in
 * Komponenten", ON-0a/ON-0c) galten für dieses eine Symbol nicht.
 * Die GRÖSSE kommt deshalb als CSS (`style`, also Token-fähig). Die Attribute
 * `width`/`height` tragen die konstante Zahl `1` — ein Platzhalter, den CSS
 * überschreibt; `viewBox="0 0 24 24"` lässt die Zeichnung mitskalieren. So
 * steht `var(…)` NIE in einem Attribut (die Browser-Warnung entfällt), und
 * es gibt keine Größen-Zahl mehr im Markup — die Zahl `1` bleibt allein hier.
 */
defineProps({
  name: { type: String, required: true },
  size: { type: [String, Number], default: 'var(--icon-md)' },
  strich: { type: [String, Number], default: 2 },
})
</script>
