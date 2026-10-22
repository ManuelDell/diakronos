<template>
  <div class="an-abschnitt">
    <h2>Anmeldung (Login)</h2>
    <p>Hier legst du fest, wer über Authentik Zugang zur Gemeinde bekommt.</p>

    <DkHint v-if="laedt" role="status">Anmeldeeinstellungen werden geladen …</DkHint>
    <DkHint v-else-if="geladen" :variant="oidcAktiv ? 'ok' : 'warn'" role="status">
      <strong>{{ oidcAktiv ? 'Authentik: eingerichtet' : 'Authentik: nicht eingerichtet' }}</strong>
      <p v-if="!oidcAktiv">Die Anmeldung erfolgt mit lokalem Passwort. Die Einstellungen darunter wirken erst,
        wenn Authentik eingerichtet ist, und sind deshalb gesperrt. Die Einrichtung übernimmt die Person,
        die den Server betreut (Betriebsanleitung, Abschnitt „Anmeldung über Authentik“).</p>
      <p v-else>Authentik ist am Server aktiviert. Dieser Status ist kein Verbindungstest zum Anbieter.</p>
    </DkHint>
    <DkHint v-if="fehler" variant="err" role="alert">{{ fehler }}</DkHint>
    <DkButton v-if="!geladen && !laedt" variant="secondary" @click="laden">Erneut laden</DkButton>

    <form ref="formular" @submit.prevent="speichernMitFokus">
      <fieldset :disabled="!bedienbar" class="an-felder">
        <DkCard title="Unbekannte Personen">
          <p>Was passiert, wenn eine Person noch kein Konto in Diakronos hat?</p>
          <div class="an-optionen">
            <label v-for="opt in modiOptionen" :key="opt.wert" class="an-option">
              <input v-model="modus" type="radio" name="unbekannte-personen" :value="opt.wert" />
              <span><strong>{{ opt.titel }}</strong><span class="an-hilfe">{{ opt.hinweis }}</span></span>
            </label>
          </div>
        </DkCard>

        <DkCard title="Authentik-Gruppen und Rollen">
          <p>Links steht der genaue Gruppenname in Authentik, nicht eine Gruppe dieser Gemeinde.
            Rechts wählst du die Rechte in Diakronos. Beim Anmelden werden Rollen ergänzt, nicht entzogen.
            Auch bestehende Konten erhalten passende Gruppenrollen.</p>
          <DkHint v-if="modus !== 'anlegen_mit_rollen'" variant="info">
            Die Zuordnungen gelten auch für bekannte Konten. Der Modus oben regelt nur neue Konten.
          </DkHint>
          <div v-for="(z, i) in zuordnungen" :key="i" class="an-zuordnung">
            <DkField label="Gruppe in Authentik" :error="zeilenFehler[i]" v-slot="feld">
              <input v-bind="feld" v-model="z.gruppe" class="dk-ui-eingabe" maxlength="255" placeholder="z. B. musik-leitung" />
            </DkField>
            <DkField label="Rolle in Diakronos" v-slot="feld">
              <select v-bind="feld" v-model="z.rolle" class="dk-ui-eingabe">
                <option value="">Bitte wählen</option>
                <option v-if="z.rolle && !rollen.includes(z.rolle)" :value="z.rolle">{{ z.rolle }} (nicht mehr verfügbar)</option>
                <option v-for="r in rollen" :key="r" :value="r">{{ r }}</option>
              </select>
            </DkField>
            <DkButton variant="ghost" :aria-label="`Zuordnung ${i + 1} entfernen`" @click="zuordnungen.splice(i, 1)">Entfernen</DkButton>
          </div>
          <DkButton variant="secondary" @click="zuordnungen.push({ gruppe: '', rolle: '' })">Zuordnung hinzufügen</DkButton>
          <label class="an-option an-admin">
            <input v-model="adminUeberGruppen" type="checkbox" />
            <span>Verwaltungsrollen über Authentik-Gruppen zulassen</span>
          </label>
          <DkHint variant="warn">Nur ein System Manager darf Verwaltungsrollen über Gruppen vergeben oder ändern.
            Wenn du diese Vergabe erlaubst, kann die Verwaltung der Authentik-Gruppen Zugriff auf die gesamte Gemeinde geben.
            Nutze dafür nur streng kontrollierte Gruppen.</DkHint>
        </DkCard>
        <DkButton type="submit" variant="primary" :loading="speichert">Speichern</DkButton>
      </fieldset>
    </form>
    <p v-if="erfolg" role="status">{{ erfolg }}</p>

    <DkCard title="Wartende und gesperrte Konten">
      <p>Hier erscheinen alle inaktiven Konten, auch manuell gesperrte. Prüfe vor dem Zulassen,
        ob die Person zur Gemeinde gehört. Ablehnen lässt das Konto gesperrt; es wird nicht gelöscht
        und bleibt zur Kontrolle in dieser Liste.</p>
      <DkHint v-if="kontenFehler" variant="err" role="alert">{{ kontenFehler }}</DkHint>
      <DkHint v-if="kontenLaden" role="status">Konten werden geladen …</DkHint>
      <DkButton v-else variant="ghost" @click="ladeKonten">Liste aktualisieren</DkButton>
      <p v-if="kontenGeladen && !konten.length">Keine wartenden oder gesperrten Konten.</p>
      <ul class="an-konten">
        <li v-for="k in konten" :key="k.user" class="an-konto">
          <div><strong>{{ k.full_name || k.user }}</strong><span class="an-hilfe">{{ k.email || k.user }}</span>
            <span class="an-hilfe">{{ k.mitglied_name || 'Noch keinem Mitglied zugeordnet' }}</span>
            <a v-if="k.mitglied && k.status !== 'geloescht'" :href="'#/mitglied/' + encodeURIComponent(k.mitglied)">Mitglied ansehen</a>
          </div>
          <div class="an-aktionen">
            <DkButton variant="primary" :disabled="kontoSpeichert" @click="vorbereiten(k, true)">Zulassen</DkButton>
            <DkButton variant="secondary" :disabled="kontoSpeichert" @click="vorbereiten(k, false)">Ablehnen</DkButton>
          </div>
        </li>
      </ul>
      <p v-if="kontoErfolg" role="status">{{ kontoErfolg }}</p>
    </DkCard>

    <DkDialog :model-value="!!aktion" :title="aktion?.freischalten ? 'Konto wieder zulassen?' : 'Konto ablehnen?'"
      :close-on-overlay="false" @update:model-value="schliesseAktion">
      <template v-if="aktion">
        <p><strong>{{ aktion.konto.full_name || aktion.konto.user }}</strong> ({{ aktion.konto.email || aktion.konto.user }})</p>
        <p>{{ aktion.freischalten ? 'Die Person kann sich danach anmelden. Vorhandene Rollen bleiben erhalten.' : 'Das Konto bleibt gesperrt. Die Person erhält keinen Zugang; ihre Daten werden nicht gelöscht.' }}</p>
        <DkHint v-if="aktion.konto.ausgeschlossen" variant="warn">Das Mitglied ist ausgeschlossen.
          Eine Kontofreigabe allein hebt den Ausschluss nicht auf.</DkHint>
        <DkHint v-if="aktionsFehler" variant="err" role="alert">{{ aktionsFehler }}</DkHint>
      </template>
      <template #footer>
        <DkButton variant="secondary" :disabled="kontoSpeichert" @click="schliesseAktion(false)">Abbrechen</DkButton>
        <DkButton :variant="aktion?.freischalten ? 'primary' : 'danger'" :loading="kontoSpeichert" @click="kontoAendern">
          {{ aktion?.freischalten ? 'Zulassen' : 'Gesperrt lassen' }}
        </DkButton>
      </template>
    </DkDialog>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick } from 'vue'
