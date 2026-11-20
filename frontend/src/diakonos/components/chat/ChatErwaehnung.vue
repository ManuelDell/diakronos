<template>
  <!-- CHAT-9b: die Auswahl hinter dem „@“ — ARIA-Combobox-Muster wie
       `ui/MitgliedAuswahl.vue` (dasselbe Zusammenspiel von Feld und Liste,
       hier ohne eigenes Eingabefeld: getippt wird im Nachrichtenfeld).

       Die Liste ist
         * per Tastatur bedienbar (↑/↓ bewegen, Enter/Tab wählt, Escape
           schließt) — die Tasten behandelt die SEITE am Eingabefeld, weil dort
           der Fokus liegt; hier wird nur gezeichnet,
         * am Handy antippbar (jeder Eintrag ist eine Trefferfläche in
           Daumengröße, `--control-h`),
         * ein `listbox` mit `aria-activedescendant` am Feld der Seite.

       Sie hängt ÜBER der Eingabezeile (position: absolute, `bottom: 100%`),
       damit sie den Verlauf nicht verschiebt. Grenzen: höchstens 6 Zeilen,
       darüber rollt sie (bei 360 px bleibt der Verlauf sichtbar).

       CHAT-9b-2: `mehr` (Server: „es gibt weitere Namen zu diesem Anfang“)
       steht als HINWEIS „Weiter tippen, um mehr Personen zu finden.“ — ein
       `<p>` AUSSERHALB des `listbox` (R1/3): die Listbox enthält nur Wahlen,
       und bei 0 Treffern steht gar keine Listbox da, sehr wohl aber der
       Hinweis. Er ist nie wählbar (kein Handler, keine Stelle in der Liste). -->
  <div v-if="offen && (beteiligte.length || mehr)" class="dk-erw">
    <ul
      v-if="beteiligte.length"
      :id="listenKennung"
      class="dk-erw-liste"
      role="listbox"
      :aria-label="LISTEN_LABEL"
    >
      <li
        v-for="(eintrag, i) in beteiligte"
        :id="optionKennung(listenKennung, i)"
        :key="eintrag.mitglied"
        class="dk-erw-eintrag"
        :class="{ 'is-aktiv': i === aktiv }"
        role="option"
        :aria-selected="i === aktiv ? 'true' : 'false'"
        @mousedown.prevent="waehlen(eintrag)"
      >
        <span class="dk-erw-name">{{ eintrag.anzeigename }}</span>
      </li>
    </ul>
    <!-- R1/3: „es gibt mehr“ — ein HINWEIS, keine Wahl. Steht AUSSERHALB
         der Listbox (die Listbox darf nicht leer sein und `aria-controls`
         darf nicht auf eine leere zeigen); bei 0 Treffern also allein da.
         Kein Handler: ↑/↓/Enter/Tab sehen ihn nie. -->
    <p v-if="mehr" class="dk-erw-mehr">{{ MEHR_TEXT }}</p>
    <p class="dk-erw-hinweis">
      {{ HINWEIS }}
      <span class="dk-erw-hinweis-pfeile">{{ HINWEIS_PFEILE }}</span>
    </p>
  </div>
</template>

<script setup>
/**
 * ChatErwaehnung — Vorschlagsliste der Beteiligten (CHAT-9b, Konzept S4).
 *
 * Der Baustein ENTSCHEIDET nichts: welche Beteiligten es gibt und welcher
 * Eintrag aktiv ist, kommt von der Seite (`beteiligte`, `aktiv`); sie kennt
 * auch den Text und den Cursor. Hier wird gezeichnet und ein Tipp
 * weitergereicht (`waehlen`) — eingesetzt in den Text wird dort.
 *
 * Warum kein eigenes `<input>`: getippt wird im Nachrichtenfeld der Seite. Ein
 * zweites Feld mitten im Satz wäre ein zweiter Cursor. Die Tasten laufen
 * deshalb über das Feld der Seite (`aria-activedescendant` zeigt auf den
 * aktiven Eintrag dieser Liste).
 */
import { computed } from 'vue'
import { optionKennung } from './erwaehnung.mjs'

