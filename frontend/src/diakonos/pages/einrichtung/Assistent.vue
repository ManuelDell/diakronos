<template>
  <!-- ON-3 (W1/W4): Einrichtungs-Assistent. Eigene Kopfzeile (Logo/Monogramm +
       „Einrichtung“ + „Speichern und später fortsetzen“), links die
       Schrittleiste (Desktop) bzw. „Schritt n von 6“ + Segment (Handy), unten
       die Fußleiste „Überspringen · Zurück · Weiter“. Nur Admin-Rollen — der
       Router schickt alle anderen auf die Übersicht, der Server prüft erneut. -->
  <div class="assistent">
    <!-- Kopfzeile -->
    <header class="assistent-kopf">
      <a class="assistent-marke" href="#/">
        <span class="assistent-monogramm" aria-hidden="true">{{ monogramm }}</span>
        <span class="assistent-marke-text">Diakronos</span>
      </a>
      <span class="assistent-trenner" aria-hidden="true"></span>
      <span class="assistent-bereich">Einrichtung</span>
      <button
        type="button"
        class="assistent-spaeter"
        :disabled="speichert"
        @click="spaeter"
      >
        Speichern und später fortsetzen
      </button>
    </header>

    <div class="assistent-koerper">
      <AssistentSchritte
        :schritte="schritte"
        :aktiv="schritt"
        :abgeschlossen="abgeschlossen"
        :fortschritt="fortschrittText"
        @gehe="wechsleZu"
        @zurueck="zurueck"
      />

      <main ref="haupt" class="assistent-haupt" tabindex="-1">
        <p v-if="laedt && !status" class="assistent-hinweis" role="status">Einrichtung wird geladen …</p>
        <div v-else-if="!status" class="assistent-karte">
          <p class="assistent-fehler" role="alert">{{ fehler || 'Die Einrichtung konnte nicht geladen werden.' }}</p>
          <DkButton variant="secondary" @click="ladeAssistent({ start: true })">Erneut laden</DkButton>
        </div>
        <div v-else class="assistent-karte">
          <p v-if="fehler" class="assistent-fehler" role="alert">{{ fehler }}</p>

          <SchrittGemeinde
            v-if="schritt === 'gemeinde'"
            :entwurf="eingaben"
            :fehler="feldFehler"
            :logo-url="logoUrl"
            :monogramm="monogramm"
            :logo-laeuft="logoLaeuft"
            :logo-fehler="logoFehler"
            @feld="feldSetzen"
            @logo-hochladen="ladeLogoHoch"
            @logo-entfernen="entferneLogo"
          />

          <SchrittKontakt
            v-else-if="schritt === 'kontakt'"
            :entwurf="eingaben"
            :fehler="feldFehler"
            :zeitzone="zeitzone"
            :zeitzone-hinweis="zeitzoneHinweis"
            @feld="feldSetzen"
          />

          <SchrittMailversand v-else-if="schritt === 'mailversand'" ref="mailversand" />

          <SchrittModule
            v-else-if="schritt === 'module'"
            :module="moduleListe"
            :auswahl="moduleEingaben"
            :laedt="laedt"
            @schalten="modulSchalten"
          />

          <SchrittMitgliederKalender
            v-else-if="schritt === 'mitglieder_kalender'"
            :mitglieder-wahl="mitgliederWahl"
            :kalender-auswahl="kalenderAuswahl"
            :gruppe-spater="gruppeSpater"
            @mitglieder="mitgliederWahl = $event"
            @kalender="kalenderWaehlen"
            @gruppe="gruppeSpater = $event"
            @weg="mitgliederWeg"
          />

          <SchrittFertig
            v-else
            :punkte="punkte"
            :offen-anzahl="offenAnzahl"
            :gesamt-anzahl="gesamtAnzahl"
            :abgeschlossen="abgeschlossen"
            :speichert="speichert"
            @abschliessen="abschliessen"
            @uebersicht="zurUebersicht"
          />
        </div>
      </main>
    </div>

    <!-- Fußleiste (W1). Auf „Fertig“ gibt es kein Überspringen/Weiter. -->
    <footer class="assistent-fuss">
      <div class="assistent-fuss-inhalt">
        <DkButton
          v-if="schritt !== 'fertig'"
          variant="ghost"
          :disabled="speichert"
          @click="ueberspringenKlick"
        >Überspringen</DkButton>
        <span v-else class="assistent-fuss-platz"></span>

        <div class="assistent-fuss-rechts">
          <DkButton
            v-if="schritt !== 'fertig'"
            variant="secondary"
            :disabled="speichert || !hatZurueck"
            @click="zurueck"
          >Zurück</DkButton>
          <DkButton
            v-if="schritt !== 'fertig'"
            variant="primary"
            :loading="speichert"
            @click="weiterKlick"
          >Weiter</DkButton>
        </div>
      </div>
    </footer>
  </div>
