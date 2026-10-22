<template>
  <div class="dk-link">
    <!-- N3: der VOLLE Link steht sichtbar und anklickbar da (Konzept
         Abschnitt 5: „nie ein Pfad“). Als Verweis (kein Textfeld), damit man
         ihn direkt oeffnen kann; der Text wird bei Bedarf umgebrochen. -->
    <a
      class="dk-link-url"
      :href="vollerLink"
      target="_blank"
      rel="noopener noreferrer"
      :title="vollerLink"
    >{{ vollerLink }}</a>

    <div class="dk-link-aktionen">
      <DkButton variant="secondary" size="sm" @click="kopieren">
        <IconCopy /> Kopieren
      </DkButton>
      <DkButton v-if="teilenMoeglich" variant="secondary" size="sm" @click="teilen">
        <IconShare /> Teilen
      </DkButton>
      <DkButton variant="secondary" size="sm" @click="oeffnen">
        <IconExternal /> Oeffnen
      </DkButton>
      <DkButton variant="secondary" size="sm" @click="qrZeigen = !qrZeigen">
        <IconQr /> {{ qrZeigen ? 'QR ausblenden' : 'QR-Code zeigen' }}
      </DkButton>
    </div>

    <!-- QR-Code: lokal gerechnet (qr.mjs), kein fremder Dienst. -->
    <div v-if="qrZeigen" class="dk-link-qr">
      <DkQrCode :text="vollerLink" :gross="qrGross" />
      <div class="dk-link-qr-aktionen">
        <DkButton variant="secondary" size="sm" :disabled="qrBusy" @click="qrHerunterladen">
          {{ qrBusy ? 'Erstelle Bild …' : 'QR herunterladen (PNG)' }}
        </DkButton>
        <DkButton variant="secondary" size="sm" :disabled="qrBusy" @click="qrDrucken">
          <IconPrint /> QR drucken
        </DkButton>
      </div>
      <p v-if="!vertraulich" class="dk-link-mini">
        Der Code wird hier im Browser erzeugt — die Adresse geht an keinen
        fremden Dienst. Zum Aushängen oder für den Gemeindebrief.
      </p>
    </div>

    <slot />
  </div>
</template>

<script setup>
/**
 * RegLinkTeilen — ein Registrierungslink mit allen Wegen, ihn weiterzugeben.
 *
 * Konzept Abschnitt 5 (N3): voller Link (anklickbar), Kopieren, auf dem
 * Mobilgeraet „Teilen“, QR-Code zeigen/als PNG sichern/drucken. Ueberall dort
 * verwendet, wo ein Link anfaellt (Unterbereich „Links & QR-Codes“ und die
 * bestehende Registrierung im Profil).
 *
 * Kein Mailversand: der Link wird selbst weitergegeben (Entscheidung 3).
 * Die PNG-Erzeugung nutzt `modern-screenshot` (schon vorhanden, kein neues
 * Paket); das QR-Bild selbst kommt aus `qr.mjs` und damit aus der App.
 */
import { computed, h, ref } from 'vue'
import { showToast } from '../../composables/useToast.js'
import DkButton from '../ui/DkButton.vue'
import DkQrCode from './DkQrCode.vue'
import { qrDateiname } from './qr.mjs'

const props = defineProps({
  /** Adresse; der Server liefert sie als `/diakonos/…?token=…`. */
  link: { type: String, required: true },
  /** Bezeichnung — nur fuer den Dateinamen des PNG. */
  bezeichnung: { type: String, default: '' },
  vertraulich: { type: Boolean, default: false },
})

/** Volle Adresse inklusive Gemeinde-Host (nie ein blosser Pfad). */
const vollerLink = computed(() => {
  const roh = String(props.link || '').trim()
  if (!roh) return ''
  try {
    return new URL(roh, window.location.origin).href
  } catch {
    return roh
  }
})

/** Teilen gibt es nur auf Geraeten, die es anbieten (typisch: Handy). */
const teilenMoeglich = computed(
  () => typeof navigator !== 'undefined' && typeof navigator.share === 'function',
)

const qrZeigen = ref(false)
const qrGross = ref(240)
const qrBusy = ref(false)

async function kopieren() {
  if (!vollerLink.value) {
    showToast('Kein Link vorhanden.', 'error')
    return
  }
  try {
    await navigator.clipboard.writeText(vollerLink.value)
    showToast('Link kopiert')
  } catch {
    showToast('Kopieren nicht möglich — bitte den Link von Hand auswählen.', 'warning')
  }
}

async function teilen() {
  try {
    await navigator.share({ title: props.bezeichnung || 'Registrierungslink', url: vollerLink.value })
  } catch {
    // Abbruch durch die Person ist kein Fehler.
  }
}

function oeffnen() {
  if (!vollerLink.value) {
    showToast('Kein Link vorhanden.', 'error')
    return
  }
  window.open(vollerLink.value, '_blank', 'noopener')
}

