/**
 * UX1b — Wächter: fünf Schriftgrößen, drei Gewichte, eine Quelle.
 *
 *   T1  `tokens.css` trägt die fünf Grundstufen 12/14/16/20/26 und die drei
 *       Gewichte 400/500/600. JEDES andere Rollen-Token (`--fs-*`, `--fw-*`)
 *       zeigt auf eine Stufe — keine Zahl daneben, kein Name ohne Ziel.
 *       Geprüft: `--fs-md` (war NIE definiert und wurde trotzdem benutzt),
 *       `--fw-medium` (dito), `--fw-h` (war 650), Tabellenziffern
 *       (`--fs-tabular`) und die Lesebreite (`--lesebreite` ≤ 70ch).
 *
 *   T2  Der Bestand in `tools/schrift-bestand.txt` darf NUR SCHRUMPFEN.
 *       Maßstab ist die im Rechner hinterlegte Liste; Test und Liste kommen
 *       aus DEMSELBEN Rechner (`tools/schrift-bestand.mjs`).
 *
 *   T3  Neue Dateien fangen bei 0 an: eine Datei unter `src/`, die nicht im
 *       Bestand steht, trägt keine feste Schriftgröße/-gewicht.
 *
 *   T4  Die Oberfläche holt ihre Schrift aus den Tokens: keine der drei
 *       grossen Stylesheets/Seiten setzt noch `font-size:`/`font-weight:`
 *       mit Rohwert. `index.css`, `kronos.css` und `Ressourcen.vue` sind in
 *       UX1b (B3) vollständig umgestellt — eine Rückkehr ist rot.
 *
 *   T5  Die Serverseite zieht mit: die Rollen in
 *       `backend/src/diakronos_app/gestaltung/tokens.py` sind KEINE
 *       Schrifttoken (Schrift ist nicht einstellbar). Das ist eine
 *       Absichtserklärung, kein Zufall — und sie hält den Server davon ab,
 *       eine Schriftgröße zu schreiben, die die fünf Stufen verlässt.
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
  fundstellen,
  wertIstFest,
  bestand,
  liesBestand,
} from '../tools/schrift-bestand.mjs'

const TOKENS = path.join(SRC, 'diakonos', 'tokens.css')

// ── 0 · Der Rechner selbst (belegt die Prüfregeln) ─────────────────────────
{
  assert.deepEqual(fundstellen('.a{font-size:var(--fs-sm)}'), [], 'var(--…) ist erlaubt')
  assert.equal(fundstellen('.a{font-size:13px}').length, 1, '13px zählt')
  assert.equal(fundstellen('.a{font-size:.82rem}').length, 1, 'rem ohne führende Null zählt')
  assert.equal(fundstellen('.a{font-size:0}').length, 0, '0 ist kein Schriftmaß')
  assert.equal(fundstellen('.a{font-size:0px}').length, 0, '0px ist kein Schriftmaß')
  assert.equal(
    fundstellen('.a{font-size:calc(var(--fs-14) * 1)}').length,
    0,
    'calc() aus Tokens ist erlaubt',
  )
  assert.equal(fundstellen('.a{font-weight:600}').length, 1, '600 zählt')
  assert.equal(fundstellen('.a{font-weight:var(--fw-h)}').length, 0, 'var(--fw…) ist erlaubt')
  assert.equal(fundstellen('.a{font-weight:bold}').length, 1, 'bold ist keine Stufe')
  assert.equal(fundstellen('.a{font-weight:normal}').length, 0, 'normal ist die Grundstellung')
  assert.equal(fundstellen('.a{font:600 14px/1.4 Inter}').length, 1, 'Kurzschreibweise zählt')
  assert.equal(fundstellen('.a{font-variant-numeric:tabular-nums}').length, 1, 'tabular-nums zählt')
  assert.equal(fundstellen('.a{font-variant-numeric:var(--fs-tabular)}').length, 0)
  assert.equal(
    fundstellen('<div style="font-size:13px">x</div>').length,
    1,
    'Inline-Stil zählt mit',
  )
  assert.equal(
    fundstellen('/* font-size: 13px */ .a{font-size:var(--fs-14)}').length,
    0,
    'Kommentar zählt nicht',
  )
  assert.equal(wertIstFest('font-size', 'var(--fs-12)'), false)
  assert.equal(wertIstFest('font-weight', '550'), true, '550 ist keine der drei Stufen')
  // Der Bestand nennt keine Token- und keine Testdatei.
  assert.equal(bestand().get(QUELLE), undefined, 'tokens.css darf nicht im Bestand stehen')
  assert.equal(
    [...bestand().keys()].filter((p) => p.endsWith('.test.mjs')).length,
    0,
    'Testdateien gehören nicht in den Bestand',
  )
}

// ── Hilfen ─────────────────────────────────────────────────────────────────
const tokensText = readFileSync(TOKENS, 'utf8')

/** Wert eines Tokens aus der ganzen Datei (erster Treffer). */
function tokenWert(name) {
  const m = tokensText.match(new RegExp(`--${name}\\s*:\\s*([^;]+);`))
  return m ? m[1].trim() : null
}

