<template>
  <DkCard title="Bausteine" anker="bausteine">
    <!-- Kopf: Stand und die EINE mögliche Aktion (Knopf nur, wenn es etwas
         zu tun gibt — kein toter Knopf bei „aktuell“). -->
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

      <div v-if="zustand.aktion" class="wb-aktionen">
        <DkButton variant="primary" :loading="spieltEin" @click="einspielen">
          {{ zustand.aktion }}
        </DkButton>
        <DkButton variant="secondary" :loading="laedt" :disabled="spieltEin" @click="laden">
          Stand neu laden
        </DkButton>
      </div>
    </div>

    <!-- Liste der mitgelieferten Bausteine. Quelle ist AUSSCHLIESSLICH die
         Serverantwort (`bausteine_status`) — nichts ist hier fest verdrahtet. -->
    <DkHint v-if="ladehinweis" variant="info" role="status">{{ ladehinweis }}</DkHint>
    <DkEmpty
      v-else-if="!zeilen.length"
      title="Keine Bausteine"
      :text="`Im ${WERKZEUG} liegt noch kein Baustein. Mit „einspielen“ werden die mitgelieferten Bausteine übertragen.`"
    />
    <ul v-else class="wb-liste">
      <li v-for="z in zeilen" :key="z.kennung" class="wb-baustein">
        <div class="wb-baustein-haupt">
          <h3 class="wb-baustein-name">{{ z.name || z.kennung }}</h3>
          <DkBadge :variant="z.stand.ton">{{ z.stand.text }}</DkBadge>
        </div>
        <p v-if="z.beschreibung" class="wb-baustein-text">{{ z.beschreibung }}</p>
        <p class="wb-baustein-freigaben">
          <template v-if="z.freigaben.length">
            Nutzt die Freigaben: {{ freigabenText(z.freigaben) }}
          </template>
          <template v-else>
            Braucht keine Freigabe aus Diakronos.
          </template>
        </p>
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
 * BS-2d — Bereich „Bausteine“ auf der Website-Seite.
 *
 * Neben den Freigaben zeigt der Bereich:
 *   - den Stand der Baustein-Bibliothek im Website-Baukasten
 *     (mitgeliefert / installiert / veraltet),
 *   - je mitgeliefertem Baustein Kurzbeschreibung und genutzte Freigaben,
 *   - den EINEN Knopf „In Website-Baukasten einspielen/aktualisieren“ samt
 *     Ergebnis-Meldung,
 *   - die Kurzanleitung (Block hinzufügen → Bibliothek → Diakronos → Felder).
 *
 * Die Logik (Stand, Zustand, Zeilen, Meldungen) steht in
 * `shared/website-bausteine.mjs` und ist dort per Node-Test geprüft; dieses
 * Bauteil zeichnet nur. Der Server liefert die Bausteinliste (BS-2b) — hier
 * ist KEIN Baustein fest verdrahtet.
 *
 * Sichtbarkeit prüft die Seite (`darfBausteineSehen`); der Server weist
 * zusätzlich mit 403 ab.
 */
import { computed } from 'vue'
import {
  WERKZEUG,
  bausteineAnleitung,
  freigabenText as freigabenAlsText,
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

function freigabenText(liste) {
  return freigabenAlsText(liste)
}

async function einspielen() {
  await einspielenJetzt()
}
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
