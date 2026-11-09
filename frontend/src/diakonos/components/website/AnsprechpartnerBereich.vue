<template>
  <DkCard title="Ansprechpartner" anker="ansprechpartner">
    <div class="wa-bereich" data-wa-abschnitt="ansprechpartner">
      <!-- P1 (Kartenvorgabe): Die Einwilligung wird hier NIE gesetzt — nur
           die Funktionen, die erscheinen dürfen. Der Hinweis steht an erster
           Stelle, damit niemand danach sucht. -->
      <DkHint variant="info">{{ EINWILLIGUNG_NUR_SELBST }}</DkHint>

      <DkSkelett v-if="laedt && !stand.daten" kurz form="zeilen" :anzahl="3" text="Die Ansprechpartner werden geladen …" />
      <DkHint v-else-if="fehler" variant="err" role="alert">{{ fehler }}</DkHint>

      <template v-else>
        <!-- ── Gespeicherte Bereiche ───────────────────────────────────── -->
        <h3 class="wa-titel">Bereiche auf der Website</h3>
        <p class="wa-hilfe">
          Je Bereich erscheint die Person, die im Organigramm die Leitung
          innehat — aber nur, wenn sie selbst im Profil zugestimmt hat.
          Ein Kontakt-Postfach ersetzt die E-Mail-Adresse: es erscheint nur
          der Postfach-Name, nie eine persönliche Adresse.
        </p>

        <DkEmpty
          v-if="!zeilen.length"
          title="Keine Bereiche ausgewählt"
          text="Ohne Auswahl erscheint kein Ansprechpartner auf der Website."
        />
        <ul v-else class="wa-liste">
          <li v-for="(z, i) in zeilen" :key="z.schluessel" class="wa-zeile" :data-wa-zeile="z.schluessel">
            <div class="wa-zeile-haupt">
              <span class="wa-art">{{ artLabel(z.art) }}</span>
              <span class="wa-name">{{ bereichBezeichnung(z, katalog[z.art]) }}</span>
            </div>
            <DkField
              :label="`Kontakt-Postfach für ${bereichBezeichnung(z, katalog[z.art])}`"
              :help="postfachHilfe(z)"
            >
              <!-- BS-3b: eine Zeile OHNE Postfach speichert `null` (der Server
                   kennt nur „Slug oder keines“); `''` wäre ein unbekannter Slug. -->
              <!-- Der Wert kommt aus dem SERVERSTAND (daten.bereiche), nicht aus
                   der berechneten Zeile: `zeilen` wird bei jeder Änderung neu
                   gebaut, ein Schreibzugriff darauf ginge verloren. -->
              <DkSelect
                :model-value="postfachWert(z)"
                :options="postfachOptionen"
                :empty-value="null"
                :disabled="speichert"
                @update:model-value="eintragAendern(i, $event)"
              />
            </DkField>
            <DkButton
              size="md"
              variant="ghost"
              :disabled="speichert"
              :aria-label="`${bereichBezeichnung(z, katalog[z.art])} entfernen`"
              @click="bereichEntfernen(z)"
            >Entfernen</DkButton>
          </li>
        </ul>

        <!-- ── Bereich übernehmen ──────────────────────────────────────── -->
        <div class="wa-neu">
          <DkField label="Funktion oder Position übernehmen">
            <div class="wa-neu-zeile">
              <DkSelect v-model="neu.art" :options="BEREICH_ARTEN" aria-label="Art des Bereichs" />
              <DkSelect
                v-model="neu.funktion"
                :options="funktionOptionen"
                aria-label="Funktion oder Position"
              />
              <DkButton
                variant="secondary"
                :disabled="!neu.funktion || bereitsGewaehlt(zeilen, neu.art, neu.funktion)"
                @click="bereichHinzufuegen"
              >Übernehmen</DkButton>
            </div>
          </DkField>
          <p v-if="!funktionOptionen.length" class="wa-hilfe">
            Im Organigramm ist für diese Art nichts eingetragen.
          </p>
          <p v-else-if="neu.funktion && bereitsGewaehlt(zeilen, neu.art, neu.funktion)" class="wa-hilfe">
            Dieser Bereich steht schon in der Liste.
          </p>
        </div>

        <div class="wa-aktionen">
          <DkButton
            variant="primary"
            :loading="speichert"
            :disabled="!standGeladen || !geaendertJetzt"
            :aria-disabled="geaendertJetzt ? undefined : 'true'"
            @click="speichernJetzt"
          >Speichern</DkButton>
          <span v-if="!geaendertJetzt" class="wa-hilfe">
            Es gibt noch nichts zu speichern.
          </span>
        </div>

        <DkHint v-if="meldung" :variant="meldung.ton" role="alert">{{ meldung.text }}</DkHint>

        <!-- ── Vorschau: wer erscheint gerade ──────────────────────────── -->
        <section class="wa-vorschau" data-wa-vorschau>
          <h3 class="wa-titel">Vorschau: was jetzt auf der Website steht</h3>
          <p class="wa-hilfe">
            Gezeigt wird genau der öffentliche Stand — also nur Personen, die
            selbst zugestimmt haben. Wer hier fehlt, ist nicht öffentlich; die
            Einwilligung kann nur die Person im eigenen Profil erteilen.
          </p>
          <DkHint v-if="oeffentlichFehler" variant="warn" role="status">{{ oeffentlichFehler }}</DkHint>
          <DkEmpty
            v-else-if="!oeffentlich.length"
            title="Niemand erscheint gerade"
            text="Entweder ist kein Bereich ausgewählt oder die zuständigen Personen haben noch nicht zugestimmt."
          />
          <ul v-else class="wa-oeffentlich">
            <li v-for="e in oeffentlich" :key="(e.funktion || e.bereich) + ':' + e.name" class="wa-oeffentlich-zeile">
              <span class="wa-name">{{ e.name }}</span>
              <span class="wa-art">{{ e.bereich }}</span>
              <span v-if="e.postfach" class="wa-hilfe">Kontakt über ein Postfach</span>
            </li>
          </ul>
          <p v-if="nichtOeffentlich.length" class="wa-hilfe" data-wa-ohne-einwilligung>
            {{ nichtOeffentlich.length === 1 ? 'Ein ausgewählter Bereich' : `${nichtOeffentlich.length} ausgewählte Bereiche` }}
            erscheinen nicht, weil die zuständige Person (noch) nicht zugestimmt
            hat oder niemand eingetragen ist.
          </p>
          <DkButton variant="secondary" size="md" @click="oeffentlichenStandLaden">Vorschau neu laden</DkButton>
        </section>
      </template>
    </div>
  </DkCard>
