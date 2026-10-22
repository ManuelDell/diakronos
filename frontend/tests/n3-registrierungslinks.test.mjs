import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { qrSvg, qrMatrix, qrDateiname, FEHLERKORREKTUR } from '../src/diakonos/components/registrierung/qr.mjs'

/**
 * N3 — Registrierungslinks: voller Link, Oeffnen, QR-Code.
 *
 * Teil 1 rechnet wirklich: der QR-Code wird aus der Adresse erzeugt (lokal,
 * ohne fremden Dienst) und die Matrix geprueft.
 * Teil 2 prueft die Verdrahtung der Linkkarte (Dateipruefung, wie bei N2):
 * voller Link, Kopieren/Teilen/Oeffnen, QR zeigen/PNG/Druck, Zustand und
 * Balken der Plaetze, Verlaengern-Dialog, kein natives confirm().
 */
const root = new URL('../src/diakonos/', import.meta.url)
const lies = (p) => readFileSync(new URL(p, root), 'utf8')

// ── Teil 1: QR-Code wirklich erzeugen ──────────────────────────────────────
{
  const link = 'https://dev.example.org/diakonos/registrierung?token=Xk3rT9aQ2w'
  const bild = qrSvg(link)
  assert.ok(bild.groesse >= 21, `QR-Groesse zu klein: ${bild.groesse}`)
  assert.equal(bild.viewBox, `0 0 ${bild.groesse} ${bild.groesse}`)
  assert.ok(bild.pfad.startsWith('M'), 'SVG-Pfad fehlt')
  assert.ok(bild.pfad.length > 100, 'SVG-Pfad zu kurz')

  const matrix = qrMatrix(link)
  assert.equal(matrix.length, bild.groesse)
  assert.equal(matrix[0].length, bild.groesse)
  // Die drei Suchermuster sitzen in den Ecken (jeweils 7x7, aussen beginnend).
  const ecke = (x0, y0) => {
    for (let y = 0; y < 7; y++) {
      for (let x = 0; x < 7; x++) {
        // Rahmen: aussen und innen schwarz, Ring dazwischen hell.
        const rand = x === 0 || x === 6 || y === 0 || y === 6
        const kern = x >= 2 && x <= 4 && y >= 2 && y <= 4
        assert.equal(matrix[y0 + y][x0 + x], rand || kern,
          `Suchermuster bei ${x0},${y0} + ${x},${y} falsch`)
      }
    }
  }
  ecke(0, 0)
  ecke(bild.groesse - 7, 0)
  ecke(0, bild.groesse - 7)

  // Fehlerkorrektur M (Aushaenge) — die Konstante ist nicht still veraendert.
  assert.equal(FEHLERKORREKTUR, 'M')

  // Ohne Inhalt kein Bild (kein leerer QR-Kasten).
  assert.equal(qrSvg('').pfad, '')
  assert.equal(qrSvg('   ').groesse, 0)

  // Dateiname ohne Sonderzeichen, mit Bezeichnung als Hinweis.
  assert.equal(qrDateiname('Gemeindefest 2026'), 'qr-gemeindefest-2026.png')
  assert.equal(qrDateiname('Größe & Würde / Test'), 'qr-groesse-wuerde-test.png')
  assert.equal(qrDateiname(''), 'qr-registrierungslink.png')

  // Zwei verschiedene Links ergeben verschiedene Codes.
  assert.notEqual(qrSvg(link).pfad, qrSvg(link + 'x').pfad)
}

