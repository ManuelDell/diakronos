/**
 * WEB-1 — Primo-Anbindung (Backend): was die Oberfläche erwarten darf.
 *
 * Die Karte ist eine Backend-/Sicherheitskarte (Rollen-Gate, Status,
 * Login-Übergabe). Es gibt deshalb KEINE Frontend-Änderung — dieser Test hält
 * den VERTRAG zwischen Server und SPA fest, damit die Karten WEB-2/WEB-3
 * nicht gegen eine erfundene Form bauen:
 *
 *   (1) Die drei Endpunkte heißen genau so, wie die Doku sie nennt.
 *   (2) Die Status-Antwort kennt genau drei Zustände.
 *   (3) Das Übergabe-Token steht im URL-FRAGMENT (`#token=…`), nicht im
 *       Query-String — sonst landet es im Server-/Proxy-Log.
 *   (4) Die Rolle „Website-Moderator“ ist im Backend als zugelassene Rolle
 *       hinterlegt und nicht etwa nur im Frontend „versteckt“.
 *
 * Geprüft wird Quelltext (Regex), nicht das Aussehen; Lauf im Docker-Build
 * über `node --test`:  cwd = frontend/
 */

import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, existsSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HIER = dirname(fileURLToPath(import.meta.url))
const REPO = join(HIER, '..', '..')
const API = join(REPO, 'backend', 'src', 'diakronos_app', 'api', 'website.py')
const ADAPTER = join(REPO, 'backend', 'src', 'diakronos_app', 'website', 'primo.py')

function lies(pfad) {
  assert.ok(existsSync(pfad), `Datei fehlt: ${pfad}`)
  return readFileSync(pfad, 'utf8')
}

test('WEB-1: die drei Endpunkte sind whitelisted und nicht für Gäste', () => {
  const quelle = lies(API)
  for (const name of ['status', 'rollen', 'login_uebergabe']) {
    // SEC-11 hat die Dekoration erweitert: schreibende Endpunkte tragen
    // zusätzlich `methods=["POST"]`. Der Vertrag dieser Karte ist unverändert
    // "whitelisted, NICHT für Gäste" — deshalb wird das `allow_guest=False`
    // innerhalb der Argumentliste verlangt, nicht die genaue Reihenfolge.
    assert.match(
      quelle,
      new RegExp(`@whitelist\\([^)\\n]*allow_guest=False[^)\\n]*\\)\\s*\\ndef ${name}\\(`),
      `Endpunkt ${name} fehlt oder ist für Gäste offen`,
    )
  }
  assert.match(quelle, /FRAPPE_MODULE = "diakronos\.diakronos\.api\.website"/)
})

test('WEB-1: Status kennt genau drei Zustände', () => {
  const quelle = lies(ADAPTER)
  const zustaende = [...quelle.matchAll(/^ZUSTAND_[A-Z_]+ = "([a-z_]+)"/gm)].map((m) => m[1])
  assert.deepEqual(zustaende.sort(), ['nicht_erreichbar', 'nicht_konfiguriert', 'verbunden'])
  assert.match(quelle, /PFAD_INFO = "\/api\/primo\/info"/)
})

test('WEB-1: Übergabe-Token nur im URL-Fragment', () => {
  const quelle = lies(ADAPTER)
  // Der Bau der Adresse: "...#token=<token>&record=<base64url>"
  assert.match(quelle, /diakronos-sso\.html/)
  assert.match(quelle, /#token=\{token\}&record=\{_base64url/)
})

test('WEB-1: Website-Moderator ist zugelassen, andere Rollen nicht', () => {
  const quelle = lies(ADAPTER)
  const block = quelle.slice(quelle.indexOf('WEBSITE_ROLLEN'), quelle.indexOf(')', quelle.indexOf('WEBSITE_ROLLEN')) + 1)
  assert.match(block, /"System Manager"/)
  assert.match(block, /"Administrator"/)
  assert.match(block, /"Website-Moderator"/)
  assert.doesNotMatch(block, /"Mitgliederadministrator"/, 'Mitgliederadministrator gehört NICHT dazu (S3)')
})

test('WEB-1: Rollen-Mapping Systemmanager->developer, Moderator->editor', () => {
  const quelle = lies(ADAPTER)
  assert.match(quelle, /\("System Manager", "developer"\)/)
  assert.match(quelle, /\("Website-Moderator", "editor"\)/)
  assert.match(quelle, /PFAD_IMPERSONATE = "\/api\/collections\/users\/impersonate\/\{record_id\}"/)
})

test('WEB-1: kein Secret in Log-Aufrufen des Adapters', () => {
  const quelle = lies(ADAPTER)
  // Jede Log-Zeile darf weder Passwort noch Token als Argument einsetzen.
  const logzeilen = quelle.split('\n').filter((z) => /logger\.(warning|info|error|debug)\(/.test(z) || /^\s+logger\./.test(z))
  for (const zeile of logzeilen) {
    assert.doesNotMatch(zeile, /password|token=|superuser_token_\)|secret/i, `Log-Zeile mit Secret: ${zeile.trim()}`)
  }
})
