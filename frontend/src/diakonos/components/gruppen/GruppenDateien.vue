<template>
  <!-- DATEIEN-4 — der Inhalt der Karte „Dateien“ auf der Gruppenseite.

       Der Baustein bringt KEINE eigene Karte mit: die Gruppenseite stellt sie
       (wie bei „Rollen der Gruppe“ und „Kalender der Gruppe“) und gibt den
       Hinweis für den Kartenkopf über `@hinweis` weiter.

       Alles Sichtbare kommt aus der Serverantwort von `dateien.liste`:
         · Kopf: `darf_hochladen`, `darf_anpinnen`, `max_bytes`
         · je Zeile: `darf_anpinnen`, `darf_bearbeiten`, `eigene`, `angepinnt`
       Die Oberfläche entscheidet nichts selbst — sie blendet nur aus, was der
       Server ohnehin verweigert (fehlt ein Feld, gibt es keinen Knopf). -->
  <div class="gd-wurzel">
    <!-- ERST die erste Antwort, dann Inhalt oder Leerzustand: vorher blitzte
         „Noch keine Dateien“ auch dann auf, wenn es Dateien gibt. Das Skelett
         erscheint erst, wenn das Laden merklich dauert (`useLadeSkelett`). -->
    <DkSkelett v-if="skelettSichtbar" form="zeilen" :anzahl="3" text="Dateien werden geladen …" />

    <!-- ux2d3a: kein Ladeprosatext als Satz im Bild — der ruhige Ladezustand
         zeigt die Form (Spinner), der Vorleser bekommt die Auskunft über
         `aria-label`. -->
    <p v-else-if="!antwortDa" class="gd-leise" role="status" aria-label="Dateien dieser Gruppe">
      <DkSpinner />
    </p>

    <template v-else>
      <DkHint v-if="fehler" variant="err">{{ fehler }}</DkHint>

      <!-- Hochladen: nur wenn der KOPF der Liste es erlaubt (F9, `max_bytes`). -->
      <div v-if="kopf.darfHochladen" class="gd-hochladen">
        <label class="gd-hochladen-knopf" :class="{ 'is-laeuft': laeuftUpload }">
          <input
            ref="dateifeld"
            type="file"
            class="gd-dateifeld"
            :disabled="laeuftUpload"
            aria-label="Datei zum Hochladen auswählen"
            @change="dateiGewaehlt"
          />
          <span class="gd-hochladen-text">
            {{ laeuftUpload ? TEXTE.hochladenLaeuft : TEXTE.hochladen }}
          </span>
        </label>
        <span v-if="kopf.maxBytes !== null" class="gd-leise">
          Höchstens {{ mbText(kopf.maxBytes) }} je Datei.
        </span>
      </div>
      <p v-if="uploadHinweis" class="gd-upload-hinweis" role="alert">{{ uploadHinweis }}</p>

      <DkEmpty v-if="zeilen.length === 0" :title="TEXTE.leer" :text="TEXTE.leerText" />

      <ul v-else class="gd-liste" data-dateiliste>
        <li
          v-for="z in zeilen"
          :key="z.name"
          class="gd-zeile"
          :class="{ 'is-angepinnt': z.angepinnt }"
          :data-datei="z.name"
        >
          <!-- Symbol als Kennzeichen der Zeile (Bild/Ton/Datei) — Deko, der
               Name darunter ist der sichtbare Text. -->
          <span class="gd-symbol" aria-hidden="true">
            <DkSymbol :name="symbolFuer(z)" :groesse="18" />
          </span>

          <div class="gd-haupt">
            <span class="gd-name" :title="z.dateiname">{{ z.dateiname }}</span>
            <span class="gd-meta">
              <DkBadge v-if="z.angepinnt" variant="warn">{{ TEXTE.angepinnt }}</DkBadge>
              <span v-if="z.groesseText">{{ z.groesseText }}</span>
              <span v-if="z.eigene" class="gd-eigene">{{ TEXTE.eigene }}</span>
            </span>
          </div>

          <!-- Öffnen (R1, Punkt 6): nur Bilder — der Browser zeigt sie in
               einem eigenen Reiter, ohne Download. Der Ausliefer-Endpunkt
               prüft auch hier LESEN (jede Fehlerart ist dieselbe 404). -->
          <a
            v-if="istBild(z)"
            class="gd-laden"
            :href="urlFuer(z)"
            target="_blank"
            rel="noopener"
            :aria-label="`${TEXTE.oeffnen}: ${z.dateiname}`"
            :title="TEXTE.oeffnen"
          ><DkSymbol name="bild" :groesse="16" /></a>

          <!-- Herunterladen: ein echter Link auf den Ausliefer-Endpunkt
               (dort wird LESEN geprüft; jede Fehlerart ist dieselbe 404). -->
          <a
            class="gd-laden"
            :href="urlFuer(z)"
            :download="z.dateiname"
            :aria-label="`${TEXTE.herunterladen}: ${z.dateiname}`"
            :title="TEXTE.herunterladen"
          ><DkSymbol name="herunterladen" :groesse="16" /></a>

          <DkAktionen
            v-if="aktionenFuerZeile(z).length > 1"
            :eintraege="eintraegeFuer(z)"
            :label="`Weitere Aktionen für „${z.dateiname}“`"
          />
        </li>
      </ul>

      <!-- Papierkorb: erscheint nur, wenn der Server Daten liefert (F5 —
           nur wer dort aufräumen darf, bekommt überhaupt eine Antwort). -->
      <div v-if="papierkorb !== null" class="gd-papierkorb" data-papierkorb>
        <DkButton
          variant="ghost"
          size="sm"
          :aria-expanded="papierkorbOffen ? 'true' : 'false'"
          @click="papierkorbUmschalten"
        >{{ TEXTE.papierkorb }} ({{ papierkorb.length }})</DkButton>

        <template v-if="papierkorbOffen">
          <DkEmpty v-if="papierkorb.length === 0" :title="TEXTE.papierkorbLeer" :text="TEXTE.papierkorbLeerText" />
          <ul v-else class="gd-liste" data-papierkorbliste>
            <li v-for="p in papierkorb" :key="p.name" class="gd-zeile" :data-datei="p.name">
              <span class="gd-symbol" aria-hidden="true"><DkSymbol name="datei" :groesse="18" /></span>
              <div class="gd-haupt">
                <span class="gd-name" :title="p.dateiname">{{ p.dateiname }}</span>
                <span class="gd-meta">
                  <span v-if="p.groesseText">{{ p.groesseText }}</span>
                  <span v-if="p.endeText" class="gd-ende">{{ p.endeText }}</span>
                </span>
              </div>
              <DkButton variant="ghost" size="sm" @click="wiederherstellen(p)">
                {{ TEXTE.wiederherstellen }}
              </DkButton>
            </li>
          </ul>
        </template>
      </div>
    </template>

    <!-- Umbenennen: eigener Dialog (kein `window.prompt`). Der Server bereinigt
         den Namen und weist gesperrte Endungen ab — seine Meldung steht hier. -->
    <DkDialog v-model="umbenennenOffen" title="Datei umbenennen" size="sm">
      <form id="gd-umbenennen" class="gd-formular" novalidate @submit.prevent="umbenennenSpeichern">
        <DkField label="Dateiname" required :error="umbenennenFehler">
          <input v-model="umbenennenWert" class="dk-ui-eingabe" type="text" :maxlength="NAME_MAX" />
        </DkField>
      </form>
      <template #footer>
        <DkButton variant="ghost" @click="umbenennenOffen = false">Abbrechen</DkButton>
        <DkButton variant="primary" @click="umbenennenSpeichern">Speichern</DkButton>
      </template>
    </DkDialog>
  </div>
