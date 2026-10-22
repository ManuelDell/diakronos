/**
 * REST-3 — Der Stift im Organigramm führte auf die Fehlerseite.
 *
 * Befund R-DES-REST-b (Nebenbefund): Gruppen ließen sich über das Organigramm
 * weder öffnen noch bearbeiten. Ein Klick auf eine Gruppen-Kachel und auf
 * ihren ✏️-Stift navigierte nach `#/gruppe/g_<Kennung>` — dort sucht die
 * Detailseite aber den ROHEN Namen. Der Server antwortete „Gruppe
 * 'g_Eheberatung' existiert nicht“.
 *
 * Der Stift selbst öffnet das Bearbeiten-Fenster; überlebt hat die Adresse
 * deshalb im Kachel-Klick. Beides wird hier geprüft — inklusive der Zusage,
 * dass die Route Detailseite + Kennung zusammenbringt und das Fenster den
 * gespeicherten Treffzeit-Eintrag zeigt (W-1).
 */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const lies = (rel) => readFileSync(new URL('../' + rel, import.meta.url), 'utf8')

// ── Die Kennung, die die Route erwartet ─────────────────────────────────────

test('REST-3 · der Kachel-Klick nimmt den rohen Namen, nicht die Knoten-Kennung', () => {
  const org = lies('src/diakonos/components/gruppen/OrganigrammAnsicht.vue')
  const handler = org.match(/window\.__orgNavigateNode = ([^]*?)\n\}/)
  assert.ok(handler, 'Handler __orgNavigateNode nicht gefunden')
  assert.match(handler[1], /roherName\(knoten\)/, 'Handler baut die Adresse ohne rohen Namen')
  assert.ok(!/'#\/gruppe\/' \+ encodeURIComponent\(id\)/.test(handler[1]),
    'Adresse enthält wieder die Knoten-Kennung (g_…/ug_…)')
  assert.match(handler[1], /rawName/, 'Roher Name kommt im Handler nicht an')
})

test('REST-3 · der Handler bekommt den rohen Namen mitgegeben', () => {
  const org = lies('src/diakonos/components/gruppen/OrganigrammAnsicht.vue')
  // Die Kachel übergibt (Kennung, Typ) — der rohe Name muss mit.
  const aufruf = org.match(/window\.__orgNavigateNode\(([^)]*)\)/)
  assert.ok(aufruf, 'Aufruf __orgNavigateNode nicht gefunden')
  assert.match(aufruf[1], /rawJs|raw_name/,
    'Aufruf übergibt keinen rohen Namen')
})

test('REST-3 · die Route reicht die Kennung an die Detailseite weiter', () => {
  const router = lies('src/diakonos/router.js')
  assert.match(router, /pattern: \/\^#\\\/gruppe\\\/\(\.\+\)\$\/, page: 'GruppeDetail', param: 'id'/,
    'Route #/gruppe/<id> fehlt')
  const detail = lies('src/diakonos/pages/GruppeDetail.vue')
  assert.match(detail, /get_gruppe_detail', \{ gruppe_id: id \}/,
    'Detailseite lädt nicht über die Kennung aus der Adresse')
})

// ── Der Stift öffnet das Fenster direkt ────────────────────────────────────

test('REST-3 · „Gruppe bearbeiten“ öffnet bei genau einer Gruppe direkt das Fenster', () => {
  const org = lies('src/diakonos/components/gruppen/OrganigrammAnsicht.vue')
  const fn = org.match(/function goToEdit\(\) \{([^]*?)\n\}/)
  assert.ok(fn, 'goToEdit nicht gefunden')
  assert.match(fn[1], /editableNodes\.value\.length === 1/, 'Einzelfall fehlt')
  assert.match(fn[1], /proceedToEdit\(\)/, 'geht nicht ins Bearbeiten-Fenster')
})

// ── W-1: der gespeicherte Treffzeit-Eintrag ist sichtbar ────────────────────

test('REST-3 · das Bearbeiten-Fenster zeigt den bisherigen Treffzeit-Eintrag', () => {
  const org = lies('src/diakonos/components/gruppen/OrganigrammAnsicht.vue')
  assert.match(org, /Bisheriger Eintrag: „\{\{ editForm\.treffzeit \}\}“/,
    'Hinweis auf den Alteintrag fehlt')
  const fn = org.match(/function treffzeitNichtRhythmus\(\) \{([^]*?)\n\}/)
  assert.ok(fn, 'treffzeitNichtRhythmus nicht gefunden')
  assert.match(fn[1], /!!editForm\.value\.treffzeit/,
    'Hinweis erscheint nicht bei jedem gespeicherten Eintrag')
})

// ── Der Stift darf den Kachel-Klick nicht mit auslösen ──────────────────────

test('REST-3 · der Stift bleibt im Kasten: sein Klick wird nicht weitergeleitet', () => {
  const org = lies('src/diakonos/components/gruppen/OrganigrammAnsicht.vue')
  // Der Stift sitzt in dem Kasten, dessen onclick die Detailseite öffnet.
  // Ohne stopPropagation lief der Klick zusätzlich zum Kasten — die Seite
  // sprang auf die Gruppe, das Bearbeiten-Fenster ging nie auf.
  const kasten = org.match(/onclick="window\.__orgNavigateNode\(/)
  assert.ok(kasten, 'Kachel-Klick nicht gefunden')
  const stift = org.match(/<button onclick="([^"]*__orgEditNode[^"]*)"/)
  assert.ok(stift, 'Stift-Handler nicht gefunden')
  assert.match(stift[1], /event\.stopPropagation\(\)/,
    'Stift-Klick steigt zum Kasten auf und öffnet die Detailseite')
})