</template>

<script setup>
/**
 * BS-3b — Bereich „Ansprechpartner“ auf der Website-Seite (Website-Rolle).
 *
 * Zeigt und pflegt die VERWALTUNGSENTSCHEIDUNG aus BS-3a: welche
 * Funktionen/Positionen aus dem Organigramm als Ansprechpartner erscheinen
 * dürfen, je Bereich optional ein Kontakt-Postfach (Slug aus BS-1a).
 *
 * Was dieses Bauteil ABSICHTLICH NICHT kann (Kartenvorgabe P1/P2):
 *   • eine Einwilligung setzen oder widerrufen — weder für sich (dafür ist das
 *     Profil zuständig) noch für andere (der Server lehnt das mit 403 ab);
 *   • Namen von Personen zeigen, die nicht zugestimmt haben. Die
 *     Verwaltungs-API liefert keine Personendaten (G1); die Vorschau liest
 *     ausschließlich den ÖFFENTLICHEN Stand.
 *
 * Bedienung: DkSelect/DkField/DkButton, genau EIN Primärknopf (Speichern),
 * gespeichert wird nur bei Änderung (UX3h3-Muster), mobile Spalten bei 390 px.
 */
import { computed, onMounted, reactive, ref, watch } from 'vue'
import {
  BEREICH_ARTEN,
  EINWILLIGUNG_NUR_SELBST,
  auswahlGeaendert as geaendert,
  bereicheZeilen,
  auswahlZeile,
  bereitsGewaehlt,
  bereichBezeichnung,
} from '../../../shared/website-einwilligung.mjs'
import { useAnsprechpartnerBereiche } from '../../composables/useAnsprechpartnerBereiche.js'
import DkButton from '../ui/DkButton.vue'
import DkCard from '../ui/DkCard.vue'
import DkEmpty from '../ui/DkEmpty.vue'
import DkField from '../ui/DkField.vue'
import DkHint from '../ui/DkHint.vue'
import DkSelect from '../ui/DkSelect.vue'
import DkSkelett from '../ui/DkSkelett.vue'

const {
  daten: datenRoh, laedt, fehler, speichert,
  katalog, postfaecher,
  oeffentlich, oeffentlichFehler,
  laden, setzen, oeffentlichenStandLaden,
} = useAnsprechpartnerBereiche()

