<template>
    <!-- REG-1b: EINE Anzeige des Anmeldeformulars.
         Genau diese Vorlage erscheint auf der oeffentlichen Registrierungsseite
         (`registrierung/App.vue`) UND in der Vorschau des Formular-Editors
         (`#/mitglieder/anfragen`, Reiter Formulare). Damit kann die Vorschau
         nicht von der Wirklichkeit abweichen.

         `vorschau`: das Formular wird gezeigt, aber nicht abgeschickt —
         die Felder bleiben bedienbar (Bild, Umbruch, Pflichtzeichen pruefbar),
         der Absende-Knopf ist abgeschaltet und ein Hinweis steht darueber.

         Reiner Text, nirgends `v-html`: die Beschreibung kommt als Klartext
         vom Server (auch '<' und '>'), Maskieren ist Sache der Interpolation. -->
    <div class="dk-pub-koerper" :data-vorschau="vorschau ? '' : null">
        <div v-if="vorschau" class="dk-pub-vorschau-hinweis" role="note">
            Vorschau — so sehen Besucher das Formular. Absenden ist hier nicht möglich.
        </div>

        <!-- Bild ueber dem Formularkopf. Dekorativ (leerer alt-Text). -->
        <img v-if="bannerBild" :src="bannerBild" alt="" class="dk-pub-banner" />

        <h1 class="dk-pub-title">{{ titel }}</h1>
        <p class="dk-pub-muted" style="margin-bottom:24px">{{ subtitel }}</p>

        <!-- Beschreibung der Gemeinde (REG-1a/REG-1b): reiner Text. -->
        <p v-if="beschreibung" class="dk-pub-beschreibung">{{ beschreibung }}</p>

        <!-- WEB-8e (E3): die Seite wurde gerade automatisch neu geladen
             (CSRF-Heilung, frisches Seiten-Token) — die Eingaben sind weg,
             das muss die Person wissen. Genau EINMAL. -->
        <p v-if="nachNeuladen" role="note" class="dk-pub-hinweis-neuladen">
            {{ hinweisNachNeuladen }}
        </p>

        <DkFehlertext v-if="fehler" :message="fehler" class="mb-4" />

        <form @submit.prevent="vorschau ? null : absenden()" class="dk-pub-form" novalidate>
            <div class="dk-pub-grid-2">
                <!-- UX2f: Feld mit Prüfung — Meldung beim Verlassen des Feldes,
                     danach beim Tippen; direkt am Feld, nicht nur oben im Kasten. -->
                <DkField label="Vorname" required :regel="regelVorname" :wert="form.vorname"
                         pflicht-name="einen Vornamen" maxlength="140"
                         v-slot="feld"
                         @update:wert="form.vorname = $event">
                    <input v-bind="feld.feldProps" type="text" autocomplete="given-name" />
                </DkField>
                <DkField label="Nachname" required :regel="regelNachname" :wert="form.nachname"
                         pflicht-name="einen Nachnamen" maxlength="140"
                         v-slot="feld"
                         @update:wert="form.nachname = $event">
                    <input v-bind="feld.feldProps" type="text" autocomplete="family-name" />
                </DkField>
            </div>
            <DkField label="E-Mail (empfohlen)" :regel="regelEmail" :wert="form.email"
                     maxlength="255"
                     help="Ohne Adresse kann die Gemeinde dich nicht erreichen."
                     v-slot="feld"
                     @update:wert="form.email = $event">
                <input v-bind="feld.feldProps" type="email" autocomplete="email" />
            </DkField>
            <div class="dk-pub-grid-2">
                <DkField label="Telefon (optional)">
                    <template #default="{ id, ariaDescribedby, ariaInvalid }">
                        <DkEingabe :id="id" type="tel" v-model="form.telefon" autocomplete="tel"
                                   :aria-describedby="ariaDescribedby" :aria-invalid="ariaInvalid" />
                    </template>
                </DkField>
                <DkField label="Geburtstag (optional)">
                    <template #default="{ id, ariaDescribedby, ariaInvalid }">
                        <DkEingabe :id="id" type="date" v-model="form.geburtstag"
                                   :aria-describedby="ariaDescribedby" :aria-invalid="ariaInvalid" />
                    </template>
                </DkField>
            </div>

            <!-- Eigene Felder des Anmeldeformulars -->
            <div v-for="feld in felder" :key="feld.label" class="dk-pub-field-group">
                <label class="dk-pub-label">
                    {{ feld.label }}<span v-if="feld.pflichtfeld" class="dk-pub-required"> *</span>
                </label>

                <!-- Text / Zahl / Datum -->
                <input v-if="['Text','Zahl','Datum'].includes(feld.feldtyp)"
                       :type="feldtypToInput(feld.feldtyp)"
                       v-model="antworten[feld.label]"
                       :required="!!feld.pflichtfeld"
                       class="dk-pub-input" />

                <!-- Ja-Nein -->
                <label v-else-if="feld.feldtyp === 'Ja-Nein'" class="dk-pub-check">
                    <input type="checkbox" v-model="antworten[feld.label]"
                           :required="!!feld.pflichtfeld"
                           class="dk-pub-checkbox" />
                    <span>Ja</span>
                </label>

                <!-- Auswahl -->
                <select v-else-if="feld.feldtyp === 'Auswahl'" v-model="antworten[feld.label]"
                        :required="!!feld.pflichtfeld"
                        class="dk-pub-input dk-pub-select">
                    <option value="">Bitte wählen…</option>
                    <option v-for="opt in optionen(feld)" :key="opt" :value="opt">{{ opt }}</option>
                </select>
            </div>

            <!-- Kinder-Sektion -->
            <div v-if="mitKinder" class="dk-pub-kinder-box">
                <h3 class="dk-pub-kinder-title">Kinder anmelden</h3>
                <div v-for="(kind, idx) in kinder" :key="idx" class="dk-pub-kinder-row">
                    <div class="dk-pub-kinder-col-4">
                        <input v-model="kind.vorname" placeholder="Vorname *"
                               class="dk-pub-input" />
                    </div>
                    <div class="dk-pub-kinder-col-4">
                        <input v-model="kind.nachname" placeholder="Nachname"
                               class="dk-pub-input" />
                    </div>
                    <div class="dk-pub-kinder-col-3">
                        <input v-model="kind.geburtstag" type="date" placeholder="Geburtstag"
                               class="dk-pub-input" />
                    </div>
                    <!-- UX1f (I2/N8): „×“ allein war ein 20-px-Zeichen ohne
                         Klickfläche und ohne Namen. Der Knopf entfernt DIESE
                         Zeile vom Formular (noch nichts gespeichert) und heißt
                         deshalb „Entfernen“ — mit sprechendem Namen für
                         Vorlesehilfen. Ab dem letzten Kind gibt es ihn nicht
                         mehr (nichts Ungültiges anbieten, I4). -->
                    <div class="dk-pub-kinder-col-1">
                        <DkButton v-if="kinder.length > 1"
                                  variant="ghost"
                                  size="md"
                                  class="dk-pub-remove-btn"
                                  :aria-label="`Kind ${idx + 1} entfernen`"
                                  @click="kinder.splice(idx,1)">Entfernen</DkButton>
                    </div>
                </div>
                <!-- UX1f: Ein Weg, der etwas HINZUFÜGT, ist ein echter Knopf
                     (secondary, umrandet) — bis hierher war er nur blauer Text
                     ohne Klickfläche. Die Hauptaktion der Seite bleibt „Anmelden“. -->
                <DkButton variant="secondary" size="md"
                          class="dk-pub-add-btn"
                          @click="kinder.push({vorname:'',nachname:'',geburtstag:''})">
                    + Kind hinzufügen
                </DkButton>
            </div>

            <!-- Dokument-Bestätigung -->
            <div v-if="dokumente.length" class="dk-pub-dokumente">
                <h3 class="dk-pub-dokumente-title">Dokumente</h3>
                <div v-for="dok in dokumente" :key="dok.label" class="dk-pub-dokument-row">
                    <label class="dk-pub-check">
                        <input type="checkbox" v-model="dokBestaetigt[dok.label]"
                               :required="!!dok.pflicht"
                               class="dk-pub-checkbox" />
                        <span>
                            <a v-if="dok.datei" :href="dok.datei" target="_blank" rel="noopener" class="dk-pub-dok-link">
                                {{ dok.label }}<span v-if="dok.pflicht"> *</span>
                            </a>
                            <span v-else>{{ dok.label }}<span v-if="dok.pflicht"> *</span></span>
                            gelesen und akzeptiert
                        </span>
                    </label>
                </div>
            </div>

            <!-- DSGVO / Einwilligung: der Text kommt vom Server
                 (window.__diakronos.texte) und ist GENAU der Wortlaut,
                 den der Server beim Absenden als Beleg speichert
                 (N9b/H-1, Art. 7 DSGVO). Reiner Text, kein HTML. -->
            <div class="dk-pub-dsgvo">
                <p v-if="willkommenstext" class="dk-pub-willkommen">{{ willkommenstext }}</p>
                <p class="dk-pub-dsgvo-text">{{ texte.einwilligung }}</p>
                <label class="dk-pub-check">
                    <input type="checkbox" v-model="form.dsgvo" class="dk-pub-checkbox" />
                    <span class="dk-pub-dsgvo-label">Ich stimme der Verarbeitung meiner Daten gemäß obiger Erklärung zu. *</span>
                </label>
                <details v-if="texte.datenschutzerklaerung" class="dk-pub-details">
                    <summary>Datenschutzerklärung</summary>
                    <p class="dk-pub-dsgvo-text">{{ texte.datenschutzerklaerung }}</p>
                </details>
                <details v-if="texte.aufbewahrung" class="dk-pub-details">
                    <summary>Wie lange werden meine Daten gespeichert?</summary>
                    <p class="dk-pub-dsgvo-text">{{ texte.aufbewahrung }}</p>
                </details>
            </div>

            <DkButton type="submit" variant="primary" block :loading="laden"
                      :disabled="vorschau"
                      :title="vorschau ? 'Vorschau — Absenden ist hier nicht möglich' : null">
                {{ vorschau ? 'Anmeldung absenden (Vorschau)' : 'Anmeldung absenden' }}
            </DkButton>
        </form>
    </div>
