<template>
  <!-- CHAT-3a: Sprechblase einer Nachricht (eigene rechts, fremde links).
       Farben und Abstände kommen aus tokens.css (--marke-flaeche/--marke-ink für
       die eigene Blase, --surface/--line für die fremde, --subtle/--surface-2 für
       die Ausgrauung) — es gibt KEINE neue Farbe (Konzept 6.3, 10.3). -->
  <li
    class="dk-chat-beitrag"
    :class="{ 'is-ich': nachricht.eigene, 'is-geloescht': nachricht.geloescht }"
    :data-name="nachricht.id"
  >
    <span v-if="!nachricht.eigene" class="dk-chat-av" aria-hidden="true">{{ initialen }}</span>
    <div class="dk-chat-inhalt">
      <!-- Antwort-Zitat: eine Zeile über der Blase (Chat-Konzept 1/S1) -->
      <div v-if="nachricht.antwort_auf && nachricht.antwortText" class="dk-chat-zitat">
        <span class="dk-chat-zitat-marke" aria-hidden="true">↳</span>
        <span>{{ nachricht.antwortText }}</span>
      </div>
      <div v-else-if="nachricht.antwort_auf" class="dk-chat-zitat is-leer">
        <span class="dk-chat-zitat-marke" aria-hidden="true">↳</span>
        <span>Antwort auf eine gelöschte Nachricht</span>
      </div>

      <div class="dk-chat-kopf">
        <span v-if="!nachricht.eigene" class="dk-chat-name">{{ nachricht.autor || 'Unbekannt' }}</span>
        <span class="dk-chat-zeit">{{ nachricht.zeit }}</span>
        <span v-if="nachricht.bearbeitet && !nachricht.geloescht" class="dk-chat-bearbeitet">bearbeitet</span>
      </div>

      <!-- Gelöschte Nachricht: die Lücke bleibt sichtbar (Soft-Delete) — als
           ruhige Zeile, nie als leerer Kasten, und NIE mit Inhalt. -->
      <p v-if="nachricht.geloescht" class="dk-chat-geloescht">{{ nachricht.hinweis }}</p>
      <div v-else class="dk-chat-blase" :class="nachricht.eigene ? 'is-ich' : 'is-andere'">{{ nachricht.text }}</div>

      <!-- Reaktionen: gesetzte Zeichen + „+“ zum Setzen (festes Set aus dem Model) -->
      <div class="dk-chat-reaktionen">
        <button
          v-for="r in reaktionen"
          :key="r.reaktion"
          type="button"
          class="dk-chat-reaktion"
          :class="{ 'is-meine': r.meines }"
          :aria-pressed="r.meines ? 'true' : 'false'"
          :aria-label="`${r.reaktion} ${r.anzahl > 0 ? `${r.anzahl} Mal` : 'als Reaktion'}`"
          @click="$emit('reaktion', { nachricht, reaktion: r.reaktion })"
        >
          <span aria-hidden="true">{{ r.reaktion }}</span>
          <span v-if="r.anzahl > 0" class="dk-chat-reaktion-zahl">{{ r.anzahl }}</span>
        </button>
        <button
          type="button"
          class="dk-chat-reaktion is-plus"
          :aria-expanded="auswahlOffen ? 'true' : 'false'"
          :aria-label="auswahlOffen ? 'Reaktionen schließen' : 'Reaktion setzen'"
          @click="auswahlOffen = !auswahlOffen"
        >
          <span aria-hidden="true">＋</span>
        </button>
      </div>
      <div v-if="auswahlOffen" class="dk-chat-auswahl" role="group" aria-label="Reaktion wählen">
        <button
          v-for="z in alleZeichen"
          :key="z.reaktion"
          type="button"
          class="dk-chat-reaktion"
          :class="{ 'is-meine': z.meines }"
          :aria-label="`Mit ${z.reaktion} reagieren`"
          @click="waehlen(z.reaktion)"
        >{{ z.reaktion }}</button>
      </div>

      <!-- Fußzeile einer Nachricht: „gelesen von N“ (F2: nur Summe) an EIGENEN;
           Antworten (auch auf eigene — der Gedanke kann nachgetragen werden),
           Bearbeiten (15 Minuten, zur ANZEIGEZEIT geprüft) und Löschen an
           eigenen. -->
      <div v-if="!nachricht.geloescht" class="dk-chat-fuss">
        <span v-if="lesestand" class="dk-chat-gelesen">
          <span aria-hidden="true">✓✓</span> {{ lesestand }}
        </span>
        <DkButton
          variant="ghost"
          size="sm"
          class="dk-chat-textknopf"
          @click="$emit('antworten', nachricht)"
        >Antworten</DkButton>
        <DkButton
          v-if="bearbeitbar"
          variant="ghost"
          size="sm"
          class="dk-chat-textknopf"
          @click="$emit('bearbeiten', nachricht)"
        >Bearbeiten</DkButton>
        <DkButton
          v-if="nachricht.eigene"
          variant="ghost"
          size="sm"
          class="dk-chat-textknopf"
          @click="$emit('loeschen', nachricht)"
        >Löschen</DkButton>
      </div>
    </div>
  </li>