/**
 * Der Serverstand als EIGENE, tief reaktive Kopie.
 *
 * BS-3b (Befund im Mount-Test): Wird `daten` (ein `ref` im Composable) im
 * Bauteil über `stand.daten = { ...stand.daten, bereiche: [...] }` ersetzt und
 * daraus unmittelbar eine berechnete Liste abgeleitet, blieb „geändert?“
 * (und damit „Speichern“) im Prüfstand gesperrt, obwohl die Liste den neuen
 * Wert zeigte. Mit EINEM explizit reaktiven Objekt (`reactive`) ist jede
 * Änderung an `.bereiche` eine gemeldete Mutation — kein Sonderfall beim
 * Ersetzen des ganzen Stands.
 */
const stand = reactive({ daten: null })
/** Den Serverstand in die reaktive Kopie übernehmen (nach Laden und Speichern). */
function standUebernehmen(neu) {
  // JSON-Kopie: `structuredClone` scheitert an verschachtelten reaktiven
  // Proxys (z. B. nach `setzen`: `{ ...daten.value, bereiche }`).
  stand.daten = neu ? JSON.parse(JSON.stringify(neu)) : null
}
// `flush: 'sync'` (Befund im Mount-Test): mit dem Vorgabe-Zeitplan läuft der
// Watch-Rückruf erst NACH dem Rendern — die berechneten Zeilen sahen dann den
// alten `null`-Stand. Synchron heißt: der Stand steht, sobald er da ist.
watch(datenRoh, standUebernehmen, { immediate: true, flush: 'sync' })


/** Die Zeilenliste, wie sie gerade GESPEICHERT wäre. */
const zeilen = computed(() => bereicheZeilen(stand.daten))

const meldung = ref(null)
const neu = reactive({ art: 'dienstbereich', funktion: '' })

const auswahlGeaendert = (antwortstand, liste) => geaendert(antwortstand, liste)
/** Weicht die Auswahl vom geladenen Stand ab? (UX3h3-Muster.) */
// Verglichen wird der ENTWURF (`zeilen`, aus `stand`) mit dem unveränderten
// SERVERSTAND (`datenRoh`) — `stand` selbst ist der Entwurf und taugt nicht
// als Vergleichsbasis (sonst ist „geändert?“ immer falsch).
const geaendertJetzt = computed(() => Boolean(datenRoh.value) && auswahlGeaendert(datenRoh.value, zeilen.value))
/** Reine Anzeige-Frage: hat der Server überhaupt einen Stand geliefert? */
const standGeladen = computed(() => Boolean(stand.daten))

const artLabel = (art) => (BEREICH_ARTEN.find((a) => a.value === art) || { label: art }).label

const postfachOptionen = computed(() => [
  { value: '', label: 'Kein Postfach' },
  ...postfaecher.value.map((p) => ({ value: p.slug, label: p.bezeichnung })),
])

const funktionOptionen = computed(() =>
  (katalog.value[neu.art] || []).map((e) => ({ value: e.funktion, label: e.bezeichnung })),
)

/** Bereiche, die ausgewählt sind, aber (noch) nicht öffentlich erscheinen. */
const nichtOeffentlich = computed(() => {
  if (!zeilen.value.length) return []
  if (oeffentlich.value.length >= zeilen.value.length) return []
  return zeilen.value.filter((z) => {
    const name = bereichBezeichnung(z, katalog.value[z.art])
    return !oeffentlich.value.some((e) => String(e.bereich || '') === name)
  })
})

/** Postfach-Slug einer Zeile aus dem SERVERSTAND (leer, wenn keines). */
function postfachWert(z) {
  const roh = stand.daten?.bereiche
  const eintrag = Array.isArray(roh)
    ? roh.find((e) => String(e?.art || '').toLowerCase() === z.art
      && String(e?.funktion || '') === z.funktion)
    : null
  return String(eintrag?.postfach || '')
}

function postfachHilfe(z) {
  if (!postfachOptionen.value.length) return 'Es sind keine Postfächer angelegt.'
  return z.postfach ? 'Erscheint als Kontaktweg — nie eine persönliche Adresse.' : 'Ohne Postfach erscheint kein Kontaktweg.'
}

/**
 * Eine Zeile ändern (Postfach). Geschrieben wird auf den SERVERSTAND
 * (`daten.bereiche`) — `zeilen` ist eine BERECHNETE Liste; ein Schreibzugriff
 * darauf ginge verloren (Befund im Mount-Test: der Knopf blieb gesperrt).
 *
 * Gesucht wird der Eintrag über den SCHLÜSSEL der Zeile (Art + Funktion), und
 * zwar aus dem AKTUELLEN `zeilen`-Stand dieser Auswertung — nicht aus einem
 * mitgegebenen Objekt, das nach einer Änderung veraltet ist.
 */
