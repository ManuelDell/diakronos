<template>
  <div class="an-abschnitt">
    <h2>Anmeldung (Login)</h2>
    <p>Hier legst du fest, wer über Authentik Zugang zur Gemeinde bekommt.</p>

    <DkSkelett v-if="ladeSichtbar" form="zeilen" :anzahl="4" text="Anmeldeeinstellungen werden geladen" />
    <DkHint v-else-if="geladen" :variant="oidcAktiv ? 'ok' : 'warn'" role="status">
      <strong>{{ oidcAktiv ? 'Authentik: eingerichtet' : 'Authentik: nicht eingerichtet' }}</strong>
      <p v-if="!oidcAktiv">Die Anmeldung erfolgt mit lokalem Passwort. Die Einstellungen darunter wirken erst,
        wenn Authentik eingerichtet ist, und sind deshalb gesperrt. Die Einrichtung übernimmt die Person,
        die den Server betreut (Betriebsanleitung, Abschnitt „Anmeldung über Authentik“).</p>
      <p v-else>Authentik ist am Server aktiviert. Dieser Status ist kein Verbindungstest zum Anbieter.</p>
    </DkHint>
    <DkHint v-if="fehler" variant="err" role="alert">{{ fehler }}</DkHint>
    <DkButton v-if="!geladen && !laedt" variant="secondary" @click="laden">Erneut versuchen</DkButton>

    <form ref="formular" @submit.prevent="speichernMitFokus">
      <!-- UI-R10b: der Server verlangt System Manager NUR für admin-relevante
           TEILE (`anmeldung/einstellungen_api._pruefe_admin_gruppen`, R-12i):
           den Schalter „Verwaltungsrollen über Gruppen“, Zuordnungen auf eine
           Verwaltungsrolle und den Modus „anlegen_mit_rollen“. Genau diese
           Stellen sind hier gesperrt und nennen den Grund — Mitglied- und
           Kalender-Zuordnungen bleiben bedienbar. Nur Komfort: der Server
           verweigert unverändert mit 403. -->
      <DkHint v-if="!istSystemManager" variant="warn" data-test="an-nur-admin">
        Gesperrt sind nur die Verwaltungs-Sachen: der Modus „Sofort anlegen und Rollen
        übernehmen“, Zuordnungen auf eine Verwaltungsrolle ({{ VERWALTUNGSROLLEN.join(', ') }})
        und der Schalter „Verwaltungsrollen über Authentik-Gruppen zulassen“ — dafür ist
        der Administrator (System Manager) zuständig. Andere Zuordnungen kannst du pflegen<span
          v-if="gespeicherterModus === 'anlegen_mit_rollen'">; gespeichert ist aber der
          Modus „anlegen“ — die Zuordnungen entscheiden dort, wer automatisch ein Konto
          bekommt, deshalb pflegt sie der Administrator</span>.
      </DkHint>
      <DkHint v-if="!istSystemManager && modusRadiosGesperrt" variant="warn" data-test="an-modus-nur-admin">
        Gespeichert ist der Modus „Sofort anlegen“ — nur der Administrator darf ihn wechseln
        (auch zurück auf „Abweisen“). Die Zuordnungen unten bleiben deshalb gesperrt.
      </DkHint>
      <fieldset :disabled="!bedienbar" class="an-felder">
        <DkCard title="Unbekannte Personen" anker="unbekannte-personen">
          <p>Was passiert, wenn eine Person noch kein Konto in Diakronos hat?</p>
          <div class="an-optionen">
            <label v-for="opt in modiOptionen" :key="opt.wert" class="an-option"
              :class="{ 'is-gesperrt': modusOptionGesperrt(opt) }">
              <input v-model="modus" type="radio" name="unbekannte-personen" :value="opt.wert"
                :disabled="modusOptionGesperrt(opt)" />
              <span><strong>{{ opt.titel }}</strong><span class="an-hilfe">{{ opt.hinweis }}</span>
                <span v-if="modusOptionGesperrt(opt)" class="an-hilfe an-grund">
                  {{ modusOptionGrund(opt) }}</span></span>
            </label>
          </div>
        </DkCard>

        <DkCard title="Authentik-Gruppen und Rollen" anker="authentik-gruppen">
          <p>Links steht der genaue Gruppenname in Authentik, nicht eine Gruppe dieser Gemeinde.
            Rechts wählst du die Rechte in Diakronos. Beim Anmelden werden Rollen ergänzt, nicht entzogen.
            Auch bestehende Konten erhalten passende Gruppenrollen.</p>
          <DkHint v-if="!systemManagerPflicht" variant="info">
            Die Zuordnungen gelten auch für bekannte Konten. Der Modus oben regelt nur neue Konten.
          </DkHint>
          <!-- UI-R10b (R-12i): im GESPEICHERTEN Modus „anlegen“ entscheiden die
               Zuordnungen, wer automatisch ein Konto bekommt — dort bleibt JEDE
               Änderung beim System Manager (Server: `_pruefe_admin_gruppen`).
               Deshalb ist die ganze Liste gesperrt, nicht nur einzelne Zeilen. -->
          <DkHint v-if="!istSystemManager && listeGesperrt" variant="warn" data-test="an-liste-nur-admin">
            Im Modus „anlegen“ pflegt der Administrator die Zuordnungen.
          </DkHint>
          <div v-for="(z, i) in zuordnungen" :key="i" class="an-zuordnung"
            :class="{ 'is-zeile-gesperrt': zeilengesperrt(z) }"
            :data-test="zeilengesperrt(z) ? 'an-zuordnung-admin-rolle' : undefined">
            <DkField label="Gruppe in Authentik" :error="zeilenFehler[i]"
              :wert="z.gruppe" @update:wert="z.gruppe = $event" v-slot="feld">
              <input v-bind="feld.feldProps" class="dk-ui-eingabe" maxlength="255"
                :disabled="zeilengesperrt(z)" placeholder="z. B. musik-leitung" />
            </DkField>
            <DkField label="Rolle in Diakronos"
              :wert="z.rolle" @update:wert="z.rolle = $event" v-slot="feld">
              <select v-bind="feld.feldProps" class="dk-ui-eingabe"
                :disabled="zeilengesperrt(z)">
                <option value="">Bitte wählen</option>
                <option v-if="z.rolle && !rollen.includes(z.rolle)" :value="z.rolle">{{ z.rolle }} (nicht mehr verfügbar)</option>
                <!-- Nur die Verwaltungsrollen sperren, nicht die ganze Auswahl
                     (R-12i: Mitglied-/Kalender-Zuordnungen darf die Verwaltung
                     pflegen). Liste aus `verwaltungsrollen.mjs` — EINE Quelle. -->
                <option v-for="r in rollen" :key="r" :value="r" :disabled="rollenOptionGesperrt(r)">
                  {{ r }}<template v-if="rollenOptionGesperrt(r)"> (nur Administrator)</template>
                </option>
              </select>
            </DkField>
            <DkButton variant="ghost" :aria-label="`Zuordnung ${i + 1} entfernen`"
              :disabled="zeilengesperrt(z)" @click="zuordnungen.splice(i, 1)">Entfernen</DkButton>
            <p v-if="zeilengesperrt(z)" class="an-hilfe an-grund">
              Diese Zeile vergibt eine Verwaltungsrolle. Nur der Administrator.</p>
          </div>
          <DkButton variant="secondary" :disabled="!zuordnungenAenderbar" data-test="an-zuordnung-ergaenzen"
            @click="zuordnungen.push({ gruppe: '', rolle: '' })">Zuordnung ergänzen</DkButton>
          <label class="an-option an-admin" :class="{ 'is-gesperrt': !istSystemManager }">
            <input v-model="adminUeberGruppen" type="checkbox" :disabled="!istSystemManager" />
            <span>Verwaltungsrollen über Authentik-Gruppen zulassen</span>
          </label>
          <p v-if="!istSystemManager" class="an-hilfe an-grund">Nur der Administrator.</p>
          <DkHint variant="warn">Nur ein System Manager darf Verwaltungsrollen über Gruppen vergeben oder ändern.
            Wenn du diese Vergabe erlaubst, kann die Verwaltung der Authentik-Gruppen Zugriff auf die gesamte Gemeinde geben.
            Nutze dafür nur streng kontrollierte Gruppen.</DkHint>
        </DkCard>
        <DkButton type="submit" variant="primary" :loading="speichert"
          :disabled="!kannSpeichern" :aria-disabled="kannSpeichern ? undefined : 'true'"
          :title="kannSpeichern ? undefined : 'Keine Änderung zum Speichern'">Speichern</DkButton>
      </fieldset>
    </form>
    <DkErfolgsmeldung :text="erfolg" />

    <DkCard title="Wartende und gesperrte Konten">
      <p>Hier erscheinen alle inaktiven Konten, auch manuell gesperrte. Prüfe vor dem Zulassen,
        ob die Person zur Gemeinde gehört. Ablehnen lässt das Konto gesperrt; es wird nicht gelöscht
        und bleibt zur Kontrolle in dieser Liste.</p>
      <DkHint v-if="kontenFehler" variant="err" role="alert">{{ kontenFehler }}</DkHint>
      <DkSkelett v-if="kontenSichtbar" kurz form="zeilen" :anzahl="3" text="Konten werden geladen" />
      <DkButton v-else-if="kontenFehler" variant="ghost" @click="ladeKonten">Erneut versuchen</DkButton>
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
import { ref, onMounted, nextTick, computed, watch } from 'vue'
import { apiCall } from '../../composables/useApi.js'
import { useAnmeldeEinstellungen } from '../../composables/useAnmeldeEinstellungen.js'
// UX3h3: „Speichern nur, wenn geändert“ — EINE Regel für alle Abschnitte.
import { useGeaendertStand } from '../../composables/useGeaendert.js'
import DkButton from '../../components/ui/DkButton.vue'
import DkCard from '../../components/ui/DkCard.vue'
import DkHint from '../../components/ui/DkHint.vue'
import DkField from '../../components/ui/DkField.vue'
import DkDialog from '../../components/ui/DkDialog.vue'
import DkErfolgsmeldung from '../../components/ui/DkErfolgsmeldung.vue'
// UX2d3b (Review UX2d3a/B): Laden zeigt den Umriss, keinen Satz.
import DkSkelett from '../../components/ui/DkSkelett.vue'
import { useLadeSkelett } from '../../composables/useLadeSkelett.js'
// UI-R10b: die Verwaltungs-Stellen dieses Abschnitts verlangen beim Server
// System Manager; die Sitzung liefert die Rolle (`boot.roles`).
import { useSession } from '../../composables/useSession.js'
// UI-R10b (R-12i): EINE Quelle für „das ist eine Verwaltungsrolle“ —
// dieselbe Liste nutzt `RollenRechte.vue`.
import { VERWALTUNGSROLLEN, istVerwaltungsrolle } from '../../verwaltungsrollen.mjs'

