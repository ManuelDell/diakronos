import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { ref, computed, h } from 'vue'
import { useFormularSchutz } from '../src/diakonos/composables/useFormularSchutz.js'
import { bestaetigung, bestaetigungAntwort } from '../src/diakonos/composables/useBestaetigen.js'
import { pflichtFehler } from '../src/diakonos/composables/formularPruefung.mjs'

const quelle = readFileSync(new URL('../src/diakonos/pages/Registrierung.vue', import.meta.url), 'utf8')
const skript = quelle.match(/<script setup>([\s\S]*?)<\/script>/)[1].replace(/^import .*$/gm, '')

function seite(apiCall = async () => ({})) {
  const meldungen = []
  return new Function('ref', 'computed', 'h', 'onMounted', 'defineProps', 'apiCall', 'showToast', 'useFormularSchutz', 'pflichtFehler', 'requestAnimationFrame', `
    ${skript}
    return { newLink, newFormular, formularFelder, showCreateLink, showCreateFormular,
      formularBearbeitet, formularBearbeiten, formularEntfernen,
      linkOeffnen, formularOeffnen, linkSchliessen, formularSchliessen,
      linkSchutz, formularSchutz, linkFehler, formularFehler,
      createLink, createFormular, addFeld, linkSpeichert, formularSpeichert,
      verlaengernOeffnen, verlaengernFuer, verlaengernDatum, verlaengernMax,
      verlaengernSchutz, verlaengernSchliessen, verlaengernBestaetigen, verlaengernFehler,
      aufnehmen, aufnehmenFuer, aufnehmenStatus, aufnehmenGruppe, aufnehmenFehler,
      aufnehmenSchutz, aufnehmenSchliessen, aufnehmenBestaetigen, aufnehmenLaeuft,
      ablehnen, ablehnenFuer, ablehnGrund, ablehnenFehler, ablehnenLaeuft,
      ablehnenSchutz, ablehnenSchliessen, ablehnenBestaetigen }
  `)(ref, computed, h, () => {}, () => {}, apiCall, (...args) => meldungen.push(args), useFormularSchutz, pflichtFehler, () => {})
}

for (const art of ['link', 'formular']) {
  test(`Registrierung ${art}: Verwerfen erhält oder löscht den gesamten Entwurf`, async () => {
    const s = seite()
    const link = art === 'link'
    const oeffnen = link ? s.linkOeffnen : s.formularOeffnen
    const schliessen = link ? s.linkSchliessen : s.formularSchliessen
    const modell = link ? s.newLink : s.newFormular
    const sichtbar = link ? s.showCreateLink : s.showCreateFormular
    oeffnen()
    modell.value.bezeichnung = 'Nicht verlieren'
    if (!link) { s.addFeld(); s.formularFelder.value[0].label = 'Ernährung' }
    const schutz = link ? s.linkSchutz : s.formularSchutz
    const vorher = JSON.stringify([modell.value, s.formularFelder.value])
    const abbruch = schliessen()
    assert.equal(bestaetigung.value.aktion, 'Verwerfen')
    bestaetigungAntwort(false)
    await abbruch
    assert.equal(sichtbar.value, true)
    assert.equal(JSON.stringify([modell.value, s.formularFelder.value]), vorher)
    // Esc/Kreuz verwenden am DkDialog genau diesen beforeClose-Helfer.
    const kreuz = schutz.darfSchliessen()
    bestaetigungAntwort(false)
    assert.equal(await kreuz, false)
    const verwerfen = schliessen()
    bestaetigungAntwort(true)
    await verwerfen
    assert.equal(sichtbar.value, false)
    oeffnen()
    assert.equal(modell.value.bezeichnung, '')
    if (!link) assert.deepEqual(s.formularFelder.value, [])
    assert.equal(await schutz.darfSchliessen(), true)
  })

  test(`Registrierung ${art}: leere Pflichtangaben senden nicht, Fehler erhalten Eingaben`, async () => {
    let aufrufe = 0
    const s = seite(async () => { aufrufe++; throw new Error('Bitte später erneut versuchen.') })
    const link = art === 'link'
    const oeffnen = link ? s.linkOeffnen : s.formularOeffnen
    const speichern = link ? s.createLink : s.createFormular
    const modell = link ? s.newLink : s.newFormular
    const fehler = link ? s.linkFehler : s.formularFehler
    const sichtbar = link ? s.showCreateLink : s.showCreateFormular
    oeffnen()
    modell.value.bezeichnung = '  '
    await speichern()
    assert.equal(aufrufe, 0)
    assert.ok(Object.values(fehler.value).some(text => text.includes('Bezeichnung')))
    modell.value.bezeichnung = 'Freizeit'
    await speichern()
    assert.equal(aufrufe, 1)
    assert.equal(sichtbar.value, true)
    assert.equal(modell.value.bezeichnung, 'Freizeit')
    assert.ok(Object.values(fehler.value).some(text => text.includes('später')))
  })
  test(`Registrierung ${art}: laufendes Speichern sperrt Schließen und Doppelabsenden`, async () => {
    let beenden
    let aufrufe = 0
    const s = seite(async () => {
      aufrufe++
      if (aufrufe === 1) return new Promise(resolve => { beenden = resolve })
      return {}
    })
    const link = art === 'link'
    ;(link ? s.linkOeffnen : s.formularOeffnen)()
    ;(link ? s.newLink : s.newFormular).value.bezeichnung = 'Freizeit'
    const speichern = link ? s.createLink : s.createFormular
    const schutz = link ? s.linkSchutz : s.formularSchutz
    const wartet = speichern()
    assert.equal((link ? s.linkSpeichert : s.formularSpeichert).value, true)
    assert.equal(await schutz.darfSchliessen(), false)
    await speichern()
    assert.equal(aufrufe, 1)
    beenden({ success: true })
    await wartet
    assert.equal((link ? s.linkSpeichert : s.formularSpeichert).value, false)
    assert.equal((link ? s.showCreateLink : s.showCreateFormular).value, false)
    assert.equal(await schutz.darfSchliessen(), true)
  })
}

