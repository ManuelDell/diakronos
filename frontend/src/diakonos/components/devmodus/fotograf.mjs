/**
 * Dev-Modus (DM2/DM3) — Aufnahmeplan und Ausschlussregeln fuer den Screenshot.
 *
 * Kern der Reparatur: der Screenshot darf NUR die Seite zeigen, nicht den
 * Dev-Modus selbst. Deshalb gilt:
 *
 * 1. Aufgenommen wird PARALLEL zum Oeffnen des Befund-Dialogs (siehe
 *    Rahmen.vue): der Dialog erscheint sofort, das Bild wird nachgereicht.
 *    Laege die Aufnahme erst im Dialog, waere der Dialog selbst (und sein
 *    Abdunkeln) schon im Bild — genau der Fehler aus der Nachtpruefung.
 * 2. DM3: Ausgeschlossen werden NUR noch eigene Dev-Elemente, erkennbar am
 *    Attribut ``data-dk-dev``. Die alten Klassen ``dk-modal``/``role=dialog``
 *    trafen auch App-Dialoge (DkModal/DkWarning) und rissen ein Element in
 *    einem App-Fenster aus dem Bild (Befund).
 *
 * Dieses Modul ist bewusst DOM-frei testbar (Node ``--test``): die Funktionen
 * arbeiten auf reinen Daten oder auf einem minimalen Knoten-Interface.
 */

/** Attribut, das ALLE Dev-Modus-Elemente tragen (eigene Kennung, DM3). */
export const DEV_ATTRIBUT = 'data-dk-dev'

/**
 * DM3b: Deckel fuer die Hintergrund-Aufnahme (Kaltstart ~5,5 s, plus Reserve
 * fuer langsame Geraete). Rahmen bricht danach mit Hinweis ab; der Dialog
 * wartet beim Speichern hoechstens genauso lange auf das nachgereichte Bild.
 */
export const AUFNAHME_LIMIT_MS = 15000

/** Selektoren fuer denselben Zweck (fuer Fremd-Renderer/Diagnose). */
export const DEV_SELEKTOREN = ['[' + DEV_ATTRIBUT + ']']

/** CSS-Klassen der Dev-Elemente — nur zur Diagnose, NICHT mehr fuer den Ausschluss. */
export const DEV_KLASSEN = [
  'dk-dev-rahmen', 'dk-dev-ecke', 'dk-dev-etikett', 'dk-dev-taste',
  'dk-dev-knopf', 'dk-dev-umriss', 'dk-dev-ziel', 'dk-dev-dialog',
]

/**
 * Traegt dieser Knoten die Dev-Kennung ``data-dk-dev``?
 * Ein Vorfahre mit der Kennung genuegt (der Text im Dialog z. B. steht in
 * einem untergeordneten Knoten, das Attribut sitzt am Dialograhmen).
 */
export function traegtDevKennung(knoten) {
  if (!knoten) return false
  if (typeof knoten.closest === 'function') {
    try { return Boolean(knoten.closest('[' + DEV_ATTRIBUT + ']')) } catch { /* weiter unten */ }
  }
  let e = knoten
  while (e) {
    const wert = e.getAttribute ? e.getAttribute(DEV_ATTRIBUT) : null
    if (wert !== null && wert !== undefined) return true
    e = e.parentElement || null
  }
  return false
}

/**
 * Ist dieser Knoten ein Dev-Modus-Element (Rahmen/Etikett/Knopf/Dialog)?
 * ``zusaetzlich`` erlaubt dem Aufrufer, weitere Knoten auszublenden.
 * ``ausser`` (z. B. das gewaehlte Zielelement) hat Vorrang: es wird nie
 * ausgeblendet.
 *
 * DM3: Ausschlaggebend ist allein die Dev-Kennung ``data-dk-dev`` — App-eigene
 * Dialoge (dk-modal/dk-ui-dialog/role=dialog) bleiben damit im Bild.
 */
export function istDevKnoten(knoten, zusaetzlich = [], ausser = null) {
  if (!knoten) return false
  if (ausser && (ausser === knoten || (ausser.contains && ausser.contains(knoten)))) return false
  if (zusaetzlich.some(z => z === knoten || (z && z.contains && z.contains(knoten)))) return true
  return traegtDevKennung(knoten)
}

/**
 * Die Dev-Elemente, die VOR dem Rendern aus dem Baum genommen werden.
 * ``ausser`` bleibt stehen (das ist die gewollte Markierung) — so zeigt das
 * Bild den Zielumriss, aber keinen Dev-Rahmen und keinen Dialog.
 */
export function devAusblenden(dokument, ausser = null) {
  if (!dokument) return []
  const alle = DEV_SELEKTOREN.flatMap(sel => [...dokument.querySelectorAll(sel)])
  // Ein Knoten kann mehrfach gefunden werden -> eindeutig.
  return [...new Set(alle)].filter(el => el !== ausser)
}

/**
 * Optionen fuer ``domToPng``: fester Ausschnitt (Viewport), ``scale 1``
 * (DM3: kein doppeltes Rendern durch devicePixelRatio) und ``filter``, das
 * jedes Dev-Element aus dem Rendern ausschliesst.
 */
export function screenshotOptionen({ breite, hoehe, scrollX = 0, scrollY = 0,
                                     dokument, ausser = null, scale = 1,
                                     fontCss = null } = {}) {
  const opt = {
    width: breite,
    height: hoehe,
    scale,
    style: { transform: `translate(${-scrollX}px, ${-scrollY}px)` },
    filter: (knoten) => !istDevKnoten(knoten, dokument ? devAusblenden(dokument, ausser) : [], ausser),
  }
  // DM3: vorgerechneter Font-CSS-Text -> modern-screenshot bettet die Schriften
  // nicht bei jeder Aufnahme neu ein.
  if (fontCss) opt.font = { cssText: fontCss }
  return opt
}

/**
 * Der Aufnahmeplan eines Klicks (DM3): nur noch EIN Fensterbild. Der
 * Element-Ausschnitt wird aus dem Fensterbild zugeschnitten (schneideAusschnitt),
 * statt das Element ein zweites Mal zu rendern.
 */
export function screenshotPlan(element) {
  return [{ art: 'fenster', name: 'fenster.png' }]
}

/**
 * Zuschneide-Rechteck des Zielelements innerhalb des Fensterbildes (CSS-Pixel,
 * relativ zum Viewport). Begrenzt auf das Bild; liegt das Element ausserhalb,
 * kommt ``null`` zurueck (dann bleibt nur das Fensterbild).
 */
export function schneideAusschnitt(position, breite, hoehe) {
  if (!position || !breite || !hoehe) return null
  const x = Math.max(0, Math.round(position.x))
  const y = Math.max(0, Math.round(position.y))
  const rechts = Math.min(breite, Math.round(position.x + position.breite))
  const unten = Math.min(hoehe, Math.round(position.y + position.hoehe))
  const w = rechts - x
  const h = unten - y
  if (w <= 0 || h <= 0) return null
  return { x, y, breite: w, hoehe: h }
}

/** Dateiname eines Aufnahmeschritts (fuer die Vorschau im Dialog). */
export function schrittName(schritt) {
  return schritt?.name || 'aufnahme.png'
}
