<template>
  <!-- ON-3 (W2, Schritt 5 „Mitglieder & Kalender“, Entwurf 08): drei Wahlkarten
       (CSV-Import / von Hand / Später), der Kalender-Vorschlag mit Häkchen und
       die optionale Gruppe. Die Wege selbst sind VORHANDEN — hier wird nur
       dorthin verwiesen und der Vorschlag als Zustand gemerkt. -->
  <section class="schritt">
    <h1 class="schritt-titel">Mitglieder &amp; Kalender</h1>
    <p class="schritt-unterzeile">Wie möchten Sie die ersten Mitglieder anlegen? Später jederzeit möglich.</p>

    <fieldset class="wahl">
      <legend class="wahl-titel">Mitglieder</legend>
      <div class="wahl-karten">
        <label
          v-for="wahl in WAHLEN"
          :key="wahl.wert"
          class="wahl-karte"
          :class="{ 'ist-gewaehlt': mitgliederWahl === wahl.wert }"
        >
          <input
            class="wahl-funk"
            type="radio"
            name="mitglieder-weg"
            :value="wahl.wert"
            :checked="mitgliederWahl === wahl.wert"
            @change="$emit('mitglieder', wahl.wert)"
          />
          <span class="wahl-kopf">
            <span class="wahl-ring" aria-hidden="true"></span>
            <span class="wahl-name">{{ wahl.titel }}</span>
          </span>
          <span class="wahl-satz">{{ wahl.satz }}</span>
        </label>
      </div>
    </fieldset>

    <!-- Die gewählte Route führt in die vorhandene Seite; der Assistent bleibt
         der Ausgangspunkt (Wiedereinstieg über den ersten offenen Schritt).

         ON-3b (N3): Der Hinweis sagte vorher „Der Schritt bleibt offen, bis die
         Mitglieder angelegt sind.“ — das stimmt NICHT: „Weiter“ setzt den
         Schritt `erledigt`, unabhängig davon, ob Mitglieder da sind. Offen
         bleibt der Checklisten-Punkt „Mitglieder“ (er hängt an den echten
         Daten, `einrichtung.status`), und mit ihm die Einrichtungs-Karte. -->
    <div v-if="mitgliederWahl !== 'spaeter'" class="wahl-ziel">
      <DkButton variant="secondary" @click="$emit('weg', mitgliederWahl)">
        {{ mitgliederWahl === 'import' ? 'Zum Import' : 'Zur Mitgliederliste' }}
      </DkButton>
      <span class="wahl-ziel-hinweis">Mit „Weiter“ ist dieser Schritt erledigt. Der Checklisten-Punkt „Mitglieder“ bleibt offen, bis Mitglieder angelegt sind.</span>
    </div>

    <section class="vorschlag">
      <h2 class="vorschlag-titel">Vorschlag: Kalender anlegen</h2>
      <p class="vorschlag-satz">Diakronos legt zwei Kalender an – Sie können das abwählen.</p>
      <div class="vorschlag-feld">
        <div v-for="v in VORSCHLAEGE" :key="v.name">
          <DkCheckbox
            :model-value="kalenderAuswahl[v.name] === true"
            @update:model-value="$emit('kalender', { name: v.name, gewaehlt: $event })"
          >
            <span class="vorschlag-name">{{ v.name }}</span>
            <span class="vorschlag-hinweis">{{ v.hinweis }}</span>
          </DkCheckbox>
        </div>
        <div class="vorschlag-trenner" aria-hidden="true"></div>
        <DkCheckbox
          :model-value="gruppeSpater"
          @update:model-value="$emit('gruppe', $event)"
        >
          <span class="vorschlag-name">Gruppen anlegen (optional)</span>
          <span class="vorschlag-hinweis">z. B. Jugendkreis, Kirchenchor, Besuchsdienst</span>
        </DkCheckbox>
        <p v-if="gruppeSpater" class="vorschlag-verweis">
          <a href="#/gruppen" class="wahl-link">Zur Gruppenseite</a>
          <span class="wahl-ziel-hinweis">Gruppen lassen sich jederzeit anlegen.</span>
        </p>
      </div>
    </section>
  </section>
</template>

<script setup>
/**
 * Schritt „Mitglieder & Kalender“ (ON-3/W2, Entwurf 08).
 *
 * Die Wahl „Mitglieder importieren“ und „Erstes Mitglied von Hand“ führen auf
 * die VORHANDENEN Wege (`#/mitglieder/import`, Dialog auf
 * `#/mitglieder/liste`) — kein zweiter Import und kein zweiter Anlege-Dialog.
 * Angelegt wird nur der KALENDER-Vorschlag, und das erst beim „Weiter“
 * (`einrichtung.kalender_vorschlag_anlegen`).
 */
import DkButton from '../ui/DkButton.vue'
import DkCheckbox from '../ui/DkCheckbox.vue'

