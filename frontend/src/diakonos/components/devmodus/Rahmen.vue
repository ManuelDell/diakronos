<template>
  <!-- Dev-Modus (DM1): 4 px roter Rahmen um das GESAMTE Browserfenster.
       position: fixed, pointer-events: none, oberste Ebene — beruehrt kein
       Layout. Das Etikett/der Knopf sind davon ausgenommen.
       DM3: data-dk-dev kennzeichnet Dev-Elemente fuer den Bild-Ausschluss. -->
  <div class="dk-dev-rahmen" data-dk-dev aria-hidden="true" />
  <div class="dk-dev-ecke" data-dk-dev>
    <span class="dk-dev-etikett" data-dk-dev>DEV</span>
    <span class="dk-dev-taste" data-dk-dev>{{ kuerzel }}</span>
    <button class="dk-dev-knopf" data-dk-dev type="button" :aria-pressed="auswahlAktiv"
            :title="'Element auswählen (' + kuerzel + ')'" @click="auswahlUmschalten">
      {{ auswahlAktiv ? 'Abbrechen' : 'Element wählen' }}
    </button>
    <button class="dk-dev-knopf is-aus" data-dk-dev type="button" title="Dev-Modus ausschalten"
            @click="ausschalten">aus</button>
  </div>

  <!-- Hervorhebung des Elements unter dem Mauszeiger -->
  <div v-if="auswahlAktiv && zielRect" class="dk-dev-umriss" data-dk-dev
       :style="umrissStil" aria-hidden="true">
    <span class="dk-dev-ziel" data-dk-dev>{{ zielEtikett }}</span>
  </div>

  <BefundDialog v-if="dialogOffen" :element="gewaehltesElement" :fehlerumfeld="fehlerumfeld"
                :bild-aufnahme-laeuft="aufnahmeLaeuft" :bild-aufnahme-fehler="aufnahmeFehler"
                :startbilder="startbilder" @schliessen="dialogSchliessen" @gespeichert="nachSpeichern" />
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'

import BefundDialog from './BefundDialog.vue'
import {
  elementUnterPunkt, elementEtikett, kuerzelPasst, positionVon, wechsleElement,
} from './logik.mjs'
import { nimmAuf, ladeRenderer, fontCssSammeln, vorwaermen } from './screenshot.mjs'
import { AUFNAHME_LIMIT_MS } from './fotograf.mjs'
import { devmodusApi, devmodusKuerzel, zustandSetzen } from '../../composables/useDevmodus.js'

const auswahlAktiv = ref(false)
const dialogOffen = ref(false)
const gewaehltesElement = ref(null)
const hoverElement = ref(null)
const fehlerumfeld = ref([])
// DM2: Die Bilder entstehen NEBEN dem Befund-Dialog (siehe onClick) und
// werden in den Dialog gereicht. So zeigt der Screenshot die Seite, nicht
// das Befund-Fenster.
const startbilder = ref([])
// DM3: Der Dialog oeffnet SOFORT; die Aufnahme laeuft im Hintergrund und
// meldet ihren Zustand an den Dialog (Platzhalter/Spinner, spaeter Bild).
const aufnahmeLaeuft = ref(false)
const aufnahmeFehler = ref('')
let aufnahmeLauf = 0
const kuerzel = computed(() => devmodusKuerzel.value || 'Strg+Shift+F')

// Eigene Overlay-Elemente sind NIE waehlbar.
function overlayKnoten() {
  return [...document.querySelectorAll('[data-dk-dev]')]
}

const zielRect = computed(() => (hoverElement.value ? positionVon(hoverElement.value) : null))
const zielEtikett = computed(() => elementEtikett(hoverElement.value))
const umrissStil = computed(() => {
  const r = zielRect.value
  if (!r) return {}
  return { left: r.x + 'px', top: r.y + 'px', width: r.breite + 'px', height: r.hoehe + 'px' }
})

