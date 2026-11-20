<template>
  <div class="bn-abschnitt" role="region" aria-labelledby="bn-titel">
    <h2 id="bn-titel">{{ PUSH_TITEL }}</h2>
    <p class="bn-einleitung">{{ PUSH_EINLEITUNG }}</p>

    <DkSkelett v-if="laedt" form="zeilen" :anzahl="2" text="Der Stand wird geladen" />

    <DkHint v-else-if="fehler" variant="err" role="alert">{{ fehler }}</DkHint>

    <template v-else>
      <!-- 1. Der Server kennt keine Schlüssel: ruhiger Satz, kein Schalter. -->
      <p v-if="zustand === 'server_aus'" class="bn-ruhig" data-test="bn-server-aus">{{ PUSH_SERVER_AUS }}</p>

      <!-- 2. Der Browser kann es nicht (ggf. mit dem iPhone-Satz). -->
      <template v-else-if="zustand === 'browser_aus'">
        <p class="bn-ruhig" data-test="bn-browser-aus">{{ PUSH_BROWSER_FEHLT }}</p>
        <p v-if="iphone" class="bn-klein" data-test="bn-iphone">{{ PUSH_IPHONE_HINWEIS }}</p>
      </template>

      <!-- 3. Gesperrt: der Satz, wie man es zurückholt — KEINE erneute Frage. -->
      <p v-else-if="zustand === 'verweigert'" class="bn-ruhig" data-test="bn-verweigert">{{ PUSH_VERWEIGERT }}</p>

      <!-- 4. Der Schalter. Der Inhaltssatz steht IMMER im Abschnitt — beim
           Schalter erklärt er ihn (`aria-describedby`). -->
      <template v-else>
        <div class="bn-schalter">
          <DkCheckbox
            :model-value="zustand === 'an'"
            :disabled="laeuft"
            :aria-describedby="HINWEIS_ID"
            :aria-label="PUSH_SCHALTER"
            data-test="bn-schalter"
            @update:model-value="umschalten"
          >{{ PUSH_SCHALTER }}</DkCheckbox>
        </div>
        <DkHint v-if="aktionsFehler" variant="err" role="alert">{{ aktionsFehler }}</DkHint>
      </template>

      <!-- Die Zusage des Abschnitts — sie hängt nicht am Schalter. -->
      <p :id="HINWEIS_ID" class="bn-klein" data-test="bn-inhaltssatz">{{ PUSH_INHALTSSATZ }}</p>
    </template>
  </div>
</template>

<script setup>
/**
 * CHAT-10b — Einstellungen › „Benachrichtigungen aufs Gerät“.
 *
 * Sichtbar für JEDE angemeldete Person (wie „Gesperrte Personen“): es geht um
 * das eigene Gerät. Der Server entscheidet ohnehin (`push.*` prüft `_benutzer`).
 *
 * ABLAUF BEIM ÖFFNEN
 *   1. `push.schluessel` (GET) — kennt der Server überhaupt Schlüssel?
 *      `aktiv: false` → ruhiger Satz, KEIN Schalter (nichts anzubieten).
 *   2. Kann dieser Browser es (Service Worker + Benachrichtigungen +
 *      PushManager)? Sonst Satz statt Schalter.
 *   3. Bestehendes Abonnement über `getSubscription()` lesen — NUR der Browser
 *      weiß, ob dieses Gerät angemeldet ist. Es wird dabei NICHTS gefragt und
 *      nichts angemeldet: das passiert ausschließlich auf Klick.
 *
 * ABLAUF BEIM ANSCHALTEN (nur nach Klick)
 *   1. `Notification.requestPermission()` — die Frage des Browsers erscheint
 *      erst hier, nie beim Öffnen der Seite.
 *   2. Service Worker registrieren (`/sw.js`, mit Betriebs-Präfix).
 *   3. `pushManager.subscribe({userVisibleOnly: true, applicationServerKey})`
 *      mit dem öffentlichen Schlüssel des Servers.
 *   4. `push.anmelden` (POST) mit `endpoint`, `p256dh`, `auth`.
 *   Schlägt ein Schritt fehl, wird das Abonnement NICHT behauptet: der
 *   Schalter springt zurück und der Grund steht darunter.
 *
 * ABLAUF BEIM AUSSCHALTEN
 *   `subscription.unsubscribe()` und danach `push.abmelden` (POST). Umgekehrte
 *   Reihenfolge wäre falsch: ohne Abonnement kann der Server nicht mehr
 *   senden — das ist der Teil, der wirklich zählt. Ein Fehler beim Abmelden
 *   wird gemeldet, aber das Gerät gilt trotzdem als abgemeldet (der Browser
 *   hat das Abonnement verworfen).
 *
 * ABGEMELDET IM BROWSER (`denied`) → Satz, wie man es zurückholt; es wird
 * NICHT erneut gefragt (der Browser fragt nach einer Ablehnung nicht wieder).
 */
