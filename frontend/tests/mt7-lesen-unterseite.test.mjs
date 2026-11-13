/**
 * MT-7 — Beiträge und Wiki: Lesen als eigene Unterseite statt Modal.
 *
 * Befund (Manuel, Live-Test 11.11. auf dev.ecg-hn.de): Beitrag bzw.
 * Wiki-Eintrag lesen öffnete ein FENSTER (DkDialog). Keine eigene Adresse,
 * der Zurück-Knopf des Browsers führte nicht zum Artikel, Drucken war nicht
 * vorgesehen.
 *
 * SOLL: eigene Unterseite mit eigener Adresse (Deeplink, Zurück-Knopf),
 * Kopf mit Titel + „‹ zurück“, Lesebreite, druckbar — für Beiträge UND Wiki.
 * Rechte unverändert, es ist NUR Darstellung.
 *
 * Geprüft wird der echte Quelltext (kein Vue-Mount, damit der Test ohne
 * `node_modules` läuft), in fünf Schichten:
 *
 *   T1  Die beiden Leseseiten gibt es und sie sind eigene Seiten
 *       (`pages/BeitragDetail.vue`, `pages/WikiArtikel.vue`).
 *   T2  Der Router kennt sie: `#/beitraege/<id>` → BeitragDetail,
 *       `#/wiki/<id>` → WikiArtikel (Adresse = Deeplink).
 *   T3  Die LISTEN öffnen kein Fenster mehr: kein DkDialog für das Lesen,
 *       kein Detail-Zustand; der Klick wechselt die Route (`navigate`).
 *   T4  Die Leseseiten tragen, was die Karte zusagt: Kopf mit Titel,
 *       „‹ zurück“, Lesebreite (--lesebreite/dk-lesetext) und Druckregeln;
 *       sie holen ihren Inhalt über den Detailaufruf (Rechte unverändert).
 *   T5  Menü und Fenstertitel führen die Unterseiten zum selben Ort
 *       (Seitenleiste bleibt „aktiv“, Tab-Titel nennt die Seite).
 *
 * Läuft im Docker-Build (node --test) und liest nur Dateien innerhalb von
 * `frontend/`.
 */
import assert from 'node:assert/strict'
import { existsSync, readFileSync } from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

const HIER = path.dirname(fileURLToPath(import.meta.url))
const FE = path.join(HIER, '..')

