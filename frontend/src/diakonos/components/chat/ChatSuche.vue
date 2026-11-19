<template>
  <!-- CHAT-3c — „Personen und Gespräche suchen“ (Chat-Konzept 10.1 Punkte 2–4,
       10.3). EIN Feld, zwei Trefferarten: oben die Gespräche (aus der schon
       geladenen Liste gefiltert), darunter die Personen (vom Server,
       entprellt). Am Handy dieselbe Komponente in voller Breite.

       Review R1, MUSS 1: Abschnittsüberschriften kommen aus `suchAbschnitte`
       — GENAU EINE „Personen“-Überschrift, und im Listenmodus (Feld leer)
       gar keine. Deshalb steht jede Überschrift in einem `v-if`. -->
  <div class="dk-chat-suche">
    <div class="dk-chat-suchfeld">
      <label class="dk-chat-nur-vorlesen" for="chat-suche">Personen und Gespräche suchen</label>
      <span class="dk-chat-suchzeichen" aria-hidden="true">⌕</span>
      <input
        id="chat-suche"
        ref="feldEl"
        :value="begriff"
        class="dk-chat-suchinput"
        type="search"
        autocomplete="off"
        :placeholder="SUCH_PLATZHALTER"
        @input="beimTippen($event.target.value)"
        @keydown.escape.prevent="leeren"
      />
      <DkButton
        v-if="begriff"
        variant="ghost"
        size="md"
        class="dk-chat-suchweg"
        aria-label="Suche leeren"
        @click="leeren"
      >
        <span aria-hidden="true">✕</span>
      </DkButton>
    </div>

    <!-- Die Fläche der Suche: Gespräche und Personen untereinander. Ein Tipp
         auf eine Trefferzeile meldet ihr Ziel an die Seite (`beiTrefferKlick`). -->
    <div class="dk-chat-suchergebnis" @click="beiTrefferKlick">
      <section v-if="abschnitte.gespraeche.length" class="dk-chat-abschnitt">
        <h3 class="dk-chat-abschnitt-titel">{{ ABSCHNITT_GESPRAECHE }}</h3>
        <ul class="dk-chat-zeilen">
          <template v-for="abschnitt in abschnitte.gespraeche" :key="abschnitt.id">
            <li v-for="zeile in abschnitt.eintraege" :key="zeilenSchluessel(zeile)">
              <a class="dk-chat-zeile dk-chat-treffer" :href="gespraechsZiel(zeile)">
                <span class="dk-chat-av" aria-hidden="true">{{ initialenFuer(zeile.titel) }}</span>
                <span class="dk-chat-zeile-text">
                  <span class="dk-chat-zeile-name">{{ zeile.titel }}</span>
                  <span class="dk-chat-zeile-vorschau">{{ abschnitt.label }}</span>
                </span>
                <span class="dk-chat-zeile-rechts">
                  <span class="dk-chat-zeile-zeit">{{ zeile.zeit }}</span>
                </span>
              </a>
            </li>
          </template>
        </ul>
      </section>

      <!-- Personen: EINE Überschrift (Treffer oder Status), sonst nichts. -->
      <section v-if="abschnitte.personen" class="dk-chat-abschnitt">
        <h3 class="dk-chat-abschnitt-titel">{{ ABSCHNITT_PERSONEN }}</h3>
        <ul v-if="abschnitte.personenZeilen.length" class="dk-chat-zeilen">
          <li v-for="person in abschnitte.personenZeilen" :key="person.mitglied">
            <!-- Mit Konto: das Profil. Ohne Konto: KEIN Link — ausgegraut,
                 nicht antippbar, mit Hinweis (10.1 Punkt 3). Ein <span> ist
                 nicht fokussierbar; der Hinweis trägt die Aussage (SOLL g). -->
            <a
              v-if="person.href"
              class="dk-chat-zeile dk-chat-treffer dk-chat-person"
              :href="person.href"
            >
              <span v-if="person.bild" class="dk-chat-av dk-chat-av--bild">
                <img :src="person.bild" alt="" />
              </span>
              <span v-else class="dk-chat-av" aria-hidden="true">{{ initialenFuer(person.name) }}</span>
              <span class="dk-chat-zeile-text">
                <span class="dk-chat-zeile-name">{{ person.name }}</span>
              </span>
            </a>
            <span v-else class="dk-chat-zeile dk-chat-treffer dk-chat-person is-ohne-konto">
              <span v-if="person.bild" class="dk-chat-av dk-chat-av--bild">
                <img :src="person.bild" alt="" />
              </span>
              <span v-else class="dk-chat-av" aria-hidden="true">{{ initialenFuer(person.name) }}</span>
              <span class="dk-chat-zeile-text">
                <span class="dk-chat-zeile-name">{{ person.name }}</span>
              </span>
              <span class="dk-chat-ohne-konto">{{ person.hinweis }}</span>
            </span>
          </li>
        </ul>

        <!-- Laden, Fehler (mit „Erneut versuchen“). Der leere Fall steht
             NICHT hier: er ist der EINE Leerzustand weiter unten (SOLL c). -->
        <template v-else-if="abschnitte.personenStatus">
          <DkSkelett v-if="zustand === 'laedt'" form="zeilen" :anzahl="2" text="Personen werden gesucht …" />
          <DkEmpty
            v-else
            icon="⚠"
            title="Die Personensuche hat nicht geklappt"
            :text="fehler"
            :erneut-versuchen="erneutVersuchen"
          />
        </template>
      </section>

      <!-- GENAU EIN Leerzustand, und nur wenn wirklich nichts gefunden wurde. -->
      <DkEmpty
        v-if="abschnitte.leer"
        class="dk-chat-suchnichts"
        icon="⌕"
        :title="SUCHE_LEER.titel"
        :text="SUCHE_LEER.text"
      />

      <!-- Ein Zeichen: die Suche bleibt offen, die Liste steht NICHT darunter. -->
      <p v-if="zuKurz" class="dk-chat-suchleer">
        Bitte mindestens {{ SUCHE_MIN_ZEICHEN }} Zeichen eingeben.
      </p>
    </div>
  </div>
