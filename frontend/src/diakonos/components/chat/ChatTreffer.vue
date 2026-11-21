<template>
  <!-- CHAT-11b — der dritte Abschnitt der Suche: „In Nachrichten“.
       Die Zeilen tragen Gesprächstitel, Absender, Zeit (relativ wie in der
       Gesprächsliste) und den Ausschnitt. Der Ausschnitt kommt vom Server als
       drei Teile reiner Text ({vor, treffer, nach}); hier werden sie
       aneinandergehängt und der mittlere Teil per <mark> hervorgehoben — über
       TEXTINTERPOLATION (dreifache Klammern ohne HTML-Einsatz gibt es hier
       nicht). Ein Text mit „<script>“ bleibt damit sichtbarer Text (Karte,
       Punkt 1). -->
  <section v-if="sichtbar" class="dk-chat-abschnitt dk-treffer" :aria-labelledby="TITEL_ID">
    <h3 :id="TITEL_ID" class="dk-chat-abschnitt-titel">{{ ABSCHNITT_NACHRICHTEN }}</h3>

    <!-- Die Trefferzahl wird angesagt, ohne den Fokus zu stehlen. Solange
         geladen wird, sagt sie „wird gesucht“ — Vorlesehilfe, kein Laden. -->
    <p class="dk-treffer-ansage" aria-live="polite">{{ ansage }}</p>

    <!-- Review R1/3: Geladen wird nur das SKELETT gezeigt, solange es noch
         keine Zeilen gibt. Beim Blättern („Weitere Treffer“) bleibt die Liste
         stehen und der Knopf zeigt den Ladezustand — der Fokus bleibt damit,
         wo er ist, und die gelesenen Zeilen verschwinden nicht. -->
    <DkSkelett
      v-if="zeigtLaedt && !zeilen.length && !zeigtFehler"
      form="zeilen"
      :anzahl="2"
      text="Nachrichten werden gesucht …"
    />
    <ul
      v-if="zeilen.length"
      :id="listenId"
      class="dk-treffer-liste"
      role="listbox"
      :aria-label="ABSCHNITT_NACHRICHTEN"
      :aria-activedescendant="aktiveKennung"
      tabindex="0"
      @keydown="beiTaste"
    >
      <li
        v-for="(zeile, i) in zeilen"
        :id="optionKennung(listenId, i)"
        :key="zeile.nachricht"
        class="dk-treffer-zeile"
        :class="{ 'is-aktiv': i === aktiv }"
        role="option"
        :aria-selected="i === aktiv ? 'true' : 'false'"
        @click="waehlen(zeile)"
      >
        <div class="dk-treffer-kopf">
          <span class="dk-treffer-titel">{{ zeile.titel || 'Gespräch' }}</span>
          <span class="dk-treffer-zeit">{{ zeile.zeit }}</span>
        </div>
        <span v-if="zeile.absender" class="dk-treffer-absender">{{ zeile.absender }}</span>
        <!-- Der Ausschnitt: drei Teile, der mittlere hervorgehoben. Nur Text
             in Klammern — `<mark>` ist das einzige Element, das hier entsteht. -->
        <span class="dk-treffer-ausschnitt"><span>{{ zeile.teile.vor }}</span><mark v-if="zeile.teile.treffer">{{ zeile.teile.treffer }}</mark><span>{{ zeile.teile.nach }}</span></span>
      </li>
    </ul>

    <!-- Ein Fehler beim BLÄTTERN lässt Seite 1 stehen (R1/3) — der Satz steht
         ruhig darunter, keine zweite Trefferfläche. -->
    <p v-if="zeigtFehler" class="dk-chat-fehler dk-treffer-fehler" role="alert">{{ fehler }}</p>
    <p v-else-if="zeigtLeer" class="dk-chat-hinweis dk-treffer-leer">{{ KEINE_TREFFER_TEXT }}</p>

    <DkButton
      v-if="mehr && zeilen.length && !zeigtFehler"
      variant="ghost"
      size="sm"
      class="dk-chat-textknopf dk-treffer-mehr"
      :loading="laedt"
      @click="$emit('mehr')"
    >{{ MEHR_TEXT }}</DkButton>
  </section>
</template>

<script setup>
/**
 * ChatTreffer — „In Nachrichten“ (CHAT-11b, Karte Punkt 1).
 *
 * Die Komponente kennt keine Regel: Filtern, Entprellung, „welche Antwort
 * zählt“, Blättern und der Sprung stehen in
 * `composables/nachrichtenTreffer.mjs` (ohne DOM prüfbar). Hier steht die
 * Verdrahtung: Überschrift, Zeilen, Markierung, Tasten und die Ansage der
 * Trefferzahl.
 *
 * Ein Klick auf eine Zeile ist KEIN Link: der Sprung braucht zuerst die
 * Auskunft des Servers (`chat.nachricht_kontext`) und lädt dann ältere Seiten
 * nach — das tut die Seite (`@waehlen`). Ein Link könnte das nicht.
 */
import { computed } from 'vue'
import DkButton from '../ui/DkButton.vue'
import DkSkelett from '../ui/DkSkelett.vue'
import {
  ABSCHNITT_NACHRICHTEN, KEINE_TREFFER_TEXT, MEHR_TEXT, naechsteTrefferStelle,
  optionKennung, trefferAnsage, trefferTaste,
} from '../../composables/nachrichtenTreffer.mjs'

