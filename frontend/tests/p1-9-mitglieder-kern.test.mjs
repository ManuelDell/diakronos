/**
 * P1-9 — Mitglieder-Kern (Frontend-Teil).
 *
 * Geprueft werden die Frontend-Anteile der Nachtbefunde:
 *
 *   UXD-R13  Mitgliederliste: „Importieren“/„⋯“ ohne Funktion entfernt,
 *            „Export“ liefert echte CSV.
 *   UXD-R14  Statusfilter aus den ECHTEN Status + „Alle“, Zähler aus der
 *            Server-Gesamtzahl, Abwählen möglich.
 *   UXD-R15  „Person anlegen“ legt ueber `create_mitglied` an (mit Prüfung) —
 *            die Maske selbst entsteht in N4.
 *   UXD-R8   maxlength=140 an Namens-/Adressfeldern; useApi wirft bei
 *            Nicht-JSON keinen Parse-Fehler.
 *   UXD-R24  Pflichtfeld-/E-Mail-Prüfung vor dem Senden.
 *   OP-ADMIN-8 Details zeigen Telefon/Geburtstag/Kommentar, Titel mit Name.
 *   OP-UI-13 Genehmigen/Ablehnen nach Bestätigungsfenster, kein prompt().
 *
 * P1-9b-Nacharbeit (Befunde 1/2/6/8/9):
 *   Befund 1  Sortierknopf A–Z/Z–A wieder funktionsfähig (toggleSortOrder).
 *   Befund 2  Export laeuft serverseitig ueber ALLE Zeilen und entschaerft
 *             Zellen (CSV-/Formel-Einschleusung).
 *   Befund 6  Dublettenhinweis beim Genehmigen kommt vom Server
 *             (`email_vorhanden`), keine 200er-Grenze im Browser mehr.
 *   Befund 8  Hinweistext nennt den echten Status („Passiver Gast“).
 *   Befund 9  Leerer Status wird nicht mehr gesendet.
 *
 * Die SFCs werden echt kompiliert (kein RegEx-Raten), laeuft im Image.
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse, compileScript, compileTemplate } from 'vue/compiler-sfc'

const wurzel = new URL('../src/', import.meta.url)
const lesen = (rel) => readFileSync(new URL(rel, wurzel), 'utf8')

function kompiliere(rel) {
  const quelle = lesen(rel)
  const { descriptor, errors } = parse(quelle, { filename: rel })
  assert.deepEqual(errors, [], rel + ': SFC-Struktur')
  const skript = compileScript(descriptor, { id: rel })
  const tpl = compileTemplate({
    source: descriptor.template.content,
    filename: rel,
    id: rel,
    compilerOptions: { bindingMetadata: skript.bindings || {} },
  })
  assert.deepEqual(tpl.errors.map((e) => e.message || String(e)), [], rel + ': Vue-Vorlage')
  return { quelle, descriptor, skriptText: descriptor.scriptSetup.content, template: descriptor.template.content }
}

// ── Mitglieder.vue: UXD-R13/R14/R15/R8 ─────────────────────────────────────

{
  const { template, skriptText } = kompiliere('diakonos/pages/Mitglieder.vue')

  // UXD-R13: kein funktionsloses „Importieren“ und kein „⋯“-Knopf mehr.
  assert.doesNotMatch(template, /Importieren/, 'kein „Importieren“-Knopf')
  assert.doesNotMatch(template, /alert\('Export-Funktion/, 'kein Platzhalter-Export')
  assert.doesNotMatch(template, /aria-label="Mehr"/, 'kein funktionsloser „⋯“-Knopf')
  assert.match(skriptText, /function exportCsv\(\)/, 'echter CSV-Export vorhanden')
  // P1-9b (Befund 2): Der Export holt den Server (alle Zeilen, Entschaerfung).
  assert.match(skriptText, /exportiere_mitglieder_csv/, 'Export laeuft ueber den Server')
  // N11: Die clientseitige Doppelsicherung `_csvZelleSicher` ist ENTFALLEN —
  // sie teilte die Serverdatei naiv an „;“ und zerlegte gequotete Zellen.
  // Der Server entschaerft und quotet (csv.writer); die Seite speichert die
  // Datei unveraendert.
  assert.doesNotMatch(skriptText, /_csvZelleSicher/, 'keine naive Zellteilung mehr (N11)')

  // Befund 1 (P1-9b): Der Sortierknopf A–Z/Z–A muss eine Funktion im Skript
  // haben, sonst ist er ein toter Knopf (bzw. Laufzeitfehler beim Klick).
  assert.match(template, /toggleSortOrder/, 'Sortierknopf im Template')
  assert.match(skriptText, /function toggleSortOrder\s*\(\s*\)/, 'toggleSortOrder im Skript')
  assert.match(
    skriptText,
    /sortOrder\.value = sortOrder\.value === 'asc' \? 'desc' : 'asc'/,
    'Sortierrichtung wird umgeschaltet'
  )

  // UXD-R14: echte Status + „Alle“.
  const statusZeile = skriptText.match(/const MT_STATUS = \[[^\]]*\]/)
  assert.ok(statusZeile, 'MT_STATUS definiert')
  for (const s of ['Mitglied', 'Gast', 'Passives Mitglied', 'Passiver Gast']) {
    assert.ok(statusZeile[0].includes(`'${s}'`), `Status ${s} im Filter`)
  }
  assert.doesNotMatch(statusZeile[0], /'Kind'|'Inaktiv'/, 'keine erfundenen Status')
  // N11: Die Zahl hinter „Alle“ ist die Server-Gesamtzahl OHNE Statusfilter
  // (`gesamt_alle`, UXD-R14); die Zahlen je Status kommen aus
  // `status_zaehler` des Servers (frueher aus den geladenen Zeilen — bei 30
  // Zeilen je Seite schlicht falsch). N11b/K1: „Alle“ nahm vorher `gesamt`
  // (die gefilterte Zahl) — bei aktivem Statusfilter stand dort „Alle 1“.
  assert.match(skriptText, /label: `Alle \$\{gesamtAlle\.value\}`/,
    '„Alle“ mit Gesamtzahl ohne Statusfilter')
  assert.match(skriptText, /function setStatusFilter/, 'Abwählen möglich')
  assert.match(skriptText, /statusZaehler\.value\[s\]/, 'Statuszahlen aus dem Server')
  assert.match(skriptText, /gesamt/, 'Zähler aus Server-Gesamtzahl')

  // UXD-R15: Die neue Maske „Mitglied hinzufügen“ entsteht in N4 auf Basis der
  // in P1-9 gehaerteten create_mitglied-Funktion — hier NICHT gebaut.
  assert.doesNotMatch(template, /title="Person anlegen"/, 'keine eigene Anlege-Maske in P1-9')

  // UXD-R14: Zähler kommen aus der Server-Gesamtzahl (`gesamt`), nicht aus
  // den geladenen Zeilen.
  assert.match(template, /\$\{gesamt\} Personen/, 'Kopfzeile zählt mit gesamt')
}

// ── useMitglieder.js: UXD-R14 Server-Gesamtzahl ────────────────────────────

{
  const quelle = lesen('diakonos/composables/useMitglieder.js')
  assert.match(quelle, /const gesamt = ref\(0\)/, 'gesamt-Ref vorhanden')
  assert.match(quelle, /payload\.total/, 'Gesamtzahl aus der Server-Antwort')
  assert.match(quelle, /gesamt: computed/, 'gesamt nach außen sichtbar')
  // hasMore orientiert sich an der Gesamtzahl.
  assert.match(quelle, /currentStart < gesamt\.value/, 'hasMore gegen Gesamtzahl')
}

// ── MitgliedDetail.vue: UXD-R6/R8/R24/UXD-R15 ──────────────────────────────

{
  const { template, skriptText } = kompiliere('diakonos/pages/MitgliedDetail.vue')

  assert.match(template, /maxlength="140"/, 'maxlength an den Feldern')
  assert.match(template, /label="Status"/, 'Statusfeld im Bearbeiten')
  assert.match(skriptText, /function _pruefeFormular/, 'Pflichtfeld-/E-Mail-Prüfung')
  assert.match(skriptText, /Pflichtfeld/, 'Pflichtfeldmeldung')
  // UXD-R6: das Geburtsdatum wird immer mitgesendet (leer loescht den Wert).
  const daten = skriptText.match(/function _formDaten\(\)[\s\S]*?\n\}/)
  assert.ok(daten, '_formDaten vorhanden')
  assert.match(daten[0], /geburtstag: editForm\.geburtstag \|\| ''/, 'geburtstag wird gesendet')
  // Befund 9 (P1-9b): ein LEERER Status wird nicht mitgesendet.
  assert.match(daten[0], /if \(status\) daten\.status = status/, 'leerer Status wird ausgelassen')
  // Befund 8 (P1-9b): der Hinweis nennt den echten Status, nicht „Ausgeschlossen“.
  assert.doesNotMatch(template, /<em>Ausgeschlossen<\/em>/, 'kein erfundener Status im Hinweis')
  assert.match(template, /Passiver Gast/, 'Hinweis nennt den echten Status')
}

// ── Registrierung.vue: OP-ADMIN-8 + OP-UI-13 ───────────────────────────────

{
  const { template, skriptText } = kompiliere('diakonos/pages/Registrierung.vue')

  // OP-ADMIN-8: keine rohe ID als Titel, Telefon/Geburtstag werden gezeigt.
  // N2 (Entscheidung 1): der Reiter heißt „Anfragen“ — deshalb lautet der
  // Fenstertitel „Anfrage von …“ statt „Anmeldung von …“ (das Wort
  // „Anmeldung“ bleibt dem Login vorbehalten, Standard S15).
  assert.doesNotMatch(template, /'Anmeldung ' \+ detailAnmeldung\.name/, 'Titel keine rohe ID')
  assert.match(template, /'Anfrage von '/, 'Titel mit Name')
  assert.match(template, /Geburtstag/, 'Geburtstag im Detail')

  // OP-UI-13: kein prompt()/confirm() in den Aufnehmen/Ablehnen-Wegen;
  // Bestätigungsfenster vorhanden. (Der separate Link-Löschen-Weg bleibt
  // unangetastet — nicht Teil dieses Befunds.) N2: „genehmigen“ heißt jetzt
  // „aufnehmen“ und öffnet ein Fenster mit Status-/Gruppenauswahl.
  const genBody = skriptText.match(/function aufnehmen\(a\)\s*\{[\s\S]*?\n\}/)
  const abBody = skriptText.match(/function ablehnen\(a\)\s*\{[\s\S]*?\n\}/)
  assert.ok(genBody && abBody, 'Aufnehmen-/Ablehnen-Wege gefunden')
  for (const [name, body] of [['aufnehmen', genBody[0]], ['ablehnen', abBody[0]]]) {
    const ohneKommentare = body.replace(/\/\/[^\n]*/g, '')
    assert.doesNotMatch(ohneKommentare, /prompt\(/, `kein prompt() in ${name}()`)
    assert.doesNotMatch(ohneKommentare, /\bconfirm\(/, `kein confirm() in ${name}()`)
  }
  assert.match(skriptText, /function aufnehmenBestaetigen/, 'Aufnehmen bestätigt')
  assert.match(skriptText, /function ablehnenBestaetigen/, 'Ablehnen bestätigt')
  // SEC-b (Fachentscheidung Manuel 2026-10-19): Eine E-Mail-Adresse gehört
  // höchstens zu EINER Person — das frühere `dublette_bestaetigt` ist
  // gegenstandslos und wird nicht mehr gesendet (Kommentare zählen nicht).
  assert.doesNotMatch(
    skriptText.replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/[^\n]*/g, ''),
    /dublette_bestaetigt/,
    'keine Dubletten-Bestätigung mehr',
  )
  // Befund 6 (P1-9b): der Dublettenhinweis kommt vom Server.
  assert.match(skriptText, /email_vorhanden/, 'server-seitiger Dublettenhinweis')
  assert.match(skriptText, /function emailDublette/, 'Hinweis wird aus der Antwort gelesen')
  assert.doesNotMatch(skriptText, /limit: 200/, 'keine 200er-Grenze im Browser mehr')
}

console.log('P1-9 Frontend: Mitgliederliste/Detail/Registrierung bestanden')
