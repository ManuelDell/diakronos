<template>
    <div class="dk-screen dk-screen-enter">
        <div class="dk-screen-header">
            <div>
                <!-- DES-R12: einheitlicher Seitentitel statt Tailwind text-2xl. -->
                <h1 class="dk-screen-title">Adressbuch</h1>
            </div>
        </div>

        <!-- Suchfeld (DES-R19: sichtbare Beschriftung + aria-label) -->
        <div class="mb-4">
            <label class="dk-sr-only" for="ab-suche">Im Adressbuch suchen</label>
            <input
                id="ab-suche"
                v-model="search"
                type="text"
                aria-label="Im Adressbuch suchen"
                placeholder="Suchen nach Name, E-Mail oder Ort..."
                class="dk-form-input max-w-md"
            />
        </div>

        <!-- OP-HANDY-19: Liste der Personen am Handy als Karten mit Anruf- und
             Mail-Verknüpfung. Die Tabelle lief seitlich über (437–445 px in
             einer 340-px-Karte), die Spalte „Telefon“ lag außerhalb, und es gab
             keinen einzigen tel:/mailto:-Link — „jemanden anrufen“ war damit
             unmöglich. Die Tabelle bleibt am Schreibtisch (dort ist Platz). -->
        <div class="ab-karten dk-card">
            <DkSkelett v-if="loading" form="tabelle" :anzahl="6" text="Adressbuch wird geladen …" class="adr-zustand" />
            <div v-else-if="error" class="dk-list-empty adr-zustand adr-fehler">{{ error }}</div>
            <DkEmpty
              v-else-if="filteredMitglieder.length === 0"
              icon="📇"
              :title="adrFilterAktiv ? 'Kein Eintrag gefunden' : 'Noch keine Einträge'"
              :text="adrFilterAktiv
                ? 'Passe die Suche an.'
                : 'Sobald Kontaktdaten freigegeben sind, erscheinen sie hier.'"
            />
            <article v-else v-for="m in filteredMitglieder" :key="'k' + m.name" class="ab-karte">
                <div class="ab-karte-kopf">
                    <!-- DSGVO-2d: Eine gelöschte Person hat kein Profil mehr.
                         Der Name bleibt (der Server liefert „Gelöschte Person“),
                         der Link entfällt — er führte auf eine Fehlerseite. -->
                    <a v-if="darfProfilLink(m)" class="ab-karte-name" :href="'#/mitglied/' + m.name">
                        {{ m.vorname }} {{ m.nachname }}
                    </a>
                    <span v-else class="ab-karte-name">{{ m.vorname }} {{ m.nachname }}</span>
                    <span v-if="m.wohnort" class="ab-karte-ort">{{ m.postleitzahl }} {{ m.wohnort }}</span>
                </div>
                <div class="ab-karte-aktionen">
                    <a v-if="m.telefonnummer" class="ab-aktion" :href="'tel:' + telHref(m.telefonnummer)" :aria-label="'Anrufen: ' + m.vorname + ' ' + m.nachname">
                        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72c.127.96.361 1.903.7 2.81a2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45c.907.339 1.85.573 2.81.7A2 2 0 0 1 22 16.92z"/></svg>
                        {{ m.telefonnummer }}
                    </a>
                    <a v-if="m.email" class="ab-aktion" :href="'mailto:' + m.email" :aria-label="'E-Mail schreiben: ' + m.vorname + ' ' + m.nachname">
                        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="2" y="4" width="20" height="16" rx="2"/><polyline points="22,6 12,13 2,6"/></svg>
                        {{ m.email }}
                    </a>
                    <a v-if="darfProfilLink(m)" class="ab-aktion ab-aktion--leise" :href="'#/mitglied/' + m.name">Profil</a>
                </div>
            </article>
        </div>

        <!-- Tabelle (Schreibtisch) -->
        <div class="ab-tabelle overflow-x-auto dk-card">
            <table class="dk-table">
                <thead>
                    <tr>
                        <th>Name</th>
                        <th>E-Mail</th>
                        <th>Telefon</th>
                        <th>PLZ</th>
                        <th>Ort</th>
                    </tr>
                </thead>
                <tbody>
                    <tr v-if="loading">
                        <td colspan="5">
                            <DkSkelett form="zeilen" :anzahl="4" text="Einträge werden geladen …" class="adr-zustand" />
                        </td>
                    </tr>
                    <tr v-else-if="error">
                        <td colspan="5">
                            <div class="dk-list-empty adr-zustand adr-fehler">{{ error }}</div>
                        </td>
                    </tr>
                    <tr v-else-if="filteredMitglieder.length === 0">
                        <td colspan="5">
                            <DkEmpty
                              icon="📇"
                              :title="adrFilterAktiv ? 'Kein Eintrag gefunden' : 'Noch keine Einträge'"
                              :text="adrFilterAktiv ? 'Passe die Suche an.' : 'Sobald Kontaktdaten freigegeben sind, erscheinen sie hier.'"
                            />
                        </td>
                    </tr>
                    <tr
                        v-for="m in filteredMitglieder"
                        :key="m.name"
                    >
                        <td class="font-medium text-[var(--dk-text)]">
                            <a v-if="darfProfilLink(m)" class="dk-zellen-link" :href="'#/mitglied/' + m.name">{{ m.vorname }} {{ m.nachname }}</a>
                            <span v-else>{{ m.vorname }} {{ m.nachname }}</span>
                        </td>
                        <td class="text-[var(--dk-text-muted)]">
                            <a v-if="m.email" class="ab-tab-link" :href="'mailto:' + m.email">{{ m.email }}</a>
                            <template v-else>-</template>
                        </td>
                        <td class="text-[var(--dk-text-muted)]">
                            <a v-if="m.telefonnummer" class="ab-tab-link" :href="'tel:' + telHref(m.telefonnummer)">{{ m.telefonnummer }}</a>
                            <template v-else>-</template>
                        </td>
                        <td class="text-[var(--dk-text-muted)]">{{ m.postleitzahl || '-' }}</td>
                        <td class="text-[var(--dk-text-muted)]">{{ m.wohnort || '-' }}</td>
                    </tr>
                </tbody>
            </table>
        </div>
    </div>
