<template>
  <div class="gem-abschnitt">
    <!-- UX2f2b (Befund): Hier stand ein zweites `<h2>` — die Seite „Gemeinde“
         ist eine Seite unter Einstellungen und trägt ihre Überschrift schon im
         Seitenkopf. Der Einleitungssatz bleibt. -->
    <p>Name, Kontakt und die Adresse, unter der die Gemeinde im Netz erreichbar ist.
      Diese Angaben erscheinen in der App und in geteilten Links.</p>

    <!-- ON-4 (H2): amber Leiste „Die Gemeinde ist noch nicht eingerichtet.“
         mit den fehlenden Angaben (Name, Logo, Kontakt). Sie erscheint nach
         dem Assistenten nur solange einer dieser Punkte offen ist
         (`hinweisFuer('gemeinde')`). -->
    <EinrichtungsLeiste seite="gemeinde" :rollen="rollen" />

    <DkHint v-if="laedt" role="status">Gemeinde-Einstellungen werden geladen …</DkHint>
    <DkHint v-if="fehler" variant="err" role="alert">{{ fehler }}</DkHint>
    <DkButton v-if="!geladen && !laedt" variant="secondary" @click="laden">Erneut versuchen</DkButton>

    <form ref="formular" @submit.prevent="speichernMitFokus">
      <fieldset :disabled="!bedienbar" class="gem-felder">
        <DkCard title="Name und Kontakt">
          <DkField label="Name der Gemeinde" required :error="feldFehler.gemeindename" v-slot="feld">
            <input v-bind="feld.feldProps" v-model="gemeindename" class="dk-ui-eingabe" maxlength="140"
              placeholder="z. B. Versöhnungskirche Heilbronn" />
          </DkField>
          <!-- ON-4 (Nachtrag Orchestrator 2026-11-03): Die Angaben aus dem
               Assistenten werden nach der Ersteinrichtung AUSSCHLIESSLICH hier
               gepflegt — Kurzname, Logo, Anschrift, Telefon, Website. -->
          <DkField label="Kurzname" :error="feldFehler.kurzname"
            help="Erscheint in Kopfzeile und Kalenderkürzeln." v-slot="feld">
            <input v-bind="feld.feldProps" v-model="kurzname" class="dk-ui-eingabe" maxlength="40"
              placeholder="z. B. Versöhnungskirche" />
          </DkField>
          <!-- UX2f: E-Mail mit Prüfung — die Meldung steht am Feld (beim
               Verlassen, danach beim Tippen), nicht erst nach dem Speichern. -->
          <DkField label="Kontakt-E-Mail" help="An diese Adresse wenden sich Personen mit Fragen."
            :error="feldFehler.kontakt_email" :regel="emailRegel()" :wert="kontaktEmail"
            maxlength="255" @update:wert="kontaktEmail = $event" v-slot="feld">
            <DkEingabe v-bind="feld.feldProps" type="email" placeholder="buero@gemeinde.example" />
          </DkField>
        </DkCard>

        <!-- ON-4: Logo (ON-2) — Hochladen/Entfernen mit derselben Vorprüfung wie
             im Assistenten; eingebunden NUR per `<img>` (kein Markup). -->
        <DkCard title="Logo">
          <p class="gem-hilfe">Erscheint in der Seitenleiste und auf der Anmeldeseite.
            Ohne Logo zeigt Diakronos ein Monogramm.</p>
          <div class="gem-logo">
            <LogoMarke :quelle="logoUrl" :buchstabe="monogramm" size="lg" />
            <div class="gem-logo-aktionen">
              <p class="gem-hilfe">{{ logoUrl ? 'Logo hinterlegt' : 'Kein Logo hinterlegt' }}</p>
              <div class="gem-logo-knoepfe">
                <label class="gem-logo-waehlen">
                  {{ logoLaeuft ? 'Wird geladen …' : 'Datei auswählen' }}
                  <input type="file" class="gem-logo-datei"
                    accept="image/png,image/jpeg,image/webp,image/svg+xml"
                    :disabled="logoLaeuft || !bedienbar" @change="dateiGewaehlt" />
                </label>
                <DkButton v-if="logoUrl" variant="ghost" size="sm"
                  :disabled="logoLaeuft || !bedienbar" @click="logoEntfernen">
                  Entfernen
                </DkButton>
              </div>
              <p class="gem-hilfe">PNG, JPEG, WebP oder SVG, quadratisch empfohlen, max. 2 MB</p>
              <p v-if="logoFehler" class="gem-logo-fehler" role="alert">{{ logoFehler }}</p>
            </div>
          </div>
        </DkCard>

        <DkCard title="Anschrift und Erreichbarkeit">
          <DkField label="Straße und Hausnummer" :error="feldFehler.strasse" v-slot="feld">
            <input v-bind="feld.feldProps" v-model="strasse" class="dk-ui-eingabe" maxlength="120"
              autocomplete="street-address" placeholder="z. B. Kirchplatz 1" />
          </DkField>
          <div class="gem-paar">
            <DkField label="PLZ" :error="feldFehler.plz" :regel="plzRegel()" :wert="plz"
              maxlength="10" @update:wert="plz = $event" v-slot="feld">
              <input v-bind="feld.feldProps" v-model="plz" class="dk-ui-eingabe" maxlength="10"
                inputmode="numeric" autocomplete="postal-code" placeholder="z. B. 12345" />
            </DkField>
            <DkField label="Ort" :error="feldFehler.ort" v-slot="feld">
              <input v-bind="feld.feldProps" v-model="ort" class="dk-ui-eingabe" maxlength="120"
                autocomplete="address-level2" placeholder="z. B. Musterstadt" />
            </DkField>
          </div>
          <DkField label="Telefon" :error="feldFehler.telefon" v-slot="feld">
            <input v-bind="feld.feldProps" v-model="telefon" class="dk-ui-eingabe" type="tel"
              maxlength="40" placeholder="z. B. +49 7131 123456" />
          </DkField>
          <DkField label="Website" :error="feldFehler.website" :regel="urlRegel()"
            :wert="website" maxlength="255"
            help="Beginnt mit https:// — z. B. https://gemeinde.example.org."
            @update:wert="website = $event" v-slot="feld">
            <input v-bind="feld.feldProps" v-model="website" class="dk-ui-eingabe" maxlength="255"
              inputmode="url" placeholder="https://gemeinde.example.org" />
          </DkField>
          <!-- Zeitzone: NUR ANZEIGE (Betriebseinstellung CALENDAR_TIMEZONE). -->
          <p class="gem-hilfe">
            Zeitzone: <strong>{{ zeitzone || '—' }}</strong>
            <template v-if="zeitzoneHinweis"> — {{ zeitzoneHinweis }}</template>
          </p>
        </DkCard>

        <DkCard title="Öffentliche Adresse">
          <p class="gem-hilfe">Die Adresse, unter der die Gemeinde von außen erreichbar ist.
            Geteilte Links (Registrierung, Passwort) werden damit vollständig gebaut.
            Bleibt sie leer, nimmt die App die Adresse aus dem Browser.</p>
          <!-- UX2f: Die Adressform wird jetzt schon AM FELD geprüft (bisher
               erst beim Speichern); die Sammelprüfung beim Speichern bleibt. -->
          <DkField label="Adresse" :error="feldFehler.adresse" :regel="urlRegel()"
            :wert="oeffentlicheAdresse" maxlength="255"
            help="Beginnt mit https:// — z. B. https://gemeinde.example.org."
            @update:wert="oeffentlicheAdresse = $event" v-slot="feld">
            <DkEingabe v-bind="feld.feldProps" type="text" inputmode="url"
              placeholder="https://gemeinde.example.org" />
          </DkField>
        </DkCard>

        <DkCard title="Willkommenstext">
          <p class="gem-hilfe">Erscheint auf der Registrierungs- und Gast-Anmeldeseite
            über dem Formular – ein kurzer Satz genügt.</p>
          <DkField label="Text" v-slot="feld">
            <textarea v-bind="feld.feldProps" v-model="willkommenstext" class="dk-ui-eingabe" rows="3"
              maxlength="4000"></textarea>
          </DkField>
        </DkCard>

        <DkButton type="submit" variant="primary" :loading="speichert">Speichern</DkButton>
      </fieldset>
    </form>
    <DkErfolgsmeldung :text="erfolg" />

    <DkCard title="Module">
      <p class="gem-hilfe">Zeigt an, welche Bereiche in der Navigation erscheinen.
        Die Anzeigenamen stammen aus der Einrichtung.</p>
      <ul class="gem-module">
        <li v-for="m in module" :key="m.schluessel" class="gem-modul">
          <label class="gem-schalter">
            <input type="checkbox" :checked="m.sichtbar" :disabled="!bedienbar || modulSpeichert === m.schluessel"
              @change="modulSchalten(m.schluessel, $event.target.checked)" />
            <span><strong>{{ m.anzeige }}</strong><span class="gem-hilfe">{{ m.schluessel }}</span></span>
          </label>
        </li>
      </ul>
    </DkCard>
  </div>
