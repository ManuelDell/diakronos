// UI-R8 + UI-R8b — „Was bewirkt welche Rolle?“: ⓘ und Seite „Rollen & Rechte“.
//
// Der Test prüft die OBERFLAECHEN-Logik, nicht den Server:
//   1. Die Texte kommen aus der EINEN Quelle (`get_rollen_erklaerung`) — die
//      Oberfläche kopiert keine Rollenerklärung, keinen Modul-/Stufentitel,
//      keine Einleitung und keine Reihenfolge (R-12, UI-R8b).
//   2. Zuordnung und Reihenfolge der Abschnitte (auch bei anderer Schreibweise
//      und bei der Reihenfolge des Backends).
//   3. Fehlt die Quelle, wird das gesagt statt erfunden — als FUNKTION, nicht
//      als Quelltext-Muster.
//   4. Barrierefreiheit am ⓘ: Knopf mit aria-label „Was bewirkt <Rolle>?“,
//      Escape schließt, kein ⓘ ohne Text. (Das Verhalten im Mount prüfen
//      `r8b-rrinfo-mount.test.mjs` und `r8b-rollenzeile-mount.test.mjs`.)
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import {
  abschnitte, einleitung, erklaerteRollen, erklaerungFuer, fehlendeErklaerung, inReihenfolge,
  ladefehlerText, HINWEIS_OHNE_QUELLE, GRUPPENROLLEN_REIHENFOLGE,
} from '../src/diakonos/composables/rollenErklaerung.mjs'

const lies = (pfad) => readFileSync(new URL(`../src/diakonos/${pfad}`, import.meta.url), 'utf8')

/** Ausschnitt der echten Antwort (Form wie `erklaerung.alles()`, Stand R-12). */
const QUELLE = {
  systemrollen: {
    'Mitglied': { titel: 'Mitglied', kurz: 'Sieht die Namen aller Mitglieder.', darf: ['lesen'], darf_nicht: ['schreiben'] },
    'System Manager': { titel: 'Administrator', kurz: 'Darf als Einzige(r) alles.', darf: ['alles'], darf_nicht: [] },
    'Kalenderadministrator': { titel: 'Kalender-Moderation', kurz: 'Prüft Gemeinde-Termine.', darf: ['prüfen'], darf_nicht: [] },
  },
  gast: { titel: 'Gast', kurz: 'Kein Konto.', darf: ['einen Link lesen'], darf_nicht: ['alles andere'] },
  gruppenrollen: {
    GL: { titel: 'Gruppenleitung (GL, Untergruppe)', kurz: 'Leitet eine Untergruppe.', darf: ['pflegen'], darf_nicht: [] },
    HV: { titel: 'Hauptverantwortliche(r) (HV)', kurz: 'Leitet die Gruppe.', darf: ['alles im Modul'], darf_nicht: ['Module ändern'] },
    MV: { titel: 'Mitverantwortliche(r) (MV)', kurz: 'Wie HV, ohne Ernennen.', darf: ['alles'], darf_nicht: ['ernennen'] },
    Mitglied: { titel: 'Gruppenmitglied', kurz: 'Liest.', darf: [], darf_nicht: [] },
  },
  module: { wiki: 'Wiki der Gruppe.', kalender: 'Kalender der Gruppe.' },
  stufen: { gemeinde: 'Gemeinde-Moderation.', untergruppe: 'Leitung der Untergruppe.' },
  // R-12: Titel, Reihenfolge und Einleitungen kommen ebenfalls vom Server.
  modul_titel: { wiki: 'Wiki (Quelle)', kalender: 'Kalender (Quelle)' },
  stufen_titel: { gemeinde: 'Alle Mitglieder der Gemeinde', untergruppe: 'Untergruppe' },
  systemrollen_reihenfolge: ['Mitglied', 'System Manager', 'Kalenderadministrator'],
  einleitungen: {
    systemrollen: 'EINLEITUNG-SYSTEM',
    gast: 'EINLEITUNG-GAST',
    gruppenrollen: 'EINLEITUNG-GRUPPE',
    module: 'EINLEITUNG-MODULE',
    stufen: 'EINLEITUNG-STUFEN',
  },
}

// ── 1 · Quelle statt Kopie ─────────────────────────────────────────────────

