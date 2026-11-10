<template>
  <!-- A10 (Entwurf „A10 Mobil Kalender"): Tagesliste der Listen-Ansicht.
       Kopf „Sonntag, 8. November" mit dem Link „Woche ›", darunter je Termin
       eine Zeile (Uhrzeit · Titel · Ort · Zusatz · ›) von 56–64 px Höhe.
       Die ganze Zeile ist der Knopf (K4), das „⋯" daneben trägt die
       Aktionen des Termins (UX2e5) — bei 56 px passt es nicht IN die Zeile. -->
  <section class="dk-tagesliste" :aria-label="tagtitel">
    <header class="dk-tagesliste-kopf">
      <h2 class="dk-tagesliste-titel">{{ tagtitel }}</h2>
      <a class="dk-tagesliste-woche" href="#/kalender" @click.prevent="$emit('woche')">
        Woche
        <span class="dk-tagesliste-pfeil" aria-hidden="true"><DkSymbol name="weiter" :groesse="14" /></span>
      </a>
    </header>

    <p v-if="!zeilen.length" class="dk-tagesliste-leer">
      An diesem Tag ist nichts eingetragen.
    </p>

    <ul v-else class="dk-tagesliste-zeilen">
      <li v-for="z in zeilen" :key="z.kennung" class="dk-tagesliste-zeile">
        <button
          type="button"
          class="dk-tagesliste-knopf"
          :aria-label="zeilenLabel(z)"
          :data-termin="z.kennung"
          :style="z.farbe ? { '--zeile-farbe': z.farbe } : null"
          @click="$emit('terminOeffnen', z.termin)"
        >
          <!-- Kalenderfarbe als schmaler Streifen am Zeilenanfang: Farbe ist
               nie alleiniger Träger (Prinzip Ä4), sie ordnet den Termin seinem
               Kalender zu — dieselbe Bedeutung wie der Punkt im Mini-Monat. -->
          <span class="dk-tagesliste-farbe" aria-hidden="true"></span>
          <span class="dk-tagesliste-zeit">{{ z.zeit || 'ganztägig' }}</span>
          <span class="dk-tagesliste-text">
            <span class="dk-tagesliste-name">{{ z.titel }}</span>
            <span v-if="z.zusatz" class="dk-tagesliste-zusatz">{{ z.zusatz }}</span>
          </span>
          <span class="dk-tagesliste-pfeil" aria-hidden="true"><DkSymbol name="weiter" :groesse="16" /></span>
        </button>
        <!-- A10-N2 (Review 09.11., Punkt 4): das „⋯“ steht INNERHALB der
             Karte — rechts in der Zeile, auf der Textlinie. Vorher lag es
             außerhalb der Fläche und wirkte wie ein fremder Knopf.
             DkAktionen zeichnet Auslöser + Teleport (Fragment-Wurzel): eine
             Klasse von außen käme nicht an (dasselbe Muster wie im Kopf,
             `KalenderKopfMobil`), deshalb steckt die Lage in einem Halter. -->
        <span class="dk-tagesliste-mehr">
          <DkAktionen
            :kennung="`termin-${z.kennung}`"
            :eintraege="eintraege"
            :label="`Aktionen für „${z.titel}“`"
            @aktion="(e) => $emit('terminAktion', { key: (e.eintrag || e).key, termin: z.termin })"
          />
        </span>
      </li>
    </ul>
  </section>
</template>

<script setup>
/**
 * KalenderTagesliste — die Tagesliste der A10-Listen-Ansicht.
 *
 * Aufbereitung der Zeilen: `mobilAnsicht.tagesTermine` (reine Funktion,
 * geprüft in `tests/a10-kalender-mobil.test.mjs`). Diese Komponente zeichnet
 * nur und meldet Handlungen nach oben; die Seite entscheidet, was passiert
 * (Lesemodus/Rechte aus UX3i bleiben unangetastet).
 */
import { computed } from 'vue'
import DkSymbol from '../ui/DkSymbol.vue'
import DkAktionen from '../ui/DkAktionen.vue'
import { MENUE_EINTRAEGE } from './terminAktionenMenue.mjs'
import { tagesTermine, tagTitel } from './mobilAnsicht.mjs'
import { sichereFarbe } from '../../../shared/sichere-ausgabe.js'

const props = defineProps({
  /** Termine des gezeigten Bereichs (Kalender-Objekte). */
  termine: { type: Array, default: () => [] },
  /** Tag `JJJJ-MM-TT`. */
  tag: { type: String, default: '' },
  /** Lesemodus: dann bietet das „⋯“ nur „Ansehen“ (wie die Terminliste). */
  lesemodus: { type: Boolean, default: true },
})

defineEmits(['terminOeffnen', 'terminAktion', 'woche'])

const tagtitel = computed(() => tagTitel(props.tag))

const eintraege = computed(() => MENUE_EINTRAEGE
  .filter((e) => (props.lesemodus !== false ? e.key === 'ansehen' : e.key !== 'ansehen')))

const zeilen = computed(() => tagesTermine(props.termine, props.tag).map((z) => ({
  ...z,
  kennung: String(z.termin?.id || z.termin?.name || z.titel),
  // Kalenderfarbe aus den DATEN (nicht Gestaltung) — geprüft, bevor sie in
  // den Stil geht; ohne Wert bleibt der Akzent.
  farbe: sichereFarbe(z.termin?.element_color || z.termin?.backgroundColor || ''),
})))

/** Vorlesehilfe: „9:30 Hauptgottesdienst, Gemeindehaus · Predigt“. */
function zeilenLabel(z) {
  return [z.zeit || 'ganztägig', z.titel, z.zusatz].filter(Boolean).join(', ')
}
</script>

<style scoped>
.dk-tagesliste {
  display: flex;
  flex-direction: column;
  flex: none;
  gap: var(--sp-2);
}
.dk-tagesliste-kopf {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--sp-2);
  min-height: 44px;
}
.dk-tagesliste-titel {
  margin: 0;
  min-width: 0;
  font-size: var(--fs-h3);
  font-weight: var(--fw-fett);
  color: var(--text);
}
.dk-tagesliste-woche {
  display: inline-flex;
  align-items: center;
  gap: var(--sp-1);
  min-height: 44px;
  padding: 0 var(--sp-2);
  color: var(--link);
  font-size: var(--fs);
  font-weight: var(--fw-mittel);
  text-decoration: none;
  white-space: nowrap;
}
.dk-tagesliste-woche:hover { color: var(--link-hover); text-decoration: underline; }
.dk-tagesliste-pfeil { display: inline-flex; align-items: center; flex: none; }
.dk-tagesliste-leer {
  margin: 0;
  padding: var(--pad);
  border-radius: var(--radius);
  background: var(--surface-2);
  color: var(--muted);
  font-size: var(--fs);
}
.dk-tagesliste-zeilen {
  display: flex;
  flex-direction: column;
  gap: var(--sp-1);
  margin: 0;
  padding: 0;
  list-style: none;
}
/* Eine Zeile = Fläche + Knopf + „⋯“. Höhe 56–64 px (Entwurf A10): 56 px
   plus Innenabstand ergibt die gemessene Höhe; bei langen Texten wächst sie.
   A10-N2: das „⋯“ liegt IN der Fläche (innen rechts), deshalb entfällt der
   Abstand zwischen Knopf und Menü und der Knopf gibt ihm den Platz über
   seinen rechten Innenabstand. */