</template>

<script setup>
/**
 * ChatSuche — das eine Suchfeld über der Gesprächsliste (CHAT-3c).
 *
 * Die Komponente kennt keine Regel: Filtern, Entprellung, „welche Antwort
 * zählt“, „antippbar oder nicht“, welche Überschrift wann steht, kommen aus
 * `composables/nachrichtenSuche.mjs` (ohne DOM prüfbar). Hier steht die
 * Verdrahtung: Feld, Timer, Aufruf von `chat.personen_suchen`, Adresse
 * (`#/nachrichten/suche?q=…`).
 *
 * Quelle der Wahrheit für den Suchbegriff ist DAS FELD (Review R1, MUSS 3).
 * `startBegriff` ist der EINGANG von außen (Aufbau aus `#/nachrichten/suche?
 * q=…` oder Zurück vom Profil) und überschreibt das Feld nur, solange niemand
 * tippt. Die Adresse wird nur nachgezogen (`sucht`), nie zurückgelesen.
 *
 * Ein Treffer ist ein NORMALES `<a href>`: der Browser springt, der Router
 * hört das `hashchange` (CHAT-3c-2, MUSS A). Die Komponente fängt den Klick
 * NICHT ab — sonst stünde die neue Adresse da, ohne dass die Seite wechselte,
 * und Strg-/Mittelklick könnte nicht in einem neuen Tab öffnen. Die
 * Suchadresse bleibt im Verlauf davor stehen, damit „Zurück“ vom Profil die
 * Suche mit Begriff und Treffern wiederfindet (Review R1, SOLL e).
 *
 * CHAT-3c-2: Ein Treffer führt schlicht auf sein Ziel (`#/mitglied/<id>` bzw.
 * `#/nachrichten/<kennung>`) — kein Sonderweg, keine Kennung von außen. Die
 * Seite braucht dafür keine Kenntnis des offenen Gesprächs mehr.
 */
import { computed, onUnmounted, ref, watch } from 'vue'
import { apiGet } from '../../composables/useApi.js'
import { fehlertext } from '../../../shared/fehlertexte.js'
import { initialen } from '../../composables/anzeigename.mjs'
import {
  gespraechHash, zeilenAdresse, zeilenSchluessel,
} from '../../composables/nachrichtenLogik.mjs'
import {
  ABSCHNITT_GESPRAECHE, ABSCHNITT_PERSONEN, ENTPRELLUNG_MS, SUCH_PLATZHALTER, SUCHE_LEER,
  SUCHE_MIN_ZEICHEN, darfPersonenFragen, entpreller, gespraechsTreffer, personenAusAntwort,
  personenZustand, suchAbschnitte, suchbegriff,
} from '../../composables/nachrichtenSuche.mjs'
import DkButton from '../ui/DkButton.vue'
import DkEmpty from '../ui/DkEmpty.vue'
import DkSkelett from '../ui/DkSkelett.vue'