// ── Teil 2: Linkkarte und Zustandsanzeige ─────────────────────────────────
{
  const teilen = lies('components/registrierung/RegLinkTeilen.vue')
  // Voller Link, sichtbar UND anklickbar.
  assert.ok(teilen.includes('class="dk-link-url"'), 'voller Link fehlt')
  assert.ok(/:href="vollerLink"/.test(teilen), 'Link ist nicht anklickbar')
  assert.ok(teilen.includes('new URL(roh, window.location.origin)'),
    'die Adresse wird nicht zur vollen Adresse ergaenzt')
  // Weitergabe: Kopieren, Teilen (Handy), Oeffnen, QR.
  for (const knopf of ['Kopieren', 'Teilen', 'Oeffnen', 'QR-Code zeigen']) {
    assert.ok(teilen.includes(knopf), `Knopf „${knopf}“ fehlt`)
  }
  assert.ok(teilen.includes('navigator.share'), 'Teilen nutzt die Geraete-Funktion')
  // QR: lokal gerechnet, PNG und Druck.
  assert.ok(teilen.includes('DkQrCode'), 'QR-Baustein fehlt')
  assert.ok(teilen.includes('QR herunterladen (PNG)'), 'PNG-Knopf fehlt')
  assert.ok(teilen.includes('QR drucken'), 'Druck-Knopf fehlt')
  assert.ok(teilen.includes("qr.mjs"), 'QR kommt nicht aus der eigenen Rechnung')
  assert.ok(!/api\.qrserver|chart\.googleapis|quickchart/.test(teilen),
    'kein fremder QR-Dienst')

  // Das QR-Bild: Schwarz auf Flaechenfarbe, und der Export findet es wieder.
  const qr = lies('components/registrierung/DkQrCode.vue')
  assert.ok(qr.includes('data-qr-svg'), 'data-qr-svg fuer den PNG-Export fehlt')
  assert.ok(qr.includes('shape-rendering="crispEdges"'), 'QR nicht scharfkantig')
  assert.ok(qr.includes('var(--surface)'), 'QR-Flaeche nutzt kein Token')

  // Karte im Unterbereich „Links & QR-Codes“.
  const reg = lies('pages/Registrierung.vue')
  const vorlage = reg.slice(0, reg.indexOf('<script setup>'))
  assert.ok(vorlage.includes('<RegLinkTeilen'), 'Linkkarte nicht eingebunden')
  assert.ok(vorlage.includes('zustandText(l)'), 'Zustand wird nicht angezeigt')
  assert.ok(vorlage.includes('plaetze_belegt'), 'belegte Plaetze fehlen')
  assert.ok(vorlage.includes('plaetze_gesamt'), 'Gesamtzahl der Plaetze fehlt')
  assert.ok(vorlage.includes('anfragen_offen'), 'offene Anfragen fehlen')
  assert.ok(vorlage.includes('reg-balken'), 'Balken der Plaetze fehlt')
  assert.ok(vorlage.includes("reg-karte-grau"), 'graue Karte fuer Abgelaufen/Voll fehlt')
  assert.ok(vorlage.includes('role="progressbar"'), 'Balken ohne Bedienhilfe-Auszeichnung')
  assert.ok(vorlage.includes('> Verlängern'), 'Knopf „Verlaengern“ fehlt')
  assert.ok(vorlage.includes('Gäste sehen nur Kalender und Profil'),
    'Hinweis fuer Gast-Links fehlt')

  // Kein natives confirm()/prompt() mehr; Loeschen fragt im App-Fenster nach.
  // Der Kommentar nennt confirm() nur, um zu begruenden, dass es NICHT benutzt
  // wird — geprueft wird deshalb auf den echten Aufruf (nicht im Kommentar).
  const ohneKommentare = reg
    .replace(/<!--[\s\S]*?-->/g, '')
    .split('\n').filter(z => !/^\s*(\/\/|\*|\/\*)/.test(z)).join('\n')
  assert.ok(!/(^|[^.\w])confirm\(/.test(ohneKommentare), 'natives confirm() in Registrierung.vue')
  assert.ok(!/(^|[^.\w])prompt\(/.test(ohneKommentare), 'natives prompt() in Registrierung.vue')
  assert.ok(reg.includes('function bestaetigen('), 'Bestaetigung im App-Fenster fehlt')
  assert.ok(reg.includes('Link löschen'), 'genaues Verb im Konfliktfenster fehlt')

  // Warnungen laufen ueber den globalen Toast (Warn-Stil vorhanden).
  assert.ok(reg.includes("from '../composables/useToast.js'"), 'useToast nicht eingebunden')
  assert.ok(!/function showToast\(/.test(reg), 'zweite Toast-Umsetzung in der Seite')
  assert.ok(!/reg-toast/.test(vorlage), 'eigener Toast-Baustein noch im Template')

  // Verlaengern ruft den Server-Endpunkt und nennt den Zustand danach.
  assert.ok(reg.includes('registrierungslink_api.verlaengern_link'), 'Verlaengern ohne Server')
  assert.ok(reg.includes('verlaengernDatum'), 'Feld fuer das neue Datum fehlt')
  assert.ok(reg.includes('verlaengernMax'), 'Feld fuer die Platzzahl fehlt')
  // R-N3-main-commits (wichtig 2): „Verlaengern“ schaltet den Link wieder ein
  // — das Fenster sagt es bei einem abgeschalteten Link.
  assert.ok(reg.includes('verlaengernFuer.inaktiv'), 'Hinweis fuer ausgeschaltete Links fehlt')
  assert.ok(reg.includes('wird er wieder'), 'Hinweistext zur Reaktivierung fehlt')

  // R-N3-main-commits (klein): Boolean-Prop als Binding, sonst gilt der
  // String "false" (truthy) und ein Klick daneben schliesst doch.
  const ohneRichtigesBinding = reg.replace(/:close-on-overlay="false"/g, '')
  assert.ok(!/(^|[^:])close-on-overlay="false"/.test(ohneRichtigesBinding),
    'close-on-overlay als String statt Binding')
  assert.ok(reg.includes(':close-on-overlay="false"'), 'close-on-overlay nicht als Binding')

  // Zustandswechsel aus dem Server, keine eigene Nachrechnung.
  assert.ok(!/const zustand\s*=\s*computed/.test(reg),
    'die Seite rechnet den Zustand selbst statt ihn zu lesen')
}

// ── Teil 3: Nachtraege aus R-N2-code (Operator-Nachtrag, Paket N3) ────────
{
  const reg = lies('pages/Registrierung.vue')

  // M2: Verweigert der Server das Aufnehmen, wird die Liste neu geladen und
  // das Fenster mit dem Grund wieder geoeffnet.
  assert.ok(reg.includes('const aufnehmenFehler = ref(\'\')'),
    'Feld fuer den Fehlergrund fehlt (M2)')
  assert.ok(/catch[\s\S]{0,600}await fetchData\(\)[\s\S]{0,400}aufnehmenFuer\.value = \{/.test(reg),
    'im Fehlerfall wird nicht neu geladen und das Fenster nicht wieder geoeffnet (M2)')
  assert.ok(reg.includes('aufnehmenFehler.value = err?.message'),
    'der Servergrund landet nicht im Fenster (M2)')

  // H1a: Kachel „Personen“ -> Filter aus der Adresse, auch auf „Alle“.
  const liste = lies('pages/Mitglieder.vue')
  assert.ok(liste.includes('statusFilter.value = _statusAusAdresse()'),
    'Statusfilter kommt nicht aus der Adresse (H1)')

  // H1b: die Fenster-Ereignisse der Bibliothek werden mit ihrer Funktion
  // abgemeldet (nicht mit `null`).
  const org = lies('components/gruppen/OrganigrammAnsicht.vue')
  assert.ok(org.includes('fensterBindungen.push([ziel, typ, rest[0]])'),
    'Zuhoerer-Funktion wird nicht mitprotokolliert (H1)')
  assert.ok(org.includes('ziel.removeEventListener(typ, fn)'),
    'Abmeldung ohne Zuhoerer-Funktion entfernt nichts (H1)')
  // Kommentare nennen `removeEventListener(typ, null)` nur als Begruendung —
  // geprueft wird der echte Aufruf im Code.
  const orgOhneKommentare = org
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .split('\n').filter(z => !/^\s*(\/\/|\*)/.test(z)).join('\n')
  assert.ok(!/removeEventListener\([^)]*,\s*null\)/.test(orgOhneKommentare),
    'removeEventListener(..., null) entfernt nichts (H1)')

  // H1c: die Abmeldung wird WIRKLICH ausgefuehrt — echter Lauf gegen ein
  // nachgebildetes Fenster/Dokument. Die beiden Funktionen werden aus der
  // Quelldatei geschnitten und mit einem Zaehler-Ziel ausgewertet.
  const quelle = org.slice(org.indexOf('const FENSTER_EREIGNISSE'),
    org.indexOf('\nonBeforeUnmount('))
  const zaehler = { add: 0, remove: 0, offen: 0 }
  const machZiel = (n) => ({
    addEventListener(t, f) { zaehler.add++; zaehler.offen++; zaehler[n] = (zaehler[n] || 0) + 1 },
    removeEventListener(t, f) { zaehler.remove++; zaehler.offen-- },
  })
  const fenster = machZiel('w')
  const dokument = machZiel('d')
  // Die geschnittenen Funktionen greifen auf die globalen Ziele zu — fuer die
  // Dauer des Laufs werden sie gesetzt und danach wieder entfernt.
  globalThis.window = fenster
  globalThis.document = dokument
  try {
    const lade = new Function('window', 'document', `${quelle}\nglobalThis.__p = { merkeFensterBindungen, loeseFensterBindungen }`)
    lade(fenster, dokument)
    // Ein Bibliotheks-Render meldet zwei Fenster- und ein Dokument-Ereignis an.
    globalThis.__p.merkeFensterBindungen(() => {
      window.addEventListener('resize.ID42', () => {})
      window.addEventListener('scroll.ID42', () => {})
      document.addEventListener('fullscreenchange.ID42', () => {})
    })
    assert.equal(zaehler.add, 3, 'Anmeldungen nicht protokolliert')
    globalThis.__p.loeseFensterBindungen()
    assert.equal(zaehler.remove, 3, 'Abmeldungen nicht ausgefuehrt')
    assert.equal(zaehler.offen, 0, 'Zuhoerer blieben angemeldet (H1)')
  } finally {
    delete globalThis.window
    delete globalThis.document
    delete globalThis.__p
  }
}

console.log('N3 Registrierungslinks: bestanden')
