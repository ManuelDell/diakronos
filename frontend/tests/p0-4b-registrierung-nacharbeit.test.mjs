/**
 * P0-4b — Nacharbeit der oeffentlichen Registrierung (Frontend-Teil).
 *
 * Geprueft werden die Befunde, die im Frontend liegen:
 *
 *   Befund 5   Die Rollenliste in der Anmeldeseite war fest einprogrammiert und
 *              lief damit auseinander. Sie kommt jetzt vom Server
 *              (`anmeldung_get_einstellungen.rollen`); ein bereits gespeicherter
 *              Wert, der nicht in der Liste steht, bleibt trotzdem waehlbar,
 *              statt die Zeile als "unvollstaendig" zu blockieren. Die alte
 *              Seite `pages/Anmeldung.vue` ist mit N12 entfallen; geprueft wird
 *              jetzt `einstellungen/Anmeldung.vue` samt Composable.
 *
 *   Befund 6   Die Einwilligung (`dsgvo`) wird jetzt mitgesendet — serverseitig
 *              verlangt.
 *
 * Der Test kompiliert die SFCs echt und fuehrt die Funktionen in einer kleinen
 * Sandbox aus. Laeuft im Docker-Build ueber `node --test`.
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse, compileScript } from 'vue/compiler-sfc'

const wurzel = new URL('../src/', import.meta.url)
const lesen = (rel) => readFileSync(new URL(rel, wurzel), 'utf8')

// ── Befund 5: Rollenliste kommt vom Server ──────────────────────────────────

{
  // Die alte Seite ist entfallen (N12) — sonst liefen zwei Oberflaechen
  // fuer dieselbe Sache auseinander.
  assert.throws(() => lesen('diakonos/pages/Anmeldung.vue'),
    /ENOENT|no such file/i, 'die alte Seite pages/Anmeldung.vue ist entfernt')

  const quelle = lesen('diakonos/pages/einstellungen/Anmeldung.vue')
  const { descriptor, errors } = parse(quelle, { filename: 'Anmeldung.vue' })
  assert.deepEqual(errors, [], 'einstellungen/Anmeldung.vue: SFC-Struktur')
  compileScript(descriptor, { id: 'Anmeldung.vue' })

  const skript = descriptor.scriptSetup.content
  const composable = lesen('diakonos/composables/useAnmeldeEinstellungen.js')

  // Keine fest eingebaute Rollenliste mehr im Quelltext; die Rollen kommen
  // ueber das Composable vom Server.
  assert.doesNotMatch(skript, /const rollen\s*=\s*ref\(\[[^\]]*'/,
    'die Rollenliste ist nicht fest einprogrammiert')
  assert.match(skript, /useAnmeldeEinstellungen/, 'die Seite nutzt das Composable')
  assert.match(composable, /rollen\.value = d\.rollen/, 'die Rollen kommen aus der Serverantwort')

  // Ein bereits gespeicherter, nicht (mehr) gelisteter Wert bleibt waehlbar.
  assert.match(descriptor.template.content,
    /<option v-if="z\.rolle && !rollen\.includes\(z\.rolle\)"/,
    'bestehende Werte bleiben waehlbar')
}

// ── Befund 6: die Einwilligung wird mitgesendet ─────────────────────────────

for (const rel of ['registrierung/App.vue', 'gast/App.vue']) {
  const quelle = lesen(rel)
  const { descriptor, errors } = parse(quelle, { filename: rel })
  assert.deepEqual(errors, [], rel + ': SFC-Struktur')
  compileScript(descriptor, { id: rel })

  const skript = descriptor.scriptSetup.content
  // Der POST-Body traegt `dsgvo` (serverseitig verlangt).
  assert.match(skript, /dsgvo:\s*form\.dsgvo/, rel + ': dsgvo wird mitgesendet')
  // N12b (W2a): UND die angezeigte Fassung. Ohne sie nimmt der Server den
  // Rueckwaerts-Pfad und belegt die AKTUELLE statt der angezeigten Fassung —
  // der Nachweis waere dann nicht mehr Art. 7 DSGVO (angezeigt = bestaetigt).
  assert.match(skript, /dsgvo_fassung:\s*texte\.einwilligung_fassung/,
    rel + ': die angezeigte Fassung wird mitgesendet')
}

console.log('P0-4b Frontend: Rollen kommen vom Server, bestehende Werte bleiben '
  + 'waehlbar, die Einwilligung samt Fassung wird mitgesendet')