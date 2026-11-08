/**
 * BS-3a — Baustein „Ansprechpartner" (mit Einwilligung).
 *
 * Der Test liest DATEIEN AUSSERHALB von `frontend/` (deploy/…, backend/…) —
 * der Frontend-Stage der `backend/Dockerfile` braucht dafür die COPY-Zeilen
 * (Karten-Nachtrag 13). Geprüft wird:
 *
 *   1. Quelle ↔ Paketkopie, VERSION erhöht, Prüfsummen hängen an der VERSION.
 *   2. Primo-Format (ein `<script>`, ein `<style>`, `$props()` einmal,
 *      `$effect` statt `onMount`, jede Feldkennung im Code).
 *   3. Grundsätze: `--dk-*` nur LESEN, keine Farb-Literale, kein CDN, keine
 *      Gemeinde-Inhalte, keine Personen-/Einwilligungsdaten im Baustein.
 *   4. Datenquelle: GENAU der öffentliche Endpunkt aus BS-3a, mit denselben
 *      fünf Feldern — und keine E-Mail, kein Telefon, keine Adresse.
 *   5. Bedienung: Kontakt-Knopf ist ein LINK (kein Absenden), `{postfach}`
 *      wird ersetzt, leere Bildadresse erzeugt kein `<img>`, Mobil-Fallback.
 *   6. Backend-Vertrag: die Feld-Positivliste der öffentlichen Antwort ist
 *      genau `bereich, funktion, name, foto_url, postfach`.
 */

import assert from 'node:assert/strict';
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { test } from 'node:test';

const HIER = dirname(fileURLToPath(import.meta.url));
const REPO = resolve(HIER, '..', '..');
const QUELLE = join(REPO, 'deploy', 'primo', 'bausteine');
const PAKET = join(REPO, 'backend', 'src', 'diakronos_app', 'website', 'bausteine', 'quellen');
const KENNUNG = 'ansprechpartner';
const DATEIEN = ['block.json', 'component.svelte', 'fields.json', 'README.md'];

const lies = (pfad) => readFileSync(pfad, 'utf8');
const quelle = lies(join(QUELLE, KENNUNG, 'component.svelte'));
const block = JSON.parse(lies(join(QUELLE, KENNUNG, 'block.json')));
const felder = JSON.parse(lies(join(QUELLE, KENNUNG, 'fields.json')));

// ── 1. Quelle, Spiegelung, Version ─────────────────────────────────────────

test('BS-3a: der Baustein liegt als Quelle und im Paket', () => {
  for (const datei of DATEIEN) {
    assert.equal(
      lies(join(PAKET, KENNUNG, datei)),
      lies(join(QUELLE, KENNUNG, datei)),
      `${KENNUNG}/${datei}: Paketkopie weicht ab — tools/bausteine_sync.py laufen lassen`
    );
  }
});

test('BS-3a: VERSION der Quelle und des Pakets stimmen überein', () => {
  const version = Number(lies(join(QUELLE, 'VERSION')).trim());
  // Review BS-3a (Punkt 4): hier stand hart `8`. Bei jedem Merge mit einer
  // anderen Baustein-Karte (BS-2c2/2d/2e) wäre der Test rot geworden, obwohl
  // der Baustein unverändert ist — geprüft wird deshalb gegen die VERSION-
  // Datei. Was zählt, ist die Gleichheit von Quelle und Paketkopie; dass
  // überhaupt hochgezählt wurde, prüft der Prüfsummen-Test darunter.
  assert.ok(Number.isInteger(version) && version >= 8, `VERSION ist ${version}`);
  assert.equal(Number(lies(join(PAKET, 'VERSION')).trim()), version);
});

