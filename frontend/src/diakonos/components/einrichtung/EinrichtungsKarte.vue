<template>
  <!-- ON-4 (H1, Entwurf 10): „Einrichtung abschließen — n von 7 offen“ über den
       Widgets der Übersicht. Erscheint nur, wenn `karteZeigen` sie zulässt
       (Admin, Assistent abgeschlossen, offene Punkte, keine Erinnerungspause).
       Schließen-Kreuz = „Später erinnern“ (dieselbe Handlung wie der Link).
       Jede Zeile führt auf ihr Ziel aus `einrichtung.status` — also in die
       EINSTELLUNGEN (bzw. Mitglieder/Kalenderverwaltung), wo die Angaben
       gepflegt werden (Nachtrag Orchestrator 2026-11-03). -->
  <section v-if="sichtbar" class="dk-einrichtungs-karte" aria-labelledby="dk-einrichtung-titel">
    <header class="dk-einrichtungs-kopf">
      <div class="dk-einrichtungs-titelblock">
        <h2 id="dk-einrichtung-titel" class="dk-einrichtungs-titel">{{ titel }}</h2>
        <p class="dk-einrichtungs-unterzeile">{{ unterzeile }}</p>
      </div>
      <button
        type="button"
        class="dk-einrichtungs-schliessen"
        :title="texte.karteSchliessen"
        :aria-label="texte.karteSchliessen"
        @click="spaeter"
      >✕</button>
    </header>

    <div
      class="dk-einrichtungs-balken"
      role="progressbar"
      :aria-valuenow="prozent"
      aria-valuemin="0"
      aria-valuemax="100"
      :aria-label="fortschritt"
    >
      <span class="dk-einrichtungs-balken-fuell" :style="{ width: prozent + '%' }"></span>
    </div>
    <p class="dk-einrichtungs-fortschritt">{{ fortschritt }}</p>

    <ul class="dk-einrichtungs-liste">
      <li v-for="zeile in zeilen" :key="zeile.schluessel" class="dk-einrichtungs-zeile">
        <span class="dk-einrichtungs-punkt" aria-hidden="true"></span>
        <span class="dk-einrichtungs-text">{{ zeile.text }}</span>
        <a :href="zeile.ziel" class="dk-einrichtungs-link">{{ zeile.zielText }}</a>
      </li>
    </ul>

    <p class="dk-einrichtungs-fuss">
      <button type="button" class="dk-einrichtungs-spaeter" @click="spaeter">
        {{ texte.spaeterErinnern }}
      </button>
      <a :href="EINSTELLUNGEN" class="dk-einrichtungs-link">{{ texte.einstellungenOeffnen }}</a>
    </p>
  </section>
</template>

<script setup>
/**
 * EinrichtungsKarte — Karte „Einrichtung abschließen“ auf der Übersicht
 * (ON-4/H1, Entwurf Frame 10).
 *
 * WOher die Angaben kommen
 * `einrichtung.status` (Server) liefert Punkte, Zähler und `ziel`; die Sätze
 * stehen wörtlich im Entwurf (`composables/einrichtungsHinweise.mjs`). Diese
 * Komponente rechnet NICHTS selbst nach — sie zeigt, was das Modul liefert.
 *
 * WANN sie verschwindet
 * Nach „Später erinnern“ (Server: `erinnern_spaeter`, Antwort bestimmt das
 * Datum) und sobald nichts mehr offen ist. Bei Nicht-Admins und während des
 * Assistenten erscheint sie gar nicht (`karteZeigen`).
 *
 * Nur Tokens (`var(--…)`) — keine Farb-, Schrift- oder Radius-Zahlen.
 */
import { computed, onMounted } from 'vue'

import { karteZeigen, fortschrittAnteil, fortschrittText } from '../../composables/einrichtung.mjs'
import {
  EINSTELLUNGEN_ROUTE,
  TEXTE,
  erinnerungBis,
  kartenZeilen,
  karteTitelMitZahl,
  spaeterErinnern,
  statusAuffrischen,
  statusLaden,
  statusStand,
} from '../../composables/einrichtungsHinweise.mjs'

const props = defineProps({
  /** Admin? (`window.__DIakonosBOOT.is_admin`) — die Leisten sind Verwaltung. */
  admin: { type: Boolean, default: false },
  /** Heute (tests) — sonst jetzt. */
  heute: { type: Date, default: () => new Date() },
})

/**
 * Sammel-Ziel der Einstellungen (Nachtrag Orchestrator 2026-11-03: alle
 * Angaben werden NACH der Ersteinrichtung ausschließlich in den Einstellungen
 * geändert — es gibt keinen eigenen Abschnitt „Einrichtung“ mehr). Die
 * einzelnen Zeilen führen auf ihr Ziel aus `einrichtung.status`.
 */
