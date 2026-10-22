<template>
  <div class="dk-screen dk-screen-enter">
    <DkPageHeader title="Einstellungen" sub="Gemeinde und Technik verwalten." />

    <div class="ei-bereich">
      <!-- Abschnittsliste. Jeder Abschnitt hat eine eigene Adresse, damit
           Lesezeichen und der Zurück-Knopf funktionieren. Nur Abschnitte mit
           Inhalt erscheinen — kein toter Eintrag. Der Dev-Modus erscheint nur,
           wenn die Instanz ihn zulässt (Konzept §7). -->
      <nav class="ei-liste" aria-label="Abschnitte">
        <a
          v-for="a in sichtbareAbschnitte"
          :key="a.id"
          class="ei-eintrag"
          :class="{ 'is-active': a.id === aktiverAbschnitt }"
          :href="a.href"
          :aria-current="a.id === aktiverAbschnitt ? 'page' : undefined"
        >{{ a.label }}</a>
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
// MAIL-1: Mailversand (SMTP-Postfach). Der Server laesst nur System Manager
// hinein; sichtbar ist der Abschnitt fuer Administratoren (Komfort).
const MAILVERSAND = defineAsyncComponent(() => import('./einstellungen/Mailversand.vue'))

// Reihenfolge wie in der Konzept-Vorgabe (§7): Gemeinde, Anmeldung,
// Rollen & Rechte, Registrierung, Datenschutz-Texte, Dev-Modus.
const abschnitte = [
  { id: 'gemeinde', label: 'Gemeinde', href: '#/einstellungen/gemeinde',
    seite: 'EinstellungenGemeinde', inhalt: GEMEINDE },
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
  // MAIL-1: „Mailversand“ steht bei der Technik — ohne Postfach kann die
  // Löschung auf Antrag nicht bestätigt werden.
  { id: 'mailversand', label: 'Mailversand', href: '#/einstellungen/mailversand',
    seite: 'EinstellungenMailversand', inhalt: MAILVERSAND },
  // Entscheidung 10: Dev-Modus ist der letzte Abschnitt. Er ist nur sichtbar,
  // wenn die Instanz ihn zulaesst (Konzept §7) — der Server entscheidet.
  { id: 'dev-modus', label: 'Dev-Modus', href: '#/einstellungen/dev-modus',
    seite: 'EinstellungenDevModus', inhalt: DEVMODUS, nurDevmodus: true },
]

// Der Dev-Modus-Eintrag erscheint nur, wenn die Instanz ihn eingeschaltet hat.
const devmodeAn = computed(() => Boolean(window.__DIakonosBOOT?.devmode))

const sichtbareAbschnitte = computed(() =>
  abschnitte.filter(a => !a.nurDevmodus || devmodeAn.value))

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
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
}
.ei-eintrag {
  padding: var(--sp-2) var(--sp-3);
  border-radius: var(--radius-sm);
  color: var(--muted);
  text-decoration: none;
  font-weight: 550;
}
.ei-eintrag:hover { color: var(--text); background: var(--surface-2); }
.ei-eintrag.is-active { color: var(--primary); background: var(--surface-2); }
@media (max-width: 720px) {
  .ei-bereich { grid-template-columns: 1fr; }
}
</style>