</template>

<script setup>
/**
 * GruppenDateien — Liste, Hochladen, Pin/Umbenennen/Löschen und Papierkorb
 * der Gruppendateien einer (Unter-)Gruppe (DATEIEN-4).
 *
 * Aufrufe (Endpunkte und Feldnamen aus `api/dateien.py`, nichts erfunden):
 *   dateien.liste(gruppe, untergruppe)          — Liste + Kopf + Rechte je Zeile
 *   dateien.hochladen(gruppe, untergruppe, datei=<Multipart>)
 *   dateien.anpinnen(name, an)
 *   dateien.umbenennen(name, dateiname)
 *   dateien.loeschen(name) / dateien.wiederherstellen(name)
 *   dateien.papierkorb(gruppe, untergruppe)     — nur MODERIEREN (403 sonst)
 *   dateien.datei(name)                         — Ausliefern (Link, GET)
 *
 * Die Regeln (welche Aktion wann, welcher Text, Papierkorb-Frist) stehen in
 * `gruppenDateien.mjs` — hier wird nur gezeichnet. Löschen geht IMMER über
 * die Rückfrage (F4), nie über `confirm()`.
 */
import { computed, onMounted, ref, watch } from 'vue'
import { apiCall, apiAntwortPruefen, apiUrl } from '../../composables/useApi.js'
import { showToast } from '../../composables/useToast.js'
import { bestaetigen } from '../../composables/useBestaetigen.js'
import { useLadeSkelett } from '../../composables/useLadeSkelett.js'
import { aktionsfehler } from '../../../shared/fehlertexte.js'
import DkButton from '../ui/DkButton.vue'
import DkBadge from '../ui/DkBadge.vue'
import DkEmpty from '../ui/DkEmpty.vue'
import DkHint from '../ui/DkHint.vue'
import DkSkelett from '../ui/DkSkelett.vue'
import DkSpinner from '../ui/DkSpinner.vue'
import DkDialog from '../ui/DkDialog.vue'
import DkField from '../ui/DkField.vue'
import DkSymbol from '../ui/DkSymbol.vue'
import DkAktionen from '../ui/DkAktionen.vue'
import {
  NAME_MAX,
  PFADE,
  TEXTE,
  aktionenFuerZeile,
  kopfAus,
  zeilenAus,
  papierkorbZeilen,
  loeschRueckfrage,
  uploadHindernis,
  mbText,
} from './gruppenDateien.mjs'

