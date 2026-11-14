import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import vm from 'node:vm'
// UI-R10b (Review, Punkt 2): der Router führt keine eigene Fassung der
// Verwaltungsregel mehr — sein Rückfall ist `false` (fail closed). Dieser
// Harness setzt deshalb die ECHTE Regel aus `menue.js` ein.
import { echteVerwaltungsregel } from './helpers/verwaltungsregel.mjs'

/**
 * UX3j — Personen: Reiter und Auswahlfelder in ALLEN Reitern einheitlich (A3).
 *
 * Karte t_60032412, Wunsch Manuel 08.11.: „Wenn man unter Personen von Liste zu
 * einem anderen Reiter wechselt, wechselt das Auswahl-Design von oberen Feldern
 * zu seitlicher Liste. Das muss konsistent werden. Das gilt für alle
 * Auswahlfelder unter Personen.“
 *
 * Geprüft wird, was die Karte zusagt — an den ECHTEN Modulen (menue.js,
 * Router in der vm) und an den SFCs (Vorlagen ohne Kommentare):
 *
 *  1. EINE Reiterzeile oben in JEDEM Reiter: derselbe Baustein (DkReiter),
 *     dieselbe Position über dem Inhalt, KEINE seitliche Liste mehr; die
 *     Unterbereiche von „Anfragen“ stehen als zweite, kleinere Ebene direkt
 *     darunter (Segmentschalter-Charakter wie die Statusfilter).
 *  2. Adressen bleiben Lesezeichen-fähig: `#/personen/<reiter>[/<unter>]`
 *     (UX3b2) — alte `?bereich=`-Formen leiten um.
 *  3. EIN Filter-Baustein: kein natives `<select>` mehr in den Reitern, alle
 *     Statusfilter sind Segmentschalter (`DkSegment`) mit derselben
 *     Zähler-Darstellung; dasselbe Suchfeld (`.dk-toolbar-search`, Lupe).
 *  4. „Person anlegen“: derselbe Knopf an derselben Stelle in allen Reitern —
 *     genau EIN gefüllter Knopf je Ansicht; in „Links“/„Formulare“ ist deren
 *     eigene Aktion primär und „Person anlegen“ sekundär (eine Regel).
 *  5. Seitenkopf in allen Reitern „Personen“ (kein „MitgliederAnfragen“).
 *  6. Mobil 390: die Reiterzeile scrollt waagerecht, keine Seitenliste.
 *  7. Funktionen/Rechte unverändert (Reiter-Guard wie bisher).
 *
 * Läuft wie die übrigen Frontend-Tests im Docker-Build (node --test) und liest
 * nur Dateien innerhalb von `frontend/`.
 */
const root = new URL('../src/diakonos/', import.meta.url)
const lies = p => readFileSync(new URL(p, root), 'utf8')

// UI-R10b (Review, Punkt 2): die echte Regel für die Router-vm (fail closed
// im Router ohne `menue.js` — die Harnesse wollen aber Seiten ÖFFNEN).
globalThis.__regel = echteVerwaltungsregel()
const menuePfad = fileURLToPath(new URL('menue.js', root))

async function menue() {
  return import(menuePfad + '?t=' + Math.random().toString(36).slice(2))
}

/** Vorlage einer SFC ohne Kommentare (Erklärungen nennen dieselben Wörter). */
function vorlage(quelle) {
  const a = quelle.indexOf('<template>')
  const b = quelle.lastIndexOf('</template>')
  return (a >= 0 && b > a ? quelle.slice(a, b) : '').replace(/<!--[\s\S]*?-->/g, '')
}
function skript(quelle) {
  const a = quelle.indexOf('<script setup>')
  return a < 0 ? '' : quelle.slice(a + '<script setup>'.length, quelle.indexOf('</script>'))
}

