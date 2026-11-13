/**
 * UX3e — Handy: untere Leiste + Menü oben links (Entwurf A8/A9).
 *
 * BEFUND/FREIGABE (Manuel 2026-11-03): Die untere Leiste zeigt
 * **Übersicht · Kalender · Dienste · Beiträge · Wiki** — KEIN „Mehr“. Das
 * Menü-Symbol OBEN LINKS öffnet eine Schublade, gruppiert wie die
 * Seitenleiste (Entwurf A8/A9), mit Profil/Abmelden unten; Esc und Wischen
 * schließen, der Fokus bleibt in der Schublade, alle Ziele sind ≥ 44 px.
 *
 * Geprüft wird der ECHTE Code (keine Textsuche):
 *  1. `handyMenue.mjs` — was steht in der Schublade (Gruppen, Reihenfolge,
 *     Rollen), was ist aktiv, und dass kein Ziel doppelt in Leiste und
 *     Schublade liegt.
 *  2. Die Bauteile: Leiste ohne „Mehr“-Knopf/Blatt, Schublade mit Fokusfalle,
 *     Esc, Zurück-Taste, Wischen, ≥ 44 px und ohne harte Farbwerte — in BEIDEN
 *     Themes (nur Tokens).
 *  3. Der Weg hinein: Menü-Knopf oben links in der Kopfzeile, im DOM nur in
 *     der Mobil-Lage (Desktop behält die Seitenleiste).
 *  4. Erreichbarkeit: alles, was die Seitenleiste anbietet, ist am Handy über
 *     Leiste + Schublade erreichbar (Prinzip N5/DES-R9).
 */
import assert from 'node:assert/strict'
import { existsSync, readFileSync } from 'node:fs'
import test from 'node:test'

import { MENUE, FUSS_EINTRAEGE, sichtbareEintraege } from '../src/diakonos/menue.js'
import { FUSSTAB_TABS, fusstabs } from '../src/diakonos/components/fusstabs.mjs'
import {
  schubladeMenue, sichtbarerFuss, istEintragAktiv, istTabAktiv,
  MENUE_KNOPF_TEXT, SCHUBLADE_KOPF_TEXT, SCHUBLADE_SCHLIESSEN_TEXT,
} from '../src/diakonos/components/handyMenue.mjs'

const WURZEL = new URL('../src/diakonos/', import.meta.url)
const lies = (p) => readFileSync(new URL(p, WURZEL), 'utf8')

const LEISTE = lies('components/AppBottomNav.vue')
const SCHUBLADE = lies('components/AppMenueSchublade.vue')
const TOPBAR = lies('components/AppTopbar.vue')
const APP = lies('App.vue')
const INDEX_CSS = lies('index.css')
const ROUTER = lies('router.js')

/** Seitenname einer Adresse laut Routentabelle (router.js) — der echte Name,
 *  nicht abgeschrieben. */
function seiteZu(adresse) {
  const m = new RegExp(`'${adresse.replace(/[/]/g, '\\/')}':\\s*'([A-Za-z]+)'`).exec(ROUTER)
  assert.ok(m, `Route ${adresse} in router.js gefunden`)
  return m[1]
}

