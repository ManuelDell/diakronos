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
// Vorlage ohne Kommentare: die Erklärungen nennen dieselben Bausteine und
// haben den Test schon einmal getäuscht (Vorbild uxa2a-bereichsliste).
const vorlage = reg.slice(0, reg.indexOf('<script setup>')).replace(/<!--[\s\S]*?-->/g, '')
const skript = reg.slice(reg.indexOf('<script setup>'))

/** Quellblock einer `const <name> = …`-Deklaration bis zum Zeilenende des Aufrufs. */
function block(name) {
  const start = skript.indexOf(`const ${name}`)
  assert.ok(start >= 0, `Deklaration ${name} fehlt`)
  const ende = skript.indexOf('\n\n', start)
  return skript.slice(start, ende === -1 ? undefined : ende)
}

// ── Statusleiter als Filter über der Tabelle (UX-A2b, UX3j-Nacharbeit) ─────
// UX-A2b (Entwurf A2, Befunde DMB-09a956e8457d + DMB-d4f788c04158): Die
// Status-Reiter „Offen · Aufgenommen · Abgelehnt“ standen ÜBER den
// Unterbereichen und filterten deshalb auch bei „Links“ und „Formularen“ —
// dort ohne Wirkung. Jetzt steht der Statusfilter MIT ZAHLEN direkt über der
// Anfragen-Tabelle. UX3j-Nacharbeit (Punkt 1): derselbe Baustein wie Liste
// und Datenschutz (DkSegment) mit derselben Zähler-Schreibweise — die
// dunkel gefüllte Chip-Zeile (DkFilterChips) ist entfallen.
{
  assert.ok(skript.includes("const statusFilter = ref('offen')"), 'Statusfilter beginnt bei „Offen“')
  const leiter = block('STATUS_LEITER')
  assert.ok(leiter.includes("label: 'Offen'"), 'Eintrag Offen')
  assert.ok(leiter.includes("label: 'Aufgenommen'"), 'Eintrag Aufgenommen')
  assert.ok(leiter.includes("label: 'Abgelehnt'"), 'Eintrag Abgelehnt')
  // Die Zahl je Eintrag kommt aus derselben Zählung wie der Filter und steht
  // in derselben Schreibweise wie in Liste und Datenschutz („Wort Zahl“).
  assert.ok(block('statusFilterOptionen').includes('label: `${s.label} ${zaehle(s.wert)}`'),
    'Filter trägt die Zahlen („Offen 3“)')
  assert.ok(skript.includes('const statusFilterOptionen = computed'), 'Filterzeile ist berechnet')
  // Nur über der Tabelle: innerhalb des Anfragen-Unterbereichs, vor der Karte.
  // UX3j: Der Kopf der Seite nennt die Unterbereiche (Links/Formulare als
  // Primärknopf) — gesucht wird deshalb der INHALTS-Block mit `<div v-if>`.
  const anfragenBlock = vorlage.slice(
    vorlage.indexOf("<div v-if=\"unterbereich === 'anfragen'\""),
    vorlage.indexOf("<div v-if=\"unterbereich === 'links'\""),
  )
  assert.ok(anfragenBlock.includes('<DkSegment'), 'Filterzeile im Anfragen-Bereich')
  assert.ok(anfragenBlock.indexOf('<DkSegment') < anfragenBlock.indexOf('<DkCard'),
    'Filterzeile steht ÜBER der Tabelle')
  // Kein Statusfilter bei Links und Formularen (je eigener Block ohne Chips).
  for (const [von, bis] of [["'links'", "'formulare'"], ["'formulare'", null]]) {
    const anfang = vorlage.indexOf(`<div v-if="unterbereich === ${von}"`)
    assert.ok(anfang > 0, `Unterbereich ${von} vorhanden`)
    const ende = bis ? vorlage.indexOf(`<div v-if="unterbereich === ${bis}"`) : vorlage.length
    assert.ok(!vorlage.slice(anfang, ende).includes('DkSegment'),
      `kein Statusfilter bei ${von}`)
  }
  // Die alte Reiterzeile ist fort: kein DkTabs mehr auf dieser Seite.
  assert.ok(!reg.includes('DkTabs'), 'die Status-Reiterzeile (DkTabs) ist entfallen')
  assert.ok(reg.includes("import DkSegment from '../components/ui/DkSegment.vue'"),
    'Filter-Baustein eingebunden (derselbe wie Liste/Datenschutz)')
  // Der Filter fährt die Liste.
  assert.ok(block('filteredAnmeldungen').includes('statusFilter.value'),
    'die Tabelle richtet sich nach dem Statusfilter')
}

