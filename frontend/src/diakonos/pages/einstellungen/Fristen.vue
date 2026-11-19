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

const festeSaetze = computed(() => festeFristen(stand.value))

/** Nur wenn ein Wert kleiner wird als der gespeicherte (Karte Punkt 3). */
const warnung = computed(() => verkuerzenFrage(werte.value, stand.value))

const kannSpeichern = computed(() =>
  geaendert(werte.value, stand.value) && Object.keys(feldFehler.value).length === 0)

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

async function abschicken() {
  if (speichert.value) return
  const ergebnis = eingabePruefen(werte.value, stand.value)
  feldFehler.value = ergebnis.fehler
  if (!ergebnis.ok) return
  if (!geaendert(ergebnis.werte, stand.value)) return

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