/** Template-/Skript-/Stilteil einer .vue-Datei. */
function teile(quelle) {
  const tpl = quelle.slice(quelle.indexOf('<template>'), quelle.lastIndexOf('</template>'))
  const skript = quelle.slice(quelle.indexOf('<script setup>'), quelle.indexOf('</script>'))
  const stil = quelle.slice(quelle.lastIndexOf('<style'))
  return { tpl, skript, stil }
}
const ohneKommentare = (text) => text.replace(/\/\*[\s\S]*?\*\//g, '').replace(/<!--[\s\S]*?-->/g, '')

const ADMIN = { istAdmin: true, istTester: true, istGast: false }
const MITGLIED = { istAdmin: false, istTester: false, istGast: false }
const GAST = { istAdmin: false, istTester: false, istGast: true }

/** Alle sichtbaren Ziele der Schublade: Gruppen + Fuß („Einstellungen“). */
const alleEintraege = (gruppen, fuss) => [...gruppen.flatMap(g => g.eintraege), ...fuss]
const labels = (gruppen, fuss = []) => alleEintraege(gruppen, fuss).map(e => e.label)
const hrefs = (gruppen, fuss = []) => alleEintraege(gruppen, fuss).map(e => e.href)

// ── 1. Die untere Leiste (Entwurf A8) ──────────────────────────────────────
test('UX3e · die Leiste zeigt genau Übersicht · Kalender · Dienste · Beiträge · Wiki', () => {
  assert.deepEqual(FUSSTAB_TABS.map(t => t.label),
    ['Übersicht', 'Kalender', 'Dienste', 'Beiträge', 'Wiki'],
    'Reihenfolge und Umfang nach Entscheidung Manuel (A8)')
  assert.deepEqual(FUSSTAB_TABS.map(t => t.href),
    ['#/', '#/kalender', '#/dienste', '#/beitraege', '#/wiki'])
  // Prinzip N5: 3–5 Ziele in der Tab-Leiste — „Mehr“ ist KEINS davon.
  assert.ok(FUSSTAB_TABS.length <= 5, 'höchstens fünf Ziele (N5)')
  assert.ok(!FUSSTAB_TABS.some(t => /mehr/i.test(t.label)), 'kein „Mehr“ in der Leiste')
})

test('UX3e · Leiste ohne „Mehr“-Knopf und ohne Blatt', () => {
  const { tpl, skript } = teile(LEISTE)
  assert.match(tpl, /class="dk-bottom-nav"/)
  // Der frühere Knopf hieß „Mehr“ und öffnete ein Blatt (dk-bn-sheet).
  assert.ok(!/>\s*Mehr\s*</.test(ohneKommentare(tpl)), 'kein „Mehr“-Knopf mehr im Markup')
  assert.ok(!/dk-bn-sheet|showMore|toggleMore/.test(ohneKommentare(tpl)),
    'kein Blatt mehr — die Navigation liegt in der Schublade')
  assert.ok(!/showMore|toggleMore|sheetFenster/.test(ohneKommentare(skript)),
    'kein Blatt-Zustand mehr im Skript')
  // Die Tabs kommen aus der EINEN Quelle (fusstabs.mjs).
  assert.match(skript, /import \{ fusstabs \} from '\.\/fusstabs\.mjs'/)
})

test('UX3e · jeder Leisten-Tab ist mindestens 44 px hoch (K4, Mobil)', () => {
  const regel = /\.dk-bn-tab\s*\{([^}]*)\}/.exec(ohneKommentare(teile(LEISTE).stil))
  assert.ok(regel, 'Regel .dk-bn-tab gefunden')
  // UX1c (T6): das Maß darf auch aus dem Token kommen — dann muss das Token
  // selbst die 44 px tragen (`--control-h` am groben Zeiger). Beides ist
  // zulässig; entscheidend ist das Maß, nicht die Schreibweise.
  const zahl = /min-height:\s*(\d+)px/.exec(regel[1])
  const token = /min-height:\s*var\(--control-h(?:-lg)?\)/.test(regel[1])
  assert.ok(zahl || token, 'min-height am Tab')
  if (zahl) assert.ok(Number(zahl[1]) >= 44, `Tab ist nur ${zahl[1]} px hoch`)
  else {
    const tokens = readFileSync(new URL('../src/diakonos/tokens.css', import.meta.url), 'utf8')
    const grob = tokens.slice(tokens.indexOf('@media (pointer: coarse)'))
    assert.match(grob, /--control-h:\s*44px/,
      'min-height kommt aus --control-h — das Token muss am groben Zeiger 44 px sein')
  }
})

