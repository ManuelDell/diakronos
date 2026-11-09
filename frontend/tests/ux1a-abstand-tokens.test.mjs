/**
 * UX1a — Wächter: Abstände, Rahmen und Radien kommen aus `tokens.css`.
 *
 * Vier Prüfungen:
 *
 *   T1  Die Skala in `tokens.css` ist die Konzept-Skala
 *       4 · 8 · 12 · 16 · 24 · 32 · 48 · 64 px  (`--sp-1` … `--sp-8`),
 *       `--pad` 16, `--gap` auf der Skala, Rahmen-Tokens vorhanden,
 *       Semantik-Tokens (`--abstand-gruppe` ≥ 2× `--abstand-innen`, `--karte-innen`).
 *
 *   T2  Der Bestand in `tools/abstand-bestand.txt` darf NUR SCHRUMPFEN.
 *       Maßstab ist die OBEN fest hinterlegte Obergrenze (OBERGRENZE), nicht
 *       die Datei selbst — sonst würde eine wachsende Datei sich mit sich
 *       selbst vergleichen.
 *
 *   T3  Neue Dateien fangen bei 0 an: jede Datei unter `src/`, die nicht in
 *       OBERGRENZE steht, trägt keine festen Werte.
 *
 *   T4  Drift-Test gegen die Server-Seite: Die Standardwerte in
 *       `backend/src/diakronos_app/gestaltung/tokens.py` (Karte UX1j) müssen
 *       den Werten in `tokens.css` entsprechen. Die Oberfläche darf nicht
 *       andere Maße zeigen als der Server schreibt.
 *
 * Der Bestand wird von `tools/abstand-bestand.mjs` erzeugt (ein Rechner für
 * Test und Datei, beide liegen in `frontend/`):
 *   node tools/abstand-bestand.mjs --schreiben
 *
 * UX1a2 (F5): Der Rechner zählt jetzt auch die Langformen (margin-top usw.),
 * negative Werte, Werte ohne führende Null und `:style`-Bindungen. Der
 * Bestand ist dadurch größer geworden — die Obergrenzen wurden am 04.11.2026
 * frisch GEZÄHLT (tools/ux1a2-grenzen.py), nicht geschätzt.
 *
 * Läuft wie die übrigen Frontend-Tests im Docker-Build (node --test).
 */
import assert from 'node:assert/strict'
import { existsSync, readFileSync } from 'node:fs'
import path from 'node:path'
import {
  FRONTEND,
  SRC,
  LISTE,
  QUELLE,
  EIGENSCHAFTEN,
  fundstellen,
  wertIstFest,
  bestand,
  liesBestand,
} from '../tools/abstand-bestand.mjs'

// ── 0 · Der Rechner selbst (belegt die Prüfregeln) ─────────────────────────
{
  assert.deepEqual(fundstellen('.a{margin:0}'), [], 'margin:0 ist kein Abstand')
  assert.deepEqual(fundstellen('.a{padding:var(--pad)}'), [], 'var(--…) ist erlaubt')
  assert.deepEqual(fundstellen('.a{gap:var(--sp-2)}'), [], 'var(--…) ist erlaubt')
  assert.equal(fundstellen('.a{margin:4px 8px}').length, 1, 'Kurzschreibweise = EINE Fundstelle')
  assert.equal(fundstellen('.a{padding:12px}').length, 1)
  assert.equal(fundstellen('.a{border:1px solid var(--rahmen-farbe)}').length, 1, 'Kurzschreibweise mit px zählt')
  assert.equal(fundstellen('.a{border-radius:6px}').length, 1)
  assert.equal(fundstellen('.a{border-radius:var(--radius)}').length, 0)
  assert.equal(fundstellen('.a{margin:0 auto}').length, 0, 'auto ist erlaubt')
  assert.equal(fundstellen('.a{left:50%}').length, 0, '% ist erlaubt')
  assert.equal(fundstellen('.a{gap:1rem}').length, 1, 'rem ist ein fester Wert')
  assert.equal(
    fundstellen('.a{padding:calc(var(--sp-2) * 2)}').length,
    0,
    'calc() aus Tokens ist erlaubt',
  )
  assert.equal(fundstellen('.a{top:0}').length, 0, 'top:0 ist kein Abstand')
  assert.equal(fundstellen('<div style="padding:12px">x</div>').length, 1, 'Inline-Stil zählt mit')
  assert.equal(fundstellen('/* margin: 4px */ .a{margin:var(--sp-1)}').length, 0, 'Kommentar zählt nicht')
  assert.equal(fundstellen('.a{width:12px}').length, 0, 'Breiten sind keine Abstände')
  assert.equal(fundstellen('.a{border-color:var(--err)}').length, 0, 'Farbe ist keine Länge')
  assert.ok(EIGENSCHAFTEN.includes('border-radius'), 'border-radius fehlt in der Liste')
  assert.ok(EIGENSCHAFTEN.includes('row-gap'), 'row-gap fehlt in der Liste')
  assert.equal(wertIstFest('0'), false)
  assert.equal(wertIstFest('1px solid'), true)
  assert.equal(wertIstFest('inherit'), false)
  // Der Bestand nennt keine token-Datei und keine Testdatei.
  assert.equal(bestand().get(QUELLE), undefined, 'tokens.css darf nicht im Bestand stehen')
  assert.equal(
    [...bestand().keys()].filter((p) => p.endsWith('.test.mjs')).length,
    0,
    'Testdateien gehören nicht in den Bestand',
  )
}