</template>

<script setup>
/**
 * DkAnmeldeformular — die Anzeige des Anmeldeformulars (REG-1b).
 *
 * Eingesetzt an zwei Stellen mit derselben Vorlage:
 *
 *   * oeffentliche Seite (`registrierung/App.vue`): `vorschau = false`,
 *     `token` = Token des Links; das Absenden geht an
 *     `registrierung.submit_registrierung`.
 *   * Editor-Vorschau (`Registrierung.vue`): `vorschau = true`; Token und
 *     Felder kommen aus dem gerade bearbeiteten Formular, abgeschickt wird
 *     nichts.
 *
 * Alle Angaben kommen als Eigenschaften herein — die Komponente liest NICHT
 * selbst aus `window.__diakronos`. So zeigt die Vorschau genau die Daten, die
 * im Editor stehen (auch ungespeicherte Aenderungen), und es gibt nur eine
 * Stelle, an der die Feldliste gepflegt wird.
 */
import { ref, reactive, computed } from 'vue'
// WEB-5b: Adressen unter dem Betriebs-Praefix (DIAKRONOS_BASE_PATH) bauen.
import { apiUrl } from '../../shared/basis.js'
// UX2g: EINE Quelle fuer angezeigte Fehlertexte (kein "Ein Fehler ist aufgetreten").
import { fehlertext } from '../../shared/fehlertexte.js'
// WEB-8b: CSRF-Ablehnung automatisch heilen (Token neu, 1 Wiederholung).
import { heileOderMelde, gastNachNeuladen, HINWEIS_NACH_NEULADEN } from '../../shared/csrf-heilung.js'
// DEP-1: eigene Bausteine statt frappe-ui (Button/FormControl/ErrorMessage).
import DkButton from '../../diakonos/components/ui/DkButton.vue'
import DkField from '../../diakonos/components/ui/DkField.vue'
import DkEingabe from '../../diakonos/components/ui/DkEingabe.vue'
import DkFehlertext from '../../diakonos/components/ui/DkFehlertext.vue'
// UX2f: Prüfregeln aus EINER Quelle (Feld und Absenden nutzen dieselben).
import { pflicht, email as emailRegel, laenge as laengeRegel } from '../../diakonos/composables/feldPruefung.mjs'

