<template>
  <div class="dk-widget-card dk-widget-full">
    <div class="dk-quick-row">
      <button v-for="link in links" :key="link.href" class="dk-quick-card" @click="navigate(link.href)">
        <!-- SEC-9: `v-html` bekommt hier AUSSCHLIESSLICH eine fest
             einprogrammierte SVG-Konstante — nie ein Feld des Schleifen-
             objekts, nie einen Serverwert. Aufgelöst wird über die
             geschlossene Zuordnung `SYMBOLE` mit einem LITERAL-Schlüssel.
             Wächter: frontend/tests/sec9-ausgabe-waechter.test.mjs -->
        <div class="dk-quick-icon" v-html="SYMBOLE[link.symbol]" />
        <div>
          <div class="dk-quick-title">{{ link.title }}</div>
          <div class="dk-quick-desc">{{ link.desc }}</div>
        </div>
      </button>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useSession } from '../../composables/useSession'

// UI-R10: Die Kacheln führen in Bereiche. „Personen“ ist Personenbereich —
// dafür zählt die Mitgliederverwaltung mit (`istMitgliederverwaltung`).
const { isAdmin, istMitgliederverwaltung, istGast } = useSession()

/* SEC-9 (Stored-XSS, Defense-in-Depth): Die Symbole sind FEST einprogrammierte
   SVG-Konstanten. Die frühere Fassung legte den SVG-String ins
   `links`-Objekt und band `v-html="link.icon"` — damit hing die HTML-Ausgabe
   an einem Objektfeld statt an einer Konstante, und ein künftiger Serverwert
   an dieser Stelle wäre sofort ausführbar gewesen. Jetzt entscheidet ein
   fester Name (`symbol`) über eine geschlossene Zuordnung. */
const ICON_KALENDER = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>'
const ICON_PROFIL = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="8" r="4"/><path d="M4 21v-2a6 6 0 0 1 6-6h4a6 6 0 0 1 6 6v2"/></svg>'
const ICON_MITGLIEDER = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>'
const ICON_GRUPPEN = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>'
const ICON_DIENSTE = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 11l3 3L22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/></svg>'

/**
 * Geschlossene Zuordnung Name -> Konstante. Der Schlüssel ist ein fester
 * Bezeichner aus dem Quelltext, kein Serverwert; ein unbekannter Name ergibt
 * `undefined` und damit kein Markup.
 */
const SYMBOLE = {
  kalender: ICON_KALENDER,
  profil: ICON_PROFIL,
  mitglieder: ICON_MITGLIEDER,
  gruppen: ICON_GRUPPEN,
  dienste: ICON_DIENSTE,
}

function navigate(href) { window.location.hash = href }

const links = computed(() => {
  // UXD-R23: Gäste sahen „Gruppen“ und „Mitglieder“ — beide führen ins Leere
  // (der Server verweigert sie). Für Gäste bleiben nur Kalender und Profil.
  if (istGast.value) {
    return [
      { href: '#/kalender', symbol: 'kalender', title: 'Kalender', desc: 'Termine und Veranstaltungen.' },
      { href: '#/profile', symbol: 'profil', title: 'Mein Profil', desc: 'Deine Angaben und Einstellungen.' },
    ]
  }
  if (isAdmin.value || istMitgliederverwaltung.value === true) {
    return [
      { href: '#/personen', symbol: 'mitglieder', title: 'Personen', desc: 'Alle Personen suchen und verwalten.' },
      { href: '#/gruppen', symbol: 'gruppen', title: 'Gruppen & Dienste', desc: 'Mitarbeitende zu Bereichen zuordnen.' },
      { href: '#/kalender', symbol: 'kalender', title: 'Kalender', desc: 'Termine und Veranstaltungen verwalten.' },
    ]
  }
  return [
    { href: '#/kalender', symbol: 'kalender', title: 'Kalender', desc: 'Termine und Veranstaltungen.' },
    { href: '#/dienste/meine-dienste', symbol: 'dienste', title: 'Meine Dienste', desc: 'Wo du eingeteilt bist.' },
    { href: '#/gruppen', symbol: 'gruppen', title: 'Gruppen', desc: 'Deine Gruppen und Bereiche.' },
  ]
})
</script>
