<template>
    <div class="dk-pub-page" :class="{ 'dk-pub-page--mit-bild': !!hintergrundBild }">
        <!-- REG-1a: Hintergrund des Formulars. Dekorativ (aria-hidden), nur ein
             Bild — der Pfad kommt vom Server und traegt den Token des Links. -->
        <div v-if="hintergrundBild" class="dk-pub-hintergrund" aria-hidden="true">
            <img :src="hintergrundBild" alt="" />
        </div>
        <div class="dk-pub-card">
            <!-- WEB-7 (U1, U6): toter Link / ohne Token — der Browser steht
                 schon auf dem Weg zur Hauptseite. Bis die Weiterleitung
                 greift, bleibt die Karte leer: keine Meldung, kein Token,
                 kein „Zurück“ auf eine Fehlerseite. -->
            <div v-if="umgeleitet" class="dk-pub-center" aria-hidden="true">&nbsp;</div>

            <!-- Fehler-Seite: NUR noch für Fälle mit Rückmeldung (U3) —
                 Rate-Limit, Serverfehler, zeitliche Grenze des Links. -->
            <div v-else-if="linkFehler" class="dk-pub-center">
                <div class="dk-pub-icon-large">🔒</div>
                <h1 class="dk-pub-title">Zugang nicht möglich</h1>
                <p class="dk-pub-muted">{{ linkFehler }}</p>
            </div>

            <!-- Erfolgsseite -->
            <div v-else-if="success" class="dk-pub-center">
                <div class="dk-pub-icon-large">✅</div>
                <h1 class="dk-pub-title">Anmeldung übermittelt!</h1>
                <p class="dk-pub-muted">
                    Vielen Dank! Deine Anmeldung wurde übermittelt.
                    Der Mitgliederadministrator prüft und bestätigt sie.
                </p>
            </div>

            <!-- Formular — REG-1b: EINE Anzeige, dieselbe Komponente zeigt die
                 Vorschau im Formular-Editor. Banner, Beschreibung und Felder
                 stehen dort; hier bleibt nur die Seite drumherum. -->
            <DkAnmeldeformular
                v-else
                :token="token"
                :felder="felder"
                :mit-kinder="mitKinder"
                :dokumente="dokumente"
                :texte="texte"
                :willkommenstext="willkommenstext"
                :beschreibung="beschreibung"
                :banner-bild="bannerBild"
                :titel="titel"
                :subtitel="subtitel"
                @erfolg="success = true"
            />
        </div>
    </div>
</template>

<script setup>
import { ref } from 'vue'
// WEB-7: Entscheidung „toter Link -> Hauptseite ohne Meldung“ (U1/U2).
import {
    brauchtWeiterleitung,
    weiterleitenZurHauptseite,
} from '../shared/linkziel.js'
// REG-1b: gemeinsame Anzeige des Anmeldeformulars (auch die Editor-Vorschau).
import DkAnmeldeformular from './components/DkAnmeldeformular.vue'

const token      = window.__diakronos?.token || ''
// WEB-7: `linkGrund` unterscheidet „der Link ist tot“ (Weiterleitung) von
// „die Person braucht eine Erklärung“ (Bremse, Serverfehler, zeitliche
// Grenze — U3). Die Einstufung kommt vom Server (`spa.py::_link_grund`).
const linkGrund  = window.__diakronos?.linkGrund || ''
const linkFehler = window.__diakronos?.linkFehler || ''

// WEB-7 (U1): ungültiger/deaktivierter Link oder Seite ohne `?token=` ->
// sofort auf die Wurzel der DOMAIN, ohne Meldung und ohne Token in der
// Konsole. `replace` ersetzt den Verlaufseintrag (U6): „Zurück“ landet nicht
// wieder auf der toten Seite.
const umgeleitet = weiterleitenZurHauptseite(
    brauchtWeiterleitung({ grund: linkGrund, tokenFehlt: !token }),
)
const felder     = window.__diakronos?.felder || []
const mitKinder  = window.__diakronos?.mitKinder || 0
const dokumente  = window.__diakronos?.dokumente || []
// N9b (H-1, M-1): die Einwilligungs-/Datenschutztexte kommen vom Server
// (window.__diakronos.texte, Quelle `gemeinde.wirksame_texte`) — reiner
// Text, NIE v-html. Es ist genau der Wortlaut, den der Server als Beleg
// speichert. Ist nichts gepflegt/veroeffentlicht, greifen die Server-
// Standardtexte; kommt das Objekt gar nicht an, zeigen wir nichts.
const texte      = window.__diakronos?.texte || {}
// REG-1a: Beschreibung und Bilder des Formulars (aus `window.__diakronos`,
// Quelle `registrierung.validate_token`). Die Bildpfade sind relativ und
// tragen den Token — die Bilder sind NUR ueber das Formular abrufbar.
const beschreibung = (window.__diakronos?.beschreibung || '').trim()
const bannerBild = window.__diakronos?.bannerBild || ''
const hintergrundBild = window.__diakronos?.hintergrundBild || ''
const willkommenstext = (window.__diakronos?.willkommenstext || '').trim()