const EINSTELLUNGEN = EINSTELLUNGEN_ROUTE
const texte = TEXTE

const sichtbar = computed(
  () => props.admin && karteZeigen(statusStand.value, props.heute),
)
const titel = computed(() => karteTitelMitZahl(statusStand.value))
const unterzeile = computed(() => TEXTE.karteUnterzeile)
const fortschritt = computed(() => fortschrittText(statusStand.value))
const prozent = computed(() => Math.round(fortschrittAnteil(statusStand.value) * 100))
const zeilen = computed(() => kartenZeilen(statusStand.value))

/**
 * „Später erinnern“: Datum einmal rechnen und ans Modul geben. Der Server
 * entscheidet (er antwortet mit `erinnerung_ab`); scheitert der Aufruf, bleibt
 * die Karte stehen — der Hinweis ist wichtiger als die Erinnerung.
 */
async function spaeter() {
  const bis = await spaeterErinnern(7, new Date())
  if (!bis && statusStand.value) {
    // Kein Serverdatum: trotzdem ausblenden, damit der Klick nicht ins Leere
    // läuft — beim nächsten Laden gilt wieder der Serverstand.
    statusStand.value = { ...statusStand.value, erinnerung_ab: erinnerungBis(new Date(), 7) }
  }
}

onMounted(() => {
  if (!props.admin) return
  // EINEN Stand für alle Stellen (Karte, Leisten): erst laden, dann neu lesen.
  statusLaden().then(() => statusAuffrischen())
})
</script>

<style scoped>
.dk-einrichtungs-karte {
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
  margin-bottom: var(--gap);
  padding: var(--pad) calc(var(--pad) * 1.2);
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow);
}
.dk-einrichtungs-kopf {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--sp-3);
}
.dk-einrichtungs-titelblock { display: flex; flex-direction: column; gap: var(--sp-1); min-width: 0; }
.dk-einrichtungs-titel {
  margin: 0;
  font-size: var(--fs-h3);
  font-weight: var(--fw-h);
  color: var(--text);
}
.dk-einrichtungs-unterzeile { margin: 0; font-size: var(--fs-sm); color: var(--muted); }
.dk-einrichtungs-schliessen {
  flex: none;
  border: 0;
  background: none;
  padding: var(--sp-1);
  font: inherit;
  font-size: var(--fs);
  line-height: 1;
  color: var(--muted);
  cursor: pointer;
  border-radius: var(--radius-sm);
}
.dk-einrichtungs-schliessen:hover { color: var(--text); background: var(--surface-2); }
.dk-einrichtungs-schliessen:focus-visible { outline: 2px solid var(--focus-ring); outline-offset: 2px; }

.dk-einrichtungs-balken {
  position: relative;
  height: var(--sp-1);
  border-radius: var(--badge-r);
  background: var(--surface-2);
  overflow: hidden;
}
.dk-einrichtungs-balken-fuell {
  display: block;
  height: 100%;
  background: var(--ok);
  border-radius: var(--badge-r);
}
.dk-einrichtungs-fortschritt { margin: 0; font-size: var(--fs-sm); color: var(--muted); }

.dk-einrichtungs-liste {
  list-style: none;
  margin: var(--sp-2) 0 0;
  padding: 0;
  display: flex;
  flex-direction: column;
}
.dk-einrichtungs-zeile {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  padding: var(--sp-2) 0;
  border-top: 1px solid var(--line);
}
.dk-einrichtungs-punkt {
  flex: none;
  width: var(--sp-1);
  height: var(--sp-1);
  border-radius: 50%;
  background: var(--warn);
}
.dk-einrichtungs-text { flex: 1 1 auto; min-width: 0; font-size: var(--fs); color: var(--text); }
.dk-einrichtungs-link {
  flex: none;
  font-size: var(--fs-sm);
  font-weight: 600;
  color: var(--link);
  text-decoration: none;
  border: 1px solid var(--line-strong);
  border-radius: var(--radius);
  padding: var(--sp-1) var(--sp-3);
}
.dk-einrichtungs-link:hover { color: var(--link-hover); background: var(--surface-2); }
.dk-einrichtungs-link:focus-visible { outline: 2px solid var(--focus-ring); outline-offset: 2px; }

.dk-einrichtungs-fuss {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--sp-3);
  margin: var(--sp-2) 0 0;
  flex-wrap: wrap;
}
.dk-einrichtungs-spaeter {
  border: 0;
  background: none;
  padding: 0;
  font: inherit;
  font-size: var(--fs-sm);
  color: var(--link);
  cursor: pointer;
}
.dk-einrichtungs-spaeter:hover { color: var(--link-hover); text-decoration: underline; }
.dk-einrichtungs-spaeter:focus-visible { outline: 2px solid var(--focus-ring); outline-offset: 2px; }
</style>