// ══════════════════════════════════════════════════════════════════════════
// 1 · EINE Reiterzeile in jedem Reiter, keine Seitenliste
// ══════════════════════════════════════════════════════════════════════════
{
  const personen = lies('pages/Personen.vue')
  const t = vorlage(personen)
  const s = skript(personen)

  // Die Reiterzeile ist EIN Baustein — in jedem Reiter derselbe (der Rahmen
  // zeichnet sie, die Reiter-Seiten bringen keine eigene Leiste mit).
  assert.ok(t.includes('<DkReiter'), 'Reiterzeile als EIN Baustein (DkReiter)')
  assert.ok(!/<DkSegment\s+v-if="zeigeReiter"/.test(t), 'kein Segmentschalter als Hauptreiterzeile')
  assert.ok(!/<DkBereichsliste/.test(t), 'keine seitliche Liste mehr (Punkt 1)')
  assert.ok(!/mb-raster|mb-liste/.test(t), 'kein Seitenlisten-Raster mehr')
  // Die Reiterzeile steht VOR dem Inhalt (oberste Position).
  const positionReiter = t.indexOf('<DkReiter')
  const positionInhalt = t.indexOf('<PersonenListe')
  assert.ok(positionReiter > 0 && positionReiter < positionInhalt,
    'die Reiterzeile steht über dem Inhalt')
  // Zweite, kleinere Ebene direkt darunter — die Unterbereiche von „Anfragen“.
  assert.match(t, /<DkReiter[\s\S]*?klein[\s\S]*?aria-label="Bereiche von Anfragen"/,
    'zweite, kleinere Ebene für die Unterbereiche von „Anfragen“')
  // Kennzahl am Eintrag „Anfragen“ (A3: Zähler-Badge).
  const m = await menue()
  const reiter = m.personenReiter({ istAdmin: true, anfragenZahl: 4 })
  assert.equal(reiter.find(e => e.id === 'anfragen').zahl, 4, 'Zähler-Badge an „Anfragen“')
  assert.ok(t.includes(':options="reiterOptionen"'), 'die Leiste liest die Einträge aus menue.js')
}

// ══════════════════════════════════════════════════════════════════════════
// 2 · Adressen: Reiter und Unterbereich bleiben Lesezeichen (Pfadform)
// ══════════════════════════════════════════════════════════════════════════
{
  const m = await menue()
  for (const [hash, reiter] of [
    ['#/personen/liste', 'liste'],
    ['#/personen/anfragen', 'anfragen'],
    ['#/personen/anfragen/links', 'anfragen'],
    ['#/personen/anfragen/formulare', 'anfragen'],
    ['#/personen/datenschutz', 'datenschutz'],
    ['#/personen/import', 'import'],
  ]) {
    assert.equal(m.personenReiterAusHash(hash, { istAdmin: true }), reiter, `${hash} → Reiter ${reiter}`)
  }
  // Die Unterbereichs-Adresse ist ein PFADTEIL (Vorgabe der Karte).
  for (const u of m.personenAnfragenReiter({ istAdmin: true })) {
    assert.match(u.href, /^#\/personen\/anfragen(\/[a-z]+)?$/, `${u.label}: Adresse der Form #/personen/<reiter>[/<unter>]`)
  }
  // Der Rahmen schreibt den Wechsel in die Adresse (Links, kein Speicher-Zustand).
  const personen = lies('pages/Personen.vue')
  assert.ok(skript(personen).includes('hashchange'), 'Adresse ist die Wahrheit (hashchange)')
  assert.ok(vorlage(personen).includes(':model-value="aktiverReiter"'), 'die Leiste zeigt den Reiter aus der Adresse')
  // Die Anfragen-Seite bekommt den Unterbereich als Eigenschaft.
  assert.ok(vorlage(personen).includes(':unterbereich="aktiverUnterbereich"'),
    'Unterbereich kommt aus der Adresse')

  // Die alte `?bereich=`-Form leitet im Router DAUERHAFT um (Lesezeichen).
  let source = lies('router.js')
  source = source.replace(/^import .*$/gm, '')
    .replace(/import\([^)]*\)/g, 'Promise.resolve({default: "Seite"})')
    .replace("import * as einrichtungLeitung from './einrichtungLeitung.mjs'",
      "({ EINRICHTUNG_ROUTE: '#/einrichtung', EINRICHTUNG_ZIEL_NACH_ABSCHLUSS: '#/einstellungen', " +
      "einrichtungGesehen: () => false, einrichtungsWeiterleitung: () => null, " +
      "einrichtungSeiteErlaubt: (b) => !b || b.is_admin === true })")
    .replace(/^export \{.*\}$/gm, '').replace(/^export /gm, '')
  source += '\nglobalThis.router = {currentHash, currentPageName};'
  let hashchange
  const window = {
    location: { hash: '#/', replace(hash) { this.hash = hash } },
    __DIakonosBOOT: { is_admin: true },
    addEventListener(event, fn) { if (event === 'hashchange') hashchange = fn },
  }
  window.history = { replaceState(_s, _t, hash) { window.location.hash = hash } }
  const context = { window, console, setzeFenstertitel() {},
    verwaltungZutreffend: globalThis.__regel,
    ref: value => ({ value }), shallowRef: value => ({ value }),
    computed: fn => ({ get value() { return fn() } }) }
  vm.createContext(context)
  vm.runInContext(source, context)
  const gehe = (hash) => { window.location.hash = hash; hashchange() }
  for (const [alt, neu] of [
    ['#/personen/anfragen?bereich=links', '#/personen/anfragen/links'],
    ['#/personen/anfragen?bereich=formulare', '#/personen/anfragen/formulare'],
    ['#/personen/anfragen?bereich=anfragen', '#/personen/anfragen'],
  ]) {
    gehe(alt)
    assert.equal(window.location.hash, neu, `${alt} → ${neu} (altes Lesezeichen bleibt gültig)`)
  }
  // Die neuen Pfad-Adressen lösen auf denselben Seitennamen auf (Rechte-Guard
  // unverändert: `MitgliederAnfragen` steht in ADMIN_ONLY_PAGES).
  for (const hash of ['#/personen/anfragen/links', '#/personen/anfragen/formulare']) {
    gehe(hash)
    assert.equal(context.router.currentPageName.value, 'MitgliederAnfragen',
      `${hash} → Seitenname MitgliederAnfragen (Guard greift weiter)`)
  }
}

