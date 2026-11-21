<template>
  <div class="cfg-abschnitt" role="region" aria-labelledby="cfg-titel">
    <h2 id="cfg-titel">Nachrichten aufbewahren</h2>
    <p class="cfg-einleitung">
      So lange bleiben Nachrichten im Chat erhalten. Die Frist gilt für die
      ganze Gemeinde; ältere Nachrichten entfernt der Server in der Nacht
      danach von selbst.
    </p>

    <DkSkelett v-if="skelettSichtbar" form="zeilen" :anzahl="4" text="Fristen werden geladen" />
    <DkHint v-if="fehler" variant="err" role="alert">{{ fehler }}</DkHint>
    <DkButton v-if="!geladen && !laedt" variant="secondary" @click="laden">Erneut versuchen</DkButton>

    <template v-if="geladen">
      <DkCard title="Fristen" :sub="'Erlaubt sind ' + stand.minimum + ' bis ' + stand.maximum + ' Monate.'">
        <form class="cfg-formular" novalidate @submit.prevent="abschicken">
          <!-- Die Felder nehmen den Feldsatz der Hülle VOLLSTÄNDIG (`v-slot` →
               `feld.feldProps`): Kennung für das Label (`<label for>`), Wert,
               Eingabeannahme und die aria-Auszeichnung (Beschreibung, invalid)
               kommen aus EINER Quelle — wie in Datensicherung.vue. Ein eigenes
               `v-model`/`id` daneben wäre eine zweite Wahrheit und ließe das
               Label ins Leere zeigen.
               JE FELD EINE ZEILE — nicht per `v-for`: die Einstellungen-Suche
               springt auf `anker="…"` (tests/ux3h-…), und eine gebundene
               Marke wäre für den Wächter nicht lesbar. Die Zuordnung
               Marke → Beschriftung/Hilfe steht in `./fristen.mjs` (FELDER). -->
          <DkField v-slot="feld" label="Gruppengespräche" anker="gruppe"
            :help="standardHinweis(stand, 'gruppe')"
            :error="feldFehler.gruppe || ''" :wert="werte.gruppe"
            @update:wert="eintippen('gruppe', $event)">
            <div class="cfg-feldzeile">
              <input
                v-bind="feld.feldProps"
                class="dk-ui-eingabe cfg-eingabe"
                type="number"
                inputmode="numeric"
                :min="stand.minimum"
                :max="stand.maximum"
                step="1"
              />
              <span class="cfg-einheit" aria-hidden="true">Monate</span>
            </div>
          </DkField>
          <DkField v-slot="feld" label="Direktnachrichten und Runden" anker="direkt"
            :help="standardHinweis(stand, 'direkt')"
            :error="feldFehler.direkt || ''" :wert="werte.direkt"
            @update:wert="eintippen('direkt', $event)">
            <div class="cfg-feldzeile">
              <input
                v-bind="feld.feldProps"
                class="dk-ui-eingabe cfg-eingabe"
                type="number"
                inputmode="numeric"
                :min="stand.minimum"
                :max="stand.maximum"
                step="1"
              />
              <span class="cfg-einheit" aria-hidden="true">Monate</span>
            </div>
          </DkField>
          <!-- CHAT-12c: Höchstgröße je Anhang. Dieselbe Bauart wie die Fristen
               (DkField + Zahlfeld + Standard-Hinweis + Speichern/Fehler) und
               EIGENER Endpunkt (`chat.chat_einstellungen_*`), weil es eine
               andere Einstellung mit eigener Prüfung ist. Der Wert gilt für
               die Vorab-Prüfung in der Chat-Seite
               (`anhang_max_bytes` in `chat.meine_gespraeche`). -->
          <DkField v-slot="feld" label="Höchstgröße je Anhang" anker="anhang"
            :help="groesseHinweis"
            :error="groesseFehler || ''" :wert="groesseWert"
            @update:wert="groesseEintippen($event)">
            <div class="cfg-feldzeile">
              <input
                v-bind="feld.feldProps"
                class="dk-ui-eingabe cfg-eingabe"
                type="number"
                inputmode="numeric"
                :min="groesseStand.minimum"
                :max="groesseStand.maximum"
                step="1"
              />
              <span class="cfg-einheit" aria-hidden="true">MB</span>
            </div>
          </DkField>

          <!-- Klartext beim Verkürzen (Karte Punkt 3): NUR wenn ein Wert
               kleiner ist als der gespeicherte. Die Farbe trägt die Aussage
               nicht allein — der Satz sagt sie. -->
          <DkHint v-if="warnung" variant="warn" role="status" class="cfg-warnung">
            {{ warnung }}
          </DkHint>

          <div class="cfg-aktionen">
            <DkButton
              type="submit"
              variant="primary"
              :loading="speichert"
              :disabled="!kannSpeichern"
              :aria-disabled="kannSpeichern ? undefined : 'true'"
              :title="kannSpeichern ? undefined : 'Keine Änderung zum Speichern'"
            >Speichern</DkButton>
            <DkButton
              variant="secondary"
              type="button"
              :disabled="speichert || !groesseAbweichend"
              :title="groesseAbweichend ? undefined : 'Das Feld steht schon auf dem Standardwert.'"
              @click="groesseAufStandard"
            >Höchstgröße auf Standard</DkButton>
            <DkButton
              variant="secondary"
              type="button"
              :disabled="speichert || !standardAbweichend"
              :title="standardAbweichend ? undefined : 'Die Felder stehen schon auf den Standardwerten.'"
              @click="aufStandard"
            >Auf Standard zurücksetzen</DkButton>
          </div>
          <DkErfolgsmeldung :text="erfolg" />
        </form>
      </DkCard>

      <!-- Feste Fristen: nur lesend, Sätze aus den Feldern der Antwort. -->
      <DkCard v-if="festeSaetze.length" title="Feste Fristen">
        <p class="cfg-hilfe">
          Diese Fristen lassen sich nicht einstellen — sie gelten unabhängig von
          den Werten darüber.
        </p>
        <ul class="cfg-feste">
          <li v-for="s in festeSaetze" :key="s.id" class="cfg-fest">{{ s.text }}</li>
        </ul>
      </DkCard>
    </template>
  </div>