</template>

<script>
import { ref, computed, watch, onMounted } from 'vue'
import { apiCall } from '../composables/useApi.js'
import { suchNormal } from '../composables/bf1Anzeige.js'
import { telHref } from '../composables/adressbuch.mjs'
import { darfProfilLink } from '../composables/geloeschte-person.mjs'

import DkEmpty from '../components/ui/DkEmpty.vue'
import DkSkelett from '../components/ui/DkSkelett.vue'

export default {
    name: 'Adressbuch',
    components: { DkEmpty, DkSkelett },
    setup() {
        const mitglieder = ref([])
        const loading = ref(false)
        const error = ref(null)
        const search = ref('')

        async function loadMitglieder() {
            loading.value = true
            error.value = null
            try {
                const payload = await apiCall('diakronos.diakonos.api.mitglieder.get_adressbuch', {
                    start: 0,
                    limit: 100,
                    suche: search.value || undefined,
                })
                mitglieder.value = payload?.data || []
            } catch (err) {
                error.value = err?.message || 'Fehler beim Laden der Mitglieder'
                console.error('Adressbuch loadMitglieder error:', err)
            } finally {
                loading.value = false
            }
        }

        // BF1-J: Der Server sucht bereits gross-/kleinschreibungs- und
        // umlautunabhaengig (get_adressbuch). Der lokale Feinfilter darf das
        // Ergebnis nicht wieder verwerfen — sonst findet „weiss“ den vom Server
        // gelieferten Treffer „Weiß“ nicht mehr. Deshalb dieselbe Normalisierung
        // wie der Server (geteilte Helferin aus bf1Anzeige.js).
        const filteredMitglieder = computed(() => {
            const q = suchNormal(search.value)
            if (!q) return mitglieder.value
            return mitglieder.value.filter((m) => {
                const name = suchNormal(`${m.vorname || ''} ${m.nachname || ''}`)
                const email = suchNormal(m.email)
                const ort = suchNormal(m.wohnort)
                return name.includes(q) || email.includes(q) || ort.includes(q)
            })
        })

        // OP-UI-19: unterscheidet „nichts gefunden“ von „noch nichts da“.
        const adrFilterAktiv = computed(() => !!String(search.value || '').trim())

        // Debounce-Suche (300 ms)
        let debounceTimer = null
        watch(search, () => {
            clearTimeout(debounceTimer)
            debounceTimer = setTimeout(() => {
                loadMitglieder()
            }, 300)
        })

        onMounted(() => {
            loadMitglieder()
        })

        return {
            search,
            loading,
            error,
            filteredMitglieder,
            adrFilterAktiv,
            telHref,
            // DSGVO-2d: eine gelöschte Person hat kein Profil (Link entfällt).
            darfProfilLink,
        }
    },
}
</script>

<style scoped>
/* DES-02: Abstände/Farbe der Zustandsflächen als Klassen. */
.adr-zustand { padding: var(--sp-8) var(--sp-6); }
.adr-fehler { color: var(--err); }

/* OP-HANDY-19: Kartenliste statt 5-Spalten-Tabelle auf schmalen Anzeigen. */
.ab-karten { display: none; }
.ab-karte {
  padding: 12px 14px;
  border-bottom: 1px solid var(--dk-divider);
}
.ab-karte:last-child { border-bottom: none; }
.ab-karte-kopf {
  display: flex; align-items: baseline; justify-content: space-between;
  gap: 8px; flex-wrap: wrap;
  margin-bottom: 8px;
}
.ab-karte-name { font-weight: 600; color: var(--dk-text); text-decoration: none; }
.ab-karte-name:hover { text-decoration: underline; }
.ab-karte-ort { font-size: 12px; color: var(--dk-text-muted); }
.ab-karte-aktionen { display: flex; flex-wrap: wrap; gap: 8px; }
.ab-aktion {
  display: inline-flex; align-items: center; gap: 5px;
  padding: 7px 11px;
  border: 1px solid var(--dk-border);
  border-radius: 9px;
  background: var(--dk-surface-2);
  color: var(--dk-text);
  font-size: 13px; font-weight: 500;
  text-decoration: none;
}
.ab-aktion--leise { color: var(--dk-text-muted); }
.ab-aktion:focus-visible { outline: 2px solid var(--focus-ring); outline-offset: 1px; }
.ab-tab-link { color: inherit; text-decoration: none; }
.ab-tab-link:hover { text-decoration: underline; }

@media (max-width: 720px) {
  .ab-tabelle { display: none; }
  .ab-karten { display: block; }
}
</style>
