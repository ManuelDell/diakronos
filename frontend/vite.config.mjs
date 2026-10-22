import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'
import { createRequire } from 'module'
import * as LucideIcons from 'lucide-static'

// ANPASSUNG 4 (Build-Config, nicht SPA-Quellcode):
// `@vitejs/plugin-vue@5.2.4` ruft `registerTS()` NICHT auf. Damit hat
// `@vue/compiler-sfc` keinen TypeScript-Loader, und JEDE .vue-Datei mit
// `defineProps<ImportierterTyp>()` stirbt beim Build mit
//   "Failed to resolve import source "<pkg>". TypeScript is required as a
//    peer dep for vue in order to support resolving types from module imports."
// Betroffen ist hier `frappe-ui/src/components/TextEditor/extensions/
// image-group/ImageGroupNodeView.vue` (`defineProps<NodeViewProps & {...}>()`),
// das ueber den Barrel-Export `frappe-ui/src/index.ts` im Modulgraph landet,
// obwohl die SPA den TextEditor nie importiert (Rollup muss jedes erreichbare
// Modul erst parsen, bevor Tree-Shaking greift).
// TypeScript selbst IST als Dependency installiert — es fehlt nur die
// Registrierung beim Compiler. `registerTS` ist oeffentlich exportiert.
const require_ = createRequire(import.meta.url)
const { registerTS } = require_('@vue/compiler-sfc')
registerTS(() => require_('typescript'))

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
    // lucide-static hat die Brand-Icons (github/linkedin/twitter/youtube)
    // entfernt. frappe-ui/src/components/TextEditor/commands.js importiert
    // `~icons/lucide/youtube`. Ohne diesen Stub gibt der load-Hook undefined
    // zurueck, Vite faellt auf load-fallback zurueck und stirbt an dem
    // \0-praefigierten Tag: "The argument 'path' must be a string ...
    // without null bytes".
    // Statt zu crashen liefern wir ein leeres <svg/> — das Icon ist im
    // Diakonos-UI nie sichtbar (nur im frappe-ui-TextEditor, der nicht
    // gemountet wird).
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

function lucideIcons() {
  const icons = getIcons()
  return {
    name: 'frappe-ui-lucide-icons',
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
    // Frappe servierte unter /assets/diakronos/frontend/; das Standalone-Backend
    // serviert unter /diakonos/assets/.
    base: '/diakonos/assets/',
    plugins: [vue(), lucideIcons(), eventCalendarEsm()],
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
        include: ['vue', 'frappe-ui', '@event-calendar/build'],
        exclude: [],
    },
})
