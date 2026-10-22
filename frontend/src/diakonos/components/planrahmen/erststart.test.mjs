import { test } from 'node:test'
import assert from 'node:assert/strict'
import { bedarfHinweise } from './erststart.mjs'

test('Erststart benennt die echte deklarierte Fähigkeit und ihre Wirkung', () => {
  // OP-CHOR-11: Der Hinweis nennt die tatsaechliche Wirkung — markierte
  // Personen werden bei fehlender Vorbelegung der Reihe nach vorgeschlagen
  // (vorher wirkten die Haken nur als Filter der Handauswahl).
  assert.deepEqual(bedarfHinweise([{ art: 'merkmal', kennung: 'klavier', abdeckung: '0 Personen mit klavier', einstufung: 'blockiert_automatik' }], { merkmale: { person: [{ id: 'klavier', name: 'spielt Klavier' }] } }), ['Wer spielt Klavier? Markiere die passenden Personen in den Stammdaten — der Vorschlag teilt sie dann der Reihe nach ein.'])
})
test('Gepflegte Daten erzeugen keine Checkliste; fehlende Listen sind verständlich', () => {
  assert.deepEqual(bedarfHinweise([{ einstufung: 'ok' }]), [])
  assert.deepEqual(bedarfHinweise([{ art: 'sammlung', kennung: 'spiele', einstufung: 'eingeschraenkt' }], { sammlungen: [{ id: 'spiele', name: 'Spiele' }] }), ['Ergänze die Liste „Spiele“ und ihre Angaben in den Stammdaten.'])
})