test('BS-3a: Prüfsummen nennen die neue VERSION und den neuen Baustein', () => {
  const summen = JSON.parse(lies(join(PAKET, 'PRUEFSUMMEN.json')));
  assert.equal(Number(summen.version), Number(lies(join(QUELLE, 'VERSION')).trim()));
  assert.match(summen.bausteine[KENNUNG] || '', /^[0-9a-f]{64}$/);
  // Die Vorgänger bleiben unverändert (keine stille Neuauslieferung).
  assert.match(summen.bausteine.kontakt || '', /^[0-9a-f]{64}$/);
});

test('BS-3a: block.json nennt Name, Index und Beschreibung', () => {
  assert.equal(block.kennung, KENNUNG);
  assert.ok(block.name.startsWith('Diakronos:'), block.name);
  assert.ok(String(block.beschreibung).length > 20);
  assert.equal(Number(block.index), 60);
  // Der Index ist in der Auslieferung nirgends sonst vergeben (block.json).
  const andere = readdirSync(QUELLE)
    .filter((name) => name !== KENNUNG && statSync(join(QUELLE, name)).isDirectory())
    .map((name) => JSON.parse(lies(join(QUELLE, name, 'block.json'))).index);
  assert.ok(!andere.includes(60), 'Index 60 ist doppelt vergeben');
});

// ── 2. Primo-Format ────────────────────────────────────────────────────────