</template>

<script setup>
import { ref, computed, nextTick, onMounted } from 'vue'
import { useGemeinde } from '../../composables/useGemeinde.js'
import { monogramm as monogrammFuer } from '../../composables/einrichtung.mjs'
import DkButton from '../../components/ui/DkButton.vue'
import DkCard from '../../components/ui/DkCard.vue'
import DkHint from '../../components/ui/DkHint.vue'
import DkField from '../../components/ui/DkField.vue'
import DkErfolgsmeldung from '../../components/ui/DkErfolgsmeldung.vue'
import DkEingabe from '../../components/ui/DkEingabe.vue'
// UX2f: Prüfregeln aus EINER Quelle (Feld, Assistent und Sammelprüfung).
import { email as emailRegel, plz as plzRegel, url as urlRegel } from '../../composables/feldPruefung.mjs'
// ON-4/H2: amber Leiste „… ist noch nicht eingerichtet.“
import EinrichtungsLeiste from '../../components/einrichtung/EinrichtungsLeiste.vue'
// ON-4/H4: Logo oder Monogramm (dieselbe Einbindung wie Seitenleiste/Assistent).
import LogoMarke from '../../components/einrichtung/LogoMarke.vue'

defineProps({ embedded: Boolean })

const { laedt, speichert, geladen, fehler, erfolg, gemeindename, kontaktEmail,
  oeffentlicheAdresse, willkommenstext, linkLaufzeitTage, linkMaxAnmeldungen,
  module, modulSpeichert, bedienbar, laden, speichern, modulSchalten,
  kurzname, strasse, plz, ort, telefon, website, zeitzone, zeitzoneHinweis,
  logoUrl, logoLaeuft, logoFehler, logoHochladen, logoEntfernen } = useGemeinde()

