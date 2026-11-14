/**
 * UI-R4d — gemeinsame Mount-Hilfe für Verhaltenstests (jsdom + echter SFC).
 *
 * Warum eine eigene Datei: `uir4b-pruefliste-verhalten.test.mjs` (Tafel,
 * Anträge) und `uir4d-pruefliste-mount.test.mjs` (gemeinsamer Stufen-Lader)
 * mounten dieselben Bauteile. Zwei Kopien des Übersetzers hätten sich
 * auseinanderentwickelt — dann prüft der eine Test etwas anderes als der
 * andere, und niemand merkt es.
 *
 * Der Übersetzer ist bewusst klein: `vue/compiler-sfc` übersetzt Script und
 * Template, jede RELATIVE Abhängigkeit wird mit übersetzt, und die Attrappen
 * (`kanbanApi.js`, `useApi.js`, `useToast.js`) werden beim Auflösen
 * ausgetauscht. Im Test läuft damit der ECHTE Bauteil-Code — nur die
 * Datenschicht ist ersetzt.
 *
 * Zwei Regeln, die den Wert der Messungen tragen (beide aus Fehlern gelernt):
 *
 *  1. **Ein Modul je Seite und Datei.** `laden()` liefert für dieselbe Datei
 *     einer Seite immer dasselbe Modul. Ohne das entstand je Aufruf eine neue
 *     Datei — und damit ein ZWEITES Modul desselben Bauteils mit eigener Kopie
 *     des gemeinsamen Laders (`freigabeStufenReaktiv.mjs`). Ein Test, der
 *     „genau EIN Ladeaufruf je Seite“ messen will, misst dann nichts.
 *  2. **Eine Seite = eigener Ordner.** Die übersetzten Dateien einer Seite
 *     liegen in `TMP/seite-<n>`; eine neue Seite bekommt einen neuen Ordner.
 *     Sonst überschriebe sie die Dateien einer laufenden Seite. Aufgeräumt
 *     wird nur der eigene `TMP` — nie ein fremder: `node --test` startet
 *     mehrere Testdateien gleichzeitig, und deren Ordner lägen hier.
 *
 * Voraussetzung: `frontend/node_modules` muss als Symlink auf den
 * Live-Checkout zeigen — die übersetzten Module importieren echte Pakete
 * (`sortablejs`, `jsdom` …), und die löst Node nur unter einem Verzeichnis mit
 * `node_modules` auf. Deshalb liegt TMP unter `frontend/` (nicht im
 * System-Temp).
 */
import { readFileSync, mkdtempSync, mkdirSync, writeFileSync, rmSync } from 'node:fs'
import { join, dirname, resolve, basename } from 'node:path'
import { pathToFileURL } from 'node:url'
import { JSDOM } from 'jsdom'
import { parse, compileScript, compileTemplate } from 'vue/compiler-sfc'

/** jsdom global setzen — MUSS vor dem ersten `import('vue')` laufen. */
export function domVorbereiten() {
  const dom = new JSDOM('<!doctype html><html><body></body></html>', { url: 'http://localhost/' })
  for (const schluessel of ['window', 'document', 'Node', 'Element', 'HTMLElement', 'Event',
    'MouseEvent', 'SVGElement', 'CSS', 'getComputedStyle', 'MutationObserver']) {
    globalThis[schluessel] = dom.window[schluessel]
  }
  return dom
}

/**
 * Einen Übersetzer für EINEN Testlauf bauen.
 *
 * @param {{ pruefungsVerzeichnis: string, srcDiakonos: string }} orte
 *        `pruefungsVerzeichnis` = `frontend/tests` (TMP entsteht daneben),
 *        `srcDiakonos` = `frontend/src/diakonos`.
 */
