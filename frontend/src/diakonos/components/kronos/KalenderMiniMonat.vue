<template>
  <!-- A10 (Entwurf „A10 Mobil Kalender"): kompakter Monat mit Punkten für Tage
       mit Terminen (Kalenderfarbe), der gewählte Tag als gefüllter Kreis.
       Kein Termin-Chip in den Zellen — am Handy waren die 47-px-Chips
       abgeschnitten (Befund der Karte). Ein Tipp auf einen Tag wählt ihn aus
       und füllt die Tagesliste darunter. -->
  <section class="dk-minimonat" aria-label="Monatsübersicht">
    <!-- A10-N2 (Review 09.11., Punkt 2): Die Monatsbewegung steht in der
         Kopfzeile des Mini-Monats (wie in Entwurf A10): ‹ ‹Titel› › — die
         beiden Pfeile bewegen den gezeigten Monat, also stehen sie am Monat
         und nicht in einer eigenen Werkzeugzeile darüber. „Heute" bleibt der
         einzige Ort dafür am Handy. Die Pfeile sind optional: ohne Rückmeldung
         von oben (`@zurueck`/`@vor`) erscheinen sie nicht. -->
    <header class="dk-minimonat-kopf">
      <DkButton
        variant="ghost"
        class="dk-minimonat-pfeil"
        aria-label="Vorheriger Monat"
        title="Zurück"
        @click="$emit('zurueck')"
      >
        <template #icon><DkSymbol name="zurueck" :groesse="16" /></template>
      </DkButton>
      <h2 class="dk-minimonat-titel">{{ titel }}</h2>
      <DkButton
        variant="ghost"
        class="dk-minimonat-pfeil"
        aria-label="Nächster Monat"
        title="Weiter"
        @click="$emit('vor')"
      >
        <template #icon><DkSymbol name="weiter" :groesse="16" /></template>
      </DkButton>
      <DkButton variant="ghost" class="dk-minimonat-heute" @click="$emit('heute')">Heute</DkButton>
    </header>

    <div class="dk-minimonat-raster" role="grid" :aria-label="titel">
      <div class="dk-minimonat-wochentage" role="row">
        <span v-for="w in wochentage" :key="w" class="dk-minimonat-wt" role="columnheader">{{ w }}</span>
      </div>
      <div v-for="(woche, wi) in raster" :key="wi" class="dk-minimonat-woche" role="row">
        <button
          v-for="tag in woche"
          :key="tag.tag"
          type="button"
          role="gridcell"
          class="dk-minimonat-tag"
          :class="{
            'is-aussen': !tag.imMonat,
            'is-heute': tag.istHeute,
            'is-gewaehlt': tag.tag === gewaehlt,
          }"
          :aria-label="tag.titel"
          :aria-current="tag.tag === gewaehlt ? 'date' : undefined"
          :data-tag="tag.tag"
          :style="tag.tag === gewaehlt ? { '--tag-flaeche': farbe } : null"
          @click="$emit('tagWechsel', tag.tag)"
        >
          <span class="dk-minimonat-zahl">{{ tag.zahl }}</span>
          <span
            v-if="tag.punkt"
            class="dk-minimonat-punkt"
            :class="{ 'ist-pruef': tag.punkt.pruefen && !tag.punkt.normal, 'ist-mehr': tag.punkt.anzahl > 1 }"
            aria-hidden="true"
          ></span>
        </button>
      </div>
    </div>
  </section>
</template>

<script setup>
/**
 * KalenderMiniMonat — der kompakte Monat der A10-Liste.
 *
 * Reine Anzeige: Raster aus `mobilAnsicht.miniRaster`, Punkte aus
 * `mobilAnsicht.punkteJeTag`. Farbe: die des gewählten Kalenders
 * (`--tag-flaeche`, aus den Kalenderdaten — KEINE Gestaltungsfarbe, deshalb
 * als Inline-Wert erlaubt wie bei den Termin-Chips).
 */
import { computed, watch } from 'vue'
import DkButton from '../ui/DkButton.vue'
import DkSymbol from '../ui/DkSymbol.vue'
import { WOCHENTAGE, miniRaster, monatsTitel, tagTitel, punkteJeTag } from './mobilAnsicht.mjs'

const props = defineProps({
  /** Monat `JJJJ-MM`. */
  monat: { type: String, required: true },
  /** Gewählter Tag `JJJJ-MM-TT`. */
  gewaehlt: { type: String, default: '' },
  /** Termine des gezeigten Bereichs (Kalender-Objekte). */
  termine: { type: Array, default: () => [] },
  /** Kennungen der zu prüfenden Termine (goldene Punkte). */
  pruefIds: { type: Array, default: () => [] },
  /** Kalenderfarbe für den gewählten Tag (aus den Serverdaten). */
  farbe: { type: String, default: '' },
})