</template>

<script setup>
/**
 * Einrichtungs-Assistent (ON-3).
 *
 * Der Bildschirm hält KEINEN eigenen Zustand: Schritt, Eingaben und Fehler
 * liegen im Modul `composables/useEinrichtungsAssistent.js`, die Regeln in
 * `composables/einrichtungAssistent.mjs`. So zeigen Kopfzeile, Schrittleiste,
 * Fußleiste und der jeweilige Schritt denselben Stand.
 *
 * Ablauf (Kartenvorgabe):
 *  - W1  Route `#/einrichtung`, nur Admin (Router-Guard), Layout wie Entwurf.
 *  - W2  sechs Schritte; gespeichert wird mit den VORHANDENEN Endpunkten.
 *  - W3  „Überspringen“ setzt `uebersprungen`, „Weiter“ `erledigt`;
 *        Wiedereinstieg beim ersten offenen Schritt.
 *  - W4  Nach dem Abschluss zeigt dieselbe Adresse die Checkliste.
 *
 * Nur Tokens (`var(--…)`) — keine Farb-, Schrift- oder Radius-Zahlen.
 */
import { computed, nextTick, onMounted, ref } from 'vue'
import { navigate } from '../../router.js'
import DkButton from '../../components/ui/DkButton.vue'
import AssistentSchritte from '../../components/einrichtung/AssistentSchritte.vue'
import SchrittGemeinde from '../../components/einrichtung/SchrittGemeinde.vue'
import SchrittKontakt from '../../components/einrichtung/SchrittKontakt.vue'
import SchrittMailversand from '../../components/einrichtung/SchrittMailversand.vue'
import SchrittModule from '../../components/einrichtung/SchrittModule.vue'
import SchrittMitgliederKalender from '../../components/einrichtung/SchrittMitgliederKalender.vue'
import SchrittFertig from '../../components/einrichtung/SchrittFertig.vue'
import {
  UEBERSICHT_ROUTE,
  hatZurueck as hatZurueckFuer,
  zeitzoneAnzeige,
} from '../../composables/einrichtungAssistent.mjs'
import { useEinrichtungsAssistent } from '../../composables/useEinrichtungsAssistent.js'
// ON-3b: der Sitzungs-Merker „lieber später“ (Router-Leitung, eine Regel).
import { merkeEinrichtungGesehen } from '../../einrichtungLeitung.mjs'

const {
  status, gemeinde, schritt, laedt, speichert, fehler, eingaben, feldFehler,
  moduleEingaben, mitgliederWahl, kalenderAuswahl, gruppeSpater,
  logoFehler, logoLaeuft,
  schritte, abgeschlossen, punkte, fortschrittText, moduleListe, monogramm,
  ladeAssistent, geheZu, weiter, ueberspringen, zurueck: zurueckSchritt,
  abschliessen, ladeLogoHoch, entferneLogo, spaeterSichern,
} = useEinrichtungsAssistent()

const haupt = ref(null)
const mailversand = ref(null)

const logoUrl = computed(() => String(gemeinde.value?.logo_url || ''))
const zeitzone = computed(() => zeitzoneAnzeige(gemeinde.value?.zeitzone))
const zeitzoneHinweis = computed(() => String(gemeinde.value?.zeitzone_hinweis || ''))
const offenAnzahl = computed(() => Number(status.value?.offen_anzahl) || 0)
const gesamtAnzahl = computed(() => Number(status.value?.gesamt_anzahl) || 0)
const hatZurueck = computed(() => hatZurueckFuer(schritt.value))

/** Eingaben und Meldungen des jeweiligen Schritts. */
function feldSetzen({ feld, wert }) {
  eingaben[feld] = wert
  if (feldFehler[feld]) delete feldFehler[feld]
}

function modulSchalten({ schluessel, sichtbar }) {
  moduleEingaben[schluessel] = sichtbar
}