const { laedt, speichert, geladen, oidcAktiv, modus, adminUeberGruppen, rollen,
  zuordnungen, fehler, erfolg, zeilenFehler, bedienbar, laden, speichern } = useAnmeldeEinstellungen()
const formular = ref(null)

// ── UX3h3: „Speichern nur, wenn geändert“ ────────────────────────────────
/**
 * Der geladene Stand: Modus, Haken „Verwaltungsrollen über Gruppen“ und die
 * Zeilen der Authentik-Zuordnungen. Die Zeilen werden als LISTE verglichen —
 * eine leere Zeile („Zuordnung ergänzen“) ist noch keine Änderung, ein
 * eingetippter Wert schon (`composables/geaendert.mjs`).
 */
const stand = useGeaendertStand()
const feldsatz = () => ({
  modus: modus.value,
  adminUeberGruppen: adminUeberGruppen.value,
  zuordnungen: zuordnungen.value.map(z => ({ gruppe: z.gruppe, rolle: z.rolle })),
})
const geaendert = stand.geaendert(feldsatz)
const kannSpeichern = computed(() => bedienbar.value && geaendert.value)
/**
 * UI-R10c: Der GESPEICHERTE Modus — nicht der gerade im Formular gewählte.
 *
 * Die Sperren unten folgen dem, was der Server beim Speichern vergleicht
 * (`einstellungen_api._pruefe_admin_gruppen`, R-12i): System Manager braucht es,
 * sobald „anlegen_mit_rollen“ gespeichert ist ODER gespeichert werden soll —
 * hinein wie heraus. Am Formularwert hing die Sperre bisher falsch: war
 * „anlegen_mit_rollen“ gespeichert, entsperrte ein Klick auf „Abweisen“ sofort
 * die ganze Zuordnungsliste und blendete den Grund aus — beim Speichern kam
 * dann 403. Quelle ist derselbe Stand, den „Speichern nur, wenn geändert“ nutzt
 * (nach dem Laden und nach erfolgreichem Speichern gesetzt).
 */