function lies(rel) {
  return readFileSync(path.join(FE, rel), 'utf8')
}
function gibtEs(rel) {
  return existsSync(path.join(FE, rel))
}
/** CSS-Kommentare entfernen (`/* … *​/`), damit Erklärungen nicht mitzählen. */
function ohneCssKommentare(text) {
  return text.replace(/\/\*[\s\S]*?\*\//g, '')
}
function ohneHtmlKommentare(text) {
  return text.replace(/<!--[\s\S]*?-->/g, '')
}

const ROUTER = lies('src/diakonos/router.js')
const MENUE = lies('src/diakonos/menue.js')
const TITEL = lies('src/diakonos/fenstertitel.js')
const BEITRAEGE = ohneHtmlKommentare(lies('src/diakonos/pages/Beitraege.vue'))
const WIKI = ohneHtmlKommentare(lies('src/diakonos/pages/Wiki.vue'))

// ── T1 — die Seiten gibt es ────────────────────────────────────────────────
test('MT-7 · Beitrag und Wiki-Eintrag haben je eine eigene Leseseite', () => {
  assert.ok(gibtEs('src/diakonos/pages/BeitragDetail.vue'), 'pages/BeitragDetail.vue fehlt')
  assert.ok(gibtEs('src/diakonos/pages/WikiArtikel.vue'), 'pages/WikiArtikel.vue fehlt')
})

// ── T2 — eigene Adressen im Router ─────────────────────────────────────────
test('MT-7 · der Router kennt #/beitraege/<id> und #/wiki/<id>', () => {
  assert.match(ROUTER, /BeitragDetail:\s*\(\)\s*=>\s*import\('\.\/pages\/BeitragDetail\.vue'\)/,
    'Router: BeitragDetail zeigt nicht auf pages/BeitragDetail.vue')
  assert.match(ROUTER, /WikiArtikel:\s*\(\)\s*=>\s*import\('\.\/pages\/WikiArtikel\.vue'\)/,
    'Router: WikiArtikel zeigt nicht auf pages/WikiArtikel.vue')
  assert.match(ROUTER, /\{\s*pattern:\s*\/\^#\\\/beitraege\\\/\(\.\+\)\$\/,\s*page:\s*'BeitragDetail',\s*param:\s*'id'\s*\}/,
    'Router: Muster #/beitraege/<id> → BeitragDetail fehlt')
  assert.match(ROUTER, /\{\s*pattern:\s*\/\^#\\\/wiki\\\/\(\.\+\)\$\/,\s*page:\s*'WikiArtikel',\s*param:\s*'id'\s*\}/,
    'Router: Muster #/wiki/<id> → WikiArtikel fehlt')
  // Die Liste bleibt unter ihrer Adresse erreichbar (kein Fangmuster, das sie schluckt).
  assert.match(ROUTER, /'#\/beitraege':\s*'Beitraege'/, 'Router: #/beitraege → Beitraege fehlt')
  assert.match(ROUTER, /'#\/wiki':\s*'Wiki'/, 'Router: #/wiki → Wiki fehlt')
})

// ── T3 — die Listen öffnen kein Fenster mehr ───────────────────────────────
test('MT-7 · Beiträge-Liste liest in der Unterseite, nicht im Fenster', () => {
  assert.ok(!/showPostDetail/.test(BEITRAEGE), 'Beiträge: der Fenster-Zustand showPostDetail steht noch da')
  assert.ok(!/selectedPost/.test(BEITRAEGE), 'Beiträge: selectedPost (Fenster-Inhalt) steht noch da')
  // Kein DkDialog mehr für das LESEN — der Editor darf bleiben.
  const dialoge = [...BEITRAEGE.matchAll(/<DkDialog\b[\s\S]*?<\/DkDialog>/g)].map((m) => m[0])
  assert.ok(dialoge.length >= 1, 'Beiträge: der Editor-Dialog fehlt (Bearbeiten/Anlegen)')
  assert.ok(dialoge.every((d) => /showEditor|editorForm|savePost/.test(d)),
    'Beiträge: ein DkDialog ist übrig, der nicht der Editor ist — Lesen gehört auf die Unterseite')
  // Der Klick wechselt die Route (echter Verlaufseintrag, Zurück-Knopf).
  assert.match(BEITRAEGE, /function oeffnenPost\(/, 'Beiträge: oeffnenPost fehlt')
  assert.match(BEITRAEGE, /navigate\(`#\/beitraege\/\$\{encodeURIComponent\(post\.id\)\}`\)/,
    'Beiträge: der Klick schreibt die Kennung nicht in die Adresse')
  assert.match(BEITRAEGE, /import \{ navigate \} from '\.\.\/router\.js'/,
    'Beiträge: `navigate` wird nicht aus dem Router geholt')
})

test('MT-7 · Wiki-Liste liest in der Unterseite, nicht im Fenster', () => {
  assert.ok(!/showArticleDetail/.test(WIKI), 'Wiki: der Fenster-Zustand showArticleDetail steht noch da')
  assert.ok(!/selectedArticle/.test(WIKI), 'Wiki: selectedArticle (Fenster-Inhalt) steht noch da')
  const dialoge = [...WIKI.matchAll(/<DkDialog\b[\s\S]*?<\/DkDialog>/g)].map((m) => m[0])
  assert.ok(dialoge.length >= 1, 'Wiki: der Editor-Dialog fehlt (Bearbeiten/Anlegen)')
  assert.ok(dialoge.every((d) => /showEditor|editorForm|saveArticle/.test(d)),
    'Wiki: ein DkDialog ist übrig, der nicht der Editor ist — Lesen gehört auf die Unterseite')
  assert.match(WIKI, /navigate\(`#\/wiki\/\$\{encodeURIComponent\(article\.id\)\}`\)/,
    'Wiki: der Klick schreibt die Kennung nicht in die Adresse')
  // P3-1b/UXD-R20 bleibt erfüllt: die Adresse ist teilbar (jetzt als Route).
  assert.ok(!/artikelAdresseSetzen/.test(WIKI),
    'Wiki: der alte replaceState-Weg (artikelAdresseSetzen) steht noch da — jetzt Route')
})

// ── T4 — was die Leseseiten zusagen ────────────────────────────────────────
const LESESEITEN = [
  { datei: 'src/diakonos/pages/BeitragDetail.vue', aufruf: 'beitraege.get_beitrag_detail', rolle: 'BeitragDetail' },
  { datei: 'src/diakonos/pages/WikiArtikel.vue', aufruf: 'wiki.get_wiki_artikel_detail', rolle: 'WikiArtikel' },
]

for (const seite of LESESEITEN) {
  test(`MT-7 · ${seite.datei}: Kopf mit Titel, „‹ zurück“, Lesebreite, druckbar`, () => {
    const text = lies(seite.datei)
    const html = ohneHtmlKommentare(text)
    const css = ohneCssKommentare(text)

    // Inhalt über den Detailaufruf — dieselben Rechte wie bisher (Server prüft).
    assert.ok(text.includes(seite.aufruf), `${seite.datei}: Detailaufruf ${seite.aufruf} fehlt`)
    // Kennung aus der Adresse, seitenbezogen (getRouteParam mit Seitennamen).
    // Beim Durchlaufen der Route steht im Parameter-Objekt nichts — die Seite
    // muss den Pfadteil selbst lesen können (Befund aus der Abnahme 11.11.:
    // „#/beitraege/<id>“ öffnete eine leere Seite).
    assert.ok(new RegExp(`getRouteParam\\('id', '${seite.rolle}'\\)`).test(text),
      `${seite.datei}: liest die Kennung nicht seitenbezogen aus der Adresse`)
    const pfad = seite.rolle === 'BeitragDetail' ? 'beitraege' : 'wiki'
    assert.ok(text.includes('/^#\\/' + pfad + '\\/'),
      `${seite.datei}: kein Rückfall auf den Pfadteil der Adresse (Kennung fehlt beim Durchlaufen)`)

    // Kopf: Titel + Zurück.
    const kopf = /<DkPageHeader\b([\s\S]*?)>/.exec(html)
    assert.ok(kopf && /:title=|\btitle="/.test(kopf[1]), `${seite.datei}: Seitenkopf mit Titel fehlt`)
    assert.match(html, /‹ zurück/, `${seite.datei}: „‹ zurück“ fehlt`)
    assert.match(html, /function zurueck\(/, `${seite.datei}: die Zurück-Funktion fehlt`)
    // MT-7b (Operator-Entscheidung 13.11.): „zurück“ springt über den Router auf
    // die gemerkte Listen-Adresse — KEIN `history.back()` mehr. Der alte Weg
    // (Merkmal im Verlaufs-Eintrag) griff nie: die Leseseite las ihren eigenen
    // Eintrag, das Merkmal lag in dem der Liste.
    assert.match(html, /rueckwegZiel\('#\//,
      `${seite.datei}: „zurück“ holt sein Ziel nicht aus dem Merker (composables/zurueckWege.mjs)`)
    // Review-Punkt 1: „zurück“ ERSETZT den Eintrag der Leseseite — ein
    // `navigate(ziel)` schiebt einen neuen davor (Zurück-Falle: Browser-„Zurück“
    // landete wieder auf der Leseseite).
    assert.match(html, /rueckwegErsetzen\('#\/(?:beitraege|wiki)'\)/,
      `${seite.datei}: „zurück“ ersetzt den Verlaufseintrag nicht (siehe composables/zurueckWege.mjs)`)
    assert.ok(!/navigate\(zurueckZiel\.value\)/.test(html),
      `${seite.datei}: „zurück“ schiebt weiterhin einen Verlaufseintrag (Zurück-Falle)`)
    // Nur im CODE suchen: Kommentare dürfen den alten Weg erwähnen („kein
    // history.back() mehr“), ausführen darf ihn niemand.
    const skriptOhneKommentare = text
      .slice(text.indexOf('<script'))
      .replace(/\/\*[\s\S]*?\*\//g, '')
      .replace(/(^|\s)\/\/[^\n]*/g, '$1')
    assert.ok(!/history\.back\s*\(/.test(skriptOhneKommentare),
      `${seite.datei}: nutzt weiterhin history.back() — die Filter der Liste gingen dabei verloren`)
    assert.ok(!/darfZurueckgehen|merkenVomLink/.test(skriptOhneKommentare),
      `${seite.datei}: der alte Verlaufs-Merkmal-Weg steht noch da (toter Code)`)
    // Der eigene Verlaufs-Eintrag wird NICHT mehr von der Leseseite gesetzt
    // (`replaceState` mit mt7) — das machte das Merkmal immer wahr.
    assert.ok(!/replaceState\([^\n]*mt7/.test(text),
      `${seite.datei}: setzt das Rückweg-Merkmal wieder selbst (Review-Punkt 6)`)
    // Review-Punkt 7: Fokus nach dem Aufbau auf der h1 der Seite.
    assert.match(html, /function fokusAufTitel\(/, `${seite.datei}: setzt den Fokus nach dem Aufbau nicht auf die Überschrift`)
    assert.match(html, /fokusAufTitel\(\)/, `${seite.datei}: „fokusAufTitel“ wird nie aufgerufen`)
    assert.match(html, /<DkPageHeader ref="kopf"/, `${seite.datei}: der Seitenkopf hat keine Referenz für den Fokus`) 

    // Lesebreite aus der einen Quelle.
    assert.match(css, /class="[^"]*\bdk-lesetext\b/, `${seite.datei}: der Inhalt nutzt .dk-lesetext (Lesebreite) nicht`)
    // Breiten nur aus Tokens (--lesebreite/--…); Literale wie `160px` sind tabu.
    assert.ok(!/(?:^|[^-])\bwidth:\s*\d+(?:px|rem|em)\b/.test(css), `${seite.datei}: feste Breite (width: <Zahl>) statt Token`)

    // Druckbar.
    assert.match(css, /@media print\s*\{/, `${seite.datei}: Druckregeln (@media print) fehlen`)

    // Keine festen Farben (ON-0b) — Farbe nur aus Tokens.
    const roh = ohneCssKommentare(text)
    const farben = [...roh.matchAll(/#[0-9a-fA-F]{3,8}\b|\brgba?\(|\bhsla?\(/g)]
      .map((m) => m[0])
      .filter((f) => !['#fff'].includes(f))
    assert.deepEqual(farben, [], `${seite.datei}: feste Farbwerte statt Tokens: ${farben.join(', ')}`)
  })
}

test('MT-7 · Vorlagen nutzen nur Funktionen, die es im Skript gibt (Befund 11.11.)', () => {
  // In der Abnahme rief das Beitrags-Template `formatDate(...)`, die Funktion
  // fehlte im <script setup> — Vue meldete „e.formatDate is not a function“,
  // und die ganze Seite blieb LEER. Das fällt im Quelltext-Test nur auf, wenn
  // man die Namen im Template gegen das Skript hält: genau das hier, für alle
  // Aufrufe der beiden Leseseiten.
  const ERLAUBT = new Set([
    // JS-/Vue-Grundlagen, die kein Skript binden muss
    'true', 'false', 'null', 'undefined', 'String', 'Number', 'Boolean', 'Array', 'Object',
    'Math', 'Date', 'JSON', 'encodeURIComponent', 'decodeURIComponent', 'console',
    'if', 'for', 'while', 'switch', 'catch', 'return', 'typeof', 'await', 'new',
    // Bausteine der Seite (kompilierte Komponenten-Aufrufe)
    'DkPageHeader', 'DkButton', 'DkBadge', 'DkSkelett', 'DkAktionen',
  ])
  for (const { datei } of LESESEITEN) {
    const text = lies(datei)
    const schablone = text.slice(0, text.indexOf('<script'))
    const skript = text.slice(text.indexOf('<script'))
    const gebunden = new Set([
      ...[...skript.matchAll(/\b(?:function|const|let|var)\s+([A-Za-z_$][\w$]*)/g)].map((m) => m[1]),
      ...[...skript.matchAll(/\bimport\s+(?:\{([^}]*)\}|([A-Za-z_$][\w$]*))\s+from/g)].flatMap((m) => {
        if (m[2]) return [m[2]]
        return [...m[1].matchAll(/([A-Za-z_$][\w$]*)(?:\s+as\s+([A-Za-z_$][\w$]*))?/g)]
          .map((n) => n[2] || n[1])
      }),
    ])
    // Ausdrücke in `{{ … }}` und in `:bind="…"`/`@event="…"`: jeder Aufrufname.
    const ausdruecke = [
      ...[...schablone.matchAll(/\{\{([\s\S]*?)\}\}/g)].map((m) => m[1]),
      ...[...schablone.matchAll(/(?::|@|v-if=|v-else-if=|v-for=)[\w:.-]*="([^"]*)"/g)].map((m) => m[1]),
    ]
    const fehlend = new Set()
    for (const a of ausdruecke) {
      for (const m of a.matchAll(/([A-Za-z_$][\w$]*)\s*\(/g)) {
        const name = m[1]
        if (ERLAUBT.has(name) || gebunden.has(name)) continue
        fehlend.add(name)
      }
    }
    assert.deepEqual([...fehlend], [],
      `${datei}: im Template aufgerufen, im Skript aber nicht vorhanden (Seite bliebe leer): ${[...fehlend].join(', ')}`)
  }
})

test('MT-7 · das Zurück-Ziel beider Leseseiten ist die jeweilige Liste', () => {
  // MT-7b: Das Ziel ist keine feste Zeichenkette mehr, sondern kommt aus dem
  // Merker — der Rückfallwert nennt die Liste ohne Filter.
  assert.match(lies('src/diakonos/pages/BeitragDetail.vue'), /rueckwegZiel\('#\/beitraege'\)/,
    'BeitragDetail: zurück zeigt nicht auf #/beitraege')
  assert.match(lies('src/diakonos/pages/WikiArtikel.vue'), /rueckwegZiel\('#\/wiki'\)/,
    'WikiArtikel: zurück zeigt nicht auf #/wiki')
})

// ── T6 — Listen: Rückweg-Merkmal, Bearbeiten aus der Adresse, Tastatur ─────
test('MT-7 · die Listen merken ihre volle Adresse vor dem Öffnen (MT-7b)', () => {
  for (const [datei, ziel] of [
    ['src/diakonos/pages/Beitraege.vue', '#/beitraege'],
    ['src/diakonos/pages/Wiki.vue', '#/wiki'],
  ]) {
    const text = lies(datei)
    assert.match(text, /import \{[^}]*\brueckwegMerken\b[^}]*\} from '\.\.\/composables\/zurueckWege\.mjs'/,
      `${datei}: die Liste benutzt den gemeinsamen Rückweg-Merker nicht`)
    assert.ok(text.includes(`const ZURUECK_ZIEL = '${ziel}'`), `${datei}: ZURUECK_ZIEL fehlt oder zeigt woanders hin`)
    // Review-Punkt 2/4: Beim Öffnen wird die volle Adresse gebildet, in den
    // EIGENEN Verlaufs-Eintrag geschrieben (Browser-„Zurück“ behält die Filter)
    // und mit der Kennung gemerkt (Fokus nach dem Zurück).
    assert.match(text, /const adresse = [A-Za-z_]+\(\)/,
      `${datei}: die Listen-Adresse wird beim Öffnen nicht gebildet`)
    assert.match(text, /adresseImVerlaufSetzen\(adresse\)/,
      `${datei}: die Filter stehen nicht im Verlaufs-Eintrag der Liste (Browser-Zurück verliert sie)`)
    assert.match(text, /rueckwegMerken\(adresse, ZURUECK_ZIEL, [A-Za-z_.]+\)/,
      `${datei}: die gemerkte Adresse wird beim Öffnen nicht mit Filtern und Kennung gebildet`)
    // Review-Punkt 2: Die Filter werden beim Tippen/Filtern in die Adresse
    // geschrieben — dann trägt der Eintrag sie schon vor dem Öffnen.
    assert.match(text, /watch\(\[[^\]]*\], \(\) => \{ adresseImVerlaufSetzen\(/,
      `${datei}: Suche/Filter landen nicht fortlaufend in der Adresse`)
    // Review-Punkt 5 (Gültigkeit des Merkers) prüft der ROUTER — eine Stelle
    // für alle Auslöser, auch für Menüpunkte im Gerüst (`AppSidebar.vue`), die
    // eine Seite nie als Klick sieht. Siehe tests/mt7b-lese-unterseiten.test.mjs.
  }
})

test('MT-7 · „Bearbeiten“ von der Leseseite öffnet den Editor der Liste (Review-Punkt 3)', () => {
  for (const [datei] of [
    ['src/diakonos/pages/Beitraege.vue'],
    ['src/diakonos/pages/Wiki.vue'],
  ]) {
    const text = lies(datei)
    assert.match(text, /async function bearbeitenAusAdresse\(/,
      `${datei}: wertet \`?bearbeiten=<Kennung>\` nicht aus — der Editor öffnet nie`)
    assert.ok(text.includes("teile.get('bearbeiten')"), `${datei}: liest den Parameter „bearbeiten“ nicht`)
    assert.match(text, /teile\.delete\('bearbeiten'\)/,
      `${datei}: nimmt die Kennung nicht wieder aus der Adresse (Neuladen öffnete das Fenster erneut)`) 
    assert.match(text, /bearbeitenAusAdresse\(\)/,
      `${datei}: „bearbeitenAusAdresse“ wird beim Aufbau nicht aufgerufen (Review-Punkt 3)`)
  }
  // Die Leseseiten springen mit genau diesem Parameter hierher.
  assert.match(lies('src/diakonos/pages/BeitragDetail.vue'), /#\/beitraege\?bearbeiten=/,
    'BeitragDetail: „Bearbeiten“ springt nicht auf die Liste mit ?bearbeiten=')
  assert.match(lies('src/diakonos/pages/WikiArtikel.vue'), /#\/wiki\?bearbeiten=/,
    'WikiArtikel: „Bearbeiten“ springt nicht auf die Liste mit ?bearbeiten=')
})

test('MT-7 · Listenkarten sind per Tastatur bedienbar, das Menü bleibt eigenständig', () => {
  for (const [datei, name] of [
    ['src/diakonos/pages/Beitraege.vue', 'bt-post'],
    ['src/diakonos/pages/Wiki.vue', 'wk-article-card'],
  ]) {
    const text = ohneHtmlKommentare(lies(datei))
    const karte = new RegExp(`class="dk-content-card ${name}"([\\s\\S]*?)>\\s*\\n`).exec(text)
    assert.ok(karte, `${datei}: die Listenkarte (${name}) wurde nicht gefunden`)
    assert.match(karte[1], /role="link"/, `${datei}: Karte hat keine Link-Rolle (Review-Punkt 8)`)
    assert.match(karte[1], /tabindex="0"/, `${datei}: Karte ist nicht per Tab erreichbar (Review-Punkt 8)`)
    // Punkt 5: `.self` — Enter/Space im „⋯“-Knopf darf die Seite NICHT öffnen.
    assert.match(karte[1], /@keydown\.enter\.self\.prevent/, `${datei}: Enter auf der Karte greift auch im „⋯“-Menü (Review-Punkt 5)`)
    assert.match(karte[1], /@keydown\.space\.self\.prevent/, `${datei}: Leertaste auf der Karte greift auch im „⋯“-Menü (Review-Punkt 5)`)
  }
})

test('MT-7 · Fokus-Ring für Karten mit Link-Rolle (Review-Punkt 8)', () => {
  const css = ohneCssKommentare(lies('src/diakonos/index.css'))
  assert.match(css, /\.dk-content-card:focus-visible\s*\{[^}]*--focus-ring/,
    'index.css: getastete Karten zeigen keinen Fokus-Ring (WCAG 2.4.7)')
})

test('MT-7 · Fehler der Leseseiten kommen aus dem Katalog (Review-Punkt 4)', () => {
  for (const [datei, aufruf] of [
    ['src/diakonos/pages/BeitragDetail.vue', 'get_beitrag_detail'],
    ['src/diakonos/pages/WikiArtikel.vue', 'get_wiki_artikel_detail'],
  ]) {
    const text = lies(datei)
    assert.match(text, /import \{[^}]*fehlertext[^}]*zustandFuer[^}]*\} from '\.\.\/\.\.\/shared\/fehlertexte\.js'/,
      `${datei}: nutzt den Fehlerkatalog (fehlertext/zustandFuer) nicht`)
    assert.ok(!/Prüfe die Verbindung und versuche es erneut\.'/.test(text),
      `${datei}: zeigt weiter bei JEDEM Fehler „Prüfe die Verbindung …“`)
    assert.match(text, /const erneutSinnvoll = computed\(/, `${datei}: „Erneut versuchen“ hängt nicht am Fehlerzustand`)
    assert.match(text, /v-if="erneutSinnvoll"/, `${datei}: „Erneut versuchen“ erscheint auch bei „nicht gefunden“/„keine Berechtigung“`) 
    assert.ok(text.includes(aufruf), `${datei}: ruft ${aufruf} nicht mehr auf`)
  }
})

test('MT-7 · Druck setzt die Farben der hellen Fassung zurück (Review-Punkt 10)', () => {
  // MT-7b: die vollständige Ableitung prüft `mt7b-lese-unterseiten.test.mjs`
  // (jedes Dunkel-Token gegen den hellen Wert). Hier bleibt der Kern: der
  // Druck-Block existiert und setzt die Namen, die vorher hellblau druckten.
  const tokens = ohneCssKommentare(lies('src/diakonos/tokens.css'))
  const druck = /@media print\s*\{[\s\S]*?\n\}/.exec(tokens.split('PAPIER').pop())
  assert.ok(druck, 'tokens.css: der Druck-Block fehlt')
  for (const name of ['--bg-subtle', '--link', '--link-hover', '--accent', '--accent-d', '--accent-soft', '--primary-hover']) {
    assert.ok(druck[0].includes(`${name}:`), `tokens.css: ${name} wird für Papier nicht auf den hellen Satz zurückgesetzt`)
  }
})

test('MT-7 · „nicht gefunden“ des Servers wird zum Katalogtext (Review-Punkt 4)', async () => {
  const { fehlertext, katalogText } = await import('../src/shared/fehlertexte.js')
  // So antwortet der Server für gelöschte/unbekannte Kennungen (DoesNotExistError).
  for (const text of ['Artikel nicht gefunden.', 'Beitrag nicht gefunden.']) {
    const err = Object.assign(new Error(text), { status: 404, exc_type: 'DoesNotExistError' })
    assert.equal(fehlertext(err, { zustand: 'weg' }), katalogText('weg'),
      `„${text}“ muss durch den Katalogtext ersetzt werden (nennt den nächsten Schritt)`)
  }
  // Ein Fachsatz mit Begründung bleibt stehen (nur die KURZE Formel wird ersetzt).
  const fach = 'Datei nicht gefunden, weil der Ordner umbenannt wurde.'
  assert.equal(fehlertext(Object.assign(new Error(fach), { status: 404 }), { zustand: 'weg' }), fach,
    'ein erklärender Servertext darf nicht ersetzt werden')
  // Außerhalb von „nicht gefunden“ bleibt der Servertext maßgeblich.
  assert.equal(fehlertext(Object.assign(new Error('Beitrag nicht gefunden.'), { status: 417 }), { zustand: 'eingabe' }),
    'Beitrag nicht gefunden.')
})

test('MT-7b · der Rückweg-Merker: gemerkte Filter-Adresse statt Verlauf (Punkt A)', async () => {
  const { bereinigeAdresse, rueckwegErsetzen, rueckwegKennung, rueckwegMerken, rueckwegZiel, rueckwegVergessen } =
    await import('../src/diakonos/composables/zurueckWege.mjs?mt7b')

  // Ohne Merker (geteilter Link, frischer Tab) führt „zurück“ in die Liste
  // ohne Filter — und NIE irgendwoanders hin.
  rueckwegVergessen()
  assert.equal(rueckwegZiel('#/wiki'), '#/wiki')
  assert.equal(rueckwegZiel('#/beitraege'), '#/beitraege')

  // Die Liste merkt ihre volle Adresse MIT Filtern; „zurück“ liefert genau sie.
  assert.equal(rueckwegMerken('#/wiki?kategorie=technik&q=beamer', '#/wiki').adresse,
    '#/wiki?kategorie=technik&q=beamer')
  assert.equal(rueckwegZiel('#/wiki'), '#/wiki?kategorie=technik&q=beamer')

  // MT-7b (Review-Punkt 4): Die Kennung des geöffneten Eintrags steht mit im
  // Merker — die Liste legt den Fokus nach dem Zurück dorthin.
  assert.equal(rueckwegMerken('#/wiki?q=beamer', '#/wiki', 'A-7').kennung, 'A-7',
    'die Kennung des geöffneten Eintrags wird nicht gemerkt')
  assert.equal(rueckwegKennung('#/wiki'), 'A-7')
  rueckwegVergessen()
  assert.equal(rueckwegKennung('#/wiki'), '', 'nach dem Vergessen darf keine Kennung mehr gelten')

  // Ein Merker der ANDEREN Liste gilt dort nicht (jede Liste hat ihr eigenes
  // Ziel; der Merker ist ein einziger Speicherplatz).
  rueckwegMerken('#/wiki?q=beamer', '#/wiki')
  assert.equal(rueckwegZiel('#/beitraege'), '#/beitraege')

  // Nur Listen-Adressen werden angenommen: keine Leseseite, keine fremde
  // Seite, keine Adresse ohne Raute.
  assert.equal(bereinigeAdresse('#/wiki/abc', '#/wiki'), '')
  assert.equal(bereinigeAdresse('#/beitraege?q=x', '#/wiki'), '')
  assert.equal(bereinigeAdresse('wiki?q=x', '#/wiki'), '')
  assert.equal(bereinigeAdresse('#/wiki?q=a?b', '#/wiki'), '')
  assert.equal(bereinigeAdresse('  #/wiki?q=x  ', '#/wiki'), '#/wiki?q=x')
  assert.equal(rueckwegMerken('#/wiki/abc', '#/wiki').adresse, '', 'eine Leseseite darf nie gemerkt werden')

  // MT-7b (Review-Punkt 1): „‹ zurück“ ERSETZT den Verlaufseintrag, es schiebt
  // keinen neuen davor — sonst führte der Zurück-Knopf des Browsers im Kreis.
  const ersetzt = []
  globalThis.window = {
    location: { replace: (ziel) => ersetzt.push(ziel), hash: '#/wiki/A-1' },
    sessionStorage: { getItem: () => null, setItem: () => {}, removeItem: () => {} },
  }
  try {
    assert.equal(rueckwegErsetzen('#/wiki'), '#/wiki?q=beamer')
    assert.deepEqual(ersetzt, ['#/wiki?q=beamer'], '„zurück“ ersetzt den Eintrag nicht')
  } finally {
    delete globalThis.window
  }

  // Leeren: danach wieder die Liste ohne Filter.
  rueckwegVergessen()
  assert.equal(rueckwegZiel('#/wiki'), '#/wiki')
})

// ── T5 — Menü und Fenstertitel ─────────────────────────────────────────────
test('MT-7 · Seitenleiste bleibt „aktiv“, Tab-Titel nennt die Seite', () => {
  assert.match(MENUE, /seiten: \['Beitraege', 'BeitragDetail'\]/,
    'menue.js: die Beitrags-Unterseite gehört nicht zum Menüpunkt „Beiträge“')
  assert.match(MENUE, /seiten: \['Wiki', 'WikiArtikel'\]/,
    'menue.js: die Wiki-Unterseite gehört nicht zum Menüpunkt „Wiki“')
  assert.match(TITEL, /BeitragDetail: 'Beitrag'/, 'fenstertitel.js: Titel für BeitragDetail fehlt')
  assert.match(TITEL, /WikiArtikel: 'Wiki-Artikel'/, 'fenstertitel.js: Titel für WikiArtikel fehlt')
})