const props = defineProps({
    /** Formular im Vorschau-Modus: keine Absendung, Hinweis darueber. */
    vorschau: { type: Boolean, default: false },
    /** Registrierungstoken — nur fuer das Absenden noetig. */
    token: { type: String, default: '' },
    /** Formularfelder (Label, feldtyp, optionen, pflichtfeld …). */
    felder: { type: Array, default: () => [] },
    mitKinder: { type: [Number, String], default: 0 },
    dokumente: { type: Array, default: () => [] },
    /** Einwilligungs-/Datenschutztexte (`gemeinde.wirksame_texte`). */
    texte: { type: Object, default: () => ({}) },
    willkommenstext: { type: String, default: '' },
    /** REG-1a/REG-1b: Kopf des Formulars. */
    beschreibung: { type: String, default: '' },
    bannerBild: { type: String, default: '' },
    titel: { type: String, default: 'Mitglied werden' },
    subtitel: {
        type: String,
        default: 'Registriere dich als Gemeindemitglied. Alle Daten werden sicher gespeichert.',
    },
})

const emit = defineEmits(['erfolg'])

// Die Einwilligungstexte einmal auflösen — die Anzeige interpoliert sie und
// der Beleg nennt die FASSUNG, die der Person angezeigt wurde (N-1).
const texte = computed(() => props.texte || {})

