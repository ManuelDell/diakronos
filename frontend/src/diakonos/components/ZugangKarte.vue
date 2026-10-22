<template>
  <DkCard title="Zugang">
    <p class="zug-hinweis">
      Konto und Rollen dieses Mitglieds. Ohne Konto kann sich die Person nicht
      anmelden und bekommt keine Rechte.
    </p>

    <div v-if="laedt" class="zug-zustand">Lade…</div>
    <DkHint v-else-if="fehler" variant="err">{{ fehler }}</DkHint>

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
        <DkButton v-else variant="primary" size="sm" :loading="arbeitet" @click="anlegen">
          Zugang mit Einladungslink einrichten
        </DkButton>
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

        <DkField label="Rollen">
          <div class="zug-rollen">
            <label v-for="r in rollenWaehlbar" :key="r" class="zug-rolle">
              <input type="checkbox" :value="r" v-model="gewaehlteRollen" />
              <span>{{ r }}</span>
            </label>
          </div>
        </DkField>

        <div class="zug-aktionen">
          <DkButton variant="primary" size="sm" :loading="arbeitet" @click="rollenSpeichern">
            Rollen speichern
          </DkButton>
          <DkButton
            :variant="konto.enabled ? 'ghost' : 'secondary'"
            size="sm"
            :loading="arbeitet"
            @click="sperrenUmschalten"
          >
            {{ konto.enabled ? 'Konto sperren' : 'Konto wieder zulassen' }}
          </DkButton>
        </div>

        <DkButton v-if="!oidcAnmeldung" variant="secondary" :loading="arbeitet" @click="linkErzeugen">Passwort-Link neu erzeugen</DkButton>
        <DkHint v-else variant="info">Passwörter werden über Authentik verwaltet. Dieses Konto ist verknüpft.</DkHint>
        <DkField v-if="!oidcAnmeldung" label="Startpasswort setzen" help="Mindestens 8 Zeichen. Beim ersten Anmelden muss die Person es ändern.">
          <div class="zug-passwort">
            <!-- K3 (R-P1-8): Das Startpasswort wird verdeckt eingegeben
                 (type=password); der Anzeigen-Schalter gibt es bei Bedarf frei.
                 Vorher stand es im Klartext auf dem Bildschirm. -->
            <input v-model="neuesPasswort" class="dk-ui-eingabe"
                   :type="passwortSichtbar ? 'text' : 'password'"
                   autocomplete="new-password" placeholder="…" />
            <DkButton variant="secondary" size="sm" :loading="arbeitet"
                      :aria-pressed="String(passwortSichtbar)"
                      @click="passwortSichtbar = !passwortSichtbar">
              {{ passwortSichtbar ? 'Verbergen' : 'Anzeigen' }}
            </DkButton>
            <DkButton variant="secondary" size="sm" :loading="arbeitet"
                      :disabled="neuesPasswort.length < 8" @click="passwortSpeichern">
              Setzen
            </DkButton>
          </div>
        </DkField>
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
import DkBadge from './ui/DkBadge.vue'
import PasswortLink from './mitglieder/PasswortLink.vue'
import {
  zugangLesen, passwortLinkErzeugen, rollenSetzen, kontoSperren, passwortSetzen,
} from '../composables/usePflege.js'
import { showToast } from '../composables/useToast.js'

const props = defineProps({
  mitgliedId: { type: String, required: true },
  email: { type: String, default: '' },
  // Ob Authentik aktiv ist, weiss der Server; die Seite reicht es durch.
  oidcAktiv: { type: Boolean, default: false },
})
const emit = defineEmits(['geaendert'])

const laedt = ref(true)
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
    fehler.value = e?.message || 'Zugang konnte nicht geladen werden.'
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
    showToast(e?.message || 'Aktion fehlgeschlagen.', 'error')
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
.zug-hinweis { font-size: var(--fs-sm); color: var(--text-muted); margin: 0 0 var(--sp-3); }
.zug-zustand { color: var(--text-muted); padding: var(--sp-3) 0; }
.zug-muted { color: var(--text-muted); }
.zug-daten { margin: 0 0 var(--sp-3); }
.zug-daten dt { font-size: var(--fs-sm); color: var(--text-muted); }
.zug-daten dd { margin: 0 0 var(--sp-2); }
.zug-rollen { display: flex; flex-direction: column; gap: var(--sp-2); }
.zug-rolle { display: flex; align-items: center; gap: var(--sp-2); }
.zug-aktionen { display: flex; gap: var(--sp-2); flex-wrap: wrap; margin: var(--sp-3) 0; }
.zug-passwort { display: flex; flex-wrap: wrap; gap: var(--sp-2); align-items: center; }
.zug-oidc { margin-bottom: var(--sp-3); }
</style>
