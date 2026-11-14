<template>
  <!-- UX3i (Entwurf A4, Punkt 4): rechte Spalte „Zu prüfen“ — NUR für
       Moderatoren. Sie zeigt die wartenden Termine aus DENSELBEN Daten, die
       die Tafel „Zu prüfen“ schon lädt (`getBoardData` → `vorschlaege`);
       kein neuer Endpunkt.
       Für alle anderen gibt es diese Spalte nicht — das Raster nimmt die
       Breite (die Seite entscheidet das, nicht dieses Bauteil). -->
  <aside class="dk-pruef-panel" aria-labelledby="dk-pruef-panel-titel">
    <header class="dk-pruef-panel-kopf">
      <div class="dk-pruef-panel-kopftext">
        <h2 id="dk-pruef-panel-titel" class="dk-pruef-panel-titel">
          Zu prüfen <span v-if="zahl !== null" class="dk-pruef-panel-zahl">({{ zahl }})</span>
        </h2>
        <!-- A4: der ruhige Untertitel sagt, WOHER die Einträge kommen. -->
        <p class="dk-pruef-panel-untertitel">Von Gruppen eingetragen</p>
      </div>
      <a class="dk-pruef-panel-alle" href="#/kalender/pruefen" @click.prevent="zurTafel">
        Alle ansehen
        <span class="dk-pruef-panel-pfeil" aria-hidden="true">
          <DkSymbol name="weiter" :groesse="14" />
        </span>
      </a>
    </header>

    <DkSkelett v-if="loading" kurz form="zeilen" :anzahl="3" text="Zu prüfende Termine werden geladen" />

    <p v-else-if="!eintraege.length" class="dk-pruef-panel-leer">
      Nichts zu prüfen. Neue Vorschläge erscheinen hier, sobald jemand einen
      Termin einträgt.
    </p>

    <ul v-else class="dk-pruef-panel-liste">
      <li v-for="e in eintraege" :key="e.id" class="dk-pruef-panel-zeile">
        <a
          class="dk-pruef-panel-link"
          href="#/kalender/pruefen"
          :aria-label="'Termin „' + (e.titel || 'ohne Titel') + '“ prüfen'"
          @click.prevent="zurTafel"
        >
          <!-- A4: Datum oben, Titel, darunter „von … · vor …“ — die Herkunft
               steht VOLLSTÄNDIG (Review 07.11. Punkt 8), nicht abgeschnitten. -->
          <span class="dk-pruef-panel-datum">{{ e.datum }}</span>
          <span class="dk-pruef-panel-titel-zeile">{{ e.titel }}</span>
          <span v-if="e.herkunft" class="dk-pruef-panel-herkunft">{{ e.herkunft }}</span>
          <!-- UI-R4: WELCHE Stufe dran ist — dieselbe Zeile wie auf der Karte. -->
          <span v-if="e.wartet" class="dk-pruef-panel-wartet">{{ e.wartet }}</span>
          <span class="dk-pruef-panel-aktion">
            Prüfen
            <span class="dk-pruef-panel-pfeil" aria-hidden="true"><DkSymbol name="weiter" :groesse="14" /></span>
          </span>
        </a>
      </li>
    </ul>

    <p v-if="eintraege.length > sichtbar" class="dk-pruef-panel-mehr">
      {{ weitereText(eintraege.length - sichtbar) }} in „Zu prüfen“
    </p>

    <!-- A4: der Fußtext erklärt den Bereich — einmal, ruhig, am Ende.
         UI-R4: „bis ein Administrator sie freigibt“ stimmt bei Stufen nicht
         (es prüft die zuständige Stufe, nicht immer der Administrator). -->
    <p class="dk-pruef-panel-fuss">
      Termine aus Gruppen erscheinen hier, bis die zuständige Stufe sie freigegeben hat.
    </p>
  </aside>
</template>