const fehler = ref('')
const laden = ref(false)

// WEB-8e (E3): wurde die Seite gerade durch die Heilung neu geladen, steht der
// Merker in `sessionStorage`. `gastNachNeuladen()` gibt ihn genau EINMAL her.
// In der VORSCHAU nie: dort wurde nichts abgeschickt.
const nachNeuladen = ref(false)
const hinweisNachNeuladen = HINWEIS_NACH_NEULADEN
if (!props.vorschau) {
    try { nachNeuladen.value = gastNachNeuladen() } catch { nachNeuladen.value = false }
}

const form = reactive({
    vorname: '',
    nachname: '',
    email: '',
    telefon: '',
    geburtstag: '',
    dsgvo: false,
})

const antworten = reactive({})
const kinder = ref([{ vorname: '', nachname: '', geburtstag: '' }])
const dokBestaetigt = reactive({})

/** Optionen eines Auswahlfelds — Zeilenweise, leere Zeilen fallen weg. */
function optionen(feld) {
    return String(feld?.optionen || '').split('\n').map(z => z.trim()).filter(Boolean)
}

function feldtypToInput(typ) {
    return { Text: 'text', Zahl: 'number', Datum: 'date' }[typ] || 'text'
}

// UX2f: Regeln der Felder — dieselben Texte am Feld und beim Absenden.
const regelVorname = (wert) => pflicht('einen Vornamen')(wert) || laengeRegel({ max: 140, name: 'Der Vorname' })(wert)
const regelNachname = (wert) => pflicht('einen Nachnamen')(wert) || laengeRegel({ max: 140, name: 'Der Nachname' })(wert)
// Die E-Mail ist hier ausdrücklich freiwillig („empfohlen") — geprüft wird
// nur, was dasteht.
const regelEmail = (wert, f) => (String(wert ?? '').trim() ? emailRegel()(wert, f) : '')

