/**
 * ON-6d — root-Meldung: die Oberfläche bekommt den Fachtext, nicht den Klassennamen.
 *
 * Befund (Review ON-6c, LOW): ändert ein anderer Administrator eine harmlose
 * Angabe am Mitglied von root (z. B. die Telefonnummer), kommt richtig 403 —
 * aber mit dem Text „…kann es ausschließen“. Der Fachtext entsteht im Backend
 * (ON-6d: eigener Satz je Vorgang); diese Datei hält fest, dass er auch
 * WIRKLICH bis zur Oberfläche durchkommt:
 *
 * 1. Der Vertragskörper der Fehlerantwort trägt den Fachtext in `message`.
 *    `exception`/`exc_type` sind der KLASSENNAME (`PermissionError`) — wer diesen
 *    als Meldung anzeigt, zeigt „PermissionError“ statt „Das Konto der
 *    Hauptverwaltung (root) ist geschützt — du kannst die Telefonnummer nicht
 *    ändern.“ (Der Router prüft genau das: `_fehler_koerper`.)
 * 2. `useApi.js` baut die Meldung aus `message` und fällt NIE auf `exception`
 *    zurück (`daten?.message || daten?.exception` wäre der Klassenname).
 * 3. Der Server schickt Fachtext und keinen Stacktrace (SEC-7/ON-6d: der
 *    Nutzer soll lesen, WAS er nicht darf — nicht, wo es geworfen wurde).
 *
 * Gelesen werden nur Dateien INNERHALB von frontend/ und backend/ (der Stage
 * bekommt beide per COPY — Regel 13, keine zusätzliche COPY-Zeile nötig).
 */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, readdirSync } from 'node:fs'

const lies = (pfad) => readFileSync(new URL('../../' + pfad, import.meta.url), 'utf8')

