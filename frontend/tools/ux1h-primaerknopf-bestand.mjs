/**
 * UX1h — Zaehler fuer den Primaerknopf je Ansicht („genau EIN gefuellter
 * Knopf je Ansicht“, Prinzip S1).
 *
 * WAS GEZAEHLT WIRD
 * `variant="primary"` in den Seiten-Komponenten (`pages/**`). Gezaehlt wird
 * STATISCH je Datei, nicht je Laufzeit — die Frage der Karte ist eine andere
 * als bei UX1e/UX1f/UX1g (dort ging es um Alt-Knoepfe): hier soll hoechstens
 * EIN Primary in einer Ansichtsdatei stehen.
 *
 * AUSNAHMEN (bewusst, mit Begruendung im Test):
 *   * Dialoge: DkDialog/DkModal/DkEndgueltig/… haben einen EIGENEN
 *     Primaerknopf im Fuss; ein Dialog ist eine eigene Ansicht. Knopfe
 *     innerhalb eines Dialogblocks werden deshalb nicht der Seite
 *     zugerechnet — gezählt wird nur, was AUSSERHALB von Dialogen steht.
 *   * Gebundene Varianten (`:variant="a ? 'primary' : 'secondary'"`) zaehlen
 *     nicht: sie schalten zur Laufzeit zwischen zwei Stufen.
 *
 * AUFRUF
 *   node tools/ux1h-primaerknopf-bestand.mjs            → Bericht (exit 1 bei Verstoss)
 *   node tools/ux1h-primaerknopf-bestand.mjs --schreiben → Liste einfrieren
 *
 * REGEL: Die Liste in `tools/ux1h-primaerknopf-bestand.txt` darf NUR
 * SCHRUMPFEN. Mehrere Primaries in einer Datei stehen dort als Ist-Zahl; sie
 * muss sinken, nicht steigen. `frontend/tests/ux1h-primaerknopf.test.mjs`
 * haelt das fest.
 *
 * Die Datei liegt in `frontend/tools/`, weil der Image-Build alle Node-Tests
 * in `frontend/` ausfuehrt (backend/Dockerfile, Stage `frontend`) und der
 * Zaehler nur `frontend/**` liest (Regel 13).
 */