async function absenden() {
    if (props.vorschau) return
    fehler.value = ''
    // UX2f: Die Feldmeldungen stehen am Feld (DkField). Bleibt dort alles
    // leer, sagt der Kasten oben, WAS fehlt — die Eingaben bleiben stehen.
    const vornameFehler = regelVorname(form.vorname)
    const nachnameFehler = regelNachname(form.nachname)
    if (vornameFehler || nachnameFehler) {
        fehler.value = vornameFehler && nachnameFehler
            ? 'Bitte Vor- und Nachnamen angeben.'
            : (vornameFehler || nachnameFehler)
        requestAnimationFrame(() => document.querySelector('.dk-pub-form [aria-invalid="true"]')?.focus())
        return
    }
    const emailFehler = regelEmail(form.email)
    if (emailFehler) {
        fehler.value = emailFehler
        return
    }
    if (!form.dsgvo) {
        fehler.value = 'Bitte stimme der Datenschutzerklärung zu.'
        return
    }

    for (const f of props.felder) {
        if (f.pflichtfeld && !antworten[f.label]) {
            fehler.value = `Bitte fülle das Feld "${f.label}" aus.`
            return
        }
    }

    for (const dok of props.dokumente) {
        if (dok.pflicht && !dokBestaetigt[dok.label]) {
            fehler.value = `Bitte bestätige: "${dok.label}"`
            return
        }
    }

    laden.value = true
    try {
        // WEB-8b: derselbe Aufruf als Funktion, damit eine CSRF-Ablehnung
        // still geheilt werden kann (frisches Token, GENAU eine Wiederholung,
        // sonst Force-Refresh). Der Token wird je Versuch frisch gelesen.
        const anfrage = () => fetch(apiUrl('diakronos.diakonos.api.registrierung.submit_registrierung'), {
            method: 'POST',
            credentials: 'same-origin',
            headers: {
                'Content-Type': 'application/json',
                'X-Frappe-CSRF-Token': document.querySelector('meta[name="csrf-token"]')?.content || window.csrf_token || '',
            },
            body: JSON.stringify({
                token: props.token,
                vorname:    form.vorname.trim(),
                nachname:   form.nachname.trim(),
                email:      form.email.trim(),
                telefon:    form.telefon.trim(),
                geburtstag: form.geburtstag || '',
                antworten: JSON.stringify(
                    Object.entries(antworten).map(([label, wert]) => ({ label, wert }))
                ),
                kinder: Number(props.mitKinder) ? JSON.stringify(
                    kinder.value.filter(k => k.vorname.trim())
                ) : '[]',
                // P0-4b: die Einwilligung wird serverseitig verlangt — ohne
                // dieses Feld entstuende kein gueltiger Nachweis.
                dsgvo: form.dsgvo,
                // N-1: die Fassung, die der Person angezeigt wurde.
                dsgvo_fassung: texte.einwilligung_fassung ?? '',
            }),
        })
        // `heileOderMelde` führt die Anfrage selbst aus und wiederholt sie nur
        // bei einer CSRF-Ablehnung (einmal). Ohne CSRF: unveränderte Antwort.
        // WEB-8c (R2): die erste Antwort wird mitgegeben — `heileOderMelde`
        // wiederholt nur bei einer CSRF-Ablehnung und dann genau einmal.
        // WEB-8d (M1): `gast: true` — hier gibt es KEIN Konto. Ein Token-Abruf
        // über `session.sitzung_status` endete für Gäste in 401 und schickte
        // sie zur Anmeldemaske. Stattdessen: höchstens ein Neuladen (frisches
        // Seiten-Token), danach die Meldung auf dieser Seite.
        const erste = await anfrage()
        const { res, data } = await heileOderMelde({ anfrage, res: erste, gast: true })
        if (!res.ok || data?.exc) {
            fehler.value = parseServerError(data)
            return
        }
        emit('erfolg')
    } catch (e) {
        // WEB-8c (R8) / WEB-8d (N3): Läuft gerade ein Neuladen, blitzt KEINE
        // Meldung auf (die Seite verschwindet).
        if (e?.neuLaden) return
        // WEB-8e (E2/E4): `e.meldung` heißt „Seite ist stehen geblieben" —
        // sofort der feste Gast-Hinweis (401/419 laden NICHT neu).
        if (e?.meldung && e?.hinweis) { fehler.value = e.hinweis; return }
        fehler.value = 'Verbindungsfehler. Bitte versuche es erneut.'
    } finally {
        laden.value = false
    }
}

