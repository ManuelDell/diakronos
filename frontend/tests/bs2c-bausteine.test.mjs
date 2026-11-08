/**
 * BS-2c — Bausteine „Gruppen-Übersicht", „Gruppen-Steckbrief", „Neuigkeiten",
 * „Veranstaltungs-Anmeldung".
 *
 * Geprüft wird der VERTRAG jedes neuen Bausteins gegen die öffentliche
 * Lese-API aus BS-1b — nicht die Optik (die belegen die Screenshots der
 * Abnahme), sondern die Dinge, die still kaputtgehen können:
 *
 *   B1 `gruppen`          Kacheln/Liste, Filter Gruppentyp, Link-Muster,
 *                         Leertext, KEIN leerer Bildplatz ohne Bild.
 *   B2 `gruppe-steckbrief` EINE Gruppe über die Kennung, Bild, Beschreibung,
 *                         Treffzeit, Treffpunkt, nächste Termine,
 *                         Überschrift-Override, Anzahl, Kontakt-Hinweis.
 *   B3 `neuigkeiten`      Liste/Karten, Anzahl, Kategorie, mit/ohne Bild,
 *                         „Weiterlesen" klappt auf — und der Inhalt geht
 *                         NICHT ungefiltert in `{@html}`.
 *   B4 `anmeldung`        nur Termine mit offener Anmeldung, Knopf zur
 *                         BESTEHENDEN Gast-Anmeldung, neuer Tab optional.
 *
 * Dazu: Primo-Format (Reihenfolge Markup/script/style, ein `$props()`),
 * `--dk-*` nur lesen, `lang="de"`, keine Gemeinde-Inhalte, kein CDN,
 * `VERSION` erhöht und Paketkopie identisch.
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

const NEU = ['anmeldung', 'gruppe-steckbrief', 'gruppen', 'neuigkeiten'];

const lies = (pfad) => readFileSync(pfad, 'utf8');
const quelle = (kennung) => lies(join(QUELLE, kennung, 'component.svelte'));
const felder = (kennung) => JSON.parse(lies(join(QUELLE, kennung, 'fields.json')));
const feldnamen = (kennung) => new Set(felder(kennung).map((f) => f.name));
const stil = (kennung) => quelle(kennung).split('<style>')[1] || '';
const skript = (kennung) => {
  const text = quelle(kennung);
  return text.slice(text.indexOf('<script>') + 8, text.lastIndexOf('</script>'));
};

/** Props aus `let { … } = $props();`. */
function props(kennung) {
  const treffer = skript(kennung).match(/let \{([\s\S]*?)\} = \$props\(\);/);
  assert.ok(treffer, `${kennung}: $props() nicht gefunden`);
  return new Set(
    treffer[1]
      .split('\n')
      .map((zeile) => zeile.match(/^\s*([a-z][a-z0-9_]*)\s*=/))
      .filter(Boolean)
      .map((m) => m[1])
  );
}

// ── 0. Auslieferung ────────────────────────────────────────────────────────

test('BS-2c: die vier neuen Bausteine liegen als Quelle und im Paket', () => {
  for (const kennung of NEU) {
    for (const datei of ['block.json', 'component.svelte', 'fields.json', 'README.md']) {
      assert.equal(
        lies(join(PAKET, kennung, datei)),
        lies(join(QUELLE, kennung, datei)),
        `Paketkopie weicht ab: ${kennung}/${datei} — tools/bausteine_sync.py laufen lassen`
      );
    }
    const block = JSON.parse(lies(join(QUELLE, kennung, 'block.json')));
    assert.equal(block.kennung, kennung);
    assert.ok(block.name.startsWith('Diakronos:'), `${kennung}: Name ohne Präfix`);
  }
});

test('BS-2c: VERSION ist gegenüber BS-2a2 (5) erhöht', () => {
  const version = Number(lies(join(QUELLE, 'VERSION')).trim());
  assert.ok(Number.isInteger(version) && version >= 6, `VERSION ist ${version}`);
  assert.equal(lies(join(PAKET, 'VERSION')).trim(), String(version));
});

