/**
 * SEC-11c · WÄCHTER — die Restpunkte der Inventar-Prüfung (Opus-Review SEC-11b).
 *
 * Diese Datei hält die drei Zusagen der Karte fest, die im INVENTAR sichtbar
 * sein müssen (nicht nur im Backend-Test), weil Frontend und Betrieb dieselbe
 * Datei lesen:
 *
 *   R1 — Die AST-Erkennung (`tools/whitelist_lesen.py`) sieht auch die
 *        Schreiber, deren Wirkung in einem IMPORTIERTEN `diakronos_app.*`-Helfer
 *        steht (früher „offen", weil das Inventar nur das eigene Modul und eine
 *        Namensliste kannte). Geprüft wird an benannten Fällen, nicht an einer
 *        Zahl, die sich beim nächsten Feature verschiebt.
 *   R2 — Ausnahmen sind nach `modul.name` geschlüsselt. Zwei gleichnamige
 *        Endpunkte in verschiedenen Modulen (`logout`) dürfen sich KEINE
 *        Ausnahme teilen.
 *   R3 — Ausnahmen tragen „Ausnahme greift (<quelle>)" statt einer
 *        `methoden_pflicht` von „POST": ein begründeter Leser muss nicht als
 *        „hier fehlt POST" erscheinen.
 *
 * Läuft im Image (backend/Dockerfile, Zeile `tests/sec11c-*.test.mjs`) und
 * lokal: `node --test tests/sec11c-inventar-restpunkte.test.mjs`
 */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, existsSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

const WURZEL = new URL('../', import.meta.url)
const INVENTAR = new URL(
  '../backend/src/diakronos_app/frappe_compat/inventar/whitelist.json', WURZEL)
const INVENTAR_PFAD = fileURLToPath(INVENTAR)

function inventar() {
  assert.ok(existsSync(INVENTAR_PFAD),
    'inventar/whitelist.json fehlt — tools/whitelist_inventar.py laufen lassen')
  return JSON.parse(readFileSync(INVENTAR_PFAD, 'utf8'))
}

function eintrag(daten, funktion) {
  const e = daten.eintraege.find((x) => x.funktion === funktion)
  assert.ok(e, `${funktion} fehlt im Inventar`)
  return e
}

// ── R1: importierte Helfer werden erkannt ────────────────────────────────

test('R1: Schreiber über einen importierten diakronos_app-Helfer sind erkannt', () => {
  const daten = inventar()
  // Die drei Musterfälle der Karte. Ihr Rumpf ruft einen Helfer aus einem
  // NACHBARMODUL, dessen Schreibung erst die Import-Verfolgung sichtbar macht:
  //   mailversand_speichern -> smtp_einstellungen.speichern  (session.add)
  //   sicherung_jetzt       -> lauf.fuehre_aus               (schreibt Dump+DB)
  //   sitzung_starten       -> devmodus.dienste.sitzung_starten (sitzung.add)
  for (const funktion of [
    'diakronos_app.api.mailversand.mailversand_speichern',
    'diakronos_app.api.sicherung.sicherung_jetzt',
    'diakronos_app.devmodus.api.sitzung_starten',
  ]) {
    const e = eintrag(daten, funktion)
    assert.equal(e.nach_rumpf, 'schreibend',
      `${funktion}: Rumpf-Befund erkennt den importierten Helfer nicht ` +
      `(${e.rumpf_grund || 'ohne Grund'})`)
    assert.ok(e.rumpf_grund && e.rumpf_grund.length > 0,
      `${funktion}: schreibend ohne Begründung`)
  }
})

test('R1: ein Präfix allein macht keine falsche Schreibung aus einem Leser', () => {
  const daten = inventar()
  // Gegenprobe: `get_*`-Leser mit Schreibverben im Namen bleiben lesend ohne
  // POST. `get_offene_aenderungen` liegt im Planrahmen und liest.
  const leser = daten.eintraege.filter(
    (e) => e.name.startsWith('get_') && e.nach_rumpf === 'lesend')
  assert.ok(leser.length > 0,
    'kein einziger get_*-Leser im Inventar — die Erkennung ist blind geworden')
  for (const e of leser) {
    assert.notEqual(e.methoden_pflicht, 'POST',
      `${e.funktion}: Leser verlangt plötzlich POST`)
  }
})

// ── R2: Schlüssel ist modul.name ─────────────────────────────────────────