// ══════════════════════════════════════════════════════════════════════════
// 3 · EIN Filter-Baustein, EIN Suchfeld
// ══════════════════════════════════════════════════════════════════════════
{
  const personen = lies('pages/Personen.vue')
  const datenschutz = lies('pages/mitglieder/Datenschutz.vue')
  const anfragen = lies('pages/Registrierung.vue')
  const importSeite = lies('pages/mitglieder/Import.vue')

  // Kein natives Auswahlfeld mehr in den Personen-Reitern (Punkt 2: natives
  // <select> nur bei > 6 Optionen — die Stand-Auswahl hat 4).
  for (const [name, quelle] of [['Liste', personen], ['Datenschutz', datenschutz],
    ['Anfragen', anfragen], ['Import', importSeite]]) {
    assert.ok(!/<select\b/.test(vorlage(quelle)), `${name}: kein natives <select> mehr`)
  }
  // Alle Statusfilter sind derselbe Baustein (DkSegment) mit Zahlen in der
  // Beschriftung („Wort Zahl“).
  assert.ok(vorlage(personen).includes(':options="filterOptionen"'), 'Liste: Statusfilter = DkSegment')
  assert.ok(vorlage(datenschutz).includes(':options="standOptionen"'), 'Datenschutz: Stand = DkSegment')
  // Dieselbe Zähler-Darstellung: „Alle 43“ / „Mitglied 33“ / „Vorhanden 12“.
  const verwaltung = lies('composables/personenVerwaltung.mjs')
  assert.ok(verwaltung.includes("label: alle === null ? 'Alle' : `Alle ${alle}`"),
    'Liste: Zähler als „Alle 43“')
  assert.ok(skript(datenschutz).includes('label: `Alle ${personen.value.length}`'),
    'Datenschutz: Zähler als „Alle 43“ (dieselbe Schreibweise)')
  assert.ok(skript(datenschutz).includes('label: `${text} ${Number(stats.value?.[wert] || 0)}`'),
    'Datenschutz: Zähler als „Vorhanden 12“ (dieselbe Schreibweise)')
  // UX3j-Nacharbeit (Punkt 1, KERN): Die Anfragen-Seite fährt ihren
  // Statusfilter mit DEMSELBEN Baustein und DERSELBEN Schreibweise — die
  // letzte dunkel gefüllte Chip-Zeile unter „Personen“ ist entfallen.
  assert.ok(skript(anfragen).includes('const statusFilterOptionen = computed'),
    'Anfragen: Statusfilter als Optionen-Liste (DkSegment)')
  assert.ok(skript(anfragen).includes('label: `${s.label} ${zaehle(s.wert)}`'),
    'Anfragen: Zähler als „Offen 3“ (dieselbe Schreibweise)')
  assert.match(vorlage(anfragen).split('Unterbereich 1')[1] || vorlage(anfragen),
    /<DkSegment[\s\S]*?:options="statusFilterOptionen"/, 'Anfragen: Statusfilter = DkSegment')

  // Punkt 1 der Nacharbeit: KEIN DkFilterChips mehr in irgendeinem Reiter
  // unter „Personen“ — und keine Chip-Zeile in den vier Reitern.
  for (const [name, quelle] of [['Liste', personen], ['Anfragen', anfragen],
    ['Datenschutz', datenschutz], ['Import', importSeite]]) {
    assert.ok(!/<DkFilterChips/.test(vorlage(quelle)),
      `${name}: kein DkFilterChips mehr (EIN Filter-Aussehen)`)
  }

  // Dasselbe Suchfeld überall: `.dk-toolbar-search` mit Lupe.
  for (const [name, quelle] of [['Liste', personen], ['Datenschutz', datenschutz]]) {
    const t = vorlage(quelle)
    assert.ok(t.includes('dk-toolbar-search'), `${name}: gemeinsames Suchfeld`)
    assert.ok(t.includes('dk-search-icon'), `${name}: Lupe im Suchfeld`)
  }
}

