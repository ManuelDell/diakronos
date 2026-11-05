<template>
  <!-- ON-3 (W2, Schritt 3 „Mailversand“, Entwurf 06): Infobox oben, dann
       Server/Port, Benutzer/Passwort, Verschlüsselung/Absendername,
       Absenderadresse und „Testmail senden“ mit dem Ergebnis. Gespeichert und
       getestet wird über die VORHANDENEN Endpunkte (`useMailversand`,
       MAIL-1) — kein zweiter Schreibweg. -->
  <section class="schritt">
    <h1 class="schritt-titel">Mailversand</h1>
    <p class="schritt-unterzeile">Zugangsdaten des Postfachs, über das Diakronos schreibt.</p>

    <DkHint variant="warn" role="status">
      Ohne Mailversand können keine Einladungen und Passwort-Links verschickt werden.
    </DkHint>

    <p v-if="laedt && !geladen" class="schritt-hinweis" role="status">Einstellungen werden geladen …</p>

    <template v-if="geladen">
      <div class="schritt-raster">
        <DkField label="SMTP-Server" required :error="fehlerFeld('host')">
          <template #default="{ id, ariaDescribedby, ariaInvalid }">
            <input
              :id="id"
              v-model.trim="form.host"
              class="dk-ui-eingabe dk-ui-eingabe--feld"
              type="text"
              autocomplete="off"
              inputmode="url"
              placeholder="z. B. mail.gemeinde.example"
              :aria-describedby="ariaDescribedby"
              :aria-invalid="ariaInvalid || undefined"
            />
          </template>
        </DkField>
        <DkField label="Port" required help="STARTTLS meist 587, SSL/TLS meist 465.">
          <template #default="{ id, ariaDescribedby }">
            <input
              :id="id"
              v-model.number="form.port"
              class="dk-ui-eingabe dk-ui-eingabe--feld"
              type="number"
              min="1"
              max="65535"
              step="1"
              inputmode="numeric"
              :aria-describedby="ariaDescribedby"
            />
          </template>
        </DkField>
      </div>

      <div class="schritt-raster">
        <DkField label="Benutzer" help="Meist die vollständige Adresse des Postfachs.">
          <template #default="{ id, ariaDescribedby }">
            <input
              :id="id"
              v-model.trim="form.benutzername"
              class="dk-ui-eingabe dk-ui-eingabe--feld"
              type="text"
              autocomplete="username"
              placeholder="z. B. versand@gemeinde.example"
              :aria-describedby="ariaDescribedby"
            />
          </template>
        </DkField>
        <DkField label="Passwort" :help="hilfePasswort">
          <template #default="{ id, ariaDescribedby }">
            <input
              :id="id"
              v-model="passwort"
              class="dk-ui-eingabe dk-ui-eingabe--feld"
              type="password"
              autocomplete="new-password"
              :placeholder="platzhalterPasswort"
              :aria-describedby="ariaDescribedby"
            />
          </template>
        </DkField>
      </div>

      <div class="schritt-raster">
        <DkField label="Verschlüsselung" required :help="hilfeSicherheit">
          <template #default="{ id, ariaDescribedby }">
            <select
              :id="id"
              v-model="form.sicherheit"
              class="dk-ui-eingabe dk-ui-eingabe--feld"
              :aria-describedby="ariaDescribedby"
              @change="sicherheitGeaendert"
            >
              <option v-for="a in SICHERHEIT_ARTEN" :key="a.wert" :value="a.wert">{{ a.label }}</option>
            </select>
          </template>
        </DkField>
        <DkField label="Absendername" help="Zum Beispiel der Name Ihrer Gemeinde.">
          <template #default="{ id, ariaDescribedby }">
            <input
              :id="id"
              v-model.trim="form.absenderName"
              class="dk-ui-eingabe dk-ui-eingabe--feld"
              type="text"
              placeholder="z. B. Ev. Gemeinde Musterstadt"
              :aria-describedby="ariaDescribedby"
            />
          </template>
        </DkField>
      </div>

      <DkField label="Absenderadresse" required help="Diese Adresse sehen die Empfänger.">
        <template #default="{ id, ariaDescribedby, ariaInvalid }">
          <input
            :id="id"
            v-model.trim="form.absender"
            class="dk-ui-eingabe dk-ui-eingabe--feld"
            type="email"
            autocomplete="off"
            placeholder="z. B. noreply@gemeinde.example"
            :aria-describedby="ariaDescribedby"
            :aria-invalid="ariaInvalid || undefined"
          />
        </template>
      </DkField>

      <div class="test-zeile">
        <DkButton variant="secondary" :loading="testet" @click="testen">
          <template #icon><AssistentSymbol name="senden" :size="'var(--icon-sm)'" /></template>
          Testmail senden
        </DkButton>
        <div class="test-ergebnis" aria-live="polite">
          <p v-if="testErfolg" class="test-ok">
            <AssistentSymbol name="kreis-haken" :size="'var(--assistent-haken-gross)'" />
            {{ testErfolg }}
          </p>
          <p v-if="testFehler" class="test-fehler" role="alert">{{ testFehler }}</p>
          <!-- Der Entwurf zeigt zusätzlich die Serverantwort. Sie wird NICHT
               ausgedacht: ohne echte Antwort steht hier nur die Sende-Zeile. -->
          <p v-if="testErfolg && testServerAntwort" class="test-antwort">{{ testServerAntwort }}</p>
        </div>
      </div>
      <p v-if="!testErfolg && !testFehler" class="schritt-hinweis">
        Die Testmail geht an Ihre eigene Adresse<template v-if="meineAdresse"> ({{ meineAdresse }})</template>.
      </p>
    </template>

    <p v-if="ladeFehler" class="schritt-fehler" role="alert">{{ ladeFehler }}</p>
  </section>
