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
  assert.ok(gruppe.includes('VerantwortlicheKarte'), 'GruppeDetail nutzt die Karte')
  assert.ok(
    gruppe.includes(':doctype="isUntergruppe ? \'Untergruppe\' : \'Gruppe\'"'),
    'doctype folgt der Ebene',
  )
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
  const rahmen = lies('pages/mitglieder/Bereich.vue')
  assert.ok(liste.includes('WartendeKontenKarte'), 'Liste bindet die Wartende-Karte ein')
  assert.ok(
    liste.includes('v-if="isAdmin"') && !liste.includes('isAdmin && !embedded'),
    'Wartende-Karte haengt nur an isAdmin (nicht an !embedded)',
  )
  // Der Rahmen bettet die Liste ein -> `embedded` ist dort immer gesetzt.
  assert.ok(rahmen.includes('embedded'), 'Rahmen rendert die Liste eingebettet')
}