function parseServerError(data) {
    // UX2g: kein „Ein Fehler ist aufgetreten" — der Fehlerkatalog nennt, was
    // passiert ist und was jetzt hilft. Ein Fachsatz des Servers bleibt stehen.
    if (!data) return fehlertext(null)
    // UXD-R27: der Serverfehlertext steht in `message` (Compat-Schicht:
    // `_error_response` -> {"message": …}); die Frappe-Schreibweise
    // `_server_messages` wird weiter unterstuetzt (Altbestand).
    if (typeof data.message === 'string' && data.message.trim()) {
        return data.message
    }
    try {
        const msgs = JSON.parse(data._server_messages || '[]')
        if (msgs.length) return JSON.parse(msgs[0]).message
    } catch {}
    return fehlertext(null)
}
</script>

<style>
/* REG-1b: Die Anzeige bringt ihre Stile selbst mit — dadurch sieht die
   Vorschau im Editor genauso aus wie die oeffentliche Seite, ohne dass die
   Stile doppelt gepflegt werden. Farben/Raumwerte NUR aus den Tokens.

   `dk-pub-*` heisst weiterhin „oeffentliche Anmeldeseite“: die Namen sind
   aus `registrierung/App.vue` uebernommen (dort standen sie bisher) und
   werden vom Regressionstest `tests/reg1a-registrierung.test.mjs` geprueft. */

.dk-pub-koerper { width: 100%; }

/* WEB-8e (E3): kurzer Hinweis nach dem automatischen Neuladen — nur Tokens
   (Hell- und Dunkelmodus), keine eigenen Farbwerte. */
.dk-pub-hinweis-neuladen {
  margin: 0 0 var(--sp-4) 0;
  padding: 8px 12px;
  border-left: 3px solid var(--warn);
  background: var(--warn-soft);
  border-radius: var(--radius-sm);
  font-size: var(--fs-sm);
  color: var(--text);
}
/* Das Banner steht ausserhalb des Formulars direkt in dieser Spalte; mit
   `display: block` und negativen Raendern zieht es bis an die Kartenkanten. */

/* REG-1b: Vorschau — sichtbarer Hinweis ueber dem Formular. */
.dk-pub-vorschau-hinweis {
  /* REG-1b: Der Hinweis steht UEBER dem Banner und wird von ihm nicht
     ueberdeckt — er ist die Begruendung, warum hier nichts abgeschickt wird. */
  position: relative;
  z-index: 1;
  margin: 0 0 var(--sp-4) 0;
  padding: 8px 12px;
  border-left: 3px solid var(--primary);
  background: var(--surface-2);
  border-radius: var(--radius-sm);
  font-size: var(--fs-sm);
  color: var(--text);
}

/* REG-1b: Das Banner liegt ueber dem Formularkopf und geht bis an die
   Innenkanten der Karte (der Formularkoerper ist ein Flex-Spalten-Element —
   `justify-self: stretch` greift, weil das Formular selbst ein Grid ist; ein
   negativer Rand allein reichte NICHT, das Bild blieb schmaler als die Karte).
   Die Werte sind die Innenabstaende der Karte (40 px, am Handy 24 px). */
.dk-pub-banner {
  display: block;
  width: calc(100% + 80px);
  max-width: calc(100% + 80px);
  margin: -40px -40px 24px -40px;
  max-height: 180px;
  object-fit: cover;
  border-radius: var(--radius-lg) var(--radius-lg) 0 0;
  box-sizing: content-box;
}

.dk-pub-beschreibung {
  margin: 0 0 20px 0;
  padding: 12px 14px;
  border-left: 3px solid var(--accent);
  background: var(--surface-2);
  border-radius: var(--radius-sm);
  color: var(--text);
  font-size: var(--fs-14);
  line-height: 1.55;
  white-space: pre-line;
}

/* Inhaltsumbruch, kein Layout: das Banner muss am schmalen Gerät über den
   kleineren Kartenrand (24 px statt 40 px) hinausreichen. */
@media (max-width: 640px) {
  .dk-pub-banner {
    width: calc(100% + 48px);
    max-width: calc(100% + 48px);
    margin: -24px -24px 20px -24px;
  }
}

.dk-pub-center { text-align: center; }

.dk-pub-icon-large { font-size: var(--fs-26); margin-bottom: 16px; }  /* UX1b: Symbolgroesse
   steht auf der groessten Stufe; 48 px waere keine Textgroesse. */

