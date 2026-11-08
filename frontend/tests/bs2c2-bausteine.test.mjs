/**
 * BS-2c2 — Nachbesserungen an der Baustein-Bibliothek (Review BS-2c, 07.11.).
 *
 * Drei Befunde, drei Verträge:
 *
 *   2 `neuigkeiten`       Der Container, den `aria-controls` nennt, steht IMMER
 *                         im DOM (ausgeblendet per `hidden`), nicht erst beim
 *                         Aufklappen. Sonst zeigt `aria-controls` ins Leere.
 *   3 `gruppe-steckbrief` Das Gruppenbild ist dekorativ: `alt=""`, weil der
 *                         Name direkt daneben als Überschrift steht.
 *   4 `anmeldung`         Fragt die Lese-API mit `nur_anmeldung=1` (Filter im
 *                         Server, `limit` gilt fürs Ergebnis) statt das ganze
 *                         Zeitfenster mit `limit=500` zu holen — und behält die
 *                         Kontrolle im Ergebnis (Adresse + Kennung).
 *
 * Dazu die Gegenprobe auf der Serverseite: das Feld `nur_anmeldung` steht in
 * der Lese-API und in deren Feld-Positivliste (`anmeldung_url`).
 */

import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { test } from 'node:test';

const HIER = dirname(fileURLToPath(import.meta.url));
const REPO = resolve(HIER, '..', '..');
const QUELLE = join(REPO, 'deploy', 'primo', 'bausteine');
const PAKET = join(REPO, 'backend', 'src', 'diakronos_app', 'website', 'bausteine', 'quellen');

const lies = (pfad) => readFileSync(pfad, 'utf8');
const quelle = (kennung) => lies(join(QUELLE, kennung, 'component.svelte'));
const skript = (kennung) => {
  const text = quelle(kennung);
  return text.slice(text.indexOf('<script>') + 8, text.lastIndexOf('</script>'));
};
const stil = (kennung) => {
  const text = quelle(kennung);
  const start = text.indexOf('<style>');
  return start < 0 ? '' : text.slice(start);
};

/** Das Markup EINES Beitrags in `neuigkeiten` (zwischen `{#each}`-Rumpf). */
function beitragsMarkup() {
  const text = quelle('neuigkeiten');
  const start = text.indexOf('<article');
  const ende = text.indexOf('</article>');
  assert.ok(start >= 0 && ende > start, 'neuigkeiten: kein <article> gefunden');
  return text.slice(start, ende);
}

// ── 2. Neuigkeiten: aria-controls zeigt nie ins Leere ──────────────────────