const props = defineProps({
  /** Gesuche Liste (`meine_gespraeche`) — Gespräche werden hieraus gefiltert. */
  gespraeche: { type: Array, default: () => [] },
  /** Der Begriff von außen (Adresse, Zurück vom Profil) — Eingang, kein Rückweg. */
  startBegriff: { type: String, default: '' },
  /** Timer/Netz hineinreichen: der Test gibt Attrappen, der Betrieb nichts. */
  timer: { type: Function, default: null },
  timerAus: { type: Function, default: null },
  holen: { type: Function, default: null },
})

/** `sucht` = Begriff für die Adresse; `treffer` = gewählter Verlauf/Profil. */
const emit = defineEmits(['sucht', 'treffer'])

const begriff = ref(String(props.startBegriff || '').trim())
const feldEl = ref(null)
const personen = ref([])
const laedt = ref(false)
const fehler = ref('')
/**
 * Laufende Nummer jeder Anfrage. Eine Antwort zählt nur, wenn ihre Nummer noch
 * die jüngste ist — so entscheidet der START, was aufgeholt wird, und ein
 * zweiter Aufruf je Tastendruck kann sich nicht gegenseitig wegwerfen.
 */
let anfrageNr = 0
/** Sind wir noch da? Eine späte Antwort schreibt dann nichts mehr. */
let aktiv = true

const holen = props.holen || ((parameter) => apiGet('chat.personen_suchen', parameter))

const rohBegriff = computed(() => String(begriff.value ?? '').trim())
const gespraeche = computed(() => gespraechsTreffer(props.gespraeche, rohBegriff.value))
const zustand = computed(() => personenZustand({
  begriff: begriff.value, laedt: laedt.value, fehler: fehler.value, treffer: personen.value,
}))
const abschnitte = computed(() => suchAbschnitte({
  gespraeche: gespraeche.value, zustand: zustand.value, personen: personen.value,
}))
/** Ein Zeichen: Suche offen (keine Liste darunter), aber niemand wird gefragt. */
const zuKurz = computed(() => rohBegriff.value !== '' && !darfPersonenFragen(rohBegriff.value))
const initialenFuer = (name) => initialen(null, name)

/**
 * Personen fragen — mit dem Begriff, für den der Entpreller fällig wurde.
 * Kommt die Antwort zu einer inzwischen geänderten Eingabe, wird sie
 * VERWORFEN (nur die Antwort zur letzten Eingabe zählt).
 */
async function personenHolen(gefragt) {
  if (!aktiv || !darfPersonenFragen(gefragt)) return
  const nummer = ++anfrageNr
  laedt.value = true
  fehler.value = ''
  try {
    const antwort = await holen({ q: suchbegriff(gefragt) })
    if (!aktiv || nummer !== anfrageNr) return
    personen.value = personenAusAntwort(antwort)
  } catch (f) {
    if (!aktiv || nummer !== anfrageNr) return
    personen.value = []
    fehler.value = fehlertext(f, { text: 'Die Personen konnten nicht gesucht werden. Versuche es noch einmal.' })
  } finally {
    if (aktiv && nummer === anfrageNr) laedt.value = false
  }
}

/**
 * Zustand der Personenfläche auf „unbekannt“ stellen — eine noch laufende
 * Anfrage darf nichts mehr schreiben (Review R1, SOLL b: offenen Entpreller
 * stoppen, personen/fehler zurücksetzen).
 */
function zuruecksetzen() {
  anfrageNr += 1
  personen.value = []
  fehler.value = ''
  laedt.value = false
  bremse.abbrechen()
}

function suchen(gefragt) {
  if (!darfPersonenFragen(gefragt)) return
  bremse.tippen(gefragt)
}

const bremse = entpreller({
  warte: ENTPRELLUNG_MS,
  ...(props.timer ? { timer: props.timer } : {}),
  ...(props.timerAus ? { timerAus: props.timerAus } : {}),
  beiFaelligkeit: (gefragt) => personenHolen(gefragt),
})

