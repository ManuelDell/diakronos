import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import assert from 'node:assert/strict'

const root = new URL('../src/diakonos/', import.meta.url)
const lies = p => readFileSync(new URL(p, root), 'utf8')
function funktion(quelle, name, ende) {
  const start = quelle.indexOf(`function ${name}(`)
  assert.ok(start >= 0, name)
  return quelle.slice(start, quelle.indexOf(ende, start))
}

test('Alte Dublettenantwort überschreibt weder neuere Antwort noch neue Eingabe', async () => {
  const text = lies('components/mitglieder/MitgliedHinzufuegenDialog.vue')
  const pruefen = funktion(text, 'dublettePruefen', '\nfunction vorhandeneOeffnen')
  const reset = funktion(text, 'dubletteZuruecksetzen', '\n/** Beim Verlassen')
  const anfragen = []
  const bauen = new Function('apiCall', `
    let pruefung = 0
    const dublette = { value: null }
    const fehler = {}
    const form = { email: 'alt@example.org', vorname: '', nachname: '' }
    const API = ''
    async ${pruefen}
    ${reset}
    return { dublette, form, dublettePruefen, dubletteZuruecksetzen }
  `)
  const zustand = bauen(() => new Promise(resolve => anfragen.push(resolve)))
  const alt = zustand.dublettePruefen()
  zustand.form.email = 'neu@example.org'
  zustand.dubletteZuruecksetzen()
  const neu = zustand.dublettePruefen()
  anfragen[1]({ dublette: { name: 'Neu' } })
  await neu
  anfragen[0]({ dublette: { name: 'Alt' } })
  await alt
  assert.equal(zustand.dublette.value.name, 'Neu')
  const unterwegs = zustand.dublettePruefen()
  zustand.dubletteZuruecksetzen()
  anfragen[2]({ dublette: { name: 'Veraltet' } })
  await unterwegs
  assert.equal(zustand.dublette.value, null)
})

test('Fehlgeschlagenes Aufnehmen öffnet nur weiterhin offene Anfragen', async () => {
  const text = lies('pages/Registrierung.vue')
  const bestaetigen = funktion(text, 'aufnehmenBestaetigen', '\n// ── Ablehnen')
  for (const [status, aktuell] of [['Bestätigt', true], ['Abgelehnt', true], ['Anmeldeanfrage', true], ['Ausstehend', true], ['Anmeldeanfrage', false]]) {
    const zeile = { name: 'A1', status }
    const ausfuehren = new Function('zeile', 'aktuell', `
      const aufnehmenFuer = { value: { name: 'A1' } }
      const aufnehmenStatus = {}, aufnehmenGruppe = {}, aufnehmenFehler = {}, processing = { value: {} }
      const aufnehmenLaeuft = { value: false }
      const aufnehmenSchutz = { merken() {} }
      const fehlerFokussieren = () => {}
      const anmeldungen = { value: [] }
      const istOffen = a => ['Anmeldeanfrage', 'Ausstehend'].includes(a.status)
      const apiCall = async () => { throw new Error('Konflikt') }
      const fetchData = async () => { anmeldungen.value = [zeile]; return aktuell }
      const showToast = () => {}, statusVorschlag = () => 'Gast', emailDublette = () => false
      async ${bestaetigen}
      const vorher = { name: 'A1', entwurf: true }
      aufnehmenFuer.value = vorher
      return aufnehmenBestaetigen()
        .then(() => ({ offen: Boolean(aufnehmenFuer.value), ersetzt: aufnehmenFuer.value !== vorher }))
    `)
    const ergebnis = await ausfuehren(zeile, aktuell)
    // P2-1: Der Entwurf geht nie verloren (Fenster bleibt offen). N5: eine nicht
    // mehr offene Anfrage darf den Entwurf NICHT durch die veraltete Zeile ersetzen.
    assert.equal(ergebnis.offen, true, status)
    const darfErsetzen = aktuell && ['Anmeldeanfrage', 'Ausstehend'].includes(status)
    if (!darfErsetzen) assert.equal(ergebnis.ersetzt, false, status)
  }
})

test('Filter bleibt in Adresse; Rückkehr und Personen-Kachel bleiben eindeutig', () => {
  const text = lies('pages/Mitglieder.vue')
  const quelle = text.slice(text.indexOf('function _statusAusAdresse'), text.indexOf('\nconst filterOptionen'))
  let hash = '#/mitglieder/liste?status=Gast'
  let listener
  const fenster = { location: { get hash() { return hash } }, history: {
    replaceState(_a, _b, ziel) { hash = ziel },
  } }
  const bauen = new Function('window', 'watch', `
    const MT_STATUS = ['Mitglied', 'Gast', 'Passives Mitglied', 'Passiver Gast']
    const statusFilter = { value: '' }
    ${quelle}
    return statusFilter
  `)
  const filter = bauen(fenster, (_ref, fn) => { listener = fn })
  assert.equal(filter.value, 'Gast')
  listener('Passives Mitglied')
  const rueckkehr = bauen(fenster, () => {})
  assert.equal(rueckkehr.value, 'Passives Mitglied')
  hash = '#/mitglieder/liste'
  assert.equal(bauen(fenster, () => {}).value, '')
})

test('Gruppen beim Öffnen neu laden; Übersicht stellt Neuladen bereit', () => {
  const bereich = lies('pages/mitglieder/Bereich.vue')
  const oeffnen = funktion(bereich, 'mitgliedHinzufuegen', '\nfunction nachAnlegen')
  assert.ok(oeffnen.indexOf('await gruppenLaden()') >= 0)
  assert.ok(oeffnen.indexOf('await gruppenLaden()') < oeffnen.indexOf('hinzufuegenOffen.value = true'))
  assert.match(lies('pages/mitglieder/Uebersicht.vue'), /defineExpose\(\{ reload: laden \}\)/)
  assert.match(bereich, /reloadFn\.call\(ziel\)/)
})

test('Warnungen nutzen bereits den zentralen Toast mit Warnstil (kein zweiter Toast)', () => {
  const reg = lies('pages/Registrierung.vue')
  assert.match(reg, /showToast\(w, 'warning'\)/)
  assert.doesNotMatch(reg, /class="reg-toast/)
  const toast = lies('index.css')
  assert.match(toast, /\.diakonos-toast--warning\s*\{[^}]*var\(--warn\)/)
})
