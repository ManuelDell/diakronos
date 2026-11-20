<template>
  <!-- CHAT-3a: Sprechblase einer Nachricht (eigene rechts, fremde links).
       Farben und Abstände kommen aus tokens.css (--marke-flaeche/--marke-ink für
       die eigene Blase, --surface/--line für die fremde, --subtle/--surface-2 für
       die Ausgrauung) — es gibt KEINE neue Farbe (Konzept 6.3, 10.3).

       CHAT-3a-4 (MUSS 2): Zwei Spalten — AVATAR | INHALT. Der Avatar steht
       links oben neben Name und erster Blase (vorher rutschte er unter die
       Blase, weil die Zeile `align-items: flex-end` hatte); die Aktionen
       gehören zur INHALTSSPALTE. Am Handy (und an eigenen Nachrichten) ist
       die Avatar-Spalte leer, damit die Blase nicht wandert. -->
  <li
    class="dk-chat-beitrag"
    :class="{ 'is-ich': nachricht.eigene, 'is-geloescht': nachricht.geloescht }"
    :data-name="nachricht.ident || nachricht.name || nachricht.id"
  >
    <!-- CHAT-3a-4 (MUSS 2): Der Avatar steht in der EIGENEN Spalte links
         oben — ein reines CSS-Element, ohne eigenen Zustand: die Spalte
         bleibt in jeder Zeile (die Blase springt nicht), der Text wird nur am
         Folgenanfang gefüllt (`folgeStart` von der Seite). Eigene Nachrichten
         tragen die Spalte gespiegelt und leer. -->
    <span class="dk-chat-av" aria-hidden="true">{{ zeigeAvatar ? initialen : '' }}</span>
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
        <!-- CHAT-3a-4 (SOLL 4): EINE kompakte Aktionszeile — Symbolknöpfe mit
             aria-label/title, gebaut aus `DkButton` (UX1g2: kein roher
             <button>). Am Desktop bei Hover/Fokus sichtbar, am Handy dauerhaft
             (dort gibt es kein Hover; die Trefferflächen sind 44 px). Sie
             bleibt im DOM und damit per Tastatur erreichbar: Fokus zeigt sie
             (`:focus-within` am Beitrag), kein eigener Zustand nötig.

             CHAT-3a-5 (A): Am HANDY stehen Antworten, Bearbeiten und Löschen
             in EINEM „⋯“-Menü (Baustein `DkAktionen`), das „＋“ für die
             Reaktion bleibt eigener Knopf. Vorher lagen 2–4 Knöpfe à 44 px
             dauerhaft in jeder Kopfzeile — bei 390 px lief sie über und jede
             Nachricht bekam 44 px Kopf. Der Desktop-Zweig bleibt unverändert. -->
        <div v-if="!nachricht.geloescht" class="dk-chat-aktionen">
          <DkButton
            v-if="!hatReaktion"
            variant="ghost"
            size="sm"
            class="dk-chat-aktion"
            :aria-expanded="auswahlOffen ? 'true' : 'false'"
            :aria-label="auswahlOffen ? 'Reaktionen schließen' : 'Reaktion setzen'"
            title="Reaktion setzen"
            @click="auswahlOffen = !auswahlOffen"
          ><template #icon><span aria-hidden="true">＋</span></template></DkButton>
          <!-- CHAT-6-UI: „Melden“ an FREMDEN, nicht gelöschten Nachrichten —
               am Desktop als Symbolknopf mit aria-label in derselben
               Aktionszeile, am Handy im „⋯“-Menü (`menueEintraege`). Die
               eigene Nachricht lässt sich nicht melden (der Server sagt
               dasselbe). -->
          <DkButton
            v-if="!handyLage && darfMelden"
            variant="ghost"
            size="sm"
            class="dk-chat-aktion"
            :aria-label="MELDE_TEXTE.melden"
            :title="MELDE_TEXTE.melden"
            @click="$emit('melden', nachricht)"
          ><template #icon><DkSymbol name="melden" :groesse="14" /></template></DkButton>
          <!-- Desktop: die drei Aktionen als eigene Symbolknöpfe (unverändert). -->
          <DkButton
            v-if="!handyLage"
            variant="ghost"
            size="sm"
            class="dk-chat-aktion"
            aria-label="Antworten"
            title="Antworten"
            @click="$emit('antworten', nachricht)"
          ><template #icon><span aria-hidden="true">↩</span></template></DkButton>
          <DkButton
            v-if="!handyLage && bearbeitbar"
            variant="ghost"
            size="sm"
            class="dk-chat-aktion"
            aria-label="Bearbeiten"
            title="Bearbeiten"
            @click="$emit('bearbeiten', nachricht)"
          ><template #icon><span aria-hidden="true">✎</span></template></DkButton>
          <DkButton
            v-if="!handyLage && nachricht.eigene"
            variant="ghost"
            size="sm"
            class="dk-chat-aktion is-loeschen"
            aria-label="Löschen"
            title="Löschen"
            @click="$emit('loeschen', nachricht)"
          ><template #icon><span aria-hidden="true">🗑</span></template></DkButton>
          <!-- Handy: dieselben Aktionen in EINEM „⋯“-Menü (`DkAktionen`,
               Entwurf B1 — gefährliche Aktion abgesetzt und in Rot). -->
          <span v-if="handyLage" class="dk-chat-aktionen-menue">
            <DkAktionen
              :eintraege="menueEintraege"
              :label="`Aktionen für die Nachricht von ${nachricht.autor || 'Unbekannt'}`"
              :kennung="`chat-nachricht-${nachricht.id}`"
            />
          </span>
        </div>
      </div>

      <!-- Gelöschte Nachricht: die Lücke bleibt sichtbar (Soft-Delete) — als
           ruhige Zeile, nie als leerer Kasten, und NIE mit Inhalt. -->
      <!-- CHAT-5-UI: Eine Umfrage erscheint als KARTE an der Stelle der
           Nachricht — statt der Blase, damit Balken und Knöpfe die Breite
           haben. Gelöscht → die Lücke (darunter). -->
      <slot v-if="!nachricht.geloescht" name="karte" />
      <div v-if="nachricht.geloescht" class="dk-chat-geloescht">{{ nachricht.hinweis }}</div>
      <!-- CHAT-9b: „@Name“-Stellen, die zu einem Eintrag in `erwaehnt`
           passen, werden hervorgehoben. Der Text bleibt TEXT: jedes Stück
           steht als `{{ }}` im DOM (kein `v-html`) — ein Anzeigename mit
           „<b>“ bleibt sichtbarer Text und wird nicht ausgeführt. Erwähnt die
           Nachricht die LESENDE Person, trägt die Blase zusätzlich
           `is-erwaehnt` (dezente Markierung, Token-Farben). -->
      <div
        v-else-if="!$slots.karte"
        class="dk-chat-blase"
        :class="[nachricht.eigene ? 'is-ich' : 'is-andere', { 'is-erwaehnt': binIchErwaehnt }]"
      ><template v-for="(stueck, i) in textStuecke" :key="i"><span
          v-if="stueck.erwaehnung"
          class="dk-chat-erwaehnung"
          :class="{ 'is-meine': stueck.meine }"
        >{{ stueck.text }}</span><template v-else>{{ stueck.text }}</template></template></div>

      <!-- Reaktionen: gesetzte Zeichen; „＋“ steht nur da, wenn noch KEINE
           Reaktion gesetzt ist (CHAT-3a-4, SOLL 4). Dann sitzt es — wie die
           übrigen Aktionen — in der einen Aktionszeile im Kopf; hier steht es
           neben vorhandenen Reaktionen, sobald es schon welche gibt. -->
      <div v-if="reaktionen.length" class="dk-chat-reaktionen">
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

      <!-- Fußzeile einer Nachricht: der Lesestand an EIGENEN Nachrichten —
           im 1:1 „gelesen“ (Stand des Gegenübers), in der Gruppe „gelesen von
           N“ (F2: nur Summe). Er steht NUR hier, an der Nachricht, nie in der
           Liste oder im Kopf (CHAT-7a-UI-2, Punkt 1). Die Aktionen (Reaktion,
           Antworten, Bearbeiten, Löschen) stehen seit CHAT-3a-4 oben in der
           Aktionszeile — hier bleibt nur der Lesestand. -->
      <div v-if="!nachricht.geloescht && lesestand" class="dk-chat-fuss">
        <span class="dk-chat-gelesen">
          <span aria-hidden="true">✓✓</span> {{ lesestand }}
        </span>
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
 *
 * CHAT-3a-4:
 *   * Avatar in der eigenen Spalte, nur an der ERSTEN Nachricht einer Folge
 *     (`folgeStart` von der Seite über `:folge-start` gesetzt; ohne Angabe
 *     immer). Aktionen in EINER Zeile im Kopf, kompakt und per Tastatur
 *     erreichbar.
 */
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import DkButton from '../ui/DkButton.vue'
import DkAktionen from '../ui/DkAktionen.vue'
import DkSymbol from '../ui/DkSymbol.vue'
import { initialen as initialenAus } from '../../composables/anzeigename.mjs'
import { innerhalbFrist, lesestandText } from '../../composables/nachrichtenLogik.mjs'
import { reaktionsAuswahl, reaktionsZeile } from '../../composables/nachrichtenReaktionen.mjs'
// CHAT-6-UI: „Melden“ nur an fremden, nicht gelöschten Nachrichten — dieselbe
// Regel prüft der Server beim Senden erneut (`meldbar` sagt nur, ob der Knopf
// bzw. Menüeintrag angeboten wird).
import { TEXTE as MELDE_TEXTE, meldbar } from './meldung.mjs'
// CHAT-9b: „@Name“ hervorheben (Text bleibt Text) und die dezente Markierung
// „hier bin ich erwähnt“ — beides entscheidet die Regel in `erwaehnung.mjs`.
import { binErwaehnt, hervorheben } from './erwaehnung.mjs'