// ── T1 · Die Skala in tokens.css ist die Konzept-Skala ─────────────────────
/** Liest den Wert eines Tokens aus dem `:root`-Block von tokens.css (in px). */
function tokenWert(text, name) {
  const m = text.match(new RegExp(`--${name}\\s*:\\s*([^;]+);`))
  return m ? m[1].trim() : null
}
/** Folgt `var(--…`-Verweisen bis zu einem Rohwert (max. 8 Sprünge). */
function tokenWertAufgeloest(text, name) {
  let wert = tokenWert(text, name)
  for (let i = 0; i < 8 && wert; i += 1) {
    const m = /^var\(\s*--([\w-]+)\s*\)$/.exec(wert)
    if (!m) return wert
    wert = tokenWert(text, m[1])
  }
  return wert
}
function px(wert, name) {
  // `0` ohne Einheit ist bei Rahmen der konzepttreue Normalfall (Karten ohne
  // Rahmen) — 0 px.
  if (/^0(?:\.0+)?$/.test(wert || '')) return 0
  const m = /^(\d+(?:\.\d+)?)px$/.exec(wert || '')
  assert.ok(m, `--${name} ist kein px-Wert: ${JSON.stringify(wert)}`)
  return Number(m[1])
}
{
  const tokensPfad = path.join(SRC, 'diakonos', 'tokens.css')
  assert.ok(existsSync(tokensPfad), `tokens.css fehlt (${tokensPfad})`)
  const tokens = readFileSync(tokensPfad, 'utf8')

  const SKALA = [4, 8, 12, 16, 24, 32, 48, 64]
  SKALA.forEach((soll, i) => {
    const name = `sp-${i + 1}`
    assert.equal(
      px(tokenWert(tokens, name), name),
      soll,
      `--${name} muss ${soll}px sein (Konzept-Skala 4·8·12·16·24·32·48·64)`,
    )
  })

  assert.equal(px(tokenWert(tokens, 'pad'), 'pad'), 16, '--pad muss 16px sein (Konzept)')

  // `--gap` steht auf der Skala — entweder direkter px-Wert aus der Skala
  // oder ein Verweis auf ein Skalen-Token.
  const gap = tokenWert(tokens, 'gap')
  const gapAufgeloest = tokenWertAufgeloest(tokens, 'gap')
  if (/^var\(--sp-[1-8]\)$/.test(gap)) {
    // Verweis auf die Skala: in Ordnung.
  } else {
    assert.ok(
      SKALA.includes(px(gapAufgeloest, 'gap')),
      `--gap muss auf der Skala liegen, ist aber ${JSON.stringify(gap)}`,
    )
  }

  // Rahmen: Breite und Farbe(n) als Tokens, nicht als Rohwert in Komponenten.
  for (const name of ['rahmen-breite', 'rahmen-farbe', 'rahmen-farbe-sanft']) {
    assert.ok(
      tokenWert(tokens, name) !== null,
      `--${name} fehlt in tokens.css (Rahmen kommen aus Tokens)`,
    )
  }
  assert.equal(px(tokenWert(tokens, 'rahmen-breite'), 'rahmen-breite'), 1, '--rahmen-breite muss 1px sein')

  // Radien bleiben die drei vorhandenen Stufen.
  for (const name of ['radius-sm', 'radius', 'radius-lg']) {
    assert.ok(tokenWert(tokens, name) !== null, `--${name} fehlt in tokens.css`)
  }

  // Semantik-Tokens (S3: Nähe = Zusammengehörigkeit).
  const gruppe = px(tokenWertAufgeloest(tokens, 'abstand-gruppe'), 'abstand-gruppe')
  const innen = px(tokenWertAufgeloest(tokens, 'abstand-innen'), 'abstand-innen')
  assert.ok(
    gruppe >= 2 * innen,
    `--abstand-gruppe (${gruppe}) muss mindestens 2× --abstand-innen (${innen}) sein`,
  )
  assert.ok(
    px(tokenWertAufgeloest(tokens, 'karte-innen'), 'karte-innen') > 0,
    '--karte-innen fehlt/unbrauchbar',
  )
  // Alle vier Semantik-Token sind auf der Skala.
  for (const name of ['abstand-gruppe', 'abstand-innen', 'karte-innen']) {
    assert.ok(
      SKALA.includes(px(tokenWertAufgeloest(tokens, name), name)),
      `--${name} liegt nicht auf der Skala`,
    )
  }

  // Dunkelmodus bleibt unberührt: Maße sind modus-unabhängig. Der
  // Dunkelmodus steht in `[data-theme="dark"]`-Blöcken; dort dürfen Farben
  // neu gesetzt werden, aber KEIN Abstands-/Rahmen-Maß.
  const dunkelIndex = tokens.search(/^\[data-theme="dark"\],?\s*$/m)
  assert.ok(dunkelIndex > 0, 'Dunkelmodus-Block ([data-theme="dark"]) fehlt in tokens.css')
  const dunkel = tokens.slice(dunkelIndex)
  for (const name of [
    'sp-1',
    'sp-5',
    'sp-8',
    'pad',
    'gap',
    'abstand-gruppe',
    'abstand-innen',
    'karte-innen',
    'rahmen-breite',
  ]) {
    assert.equal(
      new RegExp(`--${name}\\s*:`).test(dunkel),
      false,
      `--${name} darf im Dunkelmodus-Block nicht neu gesetzt werden (Maße sind modus-unabhängig)`,
    )
  }
}

