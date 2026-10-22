<template>
  <DkDialog :model-value="true" :title="titel" size="lg" :close-on-overlay="false" dev
            @update:model-value="schliessen">
    <div class="dk-dm" data-dk-dev>
      <p v-if="bildAufnahmeFehler" class="dk-dm-warnung" role="alert" data-dk-dev>{{ bildAufnahmeFehler }}</p>
      <!-- Element -->
      <div class="dk-dm-zeile">
        <span class="dk-dm-label">Element</span>
        <code class="dk-dm-kontext">{{ elementInfo }}</code>
      </div>

      <!-- Text + Sprache -->
      <label class="dk-dm-feld">
        <span class="dk-dm-label">Was ist passiert? <em>(oder sprechen)</em></span>
        <textarea v-model="text" rows="4" ref="textFeld"
                  placeholder="Kurz beschreiben — was hast du erwartet, was ist passiert?" />
      </label>

      <div class="dk-dm-aktionen">
        <DkButton v-if="sttAn" variant="secondary" size="sm" type="button"
                  @click="aufnahmeUmschalten">
          {{ aufnahmeLaeuft ? 'Aufnahme stoppen' : 'Sprechen (Server)' }}
        </DkButton>
        <DkButton v-else-if="webSpeechAn" variant="secondary" size="sm" type="button"
                  @click="webSpeechUmschalten">
          {{ sprachLaeuft ? 'Erkennung stoppen' : 'Sprechen (Browser)' }}
        </DkButton>
        <span v-if="webSpeechAn && !sttAn" class="dk-dm-hinweis">
          Hinweis: Chrome/Edge/Safari senden die Aufnahme zur Erkennung an Google.
        </span>
        <span v-else-if="!sttAn && !webSpeechAn" class="dk-dm-hinweis">
          Spracheingabe wird von diesem Browser nicht unterstützt — bitte tippen.
        </span>
        <span v-if="aufnahmeLaeuft" class="dk-dm-hinweis">Aufnahme läuft… (Server-Transkription)</span>
      </div>

      <!-- Bilder -->
      <div class="dk-dm-bilder">
        <div v-for="(bild, i) in bilder" :key="i" class="dk-dm-bild">
          <img :src="bild.vorschau" :alt="bild.name || 'Bild'" @mousedown="schwaerzen(i, $event)" />
          <button class="dk-dm-weg" type="button" title="Bild entfernen" @click="bildEntfernen(i)">×</button>
        </div>
        <p v-if="!bilder.length && bildAufnahmeLaeuft" class="dk-dm-hinweis" role="status">
          <span class="dk-dm-spinner" aria-hidden="true" />Screenshot wird erstellt …
        </p>
        <p v-else-if="!bilder.length" class="dk-dm-hinweis">
          Kein Bild — „Aufnehmen“ oder Strg+V.
        </p>
      </div>
      <div class="dk-dm-aktionen">
        <DkButton variant="secondary" size="sm" type="button" :disabled="laeuft" @click="aufnehmen">
          Aufnehmen (DOM)
        </DkButton>
        <DkButton variant="secondary" size="sm" type="button" :disabled="laeuft" @click="bildschirmAufnehmen">
          Bildschirm aufnehmen
        </DkButton>
        <label class="dk-dm-datei">
          <span class="dk-dm-datei-knopf">Datei</span>
          <input type="file" accept="image/png,image/jpeg,image/webp" multiple @change="aufDateiWahl" />
        </label>
        <span class="dk-dm-hinweis" v-if="bildHinweis">{{ bildHinweis }}</span>
      </div>
      <p class="dk-dm-hinweis">Zum Schwärzen: mit gedrückter Maustaste über das Bild ziehen.</p>

      <!-- Einordnung -->
      <div class="dk-dm-zeilen">
        <label class="dk-dm-feld is-klein">
          <span class="dk-dm-label">Art</span>
          <select v-model="art">
            <option value="fehler">Fehler</option>
            <option value="design">Design</option>
            <option value="wunsch">Wunsch</option>
            <option value="frage">Frage</option>
          </select>
        </label>
        <label class="dk-dm-feld is-klein">
          <span class="dk-dm-label">Wichtigkeit</span>
          <select v-model="wichtigkeit">
            <option value="niedrig">niedrig</option>
            <option value="mittel">mittel</option>
            <option value="hoch">hoch</option>
          </select>
        </label>
      </div>

      <details v-if="fehlerumfeld.length" class="dk-dm-umfeld">
        <summary>{{ fehlerumfeld.length }} Fehler im Umfeld (letzte 60 s) — wird mitgespeichert</summary>
        <ul>
          <li v-for="e in fehlerumfeld.slice(0, 8)" :key="e.name">{{ ereignisZeile(e) }}</li>
        </ul>
      </details>

      <p v-if="meldung" class="dk-dm-warnung" role="alert">{{ meldung }}</p>
    </div>

    <template #footer>
      <DkButton variant="ghost" type="button" @click="schliessen">Abbrechen</DkButton>
      <DkButton variant="primary" type="button" :disabled="laeuft" @click="speichern">
        {{ laeuft ? 'Speichern…' : 'Befund speichern' }}
      </DkButton>
    </template>
  </DkDialog>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'

