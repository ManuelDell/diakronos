<template>
  <!-- CHAT-3a — die Liste „meine Gespräche“ (Chat-Konzept 6.2 Variante B).
       Sie steht am Desktop links neben dem Verlauf und am Handy allein; die
       Seite entscheidet, welche der beiden gilt. Reine Darstellung: was in
       welchem Abschnitt steht, hat `gruppierteListe()` schon entschieden. -->
  <div class="dk-chat-liste">
    <div class="dk-chat-liste-kopf">
      <h2 class="dk-chat-liste-titel">Alle Gespräche</h2>
      <span v-if="ungelesen > 0" class="dk-chat-liste-neu">{{ ungelesen }} neu</span>
    </div>

    <!-- Laden: ruhiger Platzhalter statt „nichts da“ (Prinzip I5, UX2d3a:
         Form statt Prosa). -->
    <DkSkelett v-if="laedt" form="zeilen" :anzahl="5" />

    <template v-else>
      <section v-for="abschnitt in gruppen" :key="abschnitt.id" class="dk-chat-abschnitt">
        <h3 class="dk-chat-abschnitt-titel">{{ abschnitt.label }}</h3>
        <ul class="dk-chat-zeilen">
          <li v-for="zeile in abschnitt.eintraege" :key="zeilenSchluessel(zeile)">
            <a
              class="dk-chat-zeile"
              :class="{ 'is-aktiv': istAktiv(zeile) }"
              :href="hrefFuer(zeile)"
              :aria-current="istAktiv(zeile) ? 'page' : undefined"
            >
              <span class="dk-chat-av" aria-hidden="true">{{ initialenFuer(zeile) }}</span>
              <span class="dk-chat-zeile-text">
                <span class="dk-chat-zeile-name">
                  {{ zeile.titel }}
                  <!-- Stumm-Symbol (F3: jede Person für sich) -->
                  <span v-if="zeile.stumm" class="dk-chat-stumm" title="stumm geschaltet">
                    <span aria-hidden="true">🔇</span>
                    <span class="dk-chat-nur-vorlesen">stumm geschaltet</span>
                  </span>
                </span>
                <span class="dk-chat-zeile-vorschau">{{ vorschau(zeile) }}</span>
              </span>
              <span class="dk-chat-zeile-rechts">
                <span class="dk-chat-zeile-zeit">{{ zeile.zeit }}</span>
                <span v-if="zeile.ungelesen > 0" class="dk-chat-zeile-zahl">
                  <span class="dk-chat-nur-vorlesen">{{ zeile.ungelesen }} ungelesen</span>
                  <span aria-hidden="true">{{ zeile.ungelesen > 99 ? '99+' : zeile.ungelesen }}</span>
                </span>
              </span>
            </a>
          </li>
        </ul>
      </section>
    </template>
  </div>
</template>

<script setup>
/**
 * ChatListe — die Gesprächsliste (CHAT-3a).
 *
 * Sortierung und Gruppierung sind NICHT hier: `gruppierteListe` in
 * `composables/nachrichtenLogik.mjs` liefert die Abschnitte fertig. Der
 * Baustein zeichnet, was er bekommt (Titel, Vorschau, Zeit, Zähler, Stumm).
 *
 * Ein Gespräch, das noch NIE geöffnet wurde, hat serverseitig keine Kennung
 * (`name: null`). Der Link führt dann auf den Bereich selbst — die Seite legt
 * das Gespräch beim Tippen an (`gespraech_anlegen`) und öffnet es. So bleibt
 * die Zeile ein echter Link (Mittelklick, Tastatur, Zurück-Taste).
 */
import { initialen as initialenAus } from '../../composables/anzeigename.mjs'
import { gespraechHash, zeilenAdresse, zeilenSchluessel } from '../../composables/nachrichtenLogik.mjs'
import DkSkelett from '../ui/DkSkelett.vue'

const props = defineProps({
  gruppen: { type: Array, default: () => [] },
  /** Kennung des offenen Gesprächs (leer = keins). */
  aktiv: { type: String, default: '' },
  /** Summe aller ungelesenen Nachrichten. */
  ungelesen: { type: Number, default: 0 },
  laedt: { type: Boolean, default: false },
})

const initialenFuer = (zeile) => initialenAus(null, zeile?.titel || '')
/**
 * Das Ziel einer Zeile: das geöffnete Gespräch hat seine Kennung, ein noch nie
 * geöffnetes hat keine (`name: null`). Es führt dann über seinen TITEL in den
 * Bereich — dort legt `sicherstellen()` das Gespräch an (`gespraech_anlegen`)
 * und stellt die Adresse auf die neue Kennung. So bleibt jede Zeile ein echter
 * Link (Mittelklick, Tastatur, Zurück-Taste) und es gibt keinen zweiten Weg.
 */
/**
 * Das Ziel einer Zeile: die Kennung, wenn es eine gibt — sonst der
 * ORTESSCHLÜSSEL (Gruppe bzw. `gruppe/untergruppe`, `zeilenAdresse`). Ein nie
 * geöffnetes Gespräch hat keine Kennung; über den Ort findet die Seite es
 * eindeutig (und legt es mit `gespraech_anlegen` an). Der TITEL ist keine
 * Adresse: zwei Untergruppen können denselben Anzeigenamen tragen.
 */
