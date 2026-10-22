/**
 * Dev-Modus (DM1) — Spracheingabe.
 *
 * Zwei Wege, beide optional:
 *
 * 1. **Web Speech API** (``webkitSpeechRecognition``/``SpeechRecognition``):
 *    laeuft im Browser, aber Chrome/Edge/Safari senden die Aufnahme zu Google.
 *    Der Dialog weist ausdruecklich darauf hin.
 * 2. **Server-STT** (bevorzugt, wenn konfiguriert): Aufnahme mit
 *    ``MediaRecorder`` -> Server -> OpenAI-kompatibler Transkriptions-Endpunkt.
 *
 * Ohne beides bleibt nur das Tippen. Alle Funktionen sind so gebaut, dass
 * fehlende Browser-Unterstuetzung kein Fehler ist.
 */

/** Ist die Web-Speech-API verfuegbar? */
export function webSpeechVerfuegbar() {
  return typeof globalThis !== 'undefined'
    && Boolean(globalThis.SpeechRecognition || globalThis.webkitSpeechRecognition)
}

/** Ist ein MediaRecorder verfuegbar (fuer den Server-Weg)? */
export function recorderVerfuegbar() {
  return typeof globalThis !== 'undefined'
    && typeof globalThis.MediaRecorder !== 'undefined'
    && Boolean(navigator?.mediaDevices?.getUserMedia)
}

/**
 * Startet die Web-Speech-Erkennung. ``onText`` bekommt erkannten Text
 * (Zwischenergebnisse inklusive). Gibt ein Objekt zum Stoppen zurueck.
 */
export function starteWebSpeech({ sprache = 'de-DE', onText, onEnde, onFehler } = {}) {
  const Konstruktor = globalThis.SpeechRecognition || globalThis.webkitSpeechRecognition
  if (!Konstruktor) return null
  const erkennung = new Konstruktor()
  erkennung.lang = sprache
  erkennung.continuous = true
  erkennung.interimResults = true
  erkennung.onresult = (ereignis) => {
    let text = ''
    for (let i = ereignis.resultIndex; i < ereignis.results.length; i++) {
      text += ereignis.results[i][0].transcript
    }
    if (text && onText) onText(text)
  }
  if (onEnde) erkennung.onend = onEnde
  if (onFehler) erkennung.onerror = (e) => onFehler(e?.error || 'unbekannt')
  try { erkennung.start() } catch { return null }
  return erkennung
}

/**
 * Nimmt Mikrofon auf (MediaRecorder). Gibt eine Aufnahme-Steuerung zurueck:
 * ``stop()`` liefert ein Promise mit ``{blob, typ}``.
 */
export async function starteAufnahme({ onFehler } = {}) {
  if (!recorderVerfuegbar()) return null
  let strom
  try {
    strom = await navigator.mediaDevices.getUserMedia({ audio: true })
  } catch {
    if (onFehler) onFehler('kein-zugriff')
    return null
  }
  const bevorzugt = ['audio/webm', 'audio/ogg', 'audio/mp4']
  const typ = bevorzugt.find(t => globalThis.MediaRecorder.isTypeSupported?.(t)) || ''
  const recorder = new MediaRecorder(strom, typ ? { mimeType: typ } : undefined)
  const stuecke = []
  recorder.ondataavailable = (e) => { if (e.data && e.data.size) stuecke.push(e.data) }
  recorder.start()
  return {
    stoppen: () => new Promise((erfuellen) => {
      recorder.onstop = () => {
        for (const spur of strom.getTracks()) spur.stop()
        erfuellen({ blob: new Blob(stuecke, { type: typ || 'audio/webm' }), typ: typ || 'audio/webm' })
      }
      recorder.stop()
    }),
  }
}

/** Blob als Data-URL lesen (fuer den Upload an den Server). */
export function blobAlsDataUrl(blob) {
  return new Promise((erfuellen, ablehnen) => {
    const leser = new FileReader()
    leser.onload = () => erfuellen(String(leser.result || ''))
    leser.onerror = () => ablehnen(new Error('Aufnahme konnte nicht gelesen werden.'))
    leser.readAsDataURL(blob)
  })
}