/** Ein Tastendruck: Personenfläche sofort leeren, Termin neu stellen. */
function beimTippen(wert) {
  begriff.value = String(wert ?? '')
  zuruecksetzen()
  emit('sucht', rohBegriff.value)
  suchen(begriff.value)
}

/** Leeren: Feld leer, Suche bleibt offen bis das Feld leer ist (Seite). */
function leeren() {
  beimTippen('')
  if (feldEl.value && typeof feldEl.value.focus === 'function') feldEl.value.focus()
}

/** „Erneut versuchen“ der Fehlerfläche — dieselbe Eingabe, sofort. */
function erneutVersuchen() {
  personenHolen(begriff.value)
}

/**
 * Das Ziel einer Gesprächszeile: die Kennung des Treffers, sonst der Ort einer
 * noch nicht geöffneten Gruppe (die Seite legt sie beim Öffnen an).
 *
 * Review R1, SOLL 7: `geschwisterAdresse` ist entfallen — der Such-Eintrag
 * braucht keine Sonderadresse mehr. Der Sprung hängt das Ziel hinten an den
 * Verlauf; „Zurück“ führt auf die Suche (mit Begriff und Treffern).
 */
function gespraechsZiel(zeile) {
  return gespraechHash(zeilenAdresse(zeile))
}

/**
 * Ein Treffer wurde angetippt (Person mit Konto oder Gespräch — beide sind ein
 * Link). Die KOMPONENTE fängt den Klick NICHT ab (CHAT-3c-2, MUSS A): das
 * `<a href>` springt wie jeder andere Link, der Browser feuert `hashchange`,
 * der Router wechselt die Seite, und Strg-/Mittelklick öffnet einen neuen Tab.
 *
 * Der Such-Eintrag bleibt dabei im Verlauf stehen (Review R1, SOLL e): eine
 * Navigation hängt ihr Ziel HINTEN an, sie ersetzt den Eintrag nicht.
 *
 * Ein Klick neben die Zeile (Hintergrund der Trefferfläche) tut nichts. Der
 * Treffer OHNE Konto ist ein <span> ohne Link — er landet hier nie.
 */
function beiTrefferKlick(ereignis) {
  const ziel = ereignis?.target
  const treffer = typeof ziel?.closest === 'function'
    ? ziel.closest('a.dk-chat-treffer')
    : null
  if (!treffer) return
  emit('treffer', treffer.getAttribute('href') || '')
}

/**
 * Der Begriff kommt von der SEITE (nicht von einer Eingabe): `#/nachrichten/
 * suche?q=…` wurde erneut zur Adresse — Zurück vom Profil, Vorwärts, ein
 * geteilter Link. Feld und Treffer stellen sich darauf ein; die Suche fragt
 * neu, denn die Treffer der Komponente gehören zum alten Begriff.
 *
 * Das ist der EINZIGE Weg, auf dem die Adresse das Feld schreiben darf: er
 * kommt von außen (Zurück/Vor), nie vom laufenden Tippen (MUSS 3). Das Feld
 * bleibt unberührt — der Fokus bleibt also, wo er war (Review R1, SOLL 3).
 */
function begriffSetzen(wert) {
  const neu = String(wert ?? '').trim()
  if (neu === rohBegriff.value) return
  begriff.value = neu
  zuruecksetzen()
  suchen(neu)
}

onUnmounted(() => {
  aktiv = false
  bremse.beenden()
})

/**
 * Der Begriff von AUSSEN (Aufbau aus der Adresse, Zurück vom Profil mit einem
 * anderen Begriff) — übernehmen und EINMAL fragen. Ist er derselbe, bleibt
 * alles stehen (Zurück vom Profil: Feld und Treffer sind noch da; SOLL e).
 */
watch(() => props.startBegriff, (neu) => {
  const eingang = String(neu || '').trim()
  if (eingang === rohBegriff.value) return
  begriff.value = eingang
  zuruecksetzen()
  suchen(eingang)
})

// Beim Aufbau: steht schon ein Begriff in der Adresse, wird er gesucht.
if (darfPersonenFragen(begriff.value)) personenHolen(begriff.value)

defineExpose({ zustand, abschnitte, begriffSetzen, anfrageNr: () => anfrageNr })
</script>