const props = defineProps({
  nachricht: { type: Object, required: true },
  /** Erste Nachricht einer Folge (gleicher Autor)? Dann steht der Avatar da. */
  folgeStart: { type: Boolean, default: true },
  /**
   * Steht die Blase in einem 1:1-Gespräch? (CHAT-7a-UI-2, Punkt 1)
   *
   * Der Lesestand ist im 1:1 der Stand des GEGENÜBERS an der EIGENEN
   * Nachricht — dort heißt er „gelesen“, nicht „gelesen von 1“. Die Regel
   * steht in `lesestandText(n, { direkt })`; die Blase reicht die Lage nur
   * durch und rät sie NICHT aus der Nachricht.
   */
  direkt: { type: Boolean, default: false },
  /**
   * Handy-Lage — kommt von der SEITE als Prop (CHAT-N3).
   *
   * Vorher rief JEDE Blase `useHandyLage()` selbst auf: bei 200 Nachrichten
   * hingen 200 `matchMedia`-Beobachter und 200 `resize`-Horcher am Fenster.
   * `Nachrichten.vue` fragt die Lage EINMAL und reicht sie hier herein; die
   * Blase entscheidet nur noch, WAS sie zeigt (Menü oder Symbolknöpfe), und
   * beobachtet selbst nichts. Ohne Angabe gilt Desktop (`false`).
   */
  handyLage: { type: Boolean, default: false },
  /**
   * CHAT-9b: die MITGLIED-Kennung der lesenden Person — nur für die dezente
   * Markierung „diese Nachricht erwähnt mich“. Ohne Angabe gibt es keine
   * Markierung; geraten wird nichts.
   */
  ich: { type: String, default: '' },
})
const emit = defineEmits(['reaktion', 'antworten', 'bearbeiten', 'loeschen', 'melden'])

