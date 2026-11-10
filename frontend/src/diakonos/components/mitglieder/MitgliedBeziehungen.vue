<template>
  <!-- DEV-B4a (Befund DMB-72325633c6b5): Der Reiter „Beziehungen" war nur
       lesend. Hier steht die Liste; im Bearbeiten-Modus kommt „Beziehung eintragen"
       (Person suchen + Beziehungsart) und an jeder Zeile „Entfernen" mit
       Rückgängig (UX2c — entfernt wird sofort, die Meldung bietet die
       Rücknahme an). -->
  <DkCard title="Beziehungen">
    <template #actions>
      <span v-if="beziehungen.length" class="mdb-zahl">
        {{ beziehungen.length === 1 ? '1 Beziehung' : beziehungen.length + ' Beziehungen' }}
      </span>
    </template>

    <p v-if="!beziehungen.length" class="mdb-muted">
      Keine Beziehungen eingetragen.
    </p>

    <ul v-else class="mdb-liste">
      <li v-for="b in beziehungen" :key="b.name" class="mdb-zeile">
        <span class="mdb-art">{{ b.beziehungstyp }}</span>
        <a
          v-if="b.beziehung_zu && !b.beziehung_zu_unbekannt"
          class="mdb-name"
          :href="'#/mitglied/' + encodeURIComponent(b.beziehung_zu)"
        >{{ b.beziehung_zu_name || b.beziehung_zu }}</a>
        <span v-else class="mdb-name">{{ b.beziehung_zu_name || b.beziehung_zu || '—' }}</span>
        <DkButton
          v-if="bearbeitbar"
          variant="ghost"
          size="sm"
          class="mdb-entfernen"
          :disabled="laeuft"
          :aria-label="`Beziehung „${b.beziehungstyp}“ zu ${b.beziehung_zu_name || b.beziehung_zu} entfernen`"
          @click="$emit('entfernen', b)"
        >Entfernen</DkButton>
      </li>
    </ul>

    <!-- Nachtrag nur im Bearbeiten-Modus. -->
    <div v-if="bearbeitbar" class="mdb-nachtrag">
      <div v-if="!offen" class="mdb-knopfzeile">
        <DkButton variant="secondary" size="sm" @click="oeffnen">Beziehung eintragen</DkButton>
        <span class="mdb-muted">
          Wer gehört zu dieser Person — Eltern, Kinder, Ehepartner, Geschwister?
        </span>
      </div>

      <div v-else class="mdb-formular">
        <DkField label="Person">
          <MitgliedAuswahl
            ref="auswahl"
            aria-label="Person für die Beziehung auswählen"
            platzhalter="Person suchen und auswählen…"
            :lade-optionen="ladePersonen"
            @ausgewaehlt="personGewaehlt"
          />
        </DkField>
        <DkField label="Beziehungsart">
          <DkSelect v-model="art" :options="artenOptionen" aria-label="Beziehungsart" />
        </DkField>
        <div class="mdb-formular-aktionen">
          <DkButton
            size="sm"
            :loading="laeuft"
            :disabled="!personOderFehler || !art"
            @click="hinzufuegen"
          >Eintragen</DkButton>
          <DkButton variant="ghost" size="sm" :disabled="laeuft" @click="schliessen">
            Abbrechen
          </DkButton>
        </div>
        <p class="mdb-vorschau" aria-live="polite">
          <template v-if="personOderFehler && art">
            {{ personName }} wird als <strong>{{ art }}</strong> eingetragen —
            bei {{ personName }} steht dann „{{ gegenart }}“.
          </template>
          <template v-else>Person und Art wählen.</template>
        </p>
      </div>
    </div>
  </DkCard>
</template>

<script>
/**
 * Exporte NEBEN dem Bauteil (reines `<script>`, damit `export` erlaubt ist).
 *
 * NUR die Beziehungsarten und ihre Gegenrichtung: die Detailseite und der
 * Waechter-Test lesen sie hier (der Server haelt dieselbe Liste in
 * `api/beziehungen.py` — der Test vergleicht beide).
 *
 * Bewusst OHNE eigenen Import: der Server-Zugang kommt als Eigenschaft
 * `api` von der Detailseite herein. So bleibt der Baustein frei von
 * `../`-Wegen und der Mount-Test laedt ihn allein.
 */
