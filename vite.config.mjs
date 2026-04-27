import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'
import * as LucideIcons from 'lucide-static'

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
  if (!svg) return null
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

export default defineConfig({
    base: '/assets/diakronos/frontend/',
    plugins: [vue(), lucideIcons()],
    build: {
        outDir: 'diakronos/public/frontend',
        emptyOutDir: true,
        manifest: true,
        cssCodeSplit: false,
        rollupOptions: {
            input: {
                diakonos: path.resolve(__dirname, 'frontend/src/diakonos/main.js'),
                admin: path.resolve(__dirname, 'frontend/src/admin/main.js'),
                registrierung: path.resolve(__dirname, 'frontend/src/registrierung/main.js'),
                gast: path.resolve(__dirname, 'frontend/src/gast/main.js'),
                organigramm: path.resolve(__dirname, 'frontend/src/organigramm/main.js'),
            },
            output: {
                entryFileNames: '[name].js',
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
            '@': path.resolve(__dirname, 'frontend/src'),
        },
        extensions: ['.mjs', '.js', '.ts', '.jsx', '.tsx', '.json', '.vue'],
    },
    optimizeDeps: {
        include: ['vue', 'frappe-ui'],
        exclude: [],
    },
})