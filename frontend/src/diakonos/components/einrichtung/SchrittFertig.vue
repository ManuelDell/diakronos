<template>
  <!-- ON-3 (W2, Schritt 6 „Fertig“, Entwurf 09/15): „Diakronos ist bereit“,
       darunter die Checkliste aus `einrichtung.status`. Erledigte Punkte grün,
       offene amber mit „Einrichten“ (Ziel vom Server, `ziel`). Beim ersten
       Durchlauf wird hier abgeschlossen; im Betrieb (W4) ist dieselbe Liste die
       Seite „Einstellungen → Einrichtung“. -->
  <section class="fertig">
    <div class="fertig-zeichen" :class="{ 'ist-offen': offenAnzahl > 0 }" aria-hidden="true">
      <AssistentSymbol name="haken" :size="29.12" :strich="1.8" />
    </div>
    <h1 class="fertig-titel">{{ ueberschrift }}</h1>
    <p class="fertig-unterzeile">{{ unterzeile }}</p>

    <ul class="fertig-liste">
      <li v-for="punkt in punkte" :key="punkt.schluessel" class="fertig-zeile">
        <span class="fertig-kreis" :class="punkt.erledigt ? 'ist-erledigt' : 'ist-offen'" aria-hidden="true">
          <AssistentSymbol
            v-if="punkt.erledigt"
            name="haken"
            :size="13.52"
            :strich="2.2"
          />
          <span v-else class="fertig-marke"></span>
        </span>
        <span class="fertig-text">
          <span class="fertig-name">{{ punkt.titel }}</span>
          <span class="fertig-hinweis">{{ punkt.hinweis }}</span>
        </span>
        <a
          v-if="!punkt.erledigt && punkt.ziel"
          :href="punkt.ziel"
          class="fertig-einrichten"
        >Einrichten</a>
        <span v-else class="fertig-status">{{ punkt.erledigt ? 'Erledigt' : '' }}</span>
      </li>
    </ul>

    <div class="fertig-aktionen">
      <DkButton
        v-if="!abgeschlossen"
        variant="primary"
        :loading="speichert"
        @click="$emit('abschliessen')"
      >Zur Übersicht</DkButton>
      <DkButton v-else variant="primary" @click="$emit('uebersicht')">Zur Übersicht</DkButton>
      <p class="fertig-fussnote">Einstellungen → Einrichtung</p>
    </div>
  </section>
</template>

<script setup>
/**
 * Fertig-Schirm (ON-3/W2, Entwurf 09 + 15).
 *
 * Die Checkliste und ihre Texte kommen AUSSCHLIESSLICH aus
 * `einrichtung.status` (Server = eine Quelle der Wahrheit, ON-2). Hier stehen
 * keine Titel, Hinweise oder Ziele aus dem Entwurf mehr: der Entwurf zeigt sie
 * nur, der Server liefert sie. Neu berechnet wird beim Aufruf der Seite.
 *
 * Die Unterzeile nennt die Zahl der offenen Punkte aus `offene_anzahl`; ist
 * alles erledigt, steht dort der Erledigt-Satz (wie in `fortschrittText`).
 */
import { computed } from 'vue'
import DkButton from '../ui/DkButton.vue'
import AssistentSymbol from './AssistentSymbol.vue'

const props = defineProps({
  punkte: { type: Array, default: () => [] },
  offenAnzahl: { type: Number, default: 0 },
  gesamtAnzahl: { type: Number, default: 0 },
  abgeschlossen: Boolean,
  speichert: Boolean,
})
defineEmits(['abschliessen', 'uebersicht'])

const ueberschrift = 'Diakronos ist bereit'

const unterzeile = computed(() => {
  const offen = Number(props.offenAnzahl) || 0
  const gesamt = Number(props.gesamtAnzahl) || 0
  if (!props.abgeschlossen) {
    // Entwurf 09: „Die Ersteinrichtung ist abgeschlossen. Drei Punkte sind noch
    // offen und lassen sich jederzeit nachholen.“ — die Zahl kommt aus den
    // echten Daten, der Satz bleibt der des Entwurfs.
    return 'Die Ersteinrichtung ist abgeschlossen.'
  }
  if (offen === 0) return `Alle ${gesamt} Punkte sind erledigt.`
  return `${offen} ${offen === 1 ? 'Punkt ist' : 'Punkte sind'} noch offen – jederzeit unter Einstellungen → Einrichtung nachholbar.`
})
</script>

