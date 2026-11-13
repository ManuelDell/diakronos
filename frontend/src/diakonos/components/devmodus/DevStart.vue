<template>
  <!-- DM1: kleiner Knopf zum EINSCHALTEN des Dev-Modus. Er erscheint NUR,
       wenn der Server den Dev-Modus eingeschaltet hat und der Benutzer
       berechtigt ist, aber noch keine Dev-Sitzung laeuft (`devStartZeigen`
       in App.vue).

       DEVBADGE-1: Am Handy (Handy-Lage `.dk-app--handy`) verdeckte das
       Abzeichen unten rechts den Knopf „Termin anlegen“ (FAB, Kalender) und
       stand der unteren Leiste im Weg. Eine schwebende Plakette oben rechts
       war nach MESSUNG auch nicht frei (Kalender: `.dk-mobilkopf` reicht bis
       382 px). Deshalb die von der Karte erlaubte zweite Form: ein EINTRAG IM
       KOPF statt eines schwebenden Elements (`dk-dev-start--kopf`, nur in der
       Handy-Lage) — die Trefferflaeche bleibt 44 px (`--treffer-handy`, kein
       8x8-px-Ziel).
       Der Text „Dev-Modus an“ erscheint dort, wo Platz ist: am Desktop voll,
       in der Kopfzeile als kleine Plakette ohne Wort (Punkt im 44-px-Feld,
       Review 11.11. Punkt 2: die Wortform quetschte den Seitentitel auf
       „Kaler…“). Der Vorlesename bleibt in beiden Faellen „Dev-Modus an …“
       und enthaelt damit den sichtbaren Text (WCAG 2.5.3, Punkt 3). -->
  <button class="dk-dev-start" :class="{ 'dk-dev-start--kopf': imKopf }"
          type="button" :title="TITEL" :aria-label="VORLESENAME"
          :aria-busy="laeuft ? 'true' : 'false'"
          data-dk-dev @click="einschalten">
    <span class="dk-dev-start-punkt" aria-hidden="true" />
    <span class="dk-dev-start-text">Dev-Modus an</span>
  </button>
</template>

<script setup>
import { ref } from 'vue'

import { devmodusApi, devmodusKuerzel, sttVerfuegbar, zustandSetzen } from '../../composables/useDevmodus.js'
import { showToast } from '../../composables/useToast.js'

/**
 * DEVBADGE-1: Die Lage kommt von AUSSEN — `App.vue` setzt den Knopf in der
 * Handy-Lage in den Slot `dev-knopf` der App-Kopfzeile und sagt es der
 * Komponente ueber `imKopf`. Die Komponente raet die Lage NICHT selbst (keine
 * zweite Lageabfrage neben `useHandyLage()`, DEV-B6).
 *
 * Grund fuer die Klasse statt eines Lage-Blocks in diesem Baustein: die
 * Bedingungen fuer ein Stueck Code, das auch in der Kopfzeile steht, sind
 * nicht eindeutig (Vites Baustein-Zuordnung entscheidet, ob die Regeln dieses
 * Bausteins ein- oder ausgeklammert werden) — eine vom Aufrufer gesetzte
 * Klasse ist davon unabhaengig und im Quelltext nachpruefbar.
 */
const props = defineProps({
  imKopf: { type: Boolean, default: false },
})
void props

/**
 * WCAG 2.5.3 („Label in Name“, Review 11.11. Punkt 3): Der Vorlesename MUSS
 * den sichtbaren Text enthalten — vorher hiess er „Dev-Modus einschalten“,
 * waehrend am Desktop sichtbar „Dev-Modus an“ stand. Jetzt beginnt er mit
 * genau diesem Text; der Zusatz sagt, was der Klick tut.
 */
const VORLESENAME = 'Dev-Modus an — einschalten'
const TITEL = 'Dev-Modus an — einschalten'

const laeuft = ref(false)

async function einschalten() {
  if (laeuft.value) return
  laeuft.value = true
  try {
    const daten = await devmodusApi.sitzungStarten()
    zustandSetzen(true, daten?.kuerzel || 'Strg+Shift+F', sttVerfuegbar.value)
    showToast('Dev-Modus an — ' + devmodusKuerzel.value + ' zum Auswählen', 'success')
  } catch {
    showToast('Dev-Modus konnte nicht eingeschaltet werden.', 'error')
  } finally {
    laeuft.value = false
  }
}
</script>

<style scoped>
/* ON-0b: Werte kommen aus tokens.css (--dev-* ist die Werkzeug-Gruppe). */
.dk-dev-start {
  position: fixed;
  right: 10px;
  bottom: 10px;
  z-index: 2147482900;
  display: flex;
  align-items: center;
  gap: 6px;
  font-family: var(--font);
  font-size: var(--fs-sm);
  line-height: 1.2;
  cursor: pointer;
  border: 1px solid var(--dev-flaeche-rand);
  background: var(--dev-flaeche);
  color: var(--dev-rot-ink);
  padding: 5px 9px;
  border-radius: var(--badge-r);
  box-shadow: var(--dev-flaeche-schatten);
}
.dk-dev-start-punkt {
  width: 8px; height: 8px; border-radius: 50%; background: var(--dev-rot);
}
/* DEVBADGE-1: Wo Platz ist, steht „Dev-Modus an“ — die Wortform faellt nur
   in der Kopfzeilen-Form weg (Regel unten). Bewusst KEIN `display: none` am
   Text im Grundblock: das war der alte Fehler (ein spaeterer Block mit
   gleicher Spezifitaet konnte ihn nicht mehr aufheben). */
