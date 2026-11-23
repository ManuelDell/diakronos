<template>
  <header class="dk-topbar">
    <div class="dk-topbar-left">
      <!-- UX3e (Entwurf A8): Menü-Symbol OBEN LINKS öffnet die Schublade mit
           der vollständigen Navigation. MT-1 (Manuel 11.11.): Es gehört
           AUSSCHLIESSLICH zur Handy-Lage. Am Laptop/Desktop gibt es genau EINEN
           Einstieg zur Navigation — die Seitenleiste selbst; eingeklappt ist
           das ihr eigener Ausklapp-Knopf oben in der Leiste (S4/N5). Vorher
           zeigte die Kopfzeile bei eingeklappter Leiste zusätzlich einen
           Hamburger, der ein ZWEITES, identisches Panel öffnete; damit standen
           beide Einstiege nebeneinander und der Hamburger lag direkt neben der
           Überschrift. Die Sichtbarkeit regelt index.css: Grundregel `none`,
           an nur noch `.dk-app--handy`. -->
      <MenueKnopf :offen="menueOffen" @oeffnen="$emit('open-menu')" />

      <!-- Zurück (UX1f): ein Weg der Kopfzeile, kein Alt-Knopf — dieselbe
           Gestaltung wie die übrigen ghost-Knöpfe (Symbol + Wort, N8), aber in
           der Höhe der Kopfzeilenknöpfe (md statt sm). -->
      <DkButton
        v-if="showBack"
        variant="ghost"
        class="dk-zurueck"
        @click="navigateBack"
      >
        <template #icon>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/></svg>
        </template>
        Zurück
      </DkButton>

      <!-- Breadcrumbs. A10 (Review 09.11., Punkt 4): Am Handy ist die letzte
           Krume der SEITENTITEL („Kalender“) — die Gestaltung der Titelstufe
           steht in index.css; die Seite gibt dafür ihren eigenen Titel ab,
           damit „Kalender“ nur EINMAL im Kopf steht. Andere Krumen
           („Personen / X“) stehen dort nicht mehr: der Titel des Bereichs
           genügt, wie Entwurf A10 es zeigt. -->
      <nav class="dk-crumbs">
        <template v-for="(crumb, i) in breadcrumbs" :key="i">
          <span v-if="i === breadcrumbs.length - 1" class="dk-crumb dk-crumb-current">{{ crumb }}</span>
          <span v-else-if="i === 0 && breadcrumbs.length > 1" class="dk-crumb dk-crumb-weg">{{ crumb }}</span>
          <span v-else-if="i > 0" class="dk-crumb dk-crumb-sep">/</span>
        </template>
      </nav>
      <!-- A10: Abzeichen „Moderator“ am Handy neben dem Titel (Entwurf A10:
           Menü · Kalender [Moderator] · Suche). Die SEITE setzt es, wenn sie
           das Recht hat (eine Rechtequelle, `can_moderate`); ohne Recht ist
           der Halter leer — kein Platz, kein Abzeichen. -->
      <span v-if="rollenMarke" class="dk-topbar-rolle">
        <DkBadge variant="info">{{ rollenMarke }}</DkBadge>
      </span>
    </div>

    <div class="dk-topbar-right">
      <!-- UX3f (Entwurf A5): Die Kopfzeile trägt wieder eine Suche — diesmal
           MIT Funktion: der Klick öffnet die Befehlspalette (Strg+K / ⌘+K).
           Der frühere tote „Suchen ⌘K“-Knopf (UXD-R19) war reines Markup ohne
           Ziel; dieser hier ruft `oeffnen()` der Palette auf. Das Kürzel steht
           als Text „Strg K“ daneben (nicht als Tastatur-Element), damit die
           Anzeige nicht wie eine zweite Bedienfläche wirkt. -->
      <button
        type="button"
        class="dk-topbar-suche"
        title="Suchen (Strg K)"
        aria-label="Suchen — Befehlspalette öffnen (Strg K)"
        @click="$emit('suche')"
      >
        <DkSymbol name="suchen" :groesse="16" />
        <span>Suchen …</span>
        <span class="dk-topbar-suche-kuerzel" aria-hidden="true">Strg K</span>
      </button>

      <!-- Notifications (OP-HANDY-6): Klick OEFFNET die Liste. Markiert wird
           erst danach — vorher setzte der Klick ungesehen alles auf gelesen.
           LEISTE-1: Denselben Baustein tragen jetzt auch die Seitenleiste
           (Eintrag „Benachrichtigungen“) und der Vollbild-Kopf der
           Nachrichten — eine Logik, drei Orte. -->
      <Glocke />

      <div class="dk-topbar-divider" />

      <!-- DEVBADGE-1: Platz für einen Eintrag der Kopfzeile — dort setzt
           `App.vue` den Dev-Einschaltknopf ein, solange die Handy-Lage gilt
           (die Karte erlaubt ausdrücklich „Eintrag im Kopf statt schwebendes
           Element“). Am Desktop trägt `App.vue` den Knopf gar nicht hier ein
           (`:dev-knopf="devStartZeigen && istHandyLage"` bleibt dort falsch),
           also wird dieser Platz dort auch nicht gerendert — kein leerer
           Rest, keine 44-px-Lücke.
           BEWUSST `v-if` MIT EIGENER EIGENSCHAFT (`devKnopf`, gesetzt in
           `App.vue`) statt eines Slots, der sich selbst ein-/ausblendet: der
           Platz in der Kopfzeile soll nur entstehen, wenn der Knopf wirklich
           da ist (sonst stünde am Handy eine leere 44-px-Lücke), und die
           Kopfzeile soll nicht am Dev-Zustand der App hängen. Die Bedingung
           steht damit an EINER Stelle (`devStartZeigen && istHandyLage` in
           App.vue) und ist im Quelltext nachprüfbar. -->
      <div v-if="devKnopf" class="dk-topbar-dev">
        <slot name="dev-knopf" />
      </div>
    </div>
  </header>
