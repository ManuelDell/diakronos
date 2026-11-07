/**
 * UX1h — genau EIN Primärknopf je Ansicht (Prinzip S1 „eine Hauptaktion“).
 *
 * Die Karte setzt zwei Dinge um:
 *
 *   (H1) WÄCHTER: Je Seiten-Komponente (`pages/**`) steht höchstens EIN
 *        `variant="primary"` — statisch gezählt. Der Bestand ist in
 *        `tools/ux1h-primaerknopf-bestand.txt` eingefroren und darf NUR
 *        SCHRUMPFEN (Muster ON-0a/0b/0c, UX1e/UX1f/UX1g).
 *
 *   (H2) BEREINIGT sind die Seiten der Karte: Registrierung, Ressourcen,
 *        ModerationModals, Profile, KalenderVerwaltung, KalenderImport,
 *        GruppeDetail, Beitraege. Jede hat ihre EINE Hauptaktion nach der
 *        Konzept-Entscheidung (Ressourcen: Buchen · Gruppen: Gruppe anlegen ·
 *        Beiträge: Beitrag schreiben · Registrierung-Verwaltung: Link
 *        anlegen), der Rest ist secondary/ghost.
 *
 * WARUM GILT EIN DIALOG ALS EIGENE ANSICHT
 * Ein Dialog liegt modal über der Seite, hat seinen eigenen Fokus und seinen
 * eigenen Fuß — er braucht seinen eigenen gefüllten Knopf („Speichern“,
 * „Anlegen“, „Buchen“). Deshalb zählt der Wächter Knöpfe INNERHALB von
 * DkDialog/DkModal/… nicht der Seite zu, und H2 prüft die Dialogfüße
 * getrennt (höchstens EIN gefüllter Knopf je Fuß, wie UX1f/F3).
 *
 * Läuft im Docker-Build (`node --test`); die Datei liegt in `frontend/tests/`
 * und liest nur `frontend/**` (Regel 13).
 */
import assert from 'node:assert/strict'
import { existsSync, readFileSync } from 'node:fs'
import path from 'node:path'
import test from 'node:test'

import {
  FRONTEND,
  LISTE,
  bestand,
  liesBestand,
  ohneDialoge,
  ohneKommentare,
  primaerzaehlung,
  seitenVorlage,
  seitendateien,
  verstoesse,
  vorlage,
} from '../tools/ux1h-primaerknopf-bestand.mjs'

const P = 'frontend/src/diakonos/'

