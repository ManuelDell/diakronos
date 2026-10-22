import assert from 'node:assert/strict'
import { readFileSync, readdirSync, existsSync } from 'node:fs'
import { parse, compileScript, compileTemplate } from 'vue/compiler-sfc'

const router = readFileSync(new URL('../src/diakonos/router.js', import.meta.url), 'utf8')
for (const match of router.matchAll(/import\('(.\/pages\/planrahmen\/[^']+\.vue)'\)/g)) {
  assert.ok(existsSync(new URL(match[1], new URL('../src/diakonos/', import.meta.url))), 'Registrierte Seite existiert: ' + match[1])
}

for (const directory of ['pages/planrahmen/', 'components/planrahmen/', 'components/ui/']) {
  const root = new URL('../src/diakonos/' + directory, import.meta.url)
  for (const filename of readdirSync(root).filter(name => name.endsWith('.vue'))) {
    const path = new URL(filename, root)
    const source = readFileSync(path, 'utf8')
    const { descriptor, errors } = parse(source, { filename })
    assert.deepEqual(errors, [], filename + ': SFC-Struktur')
    const script = descriptor.scriptSetup ? compileScript(descriptor, { id: filename }) : null
    if (descriptor.template) {
      const template = compileTemplate({ source: descriptor.template.content, filename, id: filename,
        compilerOptions: { bindingMetadata: script?.bindings || {} } })
      assert.deepEqual(template.errors.map(e => ({message: e.message || String(e), line: e.loc?.start.line})), [], filename + ': Vue-Vorlage')
    } else {
      assert.ok(descriptor.scriptSetup, filename + ': hat Skript oder Vorlage')
    }
  }
}
console.log('Planrahmen Vue-Komponenten: Script und Templates kompiliert')