import { apiCall } from '../../composables/useApi.js'
import { useAnmeldeEinstellungen } from '../../composables/useAnmeldeEinstellungen.js'
import DkButton from '../../components/ui/DkButton.vue'
import DkCard from '../../components/ui/DkCard.vue'
import DkHint from '../../components/ui/DkHint.vue'
import DkField from '../../components/ui/DkField.vue'
import DkDialog from '../../components/ui/DkDialog.vue'

const { laedt, speichert, geladen, oidcAktiv, modus, adminUeberGruppen, rollen,
  zuordnungen, fehler, erfolg, zeilenFehler, bedienbar, laden, speichern } = useAnmeldeEinstellungen()
const formular = ref(null)
const modiOptionen = [
  { wert: 'abweisen', titel: 'Abweisen (sicherer Standard)', hinweis: 'Unbekannte Personen erhalten keinen Zugang und wenden sich an die Gemeindeleitung.' },
  { wert: 'als_gast_anlegen', titel: 'Konto anlegen und auf Freischaltung warten', hinweis: 'Kein Zugang bis zur Prüfung in der Kontenliste unten.' },
  { wert: 'anlegen_mit_rollen', titel: 'Sofort anlegen und Rollen aus Authentik-Gruppen übernehmen', hinweis: 'Das neue Konto ist sofort aktiv. Prüfe die Gruppen und Rechte besonders sorgfältig.' },
]
async function speichernMitFokus() {
  if (!await speichern()) {
    await nextTick()
    formular.value?.querySelector('[aria-invalid="true"]')?.focus()
  }
}
const konten = ref([])
const kontenLaden = ref(false)
const kontenGeladen = ref(false)
const kontenFehler = ref('')
const kontoErfolg = ref('')
const kontoSpeichert = ref(false)
const aktion = ref(null)
const aktionsFehler = ref('')
async function ladeKonten() {
  kontenLaden.value = true
  kontenFehler.value = ''
  try {
    const d = await apiCall('diakronos.diakonos.api.zugang.get_wartende_konten', {})
    konten.value = (d.message || d).konten || []
    kontenGeladen.value = true
  } catch (e) { kontenFehler.value = e.message || 'Die Konten konnten nicht geladen werden.' }
  finally { kontenLaden.value = false }
}
function vorbereiten(konto, freischalten) {
  aktionsFehler.value = ''
  aktion.value = { konto, freischalten }
}
function schliesseAktion(offen) { if (!offen && !kontoSpeichert.value) aktion.value = null }
async function kontoAendern() {
  if (!aktion.value || kontoSpeichert.value) return
  kontoSpeichert.value = true
  aktionsFehler.value = ''
  const { konto, freischalten } = aktion.value
  try {
    await apiCall('diakronos.diakonos.api.zugang.konto_freischalten', { user: konto.user, freischalten })
    kontoErfolg.value = freischalten ? 'Konto wieder zugelassen.' : 'Abgelehnt: Das Konto bleibt gesperrt.'
    aktion.value = null
    await ladeKonten()
  } catch (e) { aktionsFehler.value = e.message || 'Das Konto konnte nicht geändert werden.' }
  finally { kontoSpeichert.value = false }
}
onMounted(() => { laden(); ladeKonten() })
</script>

