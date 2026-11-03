<template>
  <!-- ON-3 (W2, Schritt 4 „Module“, Entwurf 07): eine Kachel je Modul mit
       Schalter und dem Satz aus dem Entwurf. GEZEIGT WIRD NUR, WAS ES GIBT —
       die Liste kommt aus `gemeinde_get_einstellungen` (Serverquelle
       `MODULE` in api/gemeinde.py), nicht aus einer zweiten Aufzählung im
       Browser. Eine feste Liste hätte hier Schalter für Module gezeichnet,
       die die Anlage gar nicht kennt. -->
  <section class="schritt">
    <h1 class="schritt-titel">Module</h1>
    <p class="schritt-unterzeile">Wählen Sie die Bereiche, die Sie nutzen – änderbar in den Einstellungen.</p>

    <p v-if="!module.length && !laedt" class="schritt-hinweis" role="status">
      Es sind keine Module hinterlegt.
    </p>

    <ul class="modul-raster">
      <li v-for="modul in module" :key="modul.schluessel">
        <div class="modul-kachel" :class="{ 'ist-an': wert(modul.schluessel) }">
          <div class="modul-text">
            <p class="modul-name">{{ modul.anzeige }}</p>
            <p v-if="satz(modul.schluessel)" class="modul-satz">{{ satz(modul.schluessel) }}</p>
          </div>
          <!-- Eigener Schiebeschalter statt nativem Kästchen: er zeigt den
               Stand OHNE zusätzliches Wort (Entwurf 07) und bleibt über
               role="switch" + aria-checked für Vorlesehilfen eindeutig. -->
          <button
            type="button"
            class="modul-schalter"
            role="switch"
            :aria-checked="wert(modul.schluessel)"
            :aria-label="modul.anzeige"
            @click="$emit('schalten', { schluessel: modul.schluessel, sichtbar: !wert(modul.schluessel) })"
          >
            <span class="modul-knopf" aria-hidden="true"></span>
          </button>
        </div>
      </li>
      <li>
        <div class="modul-kachel ist-platzhalter">
          <div class="modul-text">
            <p class="modul-name">Weitere Module folgen</p>
            <p class="modul-satz">Wünsche nehmen wir gerne auf.</p>
          </div>
        </div>
      </li>
    </ul>
  </section>
</template>

<script setup>
/**
 * Schritt „Module“ (ON-3/W2, Entwurf 07).
 *
 * Der Schalter setzt nur den lokalen Entwurf; geschrieben wird beim „Weiter“
 * (ein Aufruf je geändertem Modul, `gemeinde_setze_modul`). So bleibt „Zurück“
 * ohne Nebenwirkung — ein sofortiges Schreiben würde jede Schalterbewegung zu
 * einem eigenen Schreibvorgang machen.
 *
 * Die Sätze sind wörtlich aus dem Entwurf; Module ohne Satz dort bekommen
 * keinen erfundenen, sondern gar keinen.
 */
const props = defineProps({
  module: { type: Array, default: () => [] },
  auswahl: { type: Object, default: () => ({}) },
  laedt: Boolean,
})
defineEmits(['schalten'])

/** Die Sätze aus dem Entwurf (Frame 07) — Zuordnung über den Server-Schlüssel. */
const SAETZE = Object.freeze({
  diakronos: 'Mitglieder, Gruppen und Kalender',
  kronos: 'Gottesdienste, Termine und Räume',
  diakonos: 'Kreise, Teams und Rollen',
  psalmos: 'Lieddatenbank und Vorschläge',
  seelsorge: 'Gespräche und Vertrauliches',
})

function satz(schluessel) {
  return SAETZE[schluessel] || ''
}

function wert(schluessel) {
  return props.auswahl[schluessel] === true
}
</script>

<style scoped>
.schritt { display: flex; flex-direction: column; gap: var(--sp-4); }
.schritt-titel { margin: 0; font-size: var(--fs-h1); font-weight: var(--fw-h); color: var(--text); line-height: 1.25; }
.schritt-unterzeile {
  margin: 0 0 var(--sp-2);
  font-size: var(--fs-fliess);
  color: var(--muted);
  line-height: 1.5;
  max-width: 640px;
}
.schritt-hinweis { margin: 0; font-size: var(--fs-sm); color: var(--muted); }
.modul-raster {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--sp-3);
}
.modul-kachel {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--sp-3);
  min-height: 84px;
  padding: var(--sp-3) var(--sp-4);
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
  background: var(--surface-2);
  transition: border-color var(--fast), background var(--fast);
}
.modul-kachel.ist-an { border-color: var(--primary); background: var(--surface); }
.modul-kachel.ist-platzhalter {
  border-style: dashed;
  background: none;
  align-items: center;
  justify-content: center;
  text-align: center;
}
.modul-text { min-width: 0; }
.modul-name { margin: 0; font-size: var(--fs); font-weight: 700; color: var(--text); }
.modul-satz { margin: var(--sp-1) 0 0; font-size: var(--fs-sm); color: var(--muted); }
.modul-kachel.ist-platzhalter .modul-name { font-size: var(--fs); color: var(--subtle); }
.modul-kachel.ist-platzhalter .modul-satz { color: var(--subtle); }

/* Schiebeschalter: Maße aus tokens.css (--segment-*), Farben aus den
   semantischen Tokens. Der Knopf sitzt in BEIDEN Ständen mittig in der Höhe
   und hat denselben Rand — kein Versatz (ON-3/W5). */
.modul-schalter {
  flex: none;
  position: relative;
  width: calc(var(--segment-knopf) * 2 + var(--segment-weg));
  height: var(--segment-h);
  padding: 0;
  border: 0;
  border-radius: var(--badge-r);
  background: var(--line-strong);
  cursor: pointer;
  transition: background var(--fast);
}
.modul-schalter[aria-checked='true'] { background: var(--primary); }
.modul-schalter:focus-visible { outline: 2px solid var(--focus-ring); outline-offset: 2px; }
.modul-knopf {
  position: absolute;
  top: var(--segment-rand);
  left: var(--segment-rand);
  width: var(--segment-knopf);
  height: var(--segment-knopf);
  border-radius: 50%;
  background: var(--surface);
  transition: transform var(--fast) var(--ease);
}
.modul-schalter[aria-checked='true'] .modul-knopf { transform: translateX(var(--segment-weg)); }

@media (max-width: 700px) {
  .modul-raster { grid-template-columns: minmax(0, 1fr); }
  .schritt-unterzeile { font-size: var(--fs); }
}
</style>