// ══════════════════════════════════════════════════════════════════════════
// 4 · „Person anlegen": derselbe Knopf, genau EIN gefüllter je Ansicht
// ══════════════════════════════════════════════════════════════════════════
{
  const personen = lies('pages/Personen.vue')
  const t = vorlage(personen)
  const s = skript(personen)

  // Der Knopf steht im EINEN Seitenkopf und wird in JEDEM Reiter gezeigt.
  const anlegen = [...t.matchAll(/<DkButton\b[^>]*>[\s\S]{0,600}?Person anlegen/gs)]
  assert.equal(anlegen.length, 1, 'genau EIN „Person anlegen“ im Kopf')
  assert.match(anlegen[0][0], /:variant="anlegenIstHauptaktion \? 'primary' : 'secondary'"/,
    'Betonung folgt der Regel (anlegenIstHauptaktion)')
  // UI-R10: „Person anlegen“ hängt am PERSONEN-Recht (Mitgliederverwaltung
  // ODER Administrator), nicht mehr am Kern-Admin — seit R-11a ist die
  // Mitgliederverwaltung kein Administrator, darf aber Personen anlegen.
  assert.match(s, /const zeigeAnlegenKnopf = computed\(\(\) => darfVerwalten\.value === true\)/,
    '„Person anlegen“ erscheint in ALLEN Reitern (Punkt 3)')
  // Die Regel: eigene Hauptaktion des Unterbereichs → deren Knopf primär.
  assert.match(s, /const UNTERBEREICH_HAUPTAKTIONEN = \{ links: 'link', formulare: 'formular' \}/,
    'die Regel steht an EINER Stelle')
  assert.match(s, /const anlegenIstHauptaktion = computed\(\(\) => !unterbereichHauptaktion\.value\)/,
    'ohne eigene Hauptaktion ist „Person anlegen“ primär')
  assert.ok(t.includes('unterbereichHauptaktion === \'link\''), '„Neuer Link“ im selben Kopf')
  assert.ok(t.includes('unterbereichHauptaktion === \'formular\''), '„Neues Formular“ im selben Kopf')
  // Genau EIN gefüllter Knopf: die drei Bedingungen schließen sich aus
  // (anlegenIstHauptaktion ist genau dann true, wenn keine Unteraktion läuft).
  const primaer = [...t.matchAll(/variant="primary"/g)].length
  assert.equal(primaer, 2, 'zwei sich ausschließende Primärknöpfe (Person anlegen · Unteraktion)')
  // Die Anfragen-Seite bringt ihren eigenen Anlege-Knopf NICHT mehr mit —
  // der eine Knopf steht im Kopf des Rahmens.
  const reg = lies('pages/Registrierung.vue')
  // Nur im eigenen Kopf (Standalone-Adresse) — im eingebetteten Betrieb ist er
  // ausgeblendet, der eine Knopf steht im Kopf des Rahmens.
  assert.equal((vorlage(reg).match(/<IconPlus \/> Neuer Link/g) || []).length, 1,
    'genau ein „Neuer Link“ — im Kopf bei v-if="!embedded"')
  assert.equal((vorlage(reg).match(/<IconPlus \/> Neues Formular/g) || []).length, 1,
    'genau ein „Neues Formular“ — im Kopf bei v-if="!embedded"')
  assert.match(vorlage(reg), /<DkPageHeader v-if="!embedded"[\s\S]*?Neuer Link/,
    'die beiden Knöpfe stehen im Kopf, der nur ohne Rahmen erscheint')
  assert.ok(skript(reg).includes('defineExpose({ linkOeffnen, formularOeffnen })'),
    'der Kopf ruft die vorhandenen Dialoge der Seite')
}