function kalenderWaehlen({ name, gewaehlt }) {
  kalenderAuswahl[name] = gewaehlt
}

/**
 * Wechsel zu einem anderen Schritt: der Fokus geht auf den Hauptbereich, damit
 * Tastatur und Vorlesehilfe am neuen Inhalt beginnen und nicht in der Leiste
 * stehen bleiben (W5).
 */
async function wechsleZu(ziel) {
  const gewechselt = ziel === 'zurueck' ? zurueckSchritt() : geheZu(ziel)
  if (!gewechselt) return
  await nextTick()
  haupt.value?.focus({ preventScroll: false })
  haupt.value?.scrollIntoView({ block: 'start' })
}

function zurueck() {
  return wechsleZu('zurueck')
}

/**
 * „Weiter“: im Mailversand-Schritt werden erst die SMTP-Felder gespeichert
 * (vorhandener Endpunkt über `useMailversand`), dann der Schrittstand.
 */
async function weiterKlick() {
  if (schritt.value === 'mailversand') {
    const erfolg = await mailversand.value?.speichern?.()
    if (erfolg === false) return
    // Nach erfolgreichem Speichern den Prozessstand setzen und weitergehen:
    // die Seite hat die Schrittlogik, der Schritt das Formular.
    const naechster = await weiter()
    if (naechster) {
      await nextTick()
      haupt.value?.focus()
    }
    return
  }
  const naechster = await weiter()
  if (naechster) {
    await nextTick()
    haupt.value?.focus()
    haupt.value?.scrollIntoView({ block: 'start' })
  }
}

async function ueberspringenKlick() {
  const erfolg = await ueberspringen()
  if (!erfolg) return
  await nextTick()
  haupt.value?.focus()
  haupt.value?.scrollIntoView({ block: 'start' })
}

/** „Speichern und später fortsetzen“ → sichert die Eingaben, dann Übersicht. */
async function spaeter() {
  const gesichert = await spaeterSichern()
  if (!gesichert) return
  // ON-3b (Orchestrator-Nachtrag): „lässt ihn raus“ — der Router führt den
  // Admin beim Öffnen der App in dieser Sitzung nicht erneut her (beim
  // nächsten Login ist der Merker weg und der Assistent kommt wieder).
  merkeEinrichtungGesehen(window.sessionStorage)
  navigate(UEBERSICHT_ROUTE)
}

function zurUebersicht() {
  navigate(UEBERSICHT_ROUTE)
}

/** Mitglieder-Weg: vorhandene Seite öffnen (kein zweiter Weg). */
function mitgliederWeg(weg) {
  navigate(weg === 'import' ? '#/mitglieder/import' : '#/mitglieder/liste')
}

onMounted(() => {
  // Wiedereinstieg (W3/W4): beim ersten offenen Schritt fortsetzen; ist der
  // Assistent fertig, zeigt dieselbe Adresse die Checkliste.
  ladeAssistent({ start: true })
})
</script>

<style scoped>
.assistent {
  display: flex;
  flex-direction: column;
  /* `height: 100%` (nicht `min-height`): der Assistent füllt den sichtbaren
     Bereich und scrollt IN SICH. Mit `min-height: 100%` wuchs die Karte über
     den Bildschirm hinaus, ohne Scrollmöglichkeit — die Klebefußleiste lag
     dann über „Zur Übersicht“ und fing den Klick ab (Befund im Wegwerf-Stack).
     Kopfzeile und Fußleiste bleiben per `position: sticky` sichtbar. */
  height: 100%;
  min-height: 0;
  background: var(--bg);
}

