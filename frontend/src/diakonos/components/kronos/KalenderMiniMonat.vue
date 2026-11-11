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
   Die Trefferfläche bleibt ≥ 44 px: die Zelle ist 48 px hoch (--zelle-hoehe)
   und ragt über ihren negativen Rand unsichtbar in die Nachbarzeile; die
   Spalte ist bei 390 px 47 px breit.
   A10-N3 (Review-Nacharbeit, Punkt 2): 30 px je Zeile reichten nicht — Kreis
   (32) + Lücke (4) + Punkt (4) = 40 px brauchen Platz IN der Zeile, sonst
   sitzt der Punkt der eigenen Zeile optisch bei der nächsten. Deshalb 48 px
   (--zelle-hoehe); der Monat bleibt trotzdem kompakt, weil der Punkt jetzt
   unter der Ziffer sitzt statt in der Nachbarzeile. */
.dk-minimonat {
  display: flex;
  flex-direction: column;
  flex: none;
  gap: var(--sp-2);
  /* A10-N3 (Punkt 1): UNTEN mehr Luft als oben. Vorher war die Karte unten
     8 px (--sp-2) und oben 12 px (--sp-3) gepolstert — die Punkte der
     letzten Zeile standen dadurch am Kartenrand (ihr Zellenrand reicht über
     den Rasterrand hinaus, s. negativer Rand der Zelle). Unten gilt jetzt
     `--pad` (16 px), damit die letzte Punktreihe sichtbar Luft hat. */
  padding: var(--sp-3) var(--sp-3) var(--pad);
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
/* Tageszelle: eine SPALTE, 48 px hoch (--zelle-hoehe) und 44 px hoch als
   TREFFERFLÄCHE (K4): die Zelle ragt über die Zeile hinaus, sodass ihre
   Mitte zugleich die Mitte des 44-px-Bandes ist. Vorher wuchs die Fläche nur
   nach OBEN — dann lag die Mitte der oberen Zelle im unteren Nachbarn, und
   ein Tipp auf die Zahl traf die falsche Zeile (im Wegwerf-Stack gemessen:
   Playwright meldete „intercepts pointer events“). Die Zelle ist deshalb so
   hoch wie das Tippziel (mindestens 44 px, s. u.); das Raster bleibt
   `--zelle-hoehe` hoch, weil der negative Rand die Zelle symmetrisch wieder
   herausnimmt. */
.dk-minimonat-tag {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  /* A10-N3 (Review-Nacharbeit, Punkt 2): Die Zelle hat eine FESTE Höhe je
     Zeile und trägt Zahl und Punkt an EINEM Anker. Vorher richtete
     `justify-content: center` die Gruppe (Zahl + Lücke + Punkt) mittig aus:
     war kein Punkt da, stand die Zahl 4 px tiefer als in Zellen MIT Punkt —
     die Zeilen wirkten unruhig. Und der Punkt saß ~22 px unter der Ziffer,
     also nur ~10 px über der nächsten Zeile; er gehörte optisch zur
     NACHBARZEILE.
     SOLL: die Ziffer steht in JEDER Zelle gleich hoch (an ihrem eigenen
     Anker oben in der Zelle), der Punkt ist unabhängig davon ABSOLUT zur
     Zelle darunter verankert (`.dk-minimonat-punkt`), und die Zeilenhöhe
     ist groß genug für Kreis + Abstand + Punkt (s. `--zelle-hoehe`). */
  justify-content: flex-start;
  /* Abstand Zahl → Punkt ist im Punkt selbst verankert (nicht als `gap`):
     so verschiebt das Vorhandensein eines Punktes nichts anderes. */
  gap: 0;
  /* 44-px-Trefferfläche (K4, Konzept: „bei pointer:coarse 44 px" — und A10
     verlangt am Handy IMMER 44 px, auch mit Maus in einem schmalen Fenster).
     44 px in JEDER Lage über das eigene Token `--treffer-handy` (ein
     390-px-Fenster mit Maus bekäme über `--control-h` sonst nur 40 px).
     Das Raster selbst bleibt über den negativen Rand `--zelle-hoehe` hoch. */
  height: var(--treffer-handy);
  margin: calc((var(--treffer-handy) - var(--zelle-hoehe)) / -2) 0;
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
/* A10-N3 (Review-Nacharbeit, Punkt 2): Der Punkt ist ABSOLUT zur ZELLE
   verankert — unabhängig davon, ob der Tag gewählt ist oder nicht, und ohne
   Einfluss auf die Lage der Ziffer. Vorher hing er im Fluss: mit Punkt stand
   die Ziffer woanders als ohne, und der Punkt saß ~22 px unter der Ziffer
   (nur ~10 px über der nächsten Zeile → optisch bei der falschen Zeile).
   Jetzt: Kreis (32 px) oben an der Zelle, Punkt `--sp-1` (4 px) darunter →
   Gesamthöhe 32 + 4 + 4 = 40 px, die Zelle ist 48 px hoch (--sp-7); damit
   bleiben 8 px Luft bis zur Zellunterkante und der Punkt hat auf jeder Seite
   ≥ 12 px Abstand zur Nachbarzeile. Der Auswahlring liegt AM Kreis (2 px
   Box-Shadow) und endet 2 px über dem Punkt — keine Kollision.
   `pointer-events: none`: der Punkt ist Dekoration, die Trefferfläche bleibt
   die ganze Zelle. */
.dk-minimonat-punkt {
  position: absolute;
  /* Zellmitte minus halbe Punktbreite — der Punkt steht mittig unter dem
     Kreis, egal wie breit er ist (`.ist-mehr` macht ihn zu einem Strich). */
  left: 50%;
  translate: -50% 0;
  top: calc(var(--sp-6) + var(--sp-1));
  display: block;
  width: var(--sp-1);
  height: var(--sp-1);
  border-radius: var(--badge-r);
  background: var(--tag-flaeche, var(--primary));
  pointer-events: none;
}
.dk-minimonat-punkt.ist-pruef { background: var(--warn); }
/* A10-N4 (Punkt A): KEINE Sonderfarben für den gewählten Tag. Der Punkt hat
   `top: 32 + 4 = 36 px` — er liegt UNTER dem 32-px-Kreis, nicht darauf. Die
   frühere Regel „gewählt → --marke-ink (Weiß)“ färbte ihn deshalb weiß auf
   weißer Karte: im hellen Theme unsichtbar. Das galt auch für das goldene
   Prüf-Gold (--dk-gold-300) — im hellen Theme ist der Punkt dann blass, aber
   grundlos anders als an jedem anderen Tag. Der Punkt behält darum seine
   NORMALE Farbe (Kalenderfarbe, bei `ist-pruef` die Warnfarbe) — in beiden
   Themes sichtbar. Farbe ist nie alleiniger Träger: die Vorlesehilfe nennt
   die Zahl, die Prüf-Zeile darüber sagt „Zu prüfen“. */
/* Mehrere Termine: der Punkt wird ein Strich (Anzahl trägt die Vorlesehilfe).
   A10-N3 (Review-Nacharbeit, Punkt 2): Der Strich war 8 px breit und
   zentriert — am Sonntag traf er auf den Strich des Nachbartags (Zellbreite
   47 px, Strich 8 px: 39,5 ± 4 → 35,5…43,5; Sonntag 43,5…51,5) und die
   beiden verschmolzen zu einem Balken. Er bleibt 8 px breit, wird aber an
   der ZELLMITTE (±4 px) verankert und nicht mehr an die Kante geschoben —
   zwischen zwei Strichen liegen damit ≥ 8 px Luft. */
.dk-minimonat-punkt.ist-mehr { width: var(--sp-2); }
</style>