<script setup>
/**
 * KalenderPruefPanel — rechte Spalte „Zu prüfen“ im Kalender (UX3i, A4).
 *
 * Datenquelle: `getBoardData()` aus `api/kanbanApi.js` — derselbe Aufruf, den
 * die Tafel „Zu prüfen“ macht (UX3d). Hier wird NICHTS entschieden und nichts
 * freigegeben: jede Zeile führt auf die Tafel, wo Prüfen stattfindet.
 *
 * Sichtbarkeit: Nur Moderatoren bekommen dieses Bauteil überhaupt gerendert
 * (die Seite prüft `can_moderate`). Die Komponente selbst zeigt nichts, wenn
 * sie keine Daten bekommt.
 */
import { computed, onMounted, ref } from 'vue'
import DkSkelett from '../ui/DkSkelett.vue'
import DkSymbol from '../ui/DkSymbol.vue'
import { getBoardData } from '../../api/kanbanApi.js'
import { navigate } from '../../router.js'
import { weitereText } from './chipText.mjs'
import { pruefZeile, PRUEF_ANZEIGE } from './pruefZeile.mjs'
// UI-R4b (Punkt 7b): EIN gemeinsamer Lader je Seite.
import { stufenTitelEinmalLaden } from './freigabeStufenReaktiv.mjs'
import { apiCall } from '../../composables/useApi.js'

const props = defineProps({
  /**
   * Zahl „Zu prüfen“ von der Seite (`null` = unbekannt). Sie kommt aus
   * `getModerationCount` — der Server zählt dieselbe Menge, die dieses Panel
   * zeigt (offene Stufe, die der Aufrufer prüfen darf). Das Panel führt
   * deshalb KEINE eigene Zahl mehr (R-12).
   */
  zahl: { type: Number, default: null },
  /** Wie viele Zeilen im Panel stehen (Rest als „+n weitere“). */
  sichtbar: { type: Number, default: PRUEF_ANZEIGE },
})

const loading = ref(true)
const rohdaten = ref([])

const eintraege = computed(() => rohdaten.value.slice(0, props.sichtbar))

function zurTafel() {
  navigate('#/kalender/pruefen')
}

/** Vorschläge laden und in Panel-Zeilen übersetzen. */
async function laden() {
  try {
    const daten = await getBoardData()
    const liste = Array.isArray(daten?.vorschlaege) ? daten.vorschlaege : []
    // UI-R4: Je Zeile die Warteline („wartet auf Freigabe für: …“). Gezeigt wird nur, was
    // der Aufrufer auf der offenen Stufe prüfen darf (`darf_pruefen`) — die
    // Zahl dazu liefert der Server (`getModerationCount`, R-12), nicht das
    // Panel: zwei eigene Zählungen liefen sonst auseinander.
    rohdaten.value = liste
      .filter(e => e?.darf_pruefen === true)
      .map(pruefZeile)
      .filter(Boolean)
  } catch {
    // Ein Fehler bleibt still (I5: kein Lärm in einer Kennzahl) — der
    // Leerzustand sagt dann, dass nichts zu prüfen ist.
    rohdaten.value = []
  }
}

onMounted(async () => {
  // Die Stufen-Titel kommen vom Server (`get_rollen_erklaerung`).
  await Promise.all([laden(), stufenTitelEinmalLaden(apiCall)])
  loading.value = false
})

defineExpose({ rohdaten, laden })
</script>

