<template>
  <DkCard title="Zugang">
    <p class="zug-hinweis">
      Konto und Rollen dieses Mitglieds. Ohne Konto kann sich die Person nicht
      anmelden und bekommt keine Rechte.
    </p>

    <!-- UX2d3a: Laden zeigt den Umriss der Felder (Skelett, erst nach 300 ms).
         Fehler: echte Meldung + „Erneut versuchen“ an `laden`. -->
    <DkSkelett v-if="skelettSichtbar" kurz form="zeilen" :anzahl="3" text="Zugang wird geladen …" />
    <DkEmpty
      v-else-if="fehler"
      icon="!"
      title="Zugang nicht geladen"
      :text="fehler"
      :erneut-versuchen="laden"
    />

    <template v-else>
      <!-- Kein Konto -->
      <template v-if="!konto">
        <p class="zug-muted">Dieses Mitglied hat noch keinen Zugang.</p>
        <div v-if="oidcAnmeldung" class="zug-oidc">
          <DkHint variant="info">
            Über Authentik entstehen Konten beim Anbieter. Bitte dort anlegen —
            die Zuordnung passiert beim ersten Login über die E-Mail
            {{ email || 'des Mitglieds' }}.
          </DkHint>
        </div>
        <!-- DEV-B3 (Review): Ohne Konto legt der Einladungslink serverseitig
             ein Konto an (`zugang.einladungslink` → `konto_anlegen`) — das ist
             eine Änderung am Zugang und deshalb nur im Bearbeiten-Modus. -->
        <DkButton
          v-else-if="bearbeitbar" variant="primary" size="md" :loading="arbeitet" @click="anlegen"
        >
          Zugang mit Einladungslink einrichten
        </DkButton>
        <p v-else class="zug-hinweis">
          Ein Zugang wird über „Bearbeiten“ eingerichtet.
        </p>
      </template>

      <!-- Konto vorhanden -->
      <template v-else>
        <dl class="zug-daten">
          <dt>Konto</dt><dd>{{ konto.user }}</dd>
          <dt>Zustand</dt>
          <dd>
            <DkBadge :variant="konto.enabled ? 'ok' : 'err'">
              {{ konto.enabled ? 'Freigeschaltet' : 'Gesperrt' }}
            </DkBadge>
          </dd>
        </dl>

        <!-- DEV-B3 (DMB-2b8262b82c08): Rollen nur im Bearbeiten-Modus ändern.
             Sonst zeigt die Karte die Rollen als Text — kein Kontrollkästchen,
             das nichts bewirkt. -->
        <DkField v-if="bearbeitbar" label="Rollen">
          <div class="zug-rollen">
            <label v-for="r in rollenWaehlbar" :key="r" class="zug-rolle">
              <input type="checkbox" :value="r" v-model="gewaehlteRollen" />
              <span>{{ r }}</span>
            </label>
          </div>
        </DkField>
        <div v-else class="zug-feld">
          <p class="zug-label">Rollen</p>
          <p class="zug-muted">
            {{ gewaehlteRollen.length ? gewaehlteRollen.join(', ') : 'Keine Rolle zugewiesen' }}
          </p>
        </div>

        <div v-if="bearbeitbar" class="zug-aktionen">
          <DkButton variant="primary" size="md" :loading="arbeitet" @click="rollenSpeichern">
            Rollen speichern
          </DkButton>
          <DkButton
            :variant="konto.enabled ? 'ghost' : 'secondary'"
            size="md"
            :loading="arbeitet"
            @click="sperrenUmschalten"
          >
            {{ konto.enabled ? 'Konto sperren' : 'Konto wieder zulassen' }}
          </DkButton>
        </div>

        <!-- Immer erlaubt: nur ein Link, keine Änderung am Mitglied. -->
        <DkButton v-if="!oidcAnmeldung" variant="secondary" :loading="arbeitet" @click="linkErzeugen">Passwort-Link neu erzeugen</DkButton>
        <DkHint v-else variant="info">Passwörter werden über Authentik verwaltet. Dieses Konto ist verknüpft.</DkHint>
        <DkField v-if="!oidcAnmeldung && bearbeitbar" label="Startpasswort setzen" help="Mindestens 8 Zeichen. Beim ersten Anmelden muss die Person es ändern.">
          <div class="zug-passwort">
            <!-- K3 (R-P1-8): Das Startpasswort wird verdeckt eingegeben
                 (type=password); der Anzeigen-Schalter gibt es bei Bedarf frei.
                 Vorher stand es im Klartext auf dem Bildschirm. -->
            <input v-model="neuesPasswort" class="dk-ui-eingabe"
                   :type="passwortSichtbar ? 'text' : 'password'"
                   autocomplete="new-password" placeholder="…" />
            <DkButton variant="secondary" size="md" :loading="arbeitet"
                      :aria-pressed="String(passwortSichtbar)"
                      @click="passwortSichtbar = !passwortSichtbar">
              {{ passwortSichtbar ? 'Verbergen' : 'Anzeigen' }}
            </DkButton>
            <DkButton variant="secondary" size="md" :loading="arbeitet"
                      :disabled="neuesPasswort.length < 8" @click="passwortSpeichern">
              Setzen
            </DkButton>
          </div>
        </DkField>
        <p v-if="!bearbeitbar && !oidcAnmeldung" class="zug-hinweis">
          Rollen, Kontozustand und Startpasswort ändern sich über „Bearbeiten“.
        </p>
      </template>
    </template>
    <PasswortLink v-if="passwortLink" :daten="passwortLink" />
  </DkCard>
</template>

