<template>
  <DkCard title="Bausteine" anker="bausteine">
    <!-- Kopf: Stand und die möglichen Aktionen. „Einspielen/aktualisieren“ ist
         secondary — der EINE Primärknopf der Ansicht ist „Website-Baukasten
         öffnen“ auf der Seite (UX1h). „Stand neu laden“ im Kopf der Seite lädt die
         Freigaben, NICHT die Bausteine; deshalb hat dieser Bereich seinen
         eigenen Knopf „Bausteine neu laden“ (BS-2d2). -->
    <div class="wb-kopf">
      <div class="wb-zustand">
        <DkBadge :variant="zustand.ton">{{ zustand.titel }}</DkBadge>
        <span v-if="stand.erreichbar && stand.installiert >= 1" class="wb-details">
          eingespielt: Fassung {{ stand.installiert }} · mitgeliefert: Fassung {{ stand.mitgeliefert }}
        </span>
      </div>
      <p class="wb-hilfe">{{ zustand.text }}</p>

      <DkHint v-if="ergebnisMeldung" :variant="ergebnisMeldung.ton" role="alert">
        {{ ergebnisMeldung.text }}
      </DkHint>

      <div v-if="zustand.aktion || daten || fehler" class="wb-aktionen">
        <DkButton v-if="zustand.aktion" variant="secondary" :loading="spieltEin"
          :disabled="laedt" aria-label="Mitgelieferte Bausteine in den Website-Baukasten einspielen"
          @click="einspielen">
          {{ zustand.aktion }}
        </DkButton>
        <DkButton variant="secondary" :loading="laedt" :disabled="spieltEin"
          aria-label="Bausteine neu laden" @click="laden">
          Bausteine neu laden
        </DkButton>
      </div>
    </div>

    <!-- Liste der mitgelieferten Bausteine. Quelle ist AUSSCHLIESSLICH die
         Serverantwort (`bausteine_status` mit `mitgeliefert[]`) — weder die
         Namen noch die Freigaben sind hier fest verdrahtet. -->
    <DkHint v-if="ladehinweis" :variant="fehler ? 'err' : 'info'" role="status">{{ ladehinweis }}</DkHint>
    <DkEmpty
      v-else-if="!zeilen.length"
      title="Keine Bausteine"
      :text="`Im ${WERKZEUG} liegt noch kein Baustein. Mit „einspielen“ werden die mitgelieferten Bausteine übertragen.`"
    />
    <ul v-else class="wb-liste">
      <li v-for="z in zeilen" :key="z.kennung" class="wb-baustein">
        <div class="wb-baustein-haupt">
          <h3 class="wb-baustein-name">{{ z.name }}</h3>
          <DkBadge :variant="z.stand.ton">{{ z.stand.text }}</DkBadge>
        </div>
        <p v-if="z.beschreibung" class="wb-baustein-text">{{ z.beschreibung }}</p>
        <p class="wb-baustein-freigaben">{{ freigabenHinweis(z) }}</p>
      </li>
    </ul>

    <!-- Kurzanleitung: wo der Baustein in der Website landet und wie er
         angepasst wird (Karten-Ziel BS-2d). -->
    <div class="wb-anleitung">
      <h3 class="wb-anleitung-titel">So kommt ein Baustein auf die Website</h3>
      <ol class="wb-anleitung-schritte">
        <li v-for="(satz, i) in anleitung" :key="i">{{ satz }}</li>
      </ol>
      <p class="wb-hilfe">
        Ein im Einsatz geänderter Block bleibt bei einer Aktualisierung
        unangetastet — die Bibliothek liefert nur die Vorlage.
      </p>
    </div>
  </DkCard>
</template>