/** Alle *Deklarationen* der Rollen-Tokens (`--fs-…`/`--fw-…`) eines Blocks. */
function rollenImBlock(block) {
  const treffer = []
  for (const m of block.matchAll(/(--(?:fs|fw)-[\w-]+)\s*:\s*([^;]+);/g)) {
    treffer.push({ name: m[1], wert: m[2].trim() })
  }
  return treffer
}

/** Der Text zwischen zwei Blockmarken (Hilfe, um `:root`-Blöcke zu trennen). */
function blockVon(bisMarke) {
  const start = tokensText.indexOf(bisMarke)
  assert.ok(start >= 0, `Blockmarke fehlt in tokens.css: ${bisMarke}`)
  const ende = tokensText.indexOf('\n}', start)
  return tokensText.slice(start, ende)
}

// ── T1 · Fünf Größen, drei Gewichte, alles verweist darauf ─────────────────
{
  const STUFEN = { 12: '12px', 14: '14px', 16: '16px', 20: '20px', 26: '26px' }
  for (const [zahl, soll] of Object.entries(STUFEN)) {
    assert.equal(
      tokenWert(`fs-${zahl}`),
      soll,
      `--fs-${zahl} muss ${soll} sein (fünf Stufen 12/14/16/20/26)`,
    )
  }
  const GEWICHTE = { 'fw-normal': '400', 'fw-mittel': '500', 'fw-fett': '600' }
  for (const [name, soll] of Object.entries(GEWICHTE)) {
    assert.equal(tokenWert(name), soll, `--${name} muss ${soll} sein (drei Gewichte)`)
  }
  // 650/550/700/bold gibt es nicht mehr als Schrift-Wert.
  for (const roh of ['650', '550', '700', 'bold']) {
    assert.ok(
      !new RegExp(`--fw-[\\w-]+\\s*:\\s*${roh}\\s*;`).test(tokensText),
      `Gewicht ${roh} steht noch als Rohwert in tokens.css`,
    )
  }

  // JEDE Rolle zeigt auf eine Stufe — geprüft im Haupt-:root-Block (der zweite
  // Block, in dem die Rollen stehen) UND im Server-Seiten-Block (Abschnitt 3d).
  const rollen = [
    ...rollenImBlock(blockVon('  --fs:     var(--fs-14);')),
    ...rollenImBlock(blockVon('  --fs-feld:       var(--fs-14);')),
    ...rollenImBlock(blockVon('  --fs-abschnitt: var(--fs-16);')),
  ]
  assert.ok(rollen.length >= 12, `zu wenige Rollen gefunden (${rollen.length})`)
  const STUFEN_NAMEN = /^var\(--fs-(?:12|14|16|20|26)\)$/
  for (const { name, wert } of rollen) {
    if (name.startsWith('--fw-')) {
      // Die drei Grundgewichte selbst tragen ihre Zahl; alle anderen zeigen
      // auf ein Grundgewicht.
      if (['--fw-normal', '--fw-mittel', '--fw-fett'].includes(name)) {
        assert.match(wert, /^(?:400|500|600)$/, `${name} muss ein Grundgewicht sein: ${wert}`)
        continue
      }
      assert.match(
        wert,
        /^var\(--fw-(?:normal|mittel|fett)\)$/,
        `${name} zeigt nicht auf ein Gewicht: ${wert}`,
      )
      continue
    }
    if (name === '--fs-tabular') {
      assert.equal(wert, 'tabular-nums', '--fs-tabular ist kein Ziffernwert')
      continue
    }
    if (name === '--fs-in-zeiger') {
      // ON-0a: Handy-Eingaben bleiben 16 px (iOS-Zoom) — über die Stufe.
      assert.equal(wert, 'var(--fs-16)', '--fs-in-zeiger muss 16 px bleiben')
      continue
    }
    assert.match(wert, STUFEN_NAMEN, `${name} steht neben der Stufen-Skala: ${wert}`)
  }

  // Die drei Rollen, die vorher NICHT existierten/neben der Skala lagen.
  assert.equal(tokenWert('fs-md'), 'var(--fs-16)', '--fs-md muss definiert sein (war es nie)')
  assert.equal(tokenWert('fw-medium'), 'var(--fw-mittel)', '--fw-medium muss definiert sein')
  assert.equal(tokenWert('fs-xs'), 'var(--fs-12)', '--fs-xs darf nicht mehr 11px sein')
  assert.equal(tokenWert('fs-h2'), 'var(--fs-20)', '--fs-h2 darf nicht mehr 19px sein')
  assert.equal(
    tokenWert('fs-in-zeiger'),
    'var(--fs-16)',
    'iOS-Zoom-Schutz bleibt 16 px (nur über die Stufe)',
  )

  // Tabellenziffern: ein Token, keine Streuung.
  assert.equal(tokenWert('fs-tabular'), 'tabular-nums', '--fs-tabular fehlt')
  const index = readFileSync(path.join(SRC, 'diakonos', 'index.css'), 'utf8')
  assert.ok(
    /\.dk-table\s*\{[^}]*font-variant-numeric:\s*var\(--fs-tabular\)/s.test(index),
    'die Tabelle nutzt die Tabellenziffern nicht über das Token',
  )
  assert.ok(/\.dk-tabular\b/.test(index), 'Klasse .dk-tabular fehlt in index.css')

  // Lesebreite ≤ ~65 Zeichen (Prinzip Ä3).
  const lese = tokenWert('lesebreite')
  const m = /^(\d+(?:\.\d+)?)ch$/.exec(lese || '')
  assert.ok(m, `--lesebreite ist kein ch-Wert: ${JSON.stringify(lese)}`)
  assert.ok(Number(m[1]) > 40 && Number(m[1]) <= 70, `--lesebreite unbrauchbar: ${lese}`)
  for (const seite of ['pages/Beitraege.vue', 'pages/Wiki.vue']) {
    const text = readFileSync(path.join(SRC, 'diakonos', seite), 'utf8')
    assert.ok(
      text.includes('max-width: var(--lesebreite)'),
      `${seite}: langer Fließtext ohne Lesebreite`,
    )
  }
}

