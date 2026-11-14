import assert from 'node:assert/strict'
import vm from 'node:vm'
import { readFileSync, readdirSync } from 'node:fs'
// UI-R10b (Review, Punkt 2): der Router führt keine eigene Fassung der
// Verwaltungsregel mehr — sein Rückfall ist `false` (fail closed). Dieser
// Harness setzt deshalb die ECHTE Regel aus `menue.js` ein.
import { echteVerwaltungsregel } from './helpers/verwaltungsregel.mjs'

/**
 * UX3c — Bereich „Dienste“: Meine Dienste · Dienstpläne · Vorlagen.
 *
 * Prüft den ECHTEN Code (keine Textsuche), soweit es ohne Browser geht:
 *
 *  A  Reiter (menue.js): Start ist „Meine Dienste“; „Dienstpläne“ ist der
 *     Planungs-Reiter und nur für Planer sichtbar (nicht jeder Admin ist
 *     Planer, nicht jeder Planer ist Admin); „Vorlagen“ bleibt Administration.
 *  B  Router (echter Code in einer vm): JEDE Adresse unter `#/planrahmen…`
 *     leitet dauerhaft auf den entsprechenden Reiter weiter — auch die
 *     Detailadressen mit Kennung. Der Bereichs-Einstieg `#/dienste` landet auf
 *     „Meine Dienste“.
 *  C  Oberfläche: Die Reiterzeile steht EINMAL im Rahmen
 *     (pages/dienste/Bereich.vue) und die Seiten zeichnen sie nicht selbst.
 *  D  Fenstertitel und Beschriftungen nennen „Planrahmen“ nicht (Begriff weg).
 *  E  Der lokale Entwurf der Vorlagen-/Plan-Seiten zeigt keine alte Adresse
 *     ohne Weiterleitung (jede `#/planrahmen…`-Adresse ist abgedeckt).
 *
 * Der Browser-belegte Teil (Screenshots, echte Reiterzeile) steht in
 * tools/demo/ux3c-screenshots.py.
 */

const WURZEL = new URL('../src/diakonos/', import.meta.url)
const lies = (p) => readFileSync(new URL(p, WURZEL), 'utf8')

// UI-R10b (Review, Punkt 2): die echte Regel für die Router-vm (fail closed
// im Router ohne `menue.js` — die Harnesse wollen aber Seiten ÖFFNEN).
globalThis.__regel = echteVerwaltungsregel()

/** menue.js ohne Importe in einer vm ausführen (website.mjs wird ersetzt). */
function menueAusfuehren() {
  let source = lies('menue.js')
  source = source.replace(/^import \{ WEBSITE_ROLLEN \}.*$/m,
    "const WEBSITE_ROLLEN = ['System Manager', 'Administrator', 'Website-Moderator']")
  source = source.replace(/^export /gm, '')
  source += `
globalThis.menue = {
  MENUE, FUSS_EINTRAEGE, MENUE_EINTRAEGE, DIENSTE_REITER,
  sichtbareReiter, reiterAusHash, eintragZuSeite,
};`
  const context = { console }
  vm.createContext(context)
  vm.runInContext(source, context)
  return context.menue
}

/** Echten Router in einer vm ausführen (Importe ersetzt, wie in n0). */
function routerAusfuehren(boot) {
  let source = lies('router.js')
  source = source.replace(/^import .*$/gm, '')
    .replace(/import\('([^']*)'\)/g, 'Promise.resolve({default: "$1"})')
    .replace("import * as einrichtungLeitung from './einrichtungLeitung.mjs'",
      "({ EINRICHTUNG_ROUTE: '#/einrichtung', EINRICHTUNG_ZIEL_NACH_ABSCHLUSS: '#/einstellungen', " +
      "einrichtungGesehen: () => false, einrichtungsWeiterleitung: () => null, " +
      "einrichtungSeiteErlaubt: (b) => !b || b.is_admin === true })")
    .replace(/^export \{.*\}$/gm, '').replace(/^export /gm, '')
  source += '\nglobalThis.router = {onBeforeEach, getRouteParams, currentHash, currentPageName, currentComponent, weiterleitungsZiel};'
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
  const context = {
    window, console, setzeFenstertitel() {},
    verwaltungZutreffend: globalThis.__regel,
    ref: (value) => ({ value }),
    shallowRef: (value) => ({ value }),
    computed: (fn) => ({ get value() { return fn() } }),
  }
  vm.createContext(context)
  vm.runInContext(source, context)
  return { window, router: context.router, gehe(hash) { window.location.hash = hash; hashchange() } }
}

