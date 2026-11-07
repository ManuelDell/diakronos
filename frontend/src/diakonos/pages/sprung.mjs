/**
 * sprung.mjs — Einstellungen: von der Suche zum FELD (Karte UX3h).
 *
 * Die Suche findet neben Bereichen auch Feldnamen. Ein Feldtreffer führt auf
 * `#/einstellungen/<bereich>/<feld>`; der Abschnitt (Gemeinde, Mailversand …)
 * zeichnet seine Felder mit `dk-sprung-<feld>` aus und springt beim Anzeigen
 * dorthin.
 *
 * WARUM NICHT EIN `#…`-Fragment IM LINK: Die App hat einen Hash-Router. Ein
 * zweites `#` in der Adresse (`#/einstellungen/gemeinde#name`) würde die Route
 * zerlegen; ein Klick auf einen Anker ginge am Router vorbei und die Seite
 * bliebe stehen. Deshalb ist das Ziel ein PFAD-Teil, den der Abschnitt liest.
 *
 * Diese Datei hält die reine Rechnung (Kennung, Adresse, Feldname) — ohne
 * DOM, damit sie im Node-Test prüfbar ist.
 */

/** Präfix der Sprungmarken im Markup. */
export const SPRUNG_PRAEFIX = 'dk-sprung-'

/** Kennung, die ein Abschnitt an sein Feld schreibt. */
export function sprungId(feldId) {
  return SPRUNG_PRAEFIX + String(feldId ?? '')
}

/**
 * Ziel-Adresse eines Feldtreffers: Bereichsadresse + Feldname.
 * Beispiel: ('#/einstellungen/gemeinde', 'name') → '#/einstellungen/gemeinde/name'
 */
export function sprungZiel(bereichHref, feldId) {
  const basis = String(bereichHref || '').replace(/\/+$/, '')
  return basis + '/' + String(feldId ?? '')
}

/**
 * Feldname aus einer Adresse. `#/einstellungen/gemeinde/name` → 'name';
 * ohne dritten Teil (nur der Bereich) → ''.
 */
export function feldAusAdresse(hash) {
  const teile = String(hash ?? '').split('/').filter(Boolean)
  // teile[0] ist leer (vor dem ersten /) bzw. '#' — gezählt werden nur die
  // sinnvollen Teile ab „einstellungen“.
  const ab = teile.indexOf('einstellungen')
  if (ab < 0) return ''
  return teile[ab + 2] || ''
}

/**
 * Wie lange nach einem Wechsel gewartet wird, bevor der erste Blick auf die
 * Sprungmarke fällt. Der Inhalt der Einstellungen wird asynchron geladen
 * (defineAsyncComponent + API) — die Marke steht erst danach im DOM. Gemessen:
 * ein Bild (frame) reicht für den Komponentenwechsel nicht immer, 60 ms tun es
 * im Wegwerf-Stack zuverlässig.
 */
export const SPRUNG_WARTE_MS = 60

/**
 * Höchstdauer des Sprungs (Millisekunden) — Obergrenze, kein fester Ablauf.
 * `springeZu` sieht bis dahin alle 40 ms nach, ob die Marke im DOM steht. Die
 * Bereiche laden über die API; 3 s decken auch einen langsamen ersten Aufruf
 * ab, ohne dass ein verpasster Sprung ewig weiterläuft.
 */
export const SPRUNG_MAX_MS = 3000

/**
 * Sucht das Zielelement und holt es in den Blick. Gibt zurück, ob es etwas
 * zu tun gab — der Aufrufer kann so „nichts gefunden“ von „gesprungen“
 * unterscheiden (und die Marke im Feld sichtbar machen).
 *
 * WARTEN IST TEIL DER AUFGABE: der Bereich lädt seine Daten erst (Skelett →
 * Formular). Bis das Feld im DOM steht, gibt es die Marke nicht. Deshalb wird
 * bis zu `SPRUNG_MAX_MS` lang alle 40 ms nachgesehen (im Stack gemessen:
 * ohne dieses Warten blieb der Sprung aus, weil der erste Blick zu früh kam).
 */
export function springeZu(feldId, wurzel, restMs) {
  const doc = wurzel || (typeof document !== 'undefined' ? document : null)
  const ziel = doc?.getElementById?.(sprungId(feldId))
  if (!ziel) {
    const rest = (restMs === undefined ? SPRUNG_MAX_MS : restMs) - 40
    if (rest > 0 && typeof setTimeout === 'function') {
      setTimeout(() => springeZu(feldId, wurzel, rest), 40)
    }
    return false
  }
  ziel.scrollIntoView?.({ block: 'center', behavior: 'auto' })
  // Die Marke ist kurz sichtbar (Ring), damit klar ist, WOHIN die Suche
  // geführt hat — Farbe ist nicht der einzige Träger (Prinzip Ä4).
  ziel.classList?.add('is-sprungziel')
  // Der Fokus gehört ins BEDIENELEMENT, nicht an die Hülle (`dk-ui-field` ist
  // ein `div`): nur dort kann man gleich tippen, und nur dort steht der
  // Fokusring. `preventScroll`, weil `scrollIntoView` schon gescrollt hat.
  const bedienbar = ziel.querySelector?.('input, select, textarea, button')
  ;(bedienbar || ziel).focus?.({ preventScroll: true })
  const spaeter = () => ziel.classList?.remove('is-sprungziel')
  if (typeof setTimeout === 'function') setTimeout(spaeter, 2400)
  return true
}