// ══════════════════════════════════════════════════════════════════════════
// 5 · Seitenkopf immer „Personen"
// ══════════════════════════════════════════════════════════════════════════
{
  const personen = lies('pages/Personen.vue')
  const t = vorlage(personen)
  assert.equal((t.match(/<DkPageHeader\b/g) || []).length, 1, 'genau EIN Seitenkopf')
  assert.match(t, /<DkPageHeader title="Personen"/, 'der Kopf heißt in jedem Reiter „Personen“')
  for (const verboten of ['MitgliederAnfragen', 'Mitglieder', 'Anfragen</h1>']) {
    assert.ok(!t.includes(verboten), `kein „${verboten}“ im Seitenkopf`)
  }
  // Die eingebetteten Reiter-Seiten bringen keinen eigenen Kopf mit.
  for (const [name, quelle] of [['Anfragen', lies('pages/Registrierung.vue')],
    ['Datenschutz', lies('pages/mitglieder/Datenschutz.vue')],
    ['Import', lies('pages/mitglieder/Import.vue')]]) {
    assert.ok(!/<h1\b/.test(vorlage(quelle)) || /v-if="!embedded"/.test(vorlage(quelle)),
      `${name}: kein zweiter Seitentitel im eingebetteten Betrieb`)
  }
  // Die Kopfleiste (Brotkrumen) nennt in allen vier Reitern „Personen“ —
  // nicht den rohen Komponentennamen („MitgliederAnfragen“).
  const topbar = lies('components/AppTopbar.vue')
  for (const seite of ['MitgliederAnfragen', 'MitgliederDatenschutz', 'MitgliederImport']) {
    assert.match(topbar, new RegExp(`${seite}:\\s*\\['Personen'\\]`),
      `${seite}: Brotkrume „Personen“`)
  }
  // Der Fenstertitel der Reiter bleibt „Personen“ (Router/`fenstertitel.js`).
  const router = lies('router.js')
  assert.ok(router.includes("'#/personen/anfragen':   'MitgliederAnfragen'"),
    'Seitenname bleibt (Anker für Guard und Fenstertitel)')
}

