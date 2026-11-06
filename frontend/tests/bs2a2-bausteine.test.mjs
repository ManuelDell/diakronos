/**
 * BS-2a2 — Baustein-Bibliothek: Nachbesserung (Befunde F1–F7) im Vertrag.
 *
 * Der Test liest DATEIEN AUSSERHALB von `frontend/` (deploy/…, backend/…).
 * Nach Karten-Nachtrag 13 braucht der Frontend-Stage der `backend/Dockerfile`
 * dafür die passenden COPY-Zeilen — sonst ist der Test im Worktree grün und im
 * Image rot (Vorfall SEC-10/WEB-2/WEB-4). Nachweis: `docker build -f
 * backend/Dockerfile --target frontend .` (exit 0, „# fail 0").
 *
 * Geprüft wird:
 *   F1  Zeitraum mehrtägiger Termine (ohne einen Tag abzuziehen).
 *   F2  In-Prozess-Merker im Installer und im Login-Übergang.
 *   F3  Rückfallweg (Einzel-API) ist Upsert, nicht Anlegen.
 *   F4  Prüfsummendatei hängt an VERSION (Code-Änderung ohne VERSION -> rot).
 *   F5  Funktionsname `_superuser_token`, `lang="de"` am Wurzelelement.
 *   F6  Sichtbare Texte sind Felder; 400 auf `postfach` eigene Meldung.
 *   F7  Rückgabetyp `_export_zip` = (bytes, revision).
 */

import assert from 'node:assert/strict';
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { test } from 'node:test';

const HIER = dirname(fileURLToPath(import.meta.url));
// Im Image liegt der Test unter /build/tests, im Repo unter <repo>/frontend/tests.
const REPO = resolve(HIER, '..', '..');

const QUELLE = join(REPO, 'deploy', 'primo', 'bausteine');
const PAKET = join(REPO, 'backend', 'src', 'diakronos_app', 'website', 'bausteine', 'quellen');
const INSTALLER = join(REPO, 'backend', 'src', 'diakronos_app', 'website', 'bausteine.py');
const API = join(REPO, 'backend', 'src', 'diakronos_app', 'api', 'website.py');

const lies = (pfad) => readFileSync(pfad, 'utf8');

function kennungen(wurzel) {
  return readdirSync(wurzel)
    .filter((name) => statSync(join(wurzel, name)).isDirectory())
    .filter((name) => /^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(name))
    .sort();
}

const BAUSTEINE = kennungen(QUELLE);

/** Felder eines Bausteins (aus fields.json der QUELLE). */
function felder(kennung) {
  return JSON.parse(lies(join(QUELLE, kennung, 'fields.json')));
}

/** Prop-Namen aus `let { … } = $props();`. */
function props(kennung) {
  const text = lies(join(QUELLE, kennung, 'component.svelte'));
  const treffer = text.match(/let \{([\s\S]*?)\} = \$props\(\);/);
  assert.ok(treffer, `${kennung}: $props() nicht gefunden`);
  return new Set(
    treffer[1]
      .split('\n')
      .map((zeile) => zeile.match(/^\s*([a-z][a-z0-9_]*)\s*=/))
      .filter(Boolean)
      .map((m) => m[1])
  );
}

// ── F1: Zeitraum mehrtägiger Termine ───────────────────────────────────────

