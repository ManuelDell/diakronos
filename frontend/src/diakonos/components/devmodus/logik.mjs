/**
 * Dev-Modus (DM1) — reine Hilfsfunktionen.
 *
 * Bewusst OHNE DOM-Abhaengigkeit fuer den Test-Teil (Node `--test`): die
 * Funktionen arbeiten entweder auf reinen Daten oder auf einem minimalen
 * Knoten-Interface (siehe Testdatei). Alles, was einen echten Browser
 * braucht, steht in den .vue-Komponenten bzw. screenshot.mjs/sprache.mjs.
 */

/** Erwartetes Tastenkuerzel: Strg+Shift+F ('F' wie Fehler), auch auf macOS Ctrl. */
export const KUERZEL_TASTE = 'F'

/**
 * Passt das Tastenereignis zum Kuerzel Strg+Shift+F?
 *
 * Bewusst `ctrlKey` (nicht `metaKey`): die Karte verlangt auch auf macOS
 * Strg, nicht Cmd. `altKey` darf nicht gedrueckt sein (sonst faengt man
 * Tastaturkuerzel des Systems ab).
 */
export function kuerzelPasst(ereignis, taste = KUERZEL_TASTE) {
  if (!ereignis) return false
  return Boolean(ereignis.ctrlKey) && Boolean(ereignis.shiftKey)
    && !ereignis.altKey && String(ereignis.key || '').toUpperCase() === taste.toUpperCase()
}

/** Ist das Ziel ein (beschreibbares) Eingabefeld? Fuer die Kuerzel-Weiterleitung. */
export function istEingabefeld(ziel) {
  if (!ziel) return false
  const tag = String(ziel.tagName || '').toUpperCase()
  if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return true
  return Boolean(ziel.isContentEditable)
}

/**
 * Eindeutiger CSS-Selektor fuer ein Element.
 *
 * Reihenfolge: id (wenn eindeutig) > stabile data-*-Attribute > Pfad aus
 * Tag + nth-of-type von der Wurzel. Das Ergebnis ist der EINSTIEG fuer die KI;
 * `komponentenkette` erklaert den Ort zusaetzlich in Klartext.
 */
export function selektorFuer(el) {
  if (!el) return ''
  const dokument = el.ownerDocument || (typeof document !== 'undefined' ? document : null)
  if (el.id) {
    const escaped = cssFlucht(el.id)
    if (!dokument || dokument.querySelectorAll(`#${escaped}`).length === 1) {
      return `#${escaped}`
    }
  }
  const daten = datenAttributSelektor(el)
  if (daten) return daten
  return pfadSelektor(el, dokument)
}

function datenAttributSelektor(el) {
  const attribute = el.attributes || []
  for (const name of ['data-testid', 'data-test', 'data-cy', 'data-name', 'data-key']) {
    const treffer = [...attribute].find(a => a.name === name)
    if (treffer && treffer.value) return `[${name}="${cssFlucht(treffer.value)}"]`
  }
  return ''
}

function pfadSelektor(el, dokument) {
  const teile = []
  let knoten = el
  while (knoten && knoten.nodeType === 1 && knoten.tagName) {
    let teil = knoten.tagName.toLowerCase()
    const geschwister = knoten.parentNode
      ? [...knoten.parentNode.children].filter(k => k.tagName === knoten.tagName)
      : []
    if (geschwister.length > 1) {
      teil += `:nth-of-type(${geschwister.indexOf(knoten) + 1})`
    }
    teile.unshift(teil)
    if (knoten.id && (!dokument || dokument.querySelectorAll(`#${cssFlucht(knoten.id)}`).length === 1)) {
      teile.unshift(`#${cssFlucht(knoten.id)}`)
      break
    }
    knoten = knoten.parentNode
    if (knoten && knoten.nodeType === 1 && knoten.tagName === 'BODY') break
  }
  return teile.join(' > ')
}

function cssFlucht(wert) {
  return String(wert).replace(/[^a-zA-Z0-9_-]/g, ch => `\\${ch}`)
}