function auswahlUmschalten() {
  auswahlAktiv.value = !auswahlAktiv.value
  if (auswahlAktiv.value) {
    document.documentElement.style.cursor = 'crosshair'
    ladeFehlerumfeld()
  } else {
    document.documentElement.style.cursor = ''
    hoverElement.value = null
  }
}

function auswahlBeenden() {
  auswahlAktiv.value = false
  document.documentElement.style.cursor = ''
  hoverElement.value = null
}

async function ladeFehlerumfeld() {
  try {
    const daten = await devmodusApi.ereignisse(60)
    fehlerumfeld.value = daten?.ereignisse || []
  } catch { fehlerumfeld.value = [] }
}

// ── Ereignisse ─────────────────────────────────────────────────────────────

function onKeydown(e) {
  if (e.key === 'Escape' && auswahlAktiv.value) {
    e.preventDefault(); e.stopPropagation()
    auswahlBeenden()
    return
  }
  if (kuerzelPasst(e)) {
    e.preventDefault(); e.stopPropagation()
    auswahlUmschalten()
    return
  }
  if (!auswahlAktiv.value) return
  if (e.key === 'ArrowUp') { e.preventDefault(); wechsle('eltern') }
  if (e.key === 'ArrowDown') { e.preventDefault(); wechsle('kind') }
}

function wechsle(richtung) {
  const start = hoverElement.value || elementUnterPunkt(
    Math.round(innerWidth / 2), Math.round(innerHeight / 2), overlayKnoten())
  hoverElement.value = wechsleElement(start, richtung, overlayKnoten())
}

function onMaus(event) {
  if (!auswahlAktiv.value) return
  hoverElement.value = elementUnterPunkt(event.clientX, event.clientY, overlayKnoten())
}

function onRad(event) {
  if (!auswahlAktiv.value) return
  event.preventDefault()
  wechsle(event.deltaY < 0 ? 'eltern' : 'kind')
}

async function onClick(event) {
  if (!auswahlAktiv.value) return
  // Der Klick wird NICHT an die App weitergegeben (Browser-Inspektor-Verhalten).
  event.preventDefault()
  event.stopPropagation()
  const el = hoverElement.value || elementUnterPunkt(event.clientX, event.clientY, overlayKnoten())
  if (!el) return
  const position = positionVon(el)
  gewaehltesElement.value = el
  auswahlBeenden()
  // DM3: Der Dialog oeffnet SOFORT (< 200 ms). Die Aufnahme laeuft PARALLEL
  // im Hintergrund; ihr Ergebnis erscheint im Dialog, sobald sie fertig ist.
  // Fehler/Haenger der Aufnahme blockieren den Dialog nie (Zeitlimit).
  startbilder.value = []
  aufnahmeFehler.value = ''
  aufnahmeLaeuft.value = true
  const lauf = ++aufnahmeLauf
  dialogOffen.value = true
  nimmAufImHintergrund(el, position, lauf)
}

/**
 * Aufnahme im Hintergrund (DM3). Kein await im Klickpfad; Fehler landen als
 * Hinweis im Dialog, ein Zeitlimit verhindert dauerhaftes „laeuft …“.
 */
async function nimmAufImHintergrund(el, position, lauf) {
  // DM3b: Timer MUSS aufgeraeumt werden, sonst laeuft er weiter und meldet
  // auf langsamen Geraeten faelschlich einen Fehler.
  let zeitgeber = null
  try {
    const bilder = await Promise.race([
      nimmAuf(el, position),
      new Promise(setzen => { zeitgeber = setTimeout(() => setzen([]), AUFNAHME_LIMIT_MS) }),
    ])
    if (lauf !== aufnahmeLauf) return // neuerer Klick gewinnt
    startbilder.value = [...startbilder.value, ...(bilder || [])]
    if (!bilder || !bilder.length) {
      aufnahmeFehler.value = 'Die Aufnahme hat nicht geklappt — bitte „Aufnehmen“ oder „Bildschirm aufnehmen“ nutzen.'
    }
  } catch (f) {
    if (lauf !== aufnahmeLauf) return
    console.warn('Dev-Modus: Aufnahme fehlgeschlagen', f)
    aufnahmeFehler.value = 'Die Aufnahme hat nicht geklappt — bitte „Aufnehmen“ oder „Bildschirm aufnehmen“ nutzen.'
  } finally {
    if (zeitgeber !== null) clearTimeout(zeitgeber)
    if (lauf === aufnahmeLauf) aufnahmeLaeuft.value = false
  }
}