const props = defineProps({
  /** Kennung der HAUPTgruppe (auf einer Untergruppen-Seite: der Obergruppe). */
  gruppe: { type: String, required: true },
  /** Kennung dieser Untergruppe (leer auf einer Gruppenseite — F3: eigene Dateien). */
  untergruppe: { type: String, default: '' },
})

const emit = defineEmits(['hinweis'])

const rohdaten = ref(null)
const papierkorbRoh = ref(null)
const fehler = ref('')
const laedt = ref(true)
const { skelettSichtbar } = useLadeSkelett(laedt)
const laeuftUpload = ref(false)
const uploadHinweis = ref('')
const dateifeld = ref(null)
const papierkorbOffen = ref(false)
// Umbenennen: eigener Dialog statt `window.prompt` (DES: keine Browser-Felder).
const umbenennenOffen = ref(false)
const umbenennenZiel = ref(null)
const umbenennenWert = ref('')
const umbenennenFehler = ref('')
/** Laufzähler: ein Wechsel der (Unter-)Gruppe entwertet unterwegs befindliche Antworten. */
let ladeNr = 0
/** War schon einmal eine Liste da? (dann ist jedes Nachladen STILL) */
let geladenEinmal = false

const antwortDa = computed(() => rohdaten.value !== null)
const kopf = computed(() => kopfAus(rohdaten.value))
const zeilen = computed(() => zeilenAus(rohdaten.value))
const papierkorb = computed(() => (papierkorbRoh.value === null
  ? null
  : papierkorbZeilen(papierkorbRoh.value)))