.dk-dev-start-text { display: inline; }
/* DEVBADGE-1b (Review Opus, Punkt 5): Der frueher hier stehende Lade-Knoten
   `.dk-dev-start-laeuft` war IMMER `display: none` — der Ladezustand `laeuft`
   war damit nie sichtbar. Statt eines toten Knotens zeigt ihn jetzt der
   PUNKT: waehrend der Anfrage wird er hohl (Rahmen statt Fuellung) und
   pulsiert; `aria-busy` am Knopf sagt es der Vorlesehilfe. Der Doppelklick-
   Schutz bleibt `laeuft` im Skript (unveraendert).
   `outline` statt `border`, damit das 8-px-Raster (kein Verschieben beim
   Umschalten) und der feste 44-px-Kasten der Kopfzeilen-Form erhalten
   bleiben. */
.dk-dev-start[aria-busy="true"] .dk-dev-start-punkt {
  background: transparent;
  outline: 2px solid var(--dev-rot);
  outline-offset: -2px;
  animation: dk-dev-start-puls 1s ease-in-out infinite;
}
@keyframes dk-dev-start-puls {
  50% { opacity: 0.35; }
}
/* Der Ring ist eine reine Zierde (die Meldung traegt `aria-busy`); bei
   „Bewegung reduzieren“ bleibt die hohle Form, das Pulsieren entfaellt. */
@media (prefers-reduced-motion: reduce) {
  .dk-dev-start[aria-busy="true"] .dk-dev-start-punkt { animation: none; }
}
/* DEVBADGE-1b (Review Opus, Punkt 6): Die frueher hier stehende Regel
   `.dk-app--handy .dk-dev-start:not(.dk-dev-start--kopf) { bottom: … }` war
   toter Code — die feste Form steht in der Handy-Lage nur noch in der
   Einrichtung (`#/einrichtung`, Vollbild ohne Kopfzeile); dort gibt es keine
   untere Leiste, der Abstand griff also nie. Entfernt, statt eine Bedingung
   zu pflegen, die nie greift. */

/* ══════════════════════════════════════════════════════════════════════════
   DEVBADGE-1 · Handy-Lage — KEIN schwebendes Element
   ══════════════════════════════════════════════════════════════════════════
   ENTSCHEIDUNG nach MESSUNG (12 Messungen, 390 hell/dunkel, Kalender ·
   Mitglieder · Gruppen · Start, tools/demo/devbadge1-abnahme.mjs): eine
   schwebende Plakette oben rechts unter der Kopfzeile war NICHT frei — auf
   dem Kalender liegt dort der Kopf des Mobil-Kalenders (`.dk-mobilkopf`,
   Segmente + zwei 44-px-Werkzeuge, rechts bis 382 px), sie traf „⋯“ und den
   Kalender-Auswahlknopf. Also die zweite von der Karte erlaubte Form:
   ein EINTRAG IM KOPF statt eines schwebenden Elements (die Karte: „ODER als
   Eintrag im Kopf/Menü (dann kein schwebendes Element)“).

   Der Knopf verlaesst damit den festen Rahmen: `App.vue` setzt ihn in der
   Handy-Lage in den Slot `dev-knopf` der App-Kopfzeile (`AppTopbar`), also
   hinter Glocke und Trennstrich. Sichtbar bleibt der Punkt im 44×44-px-Feld
   (Rand und Schatten weg) — kein 8×8-px-Ziel (Bedingung der Karte) und kein
   Wort, das den Seitentitel verdraengt (Review 11.11. Punkt 2: mit „Dev“
   stand dort „Kaler…“; der Name steht im `aria-label`, der sichtbare Text
   „Dev-Modus an“ erscheint weiter am Desktop).

   Welche Form gilt, entscheidet `App.vue` ueber `istHandyLage` — dieselbe
   Quelle, an der die Gerüst-Klasse `.dk-app--handy` haengt (DEV-B6). Hier
   steht nur die Optik der Kopfzeilen-Form; ein Laptop mit Maus behaelt
   unten rechts. */
.dk-dev-start--kopf {
  position: static;
  flex: none;
  min-width: var(--treffer-handy);
  min-height: var(--treffer-handy);
  width: var(--treffer-handy);
  height: var(--treffer-handy);
  right: auto;
  bottom: auto;
  z-index: auto;
  justify-content: center;
  gap: 0;
  padding: 0;
  background: transparent;
  border-color: transparent;
  box-shadow: none;
}
.dk-dev-start--kopf .dk-dev-start-text { display: none; }
</style>