/** SVG des QR-Codes als PNG-Datenadresse (lokal, ohne Netz). */
async function qrAlsPng() {
  const svg = document.querySelector(`[data-qr-svg="${CSS.escape(vollerLink.value)}"]`)
  if (!svg) throw new Error('kein QR-Bild gefunden')
  const { domToPng } = await import('modern-screenshot')
  return domToPng(svg, { scale: 3, backgroundColor: '#ffffff' })
}

async function qrHerunterladen() {
  qrBusy.value = true
  try {
    const daten = await qrAlsPng()
    const a = document.createElement('a')
    a.href = daten
    a.download = qrDateiname(props.bezeichnung)
    a.click()
    showToast('QR-Code gespeichert')
  } catch (err) {
    console.error(err)
    showToast('Das Bild liess sich nicht erstellen. Bitte noch einmal versuchen.', 'error')
  } finally {
    qrBusy.value = false
  }
}

/** Druckfertig: nur der Code und die Bezeichnung auf weissem Grund. */
async function qrDrucken() {
  qrBusy.value = true
  try {
    const daten = await qrAlsPng()
    const fenster = window.open('', '_blank')
    if (!fenster) {
      showToast('Bitte Fenster für den Druck erlauben.', 'warning')
      return
    }
    fenster.document.write(
      `<!doctype html><title>${escapeHtml(props.bezeichnung || 'Registrierungslink')}</title>`
      + '<body style="margin:0;display:flex;flex-direction:column;align-items:center;gap:12px;'
      + 'font-family:system-ui,sans-serif;padding:24px">'
      + `<img src="${daten}" style="width:min(70vw,480px);height:auto" alt="QR-Code">`
      + `<p style="font-size:18px;text-align:center;word-break:break-all;margin:0">${escapeHtml(props.bezeichnung || '')}</p>`
      + `<p style="font-size:13px;color:#555;text-align:center;word-break:break-all;margin:0">${escapeHtml(vollerLink.value)}</p>`
      + '</body>',
    )
    fenster.document.close()
    fenster.focus()
    fenster.print()
  } catch (err) {
    console.error(err)
    showToast('Der Druck liess sich nicht vorbereiten.', 'error')
  } finally {
    qrBusy.value = false
  }
}

function escapeHtml(text) {
  return String(text ?? '').replace(/[&<>"']/g, (z) => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[z]
  ))
}

// Symbole (dekorativ)
const strich = { width: 14, height: 14, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': 2, 'stroke-linecap': 'round', 'stroke-linejoin': 'round' }
const IconCopy = () => h('svg', strich, [h('rect', { x: 9, y: 9, width: 13, height: 13, rx: 2 }), h('path', { d: 'M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1' })])
const IconShare = () => h('svg', strich, [h('circle', { cx: 18, cy: 5, r: 3 }), h('circle', { cx: 6, cy: 12, r: 3 }), h('circle', { cx: 18, cy: 19, r: 3 }), h('path', { d: 'M8.6 13.5l6.8 4M15.4 6.5l-6.8 4' })])
const IconExternal = () => h('svg', strich, [h('path', { d: 'M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6' }), h('polyline', { points: '15 3 21 3 21 9' }), h('line', { x1: 10, y1: 14, x2: 21, y2: 3 })])
const IconQr = () => h('svg', strich, [h('rect', { x: 3, y: 3, width: 7, height: 7 }), h('rect', { x: 14, y: 3, width: 7, height: 7 }), h('rect', { x: 3, y: 14, width: 7, height: 7 }), h('path', { d: 'M14 14h3v3h-3zM20 14h1v1h-1zM14 20h1v1h-1zM18 18h3v3h-3z' })])
const IconPrint = () => h('svg', strich, [h('polyline', { points: '6 9 6 2 18 2 18 9' }), h('path', { d: 'M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2' }), h('rect', { x: 6, y: 14, width: 12, height: 8 })])
</script>

<style scoped>
.dk-link { display: flex; flex-direction: column; gap: var(--sp-3); min-width: 0; }
.dk-link-url {
  display: block; padding: var(--sp-2) var(--sp-3);
  background: var(--surface-2); border-radius: var(--radius-sm);
  font-size: var(--fs-sm); color: var(--primary);
  word-break: break-all; text-decoration: none;
}
.dk-link-url:hover { text-decoration: underline; }
.dk-link-aktionen { display: flex; gap: var(--sp-2); flex-wrap: wrap; }
.dk-link-qr {
  display: flex; flex-direction: column; gap: var(--sp-3);
  align-items: center; padding: var(--sp-4);
  background: var(--surface-2); border-radius: var(--radius);
}
.dk-link-qr-aktionen { display: flex; gap: var(--sp-2); flex-wrap: wrap; justify-content: center; }
.dk-link-mini { font-size: var(--fs-xs); color: var(--muted); text-align: center; margin: 0; max-width: 34rem; }
</style>