// ON-4/H2: Boot-Objekt — `is_admin` entscheidet über die Leiste (Server: 403).
const rollen = window.__DIakonosBOOT || {}

const formular = ref(null)
const feldFehler = ref({})

// UX2f: Prüfregeln der Felder — direkt aus EINER Quelle. Alle Angaben sind
// freiwillig; die Regeln lassen ein leeres Feld in Ruhe (UX2f2a), deshalb
// braucht es hier KEINE `…Frei`-Hüllen mehr (UX2f2b, Punkt 4). Pflicht wäre
// eine Fachertscheidung und steht nicht dahinter.
// Dieselben Regeln nutzt auch die Sammelprüfung in `pruefeSchritt`.

/** Monogramm wie überall (Kurzname vor Gemeindename, `monogramm()`). */
const monogramm = computed(() => {
  const buchstabe = monogrammFuer({ kurzname: kurzname.value, gemeindename: gemeindename.value })
  return buchstabe === '?' ? '' : buchstabe
})

/**
 * Speichern: die Adressform der öffentlichen Adresse prüft diese Seite (sie
 * ist kein Feld des Assistenten), alles andere kommt aus `pruefeSchritt` —
 * dieselben Validierungen wie im Assistenten, keine Kopie.
 */
async function speichernMitFokus() {
  // UX2f2b (Befund): Hier wurde der Fehler IMMER gesetzt — bei gültiger
  // Adresse stand `adresse: ''` im Objekt, `Object.keys(...).length` war
  // dadurch nie 0 und `speichernMitFokus` brach JEDES Mal ab: die API wurde
  // nie gerufen. Jetzt steht nur eine ECHTE Meldung im Objekt (gleiches
  // Muster wie `useGemeinde.speichern`: nur beanstandete Felder).
  feldFehler.value = {}
  const adressMeldung = urlRegel()(oeffentlicheAdresse.value)
  if (adressMeldung) feldFehler.value.adresse = adressMeldung
  if (Object.keys(feldFehler.value).length) {
    await nextTick()
    formular.value?.querySelector('[aria-invalid="true"]')?.focus()
    return
  }
  // Link-Vorgaben werden auf der Karte „Registrierung“ gepflegt und hier
  // weggelassen — der Server laesst sie dann unveraendert.
  const erfolgGespeichert = await speichern({ mitLinkVorgaben: false })
  if (erfolgGespeichert === false) {
    // Absage am FELD statt nur als Meldung (wie im Assistenten): die
    // Pruefungen stehen in `useGemeinde` (dieselbe Quelle). Der erste
    // Fehlertext nennt das Feld; fokussiert wird das erste ungueltige.
    await nextTick()
    formular.value?.querySelector('[aria-invalid="true"]')?.focus()
  }
}

