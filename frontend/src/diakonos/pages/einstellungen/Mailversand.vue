<template>
  <div class="mv-abschnitt">
    <h2>Mailversand</h2>
    <p>
      Diakronos verschickt E-Mails an Mitglieder — zum Beispiel die Meldung
      „deine Daten werden gelöscht“, wenn du einen Löschantrag freigibst. Dafür
      braucht die App ein Postfach zum Versenden. Richte es hier einmal ein;
      danach musst du nichts mehr tun.
    </p>

    <DkHint v-if="laedt" role="status">Einstellungen werden geladen …</DkHint>
    <DkHint v-if="fehler" variant="err" role="alert">{{ fehler }}</DkHint>
    <DkHint v-if="erfolg" variant="ok" role="status">{{ erfolg }}</DkHint>
    <DkButton v-if="!geladen && !laedt" variant="secondary" @click="laden">Erneut laden</DkButton>

    <template v-if="geladen">
      <DkHint v-if="!eingerichtet" variant="warn" role="status">
        Der Mailversand ist noch nicht eingerichtet. Solange das so ist, kannst du
        keinen Löschantrag freigeben — die Meldung an die Person muss vorher
        rausgehen.
      </DkHint>
      <DkHint v-else variant="ok" role="status">
        Der Mailversand ist eingerichtet. Meldungen gehen über
        <strong>{{ form.absender }}</strong> raus.
      </DkHint>

      <form @submit.prevent="speichern">
        <fieldset class="mv-felder">
          <DkCard title="Server">
            <DkField label="Name des Mailservers" required
              help="Zum Beispiel mail.example.org — ohne http:// und ohne Schrägstrich.">
              <input v-model.trim="form.host" class="dk-ui-eingabe" type="text"
                autocomplete="off" inputmode="url" required />
            </DkField>

            <DkField label="Verschlüsselung" required :help="hilfeSicherheit">
              <select v-model="form.sicherheit" class="dk-ui-eingabe"
                @change="sicherheitGeaendert">
                <option v-for="a in SICHERHEIT_ARTEN" :key="a.wert" :value="a.wert">
                  {{ a.label }}
                </option>
              </select>
            </DkField>

            <DkHint v-if="form.sicherheit === 'keine'" variant="err" role="alert">
              Ohne Verschlüsselung gehen E-Mails mit Personendaten im Klartext
              über das Netz. Nimm das nur, wenn der Mailserver im selben
              abgeschotteten Netz steht — und dann ohne Anmeldung.
            </DkHint>

            <DkField label="Port" required
              help="STARTTLS meist 587, SSL/TLS meist 465. Manche Anbieter verlangen etwas anderes.">
              <input v-model.number="form.port" class="dk-ui-eingabe" type="number"
                min="1" max="65535" step="1" inputmode="numeric" required />
            </DkField>

            <DkField label="Zeitlimit in Sekunden"
              help="So lange wartet Diakronos auf den Mailserver, bevor der Versand abbricht.">
              <input v-model.number="form.timeout" class="dk-ui-eingabe" type="number"
                min="3" max="120" step="1" inputmode="numeric" />
            </DkField>
          </DkCard>

          <DkCard title="Anmeldung">
            <DkField label="Benutzername"
              help="Meist die vollständige Adresse des Postfachs. Leer lassen, wenn der Server keine Anmeldung verlangt.">
              <input v-model.trim="form.benutzername" class="dk-ui-eingabe" type="text"
                autocomplete="username" />
            </DkField>

            <DkField label="Passwort" :help="hilfePasswort">
              <input v-model="passwort" class="dk-ui-eingabe" type="password"
                autocomplete="new-password" :placeholder="platzhalterPasswort" />
            </DkField>
            <p v-if="passwortGesetzt" class="mv-hilfe">
              Ein Passwort ist hinterlegt. Leer lassen, um es zu behalten.
            </p>
            <p v-else class="mv-hilfe">Es ist noch kein Passwort hinterlegt.</p>
            <!-- MAIL-1b (N4): ohne diesen Knopf war der Wechsel auf „keine
                 Verschlüsselung“ bzw. einen Server ohne Anmeldung nicht
                 bedienbar — der Server verlangt dann das Entfernen. -->
            <DkButton v-if="passwortGesetzt" variant="secondary" type="button"
              @click="passwortEntfernenOeffnen">
              Gespeichertes Passwort entfernen
            </DkButton>
          </DkCard>

          <DkCard title="Absender">
            <DkField label="Absenderadresse" required
              help="Diese Adresse sehen die Empfänger. Meist dieselbe wie der Benutzername.">
              <input v-model.trim="form.absender" class="dk-ui-eingabe" type="email"
                autocomplete="off" required />
            </DkField>
            <DkField label="Absendername"
              help="Zum Beispiel der Name deiner Gemeinde. Ohne Angabe steht dort „Diakronos“.">
              <input v-model.trim="form.absenderName" class="dk-ui-eingabe" type="text" />
            </DkField>
          </DkCard>

          <div class="mv-aktionen">
            <DkButton type="submit" variant="primary" :loading="speichert">
              Speichern
            </DkButton>
            <DkButton variant="secondary" :loading="testet" @click="testmail">
              Testmail senden
            </DkButton>
          </div>
        </fieldset>
      </form>

      <DkCard title="Testmail">
        <p class="mv-hilfe">
          Die Testmail geht an die Adresse deines eigenen Kontos
          <template v-if="meineAdresse">(<strong>{{ meineAdresse }}</strong>)</template>.
          Du kannst sie schicken, bevor du speicherst — dann siehst du sofort, ob
          Server und Zugangsdaten stimmen.
        </p>
        <DkHint v-if="testFehler" variant="err" role="alert">{{ testFehler }}</DkHint>
        <DkHint v-if="testErfolg" variant="ok" role="status">{{ testErfolg }}</DkHint>
        <p v-if="geaendert" class="mv-hilfe">Zuletzt geändert: {{ geaendertText }}</p>
      </DkCard>
    </template>

    <!-- MAIL-1b (N4): eigener Dialog statt confirm() — er nennt die Folge und
         laesst sich mit „Abbrechen“ verlassen. -->
    <DkDialog :model-value="passwortEntfernen" title="Gespeichertes Passwort entfernen"
      :close-on-overlay="false" @update:model-value="dialogSchliessen">
      <DkHint variant="warn" role="status">
        Danach ist am Mailserver <strong>keine Anmeldung</strong> mehr möglich —
        Diakronos wird also nicht mehr angemeldet. Das Passwort lässt sich nicht
        wiederherstellen; du musst es neu eintippen.
      </DkHint>
      <p class="mv-hilfe">
        Sinnvoll, wenn der Mailserver ohne Anmeldung arbeitet oder du auf „keine
        Verschlüsselung“ umstellen willst. Speichere danach die Einstellungen.
      </p>
      <template #footer>
        <DkButton variant="ghost" :disabled="speichert" @click="dialogSchliessen(false)">
          Abbrechen
        </DkButton>
        <DkButton variant="danger" :loading="speichert" @click="passwortEntfernenBestaetigen">
          Passwort entfernen
        </DkButton>
      </template>
    </DkDialog>
  </div>