// ── 2. Die Schublade (Entwurf A9) ──────────────────────────────────────────
test('UX3e · Schublade ist wie die Seitenleiste gruppiert', () => {
  // WEB-3: „Website“ hängt an einer ROLLENLISTE — ohne sie bleibt der Eintrag
  // fail-closed verborgen. Der Admin eines Betriebs hat sie (Boot-Objekt).
  const gruppen = schubladeMenue({
    ...ADMIN,
    rollen: ['System Manager', 'Administrator'],
  })
  assert.deepEqual(gruppen.map(g => g.gruppe).filter(Boolean), ['Gemeinde', 'Planen', 'Inhalte'],
    'dieselben Gruppen wie MENUE (Entwurf A9)')
  const alle = labels(gruppen)
  // Häufiges oben (N3): Übersicht, dann Personen/Gruppen.
  assert.deepEqual(alle.slice(0, 3), ['Übersicht', 'Personen', 'Gruppen'])
  assert.ok(alle.includes('Lieder') && alle.includes('Website') && alle.includes('Ressourcen'),
    'was vorher nur im „Mehr“-Blatt stand, ist jetzt hier erreichbar')
  // Fuß: wie in der Seitenleiste UNTEN, getrennt von den Gruppen (Entwurf A9).
  assert.deepEqual(sichtbarerFuss({ istAdmin: true }).map(e => e.label), ['Einstellungen'])
  assert.ok(!alle.includes('Einstellungen'), 'Einstellungen steht nicht in einer Gruppe')
  assert.deepEqual(sichtbarerFuss({ istAdmin: false }), [], 'für Mitglieder kein Fuß')
})

test('UX3e · Schublade zeigt die VOLLE Seitenleiste (Entwurf A9), auch die Leisten-Ziele', () => {
  // A9 zeigt Kalender, Dienste, Beiträge, Wiki in der Schublade, obwohl sie
  // auch in der Leiste stehen — die Schublade ist die Seitenleiste am Handy.
  for (const [name, rolle] of [['Admin', ADMIN], ['Mitglied', MITGLIED], ['Gast', GAST]]) {
    const gruppen = schubladeMenue({ ...rolle, rollen: [] })
    const seitenleiste = MENUE
      .map(g => ({ gruppe: g.gruppe, eintraege: sichtbareEintraege(g, { ...rolle, rollen: [] }) }))
      .filter(g => g.eintraege.length > 0)
    assert.deepEqual(gruppen.map(g => [g.gruppe, g.eintraege.map(e => e.href)]),
      seitenleiste.map(g => [g.gruppe, g.eintraege.map(e => e.href)]),
      `${name}: Schublade = Seitenleiste (Gruppen, Reihenfolge, Sichtbarkeit)`)
    const drin = hrefs(gruppen, sichtbarerFuss({ istAdmin: rolle.istAdmin }))
    assert.equal(new Set(drin).size, drin.length, `${name}: kein Ziel zweimal in der Schublade`)
  }
  const mitglied = labels(schubladeMenue({ ...MITGLIED, rollen: [] }))
  for (const ziel of ['Übersicht', 'Personen', 'Gruppen', 'Kalender', 'Dienste', 'Ressourcen', 'Beiträge', 'Wiki', 'Lieder']) {
    assert.ok(mitglied.includes(ziel), `Mitglied findet „${ziel}“ in der Schublade (A9)`)
  }
})

test('UX3e · Schublade hält sich an die Rollen (Gast sieht nur, was der Server erlaubt)', () => {
  const gastGruppen = schubladeMenue({ ...GAST, rollen: [] })
  const gast = labels(gastGruppen, sichtbarerFuss({ istAdmin: false }))
  for (const verboten of ['Personen', 'Gruppen', 'Dienste', 'Ressourcen', 'Website', 'Einstellungen']) {
    assert.ok(!gast.includes(verboten), `Gast sieht „${verboten}“ nicht`)
  }
  // Gast sieht GENAU, was die Seitenleiste ihm zeigt — nicht mehr, nicht weniger.
  assert.deepEqual(gast, MENUE.flatMap(g => sichtbareEintraege(g, { ...GAST, rollen: [] })).map(e => e.label),
    'Gast: dieselbe Liste wie die Seitenleiste')
  // „Einstellungen“ ist Administration — für Mitglieder nicht sichtbar.
  const mitglied = labels(schubladeMenue({ ...MITGLIED, rollen: [], leistenZiele: [] }),
    sichtbarerFuss({ istAdmin: false }))
  assert.ok(!mitglied.includes('Einstellungen'), 'Mitglieder sehen keine Einstellungen')
  assert.deepEqual(FUSS_EINTRAEGE.filter(e => e.rolle === 'admin').map(e => e.label), ['Einstellungen'])
})

