<template>
  <!-- A10 (Entwurf „A10 Mobil Kalender"): der EINE Kopf des Kalenders auf dem
       Handy. Links die Segmentsteuerung „Monat · Woche · Liste" (aktives
       Segment weiß mit Schatten), rechts in DERSELBEN Zeile
       die Werkzeuge als 44-px-Symbolknöpfe: Kalender-Auswahl (mit Zahl) und
       „⋯" (alles Seltene). Es gibt KEINE eigene Werkzeugzeile mehr.

       NUR Mobil: Die Seite rendert dieses Bauteil nur unterhalb der
       Layout-Grenze (`breiten.mjs`, 720 px). Der Desktop behält A4.

       KEIN zweiter Titel: „Kalender" und das Abzeichen „Moderator" stehen in
       der App-Kopfzeile (Menü · Kalender [Moderator] · Suche — genau die
       Zeile, die Entwurf A10 oben zeigt).

       A10-N2 (Review 09.11., Punkt 2): Vorher stand hier eine zweite, eigene
       Zeile „Kalender 3 · ‹ · › · ⋯". Die ist entfallen. ‹ › gehören in die
       Kopfzeile des Mini-Monats (`KalenderMiniMonat`, Vorbild A10) — sie
       bewegen beide den gezeigten Monat, also stehen sie am Monat. -->
  <header class="dk-mobilkopf">
    <div class="dk-mobilkopf-segmente" role="tablist" aria-label="Kalender-Ansicht">
      <button
        v-for="a in ansichten"
        :key="a.id"
        type="button"
        role="tab"
        class="dk-mobilkopf-segment"
        :class="{ 'is-aktiv': a.id === ansicht }"
        :aria-selected="a.id === ansicht ? 'true' : 'false'"
        :data-ansicht="a.id"
        @click="$emit('ansichtWechsel', a.id)"
      >{{ a.label }}</button>
    </div>

    <!-- Werkzeuge, 44 × 44 (K4): Kalender-Auswahl und „⋯". Beide sind
         SYMBOLknöpfe — die Beschriftung steht im `aria-label`/`title`, nicht
         als Text daneben (so bleibt eine Kopfzeile). -->
    <div class="dk-mobilkopf-werkzeuge">
      <DkButton
        variant="secondary"
        class="dk-mobilkopf-knopf dk-mobilkopf-kalender"
        data-kalender-ausloeser="mobil" data-kalender-sichtbar="1"
        :aria-expanded="auswahlOffen ? 'true' : 'false'"
        aria-haspopup="dialog"
        aria-label="Kalender auswählen"
        :title="kalenderTitel"
        @click="$emit('kalenderauswahl')"
      >
        <template #icon><DkSymbol name="kalender" :groesse="20" /></template>
        <span v-if="eingeblendet !== null" class="dk-mobilkopf-zahl" aria-hidden="true">{{ eingeblendet }}</span>
      </DkButton>
      <!-- DkAktionen zeichnet Auslöser + Teleport (Fragment-Wurzel): eine
           Klasse von außen käme nicht an, deshalb steckt der Abstand in
           einem eigenen Halter. -->
      <div class="dk-mobilkopf-mehr">
        <DkAktionen
          kennung="kalender-mobil"
          :eintraege="menue"
          label="Weitere Kalender-Aktionen"
          menue-label="Weitere Kalender-Aktionen"
          @aktion="onMenueAktion"
        />
      </div>
    </div>
  </header>
</template>

<script setup>
/**
 * KalenderKopfMobil — Kopf des Mobil-Kalenders (Karte A10).
 *
 * Zeichnet nur; Rechte, Ansicht und Menüinhalt kommen von der Seite
 * (`pages/Kalender.vue`) bzw. aus `mobilAnsicht.mjs`. Dieselbe Trennung wie
 * bei `KronosTopbar` (A4/UX3i): hier wird KEIN Recht entschieden.
 *
 * Die App-Kopfzeile (Menü · Titel · Suche) bleibt sichtbar — A10 beschreibt
 * sie als Rahmen, den die App selbst stellt. Titel und Abzeichen „Moderator"
 * stehen SEIT DER NACHARBEIT (Review 09.11., Punkt 4) dort und nicht mehr
 * hier.
 */
import { computed } from 'vue'
import DkButton from '../ui/DkButton.vue'
import DkSymbol from '../ui/DkSymbol.vue'
import DkAktionen from '../ui/DkAktionen.vue'
import { MOBIL_ANSICHTEN, mobilMenue } from './mobilAnsicht.mjs'

const props = defineProps({
  /** Gewählte Ansicht: `monat` · `woche` · `liste`. */
  ansicht: { type: String, default: 'liste' },
  /** Persönliche Standard-Ansicht (Häkchen im „⋯"-Menü). */
  standard: { type: String, default: 'liste' },
  /** UX3d: `can_moderate` aus dem Boot-Objekt — die Seite setzt dafür das
   *  Abzeichen in der App-Kopfzeile; hier dient das Recht dem Menü. */
  darfPruefen: { type: Boolean, default: false },
  /** Zahl eingeblendeter Kalender (`null` = unbekannt). */
  eingeblendet: { type: Number, default: null },
  auswahlOffen: { type: Boolean, default: false },
  hatSchreibrecht: { type: Boolean, default: false },
  istKalenderAdmin: { type: Boolean, default: false },
  lesemodus: { type: Boolean, default: true },
})

const emit = defineEmits([
  'ansichtWechsel', 'kalenderauswahl', 'heute', 'zurueck', 'vor',
  'standardSetzen', 'ressourcenplan', 'bearbeitenUmschalten', 'abgelehnteTermine', 'hilfe',
])

