/**
 * Dev-Modus (DM1/DM2/DM3) — Screenshot ohne Berechtigungsdialog.
 *
 * Zwei Wege, in dieser Reihenfolge:
 *
 * 1. **DOM-Rendering** (bevorzugt): ``modern-screenshot`` wird im Browser zu
 *    einem Canvas gerendert. Die Bibliothek wird NUR im Dev-Modus dynamisch
 *    nachgeladen (``import(...)``), damit normale Nutzer sie nie laden.
 * 2. **Bildschirm aufnehmen** (``getDisplayMedia``): der Browser fragt nach —
 *    der Nutzer bestaetigt. Faellt Weg 1 aus, wird das angeboten.
 *
 * DM3 (Tempo): Es wird NUR noch der sichtbare Fensterausschnitt EINMAL mit
 * ``scale 1`` gerendert. Der Element-Ausschnitt entsteht durch Zuschneiden aus
 * dem Fensterbild (kein zweites Rendern). Web-Schriften werden EINMAL vorab
 * eingebettet (Cache) statt bei jeder Aufnahme. Alle Dev-Elemente (Kennung
 * ``data-dk-dev``) werden per ``filter`` aus dem Bild ausgeschlossen — der
 * Screenshot zeigt die Seite, nicht den Dev-Modus. App-eigene Dialoge
 * (DkModal/DkWarning) bleiben im Bild.
 */

import { screenshotOptionen, devAusblenden, schneideAusschnitt } from './fotograf.mjs'

let _renderer = null
let _rendererGeladen = false

/** Laedt modern-screenshot dynamisch (einmal je Sitzung). Gibt ``null`` zurueck, wenn nicht da. */
export async function ladeRenderer() {
  if (_rendererGeladen) return _renderer
  try {
    const modul = await import('modern-screenshot')
    if (typeof modul.domToPng === 'function') _renderer = modul.domToPng
  } catch {
    /* Nicht im Dev-Modus gebaut oder offline: Weg 2 anbieten. */
  }
  _rendererGeladen = true
  return _renderer
}

/** Setzt den Renderer-Cache zurueck (Tests). */
export function rendererCacheLeeren() {
  _renderer = null
  _rendererGeladen = false
  _fontCss = null
}

// DM3 (Tempo): Das Einbetten der Web-Schriften ist der teuerste Teil jeder
// Aufnahme. Die Regeln werden EINMAL gesammelt UND die Schriftdateien ueber
// absolute URIs (Aufloesung relativer url() gegen das Stylesheet) EINMAL zu
// data:-URIs eingebettet. Danach rendert jede Aufnahme ohne Fremd-Requests.
let _fontCss = null
let _fontCssLauf = null

