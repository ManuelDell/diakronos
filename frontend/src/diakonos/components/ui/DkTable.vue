<template>
  <div class="dk-ui-table-wrap">
    <table class="dk-ui-table" :class="{ 'has-aktion': hatAktion }">
      <thead v-if="spalten.length">
        <tr>
          <th v-for="s in spalten" :key="s.key" :style="s.width ? { width: s.width } : null"
              :class="{ 'is-num': s.numeric, 'is-aktion': s.aktion }">{{ s.label }}</th>
        </tr>
      </thead>
      <tbody>
        <slot />
      </tbody>
    </table>
    <DkEmpty v-if="leer" :title="leerTitel" :text="leerText">
      <template v-if="$slots.leer" #aktion><slot name="leer" /></template>
    </DkEmpty>
  </div>
</template>

<script setup>
/**
 * DkTable — Tabelle (Stil A) mit Kopf, Zeilen, leerem Zustand und
 * waagerechtem Scrollen. Zeilen kommen über den Standard-Slot
 * (<tr><td>…</td></tr>). Spalten definieren die Kopfzeile.
 *
 * spalten: [{ key, label, width?, numeric?, aktion? }]
 *   aktion: Die Zelle enthält Knöpfe. Sie bekommt eine Mindestbreite und
 *           bricht um (`.is-aktion`, siehe FIX-4). Zugleich schaltet diese
 *           Angabe die Tabelle auf `table-layout: fixed` (`.has-aktion`) —
 *           nur dann, denn `fixed` teilt die Breite gleichmäßig auf und würde
 *           Tabellen mit vielen Textspalten (z.B. Mitgliederliste mit 7
 *           Spalten) die Zellen zu eng machen. Ohne `aktion` bleibt es bei
 *           `auto`, die Spalten richten sich dann wie bisher nach dem Inhalt.
 *
 * Nur Tokens, keine festen Farben (waagerechtes Scrollen ist echte
 * Funktionalität und bleibt erlaubt).
 */
import { computed } from 'vue'
import DkEmpty from './DkEmpty.vue'

const props = defineProps({
  spalten: { type: Array, default: () => [] },
  leer: Boolean,
  leerTitel: { type: String, default: 'Keine Einträge' },
  leerText: { type: String, default: '' },
})

/** FIX-4: `fixed` nur, wenn eine Spalte Knöpfe trägt (siehe Kommentar oben). */
const hatAktion = computed(() => props.spalten.some((s) => s && s.aktion))

</script>

<style scoped>
.dk-ui-table-wrap {
  width: 100%;
  overflow-x: auto;
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
  background: var(--surface);
}
.dk-ui-table {
  width: 100%;
  max-width: 100%;
  min-width: 640px;
  border-collapse: collapse;
  /* UX1b (Prinzip Ä3): Ziffern in Tabellen gleiche Breite — Spalten stehen
     sonst nicht untereinander (Wert aus dem Token in tokens.css). */
  font-variant-numeric: var(--fs-tabular);
  /* FIX-4 (Befund DMB-9a25839dfda4): Seitentabellen hatten `auto`; der Browser
     verteilte die Breite nach Inhalt — die Aktionszelle mit zwei
     `white-space: nowrap`-Knöpfen schob sich dabei über die Nachbarzelle (am
     Handy sichtbar). `fixed` gilt deshalb NUR für Tabellen mit Aktionsspalte
     (`.has-aktion`): dann teilen sich die Spalten die Tabellenbreite
     gleichmäßig, Text bricht in seiner Zelle um, Knöpfe brechen in ihrer Zelle
     um (`.is-aktion`). Tabellen ohne Aktionsspalte (z.B. die Mitgliederliste
     mit sieben Spalten) bleiben bei `auto` — `fixed` würde dort jede Zelle auf
     einen Bruchteil der Breite stutzen und lange Inhalte umbrechen. Der
     Überlauf bleibt in beiden Fällen im `.dk-ui-table-wrap`. */
}
.dk-ui-table.has-aktion { table-layout: fixed; }

.dk-ui-table thead th {
  text-align: left;
  font-size: var(--fs-xs);
  font-weight: 600;
  letter-spacing: .06em;
  text-transform: uppercase;
  color: var(--subtle);
  padding: 10px calc(var(--pad) * 1.2);
  background: var(--surface-2);
  border-bottom: 1px solid var(--line);
  white-space: nowrap;
}
.dk-ui-table thead th.is-num { text-align: right; }
.dk-ui-table tbody :deep(td) {
  height: var(--row-h);
  padding: 0 calc(var(--pad) * 1.2);
  border-top: 1px solid var(--line);
  vertical-align: middle;
  color: var(--text);
}
.dk-ui-table tbody :deep(tr:first-child td) { border-top: none; }
.dk-ui-table tbody :deep(tr:hover td) { background: var(--surface-hover); }

/* FIX-4 (Befund DMB-9a25839dfda4): Aktionsspalte. Die Knöpfe der Zeile
   stehen dort nebeneinander und brechen bei knapper Breite untereinander um,
   statt über die Nachbarzelle zu laufen. Die Mindestbreite ist die Breite
   zweier kleiner Knöpfe plus Abstand — sie gilt dem `<th>` (Spaltenbreite bei
   `table-layout: fixed`) und der Zelle. Knöpfe tragen `white-space: nowrap`
   (DkButton); umgebrochen wird deshalb in der Zelle: sie ist eine echte
   Tabellenzelle (`table-cell`) und leitet den Umbruch an ihren Inhalt weiter
   — ein `display: flex` auf dem `<td>` würde die Zelle aus dem Tabellensatz
   lösen und Spaltenbreite/-höhe verfälschen. Zellen ohne diese Klasse bleiben
   unverändert. */
.dk-ui-table th.is-aktion,
.dk-ui-table td.is-aktion {
  width: 200px;
  min-width: 200px;
  vertical-align: top;
}
.dk-ui-table th.is-aktion { white-space: normal; }
.dk-ui-table tbody :deep(td.is-aktion) {
  height: auto;
  padding-top: var(--sp-2);
  padding-bottom: var(--sp-2);
}
/* Inhalt der Aktionszelle: Knöpfe und ein etwaiger Wrapper (die Seiten legen
   ihre Knöpfe teils in ein eigenes <div>) brechen als Flex-Zeile um. */
.dk-ui-table tbody :deep(td.is-aktion > *) {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--sp-2);
  min-width: 0;
}
</style>