.dk-pub-title {
  font-size: var(--fs-20);
  font-weight: var(--fw-fett);
  color: var(--text);
  margin: 0 0 6px 0;
  letter-spacing: -0.01em;
}

.dk-pub-muted {
  font-size: var(--fs-14);
  color: var(--muted);
  margin: 0;
  line-height: 1.5;
}

.dk-pub-form { display: flex; flex-direction: column; gap: 14px; }

.dk-pub-grid-2 {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}
@media (max-width: 480px) {
  .dk-pub-grid-2 { grid-template-columns: 1fr; }
}

.dk-pub-field-group { display: flex; flex-direction: column; gap: 6px; }

.dk-pub-label {
  font-size: var(--fs-14);
  font-weight: var(--fw-mittel);
  color: var(--text);
}

.dk-pub-required { color: var(--err); }

.dk-pub-input {
  width: 100%;
  padding: 9px 12px;
  font-size: var(--fs-14);
  color: var(--text);
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  outline: none;
  transition: border-color 150ms var(--ease), box-shadow 150ms var(--ease);
  font-family: inherit;
}
.dk-pub-input:focus {
  border-color: var(--primary);
  box-shadow: 0 0 0 3px color-mix(in oklch, var(--primary) 12%, transparent);
}
.dk-pub-input::placeholder { color: var(--subtle); }

.dk-pub-select { appearance: auto; cursor: pointer; }

.dk-pub-check {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  font-size: var(--fs-14);
  color: var(--text);
}

.dk-pub-checkbox {
  width: 16px;
  height: 16px;
  accent-color: var(--primary);
  cursor: pointer;
  flex-shrink: 0;
}

.dk-pub-kinder-box {
  background: var(--surface-2);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.dk-pub-kinder-title { font-size: var(--fs-14); font-weight: var(--fw-fett); color: var(--text); margin: 0; }

.dk-pub-kinder-row {
  display: grid;
  grid-template-columns: 4fr 4fr 3fr 1fr;
  gap: 8px;
  align-items: end;
}
@media (max-width: 480px) {
  .dk-pub-kinder-row { grid-template-columns: 1fr 1fr; }
  .dk-pub-kinder-col-3, .dk-pub-kinder-col-1 { grid-column: span 1; }
}

/* UX1f: Höhe, Innenabstand, Rahmen und Farbe bringt `DkButton` mit; hier steht
   nur, wo die beiden Knöpfe der Kinder-Sektion sitzen. Der „Entfernen“-Knopf
   sitzt in der letzten Spalte der Zeile und schließt mit den Feldern ab. */
.dk-pub-remove-btn { justify-self: end; }
.dk-pub-add-btn { align-self: flex-start; }

.dk-pub-dokumente {
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 16px;
  font-size: var(--fs-14);
}
.dk-pub-dokumente-title {
  font-size: var(--fs-14);
  font-weight: var(--fw-fett);
  color: var(--muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin: 0 0 10px;
}
.dk-pub-dokument-row { margin-bottom: 8px; }
.dk-pub-dok-link { color: var(--primary); text-decoration: underline; }

.dk-pub-dsgvo {
  background: var(--surface-2);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 16px;
  font-size: var(--fs-14);
}

.dk-pub-dsgvo-text { color: var(--muted); margin: 0 0 12px 0; line-height: 1.5; white-space: pre-line; }

.dk-pub-dsgvo-label { font-weight: var(--fw-mittel); color: var(--text); }

/* N9b: der gepflegte Willkommenstext steht hervorgehoben ueber dem Formular. */
.dk-pub-willkommen {
  color: var(--text);
  font-weight: var(--fw-mittel);
  margin: 0 0 12px 0;
  line-height: 1.5;
  white-space: pre-line;
}

/* N9b: Datenschutzerklaerung/Aufbewahrung als aufklappbare Textbloecke
   (reiner Text, kein HTML). */
.dk-pub-details { margin-top: 8px; }
.dk-pub-details summary {
  cursor: pointer;
  color: var(--primary);
  font-weight: var(--fw-mittel);
  padding: 4px 0;
}
.dk-pub-details .dk-pub-dsgvo-text { margin: 8px 0 0 0; }
</style>