import { computed, onMounted, ref } from 'vue'
import { apiCall, apiGet } from '../../composables/useApi.js'
import { mitBasis } from '../../../shared/basis.js'
import { fehlertext } from '../../../shared/fehlertexte.js'
import DkCheckbox from '../../components/ui/DkCheckbox.vue'
import DkHint from '../../components/ui/DkHint.vue'
import DkSkelett from '../../components/ui/DkSkelett.vue'
import {
  PUSH_BROWSER_FEHLT, PUSH_EINLEITUNG, PUSH_FEHLER_AUS, PUSH_FEHLER_EIN,
  PUSH_IPHONE_HINWEIS, PUSH_INHALTSSATZ,
  PUSH_SCHALTER, PUSH_SERVER_AUS, PUSH_TITEL, PUSH_VERWEIGERT,
  browserKannPush, istIphone, schluesselBytes, SW_PFAD, zustand as zustandFuer,
} from './benachrichtigungen.mjs'

/** Kennung des Satzes, der den Schalter erklärt (`aria-describedby`). */
const HINWEIS_ID = 'bn-schalter-hinweis'

const laedt = ref(true)
const fehler = ref('')
const aktionsFehler = ref('')
const laeuft = ref(false)

const serverAktiv = ref(false)
const oeffentlicherSchluessel = ref('')
const berechtigung = ref('')
const abonniert = ref(false)
const serverAn = ref(false)
const umgebung = typeof globalThis !== 'undefined' ? globalThis : {}

const browserKann = computed(() => browserKannPush(umgebung))
const iphone = computed(() => istIphone(umgebung))

const zustand = computed(() => zustandFuer({
  serverAktiv: serverAktiv.value,
  browserKann: browserKann.value,
  berechtigung: berechtigung.value,
  abonniert: abonniert.value,
  serverAn: serverAn.value,
}))

/** Der Service Worker dieses Browsers — oder `null`. */
function swZugang() {
  return umgebung.navigator?.serviceWorker || null
}

/** Die bestehende Anmeldung dieses Geräts — ohne Frage, ohne Schreiben. */
async function bestehendesAbo() {
  const sw = swZugang()
  if (!sw) return null
  try {
    const reg = await sw.getRegistration()
    return await (reg?.pushManager?.getSubscription?.() || null)
  } catch {
    return null
  }
}

async function laden() {
  laedt.value = true
  fehler.value = ''
  aktionsFehler.value = ''
  // Die eigene Berechtigung ist noch kein Serverstand — sie gilt auch dann,
  // wenn der Server keine Schlüssel hat.
  berechtigung.value = String(umgebung.Notification?.permission || '')
  try {
    const antwort = await apiGet('diakronos_app.api.push.schluessel', {})
    serverAktiv.value = Boolean(antwort?.aktiv)
    oeffentlicherSchluessel.value = String(antwort?.public_key || '')
    if (!serverAktiv.value) {
      abonniert.value = false
      serverAn.value = false
      return
    }
    if (!browserKann.value) return
    const abo = await bestehendesAbo()
    abonniert.value = Boolean(abo)
    // Ein Abonnement ohne Servermeldung: der Server ist die Wahrheit darüber,
    // ob er dieses Gerät kennt. `anmelden` ist idempotent — deshalb wird ein
    // vorhandenes Abo hier nachgemeldet statt im Schalter zu lügen.
    serverAn.value = false
    if (abo) {
      serverAn.value = await nachmelden(abo)
    }
  } catch (err) {
    fehler.value = fehlertext(err)
  } finally {
    laedt.value = false
  }
}