<script setup>
/**
 * BS-2d/BS-2d2 — Bereich „Bausteine“ auf der Website-Seite.
 *
 * Neben den Freigaben zeigt der Bereich:
 *   - den Stand der Baustein-Bibliothek im Website-Baukasten
 *     (mitgeliefert / installiert / veraltet),
 *   - je mitgeliefertem Baustein Name, Kurzbeschreibung und genutzte
 *     Freigaben — alles aus `mitgeliefert[]` der Serverantwort,
 *   - den Knopf „In Website-Baukasten einspielen/aktualisieren“ samt
 *     Ergebnis-Meldung,
 *   - die Kurzanleitung (Block hinzufügen → Bibliothek → Diakronos → Felder).
 *
 * BS-2d2 (Nacharbeit):
 *   1. `onMounted(laden)` — beim Öffnen der Seite steht der Stand sofort da;
 *      der mount-Test „Seite öffnen → Liste + Knopf sichtbar“ belegt es.
 *   2. Freigaben kommen aus der Serverantwort; die früher hier fest kodierte
 *      Zuordnungstabelle ist entfallen (`shared/website-bausteine.mjs`).
 *   3. Einspielen ist `secondary`; der EINE Primärknopf der Ansicht bleibt
 *      „Website-Baukasten öffnen“ (Website.vue). Der zweite Knopf heißt
 *      „Bausteine neu laden“ (nicht „Stand neu laden“ — das sitzt im Kopf der
 *      Seite) und trägt ein eindeutiges `aria-label`.
 *
 * Die Logik (Stand, Zustand, Zeilen, Meldungen) steht in
 * `shared/website-bausteine.mjs` und ist dort per Node-Test geprüft; dieses
 * Bauteil zeichnet nur.
 *
 * Sichtbarkeit prüft die Seite (`darfBausteineSehen`); der Server weist
 * zusätzlich mit 403 ab.
 */
import { computed, onMounted } from 'vue'
import {
  WERKZEUG,
  bausteineAnleitung,
  freigabenHinweis,
  installationsMeldung,
} from '../../../shared/website-bausteine.mjs'
import { useWebsiteBausteine } from '../../composables/useWebsiteBausteine.js'
import DkBadge from '../ui/DkBadge.vue'
import DkButton from '../ui/DkButton.vue'
import DkCard from '../ui/DkCard.vue'
import DkEmpty from '../ui/DkEmpty.vue'
import DkHint from '../ui/DkHint.vue'

const {
  daten, laedt, fehler, spieltEin, ergebnis, stand, zustand, zeilen, laden, einspielen: einspielenJetzt,
} = useWebsiteBausteine()

const anleitung = bausteineAnleitung()

/** Fehler beim LADEN: der leere Bereich braucht einen Satz, keinen stillen Nichts. */
const ladehinweis = computed(() => {
  if (laedt.value && !daten.value) return 'Die Bausteine werden geladen …'
  return fehler.value
})

/** Erfolg wird als Meldung gezeigt, ein Fehler ebenso — beides Klartext. */
const ergebnisMeldung = computed(() => {
  const r = ergebnis.value
  if (!r) return null
  if (!r.ok) return { ton: 'err', text: r.fehler }
  return installationsMeldung(r.antwort)
})

async function einspielen() {
  await einspielenJetzt()
}

// BS-2d2 (Punkt 1): beim Öffnen der Seite den Stand holen. Das Bauteil wird
// erst im geschützten Zweig der Seite eingehaengt (Rollenprüfung dort), ein
// unberechtigter Aufruf entsteht so nicht.
onMounted(laden)
</script>

<style scoped>
.wb-kopf { display: grid; grid-template-columns: minmax(0, 1fr); gap: var(--sp-2); min-width: 0; }
.wb-zustand { display: flex; flex-wrap: wrap; align-items: center; gap: var(--sp-2); min-width: 0; }
.wb-details { color: var(--muted); font-size: var(--fs-sm); }
.wb-hilfe { margin: 0; color: var(--muted); font-size: var(--fs-sm); }
.wb-aktionen { display: flex; flex-wrap: wrap; gap: var(--sp-3); }
.wb-liste {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: var(--sp-2);
  margin: var(--sp-4) 0 0;
  padding: 0;
  list-style: none;
  min-width: 0;
}
/* Karten ohne Rahmen: getönte Fläche statt Linie (Prinzip Ä2). */
.wb-baustein {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: var(--sp-1);
  padding: var(--sp-3);
  border-radius: var(--radius);
  background: var(--surface-2);
  min-width: 0;
}
.wb-baustein-haupt {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--sp-2);
  min-width: 0;
}
.wb-baustein-name { margin: 0; font-size: var(--fs-h4); font-weight: var(--fw-fett); color: var(--text); }
.wb-baustein-text { margin: 0; color: var(--text); overflow-wrap: anywhere; }
.wb-baustein-freigaben { margin: 0; color: var(--muted); font-size: var(--fs-sm); overflow-wrap: anywhere; }
.wb-anleitung {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: var(--sp-2);
  margin-top: var(--sp-5);
  min-width: 0;
}
.wb-anleitung-titel { margin: 0; font-size: var(--fs-h4); font-weight: var(--fw-fett); color: var(--text); }
.wb-anleitung-schritte {
  margin: 0;
  padding-left: var(--sp-5);
  display: grid;
  gap: var(--sp-1);
  color: var(--text);
}
</style>
