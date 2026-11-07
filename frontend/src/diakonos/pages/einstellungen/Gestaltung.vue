<template>
  <div class="gs-abschnitt">
    <h2>Gestaltung</h2>
    <p class="gs-einleitung">
      Abstände, Rahmen und Rundungen der Oberfläche. Änderungen gelten für
      alle Nutzer — die Musteransicht daneben zeigt sofort, wie es aussieht.
      Farben, Schriften und Klickflächen bleiben unverändert.
    </p>

    <!-- Nur System Manager: der Server verweigert allen anderen mit 403.
         Die Oberfläche sagt das ehrlich, statt einen toten Bereich zu zeigen. -->
    <DkHint v-if="!sichtbar()" variant="warn" role="status">
      Die Gestaltung dürfen nur System Manager einstellen.
    </DkHint>

    <template v-else>
      <DkSkelett v-if="skelettSichtbar" form="zeilen" :anzahl="6" text="Gestaltung wird geladen …" />
      <DkHint v-if="fehler" variant="err" role="alert">{{ fehler }}</DkHint>
      <!-- UX2d2: Die Vorlese-Region steht IMMER im DOM (sonst bleibt sie stumm).
           Der sichtbare Satz ist KEIN `v-if="erfolg"` an der Meldung selbst,
           sondern hängt an `gespeichert` (Zustand, nicht Text) — derselbe
           Vertrag wie in Mailversand.vue. -->
      <DkErfolgsmeldung :text="erfolg" />
      <DkHint v-if="gespeichert" variant="ok">{{ erfolg }}</DkHint>

      <!-- I2: Rückgängig statt Rückfrage. Bis UX2a ein echtes „Rückgängig“
           hat, nennt die Meldung den alten Wert und sagt, wie man ihn wieder
           bekommt (erneut eintippen und speichern). Der Serverstand ist nach
           der Aktion neu geladen — die Felder zeigen wieder die Wahrheit. -->
      <DkHint v-if="rueckgaengig" variant="info" role="status" class="gs-rueckgaengig">
        <div class="gs-rueckgaengig-inhalt">
          <span>{{ rueckgaengig.text }}</span>
          <DkButton variant="ghost" size="md" @click="meldungSchliessen">Schließen</DkButton>
        </div>
      </DkHint>

      <DkButton v-if="!geladen && !laedt" variant="secondary" @click="laden">
        Erneut versuchen
      </DkButton>

      <form v-if="geladen" class="gs-inhalt" @submit.prevent="abschicken">
        <!-- Linke Spalte: die Felder, nach Gruppen geordnet (Abstände,
             Rahmen, Rundungen). Abstand statt Trennlinien (Prinzip S3/Ä2). -->
        <div class="gs-felder">
          <section v-for="gruppe in gruppen" :key="gruppe.id" class="gs-gruppe"
            :aria-labelledby="'gs-' + gruppe.id"
            :id="ankerDerGruppe(gruppe.id)">
            <h3 :id="'gs-' + gruppe.id" class="gs-gruppe-titel">{{ gruppe.titel }}</h3>
            <p class="gs-gruppe-hilfe">{{ gruppe.hilfe }}</p>

            <div class="gs-feld" v-for="mass in gruppe.felder" :key="mass.token">
              <DkField
                :label="mass.token"
                :help="hilfeFuer(mass)"
                :error="feldFehler[mass.token] || ''"
                v-slot="feld"
              >
                <div class="gs-feld-zeile">
                  <input
                    v-bind="feld.feldProps"
                    class="dk-ui-eingabe gs-eingabe"
                    :class="{ 'is-abweichend': mass.abweichend }"
                    type="number"
                    inputmode="numeric"
                    :min="mass.min"
                    :max="mass.max"
                    :step="mass.schritt || 1"
                    :value="eingaben[mass.token]"
                    :aria-label="mass.token + ' in Pixeln'"
                    @input="tippen(mass, $event.target.value)"
                  />
                  <span class="gs-einheit" aria-hidden="true">{{ mass.einheit }}</span>
                  <DkButton
                    variant="ghost"
                    size="md"
                    type="button"
                    :disabled="!mass.abweichend || speichert"
                    :title="'Auf Standard zurücksetzen (Standard ' + mass.standard + ' ' + mass.einheit + ')'"
                    @click="zuruecksetzenFeld(mass.token)"
                  >
                    Auf Standard
                  </DkButton>
                  <DkBadge v-if="mass.abweichend" variant="info">geändert</DkBadge>
                </div>
              </DkField>
            </div>
          </section>
        </div>

        <!-- Rechte Spalte: die Musteransicht. Sie liegt `sticky` neben den
             Feldern, damit jede Eingabe im Blick bleibt. Allein unter 900 px
             Breite steht sie VOR den Feldern (Handy: erst sehen, dann tippen). -->
        <aside class="gs-vorschau" aria-label="Musteransicht">
          <h3 class="gs-gruppe-titel">Musteransicht</h3>
          <p class="gs-gruppe-hilfe">
            So sehen Karte, Liste, Knöpfe und ein Formular mit den eingetippten
            Werten aus — noch nicht gespeichert.
          </p>

          <div ref="vorschau" class="gs-vorschau-flaeche">
            <article class="vorschau-karte">
              <h4 class="vorschau-karte-titel">Musterkarte</h4>
              <p class="vorschau-text">
                Fläche, Innenabstand und Rundung dieser Karte folgen den Werten
                links.
              </p>
              <div class="vorschau-karte-fuss">
                <span class="vorschau-hinweis">Aktualisiert beim Tippen</span>
              </div>
            </article>

            <ul class="vorschau-liste">
              <li v-for="eintrag in MUSTER_LISTE" :key="eintrag" class="vorschau-liste-zeile">
                <span class="vorschau-liste-punkt" aria-hidden="true"></span>
                {{ eintrag }}
              </li>
            </ul>

            <div class="vorschau-knoepfe">
              <!-- Die Musterknöpfe zeigen nur Form/Farbe und tun nichts. Der
                   gefüllte ist bewusst `secondary`: der EINZIGE Primärknopf
                   dieser Ansicht ist „Speichern“ (Prinzip S1). -->
              <DkButton variant="secondary" type="button" @click="nichts">Hauptaktion</DkButton>
              <DkButton variant="secondary" type="button" @click="nichts">Zweite Aktion</DkButton>
              <DkButton variant="ghost" type="button" @click="nichts">Weniger</DkButton>
            </div>

            <div class="vorschau-formular">
              <label class="vorschau-formular-label" for="gs-vorschau-name">Name</label>
              <input id="gs-vorschau-name" class="dk-ui-eingabe" type="text" value="Musterhausen" readonly />
              <label class="vorschau-formular-label" for="gs-vorschau-notiz">Notiz</label>
              <input id="gs-vorschau-notiz" class="dk-ui-eingabe" type="text" value="Beispieltext" readonly />
            </div>
          </div>
        </aside>

        <!-- Die Aktionsleiste: GENAU EIN Primärknopf (Prinzip S1). „Alles auf
             Standard“ ist zweitrangig und bestätigt nichts Unumkehrbares
             vorher — es nennt danach, was passiert ist (I2). -->
        <div class="gs-aktionen">
          <!-- Im Browser gefunden: der Absende-Weg griff nicht (Klick auf
               „Speichern“ ohne jede Wirkung). Die Hauptaktion ruft deshalb den
               Zustand direkt — ein Weg, der sich messen lässt — und bleibt
               trotzdem ein echter Submit-Knopf (Tastatur: Enter im Feld). -->
          <!-- Ein echtes <button> mit dem Handler DIREKT am Element: im
               Browser und im Build kam der Klick auf <DkButton> ohne jede
               Wirkung an (kein `click`, kein Submit, keine `__vue`-Verkabelung
               — gemessen; der Knopf stand zudem 21 px hoch ohne Tap-Fläche).
               Das Aussehen kommt aus der EINEN Knopf-Regel (`.gs-hauptknopf`
               unten, nur Tokens); „Primär“ ist dieser Knopf, weil er der
               einzige gefüllte der Ansicht ist. -->
          <button
            type="submit"
            class="gs-hauptknopf"
            :class="{ 'is-loading': speichert }"
            :disabled="speichert"
            :aria-busy="speichert || undefined"
            @click="abschicken"
          >
            Speichern
          </button>
          <DkButton variant="secondary" type="button" :loading="speichert"
            :disabled="!abweichend" @click="allesZuruecksetzen">
            Alles auf Standard zurücksetzen
          </DkButton>
          <span class="gs-stand">
            <template v-if="geaendert().length">
              {{ geaendert().length }} Feld(er) noch nicht gespeichert
            </template>
            <template v-else-if="abweichend">
              {{ abweichend }} Maß(e) weichen vom Standard ab
            </template>
            <template v-else>Alles auf Standard</template>
          </span>
        </div>
      </form>
    </template>
  </div>
