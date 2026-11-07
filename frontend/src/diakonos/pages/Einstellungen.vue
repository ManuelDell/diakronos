<template>
  <div class="dk-screen dk-screen-enter">
    <DkPageHeader title="Einstellungen" sub="Gemeinde und Technik verwalten." />

    <!-- UX3h: Einstellungen = Kategorien + Suche (Entwurf A6, Prinzip N8).
         Die Suche steht ÜBER der Liste und filtert BEIDES: die Bereiche
         (Stichworte je Abschnitt) und die Feldnamen. Ein Treffer in einem
         Feld führt nicht nur zum Bereich, sondern zum FELD — die Auswahl
         bleibt stehen, bis der Nutzer sie aufhebt („Alle Bereiche“). -->
    <div class="ei-bereich">
      <div class="ei-navi">
        <div class="ei-suche">
          <label class="ei-suche-feld" for="ei-suche-eingabe">
            <span class="ei-suche-sr">Einstellungen durchsuchen</span>
            <svg class="ei-suche-symbol" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
              <circle cx="10.5" cy="10.5" r="6.5" fill="none" stroke="currentColor" stroke-width="1.8" />
              <path d="M15.5 15.5 L20 20" fill="none" stroke="currentColor" stroke-width="1.8"
                stroke-linecap="round" />
            </svg>
            <input
              id="ei-suche-eingabe"
              v-model="begriff"
              class="ei-suche-eingabe"
              type="text"
              autocomplete="off"
              role="searchbox"
              placeholder="Einstellungen durchsuchen"
              @keydown.escape="sucheLeeren"
            />
            <button
              v-if="begriff"
              type="button"
              class="ei-suche-loeschen"
              aria-label="Suche leeren"
              @click="sucheLeeren"
            >×</button>
          </label>
        </div>

        <!-- Ergebnis der Suche: erst die Bereiche, je Bereich die Felder.
             Kein Karte-in-Karte (Prinzip Ä2): die Liste ist eine Navigation
             auf dem Grund, getrennt durch Abstand. -->
        <nav class="ei-liste" :aria-label="begriff ? 'Suchtreffer' : 'Abschnitte'">
          <p v-if="begriff" class="ei-suche-stand" role="status">
            {{ anzahlTreffer === 1 ? '1 Bereich passt.' : anzahlTreffer + ' Bereiche passen.' }}
          </p>

          <p v-if="begriff && anzahlTreffer === 0" class="ei-suche-leer">
            Kein Bereich und kein Feld enthält „{{ begriff }}“.
            <button type="button" class="ei-suche-alle" @click="sucheLeeren">Alle Bereiche zeigen</button>
          </p>

          <div v-for="g in sichtbareGruppen" :key="g.id" class="ei-gruppe">
            <p class="ei-gruppe-titel">{{ g.titel }}</p>
            <div v-for="a in g.eintraege" :key="a.id" class="ei-eintrag-block">
              <a
                class="ei-eintrag"
                :class="{ 'is-active': a.id === aktiverAbschnitt }"
                :href="a.href"
                :aria-current="a.id === aktiverAbschnitt ? 'page' : undefined"
                @click="trefferMerken(a.id)"
              >{{ a.label }}</a>
              <ul v-if="feldTreffer(a.id).length" class="ei-felder">
                <li v-for="f in feldTreffer(a.id)" :key="f.id">
                  <a class="ei-feld" :href="feldZiel(a, f)">{{ f.label }}</a>
                </li>
              </ul>
            </div>
          </div>


        </nav>
      </div>

      <div class="ei-inhalt">
        <component :is="inhalt" embedded />
      </div>
    </div>
  </div>
</template>

