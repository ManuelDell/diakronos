/**
 * ON-0b — Wächter: EINE CSS-Quelle (tokens.css), jetzt für das GANZE Frontend.
 *
 * Was ON-0a nur stichprobenartig prüfte (feste Schriftfamilien in drei
 * Verzeichnissen), gilt hier flächendeckend:
 *
 *   F1  ALLE `frontend/src/**` (.vue/.css/.js/.mjs) außer `diakonos/tokens.css`
 *       tragen keine festen Farben (#hex, rgb(), hsl()), keine festen
 *       Schriftfamilien und keine `font:`-Kurzschreibweise mit Schriftnamen.
 *       Inline-Stile (`style="…"`) sind Text wie jeder andere und zählen mit.
 *       Datendaten-Farben (Google-/Kalender-/Kachelfarben) sind als
 *       dokumentierte Ausnahmen in `tools/css-ssot-bestand.mjs` hinterlegt.
 *
 *   F2  Der Bestand in `tools/css-ssot-bestand.txt` darf NUR SCHRUMPFEN.
 *       Maßstab ist die OBEN fest hinterlegte Obergrenze (OBERGRENZE) — nicht
 *       die Datei selbst, sonst könnte eine Wachstums-Datei sich mit sich
 *       selbst vergleichen. Geprüft wird in beide Richtungen:
 *         * Fundstellen > Obergrenze ODER neuer Pfad  -> rot
 *         * Datei fehlt / Zahl zu hoch                -> rot
 *         * Datei niedriger als Obergrenze angegeben  -> rot (nachziehen)
 *       Ein Pfad, der WEIT unter seiner Obergrenze liegt, darf in der Datei
 *       fehlen — dann zählt die 0 aus OBERGRENZE.
 *
 * Der Bestand wird von `tools/css-ssot-bestand.mjs` erzeugt (ein Rechner für
 * Test und Datei, beide liegen in `frontend/`):  node tools/css-ssot-bestand.mjs --schreiben
 *
 * Läuft wie die übrigen Frontend-Tests im Docker-Build (node --test).
 */
import assert from 'node:assert/strict'
import { readFileSync, readdirSync, statSync, existsSync } from 'node:fs'
import path from 'node:path'
import {
  FRONTEND,
  SRC,
  LISTE,
  QUELLE,
  AUSNAHMEN,
  fundstellen,
  bestand,
  liesBestand,
} from '../tools/css-ssot-bestand.mjs'

/**
 * Obergrenze je Datei — am Ende von ON-0b eingefroren (Stand der Abgabe).
 *
 * Diese Zahlen sind die Wahrheit, gegen die gemessen wird. Sie dürfen
 * gesenkt, aber NIE erhöht werden; eine Datei zu 0 zu bringen heißt: Zeile
 * hier löschen.
 */
const OBERGRENZE = {
  'frontend/src/diakonos/components/registrierung/RegLinkTeilen.vue': 1,
  'frontend/src/diakonos/index.css': 46,
  'frontend/src/diakonos/kronos.css': 29,
  'frontend/src/grundreset.css': 1,
  'frontend/src/shared/kachelfarbe.mjs': 3,
  'frontend/src/shared/sichere-ausgabe.js': 1,
}

// ── 1 · tokens.css bleibt die Quelle, alle anderen sind sauber ─────────────
{
  const tokensPfad = path.join(SRC, 'diakonos', 'tokens.css')
  assert.ok(existsSync(tokensPfad), `tokens.css fehlt (${tokensPfad})`)
  const tokens = readFileSync(tokensPfad, 'utf8')
  assert.ok(tokens.includes('--dk-navy-500'), 'tokens.css ohne Marken-Skala')
  assert.ok(tokens.includes('--font:'), 'tokens.css ohne Schrift-Token')
}

// ── 2 · Der Wächter sieht ALLE Vue-/CSS-Dateien (nicht nur drei Ordner) ────
function* dateien(dir) {
  for (const name of readdirSync(dir)) {
    const p = path.join(dir, name)
    if (statSync(p).isDirectory()) {
      if (name === 'node_modules' || name === 'dist') continue
      yield* dateien(p)
    } else if (/\.(vue|css|js|mjs)$/.test(name)) yield p
  }
}
{
  const alle = [...dateien(SRC)].map((p) =>
    path.relative(FRONTEND, p).split(path.sep).join('/'),
  )
  const vue = alle.filter((p) => p.endsWith('.vue'))
  assert.ok(vue.length > 50, `nur ${vue.length} Vue-Dateien gefunden — Wurzel falsch?`)
  assert.ok(
    alle.some((p) => p.startsWith('src/diakonos/pages/')),
    'Seiten werden nicht erfasst',
  )
  // `SRC` ist `<frontend>/src`; die Liste nennt Pfade ab der Repo-Wurzel.
  assert.equal(
    path.relative(FRONTEND, SRC).split(path.sep).join('/'),
    'src',
    'SRC zeigt nicht auf frontend/src',
  )
  // tokens.css liegt im Baum, wird aber vom Rechner (bestand()) selbst
  // ausgenommen — hier wird belegt, dass genau das passiert.
  assert.equal(
    bestand().get(QUELLE),
    undefined,
    'tokens.css darf nicht im Bestand stehen',
  )
  // Testdateien (Ko-Lokation, z. B. composables/*.test.mjs) tragen den
  // Prüftext selbst — sie werden vom Rechner ausgenommen.
  assert.equal(
    [...bestand().keys()].filter((p) => p.endsWith('.test.mjs')).length,
    0,
    'Testdateien gehören nicht in den Bestand',
  )
}