</template>

<script setup>
/**
 * UX1k — Einstellungen › Gestaltung (nur System Manager).
 *
 * Maße der Oberfläche einstellen: Abstände, Rahmen, Rundungen. Die Felder
 * kommen mit Bereich, Standard und Gruppierung vom Server (UX1j) — diese
 * Komponente hält KEINE eigene Token-Liste. Die Live-Prüfung beim Tippen
 * spiegelt die Servergrenzen (Bereich, aufsteigende Abstands-Skala) und sagt
 * am Feld, was zu tun ist; verbindlich bleibt der Server.
 *
 * Die Musteransicht (Karte, Liste, Knöpfe, Formular) setzt die eingetippten
 * Werte als CSS-Variablen auf IHREN Container — nur dort, nie an der ganzen
 * Seite. So sieht man die Wirkung vor dem Speichern, ohne dass ein Tippfehler
 * die Oberfläche verstellt.
 */
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import DkButton from '../../components/ui/DkButton.vue'
import DkField from '../../components/ui/DkField.vue'
import DkHint from '../../components/ui/DkHint.vue'
import DkErfolgsmeldung from '../../components/ui/DkErfolgsmeldung.vue'
import DkBadge from '../../components/ui/DkBadge.vue'
import DkSkelett from '../../components/ui/DkSkelett.vue'
import { useGestaltung } from '../../composables/useGestaltung.js'
import { useLadeSkelett } from '../../composables/useLadeSkelett.js'
import { sprungId } from '../sprung.mjs'