</template>

<script setup>
/**
 * CHAT-8-UI — Einstellungen › „Nachrichten aufbewahren“ (Chat-Konzept 4.2, F8).
 *
 * Zwei Zahlenfelder in Monaten (Gruppengespräche · Direktnachrichten und
 * Runden). Gelesen wird `chat.fristen_lesen`, gespeichert über
 * `chat.fristen_speichern` — nur die Administration darf schreiben; der Server
 * entscheidet, ein 403 bleibt hier ruhig stehen (keine eigene Rollenprüfung).
 *
 * CHAT-12c: DASSELBE Formular trägt zusätzlich die „Höchstgröße je Anhang“ in
 * MB (1–50, Standard 10) — eigene Endpunkte `chat.chat_einstellungen_lesen`
 * (jedes angemeldete Konto) und `chat.chat_einstellungen_speichern` (nur
 * Administration, wie bei den Fristen). Die Regeln stehen in
 * `./anhanggroesse.mjs`. Die Chat-Seite nimmt dieselbe Zahl aus
 * `chat.meine_gespraeche` (`anhang_max_bytes`) für ihre Vorab-Prüfung.
 *
 * Sichtbarkeit regelt der Rahmen: der Abschnitt hängt in
 * `pages/Einstellungen.vue` an `verwaltung: 'admin'` (dieselbe Regel wie
 * Papierkorb und Datenschutz-Texte) — hier steht KEINE zweite Rechteprüfung.
 *
 * Die Regeln (Grenzen, Verkürzen, Sätze der festen Fristen) stehen ohne DOM in
 * `./fristen.mjs`.
 */