function eintragAendern(index, wert) {
  const roh = stand.daten?.bereiche
  if (!Array.isArray(roh)) return
  const schluessel = zeilen.value[index]?.schluessel
  if (!schluessel) return
  // IN PLACE ändern: `roh` ist die reaktive Liste; ein neues Objekt an
  // `stand.daten` zu hängen ginge an den abgeleiteten Zeilen vorbei.
  roh.forEach((eintrag) => {
    const eigener = `${String(eintrag?.art || '').toLowerCase()}:${String(eintrag?.funktion || '')}`
    if (eigener === schluessel) eintrag.postfach = String(wert || '')
  })
  meldung.value = null
}

function bereichHinzufuegen() {
  if (!neu.funktion) return
  if (bereitsGewaehlt(zeilen.value, neu.art, neu.funktion)) return
  const naechste = zeilen.value.length
  // `zeilen` ist eine berechnete Liste — die Änderung muss auf den
  // Serverstand, damit „geändert?“ und „Speichern“ stimmen.
  if (stand.daten && Array.isArray(stand.daten.bereiche)) {
    stand.daten.bereiche.push({
      art: neu.art, funktion: neu.funktion, bezeichnung: '', postfach: null, sortierung: naechste,
    })
    stand.daten = { ...stand.daten }
  }
  neu.funktion = ''
  meldung.value = null
}

function bereichEntfernen(z) {
  if (!stand.daten || !Array.isArray(stand.daten.bereiche)) return
  const rest = zeilen.value
    .filter((eintrag) => eintrag.schluessel !== z.schluessel)
    .map((eintrag, i) => ({ ...eintrag, sortierung: i }))
  stand.daten = { ...stand.daten, bereiche: rest.map((e) => auswahlZeile(e)) }
  meldung.value = null
}

async function speichernJetzt() {

  if (!geaendertJetzt.value) return
  meldung.value = null
  const ergebnis = await setzen(zeilen.value)
  meldung.value = ergebnis.ok
    ? { ton: 'success', text: 'Die Ansprechpartner sind gespeichert.' }
    : { ton: 'err', text: ergebnis.fehler }
}

onMounted(async () => {
  const geladen = await laden()
  // BS-3b: der Watch übernimmt den Stand zwar schon beim Setzen von `daten`;
  // `standUebernehmen` hier EXPLIZIT, damit die reaktive Kopie sicher steht,
  // bevor die Seite bedienbar ist (Reihenfolge hing sonst am Zeitplan).
  standUebernehmen(datenRoh.value)
  if (geladen) await oeffentlichenStandLaden()
})
</script>

<style scoped>
.wa-bereich { display: grid; grid-template-columns: minmax(0, 1fr); gap: var(--sp-4); min-width: 0; }
.wa-titel { margin: 0; font-size: var(--fs-h4); font-weight: var(--fw-fett); color: var(--text); }
.wa-hilfe { margin: 0; color: var(--muted); font-size: var(--fs-sm); overflow-wrap: anywhere; }
.wa-liste { display: grid; grid-template-columns: minmax(0, 1fr); gap: var(--sp-2); margin: 0; padding: 0; list-style: none; min-width: 0; }
.wa-zeile {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 240px) auto;
  align-items: end;
  gap: var(--sp-3);
  padding: var(--sp-3);
  border-radius: var(--radius);
  background: var(--surface-2);
  min-width: 0;
}
.wa-zeile-haupt { display: flex; flex-wrap: wrap; align-items: baseline; gap: var(--sp-2); min-width: 0; }
.wa-art { color: var(--muted); font-size: var(--fs-sm); }
.wa-name { font-weight: var(--fw-mittel); color: var(--text); overflow-wrap: anywhere; }
.wa-neu { display: grid; grid-template-columns: minmax(0, 1fr); gap: var(--sp-1); min-width: 0; }
.wa-neu-zeile { display: grid; grid-template-columns: minmax(0, 180px) minmax(0, 1fr) auto; gap: var(--sp-2); align-items: center; min-width: 0; }
.wa-aktionen { display: flex; flex-wrap: wrap; align-items: center; gap: var(--sp-3); }
.wa-vorschau { display: grid; grid-template-columns: minmax(0, 1fr); gap: var(--sp-2); padding-top: var(--sp-3); min-width: 0; }
.wa-oeffentlich { display: grid; grid-template-columns: minmax(0, 1fr); gap: var(--sp-2); margin: 0; padding: 0; list-style: none; }
.wa-oeffentlich-zeile {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: var(--sp-2);
  padding: var(--sp-2) var(--sp-3);
  border-radius: var(--radius);
  background: var(--surface-2);
  min-width: 0;
}

@media (max-width: 600px) {
  .wa-zeile { grid-template-columns: minmax(0, 1fr); }
  .wa-neu-zeile { grid-template-columns: minmax(0, 1fr); }
}
</style>