const props = defineProps({
  /** Die gefilterten Beteiligten `[{mitglied, anzeigename}]` (ohne mich). */
  beteiligte: { type: Array, default: () => [] },
  /** Steht die Auswahl offen? (Die Seite entscheidet: „@“ am Wortanfang.) */
  offen: { type: Boolean, default: false },
  /** Stelle des aktiven Eintrags (Tastatur). */
  aktiv: { type: Number, default: 0 },
  /** Kennung der Liste — die Seite setzt sie an `aria-controls`. */
  listenKennung: { type: String, default: 'dk-erwaehnung-liste' },
  /** CHAT-9b-2: Hat der Server `mehr: true` gesagt? Dann steht der Hinweis
   *  „weiter tippen“ da — AUSSERHALB der Listbox, nie wählbar (R1/3). */
  mehr: { type: Boolean, default: false },
})
const emit = defineEmits(['waehlen'])

/** Der Satz über der Liste. DEUTSCH, geschlechtsneutral, ohne Fachwort. */
const LISTEN_LABEL = 'Beteiligte zum Erwähnen'
/** R1/5: Am Handy gibt es keine Pfeiltasten — dort steht nur das Antippen. */
const HINWEIS = 'Zum Erwähnen antippen.'
const HINWEIS_PFEILE = 'Am Rechner: Pfeiltasten wählen, Enter oder Tab übernimmt.'
/** CHAT-9b-2: Text der nicht wählbaren Zeile bei `mehr: true` (Karte). */
const MEHR_TEXT = 'Weiter tippen, um mehr Personen zu finden.'

/** Nur anzeigen, was wirklich in der Liste steht. */
const beteiligte = computed(() => (Array.isArray(props.beteiligte) ? props.beteiligte : []))

function waehlen(eintrag) {
  emit('waehlen', eintrag)
}
</script>

<style scoped>
/* ÜBER der Eingabezeile: die Zeile der Seite ist `position: relative`. */
.dk-erw {
  position: absolute;
  /* R1/8: vorhandenes z-Token (es gibt kein `--z-dropdown`). */
  z-index: var(--z-sticky);
  bottom: calc(100% + var(--sp-1));
  left: 0;
  right: 0;
  max-width: 24rem;
  background: var(--surface);
  border: var(--rahmen-breite) solid var(--line);
  border-radius: var(--radius);
  box-shadow: var(--shadow-md);
  overflow: hidden;
}
.dk-erw-liste {
  margin: 0;
  padding: var(--sp-1);
  list-style: none;
  /* R1/8: 6 Zeilen in rem (kein fester px-Wert). */
  max-height: 13.5rem;
  overflow-y: auto;
}
.dk-erw-eintrag {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  /* K4: am Finger mindestens 44 px (--control-h ist am groben Zeiger 44 px). */
  min-height: var(--control-h);
  padding: 0 var(--sp-2);
  border-radius: var(--radius-sm);
  color: var(--text);
  font-size: var(--fs-14);
  cursor: pointer;
}
.dk-erw-eintrag.is-aktiv { background: var(--surface-hover); }
.dk-erw-eintrag.is-aktiv .dk-erw-name { font-weight: var(--fw-fett); }
/* R1/3: der „weiter tippen“-Hinweis ist ein Satz, keine Wahl — er steht
   unter der Liste (bzw. allein bei 0 Treffern), gedämpft, ohne Zeiger. */
.dk-erw-mehr {
  margin: 0;
  padding: var(--sp-1) var(--sp-2);
  color: var(--muted);
  font-size: var(--fs-12);
  cursor: default;
}
.dk-erw-name {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.dk-erw-hinweis {
  margin: 0;
  padding: var(--sp-1) var(--sp-2);
  border-top: var(--rahmen-breite) solid var(--line);
  background: var(--surface-2);
  color: var(--muted);
  font-size: var(--fs-12);
}
/* R1/5: Der Pfeiltasten-Satz steht nur, wo es einen feinen Zeiger gibt. */
.dk-erw-hinweis-pfeile { display: none; }
@media (pointer: fine) {
  .dk-erw-hinweis-pfeile { display: inline; }
}
</style>
