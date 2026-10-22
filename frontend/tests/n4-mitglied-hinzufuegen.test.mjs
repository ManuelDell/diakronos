import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

/**
 * N4 — Dialog „Mitglied hinzufügen“ (ohne Zugang).
 *
 * Prüft den Dialog gegen das Neuordnungs-Konzept (Abschnitt 4):
 *  - Pflichtfelder Vorname/Nachname, dazu E-Mail, Status und optionale Gruppe,
 *  - Dublettenprüfung BEIM TIPPEN über den Server (gleiche E-Mail blockiert,
 *    gleicher Name warnt nur),
 *  - Zugang ausdrücklich „kein Zugang“ (`create_user: false`) — die
 *    Passwort-Wege kommen erst mit N5,
 *  - angelegt wird über das gehärtete `create_mitglied`, Fehler bleiben im
 *    Dialog stehen (kein flüchtiger Toast),
 *  - der Kopf-Knopf von „Mitglieder“ öffnet den Dialog statt in die
 *    Anmeldungen zu springen,
 *  - Bedienung über das Design-System (DkDialog/DkField/DkHint), keine
 *    festen Farben.
 *
 * Läuft als Dateiprüfung (kein Vue-Compiler): die Dateien werden als Text
 * gelesen — wie n1/n2/n3.
 */
const root = new URL('../src/diakonos/', import.meta.url)
const lies = p => readFileSync(new URL(p, root), 'utf8')

const dialog = lies('components/mitglieder/MitgliedHinzufuegenDialog.vue')
const dVorlage = dialog.slice(0, dialog.indexOf('<script setup>'))
const dSkript = dialog.slice(dialog.indexOf('<script setup>'))
const bereich = lies('pages/mitglieder/Bereich.vue')
const bSkript = bereich.slice(bereich.indexOf('<script setup>'))

/** Quellblock einer `const <name> = …`-Deklaration bis zur Leerzeile. */
function block(text, name) {
  const start = text.indexOf(`const ${name}`)
  assert.ok(start >= 0, `Deklaration ${name} fehlt`)
  const ende = text.indexOf('\n\n', start)
  return text.slice(start, ende === -1 ? undefined : ende)
}

// ── Kopf-Knopf öffnet den Dialog (nicht mehr die Anmeldungen) ──────────────
{
  assert.ok(bereich.includes('MitgliedHinzufuegenDialog'), 'Bereich bindet den Dialog ein')
  assert.ok(bereich.includes('const hinzufuegenOffen = ref(false)'), 'Sichtbarkeit als Ref')
  assert.ok(bereich.includes('v-model="hinzufuegenOffen"'), 'Dialog wird über v-model gesteuert')
  const fnStart = bSkript.indexOf('function mitgliedHinzufuegen')
  assert.ok(fnStart >= 0, 'Funktion mitgliedHinzufuegen vorhanden')
  const fn = bSkript.slice(fnStart, bSkript.indexOf('\n}', fnStart) + 2)
  assert.ok(fn.includes('hinzufuegenOffen.value = true'), 'Knopf öffnet den Dialog')
  assert.ok(
    !bSkript.includes("navigate('#/mitglieder/anfragen')"),
    'kein Sprung mehr in die Anmeldungen',
  )
}

// ── Pflichtfelder und Feldsatz (Konzept Abschnitt 4, Schritt 1) ────────────
{
  for (const feld of ['vorname', 'nachname', 'email', 'status', 'gruppe']) {
    assert.ok(dSkript.includes(`form.${feld}`), `Feld ${feld} im Formular`)
  }
  assert.ok(dVorlage.includes('label="Vorname" required'), 'Vorname ist Pflichtfeld')
  assert.ok(dVorlage.includes('label="Nachname" required'), 'Nachname ist Pflichtfeld')
  const speicherbar = block(dSkript, 'speicherbar')
  assert.ok(speicherbar.includes('form.vorname.trim()'), 'Speichern braucht Vornamen')
  assert.ok(speicherbar.includes('form.nachname.trim()'), 'Speichern braucht Nachnamen')
  // Echte Statuswerte aus mitglieder.MITGLIED_STATUS.
  assert.ok(dSkript.includes("'Passives Mitglied'"), 'echter Status „Passives Mitglied“')
  assert.ok(dSkript.includes("'Passiver Gast'"), 'echter Status „Passiver Gast“')
  // Gruppenauswahl kommt vom Aufrufer (dieselbe Quelle wie überall).
  assert.ok(dSkript.includes('props.gruppen'), 'Gruppenauswahl über Props (Komfort)')
}

