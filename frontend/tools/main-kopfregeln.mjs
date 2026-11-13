/**
 * Erzeugt `tools/main-kopfregeln.txt` — die Kopfzeilen-/Krumen-Regeln aus `main`.
 * (DEVBADGE-1c: `.dk-topbar` selbst zählt mit — vorher waren nur die Nachfahren
 * erfasst, der geänderte Kopf-Rand fiel damit durch. Siehe `BEREICH`.)
 *
 * WOZU: Der CSS-Wächter `tests/devbadge1b-css-main-treue.test.mjs` vergleicht
 * den Branch gegen den main-Stand. Im Image-Build gibt es kein `.git`, dort
 * kann er `git show main:…` nicht aufrufen — dann liest er diese Datei.
 *
 * Aufruf (aus frontend/):
 *   node tools/main-kopfregeln.mjs --schreiben    # Datei neu erzeugen
 *   node tools/main-kopfregeln.mjs                # nur zeigen, was drinsteht
 *
 * Nach einem Merge nach main: einmal `--schreiben` und die Datei committen.
 */
import { execFileSync } from 'node:child_process'
import { writeFileSync, readFileSync } from 'node:fs'
import { join, dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const HIER = dirname(fileURLToPath(import.meta.url))
const FRONTEND = resolve(HIER, '..')
export const LISTE = join(HIER, 'main-kopfregeln.txt')

/**
 * Der Bereich, den der Dev-Eintrag verknappt: Kopfzeile und Krumen.
 *
 * DEVBADGE-1c (Review, Wächter-Lücke): `.dk-topbar` SELBST fehlte — die
 * Karte änderte den Kopf-Rand (`.dk-app--dev.dk-app--handy .dk-topbar`), aber
 * nur die Nachfahren (`dk-topbar-*`) waren erfasst. Eine Regel
 * `.dk-app--handy .dk-topbar { padding: 0 var(--sp-3) }` ohne Dev-Kopplung
 * wäre also unbemerkt durchgegangen. Jetzt zählt `.dk-topbar` mit
 * (`dk-topbar(?![\w-])`, damit nur der eigene Wähler trifft und kein
 * `dk-topbar-suche` daneben), ebenso die Krumen mit `dk-crumb` (deckt
 * `dk-crumbs`, `dk-crumb`, `dk-crumb-current` … ab).
 * Ausgenommen bleibt nur der Menü-Knopf (`.dk-topbar-symbol.dk-menue`):
 * Trefferfläche aus DEV-B6, keine Folge des Dev-Eintrags.
 */
export const BEREICH = /dk-topbar(?![\w-])|dk-topbar-(?!symbol\.dk-menue)|dk-crumb/

export function ohneKommentare(text) {
  return text.replace(/\/\*[\s\S]*?\*\//g, '')
}

/** Zerlegt CSS in `{ waehler, inhalt, media }` — auch in `@media`-Blöcken. */
export function regeln(cssText) {
  const text = ohneKommentare(cssText)
  const ergebnis = []
  let i = 0
  const mediaStapel = []
  let puffer = ''
  while (i < text.length) {
    const zeichen = text[i]
    if (zeichen === '@' && text.slice(i, i + 6) === '@media') {
      const klammer = text.indexOf('{', i)
      mediaStapel.push(text.slice(i, klammer).trim())
      i = klammer + 1
      puffer = ''
      continue
    }
    if (zeichen === '{') {
      const waehler = puffer.trim().replace(/\s+/g, ' ')
      puffer = ''
      let tiefe = 1
      let j = i + 1
      while (j < text.length && tiefe > 0) {
        if (text[j] === '{') tiefe++
        else if (text[j] === '}') tiefe--
        j++
      }
      const inhalt = text.slice(i + 1, j - 1).trim().replace(/\s+/g, ' ').replace(/;\s*$/, '')
      if (waehler && !waehler.startsWith('@')) {
        ergebnis.push({ waehler, inhalt, media: mediaStapel.join(' & ') })
      }
      i = j
      continue
    }
    if (zeichen === '}') {
      mediaStapel.pop()
      puffer = ''
      i++
      continue
    }
    puffer += zeichen
    i++
  }
  return ergebnis
}

/** Die Regeln des Bereichs aus einem CSS-Text. */
export function kopfRegeln(cssText) {
  return regeln(cssText).filter((r) => BEREICH.test(r.waehler))
}

/** Die Regeln des Bereichs aus `main` (braucht `.git`). */
export function ausMain() {
  const css = execFileSync('git', ['show', 'main:frontend/src/diakonos/index.css'], {
    cwd: FRONTEND, encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'],
  })
  return kopfRegeln(css)
}

/** Die eingefrorene Liste lesen: `[{ media, waehler, inhalt }]`. */
export function ausListe() {
  const text = readFileSync(LISTE, 'utf8')
  const zeilen = text.split('\n').filter((z) => z.trim() && !z.startsWith('#'))
  return zeilen.map((z) => {
    const [media, waehler, ...rest] = z.split('|')
    return { media, waehler, inhalt: rest.join('|') }
  })
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const regelnMain = ausMain()
  if (process.argv.includes('--schreiben')) {
    const kopf = [
      '# Kopfzeilen-/Krumen-Regeln aus `main` (Stand beim Start von DEVBADGE-1b).',
      '# ERZEUGT, nicht gepflegt: `node tools/main-kopfregeln.mjs --schreiben`.',
      '# Der CSS-Wächter (tests/devbadge1b-css-main-treue.test.mjs) liest diese',
      '# Liste, damit er auch OHNE .git (Image-Build) gegen main prüfen kann.',
      '# Format: <media>|<wähler>|<inhalt>',
    ]
    const zeilen = regelnMain.map((r) => `${r.media}|${r.waehler}|${r.inhalt}`)
    writeFileSync(LISTE, [...kopf, ...zeilen].join('\n') + '\n')
    console.log(`geschrieben: ${LISTE} (${regelnMain.length} Regeln)`)
  } else {
    console.log(JSON.stringify(regelnMain, null, 2))
  }
}