</template>

<script setup>
/**
 * Schritt „Mailversand“ (ON-3/W2, Entwurf 06).
 *
 * Verwendet `composables/useMailversand.js` — dieselben Endpunkte, Prüfungen
 * und Meldungen wie der Einstellungs-Abschnitt (MAIL-1). Ein zweiter
 * Schreibweg für SMTP wäre eine zweite Wahrheit über das Postfach.
 *
 * „Weiter“ in der Fußleiste ruft `speichern` (siehe Seite) und schreibt nur bei
 * Erfolg den Schrittstand. „Überspringen“ lässt alles unberührt.
 */
import { computed, onMounted } from 'vue'
import { useMailversand, SICHERHEIT_ARTEN } from '../../composables/useMailversand.js'
import DkField from '../ui/DkField.vue'
import DkButton from '../ui/DkButton.vue'
import DkHint from '../ui/DkHint.vue'
import AssistentSymbol from './AssistentSymbol.vue'

const {
  laedt, testet, geladen, fehler, testFehler, testErfolg,
  form, passwort, passwortGesetzt, meineAdresse, speichern, testmail, laden,
} = useMailversand()

// Der Testmail-Erfolgstext von `useMailversand` nennt die Zieladresse; eine
// „Antwort des Servers“ gibt die API nicht zurück — deshalb bleibt dieses Feld
// leer, statt einen SMTP-Code zu erfinden.
const testServerAntwort = ''

const hilfePasswort = computed(() => (passwortGesetzt.value
  ? 'Ein Passwort ist hinterlegt. Leer lassen, um es zu behalten.'
  : 'Noch kein Passwort hinterlegt.'))
const platzhalterPasswort = computed(() => (passwortGesetzt.value ? '••••••••' : 'Passwort'))
const hilfeSicherheit = computed(() => {
  const art = SICHERHEIT_ARTEN.find((a) => a.wert === form.value.sicherheit)
  return art ? art.help : ''
})
const ladeFehler = computed(() => (geladen.value ? '' : fehler.value))

/** Feldfehler: `useMailversand` meldet einen Satz, kein Feld — hier nur `host`. */
function fehlerFeld(feld) {
  const text = String(fehler.value || '')
  if (feld === 'host' && /Mailserver/i.test(text)) return text
  return ''
}

function sicherheitGeaendert() {
  const art = SICHERHEIT_ARTEN.find((a) => a.wert === form.value.sicherheit)
  if (art) form.value.port = art.port
}

/** Testmail: erst die eingegebenen Werte prüfen, dann senden. */
async function testen() {
  await testmail()
}

onMounted(() => { laden() })

// Die Seite (Fußleiste) ruft dies über eine Vorlagen-Referenz auf.
defineExpose({ speichern })
</script>

<style scoped>
.schritt { display: flex; flex-direction: column; gap: var(--sp-4); }
.schritt-titel { margin: 0; font-size: var(--fs-h1); font-weight: var(--fw-h); color: var(--text); line-height: 1.25; }
.schritt-unterzeile {
  margin: 0 0 var(--sp-2);
  font-size: var(--fs-fliess);
  color: var(--muted);
  line-height: 1.5;
  max-width: 640px;
}
.schritt-raster { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: var(--sp-3); }
.schritt-hinweis { margin: 0; font-size: var(--fs-sm); color: var(--muted); }
.schritt-fehler { margin: 0; font-size: var(--fs-sm); font-weight: 500; color: var(--err); }
.test-zeile {
  display: flex;
  align-items: center;
  gap: var(--sp-4);
  flex-wrap: wrap;
  margin-top: var(--sp-2);
}
.test-ergebnis { min-height: var(--control-h); display: flex; flex-direction: column; justify-content: center; }
.test-ok {
  display: inline-flex;
  align-items: center;
  gap: var(--sp-2);
  margin: 0;
  font-size: var(--fs);
  font-weight: 600;
  color: var(--ok);
}
.test-fehler { margin: 0; font-size: var(--fs); font-weight: 600; color: var(--err); }
.test-antwort { margin: 0; font-size: var(--fs-sm); color: var(--subtle); }

@media (max-width: 700px) {
  .schritt-raster { grid-template-columns: minmax(0, 1fr); }
  .schritt-unterzeile { font-size: var(--fs); }
}
</style>