const gespeicherterModus = computed(() => stand.stand.value?.modus ?? modus.value)
watch(geladen, (ist) => { if (ist) stand.merken(feldsatz) })
watch(speichert, (laeuft, lief) => { if (lief && !laeuft && !fehler.value) stand.merken(feldsatz) })
const { istSystemManager } = useSession()
/**
 * UI-R10b (R-12i) — was sperrt der Server wirklich?
 *
 * `_pruefe_admin_gruppen` verlangt System Manager für (a) den Schalter
 * „Verwaltungsrollen über Gruppen“, (b) Zuordnungen auf eine Verwaltungsrolle
 * und (c) den Modus „anlegen_mit_rollen“ (hinein wie heraus). Ist der Modus
 * GESPEICHERT, entscheiden die Zuordnungen, wer automatisch ein Konto bekommt
 * (Zugangsweg, R-N8) — dann bleibt jede Zuordnungs-Änderung beim System
 * Manager. Alles andere darf die Mitgliederverwaltung pflegen; hier wird nur
 * gesperrt, was der Server ohnehin verweigert.
 */
const systemManagerPflicht = computed(() => gespeicherterModus.value === 'anlegen_mit_rollen')
/** Die ganze Zuordnungsliste gesperrt: nur für Nicht-System-Manager im Modus „anlegen“. */
const listeGesperrt = computed(() => !istSystemManager.value && systemManagerPflicht.value)
/** Darf „Zuordnung ergänzen“ gedrückt werden? (Entfernen hängt an der Zeile.) */
const zuordnungenAenderbar = computed(() => !listeGesperrt.value)
/**
 * UI-R10c: Sind ALLE Modus-Radios gesperrt? Gespeicherter Modus
 * „anlegen_mit_rollen“ — der Server verlangt den System Manager für den Wechsel
 * IN diesen Modus UND für den Wechsel HERAUS. Ein Klick auf „Abweisen“ wäre
 * also ein 403; deshalb bleiben hier alle drei Felder zu, mit Grund am Feld.
 */