import { computed, onMounted, ref } from 'vue'
import { apiCall } from '../../composables/useApi.js'
import { bestaetigen } from '../../composables/useBestaetigen.js'
import DkButton from '../../components/ui/DkButton.vue'
import DkCard from '../../components/ui/DkCard.vue'
import DkErfolgsmeldung from '../../components/ui/DkErfolgsmeldung.vue'
import DkField from '../../components/ui/DkField.vue'
import DkHint from '../../components/ui/DkHint.vue'
import DkSkelett from '../../components/ui/DkSkelett.vue'
import { useLadeSkelett } from '../../composables/useLadeSkelett.js'
import {
  FELDER, eingabePruefen, feldTexte, festeFristen, geaendert, speicherNutzlast,
  standLesen, standardHinweis, standardTexte, verkuerzenFrage, verkuerzt,
} from './fristen.mjs'
import {
  eingabePruefen as groessePruefen, feldText as groesseFeldText,
  geaendert as groesseGeaendert, speicherNutzlast as groesseNutzlast,
  speicherFehlerText as groesseFehlerText, standLesen as groesseStandLesen,
  standardHinweis as groesseStandardHinweis, standardText as groesseStandardText,
} from './anhanggroesse.mjs'

const laedt = ref(true)
// Platzhalter erst nach 300 ms (kein Blitzen, keine Aussage vor der Antwort).
const { skelettSichtbar } = useLadeSkelett(laedt)
const geladen = ref(false)
const speichert = ref(false)
const fehler = ref('')
const erfolg = ref('')
const feldFehler = ref({})
const stand = ref(standLesen(null))
// Die ROHE Antwort des Servers zum Stand — beim Speichern kommt die Antwort nur
// mit den geänderten Feldern zurück; der Rest (Standard, Grenzen, feste
// Fristen) bleibt so erhalten, ohne neu zu laden.
let standwert = {}
const werte = ref(feldTexte(stand.value))

// ── CHAT-12c: Höchstgröße je Anhang ─────────────────────────────────────────
// EIGENE Antwort und EIGENE Endpunkte (`chat.chat_einstellungen_lesen` /
// `…_speichern`) — dieselbe Bauart wie die Fristen, aber eine andere
// Einstellung. Der Wert wird GETRENNT gespeichert, damit ein Fehler bei der
// einen Einstellung nicht die andere blockiert; beide Knöpfe teilen sich das
// Formular, weil der Abschnitt „Nachrichten aufbewahren“ sie zusammen zeigt.
const groesseStand = ref(groesseStandLesen(null))
const groesseWert = ref(groesseFeldText(groesseStand.value))
const groesseFehler = ref('')
let groesseStandwert = {}

const groesseHinweis = computed(() => groesseStandardHinweis(groesseStand.value))

const groesseGeaendertJetzt = computed(() =>
  groesseGeaendert(groesseWert.value, groesseStand.value))

/** Steht das Größenfeld auf dem Standardwert? Dann gibt es nichts zurückzusetzen. */
const groesseAbweichend = computed(() =>
  String(groesseWert.value ?? '') !== String(groesseStandardText(groesseStand.value) ?? ''))

/** „Höchstgröße auf Standard“ füllt nur das Feld — gespeichert wird danach. */
function groesseAufStandard() {
  groesseWert.value = groesseStandardText(groesseStand.value)
  groesseFehler.value = groessePruefen(groesseWert.value, groesseStand.value).fehler
  erfolg.value = ''
}

const festeSaetze = computed(() => festeFristen(stand.value))

/** Nur wenn ein Wert kleiner wird als der gespeicherte (Karte Punkt 3). */
const warnung = computed(() => verkuerzenFrage(werte.value, stand.value))

const kannSpeichern = computed(() =>
  (geaendert(werte.value, stand.value) && Object.keys(feldFehler.value).length === 0)
  // CHAT-12c: auch eine geänderte Anhangsgröße ist etwas zu speichern.
  || (groesseGeaendertJetzt.value && !groesseFehler.value))

/** Stehen die Felder auf den Standardwerten? Dann gibt es nichts zurückzusetzen. */
const standardAbweichend = computed(() => {
  const s = standardTexte(stand.value)
  return FELDER.some((f) => String(werte.value[f.id] ?? '') !== String(s[f.id] ?? ''))
})