const auswahlOffen = ref(false)
const reaktionen = computed(() => reaktionsZeile(props.nachricht.reaktionen))
const hatReaktion = computed(() => reaktionen.value.some((r) => r.anzahl > 0))
const alleZeichen = computed(() => reaktionsAuswahl(props.nachricht.reaktionen))
const initialen = computed(() => initialenAus(null, props.nachricht.autor || ''))
const lesestand = computed(() => lesestandText(props.nachricht, { direkt: props.direkt === true }))
/** CHAT-6-UI: Darf DIESE Nachricht gemeldet werden (fremd, nicht gelöscht)? */
const darfMelden = computed(() => meldbar(props.nachricht))
/**
 * CHAT-9b: der Text in Stücken — „@Name“-Stellen hervorgehoben, sonst reiner
 * Text. Grundlage ist NUR die Serverliste `erwaehnt` der Nachricht.
 */
const textStuecke = computed(() => hervorheben(props.nachricht.text, props.nachricht.erwaehnt, { ich: props.ich }))
/** Ist die LESENDE Person in dieser Nachricht erwähnt? (dezente Markierung) */
const binIchErwaehnt = computed(() => binErwaehnt(props.nachricht, { ich: props.ich }))
/** Der Avatar gehört an den Anfang einer Folge — und nie an eigene Zeilen. */
const zeigeAvatar = computed(() => props.nachricht.eigene !== true && props.folgeStart !== false)

