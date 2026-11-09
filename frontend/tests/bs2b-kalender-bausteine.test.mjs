/**
 * BS-2b — Bausteine „Kalender", „Nächster Gottesdienst", „Kalender-Abo".
 *
 * Der Test liest DATEIEN AUSSERHALB von `frontend/` (deploy/…, backend/…) —
 * der Frontend-Stage der `backend/Dockerfile` braucht dafür die passenden
 * COPY-Zeilen (Karten-Nachtrag 13: sonst im Worktree grün, im Image rot).
 *
 * Geprüft wird:
 *   1. Quellen ↔ Paketkopie, VERSION erhöht, Installer nimmt sie von selbst auf.
 *   2. Monatsraster: Länge, Wochenstart Montag/Sonntag, Jahreswechsel,
 *      Schaltjahr — gegen die Rechenschicht `kalenderlogik.mjs`.
 *   3. Zeitzonenwechsel Ende Oktober (MESZ → MEZ, 25-Stunden-Tag): der Tag
 *      bleibt der Tag, die Uhrzeit bleibt die Uhrzeit.
 *   4. Primo-Format (ein `<script>`, `$props()` einmal, Feldkennungen im Code),
 *      `--dk-*` nur lesen, keine Farben/CDN/Gemeinde-Inhalte.
 *   5. Die Bausteine sprechen die belegten Endpunkte aus BS-1b an
 *      (termine/naechster_termin/kalender + iCal-Adresse …ics).
 *   6. Kalender-Baustein: Startansicht, Vor/Heute/Weiter, Detail mit
 *      Anmelde-Link, Mobil-Fallback (Liste), Knöpfe ohne Absenden (type=button).
 *   7. BS-2e (Abnahme am echten Primo): Vorlesezeile ohne doppelte Tageszahl,
 *      Leiste mobil ausgeblendet statt wirkungslos, Liste zeigt den ganzen
 *      Monat (vergangene Tage gedämpft).
 */

import assert from 'node:assert/strict';
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { test } from 'node:test';

import * as L from '../../deploy/primo/bausteine/kalender/kalenderlogik.mjs';

const HIER = dirname(fileURLToPath(import.meta.url));
const REPO = resolve(HIER, '..', '..');
const QUELLE = join(REPO, 'deploy', 'primo', 'bausteine');
const PAKET = join(REPO, 'backend', 'src', 'diakronos_app', 'website', 'bausteine', 'quellen');

const NEU = ['kalender', 'kalender-abo', 'naechster-gottesdienst'];
const DATEIEN = ['block.json', 'component.svelte', 'fields.json', 'README.md'];

const lies = (pfad) => readFileSync(pfad, 'utf8');
const quelle = (kennung) => lies(join(QUELLE, kennung, 'component.svelte'));
const felder = (kennung) => JSON.parse(lies(join(QUELLE, kennung, 'fields.json')));

function kennungen(wurzel) {
  return readdirSync(wurzel)
    .filter((name) => statSync(join(wurzel, name)).isDirectory())
    .filter((name) => /^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(name))
    .sort();
}

// ── 1. Quellen, Spiegelung, Version ────────────────────────────────────────

test('BS-2b: die drei Bausteine liegen als Quelle und im Paket', () => {
  const vorhanden = kennungen(QUELLE);
  for (const kennung of NEU) {
    assert.ok(vorhanden.includes(kennung), `${kennung} fehlt in deploy/primo/bausteine`);
    for (const datei of DATEIEN) {
      assert.equal(
        lies(join(PAKET, kennung, datei)),
        lies(join(QUELLE, kennung, datei)),
        `${kennung}/${datei}: Paketkopie weicht ab — tools/bausteine_sync.py laufen lassen`
      );
    }
  }
});

test('BS-2b: VERSION ist gegenüber BS-2a erhöht (5 -> 6)', () => {
  const version = Number(lies(join(QUELLE, 'VERSION')).trim());
  assert.ok(Number.isInteger(version) && version >= 6, `VERSION ist ${version}`);
  assert.equal(Number(lies(join(PAKET, 'VERSION')).trim()), version);
});

test('BS-2b: Prüfsummen nennen die neue VERSION und die neuen Bausteine', () => {
  const summen = JSON.parse(lies(join(PAKET, 'PRUEFSUMMEN.json')));
  assert.equal(Number(summen.version), Number(lies(join(QUELLE, 'VERSION')).trim()));
  for (const kennung of NEU) {
    assert.match(summen.bausteine[kennung] || '', /^[0-9a-f]{64}$/, `${kennung} ohne Prüfsumme`);
  }
});