<style scoped>
.dk-chat-suche {
  display: flex;
  flex-direction: column;
  min-height: 0;
  flex: 1;
}
.dk-chat-suchfeld {
  display: flex;
  align-items: center;
  gap: var(--sp-1);
  margin: 0 var(--sp-3) var(--sp-2);
  padding: 0 var(--sp-2);
  min-height: var(--control-h);
  border: var(--rahmen-breite) solid var(--rahmen-farbe);
  border-radius: var(--radius);
  background: var(--surface);
  box-shadow: var(--schatten-eingabe);
  flex: none;
}
.dk-chat-suchzeichen { color: var(--subtle); flex: none; }
.dk-chat-suchinput {
  flex: 1;
  min-width: 0;
  border: none;
  background: none;
  color: var(--text);
  font-family: inherit;
  font-size: var(--fs-14);
  padding: var(--sp-1) 0;
}
.dk-chat-suchinput:focus { outline: none; }
.dk-chat-suchfeld:focus-within {
  outline: var(--rahmen-breite) solid var(--focus-ring);
  outline-offset: var(--rahmen-breite);
}
.dk-chat-suchweg {
  flex: none;
  border: none;
  background: none;
  color: var(--muted);
  font-family: inherit;
  font-size: var(--fs-12);
  cursor: pointer;
  padding: var(--sp-1) var(--sp-2);
  min-width: var(--control-h);
  min-height: var(--control-h);
}
.dk-chat-suchergebnis {
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow-y: auto;
  padding-bottom: var(--sp-2);
}
/* Abschnittstitel: dieselbe Gestalt wie in `ChatListe.vue` (dort ohne Token
   für die Sperrung) — hier mit einem Token aus `tokens.css`. */
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
  padding: 0;
}
/* Dieselbe Zeile wie die Gesprächsliste (K4: 44 px Trefferfläche). */
.dk-chat-zeile {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  padding: var(--sp-2) var(--sp-3);
  border-left: var(--rahmen-breite) solid transparent;
  text-decoration: none;
  color: var(--text);
  min-height: var(--control-h);
}
a.dk-chat-zeile:hover { background: var(--surface-hover); }
a.dk-chat-zeile:focus-visible {
  outline: var(--rahmen-breite) solid var(--focus-ring);
  outline-offset: calc(var(--rahmen-breite) * -2);
}
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
.dk-chat-av--bild img { width: 100%; height: 100%; object-fit: cover; }
.dk-chat-zeile-text {
  display: flex;
  flex-direction: column;
  min-width: 0;
  flex: 1;
}
.dk-chat-zeile-name {
  font-size: var(--fs-14);
  font-weight: var(--fw-mittel);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.dk-chat-zeile-vorschau {
  font-size: var(--fs-12);
  color: var(--muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.dk-chat-zeile-rechts { flex: none; }
.dk-chat-zeile-zeit {
  font-size: var(--fs-12);
  color: var(--subtle);
  font-variant-numeric: var(--fs-tabular);
}
/* Person OHNE Konto: ausgegraut, ohne Zeiger, kein Link (10.1 Punkt 3). Nur
   vorhandene Stufen (--subtle/--surface-2/--ausgegraut), keine neue Farbe. */
.dk-chat-person.is-ohne-konto {
  color: var(--subtle);
  cursor: default;
  background: var(--surface-2);
}
.dk-chat-person.is-ohne-konto .dk-chat-av { opacity: var(--ausgegraut); }
.dk-chat-person.is-ohne-konto .dk-chat-zeile-name { font-weight: var(--fw-normal); }
.dk-chat-ohne-konto {
  flex: none;
  padding: 0 var(--sp-2);
  border-radius: var(--badge-r);
  background: var(--surface);
  color: var(--subtle);
  font-size: var(--fs-12);
  white-space: nowrap;
}
.dk-chat-suchleer {
  margin: 0;
  padding: var(--sp-1) var(--sp-4) var(--sp-2);
  color: var(--muted);
  font-size: var(--fs-12);
}
.dk-chat-suchnichts { padding: var(--sp-4); }
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
/* Handy: dieselbe Komponente, volle Breite (die Spalte füllt sie ohnehin). */
@media (max-width: 720px) {
  .dk-chat-suchfeld { margin: 0 var(--sp-2) var(--sp-2); }
}
</style>
