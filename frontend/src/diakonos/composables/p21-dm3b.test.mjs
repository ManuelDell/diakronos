import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { fontCssSammeln, fontCacheLeeren } from '../components/devmodus/screenshot.mjs'

test('DM3b: frühes leeres Font-Ergebnis verhindert spätere Schriften nicht', async () => {
    fontCacheLeeren()
    assert.equal(await fontCssSammeln({ styleSheets: [] }), '')
    const css = '@font-face { font-family: Test; src: url("/font.woff2"); }'
    const doc = { styleSheets: [{ href: 'https://gemeinde.invalid/style.css', cssRules: [{ constructor: { name: 'CSSFontFaceRule' }, cssText: css }] }] }
    assert.match(await fontCssSammeln(doc, { einbetten: false }), /font-family: Test/)
})

test('DM3b: Font-fetch hat ein Abbruchsignal, bestehende Bilder beenden das Warten nicht', async () => {
    fontCacheLeeren()
    const alt = globalThis.fetch
    let signal
    globalThis.fetch = async (url, optionen) => { signal = optionen.signal; throw new Error('Abgebrochen') }
    try {
        await fontCssSammeln({ styleSheets: [{ href: 'https://gemeinde.invalid/style.css', cssRules: [{ constructor: { name: 'CSSFontFaceRule' }, cssText: '@font-face { src: url("/font.woff2") }' }] }] })
        assert.ok(signal instanceof AbortSignal)
        const dialog = await readFile(new URL('../components/devmodus/BefundDialog.vue', import.meta.url), 'utf8')
        const warten = dialog.slice(dialog.indexOf('function warteAufBild'), dialog.indexOf('async function bildschirmAufnehmen'))
        assert.doesNotMatch(warten, /bilder.value.length/)
    } finally { globalThis.fetch = alt; fontCacheLeeren() }
})