test('UX3e · Erreichbarkeit: jede Seitenleisten-Seite ist am Handy erreichbar', () => {
  for (const [name, rolle] of [['Admin', ADMIN], ['Mitglied', MITGLIED], ['Gast', GAST]]) {
    const desktop = [
      ...MENUE.flatMap(g => sichtbareEintraege(g, rolle)).map(e => e.href),
      ...FUSS_EINTRAEGE.filter(e => e.rolle !== 'admin' || rolle.istAdmin).map(e => e.href),
    ].sort()
    const handy = [
      ...fusstabs({ istGast: rolle.istGast }).map(t => t.href),
      ...hrefs(
        schubladeMenue({ ...rolle, rollen: [] }),
        sichtbarerFuss({ istAdmin: rolle.istAdmin }),
      ),
    ]
    assert.deepEqual([...new Set(handy)].sort(), desktop,
      `${name}: am Handy fehlt eine Seite oder es gibt eine zu viel`)
  }
})

test('UX3e · „wo bin ich“: aktiver Eintrag in Leiste und Schublade', () => {
  const personen = MENUE.flatMap(g => g.eintraege).find(e => e.id === 'personen')
  const gruppen = MENUE.flatMap(g => g.eintraege).find(e => e.id === 'gruppen')
  const kalender = FUSSTAB_TABS.find(t => t.href === '#/kalender')
  assert.equal(istEintragAktiv(personen, { seite: 'Personen' }), true)
  assert.equal(istEintragAktiv(personen, { seite: 'Kalender' }), false)
  // Detailseite einer Gruppe markiert weiter „Gruppen“ (wie die Seitenleiste).
  assert.equal(istEintragAktiv(gruppen, { seite: 'GruppeDetail', hash: '#/gruppe/x' }), true)
  assert.equal(istEintragAktiv(gruppen, { seite: 'Personen', hash: '#/personen' }), false)
  // Leiste: der Bereich bleibt markiert, auch auf seinen Unterseiten.
  assert.equal(istTabAktiv(kalender, { seite: 'KalenderImport' }), true)
  assert.equal(istTabAktiv(kalender, { seite: 'Personen' }), false)
  // Kalender-Verwaltung und Moderation gehören zum Kalender — wie in menue.js.
  assert.equal(seiteZu('#/kalender/verwalten'), 'KalenderVerwaltung')
  assert.equal(istTabAktiv(kalender, { seite: seiteZu('#/kalender/verwalten') }), true,
    'Leiste markiert „Kalender“ auf #/kalender/verwalten')
  assert.equal(istTabAktiv(kalender, { seite: 'Moderation' }), true)
  const kalenderMenue = MENUE.flatMap(g => g.eintraege).find(e => e.id === 'kalender')
  assert.deepEqual([...kalender.seiten].sort(), [...kalenderMenue.seiten].sort(),
    'Leiste und Seitenleiste markieren „Kalender“ auf denselben Seiten')
  // Jeder Leisten-Tab markiert dieselben Seiten wie sein Seitenleisten-Eintrag.
  for (const tab of FUSSTAB_TABS) {
    const eintrag = MENUE.flatMap(g => g.eintraege).find(e => e.href === tab.href)
    if (eintrag) assert.deepEqual([...tab.seiten].sort(), [...eintrag.seiten].sort(), `Tab ${tab.label}`)
  }
})

