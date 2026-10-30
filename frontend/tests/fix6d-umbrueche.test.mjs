// FIX-6d — die 640px-Blöcke sind entschieden und begründet.
//
// Betreiber-Regel (Karte FIX-6d):
//   * Layout-Umschaltung (Navigation, Seitenleiste, Kopf, mobile Bedienelemente)
//     einheitlich bei 720px (= MOBIL_GRENZE_PX in composables/eingabeart.mjs).
//   * Reine Inhaltsumbrüche (Raster 2 -> 1 Spalte innerhalb einer Karte usw.)
//     dürfen bei 640px bleiben, brauchen aber an der Stelle den Kommentar
//     "Inhaltsumbruch, kein Layout" in derselben oder der vorherigen Zeile.
//
// Der Test gilt für die 640px-Stellen dieses Pakets (Entscheidungstabelle in der
// Karte bzw. im Abschlusskommentar). Er prüft drei Dinge:
//   1. keine Layout-Umschaltung in einem 640px-Block,
//   2. jede 640px-Stelle trägt den Kommentar,
//   3. die Liste der 640px-Dateien ist vollständig (keine neue Stelle unbemerkt).
//
// Lauf: node --test tests/fix6d-umbrueche.test.mjs   (cwd = frontend/)

import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, readdirSync, statSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join, relative, sep } from 'node:path'

const HIER = dirname(fileURLToPath(import.meta.url))
const SRC = join(HIER, '..', 'src')
const KOMMENTAR = 'Inhaltsumbruch, kein Layout'
const MOBIL = 720
const INHALT = 640

