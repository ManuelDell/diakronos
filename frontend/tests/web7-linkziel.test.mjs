/**
 * WEB-7 — U1/U2: ungültige Registrierungs-/Gast-Links führen auf die Hauptseite.
 *
 * BEFUND: Ein abgelaufener, deaktivierter oder erfundener Link zeigte bis
 * WEB-7 eine öffentliche Seite „Zugang nicht möglich – Ungültiger oder
 * deaktivierter Registrierungslink“. Manuel 2026-10-30: „Überall wo man keine
 * Rückmeldung braucht, die Umleitung (auf die Hauptseite).“
 *
 * Verhalten (Regeln U1–U4, Entscheidung in `src/shared/linkziel.js`):
 *   - Token unbekannt/deaktiviert oder `?token=` fehlt
 *        → `location.replace('/')` OHNE Meldung (kein Token in der Konsole).
 *   - Rate-Limit (429), Netzwerk-/Serverfehler (5xx) sowie zeitliche Grenzen
 *     („Anmeldung ab …“, „abgelaufen“, Kontingent erschöpft) → Hinweis bleibt.
 *
 * Die Attrappen sind bewusst schlicht: KEIN Vue-Mount, KEIN jsdom, nur
 * `window`- und `fetch`-Objekte (wie `tests/p0-4-oeffentliche-anmeldung`).
 * Der Test läuft lokal (`node --test`) und im Image (backend/Dockerfile).
 */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

import {
  GRUND_UNBEKANNT,
  HAUPTSEITE,
  brauchtWeiterleitung,
  istToterLink,
  weiterleitenZurHauptseite,
} from '../src/shared/linkziel.js'

const SRC = new URL('../src/', import.meta.url)

// ── Attrappen ──────────────────────────────────────────────────────────────

/** `window`-Attrappe: merkt sich, wohin `location.replace` geführt hat. */
function fensterAttrappe(lage = {}) {
  const ersetzt = []
  return {
    __diakronos: {
      token: 'tok-geheim',
      linkFehler: lage.linkFehler || '',
      linkGrund: lage.linkGrund || '',
      felder: [],
      mitKinder: 0,
      dokumente: [],
      texte: {},
      willkommenstext: '',
    },
    __DIakonosBOOT: { basePath: lage.basePath || '' },
    location: {
      replace(ziel) { ersetzt.push(ziel) },
    },
    ersetzt,
  }
}

/**
 * Die Regel „soll diese Seite weiterleiten?“ wie sie die Seiten benutzen:
 * Entscheidung aus `linkziel.js`, angewendet auf das Boot-Objekt
 * `window.__diakronos` (Token + linkGrund vom Server).
 */
function seiteWeiterleiten(fenster) {
  const d = fenster.__diakronos || {}
  return weiterleitenZurHauptseite(
    brauchtWeiterleitung({ grund: d.linkGrund || '', tokenFehlt: !d.token }),
    fenster,
  )
}

// ── U1/U2: tote Links → Hauptseite, ohne Meldung ───────────────────────────

test('WEB-7 · U1: unbekannter/deaktivierter Token -> location.replace("/")', () => {
  const w = fensterAttrappe({ linkGrund: GRUND_UNBEKANNT })
  assert.equal(seiteWeiterleiten(w), true, 'toter Link muss weiterleiten')
  assert.deepEqual(w.ersetzt, ['/'], 'Ziel ist genau die Wurzel der Domain')
  assert.equal(HAUPTSEITE, '/')
})

test('WEB-7 · U1: Seite ohne token-Parameter -> location.replace("/")', () => {
  const w = fensterAttrappe({ linkGrund: GRUND_UNBEKANNT })
  w.__diakronos.token = ''          // `?token=` fehlt
  w.__diakronos.linkFehler = 'Kein Registrierungstoken angegeben.'
  assert.equal(seiteWeiterleiten(w), true)
  assert.deepEqual(w.ersetzt, ['/'])
})

test('WEB-7 · U2: Gast-Link mit totem Token -> location.replace("/")', () => {
  // Dieselbe Entscheidung für das Bundle `gast` — der Grund kommt aus
  // `_validate_token` (identisch für beide Linktypen).
  const w = fensterAttrappe({ linkGrund: GRUND_UNBEKANNT })
  w.seite = 'gast'
  assert.equal(seiteWeiterleiten(w), true)
  assert.deepEqual(w.ersetzt, ['/'])
})

