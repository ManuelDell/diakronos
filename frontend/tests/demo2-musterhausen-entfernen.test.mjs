/**
 * DEMO-2 — Demo-Seed „Musterhausen": Loeschen unter PostgreSQL und
 * Moderator-/Prediger-Felder.
 *
 * Zwei Befunde aus dem Dev-Modus:
 *
 *  1. `tools/demo/musterhausen.py --entfernen` sei unter PostgreSQL an
 *     Fremdschluesseln gescheitert. Reproduziert (wegwerf-PostgreSQL, scharfe
 *     FKs): musikalische Untergruppen zeigten auf die Dachgruppe „Musikteams",
 *     `ressourcen_buchung.moderiert_von` und `audit_log.actor` auf die
 *     Demo-Konten. Die Tests dazu stehen in
 *     `backend/tests/test_demo2_entfernen_pg.py` (echtes PostgreSQL).
 *  2. Moderator-/Prediger-Felder im Gottesdienst-Ablauf wurden beim Seed
 *     abgelehnt: das Skript schrieb den ANZEIGENAMEN („Anna Beispiel") in ein
 *     Personenfeld, `eintrag_setzen` erwartet die SERVER-Kennung (ID-1d) und
 *     antwortete „Unbekannte Person, Gruppe oder Sammlungseintrag.".
 *
 * SQLite-Testlaeufe sehen Befund 1 nicht (Fremdschluessel sind dort
 * standardmaessig aus) — dieser Waechter haelt die Ursachen deshalb im
 * QUELLTEXT fest: keine Personenfelder mit Anzeigenamen, Untergruppen vor der
 * Dachgruppe, Konten erst nach ihren Verweisen.
 *
 * Lauf: node --test (siehe backend/Dockerfile, Frontend-Stage).
 */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HIER = dirname(fileURLToPath(import.meta.url))

/** Im REPO liegt die Datei unter <wurzel>/tools/, im IMAGE unter /tools/. */
function seedQuelltext() {
  for (const pfad of [
    join(HIER, '..', '..', 'tools', 'demo', 'musterhausen.py'),
    '/tools/demo/musterhausen.py',
  ]) {
    try {
      return readFileSync(pfad, 'utf8')
    } catch {
      // naechster Ort
    }
  }
  throw new Error('tools/demo/musterhausen.py weder im Repo noch unter /tools')
}

const SEED = seedQuelltext()

/** Der Rumpf einer Top-Level-Funktion (bis zur naechsten `\ndef ` bzw. EOF). */
function funktion(name) {
  const start = SEED.indexOf(`\ndef ${name}(`)
  assert.notEqual(start, -1, `Funktion ${name} fehlt im Seed-Skript`)
  const rest = SEED.slice(start + 1)
  const ende = rest.indexOf('\ndef ')
  return ende === -1 ? rest : rest.slice(0, ende)
}

// ── Befund 2: Personenfelder tragen die Server-Kennung ─────────────────────

test('DEMO-2 · Moderator im Ablauf wird als Personen-Kennung gesetzt', () => {
  const rumpf = funktion('plan_besetzen_und_veroeffentlichen')
  assert.match(
    rumpf,
    /\.moderator"\)[\s\S]{0,300}?wert = person_kennung\(/,
    'Moderator-Felder muessen person_kennung(...) verwenden (Anzeigename wird abgelehnt)')
})

test('DEMO-2 · Prediger im Ablauf wird als Personen-Kennung gesetzt', () => {
  const rumpf = funktion('plan_besetzen_und_veroeffentlichen')
  assert.match(
    rumpf,
    /\.prediger"\)[\s\S]{0,300}?wert = person_kennung\(/,
    'Prediger-Felder muessen person_kennung(...) verwenden (Anzeigename wird abgelehnt)')
})

test('DEMO-2 · kein Personenfeld bekommt einen rohen Anzeigenamen', () => {
  const rumpf = funktion('plan_besetzen_und_veroeffentlichen')
  // Die Merkmalslisten selbst sind Anzeigenamen — sie duerfen nur durch
  // `person_kennung(...)` gehen.
  for (const feld of ['moderatoren', 'prediger', 'dirigenten', 'klaviere', 'einsingen']) {
    for (const m of rumpf.matchAll(new RegExp(`wert = ${feld}\\[[^\\]]*\\]`, 'g'))) {
      const danach = rumpf.slice(m.index, m.index + 600)
      assert.ok(danach.includes('person_kennung('),
        `Anzeigename landet direkt im Personenfeld (${feld} bei Zeichen ${m.index})`)
    }
  }
})

// ── Befund 1: Loeschreihenfolge ────────────────────────────────────────────