</template>

<script setup>
/**
 * ChatBlase — eine Nachricht im Verlauf (CHAT-3a).
 *
 * Der Baustein ZEICHNET nur: was drin steht, entscheidet
 * `composables/nachrichtenLogik.mjs` (`verlaufsZeile`, `lesestandText`), welche
 * Reaktionen es gibt `composables/nachrichtenReaktionen.mjs`. Die Ereignisse
 * (`reaktion`, `bearbeiten`, `loeschen`) gehören der Seite — hier wird nichts
 * gesendet.
 *
 * Sicherheit: der Text steht als Text im DOM (`{{ }}`), nie als HTML. Der
 * Server liefert reine Textnachrichten (S1: keine Formatierung außer
 * Zeilenumbruch) — `white-space: pre-line` hält die Absätze.
 */
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { initialen as initialenAus } from '../../composables/anzeigename.mjs'
import { innerhalbFrist, lesestandText } from '../../composables/nachrichtenLogik.mjs'
import { reaktionsAuswahl, reaktionsZeile } from '../../composables/nachrichtenReaktionen.mjs'
import DkButton from '../ui/DkButton.vue'

const props = defineProps({
  nachricht: { type: Object, required: true },
})
const emit = defineEmits(['reaktion', 'antworten', 'bearbeiten', 'loeschen'])

const auswahlOffen = ref(false)
const reaktionen = computed(() => reaktionsZeile(props.nachricht.reaktionen))
const alleZeichen = computed(() => reaktionsAuswahl(props.nachricht.reaktionen))
const initialen = computed(() => initialenAus(null, props.nachricht.autor || ''))
const lesestand = computed(() => lesestandText(props.nachricht))

/**
 * Bearbeitbar zur ANZEIGEZEIT prüfen (Review R1).
 *
 * `bearbeitbar` kommt aus `verlaufsZeile` (Stand des letzten Abrufs). Ohne Poll
 * in diesem Gespräch stünde der Stift auch noch 20 Minuten später da — der
 * Server lehnte dann mit 417 ab. Deshalb prüft die Blase die 15-Minuten-Frist
 * gegen die laufende Uhr nach: ein ruhiger Takt (30 s) zieht sie nach und wird
 * beim Abbau abgeräumt (EIN Timer je Blase, kein Leck).
 *
 * CHAT-3a-3 (Klein): Der Takt ENDET, sobald die Frist abgelaufen ist — vorher
 * lief er bis zum Abbau der Blase weiter und setzte alle 30 s einen Wert, der
 * nichts mehr ändern konnte (bis zu 50 Timer auf einer Verlaufsseite, die nie
 * zur Ruhe kommen). Geprüft wird die ECHTE Frist des Servers
 * (`innerhalbFrist`), nicht eine zweite Zeitrechnung.
 */
const jetzt = ref(new Date())
let fristTimer = null
function fristBeenden() {
  if (fristTimer) clearInterval(fristTimer)
  fristTimer = null
}
onMounted(() => {
  if (props.nachricht?.bearbeitbar !== true) return
  if (!innerhalbFrist(props.nachricht.erstellt_am, jetzt.value)) return // schon vorbei
  fristTimer = setInterval(() => {
    jetzt.value = new Date()
    // Abgelaufen: nichts mehr nachzuziehen — Takt einstellen (kein Leerlauf).
    if (!innerhalbFrist(props.nachricht.erstellt_am, jetzt.value)) fristBeenden()
  }, 30_000)
})
onBeforeUnmount(fristBeenden)
const bearbeitbar = computed(() => props.nachricht.eigene === true
  && props.nachricht.geloescht !== true
  && props.nachricht.bearbeitbar === true
  && innerhalbFrist(props.nachricht.erstellt_am, jetzt.value))

/** Ein Tipp auf ein Zeichen: setzen, wechseln oder entfernen (Regel im Modul). */
function waehlen(zeichen) {
  auswahlOffen.value = false
  emit('reaktion', { nachricht: props.nachricht, reaktion: zeichen })
}
</script>

<style scoped>
.dk-chat-beitrag {
  display: flex;
  gap: var(--sp-2);
  align-items: flex-end;
  list-style: none;
  margin: 0;
}
.dk-chat-beitrag.is-ich { flex-direction: row-reverse; }
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
.dk-chat-inhalt {
  display: flex;
  flex-direction: column;
  gap: var(--sp-1);
  min-width: 0;
  max-width: 74%;
}
.dk-chat-beitrag.is-ich .dk-chat-inhalt { align-items: flex-end; }