test('Formularfelder benötigen ebenfalls eine Bezeichnung, bevor etwas gespeichert wird', async () => {
  let aufrufe = 0
  const s = seite(async () => { aufrufe++; return {} })
  s.formularOeffnen()
  s.newFormular.value.bezeichnung = 'Freizeit'
  s.addFeld()
  await s.createFormular()
  assert.equal(aufrufe, 0)
  assert.ok(s.formularFehler.value['reg-feld-0'])
})

test('Enter sendet über echte Formulare; Pflichtangaben sperren nicht den Prüfknopf', () => {
  for (const [id, aktion, schutz] of [['reg-link-form', 'createLink', 'linkSchutz'], ['reg-formular-form', 'createFormular', 'formularSchutz']]) {
    assert.match(quelle, new RegExp(`<form[^>]*id="${id}"[^>]*@submit\\.prevent="${aktion}"`))
    assert.match(quelle, new RegExp(`type="submit" form="${id}"`))
    assert.match(quelle, new RegExp(`:before-close="${schutz}\\.darfSchliessen"`))
  }
  assert.doesNotMatch(quelle, /:disabled="!new(?:Link|Formular)\./)
})

const anfrage = { name: 'anfrage-1', vorname: 'Anna', nachname: 'Beispiel', gruppe: 'gruppe-1', anmeldungstyp: 'Mitglied-Registrierung' }
const link = { name: 'link-1', bezeichnung: 'Einladung', gueltig_bis: '2027-01-01', plaetze_gesamt: 10 }
const bearbeitungen = [
  { art: 'verlaengern', oeffnen: s => s.verlaengernOeffnen(link), aendern: s => { s.verlaengernDatum.value = '2027-02-01'; s.verlaengernMax.value = 30 }, lesen: s => [s.verlaengernDatum.value, s.verlaengernMax.value], ursprung: ['2027-01-01', 10] },
  { art: 'aufnehmen', oeffnen: s => s.aufnehmen(anfrage), aendern: s => { s.aufnehmenStatus.value = 'Gast'; s.aufnehmenGruppe.value = 'gruppe-2' }, lesen: s => [s.aufnehmenStatus.value, s.aufnehmenGruppe.value], ursprung: ['Mitglied', 'gruppe-1'] },
  { art: 'ablehnen', oeffnen: s => s.ablehnen(anfrage), aendern: s => { s.ablehnGrund.value = 'Keine Plätze mehr' }, lesen: s => [s.ablehnGrund.value], ursprung: [''] },
]
for (const { art, oeffnen, aendern, lesen, ursprung } of bearbeitungen) {
  test(`${art}: unverändert schließen, Änderungen behalten oder verwerfen, beim Öffnen zurücksetzen`, async () => {
    const s = seite()
    oeffnen(s)
    assert.equal(await s[art + 'Schutz'].darfSchliessen(), true)
    aendern(s)
    const entwurf = lesen(s)
    const warten = s[art + 'Schliessen']()
    assert.equal(bestaetigung.value.aktion, 'Verwerfen')
    bestaetigungAntwort(false)
    await warten
    assert.ok(s[art + 'Fuer'].value)
    assert.deepEqual(lesen(s), entwurf)
    const verwerfen = s[art + 'Schliessen']()
    bestaetigungAntwort(true)
    await verwerfen
    assert.equal(s[art + 'Fuer'].value, null)
    oeffnen(s)
    assert.deepEqual(lesen(s), ursprung)
    assert.equal(await s[art + 'Schutz'].darfSchliessen(), true)
  })

  test(`${art}: laufender Aufruf sperrt Doppelabsenden/Schließen, Fehler erhält Entwurf`, async () => {
    let ablehnen
    let aufrufe = 0
    const s = seite(() => { aufrufe++; return aufrufe === 1 ? new Promise((_, reject) => { ablehnen = reject }) : Promise.resolve({}) })
    oeffnen(s)
    aendern(s)
    const entwurf = lesen(s)
    const warten = s[art + 'Bestaetigen']()
    assert.ok(s[art + 'Fuer'].value, 'Fenster bleibt während des Schreibens offen')
    assert.equal(await s[art + 'Schutz'].darfSchliessen(), false)
    await s[art + 'Bestaetigen']()
    assert.equal(aufrufe, 1)
    ablehnen(new Error('Bitte später erneut versuchen.'))
    await warten
    assert.ok(s[art + 'Fuer'].value)
    assert.deepEqual(lesen(s), entwurf)
    assert.match(s[art + 'Fehler'].value, /später/)
    const verwerfen = s[art + 'Schliessen']()
    bestaetigungAntwort(true)
    await verwerfen
  })

  test(`${art}: Erfolg schließt erst nach dem Schreiben und übernimmt Eingaben`, async () => {
    const aufrufe = []
    const s = seite(async (methode, daten) => { aufrufe.push([methode, daten]); return { success: true } })
    oeffnen(s)
    aendern(s)
    await s[art + 'Bestaetigen']()
    assert.equal(s[art + 'Fuer'].value, null)
    const daten = aufrufe[0][1]
    if (art === 'verlaengern') assert.deepEqual(daten, { link_id: 'link-1', gueltig_bis: '2027-02-01', max_anmeldungen: 30 })
    if (art === 'aufnehmen') assert.deepEqual(daten, { anmeldung_id: 'anfrage-1', status: 'Gast', gruppe: 'gruppe-2' })
    if (art === 'ablehnen') assert.deepEqual(daten, { anmeldung_id: 'anfrage-1', grund: 'Keine Plätze mehr' })
    oeffnen(s)
    assert.equal(s[art + 'Fehler'].value, '')
  })
}

test('Aufnehmen erklärt fehlenden Status; Verlängern verwirft ungültige Zahlen nicht als unbegrenzt', async () => {
  let aufrufe = 0
  const s = seite(async () => { aufrufe++; return {} })
  s.aufnehmen(anfrage)
  s.aufnehmenStatus.value = ''
  await s.aufnehmenBestaetigen()
  assert.equal(aufrufe, 0)
  assert.match(s.aufnehmenFehler.value, /Status/)
  for (const zahl of [-1, 1.5, 'keine Zahl']) {
    s.verlaengernOeffnen(link)
    s.verlaengernMax.value = zahl
    await s.verlaengernBestaetigen()
    assert.equal(aufrufe, 0)
    assert.match(s.verlaengernFehler.value, /ganze Zahl/)
  }
})

test('Alle drei Bearbeitungsfenster verdrahten Enter, Esc, Kreuz und Abbrechen mit dem Schutz', () => {
  for (const art of ['verlaengern', 'aufnehmen', 'ablehnen']) {
    assert.match(quelle, new RegExp(`:before-close="${art}Schutz\\.darfSchliessen"`))
    assert.match(quelle, new RegExp(`@click="${art}Schliessen"`))
    assert.match(quelle, new RegExp(`<form[^>]*id="reg-${art}-form"[^>]*@submit\\.prevent="${art}Bestaetigen"`))
    assert.match(quelle, new RegExp(`type="submit" form="reg-${art}-form"`))
  }
  assert.doesNotMatch(quelle, /:disabled="!aufnehmenStatus"/)
})
