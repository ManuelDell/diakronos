/**
 * MAIL-1 — Mailversand in der Oberfläche.
 *
 * Geprüft werden die Zusagen der Karte, die man am Quelltext prüfen kann:
 *
 * 1. Der Abschnitt hängt im Admin-Bereich „Einstellungen“ (Adresse, Guard,
 *    Menü) und ruft AUSSCHLIESSLICH die drei vorgesehenen Endpunkte.
 * 2. Das Passwort kommt nie zurück: das Formular hat keine Bindung an einen
 *    vom Server gelieferten Wert, und die Komponente zeigt nur „gesetzt“.
 * 3. „Ohne Verschlüsselung“ bekommt eine deutliche Warnung (S1).
 * 4. Der Absender-Hinweis auf der Datenschutz-Seite verlinkt die Seite und
 *    erscheint nur für System Manager (S5).
 * 5. Die Prüfung im Browser kennt dieselben Grenzen wie der Server (Port,
 *    Zeitlimit, Anmeldung ohne Passwort, „keine“ nur ohne Anmeldung).
 */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import vm from 'node:vm'
import { readFileSync } from 'node:fs'

const lies = (pfad) => readFileSync(new URL('../src/diakonos/' + pfad, import.meta.url), 'utf8')

/** Quelltext ohne Kommentare — Aussagen ueber „es gibt kein X“ stehen dort. */
const liesCode = (pfad) => {
  const roh = lies(pfad)
  const ohneBloecke = roh.replace(/<!--[\s\S]*?-->/g, '').replace(/\/\*[\s\S]*?\*\//g, '')
  return ohneBloecke.replace(/^\s*\/\/.*$/gm, '')
}

// ── 1. Verdrahtung ────────────────────────────────────────────────────────

test('MAIL-1: Router kennt die Adresse und den Admin-Guard', () => {
  const router = lies('router.js')
  assert.ok(router.includes("EinstellungenMailversand: () => import('./pages/Einstellungen.vue')"))
  assert.ok(router.includes("'#/einstellungen/mailversand': 'EinstellungenMailversand'"))
  assert.ok(router.includes("'EinstellungenMailversand',"), 'die Seite steht im Admin-Guard')
})

test('MAIL-1: Menue zaehlt die Seite zum Eintrag Einstellungen', () => {
  assert.ok(lies('menue.js').includes("'EinstellungenMailversand'"))
})

test('MAIL-1: Abschnitt steht im Einstellungsbereich', () => {
  const seite = lies('pages/Einstellungen.vue')
  assert.ok(seite.includes("import('./einstellungen/Mailversand.vue')"))
  assert.ok(seite.includes("href: '#/einstellungen/mailversand'"))
  assert.ok(seite.includes("label: 'Mailversand'"))
})

test('MAIL-1: die Oberflaeche ruft nur die drei Endpunkte', () => {
  const quelle = liesCode('composables/useMailversand.js')
  const aufrufe = [...quelle.matchAll(/apiCall\(([^,)]+)/g)].map(m => m[1].trim())
  assert.ok(aufrufe.length >= 3, `nur ${aufrufe.length} Aufrufe gefunden`)
  for (const aufruf of aufrufe) {
    assert.ok(aufruf.includes('API +'), `Endpunkt zusammengesetzt: ${aufruf}`)
  }
  // MAIL-1b (N4): „Passwort entfernen“ geht ueber denselben Speicher-Endpunkt —
  // deshalb hier die MENGE der Endpunkte, nicht ihre Anzahl.
  const namen = [...new Set(
    [...quelle.matchAll(/apiCall\(API \+ '([a-z_]+)'/g)].map(m => m[1]))].sort()
  assert.deepEqual(namen, ['mailversand_get', 'mailversand_speichern', 'mailversand_testmail'])
})

// ── 2. Passwort ───────────────────────────────────────────────────────────

test('MAIL-1: das Passwort steht nie im Formularzustand des Servers', () => {
  const quelle = liesCode('composables/useMailversand.js')
  // Aus `einstellungen` uebernommen werden nur diese Felder — kein Passwort.
  const block = quelle.slice(quelle.indexOf('function uebernehmen'), quelle.indexOf('async function laden'))
  // Die Zeile, die den Passwort-Status setzt, nennt kein Wertfeld — nur ja/nein.
  const zeile = block.split('\n').find(z => z.includes('passwort_gesetzt')) || ''
  assert.ok(zeile, 'uebernehmen() liest passwort_gesetzt')
  assert.ok(!/passwort\s*:/.test(block), 'uebernehmen() darf keinen Passwortwert setzen')
  assert.ok(!/form\.value\.passwort/.test(block))
})

test('MAIL-1: die Seite zeigt nur „gesetzt“ und bindet kein Passwort', () => {
  const seite = lies('pages/einstellungen/Mailversand.vue')
  assert.ok(seite.includes('type="password"'))
  assert.ok(seite.includes('autocomplete="new-password"'))
  assert.ok(seite.includes('passwortGesetzt'))
  // Kein Ausgeben eines Wertes aus dem Server in das Feld (ein `v-model`
  // wäre die andere Form; `model-value`/`@…` eines Dialogs ist damit nicht
  // gemeint — MAIL-1b hat den Dialog „Passwort entfernen“ ergänzt).
  assert.ok(!/\svalue="[^"]*passwort/i.test(seite))
  // MAIL-1b: `v-model="passwort"` ist erlaubt — das Feld gehoert dem
  // Eingetippten. Verboten bleibt eine Bindung an einen SERVER-Wert
  // (`v-model` auf `form.*`/`einstellungen.*`).
  assert.ok(!/v-model="(form|einstellungen|daten)[^"]*"[^>]*type="password"/i.test(seite))
  // MAIL-1b (N4) hat den Satz um „Gespeichertes Passwort entfernen“ ergänzt —
  // geprueft wird der Kern, nicht die historische Zeile.
  assert.ok(/Ein Passwort ist hinterlegt\. Leer lassen, um es zu behalten\./.test(seite))
})

// ── 3. „keine“ mit deutlicher Warnung ─────────────────────────────────────

test('MAIL-1: ohne Verschluesselung erscheint eine deutliche Warnung', () => {
  const seite = lies('pages/einstellungen/Mailversand.vue')
  assert.ok(seite.includes("form.sicherheit === 'keine'"))
  assert.ok(seite.includes('variant="err"'))
  assert.ok(seite.includes('im Klartext'))
})

// ── 4. Hinweis auf der Admin-Startseite (Datenschutz) ─────────────────────

test('MAIL-1: der Hinweis steht bei den Loeschantraegen und verlinkt die Seite', () => {
  const seite = lies('pages/mitglieder/Datenschutz.vue')
  assert.ok(seite.includes('mailversand_status'))
  assert.ok(seite.includes("href=\"#/einstellungen/mailversand\""))
  assert.ok(seite.includes('Mailversand ist noch nicht eingerichtet'))
  // Nur System Manager koennen ihn abstellen -> nur sie sehen ihn.
  assert.ok(seite.includes('mailversand.darf_aendern'))
})

// ── 5. Prüfung im Browser ─────────────────────────────────────────────────

function ladePruefung() {
  const quelle = liesCode('composables/useMailversand.js')
  const start = quelle.indexOf('export const SICHERHEIT_ARTEN')
  const ende = quelle.indexOf('export function useMailversand')
  // `export` entfernen, damit der Ausschnitt als Ausdruck laeuft; die
  // Konstanten kommen als Rueckgabewert heraus (keine Kopie der Werte).
  const code = quelle.slice(start, ende).replace(/export /g, '')
  const ergebnis = vm.runInNewContext(`(function(){ ${code}; return { SICHERHEIT_ARTEN, leeresFormular } })()`,
    { console })
  return ergebnis
}

test('MAIL-1: drei Verschluesselungsarten mit den ueblichen Ports', () => {
  const { SICHERHEIT_ARTEN } = ladePruefung()
  assert.deepEqual([...SICHERHEIT_ARTEN].map(a => a.wert), ['starttls', 'ssl', 'keine'])
  assert.equal(SICHERHEIT_ARTEN[0].port, 587)
  assert.equal(SICHERHEIT_ARTEN[1].port, 465)
})

test('MAIL-1: die Pruefung im Browser kennt die Grenzen des Servers', () => {
  const quelle = liesCode('composables/useMailversand.js')
  assert.ok(/port < 1 \|\| port > 65535/.test(quelle), 'Port-Grenzen')
  assert.ok(/t < 3 \|\| t > 120/.test(quelle), 'Zeitlimit-Grenzen')
  assert.ok(quelle.includes("f.sicherheit === 'keine' && String(f.benutzername || '').trim()"),
    '„keine“ nur ohne Anmeldung')
  assert.ok(quelle.includes('Für die Anmeldung fehlt das Passwort.'))
  assert.ok(quelle.includes('Bitte den Namen des Mailservers angeben.'))
})