async function laden() {
  laedt.value = true
  fehler.value = ''
  try {
    const antwort = await apiCall('diakronos_app.api.chat.fristen_lesen', {})
    standwert = antwort || {}
    stand.value = standLesen(standwert)
    werte.value = feldTexte(stand.value)
    feldFehler.value = {}
    geladen.value = true
  } catch (err) {
    fehler.value = err?.message || 'Die Aufbewahrungsfristen konnten nicht geladen werden.'
  } finally {
    laedt.value = false
  }
  // CHAT-12c: die Anhangsgröße hat einen EIGENEN Lese-Endpunkt (jedes
  // angemeldete Konto darf sie lesen). Ein Fehler dort lässt die Fristen
  // stehen — das Feld sagt dann, dass es nichts weiß.
  try {
    const antwort = await apiCall('diakronos_app.api.chat.chat_einstellungen_lesen', {})
    groesseStandwert = antwort || {}
    groesseStand.value = groesseStandLesen(groesseStandwert)
    groesseWert.value = groesseFeldText(groesseStand.value)
    groesseFehler.value = ''
  } catch {
    groesseFehler.value = 'Die Anhangsgröße konnte nicht geladen werden.'
  }
}

/**
 * Tippen: Wert merken, Fehler dieses Feldes neu prüfen — nicht erst beim
 * Speichern (das Feld sagt sofort, was es erwartet).
 */
function eintippen(id, wert) {
  werte.value = { ...werte.value, [id]: wert }
  const ergebnis = eingabePruefen(werte.value, stand.value)
  feldFehler.value = ergebnis.fehler
  erfolg.value = ''
}

/** „Auf Standard zurücksetzen“ füllt nur die Felder — gespeichert wird danach. */
function aufStandard() {
  werte.value = { ...standardTexte(stand.value) }
  feldFehler.value = eingabePruefen(werte.value, stand.value).fehler
  erfolg.value = ''
}

/** CHAT-12c: Tippen im Größenfeld — sofort prüfen, nicht erst beim Speichern. */
function groesseEintippen(wert) {
  groesseWert.value = wert
  groesseFehler.value = groessePruefen(wert, groesseStand.value).fehler
  erfolg.value = ''
}

/**
 * CHAT-12c: die Anhangsgröße speichern — eigener Endpunkt, eigener Fehler.
 *
 * Nur die ADMINISTRATION darf schreiben (der Server prüft `rechte.ist_admin`);
 * hier steht KEINE Rollenprüfung — ein 403 wird ruhig erklärt.
 */
async function groesseSpeichern() {
  if (speichert.value) return
  const ergebnis = groessePruefen(groesseWert.value, groesseStand.value)
  groesseFehler.value = ergebnis.fehler
  if (!ergebnis.ok) return
  if (!groesseGeaendert(ergebnis.wert, groesseStand.value)) return

  speichert.value = true
  fehler.value = ''
  erfolg.value = ''
  try {
    const antwort = await apiCall(
      'diakronos_app.api.chat.chat_einstellungen_speichern',
      groesseNutzlast(ergebnis.wert),
    )
    erfolg.value = 'Gespeichert. Die neue Höchstgröße gilt für alle Anhänge im Chat.'
    groesseStand.value = groesseStandLesen({ ...groesseStandwert, ...antwort })
    groesseStandwert = { ...groesseStandwert, ...antwort }
    groesseWert.value = groesseFeldText(groesseStand.value)
    groesseFehler.value = ''
  } catch (err) {
    // Die Server-Meldung (422: „… muss zwischen 1 und 50 MB liegen.“) steht
    // im Feld; ein 403 erklärt der Satz für die Administration.
    groesseFehler.value = groesseFehlerText(err, {
      ersatz: 'Die Anhangsgröße konnte nicht gespeichert werden.',
    })
  } finally {
    speichert.value = false
  }
}

