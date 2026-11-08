/**
 * BS-2a — Baustein-Bibliothek: Vertrag von Quellen, Installer und Bausteinen.
 *
 * Der Test liest DATEIEN AUSSERHALB von `frontend/` (backend/…, deploy/…,
 * tools/…). Nach Karten-Nachtrag 13 braucht der Frontend-Stage der
 * `backend/Dockerfile` dafür die passenden COPY-Zeilen — sonst ist der Test im
 * Worktree grün und im Image rot (Vorfall SEC-10/WEB-2/WEB-4).
 *
 * Geprüft wird:
 *   1. Die Baustein-Quellen liegen doppelt (deploy/ = Quelle, Paket =
 *      Laufzeit) und stimmen überein (Mirror-Vertrag, tools/bausteine_sync.py).
 *   2. Jeder Baustein hält die Formatregeln von Primo ein (Reihenfolge
 *      html/script/style, Props im js-Feld, kein doppeltes $props()).
 *   3. Die gemeinsame Hilfslogik ist in BEIDEN Bausteinen vorhanden
 *      (Absolute Adresse, Zeitlimit, de-DE/Europe-Berlin, Fehlertext) —
 *      Blöcke sind eigenständig (README Regel 1).
 *   4. `--dk-*` wird nur gelesen, nie deklariert (BS-0 F5, padding:0-Fund).
 *   5. Der Installer spricht den belegten Weg (ZIP + expected_revision, Einzel
 *      weg als Rückfall) und setzt die Basisadresse nur absolut.
 *   6. Die Endpunkte sind im whitelist-Inventar (Status lesend, Installieren
 *      POST/schreibend); der Login-Übergang zieht NACH der URL nach.
 */

import assert from 'node:assert/strict';
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { test } from 'node:test';

const HIER = dirname(fileURLToPath(import.meta.url));
// Im Image liegt der Test unter /build/tests, im Repo unter
// <repo>/frontend/tests. Beides zeigt auf das Wurzelverzeichnis des Repos
// bzw. des Build-Kontexts.
const REPO = resolve(HIER, '..', '..');

const QUELLE = join(REPO, 'deploy', 'primo', 'bausteine');
const PAKET = join(
  REPO, 'backend', 'src', 'diakronos_app', 'website', 'bausteine', 'quellen'
);
const INSTALLER = join(REPO, 'backend', 'src', 'diakronos_app', 'website', 'bausteine.py');
const API = join(REPO, 'backend', 'src', 'diakronos_app', 'api', 'website.py');
const INVENTAR = join(
  REPO, 'backend', 'src', 'diakronos_app', 'frappe_compat', 'inventar', 'whitelist.json'
);

function lies(pfad) {
  return readFileSync(pfad, 'utf8');
}

function kennungen(wurzel) {
  return readdirSync(wurzel)
    .filter((name) => statSync(join(wurzel, name)).isDirectory())
    .filter((name) => /^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(name))
    .sort();
}

const BAUSTEINE = kennungen(QUELLE);
const DATEIEN = ['block.json', 'component.svelte', 'fields.json', 'README.md'];

//: Alle mitgelieferten Bausteine (Reihenfolge von `block.json:index`).
//: BS-2c: um Gruppen-Übersicht, Gruppen-Steckbrief, Neuigkeiten und Anmeldung
//: erweitert. Weitere BS-Karten erweitern NUR diese Liste.
const MITGELIEFERT = [
  'anmeldung',
  'gruppe-steckbrief',
  'gruppen',
  'kalender',
  'kalender-abo',
  'kontakt',
  'naechster-gottesdienst',
  'neuigkeiten',
  'termine-liste'
];

// ── 1. Quellen und Spiegelung ───────────────────────────────────────────────

test('BS-2a: alle Bausteine liegen als Quelle und im Paket', () => {
  assert.deepEqual(BAUSTEINE, MITGELIEFERT);
  for (const kennung of BAUSTEINE) {
    for (const datei of DATEIEN) {
      const quelle = lies(join(QUELLE, kennung, datei));
      const paket = lies(join(PAKET, kennung, datei));
      assert.equal(
        paket,
        quelle,
        `Paketkopie weicht ab: ${kennung}/${datei} — tools/bausteine_sync.py laufen lassen`
      );
    }
  }
});