/** Quelltext ohne Kommentare — Aussagen über „es gibt kein X“ stehen dort. */
const ohneKommentare = (roh) => {
  const ohneBloecke = roh.replace(/\/\*[\s\S]*?\*\//g, '')
  return ohneBloecke.replace(/^\s*\/\/.*$/gm, '')
}

const liesCode = (pfad) => ohneKommentare(lies(pfad))

/**
 * Eine Frontend-Quelle lesen — im Worktree (`frontend/src/diakonos/…`) UND im
 * `/build` des Frontend-Stages (dort flach: `composables/…`, `pages/…`).
 *
 * GESUCHT wird über das Verzeichnis (Stem + Endung), NICHT über einen
 * zusammengesetzten Pfad: die Quellverzeichnisse dieses Projekts sind
 * typografisch „diakonos“ geschrieben, waehrend die Vue-Importe „diakonos“
 * verwenden — ein zusammengesetzter Pfad scheitert je nach Kontext an genau
 * dieser Stelle (Regel 13: derselbe Test muss im Image UND hier gruen sein).
 */
/** Alle Dateien unter ``wurzel`` (rekursiv, ohne node_modules/dist). */
const alleDateien = (wurzel) => {
  const raus = []
  for (const eintrag of readdirSync(wurzel, { withFileTypes: true })) {
    const name = String(eintrag.name)
    if (name === 'node_modules' || name === 'dist' || name === '.git') continue
    const pfad = wurzel + '/' + name
    if (eintrag.isDirectory()) raus.push(...alleDateien(pfad))
    else raus.push(pfad)
  }
  return raus
}

/**
 * Eine Frontend-Quelle lesen — im Worktree (`frontend/src/diakonos/…`) UND im
 * `/build` des Frontend-Stages (dort flach: `composables/…`, `pages/…`).
 *
 * GESUCHT wird über Dateiname + Verzeichnis, NICHT über einen
 * zusammengesetzten Pfad: die Quellverzeichnisse dieses Projekts tragen eine
 * andere Schreibweise, als die Vue-Importe sie nennen — ein zusammengesetzter
 * Pfad scheitert je nach Kontext an genau dieser Stelle (Regel 13: derselbe
 * Test muss im Image UND hier gruen sein).
 */
const frontendDatei = (stem, endung = '.js') => {
  const treffer = alleDateien(new URL('../', import.meta.url).pathname)
    .filter((p) => p.split('/').pop() === stem + endung)
    .sort((a, b) => a.split('/').length - b.split('/').length)
  if (!treffer.length) throw new Error(`nicht gefunden: ${stem}${endung}`)
  return ohneKommentare(readFileSync(treffer[0], 'utf8'))
}

// ── 1. Fehlerkörper: Fachtext in `message` ────────────────────────────────

test('ON-6d: der Fehlerkörper führt den Fachtext in `message`', () => {
  const router = liesCode('backend/src/diakronos_app/frappe_compat/router.py')
  const treffer = router.match(/def _fehler_koerper\([\s\S]*?\n\n/)
  assert.ok(treffer, '_fehler_koerper nicht gefunden')
  assert.ok(treffer[0].includes('"message": str(msg)'),
    'der Körper muss den Fachtext als `message` führen')
  assert.ok(treffer[0].includes('"exception": oeffentlich'),
    '`exception` trägt den Klassennamen (Allowlist), nicht den Fachtext')
})

test('ON-6d: root-Meldungen nennen den Vorgang (nicht überall „ausschließen“)', () => {
  const zugang = liesCode('backend/src/diakronos_app/api/zugang.py')
  assert.ok(zugang.includes('_ROOT_BEARBEITEN_TEXTE'),
    'eigene Bearbeiten-Texte fehlen')
  assert.ok(zugang.includes('"telefon"') && zugang.includes('Telefonnummer'),
    'der Text für die Telefonnummer fehlt')
  assert.ok(zugang.includes('"ausschluss"') && zugang.includes('nicht ausschließen'),
    'der Ausschluss muss seinen eigenen Text behalten')
  // „geschützt“ bleibt in jeder Fassung — daran hängen die ON-6c-Proben.
  assert.ok((zugang.match(/geschützt/g) || []).length >= 3,
    '„geschützt“ muss in allen Meldungen stehen')
})

test('ON-6d: die generische Schranke leitet die Art aus dem Vorgang ab', () => {
  const helper = liesCode('backend/src/diakronos_app/frappe_compat/api_helpers.py')
  assert.ok(helper.includes('_loeschen_art(vorgang, loeschen=loeschen)'),
    'Löschen muss als Löschen gemeldet werden (nicht „bearbeiten“)')
  assert.ok(helper.includes('root_art = "ausschluss"'),
    'der Ausschluss behält seinen eigenen Text')
  assert.ok(helper.includes('root_feld = _root_feld('),
    'das geänderte Feld muss in die Meldung einfließen')
})

// ── 2. Oberfläche zeigt `message`, nicht `exception` ──────────────────────

test('ON-6d: useApi baut die Meldung aus `message`, nie aus `exception`', () => {
  const api = frontendDatei('useApi')
  assert.ok(api.includes('daten?.message'), '`message` wird gelesen')
  assert.ok(!/new Error\([^)]*daten\?\.exception/.test(api),
    'kein Rückfall auf den Klassennamen als Meldung')
  // Der Klassenname bleibt, wo er hingehört: Einstufung im Fehlerkatalog.
  assert.ok(api.includes("error.exc_type = String(daten?.exc_type || daten?.exception || '')"),
    'exc_type bleibt als Kennung erhalten')
})

// ── 3. Lehrer/Administrator liest den Grund, keine Interna ────────────────

test('ON-6d: Meldungstexte sind Du-Form, kurz und ohne Fachbegriffe', () => {
  const zugang = lies('backend/src/diakronos_app/api/zugang.py')
  const texte = [...zugang.matchAll(/"(Das Konto der Hauptverwaltung[\s\S]*?)"/g)]
    .map((m) => m[1].replace(/"\s*\n\s*"/g, ' '))
  assert.ok(texte.length >= 4, `zu wenige Meldungen gefunden: ${texte.length}`)
  for (const text of texte) {
    const klar = text.split(/\s+/).join(' ')
    assert.ok(klar.includes('geschützt'), klar)
    assert.ok(!klar.includes('Root-Benutzer'), `Fachbegriff: ${klar}`)
    assert.ok(!/\bSie /.test(klar), `Sie-Form: ${klar}`)
  }
})
