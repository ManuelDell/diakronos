import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'
import { existsSync, readFileSync, statSync } from 'node:fs'
import * as LucideIcons from 'lucide-static'

// DEP-1: Die TS-Registrierung (`registerTS`) war nur fuer die .vue-Dateien von
// frappe-ui (TextEditor, `defineProps<Typ>()`) noetig. Mit dem Paket entfaellt
// sie — und mit ihr die implizite Abhaengigkeit auf `typescript`, das nie in
// package.json stand und nur transitiv von frappe-ui kam.

const VIRTUAL_PREFIX = '~icons/lucide/'
const RESOLVED_PREFIX = '\0~icons/lucide/'

function getIcons() {
  let icons = {}
  for (const icon in LucideIcons) {
    if (icon === 'default') continue
    let iconSvg = LucideIcons[icon]
    if (typeof iconSvg === 'string' && iconSvg.includes('stroke-width')) {
      iconSvg = iconSvg.replace(/stroke-width="2"/g, 'stroke-width="1.5"')
    }
    icons[icon] = iconSvg
    let dashKeys = camelToDash(icon)
    for (let dashKey of dashKeys) {
      if (dashKey !== icon) icons[dashKey] = iconSvg
    }
  }
  return icons
}

function camelToDash(key) {
  let withNumber = key.replace(/[A-Z0-9]/g, (m) => '-' + m.toLowerCase())
  if (withNumber.startsWith('-')) withNumber = withNumber.substring(1)
  let withoutNumber = key.replace(/[A-Z]/g, (m) => '-' + m.toLowerCase())
  if (withoutNumber.startsWith('-')) withoutNumber = withoutNumber.substring(1)
  if (withNumber !== withoutNumber) return [withNumber, withoutNumber]
  return [withNumber]
}

function generateIconModule(icons, iconName) {
  const svg = icons[iconName]
  if (!svg) {
    // ANPASSUNG 3 (Build-Config, nicht SPA-Quellcode):
    // lucide-static fuehrt keine Brand-Icons (github/linkedin/twitter/youtube).
    // Ohne diesen Stub gibt der load-Hook undefined zurueck, Vite faellt auf
    // load-fallback zurueck und stirbt an dem \0-praefigierten Tag: "The
    // argument 'path' must be a string ... without null bytes".
    // Ursprünglicher Auslöser war frappe-ui/TextEditor (DEP-1: Paket
    // entfernt); der Stub bleibt als Sicherheitsnetz für eigene Bausteine,
    // die `~icons/lucide/<name>` nutzen.
    // Statt zu crashen liefern wir ein leeres <svg/>.
    return 'import { h } from "vue"\nexport default {\n  inheritAttrs: false,\n  render() { return h("svg", { xmlns: "http://www.w3.org/2000/svg", width: "24", height: "24", viewBox: "0 0 24 24", ...this.$attrs }) }\n}'
  }
  const innerMatch = svg.match(/<svg[^>]*>([\s\S]*)<\/svg>/)
  const innerHTML = innerMatch ? innerMatch[1].replace(/>\s+</g, '><').trim() : ''
  return `import { h } from 'vue'
export default {
  inheritAttrs: false,
  render() {
    return h('svg', {
      xmlns: 'http://www.w3.org/2000/svg',
      width: '24',
      height: '24',
      viewBox: '0 0 24 24',
      fill: 'none',
      stroke: 'currentColor',
      'stroke-width': '1.5',
      'stroke-linecap': 'round',
      'stroke-linejoin': 'round',
      ...this.$attrs,
      innerHTML: ${JSON.stringify(innerHTML)},
    })
  }
}`
}

// ── ON-0a: Token- und Seiten-Stylesheet als STABILE Dateien ──────────────
//
// WARUM EIN EIGENER PLUGIN
//   Die SPA bündelt ihr CSS (`cssCodeSplit: false`) zu EINER Datei mit
//   Inhalts-Hash im Namen (`style-<hash>.css`). Serverseitig gerenderte
//   Seiten (Anmeldung, Passwort setzen, Fehlerseiten) können diesen Namen
//   nicht kennen — und dürfen ihn auch nicht kennen, sonst müsste die
//   Backend-Vorlage den Build-Hash mitschleppen.
//
// WAS ER TUT
//   Er nimmt die beiden CSS-Einstiege des Design-Systems und schreibt sie
//   unter FESTEN Namen nach `dist/`:
//     src/diakonos/tokens.css  ->  dist/diakronos-tokens.css
//     src/ssot/seiten.css      ->  dist/diakronos-seiten.css
//   `tokens.css` bleibt dabei die einzige Quelle: der Plugin bündelt sie
//   (löst `@import '@fontsource/…'` auf, damit die Schrift auch auf
//   Server-Seiten lokal liegt) — er schreibt KEINE Werte um.
//
//   Warum `assets/` statt `/diakonos/assets/…`: derselbe Weg wie alle
//   übrigen Build-Artefakte. Der Catch-all in `spa.py` löst `/diakonos/assets/<name>`
//   gegen das Build-Verzeichnis auf, das Vite `base: './'` nicht kennt.
//
// CACHE-BUSTING
//   Der Name ist stabil, `spa.py` liefert die Datei deshalb NICHT
//   `immutable`, sondern `no-cache` + ETag — der Browser fragt nach und
//   bekommt bei unverändertem Inhalt ein 304. Ein Hash im Namen wäre die
//   Alternative; dann müsste aber JEDE Server-Seite den Hash kennen.
const SSOT_DATEIEN = [
  { quelle: 'src/diakonos/tokens.css', name: 'diakronos-tokens.css' },
  { quelle: 'src/ssot/seiten.css', name: 'diakronos-seiten.css' },
]