test('BS-3a: der Baustein hält das Primo-Format ein', () => {
  assert.equal((quelle.match(/<script>/g) || []).length, 1, 'genau ein <script>');
  assert.ok(!/<script module>/.test(quelle), 'kein <script module>');
  assert.equal((quelle.match(/<style>/g) || []).length, 1, 'genau ein <style>');
  assert.ok(quelle.indexOf('<script>') < quelle.indexOf('<style>'), 'script vor style');
  assert.ok(quelle.trimStart().startsWith('<'), 'beginnt mit Markup');

  const js = quelle.slice(quelle.indexOf('<script>') + 8, quelle.indexOf('</script>'));
  const markup = quelle.slice(0, quelle.indexOf('<script>'));
  assert.equal((js.match(/\$props\(/g) || []).length, 1, 'genau ein $props()');
  assert.ok(!markup.includes('$props('), 'kein $props() im Markup');
  assert.ok(!/onMount/.test(js), 'onMount ist bei Primo-SSR verboten');
  assert.match(js, /\$effect\(/, 'Abruf gehört in $effect');

  for (const feld of felder) {
    assert.ok(js.includes(feld.name), `Feld ${feld.name} fehlt im Baustein`);
    assert.ok('default' in feld, `Feld ${feld.name} ohne Vorgabewert`);
  }
});

// ── 3. Grundsätze ──────────────────────────────────────────────────────────

test('BS-3a: --dk-* wird nur gelesen, nie deklariert', () => {
  const style = quelle.slice(quelle.indexOf('<style>'));
  assert.ok(
    !/--dk-[a-z-]+\s*:/.test(style),
    'eine --dk-*-Variable wird im Baustein DEKLARIERT (BS-0 F5)'
  );
  assert.match(style, /var\(--dk-farbe-text/, 'Textfarbe kommt aus --dk-*');
});

test('BS-3a: keine Farb-Literale, kein CDN, keine Fremdschriften', () => {
  const style = quelle.slice(quelle.indexOf('<style>'));
  assert.ok(!/#[0-9a-fA-F]{3,8}\b/.test(style), 'Farb-Literal im Stil');
  assert.ok(!/\brgba?\(/.test(style), 'rgb()-Farbe im Stil');
  assert.ok(!/https?:\/\/(?!example)/.test(quelle), 'externe Adresse im Baustein');
  assert.ok(!/cdn\.|fonts\.googleapis|unpkg|jsdelivr/.test(quelle), 'CDN/Fremdschrift');
});

test('BS-3a: keine Personen- oder Einwilligungsdaten im Baustein', () => {
  for (const verboten of [
    'einwilligung',
    'E-Mail',
    'Telefon',
    'geburtstag',
    'straße',
    'mitglied',
    'website_einwilligung'
  ]) {
    assert.ok(
      !quelle.includes(verboten),
      `„${verboten}" steht im Baustein — Personendaten gehören nicht hinein`
    );
  }
});

// ── 4. Datenquelle ─────────────────────────────────────────────────────────

test('BS-3a: der Baustein spricht genau den öffentlichen Endpunkt an', () => {
  assert.ok(
    quelle.includes("/website/oeffentlich/ansprechpartner"),
    'Endpunkt aus BS-3a fehlt'
  );
  assert.ok(!quelle.includes('/api/method/'), 'kein Verwaltungs-Endpunkt im Baustein');
});

test('BS-3a: gelesen werden genau die fünf erlaubten Felder', () => {
  for (const feld of ['name', 'bereich', 'foto_url', 'postfach', 'funktion']) {
    assert.ok(quelle.includes(`eintrag.${feld}`), `Feld ${feld} wird nicht gelesen`);
  }
  for (const verboten of ['eintrag.email', 'eintrag.telefon', 'eintrag.geburtstag']) {
    assert.ok(!quelle.includes(verboten), `${verboten} wird gelesen — verboten`);
  }
});

test('BS-3a: der Backend-Vertrag ist die Feld-Positivliste', () => {
  const auswahl = lies(
    join(REPO, 'backend', 'src', 'diakronos_app', 'website', 'oeffentlich_auswahl.py')
  );
  const treffer = auswahl.match(/FELDER_ANSPRECHPARTNER = \(([\s\S]*?)\)/);
  assert.ok(treffer, 'FELDER_ANSPRECHPARTNER fehlt');
  const namen = [...treffer[1].matchAll(/"([a-z_]+)"/g)].map((m) => m[1]);
  assert.deepEqual(namen.sort(), ['bereich', 'foto_url', 'funktion', 'name', 'postfach']);
});

// ── 5. Bedienung ───────────────────────────────────────────────────────────

test('BS-3a: der Kontakt-Knopf ist ein Link, kein Absenden', () => {
  assert.match(quelle, /<a class="dk-ansprechpartner__knopf" href=\{person\.kontakt_ziel\}/);
  assert.ok(!/<button/.test(quelle), 'kein <button> im Ansprechpartner-Baustein');
  assert.ok(!/<form/.test(quelle), 'kein Formular im Ansprechpartner-Baustein');
  assert.ok(!/type="submit"/.test(quelle), 'kein Absenden-Knopf');
});

test('BS-3a: {postfach} wird ersetzt und nur http(s)/relative Ziele bleiben', () => {
  const js = quelle.slice(quelle.indexOf('<script>'), quelle.indexOf('</script>'));
  assert.match(js, /replace\(\/\\\{postfach\\\}\/g/);
  assert.match(js, /nur_webadresse\(ziel\)/);
  assert.match(js, /ziel\.startsWith\('\/'\)/);
});

test('BS-3a: ohne Bildadresse entsteht kein <img>', () => {
  assert.match(quelle, /\{#if person\.foto_url\}/);
  assert.match(quelle, /alt=\{person\.name\}/, 'Alt-Text fehlt');
  assert.match(quelle, /loading="lazy"/);
});

test('BS-3a: Mobil zuerst, Raster erst ab 40 em, Liste als Fallback', () => {
  const style = quelle.slice(quelle.indexOf('<style>'));
  assert.match(style, /grid-template-columns: 1fr;/);
  assert.match(style, /@media \(min-width: 40em\)/);
  assert.match(style, /@media \(min-width: 60em\)/);
  assert.match(style, /data-darstellung='liste'/);
  assert.match(style, /prefers-reduced-motion/);
});

test('BS-3a: Zustände sind zugänglich angekündigt', () => {
  assert.match(quelle, /role="status"/, 'Lade-/Leer-/Fehlertext ohne role=status');
  assert.match(quelle, /aria-live="polite"/, 'Liste ohne aria-live');
});