const props = defineProps({
  mitgliederWahl: { type: String, default: 'spaeter' },
  kalenderAuswahl: { type: Object, default: () => ({}) },
  gruppeSpater: Boolean,
})
defineEmits(['mitglieder', 'kalender', 'gruppe', 'weg'])

/** Die drei Wahlkarten — Texte wörtlich aus dem Entwurf (Frame 08). */
const WAHLEN = [
  {
    wert: 'import',
    titel: 'Mitglieder importieren (CSV)',
    satz: 'Adressliste aus einer Datei übernehmen.',
  },
  {
    wert: 'hand',
    titel: 'Erstes Mitglied von Hand',
    satz: 'Eine Person direkt im Formular anlegen.',
  },
  {
    wert: 'spaeter',
    titel: 'Später',
    satz: 'Mitglieder nach der Einrichtung anlegen.',
  },
]

/** Die zwei Vorschläge aus dem Entwurf. */
const VORSCHLAEGE = [
  { name: 'Gottesdienste', hinweis: 'Sonntags 10:00, mit Predigt und Liedern' },
  { name: 'Gemeindekalender', hinweis: 'Alle übrigen Termine der Gemeinde' },
]
</script>

<style scoped>
.schritt { display: flex; flex-direction: column; gap: var(--sp-4); }
.schritt-titel { margin: 0; font-size: var(--fs-h1); font-weight: var(--fw-h); color: var(--text); line-height: 1.25; }
.schritt-unterzeile {
  margin: 0;
  font-size: var(--fs-fliess);
  color: var(--muted);
  line-height: 1.5;
  max-width: 640px;
}
.wahl { border: 0; margin: 0; padding: 0; }
.wahl-titel { padding: 0; font-size: var(--fs-feld); font-weight: 600; color: var(--muted); margin-bottom: var(--sp-2); }
.wahl-karten { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: var(--sp-3); }
.wahl-karte {
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
  padding: var(--sp-3) var(--sp-4);
  min-height: 136px;
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
  background: var(--surface);
  cursor: pointer;
  transition: border-color var(--fast);
}
.wahl-karte:hover { border-color: var(--line-strong); }
.wahl-karte.ist-gewaehlt { border-color: var(--primary); }
.wahl-karte:focus-within { outline: 2px solid var(--focus-ring); outline-offset: 1px; }
/* Das Radio bleibt im Baum (Tastatur, Vorlesehilfe) — nur unsichtbar. Der
   sichtbare Ring ist ein eigenes Element, damit er die Farbe aus den Tokens
   bekommt und mittig sitzt (ON-3/W5). */
.wahl-funk {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip-path: inset(50%);
  border: 0;
}
.wahl-kopf { display: flex; align-items: flex-start; gap: var(--sp-2); }
.wahl-ring {
  flex: none;
  width: var(--icon-md);
  height: var(--icon-md);
  margin-top: 2px;
  border-radius: 50%;
  border: 1.5px solid var(--line-strong);
  background: var(--surface);
}
.wahl-karte.ist-gewaehlt .wahl-ring {
  border-color: var(--primary);
  box-shadow: inset 0 0 0 3px var(--surface);
  background: var(--primary);
}
.wahl-name { font-size: var(--fs); font-weight: 700; color: var(--text); line-height: 1.3; }
.wahl-satz { font-size: var(--fs-sm); color: var(--muted); line-height: 1.4; }

.wahl-ziel { display: flex; flex-wrap: wrap; gap: var(--sp-2); align-items: baseline; margin: 0; }
.wahl-link { color: var(--link); font-weight: 600; }
.wahl-link:hover { color: var(--link-hover); }
.wahl-ziel-hinweis { font-size: var(--fs-sm); color: var(--subtle); }

.vorschlag { display: flex; flex-direction: column; gap: var(--sp-1); }
.vorschlag-titel { margin: 0; font-size: var(--fs-h4); font-weight: 700; color: var(--text); }
.vorschlag-satz { margin: 0 0 var(--sp-2); font-size: var(--fs-sm); color: var(--muted); }
.vorschlag-feld {
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
  padding: var(--sp-4);
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
  background: var(--surface-2);
}
.vorschlag-name { display: block; font-size: var(--fs); font-weight: 600; color: var(--text); }
.vorschlag-hinweis { display: block; font-size: var(--fs-sm); color: var(--subtle); }
.vorschlag-trenner { height: 1px; background: var(--line); }
.vorschlag-verweis { display: flex; flex-wrap: wrap; gap: var(--sp-2); align-items: baseline; margin: 0; }

@media (max-width: 700px) {
  .wahl-karten { grid-template-columns: minmax(0, 1fr); }
  .wahl-karte { min-height: 0; }
  .schritt-unterzeile { font-size: var(--fs); }
}
</style>