// ══════════════════════════════════════════════════════════════════════════
// 6 · Mobil 390: Reiterzeile scrollt waagerecht, keine Seitenliste
// ══════════════════════════════════════════════════════════════════════════
{
  const ui = lies('components/ui/DkReiter.vue')
  assert.ok(/overflow-x: auto/.test(ui), 'die Reiterzeile scrollt waagerecht')
  assert.ok(/white-space: nowrap/.test(ui), 'Einträge brechen nicht um')
  assert.ok(!/grid-template-columns/.test(ui), 'keine Spalten-Aufteilung (keine Seitenliste)')
  assert.ok(ui.includes('scrollbar-width: none'), 'keine sichtbare Scrollleiste (A9/A10-Muster)')
  // Der Rahmen stellt auf schmalen Anzeigen NICHT auf eine Liste um.
  const personen = lies('pages/Personen.vue')
  assert.ok(!/mb-raster|mb-liste/.test(personen), 'kein Listen-Raster im Rahmen')
}

// ══════════════════════════════════════════════════════════════════════════
// 7 · Funktionen und Rechte unverändert
// ══════════════════════════════════════════════════════════════════════════
{
  const m = await menue()
  // Nur der Mitgliederadministrator sieht mehr als die Liste.
  assert.deepEqual(m.personenReiter({ istAdmin: false }).map(e => e.id), ['liste'],
    'ohne Recht nur die Liste (wie heute)')
  assert.equal(m.personenAnfragenReiter({ istAdmin: false }).length, 0,
    'ohne Recht keine Anfragen-Unterbereiche')
  // Verwaltungsfunktionen hängen an der EINEN Verwaltungsregel — seit UI-R10
  // am PERSONEN-Flag (`istMitgliederverwaltung`, Administrator ODER
  // Mitgliederadministrator), nicht mehr am Kern-Admin.
  const personen = lies('pages/Personen.vue')
  assert.ok(skript(personen).includes('verwaltungSichtbar(darfVerwalten.value)'),
    'Verwaltungsfunktionen nur mit Personen-Verwaltungsrecht')
  // Der Reiter-Guard im Router schützt dieselben Seiten wie bisher — jetzt in
  // der Liste des Personenbereichs (`PERSONEN_VERWALTUNG_PAGES`).
  const router = lies('router.js')
  const guard = router.slice(router.indexOf('const PERSONEN_VERWALTUNG_PAGES'))
  for (const seite of ['MitgliederAnfragen', 'MitgliederDatenschutz', 'MitgliederImport']) {
    assert.ok(guard.includes(`'${seite}'`), `${seite} bleibt geschützt`)
  }
}

