/**
 * P1-10 — Lieder & Material (Frontend-Teil).
 *
 * Geprueft werden die Frontend-Anteile der Nachtbefunde:
 *
 *   UXM-R1   Lied speichern: Kategorien/Anlaesse als Auswahl (Optionen laden),
 *            Hilfetexte ohne falsche Beispiele (Lob/Chorprobe).
 *   UXM-R4   Lied-Detail: Material „Öffnen“ nutzt die Datei-URL
 *            (datei.datei_url), nicht die interne Anhang-Kennung (404).
 *   UXM-R7   Material „Hochladen“ ohne Plantyp möglich (kein stummer Abbruch).
 *   UXM-R8   Material „Entfernen“ sendet die Kennung der Material-Zeile.
 *   UXM-R9   Liedgruppen anlegen/bearbeiten/löschen + Liedzuordnung.
 *   UXM-R10  Liedgruppe-Detail zeigt den Titel statt der internen Kennung.
 *   UXM-R16  beforeunload-Warnung bei ungespeicherten Eingaben.
 *   UXM-R17  Dublettenwarnung vor dem Anlegen.
 *   OP-UI-4  Fokussieren/Scrollen zum ersten fehlerhaften Feld.
 *   OP-HANDY-13 Lieder-Suche: Filterblatt, Kartenliste, Suchbegriff in ?q=.
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
  return { quelle, template: descriptor.template.content, skriptText: descriptor.scriptSetup.content }
}

// ── LiedBearbeiten.vue: UXM-R1/R7/R8/R16/R17 + OP-UI-4 ─────────────────────

{
  const { template, skriptText } = kompiliere('diakonos/components/lieder/LiedBearbeiten.vue')

  // UXM-R1: Kategorien/Anlässe-Vorschläge werden geladen (nicht mehr leer).
  assert.match(skriptText, /function optionenLaden\s*\(/, 'Optionsladen vorhanden')
  assert.match(skriptText, /get_lied_filteroptionen/, 'Optionen kommen vom Server')
  assert.match(skriptText, /kategorienVorschlaege\.value = opt\?\.kategorien/, 'Kategorien gefüllt')
  // Falsche Hilfe-Beispiele sind weg.
  assert.doesNotMatch(template, /z\. B\. Lob, Abendmahl/, 'kein falsches Kategorie-Beispiel')
  assert.doesNotMatch(template, /Chorprobe/, 'kein falsches Anlass-Beispiel')

  // UXM-R7: Upload ohne Plantyp; kein stummer Abbruch.
  assert.doesNotMatch(
    skriptText, /if \(!upload\.datei \|\| !props\.plantyp \|\| !form\.name\) return/,
    'kein stummer Plantyp-Abbruch mehr'
  )
  assert.match(skriptText, /liedMaterialHinzufuegen\(props\.plantyp \|\| null/, 'Upload ohne Plantyp')

  // UXM-R8: Entfernen sendet die Zeilen-Kennung m.material.
  assert.match(skriptText, /m\.material/, 'Material-Kennung verwendet')
  assert.match(skriptText, /const zeile = m\.material/, 'Zeile = Materialkennung')

  // UXM-R16: beforeunload-Warnung.
  assert.match(skriptText, /beforeunload/, 'beforeunload registriert')
  assert.match(skriptText, /function vorSeitenverlassen/, 'Handler vorhanden')

  // Befund 4 (P1-10b): neue Katalogbegriffe werden im Chip als "neu" gekennzeichnet.
  assert.match(skriptText, /function istNeuerBegriff\s*\(/, 'Neu-Erkennung vorhanden')
  assert.match(template, /istNeuerBegriff\(k, 'kategorie'\)/, 'Kategorie-Chip kennzeichnet neu')
  assert.match(template, /istNeuerBegriff\(a, 'anlass'\)/, 'Anlass-Chip kennzeichnet neu')
  assert.match(template, /class="lb-neu"/, 'Neu-Marke im Markup')

  // UXM-R17: Dublettenwarnung.
  assert.match(skriptText, /function dublettePruefen/, 'Dublettenprüfung vorhanden')
  assert.match(template, /Es gibt schon ein solches Lied/, 'Dublettendialog im Template')
  assert.match(template, /dubletteTrotzdem/, 'Trotzdem-Knopf')

  // OP-UI-4: Fokus/Scroll zum ersten fehlerhaften Feld.
  assert.match(skriptText, /function feldFokussieren/, 'feldFokussieren vorhanden')
  assert.match(skriptText, /aria-invalid="true"/, 'sucht das markierte Feld')
  assert.match(skriptText, /scrollIntoView/, 'holt es in den Blick')
}

// ── LiedDetail.vue: UXM-R4 ─────────────────────────────────────────────────

{
  const { template } = kompiliere('diakonos/pages/LiedDetail.vue')
  // Öffnen nutzt die Datei-URL — nicht die interne Anhang-Kennung (404).
  assert.match(template, /m\.datei\.datei_url/, 'Datei-URL wird verwendet')
  assert.doesNotMatch(template, /:href="m\.anhang"/, 'kein m.anhang (404) mehr')
}

// ── LiedgruppeDetail.vue: UXM-R9/R10 ───────────────────────────────────────

{
  const { template, skriptText } = kompiliere('diakonos/pages/LiedgruppeDetail.vue')
  // UXM-R10: Titel statt interner Kennung.
  assert.match(template, /row\.titel \|\| row\.lied/, 'Titel statt Kennung')
  // UXM-R9: Bearbeiten/Löschen.
  assert.match(template, /bearbeitenOeffnen/, 'Bearbeiten-Knopf')
  assert.match(template, /loeschenFragen/, 'Löschen-Knopf')
  assert.match(skriptText, /liedgruppeLoeschen/, 'Löschen ruft den Server')
  assert.match(template, /LiedgruppeBearbeiten/, 'Editor-Komponente eingebunden')
}

// ── Liedgruppen.vue: UXM-R9 ────────────────────────────────────────────────

{
  const { template, skriptText } = kompiliere('diakonos/pages/Liedgruppen.vue')
  assert.match(template, /Neue Liedgruppe/, 'Anlegen-Knopf')
  assert.match(template, /LiedgruppeBearbeiten/, 'Editor-Komponente eingebunden')
  assert.match(skriptText, /rechteLaden/, 'Schreibrecht vom Server')
  assert.match(skriptText, /lied_rechte/, 'Rechte-Endpunkt genutzt')
}

// ── LiedgruppeBearbeiten.vue: UXM-R9 ───────────────────────────────────────

{
  const { template, skriptText } = kompiliere('diakonos/components/lieder/LiedgruppeBearbeiten.vue')
  assert.match(skriptText, /save_liedgruppe|liedgruppeSpeichern/, 'Speichern verdrahtet')
  assert.match(skriptText, /liederSuchen/, 'Liedsuche für die Zuordnung')
  assert.match(template, /Lieder dieser Gruppe/, 'Zuordnungsbereich')
  assert.match(skriptText, /aria-invalid="true"/, 'Fehlerfokus (OP-UI-4)')
}

// ── Lieder.vue: OP-HANDY-13 ────────────────────────────────────────────────

{
  const { template, skriptText } = kompiliere('diakonos/pages/Lieder.vue')
  assert.match(template, /ld-filter-knopf/, 'Filter-Knopf (Blatt) vorhanden')
  assert.match(template, /ld-karten/, 'Kartenliste vorhanden')
  assert.match(skriptText, /filterBlatt/, 'Filterblatt-Zustand')
  assert.match(skriptText, /suchbegriffInAdresse/, 'Suchbegriff in die Adresse')
  assert.match(skriptText, /suchbegriffAusAdresse/, 'Suchbegriff aus der Adresse')
  assert.match(skriptText, /aktiveFilterZahl/, 'Filterzähler')
}

// ── Reine Logik: Liedgruppe-Editor (UXM-R9) ────────────────────────────────

{
  const modul = await import('../src/diakonos/components/lieder/liedgruppe-bearbeiten.mjs')

  // Prüfung: Name ist Pflicht.
  assert.equal(modul.pruefen(modul.leereGruppe()).ok, false, 'leerer Name ist Fehler')
  const ok = { ...modul.leereGruppe(), gruppenname: 'Chorlieder' }
  assert.equal(modul.pruefen(ok).ok, true, 'mit Namen gültig')

  // Unbekannter Typ wird beanstandet.
  assert.equal(modul.pruefen({ ...ok, typ: 'Erfunden' }).ok, false, 'unbekannter Typ')

  // Zuordnung: reihenfolge = 1..n, leere Zeilen weg.
  const lieder = modul.zuordnungenNormalisieren([
    { lied: 'l1', titel: 'A' }, { lied: '' }, { lied: 'l2', titel: 'B' },
  ])
  assert.deepEqual(lieder.map((z) => z.lied), ['l1', 'l2'], 'leere Zeilen entfernt')
  assert.deepEqual(lieder.map((z) => z.reihenfolge), [1, 2], 'neu durchnummeriert')

  // Hinzufügen überspringt Duplikate.
  let liste = modul.liedHinzufuegen([], { name: 'l1', titel: 'A' })
  liste = modul.liedHinzufuegen(liste, { name: 'l1', titel: 'A' })
  assert.equal(liste.length, 1, 'Duplikat übersprungen')

  // Verschieben hält die Reihenfolge konsistent.
  const zwei = modul.liedHinzufuegen(modul.liedHinzufuegen([], { name: 'a' }), { name: 'b' })
  const getauscht = modul.liedVerschieben(zwei, 0, 1)
  assert.deepEqual(getauscht.map((z) => z.lied), ['b', 'a'], 'Reihenfolge getauscht')
  assert.deepEqual(getauscht.map((z) => z.reihenfolge), [1, 2], 'neu nummeriert')

  // Entfernen nummeriert neu.
  const entfernt = modul.liedEntfernen(zwei, 0)
  assert.deepEqual(entfernt.map((z) => z.reihenfolge), [1], 'nach Entfernen neu nummeriert')

  // Nutzlast: Anlegen ohne name, Ändern mit name.
  assert.equal('name' in modul.nutzlast(ok), false, 'Neuanlage ohne name')
  assert.equal(modul.nutzlast({ ...ok, name: 'G1' }).name, 'G1', 'Ändern mit name')

  // Formular aus Detail übernimmt Lieder in Reihenfolge.
  const form = modul.gruppeAusDetail({
    liedgruppe: { name: 'G1', gruppenname: 'Chor', typ: 'Sammlung' },
    lieder: [{ lied: 'l2', titel: 'B', reihenfolge: 2 }, { lied: 'l1', titel: 'A', reihenfolge: 1 }],
  })
  assert.equal(form.name, 'G1', 'Detail-Name übernommen')
  assert.deepEqual(form.lieder.map((z) => z.lied), ['l2', 'l1'], 'Lieder übernommen')
}

console.log('p1-10 Lieder & Material: OK')