// ── T2 · Bestand darf nur schrumpfen ───────────────────────────────────────
{
  const jetzt = bestand()
  const eingefroren = liesBestand()
  assert.ok(existsSync(LISTE), `Bestandsliste fehlt (${LISTE})`)
  assert.ok(eingefroren.size > 0, 'Bestandsliste ist leer')

  const gewachsen = []
  for (const [pfad, zahl] of jetzt) {
    const soll = eingefroren.get(pfad)
    if (soll === undefined) gewachsen.push(`${pfad}: neu (${zahl})`)
    else if (zahl > soll) gewachsen.push(`${pfad}: ${soll} → ${zahl}`)
  }
  assert.deepEqual(
    gewachsen,
    [],
    'feste Schriftwerte sind gewachsen — neue Werte kommen aus den Tokens:\n' +
      gewachsen.join('\n'),
  )

  // Behobene Stellen müssen nachgezogen sein (sonst misst die Liste gegen eine
  // Welt, die es nicht mehr gibt und der nächste Zuwachs fiele nicht auf).
  const veraltet = []
  for (const [pfad, soll] of eingefroren) {
    const ist = jetzt.get(pfad) || 0
    if (ist !== soll) veraltet.push(`${pfad}: Liste ${soll}, tatsächlich ${ist}`)
  }
  assert.deepEqual(
    veraltet,
    [],
    'Bestandsliste nicht nachgezogen (node tools/schrift-bestand.mjs --schreiben):\n' +
      veraltet.join('\n'),
  )
}

// ── T3 · Neue Dateien fangen bei 0 an ─────────────────────────────────────
{
  const eingefroren = liesBestand()
  const neuMitWerten = [...bestand().keys()].filter((p) => !eingefroren.has(p))
  assert.deepEqual(
    neuMitWerten,
    [],
    'neue Datei mit festen Schriftwerten (nicht in der Liste = 0 erlaubt)',
  )
}

// ── T4 · Die grossen Stylesheets holen alles aus den Tokens ───────────────
{
  for (const datei of ['diakonos/index.css', 'diakonos/kronos.css', 'diakonos/pages/Ressourcen.vue']) {
    const text = readFileSync(path.join(SRC, datei), 'utf8')
    const offen = fundstellen(text)
    assert.deepEqual(
      offen.map((f) => `${f.eigenschaft}: ${f.wert}`),
      [],
      `${datei} trägt noch feste Schriftwerte (UX1b B3)`,
    )
  }
}

// ── T5 · Der Server schreibt keine Schriftgroessen ────────────────────────
{
  // Im Image liegt das Backend nicht unter ../backend (Regel 13) — dann
  // entfällt diese Prüfung ausdrücklich, statt still zu bestehen.
  // Im Image liegt die Kopie unter `/ux1b-backend/gestaltung` (backend/Dockerfile,
  // Stage frontend); im Repo unter `../backend/src/diakronos_app/gestaltung`.
  // `UX1B_BACKEND` hat Vorrang (Nachweis im Wegwerf-Container).
  const backend = process.env.UX1B_BACKEND
    ? path.resolve(process.env.UX1B_BACKEND)
    : ['/ux1b-backend/gestaltung', path.resolve(FRONTEND, '..', 'backend', 'src', 'diakronos_app', 'gestaltung')]
        .find((p) => existsSync(path.join(p, 'tokens.py'))) || '/ux1b-backend/gestaltung'
  const tokensPfad = path.join(backend, 'tokens.py')
  if (!existsSync(tokensPfad)) {
    console.log('# SKIP Backend-Paket nicht vorhanden:', tokensPfad)
  } else {
    const tokens = readFileSync(tokensPfad, 'utf8')
    const schrift = /Token\(\s*"--f[s|w]-/.test(tokens)
    assert.equal(schrift, false, 'gestaltung/tokens.py führt Schrift-Token — Schrift ist nicht einstellbar')
    assert.ok(
      !/--fs-|--fw-/.test(tokens),
      'gestaltung/tokens.py nennt Schrift-Token (--fs-/--fw-) — die fünf Stufen sind nicht einstellbar',
    )
  }
}