test('BS-2a2/F1: der Termine-Baustein zeigt den Zeitraum', () => {
  const text = lies(join(QUELLE, 'termine-liste', 'component.svelte'));
  assert.match(text, /function ende_text\(/);
  assert.match(text, /zeitraum:\s*ende_text\(beginn, eintrag\.ende\)/);
  assert.match(text, /\{termin\.zeitraum\}/);
});

test('BS-2a2/F1: das Ende wird NICHT um einen Tag gekürzt', () => {
  const text = lies(join(QUELLE, 'termine-liste', 'component.svelte'));
  const start = text.indexOf('function ende_text(');
  const block = text.slice(start, text.indexOf('\n  }', start));
  // Diakronos speichert das Ganztags-Ende EINSCHLIESSLICH — Tagesarithmetik
  // wäre genau der Fehler, den die Karte verbietet.
  for (const verboten of ['86400000', 'getDate() - 1', 'getDate()-1', 'setDate(', 'minusOneDay']) {
    assert.ok(!block.includes(verboten), `Tagesarithmetik im Zeitraum: ${verboten}`);
  }
  assert.ok(block.includes('isodatum(beginn) === isodatum(ende_datum)'),
    'gleicher Kalendertag muss ohne Zeitraum auskommen');
});

test('BS-2a2/F1: Zeitraum steht neben dem Beginn (eigenes Element)', () => {
  const text = lies(join(QUELLE, 'termine-liste', 'component.svelte'));
  const kopf = text.slice(0, text.indexOf('</section>'));
  const tag = kopf.indexOf('{termin.tag}');
  const bis = kopf.indexOf('{termin.zeitraum}');
  const uhr = kopf.indexOf('{termin.uhrzeit}');
  assert.ok(tag >= 0 && bis > tag, 'Zeitraum folgt dem Beginn');
  assert.ok(uhr > bis, 'Uhrzeit steht nach dem Zeitraum');
  assert.match(text, /\.dk-termine__bis/);
});

// ── F2: In-Prozess-Merker ─────────────────────────────────────────────────

test('BS-2a2/F2: Installer führt einen Prozess-Merker', () => {
  const text = lies(INSTALLER);
  assert.match(text, /_bestaetigte_version\s*=\s*0/);
  assert.match(text, /def version_bestaetigen\(/);
  assert.match(text, /def steht_bereit\(/);
  assert.match(text, /def merker_zuruecksetzen\(/);
  // `sync()` merkt die bestätigte Version.
  const sync_block = text.slice(text.indexOf('def sync('));
  assert.match(sync_block.slice(0, 900), /version_bestaetigen\(ergebnis\.version\)/);
});

test('BS-2a2/F2: Login-Übergang überspringt Primo bei bestätigter Version', () => {
  const text = lies(API);
  const start = text.indexOf('def _bausteine_nachziehen(');
  assert.ok(start > 0, '_bausteine_nachziehen fehlt');
  const block = text.slice(start, start + 2000);
  assert.match(block, /steht_bereit\(\)/,
    'ohne Merker-Abfrage macht jeder Login Superuser-Auth + Voll-Export');
  // Die Abfrage steht VOR dem Stand-Lesen.
  assert.ok(block.indexOf('steht_bereit()') < block.indexOf('bibliothek_stand()'),
    'Merker muss vor dem Stand-Lesen greifen');
  // Und der Fehlerpfad bleibt: jede Ausnahme wird gefangen.
  assert.match(block, /except Exception/);
});

test('BS-2a2/F2: Merker ist reiner Prozess-Zustand (keine Tabelle, kein Redis)', () => {
  const text = lies(INSTALLER);
  const start = text.indexOf('_bestaetigte_version = 0');
  const block = text.slice(Math.max(0, start - 800), start + 2500);
  for (const verboten of ['redis', 'sess.add(', 'sess.commit', 'Table', 'alembic']) {
    assert.ok(!block.includes(verboten), `Merker benutzt ${verboten}`);
  }
});

// ── F3: Rückfallweg idempotent ────────────────────────────────────────────

test('BS-2a2/F3: Einzelweg ist Upsert (Filter + PATCH), nicht Anlegen', () => {
  const text = lies(INSTALLER);
  const start = text.indexOf('def _import_einzeln(');
  const block = text.slice(start, text.indexOf('def _zerlegen(', start));
  assert.match(block, /_upsert\(/, 'Einzelweg muss über den Upsert gehen');
  const upsert = text.slice(text.indexOf('def _upsert('), start);
  assert.match(upsert, /client\.patch\(/, 'vorhandener Datensatz wird per PATCH ergänzt');
  assert.match(upsert, /client\.post\(/, 'fehlender Datensatz wird angelegt');
  assert.match(text, /def _finde_eintrag\(/);
  assert.match(text, /"filter": filter_/);
});

test('BS-2a2/F3: fehlender Import-Endpunkt führt zum Rückfall mit klarer Meldung', () => {
  const text = lies(INSTALLER);
  const start = text.indexOf('def sync(');
  const block = text.slice(start, start + 2000);
  assert.match(block, /in \(404, 405\)/);
  assert.match(block, /Einzelweg/);
});

// ── F4: Prüfsummen hängen an VERSION ──────────────────────────────────────

test('BS-2a2/F4: Prüfsummendatei liegt im Paket und nennt die VERSION', () => {
  const datei = join(PAKET, 'PRUEFSUMMEN.json');
  const daten = JSON.parse(lies(datei));
  const version = Number(lies(join(QUELLE, 'VERSION')).trim());
  assert.equal(daten.version, version,
    'PRUEFSUMMEN.json gehört zu einer anderen VERSION — tools/bausteine_sync.py ausführen');
  assert.deepEqual(Object.keys(daten.bausteine).sort(), BAUSTEINE);
  for (const [kennung, sha] of Object.entries(daten.bausteine)) {
    assert.match(sha, /^[0-9a-f]{64}$/, `${kennung}: keine SHA-256`);
  }
});

test('BS-2a2/F4: VERSION ist seit der Auslieferung 1 erhöht (Code geändert)', () => {
  // Die Nachbesserung ändert Code und Feldschema -> neue Version, sonst
  // würden eingesetzte Kopien stillschweigend veralten (F4).
  const version = Number(lies(join(QUELLE, 'VERSION')).trim());
  assert.ok(version >= 2, `VERSION ist ${version} — die Nachbesserung braucht mindestens 2`);
});

test('BS-2a2/F4: das Werkzeug bindet die Summen an die VERSION', () => {
  const werkzeug = join(REPO, 'tools', 'bausteine_sync.py');
  let text;
  try {
    text = lies(werkzeug);
  } catch {
    // Im Frontend-Stage kann tools/ fehlen (es steht nicht in der Dockerfile);
    // die Bindung prüft dort die Paketdatei oben.
    return;
  }
  assert.match(text, /PRUEFSUMMEN\s*=\s*"PRUEFSUMMEN\.json"/);
  assert.match(text, /def schreibe_pruefsummen\(/);
  assert.match(text, /"version":\s*int\(version\)/);
  assert.match(text, /def baustein_sha\(/);
});

// ── F5: Name und Sprache ──────────────────────────────────────────────────

test('BS-2a2/F5: die Tokenfunktion heißt _superuser_token', () => {
  const text = lies(INSTALLER);
  assert.match(text, /def _superuser_token\(\)/);
  assert.ok(!text.includes('_development_token'),
    'der alte (falsche) Name steht noch im Code');
});

test('BS-2a2/F5: jedes Wurzelelement trägt lang="de"', () => {
  for (const kennung of BAUSTEINE) {
    const text = lies(join(QUELLE, kennung, 'component.svelte'));
    const erste_zeile = text.split('\n')[0];
    assert.match(erste_zeile, /^<section[^>]*\blang="de"/,
      `${kennung}: lang="de" fehlt am Wurzelelement`);
    assert.ok(!text.includes('<html'), `${kennung}: zweites <html> wäre ungültig`);
  }
});

// ── F6: Texte als Felder ──────────────────────────────────────────────────

test('BS-2a2/F6: sichtbare Texte sind Felder (Prop-Vertrag erfüllt)', () => {
  const pflicht = {
    kontakt: [
      'text_name',
      'text_email',
      'text_postfach',
      'text_nachricht',
      'text_sendet',
      'text_postfach_fehler',
      'text_postfach_fehler_server',
      'text_adresse_fehlt',
      'text_rate_limit'
    ],
    'termine-liste': ['text_ganztaegig', 'text_laedt', 'text_anmeldung']
  };
  for (const [kennung, namen] of Object.entries(pflicht)) {
    const feldnamen = new Set(felder(kennung).map((f) => f.name));
    const propnamen = props(kennung);
    for (const name of namen) {
      assert.ok(feldnamen.has(name), `${kennung}: Feld ${name} fehlt (F6)`);
      assert.ok(propnamen.has(name), `${kennung}: ${name} ist kein Prop`);
      assert.ok(lies(join(QUELLE, kennung, 'component.svelte')).includes(name),
        `${kennung}: ${name} wird nicht benutzt`);
    }
  }
});

test('BS-2a2/F6: kein fest verdrahteter Text im Markup', () => {
  const kontakt = lies(join(QUELLE, 'kontakt', 'component.svelte'));
  for (const fest of ['>Ihr Name<', '>Ihre E-Mail-Adresse<', '>Wird gesendet', '>Ihre Nachricht<']) {
    assert.ok(!kontakt.includes(fest), `fester Text im Kontakt-Baustein: ${fest}`);
  }
  const termine = lies(join(QUELLE, 'termine-liste', 'component.svelte'));
  for (const fest of ['>Zur Anmeldung<', '>Termine werden geladen']) {
    assert.ok(!termine.includes(fest), `fester Text im Termine-Baustein: ${fest}`);
  }
});

test('BS-2a2/F6: 400 auf "postfach" hat eine eigene Meldung am Feld', () => {
  const text = lies(join(QUELLE, 'kontakt', 'component.svelte'));
  assert.match(text, /schluessel === 'postfach'/);
  assert.match(text, /fehler\.postfach/);
  assert.match(text, /id_postfach \+ '-fehler'/);
  assert.match(text, /text_postfach_fehler_server/);
});

test('BS-2a2/F6: jede Feldkennung ist ein Prop (kein Prop ohne Feld)', () => {
  for (const kennung of BAUSTEINE) {
    const feldnamen = new Set(felder(kennung).map((f) => f.name));
    const propnamen = props(kennung);
    const ohne_feld = [...propnamen].filter((name) => !feldnamen.has(name));
    assert.deepEqual(ohne_feld, [], `${kennung}: Props ohne Feld im Editor`);
    const ohne_prop = [...feldnamen].filter((name) => !propnamen.has(name));
    assert.deepEqual(ohne_prop, [], `${kennung}: Felder ohne Prop im Code`);
  }
});

// ── F7: Rückgabetyp ───────────────────────────────────────────────────────

test('BS-2a2/F7: _export_zip gibt (bytes, revision) zurück', () => {
  const text = lies(INSTALLER);
  assert.match(text, /def _export_zip\(token: str\) -> tuple\[bytes, str\]:/);
  const start = text.indexOf('def _export_zip(');
  const block = text.slice(start, start + 1600);
  assert.match(block, /return antwort\.content or b"", revision/);
});

// ── Quellen und Paket bleiben gleich ──────────────────────────────────────

test('BS-2a2: Paketkopie der Bausteine ist aktuell', () => {
  for (const kennung of BAUSTEINE) {
    for (const datei of ['component.svelte', 'fields.json', 'block.json']) {
      const a = lies(join(QUELLE, kennung, datei));
      const b = lies(join(PAKET, kennung, datei));
      assert.equal(b, a, `${kennung}/${datei}: Paket weicht ab`);
    }
  }
  assert.equal(
    Number(lies(join(PAKET, 'VERSION')).trim()),
    Number(lies(join(QUELLE, 'VERSION')).trim())
  );
});

test('BS-2a2: Dockerfile trägt den neuen Node-Test und den Backend-Test', () => {
  const pfad = join(REPO, 'backend', 'Dockerfile');
  let text;
  try {
    text = lies(pfad);
  } catch {
    return; // im Frontend-Stage liegt die Dockerfile unter /backend/Dockerfile
  }
  // FE-TEST-1: die Muster stehen in `frontend/tests/testliste.txt`.
  assert.match(text, /^ARG NODE_TESTLISTE=tests\/testliste\.txt$/m,
    'backend/Dockerfile liest die Muster nicht aus tests/testliste.txt');
  // Liste über DIE TESTDATEI auflösen (nicht über REPO): im Image liegt sie
  // neben diesem Test unter /build/tests, REPO wäre dort `/`.
  const testliste = readFileSync(new URL('./testliste.txt', import.meta.url), 'utf8');
  assert.match(testliste, /^tests\/bs2a2-\*\.test\.mjs$/m,
    'der neue Node-Test steht nicht in der Testliste (Regel 13)');
});

test('BS-2a2: kein onMount im Baustein (Primo rendert per svelte/server)', () => {
  // Abnahme-Befund 2026-11-03: `onMount` wirft im Server-Render
  // `lifecycle_outside_component`; der Publish bricht mit „Render error" ab.
  // Geprueft wird der CODE (der Kommentar nennt den Namen bewusst).
  for (const kennung of BAUSTEINE) {
    const text = lies(join(QUELLE, kennung, 'component.svelte'));
    const skript = text.split('<script>')[1].split('</script>')[0];
    const code = skript
      .split('\n')
      .filter((zeile) => !zeile.trim().startsWith('//'))
      .join('\n');
    assert.ok(!code.includes('onMount('), `${kennung}: onMount ist verboten`);
    assert.ok(!code.includes('import { onMount }'), `${kennung}: onMount importiert`);
    assert.ok(code.includes('$effect('), `${kennung}: Abruf gehoert in $effect`);
  }
});

// ── Dunkelmodus: Bausteine erben von der Site (Entscheidung 2026-11-04) ────

const STIL = (kennung) => {
  const text = lies(join(QUELLE, kennung, 'component.svelte'));
  return text.split('<style>')[1];
};

test('BS-2a2/Dunkel: keine Hexfarbe als Textfarbe (color:)', () => {
  // Befund Abnahme 2026-11-03: `color: var(--dk-farbe-text, #1f2933)` blieb im
  // `prefers-color-scheme: dark` auf einem dunklen Primo-Grund stehen
  // (Kontrast ~1,3:1 — unlesbar). Ein fester Wert darf die geerbte Textfarbe
  // der Site nicht mehr ueberschreiben.
  //
  // Ausnahme: `color` INNERHALB des Knopf-Blocks. Dort traegt der Akzent die
  // FLAECHE (erlaubt), und auf einer gefuellten Akzentflaeche ist geerbte
  // Schrift falsch — der Knopf braucht die Kontrastfarbe (weiss vorbelegt,
  // von der Site ueber --dk-farbe-knopf-text ueberschreibbar).
  for (const kennung of BAUSTEINE) {
    let imKnopf = false;
    for (const zeile of STIL(kennung).split('\n')) {
      if (/\{\s*$/.test(zeile)) imKnopf = zeile.includes('__knopf');
      if (/^\s*\}\s*$/.test(zeile)) imKnopf = false;
      if (imKnopf) continue;
      if (!/^\s*color\s*:/.test(zeile)) continue;
      assert.doesNotMatch(zeile, /#[0-9a-fA-F]{3,8}\b/,
        `${kennung}: Hexfarbe als Textfarbe -> ${zeile.trim()}`);
    }
  }
});

test('BS-2a2/Dunkel: Text und Flaeche erben von der Site', () => {
  for (const kennung of BAUSTEINE) {
    const stil = STIL(kennung);
    // Wurzelblock des Bausteins: Text erbt, Flaeche bleibt durchsichtig.
    assert.match(stil, /color:\s*var\(--dk-farbe-text,\s*inherit\)/,
      `${kennung}: Text muss erben (fallback inherit)`);
    assert.match(stil, /background:\s*var\(--dk-farbe-flaeche,\s*transparent\)/,
      `${kennung}: Flaeche muss transparent bleiben`);
    // Gedaempft und Rahmen folgen der geerbten Farbe statt eines festen Grau.
    assert.ok(stil.includes('color-mix(in srgb, currentColor 70%, transparent)'),
      `${kennung}: gedaempfte Schrift folgt currentColor`);
    assert.ok(stil.includes('color-mix(in srgb, currentColor 25%, transparent)'),
      `${kennung}: Rahmen folgt currentColor`);
  }
});

test('BS-2a2/Dunkel: Akzent nur als Flaeche/Kontur, nie als Textfarbe', () => {
  for (const kennung of BAUSTEINE) {
    for (const zeile of STIL(kennung).split('\n')) {
      if (/^\s*color\s*:/.test(zeile)) {
        assert.ok(!zeile.includes('--dk-farbe-akzent'),
          `${kennung}: Akzent darf keine Textfarbe sein -> ${zeile.trim()}`);
        assert.ok(!zeile.includes('--dk-farbe-warnung'),
          `${kennung}: Warnung darf keine Textfarbe sein (Warn-Rahmen genuegt) -> ${zeile.trim()}`);
      }
    }
  }
});

test('BS-2a2/Dunkel: Links sind unterstrichen (Auszeichnung nicht nur Farbe)', () => {
  // Ä4 „Farbe nie alleiniger Träger": die Links erben jetzt die Textfarbe,
  // also muss die Unterstreichung die Auszeichnung tragen.
  for (const kennung of BAUSTEINE) {
    const stil = STIL(kennung);
    const linkBlock = stil.slice(stil.indexOf('__link'));
    assert.ok(linkBlock.length > 0, `${kennung}: kein __link-Stil gefunden`);
    const block = linkBlock.slice(0, linkBlock.indexOf('}'));
    assert.match(block, /text-decoration:\s*underline/, `${kennung}: Link ohne Unterstreichung`);
  }
});