<script setup>
/**
 * Einstellungen — ein Ort für Gemeinde und Technik (Neuordnung N8/N9).
 * Links die Bereiche in fünf Gruppen, rechts der Inhalt; am Handy werden die
 * Gruppen gestapelt. Jeder Bereich hat eine eigene Adresse
 * (#/einstellungen/...).
 *
 * UX3h — Gruppen + Suche (Entwurf A6):
 *   * Fünf Gruppen nach dem Entwurf: Gemeinde · Zugang · Kommunikation ·
 *     Datenschutz · Erweitert. Die frühere Sammelgruppe „Einstellungen“ ist
 *     weg (ein Wort für elf Bereiche sagt nichts — Prinzip N1/N3).
 *   * Suchfeld oben. Es filtert Bereiche UND Feldnamen; bei einem Feldtreffer
 *     steht der Feldname unter dem Bereich und springt direkt hin (Prinzip
 *     N7: Treffer zeigen ihren Ort). Die Ordnung und die Stichworte stehen in
 *     `./suche.mjs` — ohne Vue prüfbar.
 *   * Ein Suchbegriff, der nichts trifft, sagt das und bietet den Weg zurück
 *     (Zustand „leer“ ist gestaltet, Prinzip I5).
 *
 * Ein Feldtreffer führt auf `#/einstellungen/<bereich>/<feld>`: der Abschnitt
 * springt beim Anzeigen zu der Kennung `dk-sprung-<feld>` (siehe `sprung.mjs`
 * und die Abschnitte, die ihre Felder damit auszeichnen). Fehlt die Kennung,
 * landet man im Bereich selbst — kein Fehler, nur die gröbere Antwort.
 */
import { computed, defineAsyncComponent, nextTick, onMounted, ref, watch } from 'vue'
import { currentPageName, getRouteParam } from '../router.js'
import DkPageHeader from '../components/ui/DkPageHeader.vue'
import { GRUPPEN, STICHWORTE, gruppiere, trefferBereiche, trefferFelder } from './einstellungen/suche.mjs'
import { feldAusAdresse, SPRUNG_WARTE_MS, sprungZiel, springeZu } from './sprung.mjs'

const GEMEINDE = defineAsyncComponent(() => import('./einstellungen/Gemeinde.vue'))
const ANMELDUNG = defineAsyncComponent(() => import('./einstellungen/Anmeldung.vue'))
const ROLLEN = defineAsyncComponent(() => import('./einstellungen/RollenRechte.vue'))
const DEVMODUS = defineAsyncComponent(() => import('./einstellungen/DevModus.vue'))
const REGISTRIERUNG = defineAsyncComponent(() => import('./einstellungen/Registrierung.vue'))
const DATENSCHUTZ = defineAsyncComponent(() => import('./einstellungen/DatenschutzTexte.vue'))
// BACKUP-1: die eigene Datensicherung. Der Server laesst nur System Manager
// hinein; sichtbar ist der Bereich fuer Administratoren (Komfort).
const DATENSICHERUNG = defineAsyncComponent(() => import('./einstellungen/Datensicherung.vue'))
// UX2b: Papierkorb — geloeschte Eintraege der letzten 7 Tage zurueckholen.
// Der Server laesst nur Administration hinein.
const PAPIERKORB = defineAsyncComponent(() => import('./einstellungen/Papierkorb.vue'))
// MAIL-1: Mailversand (SMTP-Postfach). Der Server laesst nur System Manager
// hinein; sichtbar ist der Bereich fuer Administratoren (Komfort).
const MAILVERSAND = defineAsyncComponent(() => import('./einstellungen/Mailversand.vue'))
// WEB-3: Zustand der optionalen Anbindung des Website-Baukastens + Kurzanleitung.
// Nur Anzeige — eingeschaltet wird sie über settings/.env (der Betrieb).
const WEBSITE = defineAsyncComponent(() => import('./einstellungen/Website.vue'))
// UX1k: Abstände, Rahmen und Rundungen (nur System Manager — Server prüft).
const GESTALTUNG = defineAsyncComponent(() => import('./einstellungen/Gestaltung.vue'))

/**
 * Die Bereiche mit ihrer GRUPPE (UX3h, Entwurf A6).
 *
 * Zuordnung nach dem Entwurf: „Gemeinde“ (Gemeinde, Website) · „Zugang“
 * (Anmeldung, Registrierung, Rollen & Rechte) · „Kommunikation“ (Mailversand)
 * · „Datenschutz“ (Texte, Datensicherung) · „Erweitert“ (Gestaltung,
 * Entwicklermodus). Papierkorb steht bei Datenschutz — er ist die Frist-Seite
 * der Datensicherung, keine eigene Kategorie.
 */