// ── Dieselbe Sprache in Tabelle, Detailfenster und Filtern (UX-A2b) ────────
{
  const sprache = block('ANMELDESTATUS_SPRACHE')
  for (const wort of ['Offen', 'Aufgenommen', 'Abgelehnt']) {
    assert.ok(sprache.includes(`wort: '${wort}'`), `Statussprache nennt „${wort}“`)
  }
  // Die rohen Server-Werte bleiben der Schlüssel — die Anzeige ist übersetzt.
  for (const roh of ['Anmeldeanfrage', 'Ausstehend', 'Bestätigt', 'Abgelehnt']) {
    assert.ok(sprache.includes(`'${roh}'`), `Schlüssel „${roh}“`)
  }
  assert.ok(vorlage.includes('statusSprache(a.status).wort'), 'Tabelle zeigt die Statussprache')
  assert.ok(!vorlage.includes('{{ a.status }}'), 'Tabelle zeigt nicht mehr den rohen Status')
  assert.ok(vorlage.includes('statusSprache(detailAnmeldung.status).wort'),
    'Detailfenster zeigt dieselbe Sprache')
  assert.ok(!skript.includes('function statusVariante'), 'die alte zweite Wortliste ist entfernt')
  // Die Spalte heisst „Typ“ (wie in der Vorlage), nicht „Art“.
  assert.ok(skript.includes("label: 'Typ'"), 'Spalte Typ')
  assert.ok(!skript.includes("label: 'Art'"), 'Spalte „Art“ ist entfallen')
  assert.ok(vorlage.includes('artText(a.anmeldungstyp)'), 'Typ in Klartext statt Rohwert')
  const typen = block('ANMELDETYP_SPRACHE')
  assert.ok(typen.includes("'Mitglied-Registrierung': 'Mitglied'"), 'Mitglied-Registrierung → Mitglied')
  assert.ok(typen.includes("'Gast-Anmeldung': 'Gast'"), 'Gast-Anmeldung → Gast')
}

// ── Unterbereiche ──────────────────────────────────────────────────────────
// UX3j (Entwurf A3): Die Unterbereiche stehen als ZWEITE, kleinere Reiterzeile
// direkt unter der Reiterzeile — gezeichnet vom Rahmen (`pages/Personen.vue`,
// menue.js `personenAnfragenReiter`). Diese Seite bringt KEINEN eigenen
// Umschalter mehr mit; der Unterbereich kommt über die Eigenschaft herein und
// steht in der Adresse (`#/personen/anfragen[/<unter>]`).
{
  const unter = block('UNTERBEREICHE')
  assert.ok(!skript.includes('unterbereichLokal'), 'kein eigener Umschalter mehr (A3)')
  // Kein eigener UMSCHALTER für die Unterbereiche — der Statusfilter der
  // Tabelle IST ein DkSegment (UX3j-Nacharbeit Punkt 1) und bleibt erlaubt.
  assert.ok(!/:options="unterReiterOptionen"/.test(vorlage),
    'keine zweite Reiterzeile in der Seite')
  assert.ok(!/:options="UNTERBEREICHE"/.test(vorlage),
    'kein Unterbereichs-Umschalter in der Seite')
  assert.ok(unter.includes("'anfragen'"), 'Unterbereich Anfragen')
  assert.ok(unter.includes('Links & QR-Codes'), 'Unterbereich Links & QR-Codes')
  assert.ok(unter.includes('Formulare'), 'Unterbereich Formulare')
  assert.ok(skript.includes("unterbereich: { type: String, default: '' }"),
    'Unterbereich kommt über die Eigenschaft herein')
  // UX3j: Steht die Seite allein (embedded = false, z. B. alte Adresse
  // #/registrierung), trägt sie ihren eigenen Kopf — die Unterbereichs-Wahl
  // bleibt beim Rahmen, hier gibt es dafür keinen Umschalter.
  assert.ok(!skript.includes("emit('unterbereich-wechsel'"),
    'kein Wechsel-Ereignis an den Rahmen')
  assert.match(vorlage, /<DkPageHeader v-if="!embedded"/, 'eigener Kopf nur ohne Rahmen')
}

// ── Liste: Datum/Name/Typ/Hinweis/Status ───────────────────────────────────
for (const spanne of ['Datum', 'Name', 'Typ', 'Hinweis', 'Status']) {
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
// UX-A2b: DkTabs ist entfallen (der Statusfilter ist eine Chip-Zeile).
// UX3j: Die Unterbereichs-Wahl zeichnet der Rahmen (`DkReiter` in
// pages/Personen.vue); diese Seite hat keinen Umschalter für die Unterbereiche
// mehr. Der STATUSFILTER ist seit der UX3j-Nacharbeit (Punkt 1) ein DkSegment
// — dieselbe Optik wie in Liste und Datenschutz, kein DkFilterChips mehr.
for (const bez of ['DkPageHeader', 'DkSegment', 'DkCard', 'DkTable', 'DkDialog']) {
  assert.ok(reg.includes(bez), `Baustein ${bez} verwendet`)
}
// Eingebettet im Mitglieder-Rahmen: kein zweiter Kopf.
assert.ok(reg.includes('v-if="!embedded"'), 'Kopf nur im Standalone-Betrieb')

console.log('N2 Anfragen: bestanden')