const MEDIA = /@media[^{]*\(\s*max-width:\s*(\d+)px\s*\)\s*\{/

function dateien(verzeichnis, liste = []) {
  for (const name of readdirSync(verzeichnis)) {
    const pfad = join(verzeichnis, name)
    if (statSync(pfad).isDirectory()) dateien(pfad, liste)
    else if (/\.(vue|css)$/.test(name)) liste.push(pfad)
  }
  return liste
}

// Block ab `{` bis zur passenden schließenden Klammer.
function blockInhalt(text, oeffnend) {
  let tiefe = 0
  for (let i = oeffnend; i < text.length; i++) {
    if (text[i] === '{') tiefe++
    else if (text[i] === '}') {
      tiefe--
      if (tiefe === 0) return text.slice(oeffnend + 1, i)
    }
  }
  return text.slice(oeffnend + 1)
}

// Selektoren, die ein LAYOUT umschalten (App-Rahmen, Navigation, Kopf,
// Seitenleiste). Inhaltsraster (Karten, Formularfelder, Tabellen) stehen bewusst
// NICHT darin — die dürfen ihren eigenen Inhalt umbrechen.
const LAYOUT_MUSTER = [
  /\.dk-app\b/,
  /\.dk-sidebar\b/,
  /\.dk-content\b/,
  /\.dk-screen\b/,
  /\.dk-stats-row\b/,
  /\.dk-quick-row\b/,
  /\.dk-widget-/,
  /\.kronos-header\b/,
  /\.kronos-sidebar\b/,
  /\.bottom-?nav/i,
  /\.sidebar-toggle/,
  /\.rs-layout\b/,
]

const funde = []
for (const pfad of dateien(SRC)) {
  const text = readFileSync(pfad, 'utf8')
  const zeilen = text.split('\n')
  const datei = relative(SRC, pfad).split(sep).join('/')
  const treffer = new RegExp(MEDIA.source, 'g')
  let m
  while ((m = treffer.exec(text)) !== null) {
    const px = Number(m[1])
    const zeile = text.slice(0, m.index).split('\n').length
    const block = blockInhalt(text, text.indexOf('{', m.index))
    funde.push({ datei, zeile, px, block, zeilen })
  }
}

const stellen = funde.filter((f) => f.px === INHALT)

test('jeder 640px-Block ist reiner Inhaltsumbruch und kommentiert', () => {
  const fehler = []
  for (const f of stellen) {
    // Kommentar steht in derselben oder der vorherigen Zeile; ein mehrzeiliger
    // Blockkommentar muss dafür nicht Zeile für Zeile wiederholt werden, deshalb
    // werden bis zu drei Zeilen davor gelesen (Muster: "… kein Layout: …").
    const umfeld = f.zeilen.slice(Math.max(0, f.zeile - 4), f.zeile).join('\n')
    if (!umfeld.includes(KOMMENTAR)) {
      fehler.push(
        `${f.datei}:${f.zeile} — Kommentar "${KOMMENTAR}" fehlt in dieser ` +
          `oder der vorherigen Zeile`
      )
    }
    for (const muster of LAYOUT_MUSTER) {
      if (muster.test(f.block)) {
        fehler.push(
          `${f.datei}:${f.zeile} — schaltet Layout (${muster}); ` +
            `Layout gehört auf ${MOBIL}px`
        )
        break
      }
    }
  }
  assert.ok(stellen.length > 0, 'keine 640px-Stellen gefunden — Muster greift nicht')
  assert.deepEqual(fehler, [], `\n${fehler.join('\n')}\n`)
})

test('Layout-Grenze im Skript ist 720 (eine Zahl, eine Bedeutung)', () => {
  const pfad = join(SRC, 'diakonos', 'composables', 'eingabeart.mjs')
  const text = readFileSync(pfad, 'utf8')
  const treffer = text.match(/MOBIL_GRENZE_PX\s*=\s*(\d+)/)
  assert.ok(treffer, 'MOBIL_GRENZE_PX fehlt in eingabeart.mjs')
  assert.equal(Number(treffer[1]), MOBIL, 'Mobilgrenze muss 720 sein')
})

test('kein Layout-Block unter 720 in den Layout-Dateien (Rahmen, Kopf, Leisten)', () => {
  const fehler = []
  const LAYOUT_DATEIEN = new Set([
    'diakonos/index.css',
    'diakonos/kronos.css',
    'diakonos/components/AppBottomNav.vue',
    'diakonos/components/kronos/KronosTopbar.vue',
  ])
  for (const f of funde) {
    if (!LAYOUT_DATEIEN.has(f.datei) || f.px >= MOBIL) continue
    for (const muster of LAYOUT_MUSTER) {
      if (!muster.test(f.block)) continue
      // Ausnahme mit Begründung direkt an der Stelle: sichtbarer Vermerk.
      const dazu = f.zeilen[f.zeile - 1] || ''
      const davor = f.zeilen[f.zeile - 2] || ''
      if ((dazu + davor).includes('kein Layout-Umschalter')) break
      fehler.push(`${f.datei}:${f.zeile} — Layout (${muster}) unter ${MOBIL}px`)
      break
    }
  }
  assert.deepEqual(fehler, [], `\n${fehler.join('\n')}\n`)
})

test('auch die 640px-Breitenangaben ohne Media-Query sind erklärt', () => {
  // `max-width: 640px` kommt auch als BREITE vor (großer Dialog in kronos.css).
  // Das ist kein Umbruch, muss aber an der Stelle erklärt sein, damit die Zahl
  // nicht mit einem Umschaltpunkt verwechselt wird.
  const pfad = join(SRC, 'diakonos', 'kronos.css')
  const zeilen = readFileSync(pfad, 'utf8').split('\n')
  const fehler = []
  zeilen.forEach((z, i) => {
    if (!/max-width:\s*640px/.test(z)) return
    // Media-Query-Zeilen prüft der obige Test (Kommentar-Pflicht dort).
    const umfeld = zeilen.slice(Math.max(0, i - 5), i + 1).join('\n')
    // Eine Media-Query-Zeile selbst ist kein Breiten-Sonderfall.
    if (/@media/.test(z)) return
    if (!/Kein Umbruch/.test(umfeld)) {
      fehler.push(`${pfad}:${i + 1} — 640px-Breite ohne Hinweis "Kein Umbruch"`)
    }
  })
  assert.deepEqual(fehler, [], `\n${fehler.join('\n')}\n`)
})

test('die 640px-Stellen sind die der Entscheidungstabelle', () => {
  const soll = [
    'diakonos/index.css',
    'diakonos/kronos.css',
    'diakonos/pages/KalenderImport.vue',
    'diakonos/pages/KalenderVerwaltung.vue',
    'diakonos/pages/Ressourcen.vue',
    'diakonos/pages/Registrierung.vue',
    'diakonos/pages/planrahmen/PlantypEditor.vue',
    'diakonos/components/planrahmen/PrFelderEditor.vue',
    'diakonos/components/planrahmen/PrAnsichtenEditor.vue',
    'diakonos/components/planrahmen/PrInfo.vue',
    'diakonos/components/planrahmen/PrEditor.vue',
    'diakonos/components/planrahmen/PrAuswahl.vue',
    'gast/App.vue',
    'registrierung/App.vue',
    'registrierung/components/DkAnmeldeformular.vue',
  ].sort()
  const ist = [...new Set(stellen.map((f) => f.datei))].sort()
  assert.deepEqual(ist, soll, '640px-Stellen weichen von der Entscheidungstabelle ab')
})