.dk-tagesliste-zeile {
  display: flex;
  align-items: stretch;
  gap: 0;
  border-radius: var(--radius);
  background: var(--surface);
  box-shadow: var(--schatten-karte);
}
.dk-tagesliste-knopf {
  display: grid;
  /* A10-N2 (Review 09.11., Punkt 2): VIER Kinder brauchen VIER Spalten —
     Farbe · Zeit · Text · Pfeil. Mit drei Spalten rutschte der „›“ in eine
     zweite Zeile und die Zeile wurde 87 px hoch statt 56–64 px (gemessen).
     Die Textspalte nimmt den Rest (`1fr`), der Pfeil seine Eigenbreite. */
  grid-template-columns: var(--sp-1) auto minmax(0, 1fr) auto;
  align-items: center;
  gap: var(--sp-3);
  flex: 1;
  min-width: 0;
  min-height: var(--sp-8);
  /* Rechts der Platz für das „⋯“ in der Fläche (44 px Trefferfläche, 4 px
     Luft) — es sitzt auf der Zeilenmitte, der Pfeil bleibt selbst stehen. */
  padding: var(--sp-2) calc(var(--treffer-handy) + var(--sp-1)) var(--sp-2) var(--sp-3);
  border: none;
  border-radius: var(--radius);
  background: transparent;
  color: var(--text);
  font: inherit;
  text-align: left;
  cursor: pointer;
}
/* A10-N2 (Punkt 2): Der Hover-Hintergrund gilt nur mit echter Maus —
   auf dem Handy blieb er nach dem Tippen „hängen“ (zwei Zeilen sahen
   gleichzeitig bedient aus). */
@media (hover: hover) {
  .dk-tagesliste-knopf:hover { background: var(--surface-hover); }
}
.dk-tagesliste-knopf:focus-visible { outline: var(--ring-breite) solid var(--focus-ring); outline-offset: calc(var(--ring-breite) * -1); }
.dk-tagesliste-farbe {
  width: var(--sp-1);
  align-self: stretch;
  margin: calc(var(--sp-2) * -1) 0;
  border-radius: var(--badge-r);
  background: var(--zeile-farbe, var(--primary));
}
.dk-tagesliste-zeit {
  font-size: var(--fs);
  font-weight: var(--fw-fett);
  font-variant-numeric: var(--fs-tabular);
  white-space: nowrap;
}
.dk-tagesliste-text {
  display: flex;
  flex-direction: column;
  gap: var(--sp-1);
  min-width: 0;
}
.dk-tagesliste-name {
  font-size: var(--fs);
  font-weight: var(--fw-mittel);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.dk-tagesliste-zusatz {
  font-size: var(--fs-sm);
  color: var(--muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
/* A10-N2: das „⋯“ steht rechts IN der Zeilenfläche und mittig zur Zeile
   (A10-N2, Punkt 4). 44-px-Trefferfläche (K4) auch im schmalen Fenster. */
.dk-tagesliste-mehr {
  flex: none;
  align-self: center;
  display: flex;
  /* A10-N2: 4 px Abstand zur Kartenkante — sonst sitzt der Knopf auf der
     Linie und wirkt wie „daneben“ (im Bild geprüft). */
  margin-inline-end: var(--sp-1);
}
.dk-tagesliste-mehr :deep(.dk-ui-aktionen-ausloeser) {
  width: var(--treffer-handy);
  height: var(--treffer-handy);
  /* A10-N2 (Review 09.11., Punkt 2): Das gemeinsame „⋯“ nimmt `--subtle` —
     auf der Karte nur 3,8:1 (dunkel) bzw. 4,9:1 (hell) und damit zu blass.
     Hier ist es die EINZIGE sichtbare Bedienung der Zeile und trägt deshalb
     die Textfarbe (7,1:1 dunkel / 14,3:1 hell gegen die Karte). */
  color: var(--text);
}
</style>
