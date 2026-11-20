<template>
  <div class="sp-abschnitt" role="region" aria-labelledby="sp-titel">
    <h2 id="sp-titel">{{ SPERR_SEITE.titel }}</h2>
    <p class="sp-einleitung">{{ SPERR_EINLEITUNG }}</p>

    <DkSkelett v-if="skelettSichtbar" form="zeilen" :anzahl="3" text="Gesperrte Personen werden geladen" />

    <DkHint v-if="fehler" variant="err" role="alert">{{ fehler }}</DkHint>
    <DkButton v-if="!geladen && !laedt" variant="secondary" @click="laden">Erneut versuchen</DkButton>

    <template v-if="geladen">
      <ul v-if="eintraege.length" class="sp-liste">
        <li v-for="e in eintraege" :key="e.mitglied" class="sp-zeile">
          <img v-if="e.bild" class="sp-bild" :src="e.bild" alt="" aria-hidden="true" />
          <span v-else class="sp-bild sp-bild--leer" aria-hidden="true">{{ kurzname(e.name) }}</span>
          <a class="sp-name" :href="e.href">{{ e.name }}</a>
          <DkButton
            variant="secondary"
            size="sm"
            :loading="laeuft === e.mitglied"
            :aria-label="`Sperre für ${e.name} aufheben`"
            @click="aufheben(e)"
          >{{ AUFHEBEN }}</DkButton>
        </li>
      </ul>
      <p v-else class="sp-leer">{{ SPERR_LEER }}</p>
    </template>
  </div>
</template>

<script setup>
/**
 * CHAT-7b-UI-b — Einstellungen › „Gesperrte Personen“ (Chat-Konzept S3).
 *
 * Die EIGENE Liste der Kontaktsperren: `chat.meine_sperren` (GET) zeigt
 * Mitglied-Kennung, gekürzten Namen und Bild — KEIN Konto/E-Mail (der Server
 * schickt sie nicht). „Aufheben“ ruft `chat.kontakt_entsperren` (POST) und
 * nimmt danach nur die EINE Zeile aus der Liste — kein Neuladen der ganzen
 * Liste, keine Spekulation über fremde Sperren (die andere Seite bleibt
 * gesperrt, wenn SIE gesperrt hat; das ist ihre Entscheidung).
 *
 * Sichtbarkeit: JEDE angemeldete Person sieht diesen Abschnitt — es sind ihre
 * eigenen Daten. Deshalb steht in `pages/Einstellungen.vue` KEINE
 * `verwaltung`-Stufe am Eintrag (die wäre „admin“ oder „personen“ und
 * schlösse genau die Menschen aus, um deren Sperren es geht). Der Server
 * entscheidet ohnehin: `_benutzer()` grenzt `meine_sperren` auf die eigene
 * Kennung ein. ACHTUNG: `Einstellungen` selbst steht in
 * `PERSONEN_VERWALTUNG_PAGES` (Router-Guard) — das ist eine bestehende
 * Eigenschaft der Seite und nicht Teil dieser Karte.
 *
 * Kein Primärknopf: „Aufheben“ ist je Zeile eine Nebenwirkung (UX1h).
 */
import { computed, onMounted, ref } from 'vue'
import { apiCall, apiGet } from '../../composables/useApi.js'
import { useLadeSkelett } from '../../composables/useLadeSkelett.js'
import { fehlertext } from '../../../shared/fehlertexte.js'
import DkButton from '../../components/ui/DkButton.vue'
import DkHint from '../../components/ui/DkHint.vue'
import DkSkelett from '../../components/ui/DkSkelett.vue'
import {
  AUFHEBEN, SPERR_EINLEITUNG, SPERR_FEHLER, SPERR_LEER, SPERR_SEITE, sperrListe,
} from '../../composables/nachrichtenDirekt.mjs'

const laedt = ref(true)
// Platzhalter erst nach 300 ms (kein Blitzen, keine Aussage vor der Antwort).
const { skelettSichtbar } = useLadeSkelett(laedt)
const geladen = ref(false)
const fehler = ref('')
const roh = ref([])
const laeuft = ref('')

const eintraege = computed(() => sperrListe({ sperren: roh.value }))

async function laden() {
  laedt.value = true
  fehler.value = ''
  try {
    // GET, nicht POST: der Server deklariert für meine_sperren nur methods=["GET"].
    const antwort = await apiGet('chat.meine_sperren', {})
    roh.value = Array.isArray(antwort?.sperren) ? antwort.sperren : []
    geladen.value = true
  } catch (err) {
    // Ein 403 heißt hier: die Sitzung darf ihre eigenen Sperren nicht lesen —
    // das ist keine Panne der Seite, sondern eine Auskunft des Servers.
    fehler.value = Number(err?.status) === 403
      ? 'Die Liste ist für dieses Konto nicht abrufbar.'
      : fehlertext(err)
  } finally {
    laedt.value = false
  }
}

/**
 * Eine Sperre aufheben. Die Zeile verschwindet erst, wenn der SERVER sie
 * wirklich gelöscht hat (kein optimistisches Entfernen): eine Zeile, die
 * bleibt, ist die ehrliche Antwort.
 */
async function aufheben(e) {
  if (laeuft.value) return
  laeuft.value = e.mitglied
  fehler.value = ''
  try {
    await apiCall('diakronos_app.api.chat.kontakt_entsperren', { mitglied: e.mitglied })
    roh.value = roh.value.filter((z) => String(z?.mitglied || '').trim() !== e.mitglied)
  } catch (err) {
    fehler.value = Number(err?.status) === 403 ? SPERR_FEHLER : fehlertext(err)
  } finally {
    laeuft.value = ''
  }
}

/** Anfangsbuchstabe als Platzhalter, wenn es kein Bild gibt. */
function kurzname(name) {
  return String(name || '').trim().slice(0, 1).toUpperCase() || '?'
}

onMounted(laden)
</script>

<style scoped>
.sp-abschnitt { display: grid; gap: var(--gap); }
.sp-einleitung,
.sp-leer { margin: 0; color: var(--text-muted); font-size: var(--fs-sm); }
.sp-liste { list-style: none; margin: 0; padding: 0; display: grid; gap: var(--sp-2); }
.sp-zeile {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  min-height: var(--control-h-lg);
  padding: var(--sp-2) 0;
  border-bottom: var(--rahmen-breite) solid var(--line);
}
.sp-zeile:last-child { border-bottom: 0; }
.sp-bild {
  width: var(--icon-lg);
  height: var(--icon-lg);
  flex: none;
  border-radius: 50%;
  object-fit: cover;
  background: var(--surface-2);
}
.sp-bild--leer {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: var(--muted);
  font-size: var(--fs-sm);
  font-weight: var(--fw-mittel);
}
.sp-name {
  flex: 1 1 auto;
  min-width: 0;
  color: var(--text);
  text-decoration: none;
  font-size: var(--fs);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.sp-name:hover { text-decoration: underline; }
.sp-name:focus-visible { outline: var(--rahmen-breite) solid var(--focus-ring); outline-offset: 2px; }

/* Am Handy: Knopf bleibt am Namen, die Zeile bricht nicht in zwei Spalten. */
@media (max-width: 720px) {
  .sp-zeile { flex-wrap: wrap; }
}
</style>
