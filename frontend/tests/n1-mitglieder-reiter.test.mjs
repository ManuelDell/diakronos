import assert from 'node:assert/strict'
import vm from 'node:vm'
import { readFileSync } from 'node:fs'

/**
 * N1 — Mitglieder mit Reitern und Übersicht.
 *
 * Läuft den ECHTEN Router in einer vm aus (keine Textsuche) und prüft:
 *  - die alte Statistik-Seite ist entfernt, #/statistik leitet in die Übersicht,
 *  - Weiterleitungen greifen auch mit Abfrageteil und Schluss-Schrägstrich
 *    (Befund R-N0-code 3),
 *  - unbekannte Adressen landen auf „Seite nicht gefunden“ statt still auf dem
 *    Dashboard (OP-UI-6),
 *  - der Mitglieder-Rahmen bindet die Kacheln an echte Ziele und den Export an
 *    eine echte Funktion (Befunde R-N0-code 1/2),
 *  - die Übersicht zählt Personen, nicht Protokollzeilen (UXD-R16) und ihre
 *    Zieladressen gibt es wirklich.
 */
const root = new URL('../src/diakonos/', import.meta.url)
const lies = p => readFileSync(new URL(p, root), 'utf8')

function routerAusfuehren(boot) {
  let source = lies('router.js')
  source = source.replace(/^import .*$/gm, '').replace(/import\([^)]*\)/g, 'Promise.resolve({default: "Seite"})')
  // ON-3b: die Leitungsregel (einrichtungLeitung.mjs) wird durch
  // feste Rückgaben ersetzt — dieser Lauf prueft den Router selbst.
  .replace("import * as einrichtungLeitung from './einrichtungLeitung.mjs'",
      "({ EINRICHTUNG_ROUTE: '#/einrichtung', EINRICHTUNG_ZIEL_NACH_ABSCHLUSS: '#/einstellungen', " +
      "einrichtungGesehen: () => false, einrichtungsWeiterleitung: () => null, " +
      "einrichtungSeiteErlaubt: (b) => !b || b.is_admin === true })")
    .replace(/^export \{.*\}$/gm, '').replace(/^export /gm, '')
  source += '\nglobalThis.router = {onBeforeEach, getRouteParams, currentHash, currentPageName};'
  let hashchange
  const window = {
    location: {
      hash: boot.hash || '#/',
      replace(hash) { this.hash = hash },
    },
    __DIakonosBOOT: boot,
    addEventListener(event, fn) { if (event === 'hashchange') hashchange = fn },
  }
  window.history = { replaceState(_s, _t, hash) { window.location.hash = hash } }
  const context = { window, console, setzeFenstertitel() {},
    ref: value => ({ value }),
    shallowRef: value => ({ value }),
    computed: fn => ({ get value() { return fn() } }) }
  vm.createContext(context)
  vm.runInContext(source, context)
  return { window, router: context.router, gehe(hash) { window.location.hash = hash; hashchange() } }
}