// ── 3. Bedienung der Schublade ─────────────────────────────────────────────
test('UX3e · Esc, Zurück-Taste und Fokusfalle sind verdrahtet', () => {
  const { tpl, skript } = teile(SCHUBLADE)
  assert.match(ohneKommentare(skript), /useDialogFokus\(offenRef,\s*fenster,\s*\(\)\s*=>\s*emit\('schliessen'\)\)/,
    'Esc + Tab-Kreis schließen über useDialogFokus')
  assert.match(ohneKommentare(skript), /useZurueckSchliesst\(offenRef,\s*\(\)\s*=>\s*emit\('schliessen'\)\)/,
    'Zurück-Taste/-Geste schließt (OP-HANDY-7)')
  assert.match(tpl, /role="dialog"/, 'modale Schublade')
  assert.match(tpl, /aria-modal="true"/)
  assert.match(tpl, /ref="fenster"/, 'Fokusziel vorhanden')
  assert.match(tpl, /@keydown="tastenFaenger"/, 'Tastaturführung am Fenster')
})

test('UX3e · Wischen nach links schließt (Entwurf A9)', () => {
  const { tpl, skript } = teile(SCHUBLADE)
  assert.match(tpl, /@touchstart\.passive="wischStart"/, 'Geste wird beobachtet')
  assert.match(tpl, /@touchend\.passive="wischEnde"/)
  const s = ohneKommentare(skript)
  assert.match(s, /const WISCH_MIN_PX = (\d+)/, 'Mindestweg ist benannt')
  const min = Number(/const WISCH_MIN_PX = (\d+)/.exec(s)[1])
  assert.ok(min >= 24 && min <= 64, `Mindestweg ${min} px ist unplausibel`)
  // Nur waagerecht nach links — senkrechtes Wischen bleibt Scrollen.
  assert.match(s, /Math\.abs\(dx\) > Math\.abs\(dy\)/, 'nur waagerechte Gesten zählen')
  assert.match(s, /dx < 0/, 'nur nach links')
})

test('UX3e · jeder Menüpunkt ist mindestens 44 px hoch (K4)', () => {
  const stil = ohneKommentare(teile(SCHUBLADE).stil)
  for (const name of ['.dk-schublade-punkt', '.dk-schublade-profil', '.dk-schublade-marke', '.dk-schublade-schliessen']) {
    const regel = new RegExp(`\\${name}\\s*\\{([^}]*)\\}`).exec(stil)
    assert.ok(regel, `Regel ${name} gefunden`)
    const text = regel[1]
    const minH = /min-height:\s*(\d+)px/.exec(text)
    const h = /(?:^|[;\s])height:\s*(\d+)px/.exec(text)
    const wert = minH ? Number(minH[1]) : (h ? Number(h[1]) : 0)
    assert.ok(wert >= 44, `${name} ist nur ${wert} px groß`)
  }
})

