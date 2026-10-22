// P1-7 — Gruppen/Organigramm (Frontend-Teil).
//
// Quelltext-Prüfungen im Stil der übrigen Node-Tests dieses Projekts: die
// SFCs werden bei jedem Build mitkompiliert (Dockerfile Stage 1), hier wird
// geprüft, dass die Reparaturen nicht stillschweigend zurückfallen.
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const root = new URL('../src/diakonos/', import.meta.url)
const read = (p) => readFileSync(new URL(p, root), 'utf8')

// ── UXD-R7: Detailrouten bekommen einen Schlüssel ───────────────────────────
{
  const app = read('App.vue')
  assert.ok(
    /<component\s+:is="currentComponent"\s+:key="currentHash"/.test(app),
    'App.vue: <component> braucht :key="currentHash" (sonst bleibt die alte Detailseite stehen)',
  )
  const detail = read('pages/GruppeDetail.vue')
  assert.ok(detail.includes('watch(gruppeId'), 'GruppeDetail: watcher auf die Routen-ID')
}

// ── UXD-R4: Parameternamen passen zum Backend ───────────────────────────────
{
  const org = read('components/gruppen/OrganigrammAnsicht.vue')
  assert.ok(org.includes('dienstbereich: f.parent'), 'create_gruppe nutzt `dienstbereich`')
  assert.ok(org.includes('gruppe: f.parent'), 'create_untergruppe nutzt `gruppe`')
  assert.ok(org.includes('untergruppenname: editForm.value.name.trim()'), 'update_untergruppe nutzt `untergruppenname`')
  assert.ok(!org.includes('parent: f.parent'), 'kein `parent` mehr an create_gruppe/untergruppe')
  assert.ok(!/alert\(/.test(org), 'Organigramm: kein roher alert() mehr, sondern Toast')
}

// ── OP-ADMIN-5: Namensfeld + can_edit_ids + Stift ───────────────────────────
{
  const detail = read('pages/GruppeDetail.vue')
  assert.ok(detail.includes('editName'), 'GruppeDetail: Namensfeld (editName)')
  assert.ok(detail.includes('gruppenname: editName.value.trim()'), 'GruppeDetail: update_gruppe schreibt gruppenname')
  assert.ok(detail.includes('untergruppenname: editName.value.trim()'), 'GruppeDetail: update_untergruppe schreibt untergruppenname')
  // Stift statt „+" am Bearbeiten-Knopf der Detailkarte.
  assert.ok(detail.includes('M16.5 3.5a2.12'), 'GruppeDetail: Stift-Symbol am Bearbeiten-Knopf')
}

// ── UXD-R11: Doppelklick-Schutz ─────────────────────────────────────────────
{
  const detail = read('pages/GruppeDetail.vue')
  assert.ok(detail.includes('if (sendingAufgabe.value) return'), 'GruppeDetail: createAufgabe sperrt doppelt')
  assert.ok(detail.includes('if (sendingAnkuendigung.value) return'), 'GruppeDetail: createAnkuendigung sperrt doppelt')
  const beitraege = read('pages/Beitraege.vue')
  assert.ok(beitraege.includes('if (addingComment.value) return'), 'Beitraege: addComment sperrt doppelt')
}

// ── UXD-R10: eigener Termine-Endpunkt statt get_events ──────────────────────
{
  const detail = read('pages/GruppeDetail.vue')
  assert.ok(detail.includes('gruppen.get_gruppe_termine'), 'GruppeDetail: Nutzt get_gruppe_termine')
  assert.ok(!detail.includes('api.kalender.get_events'), 'GruppeDetail: kein kaputter get_events-Aufruf mehr')
}

// ── UXD-R25: Anzeigenamen im Untertitel ─────────────────────────────────────
{
  const detail = read('pages/GruppeDetail.vue')
  assert.ok(detail.includes('dienstbereich_name'), 'GruppeDetail: Dienstbereichsname im Untertitel')
  assert.ok(detail.includes('gruppe_name'), 'GruppeDetail: Obergruppen-Name im Untertitel')
}

// ── OP-ADMIN-22/UXD-R4: Organigramm-IDs ohne Präfix ────────────────────────
{
  const org = read('components/gruppen/OrganigrammAnsicht.vue')
  assert.ok(org.includes('function roherName'), 'Organigramm: Präfix-Stripper für Knoten-IDs')
  assert.ok(org.includes('raw_name'), 'Organigramm: nutzt raw_name für API-Aufrufe')
  // OP-ADMIN-5: der Stift muss gegen den rohen Namen prüfen, sonst bleibt er weg.
  assert.ok(
    org.includes('can_edit_ids?.includes(d.data.raw_name || d.data.id)'),
    'Organigramm: Stift-Prüfung gegen raw_name (sonst 0 Stifte wie im Befund)',
  )
}

// ── OP-ADMIN-6: Gruppen anlegen von der Gruppenseite aus ────────────────────
{
  const gruppen = read('pages/Gruppen.vue')
  assert.ok(gruppen.includes('can_create_any'), 'Gruppen: Anlegen-Knopf bei can_create_any')
  assert.ok(gruppen.includes('create_gruppe'), 'Gruppen: create_gruppe verdrahtet')
  assert.ok(gruppen.includes('create_untergruppe'), 'Gruppen: create_untergruppe verdrahtet')
  assert.ok(gruppen.includes('dienstbereich_auswahl'), 'Gruppen: Dienstbereichs-Auswahl vom Server')
}

// ── B4: Warnungen der Mitgliedsanlage erreichen die Oberflaeche ─────────────
{
  const reg = read('pages/Registrierung.vue')
  assert.ok(
    reg.includes('res.warnungen'),
    'Registrierung: Warnungen aus genehmige_anmeldung anzeigen',
  )
  assert.ok(
    /showToast\(w, 'warning'\)/.test(reg),
    'Registrierung: Warnung als Toast sichtbar (nicht verschluckt)',
  )
}

console.log('P1-7 Gruppen-Reparatur (Frontend): bestanden')