/**
 * CHAT-3a-5 (A), CHAT-N3: Handy-Lage — EINE Quelle, aber nicht mehr hier.
 *
 * Vorher entschied nur CSS über die Aktionszeile; für ein „⋯“-Menü genügt das
 * nicht: dann stünden am Handy ZWEI Sätze Aktionen im DOM (Knöpfe und Menü).
 * Die Komponente wählt deshalb selbst — am Handy Menü + „＋“, am Desktop die
 * drei Symbolknöpfe wie bisher. Die LAGE kommt seit CHAT-N3 als Prop von der
 * Seite (`Nachrichten.vue` fragt `useHandyLage()` genau einmal); die Blase
 * hängt keine eigenen Beobachter ans Fenster.
 */
const handyLage = computed(() => props.handyLage === true)

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

/**
 * CHAT-3a-5 (A): Die Einträge des Handy-Menüs — genau die Aktionen, die am
 * Desktop als Symbolknöpfe stehen, in derselben Reihenfolge und mit derselben
 * Erlaubnis: Antworten (immer), Bearbeiten (nur eigene, innerhalb der Frist),
 * Melden (nur fremde, nicht gelöschte — CHAT-6-UI), Löschen (nur eigene,
 * gefährlich → abgesetzt am Ende, Entwurf B1).
 * Die Ausführung meldet dieselben Ereignisse wie die Knöpfe; die Seite bleibt
 * die einzige Stelle, die etwas sendet.
 */
const menueEintraege = computed(() => {
  const liste = [
    { key: 'antworten', label: 'Antworten', icon: 'antworten', aktion: () => emit('antworten', props.nachricht) },
  ]
  if (bearbeitbar.value) {
    liste.push({ key: 'bearbeiten', label: 'Bearbeiten', icon: 'stift', aktion: () => emit('bearbeiten', props.nachricht) })
  }
  if (darfMelden.value) {
    liste.push({ key: 'melden', label: MELDE_TEXTE.melden, icon: 'melden', aktion: () => emit('melden', props.nachricht) })
  }
  if (props.nachricht.eigene === true) {
    liste.push({ key: 'loeschen', label: 'Löschen', icon: 'loeschen', gefahr: true, aktion: () => emit('loeschen', props.nachricht) })
  }
  return liste
})

/** Ein Tipp auf ein Zeichen: setzen, wechseln oder entfernen (Regel im Modul). */
function waehlen(zeichen) {
  auswahlOffen.value = false
  emit('reaktion', { nachricht: props.nachricht, reaktion: zeichen })
}
</script>