test('BS-2c2/2: der Inhalt-Container steht unbedingt im Markup (hidden statt {#if})', () => {
  const markup = beitragsMarkup();
  // Der Container mit der id, die `aria-controls` nennt, ist NICHT mehr von
  // einem `{#if}` umschlossen — sonst fehlt er im zugeklappten Zustand.
  const treffer = markup.match(/<div class="dk-neuigkeiten__inhalt" id=\{beitrag\.inhalt_id\}([\s\S]*?)>/);
  assert.ok(treffer, 'neuigkeiten: Inhalt-Container mit id fehlt');
  const kopf = treffer[1];
  assert.match(kopf, /hidden=/, 'neuigkeiten: Container wird nicht per `hidden` ausgeblendet');
  // Kein `{#if ...}` unmittelbar davor.
  const davor = markup.slice(0, markup.indexOf('<div class="dk-neuigkeiten__inhalt"')).trimEnd();
  assert.ok(!/\{#if[^}]*\}\s*$/.test(davor.split('\n').slice(-1)[0] + '\n' + (davor.split('\n').slice(-2)[0] || '')),
    'neuigkeiten: Container steht noch unter {#if}');
  // Und der Knopf spricht ihn weiterhin an.
  assert.match(markup, /aria-controls=\{beitrag\.inhalt_id\}/, 'neuigkeiten: aria-controls fehlt');
  // `hidden` MUSS die Anzeige-Regeln schlagen (Karte ist in der Liste `grid`).
  assert.match(stil('neuigkeiten'), /\[hidden\]\s*\{\s*display:\s*none\s*!important;/,
    'neuigkeiten: `hidden` wird von einer display-Regel ausgehebelt');
});

test('BS-2c2/2: ausgeblendet heisst hidden, nicht leer — nur offen ist es sichtbar', () => {
  const markup = beitragsMarkup();
  // `hidden` folgt GENAU dem Aufklapp-Zustand.
  assert.match(markup, /hidden=\{!offen\[beitrag\.id\]\}/,
    'neuigkeiten: `hidden` haengt nicht am Aufklapp-Zustand');
  // Der Inhalt selbst wird weiterhin aus `inhalt_teile` gebaut (Whitelist),
  // nicht roh eingesetzt.
  assert.match(markup, /\{#each beitrag\.inhalt_teile as teil/, 'neuigkeiten: Inhalt nicht aus inhalt_teile');
});

// ── 3. Steckbrief: dekoratives Bild ────────────────────────────────────────

test('BS-2c2/3: gruppe-steckbrief — Bild mit alt="" (Name steht als Ueberschrift daneben)', () => {
  const text = quelle('gruppe-steckbrief');
  const bilder = text.match(/<img\s[^>]*>/g) || [];
  assert.equal(bilder.length, 1, `gruppe-steckbrief: ${bilder.length} <img>`);
  assert.match(bilder[0], /\balt=""/, 'gruppe-steckbrief: Bild ohne leeres alt (doppelte Vorlesung)');
  assert.ok(!/\balt=\{befund\.name\}/.test(bilder[0]), 'gruppe-steckbrief: alt mit dem Gruppennamen');
  // Der Name steht als Ueberschrift — die Begruendung fuer alt="".
  assert.match(text, /<h2 class="dk-steckbrief__titel">\{titel_anzeige\}<\/h2>/,
    'gruppe-steckbrief: keine Ueberschrift mit dem Namen');
});

test('BS-2c2/3: jedes Baustein-Bild hat eine Alt-Entscheidung', () => {
  for (const kennung of ['gruppen', 'neuigkeiten', 'anmeldung', 'termine-liste', 'kontakt']) {
    const text = quelle(kennung);
    // Nur echte Elemente — der Kommentar nennt `<img>` im Text.
    for (const bild of text.match(/<img\s[^>]*>/g) || []) {
      // Entweder ein gepflegter Alt-Text aus den Daten (`bild_alt`) oder ein
      // bewusst leeres `alt=""` — nie ein <img> ohne alt-Attribut.
      assert.match(bild, /\salt=(\{[^}]*\}|"")/, `${kennung}: <img> ohne alt`);
    }
  }
});

// ── 4. Anmeldung: Filter im Server statt im Browser ────────────────────────

test('BS-2c2/4: anmeldung fragt die Lese-API mit nur_anmeldung=1', () => {
  const code = skript('anmeldung');
  assert.match(code, /parameter\.set\('nur_anmeldung',\s*'1'\)/,
    'anmeldung: kein nur_anmeldung-Filter in der Abfrage');
  // KEIN pauschales limit=500 mehr: das Limit haengt an „Anzahl“.
  assert.ok(!/parameter\.set\('limit',\s*'500'\)/.test(code), 'anmeldung: limit=500 fest verdrahtet');
  assert.match(code, /parameter\.set\('limit',\s*String\(Math\.min\(500,/,
    'anmeldung: Limit haengt nicht an der Anzahl');
  // Gruppen-Kennung geht an den Server (die API kennt `gruppe`).
  assert.match(code, /parameter\.set\('gruppe',\s*kennungswert\)/, 'anmeldung: Gruppe nicht an den Server');
});

test('BS-2c2/4: anmeldung behaelt die Pruefung im Ergebnis (Adresse + Kennung)', () => {
  const code = skript('anmeldung');
  assert.match(code, /if \(adresse === ''\) continue;/, 'anmeldung: Termine ohne Anmeldung bleiben');
  assert.match(code, /id !== gewuenschte_kennung/, 'anmeldung: Einzeltermin-Kennung wird nicht geprueft');
  // Anzahl gilt fuer das ERGEBNIS: der Abbruch steht nach dem Filter.
  assert.ok(code.indexOf("adresse === ''") < code.indexOf('ergebnis.length >= hoechstzahl'),
    'anmeldung: Anzahl greift vor dem Filter');
});

test('BS-2c2/4: die Lese-API kennt nur_anmeldung und behaelt die Feld-Positivliste', () => {
  const api = lies(join(REPO, 'backend', 'src', 'diakronos_app', 'website', 'oeffentlich_api.py'));
  assert.match(api, /def termine\([^)]*nur_anmeldung=None\)/s,
    'oeffentlich_api.termine: Parameter nur_anmeldung fehlt');
  assert.match(api, /t\.get\("anmeldung_url"\)/, 'oeffentlich_api: kein Nachfilter auf anmeldung_url');
  const daten = lies(join(REPO, 'backend', 'src', 'diakronos_app', 'website', 'oeffentlich_daten.py'));
  assert.match(daten, /def termine\([\s\S]*?nur_anmeldung: bool = False/,
    'oeffentlich_daten.termine: Parameter nur_anmeldung fehlt');
  assert.match(daten, /def _hat_anmeldung\(/, 'oeffentlich_daten: _hat_anmeldung fehlt');
  // Feld-Positivliste unveraendert: genau diese Schluessel, nichts Zusaetzliches.
  const auswahl = lies(join(REPO, 'backend', 'src', 'diakronos_app', 'website', 'oeffentlich_auswahl.py'));
  const block = auswahl.match(/FELDER_TERMIN\s*=\s*\(([\s\S]*?)\)/);
  assert.ok(block, 'oeffentlich_auswahl: FELDER_TERMIN fehlt');
  assert.equal(
    new Set(block[1].match(/"[a-z_]+"/g).map((s) => s.slice(1, -1))).size,
    11,
    'oeffentlich_auswahl: FELDER_TERMIN hat sich veraendert'
  );
});

// ── Auslieferung: Quelle und Paket bleiben gleich ──────────────────────────

test('BS-2c2: geaenderte Bausteine sind gespiegelt (Quelle = Paket)', () => {
  for (const kennung of ['anmeldung', 'gruppe-steckbrief', 'neuigkeiten']) {
    for (const datei of ['component.svelte', 'fields.json', 'block.json', 'README.md']) {
      const a = lies(join(QUELLE, kennung, datei));
      const b = lies(join(PAKET, kennung, datei));
      assert.equal(a, b, `${kennung}/${datei}: Paket weicht von der Quelle ab`);
    }
  }
});

// Review BS-2c2 (08.11.): `gruppe` kommt aus der Lese-API als Objekt {slug, name}
// (oeffentlich_auswahl.py). Der Vergleich im Browser muss den slug nehmen —
// `String(objekt)` ergäbe "[object Object]" und verwürfe jeden Eintrag.
test('BS-2c2: anmeldung vergleicht die Gruppe über gruppe.slug', () => {
  const pfad = resolve(dirname(fileURLToPath(import.meta.url)),
    '../../deploy/primo/bausteine/anmeldung/component.svelte');
  const quelle = readFileSync(pfad, 'utf8');
  assert.match(quelle, /eintrag\.gruppe\?\.slug/, 'Gruppe wird nicht über slug verglichen');
  assert.doesNotMatch(quelle, /String\(eintrag\.gruppe \|\|/, 'Gruppe wird als Objekt in Text gewandelt');
});