</template>

<script setup>
/**
 * MAIL-1 — Einstellungen-Abschnitt „Mailversand“ (nur System Manager).
 *
 * Server, Port, Verschlüsselung, Anmeldung und Absender des Postfachs, mit dem
 * Diakronos Mails verschickt. Das Passwort kommt nie zurück: das Feld ist
 * immer leer, und leer lassen heißt „behalten“. „Testmail senden“ probt die
 * eingegebenen Werte, bevor gespeichert wird.
 *
 * Auch mit den FELDERN von Formular und Test kommt kein Vertraulichkeitsproblem
 * nach außen: der Server liefert ausschließlich „Passwort gesetzt: ja/nein“.
 */
import { ref, computed, onMounted } from 'vue'
import { useMailversand, SICHERHEIT_ARTEN } from '../../composables/useMailversand.js'
import DkButton from '../../components/ui/DkButton.vue'
import DkCard from '../../components/ui/DkCard.vue'
import DkHint from '../../components/ui/DkHint.vue'
import DkField from '../../components/ui/DkField.vue'
import DkDialog from '../../components/ui/DkDialog.vue'

defineProps({ embedded: Boolean })

const {
  laedt, speichert, testet, geladen, fehler, erfolg, testFehler, testErfolg,
  form, passwort, passwortGesetzt, eingerichtet, geaendert, meineAdresse,
  passwortEntfernen,
  laden, speichern, testmail,
  passwortEntfernenOeffnen, passwortEntfernenAbbrechen,
  passwortEntfernenBestaetigen,
} = useMailversand()

/** Dialog schliessen (Abbrechen, Esc, Klick daneben) — ohne zu loeschen. */
function dialogSchliessen(offen) {
  if (offen === false) passwortEntfernenAbbrechen()
}

const hilfePasswort = computed(() =>
  passwortGesetzt.value
    ? 'Ein Passwort ist hinterlegt. Lass das Feld leer, um es zu behalten.'
    : 'Meist braucht der Server ein Passwort (bei vielen Anbietern ein eigenes „App-Passwort“).')

const platzhalterPasswort = computed(() =>
  passwortGesetzt.value ? '••••••••  (gespeichert)' : 'Passwort des Postfachs')

const hilfeSicherheit = computed(() =>
  (SICHERHEIT_ARTEN.find(a => a.wert === form.value.sicherheit) || SICHERHEIT_ARTEN[0]).help)

/**
 * Beim Wechsel der Verschlüsselung den üblichen Port vorschlagen — aber nur,
 * wenn dort noch der Standard der VORIGEN Art steht. Eine bewusst gesetzte
 * Zahl darf nicht überschrieben werden.
 */
function sicherheitGeaendert() {
  const neu = SICHERHEIT_ARTEN.find(a => a.wert === form.value.sicherheit)
  const alt = SICHERHEIT_ARTEN.map(a => a.port)
  if (!neu) return
  if (alt.includes(Number(form.value.port))) form.value.port = neu.port
}

const geaendertText = computed(() => {
  const treffer = String(geaendert.value || '').match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/)
  if (!treffer) return ''
  const [, jahr, monat, tag, stunde, minute] = treffer
  return `${tag}.${monat}.${jahr}, ${stunde}:${minute} Uhr`
})

onMounted(laden)
</script>

<style scoped>
.mv-abschnitt, .mv-felder { display: grid; gap: var(--sp-4); min-width: 0; }
.mv-abschnitt h2, .mv-abschnitt p { margin: 0; }
.mv-felder { padding: 0; border: 0; margin: 0; }
.mv-hilfe { display: block; color: var(--muted); font-size: var(--fs-sm); }
.mv-aktionen { display: flex; flex-wrap: wrap; gap: var(--sp-3); }
</style>
