/**
 * SEC-11b · WÄCHTER — das Inventar prüft den FUNKTIONSRUMPF, nicht den Namen.
 *
 * BEFUND (Opus-Review SEC-11, HOCH): `tools/whitelist_inventar.py` stufte
 * „lesend" nur nach dem Namen ein. `get_oauth_url` heißt „get" und schreibt
 * trotzdem den OAuth-State nach Redis; `schliesse_mitglied_aus`,
 * `register_mitglied`, `speichere_plan_entwurf`, `submit_registrierung` und
 * `submit_gast` hießen harmlos und nahmen GET an. Ein GET-Link von einer
 * fremden Seite führte sie aus.
 *
 * Dieser Test hält die drei Zusagen der Nachbesserung fest:
 *
 *   F2 — Jede Funktion, deren RUMPF schreibt, ist im Inventar „schreibend"
 *        und trägt `methods=["POST"]` (oder steht mit Begründung in
 *        AUSNAHMEN). Der Wächter liest das INVENTAR (im Image per COPY-Zeile
 *        vorhanden, Regel 13), nicht den Quelltext im Backend.
 *   F3 — Der Schlüssel ist `modul.name`: gleichnamige Funktionen aus zwei
 *        Modulen sind zwei Einträge.
 *   F4 — Die C4-Ausnahme ist eine exakte Namensmenge, kein `website.*`-Präfix.
 *
 * Läuft im Image (backend/Dockerfile, Zeile `tests/sec11b-*.test.mjs`) und
 * lokal: `node --test tests/sec11b-inventar-rumpf.test.mjs`
 */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, existsSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

const WURZEL = new URL('../', import.meta.url)
const INVENTAR = new URL(
  '../backend/src/diakronos_app/frappe_compat/inventar/whitelist.json', WURZEL)
const MITTELWARE = new URL(
  '../backend/src/diakronos_app/frappe_compat/auth_middleware.py', WURZEL)

const INVENTAR_PFAD = fileURLToPath(INVENTAR)
const MITTELWARE_PFAD = fileURLToPath(MITTELWARE)

function inventar() {
  assert.ok(existsSync(INVENTAR_PFAD),
    'inventar/whitelist.json fehlt — tools/whitelist_inventar.py laufen lassen')
  return JSON.parse(readFileSync(INVENTAR_PFAD, 'utf8'))
}

/** Die sechs Nachzügler aus dem Review (F1). */
const NACHzUEGLER = [
  'schliesse_mitglied_aus',
  'register_mitglied',
  'speichere_plan_entwurf',
  'submit_registrierung',
  'submit_gast',
  'get_oauth_url',
]

test('F2: das Inventar enthält einen Rumpfbefund je Funktion', () => {
  const daten = inventar()
  assert.ok(daten.rumpf_zaehlung, 'kein Rumpfbefund im Inventar (altes Format)')
  assert.ok(daten.rumpf_zaehlung.schreibend > 0,
    'der Rumpfbefund findet keine schreibende Funktion — Erkennung kaputt')
  for (const e of daten.eintraege) {
    assert.ok('nach_rumpf' in e, `${e.funktion}: nach_rumpf fehlt`)
    assert.ok('rumpf_grund' in e, `${e.funktion}: rumpf_grund fehlt`)
    assert.ok(['schreibend', 'lesend', 'unbekannt'].includes(e.nach_rumpf),
      `${e.funktion}: unbekannte Einstufung ${e.nach_rumpf}`)
  }
})

test('F2: keine Funktion schreibt im Rumpf, ohne POST zu sein', () => {
  const daten = inventar()
  const ausnahmen = daten.ausnahmen || {}
  const verstoesse = []
  for (const e of daten.eintraege) {
    if (e.nach_rumpf !== 'schreibend') continue
    // SEC-11c (R2): Ausnahmen sind seit dieser Karte nach `modul.name`
    // geschluesselt (vorher der blosse Funktionsname — zwei gleichnamige
    // Endpunkte in verschiedenen Modulen haetten sich eine Ausnahme geteilt).
    if (e.funktion in ausnahmen) continue
    const post = Array.isArray(e.methoden) && e.methoden.includes('POST')
    if (!post) verstoesse.push(`${e.funktion} -> ${JSON.stringify(e.methoden)}`)
  }
  assert.deepEqual(verstoesse, [],
    'SEC-11b/F2: Rumpf schreibt, Methode erlaubt GET:\n  ' + verstoesse.join('\n  '))
})

