import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

// Tatsächliches script-setup der Seite mit minimalem Vue-Stub — ohne node_modules.
globalThis.__sdVue = {
  ref: (v) => ({ value: v }),
  reactive: (o) => o,
  computed: (f) => (typeof f === 'function' ? { get value() { return f() } } : f),
  watch: () => {},
  onUnmounted: () => {},
}
globalThis.__sdProps = { plantyp: '', plan: '' }
globalThis.__sdRouten = {}
globalThis.__sdRoute = (key) => globalThis.__sdRouten[key] || ''
globalThis.__sdToast = () => {}
globalThis.__sdFehler = (e) => [{ pfad: '', code: '', meldung: e?.message || 'Fehler', hinweis: '', stufe: 'fehler' }]
globalThis.defineProps = () => globalThis.__sdProps

// API-Grenze: Aufrufe protokollieren, Antworten aus der Folie.
const aufrufe = []
let folie = {}
globalThis.__sdApi = {
  planHolen: async (plan) => { aufrufe.push({ name: 'planHolen', plan }); return folie.plan || {} },
  stammdatenHolen: async (plantyp, plan) => { aufrufe.push({ name: 'stammdatenHolen', plantyp, plan }); return folie.daten() },
  bedarf: async (plantyp, plan) => { aufrufe.push({ name: 'bedarf', plantyp, plan }); return folie.bedarf || [] },
  merkmalePflegen: async (plantyp, werte, plan) => { aufrufe.push({ name: 'merkmalePflegen', plantyp, werte, plan }); return { gruppe_id: 'g1' } },
  sammlungPflegen: async (plantyp, sammlung, eintraege, plan) => {
    aufrufe.push({ name: 'sammlungPflegen', plantyp, sammlung, eintraege, plan })
    return folie.sammlungPflegen ? folie.sammlungPflegen(sammlung, eintraege) : { eintraege: [], gruppe_id: 'g2' }
  },
}

const definition = {
  name: 'Chorplan',
  merkmale: {
    person: [
      { id: 'klavier', name: 'Spielt Klavier', art: 'tag' },
      { id: 'stimmtest', name: 'Stimmtest', art: 'auswahl', werte: ['Sopran', 'Alt', 'Bass'], mehrfach: true },
      { id: 'probeort', name: 'Probeort', art: 'text' },
    ],
    bibelarbeiten: [{ id: 'stelle', name: 'Bibelstelle', art: 'text' }],
  },
  sammlungen: [
    { id: 'bibelarbeiten', name: 'Bibelarbeiten', umfang: 'gemeinde' },
    { id: 'themen', name: 'Themen', umfang: 'plan' },
  ],
}
const personen = [
  { id: 'p1', name: 'Anna A', kuerzel: 'AA', gruppen: ['Chor'], merkmale: { klavier: true } },
  { id: 'p2', name: 'Bernd B', kuerzel: 'BB', gruppen: ['Chor', 'Technik'], merkmale: {} },
  { id: 'p3', name: 'Chris C', kuerzel: 'CC', gruppen: ['Technik'], merkmale: { stimmtest: ['Alt'] } },
]
const sammlungen = {
  bibelarbeiten: [
    { id: 'e1', daten: { titel: 'Psalm 23' }, reihenfolge: 0, aktiv: true, merkmale: { stelle: 'Psalm 23' } },
    { id: 'e2', daten: { titel: 'Jesaja 40' }, reihenfolge: 1, aktiv: true, merkmale: {} },
    { id: 'e3', daten: { titel: 'Alt (inaktiv)' }, reihenfolge: 2, aktiv: false, merkmale: {} },
  ],
  themen: [],
  // Eigene Form mit kennung/titel-Extras (Rückfallform des Servers).
  lieder: [{ kennung: 'l1', titel: 'Advent', merkmale: {} }],
}
folie = {
  daten: () => ({ definition, personen, sammlungen, darf_bearbeiten: true }),
  bedarf: [
    { art: 'merkmal', kennung: 'klavier', abdeckung: '1 Personen mit klavier', detail: '', einstufung: 'eingeschraenkt' },
    { art: 'sammlung', kennung: 'themen', abdeckung: 'Sammlung themen ist leer', detail: '', einstufung: 'blockiert_automatik' },
  ],
  plan: { plan: { plantyp: 'chorplan', titel: 'Chorplan 2026', zeitraum_von: '2026-01-01', zeitraum_bis: '2026-12-31' } },
  sammlungPflegen: (sammlung, eintraege) => ({ eintraege: [{ id: 'e-neu', daten: eintraege[0]?.daten || {} }], gruppe_id: 'g2' }),
}