function dialogSchliessen() {
  dialogOffen.value = false
  gewaehltesElement.value = null
  startbilder.value = []
  aufnahmeLaeuft.value = false
  aufnahmeFehler.value = ''
  aufnahmeLauf++ // laufende Aufnahme verwerfen
}

function nachSpeichern() {
  dialogSchliessen()
  // Dev-Modus bleibt an.
}

async function ausschalten() {
  try { await devmodusApi.sitzungBeenden() } catch { /* egal */ }
  zustandSetzen(false)
}

onMounted(() => {
  window.addEventListener('keydown', onKeydown, true)
  window.addEventListener('mousemove', onMaus, true)
  window.addEventListener('click', onClick, true)
  window.addEventListener('wheel', onRad, { capture: true, passive: false })
  // DM3b: Im Leerlauf Renderer + Schriften vorladen und einmal probeweise
  // rendern. Die erste echte Aufnahme ist dann "warm" statt ~5,5 s kalt.
  const vorladen = () => { try { vorwaermen({ ladeRenderer, fontCssSammeln }) } catch { /* egal */ } }
  if (typeof requestIdleCallback === 'function') requestIdleCallback(vorladen, { timeout: 3000 })
  else setTimeout(vorladen, 1200)
})
onUnmounted(() => {
  window.removeEventListener('keydown', onKeydown, true)
  window.removeEventListener('mousemove', onMaus, true)
  window.removeEventListener('click', onClick, true)
  window.removeEventListener('wheel', onRad, true)
  document.documentElement.style.cursor = ''
})
</script>

<style scoped>
.dk-dev-rahmen {
  position: fixed;
  inset: 0;
  border: 4px solid #e02424;
  pointer-events: none;
  z-index: 2147483000;
  box-sizing: border-box;
}
.dk-dev-ecke {
  position: fixed;
  top: 6px;
  right: 8px;
  max-width: calc(100vw - 16px);
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  justify-content: flex-end;
  z-index: 2147483001;
  font: 12px/1.2 system-ui, sans-serif;
}
.dk-dev-etikett {
  background: #e02424;
  color: #fff;
  font-weight: 700;
  letter-spacing: 0.05em;
  padding: 3px 7px;
  border-radius: 6px;
}
.dk-dev-taste {
  background: rgba(17, 17, 17, 0.82);
  color: #fff;
  padding: 3px 7px;
  border-radius: 6px;
  white-space: nowrap;
}
.dk-dev-knopf {
  font: inherit;
  cursor: pointer;
  border: 1px solid rgba(255, 255, 255, 0.35);
  background: #e02424;
  color: #fff;
  padding: 4px 10px;
  border-radius: 6px;
}
.dk-dev-knopf.is-aus { background: rgba(17, 17, 17, 0.82); }
.dk-dev-umriss {
  position: fixed;
  border: 2px solid #e02424;
  background: rgba(224, 36, 36, 0.10);
  pointer-events: none;
  z-index: 2147482999;
}
.dk-dev-ziel {
  position: absolute;
  top: -22px;
  left: 0;
  background: #e02424;
  color: #fff;
  font: 11px/1.2 ui-monospace, monospace;
  padding: 2px 6px;
  border-radius: 4px;
  white-space: nowrap;
  max-width: 60vw;
  overflow: hidden;
  text-overflow: ellipsis;
}
@media (max-width: 480px) {
  .dk-dev-taste { display: none; }
}
</style>