export function uebersetzer({ pruefungsVerzeichnis, srcDiakonos }) {
  /** Zielordner für die übersetzten Module — EINMAL je Testlauf. */
  const TMP = mkdtempSync(join(pruefungsVerzeichnis, '..', `.ui-r4-mount-${basename(pruefungsVerzeichnis)}-`))
  /** Eine „Seite“ = ein Unterordner (s. `cacheLeeren`). */
  let seiteNr = 0
  let seiteOrdner = join(TMP, 'seite-0')
  mkdirSync(seiteOrdner, { recursive: true })
  /** Übersetzte Dateien dieser Seite: `abs → Datei`. */
  const dateien = new Map()
  /** Geladene Module dieser Seite: `rel → Promise<Modul>`. */
  const moduleJeDatei = new Map()
  /** Zähler nur für sprechende Dateinamen im Ordner. */
  let dateiNr = 0
  const attrappen = new Map()
  const VUE_URL = import.meta.resolve('vue')
  // Zum Nachsehen im Fehlerfall: `UI_R4_MOUNT_BEHALTEN=1` lässt die
  // übersetzten Module liegen (dann räumt der Test sie NICHT ab).
  const BEHALTEN = process.env.UI_R4_MOUNT_BEHALTEN === '1'

  /** Eine Attrappe, die anstelle einer echten Datenschicht-Datei importiert wird. */
  function attrappe(name, code) {
    const ziel = join(TMP, `${name}.mjs`)
    writeFileSync(ziel, code)
    attrappen.set(name, pathToFileURL(ziel).href)
  }

  /** Ein SFC dieser Seite übersetzen (je Datei genau einmal). */
  function kompilieren(abs) {
    if (dateien.has(abs)) return dateien.get(abs)
    const filename = basename(abs)
    const { descriptor, errors } = parse(readFileSync(abs, 'utf8'), { filename })
    if (errors.length) {
      throw new Error(`${filename}: SFC ist nicht lesbar — ${errors.map((e) => e.message).join(', ')}`)
    }
    const script = compileScript(descriptor, { id: filename })
    const tpl = compileTemplate({
      source: descriptor.template.content,
      filename,
      id: filename,
      compilerOptions: { bindingMetadata: script.bindings },
    })
    if (tpl.errors.length) {
      throw new Error(`${filename}: Vorlagenfehler — ${tpl.errors.map(String).join(', ')}`)
    }
    let code = script.content.replace(/\nexport default /, '\nconst __sfc__ = ')
    code += '\n' + tpl.code.replace(/^export function render/m, 'function render')
    code += '\n__sfc__.render = render\nexport default __sfc__\n'
    code = code.replace(/from\s+['"]vue['"]/g, `from '${VUE_URL}'`)
    code = code.replace(/from\s+['"]([^'"]+)['"]/g, (voll, spec) => {
      if (!spec.startsWith('.')) return voll
      const name = basename(spec)
      if (attrappen.has(name)) return `from '${attrappen.get(name)}'`
      const ziel = resolve(dirname(abs), spec)
      // Auch reine `.mjs`-Helfer bleiben Teil DIESER Seite — nur so teilen
      // sich alle Bauteile einer Seite den Modul-Merker des Laders.
      return `from '${pathToFileURL(spec.endsWith('.vue') ? kompilieren(ziel) : ziel).href}'`
    })
    const ziel = resolve(seiteOrdner, `${filename.replace(/\.vue$/, '')}.${dateiNr}.mjs`)
    dateiNr += 1
    writeFileSync(ziel, code)
    dateien.set(abs, ziel)
    return ziel
  }

  /**
   * Eine frische „Seite“: eigener Zwischenspeicher UND eigener Ordner.
   *
   * Eine Seite = eine Seiten-Lebensdauer der Anwendung. Innerhalb einer Seite
   * teilen sich alle Bauteile den Stand des gemeinsamen Laders; über
   * Seitengrenzen hinweg darf nichts „hängen bleiben“.
   */
  function cacheLeeren() {
    dateien.clear()
    moduleJeDatei.clear()
    dateiNr = 0
    seiteNr += 1
    seiteOrdner = join(TMP, `seite-${seiteNr}`)
    mkdirSync(seiteOrdner, { recursive: true })
  }

  /**
   * Ein Bauteil (`rel` endet auf `.vue`) oder einen Helfer laden.
   *
   * @param {string} rel Pfad unter `src/diakonos`
   * @returns {Promise<any>} `.default` bei `.vue`; sonst das Modul selbst
   */
  async function laden(rel) {
    if (!moduleJeDatei.has(rel)) {
      const ziel = rel.endsWith('.vue')
        ? kompilieren(join(srcDiakonos, rel))
        : join(srcDiakonos, rel)
      // Bricht der Import ab, ist das ein Testfehler und KEIN „nichts
      // passiert“ — sonst prüfen die Zusagen danach nichts und der Lauf sieht
      // grün aus.
      moduleJeDatei.set(rel, import(pathToFileURL(ziel).href).catch((fehler) => {
        moduleJeDatei.delete(rel)
        throw new Error(`${rel}: Import der übersetzten Datei scheiterte (${ziel}) — ${fehler.message}`)
      }))
    }
    const geladen = await moduleJeDatei.get(rel)
    return rel.endsWith('.vue') ? geladen.default : geladen
  }

  /**
   * Nur den eigenen Ordner abräumen. Bewusst KEIN Rundumschlag über alle
   * `.ui-r4-mount-*`: `node --test` startet mehrere Testdateien gleichzeitig,
   * deren Seitenordner hier lägen.
   */
  function aufraeumen() {
    if (BEHALTEN) {
      console.log(`[sfc-mount] übersetzte Module behalten: ${TMP}`)
      return
    }
    rmSync(TMP, { recursive: true, force: true })
  }

  return { attrappe, cacheLeeren, laden, aufraeumen }
}

/** Auf den nächsten Microtask/Timer-Tick warten. */
export const tick = () => new Promise((loese) => setTimeout(loese, 0))

/** Feste Wartezeit (ms) — für Antworten, die über einen Timer kommen. */
export const warte = (ms) => new Promise((loese) => setTimeout(loese, ms))

/** Sichtbarer Text eines Hosts, Leerraum zusammengezogen. */
export function text(host) {
  return host.textContent.replace(/\s+/g, ' ').trim()
}

/**
 * Bauteil in jsdom mounten und alle Vue-Warnungen einsammeln.
 *
 * @param {any} Vue  das aus demselben Modulgraphen geladene `vue`
 * @param {any} Komponente
 * @param {object} [props]
 */
export async function mounten(Vue, Komponente, props = {}) {
  const host = document.createElement('div')
  document.body.appendChild(host)
  const warnungen = []
  const app = Vue.createApp(Komponente, props)
  app.config.warnHandler = (meldung) => warnungen.push(meldung)
  const vm = app.mount(host)
  await tick()
  return { host, app, vm, warnungen }
}