const M = menueAusfuehren()
const liste = (a) => Array.from(a)

// ── A: Reiter des Bereichs „Dienste“ ────────────────────────────────────────
{
  const reiter = liste(M.DIENSTE_REITER)
  assert.deepEqual(reiter.map((r) => r.label), ['Meine Dienste', 'Dienstpläne', 'Vorlagen'],
    'Reiterreihenfolge nach Entwurf A2')
  // Start-Reiter ist „Meine Dienste“ — für alle Rollen.
  assert.equal(reiter[0].id, 'meine-dienste')
  assert.equal(reiter[0].rolle, 'alle')
  assert.equal(reiter[0].href, '#/dienste/meine-dienste')

  // „Dienstpläne“ ist Planungsarbeit: Admin ODER Planer-Rolle. Ein reiner
  // Admin ohne Planungsrecht sieht den Reiter NICHT (sonst leerer Reiter),
  // ein Planer ohne Admin sieht ihn (vorher: nur Admins).
  const dienstplaene = reiter.find((r) => r.id === 'dienstplaene')
  assert.ok(dienstplaene, 'Reiter „Dienstpläne“ fehlt')
  assert.equal(dienstplaene.seite, 'DiensteDienstplaene')
  assert.equal(dienstplaene.href, '#/dienste/dienstplaene')

  // „Vorlagen“ bleibt Verwaltungsarbeit (Einstellungs-relevant) — Admin.
  const vorlagen = reiter.find((r) => r.id === 'vorlagen')
  assert.equal(vorlagen.rolle, 'admin')

  // Sichtbarkeit: ohne Recht nur der Start-Reiter; mit Planungsrecht zwei;
  // Admin mit Planungsrecht alle drei.
  const nurMitglied = liste(M.sichtbareReiter(M.DIENSTE_REITER, { istAdmin: false, darfPlanen: false }))
  assert.deepEqual(nurMitglied.map((r) => r.id), ['meine-dienste'],
    'ohne Rechte nur „Meine Dienste“')
  const planer = liste(M.sichtbareReiter(M.DIENSTE_REITER, { istAdmin: false, darfPlanen: true }))
  assert.deepEqual(planer.map((r) => r.id), ['meine-dienste', 'dienstplaene'],
    'Planer ohne Admin sieht „Dienstpläne“, aber keine „Vorlagen“')
  const adminPlaner = liste(M.sichtbareReiter(M.DIENSTE_REITER, { istAdmin: true, darfPlanen: true }))
  assert.deepEqual(adminPlaner.map((r) => r.id), ['meine-dienste', 'dienstplaene', 'vorlagen'],
    'Admin mit Planungsrecht sieht alle drei Reiter')

  // Reiter-Auflösung aus der Adresse (eine Quelle für Oberfläche und Tests).
  assert.equal(M.reiterAusHash(M.DIENSTE_REITER, '#/dienste/meine-dienste'), 'PlanrahmenDienste')
  assert.equal(M.reiterAusHash(M.DIENSTE_REITER, '#/dienste/dienstplaene'), 'DiensteDienstplaene')
  assert.equal(M.reiterAusHash(M.DIENSTE_REITER, '#/dienste/vorlagen'), 'DiensteVorlagen')
  // Unteradressen markieren denselben Reiter (Detailseiten, Editor).
  assert.equal(M.reiterAusHash(M.DIENSTE_REITER, '#/dienste/dienstplaene/plan/abc'),
    'DiensteDienstplaene', 'Plan-Detail markiert „Dienstpläne“')
  assert.equal(M.reiterAusHash(M.DIENSTE_REITER, '#/dienste/vorlagen/chorplan'), 'DiensteVorlagen',
    'Vorlagen-Editor markiert „Vorlagen“')
}