<style scoped>
.dk-pruef-panel {
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
  padding: var(--karte-innen, var(--sp-4));
  border-radius: var(--radius-lg);
  background: var(--surface);
  box-shadow: var(--schatten-karte);
  border: var(--karte-rand) solid var(--rahmen-farbe);
  min-width: 0;
}
.dk-pruef-panel-kopf {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--sp-2);
}
.dk-pruef-panel-titel {
  margin: 0;
  font-size: var(--fs);
  font-weight: var(--fw-fett);
  color: var(--text);
}
/* Gold ist Statusfarbe („zu prüfen“) — hier nur als Zahl, nicht als Fläche. */
.dk-pruef-panel-zahl { color: var(--warn); font-variant-numeric: tabular-nums; }
.dk-pruef-panel-alle,
.dk-pruef-panel-aktion {
  display: inline-flex;
  align-items: center;
  gap: var(--sp-1);
  color: var(--link);
  font-size: var(--fs-sm);
  font-weight: var(--fw-mittel);
  text-decoration: none;
  white-space: nowrap;
}
.dk-pruef-panel-alle:hover { color: var(--link-hover); text-decoration: underline; }
/* Das Symbol steht exakt auf der Textlinie (Auflage der Entwürfe):
   inline-flex + align-items:center, feste Größe 14. */
.dk-pruef-panel-pfeil { display: inline-flex; align-items: center; flex: none; }
.dk-pruef-panel-liste {
  display: flex;
  flex-direction: column;
  gap: var(--sp-1);
  margin: 0;
  padding: 0;
  list-style: none;
}
.dk-pruef-panel-zeile { min-width: 0; }
.dk-pruef-panel-link {
  display: flex;
  flex-direction: column;
  gap: var(--sp-1);
  min-height: var(--control-h);
  padding: var(--sp-2);
  border-radius: var(--radius);
  color: var(--text);
  text-decoration: none;
}
.dk-pruef-panel-link:hover { background: var(--surface-hover); }
.dk-pruef-panel-link:focus-visible { outline: 2px solid var(--focus-ring); outline-offset: 1px; }
.dk-pruef-panel-datum {
  font-size: var(--fs-sm);
  color: var(--muted);
  font-variant-numeric: tabular-nums;
}
.dk-pruef-panel-titel-zeile {
  font-size: var(--fs);
  font-weight: var(--fw-mittel);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.dk-pruef-panel-herkunft {
  font-size: var(--fs-sm);
  color: var(--muted);
  /* Review 07.11. Punkt 8: „von … · vor …“ steht VOLLSTÄNDIG — umbrechen
     statt abschneiden (die Zeile ist die Begründung, warum etwas wartet). */
  overflow-wrap: anywhere;
}
/* UI-R4: „wartet auf Freigabe für: …“ — gleiche Zeile wie auf der Karte. */
.dk-pruef-panel-wartet {
  font-size: var(--fs-sm);
  font-weight: var(--fw-mittel);
  color: var(--warn);
  overflow-wrap: anywhere;
}
.dk-pruef-panel-untertitel {
  margin: var(--sp-1) 0 0;
  font-size: var(--fs-sm);
  color: var(--muted);
}
.dk-pruef-panel-kopftext { min-width: 0; }
/* Fußtext (A4): erklärt den Bereich, ruhig und abgesetzt. */
.dk-pruef-panel-fuss {
  margin: 0;
  padding-top: var(--sp-2);
  border-top: var(--rahmen-breite) solid var(--rahmen-farbe-leise);
  font-size: var(--fs-sm);
  color: var(--muted);
}
.dk-pruef-panel-leer,
.dk-pruef-panel-mehr {
  margin: 0;
  font-size: var(--fs-sm);
  color: var(--muted);
}
.dk-pruef-panel-mehr { padding-left: var(--sp-2); }
/* Review 07.11. Punkt 8: Das „⋯“ (hier „Alle ansehen“) muss deutlich lesbar
   sein — Link-Farbe und Gewicht statt blassem Grau. */
.dk-pruef-panel-alle { min-height: var(--control-h); }
.dk-pruef-panel-alle:focus-visible { outline: 2px solid var(--focus-ring); outline-offset: 2px; }
/* K4: bei Fingerbedienung sind die Zeilen 44 px hoch. */
@media (pointer: coarse) {
  .dk-pruef-panel-link { min-height: 44px; }
}
</style>