const modusRadiosGesperrt = computed(() => !istSystemManager.value && systemManagerPflicht.value)
/** Ist dieser Modus für diese Sitzung nicht wählbar? */
function modusOptionGesperrt(opt) {
  if (istSystemManager.value) return false
  return modusRadiosGesperrt.value || opt.nurAdmin === true
}
/** Der Grund am gesperrten Modus (ohne Grund wirkt die Sperre wie ein Fehler). */
function modusOptionGrund(opt) {
  return modusRadiosGesperrt.value
    ? 'Gesperrt, weil „Sofort anlegen“ gespeichert ist. Nur der Administrator.'
    : 'Nur der Administrator.'
}
/** Eine Verwaltungsrolle im Auswahlfeld ist für Nicht-System-Manager nicht wählbar. */
function rollenOptionGesperrt(rolle) {
  return !istSystemManager.value && istVerwaltungsrolle(rolle)
}
/** Eine Zeile, die schon eine Verwaltungsrolle trägt (oder die ganze Liste im Modus „anlegen“). */
function zeilengesperrt(z) {
  if (listeGesperrt.value) return true
  return !istSystemManager.value && istVerwaltungsrolle(z.rolle)
}
const modiOptionen = [
  { wert: 'abweisen', titel: 'Abweisen (sicherer Standard)', hinweis: 'Unbekannte Personen erhalten keinen Zugang und wenden sich an die Gemeindeleitung.' },
  { wert: 'als_gast_anlegen', titel: 'Konto anlegen und auf Freischaltung warten', hinweis: 'Kein Zugang bis zur Prüfung in der Kontenliste unten.' },
  // UI-R10b: `nurAdmin` — der Server verlangt für diesen Modus System Manager
  // (`anmeldung/einstellungen_api._require_admin`). Für die Mitgliederverwaltung
  // ist die Auswahl gesperrt und sagt warum.
  { wert: 'anlegen_mit_rollen', titel: 'Sofort anlegen und Rollen aus Authentik-Gruppen übernehmen', hinweis: 'Das neue Konto ist sofort aktiv. Prüfe die Gruppen und Rechte besonders sorgfältig.', nurAdmin: true },
]
async function speichernMitFokus() {
  if (!await speichern()) {
    await nextTick()
    formular.value?.querySelector('[aria-invalid="true"]')?.focus()
    return
  }
  // UX3h3: Gespeichert = der eingetippte Satz IST jetzt der gespeicherte
  // Stand → „Speichern“ wieder gesperrt (bis zur nächsten Änderung).
  stand.merken(feldsatz)
}
// UX2d3b: Platzhalter erst nach 300 ms (kein Blitzen, keine Aussage vor der Antwort).
const { skelettSichtbar: ladeSichtbar } = useLadeSkelett(laedt)
const konten = ref([])
const kontenLaden = ref(false)
const { skelettSichtbar: kontenSichtbar } = useLadeSkelett(kontenLaden)
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
/* UI-R10b: gesperrte Stelle — sie sieht gesperrt aus UND nennt den Grund
   (`.an-grund` steht direkt darunter). Kein reines Ausgrauen ohne Satz. */
.an-option.is-gesperrt, .an-admin.is-gesperrt { opacity: .6; }
/* UI-R10b (R-12i): eine Zeile mit Verwaltungsrolle ist ganz gesperrt —
   Felder und „Entfernen“ — und nennt den Grund darunter. */
.an-zuordnung.is-zeile-gesperrt { opacity: .75; }
.an-zuordnung.is-zeile-gesperrt > .an-grund { grid-column: 1 / -1; }
.an-grund { color: var(--warn); }
.an-konten { list-style: none; padding: 0; margin: 0; }
.an-konto { display: flex; justify-content: space-between; gap: var(--sp-3); padding-block: var(--sp-3); border-bottom: 1px solid var(--line); }
.an-konto > div { min-width: 0; overflow-wrap: anywhere; }
.an-aktionen { display: flex; flex-wrap: wrap; align-items: center; gap: var(--sp-2); }
@media (max-width: 720px) {
  .an-zuordnung { grid-template-columns: 1fr; }
  .an-konto { flex-direction: column; }
}
</style>