test('F2: jede Ausnahme ist begründet — und keine ist still', () => {
  const daten = inventar()
  const ausnahmen = daten.ausnahmen || {}
  assert.ok(Object.keys(ausnahmen).length > 0,
    'das Inventar kennt keine Ausnahmen — Format veraltet')
  for (const [name, grund] of Object.entries(ausnahmen)) {
    assert.equal(typeof grund, 'string')
    assert.ok(grund.length > 10, `${name}: keine Begründung im Inventar`)
  }
  // Jede angewandte Ausnahme ist eine lesende Funktion — sonst wäre sie
  // wirkungslos und würde einen echten Verstoß verdecken.
  //
  // SEC-11c (R2/R3): `ausnahmen_angewandt` führt seit dieser Karte
  // `modul.name` (nicht mehr den blossen Namen), und `ausnahme_greift` sagt,
  // ob die Ausnahme einen echten abweichenden Befund deckt. Beides wird hier
  // geprüft — aber OHNE die Einstufung zu erzwingen: eine Ausnahme kann auch
  // einen Endpunkt begründen, dessen Deklaration ohnehin POST verlangt
  // (`logout`, `delete_my_data`); dann ist die Einstufung „schreibend" und die
  // Ausnahme erklärt trotzdem, warum Rumpf/Name allein nicht zählen.
  const eintraege = new Map(daten.eintraege.map((e) => [e.funktion, e]))
  for (const funktion of daten.ausnahmen_angewandt || []) {
    const e = eintraege.get(funktion)
    assert.ok(e, `${funktion}: angewandt, aber nicht im Inventar`)
    assert.equal(e.ausnahme_greift, true,
      `${funktion}: in ausnahmen_angewandt, aber ausnahme_greift ist falsch`)
    assert.ok(e.ausnahme_quelle,
      `${funktion}: greift, nennt aber keine Quelle (rumpf/name/deklaration)`)
    // „Ausnahme greift" statt `methoden_pflicht POST` (R3).
    assert.match(String(e.methoden_pflicht), /^Ausnahme greift/,
      `${funktion}: methoden_pflicht verrät die Ausnahme nicht (${e.methoden_pflicht})`)
  }
  // Ausnahmen, die gar keinen abweichenden Befund mehr decken, stehen
  // ausdrücklich im Inventar (nicht still) — genau das ist die Aussage.
  for (const funktion of daten.ausnahmen_ohne_quelle || []) {
    const e = eintraege.get(funktion)
    assert.ok(e && e.ausnahme, `${funktion}: ohne Quelle, aber ohne Begründung`)
  }
})

test('F1: die sechs Nachzügler sind POST-only', () => {
  const daten = inventar()
  const namen = new Map(daten.eintraege.map((e) => [e.name, e]))
  for (const fn of NACHzUEGLER) {
    const e = namen.get(fn)
    assert.ok(e, `${fn} fehlt im Inventar`)
    assert.deepEqual(e.methoden, ['POST'], `${fn} nimmt noch GET an`)
    assert.equal(e.einstufung, 'schreibend', `${fn} gilt noch als lesend`)
  }
})

test('F2: der Rumpfbefund widerspricht dem Namen — sichtbar, nicht still', () => {
  const daten = inventar()
  const namen = new Map(daten.eintraege.map((e) => [e.name, e]))
  // `get_oauth_url` heißt „lesen" und schreibt — der Musterfall der Karte.
  const oauth = namen.get('get_oauth_url')
  assert.equal(oauth.nach_name, 'lesend', 'Namensbefund für get_oauth_url geändert?')
  assert.equal(oauth.nach_rumpf, 'schreibend', 'Rumpfbefund erkennt das Redis-set nicht')
  assert.match(oauth.rumpf_grund, /set/i,
    `Grund nennt die Schreibung nicht: ${oauth.rumpf_grund}`)
  // Und der umgekehrte Fall: `check_resource_conflict` liest, trägt aber ein
  // Schreibverb im Namen — er muss lesend bleiben und ohne POST erreichbar.
  const check = namen.get('check_resource_conflict')
  assert.ok(check, 'check_resource_conflict fehlt im Inventar')
  assert.notEqual(check.nach_rumpf, 'schreibend',
    `Fehlalarm: check_resource_conflict schreibt angeblich (${check.rumpf_grund})`)
  assert.equal(check.einstufung, 'lesend', 'check_resource_conflict ist nicht mehr lesend')
  assert.equal(check.methoden, null, 'check_resource_conflict trägt jetzt eine Methodenliste')
})

test('F3: Schlüssel sind modul.name — gleichnamige Funktionen bleiben getrennt', () => {
  const daten = inventar()
  const schluessel = daten.eintraege.map((e) => e.funktion)
  assert.equal(new Set(schluessel).size, schluessel.length,
    'doppelte Funktion-Einträge im Inventar')
  const namen = daten.eintraege.map((e) => e.name)
  const doppelt = namen.filter((n, i) => namen.indexOf(n) !== i)
  assert.ok(doppelt.length > 0,
    'keine gleichnamigen Funktionen — der Schlüssel-Test prüft ins Leere')
  for (const n of new Set(doppelt)) {
    const eintraege = daten.eintraege.filter((e) => e.name === n)
    assert.equal(eintraege.length, namen.filter((x) => x === n).length,
      `${n}: Einträge zusammengefallen`)
    assert.equal(new Set(eintraege.map((e) => e.modul)).size, eintraege.length,
      `${n}: Module nicht getrennt`)
  }
  // Der bekannte Fall aus dem Review: `sitzung_status` in zwei Modulen.
  const sitzung = daten.eintraege.filter((e) => e.name === 'sitzung_status')
  assert.ok(sitzung.length >= 2, 'sitzung_status fehlt in einem der Module')
})

test('F4: die C4-Ausnahme ist eine exakte Liste, kein Präfix', () => {
  const text = readFileSync(MITTELWARE_PFAD, 'utf8')
  assert.doesNotMatch(text, /startswith\(\s*["']website\./,
    'C4: der `website.*`-Präfix-Zweig ist wieder da')
  assert.doesNotMatch(text, /startswith\(\s*["']website\.oeffentlich\./,
    'C4: der tote `website.oeffentlich.*`-Zweig ist wieder da')
  assert.match(text, /_OEFFENTLICHE_WEBSITE_NAMEN\s*=\s*frozenset\(\{/,
    'C4: die exakte Namensmenge fehlt')
  for (const name of ['website.kontakt_senden', 'kontakt.kontakt_senden']) {
    assert.ok(text.includes(name), `C4: ${name} fehlt in der Ausnahme`)
  }
})