/** Quelle einer Datei (Pfad in Listen-Schreibweise, `frontend/…`). */
function lies(rel) {
  const abs = path.join(FRONTEND, rel.replace(/^frontend\//, ''))
  assert.ok(existsSync(abs), `Datei fehlt: ${rel}`)
  return readFileSync(abs, 'utf8')
}

/** Die Seiten der Karte (H2). */
const BEREINIGT = {
  // Seite → Name der EINEN Hauptaktion (Beschriftung im Knopf)
  [`${P}pages/Ressourcen.vue`]: 'Buchen',
  [`${P}pages/Registrierung.vue`]: 'Neuer Link',
  [`${P}pages/KalenderVerwaltung.vue`]: 'Neuer Kalender',
  // KalenderImport: keine Hauptaktion der Seite selbst — die zwei Reiter
  // (Google / iCal) sind eigene Ansichten mit je einem gefüllten Knopf.
  [`${P}pages/KalenderImport.vue`]: null,
  [`${P}pages/Profile.vue`]: null,
  // Beitraege: der Kopfknopf ist der gefuellte (Name folgt nach einem
  // Symbol-Element, darum keine Textpruefung hier — siehe eigener Test).
  [`${P}pages/Beitraege.vue`]: null,
}

// ── H1: Wächter (nur schrumpfen) ───────────────────────────────────────────

test('UX1h/H1: der Bestand der Primärknöpfe schrumpft und ist aktuell', () => {
  assert.ok(existsSync(LISTE), 'tools/ux1h-primaerknopf-bestand.txt fehlt')
  const fehler = verstoesse(bestand(), liesBestand())
  assert.deepEqual(fehler, [],
    'Die Liste tools/ux1h-primaerknopf-bestand.txt passt nicht zum Stand:\n  '
    + fehler.join('\n  ')
    + '\nNach dem Beheben: node tools/ux1h-primaerknopf-bestand.mjs --schreiben')
})

/**
 * Seiten mit mehreren Ansichten, die im Rumpf stehen. Sie sind von der
 * „1 je Datei“-Regel ausgenommen und werden in der Bestandsliste weiter
 * gefuehrt (nur schrumpfen). Je Seite ist der zweite gefüllte Knopf eine
 * ANDERE Ansicht bzw. ein Zustand, der den ersten ausschliesst:
 *
 *   GruppeDetail  Detailseite mit vier Karten (Details, Ankündigungen,
 *                 Aufgaben, Wiki); zwei Karten legen beim Aufklappen ein
 *                 Formular mit eigener Hauptaktion auf, die dritte ist
 *                 „Speichern“ beim Bearbeiten der Details.
 *   Home          Startseite; der zweite ist „Karten einblenden“ im
 *                 Leer-/Anfangszustand (schliesst sich mit der Übersicht aus).
 *   Lieder        Liste; der zweite ist „Erstes Lied anlegen“ im Leerzustand
 *                 (schliesst sich mit der Liste aus).
 *   MitgliedDetail  Detailseite mit Stammdaten- und Bearbeiten-Zustand
 *                 (Speichern) sowie dem Foto-Dialog.
 *   Die sieben Seiten unter `NICHT_IN_DIESER_KARTE` (Einstellungen,
 *   Planrahmen, Mitglieder-Import) sind NICHT Teil dieser Karte: dort stehen
 *   zwei gefuellte Knoepfe in zwei getrennten Karten, und eine Bereinigung
 *   waere eine eigene Gestaltungsentscheidung (je Karte eine Hauptaktion statt
 *   je Seite). Sie bleiben unveraendert in der Liste eingefroren, damit der
 *   Bestand nicht waechst; die naechste Karte nimmt sie sich vor.
 */
const NICHT_IN_DIESER_KARTE = new Set([
  `${P}pages/einstellungen/Anmeldung.vue`,
  `${P}pages/einstellungen/Datensicherung.vue`,
  `${P}pages/mitglieder/Datenschutz.vue`,
  `${P}pages/mitglieder/Import.vue`,
  `${P}pages/planrahmen/Plan.vue`,
  `${P}pages/planrahmen/PlantypEditor.vue`,
  `${P}pages/planrahmen/Stammdaten.vue`,
])

const MEHRERE_ANSICHTEN = new Set([
  `${P}pages/GruppeDetail.vue`,
  `${P}pages/Home.vue`,
  `${P}pages/Lieder.vue`,
  `${P}pages/MitgliedDetail.vue`,
])

test('UX1h/H1: keine Seite hat mehr als EINEN Primärknopf ausserhalb von Dialogen', () => {
  const zuviel = [...bestand()]
    .filter(([pfad, zahl]) => zahl > 1 && !MEHRERE_ANSICHTEN.has(pfad)
      // Unterbereiche/Reiter zaehlen als eigene Ansichten (ANSICHTEN).
      && !ANSICHTEN[pfad]
      && !NICHT_IN_DIESER_KARTE.has(pfad))
    .map(([pfad, zahl]) => `${pfad}: ${zahl}`)
  assert.deepEqual(zuviel, [],
    'Diese Ansichten haben mehr als einen gefüllten Knopf (S1 — genau eine '
    + 'Hauptaktion je Ansicht):\n  ' + zuviel.join('\n  ')
    + '\nNebenaktionen werden secondary/ghost; Dialoge sind eigene Ansichten '
    + 'und behalten ihren Primärknopf im Fuß.')
})

test('UX1h/H1: die Liste kennt keine Datei ausserhalb der Seiten', () => {
  for (const pfad of liesBestand().keys()) {
    assert.match(pfad, /^frontend\/src\/diakonos\/pages\/[^/]+(\.vue|\/[^/]+\.vue)$/,
      `${pfad}: nicht im Bereich pages/**`)
  }
})

test('UX1h/H1: der Zähler rechnet richtig (Dialoge, Kommentare, gebundene Varianten)', () => {
  // Ein Dialog ist eine eigene Ansicht: sein Primärknopf zählt nicht zur Seite.
  const mitDialog = vorlage(`<template><div>
    <DkButton variant="primary">Seite</DkButton>
    <DkDialog v-model="offen">
      <template #footer><DkButton variant="primary">Speichern</DkButton></template>
    </DkDialog>
  </div></template>`)
  assert.equal(primaerzaehlung(ohneDialoge(ohneKommentare(mitDialog))), 1)

  // Gleichnamige Dialoge in derselben Datei (verschachtelt verschachtelt).
  const zweiDialoge = vorlage(`<template><div><DkButton variant="primary">A</DkButton>
    <DkModal><div><DkModal></DkModal></div></DkModal>
    <DkModal><DkButton variant="primary">B</DkButton></DkModal></div></template>`)
  assert.equal(primaerzaehlung(ohneDialoge(ohneKommentare(zweiDialoge))), 1)

  // Kommentare mit Beispiel-Code zählen nicht.
  const kommentar = vorlage(`<template><div>
    <!-- <DkButton variant="primary">Beispiel</DkButton> -->
    <DkButton variant="primary">Echt</DkButton></div></template>`)
  assert.equal(primaerzaehlung(ohneKommentare(kommentar)), 1)

  // Gebundene Variante: schaltet zur Laufzeit, ist nie zweimal gefüllt.
  const gebunden = vorlage(
    `<template><div><DkButton :variant="an ? 'primary' : 'secondary'">Umschalter</DkButton></div></template>`)
  assert.equal(primaerzaehlung(gebunden), 0)
})

test('UX1h/H1: jede Seite wird gezählt (auch Unterordner)', () => {
  const dateien = seitendateien()
  assert.ok(dateien.length > 20, `nur ${dateien.length} Seiten gefunden`)
  assert.ok(dateien.some((p) => p.includes('/pages/planrahmen/')),
    'Unterordner der Seiten werden nicht gelesen')
})

// ── H2: die bereinigten Seiten ─────────────────────────────────────────────

/**
 * Seiten, deren Vorlage aus MEHREREN Ansichten besteht (Unterbereiche bzw.
 * Reiter), die sich ausschliessen. Sie werden je Ansicht geprueft: je
 * Unterbereich genau EIN gefuellter Knopf, und die Zahl der Ansichten ist
 * vorher festgehalten (sie darf nicht wachsen).
 */
const ANSICHTEN = {
  [`${P}pages/Registrierung.vue`]: {
    // Die Trenn-Kommentare stehen IM HTML und werden von `seitenVorlage()`
    // entfernt — deshalb ueber den v-if-Zweig der Unterbereiche trennen.
    trenner: /<div v-if="unterbereich === '/g,
    anzahl: 3,
  },
  [`${P}pages/KalenderImport.vue`]: {
    // Der erste Reiter steht auf `v-if`, der zweite auf `v-else` (ohne Wert).
    trenner: /<section v-(?:if|else-if|else|show)\b[^>]*role="tabpanel"/g,
    anzahl: 2,
  },
}

/**
 * Zerlegt einen Reiter/Unterbereich an seinen Arbeitsschritten. Der
 * Google-Import fuehrt durch drei Schritte (`step === 1|2|3`), die sich
 * ausschliessen — jeder Schritt ist seine eigene Ansicht mit eigenem
 * gefuellten Knopf.
 */
function schritte(teil) {
  const stellen = [...teil.matchAll(/\bstep === |>\s*<h2>3\./g)].map((m) => m.index)
  if (stellen.length < 2) return [teil]
  return stellen.map((start, i) => teil.slice(start, i + 1 < stellen.length ? stellen[i + 1] : teil.length))
}

/** Zerlegt eine Seitenvorlage an ihren Ansichts-Trennern. */
function ansichten(datei) {
  const text = seitenVorlage(path.join(FRONTEND, datei.replace(/^frontend\//, '')))
  const regel = ANSICHTEN[datei]
  if (!regel) return [text]
  const stellen = [...text.matchAll(regel.trenner)].map((m) => m.index)
  return stellen.map((start, i) => text.slice(start, i + 1 < stellen.length ? stellen[i + 1] : text.length))
}

test('UX1h/H2: die Seiten der Karte haben genau eine Hauptaktion', () => {
  for (const [datei, aktion] of Object.entries(BEREINIGT)) {
    const text = seitenVorlage(path.join(FRONTEND, datei.replace(/^frontend\//, '')))
    const zahl = primaerzaehlung(text)
    const ansichtszahl = ANSICHTEN[datei]
      ? ansichten(datei).flatMap((teil) => schritte(teil)).length
      : 1
    assert.ok(zahl <= ansichtszahl,
      `${datei}: ${zahl} Primärknöpfe ausserhalb der Dialoge für ${ansichtszahl} `
      + 'Ansicht(en) — je Ansicht ist genau einer erlaubt (S1)')
    if (aktion) {
      assert.match(text, new RegExp(`variant="primary"[^>]*>[\\s\\S]{0,160}?${aktion}`),
        `${datei}: „${aktion}“ ist die Hauptaktion der Ansicht und muss der `
        + 'gefüllte Knopf sein')
    }
  }
})

/** Gefüllte Knöpfe in einem Stück Vorlage: primary UND danger. */
function gefuellte(text) {
  return [...text.matchAll(/<DkButton\b[^>]*?\bvariant="(primary|danger)"/gs)].map((m) => m[1])
}

/** Die Knopfleisten der Dialogfüße (je Sicht eine Leiste). */
function fuesse(fileText) {
  const leisten = []
  for (const m of vorlage(fileText).matchAll(/<template #footer>([\s\S]*?)<\/template>/g)) {
    leisten.push(m[1])
  }
  return leisten
}

/**
 * Die Fussleisten eines Dialogs samt den Sichten, die sich darin
 * ausschliessen (`v-if` / `v-else-if` / `v-else`). Ein `<template v-if>` im
 * Fuss ist kein eigener Dialogfuss — es ist eine Sicht DESSELBEN Fusses.
 */
function fussSichten(fileText) {
  const sichten = []
  const text = vorlage(fileText)
  for (const m of text.matchAll(/<template #footer>([\s\S]*?)<\/Dk(?:Dialog|Modal)>/g)) {
    const innen = m[1]
    // Sichten im Fuß: `<template v-if>` … und daneben die Geschwister mit
    // `v-if` / `v-else-if` / `v-else` auf einem <div> (Seriendialog).
    const teile = [...innen.matchAll(/<template v-(?:if|else-if|else)\b[^>]*>([\s\S]*?)<\/template>/g)]
      .map((t) => t[1])
    if (teile.length === 1) { sichten.push(...teile); continue }
    const geschwister = splitGeschwister(innen)
    sichten.push(...(geschwister.length ? geschwister : [innen]))
  }
  return sichten
}

/**
 * Zerlegt eine Knopfleiste an den Geschwistern mit `v-if` / `v-else-if` /
 * `v-else` (jeweils bis zum naechsten solchen Attribut). Damit hat jede Sicht
 * ihre eigene Leiste — ein `v-if`-Waechter wie „nur wenn nicht geladen“ ist
 * eine Vorschaltung, keine eigene Sicht, und bleibt bei seiner Leiste.
 */
function splitGeschwister(innen) {
  // `v-else-if` zuerst, sonst bliebe beim `v-else` ein „-if“ stehen und der
  // Alt-Zweig liefe bis ans Ende der Leiste (er enthielte den `v-else`-Knopf).
  const marken = [...innen.matchAll(/\s(v-else-if|v-if|v-else)(?=[\s=>])/g)].map((m) => m.index)
  if (marken.length < 2) return []
  const teile = []
  for (let i = 0; i < marken.length; i += 1) {
    teile.push(innen.slice(marken[i], i + 1 < marken.length ? marken[i + 1] : innen.length))
  }
  return teile
}

test('UX1h/H2 GruppeDetail: je Karte hoechstens ein gefüllter Knopf', () => {
  // Die Detailseite traegt vier Karten; „Details bearbeiten“, „Ankündigung
  // anlegen“ und „Aufgabe anlegen“ legen je ein Formular mit eigener
  // Hauptaktion auf. Geprüft wird deshalb je Karte.
  const text = seitenVorlage(path.join(FRONTEND, `${P}pages/GruppeDetail.vue`.replace(/^frontend\//, '')))
  const karten = text.split('<DkCard').slice(1)
  assert.ok(karten.length >= 3, `nur ${karten.length} Karten gefunden`)
  for (const karte of karten) {
    const voll = gefuellte(karte)
    assert.ok(voll.length <= 1,
      `GruppeDetail: ${voll.length} gefüllte Knöpfe (${voll.join(', ')}) in EINER Karte`)
  }
})

test('UX1h/H2: je Ansicht (Unterbereich/Reiter) höchstens EIN gefüllter Knopf', () => {
  for (const [datei, regel] of Object.entries(ANSICHTEN)) {
    const teile = ansichten(datei).flatMap((teil) => schritte(teil))
    assert.equal(ansichten(datei).length, regel.anzahl,
      `${datei}: ${ansichten(datei).length} Ansichten gefunden, ${regel.anzahl} erwartet `
      + '(Unterbereiche/Reiter sind eigene Ansichten — die Zahl ist der Stand dieser Karte)')
    for (const teil of teile) {
      const voll = gefuellte(teil)
      assert.ok(voll.length <= 1,
        `${datei}: ${voll.length} gefüllte Knöpfe in EINER Ansicht (${voll.join(', ')})`)
    }
  }
})

test('UX1h/H2: je Dialogfuß höchstens EIN gefüllter Knopf', () => {
  for (const datei of [...Object.keys(BEREINIGT), `${P}components/kronos/ModerationModals.vue`]) {
    for (const inhalt of fussSichten(lies(datei))) {
      const voll = gefuellte(inhalt)
      assert.ok(voll.length <= 1,
        `${datei}: ${voll.length} gefüllte Knöpfe (${voll.join(', ')}) in EINER Sicht eines Fußes`)
    }
  }
})

// ── H2: die Befunde im Einzelnen ───────────────────────────────────────────

test('UX1h/H2 Ressourcen: „Buchen“ ist der eine gefüllte Knopf, „Buchung anlegen“ ist weg', () => {
  const text = lies(`${P}pages/Ressourcen.vue`)
  // Nur der Vorlagenteil zaehlt (Kommentare dürfen den alten Namen nennen).
  assert.doesNotMatch(ohneKommentare(vorlage(text)), /Buchung anlegen/,
    'zweiter Weg zum selben Formular — „Buchen“ deckt das ab')
  // Der Umschalter ist keine Aktion: secondary, mit angesagtem Zustand.
  assert.match(text, /variant="secondary"\s+:aria-pressed="showMyBookings \? 'true' : 'false'"/,
    '„Meine Buchungen“ muss secondary sein und seinen Zustand ansagen')
  // Moderations-Freigabe ist Arbeit des Moderators, nicht die Seitenhauptaktion.
  assert.doesNotMatch(text, /variant="primary"\s+size="md"\s+@click="approve/,
    'die Freigabe-Knöpfe der Anfragen sind secondary')
  // Der Leerzustand wiederholt „Buchen“ abgestuft (kein zweiter Primary).
  const leer = text.slice(text.indexOf('<DkEmpty'), text.indexOf('<!-- Offene Anfragen'))
  assert.match(leer, /variant="ghost"[^>]*@click="openBookingModal\(\)"/,
    'der Leerzustand bietet „Buchen“ als ghost an')
})

test('UX1h/H2 Ressourcen: „Buchen“ hängt nicht am Admin-Recht', () => {
  const text = lies(`${P}pages/Ressourcen.vue`)
  const kopf = text.slice(text.indexOf('<DkPageHeader'), text.indexOf('<!-- Toolbar'))
  assert.match(kopf, /v-if="darfBuchen" variant="primary"/,
    'der gefüllte Knopf muss das Anmeldekonto prüfen, nicht isAdmin — '
    + 'sonst fehlt normalen Mitgliedern der einzige Weg zu einer Buchung')
  assert.match(text, /const darfBuchen = computed\(\(\) => !!user\.value\)/,
    'darfBuchen ist nicht definiert')
})

test('UX1h/H2 Registrierung: „Neuer Link“ ist der Primärknopf, Zeilen sind secondary', () => {
  const text = lies(`${P}pages/Registrierung.vue`)
  assert.match(text, /variant="primary" @click="linkOeffnen"/,
    '„Neuer Link“ muss der gefüllte Knopf sein')
  assert.doesNotMatch(text, /variant="primary" @click="verlaengernOeffnen/,
    '„Verlängern“ je Zeile ist secondary')
  assert.doesNotMatch(text, /variant="primary" @click="formularBearbeiten/,
    '„Bearbeiten“ je Tabellenzeile ist secondary')
  assert.match(text, /variant="primary" @click="formularOeffnen"/,
    'im Unterbereich Formulare ist „Neues Formular“ die Hauptaktion')
})

test('UX1h/H2 KalenderVerwaltung: der Leerzustand wiederholt den Kopfknopf abgestuft', () => {
  const text = lies(`${P}pages/KalenderVerwaltung.vue`)
  const leer = text.slice(text.indexOf('<DkEmpty'), text.indexOf('<div v-else class="kv-karten"'))
  assert.match(leer, /variant="ghost"[^>]*@click="neuerKalender"/,
    '„Neuer Kalender“ im Leerzustand ist ghost (der Kopf trägt den Primary)')
})

test('UX1h/H2 ModerationModals: je Sicht des Seriendialogs ein gefüllter Knopf', () => {
  const text = lies(`${P}components/kronos/ModerationModals.vue`)
  // Konflikt-/Seriendialoge sind eigene Ansichten: genau ein gefüllter Knopf
  // je Sicht ihres Fusses (Sichten schliessen sich aus).
  const sichten = fussSichten(text)
  assert.ok(sichten.length >= 4, `nur ${sichten.length} Fußsichten gefunden`)
  for (const sicht of sichten) {
    assert.ok(gefuellte(sicht).length <= 1,
      `ModerationModals: ${gefuellte(sicht).length} gefüllte Knöpfe in einer Fußsicht`)
  }
})

test('UX1h/H2 Beitraege: „Neuer Beitrag“ bleibt die Hauptaktion der Ansicht', () => {
  const text = lies(`${P}pages/Beitraege.vue`)
  assert.match(text, /variant="primary" @click="openEditor\(\)"/,
    '„Neuer Beitrag“ ist die eine Hauptaktion der Seite')
  assert.match(text, /Neuer Beitrag\s*<\/DkButton>/,
    'die Beschriftung des Kopfknopfes ist „Neuer Beitrag“')
  // Die Seite selbst (ohne Dialoge) hat nur diesen einen Primary.
  const seite = seitenVorlage(path.join(FRONTEND, `${P}pages/Beitraege.vue`.replace(/^frontend\//, '')))
  assert.equal(primaerzaehlung(seite), 1)
})

test('UX1h/H2 Profil: „Erteilen“ je Einwilligung ist secondary', () => {
  // Der Befund aus dem Wegwerf-Stack: die Einwilligungszeilen trugen
  // `:variant="… ? 'ghost' : 'primary'"` — je nicht erteilter Einwilligung
  // ein gefüllter Knopf, also mehrere Primärknöpfe auf einer Ansicht.
  const text = lies(`${P}pages/Profile.vue`)
  assert.doesNotMatch(text, /variant="[^"]*\?[^"]*primary/,
    'keine gebundene Variante mit primary — je Ansicht ist genau einer gefüllt')
  assert.match(text, /variant="secondary"\s+:disabled="savingConsent"/,
    'die Einwilligungsknöpfe sind secondary')
})

test('UX1h: Kalender-Seiten bleiben bei UX3i (nicht angefasst)', () => {
  // Der Orchestrator hat die Kalender-Seiten dieser Karte entzogen.
  assert.ok(!('frontend/src/diakonos/pages/Kalender.vue' in BEREINIGT))
})