test('BS-2b: block.json ordnet die Bausteine eindeutig ein', () => {
  const indizes = kennungen(QUELLE).map((kennung) => {
    const block = JSON.parse(lies(join(QUELLE, kennung, 'block.json')));
    assert.equal(block.kennung, kennung);
    assert.ok(block.name.startsWith('Diakronos:'), block.name);
    assert.ok(String(block.beschreibung || '').length > 20, `${kennung}: Beschreibung fehlt`);
    return block.index;
  });
  assert.equal(new Set(indizes).size, indizes.length, 'doppelter Anzeige-Index');
});

// ── 2. Primo-Format und Grundsätze ─────────────────────────────────────────

for (const kennung of NEU) {
  test(`BS-2b: ${kennung} hält das Primo-Format ein`, () => {
    const text = quelle(kennung);
    // Genau EIN Instanz-<script>; ein zweiter, module-weiter Block ist erlaubt
    // (nur für die Prüfung des Stammsatzes, siehe Begründung im Block).
    assert.equal((text.match(/<script>/g) || []).length, 1, 'genau ein <script>');
    // Ein module-Block wäre in Primo eine zweite Baustelle — der Block trägt
    // seinen Stammsatz im Instanz-<script> (geprüft im Abschnitt 7).
    assert.ok(!/<script module>/.test(text), 'kein <script module> (Primo-Format)');
    assert.equal((text.match(/<style>/g) || []).length, 1, 'genau ein <style>');
    assert.ok(text.indexOf('<script>') < text.indexOf('<style>'), 'script vor style');
    assert.ok(text.trimStart().startsWith('<'), 'beginnt mit Markup');

    const js = text.slice(text.indexOf('<script>') + 8, text.indexOf('</script>'));
    const markup = text.slice(0, text.indexOf('<script>'));
    assert.equal((js.match(/\$props\(/g) || []).length, 1, 'genau ein $props()');
    assert.ok(!markup.includes('$props('), 'kein $props() im Markup');
    // Kein onMount: Primo rendert Abschnitte mit svelte/server (BS-2a2-Befund).
    assert.ok(!/onMount/.test(js), 'onMount ist bei Primo-SSR verboten');
    assert.match(js, /\$effect\(/, 'Abruf gehört in $effect');

    for (const feld of felder(kennung)) {
      assert.ok(js.includes(feld.name), `Feld ${feld.name} fehlt im Baustein`);
      assert.ok('default' in feld, `Feld ${feld.name} ohne Vorgabewert`);
    }
  });

  test(`BS-2b: ${kennung} liest --dk-* nur und bringt keine Fremdinhalte mit`, () => {
    const text = quelle(kennung);
    assert.equal(/^\s*--dk-[a-z-]+\s*:/m.test(text), false, 'deklariert ein --dk-Token');
    assert.ok(text.includes('var(--dk-'), 'liest keine --dk-Tokens');
    for (const farbe of text.match(/#[0-9a-fA-F]{3,8}\b/g) || []) {
      const muster = new RegExp(`var\\(--dk-[a-z-]+,\\s*${farbe}`);
      assert.match(text, muster, `${kennung}: Farbe ${farbe} nicht als var()-Fallback`);
    }
    for (const verboten of ['esm.sh', 'fonts.googleapis', 'cdn.jsdelivr', 'unpkg.com', 'Musterhausen', 'ECG']) {
      assert.ok(!text.includes(verboten), `${kennung}: ${verboten}`);
    }
    // Eigene Hilfslogik je Block (README Regel 1: keine Importe zwischen Blöcken).
    assert.ok(!/from\s+['"]\.\.?\//.test(text), `${kennung}: importiert aus anderem Baustein`);
    assert.match(text, /function nur_webadresse\(/, 'absolute Adresse fehlt');
    assert.match(text, /AbortController/, 'Zeitlimit/Abbruch fehlt');
    assert.match(text, /await fetch\(/, 'kein client-seitiger Abruf');
  });
}

test('BS-2b: jeder Baustein holt seine Daten von der Lese-API (BS-1b)', () => {
  assert.ok(quelle('kalender').includes("'/website/oeffentlich/termine?'"), 'Kalender: falscher Pfad');
  for (const teil of ['kalender', 'kategorie', 'gruppe']) {
    assert.ok(quelle('kalender').includes(`parameter.set('${teil}'`), `Kalender: Parameter ${teil} fehlt`);
  }
  // Der Kalender fragt volle Monate ab (Fenster = Monat, nicht Raster).
  assert.match(quelle('kalender'), /function stand_schluessel\(/, 'Kalender: Monatsfenster fehlt');
  assert.ok(
    quelle('naechster-gottesdienst').includes("'/website/oeffentlich/naechster_termin'"),
    'Gottesdienst: falscher Pfad'
  );
  assert.ok(quelle('kalender-abo').includes("'/website/oeffentlich/kalender'"), 'Abo: Kalenderliste fehlt');
  assert.ok(quelle('kalender-abo').includes("'/website/ical/'"), 'Abo: iCal-Pfad fehlt');
  assert.ok(quelle('kalender-abo').includes("'.ics'"), 'Abo: .ics fehlt');
});

test('BS-2b: alle Knöpfe sind type="button" (kein Absenden)', () => {
  for (const kennung of NEU) {
    const text = quelle(kennung);
    for (const knopf of text.match(/<button[^>]*>/g) || []) {
      assert.match(knopf, /type="button"/, `${kennung}: ${knopf}`);
    }
  }
});

// ── 3. Startansicht, Steuerung, Detail, Mobil-Fallback ────────────────────

test('BS-2b: der Kalender hat Startansicht, Umschaltung, Vor/Heute/Weiter', () => {
  const text = quelle('kalender');
  const namen = felder('kalender').map((f) => f.name);
  for (const feld of ['startansicht', 'ansicht_umschaltbar', 'wochenstart', 'farben_kalender', 'kalender', 'kategorie']) {
    assert.ok(namen.includes(feld), `Feld ${feld} fehlt`);
  }
  const start = felder('kalender').find((f) => f.name === 'startansicht');
  assert.deepEqual(
    start.config.options.map((o) => o.value).sort(),
    ['liste', 'monat'],
    'Startansicht kennt die zwei Ansichten'
  );
  for (const knopf of ['text_heute', 'text_zurueck', 'text_weiter', 'text_monat', 'text_liste']) {
    assert.ok(text.includes(`{${knopf}}`), `${knopf} wird nicht angezeigt`);
  }
  assert.match(text, /function schritt\(/, 'Vor/Zurück fehlt');
  assert.match(text, /function heute\(/, 'Heute fehlt');
  assert.match(text, /aria-pressed=/, 'Umschaltung ohne aria-pressed');
});

test('BS-2b: Klick auf einen Termin öffnet das Detail mit Anmeldelink', () => {
  const text = quelle('kalender');
  assert.match(text, /function oeffnen\(/);
  assert.ok(text.includes('detail.datum_lang'), 'Detail ohne Datum');
  assert.match(text, /ende_text\(eintrag\.beginn, eintrag\.ende\)/, 'Zeitraum des Termins fehlt');
  assert.ok(text.includes('detail.ort'), 'Detail ohne Ort');
  assert.ok(text.includes('detail.beschreibung'), 'Detail ohne Beschreibung');
  assert.ok(text.includes('detail.anmeldung_url'), 'Detail ohne Anmelde-Link');
  assert.match(text, /aria-live="polite"/, 'Detail nicht angesagt');
});

// NACHARBEIT 08.11. (Review, schwer 1+3, mittel 5+6, klein 7):
test('BS-2b/Raster: jede Zeile ist eine <tr> mit sieben Zellen', () => {
  const text = quelle('kalender');
  const markup = text.slice(0, text.indexOf('<script>'));
  // <td> darf nur in <tr> stehen — sonst ordnet der Browser sie fremd an und
  // die Zellen bleiben leer (Review-Befund 1).
  assert.match(markup, /<tbody>\s*\{#each rasterwochen as woche/, 'keine Wochen-Schleife');
  assert.match(markup, /<tr>\s*\{#each woche\.tage as tag/, 'keine Zellen-Schleife in <tr>');
  assert.equal((markup.match(/<tbody>[\s\S]*?<\/tbody>/)[0].match(/<td/g) || []).length, 1,
    'die Vorlage hat mehr als eine <td>-Stelle (Schleife fehlt?)');
  assert.ok(!/<tbody>\s*\{#each [^}]*\}\s*<td/.test(markup), '<td> direkt unter <tbody>');
});

test('BS-2b/Raster: Termine sind Knöpfe (Klick und Tastatur öffnen das Detail)', () => {
  const text = quelle('kalender');
  const markup = text.slice(0, text.indexOf('<script>'));
  const zelle = markup.slice(markup.indexOf('dk-kalender__tagesliste'), markup.indexOf('</td>'));
  assert.match(zelle, /<button[\s\S]*?type="button"[\s\S]*?class="dk-kalender__eintrag"/, 'Rastereintrag ist kein Knopf');
  assert.match(zelle, /onclick=\{\(ereignis\) => \{ oeffnen\(termin\.id, ereignis\); \}\}/, 'Klick öffnet das Detail nicht');
  assert.match(zelle, /aria-label=\{termin\.vorlesetext\}/, 'Knopf ohne gesprochenen Namen');
  // Fokus geht beim Öffnen auf die Detail-Überschrift, Escape schließt, der
  // Fokus kehrt zum auslösenden Termin zurück (mittel 5).
  assert.match(text, /tabindex="-1" bind:this=\{detailkopf\}/, 'Detailtitel nicht fokussierbar');
  // Fokus wird NACH dem Rendern gesetzt (der Effekt über dem {#if} sähe den
  // neuen Zweig in Svelte 5 noch nicht) — deshalb async + Fokus im Zweig.
  assert.match(text, /if \(detail !== ziel\) return;/, 'Fokus ohne Bezug zum geöffneten Detail');
  assert.match(text, /if \(detailkopf && typeof detailkopf\.focus === 'function'\) detailkopf\.focus\(\)/,
    'kein Fokus auf den Detailtitel');
  assert.match(text, /ereignis\.key === 'Escape'/, 'Escape schließt nicht');
  assert.match(text, /setTimeout\(\(\) => \{\s*\n\s*if \(detail !== null\) return;\s*\n\s*ziel\.focus\(\);/, 'Fokus kehrt nicht zurück');
});

test('BS-2b: Leertext, Farben und veraltete Abrufe', () => {
  const text = quelle('kalender');
  // mittel 6: Leertext aus den Terminen der GEZEIGTEN Ansicht (nicht aus dem
  // Raster, wenn die Liste steht). BS-2e: die Liste führt jetzt den ganzen
  // Monat (`liste_zeilen`).
  assert.match(text, /let anzahl_ansicht = \$derived\(raster_sichtbar \? termine\.length : liste_zeilen\.length\)/,
    'Leertext zählt nicht die gezeigte Ansicht');
  assert.match(text, /#if anzahl_ansicht === 0/, 'Leertext hängt an der falschen Größe');
  assert.ok(!text.includes('{#if liste.length === 0}'), 'Leertext noch aus `liste`');
  // mittel 6: „Farben aus Kalender" wird dargestellt (Streifen am Termin).
  assert.match(text, /style:border-left-color=\{termin\.farbe \|\| null\}/, 'Terminfarbe wird nicht angezeigt');
  // mittel 6: `text_mehr` gehoert zur Eingabe „weitere“ (die Zelle zeigt „+n weitere“).

  // klein 7: nur die Antwort des jüngsten Abrufs zählt.
  assert.match(text, /let abruf_nr = 0/, 'kein Abruf-Zähler');
  assert.match(text, /if \(!abruf_ist_aktuell\(meine, abruf_nr\)\) return/, 'veraltete Antwort wird nicht verworfen');
});

test('BS-2b: relative Anmeldeadressen bekommen die Diakronos-Basis', () => {
  const text = quelle('kalender');
  assert.match(text, /function anmelde_adresse\(/);
  assert.match(text, /anmeldung_url: anmelde_adresse\(eintrag\.anmeldung_url\)/, 'Anmeldeadresse nicht aufgebaut');
  assert.ok(!text.includes('anmeldung_url: nur_webadresse(eintrag.anmeldung_url)'),
    'relative Anmeldeadresse fällt weiter weg');
});

// NACHARBEIT 08.11. (Review): Primo gibt Block-CSS in eigener Reihenfolge aus
// (und schreibt Selektoren um) — ein CSS-Umschalter ist dort nicht verlässlich.
// Deshalb schaltet der Block über das `hidden`-Attribut: Markup, kein CSS.
// BS-2e (Abnahme 08.11., Befund B3): unter 40 em war die Umschaltung
// wirkungslos (das Raster war dort ohnehin aus). Mobil gilt jetzt die Liste,
// die Leiste entfällt — es gibt keinen Knopf ohne Wirkung.
test('BS-2e: mobil zeigt der Kalender die Liste, die Umschaltung entfällt', () => {
  const text = quelle('kalender');
  // Beide Ansichten stehen IMMER im DOM und werden über `hidden` geschaltet.
  assert.match(text, /let liste_sichtbar = \$derived\(ansicht === 'liste'\)/,
    'Liste hängt nicht an der Ansicht');
  assert.match(text, /let raster_sichtbar = \$derived\(ansicht === 'monat'\)/,
    'Raster hängt nicht an der Ansicht');
  assert.match(text, /let leiste_sichtbar = \$derived\(umschaltbar && !ist_schmal\)/,
    'Leiste nicht an die Breite gebunden');
  assert.match(text, /\{#if leiste_sichtbar\}/, 'Leiste ohne Sichtbarkeitsbedingung');
  assert.match(text, /function schmal_umstellen\(schmal\)/, 'Breitenwechsel stellt die Ansicht nicht um');
  assert.match(text, /<ul class="dk-kalender__liste" hidden=\{!liste_sichtbar\}>/, 'Liste ohne hidden-Schaltung');
  assert.ok(!/#if ansicht === 'monat'/.test(text), 'Markup hängt noch an einer Ansichts-Bedingung');
  assert.match(text, /\{#if raster_sichtbar\}\s*\n\s*<table class="dk-kalender__raster">/, 'Raster ohne Sichtbarkeitsbedingung');
  // Die Breite kommt aus dem Browser (matchMedia, 40em wie die Site-Regeln);
  // bei SSR gibt es kein window — der Effekt darf SSR nicht sprengen.
  assert.match(text, /matchMedia\('\(min-width: ' \+ BREIT_AB \+ '\)'\)/, 'kein matchMedia');
  assert.ok(text.includes("const BREIT_AB = '40em'"), 'Breitengrenze fehlt');
  assert.match(text, /typeof window === 'undefined'/, 'SSR-Wächter fehlt');
  // Die Schaltung selbst muss `display:none` auch gegen Site-Stile halten.
  assert.match(text, /\[hidden\]\s*\{\s*display:\s*none !important/, 'hidden nicht abgesichert');
});

// BS-2e (Befund B1): Primo liefert das Block-CSS nur beim Publish aus — im
// Editor steht das Markup ohne Stylesheet da und die Vorlesezeile
// („10. November") wurde sichtbar: „10 10. November". Sie braucht deshalb ein
// KLASSEN-Kennzeichen, das ohne Nachfahren-Selektor greift.
test('BS-2e: die Vorlesezeile der Tageszelle trägt ein eigenes Klassen-Kennzeichen', () => {
  const text = quelle('kalender');
  assert.match(text, /<span class="dk-kalender__versteckt dk-versteckt">/, 'Kennzeichen fehlt am Span');
  assert.match(text, /\.dk-kalender__versteckt,\s*\n\s*\.dk-versteckt\s*\{/, 'Regel für das Kennzeichen fehlt');
  assert.match(text, /clip-path: inset\(50%\)/, 'clip-path (heutige Vorlese-Technik) fehlt');
});

// BS-2e (Befund B4): Die Liste zeigt den GANZEN gezeigten Monat — vorher
// fielen vergangene Tage weg und der Monat wirkte leer. Der Leertext gilt
// deshalb auch für die Liste.
test('BS-2e: die Liste zeigt den ganzen Monat, vergangene Tage gedämpft', () => {
  const text = quelle('kalender');
  assert.match(text, /let liste_zeilen = \$derived\(\s*\n\s*termine/, 'Liste hängt noch an „ab heute"');
  assert.ok(!/zeile\.iso >= heute_iso\)\s*\n\s*\.sort/.test(
    text.slice(text.indexOf('let liste_zeilen'), text.indexOf('let liste_zeilen') + 500)),
  'Liste filtert noch auf künftige Tage');
  assert.match(text, /class:vergangen=\{termin\.iso < heute_iso\}/, 'vergangene Zeile nicht gekennzeichnet');
  assert.match(text, /let anzahl_ansicht = \$derived\(raster_sichtbar \? termine\.length : liste_zeilen\.length\)/,
    'Leertext rechnet mit der falschen Menge');
});

// ── 4. Monatsraster, Wochenstart, Zeitzonenwechsel ────────────────────────

test('BS-2b/Raster: Oktober 2026 beginnt am Donnerstag, 31 Tage, 5 Wochen', () => {
  const raster = L.monatsraster(2026, 10, 'montag', '');
  assert.equal(raster.length % 7, 0, 'keine vollen Wochen');
  assert.equal(raster.length, 35);
  // 1.10.2026 ist ein Donnerstag -> Montag davor ist der 28.09.
  assert.equal(raster[0].iso, '2026-09-28');
  assert.equal(raster[0].wochentag, 1, 'Raster beginnt nicht am Montag');
  assert.equal(raster[raster.length - 1].iso, '2026-11-01');
  assert.equal(L.tage_im_monat(2026, 10), 31);
  assert.equal(raster.filter((t) => t.im_monat).length, 31);
});

test('BS-2b/Raster: Wochenstart Sonntag beginnt am Sonntag', () => {
  const raster = L.monatsraster(2026, 10, 'sonntag', '');
  assert.equal(raster[0].wochentag, 0, 'Raster beginnt nicht am Sonntag');
  assert.equal(raster[0].iso, '2026-09-27');
  assert.equal(raster.length % 7, 0);
  assert.deepEqual(L.raster_kopf('sonntag'), ['So', 'Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa']);
  assert.deepEqual(L.raster_kopf('montag'), ['Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So']);
});

test('BS-2b/Raster: „Heute" wird genau einmal und nur im Monat markiert', () => {
  const raster = L.monatsraster(2026, 10, 'montag', '2026-10-24');
  const heute = raster.filter((t) => t.heute);
  assert.equal(heute.length, 1);
  assert.equal(heute[0].iso, '2026-10-24');
  assert.equal(heute[0].im_monat, true);
});

test('BS-2b/Raster: Monatswechsel über die Jahresgrenze', () => {
  assert.deepEqual(L.monat_verschieben(2026, 1, -1), { jahr: 2025, monat: 12 });
  assert.deepEqual(L.monat_verschieben(2026, 12, 1), { jahr: 2027, monat: 1 });
  assert.equal(L.monat_titel(2025, 12), 'Dezember 2025');
  assert.equal(L.monat_ende(2026, 12), '2026-12-31');
  // Februar im Schaltjahr / Nicht-Schaltjahr / Säkularjahr.
  assert.equal(L.tage_im_monat(2024, 2), 29);
  assert.equal(L.tage_im_monat(2026, 2), 28);
  assert.equal(L.tage_im_monat(2100, 2), 28);
  assert.equal(L.tage_im_monat(2000, 2), 29);
});

// Die Zeitrechnung setzt eine vollständige ICU-Datenbank voraus (Europe/Berlin
// mit MESZ/MEZ). Fehlt sie in einer Node-Ausführung (small-icu), meldet dieser
// Wächter das — statt die Zeitzonentests mit falschen Stunden zu „bestehen".
function icu_kennt_zeitzone() {
  try {
    return new Intl.DateTimeFormat('de-DE', { timeZone: 'Europe/Berlin', timeZoneName: 'short' })
      .format(new Date('2026-07-01T12:00:00Z'))
      .includes('MESZ');
  } catch (fehler) {
    return false;
  }
}

test('BS-2b/Zeitzone: die Laufzeit kennt Europe/Berlin mit Sommerzeit', () => {
  assert.ok(icu_kennt_zeitzone(), 'Node ohne vollständige ICU-Daten (small-icu) — Zeitzonentests nicht belastbar');
});

test('BS-2b/Zeitzone: Ende Oktober bleibt der Tag der 25. (25-Stunden-Tag)', () => {
  // 2026-10-25: Umstellung MESZ -> MEZ um 03:00 Ortszeit.
  const vorher = new Date('2026-10-24T22:30:00Z'); // 25.10. 00:30 MESZ
  const nachher = new Date('2026-10-25T23:30:00Z'); // 26.10. 00:30 MEZ
  assert.equal(L.isodatum(vorher), '2026-10-25');
  assert.equal(L.uhrzeittext(vorher), '00:30');
  assert.equal(L.isodatum(nachher), '2026-10-26');
  assert.equal(L.uhrzeittext(nachher), '00:30');
  // Die doppelte Stunde: 02:30 MESZ (= 00:30Z) und 02:30 MEZ (= 01:30Z).
  assert.equal(L.uhrzeittext(new Date('2026-10-25T00:30:00Z')), '02:30');
  assert.equal(L.uhrzeittext(new Date('2026-10-25T01:30:00Z')), '02:30');
  // Ein Termin über die doppelte Stunde hinweg: 02:30 MESZ (= 00:30Z) bis
  // 03:30 MEZ (= 02:30Z). Das Fenster zeigt 02:30 – 03:30, also den Sprung
  // von der Sommer- auf die Winterzeit. Vor der Umstellung liegt Berlin zwei
  // Stunden vor UTC (MESZ), danach eine (MEZ) — genau diese Stunde ist der
  // Prüfstein; eine Rechnung in UTC ergäbe 02:30 – 04:30.
  const beginn = new Date('2026-10-25T00:30:00Z'); // 02:30 MESZ
  const ende = new Date('2026-10-25T02:30:00Z'); // 03:30 MEZ
  assert.equal(L.zeitfenster(beginn.toISOString(), ende.toISOString()), '02:30 – 03:30');
  // Tagestext des 25.10.2026 ist ein Sonntag.
  assert.equal(L.tagestext('2026-10-25'), 'So., 25.10.');
  assert.equal(L.tagestext_lang('2026-10-25'), 'Sonntag, 25. Oktober 2026');
});

test('BS-2b/Zeitzone: späte UTC-Zeit gehört schon zum nächsten Tag', () => {
  // 23:30Z am 31.10. ist in Berlin bereits der 01.11.
  // Ein Termin am 01.11. 00:30 Ortszeit (23:30Z am 31.10.) — in Berlin ist
  // das schon der nächste Tag, die Uhrzeit bleibt 00:30 MEZ.
  assert.equal(L.isodatum(new Date('2026-10-31T23:30:00Z')), '2026-11-01');
  assert.equal(L.uhrzeittext(new Date('2026-10-31T23:30:00Z')), '00:30');
  // Reicht ein Termin über Mitternacht, zeigt das Zeitfenster nur den Beginn.
  assert.equal(L.zeitfenster('2026-10-31T23:30:00Z', '2026-11-01T02:00:00Z'), '00:30 – 03:00');
  assert.equal(L.zeitangabe({ beginn: '2026-11-08T10:00:00Z', ganztaegig: true }), 'ganztägig');
});

test('BS-2b: Termine werden dem richtigen Kalendertag zugeordnet', () => {
  const karte = L.termine_je_tag([
    { id: 'a', beginn: '2026-10-25T08:00:00Z' },
    { id: 'b', beginn: '2026-10-25T18:00:00Z' },
    { id: 'c', beginn: '2026-10-24T22:00:00Z' },
    { id: 'kaputt', beginn: '' }
  ]);
  // c beginnt 00:00 Ortszeit am 25.10. (22:00Z am 24.) — derselbe Kalendertag.
  assert.deepEqual(karte.get('2026-10-25').map((e) => e.id), ['a', 'b', 'c']);
  assert.equal(karte.has('2026-10-24'), false, 'UTC-Datum ist nicht der Kalendertag der Gemeinde');
});

test('BS-2b: nur gültige Farben gelangen ins CSS', () => {
  assert.equal(L.farbe_wert('#0a7'), '#0a7');
  assert.equal(L.farbe_wert('#0066cc'), '#0066cc');
  assert.equal(L.farbe_wert('rgb(1,2,3)'), 'rgb(1,2,3)');
  assert.equal(L.farbe_wert('url(javascript:alert(1))'), '');
  assert.equal(L.farbe_wert('red;} body{display:none'), '');
  assert.equal(L.farbe_wert(''), '');
});

test('BS-2b: Kennungen und Adressen werden geprüft', () => {
  assert.deepEqual(L.kennungen(' a, b ,,c '), ['a', 'b', 'c']);
  assert.deepEqual(L.kennungen(''), []);
  assert.equal(L.nur_webadresse('https://gem.example/diakronos/'), 'https://gem.example/diakronos');
  assert.equal(L.nur_webadresse('javascript:alert(1)'), '');
  assert.equal(L.nur_webadresse('/diakronos'), '');
  assert.equal(L.zahl('12', 5, 1, 50), 12);
  assert.equal(L.zahl('999', 5, 1, 50), 50);
  assert.equal(L.zahl('x', 5, 1, 50), 5);
});

test('BS-2b/Raster: mehrtägige Termine nennen ihren Zeitraum (kein Tag abgezogen)', () => {
  // Ganztags-Ende kommt einschließlich aus der Lese-API (BS-2a2/F1) — die
  // Kalender-Hilfslogik übernimmt das unverändert.
  assert.equal(L.ende_text('2026-11-07T00:00:00Z', '2026-11-09T00:00:00Z'), 'Mo., 09.11.');
  // Eintägig (gleicher Kalendertag) bleibt ohne Zeitraum.
  assert.equal(L.ende_text('2026-11-08T10:00:00Z', '2026-11-08T11:30:00Z'), '');
  // Ohne Ende kein Zeitraum.
  assert.equal(L.ende_text('2026-11-08T10:00:00Z', ''), '');
  // Der Kalender-Baustein zeigt ihn in Liste und Detail.
  const text = quelle('kalender');
  assert.match(text, /function ende_text\(/);
  assert.ok(text.includes('{termin.zeitraum}'), 'Liste ohne Zeitraum');
  assert.match(text, /ende_text\(eintrag\.beginn, eintrag\.ende\)/, 'Detail ohne Zeitraum');
});

// ── 7. Stammsatz (NACHARBEIT 08.11.): Block und Prüfdatei rechnen gleich ──

const BLOCK = quelle('kalender');
const BLOCK_JS = BLOCK.slice(BLOCK.indexOf('<script>') + 8, BLOCK.indexOf('</script>'));

test('BS-2b/Kalender: der Block führt die geprüfte Kalenderlogik selbst mit', () => {
  for (const name of [
    'monat_versionschieben'.replace('versionschieben', 'verschieben'),
    'zeitraum_ein_monat',
    'raster_wochen',
    'zelle_aufteilen',
    'abruf_ist_aktuell',
    'anmelde_adresse'
  ]) {
    const muster = name === 'monat_verschieben' ? /function schritt\(/ : new RegExp(`function ${name}\\(`);
    assert.match(BLOCK_JS, muster, `${name}: nicht im Block`);
  }
});

test('BS-2b: Zeilen- und Wochenaufteilung rechnet richtig', () => {
  const raster = L.monatsraster(2026, 10, 'montag', '');
  const wochen = L.raster_wochen(raster);
  assert.equal(wochen.length, 5, 'Oktober 2026 hat fünf Rasterwochen');
  for (const woche of wochen) {
    assert.equal(woche.tage.length, 7, 'Woche ohne sieben Tage');
    assert.match(woche.schluessel, /^\d{4}-\d{2}-\d{2}$/, 'Wochenschlüssel fehlt');
  }
  assert.deepEqual(wochen.map((w) => w.tage[0].wochentag), [1, 1, 1, 1, 1], 'Wochen starten nicht am Montag');
  // Sechs Wochen bei Monaten, die einen Sonntag-Start brauchen.
  // August 2026: 1. ist Samstag, 31. ist Montag -> sechs volle Wochen.
  const sechs = L.raster_wochen(L.monatsraster(2026, 8, 'montag', ''));
  assert.equal(sechs.length, 6, 'August 2026 braucht sechs Rasterwochen');
  assert.equal(sechs[0].tage[0].iso, '2026-07-27');
});

test('BS-2b: eine Zelle zeigt höchstens drei Termine, der Rest als „+n“', () => {
  const zwei = L.zelle_aufteilen([{ id: 'a' }, { id: 'b' }], 3);
  assert.equal(zwei.termine.length, 2);
  assert.equal(zwei.weitere, 0);
  const fuenf = L.zelle_aufteilen([1, 2, 3, 4, 5], 3);
  assert.deepEqual(fuenf.termine, [1, 2, 3]);
  assert.equal(fuenf.weitere, 2);
  assert.deepEqual(L.zelle_aufteilen(null, 3), { termine: [], weitere: 0 });
  // Grenze 0 bedeutet „Vorgabe" (3), nie „alle weg".
  assert.equal(L.zelle_aufteilen([1, 2], 0).termine.length, 2);
});

test('BS-2b: Monatsfenster für den Abruf ist der volle Monat', () => {
  assert.deepEqual(L.zeitraum_ein_monat(2026, 2), { von: '2026-02-01', bis: '2026-02-28' });
  assert.deepEqual(L.zeitraum_ein_monat(2024, 2), { von: '2024-02-01', bis: '2024-02-29' });
  assert.deepEqual(L.zeitraum_ein_monat(2026, 10), { von: '2026-10-01', bis: '2026-10-31' });
});

test('BS-2b: nur die Antwort des jüngsten Abrufs gilt', () => {
  assert.equal(L.abruf_ist_aktuell(2, 3), false, 'alte Antwort gelte als aktuell');
  assert.equal(L.abruf_ist_aktuell(3, 3), true, 'neueste Antwort verworfen');
  assert.equal(L.abruf_ist_aktuell('3', 3), true, 'Text/Zahl nicht vergleichbar');
});

test('BS-2b: relative Anmeldeadressen bekommen die Basis (Präfix nur einmal)', () => {
  const basis = 'https://gem.example/diakronos';
  assert.equal(L.anmelde_adresse('/diakonos/gast?token=x', basis), 'https://gem.example/diakonos/gast?token=x');
  // Pfad trägt den Präfix schon -> nicht verdoppeln.
  assert.equal(L.anmelde_adresse('/diakronos/diakonos/gast?t=1', basis),
    'https://gem.example/diakronos/diakonos/gast?t=1');
  // Ohne Präfix in der Basis kein doppelter Pfad.
  assert.equal(L.anmelde_adresse('/diakonos/gast', 'https://gem.example'),
    'https://gem.example/diakonos/gast');
  // Absolute Adresse bleibt, Fremdschemata fallen weg.
  assert.equal(L.anmelde_adresse('https://gem.example/x/', basis), 'https://gem.example/x');
  assert.equal(L.anmelde_adresse('javascript:alert(1)', basis), '');
  assert.equal(L.anmelde_adresse('/x', ''), '', 'ohne Basis kein relativer Link');
});

test('BS-2b: kalender-abo vergibt die Feldkennung über $props.id()', () => {
  const text = quelle('kalender-abo');
  assert.ok(text.includes('$props.id()'), '$props.id() fehlt');
  assert.ok(!text.includes('Math.random'), 'Math.random macht SSR und Client ungleich');
  assert.match(text, /const FELD_ID = 'dk-abo-adresse-'/, 'Feldkennung fehlt');
});