// ══════════════════════════════════════════════════════════════════════════
// 8 · Nacharbeit: Werkzeuge auf Höhe der Reiterzeile, zweite Ebene = Segmentschalter
// ══════════════════════════════════════════════════════════════════════════
{
  const personen = lies('pages/Personen.vue')
  const t = vorlage(personen)
  const s = skript(personen)

  // Punkt 4: „Filter“ + „Person anlegen“ stehen IN derselben Zeile wie die
  // Reiterzeile (A3) — nicht in einem Aktionsblock des Seitenkopfs darüber.
  assert.match(t, /<div class="p3-reiterzeile">\s*<DkReiter/,
    'die Reiterzeile öffnet die gemeinsame Kopfzeile')
  assert.match(t, /class="p3-reiterzeile"[\s\S]*?class="p3-aktionen"[\s\S]*?<\/div>\s*<\/div>/,
    'die Aktionen stehen in derselben Kopfzeile')
  assert.ok(!/<DkPageHeader[\s\S]*?<template #actions>/.test(t),
    'kein eigener Aktionsblock im Seitenkopf mehr')
  assert.equal((t.match(/<DkPageHeader\b/g) || []).length, 1, 'weiterhin genau EIN Seitenkopf')
  // Am Handy rutschen die Werkzeuge unter die Reiter (keine Seitenliste).
  assert.match(personen, /@media \(max-width: 720px\)[\s\S]*?\.p3-aktionen \{ width: 100%/,
    'Mobil: Werkzeuge nehmen die zweite Zeile, keine Seitenliste')

  // Punkt 4, zweite Hälfte: „Filter“ nur, wo er wirkt.
  assert.match(s, /const zeigeFilter = computed/, 'der Filterknopf ist an den Reiter gebunden')
  assert.match(s, /if \(aktiverReiter\.value === 'anfragen'\) return aktiverUnterbereich\.value === 'anfragen'/,
    'kein Filterknopf bei „Links“/„Formulare“ (dort filtert nichts)')
  assert.ok(t.includes('v-if="zeigeFilter"'), 'der Filterknopf wird bedingt gezeichnet')

  // Punkt 3: Die zweite Ebene ist ein kleiner Segmentschalter (Optik von
  // DkSegment), bleibt aber eine Zeile aus Links mit eigener Adresse.
  assert.match(t, /<DkReiter[\s\S]*?klein[\s\S]*?segment[\s\S]*?aria-label="Bereiche von Anfragen"/,
    'zweite Ebene: klein + Segmentschalter-Optik')
  const ui = lies('components/ui/DkReiter.vue')
  assert.ok(/\.dk-ui-reiter\.is-segment/.test(ui), 'DkReiter kennt die Segment-Optik')
  assert.ok(/background: var\(--surface-2\)/.test(ui), 'Segmentfläche wie DkSegment (Token)')

  // Punkt 5: kein Zähler „0“.
  assert.match(ui, /return Number\.isFinite\(n\) && n > 0 \? n : null/,
    'die Zahl 0 wird nicht gezeichnet')

  // Punkt 6: Inhalt bündig mit der Reiterzeile.
  assert.match(t, /class="p3-inhalt"/, 'die Inhalte tragen die bündige Klasse')
  assert.match(personen, /\.p3-inhalt \{ margin-top: 0; \}/, 'kein Einzug über dem Inhalt')
}

// ══════════════════════════════════════════════════════════════════════════
// 9 · Nacharbeit: Router prüft Muster gegen den Hash OHNE Abfrageteil
// ══════════════════════════════════════════════════════════════════════════
{
  const router = lies('router.js')
  const fn = router.slice(router.indexOf('function weiterleitungsZiel('))
  const koerper = fn.slice(0, fn.indexOf('\n}'))
  // Feste Weiterleitungen zuerst, dann die Muster.
  assert.ok(koerper.indexOf('const fest = WEITERLEITUNGEN[pfad]') < koerper.indexOf('for (const regel of MUSTER_WEITERLEITUNGEN)'),
    'feste Weiterleitungen haben Vorrang vor den Mustern')
  assert.match(koerper, /zerlegeHash\(String\(vollerHash\)\)/, 'der Abfrageteil wird abgetrennt')
  assert.match(koerper, /regel\.mitAbfrage \? suchTeil : pfadOhneAbfrage/,
    'Muster sehen den Abfrageteil nur mit Flag')

  // Verhalten: Die Weiterleitungstabelle ist nicht exportiert — geprüft wird
  // deshalb an der QUELLE, dass die alten `?bereich=`-Formen weiter umleiten
  // und Muster ohne Abfragebedarf unverändert bleiben. Ein echtes Verhalten
  // prüft zusätzlich der Runner unten (menue.js), nicht der Router.
  assert.match(router, /pattern: \/\^#\\\/personen\\\/anfragen\\\?bereich=\(\?:anfragen\)\?\$\//,
    'alte ?bereich=-Form bleibt umgeleitet')
  assert.match(router, /pattern: \/\^#\\\/liedergruppen\\\/\(\.\+\)\$\//,
    'Muster ohne Abfragebedarf bleibt unverändert')
  // Die Abfrage-Weitergabe an das Ziel kennt die Anfragen-Sonderform — ein
  // `?bereich=` bleibt nicht am Ziel hängen.
  assert.match(router, /!\/\^#\\\/personen\\\/anfragen\\\?bereich=\/\.test\(vollerHash\)/,
    '?bereich= wird nicht als Abfrage ans Ziel gehängt')
}

console.log('UX3j Personen-Reiter und Auswahlfelder: bestanden')