</template>

<script setup>
// LEISTE-1/2: der eine Menü-Knopf (auch auf Vollbild-Seiten verwendet).
import MenueKnopf from './MenueKnopf.vue'
import { computed } from 'vue'
import { currentPageName, navigate } from '../router.js'
import { rollenMarke } from '../composables/useBereichskopf.js'
import DkButton from './ui/DkButton.vue'
import DkSymbol from './ui/DkSymbol.vue'
import DkBadge from './ui/DkBadge.vue'
// LEISTE-1: die Glocke ist ein eigener Baustein — sie steht außer hier auch in
// der Seitenleiste und im Vollbild-Kopf der Nachrichten (eine Logik, drei Orte).
import Glocke from './Glocke.vue'
import { krumenZuSeite, verwaltungZutreffend, PERSONENVERWALTUNG_BASIS } from '../menue.js'
// CHAT-R2d: der Zurück-Weg ohne Verwaltungsrecht führt in die Personensuche
// (dort kommen die Profile im Chat her) — dieselbe Hilfe, die auch das
// Personenprofil benutzt.
import { sucheAdresse } from '../composables/nachrichtenDirekt.mjs'
import { useSession } from '../composables/useSession.js'

const props = defineProps({
  collapsed: Boolean,
  // UX3e: Zustand des Menü-Knopfes (`aria-expanded`) — er muss sagen, ob die
  // Schublade offen ist, sonst kündigt er sie falsch an (Prinzip N4/S4).
  menueOffen: { type: Boolean, default: false },
  // A10: Abzeichen neben dem Titel am Handy („Moderator“) — LEER, wenn die
  // Seite kein Recht gemeldet hat (dann gibt es kein Abzeichen und keinen
  // Platz dafür, Karte A10).
  rollenMarke: { type: String, default: '' },
  // DEVBADGE-1: In der Handy-Lage trägt die Kopfzeile den Dev-Einschaltknopf
  // (statt eines schwebenden Abzeichens). Der Platz entsteht nur, wenn der
  // Knopf wirklich da ist — sonst stünde am Handy eine leere Lücke.
  devKnopf: { type: Boolean, default: false },
})
// UX3f: `suche` öffnet die Befehlspalette (der Klick auf das Suchfeld).
defineEmits(['toggle-collapse', 'open-menu', 'suche'])

const page = currentPageName

// CHAT-R2d: die zwei Verwaltungsstufen der Sitzung für den Zurück-Weg aus dem
// Personenprofil — dieselbe Quelle wie Menü, Reiterzeile und Routen-Wächter.
// `useSession()` liefert die Refs als Eigenschaften; sie werden erst im
// `navigateBack()` gelesen (dort stehen die beiden Stufen).
const sitzung = useSession()