import DkDialog from '../ui/DkDialog.vue'
import DkButton from '../ui/DkButton.vue'
import { elementEtikett, ereignisZeile } from './logik.mjs'
import { AUFNAHME_LIMIT_MS as KALTSTART_LIMIT_MS } from './fotograf.mjs'
import {
  bildschirmAufnehmen as bildschirmAufnehmenRoh, dataUrlGroesse, nimmAuf,
} from './screenshot.mjs'
import {
  blobAlsDataUrl, starteAufnahme, starteWebSpeech, webSpeechVerfuegbar,
} from './sprache.mjs'
import { devmodusApi, fehlerZeilen, sttVerfuegbar } from '../../composables/useDevmodus.js'
import { showToast } from '../../composables/useToast.js'

const props = defineProps({
  element: { type: Object, default: null },
  fehlerumfeld: { type: Array, default: () => [] },
  // DM2/DM3: Bilder, die NEBEN dem Oeffnen des Dialogs aufgenommen wurden
  // (siehe Rahmen.vue) — der Screenshot zeigt so die Seite, nicht den Dialog.
  startbilder: { type: Array, default: () => [] },
  // DM3: Zustand der Hintergrund-Aufnahme (Platzhalter/Spinner bzw. Hinweis).
  bildAufnahmeLaeuft: { type: Boolean, default: false },
  bildAufnahmeFehler: { type: String, default: '' },
})
const emit = defineEmits(['schliessen', 'gespeichert'])

const text = ref('')
const art = ref('fehler')
const wichtigkeit = ref('mittel')
const bilder = ref([])
const audio = ref(null)
const laeuft = ref(false)
const meldung = ref('')
const bildHinweis = ref('')
const textFeld = ref(null)

const titel = computed(() => (props.element ? 'Befund melden' : 'Befund ohne Element'))
const sttAn = computed(() => Boolean(sttVerfuegbar?.value))
const webSpeechAn = computed(() => webSpeechVerfuegbar())
const elementInfo = computed(() => {
  if (!props.element) return '—'
  const e = elementEtikett(props.element)
  return e || String(props.element.tagName || '').toLowerCase()
})

let webSpeech = null
const sprachLaeuft = ref(false)
let aufnahme = null
const aufnahmeLaeuft = ref(false)

// ── Bilder ─────────────────────────────────────────────────────────────────

function bildHinzufuegen(datenUrl, name) {
  bilder.value.push({ vorschau: datenUrl, name, bytes: dataUrlGroesse(datenUrl) })
  if (bilder.value.length > 8) bilder.value = bilder.value.slice(0, 8)
}

const bildEntfernen = (i) => { bilder.value.splice(i, 1) }

/** Schon aufgenommene Bilder eintragen (Startbilder bzw. nachgereichte). */
function startbilderUebernehmen(neu) {
  if (!Array.isArray(neu) || !neu.length) return
  const bekannt = new Set(bilder.value.map(b => b.vorschau))
  for (const bild of neu) {
    const url = bild?.datenUrl || bild?.vorschau
    if (url && !bekannt.has(url)) bildHinzufuegen(url, bild.name)
  }
}

// DM3: Die Aufnahme laeuft im Hintergrund — ihr Ergebnis trifft NACH dem
// Oeffnen ein und wird nachgereicht.
watch(() => props.startbilder, (neu) => startbilderUebernehmen(neu), { deep: true })

