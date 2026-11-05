<template>
  <div class="dk-screen dk-screen-enter">
    <DkPageHeader title="Einstellungen" sub="Gemeinde und Technik verwalten." />

    <div class="ei-bereich">
      <!-- Abschnittsliste. Jeder Abschnitt hat eine eigene Adresse, damit
           Lesezeichen und der Zurück-Knopf funktionieren. Nur Abschnitte mit
           Inhalt erscheinen — kein toter Eintrag. Der Dev-Modus erscheint nur,
           wenn die Instanz ihn zulässt (Konzept §7). -->
      <nav class="ei-liste" aria-label="Abschnitte">
        <div v-for="g in sichtbareGruppen" :key="g.id" class="ei-gruppe">
          <p class="ei-gruppe-titel">{{ g.titel }}</p>
          <a
            v-for="a in g.eintraege"
            :key="a.id"
            class="ei-eintrag"
            :class="{ 'is-active': a.id === aktiverAbschnitt }"
            :href="a.href"
            :aria-current="a.id === aktiverAbschnitt ? 'page' : undefined"
          >{{ a.label }}</a>
        </div>
      </nav>

      <div class="ei-inhalt">
        <component :is="inhalt" embedded />
      </div>
    </div>
  </div>
</template>

<script setup>
/**
 * Einstellungen — ein Ort für Gemeinde und Technik (Neuordnung N8/N9).
 * Links die Abschnitte, rechts der Inhalt; am Handy werden die Abschnitte
 * gestapelt. Jeder Abschnitt hat eine eigene Adresse (#/einstellungen/...).
 * Die Abschnitte kommen mit ihren Paketen: „Anmeldung (Login)“ (N8),
 * „Gemeinde“, „Registrierung“ und „Datenschutz-Texte“ (N9).
 */
import { computed, defineAsyncComponent } from 'vue'
import { currentPageName } from '../router.js'
import DkPageHeader from '../components/ui/DkPageHeader.vue'

const GEMEINDE = defineAsyncComponent(() => import('./einstellungen/Gemeinde.vue'))
const ANMELDUNG = defineAsyncComponent(() => import('./einstellungen/Anmeldung.vue'))
const ROLLEN = defineAsyncComponent(() => import('./einstellungen/RollenRechte.vue'))
const DEVMODUS = defineAsyncComponent(() => import('./einstellungen/DevModus.vue'))
const REGISTRIERUNG = defineAsyncComponent(() => import('./einstellungen/Registrierung.vue'))
const DATENSCHUTZ = defineAsyncComponent(() => import('./einstellungen/DatenschutzTexte.vue'))
// BACKUP-1: die eigene Datensicherung. Der Server laesst nur System Manager
// hinein; sichtbar ist der Abschnitt fuer Administratoren (Komfort).
const DATENSICHERUNG = defineAsyncComponent(() => import('./einstellungen/Datensicherung.vue'))
// UX2b: Papierkorb — geloeschte Eintraege der letzten 7 Tage zurueckholen.
// Der Server laesst nur Administration hinein.
const PAPIERKORB = defineAsyncComponent(() => import('./einstellungen/Papierkorb.vue'))
// MAIL-1: Mailversand (SMTP-Postfach). Der Server laesst nur System Manager
// hinein; sichtbar ist der Abschnitt fuer Administratoren (Komfort).
const MAILVERSAND = defineAsyncComponent(() => import('./einstellungen/Mailversand.vue'))
// WEB-3: Zustand der optionalen Primo-Anbindung + Kurzanleitung. Nur Anzeige —
// eingeschaltet wird sie über settings/.env (der Betrieb).
const WEBSITE = defineAsyncComponent(() => import('./einstellungen/Website.vue'))
// UX1k: Abstände, Rahmen und Rundungen (nur System Manager — Server prüft).
const GESTALTUNG = defineAsyncComponent(() => import('./einstellungen/Gestaltung.vue'))