<script setup>
/**
 * ZugangKarte — Konto und Rollen eines Mitglieds pflegen (OP-ADMIN-2, P1-8).
 *
 * Ohne Authentik ist dies der einzige Weg zu einem Zugang; mit aktivem
 * Authentik entstehen Konten beim Anbieter (Entscheidung 5) — dann zeigt die
 * Karte nur den Hinweis. Rollen kommen aus der FESTEN Diakronos-Liste des
 * Servers; die Zuweisung prueft ohnehin das Backend.
 */
import { ref, onMounted } from 'vue'
import DkCard from './ui/DkCard.vue'
import DkButton from './ui/DkButton.vue'
import DkField from './ui/DkField.vue'
import DkHint from './ui/DkHint.vue'
import DkEmpty from './ui/DkEmpty.vue'
import DkSkelett from './ui/DkSkelett.vue'
import { useLadeSkelett } from '../composables/useLadeSkelett.js'
import DkBadge from './ui/DkBadge.vue'
import PasswortLink from './mitglieder/PasswortLink.vue'
import {
  zugangLesen, passwortLinkErzeugen, rollenSetzen, kontoSperren, passwortSetzen,
} from '../composables/usePflege.js'
import { showToast } from '../composables/useToast.js'
// UX2d3b (Review UX2d3a/A): Fehlertexte aus dem Katalog, nicht `e?.message`
// (das zeigte „HTTP 500“).
import { aktionsfehler } from '../../shared/fehlertexte.js'

const props = defineProps({
  mitgliedId: { type: String, required: true },
  email: { type: String, default: '' },
  // Ob Authentik aktiv ist, weiss der Server; die Seite reicht es durch.
  oidcAktiv: { type: Boolean, default: false },
  // DEV-B3 (DMB-2b8262b82c08): Rollen, Kontozustand und Startpasswort nur
  // im Bearbeiten-Modus der Detailseite. Der Passwort-Link ist davon
  // ausgenommen (nur ein Link, keine Änderung am Mitglied).
  bearbeitbar: { type: Boolean, default: false },
})
const emit = defineEmits(['geaendert'])

const laedt = ref(true)
// UX2d3a: Platzhalter erst, wenn das Laden merklich dauert (300 ms).
const { skelettSichtbar } = useLadeSkelett(laedt)
const fehler = ref('')
const konto = ref(null)
const rollenWaehlbar = ref([])
const gewaehlteRollen = ref([])
const neuesPasswort = ref('')
const passwortSichtbar = ref(false)
const arbeitet = ref(false)
const oidcAnmeldung = ref(props.oidcAktiv)
const passwortLink = ref(null)

async function laden() {
  laedt.value = true
  fehler.value = ''
  try {
    const daten = await zugangLesen(props.mitgliedId)
    konto.value = daten.konto
    oidcAnmeldung.value = daten.oidc_aktiv === true
    rollenWaehlbar.value = daten.rollen_waehlbar || []
    gewaehlteRollen.value = (daten.konto?.rollen || []).filter(
      (r) => rollenWaehlbar.value.includes(r)
    )
  } catch (e) {
    fehler.value = aktionsfehler('laden', e)
  } finally {
    laedt.value = false
  }
}

async function _fuehreAktion(fn, erfolg) {
  arbeitet.value = true
  try {
    await fn()
    await laden()
    showToast(erfolg, 'success')
    emit('geaendert')
  } catch (e) {
    showToast(aktionsfehler('aktion', e), 'error')
  } finally {
    arbeitet.value = false
  }
}

function anlegen() {
  linkErzeugen()
}

function linkErzeugen() {
  passwortLink.value = null
  _fuehreAktion(async () => {
    passwortLink.value = await passwortLinkErzeugen(props.mitgliedId)
  }, 'Passwort-Link erstellt.')
}

function rollenSpeichern() {
  _fuehreAktion(
    () => rollenSetzen(props.mitgliedId, gewaehlteRollen.value),
    'Rollen gespeichert.'
  )
}

function sperrenUmschalten() {
  const gesperrt = !konto.value.enabled
  _fuehreAktion(
    () => kontoSperren(props.mitgliedId, gesperrt),
    gesperrt ? 'Konto gesperrt.' : 'Konto freigeschaltet.'
  )
}

function passwortSpeichern() {
  passwortLink.value = null
  _fuehreAktion(
    () => passwortSetzen(props.mitgliedId, neuesPasswort.value),
    'Startpasswort gesetzt.'
  ).then(() => { neuesPasswort.value = '' })
}

onMounted(laden)
</script>

<style scoped>
.zug-hinweis { font-size: var(--fs-sm); color: var(--muted); margin: 0 0 var(--sp-3); }
.zug-zustand { color: var(--muted); padding: var(--sp-3) 0; }
.zug-muted { color: var(--muted); }
.zug-daten { margin: 0 0 var(--sp-3); }
.zug-daten dt { font-size: var(--fs-sm); color: var(--muted); }
.zug-daten dd { margin: 0 0 var(--sp-2); }
.zug-rollen { display: flex; flex-direction: column; gap: var(--sp-2); }
.zug-rolle { display: flex; align-items: center; gap: var(--sp-2); }
.zug-aktionen { display: flex; gap: var(--sp-2); flex-wrap: wrap; margin: var(--sp-3) 0; }
.zug-passwort { display: flex; flex-wrap: wrap; gap: var(--sp-2); align-items: center; }
.zug-oidc { margin-bottom: var(--sp-3); }
/* DEV-B3: Rollen im Ansichtsmodus als Text (gleiche Anmutung wie DkField-Label). */
.zug-feld { margin-bottom: var(--sp-3); }
.zug-label { font-size: var(--fs-sm); font-weight: var(--fw-fett); color: var(--text); margin: 0 0 var(--sp-1); }
.zug-feld .zug-muted { margin: 0; }
</style>