const hrefFuer = (zeile) => gespraechHash(zeilenAdresse(zeile))
/**
 * Ist das die offene Zeile? Verglichen wird der Schlüssel, nicht der Titel.
 *
 * CHAT-3a-3/C2 (Review Runde 2): `props.aktiv` kommt von der Seite als BLANKE
 * Kennung (`Nachrichten.vue`: `:aktiv="kennung"`, also `CHAT-…`), hier steht
 * der Schlüssel der Zeile aber als `n:CHAT-…`. Der direkte Vergleich traf
 * deshalb NIE: das offene Gespräch war nicht hervorgehoben und `aria-current`
 * fehlte. Beide Formen werden jetzt auf DENSELBEN Schlüssel gebracht
 * (`zeilenSchluessel` der Zeile gegen den Schlüssel, den die Kennung ergibt).
 */
const istAktiv = (zeile) => {
  const aktiv = String(props.aktiv || '').trim()
  if (!aktiv) return false
  const schluessel = zeilenSchluessel(zeile)
  return Boolean(schluessel) && schluessel === schluesselFuer(aktiv)
}

/** Der Schlüssel einer blanken Kennung bzw. eines Ortesschlüssels (`o:…`). */
function schluesselFuer(wert) {
  const text = String(wert || '').trim()
  if (!text) return ''
  if (text.startsWith('n:') || text.startsWith('o:')) return text
  return `n:${text}`
}
/**
 * Vorschau: die letzte Nachricht (eine Zeile). Ein Gespräch, das noch nie
 * geöffnet wurde, hat keine (`geoeffnet: false`, `letzte_nachricht: null`) —
 * dort steht der ruhige Hinweis. Der Server liefert schon EINE Zeile
 * (`_zitat`), hier wird nur noch einmal auf eine Zeile gekürzt.
 */
function vorschau(zeile) {
  const letzte = String(zeile?.letzte || '').replace(/\s+/g, ' ').trim()
  return letzte || 'Noch keine Nachrichten'
}
</script>

<style scoped>
.dk-chat-liste {
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow-y: auto;
  background: var(--surface);
}
.dk-chat-liste-kopf {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  padding: var(--sp-3) var(--sp-4) var(--sp-2);
  position: sticky;
  top: 0;
  background: var(--surface);
  z-index: 1;
}
.dk-chat-liste-titel {
  margin: 0;
  font-size: var(--fs-16);
  font-weight: var(--fw-fett);
  color: var(--text);
}
.dk-chat-liste-neu {
  margin-left: auto;
  padding: 0 var(--sp-2);
  border-radius: var(--badge-r);
  background: var(--marke-flaeche);
  color: var(--marke-ink);
  font-size: var(--fs-12);
  font-weight: var(--fw-fett);
  white-space: nowrap;
}
.dk-chat-abschnitt-titel {
  margin: 0;
  padding: var(--sp-3) var(--sp-4) var(--sp-1);
  font-size: var(--fs-12);
  font-weight: var(--fw-fett);
  letter-spacing: 0.07em;
  text-transform: uppercase;
  color: var(--subtle);
}
.dk-chat-zeilen {
  list-style: none;
  margin: 0;
  padding: 0 0 var(--sp-2);
}
.dk-chat-zeile {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  padding: var(--sp-2) var(--sp-3);
  border-left: var(--rahmen-breite) solid transparent;
  text-decoration: none;
  color: var(--text);
  /* K4: eine Zeile ist eine Trefferfläche — mindestens 44 px am Finger. */
  min-height: var(--control-h);
}
.dk-chat-zeile:hover { background: var(--surface-hover); }
.dk-chat-zeile.is-aktiv {
  background: var(--surface-2);
  border-left-color: var(--accent);
}
.dk-chat-zeile:focus-visible { outline: var(--rahmen-breite) solid var(--focus-ring); outline-offset: calc(var(--rahmen-breite) * -2); }
.dk-chat-av {
  width: var(--sp-6);
  height: var(--sp-6);
  border-radius: 50%;
  display: grid;
  place-items: center;
  flex: none;
  background: var(--surface-2);
  color: var(--muted);
  font-size: var(--fs-12);
  font-weight: var(--fw-fett);
}
.dk-chat-zeile-text {
  display: flex;
  flex-direction: column;
  min-width: 0;
  flex: 1;
}
.dk-chat-zeile-name {
  display: flex;
  align-items: center;
  gap: var(--sp-1);
  font-size: var(--fs-14);
  font-weight: var(--fw-mittel);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.dk-chat-stumm { color: var(--subtle); font-size: var(--fs-12); }
.dk-chat-zeile-vorschau {
  font-size: var(--fs-12);
  color: var(--muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.dk-chat-zeile-rechts {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: var(--sp-1);
  flex: none;
}
.dk-chat-zeile-zeit {
  font-size: var(--fs-12);
  color: var(--subtle);
  font-variant-numeric: var(--fs-tabular);
}
.dk-chat-zeile-zahl {
  min-width: var(--sp-4);
  height: var(--sp-4);
  padding: 0 var(--sp-1);
  border-radius: var(--badge-r);
  background: var(--marke-flaeche);
  color: var(--marke-ink);
  font-size: var(--fs-12);
  font-weight: var(--fw-fett);
  display: inline-grid;
  place-items: center;
  line-height: 1;
}
/* Text, der nur die Vorlesehilfe angeht (Zähler und Stumm-Symbol sind ohne
   ihn nackte Zahlen bzw. ein Emoji). */
.dk-chat-nur-vorlesen {
  position: absolute;
  width: var(--rahmen-breite);
  height: var(--rahmen-breite);
  margin: calc(var(--rahmen-breite) * -1);
  padding: 0;
  overflow: hidden;
  clip-path: inset(50%);
  white-space: nowrap;
  border: 0;
}
</style>