test('R2: jede Ausnahme ist mit einem MODULPFAD geschlüsselt', () => {
  const daten = inventar()
  const ausnahmen = Object.keys(daten.ausnahmen || {})
  assert.ok(ausnahmen.length > 0, 'das Inventar kennt keine Ausnahmen')
  for (const schluessel of ausnahmen) {
    assert.ok(schluessel.includes('.'),
      `${schluessel}: kein 'modul.name' — ein blosser Name teilt die Ausnahme ` +
      'zwischen gleichnamigen Modulen')
    assert.ok(schluessel.startsWith('diakronos_app.'),
      `${schluessel}: Modulpfad ausserhalb von diakronos_app`)
  }
})

test('R2: gleichnamige Funktionen teilen sich keine Ausnahme', () => {
  const daten = inventar()
  // `logout` gibt es in `api.auth` und `api.frappe_core`. Eine Ausnahme fuer
  // den einen darf den anderen nicht freistellen — genau das war mit dem
  // blossen Namen möglich.
  const logout = daten.eintraege.filter((e) => e.name === 'logout')
  assert.ok(logout.length >= 2,
    'die beiden logout-Endpunkte fehlen — der Fall ist nicht mehr geprüft')
  const mitAusnahme = logout.filter((e) => e.ausnahme)
  assert.ok(mitAusnahme.length < logout.length,
    'ALLE logout-Endpunkte tragen eine Ausnahme — die Trennung wirkt nicht')
})

// ── R3: „Ausnahme greift" statt methoden_pflicht POST ────────────────────

test('R3: begründete Ausnahmen tragen „Ausnahme greift (<quelle)"', () => {
  const daten = inventar()
  const angewandt = daten.ausnahmen_angewandt || []
  assert.ok(angewandt.length > 0,
    'keine angewandte Ausnahme — Format veraltet oder alle Ausnahmen tot')
  for (const funktion of angewandt) {
    const e = eintrag(daten, funktion)
    assert.equal(e.ausnahme_greift, true,
      `${funktion}: in ausnahmen_angewandt, aber ausnahme_greift fehlt`)
    assert.match(String(e.methoden_pflicht), /^Ausnahme greift/,
      `${funktion}: methoden_pflicht nennt die Ausnahme nicht ` +
      `(${e.methoden_pflicht})`)
    assert.match(String(e.methoden_pflicht),
      /\((rumpf|name|deklaration|rumpf, name|name, rumpf)/,
      `${funktion}: Quelle der Ausnahme fehlt (${e.methoden_pflicht})`)
    assert.ok(['konfig', 'sperre', 'name', 'rueckkanal', 'schranke',
      'nur_vorschau'].includes(e.ausnahme_art),
      `${funktion}: unbekannte Ausnahme-Art ${e.ausnahme_art}`)
  }
})

test('R3: Ausnahmen ohne Quelle stehen sichtbar, nicht still', () => {
  const daten = inventar()
  // `fail_validation` deckt heute keinen abweichenden Befund mehr (Rumpf und
  // Name lesen). Das ist erlaubt — aber es muss IM INVENTAR stehen, damit es
  // niemand fuer eine wirksame Ausnahme haelt.
  assert.ok(Array.isArray(daten.ausnahmen_ohne_quelle),
    'Feld ausnahmen_ohne_quelle fehlt — Inventar veraltet')
  for (const funktion of daten.ausnahmen_ohne_quelle) {
    const e = eintrag(daten, funktion)
    assert.ok(e.ausnahme, `${funktion}: ohne Quelle, aber ohne Begründung`)
    assert.notEqual(e.ausnahme_greift, true,
      `${funktion}: ohne Quelle, aber als greifend ausgewiesen`)
  }
})

test('R3: offene Widersprueche sind eine kurze, benannte Liste', () => {
  const daten = inventar()
  assert.ok(Array.isArray(daten.widersprueche), 'Feld widersprueche fehlt')
  const offen = daten.widersprueche.filter((w) => w.offen)
  // SEC-11b hatte 38 offene Widersprueche (nur per Name erkannt). Nach R1
  // bleiben die Fälle übrig, in denen sich Rumpf und Name WIDERSPRECHEN — das
  // ist eine Aussage über den Code und braucht eine Entscheidung, keine
  // Ausnahme. Die Grenze ist bewusst eine Zahl: wächst sie, hat jemand einen
  // neuen Schreiber gebaut, dessen Methode nicht dazu passt.
  assert.ok(offen.length <= 3,
    `${offen.length} offene Widersprueche (vorher 1): ` +
    offen.map((w) => w.funktion).join(', '))
  for (const w of offen) {
    assert.ok(w.methoden, `${w.funktion}: offener Widerspruch ohne Methodenangabe`)
  }
})