const ansichten = MOBIL_ANSICHTEN

/** Vorlesehilfe des Auswahl-Knopfs: „Kalender auswählen (3 eingeblendet)". */
const kalenderTitel = computed(() => (props.eingeblendet === null
  ? 'Meine Kalender ein-/ausblenden'
  : `Meine Kalender ein-/ausblenden — ${props.eingeblendet} eingeblendet`))

const menue = computed(() => mobilMenue({
  ansicht: props.ansicht,
  standard: props.standard,
  istKalenderAdmin: props.istKalenderAdmin === true,
  hatSchreibrecht: props.hatSchreibrecht === true,
  lesemodus: props.lesemodus !== false,
}))

/** DkAktionen meldet `{ eintrag, index }` — nur der Eintrag zählt. */
function onMenueAktion(ereignis) {
  const eintrag = ereignis && ereignis.eintrag ? ereignis.eintrag : ereignis
  if (!eintrag || !eintrag.key) return
  if (eintrag.href) return   // echte Links (Verwalten/Import) navigiert der Browser
  const erlaubt = [
    'standardSetzen', 'ressourcenplan', 'bearbeitenUmschalten', 'abgelehnteTermine', 'hilfe',
  ]
  if (erlaubt.includes(eintrag.aktion)) emit(eintrag.aktion)
}
</script>

<style scoped>
/* Kopf des Mobil-Kalenders: EINE Fläche, kein Rahmen (Ä2), Abstände aus der
   Skala. A10-N2 (Re-Review 09.11.): EINE Zeile — Segmente nehmen den Rest,
   rechts die zwei Symbolknöpfe. Zwei Zeilen untereinander wären wieder die
   eigene Werkzeugzeile (44 px Höhe für zwei Knöpfe). */
.dk-mobilkopf {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: var(--sp-2);
  padding: var(--sp-3) var(--sp-2) 0;
  background: var(--bg);
}
/* Symbolknöpfe: quadratisch, 44 px Tippziel (K4). `--control-h` ist bei
   grobem Zeiger bereits 44 px; das Mindestmaß steht hier ausdrücklich,
   damit es auch mit Maus (schmales Fenster) nicht darunter fällt. */
.dk-mobilkopf-knopf {
  flex: none;
  min-width: var(--treffer-handy);
  min-height: var(--treffer-handy);
  padding: 0;
}
/* DkButton bringt seine Höhe aus `--filter-h` (40 px am feinen Zeiger) — in
   dieser Handy-Ansicht ist das zu klein, also hier ausdrücklich das Maß der
   Mobile-Lage. */
.dk-mobilkopf-knopf:deep(.dk-ui-btn) { min-height: var(--treffer-handy); }
/* A10-N2 (Review 09.11., Punkt 2): Der Auswahlknopf ist ein SYMBOLknopf mit
   der Zahl daneben — die Zahl ist Information („wie viele Kalender sind
   eingeblendet"), keine Beschriftung. Schmal, damit die Zeile ruhig bleibt. */
.dk-mobilkopf-kalender {
  width: auto;
  padding: 0 var(--sp-2);
  gap: var(--sp-1);
}
.dk-mobilkopf-zahl {
  color: var(--text);
  font-size: var(--fs);
  font-weight: var(--fw-mittel);
  font-variant-numeric: var(--fs-tabular);
  line-height: 1;
}
/* Segmentsteuerung: aktives Segment WEISS mit Schatten (Entwurf A10). */
.dk-mobilkopf-segmente {
  display: flex;
  flex: 1 1 auto;
  min-width: 0;
  gap: var(--sp-1);
  padding: var(--sp-1);
  border-radius: var(--radius);
  background: var(--surface-2);
}
.dk-mobilkopf-segment {
  flex: 1;
  min-width: 0;
  min-height: var(--treffer-handy);
  padding: 0 var(--sp-2);
  border: none;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--muted);
  font: inherit;
  font-size: var(--fs);
  font-weight: var(--fw-mittel);
  cursor: pointer;
  transition: background var(--fast), color var(--fast);
}
.dk-mobilkopf-segment.is-aktiv {
  background: var(--surface);
  color: var(--text);
  font-weight: var(--fw-fett);
  box-shadow: var(--shadow-sm);
}
.dk-mobilkopf-segment:focus-visible { outline: var(--ring-breite) solid var(--focus-ring); outline-offset: var(--sp-1); }
/* Werkzeuge: EINE Zeile mit zwei 44-px-Zielen; „⋯" steht rechts außen
   (N6: Objekt-Aktionen am Objekt; hier: alles Seltene an einer Stelle). */
.dk-mobilkopf-werkzeuge {
  display: flex;
  flex: none;
  align-items: center;
  gap: var(--sp-2);
}
.dk-mobilkopf-mehr { margin-left: auto; display: flex; }
/* Das „⋯" ist ein Baustein (DkAktionen) und wächst am groben Zeiger selbst
   auf 44 px; in einem SCHMALEN Fenster mit Maus bliebe es bei 40 px. Diese
   Ansicht ist nur die Handy-Lage — hier gilt das Handy-Maß in jeder Lage. */
.dk-mobilkopf-mehr :deep(.dk-ui-aktionen-ausloeser) {
  width: var(--treffer-handy);
  height: var(--treffer-handy);
  /* A10-N2 (Punkt 2): `--subtle` ist im Dunkelmodus 3,8:1 — zu blass für ein
     Bedienelement. Das „⋯“ trägt hier die Textfarbe (7,1:1 / 14,3:1). */
  color: var(--text);
}
</style>
