import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

/**
 * N2 — Reiter „Anfragen“ (Registrierung zieht um).
 *
 * Prüft die Struktur des Anfragen-Reiters gegen das Neuordnungs-Konzept
 * (Abschnitt 3, Reiter 3):
 *  - zwei Leitern: Status (Offen mit Zähler / Aufgenommen / Abgelehnt) und
 *    Unterbereiche (Anfragen / Links & QR-Codes / Formulare),
 *  - die Liste nennt Datum, Name, Art, Hinweis und Status,
 *  - „Aufnehmen“ ist kein Ein-Klick-Vorgang: Dialog mit Status- und
 *    Gruppenauswahl (OP-ADMIN-7),
 *  - die Dublettenwarnung stammt aus dem Server (`email_vorhanden`), nicht aus
 *    einer im Browser gekappten Mitgliederliste,
 *  - „Ablehnen“ läuft im App-Fenster (kein natives prompt()),
 *  - die Titel der Fenster nennen „Anfrage …“ statt „Anmeldung“.
 *
 * Läuft als Dateiprüfung (kein Vue-Compiler): die Datei wird als Text gelesen.
 */
const root = new URL('../src/diakonos/', import.meta.url)
const lies = p => readFileSync(new URL(p, root), 'utf8')
const reg = lies('pages/Registrierung.vue')
const vorlage = reg.slice(0, reg.indexOf('<script setup>'))
const skript = reg.slice(reg.indexOf('<script setup>'))

/** Quellblock einer `const <name> = …`-Deklaration bis zum Zeilenende des Aufrufs. */
function block(name) {
  const start = skript.indexOf(`const ${name}`)
  assert.ok(start >= 0, `Deklaration ${name} fehlt`)
  const ende = skript.indexOf('\n\n', start)
  return skript.slice(start, ende === -1 ? undefined : ende)
}

// ── Statusleiter mit Zähler ─────────────────────────────────────────────────
{
  const statusTabs = block('statusTabs')
  assert.ok(skript.includes("const statusTab = ref('offen')"), 'Statusleiter beginnt bei „Offen“')
  assert.ok(statusTabs.includes('Offen (${zaehle('), '„Offen“ traegt einen Zähler')
  // W1: das Glossar ersetzt „Genehmigt“ auf der Statusleiter durch
  // „Aufgenommen“ — der gespeicherte Kennwert bleibt `genehmigt`.
  assert.ok(statusTabs.includes("label: 'Aufgenommen'"), 'Statusreiter Aufgenommen')
  assert.ok(statusTabs.includes('Abgelehnt'), 'Statusreiter Abgelehnt')
}

// ── Unterbereiche ──────────────────────────────────────────────────────────
{
  const unter = block('unterbereiche')
  assert.ok(skript.includes("const unterbereich = ref('anfragen')"), 'Unterbereich beginnt bei Anfragen')
  assert.ok(unter.includes("'anfragen'"), 'Unterbereich Anfragen')
  assert.ok(unter.includes('Links & QR-Codes'), 'Unterbereich Links & QR-Codes')
  assert.ok(unter.includes('Formulare'), 'Unterbereich Formulare')
}

// ── Liste: Datum/Name/Art/Hinweis/Status ───────────────────────────────────
for (const spanne of ['Datum', 'Name', 'Art', 'Hinweis', 'Status']) {
  assert.ok(skript.includes(`label: '${spanne}'`), `Spalte ${spanne}`)
}

// ── Aufnehmen-Dialog mit Status und Gruppe (OP-ADMIN-7) ────────────────────
{
  assert.ok(vorlage.includes('aufnehmenFuer'), 'Aufnehmen-Dialog vorhanden')
  assert.ok(skript.includes('const aufnehmenStatus'), 'Statusauswahl im Aufnehmen-Dialog')
  assert.ok(skript.includes('const aufnehmenGruppe'), 'Gruppenauswahl im Aufnehmen-Dialog')
  assert.ok(block('statusOptionen').includes("value: 'Passives Mitglied'"), 'echte Statuswerte (MITGLIED_STATUS)')
  assert.ok(block('gruppeOptionen').includes('gruppenAuswahl'), 'Gruppenoptionen aus der API')
  assert.ok(skript.includes('get_gruppen_page_data'), 'Gruppenliste kommt aus der Gruppen-Ansicht')
  assert.ok(skript.includes('status: aufnehmenStatus.value'), 'Status geht an den Server')
  assert.ok(skript.includes('gruppe: aufnehmenGruppe.value'), 'Gruppe geht an den Server')
  assert.ok(skript.includes('genehmige_anmeldung'), 'Aufnehmen ruft den Server-Endpunkt')
  // Kein Ein-Klick-Vorgang mehr: der frühere direkte Aufruf ohne Dialog ist weg.
  assert.ok(!/async function genehmigen\(/.test(reg), 'kein Ein-Klick-Genehmigen mehr')
}

// ── Dublettenwarnung aus dem Server (OP-ADMIN-7) ───────────────────────────
assert.ok(skript.includes('email_vorhanden'), 'Dublettenhinweis aus `email_vorhanden`')
assert.ok(vorlage.includes('E-Mail schon vorhanden'), 'verständlicher Hinweistext in der Zeile')

// ── Details vollständig und Titel mit Namen (OP-ADMIN-8) ───────────────────
assert.ok(vorlage.includes('detailAnmeldung.telefon'), 'Telefon in den Details')
assert.ok(vorlage.includes('detailAnmeldung.geburtstag'), 'Geburtstag in den Details')
assert.ok(vorlage.includes('detailAnmeldung.kommentar'), 'Kommentar in den Details')
assert.ok(vorlage.includes("'Anfrage von '"), 'Fenstertitel nennt „Anfrage von …“ statt roher ID')

// ── Ablehnen im App-Fenster (kein natives prompt()) ────────────────────────
assert.ok(!skript.includes('prompt('), 'kein natives prompt() mehr')
assert.ok(skript.includes('ablehnenFuer'), 'Ablehnen-Dialog vorhanden')
assert.ok(vorlage.includes('Ablehnen'), 'Ablehnen-Knopf vorhanden')

// ── Kopf und Reiter kommen weiter aus dem Design-System ────────────────────
for (const bez of ['DkPageHeader', 'DkTabs', 'DkSegment', 'DkCard', 'DkTable', 'DkDialog']) {
  assert.ok(reg.includes(bez), `Baustein ${bez} verwendet`)
}
// Eingebettet im Mitglieder-Rahmen: kein zweiter Kopf.
assert.ok(reg.includes('v-if="!embedded"'), 'Kopf nur im Standalone-Betrieb')

console.log('N2 Anfragen: bestanden')