async function aufnehmen() {
  bildHinweis.value = ''
  laeuft.value = true
  try {
    const neu = await nimmAuf(props.element)
    if (!neu.length) {
      bildHinweis.value = 'DOM-Rendering nicht verfügbar — bitte „Bildschirm aufnehmen“ nutzen.'
      return
    }
    for (const bild of neu) bildHinzufuegen(bild.datenUrl, bild.name)
  } catch {
    bildHinweis.value = 'Aufnahme fehlgeschlagen — bitte „Bildschirm aufnehmen“ oder Datei wählen.'
  } finally {
    laeuft.value = false
  }
}

/**
 * DM3b: wartet, bis die Hintergrund-Aufnahme fertig ist (Bild da ODER
 * ``bildAufnahmeLaeuft`` wird falsch ODER Zeitlimit). Reicht die Aufnahme ein
 * Bild nach, wird es mitgenommen — so geht das Bild beim schnellen Speichern
 * nicht verloren. ``ms`` deckt den Kaltstart ab (Rahmen-Limit).
 */
function warteAufBild(ms) {
  return new Promise((fertig) => {
    if (!props.bildAufnahmeLaeuft) { fertig(); return }
    const ende = Date.now() + ms
    const schauen = () => {
      if (!props.bildAufnahmeLaeuft || Date.now() >= ende) {
        fertig(); return
      }
      setTimeout(schauen, 80)
    }
    setTimeout(schauen, 80)
  })
}

async function bildschirmAufnehmen() {
  bildHinweis.value = ''
  const daten = await bildschirmAufnehmenRoh()
  if (daten) bildHinzufuegen(daten, 'bildschirm.png')
  else bildHinweis.value = 'Bildschirmaufnahme abgebrochen.'
}

async function aufDateiWahl(ereignis) {
  for (const datei of Array.from(ereignis.target.files || [])) {
    const daten = await new Promise((ok) => {
      const leser = new FileReader()
      leser.onload = () => ok(String(leser.result || ''))
      leser.onerror = () => ok('')
      leser.readAsDataURL(datei)
    })
    if (daten) bildHinzufuegen(daten, datei.name)
  }
  ereignis.target.value = ''
}

async function aufEinfuegen(ereignis) {
  const dateien = [...(ereignis.clipboardData?.items || [])]
    .filter(i => i.type.startsWith('image/')).map(i => i.getAsFile()).filter(Boolean)
  for (const datei of dateien) await aufDateiWahl({ target: { files: [datei], value: '' } })
}

// ── Schwaerzen ─────────────────────────────────────────────────────────────

function schwaerzen(index, ereignis) {
  const bild = bilder.value[index]
  const img = ereignis.target
  const start = { x: ereignis.offsetX, y: ereignis.offsetY }
  const leinwand = document.createElement('canvas')
  leinwand.width = img.naturalWidth
  leinwand.height = img.naturalHeight
  const ctx = leinwand.getContext('2d')
  const basis = new Image()
  basis.onload = () => {
    ctx.drawImage(basis, 0, 0)

    function ziehen(bewegung) {
      const jetzt = { x: bewegung.offsetX, y: bewegung.offsetY }
      const x = Math.min(start.x, jetzt.x) * (img.naturalWidth / img.clientWidth)
      const y = Math.min(start.y, jetzt.y) * (img.naturalHeight / img.clientHeight)
      const w = Math.abs(jetzt.x - start.x) * (img.naturalWidth / img.clientWidth)
      const h = Math.abs(jetzt.y - start.y) * (img.naturalHeight / img.clientHeight)
      ctx.fillStyle = '#000'
      ctx.fillRect(x, y, w, h)
    }
    function loslassen() {
      window.removeEventListener('mousemove', ziehen)
      window.removeEventListener('mouseup', loslassen)
      bild.vorschau = leinwand.toDataURL('image/png')
    }
    window.addEventListener('mousemove', ziehen)
    window.addEventListener('mouseup', loslassen)
  }
  basis.src = bild.vorschau
}

// ── Sprache ────────────────────────────────────────────────────────────────

function webSpeechUmschalten() {
  if (sprachLaeuft.value && webSpeech) { webSpeech.stop(); return }
  webSpeech = starteWebSpeech({
    onText: (t) => { text.value = (text.value ? text.value + ' ' : '') + t },
    onEnde: () => { sprachLaeuft.value = false },
    onFehler: () => { sprachLaeuft.value = false },
  })
  sprachLaeuft.value = Boolean(webSpeech)
}