const emit = defineEmits(['tagWechsel', 'heute', 'spanne', 'zurueck', 'vor'])

const wochentage = WOCHENTAGE
const titel = computed(() => monatsTitel(props.monat))

/** Die gezeigten sechs Wochen — die Seite holt genau dafür die Termine. */
const spanne = computed(() => {
  const zeilen = miniRaster(props.monat)
  if (!zeilen.length) return null
  return [zeilen[0][0].tag, zeilen[zeilen.length - 1][6].tag]
})
watch(spanne, (wert) => { if (wert) emit('spanne', wert) }, { immediate: true })

const raster = computed(() => {
  const zeilen = miniRaster(props.monat)
  const punkte = punkteJeTag(props.termine, props.pruefIds, [
    zeilen.length ? zeilen[0][0].tag : '',
    zeilen.length ? zeilen[zeilen.length - 1][6].tag : '',
  ])
  return zeilen.map((woche) => woche.map((tag) => ({
    ...tag,
    punkt: punkte.get(tag.tag) || null,
    titel: `${tagTitel(tag.tag)}${punkte.get(tag.tag) ? ` · ${punkte.get(tag.tag).anzahl} Termin${punkte.get(tag.tag).anzahl === 1 ? '' : 'e'}` : ''}`,
  })))
})
</script>

<style scoped>
/* A10 (Nacharbeit 09.11., Punkt 4): der Monat ist nach den A10-Maßen
   KOMPAKTER. Vorbild ist `gen_ui.py` (Abschnitt A10): Zeile 30 px, Tageszahl
   12 px, gewählter Tag ein 28-px-Kreis, Punkt 4 px. Vorher fraß der
   Mini-Monat 44 px je Zeile, sodass die Tagesliste erst nach dem Scrollen
   erschien — beim Moderator muss sie im ersten Bildschirm stehen.
   Die Trefferfläche bleibt ≥ 44 px: die Zelle ist 30 px hoch und ragt über
   ihren negativen Rand unsichtbar in die Nachbarzeile; die Spalte ist bei
   390 px 47 px breit. */
.dk-minimonat {
  display: flex;
  flex-direction: column;
  flex: none;
  gap: var(--sp-2);
  padding: var(--sp-3) var(--sp-3) var(--sp-2);
  border-radius: var(--radius-lg);
  background: var(--surface);
  box-shadow: var(--schatten-karte);
}
.dk-minimonat-kopf {
  display: flex;
  align-items: center;
  gap: var(--sp-1);
  min-height: var(--treffer-handy);
}
.dk-minimonat-titel {
  margin: 0;
  flex: 1;
  min-width: 0;
  text-align: center;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: var(--fs);
  font-weight: var(--fw-fett);
  color: var(--text);
}
/* A10-N2 (Punkt 2): ‹ › stehen in DIESER Kopfzeile (Vorbild A10) — je
   44 px Tippziel (K4), ruhige ghost-Knöpfe links und rechts am Titel. */
.dk-minimonat-pfeil {
  flex: none;
  min-width: var(--treffer-handy);
  min-height: var(--treffer-handy);
  padding: 0;
}
.dk-minimonat-pfeil:deep(.dk-ui-btn) { min-height: var(--treffer-handy); }
/* „Heute“ ist der einzige Ort dafür am Handy (Entwurf A10) — ein ruhiger
   Textknopf, Tippziel 44 px. */
.dk-minimonat-heute {
  flex: none;
  min-height: var(--treffer-handy);
  padding: 0 var(--sp-2);
  font-size: var(--fs-sm);
}
/* DkButton bringt `--filter-h` (40 px am feinen Zeiger) — hier gilt das
   Handy-Maß in jeder Lage. */
.dk-minimonat-heute:deep(.dk-ui-btn) { min-height: var(--treffer-handy); }
.dk-minimonat-raster {
  display: flex;
  flex-direction: column;
  gap: 0;
}
.dk-minimonat-wochentage,
.dk-minimonat-woche {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 0;
}
.dk-minimonat-wt {
  text-align: center;
  font-size: var(--fs-sm);
  font-weight: var(--fw-fett);
  color: var(--muted);
  padding-bottom: var(--sp-1);
}
/* Tageszelle: eine SPALTE, 30 px hoch (Rasterzeile A10) und 44 px hoch als
   TREFFERFLÄCHE (K4): die Zelle ragt 7 px über die Zeile hinaus, sodass ihre
   Mitte zugleich die Mitte des 44-px-Bandes ist. Vorher wuchs die Fläche nur
   nach OBEN — dann lag die Mitte der oberen Zelle im unteren Nachbarn, und
   ein Tipp auf die Zahl traf die falsche Zeile (im Wegwerf-Stack gemessen:
   Playwright meldete „intercepts pointer events“). Die Zelle ist deshalb so
   hoch wie das Tippziel (mindestens 44 px, s. u.); das Raster bleibt 30 px
   je Zeile, weil der negative Rand die Zelle symmetrisch wieder herausnimmt. */