<style scoped>
.fertig { display: flex; flex-direction: column; gap: var(--sp-3); align-items: flex-start; }
.fertig-zeichen {
  width: 56px;
  height: 56px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  background: var(--ok-soft);
  color: var(--ok);
  margin-bottom: var(--sp-2);
}
.fertig-zeichen.ist-offen { background: var(--warn-soft); color: var(--warn); }
/* ON-3/W5: Symbol mittig (grid/place-items) — der Entwurf hatte es leicht
   nach unten versetzt gezeichnet. */
.fertig-zeichen :deep(svg) { display: block; }
.fertig-titel { margin: 0; font-size: var(--fs-h1); font-weight: var(--fw-h); color: var(--text); line-height: 1.25; }
.fertig-unterzeile {
  margin: 0;
  font-size: var(--fs-fliess);
  color: var(--muted);
  line-height: 1.5;
  max-width: 640px;
}
.fertig-liste {
  list-style: none;
  margin: var(--sp-3) 0 0;
  padding: var(--sp-2) var(--sp-4);
  width: 100%;
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
  background: var(--surface-2);
}
.fertig-zeile {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  padding: var(--sp-2) 0;
  border-bottom: 1px solid var(--line);
}
.fertig-zeile:last-child { border-bottom: 0; }
.fertig-kreis {
  flex: none;
  width: var(--check-kreis);
  height: var(--check-kreis);
  border-radius: 50%;
  display: grid;
  place-items: center;
}
.fertig-kreis :deep(svg) { display: block; }
.fertig-kreis.ist-erledigt { background: var(--ok-soft); color: var(--ok); }
.fertig-kreis.ist-offen { background: var(--warn-soft); }
.fertig-marke {
  width: 13px;
  height: 13px;
  border-radius: 50%;
  background: var(--warn);
}
/* ON-3 (Nachtrag Mobil): `flex: 1 1 auto` MIT `min-width: 0` — sonst hat die
   Textspalte am Handy die Breite 0 (`flex-basis: auto` bei langem Inhalt) und
   Titel/Hinweis umbrechen zeichenweise über den Knopf. `overflow-wrap` ist die
   zweite Sicherung für sehr schmale Geräte. */
.fertig-text {
  display: flex;
  flex-direction: column;
  flex: 1 1 auto;
  min-width: 0;
  overflow-wrap: anywhere;
}
.fertig-name { font-size: var(--fs); font-weight: 700; color: var(--text); }
.fertig-hinweis { font-size: var(--fs-sm); color: var(--subtle); }
.fertig-einrichten {
  flex: none;
  display: inline-flex;
  align-items: center;
  padding: var(--sp-1) var(--sp-3);
  min-height: 30px;
  border: 1px solid var(--line-strong);
  border-radius: var(--radius);
  background: var(--surface);
  color: var(--text);
  font-size: var(--fs-sm);
  font-weight: 700;
  text-decoration: none;
}
.fertig-einrichten:hover { background: var(--surface-hover); }
.fertig-einrichten:focus-visible { outline: 2px solid var(--focus-ring); outline-offset: 1px; }
.fertig-status { flex: none; font-size: var(--fs-sm); color: var(--subtle); }
.fertig-aktionen {
  display: flex;
  align-items: center;
  gap: var(--sp-4);
  flex-wrap: wrap;
  margin-top: var(--sp-4);
}
.fertig-fussnote { margin: 0; font-size: var(--fs-sm); color: var(--subtle); }

@media (max-width: 600px) {
  .fertig-kreis { width: var(--check-kreis-mobil); height: var(--check-kreis-mobil); }
  .fertig-unterzeile { font-size: var(--fs); }
  /* Handy (Entwurf 15): Kreis + Text in EINER Zeile, „Einrichten" darunter.
     Vorher teilten sich Text und Knopf die Zeile — bei 390 px blieb für den
     Text 0 px Breite, Titel und Hinweis brachen zeichenweise um (gemessen:
     `scrollWidth > clientWidth`). Das Kennwort „Erledigt" entfällt ohnehin
     (der grüne Haken sagt dasselbe, Entwurf 15 zeigt es nicht). */
  .fertig-zeile {
    display: grid;
    grid-template-columns: var(--check-kreis-mobil) minmax(0, 1fr);
    grid-template-areas: 'kreis text' '. knopf';
    align-items: start;
    column-gap: var(--sp-3);
    row-gap: var(--sp-1);
  }
  .fertig-kreis { grid-area: kreis; }
  .fertig-text { grid-area: text; }
  .fertig-einrichten { grid-area: knopf; justify-self: start; }
  .fertig-status { display: none; }
  .fertig-aktionen { flex-direction: column; align-items: stretch; }
  .fertig-aktionen :deep(.dk-ui-btn) { width: 100%; }
}
</style>