// Reihenfolge wie in der Konzept-Vorgabe (§7): Gemeinde, Anmeldung,
// Rollen & Rechte, Registrierung, Datenschutz-Texte, Dev-Modus.
const abschnitte = [
  { id: 'gemeinde', label: 'Gemeinde', href: '#/einstellungen/gemeinde',
    seite: 'EinstellungenGemeinde', inhalt: GEMEINDE },
  // ON-4 (Nachtrag Orchestrator 2026-11-03): KEIN eigener Abschnitt
  // „Einrichtung“. Nach der Ersteinrichtung werden alle Angaben AUSSCHLIESSLICH
  // in den Einstellungen gepflegt (Gemeinde, Mailversand, Module …); die
  // „Einrichten“-Knöpfe führen genau dorthin (Ziel aus `einrichtung.status`).
  { id: 'anmeldung', label: 'Anmeldung (Login)', href: '#/einstellungen/anmeldung',
    seite: 'EinstellungenAnmeldung', inhalt: ANMELDUNG },
  { id: 'rollen', label: 'Rollen & Rechte', href: '#/einstellungen/rollen',
    seite: 'EinstellungenRollen', inhalt: ROLLEN },
  { id: 'registrierung', label: 'Registrierung', href: '#/einstellungen/registrierung',
    seite: 'EinstellungenRegistrierung', inhalt: REGISTRIERUNG },
  { id: 'datenschutz', label: 'Datenschutz-Texte', href: '#/einstellungen/datenschutz',
    seite: 'EinstellungenDatenschutz', inhalt: DATENSCHUTZ },
  // BACKUP-1: „Datensicherung“ steht direkt neben den Datenschutz-Texten —
  // beides betrifft die Aufbewahrung von Personendaten.
  { id: 'datensicherung', label: 'Datensicherung', href: '#/einstellungen/datensicherung',
    seite: 'EinstellungenDatensicherung', inhalt: DATENSICHERUNG },
  // UX2b: „Papierkorb“ steht neben der Datensicherung — beides betrifft
  // geloeschte Daten und ihre Frist.
  { id: 'papierkorb', label: 'Papierkorb', href: '#/einstellungen/papierkorb',
    seite: 'EinstellungenPapierkorb', inhalt: PAPIERKORB },
  // MAIL-1: „Mailversand“ steht bei der Technik — ohne Postfach kann die
  // Löschung auf Antrag nicht bestätigt werden.
  { id: 'mailversand', label: 'Mailversand', href: '#/einstellungen/mailversand',
    seite: 'EinstellungenMailversand', inhalt: MAILVERSAND },
  // WEB-3: „Website-Baukasten“ (UX3a) steht bei der Technik — es beschreibt eine
  // Anbindung, keine Gemeindeeinstellung. Der Abschnitt ist nur Anzeige.
  { id: 'website', label: 'Website-Baukasten', href: '#/einstellungen/website',
    seite: 'EinstellungenWebsite', inhalt: WEBSITE },
  // UX1k: Gestaltung steht unter „Erweitert“ — sie ändert die Maße für ALLE
  // Nutzer und ist deshalb seltenes Handwerkszeug, keine Alltagseinstellung
  // (Prinzip K2/N3). Nur System Manager sehen sie; der Server verweigert
  // zusätzlich mit 403.
  { id: 'gestaltung', label: 'Gestaltung', href: '#/einstellungen/gestaltung',
    seite: 'EinstellungenGestaltung', inhalt: GESTALTUNG,
    gruppe: 'Erweitert', nurSystemManager: true },
  // Entscheidung 10: Dev-Modus ist der letzte Abschnitt. Er ist nur sichtbar,
  // wenn die Instanz ihn zulaesst (Konzept §7) — der Server entscheidet.
  { id: 'dev-modus', label: 'Dev-Modus', href: '#/einstellungen/dev-modus',
    seite: 'EinstellungenDevModus', inhalt: DEVMODUS, nurDevmodus: true },
]

// Der Dev-Modus-Eintrag erscheint nur, wenn die Instanz ihn eingeschaltet hat.
const devmodeAn = computed(() => Boolean(window.__DIakonosBOOT?.devmode))

// UX1k: „Gestaltung“ sieht nur ein System Manager (die Rollenliste der
// Sitzung; dieselbe Entscheidung trifft der Server). Nur Komfort — kein
// zweiter Weg an der Serverprüfung vorbei.
const istSystemManager = computed(() => {
  const rollen = window.__DIakonosBOOT?.roles
  return Array.isArray(rollen) && rollen.includes('System Manager')
})

const sichtbareAbschnitte = computed(() =>
  abschnitte.filter(a => (!a.nurDevmodus || devmodeAn.value)
    && (!a.nurSystemManager || istSystemManager.value)))

// Gruppen für die Abschnittsliste (Prinzip N3: 3–7 je Gruppe; Seltenes unter
// „Erweitert“). Ohne Gruppenschlüssel gehören die Abschnitte zu „Einstellungen“.
const sichtbareGruppen = computed(() => {
  const reihenfolge = ['Einstellungen', 'Erweitert']
  const nach = new Map(reihenfolge.map(id => [id, []]))
  for (const a of sichtbareAbschnitte.value) {
    const id = a.gruppe || 'Einstellungen'
    if (!nach.has(id)) nach.set(id, [])
    nach.get(id).push(a)
  }
  return [...nach.entries()]
    .filter(([, liste]) => liste.length)
    .map(([id, liste]) => ({ id, titel: id, eintraege: liste }))
})

// Ohne eigene Unterseite (alte Adresse #/einstellungen) zeigt der Bereich die
// Gemeinde — der erste Abschnitt ist der Einstieg.
const aktiverAbschnitt = computed(() => {
  const treffer = abschnitte.find(a => a.seite === currentPageName.value)
  return (treffer || abschnitte[0]).id
})

const inhalt = computed(() =>
  (abschnitte.find(a => a.id === aktiverAbschnitt.value) || abschnitte[0]).inhalt)
</script>

<style scoped>
.ei-bereich {
  display: grid;
  grid-template-columns: 220px minmax(0, 1fr);
  gap: var(--gap);
  align-items: start;
}
.ei-liste {
  display: flex;
  flex-direction: column;
  gap: var(--sp-1);
  padding: var(--sp-2);
  background: var(--surface);
  /* UX1d (D2): Der Kasten um die Abschnittsliste war der äußere „Rahmen im
     Rahmen“ — die Liste ist eine Navigation, keine Karte in einer Karte.
     Getönte Fläche genügt; der Rahmen kommt nur aus der Einstellung. */
  border: var(--karte-rand) solid var(--rahmen-farbe);
  border-radius: var(--radius-lg);
}
.ei-eintrag {
  padding: var(--sp-2) var(--sp-3);
  border-radius: var(--radius-sm);
  color: var(--muted);
  text-decoration: none;
  font-weight: var(--fw-mittel);
}
.ei-gruppe { display: flex; flex-direction: column; gap: var(--sp-1); }
.ei-gruppe + .ei-gruppe { margin-top: var(--sp-3); }
.ei-gruppe-titel {
  margin: 0;
  padding: 0 var(--sp-3);
  color: var(--muted);
  font-size: var(--fs-xs);
  font-weight: var(--fw-fett);
  text-transform: uppercase;
  letter-spacing: .04em;
}
.ei-eintrag:hover { color: var(--text); background: var(--surface-2); }
.ei-eintrag.is-active { color: var(--primary); background: var(--surface-2); }
@media (max-width: 720px) {
  .ei-bereich { grid-template-columns: 1fr; }
}
</style>