<style scoped>
/* CHAT-3a-4 (MUSS 2): Zwei Spalten — Avatar | Inhalt. Der Avatar steht links
   OBEN (Name/erste Blase), nicht unter der Blase. Eigene Nachrichten spiegeln
   die Spalten (Avatar rechts, dort leer), die Blase bleibt rechtsbündig. */
.dk-chat-beitrag {
  display: grid;
  grid-template-columns: var(--sp-6) minmax(0, 1fr);
  column-gap: var(--sp-2);
  align-items: start;
  list-style: none;
  margin: 0;
}
.dk-chat-beitrag.is-ich { grid-template-columns: minmax(0, 1fr) var(--sp-6); }
.dk-chat-av {
  width: var(--sp-6);
  height: var(--sp-6);
  border-radius: 50%;
  display: grid;
  place-items: center;
  margin-top: var(--sp-1);
  background: var(--surface-2);
  color: var(--muted);
  font-size: var(--fs-12);
  font-weight: var(--fw-fett);
}
/* Leere Avatar-Zelle (Folge-Zeile, eigene Nachricht): die SPALTE bleibt, damit
   Namen und Blasen aller Zeilen auf einer Flucht stehen — nur Kreis und
   Fläche fehlen. `:empty` statt einer Klasse: kein Zustand nötig. */
.dk-chat-av:empty {
  background: none;
  border-radius: 0;
}
/* Folge-Zeilen und eigene Zeilen: die Spalte bleibt (Blase springt nicht),
   nur der Kreis fehlt — die Zeile ist dann einfach leer. */
