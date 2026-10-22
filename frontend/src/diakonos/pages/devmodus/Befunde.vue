<template>
  <div class="dk-screen dk-screen-enter">
    <DkPageHeader title="Dev-Befunde"
                  sub="Gemeldete Fehler, Wünsche und Fragen mit Bild, Element und URL."
                  :krumen="[{ text: 'Start', href: '#/' }, { text: 'Dev-Befunde' }]" />

    <div class="dk-dm-leiste">
      <label class="dk-dm-filter">Status
        <select v-model="filter.status" @change="laden">
          <option value="alle">alle</option>
          <option value="offen">offen</option>
          <option value="an_claude">an Claude</option>
          <option value="behoben">behoben</option>
          <option value="verworfen">verworfen</option>
        </select>
      </label>
      <label class="dk-dm-filter">Art
        <select v-model="filter.art" @change="laden">
          <option value="">alle</option>
          <option value="fehler">Fehler</option>
          <option value="design">Design</option>
          <option value="wunsch">Wunsch</option>
          <option value="frage">Frage</option>
        </select>
      </label>
      <DkButton variant="secondary" size="sm" type="button" :disabled="laeuft" @click="laden">
        Aktualisieren
      </DkButton>
      <DkButton variant="secondary" size="sm" type="button" :disabled="laeuft" @click="bericht">
        Bericht erzeugen
      </DkButton>
      <span v-if="meldung" class="dk-dm-hinweis">{{ meldung }}</span>
    </div>

    <DkEmpty v-if="!befunde.length && !laeuft"
             title="Keine Befunde"
             text="Im gewählten Filter liegt nichts vor." />

    <ul class="dk-dm-liste">
      <li v-for="b in befunde" :key="b.name" class="dk-dm-karte" :class="`is-${b.status}`">
        <button class="dk-dm-kopf" type="button" :aria-expanded="Boolean(offen[b.name])"
                @click="umschalten(b)">
          <span class="dk-dm-art" :class="`is-${b.art}`">{{ b.art }}</span>
          <span class="dk-dm-titel">{{ b.titel || ersteZeile(b.text) || b.name }}</span>
          <span class="dk-dm-status" :class="`is-${b.status}`">{{ b.status }}</span>
        </button>
        <div v-if="offen[b.name]" class="dk-dm-detail">
          <img v-if="(b.bilder || []).length" class="dk-dm-vorschau" :src="bildUrl(b.bilder[0])"
               :alt="'Bild zu ' + (b.titel || b.name)" @click="gross(b.bilder[0])" />
          <p class="dk-dm-text">{{ b.text || '(ohne Beschreibung)' }}</p>
          <dl class="dk-dm-meta">
            <dt>Ort</dt><dd>{{ b.seite || '—' }} · {{ b.route || '—' }}</dd>
            <dt>URL</dt><dd class="dk-dm-umbrich">{{ b.url || '—' }}</dd>
            <dt>Element</dt>
            <dd><code>{{ (b.element || {}).selektor || '—' }}</code>
              <span v-if="(b.element || {}).komponenten?.length">
                · {{ (b.element.komponenten).join(' &gt; ') }}</span></dd>
            <dt>Gerät</dt><dd>{{ b.viewport || '—' }} · {{ b.geraet || '—' }}</dd>
            <dt>Zeit</dt><dd>{{ b.zeitpunkt || '—' }} · von {{ b.benutzer || '—' }}</dd>
            <dt>Fehlerumfeld</dt><dd>{{ (b.fehlerumfeld || []).length }} Einträge (letzte 60 s)</dd>
          </dl>
          <div v-if="(b.bilder || []).length > 1" class="dk-dm-bilder">
            <img v-for="(p, i) in b.bilder.slice(1)" :key="i" :src="bildUrl(p)"
                 :alt="'Bild ' + (i + 2) + ' zu ' + (b.titel || b.name)" @click="gross(p)" />
          </div>
          <div class="dk-dm-aktionen">
            <DkButton variant="secondary" size="sm" type="button" @click="setzen(b, 'offen')">offen</DkButton>
            <DkButton variant="secondary" size="sm" type="button" @click="setzen(b, 'an_claude')">an Claude</DkButton>
            <DkButton variant="secondary" size="sm" type="button" @click="setzen(b, 'behoben')">behoben</DkButton>
            <DkButton variant="secondary" size="sm" type="button" @click="setzen(b, 'verworfen')">verworfen</DkButton>
            <DkButton v-if="istAdmin" variant="danger" size="sm" type="button" @click="loeschen(b)">löschen</DkButton>
          </div>
        </div>
      </li>
    </ul>

    <div v-if="grossesBild" class="dk-dm-gross" @click="grossesBild = null">
      <img :src="grossesBild" alt="Befund-Bild groß" />
    </div>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'

import DkButton from '../../components/ui/DkButton.vue'
import DkEmpty from '../../components/ui/DkEmpty.vue'
import DkPageHeader from '../../components/ui/DkPageHeader.vue'
import { bildUrl as bildUrlRoh, devmodusApi, fehlerZeilen } from '../../composables/useDevmodus.js'
import { useSession } from '../../composables/useSession.js'
import { showToast } from '../../composables/useToast.js'
import { bestaetigen } from '../../composables/useBestaetigen.js'