// ── 3 · F2: Bestand darf nur schrumpfen (Maßstab: OBERGRENZE) ─────────────
{
  assert.ok(existsSync(LISTE), 'tools/css-ssot-bestand.txt fehlt')
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
    // Die Datei darf einen Pfad auch WEGLASSEN (dann gilt 0 aus OBERGRENZE);
    // steht er drin, muss er zum Bestand passen.
    if (angegeben !== undefined && angegeben !== tatsaechlich) {
      verstoesse.push(
        `${pfad}: tools/css-ssot-bestand.txt nennt ${angegeben}, tatsächlich ${tatsaechlich}` +
          (angegeben > tatsaechlich
            ? ' — veraltet, senken/entfernen'
            : ' — zu hoch, neu aufnehmen'),
      )
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
    'Feste Farb-/Schriftwerte im Frontend. Werte kommen aus tokens.css (var(--…)):\n  ' +
      verstoesse.join('\n  '),
  )
}

// ── 4 · F1: Stichproben, die die Prüfregeln selbst belegen ────────────────
{
  // Inline-Stil im Markup: Farbwert MUSS gesehen werden.
  assert.deepEqual(fundstellen('<p style="color:#abc">x</p>'), ['#abc'])
  assert.deepEqual(fundstellen('<p style="background:rgba(1,2,3,.4)">x</p>'), ['rgba('])
  // Kurzschreibweise mit Schriftnamen: MUSS gesehen werden.
  assert.deepEqual(fundstellen('.a{font:12px/1.2 system-ui, sans-serif}'), [
    'font:12px/1.2 system-ui, sans-serif',
  ])
  // Kurzschreibweise ohne Schriftnamen und `inherit` sind erlaubt.
  assert.deepEqual(fundstellen('.a{font:inherit}'), [])
  assert.deepEqual(fundstellen('.a{font:600 14px/1.4}'), [])
  assert.deepEqual(fundstellen('.a{font-family:var(--font)}'), [])
  // Kommentar erreicht den Browser nie -> keine Fundstelle.
  assert.deepEqual(fundstellen('/* vorher #fff */ .a{color:var(--text)}'), [])

  // Ausnahmen sind wirklich Ausnahmen: die Google-Farbe bleibt erlaubt …
  const importDatei = readFileSync(
    path.join(SRC, 'diakonos', 'pages', 'KalenderImport.vue'),
    'utf8',
  )
  assert.ok(importDatei.includes('#4285F4'), 'Google-Farbe fehlt — Ausnahme prüfen')
  assert.equal(
    bestand().get('frontend/src/diakonos/pages/KalenderImport.vue') || 0,
    0,
    'Google-Farbe muss als Ausnahme zählen (0)',
  )
  // … und ist dokumentiert.
  assert.ok(
    AUSNAHMEN['frontend/src/diakonos/pages/KalenderImport.vue'].includes('#4285F4'),
    'Google-Farbe ist nicht als Ausnahme dokumentiert',
  )

  // ON-0c (R4): Kurzschreibweise MIT Anfuehrungszeichen/Komma zaehlt immer —
  // vorher brauchte es einen bekannten Namen aus SCHRIFTNAME.
  assert.deepEqual(fundstellen('.a{font:12px/1.2 "Foo Bar", serif}'), [
    'font:12px/1.2 "Foo Bar", serif',
  ])
  assert.deepEqual(fundstellen(".a{font:12px 'Foo Bar'}"), ["font:12px 'Foo Bar'"])
  // Komma ohne Anfuehrungszeichen: eigener Name, der nicht in SCHRIFTNAME steht.
  assert.deepEqual(fundstellen('.a{font:12px FooBar, Baz}'), ['font:12px FooBar, Baz'])
  // Reine Groesse bleibt erlaubt (kein Komma, kein Anfuehrungszeichen).
  assert.deepEqual(fundstellen('.a{font:700 14px/1.5 var(--font)}'), [])
}

// ── 6 · ON-0c (R4): die Ausnahme-Liste ist eingefroren ────────────────────
{
  // Die Dokumentation im Kopf von tools/css-ssot-bestand.txt nennt die
  // Ausnahmen namentlich; ein neuer Eintrag in AUSNAHMEN ohne diese Zusage
  // waere ein stiller Freibrief. Deshalb steht die Zahl hier fest.
  const AUSNAHMEN_ANZAHL = 4
  assert.equal(
    Object.keys(AUSNAHMEN).length,
    AUSNAHMEN_ANZAHL,
    `AUSNAHMEN hat ${Object.keys(AUSNAHMEN).length} Dateien, eingefroren sind ${AUSNAHMEN_ANZAHL} — ` +
      'eine neue Ausnahme ist eine Entscheidung (Karte), kein Nebeneffekt',
  )
  // Und INNERHALB einer Ausnahme nur Farb-Literale: eine Schriftfamilie oder
  // ein `font:`-Eintrag ist nie „Datendaten".
  for (const [datei, werte] of Object.entries(AUSNAHMEN)) {
    assert.ok(Array.isArray(werte) && werte.length > 0, `${datei}: leere Ausnahme`)
    const falsch = werte.filter((w) => !/^#[0-9a-fA-F]{3,8}$/.test(w))
    assert.deepEqual(
      falsch,
      [],
      `${datei}: Ausnahmen sind nur Hex-Farben (Datendaten); hier stehen: ${falsch.join(', ')}`,
    )
  }
}

// ── 5 · Die eingefrorene Datei entspricht dem Rechner ─────────────────────
{
  const datei = liesBestand()
  const ist = bestand()
  for (const [pfad, zahl] of datei) {
    assert.equal(
      ist.get(pfad) || 0,
      zahl,
      `${pfad}: tools/css-ssot-bestand.txt (${zahl}) passt nicht zum Bestand (${ist.get(pfad) || 0})`,
    )
  }
}
