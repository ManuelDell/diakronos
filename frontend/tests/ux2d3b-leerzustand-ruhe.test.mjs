/**
 * UX2d3b · Zustände Teil B: kein Leerzustand, solange geladen wird.
 *
 * BEFUND (Review UX2d3a/C): Seiten bauen im Ladezustand auf (`ref(true)`).
 * Bis die Antwort da ist, sind die Listen leer — und was für „leer" steht,
 * sahen die Nutzer SOFORT: „Keine Termine an diesem Tag.", „Noch keine
 * Beiträge", „Keine offenen Löschanträge.". Nach wenigen Millisekunden sprang
 * der Inhalt darüber. Wer es eilig hatte, las eine Aussage, die noch niemand
 * geprüft hatte.
 *
 * REGEL: In den ersten 300 ms (und überhaupt während des Ladens) steht KEIN
 * Leerzustand. Entweder ein Platzhalter (`DkSkelett` über `useLadeSkelett`,
 * erst nach 300 ms) oder — weil 300 ms kurz sind — nichts. Erst wenn das
 * Laden vorbei ist, darf „nichts da" behauptet werden (Prinzip I5: leer,
 * ladend und Fehler sind drei Zustände).
 *
 * GEPRÜFT WIRD DER QUELLTEXT, nicht ein Kommentar: je Datei jede Zeile, die
 * einen Leerzustands-Baustein (`DkEmpty`, `DkTable`) öffnet. Sie muss entweder
 * hinter einem Skelett (`v-else` zu `v-if="…skelett…"`) stehen oder
 * ausdrücklich „nicht mehr laden" verlangen (`!loading`, `!laedt`, `geladen`).
 *
 * Lauf: node --test tests/ux2d3b-leerzustand-ruhe.test.mjs   (cwd = frontend/)
 */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'
import * as domCompiler from '@vue/compiler-dom'

const HIER = dirname(fileURLToPath(import.meta.url))
const SRC = join(HIER, '..', 'src', 'diakonos')

function lies(relativ) {
  return readFileSync(join(SRC, relativ), 'utf8')
}

/**
 * Nur der Vorlagen-Abschnitt (Skript und Stil zitieren Befunde).
 *
 * Der schließende Tag wird ab `<template>` gesucht — ein `</template>` VOR der
 * Hauptvorlage (ein `<template #slot>` im Kopf der Datei) darf den Ausschnitt
 * nicht auf zwei Zeilen verkürzen.
 */
function vorlage(quelle) {
  const start = quelle.indexOf('<template>')
  if (start < 0) return ''
  const rest = quelle.slice(start)
  const ende = rest.search(/\n<\/template>/)
  return ende < 0 ? rest : rest.slice(0, ende)
}

/**
 * Kommentare fallen weg — sie ZITIEREN den Befund und sind kein Text.
 * Mehrzeilige Kommentare werden ERSETZT, nicht gelöscht: sonst rückten die
 * Zeilen zusammen und die Einrückung (die Grenze zwischen Bedingungskette und
 * Elternelement) wäre an dieser Stelle falsch.
 */
function ohneKommentare(text) {
  return text.replace(/<!--[\s\S]*?-->/g, (treffer) => '\n'.repeat((treffer.match(/\n/g) || []).length))
}

/** Bausteine, die irgendwo einen LEERZUSTAND zeigen (DkTable malt ihn selbst). */
const LEER_BAUSTEINE = ['DkEmpty', 'DkTable']

/**
 * Die Flächen dieser Karte: genau die Stellen, an denen Nutzer während des
 * Ladens „nichts da" lesen konnten. Bewusst namentlich — eine Volltextsuche
 * über alle Dateien fände auch Bausteine ohne Ladezustand.
 */
const GEPRUEFT = [
  'pages/Beitraege.vue',
  'pages/Ressourcen.vue',
  'pages/Mitglieder.vue',
  'pages/Lieder.vue',
  'pages/Dienstplan.vue',
  'pages/KalenderVerwaltung.vue',
  'pages/mitglieder/Uebersicht.vue',
  'pages/mitglieder/Datenschutz.vue',
  'pages/einstellungen/Anmeldung.vue',
  'pages/einstellungen/Papierkorb.vue',
  'components/mitglieder/LoeschantraegeListe.vue',
  'components/kronos/ModerationBoard.vue',
  'components/kronos/KronosDayEventsDialog.vue',
]

/**
 * Steht vor dem Baustein in Zeile `i` ein Lade-Ausschluss?
 * Liefert eine Liste von Befundtexten (leer = in Ordnung).
 */