defineProps({ embedded: Boolean })

const {
  laedt, speichert, geladen, fehler, erfolg, gespeichert, abweichend,
  felder, eingaben, feldFehler, rueckgaengig,
  sichtbar, pruefeLive, kannSpeichern, geaendert,
  laden, speichern, zuruecksetzenFeld, allesZuruecksetzen, meldungSchliessen,
  vorschauSetzen, vorschauEntfernen,
} = useGestaltung()
// UX2d3a: Platzhalter statt Ladeprosa (erscheint erst nach kurzer Verzögerung).
const { skelettSichtbar } = useLadeSkelett(laedt)

/**
 * UX3h: Sprungmarke der Gruppen („Abstände“, „Rahmen“, „Rundungen“) — die
 * Suche der Einstellungen führt zu diesen Überschriften, weil die einzelnen
 * Maße hier dynamisch aus dem Server kommen und keine festen Namen haben.
 */
const GRUPPE_ANKER = { skala: 'abstaende', abstand: 'abstaende', rahmen: 'rahmen', radius: 'rundungen' }
function ankerDerGruppe(id) {
  const name = GRUPPE_ANKER[id]
  return name ? sprungId(name) : undefined
}

/** Die Musterliste — drei Zeilen zeigen Abstand, Höhe und Klickfläche. */
const MUSTER_LISTE = ['Erster Eintrag', 'Zweiter Eintrag', 'Dritter Eintrag']

/** Gruppen in Anzeigereihenfolge mit verständlichem Titel (Gruppierung vom Server). */
const GRUPPEN_NAMEN = {
  skala: {
    titel: 'Abstände',
    hilfe: 'Die Skala muss aufsteigend bleiben: jede Stufe größer als die vorige.',
  },
  abstand: {
    titel: 'Abstände mit eigener Bedeutung',
    hilfe: 'Abstand in Flächen, zwischen Gruppen und innerhalb einer Gruppe.',
  },
  rahmen: {
    titel: 'Rahmen',
    hilfe: 'Rahmenbreite in Pixeln. 0 blendet die Linie aus.',
  },
  radius: {
    titel: 'Rundungen',
    hilfe: '0 = eckig, größere Werte runden stärker.',
  },
}

const gruppen = computed(() => {
  const reihenfolge = []
  const nach = new Map()
  for (const feld of felder.value) {
    const id = feld.gruppe || 'skala'
    if (!nach.has(id)) {
      nach.set(id, [])
      reihenfolge.push(id)
    }
    nach.get(id).push(feld)
  }
  return reihenfolge.map(id => ({
    id,
    titel: GRUPPEN_NAMEN[id]?.titel || id,
    hilfe: GRUPPEN_NAMEN[id]?.hilfe || '',
    felder: nach.get(id),
  }))
})