// `@import '<pfad>';` am Zeilenanfang — genau die Form, die tokens.css für die
// lokale Schrift nutzt (`@import '@fontsource/inter/latin-400.css';`).
const CSS_IMPORT = /@import\s+(?:url\()?['"]([^'"]+)['"]\)?\s*;/g

// ON-0b (F3): Wohin die Schriftdateien der Server-Seiten gehen.
//
// Vite benennt Schriften sonst nach Inhalt (`assets/inter-latin-400-normal-<hash>.woff2`)
// und setzt in CSS `url(./assets/<name>)`. Die beiden Server-Stylesheets liegen
// aber FLACH in `dist/` — `./assets/…` traefe dort nichts, und der Catch-all in
// `spa.py` hätte den Pfad als Seite behandelt (Anmeldeschranke statt Schrift).
//
// Deshalb: EIN fester Ordner `schriften/` mit den NAMEN AUS DER QUELLE
// (`inter-latin-400-normal.woff2`). Der Name kommt aus dem `@font-face` selbst,
// hier wird nichts umbenannt — nur der Pfad geradegezogen.
const SCHRIFT_ORDNER = 'schriften'
// `url(<pfad>)` in einem @font-face — genau die Form, die @fontsource schreibt
// (`url(./files/inter-latin-400-normal.woff2) format('woff2')`).
const SCHRIFT_URL = /url\(\s*(['"]?)([^'")]+?)\1\s*\)/g
// Wo die Datei im CSS liegt, darf NICHT als Ziel gelten (sie ist kein Build-Artefakt).
const CSS_DATEI = /\.css$/i

/**
 * Liest ein Stylesheet und setzt seine `@import`-Zeilen WÖRTLICH ein (rekursiv).
 *
 * Warum nicht einfach `fs.readFileSync`: `tokens.css` bindet die lokale Schrift
 * per `@import` ein. Ohne Auflösung zeigte die ausgelieferte Token-Datei auf
 * `@fontsource/inter/…`, was im Browser eine Anfrage auf einen Pfad auslöste,
 * den es unter `/diakonos/assets/` nicht gibt (die Schrift läge unbemerkt im
 * Falle „Inter-Fallback"). Der Import wird deshalb hier eingesammelt — die
 * Werte selbst bleiben unverändert, `tokens.css` bleibt die Quelle.
 *
 * Der Pfad wird über den Ordner der einbindenden Datei aufgelöst (CSS-Regel).
 * Ein Paket-Import (`@fontsource/…`) geht über node_modules.
 */
function leseCssMitImporten(datei, gesehen = new Set(), schriften = new Map()) {
  const absolut = path.resolve(datei)
  if (gesehen.has(absolut)) return '' // Ringbezug: nur einmal
  gesehen.add(absolut)
  const text = readFileSync(absolut, 'utf8')
  // ON-0b (F3): erst die Importe einsetzen …
  const mitImporten = text.replace(CSS_IMPORT, (_treffer, ziel) => {
    let pfad = ziel.startsWith('.')
      ? path.resolve(path.dirname(absolut), ziel)
      : path.resolve(__dirname, 'node_modules', ziel)
    if (!existsSync(pfad)) {
      // Der Import ist keine Datei (z. B. eine Media-Query-Form) — unverändert
      // stehen lassen, damit nichts stillschweigend verschwindet.
      return _treffer
    }
    return leseCssMitImporten(pfad, gesehen, schriften)
  })
  // … dann jede `url()`-Angabe, die auf eine vorhandene SCHRIFTDATEI zeigt,
  // auf den festen Ordner umschreiben und die Datei vormerken.
  return mitImporten.replace(SCHRIFT_URL, (treffer, quote, ziel) => {
    if (/^data:/i.test(ziel) || /^https?:/i.test(ziel) || CSS_DATEI.test(ziel)) return treffer
    if (!ziel.startsWith('.') || path.isAbsolute(ziel)) return treffer
    // CSS-Regel: ein relativer Pfad gilt ab dem Ordner der EINBINDENDEN Datei.
    const kandidat = path.resolve(path.dirname(datei), ziel)
    if (!existsSync(kandidat) || statSync(kandidat).isDirectory()) return treffer
    const name = path.basename(kandidat)
    schriften.set(name, kandidat)
    return `url(${quote}./${SCHRIFT_ORDNER}/${name}${quote})`
  })
}

function ssotStylesheets() {
  return {
    name: 'dk-ssot-stylesheets',
    apply: 'build',
    // Nach dem Rollup-Bündeln: die beiden Dateien unter festen Namen ablegen.
    generateBundle() {
      // ON-0b (F3): JEDE `url()` der Server-Stylesheets muss im Build eine
      // Datei haben. Gesammelt wird über ALLE Stylesheets, damit derselbe
      // Schriftstand für beide gilt; ausgegeben wird jede Datei genau einmal.
      const schriften = new Map()
      for (const datei of SSOT_DATEIEN) {
        const css = leseCssMitImporten(path.resolve(__dirname, datei.quelle), new Set(), schriften)
        if (!css.trim()) {
          this.error(`ON-0a: ${datei.quelle} ergab kein CSS — Token-Datei leer?`)
        }
        this.emitFile({ type: 'asset', fileName: datei.name, source: css })
      }
      for (const [name, quelle] of schriften) {
        this.emitFile({
          type: 'asset',
          fileName: `${SCHRIFT_ORDNER}/${name}`,
          source: readFileSync(quelle),
        })
      }
    },
  }
}

function lucideIcons() {
  const icons = getIcons()
  return {
    name: 'dk-lucide-icons',
    resolveId(id) {
      if (id.startsWith(VIRTUAL_PREFIX)) {
        return RESOLVED_PREFIX + id.slice(VIRTUAL_PREFIX.length)
      }
    },
    load(id) {
      if (!id.startsWith(RESOLVED_PREFIX)) return
      const iconName = id.slice(RESOLVED_PREFIX.length)
      return generateIconModule(icons, iconName)
    },
  }
}


function eventCalendarEsm() {
  return {
    name: 'event-calendar-esm',
    transform(code, id) {
      if (id.includes('@event-calendar/build') && id.endsWith('.js')) {
        return { code: code + '\nexport default EventCalendar;\n', map: null }
      }
    }
  }
}
export default defineConfig({
    // ANPASSUNG 1 (nicht SPA-Quellcode): Basis-Pfad der ausgelieferten Assets.
    //
    // WEB-5b (S2): RELATIV, nicht absolut. Der Build kennt den Betriebs-Präfix
    // (`DIAKRONOS_BASE_PATH`) nicht — ein fester Wert wie '/diakonos/assets/'
    // wäre unter '/gemeinde/diakronos/assets/…' falsch und würde einen zweiten
    // Build je Präfix erzwingen (Karte: ausdrücklich NICHT).
    //
    // Mit './' schreibt Vite './assets/<datei>.js' ins index.html. Das
    // index.html wird vom Server unter '{basePath}/diakonos/…' ausgeliefert
    // (auch für die Hash-Routen, die dort alle denselben Verzeichnispfad
    // haben), das Bundle liegt unter '{basePath}/diakonos/assets/…'. Der
    // relative Pfad löst deshalb zur Laufzeit immer richtig auf — MIT und OHNE
    // Präfix, ohne dass das Bundle den Präfix kennen muss.
    //
    // ACHTUNG für andere Stellen: `base` wirkt auch auf Adressen, die im CODE
    // per `import` entstehen (Fonts, Bilder) — die werden relativ aufgelöst.
    base: './',
    plugins: [vue(), ssotStylesheets(), lucideIcons(), eventCalendarEsm()],
    build: {
        // ANPASSUNG 2: Output-Pfad → frontend/dist (statt diakronos/public/frontend).
        outDir: 'dist',
        emptyOutDir: true,
        manifest: true,
        cssCodeSplit: false,
        rollupOptions: {
            onwarn(warning, warn) {
              if (warning.code === "MISSING_EXPORT" && warning.exporter?.includes("@event-calendar")) return
              warn(warning)
            },
            input: {
                diakonos: path.resolve(__dirname, 'src/diakonos/main.js'),
                registrierung: path.resolve(__dirname, 'src/registrierung/main.js'),
                gast: path.resolve(__dirname, 'src/gast/main.js'),
                organigramm: path.resolve(__dirname, 'src/organigramm/main.js'),
            },
            output: {
                entryFileNames: '[name]-[hash].js',
                chunkFileNames: 'chunks/[name]-[hash].js',
                assetFileNames: (assetInfo) => {
                    const info = assetInfo.name.split('.')
                    const ext = info[info.length - 1]
                    if (ext === 'css') {
                        return 'css/[name]-[hash][extname]'
                    }
                    return 'assets/[name]-[hash][extname]'
                },
            },
        },
        target: 'es2020',
    },
    resolve: {
        alias: {
            '@': path.resolve(__dirname, 'src'),
        },
        extensions: ['.mjs', '.js', '.ts', '.jsx', '.tsx', '.json', '.vue'],
    },
    optimizeDeps: {
        include: ['vue', '@event-calendar/build'],
        exclude: [],
    },
})