// ── Statistik-Seite entfernt, Adresse leitet in die Übersicht ───────────────
{
  const h = routerAusfuehren({ is_admin: true, hash: '#/' })
  h.gehe('#/statistik')
  assert.equal(h.window.location.hash, '#/personen/uebersicht', '#/statistik → Übersicht')
  h.gehe('#/personen/uebersicht')
  assert.equal(h.router.currentPageName.value, 'MitgliederUebersicht', 'Übersicht löst auf')

  const router = lies('router.js')
  // N13b: seit dem Merge von main (N0/N1/N1b) liegen die Weiterleitungen in
  // EINER Tabelle und jede Adresse hat genau ein Ziel — die alte
  // '#/statistik'-Route ist keine eigene Seite mehr.
  assert.ok(
    router.includes("'#/statistik':    '#/personen/uebersicht'"),
    '#/statistik ist eine Weiterleitung (keine eigene Seite)',
  )
  assert.ok(!/'#\/statistik'\s*:\s*'[A-Za-z]/.test(router), 'Statistik ist keine eigene Route mehr')
  let statistikDateiFehlt = false
  try { lies('pages/Statistik.vue') } catch { statistikDateiFehlt = true }
  assert.ok(statistikDateiFehlt, 'pages/Statistik.vue ist entfernt')
}

// ── Weiterleitungen mit Abfrageteil und Schluss-Schrägstrich ────────────────
{
  const h = routerAusfuehren({ is_admin: true, hash: '#/' })
  const faelle = [
    ['#/registrierung?token=abc', '#/personen/anfragen?token=abc'],
    ['#/registrierung/', '#/personen/anfragen'],
    ['#/statistik/', '#/personen/uebersicht'],
    ['#/plaene/', '#/dienste/dienstplaene'],
  ]
  for (const [alt, neu] of faelle) {
    h.window.location.hash = alt
    h.gehe(alt)
    assert.equal(h.window.location.hash, neu, `${alt} → ${neu}`)
  }
}

// ── Unbekannte Adresse → „Seite nicht gefunden“ (OP-UI-6) ───────────────────
{
  const h = routerAusfuehren({ is_admin: true, hash: '#/' })
  for (const unbekannt of ['#/personen/foo', '#/einstellungen/xyz', '#/gibtsnicht']) {
    h.window.location.hash = unbekannt
    h.gehe(unbekannt)
    assert.equal(h.router.currentPageName.value, 'NichtGefunden', `${unbekannt} → NichtGefunden`)
  }
  // Die Wurzel bleibt Startseite.
  h.gehe('#/')
  assert.equal(h.router.currentPageName.value, 'Home', '#/ bleibt Home')
  // Die Seite existiert und nennt einen Rückweg.
  const nichtGefunden = lies('pages/NichtGefunden.vue')
  assert.ok(nichtGefunden.includes('Seite nicht gefunden'), 'Text „Seite nicht gefunden“')
  assert.ok(nichtGefunden.includes("'#/'"), 'Rückweg zum Dashboard')
}

// ── Personen-Rahmen: echte Aktionen, keine toten Knöpfe ─────────────────────
// UX3j (Entwurf A3): Es gibt EINEN Rahmen — `pages/Personen.vue`. Die Datei
// `pages/mitglieder/Bereich.vue` ist nur noch ihr Adress-Ziel (die alten
// Reiter-Seitennamen, damit Rechte-Guard und Fenstertitel unverändert gelten);
// die Prüfungen lesen deshalb den einen Rahmen.
{
  const bereich = lies('pages/Personen.vue')
  const liste = lies('pages/Mitglieder.vue')
  // H1: Export ist eine echte Funktion, kein Platzhalter-Toast. N1b: Der
  // Rahmen zeigt den Knopf nur im Reiter „Liste“ und ruft den Server-Export
  // der Liste (P1-9b) über ihre Template-Ref auf — der fruehere zweite,
  // clientseitige Export ist entfallen (Befund R-N1-code N1-3/N1-5).
  assert.ok(bereich.includes('async function exportieren()'), 'echte Export-Funktion')
  assert.ok(bereich.includes('exportiere_mitglieder_csv'), 'Export laeuft serverseitig')
  assert.ok(liste.includes('exportCsv'), 'Liste stellt den Export bereit')
  // Kein selbstgebauter CSV-Text: gespeichert wird genau `antwort.csv` vom
  // Server. Geprueft wird das Skript, nicht der erklaerende Kommentar.
  const bereichSkript = bereich.slice(bereich.indexOf('<script setup>'))
  assert.ok(!/split\(';'\)|_csvZelleSicher/.test(bereichSkript), 'kein selbstgebauter CSV-Text im Rahmen')
  assert.ok(!bereich.includes('diakonos:mitglieder-export'), 'keine Ereignisbruecke mehr')
  // N1-4: Kein Knopf mit falscher Beschriftung. Geprueft wird der
  // Vorlagenteil, damit der erklaerende Kommentar nicht als Knopf gilt.
  const vorlage = bereich.slice(0, bereich.indexOf('<script setup>'))
  assert.ok(vorlage.includes('Person anlegen'), 'Knopf „Person anlegen“ vorhanden')
  assert.ok(!vorlage.includes('Importieren'), 'kein Knopf mit falscher Beschriftung (N1-4)')
  // Die Übersicht ist eine eigene Seite (Kachel-Ziele), keine Statistik.vue.
  assert.ok(!bereich.includes('Statistik.vue'), 'kein Verweis auf Statistik.vue')
  // N1-6: die Unterzeile nennt keine erfundene Gesamtzahl mehr.
  assert.ok(!bereich.includes('totalCount'), 'kein totalCount in der Liste')
  // Kein Placeholder-Toast mehr in der Liste.
  assert.ok(!liste.includes('Export-Funktion folgt in Phase 3'),
    'Liste ohne Platzhalter-Export')
}

// ── Übersicht: Personenzählung (UXD-R16) und echte Zieladressen ─────────────
{
  const uebersicht = lies('pages/mitglieder/Uebersicht.vue')
  assert.ok(uebersicht.includes('get_statistik'), 'Zahlen kommen aus get_statistik')
  // Jede Kennzahl-Kachel ist klickbar und führt in einen existierenden Reiter.
  // UX3a: Die Übersicht verlinkt über die HREF-Konstanten; der Test prüft die
  // ZIELE, nicht die Schreibweise der Verwendung im Quelltext.
  for (const ziel of ['#/personen/liste', '#/personen/anfragen', '#/personen/datenschutz']) {
    assert.ok(uebersicht.includes(ziel), `Kachelziel ${ziel}`)
  }
  // Die Zählung „Datenschutz offen“ kommt aus dsgvo.fehlt (Personen).
  assert.ok(uebersicht.includes('dsgvo.fehlt') || uebersicht.includes('d.fehlt'),
    'Datenschutz-Kachel nutzt die Personenzahl')
}

// ── N1b (H1): Adressen mit Abfrageteil und Schluss-Schrägstrich ─────────────
{
  const h = routerAusfuehren({ is_admin: true, hash: '#/' })
  const faelle = [
    // UX3b: der Reiter „Liste“ ist die zusammengelegte Personen-Seite.
    ['#/personen/liste?status=Mitglied', 'Personen'],
    ['#/personen/liste/', 'Personen'],
    ['#/personen/uebersicht/', 'MitgliederUebersicht'],
    ['#/personen/anfragen?x=1', 'MitgliederAnfragen'],
    ['#/kalender/', 'Kalender'],
    ['#/lieder/neu', 'LiedNeu'],
    ['#/mitglied/MT-0001', 'MitgliedDetail'],
  ]
  for (const [hash, seite] of faelle) {
    h.gehe(hash)
    assert.equal(h.router.currentPageName.value, seite, `${hash} → ${seite}`)
  }
  // Die Abfrage darf nicht als Seite missverstanden werden.
  h.gehe('#/personen/liste?status=Mitglied')
  assert.equal(h.router.currentPageName.value, 'Personen', 'Abfrage stoert nicht')
  assert.equal(h.router.currentHash.value, '#/personen/liste?status=Mitglied',
    'der volle Hash bleibt fuer die Seite erhalten')
  // Auch mit Abfrageteil unbekannter Pfad bleibt „Seite nicht gefunden“.
  h.gehe('#/gibtsnicht?x=1')
  assert.equal(h.router.currentPageName.value, 'NichtGefunden', 'unbekannt + Abfrage')
}

// ── N1b (H2): die Liste übernimmt ?status als Startfilter ──────────────────
{
  const liste = lies('pages/Mitglieder.vue')
  assert.ok(liste.includes('_statusAusAdresse'), 'Filter wird aus der Adresse gelesen')
  assert.ok(liste.includes("URLSearchParams(hash.slice(frage + 1)).get('status')"),
    'der Parameter heisst status')
  assert.ok(liste.includes('MT_STATUS.includes(wert)'), 'nur echte Status werden uebernommen')
  assert.ok(liste.includes('statusFilter.value = _statusAusAdresse()'),
    'Startfilter wird gesetzt — auch auf „Alle“ (Kachel „Personen“, H1 R-N2-code)')
}

// ── N1b: keine Ref-Ausdruecke in der Vorlage des Rahmens ───────────────────
// In der Vorlage packt der Compiler Verweise aus `script setup` in AUSDRUECKEN
// nicht aus. `v-if="istAdmin && aktiverReiter.id === 'liste'"` war deshalb
// immer falsch (der Kopf zeigte weder Export noch „Mitglied hinzufügen“),
// waehrend `aktiverReiter.value.id` im Skript richtig ist. Die Vorlage darf
// solche Ausdruecke nicht mehr enthalten.
// UX3j: Es gibt EINEN Personen-Rahmen (`pages/Personen.vue`).
{
  const bereich = lies('pages/Personen.vue')
  const vorlage = bereich.slice(0, bereich.indexOf('<script setup>'))
  const skript = bereich.slice(bereich.indexOf('<script setup>'))
  // Betroffen sind Zugriffe auf Verweise (Reiter/Berechtigung), nicht auf
  // Listenlaengen: `reiterOptionen.length` ist ein Array und unbedenklich.
  assert.ok(!/v-if="[^"]*(istAdmin|aktiverReiter)\.[a-zA-Z_]+/.test(vorlage),
    'kein Eigenschaftszugriff auf Refs in v-if der Vorlage')
  assert.ok(!/v-if="[^"]*(istAdmin|aktiverReiter)[^"]*&&/.test(vorlage),
    'keine &&-Ausdruecke ueber Refs in v-if')
  // UX3j: Welche Knöpfe die Kopfzeile zeigt, entscheiden fertige
  // Wahrheitswerte aus dem Skript (Reiter + Unterbereich + Rechte).
  for (const wert of ['zeigeAnlegenKnopf', 'anlegenIstHauptaktion', 'unterbereichHauptaktion']) {
    assert.ok(vorlage.includes(wert), `Kopfzeile über fertigen Wahrheitswert „${wert}“`)
    assert.ok(skript.includes(`${wert} = computed`), `„${wert}“ im Skript gebildet`)
  }
  // Der Reiter wird im SKRIPT aus der Adresse bestimmt (dort sind Refs
  // ausgepackt) — menue.js ist die eine Quelle der Einträge.
  assert.match(skript, /personenReiterAusHash\(/, 'Reiter aus der Adresse (menue.js)')
  assert.ok(vorlage.includes(':options="reiterOptionen"'), 'Reiterzeile aus menue.js-Einträgen')
  assert.ok(!/class="mb-raster"/.test(vorlage), 'keine seitliche Bereichsliste mehr (A3)')
}

console.log('N1 Mitglieder mit Reitern und Übersicht: bestanden')