test('WEB-7 · U6: replace statt href — kein Zurück-Sprung auf den toten Link', () => {
  const quelle = readFileSync(new URL('shared/linkziel.js', SRC), 'utf8')
  assert.match(quelle, /location\.replace\(HAUPTSEITE\)/,
    'Weiterleitung nur über location.replace (Verlaufseintrag ersetzen)')
  assert.doesNotMatch(quelle, /location\.href\s*=/, 'kein location.href (Zurück führt zurück)')
  assert.doesNotMatch(quelle, /console\.(log|info|warn|error)\(.*token/i,
    'kein Token in der Konsole (U6)')
})

test('WEB-7 · Ziel ist die Wurzel der DOMAIN, nicht das Diakronos-Präfix', () => {
  // Mit Präfix (`DIAKRONOS_BASE_PATH=/diakronos`) liegt auf "/" die
  // Gemeinde-Website, in Diakronos landet man nur OHNE Präfix. Ein
  // `mitBasis('/')` würde unter dem Präfix auf die App zeigen — falsch.
  const w = fensterAttrappe({ linkGrund: GRUND_UNBEKANNT, basePath: '/diakonos' })
  assert.equal(seiteWeiterleiten(w), true)
  assert.deepEqual(w.ersetzt, ['/'], 'auch mit Präfix exakt "/"')
})

// ── U3: Rückmeldung bleibt ─────────────────────────────────────────────────

test('WEB-7 · U3: Rate-Limit (429) -> KEINE Weiterleitung, Meldung bleibt', () => {
  const w = fensterAttrappe({
    linkGrund: 'rate_limit',
    linkFehler: 'Es sind gerade zu viele Anmeldungen eingegangen. Bitte versuche es in ein paar Minuten erneut.',
  })
  assert.equal(brauchtWeiterleitung({ grund: 'rate_limit' }), false)
  assert.equal(seiteWeiterleiten(w), false, '429 ist umkehrbar — die Person muss es wissen')
  assert.deepEqual(w.ersetzt, [])
})

test('WEB-7 · U3: Serverfehler (5xx) -> KEINE Weiterleitung, Meldung bleibt', () => {
  for (const grund of ['serverfehler', 'netzwerk']) {
    const w = fensterAttrappe({ linkGrund: grund, linkFehler: 'Zugang nicht möglich.' })
    assert.equal(seiteWeiterleiten(w), false, `${grund}: Meldung bleibt stehen`)
    assert.deepEqual(w.ersetzt, [])
  }
})

test('WEB-7 · U3: zeitliche Link-Grenzen bleiben als Hinweis stehen', () => {
  // „Anmeldung ab … möglich“ / „abgelaufen“ / „maximale Anzahl erreicht“ —
  // der Link ist nicht FALSCH, die Person bekommt einen neuen. Blind
  // weiterleiten sähe wie ein kaputter Link aus.
  for (const grund of ['ab_gleich', 'abgelaufen', 'voll']) {
    assert.equal(istToterLink(grund), false, `${grund} ist kein toter Link`)
    assert.equal(brauchtWeiterleitung({ grund }), false, `${grund}: Meldung bleibt`)
  }
})

test('WEB-7 · gültiger Link (kein Grund) -> Formular, keine Weiterleitung', () => {
  const w = fensterAttrappe({ linkGrund: '' })
  assert.equal(seiteWeiterleiten(w), false)
  assert.deepEqual(w.ersetzt, [])
})

test('WEB-7 · ohne `location` (Sandbox) nie werfen', () => {
  assert.equal(weiterleitenZurHauptseite(true, {}), false)
  assert.equal(weiterleitenZurHauptseite(false, undefined), false)
})

// ── Verdrahtung: die drei öffentlichen Seiten nutzen die EINE Stelle ───────

for (const datei of ['registrierung/App.vue', 'gast/App.vue']) {
  test(`WEB-7 · ${datei}: Weiterleitung vor der Anzeige verdrahtet`, () => {
    const text = readFileSync(new URL(datei, SRC), 'utf8')
    assert.match(text, /from '\.\.\/shared\/linkziel\.js'/,
      'nutzt die gemeinsame Entscheidung (shared/linkziel.js)')
    assert.match(text, /brauchtWeiterleitung\(/,
      'fragt brauchtWeiterleitung() — keine eigene Regel')
    assert.doesNotMatch(text, /location\.href\s*=/, 'kein location.href (U6)')
  })
}

test('WEB-7 · Meldung nur im Zweig ohne Weiterleitung, kein Token in der Konsole', () => {
  // Ein toter Link wird NICHT mehr erklärt (U1/U2): die Anzeige des Fehlers
  // hängt hinter `umgeleitet` — vor jeder Meldung steht die Weiterleitung.
  for (const datei of ['registrierung/App.vue', 'gast/App.vue']) {
    const text = readFileSync(new URL(datei, SRC), 'utf8')
    const kopfteil = text.split('<script')[0]  // Template der Seite
    assert.match(kopfteil, /v-if="umgeleitet"/,
      `${datei}: bei toter Weiterleitung bleibt die Karte leer (keine Meldung)`)
    assert.match(kopfteil, /v-else-if="linkFehler"/,
      `${datei}: die Meldung erscheint NUR, wenn nicht weitergeleitet wird`)
    assert.doesNotMatch(text, /console\./,
      `${datei}: keine Konsolenausgaben (der Token steht in der Adresse)`)
  }
})
