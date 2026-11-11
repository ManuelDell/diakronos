/**
 * MT-1 — Nur EIN Seitenmenü (Manuel 11.11., Live-Test dev.ecg-hn.de).
 *
 * BEFUND: Ein-/Ausklappen der Seitenleiste funktioniert. Im EINGEKLAPPTEN
 * Zustand erschien zusätzlich ein Hamburger in der Kopfzeile, direkt neben der
 * Überschrift; ein Klick öffnete ein ZWEITES, identisches Seitenpanel.
 *
 * SOLL (Karte): Am Laptop/Desktop gibt es genau EINEN Einstieg in die
 * Navigation — die (eingeklappte) Seitenleiste selbst bzw. ihr
 * Ausklapp-Knopf. Der Kopfzeilen-Hamburger entfällt AUSSERHALB der Handy-Lage
 * (`.dk-app--handy`). Am Handy bleibt das Menü wie heute (Leiste unten +
 * Schublade über den Kopfzeilen-Knopf).
 *
 * Geprüft wird der ECHTE Quelltext (kein Vue-Mount nötig, damit der Test ohne
 * Build läuft) — in drei Schichten:
 *  1. CSS: genau EINE Sichtbar-Regel für den Kopfzeilen-Knopf, und zwar an
 *     `.dk-app--handy`. Kein `is-collapsed`-Schalter.
 *  2. Bauteile: die eingeklappte Leiste trägt ihren eigenen Ausklapp-Knopf
 *     (beschriftet, 40 px / 44 px, öffnet die Leiste); die Schublade liegt nur
 *     in der Handy-Lage im DOM (kein Navigationsweg ohne sichtbaren Einstieg).
 *  3. Alle Seiten der App: der Hamburger kommt ausschließlich aus der EINEN
 *     Kopfzeile (AppTopbar) — keine Seite baut ein zweites Seitenpanel oder
 *     einen eigenen Menü-Knopf.
 */
import assert from 'node:assert/strict'
import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join, resolve } from 'node:path'
import test from 'node:test'

const SRC = resolve('src/diakonos')

