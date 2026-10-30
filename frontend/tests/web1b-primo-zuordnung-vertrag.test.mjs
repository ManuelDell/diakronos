/**
 * WEB-1b — Nachbesserung der Primo-Anbindung: was die Oberfläche erwarten darf.
 *
 * Die Karte ist eine Backend-/Sicherheitskarte; es gibt KEINE
 * Frontend-Änderung. Dieser Test hält den VERTRAG zwischen Server und SPA
 * fest, damit WEB-2/WEB-3 nicht gegen eine erfundene Form bauen:
 *
 *   (1) Ein Konto entsteht über eine ZUORDNUNG, nicht über die E-Mail.
 *   (2) `login_uebergabe` nimmt nur POST an.
 *   (3) 409 ist der Status für „Verknüpfung durch Admin nötig"; 503 bleibt
 *       503, aber ohne internen Klassennamen (SEC-8-Allowlist unverändert).
 *   (4) Der Status-Endpunkt hat das Feld `warnung` (https-Hinweis).
 *   (5) Token-Dauer 4 h, Grenzen 300..43200.
 *   (6) „Website-Moderator" bleibt aus der Zugangs-Rollenauswahl (ZUGANGS_ROLLEN).
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
const SETTINGS = join(REPO, 'backend', 'src', 'diakronos_app', 'settings.py')
const MODELL = join(REPO, 'backend', 'src', 'diakronos_app', 'models', 'website.py')
const MIGRATION = join(REPO, 'backend', 'alembic', 'versions', 'web1b_primo_konto.py')
const AUSWAHL = join(REPO, 'backend', 'src', 'diakronos_app', 'api', 'verantwortliche.py')

function lies(pfad) {
  assert.ok(existsSync(pfad), `Datei fehlt: ${pfad}`)
  return readFileSync(pfad, 'utf8')
}

test('WEB-1b: Zuordnungstabelle existiert mit eindeutiger primo_id', () => {
  const modell = lies(MODELL)
  assert.match(modell, /__tablename__ = "website_primo_konto"/)
  assert.match(modell, /Index\("uq_website_primo_konto_primo_id", "primo_id", unique=True\)/)

  const migration = lies(MIGRATION)
  assert.match(migration, /revision: str = "web1b_primo_konto"/)
  assert.match(migration, /down_revision: Union\[str, None\] = "web1_website_moderator"/)
  assert.match(migration, /op\.create_table\(\s*TABELLE/)
})

test('WEB-1b: Konto wird über die Zuordnung gesucht, nicht über die E-Mail', () => {
  const quelle = lies(ADAPTER)
  // Signatur trägt den Benutzer (Schlüssel der Zuordnung).
  assert.match(quelle, /def konto_sicherstellen\(\s*user: str,\s*email: str,/)
  assert.match(quelle, /def login_uebergabe\(\s*user: str, email: str,/)
  // Die drei 409-Lagen sind als Konstanten benannt.
  assert.match(quelle, /KONFLIKT_KONTO_EXISTIERT = \(\s*"Konto besteht bereits in Primo – Verknüpfung durch Admin nötig\."/)
  assert.match(quelle, /KONFLIKT_MAIL_ABWEICHEND/)
  assert.match(quelle, /KONFLIKT_GESCHUETZT/)
  // Es gibt keine Übernahme per Adressgleichheit mehr: ein vorhandenes Konto
  // führt zum Konflikt, nicht zum PATCH.
  const block = quelle.slice(quelle.indexOf('vorhanden = _hole_benutzer(client'))
  assert.match(block, /raise PrimoKontoKonflikt\(KONFLIKT_KONTO_EXISTIERT\)/)
})

test('WEB-1b: geschützte Konten und Superuser sind hart ausgeschlossen', () => {
  const settings = lies(SETTINGS)
  assert.match(settings, /primo_geschuetzte_konten: str = Field\(/)
  assert.match(settings, /"diakronos-integration@diedells.de"/)
  assert.match(settings, /def primo_ist_geschuetzt/)

  const quelle = lies(ADAPTER)
  // Vor dem Superuser-Login geprüft (Reihenfolge im Quelltext).
  const indexPruefung = quelle.indexOf('settings.primo_ist_geschuetzt(adresse)')
  const indexLogin = quelle.indexOf('superuser = superuser_token()', indexPruefung - 4000)
  assert.ok(indexPruefung > 0, 'Gesperrte Konten werden nicht geprüft')
  assert.ok(indexPruefung < indexLogin, 'Prüfung muss VOR dem Superuser-Login stehen')
})

test('WEB-1b: login_uebergabe nimmt nur POST an', () => {
  const api = lies(API)
  assert.match(api, /def login_uebergabe\(request=None\)/)
  assert.match(api, /\.upper\(\) != "POST"/)
  assert.match(api, /FrappePermissionError/)
})

test('WEB-1b: 409 ist ein eigener Status, die SEC-8-Allowlist bleibt unverändert', () => {
  const api = lies(API)
  assert.match(api, /throw\(exc\.meldung, KonfliktError\)/)

  const ausnahmen = readFileSync(
    join(REPO, 'backend', 'src', 'diakronos_app', 'frappe_compat', 'exceptions.py'),
    'utf8',
  )
  assert.match(ausnahmen, /class KonfliktError\(FrappeCompatError\)/)
  assert.match(ausnahmen, /http_status = 409/)

  const router = readFileSync(
    join(REPO, 'backend', 'src', 'diakronos_app', 'frappe_compat', 'router.py'),
    'utf8',
  )
  const allowlist = router.match(/EXC_TYPEN_ALLOWLIST = frozenset\(\{([^}]*)\}\)/)
  assert.ok(allowlist, 'Allowlist nicht gefunden')
  const namen = allowlist[1].split(',').map((n) => n.trim()).filter(Boolean)
  assert.deepEqual(namen.sort(), ['"CSRFTokenError"', '"PermissionError"', '"SessionExpired"'])
  assert.doesNotMatch(allowlist[1], /KonfliktError|DienstNichtVerfuegbarError/)
})

test('WEB-1b: Status-Endpunkt hat ein warnungs-Feld (https)', () => {
  const quelle = lies(ADAPTER)
  assert.match(quelle, /"warnung": warnung/)
  const settings = lies(SETTINGS)
  assert.match(settings, /def primo_public_url_warnung/)
  assert.match(settings, /startswith\("https:\/\/"\)/)
})

test('WEB-1b: Token-Dauer 4 h, Grenzen 300..43200', () => {
  const settings = lies(SETTINGS)
  assert.match(settings, /primo_token_sekunden: int = Field\(\s*14400,/)
  assert.match(settings, /300 <= wert <= 43200/)
})

test('WEB-1b: Website-Moderator NICHT in der Zugangs-Rollenauswahl', () => {
  const quelle = lies(AUSWAHL)
  const block = quelle.slice(quelle.indexOf('ZUGANGS_ROLLEN = ('), quelle.indexOf(')', quelle.indexOf('ZUGANGS_ROLLEN = (')))
  assert.doesNotMatch(block, /Website-Moderator/)
  assert.match(block, /"Mitglied"/)
})
