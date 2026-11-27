<template>
  <!-- CHAT-3a — die Liste „meine Gespräche“ (Chat-Konzept 6.2 Variante B).
       Sie steht am Desktop links neben dem Verlauf und am Handy allein; die
       Seite entscheidet, welche der beiden gilt. Reine Darstellung: was in
       welchem Abschnitt steht, hat `gruppierteListe()` schon entschieden.
       CHAT-7a: Direktgespräche (1:1) stehen in DERSELBEN Liste — mit dem
       Namen des Gegenübers, „gelesen“ statt Teilnehmerzahl und dem Einstieg
       „Neue Nachricht“ in die Personensuche (Karte Punkt 3 und 4). -->
  <div class="dk-chat-liste">
    <!-- LEISTE-1: Auf der Vollbild-Seite steht hier KEINE Überschrift mehr —
         nur der Ungelesen-Zähler, wenn es einen gibt (er braucht die Zeile,
         sonst stünde die Zahl ohne Bezug). Wo der Kopf aus ist und nichts
         ungelesen ist, entsteht auch keine leere Zeile. -->
    <div v-if="kopfSichtbar" class="dk-chat-liste-kopf">
      <h2 v-if="kopf" class="dk-chat-liste-titel">Alle Gespräche</h2>
      <span v-if="ungelesen > 0" class="dk-chat-liste-neu">{{ ungelesen }} neu</span>
    </div>

    <!-- Karte Punkt 4: der klare Einstieg — steht IMMER oben, auch bei leerer
         Liste (dann ist er der einzige Weg). Eine Trefferfläche ≥ 44 px.
         CHAT-7b-UI: daneben „Neue Runde“ (Karte Punkt 1) — der zweite Einstieg
         im SELBEN Muster (dieselbe Zeile, dasselbe Zeichen, nur ein anderer
         Anfang), er öffnet den Dialog der Seite (`neueRunde`). -->
    <!-- HAUPTKNOPF (Manuel 27.11.): „Neue Nachricht“ ist die EINE Hauptaktion
         der Nachrichten-Seite — gefüllt (primary), weiter ein Link in die
         Personensuche. -->
    <DkButton
      v-if="neueRunde"
      as="a"
      variant="primary"
      class="dk-chat-neu dk-chat-neu--haupt"
      :href="SUCHE"
      :aria-label="`${NEUE_NACHRICHT} — Personen suchen`"
    >
      <span class="dk-chat-neu-zeichen" aria-hidden="true">+</span>
      <span>{{ NEUE_NACHRICHT }}</span>
    </DkButton>
    <!-- CHAT-7b-UI: der zweite Einstieg im SELBEN Muster — ein DkButton
         (Knopf-System, UX1g2), der den Dialog der Seite öffnet.
         LEISTE-1: Am Handy stehen beide Einstiege hinter dem Plus im Kopf
         (Entwurf „02“) — dort ist der zweite Link ausgeblendet; einen Weg
         gibt es trotzdem, nur an einer Stelle. -->
    <DkButton
      v-if="neueRunde"
      variant="ghost"
      class="dk-chat-neu dk-chat-neu--knopf"
      :aria-label="`${NEUE_RUNDE} — mehrere Personen auswählen`"
      @click="$emit('neueRunde')"
    >
      <template #icon><DkSymbol name="runde" /></template>
      {{ NEUE_RUNDE }}
    </DkButton>

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
              <!-- Karte UI-2 Punkt 4: das Bild des Gegenübers wie in der
                   3c-Suche (`dk-chat-av--bild`), sonst die Initialen. -->
              <span v-if="bildFuer(zeile)" class="dk-chat-av dk-chat-av--bild">
                <img :src="bildFuer(zeile)" alt="" />
              </span>
              <!-- CHAT-7b-UI (Karte Punkt 2): eine RUNDE trägt ihr eigenes
                   Symbol (`runde` aus `ui/symbole.mjs`) statt Initialen —
                   sonst sähe eine Runde wie eine einzelne Person aus. -->
              <span v-else-if="istRundenZeile(zeile)" class="dk-chat-av dk-chat-av--runde">
                <DkSymbol name="runde" :groesse="18" />
              </span>
              <span v-else class="dk-chat-av" aria-hidden="true">{{ initialenFuer(zeile) }}</span>
              <span class="dk-chat-zeile-text">
                <span class="dk-chat-zeile-name">
                  {{ nameFuer(zeile) }}
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
                <!-- KEIN „gelesen“ mehr: der Zähler sagt, ob etwas offen ist
                     (Karte UI-2 Punkt 1). Im 1:1 steht rechts nur die Zeit. -->
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
 *
 * CHAT-7a: Direktgespräche (1:1) tragen `art: 'direkt'`, den Namen des
 * Gegenübers als Titel, dessen Bild (`bild`, sonst Initialen) und IMMER eine
 * Kennung — sie kommen aus `meine_gespraeche` fertig angelegt.
 *
 * CHAT-7a-UI-2 (Review): KEIN Kennzeichen „1:1“ mehr an der Zeile (Punkt 7)
 * — der Abschnitt „Direktnachrichten“ sagt es schon, und ein zweiter Weg,
 * dieselbe Sache zu benennen, ist einer zu viel. Auch das Wort „gelesen“
 * steht hier nicht mehr (Punkt 1): der Lesestand gehört an die Nachricht,
 * nicht in die Liste.
 */