const props = defineProps({
  /** Die Zeilen aus `trefferAusAntwort` (schon zusammengesetzt). */
  zeilen: { type: Array, default: () => [] },
  /** Steht der Abschnitt überhaupt da? (ab 2 Zeichen — die Suche entscheidet) */
  sichtbar: { type: Boolean, default: false },
  laedt: { type: Boolean, default: false },
  fehler: { type: String, default: '' },
  /** Sagt der Server „es gibt noch mehr“? */
  mehr: { type: Boolean, default: false },
  /** Der gewählte Eintrag (Tastatur). */
  aktiv: { type: Number, default: 0 },
  /**
   * Review R1/8: Die Kennung der Liste kommt von der Suche — das Suchfeld
   * zeigt über `aria-controls`/`aria-activedescendant` auf DIESELBE Liste
   * (Combobox). Ohne Vorgabe bleibt es bei der eigenen Kennung.
   */
  listenId: { type: String, default: 'dk-chat-treffer-liste' },
})

const emit = defineEmits(['waehlen', 'mehr', 'aktiv', 'schliessen'])

const TITEL_ID = 'dk-chat-treffer-titel'

const zeigtFehler = computed(() => Boolean(String(props.fehler || '').trim()))
const zeigtLaedt = computed(() => !zeigtFehler.value && props.laedt)
/** „Keine Treffer“ steht erst, wenn weder geladen noch gefehlt wird. */
const zeigtLeer = computed(() => !zeigtFehler.value && !props.laedt && props.zeilen.length === 0)
const ansage = computed(() => trefferAnsage({
  anzahl: props.zeilen.length, laedt: props.laedt, fehler: props.fehler,
}))
const aktiveKennung = computed(() => (props.zeilen.length
  ? optionKennung(props.listenId, Math.min(props.aktiv, props.zeilen.length - 1))
  : null))

/** Eine Taste in der Liste: ↓/↑ bewegen, Enter öffnet, Escape schließt. */
function beiTaste(ereignis) {
  const absicht = trefferTaste({
    key: ereignis.key,
    isComposing: ereignis.isComposing === true,
    anzahl: props.zeilen.length,
  })
  if (!absicht) return
  ereignis.preventDefault()
  if (absicht === 'schliessen') {
    emit('schliessen')
    return
  }
  if (absicht === 'oeffnen') {
    const zeile = props.zeilen[Math.min(props.aktiv, props.zeilen.length - 1)]
    if (zeile) waehlen(zeile)
    return
  }
  const neu = naechsteTrefferStelle(props.aktiv, absicht === 'weiter' ? 1 : -1, props.zeilen.length)
  emit('aktiv', neu)
}

function waehlen(zeile) {
  if (!zeile) return
  emit('waehlen', zeile)
}
</script>

<style scoped>
.dk-treffer-kopf {
  display: flex;
  align-items: baseline;
  gap: var(--sp-2);
  min-width: 0;
}
.dk-treffer-titel {
  font-size: var(--fs-14);
  font-weight: var(--fw-mittel);
  color: var(--text);
  flex: 1;
  min-width: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.dk-treffer-zeit {
  flex: none;
  font-size: var(--fs-12);
  color: var(--subtle);
  font-variant-numeric: var(--fs-tabular);
}
.dk-treffer-absender {
  display: block;
  font-size: var(--fs-12);
  color: var(--muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
/* Der Ausschnitt: höchstens drei Zeilen (Review R1/9 — der Kommentar sagte
   das vorher, die Regel fehlte). Er ist ein Hinweis, keine Nachricht; der
   volle Text steht nach dem Sprung im Gespräch. `-webkit-line-clamp` trägt
   in allen Zielbrowsern, `line-clamp` steht daneben als künftige Langform.
   Der Server liefert reinen Text: lange Wörter brechen um (`anywhere`). */
.dk-treffer-ausschnitt {
  display: -webkit-box;
  -webkit-line-clamp: 3;
  line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
  margin-top: var(--sp-1);
  font-size: var(--fs-12);
  color: var(--muted);
  overflow-wrap: anywhere;
}
/* Die Markierung: Gold-Fläche (--accent-soft) mit Text-Farbe (--text) — in
   beiden Themes lesbar, und die Standard-Markierung des Browsers (grelles
   Gelb mit schwarzer Schrift) ist im Dunkelmodus unbrauchbar. */
.dk-treffer-ausschnitt mark {
  background: var(--accent-soft);
  color: var(--text);
  border-radius: var(--radius-sm);
  padding: 0 var(--sp-1);
}
.dk-treffer-liste {
  list-style: none;
  margin: 0;
  padding: 0;
}
.dk-treffer-liste:focus-visible {
  outline: var(--rahmen-breite) solid var(--focus-ring);
  outline-offset: calc(var(--rahmen-breite) * -2);
}
.dk-treffer-zeile {
  display: flex;
  flex-direction: column;
  gap: 0;
  padding: var(--sp-2) var(--sp-3);
  border-left: var(--rahmen-breite) solid transparent;
  min-height: var(--control-h);
  cursor: pointer;
}
.dk-treffer-zeile:hover { background: var(--surface-hover); }
.dk-treffer-zeile.is-aktiv {
  background: var(--surface-2);
  border-left-color: var(--focus-ring);
}
.dk-treffer-ansage {
  margin: 0;
  padding: 0 var(--sp-4) var(--sp-1);
  font-size: var(--fs-12);
  color: var(--subtle);
}
.dk-treffer-leer {
  margin: 0;
  padding: var(--sp-2) var(--sp-4);
}
.dk-treffer-fehler {
  margin: 0;
  padding: var(--sp-2) var(--sp-4);
}
.dk-treffer-mehr { margin: var(--sp-1) var(--sp-3); }
@media (max-width: 720px) {
  .dk-treffer-zeile { padding: var(--sp-2); }
}
</style>