export const BEZIEHUNGSARTEN = ['Elternteil', 'Kind', 'Ehepartner', 'Geschwister', 'Sonstiges']

/** A→B vom Typ X bedeutet B→A vom Typ Y (Altcode `_INVERSE`). */
export const GEGENRICHTUNG = {
  Elternteil: 'Kind',
  Kind: 'Elternteil',
  Ehepartner: 'Ehepartner',
  Geschwister: 'Geschwister',
  Sonstiges: 'Sonstiges',
}
</script>

<script setup>
/**
 * MitgliedBeziehungen — Liste + Nachtrag der Beziehungen einer Person.
 *
 * DEV-B4a: Vorher stand der Reiter fest in `MitgliedDetail.vue` (nur lesend).
 * Der Nachtrag fehlt dort ganz: „Beziehung eintragen" (Person suchen + Art),
 * „Entfernen" je Zeile mit Rückgängig auf der Detailseite.
 *
 * Die Server-Zugänge (`api`) und die Meldungsquelle (`melden`) kommen als
 * Eigenschaften von der Detailseite: der Baustein hat dann KEINE
 * `../`-Bezugswege, und der Mount-Test (`tests/dev-b4a-beziehungen.test.mjs`)
 * kann ihn allein kompilieren. Die Aufrufe selbst stehen in
 * `mitgliedBeziehungenApi` (eine Stelle je Endpunkt).
 *
 * Die Auswahlliste ist dieselbe wie beim „Mitglied hinzufügen" einer Gruppe
 * (`MitgliedAuswahl` + `get_beziehungen_auswahl`): nur Name und „schon
 * eingetragen", keine E-Mail (B-1), Suche serverseitig.
 */
import { computed, ref } from 'vue'
import MitgliedAuswahl from '../MitgliedAuswahl.vue'
import DkCard from '../ui/DkCard.vue'
import DkButton from '../ui/DkButton.vue'
import DkField from '../ui/DkField.vue'
import DkSelect from '../ui/DkSelect.vue'

const props = defineProps({
  mitgliedId: { type: String, required: true },
  beziehungen: { type: Array, default: () => [] },
  /** Nur im Bearbeiten-Modus: Nachtrag und Entfernen erscheinen. */
  bearbeitbar: Boolean,
  laeuft: Boolean,
  /**
   * Server-Zugang von AUSSEN: `(methode, argumente) => Promise<any>`.
   *
   * Bewusst als Eigenschaft statt Import im Bauteil: der Baustein hat dann
   * keine `../`-Bezugswege, und der Mount-Test kann ihn allein kompilieren
   * (die Detailseite baut `api` aus `beziehungenApi`).
   */
  api: { type: Function, required: true },
  /** `showToast(text, art)` von aussen (dieselbe Meldungsquelle der App). */
  melden: { type: Function, default: null },
  /** `aktionsfehler(aktion, fehler)` von aussen (Fehlerkatalog, I4). */
  fehlertext: { type: Function, default: null },
})

const emit = defineEmits(['geaendert', 'entfernen'])

// Dieselben Listen wie der Server (`api/beziehungen.py`) — sie stehen oben im
// neutralen `<script>`-Block, damit der Waechter-Test sie vergleichen kann.
const ARTEN = BEZIEHUNGSARTEN
const INVERS = GEGENRICHTUNG

/**
 * Rueckfall fuer den Fehlertext, WENN die Seite keine Quelle hereinreicht
 * (Tests, fremde Einbettung). Die App reicht `fehlertext` aus dem
 * Fehlerkatalog durch (`shared/fehlertexte.js`) — dann gilt dessen Text.
 */