const abschnitte = [
  { id: 'gemeinde', label: 'Gemeinde', href: '#/einstellungen/gemeinde',
    seite: 'EinstellungenGemeinde', inhalt: GEMEINDE, gruppe: 'gemeinde' },
  // ON-4 (Nachtrag Orchestrator 2026-11-03): KEIN eigener Bereich
  // „Einrichtung“. Nach der Ersteinrichtung werden alle Angaben AUSSCHLIESSLICH
  // in den Einstellungen gepflegt (Gemeinde, Mailversand, Module …); die
  // „Einrichten“-Knöpfe führen genau dorthin (Ziel aus `einrichtung.status`).
  //
  // WEB-3/UX3a: der Website-Baukasten beschreibt eine Anbindung, steht aber
  // nach Entwurf A6 bei „Gemeinde“ — er zeigt, unter welcher Adresse die
  // Gemeinde im Netz erscheint.
  { id: 'website', label: 'Website-Baukasten', href: '#/einstellungen/website',
    seite: 'EinstellungenWebsite', inhalt: WEBSITE, gruppe: 'gemeinde' },
  { id: 'anmeldung', label: 'Anmeldung', href: '#/einstellungen/anmeldung',
    seite: 'EinstellungenAnmeldung', inhalt: ANMELDUNG, gruppe: 'zugang' },
  { id: 'registrierung', label: 'Registrierung', href: '#/einstellungen/registrierung',
    seite: 'EinstellungenRegistrierung', inhalt: REGISTRIERUNG, gruppe: 'zugang' },
  { id: 'rollen', label: 'Rollen & Rechte', href: '#/einstellungen/rollen',
    seite: 'EinstellungenRollen', inhalt: ROLLEN, gruppe: 'zugang' },
  // MAIL-1: „Mailversand“ ist die einzige Stelle, an der die App selbst
  // schreibt — eigene Gruppe „Kommunikation“ (Entwurf A6).
  { id: 'mailversand', label: 'Mailversand', href: '#/einstellungen/mailversand',
    seite: 'EinstellungenMailversand', inhalt: MAILVERSAND, gruppe: 'kommunikation' },
  { id: 'datenschutz', label: 'Datenschutz-Texte', href: '#/einstellungen/datenschutz',
    seite: 'EinstellungenDatenschutz', inhalt: DATENSCHUTZ, gruppe: 'datenschutz' },
  // BACKUP-1: „Datensicherung“ steht neben den Datenschutz-Texten — beides
  // betrifft die Aufbewahrung von Personendaten.
  { id: 'datensicherung', label: 'Datensicherung', href: '#/einstellungen/datensicherung',
    seite: 'EinstellungenDatensicherung', inhalt: DATENSICHERUNG, gruppe: 'datenschutz' },
  // UX2b: „Papierkorb“ steht neben der Datensicherung — beides betrifft
  // geloeschte Daten und ihre Frist.
  { id: 'papierkorb', label: 'Papierkorb', href: '#/einstellungen/papierkorb',
    seite: 'EinstellungenPapierkorb', inhalt: PAPIERKORB, gruppe: 'datenschutz' },
  // UX1k: Gestaltung steht unter „Erweitert“ — sie ändert die Maße für ALLE
  // Nutzer und ist deshalb seltenes Handwerkszeug, keine Alltagseinstellung
  // (Prinzip K2/N3). Nur System Manager sehen sie; der Server verweigert
  // zusätzlich mit 403.
  { id: 'gestaltung', label: 'Gestaltung', href: '#/einstellungen/gestaltung',
    seite: 'EinstellungenGestaltung', inhalt: GESTALTUNG,
    gruppe: 'erweitert', nurSystemManager: true },
  // Entscheidung 10: Dev-Modus ist der letzte Abschnitt. Er ist nur sichtbar,
  // wenn die Instanz ihn zulaesst (Konzept §7) — der Server entscheidet.
  { id: 'dev-modus', label: 'Entwicklermodus', href: '#/einstellungen/dev-modus',
    seite: 'EinstellungenDevModus', inhalt: DEVMODUS, gruppe: 'erweitert', nurDevmodus: true },
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

// ── Suche ────────────────────────────────────────────────────────────────
/**
 * Der Suchbegriff. Er liegt ZUSÄTZLICH in `sessionStorage`: App.vue zeichnet
 * die Seite bei jedem Adresswechsel neu (`:key="currentHash"`), und genau das
 * passiert beim Klick auf einen Treffer. Ein Begriff nur im `ref` wäre danach
 * weg — und mit ihm die Trefferliste, aus der man gerade gekommen ist
 * (Zurück-Navigation landete in der vollen Liste). gelesen wird beim Aufbau,
 * geschrieben bei jeder Änderung; `sessionStorage` kann fehlen (Privatmodus,
 * jsdom) → try/catch, dann gilt nur der Speicher dieser Seite.
 *
 * Kein Tastenkürzel: Strg+K gehört der Befehlspalette (Karte UX3f). Escape im
 * Feld leert die Suche — das erledigt das Feld selbst.
 */
const BEGRIFF_SCHLUESSEL = 'dk-einstellungen-suche'

function gespeicherterBegriff() {
  try {
    return window.sessionStorage?.getItem(BEGRIFF_SCHLUESSEL) || ''
  } catch {
    return ''
  }
}

const begriff = ref(gespeicherterBegriff())

watch(begriff, (wert) => {
  try {
    if (wert) window.sessionStorage?.setItem(BEGRIFF_SCHLUESSEL, wert)
    else window.sessionStorage?.removeItem(BEGRIFF_SCHLUESSEL)
  } catch {
    // Kein Speicher (Privatmodus/jsdom): der Begriff gilt nur auf dieser Seite.
  }
})

/** Zuletzt angesprungener Bereich — bleibt markiert, bis die Suche endet. */
// Wie der Begriff in sessionStorage: die Seite wird je Klick neu aufgebaut.
const TREFFER_SCHLUESSEL = BEGRIFF_SCHLUESSEL + ':treffer'
const gemerkterTreffer = ref((() => {
  try { return begriff.value ? (window.sessionStorage?.getItem(TREFFER_SCHLUESSEL) || '') : '' } catch { return '' }
})())
watch(gemerkterTreffer, (wert) => {
  try {
    if (wert) window.sessionStorage?.setItem(TREFFER_SCHLUESSEL, wert)
    else window.sessionStorage?.removeItem(TREFFER_SCHLUESSEL)
  } catch {
    // Kein Speicher: die Markierung gilt nur auf dieser Seite.
  }
})

function sucheLeeren() {
  begriff.value = ''
  gemerkterTreffer.value = ''
}

const treffer = computed(() => trefferBereiche(sichtbareAbschnitte.value, begriff.value))
const anzahlTreffer = computed(() => treffer.value.size)

function feldTreffer(id) {
  return begriff.value ? (treffer.value.get(id)?.felder || []) : []
}

/**
 * Ziel eines Feldtreffers: der Bereich MIT Sprungmarke. Der Abschnitt setzt
 * die Kennung selbst an sein Feld (`dk-sprung-<id>`); der Sprung wird nach dem
 * Wechsel nachgeholt (`sprungNachholen`) — ein reiner Fragment-Link würde im
 * Hash-Router die Adresse verfälschen.
 */
function feldZiel(a, f) {
  return sprungZiel(a.href, f.id)
}

/**
 * Aktiver Bereich. Drei Wege führen hierher, in dieser Reihenfolge:
 *   1. eine gemerkte Auswahl in der Suche (`gemerkterTreffer`) — sie gewinnt,
 *      solange die Suche läuft, auch wenn schon ein FELD angesprungen ist;
 *   2. die Bereichsadresse (`#/einstellungen/gemeinde`) → Seite = Bereich,
 *   3. ein Feldtreffer (`#/einstellungen/<bereich>/<feld>`) → Router nennt die
 *      Seite „Einstellungen“ und reicht den Bereich als `bereich` mit (UX3h).
 *      Ohne diesen dritten Weg blieb bei einem Feldtreffer der ERSTE Bereich
 *      stehen — der Sprung ins Feld lief dann ins Leere (im Stack gemessen).
 * Geprüft wird gegen `sichtbareAbschnitte`: ein Bereich, den diese Sitzung
 * nicht sehen darf (Entwicklermodus aus, kein System Manager), wird nicht
 * aktiv — sonst stünde ein unsichtbarer Eintrag als „aktiv“ in der Liste.
 */
const aktiverAbschnitt = computed(() => {
  if (gemerkterTreffer.value
    && sichtbareAbschnitte.value.some(a => a.id === gemerkterTreffer.value)) {
    return gemerkterTreffer.value
  }
  const trefferAbschnitt = abschnitte.find(a => a.seite === currentPageName.value)
  if (trefferAbschnitt) return trefferAbschnitt.id
  const ausAdresse = getRouteParam('bereich', 'Einstellungen')
  if (ausAdresse && sichtbareAbschnitte.value.some(a => a.id === ausAdresse)) return ausAdresse
  return (sichtbareAbschnitte.value[0] || abschnitte[0]).id
})

/**
 * Gruppen der Liste. Ohne Suchbegriff: alle Gruppen in der Reihenfolge des
 * Entwurfs. MIT Suchbegriff: nur Gruppen mit Treffern — die Gruppe fällt weg,
 * wenn sie nichts trifft (kein leerer Gruppenkopf).
 */
const sichtbareGruppen = computed(() => {
  const quelle = begriff.value
    ? sichtbareAbschnitte.value.filter(a => treffer.value.has(a.id))
    : sichtbareAbschnitte.value
  return gruppiere(quelle).map(g => ({ ...g, titel: titelDerGruppe(g.id) }))
})

function titelDerGruppe(id) {
  return (GRUPPEN.find(g => g.id === id) || { titel: id }).titel
}

// Stichworte sind die Grundlage der Suche — hier nur, damit ein Tippfehler in
// der Zuordnung sofort auffällt (jeder sichtbare Bereich hat welche).
const ohneStichworte = computed(() => sichtbareAbschnitte.value.filter(a => !STICHWORTE[a.id]))
if (import.meta.env?.DEV && ohneStichworte.value.length) {
  console.warn('Einstellungen: Bereich ohne Stichworte:', ohneStichworte.value.map(a => a.id))
}

// Nach einem Feldtreffer: der Inhalt ist asynchron geladen — die Sprungmarke
// gibt es erst danach. Deshalb einmal nach dem Wechsel danach suchen. Auch
// beim ERSTEN Anzeigen (Lesezeichen auf ein Feld), nicht nur beim Wechsel.
async function sprungPruefen() {
  const feld = feldAusAdresse(window.location.hash)
  if (!feld) return
  await nextTick()
  // Kurz warten: der Bereich selbst lädt seine Daten erst (Skelett → Formular).
  setTimeout(() => springeZu(feld), SPRUNG_WARTE_MS)
}
watch(() => currentPageName.value, sprungPruefen)
onMounted(sprungPruefen)

function trefferMerken(id) {
  gemerkterTreffer.value = id
}

const inhalt = computed(() =>
  (abschnitte.find(a => a.id === aktiverAbschnitt.value) || abschnitte[0]).inhalt)
</script>

<style scoped>
.ei-bereich {
  display: grid;
  /* 248 px nach Entwurf A6 (der Entwurf setzt das Suchfeld 248 px breit an).
     240 px reichten für „Einstellungen durchsuchen“ in 12 px NICHT: der
     Platzhalter wurde abgeschnitten (Review 06.11., Punkt 5). Die Spalte
     wächst, nicht der Text — A6 schreibt den Wortlaut vor. */
  grid-template-columns: 248px minmax(0, 1fr);
  gap: var(--gap);
  align-items: start;
}

/* Die Navigation (Suchfeld + Liste) ist KEINE Karte in einer Karte
   (Prinzip Ä2): getönte Fläche, sanfter Schatten, kein Rahmen. */
.ei-navi {
  display: flex;
  flex-direction: column;
  gap: var(--sp-4);
  min-width: 0;
  padding: var(--pad);
  background: var(--surface-2);
  border-radius: var(--radius-lg);
  box-shadow: var(--schatten-karte);
}

/* ── Suchfeld ────────────────────────────────────────────────────────── */
/* A6/UX1d: Fläche + sanfter Schatten statt Rahmen (Ä2). Der Rahmen bleibt
   als durchsichtige Linie erhalten, damit der Fokus-Wechsel die Höhe nicht
   verschiebt; sichtbar wird er erst beim Fokus. */
.ei-suche-feld {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  height: var(--control-h-lg);
  padding: 0 var(--sp-3);
  background: var(--surface);
  border: var(--rahmen-breite) solid transparent;
  border-radius: var(--radius);
  box-shadow: var(--schatten-eingabe);
  transition: border-color var(--fast) var(--ease), box-shadow var(--fast) var(--ease);
}
.ei-suche-feld:focus-within {
  border-color: var(--focus-ring);
  box-shadow: 0 0 0 var(--ring-breite) var(--focus-ring);
}
/* Symbol mittig zur Textzeile (Auflage Manuel 2026-11-04): feste Größe je
   Schriftstufe, `align-items:center` der Zeile, keine Grundlinien-Tricks. */
.ei-suche-symbol {
  width: var(--icon-md);
  height: var(--icon-md);
  flex: 0 0 auto;
  color: var(--muted);
}
.ei-suche-eingabe {
  flex: 1 1 auto;
  min-width: 0;
  height: 100%;
  border: 0;
  background: transparent;
  color: var(--text);
  font-family: inherit;
  /* 12 px wie im Entwurf A6: der Platzhalter „Einstellungen durchsuchen“
     (25 Zeichen) braucht damit ~151 px statt ~176 px. Die Eingabe selbst
     bleibt eine Ebene unter den Einträgen (14 px) — das Suchfeld ist Werkzeug,
     nicht Inhalt. */
  font-size: var(--fs-xs);
}
.ei-suche-eingabe::placeholder { color: var(--subtle); }
.ei-suche-eingabe:focus { outline: none; }
.ei-suche-sr {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip-path: inset(50%);
  white-space: nowrap;
}
.ei-suche-loeschen {
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: var(--icon-lg);
  height: var(--icon-lg);
  padding: 0;
  border: 0;
  border-radius: var(--badge-r);
  background: transparent;
  color: var(--muted);
  font-size: var(--fs-md);
  line-height: 1;
  cursor: pointer;
}
.ei-suche-loeschen:hover { background: var(--surface-hover); color: var(--text); }

/* ── Liste ───────────────────────────────────────────────────────────── */
.ei-liste {
  display: flex;
  flex-direction: column;
  gap: var(--sp-4);
  min-width: 0;
}
.ei-gruppe { display: flex; flex-direction: column; gap: var(--sp-1); }
.ei-gruppe-titel {
  margin: 0;
  padding: 0 var(--sp-2);
  color: var(--muted);
  font-size: var(--fs-xs);
  font-weight: var(--fw-fett);
  text-transform: uppercase;
  letter-spacing: .04em;
}
.ei-eintrag-block { display: flex; flex-direction: column; gap: var(--sp-1); }
.ei-eintrag,
.ei-feld {
  display: flex;
  align-items: center;
  min-height: var(--control-h-lg);
  padding: 0 var(--sp-2);
  border-radius: var(--radius-sm);
  color: var(--muted);
  text-decoration: none;
  font-weight: var(--fw-mittel);
  font-size: var(--fs);
}
.ei-eintrag:hover,
.ei-feld:hover { color: var(--text); background: var(--surface-hover); }
/* A6 (Review 06.11.): Der aktive Eintrag ist NICHT die volle Primärfläche —
   sonst konkurriert er mit dem einen Primärknopf der Ansicht (Prinzip K1).
   Stattdessen: Primärfarbe als Text, leise getönte Fläche, ein schmaler
   Primärbalken links (Box-shadow, damit er keinen Platz verschiebt) und
   fette Schrift. Der Balken trägt die Markierung auch ohne Farbwahrnehmung
   (Prinzip Ä4) und die Fläche ist kein Knopf-Look. */
.ei-eintrag.is-active {
  color: var(--primary);
  background: var(--accent-soft);
  box-shadow: inset var(--ring-breite) 0 0 var(--primary);
  font-weight: var(--fw-fett);
}
.ei-eintrag:focus-visible,
.ei-feld:focus-visible,
.ei-suche-alle:focus-visible {
  outline: var(--rahmen-breite) solid var(--focus-ring);
  outline-offset: var(--ring-breite);
}

/* Feldtreffer: eine Ebene tiefer, kleiner, mit Einzug (Prinzip S3: Nähe). */
.ei-felder {
  list-style: none;
  margin: 0;
  padding: 0 0 0 var(--sp-3);
  display: flex;
  flex-direction: column;
}
.ei-feld {
  min-height: var(--control-h-lg);
  font-size: var(--fs-sm);
  font-weight: var(--fw-normal);
  color: var(--subtle);
}

.ei-suche-stand {
  margin: 0;
  padding: 0 var(--sp-2);
  color: var(--muted);
  font-size: var(--fs-sm);
}
.ei-suche-leer {
  margin: 0;
  padding: var(--sp-2);
  color: var(--muted);
  font-size: var(--fs-sm);
  line-height: 1.5;
}
.ei-suche-alle {
  display: inline-flex;
  align-items: center;
  min-height: var(--control-h-lg);
  padding: 0;
  border: 0;
  background: transparent;
  color: var(--link);
  font: inherit;
  text-decoration: underline;
  cursor: pointer;
}
.ei-suche-alle:hover { color: var(--link-hover); }

/* Am Handy stehen Suchfeld und Liste VOR dem Inhalt (erst finden, dann
   lesen) — dieselbe eine Breitengrenze wie im Rest der App. */
@media (max-width: 720px) {
  .ei-bereich { grid-template-columns: 1fr; }
  .ei-eintrag,
  .ei-feld,
  .ei-suche-alle { min-height: var(--control-h); }
}
</style>