/**
 * Bedingungen, die für jeden Baustein gelten — gelesen am AST der Vorlage.
 *
 * UX2d3c: Die frühere Fassung tastete rückwärts ZEILEN ab und hing an der
 * Einrückung. Sie verlor Bedingungen in eigenen Attributzeilen (`<DkEmpty` in
 * einer Zeile, `v-if` in der nächsten), rechnete bei mehrzeilig geöffneten
 * Bausteinen mit der falschen Tiefe und sammelte Bedingungen fremder Ketten
 * ein (Elternzweige, `v-for`-Zeilen). Jetzt parst `@vue/compiler-dom` die
 * Vorlage; jeder Knoten kennt seinen Elternteil und seine Zweigposition.
 *
 * Ergebnis: eine Liste `{ tag, zeile, bedingungen }` je Element — in
 * Dokumentreihenfolge.
 */
function knotenBedingungen(text) {
  const ast = domCompiler.parse(text)
  const ergebnis = []

  const zweigVorher = (geschwister, idx) => {
    // Bedingungen der `v-if`/`v-else-if`-Geschwister VOR diesem Element
    // (Basis für die Negation in einem `v-else`-Zweig).
    const liste = []
    for (let k = 0; k < idx; k++) {
      const el = geschwister[k]
      if (!el || el.type !== 1) continue
      const d = (el.props || []).filter((p) => p.type === 7)
      const vIf = d.find((p) => p.name === 'if')
      const vElseIf = d.find((p) => p.name === 'else-if')
      const wert = vIf ? ausdruck(vIf) : vElseIf ? ausdruck(vElseIf) : null
      if (wert === null) continue
      // Neue Kette, wenn davor ein Element ohne Bedingung stand.
      liste.push(wert)
    }
    return liste
  }

  const lauf = (knoten, erbe) => {
    if (!knoten || typeof knoten !== 'object') return
    if (Array.isArray(knoten)) {
      knoten.forEach((kind, idx) => {
        if (kind && kind.type === 1) {
          const d = (kind.props || []).filter((p) => p.type === 7)
          const vIf = d.find((p) => p.name === 'if')
          const vElseIf = d.find((p) => p.name === 'else-if')
          const vElse = d.find((p) => p.name === 'else')
          const eigene = []
          if (vIf) eigene.push(ausdruck(vIf))
          else if (vElseIf) {
            for (const b of zweigVorher(knoten, idx)) eigene.push(`!(${b})`)
            eigene.push(ausdruck(vElseIf))
          } else if (vElse) {
            for (const b of zweigVorher(knoten, idx)) eigene.push(`!(${b})`)
          }
          const bedingungen = eigene.length ? [...erbe, ...eigene] : erbe
          // `:leer="…"` (DkTable) ist der Lade-Ausschluss der Tabelle selbst.
          const leerAttr = (kind.props || [])
            .find((p) => p.type === 7 && p.name === 'bind' && p.arg && p.arg.content === 'leer')
          const leerWert = leerAttr && leerAttr.exp && typeof leerAttr.exp.content === 'string'
            ? leerAttr.exp.content
            : ''
          ergebnis.push({
            tag: kind.tag,
            zeile: kind.loc ? kind.loc.start.line : 0,
            bedingungen,
            leerGeladen: /!\s*(loading|laedt)|\bgeladen\b/.test(leerWert),
          })
          lauf(kind.children || [], bedingungen)
          for (const zweig of kind.branches || []) lauf(zweig.children || [], bedingungen)
          return
        }
        lauf(kind, erbe)
      })
      return
    }
    if (knoten.type === 0 /* ROOT */) {
      lauf(knoten.children || [], erbe)
      return
    }
    if (knoten.type === 1) {
      lauf(knoten.children || [], erbe)
      for (const zweig of knoten.branches || []) lauf(zweig.children || [], erbe)
    }
  }
  lauf(ast, [])
  return ergebnis
}

/** Kurzform eines Bindungswertes (`v-if="a && b"` → `a && b`). */
function ausdruck(direktive) {
  return direktive.exp && typeof direktive.exp.content === 'string' ? direktive.exp.content.trim() : ''
}

/**
 * Befundtexte je Baustein (leer = in Ordnung).
 */
