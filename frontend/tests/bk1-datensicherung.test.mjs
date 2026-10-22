/**
 * BACKUP-1 — Datensicherung in der Oberfläche.
 *
 * Geprüft werden die Zusagen der Karte, die man am Quelltext prüfen kann:
 *
 * 1. Der Abschnitt hängt im Admin-Bereich „Einstellungen“ (Adresse, Guard,
 *    Menü) und ruft AUSSCHLIESSLICH die vier vorgesehenen Endpunkte.
 * 2. Kein Herunterladen, kein Wiederherstellen über die Oberfläche.
 * 3. „Löschen“ fragt über `bestaetigen()` nach — kein `confirm()`.
 * 4. Der Hinweis zur DSGVO-Frist steht im Text.
 * 5. Aufbewahrung ist Pflicht mit Minimum 1 (auch im Browser geprüft).
 * 6. Der zusammengebaute API-Helfer (composables/useSicherung.js) prüft
 *    Grenzen, bevor er den Server fragt — und schickt die erwarteten Felder.
 */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import vm from 'node:vm'
import { readFileSync } from 'node:fs'

const lies = (pfad) => readFileSync(new URL('../src/diakonos/' + pfad, import.meta.url), 'utf8')

/** Quelltext ohne Kommentare — Aussagen ueber "es gibt kein X" stehen dort. */
const liesCode = (pfad) => {
  const roh = lies(pfad)
  // Blockkommentare und Zeilenkommentare entfernen (kein Kommentar im Code
  // enthaelt ein "*/" oder ein Anfuehrungszeichen, das hier stoeren wuerde).
  const ohneBloecke = roh.replace(/<!--[\s\S]*?-->/g, '').replace(/\/\*[\s\S]*?\*\//g, '')
  return ohneBloecke.replace(/^\s*\/\/.*$/gm, '')
}

// ── 1. Verdrahtung ────────────────────────────────────────────────────────

test('BACKUP-1: Router kennt die Adresse und den Admin-Guard', () => {
  const router = lies('router.js')
  assert.ok(router.includes("EinstellungenDatensicherung: () => import('./pages/Einstellungen.vue')"))
  assert.ok(router.includes("'#/einstellungen/datensicherung': 'EinstellungenDatensicherung'"))
  assert.ok(router.includes("'EinstellungenDatensicherung',"),
    'die Seite steht im Admin-Guard')
})

test('BACKUP-1: Menue zaehlt die Seite zum Eintrag Einstellungen', () => {
  const menue = lies('menue.js')
  assert.ok(menue.includes("'EinstellungenDatensicherung'"))
})

test('BACKUP-1: Abschnitt steht im Einstellungsbereich', () => {
  const seite = lies('pages/Einstellungen.vue')
  assert.ok(seite.includes("import('./einstellungen/Datensicherung.vue')"))
  assert.ok(seite.includes("href: '#/einstellungen/datensicherung'"))
  assert.ok(seite.includes("label: 'Datensicherung'"))
})

// ── 2. Nur die vorgesehenen Endpunkte, kein Download ───────────────────────

test('BACKUP-1: die Oberflaeche ruft nur die vier Endpunkte', () => {
  const quelle = lies('composables/useSicherung.js')
  const aufrufe = [...quelle.matchAll(/apiCall\(([^,)]+)/g)].map(m => m[1].trim())
  assert.ok(aufrufe.length >= 4)
  for (const aufruf of aufrufe) {
    assert.ok(aufruf.includes('API +'), `Endpunkt zusammengesetzt: ${aufruf}`)
  }
  const namen = [...quelle.matchAll(/API \+ '(\w+)'/g)].map(m => m[1]).sort()
  assert.deepEqual(namen, [
    'sicherung_einstellungen_speichern',
    'sicherung_get',
    'sicherung_jetzt',
    'sicherung_loeschen',
  ])
})

test('BACKUP-1: kein Herunterladen und kein Wiederherstellen in der Oberflaeche', () => {
  for (const datei of ['composables/useSicherung.js', 'pages/einstellungen/Datensicherung.vue']) {
    const code = liesCode(datei)
    assert.ok(!/herunterladen|download|wiederherstell|restore/i.test(code),
      `${datei} darf keinen Download/Wiederherstellen-Weg enthalten`)
    assert.ok(!/blob:|createObjectURL|window\.open/i.test(code), 'kein Datei-Ausliefern')
  }
})

// ── 3./4./5. Loeschen mit Rueckfrage, Hinweise, Grenzen ───────────────────

test('BACKUP-1: Loeschen fragt nach — ueber bestaetigen(), nicht confirm()', () => {
  const seite = lies('pages/einstellungen/Datensicherung.vue')
  assert.ok(seite.includes("from '../../composables/useBestaetigen.js'"))
  assert.ok(seite.includes('await bestaetigen('))
  assert.ok(!/\bconfirm\s*\(/.test(liesCode('pages/einstellungen/Datensicherung.vue')),
    'kein Browser-confirm()')
  assert.ok(seite.includes('gefahr: true'), 'Loeschen ist als gefaehrlich markiert')
})

test('BACKUP-1: Hinweis auf die DSGVO-Frist steht in der Oberflaeche', () => {
  const seite = lies('pages/einstellungen/Datensicherung.vue')
  assert.ok(/DSGVO/.test(seite))
  assert.ok(/Aufbewahrung/.test(seite))
  assert.ok(/neueste Sicherung wird nie gelöscht/i.test(seite),
    'die Ausnahme "neueste bleibt" muss dastehen')
})

test('BACKUP-1: Aufbewahrung ist Pflichtfeld mit Minimum 1', () => {
  const seite = lies('pages/einstellungen/Datensicherung.vue')
  assert.ok(seite.includes('min="1"'))
  assert.ok(seite.includes('max="3650"'))
  assert.ok(seite.includes('required'))
})

// ── 6. Der API-Helfer (ausgefuehrt in einer VM) ───────────────────────────

function baueHelfer(apiCall) {
  const quelle = lies('composables/useSicherung.js')
  const ctx = vm.createContext({ ref: wert => ({ value: wert }), apiCall })
  vm.runInContext(
    quelle.replace(/^import .*$/gm, '')
      .replace('export function useSicherung', 'function useSicherung')
      .replace('export function groesseText', 'function groesseText')
      .replace('export function zeitpunktText', 'function zeitpunktText')
      .replace('export function statusText', 'function statusText')
      + '\nglobalThis.h = useSicherung()'
      + '\nglobalThis.groesseText = groesseText'
      + '\nglobalThis.zeitpunktText = zeitpunktText'
      + '\nglobalThis.statusText = statusText',
    ctx,
  )
  return ctx
}

const antwort = {
  einstellungen: { automatisch: true, uhrzeit: '03:00', aufbewahrung_tage: 30 },
  sicherungen: [
    { name: '2026-10-20_030000', zeitpunkt: '2026-10-20T03:00:00', groesse_bytes: 4096,
      status: 'ok', ausloeser: 'automatisch', meldung: '' },
  ],
  ablage: { benutzbar: true, hinweis: '', vorhanden: 1 },
}

test('BACKUP-1: Laden uebernimmt Einstellungen, Liste und Ablagezustand', async () => {
  const calls = []
  const { h } = baueHelfer(async (m, d) => {
    calls.push([m, d])
    return antwort
  })
  assert.equal(await h.laden(), true)
  assert.equal(calls[0][0], 'diakronos.diakonos.api.sicherung.sicherung_get')
  assert.equal(h.geladen.value, true)
  assert.equal(h.automatisch.value, true)
  assert.equal(h.uhrzeit.value, '03:00')
  assert.equal(h.aufbewahrungTage.value, 30)
  assert.equal(h.sicherungen.value.length, 1)
  assert.equal(h.ablage.value.benutzbar, true)
})

test('BACKUP-1: Speichern schickt genau die drei Felder', async () => {
  const calls = []
  const { h } = baueHelfer(async (m, d) => {
    calls.push([m, d])
    return { gespeichert: true, einstellungen: { automatisch: false, uhrzeit: '04:15', aufbewahrung_tage: 7 } }
  })
  h.aufbewahrungTage.value = 7
  h.uhrzeit.value = '04:15'
  h.automatisch.value = false
  assert.equal(await h.einstellungenSpeichern(), true)
  assert.equal(calls[0][0], 'diakronos.diakonos.api.sicherung.sicherung_einstellungen_speichern')
  // `deepEqual` (nicht `deepStrictEqual`): das Objekt kommt aus dem
  // VM-Kontext und hat dort einen anderen Object-Prototyp.
  assert.deepEqual({ ...calls[0][1] },
    { automatisch: false, uhrzeit: '04:15', aufbewahrung_tage: 7 })
})

test('BACKUP-1: 0 Tage und kaputte Uhrzeit werden VOR dem Server abgelehnt', async () => {
  const calls = []
  const { h } = baueHelfer(async (m, d) => {
    calls.push([m, d])
    return {}
  })
  h.aufbewahrungTage.value = 0
  assert.equal(await h.einstellungenSpeichern(), false)
  assert.match(h.fehler.value, /mindestens 1 Tag/)
  h.aufbewahrungTage.value = 30
  h.uhrzeit.value = '25:00'
  assert.equal(await h.einstellungenSpeichern(), false)
  assert.match(h.fehler.value, /HH:MM/)
  assert.equal(calls.length, 0, 'kein Aufruf bei offensichtlichem Fehler')
})

test('BACKUP-1: Jetzt sichern meldet Erfolg mit Groesse und laedt die Liste neu', async () => {
  const calls = []
  const { h } = baueHelfer(async (m, d) => {
    calls.push([m, d])
    if (m.endsWith('sicherung_jetzt')) {
      return { ok: true, name: '2026-10-20_030000', status: 'ok',
        meldung: 'Sicherung vollstaendig.', groesse_bytes: 2048, entfernt: [] }
    }
    return antwort
  })
  assert.equal(await h.jetztSichern(), true)
  assert.equal(calls[0][0], 'diakronos.diakonos.api.sicherung.sicherung_jetzt')
  assert.match(h.erfolg.value, /Sicherung fertig/)
  assert.equal(calls.at(-1)[0], 'diakronos.diakonos.api.sicherung.sicherung_get')
})

test('BACKUP-1: Fehlschlag beim Sichern zeigt die Servermeldung', async () => {
  const { h } = baueHelfer(async (m) => {
    if (m.endsWith('sicherung_jetzt')) {
      // `apiCall` liefert `{ message: <Rueckgabe des Endpunkts> }`.
      return { message: { ok: false, status: 'fehlgeschlagen',
        meldung: 'Der Datenbank-Dump ist fehlgeschlagen (Exit 1).', groesse_bytes: 0 } }
    }
    return antwort
  })
  assert.equal(await h.jetztSichern(), false)
  assert.match(h.fehler.value, /Datenbank-Dump/)
})

test('BACKUP-1: Loeschen schickt den Namen und laedt neu', async () => {
  const calls = []
  const { h } = baueHelfer(async (m, d) => {
    calls.push([m, d])
    if (m.endsWith('sicherung_loeschen')) return { geloescht: true, name: d.name }
    return antwort
  })
  assert.equal(await h.loeschen('2026-10-19_030000'), true)
  assert.equal(calls[0][0], 'diakronos.diakonos.api.sicherung.sicherung_loeschen')
  assert.deepEqual({ ...calls[0][1] }, { name: '2026-10-19_030000' })
})

test('BACKUP-1: Groessen- und Zeitangaben sind lesbar', () => {
  const { groesseText, zeitpunktText, statusText } = baueHelfer(async () => ({}))
  assert.equal(groesseText(0), '—')
  assert.equal(groesseText(512), '512 Byte')
  assert.equal(groesseText(2048), '2.0 KB')
  assert.equal(groesseText(5 * 1024 * 1024), '5.0 MB')
  assert.equal(groesseText(40 * 1024 * 1024), '40 MB')
  assert.equal(zeitpunktText('2026-10-20_030000'), '20.10.2026, 03:00 Uhr')
  assert.equal(zeitpunktText('2026-10-20T03:00:00'), '20.10.2026, 03:00 Uhr')
  assert.equal(zeitpunktText(''), '—')
  assert.equal(statusText('ok').wort, 'Fertig')
  assert.equal(statusText('fehlgeschlagen').wort, 'Fehlgeschlagen')
  assert.equal(statusText('laeuft').wort, 'Läuft gerade')
})