/**
 * Vue-Komponentenkette vom Element bis zur Seite: z.B. Lieder > DkTable > DkButton.
 *
 * Vue haengt die Komponenten-Instanz als `__vueParentComponent` an das
 * DOM-Element. Ohne Vue (Tests) bleibt die Liste leer — das ist kein Fehler.
 */
export function komponentenkette(el) {
  const namen = []
  let knoten = el
  while (knoten) {
    // Zuerst die Dev-Modus-Anmerkung aus main.js (funktioniert auch im
    // Produktionsbuild, in dem Vue `__vueParentComponent` entfernt). Jedes
    // Element traegt nur seinen EIGENEN Namen; die Kette entsteht beim
    // Hochlaufen und wird am Ende umgedreht (aussen zuerst).
    const markiert = knoten.__dkName
    if (markiert) {
      if (namen[namen.length - 1] !== markiert) namen.push(markiert)
    } else {
      const instanz = knoten.__vueParentComponent
      if (instanz) {
        const name = komponentenName(instanz)
        if (name && namen[namen.length - 1] !== name) namen.push(name)
      }
    }
    knoten = knoten.parentElement
  }
  return namen.reverse()
}

function komponentenName(instanz) {
  const typ = instanz?.type || instanz?.$options || {}
  return String(typ.name || typ.__name || typ.__file?.split('/').pop()?.replace(/\.vue$/, '') || '')
}

/** Sichtbarer Text eines Elements, gekuerzt und ohne Mehrfach-Leerraum. */
export function sichtbarerText(el, grenze = 400) {
  if (!el) return ''
  const roh = typeof el.innerText === 'string' && el.innerText
    ? el.innerText
    : (el.textContent || '')
  const kurz = String(roh).replace(/\s+/g, ' ').trim()
  return kurz.length > grenze ? kurz.slice(0, grenze) + '…' : kurz
}

/** Position/Groesse eines Elements (gerundet). */
export function positionVon(el) {
  if (!el || typeof el.getBoundingClientRect !== 'function') return null
  const r = el.getBoundingClientRect()
  return {
    x: Math.round(r.left), y: Math.round(r.top),
    breite: Math.round(r.width), hoehe: Math.round(r.height),
    seiteX: Math.round(r.x + (el.ownerDocument?.defaultView?.scrollX || 0)),
    seiteY: Math.round(r.y + (el.ownerDocument?.defaultView?.scrollY || 0)),
  }
}

/** Wichtige berechnete Stile (nur die, die fuer ein Bild/Fehler relevant sind). */
export function wichtigeStile(el) {
  if (!el || typeof getComputedStyle !== 'function' || !el.ownerDocument?.defaultView) return {}
  const s = el.ownerDocument.defaultView.getComputedStyle(el)
  if (!s) return {}
  const felder = ['color', 'backgroundColor', 'fontSize', 'fontWeight', 'fontFamily',
    'width', 'height', 'marginTop', 'marginRight', 'marginBottom', 'marginLeft',
    'paddingTop', 'paddingRight', 'paddingBottom', 'paddingLeft',
    'display', 'position', 'opacity', 'borderRadius', 'borderColor', 'zIndex']
  const aus = {}
  for (const f of felder) if (s[f]) aus[f] = s[f]
  return aus
}

/** data-*-Attribute eines Elements als Objekt. */
export function datenattribute(el) {
  const aus = {}
  for (const a of el?.attributes || []) {
    if (a.name.startsWith('data-')) aus[a.name] = a.value
  }
  return aus
}

/** Formularwerte nur sichtbar und redigiert (Passwort/versteckt NIE). */
export function formularwerte(el) {
  if (!el) return null
  const aus = {}
  const felder = el.querySelectorAll ? el.querySelectorAll('input, textarea, select') : []
  for (const feld of felder) {
    const typ = String(feld.type || '').toLowerCase()
    const name = feld.name || feld.id
    if (!name) continue
    if (typ === 'password' || typ === 'hidden' || typ === 'file') {
      aus[name] = '[entfernt]'
      continue
    }
    if (typ === 'checkbox' || typ === 'radio') { aus[name] = Boolean(feld.checked); continue }
    aus[name] = String(feld.value ?? '')
  }
  return Object.keys(aus).length ? aus : null
}