test('UI-R8: die Rollenerklärungen werden vom Server geholt, nicht im Frontend geführt', () => {
  const api = lies('composables/useRollenRechte.js')
  assert.match(api, /get_rollen_erklaerung/, 'Endpunkt get_rollen_erklaerung fehlt')
  assert.match(api, /export function rollenErklaerung/, 'keine Funktion rollenErklaerung')

  // Keine der Erklärtexte steht als Kopie in der Oberfläche.
  const seite = lies('pages/einstellungen/RollenRechte.vue')
  const zugang = lies('components/ZugangKarte.vue')
  const baustein = lies('components/ui/RrInfo.vue')
  for (const [datei, inhalt] of [['RollenRechte.vue', seite], ['ZugangKarte.vue', zugang], ['RrInfo.vue', baustein]]) {
    assert.ok(!inhalt.includes('Darf als Einzige(r) alles'),
      `${datei} enthält eine Kopie einer Rollenerklärung`)
    assert.ok(!/„?Darf nicht“?\s*:\s*\[/.test(inhalt), `${datei} führt eigene darf-nicht-Listen`)
  }
  // Die Seite liest die Quelle über den Composable, nicht über eigenes HTTP.
  assert.match(seite, /rollenErklaerung/)
  assert.match(zugang, /rollenErklaerung\(\)/, 'Zugang-Karte holt die Erklärungen nicht aus der Quelle')
  // R-12: auch Modul-/Stufentitel und Einleitungen stehen NICHT im Frontend.
  assert.ok(!/MODUL_TITEL|STUFEN_TITEL/.test(lies('composables/rollenErklaerung.mjs')),
    'rollenErklaerung.mjs führt noch eigene Modul-/Stufentitel')
  for (const [datei, inhalt] of [['RollenRechte.vue', seite], ['ZugangKarte.vue', zugang]]) {
    assert.ok(!/„für alle“|für alle Mitglieder der Gemeinde/.test(inhalt),
      `${datei} schreibt eigene Rechte-Texte`)
  }
  // Einleitungen der Seite kommen wörtlich aus `erklaerung.einleitungen`.
  assert.match(seite, /erklaerung\.einleitungen\.systemrollen/)
  assert.match(seite, /erklaerung\.einleitungen\.stufen/)
})

test('UI-R8b: Rollen-ⓘ sitzt in der Rollenauswahl — nicht in GruppeDetail (UI-R1)', () => {
  // Der ⓘ an den Rollen gehört in die eigentliche Rollenauswahl. GruppeDetail
  // gehört UI-R1 (Gruppen-Einstellungen) und bleibt hier unberührt; der ⓘ an
  // HV/MV/GL kommt in einer eigenen Karte.
  const zugang = lies('components/ZugangKarte.vue')
  assert.match(zugang, /<RrInfo[^>]*:name="r"/, 'Zugang-Karte ohne ⓘ an den Rollen')
  const seite = lies('pages/einstellungen/RollenRechte.vue')
  assert.match(seite, /<RrInfo[^>]*:name="r"/, 'Rollenauswahl ohne ⓘ')
  assert.match(seite, /Was bewirkt welche Rolle\?/, 'Abschnitt „Was bewirkt welche Rolle?“ fehlt')
  for (const wort of ['Rollen im System', 'Ohne Konto', 'Rollen in einer Gruppe', 'Module', 'Prüfstufen']) {
    assert.ok(seite.includes(wort), `Abschnitt „${wort}“ fehlt`)
  }
  const gruppe = lies('pages/GruppeDetail.vue')
  assert.ok(!/RrInfo/.test(gruppe), 'GruppeDetail.vue darf kein ⓘ tragen (UI-R1-Karte)')
})

// ── 2 · Zuordnung und Reihenfolge ──────────────────────────────────────────

test('UI-R8: ⓘ findet die Erklärung auch bei anderer Schreibweise des Rollennamens', () => {
  // Die Rollenauswahl zeigt „Mitglied“, `Has Role` kennt Systemnamen — die
  // Oberfläche muss beide Formen treffen („Systemmanager“ vs. „System Manager“).
  const direkt = erklaerungFuer(QUELLE.systemrollen, 'System Manager')
  assert.equal(direkt.titel, 'Administrator')
  const anders = erklaerungFuer(QUELLE.systemrollen, 'Systemmanager')
  assert.equal(anders?.titel, 'Administrator')
  assert.equal(erklaerungFuer(QUELLE.systemrollen, 'system_manager')?.titel, 'Administrator')
  assert.equal(erklaerungFuer(QUELLE.systemrollen, 'Unbekannt'), null)
})

test('UI-R8: Abschnitte erscheinen in der Reihenfolge des Servers', () => {
  const a = abschnitte(QUELLE)
  // R-12: die Reihenfolge gibt das BACKEND vor (`systemrollen_reihenfolge`).
  assert.deepEqual(a.systemrollen.map((e) => e.schluessel),
    ['Mitglied', 'System Manager', 'Kalenderadministrator'])
  assert.deepEqual(a.gruppenrollen.map((e) => e.schluessel), ['HV', 'MV', 'GL', 'Mitglied'])
  // Module und Stufen: Schlüsselreihenfolge der Antwort (der Server liefert
  // keine eigene — deshalb steht hier `wiki` vor `kalender`).
  assert.deepEqual(a.module.map((m) => m.schluessel), ['wiki', 'kalender'])
  assert.deepEqual(a.stufen.map((s) => s.schluessel), ['gemeinde', 'untergruppe'])
  assert.equal(a.gast.titel, 'Gast')
  assert.equal(a.leer, false)
  // Und die Überschriften der Module/Stufen sind die des Backends.
  assert.deepEqual(a.module.map((m) => m.titel), ['Wiki (Quelle)', 'Kalender (Quelle)'])
  assert.deepEqual(a.stufen.map((s) => s.titel), ['Alle Mitglieder der Gemeinde', 'Untergruppe'])
})

test('UI-R8b: die Server-Reihenfolge wird übernommen — keine Not-Liste im Frontend', () => {
  // Ohne `systemrollen_reihenfolge` gilt die Schlüsselreihenfolge der Antwort.
  // Eine eigene Reihenfolge im Frontend würde hier „System Manager“ nach vorn
  // ziehen und damit den Server überstimmen.
  const ohne = { ...QUELLE }
  delete ohne.systemrollen_reihenfolge
  assert.deepEqual(abschnitte(ohne).systemrollen.map((e) => e.schluessel),
    ['Mitglied', 'System Manager', 'Kalenderadministrator'])

  // Beweis, dass es keine Not-Liste mehr gibt: eine Antwort in umgekehrter
  // Reihenfolge wird unverändert übernommen.
  const umgekehrt = {
    systemrollen: QUELLE.systemrollen,
    systemrollen_reihenfolge: ['Kalenderadministrator', 'Mitglied', 'System Manager'],
  }
  assert.deepEqual(abschnitte(umgekehrt).systemrollen.map((e) => e.schluessel),
    ['Kalenderadministrator', 'Mitglied', 'System Manager'])
})

test('UI-R8b: das Frontend führt keine zweite Liste von Rollenwissen (Not-Listen gestrichen)', () => {
  const modul = lies('composables/rollenErklaerung.mjs')
  for (const name of ['SYSTEMROLLEN_REIHENFOLGE', 'MODULE_REIHENFOLGE', 'STUFEN_REIHENFOLGE']) {
    assert.ok(!new RegExp(`export\\s+const\\s+${name}`).test(modul),
      `${name} ist wieder da — das ist eine zweite Kopie von Rollenwissen`)
  }
  // Auch keine Rollennamen (außer der reinen Darstellungsreihenfolge der
  // Gruppenrollen, die das Backend gar nicht liefert).
  assert.ok(!/'Mitgliederadministrator'|'Kalenderadministrator'|'Ressourcenmoderator'/.test(modul),
    'Rollenname im Frontend-Modul')
})

test('UI-R8: Einleitungen der fünf Abschnitte kommen wörtlich aus der Quelle', () => {
  const a = abschnitte(QUELLE)
  assert.equal(a.einleitungen.systemrollen, 'EINLEITUNG-SYSTEM')
  assert.equal(a.einleitungen.gast, 'EINLEITUNG-GAST')
  assert.equal(a.einleitungen.gruppenrollen, 'EINLEITUNG-GRUPPE')
  assert.equal(a.einleitungen.module, 'EINLEITUNG-MODULE')
  assert.equal(a.einleitungen.stufen, 'EINLEITUNG-STUFEN')
  // Fehlt ein Text, bleibt er LEER — das Frontend erfindet keine Einleitung.
  assert.equal(einleitung(QUELLE, 'unbekannt'), '')
  assert.equal(einleitung(null, 'systemrollen'), '')
  assert.deepEqual(
    Object.values(abschnitte({ systemrollen: QUELLE.systemrollen }).einleitungen),
    ['', '', '', '', ''],
  )
})

test('UI-R8: die Server-Reihenfolge versteckt keine Rolle, die zusätzlich kommt', () => {
  const liste = inReihenfolge({ 'System Manager': {}, 'Neue Rolle': {} },
    ['System Manager', 'Mitglied', 'Kalenderadministrator'])
  assert.deepEqual(liste.map((e) => e.schluessel), ['System Manager', 'Neue Rolle'])
  // leere/kaputte Einträge ergeben eine leere, aber gültige Erklärung
  const e = liste[1].erklaerung
  assert.deepEqual([e.titel, e.kurz, e.darf.length, e.darf_nicht.length], ['', '', 0, 0])
})

test('UI-R8: Gruppenrollen-Reihenfolge ist Leitung vor Mitglied', () => {
  assert.deepEqual([...GRUPPENROLLEN_REIHENFOLGE], ['HV', 'MV', 'GL', 'Mitglied'])
})

// ── 3 · Fehlt die Quelle, wird es gesagt ───────────────────────────────────

test('UI-R8: ohne Quelle bleibt die Anzeige leer und sagt ehrlich warum', () => {
  for (const wert of [null, undefined, {}]) {
    const a = abschnitte(wert)
    assert.equal(a.leer, true)
    assert.deepEqual(a.systemrollen, [])
    assert.equal(a.gast, null)
  }
  assert.match(HINWEIS_OHNE_QUELLE, /nicht geladen/)
  assert.match(HINWEIS_OHNE_QUELLE, /unverändert/, 'muss sagen, dass die Rollen trotzdem gelten')
})

test('UI-R8b: der Ladefehler-Text nennt IMMER, dass die Rollen weiter gelten (Review R8-7)', () => {
  // Der Satz steht immer — ein nacktes „HTTP 500“ erklärt niemandem, dass
  // die Rollen trotzdem gelten.
  for (const fehler of [null, undefined, new Error(''), new Error('   ')]) {
    assert.equal(ladefehlerText(fehler), HINWEIS_OHNE_QUELLE)
  }
  // Ein Grund des Servers hängt ergänzend HINTEN dran, ersetzt den Satz nie.
  const mitGrund = ladefehlerText(new Error('HTTP 500'))
  assert.equal(mitGrund, `${HINWEIS_OHNE_QUELLE} (HTTP 500)`)
  assert.ok(mitGrund.startsWith(HINWEIS_OHNE_QUELLE), 'der Hinweis wird nicht ersetzt')
  // Auch ein reiner String oder ein Objekt ohne `message` geht nicht verloren.
  assert.equal(ladefehlerText('Netz weg'), `${HINWEIS_OHNE_QUELLE} (Netz weg)`)
  assert.equal(ladefehlerText({ message: ' Zeitüberschreitung ' }),
    `${HINWEIS_OHNE_QUELLE} (Zeitüberschreitung)`)
})

test('UI-R8: ⓘ nur für Rollen mit Erklärung — fehlende werden benannt', () => {
  const waehlbar = ['Mitglied', 'Tester', 'Kalenderadministrator', 'Mitglied']
  assert.deepEqual(erklaerteRollen(waehlbar, QUELLE.systemrollen).map((r) => r.name),
    ['Mitglied', 'Kalenderadministrator'])
  assert.deepEqual(fehlendeErklaerung(waehlbar, QUELLE.systemrollen), ['Tester'])
  // ohne Quelle gibt es keine ⓘs und keine falsche Beschwerde über 0 Rollen
  assert.deepEqual(erklaerteRollen(null, null), [])
  assert.deepEqual(fehlendeErklaerung(null, null), [])
})

// ── 4 · Barrierefreiheit des ⓘ ─────────────────────────────────────────────

test('UI-R8: ⓘ ist ein Knopf mit aria-label „Was bewirkt <Rolle>?“', () => {
  const baustein = lies('components/ui/RrInfo.vue')
  // UX1g2: eigenes <button> ist verboten — der ⓘ ist ein <DkButton>.
  assert.match(baustein, /<DkButton[\s\S]*?@click="umschalten"/, 'ⓘ muss ein DkButton sein')
  assert.ok(!/<button[\s>]/.test(baustein), 'kein eigener <button> (UX1g2)')
  assert.match(baustein, /Was bewirkt \$\{/, 'aria-label „Was bewirkt <Rolle>?“ fehlt')
  assert.match(baustein, /:aria-expanded=/, 'aufklappender Knopf braucht aria-expanded')
  assert.match(baustein, /aria-haspopup="dialog"/)
  // Popover schließt mit Escape — am Knopf UND im Panel.
  const escapes = baustein.match(/@keydown\.escape/g) || []
  assert.ok(escapes.length >= 2, 'Escape muss an Knopf und Popover hängen')
  assert.match(baustein, /role="dialog"/, 'Popover braucht eine Rolle mit Namen')
  assert.match(baustein, /tabindex="-1"/, 'Popover muss den Fokus aufnehmen können')
  // UI-R8b: eindeutige Kennung je Instanz statt Modulzähler.
  assert.match(baustein, /useId\(\)/, 'Kennung muss aus useId() kommen')
  assert.ok(!/let zaehler = 0/.test(baustein), 'Modulzähler statt useId()')
})

test('UI-R8b: weicht der Titel vom Rollennamen ab, nennt das aria-label BEIDE', () => {
  const baustein = lies('components/ui/RrInfo.vue')
  assert.match(baustein, /`Was bewirkt \$\{name\} \(\$\{titel\}\)\?`/,
    'aria-label „Was bewirkt <Rolle> (<Titel>)?“ fehlt')
  // Nur wenn beide gleich sind, bleibt es beim kurzen Satz.
  assert.match(baustein, /if \(!name \|\| name === titel\)/)
})

test('UI-R8: die Seite baut den Ladefehler-Text über die Funktion, nicht als Textkopie', () => {
  const seite = lies('pages/einstellungen/RollenRechte.vue')
  assert.match(seite, /ladefehlerText\(/, 'Fehlertext wird nicht aus der Funktion gebaut')
  assert.ok(!/\$\{HINWEIS_OHNE_QUELLE\}/.test(seite),
    'Fehlertext steht wieder als Vorlage in der Seite statt in der Funktion')
  // Kein toter Code mehr (Review R8-5): kein Prop `im-dialog`, kein
  // widersprüchliches `border-width: 0`.
  assert.ok(!/im-dialog/.test(seite), 'erfundenes Prop im-dialog')
  assert.ok(!/border-width:\s*0/.test(lies('components/ui/RrInfo.vue')), 'toter Rahmen-Code')
})

test('UI-R8: die ⓘ-Beschriftung nennt den Rollentitel, nicht die Kennung', () => {
  const baustein = lies('components/ui/RrInfo.vue')
  // `kopf` fällt auf den übergebenen Namen zurück, wenn der Titel fehlt.
  assert.match(baustein, /erklaerung\.value\.titel \|\| props\.name/)
})

test('UI-R8b: Kleinkram — kein `1px`, Numerus stimmt, keine eigene CSS-Zahl', () => {
  const seite = lies('pages/einstellungen/RollenRechte.vue')
  assert.ok(!/[^\w(-]1px solid/.test(seite), 'harter 1px-Rahmen statt Token')
  assert.match(seite, /border-inline-start:\s*var\(--rahmen-breite\) solid/, 'Rahmen ohne Token')
  // Numerus: Einzahl und Mehrzahl getrennt — „sie gelten … beschrieben ist sie“
  // war der Fehler.
  assert.match(seite, /ohneErklaerung\.length === 1/, 'kein Einzahl-Zweig')
  assert.match(seite, /die Rollen gelten wie jede andere; beschrieben sind sie noch nicht/)
  assert.match(seite, /die Rolle gilt wie jede andere; beschrieben ist sie noch nicht/)
})