.dk-minimonat-tag {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0;
  /* 44-px-Trefferfläche (K4, Konzept: „bei pointer:coarse 44 px" — und A10
     verlangt am Handy IMMER 44 px, auch mit Maus in einem schmalen Fenster).
     44 px in JEDER Lage über das eigene Token `--treffer-handy` (ein
     390-px-Fenster mit Maus bekäme über `--control-h` sonst nur 40 px).
     Das Raster selbst bleibt über den negativen Rand 30 px hoch. */
  height: var(--treffer-handy);
  margin: calc((var(--treffer-handy) - var(--sp-6)) / -2) 0;
  padding: 0;
  border: none;
  background: transparent;
  color: var(--text);
  font: inherit;
  font-size: var(--fs-sm);
  font-weight: var(--fw-mittel);
  font-variant-numeric: var(--fs-tabular);
  cursor: pointer;
}
.dk-minimonat-zahl {
  position: relative;
  z-index: 1;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: var(--sp-6);
  height: var(--sp-6);
  border-radius: var(--badge-r);
  line-height: 1;
}
.dk-minimonat-tag.is-aussen { color: var(--subtle); }
.dk-minimonat-tag.is-heute .dk-minimonat-zahl {
  font-weight: var(--fw-fett);
  text-decoration: underline;
  text-underline-offset: var(--sp-1);
}
/* A10 (Review 09.11., Punkt 4): der gewählte Tag ist NAVY — nicht die
   Kalenderfarbe. Die Kalenderfarbe trägt den PUNKT; eine Fläche in derselben
   Farbe wie der Punkt hätte den Punkt unsichtbar gemacht (beides navy)
   oder, bei einem hellen Kalender, unlesbare Zahlen ergeben. */
.dk-minimonat-tag.is-gewaehlt .dk-minimonat-zahl {
  background: var(--marke-flaeche);
  color: var(--marke-ink);
  font-weight: var(--fw-fett);
  text-decoration: none;
  /* A10-N2 (Review 09.11., Punkt 3): Im Dunkelmodus liegt Navy auf Navy-grau
     (1,16:1) — der gewählte Tag wäre nicht als Fläche zu erkennen. Der Ring
     kommt aus dem Token: hell transparent, dunkel hellblau (8,6:1). */
  box-shadow: 0 0 0 var(--marke-ring-breite) var(--marke-ring);
}
.dk-minimonat-tag:focus-visible .dk-minimonat-zahl {
  outline: var(--ring-breite) solid var(--focus-ring);
  outline-offset: var(--sp-1);
}
/* Ein Punkt und der Kreis passen nicht BEIDE in 30 px: die Zahl sitzt im
   Kreis, der Punkt steht direkt DARUNTER am unteren Zellenrand (absolut,
   waagerecht zentriert über `inset-inline`). */
.dk-minimonat-punkt {
  position: absolute;
  inset-inline: 0;
  bottom: 0;
  margin-inline: auto;
  width: var(--sp-1);
  height: var(--sp-1);
  border-radius: var(--badge-r);
  background: var(--tag-flaeche, var(--primary));
}
.dk-minimonat-tag.is-gewaehlt .dk-minimonat-punkt { background: var(--marke-ink); }
.dk-minimonat-punkt.ist-pruef { background: var(--warn); }
/* Am gewählten Tag liegt der goldene Punkt auf Navy: dort nimmt er das helle
   Gold (--dk-gold-300), sonst wäre ein dunkler Ton auf dunklem Kreis unsichtbar
   (Farbe ist nie alleiniger Träger — die Vorlesehilfe nennt die Zahl, die
   Prüf-Zeile darüber sagt „Zu prüfen“). */
.dk-minimonat-tag.is-gewaehlt .dk-minimonat-punkt.ist-pruef { background: var(--dk-gold-300); }
/* Mehrere Termine: der Punkt wird ein Strich (Anzahl trägt die Vorlesehilfe). */
.dk-minimonat-punkt.ist-mehr { width: var(--sp-2); }
</style>