/* Antwort-Zitat: ruhig, klein, über der Blase — es zeigt eine Zeile. */
.dk-chat-zitat {
  display: flex;
  gap: var(--sp-1);
  align-items: baseline;
  max-width: 100%;
  padding: var(--sp-1) var(--sp-2);
  border-left: var(--rahmen-breite) solid var(--line-strong);
  color: var(--muted);
  font-size: var(--fs-12);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.dk-chat-zitat-marke { color: var(--subtle); flex: none; }
.dk-chat-zitat.is-leer { font-style: italic; }

.dk-chat-kopf {
  display: flex;
  gap: var(--sp-2);
  align-items: baseline;
  padding: 0 var(--sp-1);
}
.dk-chat-name { font-size: var(--fs-12); font-weight: var(--fw-fett); color: var(--text); }
.dk-chat-zeit { font-size: var(--fs-12); color: var(--subtle); font-variant-numeric: var(--fs-tabular); }
.dk-chat-bearbeitet { font-size: var(--fs-12); color: var(--subtle); }

/* Die Blase: eigene in der Markenfläche (Schrift --marke-ink, beide Themes
   lesbar), fremde auf der Kartenfläche mit Rahmen. Die Zeilenumbrüche der
   Nachricht bleiben erhalten (`pre-line`), lange Wörter brechen um. */
.dk-chat-blase {
  padding: var(--sp-2) var(--sp-3);
  border-radius: var(--radius-lg);
  font-size: var(--fs-14);
  line-height: var(--lh-text);
  white-space: pre-line;
  overflow-wrap: anywhere;
}
.dk-chat-blase.is-andere {
  background: var(--surface);
  color: var(--text);
  border: var(--rahmen-breite) solid var(--rahmen-farbe);
}
.dk-chat-blase.is-ich {
  background: var(--marke-flaeche);
  color: var(--marke-ink);
}

/* Gelöschte Nachricht: Hinweiszeile statt Kasten — die Lücke bleibt sichtbar. */
.dk-chat-geloescht {
  margin: 0;
  padding: var(--sp-2) var(--sp-3);
  border-radius: var(--radius-lg);
  border: var(--rahmen-breite) dashed var(--line-strong);
  background: var(--surface-2);
  color: var(--subtle);
  font-size: var(--fs-12);
  font-style: italic;
}

.dk-chat-reaktionen {
  display: flex;
  gap: var(--sp-1);
  flex-wrap: wrap;
  margin-top: var(--sp-1);
}
.dk-chat-auswahl {
  display: flex;
  gap: var(--sp-1);
  margin-top: var(--sp-1);
  padding: var(--sp-1) var(--sp-2);
  border-radius: var(--radius);
  background: var(--surface-2);
}
.dk-chat-reaktion {
  display: inline-flex;
  align-items: center;
  gap: var(--sp-1);
  /* K4: am Finger mindestens 44 px — hier über --control-h, das am groben
     Zeiger 44 px ist. Ein Emoji-Knopf ist eine Trefferfläche, kein Text. */
  min-height: var(--sp-5);
  padding: 0 var(--sp-2);
  border-radius: var(--badge-r);
  border: var(--rahmen-breite) solid var(--rahmen-farbe);
  background: var(--surface);
  color: var(--muted);
  font-size: var(--fs-12);
  cursor: pointer;
  font-family: inherit;
}
.dk-chat-reaktion:hover { background: var(--surface-hover); }
.dk-chat-reaktion.is-meine {
  background: var(--accent-soft);
  border-color: var(--accent);
  color: var(--text);
  font-weight: var(--fw-fett);
}
.dk-chat-reaktion.is-plus { color: var(--subtle); }
.dk-chat-reaktion:focus-visible { outline: var(--rahmen-breite) solid var(--focus-ring); outline-offset: var(--rahmen-breite); }
.dk-chat-reaktion-zahl { font-variant-numeric: var(--fs-tabular); }

.dk-chat-fuss {
  display: flex;
  gap: var(--sp-2);
  align-items: center;
  padding: 0 var(--sp-1);
  flex-wrap: wrap;
}
.dk-chat-gelesen { font-size: var(--fs-12); color: var(--subtle); }
/* Die Fußzeilen-Aktionen sind DkButton (ghost/sm) — hier bleibt nur die Größe
   der Beschriftung, damit sie zur Zeile (12 px) passt. */
.dk-chat-textknopf { font-size: var(--fs-12); }

/* Handy: die Blase nimmt mehr Breite (Konzept 6.3: 74 % statt 520 px). */
@media (max-width: 720px) {
  .dk-chat-inhalt { max-width: 82%; }
}
</style>