/** Der Raum als Parameter — Untergruppe nur, wenn es eine gibt. */
function raum() {
  const p = { gruppe: props.gruppe }
  if (props.untergruppe) p.untergruppe = props.untergruppe
  return p
}

/** Adresse der Auslieferung über die EINE Basis-Quelle (`apiUrl`). */
function urlFuer(z) {
  const pfad = String(apiUrl(PFADE.datei) || '')
  if (!pfad || !z?.name) return ''
  return `${pfad}?name=${encodeURIComponent(z.name)}`
}

/** Ist das ein Bild (nur nach dem GEPRÜFTEN MIME-Typ — nie am Namen)? */
function istBild(z) {
  return String(z?.mime || '').toLowerCase().startsWith('image/')
}

/** Symbol der Zeile aus dem geprüften MIME-Typ (nie am Dateinamen geraten). */
function symbolFuer(z) {
  const mime = String(z?.mime || '').toLowerCase()
  if (mime.startsWith('image/')) return 'bild'
  if (mime.startsWith('audio/')) return 'ton'
  return 'datei'
}

function eintraegeFuer(z) {
  const bauen = {
    umbenennen: () => umbenennen(z),
    anpinnen: () => pinUmschalten(z),
    loeschen: () => loeschen(z),
  }
  return aktionenFuerZeile(z)
    .filter((e) => bauen[e.key])
    .map((e) => ({ ...e, aktion: bauen[e.key] }))
}

/** Nach jeder Änderung: Liste still nachziehen (Inhalt bleibt stehen). */
async function nachladen() {
  await laden({ still: true })
}

async function laden({ still = false } = {}) {
  const nr = ++ladeNr
  const veraltet = () => nr !== ladeNr
  if (!still) {
    if (!geladenEinmal) laedt.value = true
    fehler.value = ''
  }
  try {
    const daten = await apiCall(PFADE.liste, raum())
    if (veraltet()) return
    rohdaten.value = daten
    geladenEinmal = true
  } catch (e) {
    if (veraltet()) return
    if (!still) rohdaten.value = null
    fehler.value = aktionsfehler('laden', e)
    return
  } finally {
    if (!veraltet()) laedt.value = false
  }
  // Papierkorb ist eine EIGENE Frage: ein 403 heißt hier „für dich nichts zu
  // räumen“ — dann gibt es die Ansicht gar nicht (keine Fehlermeldung).
  try {
    const korb = await apiCall(PFADE.papierkorb, raum())
    if (veraltet()) return
    papierkorbRoh.value = korb
  } catch {
    if (veraltet()) return
    papierkorbRoh.value = null
  }
}

// ── Hochladen ─────────────────────────────────────────────────────────────

function dateiGewaehlt(ereignis) {
  const datei = ereignis?.target?.files?.[0]
  // Das Feld leeren, damit dieselbe Datei erneut wählbar ist.
  if (ereignis?.target) ereignis.target.value = ''
  if (!datei) return
  const hindernis = uploadHindernis(datei, kopf.value.maxBytes)
  if (hindernis) {
    uploadHinweis.value = hindernis
    return
  }
  hochladen(datei)
}

/**
 * Multipart-Upload über rohes `fetch` (wie `ChatAnhangChips` in `Nachrichten.vue`):
 * `apiCall` erzwingt JSON, eine Datei ist Multipart. Sitzungs- und
 * CSRF-Prüfung kommen trotzdem von der EINEN Stelle (`apiAntwortPruefen`) —
 * die Anfrage wird als Funktion übergeben, damit eine CSRF-Ablehnung mit
 * frischem Token genau EINMAL wiederholt werden kann.
 */