/**
 * Redigiert einen outerHTML-String: Werte von Passwort-/versteckten Feldern
 * werden NIE uebernommen. (Der Server redigiert zusaetzlich — defense in depth.)
 */
export function redigiereHtml(html, grenze = 4000) {
  if (!html) return ''
  let aus = String(html)
  aus = aus.replace(
    /(<input\b[^>]*type\s*=\s*["']?(?:password|hidden)["']?[^>]*value\s*=\s*["'])[^"']*(["'])/gi,
    '$1[entfernt]$2')
  aus = aus.replace(/(<input\b[^>]*value\s*=\s*["'])[^"']*(["'][^>]*type\s*=\s*["']?(?:password|hidden))/gi,
    '$1[entfernt]$2')
  return aus.length > grenze ? aus.slice(0, grenze) + '…' : aus
}

/**
 * Vollstaendiger Element-Kontext fuer einen Befund. Alle Geheimnisse werden
 * hier redigiert; die Server-Redaktion laeuft zusaetzlich.
 */
export function elementKontext(el) {
  if (!el) return {}
  const komponenten = komponentenkette(el)
  return {
    selektor: selektorFuer(el),
    tag: String(el.tagName || '').toLowerCase(),
    id: el.id || null,
    klassen: el.className && typeof el.className === 'string' ? el.className : null,
    datenattribute: datenattribute(el),
    text: sichtbarerText(el),
    aria_label: el.getAttribute ? el.getAttribute('aria-label') : null,
    role: el.getAttribute ? el.getAttribute('role') : null,
    komponenten,
    position: positionVon(el),
    stile: wichtigeStile(el),
    formularwerte: formularwerte(el),
    outer_html: redigiereHtml(el.outerHTML),
  }
}

/**
 * Sichtbares Element unter einem Punkt (oberstes, aber NICHT unser Overlay).
 * `ausschluss` ist ein Set von Elementen, die nie gewaehlt werden duerfen.
 */
export function elementUnterPunkt(x, y, ausschluss = []) {
  if (typeof document === 'undefined') return null
  const treffer = document.elementsFromPoint(x, y) || []
  for (const el of treffer) {
    if (ausschluss.some(a => a === el || (a && a.contains && a.contains(el)))) continue
    if (String(el.tagName).toLowerCase() === 'html') continue
    return el
  }
  return null
}

/** Eltern-/Kindwechsel fuer die Pfeiltasten (Browser-Inspektor-Verhalten). */
export function wechsleElement(el, richtung, ausschluss = []) {
  if (!el) return null
  if (richtung === 'eltern') {
    let e = el.parentElement
    while (e && ausschluss.some(a => a && a.contains(e))) e = e.parentElement
    return e
  }
  const kind = el.firstElementChild
  if (kind && !ausschluss.some(a => a && a.contains(kind))) return kind
  return el
}

/** Gekuerzte Darstellung eines Elements fuer das Etikett (Komponente oder Tag). */
export function elementEtikett(el) {
  if (!el) return ''
  const teile = komponentenkette(el)
  const letzte = teile[teile.length - 1]
  const tag = String(el.tagName || '').toLowerCase()
  const id = el.id ? `#${el.id}` : ''
  const kl = el.classList && el.classList.length ? '.' + [...el.classList].slice(0, 2).join('.') : ''
  return `${letzte ? letzte + ' ' : ''}${tag}${id}${kl}`.trim()
}

/** Fehlerumfeld eines Ereignisses als lesbare Zeile (wie in der Testleiste). */
export function ereignisZeile(e) {
  if (!e) return ''
  const teile = [e.art, e.methode, e.pfad, e.status ? `HTTP ${e.status}` : '']
    .filter(Boolean).map(String)
  if (e.meldung) teile.push(String(e.meldung).slice(0, 200))
  return teile.join(' · ')
}
