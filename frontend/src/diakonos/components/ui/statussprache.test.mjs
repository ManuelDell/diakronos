import assert from 'node:assert/strict'
import { statusSprache, stufeSprache, statusWort, stufeWort, statusBadgeKlasse, stufeBadgeKlasse, PLAN_STATUS, STUFEN } from './statussprache.mjs'

// Plan-Status: Wort und Kennzeichen sind festgelegt.
assert.deepEqual(statusSprache('entwurf'), { wort: 'Entwurf', variant: 'warn' })
assert.deepEqual(statusSprache('veroeffentlicht'), { wort: 'Veröffentlicht', variant: 'ok' })
assert.deepEqual(statusSprache('archiviert'), { wort: 'Archiviert', variant: 'neutral' })
assert.equal(statusSprache('ENTWURF').wort, 'Entwurf')
assert.equal(statusSprache('gibtsnicht').variant, 'neutral')
assert.equal(statusSprache(null).wort, 'Unbekannt')

// Stufen: muss→Fehler, sollte→Warnung, hinweis→Hinweis.
assert.deepEqual(stufeSprache('muss'), { wort: 'Fehler', variant: 'err', piktogramm: '⛔' })
assert.deepEqual(stufeSprache('sollte'), { wort: 'Warnung', variant: 'warn', piktogramm: '⚠️' })
assert.deepEqual(stufeSprache('hinweis'), { wort: 'Hinweis', variant: 'info', piktogramm: 'ℹ️' })
assert.equal(stufeSprache('fehler').variant, 'err')
assert.equal(stufeSprache('gibtsnicht').wort, 'Unbekannt')

// Kurzformen.
assert.equal(statusWort('entwurf'), 'Entwurf')
assert.equal(stufeWort('muss'), 'Fehler')

// Badge-Klassen (globales .dk-badge).
assert.equal(statusBadgeKlasse('veroeffentlicht'), 'dk-badge dk-badge-success')
assert.equal(statusBadgeKlasse('entwurf'), 'dk-badge dk-badge-warning')
assert.equal(statusBadgeKlasse('unbekannt'), 'dk-badge')
assert.equal(stufeBadgeKlasse('muss'), 'dk-badge dk-badge-danger')
assert.equal(stufeBadgeKlasse('hinweis'), 'dk-badge dk-badge-info')

// Wortschatz vollständig (kein Status ohne Eintrag).
for (const s of Object.keys(PLAN_STATUS)) assert.ok(statusSprache(s).wort)
for (const s of Object.keys(STUFEN)) assert.ok(stufeSprache(s).wort)

console.log('Statussprache: Wörter und Kennzeichen einheitlich')