let code = readFileSync(new URL('../src/diakonos/pages/planrahmen/Stammdaten.vue', import.meta.url), 'utf8')
code = code.split('<script setup>')[1].split('</script>')[0]
code = code.replace(/import[^\n]+from[^\n]+\n/g, '')
code = `const { ref, reactive, computed, watch, onUnmounted } = globalThis.__sdVue
const usePlanrahmen = () => globalThis.__sdApi
const getRouteParam = globalThis.__sdRoute
const showToast = globalThis.__sdToast
const fehlerMeldungen = globalThis.__sdFehler
const datumText = (x) => x
` + code
code += `\nexport { ladenStarten, daten, geladenerTyp, planIdGeladen, planTitel, reiter, suche, gruppeWahl,
  gruppenListe, gefiltertePersonen, personenListe, personenMerkmale, auswahl, auswahlUmschalten, auswahlLeeren,
  alleSichtbarGewaehlt, alleSichtbarenUmschalten, massenMerkmal, massenWert, massenBereit, massenMerkmalDef,
  massenAnwenden, wertAendern, sammlungenListe, sammlungMerkmale, zeilen, zeilenProSammlung, sammlungEditierbar,
  sammlungNeuErlaubt, sammlungReorderbar, sammlungSperrGrund, zeilenUmsortiert, titelAendern, aktivAendern,
  merkmalZeileAendern, neuEingaben, neuEingabe, neuEingabeOeffnen, neuAbbrechen, neuTitelSetzen, neuMerkmalSetzen,
  eintragAnlegen, bedarfOeffnen, bedarfOffen, bedarfListe, bedarfEinrichten, bedarfUeberspringen, uebersprungene,
  hervorhebung, hervorTimer, schreibFehler, seitenFehler, laden, darfBearbeiten, kopfText, titelZusatz, artText,
  sammlungenNormalisieren, eintragNormalisieren, datenNeuLaden };`
const m = await import('data:text/javascript;base64,' + Buffer.from(code).toString('base64'))

// ── Laden über Route '#/planrahmen/stammdaten/<plantyp>' ───────────────────
globalThis.__sdRouten = { plantyp: 'chorplan' }
await m.ladenStarten()
assert.deepEqual(aufrufe[0], { name: 'stammdatenHolen', plantyp: 'chorplan', plan: null })
assert.equal(m.personenMerkmale.value.length, 3, 'Drei Personenmerkmale aus der Definition')
assert.equal(m.darfBearbeiten.value, true)
assert.equal(m.titelZusatz.value, 'Chorplan')
assert.equal(m.artText(m.personenMerkmale.value[0]), 'ja/nein')
assert.equal(m.artText(m.personenMerkmale.value[1]), 'mehrfach')

// ── Suche und Gruppenfilter ────────────────────────────────────────────────
m.suche.value = 'bernd'
assert.deepEqual(m.gefiltertePersonen.value.map((p) => p.id), ['p2'])
m.suche.value = ''
m.gruppeWahl.value = 'Technik'
assert.deepEqual(m.gefiltertePersonen.value.map((p) => p.id), ['p2', 'p3'], 'Gruppenfilter')
m.gruppeWahl.value = ''
assert.deepEqual([...m.gruppenListe.value], ['Chor', 'Technik'])

// ── Einzeländerung einer Person ────────────────────────────────────────────
await m.wertAendern(m.personenListe.value[0], m.personenMerkmale.value[0], false)
let call = aufrufe.findLast((a) => a.name === 'merkmalePflegen')
assert.deepEqual(call.werte, [{ ziel: 'person', schluessel: 'klavier', ziel_id: 'p1', wert: false }])
assert.equal(call.plan, null)

// ── Massenaktion nur mit explizit ausgewählten Personen ────────────────────
m.auswahlUmschalten('p1', true)
m.auswahlUmschalten('p3', true)
assert.equal(m.alleSichtbarGewaehlt.value, false)
m.massenMerkmal.value = 'stimmtest'
m.massenWert.value = ['Sopran']
m.massenBereit.value = true
await m.massenAnwenden()
call = aufrufe.findLast((a) => a.name === 'merkmalePflegen')
assert.equal(call.werte.length, 2, 'Zwei ausgewählte Personen')
assert.deepEqual(call.werte.map((w) => w.ziel_id).sort(), ['p1', 'p3'])
assert.deepEqual(call.werte[0], { ziel: 'person', schluessel: 'stimmtest', ziel_id: 'p1', wert: ['Sopran'] })
assert.equal(m.auswahl.value.size, 0, 'Auswahl wird nach der Massenaktion geleert')
assert.equal(m.massenBereit.value, false)

// ── Auswahl-Logik ──────────────────────────────────────────────────────────
m.alleSichtbarenUmschalten(true)
assert.equal(m.alleSichtbarGewaehlt.value, true)
m.auswahlLeeren()
assert.equal(m.auswahl.value.size, 0)