// ── T2 · Bestand darf nur schrumpfen (Maßstab: OBERGRENZE) ─────────────────
/**
 * Obergrenze je Datei — Stand der Umstellung, eingefroren.
 * Diese Zahlen sind die Wahrheit, gegen die gemessen wird. Sie dürfen
 * GESENKT, aber nie erhöht werden; eine Datei auf 0 zu bringen heißt:
 * Zeile hier löschen.
 */
const OBERGRENZE = {
  'frontend/src/diakonos/App.vue': 8,
  'frontend/src/diakonos/components/AppBottomNav.vue': 24,
  'frontend/src/diakonos/components/AppSidebar.vue': 1,
  'frontend/src/diakonos/components/MitgliedAuswahl.vue': 15,
  'frontend/src/diakonos/components/VerantwortlicheKarte.vue': 1,
  'frontend/src/diakonos/components/WartendeKontenKarte.vue': 1,
  'frontend/src/diakonos/components/devmodus/BefundDialog.vue': 11,
  'frontend/src/diakonos/components/devmodus/DevStart.vue': 6,
  'frontend/src/diakonos/components/devmodus/Rahmen.vue': 11,
  'frontend/src/diakonos/components/devmodus/screenshot.mjs': 1,
  'frontend/src/diakonos/components/einrichtung/AssistentSchritte.vue': 4,
  'frontend/src/diakonos/components/einrichtung/EinrichtungsKarte.vue': 3,
  'frontend/src/diakonos/components/einrichtung/EinrichtungsLeiste.vue': 2,
  'frontend/src/diakonos/components/einrichtung/MitgliederLeerzustand.vue': 2,
  'frontend/src/diakonos/components/einrichtung/SchrittFertig.vue': 3,
  'frontend/src/diakonos/components/einrichtung/SchrittGemeinde.vue': 3,
  'frontend/src/diakonos/components/einrichtung/SchrittKontakt.vue': 1,
  'frontend/src/diakonos/components/einrichtung/SchrittMitgliederKalender.vue': 5,
  'frontend/src/diakonos/components/einrichtung/SchrittModule.vue': 1,
  'frontend/src/diakonos/components/gruppen/OrganigrammAnsicht.vue': 9,
  'frontend/src/diakonos/components/kronos/KronosConflictDialog.vue': 1,
  'frontend/src/diakonos/components/kronos/KronosEventCreate.vue': 11,
  'frontend/src/diakonos/components/kronos/KronosEventEdit.vue': 11,
  'frontend/src/diakonos/components/kronos/KronosEventView.vue': 3,
  'frontend/src/diakonos/components/kronos/KronosMiniCalendar.vue': 7,
  'frontend/src/diakonos/components/kronos/KronosSeriesDialog.vue': 1,
  'frontend/src/diakonos/components/kronos/KronosSidebar.vue': 7,
  'frontend/src/diakonos/components/kronos/KronosTopbar.vue': 16,
  'frontend/src/diakonos/components/kronos/ModerationAenderungen.vue': 6,
  'frontend/src/diakonos/components/kronos/ModerationBoard.vue': 18,
  'frontend/src/diakonos/components/kronos/ModerationCard.vue': 25,
  'frontend/src/diakonos/components/kronos/ModerationModals.vue': 10,
  'frontend/src/diakonos/components/lieder/LiedBearbeiten.vue': 7,
  'frontend/src/diakonos/components/lieder/LiedgruppeBearbeiten.vue': 1,
  'frontend/src/diakonos/components/mitglieder/MitgliedHinzufuegenDialog.vue': 2,
  'frontend/src/diakonos/components/planrahmen/BedarfDialog.vue': 11,
  'frontend/src/diakonos/components/planrahmen/LiederPflege.vue': 37,
  'frontend/src/diakonos/components/planrahmen/MerkmalWert.vue': 7,
  'frontend/src/diakonos/components/planrahmen/PrAblauf.vue': 21,
  'frontend/src/diakonos/components/planrahmen/PrAnsicht.vue': 13,
  'frontend/src/diakonos/components/planrahmen/PrAnsichtenEditor.vue': 16,
  'frontend/src/diakonos/components/planrahmen/PrAuswahl.vue': 2,
  'frontend/src/diakonos/components/planrahmen/PrDeklarationenEditor.vue': 17,
  'frontend/src/diakonos/components/planrahmen/PrDiff.vue': 7,
  'frontend/src/diakonos/components/planrahmen/PrEditor.vue': 20,
  'frontend/src/diakonos/components/planrahmen/PrErklaerung.vue': 3,
  'frontend/src/diakonos/components/planrahmen/PrErststart.vue': 7,
  'frontend/src/diakonos/components/planrahmen/PrFelderEditor.vue': 23,
  'frontend/src/diakonos/components/planrahmen/PrHandyHinweis.vue': 2,
  'frontend/src/diakonos/components/planrahmen/PrInfo.vue': 6,
  'frontend/src/diakonos/components/planrahmen/PrKalender.vue': 4,
  'frontend/src/diakonos/components/planrahmen/PrKnotenEditor.vue': 9,
  'frontend/src/diakonos/components/planrahmen/PrLegende.vue': 5,
  'frontend/src/diakonos/components/planrahmen/PrMeldungen.vue': 14,
  'frontend/src/diakonos/components/planrahmen/PrParameterForm.vue': 9,
  'frontend/src/diakonos/components/planrahmen/PrRaster.vue': 15,
  'frontend/src/diakonos/components/planrahmen/PrRegelnEditor.vue': 14,
  'frontend/src/diakonos/components/planrahmen/PrReihenEditor.vue': 9,
  'frontend/src/diakonos/components/planrahmen/PrSprungleiste.vue': 5,
  'frontend/src/diakonos/components/planrahmen/PrStammdatenPanel.vue': 7,
  'frontend/src/diakonos/components/planrahmen/PrTabelle.vue': 27,
  'frontend/src/diakonos/components/planrahmen/PrTermineEditor.vue': 9,
  'frontend/src/diakonos/components/planrahmen/PrWert.vue': 4,
  'frontend/src/diakonos/components/planrahmen/Probelauf.vue': 1,
  'frontend/src/diakonos/components/registrierung/DkQrCode.vue': 1,
  'frontend/src/diakonos/components/registrierung/RegLinkTeilen.vue': 2,
  'frontend/src/diakonos/components/ui/DkBadge.vue': 2,
  'frontend/src/diakonos/components/ui/DkBereichsliste.vue': 12,
  'frontend/src/diakonos/components/ui/DkButton.vue': 7,
  'frontend/src/diakonos/components/ui/DkDatumZeit.vue': 1,
  'frontend/src/diakonos/components/ui/DkDialog.vue': 3,
  'frontend/src/diakonos/components/ui/DkEingabe.vue': 2,
  'frontend/src/diakonos/components/ui/DkFehlertext.vue': 1,
  'frontend/src/diakonos/components/ui/DkField.vue': 1,
  'frontend/src/diakonos/components/ui/DkHint.vue': 2,
  'frontend/src/diakonos/components/ui/DkSegment.vue': 4,
  'frontend/src/diakonos/components/ui/DkSelect.vue': 2,
  'frontend/src/diakonos/components/ui/DkSkelett.vue': 1,
  'frontend/src/diakonos/components/ui/DkSpinner.vue': 2,
  'frontend/src/diakonos/components/ui/DkTable.vue': 4,
  'frontend/src/diakonos/components/ui/DkTabs.vue': 3,
  'frontend/src/diakonos/components/website/FreigabeZeile.vue': 2,
  'frontend/src/diakonos/components/widgets/MyServicesWidget.vue': 7,
  'frontend/src/diakonos/components/widgets/PendingRegistrationsWidget.vue': 13,
  'frontend/src/diakonos/index.css': 285,
  'frontend/src/diakonos/kronos.css': 188,
  'frontend/src/diakonos/pages/Adressbuch.vue': 9,
  'frontend/src/diakonos/pages/Beitraege.vue': 10,
  'frontend/src/diakonos/pages/GruppeDetail.vue': 9,
  'frontend/src/diakonos/pages/Gruppen.vue': 17,
  'frontend/src/diakonos/pages/Home.vue': 5,
  'frontend/src/diakonos/pages/Kalender.vue': 1,
  'frontend/src/diakonos/pages/KalenderImport.vue': 5,
  'frontend/src/diakonos/pages/KalenderVerwaltung.vue': 6,
  'frontend/src/diakonos/pages/LiedDetail.vue': 13,
  'frontend/src/diakonos/pages/Lieder.vue': 14,
  'frontend/src/diakonos/pages/LiedgruppeDetail.vue': 8,
  'frontend/src/diakonos/pages/Liedgruppen.vue': 14,
  'frontend/src/diakonos/pages/MitgliedDetail.vue': 1,
  'frontend/src/diakonos/pages/Mitglieder.vue': 5,
  'frontend/src/diakonos/pages/Moderation.vue': 2,
  'frontend/src/diakonos/pages/Profile.vue': 8,
  'frontend/src/diakonos/pages/Registrierung.vue': 8,
  'frontend/src/diakonos/pages/Ressourcen.vue': 108,
  'frontend/src/diakonos/pages/Wiki.vue': 12,
  'frontend/src/diakonos/pages/devmodus/Befunde.vue': 12,
  'frontend/src/diakonos/pages/einrichtung/Assistent.vue': 3,
  'frontend/src/diakonos/pages/einstellungen/Anmeldung.vue': 1,
  'frontend/src/diakonos/pages/einstellungen/DatenschutzTexte.vue': 2,
  'frontend/src/diakonos/pages/einstellungen/Gemeinde.vue': 1,
  'frontend/src/diakonos/pages/einstellungen/Registrierung.vue': 1,
  'frontend/src/diakonos/pages/einstellungen/RollenRechte.vue': 3,
  'frontend/src/diakonos/pages/mitglieder/Uebersicht.vue': 1,
  'frontend/src/diakonos/pages/planrahmen/Einrichten.vue': 14,
  'frontend/src/diakonos/pages/planrahmen/MeineDienste.vue': 46,
  'frontend/src/diakonos/pages/planrahmen/Plan.vue': 13,
  'frontend/src/diakonos/pages/planrahmen/PlantypEditor.vue': 43,
  'frontend/src/diakonos/pages/planrahmen/Stammdaten.vue': 44,
  'frontend/src/diakonos/pages/planrahmen/Uebersicht.vue': 20,
  'frontend/src/gast/App.vue': 17,
  'frontend/src/organigramm/App.vue': 12,
  'frontend/src/registrierung/App.vue': 9,
  'frontend/src/registrierung/components/DkAnmeldeformular.vue': 34,
  'frontend/src/ssot/seiten.css': 7,
  // UX1a2 (F5): Stand nach dem Schliessen der Waechter-Luecken.
  // Gemessen am 128 Dateien / 1683 Fundstellen — gezaehlt von
  // frontend/tools/abstand-bestand.mjs, nicht geschaetzt.
  // UX1d (D1/D2): Karten ohne Rahmen, Trennlinien leise — acht feste Werte
  // entfallen. DkCard, LoeschantraegeListe, Einstellungen und Datenschutz
  // stehen auf 0 und sind hier GESTRICHEN (ein Eintrag ohne Fundstelle waere
  // nur Ballast); index.css 315 -> 293 (der tote Block `.dk-widget`/`.dk-widget-title` kam dazu), Uebersicht 3 -> 1.
}
{
  assert.ok(existsSync(LISTE), 'tools/abstand-bestand.txt fehlt')
  const ist = bestand()
  const datei = liesBestand()
  const verstoesse = []

  for (const [pfad, zahl] of ist) {
    const soll = OBERGRENZE[pfad]
    if (soll === undefined) {
      verstoesse.push(`${pfad}: ${zahl} Fundstellen, NEU (nicht in der Obergrenze)`)
    } else if (zahl > soll) {
      verstoesse.push(`${pfad}: ${zahl} Fundstellen, erlaubt ${soll}`)
    }
  }
  for (const [pfad, soll] of Object.entries(OBERGRENZE)) {
    const angegeben = datei.get(pfad)
    const tatsaechlich = ist.get(pfad) || 0
    if (angegeben !== undefined && angegeben !== tatsaechlich) {
      verstoesse.push(
        `${pfad}: tools/abstand-bestand.txt nennt ${angegeben}, tatsächlich ${tatsaechlich}` +
          (angegeben > tatsaechlich ? ' — veraltet, senken/entfernen' : ' — zu niedrig, nachziehen'),
      )
    }
    if (tatsaechlich > soll) {
      verstoesse.push(`${pfad}: ${tatsaechlich} Fundstellen über der eingefrorenen Grenze ${soll}`)
    }
  }
  for (const [pfad, angegeben] of datei) {
    if (!(pfad in OBERGRENZE) && angegeben > 0) {
      verstoesse.push(`${pfad}: Eintrag ohne Obergrenze (Datei gehört nicht in den Bestand)`)
    }
  }
  assert.deepEqual(
    verstoesse,
    [],
    'Feste Abstands-/Rahmen-/Radius-Werte im Frontend. Werte kommen aus tokens.css (var(--…)):\n  ' +
      verstoesse.join('\n  '),
  )
}