const CRUMB_MAP = {
  PlanrahmenPlan:       ['Pläne', 'Plan'],
  PlanrahmenEinrichten: ['Pläne', 'Einrichten'],
  PlanrahmenPlantypEditor: ['Pläne', 'Planvorlage bearbeiten'],
  PlanrahmenStammdaten: ['Pläne', 'Stammdaten'],
  MitgliedDetail:['Mitglieder', 'Profil'],
  GruppeDetail:  ['Gruppen', 'Detail'],
  KalenderImport:['Kalender', 'Import'],
  LiedNeu:       ['Lieder', 'Neu'],
  LiedDetail:    ['Lieder', 'Detail'],
  LiedgruppeDetail: ['Liedgruppen', 'Detail'],
  Profile:       ['Profil'],
  // UXM-R14: Seiten ohne Menüeintrag zeigten den rohen Komponentennamen.
  // Sie bekommen hier ihren Lesetext — „Registrierung“ heißt wie die Seite,
  // nicht „Anmeldungen“. Die alte Seite „Anmeldung“ ist mit N12 entfallen
  // (ihre Einstellungen liegen unter „Einstellungen → Anmeldung“).
  Registrierung: ['Mitglieder', 'Registrierung'],
  // UX3j (A3, Punkt 4): Die Reiter von „Personen“ tragen oben „Personen“ —
  // vorher stand dort der rohe Komponentenname („MitgliederAnfragen“).
  // Die Seitennamen selbst bleiben (Anker für Rechte-Guard und Fenstertitel).
  // CHAT-R2a (Chat-Konzept 10.1 Punkt 5): Die Personen-Reiter sind jetzt Teil
  // der EINSTELLUNGEN — der Bereich ist umgezogen, die Adressen sind geblieben.
  // Die Brotkrumen nennen deshalb den Ort, an dem man sie heute findet;
  // „Personenprofil“ (`MitgliedDetail`) heißt weiter „Personen“, denn das
  // Profil einer Person bleibt das Profil einer Person (10.2, Tabelle).
  // CHAT-R2a-2 (Punkt f): ALLE Personen-Reiter tragen EINHEITLICH
  // „Einstellungen › Personenverwaltung“ — auch „Übersicht“, „Löschanträge“,
  // die eingebettete Liste (`Personen`, `MitgliederListe`) und der Abschnitt
  // selbst. Fachliche Untertitel („Löschanträge“) gibt es NICHT mehr: sie
  // zeigten für dieselbe Ebene zwei verschiedene Wege an (Review-Befund).
  MitgliederAnfragen:    ['Einstellungen', 'Personenverwaltung'],
  MitgliederDatenschutz: ['Einstellungen', 'Personenverwaltung'],
  MitgliederImport:      ['Einstellungen', 'Personenverwaltung'],
  MitgliederLoeschantraege: ['Einstellungen', 'Personenverwaltung'],
  MitgliederUebersicht:  ['Einstellungen', 'Personenverwaltung'],
  MitgliederListe:       ['Einstellungen', 'Personenverwaltung'],
  EinstellungenPersonenverwaltung: ['Einstellungen', 'Personenverwaltung'],
  // Die alte Bereichsadresse `#/personen/*` bleibt erreichbar; auch dort
  // nennt die Brotkrume den Ort des Bereichs (kein roher Seitenname).
  Personen:              ['Einstellungen', 'Personenverwaltung'],
  Wiki:          ['Wiki'],
  NichtGefunden: ['Seite nicht gefunden'],
}

// Brotkrumen aus der zentralen Menüdefinition (Standard S12). Der Rückfall
// liefert IMMER einen Lesetext — nie einen internen Komponentennamen.
const breadcrumbs = computed(() => CRUMB_MAP[page.value] || krumenZuSeite(page.value) || ['Übersicht'])

const showBack = computed(() => ['MitgliedDetail', 'GruppeDetail'].includes(page.value))

function navigateBack() {
  // CHAT-R2d (Operator-Review R1): Der Zurück-Weg richtet sich nach dem RECHT
  // der Sitzung, nicht nach der Seite. Die Personenverwaltung lebt in den
  // Einstellungen (`#/einstellungen/personenverwaltung`) — dorthin gehört die
  // Verwaltung. Ein MITGLIED, das ein Profil aus dem Chat geöffnet hat, landete
  // dort auf dem Dashboard (der Wächter schließt den Abschnitt): es kommt
  // dorthin zurück, wo es herkam — in die Personensuche der Nachrichten.
  //
  // Das Recht kommt aus der VORHANDENEN Hilfe (`verwaltungZutreffend` über
  // `useSession`), nicht aus einer zweiten Rechnung. Während einer
  // Identitätsübernahme liefert `useSession` das Konto (fail closed).
  if (page.value === 'MitgliedDetail') {
    const recht = verwaltungZutreffend('personen', {
      istAdmin: sitzung.isAdmin.value === true,
      istMitgliederverwaltung: sitzung.istMitgliederverwaltung.value === true,
    })
    navigate(recht ? PERSONENVERWALTUNG_BASIS : sucheAdresse())
  } else if (page.value === 'GruppeDetail') navigate('#/gruppen')
}
</script>
