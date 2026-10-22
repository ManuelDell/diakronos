/**
 * N13 — Organigramm als Ansicht in „Gruppen“.
 *
 * Entscheidung 9 der Neuordnung: der eigene Menüpunkt „Organigramm“ entfällt,
 * das Organigramm wird die zweite Ansicht der Seite „Gruppen“ (Umschalter
 * Liste/Organigramm), die alte Adresse `#/organigramm` leitet weiter.
 *
 * Der Test liest die echten Quelltexte (keine Kopien) und prüft zusätzlich
 * die Ansichts-Auswertung aus dem Hash als Verhalten (wie
 * `organigramm-xss-farbe.test.mjs` die Renderer lädt). Läuft im Docker-Build
 * über den Globb `tests/planrahmen-*.test.mjs`.
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, existsSync } from 'node:fs'

const root = new URL('../src/diakonos/', import.meta.url)
const read = (p) => readFileSync(new URL(p, root), 'utf8')

// ── Router: neue Adresse, alte Adresse leitet weiter ───────────────────────
{
  const router = read('router.js')
  assert.ok(
    router.includes("'#/gruppen/organigramm': 'GruppenBereich'"),
    'Router: #/gruppen/organigramm zeigt auf die Seite Gruppen',
  )
  assert.ok(
    router.includes("'#/organigramm':  '#/gruppen/organigramm'"),
    'Router: #/organigramm leitet in der zentralen Weiterleitungstabelle um',
  )
  assert.ok(
    !/if \(hash === '#\/organigramm'\)/.test(router),
    'Router: keine zweite Weiterleitung neben der zentralen Tabelle',
  )
  assert.ok(
    !/'#\/organigramm'\s*:\s*'[A-Za-z]/.test(router),
    'Router: #/organigramm ist keine eigene Route mehr',
  )
  assert.ok(
    !router.includes('./pages/Organigramm.vue'),
    'Router: die Seite Organigramm ist nicht mehr registriert',
  )
}

// ── Alte Seite ist entfallen, Ansicht lebt weiter ──────────────────────────
{
  assert.ok(
    !existsSync(new URL('pages/Organigramm.vue', root)),
    'pages/Organigramm.vue ist entfernt (das Organigramm ist eine Ansicht)',
  )
  const ansicht = read('components/gruppen/OrganigrammAnsicht.vue')
  assert.ok(
    ansicht.includes('get_gruppen_for_orgchart') && ansicht.includes('get_user_create_permissions'),
    'Ansicht: dieselben Backend-Aufrufe wie zuvor (Rechte wie Gruppen)',
  )
  assert.ok(
    ansicht.includes("from '../../../shared/sichere-ausgabe.js'"),
    'Ansicht: sichere Ausgabe aus dem gemeinsamen Modul (P0-5/P0-5b beibehalten)',
  )
  assert.ok(
    ansicht.includes("buildNodeContent") && ansicht.includes("sichereFarbe(d.data.farbe)"),
    'Ansicht: Knoten werden weiter ueber die geprueften Helfer gebaut',
  )
  assert.ok(
    ansicht.includes('id="dk-org-chart"') && ansicht.includes('class="org-scroll"'),
    'Ansicht: der Zeichenbereich rollt auf schmalen Geraeten waagerecht',
  )
  assert.ok(
    ansicht.includes('function knotenBreite') && ansicht.includes('schmalerRahmen'),
    'Ansicht: auf schmalen Geraeten werden schmalere Kaesten gezeichnet (nichts abgeschnitten)',
  )
  // Beim Umschalten auf die Liste wird die Ansicht abgebaut; d3-org-chart meldet
  // sein Fenster-Ereignis (`resize.ID<zahl>`) beim Zeichnen an. Bleibt es nach
  // dem Abbau angemeldet, greift sein Handler auf den entfernten Zeichenbereich
  // zu und wirft `Cannot read properties of null (reading
  // 'getBoundingClientRect')`, sobald sich das Fenster danach aendert
  // (Groessenaenderung, Drehen, Desktop/Mobil).
  assert.ok(
    ansicht.includes('onBeforeUnmount'),
    'Ansicht: d3-org-chart wird beim Abbau geloest (onBeforeUnmount)',
  )
  assert.ok(
    ansicht.includes('chart.clear()'),
    'Ansicht: der Baum wird beim Abbau ueber clear() abgeraeumt',
  )
  // Die Anmeldung am Fenster wird beim Zeichnen mitgeschrieben und beim Abbau
  // ueber die gemerkten Namen wieder abgemeldet.
  assert.ok(
    /function merkeFensterBindungen/.test(ansicht),
    'Ansicht: die Fenster-Ereignisse der Bibliothek werden beim Zeichnen gemerkt',
  )
  assert.ok(
    /function loeseFensterBindungen/.test(ansicht),
    'Ansicht: es gibt eine eigene Abmeldung fuer die Fenster-Ereignisse',
  )
  assert.ok(
    /onBeforeUnmount\(\(\) => \{[\s\S]{0,400}loeseFensterBindungen\(\)/.test(ansicht),
    'Ansicht: beim Abbau werden die Fenster-Ereignisse abgemeldet (kein JS-Fehler danach)',
  )
  // H1 (R-N2-code): abgemeldet wird mit GENAU der Zuhoerer-Funktion, die
  // angemeldet wurde — `removeEventListener(typ, null)` entfernte nichts.
  assert.ok(
    /ziel\.removeEventListener\(\s*typ\s*,\s*fn\s*\)/.test(ansicht),
    'Ansicht: abgemeldet wird mit der gemerkten Zuhoerer-Funktion (H1)',
  )
  assert.ok(
    /fensterBindungen\.push\(\[\s*ziel\s*,\s*typ\s*,\s*rest\[0\]\]/.test(ansicht),
    'Ansicht: beim Merken wird die Zuhoerer-Funktion mitgeschrieben (H1)',
  )
  // Der Merker darf `render()` nicht umgehen: er muss den Aufruf umschliessen.
  assert.ok(
    /merkeFensterBindungen\(\s*\(\)\s*=>\s*chart[\s\S]{0,600}\.render\(\)\s*\)/.test(ansicht),
    'Ansicht: der Merker umschliesst den render()-Aufruf',
  )
}

// ── Umschalter im Gruppen-Bereich (pages/gruppen/Bereich.vue) ───────────────
// N13b: main bringt den Rahmen `GruppenBereich` mit, der Umschalter sitzt
// dort. `pages/Gruppen.vue` bleibt die reine Liste (so wie auf main).
{
  const bereich = read('pages/gruppen/Bereich.vue')
  assert.ok(bereich.includes('DkSegment'), 'Bereich: Umschalter ist die Segmentleiste (DkSegment)')
  assert.ok(bereich.includes("value: 'liste'") && bereich.includes("value: 'organigramm'"),
    'Bereich: beide Ansichten Liste und Organigramm angeboten')
  assert.ok(
    bereich.includes("import('../../components/gruppen/OrganigrammAnsicht.vue')"),
    'Bereich: die Ansicht wird aus components/gruppen geladen',
  )
  assert.ok(
    !bereich.includes("import('../Organigramm.vue')"),
    'Bereich: die entfallene Seite pages/Organigramm.vue wird nicht mehr geladen',
  )
  assert.ok(
    bereich.includes("'#/gruppen/organigramm'"),
    'Bereich: der Umschalter schreibt die eigene Adresse',
  )
  // Die reine Liste führt keinen zweiten Umschalter mehr (sonst zwei Leisten).
  const gruppen = read('pages/Gruppen.vue')
  assert.ok(!gruppen.includes('DkSegment'), 'Gruppen: reine Liste — kein zweiter Umschalter')
  assert.ok(!gruppen.includes('<OrganigrammAnsicht'), 'Gruppen: reine Liste — kein eingebetteter Baum')
  assert.ok(!gruppen.includes('ansichtAusHash'), 'Gruppen: reine Liste — keine Ansichts-Auswertung mehr')
  // Der Anlegen-Knopf gehört zur Liste; im Organigramm wird er nicht gezeigt.
  assert.ok(
    gruppen.includes('perms.can_create_any'),
    'Gruppen: Anlegen-Knopf hängt an den Server-Rechten',
  )
}

// ── Menü: der eigene Eintrag ist weg (Seitenleiste + Mehr-Blatt) ─────────────
{
  // Seitenleiste und „Mehr“-Blatt speisen sich aus EINER Menüdefinition
  // (menue.js, Standard S12) — dort darf kein Organigramm-Eintrag stehen.
  const menue = read('menue.js')
  assert.ok(!menue.includes('#/organigramm'), 'Menüdefinition: kein Organigramm-Eintrag mehr')
  assert.ok(!menue.includes("'Organigramm'"), 'Menüdefinition: keine Organigramm-Beschriftung mehr')
  assert.ok(menue.includes("href: '#/gruppen'"), 'Menüdefinition: Gruppen bleibt erreichbar')
  for (const datei of ['components/AppSidebar.vue', 'components/AppBottomNav.vue']) {
    const nav = read(datei)
    assert.ok(!nav.includes('#/organigramm'), `${datei}: kein fest verdrahteter Organigramm-Eintrag`)
    assert.ok(nav.includes('menue.js'), `${datei}: liest die zentrale Menüdefinition`)
    assert.ok(nav.includes('MENUE'), `${datei}: nutzt die zentrale Menüliste`)
  }
  // Der aktive Zustand der Gruppe deckt auch die Organigramm-Adresse ab:
  // die Sonderregel sitzt in `istAktiv` (nicht mehr im Vorlagen-Ausdruck).
  const sidebar = read('components/AppSidebar.vue')
  assert.ok(
    /istAktiv\(eintrag\)[\s\S]{0,200}currentHash\.value\.startsWith\('#\/gruppen'\)/.test(sidebar),
    'Seitenleiste: Gruppen bleibt bei #/gruppen/organigramm aktiv',
  )
  const topbar = read('components/AppTopbar.vue')
  assert.ok(!/\bOrganigramm:/.test(topbar), 'Kopfzeile: kein Brotkrumen-Eintrag Organigramm mehr')
}

// ── Verhalten: Ansicht aus der Adresse ─────────────────────────────────────
// Geprüft wird die echte Funktion aus `pages/gruppen/Bereich.vue` (der Rahmen
// mit dem Umschalter), nicht eine Kopie.
async function ladeAnsicht() {
  let code = read('pages/gruppen/Bereich.vue').split('<script setup>')[1].split('</script>')[0]
  code = code.replace(/import[^\n]+from[^\n]+\n/g, '')
  code = `
const computed = (f) => ({ get value() { return f() } });
const defineAsyncComponent = () => ({});
const navigate = () => {};
const currentHash = { value: '#/gruppen' };
${code}
export { ansichtAusHash };
`
  return import('data:text/javascript;base64,' + Buffer.from(code).toString('base64'))
}

test('N13: der Hash bestimmt die Ansicht (Liste/Organigramm)', async () => {
  const m = await ladeAnsicht()
  assert.equal(m.ansichtAusHash('#/gruppen'), 'liste')
  assert.equal(m.ansichtAusHash('#/gruppen/'), 'liste')
  assert.equal(m.ansichtAusHash('#/gruppen?x=1'), 'liste')
  assert.equal(m.ansichtAusHash('#/gruppen/organigramm'), 'organigramm')
  assert.equal(m.ansichtAusHash('#/gruppen/organigramm/'), 'organigramm')
  assert.equal(m.ansichtAusHash('#/gruppen/organigramm?view=1'), 'organigramm')
  // Die alte Adresse ist hier (noch) keine Ansicht — der Router leitet vorher um.
  assert.equal(m.ansichtAusHash('#/organigramm'), 'liste')
  assert.equal(m.ansichtAusHash(''), 'liste')
})

console.log('N13 Organigramm als Ansicht in Gruppen: bestanden')