<style scoped>
.an-abschnitt, .an-felder { display: grid; gap: var(--sp-4); min-width: 0; }
.an-abschnitt h2, .an-abschnitt p { margin: 0; }
.an-felder { padding: 0; border: 0; margin: 0; }
.an-felder:disabled { opacity: .65; }
.an-optionen { display: grid; gap: var(--sp-3); margin-top: var(--sp-3); }
.an-option { display: flex; align-items: flex-start; gap: var(--sp-2); }
.an-option input { margin-top: var(--sp-1); flex-shrink: 0; }
.an-hilfe { display: block; color: var(--muted); font-size: var(--fs-sm); overflow-wrap: anywhere; }
.an-zuordnung { display: grid; grid-template-columns: 1fr 1fr auto; align-items: end; gap: var(--sp-2); margin-block: var(--sp-3); }
.an-admin { margin-block: var(--sp-4); }
.an-konten { list-style: none; padding: 0; margin: 0; }
.an-konto { display: flex; justify-content: space-between; gap: var(--sp-3); padding-block: var(--sp-3); border-bottom: 1px solid var(--line); }
.an-konto > div { min-width: 0; overflow-wrap: anywhere; }
.an-aktionen { display: flex; flex-wrap: wrap; align-items: center; gap: var(--sp-2); }
@media (max-width: 720px) {
  .an-zuordnung { grid-template-columns: 1fr; }
  .an-konto { flex-direction: column; }
}
</style>