async function aufnahmeUmschalten() {
  if (aufnahmeLaeuft.value && aufnahme) {
    aufnahmeLaeuft.value = false
    const { blob, typ } = await aufnahme.stoppen()
    aufnahme = null
    await transkribieren(blob, typ)
    return
  }
  aufnahme = await starteAufnahme({ onFehler: () => { meldung.value = 'Kein Mikrofon-Zugriff.' } })
  aufnahmeLaeuft.value = Boolean(aufnahme)
}

async function transkribieren(blob, typ) {
  if (!blob || !blob.size) return
  laeuft.value = true
  try {
    const datenUrl = await blobAlsDataUrl(blob)
    const antwort = await devmodusApi.audioHochladen(datenUrl, typ)
    audio.value = antwort ? { pfad: antwort.pfad, typ: antwort.typ } : null
    // Ohne Server-Endpunkt zur Transkription bleibt die Aufnahme nur als Beleg.
    if (antwort?.text) text.value = (text.value ? text.value + ' ' : '') + antwort.text
    else if (!String(text.value).trim()) meldung.value = 'Aufnahme gespeichert — bitte Text kurz ergänzen.'
  } catch (f) {
    meldung.value = fehlerZeilen(f).join(' | ')
  } finally {
    laeuft.value = false
  }
}

// ── Speichern ──────────────────────────────────────────────────────────────

async function speichern() {
  // UXM-R13: Befund ohne Text ist nur mit Bild/Sprache sinnvoll; sonst
  // ergibt die Liste lauter gleichlautende Titel.
  if (!String(text.value).trim() && !bilder.value.length && !audio.value
      && !props.bildAufnahmeLaeuft) {
    meldung.value = 'Bitte einen Kommentar schreiben, sprechen oder ein Bild aufnehmen.'
    textFeld.value?.focus?.()
    return
  }
  if (!String(text.value).trim() && !audio.value) {
    meldung.value = 'Bitte kurz beschreiben, was passiert ist — das Bild allein sagt nicht, was du erwartet hast.'
    textFeld.value?.focus?.()
    return
  }
  laeuft.value = true
  meldung.value = ''
  // DM3b: Laeuft die Hintergrund-Aufnahme noch, warten WIR auf ihr Ergebnis
  // (sichtbarer Hinweis, Deckel = Kaltstart-Dauer). Danach ist das Bild sicher
  // dabei — beim schnellen Speichern geht es nicht mehr verloren.
  if (props.bildAufnahmeLaeuft && !bilder.value.length) {
    meldung.value = 'Screenshot wird noch erstellt … bitte einen Moment.'
    await warteAufBild(KALTSTART_LIMIT_MS)
    meldung.value = ''
  }
  try {
    // Bild-Liste vor dem Hochladen einfrieren: das watch kann waehrend des
    // Uploads nichts mehr anhaengen (Race in der Review-Anmerkung).
    const zuLaden = bilder.value.slice()
    const pfade = []
    for (const bild of zuLaden) {
      const antwort = await devmodusApi.bildHochladen(bild.vorschau, 'image/png')
      if (antwort?.pfad) pfade.push({ pfad: antwort.pfad })
    }
    await devmodusApi.befundSpeichern({
      text: text.value,
      art: art.value,
      wichtigkeit: wichtigkeit.value,
      url: window.location.href,
      route: window.location.hash,
      seitentitel: document.title,
      seite: props.element ? elementEtikett(props.element) : document.title,
      viewport: `${window.innerWidth}x${window.innerHeight}`,
      bildschirm: `${window.screen.width}x${window.screen.height}`,
      geraet: navigator.platform || '',
      browser: navigator.userAgent,
      theme: document.documentElement.getAttribute('data-theme') || themeAusSpeicher(),
      sprache: navigator.language || '',
      element: elementKontext(props.element),
      bilder: pfade,
      audio: audio.value,
    })
    showToast('Befund gespeichert', 'success')
    emit('gespeichert')
  } catch (f) {
    meldung.value = fehlerZeilen(f).join(' | ')
  } finally {
    laeuft.value = false
  }
}

function themeAusSpeicher() {
  try { return localStorage.getItem('dk-theme') || 'hell' } catch { return 'hell' }
}

