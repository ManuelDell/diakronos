<template>
  <!-- ON-3 (W1): Schrittleiste. Auf dem Desktop eine senkrechte Liste links
       (Entwurf 04), am Handy „Schritt n von 6“ + Segmentbalken (Entwurf 14).
       Es ist eine NAVIGATION zwischen Schritten (auf „Fertig“ erst am Ende),
       deshalb <button> in einer Liste mit aria-current — kein tablist-Muster.
       Der Haken im Kreis sitzt mittig (ON-3/W5: Entwurf hatte Versatz). -->
  <div class="assistent-schritte">
    <!-- Desktop -->
    <nav class="assistent-leiste" aria-label="Schritte der Einrichtung">
      <p class="assistent-leiste-titel">Einrichtung</p>
      <p v-if="fortschritt" class="assistent-leiste-fortschritt">{{ fortschritt }}</p>
      <ol class="assistent-liste">
        <li v-for="(eintrag, i) in schritte" :key="eintrag.schluessel" class="assistent-punkt">
          <span class="assistent-linie" :class="linieKlasse(i)" aria-hidden="true"></span>
          <button
            type="button"
            class="assistent-schritt"
            :class="{
              'ist-aktiv': eintrag.schluessel === aktiv,
              'ist-erledigt': eintrag.zustand === 'erledigt',
              'ist-uebersprungen': eintrag.zustand === 'uebersprungen',
            }"
            :aria-current="eintrag.schluessel === aktiv ? 'step' : undefined"
            :disabled="eintrag.schluessel === 'fertig' && !abgeschlossen"
            @click="$emit('gehe', eintrag.schluessel)"
          >
            <span class="assistent-kreis" aria-hidden="true">
              <AssistentSymbol
                v-if="eintrag.zustand === 'erledigt'"
                name="haken"
                :size="haken"
                :strich="2.4"
              />
              <span v-else-if="eintrag.zustand === 'uebersprungen'" class="assistent-punktmarke"></span>
              <span v-else>{{ i + 1 }}</span>
            </span>
            <span class="assistent-beschriftung">
              <span class="assistent-name">{{ eintrag.anzeige }}</span>
              <span v-if="eintrag.zustand === 'uebersprungen'" class="assistent-uebersprungen">
                Übersprungen
              </span>
            </span>
          </button>
        </li>
      </ol>
    </nav>

    <!-- Handy: „Schritt n von 6“ + Segmentbalken -->
    <div class="assistent-mobil">
      <div class="assistent-mobil-kopf">
        <button
          v-if="hatZurueck"
          type="button"
          class="assistent-mobil-zurueck"
          @click="$emit('zurueck')"
        >
          <AssistentSymbol name="zurueck" :size="18" />
          <span class="assistent-sr">{{ schrittText }}</span>
        </button>
        <p class="assistent-mobil-text" aria-hidden="true">{{ schrittText }}</p>
        <p class="assistent-mobil-name" aria-hidden="true">{{ aktivName }}</p>
      </div>
      <div
        class="assistent-segment"
        role="progressbar"
        :aria-valuenow="nummer"
        aria-valuemin="1"
        :aria-valuemax="anzahl"
        :aria-label="schrittText"
      >
        <span class="assistent-segment-fuell" :style="{ width: anteilProzent }"></span>
      </div>
    </div>
  </div>
</template>

<script setup>
/**
 * AssistentSchritte — Schrittleiste des Einrichtungs-Assistenten (ON-3/W1).
 *
 * Rein darstellend: `schritte` kommt aus `einrichtungAssistent.schrittListe`,
 * der aktive Schritt aus dem Modulzustand. Gewechselt wird per Ereignis
 * (`gehe`), damit die Seite die EINE Stelle bleibt, die den Schritt setzt.
 *
 * Nur Tokens (`var(--…)`) — keine Farb-, Schrift- oder Radius-Zahlen.
 */
import { computed } from 'vue'
import AssistentSymbol from './AssistentSymbol.vue'
import { SCHRITT_ANZAHL, segmentAnteil, schrittIndex, schrittText as schrittTextFuer } from '../../composables/einrichtungAssistent.mjs'

const props = defineProps({
  schritte: { type: Array, required: true },
  aktiv: { type: String, required: true },
  abgeschlossen: Boolean,
  fortschritt: { type: String, default: '' },
})
defineEmits(['gehe', 'zurueck'])

const haken = 'var(--assistent-schritt-haken)'
const hatZurueck = computed(() => schrittIndex(props.aktiv) > 0)
const nummer = computed(() => Math.max(1, schrittIndex(props.aktiv) + 1))
const anzahl = SCHRITT_ANZAHL
const schrittText = computed(() => schrittTextFuer(props.aktiv))
const anteilProzent = computed(() => `${Math.round(segmentAnteil(props.aktiv) * 100)}%`)
const aktivName = computed(() => props.schritte.find((s) => s.schluessel === props.aktiv)?.anzeige || '')

/**
 * Die Verbindungslinie unter einem Schritt: grün, wenn der Schritt DAHINTER
 * erledigt ist (Entwurf 05: „Gemeinde“ erledigt → Linie grün), sonst neutral.
 * Auf dem letzten Schritt gibt es keine Linie.
 */
function linieKlasse(index) {
  if (index >= props.schritte.length - 1) return 'ist-letzte'
  const naechster = props.schritte[index + 1]
  return naechster?.zustand === 'erledigt' ? 'ist-fertig' : ''
}
</script>