/** Dateiauswahl des Logos: sofort hochladen (Entwurf 04: „Datei auswählen“). */
function dateiGewaehlt(ereignis) {
  const datei = ereignis?.target?.files?.[0]
  if (!datei) return
  logoHochladen(datei)
  if (ereignis.target) ereignis.target.value = ''
}

onMounted(laden)
</script>

<style scoped>
.gem-abschnitt, .gem-felder { display: grid; gap: var(--sp-4); min-width: 0; }
.gem-abschnitt p { margin: 0; }
.gem-felder { padding: 0; border: 0; margin: 0; }
.gem-felder:disabled { opacity: .65; }
.gem-hilfe { display: block; color: var(--muted); font-size: var(--fs-sm); }
.gem-module { list-style: none; padding: 0; margin: var(--sp-3) 0 0; display: grid; gap: var(--sp-2); }
.gem-schalter { display: flex; align-items: flex-start; gap: var(--sp-2); }
.gem-schalter input { margin-top: var(--sp-1); flex-shrink: 0; }
/* ON-4: Logo-Vorschau + Aktionen (wie im Assistenten, hier im Einstellungs-Satz). */
.gem-logo { display: flex; gap: var(--sp-4); align-items: flex-start; flex-wrap: wrap; }
.gem-logo-aktionen { display: flex; flex-direction: column; gap: var(--sp-2); min-width: 0; }
.gem-logo-knoepfe { display: flex; gap: var(--sp-2); flex-wrap: wrap; align-items: center; }
.gem-logo-waehlen {
  position: relative;
  display: inline-flex;
  align-items: center;
  height: var(--control-h);
  padding: 0 var(--sp-4);
  border: 1px solid var(--line-strong);
  border-radius: var(--radius);
  background: var(--surface);
  color: var(--text);
  font-size: var(--fs);
  font-weight: 550;
  cursor: pointer;
}
.gem-logo-waehlen:focus-within { outline: 2px solid var(--focus-ring); outline-offset: 2px; }
.gem-logo-datei { position: absolute; width: 1px; height: 1px; opacity: 0; overflow: hidden; }
.gem-logo-fehler { margin: 0; color: var(--err); font-size: var(--fs-sm); font-weight: 600; }
.gem-paar { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 2fr); gap: var(--sp-3); }
@media (max-width: 720px) { .gem-paar { grid-template-columns: 1fr; } }
</style>
