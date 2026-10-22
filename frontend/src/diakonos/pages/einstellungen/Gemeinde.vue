<template>
  <div class="gem-abschnitt">
    <h2>Gemeinde</h2>
    <p>Name, Kontakt und die Adresse, unter der die Gemeinde im Netz erreichbar ist.
      Diese Angaben erscheinen in der App und in geteilten Links.</p>

    <DkHint v-if="laedt" role="status">Gemeinde-Einstellungen werden geladen …</DkHint>
    <DkHint v-if="fehler" variant="err" role="alert">{{ fehler }}</DkHint>
    <DkButton v-if="!geladen && !laedt" variant="secondary" @click="laden">Erneut laden</DkButton>

    <form ref="formular" @submit.prevent="speichernMitFokus">
      <fieldset :disabled="!bedienbar" class="gem-felder">
        <DkCard title="Name und Kontakt">
          <DkField label="Name der Gemeinde" required :error="feldFehler.name" v-slot="feld">
            <input v-bind="feld" v-model="gemeindename" class="dk-ui-eingabe" maxlength="140"
              placeholder="z. B. Versöhnungskirche Heilbronn" />
          </DkField>
          <DkField label="Kontakt-E-Mail" help="An diese Adresse wenden sich Personen mit Fragen."
            :error="feldFehler.email" v-slot="feld">
            <input v-bind="feld" v-model="kontaktEmail" class="dk-ui-eingabe" type="email"
              maxlength="255" placeholder="buero@gemeinde.example" />
          </DkField>
        </DkCard>

        <DkCard title="Öffentliche Adresse">
          <p class="gem-hilfe">Die Adresse, unter der die Gemeinde von außen erreichbar ist.
            Geteilte Links (Registrierung, Passwort) werden damit vollständig gebaut.
            Bleibt sie leer, nimmt die App die Adresse aus dem Browser.</p>
          <DkField label="Adresse" placeholder="https://gemeinde.example.org"
            :error="feldFehler.adresse" v-slot="feld">
            <input v-bind="feld" v-model="oeffentlicheAdresse" class="dk-ui-eingabe"
              inputmode="url" maxlength="255" />
          </DkField>
        </DkCard>

        <DkCard title="Willkommenstext">
          <p class="gem-hilfe">Erscheint auf der Registrierungs- und Gast-Anmeldeseite
            über dem Formular – ein kurzer Satz genügt.</p>
          <DkField label="Text" v-slot="feld">
            <textarea v-bind="feld" v-model="willkommenstext" class="dk-ui-eingabe" rows="3"
              maxlength="4000"></textarea>
          </DkField>
        </DkCard>

        <DkButton type="submit" variant="primary" :loading="speichert">Speichern</DkButton>
      </fieldset>
    </form>
    <p v-if="erfolg" role="status">{{ erfolg }}</p>

    <DkCard title="Module">
      <p class="gem-hilfe">Zeigt an, welche Bereiche in der Navigation erscheinen.
        Die Anzeigenamen stammen aus der Einrichtung.</p>
      <ul class="gem-module">
        <li v-for="m in module" :key="m.schluessel" class="gem-modul">
          <label class="gem-schalter">
            <input type="checkbox" :checked="m.sichtbar" :disabled="!bedienbar || modulSpeichert === m.schluessel"
              @change="modulSchalten(m.schluessel, $event.target.checked)" />
            <span><strong>{{ m.anzeige }}</strong><span class="gem-hilfe">{{ m.schluessel }}</span></span>
          </label>
        </li>
      </ul>
    </DkCard>
  </div>
</template>

<script setup>
import { ref, nextTick, onMounted } from 'vue'
import { useGemeinde } from '../../composables/useGemeinde.js'
import DkButton from '../../components/ui/DkButton.vue'
import DkCard from '../../components/ui/DkCard.vue'
import DkHint from '../../components/ui/DkHint.vue'
import DkField from '../../components/ui/DkField.vue'

const { laedt, speichert, geladen, fehler, erfolg, gemeindename, kontaktEmail,
  oeffentlicheAdresse, willkommenstext, linkLaufzeitTage, linkMaxAnmeldungen,
  module, modulSpeichert, bedienbar, laden, speichern, modulSchalten } = useGemeinde()

const formular = ref(null)
const feldFehler = ref({})

async function speichernMitFokus() {
  feldFehler.value = {}
  if (!gemeindename.value.trim()) feldFehler.value.name = 'Bitte einen Gemeindenamen eintragen.'
  if (kontaktEmail.value.trim() && !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(kontaktEmail.value.trim()))
    feldFehler.value.email = 'Das sieht nicht nach einer E-Mail-Adresse aus.'
  if (oeffentlicheAdresse.value.trim()
      && !/^https?:\/\/.+/.test(oeffentlicheAdresse.value.trim()))
    feldFehler.value.adresse = 'Bitte mit http:// oder https:// beginnen.'
  if (Object.keys(feldFehler.value).length) {
    await nextTick()
    formular.value?.querySelector('[aria-invalid="true"]')?.focus()
    return
  }
  // Link-Vorgaben werden auf der Karte „Registrierung“ gepflegt und hier
  // weggelassen — der Server laesst sie dann unveraendert.
  await speichern({ mitLinkVorgaben: false })
}

onMounted(laden)
</script>

<style scoped>
.gem-abschnitt, .gem-felder { display: grid; gap: var(--sp-4); min-width: 0; }
.gem-abschnitt h2, .gem-abschnitt p { margin: 0; }
.gem-felder { padding: 0; border: 0; margin: 0; }
.gem-felder:disabled { opacity: .65; }
.gem-hilfe { display: block; color: var(--muted); font-size: var(--fs-sm); }
.gem-module { list-style: none; padding: 0; margin: var(--sp-3) 0 0; display: grid; gap: var(--sp-2); }
.gem-schalter { display: flex; align-items: flex-start; gap: var(--sp-2); }
.gem-schalter input { margin-top: var(--sp-1); flex-shrink: 0; }
</style>