import { readdirSync, readFileSync, writeFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

/** `frontend/` — Wurzel aller Pfade dieser Datei. */
const HIER = path.dirname(fileURLToPath(import.meta.url))
export const FRONTEND = path.resolve(HIER, '..')
const SRC = path.join(FRONTEND, 'src')
export const LISTE = path.join(HIER, 'ux1h-primaerknopf-bestand.txt')

/** Bereich der Karte: die Seiten-Komponenten. */
const SEITEN = 'diakonos/pages'

/** Elemente, die ihre eigene Ansicht mit eigenem Primaerknopf aufmachen. */
export const DIALOG_TAGS = [
  'DkDialog',
  'DkModal',
  'DkEndgueltig',
  'DkWarning',
  'AuditConfirmModal',
  'KronosEventCreate',
  'KronosEventEdit',
  'KronosSeriesDialog',
  'KronosConflictDialog',
  'BefundDialog',
  'GruppeAnlegenDialog',
  'MitgliedHinzufuegenDialog',
]

export function vorlage(text) {
  const start = templateStart(text)
  if (start < 0) return ''
  // Erster Block: das echte `</template>` der Aussenebene suchen.
  let tiefe = 1
  let pos = start
  for (;;) {
    const a = templateStart(text, pos + 1)
    const z = naechstesEnde(text, pos + 1)
    if (z < 0) return text.slice(start)
    if (a >= 0 && a < z) {
      tiefe += 1
      pos = a
      continue
    }
    tiefe -= 1
    if (tiefe === 0) return text.slice(start, z + '</template>'.length)
    pos = z + '</template>'.length
  }
}

/** Position des naechsten schliessenden `</template>` ab `ab` (oder -1). */
function naechstesEnde(text, ab = 0) {
  let pos = ab
  for (;;) {
    const i = text.indexOf('</template', pos)
    if (i < 0) return -1
    const danach = text[i + '</template'.length]
    if (danach !== undefined && /[A-Za-z0-9_.:-]/.test(danach)) {
      pos = i + 1
      continue
    }
    return i
  }
}

/** Position des naechsten oeffnenden `<template …>` ab `ab` (oder -1). */
function templateStart(text, ab = 0) {
  let pos = ab
  for (;;) {
    const i = text.indexOf('<template', pos)
    if (i < 0) return -1
    const danach = text[i + '<template'.length]
    if (danach !== undefined && /[A-Za-z0-9_.:-]/.test(danach)) {
      pos = i + 1
      continue
    }
    return i
  }
}

/** Kommentare entfernen (sie enthalten Beispiele und Erklaerungen). */
export function ohneKommentare(text) {
  return text.replace(/<!--[\s\S]*?-->/g, '')
}

/**
 * Den Inhalt eines Dialog-Elements entfernen — verschachtelungssicher je
 * Tag-Art (auch aehnlich benannte Elemente zaehlen als eigene Tiefe).
 * Fehlt ein schliessender Tag, bleibt der Rest stehen; dann zaehlt der Test
 * hoechstens zu viel, nicht zu wenig.
 */
export function ohneDialoge(text) {
  let out = text
  for (const tag of DIALOG_TAGS) {
    let start = tagStelle(out, tag, 0)
    while (start >= 0) {
      const ende = endeVon(out, start, tag)
      if (ende < 0) break
      out = out.slice(0, start) + out.slice(ende)
      start = tagStelle(out, tag, 0)
    }
  }
  return out
}

/** Position des naechsten oeffnenden Tags `tag` ab `ab` (oder -1). */
function tagStelle(text, tag, ab) {
  let pos = ab
  for (;;) {
    const i = text.indexOf('<' + tag, pos)
    if (i < 0) return -1
    const danach = text[i + tag.length + 1]
    if (danach === undefined || /[A-Za-z0-9_.:-]/.test(danach)) {
      pos = i + 1
      continue
    }
    return i
  }
}

/** Index direkt nach `</tag>` (verschachtelungssicher) oder -1. */
function endeVon(text, start, tag) {
  let pos = start + tag.length + 1
  let tiefe = 1
  while (tiefe > 0) {
    const a = tagStelle(text, tag, pos)
    const z = text.indexOf('</' + tag, pos)
    if (z < 0) return -1
    if (a >= 0 && a < z) {
      tiefe += 1
      const gt = text.indexOf('>', a)
      if (gt < 0) return -1
      pos = gt + 1
      continue
    }
    const gt = text.indexOf('>', z)
    if (gt < 0) return -1
    tiefe -= 1
    pos = gt + 1
    if (tiefe === 0) return pos
  }
  return -1
}

/** Alle `.vue`-Dateien der Seiten (rekursiv, Pfade ab `frontend/`). */
export function seitendateien(dir = path.join(SRC, SEITEN)) {
  const out = []
  for (const eintrag of readdirSync(dir, { withFileTypes: true })) {
    const abs = path.join(dir, eintrag.name)
    if (eintrag.isDirectory()) out.push(...seitendateien(abs))
    else if (eintrag.name.endsWith('.vue')) out.push(relativ(abs))
  }
  return out.sort()
}

/** Pfad in Listen-Schreibweise (`frontend/…`). */
export function relativ(abs) {
  return `frontend/${path.relative(FRONTEND, abs).split(path.sep).join('/')}`
}

/** Der Vorlagen-Ausschnitt einer Seite OHNE Dialoge. */
export function seitenVorlage(abs) {
  return ohneDialoge(ohneKommentare(vorlage(readFileSync(abs, 'utf8'))))
}

/** Die Primaerknoepfe einer Seitenvorlage (Zahl). */
export function primaerzaehlung(text) {
  return [...text.matchAll(/<DkButton\b[^>]*?\bvariant="primary"/gs)].length
}

/**
 * Ist-Zahl je Seiten-Datei mit Primaerknopf. Gebundene Varianten
 * (`:variant="a ? 'primary' : 'secondary'"`) zaehlen NICHT als Primary: sie
 * schalten zur Laufzeit zwischen zwei Stufen und sind nie zwei gefuellte
 * Knoepfe gleichzeitig.
 */
export function bestand() {
  const map = new Map()
  for (const rel of seitendateien()) {
    const abs = path.join(FRONTEND, rel.replace(/^frontend\//, ''))
    const zahl = primaerzaehlung(seitenVorlage(abs))
    if (zahl > 0) map.set(rel, zahl)
  }
  return map
}

/** Die eingefrorene Liste lesen: Pfad → Zahl. */
export function liesBestand(datei = LISTE) {
  let text = ''
  try {
    text = readFileSync(datei, 'utf8')
  } catch {
    return new Map()
  }
  const map = new Map()
  for (const zeile of text.split('\n')) {
    if (!zeile.trim() || zeile.trim().startsWith('#')) continue
    const [pfad, zahl] = zeile.split('\t')
    if (pfad && zahl) map.set(pfad.trim(), Number(zahl))
  }
  return map
}

/** „Nur schrumpfen“: liefert die Verstoesse als Textzeilen. */
export function verstoesse(jetzt = bestand(), frueher = liesBestand()) {
  const fehler = []
  for (const [pfad, zahl] of jetzt) {
    const alt = frueher.get(pfad)
    if (alt === undefined) fehler.push(`${pfad}: neu mit ${zahl} Primärknopf/-knöpfen`)
    else if (zahl > alt) fehler.push(`${pfad}: ${zahl} statt ${alt} Primärknöpfe (darf nur sinken)`)
  }
  return fehler
}

const KOPF = `# UX1h — eingefrorener Bestand der Primärknöpfe je Ansicht (Prinzip S1).
#
# Gezählt: \`variant="primary"\` in pages/**/*.vue, NUR ausserhalb von
#          Dialogen (DkDialog, DkModal, DkEndgueltig, DkWarning, …), ohne
#          Kommentare. Gebundene Varianten (\`:variant="a ? 'primary' : …"\`)
#          zaehlen nicht.
# Format:  relativer/pfad<TAB>anzahl_primary
#
# REGEL: Die Zahlen dürfen NUR SINKEN. Zielzustand: keine Zeile mehr (oder
# höchstens 1 je Datei). Erzeugt mit (aus frontend/ heraus):
#   node tools/ux1h-primaerknopf-bestand.mjs --schreiben
# Geprüft von frontend/tests/ux1h-primaerknopf.test.mjs.
`

/** Der Bestand als Text der Liste. */
export function alsText() {
  const jetzt = bestand()
  const zeilen = [...jetzt].map(([pfad, zahl]) => `${pfad}\t${zahl}`).join('\n')
  const summe = [...jetzt.values()].reduce((a, b) => a + b, 0)
  return `${KOPF}#\n# Stand (UX1h): ${summe} Primärknöpfe in ${jetzt.size} Dateien.\n${zeilen}\n`
}

// ── Aufruf von der Kommandozeile ───────────────────────────────────────────
if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  if (process.argv.includes('--schreiben')) {
    writeFileSync(LISTE, alsText(), 'utf8')
    console.log(`geschrieben: ${path.relative(process.cwd(), LISTE)}`)
  } else {
    const jetzt = bestand()
    for (const [pfad, zahl] of jetzt) console.log(`${pfad}\t${zahl}`)
    const fehler = verstoesse(jetzt)
    if (fehler.length) {
      console.error('\nVerstoss (nur schrumpfen):\n  ' + fehler.join('\n  '))
      process.exit(1)
    }
    console.log('\nOK — ' + [...jetzt.values()].reduce((a, b) => a + b, 0) + ' Primärknöpfe')
  }
}