async function abschicken() {
  if (speichert.value) return
  // CHAT-12c: steht im Größenfeld etwas zu Speicherndes, geht es als ERSTES
  // hinaus (eigener Endpunkt) — ein Tippfehler dort hält die Fristen nicht auf,
  // und ein Fehler dort lässt die Fristen unberührt.
  if (groesseGeaendertJetzt.value && !groesseFehler.value) {
    await groesseSpeichern()
    if (groesseFehler.value) return
  }

  const ergebnis = eingabePruefen(werte.value, stand.value)
  feldFehler.value = ergebnis.fehler
  if (!ergebnis.ok) return
  if (!geaendert(ergebnis.werte, stand.value)) {
    // Nichts an den Fristen zu ändern — die Anhangsgröße ist gespeichert.
    if (!groesseGeaendertJetzt.value) return
    return
  }

  // Verkürzen ist endgültig: erst fragen, dann speichern. Die Fragetexte sind
  // derselbe Klartext-Satz, der schon über den Knöpfen steht (Karte Punkt 3) —
  // er nennt beide alten und neuen Werte und was der nächste Lauf löscht.
  if (verkuerzt(ergebnis.werte, stand.value).length) {
    const text = verkuerzenFrage(ergebnis.werte, stand.value)
    if (!await bestaetigen({
      titel: 'Fristen verkürzen?',
      text,
      aktion: 'Fristen speichern',
      gefahr: true,
    })) return
  }

  speichert.value = true
  fehler.value = ''
  erfolg.value = ''
  try {
    const antwort = await apiCall('diakronos_app.api.chat.fristen_speichern', speicherNutzlast(ergebnis.werte))
    erfolg.value = 'Gespeichert. Die neuen Fristen gelten ab dem nächsten nächtlichen Lauf.'
    // Den Serverstand aus der ANTWORT übernehmen, nicht neu laden: ein zweiter
    // Ladevorgang ließe das Platzhalter-Skelett über das Formular blitzen, und
    // die Antwort trägt die gespeicherten Werte bereits.
    stand.value = standLesen({ ...standwert, ...antwort })
    werte.value = feldTexte(stand.value)
    feldFehler.value = {}
  } catch (err) {
    // Ein 403 ist keine Panne: die Administration fehlt dieser Sitzung.
    fehler.value = err?.status === 403
      ? 'Nur die Administration darf die Aufbewahrungsfristen ändern.'
      : (err?.message || 'Die Fristen konnten nicht gespeichert werden.')
  } finally {
    speichert.value = false
  }
}

onMounted(laden)
</script>

<style scoped>
.cfg-abschnitt { display: grid; gap: var(--gap); }
.cfg-einleitung,
.cfg-hilfe { color: var(--text-muted); }
.cfg-formular { display: grid; gap: var(--gap); }
.cfg-feldzeile { display: flex; align-items: center; gap: var(--sp-2); }
/* Klickfläche des Feldes ≥ 44 px am groben Zeiger (Prinzip K4) — im
   Formular steht die Höhe des Feldes, nicht nur der Schrift. */
.cfg-eingabe {
  min-height: var(--control-h-lg);
  /* Kurze Zahlenfelder: die Breite wächst nicht mit der Spalte — ein Feld für
     „24“ braucht keinen halben Bildschirm. */
  max-width: calc(var(--sp-7) * 2);
  text-align: right;
}
.cfg-einheit { color: var(--text-muted); font-size: var(--fs-sm); }
.cfg-aktionen { display: flex; flex-wrap: wrap; gap: var(--sp-2); align-items: center; }
.cfg-feste {
  display: grid;
  gap: var(--sp-2);
  margin: 0;
  padding-left: var(--sp-4);
  color: var(--text);
}
.cfg-fest { font-size: var(--fs-sm); }

/* Am Handy stehen die Felder untereinander, die Einheit direkt am Feld —
   die Knöpfe fallen auf volle Breite (Handy-Regel der übrigen Abschnitte). */
@media (max-width: 720px) {
  .cfg-eingabe { max-width: none; width: 100%; }
  .cfg-aktionen :deep(.dk-ui-btn) { width: 100%; }
}
</style>