// ── T3 · Die eingefrorene Datei entspricht dem Rechner ─────────────────────
{
  const datei = liesBestand()
  const ist = bestand()
  for (const [pfad, zahl] of datei) {
    assert.equal(
      ist.get(pfad) || 0,
      zahl,
      `${pfad}: tools/abstand-bestand.txt (${zahl}) passt nicht zum Bestand (${ist.get(pfad) || 0})`,
    )
  }
  // Mindestens die Karten-relevanten Verzeichnisse sind erfasst (Wurzel richtig).
  const pfade = [...ist.keys()]
  assert.ok(pfade.some((p) => p.includes('/pages/')), 'Seiten werden nicht erfasst — Wurzel falsch?')
  assert.ok(pfade.some((p) => p.includes('/components/')), 'Komponenten werden nicht erfasst')
}

// ── T4 · Drift-Test gegen die Server-Seite (UX1j, gestaltung/tokens.py) ────
/**
 * UX1a2 (F6): Der Schalter ist SCHARF. Solange UX1j (`gestaltung/tokens.py`)
 * nicht in `main` liegt, gibt es keine zweite Wertquelle — der Test belegt
 * das ausdrücklich und besteht (der Platzhalter-README in
 * `backend/src/diakronos_app/gestaltung/` bleibt dafür liegen).
 *
 * Sobald die Datei existiert, ist Überspringen VERBOTEN: sie wird gelesen,
 * jedes `Token("--name", standard, …)` gegen `tokens.css` aufgelöst und
 * jede Abweichung ist rot. Drei Zusicherungen halten den Schalter ehrlich:
 *   * die Datei muss lesbar sein (Lese-/Syntaxfehler -> rot, nicht grün);
 *   * sie muss mindestens 10 Token nennen (Muster passt nicht -> rot);
 *   * der Detektor wird an einem Beispiel GEGENGEPRÜFT (er findet die
 *     Standardwerte wirklich) — sonst wäre „0 Drift" nur Zufall.
 */
{
  // `frontend/` liegt im Repo; der Backend-Pfad ist von dort aus erreichbar.
  // Im Image-Build (Regel 13) liegt die Kopie unter `UX1A_BACKEND`
  // (backend/Dockerfile, Stage `frontend`) — wie bei UX1j aus demselben Grund
  // NICHT unter dem echten Backend-Pfad (andere Wächter prüfen dort Dateien
  // mit eigenen Erwartungen).
  const py = process.env.UX1A_BACKEND
    ? path.join(process.env.UX1A_BACKEND, 'gestaltung', 'tokens.py')
    : path.resolve(FRONTEND, '..', 'backend', 'src', 'diakronos_app', 'gestaltung', 'tokens.py')

  /** Liest `Token("--name", standard[, min, max[, gruppe=…]])` aus dem Quelltext. */
  const tokenAus = (quelle) =>
    [...quelle.matchAll(/Token\(\s*"(--[\w-]+)"\s*,\s*(-?\d+)\s*,/g)].map((m) => ({
      name: m[1],
      standard: Number(m[2]),
    }))

  // Gegenprobe des Detektors: findet er Standard und Namen wirklich?
  {
    const probe = tokenAus('Token("--sp-5", 24, 12, 80),\nToken("--pad", 16, 4, 48),')
    assert.deepEqual(
      probe,
      [
        { name: '--sp-5', standard: 24 },
        { name: '--pad', standard: 16 },
      ],
      'Gegenprobe: der Token-Detektor liest tokens.py nicht richtig (Namen/Standard)',
    )
  }

  if (!existsSync(py)) {
    process.stderr.write(
      'UX1a2 (F6): backend/src/diakronos_app/gestaltung/tokens.py fehlt (UX1j noch nicht in main) ' +
        '— es gibt keine zweite Wertquelle, also auch keinen Drift. Der Schalter greift, ' +
        'sobald die Datei existiert: dann wird JEDE Abweichung rot.\n',
    )
  } else {
    const quelle = readFileSync(py, 'utf8')
    const tokensCss = readFileSync(path.join(SRC, 'diakonos', 'tokens.css'), 'utf8')
    const tokens = tokenAus(quelle)
    assert.ok(
      tokens.length >= 10,
      `tokens.py liegt vor, aber nur ${tokens.length} Token erkannt — das Muster passt nicht ` +
        '(Änderung der Schreibweise in UX1j?) — Drift-Prüfung darf nicht ins Leere laufen',
    )

    const drift = []
    for (const { name, standard } of tokens) {
      const nameOhne = name.replace(/^--/, '')
      const imCss = tokenWert(tokensCss, nameOhne)
      if (imCss === null) {
        drift.push(`${name}: Standard ${standard} in tokens.py, aber NICHT in tokens.css`)
        continue
      }
      const zahl = px(tokenWertAufgeloest(tokensCss, nameOhne), nameOhne)
      if (zahl !== standard) {
        drift.push(`${name}: tokens.css ${zahl}px ≠ tokens.py Standard ${standard}px`)
      }
    }
    assert.deepEqual(
      drift,
      [],
      'Drift zwischen tokens.css und den Gestaltungs-Standardwerten (tokens.py):\n  ' + drift.join('\n  '),
    )
  }
}