const titel    = mitKinder ? 'Anmeldung' : 'Mitglied werden'
const subtitel = mitKinder
    ? 'Melde dich und deine Kinder an. Alle Daten werden sicher gespeichert.'
    : 'Registriere dich als Gemeindemitglied. Alle Daten werden sicher gespeichert.'

const success = ref(false)
</script>

<style>
/* Diakronos Public Page — Farben/Raumwerte kommen aus tokens.css (Import in
   main.js). Der frühere lokale :root-Block mit kopierten Token-WERTEN ist
   entfernt: tokens.css ist die einzige Quelle (Wächter-Test DS3).

   REG-1b: Die Stile des Formulars selbst (Kopf, Banner, Beschreibung,
   Felder, Kinder, DSGVO) stehen in `components/DkAnmeldeformular.vue` —
   dort, wo die Anzeige gebaut wird, weil dieselbe Anzeige auch im Editor
   als Vorschau laeuft. Hier bleibt nur der Seitenrahmen. */

.dk-pub-page {
  min-height: 100vh;
  background: var(--bg);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  font-family: var(--font);
  font-size: 14px;
  line-height: 1.5;
  color: var(--text);
  -webkit-font-smoothing: antialiased;
}

/* REG-1a: Hintergrundbild hinter der Karte.
   REG-1b (Punkt 4): Das Bild darf den Text nicht unlesbar machen. Die Karte
   selbst bleibt voll deckend (`--surface`) — der Formulartext steht also
   immer auf einer ruhigen Flaeche. Zusaetzlich liegt ein Schleier aus dem
   Hintergrund-Token ueber dem Bild, damit auch die Kartenkanten ruhig stehen.
   Keine neuen Farbwerte: nur Tokens. */
.dk-pub-page--mit-bild { position: relative; }

/* REG-1c (5): Vorschau-Hinweis — eigener Abstand nach unten, weil das Banner
   mit `-40px` (am Handy `-24px`) nach OBEN zieht. Ohne den Zuschlag lag die
   Unterkante des Hinweises unter dem Bildanfang: das Banner deckte ihn halb zu
   (gemessen in der Abnahme: Hinweis 163–215 px, Banner ab 191 px). Der
   Zuschlag entspricht genau dem negativen Rand des Banners, damit der Hinweis
   wieder frei steht. Nur in der Vorschau — die oeffentliche Seite hat keinen
   Hinweis. */
.dk-pub-koerper[data-vorschau] .dk-pub-vorschau-hinweis {
  margin-bottom: calc(var(--sp-4) + 40px);
}

/* Inhaltsumbruch, kein Layout: der Vorschau-Hinweis braucht den Ausgleich für
   den kleineren Banner-Abstand; die öffentliche Seite selbst bleibt zentriert
   ohne App-Rahmen. */
@media (max-width: 640px) {
  .dk-pub-koerper[data-vorschau] .dk-pub-vorschau-hinweis {
    /* Am Handy zieht das Banner nur 24 px nach oben (siehe `.dk-pub-banner`). */
    margin-bottom: calc(var(--sp-4) + 24px);
  }
}

.dk-pub-hintergrund {
  position: absolute;
  inset: 0;
  overflow: hidden;
  pointer-events: none;
}

.dk-pub-hintergrund img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  opacity: 0.3;
  filter: saturate(0.85);
}

.dk-pub-page--mit-bild::before {
  content: '';
  position: absolute;
  inset: 0;
  background: color-mix(in oklch, var(--bg) 82%, transparent);
  pointer-events: none;
}

.dk-pub-card {
  position: relative;
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-md);
  width: 100%;
  max-width: 520px;
  padding: 40px;
}

/* Inhaltsumbruch, kein Layout: Innenabstand der öffentlichen Karte, leiseres
   Hintergrundbild und dichterer Schleier (Lesbarkeit der Beschriftungen). */
@media (max-width: 640px) {
  .dk-pub-card { padding: 24px; }
  .dk-pub-page { padding: 16px; }
  /* Am Handy ist wenig Platz: Hintergrundbild leiser, Schleier dichter —
     die Beschriftungen der Felder bleiben so in jedem Fall lesbar. */
  .dk-pub-hintergrund img { opacity: 0.2; }
  .dk-pub-page--mit-bild::before {
    background: color-mix(in oklch, var(--bg) 90%, transparent);
  }
}

.dk-pub-center { text-align: center; }

.dk-pub-icon-large { font-size: 48px; margin-bottom: 16px; }

.dk-pub-title {
  font-size: 22px;
  font-weight: 600;
  color: var(--text);
  margin: 0 0 6px 0;
  letter-spacing: -0.01em;
}

.dk-pub-muted {
  font-size: 13px;
  color: var(--muted);
  margin: 0;
  line-height: 1.5;
}
</style>