/* Kopfzeile bleibt oben stehen (der Körper darunter scrollt). */
.assistent-kopf {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  position: sticky;
  top: 0;
  z-index: var(--z-sticky);
  flex: none;
  height: var(--assistent-kopf);
  padding: 0 var(--sp-8);
  background: var(--surface);
  border-bottom: 1px solid var(--line);
  flex-wrap: wrap;
}
.assistent-marke {
  display: inline-flex;
  align-items: center;
  gap: var(--sp-3);
  text-decoration: none;
  color: var(--text);
  border-radius: var(--radius-sm);
}
.assistent-marke:focus-visible { outline: 2px solid var(--focus-ring); outline-offset: 2px; }
.assistent-monogramm {
  width: 30px;
  height: 30px;
  border-radius: var(--radius-sm);
  background: var(--side-bg);
  color: var(--accent);
  display: grid;
  place-items: center;
  font-size: var(--fs-monogramm);
  font-weight: 700;
  line-height: 1;
}
.assistent-marke-text { font-size: var(--fs-h3); font-weight: 700; color: var(--side-bg); }
.assistent-trenner { width: 1px; height: 20px; background: var(--line-strong); }
.assistent-bereich { font-size: var(--fs); color: var(--muted); }
.assistent-spaeter {
  margin-left: auto;
  border: 0;
  background: none;
  padding: var(--sp-1) var(--sp-2);
  color: var(--link);
  font: inherit;
  font-size: var(--fs);
  cursor: pointer;
  border-radius: var(--radius-sm);
}
.assistent-spaeter:hover { color: var(--link-hover); text-decoration: underline; }
.assistent-spaeter:disabled { cursor: progress; text-decoration: none; color: var(--muted); }
.assistent-spaeter:focus-visible { outline: 2px solid var(--focus-ring); outline-offset: 2px; }

/* ── Körper: Leiste + Inhalt ─────────────────────────────────────────── */
.assistent-koerper {
  display: flex;
  align-items: stretch;
  /* `1 1 0` statt `flex: 1` — die BREITE des Inhalts darf den Elternteil nicht
     bestimmen (am Handy bekam der Inhalt sonst nur 201 px, die Karte 161 px).
     `min-height: 0` + `overflow-y: auto`: der Körper ist der Scrollbereich,
     Kopfzeile und Fußleiste (sticky) bleiben sichtbar. */
  flex: 1 1 0;
  min-height: 0;
  min-width: 0;
  width: 100%;
  overflow-y: auto;
}
.assistent-haupt {
  flex: 1 1 0;
  min-width: 0;
  padding: var(--sp-8) var(--sp-8) calc(var(--assistent-fuss) + var(--sp-8));
  display: flex;
  justify-content: center;
  align-items: flex-start;
}
.assistent-haupt:focus { outline: none; }
.assistent-hinweis { margin: 0; font-size: var(--fs); color: var(--muted); }
/* `width: 100%` PLUS `min-width: 0`: ohne die Mindestbreite dehnt der Inhalt
   eines Flex-Kindes (hier die Checkliste) seinen Elternteil auf, statt sich zu
   fügen — am Handy blieb dann nur 161 px für die Karte (gemessen). */
.assistent-karte {
  width: 100%;
  min-width: 0;
  max-width: 720px;
  padding: var(--sp-8);
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow);
  display: flex;
  flex-direction: column;
  gap: var(--sp-4);
}
.assistent-fehler {
  margin: 0;
  padding: var(--sp-3) var(--sp-4);
  border-radius: var(--radius);
  background: var(--err-soft);
  color: var(--err);
  font-size: var(--fs-meldung);
  font-weight: 600;
}

/* ── Fußleiste (sticky im scrollenden Körper) ────────────────────────── */
.assistent-fuss {
  position: sticky;
  bottom: 0;
  z-index: var(--z-sticky);
  flex: none;
  background: var(--surface);
  border-top: 1px solid var(--line);
}
.assistent-fuss-inhalt {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--sp-3);
  min-height: var(--assistent-fuss);
  padding: var(--sp-3) var(--sp-8);
}
.assistent-fuss-rechts { display: flex; align-items: center; gap: var(--sp-2); margin-left: auto; }
.assistent-fuss-platz { flex: 1; }

/* Handy (Entwurf 14): kompaktere Abstände, Fußleiste mit zwei Knöpfen. Der
   Körper wird zur SPALTE — Kopf der Schrittleiste („Schritt n von 6" +
   Segmentbalken) steht dann ÜBER der Karte, nicht daneben. */
@media (max-width: 900px) {
  .assistent-kopf { padding: 0 var(--sp-5); height: auto; min-height: var(--assistent-kopf); }
  .assistent-koerper { flex-direction: column; }
  .assistent-haupt { padding: var(--sp-4) var(--sp-5) calc(var(--assistent-fuss-mobil) + var(--sp-5)); }
  .assistent-karte { padding: var(--sp-5); border: 0; box-shadow: none; background: var(--bg); }
  .assistent-fuss-inhalt { min-height: var(--assistent-fuss-mobil); padding: var(--sp-3) var(--sp-5); }
}
@media (max-width: 600px) {
  .assistent-marke-text { display: none; }
  .assistent-spaeter { font-size: var(--fs-sm); }
}
</style>