// ── Sammlungen: Formen und Rechte ──────────────────────────────────────────
const samKeys = m.sammlungenListe.value.map((s) => s.id)
assert.deepEqual(samKeys, ['bibelarbeiten', 'themen', 'lieder'])
const bibel = m.sammlungenListe.value.find((s) => s.id === 'bibelarbeiten')
const themen = m.sammlungenListe.value.find((s) => s.id === 'themen')
const lieder = m.sammlungenListe.value.find((s) => s.id === 'lieder')
assert.equal(m.sammlungEditierbar(bibel), true, 'Gemeinde-Sammlung editierbar')
assert.equal(m.sammlungEditierbar(themen), false, 'Umfang plan ohne Plan: nicht editierbar')
assert.ok(m.sammlungSperrGrund(themen).includes('Vorbereitung'))
assert.equal(lieder.eingebaut, true)
assert.equal(m.sammlungEditierbar(lieder), false, 'Liedstammdaten nicht editierbar')
assert.equal(m.sammlungReorderbar(bibel), true)
assert.deepEqual(m.sammlungMerkmale('bibelarbeiten').map((x) => x.id), ['stelle'])

// Zeilen: 3 Bibelarbeiten + lieder aus kennung-Form, inaktiv bleibt sichtbar
assert.equal(m.zeilen('bibelarbeiten').length, 3)
assert.equal(m.zeilen('bibelarbeiten')[2].aktiv, false, 'Inaktiver Eintrag bleibt sichtbar (reaktivierbar)')
assert.deepEqual(m.zeilen('lieder')[0], {
  id: 'l1', titel: 'Advent', daten: { titel: 'Advent' }, reihenfolge: 0, aktiv: true, merkmale: {},
}, 'kennung/titel-Form normalisiert')
assert.equal(m.zeilen('themen').length, 0)

// ── Titel, aktiv, Merkmale einzelner Zeile ────────────────────────────────
const e1 = m.zeilen('bibelarbeiten')[0]
await m.titelAendern(bibel, e1, 'Psalm 23 neu')
call = aufrufe.findLast((a) => a.name === 'sammlungPflegen')
assert.deepEqual(call.eintraege, [{ id: 'e1', daten: { titel: 'Psalm 23 neu' }, reihenfolge: 0, aktiv: true }])
await m.aktivAendern(bibel, m.zeilen('bibelarbeiten')[2], true)
call = aufrufe.findLast((a) => a.name === 'sammlungPflegen')
assert.equal(call.eintraege[0].aktiv, true, 'Reaktivieren eines inaktiven Eintrags')
await m.merkmalZeileAendern(bibel, m.sammlungMerkmale('bibelarbeiten')[0], e1, 'Psalm 9')
call = aufrufe.findLast((a) => a.name === 'merkmalePflegen')
assert.deepEqual(call.werte, [{ ziel: 'sammlung:bibelarbeiten', schluessel: 'stelle', ziel_id: 'e1', wert: 'Psalm 9' }])

// ── Drag & Drop: alle Zeilen neu nummerieren ───────────────────────────────
const liste = m.zeilen('bibelarbeiten')
liste.push(liste.shift()) // Umsortieren simulieren: erste Zeile wandert ans Ende
await m.zeilenUmsortiert(bibel, { oldIndex: 0, newIndex: 2 })
call = aufrufe.findLast((a) => a.name === 'sammlungPflegen')
assert.equal(call.eintraege.length, 3, 'Alle Zeilen werden mit neuer Reihenfolge gespeichert')
assert.deepEqual(call.eintraege.map((e) => e.reihenfolge), [0, 1, 2])
assert.equal(call.eintraege[2].id, 'e1', 'Umgezogene Zeile liegt an Position 2')
const letzterCall = call
const laengeVorher = aufrufe.length
await m.zeilenUmsortiert(bibel, { oldIndex: 1, newIndex: 1 })
assert.equal(aufrufe.length, laengeVorher, 'Unveränderte Position löst keinen Schreibaufruf aus')
assert.equal(letzterCall.name, 'sammlungPflegen', 'Das eigentliche Umsortieren wurde geschrieben')

// ── Neuer Eintrag: erst sammlung_pflegen, dann merkmale_pflegen ────────────
const vorher = aufrufe.length
m.neuEingabeOeffnen(bibel)
assert.ok(m.neuEingabe(bibel), 'Neueingabe geöffnet')
m.neuTitelSetzen(bibel, 'Psalm 42')
m.neuMerkmalSetzen(bibel, { id: 'stelle' }, '42,1-6')
await m.eintragAnlegen(bibel)
const neuCalls = aufrufe.slice(vorher)
assert.equal(neuCalls[0].name, 'sammlungPflegen', 'Zuerst Sammlungseintrag anlegen')
assert.deepEqual(neuCalls[0].eintraege, [{ daten: { titel: 'Psalm 42' }, reihenfolge: 3, aktiv: true }])
assert.equal(neuCalls[1].name, 'merkmalePflegen', 'Dann Merkmale pflegen')
assert.deepEqual(neuCalls[1].werte, [{ ziel: 'sammlung:bibelarbeiten', schluessel: 'stelle', ziel_id: 'e-neu', wert: '42,1-6' }])
assert.equal(m.neuEingabe(bibel), null, 'Neueingabe nach dem Anlegen geschlossen')