import { computed } from 'vue'
import { initialen as initialenAus } from '../../composables/anzeigename.mjs'
import {
  gespraechHash, listenkopfSichtbar, zeilenAdresse, zeilenSchluessel,
} from '../../composables/nachrichtenLogik.mjs'
import { NEUE_NACHRICHT, SUCHE, direktTitel } from '../../composables/nachrichtenDirekt.mjs'
import {
  NEUE_RUNDE, istRunde, rundenTitel, rundenZeilenText,
} from '../../composables/nachrichtenRunden.mjs'
import DkButton from '../ui/DkButton.vue'
import DkSkelett from '../ui/DkSkelett.vue'
import DkSymbol from '../ui/DkSymbol.vue'

const props = defineProps({
  gruppen: { type: Array, default: () => [] },
  /** Kennung des offenen Gesprächs (leer = keins). */
  aktiv: { type: String, default: '' },
  /** Summe aller ungelesenen Nachrichten. */
  ungelesen: { type: Number, default: 0 },
  laedt: { type: Boolean, default: false },
  /**
   * LEISTE-1: Trägt die Spalte den Kopf „Alle Gespräche“? Die Vollbild-Seite
   * „Nachrichten“ schaltet ihn ab (keine Überschrift, kein doppelter Satz);
   * bleibt der Ungelesen-Zähler, steht dafür eine Zeile.
   */
  kopf: { type: Boolean, default: true },
  /**
   * LEISTE-1: Stehen die zwei Einstiege („Neue Nachricht“, „Neue Runde“) hier
   * in der Liste? Am Desktop JA; am Handy sitzen beide hinter dem Plus im
   * Kopf der Seite — zweimal derselbe Weg wäre einer zu viel.
   */
  neueRunde: { type: Boolean, default: true },
})

const kopfSichtbar = computed(() => listenkopfSichtbar({
  kopf: props.kopf, ungelesen: props.ungelesen,
}))

/**
 * CHAT-7b-UI: „Neue Runde“ öffnet den Dialog der SEITE — das Ereignis geht
 * nach oben, gesendet wird dort (ein Weg, wie beim Umfrage-Dialog).
 */
defineEmits(['neueRunde'])

/**
 * Der Titel einer Zeile — im 1:1 ohne Namen „Unbekannte Person“ (Punkt 6),
 * bei einer Runde ihr Name (leer → „Runde“, nie eine leere Zeile).
 */
