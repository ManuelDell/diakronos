import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

/**
 * P1-8 — Verantwortliche und Zugang pflegbar (Frontend).
 *
 * Prüft die neuen Oberflächen gegen den Kartenumfang:
 *  - „Verantwortliche"-Karte in Gruppe/Untergruppe (OP-CHOR-3/OP-ADMIN-4),
 *  - „Zugang"-Reiter im Mitglied-Detail (OP-ADMIN-2),
 *  - Zugriff gebündelt in `composables/usePflege.js` (Kartenkonvention),
 *  - Rechte vom Server: `darf_pflegen` steuert nur den Knopf,
 *  - Auswahl nur Personen mit Konto.
 *
 * Läuft als Dateiprüfung (kein Vue-Compiler) — wie n1–n4 und p1-9.
 */
const root = new URL('../src/diakonos/', import.meta.url)
const lies = p => readFileSync(new URL(p, root), 'utf8')

const verw = lies('components/VerantwortlicheKarte.vue')
const zug = lies('components/ZugangKarte.vue')
const pflege = lies('composables/usePflege.js')
const gruppe = lies('pages/GruppeDetail.vue')
const mitglied = lies('pages/MitgliedDetail.vue')

// ── API-Zugriff gebündelt in einer Datei ───────────────────────────────────
{
  for (const fn of [
    'verantwortlicheLesen', 'verantwortlicheSetzen', 'verantwortlicheAuswahl',
    'zugangsRollen', 'zugangLesen', 'kontoAnlegen', 'rollenSetzen',
    'kontoSperren', 'passwortSetzen', 'wartendeKonten',
  ]) {
    assert.ok(pflege.includes(`export function ${fn}`), `usePflege exportiert ${fn}`)
  }
  assert.ok(pflege.includes('diakronos.diakonos.api.verantwortliche'), 'Verantwortlichen-Modul')
  assert.ok(pflege.includes('diakronos.diakonos.api.zugang'), 'Zugangs-Modul')
}

// ── Verantwortliche-Karte (OP-CHOR-3) ──────────────────────────────────────
{
  assert.ok(verw.includes('darfPflegen'), 'Rechte kommen vom Server (darf_pflegen)')
  assert.ok(verw.includes('verantwortlicheAuswahl'), 'Auswahl nur Personen mit Konto')
  assert.ok(verw.includes('verantwortlicheSetzen'), 'Zuweisung über den Endpunkt')
  // Alle drei Ebenen sind pflegbar.
  for (const d of ['Dienstbereich', 'Gruppe', 'Untergruppe']) {
    assert.ok(verw.includes(d), `Ebene ${d} unterstützt`)
  }
  // Nur wer pflegen darf, sieht den Bearbeiten-Knopf.
  assert.ok(
    verw.includes('v-if="darfPflegen && !bearbeiten"'),
    'Bearbeiten-Knopf nur mit Recht',
  )
}

// ── Einbindung in GruppeDetail ─────────────────────────────────────────────
{
  // UI-R1 (Manuel 11.11.): Die P1-8-Karte „Verantwortliche“ ist von der
  // Gruppenseite ENTFALLEN — sie schrieb über
  // `verantwortliche.set_verantwortliche` am EINEN Rechtesystem vorbei. Ihre
  // Aufgabe (wer führt die Gruppe) übernimmt der Reiter „Einstellungen“
  // (Rollen HV/MV/GL). Die Karte selbst bleibt für den Dienstbereich
  // bestehen; ihre Endpunkte prüft der Backend-Test.
  assert.ok(!gruppe.includes('VerantwortlicheKarte'),
    'GruppeDetail benutzt das alte Verantwortlichen-Board nicht mehr')
  assert.ok(gruppe.includes('GruppenEinstellungen'),
    'GruppeDetail bindet die Rollen-Einstellungen ein')
  assert.ok(gruppe.includes('darfEinstellungenSehen'),
    'Sichtbarkeit des Reiters aus den Serverrechten')
}

// ── Zugang-Reiter im Mitglied-Detail (OP-ADMIN-2) ──────────────────────────
{
  assert.ok(mitglied.includes('ZugangKarte'), 'MitgliedDetail nutzt die Karte')
  assert.ok(
    mitglied.includes("activeTab === 'zugang'"),
    'Zugang ist ein eigener Reiter',
  )
  // Authentik beachten: die Option hängt am Serverzustand.
  assert.ok(zug.includes('oidcAktiv'), 'ZugangKarte kennt den OIDC-Zustand')
  assert.ok(
    zug.includes('Über Authentik entstehen Konten beim Anbieter'),
    'Hinweis bei aktivem Authentik',
  )
}

// ── W1: wartende Konten sind in der Liste WIRKLICH erreichbar ──────────────
{
  // Befund P1-8b: die Karte hing an `!embedded`. Die Liste wird aber immer
  // eingebettet vom Rahmen (pages/mitglieder/Bereich.vue) gerendert — mit
  // `!embedded` war die Karte in der Oberfläche nie sichtbar, und wartende
  // Gastkonten liessen sich nicht freischalten. Der Test haelt die Bedingung
  // fest: die Karte haengt NUR an `isAdmin`.
  const liste = lies('pages/Mitglieder.vue')
  // UX3j (A3): Der Personen-Rahmen ist `pages/Personen.vue`; die Karte steht
  // dort direkt im Liste-Reiter (kein zweites Einbetten mehr nötig).
  const rahmen = lies('pages/Personen.vue')
  assert.ok(liste.includes('WartendeKontenKarte'), 'Liste bindet die Wartende-Karte ein')
  // UI-R10: die Karte hängt am Personen-Recht (`darfVerwalten` =
  // `istMitgliederverwaltung`), nicht mehr am Kern-Admin — die
  // Mitgliederverwaltung pflegt Konten (R-11a). Und nicht an `!embedded`.
  assert.ok(
    liste.includes('v-if="darfVerwalten"'),
    'Wartende-Karte haengt am Personen-Recht (UI-R10)',
  )
  // … und NICHT an `embedded`/`!embedded`: die Karte gehoert zum Inhalt.
  const karte = liste.slice(liste.indexOf('WartendeKontenKarte v-if'))
  assert.ok(!/embedded/.test(karte.slice(0, karte.indexOf('>'))),
    'Wartende-Karte haengt nicht an embedded')
  // Der Rahmen zeigt die Karte im Reiter „Liste“ — nur für Mitgliederadmins.
  assert.ok(rahmen.includes('<WartendeKontenKarte v-if="verwaltung"'),
    'Rahmen zeigt die wartenden Konten in der Liste')
}