/**
 * Ein bestehendes Abonnement beim Server anmelden (idempotent).
 * Liefert `true`, wenn der Server es kennt. Fehler werden zu `false` — der
 * Schalter bleibt dann aus und bietet das Anschalten an.
 */
async function nachmelden(abo) {
  try {
    const daten = abo?.toJSON ? abo.toJSON() : abo
    const antwort = await apiCall('diakronos_app.api.push.anmelden', {
      endpoint: String(daten?.endpoint || ''),
      p256dh: String(daten?.keys?.p256dh || ''),
      auth: String(daten?.keys?.auth || ''),
    })
    return Boolean(antwort?.aktiv && antwort?.angemeldet)
  } catch {
    return false
  }
}

/**
 * Auf einen AKTIVEN Worker warten.
 *
 * Nach `register()` ist der Worker noch nicht aktiv (`installing`/`waiting`);
 * `pushManager.subscribe()` auf einer solchen Registration scheitert beim
 * ERSTEN Einschalten mit „no active Service Worker“. Deshalb:
 *   1. Ist schon ein aktiver Worker da, sofort zurück.
 *   2. Sonst `navigator.serviceWorker.ready` — es löst auf, sobald im Scope
 *      dieser Seite ein Worker aktiv ist (die Seite liegt im Scope, den wir
 *      beim Registrieren gesetzt haben).
 *   3. Zusätzlich am `statechange` des Workers horchen: meldet eine Quelle
 *      „aktiv“, ist das der verlässlichste Moment.
 * Die Wartezeit ist begrenzt (10 s): ein Worker, der nie aktiv wird, soll
 * nicht den Knopf einfrieren, sondern den Fehlersatz zeigen.
 */
const AKTIV_WARTEN_MS = 10000

function warteAufAktiv(reg) {
  if (reg?.active && reg.active.state === 'activated') return Promise.resolve(reg)
  const sw = swZugang()
  const bereit = sw && typeof sw.ready === 'object' && sw.ready ? sw.ready : null
  // EIN Signal genügt (Review): `ready` ODER `statechange → activated`. Nur
  // vorhandene Signale nehmen am Rennen teil — ein fehlender Kandidat darf das
  // Rennen nicht sofort „gewinnen“.
  const signale = []
  if (bereit) signale.push(bereit.catch(() => null))
  const kandidat = reg?.installing || reg?.waiting
  if (kandidat && typeof kandidat.addEventListener === 'function') {
    signale.push(new Promise((loese) => {
      kandidat.addEventListener('statechange', function () {
        if (kandidat.state === 'activated') loese(null)
      })
    }))
  }
  const fertig = (signale.length ? Promise.race(signale) : Promise.resolve(null)).then(() => null)
  const geduld = new Promise((loese) => {
    umgebung.setTimeout ? umgebung.setTimeout(loese, AKTIV_WARTEN_MS) : loese(null)
  })
  return Promise.race([fertig, geduld]).then(() => bestehendeRegistration())
}

/** Die Registration dieses Browsers (`getRegistration()`), notfalls `null`. */
async function bestehendeRegistration() {
  const sw = swZugang()
  if (!sw || typeof sw.getRegistration !== 'function') return null
  try {
    return await sw.getRegistration()
  } catch {
    return null
  }
}

/** Das Verzeichnis, in dem DIESE Seite liegt — der Geltungsbereich des Workers.
 *
 * `#/einstellungen/…` steht in der Adresszeile hinter `/diakonos` (bzw.
 * `/{Praefix}/diakonos`); der Hash gehört nicht dazu. Der Worker liegt an der
 * Wurzel (`/sw.js`) und darf mit `Service-Worker-Allowed: /` über sein
 * Verzeichnis hinaus bedienen — sein Scope ist deshalb das App-Verzeichnis,
 * genau wie `basePath` es nennt.
 */
function appScope() {
  const praefix = mitBasis('/')
  return `${praefix === '/' ? '' : praefix}/diakonos`
}

/** Den Service Worker holen (Registration ist idempotent). */
async function workerHolen() {
  const sw = swZugang()
  const vorhanden = await sw.getRegistration()
  if (vorhanden) return vorhanden
  return sw.register(mitBasis(SW_PFAD), { scope: appScope() })
}

