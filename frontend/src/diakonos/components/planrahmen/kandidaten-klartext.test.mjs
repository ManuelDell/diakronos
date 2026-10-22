import { test } from 'node:test'
import assert from 'node:assert/strict'
import { kandidatenHinweise } from './klartext.mjs'
test('Kandidatenhinweise übersetzen deklarierte Angaben und Personenkennungen', () => {
  assert.equal(kandidatenHinweise({ merkmale: { dirigent: 'ui1-m-0002', thema: 'Advent' }, abwesend: true }, [{ id: 'dirigent', art: 'person', name: 'Dirigent' }, { id: 'thema', art: 'text', name: 'Thema' }], { 'ui1-m-0002': { name: 'Tim Test' } }), 'im Urlaub / abwesend · Dirigent: Tim Test · Thema: Advent')
})
test('Fehlende Personenanzeige lässt keine ID durch', () => {
  assert.equal(kandidatenHinweise({ merkmale: { dirigent: 'ui1-m-0002' } }, [{ id: 'dirigent', art: 'person' }]), 'Dirigent: Nicht mehr verfügbar')
})