function standardFehlertext(aktion, fehler) {
  const text = String(fehler?.message || '').trim()
  return text || 'Das Speichern hat nicht geklappt. Bitte erneut versuchen.'
}

const artenOptionen = ARTEN.map(a => ({ value: a, label: a }))
const art = ref('')
const person = ref(null)
const offen = ref(false)
const auswahl = ref(null)
const speichert = ref(false)

const personName = computed(() => person.value?.name || '')
const personOderFehler = computed(() => Boolean(person.value?.mitglied))
const gegenart = computed(() => INVERS[art.value] || 'Sonstiges')

function oeffnen() {
  offen.value = true
  if (!art.value) art.value = 'Kind'
  // Die Auswahlliste holt ihre Personen selbst beim ersten Öffnen.
}

function schliessen() {
  offen.value = false
  person.value = null
}

function personGewaehlt(m) {
  person.value = m
  if (m?.in_beziehung) {
    props.melden?.(`Mit ${m.name} besteht bereits eine Beziehung.`, 'info')
  }
}

async function ladePersonen(suche = '') {
  const antwort = await props.api('get_beziehungen_auswahl', {
    mitglied_id: props.mitgliedId,
    suche: suche || '',
  })
  const daten = antwort?.data ?? antwort
  return Array.isArray(daten) ? daten : []
}

async function hinzufuegen() {
  if (speichert.value || !personOderFehler.value) return
  speichert.value = true
  try {
    const antwort = await props.api('add_beziehung', {
      mitglied_id: props.mitgliedId,
      person_id: person.value.mitglied,
      beziehungsart: art.value,
    })
    props.melden?.(
      antwort?.bestand
        ? 'Diese Beziehung bestand bereits.'
        : `${person.value.name} als „${art.value}“ eingetragen.`,
      'success',
    )
    schliessen()
    emit('geaendert')
  } catch (e) {
    // I4: Meldung sagt, was passiert ist; die Eingabe bleibt stehen.
    props.melden?.((props.fehlertext || standardFehlertext)('speichern', e), 'error')
  } finally {
    speichert.value = false
  }
}

defineExpose({ oeffnen, schliessen })
</script>



<style scoped>
.mdb-zahl { color: var(--muted); font-size: var(--fs-sm); }
.mdb-muted { color: var(--muted); margin: 0; }
.mdb-liste {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
}
.mdb-zeile {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  min-height: var(--control-h);
  padding: var(--sp-1) var(--sp-3);
  background: var(--surface-2);
  border-radius: var(--radius);
}
.mdb-art {
  flex: 0 0 auto;
  /* Mindestbreite der Art-Spalte aus der Abstandsskala (Token, kein Literal):
     „Ehepartner" passt hinein, kürzere Arten („Kind") rücken nach, damit die
     Namen auf einer Linie stehen. */
  min-width: var(--sp-7);
  color: var(--muted);
  font-size: var(--fs-sm);
}
.mdb-name {
  flex: 1 1 auto;
  min-width: 0;
  color: var(--text);
  font-weight: var(--fw-mittel);
  overflow-wrap: anywhere;
}
a.mdb-name { text-decoration: none; }
a.mdb-name:hover { text-decoration: underline; }
.mdb-entfernen { flex: 0 0 auto; }
.mdb-nachtrag {
  margin-top: var(--sp-4);
  padding-top: var(--sp-4);
  /* Trenner ohne Maßangabe: `--line` traegt die Farbe, die Staerke kommt aus
     der Rahmen-Regel der Bibliothek. */
  border-top-width: var(--hairline, thin);
}
.mdb-knopfzeile {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--sp-3);
}
.mdb-formular {
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
}
.mdb-formular-aktionen {
  display: flex;
  flex-wrap: wrap;
  gap: var(--sp-2);
}
.mdb-vorschau {
  margin: 0;
  color: var(--muted);
  font-size: var(--fs-sm);
}
/* K4: Klickflaechen kommen aus `--control-h`; `tokens.css` hebt den Wert bei
   grobem Zeiger selbst an (dieselbe Regel wie ueberall). */
</style>

