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
  assert.equal(h.window.location.hash, '#/mitglieder/uebersicht', '#/statistik → Übersicht')
  h.gehe('#/mitglieder/uebersicht')
  assert.equal(h.router.currentPageName.value, 'MitgliederUebersicht', 'Übersicht löst auf')

  const router = lies('router.js')
  // N13b: seit dem Merge von main (N0/N1/N1b) liegen die Weiterleitungen in
  // EINER Tabelle und jede Adresse hat genau ein Ziel — die alte
  // '#/statistik'-Route ist keine eigene Seite mehr.
  assert.ok(
    router.includes("'#/statistik':    '#/mitglieder/uebersicht'"),
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
    ['#/registrierung?token=abc', '#/mitglieder/anfragen?token=abc'],
    ['#/registrierung/', '#/mitglieder/anfragen'],
    ['#/statistik/', '#/mitglieder/uebersicht'],
    ['#/plaene/', '#/planrahmen'],
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
  for (const unbekannt of ['#/mitglieder/foo', '#/einstellungen/xyz', '#/gibtsnicht']) {
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

// ── Mitglieder-Rahmen: echte Aktionen, keine toten Knöpfe ───────────────────
{
  const bereich = lies('pages/mitglieder/Bereich.vue')
  const liste = lies('pages/Mitglieder.vue')
  // H1: Export ist eine echte Funktion, kein Platzhalter-Toast. N1b: Der
  // Rahmen zeigt den Knopf nur im Reiter „Liste“ und ruft den Server-Export
  // der Liste (P1-9b) über ihre Template-Ref auf — der fruehere zweite,
  // clientseitige Export ist entfallen (Befund R-N1-code N1-3/N1-5).
  assert.ok(bereich.includes('function exportieren()'), 'echte Export-Funktion')
  assert.ok(/ref="liste"/.test(bereich), 'Rahmen greift auf die Liste zu')
  assert.ok(liste.includes('defineExpose({ exportCsv'), 'Liste stellt den Export bereit')
  assert.ok(liste.includes('exportiere_mitglieder_csv'), 'Export laeuft serverseitig')
  // N11: Der Reiter „Import“ hat keine eingebettete Liste, deren Export
  // gerufen werden koennte — dort holt der Rahmen den Server-Export selbst
  // (`exportierenDirekt`) und speichert die Datei unveraendert. Einen
  // zweiten, selbstgebauten CSV-Text gibt es weiterhin nicht.
  assert.ok(bereich.includes('function exportierenDirekt()'), 'Export im Import-Reiter (N11)')
  // Kein selbstgebauter CSV-Text: gespeichert wird genau `antwort.csv` vom
  // Server. Geprueft wird das Skript, nicht der erklaerende Kommentar.
  const bereichSkript = bereich.slice(bereich.indexOf('<script setup>'))
  assert.ok(!/split\(';'\)|_csvZelleSicher/.test(bereichSkript), 'kein selbstgebauter CSV-Text im Rahmen')
  assert.ok(!bereich.includes('diakonos:mitglieder-export'), 'keine Ereignisbruecke mehr')
  // N1-4: „Importieren“ entfaellt bis zum Import-Reiter (N11); der Rahmen
  // fuehrt „Mitglied hinzufügen“ echt aus. Geprueft wird der Vorlagenteil,
  // damit der erklaerende Kommentar nicht als Knopf gilt.
  const vorlage = bereich.slice(0, bereich.indexOf('<script setup>'))
  assert.ok(vorlage.includes('Mitglied hinzufügen'), 'Knopf „Mitglied hinzufügen“ vorhanden')
  assert.ok(!vorlage.includes('Importieren'), 'kein Knopf mit falscher Beschriftung (N1-4)')
  // Die Übersicht ist die neue eigene Seite, nicht mehr Statistik.vue.
  assert.ok(bereich.includes("import('./Uebersicht.vue')"), 'Rahmen bindet die neue Übersicht')
  assert.ok(!bereich.includes('Statistik.vue'), 'kein Verweis auf Statistik.vue')
  // N1-6: die Unterzeile nennt keine erfundene Gesamtzahl mehr.
  assert.ok(!bereich.includes('totalCount'), 'kein totalCount mehr in der Liste')
  // Kein Placeholder-Toast mehr in der Liste.
  assert.ok(!liste.includes('Export-Funktion folgt in Phase 3'),
    'Liste ohne Platzhalter-Export')
}

// ── Übersicht: Personenzählung (UXD-R16) und echte Zieladressen ─────────────
{
  const uebersicht = lies('pages/mitglieder/Uebersicht.vue')
  assert.ok(uebersicht.includes('get_statistik'), 'Zahlen kommen aus get_statistik')
  // Jede Kennzahl-Kachel ist klickbar und führt in einen existierenden Reiter.
  for (const ziel of ['#/mitglieder/liste', '#/mitglieder/anfragen', '#/mitglieder/datenschutz']) {
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
    ['#/mitglieder/liste?status=Mitglied', 'MitgliederListe'],
    ['#/mitglieder/liste/', 'MitgliederListe'],
    ['#/mitglieder/uebersicht/', 'MitgliederUebersicht'],
    ['#/mitglieder/anfragen?x=1', 'MitgliederAnfragen'],
    ['#/kalender/', 'Kalender'],
    ['#/lieder/neu', 'LiedNeu'],
    ['#/mitglied/MT-0001', 'MitgliedDetail'],
  ]
  for (const [hash, seite] of faelle) {
    h.gehe(hash)
    assert.equal(h.router.currentPageName.value, seite, `${hash} → ${seite}`)
  }
  // Die Abfrage darf nicht als Seite missverstanden werden.
  h.gehe('#/mitglieder/liste?status=Mitglied')
  assert.equal(h.router.currentPageName.value, 'MitgliederListe', 'Abfrage stoert nicht')
  assert.equal(h.router.currentHash.value, '#/mitglieder/liste?status=Mitglied',
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
{
  const bereich = lies('pages/mitglieder/Bereich.vue')
  const vorlage = bereich.slice(0, bereich.indexOf('<script setup>'))
  const skript = bereich.slice(bereich.indexOf('<script setup>'))
  // Betroffen sind Zugriffe auf Verweise (Reiter/Berechtigung), nicht auf
  // Listenlaengen: `reiter.length` ist ein Array und damit unbedenklich.
  assert.ok(!/v-if="[^"]*(istAdmin|aktiverReiter)\.[a-zA-Z_]+/.test(vorlage),
    'kein Eigenschaftszugriff auf Refs in v-if der Vorlage')
  assert.ok(!/v-if="[^"]*(istAdmin|aktiverReiter)[^"]*&&/.test(vorlage),
    'keine &&-Ausdruecke ueber Refs in v-if')
  assert.ok(vorlage.includes('zeigeExportKnopf'), 'Export-Knopf ueber fertigen Wahrheitswert')
  assert.ok(skript.includes('zeigeExportKnopf = computed'), 'Wahrheitswert im Skript gebildet')
  assert.match(skript, /aktiverReiter\.value\.id === 'liste'/,
    'Reiterpruefung im Skript ueber .value')
  assert.ok(vorlage.includes('v-if="istAdmin"'), '„Mitglied hinzufügen“ ueber einfachen Namen')
}

console.log('N1 Mitglieder mit Reitern und Übersicht: bestanden')