const nameFuer = (zeile) => {
  if (String(zeile?.art || '') === 'direkt') return direktTitel(zeile)
  if (istRunde(zeile)) return rundenTitel(zeile)
  return String(zeile?.titel || '')
}
/** Trägt die Zeile das Rundensymbol? (Karte Punkt 2) */
const istRundenZeile = (zeile) => istRunde(zeile)
/**
 * Das Bild des Gegenübers (`bild` aus `meine_gespraeche`) — nur beim 1:1.
 * Eine Gruppe hat kein Bild; dort bleiben die Initialen des Namens.
 */
const bildFuer = (zeile) => (String(zeile?.art || '') === 'direkt'
  ? String(zeile?.bild || '').trim()
  : '')
const initialenFuer = (zeile) => initialenAus(null, nameFuer(zeile) || '')
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
  // CHAT-7b-UI (Karte Punkt 2): eine Runde zeigt zuerst, wie viele dabei sind
  // („4 Beteiligte“) und dann den letzten Beitrag — dieselbe Zeile, eine
  // Auskunft mehr. Ohne letzten Beitrag bleibt es beim ruhigen Hinweis.
  const letzte = String(zeile?.letzte || '').replace(/\s+/g, ' ').trim()
  if (istRunde(zeile)) {
    const zahl = rundenZeilenText(zeile)
    if (letzte) return zahl ? `${zahl} · ${letzte}` : letzte
    return zahl || 'Noch keine Nachrichten'
  }
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
.dk-chat-neu {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  margin: 0 var(--sp-3) var(--sp-2);
  padding: 0 var(--sp-3);
  /* K4: Trefferfläche am Finger — mindestens 44 px. */
  min-height: var(--control-h);
  border: var(--rahmen-breite) dashed var(--divider);
  border-radius: var(--radius);
  color: var(--accent);
  font-size: var(--fs-14);
  font-weight: var(--fw-mittel);
  text-decoration: none;
}
.dk-chat-neu:hover { background: var(--surface-hover); }
.dk-chat-neu:focus-visible { outline: var(--rahmen-breite) solid var(--focus-ring); outline-offset: var(--rahmen-breite); }
.dk-chat-neu-zeichen { font-size: var(--fs-16); line-height: 1; display: inline-flex; align-items: center; }
/* HAUPTKNOPF (27.11.): „Neue Nachricht“ trägt die gefüllte Optik des
   Knopf-Systems (primary). Die Listen-Regel oben (gestrichelter Rahmen,
   Akzent-Schrift, heller Hover) darf sie nicht übermalen. */
.dk-chat-neu--haupt {
  border: var(--rahmen-breite) solid var(--primary);
  background: var(--primary);
  color: var(--primary-ink);
  justify-content: center;
}
.dk-chat-neu--haupt:hover { background: var(--primary-hover); }
/* CHAT-7b-UI: „Neue Runde“ ist derselbe Einstieg als <button> — Optik und
   Trefferfläche wie der Link darüber, nur Textfarbe/Zeiger vom Knopf-Modell. */
.dk-chat-neu--knopf {
  width: auto;
  background: none;
  font-family: inherit;
  cursor: pointer;
  text-align: start;
}
/* Das Rundensymbol sitzt in der Avatar-Fläche, ohne Bild — Strichzeichnung. */
.dk-chat-av--runde { color: var(--muted); }
.dk-chat-abschnitt-titel {
  margin: 0;
  padding: var(--sp-3) var(--sp-4) var(--sp-1);
  font-size: var(--fs-12);
  font-weight: var(--fw-fett);
  letter-spacing: var(--ls-klein);
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
  overflow: hidden;
}
/* Punkt 4: das Bild des Gegenübers — dieselbe Gestalt wie die Initialen
   (rund, gleiche Größe), nur gefüllt. Keine neue Farbe, kein Rahmen. */
.dk-chat-av--bild img { width: 100%; height: 100%; object-fit: cover; }
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