// ── B: Router — „Planrahmen“ verschwindet aus der Adresse ───────────────────
{
  const feste = {
    '#/planrahmen': '#/dienste/dienstplaene',
    '#/planrahmen/meine-dienste': '#/dienste/meine-dienste',
    '#/planrahmen/einrichten': '#/dienste/vorlagen',
    '#/planrahmen/plan': '#/dienste/dienstplaene',
  }
  const h = routerAusfuehren({ is_admin: true, hash: '#/' })
  for (const [alt, neu] of Object.entries(feste)) {
    h.gehe(alt)
    assert.equal(h.window.location.hash, neu, `${alt} → ${neu}`)
  }

  // Detailadressen MIT Kennung: jede endet auf einem Reiter-Adressraum.
  const mitKennung = {
    '#/planrahmen/plan/p-42': '#/dienste/dienstplaene/plan/p-42',
    '#/planrahmen/vorbereiten/p-42': '#/dienste/dienstplaene/vorbereiten/p-42',
    '#/planrahmen/stammdaten/chorplan': '#/dienste/vorlagen/chorplan/stammdaten/-',
    '#/planrahmen/einrichten/chorplan': '#/dienste/vorlagen/chorplan',
  }
  for (const [alt, neu] of Object.entries(mitKennung)) {
    h.gehe(alt)
    assert.equal(h.window.location.hash, neu, `${alt} → ${neu}`)
  }

  // Alte Adressen mit Abfrageteil behalten ihn (Lesezeichen aus der Praxis).
  h.gehe('#/planrahmen/plan/p-42?ansicht=druck')
  assert.equal(h.window.location.hash, '#/dienste/dienstplaene/plan/p-42?ansicht=druck')

  // Die Ziele selbst öffnen die erwartete Seite (kein „nicht gefunden“).
  const ziel = routerAusfuehren({ is_admin: true, hash: '#/dienste/dienstplaene/plan/p-42' })
  assert.equal(ziel.router.currentPageName.value, 'PlanrahmenPlan')
  const stamm = routerAusfuehren({ is_admin: true, hash: '#/dienste/vorlagen/chorplan/stammdaten/-' })
  assert.equal(stamm.router.currentPageName.value, 'PlanrahmenStammdaten')
  const editor = routerAusfuehren({ is_admin: true, hash: '#/dienste/vorlagen/chorplan' })
  assert.equal(editor.router.currentPageName.value, 'PlanrahmenPlantypEditor')

  // Bereichs-Einstieg: „Meine Dienste“ liegen die Planung einen Reiter daneben.
  h.gehe('#/dienste')
  assert.equal(h.window.location.hash, '#/dienste/meine-dienste')

  // Der Bereichs-Einstieg führt NICHT in die Planung (Rollen-Default bleibt
  // die persönliche Sicht — der Planer ist eine Ausnahme, keine Vorgabe).
  const planer = routerAusfuehren({ is_admin: false, mitglied: { status: 'Mitglied' }, hash: '#/' })
  planer.gehe('#/dienste')
  assert.equal(planer.window.location.hash, '#/dienste/meine-dienste')
}

