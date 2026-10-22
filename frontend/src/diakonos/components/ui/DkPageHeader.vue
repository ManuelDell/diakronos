<template>
  <header class="dk-ui-pageheader">
    <div class="dk-ui-pageheader-main">
      <nav v-if="krumen.length" class="dk-ui-brot" aria-label="Brotkrumen">
        <template v-for="(k, i) in krumen" :key="i">
          <span v-if="i" class="dk-ui-brot-sep" aria-hidden="true">/</span>
          <a v-if="k.href && i < krumen.length - 1" class="dk-ui-brot-link" :href="k.href">{{ k.text }}</a>
          <span v-else class="dk-ui-brot-current">{{ k.text }}</span>
        </template>
      </nav>
      <h1 class="dk-ui-pageheader-titel">{{ title }}</h1>
      <p v-if="sub" class="dk-ui-pageheader-sub">{{ sub }}</p>
      <div v-if="badges.length" class="dk-ui-pageheader-badges">
        <DkBadge v-for="(b, i) in badges" :key="i" :variant="b.variant || 'neutral'">{{ b.text }}</DkBadge>
      </div>
    </div>
    <div v-if="$slots.actions" class="dk-ui-pageheader-aktionen">
      <slot name="actions" />
    </div>
  </header>
</template>

<script setup>
/**
 * DkPageHeader — Seitenkopf (Stil A): Brotkrumen, Titel, Unterzeile,
 * Status-Kennzeichen und Aktionen.
 * krumen: [{ text, href? }]  badges: [{ text, variant? }]
 * Nur Tokens, keine festen Farben.
 */
import DkBadge from './DkBadge.vue'

defineProps({
  title: { type: String, required: true },
  sub: { type: String, default: '' },
  krumen: { type: Array, default: () => [] },
  badges: { type: Array, default: () => [] },
})
</script>

<style scoped>
.dk-ui-pageheader {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: var(--gap);
  flex-wrap: wrap;
  /* DES-R13 / Entwicklung 16.10.: Auf Detailseiten stieß der Seitenkopf ohne
     jeden Abstand direkt an die erste Karte (0 px). Der Abstand gehört an EINE
     Stelle — hier —, nicht in jede Seite. */
  margin-bottom: var(--sp-5);
}
.dk-ui-pageheader-main { display: flex; flex-direction: column; gap: var(--sp-2); min-width: 0; }
.dk-ui-brot { display: flex; align-items: center; gap: var(--sp-2); font-size: var(--fs-sm); color: var(--subtle); }
.dk-ui-brot-sep { color: var(--subtle); }
.dk-ui-brot-link { color: var(--muted); text-decoration: none; }
.dk-ui-brot-link:hover { color: var(--text); text-decoration: underline; }
.dk-ui-brot-current { color: var(--muted); }
.dk-ui-pageheader-titel { font-size: var(--fs-h1); font-weight: var(--fw-h); letter-spacing: -.01em; margin: 0; color: var(--text); }
.dk-ui-pageheader-sub { font-size: var(--fs); color: var(--muted); margin: 0; }
.dk-ui-pageheader-badges { display: flex; flex-wrap: wrap; gap: var(--sp-2); }
/* P3-4b/Restpunkt 10: „Alle festlegen“ sass am Desktop ohne erkennbaren Abstand
   direkt über der Zahl-Plakette. Die Aktionen bekommen deshalb eine eigene
   Mindest-Hoehe und einen Abstand, damit Knopf und darunterliegender Inhalt
   nicht aneinanderkleben (auch wenn die Plakette in dieselbe Zeile rutscht). */
.dk-ui-pageheader-aktionen {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  flex-wrap: wrap;
  padding-block: var(--sp-1);
  min-height: calc(var(--sp-8) + var(--sp-2));
}
.dk-ui-pageheader-badges { margin-block: var(--sp-1); }
</style>