async function hochladen(datei) {
  if (laeuftUpload.value) return
  uploadHinweis.value = ''
  laeuftUpload.value = true
  const nummer = ladeNr
  const anfrage = () => {
    const form = new FormData()
    for (const [feld, wert] of Object.entries(raum())) form.append(feld, String(wert))
    form.append('datei', datei, String(datei?.name || 'datei'))
    return fetch(apiUrl(PFADE.hochladen), {
      method: 'POST',
      headers: { 'X-Frappe-CSRF-Token': window.__DIakonosBOOT?.csrf_token || '' },
      body: form,
    })
  }
  try {
    const erste = await anfrage()
    const daten = await apiAntwortPruefen(erste, { anfrage })
    const res = daten?.dkAntwort || erste
    if (!res.ok || daten?.exc) {
      throw new Error(daten?.message || daten?.exception || `HTTP ${res.status}`)
    }
    const antwort = daten?.message
    if (antwort && typeof antwort === 'object' && antwort.success === false) {
      throw new Error(antwort.message || aktionsfehler('hochladen', antwort))
    }
    if (nummer !== ladeNr) return
    showToast(`„${datei.name}“ hochgeladen`, 'success')
    await nachladen()
  } catch (e) {
    if (nummer !== ladeNr) return
    uploadHinweis.value = e?.message || aktionsfehler('hochladen', e)
  } finally {
    laeuftUpload.value = false
  }
}

// ── Anpinnen, Umbenennen, Löschen ─────────────────────────────────────────

async function pinUmschalten(z) {
  const an = !z.angepinnt
  try {
    const res = await apiCall(PFADE.anpinnen, { name: z.name, an })
    if (res?.success) {
      showToast(an ? 'Angepinnt' : 'Pin gelöst', 'success')
      await nachladen()
    } else {
      showToast(aktionsfehler('speichern', res), 'error')
    }
  } catch (e) {
    showToast(aktionsfehler('speichern', e), 'error')
  }
}

async function umbenennen(z) {
  umbenennenZiel.value = z
  umbenennenWert.value = z.dateiname
  umbenennenFehler.value = ''
  umbenennenOffen.value = true
}

async function umbenennenSpeichern() {
  const z = umbenennenZiel.value
  const name = String(umbenennenWert.value || '').trim()
  if (!z) return
  if (!name) {
    umbenennenFehler.value = 'Bitte einen Dateinamen angeben.'
    return
  }
  umbenennenFehler.value = ''
  try {
    const res = await apiCall(PFADE.umbenennen, { name: z.name, dateiname: name })
    if (res?.success) {
      umbenennenOffen.value = false
      showToast('Umbenannt', 'success')
      await nachladen()
    } else {
      umbenennenFehler.value = res?.message || aktionsfehler('speichern', res)
    }
  } catch (e) {
    umbenennenFehler.value = e?.message || aktionsfehler('speichern', e)
  }
}

async function loeschen(z) {
  const frage = loeschRueckfrage(z)
  if (!frage.ja) return
  const ok = await bestaetigen({
    titel: frage.titel,
    text: frage.text,
    aktion: frage.aktion,
    gefahr: true,
  })
  if (!ok) return
  try {
    const res = await apiCall(PFADE.loeschen, { name: z.name })
    if (res?.success) {
      showToast('In den Papierkorb gelegt')
      await nachladen()
    } else {
      showToast(aktionsfehler('loeschen', res), 'error')
    }
  } catch (e) {
    showToast(aktionsfehler('loeschen', e), 'error')
  }
}

// ── Papierkorb ────────────────────────────────────────────────────────────

function papierkorbUmschalten() {
  papierkorbOffen.value = !papierkorbOffen.value
}

async function wiederherstellen(p) {
  try {
    const res = await apiCall(PFADE.wiederherstellen, { name: p.name })
    if (res?.success) {
      showToast('Wiederhergestellt', 'success')
      await nachladen()
    } else {
      showToast(aktionsfehler('speichern', res), 'error')
    }
  } catch (e) {
    showToast(aktionsfehler('speichern', e), 'error')
  }
}