const { isAdmin: istAdmin } = useSession()

const befunde = ref([])
const offen = reactive({})
const grossesBild = ref(null)
const laeuft = ref(false)
const meldung = ref('')
const filter = reactive({ status: 'alle', art: '' })

/** Befund-Bild ueber den Dev-Modus-Endpunkt (UXM-R12), nicht ueber /files. */
function bildUrl(pfad) { return bildUrlRoh(pfad) }

function ersteZeile(text) {
  return String(text || '').split('\n').map(z => z.trim()).find(Boolean) || ''
}

function umschalten(b) { offen[b.name] = !offen[b.name] }

async function laden() {
  laeuft.value = true
  meldung.value = ''
  try {
    const args = {}
    if (filter.status && filter.status !== 'alle') args.status = filter.status
    if (filter.art) args.art = filter.art
    befunde.value = await devmodusApi.befunde(args) || []
  } catch (f) {
    meldung.value = fehlerZeilen(f).join(' | ')
  } finally {
    laeuft.value = false
  }
}

async function setzen(b, status) {
  try {
    await devmodusApi.befundSetzen(b.name, status)
    b.status = status
    showToast('Status geändert', 'success')
  } catch (f) {
    meldung.value = fehlerZeilen(f).join(' | ')
  }
}

async function loeschen(b) {
  if (!await bestaetigen({ titel: 'Befund löschen?', text: 'Ein Befund wird dauerhaft gelöscht.', aktion: 'Löschen', gefahr: true })) return
  try {
    await devmodusApi.befundLoeschen(b.name)
    befunde.value = befunde.value.filter(x => x.name !== b.name)
    showToast('Befund gelöscht', 'success')
  } catch (f) {
    meldung.value = fehlerZeilen(f).join(' | ')
  }
}

async function bericht() {
  try {
    const antwort = await devmodusApi.berichtErzeugen()
    meldung.value = 'Bericht: ' + (antwort?.bericht || 'erzeugt')
  } catch (f) {
    meldung.value = fehlerZeilen(f).join(' | ')
  }
}

function gross(pfad) { grossesBild.value = bildUrlRoh(pfad) }

onMounted(laden)
</script>

<style scoped>
.dk-dm-leiste { display: flex; gap: var(--sp-3); align-items: center; flex-wrap: wrap; margin: var(--sp-4) 0; }
.dk-dm-filter { display: flex; gap: 6px; align-items: center; font-size: var(--fs); }
.dk-dm-filter select {
  font: inherit; padding: 6px; border-radius: var(--radius-sm);
  border: 1px solid var(--line); background: var(--surface); color: var(--text);
}
.dk-dm-hinweis { color: var(--muted); font-size: var(--fs-sm); }
.dk-dm-liste { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: var(--sp-3); }
.dk-dm-karte {
  border: 1px solid var(--line); border-radius: var(--radius-lg);
  background: var(--surface); overflow: hidden;
}
.dk-dm-karte.is-offen { border-left: 4px solid var(--accent); }
.dk-dm-karte.is-an_claude { border-left: 4px solid var(--warn); }
.dk-dm-karte.is-behoben { border-left: 4px solid var(--ok); }
.dk-dm-kopf {
  display: flex; gap: var(--sp-3); align-items: center; padding: var(--pad);
  cursor: pointer; width: 100%; text-align: left; background: transparent;
  border: 0; color: inherit; font: inherit;
}
.dk-dm-kopf:hover { background: var(--surface-hover); }
.dk-dm-kopf:focus-visible { outline: 2px solid var(--focus-ring); outline-offset: -2px; }
.dk-dm-art { font-size: var(--fs-xs); padding: 2px 6px; border-radius: var(--radius-sm); background: var(--surface-2); }
.dk-dm-titel { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.dk-dm-status { font-size: var(--fs-xs); color: var(--muted); }
.dk-dm-detail { padding: 0 var(--pad) var(--pad); display: flex; flex-direction: column; gap: var(--sp-2); }
.dk-dm-vorschau { max-width: 100%; max-height: 260px; border-radius: var(--radius-sm); cursor: zoom-in; }
.dk-dm-bilder { display: flex; gap: 6px; flex-wrap: wrap; }
.dk-dm-bilder img { max-width: 120px; max-height: 90px; border-radius: var(--radius-sm); cursor: zoom-in; }
.dk-dm-text { margin: 0; }
.dk-dm-meta { display: grid; grid-template-columns: 90px 1fr; gap: 2px var(--sp-3); margin: 0; font-size: var(--fs-sm); }
.dk-dm-meta dt { color: var(--muted); }
.dk-dm-meta dd { margin: 0; }
.dk-dm-umbrich { overflow-wrap: anywhere; }
.dk-dm-aktionen { display: flex; gap: 6px; flex-wrap: wrap; }
.dk-dm-gross {
  position: fixed; inset: 0; background: color-mix(in oklch, var(--dk-navy-900) 80%, transparent);
  display: flex; align-items: center; justify-content: center; z-index: var(--z-modal); cursor: zoom-out;
}
.dk-dm-gross img { max-width: 94vw; max-height: 94vh; }
@media (max-width: 600px) {
  .dk-dm-meta { grid-template-columns: 1fr; }
  .dk-dm-meta dt { margin-top: 6px; }
}
</style>
