// P2-6 — Datenschutz: keine Schrift von Google (Befund OP-HANDY-17).
//
// Befund: Das ausgelieferte HTML lud Inter von fonts.googleapis.com
// (IP-Adresse jedes Mitglieds an Google, in Deutschland abgemahnt) und
// kostete 48 KB Fremdverkehr im langsamen Gemeindenetz.
//
// Die Ursache lag in `backend/src/diakronos_app/spa.py` (dort entfernt).
// Dieser Test haelt die FRONTEND-Seite der Regel fest: die Schrift muss
// lokal im Buendel liegen und darf in keiner Quelle mehr ueber einen fremden
// Host eingebunden werden. So kann die Regel nicht ueber eine spaetere
// Seite oder ein neues CSS wieder einreissen.

import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const hier = path.dirname(fileURLToPath(import.meta.url))
const src = path.resolve(hier, '../src')

// Hosts, die eine Anfrage des Browsers an einen Dritten bedeuten.
const FREMD = ['fonts.googleapis.com', 'fonts.gstatic.com', 'googleapis.com', 'gstatic.com']

function durchlaufe(verzeichnis) {
  const raus = []
  for (const eintrag of fs.readdirSync(verzeichnis, { withFileTypes: true })) {
    const voll = path.join(verzeichnis, eintrag.name)
    if (eintrag.isDirectory()) raus.push(...durchlaufe(voll))
    else raus.push(voll)
  }
  return raus
}

const QUELLDATEIEN = ['.vue', '.js', '.mjs', '.ts', '.css', '.html', '.json']

test('keine Frontend-Quelle verweist auf einen Google-Schrift-Host (OP-HANDY-17)', () => {
  const treffer = []
  for (const datei of durchlaufe(src)) {
    if (!QUELLDATEIEN.some((e) => datei.endsWith(e))) continue
    const inhalt = fs.readFileSync(datei, 'utf8')
    for (const host of FREMD) {
      if (inhalt.includes(host)) treffer.push(`${path.relative(src, datei)} -> ${host}`)
    }
  }
  assert.deepEqual(treffer, [], `Fremde Schriftquelle gefunden:\n${treffer.join('\n')}`)
})

test('Inter kommt lokal aus dem Buendel (frappe-ui, OFL)', () => {
  // `index.css` zieht `frappe-ui/style.css`; DORT steht das @font-face mit
  // der WOFF2-Datei. Ohne diese Kette waere die Schrift schlicht weg —
  // der Test bindet die lokale Verfuegbarkeit an den Nachweis oben.
  const indexCss = fs.readFileSync(path.join(src, 'diakonos/index.css'), 'utf8')
  assert.match(indexCss, /@import\s+['"]frappe-ui\/style\.css['"]/, (
    'index.css muss frappe-ui/style.css importieren — sonst fehlt die lokale Inter-Schrift.'
  ))

  const frappeStyle = path.resolve(
    hier, '../node_modules/frappe-ui/src/fonts/Inter/inter.css'
  )
  assert.ok(fs.existsSync(frappeStyle), `Lokale Inter-Quelle fehlt: ${frappeStyle}`)
  const face = fs.readFileSync(frappeStyle, 'utf8')
  assert.match(face, /@font-face/, 'frappe-ui/fonts/Inter/inter.css deklariert kein @font-face.')
  assert.match(face, /Inter\.var\.woff2/, 'Inter-Variable-Schrift nicht referenziert.')
  // Und die Datei selbst muss existieren (kein toter Verweis im Buendel).
  const woff2 = path.resolve(hier, '../node_modules/frappe-ui/src/fonts/Inter/Inter.var.woff2')
  assert.ok(fs.existsSync(woff2), `WOFF2-Datei fehlt: ${woff2}`)
})