/** Datei lesen, CSS-Kommentare entfernt (`/* … *\/`). */
function lies(rel) {
  return readFileSync(resolve(SRC, rel), 'utf8')
}
function ohneCssKommentare(text) {
  return text.replace(/\/\*[\s\S]*?\*\//g, '')
}
function ohneHtmlKommentare(text) {
  return text.replace(/<!--[\s\S]*?-->/g, '')
}

/**
 * Sucht die Regel, deren Selektor-Kette GENAU so im CSS steht (`{` am
 * Zeilenende) und liefert ihren Deklarationsblock.
 */
function block(css, selektor) {
  const re = new RegExp(`(?:^|\\})\\s*${selektor.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\s*\\{([^}]*)\\}`, 'm')
  const m = re.exec(css)
  return m ? m[1] : null
}

const INDEX_CSS = ohneCssKommentare(lies('index.css'))
const TOPBAR = ohneHtmlKommentare(lies('components/AppTopbar.vue'))
const SIDEBAR = ohneHtmlKommentare(lies('components/AppSidebar.vue'))
const APP = ohneHtmlKommentare(lies('App.vue'))
const TOKENS = lies('tokens.css')

// ── 1. CSS: EIN Sichtbar-Schalter, und zwar die Handy-Lage ────────────────
test('MT-1 · der Kopfzeilen-Knopf hängt AUSSCHLIESSLICH an der Handy-Lage', () => {
  const grund = block(INDEX_CSS, '.dk-topbar-symbol.dk-menue-knopf')
  assert.ok(grund, 'Grundregel `.dk-topbar-symbol.dk-menue-knopf` fehlt (zwei Klassen — sonst gewinnt DkButton)')
  assert.match(grund, /display:\s*none/, 'ohne Handy-Lage ist der Knopf AUS')

  // Genau EINE Regel schaltet ihn sichtbar — und die trägt die Handy-Klasse.
  assert.match(INDEX_CSS, /\.dk-app--handy \.dk-topbar-symbol\.dk-menue-knopf\s*\{\s*display:\s*inline-flex/,
    'in der Handy-Lage sichtbar (Klasse aus useHandyLage)')
  const sichtbar = [...INDEX_CSS.matchAll(/([^{}]*\.dk-topbar-symbol\.dk-menue-knopf[^{}]*)\{([^}]*)\}/g)]
    .filter((m) => /display:\s*(inline-)?flex/.test(m[2]))
    .map((m) => m[1].trim())
  assert.deepEqual(sichtbar, ['.dk-app--handy .dk-topbar-symbol.dk-menue-knopf'],
    'genau EINE Sichtbar-Regel (Handy-Lage) — sonst gibt es wieder zwei Einstiege')
})

test('MT-1 · eingeklappte Leiste zeigt KEINEN Hamburger mehr (Befund)', () => {
  // Der Befund selbst: `.dk-app.is-collapsed` blendete den Knopf ein, obwohl
  // daneben der Ausklapp-Knopf der Leiste stand.
  assert.ok(!/\.dk-app\.is-collapsed\s+\.dk-topbar-symbol\.dk-menue-knopf/.test(INDEX_CSS),
    'es gibt keine Sichtbar-Regel `…is-collapsed … .dk-menue-knopf` mehr')
  assert.ok(!/is-collapsed[^{}]*\.dk-menue-knopf[^{}]*\{/.test(INDEX_CSS),
    'keine Regel, die den Menu-Knopf an `is-collapsed` koppelt (MT-1)')
})

test('MT-1 · der eine Einstieg am Laptop ist der Ausklapp-Knopf der Leiste', () => {
  // Sichtbar bleibt er in der eingeklappten Leiste, mit derselben Trefferfläche
  // wie die übrigen Kopfzeilen-Knöpfe (K4: 40 px, am Finger 44 px).
  assert.ok(block(INDEX_CSS, '.is-collapsed .dk-sb-collapse'), 'die eingeklappte Leiste zeigt ihren Knopf')
  const knopf = block(INDEX_CSS, '.dk-sb-collapse')
  assert.ok(knopf, 'Grundregel `.dk-sb-collapse` fehlt')
  assert.match(knopf, /width:\s*var\(--control-h\)/, 'Trefferfläche aus dem Token --control-h')
  assert.match(TOKENS, /--control-h:\s*40px/, 'Maus: 40 px')
  assert.match(TOKENS.slice(TOKENS.indexOf('@media (pointer: coarse)')), /--control-h:\s*44px/,
    'Finger: 44 px (K4)')
})

// ── 2. Bauteile ───────────────────────────────────────────────────────────
test('MT-1 · der Ausklapp-Knopf der Leiste ist beschriftet und öffnet die Leiste', () => {
  const { tpl, skript } = teile(SIDEBAR)
  assert.match(tpl, /class="dk-sb-collapse"/, 'Ausklapp-Knopf steht in der Leiste')
  assert.match(tpl, /:aria-label="collapsed \? 'Seitenleiste ausklappen' : 'Seitenleiste einklappen'"/,
    'beschriftet statt nur Symbol (N8)')
  assert.match(tpl, /:title="collapsed \? 'Ausklappen' : 'Einklappen'"/, 'Tooltip nennt die Aktion')
  assert.match(tpl, /@click="\$emit\('toggle-collapse'\)"/, 'der Klick klappt die Leiste wieder aus')
  // AppSidebar gibt das Ereignis weiter, App.vue schaltet den Zustand.
  assert.match(ohneHtmlKommentare(skript), /defineEmits\(\['toggle-collapse'/, 'Ereignis deklariert')
  assert.match(APP, /<AppSidebar[^>]*@toggle-collapse="sidebarCollapsed = !sidebarCollapsed"/,
    'App.vue schaltet den Zustand der Leiste')
})

test('MT-1 · die Schublade liegt nur in der Handy-Lage im DOM', () => {
  assert.match(APP, /<AppMenueSchublade[\s\S]{0,200}v-if="!isVollbildMode && istHandyLage"/,
    'v-if = genau die Bedingung des Kopfzeilen-Knopfes')
  assert.ok(!/<AppMenueSchublade[\s\S]{0,200}sidebarCollapsed/.test(APP),
    'die Schublade hängt nicht mehr an der eingeklappten Leiste')
})

test('MT-1 · Kopfzeilen-Knopf bedient die Schublade weiter (Handy unverändert)', () => {
  const links = TOPBAR.slice(TOPBAR.indexOf('dk-topbar-left'), TOPBAR.indexOf('dk-topbar-right'))
  assert.match(links, /class="dk-topbar-symbol dk-menue-knopf"/, 'Knopf steht links in der Kopfzeile')
  assert.match(links, /@click="\$emit\('open-menu'\)"/, 'er öffnet die Schublade')
  assert.match(APP, /@open-menu="menueOeffnen"/, 'App.vue nimmt das Ereignis an')
})

// ── 3. Alle Seiten: kein zweiter Einstieg irgendwo ────────────────────────
/** Alle .vue-Dateien unter src/diakonos (rekursiv). */
function alleVue(verzeichnis = SRC) {
  const raus = []
  for (const name of readdirSync(verzeichnis)) {
    const pfad = join(verzeichnis, name)
    if (statSync(pfad).isDirectory()) raus.push(...alleVue(pfad))
    else if (name.endsWith('.vue')) raus.push(pfad)
  }
  return raus
}

test('MT-1 · keine Seite baut eine zweite Seitenleiste oder einen eigenen Menü-Knopf', () => {
  const seiten = alleVue().filter((p) => {
    const rel = p.slice(SRC.length + 1)
    // Die Kopfzeile IST der eine Ort des Menü-Knopfs; der App-Rahmen bringt
    // Leiste und Schublade (geprüft in den Tests 4–6).
    return rel !== 'App.vue' && rel !== 'components/AppTopbar.vue' && rel !== 'components/AppSidebar.vue'
      && rel !== 'components/AppMenueSchublade.vue'
  })
  assert.ok(seiten.length > 20, 'Seiten gefunden (Dashboard, Gruppen, Kalender, Mitglieder, Dienste …)')
  for (const pfad of seiten) {
    const text = ohneHtmlKommentare(readFileSync(pfad, 'utf8'))
    const kurz = pfad.slice(SRC.length + 1)
    // Der App-Rahmen (App.vue) BRINGT Leiste und Schublade — er ist der eine
    // Ort, an dem sie entstehen; geprüft wird er in den Tests 4 und 5.
    if (kurz === 'App.vue') continue
    assert.ok(!/dk-menue-knopf/.test(text),
      `${kurz}: kein eigener Menü-Knopf (der eine steht in AppTopbar.vue)`)
    assert.ok(!/<AppMenueSchublade|AppSidebar\b/.test(text),
      `${kurz}: die Seite bringt kein zweites Seitenpanel mit`)
    // Ein Hamburger-SYMBOL (`x1="3" … x2="21"`, drei Linien) außerhalb der
    // Kopfzeile wäre ein zweiter Einstieg. Das Sortier-Symbol von „Personen“
    // ist KEIN Hamburger (Linien ab x1="8" + Punkte) und bleibt erlaubt.
    assert.ok(!/<line x1="3" y1="6" x2="21" y2="6"/.test(text), `${kurz}: kein Hamburger-Symbol in der Seite`)
  }
})

/** Template-, Skript- und Stilteil einer .vue-Datei. */
function teile(quelle) {
  const tpl = quelle.slice(quelle.indexOf('<template>'), quelle.lastIndexOf('</template>'))
  const skript = quelle.slice(quelle.indexOf('<script setup>'), quelle.indexOf('</script>'))
  return { tpl, skript }
}