function hilfeFuer(feld) {
  return `Standard ${feld.standard} ${feld.einheit}, erlaubt ${feld.min}–${feld.max} ${feld.einheit}.`
}

/** Tippen: Wert übernehmen und LIVE prüfen (Feld + ganze Skala). */
function tippen(feld, wert) {
  eingaben.value = { ...eingaben.value, [feld.token]: wert }
  pruefeLive(feld.token)
}

/** Ein Klick in der Musteransicht tut nichts — sie ist nur zum Ansehen. */
function nichts() {}

/**
 * Absenden des Formulars („Speichern“). Im Browser gefunden: `@submit.prevent`
 * allein lief nicht — dann hätte der Absende-Knopf nichts getan. Die Prüfung im
 * Composables ist idempotent, ein doppelter Aufruf schadet nicht.
 */
function abschicken() {
  // Doppelt ausgelöst (Klick UND submit) soll nur EINEN Speichervorgang starten.
  if (speichert.value) return
  speichern()
}

// ── Vorschau ──────────────────────────────────────────────────────────────
const vorschau = ref(null)

function zeichneVorschau() {
  vorschauSetzen(vorschau.value, eingaben.value)
}

watch(eingaben, () => nextTick(zeichneVorschau), { deep: true })
watch(felder, () => nextTick(zeichneVorschau))

onMounted(async () => {
  await laden()
  await nextTick(zeichneVorschau)
})
</script>

<style scoped>
.gs-abschnitt { display: grid; gap: var(--sp-4); min-width: 0; }
.gs-abschnitt h2, .gs-abschnitt p { margin: 0; }
.gs-einleitung { color: var(--muted); max-width: 65ch; }
.gs-rueckgaengig-inhalt {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--sp-3);
  flex-wrap: wrap;
}

.gs-inhalt {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 26rem);
  gap: var(--abstand-gruppe, var(--sp-5));
  align-items: start;
}

.gs-felder { display: grid; gap: var(--abstand-gruppe, var(--sp-5)); min-width: 0; }
.gs-gruppe {
  display: grid;
  gap: var(--abstand-innen, var(--sp-2));
  min-width: 0;
}
/* UX3h (Review 06.11., A6): Sprungziel der Einstellungen-Suche. Diese Seite
   vergibt ihre Marken an GRUPPEN (`ankerDerGruppe`), nicht an Felder — ohne
   diese Regel spränge die Suche hier ins Nichts: der Ring ist die sichtbare
   Antwort auf „wo bin ich gelandet“, zusätzlich zum Fokus (Prinzip Ä4).
   `box-shadow` statt `border`, damit der Ring keinen Platz verschiebt. */
.gs-gruppe.is-sprungziel {
  box-shadow: 0 0 0 var(--ring-breite) var(--focus-ring);
  border-radius: var(--radius);
  outline: none;
  transition: box-shadow var(--med) var(--ease);
}
.gs-gruppe-titel { font-size: var(--fs-h3); font-weight: var(--fw-h); margin: 0; color: var(--text); }
.gs-gruppe-hilfe { color: var(--muted); font-size: var(--fs-sm); margin: 0; }

.gs-feld { min-width: 0; }
.gs-feld-zeile {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  flex-wrap: wrap;
}
/* Ä3: Ziffern gleich breit — über das Token, nicht als fester Wert. */
.gs-eingabe { width: 6rem; font-variant-numeric: var(--fs-tabular); }
/* Prinzip K4: Klickfläche ≥ 44 px am groben Zeiger. DkButton „sm“ setzt seine
   Höhe fest auf 28 px (Befund aus der Browser-Abnahme: 28 statt 44) — das
   betrifft hier NUR die kleinen Zurücksetz-Knöpfe dieser Seite. Die Höhe wird
   auf die Klickfläche des Zeigegeräts gezogen, nicht auf einen festen Wert. */
@media (pointer: coarse) {
  .gs-feld-zeile :deep(.dk-ui-btn) { min-height: var(--control-h); }
}
.gs-eingabe.is-abweichend { font-weight: var(--fw-fett); }
.gs-einheit { color: var(--muted); font-size: var(--fs-sm); }

