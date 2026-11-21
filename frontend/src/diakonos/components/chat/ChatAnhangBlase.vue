<template>
  <!-- CHAT-12b: die Anhänge EINER Nachricht unter dem Text (Karte Punkt 3).

       Bilder (jpg/png/webp) als Vorschau, HEIC und PDF als Dateizeile mit
       Symbol/Name/Größe/Herunterladen, Audio als `<audio controls
       preload="none">`. Jede Adresse kommt über `chat.anhang?name=…` — DIESELBE
       Basis wie die übrigen Aufrufe (`apiUrl`), es gibt keine zweite Logik.

       `preload="none"` ist Absicht: ein Verlauf mit zehn Sprachnachrichten
       lädt sonst zehn Dateien, von denen niemand eine anhört. -->
  <ul v-if="posten.length" class="dk-chat-anhaenge-blase" aria-label="Anhänge">
    <li v-for="a in posten" :key="a.name" class="dk-chat-anhang" :class="`is-${a.art}`">
      <!-- Bild: Vorschau mit fester Höhe, Klick öffnet groß im neuen Tab.
           `alt` ist der Dateiname (Karte Punkt 4). -->
      <a
        v-if="a.art === 'bild'"
        class="dk-chat-anhang-bild"
        :href="a.url"
        target="_blank"
        rel="noopener"
        :aria-label="`${TEXTE.bildOeffnen}: ${a.dateiname}`"
      >
        <img
          :src="a.url"
          :alt="a.dateiname"
          loading="lazy"
          decoding="async"
          class="dk-chat-anhang-vorschau"
        >
      </a>

      <!-- Audio: der eingebaute Abspieler, ohne Vorabladen. -->
      <audio
        v-else-if="a.art === 'audio'"
        class="dk-chat-anhang-ton"
        :src="a.url"
        controls
        preload="none"
        :aria-label="a.dateiname"
      ></audio>

      <!-- Alles andere (PDF, HEIC, unbekannt): eine Zeile mit Symbol, Name,
           Größe und Herunterladen. HEIC ist bewusst hier — die wenigsten
           Browser zeigen es, eine leere Vorschau wäre eine Enttäuschung. -->
      <span v-else class="dk-chat-anhang-zeile">
        <span class="dk-chat-anhang-symbol" aria-hidden="true"><DkSymbol :name="a.symbol" :groesse="18" /></span>
        <span class="dk-chat-anhang-text">
          <span class="dk-chat-anhang-name" :title="a.dateiname">{{ a.dateiname }}</span>
          <span class="dk-chat-anhang-meta">{{ a.groesseText }}</span>
        </span>
        <a
          class="dk-chat-anhang-laden"
          :href="a.url"
          :download="a.dateiname"
          :aria-label="`${TEXTE.herunterladen}: ${a.dateiname}`"
          :title="TEXTE.herunterladen"
        ><DkSymbol name="herunterladen" :groesse="16" /></a>
      </span>
    </li>
  </ul>
</template>

<script setup>
/**
 * ChatAnhangBlase — zeigt die Anhänge einer Nachricht (CHAT-12b).
 *
 * Der Baustein ZEICHNET nur: welche Anhänge eine Nachricht trägt und wie sie
 * gezeigt werden, entscheidet `anzeigen` hier aus der Serverliste
 * (`anhaenge: [{name, dateiname, mime, groesse}]`) mit den Regeln aus
 * `anhaenge.mjs` (`zeilenAnhaenge`, `anhangArt`, `anhangUrl`). Eine GELÖSCHTE
 * Nachricht liefert keine Anhänge — die Blase fragt gar nicht erst.
 *
 * Die Kennung eines Anhangs ist eine Adresse, kein Geheimnis: sie geht als
 * `?name=` an `chat.anhang`, und der Server prüft bei JEDEM Abruf die Rechte
 * (fremdes Gespräch, gelöschte Nachricht, offener Anhang → 404). Deshalb steht
 * sie offen im `src`/`href`.
 */
import { computed } from 'vue'
import DkSymbol from '../ui/DkSymbol.vue'
import { TEXTE, anhangArt, anhangName, anhangSymbol, anhangUrl, groesseText, zeilenAnhaenge } from './anhaenge.mjs'

const props = defineProps({
  /** Die Nachricht des Verlaufs (Feld `anhaenge`). */
  nachricht: { type: Object, required: true },
  /**
   * Die Adress-Basis — `apiUrl` aus `shared/basis.js`, von der Seite
   * hineingereicht (`(methode) => …`). Ohne sie entsteht der nackte Pfad; die
   * Seite übergibt sie immer, damit der Betriebs-Präfix gilt.
   */
  basis: { type: Function, default: null },
})

/** Die Anhänge, fertig zum Zeichnen — in der Reihenfolge des Servers. */
const posten = computed(() => zeilenAnhaenge(props.nachricht).map((a) => ({
  ...a,
  dateiname: anhangName(a),
  art: anhangArt(a),
  symbol: anhangSymbol(a),
  groesseText: groesseText(a.groesse),
  url: anhangUrl(a.name, props.basis),
})))
</script>

<style scoped>
.dk-chat-anhaenge-blase {
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
  margin: var(--sp-2) 0 0;
  padding: 0;
  list-style: none;
}
.dk-chat-anhang { max-width: 100%; }
/* Die Vorschau: feste Höchsthöhe, volle Breite nur bis zur Blasenbreite —
   kein Sprung im Verlauf, wenn das Bild nachgeladen wird (die Höhe steht in
   der Gestaltung, nicht im Bild). */
.dk-chat-anhang-bild { display: block; line-height: 0; }
.dk-chat-anhang-vorschau {
  display: block;
  max-width: 100%;
  max-height: calc(var(--sp-7) * 5);
  border-radius: var(--radius-sm);
  border: var(--rahmen-breite) solid var(--line);
  object-fit: cover;
  background: var(--surface-2);
}
.dk-chat-anhang-ton {
  display: block;
  width: 100%;
  max-width: calc(var(--sp-8) * 5);
  min-height: var(--treffer-handy);
}
.dk-chat-anhang-zeile {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  min-height: var(--treffer-handy);
  padding: var(--sp-1) var(--sp-2);
  border: var(--rahmen-breite) solid var(--line);
  border-radius: var(--radius-sm);
  background: var(--surface-2);
  color: var(--text);
}
.dk-chat-anhang-symbol { display: flex; color: var(--muted); flex: none; }
.dk-chat-anhang-text {
  display: flex;
  flex-direction: column;
  min-width: 0;
  flex: 1;
}
.dk-chat-anhang-name {
  font-size: var(--fs-14);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.dk-chat-anhang-meta { font-size: var(--fs-12); color: var(--muted); }
/* Die Trefferfläche des Herunterladens ist 44 px — am Handy mit dem Finger
   zu treffen, am Desktop unauffällig. */
.dk-chat-anhang-laden {
  display: flex;
  align-items: center;
  justify-content: center;
  width: var(--treffer-handy);
  height: var(--treffer-handy);
  flex: none;
  margin: calc(-1 * var(--sp-1)) calc(-1 * var(--sp-2)) calc(-1 * var(--sp-1)) 0;
  border-radius: var(--radius-sm);
  color: var(--marke-ink, var(--text));
}
.dk-chat-anhang-laden:focus-visible { outline: var(--rahmen-breite) solid var(--focus-ring); outline-offset: var(--sp-1); }
</style>