// ── B2: Jede Quelladresse unter `#/planrahmen…` hat eine Weiterleitung ─────
{
  // Der Dokumentkopf von PlantypEditor nannte früher eine Adresse, die es
  // nicht gab. Hier wird JEDE im Quellbaum genannte `#/planrahmen…`-Adresse
  // gegen den echten Router geprüft — so kann keine zweite Wahrheit
  // entstehen.
  const quellen = []
  const sammle = (verzeichnis) => {
    for (const eintrag of readdirSync(verzeichnis, { withFileTypes: true })) {
      const pfad = new URL(`${verzeichnis}${eintrag.name}${eintrag.isDirectory() ? '/' : ''}`, WURZEL)
      if (eintrag.isDirectory()) { if (!['node_modules', 'dist'].includes(eintrag.name)) sammle(pfad.pathname); continue }
      if (!/\.(vue|js|mjs)$/.test(eintrag.name)) continue
      quellen.push(readFileSync(pfad, 'utf8'))
    }
  }
  sammle(WURZEL.pathname)
  const adressen = new Set()
  for (const text of quellen) {
    for (const m of text.matchAll(/#\/planrahmen[^\s'"`)]*/g)) {
      // Satzzeichen am Zitatende gehören nicht zur Adresse (`,` `;` `.` `：`).
      const adresse = m[0].replace(/[,;:.!?]+$/, '')
      if (adresse !== '#/planrahmen' && !adresse.startsWith('#/planrahmen/')) continue
      adressen.add(adresse)
    }
  }
  const h = routerAusfuehren({ is_admin: true, hash: '#/' })
  for (const alt of adressen) {
    h.gehe(alt)
    const jetzt = h.window.location.hash
    assert.ok(!jetzt.startsWith('#/planrahmen'), `${alt} wird nicht weitergeleitet (landet auf ${jetzt})`)
    // Das Ziel muss ein Reiter-Adressraum sein — nicht die Startseite.
    assert.ok(jetzt.startsWith('#/dienste'), `${alt} → ${jetzt} (kein Reiter)`)
  }
  assert.ok(adressen.size >= 8, `Adressen gesammelt (${adressen.size})`)
}

// ── C: Die Reiterzeile steht EINMAL (im Rahmen) ─────────────────────────────
{
  // Der Bereich „Dienste“ hat einen eigenen Rahmen (wie „Personen“): die
  // Reiterzeile wird dort gezeichnet, nicht auf jeder Seite. Das ist die
  // Bedingung dafür, dass die Rechte EINMAL ermittelt werden und beim
  // Wechsel nicht neu aufblitzen.
  const rahmen = lies('pages/dienste/Bereich.vue')
  assert.match(rahmen, /<DiensteReiter/, 'der Rahmen zeichnet die Reiterzeile')
  const seiten = ['MeineDienste', 'Uebersicht', 'Einrichten']
  for (const seite of seiten) {
    const code = lies(`pages/planrahmen/${seite}.vue`)
    assert.doesNotMatch(code, /<DiensteReiter/, `${seite} zeichnet die Reiterzeile nicht selbst`)
  }
  // Die Detailseiten gehören zum selben Bereich (Seitenleiste bleibt „Dienste“).
  const menue = lies('menue.js')
  assert.match(menue, /PlanrahmenPlan/, 'Detailseiten sind dem Menüpunkt „Dienste“ zugeordnet')
}

// ── D: Fenstertitel und Begriffe ohne „Planrahmen“ ──────────────────────────
{
  const titel = lies('fenstertitel.js')
  // Jeder Seitenname des Bereichs hat einen Titel — sonst zeigt der Tab den
  // technischen Namen.
  for (const seite of ['Dienste', 'DiensteDienstplaene', 'DiensteVorlagen',
    'PlanrahmenDienste', 'PlanrahmenPlan', 'PlanrahmenPlantypEditor', 'PlanrahmenStammdaten']) {
    assert.match(titel, new RegExp(`${seite}:`), `Fenstertitel für ${seite} fehlt`)
  }
  // „Planrahmen“ ist kein sichtbarer Begriff mehr (Konzept: Begriff weg).
  // Geprüft werden die SPRACHWÖRTER — Zeichenketten mit Kleinbuchstaben, die
  // nicht aus mehreren Wörtern mit Großbuchstaben bestehen. Seitennamen wie
  // `PlanrahmenDienste` sind interne Kennungen (Binnenmajuskel, keine
  // Beschriftung) und stehen so auch nicht im Glossar.
  const istKennung = (text) => !/[\s]/.test(text) && /^[A-ZÄÖÜ][a-zäöüß]+([A-ZÄÖÜ][a-zäöüß]*)+$/.test(text)
  const sichtbareTexte = []
  for (const datei of ['fenstertitel.js', 'menue.js']) {
    for (const m of lies(datei).matchAll(/'([^'\n]*)'/g)) sichtbareTexte.push([datei, m[1]])
  }
  let geprueft = 0
  for (const [datei, text] of sichtbareTexte) {
    if (istKennung(text)) continue
    if (!/[a-zA-ZäöüßÄÖÜ]/.test(text)) continue
    geprueft += 1
    assert.ok(!/Planrahmen|Plan-Rahmen|planrahmen/.test(text),
      `${datei}: „${text}“ nennt den alten Begriff`)
  }
  assert.ok(geprueft > 20, `Beschriftungen geprüft (${geprueft})`)
}

// ── F: Route-Auflösung — jede Dienste-Adresse landet im Rahmen ─────────────
// Prüfbefund: Die Reiter-Routen zeigten direkt auf die nackten Seiten, der
// Rahmen (pages/dienste/Bereich.vue) wurde nie gezeichnet. Hier läuft der
// ECHTE Router (Seiten-Lader liefern ihren Importpfad) und der ECHTE
// Skriptteil des Rahmens (wählt die innere Seite nach `currentPageName`).
{
  const warte = async () => { for (let i = 0; i < 10; i++) await new Promise((r) => setImmediate(r)) }

  /** Skriptteil von Bereich.vue ausführen; liefert die innere Seite je Seitenname. */
  function rahmenInhalt(seitenname) {
    const sfc = lies('pages/dienste/Bereich.vue')
    let script = sfc.match(/<script setup>([\s\S]*?)<\/script>/)[1]
    script = script.replace(/^import .*$/gm, '')
      .replace(/import\('([^']*)'\)/g, '"$1"')
    script += '\nglobalThis.inhalt = inhalt;'
    const context = {
      window: { location: { hash: '' } },
      computed: (fn) => ({ get value() { return fn() } }),
      ref: (value) => ({ value }),
      onMounted() {},
      defineAsyncComponent: (lader) => lader(),
      DiensteReiter: {}, DIENSTE_REITER: [], reiterAusHash: () => null,
      currentPageName: { value: seitenname },
      usePlanrahmen: () => ({ einrichtenRechte: async () => {} }),
    }
    vm.createContext(context)
    vm.runInContext(script, context)
    return context.inhalt.value
  }

  const RAHMEN = './pages/dienste/Bereich.vue'
  const faelle = [
    // Der Bereichs-Einstieg leitet auf „Meine Dienste“ weiter.
    ['#/dienste', 'PlanrahmenDienste', '../planrahmen/MeineDienste.vue', '#/dienste/meine-dienste'],
    ['#/dienste/meine-dienste', 'PlanrahmenDienste', '../planrahmen/MeineDienste.vue'],
    ['#/dienste/dienstplaene', 'DiensteDienstplaene', '../planrahmen/Uebersicht.vue'],
    ['#/dienste/vorlagen', 'DiensteVorlagen', '../planrahmen/Einrichten.vue'],
  ]
  for (const [hash, seite, innen, ziel = hash] of faelle) {
    const h = routerAusfuehren({ is_admin: true, hash: '#/' })
    h.gehe(hash)
    await warte()
    assert.equal(h.window.location.hash, ziel, `${hash} → ${ziel}`)
    // Weiterleitung: der Browser meldet die neue Adresse als hashchange.
    if (ziel !== hash) { h.gehe(ziel); await warte() }
    assert.equal(h.router.currentPageName.value, seite, `${hash} → Seitenname ${seite}`)
    assert.equal(h.router.currentComponent.value, RAHMEN, `${hash} lädt den Dienste-Rahmen`)
    assert.equal(rahmenInhalt(seite), innen, `${hash}: Rahmen zeigt ${innen}`)
  }
  // Seitenname „Dienste“ (Bereichsname) zeigt ebenfalls „Meine Dienste“.
  assert.equal(rahmenInhalt('Dienste'), '../planrahmen/MeineDienste.vue')
  // Unbekannter Seitenname fällt auf „Meine Dienste“ zurück.
  assert.equal(rahmenInhalt('Unbekannt'), '../planrahmen/MeineDienste.vue')

  // Rechte: Nicht-Admin wird von „Vorlagen“ abgewiesen, „Dienstpläne“ bleibt
  // erreichbar (Planer ohne Admin-Rolle; der Server prüft das Planungsrecht).
  {
    const h = routerAusfuehren({ is_admin: false, hash: '#/' })
    h.gehe('#/dienste/vorlagen')
    await warte()
    assert.equal(h.window.location.hash, '#/', 'Nicht-Admin: Vorlagen gesperrt')
    assert.notEqual(h.router.currentPageName.value, 'DiensteVorlagen')
    h.gehe('#/dienste/dienstplaene')
    await warte()
    assert.equal(h.window.location.hash, '#/dienste/dienstplaene', 'Nicht-Admin: Dienstpläne erreichbar')
    assert.equal(h.router.currentPageName.value, 'DiensteDienstplaene')
    assert.equal(h.router.currentComponent.value, RAHMEN)
  }
}

console.log('UX3c Dienste: Reiter A2, Planer-Sichtbarkeit, Weiterleitungen und Reiterrahmen: bestanden')