test('BS-2c: jeder neue Baustein hält das Primo-Format ein', () => {
  for (const kennung of NEU) {
    const text = quelle(kennung);
    assert.equal((text.match(/<script>/g) || []).length, 1, `${kennung}: genau ein <script>`);
    assert.equal((text.match(/<style>/g) || []).length, 1, `${kennung}: genau ein <style>`);
    assert.ok(text.indexOf('<script>') < text.indexOf('<style>'), `${kennung}: script vor style`);
    assert.ok(text.trimStart().startsWith('<'), `${kennung}: beginnt nicht mit Markup`);
    // Kein onMount: Primo rendert Abschnitte mit svelte/server.
    assert.ok(!/onMount\s*\(/.test(skript(kennung)), `${kennung}: onMount ist bei SSR verboten`);
    assert.ok(/<section[^>]*\blang="de"/.test(text.split('\n')[0]), `${kennung}: lang="de" fehlt`);
    // Jede Feldkennung ist ein Prop (Vorgaben kommen als Props, nicht über content).
    const propnamen = props(kennung);
    for (const name of feldnamen(kennung)) {
      assert.ok(propnamen.has(name), `${kennung}: Feld ${name} ist kein Prop`);
      assert.ok(text.includes(name), `${kennung}: Feld ${name} kommt im Code nicht vor`);
    }
  }
});

test('BS-2c: --dk-* wird nur gelesen, nie deklariert; kein CDN, keine Gemeindenamen', () => {
  for (const kennung of NEU) {
    const text = quelle(kennung);
    assert.equal(text.match(/^\s*--dk-[a-z-]+\s*:/m), null, `${kennung}: deklariert --dk-*`);
    assert.ok(text.includes('var(--dk-'), `${kennung}: liest keine --dk-Tokens`);
    for (const farbe of text.match(/#[0-9a-fA-F]{3,8}\b/g) || []) {
      assert.match(
        text,
        new RegExp(`var\\(--dk-[a-z-]+,\\s*${farbe}`),
        `${kennung}: Farbe ${farbe} nicht als var()-Fallback`
      );
    }
    for (const verboten of ['esm.sh', 'fonts.googleapis', 'cdn.jsdelivr', 'unpkg.com']) {
      assert.ok(!text.includes(verboten), `${kennung}: ${verboten}`);
    }
    for (const verboten of ['Musterhausen', 'ECG']) {
      assert.ok(!text.includes(verboten), `${kennung}: ${verboten}`);
    }
  }
});

test('BS-2c: jeder Baustein ruft die öffentliche Lese-API, nie eine Verwaltungs-API', () => {
  const erwartet = {
    gruppen: '/website/oeffentlich/gruppen',
    'gruppe-steckbrief': '/website/oeffentlich/gruppe',
    neuigkeiten: '/website/oeffentlich/beitraege',
    anmeldung: '/website/oeffentlich/termine'
  };
  for (const [kennung, pfad] of Object.entries(erwartet)) {
    const text = quelle(kennung);
    assert.ok(text.includes(`'${pfad}`), `${kennung}: Pfad ${pfad} fehlt`);
    // Relative Pfade scheitern im srcdoc-iframe des Editors (BS-0 F4).
    assert.ok(text.includes('basis() '), `${kennung}: Adresse nicht über die Basis gebaut`);
    assert.match(text, /basiswert \+ '\/website\/oeffentlich\//,
      `${kennung}: Pfad nicht aus der Diakronos-Adresse gebaut`);
    assert.ok(text.includes('credentials: \'omit\''), `${kennung}: credentials fehlt`);
    assert.ok(text.includes('ZEITLIMIT_MS'), `${kennung}: Zeitlimit fehlt`);
    assert.ok(text.includes('AbortController'), `${kennung}: Abbruch fehlt`);
  }
});

// ── B1 Gruppen-Übersicht ───────────────────────────────────────────────────

test('BS-2c/B1: gruppen — Kacheln oder Liste, Filter, Link-Muster, Leertext', () => {
  const namen = feldnamen('gruppen');
  for (const pflicht of ['ueberschrift', 'basisadresse', 'darstellung', 'gruppentyp',
    'detail_link', 'leertext']) {
    assert.ok(namen.has(pflicht), `gruppen: Feld ${pflicht} fehlt`);
  }
  const text = quelle('gruppen');
  // Darstellung: genau die zwei Werte der Karte.
  assert.ok(text.includes("=== 'liste' ? 'liste' : 'kacheln'"), 'gruppen: Darstellung unklar');
  assert.match(stil('gruppen'), /data-darstellung='liste'/, 'gruppen: kein Listen-Stil');
  assert.match(stil('gruppen'), /data-darstellung='kacheln'/, 'gruppen: kein Kachel-Stil');
  // Filter auf den Gruppentyp.
  assert.ok(text.includes("parameter.set('typ'"), 'gruppen: Filter Gruppentyp fehlt');
  // Link-Muster: {slug} wird ERSETZT — es darf nie unersetzt ins Markup gehen
  // (Svelte wuerde `{slug}` als Ausdruck lesen und den Build brechen).
  assert.match(text, /indexOf\('\{slug\}'\)/, 'gruppen: Platzhalter {slug} wird nicht erkannt');
  assert.match(text, /replace\(\/\\\{slug\\\}\/g, encodeURIComponent\(kennung\)\)/,
    'gruppen: {slug} wird nicht ersetzt');
  const markup = text.slice(0, text.indexOf('<script>'));
  assert.ok(!markup.includes('{slug}'), 'gruppen: roher Platzhalter im Markup');
  assert.match(text, /encodeURIComponent\(kennung\)/, 'gruppen: Slug wird nicht kodiert');
  // Kein javascript:-Ziel aus einem Feldwert.
  assert.match(text, /startsWith\('\/'\) && !ziel\.startsWith\('\/\/'\)/,
    'gruppen: relatives Link-Ziel nicht geprüft');
});

test('BS-2c/B1: gruppen rendert ohne Bild KEIN leeres img', () => {
  // Karte: „Ohne Bild sauberer Text-Block (kein leerer Bildplatz)."
  const text = quelle('gruppen');
  // Das <img> steht in einem {#if …}-Block …
  const abschnitt = text.slice(text.indexOf('<img'), text.indexOf('<img') + 220);
  assert.match(abschnitt, /src=\{gruppe\.bild_url\}/, 'gruppen: img ohne Bildbezug');
  const davor = text.slice(Math.max(0, text.indexOf('<img') - 90), text.indexOf('<img'));
  assert.match(davor, /\{#if gruppe\.bild_url\}/, 'gruppen: img steht nicht unter {#if bild_url}');
  // … und im MARKUP steht kein weiteres Bild (kein Platzhalter-Element).
  const markup = text.slice(0, text.indexOf('<script>'));
  assert.equal((markup.match(/<img/g) || []).length, 1, 'gruppen: mehr als ein <img> im Markup');
  assert.ok(!/placeholder/i.test(markup), 'gruppen: Platzhalter-Element im Markup');
});

// ── B2 Gruppen-Steckbrief ──────────────────────────────────────────────────

test('BS-2c/B2: gruppe-steckbrief — Kennung, Bild, Beschreibung, Treffzeit/-punkt, Termine', () => {
  const namen = feldnamen('gruppe-steckbrief');
  for (const pflicht of ['ueberschrift', 'basisadresse', 'gruppe', 'anzahl_termine',
    'kontakt_hinweis', 'treffzeit', 'treffpunkt', 'naechste_termine']) {
    if (pflicht === 'treffzeit' || pflicht === 'treffpunkt') {
      // Beschriftungen sind eigene Felder (text_treffzeit / text_treffpunkt).
      assert.ok(namen.has(`text_${pflicht}`), `gruppe-steckbrief: Feld text_${pflicht} fehlt`);
      continue;
    }
    if (pflicht === 'naechste_termine') {
      assert.ok(quelle('gruppe-steckbrief').includes('naechste_termine'),
        'gruppe-steckbrief: naechste_termine wird nicht gelesen');
      continue;
    }
    assert.ok(namen.has(pflicht), `gruppe-steckbrief: Feld ${pflicht} fehlt`);
  }
  const text = quelle('gruppe-steckbrief');
  // Die EINE Gruppe kommt über den Slug.
  assert.ok(text.includes("parameter.set('slug'"), 'gruppe-steckbrief: kein slug-Parameter');
  // Anzahl der Termine wirkt (0 blendet die Liste aus).
  assert.match(text, /anzahl >= 1/, 'gruppe-steckbrief: Anzahl 0 blendet nicht aus');
  assert.match(text, /slice\(0, anzahl\)/, 'gruppe-steckbrief: Anzahl begrenzt nicht');
  // Überschrift-Override: leer -> Name der Gruppe.
  assert.match(text, /String\(ueberschrift \|\| ''\)\.trim\(\) !== ''/, 'Override fehlt');
  // Nicht freigegeben -> Leertext, nicht Fehlertext (404 der API).
  assert.match(text, /antwort\.status === 404/, 'gruppe-steckbrief: 404 nicht behandelt');
});

// ── B3 Neuigkeiten ─────────────────────────────────────────────────────────

test('BS-2c/B3: neuigkeiten — Anzahl, Kategorie, Darstellung, mit/ohne Bild', () => {
  const namen = feldnamen('neuigkeiten');
  for (const pflicht of ['ueberschrift', 'basisadresse', 'darstellung', 'anzahl', 'kategorie',
    'bilder_anzeigen', 'weiterlesen', 'text_weiterlesen', 'leertext']) {
    assert.ok(namen.has(pflicht), `neuigkeiten: Feld ${pflicht} fehlt`);
  }
  const text = quelle('neuigkeiten');
  assert.ok(text.includes("parameter.set('limit'"), 'neuigkeiten: Anzahl fehlt in der Abfrage');
  assert.ok(text.includes("parameter.set('kategorie'"), 'neuigkeiten: Kategorie fehlt');
  // Ohne Bild kein <img> (wie B1).
  const davor = text.slice(Math.max(0, text.indexOf('<img') - 90), text.indexOf('<img'));
  assert.match(davor, /\{#if beitrag\.bild_url\}/, 'neuigkeiten: img nicht unter {#if bild_url}');
  assert.match(text, /bilder_anzeigen === true \? bild_adresse/, 'neuigkeiten: Schalter wirkt nicht');
});

test('BS-2c/B3: „Weiterlesen" klappt auf und ist barrierefrei', () => {
  const text = quelle('neuigkeiten');
  assert.match(text, /aria-expanded=/, 'neuigkeiten: aria-expanded fehlt');
  assert.match(text, /aria-controls=/, 'neuigkeiten: aria-controls fehlt');
  assert.match(text, /<button/, 'neuigkeiten: kein <button> (Tastatur!)');
  assert.match(text, /onclick=\{\(\) => umschalten\(/, 'neuigkeiten: kein Umschalter');
  // Der Auszug verschwindet, wenn der Inhalt offen ist.
  assert.match(text, /beitrag\.auszug && !offen\[beitrag\.id\]/, 'neuigkeiten: Auszug bleibt offen');
});

test('BS-2c/B3: der Inhalt geht NICHT ungefiltert in {@html}', () => {
  const text = quelle('neuigkeiten');
  // Es gibt genau EIN {@html} — und es speist sich aus `inhalt_teile`.
  const stellen = text.match(/\{@html [^}]*\}/g) || [];
  assert.equal(stellen.length, 1, `neuigkeiten: ${stellen.length} {@html}-Stellen`);
  assert.equal(stellen[0], '{@html teil.html}', 'neuigkeiten: {@html} mit fremdem Wert');
  assert.ok(!/\{@html beitrag\.inhalt/.test(text), 'neuigkeiten: {@html beitrag.inhalt (ungefiltert)');
  // Zweite Whitelist im Browser: DOMParser + Neubau der Knoten.
  assert.match(text, /new DOMParser\(\)\.parseFromString/, 'neuigkeiten: kein DOMParser');
  assert.match(text, /ERLAUBTE_TAGS/, 'neuigkeiten: keine Element-Allowlist im Client');
  assert.match(text, /ERLAUBTE_SCHEMATA/, 'neuigkeiten: keine Schema-Allowlist im Client');
  assert.match(text, /function escapeHtml\(/, 'neuigkeiten: keine Maskierung');
  assert.match(text, /function escapeAttr\(/, 'neuigkeiten: keine Attribut-Maskierung');
  assert.match(text, /function link_ziel\(/, 'neuigkeiten: href wird nicht geprüft');
  // `innerHTML` kommt nirgends vor (nur der Neubau geht in {@html}).
  assert.ok(!/innerHTML/.test(text), 'neuigkeiten: schreibt per innerHTML');
  // Die Allowlist im Client ist so streng wie der Server.
  for (const tag of ['P', 'BR', 'STRONG', 'EM', 'UL', 'OL', 'LI', 'A', 'H2', 'H3', 'BLOCKQUOTE']) {
    assert.ok(text.includes(`'${tag}'`), `neuigkeiten: Client-Allowlist ohne ${tag}`);
  }
});

// ── B4 Veranstaltungs-Anmeldung ────────────────────────────────────────────

test('BS-2c/B4: anmeldung — Überschrift, Kalender, Knopftext, Leertext', () => {
  const namen = feldnamen('anmeldung');
  for (const pflicht of ['ueberschrift', 'basisadresse', 'kalender', 'knopftext', 'leertext',
    'neuer_tab']) {
    assert.ok(namen.has(pflicht), `anmeldung: Feld ${pflicht} fehlt`);
  }
  const text = quelle('anmeldung');
  assert.ok(text.includes("parameter.set('kalender'"), 'anmeldung: Kalenderfilter fehlt');
  // Nur Termine MIT offener Anmeldung: ohne brauchbare Adresse fliegt die Zeile raus.
  assert.match(text, /if \(adresse === ''\) continue;/, 'anmeldung: Termine ohne Anmeldung bleiben');
  // Anzahl wird erst NACH dem Filter angewandt.
  const block = skript('anmeldung');
  assert.ok(block.indexOf('anmeldung_url') < block.indexOf('hoechstzahl'),
    'anmeldung: Anzahl greift vor dem Filter');
});

test('BS-2c/B4: anmeldung verlinkt die BESTEHENDE Gast-Anmeldung', () => {
  const text = quelle('anmeldung');
  // Die Adresse kommt fertig aus der API (keine eigene Anmeldung im Block).
  assert.match(text, /anmelde_adresse\(eintrag\.anmeldung_url\)/, 'anmeldung: nutzt anmeldung_url nicht');
  // Nur der CODE zaehlt, nicht der erklaerende Kommentar: Doc-Zeilen
  // (//, /*, * ) werden vorher entfernt.
  const code = skript('anmeldung')
    .split('\n')
    .filter((zeile) => !/^\s*(\/\/|\/\*|\*)/.test(zeile))
    .join('\n');
  assert.ok(!/token=/.test(code), 'anmeldung: baut selbst ein Token (eigene Anmeldung!)');
  assert.ok(!/gast\?/.test(code), 'anmeldung: baut die Gast-Seite selbst');
  // Relative Adresse (keine gepflegte öffentliche Adresse) -> Diakronos-Basis davor.
  assert.match(text, /if \(basiswert === '' \|\| !text\.startsWith\('\/'\)\) return '';/,
    'anmeldung: relative Adresse nicht abgesichert');
  // Neuer Tab nur mit noopener: das <a> mit target="_blank" traegt rel immer.
  const blank = text.split('\n').filter((z) => z.includes('target="_blank"'));
  assert.ok(blank.length > 0, 'anmeldung: neuer Tab wird nicht angeboten');
  for (const zeile of blank) {
    assert.match(zeile, /rel="noopener noreferrer"/, 'anmeldung: _blank ohne noopener');
  }
  // Der Schalter wirkt: nur bei `neuer_tab` gibt es ein target.
  assert.match(text, /\{#if neuer_tab\}/, 'anmeldung: Schalter "neuer Tab" fehlt');
  assert.match(text, /rel="noopener noreferrer"/, 'anmeldung: rel fehlt');
  // Touch-Ziel.
  assert.match(stil('anmeldung'), /min-height:\s*44px/, 'anmeldung: Knopf unter 44 px');
});

// ── Querschnitt: Texte sind Felder ─────────────────────────────────────────

test('BS-2c: sichtbare Texte sind Felder, nicht fest verdrahtet', () => {
  const fest = {
    gruppen: ['>Gruppen werden geladen', '>Mehr erfahren<', '>Zurzeit sind keine Gruppen'],
    'gruppe-steckbrief': ['>Treffzeit<', '>Treffpunkt<', '>Nächste Termine<'],
    neuigkeiten: ['>Weiterlesen<', '>Zuklappen<', '>Neuigkeiten werden geladen'],
    anmeldung: ['>Jetzt anmelden<', '>Anmeldung<', '>Termine werden geladen']
  };
  for (const [kennung, muster] of Object.entries(fest)) {
    const text = quelle(kennung);
    for (const teil of muster) {
      assert.ok(!text.includes(teil), `${kennung}: fester Text im Markup: ${teil}`);
    }
  }
});

// ── Abnahmebefund 07.11. (Browser): Prop-Name kollidiert mit den Daten ─────

test('BS-2c/Befund: gruppe-steckbrief rendert die DATEN, nicht den Slug', () => {
  // Im Browser gemessen: `Cannot read properties of undefined (reading
  // 'length')`. Ursache: das Feld heisst `gruppe` (String = Slug), der
  // Zustand der geladenen Gruppe heisst ebenfalls `gruppe`. Im Markup stand
  // `{#if gruppe === null}` — das war immer falsch (der Slug ist nie null),
  // und `gruppe.termine.length` stuerzte ab, sobald Zeilen gezeigt wurden.
  //
  // Der Test haelt die Trennung fest: im Markup wird NUR `befund` gelesen,
  // der Feldname `gruppe` kommt ausschliesslich im Skript vor (Abfrage).
  const text = quelle('gruppe-steckbrief');
  const markup = text.slice(0, text.indexOf('<script>'));
  assert.ok(!/\bgruppe\./.test(markup), 'gruppe-steckbrief: Markup liest `gruppe.…` (Prop statt Daten)');
  assert.ok(!/gruppe\s*===\s*null/.test(markup), 'gruppe-steckbrief: Null-Pruefung am Prop');
  assert.match(markup, /\{:(else )?if befund === null\}/, 'gruppe-steckbrief: Null-Pruefung fehlt an befund');
  assert.match(markup, /befund\.termine\.length/, 'gruppe-steckbrief: Terminliste ohne Längenprüfung');
  // Die Kennung kommt weiter aus dem Feld.
  assert.match(skript('gruppe-steckbrief'), /String\(gruppe \|\| ''\)\.trim\(\)/,
    'gruppe-steckbrief: Feld Kennung wird nicht mehr gelesen');
});

test('BS-2c/Befund: kein Baustein prueft Daten auf einem Prop-Namen', () => {
  // Dieselbe Fehlerklasse bei allen neuen Bausteinen: ein Prop, das wie ein
  // Datenzustand heisst, verdeckt den Zustand (`gruppe`, `zeilen`, `befund`).
  const zustaende = {
    gruppen: ['gruppen', 'ladezustand'],
    'gruppe-steckbrief': ['befund', 'ladezustand'],
    neuigkeiten: ['beitraege', 'offen', 'ladezustand'],
    anmeldung: ['zeilen', 'ladezustand']
  };
  for (const [kennung, namen] of Object.entries(zustaende)) {
    const markup = quelle(kennung).slice(0, quelle(kennung).indexOf('<script>'));
    const propnamen = props(kennung);
    for (const name of namen) {
      assert.ok(!propnamen.has(name),
        `${kennung}: Datenzustand ${name} ist auch ein Prop (Kollision)`);
    }
  }
});

test('BS-2c/Befund: anmeldung haengt das Praefix nicht doppelt an', () => {
  // Im Browser gemessen: der Knopf führte auf
  // `/diakronos/diakronos/diakonos/gast?token=…`. Die Lese-API liefert den
  // Pfad MIT Präfix (`link_anzeige` -> `/diakronos/diakonos/gast`), die
  // Diakronos-Adresse im Feld trägt ihn ebenfalls
  // (`https://gemeinde.example/diakronos`). Einfaches Anhängen ergibt einen
  // toten Link.
  const text = quelle('anmeldung');
  assert.match(text, /basis_pfad/, 'anmeldung: Präfix der Basisadresse wird nicht geprüft');
  assert.match(text, /startsWith\(basis_pfad \+ '\/'\)/,
    'anmeldung: Zielpfad wird nicht gegen den Basis-Präfix geprüft');
  assert.match(text, /pathname\.slice\(basis_pfad\.length\)/,
    'anmeldung: Präfix wird nicht aus dem Zielpfad entfernt');
});