/** Absolut-URL einer url() gegen das Träger-Stylesheet (relative Pfade!). */
function absoluteUrl(wert, basisUrl) {
  if (!wert) return wert
  const roh = String(wert).trim().replace(/^url\(\s*['"]?|['"]?\s*\)$/g, '').trim()
  if (!roh || /^(data:|blob:|https?:)/i.test(roh)) return roh
  try { return new URL(roh, basisUrl || globalThis.location?.href || undefined).href } catch { return roh }
}

/** Ersetzt alle url(...) einer @font-face-Regel durch absolute Adressen. */
function urlsAbsolute(cssText, basisUrl) {
  return String(cssText).replace(/url\(\s*(['"]?)([^'")]+)\1\s*\)/gi,
    (_treffer, quote, wert) => `url("${absoluteUrl(wert, basisUrl)}")`)
}

/** Laedt eine Schriftdatei einmal und gibt sie als data:-URI zurueck. */
async function alsDataUri(url, abrufen) {
  if (!url || /^data:/i.test(url)) return url
  try {
    const antwort = await abrufen(url)
    if (!antwort || !antwort.ok) return null
    const blob = await antwort.blob()
    return await new Promise((ok) => {
      const leser = new FileReader()
      leser.onload = () => ok(String(leser.result || ''))
      leser.onerror = () => ok(null)
      leser.readAsDataURL(blob)
    })
  } catch { return null }
}

/**
 * Baut den Font-CSS-Text EINMAL aus den ``@font-face``-Regeln des Dokuments.
 * Relative ``url()`` werden aufgeloest und die Schriftdateien zu data:-URIs
 * eingebettet; modern-screenshot bekommt dann einen fertigen, cachebaren
 * CSS-Text und laedt nichts mehr je Aufnahme (Review R-DM3, Befund 3).
 * Ohne erreichbare Regeln kommt ``''`` zurueck -> Systemschrift-Fallback.
 */
export async function fontCssSammeln(dokument = globalThis.document,
                                     { abrufen = null, einbetten = true } = {}) {
  if (_fontCss !== null) return _fontCss
  if (_fontCssLauf) return _fontCssLauf
  const holen = abrufen || (typeof fetch === 'function'
    ? (url) => fetch(url, { credentials: 'same-origin', signal: AbortSignal.timeout(4000) }) : null)
  _fontCssLauf = (async () => {
    let text = ''
    try {
      const gesammelt = new Set()
      for (const blatt of [...(dokument?.styleSheets || [])]) {
        let regeln = null
        try { regeln = blatt.cssRules } catch { regeln = null } // CORS -> ueberspringen
        const basis = blatt.href || globalThis.location?.href || undefined
        for (const regel of [...(regeln || [])]) {
          try {
            if (regel.constructor?.name === 'CSSFontFaceRule') {
              gesammelt.add(urlsAbsolute(regel.cssText, basis))
            }
            if (regel.constructor?.name === 'CSSImportRule' && regel.styleSheet?.cssRules) {
              const unterBasis = regel.styleSheet.href || basis
              for (const unter of [...regel.styleSheet.cssRules]) {
                if (unter.constructor?.name === 'CSSFontFaceRule') {
                  gesammelt.add(urlsAbsolute(unter.cssText, unterBasis))
                }
              }
            }
          } catch { /* einzelne Regel nicht lesbar */ }
        }
      }
      text = [...gesammelt].join('\n')
    } catch { text = '' }
    // Schriftdateien einmal zu data:-URIs machen (ein Fetch je Datei, gecacht).
    if (einbetten && text && holen) {
      const gesehen = new Map()
      for (const treffer of [...text.matchAll(/url\(\s*["']?([^"')]+)["']?\s*\)/gi)]) {
        const url = treffer[1]
        if (gesehen.has(url)) continue
        const daten = await alsDataUri(url, holen)
        gesehen.set(url, daten)
      }
      text = text.replace(/url\(\s*["']?([^"')]+)["']?\s*\)/gi,
        (treffer, url) => (gesehen.get(url) ? `url("${gesehen.get(url)}")` : treffer))
    }
    if (text) _fontCss = text
    return text
  })()
  try { return await _fontCssLauf } finally { _fontCssLauf = null }
}

/** Setzt den Font-Cache zurueck (Tests). */
export function fontCacheLeeren() { _fontCss = null }

/**
 * Rendert den ganzen sichtbaren Bereich (Viewport) als Data-URL-PNG.
 * Dev-Elemente werden ausgeblendet; ``markierung`` (das Zielelement) bleibt
 * sichtbar und traegt den Umriss.
 */
export async function fensterAlsPng(domToPng, markierung = null, entferneUmriss = null) {
  if (!domToPng) return null
  try {
    const dokument = globalThis.document
    // DM3: Schriften NICHT je Aufnahme einbetten — fertiger Cache-CSS-Text.
    const fontCss = await fontCssSammeln(dokument)
    return await domToPng(dokument.documentElement, screenshotOptionen({
      breite: globalThis.innerWidth,
      hoehe: globalThis.innerHeight,
      scrollX: globalThis.scrollX,
      scrollY: globalThis.scrollY,
      dokument,
      ausser: markierung,
      // DM3: scale 1 — kein doppeltes Rendern durch devicePixelRatio.
      scale: 1,
      fontCss,
    }))
  } catch {
    return null
  } finally {
    if (entferneUmriss) entferneUmriss()
  }
}

/**
 * DM3b: laedt Renderer + Schriften vor und macht einen winzigen Probe-Render,
 * damit die erste echte Aufnahme "warm" ist (Kaltstart verkuerzen). Laeuft im
 * Leerlauf (requestIdleCallback) und wirft nie.
 */
export async function vorwaermen({ ladeRenderer: holen = ladeRenderer,
                                   fontCssSammeln: sammeln = fontCssSammeln } = {}) {
  try {
    const renderer = await holen()
    if (!renderer) return false
    await sammeln(globalThis.document)
    // Probe-Render: 1x1-Knoten — waermt Schrift-/Ressourcen-Caches auf.
    const probe = globalThis.document?.createElement?.('div')
    if (probe) {
      probe.style.cssText = 'position:fixed;left:-9999px;top:0;width:1px;height:1px'
      globalThis.document.body.appendChild(probe)
      try { await renderer(probe, { scale: 1 }) } finally { probe.remove() }
    }
    return true
  } catch { return false }
}

/**
 * DM3: Element-Ausschnitt aus dem fertigen Fensterbild zuschneiden — kein
 * zweites Rendern. Ohne Canvas/Image (Tests) bleibt nur das Fensterbild.
 */
export async function schneideBild(datenUrl, ausschnitt, ladefunktion = null) {
  if (!datenUrl || !ausschnitt) return null
  const laden = ladefunktion || ((url) => new Promise((ok, fehler) => {
    const img = new Image()
    img.onload = () => ok(img)
    img.onerror = () => fehler(new Error('Bild nicht ladbar'))
    img.src = url
  }))
  try {
    const img = await laden(datenUrl)
    const quelle = img.naturalWidth || img.width
    // Fensterbild kann groesser/kleiner als der Viewport sein -> Massstab.
    const massstab = quelle && globalThis.innerWidth ? quelle / globalThis.innerWidth : 1
    const leinwand = globalThis.document.createElement('canvas')
    leinwand.width = Math.max(1, Math.round(ausschnitt.breite * massstab))
    leinwand.height = Math.max(1, Math.round(ausschnitt.hoehe * massstab))
    leinwand.getContext('2d').drawImage(
      img,
      Math.round(ausschnitt.x * massstab), Math.round(ausschnitt.y * massstab),
      leinwand.width, leinwand.height,
      0, 0, leinwand.width, leinwand.height)
    return leinwand.toDataURL('image/png')
  } catch {
    return null
  }
}

/** Markiert ein Element sichtbar (roter Umriss) und liefert eine Aufraeumfunktion. */
export function markiere(el) {
  if (!el || !el.style) return () => {}
  const vorher = el.style.outline
  el.style.outline = '3px solid #e02424'
  return () => { el.style.outline = vorher }
}

/**
 * Nimmt das Fenster (mit Markierung) auf und schneidet den Element-Ausschnitt
 * aus dem Ergebnis — EIN Rendervorgang. Laeuft PARALLEL zum Befund-Dialog
 * (siehe Rahmen.vue); der Dialog wartet NICHT darauf.
 *
 * Rueckgabe: Liste ``[{datenUrl, name}]``.
 */
export async function nimmAuf(element, position = null, { holeRenderer = ladeRenderer } = {}) {
  const renderer = await holeRenderer()
  if (!renderer) return []
  const aufraeumen = element ? markiere(element) : null
  const ganz = await fensterAlsPng(renderer, element, aufraeumen)
  if (!ganz) return []
  const ergebnis = [{ datenUrl: ganz, name: 'fenster.png' }]
  const ausschnitt = schneideAusschnitt(position, globalThis.innerWidth, globalThis.innerHeight)
  if (ausschnitt) {
    const teil = await schneideBild(ganz, ausschnitt)
    if (teil) ergebnis.push({ datenUrl: teil, name: 'element.png' })
  }
  return ergebnis
}

/**
 * Weg 2: Bildschirm aufnehmen ueber getDisplayMedia. Der Browser fragt den
 * Nutzer; ohne Zusage kommt ``null`` zurueck (kein Fehler).
 */
export async function bildschirmAufnehmen() {
  if (!navigator.mediaDevices?.getDisplayMedia) return null
  let strom = null
  try {
    strom = await navigator.mediaDevices.getDisplayMedia({ video: true })
    const video = document.createElement('video')
    video.srcObject = strom
    await video.play()
    const canvas = document.createElement('canvas')
    canvas.width = video.videoWidth
    canvas.height = video.videoHeight
    canvas.getContext('2d').drawImage(video, 0, 0)
    return canvas.toDataURL('image/png')
  } catch {
    return null
  } finally {
    if (strom) for (const spur of strom.getTracks()) spur.stop()
  }
}

/** Data-URL-Groesse in Bytes (grob, fuer die Vorschau-Anzeige). */
export function dataUrlGroesse(datenUrl) {
  if (!datenUrl || typeof datenUrl !== 'string') return 0
  const index = datenUrl.indexOf(',')
  if (index < 0) return 0
  return Math.round((datenUrl.length - index - 1) * 0.75)
}