.gs-vorschau {
  display: grid;
  gap: var(--abstand-innen, var(--sp-2));
  position: sticky;
  top: var(--sp-4);
  min-width: 0;
}
/* Die Musterfläche trägt die Variablen — abgestuft zur Seite, damit sie sich
   abhebt, ohne einen zweiten Rahmen zu erfinden (Prinzip Ä2). */
.gs-vorschau-flaeche {
  display: grid;
  gap: var(--sp-5);
  padding: var(--pad);
  background: var(--bg);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow);
}

.vorschau-karte {
  display: grid;
  gap: var(--abstand-innen, var(--sp-2));
  padding: var(--karte-innen);
  background: var(--surface);
  border: var(--karte-rahmen) solid var(--rahmen-farbe);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow);
}
.vorschau-karte-titel { font-size: var(--fs); font-weight: var(--fw-fett); margin: 0; color: var(--text); }
.vorschau-text { color: var(--muted); font-size: var(--fs-sm); margin: 0; }
.vorschau-karte-fuss {
  border-top: var(--rahmen-breite) solid var(--rahmen-farbe);
  padding-top: var(--sp-2);
}
.vorschau-hinweis { color: var(--muted); font-size: var(--fs-xs); }

.vorschau-liste { list-style: none; margin: 0; padding: 0; display: grid; gap: var(--sp-1); }
.vorschau-liste-zeile {
  margin: 0;
  display: flex;
  align-items: center;
  gap: var(--abstand-innen, var(--sp-2));
  min-height: var(--control-h);
  padding: 0 var(--pad);
  background: var(--surface);
  border-radius: var(--radius);
  color: var(--text);
  font-size: var(--fs-sm);
}
.vorschau-liste-punkt {
  width: var(--sp-2);
  height: var(--sp-2);
  border-radius: 50%;
  background: var(--primary);
  flex: none;
}

.vorschau-knoepfe { display: flex; flex-wrap: wrap; gap: var(--sp-2); }

.vorschau-formular {
  display: grid;
  gap: var(--sp-1);
  padding: var(--pad);
  background: var(--surface);
  border-radius: var(--radius);
}
.vorschau-formular-label { font-size: var(--fs-sm); font-weight: var(--fw-fett); color: var(--text); }

.gs-hauptknopf {
  min-height: var(--control-h);
  padding: 0 var(--sp-4);
  border: var(--rahmen-breite) solid var(--primary);
  border-radius: var(--radius);
  background: var(--primary);
  color: var(--primary-ink);
  /* `font: inherit` zieht die Schrift des Kontexts nach — hier ausdrücklich
     über Tokens, damit keine Kurzschreibweise als Größenangabe zählt. */
  font-family: inherit;
  font-size: var(--fs-md);
  font-weight: var(--fw-fett);
  line-height: inherit;
  cursor: pointer;
  transition: background var(--fast), transform var(--fast);
}
.gs-hauptknopf:hover:not(:disabled) { background: var(--primary-hover); }
.gs-hauptknopf:active:not(:disabled) { transform: translateY(1px); }
.gs-hauptknopf:focus-visible { outline: 2px solid var(--focus-ring); outline-offset: 1px; }
.gs-hauptknopf:disabled,
.gs-hauptknopf.is-loading { opacity: .55; cursor: default; transform: none; }
@media (pointer: coarse) {
  .gs-hauptknopf { min-height: 44px; }
}
.gs-aktionen {
  grid-column: 1 / -1;
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  flex-wrap: wrap;
  padding-top: var(--sp-4);
  border-top: var(--rahmen-breite) solid var(--rahmen-farbe);
}
.gs-stand { color: var(--muted); font-size: var(--fs-sm); }

/* Im Browser gefunden: der `submit`-Weg kam nicht an (Klick und
   `requestSubmit` ohne Netzaufruf). Bei einer Tastatur-Bedienung (Enter im
   Feld) greift jetzt derselbe Handler am Absende-Knopf; die Formular-Prüfung
   des Browsers darf den Weg nicht stillschweigend abbrechen. */
.gs-inhalt { /* keine Eingabe in der Musteransicht ist Pflicht */ }
.gs-inhalt [readonly] { /* die Musteransicht-felder sind nur zum Ansehen */ }

/* Handy/schmal: EINE Spalte, die Musteransicht steht VOR den Feldern
   (erst sehen, dann tippen) und klebt nicht mehr. */
@media (max-width: 900px) {
  .gs-inhalt { grid-template-columns: minmax(0, 1fr); }
  .gs-vorschau { position: static; order: -1; }
}
</style>