test('DEMO-2 · Untergruppen verschwinden vor ihrer Dachgruppe', () => {
  const rumpf = funktion('entfernen')
  const unter = rumpf.indexOf('DELETE FROM untergruppe WHERE name IN')
  assert.notEqual(unter, -1, 'Untergruppen werden nicht (als Statement) geloescht')
  // Nicht auf die erste Erwaehnung von MUSIKTEAMS_OBERGRUPPE pruefen: die
  // Bindung `_og` steht seit der Nacharbeit VOR den DELETEs. Massgeblich ist
  // das Loeschen der Dachgruppe selbst (`session.get(Gruppe, …)`).
  const dach = rumpf.indexOf('session.get(Gruppe, daten.MUSIKTEAMS_OBERGRUPPE)')
  assert.notEqual(dach, -1, 'Dachgruppe wird nicht geloescht')
  assert.ok(unter < dach,
    'untergruppe.gruppe zeigt auf die Dachgruppe — sie muss VOR ihr weg sein (untergruppe_gruppe_fkey)')
})

test('DEMO-2 · alle vier Demo-Ressourcenbuchungen werden entfernt', () => {
  const rumpf = funktion('entfernen')
  const anlegen = funktion('ressourcenbuchungen_anlegen')
  const namen = [...anlegen.matchAll(/\("(buchung-[a-z]+)"/g)].map(m => m[1])
  assert.ok(namen.length >= 4, `nur ${namen.length} Buchungen im Seed gefunden`)
  for (const name of namen) {
    assert.ok(rumpf.includes(name),
      `${name} wird angelegt, aber von --entfernen nicht geloescht (ressourcen_buchung.moderiert_von -> user)`)
  }
})

test('DEMO-2 · Verweise auf die Demo-Konten sind vor deren Loeschung geloest', () => {
  const rumpf = funktion('entfernen')
  const kontoWeg = rumpf.indexOf('session.get(User, email)')
  assert.notEqual(kontoWeg, -1, 'Konten werden nicht geloescht')
  for (const [tabelle, spalte] of [
    ['audit_log', 'actor'],
    ['notification_log', 'for_user'],
    ['RessourcenBuchung', null],
  ]) {
    const stelle = rumpf.indexOf(tabelle)
    assert.notEqual(stelle, -1, `${tabelle} wird vor den Konten nicht aufgeraeumt`)
    assert.ok(stelle < kontoWeg, `${tabelle} muss VOR der Konten-Loeschung aufgeraeumt werden`)
    if (spalte) {
      assert.ok(rumpf.includes(spalte), `${tabelle}.${spalte} wird nicht behandelt`)
    }
  }
})

test('DEMO-2 · Untergruppen-Loeschung ist auf die Musikteam-Dachgruppe begrenzt', () => {
  // „Gruppe 3“ ist ein allgemeiner Name. Ohne die Bedingung auf
  // `gruppe = Musikteams` wuerde eine gleichnamige ECHTE Untergruppe einer
  // fremden Gruppe mitgeloescht (Review zur Nacharbeit).
  const rumpf = funktion('entfernen')
  assert.match(rumpf, /DELETE FROM untergruppe WHERE name IN :p AND gruppe = :og/,
    'untergruppe-Loeschung ohne `AND gruppe = :og` — fremde Untergruppen waeren betroffen')
  assert.ok(rumpf.includes('daten.MUSIKTEAMS_OBERGRUPPE'),
    'die Dachgruppe muss als Bindung `og` gesetzt werden')
  // Auch die Kindzeilen haengen an derselben Einschraenkung (Subselect).
  for (const tabelle of ['untergruppenmitgliedschaft', 'untergruppe_verantwortlicher']) {
    const stelle = rumpf.indexOf(`DELETE FROM ${tabelle}`)
    assert.notEqual(stelle, -1, `${tabelle} wird nicht geloescht`)
    const umfeld = rumpf.slice(stelle, stelle + 300)
    assert.ok(umfeld.includes('SELECT name FROM untergruppe WHERE name IN :p AND gruppe = :og'),
      `${tabelle} haengt nicht an der Dachgruppen-Bedingung (Subselect noetig)`)
  }
})

test('DEMO-2 · Konten werden nur angefasst, wenn sie zur Demo gehoeren', () => {
  const rumpf = funktion('entfernen')
  const pruefung = rumpf.indexOf('pruefe_demo_konten(session)')
  assert.notEqual(pruefung, -1, 'entfernen() prueft die Demo-Merkmale der Konten nicht')
  // Die Pruefung muss VOR dem ersten Loeschen laufen.
  assert.ok(pruefung < rumpf.indexOf('session.delete(instanz)'),
    'pruefe_demo_konten muss VOR dem ersten DELETE laufen (Abbruch laesst alles unveraendert)')
  const waechter = funktion('pruefe_demo_konten')
  assert.ok(waechter.includes('DemoFehler'),
    'ein fremdes Konto muss den Lauf mit DemoFehler abbrechen, nicht stillschweigend mitnehmen')
})

test('DEMO-2 · person_kennung faellt nicht still auf den Anzeigenamen zurueck', () => {
  const rumpf = funktion('person_kennung')
  assert.ok(!/return\s+_KENNUNGEN\.get\(name,\s*name\)/.test(rumpf),
    'Rueckfall auf den Anzeigenamen ist der Ursprung des Befunds (Feld abgelehnt)')
  assert.ok(rumpf.includes('DemoFehler'),
    'fehlende Kennung muss laut abbrechen (DemoFehler), nicht still den Namen liefern')
})
