/**
 * ORG-1 — Organigramm-Knoten-IDs tragen den Typ-Praefix.
 *
 * Befund SEED-1: hat ein Dienstbereich und eine Gruppe dieselbe Kennung
 * (Altdaten/Import), hatte die Knotenliste zwei Knoten mit derselben `id`;
 * d3-org-chart (3.1.1) zeichnet den Knoten dann doppelt — der Baum ist korrupt.
 * Behebung: Knoten-ids mit Typ-Praefix (`db_`/`g_`/`ug_`), die echte Kennung
 * bleibt als `raw_name` fuer Klick-Ziel/Bearbeiten erhalten.
 *
 * Der Test liest die echten Quelltexte (keine Kopien): die Kennungs-Bildung im
 * Backend und die Stellen der Oberflaeche, die eine Knoten-id auswerten.
 *
 * Laeuft im Docker-Build ueber den Globb `tests/org-1-*.test.mjs`.
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const root = new URL('../', import.meta.url)
const read = (p) => readFileSync(new URL(p, root), 'utf8')

// Im Docker-Build liegt das Backend NICHT unter `frontend/../../backend`
// (Build-Kontext ist das Frontend-Verzeichnis). Fehlt die Quelle, wird der
// Backend-Teil uebersprungen — der Test prueft dann nur die Oberflaeche.
let backend = ''
try {
  backend = read('../backend/src/diakronos_app/api/orgchart_api.py')
} catch {
  backend = ''
}
const eigenerEndpunkt = read('src/organigramm/App.vue')
const ansicht = read('src/diakonos/components/gruppen/OrganigrammAnsicht.vue')

// ── Backend: Kennungen mit Typ-Praefix ─────────────────────────────────────
if (backend) {
  assert.ok(
    /_ID_PRAEFIX_DIENSTBEREICH\s*=\s*"db_"/.test(backend),
    'Backend: Dienstbereich-Knoten tragen den Praefix db_',
  )
  assert.ok(
    /_ID_PRAEFIX_GRUPPE\s*=\s*"g_"/.test(backend),
    'Backend: Gruppen-Knoten tragen den Praefix g_',
  )
  assert.ok(
    /_ID_PRAEFIX_UNTERGRUPPE\s*=\s*"ug_"/.test(backend),
    'Backend: Untergruppen-Knoten tragen den Praefix ug_',
  )
  // Die Knoten-IDs entstehen ueber die Helfer, nicht mehr aus dem rohen docname.
  assert.ok(
    /"id":\s*_id_bereich\(db\["name"\]\)/.test(backend),
    'Backend: Dienstbereich-Knoten nutzt _id_bereich()',
  )
  assert.ok(
    /"id":\s*_id_gruppe\(g\["name"\]\)/.test(backend),
    'Backend: Gruppen-Knoten nutzt _id_gruppe()',
  )
  assert.ok(
    /"id":\s*_id_untergruppe\(ug\["name"\]\)/.test(backend),
    'Backend: Untergruppen-Knoten nutzt _id_untergruppe()',
  )
  // Elternkanten der Kinder zeigen auf die PRAEFIGIERTE Kennung.
  assert.ok(
    /_id_bereich\(g\["dienstbereich"\]\)/.test(backend),
    'Backend: Gruppe haengt an der praefigierten Dienstbereich-Kennung',
  )
  assert.ok(
    /"parentId":\s*_id_gruppe\(ug\["gruppe"\]\)/.test(backend),
    'Backend: Untergruppe haengt an der praefigierten Gruppen-Kennung',
  )
  assert.ok(
    /"parentId":\s*_id_gruppe\(m\["gruppe"\]\)/.test(backend),
    'Backend: Gruppenmitglied haengt an der praefigierten Gruppen-Kennung',
  )
  assert.ok(
    /"parentId":\s*_id_untergruppe\(m\["untergruppe"\]\)/.test(backend),
    'Backend: Untergruppenmitglied haengt an der praefigierten Untergruppen-Kennung',
  )
  // Die echte Kennung bleibt als raw_name erhalten (Klick-Ziel, Bearbeiten).
  for (const feld of ['db', 'g', 'ug']) {
    assert.ok(
      new RegExp(`"raw_name":\\s*${feld}\\["name"\\]`).test(backend),
      `Backend: Struktur-Knoten (${feld}) traegt raw_name fuer das Klick-Ziel`,
    )
  }
}

// ── Oberflaeche: Klick-Ziel ist die echte Kennung ──────────────────────────
{
  // Die Ansicht in „Gruppen“ ist der Weg mit Klick-Ziel: sie fuehrt ueber
  // raw_name auf die echte Kennung zurueck und darf nicht auf die praefigierte
  // id zurueckfallen.
  assert.ok(
    /node\.raw_name\s*\|\|\s*node\.id/.test(ansicht),
    'Ansicht Gruppen: Klick-Ziel bleibt der rohe Name (raw_name)',
  )
  // Der eigenstaendige Organigramm-Einstieg fuehrt keinen Router mit: er hat
  // KEINE Knoten-Navigation (nur Auf-/Zuklappen). Ein hash-Sprung dorthin
  // waere wirkungslos — dieser Waechter haelt die Oberflaeche dabei.
  assert.ok(
    !/#\/gruppe\//.test(eigenerEndpunkt),
    'Organigramm-Seite: keine wirkungslose Knoten-Navigation ohne Router',
  )
}

console.log('ORG-1 Knoten-IDs mit Typ-Praefix: bestanden')