function bausteinBefunde(datei) {
  // Ganze Datei parsen (die SFC-Struktur ist gueltig) und dann die Knoten der
  // Hauptvorlage werten — ein Ausschnitt bis zum ersten `</template>` wäre bei
  // verschachtelten `<template #slot>`-Bloecken unvollstaendig.
  const befunde = []
  for (const k of knotenBedingungen(lies(datei))) {
    if (!LEER_BAUSTEINE.includes(k.tag)) continue
    const bedingungen = k.bedingungen

    // UX2d3c: Der FEHLERZUSTAND (`v-if="fehler && !laedt"`) ist ein eigener
    // Zustand, kein Leerzustand — aber er darf nicht während des Ladens stehen
    // („nicht geladen", obwohl noch geladen wird): er braucht einen
    // Lade-Ausschluss.
    // Maßstab ist „der Ladevorgang ist vorbei" — das kann auch über ein
    // Skelett ausgedrückt sein (`v-else-if="fehler"` hinter `v-if="skelettSichtbar"`
    // bringt das `!(…skelett…)` als Vorbedingung mit).
    if (bedingungen.some((b) => /\bfehler\b/.test(b)) &&
        !bedingungen.some((b) => /!\s*(loading|laedt)|[Ss]kelett|[Bb]oardSichtbar/.test(b))) {
      befunde.push(`${datei}:${k.zeile}: Fehlerzustand vor dem Ende des Ladens (Bedingungen: ${JSON.stringify(bedingungen)})`)
      continue
    }

    const skelett = bedingungen.some((b) => /[Ss]kelett|[Bb]oardSichtbar/.test(b))
    const nichtMehrLaden = bedingungen.some((b) => /(!\s*(loading|laedt|isLoading)|\bgeladen\b)/.test(b))
    if (skelett || nichtMehrLaden) continue

    // `DkTable` traegt den Lade-Ausschluss im `:leer`-Attribut (nicht in
    // `v-if`) — das liest die Prüfung am Knoten selbst.
    if (k.leerGeladen) continue
    befunde.push(`${datei}:${k.zeile}: Leerzustand ohne Lade-Ausschluss <${k.tag}> (Bedingungen: ${JSON.stringify(bedingungen)})`)
  }
  return befunde
}

function leerzustandBefunde(datei) {
  const zeilen = ohneKommentare(vorlage(lies(datei))).split('\n')
  const befunde = []
  zeilen.forEach((zeile, i) => {
    // Baustein-Name aus dem KOMPLETTEN Tag holen (mehrzeilig): von `<DkEmpty`
    // bis zum `>` über höchstens fünf Zeilen.
    if (!/^\s*<[A-Za-z]/.test(zeile)) return
    const tag = zeilen.slice(i, i + 5).join(' ').match(/^\s*<([A-Za-z][\w]*)/)
    if (!tag || !LEER_BAUSTEINE.includes(tag[1])) return
    if (zeile.trimStart().startsWith('<!--')) return
    for (const befund of bedingungenVor(zeilen, i)) befunde.push(`${datei}:${i + 1}: ${befund}`)
  })
  return befunde
}

test('UX2d3b · kein Leerzustand, solange noch geladen wird', () => {
  const befunde = GEPRUEFT.flatMap(bausteinBefunde)
  assert.deepEqual(
    befunde,
    [],
    'Der Leerzustand erscheint vor der Antwort (Review UX2d3a/C):\n  ' + befunde.join('\n  '),
  )
})

test('UX2d3b · die geprüften Seiten nutzen das gemeinsame Skelett mit Verzögerung', () => {
  // Ein Leerzustand lässt sich auch „vergessen", indem man ihn hinter ein
  // Skelett hängt, das SOFORT kommt — dann blitzt statt „keine Beiträge"
  // eben ein grauer Balken. Deshalb: wer ein Skelett zeigt, nimmt es über
  // `useLadeSkelett` (300 ms).
  const befunde = []
  for (const datei of GEPRUEFT) {
    const quelle = lies(datei)
    if (!/<DkSkelett\b/.test(quelle)) continue
    // DkSkelett wird über `useLadeSkelett` gezeigt; der Rückgabewert heißt
    // je Seite anders (`skelettSichtbar`, `boardSichtbar`, `ladeSichtbar` …).
    // Der gemeinsame Nenner ist die Komposition selbst.
    if (!/useLadeSkelett\(/.test(quelle)) {
      befunde.push(`${datei}: DkSkelett ohne useLadeSkelett (Blitzgefahr)`)
    }
  }
  assert.deepEqual(befunde, [], befunde.join('\n'))
})

test('UX2d3b · der gebündelte Helfer begrenzt den Ladezustand zeitlich', async () => {
  // Die Regel selbst: erst nach 300 ms sichtbar, danach endgültig.
  const { ladeSkelett, VERZOEGERUNG_MS } = await import(
    '../src/diakonos/composables/ladeSkelett.mjs'
  )
  assert.equal(VERZOEGERUNG_MS, 300)
  const gemeldet = []
  let laufenderTimer = null
  const waechter = ladeSkelett(true, (s) => gemeldet.push(s), {
    timer: {
      set: (fn) => {
        laufenderTimer = fn
        return 1
      },
      clear: () => {
        laufenderTimer = null
      },
    },
  })
  waechter.pruefe(true)
  assert.deepEqual(gemeldet, [], 'Skelett kam sofort')
  laufenderTimer?.()
  assert.deepEqual(gemeldet, [true], 'Skelett kam nach 300 ms nicht')
  waechter.pruefe(false)
  assert.deepEqual(gemeldet, [true, false], 'Skelett blieb nach dem Laden stehen')
})