<style scoped>
.assistent-schritte { display: contents; }

/* Am Handy ist die Desktop-Leiste `display: none` — ABER `display: contents`
   am Wrapper hebt die Kindregel nicht auf: das <nav> blieb als Flex-Kind im
   `.assistent-koerper` und nahm mit `--assistent-leiste` (300 px) Breite weg
   (gemessen: Inhalt 390 → 201 px, Karte 390 → 161 px). Deshalb hier `none`
   für den Wrapper selbst; sichtbar bleibt die Mobilform darunter. */
@media (max-width: 900px) {
  .assistent-schritte { display: block; }
}

.assistent-sr {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip-path: inset(50%);
  white-space: nowrap;
  border: 0;
}

/* ── Desktop: senkrechte Leiste ───────────────────────────────────────── */
.assistent-leiste {
  width: var(--assistent-leiste);
  flex: none;
  border-right: 1px solid var(--line);
  background: var(--surface);
  padding: var(--sp-6) var(--sp-4) var(--sp-5) var(--sp-6);
  overflow-y: auto;
}
.assistent-leiste-titel {
  margin: 0 0 var(--sp-1);
  font-size: var(--fs-sm);
  font-weight: 700;
  color: var(--subtle);
  text-transform: none;
}
.assistent-leiste-fortschritt {
  margin: 0 0 var(--sp-6);
  font-size: var(--fs-sm);
  color: var(--muted);
}
.assistent-liste { list-style: none; margin: 0; padding: 0; }
.assistent-punkt { position: relative; padding-bottom: var(--sp-5); }
.assistent-punkt:last-child { padding-bottom: 0; }
.assistent-linie {
  position: absolute;
  left: calc(var(--assistent-schritt) / 2 - 1px);
  top: var(--assistent-schritt);
  bottom: var(--sp-5);
  width: 2px;
  background: var(--line-strong);
}
.assistent-linie.ist-fertig { background: var(--ok); }
.assistent-linie.ist-letzte { display: none; }

.assistent-schritt {
  display: flex;
  align-items: flex-start;
  gap: var(--sp-4);
  width: 100%;
  padding: 0;
  border: 0;
  background: none;
  text-align: left;
  font: inherit;
  font-size: var(--fs-schritt);
  color: var(--subtle);
  cursor: pointer;
  border-radius: var(--radius-sm);
}
.assistent-schritt:disabled { cursor: default; }
.assistent-schritt:focus-visible {
  outline: 2px solid var(--focus-ring);
  outline-offset: 2px;
}
.assistent-kreis {
  flex: none;
  width: var(--assistent-schritt);
  height: var(--assistent-schritt);
  border-radius: 50%;
  display: grid;
  place-items: center;
  font-size: var(--fs-sm);
  font-weight: 700;
  line-height: 1;
  background: var(--surface);
  border: 1.4px solid var(--line-strong);
  color: var(--subtle);
}
/* ON-3/W5: Der Haken wird von `place-items: center` mittig gesetzt — der
   Entwurf hatte ihn um gut 1 px nach unten versetzt gezeichnet. */
.assistent-kreis :deep(svg) { display: block; }
.assistent-punktmarke {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--warn);
}
.assistent-name { display: block; }
.assistent-uebersprungen {
  display: block;
  font-size: var(--fs-sm);
  color: var(--warn);
}

.assistent-schritt.ist-erledigt { color: var(--muted); }
.assistent-schritt.ist-erledigt .assistent-kreis {
  background: var(--ok-soft);
  border-color: transparent;
  color: var(--ok);
}
.assistent-schritt.ist-uebersprungen { color: var(--warn); }
.assistent-schritt.ist-uebersprungen .assistent-kreis {
  background: var(--warn-soft);
  border-color: transparent;
}
.assistent-schritt.ist-aktiv {
  color: var(--primary);
  font-weight: 700;
}
.assistent-schritt.ist-aktiv .assistent-kreis {
  background: var(--primary);
  border-color: var(--primary);
  color: var(--primary-ink);
}

/* ── Handy: Kopf + Segmentbalken ──────────────────────────────────────── */
.assistent-mobil { display: none; }
.assistent-mobil-kopf {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  padding: var(--sp-3) var(--sp-alt-20);
  background: var(--surface);
}
.assistent-mobil-zurueck {
  display: inline-flex;
  align-items: center;
  border: 0;
  background: none;
  padding: 0;
  color: var(--link);
  cursor: pointer;
  border-radius: var(--radius-sm);
}
.assistent-mobil-zurueck:focus-visible { outline: 2px solid var(--focus-ring); outline-offset: 2px; }
.assistent-mobil-text { margin: 0; font-size: var(--fs-sm); color: var(--muted); }
.assistent-mobil-name { margin: 0 0 0 auto; font-size: var(--fs-sm); color: var(--muted); }
.assistent-segment {
  height: var(--assistent-balken);
  margin: 0 var(--sp-alt-20);
  background: var(--divider);
  border-radius: var(--badge-r);
  overflow: hidden;
}
.assistent-segment-fuell {
  display: block;
  height: 100%;
  background: var(--primary);
  border-radius: var(--badge-r);
  transition: width var(--med) var(--ease);
}

@media (max-width: 900px) {
  .assistent-leiste { display: none; }
  .assistent-mobil { display: block; }
}
</style>