test('UX3e · Schublade nutzt nur Tokens (hell und dunkel aus EINER Quelle)', () => {
  // Farben, Abstände, Radien, Schriftgrößen ausschließlich als var(--…).
  const stil = ohneKommentare(teile(SCHUBLADE).stil)
  const farben = stil.match(/(^|[;{\s])(color|background|background-color|border-color|box-shadow|outline)\s*:\s*([^;]+)/g) || []
  for (const f of farben) {
    assert.ok(!/#[0-9a-fA-F]{3,8}\b/.test(f) && !/\b(rgba?|hsla?)\(/.test(f),
      `harter Farbwert: ${f.trim()}`)
  }
  // Erlaubt sind nur die Tokens sowie hsl-freie Funktionen der Gestaltung
  // (`color-mix` mit Tokens) — ein Rohwert für Abstände wäre ein Bruch (Ä1).
  const abstaende = stil.match(/(^|[;{\s])(gap|padding|margin)\s*:\s*([^;]+)/g) || []
  for (const a of abstaende) {
    assert.ok(!/:\s*-?\d+px/.test(a), `harter Abstand statt Skala: ${a.trim()}`)
  }
})

test('UX3e · Schublade beschriftet ihre Ziele (N8 „beschriften statt nur Symbole“)', () => {
  const { tpl } = teile(SCHUBLADE)
  assert.match(tpl, /\{\{ e\.label \}\}/, 'jeder Menüpunkt trägt seine Beschriftung')
  assert.match(tpl, /<span class="dk-schublade-text">Abmelden<\/span>/, 'Abmelden ist beschriftet')
  // Der Darstellungs-Knopf nennt das ZIEL (wie umschalterText) — Symbol und
  // Text zeigen dasselbe: dunkel → Sonne/„Hell darstellen“, hell → Mond.
  assert.match(tpl, /theme === 'dark' \? 'Hell darstellen' : 'Dunkel darstellen'/)
  assert.match(tpl, /<template v-if="theme === 'dark'">[\s\S]{0,400}circle cx="12" cy="12" r="5"/,
    'im Dunkelmodus zeigt das Symbol die Sonne (Ziel: hell)')
  assert.match(tpl, /<span class="dk-schublade-profil-rolle">Profil<\/span>/, 'Profil ist beschriftet')
  assert.equal(MENUE_KNOPF_TEXT, 'Menü')
  assert.equal(SCHUBLADE_KOPF_TEXT, 'Menü')
  assert.match(SCHUBLADE_SCHLIESSEN_TEXT, /schlie(ß|ss)en/i)
})

// ── 4. Der Weg hinein: Menü-Symbol oben links ──────────────────────────────
test('UX3e · der Menü-Knopf steht links in der Kopfzeile und meldet seinen Zustand', () => {
  const { tpl } = teile(TOPBAR)
  const links = tpl.slice(tpl.indexOf('dk-topbar-left'), tpl.indexOf('dk-topbar-right'))
  // UX1g: Die Kopfzeilen-Knöpfe sind DkButtons (ghost) mit
  // `.dk-topbar-symbol` — die Altklasse `.dk-icon-btn` gibt es nicht mehr.
  assert.match(links, /class="dk-topbar-symbol dk-menue-knopf"/, 'Knopf liegt im linken Bereich')
  assert.match(links, /:aria-label="MENUE_KNOPF_TEXT"/, 'beschriftet für Screenreader')
  assert.match(links, /:aria-expanded="menueOffen \? 'true' : 'false'"/, 'sagt, ob er offen ist')
  assert.match(links, /aria-haspopup="dialog"/, 'kündigt einen Dialog an')
  assert.match(links, /@click="\$emit\('open-menu'\)"/, 'öffnet die Schublade')
  // Der frühere tote Knopf (ohne Funktion, per Inline-Stil versteckt) ist weg.
  assert.ok(!/style="display:none"/.test(ohneKommentare(tpl)),
    'kein totes Inline-verstecktes Menü-Symbol mehr')
})

test('UX3e · Menü-Knopf sichtbar in der Mobil-Lage, versteckt am Desktop', () => {
  const css = ohneKommentare(INDEX_CSS)
  // Nur die Regel am SELEKTORANFANG (`.dk-menue-knopf {`), nicht
  // `.dk-topbar-symbol.dk-menue-knopf` im Template — und mehrzeilig, denn
  // DEV-B6 schreibt eine Deklaration je Zeile.
  const grund = /(?:^|\})\s*\.dk-topbar-symbol\.dk-menue-knopf\s*\{([^}]*?)\}/.exec(css)
  assert.ok(grund, 'Regel .dk-menue-knopf in index.css')
  assert.match(grund[1], /display:\s*none/, 'am Desktop ausgeblendet (dort führt die Seitenleiste)')
  // DEV-B6 (Manuel 09.11.; Nacharbeit 10.11.): DIESELBE Bedingung wie das
  // Handy-Gerüst — jetzt als KLASSE `.dk-app--handy` (Quelle
  // `composables/handyLage.mjs`, identisch mit Token `--layout-mobil`). Es
  // gibt damit keinen eigenen 720-px-/Querformat-Block für den Knopf mehr.
  assert.match(css, /\.dk-app--handy \.dk-topbar-symbol\.dk-menue-knopf\s*\{\s*display:\s*inline-flex/,
    'in der Handy-Lage sichtbar (Klasse aus useHandyLage)')
  // Bei eingeklappter Seitenleiste ist der Einstieg die LEISTE SELBST
  // (`.dk-sb-collapse`) — MT-1 (Manuel 11.11., „nur EIN Seitenmenü“): der
  // frühere zweite Sichtbar-Schalter `.dk-app.is-collapsed` für den
  // Kopfzeilen-Knopf entfällt, sonst standen zwei Einstiege nebeneinander und
  // der Hamburger lag neben der Überschrift.
  assert.ok(!/\.dk-app\.is-collapsed \.dk-menue-knopf/.test(css.replace(/\.dk-app\.is-collapsed \.dk-topbar-symbol\.dk-menue-knopf/g, '')),
    'kein zweiter Sichtbar-Schalter für den Kopfzeilen-Knopf (MT-1)')
  assert.ok(!/is-collapsed[^{}]*\.dk-topbar-symbol\.dk-menue-knopf/.test(css),
    'der Kopfzeilen-Knopf hängt NICHT an der eingeklappten Leiste (MT-1)')
  const seite = lies('components/AppSidebar.vue')
  assert.match(ohneKommentare(seite), /class="dk-sb-collapse"/,
    'die eingeklappte Leiste hat ihren eigenen Ausklapp-Knopf')
  assert.match(ohneKommentare(seite), /:aria-label="collapsed \? 'Menü ausklappen' : 'Menü einklappen'"/,
    'der Ausklapp-Knopf ist beschriftet (N8) und nennt das Ziel')
  assert.match(ohneKommentare(seite), /:aria-expanded="collapsed \? 'false' : 'true'"/,
    'der Ausklapp-Knopf meldet, ob die Leiste offen ist (MT-1b)')
  assert.match(ohneKommentare(seite), /@click="\$emit\('toggle-collapse'\)"/,
    'der Ausklapp-Knopf öffnet die Leiste')
  assert.match(css, /\.dk-sidebar \.dk-sb-top \.dk-sb-collapse\s*\{/,
    'der Ausklapp-Knopf ist als DkButton immer sichtbar; seine Form trägt eine Drei-Klassen-Regel (MT-1b2)')
  // Trefferfläche aus dem Token (UX1c: kein Literal in der Komponente):
  // 40 px am feinen Zeiger, 44 px am Finger (tokens.css).
  // MT-1b: Das eigene Token `--dk-menue-knopf-h` ist entfallen — der Knopf
  // existiert nur noch in der Handy-Lage, also gibt es keinen zweiten Zweig.
  const masse = grund[1]
  assert.match(masse, /width:\s*var\(--control-h\)/, 'Breite aus --control-h')
  assert.match(masse, /height:\s*var\(--control-h\)/, 'Höhe aus --control-h')
  const tokens = readFileSync(new URL('../src/diakonos/tokens.css', import.meta.url), 'utf8')
  assert.match(tokens, /--control-h:\s*40px/, 'Maus: 40 px')
  assert.match(tokens.slice(tokens.indexOf('@media (pointer: coarse)')), /--control-h:\s*44px/,
    'Touch: Trefferfläche 44 px')
})

test('UX3e · App.vue verdrahtet Knopf, Leiste und Schublade', () => {
  const { tpl, skript } = teile(APP)
  const t = ohneKommentare(tpl)
  const s = ohneKommentare(skript)
  assert.match(t, /@open-menu="menueOeffnen"/, 'Kopfzeile öffnet die Schublade')
  assert.match(t, /:menue-offen="menueOffen"/, 'Kopfzeile kennt den Zustand')
  assert.match(t, /<AppMenueSchublade[\s\S]*?:offen="menueOffen"/, 'Schublade hängt am Zustand')
  assert.match(t, /@schliessen="menueOffen = false"/, 'Schließen setzt den Zustand zurück')
  assert.match(t, /<AppBottomNav[^>]*:seite="currentPageName"/,
    'Leiste markiert nach der Route')
  // Die Schublade liegt nur dort im DOM, wo ein Menü-Knopf sie öffnet — in
  // der Handy-Lage (MT-1: NICHT mehr bei eingeklappter Seitenleiste; dort ist
  // der Ausklapp-Knopf der Leiste der einzige Einstieg). Sonst stünde ein
  // zweiter Navigationsweg ohne sichtbaren Einstieg im Tab-Ring.
  assert.match(t, /<AppMenueSchublade[\s\S]{0,200}v-if="!isVollbildMode && istHandyLage"/,
    'Schublade nur in der Handy-Lage (MT-1: ein Seitenmenü)')
  assert.ok(!/<AppMenueSchublade[\s\S]{0,200}sidebarCollapsed/.test(t),
    'die Schublade hängt NICHT mehr an der eingeklappten Leiste (MT-1)')
  // Handy-Lage = DIESELBEN Bedingungen wie das Token `--layout-mobil` in
  // tokens.css (DEV-B6; Nacharbeit 10.11.): grober Zeiger UND 720 px, ODER
  // grober Zeiger und flaches Querformat. Die Zeichenkette steht jetzt EINMAL
  // im Composable (`composables/handyLage.mjs`), App.vue importiert sie.
  assert.match(s, /HANDY_KLASSE, SEITENLEISTE_SCHMAL_ABFRAGE, useHandyLage,/,
    'App.vue nutzt die eine Handy-Lage-Quelle')
  assert.match(s, /const \{ istHandyLage \} = useHandyLage\(\)/, 'Lage aus dem Composable')
  assert.ok(!/const HANDY_LAGE_ABFRAGE/.test(s), 'keine zweite Kopie der Zeichenkette in App.vue')
  // Der Abbau meldet die Breiten-Abfrage ab (die Lage meldet sich selbst ab).
  assert.match(s, /flachAbfrage = window\.matchMedia\(SEITENLEISTE_SCHMAL_ABFRAGE\)/, 'Breiten-Abfrage wird verwendet')
  assert.match(s, /removeEventListener\('change', breiteNachziehen\)/, 'Listener wird beim Abbau entfernt')
  // Der entfallene „Mehr“-Knopf hinterlässt keinen toten Empfänger.
  assert.ok(!/open-admin-dialog/.test(t), 'kein toter Empfänger in der Vorlage')
})

// ── 5. Der Test läuft im Image (Regel 13) ──────────────────────────────────
test('UX3e · die Testdatei steht in der node-Testliste der backend/Dockerfile', (t) => {
  // Im Image liegt nur frontend/ (/build) — die Dockerfile steht dort NICHT.
  // Geprüft wird der Eintrag, wo die Dockerfile erreichbar ist (Worktree);
  // beim Lauf im Image entfällt der Nachweis, statt fälschlich rot zu werden
  // (Muster: fix1).
  const kandidaten = [
    new URL('../../backend/Dockerfile', import.meta.url),
    new URL('../../../backend/Dockerfile', import.meta.url),
  ]
  const treffer = kandidaten.find((u) => existsSync(u))
  if (!treffer) return t.skip('backend/Dockerfile im Abbild nicht vorhanden')
  const dockerfile = readFileSync(treffer, 'utf8')
  // FE-TEST-1: die Muster stehen in frontend/tests/testliste.txt.
  assert.match(dockerfile, /^ARG NODE_TESTLISTE=tests\/testliste\.txt$/m,
    'backend/Dockerfile liest die Muster nicht aus tests/testliste.txt')
  const testliste = readFileSync(new URL('./testliste.txt', import.meta.url), 'utf8')
  assert.match(testliste, /^tests\/ux3e-\*\.test\.mjs$/m, 'Glob tests/ux3e-*.test.mjs eingetragen')
})