.dk-chat-beitrag.is-ich .dk-chat-av { order: 2; }
.dk-chat-inhalt {
  display: flex;
  flex-direction: column;
  gap: var(--sp-1);
  min-width: 0;
  max-width: 74%;
}
.dk-chat-beitrag.is-ich .dk-chat-inhalt { grid-column: 1; align-items: flex-end; }

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
  align-items: center;
  padding: 0 var(--sp-1);
  min-height: var(--sp-5);
}
.dk-chat-name { font-size: var(--fs-12); font-weight: var(--fw-fett); color: var(--text); min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.dk-chat-zeit { font-size: var(--fs-12); color: var(--subtle); font-variant-numeric: var(--fs-tabular); }
.dk-chat-bearbeitet { font-size: var(--fs-12); color: var(--subtle); }

/* CHAT-3a-4 (SOLL 4): EINE Zeile mit Symbolknöpfen. Am Desktop ruhig (erst
   bei Hover/Fokus eingeblendet), am Handy immer da. Sie bleibt bedienbar:
   `opacity` nimmt nichts aus der Fokusfolge — Tab holt sie hervor.

   CHAT-3a-5 (A): Die Zeile darf nie breiter werden als ihr Inhalt —
   `flex-wrap: nowrap` OHNE Mindestbreite, und der Inhalt darf schrumpfen
   (`min-width: 0`). Am Handy steht dort nur noch „＋“ und „⋯“ (zwei
   Trefferflächen à 44 px). */
.dk-chat-aktionen {
  display: flex;
  align-items: center;
  gap: var(--sp-1);
  margin-left: auto;
  min-width: 0;
  opacity: 0;
  transition: opacity var(--fast) var(--ease);
}
.dk-chat-beitrag:hover .dk-chat-aktionen,
.dk-chat-beitrag:focus-within .dk-chat-aktionen { opacity: 1; }
/* Der „⋯“-Auslöser (DkAktionen) sitzt bündig in der Zeile: kein eigener
   Rahmen, dieselbe Höhe wie die Symbolknöpfe. Die Maße selbst gehören dem
   Baustein (44 px am groben Zeiger, K4) — hier wird nichts überschrieben. */
.dk-chat-aktionen-menue { display: inline-flex; flex: none; }
.dk-chat-aktion {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: var(--sp-6);
  height: var(--sp-6);
  padding: 0;
  border: none;
  border-radius: var(--badge-r);
  background: transparent;
  color: var(--subtle);
  font-family: inherit;
  font-size: var(--fs-12);
  line-height: 1;
  cursor: pointer;
}
.dk-chat-aktion:hover { background: var(--surface-hover); color: var(--text); }
.dk-chat-aktion:focus-visible { outline: var(--rahmen-breite) solid var(--focus-ring); outline-offset: var(--rahmen-breite); }
.dk-chat-aktion.is-loeschen:hover { color: var(--err); }

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

/* CHAT-9b: „@Name“-Stellen, die zu `erwaehnt` passen — nur Darstellung, der
   Text bleibt Text. Die Fläche ist die vorhandene Akzent-Weichfarbe (hell
   Gold-Beige, dunkel durchscheinendes Gold aus `--accent-soft`), die Schrift
   bleibt die Schrift der Blase. Kein Unterstrich: es ist kein Verweis. */
.dk-chat-erwaehnung {
  padding: 0 var(--sp-1);
  border-radius: var(--radius-sm);
  background: var(--accent-soft);
  font-weight: var(--fw-fett);
}
/* In der EIGENEN Blase (Markenfläche, weiße Schrift) trägt die Hervorhebung
   über die halbtransparente Weichfarbe — der Rahmen hält sie auch im hellen
   Token sichtbar, ohne eine neue Farbe zu erfinden.
   R1/8: EIN Ring, nicht zwei (vorher box-shadow + outline übereinander). */
.dk-chat-blase.is-ich .dk-chat-erwaehnung {
  background: transparent;
  box-shadow: inset 0 0 0 var(--rahmen-breite) var(--marke-ink);
}
/* Die Erwähnung der LESENDEN Person: dieselbe Hervorhebung, eine Stufe
   kräftiger (Akzentlinie) — die Blase selbst ist zusätzlich markiert. */
.dk-chat-erwaehnung.is-meine {
  border: var(--rahmen-breite) solid var(--accent);
}
.dk-chat-blase.is-ich .dk-chat-erwaehnung.is-meine {
  box-shadow: inset 0 0 0 var(--rahmen-breite) var(--accent);
}

/* Erwähnt mich diese Nachricht? Dezente Markierung: ein Streifen der
   Akzentfarbe an der Blase (Richtung egal, keine neue Fläche) und ein etwas
   festerer Rahmen an der fremden Blase. Beide Themes über Tokens.
   R1/8: Die Breite ist ein Vielfaches von `--rahmen-breite` (kein loses 3px). */
.dk-chat-blase.is-erwaehnt {
  box-shadow: inset calc(var(--rahmen-breite) * 3) 0 0 0 var(--accent);
  border-color: var(--accent);
}
.dk-chat-blase.is-erwaehnt.is-ich {
  border: var(--rahmen-breite) solid var(--accent);
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
  min-height: var(--sp-4);
}
.dk-chat-gelesen { font-size: var(--fs-12); color: var(--subtle); }

/* Handy: die Blase nimmt mehr Breite (Konzept 6.3: 74 % statt 520 px). */
@media (max-width: 720px) {
  .dk-chat-inhalt { max-width: 82%; }
}

/* CHAT-3a-4 (SOLL 4/SOLL 3): In der Handy-Lage stehen die Aktionen dauerhaft
   in EINER Zeile (kein Hover am Finger) — und ihre Trefferflächen sind
   Daumengröße (`--control-h` = 44 px am groben Zeiger). */
.dk-app--handy .dk-chat-aktionen { opacity: 1; }
.dk-app--handy .dk-chat-aktion {
  width: var(--control-h);
  height: var(--control-h);
}
@media (pointer: coarse) {
  .dk-chat-aktionen { opacity: 1; }
  .dk-chat-aktion {
    width: var(--control-h);
    height: var(--control-h);
  }
}
</style>