// elementKontext wird dynamisch geholt, damit die Logik im .mjs bleibt.
let elementKontext = () => ({})
onMounted(async () => {
  const modul = await import('./logik.mjs')
  elementKontext = modul.elementKontext
  window.addEventListener('paste', aufEinfuegen)
  // DM2/DM3: Schon vorhandene Bilder kommen aus Rahmen.vue (Aufnahme laeuft
  // im Hintergrund und reicht ggf. spaeter nach — siehe watch oben).
  startbilderUebernehmen(props.startbilder)
  textFeld.value?.focus?.()
})
onUnmounted(() => {
  window.removeEventListener('paste', aufEinfuegen)
  if (webSpeech) webSpeech.stop()
})

function schliessen() { emit('schliessen') }
</script>

<style scoped>
.dk-dm { display: flex; flex-direction: column; gap: var(--sp-3); font-size: var(--fs); }
.dk-dm-zeile { display: flex; gap: var(--sp-2); align-items: baseline; flex-wrap: wrap; }
.dk-dm-label { color: var(--muted); }
.dk-dm-label em { font-style: normal; font-size: var(--fs-sm); }
.dk-dm-kontext { font-family: ui-monospace, monospace; overflow-wrap: anywhere; }
.dk-dm-feld { display: flex; flex-direction: column; gap: var(--sp-1); min-width: 0; }
.dk-dm-feld textarea, .dk-dm-feld select {
  font: inherit; padding: 7px; border-radius: var(--radius-sm);
  border: 1px solid var(--line); background: var(--surface); color: var(--text);
  width: 100%; min-width: 0;
}
.dk-dm-zeilen { display: flex; gap: var(--sp-3); flex-wrap: wrap; }
.dk-dm-feld.is-klein { flex: 1 1 140px; }
/* Eine Zeile, die bei Platznot umbricht — statt gequetschter Knoepfe. */
.dk-dm-aktionen { display: flex; gap: var(--sp-2); align-items: center; flex-wrap: wrap; }
.dk-dm-datei { display: inline-flex; }
.dk-dm-datei input { display: none; }
.dk-dm-datei-knopf {
  display: inline-flex; align-items: center; height: 28px; padding: 0 10px;
  border: 1px solid var(--line); border-radius: var(--radius);
  background: var(--surface); color: var(--text); font-size: var(--fs-sm);
  font-weight: 550; cursor: pointer; white-space: nowrap;
}
.dk-dm-datei-knopf:hover { background: var(--surface-hover); border-color: var(--line-strong); }
.dk-dm-bilder { display: flex; flex-wrap: wrap; gap: var(--sp-2); }
.dk-dm-bild { position: relative; }
.dk-dm-bild img {
  max-width: 180px; max-height: 140px; border: 1px solid var(--line);
  border-radius: var(--radius-sm); cursor: crosshair; display: block;
}
.dk-dm-weg {
  position: absolute; top: -8px; right: -8px; width: 20px; height: 20px; line-height: 1;
  border-radius: 50%; border: 1px solid var(--line); background: var(--surface);
  cursor: pointer; color: var(--text);
}
.dk-dm-hinweis { color: var(--muted); font-size: var(--fs-xs); margin: 0; }
.dk-dm-spinner {
  display: inline-block; width: 12px; height: 12px; vertical-align: -1px;
  margin-right: 6px; border: 2px solid var(--line); border-top-color: var(--primary);
  border-radius: 50%; animation: dk-dm-dreh 0.8s linear infinite;
}
@keyframes dk-dm-dreh { to { transform: rotate(360deg); } }
.dk-dm-umfeld summary { cursor: pointer; color: var(--muted); font-size: var(--fs-sm); }
.dk-dm-umfeld ul { margin: var(--sp-1) 0 0; padding-left: 18px; font-size: var(--fs-sm); }
.dk-dm-warnung { color: var(--err); margin: 0; }

/* Mobil: volle Breite, nichts laeuft ueber den Rand (Befund 3). */
@media (max-width: 600px) {
  .dk-dm-aktionen { gap: var(--sp-1); }
  .dk-dm-aktionen :deep(.dk-ui-btn) { flex: 1 1 auto; }
  .dk-dm-feld.is-klein { flex: 1 1 100%; }
}
</style>
