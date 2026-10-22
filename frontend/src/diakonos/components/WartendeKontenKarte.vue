<template>
  <DkCard title="Wartende Konten">
    <p class="wk-hinweis">
      Konten, die noch nicht zugelassen sind. Im Modus „Als Gast anlegen“
      entstehen sie beim ersten Anmeldeversuch — ohne Zulassung kann sich
      niemand damit anmelden.
    </p>

    <div v-if="laedt" class="wk-zustand">Lade…</div>
    <DkHint v-else-if="fehler" variant="err">{{ fehler }}</DkHint>

    <template v-else>
      <p v-if="!konten.length" class="wk-muted">
        Zurzeit wartet kein Konto auf Zulassung.
      </p>

      <ul v-else class="wk-liste">
        <li v-for="k in konten" :key="k.user" class="wk-eintrag">
          <div class="wk-daten">
            <span class="wk-name">{{ k.full_name || k.user }}</span>
            <span class="wk-konto">{{ k.email || k.user }}</span>
            <DkBadge v-if="!k.enabled" variant="err">Gesperrt</DkBadge>
          </div>
          <DkButton variant="primary" size="sm" :loading="arbeitet === k.user"
                    @click="freischalten(k)">
            Zulassen
          </DkButton>
        </li>
      </ul>

      <!-- R-N8 (Punkt 2): abgelehnte E-Mail-Zuordnungen. Hier steht nur der
           Anbieter-Account; die Verwaltung muss die Person pruefen. -->
      <section v-if="abgelehnt.length" class="wk-abschnitt">
        <h4 class="wk-abschnitt-titel">Nicht zugeordnet — bitte prüfen</h4>
        <p class="wk-hinweis">
          Bei diesen Anmeldungen passt die E-Mail-Adresse nicht eindeutig zu
          einer Person (oder die Person ist gesperrt). Sie wurden abgewiesen.
        </p>
        <ul class="wk-liste">
          <li v-for="(a, i) in abgelehnt" :key="i" class="wk-eintrag">
            <div class="wk-daten">
              <span class="wk-name">{{ a.name || a.email || 'Unbekannt' }}</span>
              <span class="wk-konto">{{ a.email }}</span>
              <DkBadge variant="warn">{{ grundText(a.grund) }}</DkBadge>
              <span v-if="a.versuche > 1" class="wk-konto">{{ a.versuche }} Versuche</span>
            </div>
            <span class="wk-konto">{{ a.meldung }}</span>
          </li>
        </ul>
      </section>
    </template>
  </DkCard>
</template>

<script setup>
/**
 * WartendeKontenKarte — Konten ohne Freischaltung sichtbar machen und
 * freischalten (R-P1-8/W1, OP-ADMIN-3).
 *
 * Im Authentik-Modus „Als Gast anlegen“ entstehen Konten mit `enabled=False`
 * und OHNE Mitglied. `konto_sperren` adressiert ueber die Mitglieds-ID und ist
 * fuer solche Konten nicht erreichbar — ohne diese Karte hingen sie dauerhaft
 * fest. Der Server bietet dafuer `get_wartende_konten` und `konto_freischalten`
 * (ueber den Kontonamen).
 */
import { ref, onMounted } from 'vue'
import DkCard from './ui/DkCard.vue'
import DkButton from './ui/DkButton.vue'
import DkHint from './ui/DkHint.vue'
import DkBadge from './ui/DkBadge.vue'
import { wartendeKonten, kontoFreischalten } from '../composables/usePflege.js'
import { showToast } from '../composables/useToast.js'

const laedt = ref(true)
const fehler = ref('')
const konten = ref([])
const abgelehnt = ref([])
const arbeitet = ref('')

/** R-N8: fachlicher Grund -> verstaendlicher Text (UI zeigt nie den Code). */
const GRUND_TEXTE = {
  mitglied_zuordnung: 'Nicht eindeutig',
}
function grundText(grund) {
  return GRUND_TEXTE[grund] || 'Zuordnung offen'
}

async function laden() {
  laedt.value = true
  fehler.value = ''
  try {
    const daten = await wartendeKonten()
    konten.value = daten.konten || []
    abgelehnt.value = daten.abgelehnt || []
  } catch (e) {
    fehler.value = e?.message || 'Wartende Konten konnten nicht geladen werden.'
  } finally {
    laedt.value = false
  }
}

async function freischalten(konto) {
  arbeitet.value = konto.user
  try {
    await kontoFreischalten(konto.user, true)
    await laden()
    showToast('Konto zugelassen.', 'success')
  } catch (e) {
    showToast(e?.message || 'Zulassen fehlgeschlagen.', 'error')
  } finally {
    arbeitet.value = ''
  }
}

onMounted(laden)
</script>

<style scoped>
.wk-hinweis { font-size: var(--fs-sm); color: var(--text-muted); margin: 0 0 var(--sp-3); }
.wk-zustand { color: var(--text-muted); padding: var(--sp-3) 0; }
.wk-muted { color: var(--text-muted); }
.wk-liste { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: var(--sp-2); }
.wk-eintrag { display: flex; align-items: center; justify-content: space-between; gap: var(--sp-3); flex-wrap: wrap; }
.wk-daten { display: flex; align-items: center; gap: var(--sp-2); flex-wrap: wrap; }
.wk-name { font-weight: 500; }
.wk-konto { color: var(--text-muted); font-size: var(--fs-sm); }
.wk-abschnitt { margin-top: var(--sp-4); border-top: 1px solid var(--line); padding-top: var(--sp-3); }
.wk-abschnitt-titel { margin: 0 0 var(--sp-2); font-size: var(--fs-md); }
.wk-abschnitt .wk-hinweis { margin-bottom: var(--sp-2); }
</style>