// ── Lieder: nur Merkmale, kein sammlung_pflegen ────────────────────────────
const vorherLied = aufrufe.length
await m.merkmalZeileAendern(lieder, { id: 'test' }, m.zeilen('lieder')[0], 'ja')
assert.equal(aufrufe[vorherLied].name, 'merkmalePflegen')
assert.deepEqual(aufrufe[vorherLied].werte, [{ ziel: 'sammlung:lieder', schluessel: 'test', ziel_id: 'l1', wert: 'ja' }])
assert.equal(aufrufe.slice(vorherLied + 1).some((a) => a.name === 'sammlungPflegen'), false)

// ── Bedarf: öffnen, einrichten (Zielwahl), überspringen ────────────────────
await m.bedarfOeffnen()
assert.equal(m.bedarfOffen.value, true)
assert.equal(m.bedarfListe.value.length, 2)
m.bedarfEinrichten({ art: 'merkmal', kennung: 'klavier' })
assert.equal(m.reiter.value, 'personen')
assert.equal(m.hervorhebung.value, 'mm:klavier')
m.bedarfEinrichten({ art: 'sammlung', kennung: 'bibelarbeiten' })
assert.equal(m.reiter.value, 'sammlungen')
assert.equal(m.hervorhebung.value, 'sam:bibelarbeiten')
m.bedarfUeberspringen({ art: 'merkmal', kennung: 'klavier' })
assert.ok(m.uebersprungene.value.has('merkmal:klavier'))
clearTimeout(m.hervorTimer)

// ── Vorbereitung: '#/planrahmen/vorbereiten/<plan>' → erst plan_holen ──────
globalThis.__sdRouten = { plan: 'plan-1' }
aufrufe.length = 0
await m.ladenStarten()
assert.deepEqual(aufrufe.map((a) => a.name), ['planHolen', 'stammdatenHolen'])
assert.equal(aufrufe[1].plantyp, 'chorplan', 'Plantyp kommt aus plan_holen')
assert.equal(aufrufe[1].plan, 'plan-1')
assert.equal(m.planIdGeladen.value, 'plan-1')
assert.equal(m.planTitel.value, 'Chorplan 2026')
assert.ok(m.kopfText.value.includes('Chorplan 2026'))
const themenMitPlan = m.sammlungenListe.value.find((s) => s.id === 'themen')
assert.equal(m.sammlungEditierbar(themenMitPlan), true, 'Mit Plan-ID ist die plan-Sammlung editierbar')
folie.daten = () => ({ definition, personen, sammlungen, darf_bearbeiten: true, darf_globale_stammdaten_bearbeiten: false })
await m.ladenStarten()
assert.equal(m.sammlungEditierbar(themenMitPlan), true, 'Planverantwortung erlaubt die eigene Plansammlung')
assert.equal(m.sammlungEditierbar(bibel), false, 'Planverantwortung erteilt keine globalen Schreibrechte')
const vorGlobal = aufrufe.length
await m.wertAendern(personen[0], {id:'klavier'}, false)
assert.equal(aufrufe.length, vorGlobal, 'Globale Personenmerkmale sind auch im UI gesperrt')

// Eine Nachladeantwort aus dem alten Plan darf einen neu geladenen Typ nicht überschreiben.
let antwortAlt
folie.daten = () => new Promise(resolve => { antwortAlt = resolve })
const altNachladen = m.datenNeuLaden()
folie.daten = () => ({ definition: {...definition, name:'Neuer Kontext'}, personen:[], sammlungen:{} })
globalThis.__sdRouten = {plantyp:'neuer-kontext'}
await m.ladenStarten()
antwortAlt({definition, personen, sammlungen})
await altNachladen
assert.equal(m.daten.value.definition.name, 'Neuer Kontext')

// ── Schreibschutz ohne Bearbeitungsrecht ──────────────────────────────────
globalThis.__sdRouten = { plantyp: 'chorplan' }
folie.daten = () => ({ definition, personen, sammlungen, darf_bearbeiten: false })
await m.ladenStarten()
assert.equal(m.darfBearbeiten.value, false)
assert.equal(m.sammlungEditierbar(m.sammlungenListe.value.find((s) => s.id === 'bibelarbeiten')), false)

console.log('Planrahmen-Stammdaten: Route/Props, Matrix, Massenaktion, Sammlungen, Drag&Drop, Neueingabe, Bedarf, Vorbereitung bestanden')