async function anschalten() {
  // 1. Die Frage des Browsers — ausschließlich hier, nach dem Klick.
  let erlaubnis = String(umgebung.Notification?.permission || '')
  if (erlaubnis !== 'granted') {
    erlaubnis = String(await umgebung.Notification.requestPermission())
  }
  berechtigung.value = erlaubnis
  if (erlaubnis !== 'granted') {
    // Abgelehnt: der Zustand wird zu „verweigert“ und der Satz erklärt den
    // Weg zurück. Kein erneuter Versuch, keine Fehlermeldung.
    if (erlaubnis === 'denied') return
    aktionsFehler.value = PUSH_FEHLER_EIN
    return
  }

  const schluessel = schluesselBytes(oeffentlicherSchluessel.value, umgebung.atob?.bind(umgebung))
  if (!schluessel) {
    aktionsFehler.value = PUSH_FEHLER_EIN
    return
  }

  // 2. Worker holen — und auf seinen AKTIVEN Zustand warten, sonst scheitert
  //    das Abonnieren beim ersten Einschalten (Review R1, Punkt 2).
  const reg = await warteAufAktiv(await workerHolen())
  if (!reg || !reg.pushManager) {
    aktionsFehler.value = PUSH_FEHLER_EIN
    abonniert.value = false
    serverAn.value = false
    return
  }
  const abo = await reg.pushManager.subscribe({
    userVisibleOnly: true,
    applicationServerKey: schluessel,
  })

  // 3. Beim Server anmelden.
  const daten = abo?.toJSON ? abo.toJSON() : abo
  const antwort = await apiCall('diakronos_app.api.push.anmelden', {
    endpoint: String(daten?.endpoint || ''),
    p256dh: String(daten?.keys?.p256dh || ''),
    auth: String(daten?.keys?.auth || ''),
  })
  if (!antwort?.aktiv || !antwort?.angemeldet) {
    // Der Server kennt es nicht: das Abo im Browser wieder verwerfen, damit
    // Schalter und Wirklichkeit dasselbe sagen.
    try { await abo?.unsubscribe?.() } catch { /* egal */ }
    abonniert.value = false
    serverAn.value = false
    aktionsFehler.value = PUSH_FEHLER_EIN
    return
  }
  abonniert.value = true
  serverAn.value = true
}

async function ausschalten() {
  const abo = await bestehendesAbo()
  const endpoint = String((abo?.toJSON ? abo.toJSON() : abo)?.endpoint || '')
  if (abo?.unsubscribe) await abo.unsubscribe()
  abonniert.value = false
  serverAn.value = false
  if (!endpoint) return
  try {
    await apiCall('diakronos_app.api.push.abmelden', { endpoint })
  } catch {
    // Das Gerät ist bereits abgemeldet (der Browser hat das Abonnement
    // verworfen); der Server räumt die Zeile beim nächsten Versand auf.
    aktionsFehler.value = PUSH_FEHLER_AUS
  }
}

async function umschalten(an) {
  if (laeuft.value) return
  laeuft.value = true
  aktionsFehler.value = ''
  try {
    if (an) await anschalten()
    else await ausschalten()
  } catch {
    aktionsFehler.value = an ? PUSH_FEHLER_EIN : PUSH_FEHLER_AUS
    // Ein halb fertiges Abonnement darf den Schalter nicht „an“ zeigen.
    if (an) {
      abonniert.value = false
      serverAn.value = false
    }
  } finally {
    laeuft.value = false
  }
}

onMounted(laden)
</script>

<style scoped>
.bn-abschnitt { display: grid; gap: var(--gap); }
.bn-einleitung,
.bn-ruhig { margin: 0; color: var(--text-muted); font-size: var(--fs-sm); }
.bn-klein { margin: 0; color: var(--text-muted); font-size: var(--fs-sm); }
.bn-schalter { display: grid; gap: var(--sp-2); min-width: 0; }

/* Am Handy (360 px) bricht der Text um, statt seitlich zu scrollen. */
@media (max-width: 720px) {
  .bn-abschnitt { min-width: 0; }
}
</style>