test('BS-2a: VERSION ist eine ganze Zahl >= 1', () => {
  const version = lies(join(QUELLE, 'VERSION')).trim();
  assert.match(version, /^[1-9][0-9]*$/, `VERSION ist ${JSON.stringify(version)}`);
  assert.equal(lies(join(PAKET, 'VERSION')).trim(), version);
});

// ── 2. Primo-Format ─────────────────────────────────────────────────────────

for (const kennung of BAUSTEINE) {
  test(`BS-2a: ${kennung} hält das Primo-Format ein`, () => {
    const quelle = lies(join(QUELLE, kennung, 'component.svelte'));
    const felder = JSON.parse(lies(join(QUELLE, kennung, 'fields.json')));
    const block = JSON.parse(lies(join(QUELLE, kennung, 'block.json')));

    // block.json
    assert.equal(block.kennung, kennung);
    assert.ok(block.name.startsWith('Diakronos:'), block.name);

    // Genau EIN <script> und höchstens EIN <style>, in dieser Reihenfolge —
    // Primo zerlegt den Quelltext mit regulären Ausdrücken
    // (internal/import.go::parseComponent).
    const skripte = quelle.match(/<script>/g) || [];
    assert.equal(skripte.length, 1, 'genau ein <script>');
    const styles = quelle.match(/<style>/g) || [];
    assert.equal(styles.length, 1, 'genau ein <style>');
    assert.ok(
      quelle.indexOf('<script>') < quelle.indexOf('<style>'),
      'script vor style'
    );
    // Das erste nicht-Leerzeichen muss Markup sein (kein Skript zuerst).
    assert.ok(quelle.trimStart().startsWith('<'), 'Beginnt mit Markup');

    // Props im js-Feld: `$props()` genau einmal, und zwar IM Skriptteil.
    const js = quelle.slice(quelle.indexOf('<script>') + 8, quelle.lastIndexOf('</script>'));
    const html = quelle.slice(0, quelle.indexOf('<script>'));
    assert.equal((js.match(/\$props\(/g) || []).length, 1, 'genau ein $props() im js-Feld');
    assert.ok(!html.includes('$props('), 'kein $props() im Markup');
    // Alle Feldkennungen kommen im Skript vor (sonst zeigt der Editor ein Feld,
    // das der Code nicht liest — Vorgaben kommen als Props).
    for (const feld of felder) {
      assert.ok(js.includes(feld.name), `Feld ${feld.name} fehlt im Baustein`);
    }
    // Jede Feldkennung hat einen Vorgabewert (Primo legt Vorgaben als Eintrag ab).
    for (const feld of felder) {
      assert.ok('default' in feld, `Feld ${feld.name} ohne Vorgabewert`);
      assert.ok(
        ['text', 'number', 'select', 'switch', 'url', 'rich-text', 'markdown',
         'date', 'slider', 'icon', 'link', 'info', 'group', 'repeater'].includes(feld.type),
        `unbekannter Feldtyp ${feld.type}`
      );
    }
  });
}

test('BS-2a: gemeinsame Hilfslogik steht in JEDEM Baustein', () => {
  // Blöcke sind eigenständig: Primo kopiert sie in Sites, ein Import zwischen
  // Bausteinen gäbe es in der Kopie nicht (README Regel 1).
  for (const kennung of BAUSTEINE) {
    const quelle = lies(join(QUELLE, kennung, 'component.svelte'));
    for (const [name, muster] of [
      ['absolute Adresse', /function nur_webadresse\(/],
      ['Zeitlimit', /ZEITLIMIT_MS/],
      ['Abbruch', /AbortController/],
      ['client-seitiger Abruf', /await fetch\(/],
      ['Ladezustand', /ladezustand|zustand = 'sendet'/]
    ]) {
      assert.match(quelle, muster, `${kennung}: ${name} fehlt`);
    }
    // Kein gemeinsamer Import zwischen den Bausteinen.
    assert.ok(!/from\s+['"]\.\.?\//.test(quelle), `${kennung}: importiert aus einem anderen Baustein`);
  }
});

test('BS-2a: Datum/Uhrzeit in de-DE und Europe/Berlin (Termine)', () => {
  // Der Termine-Baustein gibt Zeiten aus; die Schreibweise darf nicht von der
  // Browsersprache abhaengen (G2: Beschriftungen deutsch).
  const quelle = lies(join(QUELLE, 'termine-liste', 'component.svelte'));
  assert.match(quelle, /Europe\/Berlin/, 'Zeitzone fehlt');
  assert.match(quelle, /Intl\.DateTimeFormat\('de-DE'/, 'de-DE-Format fehlt');
  assert.match(quelle, /timeZone: ZEITZONE/, 'Zeitzone wird nicht gesetzt');
});

test('BS-2a: --dk-* wird nur gelesen, nie deklariert', () => {
  // BS-0 F5: `--dk-abstand: var(--dk-abstand, …)` ist nach CSS ungültig und
  // fällt auf „unset" zurück (gemessen: padding 0).
  for (const kennung of BAUSTEINE) {
    const quelle = lies(join(QUELLE, kennung, 'component.svelte'));
    const deklaration = quelle.match(/^\s*--dk-[a-z-]+\s*:/m);
    assert.equal(deklaration, null, `${kennung}: deklariert ${deklaration && deklaration[0]}`);
    assert.ok(quelle.includes('var(--dk-'), `${kennung}: liest keine --dk-Tokens`);
    // Keine hartkodierten Farben ausserhalb von var()-Fallbacks.
    for (const farbe of quelle.match(/#[0-9a-fA-F]{3,8}\b/g) || []) {
      const muster = new RegExp(`var\\(--dk-[a-z-]+,\\s*${farbe}`);
      assert.match(quelle, muster, `${kennung}: Farbe ${farbe} nicht als var()-Fallback`);
    }
  }
});

test('BS-2a: kein externes CDN und keine Gemeinde-Inhalte im Code', () => {
  for (const kennung of BAUSTEINE) {
    const quelle = lies(join(QUELLE, kennung, 'component.svelte'));
    for (const verboten of ['esm.sh', 'fonts.googleapis', 'cdn.jsdelivr', 'unpkg.com']) {
      assert.ok(!quelle.includes(verboten), `${kennung}: ${verboten}`);
    }
    for (const verboten of ['Musterhausen', 'ECG', 'Gemeinde des']) {
      assert.ok(!quelle.includes(verboten), `${kennung}: ${verboten}`);
    }
  }
});

test('BS-2a: Termine-Baustein nutzt die oeffentliche Lese-API', () => {
  const quelle = lies(join(QUELLE, 'termine-liste', 'component.svelte'));
  assert.ok(quelle.includes("'/website/oeffentlich/termine?'"), 'falscher Pfad');
  for (const parameter of ['von', 'bis', 'limit', 'kalender', 'kategorie', 'gruppe']) {
    assert.ok(quelle.includes(`parameter.set('${parameter}'`), `Parameter ${parameter} fehlt`);
  }
  // Ganztags wird nicht als 00:00 angezeigt.
  assert.ok(quelle.includes("'ganztägig'"), 'Ganztags-Kennzeichnung fehlt');
});

test('BS-2a: Kontakt-Baustein sendet an den Kontakt-Endpunkt und prueft wie der Server', () => {
  const quelle = lies(join(QUELLE, 'kontakt', 'component.svelte'));
  assert.ok(quelle.includes("'/api/method/website.kontakt_senden'"), 'falscher Pfad');
  assert.ok(quelle.includes("'/website/oeffentlich/postfaecher'"), 'Postfach-Liste fehlt');
  // Honeypot: versteckt, aus der Tab-Reihenfolge, aria-hidden.
  assert.match(quelle, /name="website"/);
  assert.match(quelle, /tabindex="-1"/);
  assert.match(quelle, /position:\s*absolute/);
  // Barrierefreiheit: aria-live/role, aria-invalid, aria-describedby, Labels.
  assert.match(quelle, /role="alert"/);
  assert.match(quelle, /role="status"/);
  assert.match(quelle, /aria-invalid=/);
  assert.match(quelle, /aria-describedby=/);
  assert.match(quelle, /<label[^>]*for=/);
  // Längen wie auf dem Server (maxlength) und Einwilligungspflicht.
  assert.match(quelle, /maxlength="120"/);
  assert.match(quelle, /maxlength="200"/);
  assert.match(quelle, /maxlength="5000"/);
  assert.ok(quelle.includes('einwilligung_erteilt !== true'), 'Einwilligung nicht geprueft');
});

// ── 3. Installer ───────────────────────────────────────────────────────────

test('BS-2a: Installer nutzt ZIP + expected_revision und den Einzelweg nur als Rueckfall', () => {
  const quelle = lies(INSTALLER);
  assert.match(quelle, /\/api\/primo\/import-library/, 'Import-Endpunkt fehlt');
  assert.match(quelle, /expected_revision/, 'Sync-Basis fehlt');
  assert.match(quelle, /X-Primo-Revision/, 'Revision wird nicht gelesen');
  assert.match(quelle, /export-library/, 'Export (Revisionsquelle) fehlt');
  // Rueckfall nur bei fehlendem Endpunkt.
  assert.match(quelle, /fehler\.status in \(404, 405\)/, 'Rueckfallbedingung fehlt');
  // BS-2a2 (F3): der Einzelweg ist ein Upsert über die PocketBase-Sammlungen
  // — der Sammlungsname steht im Aufruf, nicht mehr im Fadenkreuz-String.
  assert.match(quelle, /library_symbol_groups/, 'Einzelweg fehlt');
  assert.match(quelle, /"library_symbols"/, 'Einzelweg: Block-Sammlung fehlt');
  // Version im Blocknamen (Primo hat keine Versionierung, BS-0 F2b).
  assert.match(quelle, /@v\{int\(version\)\}/, 'Versionsvermerk fehlt');
  // Laufzeitdateien ausschliesslich ueber importlib.resources.
  assert.match(quelle, /resources\.files\(/, 'importlib.resources fehlt');
  assert.ok(!quelle.includes('/root/.hermes'), 'Zugriff auf /root/.hermes');
});

test('BS-2a: Basisadresse wird nur absolut gesetzt, nie erfunden', () => {
  const quelle = lies(INSTALLER);
  assert.match(quelle, /def _absolute_adresse/);
  assert.match(quelle, /teile\.scheme not in \("http", "https"\)/);
  // Leere/unbrauchbare Adresse -> leeres Feld, kein Platzhalter.
  assert.match(quelle, /return ""/);
  // Adresse kommt aus der Gemeinde-Einstellung bzw. APP_BASE_URL + Praefix.
  assert.match(quelle, /oeffentliche_basis/);
  assert.match(quelle, /app_base_url/);
  assert.match(quelle, /diakronos_base_path/);
});

test('BS-2a: Installer fasst Site-Kopien nicht an', () => {
  // BS-0 F2c: eine automatische Uebernahme wuerde Anpassungen ueberschreiben.
  const quelle = lies(INSTALLER);
  for (const verboten of ['site_symbols', 'refresh_code']) {
    assert.ok(!quelle.includes(verboten), `Installer greift auf ${verboten} zu`);
  }
});

// ── 4. Endpunkte und Inventar ──────────────────────────────────────────────

test('BS-2a: Endpunkte sind whitelist, Status lesend, Installieren POST', () => {
  const quelle = lies(API);
  const statusAbschnitt = quelle.slice(quelle.indexOf('def bausteine_status'));
  assert.match(quelle, /@whitelist\(allow_guest=False\)\ndef bausteine_status/, 'Status-Gate fehlt');
  assert.match(
    quelle,
    /@whitelist\(methods=\["POST"\], allow_guest=False\)\ndef bausteine_installieren/,
    'Installieren ist nicht POST'
  );
  assert.ok(statusAbschnitt.includes('_nur_post(request)'), 'Methodenpruefung fehlt');
  assert.match(quelle, /"bausteine_installieren",/, 'nicht in _NUR_POST');
});

test('BS-2a: beide Endpunkte stehen im whitelist-Inventar', () => {
  const inventar = JSON.parse(lies(INVENTAR));
  const eintraege = inventar.eintraege || [];
  const status = eintraege.find((e) => e.name === 'bausteine_status');
  const install = eintraege.find((e) => e.name === 'bausteine_installieren');
  assert.ok(status, 'bausteine_status fehlt im Inventar');
  assert.ok(install, 'bausteine_installieren fehlt im Inventar');
  assert.equal(status.einstufung, 'lesend', 'Status ist nicht lesend eingestuft');
  assert.equal(install.einstufung, 'schreibend', 'Installieren ist nicht schreibend');
  // `deklariert` traegt im Inventar die EINSTUFUNG der Deklaration
  // (`methods=["POST"]` -> "schreibend"), nicht die Methodenliste.
  assert.equal(install.deklariert, 'schreibend');
  assert.equal(install.nach_rumpf, 'lesend');
  assert.equal(install.nach_name, 'lesend');
  assert.equal(install.allow_guest, false);
});

test('BS-2a: Login-Uebergang zieht die Bibliothek NACH der Antwort nach', () => {
  const quelle = lies(API);
  const abschnitt = quelle.slice(
    quelle.indexOf('def login_uebergabe'),
    quelle.indexOf('def _mit_nachziehen')
  );
  // B2: das Nachziehen haengt als Hintergrundaufgabe AN der Antwort. Damit
  // geht die Uebergabe-URL zuerst raus und ein Bibliotheksfehler kann die
  // Anmeldung nicht mehr kippen.
  assert.ok(abschnitt.includes('_mit_nachziehen('), 'login_uebergabe zieht nicht nach');
  assert.ok(!abschnitt.includes('return {"url": url}'), 'antwortet noch ohne Hintergrundaufgabe');
  assert.ok(
    abschnitt.indexOf('_mit_nachziehen(') > abschnitt.indexOf('uebergabe_url(') ||
      abschnitt.indexOf('_mit_nachziehen(') > abschnitt.indexOf('_im_thread(primo.login_uebergabe'),
    'Nachziehen laeuft VOR der Uebergabe-URL'
  );

  const helfer = quelle.slice(quelle.indexOf('def _mit_nachziehen'));
  assert.match(helfer, /BackgroundTask\(_bausteine_nachziehen\)/, 'keine Hintergrundaufgabe');
  assert.match(helfer, /if request is None:\s*\n\s*return daten/, 'Rueckfall ohne request fehlt');

  const nachziehen = quelle.slice(quelle.indexOf('def _bausteine_nachziehen'));
  const rumpf = nachziehen.slice(0, nachziehen.indexOf('\n\n\n'));
  assert.match(rumpf, /except Exception/, 'Fehler werden nicht gefangen (Login muesste scheitern)');
  assert.match(rumpf, /stand\.veraltet/, 'Nachziehen ohne Versionsvergleich');
});


test('BS-2a: Dockerfile traegt Bausteine und die im Test gelesenen Dateien', () => {
  const dockerfile = lies(join(REPO, 'backend', 'Dockerfile'));
  // Laufzeitdaten (ZIP-Bau) muessen im Image liegen …
  assert.match(dockerfile, /COPY backend\/src \/app\/src/, 'App-Quellen fehlen');
  // … und der Frontend-Stage braucht die Dateien dieses Tests (Regel 13).
  for (const pfad of [
    'backend/src/diakronos_app/website/bausteine/',
    'backend/src/diakronos_app/website/bausteine.py',
    'backend/src/diakronos_app/api/website.py',
    'backend/src/diakronos_app/frappe_compat/inventar/',
    'backend/src/diakronos_app/frappe_compat/registry.py'
  ]) {
    assert.ok(dockerfile.includes(pfad), `Frontend-Stage: COPY fuer ${pfad} fehlt`);
  }
  // Die Node-Testliste nennt den neuen Test — seit FE-TEST-1 in
  // `frontend/tests/testliste.txt` (die Dockerfile liest sie über
  // `ARG NODE_TESTLISTE`); die Dockerfile selbst muss darauf zeigen.
  assert.match(dockerfile, /^ARG NODE_TESTLISTE=tests\/testliste\.txt$/m,
    'backend/Dockerfile liest die Muster nicht aus tests/testliste.txt');
  // Liste über DIE TESTDATEI auflösen (nicht über REPO): im Image liegt sie
  // neben diesem Test unter /build/tests, REPO wäre dort `/`.
  const testliste = readFileSync(new URL('./testliste.txt', import.meta.url), 'utf8');
  assert.match(testliste, /^tests\/bs2a-\*\.test\.mjs$/m, 'bs2a fehlt in der Frontend-Testliste');
});

test('BS-2a: pyproject fuehrt die Bausteine als Paketdaten', () => {
  const pyproject = lies(join(REPO, 'backend', 'pyproject.toml'));
  assert.match(pyproject, /"diakronos_app\.website\.bausteine\.quellen"/, 'Paketdaten fehlen');
  for (const muster of ['VERSION', '*/component.svelte', '*/fields.json', '*/block.json']) {
    assert.ok(pyproject.includes(muster), `Paketdaten ohne ${muster}`);
  }
});