// ── Hinweis für den Kartenkopf + Laden ────────────────────────────────────

const hinweis = computed(() => {
  if (!antwortDa.value) return 'Dateien dieser Gruppe.'
  const n = zeilen.value.length
  const was = n === 1 ? '1 Datei' : `${n} Dateien`
  return n === 0 ? 'Dateien dieser Gruppe.' : `${was} in dieser Gruppe.`
})
watch(hinweis, (wert) => emit('hinweis', wert), { immediate: true })

onMounted(() => laden())
watch(() => [props.gruppe, props.untergruppe], () => {
  rohdaten.value = null
  papierkorbRoh.value = null
  papierkorbOffen.value = false
  laden()
})

defineExpose({ laden, nachladen })
</script>

<style scoped>
.gd-wurzel { display: flex; flex-direction: column; gap: var(--sp-3); min-width: 0; }
.gd-leise {
  display: inline-flex;
  align-items: center;
  gap: var(--sp-2);
  margin: 0;
  color: var(--muted);
  font-size: var(--fs-sm);
}

/* Hochladen: EIN sichtbarer Knopf — das Dateifeld selbst ist unsichtbar,
   aber über die Beschriftung mit der Tastatur erreichbar. */
.gd-hochladen { display: flex; align-items: center; gap: var(--sp-3); flex-wrap: wrap; }
.gd-hochladen-knopf {
  position: relative;
  display: inline-flex;
  align-items: center;
  min-height: var(--control-h);
  padding: 0 var(--sp-3);
  border: var(--rahmen-breite) solid var(--rahmen-farbe);
  border-radius: var(--radius);
  background: var(--surface-2);
  color: var(--text);
  font-size: var(--fs-sm);
  cursor: pointer;
}
.gd-hochladen-knopf:hover { background: var(--surface-hover); }
/* R1 (4): das Dateifeld selbst ist unsichtbar — der Fokus muss an seiner
   Beschriftung sichtbar sein (sonst tastet man blind). */
.gd-hochladen-knopf:focus-within {
  outline: var(--ring-breite) solid var(--focus-ring);
  outline-offset: var(--sp-1);
}
.gd-hochladen-knopf.is-laeuft { opacity: .6; cursor: progress; }
.gd-dateifeld {
  position: absolute;
  inset: 0;
  width: 100%;
  opacity: 0;
  cursor: pointer;
}
.gd-dateifeld:disabled { cursor: progress; }
.gd-upload-hinweis { margin: 0; color: var(--err); font-size: var(--fs-sm); }
.gd-formular { display: flex; flex-direction: column; gap: var(--sp-3); }

.gd-liste { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: var(--sp-2); }
.gd-zeile {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  padding: var(--sp-2) 0;
  border-bottom: var(--rahmen-breite) solid var(--rahmen-farbe);
  min-width: 0;
}
.gd-zeile:last-child { border-bottom: none; }
.gd-symbol { display: inline-flex; color: var(--muted); flex: none; }
.gd-haupt { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: var(--sp-1); }
.gd-name { color: var(--text); font-size: var(--fs-sm); overflow-wrap: anywhere; }
.gd-meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--sp-2);
  color: var(--muted);
  font-size: var(--fs-xs);
}
.gd-eigene { color: var(--muted); }
.gd-ende { color: var(--warn); }
.gd-laden {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: var(--control-h);
  height: var(--control-h);
  border-radius: var(--radius);
  color: var(--primary);
  flex: none;
}
.gd-laden:hover { background: var(--surface-hover); }

.gd-papierkorb {
  margin-top: var(--sp-2);
  padding-top: var(--sp-3);
  border-top: var(--rahmen-breite) solid var(--rahmen-farbe);
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
}
</style>