// ── Dublettenprüfung beim Tippen (UXD-R15) ─────────────────────────────────
{
  assert.ok(dSkript.includes("'pruefe_mitglied_dublette'"), 'Serverprüfung beim Tippen')
  assert.ok(dVorlage.includes('@blur="dublettePruefen"'), 'Prüfung beim Verlassen der Felder')
  const blockiert = block(dSkript, 'dubletteBlockiert')
  assert.ok(blockiert.includes("grund === 'email'"), 'gleiche E-Mail blockiert')
  // Nur die E-Mail blockiert das Speichern, der Name warnt lediglich.
  const speicherbar = block(dSkript, 'speicherbar')
  assert.ok(speicherbar.includes('dubletteBlockiert'), 'Blockade fließt in „speicherbar“ ein')
  assert.ok(dVorlage.includes(":variant=\"dubletteBlockiert ? 'err' : 'warn'\""), 'Warnstufe je Grund')
}

// ── Zugang ausdrücklich „kein Zugang“ (N4, ohne Passwort-Wege) ─────────────
{
  assert.ok(/create_user:\s*false/.test(dSkript), 'create_user: false (kein Zugang)')
  assert.ok(!dSkript.includes('create_user: true'), 'kein Zugang wird hier nicht erzeugt')
  // Keine Passwort-/Einladungs-Optionen in der Oberfläche — die bringt erst N5.
  // (Kommentare und der CSS-Klassenname „mh-link“ zählen nicht.)
  const sichtbar = dVorlage + (dSkript.match(/const statusOptionen[\s\S]*?const gruppeOptionen/) || [''])[0]
  // N5 erweitert N4: „kein Zugang“ bleibt wählbar, Link ist Standard.
  assert.ok(dVorlage.includes('value="kein"'), 'kein Zugang weiterhin wählbar')
  assert.ok(dSkript.includes("const zugangsart = ref('link')"), 'Einladungslink vorausgewählt')
  assert.ok(dSkript.includes("zugangsart: modus.value ? 'kein' : zugangsart.value"),
    'Authentik legt ausschließlich einen Eintrag an')
  assert.ok(dVorlage.includes('autocomplete="new-password"'), 'Startpasswort verdeckt eingeben')
}

// ── Anlegen über das gehärtete create_mitglied, Fehler bleiben stehen ──────
{
  assert.ok(dSkript.includes("'create_mitglied'"), 'Anlegen ruft create_mitglied')
  assert.ok(dSkript.includes('gruppe_id: form.gruppe'), 'Gruppe geht an den Server')
  assert.ok(dSkript.includes('fehler.allgemein = err?.message'), 'Serverfehler bleibt im Dialog')
  assert.ok(dVorlage.includes('v-if="fehler.allgemein"'), 'Fehler wird angezeigt')
  assert.ok(dSkript.includes("emit('angelegt'"), 'Erfolg wird dem Rahmen gemeldet')
  assert.ok(bereich.includes('@angelegt="nachAnlegen"'), 'Rahmen lädt die Liste nach')
  assert.ok(bereich.includes('typeof ziel.reload'), 'Nachladen nutzt die Listen-Ref')
}

// ── Backend: Endpunkt existiert (nur der Name, keine Dateiprüfung) ─────────
// Die vollständige Prüfung des Endpunkts läuft in
// backend/tests/test_n4_mitglied_dublette.py — diese Datei prüft nur die
// Oberfläche und darf im Image (ohne backend/-Quellbaum) laufen.
assert.ok(
  dSkript.includes("'pruefe_mitglied_dublette'"),
  'Dialog fragt den Server nach Dubletten',
)

// ── Design-System, keine festen Farben ─────────────────────────────────────
{
  for (const bez of ['DkDialog', 'DkButton', 'DkField', 'DkSelect', 'DkHint']) {
    assert.ok(dialog.includes(bez), `Baustein ${bez} verwendet`)
  }
  const farben = dialog.match(/#[0-9a-fA-F]{3,8}\b|rgb\(|hsl\(/g)
  assert.equal(farben, null, 'keine festen Farbwerte (nur var(--…))')
}

console.log('N4 Dialog Mitglied hinzufügen: bestanden')
